# Q2: the runtime startup characterization

Status: **the Q2 workflow is frozen, and no characterization has run.** The synthetic
directories of the suite show each rule and each refusal at C0. No value of S exists.

Before a V2 reliability experiment runs, Q2 measures how long a serving runtime pod of
the qualified release takes from its creation to its first Ready condition, when the
Deployment controller replaces it in a controlled restart. It runs in the environment
that [the Q1 qualification `q1-1`](environment-qualification.md) selected. Every
replacement pod is one observation, and **S is the maximum of the observations**. The
result is `CHARACTERIZED`, `INCONCLUSIVE`, or `REFUSED`.

Q2 is a qualification and not a reliability experiment. It injects no fault and runs no
caller. S is not a startup benchmark, a capacity figure, a latency, or a threshold, and
no claim cites it. Later work derives bounds from S. Those bounds are not part of Q2.

| Property | Value |
|---|---|
| Freeze record | [`freeze-r2.v1alpha1.json`](../proof/experiments/v2-q2/freeze-r2.v1alpha1.json), experiment `v2-q2-runtime-startup-characterization`, part `Q2`, criteria `Q2-AC1` to `Q2-AC16`. It supersedes [revision 1](../proof/experiments/v2-q2/freeze-r1.v1alpha1.json), under which no characterization ran |
| Driver | [`q2-driver.txt`](../proof/experiments/v2-q2/procedure/q2-driver.txt), a pinned input of the freeze record, with the phases `up`, `characterize`, and `down` |
| Tool | [`tools/runtime_startup`](../../tools/runtime_startup/core.py): `python -m tools.runtime_startup DIRECTORY`, `--preconditions DIRECTORY`, and `--check` |
| Tests | [`tests/domain/test_runtime_startup.py`](../../tests/domain/test_runtime_startup.py) |
| Target | The release that `q1-1` qualified: key `local-docker-desktop/support-assistant`, 2 API replicas, 2 runtime replicas, provider `docker-desktop`, environment `sha256:23db293eeac80960eb77eac228188ceb5ac2cd1c11a925636aa61f1318866461` |
| Restarts | Three for each characterization, `r1`, `r2`, and `r3`, one at a time. Each replaces the 2 runtime pods, so a characterization has 6 observations |
| Runs | None. A characterization is committed under `docs/proof/experiments/v2-q2/runs/q2-N/` |
| Validation record | [`v2-s6-002-pr1-validation.md`](../proof/environment/v2-s6-002-pr1-validation.md) |

## A restart, and not a fault

**A restart is one `kubectl rollout restart` of the runtime Deployment.** The
restart changes one annotation of the pod template. The Deployment controller then
replaces each runtime pod under the rollout bounds that the chart states: 1 pod
unavailable and no pod above the replica count. Kubernetes documents what the two bounds
allow. At 2 replicas they allow one old pod to be taken away and replaced, and they
allow the second to be replaced only when 2 pods are available again. So each restart
is expected to give two replacements, one after the other. That expectation is not
assumed: a rule holds that the second replacement was created no earlier than the first
was Ready.

The driver deletes no pod by name, runs no caller, and changes no replica count,
request, limit, or bound. A restart is not the fault of a reliability experiment, and no
run of a reliability experiment is used as a characterization.

## What is measured

**One observation is one replacement pod.** Its interval `startToReadyMs` is from the
creation instant of the pod, `metadata.creationTimestamp`, to the transition instant of
its first Ready condition. The driver records every event of a watch of the runtime pods,
`kubectl get pods --watch --output-watch-events`, and the tool reads the first event in
which the Ready condition of the pod is `True`.

**Ready is the Ready condition of the pod.** The kubelet sets it from the readiness probe
of the runtime container, which asks `/health`. The runtime answers 503 to `/health`
while it loads the model, so a pod is not Ready while its model loads. After each
restart, the driver sends one completion to each replacement through a port-forward to
that pod, and a rule holds that each answered. The completion is not a part of the
interval.

**The resolution is one second.** Both instants are cluster timestamps of whole seconds,
so each interval is within one second of the time that passed. The record states two
parts beside it: from creation to the Initialized condition, which includes the
verification of the model by the `verify-model` init container, and from Initialized to
Ready, which includes the load of the model.

**S is the maximum.** S is the maximum `startToReadyMs` of every observation of a
characterization whose result is `CHARACTERIZED`. It is the maximum and not an average,
because it is used only as a conservative bound. A record whose result is not
`CHARACTERIZED` states no S. The record states no average, no percentile, and no rate.

## A refusal is a result

