# Whether a second version should proceed

Status: **decided: defer**, in `V1-S5-009-PR1` on 2026-09-27. Review by **2026-12-27**,
or sooner when [a trigger below](#review) fires. The decision takes effect when the
`repository-maintainer` role merges the change that carries it; the merge is the whole
act, the role has one holder, and nobody outside this repository has reviewed the
decision. The authoritative form is
[`v2-investment-decision.v1alpha1.json`](v2-investment-decision.v1alpha1.json), and
`tests/testing/test_v2_investment_decision.py` holds this page to it and both to the
register and the evidence index.

> [!IMPORTANT]
> **No second version is opened, and this record names no scope for one.** It decides
> whether V1's evidence justifies another version now, and what problem one would have
> to prove. It adds no claim, moves no claim, and changes no file in the frozen
> evidence pack. Every problem below is an engineering problem V1 measured or stated;
> none is a statement about demand, a buyer, or a saving, and nothing here measures one.

## The decision

**Defer.** V1's own road is not yet closed for one workload: nothing turns a validated
contract into release values. Only its author has walked that road, and nobody outside
the repository has reviewed it. The problem V1's evidence points at most strongly — a
caller-visible outage that one replica causes — cannot be tested on the only host
measured, which refused the multi-replica profile at its capacity gate. The next
InferOps work, if any, finishes V1's own planned claims inside the `v1alpha1` contract.
The revised problem statement under [revise](#revise) is kept as the one a later
proposal has to start from.

A decision that opens a version while one of its own entry gates is unmet is refused
by the test, so the outcome is not free to disagree with the gates. The gates are
stated [below](#entry-gates) so that a reader can reject them rather than the outcome.

## What it rests on

The evidence pack frozen by `V1-S5-013-PR2`, and nothing newer:

| Digest | SHA-256 |
|---|---|
| Evidence pack | `652e9051161d38e6dd2e77306a431bf96d863a262cc4b0dab15c0518ba920ad2` |
| Evidence set | `1d40b33fd79d7b6436c35cfe1fc4ec943a8b82fc77ad1da7cd5d96bb2a5ac23a` |

Counted from the register: 59 claims, of which 41 are certified, 7 planned,
1 deferred, and 10 not claimed, behind 64 evidence records, of which 26 are `C0`,
8 are `C1`, 30 are `C2`, and none is `C3` or `C4`. The levels are those of
[InferOps Evidence Levels](../testing/evidence-levels.md): project-defined, not an
external certification standard, and not a maturity score.

The annotated tag `v1.0.0` exists on `718ad2e`, the merge of `V1-S5-008-PR1`, with
[its release notes](../releases/v1.0.0.md). The register inside the frozen pack still
lists `a-v1-release-has-been-published` as not claimed; moving that row is a change
after the tag, under a new ledger, and this record does not make it.

## What V1 found that bears on it

Each row is a finding the [case study](../case-study/v1-engineering-case-study.md) or
the register already publishes. The status and record levels are the register's, and
the test fails if either moves.

| Finding | What V1 recorded | Claims, status, and record levels | Record |
|---|---|---|---|
| `more-callers-bought-waiting` | Completed requests stayed between 0.554 and 0.575 per second from concurrency 1 to 4 while median latency rose about fourfold; whether the slot or the processor held the rate was not tested | `a-bounded-local-performance-matrix-was-measured-and-a-degradation-point-observed` certified, `C2`; `sustained-throughput-and-capacity-under-load` deferred, none | [performance findings](../proof/serving/v1-s4-004-pr2-performance-findings.md) |
| `one-replica-is-the-outage` | Losing the only serving pod caused a 31 960 ms caller-visible outage in which 40 of the 41 requests were refused; a second run's was 2 832 ms. One replica is the cause | `caller-visible-impact-of-losing-the-inference-pod-was-measured-under-load` certified, `C2` | [pod recovery](../proof/serving/v1-s4-006-pr1-inference-pod-recovery.md) |
| `readiness-and-scrape-health-disagreed-with-the-service` | The deleted pod reported Ready while the Service had no ready endpoint; scrape health read it up after the delete; two registered series are emitted by nothing, nothing is kept past a release, and no alert is evaluated in a release or delivered | `caller-visible-impact-of-losing-the-inference-pod-was-measured-under-load` certified, `C2`; `a-release-scoped-collector-scrapes-both-inferops-jobs-on-the-reference-provider` certified, `C2`; `the-v1-alerts-were-replayed-over-the-telemetry-three-real-experiments-recorded` certified, `C0`; `an-alert-reaches-somebody` not claimed, none | [pod recovery](../proof/serving/v1-s4-006-pr1-inference-pod-recovery.md), [alert validation](../proof/telemetry/v1-s4-008-pr1-alert-validation.md) |
| `the-topology-decided-the-error` | A model held from loading stayed unready for 179 755 ms without a restart, and no caller met `model-not-ready`, because the runtime's Service never held an address | `an-unready-model-was-held-unready-and-recovered-by-an-operator` certified, `C2`; `a-model-that-is-not-ready-is-a-canonical-error` planned, none; `an-unreachable-runtime-is-a-canonical-error` planned, none | [unready model](../proof/serving/v1-s4-007-pr1-unready-model-recovery.md) |
| `the-road-stops-before-deployment` | Nothing turns a validated contract into release values; a values file is written by hand | `the-platform-serves-a-workload-the-contract-describes` planned, none; `deployment-values-derive-only-from-a-validated-document` planned, none | none: both are planned |
| `only-the-author-has-walked-the-road` | The whole path completed once from a fresh clone, on its third attempt, by the change's author, an AI coding agent; the scaffold walkthrough was an independent AI reviewer, not a human | `a-reviewer-can-reproduce-v1-from-a-clean-clone` certified, `C2`; `a-workload-scaffold-is-generated-without-overwriting-anything` certified, `C2` | [clean-clone run](../proof/environment/v1-s5-001-pr2-clean-clone-run.md), [walkthrough](../proof/scaffolding/v1-s1-006-independent-walkthrough.md) |
| `multi-replica-refused-at-the-capacity-gate` | The multi-replica profile was refused at its capacity gate before anything was installed; the gate was not weakened | `multi-replica-serving-is-certified` not claimed, `C0` | [paved road](../proof/environment/v1-s3-011-pr1-docker-desktop-paved-road.md) |
| `use-and-reservation-diverged` | The request path used about 5.4 times the processor time it reserved while most of its memory reservation sat idle; every price is synthetic | `the-cost-method-was-applied-to-use-taken-from-a-measured-run` certified, `C0`; `what-running-an-inference-workload-costs-on-a-provider` not claimed, none | [cost baseline](../proof/cost/v1-s4-005-pr2-cost-baseline.md) |
| `nothing-is-defended` | No caller is authenticated or authorized and nothing is rate-limited; the local plugin enforced none of the rendered policy; ten of twelve carried risks block production use | `a-deployed-inferops-workload-is-defended` not claimed, none; `the-rendered-network-policy-is-enforced-by-the-cluster` not claimed, `C1` | [network-policy experiment](../proof/security/v1-s3-004-pr1-network-policy-enforcement.md) |
| `nothing-real-runs-in-continuous-integration` | The one automated lane runs no cluster and no model, and no runner is selected to hold the pinned model | `a-cluster-or-real-runtime-lane-runs-in-continuous-integration` not claimed, none | none: it is not claimed |
| `every-result-is-one-setup` | One provider, one Windows host, CPU, one replica of each tier; nothing is `C3`, and nothing can be `C4` | `inferops-is-a-portable-production-platform` not claimed, none; `a-local-cluster-is-created-and-removed-without-residue` not claimed, `C2` | none: it is not claimed |

## The problems they expose, and three questions for each

A finding is not yet a reason to build anything. Each problem below is asked three
separate questions, because they fail separately: whether it matters enough to justify
more work, whether the next experiment is feasible and bounded **now**, and whether it
belongs in InferOps at all.

| Problem | Important? | Feasible now? | Where it belongs | Level if it succeeds |
|---|---|---|---|---|
| `the-self-service-road-is-open` | yes | yes | `inferops-v1-completion` | `C2` |
| `v1-planned-claims-hold-no-record` | partly | yes | `inferops-v1-completion` | `C2` |
| `one-replica-is-the-outage` | yes | no | `inferops-later-version` | `C2` |
| `signals-an-operator-cannot-trust` | yes | partly | `split` | `C2` |
| `what-held-the-rate-was-not-tested` | partly | yes | `split` | `C2` |
| `one-setup-one-author` | yes | partly | `inferops-v1-completion` | `C2` |
| `the-platform-is-not-defended` | yes | partly | `split` | `C2` |
| `nothing-real-runs-in-continuous-integration` | partly | no | `inferops-later-version` | `C2` |
| `no-real-price` | partly | no | `split` | `C2` |
| `no-representative-evidence` | partly | partly | `inferops-later-version` | `C3` |

`inferops-v1-completion` finishes something V1 already states, inside the `v1alpha1`
contract. `inferops-later-version` is this platform's own work but changes what V1 is
for or an accepted decision. `split` means part of it belongs here and part does not,
and the paragraph says which.

**`the-self-service-road-is-open`.** A workload owner can write and validate a
contract, but nothing deploys what it describes. It is the one step that makes the
contract more than validated paper, and the case study calls it the most important
unbuilt component in V1. It needs the existing host, the existing chart, and no paid
resource. Success would move the two planned contract claims with `C2` records on the
one host measured; it would prove nothing about another host, another provider, or a
workload shape the contract does not define.

**`v1-planned-claims-hold-no-record`.** Five more planned claims have no record: the
mock's self-identification, the two canonical errors, redaction in a real run, and no
credential or model artifact in public history. Each can be exercised on the existing
host. The unready-model run already showed that `model-not-ready` may not be reachable
as the claim is written, through the deployed topology; if a run confirms it, restating
the claim is the result, not a failure to hide. A history scan is a static reading and
reaches `C0`, not `C2`.

**`one-replica-is-the-outage`.** Whether a caller can be kept served while a serving
pod is lost. It is the largest caller-visible effect V1 measured and the only one whose
cause its record names. It is not feasible now: the only host measured fails the
multi-replica capacity gate, the difference is held by workloads that are not this
project's to remove, and another host means other hardware or a paid provider, neither
authorized nor budgeted. How many replicas of its own release the platform runs is this
platform's business; making the runtime answer more requests is not, under
[boundary rule 3](../architecture/project-boundaries.md#3-making-one-runtime-work-is-not-the-same-as-engineering-the-runtime).
A `C2` record would certify only the host it ran on, and `C3` needs a representative
intent and criteria declared before the run.

**`signals-an-operator-cannot-trust`.** An operator who trusted pod readiness during the
pod-loss experiment was wrong for its whole outage, and a rule nobody evaluates tells
nobody. Emitting the two registered series nothing emits is V1 completion, since V1's
own catalog registers them. Evaluating, delivering, and keeping InferOps's own signals
are feasible on the existing host but deferred out of V1 by
[ADR 0004](../architecture/decisions/ADR-0004-component-and-ownership-boundaries.md) D7,
so taking them on changes an accepted decision and is a later version's. A telemetry
backend other systems' telemetry flows into is a capability a workload declares
through `spec.integrations`, which
[boundary rule 1](../architecture/project-boundaries.md#1-a-capability-a-contract-can-name-is-not-a-capability-this-project-provides)
says this project does not provide.

**`what-held-the-rate-was-not-tested`.** Whether the single slot or the processor held
the rate flat. A bounded rerun with more than one slot, processor throttling sampled,
and a varied or uncached prompt mix is feasible on the existing host and permitted by
[ADR 0013](../architecture/decisions/ADR-0013-bounded-local-performance-observations.md)
as a bounded observation. Naming what limited one declared release belongs here;
raising throughput, batching, or capacity is work on the runtime's own behaviour and
belongs elsewhere under boundary rule 3. No claim moves: sustained throughput and
capacity stay deferred.

**`one-setup-one-author`.** A reference path only its author has followed, on one
machine, is not yet shown to be a reference for anybody. A second person's run is not
something the author can produce. Running on `kind` needs an install the maintainer
declined for the release, and a non-Windows host needs other hardware. Reproducing V1
elsewhere is evidence about V1, not new scope; each new record would certify only its
own host and provider, and neither is read across to the other.

**`the-platform-is-not-defended`.** While ten carried risks block production use,
nothing beyond one loopback host started by hand is possible. An enforcing network
plugin and pod admission can run on a local cluster, and enforcing policy for the
platform's own releases belongs here, in a later version.
[Boundary rule 2](../architecture/project-boundaries.md#2-standing-between-a-caller-and-a-choice-of-providers-is-not-this-projects-job)
places a component in front of several providers elsewhere, and does not settle who
authenticates a single-provider API's own callers: that is a question for ADR 0004 that
this record does not answer. No single record reaches "defended".

**`nothing-real-runs-in-continuous-integration`.** Every real result was produced by
hand. A lane needs a runner authorized to hold the pinned model, and
[ADR 0005](../architecture/decisions/ADR-0005-test-ci-and-certification-strategy.md) D6
and [ADR 0012](../architecture/decisions/ADR-0012-continuous-integration-service.md)
leave that runner unselected.

**`no-real-price`.** The useful cost finding — that reservation and use diverged in
opposite directions — needed no price. A real one needs a provider account and a
budget, neither authorized. An actual-basis record for InferOps's own release belongs
here, because the method exists and is tested; accelerator economics is work on the
runtime's hardware and belongs elsewhere under boundary rule 3. Paying a provider is
not production operation.

**`no-representative-evidence`.** It is the only way to change a level rather than
repeat one, and a higher level is not better evidence for every claim. V1 declared no
intended use beyond a contributor's own machine, so the first step is deciding what to
represent, which widens what V1 is for. `C4` stays out of reach whatever is built:
there is no organizational production to observe.

## Where the work belongs

Three places, and the boundary rules decide which, not the appeal of the work:

- **InferOps, finishing V1.** The self-service road, the other planned claims, emitting
  the series V1's catalog registers, and reproducing V1 on another host or by another
  person. None needs a new decision; all of it is already promised.
- **InferOps, a later version.** Redundancy of its own release, evaluating and
  delivering its own alerts and keeping its own signals, enforcing policy for its own
  pods, a real-runtime lane, an actual price for its own release, and a declared
  representative use. Each changes an accepted decision or what V1 is for.
- **Not this project.** Anything in front of several providers (boundary rule 2), work
  on the runtime's own throughput, batching, capacity, or hardware (rule 3), and a
  capability a workload declares through `spec.integrations` (rule 1). This record
  names no other project and commits to none; that is the boundary document's rule,
  and it holds here.

Who authenticates InferOps's own callers is the one placement this record leaves open.

## Proceed, revise, or defer

### Proceed

Open a second version now, take V1's road as complete for one workload, and widen it to
further workload shapes and the operations V1 left unowned.

- **Problem addressed:** whether the contract generalizes beyond one workload profile.
- **V1 evidence that motivates it:** none. The contract refuses an asynchronous profile
  by design, which records a choice, not a measured need.
- **Evidence if it succeeds:** `C2` for a second profile on the same host and provider —
  a new claim that is still one setup.
- **Prerequisites:** every unmet entry gate, including a road that deploys one workload
  from its contract.
- **Costs and risks:** generality built on a deployment step written by hand, with every
  result again one host, one provider, one replica: what the case study says would not
  justify a second version.
- **Could strengthen:** no existing claim.
- **Would remain unproven:** everything the pod-loss, capacity-gate, telemetry, and
  security findings left open, and the self-service road itself.
- **Overlap with work that belongs elsewhere:** further workload shapes cross no
  boundary rule, and none answers a V1 finding.
- **Refused:** three entry gates are unmet, and its problem is not one V1's evidence
  exposed.

### Revise

Open a second version now, with its problem restated from V1's evidence: **keeping a
caller served, and an operator told the truth, when a serving pod is lost.**

- **Problem addressed:** the one-replica outage and the signals that misdescribed it,
  together.
- **V1 evidence that motivates it:** `one-replica-is-the-outage`,
  `readiness-and-scrape-health-disagreed-with-the-service`, and
  `multi-replica-refused-at-the-capacity-gate`.
- **Evidence if it succeeds:** `C2` on a host that passes the capacity gate, certifying
  only that host; `C3` only if a representative intent and acceptance criteria are
  declared before the run.
- **Prerequisites:** a host that passes the multi-replica capacity gate, authorized and
  budgeted if it is paid for; an amendment to ADR 0004 D7 for alert delivery and a
  durable store; and every unmet entry gate.
- **Costs and risks:** spend nobody has authorized, and drift from redundancy into
  autoscaling and throughput, which boundary rule 3 places elsewhere.
- **Could strengthen:** `multi-replica-serving-is-certified` and
  `an-alert-reaches-somebody`.
- **Would remain unproven:** a lost node, capacity, an availability figure, production
  operation, and any provider not run.
- **Overlap with work that belongs elsewhere:** deeper serving work, if it widens from
  redundancy to throughput or autoscaling; a telemetry backend for other systems, if it
  widens from InferOps's own signals.
- **Not now:** its problem is the right one, but three entry gates are unmet and the
  host it needs is not available. It is kept as the problem statement a later proposal
  starts from.

### Defer

**Selected.** Open no second version now. The next InferOps work, if any, finishes V1's
own claims inside the `v1alpha1` contract; the revised problem statement is held for the
review.

- **Problem addressed:** the self-service road, V1's other planned claims, and a second
  person walking the road.
- **V1 evidence that motivates it:** `the-road-stops-before-deployment`,
  `the-topology-decided-the-error`, and `only-the-author-has-walked-the-road`.
- **Evidence if it succeeds:** `C2` on the existing host for claims V1 already states —
  new claims reaching a record, not repeats of one.
- **Prerequisites:** none beyond the existing host for the planned claims. A second
  person's run and an outside review cannot be produced by the author; they are waited
  for, not scheduled.
- **Costs and risks:** the largest caller-visible effect V1 measured stays unaddressed
  until the review, and a reviewer may reasonably weigh it above closing the road first.
  That is the trade-off in this record most open to rejection.
- **Could strengthen:** the seven planned claims.
- **Would remain unproven:** everything the one-replica, signal, rate, security, lane,
  price, and representative problems name.
- **Overlap with work that belongs elsewhere:** none; all of it is inside V1's boundary
  and contract.
- **Selected because:** it is the only option no unmet gate refuses, and it answers
  findings V1 published rather than a plan.

## Entry gates

A second version opens only when every gate is met. Three are unmet today.

| Gate | Condition | State | Evidence |
|---|---|---|---|
| `a-release-is-cut-over-the-frozen-pack` | A first versioned release is cut over the frozen pack | `met` | The tag `v1.0.0`; the register's release row is still not claimed and is owed a change after the tag |
| `runtime-and-failure-evidence-exists` | Real runtime and failure evidence exists for the road V1 built | `met` | `C2` records for the load matrix, the pod loss, the unready model, and the clean-clone run |
| `the-road-is-closed-for-one-workload` | One workload is served from its validated contract alone | `unmet` | Both contract claims are planned and hold no record |
| `a-second-person-has-reproduced-v1` | Somebody other than the author has completed the clean-clone journey | `unmet` | One run, by the change's author; no second engineer has repeated it |
| `someone-outside-the-repository-has-reviewed-v1` | Somebody outside the repository has reviewed a claim, a record, or the release, and any need they name is weighed | `unmet` | No outside party has reviewed anything; every approval is one role with one holder |
| `the-decision-is-recorded` | A proceed, revise, or defer decision is recorded with its evidence | `met-on-merge` | This record |

The two gates that wait on other people cannot be met by more work from the author, and
this record does not pretend they can. No feedback from outside the repository exists to
weigh, so none is cited.

## Every claim V1 does not certify, and where this decision puts it

| Claim | Status | Placed in |
|---|---|---|
| `the-platform-serves-a-workload-the-contract-describes` | planned | `the-self-service-road-is-open`, `the-road-is-closed-for-one-workload` |
| `deployment-values-derive-only-from-a-validated-document` | planned | `the-self-service-road-is-open`, `the-road-is-closed-for-one-workload` |
| `the-mock-serving-path-identifies-itself-as-a-mock` | planned | `v1-planned-claims-hold-no-record` |
| `a-model-that-is-not-ready-is-a-canonical-error` | planned | `v1-planned-claims-hold-no-record` |
| `an-unreachable-runtime-is-a-canonical-error` | planned | `v1-planned-claims-hold-no-record` |
| `no-prompt-response-or-secret-reaches-a-log-or-a-metric` | planned | `v1-planned-claims-hold-no-record` |
| `no-credential-or-model-artifact-enters-public-history` | planned | `v1-planned-claims-hold-no-record` |
| `sustained-throughput-and-capacity-under-load` | deferred | `what-held-the-rate-was-not-tested` |
| `a-local-cluster-is-created-and-removed-without-residue` | not-claimed | `one-setup-one-author` |
| `multi-replica-serving-is-certified` | not-claimed | `one-replica-is-the-outage` |
| `an-alert-reaches-somebody` | not-claimed | `signals-an-operator-cannot-trust` |
| `what-running-an-inference-workload-costs-on-a-provider` | not-claimed | `no-real-price` |
| `the-rendered-network-policy-is-enforced-by-the-cluster` | not-claimed | `the-platform-is-not-defended` |
| `a-deployed-inferops-workload-is-defended` | not-claimed | `the-platform-is-not-defended` |
| `a-cluster-or-real-runtime-lane-runs-in-continuous-integration` | not-claimed | `nothing-real-runs-in-continuous-integration` |
| `every-certifying-record-lives-under-docs-proof-and-declares-its-own-boundary` | not-claimed | nowhere: it is about how V1's records were written, and neither motivates nor blocks a second version |
| `a-v1-release-has-been-published` | not-claimed | `a-release-is-cut-over-the-frozen-pack` |
| `inferops-is-a-portable-production-platform` | not-claimed | `no-representative-evidence` |

## What would not justify a second version

- More executions of the one-host, one-replica setup, or more `C2` records of the same
  kind: the same observation made more times.
- A feature that makes the repository larger, its tool list longer, or its drawings
  busier without answering a finding above.
- Running on a public cloud or an accelerator for its own sake. Spending on
  infrastructure is not evidence, and paying a provider does not produce production
  operation.
- The existence of an earlier intention to build one. A plan is not a finding.
- Interest in a problem. That latency, reliability, or cost attribution are real
  engineering problems does not show that anybody needs InferOps to solve them, and
  nothing here measures demand.

## Evidence levels a later version could reach

A level describes how one record was obtained, and it is kept apart from what the
workload was, where it ran, and whether anything was substituted. A `C2` record on a
second host is a different observation, not a stronger one of the same kind. A cloud or
accelerator run is `C2`, or `C3` where it meets the representativeness requirements, and
never `C4`: that needs genuine organizational production operation over a stated
period, and this project has none. Every expected level in this record is the level a
successful record could reach, not a result, and none is `C4`.

## Review

Review by **2026-12-27**, or at the first of these:

- `the-review-date` — the review date arrives;
- `the-road-closes` — both planned contract claims are certified;
- `somebody-else-walks-the-road` — a second person completes the clean-clone journey, or
  somebody outside the repository reviews a claim, a record, or the release;
- `a-capable-host-is-available` — a host that passes the multi-replica capacity gate, or
  an authorized budget for one, becomes available;
- `outside-feedback-names-a-need` — feedback from outside the repository names a need
  this record does not list.

A review either confirms this record with a dated note or replaces it with a new
decision; it does not edit the reasoning above in place.

## Where the published evidence still describes the repository before this decision

[The case study's section on what would justify a second version](../case-study/v1-engineering-case-study.md#13-what-evidence-would-justify-a-second-version)
says that whether a second version proceeds "is a separate decision that has not been
made". It is bound to the frozen digests and stays as published. This record is that
decision. Three of its six entry gates — the release, a second person's run, and a road
closed for one workload — are named in that section; the other three are this record's.

## What this record does not do

- **It does not open a second version, schedule one, or name its scope.** The revised
  problem statement says what a later proposal has to prove, not what it contains.
- **It does not add or move a claim,** and it changes no file in the frozen evidence
  pack, no register row, and no ledger.
- **It does not change an accepted decision.** ADR 0004, 0005, 0012, and 0013 are cited
  as they stand; a later version that needs one changed says so in its own record.
- **It does not add an authority.** None of the four in
  [the decision-authority register](decision-authority.md) is a decision to open a
  version; the role that merges accepts this record, and that is accountability, not
  review.
- **It does not name another project.** "Elsewhere" is a boundary, as in
  [the project boundaries](../architecture/project-boundaries.md), not a plan.

## What is machine-checked, and what is not

`tests/testing/test_v2_investment_decision.py` establishes that:

- exactly one option is selected, it is the recorded outcome, and every option states
  every field a comparison needs;
- no option that opens a version is selected while a gate is unmet, and this page lists
  every gate with the state the data holds;
- every claim a finding, a problem, a gate, or an option cites is a register row, and
  every status and record level stated for it is the register's;
- every record a finding points to exists and is cited by that finding's own claims;
- every claim the register does not certify is placed somewhere, or carries a reason
  it is not, and none is placed in something that does not exist;
- every problem answers all three questions from a closed vocabulary, and no expected
  level is `C4`;
- the digests and counts are the evidence index's, every figure is one the case study
  reads back, and no other measurement appears on this page;
- the review date follows the decision and is no more than six months after it;
- the case study still says what this page says it says, and the register's release
  row is still not claimed while the tag is named;
- this page publishes every identifier the data holds, and the README and the
  governance table link it.

What it does not establish: that a problem is correctly judged important, that an
experiment is feasible, that a boundary is drawn in the right place, or that deferring
is the right call. Those are the reasoning, and the reasoning is for a reader to reject.
