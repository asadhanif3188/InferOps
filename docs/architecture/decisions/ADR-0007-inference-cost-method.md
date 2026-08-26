# ADR 0007: Inference cost-calculation method

| Field | Value |
|---|---|
| Status | **Accepted in part** |
| Date proposed | 2026-08-26 |
| Date accepted | 2026-08-26, for D1 through D11 only |
| Decision owner | Unassigned; no public maintainer roster exists yet |
| Supersedes | None |
| Superseded by | None |

> [!IMPORTANT]
> This record decides how a V1 inference cost figure is produced and what it may be
> called. It does **not** produce one. No component in this repository computes,
> emits, stores, or reads a cost record; no invoice has ever been seen; and the only
> rate card committed here is synthetic, so every amount this project can produce
> today is arithmetically correct and economically meaningless.
>
> Most of it is machine-checked. The method is committed as data and validated by
> `tests/cost/test_cost_method.py`, which recomputes every amount, share, and unit
> cost in the worked example in exact decimal from the declared reservations and
> rates, requires the workload lines and the unallocated residual to close against
> the machine exactly, recomputes each record's confidence from its own inputs, and
> derives whether a record field may be committed from the sensitivity class the
> telemetry catalog already gave it. Two of the fourteen rules are enforced by
> **review alone** and are marked as such.
>
> D12 and D13 are **not decided**: no provider rate card is selected, and which
> component computes a cost record remains unowned. The second is deliberately left
> to ADR 0004's open ownership question rather than answered in passing here.

## Decision status

| ID | Decision | Status | What supports it |
|---|---|---|---|
| D1 | Three bases — invoice, allocation, estimate — that are never mixed in one total, and only one of which V1 can reach | **Accepted** | A committed method, with the reachable set and the invoice-vocabulary rule enforced by tests |
| D2 | Allocation is by reserved capacity, not by observed use | **Accepted** | Review, plus a test that recomputes every reservation from the declared request and replica count |
| D3 | Capacity nobody reserved is a reported line, and the parts must close against the whole | **Accepted** | Arithmetic the suite performs on the worked example |
| D4 | Half-open UTC windows, split at a change of reservation | **Accepted** as a rule | Review. The splitting half is enforced by review alone; nothing produces a window |
| D5 | Prices are committed, versioned, dated, and — in V1 — synthetic only | **Accepted** | Tests that every source is committed, that the only class published is synthetic, and that it says so in its own contents |
| D6 | Decimal money at a scale of six, rounded half-even once, with binary and decimal units kept apart | **Accepted** | A test that no binary float appears anywhere in the committed method |
| D7 | A missing input is null with a reason, never a zero | **Accepted** | Tests in both directions over the worked example |
| D8 | Confidence is derived from a record's own inputs, not asserted by its producer | **Accepted** | The suite recomputes it from the declared rules |
| D9 | Every input names a telemetry signal or records that no source exists | **Accepted** | A test comparing each named signal against the committed telemetry catalog |
| D10 | The output shape is published as part of the method and **not** as a contract | **Accepted** | Review, plus the contract package's own rule about publishing in advance |
| D11 | V1 publishes the method and a synthetic example, and no cost figure | **Accepted** as a rule | Review alone. It is a rule about future publications, and no test can hold one |
| D12 | Which provider rate cards a comparison against hosted capacity would use | **Not decided** | Nothing. No provider is selected and no account exists |
| D13 | Which component computes a cost record, and who owns it | **Not decided, and not this record's to decide** | ADR 0004 leaves the equivalent question open; this record does not fill it in |

## Context

Six decisions are accepted, one contract is published, three suites run, one serving
runtime has been proven once, and a telemetry catalog says what a running V1 would
report about itself. What none of it says is what any of it costs.

The gap is not neutral. A cost model is the easiest artifact in a project of this
kind to produce and the hardest to keep honest, because the arithmetic is trivial and
the failure is entirely in the labelling. Multiply a declared processor request by an
invented hourly rate and a number appears. It has six decimal places, a currency, and
no property that resists being placed in a sentence beginning *running this costs*.

