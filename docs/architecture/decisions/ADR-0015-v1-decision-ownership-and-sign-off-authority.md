# ADR 0015: V1 decision ownership and sign-off authority rest with the repository maintainer role

| Field | Value |
|---|---|
| Status | **Accepted** |
| Date proposed | 2026-09-21 |
| Date accepted | 2026-09-21 |
| Decision owner | [`repository-maintainer`](../../governance/decision-authority.md) |
| Supersedes | None |
| Amends | [ADR 0008](ADR-0008-v1-security-baseline.md) D13, which moves from **not decided** to decided; and the `Decision owner` metadata of [ADR 0001](ADR-0001-local-development-environment.md) through [ADR 0014](ADR-0014-v1-cost-calculation-reaches-the-estimated-basis.md), which all read `Unassigned` |
| Superseded by | None |

> [!IMPORTANT]
> This record decides **who is accountable** for a V1 architectural decision, who may
> accept or amend one, who signs that a published claim matches its evidence, and who
> approves a V1 release. It decides nothing about the system.
>
> It is worth being exact about what changes, because a governance record is the
> easiest kind to read as more than it is. Before this record, fourteen decisions
> carried `Decision owner: Unassigned; no public maintainer roster exists yet`, and
> six documents pointed at that sentence as a known gap. After it, fifteen decisions
> name an owner, and **not one line of evidence has changed**. No claim moves, no
> certification level moves, no evidence class moves, and nothing observed runs any
> differently.
>
> Fourteen of the fifteen owners are assigned **retrospectively**. Nobody re-read
> those records' historical evidence as part of assigning them, the committed data
> says so in a field, and a test refuses an entry that does not declare its basis.
> That is the single most important property of this record: a fresh owner row is
> not a fresh review, and this is the mechanism that stops it being read as one.
>
> The model is machine-checked. It is committed as data in
> [`decision-authority.v1alpha1.json`](../../governance/decision-authority.v1alpha1.json),
> explained in [the decision-authority document](../../governance/decision-authority.md),
> and `tests/architecture/test_decision_authority.py` refuses a decision record with
> no entry, an entry with no record, an owner who is not a declared role, a
> placeholder owner, a metadata row that disagrees with the data, and any governance
> document that still says this authority is unassigned.

## Decision status

| ID | Decision | Status | What supports it |
|---|---|---|---|
| D1 | The accountable unit is a **role**, `repository-maintainer`, and not a person | **Accepted** | The role is defined by an ability the repository already confers — merging into `main` — so it needs no roster to be true |
| D2 | Every V1 decision record has exactly one owner, and it is that role | **Accepted** | Fifteen committed entries, compared against the records on disk in both directions by a test |
| D3 | An owner assigned after the fact declares that it was, in a committed `basis` field | **Accepted** | A test requires the field, restricts it to the two declared values, and refuses an entry without one |
| D4 | Four authorities are named separately: decision ownership, acceptance and amendment, claim sign-off, and release approval | **Accepted** | Each is committed with the question it answers, how it is exercised, and what it does not establish |
| D5 | All four are held by the same role today, because the role has one holder | **Accepted** | Stated rather than implied, so a reader knows which form of approval they are looking at |
| D6 | Exercising any of the four changes no status, level, class, or claim | **Accepted** | Every authority commits a `doesNotEstablish` list; a test requires each list to be non-empty |
| D7 | No public roster of people is published, and that is a decision rather than a pending item | **Accepted** | The role is the published unit; the commit history is where this repository says who acted |
| D8 | When the role has more than one holder, the maintainer who accepts a record may not be its author | **Accepted** as a rule; enforced by review | No second holder exists, so nothing can check it yet; it is written now because it is cheapest to write before it is needed |
| D9 | [ADR 0008](ADR-0008-v1-security-baseline.md) D13 — who signs off a control and its evidence — is answered here | **Accepted** | The `claim-evidence-sign-off` authority answers it, and a test refuses the old wording surviving in either record |

## Context

This project's governing habit is that a rule written down is worth less than a rule
written down as unenforced. It applied that habit to controls, to claims, to
certification levels, and to cost bases. It did not apply it to itself.

