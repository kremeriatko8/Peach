# Remaining backend release permissions — NOT APPLIED

Applies to the existing peach-backend/peach-migrations UPDATE path only.
Live policy enumeration and iam:SimulatePrincipalPolicy are denied, so effective
permissions cannot be exhaustively established. No denied writes were probed.
The owner reports PeachMigrationChangeSetCreate is now attached; no release retry
was made to test that mutation.

| Workflow phase | Required actions | Evidence/status |
|---|---|---|
| Existing preflight | sts:GetCallerIdentity; cloudformation:DescribeStacks, DescribeStackResource, ValidateTemplate; secretsmanager:GetSecretValue on the one existing secret; lambda:GetFunctionConfiguration on backend; rds:DescribeDBClusters, DescribeDBClusterSnapshots; ecr:DescribeRepositories | Passed in authorized preflight/release; do not expand these grants. |
| ECR publish | ecr:GetAuthorizationToken; InitiateLayerUpload, UploadLayerPart, CompleteLayerUpload, BatchCheckLayerAvailability, PutImage, DescribeImages on peach-backend | Published successfully. Token uses Resource *; repository operations stay repository-scoped. |
| Backend change set | cloudformation:CreateChangeSet, DescribeChangeSet, ExecuteChangeSet; DescribeStacks waiter/output reads | Creation/review passed. Execution is still untested; no current grant export is readable. Supplement includes ExecuteChangeSet on only peach-backend to cover this potential gap. |
| Migration CLI deploy | cloudformation:GetTemplateSummary, DescribeStacks, CreateChangeSet, DescribeChangeSet, ExecuteChangeSet; DeleteChangeSet for empty-set cleanup; GetTemplate/DescribeStackEvents for review | GetTemplateSummary and CreateChangeSet were confirmed denied in previous attempts; owner reports grants added. Later actions remain potential gaps. |
| Both existing Lambda updates | lambda:GetFunction, GetFunctionConfiguration, provider configuration/concurrency reads, ListTags, UpdateFunctionCode, UpdateFunctionConfiguration, TagResource, UntagResource; iam:PassRole on existing execution role; ECR retrieval reads | Backend metadata read works. Migration GetFunction was previously denied. Writes/provider reads remain untested. Supplement covers exact functions/role. |
| Migration role inspection | iam:GetRole, GetRolePolicy, ListRolePolicies, ListAttachedRolePolicies, ListRoleTags | Scoped metadata reads only. No create/update/delete role or managed-policy grants. |
| Existing migration log group | logs:DescribeLogGroups, DescribeResourcePolicies, DescribeIndexPolicies; GetDataProtectionPolicy, ListTagsForResource; TagResource/UntagResource, retention updates if needed | Existing group is readable via FilterLogEvents; provider reads/writes may be gaps. No group creation/deletion or log-policy modification granted. |
| Runner verification | lambda:GetFunctionConfiguration waiter; lambda:InvokeFunction on peach-migrations; validation of returned JSON and preservation flags | Not yet invoked. IAM cannot constrain InvokeFunction's payload: migrate authorization is operational, not enforced by this policy. |
| Backend completion/health | cloudformation:DescribeStacks; lambda:GetFunction/GetFunctionConfiguration for final digest/state; public GET /health | Health URL is public; no extra IAM permission. Script only warns on health failure, so independently require successful health before PASS. |

`operator-backend-release-completion.json` is ONE temporary customer-managed
supplement, not a replacement for original policies. It includes the already
added migration CFN actions to avoid another fragmented patch, plus the unverified
downstream gaps, all bound to exact existing resources. Attach after administrator
review only to sofiia, e.g. PeachBackendReleaseCompletion; not to reporting deploy
or GitHub roles. Preserve existing policies. Compact size is below 6144 characters.
Regional Logs discovery APIs require Resource *; scoped APIs use the correct ARN
form. No account-wide CloudFormation/Lambda/IAM grants. No secret grants are added.

No RDS mutations, new snapshots, networking mutations, IAM mutations, resource
creation/deletion, backend function invocation, reporting deployment or cleanup
permissions are added. No execution-role replacement is allowed. This covers the
reviewed update path and ordinary rollback to previous Lambda code/configuration;
other future template changes require separate review.

An existing ECR Lambda retrieval policy must remain compatible; there is no
SetRepositoryPolicy grant. A new denial caused by SCPs/boundaries/resource policies
must be reviewed instead of broadening this document blindly. IAM simulation
metadata is not a deployment proof. Do not retry until separately instructed.
