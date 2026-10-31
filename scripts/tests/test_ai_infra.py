"""Offline assertions for the budget and AI deployment boundary; no AWS clients.

Parser resource properties are asserted in infra/tests/migration.tftest.hcl.
"""

from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]


class Loader(yaml.SafeLoader):
    pass


Loader.add_multi_constructor(
    "!",
    lambda loader, tag, node: (
        loader.construct_scalar(node)
        if isinstance(node, yaml.ScalarNode)
        else loader.construct_sequence(node)
        if isinstance(node, yaml.SequenceNode)
        else loader.construct_mapping(node)
    ),
)


def test_budget_is_email_only_five_dollars():
    template = yaml.load((ROOT / "infra/budget.yml").read_text(), Loader=Loader)
    props = template["Resources"]["MonthlyBudget"]["Properties"]
    assert props["Budget"]["BudgetLimit"] == {"Amount": 5, "Unit": "USD"}
    assert props["Budget"]["TimeUnit"] == "MONTHLY"
    assert props["Budget"]["CostTypes"] == {
        "UseBlended": False,
        "UseAmortized": False,
        "IncludeCredit": False,
        "IncludeRefund": False,
    }
    assert template["Parameters"]["BudgetName"]["AllowedValues"] == [
        "peach-monthly-cost-alert"
    ]
    assert (
        props["NotificationsWithSubscribers"][0]["Subscribers"][0]["SubscriptionType"]
        == "EMAIL"
    )


def test_no_automatic_ai_deployment():
    workflow = (ROOT / ".github/workflows/deploy-backend.yml").read_text()
    assert "deploy-ai" not in workflow and "budget.yml" not in workflow
