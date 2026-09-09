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
- `tests/architecture/test_helm_upgrade_rollback.py` — 143 checks, one of which
  skips where the host does not permit creating a symlink.
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
| `python -m pytest tests/architecture/test_helm_upgrade_rollback.py -q` | 142 passed, 1 skipped |
| `python -m pytest -q` | 7,090 passed, 29 skipped, 14 deselected |
| `python -m ruff check .` | clean |
| `python -m ruff format --check .` | clean |
| `python -m mypy` | 28 pre-existing errors in 25 files, none in this change |
| `python -m tools.helm_upgrade_rollback check` | descriptor accepted; `execution not started` |
| `bash -n scripts/environment/helm-upgrade-rollback.sh` | parses |
| `shellcheck scripts/environment/helm-upgrade-rollback.sh` | **not run**: shellcheck is not installed on this host |
| `git diff --check` | no whitespace errors |

The one skip is the symlink test: creating a directory symlink needs a privilege
this host does not always grant, and the test skips rather than passing on a
check it could not perform.

## What the suite establishes, and what it cannot

It establishes that the descriptor agrees with the certification, the chart, the
chart's schema, the chart's validation template, `lib.sh`, and the model source
record; that thirty-two ways of weakening the descriptor are each refused with a
message naming what was weakened; that **thirty-nine** ways of making a run look
better than it was each stop it, among them a baseline that was never healthy, a
candidate the cluster never applied, a candidate served by the pod that was
already serving, a healthy "unhealthy" candidate, a deadline read as health, a
decisive signal with a zero exit code, a failure read off another workload, a
candidate that never scheduled, a failing pod that was the serving pod, a
rollback that left the fault in place, a rollback to the wrong revision, a
rollback recorded as the revision it restored, a clock that runs backwards, two
clocks that disagree, a window nobody sampled, a mock answering afterwards, a
mock adapter kind, an absent token-usage declaration, an empty completion, and
token counts that do not add up; and that the operating script has the safety
properties this project requires of anything that operates a cluster.

It establishes **nothing** about what happens when it is run. Every fact it reads
is a document this suite wrote. Every answer the restored release gives is a
dictionary this suite constructed. No `helm upgrade` has been issued, no init
container has failed, no rollback has been performed, and no recovery has been
timed. A static reading of a shell script is not a substitute for running it, and
neither is a synthetic answer for a model's.

The `local real Kubernetes` label the module writes is truthful only for an
authorized run against the real release. Nothing in this change produces it.

## What was checked against the chart itself, offline

`helm template` renders locally and contacts no cluster, so three claims this
change makes about the chart were checked rather than asserted. Every command
below was run from the repository root against
`charts/inferops-llm/ci/real-values.yaml`, which is a render fixture and is not
installable.

| Question | Command | Result |
|---|---|---|
| Does the chart **accept** the injected fault? | `helm template inferops charts/inferops-llm --namespace inferops-release --values charts/inferops-llm/ci/real-values.yaml --set model.artifact.sizeBytes=1` | Renders. The verification script becomes `if [ "$present" != "1" ]`, which the pinned 1,834,426,016-byte artifact cannot satisfy |
| Does the controlled change **roll** the workload? | the same, with `--set telemetry.serviceVersion=v1-s3-008-candidate` | Both Deployments' `inferops.io/configuration-checksum` values change against the unmodified render |
| Does the fault **spare** the platform API? | diff of the two rendered pod templates | The platform API's pod template is **byte-identical** across the fault; the serving runtime's differs |

The third is the one that matters, and it was an assertion in the descriptor
before it was a measurement. It is what makes the impact record mean anything: if
the fault rolled the API as well, every readiness probe during the failure window
would be asking a tier that was itself being replaced, and "no caller saw a
failure" would be a statement about two rollouts rather than one. The chart
itself is now the proof — `model.artifact.sizeBytes` appears in exactly one
template outside the validation helper, the verification script that only the
runtime's Deployment includes, and it is absent from `inferops-llm.derivedEnv` —
and a test asserts that structure so the property survives an edit to the chart.

These renders were **not** installed, applied, or sent anywhere. `helm template`
is local text substitution.

## What independent review found, and what changed

