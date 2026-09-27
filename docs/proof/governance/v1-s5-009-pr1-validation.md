# V1-S5-009-PR1 validation

Date: 2026-09-27

What this change checked before it was committed, and how. What it decided is in
[the decision whether a second version should proceed](../../governance/v2-investment-decision.md);
this page is about the checks run over the repository after that page was written.

The decision's commits executed nothing against a host: no cluster, runtime, or model
was contacted, and nothing was published. They read the frozen evidence and add none. Every
figure the decision quotes was already committed and declared by the case study.

> [!NOTE]
> Everything down to [the post-release reconciliation](#the-post-release-reconciliation)
> is about the decision, the first two commits of this change, which touched no file in
> the evidence pack. The same change then recorded the `v1.0.0` release after it was
> made, which did move the register and add a ledger; that section says what it checked,
> and what it read from the hosting service.

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

## The post-release reconciliation

After the decision's two commits, the same change reconciled the current-facing
surfaces of `main` with the `v1.0.0` release that had been made in the meantime. It is
subordinate to the decision and changes nothing the decision concludes. What it read
from Git and the hosting service is in
[its own record](../releases/v1-s5-009-pr1-v1.0.0-publication.md), which is evidence;
this section is about how the repository was checked around it.

### Verified before anything was edited

Each value was read, not taken from the request that asked for this work:

- **The tag.** `git cat-file -t v1.0.0` printed `tag`; the tag object is
  `17c9bbd71ffaeaf286f7949a1c91624bbcfe3e04`, it points to
  `718ad2e0fac8ae70c6d053a2decb00e61ff3de39`, the merge of `V1-S5-008-PR1`, its message
  quotes the pack digest `652e9051…`, and the remote holds the same object.
- **The release.** The hosting service's public API returned one release,
  `InferOps v1.0.0`, on the tag, neither draft nor prerelease, published
  2026-09-27T09:22:34Z, with no file attached.
- **The candidate's checks.** One `checks` run exists for `718ad2e`, and it passed in all
  eleven jobs before the tag.
- **Private reporting.** The API read `{"enabled": true}`; it does not say since when.
- **The frozen digests at the tag.** In a worktree at `v1.0.0`, `--gate` printed the set
  `1d40b33f…` and the pack `652e9051…`, and checks 2.4 and 2.5 passed.

### The audit

A search of the current surfaces for wording that described the release as still to
come, the private channel as disabled, or a published release as absent. Dated records
under `docs/proof/`, the dated changelog sections, and an ADR's accepted text were read
as history, and left.

| Surface | What it said | Historical or current-facing | Still true | Action |
|---|---|---|---|---|
| README, lead paragraph | `v1.0.0` "is prepared … and tagged only after its post-merge checks pass" | Current | No | Now says it is the first versioned release, cut over the frozen pack and published |
| README, counts, limitations, roadmap, entry-point rows | 41 certified, 10 not claimed, 64 records; a published release not claimed; the tag created only after the checks | Current | No | Counts and wording follow the register; the release row says it is certified only on `main`, on a record after the release |
| `SECURITY.md` and the security README, baseline, deferred risks, `CONTRIBUTING.md` | The channel read disabled; the checklist refuses the tag until it reads enabled | Current, with a dated reading | The dated reading is; the current state is not | The dated reading kept beside the one after the release; the baseline's flag moved to true |
| The register's release row | Not claimed: "no release has been executed" | Current on `main`; history in the pack | Not on `main` | Moved through the post-release ledger, at `C0`, on the new record |
| The register's reason for `SECURITY.md`, and for the evidence index | "no private channel is published"; "the four ledgers" | Current | No | Replaced through the same ledger |
| The proof dashboard, the matrix, the evidence index and its page | The release not claimed; four ledgers; one pair of digests | Current, generated or bound | No | Regenerated; the index page states the released pair and the current pair |
| Release notes | Prepared; the channel read disabled; surfaces left standing | The notes as released | True of the release | Kept word for word; a note at the top and one section after the release added |
| Release checklist | Pre-merge status; gate 12 open; post-merge checks and tag not yet run | The checklist as prepared | True when written | Kept, its status line included; a status line after the release and a section 6 of what was observed after the tag added |
| Release process and governance table | Prepared, executed only when the tag exists | Current | No | Now released on 2026-09-27 |
| Case study | A published release among what V1 does not have; a first release as the next step | Dated publication bound to the pack | True of the pack | Body kept; a note in its reading guide says the release has been made since, and that its counts describe the pack |
| The decision whether a second version should proceed | The release row is still not claimed and owed a change after the tag | Current, made in this change | No | Now reads the register as released, and says the row is certified on `main` |
| ADR 0008's dated note | The channel read disabled | History | True when written | A second dated note added |

### The claim decision

`C0` is **static evidence: artifacts inspected without executing the target
behaviour**. A release is an artifact that either exists or does not, and the record
inspected it; it executed nothing of InferOps. The register already holds a `C0` record
made with a tool that read something outside the repository, the security scan's, and
says so in its limitation. So the model permits `C0` here, and permits nothing higher:
`C1` and `C2` are about behaviour executing. What it cannot represent is recorded as a
finding and not changed: no environment for a hosting service, no evidence class whose
reads use the network, and no field for state a record cannot pin.

### Which pack is which

The pack `v1.0.0` quotes is `652e9051161d38e6dd2e77306a431bf96d863a262cc4b0dab15c0518ba920ad2`,
over the set `1d40b33fd79d7b6436c35cfe1fc4ec943a8b82fc77ad1da7cd5d96bb2a5ac23a`. After
the post-release ledger, `main` holds the set `08d4868fcf4c320961d2937b5369dc9846ca4f0455e2f60375c1decfbdab23df` and the pack
`b958a7244cb6aab924615ff099112435d1e3d527ea348b66ec7ae3e8fd1c8532`, which no release quotes. The index no longer states only one pair: it
recomputes the released pair by undoing the post-release ledger and refuses a result
that differs, and the pair itself is written once in the tool and compared with the
tag's message where the clone has the tag. A test compares the undone register with the
tagged one byte for byte, also only where the clone has the tag: continuous integration
checks out without tags, so there those two checks skip and the written pair is the
fixed reference. No cited file, earlier ledger, or dated record was edited, or the
recomputation would fail.

### Tests that had to change, and why

Six modules held the register, the index's counts, or its digests to what the frozen
pack said, and read them from the current register and summary. Each now reads the
state it is about: the historical ledgers' modules, the case study's, the release's,
and the decision's read the register as released and the released summary; the
surfaces that are current read the current ones. Three tests were tripwires set to
fire when this row moved: `test_release.py`'s and the decision's release-row checks,
and the dashboard's count for its release group. Each fired. The first two are replaced
by checks of both states; the dashboard's reads the current state only, because the
dashboard is current. The security baseline's and the release's
reporting-setting checks moved with the reading, as their docstrings said they would.
The index's rule that no ledger promotes a status gained one exception, for exactly
this claim and exactly this ledger, on a record the same ledger adds.

### Results

On 2026-09-27, on the same Windows host, with every file staged:

| Command | Result |
|---|---|
| `ruff format --check .` | 525 files already formatted |
| `ruff check .` | All checks passed, after one fix it applied to the new module's comparison order |
| `python -m mypy` | No issues in 280 source files |
| `pytest tests/testing/test_evidence_post_release.py -q -rs` | 27 passed, none skipped: this clone holds the tag, so the two checks that read it ran |
| `pytest tests/testing tests/security tests/architecture -q` | 10723 passed, 3 skipped, and 1 failed, the dashboard's release-group count, a tripwire; after it was replaced the default lane below ran them all again |
| `python -m tools.proof_dashboard --check` and `python -m tools.evidence_index --check` | Both `OK` |
| `python -m tools.evidence_index --gate` | Exit 0: `FROZEN V1-S5-013-PR2`, then `RELEASED v1.0.0` with the set `1d40b33f…` and the pack `652e9051…`, then `CURRENT` with the pair above |
| `pytest -q`, the default lane | 15438 passed, 30 skipped, 14 deselected, in 24 min 5 s |
| `git diff --cached --check` | Clean, after one blank line at the end of the transcript was removed |

The first run of the documentation suites after the register moved failed at
collection in three modules, which undid the publication ledger from the current
register and met the post-release change first; that is what led to reading each
module's state explicitly. The next full run failed one test, the dashboard's release
group count, which was a tripwire.

### What the independent review of the reconciliation found

Two reviewers read the reconciliation's commit independently: one checked every value
against Git and the hosting service's API and every statement against the files, and
the planning set for leakage; one reviewed the tooling and the tests and mutated them.
Every release value, count, and digest was confirmed, the recomputed released counts
equal the tagged index's, and nothing leaked. What they found, each corrected before
the next commit:

- **The released pair had no fixed reference where tests run without tags.** An earlier
  ledger edited after the release, with every committed copy of the old digest
  rewritten to the new one, passed every test a clone without tags runs. The pair is now
  written once in the tool, `RELEASED_DIGESTS`, and a ledger that states another pair
  for the tag is refused; a new test edits an earlier ledger in a copy of the tree and
  requires the refusal. The commit message had said the index refuses a pair differing
  from the digests themselves; until this change it compared only with the ledger.
- **The index page's two rows were not tied to their labels.** Swapping them passed; the
  test now reads each row whole, and the swap fails.
- **The merged released summary fell back to current values** for four counts the
  released pack did not state; it now states them.
- **Two checks about the current register had moved onto the released one**; each now
  reads both.
- **Smaller test defects**: the refusal tests matched any error, one assertion could not
  fail because text reading removes carriage returns, a docstring promised a comparison
  with the tagged notes that nothing made, and the register's own rendering was checked
  only against the tag. Each is fixed: the refusals match their messages, the transcript
  is read as bytes, the notes are compared with the tag where the clone has it, and the
  register is compared with its rendering in every clone.
- **False or overstated wording.** The matrix page still gave the two surface reasons the
  ledger replaced. The notes and the release data placed the case study's note "at its
  top" when it was in section 12, and the case study's section 6 still stated the pack's
  counts as today's; the note now sits in its reading guide and covers every such
  statement. The dashboard attributed the release claim's new level to the migration
  report; it now says a claim can gain a record through a later ledger. The checklist's
  original status line had been reworded rather than kept, and is now kept verbatim; 2.1
  was called verified when only the tagged commit is; 2.2, 2.3, and section 4 had no
  row. The record said nothing but the tag and archives is published, where no registry
  was read; listed seven of its sixteen commands; and called the security scan's
  limitation the same mismatch when it states only a dependence on time. "Executed"
  said more than the unrecorded pre-tag checks allow, "the only record made since"
  missed this page, and the decision page's "moves no claim" needed the post-release
  ledger set apart from it.

### After the review of the reconciliation

Before the next commit, on the same host, with every file staged: `ruff format --check .`
525 files already formatted; `ruff check .` all checks passed; `python -m mypy` no issues
in 280 source files; the post-release module 30 passed, none skipped; `--check` for the
dashboard and the index both `OK`; `--gate` exit 0, `RELEASED` with `1d40b33f…` and
`652e9051…` and `CURRENT` with the pair stated above; swapping the index page's two rows,
which the review's mutation had passed, now fails the module; the default lane 15442
passed, 30 skipped, 14 deselected, in 30 min 28 s; and `git diff --cached --check` clean.
The release notes, the checklist, the case study, and ADR 0008 differ from the tag by
added lines only.

### Left as history, and why

The release notes and the checklist above their added sections, the case study's body,
the dated reports and records under `docs/proof/`, the changelog's `1.0.0` section, and
the accepted text of ADR 0008 and ADR 0009 describe the repository when they were
written, and are true of it. Rewriting them would make the frozen pack look as if it had
known about its own release.

### Privacy

The tagger's name and address are replaced in the transcript, and the new files were
searched for a drive-letter or home-directory path, a scratch directory, and an address;
none is present. The repository's public identifiers, its owner's account name in its
URL and in the merge commit's subject, are the ones the hosting service already
publishes.
