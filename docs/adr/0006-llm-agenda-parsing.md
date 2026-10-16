# ADR 0006: LLM agenda parsing

Status: implemented locally; AWS deployment and paid inference not performed.

## Context

Users paste multilingual meeting notes, review structured proposals, and save
corrected agendas. Source text is untrusted, potentially sensitive and may contain
prompt injection. Peach previously had meetings and generic tasks, but no agenda
API. Existing Aurora and reporting must be preserved. No NAT and low recurring
cost are constraints.

## Decision

Use configured `PARSER_MODEL=anthropic.claude-opus-5-5` in `us-east-1` through
`anthropic[bedrock]` / `AnthropicBedrockMantle`. Pin the SDK in uv.lock. A separate
512 MB/30 s container Lambda outside the VPC verifies existing Cognito access JWTs
before inference. It has no database URL, database permissions, or save behavior.
Use tool `record_agenda`, the assignment Pydantic schema, and `agenda-v1`. Validate
output and allow one repair. Missing or ambiguous fields stay null. Inference
output is advice, never trusted commands or user authorization.

The browser edits a separate copy. Explicit Save calls the owner-scoped agenda
API on the existing backend. One additive agendas table stores reviewed fields
and nullable original proposal/model/prompt metadata. Omitted provenance retains
it; explicit null supports a manual replacement. This is client-submitted
provenance, not cryptographic proof. One current proposal per meeting is retained;
regeneration replaces it on Save. Historical proposal versioning is outside scope.

## Alternatives

- Existing VPC API plus interface endpoint: fewer application boundaries, but
  recurring endpoint charges and a larger inference permission boundary. Mantle
  endpoint/service compatibility must also be checked; do not assume a
  bedrock-runtime endpoint works for Mantle.
- Direct Claude API: requires another provider credential/billing path and does
  not meet the required Bedrock integration.
- Regular expressions: low compute cost but brittle for multilingual prose,
  signatures, relative dates, and incomplete notes.

## Consequences

No new always-on networking. Costs are input/output tokens, up to two calls per
parse, Lambda duration, logs and image storage. Rates must be verified and
configured before parser activation. Logs include Cognito subject, model, prompt,
usage, latency and estimated USD; no source text, JWTs, or raw provider errors.
Unknown/failed-call usage cannot be claimed as zero billed usage. A $5 account-wide
budget alerts by email; it is not a cap. Concurrency 1 and per-warm-instance rate
limits reduce bursts but do not guarantee a monthly spending ceiling.

Client cancellation aborts fetch and discards late responses; it does not promise
cancellation of an already-running model request. Manual entry remains available
when inference is disabled, throttled, invalid or unavailable. Save and reporting
continue independently of Bedrock. Routine rollback retains additive schema 0005.
