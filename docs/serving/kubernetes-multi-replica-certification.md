# Certifying multi-replica inference through Kubernetes

Status: **published procedure, not yet executed.** The workflow described here is
committed and its descriptor validates. Nothing in this repository has installed
the chart into a cluster, and no multi-replica `C2` record exists. Every figure in
a future record comes from a run; none is quoted here.

This procedure answers one question the
[single-replica certification](kubernetes-real-inference-certification.md)
deliberately does not: **do real inference requests sent through the release's
Kubernetes Service actually reach more than one serving replica?** That document
certifies a one-replica release and refuses any other replica count rather than
reporting a stronger result than it measured. This one is the other half, and it
is a separate descriptor, a separate script, and a separate record because the two
answers are separate.

## Why a port-forward could not answer this

The single-replica certification sends its request through
`kubectl port-forward`, and states the bound: a forward is served by the API
server against **one selected endpoint**, so it never traverses the Service's
virtual IP. A forward cannot distribute anything. Ten requests through one forward
would land on one pod and prove nothing about a Service.

So the request set here is driven from **inside** the cluster: one short-lived Job
addresses the API Service by name, opens one connection per request, and
`kube-proxy` picks the endpoint each time. That is the path a real caller inside
the cluster takes, and it is the only path in this environment on which the
question means anything.

**The consequence is that distribution is observed, never arranged.** Nothing here
configures balancing, affinity, or routing, and this workflow does not certify
any. The requests are independent connections and the endpoint choice is the
cluster's. Ten requests across two ready endpoints land on one replica roughly two
times in a thousand, and when they do the run **fails**, saying that successful
requests reached one distinct replica and that this is an outcome rather than a
defect. It is not retried, downgraded, or reported as a pass with a footnote.

## What runs, and what owns each piece

| Piece | Owns | Where |
|---|---|---|
| [`scripts/environment/kubernetes-multi-replica-certification.sh`](../../scripts/environment/kubernetes-multi-replica-certification.sh) | Every cluster operation: capacity measurement, prerequisites, install, readiness waits, the request driver, log collection, diagnostics, teardown | Shell, beside the other environment scripts |
| [`tools/kubernetes_certification/multi_replica.py`](../../tools/kubernetes_certification/multi_replica.py) | The descriptor, the capacity gate, the assertions, the correlation, and the machine-readable record | Python, driven by the script |
| [`tools/kubernetes_certification/multi_replica_cli.py`](../../tools/kubernetes_certification/multi_replica_cli.py) | The four commands, and the exit code that separates "this host is too small" from "the platform did not certify" | Python |
| [`deploy/serving/certification/k8s-multi-replica-inference.v1.json`](../../deploy/serving/certification/k8s-multi-replica-inference.v1.json) | Every budget, replica count, capacity figure, request, and assertion the run applies | Committed data |
| [`tests/architecture/test_kubernetes_multi_replica_certification.py`](../../tests/architecture/test_kubernetes_multi_replica_certification.py) | That the descriptor agrees with the chart and the accepted records, that every refusal fires, and that the script is written the way the safety decisions require | Default check lane |

The split between the first two is the one the single-replica workflow already
makes, for the same reason: the guard that establishes **which cluster is being
acted on** lives in [`lib.sh`](../../scripts/environment/lib.sh), every script
here acts through it, and a second implementation of it in Python would be a
second guard. Python operates no cluster.

The descriptor is **cross-checked against the single-replica descriptor at load**.
Both install one chart into one namespace on one cluster, and two files
disagreeing about which release that is, or about how long a model may take to
load, would be two answers to one question — with the one a reader trusted being
whichever file they happened to open. The shared cluster, release, model-cache,
budget, and real-path values must be identical, and the two record file names must
differ, or the descriptor is refused.

## Which tier is multi-replica, and why only one

**The platform API runs two replicas. The serving runtime runs one.** That is a
scope, stated here rather than discovered in the record.

The correlation this certification rests on is the InferOps API's **own
structured log**: every `request.completed` record carries `inferops.request.id`
and `k8s.pod.name`, the catalog places the pod name on records and deliberately
keeps it off every metric, and the chart already supplies `INFEROPS_POD_NAME`
through the downward API. `llama-server` publishes no equivalent — it has no
InferOps request identifier and no pod-aware record — so a run could not prove
which runtime replica answered anything without inventing a mechanism for it.

