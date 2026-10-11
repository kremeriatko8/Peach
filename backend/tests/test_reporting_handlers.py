import io
import json
from dataclasses import replace
from email import policy
from email.parser import BytesParser
from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError

from app.reporting import builder, mailer
from app.reporting.config import ReportingSettings
from app.reporting.events import builder_trigger, mailer_events, parse_trigger


@pytest.fixture
def settings():
    return ReportingSettings(
        "user-a",
        "lab-scope",
        "peach-reports-test",
        "arn:aws:sqs:us-east-1:123456789012:peach-report-work",
        "recipient@example.test",
        "sender@example.test",
        "mail-state",
    )


def error(code):
    return ClientError({"Error": {"Code": code, "Message": "synthetic failure"}}, "Test")


def manual(week="2026-W40"):
    return {"source": "manual", "week": week, "correlation_id": "test-correlation"}


def schedule(timestamp="2026-10-05T04:00:00Z"):
    return {
        "source": "schedule",
        "scheduled_time": timestamp,
        "correlation_id": "execution-1",
        "schedule_arn": "arn:aws:scheduler:us-east-1:123456789012:schedule/peach-reports/weekly",
        "attempt": "1",
    }


def sqs(settings, payload=None):
    return {
        "Records": [
            {
                "eventSource": "aws:sqs",
                "eventSourceARN": settings.queue_arn,
                "messageId": "message-1",
                "body": json.dumps(payload or manual()),
            }
        ]
    }


def s3event(settings, key=None):
    return {
        "Records": [
            {
                "eventSource": "aws:s3",
                "eventName": "ObjectCreated:Put",
                "s3": {
                    "bucket": {"name": settings.bucket},
                    "object": {
                        "key": key or "reports%2Flab-scope%2F2026-W40.csv",
                        "sequencer": "A1",
                    },
                },
            }
        ]
    }


@pytest.mark.parametrize(
    ("timestamp", "expected"),
    [
        ("2026-10-05T04:00:00Z", "2026-W40"),
        ("2021-01-04T05:00:00Z", "2020-W53"),
        ("2026-03-30T04:00:00Z", "2026-W13"),
        ("2026-10-26T05:00:00Z", "2026-W43"),
        ("2026-10-04T21:00:00Z", "2026-W40"),
    ],
)
def test_schedule_uses_scheduled_time_not_processing_time(timestamp, expected):
    assert parse_trigger(schedule(timestamp)).week == expected


def test_sqs_and_direct_paths(settings):
    trigger = builder_trigger(sqs(settings), settings)
    assert trigger.week == "2026-W40" and trigger.message_id == "message-1"
    with pytest.raises(ValueError, match="disabled"):
        builder_trigger(manual(), settings)
    assert builder_trigger(schedule(), replace(settings, allow_direct=True)).week == "2026-W40"


@pytest.mark.parametrize("field", ["owner_sub", "owner_id", "recipient", "bucket", "sql"])
def test_untrusted_target_fields_rejected(settings, field):
    with pytest.raises(ValueError):
        builder_trigger(sqs(settings, {**manual(), field: "attacker"}), settings)


@pytest.mark.parametrize(
    "payload",
    [
        {**manual(), "week": "2025-W53"},
        {**manual(), "source": "unknown"},
        {**manual(), "correlation_id": "injected\nlog"},
        {**schedule(), "scheduled_time": "2026-10-05T07:00:00"},
        {**schedule(), "attempt": "bad"},
        {**schedule(), "owner_id": "other"},
    ],
)
def test_bad_payloads(payload):
    with pytest.raises((ValueError, TypeError)):
        parse_trigger(payload)


def test_wrong_queue_batch_and_duplicate_json_fields(settings):
    event = sqs(settings)
    event["Records"][0]["eventSourceARN"] = "other"
    with pytest.raises(ValueError):
        builder_trigger(event, settings)
    event = sqs(settings)
    event["Records"] *= 2
    with pytest.raises(ValueError):
        builder_trigger(event, settings)
    event = sqs(settings)
    event["Records"][0]["body"] = '{"source":"manual","source":"schedule"}'
    with pytest.raises(ValueError, match="Duplicate"):
        builder_trigger(event, settings)


