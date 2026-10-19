#!/usr/bin/env python3
"""Guarded agenda release phases. Defaults to an OFFLINE plan; never auto-activates.

AWS mutation phases require --approve ACCOUNT:COMMIT:PHASE. This is an operator
interlock, not a substitute for the user's explicit authorization.
"""

import argparse
import asyncio
import hashlib
import json
import os
import re
import ssl
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(__file__).resolve().parents[1]
ACCOUNT = "968053399627"
REGION = "us-east-1"
BASE = "5dd75e6a67dd2607b4ae30516e4968b15b097bf6"
BRANCH = "feat/paste-agenda"
REQUIRED = [
    "infra/ai.yml",
    "infra/budget.yml",
    "backend/app/ai/agenda_lambda.py",
    "backend/migrations/versions/0005_create_agendas.py",
    "docs/adr/0006-llm-agenda-parsing.md",
    "scripts/agenda-release.py",
]


class Stop(ValueError):
    pass


def require(condition, message):
    if not condition:
        raise Stop(message)


def git(*args):
    return subprocess.check_output(["git", "-C", str(ROOT), *args], text=True).strip()


def now():
    return datetime.now(timezone.utc)


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, default=str))
    path.chmod(0o600)


def source(commit, clean=True):
    require(
        re.fullmatch(r"[a-f0-9]{40}", commit), "Pin the full reviewed release commit"
    )
    require(git("rev-parse", "HEAD") == commit, "HEAD differs from the reviewed commit")
    require(git("branch", "--show-current") == BRANCH, "Wrong feature branch")
    subprocess.run(
        ["git", "-C", str(ROOT), "merge-base", "--is-ancestor", BASE, commit],
        check=True,
    )
    dirty = bool(git("status", "--porcelain"))
    require(
        not clean or not dirty,
        "Commit/review local safeguards first; dirty releases refused",
    )
    require(
        all((ROOT / p).is_file() for p in REQUIRED),
        "Expected release artifacts missing",
    )
    schema = json.loads(
        subprocess.check_output(
            [sys.executable, str(ROOT / "scripts/schema-release.py")], text=True
        )
    )
    require(schema["revision"] == "0005", "Unexpected migration head")
    return {"commit": commit, "branch": BRANCH, "dirty": dirty, "schema": schema}


def session(profile=None):
    import boto3

    require(
        os.environ.get("AWS_REGION", REGION) == REGION, "AWS_REGION must be us-east-1"
    )
    require(
        os.environ.get("AWS_DEFAULT_REGION", REGION) == REGION, "Wrong default region"
    )
    result = boto3.Session(profile_name=profile or None, region_name=REGION)
    identity = result.client("sts").get_caller_identity()
    require(identity["Account"] == ACCOUNT, "Wrong AWS account")
    return result


def deployment_environment(aws, commit):
    """Freeze the identity already checked by STS; never reload local credentials."""
    credentials = aws.get_credentials()
    require(credentials is not None, "Verified AWS session has no credentials")
    frozen = credentials.get_frozen_credentials()
    env = dict(os.environ)
    require(
        not any(
            k == "AWS_ENDPOINT_URL" or k.startswith("AWS_ENDPOINT_URL_") for k in env
        ),
        "Custom AWS service endpoints are not allowed for release",
    )
    for key in (
        "AWS_PROFILE",
        "AWS_DEFAULT_PROFILE",
        "AWS_SESSION_TOKEN",
        "AWS_SECURITY_TOKEN",
    ):
        env.pop(key, None)
    env.update(
        AWS_ACCESS_KEY_ID=frozen.access_key,
        AWS_SECRET_ACCESS_KEY=frozen.secret_key,
        AWS_REGION=REGION,
        AWS_DEFAULT_REGION=REGION,
        PEACH_IGNORE_LOCAL_ENV="true",
        PROJECT_NAME="peach",
        STACK_NAME="peach-backend",
        AUTH_STACK_NAME="peach-auth",
        MIGRATION_STACK_NAME="peach-migrations",
        FRONTEND_STACK_NAME="peach-frontend",
        ECR_REPOSITORY="peach-backend",
        LAMBDA_ARCHITECTURE="arm64",
        IMAGE_TAG=commit[:12],
    )
    if frozen.token:
        env["AWS_SESSION_TOKEN"] = frozen.token
    return env


