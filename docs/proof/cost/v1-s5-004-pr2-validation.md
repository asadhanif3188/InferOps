# V1-S5-004-PR2 validation — publishing the V1 cost and capacity method

Change: [the V1 cost and capacity method](../../cost/cost-capacity-method.md) with its
authoritative record beside it; an extension of
[`tests/testing/test_published_methods.py`](../../../tests/testing/test_published_methods.py)
that holds that record to the cost method, the claim and evidence register, the
committed workflow, and the committed results its figures are quoted from; and one
in-place correction. This record is what was run, what it found, and what none of it
supports.

**Evidence class.** Everything this change asserts about the repository is
`local-static`: files read, compared, formatted, linted, type-checked, and driven
through suites that contact nothing. **No cluster was contacted.** No cluster was
created or selected, no release was installed, no model was downloaded, no inference
request was sent, and no network read was made. Every measured quantity the method quotes
is read from a record made earlier — the `V1-S4-004` samples, as taken into the
`V1-S4-005-PR2` baseline — and a test reads it back from that record. **No claim in
[the register](../../testing/claim-evidence-matrix.v1alpha1.json) gains, loses, or moves
evidence, and no rule, basis, rate card, or figure is added to
[the cost method](../../cost/cost-method.v1alpha1.json).** The generated
[proof dashboard](../dashboard.md) is unchanged, because nothing it is generated from
changed.

**This is a documentation change.** No product behaviour was modified. `src/`,
`charts/`, `infra/`, `deploy/`, `scripts/`, `tools/`, `contracts/`, and `.github/` are
byte-for-byte unchanged, and so are the cost method's data and every record under
`docs/proof/cost/` and `docs/proof/serving/`. The only executable file this change
touches is a test.

## Part 1 — what the method is

The method walks eleven topics, the ones a cost and capacity method has to answer:
actual billing against estimated cost against allocated cost; the formula, units, and
precision; the price source, version, and date; workload and resource inputs and the
measurement window; allocation, idle, and shared cost; outputs and how they map to a cost
record; cost against the measured load and resource profile; confidence and uncertainty;
excluded costs; dashboard and query hooks; and capacity, with the questions V1 defers.

Every topic has two tables, as the security and observability methods do:

- **Implemented** — twelve items. Each names at least one test or gate **and** at least
  one committed record, and every certified claim it rests on. Between them they name 90
  pieces of evidence: 57 test functions, 12 gate references, 17 record references over
  seven distinct records, three code modules, and one configuration file. Ten are
  labelled `local-static`; two — the link to the measured run and the capacity
  statement — are `local-real-cpu`, because the claims they rest on are.
- **Not implemented** — seventeen items. Each names what carries it: a cost rule
  enforced by review alone, a basis V1 cannot reach, a limitation or open question of the
  cost method, an uncertified claim, the unemitted cost counter, or one of nine gaps the
  record declares — and a sentence saying what is not claimed.

The method opens with a table that keeps the three kinds of number in a cost record
apart by evidence class: measured use is `local-real-cpu`, every rate is `synthetic`,
every amount and every figure divided from one is `estimated`, and an invoice does not
exist. That table is the direct answer to the criterion that a cost estimate cannot be
mistaken for billing, and the rules behind it were already enforced.

**Where the line comes from.** The author does not decide which side an item sits on:

| Anchor | Decided by | Check |
|---|---|---|
| A cost rule | The cost method's `enforcement` field: `test` may be implemented, `review` may not | `test_no_cost_rule_sits_on_the_side_its_enforcement_denies` |
| A basis | The cost method's `v1Reachable` field | `test_no_basis_sits_on_the_side_its_reachability_denies` |
| A limitation or open question | Always a statement of what is not done, so never implemented | `test_every_cost_limitation_and_open_question_is_carried_as_a_gap` |
| A signal | The telemetry catalog's `emission` field | `test_no_signal_sits_on_the_side_its_emission_denies`, now over the cost method too |
| A claim | The register's status: implemented only on `certified`, a gap never on it | the existing claim checks |

And nothing is left out: all nineteen cost rules, all three bases, all fourteen cost
limitations, and both open questions appear. The two review-only rules,
`no-cost-figure-is-published-from-v1` and `a-window-in-which-the-shape-changed-is-split`,
sit on the not-implemented side, which is the only honest place for a rule nothing
tests.

**Figures are read, not typed.** The record declares 21 figures, each with the committed
file and JSON pointer it came from and how the source's own convention is spelled in
prose (as written, a grouped integer, thousandths, or per-mille as a percentage). The
suite reads every one back, requires every one to appear in the document, and refuses any
six-place figure in the document that the record does not declare.

## Part 2 — what writing it found

**One statement had stopped being true.** [The cost calculation](../../cost/cost-calculation.md)'s
limits began "Every figure is synthetic". That was true of the two fixtures it was
written about, and stopped being true of the tool when `V1-S4-005-PR2` committed two
records whose use was measured on a real host. What is synthetic is every price, and so
every amount. The line is corrected in place with the date, and the phrase joins the
suite's retired sentences, now searched in six cost documents as well as the twenty the
security and observability methods govern.

