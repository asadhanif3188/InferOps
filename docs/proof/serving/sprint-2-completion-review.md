# Sprint 2 completion review and remediation

Date: 2026-09-04

This record closes the Sprint 2 completion review. That review returned **FAIL**
with three completion blockers, two stale-documentation defects, and one
governance deviation to be recorded rather than hidden. This document states what
each of those was, what was done about it, and what is still not true.

It is a reconciliation record, not a story record. It publishes no new capability.
Two of its three blockers were closed by **executing** something the sprint had
built and never run; the third was closed by citing evidence that already existed
and had been left scattered.

## Classification

| Field | Value |
|---|---|
| Evidence class | `local-real-cpu` for the two executed runs; `local-static` for every documentation correction |
| Ceiling those classes carry | `C2` and `C0` respectively |
| Claims supported | The C2 smoke path certifies on a capable host; a real model-cache miss classifies and refuses as documented; the corrected status statements match the repository |
| Claims not supported | Any figure derived from these runs is a benchmark; the certification failure path works against a real runtime; a second host behaves the same way; a continuous-integration lane exists |

## Provenance

| Input | Value |
|---|---|
| Repository | InferOps |
| Branch point | `47478a49848f98a590016cd4bb693a5bc799277c` on `main`, the Sprint 2 head |
| Branch | `fix/sprint-2-completion-remediation` |
| Dependencies | The committed `uv.lock`, consumed with `--locked` |
| Runtime image | `ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384` |
| Model artifact | `Qwen/Qwen3-1.7B-GGUF`, revision `90862c4b9d2787eaed51d12237eafdfe7c5f6077`, `sha256:061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a` |

## Environment

Windows 11 on `AMD64`, Python 3.12.12, uv 0.9.16, Docker 29.7.2 with 20 logical
CPUs and 8,158,400,512 bytes visible to the engine, 80.00 GiB free on the
model-cache volume. CPU only; no accelerator. Every run was loopback-only.

No hostname, username, absolute local path, credential, prompt, or completion is
recorded here.

## The review's required remediation

