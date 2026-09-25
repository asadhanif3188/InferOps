# InferOps V1: an engineering case study

Status: **draft**, written in `V1-S5-007-PR1`. It is not published: nothing links to it
from the README, and it may change in any sentence before it is. It was written against
an evidence pack that is **not frozen**. The release gate that decides the freeze is
incomplete while five certified claims rest on records whose repository code nothing
identifies, and `python -m tools.evidence_index --gate` exits 1 until each is closed.
Those five are named where this draft leans on them and in
[the claims appendix](#appendix-the-claims-this-draft-relies-on). Verifying every
sentence against a frozen pack, and publishing, belong to the next change.

Every figure below is quoted from a committed record, and
[`v1-engineering-case-study.v1alpha1.json`](v1-engineering-case-study.v1alpha1.json)
names the file and the field or the sentence each one is read from.
[`tests/testing/test_case_study.py`](../../tests/testing/test_case_study.py) reads every
one of them back, recomputes every count this page states from the register, and
fails if a claim this page cites changes status, level, or blocker state without the
page changing with it. It checks citations and figures. Whether a sentence says what
its record says is a reading, and no test performs one.

> [!IMPORTANT]
> **Every real result in this study is one provider, one host, one replica.** Docker
> Desktop's Kubernetes (`docker-desktop`), one Windows workstation, CPU only, one
> replica of each tier. No figure here is a capacity, a service-level objective, an
> availability figure, or a benchmark, and none describes `kind`, Linux, macOS, a GPU,
> another model, or another runtime version. The evidence levels `C0` to `C4` used
> below are [InferOps Evidence Levels](../testing/evidence-levels.md): **project-defined,
> and not an ISO, NIST, regulatory, or industry certification standard.**

## 1. Why LLM serving needs a paved road

Serving a language model is easy to demonstrate and hard to state honestly. A
container starts, a prompt goes in, text comes out, and the demonstration is over. What
the demonstration does not show is everything this project had to learn on its own
path before a completion could be called evidence. Each of the following was found
here, on this project's host, and none is offered as a survey of anybody else's.

- **A model is a large artifact with an identity.** The selected weights are a
  1.71 GiB file. A moving tag is not a pin, so the file is fetched at a named revision
  and its SHA-256 compared before anything loads it; the download on the clean-clone
  run stopped twice and resumed by byte range both times.
- **Start-up takes minutes, and the orchestrator has to know that.** On the clean-clone
  run the pinned runtime became ready in 183 015 ms against a 300 000 ms budget. A
  liveness probe that treated loading as failure would kill the process it was waiting
  for. The chart asks liveness at the socket and readiness at the model, and a
  release starved of processor stayed alive and unready for 179 755 ms without a
  single restart.
- **Memory accounting does not mean what it appears to.** The runtime memory-maps its
  weights, and two identical pods were observed reporting 2.167 GiB and 531 MiB for the
  same work, because the kernel charges mapped pages to whichever group faults them in
  first. A limit sized from the smaller figure fails as silent eviction, not as an
  error.
- **The signal an operator reaches for first can be wrong.** When the serving pod was
  deleted under load, the deleted pod went on reporting `Ready: True` for the whole
  outage while the Service had no ready endpoint, and scrape health said the job was up
  throughout.
- **A figure is a property of its setup.** One single-slot runtime, one fixed prompt:
  adding concurrent callers added waiting and no completed requests. Quoted without
  that setup, the same figure is a capacity claim nobody measured.
- **A mock can pass every API test while nothing is served.** A mock is necessary for
  fast checks and worthless as evidence that a model answers, and the two are easy to
  confuse once both are green.

A paved road is the answer to that list: one way to go from a workload description to
real, observed inference, in which each of those lessons is encoded once — in a
contract, a pinned runtime and model, a probe split, a cluster guard, canonical errors,
telemetry, and a register that refuses to publish a claim without its evidence — so
that the next workload does not have to rediscover them.

**Evidence.** [The clean-clone run](../proof/environment/v1-s5-001-pr2-clean-clone-run.md),
[the unready-model record](../proof/serving/v1-s4-007-pr1-unready-model-recovery.md),
[the system architecture's deployment argument](../architecture/system-architecture.md#why-the-runtime-is-a-separate-deployment-rather-than-a-sidecar),
[the pod-recovery record](../proof/serving/v1-s4-006-pr1-inference-pod-recovery.md),
[the performance findings](../proof/serving/v1-s4-004-pr2-performance-findings.md), and
[the mock and real boundary](../serving/mock-and-real-boundary.md). Claims
`the-model-artifact-matches-its-published-hash`,
`a-reviewer-can-reproduce-v1-from-a-clean-clone`,
`an-unready-model-was-held-unready-and-recovered-by-an-operator`,
`caller-visible-impact-of-losing-the-inference-pod-was-measured-under-load`,
`a-bounded-local-performance-matrix-was-measured-and-a-degradation-point-observed`,
`a-mock-result-can-never-certify-real-runtime-behaviour`.

## 2. Who it is for, and what bound it

Three readers are served, and they want different things:

- **A workload owner** — an application team — writes a `WorkloadContract` document and
  wants a validated, scaffolded workload and a serving endpoint without learning the
  runtime's probe semantics.
- **A platform contributor or operator** owns the cluster and the host, runs the
  releases, and needs to know what the platform will and will not do to either.
- **A reviewer** wants to know what has been proven and what has not, without the
  author present.

V1 was bound by the host it had and by rules it set itself:

- **One host.** A Windows workstation whose container virtual machine had 7.60 GiB of
  memory, an AVX2 processor without AVX-512, and no discrete accelerator. The CPU path
  was mandatory, and the host met the minimum tier and not the recommended one.
- **No paid API and no account.** The serving path had to use an openly licensed model
  and a runtime anyone can fetch anonymously.
- **The cluster is the operator's.** InferOps may not create, reset, or delete a
  cluster, so it consumes one the operator already has, selected explicitly.
- **Nothing is published without its evidence.** Every capability claim is a row in a
  register with the limitation that travels with it, a certified one is bound to the
  executed records behind it, and the pages a reader meets are derived from that
  register or checked against it.

**Evidence.** [ADR 0002's context](../architecture/decisions/ADR-0002-model-and-serving-runtime.md#context),
[ADR 0011](../architecture/decisions/ADR-0011-external-local-cluster-provider-contract.md),
and [the claim and evidence register](../testing/claim-evidence-matrix.md). Claims
`inferops-consumes-an-operator-owned-cluster-and-verifies-it-before-mutating`,
`a-runtime-and-model-pair-was-selected-by-a-recorded-feasibility-procedure`.

## 3. The architecture and the self-service contract

```text
  workload owner                                         reviewer
       | writes a WorkloadContract v1alpha1                  | reads
       v                                                     v
  contract validation --> platform domain            claim register --> proof dashboard
  (schema + cross-field    (typed objects,            (every claim bound    (generated,
   rules, canonical         model/runtime              to records and a      never typed)
   refusals)                selection, policy)         limitation)
                                  |                          ^
                                  v                          | records, written by
                    deployment rendering: UNBUILT            | reviewed changes
                    (a values file is written by hand)       |
                                  |                          |
                                  v                          |
  serving path: a Docker composition on one host, or a Helm release on Terraform
  prerequisites in the operator's cluster
     InferOps API (five routes, adapter chosen by name, never by fallback)
        mock adapter -> deterministic fixture, loads no model
        real adapter -> llama.cpp server, digest-pinned, serving a hash-verified
                        Qwen3-1.7B GGUF from a Terraform-owned model cache
     release-scoped Prometheus collector, a checked dashboard, six alert definitions
```

The self-service surface is the contract. A workload owner writes a `WorkloadContract`
`v1alpha1` document; the validator refuses a malformed one with a canonical error code,
a stable rule identifier, and a field location the contract document publishes; the
platform domain parses a valid one into typed objects; and the scaffolder renders a
workload project — a contract document and the tests that go with it — for the mock and
synchronous profiles, without overwriting anything.

**Where the self-service road stops.** Nothing yet turns a validated contract into
release values. A values file is written by hand, so the two claims that would close
the loop — that a described workload is served, and that deployment values come only
from a validated document — are `planned`, not certified. This is the most important
unbuilt component in V1, and the draft says so here rather than in a footnote.

Three structural decisions carry most of the design:

- **The domain depends on nothing.** No module under the platform domain may import a
  Kubernetes client, Helm, a runtime SDK, or an HTTP framework, and a test reads every
  module to hold that. Adapters implement an interface the domain owns, and the API
  chooses one at composition time.
- **The runtime is its own deployment, not a sidecar.** The API stays up and answers
  with a canonical error while the model loads or the runtime is gone. The cost is a
  network hop and a failure mode — the API healthy while its runtime is unreachable —
  that therefore has to be a first-class error.
- **Terraform owns what outlives a release; Helm owns the release.** The model cache
  claim and the namespace are prerequisites, so a replaced pod reads the cached
  artifact rather than repeating the download.

**Evidence.** [The system architecture](../architecture/system-architecture.md),
[ADR 0004](../architecture/decisions/ADR-0004-component-and-ownership-boundaries.md),
[the workload contract](../contracts/workload-contract.md), and
[resource ownership](../architecture/resource-ownership.md). Claims
`the-workload-contract-and-its-rejection-matrix-are-published`,
`an-invalid-workload-document-is-refused-with-a-published-reason`,
`the-workload-domain-parses-a-contract-document-into-typed-objects`,
`a-workload-scaffold-is-generated-without-overwriting-anything`,
`the-inference-api-serves-five-routes-with-explicit-adapter-selection`,
`no-resource-in-the-architecture-has-two-owners`,
`the-platform-serves-a-workload-the-contract-describes`,
`deployment-values-derive-only-from-a-validated-document`.

## 4. Choosing a runtime and a model

The runtime and model were chosen by a feasibility procedure with twelve thresholds
written down before the trial, so that the trial had something to fail against.
Licence and immutability were gates rather than weights: a candidate that could not be
redistributed without a field-of-use restriction, or whose bytes could not be named
and fetched again by digest, was not compared on anything else.

- **Runtime: llama.cpp `llama-server`**, pinned by image digest. Its CPU path on AVX2
  is the designed path rather than a degraded one, it exposes health that reports
  not-ready while loading, and it serves native metrics. vLLM's CPU backend was set
  aside because its own documentation puts CPUs without AVX-512 on a limited path;
  Ollama because it exposes no metrics endpoint of its own; the archived Text
  Generation Inference project on maintenance status; serving platforms because they
  would add a second orchestration layer inside a cluster InferOps already
  orchestrates; and hosted APIs by requirement.
- **Model: Qwen3-1.7B, the publisher's own `Q8_0` GGUF**, pinned by revision and
  SHA-256. `Q8_0` over a smaller community quantisation kept the pinned artifact the
  publisher's own file at the price of disk and decode speed. 1.7B over 0.6B because a
  path that only works with a model too small to be worth serving proves very little.
  Llama 3.2 was excluded on licence, and 7B-class models on the host's memory.

Every rejection above was read from the candidates' own documentation; only the
selected pair was executed.

Eleven of the twelve thresholds were met. **One blocking threshold was not**: the
runtime exposes token counters and no cumulative request counter. The pair was
accepted with that exception argued in the open — the platform receives the requests,
so the platform counts them — and the decision record says plainly that narrowing a
threshold after seeing the measurement is the move pre-registration exists to prevent.
That is the first trade-off in this project that a reviewer may reasonably reject, and
the record keeps everything needed to do so.

**Evidence.** [ADR 0002](../architecture/decisions/ADR-0002-model-and-serving-runtime.md)
and [the feasibility record](../proof/serving/v1-s0-003-pr2-runtime-feasibility.md).
Claims `a-runtime-and-model-pair-was-selected-by-a-recorded-feasibility-procedure`,
`the-model-artifact-matches-its-published-hash`.

## 5. Local and Kubernetes implementation

**Locally**, one guarded workflow acquires the model at its pinned revision, verifies
its hash, starts the digest-pinned runtime, starts a real-adapter API in front of it,
sends one completion, asserts the real identity, and tears both down. Every step that
touches the network, the container engine, or the model asks for consent by flag, and
none falls back to a mock. In the clean-clone run the runtime became ready in
183 015 ms and the completion returned in 3 641 ms with 43 tokens. That readiness
margin is thin on this host: on the same day an earlier attempt failed that step twice,
and its record infers, without having observed it, that the budget was spent.

**In Kubernetes**, the operator selects a provider by name and InferOps verifies the
target positively before mutating anything; it creates and deletes no cluster.
Terraform applies the namespace and the model cache claim, Helm installs the release,
an init container compares the model's hash inside the cluster, and a real completion
is served through the release's own Service.

**From a clean clone**, one workflow walks the whole journey — prerequisites, two
continuous-integration gates, scaffolding, model acquisition, local real inference,
provider verification, Terraform, Helm install, upgrade, and rollback, Kubernetes
inference, telemetry, load, a pod-loss experiment, scoped cleanup, and a check that
the operator's cluster survived — and keeps a ledger of every step. It completed all
18 steps in 1 h 30 min 32 s of wall clock across three invocations, on its third
attempt: the first two stopped on five defects of the repository, each fixed before
the next attempt ran. No second engineer has repeated it.

Two of the Kubernetes lifecycle claims are **release blockers** today: the Helm
uninstall's clause that the operator's cluster, node, and storage class survive, and
the upgrade-and-rollback experiment. Both executed and both were recorded, and in
neither does the record identify the repository code that ran. The same holds for the
optional `kind` helper and for the pod-replacement run that showed the model artifact
surviving on the Terraform-owned claim.

**Evidence.** [Real-runtime certification](../proof/serving/v1-s2-004-c2-certification-result.md),
[the Docker Desktop paved road](../proof/environment/v1-s3-011-pr1-docker-desktop-paved-road.md),
[the upgrade and rollback experiment](../proof/environment/v1-s3-011-pr2-upgrade-rollback.md),
and [the clean-clone run](../proof/environment/v1-s5-001-pr2-clean-clone-run.md). Claims
`the-selected-model-serves-a-real-completion-through-the-inferops-api`,
`inferops-consumes-an-operator-owned-cluster-and-verifies-it-before-mutating`,
`the-selected-runtime-serves-a-real-completion-in-a-cluster`,
`a-reviewer-can-reproduce-v1-from-a-clean-clone`,
`a-helm-release-installs-and-uninstalls-without-residue`,
`a-controlled-release-change-can-be-reversed-and-real-inference-restored`,
`a-local-cluster-is-created-and-removed-without-residue`,
`the-model-artifact-survives-a-pod-replacement-on-a-terraform-owned-claim`.

## 6. How a claim becomes publishable

The rule the project holds itself to is that **the strength of a claim must not exceed
the evidence supporting it.** Each public claim is one row in
[the claim and evidence register](../testing/claim-evidence-matrix.md), and every row
has the same chain: a statement; the implementation that makes it true; the tests that
would fail if it stopped being true; the continuous-integration gates that run them;
one or more evidence records, each at its own level, naming what executed, what was
substituted, the workload, and where it ran; and the limitation and the boundary of
what it does not establish. The README's entry points must each be governed by a row,
[the proof dashboard](../proof/dashboard.md) is generated from the register, and a test
refuses either if it disagrees.

Two things are kept apart on purpose. A claim's **status** says whether the project
publishes the property at all: `certified`, `planned`, `deferred`, or `not-claimed`. An
**evidence level** belongs to one record and says only how that record was obtained:
`C0` Static, `C1` Substituted Execution, `C2` Runtime, `C3` Representative, and `C4`
Operational. A mock, a simulation, or an estimate cannot certify real runtime
behaviour, and a workload's origin — synthetic or not — does not by itself lower a
level. Failure, composition, provider, and hardware are separate metadata, never a
level.

Today the register holds 59 claims: 42 certified, 7 planned, 1 deferred, and 9 not
claimed. Behind them are 60 evidence records: 26 at `C0`, 8 at `C1`, 26 at `C2`, and
none at `C3` or `C4`. Nothing here is `C3`, because no experiment was run under a
deliberately representative workload with stated criteria; nothing is `C4`, because
there is no production operation to observe.

**The pack is not frozen.** The completeness check that stands before a freeze read how
every executed record identifies the code that ran. 16 of the 34 executed records name
the revision that ran. Where a certified statement rests on a record that identifies its
code by nothing better than a branch name, a chart version label, or a revision dated
after the run, and no other record supports it, the claim is a
release blocker, and there are 5 release blockers. Each names the run that would close
it and the status decision that could replace the run. None of the five has been
closed.

**Evidence.** [InferOps Evidence Levels](../testing/evidence-levels.md),
[ADR 0016](../architecture/decisions/ADR-0016-inferops-evidence-level-model.md),
[the V1 evidence index](../proof/v1-evidence-index.md), and
[the completeness check](../proof/testing/v1-s5-006-pr2-evidence-completeness.md).
Claims `published-documents-link-only-to-things-that-exist`,
`the-published-strategy-and-its-data-cannot-drift-apart`,
`a-mock-result-can-never-certify-real-runtime-behaviour`,
`every-certifying-record-lives-under-docs-proof-and-declares-its-own-boundary`.

## 7. Experiments and what they found

Four experiments were run against a real release on `docker-desktop`, each once or
twice, each from a descriptor registered before it ran. Every figure is published under
[ADR 0013](../architecture/decisions/ADR-0013-bounded-local-performance-observations.md),
which allows a bounded observation of one declared experiment to be published with its
setup named, and refuses capacity, service-level objectives, availability figures,
benchmarks, and any reading of one provider's figures as another's.

### Declared load, and where that setup degraded

The committed load profile — a three-request warm-up, then 60 requests each at
concurrency 1, 2, and 4, closed loop, one fixed prompt of 35 input tokens — ran twice
against one single-replica release whose runtime had one parallel slot and a six-core
limit. All 360 measured requests answered `HTTP 200`, and so did the warm-ups. Completed requests stayed
between 0.554 and 0.575 per second at every level, while median latency rose about
twofold and fourfold. **For that setup, the observed degradation point is concurrency
2**: adding callers added waiting and no completed requests beyond the difference
between the two runs.

What limited it is correlated, not established. The runtime never processed more than
one request at a time and deferred the rest, and its container used 99.1–99.9% of its
processor limit, averaged over each measured phase, at every level, the baseline
included. Whether the single slot or the
processor bound the rate was not tested, and processor throttling was not sampled. The
prompt-token totals are consistent with nearly every request reusing a cached prompt,
so every service time here is for a prompt the runtime had almost entirely seen.

One finding is about observation rather than serving: the dashboard's latency and rate
panels, read at a phase's end, are **not** that phase's figures, because they take a
five-minute window over phases shorter than two minutes. The raw record sets are the
source for a level's own distribution.

### Losing the serving pod under load

One serving pod was deleted by name while the load profile was running. The
replacement reported itself Ready 33 665 ms after the delete. Callers saw a 31 960 ms
outage in which 40 of the 41 requests dispatched were refused — fast, between 20 ms and
83 ms each, with `503` `capability-unavailable`, because the API refuses immediately
once the Service has no ready endpoint. The one request already in flight when the pod
went was a different shape: it hung and came back `500`. Nothing in the workflow
intervened between the delete and its closing uninstall; the replica set and the
endpoint slice did all of the recovering.

The finding that matters most is the disagreement already quoted in section 1: pod
readiness reported a healthy replica for the whole outage. The signal that tracked what
a caller could reach was the Service's ready-endpoint count, and the one that named
what went wrong was the API's error counter by canonical code. One replica is the
cause of the outage, and the experiment says nothing about what a second would change.

### A model that did not become ready

A release was installed with one committed overlay that starves the runtime of
processor, so the process starts, binds its port, begins loading, and does not finish.
It was held there for 179 755 ms — 30.0% of the runtime's own 600 000 ms startup budget
— with readiness sampled from four places that all agreed, and liveness restarting
nothing. Dropping the overlay and upgrading returned it to a served completion.

Every completion asked in that window came back `capability-unavailable` with condition
`runtime-unreachable` and `retryable: true`. **None came back `model-not-ready`**,
the code the adapter gives a runtime it can reach that answers `Loading model`: the
readiness probe had already removed the runtime's only address from its Service before
the adapter could see that answer. Which canonical error a caller meets is decided by
the topology, and that was written down nowhere before the run. It is also a reason
the claim that an unready model produces a canonical error of its own stays
`planned`.

### The whole journey from a clean clone

Described in [section 5](#5-local-and-kubernetes-implementation). Its most useful
output was not its duration but its five defects: a test suite inheriting the
operator's provider selection, a certification that called a spent readiness budget
"unexpected", a test writing a diagnostics record into the checkout, a residue check
asked once instead of within a bound, and three network sources the consent flags did
not name. None was a host problem.

**Evidence.** [The performance findings](../proof/serving/v1-s4-004-pr2-performance-findings.md),
[the pod-recovery record](../proof/serving/v1-s4-006-pr1-inference-pod-recovery.md),
[the unready-model record](../proof/serving/v1-s4-007-pr1-unready-model-recovery.md),
and [the clean-clone run](../proof/environment/v1-s5-001-pr2-clean-clone-run.md). Claims
`repeatable-llm-load-can-be-generated-from-a-versioned-profile`,
`a-bounded-local-performance-matrix-was-measured-and-a-degradation-point-observed`,
`caller-visible-impact-of-losing-the-inference-pod-was-measured-under-load`,
`an-unready-model-was-held-unready-and-recovered-by-an-operator`,
`a-reviewer-can-reproduce-v1-from-a-clean-clone`,
`a-model-that-is-not-ready-is-a-canonical-error`.

## 8. Telemetry: what the signals did and did not show

The API emits eight catalog metrics and structured request records, each inside a
declared series budget, and the telemetry catalog gives a prompt, a response, a
provider error body, and a secret no permitted placement at all. A release-scoped
Prometheus collector scraped both InferOps jobs on `docker-desktop`. A real Prometheus
evaluated all 30 panel expressions of the operations dashboard in nine controlled
states, and a real Grafana rendered all 29 panels. Six alerts are published, each with
an owner, a severity, an evidence query, and a runbook section; five were replayed over
the telemetry three real experiments recorded, and one fired.

What the experiments added is a list of what the signals **cannot** do. Scrape health
stayed up through an outage. Pod readiness lied about a deleted pod. A dashboard panel
at a phase end mixes that phase with the ones before it. Two registered series,
`inferops_model_ready` and container restarts, are still emitted by nothing. The
collector's series live in an `emptyDir` and vanish with the release, and nothing
evaluates or routes an alert to anybody.

**Evidence.** [The dashboard validation](../proof/telemetry/v1-s4-002-pr2-dashboard-validation.md),
[the alert validation](../proof/telemetry/v1-s4-008-pr1-alert-validation.md), and
[the operator runbook](../environment/operator-runbook.md). Claims
`the-api-emits-catalog-metrics-and-structured-request-records`,
`the-telemetry-catalog-cannot-admit-a-prompt-or-an-unbounded-label`,
`a-release-scoped-collector-scrapes-both-inferops-jobs-on-the-reference-provider`,
`the-inference-operations-dashboard-was-asked-of-a-real-prometheus-and-rendered`,
`six-v1-alerts-carry-an-owner-a-severity-an-evidence-query-and-a-runbook-link`,
`the-v1-alerts-were-replayed-over-the-telemetry-three-real-experiments-recorded`,
`a-v1-operator-runbook-covers-every-incident-class-and-every-alert-links-into-it`,
`an-alert-reaches-somebody`.

## 9. Cost: a method, not a price

V1 publishes a cost **method** and no figure for what running the workload costs on a
provider. The reason is structural rather than cautious: a cost per request is a price
divided by a throughput, and publishing the quotient publishes the divisor, which is
one setup's observation and nothing more. The method is amended to reach the estimated
basis only, every amount must declare its basis, and a record's confidence is
recomputed from its own inputs rather than read from a field.

The method was applied to use taken, by a tool, from the committed samples of the load
experiment, and priced at a rate card that is **synthetic** by name, so every record
carries confidence `none`. Three findings survive the invented prices because they are
about measured use:

- processor time is 98.9% of each amount, because the runtime ran at its limit;
- the request path was measured using about 5.4 times the processor time it reserved,
  and the estimate prices the time used rather than the time reserved, while most of
  the memory reservation sat idle;
- the method declined to publish a cost per million tokens, because the run produced
  fewer tokens than its declared minimum sample.

**Evidence.** [The V1 cost baseline](../proof/cost/v1-s4-005-pr2-cost-baseline.md),
[the cost and capacity method](../cost/cost-capacity-method.md),
[ADR 0007](../architecture/decisions/ADR-0007-inference-cost-method.md), and
[ADR 0014](../architecture/decisions/ADR-0014-v1-cost-calculation-reaches-the-estimated-basis.md).
Claims `a-cost-figure-cannot-be-presented-as-a-bill`,
`the-cost-method-was-applied-to-use-taken-from-a-measured-run`,
`what-running-an-inference-workload-costs-on-a-provider`.

## 10. The security boundary

V1's security baseline is a statement of what is **not** defended, and the case study
repeats it rather than softening it. No caller is authenticated and no request is
authorized. Nothing is rate-limited. Every real run was loopback-only, on one host,
started by hand under explicit consent. The chart renders pod-security settings and a
network policy; nothing enforces the former for a pod this platform deploys, and one
experiment measured that the local cluster's network plugin does not enforce the
latter. Twelve risks are carried rather than reduced, and ten of them block production
use.

What is enforced is narrower and real: a committed manifest that drops a required
workload control is refused naming the rules it drops, no control in the baseline may
claim enforcement it does not have, the pinned image and the locked dependencies were
scanned once by hand, and the telemetry catalog admits no prompt, response, or secret.
That the redaction holds in a real run is still `planned`.

**Evidence.** [The security baseline](../security/README.md),
[the deferred risks](../security/deferred-risks.md), and
[the network-policy experiment](../proof/security/v1-s3-004-pr1-network-policy-enforcement.md).
Claims `a-security-control-cannot-claim-enforcement-it-does-not-have`,
`a-workload-manifest-that-omits-a-required-security-control-is-refused`,
`the-pinned-image-and-the-locked-dependencies-were-scanned-and-a-bill-of-materials-published`,
`the-rendered-network-policy-is-enforced-by-the-cluster`,
`a-deployed-inferops-workload-is-defended`,
`no-prompt-response-or-secret-reaches-a-log-or-a-metric`.

## 11. Trade-offs and the alternatives not taken

| Decision | Selected | Alternative not taken | What the selection costs |
|---|---|---|---|
| Serving runtime | llama.cpp `llama-server`, digest-pinned | vLLM on CPU; Ollama; a serving platform | A blocking threshold failed and argued past: the runtime counts no requests, so the platform must |
| Model | Qwen3-1.7B, publisher's `Q8_0` | A smaller community quantisation; 0.6B | More disk and slower decode for first-party provenance and an informative model size |
| Runtime placement | Its own Deployment and Service | A sidecar in the API pod | A network hop, and an API that can be healthy while its runtime is unreachable |
| Cluster ownership | The operator's, verified before mutation | InferOps creating and deleting a `kind` cluster | No control of the cluster's version or its other tenants, recorded as limitations |
| Lifecycle split | Terraform for prerequisites, Helm for the release | One tool for both | Two tools to operate, and a boundary the ownership inventory has to check |
| Performance publication | Bounded observations of one declared setup | Publishing nothing; publishing capacity | Every figure must carry its setup, and nothing can check prose for portability |
| Cost | A method, applied at a synthetic rate card | A provider rate card | No real price anywhere in V1 |
| Evidence strength | A level per record, status per claim, a gate before a freeze | One level per claim | More data per claim, and a release blocked until five claims' code is identified |
| Continuous integration | One default lane, no cluster and no model | A lane that installs a release or loads a model | Nothing in continuous integration exercises real serving |

**Evidence.** [ADR 0002](../architecture/decisions/ADR-0002-model-and-serving-runtime.md),
[ADR 0004](../architecture/decisions/ADR-0004-component-and-ownership-boundaries.md),
[ADR 0011](../architecture/decisions/ADR-0011-external-local-cluster-provider-contract.md),
[ADR 0012](../architecture/decisions/ADR-0012-continuous-integration-service.md),
[ADR 0013](../architecture/decisions/ADR-0013-bounded-local-performance-observations.md),
[ADR 0014](../architecture/decisions/ADR-0014-v1-cost-calculation-reaches-the-estimated-basis.md),
and [ADR 0016](../architecture/decisions/ADR-0016-inferops-evidence-level-model.md).
Claims `eleven-default-lane-gates-are-committed-and-mapped-to-the-claims-they-defend`,
`the-default-lane-cannot-execute-a-real-model`,
`a-cluster-or-real-runtime-lane-runs-in-continuous-integration`.

## 12. What V1 does not prove

Every claim the register does not certify is listed here, because an absence somebody
measured is worth more than one nobody mentions.

- **Planned, and proven by nothing:** a workload the contract describes is served; deployment
  values derive only from a validated document; the mock path identifies itself and
  refuses a model identity that is not mock-labelled; an unready model and an
  unreachable runtime each produce a canonical error of their own; redaction holds in
  a real run; and no credential or model artifact enters public history.
- **Deferred out of V1 by decision:** sustained throughput and capacity under load.
- **Not claimed, and stated as absent:** multi-replica serving, refused at the capacity
  gate on the measured host; an alert that reaches somebody; an enforced network
  policy; a defended workload; a cluster or real-runtime lane in continuous
  integration; a published release; a portable platform someone can deploy for someone
  else; a provider cost; and an authorisation statement in every certifying record.
- **Certified, and blocked from a freeze:** the local serving baseline, the `kind`
  helper, the Helm uninstall's survival clause, the upgrade and rollback, and the pod
  replacement, until each is re-run at a named commit or its status is decided again.

Beyond the register: every real result is one provider and one host, each experiment
ran once or twice, and no second engineer has followed the clean-clone journey. More
runs of the same setup would not widen any claim; they would be the same observation
made more times.

**Evidence.** [The proof dashboard's list of what V1 does not claim](../proof/dashboard.md#what-v1-does-not-claim)
and [the release blockers](../proof/testing/v1-s5-006-pr2-evidence-completeness.md#the-release-blockers).
Claims `the-platform-serves-a-workload-the-contract-describes`,
`deployment-values-derive-only-from-a-validated-document`,
`the-mock-serving-path-identifies-itself-as-a-mock`,
`a-model-that-is-not-ready-is-a-canonical-error`,
`an-unreachable-runtime-is-a-canonical-error`,
`no-prompt-response-or-secret-reaches-a-log-or-a-metric`,
`no-credential-or-model-artifact-enters-public-history`,
`sustained-throughput-and-capacity-under-load`,
`multi-replica-serving-is-certified`,
`an-alert-reaches-somebody`,
`the-rendered-network-policy-is-enforced-by-the-cluster`,
`a-deployed-inferops-workload-is-defended`,
`a-cluster-or-real-runtime-lane-runs-in-continuous-integration`,
`a-v1-release-has-been-published`,
`inferops-is-a-portable-production-platform`,
`what-running-an-inference-workload-costs-on-a-provider`,
`every-certifying-record-lives-under-docs-proof-and-declares-its-own-boundary`,
`a-local-serving-baseline-was-measured-under-a-method-registered-first`,
`a-local-cluster-is-created-and-removed-without-residue`,
`a-helm-release-installs-and-uninstalls-without-residue`,
`a-controlled-release-change-can-be-reversed-and-real-inference-restored`,
`the-model-artifact-survives-a-pod-replacement-on-a-terraform-owned-claim`.

## 13. What evidence would justify a second version

This section states evidence, not scope. Whether a second version proceeds, and what it
contains, is a separate decision that has not been made, and nothing here assumes it.

**Before anything new:** the five release blockers closed, each by a re-run from a
fresh clone at a named commit recording `git rev-parse HEAD` and an empty
`git status`, or by a status decision; the evidence pack frozen; and a first versioned
release cut against it. A second version built on an unfrozen first one would inherit
claims nobody can tie to code.

**Evidence that V1's shape holds beyond one setup:**

- a second engineer completing the clean-clone journey from its own page, unaided;
- `C2` records on `kind` and on a non-Windows host, each certifying only itself;
- the multi-replica profile run on a host that passes its capacity gate;
- the load experiment repeated with more than one slot, with processor throttling
  sampled, and with a varied or uncached prompt mix, answering what the single-slot
  result left open.

**Evidence that the self-service road is closed:** deployment rendering built, so the
two `planned` contract claims can be certified by a workload deployed only from a
validated document; and redaction observed in a real run.

**Evidence that it can be operated rather than only run:** an alert delivered to a
receiver, a lane in continuous integration that installs a release or loads a model,
and a durable telemetry store.

**Evidence that would change a level rather than repeat one:** a `C3` record — a
deliberately representative workload and infrastructure, with its criteria stated
before the run. Nothing short of genuine production operation can reach `C4`, and V1
has none.

What would **not** justify a second version: more executions of the same one-host,
one-replica setup, a longer document, or a higher count of `C2` records of the same
kind.

**Evidence.** [The limitations the README carries](../../README.md#limitations),
[the system architecture's non-goals](../architecture/system-architecture.md#9-what-this-architecture-is-not),
and [the multi-replica certification](../serving/kubernetes-multi-replica-certification.md).
Claims `multi-replica-serving-is-certified`,
`the-platform-serves-a-workload-the-contract-describes`,
`deployment-values-derive-only-from-a-validated-document`,
`a-v1-release-has-been-published`.

## Appendix: the claims this draft relies on

Every claim this draft cites, with its status, the levels of the records behind it, and
whether it is a release blocker, all as the register and the completeness ledger hold
them. A test derives each cell and fails if this table, or the sections citing a claim,
disagree with them. A certified claim marked as a blocker may be read only with its
blocker beside it.

| Claim | Status | Record levels | Release blocker |
|---|---|---|---|
| `the-workload-contract-and-its-rejection-matrix-are-published` | `certified` | `C0` | no |
| `an-invalid-workload-document-is-refused-with-a-published-reason` | `certified` | `C0` | no |
| `the-workload-domain-parses-a-contract-document-into-typed-objects` | `certified` | `C2` | no |
| `the-platform-serves-a-workload-the-contract-describes` | `planned` | none | no |
| `deployment-values-derive-only-from-a-validated-document` | `planned` | none | no |
| `a-workload-scaffold-is-generated-without-overwriting-anything` | `certified` | `C2` | no |
| `a-reviewer-can-reproduce-v1-from-a-clean-clone` | `certified` | `C2` | no |
| `the-inference-api-serves-five-routes-with-explicit-adapter-selection` | `certified` | `C1` | no |
| `the-mock-serving-path-identifies-itself-as-a-mock` | `planned` | none | no |
| `a-mock-result-can-never-certify-real-runtime-behaviour` | `certified` | `C0` | no |
| `a-model-that-is-not-ready-is-a-canonical-error` | `planned` | none | no |
| `an-unreachable-runtime-is-a-canonical-error` | `planned` | none | no |
| `a-runtime-and-model-pair-was-selected-by-a-recorded-feasibility-procedure` | `certified` | `C2` | no |
| `the-model-artifact-matches-its-published-hash` | `certified` | `C2` | no |
| `the-selected-model-serves-a-real-completion-through-the-inferops-api` | `certified` | `C2` | no |
| `a-local-serving-baseline-was-measured-under-a-method-registered-first` | `certified` | `C2` | **yes** |
| `inferops-consumes-an-operator-owned-cluster-and-verifies-it-before-mutating` | `certified` | `C0`, `C2` | no |
| `a-local-cluster-is-created-and-removed-without-residue` | `certified` | `C2` | **yes** |
| `the-selected-runtime-serves-a-real-completion-in-a-cluster` | `certified` | `C1`, `C2` | no |
| `a-helm-release-installs-and-uninstalls-without-residue` | `certified` | `C2` | **yes** |
| `a-controlled-release-change-can-be-reversed-and-real-inference-restored` | `certified` | `C2` | **yes** |
| `the-model-artifact-survives-a-pod-replacement-on-a-terraform-owned-claim` | `certified` | `C2` | **yes** |
| `multi-replica-serving-is-certified` | `not-claimed` | `C0` | no |
| `repeatable-llm-load-can-be-generated-from-a-versioned-profile` | `certified` | `C1`, `C2` | no |
| `a-bounded-local-performance-matrix-was-measured-and-a-degradation-point-observed` | `certified` | `C2` | no |
| `sustained-throughput-and-capacity-under-load` | `deferred` | none | no |
| `a-v1-operator-runbook-covers-every-incident-class-and-every-alert-links-into-it` | `certified` | `C0` | no |
| `caller-visible-impact-of-losing-the-inference-pod-was-measured-under-load` | `certified` | `C2` | no |
| `an-unready-model-was-held-unready-and-recovered-by-an-operator` | `certified` | `C2` | no |
| `the-api-emits-catalog-metrics-and-structured-request-records` | `certified` | `C1` | no |
| `the-telemetry-catalog-cannot-admit-a-prompt-or-an-unbounded-label` | `certified` | `C0` | no |
| `no-prompt-response-or-secret-reaches-a-log-or-a-metric` | `planned` | none | no |
| `a-release-scoped-collector-scrapes-both-inferops-jobs-on-the-reference-provider` | `certified` | `C2` | no |
| `the-inference-operations-dashboard-was-asked-of-a-real-prometheus-and-rendered` | `certified` | `C0`, `C2` | no |
| `six-v1-alerts-carry-an-owner-a-severity-an-evidence-query-and-a-runbook-link` | `certified` | `C0` | no |
| `the-v1-alerts-were-replayed-over-the-telemetry-three-real-experiments-recorded` | `certified` | `C0` | no |
| `an-alert-reaches-somebody` | `not-claimed` | none | no |
| `a-cost-figure-cannot-be-presented-as-a-bill` | `certified` | `C0` | no |
| `the-cost-method-was-applied-to-use-taken-from-a-measured-run` | `certified` | `C0` | no |
| `what-running-an-inference-workload-costs-on-a-provider` | `not-claimed` | none | no |
| `a-security-control-cannot-claim-enforcement-it-does-not-have` | `certified` | `C0` | no |
| `a-workload-manifest-that-omits-a-required-security-control-is-refused` | `certified` | `C0` | no |
| `the-rendered-network-policy-is-enforced-by-the-cluster` | `not-claimed` | `C1` | no |
| `the-pinned-image-and-the-locked-dependencies-were-scanned-and-a-bill-of-materials-published` | `certified` | `C0` | no |
| `no-credential-or-model-artifact-enters-public-history` | `planned` | none | no |
| `a-deployed-inferops-workload-is-defended` | `not-claimed` | none | no |
| `published-documents-link-only-to-things-that-exist` | `certified` | `C0` | no |
| `the-published-strategy-and-its-data-cannot-drift-apart` | `certified` | `C0` | no |
| `the-default-lane-cannot-execute-a-real-model` | `certified` | `C0` | no |
| `no-resource-in-the-architecture-has-two-owners` | `certified` | `C0` | no |
| `eleven-default-lane-gates-are-committed-and-mapped-to-the-claims-they-defend` | `certified` | `C0` | no |
| `a-cluster-or-real-runtime-lane-runs-in-continuous-integration` | `not-claimed` | none | no |
| `every-certifying-record-lives-under-docs-proof-and-declares-its-own-boundary` | `not-claimed` | `C0` | no |
| `a-v1-release-has-been-published` | `not-claimed` | none | no |
| `inferops-is-a-portable-production-platform` | `not-claimed` | none | no |
