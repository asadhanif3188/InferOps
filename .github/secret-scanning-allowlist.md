# Secret Scanning Allowlist

This document explains which credential patterns are intentionally used as test fixtures in this repository and why they do not pose a security risk.

## Test Fixtures

The following credentials are **synthetic test data**. They authenticate against nothing and exist only to test shape detection and redaction. Four test suites use them:

- `tests/contracts/test_workload_contract_validation.py` — validates that the workload contract validation logic correctly rejects credential-like locators;
- `tests/domain/test_workload_domain.py` — uses `AKIAIOSFODNN7EXAMPLE` and the zero-padded `ghp_` value to assert that a domain refusal does **not** repeat a value read out of the document;
- `tests/adapters/test_llama_server_settings.py` — uses the zero-padded `ghp_` value inside a URL's userinfo to assert that a runtime endpoint carrying a credential is refused and that the refusal does **not** repeat it;
- `tests/scaffolding/test_workload_template_parameters.py` — uses `AKIAIOSFODNN7EXAMPLE` to assert that a workload-template refusal does **not** repeat the value it refused.

### AWS Keys
- `AKIAIOSFODNN7EXAMPLE` — Official example key published in [AWS documentation](https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_identifiers.html)
- `ASIAIOSFODNN7EXAMPLE` — Official example session credential prefix, also from AWS docs

### Credentials with Zero-Padding
These follow valid credential format prefixes but use trailing zeros to ensure they cannot authenticate:

- `ghp_0000000000000000000000000000000000` — GitHub PAT (zero-padded)
- `github_pat_00000000000000000000000000` — GitHub PAT new format (zero-padded)
- `glpat-00000000000000000000` — GitLab PAT (zero-padded)
- `hf_000000000000000000000000000000000000` — Hugging Face token (zero-padded)
- `xoxb-000000000000-000000000000-000000` — Slack bot token (zero-padded)
- `sk-000000000000000000000000000000000000` — OpenAI API key (zero-padded)
- `AIza00000000000000000000000000000000000` — Google API key (zero-padded)

### Other Synthetic Patterns
- `eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9` — The unsigned, universally published JWT header `{"alg":"HS256","typ":"JWT"}`. Contains no claim, signature, or subject.
- `inferops/telemetry/Zx4Kq9TbLm2Rd7Wf1Hs3Nv8Yc6Ej0Pa` — Fixed synthetic string for testing path-based credential detection

## Configuration

Secret scanning is configured in `.gitleaks.toml` with explicit allowlist rules for these patterns and paths.

`.gitleaks.toml` allowlists two **paths** (`tests/contracts/`, `docs/proof/`) and, separately, the **patterns** above. The pattern rules are path-independent, which is why `tests/domain/` is covered without being added to the path list — and it is deliberately not added, because a path allowlist would exempt a future secret in that directory rather than the two published placeholders.

## References

- **AWS Example Keys**: https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_identifiers.html
- **Test Files**: `tests/contracts/test_workload_contract_validation.py` (see test `test_a_credential_shaped_locator_is_caught`) and `tests/domain/test_workload_domain.py` (see `test_a_refusal_repeats_nothing_from_the_document`)
- **Gitleaks Config**: `.gitleaks.toml`
