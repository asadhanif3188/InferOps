# V2-S0-001-PR1 validation

Date: 2026-09-28

What this change checked before it was committed, and how. What it decided is in
[the decision that opens a second version](../../governance/v2-authorization.md); this
page is about the checks run over the repository after that page was written.

The change executed nothing against a host: no cluster, runtime, or model was
contacted, nothing was provisioned, and nothing was published. It reads the pack
`v1.0.0` was cut over and adds no evidence to it.

## Eligibility, checked before anything was written

- **The earlier decision is merged.** `main` was at `7d0167d`, the merge of
  `V1-S5-009-PR1`, which carries the defer decision this change supersedes.
- **The release.** The tag `v1.0.0` resolves to `718ad2e`.
- **The gate and the pack.** `python -m tools.evidence_index --gate` exited 0: `FROZEN`
  for `V1-S5-013-PR2`, `RELEASED v1.0.0` with the set `1d40b33f…` and the pack
  `652e9051…`, and `CURRENT` with the set `08d4868f…` and the pack `b958a724…`.
- **What the pack covers.** Every file a record cites, the register, and its five
  ledgers. None of the files this change touches is among them, so all three pairs of
  digests could stay where they were, and did.
- **What the earlier record provides for.** It does not provide for a decision before
  its review date or one of its triggers, and none of its five triggers had fired; the
  new page says so, and that it is taken on the maintainer's initiative. It follows the
  form the earlier record sets for a review, which "either confirms this record with a
  dated note or replaces it with a new decision; it does not edit the reasoning above in
  place": a new decision, with only a dated note added at the earlier page's top.

## What changed

- **The decision.** `docs/governance/v2-authorization.md` and the data it is held to,
  `v2-authorization.v1alpha1.json`: the earlier record, with hashes of its data and of
  its page without the note; its five triggers, none fired; the thesis, the five
  earlier findings it starts from, and the one V1 claim about release change; one moved
  placement; the six earlier gates and three of the `revise` option's prerequisites,
  each with a treatment; eight things the version does not take on; three reasons to
  look at the decision again; and two passages of the case study left standing.
- **The earlier decision.** Its page gains a dated note under its title, three added
  lines. Its data and its test are unchanged.
- **Current surfaces.** The README's roadmap bullet and the governance table's
  "Next version" row said the version was deferred; both now say it is open, link both
  records, and keep the three unmet gates visible. The proof records index lists this
  record. The changelog gains one entry under the unreleased section.
- **Tests.** `tests/testing/test_v2_authorization.py` is new. The test inventory lists
  it, which makes forty-seven documentation modules and forty-nine that defend no claim;
  both counted sentences and the documentation layer's narrative sentence are extended.
- **A pre-existing test defect.** `tests/testing/test_release.py`'s check that every
  story merged into the release is listed read the merges of `HEAD`, so the first story
  merged after the release, `V1-S5-009-PR1`'s pull request, failed it on every full
  clone of `main` since that merge. Continuous integration skips the check, because it
  clones without history, so the failure was never reported. It now reads the merges the
  released commit contains, which the release data already records. No release file is
  changed.

## Traceability: what the story asks, and where the decision answers it

| The story asks that | Answered in |
|---|---|
| A governed decision explicitly revisits, revises, or supersedes the defer outcome | The page's status line and "The decision": it supersedes the outcome and edits none of the earlier record; the test holds the earlier data to its hash and the earlier page to its hash without the note |
| The decision names caller-visible reliability under failure or change as the thesis | "The thesis", which also says what V1 did and did not measure of release change |
| Contract-to-deployment rendering is moved into V2, and the reason is documented | "Contract-to-deployment rendering moves into V2", with three reasons and what does not change |
| Still-unmet gates stay visible and are classified as targets, deferred items, or blockers | "The earlier record's entry gates, and how each is treated": six gates and three prerequisites; the test refuses a gate unmet then and called met now |
| No V1 evidence, tag, release, or historical decision is rewritten | No file in the pack changed, and the gate printed the same three pairs of digests before and after; the earlier record's data is byte for byte as merged; no release file changed; the one edit to a V1 test is to a check's history range, not to what it compares |

