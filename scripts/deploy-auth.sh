#!/usr/bin/env bash
# Retired infrastructure deployment entry point. Original templates remain for retention handover.
set -euo pipefail
printf 'Infrastructure deploys move to HCP Terraform. Use make infra-plan after explicit approval.\n' >&2
printf 'Retention-only CloudFormation handover is a separately reviewed live operation.\n' >&2
exit 1
