# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project intends to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
once versioned releases begin.

## [Unreleased]

### Added

- Public repository purpose and status without functional capability claims.
- MIT license and contribution, review, commit, conduct, and release conventions.
- Public indexes for prerequisites, contracts, architecture decisions, and governance.
- Security-reporting expectations, including the unresolved private-channel blocker.
- Reproducible POSIX and PowerShell documentation link checks in the contribution guide.
- A pull-request template covering scope, decision impact, validation, and evidence.
- An explicit record that no public maintainer roster or `CODEOWNERS` file exists yet.
- A decision-record convention and index under `docs/architecture/decisions/`.
- ADR 0001, comparing alternatives for the container runtime, the local Kubernetes
  distribution, the task runner, how dependencies are installed, how the project's
  workspace stays isolated, how it is torn down, and what a host needs. Added as a
  proposal; see **Changed** below for the status it now holds.
- A redacted inventory of the one development host measured for that decision, with
  every row marked as either measured or documented.
- Minimum and recommended CPU, memory, and disk figures, kept separate from the
  prerequisites this repository actually supports.
- A stated verdict that the one measured host does not meet the recommended tier,
  rather than an estimate left unchecked against the evidence beside it.
- A reproducible local development cluster: prerequisite checks, cluster creation
  from a digest-pinned node image, a hello-world smoke test verified from inside
  the cluster, scoped teardown, and residue verification, under
  `scripts/environment/` and `deploy/`.
- A runbook for that cluster, including what it creates, what survives teardown,
  and what it does not establish.
- Real-runtime evidence that the cluster can be created, exercised, and removed
  repeatably on one Windows host, including four attempts to make the teardown act
  outside its own cluster, all of which were refused.

### Changed

- ADR 0001 moves from proposed to **accepted in part**. The container runtime, the
  local Kubernetes distribution, the isolation rules, the cleanup rules, and the
  minimum host tier are accepted on executed evidence. The task runner, the
  dependency installation approach, and the recommended host tier are not, and stay
  proposed.
- The minimum host tier's CPU, memory, and disk figures are now measured rather
  than estimated, and its description no longer mentions a mock serving path that
  does not exist. The recommended tier remains an estimate.
- The container virtual machine's memory ceiling is measured at 7.60 GiB, replacing
  the assumed platform default, and the risk that recorded it as unmeasured is
  closed.
- Prerequisites now state a supported local development environment alongside the
  documentation path, and separate both from serving, which remains unsupported.
- The decision-record conventions define `Accepted in part`, which requires a
  per-decision status table.

### Fixed

- Two teardown claims that the evidence contradicted: the engine's virtual disk
  does not return space to the host when a cluster is deleted, and a cluster
  identity check based on a Kubernetes node label does not work, because the label
  is on the node container rather than on the node object.
- Defects in the environment scripts that review found and that every passing run
  had hidden: the diagnostics collector could never run, because an `ERR` trap is
  not reached when a failure occurs inside a shell function; the residue verifier
  certified a clean teardown when the container engine was merely unreachable; the
  cluster identity guard did not cover the default teardown path; and the node
  image digest read-back compared the pin against a value that is only
  incidentally equal to it.
- Slow and nondeterministic failure behaviour in the smoke test: a failed
  verification now reports in about 25 seconds rather than after a 180-second
  timeout, and job retries are disabled so the assertion always reads the log it
  was meant to read.
- Argument handling on the destructive scripts: a second, ignored argument and a
  valueless `--cycles` are now refused rather than silently doing something other
  than what was asked.

ADR 0001 is accepted only for what was executed, on one Windows host, one
architecture, one point in time. Linux and macOS remain untested. No model, serving
runtime, inference, benchmark, ingress, or load-balancing behaviour is proven by
any entry above, and no V1 product capability or versioned release is included.