def stack(aws, name, optional=False):
    from botocore.exceptions import ClientError

    try:
        result = aws.client("cloudformation").describe_stacks(StackName=name)["Stacks"][
            0
        ]
    except ClientError as error:
        if (
            optional
            and error.response["Error"]["Code"] == "ValidationError"
            and "does not exist" in error.response["Error"]["Message"]
        ):
            return None
        raise
    if name in {
        "peach-backend",
        "peach-migrations",
        "peach-frontend",
        "peach-ai",
        "peach-budget",
    }:
        require(
            not result.get("RoleARN"), "Unreviewed CloudFormation service role: " + name
        )
    require(
        result["StackStatus"]
        in {"CREATE_COMPLETE", "UPDATE_COMPLETE", "UPDATE_ROLLBACK_COMPLETE"},
        f"Unstable stack: {name}",
    )
    return result


def outputs(value):
    return {v["OutputKey"]: v["OutputValue"] for v in value.get("Outputs", [])}


def image(aws, name):
    result = aws.client("lambda").get_function(FunctionName=name)
    cfg = result["Configuration"]
    require(
        cfg.get("State") == "Active" and cfg.get("LastUpdateStatus") == "Successful",
        f"Function not stable: {name}",
    )
    return result["Code"]["ResolvedImageUri"]


def state_file(args):
    folder = args.directory.resolve()
    require(
        folder.is_relative_to((ROOT / "reports-local/agenda").resolve()),
        "Release state must stay in ignored reports-local/agenda",
    )
    return folder / "release.json"


def load_state(args):
    data = json.loads(state_file(args).read_text())
    require(
        data["source"] == source(args.commit),
        "Release state differs from reviewed source",
    )
    require(
        data["account"] == ACCOUNT and data["region"] == REGION, "State target mismatch"
    )
    return data


def check_capacity(aws):
    """Lab parser shares regional concurrency; no reservation/quota increase needed."""
    free = aws.client("lambda").get_account_settings()["AccountLimit"][
        "UnreservedConcurrentExecutions"
    ]
    require(type(free) is int and free > 0, "No unreserved Lambda capacity available")


def matching_budget(budget):
    """Require the named account-wide, pre-credit budget, not a filtered lookalike."""
    costs = budget.get("CostTypes", {})
    return (
        budget.get("BudgetName") == "peach-monthly-cost-alert"
        and budget.get("TimeUnit") == "MONTHLY"
        and budget.get("BudgetType") == "COST"
        and budget.get("BudgetLimit", {}).get("Unit") == "USD"
        and float(budget.get("BudgetLimit", {}).get("Amount", 0)) == 5
        and not budget.get("CostFilters")
        and not budget.get("FilterExpression")
        and costs.get("IncludeCredit") is False
        and costs.get("IncludeRefund") is False
        and costs.get("UseBlended", False) is False
        and costs.get("UseAmortized", False) is False
    )


def check_image_retention(aws, images):
    """Read-only gate, repeated immediately before publishing a new shared image."""
    from botocore.exceptions import ClientError

    ecr = aws.client("ecr")
    try:
        rules = json.loads(
            ecr.get_lifecycle_policy(repositoryName="peach-backend")[
                "lifecyclePolicyText"
            ]
        )["rules"]
    except ClientError as error:
        if error.response["Error"]["Code"] != "LifecyclePolicyNotFoundException":
            raise
        rules = []
    require(
        all(r["selection"]["tagStatus"] == "untagged" for r in rules),
        "Lifecycle may expire tagged rollback/report images; administrator must protect them",
    )
    for uri in set(images.values()):
        require(
            re.fullmatch(
                rf"{ACCOUNT}\.dkr\.ecr\.{REGION}\.amazonaws\.com/peach-backend@sha256:[a-f0-9]{{64}}",
                uri,
            ),
            "Unexpected protected image repository or digest",
        )
        detail = ecr.describe_images(
            repositoryName="peach-backend",
            imageIds=[{"imageDigest": uri.split("@")[-1]}],
        )["imageDetails"][0]
        require(
            not rules or detail.get("imageTags"), "A protected live digest is untagged"
        )


