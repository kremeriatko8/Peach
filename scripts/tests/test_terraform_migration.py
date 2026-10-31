"""Offline migration tests. Plans/replies are synthetic; recorded IDs are fixtures."""

import copy
import importlib.util
import json
import os
import re
import subprocess
from pathlib import Path
from types import SimpleNamespace

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


def module(name):
    spec = importlib.util.spec_from_file_location(
        name.replace("-", "_"), ROOT / "scripts" / f"{name}.py"
    )
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def inventory():
    return json.loads((ROOT / "docs/terraform-migration-inventory.json").read_text())


def test_inventory_exactly_covers_protected_terraform_resources():
    text = "\n".join(p.read_text() for p in (ROOT / "infra").glob("*.tf"))
    addresses = {
        f"{kind}.{name}"
        for kind, name in re.findall(r'resource "([^"]+)" "([^"]+)"', text)
    }
    expected = {
        r["terraform_address"].replace("[0]", "") for r in inventory()["resources"]
    }
    assert len(expected) == 41
    assert addresses == expected
    assert text.count("prevent_destroy = true") == len(expected)
    assert text.count("condition     = var.adoption_inventory_complete") == len(
        expected
    )
    assert not re.search(r"ignore_changes\s*=", text)
    assert all(
        r["import_id"] is None and r["strategy"] == "import"
        for r in inventory()["resources"]
    )


def synthetic_plan(importing=True):
    return {
        "complete": True,
        "errored": False,
        "resource_changes": [
            {
                "address": r["terraform_address"],
                "mode": "managed",
                "change": {
                    "actions": ["no-op"],
                    **({"importing": {"id": r["import_id"]}} if importing else {}),
                },
            }
            for r in live_inventory()["resources"]
        ],
    }


def test_import_only_and_clean_plan_guards():
    guard = module("terraform-review-plan")
    assert guard.review(synthetic_plan(), "adopt") == 41
    assert guard.review(synthetic_plan(False), "clean") == 0
    with pytest.raises(ValueError):
        guard.review(synthetic_plan(), "clean")
    with pytest.raises(ValueError):
        guard.review(synthetic_plan(False), "adopt")


@pytest.mark.parametrize(
    "actions",
    [["create"], ["update"], ["delete"], ["delete", "create"], ["create", "delete"]],
)
def test_plan_guard_rejects_every_mutation(actions):
    plan = synthetic_plan()
    plan["resource_changes"][0]["change"]["actions"] = actions
    with pytest.raises(ValueError):
        module("terraform-review-plan").review(plan, "adopt")


@pytest.mark.parametrize(
    "change",
    [
        "missing",
        "duplicate",
        "unknown",
        "failed_check",
        "deferred",
        "incomplete",
        "errored",
    ],
)
def test_plan_guard_fails_closed(change):
    plan = synthetic_plan()
    if change == "missing":
        plan["resource_changes"].pop()
    elif change == "duplicate":
        plan["resource_changes"].append(plan["resource_changes"][0])
    elif change == "unknown":
        plan["resource_changes"][0]["address"] = "aws_s3_bucket.unreviewed"
    elif change == "failed_check":
        plan["checks"] = [{"status": "unknown"}]
    elif change == "deferred":
        plan["deferred_changes"] = [{"reason": "test-only"}]
    elif change == "incomplete":
        plan["complete"] = False
    else:
        plan["errored"] = True
    with pytest.raises(ValueError):
        module("terraform-review-plan").review(plan, "adopt")


def test_output_helper_redacts_failures(monkeypatch):
    helper = module("infra-outputs")
    monkeypatch.setattr(
        helper.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=1, stderr="private-test-secret"),
    )
    with pytest.raises(ValueError) as error:
        helper.read_outputs("auth")
    assert "private-test-secret" not in str(error.value)


def test_only_named_allowlisted_outputs_are_read(monkeypatch):
    helper = module("infra-outputs")
    contract = json.loads((ROOT / "docs/terraform-output-contract.json").read_text())
    values = {key: "test-only-public-value" for key in contract["auth"]}
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout=json.dumps(values))

    monkeypatch.setattr(helper.subprocess, "run", run)
    assert helper.read_outputs("auth") == values
    assert calls[0][-3:] == ["output", "-json", "auth_outputs"]
    values["DatabaseUrl"] = "test-only-secret"
    with pytest.raises(ValueError):
        helper.read_outputs("auth")


