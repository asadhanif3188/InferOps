# V1-S5-009-PR1 validation

Date: 2026-09-27

What this change checked before it was committed, and how. What it decided is in
[the decision whether a second version should proceed](../../governance/v2-investment-decision.md);
this page is about the checks run over the repository after that page was written.

This change executed nothing against a host: no cluster, runtime, or model was
contacted, and nothing was published. It reads the frozen evidence and adds none. Every
figure the decision quotes was already committed and declared by the case study.

## Eligibility, checked before anything was written

- **The gate and the freeze.** On `main` at `718ad2e`, `python -m tools.evidence_index
  --gate` exited 0 with the gate complete and the pack frozen, the evidence set
  `1d40b33f…` and the evidence pack `652e9051…`.
- **The release.** `git tag -l v1.0.0` printed the tag, and it resolves to `718ad2e`,
  the merge of `V1-S5-008-PR1`. Both stories this one depends on are merged.
- **What the pack covers.** Every file a record cites, the register, and its four
  ledgers. The decision's page and data, the README, the governance table, the
  changelog, and the test inventory are outside it, so the change could leave both
  digests where they were frozen; it touches no file inside the pack.

## What changed

- **The decision.** `docs/governance/v2-investment-decision.md` and the data it is held
  to, `v2-investment-decision.v1alpha1.json`: eleven findings with the register rows
  behind each, ten problems each asked three questions, three options compared on the
  same fields, six entry gates, the eighteen uncertified claims placed, figures, a
  review date and triggers, and one surface left standing.
- **Links to it.** A bullet in the README's roadmap and a row in the governance table,
  both in prose; the README's entry-point table is governed by the register, which is
  inside the frozen pack, so the decision is not added there.
- **The changelog.** One entry under the unreleased section.
- **Tests.** `tests/testing/test_v2_investment_decision.py` is new. The test inventory
  lists it, which makes forty-five documentation modules and forty-seven that defend no
  claim. The documentation layer's narrative sentence had stopped at the forty-third
  module; `V1-S5-008-PR1` added the forty-fourth without extending it, and this change
  extends it for both.

## What the checks caught before the first commit

- **Formatting.** `ruff format --check` refused the new module until it was reformatted.
- **Mutations.** Eighteen deliberate corruptions of the data and the page were applied
  one at a time by a script kept outside the repository, and the module was run after
  each: an outcome that opens a version while gates are unmet, a finding's status or
  record levels differing from the register, a record its finding's claims do not
  cite, an uncertified claim dropped or placed in something that does not exist, an
  expected `C4`, a review date a year out, an option missing a field, a wrong digest, a
  wrong tag commit, a stray measurement, a gate state or a problem answer differing
  between page and data, a broken fragment, a forbidden phrase, the selected marker on
  no option, and a status wrong in the page's findings table. Each was refused, and the
  files were restored after each. The script is not committed, so this paragraph is its
  only record and a reader cannot rerun it; the checks it exercised are the module's.

## Commands

From Git Bash at the repository root, with every file of this change staged so that the
suites that read `git ls-files` see it. `uv` ran with `--offline` against its cache, as
in `V1-S5-008-PR1`; the lock is unchanged.

```text
uv run --locked --offline ruff format --check .
uv run --locked --offline ruff check .
uv run --locked --offline python -m mypy
uv run --locked --offline python -m pytest tests/testing/test_v2_investment_decision.py -q -rs
uv run --locked --offline python -m pytest tests/testing tests/security tests/architecture -q
uv run --locked --offline python -m tools.proof_dashboard --check
uv run --locked --offline python -m tools.evidence_index --check
uv run --locked --offline python -m tools.evidence_index --gate
uv run --locked --offline python -m pytest -q
git diff --cached --check
```

## Results

On 2026-09-27, on one Windows host, before the first commit:

| Command | Result |
|---|---|
| `ruff format --check .` | 523 files already formatted, after one reformat of the new module |
| `ruff check .` | All checks passed |
| `python -m mypy` | No issues in 279 source files |
| `pytest tests/testing/test_v2_investment_decision.py -q -rs` | 69 passed, none skipped |
| `pytest tests/testing tests/security tests/architecture -q` | 10658 passed, 3 skipped, in 8 min 24 s |
| `python -m tools.proof_dashboard --check` | `OK       dashboard.md is what the register produces` |
| `python -m tools.evidence_index --check` | `OK       v1-evidence-index.v1alpha1.json is what the register and ledger produce` |
| `python -m tools.evidence_index --gate` | Exit 0, `FROZEN   V1-S5-013-PR2` with the evidence set `1d40b33fd79d7b6436c35cfe1fc4ec943a8b82fc77ad1da7cd5d96bb2a5ac23a` and the evidence pack `652e9051161d38e6dd2e77306a431bf96d863a262cc4b0dab15c0518ba920ad2`: both unchanged from `main` |
| `pytest -q`, the default lane | 15372 passed, 30 skipped, 14 deselected, in 13 min 38 s |
| `git diff --cached --check` | Clean |

The Helm and Terraform gates were not run: nothing under `charts/` or `infra/` changed.
The hosted `checks` workflow runs on the pull request and is not quoted here. The default
lane ran before one sentence of the decision page was reworded — it had said the
record draws its entry gates from the case study, when three of the six come from there —
which changed prose only; the decision, security-baseline, and link suites passed again
afterwards.

## What the independent review found

