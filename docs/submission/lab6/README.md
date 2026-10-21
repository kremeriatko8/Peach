# Peach Lab 6 submission

## Exactly five submission categories

1. **Commit:** [feature branch](https://github.com/kremeriatko8/Peach/tree/feat/paste-agenda). Final documentation commit is the branch tip. It contains parser `backend/app/ai/agenda.py`, `infra/ai.yml`, `frontend/components/agenda-dialog.tsx` and [ADR](../../adr/0006-llm-agenda-parsing.md). Code deployed from commit `00fa49d23e52ffe7db671f9b016a7cf365e185a0`; documentation-only tip does not imply redeployment.
2. **Video — attach manually:** user reports a 24-second deployed MP4/GIF showing demo meeting, paste, Parse, suggestions, duration corrected to 55, Save and updated Meetings list. Meets described <=45-second sequence; file not supplied/independently inspected. No video is committed here.
3. **Five-input table — PARTIAL evidence, all categories executed:** [final v3 table](v3-five-tests.md), [machine-readable results](v3-five-tests.json), [seven matching CloudWatch events](v3-cloudwatch-events.json). Cases1/2 PARTIAL, Case3 PASS, Case4 FAIL, Case5 PASS for exact pre-inference rejection. **Case4 actual response bodies remain unavailable.** Case5 has one captured error body for two user-confirmed clicks, without per-click attribution. Cases1–3 bodies were user-pasted, not independently downloaded. Seven manual requests/eight provider calls cost $0.00122478 estimated. Case4's second click is now explicitly explained by the user, not an unexplained request. [V2 table](v2-five-tests.md) retains missing JSON; [V1 table](v1-five-tests.md) is a different supplementary dataset, never a substitute.
4. **Real log — READY:** [October 21 v3 successful event](cloudwatch-v3-success.json), retrieved read-only from CloudWatch. Request a1240f16-fb4b-4cd8-80f5-c1c14666103e, timestamp 2026-10-21T16:42:28.272Z. Match to recording not independently established. Earlier failed attempts have unknown usage/cost, not zero.
5. **Four written answers — READY with disclosed limitations:** [evaluation](../../agenda-evaluation.md), including separate v1/v2 outcomes, injection failure, measured cost extrapolation and proposed 500-case evaluation.

## Required supporting documents

- [C4 container diagram](../../architecture.md): Browser→Parser→Bedrock and Browser→API→Aurora.
- [ADR0006](../../adr/0006-llm-agenda-parsing.md): decisions, alternatives, costs/fallback.
- Budget `peach-monthly-cost-alert`: verified $5/month; actual 85%/100%, forecast 100% email notifications; Credit/Refund excluded. Private email intentionally omitted. No duplicate budget stack is required. [Template](../../../infra/budget.yml).
- Live app: https://diby4tampbgny.cloudfront.net/meetings

## Explicit assignment deviation / limitations

Assignment specifies Claude Opus 5.5 with AnthropicBedrockMantle. Nova Lite (`amazon.nova-lite-v1:0`) / Bedrock Runtime Converse was used because account metadata reported Claude unavailable with zero applicable Mantle quotas and external access approval needed. **Instructor approval has not been obtained.** No claim of literal model/client compliance is made.

Parser remains enabled at the verified v3 digest. Known timeout hypothesis remains unresolved; final v3 results show remaining extraction errors and validation failure. Two exact-payload injection requests were rejected before inference; this is not universal protection. Shared concurrency and non-global warm-instance rate limiting remain; budget does not stop spending. No new inference, infrastructure changes or private evidence publication was needed for this documentation pass.

## Manual finish / Moodle upload

1. Attach the **24-second MP4/GIF** to Moodle's Lab6 submission file area. It is user-held, not present in this repository, and has not been independently inspected. Do not upload authentication headers, HAR files or tokens.
2. Include the immutable implementation commit URL: https://github.com/kremeriatko8/Peach/commit/7499d3d0e153ae4d42eed33905cde94b1a71790d . Final evidence edits in this checkout are **not yet committed/pushed**; do not claim GitHub already contains them.
3. Upload `v3-five-tests.md`, `v3-five-tests.json` and `v3-cloudwatch-events.json` as the test-evidence category, with the missing Case4 bodies and one-body/two-click Case5 limitation disclosed. Keep v1/v2 as clearly labelled supplemental evidence if included.
4. Upload `cloudwatch-v3-success.log` for the standalone successful-log category.
5. Upload `docs/agenda-evaluation.md` for the four written answers; link the ADR and architecture in the repository. Explicitly disclose the Nova/Converse substitution, pending instructor approval, and missing response evidence.

These are the assignment's five evidence categories, not a claim that the literal model requirement or all-response capture requirement is satisfied. Obtain instructor acceptance of those deviations rather than inventing JSON or running unapproved tests.

No commit/push is authorized in this stage. A push to main triggers backend deployment even for docs; use direct Moodle attachments now or separately approve a documentation branch/PR with no merge. No additional inference is needed to package the available evidence.
