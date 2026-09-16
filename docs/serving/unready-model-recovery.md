# A model that does not become ready, on purpose

[`ADR 0010` D8](../architecture/decisions/ADR-0010-inference-api-compatibility-surface.md)
publishes nine rows of error mapping and marks exactly one of them **observed** —
`model-not-ready`, seen once, incidentally, in a control-plane line during the Sprint 0
feasibility trial. The mock adapter reproduces the shape as `MockScenario.MODEL_NOT_READY`,
and [the mock and real boundary](mock-and-real-boundary.md) states as its rule that
*a mock serving path may never be used to certify real local runtime behaviour, however
faithfully it reproduces the API surface*. So the one observed row of the
accepted mapping rests on an incident nobody arranged and a fixture that certifies
nothing. This experiment arranges it.

## The question

**What does a caller see, what does an operator see, does the platform destroy itself
while it waits, and does correcting one value get the release back — when the runtime
process is healthy and the model behind it is not ready?** It is a different question
from `V1-S3-008`'s, whose artifact mismatch is refused by the `verify-model` init
container *before* the runtime container is ever started, and a different one from
`V1-S4-006`'s, which deleted a pod that was healthy and ready. Seven things are
measured, and each of them is measured from one place rather than inferred from
another:

| Measured | Read from |
|---|---|
| Model readiness | the serving runtime's own `/health`, asked through a forward to its pod |
| Platform readiness | the API's `/health/ready`, and the API pod's own `Ready` condition |
| What a caller is told | the canonical code, condition, and retryable flag in the API's own error body |
| Whether liveness destroyed anything | the serving runtime container's `restartCount`, sampled throughout |
| Whether the process was alive at all | the instant the runtime first answered on its own port, and every answer after it |
| Whether the artifact was ever in question | the `verify-model` init container's exit code, in both pods |
| Recovery | a real completion served after the fix, with its output token count |

## What runs, and what owns each piece

| Piece | Path | Owns |
|---|---|---|
| Descriptor | [`deploy/serving/experiments/unready-model-recovery.v1.json`](../../deploy/serving/experiments/unready-model-recovery.v1.json) | What is asked, what is read, what the disruption is, what was rejected, and what may not be claimed |
| Values overlay | [`deploy/serving/experiments/unready-model-values.v1.yaml`](../../deploy/serving/experiments/unready-model-values.v1.yaml) | The whole disruption, pinned by digest from the descriptor |
| Operating script | [`scripts/environment/unready-model-recovery.sh`](../../scripts/environment/unready-model-recovery.sh) | Every contact with the cluster, and the two mutating commands that follow the install |
| Record tool | [`tools/unready_model_recovery`](../../tools/unready_model_recovery) | Every assertion, and the labelled record. Contacts nothing but one loopback collector |
| Offline suite | [`tests/architecture/test_unready_model_recovery.py`](../../tests/architecture/test_unready_model_recovery.py) | Reading the safety argument off the script, and the record's behaviour on inputs no run produced |
| Report template | [`docs/proof/serving/TEMPLATE-unready-model-recovery.md`](../proof/serving/TEMPLATE-unready-model-recovery.md) | The shape a published result takes, registered before a run |

## The disruption, and the four mechanisms that were rejected

The overlay sets the serving runtime container's processor request and limit to `10m`
and **nothing else**. `10m` is the floor rather than a choice: a container runtime
enforces a quota of at most one millisecond in a hundred, so a smaller number in a
values file buys nothing. No model value, no image, no probe, no profile. That is what makes
this a runtime fault rather than an artifact fault: the chart validates, the
`verify-model` init container reads the same bytes it always reads and compares them
against the same pinned byte count and SHA-256, and `llama-server` starts, binds its
port, begins loading the model, and does not finish.

Four other mechanisms were tried against the pinned image and the cached artifact
before this one was chosen, and each is recorded in the descriptor with the reason it
was rejected:

- **An artifact size or hash mismatch.** This is `V1-S3-008`'s mechanism. The init
  container refuses it and the runtime container is never started, so it is an
  install-time refusal and says nothing about a running process.
