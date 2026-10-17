import pytest
from alembic import command
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from test_migrations import drop, prepare

from app import migration_handler as runner


async def test_guarded_runner_compares_actual_revision_before_upgrade(engine, monkeypatch):
    schema, config = await prepare(engine, "0004")

    def factory(url, **kwargs):
        kwargs["connect_args"] = {
            **kwargs.get("connect_args", {}),
            "server_settings": {"search_path": schema},
        }
        return create_async_engine(url, **kwargs)

    monkeypatch.setattr(runner, "create_async_engine", factory)
    try:
        inspected = await runner.run({"action": "inspect_revision"})
        assert inspected == {"status": "ok", "revision": "0004", "read_only": True}
        result = await runner.run({"action": "migrate", "expected_from": "0004"})
        assert result["from_revision"] == "0004" and result["migrated_to"] == "0005"
        calls = []
        monkeypatch.setattr(command, "upgrade", lambda *args: calls.append(args))
        with pytest.raises(ValueError, match="approved source revision"):
            await runner.run({"action": "migrate", "expected_from": "0004"})
        assert calls == []
        async with engine.connect() as connection:
            await connection.execute(text(f'SET search_path TO "{schema}"'))
            assert (
                await connection.scalar(text("SELECT version_num FROM alembic_version")) == "0005"
            )
    finally:
        await drop(engine, schema)