Two independent reviews ran before the push: one over the whole change, one over
the operating script alone. Between them they raised one HIGH, two MEDIUM, and
four LOW findings. Every one is fixed.

**HIGH — the deliberately-failing `helm upgrade` was not in the cleanup path.**
It is backgrounded so that the detection is not a timeout, and its pid was
captured where it was started rather than declared with the other two. A run that
ended between backgrounding it and waiting for it — an interrupt during the
detection loop, or a refusal inside it — would have left a `helm upgrade` running
detached against a real release, still writing that release's history, while the
script printed the `helm uninstall` that would race it. All three pids are now
declared together and `stop_background` kills and reaps each one. A test derives
the set of backgrounded pids from the script and fails if any of them is missing
from the cleanup function, so this cannot be reintroduced by adding a fourth.

**MEDIUM — the exit trap named only `EXIT`.** Both sibling certification scripts
use `trap on_exit INT TERM EXIT`, and one of them carries the reason in a
comment: Bash normally runs an EXIT trap when a signal terminates the shell, but
on Git Bash signal delivery to a native child is less predictable. This script
backgrounds *more* than either sibling and had dropped the convention. It now
names the signals, and a test asserts that all three scripts do.

**MEDIUM — three queries were piped straight into a parser.** `require_query ...
| python -c ...` aborts correctly when the query fails, but python still runs
against empty input first and prints a JSON traceback on top of the refusal that
explains it. Two failures for one cause reads as two causes. All three now
capture and then parse, which is what the rest of the file already did, and a
test refuses the pipe shape.

**LOW — `--port` accepted `0` and values above 65535.** `kubectl port-forward`
reads `0` as "pick an ephemeral port", this script never parses back the port
that was bound, and the run would have failed later as an unopened forward rather
than immediately as a bad argument. It is now range-checked.

**LOW — three descriptor fields reached a label selector and a jsonpath filter
unchecked.** The candidate value was held to a plain-identifier shape at the
point of use and the two component names and the verification container name were
not. They are committed, validated values, so this was never exploitable — but a
rule applied to one interpolation and not the next is a rule a later edit reads as
optional. All three are now held to a DNS-1123 label.

**LOW — the detection poll interval had no floor in the shell.** Below 1,000 ms
the millisecond-to-second division truncates to zero and the loop becomes a busy
poll against the API server. The Python validator refuses it, and the script
already carries a comment explaining why a guard that depends on the order two
programs run in is not enough; the magnitude half of that argument is now
enforced beside the numeric half.

**LOW — a docstring described the chart's refusal when it was testing this
module's own floor.** Reworded; the test that actually reads `_validate.tpl` is
named beside it.

Two further defects were found by the author's own pass and are fixed here:

**`record_stage` turned an unanswered query into an empty value.** Four fields
used `|| value=""`. Three of them may legitimately be empty — the service version
before the upgrade, and either pod name while nothing of that component is ready
— so an API server that refused the query was indistinguishable from the release
genuinely having nothing to report, and the run would then have reported that the
upgrade never reached the workload, which names the wrong thing entirely. This is
the same reading `helm-lifecycle.sh` already refuses for claim counts. The status
is now checked and the value is not, and a test refuses the fallback shape.

**Nine assertions had no test behind them.** A check nobody has seen fail is a
check nobody has seen. Each now has one: stage names that are not the four, a
baseline slower than a healthy rollout, a controlled upgrade over budget, a
release test passing against a stage recorded as failed, an unhealthy stage
shorter than the detection inside it, a rollback over budget, a rollback to a
byte count that is neither the injected one nor the pin, a run that recorded no
recovery at all, and an impact window that does not run forwards.

## Deferred, and depended on

- **The run itself.** It needs an InferOps API image, which does not exist. When
  one does, the run is `scripts/environment/helm-upgrade-rollback.sh run --values
  ... --confirm-real-kubernetes` and its record goes beside this one.
- **`shellcheck`.** It is not installed on this host, so it was not run. The
  script parses under `bash -n`, and every rule
  `tests/architecture/test_cluster_lifecycle_safety.py` states for a script that
  operates a cluster is applied to it, but neither of those is a shellcheck scan.
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
