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
