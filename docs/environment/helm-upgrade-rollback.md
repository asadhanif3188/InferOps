# Upgrading a release, breaking it on purpose, and getting it back

Status: **executed on the `docker-desktop` provider.** The record is
[`docs/proof/environment/v1-s3-011-pr2-upgrade-rollback.md`](../proof/environment/v1-s3-011-pr2-upgrade-rollback.md).
A real release was installed, upgraded with a controlled change, upgraded again
with a fault the cluster could not run, detected off the workload the fault was
injected into, rolled back to its last known-good revision, and a real model
answered again.

This document previously said the experiment was written and never run, and that
the blocker was one line: **no InferOps API image is published.** That image now
exists and is loaded into the selected cluster. Five attempts were needed, four
of them failed, and each failure found a defect that only an execution could
find; they are recorded in the proof record rather than omitted from it.

What that record establishes is bounded to `docker-desktop`, one Windows host,
CPU only, one replica of each tier, and one injected fault. It certifies no other
provider.

## What it answers, and what `helm rollback` does not

`helm rollback` returning zero says a revision was recorded. It does not say the
rendered configuration went back, that the workload followed, that the injected
fault is gone, or that a real model answers again — and a Deployment that never
rolled, a Service selecting a pod that loaded nothing, and a healthy release all
look identical from outside until something asks for a completion.

So the four things are asked separately:

| Question | How it is answered |
|---|---|
| Did the controlled change reach the workload? | The rendered `ConfigMap` carries the candidate value **and** the serving pod's name changed |
| Was the failed candidate detectable? | An init container that ran and exited non-zero, read off the workload the fault was injected into |
| Did the rollback restore real inference? | The release's own in-cluster test passed **and** one completion came back from the real adapter, with runtime-derived token counts and non-empty content |
| What did it cost? | Four revisions, a detection time, a rollback time, and a recovery time, all recorded |

## What runs, and what owns each piece

| Piece | What it owns |
|---|---|
| [`deploy/serving/experiments/helm-upgrade-rollback.v1.json`](../../deploy/serving/experiments/helm-upgrade-rollback.v1.json) | Every target, budget, assertion, evidence location, and limitation |
| [`scripts/environment/helm-upgrade-rollback.sh`](../../scripts/environment/helm-upgrade-rollback.sh) | Every `terraform`, `helm`, and `kubectl` invocation, the forward, the impact probe, and the teardown |
| [`tools/helm_upgrade_rollback`](../../tools/helm_upgrade_rollback) | Reading the descriptor, holding what was collected to it, the two calls to the restored release, and the record |

Nothing in the Python operates a cluster. The guard that establishes which
cluster is being acted on already lives in
[`lib.sh`](../../scripts/environment/lib.sh) beside every other environment
script, and a second implementation of it in another language would be a second
guard.

The descriptor is checked against
[the Kubernetes real-inference certification](../../deploy/serving/certification/k8s-real-inference.v1.json)
for **equality** on the cluster, the release, the request, and eight of its
twelve budgets. The two workflows install the same chart as the same release into
the same namespace on the same cluster; a second set of numbers describing that
would be a second release waiting to be discovered.

## The stages

```
baseline -> candidate -> unhealthy-candidate -> rollback -> cleanup
```

1. **`baseline`.** Terraform's prerequisites are applied, the release is
   installed *without* `--wait` so that readiness is measured rather than folded
   into an install, both rollouts are waited on against the chart's own progress
   deadlines, and `helm test` runs. This is revision 1, and everything after it
   is an upgrade from a known-good state — which is asserted, not assumed: a
   baseline whose release test did not pass stops the run.
2. **`candidate`.** One controlled change: `telemetry.serviceVersion` becomes the
   descriptor's candidate value. That path is fixed in the tool rather than left
   to the descriptor, because it is inside
   [`inferops-llm.derivedEnv`](../../charts/inferops-llm/templates/_helpers.tpl)
   and therefore inside the pod template's configuration checksum. A value
   outside that block would produce a revision Helm records and Kubernetes never
   acts on, and rolling *that* back would prove nothing. Two things are then
   checked: the value reached the rendered `ConfigMap`, and the serving pod is a
   different pod. This is revision 2, and it is the **last known-good revision**.
3. **`unhealthy-candidate`.** `model.artifact.sizeBytes` is set to a value the
   mounted artifact cannot match. The upgrade is issued **without** `--wait` and
   without a rollout wait — see below. This is revision 3.
4. **`rollback`.** `helm rollback` to revision 2, both rollouts waited on,
   `helm test` again, and one real completion through the forward. This is
   revision 4, and it is a *new* revision restoring an old one rather than a
   return to it: a run whose recorded revisions do not strictly increase is
   refused.
