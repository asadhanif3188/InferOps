# Local cluster provider contract

Status: **accepted** as the V1 environment contract, in
[ADR 0011](../architecture/decisions/ADR-0011-external-local-cluster-provider-contract.md),
and **implemented on one side only**. The authoritative form is data:
[`local-cluster-provider-contract.v1alpha1.json`](local-cluster-provider-contract.v1alpha1.json).
This page explains it, and
[`tests/architecture/test_local_cluster_provider_contract.py`](../../tests/architecture/test_local_cluster_provider_contract.py)
holds the two to each other and to the repository.

Read the status before the content. The only guard that exists is the `kind` one
in [`scripts/environment/lib.sh`](../../scripts/environment/lib.sh), and it
accepts one cluster name, `inferops-dev`. **Nothing can identify a Docker Desktop
cluster yet**, so every environment script refuses one — which is the right
failure until a positive check exists, and is not support. There is no provider
selection input anywhere in the scripts; they assume `kind`. Every row below that
nothing enforces says so, and says who owes it.

## What InferOps does and does not do to a cluster

**InferOps consumes a cluster somebody else created.** It never creates, enables,
resets, reconfigures, or deletes one, and no platform workflow runs a helper that
does. The operator does all five with the provider's own tooling: the `kind` CLI,
or Docker Desktop's settings.

What InferOps does own, in order:

```text
   operator provides an existing cluster       (kind CLI, or Docker Desktop)
       |
   selection: the operator names the provider, and for kind the cluster
       |
   verification: that provider's identity checks, against the reachable
   API server, before anything is changed          -> refuse, or:
       |
   project-scoped access: one kubeconfig, one context, written only now
       |
   target facts handed on: Terraform and Helm get an address; the drivers
   and the evidence get the rest
       |
   Terraform prerequisites, then the Helm release, inside that cluster
       |
   every runtime record names the provider it ran on
```

The `kind` helper scripts — `cluster-up.sh`, `cluster-down.sh`, `proof.sh`, and
the runbook in [the local cluster page](local-cluster.md) — stay in the
repository. They are one way for an operator to create a `kind` cluster, their
evidence is valid for what it measured, and they are not part of the platform
path.

## Selecting a target

| Provider | Selection inputs | Lifecycle, and who performs it |
|---|---|---|
| `kind` | `provider`, `clusterName` | The operator, with the `kind` CLI. The helper is optional |
| `docker-desktop` | `provider` | The operator, in Docker Desktop's settings. InferOps ships nothing that could |

**No input has a default.** A default is a selection somebody else made, and the
case where it is wrong is the case where the operator did not notice. A `kind`
cluster name is required because several `kind` clusters can share one engine;
Docker Desktop takes no name because its cluster is a singleton, and a name input
would be a second way to be wrong.

**Detection may report, never select.** A workflow may say which providers it can
see. It never picks one.

**Every mutating workflow is given the selection and re-verifies.** A target
recorded by an earlier run is compared against, never trusted: the cluster a
context points at can change between two commands.

## What verification hands on

These are the fields of the verified target. A consumer receives only the fields
naming it.

| Fact | Terraform | Helm | kubectl workflows | Certification | In evidence |
|---|:---:|:---:|:---:|:---:|:---:|
| `provider` | | | Yes | Yes | Yes |
| `clusterName` | | | Yes | Yes | Yes |
| `kubeconfigPath` | Yes | Yes | Yes | Yes | **No** |
| `kubeContext` | Yes | Yes | Yes | Yes | Yes |
| `serverVersion` | | | | Yes | Yes |
| `nodeNames` | | | | Yes | Yes |
| `containerRuntime` | | | | | Yes |
| `networkPlugin` | | | | | Yes |
| `networkPolicyEnforcement` | | | | Yes | Yes |
| `defaultStorageClass` | | | | Yes | Yes |
| `imagePreparation` | | | Yes | Yes | Yes |
| `engineCapacity` | | | | Yes | Yes |
| `verifiedAt` | | | | Yes | Yes |
| `verifiedRevision` | | | | | Yes |

**Terraform and Helm receive an address and never a provider.** A module that
knows which provider it is on starts accreting provider-specific lifecycle logic,
which is exactly what this contract moved out of InferOps. The prerequisite
module already names no provider. Its environment root does not yet comply: its
`kube_context` validation accepts only `kind-inferops-` contexts, and a test pins
that gap so that closing it has to update this page.

**The kubeconfig is a credential.** For `kind` it holds the client certificate and
key the helper wrote; for `docker-desktop` it would hold a copy of Docker Desktop's.
Its path never enters a record and the file never enters the repository. Nor do
the API server's address, any certificate, key, or token, the operator's own
kubeconfig or its path, any context other than the verified one, or host names,
user accounts, and filesystem paths.

