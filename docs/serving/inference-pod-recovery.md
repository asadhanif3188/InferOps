# Losing the inference pod while callers are waiting

Sprint 3 deleted a serving pod and proved that the model artifact was still there
afterwards. It sent one request before and one after, and it said plainly what it had
not done: *nothing here measures that outage from a caller's side.*
[That record](../proof/serving/v1-s3-003-pr2-kubernetes-pod-restart.md) is unchanged
and still correct. This workflow measures the thing it declined to.

## The question

While the committed load profile is mid-flight, one serving runtime pod is deleted.
What does a caller see, what does an operator see, how long until a real completion
comes back, and which of the signals this platform emits noticed?

Six things are measured, and each of them is measured from one place rather than
inferred from another:

| Measured | Read from |
|---|---|
| Detection | the first request after the delete that did not come back served, and the readiness samples |
| Request success and failure | the raw load record sets, sliced by dispatch against the moment the delete was issued |
| Latency impact | the latency of successes before and after, within the phase the disruption landed in |
| Replacement | the replacement pod's own name, uid, owner, and `Ready` condition |
| Model reload | the replacement pod from the workflow's first sighting of it to its own `Ready` condition |
| Readiness recovery | the number of endpoints the runtime Service is willing to send traffic to |

## What runs, and what owns each piece

| Piece | Path | Owns |
|---|---|---|
| Descriptor | [`deploy/serving/experiments/inference-pod-recovery.v1.json`](../../deploy/serving/experiments/inference-pod-recovery.v1.json) | What is sent, what is read, what the disruption is, and what may not be claimed |
| Load profile | [`deploy/serving/load/llm-load-profile.v1.json`](../../deploy/serving/load/llm-load-profile.v1.json) | The traffic, pinned by digest from the descriptor |
| Operating script | [`scripts/environment/inference-pod-recovery.sh`](../../scripts/environment/inference-pod-recovery.sh) | Every contact with the cluster, and the one delete |
| Record tool | [`tools/inference_pod_recovery`](../../tools/inference_pod_recovery) | Every assertion, and the labelled record. Contacts nothing but one loopback collector |
| Offline suite | [`tests/architecture/test_inference_pod_recovery.py`](../../tests/architecture/test_inference_pod_recovery.py) | Reading the safety argument off the script, and the record's behaviour on inputs no run produced |
| Report template | [`docs/proof/serving/TEMPLATE-inference-pod-recovery.md`](../proof/serving/TEMPLATE-inference-pod-recovery.md) | The shape a published result takes, registered before a run |

## The stages

```text
prerequisites -> install -> idle baseline -> run 1 starts
              -> delete one pod -> watch the replacement
              -> run 1 finishes -> settle -> run 2 (after the recovery)
              -> settle -> collector -> uninstall -> record
```

The delete is issued a registered number of milliseconds after the first run starts,
and **which phase it landed in is a result rather than an arrangement**: the record
reads the phase off the raw set afterwards and a check refuses a run whose disruption
landed somewhere the descriptor did not register.

## Why the load runs twice

A refused request comes back far faster than a served one. One run of the committed
profile therefore spends its whole remaining request budget within seconds of losing
the pod — every level's ceiling is a request count, and refusals fill it — and ends
before anything is ready again. A single run cannot have an "after".

So there are two, both the same profile at the same concurrency levels. The first is
disrupted and measures what the loss cost callers. The second starts once the
replacement reports Ready and measures what callers get back, which is what makes the
before and after figures comparable at all.

The cost of that choice is stated rather than hidden: the requests after the recovery
are a second run's rather than the same run's, and where the recovery instant comes
from the second run, the interval from the deletion includes this workflow's own
readiness polling and the load generator's start-up. The record publishes the interval
from the replacement being ready separately for exactly that reason, and names which
run the recovery was seen in.

## What the one delete touches

One pod, addressed by the name the cluster gave it, with `--wait=false`, no label
selector, and no `--all`. The pod is located by counting rather than by indexing, so a
release that somehow has two serving pods refuses rather than choosing one, and the
name is checked against the shape a Kubernetes name may have before it reaches the
delete. No Deployment, no claim, no release revision, no cluster-scoped object, and
nothing in another namespace.