5. **`cleanup`.** The release is uninstalled. The namespace, the model cache
   claim, and the cluster are not touched.

## The injected fault, and why it is this one

`model.artifact.sizeBytes` is compared inside the pod, by the `verify-model` init
container, **before** the SHA-256 read — so a wrong byte count fails at the first
check rather than after reading 1.83 GB, and the reason is printed by the
container that made it.

Every property that keeps it safe is declared in the descriptor and checked:

- **it is accepted by the chart.** The values schema takes any integer and
  `_validate.tpl` refuses only a zero, so the fault reaches the cluster. A fault
  Helm rejected would stop the upgrade before anything was installed, and a run
  that never installed its own fault would report a detection it did not make;
- **it changes no image reference and pulls nothing.** Nothing outside the node
  is contacted;
- **it creates no object outside the release**, changes no cluster-scoped object,
  and changes no `PersistentVolumeClaim`. The claim stays mounted read-only and
  the candidate that would read it never starts;
- **it is removed by the rollback**, not by a second edit. A fault an operator has
  to undo by hand is a fault the rollback was never asked to reverse;
- **it reaches the serving runtime's pod template and nothing else.**
  `sizeBytes` is not in `inferops-llm.derivedEnv`, so the `ConfigMap` is
  unchanged and the platform API is not rolled at all.

That last point is what makes the impact measurement meaningful: the API keeps
serving through its existing pods while the runtime's new pod fails.

## Detection is evidence, never a clock

The failing upgrade is issued in the background and **not waited on**. Waiting
would make the detection a timeout, and a timeout cannot tell a broken container
from a slow model load — this project has measured loads from 133,515 ms to
358,735 ms.

Two signals are **decisive**, and one of them is required:

| Signal | What the cluster reported |
|---|---|
| `init-container-nonzero-exit` | `verify-model` ran and terminated with a non-zero exit code |
| `init-container-crash-loop` | the same container is in `CrashLoopBackOff` after a non-zero exit |

`progress-deadline-exceeded` is recorded as what it is — a **deadline** — and is
refused as a detection of health. The descriptor may not set a detection budget
shorter than a healthy runtime rollout, so no deadline can be reached sooner than
a healthy release is allowed to take.

Only pods that are **not** ready are inspected. The pod still serving has a
succeeded `verify-model` of the same name, and reading its terminated state would
report a zero exit code as a detection.

One signal is neither: `candidate-pod-unschedulable`. A candidate pod the host
could not place never ran the init container, so the run observed its own
capacity rather than the fault it injected. That is **inconclusive** — exit code
5 — with a named remedy, rather than a record.

## What a caller saw

While the candidate is failing, a probe asks the release's own
`/health/ready` through the forward every five seconds and records the status
each time. That is the answer a caller in front of the Service would get.

It is a **measurement, not an assumption**. A rolling update of a single-replica
Deployment surges rather than displacing, so the expectation is that every probe
is answered — but a refused probe is recorded and reported rather than failing
the experiment, because what a caller saw is the result and not the pass
condition. What it does not do is generate load: it bounds what one caller saw
and measures no throughput, no latency distribution, and no in-flight request.

## Prerequisites

- the local cluster is up (`scripts/environment/cluster-up.sh`) and is this
  project's;
- the Terraform prerequisite layer applies — the script applies it;
- the model cache claim already holds the pinned artifact;
- **an InferOps API image exists and is loaded into the cluster.** It does: it is
built by [`scripts/environment/api-image.sh`](../../scripts/environment/api-image.sh)
and made visible to the selected cluster by that provider's own image path.
  See the status note at the top.

The values file is required and nothing is assumed: the chart's shipped defaults
select no serving profile and are refused on purpose. The two files under
[`charts/inferops-llm/ci/`](../../charts/inferops-llm/ci/) are render fixtures and
are **not** installable — both carry a placeholder API image digest that resolves
to no image.

## Running it

```sh
# Reads committed files and contacts nothing.
scripts/environment/helm-upgrade-rollback.sh check

# Installs, upgrades, breaks, detects, rolls back, verifies, and uninstalls.
scripts/environment/helm-upgrade-rollback.sh run \
  --values path/to/your-values.yaml \
  --confirm-real-kubernetes
```

`--confirm-real-kubernetes` is required and has no default. `--port N` moves the
loopback forward when something already holds the default.

The Python half can be run on its own:

```sh
python -m tools.helm_upgrade_rollback check
```

`evaluate` and `record-cleanup` are invoked by the script rather than by hand:
the script owns the cluster, the forward, and the teardown, and `evaluate`
refuses a base URL that is not the loopback forward it opened.

