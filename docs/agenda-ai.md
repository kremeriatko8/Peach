# Paste an agenda — implementation and release guide

Status: local implementation. No live inference, deployment, production migration,
budget mutation, or deployed UI verification has been performed by this work.

## Configuration and local commands

Install with `cd backend && uv sync --frozen`. `anthropic[bedrock]` is locked in
`uv.lock`. No AWS credentials belong in frontend configuration. Backend Settings
reads `.env` relative to the command working directory; export parser settings
explicitly or supply backend/.env locally. Do not copy production DB URLs to tests.

- `PARSER_MODEL`: defaults to `anthropic.claude-opus-5-5`.
- `PARSER_ENABLED`: false by default; only the HTTP adapter uses this kill switch.
- `PARSER_MAX_TOKENS`: 2048 default, maximum 4096 per attempt.
- `PARSER_REQUESTS_PER_MINUTE`: 3 per subject per warm execution environment.
- `PARSER_INPUT_USD_PER_MILLION`, `PARSER_OUTPUT_USD_PER_MILLION`: positive verified
  regional rates. Missing pricing disables HTTP inference; never use fake rates.
- `COGNITO_AUTHORITY`, `COGNITO_CLIENT_ID`, `COGNITO_JWKS_JSON`: existing public
  verifier configuration. Signing-key rotation needs redeployment.
- `NEXT_PUBLIC_PARSER_URL`: local frontend parser URL.
- `PARSER_URL`: parser URL injected as NEXT_PUBLIC_PARSER_URL by frontend deployment.

After explicit paid-call authorization only:

```sh
make llm-hello
make parse TEXT="Pricing sync; Олена reviews Pro pricing for 15 minutes"
# Explicit reproducible context:
cd backend
TEXT="next Tuesday after lunch" uv run python -m app.ai.cli parse --today 2026-10-12 --tz Europe/Kyiv
```

These commands intentionally use the laptop AWS credential chain and incur model
cost. They do not enable the HTTP parser or write to a database. TEXT is exported
by make, not expanded as shell source. Avoid entering private text into history.

## Data and review behavior

GET/PUT `/api/v1/meetings/{id}/agenda` use existing verified-sub ownership.
GET returns null for an owned meeting with no agenda; another user's meeting is
404. PUT validates nested fields and optional reviewed meeting updates and commits
atomically. A meeting row lock serializes agenda upserts. Deleting a meeting
cascades to its agenda. Existing meeting/task columns and reporting are unchanged.

One current agenda stores item/action arrays, language, and nullable ai_suggestion
with original ParsedAgenda, model, prompt_version. Ordinary edits retain original
provenance. A new accepted parse replaces the current proposal on Save. Source
text is not persisted. Provenance passes through the browser and is not a signed
provider receipt. Treat it as research data, not a security audit trail.

The form keeps uncertain dates blank and requires an offset-bearing timestamp
before optional meeting updates. Parsed names never resolve account access.
Agenda action items do not automatically create tasks. Per-field AI markers clear
when edited. Parse replaces the unsaved editor draft; saved data changes only on
Save. Cancel/close/account changes abort browser work and suppress late results.

## Offline verification

Use a disposable local PostgreSQL database ending `_test`; never production.
Run backend pytest, scripts/tests, Ruff, frontend tests/lint/format/types, and
`make ai-validate` where cfn-lint is installed. Backend CI continues normal
validation without AWS credentials. Infrastructure tests reject VPC/DB/network
resources in the AI template. Paid calls are not part of test execution.

## Approval gates and deployment commands (NOT EXECUTED)

1. Review code/tests and final schema fingerprint. Check live baseline only after
   AWS access is approved: existing stack identity, networking, revision, image
   digests, report configuration and rollback artifacts. No automatic role expansion.
2. Verify account access to the exact model in us-east-1, Mantle tool support,
   quotas, current regional pricing and minimum scoped Mantle IAM. SDK uses the
   Lambda role credential chain; do not inject bearer API keys. Required runtime
   action is `bedrock-mantle:CreateInference` on the verified existing default Mantle project ARN, with a model condition.
   Do not guess its ARN or add wildcard/project permissions without review.
3. Review/create account-wide budget separately. Confirm email and no duplicate
   budget. Billing permissions: budgets:ViewBudget, budgets:CreateBudget and, for
   an intentional update, budgets:ModifyBudget as applicable to the deployer.
   Review effective CloudFormation execution permissions before deploying.

   ```sh
   aws cloudformation deploy --region us-east-1 --stack-name peach-budget \
     --template-file infra/budget.yml --parameter-overrides NotificationEmail=REVIEWED_EMAIL
   ```

4. Approve controlled backend schema release: fingerprint approval and verified
   fresh manual snapshot as documented in deployment.md. Preserve credentials,
   existing RDS and reporting resources. Backend release publishes a reviewed
   digest containing all handlers, then private runner verifies 0005 before API
   update. Do not push main merely to publish an image; main triggers production.
   Use the existing reviewed release process only with explicit approval.
