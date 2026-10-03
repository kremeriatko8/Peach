#!/usr/bin/env bash
# Read-only AWS lookup and public JWKS download for local Compose configuration.
set +x
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/auth-env.sh"
unset GOOGLE_CLIENT_ID GOOGLE_CLIENT_SECRET
aws cloudformation describe-stacks --region "${AWS_REGION}" \
  --stack-name "${AUTH_STACK_NAME}" --query 'Stacks[0].Outputs' --output json --no-cli-pager \
  | python3 "${ROOT}/scripts/cognito-snapshot.py" \
  | python3 -c 'import json,pathlib,sys; values=json.load(sys.stdin); pathlib.Path(sys.argv[1]).write_text("\n".join(k+"="+v for k,v in values.items())+"\n")' "${ROOT}/backend/.env.auth.local"
printf 'Wrote public backend verifier configuration; restart the local backend.\n'
