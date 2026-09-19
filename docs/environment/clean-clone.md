# Reproducing V1 from a clean clone

Status: **implemented and executed once.** The workflow, its checklist, and the
ledger it keeps were run to completion from a clean clone, against a real cluster,
by the author of the change that ran them.
[The executed record](../proof/environment/v1-s5-001-pr2-clean-clone-run.md) names
what it establishes and what it does not -- principally, that **no second engineer
has repeated it**. Until one does,
[`a-reviewer-can-reproduce-v1-from-a-clean-clone`](../testing/claim-evidence-matrix.md#scaffolding-and-the-quick-start)
is certified at C2 with that limitation attached, not confirmed by an independent
reviewer.

The authoritative form is data:
[`clean-clone.v1alpha1.json`](clean-clone.v1alpha1.json). The workflow is
[`scripts/environment/clean-clone.sh`](../../scripts/environment/clean-clone.sh);
the rules for what a run may record are in
[`tools/clean_clone`](../../tools/clean_clone/).

## What it is

One command that walks the V1 journey in order -- host prerequisites, the commands
of two of the default-checks lane's gates, workload scaffolding, model acquisition,
local real inference, provider verification, the release images, Terraform, Helm,
real Kubernetes inference, telemetry, load, a failure experiment, and scoped
cleanup -- and writes down, for every step, when it started, when it finished, what
it exited with, and what its result may be labelled.

It is mostly an orchestrator. Most steps run a workflow that already exists and
already guards itself, and hand it its own consent flag; a workflow's own refusals
are never bypassed. Some steps carry logic of their own, and those are the ones to
read closely: the host prerequisites, the runtime image pull, the namespace
snapshot in provider verification, the values merge, the survival check, and
cleanup -- whose release uninstall is the one mutation this script makes directly
rather than through an existing workflow.

## The cluster is the operator's

[ADR 0011](../architecture/decisions/ADR-0011-external-local-cluster-provider-contract.md)
decides this and the workflow follows it without exception:

- **The cluster must already exist.** Nothing here creates, enables, resets, or
  deletes one, and no kind helper is run. A step the story once described as
  "local cluster creation" is, under ADR 0011, provider *selection and
  verification* of a cluster the operator already has.
- **The provider is selected explicitly**, as everywhere else:
  `INFEROPS_PROVIDER=docker-desktop`, or `INFEROPS_PROVIDER=kind` with
  `INFEROPS_KIND_CLUSTER_NAME`. There is no default.
- **Full clean-clone certification is a complete run on `docker-desktop`.** `kind`
  is supported and the workflow runs on it, but a complete run there is recorded
  as complete and certifying nothing; the ledger's summary says which.
- **The cluster is still there afterwards,** with every namespace it held before
  the run. That is checked, by the last step, rather than inferred from not having
  run a delete.

## Consent

A certification run needs every forward-path consent -- the first three flags below
-- on **every** invocation, including one that resumes. Consent is never read back
out of a ledger. Cleanup's consent is asked for separately, when cleanup runs.

| Flag | Consent it gives | Steps that need it |
|---|---|---|
| `--confirm-downloads` | Download the pinned model, about 1.71 GiB, and pull the pinned runtime image by digest | `model-acquisition`, `runtime-image` |
| `--confirm-real-runtime` | Start the pinned runtime on this host against the verified model, and remove it | `local-real-inference` |
| `--confirm-real-kubernetes` | Contact the selected cluster, load images into its node, apply Terraform, install and exercise the release, and send it real load and a pod deletion | every step from `provider-verification` to `failure` |
| `--confirm-cleanup` on `run`, `--confirm` on `cleanup` | Uninstall a release this run left, destroy the Terraform prerequisites, and remove this run's scaffolds | `cleanup` |

`--confirm-downloads` is this workflow's own: neither step it covers belongs to a
workflow that takes a consent flag. Cleanup's consent reaches the Terraform wrapper
as that wrapper's own `destroy --confirm`.

### What else reaches the network

`--confirm-downloads` covers the two large, pinned artifacts. It is not the only
thing a clean clone fetches, and the first executed run found the rest by meeting
them:

| Step | Fetches | From |
|---|---|---|
| `toolchain-sync` | the locked Python packages, unless `uv`'s own cache already holds them | the package index `uv.lock` names |
| `release-images` | the two base images the Dockerfiles pin by digest, unless the engine already holds them | their registries |
| `terraform-prerequisites` | the pinned Kubernetes provider plugin, into `infra/terraform/environments/local/.terraform/` | `registry.terraform.io` |

None of these is gated by a consent flag, and none is a large model or runtime
image. A host without network access to those three sources cannot complete a run,
and a transient failure to reach one stops the step: the executed run's
`terraform-prerequisites` failed once on a name-resolution failure for
`registry.terraform.io` and passed on the next invocation.

A **preparation run** (`--prepare-only`) needs none of them. It runs every step
that needs no consent, runs any real step whose consent it *was* given, and records
every other real step as `not-run` with the reason. That is the only way a step is
ever recorded as not run, and a preparation ledger never summarises as `complete`:
it is `preparation-only`, or `failed` if a step it ran failed.

## Running it

Run from the repository root, in Git Bash on Windows. The workflow needs bash 5 or
later, and a host CPython 3.12 on `PATH` as `python`: until the `toolchain-sync`
step installs the locked environment, the ledger is kept by the host's own
interpreter, using its standard library only.

```text
scripts/environment/clean-clone.sh plan
scripts/environment/clean-clone.sh prerequisites
scripts/environment/clean-clone.sh run --prepare-only
```

The first prints the checklist; the second asks whether a certification run could
start here and writes nothing; the third runs everything that needs no consent.

A certification run, cleaning up after itself when the forward path succeeds:

```text
INFEROPS_PROVIDER=docker-desktop scripts/environment/clean-clone.sh run \
  --confirm-downloads --confirm-real-runtime --confirm-real-kubernetes \
  --confirm-cleanup
```

Nothing here has timed the whole journey; that is the next change's record. For a
sense of scale only, from separate records on one host: the one recorded run of the
load step's workflow took 16 min 56 s
([its validation record](../proof/serving/v1-s4-004-pr1-validation.md)), and the
default-lane suite the `default-lane-checks` step runs took 1 085 s in
[this change's own validation record](../proof/environment/v1-s5-001-pr1-validation.md).

### What a fresh run refuses

A fresh certification run starts only from a checkout that could be a clean
clone: no uncommitted change, and none of the state a previous run leaves --
`.artifacts/`, `.kube/`, `.cache/inferops/`, `.quickstart/`, or Terraform's local
state. A checkout refused here gets no ledger, so the next invocation is fresh
again rather than a resumption that would skip the check.

It then refuses a cluster that already holds the `inferops-release` namespace.
That is what makes the cleanup safe: the run records the namespaces the cluster
held when it first verified it, and everything cleanup later removes is inside a
namespace that was not there.

### Resuming

Run the same command again. The ledger is continued rather than restarted, and it
is refused if the checkout has moved to another revision, the provider or kind
cluster differs, a certification run is being continued as a preparation run or
the other way round, or the run has already been cleaned up.

A step that passed is skipped when the checklist marks it `resumable`. The
checkout, the host prerequisites, and the cluster's identity are asked again on
every invocation, because each can change between two commands. The identity is
the provider, the cluster name, and the UID of the cluster's `kube-system`
namespace: the first two do not change when a cluster is reset or recreated --
Docker Desktop's is always `docker-desktop` -- and the UID does. A step that failed
is where the next invocation starts.

Two things resuming does not do for you:

- **A release a failed step left installed is left installed.** Every release
  workflow refuses to install over one, which is deliberate: the failed release is
  the diagnosis. Uninstall it with the release-scoped command in
  [the troubleshooting guide](kubernetes-troubleshooting.md#1-uninstall-the-workload)
  -- that command names the `kind` helper's kubeconfig and context; name the
  verified target's instead, which for `docker-desktop` is the `docker-desktop`
  context -- record that you did with `note`, and run again.
- **A load or failure experiment's earlier run directory is moved aside, not
  deleted.** Both experiments refuse to start over one; the workflow renames it
  `<directory>.attempt-<milliseconds>`, because it is the record of what that
  attempt saw.

`run --restart` moves the ledger and the previous run's cluster snapshot aside and
begins again, so the restarted run verifies the cluster, refuses an existing
release namespace, and takes its own snapshot. That is useful for a preparation
run. A certification run cannot restart in the same checkout: the fresh-run check
refuses `.artifacts/`, which is where the ledger lives, so a new certification run
starts from a new clone.

### Manual steps

The ledger records what the operator tells it. Anything a person does that no step
did for them -- installing a tool, starting the engine, placing a `kubectl` within
one minor of the server first on `PATH`, setting `INFEROPS_DISK_VOLUME`,
uninstalling a failed release -- is recorded with `note`, and only then:

```text
scripts/environment/clean-clone.sh note "Placed kubectl v1.34.3 first on PATH" --step provider-verification
```

A note that carries a host path -- a drive letter, a `/home/...` or `/Users/...`
path, a network share -- is refused, so the ledger stays publishable without an
edit.

### Status

```text
scripts/environment/clean-clone.sh status
```

prints the summary: the run's status (`complete`, `incomplete`, `failed`, or
`preparation-only`), whether it certifies anything, the wall-clock time from the
first step's start to the last step's finish, the manual-step count, and each
step's latest outcome and elapsed time.

## What each step runs

| Step | Runs | Evidence it may carry |
|---|---|---|
| `clean-checkout` | `python -m tools.clean_clone checkout` | `local-static` |
| `host-prerequisites` | this script's own check: the ADR 0001 tier's figures from `lib.sh`, and the tools each authorized step needs | `local-static` |
| `toolchain-sync` | `uv sync --locked`, then the locked environment first on `PATH` | `local-static` |
| `default-lane-checks` | the commands of the default-checks lane's `code-quality` and `default-lane-tests` gates: formatting, lint, types, and the default-lane test suite. The lane's other nine gates are not run | `mock` |
| `workload-scaffold` | the quick start's two workloads, scaffolded into this run's own directory, validated, and tested | `local-static` |
| `model-acquisition` | `python -m tools.model_acquisition acquire`, then `verify` | `local-real-cpu` |
| `runtime-image` | `docker pull` of the digest the runtime package pins, which no workflow does implicitly | `local-real-cpu` |
| `local-real-inference` | `python -m tools.runtime_certification certify --confirm-real-runtime` | `local-real-cpu` |
| `provider-verification` | `target-detect.sh`, then `inferops::resolve_target`, then this script's own namespace snapshot | `local-real-cpu` |
| `release-images` | `api-image.sh` and `model-seed-image.sh`: build, load, values; then one merged values file | `local-real-cpu` |
| `terraform-prerequisites` | `terraform-prerequisites.sh` check, plan, apply | `local-real-cpu` |
| `helm-deployment` | `helm-lifecycle.sh` | `local-real-cpu` |
| `kubernetes-inference` | `kubernetes-certification.sh certify` | `local-real-cpu` |
| `telemetry-verification` | `telemetry-collection-verify.sh verify` | `local-real-cpu` |
| `load` | `performance-scenarios.sh run` | `local-real-cpu` |
| `failure` | `inference-pod-recovery.sh run` | `local-real-cpu` |
| `cleanup` | this script's own release uninstall if one was left, then `terraform-prerequisites.sh destroy --confirm` | `local-real-cpu` |
| `cluster-survived` | this script's own check: `inferops::resolve_target`, node readiness, and the namespace snapshot compared | `local-real-cpu` |

Two steps do work the existing workflows leave to the operator. The C2
certification never pulls its image, and
[the runtime package](../serving/local-runtime-package.md#prerequisites-for-a-real-run)
lists pulling the exact digest as a prerequisite the operator provides. And six
release workflows take a single `--values` file -- a second one silently replaces
the first -- which leaves composing one from the committed real values and the two
overlays the image scripts print to whoever runs them. The workflow now does both:
`python -m tools.clean_clone values` layers the three files the way `helm -f`
would.

The evidence label is the most a step's result may be labelled, not what it is.
Nothing here raises a certification level: each step's own workflow writes its own
record, and those records keep their own labels and limitations.

## Cleanup, and what it keeps

`cleanup --confirm`, or `run --confirm-cleanup` once the forward path has passed:

1. refuses a run whose cleanup already passed: it owns nothing further;
2. re-verifies the cluster, and refuses one that is not the cluster this run first
   verified -- by provider, cluster name, and `kube-system` UID;
3. lists the releases in `inferops-release` and refuses if the listing fails --
   a listing that could not be made is never read as an empty one -- or if it
   holds any release other than `inferops`;
4. uninstalls `inferops` if a failed step left it installed;
5. destroys the Terraform prerequisites through the guarded wrapper, which
   refuses again if a release is still there; the namespace cascades and the
   model weights in the claim are reclaimed;
6. waits for the namespace to finish terminating;
7. removes this run's workload scaffolds -- and, only when the `cleanup` command
   itself is given `--include-model-cache`, the workspace model cache, through the
   locked environment's interpreter. `run` does not take that flag.

If the run never verified a cluster, cleanup touches nothing in any cluster:
nothing there is known to be the run's own.

`cluster-survived` then runs whether or not cleanup succeeded, because a failed
cleanup is exactly when that answer matters. It re-verifies the cluster, requires
every node to be Ready, requires every namespace present before the run to still
be there, and requires `inferops-release` to be gone.

When the run never verified a cluster, both steps pass without asking a cluster
anything, and each says so in its output. Their ledger rows still carry the label
`local-real-cpu` as the most they *may* carry; such a run's summary is never
`complete`, because the steps that would have verified a cluster did not pass.

**Kept, by design:** the cluster and every namespace the run did not create; the
images loaded into the cluster's node, which nothing InferOps runs removes on
`docker-desktop`; the API, model seed, and runtime images on the host's engine;
the workspace model cache unless asked; and every record under `.cache/inferops/`
and the ledger, which are the evidence.

## Where things are written

Everything below is ignored by version control and is host state, not evidence
until a record is written from it.

| Path | What |
|---|---|
| `.artifacts/clean-clone/ledger.v1alpha1.json` | the ledger |
| `.artifacts/clean-clone/ledger.<timestamp>.v1alpha1.json` | a ledger `run --restart` moved aside |
| `.artifacts/clean-clone/target-before.txt` | the provider, cluster, context, `kube-system` UID, and server version first verified |
| `.artifacts/clean-clone/namespaces-before.txt` | the namespaces cleanup must leave in place |
| `.artifacts/clean-clone/*.attempt-<milliseconds>` | a snapshot `run --restart` moved aside |
| `.artifacts/clean-clone/api-image-values.yaml`, `model-seed-values.yaml` | the two image overlays |
| `.artifacts/clean-clone/real-values.merged.yaml` | the merged values file |
| `.artifacts/clean-clone/workloads/` | the scaffolded workloads, one directory per attempt |
| `.venv/` | the locked environment `toolchain-sync` installs |
| `.kube/inferops-target.config` | the project-scoped kubeconfig `inferops::resolve_target` writes -- a credential |
| `.cache/inferops/models/` | the acquired model |
| `infra/terraform/environments/local/` | Terraform's plugins and local state |
| `.cache/inferops/` | every record the steps' own workflows write |

`namespaces-before.txt` names every namespace in the operator's cluster, including
ones that belong to unrelated work. Treat it as host state: a record published from
a run should count those namespaces and name only InferOps's.

## What this does not establish

One complete certification run exists:
[the executed record](../proof/environment/v1-s5-001-pr2-clean-clone-run.md), on
`docker-desktop`, on one Windows host, by the author of the change that made the
run. Its own limitations section is the fuller statement; this list is what stays
true regardless of that run.

- **That the journey completes reliably.** One complete run, after two that
  stopped on defects this change fixed, is not a distribution. The tests still
  drive the ordering, consent, ledger, and cleanup rules against stubs, and one
  execution is not exhaustive of what a real host can do to a real step.
- **Anything about `kind`.** The workflow runs on it; nothing has certified it
  there, and a complete run on `kind` would not certify this checklist.
- **The host prerequisites exhaustively.** The step checks tool presence --
  including `sha256sum`, which the model seed build needs -- CPython 3.12, bash 5,
  and the ADR 0001 tier's engine processors, memory, and disk. It does not check
  tool versions against the versions the executed records name, and `kubectl`'s
  skew is left to `inferops::resolve_target`, which refuses it at
  `provider-verification`.
- **That a second engineer can follow it.** The story asks for that where it is
  available; the executed run was made by the change's own author, and no
  independent reviewer has repeated it.
