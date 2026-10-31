#!/usr/bin/env bash
# Auth outputs come from HCP Terraform (workspace peach-dev); read-only.
# The [{OutputKey, OutputValue}] shape keeps existing callers unchanged.
peach_auth_outputs() {
  python3 "${ROOT}/scripts/infra-outputs.py" auth --format cfn
}
