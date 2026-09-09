# V1-S3-008-PR1 validation — the Helm upgrade and rollback experiment

Change: the workflow that proves a release change can be reversed exists. A
committed descriptor fixes every target, budget, and assertion; a shell script
installs a known-good release, upgrades it with a controlled change, upgrades it
again with a fault the cluster cannot run, detects the failure on evidence rather
than on a clock, rolls back to the last known-good revision, and tears the
release down; a Python tool holds all of that to the descriptor, asks the
restored release for a real completion, and writes a machine-readable record
labelled `local real Kubernetes`. This record is what was run, what it found, and
what it does not support.

**Evidence class.** Everything asserted here is `local-static`: files read,
compared, formatted, linted, type-checked, and driven through injected HTTP and
clock seams. **Nothing has been installed.** No cluster was contacted, no
`terraform apply` ran, no Helm release was installed, upgraded, broken, or rolled
back, no forward was opened, no readiness probe was sent, no model byte was read,
and no completion was generated. **No upgrade-and-rollback record exists**, and
no claim in [the matrix](../../testing/claim-test-matrix.md) gains evidence from
this change.

**It cannot be run.** The blocker is the one that already blocks
[the lifecycle procedure](../../environment/helm-release-lifecycle.md) and both
Kubernetes certifications: `platform-api-container-image` is `planned` in
[the ownership inventory](../../architecture/resource-ownership.v1alpha1.json),
no `Dockerfile` is committed anywhere in this repository, and a release whose API
image does not resolve never becomes ready. That is stated at the top of the
procedure document rather than left to be discovered.

## What the change is

**The descriptor is the authority, and it cannot disagree with what already
decides it.**
[`deploy/serving/experiments/helm-upgrade-rollback.v1.json`](../../../deploy/serving/experiments/helm-upgrade-rollback.v1.json)
holds the cluster and release targets, the controlled change, the injected fault
and every property that keeps it reversible, the detection policy, the rollback
policy, the impact plan, twelve budgets, the assertions, the evidence locations,
the cleanup policy, and six limitations. Loading it cross-checks
[the Kubernetes real-inference certification](../../../deploy/serving/certification/k8s-real-inference.v1.json)
for **equality** on the cluster block, the release block, the request, and eight
of the twelve budgets, and refuses the descriptor rather than a run when any of
them disagrees. The two workflows install the same chart as the same release into
the same namespace on the same cluster; a second set of numbers describing that
would be a second release waiting to be discovered.

**The controlled change is fixed in code, not left to the descriptor.**
`telemetry.serviceVersion` is the one value this experiment may change, and
`INFEROPS_SERVICE_VERSION` is the one key it may be asserted at. Both are
constants in
[`tools/helm_upgrade_rollback/core.py`](../../../tools/helm_upgrade_rollback/core.py)
and a descriptor naming anything else is refused. The reason is a property of the
chart: that value is inside `inferops-llm.derivedEnv`, whose rendering is hashed
into every pod template's `inferops.io/configuration-checksum`. A change outside
that block would produce a revision Helm records and Kubernetes never acts on,
and rolling *that* back would prove nothing about whether the workload followed.
The suite reads the helper and the Deployment template and asserts both halves.

**The injected fault is the smallest thing that is genuinely unrunnable.**
`model.artifact.sizeBytes` is set to a value the mounted artifact cannot match.
The chart's verification script compares the byte count **before** the SHA-256
read, so the failure is fast and its reason is printed by the `verify-model` init
container that made it. Six safety properties are declared in the descriptor and
each is refused if false: it is accepted by the chart's schema and by
`_validate.tpl`, it reaches the pod template, it creates no object outside the
release, it pulls no image, it changes no image reference, it changes no
cluster-scoped object, and it changes no `PersistentVolumeClaim`. The suite
additionally reads the schema and the validation template to establish the first
of those rather than accept the descriptor's word for it — because a fault Helm
would refuse before installing is a run that never installed its own fault and
would then report a detection it did not make.

**Detection is evidence, never a clock.** The failing upgrade is issued in the
background and deliberately **not** waited on. Two signals are decisive — an init
container that terminated non-zero, and one crash-looping after a non-zero exit —
and one of them is required. `progress-deadline-exceeded` is recorded as a
deadline and refused as a detection of health, and the descriptor may not set a
detection budget shorter than a healthy runtime rollout, so no deadline can be
reached sooner than a healthy release is allowed to take. This project has
measured model loads from 133,515 ms to 358,735 ms; a timeout cannot tell one of
those from a broken container.