5. Prepare AI parameter JSON entries with ParameterKey/ParameterValue for:
   ImageUri (exact same reviewed backend digest), Architecture, public Cognito
   settings, FrontendOrigins (exact HTTPS origin), InferenceResourceArn,
   InputUsdPerMillion, OutputUsdPerMillion, ParserEnabled=false, optional
   ProjectName/ParserModel. Keep the parser disabled initially.

   ```sh
   PEACH_APPROVE_AI_DEPLOY=yes AI_PARAMETERS_FILE=/private/tmp/ai-parameters.json make ai-prepare-deploy
   aws cloudformation describe-change-set --region us-east-1 --stack-name peach-ai --change-set-name agenda-parser-reviewed
   # Separate approval: execute the exact reviewed change set
   aws cloudformation execute-change-set --region us-east-1 --stack-name peach-ai --change-set-name agenda-parser-reviewed
   ```

   The helper creates a change set only. For an existing stack explicitly set
   AI_CHANGE_SET_TYPE=UPDATE and a unique AI_CHANGE_SET_NAME. Deployer needs scoped
   CloudFormation, Lambda/Function URL permissions, IAM role creation/policies/
   PassRole, logs and existing ECR image access. Verify account concurrency permits
   reserved concurrency 1. No VPC, RDS, Secrets Manager or reporting permissions
   belong in the parser role. Template ARN scope is intentionally fail-closed until
   a supported Mantle inference resource is verified.
6. After separate paid-call/activation approval, create/review an UPDATE change set
   with ParserEnabled=true and otherwise preserved parameters. Execute it, then
   verify 401 without a token and 413 before inference; run one approved sample.
7. Set PARSER_URL to reviewed HTTPS parser URL and deploy static frontend through
   the existing manual process. Verify API + parser CORS origins and Cognito flow.
8. Execute the five deployed cases and record actual evidence. Keep reporting
   schedule, queues, objects, roles and pinned report images unchanged.

## Rollback and risks

Disable parser with an approved CloudFormation parameter update; retain stack and
logs for investigation. Revert frontend/API to reviewed compatible image/assets,
preserving schema marker and 0005. Never downgrade/drop agendas or meetings as a
routine rollback. No destructive stack commands are needed.

The 30 s Lambda budget allows two <=10 s calls with no automatic SDK retries.
Opus may exceed that budget; measure actual latency before activation. Inference
can still be billed when a response is lost. Failed-call logs mark usage incomplete;
zero observed tokens is not proof of no charge. CORS is not authentication.
Warm-instance rate limits reset on cold starts and are not globally enforceable.
Budget is delayed alerting, not a hard cap. No paid WAF, NAT, provisioned throughput,
interface endpoint or additional database is introduced. CloudWatch has seven-day
retention. Do not enable paid CloudTrail inference data events just for evidence.

Cost formula: `(input_tokens * input_rate + output_tokens * output_rate) / 1e6`,
summed over both attempts. Record the model/rate/date used. 20 organizations × 30
weekly × 52/12 = about 2,600 parses/month. Multiply observed mean cost by 2,600;
include Lambda/log costs separately. The assignment's $7.30/month endpoint equals
$0.00280769 per parse at that volume; that endpoint cost would be in addition to
inference, not a substitute for it.

Public IAM reference checked during implementation:
https://docs.aws.amazon.com/service-authorization/latest/reference/list_bedrock-mantle.html
CreateInference scopes to project resources, with bedrock-mantle:Model conditions.
The current client uses project/default, and the template intentionally permits only
that ARN. Custom projects require an explicitly reviewed client/header change.
Provide the existing/default project ARN after approved account inspection. Do not
create a paid project/service or broaden to all resources merely to bypass denial.

Approved activation command (NOT EXECUTED): prepare a full reviewed parameter file
preserving the deployed values and setting ParserEnabled=true, then:

```sh
aws cloudformation create-change-set --region us-east-1 --stack-name peach-ai \
  --change-set-name agenda-parser-activation --change-set-type UPDATE \
  --use-previous-template --parameters file:///private/tmp/ai-activation-parameters.json \
  --capabilities CAPABILITY_IAM
aws cloudformation describe-change-set --region us-east-1 --stack-name peach-ai \
  --change-set-name agenda-parser-activation
# Execute only after explicit review/approval:
aws cloudformation execute-change-set --region us-east-1 --stack-name peach-ai \
  --change-set-name agenda-parser-activation
```

Default Next.js/Turbopack build encountered an environment worker-port restriction
in this session. Static export was verified with `NEXT_OUTPUT=export pnpm exec next
build --webpack`. For an approved frontend deployment use
`FRONTEND_BUILD_ENGINE=webpack make deploy-frontend`; default remains Turbopack.
