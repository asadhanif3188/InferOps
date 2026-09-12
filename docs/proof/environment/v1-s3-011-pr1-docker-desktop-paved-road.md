# V1-S3-011-PR1 Docker Desktop paved road

Date captured: 2026-09-12

Classification: **local real evidence**, redacted. A real InferOps release was
installed into the Kubernetes cluster Docker Desktop provides, a real model was
loaded from a claim Terraform created, a real completion was returned through the
release's own Service, and the release was removed without residue. Nothing in
this record is mock, synthetic, or estimated.

This is an environment record about the `docker-desktop` provider. It is cited by
[the local cluster provider contract](../../environment/local-cluster-provider-contract.md)
for two capability answers that contract previously carried as `unknown` and owed
to this story, and for the identity check it carried as `undecided`.

## Classification and certification

Evidence class: `local-real-cpu`

Claim boundary: one Windows host, one Docker Desktop installation, one point in
time, one model revision, one runtime image digest, **one replica of each tier**.

It establishes, for the `docker-desktop` provider only:

- how a locally built image is made visible to that cluster, and that the engine's
  image store is not shared with it;
- that the cluster's nodes are containers on the local engine and can be bound to
  it, which is what the contract recorded as undecided;
- what the node's allocatable processors and memory actually are, against the
  engine's allocation;
- that the Terraform prerequisites, the Helm release, the model acquisition hook,
  the runtime, the API, the in-cluster connection test, and a real single-replica
  C2 completion all work end to end on that provider;
- that the telemetry collector the release installs discovers and scrapes both
  InferOps jobs, and that a real Prometheus can evaluate every accepted
  correlation query.

It establishes **nothing** about:

- the `kind` provider. Every answer here is Docker Desktop's, and
  [ADR 0011](../../architecture/decisions/ADR-0011-external-local-cluster-provider-contract.md)
  forbids borrowing one provider's answer for the other. `kind` remains
  *implemented and not executed* for the image path;
- **multi-replica serving.** The capacity gate refused on this host and that
  refusal is recorded below as the bounded evidence it is. There is no
  multi-replica claim here;
- throughput, latency, capacity, concurrency, model quality, any other host, or
  production behaviour. Three inference requests were sent during the telemetry
  stage for the sole purpose of moving counters off zero; their timings were
  deliberately not recorded.

## Provenance

| Input | Immutable identifier |
|---|---|
| Repository revision | `820a97797aa1cdafffc8944be3bc7299a54abd31` (the merge of V1-S3-010-PR2) |
| Node image | `kindest/node@sha256:08497ee19eace7b4b5348db5c6a1591d7752b164530a36f855cb0f2bdcbadd48` (tag `v1.34.3`) |
| InferOps API image | `localhost/inferops-api@sha256:7762924ac72ad7235ca6990980cb6a307bb5adca91276bf82240760590337c58` — built on this host, published to no registry |
| Model seed image | `localhost/inferops-model-seed@sha256:d791287d0f2aa67aaff4c133d8c0b041d8ce01360a6c84452fe76952bef011c7` — built on this host, published to no registry |
| Serving runtime image | `ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384` |
| Model integrity init image | `docker.io/library/busybox@sha256:9db7b59979c38555a39def84a31fb98b5296952f9e3afd4f6f11f05b07adfab0` |
| Model artifact | `Qwen/Qwen3-1.7B-GGUF`, revision `90862c4b9d2787eaed51d12237eafdfe7c5f6077`, file `Qwen3-1.7B-Q8_0.gguf`, `sha256:061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a` |
| Chart | `inferops-llm-0.3.0` |
| Helm | `v3.19.0+g3d8990f` |
| kubectl | `v1.34.3` |
| Terraform | `1.15.8` |
| Python | `3.12.6` |

Every version above was read from the tool itself during the run, not from a
document describing what should be installed. The two `localhost/` digests are
manifest digests of images built on this machine; they resolve in no registry and
describe this host's build rather than this repository.

## Environment

