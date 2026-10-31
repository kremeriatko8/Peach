"""Synthetic inputs only; never invoke AWS/HCP or Terraform planning."""

import importlib.util
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]


def helper():
    spec = importlib.util.spec_from_file_location(
        "live_inputs", ROOT / "scripts/terraform-live-inputs.py"
    )
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def fixtures():
    return (
        {"client_secret": "test-only-google-secret"},
        {
            "DATABASE_URL": "postgresql+asyncpg://test:test@localhost/test",
            "REPORT_OWNER_SUB": "test-owner",
        },
        {
            "REPORT_FROM_EMAIL": "sender@example.com",
            "REPORT_RECIPIENT_EMAIL": "recipient@example.com",
        },
        {
            "Statement": [
                {
                    "Effect": "Allow",
                    "Action": "ses:SendRawEmail",
                    "Condition": {
                        "StringEquals": {"ses:FromAddress": "sender@example.com"},
                        "ForAllValues:StringEquals": {
                            "ses:Recipients": ["recipient@example.com"]
                        },
                    },
                }
            ]
        },
    )


def test_exact_sources_and_run_environment_never_put_secrets_in_command():
    h = helper()
    values = h.authoritative_inputs(*fixtures())
    env = h.preview_environment(
        values,
        "test-token",
        Path("/tmp/test-data"),
        {
            "PATH": "/bin",
            "TF_VAR_database_url": "wrong",
            "TF_CLI_ARGS_plan": "-destroy",
            "TF_LOG_PROVIDER": "TRACE",
            "AWS_PROFILE": "wrong",
        },
    )
    assert env["TF_VAR_database_url"] == fixtures()[1]["DATABASE_URL"]
    assert not {"TF_CLI_ARGS_plan", "TF_LOG_PROVIDER", "AWS_PROFILE"}.intersection(env)
    command = h.preview_command(Path("/tmp/terraform"), Path("/tmp/infra"))
    assert command[2] == "plan"
    assert command[-1] == "-var=adoption_inventory_complete=true"
    assert not any(value in " ".join(command) for value in values.values())
    assert not any(flag.startswith(("-out", "-target", "-replace")) for flag in command)


@pytest.mark.parametrize(
    "case", ["wildcard", "multiple", "operator", "environment", "empty"]
)
def test_ambiguous_or_mismatched_sources_stop(case):
    args = fixtures()
    condition = args[3]["Statement"][0]["Condition"]
    if case == "wildcard":
        condition["ForAllValues:StringEquals"]["ses:Recipients"] = ["*@example.com"]
    elif case == "multiple":
        condition["ForAllValues:StringEquals"]["ses:Recipients"].append(
            "second@example.com"
        )
    elif case == "operator":
        condition["StringLike"] = condition.pop("StringEquals")
    elif case == "environment":
        args[2]["REPORT_FROM_EMAIL"] = "different@example.com"
    else:
        args[1]["REPORT_OWNER_SUB"] = ""
    with pytest.raises(ValueError):
        helper().authoritative_inputs(*args)


def test_default_mode_cannot_run_plan(monkeypatch, capsys):
    h = helper()
    monkeypatch.setattr(sys, "argv", ["live-inputs", "--manifest", "/tmp/fake.json"])
    monkeypatch.setattr(h, "checked_archive", lambda _: Path("/tmp/infra"))
    monkeypatch.setattr(h, "hcp_preflight", lambda: "test-token")
    monkeypatch.setattr(
        h, "read_aws_inputs", lambda: h.authoritative_inputs(*fixtures())
    )
    monkeypatch.setattr(
        h.subprocess, "run", lambda *a, **k: pytest.fail("Plan must not execute")
    )
    assert h.main() == 0
    output = capsys.readouterr().out
    assert '"status": "preflight-passed"' in output
    assert "test-only-google-secret" not in output


def test_execute_requires_explicit_approval_before_network(monkeypatch):
    h = helper()
    monkeypatch.delenv("PEACH_APPROVE_INFRA_PLAN", raising=False)
    monkeypatch.setattr(
        sys,
        "argv",
        ["live-inputs", "--manifest", "/tmp/fake.json", "--execute-preview"],
    )
    monkeypatch.setattr(
        h, "hcp_preflight", lambda: pytest.fail("No network without approval")
    )
    with pytest.raises(ValueError):
        h.main()