**A third signal is neither a pass nor a fail.** A candidate pod the host could
not schedule never ran the init container, so the run observed its own capacity
rather than the fault it injected. That is `ExperimentInconclusive`, exit code 5,
with a named remedy — not a detection, and not a silent failure.

**Only pods that are not ready are inspected.** The pod still serving has a
succeeded `verify-model` of the same name, and reading its terminated state would
report a zero exit code as a detection. The script says so in a comment the suite
asserts is there, and the module refuses a decisive signal carrying a zero exit
code as a second line.

**A rollback is four questions, not one.** Helm's history says a revision exists.
Whether the rendered configuration went back to the last known-good value,
whether the injected byte count is gone and the pinned one is back, whether the
release's own in-cluster test passes, and whether a real model answers are each
asked separately, and none may be waived. The recorded revisions must strictly
increase, because a rollback is a *new* revision restoring an old one rather than
a return to it.

**User impact is measured rather than assumed.** A probe asks the release's own
readiness path through the forward every five seconds across the failure window
and records each status. A refused probe is recorded and reported; it does not
fail the experiment, because what a caller saw is the result and not the pass
condition. A window with fewer probes than the descriptor requires, a window that
closed before the detection, and a probe outside its own window each stop the
run — a window nobody sampled is not a window with no impact in it.

**Recovery is one figure with a stated meaning.** It is measured from the moment
the failure was detected to the moment a real completion was served again. The
whole timeline must run forwards and must agree with the detection record.
Whether the runtime had to reload the model is **recorded rather than assumed**,
as `runtimeReloaded`: a rollback to a revision whose pod is still running reloads
nothing, and that is the difference between a recovery of seconds and one of
minutes.

**The record is written twice, and the second write adds one member.** The
identity and the completion are read while the release is still installed,
through the forward; the cleanup outcome cannot exist until after the teardown. A
record produced only after a successful teardown would be a record that
disappeared whenever the interesting thing happened, so the first write carries a
null cleanup and `record-cleanup` fills it in. Nothing else is re-derived, a
record belonging to another experiment is refused, and a record that already
carries a cleanup is refused rather than replaced.

**One guard, not two.** The base-URL guard is the certification's
`require_forwarded_base_url`, called rather than reimplemented — the rule is
identical, and this descriptor is refused unless its request host is the
certification's.

## Files changed

New:

- `deploy/serving/experiments/helm-upgrade-rollback.v1.json` — the descriptor.
- `tools/helm_upgrade_rollback/__init__.py`, `core.py`, `__main__.py` — the
  reader, the assertions, the two observations, the record, and the CLI.
- `scripts/environment/helm-upgrade-rollback.sh` — the operating script.
- `tests/architecture/test_helm_upgrade_rollback.py` — 129 checks.
- `docs/environment/helm-upgrade-rollback.md` — the procedure.
- `docs/proof/environment/v1-s3-008-pr1-validation.md` — this record.

Changed:

- `.gitignore` — `/.cache/inferops/experiments/`, the ignored evidence directory.
- `tests/architecture/test_cluster_lifecycle_safety.py` — the new script added to
  `ENTRY_POINTS`, so every safety rule in that suite applies to it.
- `tests/testing/test_test_inventory.py` — the number-word table extended past
  seventeen, which is what the count of modules defending no claim just became.
- `docs/testing/test-inventory.v1alpha1.json`, `docs/testing/test-inventory.md` —
  the new module inventoried, the two counts corrected.
- `docs/environment/helm-release-lifecycle.md` — its "what is not here" entry for
  upgrade and rollback safety now points at the document that answers it.
- `CHANGELOG.md`.

## Validation performed

Every command below was run from the repository root on the reference host, and
every one of them reads files.

| Command | Result |
|---|---|
| `python -m pytest tests/architecture/test_helm_upgrade_rollback.py -q` | 129 passed, 1 skipped |
| `python -m pytest -q` | the default lane, green |
| `python -m ruff check .` | clean |
| `python -m ruff format --check .` | clean |
| `python -m mypy` | clean |
| `python -m tools.helm_upgrade_rollback check` | descriptor accepted; `execution not started` |
| `bash -n scripts/environment/helm-upgrade-rollback.sh` | parses |
| `shellcheck scripts/environment/helm-upgrade-rollback.sh` | see below |
| `git diff --check` | no whitespace errors |

