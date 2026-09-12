# Platform prerequisites: what Terraform owns, its state, and its teardown

Status: **applied, re-applied, and destroyed on the `docker-desktop` provider.**
`V1-S3-011` ran this configuration against the Kubernetes cluster Docker Desktop
provides: it created the namespace and the model cache claim, a re-apply reported
no changes, releases were installed into and removed from the namespace it owns,
and a guarded `destroy` removed both. Every Terraform-owned row in
[the ownership inventory](../architecture/resource-ownership.md) is now
`implemented` and cites the run that moved it.

That is one provider, on one Windows host. `kind` has not executed this
configuration since the ownership realignment, and
[ADR 0011](../architecture/decisions/ADR-0011-external-local-cluster-provider-contract.md)
forbids reading one provider's answer as the other's.

What was already established remains what it was: `terraform fmt` and
`terraform validate` pass, and an architecture suite compares this configuration
against the ownership inventory in both directions. That is `local-static`
evidence about files, and it is a different kind of evidence from a run.

## Where it lives

| Path | What it is |
|---|---|
| [`infra/terraform/modules/platform-prerequisites/`](../../infra/terraform/modules/platform-prerequisites/) | The module. Two resources and their metadata |
| [`infra/terraform/environments/local/`](../../infra/terraform/environments/local/) | The only environment. Pins the provider, names the kubeconfig and context, calls the module |
| [`infra/terraform/environments/local/.terraform.lock.hcl`](../../infra/terraform/environments/local/.terraform.lock.hcl) | The provider lock, with checksums for six platforms |
| [`scripts/environment/terraform-prerequisites.sh`](../../scripts/environment/terraform-prerequisites.sh) | The wrapper. Establishes cluster identity before Terraform reaches a cluster |
| [`tests/architecture/test_terraform_prerequisites.py`](../../tests/architecture/test_terraform_prerequisites.py) | What holds the configuration to the inventory |

## What it owns

Three inventory rows, and one Kubernetes object per row except where two rows
describe one object.

| `resourceId` | Kind | Where |
|---|---|---|
| `platform-namespace` | `v1/Namespace` | `kubernetes_namespace_v1.platform` |
| `namespace-metadata` | Object metadata | The labels and annotations on that namespace. One object, two rows: the namespace is the container a release installs into, and its metadata is the marker that keeps a scoped sweep away from it |
| `model-cache-volume-claim` | `v1/PersistentVolumeClaim` | `kubernetes_persistent_volume_claim_v1.model_cache` |

A fourth row, `platform-resource-quota`, is **deferred out of V1 and deliberately
absent.** It is named in the inventory so that if a quota is ever wanted it lands
on the prerequisite side of the boundary rather than inside a chart, which is
where a quota is usually put by accident. Naming it is not permission to build
it, and a test fails if it appears here.

### What it may never own

Stated as prohibitions because each is a specific way this boundary gets crossed
by accident rather than by argument.

- **Anything a release installs.** Terraform never imports or adopts a Helm-owned
  object. A resource in Terraform state and in a chart is reconciled by both, and
  the loser is whichever ran last.
- **A `Namespace` a release could also create.** The flag that does that is one
  flag and it is the default suggestion in most documentation. It is refused in
  the environment scripts, in `CONTRIBUTING`, and — as code — in this
  configuration.
- **A cluster.** Neither Terraform nor Helm may create, reconfigure, or delete
  one. That is
  [`scripts/environment/cluster-up.sh`](../../scripts/environment/cluster-up.sh)
  and `cluster-down.sh`, and it is the contributor's host that owns it.
- **A derived object.** Pods, ReplicaSets, EndpointSlices, and the
  `PersistentVolume` the provisioner binds to the claim are created by
  controllers. Adopting one into state means owning something that will not hold
  still.
- **Any cloud resource.** There is one provider and it talks to one local
  cluster. V1 provisions nothing that costs money.

### The label that carries the boundary

Every object this project creates carries `app.kubernetes.io/part-of: inferops`.
The accepted cleanup rules describe partial teardown as deleting *"only objects
matching the project label selector inside `inferops-` namespaces"* — so a sweep
matching only that label would delete these prerequisites, and one resource would
have two destroyers.

The resolution specified in [ADR 0004](../architecture/decisions/ADR-0004-component-and-ownership-boundaries.md)
is a second label, and this configuration is where it is finally set:

```text
app.kubernetes.io/part-of:    inferops      # every object, release and prerequisite
app.kubernetes.io/managed-by: Terraform     # which tool destroys this one
inferops.io/lifecycle:        prerequisite  # what a scoped sweep must exclude
```

**The exclusion itself is still not implemented.** The environment scripts'
scoped teardown is bound to the single smoke-test namespace and does not sweep
across `inferops-` namespaces at all, so nothing today can reach a prerequisite.
The constraint recorded in the ownership document stands unchanged and is now
one step closer to mattering: **the scoped sweep must exclude
`inferops.io/lifecycle=prerequisite` before it is ever generalised beyond the
smoke namespace.** This change does not generalise it and does not modify those
scripts.

## Providers and versions

| | Value | Why |
|---|---|---|
| Terraform | `>= 1.9.0` | A floor rather than a pin. Terraform is a host tool, like `helm` and `kubectl`, and this repository does not vendor it |
| Provider | `hashicorp/kubernetes` `2.38.0` | Exact. Everywhere else here a pin is exact — the node image and the runtime image by digest, the model by revision and per-file hash — because a range resolves to whatever was published most recently, and "it worked yesterday" becomes a statement about the registry |
| Lock | Six platforms | `terraform init` records the checksum for the platform it ran on and no other, which makes it a lock on one contributor's machine and an unpinned dependency on everybody else's. The committed lock covers `linux_amd64`, `linux_arm64`, `darwin_amd64`, `darwin_arm64`, `windows_amd64`, and `windows_386`, generated with `terraform providers lock -platform=…`. The last is what the reference host's own Terraform build reports, and a lock omitting the platform it was generated on would be a lock for other people and not for the person who wrote it |

The provider line is `2.x` and not `3.x` on purpose. Crossing a provider major
version changes resource schemas and how state represents them, and that is a
decision to take with a plan against a real cluster in front of you. Nothing here
has ever been applied, so this configuration is in no position to make that call.

## Variables

Every input, its default, and the refusal attached to it. The defaults are the
local environment; there is no committed `.tfvars` file, and there is no
contributor's absolute path anywhere in this configuration.

| Variable | Default | Refuses |
|---|---|---|
| `namespace` | `inferops-release` | A name not prefixed `inferops-` (ADR 0001 D5 makes the prefix the isolation rule), a name over 63 characters, and `inferops-smoke` — which `cluster-down.sh` deletes outright, so a prerequisite inside it would have two destroyers |
| `model_cache_claim_name` | `inferops-model-cache` | A name that is not a DNS-1123 label |
| `model_cache_size` | `4Gi` | Anything but a whole number of gibibytes, and anything below `2Gi`. The pinned artifact is 1,834,426,016 bytes — about 1.71 GiB — and the layout inside the claim is keyed by revision, so the default holds two pinned revisions rather than one |
| `storage_class_name` | `null` | Nothing. Null takes the cluster default; naming a class would tie the prerequisite layer to a distribution it does not own |
| `wait_until_bound` | `false` | Nothing, and see below — the default is the load-bearing part |
| `kubeconfig_path` (environment only) | `../../../../.kube/inferops-dev.config` | Nothing. Relative to the configuration, so a checkout anywhere works |
| `kube_context` (environment only) | `kind-inferops-dev` | A context not named `kind-inferops-…` |

### The two defaults that are not cosmetic

**`wait_until_bound = false`, and it has to be.** The accepted local provisioner
binds a claim on first consumer, so a claim nothing mounts stays `Pending` by
design. The provider's own default is to wait, which would hang `terraform apply`
until its timeout and then report a correctly-provisioned prerequisite as a
failure. The claim binds when the release that mounts it is installed, and the
bound volume is owned by a controller rather than by this configuration.

**The context validation is a name check and nothing more.** It refuses a context
that is not one of this project's kind clusters, which stops the common accident
of an apply following a context left selected from other work. It cannot
establish that the cluster on the other end really is this project's — a context
can be named anything. That check reads the node containers' kind labels and
lives in the wrapper script, which is how this configuration is meant to be run.

## Outputs

| Output | What it is for |
|---|---|
| `namespace` | The namespace a release installs into and must not create |
| `model_cache_claim_name` | The claim the chart mounts as `model.cache.claimName` and must not create |
| `model_cache_size` | The figure `terraform destroy` reclaims without destroying the cluster |
| `prerequisite_label_selector` | `inferops.io/lifecycle=prerequisite` — the selector a scoped teardown must exclude |

