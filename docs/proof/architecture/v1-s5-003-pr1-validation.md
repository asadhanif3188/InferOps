# V1-S5-003-PR1 validation — reconciling the implemented architecture and the ADRs

Change: the architecture records reconciled against the repository that was
actually built; [ADR 0015](../../architecture/decisions/ADR-0015-v1-decision-ownership-and-sign-off-authority.md),
which decides who owns an accepted V1 decision, who may amend one, who signs off a
claim, and who approves a release; the `Decision owner` field of all fourteen
earlier records filled in; [ADR 0008](../../architecture/decisions/ADR-0008-v1-security-baseline.md)
`D13` moved from **not decided** to decided; four resources added to the ownership
inventory; and a suite that holds the ownership half of all of it to the repository.
This record is what was run, what it found, and what none of it supports.

**Evidence class.** Everything asserted here is `local-static`: files read,
compared, formatted, linted, type-checked, and driven through a test suite that
contacts nothing. **No cluster was contacted.** No cluster was created or selected,
no `terraform apply` ran, no Helm release was installed, no model was downloaded,
and no inference request was sent. Every runtime fact this change writes into a
document is quoted from a record made earlier and names that record. **No claim in
[the register](../../testing/claim-evidence-matrix.v1alpha1.json) gains, loses, or
moves evidence**, and the generated [proof dashboard](../dashboard.md) is
byte-identical before and after.

**This is a decision, architecture, and documentation change.** No product
behaviour was modified. `src/`, `charts/`, `infra/`, `deploy/`, `scripts/`, and
every tool under `tools/` are byte-for-byte unchanged; the only executable file this
change adds is a test.

## Part 1 — what the reconciliation found

The architecture records were read against the tree. Nine published statements were
false, two capability classes were undrawn, and four committed artifacts were acting
with no ownership row. None of it was caught by a test, because none of it is the kind of
thing the existing tests read: they compare data to data and data to a table's first
column, and a paragraph beside the table drifts freely.
[The ownership document](../../architecture/resource-ownership.md) says exactly that
about itself, and this is what it looks like when it happens.

### Statements that were true when written and had become false

| Where | What it said | What is true | Since |
|---|---|---|---|
| `system-architecture.md`, "How these diagrams are maintained" | The repository has "no continuous-integration lane to run one in", as half the argument for ASCII diagrams | `.github/workflows/checks.yml` is committed and runs eleven gates, one of which reads every committed document | ADR 0012, 2026-09-12 |
| `system-architecture.md` §5 collector box | "Dashboard definition: a repository artifact, never imported" | One throwaway Grafana imported it once for the `V1-S4-002-PR2` validation and was removed. The machine-checked inventory beside the diagram already said so | 2026-09-13 |
| `system-architecture.md` §5 collector box | Alert definitions: "Nothing has loaded them" | The pinned collector's own `promtool` loads both rendered files. Nothing *routes* one, which is the half that survived | 2026-09-17 |
| `system-architecture.md` §3 | "Every request in the one executed trial was single and sequential; the runtime reported four slots and one was ever used" | The committed performance scenarios drive this flow at concurrency 1, 2, and 4, and deferred requests were counted | `V1-S4-004`, 2026-09-14 |
| `system-architecture.md` §7, now §9 | Components "have served a request through this architecture — once" | Several hundred requests across declared load, performance, failure, and clean-clone experiments | `V1-S4-003`, 2026-09-13 |
| `architecture/README.md` status line | "seven decisions accepted in part, one accepted with a recorded exception, two accepted, and one accepted and later amended" — eleven records | Fifteen records: nine accepted in part, four accepted, one with a recorded exception, one amended | ADR 0011, 2026-09-11 |
| `architecture/README.md`, ADR 0005 paragraph | "there is no workflow file in this repository" | One exists. The same document's own ADR 0012 row said the opposite, four rows above | ADR 0012, 2026-09-12 |
| `architecture/README.md`, ADR 0008 paragraph | "No secret scanner has been run and recorded", and neither the image scanner nor the dependency auditor "runs continuously, because no continuous-integration service is selected" | All three are gates in the committed workflow | `V1-S4-001`, 2026-09-13 |
| `testing/test-inventory.md` ×2 | "no continuous-integration service is configured" and "There is no workflow file" | The same | ADR 0012, 2026-09-12 |

