#!/usr/bin/env bash
# Read-only AWS lookup; only public configuration is written to the frontend.
set +x
set -euo pipefail
source "$(dirname "${BASH_SOURCE[0]}")/auth-env.sh"
unset GOOGLE_CLIENT_ID GOOGLE_CLIENT_SECRET
mode="${1:-local}"
[[ "${mode}" == local || "${mode}" == deployed ]] || die "usage: auth-config.sh [local|deployed]"
aws cloudformation describe-stacks --region "${AWS_REGION}" \
  --stack-name "${AUTH_STACK_NAME}" --query 'Stacks[0].Outputs' \
  --output json --no-cli-pager | python3 -c '
import json, os, pathlib, sys
from urllib.parse import urlsplit
mode, root = sys.argv[1:]
outputs = {entry["OutputKey"]: entry["OutputValue"] for entry in json.load(sys.stdin)}
keys = {
    "NEXT_PUBLIC_COGNITO_AUTHORITY": "Authority",
    "NEXT_PUBLIC_COGNITO_CLIENT_ID": "UserPoolClientId",
    "NEXT_PUBLIC_COGNITO_DOMAIN": "CognitoDomain",
    "NEXT_PUBLIC_AUTH_REDIRECT_URI": "LocalhostCallbackUrl" if mode == "local" else "FrontendCallbackUrl",
    "NEXT_PUBLIC_AUTH_LOGOUT_URI": "LocalhostLogoutUrl" if mode == "local" else "FrontendLogoutUrl",
}
values = {}
for env, key in keys.items():
    value = outputs.get(key)
    if not value or value == "None" or any(char in value for char in "\n\r\"\\$"):
        sys.exit("Missing or invalid public auth output: " + key)
    values[env] = value
callback = values["NEXT_PUBLIC_AUTH_REDIRECT_URI"]
logout = values["NEXT_PUBLIC_AUTH_LOGOUT_URI"]
if callback != logout + "auth/callback/" or not logout.endswith("/"):
    sys.exit("Auth callback/logout outputs are inconsistent")
if mode == "local" and urlsplit(callback).hostname != "localhost":
    sys.exit("Local auth callback must use localhost")
expected = os.environ.get("AUTH_EXPECTED_SITE_URL")
if expected and logout != expected.rstrip("/") + "/":
    sys.exit("Auth stack frontend origin differs from frontend SiteUrl; update auth URLs first")
path = pathlib.Path(root) / "frontend/.env.local"
lines = path.read_text().splitlines() if path.exists() else []
lines = [line for line in lines if line.split("=", 1)[0] not in keys]
lines.extend(env + "=" + value for env, value in values.items())
path.write_text("\n".join(lines) + "\n")
print("Wrote public " + mode + " auth configuration to frontend/.env.local")
' "${mode}" "${ROOT}"
