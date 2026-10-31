# Lab 7 evidence checklist

This directory is intentionally empty of live screenshots and plan files. Do not
commit HCP plan JSON, Terraform state, downloaded workspace archives, credentials,
or any screenshot that exposes private values.

## Required by the assignment

1. **Final merged commit or PR link.** It must replace the three lab templates in
   `infra/` with Terraform and include the Makefile, README, and ADR 0007 changes.
2. **HCP screenshot.** Capture the `peach-dev` run after it says **Apply finished**.
   The screen must show that the run came from the VCS push/merge, not a CLI run.
   Redact nothing by editing the evidence; instead use a view that does not show
   sensitive values.
3. **Immediate clean plan.** Save terminal or HCP output from the first full plan
   after adoption ending in `No changes. Your infrastructure matches the
   configuration.` It must be a genuine post-state-adoption result.

## Useful supporting evidence (only if requested)

- Retention change-set review and post-update template verification for
  `peach-auth`, `peach-reports`, and `peach-ai`.
- Stack deletion completion plus retained-resource verification.
- The reviewed initial HCP plan summary: 41 imports, 0 adds, 4 documented
  sensitivity-metadata updates, 0 replacements, 0 destructions. It is not the
  required clean-plan artifact and must not be represented as zero changes.
- Drift exercise: parser timeout changed manually, detected by HCP Plan only, then
  restored through reviewed Terraform after explicit authorization.

Store raw private artifacts outside Git in a 0700 directory with 0600 files. Record
only URLs, timestamps, counts, and sanitized outcomes in Git documentation.
