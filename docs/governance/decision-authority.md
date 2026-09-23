# Decision ownership and sign-off authority

Status: **accepted**, in
[ADR 0015](../architecture/decisions/ADR-0015-v1-decision-ownership-and-sign-off-authority.md),
on 2026-09-21. The authoritative form is
[`decision-authority.v1alpha1.json`](decision-authority.v1alpha1.json), and
`tests/architecture/test_decision_authority.py` compares this document to it in both
directions.

Until this record, every architecture decision in this repository carried the same
metadata row — `Decision owner: Unassigned; no public maintainer roster exists yet` —
and six other documents pointed at that sentence as a known gap. The gap was
real, and the reason given for it was wrong. What was missing was never a roster of
people. It was a decision about **which role** is accountable, and nobody had made it.

This document makes it, for four kinds of authority that are easy to collapse into
one and should not be.

## The role

| `roleId` | Who holds it | How it is conferred | Public roster |
|---|---|---|---|
| `repository-maintainer` | Anyone able to merge a pull request into `main` in this repository | Write access, which the repository's own settings decide and no document here can grant | No, and deliberately so |

One role, held today by one person. The role is what the records name, because a
person named in a record goes stale the day they stop merging, and a record naming
someone who no longer acts is worse than one naming the role that still does. Who
holds the role is repository state; the commit history is where this repository
answers that question, and it is the only place it does.

This is not the same as the seven **evidence owners** in
[the test strategy](../testing/test-strategy.md). Those say which area a result
belongs to. They have never been sign-off authorities and this record does not make
them ones.

## The four authorities

They are listed separately because they are separable, not because they are separated
today. All four are held by `repository-maintainer`, for the reason the project gives
for most of its other one-of-everything choices: there is one.

| `authorityId` | The question it answers | Held by | Exercised by |
|---|---|---|---|
| `adr-decision-ownership` | Who is accountable for an accepted decision continuing to describe the system? | `repository-maintainer` | Carrying the record: amending it when the implementation moves, superseding it when the decision no longer holds |
| `adr-acceptance-and-amendment` | Who may accept, amend, or supersede a V1 architectural decision? | `repository-maintainer` | Approving and merging the pull request that carries the record. The merge is the act; there is no separate approval artifact |
| `claim-evidence-sign-off` | Who signs that a published claim's status matches its evidence? | `repository-maintainer` | Merging the change that sets or moves a claim's status in [the claim and evidence register](../testing/claim-evidence-matrix.md), having read the record the row cites |
| `v1-release-approval` | Who approves a V1 release candidate, as far as architecture and governance are concerned? | `repository-maintainer` | Approving the exact candidate commit named in [the release checklist](../releases.md), after the gates it requires have passed |

