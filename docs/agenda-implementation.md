> **October 18 Nova adaptation:** Provider/model instructions below are historical.
> Current implementation uses amazon.nova-lite-v1:0 via Runtime Converse; see
> [current release guide](agenda-ai.md) and [ADR 0006](adr/0006-llm-agenda-parsing.md).
> This deviation from required Claude is not instructor approved. Existing infrastructure
> blockers remain; historical model checks/results are not Nova availability evidence.

# Agenda initial implementation handoff

For the completed preparation review, AWS results and current test counts, see
[deployment readiness](agenda-deployment-readiness.md). The initial-phase account
below records the state before the later authorized read-only AWS checks.

Local implementation on `feat/paste-agenda`, based on the clean current main at
start. No commits, pushes, AWS API calls, model invocations, production migrations,
resource changes, or budget creation were performed. Existing private reporting
submission evidence was not edited.

## Implemented

Manual meeting agendas and action items, owner-scoped GET/PUT API, additive 0005
migration, original suggestion JSONB, atomic reviewed meeting updates, migration
schema/data preservation proofs, exact assignment tool parser, one repair attempt,
Mantle SDK, local paid-command entry points, JWT-protected parser Lambda, bounded
requests/concurrency, structured metadata logs, manual fallback, cancellation,
field suggestion markers, static frontend integration, separate disabled AI stack,
$5 email budget definition, architecture, ADR and evaluation preparation.

## Verification performed

| Check | Result |
|---|---|
| Full backend suite | 207 passed |
| Final parser/Lambda targeted check | 22 passed |
| Deployment/script suite | 107 passed, 58 subtests passed |
| Frontend suite | 93 passed |
| Ruff backend lint/format | passed |
| Ruff scripts configured lint/format | passed |
| ESLint / Prettier / TypeScript | passed |
| cfn-lint AI and budget templates | passed |
| Shell syntax checks / git diff whitespace | passed |
| Schema release compatibility | head 0005, fingerprint emitted |
| Next.js static export with webpack | passed, all routes exported |

Database tests ran against a disposable localhost PostgreSQL 16.2 instance in
/private/tmp, never production. Docker Desktop was unavailable; repository CI uses
PostgreSQL 17, which should be checked before release. No container image build was
possible. Initial sandboxed DB attempts failed with local networking permissions;
rerun with authorized local access passed. An old 0004 assertion was updated to
0005; full backend rerun passed. Default Turbopack build failed on local worker-port
restrictions; supported webpack static export passed. The default build script
was preserved. The temporary PostgreSQL instance was stopped after verification.

## Remaining gates

- Verify actual account/model access, default Mantle project ARN, quotas, IAM
  condition behavior, current regional pricing, budget email and existing budgets.
- Review image build on Linux/selected architecture and PostgreSQL 17 CI results.
- Approve snapshot/fingerprint-controlled 0005 backend release separately.
- Approve disabled AI change set, budget creation, activation/paid calls, and manual
  frontend deployment separately. Nothing automatically deploys the AI stack.
- Collect actual deployed tests, recording and CloudWatch evidence; create/publish
  a commit only when authorized. No deployment-success claim is made.

Warm-instance rate limits are best effort and reset with execution environments;
concurrency and budget alerts are not monthly spending caps. Unknown inference
pricing disables HTTP parsing. Browser cancel does not guarantee server cancellation.
Client-carried suggestion provenance is not cryptographically authenticated.
One current proposal is kept per meeting; full generation history/source text is
not stored. Source texts must be collected with consent for faithful v2 re-evaluation.

See [release guide](agenda-ai.md), [evaluation template](agenda-evaluation.md),
[ADR](adr/0006-llm-agenda-parsing.md), and [C4 diagram](architecture.md).

## All modified files

- `.env.example`
- `Makefile`
- `PROJECT.md`
- `README.md`
- `backend/app/api/router.py`
- `backend/app/config.py`
- `backend/app/migration_handler.py`
- `backend/app/models/__init__.py`
- `backend/pyproject.toml`
- `backend/tests/test_lambda_handler.py`
- `backend/tests/test_migrations.py`
- `backend/uv.lock`
- `docs/deployment.md`
- `frontend/components/item-session.tsx`
- `frontend/components/meetings.tsx`
- `frontend/lib/api.ts`
- `frontend/tests/item-session.test.tsx`
- `scripts/deploy-backend.sh`
- `scripts/deploy-frontend.sh`
- `scripts/tests/test_backend_deployment.py`
- `scripts/tests/test_schema_release.py`

## All created files

- `backend/app/ai/__init__.py`
- `backend/app/ai/agenda.py`
- `backend/app/ai/agenda_lambda.py`
- `backend/app/ai/cli.py`
- `backend/app/ai/costs.py`
- `backend/app/api/routes/agendas.py`
- `backend/app/models/agenda.py`
- `backend/app/schemas/agenda.py`
- `backend/app/services/agendas.py`
- `backend/migrations/versions/0005_create_agendas.py`
- `backend/tests/test_agenda_lambda.py`
- `backend/tests/test_agenda_parser.py`
- `backend/tests/test_agendas.py`
- `docs/adr/0006-llm-agenda-parsing.md`
- `docs/agenda-ai.md`
- `docs/agenda-deployment-readiness.md`
- `docs/agenda-evaluation.md`
- `docs/agenda-implementation.md`
- `docs/architecture.md`
- `frontend/components/agenda-dialog.tsx`
- `frontend/lib/agendas.ts`
- `frontend/tests/agendas.test.tsx`
- `infra/ai.yml`
- `infra/budget.yml`
- `scripts/deploy-ai.sh`
- `scripts/tests/test_ai_infra.py`
- `scripts/tests/test_ai_parameters.py`
- `scripts/validate-ai-parameters.py`