The two ways to invent one were both refused. Exposing pod identity in a response
header or body member would make a replica's name part of the API's contract in
order to test it. Inferring the runtime tier's distribution from the API's would
be inferring distribution from a desired replica count, which is exactly what a
multi-replica claim may not do.

So the certified statement is bounded: **successful real requests through the
Kubernetes Service reached at least two distinct ready platform API replicas, each
of which served a real completion from the loaded model.** Every API replica's
readiness is model readiness — `/health/ready` is false whenever either the API or
its adapter is unable — so a ready replica is one that could reach the runtime and
the model was loaded. Runtime-tier distribution is not claimed, and the record's
`limitations` say so.

## The stages

A run passes through these in order, and a diagnostics record names the one it
stopped in.

| Stage | What it establishes | What a failure there means |
|---|---|---|
| `load` | The descriptor is internally consistent, agrees with the single-replica descriptor on everything they share, requests at least two API replicas, and can hold its own request set inside its own budget | An edit to one record and not the others. Nothing was contacted |
| `capacity` | The container engine meets the accepted minimum tier, and what is left of the cluster's allocatable processor and memory can hold this profile's requests and its peak | The host, and **nothing has been installed**. Exit code 5 rather than 4 |
| `prerequisites` | The run is authorized, the tools are present, and the cluster is this project's and is running the pinned node image | The host or the authorization |
| `release` | The Terraform prerequisites applied and Helm installed one release of the real profile with the descriptor's replica counts, digest-pinned images, and the model cache mounted read-only and verified against its pinned hash | The chart, the values file, or the prerequisite layer |
| `readiness` | Both Deployments reported every replica ready inside their budgets, **each individual pod** reported ready inside its own, and the release's in-cluster test passed | Most often the model load, or a host that fit the requests and not the reality |
| `distribution` | Exactly the planned request set was sent, every request answered 200, and every answer carried the real adapter kind and consistent runtime-derived token counts | The platform, and the release is left standing |
| `correlation` | Every successful request is recorded exactly once, by a pod that was one of the ready API replicas, as a real completion — and those pods number at least the declared minimum | Either the platform or the Service's own endpoint choice, and the message says which |
| `cleanup` | The driver was removed, the release uninstalled, no labelled object survived, the namespace survived, and the claim count is unchanged | The teardown, after the record was already written |
| `evidence` | The record was written to the ignored evidence directory | The workspace, not the cluster |

## The capacity gate, and why it is a gate

Two API replicas and one runtime replica are roughly 1,210 millicores and 2.25 GiB
of **requests**, peaking at about 4.06 GiB of **memory limits**. A host that
cannot hold that does not fail loudly: a pod whose requests do not fit stays
`Pending` until a rollout deadline expires, and the run then reports a readiness
failure for what is actually a laptop.

So the figures are declared in the descriptor, the architecture suite computes
them from the chart's own resource blocks times the replica counts and fails if
the two drift, and the preflight measures the host **before the namespace has
anything in it**:

| Check | Compared against |
|---|---|
| Container engine memory and processors | The ADR 0001 D7 minimum tier, as `lib.sh` already states it |
| Uncommitted cluster processor | This profile's requests plus headroom |
| Uncommitted cluster memory | This profile's **peak**, plus headroom, because the container loading a 1.83 GB model is the one that would use its whole limit |

"Uncommitted" is allocatable minus what is already requested by every pod that has
not finished, with each pod counted the way the scheduler counts it — the larger
of its containers together and its largest init container alone. Every shortfall
is reported at once with a remedy, rather than one per attempt: each attempt would
otherwise cost another model load on a host that was just told it is short of
memory.

**The replica count is never reduced to fit.** A certification of fewer replicas
than the profile requests is not this certification, and both the validator and
the script refuse it — the script again at the point the count is handed to Helm,
because that is the one value whose downgrade would turn this into the
single-replica workflow wearing a multi-replica record.

## The request driver

One `batch/v1` Job, created by the script and deleted by it, running the same
BusyBox image the chart's own release test pins — one pin, not several.

