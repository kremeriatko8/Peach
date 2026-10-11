"""Offline IAM review assertions. No AWS calls, credentials or databases."""

import importlib.util
import json
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]
POLICIES = ROOT / "infra/iam/reports"
ACCOUNT = "968053399627"
REGION = "us-east-1"
REFERENCE = json.loads((POLICIES / "action-reference.json").read_text())["actions"]


def policy(name):
    return json.loads((POLICIES / f"{name}.json").read_text())


def many(value):
    return [value] if isinstance(value, str) else value


def actions(name):
    return {
        action
        for statement in policy(name)["Statement"]
        if statement["Effect"] == "Allow"
        for action in many(statement["Action"])
    }


def statement(name, sid):
    return next(s for s in policy(name)["Statement"] if s.get("Sid") == sid)


IDENTITY_NAMES = sorted(
    p.stem
    for p in POLICIES.glob("*.json")
    if p.name.startswith(("deployment-", "operator-", "runtime-"))
    or p.name
    in {
        "optional-console-discovery.json",
        "optional-image-publish.json",
        "optional-ecr-retrieval-bootstrap.json",
        "optional-pass-cloudformation-role.json",
    }
)


@pytest.mark.parametrize("name", IDENTITY_NAMES)
def test_identity_policy_syntax_actions_and_managed_policy_limit(name):
    document = policy(name)
    assert document["Version"] == "2012-10-17"
    assert len(json.dumps(document, separators=(",", ":"))) <= 6144
    for s in document["Statement"]:
        assert s["Effect"] in {"Allow", "Deny"}
        assert "Principal" not in s and "NotAction" not in s
        assert len(many(s["Resource"])) > 0
        for action in many(s["Action"]):
            assert action in REFERENCE
            if not REFERENCE[action]["resources"]:
                assert s["Resource"] == "*", (name, action)
        for resource in many(s["Resource"]):
            if resource == "*":
                continue
            assert resource.startswith("arn:aws:")
            parts = resource.split(":", 5)
            assert parts[3] in {REGION, ""}
            assert parts[4] in {ACCOUNT, ""}
            assert (
                "peach" in resource
                or ":ec2:" in resource
                or ":event-source-mapping:" in resource
                or resource.endswith("identity/__SENDER_EMAIL__")
                or resource
                == f"arn:aws:cognito-idp:{REGION}:{ACCOUNT}:userpool/us-east-1_bs7cWxhJp"
            )


def test_every_wildcard_allow_has_documented_scope():
    for name in IDENTITY_NAMES:
        for s in policy(name)["Statement"]:
            if s["Effect"] != "Allow" or s["Resource"] != "*":
                continue
            if name == "optional-console-discovery" and s["Sid"] == "BucketConsoleList":
                assert s["Action"] == "s3:ListAllMyBuckets"
            elif s["Sid"] == "CreateOnlyBuilderMapping":
                assert s["Condition"]["ArnEquals"]["lambda:FunctionArn"].endswith(
                    ":function:peach-report-builder"
                )
            else:
                assert s["Condition"]["StringEquals"]["aws:RequestedRegion"] == REGION
            assert all("*" not in action for action in many(s["Action"]))


def test_deployment_cannot_send_read_private_objects_or_mutate_production_db():
    granted = set().union(
        *(actions(n) for n in IDENTITY_NAMES if n.startswith("deployment-"))
    )
    assert not any(
        a.startswith(
            (
                "rds:",
                "rds-db:",
                "secretsmanager:",
                "ses:",
                "cognito",
                "kms:",
                "cloudwatch:",
                "sns:",
                "events:",
            )
        )
        for a in granted
    )
    assert not granted & {
        "sqs:SendMessage",
        "sqs:ReceiveMessage",
        "sqs:PurgeQueue",
        "lambda:InvokeFunction",
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject",
        "dynamodb:GetItem",
        "dynamodb:UpdateItem",
        "dynamodb:Scan",
        "dynamodb:Query",
        "iam:CreateServiceLinkedRole",
        "iam:AttachRolePolicy",
        "ec2:CreateNatGateway",
        "ec2:CreateRoute",
        "ec2:DeleteRouteTable",
        "ec2:AuthorizeSecurityGroupIngress",
    }


