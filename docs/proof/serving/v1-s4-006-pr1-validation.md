# V1-S4-006-PR1 — validating the change that measures inference pod recovery

Date captured: 2026-09-16

Classification: **local static evidence** for the change itself, alongside one
**local real** executed record. The change is validated by the repository's own
offline suites; the experiment it adds was executed twice on `docker-desktop` and its
result is [`v1-s4-006-pr1-inference-pod-recovery.md`](v1-s4-006-pr1-inference-pod-recovery.md).
This record is about the change, not about recovery.

## What this PR adds

| Piece | Path |
|---|---|
| Committed descriptor | [`deploy/serving/experiments/inference-pod-recovery.v1.json`](../../../deploy/serving/experiments/inference-pod-recovery.v1.json) |
| Operating script | [`scripts/environment/inference-pod-recovery.sh`](../../../scripts/environment/inference-pod-recovery.sh) |
| Assertions and record | [`tools/inference_pod_recovery/`](../../../tools/inference_pod_recovery/) |
| Offline suite | [`tests/architecture/test_inference_pod_recovery.py`](../../../tests/architecture/test_inference_pod_recovery.py) |
| Procedure | [`docs/serving/inference-pod-recovery.md`](../../serving/inference-pod-recovery.md) |
| Report template | [`TEMPLATE-inference-pod-recovery.md`](TEMPLATE-inference-pod-recovery.md) |
| Executed result | [`v1-s4-006-pr1-inference-pod-recovery.md`](v1-s4-006-pr1-inference-pod-recovery.md) + six committed inputs and the record |

The split is the one the other Kubernetes workflows here use: the shell owns every
contact with the cluster and the one delete, and the Python owns everything that can be
decided without one. The record builder is a pure function of six committed inputs.

## Architecture, contract, and design decisions

**No accepted decision is changed.** ADR 0013 already permits a bounded local
observation from a declared experiment; its D1 and D3 each gain a dated
`Implementation update, 2026-09-16 (V1-S4-006-PR1)` note recording two facts about the
world rather than a new permission: that a failure experiment publishes recovery and
before/during/after figures under D1 (which the Sprint 4 §11.1 amendment already listed
as permitted evidence for this exact environment), and that there is now a third
committed descriptor of the kind D3 clause 1 requires and a third tool that refuses a
record without its boundary. No accepted sentence was spliced; the notes sit beside
them. D2 is untouched, and the gap it states — that whether a figure is *presented* as
an availability figure is not machine-checked anywhere — is restated rather than
implied closed.

**One thing this record's flags do that no earlier record's did.** The descriptor and
the record carry `availabilityClaim: false` beside the `productionBenchmark` and
`portableCapacityClaim` flags ADR 0013 D3 requires, and the tool refuses a descriptor
or record where it is not `false`. A recovery experiment is the first one in this
repository whose figures could be mistaken for an availability claim, so the flag is
new here.

**The experiment does not repeat `V1-S3-003-PR2`.** The descriptor carries a
`distinctProofQuestion`, the procedure states it, and a test asserts that **no field of
the record** reports an artifact identity — no `inode`, no `mtime`, no artifact digest
or byte count. Persistence stays Sprint 3's result.

## Tests and validation performed

Run from Git Bash at the repository root, inside the locked environment.

```text
uv run --locked ruff format --check .                              421 files, clean
uv run --locked ruff check .                                       clean
uv run --locked python -m mypy                                     236 files, clean
uv run --locked python -m pytest tests/architecture -q             pass
uv run --locked python -m pytest tests/testing -q                  pass
uv run --locked python -m pytest tests/security -q                 pass
uv run --locked python -m pytest -q                                pass
bash -n scripts/environment/inference-pod-recovery.sh              clean
python -m tools.inference_pod_recovery check                       exit 0
python -m tools.inference_pod_recovery verify \
  --dir docs/proof/serving --prefix v1-s4-006-pr1-                 exit 0
git diff --check                                                   clean
```

`shellcheck` is **not** installed on this host, so the shell lint
[`CONTRIBUTING.md`](../../../CONTRIBUTING.md) publishes was **not run**. `bash -n` was.
That gap is this repository's existing one and is not closed here.

