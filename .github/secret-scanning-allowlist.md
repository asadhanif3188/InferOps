# Secret Scanning Allowlist

This document explains which credential patterns are intentionally used as test fixtures in this repository and why they do not pose a security risk.

## Test Fixtures

The following credentials are **synthetic test data**. They authenticate against nothing and exist only to test shape detection and redaction. Eight test suites use them:

- `tests/contracts/test_workload_contract_validation.py` — validates that the workload contract validation logic correctly rejects credential-like locators;
- `tests/domain/test_workload_domain.py` — uses `AKIAIOSFODNN7EXAMPLE` and the zero-padded `ghp_` value to assert that a domain refusal does **not** repeat a value read out of the document;
- `tests/adapters/test_llama_server_settings.py` — uses the zero-padded `ghp_` value inside a URL's userinfo to assert that a runtime endpoint carrying a credential is refused and that the refusal does **not** repeat it;
- `tests/domain/test_workload_validation.py` — uses every credential prefix the WorkloadContract's heuristic knows, each followed by a short run of zeros, and two fixed mixed-case strings including `Zx4Kq9TbLm2Rd7Wf1Hs3Nv8Yc6Ej0Pa`, to assert which locators the domain's credential rule refuses. Its zero-padded values are shorter than the forms listed below, so no pattern rule matches them; gitleaks 8.30.1 with this configuration reports no finding in the file, so there is nothing to exempt. This suite was missing from this list, which said five suites while six used these values, until `V2-S1-002-PR1` added the seventh and recounted;
- `tests/scaffolding/test_workload_template_parameters.py` — uses `AKIAIOSFODNN7EXAMPLE` to assert that a workload-template refusal does **not** repeat the value it refused;
- `tests/contracts/test_environment_binding_v1alpha1.py` — uses the AWS placeholder, the zero-padded `ghp_`, `github_pat_`, `hf_`, `sk-`, `glpat-`, and `xoxb-` values, a zero-padded GitLab deploy token `gldt-00000000000000000000`, the JWT header, and the bare synthetic segment `Zx4Kq9TbLm2Rd7Wf1Hs3Nv8Yc6Ej0Pa`, to assert which credential shapes an EnvironmentBinding's patterns refuse and which lowercase ones they still accept. The `gldt-` value appears in no other file except the RenderedWorkloadRelease suite below and has no pattern rule; in both it is covered only because the module sits under the exempted `tests/contracts/` path.
- `tests/contracts/test_rendered_workload_release_v1alpha1.py` — uses the same values as the EnvironmentBinding suite, including the zero-padded `gldt-` token, plus `AKIAIOSFODNN7EXAMPLE` behind a version's pre-release separator, to assert which credential shapes a RenderedWorkloadRelease's patterns refuse and which lowercase ones they still accept. It also carries a fixed UUID and a fixed 64-character hexadecimal string, neither of which is credential-shaped, to assert what a release identifier's pattern refuses and accepts.
- `tests/domain/test_rendered_workload_release_domain.py` — uses the `sk-`, `glpat-`, `gldt-`, and `xoxb-` prefixes, and the `ghp_`, `hf_`, `npm_`, `sk_live_`, and `doo_v1_` prefixes inside a synthetic image reference, each followed by four zeros, builds every prefix the WorkloadContract's heuristic knows followed by four zeros at run time, and carries a fixed lowercase string with no published prefix, to assert which values the release domain's credential rule refuses and which it still cannot. Like `tests/domain/test_workload_validation.py`, its values are shorter than the forms listed below and match no pattern rule; gitleaks 8.30.1 with this configuration reports no finding in the file, so no rule and no path was added. Added by `V2-S1-002-PR2`.

Two EnvironmentBinding invalid fixtures, outside both exempted paths, also carry synthetic values: `contracts/environment/examples/invalid/secret-value-in-a-field.yaml` carries the JWT header, which its pattern rule covers, and `contracts/environment/examples/invalid/secret-value-in-an-identifier.yaml` carries `AKIAIOSFODNN7EXAMPLE`, which its pattern rule covers, and the synthetic segment under a `gitops/environments/` prefix, which **no rule covers** — the pattern rule is anchored to the `inferops/telemetry/` prefix. No rule was added for it: gitleaks 8.30.1 with this configuration reports no finding in either file, so there is no finding to exempt. If a later scanner version flags it, the right change is a pattern for that exact string, not a path exemption for the directory.

Two RenderedWorkloadRelease invalid fixtures, also outside both exempted paths, carry synthetic values, each covered by an existing pattern rule: `contracts/release/examples/invalid/secret-value-in-a-field.yaml` carries the JWT header, and `contracts/release/examples/invalid/secret-value-in-an-identifier.yaml` carries `AKIAIOSFODNN7EXAMPLE`, once alone and once behind a version's pre-release separator, and the zero-padded `ghp_` value. No rule and no path was added for them.

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

`.gitleaks.toml` allowlists two **paths** (`tests/contracts/`, `docs/proof/`) and, separately, the eleven **patterns** above. The pattern rules are path-independent, which is why `tests/domain/` is covered without being added to the path list — and it is deliberately not added, because a path allowlist would exempt a future secret in that directory rather than the two published placeholders.

### The structure, and why it changed

Each exemption is a `[[allowlists]]` block — plural — carrying a `description` and either `paths` or `regexes`.

It was written as a single `[allowlist]` with a list of `[[allowlist.regexes]]` **tables**, each pairing a `description` with a `regex`. That reads better than the schema and is not the schema: gitleaks requires `regexes` to be a list of strings, and it refused the whole configuration with eleven decoding errors and scanned nothing. Nobody saw that until `V1-S4-001-PR1` ran the scanner for the first time, because the check reading this file matched quoted lines with a regular expression rather than parsing it the way the tool does. That check now uses `tomllib`, asserts every allowlist says what it exempts, asserts every exempted path exists, and compiles every pattern.

The exemptions themselves are unchanged: the same two directories and the same eleven values, in the shape the tool accepts.

## References

- **AWS Example Keys**: https://docs.aws.amazon.com/IAM/latest/UserGuide/reference_identifiers.html
- **Test Files**: `tests/contracts/test_workload_contract_validation.py` (see test `test_a_credential_shaped_locator_is_caught`) and `tests/domain/test_workload_domain.py` (see `test_a_refusal_repeats_nothing_from_the_document`)
- **Gitleaks Config**: `.gitleaks.toml`
