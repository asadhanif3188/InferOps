# Opening a second version

Status: **decided: open**, in `V2-S0-001-PR1` on 2026-09-28. It **supersedes the
outcome** of [the decision whether a second version should proceed](v2-investment-decision.md),
which `V1-S5-009-PR1` decided as defer on 2026-09-27, and edits no word of it. The
decision takes effect when the `repository-maintainer` role merges the change that
carries it; the merge is the whole act, the role has one holder, and nobody outside
this repository has reviewed the decision. The authoritative form is
[`v2-authorization.v1alpha1.json`](v2-authorization.v1alpha1.json), and
`tests/testing/test_v2_authorization.py` holds this page to it, to the earlier record,
and to the register and the evidence index.

> [!IMPORTANT]
> **This record authorizes implementation of a second version; it implements
> nothing.** It builds no capability, adds no evidence, moves no claim, and changes no
> file in the evidence pack. Every claim V1 does not certify stays as the register
> states it, and the earlier record's findings, problems, and boundaries stand except
> where this page says otherwise.

## The decision

**Open V2 for implementation, under one thesis: caller-visible reliability under
failure and change** — whether InferOps can keep a caller served, and tell an operator
the truth, while a serving pod is lost or a workload's release fails or changes.

Two things change from the earlier record, and nothing else does:

1. **Contract-to-deployment rendering moves into V2**, as its first capability. The
   earlier record placed it in finishing V1; [the reason it moves](#contract-to-deployment-rendering-moves-into-v2)
   is below.
2. **The unmet entry gates stop being preconditions for opening.** All three are
   still unmet. Each is kept, and [classified below](#the-earlier-records-entry-gates-and-how-each-is-treated)
   as a V2 target, a deferred item, or a blocker; none is reported as met.

This is a change of judgment, not of evidence, and the next section says so.

## Why now, when nothing new has been measured

The earlier record was decided one day before this one. Between them no experiment
ran, no record was added except the post-release ledger's reading of the release, and
none of the earlier record's review triggers fired:

| Trigger | Fired | Reading |
|---|---|---|
| `the-review-date` | no | The review date is 2026-12-27; this record is taken before it, on the maintainer's initiative |
| `the-road-closes` | no | Both contract claims are planned and hold no record |
| `somebody-else-walks-the-road` | no | Nobody else has completed the clean-clone journey, and nobody outside the repository has reviewed a claim, a record, or the release |
| `a-capable-host-is-available` | no | Nothing has re-measured the host since 2026-09-12, and no paid host is authorized |
| `outside-feedback-names-a-need` | no | No feedback from outside the repository exists |

So this record does not say the earlier one misread its evidence. It reads the same
pack, the one `v1.0.0` was cut over:

| Digest | SHA-256 |
|---|---|
| Evidence pack | `652e9051161d38e6dd2e77306a431bf96d863a262cc4b0dab15c0518ba920ad2` |
| Evidence set | `1d40b33fd79d7b6436c35cfe1fc4ec943a8b82fc77ad1da7cd5d96bb2a5ac23a` |

It disagrees with two of the earlier record's judgments, and the earlier record named
each as open to rejection:

- **The trade-off.** Deferring leaves the one-replica outage untested with a second
  replica, and the earlier record said "a reviewer may reasonably weigh it above
  closing the road first. That is the trade-off in this record most open to
  rejection." This record weighs it that way. The outage a lost pod caused, and the
  signals that misdescribed it, are the problem V1's evidence exposed most clearly, and
  the earlier record's own `revise` option said "its problem is the right one".
- **The gates as preconditions.** Two of the three unmet gates wait on other people,
  and the earlier record said they "cannot be met by more work from the author". As
  preconditions they would hold the version for as long as nobody else acts, including
  the work that does not depend on them. The third, a road closed for one workload, is
  work V2 needs as its own first step. The earlier record stated its gates "so that a
  reader can reject them rather than the outcome"; this record rejects them as
  preconditions and keeps them as conditions.

The earlier record's rule that no option opening a version is selected while a gate is
unmet holds that record's outcome to that record's gates. Its test is unchanged and
still passes, because that outcome is still defer. This record is held to a different
check: every gate the earlier record listed is classified here, in its order and with
its state, and none is called met that was not. The same author chose the earlier
gates, this treatment of them, and both outcomes; the check guards only against the
records drifting apart, not against the judgment.

## The thesis

**Caller-visible reliability under failure and change**: whether InferOps can keep a
caller served, and tell an operator the truth, while a serving pod is lost or a
workload's release fails or changes.

It starts from the problem statement the earlier record kept for a later proposal,
under `revise`: "keeping a caller served, and an operator told the truth, while a
serving pod is lost". It adds one thing, **release change** — a workload release that
fails, is rolled back, or drifts from what was declared — and that addition is this
record's judgment, not a V1 result. V1 never deployed a bad release, rolled one back,
or measured drift. The nearest finding is `the-topology-decided-the-error`, a model held
unready that stayed so until an operator acted. The first V2 results on release change
will be the first evidence either way.

The earlier record's findings it starts from:

- `one-replica-is-the-outage` — losing the only serving pod was a caller-visible outage.
- `readiness-and-scrape-health-disagreed-with-the-service` — the signals an operator
  had did not describe what a caller could reach.
- `multi-replica-refused-at-the-capacity-gate` — a second replica has not been tried.
- `the-topology-decided-the-error` — what a caller met was decided by the deployed path,
  not by the runtime's state.
- `the-road-stops-before-deployment` — nothing deploys a workload from its contract.

How it is judged:

- **By what a caller meets** on the declared serving path, measured independently of a
  deployment tool's reconciliation or health state, pod readiness, the replica count,
  the ready-endpoint count, and scrape health. Each is recorded beside the caller's
  result; none stands in for it. Two replicas are not evidence of reliability; what a
  caller meets while one is lost is.
- **By experiments registered before they run**, with their criteria frozen. A
  criterion changed after a result is seen is a new registration and a rerun, and a
  valid unfavourable, failed, or inconclusive result is kept, not rerun away.
- **By records bounded to what ran**: the host, the provider, and the topology.

## Contract-to-deployment rendering moves into V2

**Before.** The earlier record placed `the-self-service-road-is-open` in
`inferops-v1-completion`, finishing V1 inside the `v1alpha1` contract, and made
`the-road-is-closed-for-one-workload` a precondition for opening a version.

**Now.** It is V2's work, and its first capability: a validated contract rendered
deterministically to the release input a deployment consumes, with invalid or
contradictory intent refused before anything is deployed.

**Why.**

- Every V2 experiment deploys the serving path it measures. If that path is still
  described by a values file written by hand, every V2 result rests on it — the cost
  the earlier record held against `proceed`, that it "builds on a deployment step
  written by hand". Rendering is the front of V2's road, not a separate task before it.
- It is expected to need input the `v1alpha1` contract does not carry, such as what
  differs between the hosts a workload is deployed to. By the earlier record's own
  definitions, work that needs something V1 does not have is a later version's, not
  finishing V1. The expectation is untested; if rendering needs nothing beyond
  `v1alpha1`, the first reason still holds.
- Doing it once, as V2's first step, avoids doing it twice: once inside `v1alpha1` to
  close V1, and again to carry what V2's experiments need.

**What does not change.**

- `the-platform-serves-a-workload-the-contract-describes` and
  `deployment-values-derive-only-from-a-validated-document` stay planned, and move only
  on records a later change adds.
- This record does not change the `v1alpha1` contract. A change that does says so in
  its own record.
- `v1-planned-claims-hold-no-record` stays in `inferops-v1-completion`. This record
  moves no other placement.

## The earlier record's entry gates, and how each is treated

A treatment is one of four: `met`, which stays met; `v2-target`, which V2 must reach
before its own release; `deferred`, which is neither a precondition nor a condition of
V2's release, and is kept visible; and `blocker`, which blocks named V2 work until it
is met, not the opening.

| Gate | Earlier state | Treatment | How |
|---|---|---|---|
| `a-release-is-cut-over-the-frozen-pack` | `met` | `met` | Stays met: the tag `v1.0.0` and the release published on it |
| `the-road-has-been-run-under-failure` | `met` | `met` | Stays met: the `C2` records the earlier record lists |
| `the-road-is-closed-for-one-workload` | `unmet` | `v2-target` | V2's first capability. It is met when both contract claims are certified on records, not when a renderer exists |
| `a-second-person-has-reproduced-v1` | `unmet` | `deferred` | Sought, not scheduled: the author cannot produce it, and a V2 release does not wait on it. A reproduction of V2 would not meet this gate, which is about V1 |
| `someone-outside-the-repository-has-reviewed-v1` | `unmet` | `v2-target` | Reframed as a condition of V2's release: no V2 release until somebody outside this repository has reviewed V2's central claim or the evidence it rests on, and what they found is recorded. The gate as written, a review of V1, stays unmet |
| `this-record-is-merged` | `met-on-merge` | `met` | The earlier record was merged with its evidence |

Three of the six were unmet when the earlier record was decided, and all three are unmet
today.

The earlier record's `revise` option named prerequisites of its own beyond the gates.
Each is treated the same way:

| Prerequisite | The earlier record's words | Treatment | How |
|---|---|---|---|
| `a-host-that-passes-the-capacity-gate` | A host that passes the multi-replica capacity gate, authorized and budgeted if it is paid for | `blocker` | Blocks the experiment that loses one of several serving replicas, and nothing else. The only host measured refused the multi-replica profile on 2026-09-12 and has not been re-measured. It is measured again before that experiment; if it is refused, a paid host is used only after an explicit authorization that declares a budget, a time limit, and a cleanup, none of which exists today. The gate is not weakened to fit a host |
| `a-registered-replica-loss-experiment` | a registered experiment for losing one of several replicas under load | `v2-target` | Registered, with its criteria frozen, before any run whose result bears on the thesis. A run before that is a rehearsal and certifies nothing |
| `an-amendment-to-adr-0004-d7` | an amendment to ADR 0004 D7 for alert delivery and a durable store | `deferred` | The version opened here does not need alert routing or a durable store to test its thesis; a V2 change that does amends D7 in its own record first. `an-alert-reaches-somebody` stays not claimed |

The option's last prerequisite, every unmet entry gate, is the first table.

## What V2 does not take on

These stay outside the version this record opens. A later recorded decision may change
one, before any implementation that needs it.

| Not taken on | What it is | Why |
|---|---|---|
| `a-second-workload-shape` | A second workload shape, asynchronous or batch | A queue, retries, and results delivered later would be a second thesis. Deferred, not rejected: it enters only if a registered experiment cannot be answered without it |
| `anything-in-front-of-several-providers` | Anything in front of several providers: a gateway or provider routing | [Boundary rule 2](../architecture/project-boundaries.md#2-standing-between-a-caller-and-a-choice-of-providers-is-not-this-projects-job) |
| `the-runtime-s-own-behaviour` | The runtime's own behaviour: throughput, batching, capacity, accelerator scheduling or optimization, and hardware or replicas given in proportion to demand | [Boundary rule 3](../architecture/project-boundaries.md#3-making-one-runtime-work-is-not-the-same-as-engineering-the-runtime). Redundancy for a lost pod is not capacity, and a change that drifts from one to the other leaves the thesis |
| `routing-or-shedding-by-load` | Routing requests by what the runtime is doing, or admitting and shedding load by caller | This record: neither answers what a caller meets when a pod is lost or a release changes |
| `a-telemetry-backend-or-cost-management` | A telemetry backend other systems' telemetry flows into, or cost management beyond what reliability costs | [Boundary rule 1](../architecture/project-boundaries.md#1-a-capability-a-contract-can-name-is-not-a-capability-this-project-provides), for the backend. Cost is reported only as what redundancy and release control cost, beside what they bought |
| `agent-runtimes-and-tool-protocols` | Agent runtimes and tool protocols | This record: no part of the thesis |
| `several-clusters-or-a-mesh` | Several clusters, zones, or regions, and a service mesh by default | This record: one cluster at a time. A lost node or zone is not tested and not claimed |
| `remediation-without-a-person` | Remediation that acts without a person approving it | This record: a rollback or a reversal is a change a person approves |

Rolling a workload's release from one revision to the next, and back, is the platform
releasing its own workload, which V1 already does through Helm. It is not the runtime
handing traffic from one model version to the next inside one process, which boundary
rule 3 places elsewhere, and this record does not narrow that rule.

## Evidence levels V2 can reach

A level describes how one record was obtained, under
[InferOps Evidence Levels](../testing/evidence-levels.md); it is project-defined, not an
external certification standard, and not a maturity score.

- **Mostly `C2`**, each record certifying only the host, provider, and topology it ran
  on; `C0` for static checks of rendering and configuration; `C1` where a
  claim-material component is deliberately substituted.
- **`C3` only after a representative intent**, workload, infrastructure assumptions,
  and acceptance criteria are declared and accepted before the run, and the run
  qualifies. Whether V2 attempts one is decided later; no `C3` is assumed here.
- **`C4` is not reachable.** It needs genuine organizational production operation,
  which this project does not have, and a paid host, a longer run, or an outside review
  does not create it.
- **A paid provider does not raise a level.** A record from one host or provider is not
  read across to another.
- **No availability figure, production SLO, or statement of fitness for production use**
  is made from V2's evidence, and no measured figure is published on this page.

## When this decision is looked at again

- `the-capacity-gate-refuses-and-no-host-is-authorized` — the host is refused at the
  multi-replica capacity gate and no paid host is authorized, so the redundancy half of
  the thesis cannot be tested. This record is looked at again rather than the
  experiment weakened.
- `a-change-leaves-the-thesis` — a proposed V2 change serves no part of the thesis or
  crosses a line this record draws. It needs its own recorded decision before
  implementation.
- `outside-review-disputes-the-thesis` — somebody outside the repository shows the
  thesis, or a gate's treatment here, to be wrong.

Nothing automated fires on any of them; holding to them is the maintainer's.

## What this record does not do

- **It implements nothing.** It builds no capability, adds no evidence, moves no claim,
  and changes no register row, ledger, or file in the evidence pack.
- **It does not edit the earlier record.** That record's data is byte for byte as it
  merged, and its page differs only by a dated note at its top that points here.
- **It does not change an accepted decision.** ADR 0004, including D7, and ADR 0005,
  0011, 0012, and 0013 stand as they are; a V2 change that needs one changed records
  that change first.
- **It does not add an authority.** None of the four in
  [the decision-authority register](decision-authority.md) is a decision to open a
  version, as the earlier record also found.
- **It does not call a gate met.** The three unmet gates are unmet, and two stay so
  until somebody other than the author acts.
- **It does not name another project.** "Elsewhere" is a boundary, as in
  [the project boundaries](../architecture/project-boundaries.md), not a plan.
- **It does not authorize spending or publishing.** Paid infrastructure, a model other
  than the pinned one, a release, a tag, or a publication each needs its own explicit
  authorization.

## What is machine-checked, and what is not

`tests/testing/test_v2_authorization.py` establishes that:

- the earlier record's data is unchanged since it merged, and its page is unchanged
  apart from exactly the note this data holds, once, directly under its title;
- the outcome, dates, and identity the data states for the earlier record are that
  record's, this record is decided after it and before its review date, and the page
  states the outcome, the dates, and the supersession;
- every trigger of the earlier record is listed here once, in its order; the date
  trigger's state follows from the dates, and the contract trigger's from the register;
- every gate of the earlier record is classified once, in its order, with its earlier
  state and a treatment from the closed vocabulary; no gate unmet then is called met;
  and the page's tables and count say what the data says;
- every quoted prerequisite is in the earlier `revise` option's words;
- the moved placement is the earlier record's own, with the same problem, gate, and
  claims, and both claims are still planned in the pack this record reads;
- every finding the thesis cites is one of the earlier record's, and its earlier
  problem statement is that record's;
- every quotation on this page is a verbatim passage of the earlier page;
- the digests are the released pack's, no file of this decision is inside the evidence
  pack, the data moves no claim, and no ledger names this change;
- the page publishes every identifier the data holds, resolves every fragment it links,
  quotes no measurement, and uses none of a set of phrases that would overclaim or
  argue from an appeal rather than from evidence;
- the README's roadmap and the governance table's row link this page and the earlier
  one, and the role that accepts it exists with no authority added.

What it does not establish: that the thesis is the right one, that moving the rendering
is wise, that a gate is treated rightly, or that opening now is the right call. The
reasoning is for a reader to reject.
