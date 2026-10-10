# V2-S4-006-PR1 validation

Status: **the comparison of the single-runtime baseline with the two-replica
release now requires one usable API image digest from each side, and the two
must be equal. An absent digest, a malformed digest, and two digests that differ
each give `REFUSED`. This is static evidence at C0.** The digest is a declared
comparison input. It is not an install input, and it is not an observed runtime
identity. No cluster was read, no image was built or read, and no run installed
either side. No Application, procedure, chart file, contract, binding,
desired-state file, freeze record, or retained evidence file was changed, and no
claim was registered. An independent review found that the first commit stated
a digest as bound in a record where no description was compared with it, and
that several sentences said more than the repository shows: see
[what the independent review found](#what-the-independent-review-found).

> [!IMPORTANT]
> **This change corrects an omission of an earlier change, and the record says
> so.** [`V2-S4-005-PR1`](v2-s4-005-pr1-validation.md) made the comparison read
> the install inputs and the readiness inputs. Its validation record states that
> the API image identity was "Not reached", that the unresolved digest did not
> refuse the comparison, and that a text that is not a digest on both sides gave
> `COMPARABLE`. A second review of the sprint, on 2026-10-09, reported that as
> the remaining part of a defect of the comparison. It was reported to the
> author, and no file in this repository records that review. The earlier
> record is not edited.
>
> **A `COMPARABLE` record does not establish an installed identity.** It says
> that the committed inputs of the two sides are comparable, and that each side
> declares one digest. It does not say that a run installs either side with that
> digest, and no later preparation of an experiment may read it that way.

| Property | Value |
|---|---|
| Date | 2026-10-10 |
| Base | `77a057185a69ec82b3655991ffd8d5be91807da6`, the merge of pull request #134 |
| Branch | `fix/v2-s4-006-api-image-identity-comparison` |
| Commits | `0e47670d`: the declared comparison inputs, the two rules, the suite, and the pages. A second commit: the corrections of the independent review, and the default lane |
| Host | One Windows workstation, Git Bash (GNU bash 5.2.26); Python 3.12.12 from `uv` 0.9.16; Helm `v3.19.0` |
| Evidence level | C0. Every check reads committed files or renders them with the chart tool |
| Claim effect | None. No claim, ledger, register row, dashboard row, or evidence-index entry was added or changed |

## The defect, reproduced at the base

One driver ran the comparison on isolated copies of its inputs, in a second
working tree at the base commit and in the working tree of this change. A case
copies the inputs with the copy function of the comparator suite of its tree,
edits the copy in one way, and runs two commands on it:

```sh
python -B -m tools.baseline_profile --record --root <case-copy>
python -B -m tools.baseline_profile --check --root <case-copy>
```

No committed file was edited, and no cluster was read. The driver is
[`v2-s4-006-pr1-comparison-cases-driver.txt`](v2-s4-006-pr1-comparison-cases-driver.txt).
Its output at the base is
[`v2-s4-006-pr1-comparison-cases-at-base.json`](v2-s4-006-pr1-comparison-cases-at-base.json),
and its output for this change is
[`v2-s4-006-pr1-comparison-cases.json`](v2-s4-006-pr1-comparison-cases.json).

**The five cases of the review.** Each edits the two install descriptions, as
the review did: the hand-written values of the Application's copy and of the
baseline's description.

| Case | At the base: result, `--record` exit | This change: result, `--record` exit | Rule that refuses in this change |
|---|---|---|---|
| The committed inputs | `COMPARABLE`, 0. The digest is listed as unresolved | `COMPARABLE`, 0. The digest is bound | None |
| Both descriptions state `abc` as the digest | `COMPARABLE`, 0. The digest is listed as unresolved | `REFUSED`, 5 | `baseline-api-image-digest-contradicted`, for each side |
| Both descriptions state `sha256:` and 64 `a` | `COMPARABLE`, 0 | `REFUSED`, 5 | `baseline-api-image-digest-contradicted`, for each side: the value is not the declared digest |
| The target's description alone states that digest | `REFUSED`, 5 | `REFUSED`, 5 | `baseline-install-differs`, `baseline-effective-values-differ`, and `baseline-api-image-digest-contradicted` for the target |
| The target's description alone states a readiness timeout of `1` | `REFUSED`, 5 | `REFUSED`, 5 | `baseline-install-differs` and `baseline-effective-values-differ` |

**The third case changed, and the reason is stated.** At the base, two
descriptions that state one syntactically valid digest gave `COMPARABLE`. In
this change the digest of each side is the one that the declared comparison
inputs state. A description that states another digest contradicts it, so the
case is refused. The positive control of this change is the committed inputs,
and two further cases: both descriptions state the declared digest
(`COMPARABLE`, exit 0), and the declared inputs state another valid digest for
both sides (`COMPARABLE`, exit 0).

**`--check` at the base.** In the second and third case at the base, `--check`
exits 1 for `baseline-record-stale` alone: the committed record no longer
states the hand-written values of the copy. The comparison itself held. In this
change `--check` exits 1 in each refused case and names the rule that refuses.
The driver output retains the exit status of `--check` and not its text. The
rule names of `--check` in this record were read from the command's output on
the same copies, and the suite asserts them for the cases that it runs through
the command.

## The representation of the digest

**How each side gave its digest before.** The tool read `/api/image/digest` of
the effective values of each side: the chart's defaults, then the generated
values, then the hand-written values of the side's description. The chart's
default is the empty text. The generated values state no API image. The
Application states no digest by design: no InferOps API image is published, so
the procedure that applies the Application adds the digest as one Helm
parameter. The baseline's description mirrors the Application. So neither side
stated a digest, and the tool listed it as unresolved and added no finding.

**What this change adds.** One hand-written file,
`tests/domain/fixtures/experiment-profiles/single-runtime-baseline.comparison-inputs.v1alpha1.yaml`,
states `apiImageDigest.baseline` and `apiImageDigest.target`. The tool reads
both, classifies each as `valid`, `absent`, `malformed`, or `not-read`, and
holds `baseline-api-image-digest-unbound` only for two valid, equal digests.

**Why a second file, and not the descriptions.** The Application must not state
the digest, and it is not edited. A digest in the baseline's description alone
is a one-sided hand-written value, which the comparison refuses, and a new
permitted difference would weaken it. A file that states both sides keeps the
two descriptions equal, keeps the Application as it is, and keeps the digest
apart from the install inputs.

**The category.** The digest of a record is a `declared-comparison-input`: a
value that a committed comparison input states. It is not an install input: the
procedure that applies the Application takes its digest from the operator and
does not read the file. It is not an observed runtime identity: the tool reads
no cluster. The record states the category and both exclusions under
`apiImageIdentity`.

**The usable form.** `sha256:` and 64 lowercase hexadecimal digits. The
procedure that applies the Application accepts that form for its digest
argument, and no stricter form exists in this repository. The tool already held
the expression; it now refuses with it.

**The origin of the committed value.** Both sides declare
`sha256:244251f76e5959c58e52689337298a24af46b34d8fd36b097cb638671eccda56`. A
cluster reported `localhost/inferops-api@` followed by that value as the
`imageID` of the two API pods of the target
in one retained read,
[`pods-before.json`](v2-s4-005-pr2-service-endpoint-state-run-1/pods-before.json)
of [the endpoint reading of 2026-10-09](v2-s4-005-pr2-validation.md). That
record states that the image was built on that host at the executing commit of
that run.

- In that read the value is an observed runtime identity of the target, on one
  provider, of one local build. Here it is copied by hand as a declared value.
- No run installed the baseline. The value was not observed for the baseline.
- No InferOps API image is published. Another build can have another digest,
  and nothing here compares two builds.
- The comparison does not establish that a later install uses the value. An
  operator who applies the Application gives the digest of the image on that
  host, and nothing compares that digest with the declared one.
- One test holds that the declared value is the one that the read reports. The
  retained read is not edited.

## What changed

- **One file is new:** the declared comparison inputs, named above. A person
  writes it. No Application and no procedure reads it.
- **`tools/baseline_profile` reads it.** Two rules are added, so a record states
  13: `baseline-api-image-digest-unbound` and
  `baseline-api-image-digest-contradicted`. The second holds that the effective
  values of a side state no digest, or the declared one of that side.
- **A record states `apiImageIdentity`:** the category, the source file, the
  usable form, the state of each side, whether the effective values were
  compared with it, each digest that the effective values state, whether the
  identity is bound, and the bound digest. The schema name
  of the record is unchanged. No reader of the record exists but the tool and
  its suite.
- **`unresolvedInputs` lists the digest only when it is not bound,** and such a
  record is `REFUSED`. The caller profile is listed in every record, and
  `experimentEligibility` is `not-established` in every record. Neither was
  changed.
- **Three limits replace one.** The record no longer says that no committed file
  states the digest. It says that the record does not establish an install with
  the declared digest, a pod of the declared image, or an image that exists.
- **The committed record is written again.** The committed baseline release, its
  two generated files, is the same bytes.
- **`--check` prints two more `OK` lines.** Its exit statuses are unchanged.
- **One test was wrong, and it is corrected.** It gave both descriptions the
  text `abc` and expected `COMPARABLE`. It now expects `REFUSED`, the exit
  status 5 of `--record`, and a refused write.
- **The baseline's install description** has a changed comment and no changed
  value.
- These pages state the change:
  [the baseline profile page](../../environment/single-runtime-baseline-profile.md),
  `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, the architecture index, the
  Application page, both test inventory files, and the proof index. This record
  and the three files of the driver are added.

## What the change was asked to reach, and what it reached

| Asked | Reached |
|---|---|
| Each side states an API image digest to the comparison, in a committed comparison input | Reached at C0. One committed file states one digest for each side |
| A digest is usable only in the canonical form | Reached at C0. 14 pairs in which both sides state one kind of value that is not a digest are each refused |
| An absent digest on either side is refused, with the refusal exit | Reached at C0: the baseline, the target, and both. `--record` exits 5 |
| A malformed digest on either side is refused | Reached at C0 |
| Two identical malformed texts are refused | Reached at C0, in the declared inputs and in the two descriptions |
| Two valid digests that differ are refused | Reached at C0 |
| Two valid equal digests satisfy the rule | Reached at C0, for the committed value and for one other value |
| `COMPARABLE` needs this rule and every other rule | Reached at C0. The result is `COMPARABLE` only when no rule has a finding, as before |
| The caller profile stays unresolved, and eligibility stays `not-established` | Reached. Neither statement is edited. The eligibility is one constant of the tool. The suite holds both statements in each refused case of the declared inputs: 7, 14, 3, and 10 cases. The driver output shows both in its 11 refused cases. The refused cases that edit a description do not assert them |
| The record does not state the digest as installed or observed | Reached, as statements. The record names the category and three limits. Nothing in this repository checks an installed or an observed digest against the declared one |
| The Application and the delivery are unchanged | Reached. No file under `infra/`, `scripts/`, `charts/`, or `gitops/` is in the diff |
| The retained endpoint evidence is unchanged and is not rerun | Reached. No file of that reading is in the diff, and no cluster command ran |

## Decisions taken in this change

**The declared inputs are one file for both sides.** The two digests must be
equal, so one file could have stated one value for both. Then a one-sided
absence and two different digests could not exist, and the comparison would
hold by construction. With one member for each side, each case is a state that
a person can write and that the tool refuses.

**A description that states a digest must state the declared one.** The tool
could have ignored the hand-written values. Then two descriptions that state
`abc` would be `COMPARABLE` beside a valid declared digest. The tool could have
let a description replace the declared digest. Then the Application would be a
second place for the value, which its design excludes. So a restated digest is
compared with the declared one, and another value is refused.

**A file that is not read whole is `not-read` for both sides, and not
`absent`.** A reader of the record can tell a file that states no digest from a
file that the tool refused. A file that parses and states no digest block gives
`absent` for both sides.

**A malformed value that is not a scalar is named by its kind.** A list or a
mapping is not printed, so a value that refers to itself cannot make the tool
fail.

**The committed value is held to its stated origin by a test.** The origin is
prose in the file and on the page. Without the test a later edit could change
the value and leave the prose. The test fails then, and its text says what the
edit owes. The tool does not read the retained read: an origin is not a rule of
the comparison.

**The schema name of the record is not changed.** One member is added, and
none is removed or renamed.

## The negative controls

Each is a test of `tests/domain/test_baseline_profile.py`, but for the one row
that is marked driver only. Each edits a copy of the inputs in a temporary
directory. The first seven rows, and the four rows on a description that state
exits, also ran through the driver, as two commands on an isolated copy. The
exits of the row for another valid digest in both descriptions are the
driver's alone: the test of that row asserts the record and no exit.

| Control | Result | `--record` exit | `--check` exit |
|---|---|---|---|
| The baseline's declared digest is absent | `REFUSED`: `baseline-api-image-digest-unbound` at `/apiImageDigest/baseline` | 5 | 1 |
| The target's declared digest is absent | `REFUSED`: the same rule at `/apiImageDigest/target` | 5 | 1 |
| Both declared digests are absent | `REFUSED`: the rule for each side | 5 | 1 |
| The baseline's declared digest is `abc` | `REFUSED`: the rule for the baseline | 5 | 1 |
| The target's declared digest is `abc` | `REFUSED`: the rule for the target | 5 | 1 |
| Both declared digests are `abc` | `REFUSED`: the rule for each side. Equality is not validity | 5 | 1 |
| Two valid declared digests that differ | `REFUSED`: the rule at `/apiImageDigest` | 5 | 1 |
| 14 more pairs in which both sides state one kind of value that is not a digest: an empty text, uppercase digits, 63 digits, 65 digits, no algorithm, another algorithm, an image reference, a trailing space, a trailing newline, a number, a boolean, a list, a mapping, and a value that refers to itself | `REFUSED`: `malformed` for each side | Not run through the command | Not run through the command |
| Two nulls, an empty digest block, and no digest block | `REFUSED`: `absent` for each side | Not run through the command | Not run through the command |
| Comparison inputs that are not read whole, in 10 forms: absent, not YAML, not text, empty, a key stated twice, another kind, another schema, another side, another member, and one digest for no side | `REFUSED`: one finding, and `not-read` for both sides | Not run through the command | Not run through the command |
| Both descriptions state `abc` | `REFUSED`: `baseline-api-image-digest-contradicted` for each side | 5 | 1 |
| Both descriptions state another valid digest | `REFUSED`: the same rule for each side | 5 | 1 |
| The baseline's description alone states a digest | `REFUSED`: `baseline-install-differs`, `baseline-effective-values-differ`, and `baseline-api-image-digest-contradicted` for the baseline | Not run through the command | Not run through the command |
| The target's description alone states a digest | `REFUSED`: the same three rules, for the target. Driver only: the suite plants the baseline's side | 5 | 1 |
| The target's description alone states a readiness timeout of `1` | `REFUSED`: `baseline-install-differs` and `baseline-effective-values-differ` | 5 | 1 |
| A malformed declared digest, and no derived release for the baseline | `REFUSED`: the digest rule is `not-held`, and the rule on the effective values is `not-evaluated` | Not run through the command | Not run through the command |
| Another digest in the target's description, and no description of the baseline | `REFUSED` for the description. The rule on the effective values is `not-evaluated`, and the record states the digest as not bound and as unresolved. Added after the review | Not run through the command | Not run through the command |
| A space, or the declared digest with a newline, in both descriptions | `REFUSED`: `baseline-api-image-digest-contradicted` for each side. Added after the review | Not run through the command | Not run through the command |

**Positive controls.**

| Control | Result | `--record` exit | `--check` exit |
|---|---|---|---|
| The committed inputs | `COMPARABLE`. The digest is bound | 0 | 0 |
| Both descriptions state the declared digest | `COMPARABLE` | 0 | 1, for `baseline-record-stale` alone |
| Another valid digest declared for both sides | `COMPARABLE` | 0 | 1, for `baseline-record-stale` alone |
| An empty text, or a null, as the digest in both descriptions | `COMPARABLE`: neither states a digest. The chart refuses to render an empty digest, and the tool renders nothing. Added after the review | Not run through the command | Not run through the command |

**A refusal and a stale record are two outcomes.** Exit status 5 of `--record`
is a refused comparison. Exit status 0 of `--check` is a current, comparable
committed record. In the last two rows the comparison holds and the committed
record is stale: `--record` exits 0 and `--check` exits 1.

## Validation at the first commit

Each command ran on the host of the table above, on the working tree of the
first commit.

| Command | Result |
|---|---|
| `uv run --locked ruff check .` | No finding |
| `uv run --locked ruff format --check .` | 689 files already formatted, with this record |
| `uv run --locked python -m mypy` | No issue in 375 source files |
| `uv run --locked python -m tools.baseline_profile --record` | Exit status 0, `COMPARABLE`. This is the comparison command on the committed inputs |
| `uv run --locked python -m tools.baseline_profile --check` | Exit status 0: six `OK` lines. This is the freshness check, and it is a separate outcome from a refusal |
| `uv run --locked python -m pytest tests/domain/test_baseline_profile.py -q` | 185 passed. The suite held 146 tests at the base |
| `uv run --locked python -m pytest tests/architecture/test_helm_chart.py -q -k baseline` | 3 passed, 267 deselected. `helm` is installed, so none skipped |
| `uv run --locked python -m pytest tests/architecture/test_helm_chart.py tests/architecture/test_argocd_bootstrap.py tests/architecture/test_argocd_application.py tests/domain/test_generated_release_drift.py tests/domain/test_renderer_input_boundary.py tests/domain/test_gitops_desired_state.py tests/domain/test_capacity_preflight.py tests/testing tests/security -q` | 10,110 passed, 7 skipped, and 1 failed. The failure was `test_a_second_process_from_another_checkout_aborts_the_run` of the first experiment's suite, which starts processes and judges them by time. Two other suites ran on the host at that moment. The test passed when it ran alone afterwards. No file that it reads is in the diff. The default lane below is the run that decides it |
| `uv run --locked python -m pytest tests/testing/test_document_links.py tests/testing/test_test_inventory.py tests/security -q`, after this record was written | 2,670 passed |
| `uv run --locked python -m tools.generated_release --check` | Exit status 0 |
| `uv run --locked python -m tools.gitops_desired_state --check` | Exit status 0 |
| `uv run --locked python -m tools.capacity_preflight --check` | `PASSED: 8 committed collection(s)` |
| `uv run --locked python -m tools.runtime_model_cache --check` | `PASSED: 1 committed run(s)` |
| `uv run --locked python -m tools.service_endpoint_state --check` | `PASSED: 8 committed collection(s)` |
| `uv run --locked python -m tools.experiment_freeze --check` | `PASSED: 3 freeze record(s), every rule held` |
| `uv run --locked python -m tools.experiment_e01 --check` | `PASSED: 2 run(s), each agrees with its own evidence` |
| `uv run --locked python -m tools.evidence_index --check` and `--gate` | Exit status 0 for each |
| `uv run --locked python -m tools.proof_dashboard --check` | Exit status 0 |
| `uv run --locked python -m tools.experiment_freeze --changes docs/proof/experiments/v2-e01/freeze-r3.v1alpha1.json` | Exit status 1, as at the base: 30 material files differ from revision 3. The output is the same text before and after this change |
| `helm lint charts/inferops-llm --strict --namespace inferops-platform --values charts/inferops-llm/ci/real-values.yaml`, and the same with `mock-values.yaml` | `1 chart(s) linted, 0 chart(s) failed` for each |
| The driver, in a second working tree at the base and in this working tree | 5 cases at the base and 14 cases here, with the results of the tables above |
| `git diff --check` against the base | No whitespace error |

**Not run at the first commit.** The default lane. `gitleaks` is not installed on this host, so no secret scan
ran. Hosted CI was not read: no pull request existed. No cluster command ran,
because the change reads no cluster.

## What the independent review found

Two reviews read the first commit, `0e47670d`, without the author's account of
it. One read the tool and the suite and tried to obtain `COMPARABLE` with a
digest that is absent, malformed, unequal, or contradicted. One read each
sentence and each number of the pages and of this record against the code, the
suite, and the driver output. Neither obtained `COMPARABLE` or exit status 0
with such a digest. Both found the first defect below.

### What the tool got wrong

- **A record stated the digest as bound when no description was compared with
  it.** `bound` was true whenever the function had no finding. When a
  description is not read whole, no effective values exist, and the rule on
  them is `not-evaluated`. A copy whose Application stated another digest, and
  whose baseline description was absent, gave `bound: true`, a bound digest,
  and no `api-image-digest` under `unresolvedInputs`. The result was `REFUSED`
  for the description, so no comparison passed. The record still said more
  than the tool had checked, and one test of the first commit asserted it.
  `bound` is now true only when the effective values of both sides were
  compared. The record states `effectiveValuesCompared`, and it lists the
  digest as unresolved when they were not. The test is corrected, and one test
  plants the case.

### What the first commit said, and what is true

| The first commit said | What is true |
|---|---|
| "No committed file stated an API image digest", in the changelog and on the page | Six committed files of the endpoint reading stated this digest for the target. No committed input of the comparison stated one. Both sentences now say that |
| "Another build has another digest", in four places | Nothing in this repository compares two builds. Each place now says that another build can have another digest |
| "A cluster reported that value as the `imageID`", in three places | The cluster reported `localhost/inferops-api@` followed by the value. The suite classifies that whole text as malformed. Each place now says what was reported |
| "A test holds both in each refused case", of the caller profile and the eligibility | One test held both, in 7 cases. The tests of the declared inputs now hold both in 34 cases, and the row states which cases do not |
| "Each is a test … The first seven also ran through the driver" | One row is driver only, 11 rows ran through the driver, and the exits of one row are the driver's alone. The paragraph now says that |
| The rule names of `--check` in the base cases, with no source | The driver output retains exit statuses only. The record now says where the rule names were read |
| A record that is not bound lists "the sides that state no usable digest" | It lists both sides when both are valid and the identity is not bound. The page now says that |
| "It is not the digest that an operator installs with", in `README.md` and on the Application page | In the reading of 2026-10-09 the same value was the install input of that run. The category is about what reads the file, so both now say that no install procedure reads it |
| "13 more pairs of equal values" | The pair that refers to itself is two values of one shape under two anchor names, and one more pair was added. The record now says 14 pairs of one kind of value |
| "`--check` fails in two ways", in `CONTRIBUTING.md`, above four entries | The sentence now names the two kinds of failure |
| "This file reads no cluster", in the comparison inputs | A file reads nothing. The comment now says that no cluster is read to write or to check it |
| "A second commit follows the independent review", in this record at the first commit | That was a prediction. The row now names both commits |

### Stale text that the first commit left

Two docstrings of `tests/architecture/test_helm_chart.py` said that no committed
file states the API image digest. The comparison inputs now state one. Both
docstrings are corrected. No statement and no assertion of that module is
changed.

### Noted, and not changed

- **An empty text, or a null, as the digest in both descriptions is
  `COMPARABLE`.** An empty text is the chart's default, and a null removes the
  member, so neither states a digest. The chart refuses to render such a
  release. The tool renders nothing, so it does not report that. Two tests now
  hold the behaviour, and the page states the limit.
- **A symbolic link in a parent directory of the comparison inputs** is not
  refused. The tool checks the file itself. The two descriptions are read in
  the same way, and this host cannot create a symbolic link to plant the case.
- **The earlier review of the sprint is not a file of this repository.** The
  note at the top says so. A reader cannot verify that sentence here.

## Validation at the second commit

Each command ran on the working tree of the second commit.

| Command | Result |
|---|---|
| `uv run --locked ruff check .` | No finding |
| `uv run --locked ruff format --check .` | 689 files already formatted |
| `uv run --locked python -m mypy` | No issue in 375 source files |
| `uv run --locked python -m tools.baseline_profile --record` | Exit status 0, `COMPARABLE` |
| `uv run --locked python -m tools.baseline_profile --check` | Exit status 0: six `OK` lines |
| `uv run --locked python -m pytest tests/domain/test_baseline_profile.py --collect-only -q` | 191 tests. The first commit held 185. They ran in the default lane below |
| `uv run --locked python -m tools.generated_release --check`, `tools.gitops_desired_state --check`, `tools.capacity_preflight --check`, `tools.runtime_model_cache --check`, `tools.service_endpoint_state --check`, `tools.experiment_freeze --check`, `tools.experiment_e01 --check`, `tools.proof_dashboard --check`, `tools.evidence_index --check`, and `tools.evidence_index --gate` | Exit status 0 for each |
| `uv run --locked python -m tools.experiment_freeze --changes docs/proof/experiments/v2-e01/freeze-r3.v1alpha1.json` | 30 material files differ, as at the base. The output is the same text as before this change |
| `helm lint charts/inferops-llm --strict --namespace inferops-platform --values charts/inferops-llm/ci/real-values.yaml`, and the same with `mock-values.yaml` | `1 chart(s) linted, 0 chart(s) failed` for each |
| The driver, in this working tree | 14 cases. The output is the same bytes as the committed output of the first commit, but for line endings |
| `git diff --check` against the base | No whitespace error |

## The default lane

`uv run --locked python -m pytest -q` ran once, on the working tree of the
second commit before this section and the table above were filled in: 20,101
passed, 37 skipped, and 14 deselected, in 38 minutes. No test failed. The lane
holds the Helm lane too: `helm` is installed, so the 270 tests of the chart
suite ran, the three render tests of the baseline among them.

The test of the first experiment's suite that failed once at the first commit,
beside two other suites, passed in this run.

The lane skipped 37 tests, for four kinds of reason: a fixture that a schema
layer does not apply to, a symbolic link that this host cannot create, a POSIX
signal that this host does not deliver, and the freeze test that skips after
the desired-state release moved from revision 3. The earlier changes of this
sprint record the same count on this host.

This section and the table above are the one edit after that run. They change
this page only. The link suite and the publication suite ran again for this
page afterwards.

**Not run.** `gitleaks` is not installed on this host, so no secret scan ran.
Hosted CI was not read: no pull request existed. No cluster command ran,
because the change reads no cluster.

## What stayed as it was

The comparison is `git diff --stat 77a057185a69ec82b3655991ffd8d5be91807da6`,
read for each path below.

- **Released V1 evidence and history.** No file under a released path is in the
  diff. `tools.evidence_index --gate` passes, and it reports the same evidence
  set and evidence pack digests as at the base.
- **Sprint 3 evidence, and the first experiment.** No freeze record, run, review
  record, or ledger of V2-E01 is in the diff. `tools.experiment_freeze --check`
  and `tools.experiment_e01 --check` pass. The list of
  `tools.experiment_freeze --changes` for revision 3 is the same 30 files before
  and after this change, compared as text: no pinned file moved.
- **The retained endpoint reading.** No file under
  `docs/proof/environment/v2-s4-005-pr2-*` is in the diff.
  `tools.service_endpoint_state --check` passes. One test of this change reads
  `pods-before.json` of that reading, and it writes nothing.
- **The other evidence of this sprint.** The model cache run, the capacity
  readings, and the endpoint-state cases are not in the diff, and each check of
  them passes.
- **The earlier validation records of the baseline.** Neither is edited.
- **The Application, the project, the procedure, and the chart.** None is
  edited.
- **The Helm render tests.** Two docstrings of
  `tests/architecture/test_helm_chart.py` are corrected, and no code of that
  module is edited. Its three baseline tests render each side with one placeholder digest,
  and they do not read the declared inputs.

## Privacy and publicability

The diff was read for private material.

- The declared comparison inputs hold one image digest. It is already in the
  committed files of the endpoint reading.
- The output of the driver names each copy as `<case-copy>`, and the driver
  asserts that no path of the host is in it.
- No credential, secret value, cloud account identifier, model artifact, or path
  of the workstation is in the diff. A refusal names a file under the
  repository root, and a test holds that no record states the path of a copy.
- No planning text, prompt, or identifier of a later change is in the diff.

## What this does not establish

- That a run installs either release with the declared API image digest. The
  procedure that applies the Application takes its digest from the operator.
- That a cluster ran a pod of the declared API image for the baseline. No run
  installed the baseline.
- That the declared digest names an image that exists on a host today, or the
  image that a build of this tree gives.
- That the baseline is eligible for an experiment. Every record states the
  eligibility as `not-established`, and no caller profile exists.
- Anything about a caller, a pod loss, availability, latency, or cost. Nothing
  ran.
- That the defect of the comparison is closed. A review of the sprint decides
  that, after this change merges. That review and the approval that follows it
  are outside this change, and both are pending.
