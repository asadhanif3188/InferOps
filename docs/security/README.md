# Security baseline

Status: **accepted in part**, in
[ADR 0008](../architecture/decisions/ADR-0008-v1-security-baseline.md). Twelve
decisions are accepted; two are explicitly not made.

> [!IMPORTANT]
> Nothing in this repository authenticates a caller, authorises a request, enforces
> a network policy, or applies a security context to a pod it deployed — because
> nothing here deploys a pod or serves a request. No secret scanner has been run
> and recorded. An image scanner and a dependency auditor have each been run once,
> by hand, against the pinned runtime image and the committed dependency lockfile;
> neither runs continuously, because no continuous-integration service is
> selected. No assessment by an outside party has ever been performed.
>
> What is enforced is enforced over committed files, over five YAML manifests, and
> by four shell functions. That is narrow and real. The distance between it and a
> defended system is [the deferred-risk register](deferred-risks.md), and it is
> twelve entries long.

## The four documents

| Document | What it answers |
|---|---|
| [Threat model](threat-model.md) | What is worth protecting, who it is protected from, where the boundaries are, and what can go wrong at each |
| [Control matrix](control-matrix.md) | Every control, what verifies it, who owns that verification, and which record it rests on |
| [Deferred risks and exceptions](deferred-risks.md) | What V1 does not defend, why, what would have to be true, and what may not be claimed while each gap stands |
| [`security-baseline.v1alpha1.json`](security-baseline.v1alpha1.json) | The authoritative form of all three, validated by [`tests/security/`](../../tests/security/) |

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
| `enforced-over-manifests` | 10 | yes |
| `enforced-on-the-host` | 4 | yes |
| `review-enforced` | 3 | no |
| `specified-only` | 3 | no |
| `deferred` | 4 | no |

Twenty-four of thirty-four controls are enforced by something. Ten are not, and the
register says why for each.

`enforced-over-manifests` is the status that needs its own sentence. Every manifest
this repository publishes is smoke or trial apparatus; none is a serving path this
platform deploys. The eight pod-security assertions and the digest pin hold over five
YAML files, which is a property of a repository and not of a cluster. `EX-04` records
that, and `DR-05` carries the gap.

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
