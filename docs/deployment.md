# Backend CI/CD and exceptional releases

Every push to `main`, without path filters, runs `.github/workflows/deploy-backend.yml`.
Manual `workflow_dispatch` remains available, with deployment restricted to `main`.
Automatic deployment is an intentional university lab requirement; do not replace
it with manual-only deployment or permanently disable the workflow.

The credential-free validation job runs locked Python 3.14 backend dependencies,
Ruff lint/formatting, all backend tests against a disposable PostgreSQL service,
deployment safety tests with mocked AWS/Docker/HTTP, migration-chain validation,
workflow validation, shell syntax checks, CloudFormation lint and an ARM64 Lambda
image build/import smoke test without publication. A failed validation job prevents
the deployment job from starting. CloudFormation lint exempts only existing W1011:
the backend already passes the preserved database password through a NoEcho
parameter. This task does not redesign secret delivery; other lint findings fail.

Only the deployment job receives `id-token: write`; it assumes
`vars.AWS_DEPLOY_ROLE_ARN` using GitHub OIDC, with existing credentials cleared.
The backend script ignores root `.env` in GitHub Actions, removes AWS profile
selection, requires temporary session credentials and verifies the STS caller
matches the configured role. The role's main-branch trust and existing scoped IAM
permissions remain unchanged. Validation has no AWS credentials. Checkout does
not persist repository credentials. Serialize CI, local releases and any recovery
operations; GitHub concurrency does not prevent an external operator deploying.

## Ordinary application releases

`scripts/schema-release.py` hashes the paths and bytes of migration Python files,
`alembic.ini`, model Python files and the private migration runner. It validates a
single complete migration chain and requires the head to match the runner's
`EXPECTED_REVISION`. Models/runner changes also need review because they affect
schema compatibility and preservation checks.

After a successful schema release, the backend CloudFormation parameter/output
`ReleaseSchemaSha256` records this manifest. An exact match means an ordinary
release: validation, configuration/auth/network preflight, image publication,
checked backend UPDATE change set, execution and health feedback run automatically.
No snapshot is created or required, and the private migration runner is neither
updated nor invoked. CORS and existing credentials are preserved.

Images are built from the checked-out source; CI tags include the commit SHA,
run ID and attempt. Deployment resolves that exact tag and pins the immutable
ECR digest. It never searches for the newest image or chooses a cleanup image.
The validation image is rebuilt in the release job; this is build compatibility
validation, not an assertion that two builds with upstream base images are identical.

The marker records a successful release, not a fresh SQL check or proof against
out-of-band database drift. Never seed/edit it manually to bypass preparation.
Any independently performed schema change or restore must invalidate/reconcile
release evidence through an explicitly reviewed recovery procedure. Tests cannot
eliminate every database or operational risk.

## Schema-changing releases and first revision 0004

A missing or changed marker is a schema release, including initial adoption of
this policy. Before any image push, it requires:

- `PEACH_APPROVED_MIGRATION_SHA256` equal to the exact reviewed local manifest.
- `PEACH_RELEASE_SNAPSHOT_ID` naming an available **manual snapshot of the existing
  cluster**, less than 24 hours old. Automated backups do not satisfy this gate.
- Existing configuration, secret, network and environment checks passing.

No snapshot is created automatically. Do not broaden IAM to let CI create backups
as a side effect. Without preparation, a main push still validates but deployment
fails closed before image publication, runner changes or database mutation.
Ordinary releases with the established manifest do not need these variables.

For the first production `0003` to `0004` release, perform these steps **later,
only after authorization**:

1. Review release code, CI role permissions, actual database revision/history,
   current owner/data preservation evidence and the intended release window.
   Retain the current image digest and prepare the manual frontend release.
2. Compute the non-secret fingerprint locally: `python3 scripts/schema-release.py`.
   It must report revision `0004`. Finalize migration/model/runner files before
   approving their fingerprint; any subsequent change invalidates approval.
3. Run `./scripts/deploy-backend.sh --preflight-only` using approved credentials.
   It reads production secrets privately, so this is a separately authorized
   preparation step, not an offline test. It deploys nothing and requires no snapshot.
4. A backup operator runs `./scripts/snapshot-backend.sh`, waits for availability
   and retains the returned snapshot ID. Snapshot storage can incur charges.
