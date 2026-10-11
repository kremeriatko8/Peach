#!/usr/bin/env python3
"""Prepare private reporting deployment artifacts offline. Never calls AWS or deploys."""

import argparse
import hashlib
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REQUIRED = {
    "ProjectName",
    "ImageUri",
    "Architecture",
    "VpcId",
    "SubnetIds",
    "RouteTableIds",
    "BackendFunctionSecurityGroupIds",
    "DatabaseUrl",
    "ReportOwnerSub",
    "ReportScopeId",
    "ReportRecipientEmail",
    "ReportFromEmail",
    "ReportTimezone",
}


def prepare(source: Path, destination: Path) -> None:
    rows = json.loads(source.read_text())
    if not isinstance(rows, list) or any(
        set(row) != {"ParameterKey", "ParameterValue"} for row in rows
    ):
        raise ValueError(
            "Expected a CloudFormation parameter list with explicit values"
        )
    values = {row["ParameterKey"]: row["ParameterValue"] for row in rows}
    if (
        len(values) != len(rows)
        or not REQUIRED <= values.keys()
        or values.keys() - REQUIRED - {"AllowDirectEvents"}
    ):
        raise ValueError("Missing, duplicate or unexpected reporting parameters")
    if any(
        not isinstance(value, str) or not value.strip() for value in values.values()
    ):
        raise ValueError("Every parameter needs a nonempty string value")
    if not re.fullmatch(
        r".+\.dkr\.ecr\..+\.amazonaws\.com/.+@sha256:[a-f0-9]{64}", values["ImageUri"]
    ):
        raise ValueError(
            "An immutable ECR image digest containing the reporting handlers is required"
        )
    if (
        values["ReportTimezone"] != "Europe/Kyiv"
        or values.get("AllowDirectEvents", "false") != "false"
    ):
        raise ValueError(
            "Preparation requires Kyiv timezone and disabled direct events"
        )
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{0,47}", values["ReportScopeId"]):
        raise ValueError("Invalid opaque report scope")
    if values["ReportOwnerSub"].lower() in values["ReportScopeId"].lower():
        raise ValueError("Scope must not contain the owner subject")
    if not values["DatabaseUrl"].startswith("postgresql+asyncpg://"):
        raise ValueError("Expected the existing async PostgreSQL URL")
    for key in ("ReportFromEmail", "ReportRecipientEmail"):
        if not re.fullmatch(r"[^\s<>@,;]+@[^\s<>@,;]+\.[^\s<>@,;]+", values[key]):
            raise ValueError("Invalid email configuration")
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    for name, content in (
        ("parameters.json", json.dumps(rows, indent=2)),
        (
            "review.json",
            json.dumps(
                {
                    "template_sha256": hashlib.sha256(
                        (ROOT / "infra/reports.yaml").read_bytes()
                    ).hexdigest(),
                    "deployment_executed": False,
                    "schedule_state": "DISABLED",
                    "pending_review": [
                        "owner/inbox",
                        "SES verification",
                        "image contains Phase 3",
                        "existing database revision 0004",
                        "subnet route tables and SG",
                        "existing S3 endpoints",
                        "deployer permissions",
                        "account concurrency",
                    ],
                },
                indent=2,
            ),
        ),
    ):
        descriptor = os.open(
            destination / name, os.O_CREAT | os.O_WRONLY | os.O_TRUNC, 0o600
        )
        with os.fdopen(descriptor, "w") as file:
            file.write(content + "\n")
        os.chmod(destination / name, 0o600)
    print(
        f"Prepared private artifacts in {destination}; NOT DEPLOYED; manual review required"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--parameters", required=True, type=Path)
    args = parser.parse_args()
    prepare(args.parameters, ROOT / "reports-local" / "deployment")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, TypeError):
        print(
            "Reporting preparation refused: invalid private parameter configuration",
            file=sys.stderr,
        )
        sys.exit(1)
