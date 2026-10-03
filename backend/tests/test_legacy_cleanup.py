"""Exercise the private cleanup action transactionally in disposable local schemas."""

import uuid

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app import migration_handler

EVENT = {"action": "cleanup_legacy_items"}


@pytest.fixture
async def cleanup_database(engine, monkeypatch):
    schema = "cleanup_" + uuid.uuid4().hex
    async with engine.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
        await connection.execute(text(f'CREATE TABLE "{schema}".items (LIKE items INCLUDING ALL)'))
        await connection.execute(
            text(f'CREATE TABLE "{schema}".alembic_version (version_num text)')
        )
        await connection.execute(text(f"INSERT INTO \"{schema}\".alembic_version VALUES ('0003')"))
    local = create_async_engine(
        engine.url,
        poolclass=NullPool,
        connect_args={"server_settings": {"search_path": schema}},
    )
    monkeypatch.setattr(migration_handler, "create_async_engine", lambda *args, **kwargs: local)
    try:
        yield local
    finally:
        await local.dispose()
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))


async def seed(engine, owner=None):
    item_id = uuid.uuid4()
    async with engine.begin() as connection:
        await connection.execute(
            text(
                "INSERT INTO items(id,name,description,status,owner_id) "
                "VALUES (:id,'Test task','Preserve this text','in_progress',:owner)"
            ),
            {"id": item_id, "owner": owner},
        )
    return item_id


async def rows(engine):
    async with engine.connect() as connection:
        return {
            str(row["id"]): dict(row)
            for row in (await connection.execute(text("SELECT * FROM items"))).mappings()
        }


async def test_cleanup_preserves_all_owned_rows_and_revision(cleanup_database):
    db = cleanup_database
    await seed(db)
    await seed(db)
    owned_a = await seed(db, "user-a")
    owned_b = await seed(db, "user-b")
    before = await rows(db)
    result = await migration_handler.run(EVENT)
    assert result == {
        "status": "ok",
        "legacy_before": 2,
        "deleted": 2,
        "legacy_after": 0,
        "owned_remaining": 2,
        "owned_rows_preserved": True,
        "database_revision": "0003",
    }
    assert await rows(db) == {str(item_id): before[str(item_id)] for item_id in (owned_a, owned_b)}
    async with db.connect() as connection:
        assert await connection.scalar(text("SELECT version_num FROM alembic_version")) == "0003"


async def test_cleanup_is_idempotent_when_only_owned_rows_exist(cleanup_database):
    await seed(cleanup_database, "user-a")
    before = await rows(cleanup_database)
    result = await migration_handler.run(EVENT)
    assert result["legacy_before"] == result["deleted"] == result["legacy_after"] == 0
    assert await rows(cleanup_database) == before


@pytest.mark.parametrize("condition", ["no-owned", "wrong-revision"])
async def test_cleanup_refuses_invalid_baseline(cleanup_database, condition):
    db = cleanup_database
    await seed(db)
    if condition == "wrong-revision":
        await seed(db, "user-a")
        async with db.begin() as connection:
            await connection.execute(text("UPDATE alembic_version SET version_num='0002'"))
    before = await rows(db)
    with pytest.raises(ValueError):
        await migration_handler.run(EVENT)
    assert await rows(db) == before


@pytest.mark.parametrize("failure", ["skip-delete", "change-owned"])
async def test_cleanup_verification_failure_rolls_back_all_changes(cleanup_database, failure):
    db = cleanup_database
    await seed(db)
    await seed(db, "user-a")
    before = await rows(db)
    body = (
        "RETURN NULL;"
        if failure == "skip-delete"
        else "UPDATE items SET description='Unexpected change' "
        "WHERE owner_id IS NOT NULL; RETURN OLD;"
    )
    async with db.begin() as connection:
        await connection.execute(
            text(
                "CREATE FUNCTION interfere() RETURNS trigger LANGUAGE plpgsql AS $$ BEGIN "
                + body
                + " END $$"
            )
        )
        await connection.execute(
            text(
                "CREATE TRIGGER interfere BEFORE DELETE ON items "
                "FOR EACH ROW EXECUTE FUNCTION interfere()"
            )
        )
    with pytest.raises(ValueError, match="verification failed"):
        await migration_handler.run(EVENT)
    assert await rows(db) == before


@pytest.mark.parametrize(
    "event",
    [
        {"action": "cleanup_legacy_items", "where": "true"},
        {"action": "cleanup_legacy_items", "sql": "DELETE FROM items"},
        {"action": "cleanup"},
    ],
)
async def test_runner_rejects_extra_inputs_without_connecting(monkeypatch, event):
    def unexpected_connection(*args, **kwargs):
        raise AssertionError("Rejected event must not reach the database")

    monkeypatch.setattr(migration_handler, "create_async_engine", unexpected_connection)
    with pytest.raises(ValueError):
        await migration_handler.run(event)
