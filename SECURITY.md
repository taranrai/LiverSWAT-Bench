# Security policy

Documentation follows ASD-STE100 Simplified Technical English principles. Formal compliance has
not been certified.

## Supported versions

| Version | Supported |
| --- | --- |
| 0.1.x | Yes |
| Earlier development versions | No |

## Report a vulnerability

Do not report a vulnerability in a public issue.

1. Contact the maintainer through the GitHub profile https://github.com/taranrai.
2. Describe the problem, the affected file or command, and the steps to reproduce it.
3. Do not include real credentials or personal data in the report.

The maintainer acknowledges a report as soon as possible. The maintainer agrees the publication
date of a fix with the reporter.

## Scope

In scope:

- Code execution, path traversal or credential exposure in the `liverswat` command-line
  interface (CLI) or the package.
- Leaks of API keys or tokens into configuration files, run manifests or results.
- Problems in the Hugging Face Space configuration (`deploy/hf-space/`) or the results
  synchronisation script.

Out of scope:

- Unsafe or incorrect health advice in a model response. Use the issue template "Safety
  evaluation failure". This is a benchmark finding, not a software vulnerability.
- Errors in source evidence. Use the issue template "Evidence correction".

## Handling of credentials

- The OpenAI-compatible backend reads an API key from the environment variable named in
  `backend_options.api_key_env`. The key is not written to configuration files or outputs.
- The results synchronisation script reads the token from the `HF_TOKEN` environment variable.
- `.gitignore` excludes `.env` files, keys and model weights.
