> **Historical initial-setup commands:** source commit, ECR protection and the manual
> $5 budget are now complete. Do not repeat sections 1–3 or create peach-budget.
> Use the updated pinned command sequence under the ignored preparation archive;
> its budget/email verification uses the existing budget and performs no creation.

# First protected Agenda release — October 19, 2026

**Prepared only: no mutation below has been run.** One approval can authorize this
whole reviewed sequence through the disabled parser, including the commit, exact
ECR policy, budget/email, fresh snapshot and guarded migration/API release. Stop
on errors, unexpected revisions, changed baselines or unexpected change-set resources;
do not automatically retry. Activation/inference/frontend/push are NOT included.

Readiness: sofiia / 968053399627 / us-east-1; feat/paste-agenda. Healthy existing
API/runner/report functions, unchanged pinned digests, stable existing stacks with
no persisted service roles. AI/budget stacks absent. Shared concurrency 10; no
quota request. ECR unsafe policy and absent budget still need approved application.
Actual production revision is unknown until the approved runner inspection.

Local validation reused: 229 offline tests +63 subtests, 13 frontend agenda tests;
prior 216 PostgreSQL 17 ORM/API tests, 93 frontend tests and ARM64 image verification.
This pass: 57 focused release/template/IAM tests, Ruff/format/cfn-lint, AWS
ValidateTemplate both templates, whitespace/secret-pattern review. Docker 29.8.1,
Python 3.14.7 and AWS CLI available. No comprehensive vulnerability-scanner proof.

Live Readiness/Release/ParserProvisioning/Boundary match local documents; ECR policy
write grant exists on exact repo. Group listing/simulation restrictions mean full
SCP/effective mutation authorization is not proven. No new IAM grant is proposed;
stop on any AccessDenied and report the exact action/resource. Do not use Root.

## 1. Approved source commit and identity

Only AFTER explicit protected-release/commit approval, open Bash at repository root:
```bash
set -euo pipefail
umask 077
unset PYTHONOPTIMIZE
export AWS_PROFILE=default AWS_REGION=us-east-1 AWS_DEFAULT_REGION=us-east-1
AWS=(aws --profile default --region us-east-1 --no-cli-pager)
PY="$PWD/backend/.venv/bin/python"
[[ "$(git branch --show-current)" == feat/paste-agenda ]]
[[ "$("${AWS[@]}" sts get-caller-identity --query Arn --output text)" == \
   arn:aws:iam::968053399627:user/sofiia ]]
git diff --check
# Explicit lab paths only; no git add . and no env/artifact directories:
git add -- .env.example Makefile backend/app/ai backend/app/config.py \
  backend/pyproject.toml backend/uv.lock backend/tests/test_agenda_parser.py \
  backend/tests/test_agenda_lambda.py backend/tests/test_agendas.py \
  backend/tests/test_ai_cli_approval.py frontend/tests/agendas.test.tsx \
  docs/agenda-*.md docs/agenda-submission-template.json docs/architecture.md \
  docs/adr/0006-llm-agenda-parsing.md infra/ai.yml infra/budget.yml \
  infra/ecr/peach-backend-lifecycle.json infra/iam/agenda \
  scripts/agenda-release.py scripts/validate-ai-parameters.py \
  scripts/tests/test_agenda_release.py scripts/tests/test_ai_infra.py \
  scripts/tests/test_ai_parameters.py scripts/tests/test_agenda_iam.py
git diff --cached --check
git diff --cached --stat
# Review staged diff and untracked files before the approved commit:
git diff --cached
git status --short
git commit -m "Adapt agenda parsing to Nova Lite and prepare protected lab release"
[[ -z "$(git status --porcelain)" ]]
C=$(git rev-parse HEAD)
D="$PWD/reports-local/agenda/release-$C"
export D
R=("$PY" scripts/agenda-release.py)
"${R[@]}" plan --commit "$C" --directory "$D"
mkdir -p "$D/admin"
```
No push/merge. The pending diff is lab-related; real .env files, credentials,
build outputs and reports-local remain ignored. Pattern scan found no AWS access
keys/private keys/GitHub tokens; inspect staged content rather than treating this
as an exhaustive scanner. If unrelated changes appear, do not include them.

## 2. Apply and verify only the approved ECR policy

