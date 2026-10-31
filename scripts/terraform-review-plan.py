#!/usr/bin/env python3
"""Offline guard for an HCP-exported plan JSON; never reads state or calls a service."""

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def review(plan, mode, google_enabled=True):
    expected = {
        r["terraform_address"]
        for r in json.loads(
            (ROOT / "docs/terraform-migration-inventory.json").read_text()
        )["resources"]
    }
    if not google_enabled:
        expected.remove("aws_cognito_identity_provider.google[0]")
    if plan.get("errored") or plan.get("complete") is False:
        raise ValueError("Incomplete or errored plan")
    if plan.get("deferred_changes"):
        raise ValueError("Deferred changes must be resolved")
    observed = {
        r["terraform_address"]: r["import_id"]
        for r in json.loads(
            (ROOT / "docs/terraform-live-import-inventory.json").read_text()
        )["resources"]
    }
    seen, imports = set(), set()
    for row in plan.get("resource_changes", []):
        if row.get("mode") == "data":
            if row["change"]["actions"] not in (["no-op"], ["read"]):
                raise ValueError("Unexpected data-source action")
            continue
        address = row["address"]
        if address not in expected or address in seen:
            raise ValueError("Unexpected or duplicate resource")
        seen.add(address)
        if row["change"]["actions"] != ["no-op"]:
            raise ValueError(
                "Managed resource create/update/delete/replacement rejected"
            )
        if row["change"].get("importing"):
            if row["change"]["importing"].get("id") != observed[address]:
                raise ValueError(
                    "Plan imports an ID different from the reviewed candidate"
                )
            imports.add(address)
    if seen != expected:
        raise ValueError("Plan does not account for the complete migration inventory")
    if mode == "adopt" and imports != expected:
        raise ValueError("Every expected object must be imported in the adoption plan")
    if mode == "clean" and imports:
        raise ValueError("Post-migration plan still contains imports")
    if mode == "clean" and any(
        value.get("actions") != ["no-op"]
        for value in plan.get("output_changes", {}).values()
    ):
        raise ValueError("Post-migration outputs still change")
    for check in plan.get("checks", []):
        if check.get("status") != "pass":
            raise ValueError("Unresolved or failing plan checks")
    return len(imports)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("plan_json", type=Path)
    parser.add_argument("--mode", choices=["adopt", "clean"], required=True)
    parser.add_argument("--google-absent", action="store_true")
    args = parser.parse_args()
    count = review(
        json.loads(args.plan_json.read_text()), args.mode, not args.google_absent
    )
    print(f"Offline plan guard passed: {count} imports; no managed resource mutations")


if __name__ == "__main__":
    try:
        main()
    except (KeyError, ValueError, TypeError, OSError):
        sys.exit(
            "Plan rejected: incomplete inventory, unresolved checks, or non-import mutations"
        )
