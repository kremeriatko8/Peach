"""Offline CloudFormation assertions, including dependency-cycle detection."""

from pathlib import Path

import pytest

yaml = pytest.importorskip(
    "yaml", reason="Run with the local cfn-lint validation environment"
)
ROOT = Path(__file__).resolve().parents[2]


class Loader(yaml.SafeLoader):
    pass


def intrinsic(loader, tag, node):
    if isinstance(node, yaml.ScalarNode):
        value = loader.construct_scalar(node)
    elif isinstance(node, yaml.SequenceNode):
        value = loader.construct_sequence(node)
    else:
        value = loader.construct_mapping(node)
    return {tag: value}


Loader.add_multi_constructor("!", intrinsic)


@pytest.fixture
def template():
    return yaml.load((ROOT / "infra/reports.yaml").read_text(), Loader=Loader)


def properties(template, resource):
    return template["Resources"][resource]["Properties"]


def test_schedule_and_delivery_failure_wiring(template):
    schedule = properties(template, "WeeklySchedule")
    assert schedule["State"] == "DISABLED"
    assert schedule["ScheduleExpression"] == "cron(0 7 ? * MON *)"
    assert template["Parameters"]["ReportTimezone"]["AllowedValues"] == ["Europe/Kyiv"]
    assert schedule["ScheduleExpressionTimezone"] == {"Ref": "ReportTimezone"}
    assert schedule["FlexibleTimeWindow"]["Mode"] == "OFF"
    assert schedule["Target"]["Arn"] == {"GetAtt": "WorkQueue.Arn"}
    for token in ("scheduled-time", "execution-id", "schedule-arn", "attempt-number"):
        assert f"<aws.scheduler.{token}>" in schedule["Target"]["Input"]
    assert schedule["Target"]["DeadLetterConfig"]["Arn"] == {
        "GetAtt": "SchedulerDlq.Arn"
    }
    role = properties(template, "SchedulerRole")
    statement = role["Policies"][0]["PolicyDocument"]["Statement"][0]
    assert statement["Action"] == "sqs:SendMessage"
    assert len(statement["Resource"]) == 2


def test_builder_queue_network_image_and_limits(template):
    queue = properties(template, "WorkQueue")
    builder = properties(template, "Builder")
    mapping = properties(template, "BuilderMapping")
    assert queue["VisibilityTimeout"] >= 6 * builder["Timeout"]
    assert builder["Timeout"] == 120
    assert queue["RedrivePolicy"]["maxReceiveCount"] == 3
    assert mapping["BatchSize"] == 1
    assert mapping["ScalingConfig"]["MaximumConcurrency"] == 2
    assert "ReservedConcurrentExecutions" not in builder
    assert "ReservedConcurrentExecutions" not in properties(template, "Mailer")
    assert builder["VpcConfig"]["SecurityGroupIds"] == {
        "Ref": "BackendFunctionSecurityGroupIds"
    }
    assert builder["ImageConfig"]["Command"] == ["app.reporting.builder.handler"]
    assert "@sha256:" in template["Parameters"]["ImageUri"]["AllowedPattern"]
    assert builder["Environment"]["Variables"]["REPORT_OWNER_SUB"] == {
        "Ref": "ReportOwnerSub"
    }
    assert template["Parameters"]["AllowDirectEvents"]["Default"] == "false"
    assert all(
        properties(template, name)["SqsManagedSseEnabled"]
        for name in ("WorkQueue", "BuilderDlq", "SchedulerDlq", "MailerFailureQueue")
    )


def test_private_bucket_lifecycle_permissions_and_endpoint(template):
    bucket = properties(template, "ReportsBucket")
    assert all(bucket["PublicAccessBlockConfiguration"].values())
    assert (
        bucket["OwnershipControls"]["Rules"][0]["ObjectOwnership"]
        == "BucketOwnerEnforced"
    )
    assert (
        bucket["BucketEncryption"]["ServerSideEncryptionConfiguration"][0][
            "ServerSideEncryptionByDefault"
        ]["SSEAlgorithm"]
        == "AES256"
    )
    assert bucket["LifecycleConfiguration"]["Rules"][0]["ExpirationInDays"] == 90
    notification = bucket["NotificationConfiguration"]["LambdaConfigurations"][0]
    assert notification["Event"] == "s3:ObjectCreated:*"
    assert notification["Filter"]["S3Key"]["Rules"] == [
        {"Name": "prefix", "Value": "reports/"},
        {"Name": "suffix", "Value": ".csv"},
    ]
    policy = properties(template, "ReportsBucketPolicy")["PolicyDocument"]
    assert policy["Statement"][0]["Condition"] == {
        "Bool": {"aws:SecureTransport": "false"}
    }
    assert "aws:SourceVpce" not in str(policy)
    endpoint = properties(template, "S3Endpoint")
    assert endpoint["VpcEndpointType"] == "Gateway"
    assert endpoint["RouteTableIds"] == {"Ref": "RouteTableIds"}
    assert all(
        resource["Type"]
        not in {"AWS::EC2::NatGateway", "AWS::RDS::DBCluster", "AWS::RDS::DBInstance"}
        for resource in template["Resources"].values()
    )


