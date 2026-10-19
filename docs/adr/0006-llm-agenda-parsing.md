# ADR 0006: Reviewed agenda suggestions through Amazon Bedrock

Status: implemented and deployed October 19, 2026. Backend/migration0005
are released; frontend is published and agenda-v2 parser is DISABLED after the
user reported a prompt-injection failure in five real UI tests. V1 and v2
CloudWatch evidence remain separate; v2 JSON/screenshots are missing. Local v3
source checks and placeholder cleanup are documented in agenda-v3-safety.md and
are not deployed or real-model verified. Instructor acceptance of the Nova substitution remains pending.
See agenda-v2-quality.md and agenda-evaluation.md.

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
repair is allowed. PROMPT_VERSION=agenda-v2 identifies revised extraction guidance
and deterministic reference calendar; historical v1 evidence remains unchanged.

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
latency or injection resistance from mocked tests. Five real representative v1
HTTP cases exist; exact course inputs and deployed UI evidence are still incomplete.

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
rate limiting is not global. Run one parse at a time and disable parsing outside
the approved demo window. This accepts modest shared-capacity risk rather than
adding distributed limiters or paid services. Auth, ownership, validation, token
bounds, disabled mode, logging, snapshots and rollback safeguards remain unchanged.
