"""Exercise Alembic against a disposable schema inside the local test database."""

import os
import subprocess
import uuid

from sqlalchemy import text


async def test_additive_ownership_migration_preserves_legacy(engine):
    schema = "migration_" + uuid.uuid4().hex
    async with engine.begin() as connection:
        await connection.execute(text(f'CREATE SCHEMA "{schema}"'))
    # A separate subprocess avoids Alembic asyncio.run() inside pytest's event loop.
    # PGOPTIONS is not honored by asyncpg; use an isolated URL with server_settings
    # via the dedicated local test harness below.
    env = dict(os.environ, MIGRATION_TEST_SCHEMA=schema)
    code = """
import asyncio, os
from alembic import command
from alembic.config import Config
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy import text
from app.config import get_settings
from pathlib import Path
import tempfile
schema = os.environ['MIGRATION_TEST_SCHEMA']
# Reuse actual migration files but run them in an isolated test schema.
with tempfile.TemporaryDirectory() as folder:
    original = Path('migrations/env.py').read_text()
    replacement = "poolclass=pool.NullPool, "
    replacement += "connect_args={'server_settings': {'search_path': '" + schema + "'}},"
    original = original.replace('poolclass=pool.NullPool,', replacement)
    root = Path(folder)
    (root/'env.py').write_text(original)
    (root/'versions').symlink_to(Path('migrations/versions').resolve())
    config = Config('alembic.ini'); config.set_main_option('script_location', str(root))
    command.upgrade(config, '0002')
    async def check(insert=False):
        engine = create_async_engine(
            get_settings().database_url,
            connect_args={'server_settings': {'search_path':schema}}
        )
        async with engine.begin() as conn:
            if insert:
                query = "INSERT INTO items(name, status) VALUES ('Legacy', 'done')"
                await conn.execute(text(query))
            else:
                row = (await conn.execute(text('SELECT name,status,owner_id FROM items'))).one()
                assert tuple(row) == ('Legacy','done',None)
                assert await conn.scalar(text("SELECT version_num FROM alembic_version")) == '0003'
                query = "SELECT count(*) FROM pg_indexes WHERE schemaname = :schema "
                query += "AND indexname = 'ix_items_owner_id_created_at'"
                assert await conn.scalar(text(query), {'schema':schema}) == 1
        await engine.dispose()
    asyncio.run(check(True))
    from app.migration_handler import migrate
    async def verified_upgrade():
        engine = create_async_engine(get_settings().database_url, poolclass=NullPool,
            connect_args={'server_settings': {'search_path':schema}})
        original_upgrade = command.upgrade
        def broken_upgrade(config, revision):
            original_upgrade(config, revision)
            config.attributes['connection'].execute(text('DROP INDEX ix_items_owner_id_created_at'))
        command.upgrade = broken_upgrade
        try:
            async with engine.begin() as conn:
                await conn.run_sync(migrate, config)
        except ValueError:
            pass
        else:
            raise AssertionError('Failed verification must abort migration')
        finally:
            command.upgrade = original_upgrade
        async with engine.begin() as conn:
            assert await conn.scalar(text('SELECT version_num FROM alembic_version')) == '0002'
            result = await conn.run_sync(migrate, config)
            assert result['migrated_to'] == '0003'
            assert result['verification']['rows_before'] == 1
            assert result['verification']['rows_after'] == 1
            assert result['verification']['null_owner_count'] == 1
        await engine.dispose()
    asyncio.run(verified_upgrade())
    asyncio.run(check())
"""
    try:
        result = subprocess.run(["python", "-c", code], env=env, capture_output=True, text=True)
        assert result.returncode == 0, result.stderr
    finally:
        async with engine.begin() as connection:
            await connection.execute(text(f'DROP SCHEMA "{schema}" CASCADE'))
