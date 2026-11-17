"""The private migration runner (still an AWS Lambda) rejects anything but explicit actions.

These moved here from test_lambda_handler.py when the HTTP Lambda adapter was removed in Lab 9.
"""

import pytest


def _http_event(path: str) -> dict:
    return {"version": "2.0", "rawPath": path, "requestContext": {"http": {"method": "GET"}}}


def test_private_runner_rejects_http_events():

    from app.migration_handler import handler as migrate

    with pytest.raises(ValueError):
        migrate(_http_event("/health"), None)


def test_private_runner_rejects_source_head_without_actual_database_revision(monkeypatch):
    from alembic import command
    from sqlalchemy.exc import SQLAlchemyError

    from app.migration_handler import handler as migrate

    calls = []
    monkeypatch.setattr(command, "upgrade", lambda config, target: calls.append(target))
    # The local ORM test database has no Alembic revision. Source head is insufficient.
    with pytest.raises(SQLAlchemyError):
        migrate({"action": "migrate"}, None)
    assert calls == ["0005"]


def test_private_runner_propagates_migration_failure(monkeypatch):
    from alembic import command

    from app.migration_handler import handler as migrate

    def fail(config, target):
        raise RuntimeError("migration failed")

    monkeypatch.setattr(command, "upgrade", fail)
    with pytest.raises(RuntimeError, match="migration failed"):
        migrate({"action": "migrate"}, None)