def test_mailer_failure_dedup_and_iam(template):
    mailer = properties(template, "Mailer")
    assert "VpcConfig" not in mailer
    assert "DATABASE_URL" not in mailer["Environment"]["Variables"]
    assert "REPORT_OWNER_SUB" not in mailer["Environment"]["Variables"]
    state = properties(template, "MailState")
    assert state["BillingMode"] == "PAY_PER_REQUEST"
    assert (
        "TimeToLiveSpecification" not in state
    )  # SENT markers persist after report expiry.
    async_config = properties(template, "MailerAsyncConfig")
    assert async_config["MaximumRetryAttempts"] == 2
    assert async_config["DestinationConfig"]["OnFailure"]["Destination"] == {
        "GetAtt": "MailerFailureQueue.Arn"
    }
    role = properties(template, "MailerRole")
    statements = role["Policies"][0]["PolicyDocument"]["Statement"]
    ses = next(row for row in statements if row["Action"] == "ses:SendRawEmail")
    assert "ses:FromAddress" in ses["Condition"]["StringEquals"]
    assert "ses:Recipients" in ses["Condition"]["ForAllValues:StringEquals"]
    assert not any(row["Action"] == "*" for row in statements)


def test_cloudformation_dependencies_are_acyclic(template):
    resources = template["Resources"]

    def references(value):
        found = set()
        if isinstance(value, dict):
            for key, child in value.items():
                if key in {"Ref", "GetAtt"} and isinstance(child, str):
                    found.add(child.split(".")[0])
                elif key == "Sub":
                    import re

                    for name in re.findall(
                        r"\$\{([^}]+)\}", child if isinstance(child, str) else child[0]
                    ):
                        found.add(name.split(".")[0])
                found |= references(child)
        elif isinstance(value, list):
            for child in value:
                found |= references(child)
        return found

    edges = {}
    for name, resource in resources.items():
        depends = resource.get("DependsOn", [])
        if isinstance(depends, str):
            depends = [depends]
        edges[name] = (references(resource) | set(depends)) & resources.keys()
    completed = set()

    def visit(name, active):
        assert name not in active, f"CloudFormation cycle at {name}"
        if name in completed:
            return
        for target in edges[name]:
            visit(target, active | {name})
        completed.add(name)

    for name in resources:
        visit(name, set())


def test_no_automatic_production_reporting_deployment():
    workflow = (ROOT / ".github/workflows/deploy-backend.yml").read_text()
    assert "  push:" in workflow and "  workflow_dispatch:" in workflow
    # Linting the template/building handlers is safe; no reporting deployment is invoked.
    assert "make reports-prepare" not in workflow
    assert "make report-now" not in workflow
    assert "cloudformation execute-change-set" not in workflow
    assert "reports.yaml" not in (ROOT / "scripts/deploy-backend.sh").read_text()
    assert "reporting" not in (ROOT / "infra/github-oidc.yaml").read_text()


def test_shared_endpoint_preserves_clients_without_broadening_report_roles(template):
    endpoint = properties(template, "S3Endpoint")["PolicyDocument"]
    assert endpoint["Statement"] == [
        {
            "Sid": "PreserveExistingS3Authorization",
            "Effect": "Allow",
            "Principal": "*",
            "Action": "s3:*",
            "Resource": "*",
        }
    ]
    for role, action in (
        ("BuilderRole", "s3:PutObject"),
        ("MailerRole", "s3:GetObject"),
    ):
        statements = properties(template, role)["Policies"][0]["PolicyDocument"][
            "Statement"
        ]
        s3_statements = [s for s in statements if "s3:" in str(s["Action"])]
        assert s3_statements == [
            {
                "Effect": "Allow",
                "Action": action,
                "Resource": {
                    "Sub": "arn:${AWS::Partition}:s3:::${ProjectName}-reports-${AWS::AccountId}-${AWS::Region}/reports/${ReportScopeId}/*.csv"
                },
            }
        ]
    bucket_policy = properties(template, "ReportsBucketPolicy")["PolicyDocument"]
    assert all(s["Effect"] == "Deny" for s in bucket_policy["Statement"])
    assert "SourceVpce" not in str(bucket_policy)
