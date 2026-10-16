"""Offline assertions for the AI boundary and budget; no AWS clients."""

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


def test_parser_has_no_database_or_network_resources():
    template = yaml.load((ROOT / "infra/ai.yml").read_text(), Loader=Loader)
    resources = template["Resources"]
    assert not any(
        r["Type"].startswith(("AWS::RDS", "AWS::EC2", "AWS::SecretsManager"))
        for r in resources.values()
    )
    function = resources["Parser"]["Properties"]
    assert function["MemorySize"] == 512 and function["Timeout"] == 30
    assert function["ReservedConcurrentExecutions"] == 1
    assert "VpcConfig" not in function
    assert "DATABASE_URL" not in function["Environment"]["Variables"]
    assert function["ImageConfig"]["Command"] == ["app.ai.agenda_lambda.handler"]
    assert resources["Url"]["Properties"]["Cors"]["AllowMethods"] == ["POST"]
    assert template["Parameters"]["ParserEnabled"]["Default"] == "false"
    statements = resources["Role"]["Properties"]["Policies"][0]["PolicyDocument"][
        "Statement"
    ]
    assert statements[0]["Action"] == "bedrock-mantle:CreateInference"
    assert "bedrock:InvokeModel" not in str(statements)


def test_budget_is_email_only_five_dollars():
    template = yaml.load((ROOT / "infra/budget.yml").read_text(), Loader=Loader)
    props = template["Resources"]["MonthlyBudget"]["Properties"]
    assert props["Budget"]["BudgetLimit"] == {"Amount": 5, "Unit": "USD"}
    assert props["Budget"]["TimeUnit"] == "MONTHLY"
    assert (
        props["NotificationsWithSubscribers"][0]["Subscribers"][0]["SubscriptionType"]
        == "EMAIL"
    )


def test_no_automatic_ai_deployment():
    workflow = (ROOT / ".github/workflows/deploy-backend.yml").read_text()
    assert "deploy-ai" not in workflow and "budget.yml" not in workflow
