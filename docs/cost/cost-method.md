# The V1 inference cost method

Status: **accepted**, in
[ADR 0007](../architecture/decisions/ADR-0007-inference-cost-method.md). The method
is committed as data and machine-checked. Nothing computes it: no component in this
repository produces, emits, stores, or reads a cost record, no invoice has ever been
seen, and the only rate card committed here is synthetic.

The authoritative form is
[`cost-method.v1alpha1.json`](cost-method.v1alpha1.json). This document and that file
are compared in both directions by [`tests/cost/`](../../tests/cost/): an input,
an output, a unit, or a rule cannot appear in one without appearing in the other.

## What this document decides

Four things, in the order they are usually got wrong.

**What kind of number it is.** Every amount carries a basis, and a basis is not a
label of convenience: `actual` means an invoice, `allocated` means a price applied to
reserved capacity, `estimated` means a price applied to measured use. Two of the
three are unreachable here, and saying which is unreachable and why is most of the
value this record has today.

**Whose number it is.** A machine has one cost and several occupants. This method
allocates by what each workload reserved, reports what nobody reserved as its own
line, and requires the parts to add up to the whole exactly.

**What it is divided by.** A cost per thousand requests is a division, and the
denominator decides whether the result means anything. Every unit cost here carries
the count it was divided by and disappears below a declared minimum.

**How much it may be trusted.** Confidence is not typed by whoever produced the
record. It is the lowest ceiling among the rules that apply to the record's own
inputs, recomputed by the suite, and every record this project can produce today
lands on `none`.

## 1. Basis: what kind of number this is

| Basis | What it means | Reachable in V1 |
|---|---|---|
| `actual` | Taken from a provider's invoice or billing export for the period it covers | No. This project has no provider account, no invoice, and no billing export |
| `allocated` | A price applied to the capacity a workload reserved, whether or not it used any | Yes, and it is the only one |
| `estimated` | A price applied to observed utilisation over the window | No. There is no metrics server, collector, or store, so there is nothing to integrate |

Three rules travel with the basis:

- a record carries exactly one basis;
- amounts on different bases are never summed into one total;
- a record whose basis is not `actual` carries no invoice reference and no field
  from which one could be inferred.

The last is the one worth enforcing rather than intending, because the failure is a
single word. An allocation described as *spend*, a total labelled *billed*, a column
headed *charges* — each of them turns a model of a cost into a claim about one, and
none of them changes a number. A test reads every committed record and fails if a
record that is not `actual` uses any of those words.

`estimated` is specified here despite being unreachable, for the same reason the
telemetry catalog names deferred signals: a basis that is not written down is a basis
that gets reinvented by relabelling an allocation, and the relabelling is exactly the
mistake the separation exists to prevent.

## 2. Allocation

| Method | What it charges for | Status |
|---|---|---|
| `requested-resource-share` | The processor, memory, and accelerator capacity a workload reserved, times its replica count, times the window | **Selected** |
| `observed-utilisation-share` | The capacity it was measured to use | Deferred; every input it needs is unavailable |
| `request-count-share` | A share of the node proportional to requests served | Rejected |

Reserved capacity is what the scheduler refuses to give to anything else, so it is
what a workload actually takes from a fixed machine. It is also the only quantity
this project can obtain: it is declared in a validated workload document, where
`spec.resources` is required in every environment and a resource-free workload is
refused.

**The honest cost of this choice**, stated because the enthusiastic version omits it:
a workload that reserves four cores and uses a tenth of one is charged exactly what a
workload that saturates four cores is charged. That is correct capacity accounting
and useless efficiency accounting. These figures answer *what is this reservation
worth*, and they do not answer *is this workload wasteful*. The second question needs
utilisation, and utilisation has no source.

`request-count-share` is rejected rather than deferred, and the reason generalises:
it makes one workload's unit cost a function of its neighbours' traffic. A workload
whose own traffic halves while nothing else changes appears to double in price. That
is a statement about the neighbours.

## 3. Idle and shared cost

