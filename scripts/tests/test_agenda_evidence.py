import importlib.util
from pathlib import Path

import pytest

spec = importlib.util.spec_from_file_location(
    "agenda_evidence", Path(__file__).resolve().parents[1] / "agenda-evidence.py"
)
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)


def test_missing_results_are_never_fabricated():
    with pytest.raises(ValueError):
        module.table({"cases": []})


def test_error_response_is_retained_with_unknown_usage():
    # Synthetic unit-test data only; never written as submission evidence.
    value = {
        "frontend_url": "https://deployed.test",
        "commit": "test",
        "today": "2026-10-17",
        "tz": "UTC",
        "cases": [
            {"case": i, "input": "test", "status": 422, "actual": {"detail": "invalid"}}
            for i in range(1, 6)
        ],
    }
    result = module.table(value)
    assert (
        "invalid" in result
        and "unknown" in result
        and "REQUIRES HUMAN REVIEW" in result
    )


def test_success_without_usage_is_rejected():
    value = {
        "frontend_url": "https://deployed.test",
        "commit": "test",
        "today": "2026-10-17",
        "tz": "UTC",
        "cases": [
            {"case": i, "input": "test", "actual": {"agenda": {}}} for i in range(1, 6)
        ],
    }
    with pytest.raises(ValueError):
        module.table(value)