def test_provider_scoped_reads_are_complete_without_optional_feature_writes():
    reference = json.loads((POLICIES / "provider-read-reference.json").read_text())
    assert set(reference["s3_bucket_read"]) <= actions("deployment-data")
    assert set(reference["dynamodb_table_read"]) <= actions("deployment-data")
    assert not actions("deployment-data") & {
        "s3:PutBucketReplication",
        "s3:PutReplicationConfiguration",
        "s3:PutObjectAcl",
        "dynamodb:CreateTableReplica",
        "dynamodb:ImportTable",
        "dynamodb:UpdateTimeToLive",
    }
    for kind in ("endpoint_tagging", "mapping_tagging"):
        assert reference[kind]["cloudFormationSystemTags"] is True
        assert reference[kind]["tagOnCreate"] is True


def test_three_exact_runtime_roles_and_service_specific_passrole():
    role_management = statement("deployment-compute", "ThreeInlineRuntimeRoles")
    assert set(role_management["Resource"]) == {
        f"arn:aws:iam::{ACCOUNT}:role/peach-report-{n}"
        for n in ("builder", "mailer", "scheduler")
    }
    for sid, service in (
        ("PassOnlyLambdaRoles", "lambda"),
        ("PassOnlySchedulerRole", "scheduler"),
    ):
        s = statement("deployment-compute", sid)
        assert s["Action"] == "iam:PassRole"
        assert (
            s["Condition"]["StringEquals"]["iam:PassedToService"]
            == f"{service}.amazonaws.com"
        )
    assert "iam:PassRole" not in actions("runtime-builder")
    assert "iam:PassRole" not in actions("runtime-mailer")
    assert "iam:PassRole" not in actions("runtime-scheduler")


def test_mapping_arn_conditions_and_s3_invoke_principal():
    for sid in ("CreateOnlyBuilderMapping", "ManageOnlyBuilderMapping"):
        s = statement("deployment-compute", sid)
        assert s["Condition"]["ArnEquals"]["lambda:FunctionArn"] == (
            f"arn:aws:lambda:{REGION}:{ACCOUNT}:function:peach-report-builder"
        )
    assert statement("deployment-compute", "ManageOnlyBuilderMapping")["Resource"] == (
        f"arn:aws:lambda:{REGION}:{ACCOUNT}:event-source-mapping:*"
    )
    s = statement("deployment-compute", "OnlyS3MayGainMailerInvocation")
    assert s["Condition"]["StringEquals"]["lambda:Principal"] == "s3.amazonaws.com"


def test_gateway_creation_and_ownership_scopes():
    s = statement("deployment-network", "ApprovedGatewayVpcAndRoute")
    assert set(s["Resource"]) == {
        f"arn:aws:ec2:{REGION}:{ACCOUNT}:vpc/vpc-0def9c995c9c73f75",
        f"arn:aws:ec2:{REGION}:{ACCOUNT}:route-table/rtb-0fb1d48c2f3f092c2",
    }
    s = statement("deployment-network", "CreateOnlyStackOwnedS3Endpoint")
    assert (
        s["Condition"]["StringEquals"]["ec2:VpceServiceName"]
        == "com.amazonaws.us-east-1.s3"
    )
    assert (
        s["Condition"]["StringEquals"]["aws:RequestTag/aws:cloudformation:stack-name"]
        == "peach-reports"
    )
    for name, sid in (
        ("deployment-network", "ManageOnlyReportingStackEndpoint"),
        ("deployment-compute", "OwnedMappingTags"),
    ):
        s = statement(name, sid)
        assert (
            s["Condition"]["StringEquals"][
                "aws:ResourceTag/aws:cloudformation:stack-name"
            ]
            == "peach-reports"
        )
        assert s["Condition"]["StringLike"][
            "aws:ResourceTag/aws:cloudformation:stack-id"
        ].endswith("stack/peach-reports/*")