Every one of these is corrected **in place with the correction stated**, not quietly
edited. The repository's convention is that a document which used to be wrong says
so, because a reader who cannot see the correction cannot calibrate the rest.

The `docker-desktop`-only, one-host, CPU, one-replica, capacity-gate-refused
qualifiers attached to those sentences were checked and are **all still correct**.
More executions did not widen any claim: they are the same one setup, measured more
times, and the corrected sentences say so.

### Capabilities that existed and were drawn nowhere

A keyword scan of `system-architecture.md` before this change returned zero hits for
`tools/`, `ci_gates`, `clean_clone`, `proof_dashboard`, `llm_load`, `performance`,
`cost_`, `recovery`, `rollback`, `pod_restart`, `scaffold`, `.github`, `workflow`,
and `continuous integration`.

Two classes were promoted to diagrams, as new sections **6. Failure and recovery
flow** and **7. Proof and claim-evidence flow**:

- **Failure and recovery.** Three shapes — a serving pod lost under load, a model
  that never becomes ready, and an upgrade that has to roll back — each built,
  executed against a real release on the reference provider, and represented in no
  diagram. The section draws what recovers (Kubernetes, not InferOps), why the API
  survives the runtime (the deployment split §2 already argued for), and what is
  refused: no availability figure, no recovery-time objective, no error budget, and
  no alert that reached anybody.
- **Proof and claim-evidence.** §5 drew the evidence arrow as far as `docs/proof/`
  and stopped. The derived second stage — register, `tools.proof_dashboard`, the
  generated page, the test that regenerates and compares it — was undrawn, and the
  generated page directly contradicted the `evidence-records` inventory row it was
  nominally covered by.

The remaining undrawn tooling — scaffolding, model lifecycle, certification drivers,
cost, load generation — is named in §9 and the related-records table rather than
given diagrams. Drawing thirty tool packages would make the document longer and no
truer; what mattered was the two capability *classes* a reviewer would ask about.

### Ownership rows for artifacts that were already acting

| Row added | Owner | Why it was a gap |
|---|---|---|
| `continuous-integration-workflow` | `repository` | The only committed artifact here that runs anything, acting since 2026-09-13 with no row |
| `claim-and-evidence-register` | `repository` | The authoritative statement of what this project claims. Four other machine-readable registers had rows; this one did not |
| `proof-dashboard-page` | `repository` | **A contradiction, not just a gap.** It sits under `docs/proof/`, so `evidence-records` nominally covered it — and that row says a record "is never regenerated by rerunning the thing it describes", while the page says it is regenerated on every change and must not be hand-edited. One row could not carry both rules, so it got its own and `evidence-records` now names the exception |
| `model-seed-container-image` | `contributor-host` | The second image this project builds locally. `platform-api-container-image` was the only image row |

Rows deliberately **not** added, after review: the alert rule files and the contract
fixtures (already inside existing rows), the `helm test` hook and the multi-replica
driver Job (excluded on purpose by the ownership document), and the committed
experiment descriptors, golden renders, and Dockerfiles (a real gap, and a larger
design question about whether repository source files belong in a *resource*
inventory at all — recorded as follow-up rather than decided in passing).

### What was checked and found correct

- **Deployment rendering is still unbuilt.** Nothing in `src/` or `tools/` turns a
  validated contract document into chart values; a values file is written by hand.
  Every statement to that effect was verified and kept.
- **Terraform and Helm ownership.** Both halves are already compared to the
  inventory in both directions by their own suites, and both passed unchanged.
- **The five trust boundaries.** Unchanged, and deliberately: the security baseline
  compares its boundary rows to this document **verbatim**, and the boundary table's
  `whatCrosses` and `enforcedToday` cells were left byte-for-byte alone.
- **Future projects as boundaries.** `project-boundaries.md` needed one
  clarification — a cost record *shape* now exists while no cost *contract* does —
  and no queued work is depicted as implemented anywhere.

## Part 2 — decision ownership and sign-off authority

