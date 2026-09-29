# V2-S1-002-PR1 validation

Date: 2026-09-29

What this change checked before it was committed, and how. What it publishes is in
[the RenderedWorkloadRelease document](../../contracts/rendered-workload-release.md);
this page is about the checks run over the repository after that document, the schema,
and the fixtures were written.

The change executed nothing against a host: no cluster, runtime, or model was contacted,
nothing was rendered, provisioned, or published. Every check below is static, which is
`C0` under [the evidence levels](../../testing/evidence-levels.md). It adds no record to
the evidence pack and moves no claim.

## Eligibility, checked before anything was written

- **The documents a release names are merged.** `main` was at `5334bb0`, the merge of
  `V2-S1-001-PR2`, so the EnvironmentBinding schema, its fixtures, and its platform domain
  were all in place, and the WorkloadContract is the released one.
- **The gate and the pack.** `python -m tools.evidence_index --gate` exited 0 with
  `FROZEN` for `V1-S5-013-PR2`, `RELEASED v1.0.0` with the set `1d40b33f…` and the pack
  `652e9051…`, and `CURRENT` with the set `08d4868f…` and the pack `b958a724…`. None of the
  files this change touches is cited by a record, so all three pairs stayed where they were,
  and the same command after the change printed the same six digests.

## What changed

- **The schema.** `contracts/release/rendered-workload-release.v1alpha1.schema.json`:
  `apiVersion` `inferops.io/v1alpha1`, `kind` `RenderedWorkloadRelease`; `metadata`
  (`workloadId`, `workloadVersion`, `releaseId`), `source` (`contract` with `apiVersion`
  and `sha256`; `environmentBinding` with `apiVersion`, `environment`, `name`, and
  `sha256`; `renderer.revision`; `platformDefaults.revision`), and `output.helmValues`
  (`path`, `sha256`). Every object is closed and every member required. There is no
  `spec` and no `status`.
- **Fixtures.** Two valid releases, one per committed binding fixture for the committed
  synchronous contract fixture, and fifteen invalid ones with a manifest of thirty-one
  expected findings.
- **A validator module.** `tools/contract_validation/rendered_workload_release.py`
  applies the schema and translates each failure through the canonical error model,
  exactly as the binding's module does. It adds no rule and no code, and the
  WorkloadContract and EnvironmentBinding validators are untouched.
- **Tests.** `tests/contracts/test_rendered_workload_release_v1alpha1.py`, 160 tests,
  inventoried in the `contract-and-schema` layer with no claim and a written reason.
- **Documents.** The release's own document and its fixtures' README; the two contract
  indexes, the contract package changelog, the project changelog, the README's contracts
  row, the test inventory's data and page, the proof index row that links here, the
  EnvironmentBinding document's sentence on where a binding's digest is recorded, and the
  secret-scanning allowlist document.

## What the change was asked to reach, and what it reached

| Asked | Reached here | How |
|---|---|---|
| A versioned, machine-readable release artifact | Yes | `apiVersion` + `kind`, a draft 2020-12 schema with an `$id`, three compatibility classes and the no-break-without-a-new-version rule in the document |
| It records workload identity, contract digest, renderer revision, platform-default revision, environment binding, release ID, and generated-values digest | Yes, as fields | Thirteen leaf fields, every one required; the document's field table is compared with the schema by a test. Nothing checks that any digest is the digest of what it names — see the pending rows below |
| Documented as a repository artifact, not a custom resource | Yes | A section of the document; no `spec` or `status`; a test fails if any chart, manifest, or infrastructure file mentions the kind |
| Canonical output contains no uncontrolled timestamp or random release ID | **In part** | No field can hold a timestamp, and every string pattern refuses RFC 3339 and HTTP dates. The release ID is defined as a derivation and the schema refuses a UUID, but it accepts any 64 hexadecimal characters: that an ID was derived is **pending**, and a test asserts the gap. Canonical serialisation of a whole release is **pending**: nothing produces one |
| Sensitive data cannot enter provenance | **In part** | Every object is closed and every string is a lowercase pattern or a vocabulary, so credential fields and the uppercase, underscore, and mixed-case shapes are refused structurally. Lowercase credential shapes in four fields, and a credential that is itself a hexadecimal string of a digest's length, are **not** refused; each is measured and asserted. A semantic credential rule is **pending** |
| Malformed digests and identifiers rejected | Yes | `value-malformed`, `value-out-of-range`, `value-not-permitted`, and `value-wrong-type`, each with fixtures: uppercase, prefixed, and short digests; a branch, a tag-like label, and an abbreviated commit; non-DNS identifiers; an over-long identifier; a values path with a directory |
| Compatibility and validation rules tested | Yes, for a single document | Every rule has a fixture except the fallback; the recordable source versions, identifiers, version forms, and environment vocabulary are held to the other two schemas; neither other schema accepts a release, and a release accepts neither's fixtures |

