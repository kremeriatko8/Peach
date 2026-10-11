import importlib.util
from pathlib import Path

import pytest


@pytest.fixture
def runner():
    path = Path(__file__).resolve().parents[1] / "report-local.py"
    spec = importlib.util.spec_from_file_location("local_report_runner", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def local_stack():
    def container(service):
        return {
            "State": {"Running": True},
            "Config": {
                "Labels": {
                    "com.docker.compose.project": "peach-meetings-local",
                    "com.docker.compose.service": service,
                    "purpose": "peach-meetings-disposable-development",
                },
                "Env": [],
            },
            "NetworkSettings": {
                "Networks": {
                    "peach-meetings-local_peach": {
                        "IPAddress": "172.19.0.2",
                        "NetworkID": "local",
                    }
                }
            },
            "HostConfig": {"Tmpfs": {}, "PortBindings": {}},
            "Mounts": [],
        }

    db, backend = container("db"), container("backend")
    db["Config"]["Env"] = [
        "POSTGRES_USER=test",
        "POSTGRES_PASSWORD=test",
        "POSTGRES_DB=peach_meetings_local",
    ]
    db["HostConfig"] = {
        "Tmpfs": {"/var/lib/postgresql/data": ""},
        "PortBindings": {"5432/tcp": [{"HostIp": "127.0.0.1"}]},
    }
    backend["Config"]["Env"] = [
        "DATABASE_URL=postgresql+asyncpg://test:test@db:5432/peach_meetings_local"
    ]
    return db, backend


def test_local_safety_accepts_verified_stack(runner, local_stack):
    runner.verify_stack(*local_stack)


@pytest.mark.parametrize(
    "failure",
    [
        "production",
        "persistent",
        "wrong_project",
        "stopped",
        "extra_network",
        "public_port",
        "credentials",
        "missing_tmpfs",
    ],
)
def test_local_safety_rejects_unverified_stack(runner, local_stack, failure):
    db, backend = local_stack
    if failure == "production":
        backend["Config"]["Env"] = [
            "DATABASE_URL=postgresql+asyncpg://test:test@prod.rds.amazonaws.com/peach"
        ]
    elif failure == "persistent":
        db["Mounts"] = [{"Destination": "/var/lib/postgresql/data", "Type": "volume"}]
    elif failure == "wrong_project":
        db["Config"]["Labels"]["com.docker.compose.project"] = "peach"
    elif failure == "stopped":
        db["State"]["Running"] = False
    elif failure == "extra_network":
        backend["NetworkSettings"]["Networks"]["other"] = {}
    elif failure == "public_port":
        db["HostConfig"]["PortBindings"]["5432/tcp"][0]["HostIp"] = "0.0.0.0"
    elif failure == "credentials":
        db["Config"]["Env"][1] = "POSTGRES_PASSWORD=other"
    else:
        db["HostConfig"]["Tmpfs"] = {}
    with pytest.raises(ValueError):
        runner.verify_stack(db, backend)


def test_cli_invalid_week_never_inspects_or_queries(runner, monkeypatch):
    monkeypatch.setattr("sys.argv", ["report-local.py", "--week", "2025-W53"])
    monkeypatch.setattr(
        runner.subprocess, "run", lambda *a, **k: pytest.fail("Docker accessed")
    )
    with pytest.raises(ValueError):
        runner.main()


def test_cli_refuses_unverified_stack_before_query(runner, monkeypatch):
    from types import SimpleNamespace

    monkeypatch.setattr("sys.argv", ["report-local.py", "--week", "2026-W40"])
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=1, stdout=""),
    )
    monkeypatch.setattr(
        runner, "query", lambda *a, **k: pytest.fail("Database queried")
    )
    with pytest.raises(ValueError, match="Cannot verify"):
        runner.main()


def test_cli_requires_configured_owner(runner, local_stack, monkeypatch, tmp_path):
    import json
    from types import SimpleNamespace

    monkeypatch.setattr("sys.argv", ["report-local.py", "--week", "2026-W40"])
    monkeypatch.setattr(runner, "OWNER_CONFIG", tmp_path / "missing")
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout=json.dumps(local_stack)),
    )
    monkeypatch.setattr(
        runner, "query", lambda *a, **k: pytest.fail("Database queried")
    )
    with pytest.raises(ValueError, match="Select a local owner first"):
        runner.main()


def test_cli_owner_selection_keeps_subject_private(
    runner, local_stack, monkeypatch, tmp_path, capsys
):
    import json
    from types import SimpleNamespace

    config = tmp_path / "owner.json"
    monkeypatch.setattr("sys.argv", ["report-local.py", "--select-owner", "1"])
    monkeypatch.setattr(runner, "OWNER_CONFIG", config)
    monkeypatch.setattr(
        runner.subprocess,
        "run",
        lambda *a, **k: SimpleNamespace(returncode=0, stdout=json.dumps(local_stack)),
    )
    monkeypatch.setattr(
        runner, "query", lambda *a, **k: {"owners": ["private-test-sub"]}
    )
    runner.main()
    assert json.loads(config.read_text()) == {"owner_sub": "private-test-sub"}
    assert config.stat().st_mode & 0o777 == 0o600
    assert "private-test-sub" not in capsys.readouterr().out
