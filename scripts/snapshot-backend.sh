#!/usr/bin/env bash
# Explicit backup operation. NEVER called automatically by deployment.
set +x
set -euo pipefail
ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
if [[ -f "${ROOT}/.env" ]]; then
  preset="$(export -p)"
  set -a
  source "${ROOT}/.env"
  set +a
  eval "${preset}"
fi
unset GOOGLE_CLIENT_ID GOOGLE_CLIENT_SECRET
export AWS_DEFAULT_REGION="${AWS_REGION:-us-east-1}"
for var in AWS_PROFILE AWS_ACCESS_KEY_ID AWS_SECRET_ACCESS_KEY AWS_SESSION_TOKEN; do
  [[ -n "${!var:-}" ]] || unset "${var}"
done
STACK_NAME="${STACK_NAME:-${PROJECT_NAME:-peach}-backend}"
CLUSTER_ID="$(aws cloudformation describe-stack-resource --stack-name "${STACK_NAME}" \
  --logical-resource-id DbCluster --query StackResourceDetail.PhysicalResourceId --output text)"
[[ -n "${CLUSTER_ID}" && "${CLUSTER_ID}" != None ]] || { echo 'Existing cluster not resolved' >&2; exit 1; }
SNAPSHOT_ID="${PROJECT_NAME:-peach}-pre-ownership-$(date -u +%Y%m%d-%H%M%S)-${RANDOM}"
aws rds create-db-cluster-snapshot --db-cluster-identifier "${CLUSTER_ID}" \
  --db-cluster-snapshot-identifier "${SNAPSHOT_ID}" >/dev/null
aws rds wait db-cluster-snapshot-available --db-cluster-snapshot-identifier "${SNAPSHOT_ID}"
aws rds describe-db-cluster-snapshots --db-cluster-snapshot-identifier "${SNAPSHOT_ID}" --output json \
  | python3 -c '
import json,sys
items=json.load(sys.stdin)["DBClusterSnapshots"]
if len(items)!=1 or items[0]["DBClusterIdentifier"]!=sys.argv[1] or items[0]["Status"]!="available" or items[0]["SnapshotType"]!="manual":
    sys.exit("Snapshot verification failed; release forbidden")
' "${CLUSTER_ID}"
printf 'Verified backup. Use PEACH_RELEASE_SNAPSHOT_ID=%s for this release (valid for 24 hours).\n' "${SNAPSHOT_ID}"
