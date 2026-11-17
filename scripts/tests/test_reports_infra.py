"""Offline guard: reporting infrastructure is never deployed by application CI.

Resource properties formerly asserted against infra/reports.yaml now live in
infra/tests/migration.tftest.hcl.
"""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def test_no_automatic_production_reporting_deployment():
    workflow = (ROOT / ".github/workflows/deploy-backend.yml").read_text()
    # Lab 9: the API moved to Cloud Run; the AWS release runs by hand only.
    assert "  push:" not in workflow and "  workflow_dispatch:" in workflow
    # Building handlers is safe; reporting infrastructure changes only via HCP Terraform.
    assert "make reports-prepare" not in workflow
    assert "make report-now" not in workflow
    assert "cloudformation execute-change-set" not in workflow
    assert "reports.yaml" not in (ROOT / "scripts/deploy-backend.sh").read_text()
    assert "reporting" not in (ROOT / "infra/github-oidc.yaml").read_text()