Each one also declares what exercising it does **not** establish, and those lists are
the load-bearing half of this record. They are in the data and summarised under
[what this does not do](#what-this-does-not-do).

## Every V1 decision, and who owns it

Sixteen records. All of them are owned by `repository-maintainer`, and none is
unassigned. The `basis` column is the part worth reading.

| Decision | Basis | Assigned |
|---|---|---|
| [ADR 0001](../architecture/decisions/ADR-0001-local-development-environment.md) | `assigned-retrospectively` | 2026-09-21 |
| [ADR 0002](../architecture/decisions/ADR-0002-model-and-serving-runtime.md) | `assigned-retrospectively` | 2026-09-21 |
| [ADR 0003](../architecture/decisions/ADR-0003-workload-contract-schema-tooling.md) | `assigned-retrospectively` | 2026-09-21 |
| [ADR 0004](../architecture/decisions/ADR-0004-component-and-ownership-boundaries.md) | `assigned-retrospectively` | 2026-09-21 |
| [ADR 0005](../architecture/decisions/ADR-0005-test-ci-and-certification-strategy.md) | `assigned-retrospectively` | 2026-09-21 |
| [ADR 0006](../architecture/decisions/ADR-0006-telemetry-and-evidence-catalog.md) | `assigned-retrospectively` | 2026-09-21 |
| [ADR 0007](../architecture/decisions/ADR-0007-inference-cost-method.md) | `assigned-retrospectively` | 2026-09-21 |
| [ADR 0008](../architecture/decisions/ADR-0008-v1-security-baseline.md) | `assigned-retrospectively` | 2026-09-21 |
| [ADR 0009](../architecture/decisions/ADR-0009-python-toolchain.md) | `assigned-retrospectively` | 2026-09-21 |
| [ADR 0010](../architecture/decisions/ADR-0010-inference-api-compatibility-surface.md) | `assigned-retrospectively` | 2026-09-21 |
| [ADR 0011](../architecture/decisions/ADR-0011-external-local-cluster-provider-contract.md) | `assigned-retrospectively` | 2026-09-21 |
| [ADR 0012](../architecture/decisions/ADR-0012-continuous-integration-service.md) | `assigned-retrospectively` | 2026-09-21 |
| [ADR 0013](../architecture/decisions/ADR-0013-bounded-local-performance-observations.md) | `assigned-retrospectively` | 2026-09-21 |
| [ADR 0014](../architecture/decisions/ADR-0014-v1-cost-calculation-reaches-the-estimated-basis.md) | `assigned-retrospectively` | 2026-09-21 |
| [ADR 0015](../architecture/decisions/ADR-0015-v1-decision-ownership-and-sign-off-authority.md) | `assigned-at-acceptance` | 2026-09-21 |
| [ADR 0016](../architecture/decisions/ADR-0016-inferops-evidence-level-model.md) | `assigned-at-acceptance` | 2026-09-23 |

| `basis` | What it means |
|---|---|
| `assigned-retrospectively` | The record was accepted before this ownership model existed. The role takes accountability for it going forward. **Nobody re-read the historical evidence as part of the assignment**, and the assignment is not a review of it |
| `assigned-at-acceptance` | The record was accepted under this model, and its owner was named when it was accepted |

Fourteen of the sixteen carry the first basis. That is the honest shape of a
governance gap closed after the fact, and writing it into the data is what stops a
later reader taking fourteen fresh owner rows as fourteen fresh reviews. The two that
do not are [ADR 0015](../architecture/decisions/ADR-0015-v1-decision-ownership-and-sign-off-authority.md),
which established this model, and
[ADR 0016](../architecture/decisions/ADR-0016-inferops-evidence-level-model.md), the
first record accepted under it.

## How this changes when a second maintainer arrives

Four rules, and deliberately no more than four.

1. **The role is the owner.** A change of holder transfers nothing, because no record
   names a holder. A new maintainer acquires every decision this file assigns to the
   role on the day they can merge, and loses it on the day they cannot.
2. **While the role has one holder, the merge is the whole act.** A single-holder
   approval is the weakest of the four authorities, and a reader is entitled to know
   which one they are looking at rather than to infer it.
3. **When the role has more than one holder, the maintainer who accepts or amends a
   record must not be its author.** [CONTRIBUTING](../../CONTRIBUTING.md) already
   requires one approving review; this makes it explicit for a decision record, which
   is the class of change least likely to fail a test when it is wrong.
4. **Splitting the four authorities across different roles is an amendment**, to this
   file and to the record behind it — not a convention adopted in passing.

## What this does not do

- **It is not an external review.** No outside party has reviewed a decision, a
  claim, or a release candidate in this repository. Merging a change is not one.
- **It does not raise anything.** No authority here changes what a result may be used
  to claim. A certification level is reached by a record, an evidence class is set by
  the layer that produced the result, and an approval moves neither. Signing a claim
  whose evidence is documented, mock, synthetic, or estimated leaves it documented,
  mock, synthetic, or estimated.
- **It does not create an approval artifact.** There is no sign-off file, no
  approval log, and no signature. The merge, the pull-request review, and the commit
  history are the whole mechanism, and anything else would be a record of a process
  this project does not run.
- **It does not confer authority over a running system.** Nothing in this repository
  administers one.
- **It does not name a person, and will not.** That is a decision under this model,
  not an item still pending.

## What is machine-checked, and what is not

`tests/architecture/test_decision_authority.py` establishes that:

- every decision record under `docs/architecture/decisions/` has exactly one entry
  here, and every entry names a record that exists — in both directions;
- every entry's owner is a declared role, and no entry carries an unassigned,
  pending, or to-be-decided placeholder;
- every record's own `Decision owner` metadata row names the role this file assigns
  it, in one spelling;
- no decision record and no governance document still states that a V1 decision
  owner, an acceptance authority, a claim sign-off, or release approval is
  unassigned or undecided;
- every authority declares what it does not establish, and declares at least one
  thing;
- this document publishes every role, authority, and decision identifier the data
  holds, and publishes none the data lacks.

What it does not establish: whether the model is a **good** one, whether the person
holding the role is a suitable owner, and whether any accountability was in fact
exercised. Those are review questions, and a test that pretended to answer them
would be the failure this repository's other suites exist to prevent.

## Related records

| Topic | Document |
|---|---|
| The decision this document implements | [ADR 0015](../architecture/decisions/ADR-0015-v1-decision-ownership-and-sign-off-authority.md) |
| Repository policy, review, and merge conventions | [Repository governance](repository.md) |
| How a change is proposed and reviewed | [CONTRIBUTING](../../CONTRIBUTING.md) |
| The decision index and record conventions | [Architecture and decision records](../architecture/README.md) |
| What a published claim may say, and on what evidence | [Claim and evidence matrix](../testing/claim-evidence-matrix.md) |
| What a result may be used to claim | [Certification levels](../testing/certification.md) |
| The release checklist this authority applies to | [Release process](../releases.md) |
