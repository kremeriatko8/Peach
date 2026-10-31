#!/usr/bin/env bash
# Static validation only, in isolation from all local/remote state and backends.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
command -v terraform >/dev/null || { echo 'terraform >=1.13.5 is required' >&2; exit 1; }
terraform -chdir="${ROOT}/infra" fmt -check -recursive
WORK="$(mktemp -d)"
trap 'rm -rf "${WORK}"' EXIT
# Copy HCL only. Never copy .terraform, state, plans, private inputs, or credentials.
cp "${ROOT}"/infra/*.tf "${WORK}/"
if [[ -f "${ROOT}/infra/.terraform.lock.hcl" ]]; then
  cp "${ROOT}/infra/.terraform.lock.hcl" "${WORK}/"
fi
export TF_IN_AUTOMATION=1 CHECKPOINT_DISABLE=1 AWS_EC2_METADATA_DISABLED=true
unset TF_CLOUD_ORGANIZATION TF_WORKSPACE TF_TOKEN_app_terraform_io
unset TF_CLI_ARGS TF_CLI_ARGS_init TF_CLI_ARGS_validate TF_CLI_ARGS_fmt TF_CLI_ARGS_test
# No ambient AWS identity may reach a local validation or mock-test process.
unset AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN AWS_PROFILE AWS_DEFAULT_PROFILE
unset AWS_ROLE_ARN AWS_WEB_IDENTITY_TOKEN_FILE AWS_CONTAINER_CREDENTIALS_RELATIVE_URI AWS_CONTAINER_CREDENTIALS_FULL_URI
export AWS_SHARED_CREDENTIALS_FILE=/dev/null AWS_CONFIG_FILE=/dev/null
# init -backend=false downloads public provider packages, never contacts HCP/AWS.
terraform -chdir="${WORK}" init -backend=false -input=false -lockfile=readonly
terraform -chdir="${WORK}" validate

mkdir -p "${WORK}/tests"
cp "${ROOT}"/infra/tests/*.tftest.hcl "${WORK}/tests/"
terraform -chdir="${WORK}" test -test-directory=tests

# Validate the exact non-secret inventory inputs without supplying real secrets.
mkdir -p "${WORK}/input-tests"
cp "${ROOT}"/infra/input-tests/*.tftest.hcl "${WORK}/input-tests/"
cp "${ROOT}/docs/terraform-live-input-worksheet.json" "${WORK}/input-tests/observed-public-inputs.json"
terraform -chdir="${WORK}" test -test-directory=input-tests -var-file="${ROOT}/infra/terraform.tfvars"