The traceability to the story's acceptance criteria was checked by the author and is a
reading; the test checks the decision against the earlier record, not against the
story.

## What the checks caught before the first commit

- **Formatting.** `ruff format --check` refused the new module until it was reformatted.
- **The test's own parser.** Its table reader dropped every table, because it tested
  for a table row before skipping the separator line; and a phrase check missed a
  sentence wrapped inside a blockquote. Both were fixed before any result below.
- **The test's list of forbidden phrases** was cut to the overclaim and appeal words the
  earlier record's test refuses.
- **Mutations.** Twenty-six deliberate corruptions of the data, the page, the earlier
  record, the README, and the governance table were applied one at a time by a script
  kept outside the repository, and the module was run after each with `-x`: the earlier
  record's data or reasoning edited, the note moved, an unmet gate called met, an earlier
  gate state restated, a treatment outside the vocabulary, a gate treatment differing
  between page and data, a duplicated gate row, a wrong unmet count, a misquoted
  prerequisite, a blocker naming nothing, an altered quotation, a wrong digest, a trigger
  said fired against the dates or the register, a trigger dropped, a claim moved, a
  placement moved from somewhere it was not, an unknown finding, a forbidden phrase, a
  stray measurement, a broken fragment, a dropped boundary link, a decision dated after
  the review date, and the README or the governance row left saying deferred. Each was
  refused, and the files were restored after each. With `-x` only the first failing test
  is reported: for twenty-three it is the check written for that corruption; for three —
  the treatment outside the vocabulary, the misquoted prerequisite, and the decision
  dated after the review — it is an agreement check that fails first, because each
  corruption also breaks agreement with the page or the earlier record's note. The script is
  not committed, so this paragraph is its only record; the checks it exercised are the
  module's.

## Commands

From Git Bash at the repository root, with every file of this change staged so that the
suites that read `git ls-files` see it. `uv` ran with `--offline` against its cache; the
lock is unchanged.

```text
uv run --locked --offline ruff format --check .
uv run --locked --offline ruff check .
uv run --locked --offline python -m mypy
uv run --locked --offline python -m pytest tests/testing/test_v2_authorization.py tests/testing/test_v2_investment_decision.py tests/testing/test_test_inventory.py tests/testing/test_release.py -q -rs
uv run --locked --offline python -m pytest tests/testing tests/security tests/architecture -q
uv run --locked --offline python -m tools.proof_dashboard --check
uv run --locked --offline python -m tools.evidence_index --check
uv run --locked --offline python -m tools.evidence_index --gate
uv run --locked --offline python -m pytest -q
git diff --cached --check
```

## Results

On 2026-09-28, on one Windows host, before the first commit:

| Command | Result |
|---|---|
| `ruff format --check .` | 528 files already formatted, after one reformat of the new module |
| `ruff check .` | All checks passed |
| `python -m mypy` | No issues in 281 source files |
| The decision's, the earlier decision's, the inventory's, and the release's modules, `-rs` | 1165 passed, none skipped |
| `pytest tests/testing tests/security tests/architecture -q` | 10776 passed, 6 skipped, in 12 min 53 s |
| `python -m tools.proof_dashboard --check` | `OK       dashboard.md is what the register produces` |
| `python -m tools.evidence_index --check` | `OK       v1-evidence-index.v1alpha1.json is what the register and ledger produce` |
| `python -m tools.evidence_index --gate` | Exit 0: `FROZEN V1-S5-013-PR2`, `RELEASED v1.0.0` with the set `1d40b33f…` and the pack `652e9051…`, and `CURRENT` with the set `08d4868f…` and the pack `b958a724…`: all unchanged from `main` |
| `pytest -q`, the default lane | 15490 passed, 33 skipped, 14 deselected, in 19 min 43 s |
| `git diff --cached --check` | Clean |

