"""Private, explicit migration and narrowly scoped legacy cleanup operations."""

import asyncio
import re
from contextlib import aclosing
from pathlib import Path
from typing import Any

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect, text
from sqlalchemy.engine import Connection
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool

from app.config import get_settings
from app.models.meeting import Meeting

EXPECTED_REVISION = "0004"
CONNECTION_BUDGET_SECONDS = 180
CONNECTION_RETRY_DELAY_SECONDS = 10


async def _connect(engine):
    """Retry transient connection failures only, before any SQL transaction."""
    async with asyncio.timeout(CONNECTION_BUDGET_SECONDS):
        while True:
            try:
                return await engine.connect()
            except TimeoutError, ConnectionError:
                pass
            except DBAPIError as error:
                if not isinstance(error.orig, (TimeoutError, ConnectionError)):
                    raise
            await asyncio.sleep(CONNECTION_RETRY_DELAY_SECONDS)


def _check_sql(value: str) -> str:
    """Normalize PostgreSQL's reflected spelling of simple check expressions."""
    value = re.sub(r"::(?:text|character varying)", "", value.lower())
    value = re.sub(r"[\s()]", "", value)
    return value.replace("trimbothfrom", "trim").replace("btrim", "trim")


def _meetings_schema_valid(connection: Connection) -> bool:
    inspector = inspect(connection)
    if not inspector.has_table("meetings"):
        return False
    columns = {column["name"]: column for column in inspector.get_columns("meetings")}
    expected = Meeting.__table__
    if set(columns) != set(expected.columns.keys()):
        return False
    for column in expected.columns:
        actual = columns[column.name]
        if (
            actual["nullable"] != column.nullable
            or actual["type"]._type_affinity != column.type._type_affinity
            or getattr(actual["type"], "length", None) != getattr(column.type, "length", None)
            or getattr(actual["type"], "timezone", None) != getattr(column.type, "timezone", None)
        ):
            return False
    if inspector.get_pk_constraint("meetings")["constrained_columns"] != ["id"]:
        return False
    if any(
        _check_sql(columns[name].get("default") or "") != expected_default
        for name, expected_default in (
            ("id", "gen_random_uuid"),
            ("created_at", "now"),
            ("updated_at", "now"),
        )
    ):
        return False
    checks = {
        check["name"]: _check_sql(check["sqltext"])
        for check in inspector.get_check_constraints("meetings")
    }
    expected_checks = {
        constraint.name: _check_sql(str(constraint.sqltext))
        for constraint in expected.constraints
        if hasattr(constraint, "sqltext")
    }
    return checks == expected_checks and any(
        index["name"] == "ix_meetings_owner_id_starts_at"
        and index["column_names"] == ["owner_id", "starts_at"]
        and not index["unique"]
        for index in inspector.get_indexes("meetings")
    )


