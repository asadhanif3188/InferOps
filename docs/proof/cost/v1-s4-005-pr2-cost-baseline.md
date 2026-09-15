# V1-S4-005-PR2 — the V1 cost baseline, and how to read it

Date: 2026-09-15

Classification: the **use** in every record is **local real CPU** evidence, measured on
`docker-desktop` during the `V1-S4-004` scenario matrix and taken from its committed
samples by a tool, not typed in. Every **price** is from the **synthetic** rate card. So
every amount below has confidence `none`: the arithmetic and the measured quantities can
be checked, and the amount says nothing about what anything costs. **It is not a bill,
not an allocation, and no cost figure is published** (ADR 0007 D11).

Claim boundary: for one single-replica release serving one fixed prompt on one host, in
two repetitions of a declared experiment, this record states how much processor time and
memory the request path was measured using, what that use comes to at invented rates,
how the capacity it did not use is accounted for, and how far those figures can be
trusted. It does not state a price, a provider bill, a capacity figure, or anything about
another host, release, prompt, or load.

## The records

Two calculations, one per run, each covering the run's whole load span: the warm-up and
the three measured levels, 183 requests.

| | Run 1 | Run 2 |
|---|---|---|
| Window (UTC, half-open) | 16:17:26.077 to 16:22:54.831 | 16:24:23.840 to 16:29:51.656 |
| Window length | 328.754 s, 0.091321 h | 327.816 s, 0.091060 h |
| Requests, all successful | 183 | 183 |
| Input and output tokens | 6,405 and 3,111 | 6,405 and 3,111 |
| Processor seconds, API and runtime pods | 1952.1241704 | 1937.7294126 |
| Memory byte-seconds, API and runtime pods | 188050670049.28 | 189068573650.944 |
| **Estimated amount** | **0.021934** | **0.021775** |
| Hourly figure over the window | 0.240182 | 0.239127 |
| Cost per thousand requests | 0.119855, of 183 | 0.118988, of 183 |
| Cost per million tokens | null, `below-minimum-sample`: 9,516 tokens | null, `below-minimum-sample`: 9,516 tokens |
| Share of the node | 0.454390 | 0.452395 |
| Node capacity amount | 0.048270 | 0.048133 |
| Unallocated | 0.026336, share 0.545598 | 0.026358, share 0.547608 |
| Confidence | `none` | `none` |

Currency `USD`, from `synthetic-illustrative-v1`, version `1`, effective 2026-08-26, at
0.040000 per core-hour and 0.005000 per gibibyte-hour. Both records' lines close against
the node exactly, and each carries `hasMeasuredUtilisation: true`, the first committed
records in this repository that do.

The committed files are [the run 1 input](v1-s4-005-pr2-baseline-run-1.input.json) and
[result](v1-s4-005-pr2-baseline-run-1.result.json),
[the run 2 input](v1-s4-005-pr2-baseline-run-2.input.json) and
[result](v1-s4-005-pr2-baseline-run-2.result.json), and
[the derivation record](v1-s4-005-pr2-baseline-derivation.v1alpha1.json), which holds
every intermediate value below.

## The methodology

### What the use was taken from

[The `V1-S4-004` performance record](../serving/v1-s4-004-pr1-performance-record.v1alpha1.json),
named in every input by path and by the SHA-256 of its LF-normalized content. Its
evidence class is `local-real-cpu`. `tools/cost_baseline` refuses to read it unless it
regenerates byte for byte from its committed inputs, and unless five of its own checks
passed: every deployment available, the same pods throughout, no container restart,
counters reconciled with the raw records, and samples covering every phase.

| | |
|---|---|
| Provider and Kubernetes | `docker-desktop`, `v1.34.3`, one node |
| Node allocatable | 12 cores, `10188024Ki` (9.71605682373046875 GiB) |
| Samples | node cgroup v1, one `docker exec` read every few seconds |
| Model and runtime | `qwen3-1-7b-q8-0`, `llama-cpp-server` at the pinned digest, 6 threads, one slot |
| Release | chart `inferops-llm-0.3.0`, one API, one runtime, and one collector replica |

### How each value was taken (ADR 0014 D3)

| Value | Rule | Run 1 | Run 2 |
|---|---|---|---|
| Window | Opens on the last sample at or before the first phase starts, closes on the first sample at or after the last phase ends, placed by host instant | 99 samples, largest gap 3,877 ms | 96 samples, largest gap 3,795 ms |
| Processor seconds | Each pod's cgroup counter increase between the two bounding samples, API plus runtime; a counter that falls is null with `input-conflict` | no reset | no reset |
| Memory byte-seconds | Each pod's working set, trapezoidal between consecutive samples on host time, API plus runtime; nothing extrapolated | | |
| Requests and tokens | Every raw record of the run, each required to lie inside the window; tokens summed over successes | requests and output tokens reconciled with the collector's counters | the same |
| Accelerator seconds | Not applicable: no device is reserved | | |

