#!/usr/bin/env bash
# Explicit, manual AWS mutation. Never called from CI or ordinary backend release.
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
[[ "${PEACH_APPROVE_AI_DEPLOY:-}" == yes ]] || { echo 'Requires explicit approval: PEACH_APPROVE_AI_DEPLOY=yes' >&2; exit 1; }
: "${AI_PARAMETERS_FILE:?Supply a reviewed CloudFormation parameter JSON file}"
python3 "${ROOT}/scripts/validate-ai-parameters.py" "${AI_PARAMETERS_FILE}"

# Create a reviewable change set only. Execution and activation are separate approvals.
aws cloudformation create-change-set --region us-east-1 \
  --stack-name "${PROJECT_NAME:-peach}-ai" \
  --change-set-name "${AI_CHANGE_SET_NAME:-agenda-parser-reviewed}" \
  --change-set-type "${AI_CHANGE_SET_TYPE:-CREATE}" \
  --template-body "file://${ROOT}/infra/ai.yml" \
  --parameters "file://${AI_PARAMETERS_FILE}" --capabilities CAPABILITY_IAM
