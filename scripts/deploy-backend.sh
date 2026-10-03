#!/usr/bin/env bash
# Publish the backend image, migrate through the private runner, then update
# the public Lambda only after successful migration. Preserve Aurora and write
# BACKEND_URL into .env for the separate frontend deployment.
#
# Existing-stack release only. --preflight-only performs read-only preparation.
set +x
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE="${ROOT}/infra/backend.yaml"
ENV_FILE="${ROOT}/.env"

log() { printf '\033[36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33m==>\033[0m %s\n' "$*" >&2; }
die() { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }

# --- configuration ----------------------------------------------------------

# .env is the same file Compose reads; anything already exported wins over it.
if [[ -f "${ENV_FILE}" ]]; then
  # Variables already exported win over .env: `AWS_REGION=eu-central-1 make x`
  # must not be quietly reset to the region .env names.
  preset="$(export -p)"
  set -a
  # shellcheck disable=SC1091
  source "${ENV_FILE}"
  set +a
  eval "${preset}"
fi

unset GOOGLE_CLIENT_ID GOOGLE_CLIENT_SECRET

# A blank AWS_PROFILE is read as a profile literally named "", and blank keys
# short-circuit the credential chain - which is exactly what a .env full of
# empty placeholders hands us. Treat empty as absent.
for var in AWS_PROFILE AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN; do
  [[ -n "${!var:-}" ]] || unset "${var}"
done

PROJECT_NAME="${PROJECT_NAME:-peach}"
STACK_NAME="${STACK_NAME:-${PROJECT_NAME}-backend}"
AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
export AWS_DEFAULT_REGION="${AWS_REGION}"

ECR_REPOSITORY="${ECR_REPOSITORY:-${PROJECT_NAME}-backend}"
LAMBDA_ARCHITECTURE="${LAMBDA_ARCHITECTURE:-arm64}"
case "${LAMBDA_ARCHITECTURE}" in
  arm64) CFN_ARCHITECTURE=arm64 ;;
  amd64) CFN_ARCHITECTURE=x86_64 ;;
  *) die "LAMBDA_ARCHITECTURE must be arm64 or amd64, got '${LAMBDA_ARCHITECTURE}'" ;;
esac

# CloudFormation copies stack tags onto every resource it can tag; the template
# also sets the same tag on each resource explicitly.
TAGS=("PROJECT_NAME=${PROJECT_NAME}")

# --- helpers ----------------------------------------------------------------

# Rewrite one KEY=VALUE in .env, leaving every other line - credentials very
# much included - exactly as it was.
env_set() {
  KEY="$1" VALUE="$2" ENV_FILE="${ENV_FILE}" python3 - <<'PY'
import os, re

key, value, path = os.environ["KEY"], os.environ["VALUE"], os.environ["ENV_FILE"]
lines = open(path).read().splitlines() if os.path.exists(path) else []
pattern = re.compile(rf"^{re.escape(key)}=")

for i, line in enumerate(lines):
    if pattern.match(line):
        lines[i] = f"{key}={value}"
        break
else:
    lines.append(f"{key}={value}")

open(path, "w").write("\n".join(lines) + "\n")
PY
  log "wrote ${1}=${2} to .env"
}

RELEASE_MODE=release
case "${1:-}" in
  "") ;;
  --preflight-only) RELEASE_MODE=preparation ;;
  *) die "usage: deploy-backend.sh [--preflight-only]" ;;
esac
[[ "$#" -le 1 ]] || die "usage: deploy-backend.sh [--preflight-only]"

# --- preflight --------------------------------------------------------------

for tool in aws docker python3; do
  command -v "${tool}" >/dev/null 2>&1 || die "${tool} is required but not installed"
done
docker info >/dev/null 2>&1 || die "docker daemon is not running"

ACCOUNT_ID="$(aws sts get-caller-identity --query Account --output text 2>/dev/null)" \
  || die "no usable AWS credentials - set AWS_PROFILE or the AWS_* keys in .env"
CALLER="$(aws sts get-caller-identity --query Arn --output text)"
log "account ${ACCOUNT_ID} in ${AWS_REGION} as ${CALLER}"

# Require the existing backend: migrate its database before updating public code.
# A new installation needs database/bootstrap infrastructure provisioned separately.
FUNCTION_NAME="$(aws cloudformation describe-stacks --stack-name "${STACK_NAME}" \
  --query "Stacks[0].Outputs[?OutputKey=='FunctionName'].OutputValue | [0]" \
  --output text --no-cli-pager)" || die "existing backend stack required"