**A sweep for other stale cost statements found none.** Before claiming that, the whole
repository outside `docs/proof/` and the changelog was searched for phrasings of "no
usage was measured", "every record is synthetic", "no cost record has been calculated",
and "typed in by hand". Every hit either is still true, describes a synthetic fixture, or
already carries a dated update, as ADR 0014's context, D3, and evidence sections and
ADR 0007's notes do.

**The guard found two omissions in the first draft of the record** before anything was
committed: a gap sentence ("Neither the single slot nor the processor limit is claimed")
that denied nothing the denial vocabulary recognises, and the cost method's
`the-example-is-not-a-measurement` limitation, which no item carried. Both are fixed.

**Its own failure modes were exercised.** A scratch script, not committed, applied
eighteen faults to the in-memory record and document one at a time and called the check
that should refuse each: a review-only rule moved to implemented, a tested rule moved to
a gap, a rule, a basis, and an open question dropped, the `actual` basis marked
implemented, a limitation put on an implemented item, a figure typed one digit off, a
figure read from the other run, the cost counter marked implemented, an implemented item
resting on the deferred capacity claim, a gap resting on a certified one, an estimate
labelled `local-real-cpu`, the deferred capacity claim dropped, an unbacked six-place
figure added to the prose, a declared figure removed from it, a stray rule named in the
wrong section, and a section that stopped naming its limitation. All eighteen were
refused.

## Part 3 — what this change leaves open

Recorded rather than fixed, because each belongs to a different boundary than this one:

- **No capacity question is answered.** The method lists the ones V1 defers — sustained
  and open-arrival load, slots, threads, processor, replicas, accelerators, prompt mix,
  provider pricing, and node sizing — and the portable capacity claim stays `deferred`.
  Answering any of them needs a new, authorized experiment.
- **No cost figure is published, and that rule is enforced by review alone.** The method
  records it as not implemented rather than pretending a test covers it.
- **No dashboard or query hook is added.** Nothing emits a cost record, so a hook would
  read a series nothing produces. The hook is the deferral each telemetry record already
  states, and the method links it.
- **No cost record contract is published.** The record shape stays part of the method, as
  ADR 0007 D10 decided.
- **The collector's place on the unallocated line** remains the baseline's stated choice
  rather than a decision; this method quotes it and does not decide it.
- **Nothing from the next story is pulled forward.** No runbook, release, or tag work is
  here.

## Part 4 — checks run

Run from Git Bash on one Windows host, against the working tree with every change
staged, so that the link suite collects the new record.

| Command | Result |
|---|---|
| `uv run --locked python -m pytest tests/testing/test_published_methods.py -q` | 430 passed |
| `uv run --locked python -m pytest tests/cost tests/testing tests/security tests/telemetry -q` | 6917 passed |
| `uv run --locked python -m pytest -q` | 12592 passed, 33 skipped, 14 deselected, in 10 min 17 s. The skips are the existing ones that need a pinned image, a tool, or a host capability absent here; none is in a suite this change touches |
| `uv run --locked python -m tools.cost_baseline verify --record-dir docs/proof/serving --record-prefix v1-s4-004-pr1- --dir docs/proof/cost --prefix v1-s4-005-pr2-` | `ok`: five committed baseline files regenerate |
| `uv run --locked python -m tools.cost_calculation verify` for each baseline run's input and result | `ok`, twice |
| `uv run --locked ruff format --check .` | 471 files already formatted, after `ruff format` reformatted the extended suite once |
| `uv run --locked ruff check .` | All checks passed |
| `uv run --locked python -m mypy` | Success: no issues found in 261 source files |
| `git diff --check` | clean |

Not run: anything that needs a cluster, a model, or the network, because nothing here
touches one.

**Private-information inspection.** The full diff was read for planning material,
prompts, host paths, host names, user names, credentials, and tenant identifiers.
Nothing was found.

## Part 5 — acceptance status

| Criterion | Status in this change |
|---|---|
| Implemented controls and deferred risks are separate | **Met** for cost, and enforced: the side of the line is derived from each rule's enforcement and each basis's reachability, not chosen. The security and observability halves were met by `V1-S5-004-PR1` |
| Telemetry semantics and dashboard interpretation are clear | Met by `V1-S5-004-PR1`; this change adds only why there is no cost panel |
| Prompt/response handling is documented | Met by `V1-S5-004-PR1`; a cost record carries no prompt, and no committed one a tenant |
| Cost estimates cannot be mistaken for billing | **Met**: the three bases and the three evidence classes are kept apart in the method's first table and first section, and every rule behind it is tested; that no figure is published is enforced by review alone, and the method says so |
| All methods link to tests/evidence | **Met** for the cost and capacity method: every implemented item names a resolving test or gate and a committed record, every section links its records, and every quoted figure reads back from its file |

With this change the parent story, `V1-S5-004`, has both of its PRs. Whether a reader
finds any of it clear is a review question no test answers.

## What none of this supports

That anything costs what an amount here says, or that InferOps, the chart, the model, or
the runtime has any stated capacity. A method summarises records other documents own; a
reference resolving says the named thing exists and not that it is a strong check.
Nothing here is an outside assessment.