5. Set the two non-secret repository variables above to the reviewed fingerprint
   and fresh snapshot ID. Verify `AWS_DEPLOY_ROLE_ARN` and `AWS_REGION`. Do not
   push to main until release preparation is approved. The push then starts the
   automatic workflow; no permanent disablement or ordinary-release approval is needed.
6. The script creates and checks the **exact public backend change set before
   migration**, rejects all RDS additions/removals/possible replacements, updates
   only the private runner with the same digest, invokes `action=migrate`, and
   verifies the actual revision, task ownership/index, Meetings schema and unchanged
   task/meeting row values and counts. Verification failure rolls back the migration
   transaction and stops public deployment. It rechecks the same change set before
   execution. Legacy cleanup is never invoked.
7. Confirm stack completion, migration proof, authenticated CRUD and owner isolation;
   then deploy the frontend manually. Remove the one-release approval/snapshot
   variables. The recorded marker now permits ordinary automatic deployments.

`make deploy-backend` runs the complete release, including migration when classified
as schema-changing. It does not pause between migration and public deployment.
Approving it means approving that whole guarded sequence. Future migration heads
must update the runner and its preservation verification; adding a revision file
alone fails compatibility validation.

A database snapshot is recovery preparation, not zero-risk migration execution.
The runner takes transactional locks and may temporarily block writes; plan a
release window. If migration succeeds but CloudFormation later fails, the database
can remain at `0004` while the old API remains deployed. Investigate stack status,
retain backup/evidence, and retry only with valid preparation; never fabricate the marker.

## Frontend and reporting remain separate

There is **no automatic frontend deployment** in the existing workflows.
`make deploy-frontend` remains a separately authorized local build/S3/CloudFront
release, performed after the backend. No frontend or Cognito behavior changed here.

Pushing application code does **not** deploy `peach-reports`, update reporting
Lambda functions, enable schedules, provision SES identities, enqueue messages or
send mail. The backend validation job may lint `infra/reports.yaml` and import
reporting handlers without creating reporting resources.

The first reporting deployment requires a separately reviewed CREATE change set
and explicit execution authorization, verified SES sender/recipient readiness,
owner/inbox parameters, migration `0004`, IAM, concurrency and route-table checks.
Select the newly reviewed backend release's immutable digest containing both
reporting handlers; verify provenance against that release. Do not select by
"latest" or newest ECR timestamp: a legacy-cleanup digest is unsuitable.
See [reporting deployment checklist](reporting.md).

A sensible future approach is a separate reporting update workflow, triggered by
relevant reporting code after validation, using a reviewed immutable artifact and
an UPDATE change set. Image-only updates can be automated after initial setup if
checks prove no role, schedule, bucket, database, endpoint, queue or retention
changes. Infrastructure/recipient/owner changes retain explicit review. Preserve
schedule state and retained objects/delivery markers. This future automation is
not implemented by this task, and backend releases currently do not refresh report images.

## Stop, failure and rollback

- Do not cancel a running migration or CloudFormation update halfway through.
  Stop further pushes/manual dispatches and coordinate operators; inspect the
  current run, stack events and runner verification before retrying.
- A validation/gate failure deploys nothing. An image may remain in ECR if a later
  change-set or migration step fails. Never manually execute an abandoned change set.
- Roll back API/frontend artifacts through a reviewed image-only change set/release;
  preserve the latest successful schema marker and additive revision `0004`.
  Pushing old migration history will require preparation rather than silently downgrade.
  Never Alembic-downgrade `0004`: it deletes Meetings. Preserve authenticated access.
- For database corruption, restore the snapshot into a **new cluster** and plan
  cutover/reconciliation of writes after the snapshot; never delete/recreate the
  existing Aurora cluster as routine rollback.
- For reporting failures, disable schedule/queue consumption only through an
  authorized recovery action, inspect DLQs and preserve bucket/table delivery
  state. Do not replay raw async envelopes or erase `SENT` markers casually.
- Keep live and rollback ECR digests and the release snapshot through the agreed
  recovery window. A health warning after stack completion needs investigation;
  it does not automatically reverse the migration or CloudFormation update.

This policy was implemented and tested locally. No push, commit, remote workflow
setting change, AWS mutation, production migration or deployment was performed.