[[ -n "${FUNCTION_NAME}" && "${FUNCTION_NAME}" != None ]] || die "existing backend function required"
MIGRATION_STACK_NAME="${MIGRATION_STACK_NAME:-${PROJECT_NAME}-migrations}"
AUTH_STACK_NAME="${AUTH_STACK_NAME:-${PROJECT_NAME}-auth}"

# All sensitive files are private and removed on exit.
WORK_DIR="$(mktemp -d)"
chmod 700 "${WORK_DIR}"
trap 'rm -rf "${WORK_DIR}"' EXIT
umask 077
PARAMS_FILE="${WORK_DIR}/backend.json"
RUNNER_PARAMS="${WORK_DIR}/runner.json"
AUTH_FILE="${WORK_DIR}/auth.json"
RESULT_FILE="${WORK_DIR}/result.json"
export PROJECT_NAME CFN_ARCHITECTURE
aws cloudformation describe-stacks --stack-name "${AUTH_STACK_NAME}" \
  --query 'Stacks[0].Outputs' --output json --no-cli-pager \
  | python3 "${ROOT}/scripts/cognito-snapshot.py" > "${AUTH_FILE}"
python3 "${ROOT}/scripts/backend-preflight.py" "${STACK_NAME}" "${FUNCTION_NAME}" \
  "${AUTH_FILE}" "${PARAMS_FILE}" "${RUNNER_PARAMS}" "${RELEASE_MODE}"

# --- ecr --------------------------------------------------------------------

# The repository lives outside the stack: the function cannot be created until
# there is an image to run, so the push has to happen first.
REGISTRY="${ACCOUNT_ID}.dkr.ecr.${AWS_REGION}.amazonaws.com"
aws ecr describe-repositories --repository-names "${ECR_REPOSITORY}" >/dev/null \
  || die "existing backend ECR repository required; refusing recreation"

aws cloudformation validate-template --template-body "file://${TEMPLATE}" >/dev/null
aws cloudformation validate-template --template-body "file://${ROOT}/infra/migrations.yaml" >/dev/null
if [[ "${RELEASE_MODE}" == preparation ]]; then
  log "Read-only preflight passed. Next: explicit snapshot, then controlled release."
  exit 0
fi

if [[ -z "${IMAGE_TAG:-}" || "${IMAGE_TAG}" == "latest" ]]; then
  if git -C "${ROOT}" rev-parse --git-dir >/dev/null 2>&1; then
    IMAGE_TAG="$(git -C "${ROOT}" rev-parse --short=12 HEAD)"
    # A dirty tree gets a unique tag, or CloudFormation would see the same
    # ImageUri as last time and leave the function on the old image.
    [[ -z "$(git -C "${ROOT}" status --porcelain -- backend)" ]] \
      || IMAGE_TAG="${IMAGE_TAG}-dirty-$(date -u +%Y%m%d%H%M%S)"
  else
    IMAGE_TAG="$(date -u +%Y%m%d%H%M%S)"
  fi
fi
IMAGE_URI="${REGISTRY}/${ECR_REPOSITORY}:${IMAGE_TAG}"

log "building ${IMAGE_URI} for linux/${LAMBDA_ARCHITECTURE}"
aws ecr get-login-password --region "${AWS_REGION}" \
  | docker login --username AWS --password-stdin "${REGISTRY}" >/dev/null

# Lambda accepts a single-platform image manifest only. buildx otherwise adds
# provenance and SBOM attestations, which turn the push into a manifest list
# that CreateFunction rejects.
docker buildx build \
  --platform "linux/${LAMBDA_ARCHITECTURE}" \
  --target lambda \
  --provenance=false \
  --sbom=false \
  --tag "${IMAGE_URI}" \
  --push \
  "${ROOT}/backend"

# Pin both functions to the same immutable published image.
IMAGE_DIGEST="$(aws ecr describe-images --repository-name "${ECR_REPOSITORY}" \
  --image-ids "imageTag=${IMAGE_TAG}" --query 'imageDetails[0].imageDigest' --output text)"
[[ "${IMAGE_DIGEST}" == sha256:* ]] || die "cannot resolve published image digest"
IMAGE_URI="${REGISTRY}/${ECR_REPOSITORY}@${IMAGE_DIGEST}"

# Pin both validated parameter sets to the immutable published image.
python3 - "${PARAMS_FILE}" "${RUNNER_PARAMS}" "${IMAGE_URI}" <<'PYIMAGE'
import json, sys
for path in sys.argv[1:3]:
    with open(path) as file:
        params = json.load(file)
    params = [item for item in params if item["ParameterKey"] != "ImageUri"]
    params.append({"ParameterKey": "ImageUri", "ParameterValue": sys.argv[3]})
    with open(path, "w") as file:
        json.dump(params, file)