def test_builder_publishes_scoped_csv_and_no_private_logs(settings, caplog):
    s3 = Mock()

    async def generate(config, week):
        assert config.owner_sub == "user-a" and week == "2026-W40"
        return b"private meeting title"

    assert builder.handle(sqs(settings), settings, s3, generate)["result"] == "published"
    values = s3.put_object.call_args.kwargs
    assert values["Key"] == "reports/lab-scope/2026-W40.csv"
    assert values["IfNoneMatch"] == "*" and values["ServerSideEncryption"] == "AES256"
    assert "private meeting title" not in caplog.text and "user-a" not in caplog.text


@pytest.mark.parametrize(
    ("code", "duplicate"),
    [
        ("PreconditionFailed", True),
        ("412", True),
        ("ConditionalRequestConflict", False),
        ("AccessDenied", False),
    ],
)
def test_builder_duplicate_vs_retry(settings, code, duplicate):
    s3 = Mock()
    s3.put_object.side_effect = error(code)

    async def generate(*args):
        return b"CSV"

    if duplicate:
        assert builder.handle(sqs(settings), settings, s3, generate)["result"] == "duplicate"
    else:
        with pytest.raises(ClientError):
            builder.handle(sqs(settings), settings, s3, generate)


def test_builder_database_failure_is_not_acknowledged(settings):
    s3 = Mock()

    async def generate(*args):
        raise RuntimeError("synthetic database failure")

    with pytest.raises(RuntimeError):
        builder.handle(sqs(settings), settings, s3, generate)
    s3.put_object.assert_not_called()


def test_s3_key_decoding(settings):
    parsed = mailer_events(s3event(settings), settings)[0]
    assert parsed.key == settings.key("2026-W40")


@pytest.mark.parametrize(
    "key",
    [
        "reports/other/2026-W40.csv",
        "reports/lab-scope/2025-W53.csv",
        "reports/lab-scope/../2026-W40.csv",
        "reports/lab-scope/2026-W40.csv.exe",
        "reports%2Flab-scope%2F2026-W40+file.csv",
    ],
)
def test_bad_s3_keys(settings, key):
    with pytest.raises(ValueError):
        mailer_events(s3event(settings, key), settings)


def test_s3_wrong_bucket_and_event_rejected(settings):
    event = s3event(settings)
    event["Records"][0]["s3"]["bucket"]["name"] = "other"
    with pytest.raises(ValueError):
        mailer_events(event, settings)
    event = s3event(settings)
    event["Records"][0]["eventName"] = "ObjectRemoved:Delete"
    with pytest.raises(ValueError):
        mailer_events(event, settings)


class MemoryDdb:
    """Minimal conditional-state model: each update is atomic, as in DynamoDB."""

    def __init__(self):
        self.items = {}
        self.fail_finish = False

    def update_item(self, **kwargs):
        key = kwargs["Key"]["report_id"]["S"]
        values = kwargs["ExpressionAttributeValues"]
        item = self.items.get(key)
        if ":lease" in values:
            now = int(values[":now"]["N"])
            if item and (item["state"]["S"] == "SENT" or int(item["lease_until"]["N"]) > now):
                raise error("ConditionalCheckFailedException")
            self.items[key] = {
                "state": {"S": "PENDING"},
                "claim_token": values[":token"],
                "lease_until": values[":lease"],
            }
        else:
            if (
                not item
                or item["claim_token"] != values[":token"]
                or item["state"]["S"] != "PENDING"
            ):
                raise error("ConditionalCheckFailedException")
            if ":zero" in values:
                item["lease_until"] = {"N": "0"}
            else:
                if self.fail_finish:
                    raise error("InternalServerError")
                item["state"] = {"S": "SENT"}
                item["ses_message_id"] = values[":message"]
                item.pop("lease_until")
        return {}

    def get_item(self, **kwargs):
        assert kwargs["ConsistentRead"] is True
        return {"Item": self.items.get(kwargs["Key"]["report_id"]["S"], {})}