**Two pre-existing suites were seen to fail once, under load, and are not this
change's.** In one full-lane run taken while other work was running on the same host,
`test_target_verification.py::test_a_mechanism_this_project_does_not_implement_refuses_before_loading`
and `test_terraform_prerequisites.py::test_the_configuration_validates` failed; both
shell out to `terraform` or to fake `kubectl`/`docker` binaries and both passed on a
quiet host, in isolation and in a clean lane. Neither file is touched by this branch.
It is recorded because a failure that is omitted is the one the next person repeats.

The new offline suite carries `pytestmark = pytest.mark.architecture` and is in the
default lane, because it contacts nothing: raw load record sets are produced by
`tools.llm_load.execute` against an injected transport and a fake clock, the cluster's
answers are JSON in a temporary directory, the collector's answers are a dictionary,
and the operating script is read as text.

### What the suite is heaviest on

- **The one delete**, read off the script: exactly one `inferops::target_kubectl delete`,
  naming one pod, with no label selector, no `--all`, and no `--timeout` beside
  `--wait=false`; no namespace, claim, or cluster deletion; every call through the
  verified-target wrappers; confirmation, values, and target verification all before
  anything is contacted; and **no mutating command at all between the delete and the
  uninstall**, which is what the record's empty intervention list rests on.
- **Where each interval begins and ends**, including two shapes refused by name that an
  independent review of `V1-S3-003-PR2` had to correct there: a recovery stamped from a
  forward accepting a connection, and a replacement stamped from the Deployment's
  aggregate.
- **The record's refusals**: a selector that matched two pods, a replacement carrying
  the deleted pod's identity, a release revision that moved, an acquisition Job that
  appeared, a Service that never lost an endpoint, readiness samples that leave a gap,
  a registered absence that answered, a registered signal that did not, an untouched
  tier that restarted, an intervention outside the recorded vocabulary, a delete issued
  at an unregistered offset, and any input carrying a host path or a network address.

## Evidence produced, and what it is

| Evidence | Class | Where |
|---|---|---|
| The executed experiment | **local real** (`local-real-cpu`, ceiling `C2`) | the record and its six inputs, under the `v1-s4-006-pr1-` prefix |
| Every figure in the offline suite | **synthetic**, and certifies nothing | in-process only; nothing is committed from it |
| The report template | **documented, unexecuted** | a template, never edited to hold a result |

## The experiment was run twice, and the first record was discarded

The first attempt is not committed. It produced a record whose twenty-two checks all
passed and whose figures were wrong: it stamped the recovery from the first request
served after the delete, that request was answered by the pod that was going away, and
two published intervals came out negative — `firstUnsuccessfulToFirstServedMs:
-25842` and `replacementReadyToFirstServedCompletionMs: -19654`.

The defect was in this change's own code, not in the run, and it contradicted this
change's own pre-registration: the descriptor had registered
`callerVisibleOutageFrom: first-unsuccessful-request-after-deletion` before anything
ran. **The descriptor was not edited.** The record builder was brought into line with
it, the window set gained `servedWhileDraining` so that what the draining pod served is
neither folded into the outage nor attributed to the replacement, a
`no-published-interval-is-negative` check was added, and the experiment was re-run. The
precedent is `V1-S3-003-PR2`, whose review corrected two stamps and re-ran rather than
publishing with a caveat.

Running it twice also established something one run could not: the API has **two**
distinct failure modes when its runtime disappears, and the first attempt saw only one
of them. Both are in the result record.

## Independent review, and what it changed

An independent review of this change was run before the first commit and reported two
findings. Both are addressed in the second commit, which is where the record of the
review lives.

1. **`afterInTheDisruptedRun` could borrow an instant from the other run.** The
   window's contents are correctly gated on the service having been restored in the
   disrupted run, but its `startEpochMs` was computed whenever a restoration existed at
   all. Where a restoration is seen in the *recovered* run, that window is empty and
   still carried a second-run timestamp under a name that says otherwise. **This is
   latent in the committed record** — that run's service was restored in the disrupted
   run, so the field is correct there — and `verify` still regenerates the committed
   record byte for byte after the fix, which is what shows the fix changed nothing for
   this evidence. A regression test was added that fails without the fix.
2. **Two tests asserted presence rather than value.** The in-flight count is now
   checked against the raw set, and the same-phase comparison now has both a case where
   it is available and one where it is not.

