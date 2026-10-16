"""Exercise real Alembic and fail-closed verification in disposable local schemas."""

import uuid
from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text

from app.migration_handler import migrate


async def prepare(engine, revision):
    schema = "migration_" + uuid.uuid4().hex
    root = Path(__file__).resolve().parents[1]
    config = Config(str(root / "alembic.ini"))
    config.set_main_option("script_location", str(root / "migrations"))
    async with engine.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        await connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))

        def upgrade(conn):
            config.attributes["connection"] = conn
            command.upgrade(config, revision)

        await connection.run_sync(upgrade)
        await connection.execute(text("INSERT INTO items(name,status) VALUES ('Legacy','done')"))
        if revision == "0003":
            await connection.execute(
                text(
                    "INSERT INTO items(name,status,owner_id) "
                    "VALUES ('Owned','in_progress','user-a')"
                )
            )
    return schema, config


async def drop(engine, schema):
    async with engine.begin() as connection:
        await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))


@pytest.mark.parametrize("revision", ["0002", "0003"])
async def test_additive_upgrade_preserves_all_tasks_and_ownership(engine, revision):
    schema, config = await prepare(engine, revision)
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            before = [
                dict(row)
                for row in (
                    await connection.execute(text("SELECT * FROM items ORDER BY name"))
                ).mappings()
            ]
            result = await connection.run_sync(migrate, config)
            assert result["migrated_to"] == "0005"
            assert result["verification"]["meetings_schema"] is True
            assert result["verification"]["rows_before"] == len(before)
            assert result["verification"]["rows_after"] == len(before)
            after = [
                dict(row)
                for row in (
                    await connection.execute(text("SELECT * FROM items ORDER BY name"))
                ).mappings()
            ]
            for old, new in zip(before, after, strict=True):
                assert all(new[key] == value for key, value in old.items())
                assert new["owner_id"] == old.get("owner_id")
            assert await connection.scalar(text("SELECT count(*) FROM meetings")) == 0
            await connection.execute(
                text(
                    "INSERT INTO meetings(owner_id,title,starts_at,"
                    "duration_minutes,participant_count) "
                    "VALUES ('user-a','Preserve me','2026-10-09T07:00:00Z',30,2)"
                )
            )
            meeting_before = dict(
                (await connection.execute(text("SELECT * FROM meetings"))).mappings().one()
            )
            repeat = await connection.run_sync(migrate, config)
            assert (
                repeat["verification"]["meetings_before"]
                == repeat["verification"]["meetings_after"]
                == 1
            )
            assert (
                dict((await connection.execute(text("SELECT * FROM meetings"))).mappings().one())
                == meeting_before
            )
    finally:
        await drop(engine, schema)


