#!/usr/bin/env bash
# Create the IAM role GitHub Actions assumes to deploy, and point the
# repository at it. No access key is created or stored anywhere.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
TEMPLATE="${ROOT}/infra/github-oidc.yaml"

log() { printf '\033[36m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[33m==>\033[0m %s\n' "$*" >&2; }
die() { printf '\033[31merror:\033[0m %s\n' "$*" >&2; exit 1; }

if [[ -f "${ROOT}/.env" ]]; then
  # Variables already exported win over .env: `AWS_REGION=eu-central-1 make x`
  # must not be quietly reset to the region .env names.
  preset="$(export -p)"
  set -a
  # shellcheck disable=SC1091
  source "${ROOT}/.env"
  set +a
  eval "${preset}"
fi

for var in AWS_PROFILE AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN; do
  [[ -n "${!var:-}" ]] || unset "${var}"
done

PROJECT_NAME="${PROJECT_NAME:-peach}"
STACK_NAME="${GITHUB_ROLE_STACK_NAME:-${PROJECT_NAME}-github-oidc}"
AWS_REGION="${AWS_REGION:-${AWS_DEFAULT_REGION:-us-east-1}}"
export AWS_DEFAULT_REGION="${AWS_REGION}"

command -v aws >/dev/null 2>&1 || die "aws cli is required"
aws sts get-caller-identity >/dev/null 2>&1 \
  || die "no usable AWS credentials - set AWS_PROFILE or the AWS_* keys in .env"

# --- which repository ---------------------------------------------------------

REPO="${GITHUB_REPO:-}"
if [[ -z "${REPO}" ]]; then
  ORIGIN="$(git -C "${ROOT}" remote get-url origin 2>/dev/null || true)"
  # Both git@github.com:owner/repo.git and https://github.com/owner/repo.git
  REPO="$(printf '%s' "${ORIGIN}" | sed -E 's#^.*github\.com[:/]##; s#\.git$##')"
fi
[[ "${REPO}" =~ ^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$ ]] \
  || die "could not work out the repo - set GITHUB_REPO=owner/repo in .env"

SUBJECT_CLAIM="${GITHUB_SUBJECT_CLAIM:-ref:refs/heads/main}"
[[ "${SUBJECT_CLAIM}" == "ref:refs/heads/main" ]] || die "deployment trust must be restricted to main"

# Ask GitHub for the actual prefix, including immutable IDs when enabled.
# Never guess based on creation date, or trust both old and new subjects.
command -v python3 >/dev/null 2>&1 || die "python3 is required"
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  OIDC_CONFIG="$(gh api "repos/${REPO}/actions/oidc/customization/sub")"
else
  command -v curl >/dev/null 2>&1 || die "curl is required (or authenticated gh)"
  OIDC_CONFIG="$(curl --fail --silent --show-error \
    "https://api.github.com/repos/${REPO}/actions/oidc/customization/sub")"
fi
SUBJECT_PREFIX="$(printf '%s' "${OIDC_CONFIG}" | python3 -c '
import json, re, sys
config = json.load(sys.stdin)
prefix = config.get("sub_claim_prefix", "")
match = re.fullmatch(r"repo:([A-Za-z0-9_.-]+)(@[0-9]+)?/([A-Za-z0-9_.-]+)(@[0-9]+)?", prefix)
if (config.get("use_default") is not True or not match
        or f"{match[1]}/{match[3]}" != sys.argv[1]):
    sys.exit("Unsupported or mismatched GitHub OIDC configuration; refusing to change trust")
print(prefix)
' "${REPO}")"

log "repository ${REPO}"
log "trusting only ${SUBJECT_PREFIX}:${SUBJECT_CLAIM}"

# --- the account may already have a GitHub provider ---------------------------

# Preserve the stack's original ownership choice. Rediscovering its own provider
# as "external" would make CreateProvider false and delete that provider on update.
if EXISTING_PROVIDER="$(aws cloudformation describe-stacks --stack-name "${STACK_NAME}" \
  --query "Stacks[0].Parameters[?ParameterKey=='ExistingProviderArn'].ParameterValue | [0]" \
  --output text 2>&1)"; then
  [[ "${EXISTING_PROVIDER}" != "None" ]] || die "stack is missing ExistingProviderArn parameter"
elif [[ "${EXISTING_PROVIDER}" == *"(ValidationError)"* && "${EXISTING_PROVIDER}" == *"does not exist"* ]]; then
  # Only a new stack discovers providers that were created elsewhere.
  EXISTING_PROVIDER="$(aws iam list-open-id-connect-providers \
    --query "OpenIDConnectProviderList[?ends_with(Arn, '/token.actions.githubusercontent.com')]|[0].Arn" \
    --output text)"
  [[ "${EXISTING_PROVIDER}" == "None" ]] && EXISTING_PROVIDER=""
else
  die "cannot inspect existing stack: ${EXISTING_PROVIDER}"
fi

if [[ -n "${EXISTING_PROVIDER}" ]]; then
  log "reusing the GitHub OIDC provider already in this account"
else
  log "the stack creates or continues managing the GitHub OIDC provider"
fi

# --- deploy -------------------------------------------------------------------

if ! aws cloudformation deploy \
  --stack-name "${STACK_NAME}" \
  --template-file "${TEMPLATE}" \
  --parameter-overrides \
    "ProjectName=${PROJECT_NAME}" \
    "GitHubRepo=${REPO}" \
    "GitHubSubjectPrefix=${SUBJECT_PREFIX}" \
    "SubjectClaim=${SUBJECT_CLAIM}" \
    "ExistingProviderArn=${EXISTING_PROVIDER}" \
  --capabilities CAPABILITY_NAMED_IAM \
  --no-fail-on-empty-changeset \
  --tags "PROJECT_NAME=${PROJECT_NAME}"; then
  warn "deploy failed - most recent failure reasons:"
  aws cloudformation describe-stack-events --stack-name "${STACK_NAME}" \
    --max-items 30 \
    --query 'StackEvents[?ResourceStatus==`CREATE_FAILED`||ResourceStatus==`UPDATE_FAILED`].[LogicalResourceId,ResourceStatusReason]' \
    --output table >&2 || true
  exit 1
fi

ROLE_ARN="$(aws cloudformation describe-stacks --stack-name "${STACK_NAME}" \
  --query "Stacks[0].Outputs[?OutputKey=='RoleArn'].OutputValue" --output text)"

log "role ready: ${ROLE_ARN}"

# --- tell the repository about it ---------------------------------------------

# Not a secret: the ARN is useless without a token from this repo's workflows.
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
  log "setting repository variables with gh"
  gh variable set AWS_DEPLOY_ROLE_ARN --repo "${REPO}" --body "${ROLE_ARN}"
  gh variable set AWS_REGION --repo "${REPO}" --body "${AWS_REGION}"
  echo
  echo "  Done. Write \"deploy\" in a commit message on main and the backend ships."
else
  echo
  echo "  gh is not installed or not logged in. Set these two repository"
  echo "  variables by hand, under Settings -> Secrets and variables -> Actions:"
  echo
  echo "    AWS_DEPLOY_ROLE_ARN = ${ROLE_ARN}"
  echo "    AWS_REGION          = ${AWS_REGION}"
  echo
fi
