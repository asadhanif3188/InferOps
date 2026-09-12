# Deleting a serving pod, and proving the model was still there

Status: **executed on the `docker-desktop` provider.** The record is
[`docs/proof/serving/v1-s3-003-pr2-kubernetes-pod-restart.md`](../proof/serving/v1-s3-003-pr2-kubernetes-pod-restart.md).
It establishes this for that provider, on one host, at one moment, and for
nothing else — `kind` has not executed it, and
[ADR 0011](../architecture/decisions/ADR-0011-external-local-cluster-provider-contract.md)
forbids borrowing one provider's answer for the other.

## The question, and the one this replaces

`V1-S3-003` asked whether model artifacts survive a pod restart. The evidence it
produced — [the measured restart and reload](../proof/serving/v1-s3-003-pr1-restart-reload.md)
— answered a narrower question, and said so: a container was stopped on the host
and another was started, and that record states in as many words that it is
**not a pod restart**. Nothing could have made it one at the time. No InferOps
API image was published, and the Terraform-owned model cache claim had never been
filled, so nothing could have scheduled a replacement pod against a surviving
claim.

Both of those exist now. This is the experiment that was missing, and the earlier
record stays exactly as it is: it is honest about what it measured, and rewriting
it to look like this one would be rewriting history.

## What a pod coming back does not establish

A pod always comes back. That is what a Deployment is for, and it is true whether
or not anything survived. So the interesting questions are asked separately:

| Question | How it is answered |
|---|---|
| Was it genuinely replaced? | A different pod **name** and a different pod **UID**, with the same Deployment's ReplicaSet as owner |
| Did anyone notice? | The serving Deployment's ready replica count, sampled across the window, observed at zero and then above zero |
| Is it the same claim? | The same claim name, the same `boundVolumeName`, and the same volume the claim itself reports being bound to |
| Are they the same bytes? | The same byte count and the same SHA-256, computed inside the cluster, **and** the release's own `verify-model` init container exiting zero |
| Is it the same *file*? | The same **inode** and the same **modification time** |
| Did anything re-acquire the model? | No acquisition Job exists across the replacement, and the Job identity does not change |
| Does it still work? | One real completion before the deletion, and one after, from the real adapter with runtime-derived token counts |

The inode and the modification time are the row that carries the most weight, and
it is worth saying why. A re-acquired artifact has the **same size and the same
digest** as the one it replaced — that is what "acquire the pinned artifact"
means, so neither of those can tell the two cases apart. What an acquisition
cannot reproduce is the file's identity: it writes a temporary file beside the
artifact and renames it over the top, which allocates a new inode and stamps a
new modification time. Without that comparison, a release that quietly re-fetched
1.83 GB on every pod replacement would look identical, from outside, to one that
preserved it.

## What runs, and what owns each piece

| Piece | What it owns |
|---|---|
| [`deploy/serving/experiments/kubernetes-pod-restart.v1.json`](../../deploy/serving/experiments/kubernetes-pod-restart.v1.json) | Every target, budget, assertion, evidence location, and limitation |
| [`scripts/environment/kubernetes-pod-restart.sh`](../../scripts/environment/kubernetes-pod-restart.sh) | Every `terraform`, `helm`, and `kubectl` invocation, the forward, the readiness sampling, and the teardown |
| [`tools/kubernetes_pod_restart`](../../tools/kubernetes_pod_restart) | Reading the descriptor, holding what was collected to it, the two calls to the recovered release, and the record |

Nothing in the Python operates a cluster. The guard that establishes which
cluster is being acted on already lives in
[`lib.sh`](../../scripts/environment/lib.sh) beside every other environment
script, and a second implementation of it in another language would be a second
guard.

The descriptor is checked against
[the Kubernetes real-inference certification](../../deploy/serving/certification/k8s-real-inference.v1.json)
for **equality** on the providers, the release, the request, and the eight
budgets the two share. Both workflows install the same chart as the same release
into the same namespace on the same cluster; a second set of numbers describing
that would be a second release waiting to be discovered.

## The stages

```text
baseline    install the real profile, wait for both rollouts, run the release's
            own in-cluster connection test, read the serving pod's identity and
            the artifact's size, digest, inode and modification time, and take
            one real completion through the API Service

deletion    delete exactly one pod, by the name the cluster gave it

replacement wait until the replacement pod -- the serving-runtime pod that is not
            the deleted one -- reports Ready itself, sampling the Deployment's
            ready replica count throughout, then wait for the rollout

recovery    read the replacement's identity and the artifact's four facts again,
            and take one real completion

cleanup     helm uninstall, then check for residue carrying the release's
            instance label
```

## What the one delete touches

One pod, addressed by name. A pod is not a declared object — no tool in
[the ownership inventory](../architecture/resource-ownership.md) owns one; they
are `derived`, created by a controller from an object that *is* owned. The delete
therefore changes no Deployment, no claim, no release revision, nothing
cluster-scoped, and nothing in another namespace, and the descriptor declares
each of those separately rather than leaving a reader to infer them.

The release revision is compared before and after, so "a pod deletion is not a
release change" is asserted rather than assumed.

## Running it

The provider is explicit and has no default, and the values file is required: the
chart's shipped defaults select no serving profile and are refused on purpose.

```bash
INFEROPS_PROVIDER=docker-desktop \
  scripts/environment/kubernetes-pod-restart.sh check

INFEROPS_PROVIDER=docker-desktop \
  scripts/environment/kubernetes-pod-restart.sh run \
    --values path/to/real-values.yaml \
    --confirm-real-kubernetes
```

`check` reads committed files and contacts nothing. `run` applies the Terraform
prerequisites, installs a release, loads a real model, deletes a running pod,
sends real inference requests, and uninstalls the release. It never removes the
namespace, never removes the claim, and never touches the cluster: reclaiming the
prerequisites is `scripts/environment/terraform-prerequisites.sh destroy
--confirm` and nothing else.

On failure the release is left in place, diagnostics are written to
`.artifacts/kubernetes-pod-restart/`, and the command to remove the release is
printed. The evidence of a failure is not torn down.

## Limitations

These are the descriptor's own `limitations`, and a test asserts that every one
of them appears here:

- The evidence is local real Kubernetes on a single-node cluster belonging to one
  explicitly selected provider, and implies nothing about another provider, a
  multi-node cluster, a node loss, or a claim on network-attached storage.
- One pod was deleted, once. The recovery figures describe that one replacement
  on one host at one moment and are not a restart benchmark, a service-level
  objective, or an availability figure.
- The disruption is a deleted pod. It says nothing about a node that goes away, a
  claim that fails to reattach, a volume that is corrupted, or a runtime that
  starts and answers wrongly.
- The serving runtime is one replica, so the replacement window is an outage for
  any caller reaching that Service. Nothing here measures that outage from a
  caller's side and nothing here claims high availability.
- The artifact is compared by the byte count and SHA-256 the release was rendered
  with, read inside the cluster. That establishes the bytes the runtime loaded,
  not that the claim's underlying storage is durable across a host failure or a
  cluster reset.
- Model acquisition is proven not to repeat for a pod replacement because the
  acquisition hook runs on install and upgrade and a pod deletion is neither.
  Nothing here says what an upgrade would re-acquire.
