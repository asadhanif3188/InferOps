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
> baseline, and software-supply-chain evidence. It does not provide a deployable
> platform, a production network server, or a released V1 capability. Nothing here
> deploys or admits a workload.
>
> A serving runtime and model **have** been selected, and the selected model
> **does** now serve real completions through the InferOps API on a contributor's
> own machine: see
> [the C2 certification result](docs/proof/serving/v1-s2-004-c2-certification-result.md)
> and [the measured baseline](docs/proof/serving/v1-s2-005-baseline-raw-results.md).
> That is a working local path backed by evidence, not a capability anyone can
> deploy. Every run behind it is loopback-only, on one host, on CPU, started by
> hand under explicit authorization. Nothing here is exposed to a network,
> authenticated, authorized, scheduled, or defended, and the manifests that exist
> are apparatus rather than a product.

## Repository status

The repository has established its public foundations, implemented the local
developer paths through the contract, adapters, ASGI API, and scaffolder, and
proved a real local serving path end to end: the pinned runtime loads the
hash-verified model, the API serves a real completion, and the run is certified at
`C2`. The [developer quick start](docs/developer-quick-start.md) is the shortest
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
| Local development cluster | [docs/environment/local-cluster.md](docs/environment/local-cluster.md) | Executed and evidenced on one Windows host |
| Serving runtime and model feasibility | [docs/serving/feasibility-workflow.md](docs/serving/feasibility-workflow.md) | Procedure executed once; one runtime and model revision selected |
| Model acquisition | [docs/serving/model-acquisition.md](docs/serving/model-acquisition.md) | Revision-pinned, resumable, hash-verifying workspace cache workflow; executed against the real 1.71 GiB artifact, which downloaded and verified against its published SHA-256. Resumption after interruption is proved synthetically only |
| Local LLM runtime profile | [docs/serving/local-runtime-profile.md](docs/serving/local-runtime-profile.md) | Digest-pinned process, external model mount, CPU resources, generation defaults, timeouts, and health semantics validated offline |
| Local runtime package | [docs/serving/local-runtime-package.md](docs/serving/local-runtime-package.md) | Standalone Docker command, loopback exposure, bounded startup/readiness/inference/shutdown, and ownership-scoped cleanup validated through offline and synthetic checks |
| Local real composition | [docs/serving/local-real-composition.md](docs/serving/local-real-composition.md) | One guarded workflow starts the pinned runtime before a real-adapter API, checks both readiness boundaries, and cleans up in reverse order; executed against the real runtime on one CPU host, repeatedly |
| Real-runtime certification | [docs/serving/real-runtime-certification.md](docs/serving/real-runtime-certification.md) | Repeatable C2 smoke workflow with hardware refusal, bounded readiness, real identity assertions, and labelled evidence output; one authorized run [certified at `C2`](docs/proof/serving/v1-s2-004-c2-certification-result.md) on 2026-09-04, with under five per cent of headroom against the readiness budget. The failure path is exercised synthetically only |
| Local serving baseline | [docs/serving/local-serving-baseline.md](docs/serving/local-serving-baseline.md) | Fixed fixture, warm-up, bounded measured phase, sanitized environment capture, raw record format, and deterministic summary registered before any run; [executed on 2026-09-03](docs/proof/serving/v1-s2-005-baseline-raw-results.md), all 30 measured requests succeeded and every pre-registered threshold was met. One host, one day, CPU only, and not a benchmark |
| Model lifecycle | [docs/serving/model-lifecycle.md](docs/serving/model-lifecycle.md) | Ordered state model spanning cache and runtime, with the answer each probe gives in each state; validated offline and measured on an authorized CPU host across three cold/warm comparisons; every ordering property held and no cold/warm timing difference was established |
| Local runtime troubleshooting | [docs/serving/local-runtime-troubleshooting.md](docs/serving/local-runtime-troubleshooting.md) | Symptom-oriented diagnosis and recovery for acquisition, integrity, disk, ports, memory, model load, readiness, timeouts, cache, connectivity, and shutdown; every diagnostic executed on one host and machine-checked against the records it quotes, with the authorization-gated recoveries described rather than run |
| Mock and real serving boundary | [docs/serving/mock-and-real-boundary.md](docs/serving/mock-and-real-boundary.md) | Accepted rule; a mock may never certify real runtime behaviour |
| Inference API surface | [docs/serving/inference-api-surface.md](docs/serving/inference-api-surface.md) | Decided shape; five endpoints, served in part |
| InferOps inference API | [docs/serving/inference-api.md](docs/serving/inference-api.md) | Five ASGI routes with explicit mock or real adapter selection; repository tooling carries a loopback-only local HTTP carrier, while the distribution has no server dependency |
| Contracts | [docs/contracts/README.md](docs/contracts/README.md) | WorkloadContract `v1alpha1` accepted; parsed by the platform domain, and no runtime component consumes it |
| Workload contract | [docs/contracts/workload-contract.md](docs/contracts/workload-contract.md) | Schema, valid and invalid fixtures, versioning and compatibility rules, and the canonical rejection matrix published |
| Workload domain model | [docs/domain/workload-domain-model.md](docs/domain/workload-domain-model.md) | Typed domain objects, parsing, and contract-version handling implemented; the validation rule pipeline is not |
| Workload template | [docs/scaffolding/workload-template.md](docs/scaffolding/workload-template.md) | Template, rendering library, and non-overwriting scaffolding command implemented and verified for mock and synchronous profiles; no generated workload is committed |
| Architecture and ADRs | [docs/architecture/README.md](docs/architecture/README.md) | Seven decisions accepted in part, one accepted with a recorded exception, two accepted |
| V1 system architecture | [docs/architecture/system-architecture.md](docs/architecture/system-architecture.md) | Design boundary accepted; the platform domain is partly built and everything below it is unbuilt |
| Resource ownership | [docs/architecture/resource-ownership.md](docs/architecture/resource-ownership.md) | Ownership inventory accepted and machine-checked; no Terraform or Helm exists |
| Project boundaries | [docs/architecture/project-boundaries.md](docs/architecture/project-boundaries.md) | Accepted scope rule; two serving capabilities and no gateway or deep-serving work |
| Test and CI strategy | [docs/testing/test-strategy.md](docs/testing/test-strategy.md) | Strategy accepted and machine-checked; eight of eleven test layers exist and no CI lane is configured |
| Python toolchain | [docs/architecture/decisions/ADR-0009-python-toolchain.md](docs/architecture/decisions/ADR-0009-python-toolchain.md) | Packaging, dependency manager, lockfile, linter, formatter, and type checker accepted and executed; no task runner and no CI service selected |
| Certification levels | [docs/testing/certification.md](docs/testing/certification.md) | Accepted definition; V1 certifies at C0 to C2 and a mock stops at C1 |
| Claim and test matrix | [docs/testing/claim-test-matrix.md](docs/testing/claim-test-matrix.md) | Twelve of twenty-one public claims certified; the rest are commitments |
| Telemetry and evidence | [docs/telemetry/README.md](docs/telemetry/README.md) | The API emits eight catalog metrics and structured request logs; no component emits a span |
| Redaction rules | [docs/telemetry/redaction.md](docs/telemetry/redaction.md) | Accepted and enforced at the API's metric-declaration and structured-record sinks; content capture is disabled and has no policy that could enable it |
| Cost method | [docs/cost/README.md](docs/cost/README.md) | Method accepted and machine-checked; the only rate card is synthetic and nothing in this repository computes a cost record |
| Worked cost example | [docs/cost/worked-example.md](docs/cost/worked-example.md) | Every figure synthetic and recomputed by the suite; confidence `none` and no figure for what anything costs |
| Threat model and security baseline | [docs/security/README.md](docs/security/README.md) | Baseline accepted and machine-checked; nothing here defends a running system, and twelve risks are carried rather than reduced |
| Deferred security risks | [docs/security/deferred-risks.md](docs/security/deferred-risks.md) | Twelve risks and four accepted exceptions; ten of the twelve block production use |
| Evidence records and templates | [docs/proof/README.md](docs/proof/README.md) | Four templates published, two of which have produced records; the full record index is in [docs/proof/README.md](docs/proof/README.md) |
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
