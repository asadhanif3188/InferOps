# V2-S2-002-PR1 validation

Date: 2026-10-02

What this change checked before it was committed, and how. What it publishes is in
[Verifying a committed release](../../domain/helm-values-renderer.md#verifying-a-committed-release);
this page is about the checks run over the repository after the code, its suite, and the
documents were written.

The change executed nothing against a host: no cluster, runtime, registry, or model was
contacted, and nothing was installed, provisioned, or published. The code wrote files
only under pytest's temporary directories, and the defect sweep below wrote only to a
copy of the working tree outside the repository. Every check below is static, which is
`C0` under [the evidence levels](../../testing/evidence-levels.md). The suites are unit
tests. They are not a run of any frozen experiment, and no experiment result is recorded.
The change adds no record to the evidence pack and moves no claim.

## Eligibility, checked before anything was written

- **What it builds on is merged.** `main` was at `1bc85ed`, the merge of `V2-S2-001-PR2`,
  so `generate_release`, `write_release`, the digest rule for generated files, and the
  reference release's golden files were in place.
- **The gate and the pack.** `python -B -m tools.evidence_index --gate` exited 0 with
  `FROZEN` for `V1-S5-013-PR2`, `RELEASED v1.0.0` at `718ad2e0…` with the set `1d40b33f…`
  and the pack `652e9051…`, and `CURRENT` with the set `08d4868f…` and the pack
  `0c2f2508…`. It reported the same five values after the change: none of the files this
  change touches is cited by a record.

## What changed

- **`tools/generated_release/`** - a new tool. `core.py` holds `DECLARED_RELEASES`, the
  committed release directories and the inputs each is derived from; `derive`, which
  builds both files again through `generate_release`; `verify`, which compares them with
  the committed files under eight rules; and `regenerate`, which replaces a named release
  through `write_release`. `__main__.py` is the command: `--list`, `--check`, and
  `--write NAME`.
- **The reference release moved**, with its bytes unchanged, from two golden files named
  `support-assistant-local.*` to the directory
  `tests/domain/fixtures/helm-values/support-assistant-local-kind/`, in the layout
  `write_release` produces. `.gitattributes` already pinned that tree to LF. The two
  suites that read the golden files point at the new paths.
- **`tests/domain/test_generated_release_drift.py`** - the new suite: 57 tests in the
  first commit, 70 after the review fixes below.
- **`tests/domain/test_renderer_input_boundary.py`** - the test that no tool imports the
  render package now exempts `tools/generated_release` by name and requires the exemption
  to be used. A new test reads every tracked file under `src`, `tools`, `scripts`,
  `charts`, `deploy`, `infra`, and `.github`, and `pyproject.toml`, and fails if any
  outside the drift check names `generated_release` as a whole word. The first commit's
  version of that test was narrower; see [the review](#what-the-independent-review-found).
- **Documents** - the [renderer page](../../domain/helm-values-renderer.md), with a new
  section on verifying a committed release and its open rows restated; the [release
  document](../../contracts/rendered-workload-release.md), whose "not applied yet" table
  lost the row the check applies and restates two others; the [boundary
  page](../../domain/renderer-input-boundary.md), for the exemption;
  [CONTRIBUTING](../../../CONTRIBUTING.md), with the verify and regenerate workflow; the
  test inventory, with the new module; and the changelog.

## What the change was asked to reach, and what it reached

| Asked | Reached |
|---|---|
| A command or test derives the expected generated release from committed source inputs and compares it with committed state | Yes. `python -m tools.generated_release --check`, and the default-lane suite through `verify` |
| Mutations for edited values, a stale contract or binding digest, and mismatched provenance | Yes. Each is planted in a copy of the declared inputs and reported under its rule, at the field it moves |
| The regenerate and verify workflow is documented | Yes. CONTRIBUTING and the renderer page |
| It runs in the low-cost tests without a cluster, model, or network | Yes. The suite runs in the default lane; a test refuses sockets during verification and refuses an import that runs a process or reaches a network |
| Verification fails with an actionable diff and does not repair drift | Yes. Exit 1, the rule, the field and what it means, a unified diff, and the regenerate command; a test holds that verification writes nothing and calls no writer |
| Stale or hand-edited generated values or provenance are detected | Yes, for every declared committed release |
| Deterministic and safe in normal CI | Yes. Two interpreters under two hash seeds print the same report; nothing is written |
| No cluster, model download, or network access | Yes |
| The regenerate and verify workflow is explicit | Yes. `--write` takes release names and has no default |

## Decisions taken while writing, and what was left out on purpose

1. **The inputs are declared in code, beside the check.** A sources file inside the
   release directory would put a third file where `write_release` writes two, and a new
   document format would need its own schema. `DECLARED_RELEASES` is typed and read by
   the same suite that holds the check.
2. **Nothing in a committed release is trusted.** Both revisions come from the
   declaration. A release that records another revision than its declaration is drift.
3. **The reference release moved into the writer's layout**, so its
   `output.helmValues.path` names a file beside it, and the check reads a release the way
   the platform writes one. Its bytes did not change.
4. **The platform defaults are read from the chart's `api` block**, as the
   generated-release suite already does. No defaults file exists. A change to those
   values is therefore drift, but the release identifier does not move with it, because
   the revision is declared. This is the limitation the renderer page already measures,
   now visible in a committed release. It is not closed: nothing reconstructs the
   defaults at a revision.
5. **An architecture rule gains a second named exemption.** The boundary test said no
   tool imports the render package, so that nothing delivers a render. The drift check
   must call `generate_release`. It is a repository check: a contributor or the test
   suite runs it, and it writes only a declared release directory in this repository. It
   is exempt by name, the exemption must be used, and a new test holds that nothing on a
   delivery path names the check. **This is the decision most worth a reviewer's
   disagreement.**
6. **Regeneration replaces, it does not merge.** It removes the two generated files and
   writes both again through `write_release`, which writes both or neither. If that write
   fails, the directory is absent, and running the command again writes it. It refuses a
   directory that holds anything else, and a left-over staging directory.
7. **Left out:** checking that a revision names a commit, reading any input at a recorded
   revision, a check over an arbitrary release directory, a delivery or GitOps layout,
   and a separate CI job: the default-lane suite already runs the check on every change.
   No claim register, evidence index, or proof dashboard entry changes, so no ledger is
   needed.

## What the checks caught before the first commit

- **An architecture rule the first draft broke.** The first domain run failed
  `test_nothing_outside_the_render_package_imports_it`: the new tool imports the render
  package. The first draft had not looked for that rule. The exemption is now explicit,
  with its reason, a used-exemption assertion, and a companion test, and decision 5 says
  what was weighed.
- **A decorative test.** The first draft's "findings are reported in rule order" test
  read only the rule list. The defect sweep below removed the sort and the suite still
  passed. The test was replaced by one that plants a stray file and a missing file, whose
  natural order is the reverse of the rule order.
- **A contract mutation that was not a drift.** A first smoke run raised only the
  maximum replica count; the renderer refuses that, so the check reported
  `generated-release-sources-refused`, not drift. The suite keeps that case as the
  refusal test and raises both bounds for the claim-relevant change.
- **The suites' own counts.** The inventory's tests failed until the module was
  registered, the no-claim count moved to sixty-one, and the number words reached
  sixty-one; the link test failed until this record existed.

## Checks that the new tests are not decorative

At the first commit, thirteen defects were planted, one at a time, in a copy of the
working tree - every
tracked and new file, copied outside the repository. Each edited file was compiled before
the suites ran, and the copy's `tools.generated_release` was confirmed to be the one
imported. Two suites - the new one and the boundary's, 178 tests - ran in full against
each. The copy passed all 178 before the first defect and again after the last was
removed. Every defect was caught:

| Defect, exactly as made | Of 178 |
|---|---|
| A drifted values file is not reported: `and name != str(VALUES_FILE_NAME)` | 10 failed |
| Field findings are never made: `if True: return []` | 15 failed |
| The values digest is never compared: `if False and actual != recorded:` | 7 failed |
| The declared renderer revision is ignored: `GitRevision("a" * 40)` | 1 failed |
| The CRLF explanation is never given: `if False:` | 1 failed |
| A stray entry is not reported: `if False:` | 3 failed |
| A left-over staging directory is not reported: `if False:` | 2 failed |
| Regeneration removes what the platform did not write: `if False: raise RegenerationRefused(...)` | 2 failed |
| `--check` regenerates every drifted release after reporting it | 2 failed |
| A drifted file carries no diff: `()` | 13 failed |
| `--write` runs without a release name: `if False:` | 1 failed |
| Findings are reported in the order they are found | 1 failed |
| A refused source crashes instead of being reported: `except (OSError, yaml.YAMLError)` | 3 failed |

The ordering defect passed the first draft of the suite; see the section above.

## Commands

Run from Git Bash on the contributor's Windows host, with the locked toolchain:

```sh
uv run --locked ruff format --check .
uv run --locked ruff check .
uv run --locked python -m mypy
uv run --locked python -m pytest tests/domain/test_generated_release_drift.py -q
uv run --locked python -m pytest tests/domain tests/architecture tests/testing -q
uv run --locked python -m pytest -q
uv run --locked python -m tools.generated_release --list
uv run --locked python -m tools.generated_release --check
python -B -m tools.evidence_index --gate
git diff --check
```

Results are in [Results](#results).

## Results

At the first commit:

| Command | Result |
|---|---|
| `ruff format --check .` | 593 files already formatted |
| `ruff check .` | All checks passed |
| `mypy` | No issues in 327 source files |
| The new suite | 57 passed |
| `tests/domain`, `tests/architecture`, `tests/testing`, before the inventory and this record existed | 11,649 passed, 24 skipped, 2 failed: the link to this record and the uninventoried module, both closed by this change |
| The default lane, `pytest -q` | 17,209 passed, 33 skipped, 14 deselected, in 12 minutes 14 seconds |
| `tools.generated_release --list` | One declared release, `support-assistant-local-kind` |
| `tools.generated_release --check` | `OK`, exit 0 |
| `tools.evidence_index --gate` | Exit 0, the five values above, unchanged |
| `git diff --check` | Clean |

Helm was on `PATH` on this host, so the generated-release suite's Helm comparisons ran
against the moved golden files and passed. The new suite does not run Helm.

## What the independent review found

An independent review of the first commit found no critical or high finding, and the
items below. Each is closed in the second commit, which also says what the first commit
claimed and what was true.

- **Three pages still said nothing commits a release.** The root README's contracts row
  and two sentences of the contracts index said "nothing commits or installs one", which
  the first commit had corrected in the release document only. They now say that a drift
  check compares the one committed release, a test's golden release, with its declared
  sources, and that nothing installs one.
- **The delivery-path guard was narrower than its wording.** The first commit's test read
  only `.py`, `.sh`, `.yaml`, and `.tf` files under six directories, and matched only the
  dotted and slashed module paths. So it missed `from tools import generated_release`, a
  chart template, a Dockerfile, a workflow, and `pyproject.toml`, while the boundary page,
  the changelog, and this record said nothing on a delivery path reaches the tool. The
  test now reads every tracked file under seven directories and `pyproject.toml`, matches
  `generated_release` as a whole word, and asserts that its pattern sees each spelling it
  names and not `test_generated_release`.
- **The check advised a regeneration it would refuse.** `--check` printed "regenerate
  with" for every drifted release, including a stray entry, a left-over staging directory,
  and refused sources, for which `--write` refuses. `BLOCKING_RULES` now names those
  rules; the command prints what to resolve first instead, and `regenerate` refuses under
  the same set.
- **The renderer page overstated `--write`.** It said the result is both files or
  neither. `regenerate` removes the old release before it writes the new one, so a failed
  write leaves the directory absent. The page now says so, the command reports a failed
  write instead of a traceback, and a test fails a write, then runs `--write` again.
- **A test did not exercise what it was named for.** "A missing file is reported and the
  other is still compared" left the other file intact, so a check that skipped it passed.
  The test now edits the other file and requires its drift finding.
- **Inputs that raised instead of being refused.** A compatibility matrix that is valid
  JSON but not an object raised `AttributeError`, and pathologically nested YAML raised
  `RecursionError`. Both are now `generated-release-sources-refused`.
- **A symbolic link was followed.** A release directory that is a link to a directory
  was compared, and `regenerate` emptied the link's target and then failed. A release
  path that is a file, a symbolic link, or a generated file that is a link is now
  `generated-release-unexpected-entry`, and regeneration refuses it. The two
  symbolic-link tests skip on this host, where an unprivileged Windows account cannot
  create a link; they run where one can, such as the Linux runner.
- **Process-wide state.** `derive` replaced the workload domain's compatibility matrix
  and did not restore it. It now restores the one set before.
- **Refusal text named absolute paths.** A missing input was reported with the host's
  full path. It is now named by its path under the repository root.
- **A stale inventory note.** The note for `tests/domain/test_generated_release.py` said
  it never establishes that anything was committed. It now says installed or served, and
  names the drift check's declaration.
- **Untested branches.** A file where the release directory belongs and a release that
  parses to a list, a scalar, or nothing now have tests.

Not changed, and recorded as limits: the socket test patches `socket.socket` and
`socket.create_connection` only, and the import test reads the tool's own imports, not
what they import. Neither was the target of a planted defect.

### Checks that the fixes are not decorative

Nineteen defects were planted, one at a time, in a fresh copy of the working tree after
the fixes: the thirteen above, with their anchors moved where the code moved, and six for
the fixes. Two suites - the drift suite and the boundary's, 191 tests, of which the two
symbolic-link tests skip on this host - ran against each. The copy passed 189 and skipped
2 before the first defect and again after the last was removed. Every defect was caught:

| Defect | Of 191 |
|---|---|
| A drifted values file is not reported | 11 failed |
| Field findings are never made | 15 failed |
| The values digest is never compared | 7 failed |
| The declared renderer revision is ignored | 1 failed |
| The CRLF explanation is never given | 1 failed |
| A stray entry is not reported | 4 failed |
| A left-over staging directory is not reported | 2 failed |
| Regeneration removes what the platform did not write | 3 failed |
| `--check` regenerates every drifted release after reporting it | 3 failed |
| A drifted file carries no diff | 13 failed |
| `--write` runs without a release name | 1 failed |
| Findings are reported in the order they are found | 1 failed |
| A refused source crashes instead of being reported | 7 failed |
| A file at the release path is reported as a missing directory | 1 failed |
| `--check` advises regeneration despite a blocking finding | 1 failed |
| The compatibility matrix is not restored | 1 failed |
| A refusal names the absolute path | 4 failed |
| A failed write is a traceback | 1 failed |
| A matrix that is not a JSON object is not refused | 3 failed |

### Results after the fixes

| Command | Result |
|---|---|
| `ruff format --check .`, `ruff check .` | Clean |
| `mypy` | No issues in 327 source files |
| The drift suite | 68 passed, 2 skipped: the symbolic-link tests |
| `tests/testing/test_test_inventory.py`, `tests/testing/test_document_links.py`, `tests/security` | 2,346 passed |
| The default lane, `pytest -q` | 17,221 passed, 35 skipped, 14 deselected, in 11 minutes 6 seconds; the two further skips are the symbolic-link tests |
| `tools.generated_release --check` | `OK`, exit 0 |
| `tools.evidence_index --gate` | Exit 0, the five values above, unchanged |
| `git diff --check` | Clean |

## Privacy and publicability

The diff was read for private material, local paths, credentials, and account
identifiers. The new files name only repository paths. The diff a drifted check prints
quotes the committed and the derived file, both repository content.

## What this does not establish

- **That anything was installed or served.** The check compares files. No cluster read
  them.
- **That either revision names a commit.** The reference release's revisions are
  placeholders, and nothing reads Git history.
- **That the platform defaults are the ones at the declared revision.** They are read
  from the chart at the checked-out commit.
- **That a release nobody declared, or a directory Git does not track, is checked.** A
  test fails if a tracked generated file is outside a declared directory; nothing else is
  searched.
- **That a generated file holds no secret value.** The bounded property on the renderer
  page is unchanged.
- **That the symbolic-link handling was run on this host.** Those two tests skip here; the
  defect sweep therefore did not exercise them either.