The first run of the three documentation suites, before the release module's history
range was corrected, failed that one check and passed everything else. The six skips in
the documentation suites are this host's: two symbolic-link tests the host does not
permit, one signal Windows does not deliver, and three checks against the pinned
collector image, which is not present on this host. The last three are why the default
lane skipped 33 here where `V1-S5-009-PR1`'s run skipped 30; none reads a file this
change touches. The default lane ran before the last two edits to the new module's list
of phrases and the page's sentence describing it; the decision's module and the quick
checks above ran after them.

The Helm and Terraform gates were not run: nothing under `charts/` or `infra/` changed.
No cluster, runtime, or model lane was run, because nothing that executes changed. The
hosted `checks` workflow runs on the pull request and is not quoted here.

## What the independent review found

Two reviewers read the first commit independently: one checked every public statement
against the files it rests on, and the private planning set for leakage and for fidelity
to the story; one reviewed the test module, the release module's change, and the data's
logic, and mutated them. They found four false statements, three test defects, two
checks weaker than they needed to be, six weaker statements, two lines that said more
about the private planning than they needed to, and notes. Each was corrected before the
second commit, or is answered below.

**What the first draft got wrong.**

- **It said V1 never deployed a bad release or rolled one back, and its test required
  the sentence.** The register certifies
  `a-controlled-release-change-can-be-reversed-and-real-inference-restored` at `C2` on
  two runs, each rolling back a release with an injected fault. The thesis now says what
  V1 measured — a rollback run by a script a person started, with readiness probes as
  the only callers — and what it did not: a caller under load during a bad release, a
  rollout, or a rollback, and any drift. The page even contradicted itself, saying
  elsewhere that V1 already rolls releases back through Helm. The data now cites the
  claim, and the test checks it is certified and that the page states its level and its
  run count.
- **It said nothing was added between the two records except the post-release ledger,
  "which moved only the release row".** The ledger and its record came in the same change
  as the earlier record, which cites both, and the ledger also adds a record and changes a
  register-level surface reason. Both sentences now say that nothing has been added since
  the earlier record merged.
- **Its data said every problem's three answers were kept**, while moving the third
  answer for one of them. It now says so.
- **The validation record's commands did not produce the result it quoted:** the release
  module was in the result and not in the command. It is now in both.

**Test defects.**

- **The page's "How" cells were never compared with the data.** Changing them on the page
  alone passed, while the page said its tables say what the data says. Every column is
  now compared.
- **The quotation check matched only straight quotes.** A fabricated passage in curly
  quotes passed. Both kinds are now matched, and the earlier page is normalised the same
  way.
- **The trigger check read only the first table in its section,** so a contradicting table
  inserted beside it passed. The section must now hold exactly its two tables.

**Checks weaker than they needed to be.** A note on the earlier page edited the same way in
the page and the data — the reviewer's example added that a gate was satisfied by the note
alone — passed every check, because the hash is taken after removing whatever the data
holds; the note's text is now pinned in the module itself. The README's sentence that the
decision moves no claim could be rewritten to say one moved; the module now requires it.

**Weaker statements, each corrected.** The capacity blocker was said to block the
replica-loss experiment "and nothing else"; it blocks every experiment needing more than
one serving replica. The outside-review condition allowed any reviewer outside the
repository and a review of the claim or its evidence; it now requires a person, not an AI
reviewer, the claim and its evidence, and no open finding that blocks the release. This
record said the earlier record allows a decision like it; the earlier record does not
provide for a decision before its review date, and this record says it follows only the
form a review takes. "Nothing has re-measured the host" was broader than true — later
records read the node's capacity — and now says nothing has run the multi-replica capacity
gate again. The judgment that the one-replica outage is the problem V1 exposed most clearly
is now stated as this record's, beside the case study's different emphasis, and the
earlier record's "its problem is the right one" is quoted with its "but". The README, the
governance row, and the changelog called the unmet gates targets, deferred items, or
blockers, when no gate is a blocker; the host prerequisite is, and they now say which is
which. The second person's run was "sought", which nothing shows; it is now "waited for",
the earlier record's words.

