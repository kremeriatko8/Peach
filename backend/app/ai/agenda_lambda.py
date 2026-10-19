"""Function URL adapter. No database dependency; every POST authenticates first."""

import base64
import json
import logging
import threading
import time
from collections import OrderedDict
from datetime import date
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

import jwt
from botocore.exceptions import (
    ClientError,
    ConnectionClosedError,
    ConnectTimeoutError,
    EndpointConnectionError,
    ReadTimeoutError,
)
from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from app.ai.agenda import PROMPT_VERSION, ParsingError, Usage, parse_agenda
from app.ai.costs import estimate_cost
from app.auth import get_verifier
from app.config import get_settings

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
_lock = threading.Lock()
_windows: OrderedDict[str, list[float]] = OrderedDict()


class ParseRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=10_000)
    today: date
    tz: str = Field(min_length=1, max_length=100)

    @field_validator("today", mode="before")
    @classmethod
    def date_only(cls, value):
        if not isinstance(value, str) or len(value) != 10:
            raise ValueError("today must be YYYY-MM-DD")
        return value

    @field_validator("tz")
    @classmethod
    def timezone_exists(cls, value):
        try:
            ZoneInfo(value)
        except (ZoneInfoNotFoundError, ValueError) as exc:
            raise ValueError("Use an IANA timezone") from exc
        return value

    @field_validator("text")
    @classmethod
    def nonblank(cls, value):
        if not value.strip():
            raise ValueError("Paste some agenda text")
        return value


def limited(sub: str) -> bool:
    """Best-effort warm-instance limit, not a distributed spending cap."""
    now = time.monotonic()
    with _lock:
        prior = [stamp for stamp in _windows.pop(sub, []) if now - stamp < 60]
        if len(prior) >= get_settings().parser_requests_per_minute:
            _windows[sub] = prior
            return True
        _windows[sub] = [*prior, now]
        while len(_windows) > 1000:
            _windows.popitem(last=False)
        return False


def reply(status, detail):
    return {
        "statusCode": status,
        "headers": {
            "Content-Type": "application/json",
            "Cache-Control": "no-store",
            **({"Retry-After": "60"} if status == 429 else {}),
        },
        "body": json.dumps(detail, ensure_ascii=False),
    }


def handler(event, context):
    if event.get("requestContext", {}).get("http", {}).get("method") != "POST":
        return reply(405, {"detail": "Use POST"})
    headers = {key.lower(): value for key, value in event.get("headers", {}).items()}
    scheme, _, token = headers.get("authorization", "").partition(" ")
    if scheme.lower() != "bearer" or not token:
        return reply(401, {"detail": "Invalid or missing access token"})
    try:
        verifier = get_verifier()
    except ValueError, KeyError, TypeError, jwt.PyJWTError:
        return reply(503, {"detail": "Authentication configuration unavailable"})
    try:
        user = verifier.verify(token)
    except jwt.PyJWTError, ValueError, TypeError, KeyError, OverflowError:
        return reply(401, {"detail": "Invalid or missing access token"})
    body = event.get("body") or ""
    if not isinstance(body, str) or len(body) > 100_000:
        return reply(413, {"detail": "Agenda text must not exceed 10,000 characters"})
    try:
        if event.get("isBase64Encoded"):
            body = base64.b64decode(body, validate=True).decode("utf-8")
        payload = json.loads(body)
        if (
            isinstance(payload, dict)
            and isinstance(payload.get("text"), str)
            and len(payload["text"]) > 10_000
        ):
            return reply(413, {"detail": "Agenda text must not exceed 10,000 characters"})
        request = ParseRequest.model_validate(payload)
    except ValueError, TypeError, UnicodeError, ValidationError:
        return reply(422, {"detail": "Supply text, today (YYYY-MM-DD), and a valid IANA timezone"})
    settings = get_settings()
    if not settings.parser_enabled:
        return reply(503, {"detail": "Agenda parsing is unavailable. Enter your agenda manually."})
    if estimate_cost(1, 1) is None:
        return reply(503, {"detail": "Parser pricing configuration is unavailable"})
    if limited(user.sub):
        return reply(429, {"detail": "Too many requests. Wait a minute and try again."})
    start = time.monotonic()
    usage = Usage()
    status = 200
    response = None
    try:
        remaining = context.get_remaining_time_in_millis() / 1000 if context else 30
        parsed, usage = parse_agenda(
            request.text,
            request.today,
            request.tz,
            deadline=start + min(24, max(1, remaining - 2)),
        )
        response = {
            "agenda": parsed.model_dump(mode="json"),
            "model": settings.parser_model,
            "prompt_version": PROMPT_VERSION,
            "input_tokens": usage.input_tokens,
            "output_tokens": usage.output_tokens,
        }
    except ParsingError as error:
        usage = error.usage
        status, response = 422, {"detail": str(error)}
    except (
        ConnectionClosedError,
        ConnectTimeoutError,
        EndpointConnectionError,
        ReadTimeoutError,
    ) as error:
        usage = getattr(error, "agenda_usage", usage)
        status, response = (
            503,
            {"detail": "Model connection unavailable. Enter your agenda manually."},
        )
    except ClientError as error:
        usage = getattr(error, "agenda_usage", usage)
        code = error.response.get("Error", {}).get("Code", "")
        if code in {"ThrottlingException", "TooManyRequestsException"}:
            status, response = 429, {"detail": "The model is busy. Try again later."}
        elif code in {
            "ServiceUnavailableException",
            "ModelNotReadyException",
            "ModelTimeoutException",
        }:
            status, response = 503, {"detail": "Model unavailable. Enter your agenda manually."}
        else:
            status, response = 502, {"detail": "The model could not complete this request."}
    except Exception as error:
        usage = getattr(error, "agenda_usage", usage)
        # Never log exception text: providers can include source content in errors.
        status, response = 503, {"detail": "Parsing unavailable. Enter your agenda manually."}
    latency = round((time.monotonic() - start) * 1000)
    cost = estimate_cost(usage.input_tokens, usage.output_tokens)
    logger.info(
        json.dumps(
            {
                "event": "agenda_parse",
                "user_id": user.sub,
                "model": settings.parser_model,
                "prompt_version": PROMPT_VERSION,
                "input_tokens": usage.input_tokens,
                "output_tokens": usage.output_tokens,
                "latency_ms": latency,
                "estimated_cost_usd": cost,
                "status": status,
                "usage_complete": status in (200, 422),
            }
        )
    )
    if status == 200:
        response.update(latency_ms=latency, estimated_cost_usd=cost)
    return reply(status, response)