def test_unapproved_plan_path_never_calls_cloud(tmp_path):
    fake = tmp_path / "aws"
    fake.write_text("#!/bin/sh\nexit 93\n")
    fake.chmod(0o755)
    env = {**os.environ, "PATH": f"{tmp_path}:/usr/bin:/bin"}
    env.pop("PEACH_APPROVE_INFRA_PLAN", None)
    result = subprocess.run(
        ["/bin/bash", str(ROOT / "scripts/terraform-plan.sh")],
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 1
    assert "HCP" in result.stderr


def test_report_now_reads_queue_from_terraform_not_old_stack(monkeypatch):
    runner = module("report-now")
    monkeypatch.setenv("PROJECT_NAME", "peach")
    monkeypatch.delenv("REPORT_QUEUE_URL", raising=False)
    monkeypatch.setattr("sys.argv", ["report-now.py", "--week", "2026-W40"])
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        if command[0] != "aws":
            assert command[-1] == "reports"
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "WorkQueueUrl": "https://sqs.us-east-1.amazonaws.com/123456789012/peach-report-work"
                    }
                ),
            )
        assert command[1:3] == ["sqs", "send-message"]
        return SimpleNamespace(returncode=0, stdout='{"MessageId":"test-only"}')

    monkeypatch.setattr(runner.subprocess, "run", run)
    runner.main()
    assert len(calls) == 2


def test_report_now_does_not_fallback_on_terraform_output_failure(monkeypatch):
    runner = module("report-now")
    monkeypatch.delenv("REPORT_QUEUE_URL", raising=False)
    monkeypatch.setattr("sys.argv", ["report-now.py", "--week", "2026-W40"])
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        assert command[0] != "aws"
        return SimpleNamespace(returncode=1)

    monkeypatch.setattr(runner.subprocess, "run", run)
    with pytest.raises(ValueError):
        runner.main()
    assert len(calls) == 1


def test_clean_guard_rejects_output_changes_and_handles_absent_google():
    guard = module("terraform-review-plan")
    plan = synthetic_plan(False)
    plan["output_changes"] = {"parser_url": {"actions": ["update"]}}
    with pytest.raises(ValueError):
        guard.review(plan, "clean")
    plan = synthetic_plan()
    plan["resource_changes"] = [
        r for r in plan["resource_changes"] if "google[0]" not in r["address"]
    ]
    assert guard.review(plan, "adopt", google_enabled=False) == 40


def live_inventory():
    return json.loads((ROOT / "docs/terraform-live-import-inventory.json").read_text())


def test_adoption_gate_on_with_fail_safe_default():
    assert re.search(
        r"(?m)^adoption_inventory_complete\s*=\s*true$",
        (ROOT / "infra/terraform.tfvars").read_text(),
    )
    assert re.search(
        r"default\s*=\s*false",
        (ROOT / "infra/variables.tf")
        .read_text()
        .split('variable "adoption_inventory_complete"')[1]
        .split("variable ")[0],
    )


def test_post_adoption_cleanup_removed_imports_and_cloudformation_paths():
    for gone in (
        "infra/imports.tf",
        "infra/generated.tf",
        "infra/auth.yaml",
        "infra/reports.yaml",
        "infra/ai.yml",
        "scripts/deploy-auth.sh",
        "scripts/deploy-ai.sh",
        "scripts/terraform-imports.py",
    ):
        assert not (ROOT / gone).exists(), gone
    hcl = "\n".join(p.read_text() for p in (ROOT / "infra").glob("*.tf"))
    assert not re.search(r"(?m)^import\s*\{", hcl)
    checked = [ROOT / "Makefile", *(ROOT / ".github/workflows").glob("*.yml")]
    checked += [*(ROOT / "scripts").glob("*.sh"), *(ROOT / "scripts").glob("*.py")]
    for path in checked:
        lines = path.read_text().splitlines()
        text = "\n".join(line for line in lines if not line.lstrip().startswith("#"))
        assert "PEACH_INFRA_SOURCE" not in text, path
        assert not re.search(r"terraform\s+apply", text), path
        for stack in ("-auth", "-reports", "-ai"):
            assert not re.search(
                rf"cloudformation (deploy|create-change-set).*{stack}\b", text
            ), path
    makefile = (ROOT / "Makefile").read_text()
    for target in ("deploy-auth:", "ai-prepare-deploy:", "reports-prepare:"):
        assert target not in makefile
    assert "infra-plan:" in makefile


def test_check_script_isolates_credentials_before_validation():
    script = (ROOT / "scripts/terraform-check.sh").read_text()
    assert (
        script.index("AWS_SHARED_CREDENTIALS_FILE=/dev/null")
        < script.index(" init -backend=false")
        < script.index(" validate")
        < script.index(" test -test-directory=tests")
    )


def test_publication_checks_cannot_run_application_deploy():
    workflow = yaml.safe_load(
        (ROOT / ".github/workflows/terraform-check.yml").read_text()
    )
    triggers = workflow.get("on", workflow.get(True))
    assert set(triggers) == {"pull_request", "workflow_dispatch"}
    assert workflow["permissions"] == {"contents": "read"}
    text = (ROOT / ".github/workflows/terraform-check.yml").read_text()
    assert "configure-aws-credentials" not in text
    assert "id-token:" not in text
    assert "terraform apply" not in text and "terraform import" not in text
    deploy = yaml.safe_load((ROOT / ".github/workflows/deploy-backend.yml").read_text())
    deploy_triggers = deploy.get("on", deploy.get(True))
    assert deploy_triggers["push"]["branches"] == ["main"]
    assert "pull_request" not in deploy_triggers


