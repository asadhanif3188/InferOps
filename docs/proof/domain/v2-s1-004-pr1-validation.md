# V2-S1-004-PR1 validation

Date: 2026-10-01

What this change checked before it was committed, and how. What it publishes is in
[provenance input trust](../../contracts/rendered-workload-release.md#provenance-input-trust)
and [recording a release](../../domain/renderer-input-boundary.md#recording-a-release);
this page is about the finding it closes and the checks run over the repository after the
code, its suite, and the documents were written.

The change executed nothing against a host: no cluster, runtime, or model was contacted,
and nothing was rendered, provisioned, written to Git, or published. Every check below is
static, which is `C0` under [the evidence levels](../../testing/evidence-levels.md). It
proves what the one supported path can build a release from, and nothing about a
deployment. It adds no record to the evidence pack and moves no claim.

## The finding this closes

An independent collective review of the first V2 sprint, after all of its planned changes
had merged, returned *blocked*. Its highest-severity finding was that the release story's
acceptance criterion - sensitive data cannot enter provenance - was not met as written:

- [the release document](../../contracts/rendered-workload-release.md#secrets) opened its
  Secrets section with "A release references nothing secret and carries nothing secret";
- `tests/domain/test_rendered_workload_release_domain.py::test_the_remaining_gap_is_a_gap`
  asserts that a lowercase token with no published credential prefix, written as a
  workload name, passes the single-release rules;
- the review's own probe recorded a release with such a workload name, with the real
  source digests, and both release checks returned no finding;
- [the `V2-S1-002-PR2` record](../contracts/v2-s1-002-pr2-validation.md) called the
  criterion "met structurally and by the credential rule, except the measured remainder" -
  and a criterion met with an exception is not met;
- separately, the render boundary accepted a binding named like a credential (`sk-` and
  four zeros) and handed it to a renderer.

The review's reading, which this change adopts: no heuristic can identify every arbitrary
secret that also has the shape of a valid identifier, so the honest correction is an
explicit input-trust policy, enforced on one supported path, with the remainder stated as
an assumption rather than claimed impossible.

## Eligibility, checked before anything was written

- **What it builds on is merged.** `main` was at `8eec36b`, the merge of `V2-S1-003-PR2`,
  so the release domain, the render boundary, its refusals, and its ownership table were
  in place.
- **The gate and the pack.** `python -B -m tools.evidence_index --gate` exited 0 with
  `FROZEN` for `V1-S5-013-PR2`, `RELEASED v1.0.0` at `718ad2e0…` with the set `1d40b33f…`
  and the pack `652e9051…`, and `CURRENT` with the set `08d4868f…` and the pack
  `b958a724…` - the six digests `V2-S1-003-PR2` recorded. None of the files this change
  touches is cited by a record.

## The policy, exactly

The policy is code, in
[`src/inferops/domain/render/recording.py`](../../../src/inferops/domain/render/recording.py),
and the release document publishes both of its tables, which a test holds to the code.

- **Three classes, closed:** `public-identity` (a name or reference, public by policy),
  `derived-digest` (a digest or a full commit revision), and `excluded` (never recorded).
- **Every field a release has: fifteen.** Nine are `public-identity` - `apiVersion`,
  `kind`, `metadata.workloadId`, `metadata.workloadVersion`, the contract's
  `apiVersion`, the binding's `apiVersion`, `environment`, and `name`, and the values
  file's `path`. Six are `derived-digest` - `metadata.releaseId`, the two source digests,
  the renderer and platform-defaults revisions, and the values digest. None is
  `excluded`. Each row names its origin - the release version, a context value, the
  context's typed sources, the renderer reference, the values reference, or the
  derivation - and the path it is read from.
- **Every value of the render context: forty-four.** Two are `public-identity`: the
  workload's name and version. Forty-two are `excluded`, under six reasons: the secret
  references, alone, as *sensitive*; the owner, tenant, and cost centre; seventeen render
  settings; twelve references to other artifacts; three platform defaults; and six
  environment facts. Each reason names what covers the value instead - the contract
  digest, the binding digest, or the platform-defaults revision.
- **Members the context does not hold as values** - a contract's description and
  annotations, a binding's owner - cannot be read by the path at all. The documents'
  versions and the binding's name and environment reach a release only through the
  context's typed sources, as the rows above name.

## What changed

- **`src/inferops/domain/render/recording.py`** (new): the two policy tables,
  `ProvenanceTrust`, `ProvenanceOrigin`, `ProvenanceField`, `ContextFieldTrust`,
  `ReleaseNotRecordedError`, `provenance_field`, and `record_release`. The package is ten
  modules; the new one imports only standard-library modules the package's import test
  already permits, and the workload and release domains.
- **`src/inferops/domain/render/__init__.py`**: exports them, and its docstring names the
  path.
- **`tests/domain/test_provenance_input_trust.py`** (new): 44 test functions, 91 tests once
  parametrized - 41 and 81 at the first commit; the review fixes added the three
  functions and ten tests described below.
- **`tests/domain/test_renderer_input_boundary.py`**: the module count the import test
  asserts goes from nine to ten. Nothing else in it changed.
- **`docs/contracts/rendered-workload-release.md`**: a new *Provenance input trust*
  section with both tables, what the path enforces, the input-trust limitation, the
  distinction from repository secret scanning, and what stays open and whose it is. The
  Secrets section's absolute opening sentence is replaced and quoted as history. The
  status paragraph, the *not applied yet* row for unprefixed lowercase credentials, the
  validation section, and two bullets of *What this contract does not do* now say that
  the domain builds a release in memory and writes none.
- **`docs/domain/renderer-input-boundary.md`**: a *Recording a release* section, two rows
  in the refusal table, and two rows of *Rules that are not applied yet* updated - the
  version a release cannot hold, and the credential-shaped binding value.
- **[The `V2-S1-002-PR2` record](../contracts/v2-s1-002-pr2-validation.md)**: a dated
  *Later correction* section appended. Nothing above it changed, and a test holds that
  the original acceptance row is still there, once, before the correction.
- The project and contract changelogs, the README's and both contract indexes' release
  rows, the proof index row that links here, the test inventory's data and page (the
  fifty-seventh module without a claim, and ten `unit` modules), its number words, and the
  secret-scanning allowlist document (a ninth suite using synthetic prefixes).

## What the change was asked to reach, and what it reached

| Asked | Reached here | How |
|---|---|---|
| Every supported provenance field has an explicit trust classification | Yes | Fifteen release fields and forty-four context values, each classified once; the schema's leaves, a recorded release's fields, and the ownership table's names are each compared with the tables |
| Release construction consumes validated typed sources and an explicit allowlist, not raw document content | Yes | `record_release` takes a `RenderContext` and two typed references whose members must be their constrained types; each field is read from its row's source; a raw document, dictionary, or string at any argument, or a reference built around bare strings, is a `TypeError`; the release is read back from its plain JSON form by the published parser, so a value of the right type that skipped its check is refused; a tripwire test reads the function body and fails on the obvious edits that would bypass the allowlisted reader. A caller importing the private sentinel can still forge a context of well-formed values; the documents state it and a test measures it |
| Classified-sensitive or excluded inputs cannot enter through the supported path | Yes | Every excluded context value, marked, reaches no release for any committed contract; eight markers planted in real inputs reach none; a row pointed at an excluded value, or a value reclassified, raises |
| Known credential-shaped values remain refused where applicable | Yes | The four lowercase shapes the schema cannot refuse are refused in the binding name, the workload name and version, and the values file name, without being quoted |
| The supported-path guarantee and the arbitrary-identifier limitation are both documented | Yes | [Provenance input trust](../../contracts/rendered-workload-release.md#provenance-input-trust); a test records an unprefixed token written as a workload name being recorded |
| Mutation and negative tests catch an added unclassified field, an added sensitive-source path, and a bypass of the typed, allowlisted boundary | Yes | See [the planted defects](#checks-that-the-new-tests-are-not-decorative) |
| No historical V1 record or completed `V2-S1-002` record is silently rewritten | Yes | No V1 file is touched; the `V2-S1-002-PR2` record gains an appended, dated section and nothing else |
| No V2 claim moves; evidence remains `C0` | Yes | The claim register, the dashboard, and the evidence index are untouched; the gate prints the same six digests |

**The release story's sensitive-data criterion, as it stands after this change.** The
original wording is history and is left where it was. The criterion is closed against the
bounded property this change enforces: *a release can be built, on the one supported
path, only from fields classified public-safe identities or derived digests and
revisions, read from validated typed inputs; nothing classified excluded - secret
references, free text, environment variables, prompts or responses, any other document
member - has a path in; known credential shapes are refused.* It is **not** closed against
"no secret can ever appear in provenance": a secret an author deliberately writes as a
valid name, or as a hexadecimal value of a revision's or digest's length, is outside what
syntax can prove, and the release document says so.

## Decisions taken while writing, and what was left out on purpose

- **The path starts at the render context.** It is the only object that is already a
  validated contract, typed defaults, and a selected, ownership-checked binding, and its
  sources are the typed identities a release records. Taking the contract and binding
  separately would have duplicated selection and ownership.
- **The tables are read at call time.** Editing a row or a classification to open a path
  makes `record_release` raise, instead of a stale copy deciding. Reaching that raise is
  a defect in the tables, so it is an `AssertionError`, as other table defects in the
  package are.
- **No rule, no code, no category was added.** A refusal is the release domain's own
  `ReleaseRefusal`, or a `MalformedReleaseError` for a version no release can hold,
  carried by a new `ReleaseNotRecordedError` under the existing `contract-invalid` code.
  The render refusal vocabulary is unchanged at twenty-one rules.
- **`verify_release_sources` is not called inside the path.** The context's sources are
  computed from the same contract and binding objects, so they agree by construction; a
  test calls it on every recorded release and finds nothing.
- **The render boundary still hands a credential-shaped binding to a renderer.** Only the
  binding's name is a provenance field; every other binding value is excluded from
  provenance, and whether generated output may carry one is a rule for the change that
  generates values. A test measures it, and both documents say whose it is.
- **The release domain's own gap test is unchanged.** It is still true of the parsed
  path, and its docstring's instruction - say so here the day a change closes it - does
  not apply: this change does not close it, it bounds it.

## What the checks caught before the first commit

Each was found by reading the code or running the suite, and fixed before anything was
committed:

- **A bypass of the typed boundary, found on re-reading the function.** The first draft
  checked only that `renderer` and `helm_values` were a `RendererReference` and a
  `HelmValuesReference`. Both are dataclasses that check nothing, so a reference built
  around a bare string passed - free text as the values file name would have reached a
  release as long as no part of it began with a published prefix. Each member must now be
  its constrained type, which refused a malformed value when it was made, and four tests
  build each kind of bare reference and assert the refusal.
- **The policy table was inferred, not written.** The first draft classified a context
  value as public whenever its reason string equalled the identity reason. Each row now
  says `_public(...)` or `_excluded(...)` explicitly; one row the rewrite missed was left a
  bare reason string, and counting the rewritten rows found it.
- **The suite's own counts.** Adding the module made the render package's import test
  assert ten modules, the inventory's `unit` section count ten, and its no-claim count
  fifty-seven; each failed until it was updated.
- `ruff` asked for import order in the new suite; a `type: ignore` placed by hand was moved
  by the formatter onto the wrong line, so the bare references are now built through a
  value typed `Any` instead.

## Checks that the new tests are not decorative

Ten defects were planted, one at a time, in an archived copy of the working tree - every
tracked and new file, copied outside the repository - never in the tree itself. Each
edited file was compiled before the suites ran, so no row below measures a syntax error,
and the copy's package was confirmed to be the one imported. Both suites that cover the
path - the new one and the render boundary's, 200 tests - ran in full against each.
Every one was caught:

| Defect, exactly as made | Of 200 |
|---|---|
| `record_release` reads the workload identifier with `DnsLabel(render_context.value("attribution.tenant"))`, bypassing the allowlisted reader | 23 failed |
| `attribution.tenant` classified `_public(_PEOPLE)` | 6 failed |
| The single-release rules are skipped: `refusals = []` | 30 failed |
| The `output.helmValues.sha256` row is deleted from `RELEASE_PROVENANCE` | 6 failed |
| The reader ignores the context classification: its check becomes `if False:` | 2 failed |
| `record_release` accepts a raw context: its `isinstance` check becomes `if False:` | 5 failed |
| The ownership table gains `_w("workload.notes", "metadata.description", required=False)`, unclassified | 9 failed |
| `recording` imports `os` and calls `os.environ.get("INFEROPS_WORKLOAD_ID")` before reading the sources | 3 failed, after the fix below |
| `security.secretRefs` classified `_public(_SENSITIVE)` | 6 failed |
| The `isinstance(helm_values.path, ValuesFileName)` clause is deleted | 2 failed |

**The environment row caught a defect in the suite.** Its first run reported 2 failed and
315 errors. The two failures were the right tests; the errors were not. The test that
makes the process environment unreadable restored it only after a successful call, so a
failing call left it unreadable, and pytest's own write of `PYTEST_CURRENT_TEST` between
phases failed in every later test. The restore now runs in `finally`, and the same defect
gives 3 failed and no errors - the third is the render package's import test, which
refuses `os` as well.

Two defects are caught by only two tests each. Those tests are the ones written for the
property, and the counts are stated so that nobody reads 81 new tests as 81 guards on
each property.

## Commands

Run from Git Bash on Windows, with the locked environment.

| Command | Result |
|---|---|
| `uv run --locked ruff check .` | All checks passed |
| `uv run --locked ruff format --check --no-cache .` | 576 files already formatted, this record included |
| `uv run --locked mypy` | No issues in 316 source files |
| `uv run --locked python -m pytest tests/domain/test_provenance_input_trust.py tests/domain/test_renderer_input_boundary.py tests/testing/test_test_inventory.py -q -p no:cacheprovider` | 1,280 passed: 81, 119, and 1,080 |
| The ten planted defects, against an archived copy | Every one caught; see above |
| `python -B -m tools.evidence_index --gate` | Exit 0; the six digests above, unchanged |
| `gitleaks dir <path> --config .gitleaks.toml --redact`, for every changed and new file, with gitleaks 8.30.1 (the version the workflow pins) | No leaks found in any |
| `git diff --check` | Exit 0, no output |

**The full default lane ran before the first commit**, with the new files registered with
Git so the link suite collected them:
`uv run --locked python -B -m pytest -q -rs -p no:cacheprovider --basetemp=<scratch>` gave
**16,800 passed, 33 skipped, 14 deselected, none failed**, in 18 min 47 s. That is 94 more
than the 16,706 `V2-S1-003-PR2` recorded: the new suite's 81, the inventory suite's 9 for
one more module, and 4 more cases in suites parametrized over the repository's files. The
skips are the ones earlier records name, such as symbolic links this host does not permit.
A first full run was started before the bare-string fix and stopped, since its tree was no
longer the one being committed.

**After the review fixes**, which touched `record_release` and its docstring, the new
suite, three documents, the inventory, and this record, the full lane was run again with
the same command: **16,810 passed, 33 skipped, 14 deselected, none failed**, in 14 min
17 s - the first run's 16,800 and the ten tests the fixes added. `ruff check`, `ruff
format --check --no-cache` (576 files), and `mypy` (316 source files) were clean again,
the three targeted suites gave 1,290 passed (91, 119, and 1,080), the gate printed the
same six digests, and gitleaks found nothing in any of the eighteen changed files. This
record's review section was completed after that run; the link and document suites were
run again over it.

## What the independent review found

A reviewer outside the change read the first commit, `7a639b2`, re-ran the linters and the
three suites, recounted every figure in this record and the documents, checked the
completed record's history byte for byte, scanned the added text for private material,
and probed the path for ways in. It found no defect it rated critical, one it rated high,
two medium, and four low. Every figure it could recount was correct.

**High - the documents claimed more than `isinstance` enforces.** The first commit's
documents said only typed inputs cross, and that each reference's members "refused a
malformed value when it was made". The reviewer built values that are the right type and
were never checked: a `ValuesFileName` subclass whose check does nothing, holding
`has spaces and SECRET text.yaml`; a `GitRevision` subclass holding `my-secret-token`; a
real `ValuesFileName` whose text was replaced with `object.__setattr__`; and a context
built with the module's private sentinel. Every one was recorded. The single-release rules
check credential prefixes, not patterns, so none was refused. **What the first commit got
wrong** is that the typed boundary rested on types in-process code can forge, while the
documents stated it as if construction were the only way to make one.

*Fixed in code and in the documents.* `record_release` now reads the release back from its
plain JSON form with the published parser and returns what the parser reads, so every
string is checked against its published pattern and length again, whatever type it came
in. Four new cases - the two unchecked subclasses, the replaced file name, and a recorded
binding name replaced in the context's sources - are each refused with a
`MalformedReleaseError` at exactly that field, without being quoted. With the parse-back
removed from a copy of the module, exactly those four fail and the other 206 tests of the
two suites pass, so they test the fix and nothing else. A context forged with the private
sentinel is still recorded, as long as its values are well formed: that is the context's
own documented limit, and a fifth new test measures it rather than leaving it implied. The
release document, the boundary document, and the module's docstring now say that the
supported path is the guarantee, not code in the same process, and no longer say that only
the boundary can issue a context.

**Medium - the tripwire was described as stronger than it is.** The test that reads
`record_release`'s body looked only at `render_context.<attribute>` and at positional
arguments, so an alias, `getattr`, a keyword argument, or a second attribute after
`sources` would have passed it. It now describes every occurrence of the name by what
encloses it and requires exactly the four the function has; five new cases add each of
those evasions, and a direct read, to the real body and assert the tripwire sees each. The
documents now call it a tripwire against the obvious edits, and say a read hidden behind
another function is beyond it.

**Medium - the limitation named four public fields without saying how wide two are.** A
workload version may be a digest-pinned image reference of up to 512 characters, and a
values file name any lowercase name of up to 255 ending in `.yaml`. The limitation
paragraph now says so.

**Low.** The "cannot enter" bullet now opens *On the supported path*. The test that the
document states the limit checked two phrases; it now checks eight, one for each statement
the change owes. The edited paragraph of `contracts/README.md` is rewrapped. The planted
defects ran in an archived copy and cannot be re-run from the repository; the reviewer
checked them for consistency, and this record already says where they ran.

**Run again after the fixes:** `ruff check`, `ruff format --check --no-cache`, `mypy`, the
three targeted suites, the gate, gitleaks over every changed path, `git diff --check`, and
the full default lane, with the results below.

## Privacy and publicability

The diff was read for private planning material, local paths, and credentials. It names
no private planning document or repository, no local filesystem path, no host or account
name, and no later story identifier. The only credential-shaped strings are four published
prefixes followed by four zeros and the same fixed lowercase string with no published
prefix that the release domain's suite already carries; each is labelled where it appears
and matches no scanner rule. The markers the suite plants are the letters `zqmark` and
a suffix, and identify nothing. The review fixes add two made-up strings,
`has spaces and SECRET text.yaml` and `my-secret-token`, as values that skipped their
check; neither has a published prefix, neither is a credential, and gitleaks reports
nothing for them.

## What this does not establish

That an identifier an author chose is not a secret written to look like one; that a
renderer revision, platform-defaults revision, or values digest a caller supplies names a
commit or a file; that any renderer produces a release, or that one was written,
committed, installed, or run; or anything about what generated values may carry.
