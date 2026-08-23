# V1-S0-002-PR2 local cluster smoke proof

Date: 2026-08-23

Classification: **local real-runtime evidence**, redacted. A cluster was created,
a workload was scheduled and answered a request, and both were removed. Nothing
here is mock, synthetic, or estimated.

Claim boundary: one Windows host, one architecture, one point in time. This
proves that the environment proposed in
[ADR 0001](../../architecture/decisions/0001-local-development-environment.md)
can be created, exercised, and removed. It proves nothing about inference,
models, serving runtimes, throughput, capacity, ingress, load balancing, or any
other operating system.

## Redaction

Host name, user account, filesystem paths, and the tool output lines that
contained them are excluded. Cluster-internal addresses are omitted where they
add nothing. Everything else is reproduced as the tools emitted it.

## What was executed

```text
scripts/environment/proof.sh --cycles 2
```

That script runs, per cycle: preflight, cluster creation, the hello-world smoke
test, partial teardown, full teardown, and residue verification. Two cycles were
run in one invocation so that "repeatable" is a result rather than an assertion.

Started `2026-08-23T12:09:40Z`, finished `2026-08-23T12:15:30Z`. Exit code `0`.

## Environment

### Host and engine

| Component | Value | Source |
|---|---|---|
| Operating system | Microsoft Windows 11 Enterprise, `10.0.26200` | Measured |
| Container engine server | `29.3.1`, API `1.54`, `linux/amd64` | Measured |
| Engine storage driver | `overlayfs` | Measured |
| Engine cgroup version | 1 | Measured |
| Engine kernel | `5.15.146.1-microsoft-standard-WSL2` | Measured |
| CPUs visible to the engine | 20 | Measured |
| Memory allocated to the container VM | **7.60 GiB** (`8158400512` bytes) | Measured |

The last row closes the open question ADR 0001 recorded as R5. The virtual
machine's memory ceiling had been assumed from the platform default at
approximately 7.84 GiB. The measured figure is 7.60 GiB — close to the
assumption, and confirming that the binding constraint is the virtual machine's
allocation and not the 15.68 GiB the host reports.

The engine provides **cgroup v1**, and kind emits a deprecation warning on every
cluster creation:

```text
cgroup v1 is deprecated in Kubernetes and will not be supported in a future kind
release, please upgrade to cgroup v2
```

Everything below worked on cgroup v1. This is recorded as a dated risk, not as a
defect.

### Tool versions

| Tool | Version | Provenance |
|---|---|---|
| kind | `v0.32.0 go1.26.3 windows/amd64` | Release binary, checksum verified below |
| kubectl client | `v1.34.1`, `windows/amd64` | Bundled with the container desktop application |
| Kubernetes server | `v1.34.8`, `linux/amd64`, built `2026-05-12` | The pinned node image |
| Node container runtime | `containerd://2.3.1` | Reported by the node |
| Node OS image | Debian GNU/Linux 13 (trixie) | Reported by the node |

The kind binary was verified before it was allowed to create anything:

```text
0bcb2d1cfedc1912d664014db716937e8a0e843e91c6807b4db2025dbc8989fa
```

That matches `kind-windows-amd64.sha256sum` as published with the v0.32.0
release.

### Digest pinning held

A pin is worth nothing unless the engine actually ran it, so the running image
was read back rather than trusted:

| | Value |
|---|---|
| Pinned in `deploy/kind/inferops-dev.yaml` | `sha256:02722c2dedddcfc00febf5d27fbeb9b7b2c14294c82109ff4a85d89ac9ba3256` |
| Image the node container ran | `sha256:02722c2dedddcfc00febf5d27fbeb9b7b2c14294c82109ff4a85d89ac9ba3256` |

Identical on both cycles.

### Client/server skew

A `v1.34.1` client against a `v1.34.8` server: **skew 0**. The server
additionally reports `minCompatibilityMinor: 33`.

This is why the node image is pinned to a Kubernetes 1.34 build rather than to
this kind release's default of 1.36. With the default, the kubectl bundled with
the container desktop application on this host would have been two minor versions
behind the server and outside the supported range. ADR 0001 recorded that
constraint; this is the measurement that acts on it.

## Results

### Cluster creation

| Cycle | Control plane ready | Node status |
|---|---|---|
| 1 | 16 s | `Ready`, `control-plane`, `v1.34.8` |
| 2 | 13 s | `Ready`, `control-plane`, `v1.34.8` |

Two further creations in the same session reported 14 s and 13 s, so four
creations fell in a 13–16 s band. These are warm figures: the node image was
already cached. A first run on a cold host also downloads roughly 1.35 GB.

All eight control-plane and system pods reached `Running` on both cycles: `etcd`,
`kube-apiserver`, `kube-controller-manager`, `kube-scheduler`, `kube-proxy`,
`kindnet`, and two `coredns` replicas.

### Hello-world workload

Applied objects: a `Namespace`, a `ConfigMap`, a `Deployment`, and a ClusterIP
`Service`, all in the `inferops-smoke` namespace and all labelled
`app.kubernetes.io/part-of: inferops`.

The rollout completed and the `Deployment` reached `Available` on both cycles.
The `Service` acquired an `EndpointSlice` pointing at the pod's port 8080.

The request was made from a `Job` running **inside** the cluster, against the
fully qualified Service name, so that cluster DNS resolution and Service routing
are part of what is proven rather than bypassed by a host-side port-forward:

```text
requesting http://hello-world.inferops-smoke.svc.cluster.local:80/index.html
response: inferops-hello-world-ok
SMOKE_ASSERTION_PASSED
```

