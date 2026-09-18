# InferOps

InferOps is an early-stage open-source project intended to make local AI inference
workloads easier to describe, operate, and evaluate through explicit contracts and
reproducible evidence.

> [!IMPORTANT]
> This repository provides governance documentation, a local development
> environment, a published workload contract and domain, mock and real serving
> adapters, an ASGI inference API, workload scaffolding, verified model-cache
> tooling, a loopback-only local composition workflow, a C2 real-runtime
> certification workflow, a model lifecycle state model, a measured local serving
> baseline, a Terraform prerequisite layer and a Helm chart that have been applied
> and installed on a real local Kubernetes cluster, and software-supply-chain
> evidence. It does not provide a production network server or a released V1
> capability, and nothing here **admits** a workload — no admission control, no
> gateway, and no multi-tenancy exist.
>
> It **does** now deploy one. `V1-S3-011` installed the real profile into the
> Kubernetes cluster Docker Desktop provides, loaded the pinned model from a
> Terraform-owned claim, served a real completion through the release's own
> Service, upgraded and rolled the release back, replaced a deleted serving pod
> against the surviving claim, and removed everything it owns. That is one
> provider, on one Windows host, on CPU, with one replica of each tier, and the
> multi-replica profile was refused at the capacity gate on that host. It is not a
> portable production Kubernetes platform and no evidence here claims to be one.
>
> A serving runtime and model **have** been selected, and the selected model
> **does** now serve real completions through the InferOps API on a contributor's
> own machine: see
> [the C2 certification result](docs/proof/serving/v1-s2-004-c2-certification-result.md)
> and [the measured baseline](docs/proof/serving/v1-s2-005-baseline-raw-results.md).
> That is a working local path backed by evidence, not a capability anyone can
> deploy for someone else. Every run behind it is loopback-only, on one host, on
> CPU, started by hand under explicit authorization against a cluster the operator
> already owns. Nothing here is exposed to a network, authenticated, authorized,
> or defended, and the Kubernetes objects that exist are apparatus rather than a
> product.

## Repository status

The repository has established its public foundations, implemented the local
developer paths through the contract, adapters, ASGI API, and scaffolder, and
proved a real local serving path end to end: the pinned runtime loads the
hash-verified model, the API serves a real completion, and the run is certified at
`C2`. Sprint 3 then put that path through Kubernetes on the `docker-desktop`
reference provider — Terraform prerequisites, a Helm release, a real completion
through the release's Service, a controlled upgrade and rollback, a deleted pod
replaced against a surviving claim, real telemetry collection, and a scoped
teardown that left the operator's cluster intact. Every one of those results names
its provider and certifies no other. The [developer quick start](docs/developer-quick-start.md) is the shortest
verified entry point; the real path needs a capable host and explicit
authorization. Any capability claim must link to reproducible evidence and
identify whether the result is documented, synthetic, mock, estimated, or produced
by a real runtime.

## Public entry points