**The leak.** Two lines of this record described what the forbidden-phrase list and the
privacy search had been looking for, which said more about the private planning than the
check needed. Both are cut to what was checked.

**Notes, answered.** The non-goal on remediation now names changing desired state or rolling
back without a person's approval, and says bringing running state back to an approved state
is not excluded. "A service mesh by default" loses its qualifier. The runtime non-goal cites
boundary rule 3 for hardware given in proportion to demand, its own words, and says drifting
into autoscaling leaves the thesis. The case study's two passages that predate this record
are listed, with a tripwire, as the earlier record listed one. "Every quotation" in the
machine-checked list now says which passages the check reads. The story's wider traceability
stays with its private planning and is not published; the table above traces its
acceptance criteria only.

**Not changed.** The check that no ledger names this change can only fire if an old ledger
is edited; it is kept, and the pack test beside it is the stronger guard. The mutation
script stays uncommitted, so its counts rest on this record.

## After the independent review

Before the second commit, on the same host, with every file staged: `ruff format --check .`
528 files already formatted; `ruff check .` all checks passed; `python -m mypy` no issues
in 281 source files; the decision's, the earlier decision's, the inventory's, and the
release's modules 1166 passed, none skipped; `--check` for the dashboard and the index both
`OK`; `--gate` exit 0 with all three pairs of digests unchanged; thirty-five corruptions,
the first twenty-six and nine for what the review found — a "How" cell changed on the page
alone, for a gate and for a prerequisite; a fabricated passage in curly quotes; a
contradicting table beside the triggers; the note extended in the page and the data
together; the README saying a claim moved; the release claim's run count wrong; the V1
rollback denied again; and a standing surface dropped from the page — each refused, and
the files restored after each; the default lane 15491 passed, 33 skipped, 14 deselected, in
9 min 0 s; and `git diff --cached --check` clean. One sentence of the page was reworded
after the lane, to say the case study is V1's rather than the earlier record's; the
decision's module passed again afterwards.

## Privacy and publicability

The staged diff's added lines were searched for a drive-letter or home-directory path, a
scratch directory, an e-mail address, a credential-shaped string, the name of any
private planning document, and a later story's identifier. None is present. The decision describes
where work stops by the boundary rules this repository already publishes, and names no
other project. No model artifact, generated render, built distribution, or machine state
is added.

## Final pre-merge governance correction

A review of the whole pull request before merge, at `bf4c7d8`, found two statements
that were not what the record means. Both are corrected in a third commit. Nothing
above is rewritten: it records the first two commits as they were checked.

**The earlier gate that asks for a review of V1 was treated as a V2 target.** The data
and the page gave `someone-outside-the-repository-has-reviewed-v1` the prior state
`unmet` and the treatment `v2-target`, and the same row said "the gate as written, a
review of V1, stays unmet". Those conflict. A target is something V2 must reach, and a
review of V2 cannot meet a gate that asks for a review of V1. The gate keeps the prior
state `unmet`, and its treatment is now `deferred`: waited for, not scheduled, not met
by anything V2 does. The review V2's release waits on is now its own entry,
`a-person-outside-the-repository-has-reviewed-v2`, under `v2ReleaseConditions` in the
data and in its own section of the page. It is `unmet`. It requires all of the following:

- a person, not an AI reviewer, outside this repository and its implementation;
- a review of V2's central claim and the evidence it rests on;
- the findings recorded;
- no blocking finding open at release.

It says it meets no V1 gate, certifies and endorses nothing, raises no record's level
(neither `C3` nor `C4`), and is no evidence of production operation. It names the earlier
gate as the one it is not the treatment of. The README's roadmap, the governance
table's row, and the changelog said two unmet gates "become conditions of the new
version's release". They now say one gate becomes a target and two are deferred, and
that V2's release separately waits on its own review.

