# Agenda v2: local quality and telemetry changes

Local improvement only, not a deployment or new model-quality result. Production
was last left disabled. No AWS calls, inference, migrations or data changes are
needed. API response fields, saved suggestion schema, authentication, ownership
and human review/save remain unchanged. No new dependencies, IAM or resources.

## Evidence and causes

Original five real runs under reports-local/agenda/lab6-nova-tests/ are unchanged.
They used agenda-v1, not this patch.

| Case | Observed result | Confirmed gap versus hypothesis |
| --- | --- | --- |
| English | Alex in text but owner null; title missing | No owner-specific schema/prompt guidance. Model classification and conservative omission are hypotheses, not proven internals. |
| Ukrainian | Wednesday became Tuesday; Friday due null; title translated | Syntactic validation cannot check source weekday meaning. Date/zone were supplied correctly, but no calendar or distinct task-deadline guidance existed. Model date/language reasoning failed. |
| Multiple owners | Correct owners/start/DST/duration; extra end-time task | No explicit meeting end-time vs follow-up distinction. Likely over-extraction by model. |
| Ambiguous | Correct null date/owner/deadline | Preserve conservative null behavior. |
| Injection | Fabricated approval/budget excluded | Preserve untrusted-source prompting and no parser DB access. One success does not prove general resistance. |

## Changes and guarantees

- PROMPT_VERSION=agenda-v2 distinguishes future results from unchanged v1 evidence.
- Trusted 14-day English/Ukrainian weekday calendar derives from supplied local
  date, never server clock. Month/year/leap-day boundaries are deterministic.
  Dates outside the calendar still require model reasoning.
- Prompt/schema field descriptions distinguish explicit owner fields, discussion
  versus follow-up work, task due versus meeting start, meeting end versus action.
  Preserve source language and names. Source remains separate untrusted user data.
- Relative convention: first future weekday on/after supplied date; if same-day
  past/future intent is unclear, use null. No guessed time for after lunch, exact
  day for next week, vague owner, or unclear end-of-week deadline.
- Parser-only timezone check rejects returned offset/wall-time contradictions and
  nonexistent local times using IANA rules; enters the existing single repair.
  Explicit other source zones preserve the instant expressed in the supplied
  zone. Repeated DST hours with valid explicit offsets are accepted; prompt says
  not to guess offsets for ambiguous source times.
- This does NOT guarantee source-weekday agreement, owner completeness or absence
  of hallucinations. A valid but wrong weekday can still pass; human review is
  mandatory. No guessed postprocessing, task deduplication or calendar engine.
- Existing strict types/extra fields, exactly-one-tool validation, input/item/token
  bounds, deadline, no SDK retries, one repair, JWT first, disabled mode, throttle,
  manual fallback and no database access remain.
- Release smoke reads current prompt version rather than hardcoding v1.
  Historical saved v1 suggestions remain valid.

## Telemetry semantics and privacy

Each structured request event includes model, prompt version, random/AWS request
ID, provider_call_count, repair_attempts, attempts[], observed aggregate tokens,
inference latency_ms, request_latency_ms, estimated_cost_usd, status, safe reason,
usage_complete and cost_complete. No Cognito subject, agenda text, raw provider
message, JWT, credentials or exception strings are logged.

Each attempt records number, observed tokens, local Converse latency, safe outcome
and estimated cost. Count increments immediately before Converse: SDK calls
initiated, not proof of receipt/billing by Bedrock if a network timeout occurs.
SDK retries remain disabled. Setup/deadline failures do not count; repair_attempts
counts actual second calls, not intended repairs. Upper bound remains two calls.

Unknown per-attempt usage/cost stays null; aggregate totals represent only observed
usage with completeness false if any dispatched attempt lacks metering. Never
present partial estimates as final bills. Valid usage survives malformed message
envelopes. A fully metered malformed response can have complete usage but failed
parsing. Zero-call rejection records zero cost, distinct status/reason. Per-attempt
rounding can differ slightly from a single aggregate rounded estimate.

Final events are emitted on normal completion/failure; abrupt Lambda termination
can prevent logging. Missing logs mean unknown, never zero. No past metrics are
backfilled. Raw provider outputs are deliberately still not logged.

## Offline tests versus model quality

Mocked tests cover calendar computation across date boundaries, field/prompt
guidance, source isolation, owner/deadline/null proposal preservation, end-time
guidance, timezone repair, malformed response envelopes, bounded repairs, setup/
timeout errors, complete/partial usage, zero-call auth/size/disabled rejection,
log privacy and current-version release checks. Mocked proposals do not prove
Nova understands these inputs.

## Follow-up live plan — separate approval required

1. Review/publish a new image and deploy parser disabled via the guarded procedure,
   preserving backend/reporting/frontend/data. No publication/deployment performed.
2. Supply fresh private access-token file; verify auth/size/disabled. Separately
   approve activation and five top-level cases.
3. Use the same scenarios with explicit recorded reference date/timezone. Label
   frozen historical dates if used for reproduction. Starts >=21s apart, max five
   HTTP requests, one repair each, no SDK/HTTP retries, conservative aggregate
   USD0.05 allowance. Stop on abnormal routing/usage or safety failure.
4. Record actual JSON, per-attempt/aggregate usage, quality and CloudWatch events
   in a NEW evidence directory. Compare weekdays, owner/due accuracy, extra actions,
   nulls, injection, latency and cost. Disable on meaningful correctness failure.
5. Frontend publication, demo Save, <=45s recording and Git push remain separately
   authorized. Nova remains an unapproved deviation from required Claude. These
   HTTP scenarios are not deployed-UI evidence or all exact original course cases.

## Local validation

186 focused offline tests passed (parser, Lambda, CLI approval, guarded release,
IAM definitions and evidence utilities); no real model or database was contacted.
Backend Ruff checks and formatting passed using backend/pyproject.toml. Release
script/test syntax/import checks (E9,F,I) and formatting passed. The broader
repository script rule set has existing unrelated lint findings (executable-bit,
implicit string concatenation, subprocess check and broad exception style);
these were not expanded into unrelated cleanup. Python AST and git diff checks
passed. Infrastructure templates were unchanged, so no new template validation
or permissions were needed. Original evidence SHA-256 checks passed unchanged.
