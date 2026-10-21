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


def console_budget():
    return {
        "BudgetName": "peach-monthly-cost-alert",
        "BudgetType": "COST",
        "TimeUnit": "MONTHLY",
        "BudgetLimit": {"Amount": "5.0", "Unit": "USD"},
        "Metrics": ["UnblendedCost"],
        "FilterExpression": {
            "Not": {
                "Dimensions": {"Key": "RECORD_TYPE", "Values": ["Credit", "Refund"]}
            }
        },
        "BillingViewArn": "arn:aws:billing::968053399627:billingview/primary",
    }


@pytest.mark.parametrize("legacy", [True, False])
def test_equivalent_budget_representations_preserve_gross_cost_checks(legacy):
    budget = gross_budget() if legacy else console_budget()
    assert release.matching_budget(budget)
    if not legacy:
        budget["CostTypes"] = None
        budget["FilterExpression"]["Not"]["Dimensions"]["Values"].reverse()
        assert release.matching_budget(budget)


@pytest.mark.parametrize(
    "change",
    [
        {"BudgetName": "other"},
        {"BudgetType": "USAGE"},
        {"TimeUnit": "DAILY"},
        {"BudgetLimit": {"Amount": "6", "Unit": "USD"}},
        {"BudgetLimit": {"Amount": "5", "Unit": "EUR"}},
        {"BudgetLimit": {"Amount": "nan", "Unit": "USD"}},
        {"BudgetLimit": {"Amount": {}, "Unit": "USD"}},
        {"BudgetLimit": None},
        {"Metrics": ["NetUnblendedCost"]},
        {"Metrics": ["BlendedCost"]},
        {"Metrics": ["AmortizedCost"]},
        {"Metrics": []},
        {"FilterExpression": None},
        {"FilterExpression": {"Not": None}},
        {"FilterExpression": {"Not": {"Dimensions": None}}},
        {
            "FilterExpression": {
                "Not": {"Dimensions": {"Key": "RECORD_TYPE", "Values": ["Credit"]}}
            }
        },
        {
            "FilterExpression": {
                "Not": {
                    "Dimensions": {
                        "Key": "RECORD_TYPE",
                        "Values": ["Credit", "Refund", "Tax"],
                    }
                }
            }
        },
        {
            "FilterExpression": {
                "Dimensions": {"Key": "SERVICE", "Values": ["Amazon Bedrock"]}
            }
        },
        {"CostFilters": {"Region": ["us-east-1"]}},
        {"CostTypes": {"IncludeCredit": True}},
        {"CostTypes": []},
        {"BillingViewArn": "arn:aws:billing::968053399627:billingview/custom"},
    ],
)
def test_console_budget_rejects_wrong_amount_basis_filters_or_malformed_structure(
    change,
):
    assert not release.matching_budget({**console_budget(), **change})


@pytest.mark.parametrize(
    "kind,threshold,ok",
    [
        ("omitted", 85, True),
        ("omitted", 100, True),
        ("PERCENTAGE", 100, True),
        ("ABSOLUTE_VALUE", 5, True),
        ("ABSOLUTE_VALUE", 4.25, True),
        ("PERCENTAGE", 101, False),
        ("ABSOLUTE_VALUE", 5.01, False),
        (None, 100, False),
        ("unknown", 5, False),
        ("omitted", 0, False),
        ("omitted", -1, False),
        ("omitted", "100", False),
        ("omitted", True, False),
        ("omitted", float("nan"), False),
        ("omitted", float("inf"), False),
    ],
)
def test_notification_default_percentage_and_bounded_threshold(kind, threshold, ok):
    notice = {
        "NotificationType": "ACTUAL",
        "ComparisonOperator": "GREATER_THAN",
        "Threshold": threshold,
    }
    if kind != "omitted":
        notice["ThresholdType"] = kind
    assert release.matching_notification(notice) is ok
    assert not release.matching_notification(
        {**notice, "NotificationType": "FORECASTED"}
    )
    assert not release.matching_notification(
        {**notice, "ComparisonOperator": "LESS_THAN"}
    )


