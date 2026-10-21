# Agenda IAM administration — Nova Lite adaptation, October 18, 2026

Local policy proposals only. This adaptation made NO live IAM or AWS changes.
The assignment required Claude Opus 5.5; AWS reported it unavailable for the account
with zero Mantle quotas. Nova Lite was chosen to avoid external approval delays.
This is a documented deviation, **not an instructor-approved substitution**.

## Policy set and exact required live changes before deployment

Use customer managed policies, not user inline policies (2,048 aggregate characters).
Each file is under the 6,144-character managed-document limit. Account 968053399627,
region us-east-1; operator sofiia through existing PeachAgendaOperators group.

| JSON | Existing managed policy | Nova action needed |
|---|---|---|
| operator-readiness.json | PeachAgendaReadiness | New default: exact-Nova GetFoundationModel plus region-limited, unscoped GetFoundationModelAvailability |
| parser-runtime-boundary.json | PeachAgendaParserBoundary | New default version: replace CreateInference + Mantle condition with exact-model bedrock:InvokeModel; keep own log writes |
| optional-laptop-inference.json | PeachAgendaLaptopInference | New default version with same exact Nova InvokeModel; keep unattached unless future laptop paid testing is separately approved |
| operator-release-writes.json | PeachAgendaRelease | No Nova changes; retain prior hardened scope |
| operator-parser-provisioning.json | PeachAgendaParserProvisioning | No Nova changes; mandatory boundary ARN and anti-removal/replacement restrictions stay |
| optional-iam-audit.json | PeachAgendaIAMAudit | No Nova changes; metadata only |

`readiness-readonly.json` is an alternative incremental metadata proposal, NOT an
additional attachment alongside operator-readiness.json. release-verification-readonly.json
is also already covered by the full bundle. Do not create duplicate policies.

Exact target ARN (no account component because this is an AWS foundation model):
`arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-lite-v1:0`.
Converse non-streaming requires bedrock:InvokeModel, not an invented bedrock:Converse
action. No streaming or cross-region permissions, IAM model wildcard, Marketplace
subscription or Mantle project permissions are needed for this selected path.

The boundary policy is created/updated only by the administrator. Do NOT attach it
as an ordinary policy to sofiia or set it as sofiia's boundary. infra/ai.yml requires
its ARN on the new parser role and grants the same Nova InvokeModel permission in
that role's inline policy. Both inline grant and boundary must allow the operation.
Runtime keeps only own log writes besides inference; no DB/VPC/S3/report access.
Generated parser role remains scoped to role/peach-ai-Role-*; CreateRole and inline
policy updates require the exact boundary, with deletion/replacement prevented.
The operator cannot edit the managed boundary through the provisioning bundle.

## Ordered Console checklist — ONLY after separate IAM approval

1. Confirm account 968053399627. Use an existing authorized IAM administrator; no
   Root credentials/access keys should be placed in the workspace.
2. Inspect current defaults/attachments for the six policies. The previous verified
   Claude defaults matched the then-local files; this Nova adaptation intentionally
   creates local/live drift in the three changed managed policies. Preserve the
   existing four group attachments and sofiia membership.
3. IAM → Policies → PeachAgendaReadiness → Edit → JSON: paste saved operator-readiness.json,
   validate, save a new default version. Keep the previous version for rollback.
4. Repeat for PeachAgendaParserBoundary using parser-runtime-boundary.json. This
   policy is not attached to user/group and must remain administrator-owned.
5. Repeat for PeachAgendaLaptopInference if preparing the future laptop path, but
   do not attach it or authorize a paid call as part of metadata verification.
6. Leave Release, ParserProvisioning, IAMAudit and all reporting/GitHub role policies
   unchanged. Do not detach or replace existing working policies. If five versions
   already exist, stop for a separately reviewed version-retention decision.
7. Sign out of the administrative session. Re-verify actual default documents with
   sofiia, then run model/account/region/quotas reads only. Confirm the exact model
   is active and supports on-demand; do not interpret a denied read as unavailability.
8. No model agreement, subscription, quota request, budget, snapshot, DB query,
   migration, parser activation or deployment is part of this IAM-only procedure.

## Readiness facts, permissions and gates

Earlier read-only checks verified Nova Lite's 200 RPM / 4M TPM on-demand quotas
(L-E386A278 / L-70423BF8), but model/account metadata reads were denied. These
positive quotas are not proof of entitlement or an actual successful inference.
The release wrapper fails closed on model metadata, regional authorization,
entitlement and any supplied agreement status. If AWS's Amazon-model response is
not compatible, inspect it explicitly before reviewing any change to the predicate.
The model has documented in-region support; avoid introducing cross-region routing.

The low-traffic lab now omits reserved concurrency and uses shared quota 10;
no concurrency quota increase is required. Shared ECR 'keep last 3, any tag' policy threatens
report/rollback images and is a release blocker. $5 email budget was absent, manual
snapshot stale, actual Aurora revision not inspected. None were resolved here.
No new permissions to mutate those controls are silently added.

The core backend/migrations/frontend/auth stacks previously had no persisted
CloudFormation service role; AI/budget were absent. Release rechecks mutable stacks
and stops if an unreviewed service RoleARN appears. Stack ARN scopes do NOT cap
underlying service-role permissions. Default CF execution uses the scoped operator
credentials. Never broaden PassRole to arbitrary CF roles. Existing API/migration
execution role and reporting/GitHub deployment roles require no Nova updates.

GetSecretValue remains exact-secret scoped because backend-preflight compares the
existing secret with deployed API DATABASE_URL to preserve credentials. Snapshot
creation scopes match scripts/snapshot-backend.sh's peach-pre-ownership-* naming.
Budget ModifyBudget/tagging is exact-budget scoped; seven-day log retention cannot
be removed by the hardened bundle. Parser-resource delete rights support initial
CloudFormation rollback only. No production DB delete/restore/downgrade permission.

## Cost/approval separation and validation limits

No fixed-capacity purchase is needed. Standard price checked October 18 is
$0.06/$0.24 per million input/output tokens, configured explicitly. Budget is an
alert, not a cap; both attempts/failed calls may bill. Preserve disabled mode,
reserved concurrency, input/output bounds, no SDK retries and explicit paid CLI flag.
Granting IAM never supplies application-level approval for paid calls or release.

Run JSON/action/ARN/size checks locally and Console JSON editor validation before
creating versions. AWS Access Analyzer validation was previously denied to the
operator; local checks do not prove effective IAM/SCP/boundary authorization or
real provider output behavior. GetGroup/ListAttachedGroupPolicies are optional
read gaps for group inventory; do not add broad IAM management rights to inspect it.

References:
- https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html
- https://docs.aws.amazon.com/nova/latest/userguide/tool-use-definition.html
- https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_iam-quotas.html
- https://docs.aws.amazon.com/IAM/latest/UserGuide/access_policies_manage-edit.html


IAM resource-scope correction verified against the public Bedrock authorization
catalog: GetFoundationModel supports the exact foundation-model ARN, but
GetFoundationModelAvailability has no resource-level scope. Its separate statement
uses Resource="*" with aws:RequestedRegion=us-east-1. This grants only availability
metadata, never inference. Runtime/boundary/laptop InvokeModel remains exact-ARN
scoped; no model wildcard inference or streaming permission is granted.