| Treatment | What it does | Chosen |
|---|---|---|
| `report-separately` | Unreserved capacity is its own line, attributed to the environment | **Yes** |
| `spread-pro-rata` | Unreserved capacity is divided between workloads in proportion to what each reserved | No |
| `discard` | Unreserved capacity is not costed | No |

Reporting it separately is the only treatment under which the workload lines and the
residual add up to the machine, and a test requires them to close exactly. The other
two each hide the same number in a different place: spreading it puts idle capacity
inside a figure that looks like a workload's cost, and discarding it leaves the parts
summing to less than the whole with no line to explain the gap.

In the worked example the unallocated line is the largest number on the page. That is
the normal case on a development host and it is the case a cost model most often
conceals.

Two shared costs are attributed rather than divided:

- **A prerequisite resource is not a workload cost.** The model cache deliberately
  outlives the release that mounts it, so that uninstalling does not force a
  re-download over a transport whose downloader does not validate certificates. A
  cost that survives the workload is not the workload's, and charging it to one makes
  deleting the workload look like a saving that does not occur.
- **Control-plane and platform overhead is environment cost.** It is real, it is
  shared, and dividing it produces per-workload numbers that move when the workload
  count changes.

## 4. Time windows

| Rule | Decision |
|---|---|
| Interval | Half-open: the start instant is included, the end instant is excluded, so adjacent windows neither overlap nor leave a gap |
| Time zone | UTC only, RFC 3339 with an explicit offset |
| Default length | One hour, aligned to the hour |
| Bounds | At least one minute, at most one day |
| Partial existence | A workload present for part of the window is charged for that part, and the record is marked incomplete |
| Shape change | A change of resource request, accelerator count, or replica count splits the window; one record per segment |

The shape-change rule is the one that costs something to follow. Averaging an
allocation across a change of reservation produces a number describing a machine
state that never existed, and nothing in the output distinguishes it from a state
that did. It is **enforced by review alone**, because the component that would split
a window does not exist.

## 5. Prices

Every price comes from a rate card committed to this repository. Nothing retrieves a
price over a network while computing, because a price that moves makes a figure
irreproducible, and a re-run that produces a different number is not a re-run.

Four classes of rate card are defined and exactly one card is published:

| Class | What it is | Ceiling it puts on confidence | Published |
|---|---|---|---|
| `provider-list-price` | A named provider's published rates, captured at a version and date | `medium` | None |
| `negotiated-price` | A contracted rate | `high` | None |
| `amortised-hardware` | A machine's purchase price, power, and lifetime reduced to an hourly rate | `low` | None |
| `synthetic-illustrative` | Invented rates that exist to demonstrate the arithmetic | `none` | One |

The published card is `synthetic-illustrative-v1`, effective 2026-08-26, in USD:

| Unit | Rate per hour |
|---|---|
| `cpu-core-hour` | 0.040000 |
| `memory-gibibyte-hour` | 0.005000 |
| `accelerator-device-hour` | 1.200000 |
| `storage-gibibyte-hour` | 0.000100 |

**Every one of those numbers is invented.** They were chosen to be round enough that
the worked example can be followed by hand, and they correspond to no provider, no
region, no contract, and no machine.

Publishing only a synthetic card is a decision rather than an omission, and it has
two reasons. A provider rate card would be a number with the shape of evidence for a
provider this project has never used. And a local development host has no hourly
price at all: hardware amortisation, an assumed lifetime, an assumed utilisation, and
a power tariff are four guesses, and multiplying four guesses produces a figure with
more decimal places than meaning.

A synthetic card declares its class **inside the artifact**, not in the directory
holding it — the same rule
[the mock and real serving boundary](../serving/mock-and-real-boundary.md) already
applies, for the same reason: a label outside the artifact does not survive the
artifact being copied out.

## 6. Units and precision