def migrate(connection: Connection, config: Config) -> dict[str, Any]:
    # Hold the legacy row set stable throughout the transactional migration.
    connection.execute(text("LOCK TABLE items IN SHARE ROW EXCLUSIVE MODE"))
    before = {
        str(row["id"]): dict(row)
        for row in connection.execute(text("SELECT items.* FROM items")).mappings()
    }
    meetings_before = {}
    if inspect(connection).has_table("meetings"):
        connection.execute(text("LOCK TABLE meetings IN SHARE ROW EXCLUSIVE MODE"))
        meetings_before = {
            str(row["id"]): dict(row)
            for row in connection.execute(text("SELECT * FROM meetings")).mappings()
        }
    config.attributes["connection"] = connection
    command.upgrade(config, EXPECTED_REVISION)
    revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
    columns = {column["name"] for column in inspect(connection).get_columns("items")}
    indexes = inspect(connection).get_indexes("items")
    index_ok = any(
        index["name"] == "ix_items_owner_id_created_at"
        and index["column_names"] == ["owner_id", "created_at"]
        for index in indexes
    )
    after = {
        str(row["id"]): dict(row)
        for row in connection.execute(text("SELECT * FROM items")).mappings()
    }
    preserved = before.keys() == after.keys() and all(
        all(after[item_id].get(key) == value for key, value in row.items())
        and ("owner_id" in row or after[item_id]["owner_id"] is None)
        for item_id, row in before.items()
    )
    meetings_ok = _meetings_schema_valid(connection)
    meetings_after = (
        {
            str(row["id"]): dict(row)
            for row in connection.execute(text("SELECT * FROM meetings")).mappings()
        }
        if meetings_ok
        else None
    )
    if (
        revision != [EXPECTED_REVISION]
        or "owner_id" not in columns
        or not index_ok
        or not preserved
        or not meetings_ok
        or meetings_before != meetings_after
    ):
        raise ValueError("Actual database migration verification failed; transaction rolled back")
    return {
        "status": "ok",
        "migrated_to": revision[0],
        "verification": {
            "owner_column": True,
            "ownership_index": True,
            "rows_preserved": True,
            "ownership_preserved": True,
            "meetings_schema": True,
            "meeting_rows_preserved": True,
            "meetings_before": len(meetings_before),
            "meetings_after": len(meetings_after),
            "rows_before": len(before),
            "rows_after": len(after),
            "null_owner_count": sum(row["owner_id"] is None for row in after.values()),
        },
    }


def cleanup_legacy_items(connection: Connection) -> dict[str, Any]:
    # Stabilize both legacy and owned rows until verification and commit finish.
    connection.execute(text("LOCK TABLE items IN SHARE ROW EXCLUSIVE MODE"))
    revision = connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
    if revision != ["0003"]:
        raise ValueError("Cleanup requires actual database revision 0003")
    owned_before = {
        str(row["id"]): dict(row)
        for row in connection.execute(
            text("SELECT * FROM items WHERE owner_id IS NOT NULL")
        ).mappings()
    }
    if not owned_before:
        raise ValueError("No authenticated tasks found; cleanup refused")
    before = connection.scalar(text("SELECT count(*) FROM items WHERE owner_id IS NULL"))
    deleted = (
        connection.execute(text("DELETE FROM items WHERE owner_id IS NULL RETURNING id"))
        .scalars()
        .all()
    )
    after = connection.scalar(text("SELECT count(*) FROM items WHERE owner_id IS NULL"))
    owned_after = {
        str(row["id"]): dict(row)
        for row in connection.execute(
            text("SELECT * FROM items WHERE owner_id IS NOT NULL")
        ).mappings()
    }
    revision_after = (
        connection.execute(text("SELECT version_num FROM alembic_version")).scalars().all()
    )
    if (
        len(deleted) != before
        or after != 0
        or owned_after != owned_before
        or revision_after != revision
    ):
        raise ValueError("Legacy cleanup verification failed; transaction rolled back")
    return {
        "status": "ok",
        "legacy_before": before,
        "deleted": len(deleted),
        "legacy_after": after,
        "owned_remaining": len(owned_after),
        "owned_rows_preserved": True,
        "database_revision": revision_after[0],
    }


async def run(event: dict[str, Any]) -> dict[str, Any]:
    if event not in ({"action": "migrate"}, {"action": "cleanup_legacy_items"}):
        raise ValueError("Only explicit migration or legacy cleanup invocations are accepted")
    engine = create_async_engine(
        get_settings().database_url, poolclass=NullPool, connect_args={"timeout": 30}
    )
    try:
        connection = await _connect(engine)
        async with aclosing(connection), connection.begin():
            if event == {"action": "cleanup_legacy_items"}:
                return await connection.run_sync(cleanup_legacy_items)
            root = Path(__file__).resolve().parent.parent
            config = Config(str(root / "alembic.ini"))
            config.set_main_option("script_location", str(root / "migrations"))
            return await connection.run_sync(migrate, config)
    finally:
        await engine.dispose()


def handler(event: dict[str, Any], context: Any) -> dict[str, Any]:
    return asyncio.run(run(event))
