# Lab 6 frontend completion — focused handoff

## Readiness

Agenda is opened from each owned meeting. Paste → Parse → editable suggestion →
manual correction → Save is implemented. Saves go to the existing authenticated
PUT /api/v1/meetings/{id}/agenda, never to the parser. The original model proposal,
model and prompt version remain separate from corrected fields. Applying meeting
title/start/duration is explicit opt-in. Manual agenda/action entry works when
parsing is disabled, unconfigured or fails; existing provenance is retained when
editing. Cancellation ignores late results.

API ownership is checked before reads/writes, with 404 for other users; writes
lock the owned meeting. JWT verification, existing auth session boundaries and
query-cache identity isolation remain. No new auth helper or infrastructure.

Focused tests exercise UI → real frontend HTTP client → mocked API responses,
including JWT headers, separate parser/save URLs, corrected owner/original
proposal, meeting opt-in, historical v1 metadata, disabled fallback and malformed
response privacy. These are offline integration tests, not a live DB/UI claim.
Existing database-backed ownership tests were reviewed, not run against production
or a newly created database. No API/database schema changes are needed.

## Existing deployment procedure — NOT executed

Only after explicit frontend publication approval. Pin the reviewed commit supplied
in the approval; require clean tree/account/region. First verify existing CORS
allows the unchanged frontend origin, auth callback matches SiteUrl, and retained
frontend object hashes/metadata still match the protected archive. Stop on a
mismatch; do not deploy backend/auth or invent a CORS change.

The existing lower-level command is scripts/deploy-frontend.sh. It resolves the
existing frontend stack, refreshes PUBLIC auth settings, builds static export,
uploads hashed assets first, syncs HTML/nonhashed assets, then invalidates /*.
Its sync deletes obsolete NONHASHED objects; existing hashed chunks are retained.
Review the unchanged frontend template/change set before granting publication.
No reporting or database resource is part of that template.

After those approvals/checks, the concrete invocation is:

~~~bash
set -euo pipefail
set +x
export AWS_PROFILE=default AWS_REGION=us-east-1 AWS_DEFAULT_REGION=us-east-1
test "$(aws sts get-caller-identity --query Arn --output text)" = arn:aws:iam::968053399627:user/sofiia
test "$(git branch --show-current)" = feat/paste-agenda
test -z "$(git status --porcelain)"
: "${PEACH_APPROVED_FRONTEND_COMMIT:?Set the exact reviewed commit from approval}"
test "$(git rev-parse HEAD)" = "$PEACH_APPROVED_FRONTEND_COMMIT"
BACKEND_URL="$(aws cloudformation describe-stacks --stack-name peach-backend --query "Stacks[0].Outputs[?OutputKey=='ApiUrl'].OutputValue | [0]" --output text)"
PARSER_URL="$(aws cloudformation describe-stacks --stack-name peach-ai --query "Stacks[0].Outputs[?OutputKey=='ParserUrl'].OutputValue | [0]" --output text)"
export BACKEND_URL PARSER_URL FRONTEND_BUILD_ENGINE=webpack
bash scripts/deploy-frontend.sh
~~~

This is the existing publication script, not a backend release. Do not follow its
generic final suggestion to redeploy the backend: existing CORS must be checked
first and already-correct CORS requires no update.

The higher-level agenda-release.py frontend phase currently requires a matching
successful paid receipt AND common backend/parser image release state. Existing
protected state predates the approved parser-only v2 release, which intentionally
left backend unchanged. It cannot be used as-is; never fabricate a receipt/state
or rerun backend/migrations to satisfy it. Explicit approval may instead cover
the existing deploy-frontend.sh procedure above, initially with AI disabled and
manual fallback, followed by an approved UI test window. This is a deliberate
release-scope decision, not an implicit bypass.

## Practical frontend rollback — separate approval if needed

Keep parser activation separate. Before publication confirm the preserved archive
is still the immediate prior frontend. If not, preserve a new coherent archive
before updating anything. Known archive:
reports-local/agenda/preparation-55699be02b6a/frontend-manifest.json and frontend/.
The existing protected release archive is also available.

To restore the archived UI, upload every manifest object to
peach-frontend-968053399627-us-east-1 with its original ContentType, CacheControl,
ContentEncoding (when present) and Metadata. Validate ALL local SHA-256 hashes
before the first upload. Do not merely rebuild an old commit or sync with --delete:
that loses exact artifacts/metadata or risks deleting useful chunks. Restore
hashed assets before HTML, leave extra new hashed assets in place, invalidate /*
on E13PELWU9NKJR8, and verify login, meetings and manual agenda/API readiness.
No DB downgrade, backend/report rollback, snapshot restore or IAM change is needed.
S3 versioning was not enabled at the last check; the verified local archive matters.

## Shortest completion path

1. Approve existing frontend publication initially disabled, with preserved assets.
2. Sign in normally in the deployed app. No token copying or new login helper.
3. Approve one bounded activation/UI evidence window. Use the exact five course
   inputs in agenda-evaluation.md once each, serially, within an explicit cost
   allowance and existing one-repair limit. This would require amending the prior
   v2 retest plan, which specified the five DIFFERENT original representative inputs.
4. Record one of those five runs: pasted text → Parse → prefilled form → one
   correction → Save, <=45 seconds. Approve one owned demo meeting/agenda write
   explicitly; do not modify unrelated existing data.
5. Capture actual JSON/usage/latency and CloudWatch events without credentials.
   Keep old v1 evidence unchanged. Disable on material safety/quality failures.
6. Finalize actual five-case table and written answers. Obtain instructor acceptance
   or transparently disclose the unapproved Claude-to-Nova deviation.
7. Approve Git push separately; use the resulting real GitHub commit permalink
   containing implementation, infra/ai.yml, frontend and ADR. No fabricated link.

## Submission inventory

- Implementation, infrastructure, ADR and C4 source: present locally.
- Migration/backend and disabled v2 parser: deployed in prior approved stages.
- Actual representative v1 five-test JSON/table: present, three semantic failures
  honestly reported; five schemas passed. Not the exact original course set.
- Actual CloudWatch line and measured cost: present (USD0.00038094 for five).
- Written answers: updated in agenda-evaluation.md from actual observations.
- GitHub commit link: pending push approval; local commit alone is not a link.
- Deployed <=45s correction-and-Save recording: pending publication/activation/write
  approval. Manual-only recording does not satisfy the AI parsing demonstration.
- Instructor acceptance of Nova and any test-case substitutions: not obtained.

## Validation for this frontend review

63 focused frontend tests passed (agenda/editor/HTTP-client integration, meetings,
auth and meeting-time); ESLint, TypeScript, Prettier and a local Next.js webpack
static export passed using the previously verified public production URLs. Build
artifacts are ignored and were not uploaded. No live AWS inspection/mutation,
inference, login helper, new test database, migration or push occurred.