| Unit | Meaning | Priced |
|---|---|---|
| `cpu-core-hour` | One processor core held for one hour | yes |
| `memory-gibibyte-hour` | One gibibyte of memory held for one hour | yes |
| `storage-gibibyte-hour` | One gibibyte of persistent storage claimed for one hour | yes |
| `accelerator-device-hour` | One accelerator device held for one hour | yes |
| `request` | One request accepted by the platform, whatever its outcome | no |
| `token` | One token as counted by the runtime's own tokeniser | no |
| `second` | One second of wall-clock time | no |
| `count` | A whole number of replicas or devices | no |
| `instant` | A point in time | no |
| `identifier` | A name that identifies rather than measures | no |
| `currency` | An amount of money in the record's declared currency | no |
| `ratio` | A dimensionless proportion between zero and one | no |

Three conversions are stated rather than assumed, because each has a wrong answer
that looks right:

- **Processor quantities are millicores.** `500m` is half a core, and the conversion
  happens before any price is applied.
- **Memory quantities are binary.** `2Gi` is 2 gibibytes, where a gibibyte is 2^30
  bytes. Reading it as 2 gigabytes introduces a 7.4 per cent error in every memory
  line, silently and in the flattering direction.
- **Accelerators are whole devices.** There is no fractional device, no time-slicing,
  and no partitioning, because the workload contract allocates devices by count.

Money is a **decimal string** at a scale of six, never a binary float: a tenth has no
binary representation, and a cost model that disagrees with itself on re-run is worse
than no cost model. Rounding is half-even and happens **once**, at the end of a
computation, never on an intermediate value.

Six places rather than two is deliberate. Rounding to a currency's minor unit is a
billing operation and V1 never bills; keeping six places means a fraction of a cent
is neither rounded into existence nor out of it when hundreds of small allocations
are summed.

## 7. Missing data

An input that is not available is recorded as unavailable **with a reason**, and
every output depending on it is null. It is never replaced by a zero, a default, or a
value from another window.

Zero is a measurement. Writing zero tokens where there is no token telemetry produces
a record stating that the workload processed nothing, and a cost per million tokens
computed from it divides by a fiction.

| Reason | What it means |
|---|---|
| `no-telemetry-source` | No component emits the signal, or no collector reads it |
| `runtime-does-not-expose` | The serving runtime does not publish the quantity and nothing derives it |
| `below-minimum-sample` | The denominator exists and is below the declared minimum for a unit cost |
| `outside-window` | The value exists but belongs to a period this record does not cover |
| `input-conflict` | Two sources disagree and the method has no rule for choosing |
| `no-producer` | Nothing computes this record, so the field has never been populated |

A unit cost needs **100 requests** or **10,000 tokens** before it is reported at all,
and a reported one always carries the count it was divided by. Both minimums are
**declared, not derived**: no analysis produced them, they are round numbers chosen
to be obviously too small to publish from, and a better-founded threshold would need
traffic this project has never had.

## 8. Confidence

| Level | What it means |
|---|---|
| `none` | Structurally valid and economically meaningless. It demonstrates the arithmetic |
| `low` | A real price applied to declared capacity. It says nothing about what was used |
| `medium` | A real price applied to measured utilisation over a complete window |
| `high` | Taken from an invoice for the period it covers |

Confidence is **derived, not asserted**. Each rule below states a condition and the
ceiling it imposes; a record's confidence is the lowest ceiling among the rules that
apply to it, and a record whose declared confidence differs from the recomputed one
fails the suite.

| Rule | Condition | Ceiling |
|---|---|---|
| `high-requires-a-provider-invoice` | The basis is not `actual` | `medium` |
| `an-allocation-is-not-a-measurement` | The basis is `allocated` | `low` |
| `an-estimate-without-measured-utilisation-is-an-allocation` | The basis is `estimated` and no utilisation input was measured | `low` |
| `a-synthetic-rate-card-carries-no-confidence` | The rate card is synthetic | `none` |
| `an-incomplete-window-caps-at-low` | The window is incomplete | `low` |
| `an-unsplit-shape-change-carries-no-confidence` | The reservation changed inside the window | `none` |

The consequence is worth stating plainly: **every cost figure this project can
produce today has confidence `none`.** The basis is an allocation and the rate card
is synthetic, so two independent ceilings apply and the lower wins. That is not a
placeholder to be raised later by editing a field; it is raised by acquiring a real
rate card, and then by acquiring utilisation telemetry, and then by acquiring a bill.

