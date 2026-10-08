# The model cache under two serving runtime replicas: what is observed, and how

Status: **the tool, the rules, and the static tests exist. No run is recorded on this page yet.**

The desired-state release declares two serving runtime replicas. A Deployment has
one pod template, so both replicas are declared to mount one claim, to verify one
pinned artifact, and to load it. This page describes how that is observed on a
cluster, which rules decide the result, and what a record does not establish.

The storage design is not changed. [Model cache storage](model-cache-storage.md)
states it: Terraform owns the claim, the release's acquisition hook is the one
writer, and each serving replica is a reader. This page adds no owner, no claim,
no access mode, and no chart value.

## What the render already states

These are properties of committed files. `tests/architecture/test_helm_chart.py`
holds each of them against a `helm template` of the desired-state release.

- The runtime Deployment declares 2 replicas and one pod template.
- The template's one runtime container declares the pinned runtime image, and is
  given one `--model` argument: the artifact's path under the cache mount.
- The template holds one PersistentVolumeClaim volume, the claim that the
  EnvironmentBinding names, with `readOnly: true`. It holds no host path.
- The runtime container and the `verify-model` init container each mount that
  volume with `readOnly: true`, at the repository-and-revision subdirectory.
- The script of `verify-model` holds the pinned byte count and the pinned
  SHA-256, and reads the path that the runtime is given.
- Neither container is given an environment variable. So no variable names
  another model.
- The release renders no PersistentVolumeClaim. Its one writable mount of the
  claim is the acquisition hook's.

A render does not show what a pod mounts or loads. The observation below does.

## The claim's access mode

The prerequisite layer creates the claim as `ReadWriteOnce`
(`infra/terraform/modules/platform-prerequisites/main.tf`). Kubernetes documents
that such a claim can be mounted by several pods that run on one node, and not by
pods on two nodes. The release states no node selector, affinity, or topology
spread for the runtime. So on a cluster with more than one schedulable node, the
second runtime pod may be placed where it cannot mount the claim. No such cluster
was used. **Two runtime pods on one node are pod redundancy. They do not
establish node-loss resilience.**

## The observation

An observation has three parts.

1. **A driver prepares one cluster and applies the release.** It uses the
   repository's own procedures:
   [the prerequisite layer](platform-prerequisites.md),
   [the bootstrap](argocd-bootstrap.md), and
   [the Application](argocd-application.md). It fills the claim from a local seed
   image first, so that the run downloads no model.
2. **The driver reads the cluster and writes one directory, the collection.**
3. **`tools/runtime_model_cache` reads the collection and prints one record.** It
   reads files and contacts no cluster.

A driver is a file of one run. It is committed beside that run as text, and it is
not a procedure of this repository.

### The capacity preflight