Fourteen decision records carried the identical sentence
`Unassigned; no public maintainer roster exists yet`. Six more documents named the
same gap, each pointing at the others: the contribution guide, the repository
governance record, the certification document, the security control matrix, and both
claim matrices. ADR 0008 left `D13`, *who signs off a control and its evidence*,
explicitly undecided, with "Nothing. There is no public maintainer roster to name" in
the column that elsewhere holds a test.

(The first draft of this record said **four**, and enumerated four of the six. The
independent review before this change landed counted the diff instead and found the
security control matrix and the certification document among them. A record about a
field nobody counted, getting its own count wrong, is worth leaving visible rather
than quietly fixing.)

Read together, those sentences make one argument, and the argument does not hold.

**The stated blocker was a roster of people. The actual blocker was a decision about
a role, and nobody had made it.** A roster is a list of individuals, and publishing
one for a project with a single contributor would be a list of length one that goes
stale on the day the project acquires a second. That is a poor reason to publish it
and a worse reason to leave every architectural decision unowned for fourteen
records. The repository already confers an ability — write access to `main` — and
that ability is the only thing any of the four authorities below actually requires.

The cost of leaving it open had also stopped being theoretical. Later V1 work needs
an authority that can say a claim's status matches its evidence, and an authority
that can approve a release candidate. Both were waiting on a sentence that was
never going to arrive, because the thing it was waiting for was the wrong thing.

## Decision criteria

Five, registered before the options were compared.

| ID | Criterion | Why |
|---|---|---|
| C1 | It must be true without a roster | A model that needs a list of people is the model that has been blocked for fourteen records |
| C2 | It must survive a change of holder | The common failure of a named owner is that the name outlives the involvement |
| C3 | It must not imply a review that did not happen | Fourteen records get an owner in one change; if that reads as fourteen reviews, the record has done harm |
| C4 | It must keep the four authorities separable | Collapsing them is convenient now and expensive when a second maintainer arrives |
| C5 | It must be machine-checkable where the fact is mechanical | An owner field that only a reader checks is the field that drifted for fourteen records |

## D1 — The accountable unit is a role

`repository-maintainer`: anyone able to merge a pull request into `main` in this
repository.

Three alternatives were compared against the criteria.

| Option | C1 | C2 | C5 | Why not |
|---|:---:|:---:|:---:|---|
| Name the individual who holds the role | no | no | partly | Fails C1 and C2 outright. It also publishes a personal identity into every record, permanently, for no property a reader can use |
| An `OWNERS`/`CODEOWNERS` file naming individuals | no | no | yes | The same failure with a file in front of it. `CODEOWNERS` routes review requests; it does not decide who is accountable for a decision |
| A review body, board, or committee | yes | yes | yes | Would satisfy every criterion and describe an organization that does not exist. Inventing governance structure is the one failure worse than leaving the gap |
| **The role** (**selected**) | yes | yes | yes | It is conferred by repository state that already exists, it is stable across holders, and the assignment is a fact a test can read |

The role is deliberately not the same thing as the seven **evidence owners** in
[the test strategy](../../testing/test-strategy.md). Those name which area a result
belongs to and have never been sign-off authorities; this record does not promote
them into ones, and both claim matrices are corrected to stop citing the absence of a
roster as the reason they are not.

## D2, D3 — Every record has one owner, and says how it got one

Fifteen entries, one per record under [`decisions/`](.), each naming the role and a
`basis`:

| `basis` | Meaning | Count |
|---|---|---:|
| `assigned-retrospectively` | Accepted before this model existed. The role takes accountability going forward; **nobody re-read the historical evidence** as part of the assignment | 14 |
| `assigned-at-acceptance` | Accepted under this model, owner named when accepted | 1 |

C3 is the reason the field exists. A change that adds fourteen owner rows on one day
looks, in a diff, exactly like a change that reviewed fourteen records on one day.
The two are not close to the same thing, and the difference is not recoverable from
the row itself. So it is recorded beside the row, in data, in a field a test requires
and restricts to two values.

## D4, D5 — Four authorities, one holder

| `authorityId` | The question | Exercised by |
|---|---|---|
| `adr-decision-ownership` | Who is accountable for an accepted decision continuing to describe the system? | Carrying the record: amending it when the implementation moves, superseding it when the decision stops holding |
| `adr-acceptance-and-amendment` | Who may accept, amend, or supersede a V1 architectural decision? | Approving and merging the pull request that carries it |
| `claim-evidence-sign-off` | Who signs that a published claim's status matches its evidence? | Merging the change that sets or moves a row in [the claim and evidence register](../../testing/claim-evidence-matrix.md), having read the record that row cites |
| `v1-release-approval` | Who approves a V1 release candidate, so far as architecture and governance are concerned? | Approving the exact candidate commit named in [the release checklist](../../releases.md), after the gates it requires have passed |

