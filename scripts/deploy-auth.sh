#!/usr/bin/env bash
# Explicit auth-only deployment. Secrets stream through stdin, never disk/argv.
set +x
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/auth-env.sh"
for var in GOOGLE_CLIENT_ID GOOGLE_CLIENT_SECRET COGNITO_DOMAIN_PREFIX; do
  [[ -n "${!var:-}" ]] || die "${var} must be set in root .env"
done
# Require an existing stack and preserve all its origin/domain parameters.
existing_prefix="$(aws cloudformation describe-stacks --region "${AWS_REGION}" \
  --stack-name "${AUTH_STACK_NAME}" \
  --query "Stacks[0].Outputs[?OutputKey=='CognitoDomainPrefix'].OutputValue | [0]" \
  --output text --no-cli-pager)" || die "cannot read existing auth stack"
[[ "${existing_prefix}" == "${COGNITO_DOMAIN_PREFIX}" ]] \
  || die "COGNITO_DOMAIN_PREFIX differs from the existing stack; refusing domain replacement"
export GOOGLE_CLIENT_ID GOOGLE_CLIENT_SECRET
python3 - <<'PARAMETERS' | aws cloudformation deploy \
  --region "${AWS_REGION}" --stack-name "${AUTH_STACK_NAME}" \
  --template-file "${ROOT}/infra/auth.yaml" \
  --parameter-overrides file:///dev/stdin --no-fail-on-empty-changeset
import json, os, sys
json.dump([
    {"ParameterKey": "GoogleClientId", "ParameterValue": os.environ["GOOGLE_CLIENT_ID"]},
    {"ParameterKey": "GoogleClientSecret", "ParameterValue": os.environ["GOOGLE_CLIENT_SECRET"]},
], sys.stdout)
PARAMETERS
unset GOOGLE_CLIENT_ID GOOGLE_CLIENT_SECRET
printf 'Auth stack updated. Frontend deployment is a separate command.\n'
