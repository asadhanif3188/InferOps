# V1-S4-007-PR1 — validating the change that tests unready-model rejection and recovery

Date captured: 2026-09-16

Classification: **local real evidence** for the executed result, **documented and
unexecuted** for nothing — every piece of this change was run. The offline suite is
**synthetic** and certifies nothing about serving, and says so in its own docstring and
in the test inventory.

## What this PR adds

| Piece | Path |
|---|---|
| Descriptor | [`deploy/serving/experiments/unready-model-recovery.v1.json`](../../../deploy/serving/experiments/unready-model-recovery.v1.json) |
| Values overlay (the whole disruption) | [`deploy/serving/experiments/unready-model-values.v1.yaml`](../../../deploy/serving/experiments/unready-model-values.v1.yaml) |
| Operating script | [`scripts/environment/unready-model-recovery.sh`](../../../scripts/environment/unready-model-recovery.sh) |
| Record tool | [`tools/unready_model_recovery`](../../../tools/unready_model_recovery) |
| Offline suite | [`tests/architecture/test_unready_model_recovery.py`](../../../tests/architecture/test_unready_model_recovery.py) |
| Safety registration | the script's name in `ENTRY_POINTS` in [`test_cluster_lifecycle_safety.py`](../../../tests/architecture/test_cluster_lifecycle_safety.py), and in both classification lists in [`test_local_cluster_provider_contract.py`](../../../tests/architecture/test_local_cluster_provider_contract.py) |
| Test inventory | a row in [`test-inventory.v1alpha1.json`](../../testing/test-inventory.v1alpha1.json) and [`test-inventory.md`](../../testing/test-inventory.md), with empty `claims` and a prose note |
| Procedure | [`docs/serving/unready-model-recovery.md`](../../serving/unready-model-recovery.md) |
| Report template | [`TEMPLATE-unready-model-recovery.md`](TEMPLATE-unready-model-recovery.md) |
| Executed result | [`v1-s4-007-pr1-unready-model-recovery.md`](v1-s4-007-pr1-unready-model-recovery.md) with its six inputs and its record |

The split is the one every cluster experiment here uses. The shell script owns every
contact with the cluster and the two mutating commands that follow the install; the
Python owns every assertion and the labelled record and contacts nothing but one
loopback collector. One thing is new: **the record tool also builds the diagnostics
document**, because deciding what of a capture is publishable is the same decision the
record's own privacy check makes, and there may be only one definition of it.

## Architecture, contract, and design decisions

**No accepted decision is changed.** `ADR 0010` and `ADR 0013` each gain one dated
implementation-update note, appended after the section it updates and changing no
sentence of it. ADR 0010's note records what happened when D8's one *observed* row was
arranged deliberately — the runtime answered exactly as D8 says, and a caller received
the *other* code, because the readiness gate removes the Service's only address before
the adapter can observe the `503`. ADR 0013's note records that a fourth committed
descriptor and a fourth refusing tool now exist. Neither note amends a decision, and
both say so.

**The disruption mechanism is a design decision, and the descriptor carries the
alternatives.** Five mechanisms were considered and rejected. **Two were measured**
against the pinned image and the cached artifact: a well-sized file that is not a GGUF,
which makes `llama-server` **exit 1** — restart churn, not a healthy process — and a
context size at the schema maximum, which was installed on the cluster and failed twice
over. **Three were ruled out by reading the chart**, and are design consequences rather
than measurements: an artifact size or hash mismatch is `V1-S3-008`'s and is refused
before the runtime container starts; an absent artifact fails the same init container,
which reads the same derived path the runtime is given, by design; and a health path the
runtime does not serve would leave the model ready and the probe wrong. The descriptor
lists all five with the reason each was rejected, and the tool refuses a descriptor that
names fewer than three — because a descriptor stating only the mechanism that was taken
hides the argument. An earlier version of this paragraph called all four rejections
measurements.

**This experiment expects an intervention, and that is the opposite of `V1-S4-006`.** A
deleted pod is replaced by the Deployment controller. A model that cannot load is not a
state any controller reverses, so the descriptor registers
`recoveryInterventionExpected: true` and names the one intervention in advance. A
descriptor claiming otherwise would be claiming a self-healing property this platform
does not have.

