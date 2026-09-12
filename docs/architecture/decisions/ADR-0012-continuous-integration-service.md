# ADR 0012: Continuous-integration service for the default lane

| Field | Value |
|---|---|
| Status | **Accepted in part** |
| Date proposed | 2026-09-12 |
| Date accepted | 2026-09-12, for D1 through D5 only |
| Decision owner | Unassigned; no public maintainer roster exists yet |
| Supersedes | [ADR 0005](ADR-0005-test-ci-and-certification-strategy.md) D6, in part |
| Superseded by | None |

> [!IMPORTANT]
> This record selects the service that runs the `default-checks` lane and commits the
> workflow that runs it. It closes **half** of [ADR 0005](ADR-0005-test-ci-and-certification-strategy.md)
> D6 — *which continuous-integration service runs the lanes*. The other half — *what
> labels a capable runner* — stays **not decided**, and D6 stays open for it.
>
> **No job in the committed workflow has ever run on the service.** Every command in
> it was executed by hand on one Windows host before it was written down, and what a
> hosted Ubuntu runner does with them is untested until the first pull request opens.
> A committed workflow is a configuration, and this record does not claim it is a
> result. Running the scanner by hand, which this change did, is a different thing
> from the gate running: it moved the `security-scan` layer to `implemented` and left
> the two claims resting on it uncertified, because one run on one host is not a
> property of every change.
>
> D6 here is **not decided**. No policy is set for whether a required-status-check
> rule protects `main`, because that is a repository setting this repository cannot
> see from inside its own history.

## Decision status

| ID | Decision | Status | What supports it |
|---|---|---|---|
| D1 | GitHub Actions runs the `default-checks` lane | **Accepted** | A committed workflow, and a test that the lane may claim automation only by naming one that exists |
| D2 | The normal lane is cluster-free and model-free, and both are checked rather than promised | **Accepted**, and enforced | Two checks that read the workflow's own text and refuse a cluster or model token |
| D3 | Every third-party action is pinned by commit SHA, and every pin is recorded beside it | **Accepted**, and enforced | A check that refuses a `uses:` reference that is not forty hexadecimal characters, plus a recorded pin per action |
| D4 | A published gate matrix, compared to the workflows in both directions | **Accepted**, and executed | The matrix is committed as data and a suite compares it to the committed jobs both ways |
| D5 | Automating a lane does not raise what it may certify | **Accepted** as a rule, and enforced | Every gate's ceiling is inherited from the strategy's evidence class rather than restated |
| D6 | Whether a required-status-check rule protects `main` | **Not decided** | Nothing. It is a repository setting, not a committed file, and no evidence of it can live here |

## Context

[ADR 0005](ADR-0005-test-ci-and-certification-strategy.md) decided eleven test
layers, four lanes, and a ceiling on what each layer's result may be used to claim.
Its D6 deliberately did not decide where any of it runs, and gave a reason: the
choice has consequences that record could not evaluate — what a capable runner
costs, whether a hosted runner may hold a model artifact at all, and whether the
project is willing to depend on one vendor's workflow syntax.

Three sprints later, two of those three have answers and the third has changed
shape.

The cost question is now separable. The `default-checks` lane needs an interpreter
and a checkout; the lanes that need a capable host are the other three, and nothing
here proposes to automate them. So the expensive question — what a capable runner
costs and whether it may hold 1.71 GiB of weights — is exactly the question this
record still declines to answer.

The vendor question is real and is accepted rather than solved. The repository is
hosted on GitHub, and a second service would mean a second place to look when a
check fails.

What has changed is the risk. This repository now carries a Terraform prerequisite
layer, a Helm chart, environment scripts that reach a cluster, and a provider guard
that refuses an unverified target. A continuous-integration lane arriving into that
without a rule about clusters is a lane that can, from a pull request, discover
whichever cluster a runner happens to see. That is the failure
[ADR 0011](ADR-0011-external-local-cluster-provider-contract.md) exists to prevent,
appearing in a new place — which is why D2 below is a mechanism rather than a
sentence.

## Decision criteria

| Criterion | Why it matters |
|---|---|
| The lane that runs on every change stays free | A check that is expensive is a check that gets turned off, and a check that is off is worse than absent because it is still in the table |
| Automation changes where a check runs, not what it proves | The whole of ADR 0005 D4 is that a mock stops at C1. A green pipeline is a persuasive thing to cite and must not become a way around that |
| The normal lane cannot touch a cluster | An ambient cluster a lane can discover is a cluster a pull request can mutate |
| A gate is reviewable | A workflow that is one opaque script is a workflow nobody reads the diff of |
| Nothing overclaims | A committed workflow that has never run is a configuration. Recording it as evidence would be the exact category of error this project's proof rules exist to prevent |
| No decision leaks into an adjacent one | Selecting a service must not label a runner capable, and must not decide anything about the real-runtime lane |

## D1 — GitHub Actions runs the `default-checks` lane

