#!/usr/bin/env python3
"""Read only allowlisted public Terraform outputs, never the complete state."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def read_outputs(group):
    # -json with a named output returns that value, not the complete output set.
    result = subprocess.run(
        [
            "terraform",
            f"-chdir={ROOT / 'infra'}",
            "output",
            "-json",
            f"{group}_outputs",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        # Never echo raw diagnostics: remote output/state errors may contain secrets.
        raise ValueError(
            "Terraform public output unavailable; check backend/authentication"
        )
    outputs = json.loads(result.stdout)
    contract = json.loads((ROOT / "docs/terraform-output-contract.json").read_text())
    if not isinstance(outputs, dict) or set(outputs) != set(contract[group]):
        raise ValueError("Unexpected public output contract")
    if any(
        not isinstance(value, str)
        or not value
        or any(char in value for char in "\n\r\0")
        for value in outputs.values()
    ):
        raise ValueError("Invalid public output value")
    return outputs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("group", choices=["auth", "reports", "ai"])
    parser.add_argument("--format", choices=["mapping", "cfn"], default="mapping")
    args = parser.parse_args()
    outputs = read_outputs(args.group)
    if args.format == "cfn":
        outputs = [{"OutputKey": k, "OutputValue": v} for k, v in outputs.items()]
    json.dump(outputs, sys.stdout)
    sys.stdout.write("\n")


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, TypeError):
        sys.exit(
            "Public Terraform outputs unavailable or invalid; no fallback attempted"
        )
