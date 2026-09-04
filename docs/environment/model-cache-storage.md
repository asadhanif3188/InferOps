# Model cache storage: ownership, revision scoping, integrity, restart, cleanup

Status: **the release half is implemented and rendered; the prerequisite half is
not written, and nothing in this document has run inside Kubernetes.** The chart
mounts a claim, scopes the mount to a revision, and verifies the artifact before
the runtime starts. No cluster has installed it: no InferOps API image is
published, and `model-cache-volume-claim` is `planned` in
[the ownership inventory](../architecture/resource-ownership.md) because
Terraform does not exist yet.

What *has* been measured is the property underneath all of it — that a stopped
runtime leaves its artifact behind and the next start reads it without a network
connection. That was measured at the container level, on one host, on
2026-09-04: the same bytes before, between, and after two starts; readiness false
on the restarted runtime's first sample; and a cache hit, which is the only state
that needs no network. The figures, the six attempts it took, and what none of it
supports are in
[the restart record](../proof/serving/v1-s3-003-pr1-restart-reload.md).

## Who owns what

One resource, one owner. The three roles here are deliberately three:

| | Owner | Creates with | Destroys with |
|---|---|---|---|
| The claim | `terraform` | `terraform apply` | `terraform destroy` |
| The bytes inside it | `helm`, through `model-acquisition-job` | `helm install` or `helm upgrade` | Not removed by a release; they outlive it |
| The mount | `helm`, in the serving Deployment | `helm install` | `helm uninstall` |

**Writing content is not owning the container.** The acquisition job writes into a
claim it does not own; that is the single sanctioned handoff in the design, and
it is named in the claim's own inventory row rather than left implicit.

**The serving replicas are readers and never writers.** The claim is mounted
`readOnly` on the volume and on the mount, and the chart refuses
`model.cache.readOnly: false` at render time. A serving replica able to write the
cache would be a second writer nobody decided on.

`model-acquisition-job` is **still deferred**, and the chart's `Chart.yaml`
declares it so. It needs an image nobody has published and a 1.71 GiB transfer
over a link this repository has not exercised from inside a cluster; it arrives
with the Kubernetes serving integration rather than here. Until then the claim is
filled out of band, and a pod that finds it empty is refused by the check below
rather than served from.

## The layout inside the claim, and why the revision is in the path

The claim holds the same layout the workspace cache already uses, which
[the model source record](../serving/model-source.v1.json) publishes:

```text
<claim>/<repository, with the separator written as two hyphens>/<revision>/<file>
```

For the selected model:

```text
Qwen--Qwen3-1.7B-GGUF/90862c4b9d2787eaed51d12237eafdfe7c5f6077/Qwen3-1.7B-Q8_0.gguf
```

The chart mounts the claim **at the repository-and-revision subdirectory**, not
at its root, and derives that subdirectory from `model.artifact.repository` and
`model.revision`. There is no values path that reaches it.

That is the whole of the acceptance criterion *cache reuse does not bypass model
revision verification*, and it is a mount rather than a check:

- a release declaring revision **B** cannot see revision **A**'s directory at
  all, so it cannot load A's bytes however the rest of it is configured;
- the file the runtime is given as `--model` and the file the integrity check
  reads are **one derived expression**, so a verified file and a served file
  cannot be two different files;
- `model.artifact.fileName` is one path segment by schema, so a name carrying a
  separator cannot climb back out of the revision directory.

Before this, `model.revision` was required, compared against nothing, and had no
bearing on which bytes a container read. It was a label beside the artifact. It
now selects it.

## What is verified, and when

An init container runs before `llama-server` on **every pod start**, and
therefore on every restart. It is BusyBox — for its `sha256sum` and its `wc`,
both confirmed present in the pinned image — carries the same security context
and the same read-only mount as the runtime, and is given no environment at all:
everything it compares against is rendered into its script from a pinned value.

`model.integrity.verifyOnStart` decides how much it reads:

| Mode | Reads | Catches | Cost per pod start |
|---|---|---|---|
| `sha256` (default) | the artifact end to end | absence, truncation, and any content that is not the pinned bytes | one full read — about 1.71 GiB for the selected model |
| `size` | the file's byte count | absence and truncation, and nothing about content | a `stat` |
| `none` | nothing | absence only | nothing |