def read_checks(aws):
    """All are metadata GETs. Any denial stops; no fallback identity or write."""
    model_id = "amazon.nova-lite-v1:0"
    bedrock = aws.client("bedrock")
    model = bedrock.get_foundation_model(modelIdentifier=model_id)["modelDetails"]
    require(
        model.get("modelId") == model_id
        and model.get("modelArn")
        == "arn:aws:bedrock:us-east-1::foundation-model/" + model_id,
        "Unexpected Nova model identity",
    )
    require(
        "ON_DEMAND" in model.get("inferenceTypesSupported", []),
        "Nova on-demand support required",
    )
    require(
        model.get("modelLifecycle", {}).get("status") == "ACTIVE",
        "Nova model is not active",
    )
    availability = bedrock.get_foundation_model_availability(modelId=model_id)
    require(
        availability.get("regionAvailability") == "AVAILABLE"
        and availability.get("authorizationStatus") == "AUTHORIZED"
        and availability.get("entitlementAvailability") == "AVAILABLE",
        "Nova regional/account access not verified; inspect model availability before release",
    )
    agreement = availability.get("agreementAvailability", {})
    require(
        agreement.get("status") == "AVAILABLE",
        "Model agreement not verified",
    )
    check_capacity(aws)
    # Pin in-region, base Nova Lite quotas; no cross-region/custom/batch substitution.
    quotas = [
        q
        for page in aws.client("service-quotas")
        .get_paginator("list_service_quotas")
        .paginate(ServiceCode="bedrock")
        for q in page["Quotas"]
    ]
    required_quotas = {"L-70423BF8", "L-E386A278"}
    relevant = {
        q["QuotaCode"]: q["Value"] for q in quotas if q["QuotaCode"] in required_quotas
    }
    require(
        set(relevant) == required_quotas and all(v > 0 for v in relevant.values()),
        "Positive Nova Lite on-demand token/request quotas must be verified",
    )
    email = os.environ.get("PEACH_BUDGET_EMAIL", "")
    require(email, "Supply the intended budget email privately")
    budgets = aws.client("budgets")
    valid = False
    for page in budgets.get_paginator("describe_budgets").paginate(AccountId=ACCOUNT):
        for budget in page.get("Budgets", []):
            if not matching_budget(budget):
                continue
            notices = budgets.describe_notifications_for_budget(
                AccountId=ACCOUNT, BudgetName=budget["BudgetName"]
            )["Notifications"]
            for notice in notices:
                absolute = (
                    notice.get("ThresholdType") == "ABSOLUTE_VALUE"
                    and 0 < notice["Threshold"] <= 5
                )
                percent = (
                    notice.get("ThresholdType") == "PERCENTAGE"
                    and 0 < notice["Threshold"] <= 100
                )
                if (
                    notice.get("NotificationType") != "ACTUAL"
                    or notice.get("ComparisonOperator") != "GREATER_THAN"
                    or not (absolute or percent)
                ):
                    continue
                people = budgets.describe_subscribers_for_notification(
                    AccountId=ACCOUNT,
                    BudgetName=budget["BudgetName"],
                    Notification=notice,
                )["Subscribers"]
                valid |= any(
                    p["SubscriptionType"] == "EMAIL" and p["Address"] == email
                    for p in people
                )
    require(
        valid, "A verified USD 5 monthly email notification is required before release"
    )
    existing = stack(aws, "peach-ai", optional=True)
    if existing:
        require(
            parser_config(aws)["Environment"]["Variables"]["PARSER_ENABLED"] == "false",
            "Existing parser is enabled; review/disable separately before a new release",
        )
    stack(aws, "peach-budget", optional=True)


