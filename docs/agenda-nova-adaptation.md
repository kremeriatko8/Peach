> **Current October 18 readiness:** [release audit](agenda-release-audit.md)
> supersedes historical access/build/test observations below. No deployment has occurred.
> The single approved minimal Nova smoke succeeded; agenda tool use and the five
> deployed test cases remain unverified. No additional inference is authorized here.

# Nova Lite local adaptation report — October 18, 2026

Implemented locally on feat/paste-agenda. No AWS resources/IAM/production data were
changed. No model was invoked, no migration run, no commit/push created. Existing
uncommitted safeguards were preserved. This is NOT instructor-approved substitution.

## Implementation

Boto3 Runtime Converse replaces AnthropicBedrockMantle for amazon.nova-lite-v1:0,
us-east-1, non-streaming. Full ParsedAgenda validation and HTTP/save contracts
remain. Tool schemas inline Pydantic refs and retain all actual fields (including
title), while removing unsupported annotations/root keys. The model must return
exactly one record_agenda tool with tool_use stop reason; one validation repair is
allowed. Both attempts' observed tokens are summed. Client credentials use SigV4,
SDK total_max_attempts=1, and combined connect/read budgets respect remaining time.
Cognito checks, request limits, disabled mode, manual fallback, review/correction
storage and ownership remain. No new database migration is needed for this switch.

The unused Anthropic dependency and its exclusively required packages were removed;
all other locked package versions stayed unchanged. Existing reporting handlers
were not edited. The outside-VPC Lambda, mandatory boundary, shared account concurrency, 512MB,
30-second timeout, output cap and warm-instance limit remain. Prices are explicit
configuration, not silent defaults; missing prices fail closed.

## Every file changed for this adaptation

Pre-existing uncommitted files that were only inspected/tested are not claimed as
new adaptation changes (for example Makefile and test_ai_cli_approval.py).

| File | Change |
|---|---|
| .env.example | Nova model and current price guidance |
| backend/app/ai/agenda.py | Converse client, schema adapter, bounded tool/repair/usage handling |
| backend/app/ai/agenda_lambda.py | Safe botocore error mapping and existing pre-inference gates |
| backend/app/ai/cli.py | Converse hello with existing explicit paid-call interlock |
| backend/app/config.py | Nova model default |
| backend/pyproject.toml | Remove unused Anthropic dependency |
| backend/uv.lock | Remove only unused dependency graph entries; no version upgrades |
| backend/tests/test_agenda_parser.py | Mocked Converse, SDK Stubber, schema/usage/retry/deadline tests |
| backend/tests/test_agenda_lambda.py | Nova cost/logging and botocore failure tests |
| backend/tests/test_agendas.py | Provider-neutral saved-suggestion fixture now uses Nova |
| infra/ai.yml | Exact Nova model/ARN, InvokeModel, enforced existing boundary |
| infra/iam/agenda/operator-readiness.json | Exact model metadata plus regional unscoped availability read |
| infra/iam/agenda/readiness-readonly.json | Same Nova metadata scopes in incremental alternative |
| infra/iam/agenda/parser-runtime-boundary.json | Exact Nova InvokeModel; own-log grants unchanged |
| infra/iam/agenda/optional-laptop-inference.json | Exact Nova InvokeModel; remains optional/unattached |
| scripts/agenda-release.py | Nova metadata/quota/model smoke gates; safe empty-budget response handling |
| scripts/validate-ai-parameters.py | Exact Nova model/ARN validation; prior disabled/auth/price gates |
| scripts/tests/test_agenda_release.py | Read-only Nova readiness gate regressions, no inference |
| scripts/tests/test_ai_parameters.py | Nova parameters and invalid-model rejection |
| scripts/tests/test_ai_infra.py | Non-streaming Runtime inference policy assertions |
| scripts/tests/test_agenda_iam.py | Boundary, exact inference ARN and regional availability scopes |
| docs/adr/0006-llm-agenda-parsing.md | Transparent decision/deviation, alternatives, cost and consequences |
| docs/agenda-ai.md | Current Nova operation, IAM, release and evidence guide |
| docs/agenda-evaluation.md | Five real Nova cases pending; explicit assignment deviation |
| docs/architecture.md | Runtime Converse/Nova parse path; save/reporting paths preserved |
| docs/agenda-guarded-release.md | Nova gates/parameters/costs; approval stages preserved |
| docs/agenda-deployment-readiness.md | Mark historical provider findings; link current guide |
| docs/agenda-implementation.md | Mark historical handoff; link current implementation |
| infra/iam/agenda/ADMIN-SESSION.md | Exact later IAM versions, scopes, attachment and approval rules |
| infra/iam/agenda/README.md | Current Nova IAM policy overview |
| docs/agenda-nova-adaptation.md | This complete report |

