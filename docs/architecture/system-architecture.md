# V1 system architecture

Status: **accepted as the V1 design boundary**, in
[ADR 0004](decisions/ADR-0004-component-and-ownership-boundaries.md). Every
component below the contract layer is **unbuilt**. This document describes what V1
is allowed to become, not what exists.

> [!IMPORTANT]
> Read every box in every diagram as a design commitment unless it is marked
> otherwise. Exactly four things drawn here exist today: the workload contract and
> its validator, the local Kubernetes cluster, the serving runtime and model that
> were selected on executed proof, and the evidence records. Nothing serves a
> request through this architecture, because no platform API, adapter, chart, or
> Terraform configuration has been written.
>
> The ownership half of this design is machine-checked. The component half is not:
> there is no code for a test to check it against, and this document says so rather
> than implying that a diagram constrains anything on its own.

## What this document is for

A reviewer should be able to answer six questions from it without reading a plan:

1. Who talks to InferOps, and what does InferOps talk to?
2. What are the components, and which of them may depend on which?
3. What happens to an inference request, including when the model is not ready?
4. What happens when a workload is deployed, and who creates each object?
5. Where does telemetry go, and where does evidence come from?
6. Where are the trust boundaries, and what is *not* defended at each one?

The lifecycle answer to question 4 is data rather than prose. It lives in
[`resource-ownership.v1alpha1.json`](resource-ownership.v1alpha1.json) and is
explained in [the resource ownership document](resource-ownership.md).

## How these diagrams are maintained

They are ASCII inside fenced blocks, for one reason: a diagram that cannot be read
in a plain `git diff` is a diagram that stops being reviewed. The repository has no
diagram toolchain, no renderer, and no continuous-integration lane to run one in,
so a Mermaid or image-based diagram would introduce a dependency nothing here can
check. The cost is real — these are harder to lay out and cannot express much — and
if a diagram ever needs more than boxes and arrows, that is the moment to revisit
the choice rather than to draw a worse ASCII picture.

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

- **The cluster is not InferOps's.** It belongs to the contributor's machine and is
  created and destroyed by the environment scripts. The platform acts inside a
  cluster it may not create, reconfigure, or delete. That boundary is what keeps a
  contributor's unrelated clusters out of reach, and it was tested by attacking it
  rather than by assuming it.
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
   |  Platform domain                                        PARTIAL |
   |  workload identity, model and runtime selection, resource and   |
   |  scaling policy, environment and ownership metadata, security   |
   |  classification, attribution           <- typed objects EXIST   |
   |  canonical errors, validation rules, policy    <- UNBUILT       |
   |                                                                 |
   |  owns the serving-adapter interface; depends on no adapter,     |
   |  no Kubernetes client, no Helm, and no runtime SDK              |
   +-----+-----------------------------------------------------+-----+
         ^                                                     |
         | implements the interface                            | renders
         | the domain owns                                     v
   +-----+------------------------+   +----------------------------------+
   |  Serving adapters   UNBUILT  |   |  Deployment rendering    UNBUILT |
   |                              |   |  a validated domain object       |
   |  +------------+ +---------+  |   |  becomes chart values, and       |
   |  | mock       | | real    |  |   |  nothing else writes them        |
   |  | CI only    | | runtime |  |   +----------------+-----------------+
   |  +------------+ +----+----+  |                    |
   +---------------------|--------+                    v
                         |                +--------------------------+
   +---------------------|--------+       |  Helm chart      UNBUILT |
   |  InferOps API       |UNBUILT |       |  and its values schema   |
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
   |  dependency; not yet deployed  |        |  UNBUILT               |
   |  by this platform              |        +------------------------+
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
this distribution. What is still unbuilt is the rest of the box: the validation
rules that decide whether a contract is accepted, the canonical error surface, and
the adapter interface itself.

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
limits, queueing, and back-pressure. Every request in the one executed trial was
single and sequential; the runtime reported four slots and one was ever used. A
design for behaviour under concurrency would be an estimate wearing a diagram's
clothes.

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
   [ contributor host ]                                     one time
       create the cluster, load locally built images
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

   cluster teardown      removes the cluster itself, by the environment
                         scripts, not by either tool.
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
                   |  Collector and store          |
                   |  NOT SELECTED. Nothing scrapes|
                   |  these endpoints today, and   |
                   |  the ownership inventory      |
                   |  records the gap rather than  |
                   |  assigning it to a tool by    |
                   |  accident.                    |
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
[the certification levels](../testing/certification.md). Both are catalogues of
components that do not exist yet, and both say so.

Nothing about the three rules above changed when they were written down in detail.
The catalog turns the third one into arithmetic — a field's placement is derived from
its sensitivity and its cardinality rather than chosen — and gives the second one an
empty placement list rather than a convention.

## 6. Trust boundaries

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
                   this project did not create, scoped teardown
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
| B2 cluster | Every platform action on Kubernetes | Cluster identity guard and scoped teardown, in the environment scripts | ADR 0001 D5 and D6 |
| B3 namespace | Everything a release installs | Nothing. A network policy is planned and its enforcement by the local cluster's network plugin is untested | [ADR 0008](decisions/ADR-0008-v1-security-baseline.md) |
| B4 workload | Process privilege inside a pod | Proven once for the runtime pod in a trial. Nothing enforces it for a pod this platform deploys, because it deploys none | [ADR 0008](decisions/ADR-0008-v1-security-baseline.md) |
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

## 7. What this architecture is not

- **It is not a production topology.** Single node, single replica, single model,
  one host, one operating system, one architecture. There is no ingress, no load
  balancing, no autoscaling, no multi-model routing, and no high availability.
- **It is not a serving platform.** The serving runtime is a third-party process
  this project configures and calls. Replacing it is a design goal; running several
  of them, batching across them, or scheduling them is not.
- **It does not describe any project other than this one.** The boundary rules for
  work that lives elsewhere are in
  [the project boundaries document](project-boundaries.md).
- **It is not evidence.** No component drawn here has served a request through this
  architecture, because most of them do not exist.

## Related records

| Topic | Document |
|---|---|
| The decision this document implements | [ADR 0004](decisions/ADR-0004-component-and-ownership-boundaries.md) |
| Who owns each resource, as data | [`resource-ownership.v1alpha1.json`](resource-ownership.v1alpha1.json) |
| Who owns each resource, explained | [Resource ownership](resource-ownership.md) |
| What belongs here and what does not | [Project boundaries](project-boundaries.md) |
| The review checklist for both | [Boundary review checklist](boundary-review-checklist.md) |
| The environment this runs inside | [ADR 0001](decisions/ADR-0001-local-development-environment.md) |
| The runtime and model it serves | [ADR 0002](decisions/ADR-0002-model-and-serving-runtime.md) |
| The contract it starts from | [WorkloadContract v1alpha1](../contracts/workload-contract.md) |
| Why a mock may not certify serving | [The mock and real serving boundary](../serving/mock-and-real-boundary.md) |
| The threats these boundaries face, and what is done about them | [The V1 security baseline](../security/README.md) |