- **An absent artifact, or a `<repository>/<revision>` subdirectory with nothing in
  it.** The init container reads the *same* derived container path the runtime is
  given — one expression, by design, so that the file that was verified and the file
  that is loaded cannot be two files — so a missing file fails the init container
  rather than the model load.
- **A well-sized file that is not a GGUF.** Measured directly: `llama-server` logs
  `exiting due to model loading error` and **exits 1**. That is container-restart
  churn, not a healthy process serving an unready model, and it would make the
  liveness question unanswerable.
- **A context size at the schema maximum.** Rejected on two counts. A large integer
  supplied from a values *file* renders in scientific notation, which the API refuses
  at start-up with `INFEROPS_LLAMA_SERVER_CONTEXT_SIZE: must be a whole number written
  in decimal` and which `llama-server` reads as a context of `1` and aborts on; and
  even rendered correctly, the allocation it asks for does not hold the process in a
  stable loading state.

A fifth — pointing `runtime.healthPath` at a path the runtime does not serve — was
rejected without being run: the model would be ready and the probe would be wrong,
which proves nothing about an unready model.

## The stages

```text
check -> terraform prerequisites -> install WITH the overlay -> wait for the container
      -> wait for the runtime's own socket -> forwards (to pods) -> idle baseline
      -> hold unready: sample readiness, ask four surfaces, every round
      -> capture diagnostics -> upgrade WITHOUT the overlay -> wait for ready
      -> re-open forwards -> ask the same four surfaces -> telemetry -> uninstall
      -> record
```

`rollout status` is used for exactly one workload, the collector. A rollout completes
when a pod is *ready*, and neither of the two tiers this experiment misconfigures will
be — so what is waited for instead is the container being reported running, and then
the runtime answering anything at all on its own port. **That second wait is evidence
rather than plumbing**: the chart's liveness probe is a TCP connect, so the instant the
socket opens is the instant liveness starts being satisfied.

## Why the forwards address pods and not Services

A release whose model is not ready has **no ready endpoint** on the serving runtime
Service *or* on the platform API Service. The runtime's readiness probe is an HTTP GET
against `/health`, which answers 503 for the whole of a model load; the API's readiness
path is the conjunction of the API accepting work and its adapter reporting itself able,
and the second half is false for the same reason. So both Services drop their only
address, and a forward to either would measure kube-proxy refusing a connection rather
than a workload answering.

This has a consequence the experiment records rather than works around: **a caller
arriving through the API Service in this state meets no endpoint at all**, which is a
different observation from the one measured here and is stated rather than measured.

## Why an intervention is expected

`V1-S4-006` registered `recoveryInterventionExpected: false` and was right to: a
deleted pod is replaced by the Deployment controller and nobody has to act. This
experiment registers `true`, and is right to for the opposite reason. **A model that
cannot load is not a state any controller reverses.** Nothing in Kubernetes notices
that a container has been given too little processor to finish a load; the startup
probe eventually kills it and starts the same load again, forever. The fix is a person
changing a value, and a descriptor claiming otherwise would be claiming a self-healing
property this platform does not have.

The script therefore issues exactly two mutating commands after the install — the
corrected upgrade and the uninstall — and records the first as the one intervention.
A test reads the script to establish that there are no others.

## Where each interval begins and ends

**The recovery is measured on the pod that was corrected, and only on that one.** A
rolling update keeps the predecessor until the replacement is ready, and the
predecessor here is a pod whose starved load can finish while the replacement's has
not started. A first execution of this experiment waited for *any* ready serving
runtime pod, stamped the recovery from the misconfigured one, and let it serve the
completions that were supposed to establish the fix. The workflow now waits for the
tier to have exactly one pod that is not terminating, for that pod to be a different
pod from the one that was starved, and for it to report itself Ready; and the record
carries a check that refuses a run whose recovered pod carries the misconfigured one's
identity.


- **The unready window** begins when the runtime has answered on its own port and the
  idle baseline is over, and ends when the registered window has elapsed. Every claim
  about readiness staying false is a claim about every sample inside it.
- **The recovery** is stamped from the moment the corrected upgrade was issued to the
  completion of the first request that came back **served with output tokens**. Not
  from a rollout command returning, not from a forward accepting a connection, and not
  from a 200 with nothing in it.
