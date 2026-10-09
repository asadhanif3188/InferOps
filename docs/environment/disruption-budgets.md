# The disruption budgets, and what they do not bound

Status: **the chart renders the budgets, and tests hold the render at evidence level C0. No eviction was requested, and no node was drained. So no statement on this page about what a budget does was observed in a cluster.**

> **Note, 2026-10-09 (`V2-S4-005-PR2`).** A release that renders the two budgets was installed once, on the `docker-desktop` provider, for one reading of the Service endpoints. [The transcript of that run](../proof/environment/v2-s4-005-pr2-service-endpoint-state-run-1-transcript.txt) lists both budget objects, each with `minAvailable` 1 and one allowed disruption, while two pods of each tier were Ready. That is one listing. No eviction was requested in that run, so it establishes nothing about what a budget refuses.

Since chart `0.6.0`, a tier of two or more replicas renders one
PodDisruptionBudget. This page states the rule, what Kubernetes documents that a
budget bounds, and what a budget does not bound.

**A budget does not protect a pod from a direct deletion.** That is the one
sentence of this page that a reader must keep. A pod deletion is tested by
deleting a pod under a caller, in an experiment of its own. A budget is not the
mechanism of that experiment, and a budget is not evidence for its result.

## The rule

| Tier | Rendered when | The budget |
|---|---|---|
| Platform API | `api.replicaCount` is 2 or more | `minAvailable: 1`, over the pods that the API Deployment selects |
| Serving runtime | The profile is `real`, and `runtime.replicaCount` is 2 or more | `minAvailable: 1`, over the pods that the runtime Deployment selects |

- **One replica renders no budget.** A budget of one available pod over one pod
  would refuse every eviction of it, and `kubectl drain` then waits on that pod.
  So a tier of one replica is not bounded for an eviction. This is the case of
  the chart's defaults, of both committed renders, and of the runtime tier of the
  [single-runtime baseline profile](single-runtime-baseline-profile.md).
- **`minAvailable` is 1 at every count from 2.** It is a whole number and not a
  percentage. At N replicas that are all available, the budget admits N-1
  evictions: one at two replicas, and fifteen at sixteen.
- **No value sets it.** The values contract holds no member for a budget, and the
  schema refuses one. So no values file can raise `minAvailable` to the replica
  count, and none can turn a budget off. The replica count of a generated release
  is not hand-written: the EnvironmentBinding owns the API count, and the
  workload contract owns the runtime count.
- **The selector is the Deployment's selector.** The budget counts the pods that
  its Deployment counts. It does not select the collector, the acquisition hook,
  or the `helm test` pod.
- **The budget states no `unhealthyPodEvictionPolicy`.** The Kubernetes default,
  `IfHealthyBudget`, applies. Kubernetes documents that under it a pod that runs
  and is not Ready can be evicted only while the budget is met. So when no pod of
  a tier is Ready, for example while both runtime pods load the model, no pod of
  that tier can be evicted, and a drain waits. Kubernetes documents the other
  setting, `AlwaysAllow`, which admits the eviction of such a pod. No accepted
  record decides between them, so the chart states neither.
- **The collector has no budget.** It has one replica.

The [desired-state release](git-desired-state.md) declares two replicas for each
tier, so its render holds both budgets. The ownership inventory holds one row
for them, `workload-disruption-budget`, with the status `planned`: the chart
renders the objects, and no cluster has held one.

## What a budget bounds

Kubernetes documents that a PodDisruptionBudget limits voluntary disruptions that
go through the eviction API. A request to that API is refused when the eviction
would leave fewer available pods than the budget states. `kubectl drain` evicts
pods through that API, unless it is told to delete them.

Kubernetes counts a pod as available for a budget when the pod is Ready. A
runtime pod is Ready only after it has loaded the model. So at two replicas,
during the load of a replacement runtime pod, the runtime tier has one available
pod, and the budget refuses an eviction of that pod.

**None of this was observed.** These sentences state what Kubernetes documents
for the objects that the chart renders.

## Where a budget makes a drain wait

**A budget does not create a place for the replacement pod.** `kubectl drain`
marks the node unschedulable first. After the first eviction of a tier, the
second eviction is refused until a replacement pod is Ready. A replacement can
become Ready only on another node that can run it.

- **On a cluster with one node, there is no other node.** The replacement stays
  pending, the budget refuses the second eviction at each retry, and the drain
  does not end by itself. This is so for the API tier and for the runtime tier.
  The one recorded run with two replicas of each tier was on a cluster with one
  node.
- **The runtime tier has a second limit.** Both runtime pods mount one model cache
  claim, which the prerequisite layer creates as `ReadWriteOnce`. Kubernetes
  documents that such a claim cannot be mounted by pods on two nodes. So while
  one runtime pod holds the claim on the drained node, a replacement cannot
  mount it on another node. With that claim, a drain of the node that holds the
  runtime pods does not end by itself at any replica count.

