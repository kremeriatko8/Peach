#!/usr/bin/env python3
"""Read-only release preflight; write sensitive parameters only to private files."""

import json
import os
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import unquote, urlsplit


def aws(*args):
    return json.loads(
        subprocess.check_output(["aws", *args, "--output", "json", "--no-cli-pager"])
    )


def environment_size(values):
    if not all(isinstance(value, str) and value for value in values.values()):
        raise ValueError("Required Lambda environment value missing")
    if (
        sum(len(key.encode()) + len(value.encode()) for key, value in values.items())
        > 4096
    ):
        raise ValueError("Complete Lambda environment exceeds 4096 bytes")


def snapshot(cluster_id, snapshot_id):
    if not snapshot_id:
        raise ValueError(
            "PEACH_RELEASE_SNAPSHOT_ID required: create and verify an explicit pre-release snapshot"
        )
    data = aws(
        "rds",
        "describe-db-cluster-snapshots",
        "--db-cluster-snapshot-identifier",
        snapshot_id,
    )["DBClusterSnapshots"]
    if len(data) != 1:
        raise ValueError("Expected exactly one release snapshot")
    item = data[0]
    created = datetime.fromisoformat(item["SnapshotCreateTime"].replace("Z", "+00:00"))
    if (
        item["DBClusterIdentifier"] != cluster_id
        or item["Status"] != "available"
        or item["SnapshotType"] != "manual"
        or created < datetime.now(timezone.utc) - timedelta(hours=24)
    ):
        raise ValueError(
            "Release snapshot must be available, manual, less than 24 hours old, and belong to the existing cluster"
        )


def prepare(stack_name, function, auth, params_path, runner_path, check_snapshot=True):
    stack = aws("cloudformation", "describe-stacks", "--stack-name", stack_name)[
        "Stacks"
    ][0]
    if stack["StackStatus"] not in (
        "CREATE_COMPLETE",
        "UPDATE_COMPLETE",
        "UPDATE_ROLLBACK_COMPLETE",
    ):
        raise ValueError("Backend stack is not stable")
    previous = {
        item["ParameterKey"]: item["ParameterValue"] for item in stack["Parameters"]
    }
    outputs = {item["OutputKey"]: item["OutputValue"] for item in stack["Outputs"]}
    reference = outputs.get("DatabaseUrlSecretArn")
    if not reference or reference == "None":
        raise ValueError(
            "Existing database secret reference missing; refusing password generation"
        )
    secret = aws("secretsmanager", "get-secret-value", "--secret-id", reference)[
        "SecretString"
    ]
    config = aws("lambda", "get-function-configuration", "--function-name", function)
    database_url = config["Environment"]["Variables"]["DATABASE_URL"]
    if secret != database_url:
        raise ValueError(
            "Existing database secret does not match public Lambda configuration"
        )
    url = urlsplit(database_url)
    password = unquote(url.password or "")
    if not password:
        raise ValueError(
            "Existing database password empty; refusing password generation"
        )
    cluster_id = aws(
        "cloudformation",
        "describe-stack-resource",
        "--stack-name",
        stack_name,
        "--logical-resource-id",
        "DbCluster",
    )["StackResourceDetail"]["PhysicalResourceId"]
    cluster = aws("rds", "describe-db-clusters", "--db-cluster-identifier", cluster_id)[
        "DBClusters"
    ][0]
    if (
        cluster["Status"] != "available"
        or url.hostname != cluster["Endpoint"]
        or unquote(url.username or "") != previous["DbUsername"]
        or url.path.lstrip("/") != previous["DbName"]
    ):
        raise ValueError("Existing database identity/configuration mismatch")
    if check_snapshot:
        snapshot(cluster_id, os.environ.get("PEACH_RELEASE_SNAPSHOT_ID", ""))
    overrides = {
        "ProjectName": os.environ.get("PROJECT_NAME", "peach"),
        "VpcId": os.environ.get("AWS_VPC_ID", ""),
        "SubnetIds": os.environ.get("AWS_SUBNET_IDS", ""),
        "DbName": os.environ.get("DB_NAME") or os.environ.get("POSTGRES_DB", ""),
        "DbUsername": os.environ.get("DB_USERNAME")
        or os.environ.get("POSTGRES_USER", ""),
        "DbEngineVersion": os.environ.get("DB_ENGINE_VERSION", ""),
    }
    for key, requested in overrides.items():
        actual = previous.get(key)
        if not actual:
            raise ValueError("Missing existing database/network parameter: " + key)
        matches = (
            set(requested.split(",")) == set(actual.split(","))
            if key == "SubnetIds"
            else requested == actual
        )
        if requested and not matches:
            raise ValueError("Refusing database/network change: " + key)
    vpc = config["VpcConfig"]
    if (
        vpc["VpcId"] != previous["VpcId"]
        or set(vpc["SubnetIds"]) != set(previous["SubnetIds"].split(","))
        or not vpc["SecurityGroupIds"]
        or not config.get("Role")
    ):
        raise ValueError("Migration runner network/role configuration mismatch")
    for key, selector in {
        "AppEnv": "APP_ENV_AWS",
        "LogLevel": "LOG_LEVEL",
        "CorsOrigins": "API_CORS_ORIGINS",
        "MemorySize": "LAMBDA_MEMORY_SIZE",
        "TimeoutSeconds": "LAMBDA_TIMEOUT_SECONDS",
    }.items():
        if os.environ.get(selector):
            previous[key] = os.environ[selector]
    previous.update(
        DbPassword=password,
        Architecture=os.environ["CFN_ARCHITECTURE"],
        CognitoAuthority=auth["COGNITO_AUTHORITY"],
        CognitoClientId=auth["COGNITO_CLIENT_ID"],
        CognitoJwksJson=auth["COGNITO_JWKS_JSON"],
    )
    environment_size(
        {
            **auth,
            "DATABASE_URL": database_url,
            "DB_POOLING": "false",
            "APP_ENV": previous["AppEnv"],
            "LOG_LEVEL": previous["LogLevel"],
            "CORS_ORIGINS": previous["CorsOrigins"],
        }
    )
    runner = {
        "ProjectName": previous["ProjectName"],
        "Architecture": previous["Architecture"],
        "ExecutionRoleArn": config["Role"],
        "SubnetIds": ",".join(vpc["SubnetIds"]),
        "SecurityGroupIds": ",".join(vpc["SecurityGroupIds"]),
        "DatabaseUrl": database_url,
    }
    environment_size(
        {"DATABASE_URL": database_url, "DB_POOLING": "false", "APP_ENV": "production"}
    )
    for path, values in ((params_path, previous), (runner_path, runner)):
        with open(path, "w") as file:
            json.dump(
                [
                    {"ParameterKey": key, "ParameterValue": value}
                    for key, value in values.items()
                ],
                file,
            )


if __name__ == "__main__":
    try:
        with open(sys.argv[3]) as file:
            auth = json.load(file)
        prepare(
            sys.argv[1],
            sys.argv[2],
            auth,
            sys.argv[4],
            sys.argv[5],
            check_snapshot=sys.argv[6] != "preparation",
        )
    except ValueError as error:
        sys.exit(
            "Production preflight failed: " + str(error) + "; no migration invoked"
        )
    except Exception:
        # Never include credential-bearing values or SDK exception bodies.
        sys.exit(
            "Production preflight failed: check snapshot, existing credentials, stack/database/network and environment configuration. No migration was invoked."
        )
