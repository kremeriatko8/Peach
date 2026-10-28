#!/usr/bin/env python3
"""Render import HCL from a reviewed private inventory. Offline; never runs Terraform."""

import argparse
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def render(inventory):
    baseline = json.loads(
        (ROOT / "docs/terraform-migration-inventory.json").read_text()
    )
    expected = {r["terraform_address"]: r for r in baseline["resources"]}
    rows = inventory["resources"]
    if len(rows) != len(expected) or {r["terraform_address"] for r in rows} != set(
        expected
    ):
        raise ValueError("Inventory must cover every address exactly once")
    imported = set()
    blocks = [
        "# Generated offline from reviewed physical IDs. No infrastructure action executed."
    ]
    for row in rows:
        address = row["terraform_address"]
        original = expected[address]
        if (row["stack"], row["logical_id"]) != (
            original["stack"],
            original["logical_id"],
        ):
            raise ValueError("Inventory mapping changed")
        if row["strategy"] == "absent":
            if address != "aws_cognito_identity_provider.google[0]" or not row.get(
                "absence_verified"
            ):
                raise ValueError(
                    "Only verified absent Google federation may be omitted"
                )
            continue
        if row["strategy"] != "import":
            raise ValueError(
                "Recreation requires a separately reviewed migration design"
            )
        identifier = row["import_id"]
        if (
            not isinstance(identifier, str)
            or not identifier.strip()
            or any(c in identifier for c in "\n\r\0")
            or "${" in identifier
            or "%{" in identifier
        ):
            raise ValueError("A real reviewed import ID is required for every resource")
        key = (address.split(".")[0], identifier)
        if key in imported:
            raise ValueError(
                "Two addresses cannot adopt the same object of one resource type"
            )
        imported.add(key)
        blocks.append(
            f"import {{\n  to = {address}\n  id = {json.dumps(identifier)}\n}}"
        )
    return "\n\n".join(blocks) + "\n"


def observed_ids(snapshot):
    """Translate recorded AWS IDs to provider import IDs, without contacting AWS."""
    physical = {
        group: {
            r["LogicalResourceId"]: r["PhysicalResourceId"] for r in stack["resources"]
        }
        for group, stack in snapshot["stacks"].items()
    }
    cognito = snapshot["resources"]["cognito"]
    pool = cognito["pool"]["Id"]
    bucket = physical["reports"]["ReportsBucket"]
    statements = snapshot["resources"]["lambda"]["Parser"]["resource_policy"][
        "Statement"
    ]
    parser_sids = {r["Action"]: r["Sid"] for r in statements}
    special = {
        "aws_cognito_user_pool.main": pool,
        "aws_cognito_identity_provider.google[0]": pool + ":Google",
        "aws_cognito_user_pool_client.frontend": pool
        + "/"
        + cognito["client"]["ClientId"],
        "aws_cognito_user_pool_domain.main": cognito["domain"]["Domain"],
        "aws_cognito_managed_login_branding.frontend": pool
        + ","
        + cognito["branding"]["ManagedLoginBrandingId"],
        "aws_iam_role_policy.parser": physical["ai"]["Role"] + ":parser",
        "aws_iam_role_policy.builder": physical["reports"]["BuilderRole"]
        + ":report-builder",
        "aws_iam_role_policy.mailer": physical["reports"]["MailerRole"]
        + ":report-mailer",
        "aws_iam_role_policy.scheduler": physical["reports"]["SchedulerRole"]
        + ":send-report-work",
        "aws_sqs_queue_redrive_allow_policy.builder_dlq": physical["reports"][
            "BuilderDlq"
        ],
        "aws_lambda_function_url.parser": physical["ai"]["Parser"],
        "aws_lambda_permission.parser_url": physical["ai"]["Parser"]
        + "/"
        + parser_sids["lambda:InvokeFunctionUrl"],
        "aws_lambda_permission.parser_invoke": physical["ai"]["Parser"]
        + "/"
        + parser_sids["lambda:InvokeFunction"],
        "aws_lambda_permission.mailer_s3": physical["reports"]["Mailer"]
        + "/"
        + snapshot["resources"]["lambda"]["Mailer"]["resource_policy"]["Statement"][0][
            "Sid"
        ],
        "aws_lambda_function_event_invoke_config.mailer": physical["reports"]["Mailer"]
        + ":$LATEST",
        "aws_scheduler_schedule.weekly": physical["reports"]["ScheduleGroup"]
        + "/"
        + physical["reports"]["WeeklySchedule"],
    }
    baseline = json.loads(
        (ROOT / "docs/terraform-migration-inventory.json").read_text()
    )
    expected = {}
    for row in baseline["resources"]:
        address = row["terraform_address"]
        if address.startswith("aws_s3_"):
            expected[address] = bucket
        elif address in special:
            expected[address] = special[address]
        else:
            expected[address] = physical[row["stack"]][row["logical_id"]]
    return expected