The review found no problem with the delete's safety argument, the interval stamping,
vacuous checks, prose overclaims, the reuse boundary against
`tools.performance_scenarios`, or private-information leakage.

## What was not run, and why

| Not run | Why |
|---|---|
| `shellcheck` | Not installed on this host. `bash -n` was run instead |
| The experiment on `kind` | The descriptor describes `docker-desktop` only, and ADR 0011 forbids reading one provider's evidence as another's |
| A multi-replica variant | The descriptor refuses a second runtime replica; this experiment is defined for one, and two would change what a caller saw |
| Any alerting on the disruption | No alerting rule, receiver, or runbook link exists. `V1-S4-008` owns that |
| A third execution | The second is the record; the first is described above and discarded |

## Private-information inspection

The public diff was read for leakage before committing. What the run touched and what
the record keeps:

- **Host paths.** The two operator values files are passed by path at run time and
  appear in the report as `<host API image values>` and `<host model seed values>`.
  `refuse_private` runs over every input and over the finished record before either is
  written, and refuses a drive-letter path, a `Users`/`home` directory, or any IPv4
  that is not loopback or the any-address. A test injects a private shape into each of
  the six inputs and asserts the refusal.
- **Configuration.** The environment keeps a fixed allowlist of nine ConfigMap keys.
  `INFEROPS_LLAMA_SERVER_ENDPOINT` is deliberately outside it, and the suite's fixture
  pins that key to a documentation address specifically to prove it is dropped.
- **Other workloads.** Counted, never named: 12 running pods in 3 other namespaces.
- **Generated text.** The descriptor sets `retainGeneratedText: false`; no prompt or
  completion appears in any committed file, and a test asserts it.
- **Nothing from `InferOps-Planning`.** No prose, prompt, backlog item, or local path
  from the private requirements repository is reproduced here.

Cluster-internal pod names, the namespace, image digests, and the node name are
reproduced as emitted, as every other Kubernetes record in this repository does.

## Acceptance criteria

| Criterion (this PR's boundary) | Status |
|---|---|
| Experiment deletes only the intended pod | **Met, and checked three ways.** The pod is located by counting rather than indexing, its name is held to a Kubernetes name shape before it reaches the delete, the count of matching pods is taken again immediately before the delete and must be 1, the record records `podsMatchingSelector: 1`, and the offline suite reads the script to establish that there is exactly one delete, that it names one pod, and that it carries no selector and no `--all` |
| Traffic runs before, during, and after failure | **Met, and measured.** 6 requests dispatched before the delete, 41 during the outage, 84 after it in the same run, and 183 in a second run of the same profile |
| Detection, errors, latency impact, replacement, model reload, and readiness recovery are measured | **Met.** Detection from the first unserved request and from the readiness samples; errors by canonical code and condition; latency by nearest-rank percentile per window; replacement from the replacement pod's own `Ready` condition; model reload from first sighting to that condition; readiness recovery from the runtime Service's ready-endpoint count |
| The experiment distinguishes its purpose from S3-003's persistence proof | **Met, and enforced.** A `distinctProofQuestion` in the descriptor, a section in both documents, and a test that refuses any record field reporting an artifact identity |
| Telemetry signals that did and did not expose the event are recorded | **Met.** Nine expressions were registered with an expectation before the run and all nine were asked. Seven answered and two returned no series, as registered. Which ones exposed the event is stated in the reviewed report, not decided by the tool |
| Required human action is recorded | **Met.** Two authorisations before the run, and no intervention between the delete and the uninstall — a claim the offline suite backs by reading the script |
| Environment/provider limitations are explicit and no availability/SLO claim is made | **Met.** Eight limitations in the descriptor, repeated verbatim in the procedure by test, and `availabilityClaim: false` carried and enforced |

### The parent story

`V1-S4-006` has one PR and this is it. Every acceptance criterion of the story is
addressed above. Nothing is deferred to a later PR of this story, because there is none.

## Authorisation

Required: **yes**, for the executed experiment. Granted by the host owner for both
attempts, for `docker-desktop` specifically. Full terms, and what survived the run, are
in [the result record](v1-s4-006-pr1-inference-pod-recovery.md#authorisation).

Not required for this change's own validation, which reads committed files and executes
nothing outside the repository.