It carries this release's `app.kubernetes.io/name` and
`app.kubernetes.io/instance` labels and the `release-test` component label, and
that is not decoration. The release's default-deny NetworkPolicy selects every pod
carrying the name and instance pair; the API's ingress rule admits pods carrying
the same pair; and the chart already renders exactly one egress allowance
describing an in-cluster client of both Services, selected by the `release-test`
component. A driver labelled anything else would be denied its egress on a
policy-enforcing plugin, or fall outside the API's ingress rule entirely. On the
accepted local cluster the question does not arise — `kindnetd` enforces no policy
at all, which [an executed
experiment](../proof/security/v1-s3-004-pr1-network-policy-enforcement.md)
established — so this is about being correct where it would matter, not about
being permitted here.

The Job is bounded: `backoffLimit: 0`, `restartPolicy: Never`, an
`activeDeadlineSeconds` taken from the descriptor's distribution budget, no
service account token, a read-only root filesystem, no privilege escalation, all
capabilities dropped, and a 16 MiB memory-backed scratch directory.

**It never prints a response body.** Each answer is written to that scratch
directory, matched for the markers a real answer carries, and left there; what the
Job prints is one line per request carrying the identifier, the status, the
adapter kind, the model identifier, and the three token counts. The generated text
is not this workflow's to retain, and a log line carrying it would put a
completion into `kubectl logs`, into `.artifacts/`, and into anything that reads
either.

## The correlation, and what it refuses

After the request set completes, the script reads each API pod's log **one pod at
a time** — a single selector-wide `kubectl logs` interleaves the pods and loses
which one wrote which line — and keeps only the structured records naming a
request this run sent, and only the fields the correlation reads.

The join then has to survive all of this, and each is a refusal rather than a
warning:

- a request no replica recorded — the requests succeeded and **nothing correlates
  them to a serving replica**;
- a request two replicas both claim;
- a record from a pod that was not one of the ready API replicas;
- a record that is not a completion, or that carries a non-success outcome or a
  status other than 200;
- a record carrying an adapter kind that is not the real one, a model revision
  that is not the pinned one, a model the release was not configured with, or a
  mock marker anywhere in its identity;
- every record naming a single pod, which is a one-replica result and is reported
  as one.

## Prerequisites

