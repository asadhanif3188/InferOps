# V2-S1-002-PR2 validation

Date: 2026-09-30

What this change checked before it was committed, and how. What it publishes is in
[the RenderedWorkloadRelease document](../../contracts/rendered-workload-release.md);
this page is about the checks run over the repository after the domain package, its
suite, and the document were written.

The change executed nothing against a host: no cluster, runtime, or model was contacted,
nothing was rendered, provisioned, or published. Every check below is static, which is
`C0` under [the evidence levels](../../testing/evidence-levels.md). It proves artifact
semantics — what a release, its canonical form, and its digests mean and refuse — and
nothing about a deployment. It adds no record to the evidence pack and moves no claim.

## Eligibility, checked before anything was written

- **The schema it builds on is merged.** `main` was at `7959d36`, the merge of
  `V2-S1-002-PR1`, so the release schema, its fixtures, and its structural validator were
  in place, beside the EnvironmentBinding domain and the released WorkloadContract.
- **The gate and the pack.** `python -B -m tools.evidence_index --gate` exited 0 with
  `FROZEN` for `V1-S5-013-PR2`, `RELEASED v1.0.0` with the set `1d40b33f…` and the pack
  `652e9051…`, and `CURRENT` with the set `08d4868f…` and the pack `b958a724…` — the six
  digests `V2-S1-002-PR1` recorded. None of the files this change touches is cited by a
  record, and the same command after the change printed the same six digests.

## What changed

- **A domain package.** `src/inferops/domain/release/`, eight modules — the package's `__init__` and seven more: typed values
  (`values`), supported and recordable versions (`versions`), frozen objects (`release`),
  a parser (`parsing`), the canonical form, digests, and release identifier
  (`canonical`), the provenance rules (`provenance`), and every refusal and rule
  (`errors`). It imports only the standard library and the rest of the domain. It reuses
  the WorkloadContract's `DnsLabel`, `Environment`, and `ImageReference`, the binding's
  `BindingVersion`, the contract's `ContractVersion`, and the WorkloadContract domain's
  credential heuristic, unchanged.
- **Seven rule identifiers**, all under the existing `contract-invalid` code, in a
  domain-only table: `release-id-not-derived`, `release-value-credential-shaped`,
  `release-contract-mismatch`, `release-contract-digest-mismatch`,
  `release-binding-mismatch`, `release-binding-digest-mismatch`, and
  `release-environment-mismatch`.