**The first seven rules are preconditions.** When one is not held, the result is
`REFUSED`, and the driver requests no restart. They hold that the phase `up` completed,
that the working tree was clean, that the frozen inputs are at their pins, that the
delivery paths equal the desired revision, and that the environment, the release, the
images, and the topology are the ones that `q1-1` states. The driver asks the tool for
the preconditions, with `--preconditions`, before it requests the first restart.

**The other rules decide the measurement.** When each precondition is held and one of
them is not, the result is `INCONCLUSIVE`, and the record states no S.

**Every characterization is kept.** A characterization is never repeated for a lower or
a higher S. A later characterization runs only after the environment or a frozen input
changes, and it takes the next identifier. When a frozen input changes, a new revision
of the freeze record comes first.

**A read that was not made is not a value.** A source that is absent gives the state
`not-observed` to each rule that reads it. A source of another form gives `not-held`.

## The procedure

The driver runs from the committed tree with a clean working tree. It writes only under
`.artifacts/`.

1. **`up RUN`** runs the phase `up` of [the Q1 driver](../proof/experiments/v2-q1/procedure/q1-driver.txt)
   without a change. So the release is prepared and applied exactly as for `q1-1`: the
   capacity gate, the API image, the model cache claim, the controller, the capacity
   gate again, the Application, and the two rollouts.
2. **`characterize RUN q2-N`** reads the executing commit, the working tree, the remote
   main as the desired revision, whether the chart, the desired-state tree, and the
   controller manifests of the executing commit equal those of that revision, and
   whether the freeze tool lists a changed material file of the Q2 or of the Q1 record.
   When the phase `up` refused, or one of these is not at its state, it reads no cluster
   state and requests no restart. Otherwise it copies the capacity collection that the
   phase `up` read before the apply, resolves the provenance of the target release at
   the desired revision, reads the Deployments, and asks the tool for the
   preconditions. When each is held, it runs `r1`, `r2`, and `r3`, one after the other.
   For each: it waits until exactly 2 runtime pods exist, at most 300 s; reads the
   runtime Deployment and the runtime pods; starts the watch and waits until it lists
   them, at most 30 s; requests the restart; waits for the rollout, at most 1800 s;
   waits until exactly 2 runtime pods exist again; waits 10 s more and stops the watch;
   reads the runtime pods; and sends one completion to each replacement. When a rollout
   does not complete within its bound, it requests no later restart. It then writes
   the header and runs the tool. It keeps the record when the tool exits 0, 5, or 6.
3. **`down RUN`** runs the phase `down` of the Q1 driver without a change.

**The driver states no result and no S.** The tool states them.

## The directory

The phase `characterize` writes one directory, `.artifacts/v2-q2/RUN-driver/q2-N/`. A
committed characterization adds `transcript.txt` and its page, `result.md`. The evidence
layout check lists a directory of `v2-q2/runs/` as a qualification, as it lists one of
`v2-q1/runs/`: it applies the credential-prefix rule and the personal-path rule to each
file, and holds it to no ExperimentRun manifest.

| File | What it holds | Written by |
|---|---|---|
| `run.json` | The header. Schema `inferops.io/runtime-startup-collection/v1alpha1` | The driver |
| `capacity/record.v1alpha1.json` | The capacity record of the reading that the phase `up` took before the apply, in its collection | [The capacity gate](capacity-preflight.md) |
| `provenance.json` | A list of one provenance record of the target release at the desired revision | [The provenance tool](desired-state-provenance.md) |
| `deployments.json` | The Deployments of the release before the first restart | The driver |
| `restarts/rN/restart.json` | The request instant, the exit status of the restart and of the rollout, the instant the rollout completed, and the instant the watch stopped, as host instants to one millisecond. Schema `inferops.io/runtime-startup-restart/v1alpha1` | The driver |
| `restarts/rN/before.deployment.json`, `restarts/rN/before.pods.json` | The runtime Deployment and the runtime pods before the restart | The driver |
| `restarts/rN/watch.jsonl` | Every event of the watch of the runtime pods, one on each line, in the order received | `kubectl` |
| `restarts/rN/after.pods.json` | The runtime pods after the restart | The driver |
| `restarts/rN/completion.<pod>.json` | The status, the finish reason, and the token counts of the one completion of a replacement. No text of the answer | The driver |
| `record.v1alpha1.json` | The Q2 record. Schema `inferops.io/runtime-startup-characterization/v1alpha1` | This tool |

