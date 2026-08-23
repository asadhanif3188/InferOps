# Security policy

Status: reporting expectations documented; no private reporting channel published.

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

No security control, threat model, scanning result, hardening posture, or compliance
property is claimed or proven by this repository. Documentation review is not a
security assessment. Any future security claim must name its control, its test, its
evidence, and whether that evidence came from a mock, a local real runtime, or a
production environment.