PYIMAGE

# Prepare and inspect the EXACT change set before any database mutation.
CHANGE_SET_NAME="peach-release-$(date -u +%Y%m%d%H%M%S)-${RANDOM}"
aws cloudformation create-change-set --stack-name "${STACK_NAME}" \
  --change-set-name "${CHANGE_SET_NAME}" --change-set-type UPDATE \
  --template-body "file://${TEMPLATE}" --parameters "file://${PARAMS_FILE}" \
  --capabilities CAPABILITY_IAM --tags Key=PROJECT_NAME,Value="${PROJECT_NAME}" >/dev/null
aws cloudformation wait change-set-create-complete --stack-name "${STACK_NAME}" \
  --change-set-name "${CHANGE_SET_NAME}" \
  || die "change set creation failed or empty; no migration invoked"
CHANGE_SET_ID="$(aws cloudformation describe-change-set --stack-name "${STACK_NAME}" \
  --change-set-name "${CHANGE_SET_NAME}" --output json \
  | python3 "${ROOT}/scripts/check-backend-changeset.py")"

aws cloudformation deploy --stack-name "${MIGRATION_STACK_NAME}" \
  --template-file "${ROOT}/infra/migrations.yaml" \
  --parameter-overrides "file://${RUNNER_PARAMS}" --no-fail-on-empty-changeset \
  --tags "${TAGS[@]}"
MIGRATION_FUNCTION="$(aws cloudformation describe-stacks --stack-name "${MIGRATION_STACK_NAME}" \
  --query "Stacks[0].Outputs[?OutputKey=='FunctionName'].OutputValue | [0]" --output text)"
aws lambda wait function-updated-v2 --function-name "${MIGRATION_FUNCTION}"
FUNCTION_ERROR="$(aws lambda invoke --function-name "${MIGRATION_FUNCTION}" \
  --cli-binary-format raw-in-base64-out --cli-read-timeout 900 \
  --payload '{"action":"migrate"}' --query FunctionError --output text "${RESULT_FILE}")"
[[ -z "${FUNCTION_ERROR}" || "${FUNCTION_ERROR}" == None ]] \
  || die "migration failed; public backend was not updated; inspect migration logs"
python3 - "${RESULT_FILE}" <<'VERIFY'
import json, sys
with open(sys.argv[1]) as file:
    result = json.load(file)
verification = result.get("verification", {})
if (result.get("status") != "ok" or result.get("migrated_to") != "0003"
    or any(verification.get(key) is not True for key in (
        "owner_column", "ownership_index", "rows_preserved", "ownership_preserved"))
    or type(verification.get("rows_before")) is not int
    or verification["rows_before"] != verification.get("rows_after")):
    sys.exit("Actual database verification failed; public backend was not updated")
VERIFY
# Recheck the same immutable change set immediately before execution.
VERIFIED_CHANGE_SET_ID="$(aws cloudformation describe-change-set --stack-name "${STACK_NAME}" \
  --change-set-name "${CHANGE_SET_ID}" --output json \
  | python3 "${ROOT}/scripts/check-backend-changeset.py")"
[[ "${VERIFIED_CHANGE_SET_ID}" == "${CHANGE_SET_ID}" ]] || die "change set identity changed"
aws cloudformation execute-change-set --stack-name "${STACK_NAME}" --change-set-name "${CHANGE_SET_ID}"
aws cloudformation wait stack-update-complete --stack-name "${STACK_NAME}" \
  || die "public stack update failed; inspect rollback before retrying"

outputs() {
  aws cloudformation describe-stacks --stack-name "${STACK_NAME}" \
    --query "Stacks[0].Outputs[?OutputKey=='$1'].OutputValue" --output text
}

FUNCTION_NAME="$(outputs FunctionName)"

# --- report -----------------------------------------------------------------

API_URL="$(outputs ApiUrl)"
API_URL="${API_URL%/}"

# deploy-frontend.sh compiles the bundle against this.
env_set BACKEND_URL "${API_URL}"

echo
echo "  api        ${API_URL}"
echo "  health     ${API_URL}/health"
echo "  docs       ${API_URL}/docs"
echo "  database   $(outputs DatabaseEndpoint)"
echo "  logs       aws logs tail $(outputs LogGroupName) --follow"
echo

if curl -fsS --max-time 30 "${API_URL}/health" >/dev/null 2>&1; then
  log "GET /health answered"
else
  warn "GET /health did not answer yet - check: make logs-backend"
fi

echo "Next: make deploy-frontend (it builds against BACKEND_URL), then set"
echo "API_CORS_ORIGINS to the frontend's origin and re-run this to narrow CORS."
