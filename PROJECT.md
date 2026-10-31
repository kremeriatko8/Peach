# Peach project overview

## Purpose and scope

Peach is a full-stack application that demonstrates an end-to-end connection between a browser UI, an HTTP API, and a relational database. Its current resource is an item with a name, description, and status (`todo`, `in_progress`, or `done`). The UI provides a dashboard and a task board with item creation, editing, deletion, and movement between status columns. This document describes the existing implementation.

## Repository structure

| Folder or file | Purpose |
| --- | --- |
| `backend/app/` | FastAPI application, configuration, database sessions, and Lambda entry point. |
| `backend/app/api/` | Versioned API router and HTTP routes for items and health checks. |
| `backend/app/schemas/` | Pydantic request and response contracts. |
| `backend/app/services/` | Item operations and database queries. |
| `backend/app/models/` | SQLAlchemy database models. |
| `backend/migrations/` | Alembic schema migration environment and revisions. |
| `backend/scripts/` | Container startup script. |
| `backend/tests/` | API, item, health, and Lambda handler tests. |
| `frontend/app/` | Next.js App Router pages, root layout, and global styles. |
| `frontend/components/` | Dashboard, board, forms, providers, and reusable UI components in `ui/`. |
| `frontend/lib/` | API client, runtime schemas, item status helpers, and utilities. |
| `frontend/public/` | Static public assets. |
| `frontend/tests/` | Vitest and React Testing Library tests and setup. |
| `infra/` | CloudFormation templates for the backend, frontend, Cognito authentication, and GitHub OIDC deployment role. |
| `scripts/` | AWS deployment, teardown, frontend domain/certificate, and GitHub role setup scripts. |
| `.github/workflows/` | Lint/type checks and backend deployment workflow. |
| `Makefile` | Commands for local services, migrations, checks, and AWS deployment. |
| `docker-compose.yml`, `docker-compose.override.yml` | Base service definitions and automatically loaded development overrides. |

## Backend architecture

The backend uses Python, FastAPI, Uvicorn, Pydantic, SQLAlchemy's asynchronous ORM, and the asyncpg PostgreSQL driver. Dependencies are managed with uv. `app/main.py` constructs the application and configures CORS; `app/config.py` loads typed settings from environment variables and an optional `.env` file.

The main request path is **HTTP route → item service → SQLAlchemy model/session → PostgreSQL**. Routes validate requests and select response/status codes. Services implement item queries and mutations. Pydantic schemas define input/output data, while SQLAlchemy models define persistence. The injected database session commits successful requests and rolls back on errors.

Locally, Uvicorn serves the ASGI application on port 8000. The Lambda image uses `app/lambda_handler.py` and Mangum to adapt Lambda function URL requests to the same FastAPI application. Only the separate private migration Lambda accepts only explicit migration events. The public HTTP Lambda does not dispatch these operations.

## Frontend architecture

The frontend uses Next.js App Router, React, and TypeScript with strict type checking. `/` is the dashboard, `/items` is the task board, and `/meetings` is the owner-scoped Meetings list. Interactive client components use TanStack Query for fetching, caching, and mutations. React Hook Form and Zod validate forms. Styling uses Tailwind CSS, with shadcn/Radix UI components, Lucide icons, and Sonner notifications.

`frontend/lib/api.ts` centralizes HTTP requests, validates responses with Zod, and exposes typed item and readiness operations. The current interactive components call the API from the browser. The client also supports server-side calls using a separate internal URL.

`next.config.ts` defaults to `standalone` output for the Node.js Docker runtime. The AWS deployment script selects `NEXT_OUTPUT=export`, producing static files for S3 and CloudFront instead of running a Next.js server in AWS.

## Database and migrations

Local development uses PostgreSQL in the `db` container. Its data persists in the `pgdata` volume. The backend connects through `DATABASE_URL`, using the `postgresql+asyncpg` driver and password authentication.

The current `items` table contains a generated UUID primary key, `name` (`varchar(120)`), nullable text `description`, a constrained status, and timezone-aware `created_at`/`updated_at` timestamps. Migration `0001` creates the table and creation-time index; `0002` replaces the original `is_done` flag with the three-state status. Alembic tracks applied revisions.

