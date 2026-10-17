# Agenda readiness permissions (prepared only; NOT ATTACHED)

`readiness-readonly.json` is a narrowly scoped additive read policy for the existing
operator. It grants no inference, deployment, IAM mutation, snapshot, database or
budget mutation. Have an administrator review it; supplying the equivalent read
results is an alternative. Existing read permissions are not repeated here.

| Denied action | Resource scope | Why | Gate |
|---|---|---|---|
| bedrock-mantle:GetProject / GetModel | arn:aws:bedrock-mantle:us-east-1:968053399627:project/default | Exact project/model metadata | Essential before activation; does not prove inference entitlement |
| budgets:ViewBudget | arn:aws:budgets::968053399627:budget/* | Find duplicates and check $5 email notification | Essential before paid activation; wildcard names needed for discovery |
| ecr:GetLifecyclePolicy | arn:aws:ecr:us-east-1:968053399627:repository/peach-backend | Protect shared report/rollback digests | Essential before image publication |
| lambda:GetAccountSettings | * (API has no function-level scope), us-east-1 condition | Capacity for concurrency 1 while keeping required unreserved capacity | Essential before parser deployment |
| servicequotas:ListServiceQuotas | * (list API), us-east-1 condition | Inspect model throughput limits | Essential capacity review; admin can provide exact quota results instead |
| cloudformation:DescribeStacks | peach-ai/*, peach-budget/* stack ARNs | Distinguish absence from denied access, avoid duplicates | Essential before create/update selection |
| lambda:GetFunction | exact peach-agenda-parser function ARN | Inspect image/state | Essential before smoke/release |
| bedrock:ListFoundationModels | * | Legacy model catalog | Optional; omitted from policy since Mantle metadata is the required path |
| bedrock:GetFoundationModelAvailability | arn:aws:bedrock:us-east-1::foundation-model/anthropic.claude-opus-5-5 | Legacy availability lookup | Optional for a Mantle-only model; omitted |
| iam:SimulatePrincipalPolicy | arn:aws:iam::968053399627:user/sofiia | Optional operator inference-policy simulation | Optional; admin effective-policy review is sufficient; omitted |

Additional parser GetFunction/GetFunctionConfiguration/GetFunctionConcurrency and AI
DescribeChangeSet/GetTemplate reads are in the separate
`release-verification-readonly.json` for later exact-config smoke and reviewed
change-set verification. They are unnecessary for resolving the current initial
readiness denials and were not all separately attempted.
Backend/auth/frontend reads and S3 ListBucket/GetObject already worked. Default
operator reporting reads are denied, but the already configured reporting profile
can perform those reads; no reporting permissions are added here.

`ListServiceQuotas` resource '*' is limited to the region and this one list action,
not arbitrary service or mutation access. If the administrator supplies exact
quota ARNs/codes, replace discovery with GetServiceQuota on those resources. Do not
invent a Mantle quota code from legacy Bedrock models. Lambda reserved concurrency
has both an account total and a minimum unreserved pool constraint.

Optional evidence collection needs logs:FilterLogEvents on
`arn:aws:logs:us-east-1:968053399627:log-group:/aws/lambda/peach-agenda-parser:*`.
It is not necessary to enable paid CloudTrail inference data events.

Future runtime permission is separately declared by infra/ai.yml:
`bedrock-mantle:CreateInference` on the default project with exact model condition.
It is deliberately NOT granted to the laptop by this read-only policy. Laptop
`llm-hello` requires separately approved CreateInference permission and paid-call
approval. Budget create/update authorization uses `budgets:ModifyBudget` on the
reviewed budget resource; the API operation name CreateBudget is not an IAM action
to grant blindly. No administrator policy is requested.

## Existing identities checked on October 17

The only configured identities are `default` (IAM user `sofiia`) and
`peach-reports-deploy` (assumed project reporting role, sourced from default).
Both passed STS account verification and both denied the initial policy's reads.
No other configured role/profile can resolve these blockers. The GitHub deployment
role trusts GitHub OIDC on main; it is not an authorized laptop fallback. Do not
alter that trust, trigger CI or extend reporting permissions to obtain these reads.
Private exact read results are in ignored
`reports-local/agenda/existing-profile-read-checks.json`.

## Minimum Console actions (administrator, after separate permission approval)

1. Sign in to account **968053399627** with an existing authorized IAM administrator.
2. Open **IAM → Users → sofiia → Permissions → Add permissions → Create inline policy**.
3. Select **JSON**, paste the complete `readiness-readonly.json`, choose **Next**,
   review the seven read actions and their scopes, name it
   `PeachAgendaReadinessReadOnly`, and create the policy. This attachment is an IAM
   mutation for the administrator, not something this preparation performs.
4. Report that the reads are available and provide the intended budget email
   privately. Re-run the read checks before approving any resources. If a boundary
   or SCP still denies a read, the administrator must diagnose that exact denial;
   do not add broad managed policies or change reporting IAM.
5. Before the later disabled-parser release, separately review/grant
   `release-verification-readonly.json` if those precise reads are not already
   permitted. Optional log evidence access is described above; do not grant
   inference to the operator merely to inspect metadata.

An administrator can instead supply the exact read results for review, but the
fail-closed automated release still needs its own permitted reads to recheck live
state. A successful model metadata read alone does not prove runtime inference
entitlement. No model call, subscription, budget creation, snapshot or deployment
is part of these instructions.