@pytest.mark.parametrize(
    "corruption",
    [
        "ALTER TABLE agendas DROP CONSTRAINT ck_agendas_items",
        "ALTER TABLE agendas ALTER COLUMN language DROP NOT NULL",
        "DROP INDEX ix_items_owner_id_created_at",
        "UPDATE items SET name = 'Changed'",
        "UPDATE items SET owner_id = 'user-b' WHERE owner_id IS NOT NULL",
        "DROP INDEX ix_meetings_owner_id_starts_at",
        "ALTER TABLE meetings ALTER COLUMN owner_id DROP NOT NULL",
        "ALTER TABLE meetings ALTER COLUMN starts_at TYPE timestamp without time zone",
        "ALTER TABLE meetings ALTER COLUMN created_at DROP DEFAULT",
        "ALTER TABLE meetings ALTER COLUMN id SET DEFAULT "
        "'00000000-0000-0000-0000-000000000000'::uuid",
        "ALTER TABLE meetings DROP CONSTRAINT ck_meetings_duration",
        "ALTER TABLE meetings DROP CONSTRAINT ck_meetings_duration; "
        "ALTER TABLE meetings ADD CONSTRAINT ck_meetings_duration "
        "CHECK (duration_minutes > 0)",
        "INSERT INTO meetings(owner_id,title,starts_at,"
        "duration_minutes,participant_count) "
        "VALUES ('user-a','Unexpected','2026-10-09T07:00:00Z',30,2)",
        "UPDATE alembic_version SET version_num = 'wrong'",
    ],
)
async def test_failed_schema_or_data_verification_rolls_back(engine, monkeypatch, corruption):
    schema, config = await prepare(engine, "0003")
    original_upgrade = command.upgrade

    def broken_upgrade(config, revision):
        original_upgrade(config, revision)
        for statement in corruption.split(";"):
            config.attributes["connection"].execute(text(statement))

    try:
        monkeypatch.setattr(command, "upgrade", broken_upgrade)
        with pytest.raises(ValueError, match="verification failed"):
            async with engine.begin() as connection:
                await connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                await connection.run_sync(migrate, config)
        async with engine.begin() as connection:
            await connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            assert (
                await connection.scalar(text("SELECT version_num FROM alembic_version")) == "0003"
            )
            assert not await connection.run_sync(lambda conn: inspect(conn).has_table("meetings"))
            rows = (
                await connection.execute(text("SELECT name,owner_id FROM items ORDER BY name"))
            ).all()
            assert rows == [("Legacy", None), ("Owned", "user-a")]
    finally:
        await drop(engine, schema)


async def test_existing_meeting_changes_fail_verification(engine, monkeypatch):
    schema, config = await prepare(engine, "0003")
    original_upgrade = command.upgrade
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            await connection.run_sync(migrate, config)
            await connection.execute(
                text(
                    "INSERT INTO meetings(owner_id,title,starts_at,"
                    "duration_minutes,participant_count) "
                    "VALUES ('user-a','Original','2026-10-09T07:00:00Z',30,2)"
                )
            )

        def broken_upgrade(config, revision):
            original_upgrade(config, revision)
            config.attributes["connection"].execute(text("UPDATE meetings SET owner_id = 'user-b'"))

        monkeypatch.setattr(command, "upgrade", broken_upgrade)
        with pytest.raises(ValueError, match="verification failed"):
            async with engine.begin() as connection:
                await connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                await connection.run_sync(migrate, config)
        async with engine.begin() as connection:
            await connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            assert await connection.scalar(text("SELECT owner_id FROM meetings")) == "user-a"
    finally:
        await drop(engine, schema)


async def test_upgrade_0004_and_repeated_run_preserve_agendas(engine, monkeypatch):
    schema, config = await prepare(engine, "0004")
    try:
        async with engine.begin() as connection:
            await connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            await connection.run_sync(migrate, config)
            await connection.execute(
                text(
                    "INSERT INTO meetings(owner_id,title,starts_at,"
                    "duration_minutes,participant_count) "
                    "VALUES ('user-a','Agenda parent','2026-10-09T07:00:00Z',30,2)"
                )
            )
            await connection.execute(
                text(
                    "INSERT INTO agendas(meeting_id,items,action_items,language,ai_suggestion) "
                    "SELECT id,'[{\"topic\":\"Keep\"}]'::jsonb,'[]'::jsonb,'en',"
                    '\'{"model":"original"}\'::jsonb FROM meetings'
                )
            )
            result = await connection.run_sync(migrate, config)
            assert result["verification"]["agendas_before"] == 1
            assert result["verification"]["agendas_after"] == 1
        original = command.upgrade

        def corrupt(config, target):
            original(config, target)
            config.attributes["connection"].execute(text("UPDATE agendas SET language='changed'"))

        monkeypatch.setattr(command, "upgrade", corrupt)
        with pytest.raises(ValueError, match="verification failed"):
            async with engine.begin() as connection:
                await connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
                await connection.run_sync(migrate, config)
        async with engine.begin() as connection:
            await connection.execute(text(f'SET LOCAL search_path TO "{schema}"'))
            assert await connection.scalar(text("SELECT language FROM agendas")) == "en"
    finally:
        await drop(engine, schema)
