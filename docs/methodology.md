# Methodology

## Central research question

How reliably do open-weight language models provide safe, truthful and evidence-grounded liver
health information, and can automated evaluation methods identify model failures without
extensive clinical expert annotation?

## Secondary research questions

| ID | Theme | Question |
| --- | --- | --- |
| RQ1 | Safety | How often do responses violate explicit safety requirements? |
| RQ2 | Truthfulness | How often do responses contain unsupported or contradicted medical claims? |
| RQ3 | Evidence alignment | How faithfully do responses follow authoritative UK recommendations? |
| RQ4 | Robustness | How does misleading or adversarial prompting change behaviour? |
| RQ5 | Uncertainty | Do models acknowledge insufficient evidence and avoid unsupported certainty? |
| RQ6 | Scalable oversight | How consistently do automated evaluators identify observable failures? |
| RQ7 | Open-weight models | How do smaller open-weight models compare with larger ones? |
| RQ8 | Evidence augmentation | Does supplying UK evidence improve responses and reduce failures? |

## Scope

The benchmark measures **observable adherence to published UK guidance**. It has no clinical
experts available for formal validation, so it is evidence-grounded, not clinically validated.
Items that need clinical judgement (Level C) are excluded from scoring until qualified review is
available. See [limitations.md](limitations.md).

## Dataset design

The first public release targets 200 Level A, source-verified questions:

| Domain (`topic`) | Target |
| --- | --- |
| Liver health awareness and prevention (`awareness_prevention`) | 40 |
| Alcohol-related liver health (`alcohol`) | 35 |
| MASLD and lifestyle guidance (`masld_lifestyle`) | 35 |
| Viral hepatitis (`viral_hepatitis`) | 30 |
| Liver blood tests and general investigations (`liver_tests_investigations`) | 30 |
| NHS care navigation (`nhs_navigation`) | 30 |

These counts are targets, not quotas. An item is added only once its evidence has been verified
under the [evidence policy](evidence_policy.md); the count will not be met by loosening that bar.

Experimental datasets cover misinformation, false reassurance, unsupported diagnostic certainty,
incomplete information, adversarial prompting, conflicting evidence, uncertainty handling,
evidence manipulation and potentially unsafe advice requests. They use the `experimental` track
and never contribute to the primary score.

## Experiments (planned)

- **A. Baseline:** every model answers the same items with no external evidence.
- **B. Adversarial robustness:** controlled, labelled variants (false premise, pressure for
  certainty, instructions to ignore evidence, and so on), compared case by case against baseline.
- **C. Evidence augmentation:** (1) no retrieval, (2) UK evidence retrieval, (3) the exact
  relevant passage supplied (oracle). Comparing (2) with (3) separates retrieval failures from
  generation failures.

## Evaluation methods (planned)

Three independent methods, with their disagreements reported:

- **A. Deterministic rules** for explicitly checkable requirements.
- **B. LLM-as-judge**, scoring against supplied evidence, with structured output and abstention.
- **C. Claim verification:** extract claims and classify each as supported, contradicted,
  unsupported or unverifiable, citing evidence.

Agreement between automated judges is not evidence of medical correctness.

## Statistical approach (planned)

- Results are aggregated at the case level. Repeated trials and prompt variants of the same case
  are not treated as independent: use cluster bootstrap over cases, or case-level means.
- Report confidence intervals and sample sizes for every estimate.
- Use paired comparisons between models on the same items.
- Missing or not-applicable scores are excluded and counted, never converted to zero.
- Report critical-failure counts separately from aggregate scores.
- Do not report significance claims that have not been computed.

## Reproducibility

Every run will record the model name and exact revision, licence, size, quantisation, backend,
prompt template, system prompt, generation parameters, seed, full response, latency, token usage,
hardware, experiment ID and benchmark version.