**One new boundary word.** This record's boundary sentence must also refuse
**recovery-time objective**, and the tool refuses a descriptor whose sentence does not,
because a record publishing an interval from a fix to a served completion is the shape
somebody reads as one.

## Tests and validation performed

Run from Git Bash at the repository root, inside the locked environment, after the
review fixes below.

```text
uv run --locked ruff format --check .                              432 files, clean
uv run --locked ruff check .                                       clean
uv run --locked python -m mypy                                     241 files, clean
uv run --locked python -m pytest tests/architecture -q             2271 passed, 3 skipped
uv run --locked python -m pytest tests/testing -q                  1867 passed
uv run --locked python -m pytest tests/security -q                 832 passed
uv run --locked python -m pytest -q                                9577 passed, 30 skipped, 14 deselected
bash -n scripts/environment/unready-model-recovery.sh              clean
python -m tools.unready_model_recovery check                       exit 0
python -m tools.unready_model_recovery verify \
  --dir docs/proof/serving --prefix v1-s4-007-pr1-                 exit 0
git diff --check                                                   clean
```

`shellcheck` is **not** installed on this host, so the shell lint
[`CONTRIBUTING.md`](../../../CONTRIBUTING.md) publishes was **not run**. `bash -n` was.
That gap is this repository's existing one and is not closed here.

Two registrations beyond the new files were needed and both were found by a suite
rather than remembered: the script's name belongs in `ENTRY_POINTS`, and it belongs in
*both* of the provider contract's classification lists, whose own test refuses a script
neither list names. The security baseline also refused this suite's privacy negative
controls, because it forbids a personal filesystem path in any committed file and does
not exempt a test demonstrating one -- which is the right rule, so the three poison
values are assembled from parts and no committed line contains one.

The offline suite is 120 tests and sits in the default lane, because it contacts
nothing: every cluster answer it reads is JSON it wrote into a temporary directory,
the probe record set and the diagnostics are strings it builds, the collector's answers
are a dictionary, and the operating script is read as text.

### What the suite is heaviest on

- **The disruption.** The whole argument that this is not `V1-S3-008` rests on the
  overlay touching no model value and on the integrity init container having passed. So
  the overlay is read as text as well as digested — a digest would not have noticed a
  model value being added — and a record whose init container did not exit zero is
  refused. The suite also refuses a descriptor that names fewer than three rejected
  mechanisms.
- **Readiness.** "The model never became ready" is a claim about every sample in a
  window, not about two of them. A sample inside the window reporting a ready pod, a
  gap wider than six polls, a window held for less than the one that was registered, or
  fewer unready samples than the descriptor asks for each make the record unusable — and
  the sample count is taken over the unready window rather than over the file, because
  samples after the fix do not support a claim about before it.
- **The restart count.** The point of a TCP-connect liveness probe is that a healthy
  process loading a model is not killed. That is established only if the count was read,
  and bounded only if the window fits inside the runtime's own startup probe budget, so
  the descriptor is refused if it does not and the record publishes the window as a
  share of that budget.
- **The canonical refusal.** Which of the two codes `ADR 0010` D8 maps to this situation
  a caller met is a result. The suite requires both to stay in the registered vocabulary,
  refuses a probe reporting a code outside it, refuses a probe naming a surface, method,
  or path the descriptor does not register, and makes a run in which more than one code
  answered the window unusable.
- **Privacy.** It matters more here than in any other experiment in this repository,
  because one of the six inputs is a diagnostic bundle. The suite feeds a host path, a
  user directory, and an address into a capture excerpt and requires each to be refused,
  and it exercises the excerpt builder directly to establish that a line carrying an
  address is withheld **entire** and counted rather than masked.

## What independent review changed

Two reviews found real defects and both were confirmed before anything was changed; the
demonstration of the worst one is reproduced in the suite. The six committed inputs are
untouched. The record was **regenerated from them** by the corrected tool, so its
`descriptorSha256` is no longer the digest the run executed — the record now publishes
both under `derivation`, and the result document's provenance table carries both rows.

- **Phase labels were never checked against the window they name.** A readiness sample
  taken five seconds into the unready window could be relabelled `recovered`, given a
  ready pod, and satisfy `the-runtime-became-ready-after-the-fix` from 205 seconds
  before the recovered window opened — with `usable: true` and no failed check. Both
  readers now bind every row's instant to its own window, forwards-only slack of one
  poll or one round, and four negative controls cover it.
