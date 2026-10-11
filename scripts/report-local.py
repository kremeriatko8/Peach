#!/usr/bin/env python3
"""Fail-closed entry point for the dedicated, tmpfs-backed local development stack."""

import argparse
import base64
import ipaddress
import json
import os
import re
import subprocess
import sys
from datetime import date, timedelta
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
OWNER_CONFIG = ROOT / ".env.report.local"
DB = "peach-meetings-local-db-1"
BACKEND = "peach-meetings-local-backend-1"
PROJECT = "peach-meetings-local"
PURPOSE = "peach-meetings-disposable-development"


def verify_stack(db: dict, backend: dict) -> None:
    for container, service in ((db, "db"), (backend, "backend")):
        labels = container.get("Config", {}).get("Labels", {})
        if (
            not container.get("State", {}).get("Running")
            or labels.get("com.docker.compose.project") != PROJECT
            or labels.get("com.docker.compose.service") != service
            or labels.get("purpose") != PURPOSE
        ):
            raise ValueError(
                "Expected dedicated local development containers are not running"
            )
    target = "/var/lib/postgresql/data"
    if target not in db.get("HostConfig", {}).get("Tmpfs", {}):
        raise ValueError("Local PostgreSQL must use disposable tmpfs storage")
    for mount in db.get("Mounts", []):
        destination = mount.get("Destination", "")
        if (
            target == destination or target.startswith(destination.rstrip("/") + "/")
        ) and mount.get("Type") != "tmpfs":
            raise ValueError(
                "Persistent PostgreSQL storage is forbidden for local reports"
            )
    db_env = dict(value.split("=", 1) for value in db["Config"]["Env"] if "=" in value)
    backend_env = dict(
        value.split("=", 1) for value in backend["Config"]["Env"] if "=" in value
    )
    url = urlsplit(backend_env.get("DATABASE_URL", ""))
    if (
        url.scheme != "postgresql+asyncpg"
        or url.hostname != "db"
        or url.port != 5432
        or url.path != "/peach_meetings_local"
        or url.query
        or url.fragment
        or url.username != db_env.get("POSTGRES_USER")
        or url.password != db_env.get("POSTGRES_PASSWORD")
        or db_env.get("POSTGRES_DB") != "peach_meetings_local"
    ):
        raise ValueError(
            "Backend database target is not the verified disposable local database"
        )
    networks = db.get("NetworkSettings", {}).get("Networks", {})
    backend_networks = backend.get("NetworkSettings", {}).get("Networks", {})
    expected = PROJECT + "_peach"
    if set(networks) != {expected} or set(backend_networks) != {expected}:
        raise ValueError(
            "Local containers must share only the dedicated development network"
        )
    address = networks[expected].get("IPAddress", "")
    if not ipaddress.ip_address(address).is_private:
        raise ValueError(
            "Disposable database container must have a private network address"
        )
    if networks[expected].get("NetworkID") != backend_networks[expected].get(
        "NetworkID"
    ):
        raise ValueError("Database and backend network identities differ")
    bindings = db.get("HostConfig", {}).get("PortBindings", {})
    if not bindings or any(
        binding.get("HostIp") != "127.0.0.1"
        for entries in bindings.values()
        for binding in entries
    ):
        raise ValueError("Local database ports must bind only to loopback")


def validate_week(value: str) -> None:
    if not re.fullmatch(r"[0-9]{4}-W[0-9]{2}", value):
        raise ValueError("Week must be a valid ISO week in YYYY-Www format")
    monday = date.fromisocalendar(int(value[:4]), int(value[6:]), 1)
    monday - timedelta(days=7)
    monday + timedelta(days=7)


def query(request: dict) -> dict:
    result = subprocess.run(
        ["docker", "exec", "-i", BACKEND, "python", "-m", "app.reports.local"],
        input=json.dumps(request),
        text=True,
        capture_output=True,
        check=False,
    )
    if result.returncode:
        raise ValueError("Local read-only report query failed")
    return json.loads(result.stdout)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--week")
    parser.add_argument("--owners", action="store_true")
    parser.add_argument("--select-owner", type=int)
    args = parser.parse_args()
    if args.week:
        validate_week(args.week)
    elif not args.owners and args.select_owner is None:
        raise ValueError("Provide --week, --owners or --select-owner")
    inspected = subprocess.run(
        ["docker", "inspect", DB, BACKEND], capture_output=True, text=True, check=False
    )
    if inspected.returncode:
        raise ValueError(
            "Cannot verify disposable local containers; refusing database access"
        )
    db, backend = json.loads(inspected.stdout)
    verify_stack(db, backend)
    database_ip = db["NetworkSettings"]["Networks"][PROJECT + "_peach"]["IPAddress"]
    if args.owners or args.select_owner is not None:
        owners = query({"action": "owners", "database_ip": database_ip})["owners"]
        if args.select_owner is None:
            for index in range(len(owners)):
                print(f"Local owner {index + 1}")
            if not owners:
                print(
                    "No local owners found; create a meeting or task through authenticated Peach"
                )
            return
        if not 1 <= args.select_owner <= len(owners):
            raise ValueError("Select one of the listed local owner numbers")
        # Only a deliberately selected owner is persisted; no PII is printed.
        descriptor = os.open(OWNER_CONFIG, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(descriptor, "w") as config:
            json.dump({"owner_sub": owners[args.select_owner - 1]}, config)
        os.chmod(OWNER_CONFIG, 0o600)
        print(
            f"Configured local owner {args.select_owner} in ignored .env.report.local"
        )
        if not args.week:
            return
    if not OWNER_CONFIG.is_file():
        raise ValueError("Select a local owner first: make report-owner OWNER=1")
    owner = json.loads(OWNER_CONFIG.read_text())["owner_sub"]
    result = query(
        {
            "action": "build",
            "week": args.week,
            "owner_sub": owner,
            "database_ip": database_ip,
        }
    )
    output = ROOT / "reports-local" / f"{args.week}.csv"
    output.parent.mkdir(mode=0o700, exist_ok=True)
    descriptor = os.open(output, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "wb") as report:
        report.write(base64.b64decode(result["csv"], validate=True))
    print(
        f"{output}\n{args.week}: {result['count']} meetings, {result['minutes']} recorded minutes"
    )


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError, OSError, OverflowError, TypeError):
        # Never disclose Docker inspect output, database credentials or owner identifiers.
        print(
            "Local report refused: invalid week, owner configuration or unverified disposable stack. "
            "Check local services; list/select owners with make report-owners/report-owner.",
            file=sys.stderr,
        )
        sys.exit(1)
