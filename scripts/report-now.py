#!/usr/bin/env python3
"""MUTATING after deployment: enqueue one report request; never invokes a Lambda."""

import argparse
import json
import os
import re
import subprocess
import sys
import uuid
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))
from app.reports.weeks import parse_week


class AwsError(ValueError):
    """Only sanitized AWS service diagnostics, never raw CLI output."""


def sanitized_error(stderr: str) -> str:
    match = re.search(
        r"An error occurred \(([^)]+)\) when calling the \w+ operation: (.*)", stderr
    )
    if not match:
        return "AWS CLI failure; service error unavailable (request outcome may be unknown)"
    message = match.group(2)
    for name, value in os.environ.items():
        if value and any(
            word in name.upper()
            for word in ("SECRET", "TOKEN", "PASSWORD", "DATABASE_URL", "ACCESS_KEY")
        ):
            message = message.replace(value, "[REDACTED]")
    message = re.sub(r"[a-zA-Z][a-zA-Z0-9+.-]*://[^\s]+", "[REDACTED_URL]", message)
    message = re.sub(r"(?:AKIA|ASIA)[A-Z0-9]{16}", "[REDACTED_KEY]", message)
    message = re.sub(
        r"(?i)(password|secret|token|credential)\s*[=:]\s*[^\s,;]+",
        r"\1=[REDACTED]",
        message,
    )
    return f"{match.group(1)}: {message[:1000]}"


def aws(arguments: list[str]) -> dict:
    result = subprocess.run(
        ["aws", *arguments, "--output", "json"],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        raise AwsError(sanitized_error(result.stderr))
    return json.loads(result.stdout)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--week", required=True)
    args = parser.parse_args()
    week = parse_week(args.week).label
    project = os.environ.get("PROJECT_NAME", "peach")
    if not re.fullmatch(r"[a-z][a-z0-9-]{0,19}", project):
        raise ValueError("Invalid project name")
    queue_url = os.environ.get("REPORT_QUEUE_URL")
    if not queue_url:
        stack = aws(
            ["cloudformation", "describe-stacks", "--stack-name", project + "-reports"]
        )
        outputs = {
            row["OutputKey"]: row["OutputValue"]
            for row in stack["Stacks"][0]["Outputs"]
        }
        queue_url = outputs["WorkQueueUrl"]
    if not re.fullmatch(
        r"https://sqs\.[a-z0-9-]+\.amazonaws\.com/[0-9]{12}/"
        + re.escape(project)
        + r"-report-work",
        queue_url,
    ):
        raise ValueError(
            "Queue URL must identify this project's AWS reporting work queue"
        )
    payload = {"source": "manual", "week": week, "correlation_id": str(uuid.uuid4())}
    print(
        "MUTATING AWS action: sending one message to the deployed reporting work queue",
        flush=True,
    )
    result = aws(
        [
            "sqs",
            "send-message",
            "--queue-url",
            queue_url,
            "--message-body",
            json.dumps(payload),
        ]
    )
    print(f"Queued {week}; message ID: {result['MessageId']}")


if __name__ == "__main__":
    try:
        main()
    except AwsError as error:
        print(f"Report enqueue failed: {error}", file=sys.stderr)
        sys.exit(1)
    except (ValueError, KeyError, OSError, TypeError):
        print(
            "Report enqueue failed: invalid configuration/week or AWS CLI failure",
            file=sys.stderr,
        )
        sys.exit(1)