- **The restart count** is read at every sample, and it means something only because
  the window fits inside the chart's own `runtime.probes.startup.budgetMs`. Past that
  budget the kubelet restarts the container and the count stops describing the model.
  The record publishes the window as a share of that budget so the bound travels with
  the figure.

No interval a reader would take as a duration is allowed to be negative. That check
exists because an independent review of `V1-S3-003-PR2` found two published figures
stamped from the wrong end, and the first execution of `V1-S4-006` repeated the shape.

## Running it

```sh
# Reads the descriptor and the overlay. Contacts nothing, installs nothing.
scripts/environment/unready-model-recovery.sh check

# The real run. It installs a release that is deliberately misconfigured, loads a real
# model, sends real requests, upgrades the release, and removes it.
INFEROPS_PROVIDER=docker-desktop \
  scripts/environment/unready-model-recovery.sh run \
  --values charts/inferops-llm/ci/real-values.yaml \
  --values <host model seed overlay> \
  --values <host API image overlay> \
  --confirm-real-kubernetes
```

The values overlay that carries the disruption is **not** passed by the operator. The
script appends it itself, from the committed path the descriptor pins by digest, so
that the file whose digest the record publishes is the file that was installed.

Everything a run writes goes under `.cache/inferops/experiments/unready-model-recovery/`,
which version control ignores. A run directory is never overwritten. Promoting a result
means copying the six inputs and the record into `docs/proof/serving/` under a story
prefix, after which anyone can regenerate the record from them without a cluster:

```sh
python -m tools.unready_model_recovery verify \
  --dir docs/proof/serving --prefix <prefix->
```

which rebuilds the record from its committed inputs and compares the two byte for byte.

## Limitations

- One provider, one host, one single-replica release, one model, one runtime build, one chart, and one misconfiguration applied once. Nothing here is portable to another provider, host, replica count, model, or runtime configuration, and nothing here is an availability figure, a service-level objective, an error budget, or a recovery-time objective.
- The model did not become ready within the registered observation window, and that is not the same as proving it never would. The load was starved rather than failed. A first execution held the release unready for 307 673 ms and then observed the starved load complete, so the window is registered at 180 s against a starved load of roughly twice that, and `10m` is the smallest quota a container runtime will enforce rather than the smallest number this experiment could have written. Every restart count published here is bounded the same way, by the runtime's own startup probe budget, after which the kubelet restarts the container into the same load.
- The disruption is a processor limit and not a corrupt artifact, a wrong revision, or an unloadable file. Those are refused earlier -- by chart validation or by the `verify-model` init container -- and this experiment says nothing about what the runtime process would do if it reached one of them, beyond the direct measurement recorded in the descriptor's own list of rejected mechanisms.
- Both request surfaces are reached through a loopback forward to a pod rather than to a Service, because a release whose model is not ready has no ready endpoint on either Service. What the probes record is therefore what each workload answers, not what a caller arriving through a Service would have met -- and a caller arriving through the API Service in this state would have met no endpoint at all, which is a different observation and is stated rather than measured here.
- The recovery is an operator changing a value and issuing an upgrade. Nothing here says a controller would have reversed it, and nothing here measures how long a person takes to notice.
- The collector scrapes every 30 seconds, so a telemetry series locates a transition to within a scrape and a rule evaluation, never to the request. No figure published here is derived from a telemetry series.
- One round of probes is sent every registered interval, not a load profile. This experiment measures what a caller is told, not what a fleet of callers experiences: V1-S4-006 owns the under-load question and this one deliberately does not repeat it.
- Other workloads on the same node and virtual machine are not controlled, and the host's file cache is in whatever state the preceding run left it -- which matters more here than usual, because the thing being starved is a load whose cost depends on it.

Every figure this experiment produces is a bounded local observation under
[`ADR 0013`](../architecture/decisions/ADR-0013-bounded-local-performance-observations.md),
and the record it writes carries `productionBenchmark`, `portableCapacityClaim`, and
`availabilityClaim` all `false` beside the sentence that says so.
