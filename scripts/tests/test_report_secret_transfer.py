"""Mock-only tests; never retrieve a real secret or connect to a database."""

import importlib.util
import json
from pathlib import Path
from unittest.mock import Mock

import pytest

ROOT = Path(__file__).resolve().parents[2]


@pytest.fixture
def helper():
    spec = importlib.util.spec_from_file_location(
        "secret_transfer", ROOT / "scripts/prepare-report-database-url.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def session(helper, value):
    sts = Mock()
    sts.get_caller_identity.return_value = {"Account": "968053399627"}
    secret = Mock()
    secret.get_secret_value.return_value = {"ARN": helper.SECRET, "SecretString": value}
    s = Mock()
    s.client.side_effect = lambda name: sts if name == "sts" else secret
    return s, secret


def test_transfer_preserves_values_and_protects_file(helper, tmp_path, capsys):
    target = tmp_path / "parameters.local"
    rows = [{"ParameterKey": "ProjectName", "ParameterValue": "peach"}]
    target.write_text(json.dumps(rows))
    value = "postgresql+asyncpg://test:dummy@cluster.rds.amazonaws.com/peach"
    s, secret = session(helper, value)
    helper.transfer(s, target)
    assert json.loads(target.read_text()) == rows + [
        {"ParameterKey": "DatabaseUrl", "ParameterValue": value}
    ]
    assert target.stat().st_mode & 0o777 == 0o600
    secret.get_secret_value.assert_called_once_with(SecretId=helper.SECRET)
    assert not capsys.readouterr().out
    assert not list(tmp_path.glob(".reports-parameters-*"))


def test_existing_secret_is_never_overwritten_or_retrieved(helper, tmp_path):
    target = tmp_path / "parameters.local"
    target.write_text(
        json.dumps([{"ParameterKey": "DatabaseUrl", "ParameterValue": "existing"}])
    )
    s = Mock()
    with pytest.raises(ValueError):
        helper.transfer(s, target)
    s.client.assert_not_called()


def test_wrong_account_prevents_secret_read(helper, tmp_path):
    target = tmp_path / "parameters.local"
    target.write_text("[]")
    s, secret = session(helper, "unused")
    s.client("sts").get_caller_identity.return_value = {"Account": "000000000000"}
    with pytest.raises(ValueError):
        helper.transfer(s, target)
    secret.get_secret_value.assert_not_called()
    assert target.read_text() == "[]"
