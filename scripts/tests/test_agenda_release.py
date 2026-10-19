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
        "StorageEncrypted": True,
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
        ("StorageEncrypted", False),
        ("StorageEncrypted", None),
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


def test_persisted_cloudformation_service_role_stops_release():
    aws = Mock()
    aws.client.return_value.describe_stacks.return_value = {
        "Stacks": [{"StackStatus": "UPDATE_COMPLETE", "RoleARN": "arn:unreviewed-role"}]
    }
    with pytest.raises(release.Stop, match="CloudFormation service role"):
        release.stack(aws, "peach-backend")


def nova_read_session():
    aws = Mock()
    services = {
        name: Mock() for name in ("bedrock", "lambda", "service-quotas", "budgets")
    }
    aws.client.side_effect = services.__getitem__
    services["bedrock"].get_foundation_model.return_value = {
        "modelDetails": {
            "modelId": "amazon.nova-lite-v1:0",
            "modelArn": "arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-lite-v1:0",
            "modelLifecycle": {"status": "ACTIVE"},
            "inferenceTypesSupported": ["ON_DEMAND"],
        }
    }
    services["bedrock"].get_foundation_model_availability.return_value = {
        "regionAvailability": "AVAILABLE",
        "authorizationStatus": "AUTHORIZED",
        "entitlementAvailability": "AVAILABLE",
        "agreementAvailability": {"status": "AVAILABLE"},
    }
    services["lambda"].get_account_settings.return_value = {
        "AccountLimit": {"UnreservedConcurrentExecutions": 10}
    }
    services["lambda"].get_function_concurrency.return_value = {}
    services["service-quotas"].get_paginator.return_value.paginate.return_value = [
        {
            "Quotas": [
                {"QuotaCode": "L-70423BF8", "Value": 4000000},
                {"QuotaCode": "L-E386A278", "Value": 200},
            ]
        }
    ]
    return aws, services


def test_nova_reads_reach_budget_gate_without_any_inference(monkeypatch):
    monkeypatch.delenv("PEACH_BUDGET_EMAIL", raising=False)
    aws, services = nova_read_session()
    with pytest.raises(release.Stop, match="budget email"):
        release.read_checks(aws)
    services["bedrock"].get_foundation_model.assert_called_once_with(
        modelIdentifier="amazon.nova-lite-v1:0"
    )
    assert "bedrock-runtime" not in [c.args[0] for c in aws.client.call_args_list]


@pytest.mark.parametrize(
    "change", ["unavailable", "zero_quota", "wrong_quota", "no_on_demand"]
)
def test_nova_readiness_fails_closed(change):
    aws, services = nova_read_session()
    if change == "unavailable":
        services["bedrock"].get_foundation_model_availability.return_value[
            "authorizationStatus"
        ] = "NOT_AUTHORIZED"
    elif change == "no_on_demand":
        services["bedrock"].get_foundation_model.return_value["modelDetails"][
            "inferenceTypesSupported"
        ] = ["PROVISIONED"]
    else:
        q = services["service-quotas"].get_paginator.return_value.paginate.return_value[
            0
        ]["Quotas"][0]
        q.update(
            {"Value": 0}
            if change == "zero_quota"
            else {"QuotaCode": "cross-region-other"}
        )
    with pytest.raises(release.Stop):
        release.read_checks(aws)
    services["budgets"].describe_budgets.assert_not_called()


@pytest.mark.parametrize("agreement", [None, {}, {"status": "NOT_AVAILABLE"}])
def test_missing_or_unavailable_agreement_stops_before_capacity_and_budget(agreement):
    aws, services = nova_read_session()
    availability = services["bedrock"].get_foundation_model_availability.return_value
    if agreement is None:
        availability.pop("agreementAvailability")
    else:
        availability["agreementAvailability"] = agreement
    with pytest.raises(release.Stop, match="agreement"):
        release.read_checks(aws)
    services["lambda"].get_account_settings.assert_not_called()
    services["budgets"].get_paginator.assert_not_called()


@pytest.mark.parametrize(
    "free,ok", [(10, True), (1, True), (0, False), (-1, False), (True, False)]
)
def test_lab_shared_capacity_needs_no_reservation_or_quota_increase(free, ok):
    aws = Mock()
    service = aws.client.return_value
    service.get_account_settings.return_value = {
        "AccountLimit": {
            "UnreservedConcurrentExecutions": free,
        }
    }
    if ok:
        release.check_capacity(aws)
    else:
        with pytest.raises(release.Stop):
            release.check_capacity(aws)
    service.put_function_concurrency.assert_not_called()
    service.get_function_concurrency.assert_not_called()


def test_capacity_read_denial_is_not_ignored():
    from botocore.exceptions import ClientError

    aws = Mock()
    aws.client.return_value.get_account_settings.side_effect = ClientError(
        {"Error": {"Code": "AccessDeniedException", "Message": "denied"}},
        "GetAccountSettings",
    )
    with pytest.raises(ClientError):
        release.check_capacity(aws)


