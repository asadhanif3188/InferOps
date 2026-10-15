# Q1: the environment and identity qualification

Status: **the Q1 workflow is frozen, and no qualification has run. The freeze
record, the driver, and the tool that builds the record exist. Synthetic
directories in the suite show a `QUALIFIED` record and each refusal at evidence
level C0. No record of a real environment exists, so no environment is
qualified or refused by this page.** The first qualification is later work.

Before a V2 reliability experiment runs, Q1 decides whether one local
environment holds the target topology of the desired-state release: two
platform API replicas and two serving runtime replicas, delivered by the
controller at the desired revision, with both runtime replicas on the pinned
model, and with the caller runner completing real requests through the API
Service. The result is `QUALIFIED` or `REFUSED`. There is no third result.

| Property | Value |
|---|---|
| Freeze record | [`freeze-r1.v1alpha1.json`](../proof/experiments/v2-q1/freeze-r1.v1alpha1.json), experiment `v2-q1-environment-qualification`, part `Q1`, criteria `Q1-AC1` to `Q1-AC17` |
| Driver | [`q1-driver.txt`](../proof/experiments/v2-q1/procedure/q1-driver.txt), a pinned input of the freeze record, with the phases `up`, `qualify`, and `down` |
| Tool | [`tools/environment_qualification`](../../tools/environment_qualification/core.py): `python -m tools.environment_qualification DIRECTORY` and `--check` |
| Tests | [`tests/domain/test_environment_qualification.py`](../../tests/domain/test_environment_qualification.py) |
| Target | Release key `local-docker-desktop/support-assistant`, 2 API replicas, 2 runtime replicas, provider `docker-desktop` |
| Runs | None. A qualification is committed under `docs/proof/experiments/v2-q1/runs/q1-N/` |
| Validation record | [`v2-s6-001-pr1-validation.md`](../proof/environment/v2-s6-001-pr1-validation.md) |

## A refusal is a result

**Q1 does not weaken its target to qualify.** The release key, the two replica
counts, the provider, and the model are constants of the tool. The command has
no option for any of them, and a source record of one runtime replica refuses.
The driver changes no replica count, no request, no limit, and no bound. When
the target check or the capacity gate refuses in the phase `up`, nothing more is
installed, and the phase `qualify` writes a `REFUSED` record from what exists.

**A refused qualification is kept.** Its directory is committed as it is. A later
qualification takes the next identifier, and it runs only after the environment
or a frozen input changes. When a frozen input changes, a new revision of the
freeze record comes first.

**A read that was not made is not a value.** A source that is absent gives the
state `not-observed` to each rule that reads it. A source of another form gives
`not-held`. Each of the two refuses.

## The selected environment

A record states the environment identity: the provider, the server version,
each node with its kubelet version and what it allocates, and the container
engine, as the capacity record states them. It also states the SHA-256 of the
canonical JSON text of that identity, `environmentSha256`. The identity holds no
address, no context name, and no path.

When a qualification is `QUALIFIED`, E02A and E02B execute in that one
environment. A run of either states its own environment identity. A run whose
identity differs from the qualified one is not a run of the controlled
comparison. No run of E02A or E02B exists, so no comparison of identities has
been made. When the local environment is `REFUSED`, the refusal is retained, and
a separate environment decision record precedes any other environment.

## The procedure

The driver runs from the committed tree with a clean working tree. It writes
only under `.artifacts/`.

1. **`up RUN`** prepares the release once. It refuses a working tree that is not
   clean, a material file that differs from its pin, and a cluster that already
   holds the release namespace or the controller namespace. It takes the
   capacity gate before anything is installed, builds and loads the API image at
   the executing commit and the model seed image, fills the model cache claim
   from the seed image with one preparation Helm release and removes that
   release, installs and verifies the controller with its bootstrap procedure,
   takes the capacity gate again, applies the Application, and waits for the two
   rollouts, at most 900 s each. **Q1 reads the second capacity reading.** The
   gate refuses a cluster that already holds the release, so the reading is
   taken before the apply.
2. **`qualify RUN q1-N`** reads the release once. It reads the executing commit,
   the working tree, the remote main as the desired revision, whether the chart,
   the desired-state tree, and the controller manifests of the executing commit
   equal those of that revision, and whether the freeze tool lists a changed
   material file. When the phase `up` refused, or one of these is not at its
   state, it reads no cluster state. Otherwise it resolves the provenance of the
   target release at the desired revision, verifies the controller, takes 5
   reconciliation samples 10 s apart, reads the Deployments, takes one endpoint
   reading, observes the model cache in each runtime pod with one model listing
   and one completion through a port-forward to that pod, and runs the caller
   runner once: RP-1 against the API Service for 60 s, with a request ceiling of
   50. It then writes the header and runs the tool.
3. **`down RUN`** removes the Application, the controller, and the prerequisite
   layer, and compares the namespaces and the custom resource definitions with
   those read before the phase `up`.

**The driver states no result.** The tool states it.

## The directory

The phase `qualify` writes one directory, `.artifacts/v2-q1/RUN-driver/q1-N/`.

