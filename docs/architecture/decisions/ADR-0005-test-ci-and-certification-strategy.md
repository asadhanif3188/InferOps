# ADR 0005: Test, CI, and certification strategy

| Field | Value |
|---|---|
| Status | **Accepted in part** |
| Date proposed | 2026-08-25 |
| Date accepted | 2026-08-25, for D1 through D5 only |
| Decision owner | Unassigned; no public maintainer roster exists yet |
| Supersedes | None |
| Superseded by | None |

> [!IMPORTANT]
> This record decides how V1 will be tested and certified. It does **not** configure
> continuous integration. There is no workflow file, no runner, and no automated lane
> in this repository, and nothing in this record or the documents it accepts claims
> otherwise.
>
> One half of it is machine-checked. The strategy is committed as data and validated
> by `tests/testing/test_test_strategy.py`, which also compares it against the
> committed `pytest.ini` in both directions — so "a mock cannot certify C2" and "the
> default lane cannot run a real model" are properties a change has to break a test
> to violate. The other half — whether the layers described will ever be written — has
> no such check, because six of the eleven have no code.
>
> D6 is **not decided**. No continuous-integration service, runner, or hosted
> capable runner is selected, and the lack is recorded rather than filled in.

## Decision status

| ID | Decision | Status | What supports it |
|---|---|---|---|
| D1 | Eleven test layers, each with an evidence class and a certification ceiling | **Accepted** | A committed strategy, with the ceiling enforced by a test |
| D2 | Four lanes, and the default lane downloads no model and touches no cluster | **Accepted** | Enforced by a test over the strategy data and the committed marker expression |
| D3 | Markers registered in `pytest.ini`, with capable-host markers deselected by default | **Accepted**, and executed | The configuration is committed and the suite runs under it |
| D4 | Certification levels C0 to C2 for V1, with class ceilings that stop a mock at C1 | **Accepted** | The published integration certification framework, plus three enforcing tests |
| D5 | Evidence retention: lane artifacts expire, certifying records are committed and do not | **Accepted** as a rule | Review, plus a test that a claim cites a record only when certified |
| D6 | Which continuous-integration service runs the lanes, and what labels a capable runner | **Not decided** | Nothing. No service is selected and no runner is labelled |

## Context

Four decisions are accepted, one contract is published, and two suites run: the
contract suite and the architecture suite. What does not exist is any statement of
which suites there will be, where each runs, and — the part that matters — what a
passing result may be used to claim.

That gap is not neutral, and the way it closes itself is predictable. The next work
in this project writes a platform domain, an adapter, a mock adapter, and an API at
roughly the same time. The mock suite will be the cheapest thing to run and the only
thing that can run on an ordinary machine in seconds. Left undecided, it becomes the
suite that gates every change, and from there the distance to citing it as evidence
that serving works is one hurried pull-request description.

[The mock and real serving boundary](../../serving/mock-and-real-boundary.md) already
forbids that in words, and the words are good ones. What they lack is a mechanism.
This record supplies one.

Two constraints come from outside. The pinned model artifact is large enough that
downloading it on every change is not a cost anybody would pay twice, so the lane
every change goes through cannot involve a model — which means the mock lane is
structurally the default and the strategy must be built around that rather than
against it. And [the project boundaries](../project-boundaries.md) forbid V1
publishing any throughput, latency, capacity, or benchmark figure, which makes a
load-testing layer something to define and defer rather than something to build.

## Decision criteria

| Criterion | Why it matters |
|---|---|
| A mock cannot certify real behaviour | The failure this whole record exists to prevent, and the one that is unrecoverable once published |
| The default lane is cheap | A check that is expensive is a check that gets skipped, and a skipped check is worse than an absent one because it is still in the table |
| Every claim has a layer, an environment, and an owner | An unattributed claim is one nobody reruns when it stops being true |
| The rule survives inattention | A rule enforced only by review is enforced only when the reviewer remembers it |
| Nothing overclaims | A configuration file is not a result; a workflow that has never run is not a lane |
| No decision leaks into an adjacent one | Selecting a test strategy must not silently select a packaging tool or a CI vendor |

## D1 — Eleven test layers with an evidence class and a ceiling

Eleven layers are defined: unit, contract and schema, architecture inventory,
documentation, security scan, adapter, mock integration, Kubernetes smoke, real
runtime smoke, failure and resilience, and capacity and load. Each declares what it
runs against as an **evidence class**, and each class carries a hard **ceiling** on
the certification level a result from it may support.

