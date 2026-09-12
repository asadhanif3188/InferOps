# Security baseline

Status: **accepted in part**, in
[ADR 0008](../architecture/decisions/ADR-0008-v1-security-baseline.md). Twelve
decisions are accepted; two are explicitly not made.

> [!IMPORTANT]
> Nothing in this repository authenticates a caller, authorises a request, or
> admits a pod. The workloads a release deploys **do** carry the pod-security
> settings the chart renders, and that establishes nothing about whether the
> running platform is defended: no check here reads a pod back, no admission
> control constrains one, and the network policy the release creates was measured
> not to be enforced by the plugin the observed clusters run. No secret scanner
> has been run and recorded. An image scanner and a dependency auditor have each
> been run once, by hand, against the pinned runtime image and the committed
> dependency lockfile;
> neither runs continuously, because no continuous-integration service is
> selected. No assessment by an outside party has ever been performed.
>
> What is enforced is enforced over committed files, over five YAML manifests and
> two committed chart renders, and by four shell functions. Every one of those
> reads a file or a contributor's host; the release installed from those renders
> was read by none of them. That is narrow and real. The distance between it and a
> defended system is
> [the deferred-risk register](deferred-risks.md), and it is twelve entries long.

## The documents

| Document | What it answers |
|---|---|
| [Threat model](threat-model.md) | What is worth protecting, who it is protected from, where the boundaries are, and what can go wrong at each |
| [Control matrix](control-matrix.md) | Every control, what verifies it, who owns that verification, and which record it rests on |
| [Deferred risks and exceptions](deferred-risks.md) | What V1 does not defend, why, what would have to be true, and what may not be claimed while each gap stands |
| [Workload policy](workload-policy.md) | Which rules a rendered Kubernetes manifest is held to, which fixtures establish that they refuse, and the distance between a checked manifest and a constrained workload |
| [`security-baseline.v1alpha1.json`](security-baseline.v1alpha1.json) | The authoritative form of all of it, validated by [`tests/security/`](../../tests/security/) |

Reporting a problem is [SECURITY.md](../../SECURITY.md), and it currently publishes
no private channel — which is a gap in its own right, recorded as such.

## The one idea

**A control's status is derived from the verification it names, never asserted.**

Each control declares how it is verified — an automated test, a shell guard, a
review, or nothing — and where it acts. Those two values determine its status
through a table committed beside the controls. A control naming a test names the file
and the function, and the suite fails if the function is not defined. A control whose
status is one the data marks as implementable names an evidence record, and the suite
fails if the record is not committed.

This exists because the realistic failure here is not a false claim. It is a list of
twenty controls, four of which have tests, being counted as twenty by a reader six
months later. The list is the artifact that travels; the qualification stays in the
paragraph above it.

## What that produces

| Status | Controls | May be called implemented |
|---|---|---|
| `enforced-over-documents` | 10 | yes |
| `enforced-over-manifests` | 15 | yes |
| `enforced-on-the-host` | 4 | yes |
| `review-enforced` | 3 | no |
| `specified-only` | 2 | no |
| `deferred` | 4 | no |

Twenty-nine of thirty-eight controls are enforced by something. Nine are not, and the
register says why for each.

`enforced-over-manifests` is the status that needs its own sentence. Every manifest this status covers is read as a file: the smoke and trial apparatus under `deploy/`, and the chart's two committed renders. The eight pod-security assertions and the digest pin hold over those seven files, which is a property of a repository and not of a cluster. A release **has** been installed from those renders, so the workloads it deployed carried the settings — and no check here read a pod that resulted, which is exactly the distance this status exists to keep. `EX-04` records that, and `DR-05` carries the gap.

Five of those fifteen arrived with V1-S3-004 and act over
[the chart's committed renders](../../charts/inferops-llm/ci/rendered/) through
[the workload policy](workload-policy.md). One of them — the network policy — moved
out of `specified-only`, which is the whole of the movement in the table above, and
what moved is the policy rather than its enforcement: a NetworkPolicy is applied by
the cluster's network plugin and not by the object. A cluster has since installed
this chart and created the objects, and whether the accepted local cluster's plugin
applies one **has been tested — and it does not**, which is a worse position than
untested rather than a better one. `DR-04` is narrowed to that half and `EX-05`
records it.

## What is claimed, and at what level

One public claim:
`a-security-control-cannot-claim-enforcement-it-does-not-have`, certified at `C0` by
the documentation layer, owned by security, resting on
[the change validation record](../proof/security/v1-s0-009-pr1-validation.md). It
certifies a committed baseline and nothing about whether anything is defended.

Two security claims in [the matrix](../testing/claim-test-matrix.md) stay `planned`,
and a test now holds them there:
`no-prompt-response-or-secret-reaches-a-log-or-a-metric` needs components that do not
exist, and `no-credential-or-model-artifact-enters-public-history` needs a scanner run
nobody has performed.

## Reserved vocabulary

Twelve terms — the adjectives of a posture rather than the names of properties — may
appear in every Markdown document committed here only inside a sentence that denies
them, and a test refuses one that does not. The list and the reason for each entry are
in [the control matrix](control-matrix.md). It catches a listed word in a Markdown
document; a claim made in a word nobody listed, or in a file that is not Markdown, is
not caught by anything here.

## Changing any of it

A change that adds a control adds the verification it names or declares that it has
none. A change that adds a threat names a control or the register entry that carries
it. A change that removes a register entry adds the control that replaces it — no
test can enforce that one, and it is marked `review` rather than dressed up.

Run the suite:

```sh
python -m pytest tests/security -q
```

It reads only files in this repository and needs `pytest` and `PyYAML`. The decision
behind all of it is
[ADR 0008](../architecture/decisions/ADR-0008-v1-security-baseline.md).