| File | What it holds | Written by |
|---|---|---|
| `run.json` | The header. Schema `inferops.io/environment-qualification-collection/v1alpha1` | The driver |
| `capacity/record.v1alpha1.json` | The capacity record of the reading before the apply, in its collection | [The capacity gate](capacity-preflight.md) |
| `provenance.json` | A list of one provenance record of the target release at the desired revision | [The provenance tool](desired-state-provenance.md) |
| `reconciliation.record.json` | The reconciliation record, beside its observation `reconciliation/` | [The reconciliation tool](reconciliation-evidence.md) |
| `deployments.json` | The Deployments of the release, as one `kubectl get` | The driver |
| `endpoints/record.v1alpha1.json` | The endpoint record, in its collection | [The endpoint state tool](service-endpoint-state.md) |
| `model-cache/record.v1alpha1.json` | The model cache record, in its collection | [The model cache observation](runtime-model-cache-observation.md) |
| `plan.json`, `caller.jsonl` | The plan of the caller run, and the caller record that each rule of its reader accepted | [The runner script](../serving/reliability-runner.md) |
| `caller.refused.jsonl` | The caller log that a rule refused, when one was refused | The runner script |
| `record.v1alpha1.json` | The Q1 record. Schema `inferops.io/environment-qualification/v1alpha1` | This tool |

The header states exactly these members: `schema`, `qualificationId` (`q1-N`),
`provider`, `releaseKey`, `executingCommit`, `desiredRevision`, `workingTree`
(`clean`, `dirty`, or `unread`), `desiredStateDiff` (`none`, `differs`, or
`unread`), `freezeRecord`, `freezeRecordSha256`, `freezeChanges` (`none`,
`listed`, or `unread`), `apiImageDigest`, `controllerVersion`,
`controllerVerified`, `targetRefusal`, `startedAt`, and `finishedAt`. A header
with another member, an absent member, or an unusable value is not a header:
the command prints no record and exits 1.

**`targetRefusal` is a category and not a message.** It is the refusal category
that the target check of the operating procedures printed, such as
`provider-mismatch` or `ambiguous-target`, or null. The message can name a
context, and a context name can hold an account identifier, so the driver keeps
only the category.

## The record

| Member | What it states |
|---|---|
| `result` | `QUALIFIED` when every rule is held, and `REFUSED` otherwise |
| `refusal` | The categories of the rules that are not held, in the order below, and the rules |
| `collection` | The header |
| `target` | The release key, the two replica counts, and the provider that Q1 qualifies |
| `identities` | The executing commit, the desired revision, the release key and identifier, the workload version, the contract digest, the Helm values digest, the environment binding, the renderer and platform-default revisions, the chart, the controller version, the API image digest, the runtime image, the model, the provider and server version, the caller profile, and the freeze record. An identity that was not read is null |
| `environment`, `environmentSha256` | The environment identity and its digest. Null when a part was not readable |
| `files` | The name and the SHA-256, with CRLF read as LF, of each file that the tool read |
| `findings` | The state of each rule, with its criterion, its category, and a detail |
| `doesNotEstablish` | What no record establishes |

The command exits 0 when the result is `QUALIFIED` and 5 when it is `REFUSED`.
It exits 1 when the directory is not a qualification directory, and 2 when the
arguments are not usable. `--check` builds the record of each committed
directory again and compares it with the committed record.

## The rules

17 rules. Each is required, and each is one acceptance criterion of the freeze
record, with the same identifier and statement. A rule is `held`, `not-held`,
or `not-observed`.

