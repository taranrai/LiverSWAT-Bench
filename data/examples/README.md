# data/examples

**Synthetic demonstration records for software testing only.** Every source here is fictional (organisation `SYNTHETIC_DEMO`), and all text is prefixed `[SYNTHETIC DEMO - NOT CLINICAL GUIDANCE]`. These records are not medical advice and are excluded from all research results.

`demo_scripted_responses.jsonl` holds **hand-written synthetic responses** that `configs/models/mock-scripted.yaml` replays, so the scorer can be exercised end to end. Each is designed to trigger one scoring behaviour (supported claim, contradiction, negation sent to review, missing information, critical violation). They are not model outputs.
