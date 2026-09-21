# ADR 0013: Bounded local performance observations may be published; portable capacity may not

| Field | Value |
|---|---|
| Status | **Accepted** |
| Date proposed | 2026-09-14 |
| Date accepted | 2026-09-14 |
| Decision owner | [`repository-maintainer`](../../governance/decision-authority.md), assigned retrospectively on 2026-09-21 by [ADR 0015](ADR-0015-v1-decision-ownership-and-sign-off-authority.md) |
| Supersedes | None |
| Amends | [ADR 0004](ADR-0004-component-and-ownership-boundaries.md) D6, the third boundary rule in [the project boundaries](../project-boundaries.md), and the context of [ADR 0005](ADR-0005-test-ci-and-certification-strategy.md) that relies on it |
| Superseded by | None |

> [!IMPORTANT]
> Until this record, V1's rule was that it publishes **no** latency, throughput,
> capacity, or benchmark figure. ADR 0004 D6 said so, the project boundaries said so,
> and ADR 0005 built the deferred `capacity` lane on top of it. The few figures earlier
> records did carry, such as the runtime feasibility trial's decode rate, were each
> labelled as not a benchmark and not a claim. The rule was written when that trial,
> one sequential request on one CPU host, was the only such measurement this project
> held.
>
> This record narrows the rule and keeps its purpose. A figure measured in a
> **declared, executed, local experiment** may be published when the record carrying
> it names the provider, host, model, runtime, release configuration, workload
> profile, versions, and evidence class. It may describe what that one setup did,
> including where it degraded. It may **not** be read, restated, or generalized as a
> portable capacity figure, a production SLO, universal performance, or a benchmark
> of Kubernetes, the model, the runtime, or any provider.
>
> **What stays deferred is unchanged.** The claim
> `sustained-throughput-and-capacity-under-load` stays a recorded gap, the `capacity`
> lane and the `capacity-and-load` layer stay deferred and unrun, and ADR 0005's rule
> that publishing a *capacity* figure means deleting a deferral in three places still
> holds. ADR 0007 D11 is untouched: no real-provider cost figure is published.

## Decision status

| ID | Decision | Status | What supports it |
|---|---|---|---|
| D1 | A bounded observation from a declared local experiment may be published | **Accepted** | Review, and two loaders that refuse a record not carrying its boundary (D3) |
| D2 | Portable capacity, production SLOs, universal performance, benchmarks, and cross-provider readings stay refused | **Accepted** as a rule | The records' boundary flags and sentence are machine-checked by the two loaders; whether a figure is read as portable is **review only**, everywhere |
| D3 | Such an observation comes from a committed descriptor, an authorized run on an explicitly selected and verified provider, and a record that carries its own boundary | **Accepted** | `tools.llm_load` and `tools.performance_scenarios` refuse a profile, raw set, descriptor, or record whose benchmark or capacity flags are not false or whose boundary sentence is missing |
| D4 | A saturation or degradation statement names its experiment boundary, and no tool makes one | **Accepted** as a rule | The performance record carries `saturationJudged: false`; a statement about degradation belongs to an analysis document, reviewed |
| D5 | Nothing earlier is reinterpreted | **Accepted** | Review. The runtime feasibility decode-rate figure stays labelled not a benchmark |

## Context

The rule this record amends did useful work. It stopped a number measured once, on one
host, against a runtime this project did not write, from being quoted as what the
runtime or the platform "does". Every serving record since has carried that caution.

It also stopped a question the platform exists to help answer. An operator of a
single-model serving path needs to know, for the setup in front of them, what latency
a request sees at a given concurrency, how much CPU the serving tier burns, what the
collector counts while it happens, and where adding callers stops adding answers.
Those are observations of one environment, not claims about all of them. A rule that
forbids publishing any figure makes that operational evidence unpublishable, and so
it is either not gathered or gathered and not shown.

By `V1-S4-003` the tooling to bound such a figure existed: a load profile whose
ceilings are kept in code, a raw record set whose accounting the reader refuses to
summarize if it does not balance, and a boundary sentence the loader refuses to see
dropped. What did not exist was a decision that let its output be published.

## Decision criteria

