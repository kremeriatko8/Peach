#!/usr/bin/env python3
"""Explicitly authorized transfer of one existing secret; never prints its value."""

import argparse
import json
import os
import tempfile
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / ".env.reports-parameters.local"
SECRET = "arn:aws:secretsmanager:us-east-1:968053399627:secret:peach/backend/database-url-EbUSp9"


def transfer(session, target=TARGET):
    if target.is_symlink() or not target.is_file():
        raise ValueError("Unsafe target")
    rows = json.loads(target.read_text())
    if not isinstance(rows, list) or any(
        set(r) != {"ParameterKey", "ParameterValue"} for r in rows
    ):
        raise ValueError("Invalid parameters")
    keys = [r["ParameterKey"] for r in rows]
    if len(keys) != len(set(keys)) or "DatabaseUrl" in keys:
        raise ValueError("Refusing duplicate or existing database value")
    if session.client("sts").get_caller_identity()["Account"] != "968053399627":
        raise ValueError("Wrong account")
    result = session.client("secretsmanager").get_secret_value(SecretId=SECRET)
    if result.get("ARN") != SECRET:
        raise ValueError("Wrong secret")
    value = result.get("SecretString", "")
    parsed = urlsplit(value)
    if (
        parsed.scheme != "postgresql+asyncpg"
        or not parsed.hostname
        or not parsed.hostname.endswith(".rds.amazonaws.com")
    ):
        raise ValueError("Unexpected database URL")
    rows.append({"ParameterKey": "DatabaseUrl", "ParameterValue": value})
    name = None
    try:
        fd, name = tempfile.mkstemp(
            prefix=".reports-parameters-", suffix=".local", dir=target.parent
        )
        with os.fdopen(fd, "w") as stream:
            json.dump(rows, stream, indent=2)
            stream.write("\n")
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, target)
    finally:
        if name and os.path.exists(name):
            os.unlink(name)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--retrieve-authorized-secret", action="store_true")
    args = parser.parse_args()
    if not args.retrieve_authorized_secret:
        print("NOT RETRIEVED. Requires separate authorization and explicit flag.")
        return
    try:
        import boto3

        transfer(boto3.Session(profile_name="default", region_name="us-east-1"))
    except Exception:  # noqa: BLE001 -- suppress credential-bearing exception details
        raise SystemExit(
            "Transfer refused or failed; details withheld to protect credentials."
        ) from None
    print(
        "Private database parameter saved; value withheld. No database connection made."
    )


if __name__ == "__main__":
    main()
