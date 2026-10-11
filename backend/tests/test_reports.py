import csv
import io
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import pytest

from app.models.item import Item
from app.models.meeting import Meeting
from app.reports.builder import ReportConfig, WeeklyReportBuilder
from app.reports.metrics import MeetingRecord, meeting_metrics, percentage_change
from app.reports.render import WeeklyReport, render_csv, safe_text
from app.reports.weeks import parse_week, previous_week

STAMP = datetime(2026, 10, 9, 12, tzinfo=UTC)


@pytest.mark.parametrize(
    "value",
    [
        "2025-W53",
        "2026-W00",
        "2026-W54",
        "2026-W1",
        "2026-w40",
        " 2026-W40",
        "2026-W40\n",
        "0000-W01",
        "2026-W99",
    ],
)
def test_invalid_weeks(value):
    with pytest.raises(ValueError):
        parse_week(value)


def test_year_boundary_and_valid_week_53():
    week = parse_week("2021-W01")
    assert previous_week(week).label == "2020-W53"
    assert week.start == datetime(2021, 1, 3, 22, tzinfo=UTC)
    assert parse_week("2020-W53").end == week.start


@pytest.mark.parametrize(
    ("label", "hours"), [("2026-W13", 167), ("2026-W43", 169), ("2026-W40", 168)]
)
def test_kyiv_dst_week_boundaries(label, hours):
    week = parse_week(label)
    assert (week.end - week.start).total_seconds() == hours * 3600
    assert previous_week(week).end == week.start


def test_metrics_and_deterministic_top_five():
    data = [MeetingRecord(UUID(int=i), f"Title {i}", STAMP, 60, 2) for i in range(7, 0, -1)]
    result = meeting_metrics(data)
    assert result.count == 7 and result.minutes == 420
    assert [meeting.id.int for meeting in result.longest] == [1, 2, 3, 4, 5]
    data.append(MeetingRecord(UUID(int=8), "Longest", STAMP, 120, 1))
    data.append(MeetingRecord(UUID(int=9), "Earlier", STAMP - timedelta(hours=1), 60, 1))
    assert [m.id.int for m in meeting_metrics(data).longest] == [8, 9, 1, 2, 3]


@pytest.mark.parametrize(
    ("current", "previous", "expected"),
    [
        (3, 2, "50.00"),
        (1, 3, "-66.67"),
        (0, 2, "-100.00"),
        (0, 0, "N/A (previous value is zero)"),
        (1, 0, "N/A (previous value is zero)"),
    ],
)
def test_percentage_changes(current, previous, expected):
    assert percentage_change(current, previous) == expected


@pytest.mark.parametrize(
    "value", ["=SUM(A1)", "+cmd", "-1+2", "@SUM(A1)", "  =cmd", "\ttext", "\rtext", "\ntext"]
)
def test_formula_injection(value):
    assert safe_text(value) == "'" + value


def test_csv_escaping_empty_and_determinism():
    week = parse_week("2026-W40")
    title = 'Київ, "planning"\nsecond line'
    metrics = meeting_metrics([MeetingRecord(uuid4(), title, week.start, 90, 3)])
    report = WeeklyReport(week, previous_week(week), STAMP, metrics, meeting_metrics([]), None)
    output = render_csv(report)
    assert render_csv(report) == output
    rows = list(csv.reader(io.StringIO(output.decode("utf-8"))))
    assert [title, "2026-09-28T00:00:00+03:00", "90", "3"] in rows
    assert ["Meeting count", "1", "0", "1", "N/A (previous value is zero)"] in rows
    assert ["Object key", "reports/2026-W40.csv"] in rows
    empty = WeeklyReport(
        week, previous_week(week), STAMP, meeting_metrics([]), meeting_metrics([]), None
    )
    assert b"Meeting count,0" in render_csv(empty)
    assert b"Tasks summary" not in render_csv(empty)


async def test_database_owner_scope_boundaries_tasks_and_comparison(session):
    week = parse_week("2026-W40")
    prior = previous_week(week)
    records = [
        ("user-a", week.start, 60),
        ("user-a", week.end - timedelta(microseconds=1), 90),
        ("user-a", prior.start, 30),
        ("user-a", week.end, 200),
        ("user-a", prior.start - timedelta(microseconds=1), 300),
        ("user-b", week.start, 1000),
    ]
    for owner, starts, minutes in records:
        session.add(
            Meeting(
                owner_id=owner,
                title="Planning",
                starts_at=starts,
                duration_minutes=minutes,
                participant_count=2,
            )
        )
    for owner, created, status in [
        ("user-a", week.start, "todo"),
        ("user-a", week.end, "done"),
        ("user-a", prior.start, "in_progress"),
        ("user-a", week.end - timedelta(seconds=1), "done"),
        ("user-b", week.start, "done"),
        (None, week.start, "todo"),
    ]:
        session.add(
            Item(owner_id=owner, name="Task", created_at=created, updated_at=STAMP, status=status)
        )
    await session.flush()
    builder = WeeklyReportBuilder(ReportConfig("user-a"), session, lambda: STAMP)
    report = await builder.collect(week.label)
    assert (report.meetings.count, report.meetings.minutes) == (2, 150)
    assert (report.previous_meetings.count, report.previous_meetings.minutes) == (1, 30)
    assert report.tasks.created == 2
    assert (report.tasks.todo, report.tasks.in_progress, report.tasks.done) == (1, 1, 2)
    output = await builder.build_weekly_report(week.label)
    assert output == await builder.build_weekly_report(week.label)
    assert b"Meeting count,2,1,1,100.00" in output
    assert b"Recorded duration (minutes),150,30,120,400.00" in output
    assert b"not historical progress" in output
    other = await WeeklyReportBuilder(ReportConfig("user-b", False), session).collect(week.label)
    assert other.meetings.minutes == 1000 and other.tasks is None
    empty = await WeeklyReportBuilder(ReportConfig("absent"), session).collect(week.label)
    assert empty.meetings.count == empty.tasks.created == empty.tasks.done == 0


@pytest.mark.parametrize("owner", ["", "  ", "x" * 129])
def test_owner_config_required(owner):
    with pytest.raises(ValueError):
        ReportConfig(owner)


async def test_naive_clock_rejected(session):
    with pytest.raises(ValueError, match="timezone-aware"):
        await WeeklyReportBuilder(
            ReportConfig("user-a"), session, lambda: datetime(2026, 10, 9)
        ).collect("2026-W40")
