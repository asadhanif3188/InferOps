# V2-S5-007-PR1 validation

Status: **the ExperimentRun page no longer states a stale number of evidence
roles, and a test holds the four places of the current pages that state the role
vocabulary to the module. The change is checked at evidence level C0, against
committed pages. No role, rule, run, raw evidence file, freeze record, claim, or
evidence level was changed.**

> **This change corrects a page of an earlier change, and the record says so.**
> [`V2-S5-002-PR2`](v2-s5-002-pr2-validation.md) published the evidence layout
> with 13 roles, and the ExperimentRun page stated that number.
> [`V2-S5-003-PR2`](../environment/v2-s5-003-pr2-validation.md) added the raw
> role `operator-events` and updated the layout page, its suite, and the index of
> the testing pages to 14. It did not update the ExperimentRun page. A review of
> the sprint on 2026-10-13 reported this. It was reported to the author, and no
> file in this repository records that review. The two earlier records are not
> edited.

| Property | Value |
|---|---|
| Date | 2026-10-14 |
| Base | `32d1a4b`, the merge of pull request #144 |
| Branch | `fix/v2-s5-007-evidence-role-docs` |
| Commits | The first commit, `c037640`: the page, the guard, and this record. The second commit: the corrections of an independent review, the record of them in this file, and the result of the default lane |
| Host | One Windows workstation, Git Bash; Python 3.12.12 from `uv`. `gitleaks` is not installed |
| Evidence level | C0. Every check reads committed files or text that a test changes in memory. No check contacts a cluster, a caller, or a telemetry collector |
| Claim effect | None. No claim, ledger, register row, dashboard row, evidence-index entry, freeze record, run directory, or raw evidence file was added or changed |

## The defect

The module [`tools/experiment_evidence`](../../../tools/experiment_evidence/core.py)
registers 14 roles in `ROLES`: 12 raw and 2 derived. The ExperimentRun page said,
in the bullet "It does not define a role vocabulary", that the evidence layout
registers 13 roles.

Five places of the current pages state the vocabulary or its number. At the base
they were as follows.

