#!/usr/bin/env bash
# Future remote plan only. No automatic init, apply, destroy or backend fallback.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ "${PEACH_APPROVE_INFRA_PLAN:-}" == yes ]] || {
  echo 'Remote planning contacts HCP/AWS. Requires PEACH_APPROVE_INFRA_PLAN=yes after approval.' >&2
  exit 1
}
: "${TF_CLOUD_ORGANIZATION:?Set the reviewed HCP organization}"
: "${TF_WORKSPACE:?Set the reviewed HCP workspace}"
export TF_IN_AUTOMATION=1
unset TF_CLI_ARGS TF_CLI_ARGS_plan
exec terraform -chdir="${ROOT}/infra" plan -input=false