def test_runtime_minimum_api_separation_and_sender_restrictions():
    assert actions("runtime-scheduler") == {"sqs:SendMessage"}
    assert "ses:SendRawEmail" not in actions("runtime-builder")
    assert not any(a.startswith("ec2:") for a in actions("runtime-mailer"))
    assert actions("runtime-mailer") == {
        "logs:CreateLogStream",
        "logs:PutLogEvents",
        "s3:GetObject",
        "dynamodb:GetItem",
        "dynamodb:UpdateItem",
        "ses:SendRawEmail",
        "sqs:SendMessage",
    }
    s = statement("runtime-mailer", "SendOnlyVerifiedSenderToApprovedInbox")
    assert s["Resource"] == f"arn:aws:ses:{REGION}:{ACCOUNT}:identity/__SENDER_EMAIL__"
    assert s["Condition"]["StringEquals"]["ses:FromAddress"] == "__SENDER_EMAIL__"
    assert s["Condition"]["ForAllValues:StringEquals"]["ses:Recipients"] == [
        "__RECIPIENT_EMAIL__"
    ]
    assert s["Condition"]["Null"]["ses:Recipients"] == "false"
    s = statement("runtime-builder", "FunctionCodeCannotManageNetwork")
    assert s["Effect"] == "Deny"
    assert s["Condition"]["ArnEquals"]["lambda:SourceFunctionArn"].endswith(
        ":peach-report-builder"
    )


def test_operator_mutations_are_explicit_separate_and_bounded():
    assert actions("operator-enqueue") == {
        "cloudformation:DescribeStacks",
        "sqs:SendMessage",
    }
    assert actions("operator-activation") == {
        "scheduler:GetSchedule",
        "scheduler:UpdateSchedule",
        "iam:PassRole",
    }
    assert not actions("operator-readiness") & {
        "sqs:ReceiveMessage",
        "sqs:SendMessage",
        "lambda:InvokeFunction",
        "ses:SendRawEmail",
    }
    invoke = statement("operator-recovery", "ReplayOnlyMailerRequestPayload")
    assert invoke["Resource"].endswith(":function:peach-report-mailer")
    redrive = statement("operator-recovery", "BuilderDlqRedrive")
    assert redrive["Resource"].endswith(":peach-report-builder-dlq")


def test_template_names_disabled_state_and_no_database_resources():
    from test_reports_infra import Loader

    resources = yaml.load((ROOT / "infra/reports.yaml").read_text(), Loader=Loader)[
        "Resources"
    ]
    assert not any(r["Type"].startswith("AWS::RDS::") for r in resources.values())
    assert not any(r["Type"] == "AWS::CloudWatch::Alarm" for r in resources.values())
    for logical, suffix in (
        ("BuilderRole", "builder"),
        ("MailerRole", "mailer"),
        ("SchedulerRole", "scheduler"),
    ):
        assert (
            resources[logical]["Properties"]["RoleName"]["Sub"]
            == f"${{ProjectName}}-report-{suffix}"
        )
    assert resources["WeeklySchedule"]["Properties"]["State"] == "DISABLED"
    assert (
        resources["WeeklySchedule"]["Properties"]["Name"]["Sub"]
        == "${ProjectName}-weekly-report"
    )
    assert resources["S3Endpoint"]["Properties"]["VpcEndpointType"] == "Gateway"
    assert resources["Builder"]["Properties"]["VpcConfig"]["SecurityGroupIds"] == {
        "Ref": "BackendFunctionSecurityGroupIds"
    }
    assert "VpcConfig" not in resources["Mailer"]["Properties"]


def test_automatic_backend_workflow_has_no_reporting_deployment():
    workflow = yaml.load(
        (ROOT / ".github/workflows/deploy-backend.yml").read_text(),
        Loader=yaml.BaseLoader,
    )
    assert workflow["on"]["push"]["branches"] == ["main"]
    assert workflow["jobs"]["deploy"]["needs"] == "validate"
    text = (ROOT / ".github/workflows/deploy-backend.yml").read_text()
    assert "make deploy-backend" in text
    assert "make reports-prepare" not in text and "make report-now" not in text
    assert "peach-reports-cfn-exec" not in text