The service is GitHub Actions and the lane is committed as
[`.github/workflows/checks.yml`](../../../.github/workflows/checks.yml). It runs on
every pull request, on every push to `main`, and on manual dispatch.

The alternative genuinely considered was to keep running everything by hand, which
is what CONTRIBUTING has described until now. It was rejected for a specific reason
rather than a general one: the repository has reached twenty-four public claims and
eleven test layers, and CONTRIBUTING now publishes a different check set for each of
a dozen areas of the tree. A rule enforced only by a contributor remembering it is
enforced only on the days they remember — and this change found the proof of that, in
a secret-scan configuration that had never parsed because nobody had ever run the
scanner over it.

A self-hosted runner was not considered for this lane and is not needed for it:
nothing in `default-checks` requires a capable host, which is the property that makes
this the half of D6 that can be decided cheaply.

Nine jobs make up the lane. What each runs, which layer it belongs to, which claim it
defends, and what it does not prove are in
[the gate matrix](../../testing/ci-gate-matrix.md).

## D2 — The normal lane is cluster-free and model-free, and it is checked

The workflow may not invoke `kubectl`, `helm`, `terraform`, or `kind`, may not select
a cluster provider, may not name a kubeconfig, and may not invoke the model
acquisition tooling or fetch the pinned artifact.

This is enforced by reading the workflow's own text and refusing a token from either
list. Reading the text rather than the parsed steps is deliberate: a cluster can be
reached from a script block, from an action input, or from an environment variable,
and only the text sees all three. Comment lines are stripped first, so this record's
own prohibitions can be written into the file as comments without tripping the check
that enforces them.

The alternative — stating the rule in this document and reviewing for it — is what
the equivalent rule for shell scripts looked like before
[ADR 0001](ADR-0001-local-development-environment.md) D5 acquired a suite. The
argument is the same one that suite makes: the failure is silent, arrives in a
one-line diff, and is indistinguishable from a reasonable convenience.

Real Kubernetes work stays where the Sprint 4 amendment puts it: opt-in, explicitly
provider-selected, positively target-verified, consuming an externally owned cluster,
and labelled in its own evidence. None of that is in this lane and none of it is
decided here.

## D3 — Every action is pinned by commit SHA

A `uses:` reference names forty hexadecimal characters, and the human-readable
version it corresponds to is recorded beside it in the gate matrix data and as a
trailing comment in the workflow.

The argument is one this repository has already accepted once. Every container image
in every manifest here is pinned by digest rather than by tag, for the reason
[ADR 0008](ADR-0008-v1-security-baseline.md) gives: a tag is a label somebody can
move, and a digest is what is actually resolved. A workflow reference to a mutable
tag is the same construct with the same failure mode, and a third-party action runs
with the workflow's token.

Two tools are not actions and are pinned differently. Trivy is installed by a
pinned action at a pinned release version. Gitleaks is downloaded from its release
and checked against a SHA-256 committed in the workflow — not against the checksum
file published beside the archive, because a checksum served from the same place as
the artifact proves the download was not corrupted and nothing more.

## D4 — A published gate matrix, compared in both directions

[The gate matrix](../../testing/ci-gate-matrix.md) is committed as data and as a
document, and `tests/testing/test_ci_gate_matrix.py` compares the data to the
committed workflows both ways: a job with no row fails, and a row with no job fails.

A gate matrix is the document most likely to be written once and then outlive what it
describes. A job gets renamed, a step gets added, a scan gets dropped for an
afternoon and stays dropped, and the table still reads well. Every rule in it is
therefore derived from a file rather than asserted: the ceiling from the strategy's
evidence class, the lane's model and cluster properties from the strategy's lane row,
the job list from the workflow, the action pins from the workflow.

One rule in it is about honesty rather than drift. A gate either names the claims it
defends or records **why it defends none**, and a row that does neither fails. The
acceptance criterion for this story is that the matrix maps every check to a V1
claim; a formatter defends no published claim, and the honest way to satisfy that
criterion is to say so in writing rather than to invent a claim for it.

## D5 — Automating a lane does not raise what it may certify

Every gate's ceiling is inherited from the evidence class its layers already carry.
The `default-lane-tests` gate runs the mock integration layer, and its ceiling is
`C1` — the same `C1` the layer had when it was run by hand.

This is stated as a decision because the pressure is real and predictable. A green
pipeline is the most persuasive artifact a repository produces, and "it passes CI" is
the shortest sentence anybody can write in a pull request. ADR 0005 D4 stops a mock
at C1 through three checks over the strategy data; this record adds a fourth over the
gate matrix so that automation cannot become a fourth way around it.

The consequence is one somebody will eventually find frustrating: a fully green run
of every gate in this lane establishes nothing whatever about whether a model serves
a completion. That is correct and is the point.

## D6 — Whether a required-status-check rule protects `main`

**Not decided.** Whether these jobs are *required* before a merge is a branch
protection setting in the repository's configuration, not a file in its history.
Nothing committed here can establish that such a rule exists, and nothing committed
here would fail if it were removed.

