import json
import re
from dataclasses import dataclass
from datetime import datetime
from urllib.parse import unquote_plus

from app.reporting.config import ReportingSettings
from app.reports.weeks import KYIV, parse_week, previous_week


@dataclass(frozen=True)
class Trigger:
    source: str
    week: str
    correlation_id: str
    message_id: str


def identifier(value: object) -> str:
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9:_./-]{1,256}", value):
        raise ValueError("Invalid correlation identifier")
    return value


def parse_trigger(payload: dict, message_id: str = "direct") -> Trigger:
    if not isinstance(payload, dict):
        raise ValueError("Report payload must be an object")
    source = payload.get("source")
    if source == "manual":
        if set(payload) != {"source", "week", "correlation_id"}:
            raise ValueError("Unexpected manual report fields")
        week = parse_week(payload["week"]).label
    elif source == "schedule":
        if set(payload) != {
            "source",
            "scheduled_time",
            "correlation_id",
            "schedule_arn",
            "attempt",
        }:
            raise ValueError("Unexpected scheduled report fields")
        if not isinstance(payload["scheduled_time"], str):
            raise ValueError("Scheduled time must be an ISO timestamp")
        timestamp = datetime.fromisoformat(payload["scheduled_time"].replace("Z", "+00:00"))
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("Scheduled time must include a timezone")
        year, number, _ = timestamp.astimezone(KYIV).isocalendar()
        week = previous_week(parse_week(f"{year:04d}-W{number:02d}")).label
        identifier(payload["schedule_arn"])
        if not re.fullmatch(r"[0-9]{1,4}", str(payload["attempt"])):
            raise ValueError("Invalid scheduler attempt")
    else:
        raise ValueError("Unknown report source")
    return Trigger(source, week, identifier(payload["correlation_id"]), identifier(message_id))


def builder_trigger(event: dict, settings: ReportingSettings) -> Trigger:
    if not isinstance(event, dict):
        raise ValueError("Invalid builder event")
    if "Records" not in event:
        if not settings.allow_direct:
            raise ValueError("Direct report events are disabled")
        return parse_trigger(event)
    if (
        set(event) != {"Records"}
        or not isinstance(event["Records"], list)
        or len(event["Records"]) != 1
    ):
        raise ValueError("Builder requires exactly one SQS record")
    record = event["Records"][0]
    if record.get("eventSource") != "aws:sqs" or record.get("eventSourceARN") != settings.queue_arn:
        raise ValueError("Unexpected report queue")
    body = record.get("body")
    if not isinstance(body, str) or len(body.encode()) > 8192:
        raise ValueError("Invalid report message body")

    def unique_fields(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate payload field")
            result[key] = value
        return result

    payload = json.loads(body, object_pairs_hook=unique_fields)
    return parse_trigger(payload, record.get("messageId"))


@dataclass(frozen=True)
class ObjectEvent:
    key: str
    week: str
    sequencer: str


def mailer_events(event: dict, settings: ReportingSettings) -> list[ObjectEvent]:
    records = event.get("Records") if isinstance(event, dict) else None
    if not isinstance(records, list) or not 1 <= len(records) <= 100:
        raise ValueError("Expected S3 ObjectCreated records")
    result = []
    for record in records:
        if record.get("eventSource") != "aws:s3" or not record.get("eventName", "").startswith(
            "ObjectCreated:"
        ):
            raise ValueError("Unexpected S3 event")
        s3 = record["s3"]
        if s3["bucket"]["name"] != settings.bucket:
            raise ValueError("Unexpected report bucket")
        key = unquote_plus(s3["object"]["key"], errors="strict")
        match = re.fullmatch(
            r"reports/" + re.escape(settings.scope) + r"/([0-9]{4}-W[0-9]{2})\.csv", key
        )
        if not match:
            raise ValueError("Unexpected report key")
        week = parse_week(match[1]).label
        sequencer = s3["object"].get("sequencer", "")
        if not re.fullmatch(r"[0-9A-Fa-f]{1,128}", sequencer):
            raise ValueError("Invalid S3 sequencer")
        result.append(ObjectEvent(key, week, sequencer))
    return result