def clients(content=b'Title,Minutes\r\n"Kyiv, planning",60\r\n'):
    s3, ses, ddb = Mock(), Mock(), MemoryDdb()
    s3.get_object.side_effect = lambda **kwargs: {
        "Body": io.BytesIO(content),
        "ContentLength": len(content),
        "Metadata": {"correlation-id": "execution-1"},
    }
    ses.send_raw_email.return_value = {"MessageId": "ses-1"}
    return s3, ses, ddb


def test_mime_and_ordinary_duplicate_suppression(settings, caplog):
    s3, ses, ddb = clients()
    event = s3event(settings)
    assert mailer.handle(event, settings, s3, ses, ddb, clock=lambda: 100)["results"] == ["sent"]
    assert mailer.handle(event, settings, s3, ses, ddb, clock=lambda: 200)["results"] == [
        "duplicate"
    ]
    ses.send_raw_email.assert_called_once()
    args = ses.send_raw_email.call_args.kwargs
    parsed = BytesParser(policy=policy.default).parsebytes(args["RawMessage"]["Data"])
    assert args["Destinations"] == [settings.recipient]
    attachment = list(parsed.iter_attachments())[0]
    assert attachment.get_filename() == "2026-W40.csv"
    assert attachment.get_content_type() == "text/csv"
    assert attachment.get_payload(decode=True) == b'Title,Minutes\r\n"Kyiv, planning",60\r\n'
    assert "Kyiv, planning" not in caplog.text and settings.recipient not in caplog.text


def test_lease_concurrency_expiry_and_stale_worker_protection():
    ddb = MemoryDdb()
    assert mailer.acquire(ddb, "table", "key", "first", 100)
    with pytest.raises(mailer.LeaseBusyError):
        mailer.acquire(ddb, "table", "key", "second", 101)
    assert mailer.acquire(ddb, "table", "key", "second", 280)
    mailer.release(ddb, "table", "key", "first")
    assert ddb.items["key"]["lease_until"]["N"] == "460"
    with pytest.raises(ClientError):
        mailer.finish(ddb, "table", "key", "first", "ses-old")
    mailer.finish(ddb, "table", "key", "second", "ses-new")
    assert not mailer.acquire(ddb, "table", "key", "third", 999999)


def test_ses_failure_releases_claim_and_can_retry(settings):
    s3, ses, ddb = clients()
    ses.send_raw_email.side_effect = error("MessageRejected")
    with pytest.raises(ClientError):
        mailer.handle(s3event(settings), settings, s3, ses, ddb, clock=lambda: 100)
    assert next(iter(ddb.items.values()))["lease_until"]["N"] == "0"
    ses.send_raw_email.side_effect = None
    assert mailer.handle(s3event(settings), settings, s3, ses, ddb, clock=lambda: 101)[
        "results"
    ] == ["sent"]


def test_ses_unknown_outcome_and_finish_failure_keep_recoverable_lease(settings):
    s3, ses, ddb = clients()
    ses.send_raw_email.side_effect = TimeoutError("synthetic timeout")
    with pytest.raises(TimeoutError):
        mailer.handle(s3event(settings), settings, s3, ses, ddb, clock=lambda: 100)
    assert next(iter(ddb.items.values()))["lease_until"]["N"] == "280"
    ses.send_raw_email.side_effect = None
    ddb.fail_finish = True
    with pytest.raises(ClientError):
        mailer.handle(s3event(settings), settings, s3, ses, ddb, clock=lambda: 280)
    ddb.fail_finish = False
    assert mailer.handle(s3event(settings), settings, s3, ses, ddb, clock=lambda: 460)[
        "results"
    ] == ["sent"]
    assert (
        ses.send_raw_email.call_count == 3
    )  # Explicitly demonstrates the non-exactly-once boundary.