def local_verify(args):
    import time
    import uuid

    src = source(args.commit)
    tag = "peach-agenda:" + args.commit[:12] + "-verified"
    subprocess.run(
        [
            "docker",
            "buildx",
            "build",
            "--platform",
            "linux/arm64",
            "--target",
            "lambda",
            "--provenance=false",
            "--sbom=false",
            "--load",
            "--tag",
            tag,
            "--label",
            "org.opencontainers.image.revision=" + args.commit,
            str(ROOT / "backend"),
        ],
        check=True,
    )
    detail = json.loads(
        subprocess.check_output(["docker", "image", "inspect", tag], text=True)
    )[0]
    require(
        detail["Os"] == "linux" and detail["Architecture"] == "arm64",
        "Wrong image platform",
    )
    subprocess.run(
        [
            "docker",
            "run",
            "--rm",
            "--network",
            "none",
            "--entrypoint",
            "python",
            tag,
            "-c",
            "from app.ai.agenda_lambda import handler; "
            "import app.lambda_handler, app.migration_handler, app.reporting.builder, app.reporting.mailer; "
            "assert handler({'requestContext':{'http':{'method':'POST'}}},None)['statusCode']==401",
        ],
        check=True,
    )
    container = "peach-agenda-check-" + uuid.uuid4().hex[:10]
    try:
        subprocess.run(
            [
                "docker",
                "run",
                "--detach",
                "--name",
                container,
                "--publish",
                "127.0.0.1::5432",
                "--tmpfs",
                "/var/lib/postgresql/data:rw,noexec,nosuid",
                "-e",
                "POSTGRES_PASSWORD=disposable-local-only",
                "-e",
                "POSTGRES_DB=peach_agenda_test",
                "postgres:17-alpine",
            ],
            check=True,
        )
        for _ in range(30):
            if (
                subprocess.run(
                    ["docker", "exec", container, "pg_isready", "-U", "postgres"],
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                ).returncode
                == 0
            ):
                break
            time.sleep(1)
        else:
            raise Stop("Disposable PostgreSQL did not become ready")
        port = (
            subprocess.check_output(["docker", "port", container, "5432"], text=True)
            .strip()
            .rsplit(":", 1)[1]
        )
        env = {
            **os.environ,
            "TEST_DATABASE_URL": f"postgresql+asyncpg://postgres:disposable-local-only@127.0.0.1:{port}/peach_agenda_test",
            "AWS_EC2_METADATA_DISABLED": "true",
        }
        subprocess.run(
            [sys.executable, "-m", "pytest", "backend/tests", "scripts/tests", "-q"],
            cwd=ROOT,
            env=env,
            check=True,
        )
    finally:
        subprocess.run(["docker", "rm", "--force", container], check=False)
    subprocess.run(["pnpm", "test"], cwd=ROOT / "frontend", check=True)
    subprocess.run(["pnpm", "lint"], cwd=ROOT / "frontend", check=True)
    subprocess.run(
        ["pnpm", "exec", "tsc", "--noEmit"], cwd=ROOT / "frontend", check=True
    )
    subprocess.run(
        ["pnpm", "exec", "prettier", "--check", "."], cwd=ROOT / "frontend", check=True
    )
    subprocess.run(
        ["pnpm", "exec", "next", "build", "--webpack"],
        cwd=ROOT / "frontend",
        env={**os.environ, "NEXT_OUTPUT": "export"},
        check=True,
    )
    subprocess.run(
        [sys.executable, "-m", "ruff", "check", "backend"], cwd=ROOT, check=True
    )
    subprocess.run(
        [sys.executable, "-m", "ruff", "format", "--check", "backend"],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [
            sys.executable,
            "-m",
            "ruff",
            "check",
            "--isolated",
            "--select",
            "E4,E7,E9,F,I,UP,B",
            "scripts",
        ],
        cwd=ROOT,
        check=True,
    )
    subprocess.run(
        [sys.executable, "-m", "ruff", "format", "--isolated", "--check", "scripts"],
        cwd=ROOT,
        check=True,
    )
    lint = Path(sys.executable).parent / "cfn-lint"
    require(lint.is_file(), "Install cfn-lint in the verification tools environment")
    subprocess.run(
        [
            str(lint),
            "--regions",
            REGION,
            "--template",
            "infra/ai.yml",
            "infra/budget.yml",
        ],
        cwd=ROOT,
        check=True,
    )
    require(source(args.commit) == src, "Source changed during verification")
    write(
        args.directory / "verification.json",
        {
            "source": src,
            "image_id": detail["Id"],
            "postgres_major": 17,
            "platform": "linux/arm64",
            "at": now().isoformat(),
        },
    )


