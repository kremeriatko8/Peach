"""Offline release classification, workflow safety and migration-chain tests."""

import importlib.util
import shutil
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def gate():
    spec = importlib.util.spec_from_file_location(
        "schema_release", ROOT / "scripts/schema-release.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def source(tmp_path):
    shutil.copytree(ROOT / "backend/migrations", tmp_path / "backend/migrations")
    (tmp_path / "backend/app").mkdir()
    shutil.copy(ROOT / "backend/app/migration_handler.py", tmp_path / "backend/app")
    shutil.copytree(ROOT / "backend/app/models", tmp_path / "backend/app/models")
    shutil.copy(ROOT / "backend/alembic.ini", tmp_path / "backend")
    return tmp_path


def test_baseline_must_be_established_by_approved_schema_release(gate):
    current = gate.manifest()
    assert current["revision"] == "0004"
    for deployed in ("", "0" * 64):
        for approval in ("", "1" * 64):
            with pytest.raises(ValueError):
                gate.classify(current, deployed, approval)
        assert gate.classify(current, deployed, current["sha256"])["kind"] == "schema"
    assert gate.classify(current, current["sha256"])["kind"] == "ordinary"
    assert gate.classify(current, "", preparation=True)["kind"] == "schema"
    with pytest.raises(ValueError):
        gate.classify(current, "malformed", preparation=True)


@pytest.mark.parametrize(
    "relative",
    [
        "backend/app/models/meeting.py",
        "backend/migrations/env.py",
        "backend/alembic.ini",
        "backend/app/migration_handler.py",
        "backend/migrations/versions/0004_create_meetings.py",
    ],
)
def test_changed_migration_or_runner_requires_new_approval(gate, source, relative):
    before = gate.manifest(source)
    path = source / relative
    path.write_text(path.read_text() + "\n# reviewed change\n")
    after = gate.manifest(source)
    assert after["sha256"] != before["sha256"]
    with pytest.raises(ValueError):
        gate.classify(after, before["sha256"], before["sha256"])


@pytest.mark.parametrize(
    "mutation", ["new-head", "delete", "branch", "duplicate", "cycle"]
)
def test_incompatible_histories_fail_closed(gate, source, mutation):
    versions = source / "backend/migrations/versions"
    if mutation == "new-head":
        (versions / "0005.py").write_text('revision = "0005"\ndown_revision = "0004"\n')
    elif mutation == "delete":
        (versions / "0003_item_ownership.py").unlink()
    elif mutation == "branch":
        (versions / "branch.py").write_text(
            'revision = "branch"\ndown_revision = "0003"\n'
        )
    elif mutation == "duplicate":
        (versions / "duplicate.py").write_text(
            'revision = "0004"\ndown_revision = "0003"\n'
        )
    else:
        p = versions / "0003_item_ownership.py"
        p.write_text(
            p.read_text().replace('down_revision = "0002"', 'down_revision = "0004"')
        )
    with pytest.raises(ValueError):
        gate.manifest(source)


def test_workflow_validates_before_obtaining_deploy_credentials():
    # BaseLoader preserves the YAML key "on" instead of YAML 1.1's boolean.
    workflow = yaml.load(
        (ROOT / ".github/workflows/deploy-backend.yml").read_text(),
        Loader=yaml.BaseLoader,
    )
    assert workflow["on"]["push"]["branches"] == ["main"]
    assert "workflow_dispatch" in workflow["on"]
    assert "paths" not in workflow["on"]["push"]
    assert workflow["concurrency"]["cancel-in-progress"] == "false"
    jobs = workflow["jobs"]
    assert jobs["deploy"]["needs"] == "validate"
    assert "id-token" not in workflow["permissions"]
    assert jobs["deploy"]["permissions"] == {"id-token": "write", "contents": "read"}
    validation = str(jobs["validate"])
    for required in (
        "ruff check",
        "ruff format --check",
        "uv run pytest",
        "pytest scripts/tests",
        "cfn-lint",
        "bash -n",
        "--load",
    ):
        assert required in validation
    assert "configure-aws-credentials" not in validation
    deploy = jobs["deploy"]
    assert deploy["if"] == "github.ref == 'refs/heads/main'"
    credentials = next(
        s for s in deploy["steps"] if "configure-aws-credentials" in s.get("uses", "")
    )
    assert credentials["with"]["role-to-assume"] == "${{ vars.AWS_DEPLOY_ROLE_ARN }}"
    assert credentials["with"]["unset-current-credentials"] == "true"
    assert "make deploy-frontend" not in str(workflow)
    assert "make report-now" not in str(workflow)
