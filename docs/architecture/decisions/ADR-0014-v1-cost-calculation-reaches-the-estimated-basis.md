# ADR 0014: The V1 cost calculation reaches the estimated basis, from bounded measured use

| Field | Value |
|---|---|
| Status | **Accepted in part** |
| Date proposed | 2026-09-15 |
| Date accepted | 2026-09-15, for D1, D2, D4, D5, and D6; D3 is accepted as a rule, half of it enforced, and D7 as a scope rule |
| Decision owner | Unassigned; no public maintainer roster exists yet |
| Supersedes | None |
| Amends | [ADR 0007](ADR-0007-inference-cost-method.md) D1, D2, D3, and D9, clarifies the scope of its D13, and amends the committed method data that carries them |
| Superseded by | None |

> [!IMPORTANT]
> Until this record, V1 could reach one cost basis, `allocated`: a price applied to
> what a workload *reserved*. `estimated`, a price applied to what it was *measured
> using*, was unreachable because no utilisation had ever been measured. Since
> `V1-S4-004`, the pod cgroup processor counters and memory readings of a
> declared local experiment are committed evidence
> ([ADR 0013](ADR-0013-bounded-local-performance-observations.md)).
>
> This record makes `estimated` the **only** basis V1 calculates, selects the
> allocation method that basis needs, states what counts as measured use, and adds a
> repository tool, `tools/cost_calculation`, that applies the method to one declared
> input document.
>
> **What does not change.** No cost figure is published: ADR 0007 D11 stands, and the
> only committed rate card is still synthetic, so every record the tool can produce
> has confidence `none` and is economically meaningless. No provider rate card is
> selected (D12). Which platform component computes and emits a cost record in a
> running system stays undecided; D13 is clarified to mean that question, and a
> repository tool run by hand is outside it (D7). The tool runs by hand, contacts
> nothing, and emits no telemetry. Every usage value it reads is **typed in by hand**; nothing in
> this repository reads it from the committed samples yet.

## Decision status

| ID | Decision | Status | What supports it |
|---|---|---|---|
| D1 | V1 calculates the `estimated` basis only; `actual` and `allocated` are refused | **Accepted** | The method's reachable set is tested, and the tool refuses the other two before writing anything |
| D2 | `observed-utilisation-share` is selected; `requested-resource-share` is deferred | **Accepted** | The method's selection is tested, and the tool refuses a method selecting anything else |
| D3 | What counts as measured use, and how a usage value is taken from samples | **Accepted as a rule.** The evidence half is tested; the integration half is review only, because no reader exists | Tests that synthetic usage never derives `hasMeasuredUtilisation` and that a measured class must name a committed record of that class, and nothing for the integration rules |
| D4 | The estimated amount, its unallocated line, and what closes; amends the meaning of ADR 0007 D3's line | **Accepted** | Fixtures whose figures are held to values worked out by hand, a closure check the tool runs on every result, and tests of every capacity bound |
| D5 | Exact arithmetic, rounded once, and which figures are taken from which | **Accepted** | Rounding tests at the tie, and a test that a unit cost is divided from the exact amount |
| D6 | The hourly figure and the cost-per-request figure | **Accepted** | Tests over the fixtures, and the unchanged denominator minimums |
| D7 | A repository tool computes a record by hand; ADR 0007 D13 is clarified, and nothing else about ownership or publication moves | **Accepted** as a scope rule | Review, and the method's `computationStatus`, which a test reads |

## Context

ADR 0007 D1 defined three bases and made one reachable. Its reasoning was specific:
`estimated` "needs container and node utilisation telemetry that no component emits
and no collector here collects", so what was left was an allocation. It specified
`estimated` anyway, because "an unnamed basis is one that gets reinvented by
relabelling an allocation, which is exactly the mistake the separation exists to
prevent". D2 likewise deferred `observed-utilisation-share` "so that acquiring a
metrics server means deleting a deferral rather than inventing a method".

Two things have happened since. `V1-S4-004` ran a declared scenario matrix on
`docker-desktop` and committed, beside it, the pod cgroup processor counters and
memory working-set readings for every release pod, sampled every few seconds. Each
sample carries the host's wall-clock time, which places it in a load phase, and the
node's own clock, which processor rates are computed over. And `V1-S4-005` asks for
an hourly figure and a cost-per-request figure on the estimate basis, validated against
the shape the method publishes.