The one skip is the symlink test: creating a directory symlink needs a privilege
this host does not always grant, and the test skips rather than passing on a
check it could not perform.

## What the suite establishes, and what it cannot

It establishes that the descriptor agrees with the certification, the chart, the
chart's schema, the chart's validation template, `lib.sh`, and the model source
record; that thirty-two ways of weakening the descriptor are each refused with a
message naming what was weakened; that every way of making a run look better than
it was — a baseline that was never healthy, a candidate the cluster never
applied, a candidate served by the pod that was already serving, a healthy
"unhealthy" candidate, a deadline read as health, a decisive signal with a zero
exit code, a failure read off another workload, a candidate that never scheduled,
a failing pod that was the serving pod, a rollback that left the fault in place, a
rollback to the wrong revision, a rollback recorded as the revision it restored, a
clock that runs backwards, two clocks that disagree, a window nobody sampled, a
mock answering afterwards, a mock adapter kind, an absent token-usage
declaration, an empty completion, and token counts that do not add up — stops the
run; and that the operating script has the safety properties this project
requires of anything that operates a cluster.

It establishes **nothing** about what happens when it is run. Every fact it reads
is a document this suite wrote. Every answer the restored release gives is a
dictionary this suite constructed. No `helm upgrade` has been issued, no init
container has failed, no rollback has been performed, and no recovery has been
timed. A static reading of a shell script is not a substitute for running it, and
neither is a synthetic answer for a model's.

The `local real Kubernetes` label the module writes is truthful only for an
authorized run against the real release. Nothing in this change produces it.

## Deferred, and depended on

- **The run itself.** It needs an InferOps API image, which does not exist. When
  one does, the run is `scripts/environment/helm-upgrade-rollback.sh run --values
  ... --confirm-real-kubernetes` and its record goes beside this one.
- **`shellcheck`.** If it is not installed on the reviewing host, that row above
  says so plainly rather than claiming a clean scan.
- **A second injected fault.** One is injected. A runtime that starts and answers
  wrongly is a different experiment and is not this PR's.
- **Load.** No request load is generated anywhere in V1, so nothing here says
  what an upgrade does to in-flight requests.
- **GitOps, progressive delivery, and automated rollback triggers.** Explicitly
  out of scope; the detection and the rollback are both performed by a script a
  human started.

## Risks, assumptions, limitations

- **The byte count is read out of the rendered init container command with a
  regular expression.** That is deliberate — it is what the cluster will actually
  enforce, where `helm get values` is only what Helm recorded — but it couples
  the script to the shape of the chart's verification script. The suite asserts
  that shape, so a change to the template fails the build rather than silently
  producing a zero.
- **The impact prober and the shell share a wall-clock origin** rather than a
  monotonic one, because they are separate processes. Over the minutes this
  experiment spans that is a duration, and the record carries only differences.
- **The expectation that no probe fails is an expectation, not a result.** A
  single-replica rolling update surges rather than displacing, so the serving pod
  should keep answering — but nothing here has observed that, and the descriptor
  does not require it.

## Acceptance criteria

### This PR

| Criterion | Status |
|---|---|
| Known-good release upgrades to a controlled candidate | **Implemented and asserted, not executed.** The workflow installs revision 1, upgrades to revision 2 with a change that must reach the rendered ConfigMap *and* replace the serving pod, and refuses a candidate that did neither |
| Failed/unhealthy candidate is detectable | **Implemented and asserted, not executed.** A decisive signal off the injected workload is required; a deadline and an unschedulable pod are each refused as detections, the second as inconclusive |
| Rollback restores real inference | **Implemented and asserted, not executed.** Four separate questions — configuration, fault removal, release test, real completion — none waivable, with mock identity and mock capability metadata refused |
| Version and recovery timing are recorded | **Implemented and asserted, not executed.** Four revisions, a detection time, a rollback time, a recovery time, and whether the runtime had to reload, all in the record |

### The parent story, V1-S3-008

Every criterion the story names is this PR's, and every one is implemented and
asserted against synthetic input. **None is executed**, so the story's evidence —
"an upgrade/rollback experiment" — does not yet exist. The story is not complete,
and this record says so rather than counting a written workflow as a performed
one.