def preserve(args, aws):
    """Archive browser assets and pinned image identities through read-only APIs."""
    src = source(args.commit)
    require(
        not state_file(args).exists(),
        "Use a new release directory; never overwrite rollback state",
    )
    read_checks(aws)
    front = outputs(stack(aws, "peach-frontend"))
    bucket = front["BucketName"]
    s3 = aws.client("s3")
    listing = [
        obj
        for page in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket)
        for obj in page.get("Contents", [])
    ]
    require(
        listing
        and len(listing) <= 20000
        and sum(v["Size"] for v in listing) <= 500_000_000,
        "Unexpected frontend archive size",
    )
    files = []
    for obj in listing:
        key = Path(obj["Key"])
        require(not key.is_absolute() and ".." not in key.parts, "Unsafe object key")
        target = args.directory / "frontend" / key
        require(not target.exists(), "Archive target already exists")
        result = s3.get_object(Bucket=bucket, Key=obj["Key"], IfMatch=obj["ETag"])
        body = result["Body"].read()
        target.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        target.write_bytes(body)
        files.append(
            {
                "key": obj["Key"],
                "sha256": hashlib.sha256(body).hexdigest(),
                "etag": obj["ETag"],
                **{
                    k: result[k]
                    for k in (
                        "ContentType",
                        "CacheControl",
                        "ContentEncoding",
                        "Metadata",
                    )
                    if k in result
                },
            }
        )
    after = [
        (o["Key"], o["ETag"])
        for p in s3.get_paginator("list_objects_v2").paginate(Bucket=bucket)
        for o in p.get("Contents", [])
    ]
    require(
        after == [(o["Key"], o["ETag"]) for o in listing],
        "Frontend changed during archive",
    )
    images = {name: image(aws, name) for name in ("peach-backend", "peach-migrations")}
    # Use the explicitly configured reporting identity only for report baseline reads.
    reports = session(args.reports_profile) if args.reports_profile else aws
    images.update(
        {
            name: image(reports, name)
            for name in ("peach-report-builder", "peach-report-mailer")
        }
    )
    check_image_retention(aws, images)
    data = {
        "source": src,
        "account": ACCOUNT,
        "region": REGION,
        "created_at": now().isoformat(),
        "images": images,
        "frontend": front,
        "assets": files,
        "phase": "preserved",
    }
    write(state_file(args), data)
    print("Read-only preservation completed; no deployment or activation")


def verify_archive(args, state, aws):
    for item in state["assets"]:
        path = args.directory / "frontend" / item["key"]
        require(
            path.is_file()
            and hashlib.sha256(path.read_bytes()).hexdigest() == item["sha256"],
            "Rollback archive missing or changed",
        )
    listing = [
        (o["Key"], o["ETag"])
        for page in aws.client("s3")
        .get_paginator("list_objects_v2")
        .paginate(Bucket=state["frontend"]["BucketName"])
        for o in page.get("Contents", [])
    ]
    require(
        listing == [(v["key"], v["etag"]) for v in state["assets"]],
        "Frontend baseline changed; capture a new coherent rollback archive",
    )


def check_snapshot(aws, identifier):
    require(identifier, "Fresh approved PEACH_RELEASE_SNAPSHOT_ID is required")
    items = aws.client("rds").describe_db_cluster_snapshots(
        DBClusterSnapshotIdentifier=identifier
    )["DBClusterSnapshots"]
    require(len(items) == 1, "Snapshot not uniquely resolved")
    value = items[0]
    age = now() - value["SnapshotCreateTime"]
    require(
        value["DBClusterIdentifier"] == "peach-db"
        and value["Status"] == "available"
        and value["SnapshotType"] == "manual"
        and value.get("StorageEncrypted") is True
        and timedelta(0) <= age < timedelta(hours=24),
        "Snapshot must be encrypted, available, manual, <24h old and belong to peach-db",
    )


def execute_disabled(args, aws, state):
    require(args.change_set_id, "Supply the exact reviewed change-set ARN")
    cf = aws.client("cloudformation")
    value = cf.describe_change_set(
        StackName="peach-ai", ChangeSetName=args.change_set_id
    )
    require(
        value["ChangeSetId"] == args.change_set_id
        and value["StackName"] == "peach-ai"
        and value["Status"] == "CREATE_COMPLETE"
        and value["ExecutionStatus"] == "AVAILABLE",
        "Change set is not the reviewed executable AI change set",
    )
    params = {p["ParameterKey"]: p.get("ParameterValue") for p in value["Parameters"]}
    require(
        params.get("ParserEnabled") == "false"
        and params.get("ImageUri") == state["new_image"],
        "AI change set must remain disabled and use the verified image",
    )
    template = cf.get_template(StackName="peach-ai", ChangeSetName=args.change_set_id)[
        "TemplateBody"
    ]
    require(
        isinstance(template, str)
        and template.strip() == (ROOT / "infra/ai.yml").read_text().strip(),
        "Stored change-set template differs from reviewed source; inspect before execution",
    )
    allowed = {"Role", "LogGroup", "Parser", "Url", "UrlPermission", "InvokePermission"}
    require(
        all(
            v["ResourceChange"]["LogicalResourceId"] in allowed
            and v["ResourceChange"]["Action"] in {"Add", "Modify"}
            for v in value["Changes"]
        ),
        "Unexpected AI resource removal/change",
    )
    current_stack = cf.describe_stacks(StackName="peach-ai")["Stacks"][0]
    require(
        not current_stack.get("RoleARN"),
        "Unreviewed CloudFormation service role: peach-ai",
    )
    current = current_stack["StackStatus"]
    cf.execute_change_set(StackName="peach-ai", ChangeSetName=args.change_set_id)
    cf.get_waiter(
        "stack_create_complete"
        if current == "REVIEW_IN_PROGRESS"
        else "stack_update_complete"
    ).wait(StackName="peach-ai")
    cfg = parser_config(aws)
    require(
        cfg["Environment"]["Variables"]["PARSER_ENABLED"] == "false",
        "Parser is not disabled",
    )
    require(
        image(aws, "peach-agenda-parser") == state["new_image"],
        "Unexpected deployed parser image",
    )
    print(
        "Disabled parser deployed. Activation and paid inference remain separate approvals."
    )


