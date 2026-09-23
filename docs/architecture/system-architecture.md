# V1 system architecture

Status: **accepted as the V1 design boundary**, in
[ADR 0004](decisions/ADR-0004-component-and-ownership-boundaries.md). Most
components below the contract layer are now **built**, and one is not. This
document describes the boundary V1 is held to; each box says what exists.

> [!IMPORTANT]
> Read every box in every diagram as a design commitment unless it is marked
> otherwise. What exists today is the workload contract and its validator, the
> platform domain, both serving adapters, the InferOps API, the workload
> scaffolding, the telemetry emission package, the Helm chart and its
> release-scoped collector, the Terraform prerequisite layer, the cluster an
> operator provides, the serving runtime and model selected on executed proof, the
> dashboard and alert definitions, the committed continuous-integration workflow,
> the repository tooling under `tools/` that drives every declared experiment, and
> the evidence records. A request **has** been served through this architecture:
> `V1-S3-011` installed the release on the `docker-desktop` reference provider and a
> real completion came back through the release's own Service, and several hundred
> more have been served through it since under declared load, failure, and
> clean-clone experiments. **Deployment rendering is still unbuilt** — nothing turns
> a validated contract document into release values, and a values file is written by
> hand.
>
> Every result behind those sentences is one provider, one Windows host, CPU, and
> one replica of each tier. The multi-replica profile was refused at the capacity
> gate on that host, and no box here is evidence of a portable production platform.
>
> The ownership half of this design is machine-checked. The component half is not:
> no test checks the decomposition this document draws, and the document says so
> rather than implying that a diagram constrains anything on its own.

## What this document is for

A reviewer should be able to answer eight questions from it without reading a plan:

1. Who talks to InferOps, and what does InferOps talk to?
2. What are the components, and which of them may depend on which?
3. What happens to an inference request, including when the model is not ready?
4. What happens when a workload is deployed, and who creates each object?
5. Where does telemetry go, and where does evidence come from?
6. What happens when something fails, and what does the platform do about it?
7. How does a committed record become a published claim?
8. Where are the trust boundaries, and what is *not* defended at each one?

Questions 6 and 7 were added on 2026-09-21. Both capabilities were built during
Sprint 4 and neither appeared in any diagram here until the reconciliation that
added them; a reviewer asking either question would previously have had to read
`tools/` to answer it.

The lifecycle answer to question 4 is data rather than prose. It lives in
[`resource-ownership.v1alpha1.json`](resource-ownership.v1alpha1.json) and is
explained in [the resource ownership document](resource-ownership.md).

## How these diagrams are maintained

They are ASCII inside fenced blocks, for one reason: a diagram that cannot be read
in a plain `git diff` is a diagram that stops being reviewed. The repository has no
diagram toolchain and no renderer, so a Mermaid or image-based diagram would
introduce a dependency nothing here can check. The cost is real — these are harder
to lay out and cannot express much — and if a diagram ever needs more than boxes and
arrows, that is the moment to revisit the choice rather than to draw a worse ASCII
picture.

**The second half of that argument expired and was removed on 2026-09-21.** It used
to read "and no continuous-integration lane to run one in", which stopped being true
when [ADR 0012](decisions/ADR-0012-continuous-integration-service.md) selected a
service and committed [`.github/workflows/checks.yml`](../../.github/workflows/checks.yml).
A lane now exists that runs eleven gates, one of which reads every committed
document. The choice
of ASCII still stands on the first reason, which is the one that was ever load-bearing;
the reasoning behind it is recorded honestly rather than left resting on a fact that
the repository disproved three weeks after it was written.

## 1. System context

```text
   +-------------------------+          +----------------------------+
   |  Workload owner         |          |  Platform contributor      |
   |  an application team    |          |  runs the cluster, the     |
   |  that owns a workload   |          |  checks, and the evidence  |
   +-----------+-------------+          +-------------+--------------+
               |                                      |
               | authors a workload contract          | operates and
               | and owns its secret material         | proves
               v                                      v
   +-----------------------------------------------------------------+
   |                            InferOps                             |
   |                                                                 |
   |  validates a contract, renders a deployment from it, serves     |
   |  inference through a real local runtime, and emits telemetry     |
   |  and evidence for what it actually did                          |
   +------+---------------------+----------------------+-------------+
          |                     |                      |
          | pulls, pinned by    | schedules into       | declares a
          | digest and hash     | a cluster it does    | dependency on
          |                     | not own              |
          v                     v                      v
   +----------------+   +------------------+   +----------------------+
   | Image and      |   | Local Kubernetes |   | Capabilities a       |
   | model          |   | cluster          |   | contract may name    |
   | publishers     |   |                  |   | and this project     |
   |                |   | owned by the     |   | does not provide:    |
   | external, and  |   | contributor's    |   | model access,        |
   | outside this   |   | machine, not by  |   | evaluation,          |
   | project's      |   | the platform     |   | a telemetry store    |
   | control        |   |                  |   |                      |
   +----------------+   +------------------+   +----------+-----------+
                                                          |
                                    contract-based only.  |
                                    No provider exists,   |
                                    and V1 does not       v
                                    depend on one.  +-------------------+
                                                    | Future projects,  |
                                                    | out of V1 scope   |
                                                    +-------------------+
```

