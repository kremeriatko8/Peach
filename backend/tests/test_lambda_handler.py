from app.lambda_handler import handler


def _function_url_event(path: str) -> dict:
    """The payload a Lambda function URL sends (format 2.0), trimmed to what Mangum reads."""
    host = "abc.lambda-url.us-east-1.on.aws"
    return {
        "version": "2.0",
        "routeKey": "$default",
        "rawPath": path,
        "rawQueryString": "",
        "headers": {"host": host},
        "requestContext": {
            "http": {"method": "GET", "path": path, "protocol": "HTTP/1.1", "sourceIp": "1.2.3.4"},
            "domainName": host,
            "stage": "$default",
            "requestId": "test",
        },
        "isBase64Encoded": False,
    }


def test_function_url_request_reaches_the_app() -> None:
    response = handler(_function_url_event("/health"), None)
    assert response["statusCode"] == 200
    assert response["body"] == '{"status":"ok"}'


def test_handler_survives_repeated_calls() -> None:
    for _ in range(2):
        assert handler(_function_url_event("/health"), None)["statusCode"] == 200


def test_authorization_header_reaches_dependency(tokens, monkeypatch):
    from app.db import get_session
    from app.main import app
    from app.services import items

    async def empty_session():
        yield None

    async def listing(*args, **kwargs):
        assert kwargs["owner_id"] == "user-a"
        return [], 0

    monkeypatch.setattr(items, "list_items", listing)
    app.dependency_overrides[get_session] = empty_session
    try:
        event = _function_url_event("/api/v1/items")
        event["headers"]["authorization"] = "Bearer " + tokens()
        assert handler(event, None)["statusCode"] == 200
        del event["headers"]["authorization"]
        assert handler(event, None)["statusCode"] == 401
    finally:
        app.dependency_overrides.clear()


def test_private_runner_rejects_http_events():
    import pytest

    from app.migration_handler import handler as migrate

    with pytest.raises(ValueError):
        migrate(_function_url_event("/health"), None)


def test_private_runner_rejects_source_head_without_actual_database_revision(monkeypatch):
    import pytest
    from alembic import command
    from sqlalchemy.exc import SQLAlchemyError

    from app.migration_handler import handler as migrate

    calls = []
    monkeypatch.setattr(command, "upgrade", lambda config, target: calls.append(target))
    # The local ORM test database has no Alembic revision. Source head is insufficient.
    with pytest.raises(SQLAlchemyError):
        migrate({"action": "migrate"}, None)
    assert calls == ["0003"]


def test_private_runner_propagates_migration_failure(monkeypatch):
    import pytest
    from alembic import command

    from app.migration_handler import handler as migrate

    def fail(config, target):
        raise RuntimeError("migration failed")

    monkeypatch.setattr(command, "upgrade", fail)
    with pytest.raises(RuntimeError, match="migration failed"):
        migrate({"action": "migrate"}, None)