The development Compose command applies `alembic upgrade head` before Uvicorn starts. The separate backend runtime entrypoint does the same. `make migrate` applies migrations explicitly.

AWS uses Aurora PostgreSQL Serverless v2 in a VPC, with a private database instance and security groups. The deployment template supplies the password-based `DATABASE_URL` to Lambda and stores a copy in Secrets Manager for deployment tooling. Lambda uses `DB_POOLING=false` (SQLAlchemy `NullPool`) so idle connections do not prevent Aurora from pausing. Local sessions use connection pooling with `pool_pre_ping`.

## Docker Compose services, ports, and dependencies

All three services share the `peach` bridge network and use `restart: unless-stopped`.

| Service | Role | Container port | Default host port | Startup dependency |
| --- | --- | --- | --- | --- |
| `db` | PostgreSQL database | 5432 | 5432 (`POSTGRES_PORT`) | None |
| `backend` | FastAPI HTTP API | 8000 | 8000 (`BACKEND_PORT`) | `db` must be healthy |
| `frontend` | Next.js UI | 3000 | 3000 (`FRONTEND_PORT`) | `backend` must be healthy |

The startup order is **db → backend → frontend**. The frontend has no direct database connection. The backend resolves the database as `db:5432`; server-side frontend calls resolve the API as `backend:8000`. Browser requests use the published backend address, normally `http://localhost:8000`. Changing a host port does not change container ports; the browser API URL and allowed CORS origin must match the addresses actually used.

The automatically loaded development override selects the Dockerfiles' `dev` stages, bind-mounts source code, and enables Uvicorn/Next.js development reload. Named volumes preserve the backend virtual environment, frontend dependencies, and Next.js build cache (`backend_venv`, `frontend_node_modules`, and `frontend_next`).

The backend Dockerfile's final stage is `lambda`. The development override explicitly selects `dev`; the base Compose file does not select a backend target, so building it alone selects that final Lambda stage. The separate Uvicorn `runtime` stage exists but is not explicitly selected by base Compose. The frontend's final stage is its standalone Node.js runtime.

## Health and readiness

| Check | Meaning and configuration |
| --- | --- |
| Database Compose healthcheck | `pg_isready` checks whether PostgreSQL accepts connections; interval 5 seconds, timeout 5 seconds, 10 retries. |
| Backend Compose healthcheck | `curl -fsS http://localhost:8000/health`; interval 5 seconds, timeout 5 seconds, 12 retries, start period 20 seconds. |
| `GET /health` | Liveness only: returns `{"status":"ok"}` without querying dependencies. |
| `GET /api/v1/health/ready` | Executes `SELECT 1`; returns `{"status":"ok","database":"ok"}` or HTTP 503 with `detail: "database unavailable"`. |
| Frontend health badge | Polls the database readiness endpoint every 15 seconds and displays Connected or Unavailable. |

The frontend has no Compose healthcheck. Its startup gate uses backend liveness, not the database readiness endpoint. Compose startup dependencies do not continuously guarantee downstream readiness.

## Frontend/backend contracts

The API uses JSON over HTTP, with item routes under `/api/v1`. FastAPI exposes Swagger at `/docs`, ReDoc at `/redoc`, and its OpenAPI schema at `/openapi.json`.

| Method and path | Contract |
| --- | --- |
| `GET /api/v1/items` | Returns `{items: Item[], total: number}`. `limit` defaults to 20 and accepts 1–100; `offset` defaults to 0 and must be nonnegative. |
| `POST /api/v1/items` | Creates an item; returns HTTP 201 and the item. |
| `GET /api/v1/items/{item_id}` | Returns an item or HTTP 404. |
| `PATCH /api/v1/items/{item_id}` | Updates supplied fields; returns the item or HTTP 404. |
| `DELETE /api/v1/items/{item_id}` | Returns HTTP 204 without a body, or HTTP 404. |

Create input requires `name` (1–120 characters). `description` is optional/nullable and limited to 2,000 characters at the API boundary. `status` is one of `todo`, `in_progress`, and `done`, defaulting to `todo` in the backend. Update fields are optional. Responses additionally contain `id` (UUID string) and timestamp strings `created_at` and `updated_at`.