@pytest.fixture
def renderer(tmp_path):
    spec = importlib.util.spec_from_file_location(
        "prepare_reports_iam", ROOT / "scripts/prepare-reports-iam.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    module.PRIVATE_ROOT = tmp_path / "private"
    module.PRIVATE_ROOT.mkdir()
    config = module.PRIVATE_ROOT / "config.json"
    config.write_text(
        json.dumps(
            {
                "sender": "sender@example.invalid",
                "recipient": "recipient@example.invalid",
                "scope": "test-opaque-scope",
            }
        )
    )
    return module, config, module.PRIVATE_ROOT / "rendered"


def test_offline_renderer_modes_placeholders_and_no_network(renderer):
    module, config, destination = renderer
    with patch("socket.socket", side_effect=AssertionError("No network allowed")):
        names = module.render(config, destination)
    assert len(names) == 25
    assert destination.stat().st_mode & 0o777 == 0o700
    for name in names:
        path = destination / name
        assert path.stat().st_mode & 0o777 == 0o600
        assert "__REPORT_SCOPE_ID__" not in path.read_text()
        assert "__SENDER_EMAIL__" not in path.read_text()
        assert "__RECIPIENT_EMAIL__" not in path.read_text()
        json.loads(path.read_text())
    assert "sender@example.invalid" in (destination / "runtime-mailer.json").read_text()


@pytest.mark.parametrize(
    "field,value",
    [
        ("scope", "../../escape"),
        ("scope", "*"),
        ("scope", "Raw-Subject"),
        ("sender", "*@gmail.com"),
        ("recipient", "x@gmail.com,other@gmail.com"),
    ],
)
def test_renderer_refuses_unsafe_scope_or_address(renderer, field, value):
    module, config, destination = renderer
    values = json.loads(config.read_text())
    values[field] = value
    config.write_text(json.dumps(values))
    with pytest.raises(ValueError):
        module.render(config, destination)
    assert not destination.exists()


def test_renderer_refuses_tracked_output_or_input_and_symlink(renderer, tmp_path):
    module, config, destination = renderer
    with pytest.raises(ValueError):
        module.render(config, tmp_path / "tracked")
    outside = tmp_path / "outside.json"
    outside.write_text(config.read_text())
    with pytest.raises(ValueError):
        module.render(outside, destination)
    destination.mkdir()
    (destination / "deployment-control.json").symlink_to(outside)
    before = outside.read_text()
    with pytest.raises(OSError):
        module.render(config, destination)
    assert outside.read_text() == before


def test_public_templates_and_docs_have_placeholders_not_inboxes():
    for path in POLICIES.iterdir():
        if path.is_file():
            assert "@gmail.com" not in path.read_text()
    assert "__SENDER_EMAIL__" in (POLICIES / "runtime-mailer.json").read_text()
    # Ignore evidence from previous tasks; validate this bundle and its private path contract.
    assert "reports-local/" in (ROOT / ".gitignore").read_text()


def test_shared_endpoint_review_matches_template_and_is_not_identity_permission():
    from test_reports_infra import Loader

    template = yaml.load((ROOT / "infra/reports.yaml").read_text(), Loader=Loader)
    assert (
        policy("resource-s3-endpoint")
        == template["Resources"]["S3Endpoint"]["Properties"]["PolicyDocument"]
    )
    assert "resource-s3-endpoint" not in IDENTITY_NAMES
    for name, action in (
        ("runtime-builder", "s3:PutObject"),
        ("runtime-mailer", "s3:GetObject"),
    ):
        s3_statements = [
            s
            for s in policy(name)["Statement"]
            if s["Effect"] == "Allow"
            and any(a.startswith("s3:") for a in many(s["Action"]))
        ]
        assert len(s3_statements) == 1
        assert many(s3_statements[0]["Action"]) == [action]
        assert s3_statements[0]["Resource"].endswith(
            "/reports/__REPORT_SCOPE_ID__/*.csv"
        )


def test_cloudformation_change_sets_authorize_stack_not_change_set_arns():
    from fnmatch import fnmatchcase

    create = statement("deployment-control", "CreateNamedReviewedReportingChangeSet")
    review = statement("deployment-control", "ReviewAndExecuteOnlyReportingChangeSets")
    stack_pattern = f"arn:aws:cloudformation:{REGION}:{ACCOUNT}:stack/peach-reports/*"
    for action in (
        "cloudformation:CreateChangeSet",
        "cloudformation:DescribeChangeSet",
        "cloudformation:ExecuteChangeSet",
        "cloudformation:DeleteChangeSet",
    ):
        assert REFERENCE[action]["resources"] == [{"Name": "stack"}]
        assert "cloudformation:ChangeSetName" in REFERENCE[action]["conditions"]
    assert create["Resource"] == review["Resource"] == stack_pattern
    assert fnmatchcase(stack_pattern.replace("*", "future-generated-id"), stack_pattern)
    assert not fnmatchcase(
        stack_pattern.replace("peach-reports/", "peach-backend/"), stack_pattern
    )
    assert create["Condition"] == {
        "StringLike": {"cloudformation:ChangeSetName": "peach-reports-*"}
    }
    assert create["Action"] == ["cloudformation:CreateChangeSet"]
    assert "cloudformation:ExecuteChangeSet" in review["Action"]
    assert "Condition" not in review
    assert not any(
        ":changeSet/" in str(s["Resource"])
        for s in policy("deployment-control")["Statement"]
    )


def test_compute_authorization_conditions_and_log_group_arn_forms():
    evidence = policy("provider-read-reference")["compute_authorization_review"]
    mapping_actions = evidence["lambda_actions"]
    assert mapping_actions["CreateEventSourceMapping"]["resources"] == []
    for name in (
        "CreateEventSourceMapping",
        "GetEventSourceMapping",
        "UpdateEventSourceMapping",
        "DeleteEventSourceMapping",
    ):
        assert "lambda:FunctionArn" in mapping_actions[name]["conditions"]
        if name != "CreateEventSourceMapping":
            assert mapping_actions[name]["resources"] == [
                {"Name": "eventSourceMapping"}
            ]
    assert "aws:RequestTag/${TagKey}" in mapping_actions["TagResource"]["conditions"]
    assert "aws:ResourceTag/${TagKey}" in evidence["mapping_resource"]["ConditionKeys"]
    for name in ("TagResource", "UntagResource", "ListTags"):
        assert "lambda:FunctionArn" not in mapping_actions[name]["conditions"]
    for name in ("TwoLogGroups", "LogGroupTags"):
        resources = statement("deployment-compute", name)["Resource"]
        suffix = ":*" if name == "TwoLogGroups" else ""
        assert set(resources) == {
            f"arn:aws:logs:{REGION}:{ACCOUNT}:log-group:/aws/lambda/peach-report-{role}{suffix}"
            for role in ("builder", "mailer")
        }
    roles = statement("deployment-compute", "ThreeInlineRuntimeRoles")
    assert set(roles["Resource"]) == {
        f"arn:aws:iam::{ACCOUNT}:role/peach-report-{role}"
        for role in ("builder", "mailer", "scheduler")
    }
    assert not {
        "iam:AttachRolePolicy",
        "iam:PutRolePermissionsBoundary",
        "iam:DeleteRolePermissionsBoundary",
    } & actions("deployment-compute")
    assert "iam:PassedToService" in evidence["iam_pass_role"]["ActionConditionKeys"]


def test_endpoint_conditions_are_supported_on_correct_ec2_resource_checks():
    evidence = policy("provider-read-reference")["network_authorization_review"][
        "actions"
    ]

    def keys(action, resource):
        return next(
            r["ConditionKeys"]
            for r in evidence[action]["resources"]
            if r["Name"] == resource
        )

    assert {r["Name"] for r in evidence["CreateVpcEndpoint"]["resources"]} == {
        "vpc",
        "route-table",
        "vpc-endpoint",
    }
    assert "ec2:VpceServiceName" in keys("CreateVpcEndpoint", "vpc-endpoint")
    assert "aws:RequestTag/${TagKey}" in keys("CreateVpcEndpoint", "vpc-endpoint")
    assert "ec2:VpceServiceName" not in keys("CreateVpcEndpoint", "route-table")
    assert "Condition" not in statement(
        "deployment-network", "ApprovedGatewayVpcAndRoute"
    )
    assert "Condition" not in statement(
        "deployment-network", "OnlyApprovedEndpointRouteUpdates"
    )
    assert statement("deployment-network", "OnlyApprovedEndpointRouteUpdates")[
        "Resource"
    ].endswith("route-table/rtb-0fb1d48c2f3f092c2")
    assert {r["Name"] for r in evidence["DeleteVpcEndpoints"]["resources"]} == {
        "vpc-endpoint"
    }
    for action in (
        "ModifyVpcEndpoint",
        "DeleteVpcEndpoints",
        "CreateTags",
        "DeleteTags",
    ):
        assert "aws:ResourceTag/${TagKey}" in keys(action, "vpc-endpoint")
    assert "ec2:CreateAction" in evidence["CreateTags"]["conditions"]
    assert (
        statement("deployment-network", "TagNewEndpoint")["Condition"]["StringEquals"][
            "ec2:CreateAction"
        ]
        == "CreateVpcEndpoint"
    )
    assert "ec2:CreateAction" not in str(
        statement("deployment-network", "ManageOnlyReportingStackEndpoint")["Condition"]
    )
    assert not {
        "ec2:CreateRoute",
        "ec2:DeleteRoute",
        "ec2:ReplaceRoute",
        "ec2:CreateNatGateway",
    } & actions("deployment-network")


def test_temporary_evidence_policy_is_read_only_and_exactly_scoped():
    doc = policy("operator-evidence-bootstrap")
    assert actions("operator-evidence-bootstrap") == {
        "cognito-idp:ListUsers",
        "cloudformation:DescribeStacks",
        "logs:FilterLogEvents",
    }
    assert {s["Resource"] for s in doc["Statement"]} == {
        f"arn:aws:cognito-idp:{REGION}:{ACCOUNT}:userpool/us-east-1_bs7cWxhJp",
        f"arn:aws:cloudformation:{REGION}:{ACCOUNT}:stack/peach-migrations/*",
        f"arn:aws:logs:{REGION}:{ACCOUNT}:log-group:/aws/lambda/peach-migrations:*",
    }
    assert REFERENCE["cognito-idp:ListUsers"]["resources"] == [{"Name": "userpool"}]
    for s in doc["Statement"]:
        assert s["Condition"] == {"StringEquals": {"aws:RequestedRegion": REGION}}


def test_backend_release_supplement_excludes_infrastructure_and_iam_mutations():
    backend = statement(
        "operator-backend-release-completion", "ExecuteOnlyReviewedBackendChangeSet"
    )
    assert backend["Action"] == "cloudformation:ExecuteChangeSet"
    assert backend["Resource"] == (
        f"arn:aws:cloudformation:{REGION}:{ACCOUNT}:stack/peach-backend/*"
    )
    names = actions("operator-backend-release-completion")
    assert {
        "cloudformation:ExecuteChangeSet",
        "lambda:InvokeFunction",
        "lambda:UpdateFunctionCode",
        "iam:PassRole",
    } <= names
    assert not any(a.startswith(("rds:", "ec2:", "secretsmanager:")) for a in names)
    assert (
        not {
            "iam:PutRolePolicy",
            "iam:CreateRole",
            "lambda:CreateFunction",
            "lambda:DeleteFunction",
            "ecr:SetRepositoryPolicy",
        }
        & names
    )
    s = statement(
        "operator-backend-release-completion", "InvokeOnlyPrivateMigrationRunner"
    )
    assert (
        s["Resource"] == f"arn:aws:lambda:{REGION}:{ACCOUNT}:function:peach-migrations"
    )
    s = statement(
        "operator-backend-release-completion", "PassOnlyExistingExecutionRole"
    )
    assert (
        s["Resource"]
        == f"arn:aws:iam::{ACCOUNT}:role/peach-backend-ExecutionRole-PWplj0iyaN28"
    )
    assert s["Condition"] == {
        "StringEquals": {"iam:PassedToService": "lambda.amazonaws.com"}
    }


def test_reporting_recovery_policy_is_scoped_and_does_not_mutate_production():
    assert actions("deployment-recovery") == {
        "ec2:CreateVpcEndpoint",
        "ec2:CreateTags",
        "logs:TagResource",
        "scheduler:DeleteSchedule",
        "cloudformation:DeleteStack",
    }
    endpoint = statement(
        "deployment-recovery", "CreateS3EndpointWithoutImplicitRequestTags"
    )
    assert endpoint["Condition"] == {
        "StringEquals": {"ec2:VpceServiceName": "com.amazonaws.us-east-1.s3"}
    }
    assert statement("deployment-recovery", "DeleteOnlyFailedReportingStack")[
        "Resource"
    ] == (f"arn:aws:cloudformation:{REGION}:{ACCOUNT}:stack/peach-reports/*")
    assert statement("deployment-recovery", "DeleteSchedulesOnlyInReportingGroup")[
        "Resource"
    ] == (f"arn:aws:scheduler:{REGION}:{ACCOUNT}:schedule/peach-reports/*")


def test_final_evidence_addition_is_read_only_and_scope_limited():
    assert actions("operator-final-evidence") == {"s3:GetObject", "dynamodb:GetItem"}
    assert statement("operator-final-evidence", "ReadOnlyScopedReportCSVs")[
        "Resource"
    ] == (
        f"arn:aws:s3:::peach-reports-{ACCOUNT}-{REGION}/reports/__REPORT_SCOPE_ID__/*.csv"
    )
    assert statement("operator-final-evidence", "VerifyReportDeliveryState")[
        "Resource"
    ] == (f"arn:aws:dynamodb:{REGION}:{ACCOUNT}:table/peach-report-mail-state")
