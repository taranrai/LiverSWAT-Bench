# Mock judge scripts

**Hand-written synthetic judge outputs** replayed by `configs/judges/mock-judge-a.yaml` and `mock-judge-b.yaml` to exercise the judge pipeline end to end. They are not outputs of any model and not assessments of anything. Each entry is matched on the `QUESTION_ID:` (and optionally `PROMPT_VERSION:`) line of the judge prompt.

Designed cases: agreement between judges; a hallucinated evidence reference (judge B, DEMO-0002); a judge-vs-judge disagreement (DEMO-0003 safety); a claim that is not quoted verbatim (judge B, DEMO-0005); potentially dangerous claims; a low-confidence claim; and a prompt-wording difference (judge A, `v1-alt`, DEMO-0003).