Without a budget, such a drain ends, and the tier has no pod until the node
takes pods again. With a budget, the drain waits, and one pod of the tier keeps
running on the drained node. An operator who must empty the node then removes
the last pod by a deletion, which no budget bounds. **So on the one environment
that this repository has used, a budget changes what a drain does. It does not
make a drain leave a caller served.** None of this was observed.

## What a budget does not bound

- **A direct pod deletion.** `kubectl delete pod`, and any other delete call to
  the pod, does not go through the eviction API. Kubernetes documents that a
  budget does not prevent it. Both pods of a tier can be deleted at once while
  the budget exists.
- **A Deployment's rolling update.** Kubernetes documents that a workload
  controller is not limited by a budget when it rolls pods, and that a pod that
  is unavailable during a rollout counts against the budget. `api.rollout` and
  `runtime.rollout` hold the rollout bounds. The runtime's bounds allow one
  runtime pod to be unavailable during a rollout, whether or not the runtime's
  budget exists. At two runtime replicas, the budget then admits no eviction
  until the replacement is Ready.
- **An involuntary disruption.** A node that fails, and a pod that the kubelet
  evicts under node pressure, are not requests to the eviction API. Kubernetes
  documents that a budget cannot prevent such a disruption, and that it counts
  against the budget.
- **A pod that is not Ready.** A container that is killed for its memory limit,
  and a pod that fails its readiness probe, are not requests to the eviction API
  either. Such a pod is not counted as available.
- **The loss of a node.** The one recorded run with two runtime replicas had both
  runtime pods on one node. Two pods of a tier on one node are lost with that
  node, and a budget does not place pods on two nodes.
- **A caller's experience.** A budget states how many pods must stay available.
  It does not state that a request succeeds while one pod is evicted. An
  eviction ends a pod as a deletion does, and a request in flight to that pod is
  not protected by the budget.

So a budget is not evidence of resilience to a pod loss. It does not show that a
caller is served when a pod of either tier is deleted, and no statement of this
repository about that case may cite it.

## Under the Argo CD Application

**The project must admit the kind before the release renders it.** The project of
the workload Application admits a list of namespaced kinds. Since this change it
admits PodDisruptionBudget, as
[the Application page](argocd-application.md#the-project) states, and
[ADR 0019](../architecture/decisions/ADR-0019-argocd-application-and-sync-policy.md)
carries a dated amendment. The project is not desired state: an operator applies
it. On a cluster that holds the earlier project, a sync of a revision that
renders a budget is expected to fail as a whole, so the Application would apply
no later revision either, until the project is applied again. That was not
observed. The one cluster that was asked when the kind was added,
`docker-desktop` on 2026-10-09, listed no `argocd` namespace.

**A budget that leaves the render stays in the cluster.** The Application's sync
policy does not prune. When a tier goes from two replicas to one, the chart
stops rendering that tier's budget, and Helm removes it on an upgrade. The
Application does not remove it. The budget then stays over one pod, which is the
object that the chart does not render: it refuses every eviction of that pod. A
person deletes it. The Application is expected to report the object as one to
prune, and so not to report `Synced` until then. This was not observed.

**How Argo CD reports a budget's health.** The pinned Argo CD version, `v3.5.3`,
holds a health check for the kind. Its source, read at that tag on 2026-10-09,
reports a budget as healthy when its condition has the reason
`InsufficientPods`, as degraded for another condition that is false, and as
progressing while the budget has no condition. So a tier with one Ready pod of
two is not expected to make the Application degraded through its budget. This is
a reading of source text. No Application reported on a budget.

The removal step of the Application procedure asks for budgets too, when it
looks for objects that a removal left behind.

## What changed for an existing release

- A release with one replica for each tier renders the same objects under chart
  `0.6.0` as under `0.5.0`. Each object carries the new chart label, so every
  pod template changes. Kubernetes documents that a changed pod template starts a
  rollout of its Deployment. No upgrade was run.
- A release with two replicas for a tier renders one more object for that tier.
- No chart value changed, and the values schema is the same.

No release was upgraded to chart `0.6.0`.

## Where the budgets are checked

[`tests/architecture/test_helm_chart.py`](../../tests/architecture/test_helm_chart.py)
renders the chart with Helm, where Helm is installed, and holds:

- which replica counts render a budget, for each tier and for the `mock` profile;
- that a budget is `minAvailable: 1` over its Deployment's selector, and nothing
  else, at 2, 3, and 16 replicas;
- that each pod template of the release is selected by its own budget or by none;
- that no value configures a budget, and that the schema refuses one;
- that a budget leaves both rollout strategies as the values state them, and
  that a second replica changes one line of the render outside the budget;
- that the desired-state release renders both budgets, and that the project
  admits exactly the kinds of that render.

The workflow renders the real profile with two replicas for each tier and
validates the render against the pinned Kubernetes schemas, so both budgets are
held to the `policy/v1` schema of the pinned version.

A render is a file. These checks do not establish that the API server admits the
objects, that an eviction is refused, or anything that a caller observes.