async def db_revision(aws):
    import asyncpg

    cluster = aws.client("rds").describe_db_clusters(DBClusterIdentifier="peach-db")[
        "DBClusters"
    ][0]
    require(cluster["Status"] == "available", "Aurora is not available")
    dsn = os.environ.get("PEACH_READONLY_DATABASE_URL", "")
    parsed = urlsplit(dsn)
    require(
        parsed.scheme in {"postgresql", "postgresql+asyncpg"}
        and parsed.hostname == cluster["Endpoint"]
        and parsed.path == "/" + cluster["DatabaseName"],
        "Provide a private read-only DB URL matching the existing Aurora endpoint/database",
    )
    try:
        ctx = ssl.create_default_context(cafile=os.environ.get("PEACH_RDS_CA_FILE"))
        conn = await asyncpg.connect(
            dsn.replace("postgresql+asyncpg:", "postgresql:", 1), ssl=ctx, timeout=10
        )
        try:
            async with conn.transaction(readonly=True, isolation="repeatable_read"):
                await conn.execute("SET LOCAL statement_timeout = '5s'")
                rows = await conn.fetch("SELECT version_num FROM alembic_version")
                require(
                    len(rows) == 1 and rows[0][0] in {"0004", "0005"},
                    "Unexpected actual DB revision",
                )
                return rows[0][0]
        finally:
            await conn.close()
    except Stop:
        raise
    except Exception as error:
        raise Stop(
            f"Private read-only DB check failed ({type(error).__name__}); no migration invoked"
        ) from None


def approve(args, phase):
    require(
        args.approve == f"{ACCOUNT}:{args.commit}:{phase}",
        f"Explicit approval required for {phase}",
    )


def token_file(path):
    require(
        path and path.is_file() and path.stat().st_mode & 0o077 == 0,
        "Use a private mode-0600 Cognito token file; never put the token in command arguments",
    )
    return path.read_text().strip()


def parser_config(aws):
    cfg = aws.client("lambda").get_function_configuration(
        FunctionName="peach-agenda-parser"
    )
    require(
        cfg.get("State") == "Active" and cfg.get("LastUpdateStatus") == "Successful",
        "Parser not ready",
    )
    env = cfg["Environment"]["Variables"]
    require(
        not cfg.get("VpcConfig", {}).get("VpcId") and "DATABASE_URL" not in env,
        "Parser isolation mismatch",
    )
    require(env["PARSER_MODEL"] == "amazon.nova-lite-v1:0", "Required model changed")
    require(
        cfg["Timeout"] == 30 and cfg["MemorySize"] == 512, "Unexpected parser limits"
    )
    concurrency = aws.client("lambda").get_function_concurrency(
        FunctionName="peach-agenda-parser"
    )
    require(
        concurrency.get("ReservedConcurrentExecutions") is None,
        "Lab parser must use shared concurrency without a reservation",
    )
    return cfg