```bash
"${AWS[@]}" ecr get-lifecycle-policy --repository-name peach-backend \
  --query lifecyclePolicyText --output text > "$D/admin/ecr-policy-before.json"
"${AWS[@]}" ecr describe-images --repository-name peach-backend \
  --output json > "$D/admin/ecr-images-before.json"
"${AWS[@]}" ecr put-lifecycle-policy --repository-name peach-backend \
  --lifecycle-policy-text file://infra/ecr/peach-backend-lifecycle.json
"$PY" - <<'PY'
import boto3,json,os
from pathlib import Path
s=boto3.Session(profile_name='default',region_name='us-east-1')
assert s.client('sts').get_caller_identity()['Arn']=='arn:aws:iam::968053399627:user/sofiia'
e=s.client('ecr')
actual=json.loads(e.get_lifecycle_policy(repositoryName='peach-backend')['lifecyclePolicyText'])
assert actual==json.loads(Path('infra/ecr/peach-backend-lifecycle.json').read_text())
protected={
 'sha256:763c0b78eaf43c322f4692842bc70a308a4358b001c88a0b0dfc8916d1c32df6',
 'sha256:aa7c0324b1e7653782cec5c4a3bd41123ae6dfed081fd715dd25b98fdca898dc',
 'sha256:ac2d47b04a705075df2e2c09fc0106c771f423fae008d7a7df2d775541935629',
}
current={x['imageDigest']:x.get('imageTags',[]) for p in e.get_paginator('describe_images').paginate(repositoryName='peach-backend') for x in p['imageDetails']}
assert protected <= current.keys() and all(current[d] for d in protected)
print('Safe untagged-only policy and all protected tagged digests verified')
PY
```
This retains tagged images; do not remove their last tag. Neither digest pinning
nor tag immutability protects against lifecycle deletion. Keep existing MUTABLE
setting. No repo recreation, tag changes, image deletion or report changes.

## 3. Create budget through reviewed change set

```bash
read -r -s -p 'Private budget notification email: ' PEACH_BUDGET_EMAIL
printf '\n'
export PEACH_BUDGET_EMAIL
"$PY" - <<'PY'
import json,os
from pathlib import Path
p=Path(os.environ['D'])/'admin/budget-parameters.json'
p.write_text(json.dumps([{'ParameterKey':'NotificationEmail','ParameterValue':os.environ['PEACH_BUDGET_EMAIL']}]))
p.chmod(0o600)
PY
BUDGET_CS=$("${AWS[@]}" cloudformation create-change-set \
  --stack-name peach-budget --change-set-name "agenda-budget-${C:0:12}" \
  --change-set-type CREATE --template-body file://infra/budget.yml \
  --parameters "file://$D/admin/budget-parameters.json" --query Id --output text)
"${AWS[@]}" cloudformation wait change-set-create-complete \
  --stack-name peach-budget --change-set-name "$BUDGET_CS"
"${AWS[@]}" cloudformation describe-change-set \
  --stack-name peach-budget --change-set-name "$BUDGET_CS"
# Review: only MonthlyBudget / AWS::Budgets::Budget Add; no service role.
"${AWS[@]}" cloudformation execute-change-set \
  --stack-name peach-budget --change-set-name "$BUDGET_CS"
"${AWS[@]}" cloudformation wait stack-create-complete --stack-name peach-budget
"${R[@]}" preserve --commit "$C" --directory "$D" \
  --reports-profile peach-reports-deploy
```
Preserve verifies the exact $5 monthly account-wide pre-credit budget, upward actual
alert and matching email, protects ECR digests/tags, and archives coherent frontend
objects/metadata/ETags. The budget excludes credit/refund offsets, does not stop
spending, and has no actions/Reports/SNS. Its email lives only in private release
state and AWS. Keep that directory private. Quota and model checks are read-only.

## 4. Fresh encrypted manual snapshot, then guarded backend

```bash
PEACH_RELEASE_SNAPSHOT_ID="peach-pre-ownership-$(date -u +%Y%m%d-%H%M%S)-lab6"
export PEACH_RELEASE_SNAPSHOT_ID
"${AWS[@]}" rds create-db-cluster-snapshot --db-cluster-identifier peach-db \
  --db-cluster-snapshot-identifier "$PEACH_RELEASE_SNAPSHOT_ID"
"${AWS[@]}" rds wait db-cluster-snapshot-available \
  --db-cluster-snapshot-identifier "$PEACH_RELEASE_SNAPSHOT_ID"
"$PY" - <<'PY'
import importlib.util,os
spec=importlib.util.spec_from_file_location('release','scripts/agenda-release.py')
r=importlib.util.module_from_spec(spec);spec.loader.exec_module(r)
r.check_snapshot(r.session('default'),os.environ['PEACH_RELEASE_SNAPSHOT_ID'])
print('Exact cluster, encrypted/manual/available, <24h snapshot verified')
PY
"$PY" scripts/schema-release.py
# The current reviewed fingerprint below is valid only while that output matches.
export PEACH_APPROVED_MIGRATION_SHA256=90ab389e380f6437f77290af7d63f8951ddd574987c334279f1bd0950dc09707
"${R[@]}" backend --commit "$C" --directory "$D" \
  --expected-db-revision 0004 --approve "968053399627:$C:backend"
```
No direct production SQL. The approved runner image update makes inspect_revision
available; it uses a READ ONLY transaction. The migrate path checks expected 0004
again under a lock in the same transaction before additive 0005. An unexpected
revision stops before DDL/API update. Do not silently retry with expected 0005.
No RDS replacement/removal is allowed. The release verifies the exact published
ARM64 image; existing comprehensive tests need not be rerun purely due to elapsed time.

## 5. Generate exact disabled-parser parameters and deploy