There are three specific ways that happens, and all three are cheap:

**An estimate acquires the vocabulary of a bill.** Not by anybody deciding to
mislead — by a column heading. *Spend*, *charges*, *billed*: each is a word somebody
reaches for while writing a dashboard, none of them changes a number, and each of
them converts a model of a cost into a claim about one.

**Idle capacity disappears.** A development host is mostly empty. If the unreserved
share is spread across the workloads it becomes part of a figure that looks like a
workload's cost, and if it is discarded the workload lines quietly sum to a fraction
of the machine. Either way the largest number on the page stops being visible, and
the unit costs that remain look far more defensible than they are.

**A unit cost is published from a handful of requests.** Cost per thousand requests
computed over forty requests has the units of a rate and the meaning of an anecdote,
and nothing in the output distinguishes it from the same figure computed over four
million.

Two constraints come from outside this record. The telemetry catalog records that
**container and node resource use has no source** — the local cluster runs no metrics
server, no collector, and no store — which removes measured utilisation from the
inputs entirely. And [the project boundaries](../project-boundaries.md) forbid V1
publishing any throughput, latency, capacity, or benchmark figure, which turns out to
constrain cost directly: a cost per thousand requests is an hourly reservation
divided by an hour of traffic, so publishing one publishes the traffic.

## Decision criteria

| Criterion | Why it matters |
|---|---|
| An estimate cannot become a bill by accident | The failure is a word, not a number, so the separation has to be structural |
| The parts sum to the whole | A model whose lines do not close hides its largest number, and nobody has to explain a gap that has no line |
| A denominator travels with its quotient | A rate is a division, and the division is where a unit cost stops meaning anything |
| Confidence is computed, not claimed | Confidence typed by a producer is the confidence the producer wanted |
| A missing input is visible as missing | A zero substituted for an absent signal is a measurement that never happened |
| Reproducible on re-run | A price fetched at runtime makes the same computation produce two answers |
| Nothing overclaims | An invented rate applied correctly is still an invented rate |
| No decision leaks into an adjacent one | Choosing how to allocate must not silently choose a provider, a component owner, or a telemetry toolchain |

## D1 — Three bases, and only one of them reachable

`actual` is a figure from an invoice. `allocated` is a price applied to reserved
capacity. `estimated` is a price applied to measured use. A record carries exactly
one; amounts on different bases are never summed; and a record whose basis is not
`actual` carries no invoice reference and none of the vocabulary of one.

Two of the three are unreachable here, and saying so is most of what this decision is
worth today. `actual` needs a provider account this project does not have. `estimated`
needs utilisation telemetry that no component emits and no collector reads. What is
left is an allocation, which is derived from a validated workload document and a rate
card, and needs no running system at all.

The alternative was a single amount with a qualifying sentence next to it. It was
rejected because the sentence and the number travel separately: the number goes into
a table, a slide, or a query result, and the qualification stays in the document
nobody opened. A basis that is a required field on the record goes wherever the
number goes.

Specifying `estimated` despite its being unreachable is deliberate, for the reason the
telemetry catalog names its deferred signals: an unnamed basis is one that gets
reinvented by relabelling an allocation, which is exactly the mistake the separation
exists to prevent.

**Not decided:** everything about producing an `actual` record. No provider, account,
invoice format, or reconciliation exists.

## D2 — Allocation by what was reserved

A workload is charged for its processor, memory, and accelerator requests multiplied
by its replica count and the window length.

Reserved capacity is what the scheduler withholds from everything else, so it is what
a workload genuinely takes from a fixed machine. It is also the only quantity
obtainable here: it is declared in a validated workload document, where `spec.resources`
is required in every environment and a resource-free workload is refused outright.

