# ADR 0006: Reviewed agenda suggestions through Amazon Bedrock

Status: implemented and deployed. As verified October 21, 2026, backend/migration0005,
frontend and agenda-v3 are released; parser is enabled. The user reports a successful
24-second correction-and-Save demo. Real v3 success telemetry exists; earlier provider
errors and unknown failed-call costs remain unresolved. V2's live injection failed;
v3's matching live injection result and v2 actual JSON are missing. Instructor acceptance
of Nova remains pending. See agenda-evaluation.md and submission/lab6/README.md.

## Context

The assignment explicitly requires Claude Opus 5.5 through AnthropicBedrockMantle.
Read-only AWS checks in account 968053399627/us-east-1 returned that model's status
as unavailable for the account, directing access inquiries to AWS Sales. Its Mantle
input/output quotas were zero. Other tested Mantle Claude models also reported
unavailable; Runtime Claude account metadata checks were denied, not proof that
all Runtime Claude models are unavailable.

The user selected Amazon Nova Lite rather than waiting for external access approval.
This is a transparent deviation from the model/client requirement, **not an
instructor-approved substitution**. The submission must state this explicitly.

Pasted external text is untrusted and potentially sensitive. AI must only suggest;
users review and save via existing validated ownership-isolated APIs. Existing
meetings, Aurora and weekly reporting must remain working. No NAT or new paid
network endpoints/always-on inference capacity are acceptable.

## Decision

Use amazon.nova-lite-v1:0 through non-streaming boto3 Bedrock Runtime Converse in
us-east-1, directly in-region, with record_agenda tool use and full Pydantic
validation. Derive the tool hint from that schema, inline references and strip
unsupported root annotations. One exact named tool invocation is required; one
repair is allowed. PROMPT_VERSION=agenda-v3 identifies current conservative source checks in addition
to extraction guidance and reference calendar; historical v1/v2 evidence stays separate.

Keep the separate 512MB/30s parser Lambda outside VPC, disabled initially. Explicit
SigV4 role credentials, exact-model InvokeModel grant, administrator-owned mandatory
permissions boundary, shared account concurrency, warm-instance request limit, 10K input
limit, bounded output, deadline and no automatic SDK retry constrain usage. JWT
verification happens before paid work. No DB credentials/access or external tool
execution is added. Save stays Browser→existing API→Aurora and preserves original
suggestions alongside human corrections. AbortController does not promise provider cancellation.

## Alternatives considered

- Required Claude/Mantle: closest assignment fit but observed account unavailability
  and zero quotas would require external AWS approval; not silently treated as accessible.
- Runtime Claude: positive quotas for some models, but account entitlement was not
  readable. Could preserve Claude with a client change, subject to later access review.
- Bedrock from existing API via paid VPC interface endpoint: introduces recurring
  costs and database-connected AI execution; separate outside-VPC parser is preferred.
- Direct Claude API: different credentials, billing and provider dependency, and
  would still deviate from the required Bedrock workflow.
- Regular expressions: poor fit for multilingual prose, relative dates and ambiguity.
- Nova cross-region/provisioned/custom inference: unnecessary broader permissions,
  routing or fixed commitments for this lab. Use the base in-region on-demand model.

## Consequences

AWS public us-east-1 price catalog checked October 18 (publication October 16)
lists standard Nova Lite input/output at $0.06/$0.24 per million tokens. Configure
rates explicitly; unknown pricing disables HTTP parsing. Example 1K input/300 output
is $0.000132, not a measurement; 2,600/month is $0.3432 before repairs and other
services. Up to two attempts can bill. No reserved/provisioned concurrency or fixed
inference commitment is necessary. $5 budget notifications are
alerts, not hard caps. New pricing/provider logic must pass offline tests first.

Log model, prompt version, invocation identifier, attempt/repair counts, per-attempt
and aggregate observed token usage, latency, safe outcomes and estimated cost;
never raw source, JWTs, database URLs or raw provider exceptions. Flag incomplete
usage on errors. Preserve manual entry when disabled/unavailable and keep save
independent of inference. Do not claim Nova's extraction quality, Ukrainian handling,
latency or injection resistance from mocked tests. Five representative v1 HTTP cases have actual JSON. Five v2 course-category UI cases
have reported outcomes and telemetry but missing actual JSON. Successful ordinary v3
parses do not establish full quality or security regression coverage.

Nova is ACTIVE and AUTHORIZED in this account/region; on-demand quotas are
4,000,000 tokens/minute and 200 requests/minute. The temporary laptop inference
policy was detached after the approved smoke and verified unattached. Existing Lambda concurrency, shared ECR retention,
budget, fresh backup and guarded migration prerequisites remain independent gates.
No live IAM/resources were changed by the original provider adaptation itself.
Migration0005 was subsequently approved and released. No further migration is
required for v2 or the frontend.

## University lab simplification

Omit reserved concurrency. The account's shared concurrency of 10 is sufficient
for a serial demonstration, so no quota increase is requested. Authenticated burst
traffic could consume this shared pool and throttle the API/reports; warm-instance
rate limiting is not global. Run one parse at a time. The user requested leaving parsing available for instructor
testing subject to successful verification and a final decision; current state is enabled,
not automatic shutdown. The $5 budget is an alert and warm-instance limits are not global. This accepts modest shared-capacity risk rather than
adding distributed limiters or paid services. Auth, ownership, validation, token
bounds, disabled mode, logging, snapshots and rollback safeguards remain unchanged.