No capacity gate exists for the V2 topology. The driver runs the V1 multi-replica
preflight before it applies the Application, with the V1 measuring program and
the V1 figures
([the V1 procedure](../serving/kubernetes-multi-replica-certification.md#the-capacity-gate-and-why-it-is-a-gate)).
A test holds that those figures are the sums of this release's three Deployments
plus one pod with the resources of the V1 request driver. The observation does
not run that driver. So the preflight asks for slightly more than this release's
Deployments request.

**If the preflight does not exit 0, the driver does not apply the Application.**
It changes no replica count, request, or limit to fit. The record of that run has
the result `REFUSED`.

The preflight is one reading of one host. It is not a capacity gate for this
topology: it does not read rollout headroom, and it does not count the
acquisition hook's pod.

### The collection

| File | What the driver wrote into it |
|---|---|
| `run.json` | The header: the run name, the provider, the namespace, the executing commit, the commit the controller reported, and two times. Schema `inferops.io/runtime-model-cache-collection/v1alpha1` |
| `expected.json` | What `python -m tools.runtime_model_cache --expected` printed before any pod was read. Schema `inferops.io/runtime-model-cache-expected/v1alpha1` |
| `capacity-facts.json`, `capacity-preflight.json` | What the V1 measuring program wrote, and the exit status of the V1 preflight |
| `readiness-samples.txt` | One line for each runtime pod at each sample, from before the apply until both rollouts returned |
| `runtime-pods.json` | The serving runtime pods, as the cluster reported them after the rollouts |
| `claims.json`, `volumes.json` | The claims of the namespace, and the cluster's PersistentVolumes |
| `events.txt` | The pod events of the namespace, one line each |
| `verify-model.<pod>.txt` | The log of the pod's `verify-model` init container |
| `mountinfo.<pod>.txt` | The mount table of the pod's runtime container |
| `artifact.<pod>.txt` | The device, the inode, and the byte count of the artifact, as the runtime container sees it |
| `models.<pod>.json` | The status, the identifier, and the metadata of the runtime's model listing |
| `completion.<pod>.json` | The status, the model name, the finish reason, and the two token counts of one completion |

The listing and the completion are sent to one pod through a port-forward to that
pod. They do not pass a Service. The driver keeps no response body: it writes the
members above and nothing else.

The expected identity comes from committed files, and not from the cluster: the
desired-state release's generated values, the chart's default mount path, and the
chart's rule for the directory inside the claim. The command exits 1 when the
release and a pin record disagree. The pin records are
[the model source record](../serving/model-source.v1.json) and
[the runtime package record](../../deploy/serving/runtime/container-package.v1.json).

### The record

The record has the schema `inferops.io/runtime-model-cache-observation/v1alpha1`.
It holds the header, the SHA-256 of each file of the collection, the expected
identity, an allowlisted reduction of each read, the state of each rule, the
result, and the statements below of what it does not establish. A digest is the
SHA-256 of the file's bytes with every CRLF replaced by LF.

**A read that was not made is not a value.** An absent file and a JSON file that
does not parse give `not-read`. A rule that needs such a read is `not-observed`.

| Rule state | Meaning |
|---|---|
| `held` | The reads show the statement |
| `not-held` | One read contradicts the statement |
| `not-observed` | A read that the rule needs was not made. With fewer than two pods, each rule that compares replicas is `not-observed`: one pod agrees with itself |

| Result | When |
|---|---|
| `REFUSED` | The capacity preflight did not exit 0, and no runtime pod was read |
| `FAILED` | One rule is `not-held` |
| `INCONCLUSIVE` | No rule is `not-held`, and one required rule is `not-observed` |
| `PASSED` | Every required rule is `held` |

The evidence level of a record is C2 when the pods ran the pinned runtime and the
pinned model. The level, the result, and the status of any claim are three
separate things. A record registers no claim.

### The rules

17 rules. 16 are required. The last is not: the samples
are taken every five seconds, and a pod whose load was not sampled leaves that
rule `not-observed` without changing the result.

| Rule | Statement |
|---|---|
| `capacity-preflight-sufficient` | The V1 multi-replica capacity preflight exited 0 before the release was applied. |
| `replica-count` | The number of serving runtime pods that are not being deleted is the declared runtime replica count. |
| `every-replica-ready` | Each serving runtime pod reports the Ready condition as True. |
| `one-runtime-image` | Each runtime container declares the pinned image reference, and each reported image identifier holds the pinned digest. |
| `one-model-argument` | Each runtime container is given the expected artifact path as its model argument, and every replica is given the same alias. |
| `one-claim` | Each pod mounts the declared claim as its one persistent volume, and no pod mounts a host path. |
| `claim-is-the-prerequisite-claim` | The declared claim is Bound, carries the labels of the prerequisite layer, and carries no label or annotation of a Helm release. |
| `no-second-claim` | The namespace holds one PersistentVolumeClaim. |
| `read-only-declared` | Each pod declares the claim read only on the volume, on the runtime container's mount, and on the verification container's mount. |
| `read-only-in-effect` | The mount table of each runtime container lists the cache mount with the option ro. |
| `revision-scoped-mount` | Each of the two mounts of each pod names the expected repository-and-revision subdirectory. |
| `one-directory` | The mount table of every runtime container names one device and one root directory for the cache mount. |
| `one-file` | Every runtime container sees the artifact as one device, one inode, and the pinned byte count. |
| `artifact-verified-on-each-start` | In each pod the verification container's script holds the pinned SHA-256 and byte count, the container exited 0, and its log holds the verification line and the checksum line for the expected path. |
| `one-reported-model` | Each runtime answered its model listing with status 200 and the alias it was given, and every replica reported the same model metadata. |
| `every-replica-completed` | Each runtime answered one completion with status 200 and at least one completion token. |
| `not-ready-while-loading` (not required) | For each pod, one sample before its first Ready sample shows the runtime container running and not ready. |

### What a record does not establish

- A record does not establish node-loss resilience. Kubernetes documents that pods which share a ReadWriteOnce claim run on one node. The record states the node of each pod.
- A record does not establish that a caller is served when one runtime pod is unavailable. No pod was removed, and no request was sent through the API Service by this collection.
- A record does not establish a rollout. No pod template changed during the collection.
- A record does not establish that readiness is false whenever inference is impossible. It states the samples in which a running runtime container was not ready, and the completion each runtime answered after it was Ready.
- A record does not establish which runtime replica serves a request that a caller sends. Each completion was sent to one pod through a port-forward, and not through a Service.
- A record does not establish behaviour on another provider, another storage class, another node count, or another day. It is one collection on one cluster.
- A record does not establish that the claim cannot be written. It states the declared mode and the mount option of each runtime container. No write was attempted, and the acquisition hook mounts the same claim writable.
- A record does not establish capacity for any other topology, and it is not a capacity gate for this one. It states one reading of the V1 preflight.
- A record does not establish a performance figure. No time in it is a latency, a throughput, or a model-load measurement.

Three more limits are of the collection, and not of one record.

- **The acquisition hook is not observed beside running runtime pods.** It runs
  before the Deployments exist on the first sync. Whether it can mount the claim
  writable while two runtime pods hold it read only, as an upgrade needs, was not
  observed.
- **The mount table shows the mount option. It does not show that every write
  is refused.** No write was attempted from a runtime container.
- **`kubectl exec` and a port-forward are not read requests.** They change no
  object that the release declares. They do run a process in the runtime
  container, and they do make each runtime decode one short completion.

## Commands

```bash
# What the committed files declare for each runtime replica.
uv run --locked python -m tools.runtime_model_cache --expected

# The record of one collection directory.
uv run --locked python -m tools.runtime_model_cache DIRECTORY

# Build the record of each committed run again, and compare.
uv run --locked python -m tools.runtime_model_cache --check
```

Exit status 0 of the second command says that a record was printed. It does not
say that a rule is held.

A committed run is a directory that matches
`docs/proof/environment/*-runtime-model-cache-run-*`. `--check` and
`tests/domain/test_runtime_model_cache.py` build its record again from its
committed collection.

## The runs

No run is committed yet. A run is added by the change that executes it.