def test_old_smoke_is_reusable_only_for_same_commit_image_and_configuration():
    receipt = {
        "at": "2026-01-01T00:00:00+00:00",
        "commit": "a" * 40,
        "image": "image@sha256:old",
        "parser_modified": "unchanged",
    }
    state = {"new_image": receipt["image"]}
    cfg = {"LastModified": receipt["parser_modified"]}
    release.check_smoke_receipt(receipt, receipt["commit"], state, cfg)
    for key in ["commit", "image", "parser_modified"]:
        with pytest.raises(release.Stop):
            release.check_smoke_receipt(
                {**receipt, key: "changed"}, receipt["commit"], state, cfg
            )


@pytest.mark.parametrize("reservation,ok", [(None, True), (0, False), (1, False)])
def test_parser_configuration_requires_shared_concurrency(reservation, ok):
    aws = Mock()
    service = aws.client.return_value
    service.get_function_configuration.return_value = {
        "State": "Active",
        "LastUpdateStatus": "Successful",
        "Timeout": 30,
        "MemorySize": 512,
        "Environment": {"Variables": {"PARSER_MODEL": "amazon.nova-lite-v1:0"}},
    }
    service.get_function_concurrency.return_value = (
        {} if reservation is None else {"ReservedConcurrentExecutions": reservation}
    )
    if ok:
        release.parser_config(aws)
    else:
        with pytest.raises(release.Stop, match="shared concurrency"):
            release.parser_config(aws)


def gross_budget():
    return {
        "BudgetName": "peach-monthly-cost-alert",
        "BudgetType": "COST",
        "TimeUnit": "MONTHLY",
        "BudgetLimit": {"Amount": "5", "Unit": "USD"},
        "CostTypes": {
            "IncludeCredit": False,
            "IncludeRefund": False,
            "UseBlended": False,
        },
    }


@pytest.mark.parametrize(
    "change",
    [
        {"BudgetName": "other-budget"},
        {"TimeUnit": "DAILY"},
        {"CostFilters": {"Service": ["Amazon Bedrock"]}},
        {
            "FilterExpression": {
                "Dimensions": {"Key": "SERVICE", "Values": ["Amazon Bedrock"]}
            }
        },
        {"CostTypes": {"IncludeCredit": True, "IncludeRefund": False}},
        {"CostTypes": {"IncludeCredit": False, "IncludeRefund": True}},
        {"CostTypes": {}},
    ],
)
def test_budget_gate_rejects_filtered_or_credit_offset_lookalikes(change):
    assert release.matching_budget(gross_budget())
    assert not release.matching_budget({**gross_budget(), **change})


def test_budget_gate_rejects_wrong_direction_notification(monkeypatch):
    monkeypatch.setenv("PEACH_BUDGET_EMAIL", "operator@example.test")
    aws, services = nova_read_session()
    budgets = services["budgets"]
    budgets.get_paginator.return_value.paginate.return_value = [
        {"Budgets": [gross_budget()]}
    ]
    budgets.describe_notifications_for_budget.return_value = {
        "Notifications": [
            {
                "NotificationType": "ACTUAL",
                "ThresholdType": "ABSOLUTE_VALUE",
                "Threshold": 5,
                "ComparisonOperator": "LESS_THAN",
            }
        ]
    }
    with pytest.raises(release.Stop, match="notification"):
        release.read_checks(aws)
    budgets.describe_subscribers_for_notification.assert_not_called()


@pytest.mark.parametrize("tag_status", ["any", "tagged"])
def test_retention_gate_rejects_expiration_of_protected_tags(tag_status):
    import json

    aws = Mock()
    aws.client.return_value.get_lifecycle_policy.return_value = {
        "lifecyclePolicyText": json.dumps(
            {
                "rules": [{"selection": {"tagStatus": tag_status}}],
            }
        )
    }
    with pytest.raises(release.Stop, match="rollback/report"):
        release.check_image_retention(aws, {})
    aws.client.return_value.put_lifecycle_policy.assert_not_called()


def test_proposed_retention_policy_preserves_tagged_digests_and_rejects_untagged():
    aws = Mock()
    ecr = aws.client.return_value
    ecr.get_lifecycle_policy.return_value = {
        "lifecyclePolicyText": (
            release.ROOT / "infra/ecr/peach-backend-lifecycle.json"
        ).read_text()
    }
    digest = "sha256:" + "a" * 64
    images = {
        "peach-report-builder": f"{release.ACCOUNT}.dkr.ecr.{release.REGION}.amazonaws.com/peach-backend@{digest}"
    }
    ecr.describe_images.return_value = {"imageDetails": [{"imageTags": ["retained"]}]}
    release.check_image_retention(aws, images)
    ecr.describe_images.return_value = {"imageDetails": [{}]}
    with pytest.raises(release.Stop, match="untagged"):
        release.check_image_retention(aws, images)
    ecr.put_lifecycle_policy.assert_not_called()