SECRET = "SYNTHETIC_PRIVATE_MARKER_NEVER_EMIT"
RUN_ID = "run-0123456789AbCdEf"
RUN_URL = "https://app.terraform.io/app/ooad-kremeriatko8/peach-dev/runs/" + RUN_ID


@pytest.mark.parametrize(
    "code,stdout,stderr",
    [
        (0, (SECRET + "\n" + RUN_URL).encode(), b""),
        (1, (SECRET + "\n" + RUN_URL).encode(), SECRET.encode()),
        (1, SECRET.encode(), b""),
        (11, b"", ("panic: " + SECRET).encode()),
        (-11, b"", SECRET.encode()),
        (0, ("malformed-output " + SECRET).encode(), b""),
    ],
)
def test_output_success_failure_malformed_and_crash_are_never_forwarded(
    monkeypatch, capsys, code, stdout, stderr
):
    from types import SimpleNamespace

    h = helper()
    monkeypatch.setattr(h, "local_security_checks", lambda *a: None)

    def run(command, **kwargs):
        assert kwargs["capture_output"] is True
        assert kwargs["stdin"] == h.subprocess.DEVNULL
        assert kwargs["check"] is False
        assert SECRET not in " ".join(command)
        return SimpleNamespace(returncode=code, stdout=stdout, stderr=stderr)

    monkeypatch.setattr(h.subprocess, "run", run)
    monkeypatch.setattr(
        h,
        "collect_result",
        lambda *a: {
            "run_url": RUN_URL,
            "status": "errored",
            "blockers": ["plan-diagnostic"],
        },
    )
    result = h.execute_preview(
        Path("/tmp/terraform"), Path("/tmp/infra"), {}, "test-token", {}
    )
    h.emit(result)
    captured = capsys.readouterr()
    assert SECRET not in captured.out + captured.err
    assert "panic:" not in captured.out + captured.err
    assert not captured.err


def test_exception_and_traceback_are_never_formatted(monkeypatch, capsys):
    h = helper()

    def explode(*a, **k):
        raise RuntimeError(SECRET)

    monkeypatch.setattr(h.subprocess, "run", explode)
    assert h.capture_process(["/tmp/fake"], {}) == (-1, b"", b"")
    monkeypatch.setattr(h, "require_write_denial", lambda: None)
    monkeypatch.setattr(h, "main", explode)
    assert h.safe_entry() == 1
    captured = capsys.readouterr()
    assert SECRET not in captured.out + captured.err
    assert "Traceback" not in captured.out + captured.err
    assert "preflight-or-result-security-check" in captured.out


@pytest.mark.parametrize(
    "message",
    [SECRET, "AccessDenied " + SECRET, "panic: " + SECRET, "Invalid input " + SECRET],
)
def test_diagnostic_categories_are_fixed_not_redacted_strings(message):
    category = helper().diagnostic_category(message)
    assert SECRET not in category
    assert category in {
        "plan-diagnostic",
        "iam-read-denied",
        "process-crash",
        "input-validation",
    }


def test_summary_reads_only_actions_and_ids_not_private_values():
    h = helper()
    plan = {
        "resource_changes": [
            {
                "address": "test.resource",
                "change": {
                    "actions": ["no-op"],
                    "importing": {"id": "test-id"},
                    "before": {"secret": SECRET},
                    "after": {"secret": SECRET},
                },
            }
        ],
    }
    counts, blockers, previous = h.summarize_changes(plan, {"test.resource": "test-id"})
    assert counts == {
        "imports": 1,
        "additions": 0,
        "updates": 0,
        "replacements": 0,
        "destructions": 0,
    }
    assert not blockers
    assert previous == 0
    assert SECRET not in str((counts, blockers, previous))


def test_plan_json_parse_error_is_fail_closed(monkeypatch, capsys):
    h = helper()
    monkeypatch.setattr(
        h, "main", lambda: h.summarize_changes({"resource_changes": SECRET}, {})
    )
    assert h.safe_entry() == 1
    captured = capsys.readouterr()
    assert SECRET not in captured.out + captured.err
    assert not captured.err


