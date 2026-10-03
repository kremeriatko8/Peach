"""Read-only preflight and change-set policy boundary tests; no AWS calls."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]


def load(name):
    spec = importlib.util.spec_from_file_location(
        name, ROOT / "scripts" / (name + ".py")
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class SafetyTests(unittest.TestCase):
    def test_complete_environment_limit(self):
        module = load("backend-preflight")
        module.environment_size({"KEY": "a" * 4093})
        for values in ({"KEY": "a" * 4094}, {"KEY": ""}, {"KEY": "é" * 2048}):
            with self.subTest(values_size=sum(len(str(v)) for v in values.values())):
                with self.assertRaises(ValueError):
                    module.environment_size(values)

    def test_snapshot_must_be_available_recent_manual_and_same_cluster(self):
        module = load("backend-preflight")
        snapshot = {
            "DBClusterIdentifier": "peach-db",
            "Status": "available",
            "SnapshotType": "manual",
            "SnapshotCreateTime": datetime.now(timezone.utc).isoformat(),
        }
        with patch.object(
            module, "aws", return_value={"DBClusterSnapshots": [snapshot]}
        ):
            module.snapshot("peach-db", "approved")
            with self.assertRaises(ValueError):
                module.snapshot("peach-db", "")
        for changes in (
            {"DBClusterIdentifier": "other"},
            {"Status": "creating"},
            {"SnapshotType": "automated"},
            {
                "SnapshotCreateTime": (
                    datetime.now(timezone.utc) - timedelta(days=2)
                ).isoformat()
            },
        ):
            with patch.object(
                module,
                "aws",
                return_value={"DBClusterSnapshots": [{**snapshot, **changes}]},
            ):
                with self.assertRaises(ValueError):
                    module.snapshot("peach-db", "approved")

    def test_database_changeset_rejects_delete_and_possible_replacement(self):
        module = load("check-backend-changeset")
        base = {
            "Status": "CREATE_COMPLETE",
            "ExecutionStatus": "AVAILABLE",
            "ChangeSetId": "reviewed",
        }
        for kind in (
            "AWS::RDS::DBCluster",
            "AWS::RDS::DBInstance",
            "AWS::RDS::DBSubnetGroup",
        ):
            for action, replacement in (
                ("Remove", None),
                ("Add", None),
                ("Modify", "True"),
                ("Modify", "Conditional"),
                ("Modify", None),
            ):
                with self.subTest(kind=kind, action=action, replacement=replacement):
                    change = {
                        "ResourceType": kind,
                        "Action": action,
                        "Replacement": replacement,
                    }
                    with self.assertRaises(ValueError):
                        module.validate(
                            {**base, "Changes": [{"ResourceChange": change}]}
                        )
        safe = {
            "ResourceType": "AWS::RDS::DBCluster",
            "Action": "Modify",
            "Replacement": "False",
        }
        self.assertEqual(
            module.validate({**base, "Changes": [{"ResourceChange": safe}]}), "reviewed"
        )
        with self.assertRaises(ValueError):
            module.validate({**base, "Changes": [], "NextToken": "more"})
        with self.assertRaises(ValueError):
            module.validate({**base, "Changes": [], "Status": "FAILED"})


class SnapshotProcessTests(unittest.TestCase):
    def test_explicit_snapshot_waits_and_verifies_cluster(self):
        for wrong_cluster in (False, True):
            with (
                self.subTest(wrong_cluster=wrong_cluster),
                tempfile.TemporaryDirectory() as folder,
            ):
                root = Path(folder)
                (root / "scripts").mkdir()
                shutil.copy(ROOT / "scripts/snapshot-backend.sh", root / "scripts")
                (root / "bin").mkdir()
                fake = root / "bin/aws"
                fake.write_text(
                    "#!"
                    + sys.executable
                    + "\n"
                    + r"""
import json,os,sys
from pathlib import Path
args=sys.argv[1:]
with open(os.environ['EVENTS'],'a') as file: file.write(json.dumps(args[:2])+'\n')
if args[:2]==['cloudformation','describe-stack-resource']: print('peach-db')
elif args[:2]==['rds','describe-db-cluster-snapshots']:
    print(json.dumps({'DBClusterSnapshots':[{'DBClusterIdentifier':'wrong' if os.environ['WRONG']=='yes' else 'peach-db','Status':'available','SnapshotType':'manual'}]}))
"""
                )
                fake.chmod(0o755)
                events = root / "events"
                result = subprocess.run(
                    ["bash", str(root / "scripts/snapshot-backend.sh")],
                    env={
                        "PATH": str(root / "bin") + os.pathsep + os.environ["PATH"],
                        "EVENTS": str(events),
                        "WRONG": "yes" if wrong_cluster else "no",
                    },
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode != 0, wrong_cluster, result.stderr)
                self.assertEqual(
                    [json.loads(line) for line in events.read_text().splitlines()],
                    [
                        ["cloudformation", "describe-stack-resource"],
                        ["rds", "create-db-cluster-snapshot"],
                        ["rds", "wait"],
                        ["rds", "describe-db-cluster-snapshots"],
                    ],
                )
