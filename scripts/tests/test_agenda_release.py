"""Release interlocks use fake AWS sessions. No AWS or paid inference."""

import importlib.util
from datetime import timedelta
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

spec = importlib.util.spec_from_file_location(
    "agenda_release", Path(__file__).resolve().parents[1] / "agenda-release.py"
)
release = importlib.util.module_from_spec(spec)
spec.loader.exec_module(release)


def test_approval_is_commit_target_and_phase_specific():
    args = SimpleNamespace(commit="a" * 40, approve=None)
    with pytest.raises(release.Stop):
        release.approve(args, "backend")
    args.approve = f"{release.ACCOUNT}:{args.commit}:backend"
    release.approve(args, "backend")
    with pytest.raises(release.Stop):
        release.approve(args, "paid-smoke")


def test_snapshot_requires_exact_cluster_manual_available_and_recent():
    value = {
        "DBClusterIdentifier": "peach-db",
        "Status": "available",
        "SnapshotType": "manual",
        "SnapshotCreateTime": release.now() - timedelta(minutes=10),
    }
    aws = Mock()
    aws.client.return_value.describe_db_cluster_snapshots.return_value = {
        "DBClusterSnapshots": [value]
    }
    release.check_snapshot(aws, "fresh")
    for key, change in [
        ("Status", "creating"),
        ("SnapshotType", "automated"),
        ("DBClusterIdentifier", "other"),
        ("SnapshotCreateTime", release.now() - timedelta(days=2)),
    ]:
        aws.client.return_value.describe_db_cluster_snapshots.return_value = {
            "DBClusterSnapshots": [{**value, key: change}]
        }
        with pytest.raises(release.Stop):
            release.check_snapshot(aws, "wrong")


def test_db_url_must_match_existing_private_cluster(monkeypatch):
    import asyncio

    aws = Mock()
    aws.client.return_value.describe_db_clusters.return_value = {
        "DBClusters": [
            {
                "Status": "available",
                "Endpoint": "production.cluster.example",
                "DatabaseName": "peach",
            }
        ]
    }
    monkeypatch.setenv(
        "PEACH_READONLY_DATABASE_URL", "postgresql://user:secret@other/db"
    )
    with pytest.raises(release.Stop, match="matching"):
        asyncio.run(release.db_revision(aws))


def test_stack_access_denied_never_means_absent():
    from botocore.exceptions import ClientError

    aws = Mock()
    aws.client.return_value.describe_stacks.side_effect = ClientError(
        {"Error": {"Code": "AccessDenied", "Message": "denied"}}, "DescribeStacks"
    )
    with pytest.raises(ClientError):
        release.stack(aws, "peach-ai", optional=True)
    aws.client.return_value.describe_stacks.side_effect = ClientError(
        {"Error": {"Code": "ValidationError", "Message": "Stack does not exist"}},
        "DescribeStacks",
    )
    assert release.stack(aws, "peach-ai", optional=True) is None


def test_private_token_file_permissions(tmp_path):
    path = tmp_path / "token"
    path.write_text("test-token")
    path.chmod(0o644)
    with pytest.raises(release.Stop):
        release.token_file(path)
    path.chmod(0o600)
    assert release.token_file(path) == "test-token"


def test_execution_requires_matching_disabled_parameters():
    aws = Mock()
    aws.client.return_value.describe_change_set.return_value = {
        "ChangeSetId": "arn:changeset",
        "StackName": "peach-ai",
        "Status": "CREATE_COMPLETE",
        "ExecutionStatus": "AVAILABLE",
        "Parameters": [
            {"ParameterKey": "ParserEnabled", "ParameterValue": "true"},
            {"ParameterKey": "ImageUri", "ParameterValue": "image@sha256:expected"},
        ],
    }
    args = SimpleNamespace(change_set_id="arn:changeset")
    with pytest.raises(release.Stop, match="disabled"):
        release.execute_disabled(args, aws, {"new_image": "image@sha256:expected"})
    aws.client.return_value.execute_change_set.assert_not_called()


def test_child_deployment_uses_verified_identity_and_pinned_targets(monkeypatch):
    monkeypatch.setenv("AWS_PROFILE", "another-profile")
    monkeypatch.setenv("AWS_SESSION_TOKEN", "stale-session")
    monkeypatch.setenv("STACK_NAME", "wrong-stack")
    aws = Mock()
    aws.get_credentials.return_value.get_frozen_credentials.return_value = (
        SimpleNamespace(access_key="test-key", secret_key="test-secret", token=None)
    )
    env = release.deployment_environment(aws, "a" * 40)
    assert "AWS_PROFILE" not in env and "AWS_SESSION_TOKEN" not in env
    assert env["AWS_ACCESS_KEY_ID"] == "test-key"
    assert env["PEACH_IGNORE_LOCAL_ENV"] == "true"
    assert env["STACK_NAME"] == "peach-backend"
    assert env["IMAGE_TAG"] == "a" * 12
    monkeypatch.setenv("AWS_ENDPOINT_URL_LAMBDA", "https://unexpected.example")
    with pytest.raises(release.Stop, match="Custom AWS"):
        release.deployment_environment(aws, "a" * 40)
