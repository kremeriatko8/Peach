#!/usr/bin/env python3
"""Render reviewed IAM templates offline into ignored private files. Never calls AWS."""

import argparse
import json
import os
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "infra/iam/reports"
PRIVATE_ROOT = ROOT / "reports-local"


def render(config_path: Path, destination: Path) -> list[str]:
    config_path = config_path.resolve()
    destination = destination.resolve()
    if (
        not config_path.is_relative_to(PRIVATE_ROOT)
        or not destination.is_relative_to(PRIVATE_ROOT)
        or config_path.is_symlink()
        or destination.is_symlink()
    ):
        raise ValueError(
            "Private inputs and outputs must remain inside ignored reports-local"
        )
    config = json.loads(config_path.read_text())
    if set(config) != {"sender", "recipient", "scope"}:
        raise ValueError(
            "Expected sender, recipient and scope only; no database credentials"
        )
    for key in ("sender", "recipient"):
        if not isinstance(config[key], str) or not re.fullmatch(
            r"[^\s<>@,;*?]+@[^\s<>@,;*?]+\.[^\s<>@,;*?]+", config[key]
        ):
            raise ValueError("An exact verified email address is required")
    if not isinstance(config["scope"], str) or not re.fullmatch(
        r"[a-z0-9][a-z0-9-]{0,47}", config["scope"]
    ):
        raise ValueError("Scope must be an opaque slug compatible with ReportScopeId")
    values = {
        "__SENDER_EMAIL__": config["sender"],
        "__RECIPIENT_EMAIL__": config["recipient"],
        "__REPORT_SCOPE_ID__": config["scope"],
    }
    destination.mkdir(parents=True, exist_ok=True, mode=0o700)
    os.chmod(destination, 0o700)
    written = []
    for source in sorted(SOURCE.glob("*.json")):
        document = json.loads(source.read_text())
        if "Statement" not in document:
            continue  # Public authorization snapshots are not IAM policies.
        content = source.read_text()
        for key, value in values.items():
            content = content.replace(key, value)
        document = json.loads(content)
        if re.search(r"__[A-Z_]+__", content):
            raise ValueError("Unresolved review placeholder")
        compact = json.dumps(document, separators=(",", ":"))
        if len(compact) > 6144:
            raise ValueError("Policy exceeds managed-policy character limit")
        target = destination / source.name
        # Do not follow a pre-existing symlink to a tracked or unrelated file.
        descriptor = os.open(
            target,
            os.O_WRONLY | os.O_CREAT | os.O_TRUNC | os.O_NOFOLLOW,
            0o600,
        )
        with os.fdopen(descriptor, "w") as file:
            file.write(json.dumps(document, indent=2) + "\n")
        os.chmod(target, 0o600)
        written.append(source.name)
    return written


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=PRIVATE_ROOT / "iam/rendered")
    args = parser.parse_args()
    files = render(args.config, args.output)
    print(
        f"Prepared {len(files)} private JSON policies; NOT APPLIED. Configuration values withheld."
    )


if __name__ == "__main__":
    try:
        main()
    except (ValueError, OSError, TypeError):
        sys.exit(
            "IAM preparation refused: check private paths, exact addresses, scope and policy size"
        )