Fourteen records carried the identical metadata row
`Decision owner: Unassigned; no public maintainer roster exists yet`. Four other
documents named the same gap, each pointing at the others. ADR 0008 `D13` left *who
signs off a control and its evidence* undecided, with "Nothing. There is no public
maintainer roster to name" in the column that elsewhere holds a test.

**The stated blocker was a roster of people. The actual blocker was a decision about
a role, and nobody had made it.** ADR 0015 makes it.

| | Before | After |
|---|---|---|
| Records with an owner | 0 of 14 | 15 of 15 |
| Records whose owner is a declared role | 0 | 15 |
| Kinds of authority named | 0 | 4, separately |
| ADR 0008 `D13` | Not decided | Decided, 2026-09-21 |
| ADR risk rows recording the gap | 3 open (`ADR 0001 R7`, `ADR 0004 R8`, `ADR 0011 R8`) | 3 resolved, with what resolved them named |
| Machine-checked | Nothing read the field | 181 checks in one suite |

**The owner is a role, `repository-maintainer`: anyone able to merge into `main`.**
No person is named and none will be; ADR 0015 `D7` makes that a decision rather than
a pending item, and the reasoning is in the record.

**Four authorities are named separately** — decision ownership, acceptance and
amendment, claim/evidence sign-off, and release approval — and all four are held by
the same role today because the role has one holder. Distributing four authorities
across one person and calling it separation of duties would be the invented
structure the record refuses. Naming them apart now means splitting them later is an
amendment to a list that exists.

### The property this record most wants read

**Fourteen of the fifteen owners are assigned retrospectively, and the data says so
in a field.**

A change that gives fourteen records an owner on one day looks, in a diff, exactly
like a change that reviewed fourteen records on one day. It was not. Nobody re-read
those records' historical evidence, and the difference is not recoverable from the
row. So it is recorded beside the row, as `basis`, restricted to two values, required
by a test, and required to appear in the record's own metadata text as well —
`test_a_retrospective_assignment_says_so_in_the_record` fails if the register and the
record disagree about it in either direction.

### What deciding this did not do

Stated here because a governance record is the easiest kind to read as more than it
is, and because every authority in the register commits its own version of this list:

- **No claim, certification level, or evidence class moved.** The generated proof
  dashboard is byte-identical before and after; a status is still derived from a
  record, and merging a change that sets one does not strengthen it.
- **No control became enforced.** ADR 0008's nine controls with no verification
  still have none, and a control's status is still recomputed from the committed
  derivation table rather than asserted by an owner.
- **No external review happened.** Sign-off under this model is internal by
  construction. No outside party has reviewed a decision, a claim, or a release
  candidate in this repository, and no document here may describe it as more.
- **Author and approver are the same person.** The role has one holder, so there is
  no separation of duties for any change, including this one. It is `R1` in ADR
  0015's own risk register, open.

## Tests and checks run

Run from Git Bash on Windows, through `uv run --locked` so every version matches the
committed lockfile.

| Command | Result |
|---|---|
| `uv run --locked ruff check .` | All checks passed! |
| `uv run --locked ruff format --check .` | 466 files already formatted |
| `uv run --locked python -m mypy` | Success: no issues found in 260 source files |
| `uv run --locked python -m pytest -q` | see the six runs below |
| `uv run --locked python -m pytest tests/architecture -q` | 2663 passed, 3 skipped — before the new suite was added |
| `uv run --locked python -m pytest tests/architecture/test_decision_authority.py -q` | 181 passed |
| `uv run --locked python -m tools.proof_dashboard --check` | OK  dashboard.md is what the register produces |

### The default lane, run six times

All six are published, rather than the best of them, because two of them failed.

| # | When | Another pytest running? | Result |
|---:|---|---|---|
| 1 | Before any change on this branch, as a baseline | no | 12 134 passed, 30 skipped, 14 deselected |
| 2 | After the first commit | no | 12 137 passed, 30 skipped, 14 deselected |
| 3 | After the review fixes | no | 12 146 passed, 30 skipped, 14 deselected |
| 4 | Against the exact committed tree | **yes** — run 3 was still finishing | **1 failed**, 12 145 passed |
| 5 | Confirming run | **yes** — a `tests/testing tests/security` run overlapped it | **1 failed**, 12 145 passed |
| 6 | Isolated, with nothing else running | no | 12 146 passed, 30 skipped, 14 deselected |