def test_plan_guard_rejects_unreviewed_physical_import_id():
    value = synthetic_plan()
    value["resource_changes"][0]["change"]["importing"]["id"] = "test-only-wrong-object"
    with pytest.raises(ValueError):
        module("terraform-review-plan").review(value, "adopt")


def test_confirmed_workspace_binding_cannot_be_redirected_by_environment():
    versions = (ROOT / "infra/versions.tf").read_text()
    assert 'organization = "ooad-kremeriatko8"' in versions
    assert 'name = "peach-dev"' in versions
    assert "cloud {}" not in versions


def test_imported_public_client_does_not_configure_create_only_secret_flag():
    evidence = json.loads(
        (ROOT / "docs/terraform-preview-remediation-evidence.json").read_text()
    )
    replacement = evidence["replacement"]
    assert replacement["replace_paths"] == [["generate_secret"]]
    assert replacement["imported_value"] is None
    assert replacement["live_client_has_secret"] is False
    client = (
        (ROOT / "infra/auth.tf")
        .read_text()
        .split('resource "aws_cognito_user_pool_client" "frontend" {')[1]
        .split('resource "')[0]
    )
    assert not re.search(r"(?m)^\s*generate_secret\s*=", client)
    assert "prevent_destroy = true" in client
    assert "ignore_changes" not in client


def test_preview_permission_supplement_is_minimal_and_region_scoped():
    policy = json.loads(
        (ROOT / "docs/terraform-preview-read-permissions.json").read_text()
    )
    statements = policy["Statement"]
    assert len(statements) == 3
    assert {s["Action"] for s in statements} == {
        "lambda:ListVersionsByFunction",
        "ec2:DescribePrefixLists",
        "cognito-idp:ListUserPoolClients",
    }
    for statement in statements:
        assert statement["Effect"] == "Allow"
        assert statement["Condition"] == {
            "StringEquals": {"aws:RequestedRegion": "us-east-1"}
        }
        if statement["Action"].startswith("lambda:"):
            assert set(statement["Resource"]) == {
                "arn:aws:lambda:us-east-1:968053399627:function:peach-report-builder",
                "arn:aws:lambda:us-east-1:968053399627:function:peach-report-mailer",
                "arn:aws:lambda:us-east-1:968053399627:function:peach-agenda-parser",
            }
        elif statement["Action"].startswith("cognito-idp:"):
            assert statement["Resource"] == (
                "arn:aws:cognito-idp:us-east-1:968053399627:userpool/us-east-1_bs7cWxhJp"
            )
        else:
            assert statement["Resource"] == "*"


def test_failed_plan_partition_preserves_all_41_imports():
    evidence = json.loads(
        (ROOT / "docs/terraform-preview-remediation-evidence.json").read_text()
    )
    expected = {
        r["terraform_address"]: r["import_id"] for r in live_inventory()["resources"]
    }
    evaluated = set(evidence["planned_import_addresses"])
    pending = {
        r["terraform_address"]: r["import_id"]
        for r in evidence["not_evaluated_imports"]
    }
    assert len(evaluated) == 29
    assert len(pending) == 12
    assert not evaluated.intersection(pending)
    assert evaluated.union(pending) == set(expected)
    assert all(value == expected[address] for address, value in pending.items())


def sensitivity_only_fixture(importing):
    """Synthetic guard contract; this does not create or simulate live state."""
    plan = synthetic_plan(importing)
    addresses = {
        "aws_cognito_identity_provider.google[0]",
        "aws_iam_role_policy.mailer",
        "aws_lambda_function.builder",
        "aws_lambda_function.mailer",
    }
    for row in plan["resource_changes"]:
        if row["address"] in addresses:
            value = {"test_private_attribute": "synthetic-private-value"}
            row["change"].update(
                actions=["update"],
                before=copy.deepcopy(value),
                after=copy.deepcopy(value),
                before_sensitive={},
                after_sensitive={"test_private_attribute": True},
                after_unknown={},
            )
    return plan


@pytest.mark.parametrize("mode", ["adopt", "clean"])
def test_sensitivity_only_updates_do_not_bypass_strict_gate(mode):
    plan = sensitivity_only_fixture(importing=mode == "adopt")
    with pytest.raises(ValueError):
        module("terraform-review-plan").review(plan, mode)


def test_persisted_sensitivity_metadata_is_compatible_with_genuine_clean_plan():
    # This is a synthetic representation of a future observed no-op plan, not
    # evidence that adoption or a live clean plan has already occurred.
    plan = sensitivity_only_fixture(importing=False)
    for row in plan["resource_changes"]:
        change = row["change"]
        if change["actions"] == ["update"]:
            change["actions"] = ["no-op"]
            change["before_sensitive"] = copy.deepcopy(change["after_sensitive"])
    assert module("terraform-review-plan").review(plan, "clean") == 0
