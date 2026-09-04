# Local development cluster

Status: the workflow on this page has been executed and its evidence recorded.
See [the cluster smoke evidence](../proof/environment/v1-s0-002-pr2-cluster-smoke.md).

This page describes how to create, exercise, and remove the InferOps local
development cluster. It covers the environment only. There is no InferOps
application, serving runtime, or model to deploy into it yet, and the workload
used here is a static-text hello-world whose only purpose is to prove the cluster
schedules, routes, and tears down.

## What this creates on your machine

| Object | Name | Removed by full teardown |
|---|---|---|
| kind cluster | `inferops-dev` | Yes |
| Node container | `inferops-dev-control-plane` | Yes |
| Kubeconfig | `.kube/inferops-dev.config` in this repository, git-ignored | Yes |
| Kubeconfig context | `kind-inferops-dev`, inside that file only | Yes |
| Namespace | `inferops-smoke` | Yes |
| Shared container network | `kind` | **No** — other clusters may use it |
| Cached node image | `kindest/node` | **No** — opt-in, see below |

Nothing is written to your default kubeconfig, no host-wide engine setting is
changed, and no administrative rights are required. The two exceptions in the
last column are stated in [ADR 0001](../architecture/decisions/ADR-0001-local-development-environment.md)
(D6) and are deliberate, not oversights.

## Prerequisites

| Tool | Version | Notes |
|---|---|---|
| Docker Engine, and the `docker` CLI | Any reachable server | The engine must be running before you start |
| kind | `v0.32.0` | Pinned; another release is reported as unverified rather than refused |
| kubectl | 1.33, 1.34, or 1.35 | Must be within one minor version of the pinned node image |
| A POSIX shell | Any | On Windows, the shell supplied with Git is sufficient |

> [!NOTE]
> These scripts require the `docker` CLI specifically, not merely a
> Docker-API-compatible engine. They ask the engine directly which containers and
> volumes carry kind's cluster label, and that is how the cluster's identity is
> established before anything is deleted. ADR 0001 (D1) selects the engine *API*
> rather than a vendor product, and keeping a permissively licensed path open
> remains the intent — but running these scripts against Podman or another engine
> would need that label query ported, and nobody has done or tested that. Treat
> non-Docker engines as unsupported here until someone proves otherwise.

The cluster node image is pinned by digest to
`kindest/node:v1.34.8@sha256:02722c2dedddcfc00febf5d27fbeb9b7b2c14294c82109ff4a85d89ac9ba3256`.

That is deliberately not the default image of this kind release. It is a
Kubernetes 1.34 build, chosen so that a kubectl bundled with a container desktop
application stays within the supported one-minor-version client/server skew.
`scripts/environment/preflight.sh` checks that skew and tells you if yours is outside it.

Host resources: see the tiers in [ADR 0001](../architecture/decisions/ADR-0001-local-development-environment.md)
(D7). Preflight measures all three figures of the minimum tier -- processors,
memory reaching the container virtual machine, and free disk -- and fails if any
is below it.

On Windows and macOS the binding limit for memory is the allocation given to the
container virtual machine, not the memory installed in the host, and preflight
reads the actual allocation rather than assuming a platform default.

Disk is measured on the engine's own data directory where that directory exists
on your filesystem. On Windows and macOS it does not -- it is a path inside the
virtual machine -- so preflight measures the volume the engine places that
machine's virtual disk on by default, says which volume it measured, and says
that the figure is a proxy. If you have relocated the virtual disk, point the
check at the volume that now holds it:

```sh
INFEROPS_DISK_VOLUME=/d scripts/environment/preflight.sh
```

That selects what is measured. It does not lower the threshold or skip the check.

### Installing kind

