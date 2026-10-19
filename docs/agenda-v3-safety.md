# Agenda v3 local safety remediation

Production agenda-v2 was disabled after the five approved UI tests. No local v3
code is deployed or real-model verified. The five UI telemetry events show six
Converse attempts (one repair), 9,185 input/1,105 output tokens and USD0.00081630
estimated inference cost. User reports: Ukrainian partial, email pass, relative
dates partial, shopping-list fallback pass, owner-override injection FAIL.

Actual output JSON/screenshots were not supplied. CloudWatch confirms usage and
HTTP outcomes, not the individual extracted fields. Chronological input-to-event
mapping is assumed from reported order. V1 inputs differ; no paired score is
valid. All old evidence is retained under reports-local/agenda/.

## Root causes

- Schema accepted a syntactically valid owner occurring in malicious source text;
  source-as-untrusted prompting alone failed. Owner presence alone does not prove
  the correct association.
- Nullable strings permit the literal string null, which frontend rendered
  unchanged. This is a confirmed validation/presentation gap.
- A numeric minimum of one validates invented defaults. Minimum-bound bias is a
  plausible model explanation, not proven. Schema checks had no source grounding.
- Discussion/action classification and due-date support were left to the model.
  No semantic truth follows from HTTP200 or a valid schema.

## Local changes

PROMPT_VERSION becomes agenda-v3. A conservative pre-provider check rejects the
entire paste when recognizable English/Ukrainian override instructions occur,
including the exact failing owner-override input. It returns the existing
manual-fallback error and logs zero calls. Text is not silently stripped or
rewritten; false positives intentionally require manual entry.

After strict Pydantic/tool validation, limited source checks only clear/drop
questionable data, never guess missing values:
- Placeholder owner strings become actual null. Non-null item owners must appear
  verbatim somewhere in the source; action owners must occur in supporting clauses.
- Minutes require an explicit numeric minute unit. A meeting duration may also
  match explicit source start/end clocks. Unsupported one-minute defaults are
  cleared; genuinely stated one-minute values survive.
- Starts without a supported explicit HH:MM clock are cleared, including invented
  after-lunch times. Other clock formats conservatively require manual correction.
- Follow-up task wording must be a source span inside a clause with a supported
  commitment/request cue and not a discussion heading. Unmatched/paraphrased
  actions are omitted. Meeting-end-only text is not a follow-up.
- Due dates need a deadline cue plus a supported ISO date, English month/date, or
  English/Ukrainian weekday in the matching task clause. Ambiguous end-of-week and
  unsupported dates become null. Missing deadlines are not filled automatically.
- Prompt reinforces actual JSON null, explicit numbers/names, no numeric defaults,
  source wording for tasks, and discussion versus commitment.

Frontend draft mapping also renders historical literal-null owners as blank.
Its stored original suggestion remains unchanged, so corrections do not overwrite
provenance. API fields, ownership/JWT, disabled mode, limits, one repair, logging,
manual save and database schema remain unchanged. No new services/permissions.

## Limits and tradeoffs

This is a conservative filter, NOT a complete NLP engine or universal injection
defense. Novel/obfuscated instructions can evade detection. Supported patterns can
reject legitimate security-discussion text. Exact task spans, sentence splitting,
limited language/date/clock patterns can omit valid paraphrases, honorific names
or unsupported formats. A name/number occurring elsewhere in a source does not
prove its relationship to a specific item; content in mixed discussion/task
clauses can still be misclassified. It does not recover omitted owners/minutes,
prove weekday semantics, verify every factual claim, or make arbitrary model
outputs safe without review. Human correction remains essential.

Existing mock fixtures previously invented unrelated fields from the word
Pricing. Grounding tests now supply source facts or expect neutralization, rather
than disabling the source checks to preserve unrealistic fixtures.

## Remaining release and submission work

Review this local patch and offline regressions. Production stays disabled.
Any deployment/reactivation or additional paid test needs separate approval.
Retest a small explicitly bounded set through the UI; injection may safely reject
to manual entry rather than produce a proposal. Preserve new actual JSON and
CloudWatch events in a new directory. Never substitute these synthetic unit
outputs for measured results. A final demo requires actual successful parsing,
one reviewed correction and authorized Save, plus <=45-second recording. Git push
and submission commit link remain separately authorized. Nova remains an
unapproved deviation from the Claude requirement.

## Validation

208 focused offline backend/release/CLI/evidence/IAM tests and 68 focused frontend
tests passed. Ruff, ESLint, formatting, TypeScript and diff checks passed. Tests
use mocks/SDK stubs, not live models or a production/test database. The exact five
UI inputs are covered with clearly synthetic provider outputs; the exact injection
must reject before calling the mock. Original v1 evidence SHA256 hashes match.
The sole production mutation was the approved ParserEnabled=false safety update.