```bash
"$PY" - <<'PY'
import boto3,json,os
from pathlib import Path
s=boto3.Session(profile_name='default',region_name='us-east-1')
assert s.client('sts').get_caller_identity()['Arn']=='arn:aws:iam::968053399627:user/sofiia'
d=Path(os.environ['D']);state=json.loads((d/'release.json').read_text())
f=s.client('lambda').get_function(FunctionName='peach-backend')
assert f['Code']['ResolvedImageUri']==state['new_image']
env=f['Configuration']['Environment']['Variables']
params={
 'ProjectName':'peach','Architecture':'arm64','ImageUri':state['new_image'],
 'FrontendOrigins':state['frontend']['SiteUrl'],
 'CognitoAuthority':env['COGNITO_AUTHORITY'],'CognitoClientId':env['COGNITO_CLIENT_ID'],
 'CognitoJwksJson':env['COGNITO_JWKS_JSON'],
 'ParserModel':'amazon.nova-lite-v1:0','ParserEnabled':'false',
 'InferenceResourceArn':'arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-lite-v1:0',
 'InputUsdPerMillion':'0.06','OutputUsdPerMillion':'0.24',
}
p=d/'admin/ai-parameters.json'
p.write_text(json.dumps([{'ParameterKey':k,'ParameterValue':v} for k,v in params.items()]))
p.chmod(0o600)
PY
"$PY" scripts/validate-ai-parameters.py "$D/admin/ai-parameters.json"
"${R[@]}" parser-disabled --commit "$C" --directory "$D" \
  --ai-parameters "$D/admin/ai-parameters.json" \
  --approve "968053399627:$C:parser-disabled"
```
Record returned exact change-set ARN as AI_CS. Wait/review before executing:
```bash
read -r -p 'Reviewed exact AI change-set ARN: ' AI_CS
"${AWS[@]}" cloudformation wait change-set-create-complete \
  --stack-name peach-ai --change-set-name "$AI_CS"
"${AWS[@]}" cloudformation describe-change-set \
  --stack-name peach-ai --change-set-name "$AI_CS"
"${R[@]}" execute-disabled --commit "$C" --directory "$D" \
  --change-set-id "$AI_CS" --approve "968053399627:$C:execute-disabled"
```
Expected only Role, LogGroup, Parser, Url, UrlPermission, InvokePermission. Wrapper
checks stored template, exact image, disabled parameter, no unreviewed service role,
shared concurrency and no VPC/DB. No inference is performed by deployment.

## 6. Disabled and reporting checks — stop here

Provide a short-lived Cognito ACCESS token in an existing mode-0600 private file.
Do not paste token into chat, command arguments or evidence. Then:
```bash
read -r -p 'Private mode-0600 access-token file path: ' TOKEN_FILE
"${R[@]}" smoke-disabled --commit "$C" --directory "$D" --token-file "$TOKEN_FILE"
"$PY" - <<'PY'
import boto3,json,os
from pathlib import Path
state=json.loads((Path(os.environ['D'])/'release.json').read_text())
s=boto3.Session(profile_name='peach-reports-deploy',region_name='us-east-1')
assert s.client('sts').get_caller_identity()['Account']=='968053399627'
for name in ['peach-report-builder','peach-report-mailer']:
 f=s.client('lambda').get_function(FunctionName=name)
 assert f['Code']['ResolvedImageUri']==state['images'][name]
 assert f['Configuration']['State']=='Active' and f['Configuration']['LastUpdateStatus']=='Successful'
resources=s.client('cloudformation').list_stack_resources(StackName='peach-reports')['StackResourceSummaries']
schedules=[x for x in resources if x['ResourceType']=='AWS::Scheduler::Schedule']
assert len(schedules)==1
for x in schedules:
 f=s.client('scheduler').get_schedule(Name=x['PhysicalResourceId'].rsplit('/',1)[-1],GroupName='peach-reports')
 assert f['State']=='ENABLED' and f['ScheduleExpression']=='cron(0 7 ? * MON *)'
 assert f['ScheduleExpressionTimezone']=='Europe/Kyiv'
print('Reporting images/state/schedule unchanged; no report was triggered')
PY
```
Require no-JWT 401, oversized 413 and valid-JWT disabled 503. If scope/configuration
changes or any check fails, STOP; no implicit retry, activation or inference.
Report metadata confirms isolation, not that a new report/email was generated.

## Rollback and later approval

If a phase fails, stop and review partial state. Preserve existing image/archive
files and fresh snapshot. After explicit rollback approval restore compatible old
API/frontend assets with metadata and retain additive 0005/schema marker. Keep
parser disabled and leave reports, safe lifecycle and budget alone. Do not drop
agendas, delete objects/images/backups, or restore old DB data automatically.

Later separate approval covers activation, one functional parse (at most two model
calls), frontend publication and five real UI inputs/evidence. No laptop grant is
needed. The prior OK smoke is not agenda-quality evidence. Nova is a documented,
not instructor-approved deviation from required Claude. No push/main merge is
included in this protected release; authorize feature-branch push separately.
