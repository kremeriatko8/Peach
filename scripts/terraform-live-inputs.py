#!/usr/bin/env python3
"""Check authoritative private inputs; execute one preview only after explicit approval.

No private values are printed or written. Only read-only AWS/HCP requests are used
before the optional, guarded, remote speculative plan. No state commands or apply.
"""

import argparse
import faulthandler
import hashlib
import json
import logging
import os
import re
import resource
import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import boto3
from botocore.config import Config

ACCOUNT = "968053399627"
REGION = "us-east-1"
POOL = "us-east-1_bs7cWxhJp"
WORKSPACE_ID = "ws-WieWVM5aHAWDay38"
PRIVATE_INPUTS = {
    "google_client_secret",
    "database_url",
    "report_owner_sub",
    "report_from_email",
    "report_recipient_email",
}


def authoritative_inputs(google, builder, mailer, policy):
    """Extract exact strings and reject ambiguity rather than normalizing values."""
    statements = []
    for statement in policy["Statement"]:
        actions = statement.get("Action", [])
        actions = [actions] if isinstance(actions, str) else actions
        if any(
            action.lower().startswith("ses:") or action == "*" for action in actions
        ):
            statements.append(statement)
    if len(statements) != 1 or statements[0].get("Effect") != "Allow":
        raise ValueError("Ambiguous SES policy; operator review required")
    condition = statements[0].get("Condition", {})
    if set(condition) != {"StringEquals", "ForAllValues:StringEquals"}:
        raise ValueError("Unexpected SES condition operators")
    if set(condition["StringEquals"]) != {"ses:FromAddress"} or set(
        condition["ForAllValues:StringEquals"]
    ) != {"ses:Recipients"}:
        raise ValueError("Unexpected SES condition keys")
    sender = condition["StringEquals"]["ses:FromAddress"]
    recipients = condition["ForAllValues:StringEquals"]["ses:Recipients"]
    if (
        not isinstance(sender, str)
        or not isinstance(recipients, list)
        or len(recipients) != 1
    ):
        raise ValueError("SES conditions require exactly one sender and recipient")
    recipient = recipients[0]
    for value in (sender, recipient):
        if not isinstance(value, str) or not re.fullmatch(
            r"[^\s@<>;,?*$]+@[^\s@<>;,?*$]+", value
        ):
            raise ValueError("Unsupported SES address; no values were disclosed")
    if (
        mailer.get("REPORT_FROM_EMAIL") != sender
        or mailer.get("REPORT_RECIPIENT_EMAIL") != recipient
    ):
        raise ValueError("Mailer environment and IAM SES conditions disagree")
    values = {
        "google_client_secret": google.get("client_secret"),
        "database_url": builder.get("DATABASE_URL"),
        "report_owner_sub": builder.get("REPORT_OWNER_SUB"),
        "report_from_email": sender,
        "report_recipient_email": recipient,
    }
    if any(not isinstance(v, str) or not v or v != v.strip() for v in values.values()):
        raise ValueError(
            "Authoritative input is missing or contains surrounding whitespace"
        )
    if not values["database_url"].startswith("postgresql+asyncpg://"):
        raise ValueError("Unexpected deployed database URL scheme")
    if len(values["report_owner_sub"]) > 128:
        raise ValueError("Unexpected deployed owner identifier length")
    return values


def read_aws_inputs():
    config = Config(connect_timeout=8, read_timeout=20, retries={"max_attempts": 0})
    runtime = boto3.Session(region_name=REGION)
    policy_session = boto3.Session(
        profile_name="peach-reports-deploy", region_name=REGION
    )
    for session in (runtime, policy_session):
        if (
            session.client("sts", config=config).get_caller_identity()["Account"]
            != ACCOUNT
        ):
            raise ValueError("AWS account mismatch")
    google = runtime.client("cognito-idp", config=config).describe_identity_provider(
        UserPoolId=POOL, ProviderName="Google"
    )["IdentityProvider"]["ProviderDetails"]
    functions = policy_session.client("lambda", config=config)
    builder = functions.get_function_configuration(FunctionName="peach-report-builder")[
        "Environment"
    ]["Variables"]
    mailer = functions.get_function_configuration(FunctionName="peach-report-mailer")[
        "Environment"
    ]["Variables"]
    policy = policy_session.client("iam", config=config).get_role_policy(
        RoleName="peach-report-mailer", PolicyName="report-mailer"
    )["PolicyDocument"]
    return authoritative_inputs(google, builder, mailer, policy)