Three things this diagram asserts, each of which is a decision rather than a
drawing:

- **The cluster is not InferOps's.** The operator provides it, with a supported
  provider's own tooling — `kind`, or Docker Desktop's Kubernetes — and InferOps
  selects it explicitly, verifies it, and acts inside it. Nothing on the platform
  path creates, enables, resets, reconfigures, or deletes a cluster
  ([ADR 0011](decisions/ADR-0011-external-local-cluster-provider-contract.md)).
  That boundary is what keeps an operator's unrelated clusters out of reach. The
  `kind` guard was tested by attacking it with a real foreign cluster wearing this
  project's context name, and it refused. A Docker Desktop guard exists too, binding
  each node to a container on this engine and to the API server port the verified
  kubeconfig dials; it has not been attacked the same way, and neither guard can
  refuse a cluster an operator deliberately named to impersonate the other.
- **Publishers are outside the trust boundary and outside the availability
  boundary.** The project pins an image digest and a model revision with a per-file
  hash, so it can prove what it ran. It cannot keep either available.
- **A declared capability is not a provided one.** A workload contract can name a
  model-access, evaluation, or telemetry capability. Nothing in V1 provides one, and
  V1's mandatory path does not require one. The contract is where a future provider
  attaches; it is not evidence that a provider exists.

## 2. Components and dependency direction

```text
   authored outside the platform
   +-----------------------------------------------------------------+
   |  WorkloadContract document                              EXISTS  |
   +--------------------------------+--------------------------------+
                                    |
   ===== InferOps ==================|=================================
                                    v
   +-----------------------------------------------------------------+
   |  Contract validation                                    EXISTS  |
   |  structural rules from the published schema, plus the           |
   |  cross-field rules a schema cannot express; every refusal       |
   |  carries a canonical code, a rule identifier, and a field       |
   +--------------------------------+--------------------------------+
                                    v
   +-----------------------------------------------------------------+
   |  Platform domain                                         EXISTS |
   |  workload identity, model and runtime selection, resource and   |
   |  scaling policy, environment and ownership metadata, security   |
   |  classification, attribution           <- typed objects EXIST   |
   |  canonical errors, validation rules, policy    <- EXIST         |
   |                                                                 |
   |  owns the serving-adapter interface; depends on no adapter,     |
   |  no Kubernetes client, no Helm, and no runtime SDK              |
   +-----+-----------------------------------------------------+-----+
         ^                                                     |
         | implements the interface                            | renders
         | the domain owns                                     v
   +-----+------------------------+   +----------------------------------+
   |  Serving adapters    EXISTS  |   |  Deployment rendering    UNBUILT |
   |                              |   |  a validated domain object       |
   |  +------------+ +---------+  |   |  becomes chart values, and       |
   |  | mock       | | real    |  |   |  nothing else writes them; a     |
   |  | CI only    | | runtime |  |   |  values file is written by hand  |
   |  | EXISTS     | | EXISTS  |  |   +----------------+-----------------+
   |  +------------+ +----+----+  |                    |
   +---------------------|--------+                    v
                         |                +--------------------------+
   +---------------------|--------+       |  Helm chart      EXISTS  |
   |  InferOps API       |EXISTS  |       |  and its values schema   |
   |  inference, live,   |        |       +--------------------------+
   |  ready, metrics,    |        |
   |  correlation id,    |        |
   |  canonical errors,  |        |
   |  redacted logs      |        |
   |                     |        |
   |  selects one adapter|        |
   |  at composition time|        |
   +---------------------|--------+
                         | HTTP, cluster-internal, never in-process
   ===== InferOps =======|===========================================
                         v
   +--------------------------------+        +------------------------+
   |  Serving runtime               | reads  |  Model cache volume    |
   |  third party, pinned by digest +------->|  holds one hash-       |
   |  EXISTS as a selected, proven  |        |  verified artifact     |
   |  dependency, and the release   |        |  EXISTS, Terraform-    |
   |  deploys it                    |        |  owned and filled      |
   |                                |        +------------------------+
   +--------------------------------+
```

### The dependency rule

One rule, stated so that a review can enforce it:

**Nothing in the platform domain may import a Kubernetes client, a Helm library, a
serving-runtime SDK, or an HTTP framework.** The domain owns the serving-adapter
interface; adapters implement it; the API selects one at composition time. A domain
that knows about the runtime cannot be tested without one, and a project whose
domain cannot be tested without a runtime will test it with a mock and then be
tempted to call that certification.