## 9. Inputs

Twenty-four inputs, each with the question it answers, where it would come from, and
whether it exists today.

| Input | Question it answers | Source | Signal it would come from |
|---|---|---|---|
| `period.start` | When does the accounting period begin? | declared | none; the producer's own clock |
| `period.end` | When does it end, exclusively? | declared | none; the producer's own clock |
| `capacity.cpuCores` | How much processor capacity is there to allocate from? | declared | none |
| `capacity.memoryGibibytes` | How much memory is there to allocate from? | declared | none |
| `capacity.acceleratorDevices` | How many accelerator devices are there? | declared | none |
| `spec.resources.cpu` | How much processor capacity did this workload reserve per replica? | declared | the workload document |
| `spec.resources.memory` | How much memory did it reserve per replica? | declared | the workload document |
| `spec.resources.accelerator.count` | How many devices did it reserve per replica? | declared | the workload document |
| `deployment.replicas` | How many copies of that reservation existed? | declared | none |
| `cost.priceSourceId` | Which rate card, at which version and date? | declared | committed data |
| `usage.requests` | How many requests is this amount divided by? | measured | `inferops_inference_requests_total` |
| `usage.inputTokens` | How many input tokens did it process? | measured | `inferops_inference_tokens_total` |
| `usage.outputTokens` | How many output tokens did it produce? | measured | `inferops_inference_tokens_total` |
| `usage.cpuSeconds` | How much processor time did it actually consume? | unavailable | `inferops_process_cpu_seconds_total`, partially |
| `usage.memoryByteSeconds` | How much memory did it actually hold, over time? | unavailable | `inferops_process_resident_memory_bytes`, partially |
| `usage.acceleratorSeconds` | How much accelerator time did it consume? | unavailable | none |
| `usage.readySeconds` | For how much of the window could it answer at all? | derived | `inferops_model_ready`, partially |
| `identity.workloadId` | Which workload is this record about? | declared | `inferops.workload.id` |
| `identity.ownerId` | Who is accountable for it? | declared | `inferops.owner.id` |
| `identity.tenantId` | Whose activity does it attribute to? | declared | `inferops.tenant.id` |
| `identity.environment` | Is this a development host? | declared | `deployment.environment` |
| `identity.modelId` | Which model was the capacity reserved for? | declared | `inferops.model.id` |
| `identity.runtimeId` | Which serving runtime held it? | declared | `inferops.runtime.id` |
| `recordId` | Which cost record is this? | declared | `inferops.cost.record.id` |

Every signal named in the last column is compared against
[the telemetry catalog](../telemetry/telemetry-catalog.v1alpha1.json) by a test, so
an input cannot claim a source the catalog does not declare.

**No usage input is available today**, whatever its coverage says, because no
component in this repository emits a single signal. Coverage describes what the
catalog would supply, not what exists, and a test refuses any usage input that claims
otherwise.

## 10. Outputs

| Output | Formula | Unit |
|---|---|---|
| `reserved.cpuCoreHours` | cores × replicas × window hours | `cpu-core-hour` |
| `reserved.memoryGibibyteHours` | gibibytes × replicas × window hours | `memory-gibibyte-hour` |
| `reserved.acceleratorDeviceHours` | devices × replicas × window hours | `accelerator-device-hour` |
| `cost.amount` | each reserved quantity × its rate, summed | `currency` |
| `capacity.amount` | each allocatable quantity × its rate × window hours | `currency` |
| `unallocated.amount` | node capacity amount − sum of workload amounts | `currency` |
| `prerequisite.amount` | claimed gibibytes × window hours × storage rate | `currency` |
| `derived.shareOfNodeCapacity` | workload amount ÷ node capacity amount | `ratio` |
| `derived.costPerThousandRequests` | workload amount ÷ requests × 1,000 | `currency` |
| `derived.costPerMillionTokens` | workload amount ÷ tokens × 1,000,000 | `currency` |