That leaves a choice ADR 0007 could not make: whether to keep producing the basis that
needs no measurement now that a measurement exists, to produce both, or to move to the
one the method was written to reach. It is recorded here rather than made in code,
because a producer that quietly started emitting `estimated` records is exactly the
relabelling ADR 0007 exists to prevent.

## Decision criteria

| Criterion | Why it matters |
|---|---|
| An estimate and an allocation cannot be read as one number | ADR 0007's whole argument is that the failure is a label, not arithmetic |
| A synthetic measurement cannot acquire a measurement's confidence | Confidence derived from a flag the preparer sets is confidence asserted |
| The parts still close against the whole | The unallocated line is the largest number on a development host and the easiest to lose |
| What is typed by hand is said to be typed by hand | A tool that reads a number off a form looks, from its output, like one that measured it |
| No publication rule moves | D11 is a decision in its own right, and ADR 0013 already declined to move it |

## D1 — V1 calculates the estimated basis, and only that

**Accepted.** A V1 cost calculation produces records whose basis is `estimated`. A
request for `actual` is refused with ADR 0007's reason: no invoice exists. A request
for `allocated` is refused as well.

Refusing `allocated` is the decision here. The arithmetic is trivial and the tool could
produce it. It does not, because an allocation and an estimate of one workload over
one window answer different questions — *what was this reservation worth* and *what
was this use worth* — and a producer able to emit both puts them side by side in a
table where they are read, and sooner or later summed, as one figure. One basis per
calculation removes that possibility structurally rather than by a sentence.

What a workload reserved is not lost. Every estimated record still carries its
reserved core-hours, gibibyte-hours, and device-hours, so the reservation and the
measured use sit next to each other without the reservation being priced. The
allocation arithmetic stays specified in the method and demonstrated by
[the synthetic worked example](../../cost/worked-example.md), which no calculation
produces; its figures are unchanged, and it gains a note saying which basis it shows.

**Enforcement.** The method data marks `estimated` as the only reachable basis, and a
test requires it. The tool refuses to run against method data that says otherwise, and
refuses an input naming another basis before any figure is written; both are tested.

## D2 — Observed use is the allocation method

**Accepted.** `observed-utilisation-share` is selected and its deferral is deleted, as
ADR 0007 D2 said it would be. `requested-resource-share` becomes `deferred`, with the
reason that it produces a basis V1 does not produce. `request-count-share` stays
rejected, for ADR 0007's reason, which no measurement changes.

The honest cost is the one the method data already recorded for observed use, though
ADR 0007's text did not: it rewards a workload for reserving capacity it does not use. Under this basis that idle
reservation lands on the unallocated line rather than on the workload's record (D4).

## D3 — What counts as measured use

**Accepted as a rule.** A calculation input names the **evidence class** its usage
values came from, from the test strategy's declared classes. `local-real-cpu`,
`cloud-real-cpu`, and `cloud-real-gpu` are measured classes; `synthetic` is not; no
other class may supply usage. A synthetic input must say it is synthetic in its own
warning and names no evidence. A **measured class must name the committed record** its
usage came from, under `docs/proof/`, by path and by the SHA-256 of its content with
line endings normalized to LF, and that record must declare the same evidence class.
Only then, with processor and memory use both present, does a record's
`hasMeasuredUtilisation` fact hold; whether a reserved device's seconds are available
does not decide it.

A usage value is taken from committed samples of a declared experiment that qualifies
under ADR 0013 D3, as follows:

- **processor seconds** are the increase of each pod's cumulative cgroup processor
  counter between the samples that bound the window, summed over the workload's pods.
  The committed samples are per pod, not per container. A counter that resets inside the window makes the value unavailable
  with the reason `input-conflict`; no reset is stitched;
- **memory byte-seconds** are each pod's cgroup working-set bytes integrated
  trapezoidally between consecutive samples inside the window, summed over its pods,
  and never extrapolated before the first sample or after the last. A window the
  samples do not cover end to end is recorded as incomplete;
- **requests and tokens** are the counts the experiment's raw records hold for the
  window, reconciled with the collector's counters where the record does so;