There is now a domain for the rule to apply to.
[The workload domain model](../domain/workload-domain-model.md) turns a contract
document into typed platform objects, it declares no runtime dependency at all, and
`tests/architecture/test_domain_dependency_boundary.py` reads every module under
`src/inferops/` and fails if one imports anything outside the standard library and
this distribution. The validation rules, the canonical error surface, and the
serving-adapter interface now sit beside it, and the first implementation of that
interface — [the deterministic mock adapter](../serving/mock-serving-adapter.md) —
lives outside the domain in `src/inferops/adapters/`, which is the dependency
direction this rule exists to fix. The adapter for the selected runtime, the API
that composes one, the chart, and the prerequisite layer have all been built
since, and `V1-S3-011` ran them together on the reference provider. What is still
unbuilt is deployment rendering: nothing turns a validated document into release
values, and a values file is written by hand.

The rule has a visible consequence and it is worth stating rather than discovering:
the composition point — the place that decides which adapter is live — is the one
component that knows about everything. It must be small, and it must be the only
such place.

### Why the runtime is a separate deployment rather than a sidecar

The serving runtime runs in its own Deployment behind its own Service, and the API
reaches it over the cluster network.

| | Separate deployment (**selected**) | Sidecar in the API pod |
|---|---|---|
| Model load | The API stays ready and answers `model not ready` with a canonical error | The whole pod is unready for the duration of the model load |
| Restart blast radius | A runtime restart does not restart the API | Either container restarting takes both |
| Memory limit | Sized against the runtime's own worst-case charge | One limit covering two very different footprints |
| Probes | The proven three-probe mapping applies to the runtime alone | One probe set for two processes with different readiness semantics |
| Cost | An extra network hop, and a service-to-service failure mode that must be a first-class error | Simpler, and loopback-only |

The deciding fact is measured rather than aesthetic. The selected runtime memory-maps
its weights, and two identical pods were observed reporting 2.167 GiB and 531 MiB for
the same work, because the kernel charges mapped pages to whichever control group
faults them in first. A limit set from the smaller figure produces page eviction and
silent latency rather than an obvious failure. Sizing that limit is hard enough on
its own; sizing it for a pod that also contains an API process is worse.

The honest cost of the selection is the extra failure mode: the API can now be
healthy while the runtime is unreachable. That is why `model not ready`, timeout, and
internal failure are canonical errors in the platform contract rather than
incidental HTTP statuses.

## 3. Inference request flow

```text
  caller            InferOps API        adapter        serving runtime
    |                    |                 |                  |
    |  POST inference    |                 |                  |
    +------------------->|                 |                  |
    |                    | assign correlation id              |
    |                    | validate request against the       |
    |                    | domain model, not the wire shape   |
    |                    |                 |                  |
    |                    | is the selected adapter ready?     |
    |                    +---------------->|                  |
    |                    |                 |  readiness probe |
    |                    |                 +----------------->|
    |                    |                 |<- - - - - - - - -+
    |                    |                 |   ready | 503    |
    |                    |<- - - - - - - - +                  |
    |                    |                 |                  |
    |     [not ready]    |                 |                  |
    |<-------------------+                 |                  |
    |  canonical error   |                 |                  |
    |  MODEL_NOT_READY   |                 |                  |
    |  retryable: true   |                 |                  |
    |                    |                 |                  |
    |     [ready]        | invoke          |  POST completion |
    |                    +---------------->+----------------->|
    |                    |                 |                  | decode
    |                    |                 |<- - - - - - - - -+
    |                    |                 |  body + usage    |
    |                    |<- - - - - - - - +                  |
    |                    |  mapped to the canonical shape;    |
    |                    |  runtime-specific fields stay      |
    |                    |  namespaced and do not leak        |
    |                    |                 |                  |
    |                    | emit: request count, latency,      |
    |                    | outcome, token counts, model and   |
    |                    | runtime identity, correlation id   |
    |<-------------------+                 |                  |
    |  response          |                 |                  |
```

Four properties this flow commits to:

- **The correlation identifier is assigned at the edge**, before anything can fail,
  so that a refusal is as traceable as a success.
- **Readiness is asked, not assumed.** The selected runtime answers 503 while it is
  loading a model. That is correct readiness behaviour and wrong liveness behaviour,
  and the platform's job is to turn it into an error a caller can act on rather than
  a timeout.
- **The request counter is the platform's obligation.** The selected runtime exposes
  native token counters and no cumulative request counter. ADR 0002 accepted that
  with a recorded exception and moved the count here, to the component that actually
  receives the requests. This diagram is where that obligation lands.
- **Runtime-specific response fields stay namespaced.** An adapter that lets a
  runtime's own vocabulary reach a caller has made the runtime part of the public
  contract, and the contract is the thing that has to survive replacing it.

What the flow deliberately does **not** decide: streaming, batching, concurrency
limits, and back-pressure. No component here bounds how many requests may be in
flight, sheds one, or queues deliberately.