Download the release binary for your platform from the
[kind v0.32.0 release](https://github.com/kubernetes-sigs/kind/releases/tag/v0.32.0),
verify it against the `.sha256sum` file published beside it, and place it on your
`PATH`. Verifying the checksum is not optional: the binary is about to create
containers on your machine.

## Running it

Every script is idempotent about its own preconditions and refuses rather than
guesses. Run them from the repository root.

```sh
# Read-only. Reports what is missing and changes nothing.
scripts/environment/preflight.sh

# Creates the cluster. Fails if one already exists, unless given --recreate.
scripts/environment/cluster-up.sh

# Read-only. Asserts the cluster is present, is ours, runs the pinned image,
# and is healthy. Run it as often as you like; it changes nothing.
scripts/environment/cluster-verify.sh

# Deploys hello-world, waits for readiness, and asserts the Service answers.
scripts/environment/smoke.sh

# Removes the cluster, the kubeconfig, and the context, then verifies residue.
scripts/environment/cluster-down.sh
```

None of these accepts an argument it does not understand. Every one of them
refuses and exits rather than ignoring it, because on a script that deletes
things the difference between a partial teardown and a full one should never be
decided by a typo nobody was told about.

To run the whole sequence from a clean state to a clean state, twice, which is
what the recorded evidence did:

```sh
scripts/environment/proof.sh --cycles 2
```

Each cycle creates the cluster, verifies it, runs the smoke test, and tears it
down. `cluster-up.sh` verifies the cluster it just made by running
`cluster-verify.sh`, and the cycle then runs the same script again on its own --
not out of caution, but because "verify is repeatable" is only a result if the
same read-only script reaches the same answer twice.

### What creation costs in time

Measured on the reference host with the node image already cached:

| Step | Elapsed |
|---|---|
| `cluster-up.sh`, including verification | 69 s |
| Of which the control plane reaching Ready | 13-16 s across four creations |
| `cluster-verify.sh` on its own | 6-7 s |
| `smoke.sh` | 23 s |
| `cluster-down.sh --workload` | 38 s |
| `cluster-down.sh` | 17 s |

A first run on a host without the node image adds the download of roughly
1.35 GB. These are one host's figures, not a specification.

## Verifying a cluster you already have

`scripts/environment/cluster-verify.sh` answers five questions and changes
nothing:

1. Does kind report a cluster by this project's name?
2. Is the project-scoped kubeconfig present, and does its current context resolve
   to node containers kind labelled for this cluster? A matching context name
   alone is not accepted.
3. Is the node running the image digest this repository pins?
4. Is every node Ready, and is every `kube-system` pod running or completed?
5. Does the server report the minor version the pinned image should produce?

It runs all five before reporting, so a cluster that is wrong in three ways tells
you all three at once, and on failure it prints the cluster list, the labelled
containers, and recent `kube-system` events before exiting non-zero.

One thing it deliberately reports without failing on: your kubectl's distance
from the server. That is a property of your workstation rather than of the
cluster, and `preflight.sh` owns it.

## Teardown options

```sh
# Delete only the objects this project created; leave the cluster running.
scripts/environment/cluster-down.sh --workload

# Full teardown, and also reclaim the cached node image (~1 GB on disk).
# Recreating the cluster afterwards downloads it again.
scripts/environment/cluster-down.sh --purge-node-image

# Assert that a teardown left nothing behind. Read-only; deletes nothing.
scripts/environment/verify-clean.sh
```

## How the scripts avoid touching anything else

These are enforced in `scripts/environment/lib.sh`, not merely intended:

- `kubectl` is only ever invoked with an explicit `--kubeconfig` and `--context`,
  so no invocation can fall through to an ambient `KUBECONFIG` or to whichever
  context happened to be current.
- Before any destructive step, the reachable cluster must present a
  control-plane node carrying kind's own `inferops-dev` cluster label. A matching
  context name alone is not accepted as proof of identity.
- Deletions are scoped by the `app.kubernetes.io/part-of=inferops` label inside
  the `inferops-` namespace, or are the deletion of the named cluster itself.
- Container and volume queries filter on kind's cluster label, so an object
  belonging to another cluster is neither reported nor at risk.
- Nothing prunes the engine, deletes all namespaces, or removes a context this
  project did not create.

Each of those is now also read out of the scripts and asserted by
[`tests/architecture/test_cluster_lifecycle_safety.py`](../../tests/architecture/test_cluster_lifecycle_safety.py),
so an edit that quietly drops a `--name` or a label selector fails the build
rather than waiting for review to notice. That suite reads the scripts as text
and runs none of them; what they actually do to a cluster is the cluster-smoke
layer's evidence, not its.

## When something fails

`scripts/environment/smoke.sh` collects diagnostics into `.artifacts/smoke/` — object
listings, descriptions, events, and pod logs — and leaves the workload in place
so you can inspect it. That directory is git-ignored; it is local host state and
must not be committed.

**If you interrupt a run.** Nothing traps Ctrl-C. Interrupting `cluster-up.sh` or
`proof.sh` mid-cycle can leave the cluster running, and the next `cluster-up.sh`
will then refuse rather than silently reuse it. `scripts/environment/cluster-down.sh`
recovers from that in one step. A teardown is deliberately not wired to a signal
handler: being interrupted halfway through deleting things is worse than being
left with something to delete.

Two failure causes are worth eliminating before blaming the cluster:

1. The engine's virtual machine memory allocation. It defaults to roughly half
   the installed memory on Windows and macOS, which can be below the minimum
   tier. Preflight reports the measured figure.
2. On Windows, an outdated WSL release. Control-group handling, init-system
   support, and networking behaviour relevant to running Kubernetes nodes as
   containers all changed across WSL releases.

**If preflight refuses your kubectl.** Container desktop applications ship their
own kubectl and move it forward on their own schedule. On the reference host it
is now `v1.36.1`, two minors from the pinned 1.34 node image, which is outside
the supported window and which preflight therefore refuses.

Moving the pin forward to match is not the fix, and this was tried rather than
assumed. kind `v0.32.0`'s own default node image is
`kindest/node:v1.36.1@sha256:3489c7674813ba5d8b1a9977baea8a6e553784dab7b84759d1014dbd78f7ebd5`,
and creating a cluster from it on this host fails during `kubeadm init` with the
control plane never reachable. The kubelet says why:

```text
failed to validate kubelet configuration, error: kubelet is configured to not run
on a host using cgroup v1. cgroup v1 support is unsupported and will be removed
in a future release
```

The engine here provides **cgroup v1**, which ADR 0001's risk register already
records; Kubernetes 1.36's kubelet refuses to start on it outright. So on a
cgroup v1 host the pin cannot move forward, and the two ways out are to install a
kubectl inside the window (1.33, 1.34, or 1.35) on your `PATH` ahead of the
bundled one, or to move the engine to cgroup v2 and then revisit the pin. Neither
is something these scripts will do to your machine.

## What this does not establish

- Nothing about ingress or `Service type=LoadBalancer`. kind ships neither, and
  ADR 0001 records installing them as outstanding work.
- Nothing about Linux or macOS. The recorded evidence is from one Windows host.
- Nothing about inference, models, serving runtimes, throughput, or capacity.
  The hello-world workload serves a fixed string from a ConfigMap.