| Criterion | Rule | Category | Statement |
|---|---|---|---|
| `Q1-AC1` | `target-reached` | `target` | The target check of the operating procedures selected the target and refused nothing. |
| `Q1-AC2` | `provider-selected` | `provider-mismatch` | The qualification selects the docker-desktop provider explicitly, the target check refused no provider, and every source record that names a provider names docker-desktop. |
| `Q1-AC3` | `context-unambiguous` | `ambiguous-context` | The target check found one target, the capacity collection names the context docker-desktop, the capacity record holds one node, and the runtime pods run on that node. |
| `Q1-AC4` | `working-tree-clean` | `desired-state` | The working tree of the executing commit was clean. |
| `Q1-AC5` | `procedure-frozen` | `desired-state` | The driver names the Q1 freeze record, the record has the content that the checkout holds, and the freeze tool listed no changed material file. |
| `Q1-AC6` | `desired-revision-known` | `desired-state` | The desired revision is one full commit identifier, and the chart, the desired-state tree, and the controller manifests of the executing commit equal those of that revision. |
| `Q1-AC7` | `one-executing-commit` | `desired-state` | The capacity collection, the endpoint collection, the model cache collection, and the reconciliation collection name the executing commit of the qualification. |
| `Q1-AC8` | `release-provenance-resolved` | `desired-state` | The provenance record resolves the target release key at the desired revision to one release identifier. |
| `Q1-AC9` | `capacity-accepted` | `capacity` | The V2 capacity gate accepted the target release key with 2 API replicas and 2 runtime replicas before the release was applied. |
| `Q1-AC10` | `controller-identified` | `reconciliation` | The verification of the delivery controller by its bootstrap procedure exited 0, and the driver states the controller version. |
| `Q1-AC11` | `controller-reconciled` | `reconciliation` | The reconciliation record is complete, holds at least 5 samples, and in each sample the Application is settled at the desired revision, resolves to the provenance release, and has no finding in its revisions, its source, and its labels. |
| `Q1-AC12` | `deployments-ready` | `topology` | The API Deployment and the runtime Deployment of the release each state 2 replicas, and each reports 2 replicas, 2 Ready, 2 available, and 2 updated at its current generation. |
| `Q1-AC13` | `endpoints-ready` | `topology` | The endpoint record is OBSERVED, and the API Service and the runtime Service each have 2 endpoints, and both are Ready. |
| `Q1-AC14` | `images-declared` | `release-identity` | The api container of the API Deployment runs the API image digest that the driver built and declared, and the runtime container of the runtime Deployment runs the pinned runtime image. |
| `Q1-AC15` | `model-identity-verified` | `model-mismatch` | The model cache record expects the pinned model and the pinned runtime image for 2 runtime replicas of the target release, and holds each of its model identity rules. |
| `Q1-AC16` | `caller-completed` | `caller` | The runner's reader accepts the caller record with its plan, in the mode in-cluster, for this qualification and the provenance release, the run ended by its own bound, and at least one request has the outcome success. |
| `Q1-AC17` | `readings-in-order` | `evidence` | The capacity reading precedes the qualification, and each other reading lies between the start and the end of the qualification. |

The categories, in the order a record states them: `target`,
`provider-mismatch`, `ambiguous-context`, `desired-state`, `capacity`,
`reconciliation`, `topology`, `release-identity`, `model-mismatch`, `caller`,
and `evidence`.

### What each rule reads

- **`provider-selected`** reads the provider that each source record names: the
  capacity collection and environment, the endpoint collection, the model cache
  collection, and the reconciliation collection. A target check that refused
  with `no-provider-selected`, `unsupported-provider`, or `provider-mismatch`
  does not hold it.
- **`context-unambiguous`** reads the context of the capacity collection, the
  nodes of the capacity record, and the nodes on which the model cache record
  places the runtime pods. A target check that refused with `ambiguous-target`
  does not hold it.
- **`controller-reconciled`** reads every sample of the reconciliation record.
  The labels comparison must be `compared`. A comparison that is
  `compared-in-part` does not hold it, because it left objects out.
- **`deployments-ready`** reads `spec.replicas`, `status.replicas`,
  `readyReplicas`, `availableReplicas`, `updatedReplicas`, and
  `observedGeneration` against `metadata.generation`. A third pod of a rollout
  does not hold it.
- **`model-identity-verified`** compares the model and the runtime image that
  the model cache record expects with
  [`model-source.v1.json`](../serving/model-source.v1.json) and
  [`container-package.v1.json`](../../deploy/serving/runtime/container-package.v1.json)
  of the checkout, and reads 15 of the 17 rules of that record. It does not read
  `capacity-preflight-sufficient`, which states the V1 multi-replica capacity
  preflight, and `not-ready-while-loading`, which states samples of the start.
  Q1 runs neither: the V2 capacity gate decides capacity. So the result of that
  record can be `INCONCLUSIVE` while this rule is held.
- **`caller-completed`** gives the caller record and its plan to the reader of
  the runner, and requires the mode `in-cluster`, the experiment
  `v2-q1-environment-qualification`, the qualification identifier as the run
  identifier, the provenance release identifier, the end state `duration` or
  `request-ceiling`, and at least one request with the outcome `success`.
- **`readings-in-order`** requires the capacity reading at or before the start
  of the qualification, and the endpoint reading, the model cache collection,
  the start of the caller run, and the first reconciliation sample between its
  start and its end. These instants come from more than one clock. The rule
  states their order, and not a duration.

## What a record does not establish

- A record does not establish behaviour under a fault, the replacement of a pod, or a recovery from either.
- A record does not establish a runtime start time, a caller gap, or any bound that Q2, Q3, or Q4 derives.
- A record does not establish a latency, a throughput, a success rate, or the reliability of the caller path. One completed request shows that the path answered once.
- A record does not establish that a later run uses the same environment. A later run states its own environment identity and compares it with this one.
- A record does not establish that a source record is what its collection gives. The module reads the stored source records and does not build them again. It checks the caller record with the runner's reader.
- A record does not establish capacity beyond the stated requests and limits on one node, or that a pod is scheduled in another state of the cluster.
- A record does not establish production availability, high availability, a service level, or resilience to the loss of a node, a zone, or a region.
- A record does not establish anything about another provider, another node, another Kubernetes version, or another release.
- A record does not establish a representative workload. RP-1 is a fixed reliability profile.

The tool reads the stored source records. It does not build the capacity,
endpoint, model cache, reconciliation, or provenance records again from their
collections. The driver runs each tool on its collection in the same
qualification, and the transcript of a qualification shows each run. It checks
the caller record with the reader of the runner.
