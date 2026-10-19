import pytest

from app.ai import cli


def test_cli_requires_explicit_approval_before_client_creation(monkeypatch):
    monkeypatch.delenv("PEACH_APPROVE_PAID_INFERENCE", raising=False)
    monkeypatch.setattr("sys.argv", ["agenda", "hello"])
    monkeypatch.setattr(cli, "make_client", lambda: pytest.fail("Unapproved paid client"))
    with pytest.raises(SystemExit) as result:
        cli.main()
    assert result.value.code == 2