The first two are the handoff, and the handoff is by name. If the claim name here
and the claim name in the values file drift apart the release does not fail
loudly: it fails at schedule time with a claim that does not exist. So both are
compared against their counterparts —
`charts/inferops-llm/ci/real-values.yaml` and `INFEROPS_RELEASE_NAMESPACE` in
`scripts/environment/lib.sh` — by a test, rather than by a reader noticing.

## How to run it

```sh
scripts/environment/terraform-prerequisites.sh check              # no cluster needed
scripts/environment/terraform-prerequisites.sh plan
scripts/environment/terraform-prerequisites.sh apply
scripts/environment/terraform-prerequisites.sh destroy --confirm
```

`check` runs `terraform fmt -check -recursive`, `terraform init -backend=false`,
and `terraform validate`. `-backend=false` is what makes it runnable with no
cluster and no state: it initialises the provider and the module and skips the
backend, so a contributor with no cluster is still told that the configuration is
malformed.

Everything else first establishes that the cluster on the other end is this
project's — the API server's nodes have to be containers kind labelled for
`inferops-dev` — and then hands Terraform the kubeconfig and the context
explicitly, as `TF_VAR_kubeconfig_path` and `TF_VAR_kube_context`, rather than
letting it inherit either. They are passed as environment variables rather than
as `-var` because a Windows kubeconfig path contains backslashes and `-var`
values are HCL, where `\8` is an invalid escape.

`apply` plans to a file and then applies that file, so that what is applied is
what was shown. The saved plan goes to `.artifacts/terraform/`, which version
control ignores; a plan embeds the prior state and is host state, not evidence.

The equivalent raw commands, for a reader who wants to see what the wrapper does,
are in the script itself. Running them by hand skips the cluster-identity check,
which is the only thing standing between `terraform apply` and whichever cluster
a terminal happens to be pointed at.

## State

| | |
|---|---|
| Where | `infra/terraform/environments/local/terraform.tfstate`, on the contributor's disk |
| Backend | None. There is no `backend` block |
| Contents | The metadata of one Namespace and one PersistentVolumeClaim |
| Not in it | Any credential, token, or kubeconfig. The kubeconfig is read by path and never copied into state |
| Version control | Ignored, along with backups, saved plans, `.terraform/`, and any `.tfvars` |
| Losing it costs | Two `terraform import` calls. No data: the weights are in the claim, and the claim is a cluster object rather than a state entry |

There is no remote backend because there is nothing to put one on. A remote
backend needs a bucket, a lock table, and credentials, for a cluster that lives
inside one laptop's container engine and is deleted by a script. Adding one would
be provisioning paid infrastructure to hold the record of a namespace.

The cost of that choice, stated rather than left to be discovered: **two
contributors applying this against two clusters have two unrelated state files,
and neither knows about the other.** With one cluster per contributor that is
correct. It stops being correct the moment a shared cluster appears, and a shared
cluster is not something V1 has.

## Apply, and what a second apply does

Derived from the provider's semantics, and since `V1-S3-011` also observed on
`docker-desktop`.

| Operation | Expected |
|---|---|
| First `apply` | Creates the namespace, then the claim inside it. The claim is `Pending` until a pod mounts it, and that is success rather than a partial result |
| Second `apply`, unchanged | No changes. Both resources are declarative, and the metadata this configuration sets is the metadata it set last time |
| `apply` after the namespace was deleted by hand | Recreates it, and recreates the claim with it. The weights are gone, because deleting a namespace cascades |
| `apply` with a changed `namespace` | **Replaces.** A namespace's name is its identity, so Terraform destroys the old one — cascading over everything in it — and creates a new one. This is not a rename |
| `apply` with a changed `model_cache_size` | Requests a resize. Whether the local provisioner honours it is a property of that provisioner and is unverified here; a claim that cannot be resized fails the apply rather than silently keeping the old size |
| `apply` with a release already installed | Leaves the release alone. Terraform does not know about it, does not adopt it, and touches nothing inside the namespace |

The third and fourth rows are the ones worth reading before running this against
anything you care about. Both destroy a namespace, and destroying a namespace
takes everything inside it.

## Cleanup