Because the window's ends are samples, the processor increase and the memory integral
cover exactly the same interval, and neither borrows a reading from outside it. The
window therefore extends past the load span by 2,553 ms in run 1 and 4,167 ms in run 2,
during which no request was in flight.

**Identity** was observed, not declared: the workload, model, runtime, and environment
are the single values the collector's own series carried during the run. The owner is the
one thing declared, by the values file the experiment executed, whose digest the record
captured. **The reservation**, 1100m and 2281701376 bytes per replica, is the API's and
the runtime's requests summed, read from the environment the experiment captured. No
workload document declares that shape: it is the sum of two pods, and is valid only
because both ran one replica, which the tool requires.

### Allocation, idle, and shared cost

| Question | Treatment |
|---|---|
| Basis | `estimated`, the only one V1 calculates (ADR 0014 D1). No allocation is produced beside it |
| Allocation method | `observed-utilisation-share`: the workload is priced for what it was measured using |
| Which pods are the workload | The request path: the API and runtime pods |
| The release's collector | Measured, not listed, so on the unallocated line, under the method's rule that platform overhead is environment cost. That is a choice: the collector is Helm-owned and release-scoped (ADR 0004 D7), so a reader could count it as the workload's. Counting it would change neither run's amount by a thousandth |
| Idle capacity, and reservation left unused | On the unallocated line, never spread |
| The platform, other pods on the node, the control plane | On the unallocated line, never spread |
| Prerequisites | None listed |

**What the unallocated line holds**, in run 1, from the derivation record. Every row is
measured except idle, which is the node's allocatable capacity less its measured use.

| Part | Processor | Memory |
|---|---|---|
| The workload (priced on its record) | 1952.12 core-s, 49.5% | 175.14 GiB-s, 5.5% |
| The release's collector | 0.67 core-s, 0.02% | 6.85 GiB-s, 0.2% |
| The node outside the release: 12 other pods, the system, and the sampler | 172.32 core-s, 4.4% | 1566.04 GiB-s, 49.0% |
| Idle, or not in the node's working set | 1819.94 core-s, 46.1% | 1446.17 GiB-s, 45.3% |
| **Node allocatable over the window** | **3945.048 core-s** | **3194.19 GiB-s** |

Priced at the card, about 77% of the run 1 unallocated amount is idle processor capacity,
and about 84% is idle processor capacity and memory outside the node's working set
together; the rest is mostly memory in the working set of what else runs on the node. Run 2 divides the same way to
within half a percentage point.

### Excluded costs

Nothing below is in any amount, and none of it is on the unallocated line either, because
the node's capacity amount prices only processor and memory:

- the **model cache claim**: its size is not in the performance record, so no storage is
  priced and no prerequisite is listed;
- **the node's disk, images, and the virtual machine's overhead** outside the node's
  allocatable capacity;
- **network, the port-forward the load travelled over, and the load generator's host**;
- **the time before and between runs**: model loading, most of the idle baseline, and the
  settle intervals, which lie outside both windows. Run 1's window opens 1,307 ms before
  its load generator launched, and so holds the last 1,057 ms of the idle baseline;
  run 2's holds none of it.

## How to read the figures

**The hourly figure** is the amount divided by the window, 0.091 hours. It says the
request path accrued use at about 0.24 an hour at invented rates *while serving this
load*. It projects nothing: the release was busy for all but the window's first and last
few seconds and idle before and after it, and an hour of it would cost what an hour of
its load looked like, which nobody measured.

**The cost per thousand requests** is the amount divided by 183 requests. It is a
throughput figure in the units of a price, and it inherits everything
[the performance findings](../serving/v1-s4-004-pr2-performance-findings.md) bound that
throughput to: one slot, one fixed 35-token prompt, 17 output tokens, a runtime at its
6-core limit at every concurrency. It is quoted per thousand, not per request, because
six places would round one request's amount to three significant digits. It is not a price per
request, and a different prompt, output length, slot count, or host would change it by an
amount nobody here measured.

**The cost per million tokens is null.** 183 requests produced 9,516 tokens, below the
method's declared minimum of 10,000. The arithmetic would have given a number; the method
declines to publish one from fewer tokens than it declares enough.

**Why the amount is almost all processor.** Processor time is 98.9% of each amount: in
run 1 the request path averaged 5.94 cores, 5.93 of them the runtime's, and held about
0.53 GiB.

**Use exceeded the reservation.** The request path reserved 1.1 cores and was measured
using 5.94 on average: 0.542 measured core-hours against 0.100453 reserved in run 1, about
5.4 times. The runtime requests one core and is limited to six, and it ran at its limit.
The estimate prices the processor time used, not the processor time reserved. Memory went
the other way: 0.049 measured gibibyte-hours against
0.194056 reserved, so most of the memory reservation was left idle and sits on the
unallocated line. No reservation is priced here (ADR 0014 D1); it is carried in each
record in core- and gibibyte-hours, unpriced.

**The two runs agree.** The amounts and the costs per thousand requests differ by 0.7%,
and the hourly figures by 0.4%, because run 2's window was shorter. That is two
repetitions on one host, a statement about repeatability here and nothing about variance
anywhere else.

