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

- **A domain package.** `src/inferops/domain/release/`, eight modules: typed values
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
- **Tests.** `tests/domain/test_rendered_workload_release_domain.py`, 259 tests,
  inventoried in the `unit` layer with no claim and a written reason. Four docstrings and
  one anchor sentence in the schema suite, `tests/contracts/test_rendered_workload_release_v1alpha1.py`,
  were corrected because they said the release has no semantic layer; its 160 tests and
  what they assert are otherwise unchanged. One number word was added to the inventory
  suite.
- **Unchanged:** the release schema, every release fixture and the expected-rejections
  manifest, the offline validator's verdicts (its module docstring was corrected), and
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
| Typed validation and canonicalisation helpers, with tests | Yes | `parse_rendered_workload_release`, `check_rendered_workload_release`, `verify_release_sources`, `canonical_json`, `canonical_sha256`, `contract_digest`, `binding_digest`, `derive_release_id`, and `canonical_release`; 259 tests |
| Uncontrolled timestamps and random IDs are absent from canonical content | Yes, for everything this package computes | The canonical form refuses dates, times, and floats rather than writing them; the package imports no clock or random module; a test makes every clock and random function fail while a release is recorded, checked, and verified; two interpreters under two hash seeds agree; the canonical form of each valid fixture and of its identity holds no date, time of day, or UUID; an underived identifier of the right shape is refused |
| Digest and reference formats are stable | Yes | A pinned value's canonical bytes and digest are held; the canonical form is the evidence index's byte for byte on the golden value and every committed contract, binding, and release fixture; key order, comments, flow style, blank lines, and an integral float move no source digest; the domain's patterns, bounds, and vocabularies are held to the schema |
| Source identities cannot be omitted | Yes | Removing any of the twenty-three members of a release — every object and every leaf — is refused by the parser at that member and by the schema; no attribute of the nine typed classes has a default |
| Claim-relevant source changes alter the appropriate provenance result | Yes | Eight identity members, one at a time, each move the identifier; two output members move the release and not its identifier; thirteen contract values and six binding values each move that document's digest and the identifier, and a release recorded before the change is refused with exactly that document's digest rule |
| Sensitive content is excluded or refused | Yes, with a measured remainder | The identity excludes the output and all document content; the typed tree has no attribute that could hold content, a time, or free text; nine reachable credential prefixes are refused in every position of the four fields that can hold one; the cost (`sk-demo` and `task-sk-demo`) and the remaining gap (a lowercase token with no published prefix) are asserted |

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
  has no digest, which is the order the requirements put validation and rendering in.
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
  measured a gap, so the same prefixes are applied at every part. The cost is measured.
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

Ten defects were put into the domain package one at a time, the domain suite was run
against each, and the file was restored byte for byte. Every defect was caught:

| Defect, exactly as made | Result, of 259 |
|---|---|
| `sort_keys=False` in `canonical_json` | 57 failed |
| `ensure_ascii=True` in `canonical_json` | 2 failed |
| The float branch of the canonical check returns instead of raising | 4 failed |
| The canonical check's final `raise`, for a type JSON has no form for, becomes `return` | 6 failed |
| `contract_digest` hashes `contract.spec.as_document()` instead of the whole contract | 6 failed |
| `release_identity` drops `source.renderer` from the identity | 45 failed |
| The credential rule looks only at the start of a value: `starts = [0]` | 27 failed |
| The derivation check's condition becomes `False` | 10 failed |
| The environment check's condition becomes `False` | 2 failed |
| The parser's closed-object check accepts undefined fields: `undefined = []` | 22 failed |

## Commands

Run from Git Bash, with `PYTHONDONTWRITEBYTECODE=1`, against the working tree with every
change staged, so that suites reading `git ls-files` saw the new files.

| Command | Result |
|---|---|
| `uv run --locked --offline --no-sync ruff format --check --no-cache .` | 556 files already formatted, after the two reformatted above |
| `uv run --locked --offline --no-sync ruff check --no-cache .` | All checks passed |
| `uv run --locked --offline --no-sync python -B -m mypy` | No issues in 302 source files |
| `python -B -m pytest tests/domain/test_rendered_workload_release_domain.py -q -p no:cacheprovider` | 259 passed |
| `uv run --locked --offline --no-sync python -B -m pytest -q -rs -p no:cacheprovider --basetemp=<scratch>` — the full default lane | **16,208 passed, 33 skipped, 14 deselected, none failed**, in 14 min 41 s |
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

## Privacy and publicability

The staged diff was read for private planning material, local paths, and credentials. It
names no private planning document or repository, no local filesystem path, no host or
account name, and no later story identifier. The only credential-shaped strings are
published prefixes followed by four zeros, and a fixed lowercase string with no published
prefix; each is labelled where it appears and matches no scanner rule.

## What this does not establish

That any renderer will produce a release, that a values digest is the digest of any file,
that the renderer and platform-defaults revisions name commits that exist, or that a
release was ever rendered, installed, or run. Nothing produces a release.
