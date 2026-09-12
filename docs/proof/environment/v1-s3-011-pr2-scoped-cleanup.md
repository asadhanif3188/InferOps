# V1-S3-011-PR2 — scoped cleanup, and the cluster that outlived it

Date captured: 2026-09-12

Classification: **local real evidence**, redacted. Evidence class `local-real-cpu`.
A real release was uninstalled, the Terraform prerequisites were destroyed through
the repository's guarded wrapper, and the Kubernetes cluster Docker Desktop
provides was still there afterwards — reachable, with its node Ready and every
namespace InferOps does not own untouched.

This is the half of the Sprint 3 exit gate that says the platform is a **guest**.
Anything can install; what matters here is what it leaves behind, and what it does
**not** take with it.

## Provenance

| Input | Value |
|---|---|
| Provider | `docker-desktop` (the V1 reference provider) |
| Cluster / context | `docker-desktop` / `docker-desktop` |
| Kubernetes | server `v1.34.3` |
| Node | `desktop-control-plane`, Ready, kubelet `v1.34.3` |
| Default StorageClass | `standard`, provisioner `rancher.io/local-path` |
| Terraform | `1.15.8` |
| Helm | `v3.19.0+g3d8990f` |

## 1. What existed before the teardown

One `deployed` release, `inferops` revision 1 of `inferops-llm-0.3.0`, and the
objects it owns:

| Kind | Count | Names |
|---|---:|---|
| Deployment | 3 | API, serving runtime, telemetry collector |
| ReplicaSet | 3 | one per Deployment |
| Service | 3 | API, runtime, collector |
| ConfigMap | 3 | runtime configuration, telemetry scrape, collector configuration |
| ServiceAccount | 3 | API, runtime, collector |
| Pod | 3 | one per Deployment |
| NetworkPolicy | 5 | default-deny, API, runtime, collector, release test |

Beside them, and **not** part of the release: the Terraform-owned namespace
`inferops-release` and the claim `inferops-model-cache`, bound to
`pvc-646749a3-f0b8-40d9-949d-cc5b6e5a919e`.

## 2. `helm uninstall`

```text
helm uninstall inferops --namespace inferops-release --wait --timeout 600s
```

| Question | Answer |
|---|---:|
| Objects carrying `app.kubernetes.io/instance=inferops` afterwards | **0** |
| How long until that was true | 9 s |
| Helm releases in the namespace | **0** |
| Telemetry collector objects (Deployment, Service, ConfigMap, ServiceAccount, Role, RoleBinding) | **0** |

Asked by kind, each separately: Deployments 0, ReplicaSets 0, Services 0,
ConfigMaps 0, ServiceAccounts 0, Pods 0, NetworkPolicies 0, Jobs 0,
EndpointSlices 0.

**Asked until the garbage collector had finished, not once.** `helm uninstall
--wait` waits for the objects Helm deleted itself; a Deployment's pods are removed
afterwards by the garbage collector on the controller manager's schedule. Asking
the instant Helm returns reports terminating pods as residue — which is exactly
what an earlier attempt at the upgrade/rollback experiment did.

**Hook objects are the one documented exception, and it did not fire here.** The
model acquisition Job carries `hook-delete-policy: before-hook-creation,hook-succeeded`,
so a Job that *succeeded* removes itself and `helm uninstall` has nothing of it
left to remove. A Job that **failed** is deliberately kept for its logs and does
outlive the uninstall; that happened during the first attempt at the
upgrade/rollback experiment, and the scoped removal the chart documents —
`kubectl delete job -l app.kubernetes.io/component=model-acquisition` — is what
cleared it. In this teardown no acquisition Job existed at all.

## 3. What Terraform owned was still there, before Terraform was asked

```text
inferops-release  labels={app.kubernetes.io/component: platform-namespace,
                          app.kubernetes.io/managed-by: Terraform,
                          app.kubernetes.io/part-of: inferops,
                          inferops.io/lifecycle: prerequisite}
inferops-model-cache   Bound   pvc-646749a3-f0b8-40d9-949d-cc5b6e5a919e
```

That is the boundary working. A release came and went; the prerequisite layer it
was a guest in did not.

## 4. `terraform destroy`, through the guarded wrapper

```text
INFEROPS_PROVIDER=docker-desktop \
  scripts/environment/terraform-prerequisites.sh destroy --confirm
```

