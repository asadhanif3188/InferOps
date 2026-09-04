# V1-S3-001-PR1 cluster lifecycle result

Date: 2026-09-04

Classification: **local real evidence**, redacted. A cluster was created, verified
four times while it existed and once after it was gone, exercised, partially torn
down, fully torn down, and confirmed clean.
Nothing here is mock, synthetic, or estimated.

Claim boundary: one Windows host, one architecture, one point in time. It
establishes that the lifecycle commands in `scripts/environment/` create, verify,
and destroy the named cluster repeatably on this machine, and that verification
returns the same answer every time it is asked. It establishes nothing about
inference, models, serving runtimes, Helm, Terraform, throughput, or any other
host. This is an environment result and may never be cited in support of a
serving claim.

Redaction: host name, user account, and filesystem paths are excluded, along with
any tool output line that contained them. Cluster-internal addresses inside the
ephemeral kind network are reproduced as emitted. Everything else is the tools'
own output.

## What was executed

`scripts/environment/proof.sh` was **not** used, because it runs `preflight.sh`
first and preflight refuses this host — see the limitation below. The same
sequence was therefore run step by step, from a clean state to a clean state:

```text
preflight.sh
cluster-up.sh
cluster-verify.sh          x2
smoke.sh
cluster-verify.sh
cluster-down.sh --workload
cluster-verify.sh
cluster-down.sh
cluster-verify.sh          (against the torn-down state)
verify-clean.sh
```

Started `2026-09-04T06:27:21Z`, finished `2026-09-04T06:30:04Z`.

## Result and elapsed time

| Step | Exit | Elapsed |
|---|---:|---:|
| `preflight.sh` | **1, see the host limitation below** | 12 s |
| `cluster-up.sh` | 0 | 53 s |
| `cluster-verify.sh` #1 | 0 | 5 s |
| `cluster-verify.sh` #2 | 0 | 5 s |
| `smoke.sh` | 0 | 19 s |
| `cluster-verify.sh` #3, after the smoke workload | 0 | 4 s |
| `cluster-down.sh --workload` | 0 | 39 s |
| `cluster-verify.sh` #4, after the partial teardown | 0 | 5 s |
| `cluster-down.sh` | 0 | 8 s |
| `cluster-verify.sh` #5, against the torn-down state | **1, intended** | 3 s |
| `verify-clean.sh` | 0 | 6 s |

The node image was already cached. A first run on a host without it adds the
transfer of roughly 1.35 GB.

The same sequence was run three times in this session, against successive states
of the scripts. The table above is the last of them, run against the code as
committed. The spread across all three: `cluster-up.sh` 53-69 s, `cluster-down.sh`
8-17 s, `smoke.sh` 19-23 s, and each `cluster-verify.sh` 3-7 s. Every run reached
the same exit codes and the same findings; the teardown figure varies most,
because it varies with how much the engine has to reclaim. All are one host's
numbers and none is a specification.

## Environment

| Component | Value | Basis |
|---|---|---|
| Operating system | Microsoft Windows 11 Enterprise, `10.0.26200` | Measured |
| Container engine server | `29.7.2`, API `1.55`, `linux/amd64` | Measured |
| Engine storage driver | `overlayfs` | Measured |
| Engine cgroup version | **1** | Measured |
| Engine kernel | `5.15.146.1-microsoft-standard-WSL2` | Measured |
| CPUs visible to the engine | 20 | Measured |
| Memory allocated to the container VM | 7.60 GiB (`8158400512` bytes) | Measured |
| Free disk on the measured volume | 22.85 GB (`22854164480` bytes) | Measured |
| kind | `v0.32.0` | Pinned |
| kubectl client | `v1.36.1`, `windows/amd64` | Bundled with the container desktop application |
| Kubernetes server | `v1.34.8`, node OS Debian GNU/Linux 13 (trixie) | The pinned node image |
| Container runtime in the node | `containerd://2.3.1` | Reported by the node |

## Create

`cluster-up.sh` completed with exit `0`. The node image digest it read back from
the engine matched the pin:

```text
[inferops] node image digest matches the pin: sha256:02722c2dedddcfc00febf5d27fbeb9b7b2c14294c82109ff4a85d89ac9ba3256
```

