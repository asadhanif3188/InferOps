# Security policy

Status: reporting expectations documented; GitHub private vulnerability reporting was
named as the private channel for `v1.0.0` in `V1-S5-008-PR1`. It is a setting on the
hosting service: on 2026-09-27 it read disabled while that change was written, and it
read enabled when [the record made after the release](docs/proof/releases/v1-s5-009-pr1-v1.0.0-publication.md) read it, later the
same day. A threat model and control baseline exist and are linked below; neither
changes anything in this policy.

This repository contains governance documentation, local development apparatus, a
chart and prerequisite layer, and one platform package that is built locally and
published to no index. A release is an annotated tag and its source archives: it ships
no container image, package, chart, or model, so a fix is distributed only as a later
version of the source.

## Supported versions

| Version | Receives a fix |
|---|---|
| The latest release, `1.0.0` | A fix lands on `main` and in the next release cut from it, whatever its number. Nothing is backported to an earlier release, and no timeline is promised |
| Earlier than `1.0.0` | Nothing was ever released below `1.0.0` |

A supported version is one a fix will be released for. It is not a statement that the
version is defended: [what is not defended](#scope-of-current-claims) is below.

## Reporting a vulnerability

Do not open a public issue, pull request, or discussion that contains a
vulnerability report, credential, private data, or a sensitive prompt or response.
Public disclosure in this repository is the failure mode this policy exists to
prevent.

Report privately through GitHub's private vulnerability reporting for this repository:
the **Security** tab, then **Report a vulnerability**. The report is visible to the
repository's maintainers and to you, and not to the public. It needs a GitHub account,
and it is the only private channel; no e-mail address is published. **If the Security
tab shows no Report a vulnerability button, the channel is not enabled**: do not report
publicly, and wait for it.

What this channel does not promise: an acknowledgement window, a remediation timeline,
coordinated disclosure on a date, or a backported fix. One role maintains this
repository, and the channel has not yet received or answered a report, so no response
time has ever been measured. Whether it is enabled is a setting on the hosting service,
which no file here can pin; it read enabled on 2026-09-27, after `v1.0.0` was
released, and its maintainer can change it.

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
| [Deferred risks and exceptions](docs/security/deferred-risks.md) | Twelve risks V1 carries rather than reduces, and six weaknesses it accepts |
| [ADR 0008](docs/architecture/decisions/ADR-0008-v1-security-baseline.md) | The decision behind all three |

**None of it establishes that a running system is defended.** Nothing in this
repository authenticates a caller, authorises a request, or admits a pod. A release
installed from this repository's chart has served a completion, and the workloads it
deployed carried the pod-security settings the chart renders — a property of what was
rendered and applied, not evidence that anything is defended: no check here reads a
running pod, no admission control constrains one, and the network policy the release
creates was measured not to be enforced by the plugin the observed clusters run.
A secret scanner, an image scanner, and a dependency auditor have each been run
once, by hand, against the committed history, the pinned runtime image, and the
committed dependency lockfile, and those runs are recorded. All three are also gates
in the default-lane workflow, and each passed on the selected service on all nineteen
pushes to `main` from 2026-09-13 to 2026-09-21, as [the run list](docs/proof/security/v1-s5-004-pr1-hosted-runs.v1alpha1.json) records;
those hosted results are read from the service and not promoted into a record. The workflow runs on a change and not on a
schedule, so each finding is current only as of the run that produced it. (Until
2026-09-22 this paragraph said no job in that workflow had run on the service, which
stopped being true on 2026-09-13.) No assessment by an outside party has ever been
performed.

What is enforced is enforced over committed files, over five YAML manifests that are
smoke and trial apparatus, over the chart's two committed renders, and by four shell
functions on a contributor's own machine. A release was installed from those renders;
no check here read the pods it produced.
A control's status in that baseline is derived from the verification it names rather
than asserted, which is what stops the list above being read as more than it is.