```text
   pod restart             -> a pod goes and comes back. Nothing declared here
                              is affected.

   helm uninstall          -> the release goes. The namespace, its metadata, and
                              the model cache survive, which is the entire
                              reason the claim is a prerequisite.

   scoped object teardown  -> project-labelled objects in the project's smoke
                              namespace go. It does not reach this namespace
                              today, and must exclude the prerequisite label
                              before it is ever widened.

   terraform destroy       -> the prerequisites go. Deleting the namespace
                              cascades, so anything still installed dies with
                              it. This is not the routine uninstall path.

   cluster teardown        -> the cluster goes, by the environment scripts.
                              Neither Terraform nor Helm may do this.
```

`terraform destroy` reclaims the model weights — roughly 1.71 GiB — and the next
release re-downloads them over a transport whose certificate this project does not
validate. That is why it is not the routine path and why the wrapper asks for
`--confirm`.

It is not, however, the *only* way those bytes go. The accepted `kind` node
declares no `extraMounts` and the claim takes the cluster's default storage class,
so the weights live inside the node container: deleting the cluster with
[`cluster-down.sh`](../../scripts/environment/cluster-down.sh) destroys them too.
The precise claim is that `terraform destroy` is the only operation that reclaims
them **while leaving the cluster standing**.

The wrapper refuses four things outright:

- **a destroy without `--confirm`**, because the cascade is wider than the
  command reads;
- **a destroy while a release is still installed**, because the cascade would
  take the release with it and leave Helm's own record claiming it exists.
  The wrapper refuses rather than uninstalling for you: removing somebody's
  release is not a decision a prerequisite teardown gets to take. It refuses for
  *any* release in the namespace, not only this project's: the cascade does not
  ask whose a release is.
- **a destroy it cannot first prove is safe**, because absence has to be
  established rather than assumed. The wrapper requires `helm` on `PATH` and asks
  `helm list --all` for the namespace's releases; a query that fails — helm
  missing, the API server unreachable, RBAC forbidding the read, a release record
  that will not deserialise — leaves the question unanswered, and an unanswered
  question is not an answer of "nothing installed". `--all` is what makes a
  failed, pending or uninstalling release count as present. Output that is not a
  release name refuses for the same reason.
- **a destroy against a cluster it cannot identify**, which every script here
  checks the same way: the nodes the API server reports must be containers `kind`
  labelled for this project's cluster.

There is no flag that overrides any of the four.

Nothing here deletes a cluster, and nothing here reaches outside the namespace it
created.

## What is checked, and by what

`tests/architecture/test_terraform_prerequisites.py`, on every default test run,
with no cluster and no network:

- every declared resource maps to a Terraform-owned inventory row, and every
  Terraform-owned row in scope is declared — the comparison the ownership
  document said could not exist yet;
- the declared resource types are exactly the two expected ones, checked as an
  allowlist as well as a denylist, so a new kind cannot arrive unnoticed;
- no release resource, no derived resource, no deferred resource, no second
  provider, and nothing that creates a cluster;
- the namespace and the claim carry the project label, the managed-by label, and
  the prerequisite lifecycle marker;
- the namespace default is what the release lifecycle installs into and is not
  the namespace another script deletes outright;
- the claim name default is the one the chart's real values file mounts;
- the size default covers two copies of the pinned artifact, read from the model
  source record rather than typed here;
- the provider pin is exact and identical in the module, the environment, and the
  lock file, and the lock covers six platforms;
- the provider names both the kubeconfig and the context, the kubeconfig default
  is relative, and no host path or credential appears anywhere;
- state, backups, and plans are ignored by version control and the lock file is
  not;
- `terraform fmt -check` and `terraform validate`, skipped loudly where the
  binary is absent.

## What this does not establish

- **That it applies on any provider but the one that ran it.** `terraform apply`,
  a re-apply, and `terraform destroy` have all run, on `docker-desktop` only.
- **That the claim binds under another provisioner.** It bound here:
  `WaitForFirstConsumer` held it `Pending` until a serving pod mounted it, and it
  stayed bound to the same PersistentVolume across a pod replacement. The
  StorageClass that did that is `rancher.io/local-path`, and nothing here says
  what another provisioner would do.
- **That a re-apply is a no-op in general.** It was one here, repeatedly:
  `No changes. Your infrastructure matches the configuration.` on every re-apply
  during `V1-S3-011`. That is an observation on one provider, not a property
  proved for every cluster.
- **That the prerequisite label protects anything.** It is set here. The teardown
  that must exclude it has not been written, and until a sweep exists to exclude
  it, the label is a marker with no enforcement behind it.
- **Anything about a cloud.** This configuration has one provider, talks to one
  local cluster, and provisions nothing that costs money. It is not a statement
  that the design would work anywhere else.