| Topic | Entry point | Current status |
|---|---|---|
| Developer quick start | [docs/developer-quick-start.md](docs/developer-quick-start.md) | Mock workflow executed locally; the real-runtime API smoke is authorization-gated and has been executed and recorded — see [the Sprint 1 real-runtime closure](docs/proof/serving/v1-s1-real-runtime-closure.md) |
| Contribution and review | [CONTRIBUTING.md](CONTRIBUTING.md) | Accepted repository convention |
| Repository governance | [docs/governance/repository.md](docs/governance/repository.md) | Accepted for this repository skeleton |
| Supported-host prerequisites | [docs/prerequisites.md](docs/prerequisites.md) | Documentation and local development supported; serving requirements measured on one host |
| Local cluster provider contract | [docs/environment/local-cluster-provider-contract.md](docs/environment/local-cluster-provider-contract.md) | Accepted in [ADR 0011](docs/architecture/decisions/ADR-0011-external-local-cluster-provider-contract.md): InferOps consumes an existing `kind` or Docker Desktop cluster the operator selects, and creates or deletes none. Both guards exist: `kind` by cluster name, and Docker Desktop by binding its node container to the API server port the verified kubeconfig dials. Docker Desktop is the executed V1 reference provider |
| Local development cluster | [docs/environment/local-cluster.md](docs/environment/local-cluster.md) | An optional `kind` helper since ADR 0011. Executed and evidenced on one Windows host |
| Clean-clone reproduction | [docs/environment/clean-clone.md](docs/environment/clean-clone.md) | Implemented, not executed. One workflow walks the V1 journey from a clean clone -- host prerequisites, two gates of the default-checks lane, scaffolding, model acquisition, local real inference, provider verification against a cluster the operator already has, Terraform, Helm, real Kubernetes inference, telemetry, load, a failure experiment, and scoped cleanup -- and records every step's outcome, exit code, and elapsed time in a ledger, with every manual action the operator records there. A certification run needs every forward-path consent on every invocation; only a preparation run may record a real step as not run, and it can never read as complete. Cleanup removes only what the run created and then checks the cluster survived. Full certification is a complete run on `docker-desktop`; none has been made, and its test modules drive it only against stubs |
| Kubernetes troubleshooting and cleanup | [docs/environment/kubernetes-troubleshooting.md](docs/environment/kubernetes-troubleshooting.md) | Symptom-oriented diagnosis for cluster, scheduling, OOM, storage, model load, probes, Service, telemetry, Helm, and Terraform, and four separated cleanup radii. Both halves are now executed and evidenced on one Windows host, on the `docker-desktop` provider: the release installs, serves, upgrades, fails, rolls back, and uninstalls without residue. Every command is machine-checked against the repository |
| Serving runtime and model feasibility | [docs/serving/feasibility-workflow.md](docs/serving/feasibility-workflow.md) | Procedure executed once; one runtime and model revision selected |
| Model acquisition | [docs/serving/model-acquisition.md](docs/serving/model-acquisition.md) | Revision-pinned, resumable, hash-verifying workspace cache workflow; executed against the real 1.71 GiB artifact, which downloaded and verified against its published SHA-256. Resumption after interruption is proved synthetically only |
| Local LLM runtime profile | [docs/serving/local-runtime-profile.md](docs/serving/local-runtime-profile.md) | Digest-pinned process, external model mount, CPU resources, generation defaults, timeouts, and health semantics validated offline |
| Local runtime package | [docs/serving/local-runtime-package.md](docs/serving/local-runtime-package.md) | Standalone Docker command, loopback exposure, bounded startup/readiness/inference/shutdown, and ownership-scoped cleanup validated through offline and synthetic checks |
| Local real composition | [docs/serving/local-real-composition.md](docs/serving/local-real-composition.md) | One guarded workflow starts the pinned runtime before a real-adapter API, checks both readiness boundaries, and cleans up in reverse order; executed against the real runtime on one CPU host, repeatedly |
| Real-runtime certification | [docs/serving/real-runtime-certification.md](docs/serving/real-runtime-certification.md) | Repeatable C2 smoke workflow with hardware refusal, bounded readiness, real identity assertions, and labelled evidence output; one authorized run [certified at `C2`](docs/proof/serving/v1-s2-004-c2-certification-result.md) on 2026-09-04, with under five per cent of headroom against the readiness budget. The failure path is exercised synthetically only |
| Local serving baseline | [docs/serving/local-serving-baseline.md](docs/serving/local-serving-baseline.md) | Fixed fixture, warm-up, bounded measured phase, sanitized environment capture, raw record format, and deterministic summary registered before any run; [executed on 2026-09-03](docs/proof/serving/v1-s2-005-baseline-raw-results.md), all 30 measured requests succeeded and every pre-registered threshold was met. One host, one day, CPU only, and not a benchmark |
| Repeatable LLM load generation | [docs/serving/llm-load-generation.md](docs/serving/llm-load-generation.md) | Versioned fixture, warm-up, rising concurrency levels, duration and request bounds, client deadline above the API's, a fixed response classification, provider and component identity with each fact's provenance, and a raw record set whose accounting is checked on read. [Rehearsed](docs/proof/serving/v1-s4-003-pr1-validation.md) against an in-process stub, which is synthetic, and first run against a real release by the performance scenarios below. Any figure a run produces is bounded to that run and is not capacity, an SLO, or a benchmark |
| Performance scenarios | [docs/serving/performance-scenarios.md](docs/serving/performance-scenarios.md) | The load profile's warm-up and levels run twice against a release the workflow installs, beside the node's cgroup counters, the release collector's series, and the dashboard at every phase end, on one wall clock; a record that regenerates from its committed inputs and is unusable if pods change, counters disagree with the raw sets, or samples leave a gap. [Executed once on `docker-desktop`](docs/proof/serving/v1-s4-004-pr1-validation.md) and [analysed](docs/proof/serving/v1-s4-004-pr2-performance-findings.md): for that one single-slot release and fixed prompt, completed requests stayed flat from concurrency 1 to 4 while latency rose with it, so its observed degradation point is concurrency 2. Bounded observations under [ADR 0013](docs/architecture/decisions/ADR-0013-bounded-local-performance-observations.md); no tool judges saturation, and nothing is capacity, an SLO, or a benchmark |
| Inference pod recovery | [docs/serving/inference-pod-recovery.md](docs/serving/inference-pod-recovery.md) | One serving pod deleted by name while the committed load profile is mid-flight, with what callers saw before, during, and after it, the Service's own ready-endpoint count sampled across the replacement, and every registered collector expression asked — including two registered as emitting nothing, which still emit nothing. [Executed once on `docker-desktop`](docs/proof/serving/v1-s4-006-pr1-inference-pod-recovery.md): the replacement reported itself Ready 33 665 ms after the delete, forty-one requests were refused in a 31 960 ms caller-visible outage, no person intervened, and the deleted pod went on reporting `Ready: True` throughout it while the Service had no ready endpoint at all. Bounded observations under [ADR 0013](docs/architecture/decisions/ADR-0013-bounded-local-performance-observations.md); nothing here is an availability figure, an SLO, an error budget, or a benchmark |
| Unready model rejection and recovery | [docs/serving/unready-model-recovery.md](docs/serving/unready-model-recovery.md) | A release installed with one committed values overlay that starves the serving runtime of processor time, so the process starts, binds its port, begins loading the model and does not finish -- then held there while four request surfaces are asked and readiness is sampled from four places, and got back by dropping the overlay and upgrading. It is deliberately neither `V1-S3-008`'s artifact mismatch, which the integrity init container refuses before the runtime starts, nor `V1-S4-006`'s deletion of a healthy pod, and the descriptor records the five mechanisms that were considered and rejected, two of them measured directly. [Executed once on `docker-desktop`](docs/proof/serving/v1-s4-007-pr1-unready-model-recovery.md). Bounded observations under [ADR 0013](docs/architecture/decisions/ADR-0013-bounded-local-performance-observations.md); nothing here is an availability figure, an SLO, an error budget, a recovery-time objective, or a benchmark |
| Model lifecycle | [docs/serving/model-lifecycle.md](docs/serving/model-lifecycle.md) | Ordered state model spanning cache and runtime, with the answer each probe gives in each state; validated offline and measured on an authorized CPU host across three cold/warm comparisons; every ordering property held and no cold/warm timing difference was established |
| Local runtime troubleshooting | [docs/serving/local-runtime-troubleshooting.md](docs/serving/local-runtime-troubleshooting.md) | Symptom-oriented diagnosis and recovery for acquisition, integrity, disk, ports, memory, model load, readiness, timeouts, cache, connectivity, and shutdown; every diagnostic executed on one host and machine-checked against the records it quotes, with the authorization-gated recoveries described rather than run |
| Mock and real serving boundary | [docs/serving/mock-and-real-boundary.md](docs/serving/mock-and-real-boundary.md) | Accepted rule; a mock may never certify real runtime behaviour |
| Inference API surface | [docs/serving/inference-api-surface.md](docs/serving/inference-api-surface.md) | Decided shape; five endpoints, served in part |
| InferOps inference API | [docs/serving/inference-api.md](docs/serving/inference-api.md) | Five ASGI routes with explicit mock or real adapter selection; repository tooling carries a loopback-only local HTTP carrier, while the distribution has no server dependency |
| Contracts | [docs/contracts/README.md](docs/contracts/README.md) | WorkloadContract `v1alpha1` accepted; parsed by the platform domain, and no runtime component consumes it |
| Workload contract | [docs/contracts/workload-contract.md](docs/contracts/workload-contract.md) | Schema, valid and invalid fixtures, versioning and compatibility rules, and the canonical rejection matrix published |
| Workload domain model | [docs/domain/workload-domain-model.md](docs/domain/workload-domain-model.md) | Typed domain objects, parsing, and contract-version handling implemented; the validation rule pipeline is not |
| Workload template | [docs/scaffolding/workload-template.md](docs/scaffolding/workload-template.md) | Template, rendering library, and non-overwriting scaffolding command implemented and verified for mock and synchronous profiles; no generated workload is committed |
| Architecture and ADRs | [docs/architecture/README.md](docs/architecture/README.md) | Seven decisions accepted in part, one accepted with a recorded exception, two accepted, one accepted and amended |
| V1 system architecture | [docs/architecture/system-architecture.md](docs/architecture/system-architecture.md) | Design boundary accepted; the platform domain, both adapters, the API, the chart, and the Terraform prerequisite layer are built and have been executed on `docker-desktop`; deployment rendering is not |
| Resource ownership | [docs/architecture/resource-ownership.md](docs/architecture/resource-ownership.md) | Ownership inventory accepted and machine-checked. Terraform and Helm both exist and have been applied and installed on `docker-desktop`; twenty rows moved from `planned` to `implemented` and each cites the run that moved it |
| Project boundaries | [docs/architecture/project-boundaries.md](docs/architecture/project-boundaries.md) | Accepted scope rule; two serving capabilities and no gateway or deep-serving work |
| Test and CI strategy | [docs/testing/test-strategy.md](docs/testing/test-strategy.md) | Strategy accepted and machine-checked; nine of eleven test layers exist and two do not. One lane of four is automated since [ADR 0012](docs/architecture/decisions/ADR-0012-continuous-integration-service.md); nine of its eleven gates have passed on the service and the two infrastructure gates have not run there |
| Continuous-integration gate matrix | [docs/testing/ci-gate-matrix.md](docs/testing/ci-gate-matrix.md) | Eleven gates for the `default-checks` lane, each mapped to the claims it defends or to a recorded reason it defends none, compared to the committed workflow in both directions. Helm and Terraform run there only as subcommands that read files; the normal lane cannot reach a cluster or download the model, and neither is a promise: both are checked. No workflow for a cluster lane is committed, only the rules one must satisfy |
| Python toolchain | [docs/architecture/decisions/ADR-0009-python-toolchain.md](docs/architecture/decisions/ADR-0009-python-toolchain.md) | Packaging, dependency manager, lockfile, linter, formatter, and type checker accepted and executed; no task runner and no CI service selected |
| Certification levels | [docs/testing/certification.md](docs/testing/certification.md) | Accepted definition; V1 certifies at C0 to C2 and a mock stops at C1 |
| Claim and test matrix | [docs/testing/claim-test-matrix.md](docs/testing/claim-test-matrix.md) | Sixteen of twenty-four public claims certified, seven are commitments, and one is deferred |
| Claim and evidence matrix | [docs/testing/claim-evidence-matrix.md](docs/testing/claim-evidence-matrix.md) | Every claim V1 intends to publish, bound to its implementation, the test modules that would fail if it stopped being true, the gates that run them, the executed record that certifies it, the evidence label that decides what that record may support, and the limitation that travels with it. 58 claims: 41 certified, 8 planned, 1 deferred, and 8 not claimed. Every public entry point in the table you are reading is either claimed by a row there or listed, with a reason, as a surface that claims nothing, and a test refuses an entry point that neither list accounts for |
| Telemetry and evidence | [docs/telemetry/README.md](docs/telemetry/README.md) | The API emits eight catalog metrics and structured request logs, and a release-scoped collector has scraped both InferOps jobs on `docker-desktop`; its series are ephemeral, no component emits a span, and no durable store, dashboard server, or alert routing path exists; [a dashboard definition](docs/telemetry/inference-operations-dashboard.md) is checked and was validated once on `docker-desktop` in a throwaway Grafana that no server runs |
| The V1 alerts | [docs/telemetry/inference-alerts.md](docs/telemetry/inference-alerts.md) | Six alerts, each with an owner, a severity, a caller impact, an evidence query, an action and a runbook section; five conditions deferred because nothing emits the signal, and eight refused with the rule that refuses each. No threshold is a figure this project measured. Five of the six replayed over the telemetry three real experiments recorded: one fires, over one capture, and every silence has a reason the record carries. The pinned collector's own promtool loads both rendered rule files. Nothing evaluates or routes any of it -- no receiver, no routing tree, nobody on the other end |
| Redaction rules | [docs/telemetry/redaction.md](docs/telemetry/redaction.md) | Accepted and enforced at the API's metric-declaration and structured-record sinks; content capture is disabled and has no policy that could enable it |
| Cost method | [docs/cost/README.md](docs/cost/README.md) | Method accepted and machine-checked, and [amended](docs/architecture/decisions/ADR-0014-v1-cost-calculation-reaches-the-estimated-basis.md) so V1 calculates the estimated basis only; [a repository tool](docs/cost/cost-calculation.md) applies it by hand to a declared input, and [the V1 cost baseline](docs/proof/cost/v1-s4-005-pr2-cost-baseline.md) applies it to use taken from the `V1-S4-004` samples. The only rate card is synthetic, so every record has confidence `none`; no cost figure is published, and no platform component computes a cost record |
| Worked cost example | [docs/cost/worked-example.md](docs/cost/worked-example.md) | Every figure synthetic and recomputed by the suite; confidence `none` and no figure for what anything costs |
| Threat model and security baseline | [docs/security/README.md](docs/security/README.md) | Baseline accepted and machine-checked; deployed workloads carry the rendered pod-security settings and nothing here establishes that a running system is defended, and twelve risks are carried rather than reduced |
| Deferred security risks | [docs/security/deferred-risks.md](docs/security/deferred-risks.md) | Twelve risks and six accepted exceptions; ten of the twelve block production use |
| V1 proof dashboard | [docs/proof/dashboard.md](docs/proof/dashboard.md) | One generated page over the claim and evidence matrix: the certified, planned, deferred, and not-claimed counts, eleven capability groups with each claim's certification level, evidence class, provider, environment, record link, and limitation, and every claim V1 does not certify listed in full. It is produced by `python -m tools.proof_dashboard` and a test regenerates it, so it cannot state a status the register does not. It answers what has been proven; Grafana answers what is happening now |
| Evidence records and templates | [docs/proof/README.md](docs/proof/README.md) | Four templates published, two of which have produced records, and no Sprint 3 record declares one; the full record index is in [docs/proof/README.md](docs/proof/README.md) |
| Release process | [docs/releases.md](docs/releases.md) | Process documented; no release executed |
| Security reporting | [SECURITY.md](SECURITY.md) | Expectations documented; private channel not published, which is a gap the baseline records |
| Changes | [CHANGELOG.md](CHANGELOG.md) | Unreleased changes only |
| License | [LICENSE](LICENSE) | MIT |
| Conduct | [CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md) | Interim expectations; formal policy deferred |

## Scope and claims

Public documentation describes only accepted repository decisions or implemented,
verified behavior. Proposals are labelled as proposals. Mock, synthetic, estimated,
and unexecuted work cannot be used as proof of real runtime or production behavior.

Unpublished planning, prompts, credentials, model artifacts, host-specific state,
and personal filesystem paths do not belong in this repository.

## Contributing

Start with [CONTRIBUTING.md](CONTRIBUTING.md). The project welcomes focused changes
that preserve the public/private boundary and accurately state their evidence.
