from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession

from app.reports.metrics import meeting_metrics
from app.reports.queries import read_meetings, read_tasks
from app.reports.render import WeeklyReport, render_csv
from app.reports.weeks import parse_week, previous_week


@dataclass(frozen=True)
class ReportConfig:
    """Trusted operator configuration, never populated from a report request payload."""

    owner_sub: str
    include_tasks: bool = True

    def __post_init__(self) -> None:
        if not self.owner_sub.strip() or len(self.owner_sub) > 128:
            raise ValueError("A configured Cognito owner sub is required")


class WeeklyReportBuilder:
    """Reusable with an injected read-only snapshot session and clock (including Lambda)."""

    def __init__(
        self,
        config: ReportConfig,
        session: AsyncSession,
        clock: Callable[[], datetime] = lambda: datetime.now(UTC),
    ):
        self.config = config
        self.session = session
        self.clock = clock

    async def collect(self, week: str) -> WeeklyReport:
        selected = parse_week(week)
        previous = previous_week(selected)
        timestamp = self.clock()
        if timestamp.tzinfo is None or timestamp.utcoffset() is None:
            raise ValueError("Report clock must return a timezone-aware timestamp")
        current_data = await read_meetings(self.session, self.config.owner_sub, selected)
        previous_data = await read_meetings(self.session, self.config.owner_sub, previous)
        tasks = (
            await read_tasks(self.session, self.config.owner_sub, selected)
            if self.config.include_tasks
            else None
        )
        return WeeklyReport(
            selected,
            previous,
            timestamp,
            meeting_metrics(current_data),
            meeting_metrics(previous_data),
            tasks,
        )

    async def build_weekly_report(self, week: str, *, object_key: str | None = None) -> bytes:
        return render_csv(await self.collect(week), object_key=object_key)