**This paragraph used to say more than that, and was corrected on 2026-09-21.** It
read "Every request in the one executed trial was single and sequential; the runtime
reported four slots and one was ever used", which was true when it was written and
stopped being true at `V1-S4-004`. The performance scenarios committed in
[`performance-scenarios.v1.json`](../../deploy/serving/experiments/performance-scenarios.v1.json)
drive this flow at concurrency 1, 2, and 4, and
[the findings](../proof/serving/v1-s4-004-pr2-performance-findings.md) record where
one host degraded. Queueing was not designed, but it **was observed**: the runtime
defers what it cannot admit, and the deferral was counted.

What has not changed is what those numbers may be used for. They are a bounded local
observation under
[ADR 0013](decisions/ADR-0013-bounded-local-performance-observations.md) — one
provider, one host, one model, one release configuration — and not a capacity figure,
a service-level objective, or a design for behaviour under concurrency. The
difference between "we measured one setup" and "we decided how this behaves under
load" is the whole distance this document still has to travel, and drawing a
back-pressure box would cross it.

## 4. Workload deployment flow

Ownership bands are marked. Nothing crosses a band except at a named handoff.

```text
   [ workload owner ]
       workload contract document
                |
                v
   [ platform ]
       validate: structural, then semantic
                |            refusal -> canonical code, rule, field. Stop.
                v
       domain object
                |
                v
       render chart values                (nothing else writes them)
                |
   -------------|------------------------------------------------------
   [ operator ]                                    outside InferOps
       provide an existing cluster: kind, or Docker Desktop
                |
   [ contributor host ]                                    every run
       select the provider, verify it, load locally built images
       by that provider's own path                        (ADR 0011)
                |
   -------------|------------------------------------------------------
   [ terraform ] prerequisites, longer-lived than any release
       namespace  ->  namespace metadata  ->  model cache claim
                |
                |  handoff: Terraform hands over an empty, labelled
                |  namespace and an empty claim. Helm is never invoked
                |  with --create-namespace.
                v
   -------------|------------------------------------------------------
   [ helm ] one release
       service account, config, services, network policy
       acquisition job  --writes into-->  the Terraform-owned claim
                |            (the one place a release writes into a
                |             prerequisite; it verifies the artifact
                |             hash before the bytes are used)
                v
       serving runtime deployment, platform API deployment
                |
   -------------|------------------------------------------------------
   [ kubernetes ] derived, declared by nobody
       replica sets -> pods -> endpoint slices
       startup probe absorbs model load
       readiness decides endpoint membership
       only a socket-level liveness probe may restart the pod
                |
                v
       the service has endpoints; requests can arrive
```

Teardown is the reverse, and the order is not a preference:

```text
   helm uninstall        removes the release. The namespace, its metadata,
                         and the model cache survive.

   terraform destroy     removes the prerequisites. Deleting the namespace
                         cascades, so anything still installed in it dies
                         with it -- which is why this is not the routine
                         uninstall path.

   cluster teardown      removes or resets the cluster itself. The
                         operator does it with the provider's own
                         tooling; nothing on InferOps's platform path
                         does, and neither tool may (ADR 0011).
```

The model cache is the interesting row, and the reason it sits on the Terraform
side is measured rather than tidy. In the one executed trial the weight cache was
placed inside the trial's own namespace, and scoped teardown destroyed it; re-running
cost the full download again. That download is roughly 1.7 GiB over a transport that
does not validate certificates, so repeating it repeats an exposure the published
file hash is carrying alone. A resource whose lifecycle is longer than a release's
belongs to the layer whose lifecycle is longer than a release's.

Its honest cost: `helm uninstall` now leaves roughly 1.7 GiB occupied on a host
measured to have about 23 GB free on the volume where the container engine keeps its
virtual disk. Reclaiming it is `terraform destroy`, and that must be documented where
an operator will find it rather than discovered as a disk-full error.

## 5. Telemetry and evidence flow

These are two different things that get confused because both are called "output".
**Telemetry is what a running system emits about itself. Evidence is what a reviewed
change records about a run that happened.** One is continuous and disposable; the
other is committed and immutable.

```text
   +---------------------------+        +---------------------------+
   |  InferOps API             |        |  Serving runtime          |
   |                           |        |                           |
   |  metrics: request count,  |        |  metrics: native token    |
   |  latency, outcome, model  |        |  counters and gauges of   |
   |  and runtime identity     |        |  instantaneous state.     |
   |                           |        |  No cumulative request    |
   |  logs: structured,        |        |  counter exists.          |
   |  redacted, correlation id |        |                           |
   +------------+--------------+        +-------------+-------------+
                |                                     |
                +------------------+------------------+
                                   |
                                   v
                   +-------------------------------+
                   |  Collector: Helm-owned and    |
                   |  release-scoped. It scraped   |
                   |  both endpoints on the        |
                   |  reference provider. Series   |
                   |  live in an emptyDir and go   |
                   |  with the pod.                |
                   |                               |
                   |  Dashboard definition: a      |
                   |  repository artifact. One     |
                   |  throwaway Grafana, owned by  |
                   |  nothing, imported it once    |
                   |  and was removed. No server   |
                   |  serves it.                   |
                   |                               |
                   |  Alert definitions: also a    |
                   |  repository artifact. The     |
                   |  pinned collector's promtool  |
                   |  loads both rendered files;   |
                   |  no collector in a cluster    |
                   |  evaluates one, and nothing   |
                   |  routes one.                  |
                   |                               |
                   |  Durable store, dashboard     |
                   |  server, alert routing: NOT   |
                   |  SELECTED. telemetry-backend  |
                   |  is deferred in the inventory.|
                   +-------------------------------+

   -------------------------------------------------------------------
   separately, and never automatically:

   an executed run  ->  a human reads the output, records versions,
                        environment, exact commands, results,
                        limitations, and failure diagnostics
                        ->  a reviewed change  ->  docs/proof/
```

