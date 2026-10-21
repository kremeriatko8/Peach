# Peach Lab 6 submission

## Exactly five submission categories

1. **Commit:** [feature branch](https://github.com/kremeriatko8/Peach/tree/feat/paste-agenda). Final documentation commit is the branch tip. It contains parser `backend/app/ai/agenda.py`, `infra/ai.yml`, `frontend/components/agenda-dialog.tsx` and [ADR](../../adr/0006-llm-agenda-parsing.md). Code deployed from commit `00fa49d23e52ffe7db671f9b016a7cf365e185a0`; documentation-only tip does not imply redeployment.
2. **Video — attach manually:** user reports a 24-second deployed MP4/GIF showing demo meeting, paste, Parse, suggestions, duration corrected to 55, Save and updated Meetings list. Meets described <=45-second sequence; file not supplied/independently inspected. No video is committed here.
3. **Five-input table — PARTIAL:** [v2 course-category table](v2-five-tests.md) contains inputs, expected/correct/incorrect fields, invented values reported by user, tokens, cost and latency. **Actual v2 JSON MISSING**, not recoverable from available artifacts. [v1 table](v1-five-tests.md) contains actual JSON for a different dataset; supplementary only. Do not relabel or reconstruct. Request instructor acceptance of the missing evidence, or separately authorize replacement evidence collection if required.
4. **Real log — READY:** [October 21 v3 successful event](cloudwatch-v3-success.json), retrieved read-only from CloudWatch. Request a1240f16-fb4b-4cd8-80f5-c1c14666103e, timestamp 2026-10-21T16:42:28.272Z. Match to recording not independently established. Earlier failed attempts have unknown usage/cost, not zero.
5. **Four written answers — READY with disclosed limitations:** [evaluation](../../agenda-evaluation.md), including separate v1/v2 outcomes, injection failure, measured cost extrapolation and proposed 500-case evaluation.

## Required supporting documents

- [C4 container diagram](../../architecture.md): Browser→Parser→Bedrock and Browser→API→Aurora.
- [ADR0006](../../adr/0006-llm-agenda-parsing.md): decisions, alternatives, costs/fallback.
- Budget `peach-monthly-cost-alert`: verified $5/month; actual 85%/100%, forecast 100% email notifications; Credit/Refund excluded. Private email intentionally omitted. No duplicate budget stack is required. [Template](../../../infra/budget.yml).
- Live app: https://diby4tampbgny.cloudfront.net/meetings

## Explicit assignment deviation / limitations

Assignment specifies Claude Opus 5.5 with AnthropicBedrockMantle. Nova Lite (`amazon.nova-lite-v1:0`) / Bedrock Runtime Converse was used because account metadata reported Claude unavailable with zero applicable Mantle quotas and external access approval needed. **Instructor approval has not been obtained.** No claim of literal model/client compliance is made.

Parser remains enabled at the verified v3 digest. Known timeout hypothesis remains unresolved; successful ordinary parses do not prove v3 fixed all injection/quality problems. Shared concurrency and non-global warm-instance rate limiting remain; budget does not stop spending. No new inference, infrastructure changes or private evidence publication was needed for this documentation pass.

## Manual finish

Attach the video; use the verified final GitHub commit link provided after publication; disclose/resolve missing v2 JSON and model substitution with the instructor. No fabricated results or automatic extra tests.