Errors use FastAPI's `detail` field; validation errors use HTTP 422. The frontend converts unsuccessful responses into `ApiError`, handles empty 204 responses, and validates successful JSON against its Zod schemas. These schemas mirror the backend contract manually; no generated shared client is present.

Browser calls use `NEXT_PUBLIC_API_URL`; server-side calls use `INTERNAL_API_URL`. `NEXT_PUBLIC_API_URL` is embedded during frontend builds. For AWS static deployment it is set from `BACKEND_URL`. Backend `CORS_ORIGINS` permits configured browser origins; the deployment script accepts `API_CORS_ORIGINS` for that setting. Item API routes require Cognito access tokens verified offline against deployment-supplied public JWKS. Each task is scoped to the verified Cognito sub; health remains public. Frontend OIDC/PKCE sessions supply access tokens explicitly and cache tasks by subject.

## AWS deployment structure

`make deploy-backend` runs `scripts/deploy-backend.sh`: it builds/pushes the Lambda image to ECR, deploys the private `infra/migrations.yaml` runner using existing DB networking, verifies migrations, then deploys `infra/backend.yaml`, and records the HTTPS function URL as `BACKEND_URL`. The stack includes Lambda, Aurora, database networking, an execution role, a database URL secret, and CloudWatch logs. Lambda reaches Aurora on PostgreSQL port 5432; public API traffic uses the HTTPS function URL.

`make deploy-frontend` runs `scripts/deploy-frontend.sh`: it builds the static export against that backend URL, deploys `infra/frontend.yaml`, uploads files to a private S3 bucket, and invalidates CloudFront's cache. CloudFront serves the browser over HTTPS and uses origin access control to read S3. A CloudFront Function rewrites page paths to exported HTML files. Custom domain/certificate setup is handled separately by `scripts/domain-frontend.sh`.

`make github-role` configures the GitHub OIDC deployment role using `infra/github-oidc.yaml`. `.github/workflows/deploy-backend.yml` deploys on every `main` push or manual dispatch, after validation, using temporary OIDC credentials. Only schema-changing releases
require exact migration manifest approval and a verified fresh manual snapshot. Frontend deployment remains a local Makefile command.

## Runtime versions and dependency definitions

| Component | Repository definition |
| --- | --- |
| Python | `>=3.14` in `backend/pyproject.toml`; `python:3.14-slim` and Lambda `python:3.14` images in `backend/Dockerfile`; CI installs 3.14. |
| uv | Dockerfile copies `ghcr.io/astral-sh/uv:latest`; an exact uv version is not pinned there. |
| PostgreSQL locally | `postgres:17-alpine` in `docker-compose.yml`. |
| Aurora PostgreSQL | Default engine version `17.4` in `infra/backend.yaml`; database instance permits automatic minor upgrades. |
| Node.js | `node:22-alpine` in `frontend/Dockerfile`; Node 22 in lint CI. |
| pnpm | `10.34.5` in `frontend/package.json` and Dockerfile; frontend deployment has an `npx pnpm@10` fallback. |
| Next.js | Exact `16.3.4` in `frontend/package.json`, also used for `eslint-config-next`. |
| React / React DOM | Exact `19.2.8` in `frontend/package.json`. |
| Frontend tooling | TypeScript `^5`, Tailwind CSS `^4`, ESLint `^9`, Prettier `^3.9.6`, and Vitest `^5.0.0` in `frontend/package.json`. |

`backend/pyproject.toml` specifies minimum versions for FastAPI, Uvicorn, SQLAlchemy, asyncpg, Alembic, Pydantic, pydantic-settings, and Mangum. `backend/uv.lock` records resolved versions. `frontend/package.json` mixes exact versions and compatible ranges; `frontend/pnpm-lock.yaml` records resolved dependencies. Builds/CI use frozen lockfile installation. Docker runtime tags select a major or minor series rather than an immutable image digest.

## Existing verification commands

`make lint` runs backend Ruff lint and frontend ESLint inside Compose. `make test` runs pytest and Vitest; backend database tests use a separate test database. Lint CI additionally runs Ruff's formatting check, Prettier's formatting check, and `pnpm exec tsc --noEmit`. The frontend tests use Vitest, jsdom, and React Testing Library. Formatting commands (`make fmt`) are separate from the read-only checks.