The header states exactly these members: `schema`, `characterizationId` (`q2-N`),
`provider`, `releaseKey`, `executingCommit`, `upExecutingCommit`, `desiredRevision`,
`workingTree`, `desiredStateDiff`, `freezeRecord`, `freezeRecordSha256`,
`freezeChanges`, `qualificationFreezeChanges`, `apiImageDigest`, `targetRefusal`,
`upRefusal`, `upStartedAt`, `startedAt`, and `finishedAt`. The five members that start
with `up`, with `apiImageDigest` and `targetRefusal`, are what the phase `up` of the Q1
driver wrote. A header with another member, an absent member, or an unusable value is
not a header: the command prints no record and exits 1.

## The record

| Member | What it states |
|---|---|
| `result` | `CHARACTERIZED` when every rule is held, `REFUSED` when a precondition is not held, and `INCONCLUSIVE` otherwise |
| `notHeld` | The categories of the rules that are not held, in the order below, and the rules |
| `collection` | The header |
| `target` | The release key, the two replica counts, the provider, the number of restarts, and the replacements of each |
| `identities` | The executing commit, the desired revision, the release key and identifier, the API image digest, the runtime image, the provider, the server version, the environment digest, the record of `q1-1` with its digest, and the freeze record with its digest. An identity that was not read is null |
| `environment` | The environment identity, computed from the capacity record as the Q1 tool computes it |
| `measurement` | The interval, the clock, and the resolution of 1000 ms |
| `observations` | One row for each replacement: the restart, its order, the pod, the creation, scheduling, Initialized, runtime start, and Ready instants, `startToReadyMs`, and its two parts |
| `bound` | S: the symbol, the rule, `valueMs`, the number of observations, and the first observation with that value. `valueMs` is null unless the result is `CHARACTERIZED` |
| `files` | The name and the SHA-256, with CRLF read as LF, of each file of the directory that the tool read |
| `findings` | The state of each rule, with its criterion, its category, and a detail |
| `doesNotEstablish` | What no record establishes |

The command exits 0 when the result is `CHARACTERIZED`, 5 when it is `REFUSED`, and 6
when it is `INCONCLUSIVE`. It exits 1 when the directory is not a characterization
directory, and 2 when the arguments are not usable. `--preconditions` prints the state of
the seven preconditions, and exits 0 when each is held and 5 otherwise. `--check` builds
the record of each committed directory again and compares it with the committed record.
It reads the record of `q1-1` and the freeze record from the checkout, and neither
changes once it is committed.

## The rules

16 rules. Each is required, and each is one acceptance criterion of the freeze record,
with the same identifier and statement. A rule is `held`, `not-held`, or `not-observed`.
The categories are `preparation`, `desired-state`, `environment`, `release-identity`,
`topology`, `measurement`, `readiness`, and `evidence`, in that order.

| Rule | Criterion | Category | Refuses | Statement |
|---|---|---|---|---|
| `preparation-completed` | Q2-AC1 | `preparation` | yes | The phase up of the Q1 driver completed: it states no refusal, the target check refused nothing, and it ran at the executing commit of the characterization. |
| `working-tree-clean` | Q2-AC2 | `desired-state` | yes | The working tree was clean when the characterization started. |
| `procedure-frozen` | Q2-AC3 | `desired-state` | yes | The driver names the Q2 freeze record, the record has the content that the checkout holds, and the freeze tool listed no changed material file of the Q2 record or of the Q1 record when the characterization started. |
| `desired-revision-known` | Q2-AC4 | `desired-state` | yes | The desired revision is one full commit identifier, and the chart, the desired-state tree, and the controller manifests of the executing commit equal those of that revision. |
| `environment-qualified` | Q2-AC5 | `environment` | yes | The qualification q1-1 is QUALIFIED, the capacity gate accepted the target release key with 2 API replicas and 2 runtime replicas before the release was applied, and the environment identity of that capacity record has the digest that q1-1 states. |
| `release-qualified` | Q2-AC6 | `release-identity` | yes | The provenance record resolves the target release key at the desired revision to the release identifier that q1-1 states, the API Deployment runs the API image digest that the phase up declared, and the runtime Deployment runs the runtime image that q1-1 states. |
| `topology-ready` | Q2-AC7 | `topology` | yes | Before the first restart, the API Deployment and the runtime Deployment each state 2 replicas and report 2 replicas, 2 Ready, 2 available, and 2 updated at their current generation. |
| `three-restarts` | Q2-AC8 | `measurement` | no | The directory holds the restarts r1, r2, and r3 and no other, the rollout restart of each exited 0, and the rollout of each completed within its bound. |
| `stable-before-each-restart` | Q2-AC9 | `topology` | no | Before each restart, the runtime Deployment states 2 replicas and reports 2 replicas, 2 Ready, 2 available, and 2 updated at its current generation, and exactly 2 runtime pods exist, each Ready and none deleted. |
| `stream-complete` | Q2-AC10 | `evidence` | no | The watch stream of each restart is a sequence of pod events of the runtime tier with no ERROR event, it opens with one ADDED event for each pod of the reading before the restart, and the watch stopped after the rollout completed. |
| `two-replacements` | Q2-AC11 | `measurement` | no | Each restart created exactly 2 runtime pods that the reading before it does not list, each with a creation instant, each became Ready in the stream no earlier than its creation, and the reading after the restart lists exactly those 2 pods, each Ready. |
| `one-at-a-time` | Q2-AC12 | `measurement` | no | In each restart, the second replacement was created no earlier than the first replacement became Ready. |
| `ready-held` | Q2-AC13 | `readiness` | no | Each replacement stayed Ready in the stream from the event in which it first became Ready to the end of the stream, and the reading after the restart states no restart of its init container or of its runtime container. |
| `model-verified` | Q2-AC14 | `readiness` | no | In the reading after the restart, the verify-model init container of each replacement terminated with exit code 0, and its runtime container runs the runtime image that q1-1 states. |
| `ready-serves` | Q2-AC15 | `readiness` | no | Each replacement answered one completion through a port-forward to that pod after the rollout of its restart completed, with HTTP status 200, a finish reason, and at least one completion token. |
| `readings-in-order` | Q2-AC16 | `evidence` | no | The phase up started before the characterization, each restart was requested after the characterization started and after the rollout of the restart before it completed, and each rollout completed after its request and before the characterization finished. |