All four sit with `repository-maintainer`. Not because they belong together — they do
not — but because the role has one holder, and distributing four authorities across
one person and calling it separation of duties would be the invented structure C1
and the alternatives table both refuse.

They are **named separately anyway**, and that is the part with a future in it. The
day a second maintainer arrives, splitting them is an amendment to a list that
already exists rather than an argument about what the list should have been.

## D6 — What exercising an authority does not do

Each authority commits its own `doesNotEstablish` list. Across the four, the rules
that matter most:

- **An approval is not evidence.** Merging a change that sets a claim's status does
  not make the evidence behind the claim stronger. If the record it cites is
  documented, mock, synthetic, or estimated, it stays documented, mock, synthetic, or
  estimated.
- **A certification level is reached by a record, never by an approval.** The
  promotion rules are in [the certification document](../../testing/certification.md)
  and this record does not touch them.
- **Sign-off here is internal.** No outside party has reviewed a decision, a claim,
  or a release candidate in this repository. That was true before this record and it
  is true after it; what changes is that "nobody has the authority" is no longer also
  true.
- **Release approval is not a fitness claim.** [The release process](../../releases.md)
  already says a version number is evidence of packaged repository state and nothing
  else. Naming who approves it does not upgrade what it means.

This is the decision's own application of the habit in the context section. A
governance record that did not say this would be a document that reads as more
finished than the repository, which is the specific failure this project treats as a
defect.

## D7 — No roster, and that is the decision

The role is the published unit. Who holds it is repository state, and the commit
history is where this repository answers who acted — the only place it does, and the
only place that stays true without maintenance.

The consequence, stated plainly: a reader cannot learn from any document here who the
maintainer is. They can learn what the maintainer may do, what they may not, and
where to look for what they actually did. For a repository with one contributor and
no external maintainers, that is the whole of what a roster would have told them,
minus a name that would need updating.

Every document that previously described the absent roster as a **pending** gap is
corrected in this change: it is a decision now, with a reason, and the six documents
that pointed at each other point here instead.

## D8 — What happens when there are two

Four rules, and deliberately no fifth.

1. The role is the owner; a change of holder transfers nothing, because no record
   names a holder.
2. While the role has one holder, the merge is the whole act, and this record says so
   rather than letting a reader assume a heavier process.
3. With more than one holder, the maintainer who accepts or amends a record must not
   be its author.
4. Splitting the four authorities across roles is an amendment to the committed data
   and to this record.

Rule 3 has no enforcement and cannot have one until a second holder exists. It is
written down now because the moment it becomes checkable is the moment it becomes
inconvenient, and a rule adopted then is a rule adopted against a specific change.

## D9 — ADR 0008 D13 is answered

ADR 0008 left `D13` — *who signs off a control and its evidence* — not decided, with
"There is no public maintainer roster to name" as its whole support. That reason is
the one D1 rejects.

`claim-evidence-sign-off` answers it. A control's status in
[the control matrix](../../security/control-matrix.md) is derived from its
verification and will continue to be; what `D13` was missing is **who is accountable
for that derivation being right**, and it is the same role as everywhere else.
ADR 0008's `D13` row, its status banner, its `D13` section, and the
`who-owns-security-verification` open question in its committed data are all amended
to record the answer and to point here.

`D14` is untouched and stays undecided. It asks where a pod-security property is
enforced once a rendering path exists, deployment rendering is still unbuilt, and
answering it would decide a component boundary ADR 0004 owns.

## Consequences

- **Fifteen records name an owner and none is unassigned.** The `Decision owner` row
  of every record changes in one change, and a test now fails if one drifts back.
- **Three ADR risk registers lose a row.** `R7` in ADR 0001 and `R8` in ADR 0004 and
  ADR 0011 each recorded the absent roster as an open risk. They are resolved rather
  than deleted, with this record named as what resolved them.
- **Two claim matrices and the certification document stop citing a missing roster.**
  Their "roles, not people" sections stay — evidence areas really are roles — but the
  reason changes from *nobody could be named* to *the accountable role is named here*.
