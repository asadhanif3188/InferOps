# InferOps

InferOps is an early-stage open-source project intended to make local AI inference
workloads easier to describe, operate, and evaluate through explicit contracts and
reproducible evidence.

> [!IMPORTANT]
> This repository currently contains governance documentation only. It does not
> provide a deployable platform, a supported workload contract, a serving runtime,
> Kubernetes automation, or a released V1 capability.

## Repository status

The repository is establishing its public foundations before implementation. Any
future capability claim must link to reproducible evidence and identify whether the
result is documented, synthetic, mock, estimated, or produced by a real runtime.

## Public entry points

| Topic | Entry point | Current status |
|---|---|---|
| Contribution and review | [CONTRIBUTING.md](CONTRIBUTING.md) | Accepted repository convention |
| Repository governance | [docs/governance/repository.md](docs/governance/repository.md) | Accepted for this repository skeleton |
| Supported-host prerequisites | [docs/prerequisites.md](docs/prerequisites.md) | Documentation-only prerequisites; runtime support pending |
| Contracts | [docs/contracts/README.md](docs/contracts/README.md) | No public contract accepted yet |
| Architecture and ADRs | [docs/architecture/README.md](docs/architecture/README.md) | No public architecture accepted yet |
| Release process | [docs/releases.md](docs/releases.md) | Process documented; no release executed |
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
