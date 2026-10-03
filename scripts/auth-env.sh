#!/usr/bin/env bash
# Shared auth CLI setup. Callers disable tracing before sourcing this file.
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
die() { printf 'error: %s\n' "$*" >&2; exit 1; }
if [[ -f "${ROOT}/.env" ]]; then
  preset="$(export -p)"
  set -a
  source "${ROOT}/.env" 2>/dev/null || die "could not load root .env"
  set +a
  eval "${preset}"
  unset preset
fi
for var in AWS_PROFILE AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN; do
  [[ -n "${!var:-}" ]] || unset "${var}"
done
AWS_REGION="${AWS_REGION:-us-east-1}"
[[ "${AWS_REGION}" == us-east-1 ]] || die "auth requires AWS_REGION=us-east-1"
AUTH_STACK_NAME="${AUTH_STACK_NAME:-${PROJECT_NAME:-peach}-auth}"
export AWS_DEFAULT_REGION="${AWS_REGION}" AWS_CLI_AUTO_PROMPT=off
command -v aws >/dev/null || die "aws CLI is required"
command -v python3 >/dev/null || die "python3 is required"
