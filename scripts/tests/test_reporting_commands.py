import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]


def module(name):
    spec = importlib.util.spec_from_file_location(
        name.replace("-", "_"), ROOT / "scripts" / f"{name}.py"
    )
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def test_report_now_uses_sqs_only_and_no_owner_fields(monkeypatch, capsys):
    runner = module("report-now")
    monkeypatch.setenv("PROJECT_NAME", "peach")
    monkeypatch.delenv("REPORT_QUEUE_URL", raising=False)
    monkeypatch.setattr("sys.argv", ["report-now.py", "--week", "2026-W40"])
    commands = []

    def fake_run(command, **kwargs):
        commands.append(command)
        if command[0] != "aws":
            assert command[1].endswith("infra-outputs.py") and command[2] == "reports"
            return SimpleNamespace(
                returncode=0,
                stdout=json.dumps(
                    {
                        "WorkQueueUrl": "https://sqs.us-east-1.amazonaws.com/123456789012/peach-report-work"
                    }
                ),
            )
        assert command[1:3] == ["sqs", "send-message"]
        payload = json.loads(command[command.index("--message-body") + 1])
        assert set(payload) == {"source", "week", "correlation_id"}
        assert payload["source"] == "manual" and payload["week"] == "2026-W40"
        return SimpleNamespace(returncode=0, stdout='{"MessageId":"synthetic-1"}')

    monkeypatch.setattr(runner.subprocess, "run", fake_run)
    runner.main()
    assert len(commands) == 2
    assert "MUTATING AWS" in capsys.readouterr().out


def test_report_now_invalid_week_never_calls_aws(monkeypatch):
    runner = module("report-now")
    monkeypatch.setattr("sys.argv", ["report-now.py", "--week", "2025-W53"])
    monkeypatch.setattr(
        runner.subprocess, "run", lambda *a, **k: pytest.fail("AWS called")
    )
    with pytest.raises(ValueError):
        runner.main()


def test_report_now_rejects_external_queue_and_target_arguments(monkeypatch):
    runner = module("report-now")
    monkeypatch.setenv("REPORT_QUEUE_URL", "http://attacker/queue")
    monkeypatch.setattr("sys.argv", ["report-now.py", "--week", "2026-W40"])
    monkeypatch.setattr(
        runner.subprocess, "run", lambda *a, **k: pytest.fail("AWS called")
    )
    with pytest.raises(ValueError):
        runner.main()
    monkeypatch.setattr(
        "sys.argv", ["report-now.py", "--week", "2026-W40", "--owner", "attacker"]
    )
    with pytest.raises(SystemExit):
        runner.main()


def test_enqueue_error_sanitizes_credentials_without_retry(monkeypatch):
    runner = module("report-now")
    monkeypatch.setenv("AWS_SECRET_ACCESS_KEY", "private-value")
    calls = []

    def fail(command, **kwargs):
        calls.append(command)
        return SimpleNamespace(
            returncode=254,
            stdout="",
            stderr=(
                "An error occurred (AccessDenied) when calling the SendMessage operation: "
                "secret=private-value postgresql://user:password@host/db"
            ),
        )

    monkeypatch.setattr(runner.subprocess, "run", fail)
    with pytest.raises(runner.AwsError) as error:
        runner.aws(["sqs", "send-message"])
    assert "AccessDenied" in str(error.value)
    assert "private-value" not in str(error.value)
    assert "user:password" not in str(error.value)
    assert len(calls) == 1


def test_unstructured_cli_error_is_not_disclosed():
    runner = module("report-now")
    assert "sensitive" not in runner.sanitized_error("sensitive unstructured output")