Every control-plane component was running within 31 seconds of the node
appearing:

```text
NAME                                                 READY   STATUS    RESTARTS   AGE
coredns-66bc5c9577-8qgz7                             1/1     Running   0          23s
coredns-66bc5c9577-n4d79                             1/1     Running   0          23s
etcd-inferops-dev-control-plane                      1/1     Running   0          31s
kindnet-gmjhr                                        1/1     Running   0          23s
kube-apiserver-inferops-dev-control-plane            1/1     Running   0          30s
kube-controller-manager-inferops-dev-control-plane   1/1     Running   0          29s
kube-proxy-bb8zz                                     1/1     Running   0          23s
kube-scheduler-inferops-dev-control-plane            1/1     Running   0          31s
```

## Verify, five times

`cluster-verify.sh` ran five times against three different cluster states. It
changes nothing, so this is a repetition rather than a sequence.

Against the freshly created cluster, and again immediately afterwards, the
`[inferops]`-prefixed output of the two runs was compared line by line and was
**identical**. The check was made with `diff` over the two captured runs; it
reported no difference.

```text
[inferops] === Cluster exists ===
[inferops] kind reports a cluster named 'inferops-dev'.

[inferops] === Kubeconfig and context ===
[inferops] project kubeconfig present at .kube/inferops-dev.config.
[inferops] context 'kind-inferops-dev' resolves to nodes kind labelled for 'inferops-dev'.

[inferops] === Pinned node image ===
[inferops] node image digest matches the pin: sha256:02722c2dedddcfc00febf5d27fbeb9b7b2c14294c82109ff4a85d89ac9ba3256

[inferops] === Node readiness ===
[inferops] every node reports Ready.

[inferops] === Control-plane workloads ===
[inferops] every kube-system pod is running or has completed.

[inferops] === Server version ===
[inferops] server minor 34 (pinned node image: 34)
[inferops] kubectl minor 36 against server minor 34; skew 2
[inferops] WARNING: kubectl is 2 minor versions from the server; the supported skew is 1.

[inferops] === Result ===
[inferops] cluster 'inferops-dev' is present, identified, pinned, and healthy.
```

Runs #3 and #4, after the smoke workload was deployed and after the partial
teardown removed it, reported the same findings and exited `0`. They were read
rather than diffed, because the pod listing they print necessarily differs -- pod
ages advance and the smoke workload comes and goes. The `[inferops]` findings
above were the same in all four, which is the point: the cluster's health is not a
function of what happens to be scheduled on it.

Run #5 is the exception and is meant to be. It ran against the torn-down state,
reported three problems, and exited `1`; it is recorded as F2 below.

## Destroy

`cluster-down.sh --workload` deleted the project's own objects and left the
cluster running:

```text
service "hello-world" deleted from inferops-smoke namespace
deployment.apps "hello-world" deleted from inferops-smoke namespace
job.batch "hello-world-verify" deleted from inferops-smoke namespace
configmap "hello-world-content" deleted from inferops-smoke namespace
namespace "inferops-smoke" deleted
[inferops] project objects removed; cluster 'inferops-dev' left running.
```

`cluster-down.sh` then removed the cluster and the project kubeconfig, and
`verify-clean.sh` confirmed what remained:

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

## Failure behaviour, deliberately provoked

Five failures were injected. Each was recovered from and the environment returned
to a clean state.

| # | Injection | Result |
|---:|---|---|
| F1 | Rename the context inside the project kubeconfig to `kind-somebody-else`, then run `cluster-verify.sh` | Refused: `cluster identity not established: expected context 'kind-inferops-dev', found 'kind-somebody-else'`. Every check after it was skipped and said so. Diagnostics printed. Exit `1` |
| F2 | Run `cluster-verify.sh` against a fully torn-down environment | Reported **three** problems in one run — no cluster, no kubeconfig, no identity — rather than stopping at the first. Diagnostics printed. Exit `1` |
| F3 | `INFEROPS_DISK_VOLUME` pointing at a path that does not exist | `could not read free space on /no/such/volume (configured); the 20.00 GB minimum tier was not checked`. A warning, not a failure: a volume that could not be read is not a volume that is full |
| F4 | `INFEROPS_DISK_VOLUME` pointing at a second, larger volume | Measured that volume instead and said `(configured)`, confirming the override selects what is measured |
| F5 | Raise the disk threshold above what the host has, then run `preflight.sh` | Refused: `free space on <volume> is 22.90 GB, below the 900.00 GB minimum tier`, and preflight exited `1` reporting two failed checks. The threshold was restored immediately afterwards |