- **accelerator seconds** stay unavailable: no accelerator has been used.

**Enforcement.** The evidence rule is enforced by the tool and tested: the class is
checked against the list, and a measured class's named record is checked to exist, to
match its digest, and to declare that class. That establishes that the evidence exists
and is of the class claimed, and nothing more. The integration rules above are **review
only**: no reader in this repository takes a usage value from the samples. Every usage
value in an input today is typed in by hand, and the tool can check that it is shaped
correctly and fits within the node's declared capacity for the window, but cannot check
that it matches the record it names, which it does not read beyond its class. That gap
is stated, not closed.

## D4 — The estimated amount, and what closes

**Accepted.** A workload's estimated amount is

```text
(cpuSeconds * rate(cpu-core-hour)
  + memoryByteSeconds / 2^30 * rate(memory-gibibyte-hour)
  + acceleratorSeconds * rate(accelerator-device-hour)) / 3600
```

Memory is binary, as ADR 0007 D6 requires. The **accelerator term is absent**, not zero,
when the workload reserves no device: a device nobody reserved cannot have been used,
and writing zero seconds would be a measurement nobody took. A workload that reserves a
device and has no measured device seconds has a null amount, with the reason.

The node's capacity amount is its declared allocatable capacity priced over the window,
as before. The **unallocated line** is that amount less the workload amounts. Under this
basis it means capacity **no workload in the calculation was measured using**: idle
capacity, reservations left unused, the platform and control plane, and any workload
the input does not list. It is reported, never spread, and the workload lines plus it
close against the node exactly. This **amends the meaning of ADR 0007 D3's line**,
which was capacity nobody reserved; its treatment, reported and never spread, is
unchanged. If any workload amount is null, the unallocated line is
null too, with the reasons that made it so, because a residual taken over the lines that
exist would hand the missing workload's use to nobody.

Measured processor, memory, or device use that exceeds what the node's declared
capacity holds in the window, for one workload or all of them together, is refused as
conflicting inputs. So is a workload reserving more devices across its replicas than the
node declares, and a device second reported for a workload that reserves no device.
With no device reserved, device seconds are **not applicable**: the input is null, no
reason is declared for it, and it is not listed as unavailable, because it is not a gap. A prerequisite resource keeps
ADR 0007 D3's attribution to the prerequisite layer and is refused if attributed to a
workload.

## D5 — Exact arithmetic, rounded once

**Accepted.** Every intermediate value is an exact rational number. A published figure
is rounded **once**, half-even, to six places, from exact values — never from another
rounded figure. A share, an hourly figure, and a unit cost are therefore each divided
from the workload's exact amount: a workload whose exact amount rounds to `0.000000`
still has a cost per thousand requests if its inputs support one.

One figure is taken from published figures on purpose. The unallocated amount is the
published node amount less the published workload amounts, so that the lines a reader
sees close exactly; that subtraction of six-place decimals is itself exact, so it adds
no rounding. Its share is divided from those same published figures. Shares are
each rounded on their own, so the published shares of a result need not add to exactly
one; the amounts close, and the shares are not required to.

## D6 — The hourly figure and the cost-per-request figure

**Accepted.** Each record carries `derived.amountPerHour`, the amount divided by the
window's length in hours. It is the rate at which the amount accrued **over that
window** and projects nothing beyond it. Over a short window it is the amount scaled
up, and reads like a run rate; it is meaningful only beside the window it carries.
ADR 0007 D4's window rules are unchanged, so a window is at least a minute and at most a
day, and a window of the default length, one hour, starts on the hour; the tool refuses
one that does not.

The cost-per-request figure is `derived.costPerThousandRequests`, carrying the request
count it was divided by. It is quoted per thousand rather than per request because six
places would round a single request's cost on the synthetic card to a figure with one
or two significant digits. ADR 0007 D7's minimums — 100 requests and 10,000 tokens —
are unchanged, and below them the figure is null with the reason
`below-minimum-sample`.

## D7 — A repository tool computes; ownership and publication do not move

**Accepted** as a scope rule. `tools/cost_calculation` is a repository tool, in the same
position as `tools/performance_findings`: run by hand over committed files, contacting no
cluster, network, or telemetry store, and emitting nothing. It validates every record it
writes against the record shape the method publishes, which gains the rate card's
version and effective date, the facts confidence is derived from, and the usage
evidence class; a record's amount may now be null.