| Criterion | Why it matters |
|---|---|
| A published figure must name the setup it describes | A latency without its provider, host, model, runtime, and profile is a benchmark by omission |
| The refusal must survive the amendment | The boundary exists to stop portable claims, and a narrowing that loses that is a repeal |
| Enforcement must be stated honestly | The loaders can refuse a record; nothing can refuse a sentence in a README |
| Nothing already deferred may move silently | ADR 0005 deliberately made publishing capacity cost three deletions |

## D1 — A bounded observation from a declared local experiment may be published

**Accepted.** A record, and a document quoting it, may publish for one executed
experiment:

- request and error counts, and outcomes by kind;
- P50, P95, and P99 latency, with the percentile method named;
- observed request and output-token rates over that experiment's own windows;
- CPU and memory observations of that experiment's tiers, with how they were read;
- token counts;
- the point at which that exact setup showed degradation, with the evidence for it.

Every such publication names, beside the figure or in the record it cites: the
provider, the host, the model and revision, the runtime and its pinned image, the
release configuration that shapes the measurement, the workload profile and its
digest, the versions of what ran, and the evidence class.

> **Implementation update, 2026-09-16 (`V1-S4-006-PR1`).** The list above is written
> in terms of load and resources, because those were what existed when it was
> accepted. A failure experiment publishes two further kinds of figure from one
> executed run, and both are recorded here as falling under D1 rather than as a new
> permission: **how long a lost workload took to be replaced and to serve again**,
> and **what callers saw before, during, and after that loss** — request counts by
> outcome, and latency percentiles either side. The sprint plan's Sprint 4
> amendment already listed "model-load/recovery observations" and "before/during/
> after failure impact" among the permitted evidence for this exact environment;
> this note records that the tooling now produces them and that they carry the same
> naming requirement as every other figure under D1. D2 is unchanged, and the
> record that publishes them carries `availabilityClaim: false` beside the two
> flags D3 requires.

## D2 — What stays refused

**Accepted as a rule.** None of the following may be published, whatever an
experiment measured:

- a **portable capacity** figure, or any statement of how many requests, users, or
  tokens "InferOps", "the chart", or "the model" supports;
- a **production SLO**, availability figure, or error budget;
- **universal performance**, or a comparison presented as holding beyond the recorded
  setup;
- a **benchmark** of Kubernetes, the model, the runtime, or any provider;
- a reading of one provider's figures as another's. `docker-desktop` evidence says
  nothing about `kind`, and nothing about a host other than the one recorded.

`sustained-throughput-and-capacity-under-load` stays deferred. The `capacity` lane
stays `deferred`, the `capacity-and-load` layer stays `deferred` and unpublishable,
and their status and deferral are unchanged; the strategy data carries a pointer note to
this record and nothing else.

**Enforcement.** The two tools in D3 refuse a record whose `productionBenchmark` or
`portableCapacityClaim` is not `false` or whose boundary sentence is missing. That is
all they check. Whether a figure is presented as portable is not machine-checked
anywhere, in a record's surrounding prose or in any other document; a reviewer is the
only thing that stops it. That gap is stated here rather than implied closed.

## D3 — Where a publishable observation comes from

**Accepted.** A figure qualifies under D1 only if it was produced by:

1. a **committed descriptor** that fixes what was sent and what was read — for load,
   [`llm-load-profile.v1.json`](../../../deploy/serving/load/llm-load-profile.v1.json);
   for a scenario matrix with resource and collector readings,
   [`performance-scenarios.v1.json`](../../../deploy/serving/experiments/performance-scenarios.v1.json);
2. a run **authorized by the host owner**, on a provider selected explicitly and
   verified by `inferops::resolve_target` before any mutation
   ([ADR 0011](ADR-0011-external-local-cluster-provider-contract.md));
3. a **record carrying its own boundary**: `productionBenchmark: false`,
   `portableCapacityClaim: false`, and the boundary sentence, which
   `tools.llm_load` and `tools.performance_scenarios` refuse to read or write
   without.

Synthetic, mock, and rehearsal output never qualifies, however it is labelled.