Canonicalisation helpers, digest computation, derivation enforcement, the credential rule,
and the mutation tests over provenance are not part of this change and are left to a later
one. So is every rule in the document's
[not-applied table](../../contracts/rendered-workload-release.md#rules-that-are-not-applied-yet).

## Decisions taken while writing, and what was left out on purpose

- **The release ID is derived, and the rule is written now.** A field whose meaning is left
  open is a field every producer fills differently. The rule hashes the release's workload
  identity and `source` block in the canonical JSON form `tools/evidence_index` already uses
  for register entries — keys sorted, compact separators, UTF-8 — rather than a new form.
  The output is deliberately not part of it, so a non-deterministic renderer shows up as
  one identifier with two values digests. The schema does not apply the rule; the fixtures
  follow it and a test recomputes it for each.
- **Digests are bare lowercase hexadecimal** under a field named `sha256`, the form the
  evidence index stores, rather than the `sha256:`-prefixed form the WorkloadContract uses
  for image digests. One accepted spelling per digest is what lets two releases be
  compared as text.
- **Revisions are full 40-character commits.** Branches, tags, and abbreviations can move
  or collide. A repository using SHA-256 object names would need a relaxed pattern, which
  is a compatible change.
- **How a document is hashed is not decided.** Each digest's description says so. Deciding
  it needs the code that produces digests, and the choice — whether comments or key order
  move a digest — is that code's.
- **The workload version is narrower than the contract's**: no uppercase in a semantic
  version's pre-release or build, and at most 128 characters. It keeps uppercase credential
  shapes out of provenance, following the precedent of the binding's claim name. The cost is
  measured: a test shows `1.0.0-RC.1` is a valid contract version that no release can
  record, and another that every committed contract fixture's version fits.
- **The binding is referenced by environment, name, and digest.** Its identity is the
  pair, and it has no revision field, so the digest is the only record of which content
  was used.
- **The values path is a bare file name** in the release's own directory, as the release
  and the values it describes sit together. Where that directory lives is not decided.
- **The digests in the valid fixtures are single repeated characters.** Real digests of the
  committed contract and binding fixtures would have meant choosing how to hash them,
  which is left open above, and a plausible-looking digest of nothing would read as a
  record of a render. A test holds each to one repeated character.
- **No owner field.** A release's owner is its workload's, read from the contract it names.
- **The command-line validator was not extended**, and the continuous-integration gate
  that runs it over the WorkloadContract's fixtures was not given the release's. The
  release fixtures run in the default pytest lane. The document says so.

## What the checks caught before the first commit

- **A test's false positive, fixed in the fixture.** The check that no refusal quotes a
  document value flagged `unsupported-vocabulary.yaml`: its binding version was
  `inferops.io/v1`, which is a prefix of the permitted value `inferops.io/v1alpha1` that
  the refusal legitimately prints. The value was changed to `inferops.io/v2alpha1`; the
  finding it produces is the same.
- **A schema description decided something it should not have.** The values digest was
  first described as "the digest of the values file's bytes as written", which decides the
  hashing question the document leaves open. It now says, like the other two digests, that
  how it is computed is not decided. This was corrected before any test ran.
- **The secret-scanning allowlist document undercounted before this change.** It said five
  test suites use the synthetic credential values; six tracked suites did, because
  `tests/domain/test_workload_validation.py` was never listed. This change adds a seventh,
  so the document now says seven and describes the missing one. That suite's zero-padded
  values are shorter than the allowlisted forms and match no pattern rule; gitleaks
  reports nothing in it, so no rule was added. The binding suite's entry also said its
  `gldt-` value "appears nowhere else", which this change's suite made false; it now names
  both.
- **Two files reformatted** by `ruff format`, the validator module and the suite.
- **Two broken links**, to this page, from the changelog and the proof index, until this
  page existed.
- **The expected-rejections manifest was generated from the validator's output**, not
  written by hand. Every entry was then compared with the refusal each fixture's header
  states it is for, and all thirty-one agree; that comparison was by reading, and a
  reviewer should repeat it rather than trust the generation.

## Checks that the new tests are not decorative

Nine edits were made to the schema, the release suite was run against each, and the
schema was restored byte for byte. Each edit was caught:

| Edit | Result |
|---|---|
| Add an optional `metadata.generatedAt` string | 16 failed |
| Open the `output` object | 1 failed |
| Accept uppercase hexadecimal in every digest | 1 failed |
| Accept an abbreviated revision of 7 to 40 characters | 1 failed |
| Accept a UUID-shaped release identifier | 3 failed |
| Add `prod` to the environment vocabulary | 2 failed |
| Add a required `status` block at the top level | 42 failed |
| Accept uppercase in a semantic version, as the contract does | 4 failed |
| Accept a values path with directories and dots | 2 failed |

## Commands

Run from Git Bash, with `PYTHONDONTWRITEBYTECODE=1`, against the working tree with every
change staged, so that suites reading `git ls-files` saw the new files.

| Command | Result |
|---|---|
| `uv run --locked --offline --no-sync ruff format --check --no-cache .` | 546 files already formatted, after the two reformatted above |
| `uv run --locked --offline --no-sync ruff check --no-cache .` | All checks passed |
| `uv run --locked --offline --no-sync python -B -m mypy` | No issues in 293 source files |
| `python -B -m pytest tests/contracts/test_rendered_workload_release_v1alpha1.py -q -p no:cacheprovider` | 160 passed |
| `python -B -m pytest tests/contracts tests/domain tests/scaffolding tests/testing tests/security tests/serving -q -rs -p no:cacheprovider` | 10,344 passed, 27 skipped, 2 failed — the two links to this page, before it existed |
| `python -B -m tools.evidence_index --gate` | Exit 0; the six digests above, unchanged |
| `gitleaks dir <path> --config .gitleaks.toml --redact`, for each of the 34 files staged before this page existed, and for `tests/domain/test_workload_validation.py`, with gitleaks 8.30.1 (the version the workflow pins; the Windows archive's SHA-256 checked against the release's checksum list) | No leaks found in any |

The full default lane, the proof dashboard and evidence index checks, a scan of this page,
and `git diff --check` were run after this page was written;
[their results](#results-after-this-page-was-written) are below.

## Results after this page was written

| Command | Result |
|---|---|
| `uv run --locked --offline --no-sync python -B -m pytest -q -rs -p no:cacheprovider --basetemp=<scratch>` | **15,922 passed, 33 skipped, 14 deselected, none failed**, in 14 min 6 s |
| `python -B -m tools.proof_dashboard --check` | Exit 0: the dashboard is what the register produces |
| `python -B -m tools.evidence_index --check` | Exit 0: the index is what the register and the ledger produce |
| `gitleaks dir docs/proof/contracts/v2-s1-002-pr1-validation.md --config .gitleaks.toml --redact` | No leaks found |
| `git diff --cached --check` | Exit 0, no output |

The 33 skips are host state and fixture layering, not passes, and none is in the release
suite: 25 WorkloadContract fixtures that a structural-only or semantic-only check skips by
design, four symbolic-link checks this Windows host does not permit, three checks against
the pinned telemetry collector image, which is not present locally, and one POSIX signal
check. The 14 deselections are the cluster, real-runtime, failure, and load lanes, which
the default marker expression excludes. Helm was on this host's path, so the chart's
render tests inside the suite ran rather than skipped. The workflow's separate gates —
`helm lint`, kubeconform, the Terraform and tflint checks, the expected-failure controls,
the package build, and the image build — were not run locally: this change touches no
chart, Terraform configuration, manifest, workflow, or packaged source outside the offline
validator, and those gates run on the hosted workflow.

This section was written after the full run, which is the only edit the change received
afterwards. The suites that read this page — the document links and the security
baseline's reserved terms — were run again over it: `python -B -m pytest tests/testing
tests/security -q -p no:cacheprovider` passed.

## Privacy and publicability

The staged diff was read for private planning material, local paths, and credentials. It
names no private planning document or repository, no local filesystem path, no host or
account name, and no later story identifier. The only credential-shaped strings are the
published AWS placeholder key identifier, the public JWT header, a fixed synthetic
mixed-case string, and zero-padded synthetic tokens; each is labelled where it appears, and
the fixtures outside the scanner's exempted directories carry only values an existing
pattern rule covers. The UUID, the abbreviated commit identifier, and the placeholder
digests and revisions identify nothing.

## What this does not establish

That any renderer will produce a release, that any digest in either valid fixture is the
digest of anything, that the release identifier rule will be enforced as written, or that a
release was ever rendered, installed, or run. Nothing produces or reads a release.