That is not an answer to ADR 0007 D13, and this record **clarifies** D13 rather than
leaving it literally true: its sentence "No component computes one" now reads as no
platform component. The question it keeps open — which platform component computes and
emits a cost record in a running system, and who owns it — stays not decided, and a
hand-run repository tool is outside the ownership question ADR 0004 leaves open. ADR 0007 D10 is
unchanged: the shape is part of the method, and no schema is published under
`contracts/`. ADR 0007 D11 is unchanged: V1 publishes the method and synthetic examples,
and no figure for what running an inference workload costs.

## What ADR 0007 keeps

D3's treatment of its line (reported, never spread, closing), D4's windows, D5's
committed and synthetic-only prices, D6's decimal money and binary memory, D7's null with
a reason, D8's derived confidence, D10, D11, and D12 are unchanged. D3's line changes
meaning (D4 above) and D13 is clarified (D7 above). The text of ADR 0007 is kept as it
was accepted, with a pointer to this record beside D1, D2, D3, D9, and D13.

## Consequences

- The method data reaches `estimated` alone, selects `observed-utilisation-share`, marks
  processor seconds, memory byte-seconds, requests, and tokens as obtainable in V1 from a
  bounded experiment by hand, and states that only a repository tool computes a record.
  Processor seconds and memory byte-seconds no longer name the catalog's process metrics,
  which never supplied them. The cost-record identifier becomes obtainable, declared by
  an input. The status counts three synthetic records produced and none measured.
- Five rules join the method, each enforced by a test, bringing it to nineteen: seventeen
  by test and two by review.
- The unallocated line on a development host now holds idle reservations as well as
  unreserved capacity, so it grows. That is the visible form of D2's honest cost.
- A record's confidence is still `none` wherever the synthetic card is used, which is
  everywhere. Measured use raises the ceiling of the basis, not of the card.
- The telemetry catalog's deferral of `inferops.cost.record.id` and
  `inferops_cost_records_total` stays, and its reason is corrected: something computes
  a cost record by hand, and nothing emits one.

## Compatibility impact

No published contract, schema, chart value, or command changes. The method data is
versioned `v1alpha1` and is not a contract; nothing consumes it except its own suites
and the new tool. Within it, `computationStatus.costRecordsProduced` is replaced by
`syntheticRecordsProduced`, `measuredRecordsProduced`, and `publishedCostFigures`, the
record shape gains four fields, and a record's amount becomes nullable. The worked example and its figures are unchanged.

## Security considerations

A cost record ties an amount to a workload, an owner, and an environment. The tool
refuses an input carrying a tenant identifier, which the telemetry catalog classes as
having no permitted placement in a committed record, and refuses any input carrying a
value shaped like a Windows drive path, a `/Users` or `/home` directory, or an IPv4
address other than loopback. It does not recognize host names, IPv6 addresses, or other
directories; those are left to review. It reads a
price only from the committed method and makes no outbound call.

## Evidence

[The change validation record](../../proof/cost/v1-s4-005-pr1-validation.md): the method
data and the tool's suites, the committed synthetic fixtures regenerating byte for byte,
and the figures in them held to values worked out by hand. It is `local-static` and
`synthetic` evidence. No usage value in it was measured, and no cost record has been
calculated from the `V1-S4-004` evidence.

## Risks, assumptions, and open questions

- **Hand-typed inputs are the weak point.** D3's integration rules are written and not
  executed. Until a reader applies them to committed samples, a calculation's usage
  values are exactly as good as whoever typed them.
- **A container's working set is not only its own allocations.** It counts file-backed
  pages the kernel charges to the container, so a memory-mapped model file is counted
  as far as the kernel charges it. The memory line prices what the kernel reported, not
  what the process allocated.
- **A cgroup processor counter counts every thread in the container**, including work
  the workload did not do for a request. That is the correct quantity for pricing use
  and the wrong one for attributing it to requests.
- **Assumed:** that one basis per calculation is enough. A reader who wants to compare
  an allocation with an estimate of the same window has no tool for it, and gets two
  documents rather than one table. That is deliberate, and it may prove inconvenient.
