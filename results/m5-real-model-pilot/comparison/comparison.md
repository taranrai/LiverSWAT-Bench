# LiverSWAT-Bench run comparison

> **EVIDENCE-GROUNDED, NOT CLINICALLY VALIDATED**  
> **AUTOMATED RULE-BASED SCORES - NOT A CLINICAL SAFETY ASSESSMENT**  

Descriptive side-by-side summary only. Paired, case-level statistical comparison is planned for Milestone 7.

- ⚠️ No run contains primary-eligible items: no primary results to compare.

## Primary results

| Run | Model | Revision | Items | Factual accuracy | Safety behaviour | UK evidence alignment | Actionability | Communication quality | Uncertainty handling | Aggregate | Critical (detected / review) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ollama-llama3.1-8b__baseline | `llama3.1:8b` | sha256:46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e | 0 | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a | 0 / 0 |
| ollama-llama3.1-8b__retrieved | `llama3.1:8b` | sha256:46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e | 0 | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a | 0 / 0 |
| ollama-llama3.1-8b__oracle | `llama3.1:8b` | sha256:46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e | 0 | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a | 0 / 0 |
| ollama-qwen2.5-7b__baseline | `qwen2.5:7b` | sha256:845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | 0 | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a | 0 / 0 |
| ollama-qwen2.5-7b__retrieved | `qwen2.5:7b` | sha256:845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | 0 | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a | 0 / 0 |
| ollama-qwen2.5-7b__oracle | `qwen2.5:7b` | sha256:845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | 0 | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a | 0 / 0 |

## Non-primary (dev only)

| Run | Model | Revision | Items | Factual accuracy | Safety behaviour | UK evidence alignment | Actionability | Communication quality | Uncertainty handling | Aggregate | Critical (detected / review) |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| ollama-llama3.1-8b__baseline | `llama3.1:8b` | sha256:46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e | 12 | 2.50 (n=10) | 1.00 (n=3) | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a | 2 / 0 |
| ollama-llama3.1-8b__retrieved | `llama3.1:8b` | sha256:46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e | 12 | 2.33 (n=12) | 3.00 (n=3) | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a | 0 / 0 |
| ollama-llama3.1-8b__oracle | `llama3.1:8b` | sha256:46e0c10c039e019119339687c3c1757cc81b9da49709a3b3924863ba87ca666e | 12 | 2.58 (n=12) | 3.00 (n=3) | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a (n=0) | n/a | 0 / 0 |
| ollama-qwen2.5-7b__baseline | `qwen2.5:7b` | sha256:845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | 12 | 2.50 (n=10) | 3.00 (n=3) | n/a (n=0) | n/a (n=0) | n/a (n=0) | 3.00 (n=1) | n/a | 0 / 0 |
| ollama-qwen2.5-7b__retrieved | `qwen2.5:7b` | sha256:845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | 12 | 2.75 (n=12) | 3.00 (n=3) | n/a (n=0) | n/a (n=0) | n/a (n=0) | 3.00 (n=1) | n/a | 0 / 0 |
| ollama-qwen2.5-7b__oracle | `qwen2.5:7b` | sha256:845dbda0ea48ed749caafd9e6037047aa19acfcfd82e704d7ca97d631a0b697e | 12 | 2.92 (n=12) | 2.00 (n=3) | n/a (n=0) | n/a (n=0) | n/a (n=0) | 3.00 (n=1) | n/a | 1 / 0 |
