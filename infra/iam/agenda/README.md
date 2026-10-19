# Agenda IAM — current Nova Lite local proposals

See [ADMIN-SESSION.md](ADMIN-SESSION.md) for the exact three policy-version changes,
attachment rules, retained permissions boundary, read-only verification gates and
single administrative-session checklist. No IAM changes are executed by these files.

Runtime/optional laptop: bedrock:InvokeModel on exactly
arn:aws:bedrock:us-east-1::foundation-model/amazon.nova-lite-v1:0.
Readiness: bedrock:GetFoundationModel on that ARN and a separate
bedrock:GetFoundationModelAvailability read on Resource="*", conditioned to us-east-1. Other service/resource grants are preserved. No streaming,
cross-region, Marketplace, NAT or paid endpoint permissions are added.

The full operator-readiness policy includes the smaller readiness-readonly and
release-verification-readonly proposals; do not attach all three redundantly.
The parser-runtime-boundary is a role cap, not an ordinary user/group attachment.
The optional laptop grant remains unattached until separately approved.

Existing live policies were verified for Claude before this local Nova adaptation;
local files intentionally differ until a separately approved administrator update.
Nova remains a documented assignment deviation, not an instructor-approved model.


IAM resource-scope correction verified against the public Bedrock authorization
catalog: GetFoundationModel supports the exact foundation-model ARN, but
GetFoundationModelAvailability has no resource-level scope. Its separate statement
uses Resource="*" with aws:RequestedRegion=us-east-1. This grants only availability
metadata, never inference. Runtime/boundary/laptop InvokeModel remains exact-ARN
scoped; no model wildcard inference or streaming permission is granted.