**The honest cost, stated because the enthusiastic version omits it:** a workload
reserving four cores and using a tenth of one is charged exactly what a workload
saturating four cores is charged. These figures answer *what is this reservation
worth* and cannot answer *is this workload wasteful*. The second question needs
utilisation, and utilisation has no source.

Allocation by observed use is defined and deferred rather than omitted, so that
acquiring a metrics server means deleting a deferral rather than inventing a method.

Allocation by request count was considered and **rejected**, not deferred. It makes
one workload's unit cost a function of its neighbours' traffic: a workload whose own
traffic halves while nothing else changes appears to double in price. That is a
statement about the neighbours, and no amount of future telemetry improves it.

## D3 — The residual is a line, and the lines close

Capacity no workload reserved is reported as its own line, attributed to the
environment. The workload lines plus that residual equal the machine exactly, and a
test requires the closure rather than trusting it.

The two alternatives are the two ways this normally goes wrong. Spreading the residual
pro rata makes a workload's unit cost depend on how empty the machine was, so the same
workload doing the same work changes price when an unrelated workload is deleted.
Discarding it leaves the workload lines summing to less than the machine with nothing
to name the difference.

In the worked example the residual is 69 per cent of the node — the largest line on
the page, and the one both alternatives would have hidden. That proportion is normal
for a development host, which is precisely why the treatment matters more here than it
would on a busy cluster.

Two shared costs are attributed rather than divided. **A prerequisite resource is not
a workload cost**: the model cache deliberately outlives the release that mounts it,
so that uninstalling does not force a re-download over a transport whose downloader
does not validate certificates — the finding
[ADR 0004](ADR-0004-component-and-ownership-boundaries.md) already records. Charging
it to a workload would make deleting that workload look like a saving that does not
occur. **Control-plane overhead is environment cost**, for the ordinary reason that
dividing it produces per-workload numbers that move when the workload count changes.

## D4 — Windows are half-open, in UTC, and split at a change of shape

A window includes its start instant and excludes its end, so adjacent windows neither
overlap nor leave a gap. One hour by default, aligned to the hour, at least a minute
and at most a day.

The rule that costs something is the last one: if a workload's requests, accelerator
count, or replica count changed inside a window, the window is split at the change and
one record is produced per segment. Averaging an allocation across a change of
reservation produces a number describing a machine state that never existed, and
nothing in the output distinguishes it from a state that did.

That rule is **enforced by review alone**, and marked as such, because the component
that would split a window does not exist. Labelling it as tested would have been the
more comfortable and less true option.

## D5 — Prices are committed, and V1's only rate card is synthetic

Every price comes from a rate card committed to this repository, identified by
version and effective date. Nothing fetches a price over a network, because a price
that moves makes a figure irreproducible and a re-run that produces a different number
is not a re-run.

Four classes are defined and exactly one card is published: `synthetic-illustrative-v1`,
whose every rate is invented.

Publishing only a synthetic card is a decision, and it has two halves. A provider rate
card would be a number with the shape of evidence, for a provider this project has
never used, in a region nobody selected. And **a local development host has no hourly
price at all**: a purchase price, an assumed lifetime, an assumed utilisation, and a
power tariff are four guesses, and multiplying four guesses produces a figure with
more decimal places than meaning. The honest options were a synthetic card that says
so or no card at all, and no card would have meant no worked example.

A synthetic card declares its class **inside the artifact**. That is the rule
[the mock and real serving boundary](../../serving/mock-and-real-boundary.md) already
applies to a mock, for the same reason: a label outside the artifact does not survive
the artifact being copied out of the directory that carried the label.

## D6 — Decimal money, one rounding, and units that are not confused

Amounts are decimal strings at a scale of six, rounded half-even once at the end of a
computation and never on an intermediate value. Binary floating point is refused
outright, and a test walks the whole committed method to establish that not one float
appears in it.

Six places rather than two is deliberate. Rounding to a currency's minor unit is a
billing operation and V1 never bills; six places mean a fraction of a cent is neither
rounded into existence nor out of it when many small allocations are summed.

