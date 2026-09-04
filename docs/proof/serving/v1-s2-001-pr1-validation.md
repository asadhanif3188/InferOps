# V1-S2-001-PR1 model acquisition validation

> [!NOTE]
> **Post-record resolution (2026-09-04):** the evidence this record reported as
> unproduced now exists and is cited below rather than left open. The workflow's
> real acquisition was executed by
> [`V1-S2-005-PR2`](v1-s2-005-pr2-validation.md) on 2026-09-03, and its real
> absent-state check and verified cache hit were re-executed on 2026-09-04 during
> the Sprint 2 completion remediation. Nothing above the resolution section is
> rewritten: this record described what it had at the time, and that is what it
> still says.

| Field | Value |
|---|---|
| Date | 2026-09-02 |
| Evidence class | `local-static` |
| Environment | Repository checkout, Python 3.12 locked environment |
| Model downloaded | **No** |
| Runtime or cluster started | **No** |
| Network used by the workflow | **No** |

## What was implemented

The selected model now has a machine-readable
[source record](../../serving/model-source.v1.json) and a repository command for
offline prerequisite checks, resumable acquisition, size and SHA-256 verification,
verified cache hits, and guarded cleanup. The public
[workflow](../../serving/model-acquisition.md) records the source, immutable
revision, Apache-2.0 licence reference, expected size, digest, cache layout, disk
assumptions, recovery behavior, and commands.

The workflow reads the accepted model identity from the existing adapter pins and
refuses a source record that drifts. A transfer writes only a `.part` file, requests
the remaining range after interruption, and atomically promotes it only after size
and SHA-256 match. Cleanup has no target override, is a dry run without
`--confirm`, refuses symlinks, and can remove only `.cache/inferops/models` inside
the current checkout.

This change does not package `llama-server`, create a runtime container, start the
InferOps API, or run inference.

## Results

All commands ran from the repository root.

| Command | Result | Classification |
|---|---|---|
| `uv run --locked python -m tools.model_acquisition check` | Passed. Printed the selected source/revision/licence/size/hash, reported cache state `absent`, and required 1.77 GiB including headroom. No network access | `local-static` |
| `uv run --locked python -m pytest tests/serving/test_model_acquisition.py tests/testing -q` | 986 passed | `local-static`; model workflow cases use tiny synthetic bytes |
| `uv run --locked ruff check .` | Passed | `local-static` |
| `uv run --locked ruff format --check .` | 219 files already formatted | `local-static` |
| `uv run --locked python -m mypy` | Passed; 121 source files checked | `local-static` |
| `uv run --locked python -m pytest -q` | 5,148 passed, 25 skipped, 14 deselected | `local-static`, `mock`, and repository-only checks according to each existing lane |

The focused suite proves workflow mechanics only. It does not prove that the
1,834,426,016-byte upstream artifact is currently reachable or that its real bytes
match the recorded digest.

## Source, cache, and verification method

| Item | Value |
|---|---|
| Source | `Qwen/Qwen3-1.7B-GGUF` |
| Revision | `90862c4b9d2787eaed51d12237eafdfe7c5f6077` |
| File | `Qwen3-1.7B-Q8_0.gguf` |
| Licence | Apache-2.0, referenced at the pinned revision |
| Expected size | 1,834,426,016 bytes |
| Verification | Revision in the fetch URL plus computed per-file SHA-256 `061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a` |
| Cache root | `.cache/inferops/models` inside the checkout |
| Fresh-cache disk assumption | Remaining bytes plus 64 MiB headroom; about 1.77 GiB before runtime images or runtime working space |

## Commands deliberately not executed

- `uv run --locked python -m tools.model_acquisition acquire`: not run **by this
  PR** because it downloads the 1.71 GiB selected model and no authorization was
  given. It was run under authorization on 2026-09-03; see the reconciliation
  section below.
- `uv run --locked python -m tools.model_acquisition verify`: not run against the
  real artifact **by this PR** because the cache was absent. It was run against the
  real artifact on 2026-09-03 and again on 2026-09-04; see the reconciliation
  section below.
- `uv run --locked python -m tools.model_acquisition clean --confirm`: not run;
  there was no model cache to remove, and destructive cleanup was unnecessary.
- Real-runtime, container, Kubernetes, load, paid-service, and production commands:
  not run and outside this PR boundary.

## Acceptance status