Two reviewers read the first commit independently: one checked every public statement
the change makes against the files it rests on, and the private planning set for
leakage; one reviewed the test module, the inventory entry, and the decision's internal
logic. Between them they found five false statements, thirteen weaker ones, three
passages whose wording was carried over from unpublished planning, two defects in the
decision's data and test, and seven notes. Every one was corrected before the second
commit, or is answered below.

**What the first draft got wrong.**

- **It said an operator who trusted pod readiness was wrong "for its whole outage".**
  The readiness samples had all finished before the outage began; the only sample
  inside it shows the replacement Ready and agrees with the Service. It now says the
  operator was wrong in the seconds before the outage, and that the outage's first
  seconds were not sampled.
- **It called the one-replica outage "the largest caller-visible effect V1 measured and
  the only one whose cause its record names".** The unready-model window refused every
  completion for longer, and its record names its cause too. It is now the outage a lost
  pod caused, whose record names one replica as the cause.
- **It said every real result is one provider.** The optional `kind` helper's record ran
  on a second provider. It now says every real result a certified claim rests on.
- **It said an evidence level is kept apart from whether anything was substituted.**
  Substitution is part of what a level encodes: `C1` is Substituted Execution. It is now
  kept apart from the workload, where it ran, and the hardware.
- **It left the inventory's "Forty-six suites protect something" sentence stale** while
  the table beneath it gained a forty-seventh row.
- **It listed a claim as movable in the next field to one saying it could not move.**
  `no-representative-evidence` named `inferops-is-a-portable-production-platform`, whose
  register row says `C4` is not reachable. It now moves no claim, and a new check refuses
  a problem that lists as movable a claim the register calls unreachable.
- **Its gate-table check accepted a duplicated, contradictory row**, because it compared
  a dictionary: the review showed a spurious `unmet` row above the real `met` one
  passing. It now compares the rows in order.
- **Its "What is machine-checked" section overclaimed.** "No other measurement appears"
  is true only of numbers beside a unit of time, a percentage, a unit of memory, or a
  rate, and the page quoted "about fourfold", which no data declares; the phrase is
  removed and the section says which numbers are scanned. "Every identifier" left out
  the surface identifier, which the page now publishes and the test now checks, and the
  governance link check read the whole file rather than the table's row.

**Weaker findings, each corrected.** Infeasibility was stated in the present tense from
one refusal on 2026-09-12 that nothing has re-measured; it now carries the date. "No
outside party has reviewed anything" widened what the release notes and the register
say, and now uses their words. "Nothing beyond one loopback host is possible" became what
has been done. "An enforcing network plugin and pod admission can run on a local
cluster" dropped that both routes the network-policy record names change an accepted
environment decision and that no record covers pod admission. "The two registered
series nothing emits" undercounted, and emitting the restart count needs an add-on the
chart does not own. Runs on `kind` and a non-Windows host were placed in finishing V1 as
"already promised"; the case study lists them as evidence for a second version, and
they are now a later version's. Redundancy was said to change an accepted decision
without naming one; V1 ships the multi-replica profile, so running it on a capable host
is now finishing V1, and only losing one of several replicas under load, which no
descriptor registers, is a later version's. "Only the author has walked the road"
ignored the scaffold walkthrough's independent reviewer, and now says the clean-clone
journey. The cost finding dropped "in the first run"; the readiness finding dropped
"at every readiness sample" and "by the record's reading"; proceed's cost was stated as
what the case study says without the hedge the data kept; and every "feasible" is now an
expectation, not yet tried, with the multi-slot rerun marked as possibly not fitting the
host.

**Wording carried over from unpublished planning.** Two gates were close to a private
list and are renamed and reworded in this record's own terms,
`the-road-has-been-run-under-failure` and `this-record-is-merged`, with the page saying
the other three gates are added here. Proceed no longer describes a direction beyond
"widen what it supports". Phrases paraphrasing the change's private brief — a list of
reasons not to add scope, a list of engineering problems, a phrase about demand, and
"rather than from a plan" — are reworded, and a generic word dropped from the test's
forbidden phrases. None revealed another project, a tool, or a schedule.

**Notes.** ADR 0011 joins the decisions cited as they stand; the boundary document's own
restraint is no longer called a rule for other records; accelerator economics is placed
under rule 3 as work on the hardware the runtime is given; the evidence basis names the
tag and notes beside the frozen pack; the scrape-health reading cites the committed
telemetry rather than the record's narrative, which says more than its data; the
mutation script's absence is stated above; and the review date is said plainly to fire
nothing automatically.

**Not changed.** The gate rule's circularity — the author chose both the gates and the
outcome — was judged honestly disclosed, and the page now says it in as many words. The
fragment check's slug approximation does not model GitHub's suffixes for repeated
headings; it would fail loudly on a correct link, and a comment says so.

## After the independent review

Before the second commit, on the same host, with every file staged:
`ruff format --check .` 523 files already formatted; `ruff check .` all checks passed;
`python -m mypy` no issues in 279 source files; the decision module 70 passed, none
skipped, and twenty-one corruptions, the first eighteen and three for what the review
found, each refused; `--check` for the dashboard and the index both `OK`; `--gate` exit
0 with both digests unchanged; the default lane 15373 passed, 30 skipped, 14 deselected,
in 13 min 6 s; and `git diff --cached --check` clean.

## Privacy and publicability

The staged diff was searched for a drive-letter or home-directory path, a scratch
directory, an e-mail address, a credential-shaped string, and the name of any private
planning document or any other project. None is present. The decision describes where
work belongs by the boundary rules this repository already publishes, and names no
other project. No model artifact, generated render, built distribution, or machine
state is added.
