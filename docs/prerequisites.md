# Supported-host prerequisites

Status: documentation contribution path supported; runtime/deployment host pending.

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