def smoke(args, aws, paid=False):
    import httpx

    state = load_state(args)
    cfg = parser_config(aws)
    require(
        image(aws, "peach-agenda-parser") == state["new_image"],
        "Unexpected parser image",
    )
    require(
        cfg["Environment"]["Variables"]["PARSER_ENABLED"]
        == ("true" if paid else "false"),
        "Parser enabled state does not match this smoke phase",
    )
    if paid:
        approve(args, "paid-smoke")
    url = outputs(stack(aws, "peach-ai"))["ParserUrl"]
    token = token_file(args.token_file)
    with httpx.Client(timeout=35) as client:
        require(
            client.post(
                url,
                json={
                    "text": "Pricing",
                    "today": now().date().isoformat(),
                    "tz": "Europe/Kyiv",
                },
            ).status_code
            == 401,
            "Unauthenticated parser must reject requests",
        )
        auth = {"Authorization": "Bearer " + token}
        payload = {
            "text": "Pricing sync. Review Pro prices — Олена, 15 minutes.",
            "today": now().date().isoformat(),
            "tz": "Europe/Kyiv",
        }
        require(
            client.post(
                url, headers=auth, json={**payload, "text": "x" * 10001}
            ).status_code
            == 413,
            "Oversized request must be rejected before inference",
        )
        result = client.post(url, headers=auth, json=payload)
    if not paid:
        require(
            result.status_code == 503,
            "Disabled parser must return 503 with a valid token",
        )
        print("Disabled/auth/size smoke passed; no inference requested")
        return
    require(
        result.status_code == 200,
        f"Paid smoke failed HTTP {result.status_code}; do not retry automatically",
    )
    from app.ai.agenda import ParsedAgenda

    body = result.json()
    ParsedAgenda.model_validate(body["agenda"])
    require(
        body["model"] == "amazon.nova-lite-v1:0"
        and body["prompt_version"] == "agenda-v1",
        "Unexpected model/prompt result",
    )
    write(
        args.directory / "paid-smoke.json",
        {
            "at": now().isoformat(),
            "commit": args.commit,
            "parser_modified": cfg["LastModified"],
            "image": state["new_image"],
            "url": url,
            "request_id": result.headers.get("x-amzn-requestid"),
            "response": body,
        },
    )
    print("One actual paid smoke recorded; not a substitute for five deployed UI cases")