Identical on both cycles. The response string is fixed in the ConfigMap and
asserted twice — once by the Job's own exit status, once by the calling script —
so a Job that completed without actually fetching anything would still fail.

This workload serves a static string. It is not inference and cannot be cited as
evidence of any serving behaviour.

### Resource cost

Measured on a settled cluster with no workload deployed, sampled six times over
roughly 150 seconds:

| Measure | Value |
|---|---|
| Node container memory, idle | 712–720 MiB of the 7.598 GiB the engine offers, about 9% |
| Node container CPU, idle | 22.7%–39.7% as the engine reports it, across six samples |
| Node container memory, workload running | 587–703 MiB observed |

The workload figures are not higher than the idle ones. That is not an anomaly to
explain away: the hello-world container requests 16 MiB, which is inside the
sampling noise of a control plane that is itself the dominant consumer.

Disk, measured across a full create-and-destroy cycle:

| Measure | Before | With cluster | After teardown |
|---|---|---|---|
| Engine local volumes | 10.34 GB across 32 | 11.45 GB across 33 | 10.35 GB across 32 |
| Engine containers | 3 | 4 | 3 |
| Host system-volume free | 22.98 GB | 22.94 GB | 22.88 GB |

Two things here deserve to be read carefully. The cluster costs about **1.1 GB**
of engine volume storage while it exists, and that space is returned on teardown.
Host free space, however, did **not** return: it fell by roughly 0.1 GB across the
cycle and stayed down, because the engine's virtual disk grows and does not shrink
when its contents are deleted. Reclaiming that is a container-engine maintenance
operation, not something a project teardown can or should perform.

The node image is a further ~1.35 GB, retained by design and removable with
`scripts/environment/cluster-down.sh --purge-node-image`.

### Teardown

Full teardown ran five times in this session. Every run reported:

```text
[inferops] no cluster named 'inferops-dev'.
[inferops] no node containers labelled for 'inferops-dev'.
[inferops] no project kubeconfig at .kube/inferops-dev.config.
[inferops] no 'kind-inferops-dev' context in the default kubeconfig.
[inferops] no volumes labelled for 'inferops-dev'.
[inferops] the shared 'kind' network is still present, as ADR 0001 (D6) states it will be.
[inferops] the cached node image is retained, as ADR 0001 (D6) states it will be.
[inferops] teardown verified: no residue beyond the artefacts ADR 0001 (D6) documents.
```

The two surviving artefacts are exactly the two ADR 0001 (D6) said would survive,
and no others were found. Partial teardown was also exercised: it removed the six
project objects and the namespace, and left the cluster running.

The contributor's default kubeconfig was inspected after every teardown and never
contained a `kind-inferops-dev` context, confirming that nothing was ever merged
into it.

## The safety guards were attacked, not assumed

ADR 0001 (D5) and (D6) make claims about what these scripts will refuse to do. A
claim of refusal is worth nothing until something tries. Four attempts were made.

| # | Attempt | Result |
|---|---|---|
| G1 | Run `cluster-up.sh` with the cluster already present | Refused: `cluster 'inferops-dev' already exists.` Exit 1 |
| G2 | Pass `cluster-down.sh` an argument it does not define | Refused: `unknown argument '--delete-everything'.` Exit 1 |
| G3 | Point the project kubeconfig's current context elsewhere, then run a destructive step | Refused: `expected context 'kind-inferops-dev', found 'does-not-exist'.` Exit 1 |
| G4 | Create a second, real kind cluster, rename its context to `kind-inferops-dev`, and point the project kubeconfig at it | Refused: `the reachable cluster reports node(s) outside 'inferops-dev': inferops-guard-probe-control-plane`. Exit 1 |

G4 is the one that matters. It is the scenario the ADR was actually worried about
— a destructive operation reaching a cluster that is not this project's — and it
was built to defeat the naive defence. The context name was correct. The
kubeconfig was valid. The cluster was real and running. It was refused anyway,
because the guard requires every node the API server reports to be a container
that kind itself labelled for `inferops-dev`, and a name a human typed cannot
satisfy that.

After the refusal, the foreign cluster was inspected and still held all five of
its namespaces. Nothing had been deleted from it. It was then removed, and the
project's own cluster was confirmed unharmed.

## Limitations

- **One host, one operating system, one architecture.** Windows 11 x64 with
  WSL 2. No Linux or macOS host was measured, so ADR 0001's cross-platform intent
  remains untested.
- **cgroup v1.** The engine on this host provides cgroup v1, which kind warns is
  deprecated. The proof holds on cgroup v1 today and says nothing about the kind
  release that drops support for it.
- **Warm creation times.** The 13–16 s figures exclude the node image download.
- **CPU figures are engine-reported instantaneous samples**, not sustained
  measurements, and were taken on a host also running an interactive desktop
  session.
- **`kubectl top` is unavailable** in kind, which ships no metrics-server, so
  per-pod resource figures were not collected. The engine-level figures above are
  what was measured.
- **No ingress controller and no `Service type=LoadBalancer`** were installed or
  exercised. kind ships neither, and ADR 0001 records this as outstanding work.
  The Service proven here is ClusterIP only.
- **The workload is a static-text HTTP server.** No model, no serving runtime, no
  inference, no benchmark, and no security scan was run.
- **The `kubectl` used is not independently pinned.** It arrives with the
  container desktop application and moves with it. The skew check catches drift;
  it does not prevent it.
- **Nothing here tests D3 or D4** of ADR 0001. No task runner and no dependency
  manager was exercised, so those two decisions remain proposed on documentation
  alone.