| # | Required | Status |
|---|---|---|
| 1 | Execute and commit the real `V1-S2-004` C2 certification result | **Done.** [Certification result](v1-s2-004-c2-certification-result.md) |
| 2 | Reconcile `V1-S2-001` acquisition/cache-hit evidence, re-downloading only if unrecoverable | **Done without re-downloading.** [Reconciliation section](v1-s2-001-pr1-validation.md#story-evidence-reconciled-on-2026-09-04) |
| 3 | Resolve the `V1-S2-007` real cache-miss partial criterion explicitly | **Done by execution.** [Cache miss observation](v1-s2-007-cache-miss-observation.md) |
| 4 | Update `README.md` to reflect the successful baseline and current capability | **Done.** Five status entries and two framing paragraphs |
| 5 | Update the claim/test matrix so scanner statements match `V1-S2-006-PR1` | **Done.** [Matrix](../../testing/claim-test-matrix.md) |
| 6 | Record the `V1-S2-005` third-PR deviation and why it was accepted | **Done.** [Below](#governance-deviations) |
| 7 | Run the full applicable manual verification suite again | **Done.** [Below](#results) |
| 8 | Add a completion-review reconciliation record | **This document** |

## 1. The blockers

### `V1-S2-004` had no C2 certification result

The story's single required evidence was a C2 certification result. The
implementation PR built the workflow and said so directly — "this change adds a
workflow, not a result" — and no authorized run had ever been performed.

One was performed on 2026-09-04 and it **certified**. The runtime reached
readiness in 285,828 ms, the API in 203 ms, one real completion returned HTTP 200
in 3,140 ms with 20 prompt and 23 completion tokens counted by the runtime, and
teardown drained the API and removed the container. The full record, including the
generated evidence file, is [here](v1-s2-004-c2-certification-result.md).

The review was right that the successful `V1-S2-005` baseline does not substitute
for this. The baseline proves inference; it does not exercise the prerequisite
refusal, the identity assertions, the evidence classification, or the cleanup
semantics this story built. Those are now exercised by a run rather than only by
tests.

Two results in that record disagree with what a reader would assume, and are
stated there rather than left to be discovered: **the readiness margin is under
five per cent** of its budget, and **neither the request nor the correlation
identifier was echoed** in the response.

### `V1-S2-001` story evidence was incomplete

The review's instinct was correct: this was an evidence-reconciliation problem, not
a missing capability, and the guidance to avoid re-downloading 1.71 GiB unless
necessary was followed. It was not necessary.

The real acquisition already existed in the `V1-S2-005-PR2` record — `check`
reporting `state absent`, `acquire` reporting `verified download verified;
1834426016 bytes`, `verify` reporting `SHA-256 matched`. Both halves were
re-executed on 2026-09-04 for a current log: a real absent-state `check` during the
cache-miss window, and a real `verify` reading all 1,834,426,016 bytes and matching
the published digest. All three are now cited from the `V1-S2-001` record itself
rather than sitting in later documents.

The reconciliation deliberately does **not** upgrade one thing: resumption after an
interrupted transfer is still proved by synthetic interruption only. No real
transfer has ever been interrupted and resumed against the upstream source, and the
record says so.

### `V1-S2-007` declared one criterion partially met

The review would not convert an implementer's *partial* into a *pass*, and offered
two legitimate resolutions: execute the miss path, or formally accept the synthetic
one at the sprint review. It took the first.

Its cost estimate turned out to be wrong in a useful direction. The `V1-S2-007`
record assumed a real miss meant a 1.71 GiB download. Recovering *from* a miss does;
observing one does not. `observe_cache` classifies an absent artifact with no
network connection, and `observe_start` refuses at any non-hit cache **before** it
creates a container. So the miss was observed for real by renaming the documented
cache directory aside and restoring it — a directory-entry move, no transfer.

With the cache absent: `cache` reported `miss`, `0 of 1834426016`, mapping to
`artifact-absent`, exit `3`; `measure --confirm-real-runtime` refused with the
message naming the explicit repair, exit `3`, and **no container was created**;
`model_acquisition check` reported `state absent (0 bytes present)`. After
restoration the artifact verified byte-identical. The full method, including
exactly how the miss state was created, is
[here](v1-s2-007-cache-miss-observation.md).

The criterion is amended from *partially met* to **met** in
[the `V1-S2-007-PR1` record](v1-s2-007-pr1-validation.md), which now cites the
observation. The `partial` cache state remains synthetic-only and is still declared
as such.

## 2. The stale claims

Both defects the review found were real, and three more were found while fixing
them. All five were the same failure: a status sentence written about **one
change** and left standing as though it described **the repository**.

| Where | Said | Corrected to |
|---|---|---|
| `README.md`, baseline row | "the experiment was not executed and no measured baseline exists" | Executed 2026-09-03; 30 of 30 measured requests succeeded and every pre-registered threshold was met |
| Claim/test matrix, security paragraph | "no secret scanner, image scanner, or dependency auditor has been run and recorded" | No **secret** scanner has been run; an image scanner and a dependency auditor have each been run once, by hand, with two committed SBOMs |
| `README.md`, model acquisition row | "no model download executed by this change" | Executed against the real 1.71 GiB artifact, which verified against its published SHA-256 |
| `README.md`, composition row | "no real run performed by this change" | Executed against the real runtime on one CPU host, repeatedly |
| `README.md`, certification row | "no authorized real run performed by this change" | One authorized run certified at `C2` on 2026-09-04 |
| `README.md`, evidence records row | "a template is a format and has produced no record" | Two of the four templates have produced records; the index is in `docs/proof/README.md` |

The framing paragraph and the repository-status paragraph were also rewritten. The
old text said "there is no serving path in this repository that anyone can deploy",
which was accurate about deployment and misleading about capability: the selected
model does now serve real completions through the InferOps API. The new text says
both — that the local path works, and that it is loopback-only, single-host, CPU,
hand-started, unauthenticated, and undefended.

The matrix correction was checked against the wording
[ADR 0008](../../architecture/decisions/ADR-0008-v1-security-baseline.md) already
carries, so the two now agree instead of contradicting each other. `V1-S2-006-PR1`
corrected the ADR and left the matrix behind; that is the specific gap this closes.

## 3. Defects found during the remediation

### A test was enforcing a claim that had become false

`docs/telemetry/telemetry-catalog.v1alpha1.json` declared `recordsProduced: 0` for
all four evidence templates, and `tests/telemetry/test_telemetry_catalog.py`
asserted that zero for each. The claim was true when
[ADR 0006](../../architecture/decisions/ADR-0006-telemetry-and-evidence-catalog.md)
was accepted. It stopped being true when `V1-S2-005` published an experiment record
and raw results in exactly those formats.

This is worse than a stale sentence: the count could not be corrected without the
suite failing, so the test protected the false claim. It is the failure mode this
repository's culture exists to prevent, found inside the machinery built to prevent
it.

The fix removes the hand-maintained constant. A record made from a template now
declares that in one line beside its title, the catalog states a count, and the
suite derives the count from the declarations, so the two cannot drift. The counted
truth is one `experiment` record and five `raw-result` records; `environment` and
`claim-evidence` have produced none, and a test now fails if that distinction stops
being visible.

Counting by section headings was considered and rejected: all four templates
require the same headings, so a structural match cannot tell an experiment record
from an environment one, and a count nobody can check is what caused this.

### Host note: the cached artifact carries a second hard link

On the host that executed this remediation, the model artifact in the documented
workspace cache carries a **second hard link outside the checkout**. One set of
bytes, two directory entries, link count 2.

Three consequences a future reader should not have to rediscover:

- `tools.model_acquisition clean --confirm` on this host removes the documented
  cache entry and frees **no space**, because the second link keeps the bytes
  alive. The cleanup behaves exactly as documented and as tested — it targets only
  the documented cache — and the containment evidence stands. The space observation
  is a property of the host, not of the workflow.
- A subsequent "fresh" acquisition on this host would not be fresh in the sense the
  `V1-S2-001` evidence means, because the bytes never left the machine.
- It is why the cache-miss observation was safe: the bytes were referenced twice
  throughout, so the rename could not lose them.

No repository behaviour depends on this arrangement, nothing in the repository
creates it, and `tools.model_acquisition` accepts no cache-root override — the
documented path is pinned by `_assert_documented_cache`. It is recorded because an
evidence project should not let a host peculiarity silently flatter a result.

## Governance deviations

### `V1-S2-005` consumed three merged PRs where the plan allows two

PR rule 1 says every story must complete in one or two PRs, and rule 5 says a story
needing a third must be split before implementation. `V1-S2-005` took three:

| Landing | What it carried |
|---|---|
| `fbf34f1`, PR #39 | The baseline experiment implementation |
| `561d0d6` and `39c6237` | The first real execution and its **failed** experiment evidence |
| `69a94e1`, PR #41 | Tooling fixes and the successful real baseline |

**Recorded as an accepted sprint governance deviation. No implementation rollback
is required, and this remediation does not restructure the merged work.**

Why it was accepted: preserving the failed pre-registered experiment as its own
landing was the right engineering decision, and it is unusually good evidence
precisely because it shows the experiment was not quietly adjusted after it failed.
Splitting the story before implementation would have been the compliant route to
the same outcome, and the deviation is that it was not split.

One detail the review did not have, added for accuracy: the middle landing is
**two linear commits on `main` with no merge commit**, unlike every other Sprint 2
PR, each of which merged through a merge commit. Whether that was a squash or
rebase merge of PR #40 or a direct push is not determinable from the repository
alone. It is recorded as observed rather than assumed.

### This remediation is itself follow-up work on merged stories

PR rule 7 says evidence-only follow-up work is not allowed after a story is marked
done. Most of this change is evidence work on `V1-S2-001`, `V1-S2-004`, and
`V1-S2-007`, whose PRs are merged.

The rule is not breached, and the reason should be explicit rather than assumed.
§3.1 says the next sprint must not begin until the user approves after review, and
that *"if the review finds a defect, the defect belongs to the sprint under review;
fix it, rerun the relevant gates, and ask the user to review again."* Sprint 2 has
not been approved, so its stories are not done in the sense rule 7 governs, and the
review that found these defects is the one §3.1 requires. The same route was taken
at the Sprint 1 boundary, recorded in
[the Sprint 1 completion remediation](sprint-1-completion-remediation-validation.md).

### No continuous-integration checks exist

There are no GitHub commit-status checks on `main`. The review accepted this and so
does this record: selecting and configuring a CI service is
[ADR 0005](../../architecture/decisions/ADR-0005-test-ci-and-certification-strategy.md)
D6, deliberately undecided, and manual lane execution is the accepted mechanism.
Every result below was produced by hand on one host. Nothing re-runs them.

## Method

Run from the public repository root:

```text
uv run --locked python -m tools.runtime_certification check
uv run --locked python -m tools.runtime_certification certify --confirm-real-runtime
uv run --locked python -m tools.model_lifecycle cache
uv run --locked python -m tools.model_lifecycle measure --confirm-real-runtime
uv run --locked python -m tools.model_acquisition check
uv run --locked python -m tools.model_acquisition verify
uv run --locked python -m tools.model_lifecycle cache --verify
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked python -m mypy
uv run --locked python -m pytest -q
git diff --check main
```

The two `model_lifecycle` commands in the middle were run with the documented cache
renamed aside; the sequence and its restoration are in
[the cache miss observation](v1-s2-007-cache-miss-observation.md). Markdown
trailing-whitespace, hard-tab, relative-link, and private-information sweeps were
run over every changed file.

## Results

| Check | Result |
|---|---|
| C2 certification, authorized real run | **Certified.** `local-real-cpu`, labelled `local real runtime` |
| Real cache miss and refusal | **Observed.** `miss`, exit `3`, no container created |
| Real cache hit and integrity | **Verified.** 1,834,426,016 bytes, SHA-256 matched |
| Ruff lint | Passed; all checks passed |
| Ruff formatting | Passed; 267 files already formatted |
| Strict mypy | Passed; 147 source files checked |
| Default pytest lane | Passed; 5,663 passed, 27 skipped, 14 deselected. Real-runtime tests remained deselected |
| Focused telemetry catalog suite | Passed; 458 tests, including the replaced template-count assertions |
| `git diff --check main` | No trailing-whitespace or hard-tab match |
| Markdown whitespace/hard-tab sweep | No match across every changed file |
| Relative Markdown link sweep | 258 relative links checked in changed files; no broken target |
| Private-information sweep | No absolute path, username, planning-repository reference, or credential-shaped string in any changed file |
| `gitleaks detect --config .gitleaks.toml --no-banner` | **Not run**; `gitleaks` is not installed on this host |

The `gitleaks` row is reported rather than claimed, exactly as every prior record in
this repository reports it. A secret scanner has still never been run here, which is
why the matrix correction above left that half of the sentence standing.

### The test count moved, and by how much it should have

The Sprint 2 head collects 5,686 selected tests; this branch collects 5,690. The
review reported 5,659 passed and 27 skipped at the head, which is that same 5,686.
The four are accounted for individually rather than assumed:

| Change | Tests |
|---|---|
| The replaced template-count assertion, still four parametrized cases | 0 |
| `test_a_template_that_produced_nothing_says_so_rather_than_going_quiet` | +1 |
| `test_a_reserved_term_appears_only_where_it_is_denied`, parametrized per Markdown document, over three new records | +3 |

No test was deleted, and the skip count is unchanged at 27 — the two symbolic-link
cleanup cases this host cannot create, plus the 25 that predate Sprint 2. None of
the 14 deselected real-runtime cases was counted as a pass anywhere in this record;
the two real runs above were executed by hand, outside the default lane.

## Limitations

- **One host, one day.** Both executed runs are Windows 11, `AMD64`, CPU only. No
  second host, no second operating system, no accelerator, and no repetition.
- **One certification run.** No variance, no distribution, and a readiness margin
  under five per cent that a busier host could plausibly exceed.
- **The certification failure path is still synthetic.** Nothing failed, so no
  diagnostics record was earned, and the stage-naming behaviour remains proved by
  tests only.
- **Resumption is still synthetic.** No real interrupted transfer has been resumed.
- **The `partial` cache state is still synthetic.** No `.part` file was created.
- **No new capability is published here**, no ADR is reversed, no contract or API
  surface changes, and no claim in the matrix changes level.
- **The template-count correction rests on a declaration, not on inference.** A
  record produced from a template that does not declare it is not counted. That is
  a deliberate undercount rather than a guess, and the suite enforces the
  declaration, not the authorship.
- **This record cannot approve Sprint 2.** §3.1 reserves that to the user.

## Authorisation

Required: **yes**, for the two executed runs — they read 1.71 GiB of real model
bytes, operate a local container, and occupy the host's CPUs.

Granted by: the host owner, on 2026-09-04. The C2 run was directed by name in the
completion review. The cache-miss sequence was authorized separately after the
exact rename-and-restore steps, the second hard link protecting the bytes, and the
absence of any download were put to the owner.

Cost: none. No cloud capacity was allocated, no paid service was contacted, and
nothing was downloaded — the image and the model artifact were already present.

Cleanup: verified. `docker ps -a` was empty after every run, and the model cache
was restored and re-verified.

Review: an independent second reader examined the first commit of this branch
against the completion review's eight required items before push. The findings and
what they changed are recorded below.

## Independent second-eye review

INDEPENDENT_REVIEW_PLACEHOLDER