Three conversions are stated rather than assumed, because each has a wrong answer that
looks right. Processor quantities are millicores. Memory quantities are **binary** —
`2Gi` is 2 gibibytes, and reading it as 2 gigabytes introduces a 7.4 per cent error in
every memory line, silently and in the flattering direction. Accelerators are whole
devices, because the workload contract allocates them by count.

## D7 — A missing input is null with a reason

An unavailable input is recorded as unavailable with a reason from a declared list,
and every output depending on it is null. It is never replaced by a zero, a default,
or a value carried over from another window.

Zero is a measurement. Writing zero tokens where there is no token telemetry produces
a record stating that the workload processed nothing, and a cost per million tokens
computed from it divides by a fiction. The suite checks the correspondence in both
directions: a null output must have a declared reason, and a declared unavailable
input must actually be null.

The same decision covers denominators. A unit cost needs 100 requests or 10,000 tokens
before it is reported at all, and a reported one carries the count it was divided by.
Both minimums are **declared, not derived** — no analysis produced them, and a
better-founded threshold would need traffic this project has never had. Recording that
they are arbitrary is cheaper than defending a number that was chosen the same way and
presented as though it were not.

## D8 — Confidence is derived, not asserted

Four levels, six rules, and a derivation: a record's confidence is the lowest ceiling
among the rules whose conditions hold for it, recomputed by the suite. A record whose
declared confidence differs from the derived one fails.

The alternative is the usual one — a `confidence` field the producer fills in. It was
rejected for the same reason the telemetry catalog refuses a chosen placement: a value
somebody types under pressure is a value that reflects what they wanted the record to
say. Deriving it means raising confidence requires changing an input, and changing an
input is visible.

The consequence is worth stating plainly, because it is the least flattering sentence
in this record: **every cost figure this project can produce today has confidence
`none`.** The basis is an allocation and the rate card is synthetic, so two independent
ceilings apply and the lower one wins. That is not a placeholder to be edited later.
It is raised by acquiring a real rate card, then utilisation telemetry, then a bill.

## D9 — Every input names its source, or records that it has none

Each input either names a signal the telemetry catalog declares or states that no
source exists and why. A test compares every named signal against the committed
catalog, so an input cannot claim a source the catalog does not have.

This is the decision that makes the record's central promise checkable rather than
assertable: that the telemetry already specified can supply what the method needs. It
can, for identity and for requests and tokens. It cannot for utilisation, and the
mapping says so in three named gaps rather than leaving the reader to discover it.

One consequence is that **no usage input is available today**, whatever its coverage
says, because no component emits a single signal and no collector reads one. Coverage
describes what the catalog would supply. A test refuses any usage input that claims to
be available.

## D10 — The output shape is part of the method, not a contract

A cost record's shape is published here, in the method's own data. No schema for it is
added under `contracts/`.

The contract package's rule is that a schema is added when the capability behind it
exists rather than in advance, and it already names a cost record among the things not
yet published. Nothing produces or consumes one, so a schema would be a commitment to
a consumer that does not exist, versioned and compatibility-constrained from the day it
was written.

One property of the shape is derived rather than chosen, and it is the one somebody
would otherwise get wrong. Whether a field may appear in a record committed to this
repository is read from the sensitivity class the telemetry catalog already assigned
it. `identity.tenantId` is `tenant-attributable`, a class with no permitted placement
in an evidence record, so the tenant identifier is absent from the worked example and
from anything else this repository will ever commit — while remaining a field the
runtime record carries. A test derives the permission from the class rather than
reading a flag, so the method and the catalog cannot disagree about it.

## D11 — V1 publishes the method, and no figure

What is published is this method and a synthetic worked example. No figure for what
running an inference workload costs is published, and none can be.

The reasoning is a consequence of a boundary this project already accepted rather than
a new restriction. A cost per thousand requests is an hourly reservation divided by an
hour of traffic; publishing the quotient publishes the divisor. Since V1 may publish no
throughput figure, it may publish no cost-per-request figure either.