- **`every-capture-excerpt-is-publishable` could not fail.** `build_record` refuses the
  whole diagnostics text over the same shapes before any check runs, so the check could
  only pass and it inflated `usable`. The refusal is right and stays; the check was
  replaced by `the-withheld-line-accounting-reconciles`, which is reachable and is about
  the same property. The check count is unchanged at twenty-nine because one replaced
  one.
- **Two intervals were ceilings presented as measurements.** The socket figure is
  stamped when this workflow's first forward answers, with the whole install bookkeeping
  in between, and the recovery figure contains the forward being re-opened against the
  replaced pod. Both are renamed or split and disclosed, and the descriptor now
  pre-registers the socket origin, which nothing did before — which is why nothing
  caught it.
- **Telemetry readings had no lower bound**, so a point predating a window could be
  published under it. Each reading now carries the instant it came from, and any label
  set whose unready reading predates the window is listed. For this run that list is
  empty everywhere.
- **`telemetry-registered-signals-answered` would have failed a run that behaved as
  registered**: it required series from rows registered as *not* expected to expose, one
  of which is registered as empty for the unready window. It now asks each row what it
  was registered as.
- **The result document cited figures another record forbids citing**, compared them
  across hosts, and quoted a warm-arm figure inside a range labelled cold. The
  comparison is gone; the warm-page-cache limitation stays as a limitation.
- **The diagnostics table printed capture size as published size**, overstating one
  capture about thirteenfold. The record now carries kept, withheld and considered, and
  the table prints both columns.
- **A response body was quoted that was never captured.** The record stores a
  classification, not a body. The real envelope is quoted instead, and the byte count
  the probes recorded — 75 — is what ties the quotation to what was stored.
- Smaller: one tautological check half, one ordinal that disagreed with three other
  documents, one `up` claim that was substantively right and literally wrong, "roughly
  twice" for 1.7×, a missing distribution, a shell variable that leaked to the global
  scope, and a validation claim that rested on asserting a comment — which now asserts
  the classifier's source and the shape of every record it writes.

Recorded as deferred rather than fixed: eight small helpers in `tools/unready_model_recovery`
are now a third byte-identical copy of `tools/inference_pod_recovery`'s primitives. No
divergence was found. Consolidating three tools is not a test PR's job.

## Evidence produced, and what it is

| Evidence | Class | Where |
|---|---|---|
| The executed run: six inputs and the record they regenerate | **local real** (`local-real-cpu`, ceiling `C2`) | `docs/proof/serving/v1-s4-007-pr1-*` |
| The published reading of that run | **local real**, reviewed prose over measured figures | [`v1-s4-007-pr1-unready-model-recovery.md`](v1-s4-007-pr1-unready-model-recovery.md) |
| Everything the offline suite builds | **synthetic**, and certifies nothing | `tests/architecture/test_unready_model_recovery.py` |
| The two direct measurements that chose the mechanism | **local real**, recorded as prose in the descriptor and the overlay rather than as a record | descriptor `disruption.rejectedMechanisms` |
| The three mechanisms ruled out by reading the chart | **reasoned**, and labelled as such rather than as measurements | same |

## The experiment was executed nine times and one record was promoted

Eight executions were discarded and none of their evidence was promoted. Two of the
failures were self-inflicted — editing the script while bash was executing it, which
bash reads by file offset — and the rest were real defects the workflow only had because
it had never been run:

1. `curl -o` given a POSIX path a native binary could not open;
2. a request body carrying `max_tokens` and `temperature`, which the API's frozen subset
   refuses `contract-invalid` before readiness is consulted;
3. a rolling update's predecessor counted as a second pod;
4. the lifecycle reader ordering the idle baseline before the install;
5. waiting for *any* ready runtime pod, which stamped the recovery from the misconfigured
   pod whose starved load had finished — and a closed forward that had not released its
   socket, so the new forward refused to bind and the probes were answered by the old one.