def hcp_preflight():
    token = os.environ.get("TF_TOKEN_app_terraform_io")
    if not token:
        credentials = json.loads(
            (Path.home() / ".terraform.d/credentials.tfrc.json").read_text()
        )
        token = credentials["credentials"]["app.terraform.io"]["token"]

    def get(path):
        request = urllib.request.Request(
            "https://app.terraform.io/api/v2/" + path,
            headers={
                "Authorization": "Bearer " + token,
                "Content-Type": "application/vnd.api+json",
            },
        )
        with urllib.request.urlopen(request, timeout=25) as response:
            return json.load(response)

    workspace = get("organizations/ooad-kremeriatko8/workspaces/peach-dev")["data"]
    attributes = workspace["attributes"]
    if (
        workspace["id"] != WORKSPACE_ID
        or attributes["execution-mode"] != "remote"
        or attributes["auto-apply"]
        or attributes["vcs-repo"]["identifier"] != "kremeriatko8/Peach"
        or workspace.get("relationships", {})
        .get("current-state-version", {})
        .get("data")
        is not None
    ):
        raise ValueError("HCP workspace safety settings mismatch")
    # Priority variable sets can outrank run-specific TF_VAR inputs. Stop rather
    # than assuming overrides win. Existing org currently has no variable sets.
    sets = get("organizations/ooad-kremeriatko8/varsets?page%5Bsize%5D=100")
    if sets["data"] or sets.get("links", {}).get("next"):
        raise ValueError("Variable sets require a fresh precedence review")
    variables = get("workspaces/" + WORKSPACE_ID + "/vars")["data"]
    environment = {
        row["attributes"]["key"]: row["attributes"].get("value")
        for row in variables
        if row["attributes"]["category"] == "env"
    }
    if (
        environment.get("TFC_AWS_PROVIDER_AUTH") != "true"
        or environment.get("TFC_AWS_RUN_ROLE_ARN")
        != "arn:aws:iam::968053399627:role/peach-hcp-terraform-read"
    ):
        raise ValueError("HCP OIDC environment mismatch")
    return token


def checked_archive(manifest_path):
    manifest = json.loads(manifest_path.read_text())
    root = Path(manifest["directory"])
    if manifest["base_commit"] != "7e2fcf32373c611f7a3e9f5be0479a38a0d1cd7c":
        raise ValueError("Unexpected preview base")
    if {str(p.relative_to(root)) for p in root.rglob("*") if p.is_file()} != set(
        manifest["files"]
    ):
        raise ValueError("Unexpected upload files")
    for name, digest in manifest["files"].items():
        path = root / name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest() != digest:
            raise ValueError("Preview archive integrity failed")
    infra = root / "infra"
    auth = (infra / "auth.tf").read_text()
    all_source = "\n".join(p.read_text() for p in infra.glob("*.tf"))
    if len(re.findall(r"prevent_destroy\s*=\s*true", all_source)) != 41:
        raise ValueError("Expected 41 lifecycle protections")
    if (
        re.search(r"(?m)^\s*generate_secret\s*=", auth)
        or "prevent_destroy = true" not in auth
    ):
        raise ValueError("Cognito preservation settings mismatch")
    if not re.search(
        r"adoption_inventory_complete\s*=\s*false",
        (infra / "terraform.tfvars").read_text(),
    ):
        raise ValueError("Source adoption gate must remain false")
    if len(re.findall(r"(?m)^import\s*\{", (infra / "imports.tf").read_text())) != 41:
        raise ValueError("Expected 41 imports")
    return infra


def preview_command(terraform, infra):
    return [
        str(terraform),
        "-chdir=" + str(infra),
        "plan",
        "-input=false",
        "-var-file=terraform.tfvars",
        "-var=adoption_inventory_complete=true",
    ]


def preview_environment(values, token, data_dir, ambient):
    if set(values) != PRIVATE_INPUTS:
        raise ValueError("Unexpected private input set")
    environment = {
        k: v
        for k, v in ambient.items()
        if not k.startswith(("TF_CLI_ARGS", "TF_VAR_", "TF_CLOUD_", "TF_LOG", "AWS_"))
        and k
        not in {
            "TF_CLI_CONFIG_FILE",
            "TF_WORKSPACE",
            "TF_DATA_DIR",
            "TF_LOG",
            "TF_LOG_PATH",
        }
    }
    environment.update({"TF_VAR_" + key: value for key, value in values.items()})
    environment.update(
        TF_TOKEN_app_terraform_io=token,
        TF_DATA_DIR=str(data_dir),
        CHECKPOINT_DISABLE="1",
        TF_IN_AUTOMATION="1",
    )
    return environment