| Place | At the base | Read by a test at the base |
|---|---|---|
| The role table of [the layout page](../../testing/experiment-evidence-layout.md#roles-raw-and-derived) | 14 rows, the names, kinds, and descriptions of the module | Yes, row for row |
| The count row of the layout page, `Roles` | `14: 12 raw and 2 derived` | No |
| The row of the layout page in [the index of the testing pages](../../testing/README.md) | "the 14 roles of an evidence file" | No |
| The bullet of [the ExperimentRun page](../../contracts/experiment-run.md#what-this-contract-does-not-do) | "registers 13 roles" | No |
| The sentence of the layout page on the change of `V2-S5-003-PR2` | "went from 13 roles to 14" | No. It is history, and it is true |

**The reproduction.** At the base, the earlier test
`test_the_document_states_each_role_as_the_module_does` passed: it read the role
table alone. The new guard of this change, run at the base against the base pages,
fails with two findings:

```text
ExperimentRun page: no link to the role table
ExperimentRun page: states a count, '13\n  roles'
```

The count is found across the line break of the page.

## What changed

- [`docs/contracts/experiment-run.md`](../../contracts/experiment-run.md): the
  bullet links to the role table of the layout page and states no number of roles.
  A note in the bullet says that it stated a number until this change, and that
  the number was stale from `V2-S5-003-PR2`.
- [`tests/testing/test_experiment_evidence_layout.py`](../../../tests/testing/test_experiment_evidence_layout.py):
  the earlier role test is replaced by a guard and its controls. The suite has 244
  tests. The base had 218. (At the first commit it had 241.)
- [`docs/testing/experiment-evidence-layout.md`](../../testing/experiment-evidence-layout.md):
  one bullet says what the guard reads and refuses.
- [The test inventory](../../testing/test-inventory.md) and
  [its data](../../testing/test-inventory.v1alpha1.json): the `protects` text of
  the layout suite names the guard. The two files state the same text.
- [`CHANGELOG.md`](../../../CHANGELOG.md): one entry under "Fixed".
- [The proof index](../README.md): this record.

The module is not edited. No role is added, removed, or renamed.

## The guard

`ROLES` of the module is the source of the vocabulary. The guard compares it with
four places, and it reads no other place.

| Place | What the guard requires |
|---|---|
| The role table of the layout page | Exactly one section `## Roles: raw and derived`. Its table rows, read inside that section only, are the roles of the module, each with its kind and description, in the order of the module. A table line that is no row of the form is refused |
| The count row of the layout page | Exactly one row `\| Roles \| <total>: <raw> raw and <derived> derived \|`, with the three numbers of the module |
| The index of the testing pages | Exactly one phrase "the <total> roles of an evidence file", with the number of the module in digits |
| The ExperimentRun page | A link to `../testing/experiment-evidence-layout.md#roles-raw-and-derived`, and no number of roles in digits or in words from one to twenty, followed by "roles" or "role names", with up to three of the words "registered", "evidence", "evidence-file", "file", "layout", "raw", and "derived" between them |

The vocabulary is an argument of the guard. So a test can change the module's
vocabulary and keep the pages, and the guard then refuses the pages.

| Test | Count | What it drives |
|---|---:|---|
| `test_the_pages_state_the_role_vocabulary_as_the_module_does` | 1 | The committed pages and the committed module. No finding |
| `test_the_role_vocabulary_is_the_fourteen_registered_roles` | 1 | A tripwire. The 14 names in their order, the two derived roles, each kind `raw` or `derived`, and each name a lowercase DNS-label word sequence |
| `test_a_page_that_drifts_from_the_role_vocabulary_is_refused` | 19 | A row that is missing, extra, duplicate, renamed, reclassified, with a misspelled kind, with an unquoted name, or renamed onto another role; a count row with another total, another raw count, or no row; an index count in other digits or in words; a count in the ExperimentRun page as "13 roles", "fourteen registered roles", "13 evidence roles", "14 registered evidence roles", and "13 role names"; a link with no anchor |
| `test_a_role_table_out_of_the_order_of_the_module_is_refused` | 1 | The `analysis` row moved. The one finding is the order |
| `test_a_role_table_outside_its_section_is_not_read` | 1 | The section heading renamed. The table under it is not read |
| `test_a_vocabulary_that_drifts_from_the_pages_is_refused` | 4 | A role added to the module, removed, renamed, and moved from raw to derived, with the pages unchanged. Each case states the complete list of its findings |

Each control asserts the finding that it expects, not only that some finding
exists. (At the first commit the four cases of the last test did not: see
[the review](#the-independent-review).)

## What the guard does not do

- **It reads four places.** A new page that states the number of roles is not
  read. A review must find it.
- **It does not read the history.** The sentence of the layout page that says the
  vocabulary went from 13 roles to 14 is not read. It is true of the change that
  it names.
- **It does not read a validation record or the changelog.** The record of
  `V2-S5-002-PR2` states 13 roles, and so does the changelog entry of that change.
  Both were true at their revision. The record of `V2-S5-003-PR2` states the
  change from 13 to 14. None is edited.
- **The ExperimentRun check reads one form of a count.** A count in words above
  twenty, a count with a word between the number and the noun other than the
  seven that it lists, and a count stated in another form, such as "a vocabulary
  of 14" or "roles: 13", are not refused. The page links to the table so that it
  needs no count.
- **It decides nothing about the meaning of a role.** It compares names, kinds,
  and descriptions as text. It does not show that a file of a role holds what the
  description says.

## The fourteenth role is intentional

`operator-events` was added by `V2-S5-003-PR2` as a raw role, for the log that
[`tools/experiment_events`](../../../tools/experiment_events/core.py) writes. The
suite of that tool asserts that the role is registered and raw.
[The analysis replay](../../testing/analysis-replay.md) reads the file of the role
as one of its six inputs. The guard keeps the role. No published record states
that the role is invalid.

## The independent review

One reviewer read the first commit, `c037640`, against the base. It did not run
the default lane. It ran the role tests of the suite and probed the patterns in
memory. It reported no critical and no high finding. The second commit acts on
three of its four findings.

| Severity | Finding | What the first commit got wrong | Action |
|---|---|---|---|
| Medium | The pattern of the ExperimentRun check did not match "13 evidence roles", "thirteen evidence roles", or "13 role names". It matched only "registered", "raw", or "derived" between the number and "roles" | The defect was reported as "13 evidence roles", so the guard let the reported wording come back. The record listed "a vocabulary of 14" as not refused, and it did not list this form | The pattern takes up to three of seven words before "roles", and it takes "role names". Three controls are added. The limit is restated above |
| Low | The record described a second commit that did not exist yet | The `Commits` row stated the second commit as done | The row now names `c037640`, and this commit makes the second commit true |
| Low | The four cases of the module-vocabulary test asserted that some finding exists and two of the counts, and no finding of the table. "Renamed" would have passed on any one finding | The record said that each control asserts the finding that it expects | Each case now states its complete list of findings |
| Low | The table reader reads each table line of the role section, so a line of a second table in that section is read as a row | Nothing. The page and the record say that the section is read | None |

The reviewer found no other current page that states the number or the list of
the roles, no edit under `docs/proof/` other than this record and its row in the
proof index, and no private reference or path of a host in the change.

## Commands and results

Run from the repository root on the tree of the first commit. `P` is
`.venv/Scripts/python.exe`, Python 3.12.12 from the locked environment.

| Command | Result |
|---|---|
| `P -m pytest tests/testing/test_experiment_evidence_layout.py -q -k role`, before the page was corrected | Exit 1. Three failures: the guard on the committed pages, with the two findings of the reproduction; the control of the order, which requires no other finding; and the control that removes the anchor of the link, because the page had no link to change |
| The same command, after the page was corrected | Exit 0. 38 passed |
| The new suite run in a worktree at the base, `-k "role_vocabulary or drifts or out_of_the_order or outside_its_section"` | Exit 1. The two findings of the reproduction |
| The earlier role test, run at the base | Exit 0. 1 passed |
| `P -m pytest tests/testing/test_experiment_evidence_layout.py -q -rs` | Exit 0. 239 passed, 2 skipped. The two skips are of this host: no symbolic link, and no line break in a file name |
| `P -m pytest tests/testing/test_document_links.py tests/testing/test_test_inventory.py tests/contracts/test_experiment_run_v1alpha1.py tests/testing/test_experiment_evidence_layout.py -q` | Exit 0. 2,278 passed, 2 skipped |
| `uv run --locked ruff format --check .` | Exit 0. 747 files already formatted. The first run reformatted the new test code |
| `uv run --locked ruff check .` | Exit 0. All checks passed |
| `uv run --locked python -m mypy` | Exit 0. No issues in 414 source files |
| `P -m tools.ci_gates expected-failures` | Exit 0. 63 controls gave their required exit status |
| `P -m tools.evidence_index --check` | Exit 0. The committed index is what the register and ledgers produce |
| `P -m tools.evidence_index --gate` | Exit 0. The released pack recomputes to evidence set `1d40b33fd79d7b6436c35cfe1fc4ec943a8b82fc77ad1da7cd5d96bb2a5ac23a` and evidence pack `652e9051161d38e6dd2e77306a431bf96d863a262cc4b0dab15c0518ba920ad2` |
| `P -m tools.experiment_freeze --check` | Exit 0. 3 freeze records, every rule held |
| `P -m tools.experiment_evidence repository` | Exit 0. 3 pre-schema runs not checked, 0 conforming, 0 refused |
| `P -m tools.analysis_replay repository` | Exit 0. 3 pre-schema runs not replayed, 0 replayed, 0 refused |
| `P -m tools.generated_release --check`, `P -m tools.gitops_desired_state --check`, `P -m tools.baseline_profile --check`, `P -m tools.runtime_model_cache --check`, `P -m tools.service_endpoint_state --check` | Exit 0 each |
| `git diff --check` | Exit 0 |

**The default lane.** `uv run --locked python -m pytest -q` exited 0: 22,327
passed, 42 skipped, 14 deselected, in 43 min 45 s. It started before the first
commit, on a tree that differs from `c037640` only in the command table of this
record, which was written while the lane ran. The skips are not passes, and this
invocation did not print their reasons.

**The tree of the second commit.** The second commit changes the suite and this
record. It changes no page that the guard reads. The default lane was not run
again on it. These commands were run on it:

| Command | Result |
|---|---|
| `P -m pytest tests/testing/test_experiment_evidence_layout.py -q -k role` | Exit 0. 41 passed |
| `P -m pytest tests/testing/test_document_links.py tests/testing/test_test_inventory.py tests/contracts/test_experiment_run_v1alpha1.py tests/testing/test_experiment_evidence_layout.py -q` | Exit 0. 2,281 passed, 2 skipped. The two skips are the two of this host in the layout suite |
| `uv run --locked ruff format --check .`, `uv run --locked ruff check .`, `uv run --locked python -m mypy` | Exit 0 each. 748 files already formatted, one more than the first count: the formatter counts Markdown pages, and this record did not exist when the first count was taken; all checks passed; no issues in 414 source files |
| `git diff --check` | Exit 0 |

The hosted workflow result is not recorded here. It runs on the pull request.

## What did not change

- No role, rule, or code of `tools/experiment_evidence` changed.
- No ExperimentRun schema, fixture, or rule changed.
- No run directory, raw evidence file, freeze record, analysis, or correction
  changed.
- No claim, ledger, register row, dashboard row, or evidence-index entry changed.
  The released V1 evidence pack is unchanged.
- The validation records of `V2-S5-002-PR2` and `V2-S5-003-PR2` are not edited.
- No cluster, model, caller, or experiment run was used.