## The evidence it produces

| Path | What it is |
|---|---|
| `.cache/inferops/experiments/helm-upgrade-rollback.json` | The record. Ignored by version control; copy what a proof record needs |
| `.cache/inferops/experiments/helm-upgrade-rollback-diagnostics.json` | Why a run stopped, and in which stage |
| `.artifacts/helm-upgrade-rollback/lifecycle-facts.json` | The four revisions, the detection, and the recovery clock, as collected |
| `.artifacts/helm-upgrade-rollback/impact-observations.json` | Every readiness probe across the failure window |
| `.artifacts/helm-upgrade-rollback/cleanup-facts.json` | What the uninstall removed and what it left |

The record is written **twice**. The first write happens while the release is
still installed, because the identity and the completion were read through a
forward to it; the second adds the cleanup outcome, which cannot exist before the
teardown. Nothing else is re-derived, and a record that already carries a cleanup
is refused rather than replaced.

**The record carries no prompt and no completion text.** It carries the character
count and the token counts, and `retainGeneratedText` is `false` in the
descriptor and refused if it is not.

## What this record will not support

These are the descriptor's own `limitations`, and a test asserts that every one
of them appears here:

- The evidence is local real Kubernetes on a single-node cluster belonging to one
  explicitly selected provider, and implies nothing about another provider, a
  production upgrade, a multi-node rollout, or a release under load.
- The unhealthy candidate is one injected fault - a byte count the mounted
  artifact cannot match - and detecting it says nothing about faults this
  experiment does not inject, including a runtime that starts and answers
  wrongly.
- The recovery time is measured from the moment the failure was detected to the
  moment a real completion was served again. It is not a time-to-detect for an
  operator who was not already watching, and it is not an outage duration.
- No request load is generated. The impact record is a readiness probe at a fixed
  interval through one forward, so it bounds what a single caller saw and
  measures no throughput, no latency distribution, and no in-flight request.
- The rollback restores a revision this experiment created minutes earlier on the
  same cluster. Nothing here says anything about rolling back across a chart
  version, a schema change, or a persisted-state migration.
- No GitOps controller, no progressive delivery, and no automated rollback
  trigger exists. Detection and rollback are both performed by the operating
  script, which a human started.

One more, which is a property of the recovery figure rather than of the
experiment: a rollback to a revision whose pod is still running reloads no model,
because the surging rollout never displaced it. Whether that happened is recorded
as `runtimeReloaded` rather than assumed, and it is the difference between a
recovery measured in seconds and one measured in minutes.

## Cleanup, and what it deliberately leaves

The run uninstalls its own release and asserts three things afterwards: no object
carrying `app.kubernetes.io/instance=inferops` remains, Helm reports no release,
and **the namespace and every claim are still there**. Both directions matter — an
uninstall that left release objects behind is incomplete, and one that removed a
prerequisite is a release that owned what it only referenced.

The namespace and the model cache claim are Terraform's
([the ownership boundary](../architecture/resource-ownership.md)). Reclaiming
them is `scripts/environment/terraform-prerequisites.sh destroy --confirm` and
nothing else. The cluster is `scripts/environment/cluster-down.sh`.

On failure the release is **left in place** and diagnostics are collected into
`.artifacts/helm-upgrade-rollback/`. A teardown that removes the evidence of its
own failure is worse than none. The script prints the one command that removes
the release, and says plainly that it removes neither the prerequisites nor the
claim.

## Troubleshooting

| Symptom | What it means |
|---|---|
| `REFUSED ... at stage load` | The descriptor disagrees with the certification, the chart, or the model source record. Nothing was installed |
| `INCONCLUSIVE ... candidate-pod-unschedulable` | The host could not place the surge pod beside the serving one. Free capacity or lower the runtime's requests, and run it again |
| `no failure was detected within ...` | Either the fault did not reach the cluster or the signal it produced cannot be read here. The release is left in place; start with `describe-pods.txt` and `events.txt` in `.artifacts/helm-upgrade-rollback/` |
| `FAILED ... at stage rollback` | Helm recorded a rollback and the cluster did not perform the one this experiment asked for. `history.txt` and the rendered `ConfigMap` are the two places to look |
| `the port-forward exited before it accepted a connection` | Something already holds the port. Pass `--port N` |

## What is not here

- **Any measured duration.** No install, upgrade, failure, or rollback has been
  timed, because none has run. Every budget in the descriptor is a bound derived
  from measurements taken outside Kubernetes.
- **A second fault.** One is injected, and the limitations say so.
- **Anything about load, GitOps, progressive delivery, or automated rollback.**