The alternative was a conventional pyramid — unit, integration, end-to-end — with
prose about what each means. It was rejected for one reason: a pyramid describes the
*shape* of a suite and says nothing about what a result may be used to claim. Two
tests at the same level of a pyramid, one against a mock and one against a real
runtime, are the same shape and are not the same evidence. The layer list here is
organised around the second distinction because it is the one that gets misused.

The ceiling lives in the data rather than in a comment, so the check is `layer's
ceiling ≤ its class's ceiling` rather than `does the reviewer remember`. Six of the
eleven layers have no code. They are registered anyway, because a marker that exists
is the marker the first test of that kind gets written under.

## D2 — Four lanes, and one of them is free

| Lane | Model | Cluster | Opt-in | Timeout |
|---|---|---|---|---|
| Default checks | none | no | no | 15 min |
| Cluster smoke | none | yes | yes | 30 min |
| Real runtime | full, hash-verified | yes | yes | 90 min |
| Capacity | full | yes | yes, and deferred | 240 min |

The acceptance criterion — normal CI runs without a full model download — is stated
as a property of the default lane and tested three ways: the lane declares no model
download; no layer in it may declare that it needs a model or a cluster; and every
marker belonging to a layer outside it must appear in the default exclusion.

Two lanes rather than four was the obvious alternative and it fails on a specific
case: a Kubernetes smoke test needs a real cluster and no model at all. Folding it in
with the real-runtime lane means paying the model cost to test a cluster; folding it
into the default lane means a cluster-dependent test sits in the lane that is supposed
to need nothing. Splitting capacity out separately is not about cost — it is about
publishability, and a lane whose output V1 may not publish should be visibly walled
off.

## D3 — Markers, and the expression that enforces D2

`pytest.ini` registers every marker a layer declares, sets `--strict-markers` so an
unregistered marker is an error rather than a typo, and sets a default marker
expression that excludes `cluster`, `realruntime`, `failure`, and `load`.

This is the executable half of the record. It is also the only part of it that has
run: the suite in this change was developed and executed under this configuration.

`pytest.ini` rather than `pyproject.toml` is deliberate and is the D3 decision that
was nearly made by accident. A `pyproject.toml` is the conventional home for pytest
configuration and would have quietly settled the Python packaging and dependency
questions that [ADR 0001](ADR-0001-local-development-environment.md) D3 and D4 and
[ADR 0003](ADR-0003-workload-contract-schema-tooling.md) all explicitly leave open.
A test strategy has no business selecting a packaging tool.

The third enforcement is the one that catches the realistic mistake: every test module
under a layer's declared paths must carry that layer's marker at module level. Without
it, the markers and the strategy can agree perfectly while `pytest -m contract`
collects nothing.

## D4 — C0 to C2, with class ceilings

V1 certifies at C0, C1, and C2 as
[the published certification framework](../../testing/certification.md) defines them.
C3 and C4 are defined and placed out of V1 scope; a test refuses an active claim
requiring either.

The mechanism that stops a mock at C1 is three checks rather than one sentence:

1. no layer may certify above its evidence class's ceiling, and the `mock` and
   `synthetic` ceilings are C1;
2. a claim requiring C2 or above may not have a mock, synthetic, or estimated layer
   among the layers that qualify to satisfy it;
3. a layer labelled with an unreal class may not also declare that it needs a real
   model, which is the shape a misfiled layer takes.

The alternative — a convention, documented and reviewed — is what the project has had
until now, and it is not obviously insufficient. It was rejected because the cost of
the failure is asymmetric. A review that misses a scope creep produces a slightly
wrong repository; a review that misses a mock certifying real serving produces a
public claim that is false, and no later correction fully undoes it.

## D5 — Evidence retention

A lane's raw output is retained for the period the lane declares — 30 days for cheap
lanes, 90 for expensive ones — and then expires. A record that certifies a public
claim is committed under `docs/proof/` and retained for as long as the claim stands.

The rule that follows: **nothing may cite an expiring artifact as the evidence for a
published claim.** Raw output a claim depends on is promoted into a committed record,
redacted, before the retention window closes. A claim whose evidence was never
promoted is uncertified, and the correct response is to rerun the lane rather than to
describe what the expired artifact used to say.

The alternative was to keep raw artifacts indefinitely. It was rejected because raw
lane output is exactly the material most likely to contain a prompt, a completion, a
host identifier, or a path — and an indefinitely retained store of it is a
public-information hazard that grows on its own. Promotion forces a redaction step at
a moment when somebody is looking.

