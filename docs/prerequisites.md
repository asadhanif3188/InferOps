# Supported-host prerequisites

Status: documentation contribution path supported; runtime/deployment host pending,
with one environment decision now proposed and under review.

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

## Runtime and deployment prerequisites

No operating system, CPU architecture, container runtime, Kubernetes distribution,
model runtime, accelerator, or minimum CPU, memory, and disk requirement is accepted
or supported yet. Those prerequisites require a public ADR and measured proof on the
selected host before they can be stated as supported.

Until that decision exists, contributors must not infer runtime support from a tool
installed on a maintainer's machine or from an unexecuted example.

## Proposed runtime prerequisites, not yet accepted

[ADR 0001](architecture/decisions/0001-local-development-environment.md) proposes a
container runtime, a local Kubernetes distribution, a task runner, a dependency
installation approach, isolation and cleanup rules, and estimated CPU, memory, and
disk requirements. It also records the operating systems on which those estimates
have and have not been measured.

That record is proposed. Its resource figures are estimates rather than measurements,
and nothing in it has been executed, so it does not change what this page supports.
It is linked here so that a contributor evaluating the project can see which
direction is under review and on what evidence.
