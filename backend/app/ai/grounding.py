"""Conservative source checks, not a general natural-language fact verifier."""

import calendar
import copy
import re
from datetime import date, datetime, timedelta

# Reject the entire paste, not just an instruction fragment that might change meaning.
# This intentionally favors manual fallback; it is not a universal injection detector.
INSTRUCTIONS = re.compile(
    r"ignore\s+(?:(?:all|your|the|previous)\s+){0,3}(?:instructions?|rules?|extraction)"
    r"|(?:system|developer)\s+(?:override|message|instructions?)"
    r"|(?:set|change|replace|assign)\s+(?:every|all)\s+owners?\b"
    r"|ігнор\w*\s+(?:(?:усі|всі|попередні|свої)\s+){0,3}(?:інструкц|правил)"
    r"|(?:зміни|встанови)\s+(?:всіх|усіх)\s+відповідальн",
    re.IGNORECASE,
)
COMMITMENT = re.compile(
    r"\b(?:will|must|shall|should|can|assign\w*|prepare\w*|send\w*|collect\w*|compare\w*)\b"
    r"|follow\s+up|збира\w*|підгот\w*|запис\w*|надіш\w*|порівня\w*|готу\w*",
    re.IGNORECASE,
)
DISCUSSION = re.compile(r"^\s*(?:agenda\b|discuss\w*|review\b|обговор\w*)", re.IGNORECASE)
WEEKDAYS = (
    r"monday|понеділ\w*",
    r"tuesday|вівтор\w*",
    r"wednesday|серед\w*",
    r"thursday|четвер\w*",
    r"friday|п['’]ятниц\w*",
    r"saturday|субот\w*",
    r"sunday|неділ\w*",
)


def normalized(text):
    return " ".join(text.casefold().split())


def due_supported(value: date, clause: str, today: date) -> bool:
    if not re.search(r"\b(?:by|due|deadline|до|термін)\b", clause, re.IGNORECASE):
        return False
    if value.isoformat() in clause:
        return True
    if re.search(r"end\s+of\s+(?:the\s+)?week|кін\w*\s+тижня", clause, re.IGNORECASE):
        return False
    for weekday, pattern in enumerate(WEEKDAYS):
        if re.search(
            r"\b(?:" + pattern + r")\b", clause, re.IGNORECASE
        ) and value == today + timedelta(days=(weekday - today.weekday()) % 7):
            return True
    for month in range(1, 13):
        for match in re.finditer(
            r"\b" + calendar.month_name[month] + r"\s+(\d{1,2})(?:,?\s+(\d{4}))?\b",
            clause,
            re.IGNORECASE,
        ):
            try:
                candidate = date(int(match[2] or today.year), month, int(match[1]))
            except ValueError:
                continue
            if candidate == value:
                return True
    return False


def clean_proposal(raw):
    """Normalize placeholder owners before strict validation; leave original input intact."""
    result = copy.deepcopy(raw)
    for group in ("items", "action_items"):
        values = result.get(group, [])
        if isinstance(values, list):
            for item in values:
                if (
                    isinstance(item, dict)
                    and isinstance(item.get("owner"), str)
                    and item["owner"].strip().casefold() in {"", "null"}
                ):
                    item["owner"] = None
    return result


def ground_proposal(parsed, text: str, today: date):
    """Only remove unsupported values; never guess missing owners/dates/durations.

    Action task text must be a verbatim source span in an actionable clause.
    Conservative rejection is intentional for paraphrases/unsupported languages.
    """
    result = parsed.model_copy(deep=True)
    if result.starts_at is not None and not re.search(r"\b[0-2]?\d:[0-5]\d\b", text):
        # Unsupported clock formats also fall back to review; never fill "after lunch".
        result.starts_at = None
    minutes = {
        int(m[1])
        for m in re.finditer(
            r"(?<!\w)(\d{1,3})\s*(?:minutes?|mins?|хв(?:илин\w*)?)(?!\w)",
            text,
            re.IGNORECASE,
        )
    }
    for item in result.items:
        if item.owner and item.owner not in text:
            item.owner = None
        if item.minutes not in minutes:
            item.minutes = None
    if result.duration_minutes not in minutes:
        # A meeting end constrains duration, not a task. Preserve a duration only
        # if it also agrees with an explicit pair of source clock times.
        clocks = [int(h) * 60 + int(m) for h, m in re.findall(r"\b([0-2]?\d):([0-5]\d)\b", text)]
        start = datetime.fromisoformat(result.starts_at) if result.starts_at else None
        supported = (
            start
            and start.hour * 60 + start.minute in clocks
            and any(
                (end - (start.hour * 60 + start.minute)) % 1440 == result.duration_minutes
                for end in clocks
            )
        )
        if not supported:
            result.duration_minutes = None
    clauses = re.split(r"[.!?;\n]+", text)
    actions = []
    for action in result.action_items:
        task = normalized(action.task).rstrip(".")
        matches = [
            clause
            for clause in clauses
            if task
            and task in normalized(clause)
            and COMMITMENT.search(clause)
            and not DISCUSSION.search(clause)
        ]
        if not matches:
            continue
        evidence = " ".join(matches)
        if action.owner and action.owner not in evidence:
            action.owner = None
        if action.due and not any(due_supported(action.due, clause, today) for clause in matches):
            action.due = None
        actions.append(action)
    result.action_items = actions
    return result