## D6 — Which service, and what labels a capable runner

**Not decided.** No continuous-integration service is selected and no runner is
labelled capable. The `real-runtime` lane's only reproducible path today is
[the manual feasibility workflow](../../serving/feasibility-workflow.md), which has
been executed once.

This is recorded as undecided rather than filled in with a plausible default because
the choice has consequences this record cannot evaluate: what a capable runner costs,
whether a hosted runner may hold a model artifact at all, and whether the project is
willing to depend on one vendor's workflow syntax. A lane may claim automation only
by naming a workflow file that exists, and a test enforces that, so the gap cannot be
closed accidentally.

## Consequences

- Adding a test that needs a cluster or a model requires naming its marker. It cannot
  arrive in the default lane by accident.
- Adding a public claim requires adding a row with a layer, an environment, a level,
  and an owner. The suite fails on a claim that has none.
- Marking a claim certified requires an executed record under `docs/proof/` **and**
  an implemented layer that produced it. Neither alone is enough.
- Making the mock more faithful does not raise what it can certify. This is intended
  and will occasionally be frustrating.
- Publishing a capacity figure requires deleting a deferral in three places — the
  matrix, the strategy data, and the marker expression — rather than adding a test.
- Seven registered markers currently select nothing. `pytest -m unit` collects zero
  tests, and that is the honest state rather than a defect.
- A second `pytest.ini` decision is now load-bearing: adding a `pyproject.toml` later
  must not move this configuration into it without reopening ADR 0001 D3 and D4.

## Compatibility impact

Compatible. No published schema, contract, error code, rule identifier, or field
location changes. The only behavioural change to an existing command is the default
marker expression, which currently deselects nothing because no test carries a
deselected marker: `python -m pytest tests -q` collects and reports exactly what it
did before this change, plus this change's own suite.

Three existing test modules gain a module-level marker. No assertion in them changes.

## Security considerations

- The retention rule reduces the window in which unredacted raw output exists, and
  forces a redaction step before anything becomes durable.
- The `real-runtime` lane's artifact list excludes prompts and completions explicitly
  rather than by omission.
- `security-scan` is recorded as `planned`, not `implemented`, because a committed
  scan configuration is not a recorded run. Marking it implemented would be the exact
  category of overclaim this record exists to prevent, in the one area where the
  overclaim is a security statement.
- Nothing here implements a control. The trust boundary map in
  [ADR 0004](ADR-0004-component-and-ownership-boundaries.md) is unchanged and remains
  a map.

## Evidence

The change validation for this record is in
[the V1-S0-006-PR1 validation record](../../proof/testing/v1-s0-006-pr1-validation.md).
It is local static evidence for the change itself: the suite runs, deliberate
corruptions of the strategy are refused, links resolve, and the diff carries nothing
private. It is not evidence that the strategy is a good one, and it is not evidence
that any unwritten layer will be written.

The prior records this one leans on are executed: the cluster smoke record, the
runtime feasibility record, and the contract and architecture validation records.
This record adds no runtime evidence of its own, because it ran nothing new against a
runtime.

## Risks, assumptions, and open questions

- **The strategy can be internally perfect and describe nothing.** Six layers have
  no code, and no test can distinguish an honestly planned layer from one that will
  never be written. The mitigation is that a claim cannot be certified from a planned
  layer, so the gap shows up as uncertified claims rather than as silent absence.
- **A determined contributor can still route around the ceiling** by mislabelling a
  layer's evidence class. The checks catch a misplaced layer; they cannot catch a
  deliberate lie about what a suite runs against. That is a review problem and is on
  [the boundary review checklist](../boundary-review-checklist.md) accordingly.
- **The default marker expression is a blunt instrument.** It excludes by marker, so a
  test that needs a cluster and forgets its marker runs in the default lane and fails
  confusingly. The module-level marker check reduces this to "a whole new module with
  no marker", which is visible in review.
- **No runner is labelled**, so the real-runtime lane depends on a contributor's own
  machine and on the manual procedure. If nobody has a capable host, the correct
  outcome is an uncertified claim and a recorded blocker, never a mock result.
- **Assumed:** that the pinned model artifact remains too large to fetch on every
  change. If that stopped being true, D2's central premise would be worth revisiting
  — but the mock ceiling in D4 would still stand, because it is an argument about what
  a mock *is*, not about what it costs.