SANDBOX_PROFILE = '(version 1)(allow default)(deny file-write*)(allow file-write-data (literal "/dev/null"))'
SAFE_STATUSES = {
    "planned_and_finished",
    "errored",
    "canceled",
    "discarded",
    "planned",
    "blocked",
    "preflight-passed",
    "local-process-failed",
    "result-unavailable",
}


SAFE_CATEGORIES = {
    "oidc-authentication",
    "iam-read-denied",
    "process-crash",
    "lifecycle-protection",
    "input-validation",
    "import-diagnostic",
    "plan-diagnostic",
    "inventory-mismatch",
    "import-id-mismatch",
    "incomplete-inventory",
    "unresolved-checks",
    "incomplete-plan",
    "run-status-unavailable",
    "acceptance-criteria-not-met",
    "run-not-terminal",
    "run-url-unavailable",
    "local-process-crash",
    "preflight-or-result-security-check",
    "sensitivity-metadata-updates",
}


def emit(result):
    """Schema allowlist: no arbitrary string, key, nested object or exception."""
    safe = {
        "status": result.get("status")
        if result.get("status") in SAFE_STATUSES
        else "blocked"
    }
    url = result.get("run_url")
    if isinstance(url, str) and re.fullmatch(
        r"https://app\.terraform\.io/app/ooad-kremeriatko8/peach-dev/runs/run-[A-Za-z0-9]{16}",
        url,
    ):
        safe["run_url"] = url
    for key in [
        "imports",
        "additions",
        "updates",
        "replacements",
        "destructions",
        "previous_updates_remaining",
    ]:
        value = result.get(key)
        if type(value) is int and 0 <= value <= (
            4 if key == "previous_updates_remaining" else 41
        ):
            safe[key] = value
    for key in ["blockers", "warnings"]:
        if key in result:
            safe[key] = sorted(
                {
                    v
                    if isinstance(v, str) and v in SAFE_CATEGORIES
                    else "plan-diagnostic"
                    for v in result[key]
                }
            )
    print(json.dumps(safe, sort_keys=True), flush=True)


def get_hcp(token, path, raw=False):
    request = urllib.request.Request(
        "https://app.terraform.io/api/v2/" + path,
        headers={
            "Authorization": "Bearer " + token,
            "Content-Type": "application/vnd.api+json",
        },
    )
    with urllib.request.urlopen(request, timeout=30) as response:
        body = response.read()
    return body if raw else json.loads(body)


def diagnostic_category(text):
    """No substring of untrusted diagnostic text is ever returned."""
    text = text.lower()
    if any(
        s in text for s in ["assumerolewithwebidentity", "invalididentitytoken", "oidc"]
    ):
        return "oidc-authentication"
    if any(
        s in text for s in ["accessdenied", "not authorized", "unauthorizedoperation"]
    ):
        return "iam-read-denied"
    if any(
        s in text
        for s in ["panic:", "fatal error:", "plugin crashed", "terraform crashed"]
    ):
        return "process-crash"
    if "prevent_destroy" in text or "cannot be destroyed" in text:
        return "lifecycle-protection"
    if "variable" in text or "input" in text:
        return "input-validation"
    if "import" in text:
        return "import-diagnostic"
    return "plan-diagnostic"


def summarize_changes(plan, expected):
    rows = [r for r in plan.get("resource_changes", []) if r.get("mode") != "data"]
    counts = {
        "imports": 0,
        "additions": 0,
        "updates": 0,
        "replacements": 0,
        "destructions": 0,
    }
    blockers = set()
    seen = set()
    previous = {
        "aws_cognito_identity_provider.google[0]",
        "aws_iam_role_policy.mailer",
        "aws_lambda_function.builder",
        "aws_lambda_function.mailer",
    }
    remaining_previous = 0
    for row in rows:
        address = row["address"]
        if address not in expected or address in seen:
            blockers.add("inventory-mismatch")
        seen.add(address)
        change = row["change"]
        actions = change["actions"]
        if actions not in [
            ["no-op"],
            ["update"],
            ["create"],
            ["delete"],
            ["create", "delete"],
            ["delete", "create"],
        ]:
            blockers.add("unexpected-action")
        counts["additions"] += int("create" in actions)
        counts["updates"] += int("update" in actions)
        counts["destructions"] += int("delete" in actions)
        counts["replacements"] += int("create" in actions and "delete" in actions)
        if change.get("importing"):
            counts["imports"] += 1
            if change["importing"].get("id") != expected.get(address):
                blockers.add("import-id-mismatch")
        remaining_previous += int(address in previous and actions != ["no-op"])
    if seen != set(expected):
        blockers.add("incomplete-inventory")
    # Full JSON can prove equal values with changed marks. Redacted placeholders
    # cannot support this classification. Keep Update actions and strict rejection.
    updates = [r["change"] for r in rows if r["change"]["actions"] == ["update"]]
    if (
        plan.get("format_version")
        and updates
        and all(
            c.get("before") == c.get("after")
            and c.get("before_sensitive") != c.get("after_sensitive")
            and not c.get("after_unknown")
            for c in updates
        )
    ):
        blockers.add("sensitivity-metadata-updates")
    if plan.get("deferred_changes") or any(
        c.get("status") != "pass" for c in plan.get("checks", [])
    ):
        blockers.add("unresolved-checks")
    if plan.get("errored") or plan.get("complete") is False:
        blockers.add("incomplete-plan")
    if any(v < 0 or v > 41 for v in counts.values()):
        raise ValueError("Invalid count")
    return counts, blockers, remaining_previous