Each is stated to six decimal places, rounded once, half-even. The last two are null
whenever their denominator is unavailable or below the declared minimum.

## 11. The record shape

A cost record carries its own audit trail: the window, the identity, the reservation,
the usage that was and was not available, the amount with its basis and rate card,
the derived unit costs with their denominators, the completeness of the inputs, and a
reference to this method.

One field is deliberately unable to reach a committed record. `identity.tenantId` is
classed `tenant-attributable` in the telemetry catalog, and that class has no
permitted placement in an evidence record: a committed record is public and permanent,
and a tenant list with a retention window of forever is not what anybody intended by
adding an attribution field. The field exists in the shape, is populated at runtime,
and is absent from every record in this repository — including the worked example. A
test derives the permission from the class rather than reading a flag, so the two
cannot disagree.

**This is not a contract.** No schema for it is published under
[`contracts/`](../../contracts/README.md), because no component produces or consumes
one, and the contract package adds a schema when the capability behind it exists
rather than in advance.

## 12. Rules

Twelve rules are enforced by a test; two are enforced by review alone and say so.

| Rule | Enforcement |
|---|---|
| `no-estimate-is-a-bill` | test |
| `an-estimate-and-an-allocation-are-never-summed` | test |
| `no-price-is-fetched-at-runtime` | test |
| `a-synthetic-rate-card-declares-its-class-in-its-own-contents` | test |
| `confidence-is-derived-not-asserted` | test |
| `an-unavailable-input-is-null-with-a-reason` | test |
| `unreserved-capacity-is-reported-not-spread` | test |
| `a-unit-cost-carries-its-denominator` | test |
| `money-is-decimal-never-binary-float` | test |
| `a-committed-record-carries-no-tenant-identifier` | test |
| `the-model-cache-is-a-prerequisite-cost` | test |
| `every-required-input-names-a-source-or-records-that-none-exists` | test |
| `no-cost-figure-is-published-from-v1` | **review** |
| `a-window-in-which-the-shape-changed-is-split` | **review** |

The first review-only rule deserves its reasoning in the open. A cost per thousand
requests is an hourly reservation divided by an hour of traffic, which means
publishing one publishes the traffic.
[The project boundaries](../architecture/project-boundaries.md) forbid V1 publishing
a throughput figure, so V1 may not publish a cost-per-request figure either. What is
published here is the method and a synthetic example; no figure for what running an
inference workload costs is published, and none can be, because none has been
measured.

## 13. What would have to exist before this produces anything

| Gap | What it blocks |
|---|---|
| No container or node resource metric, and no metrics server | The `estimated` basis and the `observed-utilisation-share` method |
| No accelerator metric, and no accelerator ever used | Any accelerator line above an allocation from a declaration |
| No collector reads anything | Every usage input, including the ones with full catalog coverage |

Two questions are **not decided** here and are not this record's to decide: which
provider rate cards a comparison against hosted capacity would use, and which
component computes a cost record and owns it. The second belongs with the ownership
question [ADR 0004](../architecture/decisions/ADR-0004-component-and-ownership-boundaries.md)
already leaves open, and answering it in a cost document would be exactly the kind of
leak this method is written to avoid.

## 14. Limitations

Twelve are recorded in the data. These are the ones that change how this document
should be read:

- **Nothing computes any of this.** No cost record has been produced, no invoice has
  been read, and every rule specifies behaviour for a producer that does not exist.
- **The only rate card is synthetic**, so every amount here is arithmetically correct
  and economically meaningless.
- **There is no utilisation source**, so the reachable basis is an allocation and the
  method cannot say whether any reserved capacity was used.
- **Node capacity is a declared input.** Nothing reads it from a cluster, so a record
  can be produced against a machine that does not exist.
- **The minimum denominators are arbitrary.** 100 requests and 10,000 tokens are
  declared, not derived.
- **Nothing prices egress, ingress, or load balancing.** The local cluster ships no
  ingress controller and no load balancer, which the ownership inventory already
  records as an open cost.

The worked example is in [worked-example.md](worked-example.md).