- **Tests.** `tests/domain/test_rendered_workload_release_domain.py`, 281 tests — 259 at the first
  commit, and twenty-two more after [the independent review](#what-the-independent-review-found) —
  inventoried in the `unit` layer with no claim and a written reason. Four docstrings and
  one anchor sentence in the schema suite, `tests/contracts/test_rendered_workload_release_v1alpha1.py`,
  were corrected because they said the release has no semantic layer; its 160 tests and
  what they assert are otherwise unchanged. One number word was added to the inventory
  suite.
- **Unchanged:** the release schema, the value of every release fixture and every
  expected refusal, the offline validator's verdicts (its module docstring, one fixture's
  header comment, and the manifest's description of its one layer were corrected), and
  the WorkloadContract and EnvironmentBinding schemas, fixtures, validators, and domains.
- **Documents.** The release document — status, a platform-domain row, the identity
  paragraph, a new section on the canonical form and source digests, the time and
  randomness section, the secrets section, the compatibility note, the rejection
  section's validator sentence, a new provenance-rules section, the not-applied table,
  validation, and what the contract does not do — and its fixtures' README; the
  EnvironmentBinding document's sentence on how a binding's digest is computed; the two
  contract indexes, the contract package changelog, the project changelog, the README's
  contracts row, the domain package's docstring, the test inventory's data and page, the
  proof index row that links here, and the secret-scanning allowlist document.

## What the change was asked to reach, and what it reached

| Asked | Reached here | How |
|---|---|---|
| Typed validation and canonicalisation helpers, with tests | Yes | `parse_rendered_workload_release`, `check_rendered_workload_release`, `verify_release_sources`, `canonical_json`, `canonical_sha256`, `contract_digest`, `binding_digest`, `derive_release_id`, and `canonical_release`; 281 tests |
| Uncontrolled timestamps and random IDs are absent from canonical content | Yes, for everything this package computes | The canonical form refuses dates, times, and floats rather than writing them; the package imports no clock or random module and names no route to import one at run time; a test makes fourteen named clock and random functions fail while a release is recorded, checked, and verified; two interpreters under two hash seeds agree; the canonical form of each valid fixture and of its identity holds no date, time of day, or UUID; an underived identifier of the right shape is refused |
| Digest and reference formats are stable | Yes | A pinned value's canonical bytes and digest are held; the canonical form is the evidence index's byte for byte on the golden value and every committed contract, binding, and release fixture; key order, comments, flow style, blank lines, and an integral float move no source digest; the domain's patterns, bounds, and vocabularies are held to the schema |
| Source identities cannot be omitted | Yes | Removing any of the twenty-three members of a release — every object and every leaf — is refused by the parser at that member and by the schema; no attribute of the nine typed classes has a default |
| Claim-relevant source changes alter the appropriate provenance result | Yes | Eight identity members, one at a time, each move the identifier; two output members move the release and not its identifier; thirteen contract values and six binding values each move that document's digest and the identifier, and a release recorded before the change is refused with exactly that document's digest rule |
| Sensitive content is excluded or refused | Yes, with a measured remainder | The identity excludes the output and all document content; the typed tree has no attribute that could hold content, a time, or free text; every lowercase published credential prefix — twenty-five of forty — is refused in every position of the four fields that can hold one, the image reference form of the version included; the cost (`sk-demo` and `task-sk-demo`) and the remaining gap (a lowercase token with no published prefix) are asserted |

**The parent story's acceptance, as it stands after this change.**

| Criterion | State | Where |
|---|---|---|
| RenderedWorkloadRelease is versioned and machine-readable | Met | `V2-S1-002-PR1` |
| It records workload identity, contract digest, renderer revision, platform-default revision, environment binding, release ID, and generated-values digest | Met as fields, and now checked for the release ID and the two source digests; the values digest is recorded and not checked | `V2-S1-002-PR1`; this change |
| Canonical output contains no uncontrolled timestamp or random release ID | Met for the release and its identity. Canonical *generated values* do not exist yet and are the renderer's to produce | This change |
| Sensitive data cannot enter provenance | Met structurally and by the credential rule, except the measured remainder above | Both changes |
| Compatibility and validation rules are tested | Met | Both changes |

## Decisions taken while writing, and what was left out on purpose

- **A source digest is of the document's parsed value, not its bytes.** The first PR left
  this open. Hashing bytes would make a comment or a re-indent a new release, and would
  make two documents JSON Schema calls equal — `apiReplicas: 1` and `apiReplicas: 1.0` —
  two digests. Hashing the value the domain reads means a document that does not parse
  has no digest: a document is read before it is hashed, as it is validated before it is
  rendered.
- **The canonical form refuses what it cannot spell one way.** Floats, integers beyond
  2⁵³ − 1, dates, non-string member names, and unencodable strings are refused rather
  than normalised, so the form is reproducible by any serialiser and a YAML date cannot
  slip in as text. No document hashed today holds any of them.
- **How the values file is hashed is not decided.** No values file exists, and whether its
  digest names bytes or value belongs to the change that writes it. The values digest is
  recorded and checked by nothing, and the document says so.
- **The rules live in the domain, not the offline validator.** The validator stays what a
  bare-schema consumer can reproduce, as the binding domain's rules do; a test holds the
  validator's verdict on an underived identifier unchanged. Those rules have no fixture
  file — each is provoked by a test instead, and a test requires every rule to refuse
  something. The contract package's README says so.
- **The credential rule looks after every separator.** The WorkloadContract's heuristic
  tests a value's start; a release version's pre-release is where the first change
  measured a gap, so the same prefixes are applied at every part — after `-`, `_`, `.`,
  `+`, `/`, `@`, and `:`. The first commit left `_` out; see the review section. The cost is
  measured.
- **The committed valid fixtures were not given real digests.** They stay placeholders,
  and a test asserts `verify_release_sources` refuses each for exactly its two digests,
  so neither can be read as a record of a render.
- **No builder.** Nothing in the package assembles a release from a contract and a
  binding; the test suite does that with the package's digest and derivation functions.
  Assembling a release is the renderer's, and no renderer exists.

## What the checks caught before the first commit

- **A test compared a typed digest with a string** and failed; the assertion now
  compares text.
- **A test's assertion had the wrong precedence** — `assert a == b if c else d` asserts
  `d` when `c` is false — and was parenthesised after reading, before it ran.
- **The provenance-rules table test failed** until the document's section existed.
- **`ruff`** reformatted two files and sorted two import blocks and two `__all__` lists;
  **`mypy`** found one untyped dictionary literal in the suite.
- **This record miscounted.** Its first draft said a release has nineteen members that
  cannot be omitted; collecting the suite gave twenty-three — nineteen is the number of
  contract and binding values the mutation tests change. It was corrected before the
  commit.
- **A test variable was named `token`** and held a random-looking lowercase string, the
  shape gitleaks' generic rule looks for beside that word; it was renamed before any scan.

## Checks that the new tests are not decorative

Defects were put into the domain package one at a time, the domain suite was run
against each, and the file was restored byte for byte. The first ten were run before the
first commit and reproduced exactly by the reviewer. The last five are defects the review
showed that suite did not catch, or that were the code itself; all fifteen were run again
against the suite as it now stands, and every one is caught:

| Defect, exactly as made | At the first commit, of 259 | Now, of 281 |
|---|---|---|
| `sort_keys=False` in `canonical_json` | 57 failed | 77 failed |
| `ensure_ascii=True` in `canonical_json` | 2 failed | 2 failed |
| The float branch of the canonical check returns instead of raising | 4 failed | 4 failed |
| The canonical check's final `raise`, for a type JSON has no form for, becomes `return` | 6 failed | 6 failed |
| `contract_digest` hashes `contract.spec.as_document()` instead of the whole contract | 6 failed | 6 failed |
| `release_identity` drops `source.renderer` from the identity | 45 failed | 63 failed |
| The credential rule looks only at the start of a value: `starts = [0]` | 27 failed | 45 failed |
| The derivation check's condition becomes `False` | 10 failed | 11 failed |
| The environment check's condition becomes `False` | 2 failed | 2 failed |
| The parser's closed-object check accepts undefined fields: `undefined = []` | 22 failed | 22 failed |
| `_` left out of the credential rule's separators — the first commit's code | Not a defect then: `_` was absent, and 1 test failed when the reviewer added it | 11 failed |
| `LARGEST_EXACT_INTEGER = 2**53` instead of `2**53 - 1` | **Not caught** (reviewer) | 1 failed |
| `__import__('datetime').datetime.now()` at the top of `derive_release_id` | **Not caught** (reviewer) | 1 failed |
| The derivation refusal constructed without `context=context` | **Not caught** (reviewer) | 1 failed |
| The version pattern compiled without `re.ASCII` — the first commit's code | Not a defect then | 1 failed |

Three defects the reviewer reported as uncaught are left uncaught, and why: removing the
length clause in `parse_release_workload_version` changes only which error message a
too-long version gets; the two `apiVersion` comparisons in `verify_release_sources` cannot
fire while one version is recordable, which the document now says; and the list-index
branch of the refusal sort key was dead code, and was removed.

## Commands

Run from Git Bash, with `PYTHONDONTWRITEBYTECODE=1`, against the working tree with every
change staged, so that suites reading `git ls-files` saw the new files.

| Command | Result |
|---|---|
| `uv run --locked --offline --no-sync ruff format --check --no-cache .` | 557 files already formatted, after the two reformatted above. The first commit's record said 556; see the review section |
| `uv run --locked --offline --no-sync ruff check --no-cache .` | All checks passed |
| `uv run --locked --offline --no-sync python -B -m mypy` | No issues in 302 source files |
| `python -B -m pytest tests/domain/test_rendered_workload_release_domain.py tests/contracts/test_rendered_workload_release_v1alpha1.py -q -p no:cacheprovider` | 441 passed: 281 and 160 |
| `uv run --locked --offline --no-sync python -B -m pytest -q -rs -p no:cacheprovider --basetemp=<scratch>` — the full default lane | At the first commit: **16,208 passed, 33 skipped, 14 deselected, none failed**, in 14 min 41 s. After the review fixes: **16,230 passed, 33 skipped, 14 deselected, none failed**, in 12 min 51 s — the twenty-two new tests, and the same skips |
| `python -B -m tools.evidence_index --gate` | Exit 0; the six digests above, unchanged |
| `gitleaks dir <path> --config .gitleaks.toml --redact`, for the new suite, the new package, and the release document, with gitleaks 8.30.1 (the version the workflow pins) | No leaks found in any |
| `git diff --cached --check` | Exit 0, no output |

The 33 skips are host state and fixture layering, not passes, and none is in either
release suite: WorkloadContract fixtures that a structural-only or semantic-only check
skips by design, symbolic-link checks this Windows host does not permit, checks against
the pinned telemetry collector image, which is not present locally, and one POSIX signal
check — the same categories `V2-S1-002-PR1` recorded. The 14 deselections are the
cluster, real-runtime, failure, and load lanes, which the default marker expression
excludes. The workflow's separate gates — `helm lint`, kubeconform, the Terraform and
tflint checks, the expected-failure controls, the package build, and the image build —
were not run locally: this change touches no chart, Terraform configuration, manifest,
or workflow, and those gates run on the hosted workflow. The package build would include
the new domain package; it was not run here.

The full lane ran with this page already written except for its result row. That row and
this paragraph are the only edits made afterwards, and the suites that read this page —
the document links and the security baseline's reserved terms — were run again over it.

## What the independent review found

A reviewer read the first commit, `f36c5d8`, against the code, the change's brief, and
every document it touched. It reran the two release suites (419 passed) and the contract,
domain, documentation, and security suites (9,221 passed, 25 skipped). It reproduced all
ten mutation counts exactly and ran eleven defects of its own. It recounted the 23 members,
9 classes, 8 identity, 13 contract, and 6 binding mutations, the 7 rules, the 26 files, the
302 type-checked files, the eight allowlisted suites, and "fifty-three". It confirmed the
two-interpreter test runs on Windows, and found no local path, private name, email, later
story identifier, or credential in the diff. It found no defect in the canonical form's
handling of booleans, floats, dates, member names, or surrogates, or in the parser's
handling of the version's two forms. It reported:

- **High — the credential rule missed `_`, and the document's count was wrong.** A workload
  version can be a digest-pinned image reference, and that form's path admits `_`. The
  first commit's separators left `_` out, so `reg.io/app_sk-x@sha256:…` was not refused.
  Its suite never placed a prefix in the image reference form, so it counted **nine**
  reachable prefixes where there are **twenty-five**. The test meant to hold the separator
  set to the schema added the image form's separators by hand, so it confirmed itself. The
  same finding makes a `V2-S1-002-PR1` sentence false: "underscores … are refused wherever
  a string can be written", and "a GitHub or Hugging Face token" excluded, are both untrue
  of that one form, whose path takes a lowercase `ghp_…` or `hf_…` segment.
- **High/medium — "every string a release can hold is ASCII by its pattern" was not true
  in Python.** The version pattern uses `\d`. JSON Schema reads that as `[0-9]`; Python's
  `re` reads it as any Unicode digit. So the domain and the offline validator both
  accepted `1٣.0.0`, which a consumer in another language would refuse.
- **Medium — two live texts were left stale.** One valid fixture's header still said how a
  contract or a binding is hashed is not decided. The expected-rejections manifest still
  said the release has no semantic layer.
- **Medium — the clock claim was wider than its test.** The document said a test replaces
  "every clock and random function those modules offer". It replaces fourteen named ones.
  The reviewer added `datetime.now()` and `random.choice()` through `__import__`, and both
  passed.
- **Low.** The integer bound was not pinned, so `2**53` passed. The refusal sort key had a
  list-index branch no release path can reach. Nothing tested that a single-release
  refusal carries its context. The two `apiVersion` comparisons cannot fire, and the
  document listed them without saying so. The document claimed a digest round-trip test
  for every committed fixture, and it covered the contracts only. The record said 556
  formatted files where the reviewer counted 557, and said "eight modules" beside seven
  names. The refusal docstring named a `binding` role no refusal uses. One phrase pointed
  vaguely at requirements a reader cannot see.

## After the independent review

- **The credential rule's separators are `-`, `_`, `.`, `+`, `/`, `@`, and `:`.** The
  separator test now finds the admitted punctuation by asking each accepted form's own
  type, not by listing it. The placement tests add the image reference form, with and
  without an `_` before the prefix. The reachable-prefix test asserts all twenty-five, and
  that they are exactly the heuristic's lowercase prefixes. A new test asserts the schema
  accepts five underscore prefixes inside an image reference path and the domain refuses
  them. The release document's secrets section states all of this, and corrects
  `V2-S1-002-PR1`'s sentence in place, saying that it did.
- **The version pattern is compiled with `re.ASCII`**, so the domain refuses a non-ASCII
  digit. The offline validator still accepts one; a test measures that, and the release
  document says so where it used to claim every string was ASCII.
- **The fixture header and the manifest's layer description are corrected.** Neither
  changes a value, a refusal, or a release identifier.
- **The clock claim now says what is tested.** A new test asserts that no module in the
  package names `__import__`, `importlib`, `builtins`, `eval`, or `exec`. The document
  names the fourteen patched functions as fourteen, and says the import tests rule out
  the rest.
- **The integer bound is pinned as a literal.** The sort key is the field, rule, and
  reason. Both single-release rules are tested for context. Binding digests are
  round-tripped too. The two unreachable comparisons are stated as unreachable, beside a
  test that each source has one recordable version.
- **This record's counts are corrected.** 557 formatted files now. The first commit's run
  printed 556 and the reviewer counted 557 on a clean export of that commit; where the one
  file of difference came from was not established. "Eight modules" now names
  `__init__`. The phrase about requirements was replaced.
- **The mutation table** gains the five defects above, and all fifteen were run again.
- **Run again after the fixes:** `ruff format --check` (557 formatted), `ruff check`,
  `mypy` (302 files, no issues), gitleaks over every changed path (no leaks), `git diff
  --cached --check`, and the full default lane (16,230 passed); then the link and security
  suites over this page once its result rows were written.

## Privacy and publicability

The staged diff was read for private planning material, local paths, and credentials. It
names no private planning document or repository, no local filesystem path, no host or
account name, and no later story identifier. The only credential-shaped strings are
published prefixes followed by four zeros — some inside a synthetic image reference whose
digest is all zeros — and a fixed lowercase string with no published prefix; each is
labelled where it appears and matches no scanner rule. The record quotes one version with
a non-ASCII digit, which identifies nothing.

## What this does not establish

That any renderer will produce a release, that a values digest is the digest of any file,
that the renderer and platform-defaults revisions name commits that exist, or that a
release was ever rendered, installed, or run. Nothing produces a release.
