from unittest.mock import AsyncMock, MagicMock

import pytest
from sqlalchemy.exc import DBAPIError

from app import migration_handler as runner


async def test_transient_connection_failure_retries_before_transaction(monkeypatch):
    connection = object()
    engine = MagicMock(connect=AsyncMock(side_effect=[TimeoutError(), connection]))
    sleep = AsyncMock()
    monkeypatch.setattr(runner.asyncio, "sleep", sleep)
    assert await runner._connect(engine) is connection
    assert engine.connect.await_count == 2
    sleep.assert_awaited_once_with(10)


async def test_authentication_failure_is_not_retried():
    error = DBAPIError(None, None, ValueError("authentication failed"))
    engine = MagicMock(connect=AsyncMock(side_effect=error))
    with pytest.raises(DBAPIError):
        await runner._connect(engine)
    assert engine.connect.await_count == 1


async def test_connection_budget_bounds_a_hanging_attempt(monkeypatch):
    async def hang():
        await runner.asyncio.sleep(10)

    monkeypatch.setattr(runner, "CONNECTION_BUDGET_SECONDS", 0.01)
    engine = MagicMock(connect=AsyncMock(side_effect=hang))
    with pytest.raises(TimeoutError):
        await runner._connect(engine)
    assert engine.connect.await_count == 1


async def test_transaction_failure_never_reconnects(monkeypatch):
    connection = MagicMock()
    connection.__aenter__ = AsyncMock(return_value=connection)
    connection.__aexit__ = AsyncMock(return_value=False)
    transaction = MagicMock()
    transaction.__aenter__ = AsyncMock(return_value=transaction)
    transaction.__aexit__ = AsyncMock(return_value=False)
    connection.aclose = AsyncMock()
    connection.begin.return_value = transaction
    connection.run_sync = AsyncMock(side_effect=TimeoutError("migration failed"))
    engine = MagicMock(dispose=AsyncMock())
    connect = AsyncMock(return_value=connection)
    monkeypatch.setattr(runner, "_connect", connect)
    monkeypatch.setattr(runner, "create_async_engine", lambda *args, **kwargs: engine)
    with pytest.raises(TimeoutError):
        await runner.run({"action": "migrate"})
    connect.assert_awaited_once_with(engine)
    connection.run_sync.assert_awaited_once()
    engine.dispose.assert_awaited_once()
