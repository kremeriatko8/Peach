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


class Loader(yaml.SafeLoader):
    pass


Loader.add_multi_constructor(
    "!",
    lambda loader, tag, node: (
        loader.construct_scalar(node)
        if isinstance(node, yaml.ScalarNode)
        else loader.construct_sequence(node)
        if isinstance(node, yaml.SequenceNode)
        else loader.construct_mapping(node)
    ),
)


@pytest.mark.parametrize(
    "filename,count", [("auth.yaml", 5), ("reports.yaml", 20), ("ai.yml", 6)]
)
def test_all_original_resources_retained_and_accounted_for(filename, count):
    template = yaml.load((ROOT / "infra" / filename).read_text(), Loader=Loader)
    resources = template["Resources"]
    assert len(resources) == count
    assert all(
        r["DeletionPolicy"] == r["UpdateReplacePolicy"] == "Retain"
        for r in resources.values()
    )
    stack = filename.split(".")[0]
    mapped = {
        r["logical_id"].split(".")[0]
        for r in inventory()["resources"]
        if r["stack"] == stack
    }
    assert mapped == set(resources)


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


def reviewed_inventory():
    result = inventory()
    for i, row in enumerate(result["resources"]):
        row["import_id"] = f"test-only-id-{i}"
    return result


def test_import_renderer_refuses_unfilled_ids_and_unknown_addresses():
    renderer = module("terraform-imports")
    with pytest.raises(ValueError):
        renderer.render(inventory())
    complete = reviewed_inventory()
    assert renderer.render(complete).count("\nimport {") == 41
    for mutate in (
        lambda r: r.pop(),
        lambda r: r.append(copy.deepcopy(r[0])),
        lambda r: r[0].update(terraform_address="aws_s3_bucket.unreviewed"),
        lambda r: r[0].update(import_id='${file("/private/test-only")}'),
        lambda r: r[0].update(strategy="recreate"),
    ):
        invalid = copy.deepcopy(complete)
        mutate(invalid["resources"])
        with pytest.raises(ValueError):
            renderer.render(invalid)


def test_only_verified_absent_google_can_be_omitted():
    renderer = module("terraform-imports")
    complete = reviewed_inventory()
    row = next(
        r for r in complete["resources"] if "google[0]" in r["terraform_address"]
    )
    row.update(strategy="absent", import_id=None)
    with pytest.raises(ValueError):
        renderer.render(complete)
    row["absence_verified"] = True
    assert renderer.render(complete).count("\nimport {") == 40
    complete["resources"][0].update(strategy="absent", absence_verified=True)
    with pytest.raises(ValueError):
        renderer.render(complete)


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


def test_output_helper_requires_cutover_and_redacts_failures(monkeypatch):
    helper = module("infra-outputs")
    monkeypatch.delenv("PEACH_INFRA_SOURCE", raising=False)
    monkeypatch.setattr(
        helper.subprocess, "run", lambda *a, **k: pytest.fail("Service called")
    )
    with pytest.raises(ValueError):
        helper.read_outputs("auth")
    monkeypatch.setenv("PEACH_INFRA_SOURCE", "terraform")
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
    monkeypatch.setenv("PEACH_INFRA_SOURCE", "terraform")
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


def test_retired_deploy_and_unapproved_plan_paths_never_call_cloud(tmp_path):
    fake = tmp_path / "aws"
    fake.write_text("#!/bin/sh\nexit 93\n")
    fake.chmod(0o755)
    env = {**os.environ, "PATH": f"{tmp_path}:/usr/bin:/bin"}
    env.pop("PEACH_APPROVE_INFRA_PLAN", None)
    for name in ("deploy-auth.sh", "deploy-ai.sh", "terraform-plan.sh"):
        result = subprocess.run(
            ["/bin/bash", str(ROOT / "scripts" / name)],
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )
        assert result.returncode == 1
        assert "HCP" in result.stderr


def test_report_now_terraform_path_never_looks_up_old_stack(monkeypatch):
    runner = module("report-now")
    monkeypatch.setenv("PROJECT_NAME", "peach")
    monkeypatch.setenv("PEACH_INFRA_SOURCE", "terraform")
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
    monkeypatch.setenv("PEACH_INFRA_SOURCE", "terraform")
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


def test_import_renderer_rejects_duplicate_physical_resources():
    complete = reviewed_inventory()
    queues = [
        r
        for r in complete["resources"]
        if r["terraform_address"].startswith("aws_sqs_queue.")
    ]
    queues[1]["import_id"] = queues[0]["import_id"]
    with pytest.raises(ValueError):
        module("terraform-imports").render(complete)


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


def test_active_imports_match_all_recorded_ids_and_configuration():
    renderer = module("terraform-imports")
    assert renderer.check_file(live_inventory(), ROOT / "infra/imports.tf") == 41
    assert len(renderer.audit(live_inventory())) == 41
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


@pytest.mark.parametrize(
    "mutation",
    [
        "wrong_id",
        "wrong_account",
        "wrong_region",
        "wrong_mapping",
        "missing",
        "duplicate",
    ],
)
def test_live_import_audit_rejects_inventory_corruption(mutation):
    value = live_inventory()
    if mutation == "wrong_id":
        value["resources"][0]["import_id"] = "test-only-wrong-id"
    elif mutation == "wrong_account":
        value["account_id"] = "123456789012"
    elif mutation == "wrong_region":
        value["region"] = "eu-west-1"
    elif mutation == "wrong_mapping":
        value["resources"][0]["logical_id"] = "UnrecordedResource"
    elif mutation == "missing":
        value["resources"].pop()
    else:
        value["resources"].append(copy.deepcopy(value["resources"][0]))
    with pytest.raises(ValueError):
        module("terraform-imports").audit(value)


def test_import_file_check_rejects_missing_duplicate_or_wrong_blocks(tmp_path):
    renderer = module("terraform-imports")
    text = renderer.render(live_inventory())
    path = tmp_path / "imports.tf"
    actual = renderer.parse_imports(text)
    address, identifier = next(iter(actual.items()))
    block = f"import {{\n to = {address}\n id = {json.dumps(identifier)}\n}}"
    for invalid in (
        "",
        text + "\n" + block,
        text.replace(identifier, "test-only-wrong-id", 1),
        text + '\nresource "aws_s3_bucket" "extra" {}',
    ):
        path.write_text(invalid)
        with pytest.raises(ValueError):
            renderer.check_file(live_inventory(), path)


def test_mock_runner_validates_imports_before_excluding_only_temporary_copy():
    script = (ROOT / "scripts/terraform-check.sh").read_text()
    assert script.index("--check") < script.index(" init -backend=false")
    assert (
        script.index(" validate")
        < script.index('mv "${WORK}/imports.tf"')
        < script.index(" test -test-directory=tests")
    )
    assert 'mv "${ROOT}/infra/imports.tf"' not in script
    assert "AWS_SHARED_CREDENTIALS_FILE=/dev/null" in script


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
    assert (
        module("terraform-imports").check_file(
            live_inventory(), ROOT / "infra/imports.tf"
        )
        == 41
    )


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