Three rules this flow fixes:

- **Nothing in a cluster writes evidence.** A record is produced by a reviewed
  change, not by a job. A record that a pipeline can regenerate is a record that can
  be regenerated to say something else.
- **Prompts and responses are not telemetry by default.** They are data the project
  does not own, and an error body is the surface most likely to be logged, pasted
  into a ticket, and kept. The contract validator already refuses to repeat a value
  read out of a document back to the caller; the same discipline applies here.
- **High-cardinality request data does not belong in a metric label.** Correlation
  identifiers, prompts, and tenant-supplied strings are log fields, not label values.

What was deferred here is now decided elsewhere. Which metrics exist, their names,
their labels and cardinality budget, and the log schema are in
[the telemetry catalog](../telemetry/telemetry-catalog.md); what a claim needs before
it may cite a run is in [the test strategy](../testing/test-strategy.md) and
[the certification levels](../testing/certification.md). Both catalogue what each
component may claim rather than what it does, they mark which components exist,
and most of them now do.

Nothing about the three rules above changed when they were written down in detail.
The catalog turns the third one into arithmetic — a field's placement is derived from
its sensitivity and its cardinality rather than chosen — and gives the second one an
empty placement list rather than a convention.

## 6. Failure and recovery flow

Added on 2026-09-21. Every capability drawn here was built and executed during
Sprint 3 and Sprint 4, and none of it appeared in any diagram in this document
until now: a reviewer asking what happens when something breaks had to read
`tools/` to find out.

Two failure shapes have been provoked deliberately against a real release on the
reference provider, and one more is a routine operation with a rollback path.

```text
   [ shape 1 ]  the serving pod is lost while traffic is arriving
        |
        |  the committed load profile is mid-flight; the pod is deleted
        v
   API stays up          endpoint slice drops the pod
   (a separate           (Kubernetes decides this, not InferOps)
    deployment is why)             |
        |                          v
        |          calls refused FAST, not hung: 503,
        |          capability-unavailable, condition runtime-unreachable.
        |          Observed at 20-83 ms each, which is why 41 requests fit
        |          inside a 32-second outage at concurrency 1.
        |
        |          The one request already in flight when the pod went is
        |          a different shape and is recorded as one: it hung, then
        |          came back 500 internal-error / runtime-error-response.
        v
   replica set recreates the pod -> startup probe absorbs the model load
        |                           (from the Terraform-owned cache, so no
        |                            download repeats)
        v
   readiness returns -> endpoint slice re-admits -> traffic resumes
        |
        v
   tools/inference_pod_recovery records: when it went, when it came back,
   what every request either side saw, and what was NOT measured

   -------------------------------------------------------------------

   [ shape 2 ]  the model does not finish loading
        |
        |  the release is installed with the runtime container starved of
        |  processor, so llama-server starts, binds its port, begins the
        |  load, and does not finish it
        v
   startup probe does not pass -> readiness does not return -> the pod never
   joins the endpoint slice
        |
        v
   the API stays live and refuses cleanly:
     runtime  GET /health        -> 503, "Loading model"
     API      GET /health/live   -> 200      <- the API is not the problem
     API      GET /health/ready  -> 503, not-ready, adapterKind=real
     API      POST /v1/chat/...  -> 503, capability-unavailable,
                                    condition runtime-unreachable,
                                    retryable: true
        |
        |  neither container restarts. A TCP-connect liveness probe will not
        |  kill a process that is listening and simply not ready, which is
        |  the asymmetry the chart's probe split exists to get right.
        v
   the bound is the kubelet's, not this project's: past the runtime's own
   startup budget the kubelet kills the container and restarts it into the
   same load. Nothing here escalates, times the failure out, or tells an
   operator, and the observed window was held well inside that budget --
   what happens past it was not measured.
        |
        v
   tools/unready_model_recovery records the shape, the four surfaces above,
   and the diagnostics that distinguish it from shape 1

   -------------------------------------------------------------------

   [ shape 3 ]  a release is upgraded and goes back
        |
        v
   helm upgrade -> new revision -> readiness gate -> old pods retire
        |
        v
   helm rollback -> a REVISION is restored, not a value. Both values the
        |           upgrade changed come back together, because that is
        |           what a revision is.
        |
        |  the Terraform-owned namespace and the model cache claim are
        |  untouched in both directions: the namespace was present and the
        |  claim count was 1 before and 1 after, and real inference was
        |  served again afterwards.
        v
   tools/helm_upgrade_rollback records both directions

   The executed run was a deliberate upgrade and rollback, not a rollback
   provoked by a readiness failure. Nothing in this repository decides that
   a release should be rolled back; an operator does.
```