def test_sandbox_denies_all_file_writes_and_no_crash_logging_env():
    h = helper()
    assert "(deny file-write*)" in h.SANDBOX_PROFILE
    values = h.authoritative_inputs(*fixtures())
    env = h.preview_environment(
        values,
        "test-token",
        Path("/tmp/data"),
        {
            "TF_LOG_PATH": "/tmp/secret.log",
            "TF_LOG": "TRACE",
            "TF_LOG_PROVIDER": "TRACE",
        },
    )
    assert not any(key.startswith("TF_LOG") for key in env)


def test_output_schema_rejects_untrusted_fields_and_strings(capsys):
    h = helper()
    h.emit(
        {
            "status": SECRET,
            "run_url": "https://example.com/" + SECRET,
            "exception": SECRET,
            "imports": SECRET,
            "blockers": [SECRET],
            "warnings": [SECRET],
        }
    )
    captured = capsys.readouterr()
    assert SECRET not in captured.out + captured.err
    assert "exception" not in captured.out
    assert "example.com" not in captured.out
    assert "plan-diagnostic" in captured.out


@pytest.mark.skipif(sys.platform != "darwin", reason="macOS OS-boundary integration")
def test_real_os_boundary_blocks_secret_files_and_captures_crash_output(
    tmp_path, capsys
):
    import os

    h = helper()
    crash_file = tmp_path / "crash.log"
    code = (
        "import os,resource,sys; resource.setrlimit(resource.RLIMIT_CORE,(0,0)); "
        "print(os.environ['SYNTHETIC_MARKER']); print(os.environ['SYNTHETIC_MARKER'],file=sys.stderr); "
        "open(sys.argv[1],'w').write(os.environ['SYNTHETIC_MARKER'])"
    )
    result, stdout, stderr = h.capture_process(
        [
            "/usr/bin/sandbox-exec",
            "-p",
            h.SANDBOX_PROFILE,
            sys.executable,
            "-c",
            code,
            str(crash_file),
        ],
        {
            "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
            "SYNTHETIC_MARKER": SECRET,
            "PYTHONDONTWRITEBYTECODE": "1",
        },
    )
    assert result != 0
    assert not crash_file.exists()
    # Some macOS sandbox-exec builds reject this profile before launching the
    # child. If it launches, capture_process must keep both streams private;
    # otherwise an empty capture is the expected pre-exec denial result.
    if SECRET.encode() in stdout or SECRET.encode() in stderr:
        assert SECRET.encode() in stdout and SECRET.encode() in stderr
    else:
        # The sandbox may emit its own denial diagnostic. It must not contain the
        # child marker, and capture_process still keeps it off the terminal.
        assert SECRET.encode() not in stdout + stderr
    h.emit({"status": "blocked", "blockers": ["process-crash"]})
    captured = capsys.readouterr()
    assert SECRET not in captured.out + captured.err


def test_invalid_arguments_cannot_echo_secret(monkeypatch, capsys):
    h = helper()
    monkeypatch.setattr(h, "require_write_denial", lambda: None)
    monkeypatch.setattr(
        sys, "argv", ["live-inputs", "--manifest", "/tmp/fake", "--unknown=" + SECRET]
    )
    assert h.safe_entry() == 1
    captured = capsys.readouterr()
    assert SECRET not in captured.out + captured.err
    assert "usage:" not in captured.err


def test_sensitivity_metadata_updates_still_count_as_updates():
    h = helper()
    plan = {
        "format_version": "1.2",
        "resource_changes": [
            {
                "address": "test.resource",
                "change": {
                    "actions": ["update"],
                    "importing": {"id": "test-id"},
                    "before": {"secret": SECRET},
                    "after": {"secret": SECRET},
                    "before_sensitive": {},
                    "after_sensitive": {"secret": True},
                    "after_unknown": {},
                },
            }
        ],
    }
    counts, blockers, _ = h.summarize_changes(plan, {"test.resource": "test-id"})
    assert counts["updates"] == 1
    assert "sensitivity-metadata-updates" in blockers
    plan.pop("format_version")
    assert (
        "sensitivity-metadata-updates"
        not in h.summarize_changes(plan, {"test.resource": "test-id"})[1]
    )