Before an authorized run, everything the
[single-replica procedure](kubernetes-real-inference-certification.md#prerequisites)
requires, and one thing more: enough host and cluster capacity for two API
replicas, which the preflight measures rather than assumes.

The same blocker applies and is stated here rather than discovered at the first
image pull. **No InferOps API image is published.**
`platform-api-container-image` is `planned` in
[the ownership inventory](../architecture/resource-ownership.md), no Dockerfile is
committed, and until an image exists and is loaded into the cluster an authorized
run stops at the `release` stage with a pull failure and a diagnostics record
saying so. That is the workflow behaving correctly; it is not a workflow that has
been run.

## Running it

Validation, which contacts nothing and installs nothing:

```bash
bash scripts/environment/kubernetes-multi-replica-certification.sh check
```

The authorized run:

```bash
bash scripts/environment/kubernetes-multi-replica-certification.sh certify \
  --values path/to/real-values.yaml \
  --confirm-real-kubernetes
```

The values file supplies the images, the model, and the ownership; the **replica
counts come from the descriptor** and are passed with `--set`, so a values file
that happens to say `replicaCount: 1` cannot decide this profile.

Without `--confirm-real-kubernetes` the script refuses before it touches anything.

The single-replica certification is unchanged and independently runnable:

```bash
bash scripts/environment/kubernetes-certification.sh certify \
  --values path/to/real-values.yaml \
  --confirm-real-kubernetes
```

Run one at a time. Both install a release named `inferops` into
`inferops-release`, and each refuses to certify over an existing release.

## The evidence it produces

| File | What it is |
|---|---|
| `.cache/inferops/certification/k8s-multi-replica-inference.json` | The record of a certified run. Ignored by version control until it is promoted |
| `.cache/inferops/certification/k8s-multi-replica-inference-diagnostics.json` | Why a run did not certify, naming the stage |
| `.artifacts/kubernetes-multi-replica-certification/capacity-facts.json` | What the host and cluster had before anything was created. **Host state, not evidence** |
| `.artifacts/kubernetes-multi-replica-certification/cluster-facts.json` | What the script measured, per workload and per pod. Host state |
| `.artifacts/kubernetes-multi-replica-certification/observations.json` | The request results and the replicas' own records. Host state |
| `.artifacts/kubernetes-multi-replica-certification/driver.log` | What the request driver printed: identifiers, statuses, and counts. No response body |
| `.artifacts/kubernetes-multi-replica-certification/replica-records.log` | The API pods' structured records, as collected |

Every location is the descriptor's and none is an argument the tool accepts: the
whole cluster half of the record is copied out of these files, so a path flag
would let a run reach a real Service and describe an environment read from
somewhere else.

The record names the requested and ready replica counts for both tiers, every
pod's readiness and how long it took, the request set and how it was distributed
across replicas, the time window it ran in, the measured resource profile, the
cluster and tool versions, the release revision and chart version, the
digest-pinned images, the model cache mounting and whether its hash was compared
in the cluster, the cleanup outcome, and the limitations. It carries **no prompt
and no completion**.

The record is written **twice**, and that is deliberate: the assertions run before
the teardown, so a failed one leaves the release standing to be looked at; the
cleanup outcome cannot exist until after the teardown. The second write adds it.

Promoting a record into `docs/proof/` is what makes a `C2` claim. The rules are in
[the certification levels](../testing/certification.md) and
[the test strategy](../testing/test-strategy.md), and nothing here raises a
ceiling.

## What this record will not support

These are the descriptor's own `limitations`, copied into every record so that a
reader of the record does not have to find this page:

- it is **local real Kubernetes** on a single-node `kind` cluster, and implies
  nothing about production **high availability**;
- only the platform API tier is multi-replica; the serving runtime runs one
  replica, for the correlation reason above;
- distribution is whatever `kube-proxy` chose during the run — observed, never
  configured, and no routing, balancing, or affinity behaviour is certified;
- no autoscaling, load generation, performance comparison, or failure experiment
  is performed, and none may be read into the record;
- one node hosts every replica, so nothing here says anything about scheduling
  across nodes, zone spreading, or node-failure tolerance.

## Cleanup, and what it deliberately leaves

On success the script deletes the request driver, uninstalls the release, and then
asks the cluster the same four questions the single-replica workflow asks — no
labelled object survived, Helm reports no such release, the namespace survived,
and the claim count is unchanged — with `jobs` added to the residue selector,
because this workflow is the one that creates one. The **namespace** and the
**model cache claim** are Terraform's and the **cluster** is the contributor's
host; reclaiming the first two is
`scripts/environment/terraform-prerequisites.sh destroy --confirm` and removing
the cluster is [`cluster-down.sh`](../../scripts/environment/cluster-down.sh),
and nothing here does either.

On failure it removes the driver and nothing else. The release stays installed,
the diagnostics are collected, and the message says how to remove it.

## Troubleshooting

| Symptom | Where to look |
|---|---|
| The run refuses at `capacity` | The report names every shortfall and a remedy. Nothing was installed; raise the container VM's allocation or remove other workloads |
| The install fails pulling an image | The API image blocker above. `.artifacts/kubernetes-multi-replica-certification/events.txt` names the pull |
| One API replica stays `Pending` | The capacity gate passed and the cluster disagreed. `describe-pods.txt` names the unschedulable resource |
| The request driver never completes | `driver.log` and `describe-pods.txt`. A driver that cannot resolve the Service and a Service that selects nothing look the same from outside |
| The run stops at `correlation` saying nothing correlates a request | The API pods wrote no record naming it. Check that `INFEROPS_POD_NAME` reaches the container — it is the chart's downward-API variable — and that `replica-records.log` is not empty |
| The run stops at `correlation` naming one distinct replica | Every request landed on one endpoint. The message says this is an outcome rather than a defect; a rerun is a fresh draw, and a repeat is worth investigating as endpoint or readiness behaviour |
| The run stops at `readiness` naming one pod | Per-pod readiness, which a Deployment's summary count would have hidden. `describe-pods.txt` for that pod |

Cluster-level symptoms are in
[the local cluster guide](../environment/local-cluster.md) and
[local runtime troubleshooting](local-runtime-troubleshooting.md).
