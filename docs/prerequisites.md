# Supported-host prerequisites

Status: documentation contribution path supported; local development environment
supported on one measured Windows host; serving requirements measured on that same
host for one model and runtime, and not yet supported on any other.

## Governance and documentation contributions

At the current repository stage, contributors need:

- a host operating system capable of running a maintained Git client;
- Git and a UTF-8 Markdown editor;
- a GitHub account to use the documented pull-request workflow;
- network access only when interacting with the remote repository or validating
  external links.

Relative Markdown links and whitespace can be reviewed on any such host. The
governance validation recorded for this repository was executed on one Windows host;
that result is not cross-platform runtime certification.

## Local development environment

[ADR 0001](architecture/decisions/ADR-0001-local-development-environment.md) selects a
container runtime, a local Kubernetes distribution, and the isolation and cleanup
rules that go with them. Those parts of it are accepted, on
[executed proof](proof/environment/v1-s0-002-pr2-cluster-smoke.md) from one host.
[The local cluster runbook](environment/local-cluster.md) describes how to run it.

Tools:

| Tool | Version | Notes |
|---|---|---|
| A Docker-API-compatible engine | Any reachable server | Verified against Docker Engine `29.3.1` |
| kind | `v0.32.0` | Verify the published checksum before running it |
| kubectl | 1.33, 1.34, or 1.35 | Must stay within one minor version of the pinned node image. A container desktop application's bundled kubectl may have moved past it; see [the runbook](environment/local-cluster.md) |
| A POSIX shell | Any | On Windows, the shell supplied with Git is sufficient |

Minimum host, measured rather than estimated:

| Resource | Requirement |
|---|---|
| Logical CPUs | 4 |
| Host memory | 8 GiB on Linux; 16 GiB on Windows or macOS |
| Memory reaching the container VM | 6 GiB — on Windows and macOS this is the binding limit, and it defaults to roughly half the installed memory |
| Free disk on one volume | 20 GB |

The cluster itself consumes about 0.7 GiB of memory and 1.1 GB of engine storage
while running, plus a ~1.35 GB cached node image. The remaining headroom is for
whatever you schedule beside it.

`scripts/environment/preflight.sh` measures three of the four rows above --
processors, the memory reaching the container VM, and free disk -- and refuses
rather than warns when one is short. Host memory is the row it does not measure,
because on Windows and macOS it is not the binding figure; the VM allocation
beneath it is, and that one is read from the engine.

Two caveats a contributor should know before relying on this:

- The proof was executed on **Windows 11 x64 with WSL 2 only**. Linux and macOS are
  intended and untested. The scripts have never been run on either.
- Teardown returns the cluster's storage to the container engine, but the engine's
  virtual disk does not return that space to the host. Repeated cycles are not free
  on a disk-constrained machine.

## Python checks

[ADR 0009](architecture/decisions/ADR-0009-python-toolchain.md) selects the
packaging layout, the dependency manager, the lockfile policy, the linter, the
formatter, and the type checker, and each of them was executed on this repository
before it was accepted. Running the checks the recorded way needs two things:

| Tool | Version | Notes |
|---|---|---|
| uv | `0.9.16` was used | A single binary, installed by the contributor. Not pinned by anything in this repository |
| CPython 3.12 series | `3.12.12` was provisioned | uv provisions its own redistributable build; it does not adopt the interpreter already on the host |

Everything else — `ruff`, `mypy`, `pytest`, `jsonschema`, and `PyYAML` — is pinned
by the committed [`uv.lock`](../uv.lock) and installed by `uv sync --locked`. The
exact versions are published in
[ADR 0009](architecture/decisions/ADR-0009-python-toolchain.md), and
[the contribution guide](../CONTRIBUTING.md) lists the commands.

No task runner is required, and none is selected. No continuous-integration service
is required, and none is selected either.

`shellcheck` and `kubeconform` are still separate installs and are still not pinned
by the lockfile, because neither is a Python distribution. `helm` joined them with
`V1-S3-002-PR1`, on the same terms:

| Tool | Version | Notes |
|---|---|---|
| Helm | `v3.21.4` was used | Needed only to lint, render, or install [the chart](../charts/inferops-llm/README.md), and to run [the release lifecycle script](environment/helm-release-lifecycle.md). The chart suite reads the chart and two committed renders of it without Helm, so the default lane is unaffected by its absence; where Helm is installed, the suite additionally re-renders and compares |

Nothing in this repository installs Helm, and nothing requires it to be present.
A contributor without it can run every check the default lane runs.

## Supply-chain scanning

[ADR 0008](architecture/decisions/ADR-0008-v1-security-baseline.md) and
[the control matrix](security/control-matrix.md) name two host-run scan guards.
Running them needs:

| Tool | Version | Notes |
|---|---|---|
| Trivy | `0.74.0` was used | A single binary, installed by the contributor. Not pinned by anything in this repository, the way `shellcheck` and `kubeconform` are not |

No continuous-integration service runs either scan; both are run by hand, the same
way every check in this repository is.

## Serving and model prerequisites

[ADR 0002](architecture/decisions/ADR-0002-model-and-serving-runtime.md) now selects
a serving runtime and an immutable model revision, on
[executed proof](proof/serving/v1-s0-003-pr2-runtime-feasibility.md) from the same
single Windows host. The figures below are **measured on that host**, for that one
model at that one quantisation. They are not a supported-platform claim, and no
second host has ever run this.

| Resource | Measured requirement for serving | Note |
|---|---|---|
| CPU instruction set | AVX2 | AVX-512 is **not** required |
| Accelerator | None | The CPU path is complete on its own |
| Memory for the serving pod | A 3 GiB limit, against a 2.167 GiB worst-case charge | Do not size this from the runtime's 531 MiB of private memory; the weights are memory-mapped and the difference is not academic |
| Memory reaching the container VM | 7.60 GiB was sufficient beside a running cluster | This is what was available, not a measured floor |
| Free disk | ~2.0 GiB added — 1.71 GiB of weights plus a 293.0 MiB runtime image | Plus whatever the cluster itself needs |
| Network | Enough to fetch 1.71 GiB, resumably | The reference run took 19 minutes and needed a resume partway |

The model and runtime are both fetched anonymously. **No account, API key, or paid
subscription is required at any point**, and that was verified rather than assumed.

Two things this does *not* establish, stated because the table above invites the
opposite reading:

- **Nothing about concurrency or throughput.** Every request in the proof was
  single and sequential.
- **Nothing about any other host or operating system.** ADR 0001 D7's
  **recommended** tier remains an estimate; the serving measurement here sits
  beside it rather than replacing it.

## Deployment prerequisites

No deployment host, production environment, or supported serving platform is
accepted. A local cluster that serves one model to one caller has demonstrated
nothing about production.

## Not yet decided

ADR 0001 D3 and D4 no longer sit here. Both were superseded on 2026-08-27 by
[ADR 0009](architecture/decisions/ADR-0009-python-toolchain.md), which rejected the
task runner and accepted, executed, and pinned the dependency manager. The
environment scripts in this repository remain POSIX shell, which is now a
consequence of there being no task runner rather than of the question being open.

What is still undecided is the continuous-integration service and what labels a
capable runner — [ADR 0005](architecture/decisions/ADR-0005-test-ci-and-certification-strategy.md)
D6. No workflow file exists, no runner is labelled, and every check in this
repository is one a contributor runs by hand and records the result of. ADR 0001 D7's
**recommended** host tier also remains an estimate rather than a measurement.