@pytest.mark.parametrize("content", [b"\xff", b"x" * (mailer.MAX_ATTACHMENT_BYTES + 1)])
def test_bad_attachment_never_sends_and_releases(settings, content):
    s3, ses, ddb = clients(content)
    with pytest.raises(ValueError):
        mailer.handle(s3event(settings), settings, s3, ses, ddb, clock=lambda: 100)
    ses.send_raw_email.assert_not_called()
    assert next(iter(ddb.items.values()))["lease_until"]["N"] == "0"


def test_full_event_validated_before_sending(settings):
    event = s3event(settings)
    bad = s3event(settings, "reports/other/2026-W40.csv")["Records"][0]
    event["Records"].append(bad)
    s3, ses, ddb = clients()
    with pytest.raises(ValueError):
        mailer.handle(event, settings, s3, ses, ddb)
    s3.get_object.assert_not_called()
    ses.send_raw_email.assert_not_called()


def test_settings_enforce_timezone_and_owner_is_not_required_by_mailer(monkeypatch):
    for name, value in {
        "REPORT_SCOPE_ID": "lab-scope",
        "REPORT_BUCKET": "peach-reports-test",
        "REPORT_TIMEZONE": "Europe/Kyiv",
    }.items():
        monkeypatch.setenv(name, value)
    monkeypatch.delenv("REPORT_OWNER_SUB", raising=False)
    assert ReportingSettings.from_env().owner_sub == "mailer-no-database-access"
    with pytest.raises(KeyError):
        ReportingSettings.from_env(builder=True)
    monkeypatch.setenv("REPORT_TIMEZONE", "UTC")
    with pytest.raises(ValueError):
        ReportingSettings.from_env()


def test_concurrent_builders_publish_only_once(settings):
    from concurrent.futures import ThreadPoolExecutor
    from threading import Barrier, Lock

    barrier, lock, published = Barrier(2), Lock(), {}

    class AtomicS3:
        def put_object(self, **kwargs):
            with lock:
                if kwargs["Key"] in published:
                    raise error("PreconditionFailed")
                published[kwargs["Key"]] = kwargs["Body"]

    async def generate(*args):
        barrier.wait(timeout=5)
        return b"CSV"

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(builder.handle, sqs(settings), settings, AtomicS3(), generate)
            for _ in range(2)
        ]
        assert sorted(f.result()["result"] for f in futures) == ["duplicate", "published"]
    assert list(published) == [settings.key("2026-W40")]


async def test_aws_generator_reuses_core_with_disposable_read_only_database(settings, engine):
    # conftest has already verified and selected the isolated *_test database.
    result = await builder.generate(settings, "2026-W40")
    assert result.startswith(b"Report metadata")
    assert b"ISO week,2026-W40" in result
    assert b"Object key,reports/lab-scope/2026-W40.csv" in result
    assert b"Tasks summary" in result


def test_handler_errors_are_sanitized_but_still_retry(monkeypatch):
    import boto3

    monkeypatch.setattr(boto3, "client", lambda *args: Mock())
    monkeypatch.setattr(
        builder.ReportingSettings,
        "from_env",
        lambda **kwargs: (_ for _ in ()).throw(ValueError("private credential")),
    )
    with pytest.raises(RuntimeError, match="SQS retry required") as exc:
        builder.handler({}, None)
    assert exc.value.__suppress_context__
    monkeypatch.setattr(
        mailer.ReportingSettings,
        "from_env",
        lambda **kwargs: (_ for _ in ()).throw(ValueError("private recipient")),
    )
    with pytest.raises(RuntimeError, match="recovery required") as exc:
        mailer.handler({}, None)
    assert exc.value.__suppress_context__


def test_scope_does_not_expose_raw_owner(settings):
    with pytest.raises(ValueError, match="must not contain"):
        replace(settings, scope="reports-user-a")
