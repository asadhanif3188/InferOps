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
| kubectl | 1.33, 1.34, or 1.35 | Must stay within one minor version of the pinned node image |
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

Two caveats a contributor should know before relying on this:

- The proof was executed on **Windows 11 x64 with WSL 2 only**. Linux and macOS are
  intended and untested. The scripts have never been run on either.
- Teardown returns the cluster's storage to the container engine, but the engine's
  virtual disk does not return that space to the host. Repeated cycles are not free
  on a disk-constrained machine.

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

The task runner and the dependency installation approach (ADR 0001 D3 and D4)
remain proposed. Neither has been installed or exercised, so neither is a
prerequisite. The environment scripts in this repository are POSIX shell for that
reason.