| Criterion | PR status | Evidence and limitation |
|---|---|---|
| Model source, revision, licence, expected size, and cache path are explicit | **Met** | Source record, workflow document, and offline `check` output |
| Model files are ignored by Git | **Met** | The documented cache and every `*.gguf` are ignored |
| Interrupted download can recover safely | **Met for workflow mechanics** | Synthetic interruption retains a partial; retry sends a matching Range request; a full response restarts safely. No 1.71 GiB transfer was run |
| Integrity/revision verification fails clearly | **Met for workflow mechanics** | The loader refuses unpinned source/licence locations and pin drift; acquisition refuses size/hash mismatch and never promotes unverified bytes |
| Cleanup targets only the documented cache | **Met** | No target override, explicit confirmation, containment and symlink checks, and a synthetic sibling-preservation test |

The PR boundary is complete. The parent story's implementation acceptance criteria
are met, but its requested **fresh real acquisition and real cache-hit logs remain
unproduced** because downloading the full model was explicitly authorization-gated.
The earlier feasibility record remains the only real download evidence; it is not
relabelled as output of this workflow.

## Story evidence, reconciled on 2026-09-04

The paragraph above was true when it was written and is left standing. The two
logs the story asked for have since been produced by **this** workflow, and the
Sprint 2 completion review required them to be cited here rather than left
scattered across later records.

| Story evidence | Produced by | Result |
|---|---|---|
| Fresh real acquisition | `V1-S2-005-PR2`, 2026-09-03, under an explicit download authorization | `check` reported `state absent (0 bytes present)`; `acquire` reported `verified download verified; 1834426016 bytes`; `verify` reported `SHA-256 matched`. Recorded in [`v1-s2-005-pr2-validation.md`](v1-s2-005-pr2-validation.md) |
| Real absent-state check | Sprint 2 completion remediation, 2026-09-04 | `state absent (0 bytes present)`; `80.00 GiB free; 1.77 GiB required`. Recorded in [the cache miss observation](v1-s2-007-cache-miss-observation.md) |
| Real cache hit | Sprint 2 completion remediation, 2026-09-04 | `check` reported `state verified (1834426016 bytes present)`; `verify` reported `Qwen3-1.7B-Q8_0.gguf (1834426016 bytes, SHA-256 matched)`, reading all 1.71 GiB |

Three things this reconciliation deliberately does **not** claim. The 2026-09-03
acquisition was performed to serve the baseline experiment, not as a rehearsal of
this workflow, though it used this workflow's commands unchanged. The 2026-09-04
cache hit was read from an artifact acquired the previous day, so it evidences the
hit path and not the transfer path. And **no interrupted transfer was ever resumed
against the real source**: resumption remains proved by synthetic interruption
only, exactly as the acceptance table above already says.

On the executing host the cached artifact also carries a second hard link outside
the checkout, which means a `clean --confirm` there frees no space and a later
"fresh" acquisition on that host would not be fresh. That is a property of one
machine and changes no repository behaviour; it is recorded in
[the Sprint 2 completion review](sprint-2-completion-review.md) so that a future
reader does not mistake a fast local acquisition for a fast download.

## Risks, assumptions, and deferred work

- Resumption depends on the source honoring HTTP Range. A `200` full response is
  handled by restarting the partial; an inconsistent `206` is refused.
- SHA-256 reads the complete 1.71 GiB file on acquisition and every cache hit. That
  cost is intentional: a filename and expected byte count are not integrity.
- The source is intentionally anonymous. Private or gated model support, tokens,
  alternate mirrors, and arbitrary cache locations are not implemented.
- Serving runtime packaging, local composition, real-runtime smoke evidence,
  runtime cache lifecycle, and Kubernetes storage remain later work.
- Fresh acquisition and cache-hit evidence require explicit authorization for the
  large download and a capable host with the documented disk allowance.

## Independent review

An independent second reader reviewed commit `a29220c` against the complete PR
brief, ADR 0002, repository conventions, and the public `main...HEAD` diff. The
review covered correctness, cache and cleanup containment, interruption recovery,
revision and digest enforcement, credential and log safety, tests, claims, private
information, machine paths, artifacts, and scope.

One blocking finding was reproduced: a `.part` holding all expected bytes after an
interruption during hashing or immediately before promotion was treated as needing
an HTTP Range request from end-of-file. A conforming source would normally return
HTTP 416, so retry could not recover without cleanup and a full redownload.

The follow-up change verifies an exact-size partial locally before any network
request, atomically promotes it when valid, discards it clearly when invalid, and
adds a regression test whose network opener fails if called. No other review
findings were reported. The reviewer independently ran the focused workflow and
inventory suites (985 passed before the regression was added), focused lint, the
security plus workflow suites (630 passed), `git diff --check main...HEAD`, and
targeted leakage and artifact scans.
