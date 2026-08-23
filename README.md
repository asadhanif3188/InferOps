# InferOps

InferOps is an early-stage open-source project intended to make local AI inference
workloads easier to describe, operate, and evaluate through explicit contracts and
reproducible evidence.

> [!IMPORTANT]
> This repository provides governance documentation and a local development
> environment. It does not provide a deployable platform, a supported workload
> contract, a serving runtime, or a released V1 capability. Nothing here has served
> a model.

## Repository status

The repository is establishing its public foundations before implementation. Any
future capability claim must link to reproducible evidence and identify whether the
result is documented, synthetic, mock, estimated, or produced by a real runtime.

## Public entry points

| Topic | Entry point | Current status |
|---|---|---|
| Contribution and review | [CONTRIBUTING.md](CONTRIBUTING.md) | Accepted repository convention |
| Repository governance | [docs/governance/repository.md](docs/governance/repository.md) | Accepted for this repository skeleton |
| Supported-host prerequisites | [docs/prerequisites.md](docs/prerequisites.md) | Documentation and local development supported; serving support pending |
| Local development cluster | [docs/environment/local-cluster.md](docs/environment/local-cluster.md) | Executed and evidenced on one Windows host |
| Contracts | [docs/contracts/README.md](docs/contracts/README.md) | No public contract accepted yet |
| Architecture and ADRs | [docs/architecture/README.md](docs/architecture/README.md) | One decision accepted in part |
| Release process | [docs/releases.md](docs/releases.md) | Process documented; no release executed |
| Security reporting | [SECURITY.md](SECURITY.md) | Expectations documented; private channel not published |
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
