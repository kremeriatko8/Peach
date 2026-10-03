"""Run deployment orchestration with fake executables: no AWS, Docker, or HTTP calls."""

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


class DeploymentTests(unittest.TestCase):
    def run_deployment(self, scenario, mode=None):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "scripts").mkdir()
            for name in (
                "deploy-backend.sh",
                "backend-preflight.py",
                "check-backend-changeset.py",
            ):
                shutil.copy(ROOT / "scripts" / name, root / "scripts")
            (root / "backend/migrations/versions").mkdir(parents=True)
            shutil.copytree(
                ROOT / "backend/migrations/versions",
                root / "backend/migrations/versions",
                dirs_exist_ok=True,
            )
            (root / "infra").mkdir()
            shutil.copy(ROOT / "infra/backend.yaml", root / "infra")
            shutil.copy(ROOT / "infra/migrations.yaml", root / "infra")
            # Synthetic configuration only. Never load the real repository .env.
            (root / ".env").write_text(
                "PROJECT_NAME=peach\nAWS_VPC_ID=vpc-test\nAWS_SUBNET_IDS=subnet-a,subnet-b\nIMAGE_TAG=test\nPEACH_RELEASE_SNAPSHOT_ID=test-snapshot\nGOOGLE_CLIENT_SECRET=test-only-never-in-build\n"
            )
            bin_dir = root / "bin"
            bin_dir.mkdir()

            def executable(name, source):
                path = bin_dir / name
                path.write_text("#!" + sys.executable + "\n" + source)
                path.chmod(0o755)

            executable(
                "aws",
                r"""import json,os,sys
from datetime import datetime, timezone
from pathlib import Path
args=sys.argv[1:]
scenario=os.environ['SCENARIO']
def value(name): return args[args.index(name)+1] if name in args else ''
with open(os.environ['EVENTS'],'a') as file:
    file.write(json.dumps({'command':args[:2],'stack':value('--stack-name'),'function':value('--function-name')})+'\n')
if args[:2]==['sts','get-caller-identity']:
    print('test-account' if value('--query')=='Account' else 'test-caller')
elif args[:2]==['cloudformation','describe-stack-resource']:
    print(json.dumps({'StackResourceDetail':{'PhysicalResourceId':'peach-db'}}))
elif args[:2]==['rds','describe-db-clusters']:
    print(json.dumps({'DBClusters':[{'Status':'available','Endpoint':'db'}]}))
elif args[:2]==['rds','describe-db-cluster-snapshots']:
    print(json.dumps({'DBClusterSnapshots':[{'DBClusterIdentifier':'wrong' if scenario=='wrong-snapshot' else 'peach-db','Status':'available','SnapshotType':'manual','SnapshotCreateTime':datetime.now(timezone.utc).isoformat()}]}))
elif args[:2]==['cloudformation','describe-stacks']:
    query=value('--query'); stack=value('--stack-name')
    if query=='Stacks[0].Outputs': print('[]')
    elif query=='Stacks[0].Parameters': print(json.dumps([{'ParameterKey':k,'ParameterValue':v} for k,v in {'ProjectName':'peach','VpcId':'vpc-test','SubnetIds':'subnet-a,subnet-b','DbName':'peach','DbUsername':'peach','DbEngineVersion':'17.4'}.items()]))
    elif 'FunctionName' in query: print('None' if scenario=='missing-stack' else ('peach-migrations' if stack=='peach-migrations' else 'peach-backend'))
    elif 'DatabaseUrlSecretArn' in query: print('test-secret')
    elif 'ApiUrl' in query: print('https://test.invalid')
    elif not query:
        values={'ProjectName':'peach','VpcId':'vpc-test','SubnetIds':'subnet-a,subnet-b','DbName':'peach','DbUsername':'peach','DbEngineVersion':'17.4','AppEnv':'production','LogLevel':'info','CorsOrigins':'https://test.invalid'}
        if scenario=='network-mismatch': values['VpcId']='vpc-wrong'
        if scenario=='missing-env': values.pop('CorsOrigins')
        print(json.dumps({'Stacks':[{'StackStatus':'UPDATE_COMPLETE','Parameters':[{'ParameterKey':k,'ParameterValue':v} for k,v in values.items()], 'Outputs':[] if scenario=='missing-secret' else [{'OutputKey':'DatabaseUrlSecretArn','OutputValue':'test-secret'}]}]}))
    else: print('test-output')
elif args[:2] in (['cloudformation','deploy'], ['cloudformation','create-change-set']):
    if value('--stack-name')=='peach-migrations' and scenario=='runner-failure': sys.exit(1)
    params=json.loads(Path((value('--parameter-overrides') or value('--parameters')).removeprefix('file://')).read_text())
    with open(os.environ['PARAMS'],'a') as file: file.write(json.dumps({'stack':value('--stack-name'),'params':params})+'\n')
elif args[:2]==['cloudformation','describe-change-set']:
    print(json.dumps({'Status':'CREATE_COMPLETE','ExecutionStatus':'AVAILABLE','ChangeSetId':'test-change-set','Changes':[{'ResourceChange':{'ResourceType':'AWS::RDS::DBCluster' if scenario=='replace-db' else 'AWS::Lambda::Function','Action':'Modify','Replacement':'True' if scenario=='replace-db' else 'False'}}]}))
elif args[:2]==['lambda','get-function-configuration']:
    print(json.dumps({'Role':'' if scenario=='missing-role' else 'test-existing-role','VpcConfig':{'VpcId':'vpc-test','SubnetIds':['subnet-a','subnet-b'],'SecurityGroupIds':['sg-existing']},'Environment':{'Variables':{'DATABASE_URL':'postgresql+asyncpg://peach:@db/peach' if scenario=='empty-password' else 'postgresql+asyncpg://peach:synthetic@db/peach'}}}))
elif args[:2]==['lambda','invoke']:
    Path(args[-1]).write_text(json.dumps({'status':'failed' if scenario=='bad-result' else 'ok','migrated_to':'0002' if scenario=='wrong-head' else '0003','verification':{'owner_column':True,'ownership_index':scenario!='bad-verification','rows_preserved':True,'ownership_preserved':True,'rows_before':14,'rows_after':14}}))
    print('Unhandled' if scenario=='migration-failure' else 'None')
elif args[:2]==['secretsmanager','get-secret-value']:
    if scenario=='secret-read-failure': sys.exit(1)
    print(json.dumps({'SecretString':'postgresql+asyncpg://peach:@db/peach' if scenario=='empty-password' else 'postgresql+asyncpg://peach:synthetic@db/peach'}))
elif args[:2]==['ecr','describe-images']: print('sha256:testdigest')
elif args[:2]==['ecr','get-login-password']: print('synthetic')
""",
            )
            executable(
                "docker",
                "import os,sys\nassert 'GOOGLE_CLIENT_SECRET' not in os.environ\nif len(sys.argv)>1 and sys.argv[1]=='login': sys.stdin.read()\n",
            )
            executable("curl", "import sys\nsys.exit(0)\n")
            executable(
                "python3",
                "import json,os,sys\nif len(sys.argv)>1 and sys.argv[1].endswith('cognito-snapshot.py'):\n assert 'GOOGLE_CLIENT_SECRET' not in os.environ\n sys.stdin.read()\n print(json.dumps({'COGNITO_AUTHORITY':'https://cognito-idp.us-east-1.amazonaws.com/us-east-1_TEST','COGNITO_CLIENT_ID':'testclient','COGNITO_JWKS_JSON':'x'*5000 if os.environ['SCENARIO']=='oversized-env' else '{\"keys\":[]}'}))\nelse: os.execv("
                + repr(sys.executable)
                + ", ["
                + repr(sys.executable)
                + "]+sys.argv[1:])\n",
            )
            events = root / "events"
            params = root / "params"
            env = {
                "PATH": str(bin_dir) + os.pathsep + os.environ["PATH"],
                "SCENARIO": scenario,
                "EVENTS": str(events),
                "PARAMS": str(params),
                "HOME": str(root),
            }
            result = subprocess.run(
                ["bash", str(root / "scripts/deploy-backend.sh")]
                + ([mode] if mode else []),
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertTrue(events.exists(), result.stderr)
            commands = [json.loads(line) for line in events.read_text().splitlines()]
            parameters = (
                [json.loads(line) for line in params.read_text().splitlines()]
                if params.exists()
                else []
            )
            self.assertNotIn("test-only-never-in-build", result.stdout + result.stderr)
            return result, commands, parameters

    def test_success_runs_migration_before_public_update(self):
        result, commands, params = self.run_deployment("success")
        self.assertEqual(result.returncode, 0, result.stderr)
        runner = next(
            i
            for i, c in enumerate(commands)
            if c["command"] == ["cloudformation", "deploy"]
            and c["stack"] == "peach-migrations"
        )
        invoke = next(
            i for i, c in enumerate(commands) if c["command"] == ["lambda", "invoke"]
        )
        public = next(
            i
            for i, c in enumerate(commands)
            if c["command"] == ["cloudformation", "execute-change-set"]
            and c["stack"] == "peach-backend"
        )
        self.assertLess(runner, invoke)
        self.assertLess(invoke, public)
        self.assertEqual(commands[invoke]["function"], "peach-migrations")
        values = {
            p["stack"]: {
                item["ParameterKey"]: item["ParameterValue"] for item in p["params"]
            }
            for p in params
        }
        self.assertEqual(
            values["peach-migrations"]["ImageUri"], values["peach-backend"]["ImageUri"]
        )
        self.assertIn("@sha256:", values["peach-backend"]["ImageUri"])
        self.assertEqual(
            values["peach-migrations"]["ExecutionRoleArn"], "test-existing-role"
        )
        self.assertEqual(values["peach-migrations"]["SecurityGroupIds"], "sg-existing")
        self.assertIn("CognitoJwksJson", values["peach-backend"])

    def test_failures_never_update_public_backend(self):
        for scenario in (
            "runner-failure",
            "migration-failure",
            "bad-result",
            "wrong-head",
            "bad-verification",
            "replace-db",
            "missing-secret",
            "secret-read-failure",
            "missing-stack",
            "missing-env",
            "missing-role",
            "empty-password",
            "network-mismatch",
            "wrong-snapshot",
            "oversized-env",
        ):
            with self.subTest(scenario=scenario):
                result, commands, _ = self.run_deployment(scenario)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(
                    any(
                        c["command"] == ["cloudformation", "execute-change-set"]
                        and c["stack"] == "peach-backend"
                        for c in commands
                    )
                )

    def test_preparation_is_read_only_and_does_not_require_snapshot(self):
        result, commands, params = self.run_deployment(
            "wrong-snapshot", "--preflight-only"
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(params, [])
        self.assertTrue(
            all(
                command["command"][1].startswith(("describe", "get", "validate"))
                for command in commands
            )
        )

    def test_preflight_failures_never_invoke_migration(self):
        for scenario in (
            "missing-secret",
            "secret-read-failure",
            "missing-stack",
            "missing-env",
            "missing-role",
            "empty-password",
            "network-mismatch",
            "wrong-snapshot",
            "oversized-env",
            "replace-db",
        ):
            with self.subTest(scenario=scenario):
                result, commands, _ = self.run_deployment(scenario)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(
                    any(c["command"] == ["lambda", "invoke"] for c in commands)
                )
                self.assertNotIn("generating the database password", result.stdout)

    def test_snapshot_uses_trusted_url_and_strips_nonpublic_fields(self):
        spec = importlib.util.spec_from_file_location(
            "snapshot", ROOT / "scripts/cognito-snapshot.py"
        )
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        urls = []

        def fetch(url):
            urls.append(url)
            return {
                "keys": [
                    {
                        "kid": "key",
                        "kty": "RSA",
                        "alg": "RS256",
                        "use": "sig",
                        "n": __import__("base64")
                        .urlsafe_b64encode(((1 << 2047) + 1).to_bytes(256, "big"))
                        .decode()
                        .rstrip("="),
                        "e": "AQAB",
                        "d": "must-not-propagate",
                    }
                ]
            }

        outputs = [
            {
                "OutputKey": "Authority",
                "OutputValue": "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_TEST",
            },
            {"OutputKey": "UserPoolClientId", "OutputValue": "testclient"},
        ]
        config = module.configuration(outputs, fetch)
        self.assertEqual(
            urls,
            [
                "https://cognito-idp.us-east-1.amazonaws.com/us-east-1_TEST/.well-known/jwks.json"
            ],
        )
        self.assertNotIn("must-not-propagate", config["COGNITO_JWKS_JSON"])
        outputs[0]["OutputValue"] = "https://untrusted.invalid"
        with self.assertRaises(ValueError):
            module.configuration(outputs, fetch)
        self.assertEqual(len(urls), 1)


if __name__ == "__main__":
    unittest.main()