Six properties this flow commits to, and one it refuses:

- **Recovery is Kubernetes's, not InferOps's.** No component in this repository
  watches a pod, decides it is unhealthy, restarts it, or fails traffic over. The
  replica set and the endpoint slice do all of it, which is the direct consequence
  of the deployment split in section 2 and the reason that split is drawn there.
- **The API surviving the runtime is the point of the split.** In shape 1 the API
  keeps answering, with a canonical error, because it is a separate deployment. In a
  sidecar it would have gone with the runtime and the caller would have seen a
  connection failure instead of a retryable refusal.
- **A refusal arrives faster than a success does.** Once the Service has no ready
  endpoint the API refuses immediately rather than waiting out a timeout. That is a
  property worth drawing, because the alternative — hanging until a request timeout —
  is what a caller experiences as an outage rather than as an error.
- **The model cache is what makes recovery cheap.** A recreated pod reads the
  Terraform-owned claim rather than repeating a roughly 1.7 GiB download over a
  transport that does not validate certificates. That is the same argument section 4
  makes for the cache's placement, observed from the other end.
- **Readiness is the only gate.** A pod that is not ready is not in the endpoint
  slice, in all three shapes and in both directions of an upgrade. Liveness is a
  separate question and is asked at the socket, which is why shape 2 persists rather
  than restart-looping: the process is listening and is simply not ready.
- **A refusal is canonical, and names which refusal it is.** Shape 2's completion
  surface answered `capability-unavailable` with condition `runtime-unreachable` and
  `retryable: true` — not a timeout, not a bare 503, and distinguishable from a model
  that is merely still loading. That is the obligation §3 places on the API, observed.
- **Nothing here is an availability claim.** These are declared, authorized, local
  experiments on one provider and one host. They are not a recovery-time objective,
  an availability figure, an error budget, or evidence that any of this holds under
  a failure nobody provoked on purpose. No alert fired at anybody during any of
  them, because nothing routes an alert.

What is **not** drawn, because it does not exist: a health-based traffic decision
made by this project, a circuit breaker, a retry policy, a drain, a budget, a
notification path, and any failure of the cluster, the node, the disk, or the
control plane. Those were not provoked and nothing here would do anything about
them.

Every figure above is quoted from the record that produced it, and each record is
one run on one setup:

| Shape | Record |
|---|---|
| 1 — the serving pod lost under load | [Losing the inference pod while callers were waiting](../proof/serving/v1-s4-006-pr1-inference-pod-recovery.md) |
| 2 — the model that did not finish loading | [A model that did not become ready](../proof/serving/v1-s4-007-pr1-unready-model-recovery.md) |
| 3 — upgrade and rollback | [The upgrade and rollback experiment](../proof/environment/v1-s3-011-pr2-upgrade-rollback.md) |
| the earlier, narrower pod restart | [The Kubernetes pod-restart persistence result](../proof/serving/v1-s3-003-pr2-kubernetes-pod-restart.md) |

## 7. Proof and claim-evidence flow

Added on 2026-09-21, for the same reason as section 6: the register and the
dashboard were built in `V1-S4-009` and reconciled in `V1-S5-002`, and section 5's
evidence arrow stopped at `docs/proof/` without drawing what happens next.

Section 5 draws the first stage. This is the second, and it is **derived** rather
than written.

```text
   [ an executed run ]
        |  a human reads the output, records versions, environment,
        |  exact commands, results, limitations, and what was NOT run
        v
   [ a reviewed change ]  ------->  docs/proof/<area>/<record>.md
        |                           committed, immutable, never regenerated
        |                           by rerunning the thing it describes
        v
   [ the claim and evidence register ]
   docs/testing/claim-evidence-matrix.v1alpha2.json
        |  one row per published claim: its status and the limitation that
        |  travels with it, and every evidence record behind it -- each with
        |  its own level, what executed and was substituted, the environment
        |  and provider it ran on, and what it does not establish
        |
        |  a record may cite only files that exist, and may not carry a
        |  level its execution does not support
        v
   [ the proof dashboard ]  python -m tools.proof_dashboard
        |
        v
   docs/proof/dashboard.md  -- GENERATED. A test regenerates it and fails if
        |                      the committed page and the register disagree,
        |                      so the page cannot say more than the register
        |                      and the register cannot say more than a record
        v
   a reviewer reads one page and reaches every record behind it
```

Four rules this flow fixes, two of them new here:

- **The dashboard is derived, and is the one thing under `docs/proof/` that is.**
  Every other record there is written by a reviewed change and never regenerated.
  This page is regenerated from the register on every change and compared against
  it, which is the opposite discipline for the opposite reason: a summary that
  drifts from what it summarises is worse than no summary. Both rules are now in
  the ownership inventory, on separate rows, because one row could not carry both.
- **The register is the only place a claim's status is set.** A document that states
  a capability without a row behind it is a claim with no evidence path, and that is
  what the register exists to make visible.
- **Nothing in a cluster writes any of it.** Section 5's rule extends here unchanged.
  `tools.proof_dashboard` reads committed files and writes one committed file; it
  reads no cluster, runs no experiment, and produces no evidence of its own.
- **The dashboard is a repository-derived evidence view, not operational
  monitoring.** It answers *what has been proven*, from files. The
  [inference operations dashboard](../telemetry/inference-operations-dashboard.md)
  answers *what is happening now*, of a running release, and is a definition that no
  server serves. The two are not substitutes and neither is a monitoring system.

Who may move a row in the register is a governance question, and since 2026-09-21 it
has an answer: the `claim-evidence-sign-off` authority in
[ADR 0015](decisions/ADR-0015-v1-decision-ownership-and-sign-off-authority.md).
That names who is accountable. It changes no row, no level, and no evidence class,
and merging a change that sets a status leaves the record underneath it exactly as
strong as it was.

## 8. Trust boundaries

> [!WARNING]
> This section maps boundaries. It does **not** implement controls. Naming a boundary
> is not defending it.
>
> The threat model, the control set, and their verification are a separate decision,
> and it has since been made:
> [ADR 0008](decisions/ADR-0008-v1-security-baseline.md) and
> [the security baseline](../security/threat-model.md) adopt these five boundaries
> unchanged — a test compares the two documents verbatim — and add a sixth for
> publication, which a running system does not cross and this project crosses on
> every commit. What that record establishes is narrow: nothing in this repository
> authenticates a caller, authorises a request, enforces a network policy, or applies
> a security context to a pod it deployed.

```text
  ==================== outside anything this project controls =========
   model and image publishers, and the transport that delivers them
     defended by:  a pinned digest, a pinned revision, a per-file hash
                   verified before the bytes are used
     NOT defended: availability, and authenticity of the transport --
                   the downloader used in the trial does not validate
                   certificates, so the published hash carries the whole
                   integrity argument alone
  =====================================================================
                                 |
  ---- B1: the artifact boundary --------------------------------------
                                 |
  ==================== the contributor's machine ======================
   container engine, cluster, kubeconfig with a client key, image cache
     defended by:  project-scoped kubeconfig ignored by version control,
                   an identity guard that refuses to act on a cluster
                   it cannot positively identify -- `kind` by pinned
                   cluster name, Docker Desktop by binding its node
                   container to the API server port the verified
                   kubeconfig dials (ADR 0011) -- scoped teardown
     NOT defended: a second cluster deliberately given this project's
                   name satisfies every check
  =====================================================================
                                 |
  ---- B2: the cluster boundary ---------------------------------------
                                 |
  ==================== inside the cluster =============================
                                 |
   +-- B3: the namespace boundary ---------------------------------+
   |                                                               |
   |   +-- B4: the workload boundary ---------------------------+  |
   |   |  API pod            runtime pod                        |  |
   |   |  intended:          proven once in a trial:            |  |
   |   |  non-root, least    non-root uid 65534, read-only      |  |
   |   |  privilege          root filesystem, all capabilities  |  |
   |   |                     dropped, no privilege escalation   |  |
   |   +--------------------------------------------------------+  |
   |                                                               |
   |   secret material: referenced by name, never templated with   |
   |   a value, never present in a contract, owned by the team     |
   +---------------------------------------------------------------+
  =====================================================================
                                 |
  ---- B5: the caller boundary ----------------------------------------
                                 |
   a caller reaching the API. In V1 this is a port-forward: no ingress
   controller and no load-balancer implementation is installed, and
   no authentication or authorization component exists.
```

| Boundary | What crosses it | Enforced today | Owned by |
|---|---|---|---|
| B1 artifact | Container images, model weights | Digest and hash pinning, hash verified before use | The pinning rules in ADR 0002 |
| B2 cluster | Every platform action on Kubernetes | Cluster identity guard and scoped teardown, in the environment scripts. Both providers have a guard: `kind`'s binds nodes to kind-labelled containers, Docker Desktop's binds them to a container on this engine and to the API server port the verified kubeconfig dials. Neither can refuse a cluster deliberately named to impersonate the other | ADR 0001 D5 and D6; [ADR 0011](decisions/ADR-0011-external-local-cluster-provider-contract.md) |
| B3 namespace | Everything a release installs | A rendered default-deny, which the local cluster's network plugin was measured not to enforce | [ADR 0008](decisions/ADR-0008-v1-security-baseline.md) |
| B4 workload | Process privilege inside a pod | Rendered and deployed workloads carry the documented pod-security settings. Nothing here reads a pod this platform deployed and no admission control constrains one, so nothing enforces it | [ADR 0008](decisions/ADR-0008-v1-security-baseline.md) |
| B5 caller | Inference requests and their responses | **Nothing.** There is no authentication, no authorization, no rate limit, and no tenant isolation | [ADR 0008](decisions/ADR-0008-v1-security-baseline.md) |