It is recorded as undecided rather than asserted because asserting it would be
unverifiable from inside the repository — which is the same reason
[ADR 0005](ADR-0005-test-ci-and-certification-strategy.md) D6 was left open rather
than filled with a plausible default.

## Consequences

- `CONTRIBUTING`'s statement that every check is run by hand is no longer true for
  the nine gates in this lane, and is corrected. The commands remain the local
  equivalents and a contributor still runs them before opening a change; what changes
  is that forgetting is now caught.
- Adding a job means adding a gate row, and adding a row means naming the claims it
  defends or stating why it defends none. Neither can arrive without the other.
- Adding an action means adding a pin. A `uses:` reference on a tag fails the build
  that introduces it.
- The `default-checks` lane is now `automated` in the strategy data. The other three
  lanes stay `manual` or `deferred`, and this record labels no runner capable.
- The `security-scan` layer became `implemented`, because this change ran its
  commands for the first time and recorded them. It did so in the most useful possible
  way: the run found that the committed scan configuration had never parsed, so the
  scanner had been refusing all of it since `V1-S0-009`. The two claims resting on that
  layer stay uncertified — one run on one host says nothing about the next change, and
  no job has executed on the service.
- A new advisory can turn an unchanged `main` red. A vulnerability database moves
  daily and the two scanning gates block on `CRITICAL` and `HIGH`, so a green result
  dates rather than proves. That is the gate working, and the response is an
  exception recorded by hand in the security baseline, never a lowered threshold.
- The lane is not hermetic. Three gates consume the network.

## Compatibility impact

Compatible. No published schema, contract, error code, rule identifier, or field
location changes. No committed command changes its behaviour, and every command the
workflow runs is one CONTRIBUTING already published. One new command is added,
`python -m tools.ci_gates expected-failures`, and it only runs commands that already
existed.

The `default-checks` lane's `automated`, `workflowRef`, and `v1Status` fields change
in the strategy data, which is the change the suite there was written to require.

## Security considerations

- The workflow's token is declared `contents: read` at the top level. Nothing in the
  lane publishes a package, writes a comment, pushes a tag, or needs a grant that
  could.
- Every third-party action is pinned by commit SHA, so a moved tag cannot introduce
  code into a job that holds that token.
- The secret-scan gate reads full history, which is the only way it can find a
  credential that was committed and later removed. It runs with `--redact`, so a
  finding is reported without reproducing the value in a public log.
- The scan output published as a lane artifact is JSON from Trivy and expires in 30
  days. It is not a record and may not be cited as one.
- Nothing here implements a control inside a running system. The trust boundary map
  in [ADR 0004](ADR-0004-component-and-ownership-boundaries.md) is unchanged.
- One risk this record creates rather than removes: a workflow is code that runs on a
  push, and a pull request from a fork runs this file as it exists on the base branch
  with a read-only token and no access to any repository secret. This lane defines no
  secret and needs none, which is the property that keeps that unremarkable.

## Evidence

The change validation for this record is in
[the V1-S4-001-PR1 validation record](../../proof/testing/v1-s4-001-pr1-validation.md).
It is local static evidence for the change itself: the suites run, the expected-failure
controls produce the exit statuses the repository requires, the workflow parses, and
the diff carries nothing private.

It also records the first run of the secret scanner this repository has ever made,
which is what moved the `security-scan` layer from `planned` to `implemented` — and
what found that the committed scan configuration had never parsed.

It is **not** evidence that any job passes on GitHub Actions, because none has run
there. It is not evidence that a scan is clean on a hosted runner, it is not evidence
that the next change will be scanned at all, and it is not evidence for any claim
about a runtime, a cluster, or a model.

## Risks, assumptions, and open questions

- **The workflow has never run.** Every command in it was run locally on Windows;
  three gates — the container build, and the two that need Trivy on a Linux runner —
  were exercised on this host in a form close to, but not identical to, what the
  runner will do. The first pull request is the first execution.
- **A vendor is now a dependency.** The lane is expressed in one service's workflow
  syntax. Moving it would mean rewriting the file; nothing else in the repository
  would change, because every gate is a command that already ran by hand.
- **Pinning by SHA freezes a known version, including its defects.** An action pinned
  by commit does not receive a security fix. The mitigation is that the pins are
  recorded in one committed table and a bump is a reviewable diff — not that they
  update themselves.
- **A scan result dates.** Two gates block on a database that changes underneath
  them. A green `main` is a statement about the day it ran.
- **Assumed:** that the `default-checks` lane fits in fifteen minutes on a hosted
  runner. It takes well under that locally, and the job timeouts are set to the lane's
  declared budget so that a lane which stops fitting fails visibly rather than
  quietly costing more.
- **Not decided, and deliberately:** what labels a capable runner, whether a hosted
  runner may hold the pinned model artifact, and whether a branch protection rule
  requires these checks. The first two are ADR 0005 D6's remaining half; the third is
  D6 here.