| Property | Value |
|---|---|
| Operating system | Windows 11 Enterprise, build 26200 |
| Shell | Git Bash (`MINGW64_NT-10.0-26200`) |
| Container engine | Docker Desktop, server `29.7.2`, storage driver `overlayfs` (containerd image store enabled), cgroup v1 |
| Engine allocation | 12 processors, 10 432 532 480 bytes |
| Kubernetes | Docker Desktop's own cluster, server `v1.34.3`, one node |
| Node | `desktop-control-plane`, container runtime `containerd://2.2.0`, network plugin `kindest/kindnetd:v20251212-v0.29.0-alpha-105-g20ccfc88` |
| Node allocatable | 12 cpu, 10 188 020 Ki (10 432 532 480 bytes) |
| Default StorageClass | `standard`, provisioner `rancher.io/local-path` |
| Accelerator | none; CPU only |
| Network | the node has outbound egress; it pulled `busybox` and `prom/prometheus` from their registries during this work |

Number of hosts: 1. Anything measured here is true of this host and no other
until it is repeated elsewhere.

The cluster was **not** created by InferOps and was not modified by it beyond the
namespace and claim Terraform owns and the release Helm owns. It was already
enabled, and it already hosted workloads belonging to unrelated work in another
namespace — which is the direct cause of the capacity refusal recorded below.
What those workloads are is not this record's business and is not named here; what
matters to a reader is that they are not InferOps's, that they were running before
this work began, and that they were not stopped.

## Method

Run from Git Bash at the repository root, with `INFEROPS_PROVIDER=docker-desktop`
set on every command. In order, including the ones that failed:

```text
scripts/environment/target-detect.sh
scripts/environment/api-image.sh load
scripts/environment/model-seed-image.sh load
scripts/environment/terraform-prerequisites.sh plan
scripts/environment/terraform-prerequisites.sh apply
scripts/environment/terraform-prerequisites.sh apply          (again, for idempotence)
scripts/environment/kubernetes-certification.sh certify        x5, four of which failed
scripts/environment/kubernetes-multi-replica-certification.sh certify   (refused at capacity)
scripts/environment/telemetry-collection-verify.sh verify
```

