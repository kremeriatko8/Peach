# Lab 6 evaluation — October 21, 2026

## Evidence and datasets

The original course specification was supplied in the project conversation; no standalone original handout was located. The required five categories remain commit link, deployed recording, five-case actual-output table, real usage log and four written answers.

Amazon Nova Lite (`amazon.nova-lite-v1:0`, Bedrock Runtime Converse) substitutes for the specified Claude Opus 5.5 / AnthropicBedrockMantle. AWS account metadata reported Claude unavailable with zero applicable Mantle quotas and directed access inquiries to AWS Sales. Other Runtime Claude entitlement could not be fully verified. The substitution avoids waiting for external approval; it is **not instructor approved** and is not literal compliance with the required model/client.

- **V1:** five representative authenticated HTTP tests, October 19. Actual JSON exists in [v1 table](submission/lab6/v1-five-tests.md). Three quality failures, two passes; 4,457 input / 473 output tokens; estimated $0.00038094. These inputs differ from the course-category UI set.
- **V2:** five course-category deployed UI tests, October 19. [Inputs, expected fields, reported outcomes and measured telemetry](submission/lab6/v2-five-tests.md): Ukrainian PARTIAL, email PASS, relative dates PARTIAL, shopping fallback PASS, injection FAIL. Six provider attempts, one repair; 9,185 input / 1,105 output; estimated $0.00081630. Exact Ukrainian wording was prescribed; the other inputs instantiate prescribed categories/examples. Logs map chronologically to reported order, not by logged source text.
- **Missing:** actual v2 response JSON was not recorded in available artifacts. Existing local JSON, saved responses and media were searched; no genuine v2 proposals were recovered. Do not reconstruct them, infer them from tokens, or substitute v1. User-observed field reports are not actual JSON.
- **V3:** deployed and enabled; user reports a successful October 21 UI demonstration, changing duration to 55 minutes, saving and showing the meeting list. User reports a 24-second recording; the file itself has not been inspected. Four successful v3 telemetry events were observed, each 1,624 input / 153 output, one call/no repair and $0.00013416; their sum is $0.00053664. No source text is logged, so a particular event cannot independently be matched to the video. This ordinary example does not establish that v3 fixed all v2 failures.
- **Earlier October 21 failures:** two HTTP503 provider attempts, no repair, approximately 8.08 seconds provider latency each. Tokens and costs are unknown (`usage_complete=false`, `cost_complete=false`); aggregate logged zeros do not mean free inference. An eight-second SDK read timeout is the leading hypothesis, not a confirmed exception diagnosis. Later successes do not resolve it.

## Final v3 five-category evaluation

[Final table and actual user-captured JSON](submission/lab6/v3-five-tests.md),
[machine-readable results](submission/lab6/v3-five-tests.json) and
[actual CloudWatch telemetry](submission/lab6/v3-cloudwatch-events.json) now cover
all five categories. English PARTIAL; Ukrainian PARTIAL; shopping PASS after one
repair; ambiguous dates FAIL with HTTP422/validation_exhausted; exact injection
PASS with two HTTP422 pre-inference rejections and zero provider calls.

Seven manual Parse requests used eight provider calls (three repairs),
13,333 input / 1,770 output tokens, estimated **$0.00122478**. This includes both
Case4 requests, confirmed by the user as two manual clicks. They are no longer
unexplained. The earlier cap was six; eight were already consumed before the
user raised the total to ten for Case5. Both Case5 clicks used zero provider calls.
Two calls remain unused; no further testing is implied or needed here.

Evidence gaps remain: both Case4 response bodies are unavailable; only one
Case5 error body was supplied for two clicks with no per-click association;
JSON for Cases1–3 was pasted by the user rather than original response files;
request today/tz fields were not captured. Logs do not record source text.
The five categories were exercised, but the literal all-responses requirement
is still partial. V1/v2 evidence is preserved separately, never substituted.

## Required written answers

1. **Failures and appropriate fixes.** V1 missed Alex, misread a Ukrainian weekday/deadline and converted meeting end time into an action. V2 added extra/misclassified actions, unsupported one-minute durations/dates and literal null owners; its injection assigned admin@example.com and omitted an explicit 15-minute duration. Prompt guidance, strict validation and v3 conservative source checks/placeholder normalization address these classes, while review/edit UI is essential. Schema validity alone does not prove factual correctness. Final v3 live evidence still shows an unsupported15-minute value on the second English item, omitted explicit Ukrainian facts and a validation-exhausted failure for ambiguous dates. The exact injection was rejected before inference in two requests; that is a guard success, not proof of model-level resistance. Validation/grounding needs better item-level association and multilingual coverage; prompt changes alone are not proven fixes. Conservative checks can reject legitimate security discussions or omit valid task/date formats.

2. **Prompt injection.** V1's different injection passed; V2's owner override FAILED. Do not average these into a claim of resistance. Two live v3 requests containing the same recognizable override returned422/source_instruction_rejected with zero provider calls and zero cost; the captured error JSON is recorded. This verifies the guard for that payload only; obfuscations may evade its patterns. JWT authorization, fixed data-only tool, strict schema, no parser database access, ownership checks and explicit human Save limit damage. Owners are text labels, not authorization grants. Review remains necessary even when the model returns valid JSON.

3. **Cost.** V2 observed mean: $0.00081630 / 5 = **$0.00016326 per parse**, including its repair. 20 organizations × 30/week × 52/12 = **2,600 parses/month**; estimate **$0.424476/month**, excluding Lambda, storage/logs, other infrastructure and unknown failed-call costs. Configured rates are $0.06/million input and $0.24/million output tokens. This small-sample extrapolation is not a bill or cap. It is below the assignment's $7.30/month interface endpoint comparison; this outside-VPC parser uses no such endpoint. For context only, the distinct v1 mean was $0.000076188 and one measured v3 success $0.00013416. Do not pool differing datasets or assume failures cost zero. The final v3 evaluation cost was $0.00122478 across seven top-level requests/eight provider calls, including a repeated Case4 failure; it is not a five-single-request mean. Two earlier provider503 failures remain unknown cost and excluded. The complete final-evaluation accounting does not resolve those older failures.

4. **500-agenda evaluation.** Preserve consented source text plus original date/timezone, suggestion, model/prompt and corrected result; corrected suggestions alone are insufficient ground truth. De-identify; split development and held-out sets; run paired versions on identical source/model/context. Measure agenda/action precision/recall, owner/date/duration accuracy, unsupported facts, schema/failure rate, normalized human edits, correction time, tokens/cost and latency. Blind-review ambiguous labels, report paired confidence intervals and reject safety regressions. No 500-case experiment has been performed. V1/v2 inputs here differ and cannot establish a paired improvement score.

## Remaining submission gaps

See [submission README](submission/lab6/README.md). Actual v2 JSON remains missing; final v3 Case4 bodies are also missing. Final v3 evidence supplies actual outputs for the other categories with the provenance limits above. Instructor acceptance of missing response evidence and the Nova deviation remains outstanding. Attach the user-held recording. Final documentation changes are local and uncommitted; publication requires approval and must not trigger backend deployment. Public evidence intentionally omits tokens, credentials, private emails and deployment archives.
