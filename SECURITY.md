# Security policy

Status: reporting expectations documented; no private reporting channel published.
A threat model and control baseline now exist and are linked below; neither changes
anything in this policy.

This repository currently contains governance documentation only. It ships no
service, container image, package, or released artifact, so there is no supported
version to patch and no security fix to distribute.

## Supported versions

None. No versioned release exists. A supported-version table will be published with
the first release that carries a security claim.

## Reporting a vulnerability

Do not open a public issue, pull request, or discussion that contains a
vulnerability report, credential, private data, or a sensitive prompt or response.
Public disclosure in this repository is the failure mode this policy exists to
prevent.

A dedicated private reporting channel is not yet published. Until one exists, this
project cannot promise confidential intake, an acknowledgement window, a remediation
timeline, or coordinated disclosure. That gap is a known governance blocker recorded
in [docs/governance/repository.md](docs/governance/repository.md), and it must be
resolved before the project accepts sensitive reports or publishes a versioned
release.

If you believe you have found a security-relevant problem now, wait for the private
channel rather than disclosing it publicly here.

## Scope of current claims

No scanning result, posture, or regulatory property is claimed or proven by this
repository. Documentation review is not a security assessment. Any security claim
must name its control, its test, its evidence, and whether that evidence came from a
mock, a local real runtime, or a production environment.

A threat model and control baseline now exist, and what they establish is narrow
enough to be worth stating here rather than left for a reader to infer:

| Document | What it is |
|---|---|
| [Threat model](docs/security/threat-model.md) | The assets, actors, boundaries, and twenty-two abuse cases this project models |
| [Control matrix](docs/security/control-matrix.md) | Every control, what verifies it, and who owns that verification |
| [Deferred risks and exceptions](docs/security/deferred-risks.md) | Twelve risks V1 carries rather than reduces, and four weaknesses it accepts |
| [ADR 0008](docs/architecture/decisions/ADR-0008-v1-security-baseline.md) | The decision behind all three |

**None of it defends a running system.** Nothing in this repository authenticates a
caller, authorises a request, enforces a network policy, or applies a security
context to a pod it deployed, because nothing here deploys a pod or serves a request.
No secret scanner, image scanner, or dependency auditor has been run and recorded,
and no assessment by an outside party has ever been performed.

What is enforced is enforced over committed files, over five YAML manifests that are
smoke and trial apparatus, and by two shell functions on a contributor's own machine.
A control's status in that baseline is derived from the verification it names rather
than asserted, which is what stops the list above being read as more than it is.
