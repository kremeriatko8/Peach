"""Local invariants for the agenda administrative policy bundle; no AWS calls."""

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
POLICIES = ROOT / "infra/iam/agenda"


def test_documents_fit_managed_policy_limits_and_have_no_wildcard_actions():
    for path in POLICIES.glob("*.json"):
        policy = json.loads(path.read_text())
        assert len(json.dumps(policy, separators=(",", ":"))) <= 6144
        for statement in policy["Statement"]:
            actions = statement["Action"]
            if isinstance(actions, str):
                actions = [actions]
            assert all("*" not in action for action in actions)


def test_parser_creation_requires_administrator_owned_boundary():
    policy = json.loads((POLICIES / "operator-parser-provisioning.json").read_text())
    create = next(s for s in policy["Statement"] if "iam:CreateRole" in s["Action"])
    assert create["Condition"]["ArnEquals"]["iam:PermissionsBoundary"] == (
        "arn:aws:iam::968053399627:policy/PeachAgendaParserBoundary"
    )
    assert "PermissionsBoundary: !Sub" in (ROOT / "infra/ai.yml").read_text()
    boundary = json.loads((POLICIES / "parser-runtime-boundary.json").read_text())
    actions = [a for s in boundary["Statement"] for a in s["Action"]]
    assert set(actions) == {
        "bedrock:InvokeModel",
        "logs:CreateLogStream",
        "logs:PutLogEvents",
    }
    assert not any("reports" in json.dumps(s) for s in boundary["Statement"])


def test_nova_inference_is_exact_and_availability_read_is_regional_only():
    target = "arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-lite-v1:0"
    for name in ("parser-runtime-boundary.json", "optional-laptop-inference.json"):
        policy = json.loads((POLICIES / name).read_text())
        statement = policy["Statement"][0]
        assert statement["Action"] == ["bedrock:InvokeModel"]
        assert statement["Resource"] == target and "Condition" not in statement
    for name in ("operator-readiness.json", "readiness-readonly.json"):
        policy = json.loads((POLICIES / name).read_text())
        availability = next(
            s
            for s in policy["Statement"]
            if "bedrock:GetFoundationModelAvailability" in s["Action"]
        )
        assert availability["Resource"] == "*"
        assert availability["Condition"] == {
            "StringEquals": {"aws:RequestedRegion": "us-east-1"}
        }