def audit(inventory):
    """Cross-check every candidate against the configuration and recorded AWS reads."""
    render(
        inventory
    )  # Validate complete scope, uniqueness and literal ID safety first.
    snapshot = json.loads((ROOT / "docs/terraform-live-assessment.json").read_text())
    if (inventory.get("account_id"), inventory.get("region")) != (
        snapshot["account_id"],
        snapshot["region"],
    ):
        raise ValueError("Inventory account or region differs from the observation")
    expected = observed_ids(snapshot)
    actual = {r["terraform_address"]: r["import_id"] for r in inventory["resources"]}
    if len(actual) != 41 or actual != expected:
        raise ValueError("Import IDs differ from the recorded resource observations")
    text = "\n".join(p.read_text() for p in (ROOT / "infra").glob("*.tf"))
    declarations = re.findall(r'resource "([^" ]+)" "([^" ]+)"', text)
    addresses = [f"{kind}.{name}" for kind, name in declarations]
    if len(addresses) != 41 or len(set(addresses)) != 41:
        raise ValueError(
            "Terraform declarations contain missing or duplicate resources"
        )
    if set(addresses) != {address.replace("[0]", "") for address in expected}:
        raise ValueError("Import destinations do not match the existing configuration")
    return actual


def parse_imports(text):
    # Intentionally accept only this candidate's literal static import-block grammar.
    pattern = re.compile(
        r"import\s*\{\s*to\s*=\s*([a-z0-9_]+\.[a-z0-9_]+(?:\[0\])?)"
        r'\s+id\s*=\s*("(?:[^"\\]|\\.)*")\s*\}',
        re.MULTILINE,
    )
    rows = pattern.findall(text)
    remainder = pattern.sub("", text)
    remainder = re.sub(r"(?m)^\s*#.*$", "", remainder).strip()
    if remainder or len({a for a, _ in rows}) != len(rows):
        raise ValueError("Unexpected configuration or duplicate imports in import file")
    return {address: json.loads(identifier) for address, identifier in rows}


def check_file(inventory, path):
    expected = audit(inventory)
    if parse_imports(path.read_text()) != expected:
        raise ValueError("Import file differs from the complete observed inventory")
    return len(expected)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inventory", type=Path)
    parser.add_argument(
        "--check",
        action="store_true",
        help="Audit the active import file without running Terraform",
    )
    args = parser.parse_args()
    inventory = json.loads(args.inventory.read_text())
    if args.check:
        count = check_file(inventory, ROOT / "infra/imports.tf")
        print(
            f"Offline import audit passed: {count} exact addresses/IDs; "
            "no cloud or state operations"
        )
    else:
        audit(inventory)
        print(render(inventory), end="")


if __name__ == "__main__":
    try:
        main()
    except (KeyError, ValueError, TypeError, OSError):
        sys.exit("Incomplete or invalid reviewed inventory; no imports emitted")