Both failures were the same test,
`tests/serving/test_performance_scenarios.py::test_the_collector_is_asked_by_get_without_parameters_and_by_post_with_them`,
and both happened in the two runs that overlapped a second pytest process on this
host. Every run without a competing process passed, including run 6, which was
executed alone specifically to settle it.

**The cause is the harness this validation was run through, not the repository and
not this change.** That test binds a real `ThreadingHTTPServer` on an ephemeral
loopback port and makes two HTTP requests against it; two full suites competing for
loopback sockets on one Windows host is a condition it was never written to survive.
The module is not touched by this branch — the only files this branch changes under
that subject are two ADR documents' metadata rows — and it passed three times in
isolation immediately after the first failure.

Two things this record deliberately does **not** say. It does not call the test
*flaky*: a test that fails under a condition that can be named and reproduced is not
random, and the first draft of this section called it a flake before the isolated run
had been done. And it does not propose a fix — the test belongs to the suite that
owns it, diagnosing loopback contention is not an architecture reconciliation's
work, and no change is made to it here.

`ruff format --check` and `mypy` each failed once first, on the new test module
only: one file needed reformatting, and `OWNER_ROW.search(...).group(...)` was
flagged because `re.search` may return `None`. Both were fixed in the new module and
nothing else was touched.

### What the new suite establishes

`tests/architecture/test_decision_authority.py`, 181 checks, `architecture` marker,
`default-checks` lane:

- every record under `docs/architecture/decisions/` has exactly one register entry,
  and every entry names a record that exists — **both directions**, so a new record
  cannot arrive unowned and an entry cannot outlive its record;
- every owner is a declared role, and no entry carries `unassigned`, `none`, `tbd`,
  `todo`, `pending`, or `undecided`;
- each record's own `Decision owner` row publishes exactly the role the register
  assigns it, and a retrospective assignment says so in that row;
- each of the four authorities declares a non-empty `doesNotEstablish` list, and all
  four required authority identifiers are present;
- ADR 0008's `D13` row no longer says "not decided", and the committed open question
  behind it names ADR 0015 and the authority that answers it;
- no decision record and none of fifteen governance documents still asserts the
  retired vocabulary. Two files may quote it — ADR 0015 and the governance document,
  which cannot say what changed without reproducing the sentence they retire — and
  only inside an inline code span, so a bare assertion in those two still fails.
  Everywhere else the phrase is refused outright, backticks included; a code span is
  typesetting, not a quotation mark. Both halves were mutation-tested: a
  backtick-wrapped assertion appended to `docs/releases.md` failed the check, and a
  bare one appended to the governance document failed two.

### What it does not establish

Whether the model is a good one, whether the role's holder is a suitable owner, and
whether any accountability was ever exercised. Those are review questions, and a
test that answered them would be the failure the rest of this repository's suites
exist to prevent.

It also reads no ASCII box. **The diagram gap this change closed by hand stays open
by construction**: nothing mechanically compares a diagram to the tree, and the four
questions added to
[the boundary review checklist](../../architecture/boundary-review-checklist.md)
(`C6`, `C7`, `F1` through `F3`) are a reviewer's obligation, not a gate.

## Not run, and why

| Not run | Why |
|---|---|
| Any Kubernetes lane, cluster creation, or provider selection | Nothing in this change touches a cluster, a script, or a chart |
| `terraform apply`, `terraform destroy`, `helm install`, `helm upgrade` | The same. The Terraform and Helm suites read files and passed unchanged |
| Any real model, real inference, or load generation | No serving path changed, and running one would produce no evidence about a documentation change |
| Any failure or recovery experiment | §6 draws experiments that were already executed and recorded; it re-runs none of them and cites the records that did |
| `bash -n` and `shellcheck` over `scripts/` | No shell script changed |
| A secret, image, or dependency scan | No dependency, image, or lockfile changed |
| Commit, push, tag, release, or publication | Not authorized by this change |

## What the independent review found

An independent review read the first commit on this branch against the repository
before anything was pushed. It recounted every number the change introduces —
against `.github/workflows/checks.yml`, a `--collect-only` run, the fifteen ADR
status fields, the file tree, the underlying proof records, and the diff itself.