**The page said "It does not change an accepted decision."** It does supersede the
outcome of an accepted decision. What stays true is narrower, and the bullet now says
it: "It does not amend any accepted ADR or edit the earlier decision in place". The
earlier decision's outcome is superseded from this record's date on, and that record
stays as it was decided. The data gains `adrsAmended`, empty. The changelog said the
change "changes no accepted decision" and now says it amends no accepted ADR.

**What the module now checks.** Seven tests are added:

- the review gate is `unmet` and `deferred`;
- no gate whose identifier ends in `-v1` is a V2 target;
- the review condition is not a gate of the earlier record, names the review gate as
  the one it is not the treatment of, and says it meets no V1 gate;
- it is unmet, required before V2's release, and requires each of the six things above;
- it says it does none of the five things above;
- the page states the condition and its limits as the data does;
- the data amends no ADR, no ADR names this change, the old sentence is gone and the
  new one present, and every ADR number the section names exists.

The README and governance-row check also refuses the old wording.

The same uncommitted script applied sixteen new corruptions, fifty-one in all, one at
a time. All fifty-one were refused, and the files were restored after each. The new
sixteen:

- the review gate set back to `v2-target` in the data alone, and in the page and the
  data together;
- one requirement dropped from the condition: the open-blocker requirement, and
  separately the human reviewer;
- `certify-anything` or `meet-a-v1-gate` dropped from what the condition does not do;
- the condition said met;
- the condition pointed at the road gate, or renamed to the V1 gate;
- the page dropping "not an AI reviewer", or saying the review produces `C3`;
- an ADR listed as amended, or an ADR naming this change;
- the old ADR sentence restored;
- the README or the governance row collapsing the gates again.

The one set back in the data alone is caught first by the check that the page's table
is the data's. The same change in both files is caught by the check written for it.

**An independent review of the staged correction** found nothing blocking. It raised
five points of polish, all taken:

- two lines to rewrap;
- a "which" whose antecedent was unclear;
- the data's `replaced` entry calling the gates "conditions" beside the new release
  condition;
- a compressed sentence in the module's docstring.

**What did not change.** No claim, status, or level; no register row, ledger, record, or
other file in the evidence pack; no ADR; the earlier record's data and page; the thesis,
the non-goals, the rendering move, and the evidence-level section; and nothing that
executes. This is a correction of how the record describes a gate. It promotes no result
and adds no evidence.

On the same host, from Git Bash, with every file staged:

| Command | Result |
|---|---|
| `ruff format --check .` | 528 files already formatted, after one reformat of the module |
| `ruff check .` | All checks passed |
| `python -m mypy` | No issues in 281 source files |
| The decision's, the earlier decision's, the inventory's, and the release's modules, `-rs` | 1173 passed, none skipped |
| `pytest tests/testing tests/security tests/architecture -q` | 10784 passed, 6 skipped, in 10 min 0 s |
| `python -m tools.proof_dashboard --check` | `OK` |
| `python -m tools.evidence_index --check` | `OK` |
| `python -m tools.evidence_index --gate` | Exit 0: `RELEASED v1.0.0` at `718ad2e` with the set `1d40b33f…` and the pack `652e9051…`, and `CURRENT` with the set `08d4868f…` and the pack `b958a724…`: unchanged |
| `pytest -q`, the default lane | See below |
| `git diff --cached --check` | Clean |
| `git diff main -- docs/governance/v2-investment-decision.v1alpha1.json` | Empty |
| `git diff --name-only main -- docs/architecture/decisions` | Empty |

The broad run and a first default-lane run (15498 passed, 33 skipped, 14 deselected)
both came before the review's polish and this section. The default lane was run again
after both; its result is in the next line.

The second default-lane run passed 15498, skipped 33, and deselected 14, in 10 min
3 s. The seven added tests are the difference from the 15491 before this correction.
The 33 skips are this host's, as above. The 14 deselected are the lanes that need a
cluster, a runtime, or a model, which a change to a governance record does not
exercise. Replacing this paragraph's placeholder was the last edit to the record.
After it, the decision's and the three related modules passed again, and
`git diff --cached --check` stayed clean.
