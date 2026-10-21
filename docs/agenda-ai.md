> **Current October 18 readiness:** [release audit](agenda-release-audit.md)
> supersedes historical access/build/test observations below. No deployment has occurred.
> The single approved minimal Nova smoke succeeded; agenda tool use and the five
> deployed test cases remain unverified. No additional inference is authorized here.

# Paste an agenda — Nova Lite implementation and release guide

Current local decision, October 18, 2026: `amazon.nova-lite-v1:0`, us-east-1,
non-streaming Bedrock Runtime Converse. No model calls or deployment were performed
for this adaptation. This substitutes the assignment's required Claude Opus 5.5;
it is a documented deviation, **not an instructor-approved substitution**.

## Configuration

Install locked dependencies with `cd backend && uv sync --frozen`. The runtime
uses existing boto3, explicit SigV4 role/profile credentials and the in-region
endpoint. The unused Anthropic SDK was removed from pyproject/lock; other locked
versions were preserved. Never pass AWS credentials to the frontend.

- PARSER_MODEL defaults to amazon.nova-lite-v1:0. Reviewed release rejects other models.
- PARSER_ENABLED=false initially. Changing it requires separate activation approval.
- PARSER_MAX_TOKENS=2048; maximum 4096; one initial call plus at most one repair.
- SDK automatic retries are disabled (total_max_attempts=1). Per-call connect/read
  timeout budgets total at most 10 seconds, reduced to the remaining parser deadline.
- PARSER_REQUESTS_PER_MINUTE=3 per subject/warm instance; no reserved concurrency for this low-traffic lab.
- PARSER_INPUT_USD_PER_MILLION=0.06 and PARSER_OUTPUT_USD_PER_MILLION=0.24 are the
  standard us-east-1 catalog rates verified October 18 (publication October 16).
  Set them explicitly after price review. Missing pricing disables HTTP parsing.
- Existing Cognito issuer/client/trusted public JWKS configuration is reused.
- PARSER_URL is injected into the deployed frontend; no browser provider access.

Only after explicit approval of the specific paid request:
`PEACH_APPROVE_PAID_INFERENCE=yes make llm-hello` or
`PEACH_APPROVE_PAID_INFERENCE=yes make parse TEXT="..."`.
CLI calls do not replace deployed-frontend submission evidence. Disabled HTTP mode
is separate from these explicitly approved CLI calls.

## Parser and API invariants

The record_agenda tool schema is derived from ParsedAgenda, references are inlined,
annotations removed, and only type/properties/required occur at the root. Pydantic
still validates the complete original contract (dates, nullability and numeric
bounds), with item-count limits. Exactly one named tool call and tool_use stop
reason are required. Validation errors are returned through Converse toolResult
for one repair; every observed attempt's tokens are summed. Failed/timeout calls
may incur unobserved usage, so logs flag incomplete usage rather than claiming free calls.

JWT verification precedes inference, input is capped at 10,000 characters, and all
source text is untrusted. The parser has no DB/VPC access or executable external
tools. Browser review/save still uses the ownership-validated existing API and
stores the original suggestion, model ID and prompt version separately from the
corrected agenda. The HTTP/DB/frontend contract is unchanged; no extra migration
is required for the provider change. Existing 0005 agenda deployment remains separately gated.

## IAM changes before any release (not applied)

1. Update PeachAgendaReadiness (or the incremental read-only proposal): exact-model
   bedrock:GetFoundationModel on the Nova foundation ARN; GetFoundationModelAvailability
   as a separate read on Resource="*", conditioned to us-east-1 (API lacks resource scope).
2. Update PeachAgendaParserBoundary's default version: replace Mantle inference
   with bedrock:InvokeModel on that exact ARN. Preserve its own-log-write grants.
   The existing boundary ARN and mandatory-boundary provisioning constraints remain.
3. The future infra/ai.yml execution-role inline policy grants the same exact
   InvokeModel permission. No live role is updated by this local work.
4. Optional laptop policy gets the same scoped permission, but remains unattached
   until separately approved. Runtime and readiness do not require operator inference.

No bedrock:InvokeModelWithResponseStream, cross-region profile, Marketplace
subscription, new project, provisioned capacity, NAT or VPC endpoint is requested.
Operator release/provisioning/IAM-audit policies otherwise retain their exact scopes.
See infra/iam/agenda/ADMIN-SESSION.md. Live AWS policies still reflect Claude until
an administrator explicitly updates only the changed policies.

## Ordered release gates

1. Confirm account 968053399627/us-east-1, metadata access and Nova regional/account
   availability without inference. These reads were previously denied; positive
   quotas alone do not establish authorization. If Amazon's availability response
   differs from the guarded predicate, STOP for review, never assume entitlement.
2. Verify in-region quotas L-70423BF8 (TPM) and L-E386A278 (RPM), currently observed
   4M/200 respectively. Do not substitute cross-region, custom-model or batch quotas.
3. Shared Lambda quota 10 is sufficient for the serial demo; no increase is needed.
   Resolve unsafe shared ECR 'any, last 3' expiry and the absent $5 budget.
   No changes to these resources are authorized by this document.
4. Review/commit local changes only after authorization; retain the completed
   relevant test results. Full local-verify is optional when comprehensive repeat
   validation is warranted and includes disposable migrations requiring approval.
5. Follow the guarded release guide: preserve all baseline API/runner/report images
   and frontend objects; separately approve fresh snapshot, guarded 0005 release,
   disabled parser change-set creation/execution, authentication/disabled smoke,
   activation, one paid functional smoke, and finally frontend publication.

AI parameter JSON must use ImageUri=verified backend digest, Architecture=arm64,
ParserModel=amazon.nova-lite-v1:0, ParserEnabled=false, exact Nova foundation ARN as
InferenceResourceArn, verified rates and existing Cognito/frontend values. Budget
creation uses infra/budget.yml with the explicitly reviewed email and remains a
separate approval. Activation uses an UPDATE change set preserving every deployed
parameter except ParserEnabled; do not enable in the initial parameter file.

## Evidence and documentation

See docs/agenda-evaluation.md for the five actual deployed cases, recording <=45s,
CloudWatch usage line and written answers. No results or instructor approval are
fabricated. ADR 0006 records the deviation and observed Claude access/zero-quota
blockers. The diagram preserves Browser→Parser→Bedrock parse and Browser→API→Aurora save.

Illustrative, not measured: 1,000 input + 300 output tokens costs $0.000132;
~2,600 such parses/month costs $0.3432 before repairs, Lambda, logs, storage and
existing application costs. A $5 budget is a delayed alert, not a cap. Cancelled
browser requests may still bill. Rollback keeps additive schema 0005 and reporting
untouched; disable parsing, restore approved baseline images/assets as needed.

References:
- https://docs.aws.amazon.com/bedrock/latest/userguide/model-card-amazon-nova-lite.html
- https://docs.aws.amazon.com/nova/latest/userguide/tool-use-definition.html
- https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html
- https://pricing.us-east-1.amazonaws.com/offers/v1.0/aws/AmazonBedrock/current/us-east-1/index.json


IAM resource-scope correction verified against the public Bedrock authorization
catalog: GetFoundationModel supports the exact foundation-model ARN, but
GetFoundationModelAvailability has no resource-level scope. Its separate statement
uses Resource="*" with aws:RequestedRegion=us-east-1. This grants only availability
metadata, never inference. Runtime/boundary/laptop InvokeModel remains exact-ARN
scoped; no model wildcard inference or streaming permission is granted.