The four failed certification attempts are not omitted. Each one found a defect
that only an execution could find, each defect is fixed in this change, and they
are listed under [results](#results) because a workflow that has never been run is
not the same thing as a workflow that works.

`kubectl` deserves its own note, because the first thing this story did was fail.
The only `kubectl` on this host was the one Docker Desktop ships, `v1.36.1`, and
the Kubernetes Docker Desktop had provisioned on it is `v1.34.3` — two minor
versions apart, which is outside the skew Kubernetes supports.
`inferops::resolve_target` refused the run outright with `client-outside-skew`
before touching anything, which is correct and is the guard doing its job. A
`v1.34.3` client was fetched and placed ahead on `PATH` for every command above.
**The guard was not weakened and was not worked around**: it states a
supported-skew requirement, and the requirement was met rather than relaxed.

That a vendor ships a client two minors ahead of the server it provisions is
itself worth recording, because it will happen again to the next person: the
mismatch is not a mistake anyone here made, and the fix is a client, not a flag.

## Results

### The two capability answers this story owed

**`imagePreparation` — established.** Docker Desktop's Kubernetes does **not**
share the local engine's image store. A pod referring to an image the engine
holds fails with `ErrImageNeverPull` under `imagePullPolicy: Never`, by tag *and*
by digest, and the same is true of an image the engine pulled from a registry
rather than built. Measured directly: `localhost/inferops-api:dev`,
`localhost/inferops-api@sha256:7762…`, and `python:3.12-slim` were each scheduled
with `imagePullPolicy: Never` in a scratch namespace and each was refused.

`kind load docker-image` is **not** the mechanism, even though this is a kind
cluster. The kind CLI finds a cluster's nodes through
`docker ps --filter label=io.x-k8s.kind.cluster=<name>`, and Docker Desktop's API
proxy filters its own containers out of `docker ps` — so that filter returns
nothing here and `kind load` would find no nodes. `docker exec` and
`docker inspect` *by name* are not filtered.

The mechanism that works, and that `inferops::target_load_image` now implements:

```text
docker save <ref> | docker exec -i desktop-control-plane \
  ctr --namespace=k8s.io images import --all-platforms -
docker exec desktop-control-plane \
  ctr --namespace=k8s.io images tag --force <ref> <repository>@<digest>
docker exec desktop-control-plane crictl inspecti <repository>@<digest>
```

The explicit tag step is not decoration. `ctr images import` stores an image under
the names the archive carries — the tag, and nothing else — while containerd
resolves a `repository@digest` reference by looking for a *name* of that form,
which CRI creates when it pulls and an import does not. Without it the bytes are
present, the digest is right, and the reference the chart pins still does not
resolve, which looks exactly like a failed load and is not one. Observed: the API
image imported and `crictl inspecti localhost/inferops-api@sha256:7762…` failed
until the tag was created, then succeeded.

| Image | Size | Import elapsed |
|---|---:|---:|
| `localhost/inferops-api:dev` | 46 340 747 bytes | 5.6 s (measured) |
| `localhost/inferops-model-seed:90862c4b…` | 1 834 426 016 bytes of weights | 279.4 s (measured) |

**`capacity` — established.** The node is given effectively the whole Docker
Desktop virtual machine rather than a partition of it:

| Figure | Value | How read |
|---|---:|---|
| Engine processors | 12 | `docker info` (measured) |
| Engine memory | 10 432 532 480 bytes | `docker info` (measured) |
| Node allocatable cpu | 12 | node `status.allocatable` (measured) |
| Node allocatable memory | 10 188 020 Ki = 10 432 532 480 bytes | node `status.allocatable` (measured) |
| Committed on the node at capacity preflight | 1 410 millicores, 1 948 254 208 bytes | sum of pod requests (derived) |
| Uncommitted at capacity preflight | 10 590 millicores, 8 484 278 272 bytes | derived |

The consequence matters more than the numbers: a capacity gate on this provider
must read the node's own allocatable **and what is already requested on it**, not
the engine's total. The engine figure counts memory that unrelated workloads in
the same cluster already hold, and on this host that is the difference between
passing and refusing.

### The identity check the contract carried as undecided

`the-nodes-are-bound-to-the-local-engine` is now **implemented**. Docker Desktop
provisions its Kubernetes *with kind*: `desktop-control-plane` is an ordinary
container on the same engine the operator's own `docker` CLI talks to, carrying
`io.x-k8s.kind.cluster=desktop` and `io.x-k8s.kind.role=control-plane`.

**The labels alone settle nothing, and it is worth saying why before saying what
the guard does.** Those are kind's own generic labels. An ordinary
`kind create cluster --name desktop` produces a container named
`desktop-control-plane` carrying exactly those two values — byte for byte what a
label-only check would require. Docker Desktop *does* add labels of its own under
`desktop.docker.io/` (observed on this host: `desktop.docker.io/ports.scheme`,
`desktop.docker.io/ports/6443/tcp`, several `desktop.docker.io/binds/...`), and
they would distinguish it — but its API proxy strips them from what
`docker inspect` returns on the endpoint these scripts use. Measured both ways on
this host: through the default endpoint `docker inspect` returns only
`io.kubernetes.pod.namespace`, `io.x-k8s.kind.cluster` and `io.x-k8s.kind.role`;
through Docker Desktop's unfiltered engine endpoint it returns the
`desktop.docker.io/` set as well. Nothing in these scripts can read the latter.

So the check that carries the weight is a **port**. The container must publish the
very API server port the project-scoped kubeconfig dials — both sides read at
verification time, the server URL out of the kubeconfig the guard itself just
wrote, and the published `6443/tcp` binding off the container. Observed here:
container `desktop-control-plane` publishes `127.0.0.1:50351`, and the verified
kubeconfig names `https://127.0.0.1:50351`. That ties the *connection being
verified* to the *container being inspected* rather than correlating two names.

What the guard therefore refuses: a node this engine does not hold; a node
belonging to a kind cluster under any name other than `desktop`; and an API
server answering anywhere other than the port that container publishes.

What it **cannot** refuse, recorded here, in the contract's `gap`, and accepted as
`EX-06` in [the deferred-risk register](../../security/deferred-risks.md):

- a kind cluster the operator themselves named `desktop`, reached through a
  context they named `docker-desktop`. The port matches in that case because that
  cluster genuinely *is* the one being dialled; the guard is not deceived about
  which cluster it reached, only about who provisioned it;
- a `docker` CLI pointed at another engine. "This machine's engine" is really
  "the engine this CLI is configured to reach"; nothing here pins `DOCKER_HOST`
  or the active docker context, and pinning it is not free because Docker
  Desktop's own engine is itself reached through a non-default context.

And the difference from `kind`'s check that remains by construction: `kind` asks
the engine to *enumerate* the containers it labelled and can therefore notice a
node it was not told about, whereas here the same question can only be asked *by
name*, because of the `docker ps` filtering above. The node-count and node-name
checks that precede it are what fix the names it then binds, and the two are
relied on together.

### Terraform prerequisites

| Step | Result | Elapsed |
|---|---|---:|
| `plan` (empty cluster) | 2 to add, 0 to change, 0 to destroy | measured |
| `apply` | 2 added | measured |
| `apply` again | **No changes.** 0 added, 0 changed, 0 destroyed | measured |
| `apply` within each later certification run | 0 added, 0 changed, 0 destroyed | 15.8 s – 25.3 s (measured) |

The namespace carries `app.kubernetes.io/managed-by: Terraform` and
`inferops.io/lifecycle: prerequisite`. The claim stayed `Pending` until a pod
mounted it, which is `rancher.io/local-path`'s `WaitForFirstConsumer` behaviour
and not a fault.

### Single-replica Kubernetes C2 certification — certified

`outcome: certified`, exit code 0.

| Stage | Elapsed |
|---|---:|
| Terraform prerequisites | 15 791 ms |
| `helm install` accepted | 7 458 ms |
| Serving runtime ready (model loaded) | 10 482 ms |
| Platform API ready | 5 896 ms |
| In-cluster connection test | 4 303 ms |
| One real completion | 3 422 ms |

The completion: HTTP 200, 20 prompt tokens, 23 completion tokens, 43 total, 123
characters of content that was **not** retained. Adapter kind `real`, runtime
`llama.cpp llama-server` at the pinned digest, model revision
`90862c4b9d2787eaed51d12237eafdfe7c5f6077`, artifact hash compared **inside the
cluster** by the `verify-model` init container, claim mounted read-only. Release
revision 1 of `inferops-llm-0.3.0`, status `deployed`, release test passed.

The record names the provider: `kubernetes.cluster.provider: docker-desktop`.
It does not imply kind was executed, and it may not be read as though it were.

Cleanup: `helm uninstall` removed every object carrying the release's instance
label; the namespace and the model cache claim survived, and the claim count was
unchanged by the release.

### Multi-replica certification — refused at capacity, and that is the evidence

The gate refused before anything was installed:

```text
REFUSED multi-replica certification at stage capacity: this host cannot hold the profile.
  uncommitted cluster memory: 8484278272 bytes available, 8657043456 bytes required.
```

Short by 172 765 184 bytes — about 165 MiB. The memory that closes the gap is
held by workloads in another namespace that belong to unrelated work — about
3.2 GB of memory limits, running for weeks before this work began. They are not
InferOps's to remove and were not removed.

**The gate was not weakened and the replica count was not reduced to fit.** A
certification of fewer replicas than the profile requests is not this
certification. This refusal is the bounded evidence the story allows in place of
a multi-replica record, and no multi-replica claim is made anywhere in this
change.

One defect was fixed here: the refusal previously printed to a terminal and wrote
**no** record, so the only artefact on disk was a diagnostics file left by an
older run on an older day, which a reader would reasonably have read as describing
this one. The preflight now raises through the same path every other refusal uses
and writes `.cache/inferops/certification/k8s-multi-replica-inference-diagnostics.json`
naming stage `capacity` and the shortfall.

### Telemetry collection and correlation

See the run's own record at `.artifacts/telemetry-collection/verification.json`
(host state; `.artifacts/` is ignored by version control). It establishes that
the collector the release installs discovered and scraped **both** InferOps
scrape jobs, and that a real Prometheus parsed and evaluated every accepted
correlation query. Before this run the query record's own `verificationStatus`
said `collected: false`, `everInstalled: false`, and "No Prometheus has parsed,
loaded, or evaluated any expression in this record."

A query that returned no samples is reported as returning no samples rather than
counted as a pass or a failure: `emptyMeans` in the query record is what
interprets an empty result, and three requests are not enough traffic for every
counter to be non-zero. No latency or throughput figure is published from this
stage.

### Defects that only an execution could find

Five, each fixed in this change and each invisible to a render, a lint, or a
schema check:

1. **Every embedded Python reader returned a trailing carriage return.** A
   Windows Python writes CRLF from `print`, and every value these readers produce
   goes into a shell variable. Only the last field of a multi-line read escapes
   it, so the failure presented as "the certification descriptor's
   `descriptor_api_port` is not a number" — which reads like a descriptor defect
   and is not one. Fixed once, in `inferops::python`.
2. **The chart's `pre-install` hook named a ServiceAccount that does not exist
   yet.** Helm applies a phase's hooks before the release manifest, so the
   runtime account the model acquisition Job named had not been created when the
   Job was: the API server refused the Job, the hook timed out, and the install
   failed reporting only `failed pre-install: timed out waiting for the
   condition`. The Job now has its own account, created by the same hook phase at
   a lower weight and removed by the same delete policy.
3. **The telemetry collector could never start.** It was passed
   `--web.enable-lifecycle=false`, and Prometheus parses its command line with
   kingpin, where a boolean flag takes no value: the process exited with
   `unexpected false` before opening a port, every probe failed, and the release's
   connection test reported a refused connection to the collector Service — three
   steps from the cause. Both refusals are now spelled `--no-<flag>`, verified
   against the pinned image.
4. **`helm test --logs` reported a passing test as a failure.** The chart deletes
   a test pod that succeeded, so `--logs` then fails fetching logs from a pod that
   is gone. The two settings were in direct contradiction. `--logs` is dropped
   from all seven call sites; the failure path keeps the pod, and the diagnostics
   collector reads it.
5. **The residue check raced Kubernetes' garbage collector.** `helm uninstall
   --wait` waits for the objects Helm deleted itself; a Deployment's pods are
   removed afterwards by the garbage collector on the controller manager's
   schedule. Asking the instant Helm returned reported three terminating pods as
   residue. Both certification scripts now ask repeatedly inside the uninstall
   budget the descriptor already states; anything present at that deadline is
   still residue.

A sixth was found and fixed while this change was being written: a collected fact
that was assigned and not exported reached the facts writer as empty, and the
existing round-trip test could not see it because it supplies the writer's
environment itself. Both certification test files now assert that every
`INFEROPS_FACT_*` the script assigns is also exported.

## Limitations

- **One host, one Docker Desktop installation, one moment.** Docker Desktop
  chooses its own Kubernetes version and node image; both are recorded here and
  neither is pinnable by InferOps. A Docker Desktop release that provisions a
  different node shape, names its kind cluster something other than `desktop`, or
  stops filtering `docker ps` would change answers in this record.
- **The `docker ps` filtering this record depends on is Docker Desktop's
  behaviour, not a documented contract.** The guard is built on `docker inspect`
  precisely because that behaviour was observed rather than promised.
- **No multi-replica evidence exists.** The capacity refusal above is not a
  weaker form of a multi-replica record; it is a different thing entirely.
- **Three inference requests are not a measurement.** They exist so that counters
  are non-zero when the correlation queries are asked. No latency, throughput, or
  capacity figure is published from this record, in keeping with
  [ADR 0005](../../architecture/decisions/ADR-0005-evidence-and-measurement.md).
- **`kind` was not executed.** Nothing here certifies the `kind` provider, and its
  image path remains *implemented and not executed*.
- **What resetting or disabling Kubernetes in Docker Desktop reclaims was not
  observed**, and is still recorded as unknown. In particular, the 1.83 GB seed
  image imported into the node's containerd is **not** removed by anything
  InferOps runs; on `kind` deleting the cluster would reclaim it, and that answer
  is not borrowed here.

## Authorisation

Required: **yes**. The run installs into a cluster the operator owns, loads a real
model, and sends real inference requests.

Granted by: the host owner, in the session that ran it, for the Docker Desktop
provider specifically. Docker Desktop was started but never reset, disabled, or
reconfigured, and no workload belonging to another project was stopped or removed
— including the unrelated workloads whose memory caused the capacity refusal.

Sensitive values removed before committing: host name, user account, absolute
filesystem paths, the operator's kubeconfig and its path, the API server address,
and any certificate, key or token. Cluster-internal addresses inside the Docker
Desktop network are reproduced as emitted. The generated completion text was never
retained by the workflow and does not appear here.
