#!/usr/bin/env python3
"""Render five actual browser results, or collect existing usage logs. Never invokes AI."""

import argparse
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def table(data):
    if sorted(case["case"] for case in data["cases"]) != [1, 2, 3, 4, 5]:
        raise ValueError("Exactly five distinct actual cases are required")
    url = data["frontend_url"]
    if not url.startswith("https://") or "localhost" in url:
        raise ValueError("Record the deployed frontend URL")
    rows = [
        "# Actual deployed agenda evaluation",
        "",
        "Source: user-captured browser responses; this tool does not attest model quality.",
        "",
        f"Frontend: {url}",
        f"Commit: {data['commit']}",
        f"Date/timezone context: {data['today']} / {data['tz']}",
        "",
        "| Case | Input | Actual JSON | Correct fields | Invented values | Input tokens | Output tokens | USD estimate | Seconds |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    for case in sorted(data["cases"], key=lambda c: c["case"]):
        if not case.get("actual") or not case.get("input"):
            raise ValueError("Never synthesize missing actual responses")
        actual = case["actual"]
        if case.get("status", 200) == 200:
            required = (
                "agenda",
                "model",
                "prompt_version",
                "input_tokens",
                "output_tokens",
                "estimated_cost_usd",
                "latency_ms",
            )
            if any(key not in actual for key in required):
                raise ValueError(
                    "Actual successful response is missing usage or agenda fields"
                )

        def cell(value):
            return html.escape(str(value)).replace("|", "&#124;").replace("\n", "<br>")

        values = [
            case["case"],
            case["input"],
            json.dumps(actual, ensure_ascii=False),
            case.get("correct_fields", "REQUIRES HUMAN REVIEW"),
            case.get("invented_values", "REQUIRES HUMAN REVIEW"),
            actual.get("input_tokens", "unknown"),
            actual.get("output_tokens", "unknown"),
            actual.get("estimated_cost_usd", "unknown"),
            actual["latency_ms"] / 1000 if "latency_ms" in actual else "unknown",
        ]
        rows.append("| " + " | ".join(cell(v) for v in values) + " |")
    return "\n".join(rows) + "\n"


def output_path(value):
    path = value.resolve()
    if not path.is_relative_to((ROOT / "reports-local/agenda").resolve()):
        raise ValueError("Keep private evidence in ignored reports-local/agenda")
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    return path


def main():
    p = argparse.ArgumentParser(description=__doc__)
    commands = p.add_subparsers(dest="command", required=True)
    render = commands.add_parser("table")
    render.add_argument("--input", required=True, type=Path)
    render.add_argument("--output", required=True, type=Path)
    logs = commands.add_parser("logs")
    logs.add_argument("--profile")
    logs.add_argument("--start-ms", required=True, type=int)
    logs.add_argument("--end-ms", required=True, type=int)
    logs.add_argument("--output", required=True, type=Path)
    args = p.parse_args()
    path = output_path(args.output)
    if args.command == "table":
        path.write_text(table(json.loads(args.input.read_text())))
    else:
        import boto3

        aws = boto3.Session(profile_name=args.profile or None, region_name="us-east-1")
        if aws.client("sts").get_caller_identity()["Account"] != "968053399627":
            raise ValueError("Wrong account")
        if not 0 < args.end_ms - args.start_ms <= 3_600_000:
            raise ValueError("Select a bounded actual-run window of at most one hour")
        client = aws.client("logs")
        found = []
        for page in client.get_paginator("filter_log_events").paginate(
            logGroupName="/aws/lambda/peach-agenda-parser",
            startTime=args.start_ms,
            endTime=args.end_ms,
            filterPattern='"agenda_parse"',
        ):
            for event in page["events"]:
                # Keep actual messages, no synthetic example line and no raw signed requests.
                if '"agenda_parse"' in event["message"]:
                    found.append(
                        {k: event[k] for k in ("timestamp", "eventId", "message")}
                    )
        if not found:
            raise ValueError("No actual parse records found; evidence was not created")
        path.write_text(json.dumps(found, ensure_ascii=False, indent=2))
    path.chmod(0o600)
    print("Saved actual supplied/read evidence to ignored local storage")


if __name__ == "__main__":
    try:
        main()
    except Exception as error:
        print(
            f"Evidence collection stopped ({type(error).__name__}); no model was called",
            file=sys.stderr,
        )
        sys.exit(1)