## How each provider is identified

Positive identification is the whole of the safety argument, so each check says
whether anything performs it.

| Check | Provider | Status | Enforced by |
|---|---|---|---|
| `the-project-kubeconfig-names-the-kind-context` | `kind` | Implemented, for `inferops-dev` only | `inferops::target_cluster_problem` |
| `every-node-is-a-container-kind-labelled-for-the-cluster` | `kind` | Implemented, for `inferops-dev` only | `inferops::target_cluster_problem` |
| `kind-reports-the-selected-cluster` | `kind` | Implemented; called by the helper and `cluster-verify.sh`, not by platform workflows | `inferops::cluster_exists` |
| `the-docker-desktop-context-exists` | `docker-desktop` | Specified; nothing implements it | — |
| `every-node-has-an-observed-docker-desktop-shape` | `docker-desktop` | Specified; nothing implements it | — |
| `the-nodes-are-bound-to-the-local-engine` | `docker-desktop` | **Undecided** | — |

The `kind` check is the one [ADR 0001](../architecture/decisions/ADR-0001-local-development-environment.md)
D5 describes and that was attacked with a real foreign cluster wearing this
project's context name. It binds every node the API server reports to a container
`kind` labelled on the local engine. **That binding is what makes it more than a
name check**, and it is the part the Docker Desktop side does not yet have.

The Docker Desktop checks are deliberately narrow. The node shape accepted is the
one this project has observed — a single node, `desktop-control-plane`, running
`kindest/kindnetd` — and any other shape is refused until somebody observes and
records it. Whether Docker Desktop's nodes can be bound to the local engine the
way `kind`'s can has not been established. If they cannot, the Docker Desktop
guard is a name-and-shape check, weaker than `kind`'s, and that becomes a
recorded security exception beside `EX-02` rather than a difference nobody
mentions.

## When a workflow must refuse

Every refusal happens before any Terraform, Helm, or kubectl mutation and before
any image is loaded.

| Refusal | When | Implemented for |
|---|---|---|
| `no-provider-selected` | A mutating workflow gets no provider | Nothing |
| `unsupported-provider` | The provider is neither `kind` nor `docker-desktop` | Nothing |
| `ambiguous-target` | The selection is not exactly one cluster: `kind` with no name, a name `kind` does not list exactly once, or a kubeconfig holding more than one context | Nothing |
| `target-missing` | No project kubeconfig, no such `kind` cluster, or no `docker-desktop` context | `kind` |
| `target-unreachable` | The API server does not answer, or reports no nodes | `kind` |
| `unexpected-context` | The project kubeconfig's context is not the verified one | `kind` |
| `provider-mismatch` | The reachable cluster fails the selected provider's checks, including when it is the other provider's cluster | `kind` |
| `capability-unknown-or-insufficient` | The workflow needs a capability the target lacks, or one recorded below as unknown | Nothing |
| `client-outside-skew` | kubectl is more than one minor version from the server the target reports | Nothing |

The four `kind` rows are all performed by one function,
`inferops::target_cluster_problem`, and only for the pinned name. `provider-mismatch`
is implemented in one direction: a Docker Desktop cluster reached where `kind` is
expected is refused, because its node carries no `kind` label. The other
direction needs a Docker Desktop check, which does not exist.

`client-outside-skew` is listed as unimplemented on purpose. `preflight.sh`
checks the client against the minor version the pinned node image should
produce, not against the version the selected cluster's server reports. For a
cluster the helper created from the pin those are the same; for Docker Desktop,
whose version the operator's Docker Desktop release decides, they need not be.

## Where the providers differ

Every answer states how it is known: **observed** on this provider and recorded;
**inferred** from a component the two share; **implemented, not executed**;
**documented** by the provider or by this repository's configuration; or
**unknown**. An unknown is written as unknown and never borrowed from the other
column.