F1 repeats, against the new script, the guard Sprint 0 established for the
teardown path. F5 is the only way to exercise the disk threshold on a host that
satisfies it, and it was performed by editing the constant in place and reverting
it; the committed value is unchanged and
[the architecture suite](../../../tests/architecture/test_cluster_lifecycle_safety.py)
compares it against ADR 0001 (D7)'s table on every run.

## Host limitation: preflight refuses this host

`preflight.sh` exited `1`:

```text
[inferops] kubectl minor 36 against node image minor 34; skew 2
[inferops] WARNING: kubectl is 2 minor versions from the pinned node image; the supported skew is 1.
[inferops] FAILED: 1 prerequisite check(s) failed. Nothing was changed.
```

That refusal is correct and was not worked around. The container desktop
application on this host now bundles kubectl `v1.36.1`, and the repository pins a
Kubernetes 1.34 node image. Every other prerequisite passed, including the disk
check added by this change.

The lifecycle was run anyway, deliberately, because `cluster-up.sh`,
`cluster-verify.sh`, and `cluster-down.sh` do not gate on the client's version —
that prerequisite belongs to preflight, and duplicating the verdict in four
scripts would only mean a contributor is told to fix it by whichever one they
happened to run. **Every result above was therefore produced with a client two
minor versions from the server, outside the window Kubernetes supports.** Nothing
observed misbehaved, and that is an observation rather than a guarantee.

### Moving the pin forward does not fix it, and this was tried

kind `v0.32.0`'s own default node image is
`kindest/node:v1.36.1@sha256:3489c7674813ba5d8b1a9977baea8a6e553784dab7b84759d1014dbd78f7ebd5`,
which would put client and server at the same minor. The pin was moved to it and a
cluster was created. `preflight.sh` passed with skew `0`. Creation then failed
after 77 s, during `kubeadm init`, with the control plane never reachable:

```text
ERROR: failed to create cluster: failed to init node with kubeadm: command
"docker exec --privileged inferops-dev-control-plane kubeadm init ..." failed with
error: exit status 1
...
error: error execution phase wait-control-plane: cannot obtain client without
bootstrap: ... dial tcp 172.23.0.5:6443: connect: connection refused
```

The run was repeated with kind's `--retain` so the node container survived, and
the kubelet's own journal gives the cause without ambiguity:

```text
kubelet: E0904 05:44:56.349308 run.go:72] "command failed" err="failed to validate
kubelet configuration, error: kubelet is configured to not run on a host using
cgroup v1. cgroup v1 support is unsupported and will be removed in a future
release"
```

The engine on this host provides **cgroup v1**, which ADR 0001's risk register
already records as a dated risk. Kubernetes 1.36's kubelet refuses to start on it
outright. The retained cluster was removed with `cluster-down.sh`, which reported
no residue, and the pin was restored to 1.34.8 unchanged.

So on a cgroup v1 host the two figures cannot be reconciled by moving the pin. The
ways out are to put a kubectl inside the supported window on `PATH` ahead of the
bundled one, or to move the engine to cgroup v2 and then revisit the pin. Both are
host changes this project does not make on a contributor's behalf, and the second
is a decision for ADR 0001 rather than for this change.

## What this does not establish

- Nothing about Linux or macOS. One Windows host, as before.
- Nothing about inference, models, serving runtimes, Helm, or Terraform. No
  InferOps workload was deployed; the only thing scheduled was the Sprint 0
  hello-world, and it serves a fixed string.
- Nothing about the recommended host tier, which remains an estimate.
- Nothing about behaviour with a kubectl inside the supported window, on this
  host, at this date — the client available here is outside it.
- Nothing about cgroup v2. The failure above establishes that Kubernetes 1.36
  refuses cgroup v1; it says nothing about whether this project works on cgroup v2,
  because that was not tested.
