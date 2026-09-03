# InferOps

InferOps is an early-stage open-source project intended to make local AI inference
workloads easier to describe, operate, and evaluate through explicit contracts and
reproducible evidence.

> [!IMPORTANT]
> This repository provides governance documentation, a local development
> environment, a published workload contract and domain, mock and real serving
> adapters, an ASGI inference API, workload scaffolding, verified model-cache
> tooling, and a loopback-only local composition workflow. It does not provide a
> deployable platform, a production network server, or a released
> V1 capability. Nothing here deploys or admits a workload.
>
> A serving runtime and model **have** now been selected and proven once, on one
> host, under
> [a recorded feasibility trial](docs/proof/serving/v1-s0-003-pr2-runtime-feasibility.md).
> That is a decision backed by evidence, not a capability: there is no serving
> path in this repository that anyone can deploy, and the trial's own manifests
> are apparatus rather than a product.

## Repository status

The repository has established its public foundations and implemented the first
local developer paths through the contract, adapters, ASGI API, and scaffolder.
The [Sprint 1 developer quick start](docs/developer-quick-start.md) is the shortest
verified entry point. Any capability claim must link to reproducible evidence and
identify whether the result is documented, synthetic, mock, estimated, or produced
by a real runtime.

## Public entry points

| Topic | Entry point | Current status |
|---|---|---|
| Developer quick start | [docs/developer-quick-start.md](docs/developer-quick-start.md) | Mock workflow executed locally; real-runtime API smoke documented as authorization-gated and not executed by this change |
| Contribution and review | [CONTRIBUTING.md](CONTRIBUTING.md) | Accepted repository convention |
| Repository governance | [docs/governance/repository.md](docs/governance/repository.md) | Accepted for this repository skeleton |
| Supported-host prerequisites | [docs/prerequisites.md](docs/prerequisites.md) | Documentation and local development supported; serving requirements measured on one host |
| Local development cluster | [docs/environment/local-cluster.md](docs/environment/local-cluster.md) | Executed and evidenced on one Windows host |
| Serving runtime and model feasibility | [docs/serving/feasibility-workflow.md](docs/serving/feasibility-workflow.md) | Procedure executed once; one runtime and model revision selected |
| Model acquisition | [docs/serving/model-acquisition.md](docs/serving/model-acquisition.md) | Revision-pinned, resumable, hash-verifying workspace cache workflow; no model download executed by this change |
| Local LLM runtime profile | [docs/serving/local-runtime-profile.md](docs/serving/local-runtime-profile.md) | Digest-pinned process, external model mount, CPU resources, generation defaults, timeouts, and health semantics validated offline |
| Local runtime package | [docs/serving/local-runtime-package.md](docs/serving/local-runtime-package.md) | Standalone Docker command, loopback exposure, bounded startup/readiness/inference/shutdown, and ownership-scoped cleanup validated through offline and synthetic checks |
| Local real composition | [docs/serving/local-real-composition.md](docs/serving/local-real-composition.md) | One guarded workflow starts the pinned runtime before a real-adapter API, checks both readiness boundaries, and cleans up in reverse order; no real run performed by this change |
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
| Evidence records and templates | [docs/proof/README.md](docs/proof/README.md) | Four templates published; a template is a format and has produced no record |
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