def check_smoke_receipt(receipt, commit, state, cfg):
    """Bind smoke to unchanged artifacts, without forcing another billable call by age."""
    require(
        receipt["commit"] == commit
        and receipt["image"] == state["new_image"]
        and receipt["parser_modified"] == cfg["LastModified"],
        "An actual functional smoke on this exact parser configuration is required",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "phase",
        choices=[
            "plan",
            "local-verify",
            "preserve",
            "check-db",
            "backend",
            "parser-disabled",
            "execute-disabled",
            "smoke-disabled",
            "paid-smoke",
            "frontend",
        ],
    )
    parser.add_argument("--commit", required=True)
    parser.add_argument(
        "--directory", type=Path, default=ROOT / "reports-local/agenda/release"
    )
    parser.add_argument("--profile")
    parser.add_argument("--reports-profile")
    parser.add_argument("--approve")
    parser.add_argument("--token-file", type=Path)
    parser.add_argument("--ai-parameters", type=Path)
    parser.add_argument("--change-set-id")
    parser.add_argument(
        "--expected-db-revision", choices=["0004", "0005"], default="0004"
    )
    args = parser.parse_args()
    state_file(args)
    if args.phase == "plan":
        print(json.dumps(source(args.commit, clean=False), indent=2))
        print(
            "OFFLINE ONLY. Dirty source cannot be released. Each mutation phase requires explicit approval."
        )
        return
    source(args.commit)
    if args.phase == "local-verify":
        local_verify(args)
        return
    if args.phase in {
        "backend",
        "parser-disabled",
        "execute-disabled",
        "frontend",
        "paid-smoke",
    }:
        approve(args, args.phase)
    aws = session(args.profile)
    if args.phase == "preserve":
        preserve(args, aws)
        return
    if args.phase == "check-db":
        print(json.dumps({"actual_readonly_revision": asyncio.run(db_revision(aws))}))
        return
    if args.phase in {"smoke-disabled", "paid-smoke"}:
        smoke(args, aws, paid=args.phase == "paid-smoke")
        return
    state = load_state(args)
    # A persisted CF service role can be reused without a new PassRole check.
    # This reviewed path deliberately uses the scoped operator credentials only.
    for name in ("peach-backend", "peach-migrations", "peach-frontend"):
        stack(aws, name)
    env = deployment_environment(aws, args.commit)
    if args.phase == "backend":
        read_checks(aws)
        require(
            image(aws, "peach-backend") == state["images"]["peach-backend"],
            "Backend baseline changed",
        )
        # Prefer the existing private runner's READ ONLY inspection, performed by
        # deploy-backend immediately after its approved code update and before DDL.
        revision = args.expected_db_revision
        if os.environ.get("PEACH_READONLY_DATABASE_URL"):
            require(
                asyncio.run(db_revision(aws)) == revision,
                "Private DB revision differs from approval",
            )
        verify_archive(args, state, aws)
        check_image_retention(aws, state["images"])
        check_snapshot(aws, os.environ.get("PEACH_RELEASE_SNAPSHOT_ID", ""))
        require(
            os.environ.get("PEACH_APPROVED_MIGRATION_SHA256")
            == state["source"]["schema"]["sha256"],
            "Approve the exact schema fingerprint; never auto-approve it",
        )
        env["PEACH_EXPECTED_DB_REVISION"] = revision
        subprocess.run(
            ["bash", str(ROOT / "scripts/deploy-backend.sh")], env=env, check=True
        )
        source(args.commit)
        state.update(phase="backend", new_image=image(aws, "peach-backend"))
        write(state_file(args), state)
    elif args.phase == "parser-disabled":
        require(state["phase"] == "backend", "Verified backend release required first")
        require(
            args.ai_parameters is not None, "Supply reviewed disabled AI parameters"
        )
        params = {
            p["ParameterKey"]: p["ParameterValue"]
            for p in json.loads(args.ai_parameters.read_text())
        }
        require(
            params["ImageUri"] == state["new_image"],
            "Parser must reuse the verified backend digest",
        )
        public = aws.client("lambda").get_function_configuration(
            FunctionName="peach-backend"
        )["Environment"]["Variables"]
        for param, key in (
            ("CognitoAuthority", "COGNITO_AUTHORITY"),
            ("CognitoClientId", "COGNITO_CLIENT_ID"),
            ("CognitoJwksJson", "COGNITO_JWKS_JSON"),
        ):
            require(
                params.get(param) == public[key],
                "Parser auth must match existing verified backend auth",
            )
        require(
            state["frontend"]["SiteUrl"]
            in params.get("FrontendOrigins", "").split(","),
            "Current frontend origin missing from parser CORS",
        )
        env.update(
            PEACH_APPROVE_AI_DEPLOY="yes",
            AI_PARAMETERS_FILE=str(args.ai_parameters.resolve()),
        )
        existing = stack(aws, "peach-ai", optional=True)
        env["AI_CHANGE_SET_TYPE"] = "UPDATE" if existing else "CREATE"
        subprocess.run(
            ["bash", str(ROOT / "scripts/deploy-ai.sh")], env=env, check=True
        )
        print(
            "Disabled AI change set CREATED ONLY. Review and separately approve exact execution; no activation."
        )
    elif args.phase == "execute-disabled":
        require(state["phase"] == "backend", "Verified backend release required first")
        execute_disabled(args, aws, state)
    elif args.phase == "frontend":
        require(state["phase"] == "backend", "Backend release not verified")
        receipt = json.loads((args.directory / "paid-smoke.json").read_text())
        cfg = parser_config(aws)
        check_smoke_receipt(receipt, args.commit, state, cfg)
        require(
            cfg["Environment"]["Variables"]["PARSER_ENABLED"] == "true",
            "Parser must be ready",
        )
        current_url = outputs(stack(aws, "peach-ai"))["ParserUrl"]
        require(current_url == receipt["url"], "Parser URL changed since smoke")
        env.update(
            PARSER_URL=current_url,
            FRONTEND_BUILD_ENGINE="webpack",
            BACKEND_URL=outputs(stack(aws, "peach-backend"))["ApiUrl"],
        )
        subprocess.run(
            ["bash", str(ROOT / "scripts/deploy-frontend.sh")], env=env, check=True
        )


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT / "backend"))
    try:
        main()
    except Exception as error:
        # Never print DB/provider credentials, tokens, signed URLs or raw configuration.
        if isinstance(error, Stop):
            print("STOP: " + str(error), file=sys.stderr)
        elif hasattr(error, "response") and isinstance(error.response, dict):
            detail = error.response.get("Error", {})
            print(
                "STOP: AWS "
                + detail.get("Code", "read denied")
                + "; inspect scoped permissions",
                file=sys.stderr,
            )
        else:
            print(
                f"STOP: {type(error).__name__}; no automatic retry or continuation",
                file=sys.stderr,
            )
        sys.exit(1)
