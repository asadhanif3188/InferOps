# The disruption budgets, and what they do not bound

Status: **the chart renders the budgets, and tests hold the render at evidence level C0. No release that renders a budget was installed, no eviction was requested, and no node was drained. So nothing on this page was observed in a cluster.**

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
  would refuse every eviction of it, and Kubernetes documents that a node drain
  then waits on that pod. So a tier of one replica is not bounded for an
  eviction. This is the case of the chart's defaults, of both committed renders,
  and of the runtime tier of the
  [single-runtime baseline profile](single-runtime-baseline-profile.md).
- **`minAvailable` is 1 at every count from 2.** It is a whole number and not a
  percentage. It is below the replica count at every such count, so the budget
  admits one eviction while every pod of the tier is available.
- **No value sets it.** The values contract holds no member for a budget, and the
  schema refuses one. So no values file can raise `minAvailable` to the replica
  count, and none can turn a budget off. The replica count of a generated release
  is not hand-written: the EnvironmentBinding owns the API count, and the
  workload contract owns the runtime count.
- **The selector is the Deployment's selector.** The budget counts the pods that
  its Deployment counts. It does not select the collector, the acquisition hook,
  or the `helm test` pod.
- **The budget states no `unhealthyPodEvictionPolicy`.** The Kubernetes default
  applies to a pod that runs and is not Ready. That policy is not decided here.
- **The collector has no budget.** It has one replica.

The [desired-state release](git-desired-state.md) declares two replicas for each
tier, so its render holds both budgets. The ownership inventory holds one row
for them, `workload-disruption-budget`, with the status `planned`: the chart
renders the objects, and no cluster has held one.

## What a budget bounds

Kubernetes documents that a PodDisruptionBudget limits voluntary disruptions that
go through the eviction API. A request to that API is refused when the eviction
would leave fewer available pods than the budget states. `kubectl drain` evicts
pods through that API, so a drain of a node that holds both pods of a tier
evicts one, and waits for its replacement to be available before it evicts the
other.

Kubernetes counts a pod as available for a budget when the pod is Ready. A
runtime pod is Ready only after it has loaded the model. So during the load of a
replacement runtime pod, the runtime tier has one available pod, and the budget
refuses an eviction of that pod.

**None of this was observed.** These sentences state what Kubernetes documents
for the objects that the chart renders.

## What a budget does not bound

- **A direct pod deletion.** `kubectl delete pod`, and any other delete call to
  the pod, does not go through the eviction API. Kubernetes documents that a
  budget does not prevent it. Both pods of a tier can be deleted at once while
  the budget exists.
- **A Deployment's rolling update.** Kubernetes documents that a workload
  controller is not limited by a budget when it rolls pods. `api.rollout` and
  `runtime.rollout` hold those bounds. The runtime's bounds allow one runtime pod
  to be unavailable during a rollout, whether or not the runtime's budget exists.
- **An involuntary disruption.** A node that fails, a pod that the kubelet evicts
  under node pressure, a container that is killed for its memory limit, and a
  pod that fails its own probes are not requests to the eviction API. Kubernetes
  documents that such a disruption still counts against the budget, and that the
  budget cannot prevent it.
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

## The Argo CD project

The project of the workload Application admits a list of namespaced kinds. Since
this change it admits PodDisruptionBudget, as
[the Application page](argocd-application.md#the-project) states, and
[ADR 0019](../architecture/decisions/ADR-0019-argocd-application-and-sync-policy.md)
carries a dated amendment. The project is not desired state: an operator applies
it. A cluster that holds the earlier project does not apply a revision that
renders a budget until the project is applied again. The removal step of the
Application procedure now asks for budgets too, when it looks for objects that a
removal left behind.

## What changed for an existing release

- A release with one replica for each tier renders the same objects under chart
  `0.6.0` as under `0.5.0`. Each object carries the new chart label, so every
  pod template changes, and an upgrade replaces the pods.
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
- that a budget changes no member of a Deployment;
- that the desired-state release renders both budgets, and that the project
  admits exactly the kinds of that render.

The workflow renders the real profile with two replicas for each tier and
validates the render against the pinned Kubernetes schemas, so both budgets are
held to the `policy/v1` schema of the pinned version.

A render is a file. These checks do not establish that the API server admits the
objects, that an eviction is refused, or anything that a caller observes.