| Question | `kind` | `docker-desktop` |
|---|---|---|
| `imagePreparation` | `kind load docker-image --name <cluster>`, then resolved in the node with `crictl inspecti`. *Implemented, not executed* | *Unknown.* Whether an engine-built image is visible without a load step has not been observed, and `kind load` is not assumed to apply |
| `defaultStorage` | kind's local-path StorageClass; the helper's node declares no `extraMounts`, so bytes live in the node container. *Documented* | A local-path provisioner under `/var/local-path-provisioner/`, reclaiming on delete. Class name not recorded. *Observed once* |
| `networkPolicyEnforcement` | Not enforced by kindnetd. *Inferred* from the Docker Desktop measurement, which ran the same plugin | Not enforced by the kindnetd build tested. *Observed* |
| `capacity` | The node shares the engine VM; preflight measures it. *Observed* | *Unknown.* The node's allocatable share of the Docker Desktop VM has not been recorded |
| `wholeClusterCleanup` | `kind delete cluster --name <cluster>` removes the node and its volumes; the `kind` network and node image survive. *Observed* | *Unknown.* What a reset or disable removes has not been observed, and no V1 workflow performs either |
| `kubernetesVersion` | Chosen by the node image; the helper pins 1.34.8. *Observed* | Bound to the Docker Desktop release, not pinnable. `v1.34.3` both times it was read. *Observed* |
| `nodeTopology` | `<cluster>-control-plane`, one node in the helper's definition. *Observed* | One node, `desktop-control-plane`, running kindest/kindnetd. *Observed* |

The two providers share a network plugin and a node shape. That is exactly what
makes it tempting to assume they share everything else, and it is why this table
exists.

## Evidence

**Every runtime record states the provider and cluster it ran on, and a result on
one provider is never presented as a result on the other.** Nothing writes a
provider into a record yet; that belongs to the implementation.

The records that have contacted a real cluster so far, labelled here without
editing them — they are history rather than documentation:

| Record | Provider | What it establishes |
|---|---|---|
| [Cluster smoke proof](../proof/environment/v1-s0-002-pr2-cluster-smoke.md) | `kind`, `inferops-dev` | Creation from the pinned image, a hello-world Service answering, teardown without residue |
| [Runtime feasibility record](../proof/serving/v1-s0-003-pr2-runtime-feasibility.md) | `docker-desktop` | The selected runtime serving real inference in a pod through a Service — from trial manifests, not from this project's chart |
| [Cluster lifecycle result](../proof/environment/v1-s3-001-pr1-cluster-lifecycle.md) | `kind`, `inferops-dev` | Repeatable create, verify, smoke, and teardown by the helper, and its refusals |
| [NetworkPolicy enforcement result](../proof/security/v1-s3-004-pr1-network-policy-enforcement.md) | `docker-desktop` | That the network plugin there enforced none of a default-deny's rules |

Read across, that says something easy to miss. **The cluster evidence behind
ADR 0001 exists only for `kind`; the in-cluster runtime evidence behind ADR 0002
exists only for Docker Desktop.** No InferOps release has been installed on
either, and neither column certifies the other.

## The rules, and which of them anything enforces

| Rule | Enforced by |
|---|---|
| `the-platform-path-never-changes-a-cluster-lifecycle` | A test reading every platform workflow for a cluster create, delete, or helper invocation |
| `the-cluster-belongs-to-its-operator` | A test reading the ownership inventory |
| `exactly-two-providers-are-supported` | A test |
| `selection-is-explicit` | **Nothing yet** |
| `detection-never-selects` | **Nothing yet** |
| `verification-precedes-every-mutation` | `inferops::assert_target_cluster`, for `kind` only |
| `a-context-name-is-never-identity` | `inferops::target_cluster_problem`, for `kind` only |
| `access-never-inherits-an-ambient-context` | `inferops::kubectl` and `inferops::helm`, for the `kind` kubeconfig only |
| `terraform-and-helm-receive-an-address-never-a-provider` | A test on the module; the environment root is the recorded gap above |
| `terraform-and-helm-ownership-stays-disjoint` | The ownership inventory's own test |
| `a-provider-difference-is-recorded-not-averaged` | A test on the capability table |
| `evidence-names-its-provider` | **Nothing yet** |
| `no-provider-certifies-another` | Review alone |
| `the-reference-provider-is-a-choice-of-host-not-a-ranking` | Review alone |

Fourteen rules: five enforced by a test, three by a shell guard for `kind` only,
three by nothing, one by another suite's test, and two by review alone. The data
records who owes each unimplemented one.

**The reference provider is `docker-desktop`.** The current re-certification runs
there because the reference host has it and does not have the `kind` CLI, and
because two of the four real-cluster records above already ran there. That is a
choice of host. It is not a claim that Docker Desktop is better, closer to
production, or equivalent to `kind`.

## What this contract does not do

- **It implements nothing on the Docker Desktop side.** Every `docker-desktop`
  check is specified or undecided, and every refusal is implemented for `kind` or
  for nothing.
- **It changes no script.** The guard, the wrappers, the Terraform variables, and
  the certification descriptors are byte-for-byte what they were.
- **It contacted no cluster.** Every Docker Desktop fact above is quoted from a
  record made earlier, with the date of that record rather than today's.
- **It cannot read prose.** The suite checks identifiers, statuses, sources, and
  the files a row names. A row whose description has drifted from the behaviour it
  describes will not fail a check.
