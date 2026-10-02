# V2-S2-001-PR2 validation

Date: 2026-10-02

What this change checked before it was committed, and how. What it publishes is in
[the generated release](../../domain/helm-values-renderer.md#the-generated-release) and
[generated files and their digests](../../contracts/rendered-workload-release.md#generated-files-and-their-digests);
this page is about the checks run over the repository after the code, its suite, and the
documents were written.

The change executed nothing against a host: no cluster, runtime, or model was contacted,
and nothing was installed, provisioned, committed by the code, or published. The code
wrote files only under pytest's temporary directories and, for one smoke run, a scratch
directory outside the repository, and `helm template` ran locally,
reading committed files and the files a test had just written, and writing to standard
output only. Every check below is static, which is `C0` under
[the evidence levels](../../testing/evidence-levels.md). The suites are unit tests: they
are not a run of any frozen experiment, and no experiment result is recorded. The change
proves what is generated for the reference inputs and how it is written, and nothing about
a deployment. It adds no record to the evidence pack and moves no claim.

## Eligibility, checked before anything was written

- **What it builds on is merged.** `main` was at `6f784b6`, the merge of `V2-S2-001-PR1`,
  so the Helm values renderer, the render boundary and its refusals, the provenance
  input-trust policy, and the release domain were in place.
- **The gate and the pack.** `python -B -m tools.evidence_index --gate` exited 0 with
  `FROZEN` for `V1-S5-013-PR2`, `RELEASED v1.0.0` at `718ad2e0…` with the set `1d40b33f…`
  and the pack `652e9051…`, and `CURRENT` with the set `08d4868f…` and the pack
  `b958a724…`. None of the files this change touches is cited by a record.

## What changed

- **`src/inferops/domain/render/generation.py`** - `generate_release`, `GeneratedRelease`,
  the two file names and the release's header, and `release_text` and `values_text`.
- **`src/inferops/domain/render/writing.py`** - `write_release`, `staging_directory`, and
  `STAGING_SUFFIX`: the one module of the render package that touches a file.
- **`src/inferops/domain/release/canonical.py`** - `output_digest`, the decided rule for a
  generated file's digest, exported from the release package.
- **`src/inferops/domain/render/renderer.py`** - the half of `render_with` that calls the
  renderer and attaches the caller's request context is now a module-private helper, so
  `generate_release` reuses it rather than copying it. `render_with` behaves as before.
- **`src/inferops/domain/render/__init__.py`**, **`release/__init__.py`**, and
  **`release/provenance.py`** - exports, and docstrings that said the package writes
  nothing or that the values digest's rule belonged to a later story.
- **`tests/domain/test_generated_release.py`** and the golden release
  `tests/domain/fixtures/helm-values/support-assistant-local.rendered-workload-release.yaml`,
  in the directory `.gitattributes` already pins to LF; its comment now names the release.
- **Three existing suites** changed: the render package's import test now counts
  fourteen modules and lets `writing.py` alone add `os` and `pathlib`, and alone name
  `open`, with one new test that only the package index imports the writer; the
  architecture suite's "no module under the distribution opens a path" test exempts that
  one module by name, with one new test that it touches a file only inside a function;
  and the inventory's number words reach sixty.
- **Documents** - the [renderer page](../../domain/helm-values-renderer.md), with a new
  section on the generated release; the [release document](../../contracts/rendered-workload-release.md),
  with a new section on the digest rule and its open rules restated; and every page that
  said values are derived only in memory, that nothing writes a release, or that the
  values digest's rule was undecided - found by searching `src`, `docs`, `contracts`, the
  README, and the example indexes: the boundary page, the binding document, the contracts
  index, both example indexes, the README, and two architecture pages; the test
  inventory, including four sibling suites' notes; the secret-scanning allowlist; the
  proof index; and the changelog.

No schema, fixture under `contracts/`, chart file, template, ownership row, render rule,
category, code, or provenance policy changed.

## What the change was asked to reach, and what it reached

| Asked | Reached |
|---|---|
| Integrate generated values with RenderedWorkloadRelease | Yes: `generate_release` renders the values and records the release naming them, by file name and by the digest of the values file's bytes, from the same render context |
| Compute canonical digests for source contract, binding, values, and provenance using repository conventions | Yes. Contract and binding: the existing rule, the digest of the parsed value, unchanged. Values and the release file: decided here, the SHA-256 of the file's exact bytes, each file written in the canonical YAML form. The release identifier: the existing derivation, unchanged |
| Clean-output double-render and mutation tests | Yes: two generations into two clean directories, in two interpreters under two hash seeds, are the same bytes; nine one-at-a-time changes each move exactly their own values and release fields |
| Write to a caller-selected output directory atomically or leave recoverable output on failure | Both: the directory appears complete or not at all, and a write that cannot clean up leaves a named staging directory that blocks the next write until it is removed |
| Generated output is C0 until a real deployment executes | Stated on both pages and in the changelog; nothing was deployed |
| Story: identical inputs produce canonically identical values and provenance | Met for the reference inputs, at C0 |
| Story: generated values remain compatible with V1 synchronous real serving | Met statically, now for the written file: `helm template` over it and the hand-written file renders the V1 fixture with the contract's environment. Not shown on a cluster; a later change owns that |
| Story: manual values do not duplicate claim-relevant contract intent | Unchanged from `V2-S2-001-PR1`: met for the committed reference file, which a test checks. Nothing runs the check on a release's values |
| Story: generated files contain no secret values | Met for what this change generates: no string in either file is credential-shaped, a declared secret reference and a credential-shaped binding name are refused before anything is written, and gitleaks reports nothing for either golden file. The input-trust limit stands: a lowercase token with no published prefix, written as an identity, passes |
| Story: release IDs and digests are deterministic | Met for the reference inputs. One shape is measured rather than hidden: a platform-defaults change stated under the same revision moves the values digest and not the release identifier |

The parent story's acceptance is therefore met at C0 for everything reachable inside this
change. That the generated values serve a workload on a cluster is not reachable here.

## Decisions taken while writing, and what was left out on purpose

Each is on the renderer page or the release document with its reason; listed here so a
reviewer can disagree with one by name.

1. A generated file is hashed by its exact bytes; a source document stays hashed by its
   value. `output.helmValues.sha256` is what `sha256sum` prints for the values file.
2. The release is written as `rendered-workload-release.yaml`, beside
   `values.generated.yaml`, in the same canonical YAML form, under a fixed two-line header
   with no revision or date.
3. A generation reports the release file's digest, and it is not the digest of the
   release's canonical JSON: that one stays the form two releases are compared in.
4. The writer writes only into a directory that does not exist, stages in
   `.<name>.partial`, reads both files back, and renames once. It does not flush the
   parent directory.
5. The writer lives in the render package as its one file-system module, so nothing
   outside the package imports the boundary; the purity tests carve out that module
   alone.
6. `generate_release` takes the Helm values renderer only: the release records Helm
   values and nothing else.
7. **An architecture rule gains one named exemption.** Nothing under `src/inferops`
   opens a path, so the distribution works from a wheel with no file system, and an
   architecture test enforces it. `writing.py` is exempt by name, and a new test holds
   that it touches a file only inside a function a caller invokes. The alternative was a
   writer under `tools/`, which would wire the render boundary into a delivery path that
   another test says does not exist yet, and that a later change owns. An earlier change
   left a process memory metric unemitted rather than read a path for it; that reasoning
   stands, and this is the one exception to it. **This is the decision most worth a
   reviewer's disagreement.**
8. Left out: a command or workflow that generates a release, committing generated
   releases, checking a release directory after it is written, a defaults file, and any
   change to the chart, the schema, or the provenance policy.

**Left stale on purpose.** The claim register's limitation for
`deployment-values-derive-only-from-a-validated-document` still reads "Deployment rendering
does not exist", as `V2-S2-001-PR1` already disclosed, and the proof dashboard and the V1
evidence index carry the same sentence. The claim does not move - nothing installs
generated values and no record cites them - and an edit to the register is a ledger
operation that moves the current evidence digests, which this change has no record to
justify.

## What the checks caught before the first commit

Each was found by running the suites, the linters, or re-reading a test, and fixed before
anything was committed:

- **A refusal test that never reached the renderer.** The first draft refused the
  secret-reference example. That example serves `dev`, so on a local binding it was refused
  as `binding-not-found` before the renderer ran. The test now puts the example's references
  on the reference contract, and asserts the renderer's rule and field.
- **Two tests that could not fail on this host.** The tests that refuse an existing output
  directory passed with the writer's existence check deleted: on Windows a rename onto an
  existing directory fails anyway, so the refusal came from the rename, after staging. Both
  now record every file the writer starts and require none.
- **A wrong expectation about paths.** `pathlib` reads `<dir>/.` as `<dir>`, so the first
  draft's "unnamed directory" case was an existing directory. The test now says so, and
  checks a bare `.` and a `..` separately.
- **Two type errors** in the suite: it reached `os` through the writer module, and read a
  `rule_id` the release error's base type does not declare. Both now go through public
  names.
- **An architecture rule the first draft broke.** The first full lane failed one test:
  nothing under `src/inferops` may open a path, and the writer does. The first draft had
  carved the writer out of the render package's own purity tests and had not looked for a
  repository-wide rule. The exemption is now explicit, by name, with its own test and its
  reason on the renderer page and in the writer's docstring, and decision 7 above says
  what was weighed. Renaming the calls so the check could not see them was not
  considered a fix.
- **The suites' own counts.** The render package's import test failed at fourteen modules
  until it was updated, and the inventory's tests until the new module was registered.

## Checks that the new tests are not decorative

Eleven defects were planted, one at a time, in an archived copy of the working tree - every
tracked and new file, copied outside the repository - never in the tree itself. Each edited
file was compiled before the suites ran, and the copy's package and suite were confirmed to
be the ones imported. Four suites - the new one, the Helm values renderer's, the boundary's,
and the release domain's, 614 tests - ran in full against each. The copy passed all 614
before the first defect and again after the last was removed. Every defect was caught:

| Defect, exactly as made | Of 614 |
|---|---|
| `output_digest` hashes `data.replace(b"\r\n", b"\n")` | 1 failed |
| `GeneratedRelease` stops checking the recorded values digest: `if False and str(named.sha256) != ...` | 1 failed |
| `generate_release` records the digest of the values without their header | 41 failed |
| `generate_release` calls the renderer without the caller's request context | 1 failed |
| The writer's existence check becomes `if False and (...)` | 2 failed |
| The writer creates its staging directory with `exist_ok=True` | 2 failed |
| The writer's read-back becomes `if False and ...` | 1 failed |
| The writer's failure path becomes `pass` instead of removing what it staged | 6 failed |
| The writer returns before naming a staging directory it could not remove | 1 failed |
| `GeneratedRelease.files()` lists the release before the values | 1 failed |
| The release header gains a line `Generated 2026-10-02.` | 7 failed |

Six defects are caught by one test each. Those are the tests written for the property, and
the counts are stated so that nobody reads 52 new tests as 52 guards on each property. The
existence-check defect is caught only because of the fix above: before it, it was caught by
nothing on this host. The writer's change after this sweep - one paragraph of its docstring
- touched no code.

## Commands

Run from Git Bash on Windows, with the locked environment.

| Command | Result |
|---|---|
| `uv run --locked ruff check --no-cache .` | All checks passed |
| `uv run --locked ruff format --check --no-cache .` | 588 files already formatted |
| `uv run --locked mypy` | No issues in 323 source files |
| `uv run --locked python -m pytest tests/domain/test_generated_release.py tests/domain/test_helm_values_renderer.py tests/domain/test_renderer_refusals.py tests/domain/test_renderer_input_boundary.py tests/domain/test_provenance_input_trust.py tests/domain/test_rendered_workload_release_domain.py tests/contracts/test_rendered_workload_release_v1alpha1.py tests/architecture/test_domain_dependency_boundary.py tests/testing/test_test_inventory.py -q -p no:cacheprovider` | 2,413 passed: 52 in the new suite |
| `python -B -m tools.evidence_index --gate` | Exit 0; the six digests above, unchanged |
| `helm template`, helm 3.19.0, through the new suite | Byte-identical to the V1 fixture with the contract's environment, over the written file |
| `gitleaks dir <path> --config .gitleaks.toml --redact`, for every changed and new path, with gitleaks 8.30.1 - the version the workflow pins, its Windows build checked against the release's checksum list, which carries the workflow's pinned checksum for the Linux build | No leaks found in any of the 29 paths |
| `git diff --check main` | Exit 0, no output |

**The full default lane ran twice before the first commit**, with the new files registered
with Git so the link suite collected them:
`uv run --locked python -B -m pytest -q -rs -p no:cacheprovider --basetemp=<scratch>`. The
first gave 17,091 passed, **1 failed**, 33 skipped, 14 deselected, in 13 min 6 s: the
architecture rule above. After the exemption and its test, the second gave **17,093 passed,
33 skipped, 14 deselected, none failed**, in 11 min 56 s - the first run's passes, the test
that had failed, and the new one. The skips are the ones earlier records name, such as
symbolic links this host does not permit. This record's tables were filled after that run;
the record and link suites were run again over it.

## What the independent review found

A reviewer outside the change read the first commit, `c445471`, re-ran the linters, mypy,
and the nine targeted suites, recounted every figure in this record, probed the writer with
its own paths and interrupts, swept `src`, `docs`, `contracts`, the README, and the
changelog for sentences the change made false, and scanned the added lines for private
material. It found nothing it rated critical or high, two findings it rated medium, and
four low. Every figure it recounted was correct, the six-of-eleven count of single-test
catches included.

**Medium - `GeneratedRelease` accepted bytes that could change after its check.** Its
docstring, and the inventory, said an instance cannot hold files that disagree with its
objects. A `bytearray` equal to the canonical bytes passed the equality check; the
reviewer mutated one afterwards and `write_release` wrote the edited release without
complaint. **What the first commit got wrong** is that claim, which was false for any
caller passing a `bytearray`. *Fixed in code:* construction now requires both files as
immutable `bytes` and raises `TypeError` otherwise, and a test passes a `bytearray` for
each.

**Medium - the exemption's test proved less than three documents said.** The writer's
docstring, the renderer page, and decision 7 above said the architecture suite holds that
the writer touches a file only when called, never on import. The test looked only for
`open`, `read_text`, and `read_bytes`, so a module-level `mkdir`, `rename`, or `fsync`
was invisible to it, and it treated a function's decorators and default values - which run
on import - as inside the function. *Fixed in the test:* it now collects exactly what runs
on import - every module-level statement, class bodies included, and every function's
decorators and defaults - and refuses any of twenty-two file-system names or `open` there;
five more cases show it finds a read, a `mkdir`, a default value, a decorator, and a class
body that touch a file. The three documents now say what the test proves.

**Low.** The release examples' index still gave "no release has been recorded for values a
renderer produced" as the reason the fixtures carry placeholder digests; it now says they
were written by hand before anything generated a release, and points at the one generated
release, a test's golden file. The test that only the package index imports the writer saw
`from .writing import ...` and not `from . import writing`; it now sees both. And an
interrupt arriving after the rename had moved a complete release into place made the writer
try to remove a staging directory that no longer existed, and note on the error that an
incomplete release was left behind; it now leaves a renamed release alone, and a test
interrupts at exactly that point.

**Noted, not changed.** The read-back reads through the operating system's cache after the
flush, so it catches a short or failed write, not corruption on the device; the documents
claim no more.

Three defects were then planted against the fixes, in a fresh archived copy, with the
three suites they touch - 351 tests - run against each: the `bytes` check removed, the
renamed-release guard removed, and a module-level `Path(".").exists()` added to the writer.
Each was caught by one test, and the copy passed all 351 before and after.

**Run again after the fixes:** `ruff check`, `ruff format --check --no-cache`, `mypy`, the
targeted suites, the gate, gitleaks over every path changed since `6f784b6`, `git diff
--check`, and the full default lane, with the results below.

| Command, after the fixes | Result |
|---|---|
| `uv run --locked ruff check --no-cache .` | All checks passed |
| `uv run --locked ruff format --check --no-cache .` | 588 files already formatted |
| `uv run --locked mypy` | No issues in 323 source files |
| The nine targeted suites, the command above | 2,420 passed: the 2,413 before, the two new tests in the new suite, now 54, and the five new cases in the architecture suite |
| `python -B -m tools.evidence_index --gate` | Exit 0; the digests above, unchanged |
| gitleaks 8.30.1 over every path changed since `6f784b6` | No leaks found in any of the 29 paths |
| `git diff --check main` | Exit 0, no output |
| The full default lane, the command above | **17,100 passed, 33 skipped, 14 deselected, none failed**, in 8 min 17 s: the 17,093 before and the same seven new tests |

This record's table was filled after that run; the record and link suites were run again
over it.

## Privacy and publicability

The diff was read for private planning material, local paths, and credentials. It names no
private planning document or repository, no local filesystem path, no host or account
name, and no later story identifier. The one credential-shaped string in the new suite is a
binding named `sk-local-kind` - a published prefix followed by an ordinary binding name -
which the secret-scanning allowlist now lists; it is not a credential or the length of one,
and gitleaks reports nothing for the file. The golden release carries two placeholder
revisions, the suite's own, and three digests computed from committed files.

## What this does not establish

That a generated release installs, becomes ready, or serves a request on any cluster; that
a release was installed with generated values; that a written release directory is still
what was written once the writer returns; that a platform-defaults change is ever reflected
in a release identifier while the defaults are named only by a stated revision; that a
hand-written value the check does not cover is safe; that an identifier an author chose is
not a secret written to look like one; or anything about the mock profile, which the
renderer does not take.

## Pre-merge correction, 2026-10-02

Added before merge, by the correction commit that follows `1864c7e` on the same branch and
pull request. **Nothing above this heading was changed**: the acceptance table, the
decisions, "Left stale on purpose", and the review section are this change's first pass
as it was pushed, and this section says where they were wrong. A commit cannot name
itself, so this section names the commit before it; the correction commit's identifier and
its hosted run are on the pull request.

A pre-merge review of the first pass against the parent story found four gaps, and asked
for the writer's exemption to be weighed again. Each is below with why it mattered, what
changed, the tests that hold it, and what was left open on purpose.

### What the first pass got wrong

- It reported **"generated files contain no secret values" as met** for what the change
  generates. As worded, the criterion is absolute, and no check here can meet it: the first
  pass itself recorded that a lowercase token with no published prefix, written as an
  identity, passes. A criterion met with an exception is not met as written - the same
  error `V2-S1-004` corrected for provenance.
- It reported the **manual-values criterion as met for the committed reference file**. That
  was one file passing one function: no boundary applied the check, the V1 comparison
  loaded the hand-written file around it, and a new hand-written file would have been
  checked by nothing.
- It **left a claim limitation it knew to be false** - "Deployment rendering does not
  exist" for `deployment-values-derive-only-from-a-validated-document` - because a register
  edit moves the current evidence digests. That put a digest ahead of a true statement. The
  pack `main` holds is expected to move when a current statement changes; the pack a
  release was cut over is the one that must not, and the tooling checks that.
- It measured the **platform-defaults gap** but named it "a defaults change under the same
  revision", which reads as a property of the defaults rather than of a caller asserting a
  revision it did not use, and did not say what a release does and does not prove.
- The writer's docstring and the renderer page said that after a power loss the staging
  directory **"holds both complete files"**. Only the files' bytes are flushed; no
  directory is, so after a crash it may hold both, one, or none.

### A. The secret criterion, bounded

**Why it mattered.** A reader of "met" would take generated files to be proven free of
secrets. The code cannot prove that for names an author chooses, and the first pass had
already measured one that passes.

**Correction.** [The renderer page](../../domain/helm-values-renderer.md#what-a-generated-file-can-carry)
gains "What a generated file can carry", and [the release
document](../../contracts/rendered-workload-release.md#generated-files-and-their-digests) a
paragraph, both in the input-trust vocabulary: **generated release artifacts expose no
supported secret-bearing field or secret reference; every string in them comes from a field
the renderer's disposition table or the provenance policy owns; a known credential shape
is refused, and not quoted; an arbitrary secret disguised as an otherwise valid public
identifier remains the input-trust limitation.** The merged `V2-S2-001-PR1` record keeps its
row and gains a dated "Later correction". No prefix was added to the credential rule.

**Tests**, in `tests/domain/test_generated_release.py`:

- `test_each_file_holds_exactly_the_fields_its_published_table_names` - both files' leaves
  equal the disposition table's chart values and the provenance table's fields;
- `test_input_content_no_row_names_reaches_neither_file` - five markers planted in real
  inputs, in the contract's description and annotations and the binding's owner, GitOps
  path, and namespace, reach neither file;
- `test_a_credential_shaped_value_is_refused_without_being_quoted` - a contract owner
  beginning `glpat-`, refused under `render-value-credential-shaped`, unquoted;
- `test_the_golden_files_are_not_exempt_from_secret_scanning` - no path exception in
  `.gitleaks.toml` covers either golden file;
- `test_a_secret_written_as_an_ordinary_lowercase_name_passes` - the limitation, measured,
  and not claimed away;
- `test_the_pages_claim_the_bounded_secret_property_and_not_the_absolute_one` and
  `test_the_merged_pr1_record_keeps_its_rows_and_adds_a_dated_correction`.

Already present and unchanged: a declared secret reference is refused with nothing to
write, a credential-shaped binding name is refused unquoted, `security.secretRefs` is
written empty, and no string in either file is credential-shaped.

**Left open.** The literal criterion is not met as worded, and cannot be by syntax. Closing
it needs the criterion restated as the bounded property where it is defined, which is not
in this repository.

### B. Manual-value ownership, enforced at a boundary

**Why it mattered.** Helm lets the last values file win. Without a boundary, a second
hand-written file could set a contract-owned value beside the generated one and nothing in
the repository would refuse it.

**Correction.** `admit_manual_values(generated, manual, *, context)` in
[`helm_values`](../../../src/inferops/domain/render/helm_values.py) pairs generated values
with a hand-written document only when `manual_value_findings` finds nothing, and otherwise
raises `RenderRefused` with every `render-manual-value-generated` finding, each naming the
path and never the value, with the request context. The pair, `AdmittedHelmValues`, holds
the hand-written half read-only and runs the check again when built. `MANUAL_VALUES_SUFFIX`,
`.manual-values.yaml`, names a supported hand-written file. Both V1 comparison layers - the
schema merge and `helm template` - and the written-file `helm template` test now consume the
admitted pair: Helm is given the admitted document, written out, not the file beside it.
No Helm precedence, chart file, or ownership row changed.

**Tests**, in `tests/domain/test_helm_values_renderer.py`:

- `test_every_supported_hand_written_file_in_the_repository_is_admitted` - walks the
  repository for the suffix rather than reading a list;
- `test_a_new_supported_file_that_repeats_contract_intent_fails_the_search` - a temporary
  tree holding such a file, a sibling-only one, one named otherwise, and one under `.venv`:
  only the first is reported, by path and field;
- `test_admission_refuses_a_hand_written_file_that_sets_replaces_or_removes_a_generated_value`,
  with seven cases: a generated scalar set; a child beneath one; a parent replaced by a
  scalar, a list, and a `null`; a generated value removed with `null`; two at once;
- `test_admission_accepts_a_sibling_and_an_empty_mapping_above_a_generated_value` - five
  cases, the empty mapping per the existing rule;
- `test_an_admission_refusal_names_the_path_and_never_the_value` and
  `test_an_admitted_pair_holds_what_was_checked_and_cannot_be_built_around_it`.

**Scope enforced.** Every file in the repository whose name ends `.manual-values.yaml`,
outside version control, tool caches, build output, and local machine state - one today -
and any document a caller passes to `admit_manual_values`. **Not controlled:** a values file
named otherwise, one outside the repository, or `--set` on Helm's command line. No supported
path installs generated values yet; the path that does is where those would have to be
refused.

### C. The stale claim limitation, corrected

**Why it mattered.** The register, the proof dashboard, and the evidence index all told a
reader that deployment rendering does not exist, after two changes had built it.

**Correction.** A sixth ledger of register changes, the second after the release,
[`v2-s2-001-pr2-claim-reconciliation.v1alpha1.json`](../testing/v2-s2-001-pr2-claim-reconciliation.v1alpha1.json),
makes two changes, each with its value before and after and a finding: `c01` replaces the
claim's limitation, and `c02` replaces the evidence index's reason in the register, which
named five ledgers. The claim's status stays **planned**, `assertsRealBehaviour` stays
false, it cites no record, and nothing is promoted. The limitation now reads:

> Deterministic deployment-value rendering exists, checked statically at C0: validated,
> typed inputs render the chart's values, and a RenderedWorkloadRelease binds the
> generated values file to the digests and revisions of what it was rendered from. No
> supported deployment or GitOps path consumes the generated files yet, so no executed
> release shows deployment values derived only from a validated document. The
> platform-defaults revision a release records is the one its caller states: nothing yet
> reconstructs the defaults from a committed source bound to that revision, so defaults
> content changed under the same stated revision changes the values and not the release
> identifier. A hand-written values file is checked against the generated values only
> when it is one the repository supports, one named with the .manual-values.yaml suffix;
> any other values file given to Helm is not checked.

The evidence index learnt to undo every post-release ledger: `POST_RELEASE_LEDGER_PATHS`
lists them, the released pack undoes both, last first, and refuses a later one that states a
release, and the summary counts both ledgers' changes. Seven test modules that rebuild the
released register now undo both, and a test shows that undoing the first alone is refused.
The index and the dashboard were regenerated with their own tools; the index page, the
matrix page, the proof index, and the changelog say so.

**Digests.**

| Pack | Before | After |
|---|---|---|
| Released `v1.0.0`, evidence set | `1d40b33fd79d7b6436c35cfe1fc4ec943a8b82fc77ad1da7cd5d96bb2a5ac23a` | unchanged |
| Released `v1.0.0`, evidence pack | `652e9051161d38e6dd2e77306a431bf96d863a262cc4b0dab15c0518ba920ad2` | unchanged |
| Current, evidence set | `08d4868fcf4c320961d2937b5369dc9846ca4f0455e2f60375c1decfbdab23df` | unchanged |
| Current, evidence pack | `b958a7244cb6aab924615ff099112435d1e3d527ea348b66ec7ae3e8fd1c8532` | `0c2f2508c0dd96fb97540fc2a20110d558f0f88096a8b3ad97857b1b32a6b807` |

The current pack moved because it covers the register and every ledger, and both changed;
the evidence set covers only cited files, and none changed. The released pair is not
copied: the index recomputes it by undoing both post-release ledgers and refuses a result
other than the pair written once for the tag. No tag, release, or released file was touched.

**Tests**, in `tests/testing/test_evidence_post_release.py`: the reconciliation ledger
follows the post-release one and states no release, freeze, or blocker; it changes one
limitation and one surface reason and nothing else; every finding is answered by changes
that exist; the claim stays planned with no record in both the current and the released
register; the limitation says what exists and what does not; the released register cannot
be rebuilt without it; and the index builder refuses a later ledger stating a release and a
reconciled limitation edited without a ledger.

### D. The platform-defaults provenance limitation

**Why it mattered.** A release names its platform defaults by a revision, and a reader
could take that revision as proof of the defaults' content. It is not.

**Correction.** The test is renamed
`test_defaults_content_changed_under_a_falsely_retained_revision_moves_the_values_digest_and_not_the_release_id`,
and asserts the values' bytes and digest differ, the recorded revision is the same and is
the stated one, and the release identifier is the same. Its docstring says not to turn it
into an equality. The renderer page now says what it means: **a RenderedWorkloadRelease
records the asserted platform-defaults revision; this change does not prove that the
defaults it was rendered from were reconstructed from that revision.** The downstream
requirement is carried where the repository already carries a claim's open conditions: the
limitation above, which the dashboard and the index show. The register's
`recordedCoverageGaps` was not used, because it means a claim no test module covers, which
is not this.

**Left open.** Reconstructing the defaults from a committed source bound to the revision a
release records. That needs a defaults source this repository does not have, and belongs to
a later change.

### The writer's exemption, weighed again

Re-read against the architecture rules, the exemption holds and is kept:

- nothing it runs on import touches the file system - module-level statements, class
  bodies, decorators, and default values are all checked by the architecture suite, which
  passes;
- no other domain module gained file access: `helm_values` gained a function and a class
  that read nothing, and the repository-wide rule still holds every module but `writing`;
- generation stays pure, and `writing` persists bytes `generate_release` already decided;
- `write_release` writes to a directory its caller names and does nothing else: no commit,
  no install, no delivery;
- both files or neither holds at the level of the directory for a running system and a
  process that fails or is killed, and the POSIX empty-directory race stays stated.

One sentence was wrong, and is fixed in the docstring and on the renderer page: neither
directory is flushed, so a crash can leave a staging directory with fewer than both files,
or, on a file system that does not order its metadata writes, an output directory without
both. The pages now say a release read after a crash is checked against its digests rather
than trusted because its directory exists.

### Acceptance after the correction

| Parent-story criterion | After the correction |
|---|---|
| Identical inputs produce canonically identical values and provenance | **Met** at C0, for the reference inputs |
| Generated values remain compatible with V1 synchronous real serving | **Met statically**, C0 only: the written values with the admitted hand-written file render the V1 fixture byte for byte with the contract's environment. Nothing ran on a cluster |
| Manual values do not duplicate claim-relevant contract intent | **Met for the supported scope**: every repository file named `*.manual-values.yaml`, and any document passed to `admit_manual_values`. Not for values files passed to Helm another way |
| Generated files contain no secret values | **Not met as worded**: the absolute property cannot be shown by syntax. The bounded property in A **is met**. The criterion needs restating where it is defined |
| Release IDs and digests are deterministic | **Met** for the reference inputs, with the measured limitation in D: the platform-defaults revision is asserted, not reconstructed |

### Checks that the new tests are not decorative

Six defects were planted in an archived copy of the corrected tree, never in it, with four
suites - the renderer, the generated release, the post-release ledgers, and the evidence
index; 619 tests that ran and 129 skipped, because the copy has no Git metadata or release
tag - run against each:

| Defect | Caught by |
|---|---|
| Admission skips the ownership check | 7 tests |
| An admitted pair is built without re-checking | 1 test |
| The admitted hand-written half is held by reference | 1 test |
| Admission drops the request context | 7 tests |
| A new supported file, `deploy/examples/new.manual-values.yaml`, repeats a generated value | 1 test |
| The reconciled limitation edited in the register without a ledger | The post-release suite, at collection |

The copy passed all 619 before and after. In this checkout the same four suites run 748
tests, none skipped.

### Commands, after the correction

| Command | Result |
|---|---|
| `uv run --locked ruff check --no-cache .` | All checks passed |
| `uv run --locked ruff format --check --no-cache .` | 588 files already formatted |
| `uv run --locked mypy` | No issues in 323 source files |
| The targeted suites, listed below | 5,937 passed, none skipped, with helm 3.19.0 on `PATH` |
| `python -B -m tools.evidence_index --check` | OK: the committed index is what the register and the six ledgers produce |
| `python -B -m tools.evidence_index --gate` | Exit 0. Released: set `1d40b33f…`, pack `652e9051…`, unchanged. Current, after 9 post-release register changes: set `08d4868f…`, unchanged; pack `0c2f2508…` |
| `python -B -m tools.proof_dashboard --check` | OK: the committed page is what the register produces |
| gitleaks 8.30.1 over every path changed since `6f784b6` | No leaks found in any of the 49 paths |
| `git diff --check main` | Exit 0, no output |
| The full default lane, the command above | **17,134 passed, 33 skipped, 14 deselected, none failed**, in 11 min 57 s; the skips are the ones earlier records name |

The targeted suites: the generated release, the renderer, its refusals and input boundary,
provenance input trust, the release domain and schema, the architecture dependency boundary,
the post-release ledgers, the evidence index, the claim and evidence matrix, the proof
dashboard, the case study, the release, the test inventory, and the documentation links.
`helm template` ran inside the renderer and generated-release suites, with helm on `PATH`,
over the written values file and the admitted hand-written file; no cluster was contacted.

gitleaks reads the new ledger and this record's directory under the configuration's
wholesale `docs/proof/` exception (EX-03), so for those two files the scan is not evidence;
they were read by eye for credentials and private material, and hold none. The golden files
under `tests/domain/` are scanned.

This section's tables were filled after those runs; the record and link suites were run
again over it.

### Privacy and publicability, again

The correction's diff names no private planning document or repository, no local
filesystem path, no host or account name, and no later story identifier. Its two new
credential-shaped test values are built by joining a published prefix to an ordinary
phrase, and the secret-scanning allowlist lists both.
