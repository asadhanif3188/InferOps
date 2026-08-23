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
- Proposed ADR 0001, comparing alternatives for the container runtime, the local
  Kubernetes distribution, the task runner, how dependencies are installed, how the
  project's workspace stays isolated, how it is torn down, and what a host needs.
- A redacted inventory of the one development host measured for that decision.
- Proposed and explicitly estimated CPU, memory, and disk figures, kept separate
  from the prerequisites this repository actually supports.

ADR 0001 is proposed, not accepted. No cluster, container, or workload was run, so
no environment, tool, or resource requirement is supported by this entry. No V1
product capability or versioned release is included in it.