def collect_result(token, run_id, expected):
    if not re.fullmatch(r"run-[A-Za-z0-9]{16}", run_id):
        raise ValueError("Invalid run identifier")
    run = get_hcp(token, "runs/" + run_id)["data"]
    if (
        run["relationships"]["workspace"]["data"]["id"] != WORKSPACE_ID
        or run["attributes"].get("plan-only") is not True
    ):
        raise ValueError("Not the expected speculative run")
    status = run["attributes"]["status"]
    plan_id = run["relationships"]["plan"]["data"]["id"]
    if not re.fullmatch(r"plan-[A-Za-z0-9]{16}", plan_id):
        raise ValueError("Invalid plan identifier")
    metadata = get_hcp(token, "plans/" + plan_id)["data"]["attributes"]
    if metadata["status"] not in {"finished", "errored", "canceled"}:
        return {
            "run_url": "https://app.terraform.io/app/ooad-kremeriatko8/peach-dev/runs/"
            + run_id,
            "status": "result-unavailable",
            "blockers": ["run-not-terminal"],
        }
    # Full or redacted plan JSON is parsed only in memory. Never save responses.
    plan = None
    for suffix in ["json-output", "json-output-redacted"]:
        body = get_hcp(token, "plans/" + plan_id + "/" + suffix, raw=True)
        if body:
            plan = json.loads(body)
            break
    if plan is None:
        raise ValueError("No reliable plan JSON")
    counts, blockers, previous = summarize_changes(plan, expected)
    warnings = set()
    # Log URLs are signed credentials. Never print or persist them or their body.
    url = metadata.get("log-read-url", "")
    if not url.startswith("https://archivist.terraform.io/"):
        raise ValueError("Unexpected diagnostic URL")
    with urllib.request.urlopen(url, timeout=30) as response:
        logs = response.read().decode("utf-8", errors="replace")
    for line in logs.splitlines():
        try:
            event = json.loads(line)
        except ValueError:
            continue
        if event.get("type") == "diagnostic":
            d = event["diagnostic"]
            category = diagnostic_category(
                str(d.get("summary", "")) + " " + str(d.get("detail", ""))
            )
            (warnings if d.get("severity") == "warning" else blockers).add(category)
    if status not in SAFE_STATUSES:
        status = "result-unavailable"
        blockers.add("run-status-unavailable")
    if counts["imports"] != 41 or any(
        counts[k] for k in ["additions", "updates", "replacements", "destructions"]
    ):
        blockers.add("acceptance-criteria-not-met")
    return {
        "run_url": "https://app.terraform.io/app/ooad-kremeriatko8/peach-dev/runs/"
        + run_id,
        "status": status,
        **counts,
        "blockers": sorted(blockers),
        "warnings": sorted(warnings),
        "previous_updates_remaining": previous,
    }


def capture_process(command, environment):
    """Capture both file descriptors privately; never include exception objects."""
    try:
        process = subprocess.run(
            command,
            env=environment,
            capture_output=True,
            stdin=subprocess.DEVNULL,
            check=False,
            close_fds=True,
        )
        return process.returncode, process.stdout or b"", process.stderr or b""
    except BaseException:  # noqa: BLE001 - exception strings may contain secrets
        return -1, b"", b""


