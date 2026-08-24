# Secret Scanning Allowlist

This document explains which credential patterns are intentionally used as test fixtures in this repository and why they do not pose a security risk.

## Test Fixtures in `tests/contracts/test_workload_contract_validation.py`

The following credentials are **synthetic test data** used to validate that the workload contract validation logic correctly rejects credential-like patterns. They authenticate against nothing and exist only to test the shape-detection heuristics.

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

## References

- **AWS Example Keys**: https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_identifiers.html
- **Test File**: `tests/contracts/test_workload_contract_validation.py` (see test `test_a_credential_shaped_locator_is_caught`)
- **Gitleaks Config**: `.gitleaks.toml`