> **Implementation update, 2026-09-16 (`V1-S4-006-PR1`).** There is now a third
> committed descriptor of the kind clause 1 requires —
> [`inference-pod-recovery.v1.json`](../../../deploy/serving/experiments/inference-pod-recovery.v1.json),
> for one inference pod lost under load — and a third tool that refuses a record
> without its boundary, `tools.inference_pod_recovery`. Neither the clause nor the
> enforcement it describes has changed: the two named above are examples of the kind,
> not a closed list, and the new tool applies the same three checks plus one more,
> refusing a record whose `availabilityClaim` is not `false`. The gap D2 states
> remains exactly as stated: whether a figure is *presented* as an availability
> figure is not machine-checked anywhere, and a reviewer is the only thing that
> stops it.

> **Implementation update, 2026-09-16 (`V1-S4-007-PR1`).** A fourth committed
> descriptor of the kind clause 1 requires —
> [`unready-model-recovery.v1.json`](../../../deploy/serving/experiments/unready-model-recovery.v1.json),
> for one release whose model does not become ready — and a fourth tool that refuses a
> record without its boundary, `tools.unready_model_recovery`. Nothing in the clause
> changes. The new tool applies the same three checks and the `availabilityClaim` one
> the third added, plus a fifth of its own: its boundary sentence must also refuse
> **recovery-time objective**, because a record that publishes an interval from a fix
> to a served completion is the shape somebody reads as one. The gap D2 states remains
> exactly as stated.

## D4 — Saturation is stated by an analysis, and bounded

**Accepted as a rule.** The tools place figures side by side; they do not judge them.
The performance record carries `saturationJudged: false`. A statement that a setup
degraded at some level is made in an analysis document that names the experiment
boundary and cites the record, and it is reviewed like any other claim.

### How this leaves ADR 0007 intact

[ADR 0007](ADR-0007-inference-cost-method.md) reasoned that a cost per thousand
requests divides an hourly reservation by an hour of traffic, so publishing one would
publish the traffic. This record now permits publishing a bounded traffic rate. It does
not permit a real-provider cost figure: ADR 0007 D11 is a decision in its own right, not
only a consequence of the rule narrowed here, and it stands.

## D5 — Nothing earlier is reinterpreted

**Accepted.** The decode-rate figure in
[the runtime feasibility record](../../proof/serving/v1-s0-003-pr2-runtime-feasibility.md)
was published as not a benchmark and stays that. Earlier records that avoided a figure
are not edited to add one.

## Consequences

- ADR 0004 D6 and the third project-boundary rule carry a pointer to this record, and
  their prohibition is read as narrowed by D1 and kept by D2.
- The notes in the test strategy that say V1 may publish no latency or throughput
  figure point here. The `capacity` rows themselves do not change.
- A performance record may be committed under `docs/proof/`. Its figures are quotable
  under D1, with the setup named.
- A reviewer now has a second question for any figure: not only "is it labelled", but
  "does the sentence around it generalize".

## Compatibility impact

Compatible. No schema, contract, error code, chart value, or command changes because
of this record. The `capacity` lane, the `capacity-and-load` layer, and every claim
row keep their status.

## Security considerations

A performance record names a host's processor count, memory, kernel release, and
container engine version. It must not name a host name, user, filesystem path, or
network address. `tools.performance_scenarios` refuses any record input carrying a
value shaped like a Windows drive path, a user or home directory, or an IPv4 address
other than loopback. It does not recognize host names or IPv6 addresses; those are left
to review.
Counts of unrelated workloads may be kept; their names may not.

## Evidence

The change validation, and the first record produced under this decision, is
[the V1-S4-004-PR1 validation record](../../proof/serving/v1-s4-004-pr1-validation.md).

## Risks, assumptions, and open questions

- **Prose is the weak point.** D2's flags are enforced on records and not on sentences. A
  portable claim written into a document passes every test in this repository.
- **One setup can still look general.** A single-replica release on one local
  host is what V1 has. Figures from it are easy to repeat without their boundary,
  and the boundary sentence travels only as far as the reader keeps it.
- **Assumed:** that the analysis documents citing a record will quote its setup. If
  that proves not to hold in review, a document check can be added; none exists.