Between the delete and the uninstall that ends the run, the workflow issues no mutating
command at all. That is what lets the record say the Deployment controller did the
recovering rather than a person, and it is read off the script by a test rather than
promised here.

## Where each interval begins and ends

Every one of them begins at the moment the delete was issued, stamped by the operating
script on the host's own clock — the same clock the load generator reads for its run
origin, which is what lets a request be placed against the disruption at all.

- **Replacement** ends when the replacement pod reports **its own** `Ready` condition.
  Not the Deployment's aggregate, which still counts the deleted pod inside its
  termination grace period.
- **The caller-visible outage** begins at the completion of the first request after the
  delete that did **not** come back served, and ends at the completion of the first one
  dispatched from then on that did. Not at the delete — the pod that is going away goes
  on serving for a while, and the first execution of this experiment measured exactly
  that. Requests it still served are kept in a window of their own, `servedWhileDraining`,
  rather than folded into either side.
- **Neither end is a forward accepting a connection**, which is an interval that ends
  before a request is even sent.

The first two of those were published the other way round in an earlier draft of the
Sprint 3 experiment and were corrected by an independent review of that change. The
third was got wrong *here*, by this workflow's own first execution: it stamped the
outage from the delete, published two negative intervals, and passed every check it
had. The check `no-published-interval-is-negative` exists because of that, and refuses
any interval a reader would take as a duration and that comes out below zero.

The two instants the *cluster* reports for the replacement container are kept as the
strings it emitted and never subtracted from anything: the node is a container whose
clock this record has no reason to assume is the host's.

## Running it

```sh
# Validates the descriptor. Contacts nothing, installs nothing, deletes nothing.
scripts/environment/inference-pod-recovery.sh check

# The real run. Needs an authorized, verified cluster and a host values file.
INFEROPS_PROVIDER=docker-desktop \
  scripts/environment/inference-pod-recovery.sh run \
    --values PATH --confirm-real-kubernetes
```

The run writes into `.cache/inferops/experiments/inference-pod-recovery/`, which is
never overwritten: an earlier run's evidence is either already promoted or still
wanted, and the script cannot tell which. Promoting a record means copying
`record/` into `docs/proof/serving/` under a `v1-s4-00N-prM-` prefix, unedited, after
which

```sh
python -m tools.inference_pod_recovery verify --dir docs/proof/serving --prefix v1-s4-006-pr1-
```

regenerates it from its committed inputs and compares.

## Limitations

- One provider, one host, one single-replica release, one model, one runtime build, one load profile, and one pod lost once. Nothing here is portable to another provider, host, replica count, workload mix, or runtime configuration, and nothing here is an availability figure, a service-level objective, or an error budget.
- The serving runtime runs one replica, so every unsuccessful request recorded here is the consequence of that choice rather than of Kubernetes. A second replica would have changed the result and this experiment says nothing about what it would have changed it to.
- Traffic is sent in two runs of the same profile rather than one continuous stream. The first is disrupted and the second starts once the replacement reports Ready, so the requests after the recovery are a second run's rather than the same run's, and the interval from the deletion to a served completion includes this workflow's own readiness polling and the load generator's start-up wherever the recovery was seen in the second run.
- Load reaches the API through a loopback port-forward to one pod, held open across the disruption. The forward is to the platform API, which is not the tier being deleted, so what the load records is the API's answer while its upstream was gone rather than a connection that died.
- A deleted pod is not a lost node. Nothing here says anything about a node that goes away, a claim that fails to reattach, a corrupted volume, or a runtime that starts and answers wrongly.
- The collector scrapes every 30 seconds, so a telemetry series locates the disruption to within a scrape and a rule evaluation, never to the request. No figure published here is derived from a telemetry series.
- That the model artifact survives a pod replacement is not re-proven here. It was established by V1-S3-003-PR2 by comparing the artifact's inode and modification time either side, and this experiment records only that no acquisition Job appeared and that the replacement served real completions.
- Other workloads on the same node and virtual machine are not controlled, and the host's file cache is in whatever state the preceding run left it.

None of the figures this workflow produces is a benchmark of Kubernetes, the model, the
runtime, or any provider.
[ADR 0013](../architecture/decisions/ADR-0013-bounded-local-performance-observations.md)
is what permits publishing them at all, and what they may not be presented as.