**`release-qualified` holds the API image to the digest that the phase `up`
declared, not to the one of `q1-1`.** The phase `up` builds the API image again, and a
build of unchanged inputs reported another digest. The inputs of that build are pinned
by the Q1 record, and `procedure-frozen` holds them unchanged. Revision 1 held the API Deployment to the API image digest that the record of `q1-1` states. The phase `up` of the Q1 driver builds the API image again, and its build at the first commit of `V2-S6-002-PR1` reported another digest, `sha256:cf30eac7cc2a75f9a91dac62c8c09a6080de5b2725d2b37262c15bafe924120d`, than `q1-1` states, `sha256:5b4be2da31141bc43c0fa65133b4377ef002a3ff922278cda98ba247a244c7e1`, while the freeze tool listed no changed input of the Q1 record. So that precondition could not hold. No characterization ran under revision 1. Revision 2 holds the API Deployment to the digest that the phase `up` declared, as Q1 does, and changes no other rule, bound, or step.

**`environment-qualified` uses the Q1 computation.** The tool imports the function of the
Q1 tool that computes the environment identity of a capacity record, so one capacity
record has one digest in both tools.

**`ready-serves` holds an answer, not an instant.** The completion is sent after the
rollout of its restart completed, not at the instant of Ready. It shows that Ready did
not precede a runtime that could not answer for the whole of the restart.

## What a record does not establish

- A startup benchmark, an average start time, a percentile, or a rate. A record states
  six intervals and their maximum.
- The start time of a pod that replaces a deleted pod, a pod that starts under caller
  traffic, or a pod that starts on a cold image cache or a cold model cache.
- A recovery time, an availability, a service level, or the reliability of the caller
  path. No caller runs.
- An interval shorter than its resolution of one second.
- That the readiness probe answered at the instant of the Ready condition. The kubelet
  sets the condition after the probe, and the probe runs every 10 s.
- That a source record is what its collection gives. The tool reads the stored source
  records and does not build them again.
- A result of a reliability experiment, or a bound that later work derives from S.
- Production availability, high availability, or resilience to the loss of a node, a
  zone, or a region.
- Anything about another provider, another node, another Kubernetes version, another
  release, or another model.

## Limitations

- One provider, one node, one Kubernetes version, one release, and one model.
- The image cache and the model cache are warm: the runtime image is in the node, and
  the model cache claim holds the verified model.
- A replacement starts while the other runtime pod runs and holds its model. That is
  the state of a rollout under the chart's bounds. A start with no other runtime pod is
  not observed.
- After the first restart, the runtime Deployment holds an annotation of its pod
  template that the desired state does not hold. A restart changes it.
- The direct `kubectl` commands of the driver name the context `docker-desktop` and run
  no target check of their own. The phase `up` of the Q1 driver runs the operating
  procedures, and each runs it.
