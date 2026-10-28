#!/usr/bin/env bash
# Transitional read-only source selection. Defaults preserve the deployed app.
peach_auth_outputs() {
  case "${PEACH_INFRA_SOURCE:-cloudformation}" in
    cloudformation)
      aws cloudformation describe-stacks --region "${AWS_REGION:-us-east-1}" \
        --stack-name "${AUTH_STACK_NAME:-${PROJECT_NAME:-peach}-auth}" \
        --query 'Stacks[0].Outputs' --output json --no-cli-pager
      ;;
    terraform)
      python3 "${ROOT}/scripts/infra-outputs.py" auth --format cfn
      ;;
    *) printf 'Invalid PEACH_INFRA_SOURCE; refusing output lookup\n' >&2; return 1 ;;
  esac
}