@pytest.mark.parametrize("legacy", [True, False])
@pytest.mark.parametrize(
    "subscriber,ok",
    [
        ({"SubscriptionType": "EMAIL", "Address": "operator@example.test"}, True),
        ({"SubscriptionType": "EMAIL", "Address": "other@example.test"}, False),
        ({"SubscriptionType": "SNS", "Address": "operator@example.test"}, False),
    ],
)
def test_complete_budget_gate_accepts_only_matching_email_for_both_formats(
    monkeypatch, legacy, subscriber, ok
):
    monkeypatch.setenv("PEACH_BUDGET_EMAIL", "operator@example.test")
    monkeypatch.setattr(release, "stack", lambda *a, **k: None)
    aws, services = nova_read_session()
    b = services["budgets"]
    b.get_paginator.return_value.paginate.return_value = [
        {"Budgets": [gross_budget() if legacy else console_budget()]}
    ]
    notice = {
        "NotificationType": "ACTUAL",
        "ComparisonOperator": "GREATER_THAN",
        "Threshold": 100,
    }
    if legacy:
        notice["ThresholdType"] = "PERCENTAGE"
    b.describe_notifications_for_budget.return_value = {"Notifications": [notice]}
    b.describe_subscribers_for_notification.return_value = {"Subscribers": [subscriber]}
    if ok:
        release.read_checks(aws)
    else:
        with pytest.raises(release.Stop, match="email notification"):
            release.read_checks(aws)
    assert "bedrock-runtime" not in [c.args[0] for c in aws.client.call_args_list]


@pytest.mark.parametrize(
    "change",
    [
        {"Metrics": ["NetUnblendedCost"]},
        {
            "CostTypes": {
                "IncludeCredit": False,
                "IncludeRefund": False,
                "UseBlended": True,
            }
        },
        {
            "CostTypes": {
                "IncludeCredit": False,
                "IncludeRefund": False,
                "UseAmortized": True,
            }
        },
        {"CostTypes": {"IncludeCredit": False}},
    ],
)
def test_legacy_budget_cannot_relax_cost_basis_when_console_support_is_added(change):
    assert not release.matching_budget({**gross_budget(), **change})


@pytest.mark.parametrize(
    "version,accepted", [("agenda-v3", True), ("agenda-v2", False)]
)
def test_paid_smoke_checks_current_prompt_version_offline(
    monkeypatch, tmp_path, version, accepted
):
    import httpx

    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[2] / "backend"))
    monkeypatch.setattr(release, "load_state", lambda args: {"new_image": "pinned"})
    monkeypatch.setattr(
        release,
        "parser_config",
        lambda aws: {
            "Environment": {"Variables": {"PARSER_ENABLED": "true"}},
            "LastModified": "same",
        },
    )
    monkeypatch.setattr(release, "image", lambda *a: "pinned")
    monkeypatch.setattr(release, "stack", lambda *a: {})
    monkeypatch.setattr(
        release, "outputs", lambda *a: {"ParserUrl": "https://parser.test"}
    )
    monkeypatch.setattr(release, "token_file", lambda *a: "synthetic-unit-test-token")
    client = Mock()
    client.post.side_effect = [
        httpx.Response(401),
        httpx.Response(413),
        httpx.Response(
            200,
            json={
                "agenda": {"items": [], "language": "en"},
                "model": "amazon.nova-lite-v1:0",
                "prompt_version": version,
            },
        ),
    ]
    context = Mock()
    context.__enter__ = Mock(return_value=client)
    context.__exit__ = Mock(return_value=False)
    monkeypatch.setattr(httpx, "Client", Mock(return_value=context))
    args = SimpleNamespace(
        commit="c" * 40,
        directory=tmp_path,
        token_file=None,
        approve=f"{release.ACCOUNT}:{'c' * 40}:paid-smoke",
    )
    if accepted:
        release.smoke(args, Mock(), paid=True)
        assert (tmp_path / "paid-smoke.json").exists()
    else:
        with pytest.raises(release.Stop):
            release.smoke(args, Mock(), paid=True)
        assert not (tmp_path / "paid-smoke.json").exists()
    assert client.post.call_count == 3