The wrapper re-verified the target **before** acting —
`target verified: provider=docker-desktop cluster=docker-desktop context=docker-desktop`
— and printed both of its warnings before destroying anything: that deleting the
namespace cascades, and that this reclaims the model weights.

It also refuses outright if a Helm release is still installed in that namespace,
or if Helm cannot be asked. Neither refusal fired, because the release was already
gone — which is the order this record is written in on purpose.

Afterwards:

| Question | Answer |
|---|---|
| Namespace `inferops-release` | `Error from server (NotFound)` |
| Claim `inferops-model-cache` | gone with it |
| Terraform state or plan artefacts tracked by git | **0** |

Nothing was deleted by hand to make any of this pass. The release was removed by
`helm uninstall` and the prerequisites by `terraform destroy`, each by the tool
the [ownership inventory](../../architecture/resource-ownership.md) assigns them
to.

## 5. The cluster survived

This is the hard acceptance criterion, and it is asked of the cluster rather than
inferred from not having run a delete command.

| Question | Answer |
|---|---|
| Does the API server still respond? | yes — server `v1.34.3` |
| Does the node still exist? | `desktop-control-plane`, **Ready**, kubelet `v1.34.3` |
| Is the node's container still running on the engine? | yes — `running`, label `io.x-k8s.kind.cluster=desktop` |
| Does the provider still verify through the committed guard? | yes — `provider=docker-desktop cluster=docker-desktop context=docker-desktop` |
| Default StorageClass | `standard`, `rancher.io/local-path`, unchanged |

**Namespaces before and after.** Before the teardown: `default`,
`inferops-release`, `inferops-serving-feasibility`, `kube-node-lease`,
`kube-public`, `kube-system`, `local-path-storage`, and one belonging to
unrelated work. Afterwards: the same list **minus `inferops-release`**. Exactly
one namespace disappeared, and it is the one Terraform owns.

**Docker Desktop was never reset, disabled, or reconfigured**, and nothing in this
project can do any of those: no workflow creates, enables, resets, or deletes a
cluster, and `tests/architecture/test_cluster_lifecycle_safety.py` refuses a
script that acquires the ability. The unrelated workloads that caused the
multi-replica capacity refusal in `V1-S3-011-PR1` were running before this work
began and were running after it ended; they were never stopped, and what they are
is not this record's business.

## 6. One piece of InferOps residue this teardown does **not** remove

`inferops-serving-feasibility` is still there, created `2026-09-02`, carrying
`app.kubernetes.io/part-of: inferops` and holding a completed `fetch-weights` pod,
a `llama-server` Service, and a Deployment scaled to zero.

It is named here because it is honest to name it: it is an InferOps-labelled
namespace, in the operator's cluster, that InferOps put there. It belongs to the
**Sprint 0 feasibility workflow** (`V1-S0-003`), which an operator applies by hand
and which is neither the release nor the Terraform prerequisite layer — so neither
`helm uninstall` nor `terraform destroy` owns it or removes it, correctly. It is
outside this PR's cleanup scope and was deliberately **not** deleted here:
removing an object this change does not own, in order to make a cleanliness
statement look better, is the opposite of what this record is for.

An operator who wants it gone removes that namespace explicitly. That it has no
owning teardown in any committed workflow is a real gap, and it is recorded as one
rather than tidied away.

## Limitations

- **One provider, one host, one teardown.** `docker-desktop`, on one Windows
  machine. Nothing here says what `kind` does, and
  [ADR 0011](../../architecture/decisions/ADR-0011-external-local-cluster-provider-contract.md)
  forbids borrowing the answer.
- **Survival was checked immediately afterwards.** The cluster was reachable and
  Ready when asked. Nothing here is a statement about it days later.
- **What a Docker Desktop reset or disable would reclaim was not observed** and is
  still recorded as unknown — including the 1.83 GB model seed image imported into
  the node's containerd, which nothing InferOps runs removes.
- **`terraform destroy` reclaimed the model weights**, as its own warning says.
  The next real run re-acquires them from the seed image on the host.

## Authorisation

Required: **yes**. The teardown removes a release and a namespace from a cluster
the operator owns.

Granted by: the host owner, in the session that ran it, for the `docker-desktop`
provider specifically.

Sensitive values removed before committing: host name, user account, absolute
filesystem paths, the operator's kubeconfig and its path, the API server address,
any certificate, key, or token, and the identity of the unrelated namespace whose
workloads are not this project's business.