- **The release checklist's approval step has somebody to satisfy it.** Step 7 asked
  for maintainer approval while every other document said no maintainer was named.
- **A fourth governance register joins the machine-checked set**, beside the ownership
  inventory, the claim register, and the test inventory.
- **Nothing this project claims changes.** No row of the claim register moves, no
  certification level moves, no evidence class moves, and this record cites no
  runtime evidence because it produces none.

## Compatibility impact

None on any published contract. `contracts/` is untouched, no schema changes, no
runtime behaviour changes, and no lane, marker, layer, or gate moves.

One documentation convention changes: a decision record's `Decision owner` field now
has a controlled form — the role identifier, linked to the governance document — and
a test reads it. A record that writes something else fails the suite rather than
passing unnoticed, which is the drift that produced fourteen identical `Unassigned`
rows.

## Security considerations

Two, and both are limits rather than improvements.

**Naming an authority defends nothing.** This record adds no control, and the
security baseline's own rule applies to it: a control that is written down is not a
control that is enforced. `D13` moving from undecided to decided changes who is
accountable for a control's status being right. It changes nothing about whether any
control acts, and twenty-nine of the baseline's thirty-eight controls have a
verification while nine do not, exactly as before.

**A single-holder approval is a single point of failure, and is recorded as one.**
There is no second reader for a decision record today, no separation between author
and approver, and no outside review of any kind. D8's rule exists to close the first
of those when a second holder makes it closable; the other two stay open and are in
the limits committed with the data.

## Evidence

| Claim | Evidence | Class | Ceiling |
|---|---|---|---|
| Every decision record has exactly one declared owner, in both directions | `tests/architecture/test_decision_authority.py` over the committed data and the records on disk | `local-static` | `C0` |
| No record or governance document still leaves this authority unassigned | The same suite, scanning the decision records and the governance documents | `local-static` | `C0` |
| Each record's own metadata row names the owner the data assigns it | The same suite | `local-static` | `C0` |
| The change itself was validated | [Change validation record](../../proof/architecture/v1-s5-003-pr1-validation.md) | `local-static` | `C0` |

**No other evidence exists, and none is possible.** This record decides who is
accountable. Accountability is not a property of a running system, nothing was
executed to establish it, and no suite can establish that it was exercised well.

## Risks, assumptions, and open questions

| ID | Risk or question | Status | Consequence |
|---|---|---|---|
| R1 | One holder means author and approver are the same person | Open | No separation of duties exists for any change, including this one. D8 closes it when a second holder arrives and nothing closes it before |
| R2 | Retrospective assignment could be read as retrospective review | Mitigated | The `basis` field is committed, required, restricted to two values, and published in the document; fourteen entries declare it |
| R3 | No outside party has reviewed any decision, claim, or release candidate here | Open | Internal sign-off is the only form this project has, and no document may describe it as more |
| R4 | A reader cannot learn who holds the role from any document | Accepted | This is D7, not a defect. The commit history answers it |
| R5 | The four authorities are held by one role, so the separation is declarative | Open | Nothing tests that they are exercised separately, because they cannot be while the role has one holder |
| Q1 | Does a contract owner need the same treatment? | Open | [The repository governance record](../../governance/repository.md) says contract owners will be named in their public artifacts. `contracts/` publishes one contract and this record does not extend to it |
| Q2 | Should acceptance require a check that the record cites evidence for its status? | Open | Today that is review. A test could compare a record's status against whether it links a proof record, and this record does not add one |

## Related records

| Topic | Document |
|---|---|
| The authority model, explained | [Decision ownership and sign-off authority](../../governance/decision-authority.md) |
| The authority model, as data | [`decision-authority.v1alpha1.json`](../../governance/decision-authority.v1alpha1.json) |
| Repository policy, review, and merge conventions | [Repository governance](../../governance/repository.md) |
| The decision whose `D13` this answers | [ADR 0008](ADR-0008-v1-security-baseline.md) |
| The decision index and record conventions | [Architecture and decision records](../README.md) |
| The claims this authority signs off | [Claim and evidence matrix](../../testing/claim-evidence-matrix.md) |
| What a result may be used to claim | [Certification levels](../../testing/certification.md) |
| The release this authority approves | [Release process](../../releases.md) |