## Why this is not a published cost figure

ADR 0007 D11 publishes the method and a synthetic worked example, and no figure for what running
an inference workload costs. Its reason was that a cost per request publishes the
throughput it is divided by, which V1 then could not publish.

Two things make these records consistent with it. The divisor is already public:
[ADR 0013](../../architecture/decisions/ADR-0013-bounded-local-performance-observations.md)
allows a bounded traffic figure from a declared local experiment, and the 183 requests
and their window are in [the performance findings](../serving/v1-s4-004-pr2-performance-findings.md).
And the dividend prices nothing: every rate is invented, the synthetic card names this
baseline in its own scope, and confidence is derived as `none`, which the method defines
as economically meaningless. So no amount here says what running the workload costs; each
says what its measured use comes to at rates that describe no machine. That reading is
this record's, not a decision's, and a figure on any other card would need one.

## Confidence and uncertainty

**Confidence is `none`, derived and not assigned.** A record's confidence is the lowest
ceiling among the rules that hold for it. Two hold here: no invoice caps an estimate at
`medium`, and the synthetic card caps any record at `none`. The rules that would cap it at
`low` do not hold, because use was measured and the windows are complete, and neither does
the `none` rule for an unsplit change of reservation. So the card alone decides it. A
different card is capped by its own class as well: an amortised-hardware card, the kind a
local host would have, allows `low`, and only a provider list price or a negotiated price
could reach `medium`, which an estimate never exceeds.

What remains uncertain even about the measured use:

| Source | Size here | Direction |
|---|---|---|
| Window edges with no load in flight | 2,553 ms and 4,167 ms, 0.8% and 1.3% of the windows | The workload's use in them is near idle, so the hourly figure is a little lower than the load's own rate |
| Host and node clocks | The node clock ran 0.154 s longer than the host's over run 1 and 0.070 s shorter over run 2 | Under 0.05% of a window; the window is on host time, which the load was placed on |
| Sample read time | Up to 1,874 ms per read, placed at the read's midpoint | A counter read lands up to about a second from its instant; the gap is inside the window's edges |
| Working set | The kernel's accounting, including file-backed pages it charges to the pod; the runtime's memory-mapped model is counted only as far as the kernel charges it | The memory line prices what the kernel reported, not what the process allocated |
| cgroup processor counter | Every thread in the pod, including work done for no request | Right for pricing use, wrong for attributing it to a request |
| Background on the node | The node outside the release, 12 pods, the system, and the sampler: 0.52 cores on average in run 1, against 0.28 in the idle baseline | Not in the workload's figures; it competes for the same cores |
| Reservation read once | Captured before the experiment; same pod identities after, and no restart | A resize in place during the run would not be seen |

## Limitations

- **One host, one release, one prompt, two runs.** None of these figures is portable, and
  the throughput they divide by is the single-slot runtime's.
- **Every price is invented.** The amounts are structurally valid and economically
  meaningless.
- **The window is a load span, not an accounting hour.** A record of an hour on the hour
  would include idle time these do not, and a different amount.
- **The collector is left on the unallocated line by a choice, not a measurement of whose
  it is.** Listing it as part of the workload would add 0.67 core-s and 6.85 GiB-s to run
  1, under a thousandth of the amount.
- **The owner is declared, not observed.** The collector's series carry no owner label.
- **Input tokens are not reconciled** against any counter by the performance record;
  requests and output tokens are.
- **Capacity and the reservation are the experiment's captured declarations**, not
  readings of the samples.

## A dashboard or query hook

**None is added.** Nothing emits a cost record: the tool is run by hand and writes
files. The telemetry catalog defers `inferops.cost.record.id` and
`inferops_cost_records_total` for that reason, and the correlation queries and the
dashboard record defer `inferops_cost_records_total`. A panel or a
query would read a series no component produces, which describes an absent capability as
a quiet one, and inventing a metric to feed it is outside the telemetry boundary. The hook
stays deferred with the platform component that would compute a cost record, which is
still not selected (ADR 0007 D13).

## Reproducing it

```sh
python -m tools.cost_baseline verify --record-dir docs/proof/serving --record-prefix v1-s4-004-pr1- --dir docs/proof/cost --prefix v1-s4-005-pr2-
python -m tools.cost_calculation verify --input docs/proof/cost/v1-s4-005-pr2-baseline-run-1.input.json --result docs/proof/cost/v1-s4-005-pr2-baseline-run-1.result.json
python -m tools.cost_calculation verify --input docs/proof/cost/v1-s4-005-pr2-baseline-run-2.input.json --result docs/proof/cost/v1-s4-005-pr2-baseline-run-2.result.json
python -m pytest tests/cost/test_cost_baseline.py -q
```

The first regenerates all five files from the committed performance record; the other two
recalculate each result from its input alone. The suite recomputes every usage value by
integer sums over the committed sample lines, every published figure in `Decimal` from
rates written out by hand, and holds every six-place figure in this document to the
results.
