#!/usr/bin/env bash
# Speculative remote plan in HCP (peach-dev, pinned in infra/versions.tf).
# HCP never applies CLI plans on this VCS-driven workspace. No init/apply/destroy here.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ "${PEACH_APPROVE_INFRA_PLAN:-}" == yes ]] || {
  echo 'Remote planning contacts HCP/AWS. Requires PEACH_APPROVE_INFRA_PLAN=yes after approval.' >&2
  exit 1
}
export TF_IN_AUTOMATION=1
unset TF_CLI_ARGS TF_CLI_ARGS_plan TF_CLOUD_ORGANIZATION TF_WORKSPACE
exec terraform -chdir="${ROOT}/infra" plan -input=false