## Authentication deployment and public configuration

Cognito is managed by HCP Terraform (`infra/auth.tf`, ADR 0007). Google
credentials are sensitive HCP workspace variables, changed through a reviewed
plan and apply in HCP.
`make auth-config` reads Terraform outputs into public `frontend/.env.local`
settings for localhost; frontend deployment reads deployed settings before build.
The browser stores its OIDC session and PKCE state in session storage. `/login/`
starts Managed Login; `/auth/callback/` is a static page processed by the global
auth provider. The header displays the email and clears the browser session before
Cognito logout. Backend verification/ownership are implemented; disposable legacy rows remain NULL-owned until separately authorized cleanup.


Ownership revision `0003` follows `0002`, adds nullable `owner_id` and an
owner/created-at index, and preserves all unassigned legacy rows. No user table,
email ownership, automatic assignment, or data deletion is introduced.
`backend/app/auth.py` verifies access tokens with cached RSA keys and no runtime
HTTP calls. `scripts/cognito-snapshot.py` obtains public keys during configuration
or deployment; rotation requires a backend redeploy. `make backend-auth-config`
writes public local backend settings to gitignored `backend/.env.auth.local`.
The private migration runner has no URL and uses `app.migration_handler.handler`;
the public HTTP handler no longer dispatches migration actions. Deployment stops
before updating public code if the runner fails. See README for rollout/IAM risks.


Schema-changing releases require preflight, exact approval via
`PEACH_APPROVED_MIGRATION_SHA256`, then an explicit manual snapshot confirmed
available before deployment. `PEACH_RELEASE_SNAPSHOT_ID` is supplied to CI as a
repository variable. Ordinary releases matching the successful
`ReleaseSchemaSha256` marker skip snapshot checks and runner invocation. The script fails closed on missing existing
credentials and validates configuration before migration. It checks the public
UPDATE change set for any RDS removal/addition/replacement, verifies actual
revision `0004`, task ownership and Meetings schema, and preserved task/meeting
rows inside the migration transaction,
then executes that exact change set. Disposable legacy NULL-owner rows are
preserved during migration and deployment; cleanup is a separate manual operation
after successful rollout verification. See README's controlled ownership release procedure.


## Meetings implementation

Meetings follow the existing route/service/schema/model layers under
`backend/app/`, with endpoints at `/api/v1/meetings`. Every query is scoped to the
verified Cognito `sub`; clients cannot supply ownership. Cross-user access
returns 404. The additive `0004_create_meetings` migration creates a separate
table with timezone-aware starts, positive bounded duration/participant counts,
nonblank title/owner checks, and an `(owner_id, starts_at)` index. Existing task
rows and ownership are preserved.

The private runner targets exactly `0004` and checks the reflected Meetings
schema plus unchanged tasks and existing meetings transactionally. The release
script requires those additional proofs before updating public code. Existing
snapshot, identity/network, image, and RDS change-set safeguards remain intact.
Legacy cleanup still requires `0003` and is not included in this release.

`frontend/app/meetings/page.tsx` uses the existing account access gate. The list
and form components reuse Peach's visual primitives, with pagination, confirmed
deletion and inline errors. `frontend/lib/meeting-time.ts` explicitly converts
Europe/Kyiv wall-clock times to UTC, rejects DST gaps, and offers both fold
occurrences. Account-scoped Meetings queries are cancelled/removed with task
queries on account changes; late responses cannot restore the old account's
state. Unchanged edit timestamps preserve their original precision.

Backend tests may only target disposable local `_test` databases; real migration
tests use additional isolated schemas. Frontend tests cover CRUD interactions,
DST transitions, account cleanup, late operations and existing Board behavior.
No reporting infrastructure or AWS changes belong to this implementation.

## Phase 2 — local weekly productivity reporting

Implemented in `backend/app/reports/`: strict Kyiv ISO-week parsing, owner-scoped
SQLAlchemy queries, metric calculation, UTF-8 CSV rendering, an injectable builder
and a read-only local subprocess adapter. `WeeklyReportBuilder` accepts trusted
`ReportConfig`, an injected session and clock; its async `build_weekly_report(week)`
returns bytes for future Lambda reuse without AWS imports.