Two things are true under all three, and they are why the weaker settings are
offered at all rather than being holes:

- **the revision scoping still holds**, because it is the mount;
- **an absent artifact is still refused**, because the file-exists check is not
  part of the mode.

The default is the strong setting. It is a minority of a start rather than a new
order of cost: this project has measured model loads between 129,328 ms and
358,735 ms, and full digest reads of the same artifact at 3,500 ms and 4,781 ms
on the reference host.

The mock profile must state `none` explicitly. It mounts no artifact, so
inheriting `sha256` would name a check with nothing to read — and a render that
described a verification which could not have happened is the same defect as a
mock transcript naming a real model.

## Restart, and what survives what

The five teardown operations, narrowest first, and what each does to the cache.
The inventory records this per resource; the table is the readable form of it.

```text
   pod restart             -> the pod goes and comes back. The claim, the
                              bytes, and the mount are untouched. The
                              replacement pod re-runs the integrity check
                              before it serves.

   helm uninstall          -> the mount goes with the Deployment. The claim
                              and the bytes survive, by design: uninstalling
                              must not force a 1.71 GiB re-download over an
                              unauthenticated transport.

   scoped object teardown  -> release-labelled objects go. Prerequisites are
                              excluded by their lifecycle label, so the claim
                              survives this too.

   terraform destroy       -> the claim goes, and the bytes with it. This is
                              the only routine operation that reclaims the
                              space.

   cluster teardown        -> everything goes.
```

The cost of that lifetime is the point of writing it down: **the claim holds
roughly 1.71 GiB from the first successful acquisition until `terraform destroy`
runs.** That is a deliberate trade — bytes for not re-downloading them — and it
is documented here rather than discovered on a full disk.

Three restart properties are claimed by
[the lifecycle record](../../deploy/serving/lifecycle/model-lifecycle.v1.json)
and each is measured rather than asserted:

- **the artifact survives** — the cache is classified between the two starts and
  its digest re-read after them, and the byte count is compared at all three
  points;
- **readiness resets** — the first probe sample of the restarted runtime is read,
  so a process that came back already ready would be visible rather than assumed
  away;
- **the restart needs no network** — it proceeds from a cache hit, which is the
  only state the record lets a start proceed from without one.

```text
uv run --locked python -m tools.model_lifecycle restart --confirm-real-runtime
```

It operates a real container and reads real model bytes, so it requires the
confirmation. It never downloads, and it never simulates a miss: a real miss is a
1.71 GiB transfer that no tool in this repository performs implicitly.

## Cleanup, and what each tool may not reach

Cleanup is scoped by refusal rather than by convention. Each of the operations
below is bounded to one target and refuses everything else, including a symbolic
link pointed elsewhere.

| Command | Reaches | Cannot reach |
|---|---|---|
| `python -m tools.model_lifecycle clean --confirm` | `.cache/inferops/lifecycle`, which now holds both comparisons' results | the model cache, refused first and by name so that the guard is reachable and testable |
| `python -m tools.model_acquisition clean --confirm` | `.cache/inferops/models` | anything outside it, any path resolving outside the checkout, any symbolic link in or above the tree |
| `scripts/environment/helm-lifecycle.sh` | one release in one namespace | the claim, which is not a release object; and it never passes `--create-namespace` |

Nothing in this repository deletes the cluster-side claim. That is
`terraform destroy`, it is the operation that reclaims the 1.71 GiB, and it is
owned by a layer that has not been written.

## What this does not establish

- **Nothing here has run in Kubernetes.** The init container has never been
  scheduled, the claim has never been bound, and a rendered manifest is a file.
  The measured restart is a container-level restart on one host — the same
  property one layer down, not the same experiment.
- **BusyBox reading a 1.71 GiB file under a read-only root filesystem as uid
  65534 is untested.** The applets it needs were confirmed present in the pinned
  image; running them under the pod's security context needs a pod.
- **`size` and `none` are weaker than they look.** `size` catches a truncated
  file and nothing else; a same-length substitution passes it.
- **No figure here is a performance claim.** The load times quoted are from one
  contributor host on CPU, and this project's own runs of the same experiment
  have spread more than 82 seconds between them.
