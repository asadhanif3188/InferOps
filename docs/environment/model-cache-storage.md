# Model cache storage: ownership, revision scoping, integrity, restart, cleanup

Status: **both halves have now run inside Kubernetes, on the `docker-desktop`
provider.** The chart mounts a claim, scopes the mount to a revision, and verifies
the artifact before the runtime starts; the claim itself is declared by
[the Terraform prerequisite layer](platform-prerequisites.md). `V1-S3-011` applied
that layer, installed the chart against it, filled the claim through the release's
acquisition hook, loaded the model from it, **deleted the serving pod and watched
the replacement read the same file**, and removed both layers afterwards.
`model-cache-volume-claim` is `implemented` in
[the ownership inventory](../architecture/resource-ownership.md) and cites the run
that moved it.

That is one provider, on one Windows host. `kind` has executed none of it since
the ownership realignment.

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
| The claim | `terraform` | `terraform apply`, on [the prerequisite layer](platform-prerequisites.md) | `terraform destroy` |
| The bytes inside it | `helm`, through `model-acquisition-job` | `helm install` or `helm upgrade` | Not removed by a release; they outlive it |
| The mount | `helm`, in the serving Deployment | `helm install` | `helm uninstall` |

**Writing content is not owning the container.** The acquisition job writes into a
claim it does not own; that is the single sanctioned handoff in the design, and
it is named in the claim's own inventory row rather than left implicit.

**The serving replicas are readers and never writers.** The claim is mounted
`readOnly` on the volume and on the mount, and the chart refuses
`model.cache.readOnly: false` at render time. A serving replica able to write the
cache would be a second writer nobody decided on.

`model-acquisition-job` is now rendered, and the chart's `Chart.yaml` declares
it owned rather than deferred. It is a `pre-install,pre-upgrade` hook, so it
completes before the runtime Deployment exists to read what it wrote. Since `V1-S3-011` it **is** evidence that the claim gets filled in a cluster:
the row is `implemented`, a release has installed the hook on the
`docker-desktop` provider, and the hook filled the claim there. A pod that finds
the claim empty is still refused by the check below rather than served from.

It takes its bytes from one of two places, and the choice is stated in values
rather than inferred:

- `download` resumes an HTTPS transfer of the pinned artifact. This is what a
  fresh checkout runs, because the URL, the byte count and the hash are all
  public and all come from [the model source record](../serving/model-source.v1.json).
  The transport is not certificate-validated, so the content hash is the whole of
  the defence, and it is compared before the bytes are used and again before the
  rename.
- `seed-image` reads the artifact out of an image built on the contributor's host
  and loaded into the node by
  [`model-seed-image.sh`](../../scripts/environment/model-seed-image.sh). A host
  that already holds the verified artifact has no reason to fetch 1.71 GiB again.
  It changes where the job reads, not who writes: the job is still the only thing
  that writes the claim, which is what keeps the single sanctioned handoff
  single.

Either way the job is a no-op against a claim that already holds a verified
artifact, and either way an artifact that does not verify is discarded rather
than reused. A file of the right length and the wrong content is corruption that
survived, not a cache hit.

**One assumption the job rests on, stated because it is not universal.** It runs
as uid 65534 with `fsGroup: 65534`, and it has to create the revision directory
inside a claim Terraform has just provisioned empty. That works when the volume
plugin either honours `fsGroup` on first write or provisions the directory
writably. The accepted cluster's plugin -- `rancher.io/local-path`, which `kind`
ships and which this claim takes by naming no storage class -- creates the host
directory world-writable, so it does. A driver that provisioned `root:root 0750`
and did not apply `fsGroup` would leave the job unable to write, and the symptom
would be a permission error from `mkdir` rather than anything about the model.
Nothing in this repository has observed that case, because nothing has run this
against another storage class.

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
  its digest re-read in full after them, the byte count is compared at the three
  points it is taken at, and the start procedure hash-verifies the artifact
  before each start as well;
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

One thing it does **not** establish, because the start procedure hash-verifies
the artifact before every start: that either of its starts was cache-cold. The
[restart record](../proof/serving/v1-s3-003-pr1-restart-reload.md) states what
that costs the figures.

## Cleanup, and what each tool may not reach

Cleanup is scoped by refusal rather than by convention. Each of the operations
below is bounded to one target and refuses everything else, including a symbolic
link pointed elsewhere.

| Command | Reaches | Cannot reach |
|---|---|---|
| `python -m tools.model_lifecycle clean --confirm` | `.cache/inferops/lifecycle`, which now holds both comparisons' results | the model cache, refused first and by name so that the guard is reachable and testable |
| `python -m tools.model_acquisition clean --confirm` | `.cache/inferops/models` | anything outside it, any path resolving outside the checkout, any symbolic link in or above the tree |
| `scripts/environment/helm-lifecycle.sh` | one release in one namespace | the claim, which is not a release object; and it never passes `--create-namespace` |
| `scripts/environment/terraform-prerequisites.sh destroy --confirm` | the platform namespace and the claim inside it, by cascade | the cluster, any other namespace, and anything the project did not create. It refuses to run while a release is still installed |

Nothing in this repository deletes the cluster-side claim except
`terraform destroy`, which is the operation that reclaims the 1.71 GiB. It is run
through
[`scripts/environment/terraform-prerequisites.sh`](../../scripts/environment/terraform-prerequisites.sh),
which refuses it without `--confirm` and refuses it while a release is still
installed. `V1-S3-011` ran it on the `docker-desktop` provider: the namespace and
the claim were both removed, and the release had already been uninstalled, so
neither refusal fired.

## What this does not establish

- **The storage underneath the claim was not tested for durability.** The claim
  bound, the init container ran, and the artifact survived a pod replacement —
  all on `rancher.io/local-path` inside one node container. Nothing here says what
  survives a host failure, a Docker Desktop reset, or another provisioner, and
  what a reset reclaims is still recorded as unknown.
- **Two different restart experiments exist, and neither replaces the other.**
  [The container-level measurement](../proof/serving/v1-s3-003-pr1-restart-reload.md)
  is the same property one layer down, on one host;
  [the pod-restart record](../proof/serving/v1-s3-003-pr2-kubernetes-pod-restart.md)
  is the Kubernetes one.
- **BusyBox reading a 1.71 GiB file under a read-only root filesystem as uid
  65534 is no longer untested**: the `verify-model` init container did exactly
  that, under the pod's own security context, and exited zero on every pod start
  in `V1-S3-011`. On `docker-desktop` only.
- **`size` and `none` are weaker than they look.** `size` catches a truncated
  file and nothing else; a same-length substitution passes it.
- **No figure here is a performance claim.** The load times quoted are from one
  contributor host on CPU, and the restart experiment's own attempts on that host
  on one day spread 209 seconds between them — from 129,328 ms to 338,375 ms.