The tenant field is the one worth calling out here, because getting it wrong is how
multi-tenancy leaks. A tenant written into a contract is a **request**, not an
assertion. It must be validated against the owning team's entitlement before it is
used for isolation, attribution, or authorisation, and it must never be trusted
because a client supplied it. Nothing validates it today, and B5 is where that
validation would have to live.

That rule now has a home rather than only a paragraph: it is `T-08` in
[the threat model](../security/threat-model.md), the control for it is
`specified-only` because the component that would apply it does not exist, and
`DR-03` carries what stays open.

## 9. What this architecture is not

- **It is not a production topology.** Single node, single replica, single model,
  one host, one operating system, one architecture. There is no ingress, no load
  balancing, no autoscaling, no multi-model routing, and no high availability.
- **It is not a serving platform.** The serving runtime is a third-party process
  this project configures and calls. Replacing it is a design goal; running several
  of them, batching across them, or scheduling them is not.
- **It does not describe any project other than this one.** The boundary rules for
  work that lives elsewhere are in
  [the project boundaries document](project-boundaries.md).
- **It is not a monitoring or alerting system.** A collector scrapes inside one
  release and writes to an `emptyDir`. A dashboard definition and six alert
  definitions are committed files. No durable store, no dashboard server, and no
  alert routing path is selected, so nothing has ever notified anybody.
- **It is not a cost system.** A cost figure is computed by a repository tool from
  a committed method and committed prices, under
  [ADR 0014](decisions/ADR-0014-v1-cost-calculation-reaches-the-estimated-basis.md).
  No component in the platform computes one, no invoice has been read, and no cost
  figure is published.
- **It is not self-healing.** Section 6 draws what recovers a lost pod, and all of
  it is Kubernetes. Nothing in this repository observes a running system, decides it
  is unhealthy, or acts on that.
- **It is not a general claim.** Components drawn here have served real requests
  through this architecture — first once in `V1-S3-011`, and several hundred more
  since across declared load, performance, failure, and clean-clone experiments.
  Every one of them was on `docker-desktop`, on one Windows host, on CPU, with one
  replica of each tier, and with the multi-replica profile refused at the capacity
  gate. (This bullet said "once" until 2026-09-21, which was true when it was
  written and stopped being true at `V1-S4-003`.) More executions do not widen the
  claim: they are the same one setup, measured more times. A drawing is not the
  evidence; the records under [`docs/proof/`](../proof/README.md) are, and no result
  on one provider is a result on the other.

## Related records

| Topic | Document |
|---|---|
| The decision this document implements | [ADR 0004](decisions/ADR-0004-component-and-ownership-boundaries.md) |
| Who owns an accepted decision, and who signs off a claim or a release | [ADR 0015](decisions/ADR-0015-v1-decision-ownership-and-sign-off-authority.md), and [the decision-authority register](../governance/decision-authority.md) |
| What has been proven, as one generated page | [The V1 proof dashboard](../proof/dashboard.md) |
| Every published claim and the evidence behind it | [Claim and evidence matrix](../testing/claim-evidence-matrix.md) |
| The lane that runs the checks, and the gates in it | [ADR 0012](decisions/ADR-0012-continuous-integration-service.md), and [the gate matrix](../testing/ci-gate-matrix.md) |
| What a bounded local performance figure may say | [ADR 0013](decisions/ADR-0013-bounded-local-performance-observations.md) |
| How a cost figure is produced, and what it may be called | [ADR 0014](decisions/ADR-0014-v1-cost-calculation-reaches-the-estimated-basis.md), and [the cost method](../cost/cost-method.md) |
| What a running release reports about itself | [The inference operations dashboard](../telemetry/inference-operations-dashboard.md) |
| Reproducing all of it from a clean clone | [The clean-clone workflow](../environment/clean-clone.md) |
| Who owns each resource, as data | [`resource-ownership.v1alpha1.json`](resource-ownership.v1alpha1.json) |
| Who owns each resource, explained | [Resource ownership](resource-ownership.md) |
| What belongs here and what does not | [Project boundaries](project-boundaries.md) |
| The review checklist for both | [Boundary review checklist](boundary-review-checklist.md) |
| The environment this runs inside | [ADR 0001](decisions/ADR-0001-local-development-environment.md) |
| The runtime and model it serves | [ADR 0002](decisions/ADR-0002-model-and-serving-runtime.md) |
| The contract it starts from | [WorkloadContract v1alpha1](../contracts/workload-contract.md) |
| Why a mock may not certify serving | [The mock and real serving boundary](../serving/mock-and-real-boundary.md) |
| The threats these boundaries face, and what is done about them | [The V1 security baseline](../security/README.md) |
