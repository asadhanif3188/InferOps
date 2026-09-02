# Sprint 1 completion remediation — change validation

> [!NOTE]
> **Post-record resolution (2026-09-02):** the two limitations that blocked the
> Sprint review were addressed later. The real adapter/API lane and its discovered
> correction are recorded in the
> [real-runtime closure](v1-s1-real-runtime-closure.md); the independent scaffolding
> run is recorded in the
> [clean-checkout walkthrough](../scaffolding/v1-s1-006-independent-walkthrough.md).
> The original remediation run below remains historical evidence.

This record covers the API-surface correction and documentation repairs made after
the Sprint 1 completion review. It is separate from real-runtime evidence: every
result here is static or mock-backed, and none may be cited as a selected-model
response.

## Classification

| Field | Value |
|---|---|
| Evidence class | `local-static` |
| Certification ceiling | `C0` |
| Claims supported | The implementation, documentation, and canonical API snapshot agree; unsupported caller generation fields are refused; the corrected relative-link targets exist |
| Claims not supported | A real runtime served a completion; the API answered over a network; a second engineer completed the scaffolding walkthrough |

## Provenance

| Input | Value |
|---|---|
| Repository | InferOps |
| Branch point | `990f7ee` |
| Branch | `fix/sprint-1-completion-blockers` |
| API snapshot | `docs/serving/inference-api-surface.v1alpha1.json` |
| Decision amended | `docs/architecture/decisions/ADR-0010-inference-api-compatibility-surface.md` |
| Dependencies | The committed `uv.lock`, consumed with `--locked` |

## Environment

| Field | Value |
|---|---|
| Host class | Contributor-owned Windows workstation |
| Workspace | Local checkout |
| Runtime/model configuration | Required real-runtime environment variables absent |
| Container/cluster tooling | No `docker` or `kubectl` command found during the capability check |
| Network runtime | Not started or contacted |

No hostname, username, absolute local path, credential, prompt, completion, or
environment-variable value is recorded here.

## Method

Run from the public repository root:

```text
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked python -m mypy
uv run --locked python -m pytest -q
git diff --check
```

The four repaired relative links in
`docs/proof/domain/v1-s1-001-pr2-validation.md` were also resolved from that
document's directory and checked with `Test-Path`.

## Results

| Check | Result |
|---|---|
| Ruff lint | Passed |
| Ruff formatting | Passed after applying the formatter's one test-layout correction |
| Strict mypy | Passed; 117 source files checked |
| Default pytest suite | Passed; 5,119 passed, 25 skipped, 14 deliberately deselected |
| Focused API/snapshot suites | Passed after the formatting-only correction; their assertions are included in the full result above |
| Diff whitespace | Passed |
| Four reported relative links | All four targets exist |

The request agreement test reads the canonical JSON snapshot and compares its
request member set with `inferops.api.surface.ACCEPTED_REQUEST_FIELDS` in both
directions. Request-validation tests send `max_tokens` and `temperature` and assert
that both receive `contract-invalid`, naming the member without echoing its value.

## Limitations

- The default suite excludes `realruntime`; its 14 real-runtime cases remain
  deliberately deselected. No skipped or deselected case is counted as a pass.
- The required real-runtime variables were absent and no capable runtime, model
  artifact, container engine, or cluster client was available from this checkout.
- No second engineer performed the scaffolding walkthrough during this work. That
  is a human review gate and cannot be self-certified by this record.
- The API snapshot is canonical and tested, but it is not OpenAPI, JSON Schema, a
  generated-client promise, or an artifact under `contracts/`.

## Authorisation

No external or cost-incurring run was performed. Static checks over the local
checkout required no additional authorization. A real-runtime run remains subject
to the capable-host and host-owner authorization rules in the test strategy.