One further execution was refused by the record tool's own privacy check, correctly, on
a pod address in `kubectl describe pod` output — which is why capture excerpts are now
filtered and counted. Every cause is listed with its output in
[the result](v1-s4-007-pr1-unready-model-recovery.md#commands-that-failed-and-their-output).
Only the ninth execution produced evidence, and it is the only evidence promoted.

## What was not run, and why

| Not run | Why |
|---|---|
| `shellcheck` | Not installed on this host. `bash -n` was run instead |
| A load profile against the unready release | `V1-S4-006` owns the under-load question. This one asks what a caller is told, not what a fleet experiences |
| A second provider | `ADR 0011` verifies `docker-desktop` only, and the descriptor describes only that provider |
| A repetition study | One release, misconfigured once. Nothing here is a distribution |
| A fix for the scientific-notation rendering defect | It is a chart defect found incidentally, and this is a test PR. It is recorded as follow-up |
| A fix for `llama-server`'s log being unpublishable | Its timestamps match this repository's address shape. Nobody has decided whether the check or the capture should change |

## Private-information inspection

Every changed and added file was read for leakage before this was written.

- **Host paths.** None. The record tool refuses any of the six inputs carrying a host
  path, a user directory, or an address that is not loopback, and it refused a real run
  on those grounds. The only drive-letter and user-directory strings in the diff are the
  deliberate poison values in the offline suite's negative controls.
- **Configuration.** The record keeps nine named ConfigMap keys and nothing else of the
  release. No secret is referenced, read, or rendered anywhere in this change.
- **Other workloads.** Counted, never named: 12 running pods across 3 namespaces.
- **Generated text.** `retainGeneratedText` is `false` and a test reads the script to
  establish that no completion body is kept. What the record keeps of a served completion
  is its status, its finish reason, its byte count, its digest, and its output token
  count.
- **Diagnostics.** Ten excerpt lines were withheld as unpublishable and the count is
  published beside each capture. The captures themselves are written whole into
  `.cache/inferops/experiments/`, which version control ignores.
- **Nothing from `InferOps-Planning`.** No planning document, backlog, prompt, or
  positioning material was copied into this repository.

## Acceptance criteria

| Criterion (this PR's boundary) | Status |
|---|---|
| Readiness remains false for the whole disrupted window | **Met, and measured from four places.** 21 samples, every one reporting 0 ready runtime pods, 0 ready runtime endpoints, 0 ready API pods and 0 ready API endpoints; the runtime answered `503 Loading model` at all 8 asks |
| Requests receive the canonical error | **Met, and it is not the one that would have been assumed.** All 8 completions came back `503 capability-unavailable`, condition `runtime-unreachable`, `retryable: true` — never `model-not-ready`, because the readiness gate removes the Service's address before the adapter can see the `503`. Recorded as observed, and ADR 0010 gains a dated note |
| Liveness does not destructively restart the runtime | **Met, and bounded.** Restart count 0 at every sample, and the socket answered at every probe round throughout the window. The instant it opened is not measured: the figure the record publishes is a ceiling containing this workflow's own install bookkeeping, and it is named and pre-registered as one. The window is 30.0% of the runtime's own startup probe budget, and the record publishes that share so the bound travels with the figure |
| Diagnostics identify the cause safely | **Met, with two limits recorded.** `runtime-resources` names the cause verbatim. Publishing required withholding 1 line of `kubectl describe pod` output and 9 of 10 lines of the runtime log, both counted in the record and both left as follow-up |
| Rollback restores real inference | **Met.** Dropping the overlay and upgrading the same release moved it from revision 1 to 2; the corrected pod — refused if it carries the misconfigured one's identity — reported Ready 20 880 ms later and a real completion came back 36 687 ms after the upgrade, three output tokens, content not retained |
| Telemetry signals classified honestly | **Met.** Ten expressions asked, including the one registered as emitting nothing and the one with no source; both answered with 0 series, as registered. `inferops_model_ready`, the one metric declared for this exact question, is the one that could not answer it |
| Nothing claims more than one run can support | **Met, and enforced.** The record carries `productionBenchmark`, `portableCapacityClaim`, and `availabilityClaim` all `false`, and its boundary sentence must also refuse *recovery-time objective* |

## Authorisation

Required: **yes**, for the executed run — it installs a release, loads a real model,
sends real requests, upgrades the release, and removes it. Granted before the run
through `--confirm-real-kubernetes` and two host values files.

Not required for the offline suite, the descriptor, the tool, or the documents: they
contact nothing.
