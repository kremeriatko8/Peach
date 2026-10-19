import json
from unittest.mock import Mock

import pytest
from app.ai import agenda_lambda as handler
from app.ai.agenda import ParsedAgenda, ParsingError, Usage
from app.config import get_settings
from botocore.exceptions import ClientError, EndpointConnectionError


@pytest.fixture
def parser(monkeypatch, tokens):
    monkeypatch.setenv("PARSER_ENABLED", "true")
    monkeypatch.setenv("PARSER_INPUT_USD_PER_MILLION", "0.06")
    monkeypatch.setenv("PARSER_OUTPUT_USD_PER_MILLION", "0.24")
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
    assert json.loads(result["body"])["estimated_cost_usd"] == 0.0000108
    log = json.loads(caplog.records[-1].message)
    assert "user_id" not in log and log["prompt_version"] == "agenda-v3"
    assert log["model"] == "amazon.nova-lite-v1:0"
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
    errors = [
        (ParsingError(Usage(10, 20)), 422),
        (
            ClientError(
                {"Error": {"Code": "ThrottlingException", "Message": "secret"}}, "Converse"
            ),
            429,
        ),
        (EndpointConnectionError(endpoint_url="https://secret"), 503),
        (
            ClientError(
                {"Error": {"Code": "AccessDeniedException", "Message": "secret"}}, "Converse"
            ),
            502,
        ),
        (
            ClientError(
                {"Error": {"Code": "ModelTimeoutException", "Message": "secret"}}, "Converse"
            ),
            503,
        ),
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
    error = EndpointConnectionError(endpoint_url="https://example.test")
    error.agenda_usage = Usage(120, 30)
    parser.side_effect = error
    assert handler.handler(event(tokens), None)["statusCode"] == 503
    log = json.loads(caplog.records[-1].message)
    assert log["input_tokens"] == 120 and log["output_tokens"] == 30
    assert log["usage_complete"] is False


def test_malformed_provider_response_is_private_fallback_with_partial_usage(parser, tokens, caplog):
    from app.ai.agenda import ProviderResponseError

    parser.side_effect = ProviderResponseError(Usage(107, 53))
    result = handler.handler(event(tokens, text="private lecture"), None)
    assert result["statusCode"] == 503
    assert "manually" in result["body"]
    assert "private lecture" not in result["body"] + caplog.text
    log = json.loads(caplog.records[-1].message)
    assert log["usage_complete"] is False
    assert (log["input_tokens"], log["output_tokens"]) == (107, 53)
    assert log["estimated_cost_usd"] == 0.00001914


@pytest.mark.parametrize("field", ["PARSER_INPUT_USD_PER_MILLION", "PARSER_OUTPUT_USD_PER_MILLION"])
def test_nonfinite_prices_disable_before_inference(parser, tokens, monkeypatch, field):
    monkeypatch.setenv(field, "inf")
    get_settings.cache_clear()
    assert handler.handler(event(tokens), None)["statusCode"] == 503
    parser.assert_not_called()


def test_real_mocked_parser_emits_complete_attempt_telemetry(parser, tokens, monkeypatch, caplog):
    from app.ai.agenda import parse_agenda
    from test_agenda_parser import response

    runtime = Mock()
    runtime.converse.side_effect = [response(count=0), response()]
    monkeypatch.setattr(
        handler, "parse_agenda", lambda *a, **kw: parse_agenda(*a, client=runtime, **kw)
    )
    request = event(tokens, text="private workshop details")
    assert handler.handler(request, None)["statusCode"] == 200
    log = json.loads(caplog.records[-1].message)
    assert log["provider_call_count"] == 2 and log["repair_attempts"] == 1
    assert [a["reason"] for a in log["attempts"]] == [
        "validation_failed",
        "source_fields_neutralized",
    ]
    assert log["usage_complete"] and log["cost_complete"]
    assert log["input_tokens"] == sum(a["input_tokens"] for a in log["attempts"]) == 200
    assert log["output_tokens"] == sum(a["output_tokens"] for a in log["attempts"]) == 100
    assert log["estimated_cost_usd"] == sum(a["estimated_cost_usd"] for a in log["attempts"])
    assert log["request_latency_ms"] >= log["latency_ms"] >= 0
    assert log["reason"] == "success"
    assert "user-a" not in caplog.text and "private workshop" not in caplog.text
    assert request["headers"]["Authorization"] not in caplog.text


@pytest.mark.parametrize(
    "bad,unknown",
    [
        ({}, True),
        ({"usage": {"inputTokens": 25, "outputTokens": 5}}, False),
    ],
)
def test_failed_envelope_telemetry_retains_observed_usage(
    parser, tokens, monkeypatch, caplog, bad, unknown
):
    from app.ai.agenda import parse_agenda

    runtime = Mock()
    runtime.converse.return_value = bad
    monkeypatch.setattr(
        handler, "parse_agenda", lambda *a, **kw: parse_agenda(*a, client=runtime, **kw)
    )
    assert handler.handler(event(tokens), None)["statusCode"] == 503
    log = json.loads(caplog.records[-1].message)
    assert log["provider_call_count"] == 1 and log["repair_attempts"] == 0
    assert log["reason"] == "malformed_response"
    assert log["usage_complete"] is (not unknown)
    assert log["cost_complete"] is (not unknown)
    assert (
        log["attempts"][0]["estimated_cost_usd"] is None
        if unknown
        else (log["attempts"][0]["estimated_cost_usd"] == 0.0000027)
    )


def test_repair_timeout_telemetry_has_unknown_second_usage(parser, tokens, monkeypatch, caplog):
    from app.ai.agenda import parse_agenda
    from botocore.exceptions import ReadTimeoutError
    from test_agenda_parser import response

    runtime = Mock()
    runtime.converse.side_effect = [response(count=0), ReadTimeoutError(endpoint_url="private")]
    monkeypatch.setattr(
        handler, "parse_agenda", lambda *a, **kw: parse_agenda(*a, client=runtime, **kw)
    )
    assert handler.handler(event(tokens), None)["statusCode"] == 503
    log = json.loads(caplog.records[-1].message)
    assert log["provider_call_count"] == 2 and log["repair_attempts"] == 1
    assert not log["usage_complete"] and not log["cost_complete"]
    assert log["input_tokens"] == 100 and log["output_tokens"] == 50
    assert log["attempts"][1]["input_tokens"] is None
    assert log["attempts"][1]["estimated_cost_usd"] is None


def test_no_inference_rejections_log_zero_calls(parser, tokens, caplog, monkeypatch):
    cases = [(event(tokens, text="x" * 10001), 413), (event(tokens, tz="unknown"), 422)]
    unauthorized = event(tokens)
    unauthorized["headers"] = {}
    cases.append((unauthorized, 401))
    for request, expected in cases:
        assert handler.handler(request, None)["statusCode"] == expected
        log = json.loads(caplog.records[-1].message)
        assert log["provider_call_count"] == log["repair_attempts"] == 0
        assert log["attempts"] == [] and log["estimated_cost_usd"] == 0
    monkeypatch.setenv("PARSER_ENABLED", "false")
    get_settings.cache_clear()
    assert handler.handler(event(tokens), None)["statusCode"] == 503
    assert json.loads(caplog.records[-1].message)["reason"] == "disabled"
    parser.assert_not_called()


def test_invalid_configuration_fails_closed_and_logs_without_sensitive_error(
    parser, tokens, monkeypatch, caplog
):
    monkeypatch.setattr(handler, "get_settings", Mock(side_effect=ValueError("private config")))
    result = handler.handler(event(tokens), None)
    assert result["statusCode"] == 503
    log = json.loads(caplog.records[-1].message)
    assert log["reason"] == "internal_error"
    assert log["provider_call_count"] == 0
    assert log["model"] is None
    assert "private config" not in caplog.text + result["body"]
    parser.assert_not_called()


def test_exact_injection_returns_manual_fallback_with_zero_provider_calls(
    parser, tokens, monkeypatch, caplog
):
    from app.ai.agenda import parse_agenda
    from test_agenda_grounding import INJECTION

    runtime = Mock()
    monkeypatch.setattr(
        handler, "parse_agenda", lambda *a, **kw: parse_agenda(*a, client=runtime, **kw)
    )
    result = handler.handler(event(tokens, text=INJECTION), None)
    assert result["statusCode"] == 422 and "manually" in result["body"]
    runtime.converse.assert_not_called()
    log = json.loads(caplog.records[-1].message)
    assert log["provider_call_count"] == 0 and log["estimated_cost_usd"] == 0
    assert log["reason"] == "source_instruction_rejected"
    assert "admin@example.com" not in caplog.text