This rule is **enforced by review alone**. It is a rule about future publications, and
no test in this repository can hold one.

## D12 — Provider rate cards: not decided

No provider is selected and no account exists. Committing a rate card for a provider
this project has never used would publish a number with the shape of evidence and none
of the substance, and it would silently select a provider in a cost document.

## D13 — Who computes a cost record: not decided here

No component computes one, and the ownership inventory assigns the work to nobody.
[ADR 0004](ADR-0004-component-and-ownership-boundaries.md) already records that a
telemetry collector is unowned and defers that question deliberately; this record does
not answer the equivalent question for cost. A method that nominated an owner in
passing would be answering an architecture question in a cost document, which is the
leak this record is written to avoid.

## Consequences

- The first component to produce a cost figure has a basis it must declare, a
  denominator it must carry, and a confidence it cannot type.
- Every record this project can produce today lands on confidence `none`, and raising
  that requires acquiring something rather than editing something.
- Idle capacity is a line rather than an absence, which makes a development host's
  economics visible and unflattering.
- Three telemetry gaps are named, so the case for a metrics server is now written down
  with the thing it unblocks attached to it.
- The telemetry catalog's two cost placeholders — a cost-record identifier and a
  cost-record counter — keep their deferrals, and their stated reasons are corrected:
  they were deferred because no cost method existed, and they remain deferred because
  nothing computes a cost record.
- The claim and test matrix gains one claim, certified at `C0` by the documentation
  layer: that a cost figure in this repository cannot be presented as a bill. It
  certifies a committed method and nothing about a running system.
- Nothing here reduces the work of measuring a real cost. It reduces the number of
  decisions that measurement is allowed to make on its own.

## Compatibility impact

None to any published interface. The workload contract, the rejection interface, the
ownership inventory, and the telemetry catalog's signal names are unchanged. The test
strategy gains one claim row and one path on an existing layer; no layer, lane,
marker, evidence class, or certification level changes.

Two deferral reasons in the telemetry catalog are corrected in this change, because
this record makes them false: `inferops.cost.record.id` and `inferops_cost_records_total`
were deferred on the grounds that no cost method was defined. Both remain deferred, on
the accurate grounds that nothing computes or emits a cost record. No name, class,
placement, or budget changes, and neither signal moves from deferred to active.

The record shape published here is versioned as `v1alpha1` and is **not** a contract.
Renaming a field after a component emits one would be a breaking change for a consumer;
today nothing emits and nothing consumes, which is the cheapest moment there will ever
be to get the names wrong and fix them.

## Security considerations

Two things in this record are security decisions rather than accounting ones.

**A cost record is an attribution record.** It ties an amount to a workload, an owner,
an environment, and a tenant, which makes it a more sensitive artifact than its subject
suggests. The tenant identifier is therefore barred from any record committed here, by
derivation from the class the telemetry catalog already gave it rather than by a rule
somebody applies. The field remains in the runtime shape, where the catalog permits it
in logs and traces.

**No price is fetched at runtime.** That is stated as a reproducibility rule above, and
it is also the rule that keeps a cost computation from making an outbound network call
from inside a cluster in order to produce a number.

The residual risk is stated plainly: none of this is enforced at runtime, because there
is no runtime. A producer that ignores every rule here would fail no test in this
repository, and no claim in this record should be read as covering one.

## Evidence

[The change validation record](../../proof/cost/v1-s0-008-pr1-validation.md), which is
local static evidence for this change: the method is internally consistent under every
rule the suite states, the worked example's arithmetic is recomputed in exact decimal
and closes, deliberate corruptions of it are each refused, every telemetry signal it
names appears in the catalog that declares it, every relative link resolves, and the
existing suites are unchanged.

There is no evidence that any cost record has ever been produced, because none has, and
no evidence about what anything costs, because the only rate card here is invented.
