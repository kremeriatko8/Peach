import json
from unittest.mock import Mock

import httpx
import pytest
from anthropic import APIConnectionError, APIStatusError, RateLimitError

from app.ai import agenda_lambda as handler
from app.ai.agenda import ParsedAgenda, ParsingError, Usage
from app.config import get_settings


@pytest.fixture
def parser(monkeypatch, tokens):
    monkeypatch.setenv("PARSER_ENABLED", "true")
    monkeypatch.setenv("PARSER_INPUT_USD_PER_MILLION", "5")
    monkeypatch.setenv("PARSER_OUTPUT_USD_PER_MILLION", "25")
    get_settings.cache_clear()
    handler._windows.clear()
    parse = Mock(return_value=(ParsedAgenda(items=[], language="en"), Usage(100, 20)))
    monkeypatch.setattr(handler, "parse_agenda", parse)
    return parse


def event(tokens, **payload):
    return {
        "requestContext": {"http": {"method": "POST"}},
        "headers": {"Authorization": "Bearer " + tokens()},
        "body": json.dumps(
            {"text": "Pricing", "today": "2026-10-12", "tz": "Europe/Kyiv", **payload}
        ),
    }


def test_auth_before_model_call(parser, tokens):
    for token in ("", "invalid", tokens(changes={"token_use": "id"}), tokens(changes={"exp": 1})):
        request = event(tokens)
        request["headers"] = {"authorization": "Bearer " + token}
        assert handler.handler(request, None)["statusCode"] == 401
    parser.assert_not_called()


@pytest.mark.parametrize(
    "payload,status",
    [
        ({"text": "x" * 10001}, 413),
        ({"text": " "}, 422),
        ({"today": "yesterday"}, 422),
        ({"tz": "fake/zone"}, 422),
        ({"text": 100}, 422),
        ({"unexpected": True}, 422),
    ],
)
def test_invalid_inputs_do_not_bill(parser, tokens, payload, status):
    assert handler.handler(event(tokens, **payload), None)["statusCode"] == status
    parser.assert_not_called()


def test_success_logs_no_content_or_token(parser, tokens, caplog):
    request = event(tokens, text="private source")
    result = handler.handler(request, None)
    assert result["statusCode"] == 200
    assert json.loads(result["body"])["estimated_cost_usd"] == 0.001
    log = json.loads(caplog.records[-1].message)
    assert log["user_id"] == "user-a" and log["prompt_version"] == "agenda-v1"
    assert log["input_tokens"] == 100 and log["latency_ms"] >= 0
    assert (
        "private source" not in caplog.text
        and request["headers"]["Authorization"] not in caplog.text
    )


def test_limit_and_disabled(parser, tokens, monkeypatch):
    for _ in range(3):
        assert handler.handler(event(tokens), None)["statusCode"] == 200
    assert handler.handler(event(tokens), None)["statusCode"] == 429
    assert parser.call_count == 3
    monkeypatch.setenv("PARSER_ENABLED", "false")
    get_settings.cache_clear()
    assert handler.handler(event(tokens), None)["statusCode"] == 503


def test_provider_errors(parser, tokens):
    request = httpx.Request("POST", "https://example.test")
    response = httpx.Response(429, request=request)
    errors = [
        (ParsingError(Usage(10, 20)), 422),
        (RateLimitError("secret", response=response, body=None), 429),
        (APIConnectionError(request=request), 503),
        (APIStatusError("secret", response=response, body=None), 502),
    ]
    for error, status in errors:
        handler._windows.clear()
        parser.side_effect = error
        result = handler.handler(event(tokens), None)
        assert result["statusCode"] == status and "secret" not in result["body"]


def test_base64_and_body_limits(parser, tokens):
    import base64

    request = event(tokens)
    request["body"] = base64.b64encode(request["body"].encode()).decode()
    request["isBase64Encoded"] = True
    assert handler.handler(request, None)["statusCode"] == 200
    request["body"] = "not base64"
    assert handler.handler(request, None)["statusCode"] == 422
    request["body"] = "x" * 100_001
    assert handler.handler(request, None)["statusCode"] == 413
    assert parser.call_count == 1


def test_missing_prices_fail_closed(parser, tokens, monkeypatch):
    monkeypatch.delenv("PARSER_INPUT_USD_PER_MILLION")
    get_settings.cache_clear()
    assert handler.handler(event(tokens), None)["statusCode"] == 503
    parser.assert_not_called()


def test_repair_connection_error_retains_observed_usage(parser, tokens, caplog):
    error = APIConnectionError(request=httpx.Request("POST", "https://example.test"))
    error.agenda_usage = Usage(120, 30)
    parser.side_effect = error
    assert handler.handler(event(tokens), None)["statusCode"] == 503
    log = json.loads(caplog.records[-1].message)
    assert log["input_tokens"] == 120 and log["output_tokens"] == 30
    assert log["usage_complete"] is False