def require_write_denial():
    """Fail closed unless this process is already OS-restricted before secrets."""
    if sys.platform != "darwin" or not Path("/usr/bin/sandbox-exec").is_file():
        raise ValueError("Required OS write-denial sandbox unavailable")
    resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
    probe = Path(
        "/private/tmp/peach-write-denial-probe-"
        + str(os.getpid())
        + "-"
        + str(time.monotonic_ns())
    )
    try:
        fd = os.open(probe, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except PermissionError:
        return
    else:
        os.close(fd)
        probe.unlink()
        raise ValueError("Launch the entire helper in the required OS sandbox")


def local_security_checks(terraform, infra, environment):
    require_write_denial()
    # Descendants inherit the already-tested OS policy; nesting sandbox-exec is
    # unnecessary and is rejected on macOS. This synthetic child confirms the
    # inherited core limit and file denial. No secret-bearing argv or files.
    probe = "/private/tmp/peach-child-write-denial-probe-" + str(os.getpid())
    code = (
        "import resource; assert resource.getrlimit(resource.RLIMIT_CORE)[0]==0; open("
        + repr(probe)
        + ",'w').write('public-probe')"
    )
    result, _, _ = capture_process(
        [sys.executable, "-c", code], {"PATH": "/usr/bin:/bin"}
    )
    if result == 0 or Path(probe).exists():
        raise ValueError("Inherited file-write denial failed")
    # Version and configuration discovery are read-only, not plan attempts.
    result, stdout, _ = capture_process(
        [str(terraform), "version", "-json"],
        {"PATH": "/usr/bin:/bin", "CHECKPOINT_DISABLE": "1"},
    )
    if result != 0 or json.loads(stdout)["terraform_version"] != "1.13.5":
        raise ValueError("Pinned Terraform unavailable under sandbox")
    result, _, _ = capture_process(
        [str(terraform), "-chdir=" + str(infra), "providers"],
        environment,
    )
    if result != 0:
        raise ValueError("Read-only configuration check failed under sandbox")


def execute_preview(terraform, infra, environment, token, expected):
    local_security_checks(terraform, infra, environment)
    # The child and descendants cannot write files at all: no debug/crash logs,
    # core dumps, saved plans or private temp files. The pinned upload packs into
    # a bytes.Buffer, so even its public config archive needs no disk staging.
    command = preview_command(terraform, infra)
    code, stdout, stderr = capture_process(command, environment)
    urls = re.findall(
        rb"https://app\.terraform\.io/app/ooad-kremeriatko8/peach-dev/runs/(run-[A-Za-z0-9]{16})(?![A-Za-z0-9])",
        stdout + b"\n" + stderr,
    )
    if len(set(urls)) != 1:
        return {
            "status": "local-process-failed",
            "blockers": ["run-url-unavailable" if code >= 0 else "local-process-crash"],
        }
    run_id = urls[0].decode("ascii")
    # No retry of the subprocess. API reads may observe a still-finishing run.
    for _ in range(5):
        result = collect_result(token, run_id, expected)
        if "run-not-terminal" not in result.get("blockers", []):
            return result
        time.sleep(2)
    return result


class QuietArgumentParser(argparse.ArgumentParser):
    def error(self, message):
        # argparse normally echoes unknown arguments, which may contain secrets.
        raise ValueError("Invalid helper arguments")


def main():
    parser = QuietArgumentParser(description=__doc__, add_help=False)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--execute-preview", action="store_true")
    parser.add_argument("--terraform", type=Path)
    parser.add_argument("--data-dir", type=Path)
    args = parser.parse_args()
    if args.execute_preview and (
        os.environ.get("PEACH_APPROVE_INFRA_PLAN") != "yes"
        or args.terraform is None
        or args.data_dir is None
    ):
        raise ValueError("Explicit approval and initialized paths required")
    if args.execute_preview:
        require_write_denial()
    infra = checked_archive(args.manifest)
    token = hcp_preflight()
    values = read_aws_inputs()
    if not args.execute_preview:
        emit({"status": "preflight-passed"})
        return 0
    expected = {
        r["terraform_address"]: r["import_id"]
        for r in json.loads(
            (
                Path(__file__).resolve().parents[1]
                / "docs/terraform-live-import-inventory.json"
            ).read_text()
        )["resources"]
    }
    environment = preview_environment(values, token, args.data_dir, os.environ)
    result = execute_preview(args.terraform, infra, environment, token, expected)
    emit(result)
    return (
        0
        if result.get("status") == "planned_and_finished" and not result.get("blockers")
        else 1
    )


def safe_entry():
    logging.disable(logging.CRITICAL)
    faulthandler.disable()
    try:
        resource.setrlimit(resource.RLIMIT_CORE, (0, 0))
        require_write_denial()
        return main()
    except BaseException:  # noqa: BLE001 - never format exceptions or tracebacks
        emit({"status": "blocked", "blockers": ["preflight-or-result-security-check"]})
        return 1


if __name__ == "__main__":
    sys.exit(safe_entry())