Reports include meeting counts/recorded minutes, previous-week comparisons and
five longest meetings (duration descending, start/UUID ascending). Monday local
boundaries convert independently to UTC, including DST and ISO year rollover.
Zero previous metrics produce an explicit N/A percentage. Meeting start assigns
the week and the full recorded duration is counted. Formula-prone user titles are
neutralized while CSV escaping preserves Unicode, punctuation and newlines.

The optional task section uses real stored fields only: weekly `created_at`
counts, current status counts across all dates and a snapshot timestamp. It does
not represent historical progress or infer completion from `updated_at`.

Run `make report-owners`, then `make report-owner OWNER=1` (choose the intended
listed test owner), then `make report-local WEEK=2026-W40`. The selected subject
is private ignored `.env.report.local`; generated CSV files live in ignored
`reports-local/`. The runner requires the existing `peach-meetings-local` tmpfs
PostgreSQL stack, verifies its identity/storage/network/target and uses a read-only
repeatable-read transaction. All report queries filter one configured Cognito
owner; unowned tasks are excluded. No seeds, migrations or production connections
are part of reporting. See README for full semantics and local safeguards.

Reporting AWS infrastructure, storage/upload, scheduling, queues and email are
intentionally deferred. Existing authentication, CRUD, task ownership and
migration/deployment safeguards remain in place.

## Phase 3 — event-driven AWS reporting, implemented locally only

Added `backend/app/reporting/` adapters for strict SQS/scheduled/manual/direct lab
payload parsing, read-only report building, conditional S3 publication, S3 event
validation, MIME/SES delivery and recoverable DynamoDB claims. The tested Phase 2
core is reused with an optional scoped object-key metadata argument;
`make report-local` retains its interface and output convention. The mailer
has no database URL or owner subject. Runtime boto3 is explicitly locked.

`infra/reports.tf` and `infra/reports-iam.tf` (HCP Terraform, formerly the
`peach-reports` stack) contain the reporting resources: four encrypted SQS
queues, two container Lambdas/log groups, three scoped roles, event-source mapping,
private AES256/lifecycle S3 bucket/notification/policy/permission, gateway endpoint,
on-demand retained mail state, mailer async failure destination and disabled Kyiv
Monday schedule/group. No database/auth resources, NAT or API changes are declared.

Added offline `reports-prepare`/`reports-validate` targets and future mutating
`report-now` (SQS only). Backend deployment preserves every main push and manual dispatch, with a
credential-free validation job and OIDC deployment only after success. Reporting
infrastructure is not deployed by that workflow. Existing migration,
snapshot and deployment checks remain intact; existing CI IAM is not expanded.

See [docs/reporting.md](docs/reporting.md) for the detailed resource settings,
owner/SES/permissions/network prerequisites, conditional-write and email lease
semantics, limitations, lab evidence, failure recovery and **NOT EXECUTED** manual
deployment/activation checklist. All Phase 3 AWS tests use mocks; production data,
resources, policies and inboxes are untouched.

## Automatic CI/CD release policy

See [docs/deployment.md](docs/deployment.md). The backend script distinguishes
ordinary releases from changed/missing migration manifests, including schema
models and runner verification. Only successful guarded migration releases record
`ReleaseSchemaSha256`. This is release evidence, not a live database drift check.
CI ignores local `.env`, requires temporary credentials and verifies the OIDC role.
Images use exact release tags and immutable digests; no newest-image selection or
legacy cleanup occurs. Frontend deployment stays manual. Reporting first deployment
requires a reviewed change set and authorization; future image-only CI updates are
documented but not implemented. Routine rollback preserves Meetings and revision
`0004`; recovery never drops/recreates the existing Aurora cluster.

## Agenda parsing lab — local implementation

New owner-scoped GET/PUT meeting agenda API and additive migration 0005 store
reviewed items/actions/language plus nullable original suggestion metadata.
Parser is a separate non-VPC Lambda with Cognito JWT checks and no database access.
The manual editor remains usable without a parser URL. See docs/agenda-ai.md for
release gates and docs/architecture.md for the C4 container diagram. AWS deployment,
paid tests, budget creation and submission evidence remain separate approvals.