Most of them held. **Two did not, and both were mine.**

| What the first draft said | What was true | Where |
|---|---|---|
| "Four more documents" named the governance gap, enumerating four of them | **Six.** The enumeration omitted the security control matrix, and the certification document's sentence was split across lines in a way that a line-based grep missed | ADR 0015 ×3, the governance document, the changelog |
| "Four questions were added here (`C6`, `C7`, `F1` through `F3`)" | **Five.** `F1` through `F3` is three, plus `C6` and `C7` | The boundary review checklist, the changelog |

Both are corrected, and the first is corrected **in the record that got it wrong**:
ADR 0015 now says what its first draft claimed and what the count actually was. A
record whose whole subject is an uncounted field, getting its own count wrong, is
worth leaving visible.

It also points at a limit that survives this change. The decision owners are counted
from data now, and a test recomputes them. **Every count in the prose around them is
still counted by hand**, including the two above, and nothing recomputes those. That
is the same class of gap this reconciliation found nine instances of, still open, one
layer out.

The review also raised a structural weakness in the new suite, and it was right.

**The code-span exemption was too broad.** The first version stripped every inline
code span from every document before looking for the retired vocabulary, so that
ADR 0015 and the governance document could quote the sentence they retire. But a
code span is typesetting, not a quotation mark: any document could have reintroduced
the unassigned-owner claim inside backticks and the suite would have passed it. The
exemption is now restricted to those two files by path; everywhere else the phrase is
refused outright, backticks included, and a **bare** assertion inside those two still
fails. A further check requires each exempted file to actually contain a quotation,
so the list cannot go stale or grow unearned.

**The governed-document set was too narrow.** It held nine documents and missed the
boundary review checklist, which this change fills with new prose about the same
model. It now holds fifteen, including the architecture documents and the README.

Both were then mutation-tested rather than assumed:

| Probe | Result |
|---|---|
| A backtick-wrapped assertion appended to `docs/releases.md` | 1 failed — the exemption no longer travels outside the two files |
| A bare assertion appended to `docs/governance/decision-authority.md` | 2 failed — quoting is allowed there, asserting is not |

Both probes were reverted and the suite returns to 181 passed. The suite grew from
172 checks to 181 across this review.

**What the review did not find**, having looked: any invented organizational
structure in ADR 0015, any document describing an internal merge as an external
review, any authority able to raise a certification level or evidence class, any
residue of the retired wording outside a historical quote, any disagreement between
the ownership inventory and the document beside it, and any private path, name,
email, or planning identifier in the diff. The failure and recovery figures in
section 6 were checked word for word against the three records they come from.

## Limitations

- **Everything here is `local-static`.** It certifies no runtime behaviour, no
  cluster, and no claim.
- **A reconciliation is a reading.** This one compared documents to a tree by hand
  and found nine false statements; it cannot establish that it found all of them.
  The classes most likely to hide another are prose beside a machine-checked table,
  which is precisely where all nine were.
- **Naming an owner defends nothing and proves nothing.** It closes a governance
  gap. Every runtime limitation this repository carried before this change it still
  carries: one provider, one Windows host, CPU, one replica, no authentication at
  the caller boundary, no durable telemetry store, no alert routing, and no
  assessment by an outside party.
- **The two new diagram sections are design records, not evidence.** They draw
  behaviour that was observed once each, on one setup, and the records they cite are
  the evidence rather than the drawings.

## Related records

| Topic | Document |
|---|---|
| The decision this change accepts | [ADR 0015](../../architecture/decisions/ADR-0015-v1-decision-ownership-and-sign-off-authority.md) |
| The authority model, explained | [Decision ownership and sign-off authority](../../governance/decision-authority.md) |
| The decision whose `D13` it answers | [ADR 0008](../../architecture/decisions/ADR-0008-v1-security-baseline.md) |
| The architecture it reconciles | [System architecture](../../architecture/system-architecture.md) |
| The ownership inventory it extends | [Resource ownership](../../architecture/resource-ownership.md) |
| The checklist whose overdue reconciliation this was | [Boundary review checklist](../../architecture/boundary-review-checklist.md) |
| What has been proven, unchanged by this record | [The V1 proof dashboard](../dashboard.md) |
