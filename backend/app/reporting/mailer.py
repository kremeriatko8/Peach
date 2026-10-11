import hashlib
import json
import logging
import time
import uuid
from email.message import EmailMessage
from email.policy import SMTP

from botocore.exceptions import ClientError

from app.reporting.config import ReportingSettings
from app.reporting.events import identifier, mailer_events

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
MAX_ATTACHMENT_BYTES = 5 * 1024 * 1024
LEASE_SECONDS = 180


class LeaseBusyError(RuntimeError):
    pass


def acquire(ddb, table: str, key: str, token: str, now: int) -> bool:
    try:
        ddb.update_item(
            TableName=table,
            Key={"report_id": {"S": key}},
            UpdateExpression="SET #state = :pending, claim_token = :token, lease_until = :lease",
            ConditionExpression=(
                "attribute_not_exists(report_id) OR (#state = :pending AND lease_until <= :now)"
            ),
            ExpressionAttributeNames={"#state": "state"},
            ExpressionAttributeValues={
                ":pending": {"S": "PENDING"},
                ":token": {"S": token},
                ":lease": {"N": str(now + LEASE_SECONDS)},
                ":now": {"N": str(now)},
            },
        )
        return True
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise
        state = ddb.get_item(
            TableName=table, Key={"report_id": {"S": key}}, ConsistentRead=True
        ).get("Item", {})
        if state.get("state", {}).get("S") == "SENT":
            return False
        raise LeaseBusyError("Report mail lease is busy; retry required") from None


def release(ddb, table: str, key: str, token: str) -> None:
    try:
        ddb.update_item(
            TableName=table,
            Key={"report_id": {"S": key}},
            UpdateExpression="SET lease_until = :zero",
            ConditionExpression="claim_token = :token AND #state = :pending",
            ExpressionAttributeNames={"#state": "state"},
            ExpressionAttributeValues={
                ":zero": {"N": "0"},
                ":token": {"S": token},
                ":pending": {"S": "PENDING"},
            },
        )
    except ClientError as exc:
        if exc.response["Error"]["Code"] != "ConditionalCheckFailedException":
            raise


def finish(ddb, table: str, key: str, token: str, message_id: str) -> None:
    ddb.update_item(
        TableName=table,
        Key={"report_id": {"S": key}},
        UpdateExpression="SET #state = :sent, ses_message_id = :message REMOVE lease_until",
        ConditionExpression="claim_token = :token AND #state = :pending",
        ExpressionAttributeNames={"#state": "state"},
        ExpressionAttributeValues={
            ":sent": {"S": "SENT"},
            ":pending": {"S": "PENDING"},
            ":token": {"S": token},
            ":message": {"S": message_id},
        },
    )


def email_bytes(settings: ReportingSettings, week: str, content: bytes) -> bytes:
    if not settings.sender or not settings.recipient:
        raise ValueError("Verified report sender and recipient must be configured")
    if len(content) > MAX_ATTACHMENT_BYTES:
        raise ValueError("Report attachment exceeds size limit")
    content.decode("utf-8", errors="strict")
    message = EmailMessage(policy=SMTP)
    message["From"] = settings.sender
    message["To"] = settings.recipient
    message["Subject"] = f"Peach weekly productivity report — {week}"
    message.set_content(
        f"Your Peach productivity report for {week} is attached.\n"
        "Reporting timezone: Europe/Kyiv.\n"
    )
    message.add_attachment(
        content, maintype="text", subtype="csv", filename=f"{week}.csv", params={"charset": "utf-8"}
    )
    return message.as_bytes()


def handle(
    event: dict,
    settings: ReportingSettings,
    s3,
    ses,
    ddb,
    clock=time.time,
    token_factory=lambda: str(uuid.uuid4()),
) -> dict:
    if not settings.dedup_table or not settings.sender or not settings.recipient:
        raise ValueError("Mailer deployment configuration is incomplete")
    objects = mailer_events(event, settings)  # Validate the complete event before sending anything.
    results = []
    for item in objects:
        claim_key = hashlib.sha256(f"{settings.bucket}/{item.key}".encode()).hexdigest()
        token = token_factory()
        fields = {"trigger": "s3", "object_key": item.key, "sequencer": item.sequencer}
        try:
            acquired = acquire(ddb, settings.dedup_table, claim_key, token, int(clock()))
        except LeaseBusyError:
            logger.warning(json.dumps({**fields, "result": "lease_busy"}))
            raise
        except Exception:
            logger.error(json.dumps({**fields, "result": "claim_failed"}))
            raise
        if not acquired:
            logger.info(json.dumps({**fields, "result": "duplicate"}))
            results.append("duplicate")
            continue
        try:
            response = s3.get_object(Bucket=settings.bucket, Key=item.key)
            stream = response["Body"]
            try:
                if response.get("ContentLength", 0) > MAX_ATTACHMENT_BYTES:
                    raise ValueError("Report attachment exceeds size limit")
                content = stream.read(MAX_ATTACHMENT_BYTES + 1)
            finally:
                stream.close()
            raw = email_bytes(settings, item.week, content)
            correlation = response.get("Metadata", {}).get("correlation-id", item.sequencer)
            fields["correlation_id"] = identifier(correlation)
        except Exception:
            release(ddb, settings.dedup_table, claim_key, token)
            logger.error(json.dumps({**fields, "result": "read_failed"}))
            raise
        try:
            sent = ses.send_raw_email(
                Source=settings.sender, Destinations=[settings.recipient], RawMessage={"Data": raw}
            )
        except ClientError:
            release(ddb, settings.dedup_table, claim_key, token)
            logger.error(json.dumps({**fields, "result": "ses_failed"}))
            raise
        except Exception:
            # The send may have succeeded. Keep the lease until expiry before recovery.
            logger.error(json.dumps({**fields, "result": "ses_outcome_unknown"}))
            raise
        try:
            finish(ddb, settings.dedup_table, claim_key, token, sent["MessageId"])
        except Exception:
            logger.error(
                json.dumps(
                    {**fields, "result": "sent_state_failed", "ses_message_id": sent["MessageId"]}
                )
            )
            raise
        logger.info(json.dumps({**fields, "result": "sent", "ses_message_id": sent["MessageId"]}))
        results.append("sent")
    return {"results": results}


def handler(event, context):
    import boto3

    try:
        return handle(
            event,
            ReportingSettings.from_env(),
            boto3.client("s3"),
            boto3.client("ses"),
            boto3.client("dynamodb"),
        )
    except Exception:
        raise RuntimeError(
            "Report mailer failed; retry or failure-queue recovery required"
        ) from None