## Local validation

- 168 selected backend/script tests plus 63 subtests passed. This includes all script
  tests with mocked AWS and non-DB parser/Lambda/CLI tests. No real migration runner
  was invoked. New Mock/Stubber test outputs are not submission evidence.
- 93 frontend tests passed. No frontend source change was necessary.
- Backend/scripts Ruff lint and format checks passed; cfn-lint AI/budget passed;
  git diff whitespace check passed; uv frozen runtime requirements export passed.
- Public official Bedrock service authorization catalog verified InvokeModel and
  GetFoundationModel support the exact foundation ARN. GetFoundationModelAvailability
  lacks resource-level scope: Resource=* plus us-east-1 condition is required.
- All five backend handlers import on the host; missing JWT returns 401 before paid
  work. All IAM JSON documents parse and fit managed-policy size limits.
- Linux ARM64 Docker build attempted but blocked: Docker daemon is not running.
  Do not claim the Nova image has been built/verified. Database-backed/migration
  tests were intentionally not run under the no-migrations restriction.

## Exact future IAM changes — NOT APPLIED

- PeachAgendaReadiness: replace Mantle metadata actions with GetFoundationModel on
  arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-lite-v1:0; separately allow
  GetFoundationModelAvailability on Resource=* conditioned to us-east-1. All other
  permissions/resources/conditions are retained.
- PeachAgendaParserBoundary: replace Mantle CreateInference/model condition with
  bedrock:InvokeModel on that exact ARN. Retain own CloudWatch log writes. Never
  attach this as an ordinary user/group policy or broaden role provisioning.
- Future parser role inline policy, deployed only through approved infra/ai.yml,
  grants the same exact InvokeModel action. No streaming/model wildcard permission.
- Optional PeachAgendaLaptopInference: replace with exact Nova InvokeModel. Creating
  a version does not authorize attaching it or making a paid call. Existing operator
  release, role-provisioning and IAM-audit policies require no Nova changes.
- No new inference profile, Mantle project, Marketplace agreement/subscription,
  provisioned throughput, NAT, VPC endpoint or reporting permission is introduced.

## Remaining blockers and safe later order

1. Approve/reconcile only those IAM versions, then verify CLI identity/default
   documents and Nova account/region/model metadata, without inference. Prior
   positive quotas (4M TPM, 200 RPM) do not prove access. Stop on unavailable,
   denied or unexpected Amazon-model availability responses for explicit review.
2. Shared concurrency=10 is adequate for the serial lab demo; no increase needed.
   Resolve ECR any-tag last-3 expiry threatening reporting/rollback images,
   and absent $5 budget/email. No such mutation was performed or authorized here.
3. Review local diff and authorize a commit. Start Docker and verify Linux ARM64
   image/imports. Database/migration verification needs separate permission under
   the current restriction; full local-verify includes migration tests and must
   not run prematurely. Existing 0005 release fingerprint/backup gates remain.
4. After explicit release approval, preserve current frontend and API/runner/report
   digests; approve/create/verify a fresh snapshot; then approve guarded runner
   read-only revision inspection, 0005 migration and API release. Actual production
   revision remains unknown and must be checked before DDL. Do not downgrade or
   restore old data as routine rollback; retain additive 0005 and reports.
5. Approve isolated disabled parser change-set creation, review, separately execute;
   run non-billable missing-JWT/oversize/disabled smoke tests without activating.
6. Separately approve activation and one actual paid functional smoke; only then
   approve frontend publication. No local test result substitutes for a live smoke.
7. Collect the five genuine deployed test cases, <=45s recording, actual usage log,
   written evaluations and approved feature-branch commit link. Explain deviation
   from required Claude/AnthropicBedrockMantle, without claiming instructor approval.

Recommendation: local adaptation is ready for review; **NO-GO for production now**.
No inference quality, paid latency or deployed behavior has been measured.
