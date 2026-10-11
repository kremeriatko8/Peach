#!/usr/bin/env python3
"""Offline migration fingerprint and fail-closed release classification.

The deployed marker is release evidence, not a live database drift check. Only
successful guarded migrations may establish it; never seed it manually.
"""

import argparse
import ast
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def literal_assignments(path):
    values = {}
    for node in ast.parse(path.read_text()).body:
        if isinstance(node, (ast.Assign, ast.AnnAssign)):
            targets = node.targets if isinstance(node, ast.Assign) else [node.target]
            for target in targets:
                if isinstance(target, ast.Name) and target.id in {
                    "revision",
                    "down_revision",
                    "EXPECTED_REVISION",
                }:
                    values[target.id] = ast.literal_eval(node.value)
    return values


def manifest(root=ROOT):
    versions = sorted((root / "backend/migrations/versions").glob("*.py"))
    revisions = {}
    for path in versions:
        if path.name == "__init__.py":
            continue
        values = literal_assignments(path)
        revision, parent = values["revision"], values["down_revision"]
        if not isinstance(revision, str) or revision in revisions:
            raise ValueError("Invalid or duplicate migration revision")
        if parent is not None and not isinstance(parent, str):
            raise ValueError(
                "Branched migrations require a separately reviewed release policy"
            )
        revisions[revision] = parent
    heads = set(revisions) - set(revisions.values())
    if len(heads) != 1 or any(
        p is not None and p not in revisions for p in revisions.values()
    ):
        raise ValueError("Migration chain must have one complete head")
    head = heads.pop()
    seen, current = set(), head
    while current is not None:
        if current in seen:
            raise ValueError("Migration cycle")
        seen.add(current)
        current = revisions[current]
    if seen != set(revisions):
        raise ValueError("Disconnected migration history")
    runner = root / "backend/app/migration_handler.py"
    if literal_assignments(runner).get("EXPECTED_REVISION") != head:
        raise ValueError(
            "Migration head and private runner target differ; update preservation verification"
        )
    paths = (
        sorted((root / "backend/migrations").rglob("*.py"))
        + sorted((root / "backend/app/models").glob("*.py"))
        + [
            root / "backend/alembic.ini",
            runner,
        ]
    )
    digest = hashlib.sha256()
    for path in sorted(paths):
        # Include path and byte length: renamed, deleted and edited files all count.
        data = path.read_bytes()
        digest.update(path.relative_to(root).as_posix().encode() + b"\0")
        digest.update(str(len(data)).encode() + b"\0" + data)
    return {"sha256": digest.hexdigest(), "revision": head}


def classify(current, deployed, approved="", preparation=False):
    if deployed and not re.fullmatch(r"[a-f0-9]{64}", deployed):
        raise ValueError("Invalid deployed schema marker")
    kind = "ordinary" if deployed == current["sha256"] else "schema"
    if kind == "schema" and not preparation and approved != current["sha256"]:
        raise ValueError(
            "Schema release requires PEACH_APPROVED_MIGRATION_SHA256 matching the reviewed manifest; "
            "a fresh verified PEACH_RELEASE_SNAPSHOT_ID is also required"
        )
    return {**current, "kind": kind}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stack")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--preparation", action="store_true")
    args = parser.parse_args()
    current = manifest()
    if not args.stack:
        print(json.dumps(current))
        return
    stack = json.loads(
        subprocess.check_output(
            [
                "aws",
                "cloudformation",
                "describe-stacks",
                "--stack-name",
                args.stack,
                "--output",
                "json",
                "--no-cli-pager",
            ]
        )
    )["Stacks"][0]
    params = {p["ParameterKey"]: p["ParameterValue"] for p in stack["Parameters"]}
    plan = classify(
        current,
        params.get("ReleaseSchemaSha256", ""),
        os.environ.get("PEACH_APPROVED_MIGRATION_SHA256", ""),
        args.preparation,
    )
    if not args.output:
        parser.error("--output is required with --stack")
    args.output.write_text(json.dumps(plan))
    print(
        f"Release classification: {plan['kind']}; revision {plan['revision']}; manifest {plan['sha256']}"
    )


if __name__ == "__main__":
    try:
        main()
    except (ValueError, KeyError):
        raise SystemExit(
            "Schema release gate failed: inspect migration chain, deployed marker and exact manifest approval"
        ) from None
