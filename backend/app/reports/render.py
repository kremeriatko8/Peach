import csv
import io
from dataclasses import dataclass
from datetime import UTC, datetime

from app.reports.metrics import MeetingMetrics, TaskMetrics, percentage_change
from app.reports.weeks import KYIV, ReportingWeek


@dataclass(frozen=True)
class WeeklyReport:
    week: ReportingWeek
    previous: ReportingWeek
    generated_at: datetime
    meetings: MeetingMetrics
    previous_meetings: MeetingMetrics
    tasks: TaskMetrics | None

    @property
    def object_key(self) -> str:
        return f"reports/{self.week.label}.csv"


def safe_text(value: str) -> str:
    """Neutralize spreadsheet formulas, including whitespace-prefixed formulas."""
    if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")):
        return "'" + value
    return value


def render_csv(report: WeeklyReport, *, object_key: str | None = None) -> bytes:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerows(
        [
            ["Report metadata"],
            ["ISO week", report.week.label],
            ["Timezone", "Europe/Kyiv"],
            ["Generated at UTC", report.generated_at.astimezone(UTC).isoformat()],
            ["Week start UTC (inclusive)", report.week.start.isoformat()],
            ["Week end UTC (exclusive)", report.week.end.isoformat()],
            ["Owner scope", "Single configured Cognito owner"],
            ["Object key", object_key or report.object_key],
            ["Meeting allocation", "Start time determines week; full recorded duration counted"],
            [],
            ["Meetings summary"],
            ["Meeting count", report.meetings.count],
            ["Total recorded duration (minutes)", report.meetings.minutes],
            [],
            ["Comparison with previous week", report.previous.label],
            [
                "Metric",
                "Selected week",
                "Previous week",
                "Absolute change",
                "Percentage change (%)",
            ],
        ]
    )
    for name, current, previous in (
        ("Meeting count", report.meetings.count, report.previous_meetings.count),
        ("Recorded duration (minutes)", report.meetings.minutes, report.previous_meetings.minutes),
    ):
        writer.writerow(
            [name, current, previous, current - previous, percentage_change(current, previous)]
        )
    writer.writerows(
        [
            [],
            ["Five longest meetings"],
            [
                "Title",
                "Start (Europe/Kyiv, UTC offset included)",
                "Duration (minutes)",
                "Participants",
            ],
        ]
    )
    for meeting in report.meetings.longest:
        writer.writerow(
            [
                safe_text(meeting.title),
                meeting.starts_at.astimezone(KYIV).isoformat(),
                meeting.duration_minutes,
                meeting.participant_count,
            ]
        )
    if report.tasks is not None:
        writer.writerows(
            [
                [],
                ["Tasks summary"],
                ["Tasks created during selected week", report.tasks.created],
                ["Current status snapshot at UTC", report.generated_at.astimezone(UTC).isoformat()],
                [
                    "Status counts meaning",
                    "Current counts across all creation dates; not historical progress",
                ],
                ["To do", report.tasks.todo],
                ["In progress", report.tasks.in_progress],
                ["Done", report.tasks.done],
            ]
        )
    return buffer.getvalue().encode("utf-8")
