"""Private subprocess adapter for the verified local runner; not an API route."""

import asyncio
import base64
import json
import os
import sys

from sqlalchemy import select, text, union
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.pool import NullPool

from app.models.item import Item
from app.models.meeting import Meeting
from app.reports.builder import ReportConfig, WeeklyReportBuilder
from app.reports.render import render_csv


async def run(request: dict) -> dict:
    engine = create_async_engine(
        make_url(os.environ["DATABASE_URL"]).set(host=request["database_ip"]),
        poolclass=NullPool,
        isolation_level="REPEATABLE READ",
    )
    try:
        async with engine.connect() as connection, connection.begin():
            await connection.execute(text("SET TRANSACTION READ ONLY"))
            directory = await connection.scalar(text("SHOW data_directory"))
            database = await connection.scalar(text("SELECT current_database()"))
            if directory != "/var/lib/postgresql/data" or database != "peach_meetings_local":
                raise ValueError(
                    "Actual database storage/identity differs from verified local target"
                )
            async with AsyncSession(bind=connection, autoflush=False) as session:
                owners = list(
                    (
                        await session.scalars(
                            union(
                                select(Meeting.owner_id),
                                select(Item.owner_id).where(Item.owner_id.is_not(None)),
                            ).order_by("owner_id")
                        )
                    ).all()
                )
                owners = [owner for owner in owners if owner and owner.strip()]
                if request["action"] == "owners":
                    return {"owners": owners}
                config = ReportConfig(request["owner_sub"])
                if config.owner_sub not in owners:
                    raise ValueError("Configured owner is not present in the local database")
                report = await WeeklyReportBuilder(config, session).collect(request["week"])
                return {
                    "csv": base64.b64encode(render_csv(report)).decode("ascii"),
                    "count": report.meetings.count,
                    "minutes": report.meetings.minutes,
                }
    finally:
        await engine.dispose()


if __name__ == "__main__":
    try:
        print(json.dumps(asyncio.run(run(json.load(sys.stdin)))))
    except Exception:
        # Database URLs and owner identifiers must never appear in CLI error output.
        print(
            "Local report query failed; check the verified local services/configuration",
            file=sys.stderr,
        )
        sys.exit(1)
