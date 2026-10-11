import asyncio
import json
import logging
import os

from botocore.exceptions import ClientError
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.reporting.config import ReportingSettings
from app.reporting.events import builder_trigger
from app.reports.builder import ReportConfig, WeeklyReportBuilder

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


async def generate(settings: ReportingSettings, week: str) -> bytes:
    engine = create_async_engine(
        os.environ["DATABASE_URL"],
        poolclass=NullPool,
        isolation_level="REPEATABLE READ",
        connect_args={"timeout": 30, "command_timeout": 60},
    )
    try:
        async with engine.connect() as connection, connection.begin():
            await connection.execute(text("SET TRANSACTION READ ONLY"))
            async with AsyncSession(bind=connection, autoflush=False) as session:
                return await WeeklyReportBuilder(
                    ReportConfig(settings.owner_sub), session
                ).build_weekly_report(week, object_key=settings.key(week))
    finally:
        await engine.dispose()


def handle(event: dict, settings: ReportingSettings, s3, build=generate) -> dict:
    trigger = builder_trigger(event, settings)
    fields = {
        "trigger": trigger.source,
        "week": trigger.week,
        "correlation_id": trigger.correlation_id,
        "message_id": trigger.message_id,
    }
    try:
        csv_data = asyncio.run(build(settings, trigger.week))
        s3.put_object(
            Bucket=settings.bucket,
            Key=settings.key(trigger.week),
            Body=csv_data,
            ContentType="text/csv; charset=utf-8",
            ServerSideEncryption="AES256",
            IfNoneMatch="*",
            Metadata={"correlation-id": trigger.correlation_id, "source": trigger.source},
        )
        result = "published"
    except ClientError as exc:
        if exc.response.get("Error", {}).get("Code") in {"PreconditionFailed", "412"}:
            result = "duplicate"
        else:
            logger.error(json.dumps({**fields, "result": "failed"}))
            raise
    except Exception:
        logger.error(json.dumps({**fields, "result": "failed"}))
        raise
    logger.info(json.dumps({**fields, "result": result}))
    return {"result": result, "week": trigger.week}


def handler(event, context):
    import boto3

    try:
        return handle(event, ReportingSettings.from_env(builder=True), boto3.client("s3"))
    except Exception:
        raise RuntimeError("Report builder failed; SQS retry required") from None
