# V2-S1-001-PR2 validation

Date: 2026-09-29

What this change checked before it was committed, and how. What it adds is described in
[the EnvironmentBinding document](../../contracts/environment-binding.md), under
[rules across bindings, and selection](../../contracts/environment-binding.md#rules-across-bindings-and-selection);
this page is about the checks run over the repository after the domain package, its
tests, and the documents were written.

The change executed nothing against a host: no cluster, runtime, or model was contacted,
nothing was provisioned, and nothing was published. Every check below is static, which is
`C0` under [the evidence levels](../../testing/evidence-levels.md). It adds no record to
the evidence pack and moves no claim.

## Eligibility, checked before anything was written

- **The schema this change reads is merged.** `main` was at `fe45a1a`, the merge of
  `V2-S1-001-PR1`, which published the binding schema, its fixtures, and the structural
  validator.
- **The gate and the pack.** `python -m tools.evidence_index --gate` exited 0 with `FROZEN`
  for `V1-S5-013-PR2`, `RELEASED v1.0.0` with the set `1d40b33f…` and the pack
  `652e9051…`, and `CURRENT` with the set `08d4868f…` and the pack `b958a724…` — the six
  digests the previous change recorded. None of the files this change touches is cited by
  a record.
- **The WorkloadContract is the released one.** Its schema, fixtures, compatibility matrix,
  validator, and domain model are unchanged; this change imports two of the domain's
  types and adds nothing to them.

## What changed

- **A domain package.** `src/inferops/domain/environment/`: frozen typed objects for a
  binding (`binding.py`), the values they hold (`values.py`), the supported binding
  version (`versions.py`), the refusals and the published rule table (`errors.py`), a
  parser (`parsing.py`), and the rules across bindings and the selection for a contract
  (`selection.py`). The binding's environment is the WorkloadContract's own `Environment`
  type and its identifiers the same `DnsLabel`, rather than copies that could drift.
- **Five rule identifiers**, all under the existing `contract-invalid` code:
  `binding-identity-duplicated`, `binding-destination-overlaps`, `binding-not-found`,
  `binding-selection-ambiguous`, and `binding-environment-mismatch`. They live in the
  domain's own table, not in the offline validator's, because the validator reads one
  document and cannot apply them; a test holds the two tables apart and the document's
  table to the domain's.
- **Tests.** `tests/domain/test_environment_binding_domain.py`, 100 tests, inventoried in
  the `unit` layer with no claim and a written reason. `tests/testing/test_test_inventory.py`
  gained one number word, `fifty-one`, because its table stopped at fifty and this is the
  fifty-first module that defends no claim. The schema suite's rule-matrix test reads the
  document's single-document table from a new anchor sentence, because the old one — "No
  code and no rule identifier was added for it" — was no longer true of the binding as a
  whole and was rewritten to say "for a single document".
- **Documents.** The binding's document (status, the domain row, a new section with the
  rule table and the selection rule, the pending table reduced to what is still pending,
  the validation section, and the non-goals); the offline validator's module docstring,
  which said nothing applied the cross-document rules; the domain package docstring; the
  two contract indexes; both changelogs; the README's contracts row; the test inventory's
  data and page, including the schema suite's note, which said nothing reads a binding;
  and the proof index row that links here.

## What the change was asked to reach, and what it reached

| Asked | Reached here | How |
|---|---|---|
| Typed parsing with the accepted toolchain and canonical error conventions | Yes | `parse_environment_binding` reads the wire form into frozen objects with the standard library only, stops at the first problem, names a field and never a value, and attaches the canonical code by error type: `version-unsupported` for an unsupported or absent version, `contract-invalid` otherwise |
| Compatibility and version handling | Yes | `SUPPORTED_BINDING_VERSIONS` is its own constant, separate from the WorkloadContract's; the version is refused before any field below it is read; the `kind` check is what keeps a WorkloadContract, which declares the same `apiVersion`, from being read as a binding. A second binding version is an entry in that constant |
| Cross-field rules | Across documents, yes; within one binding, none | No rule relating two fields of one binding is grounded in a record. The one considered — which environments a local provider may serve — is not decided anywhere, and the document says the domain does not guess. The rules that exist relate a binding to other bindings and to a contract |
| Stable refusal categories | Yes | Two parse error types and five published rule identifiers, each with its code; no canonical code added |
| Tests proving the binding cannot own or override WorkloadContract semantics | Yes | Attribute and wire names of both trees compared; the shared key is the contract's type; five workload blocks written into a binding are each refused whole at `$.spec`; the serving replica count under `platform` is refused; selection returns a supplied binding as the same object, leaves the contract equal to itself, and reads only its environment |
| The model infrastructure-neutral where practical | Yes | No Kubernetes, Helm, Argo, or file-system import; the existing boundary suite covers the package, and the new suite asserts it imports only the standard library |
| WorkloadContract behaviour preserved | Yes | No WorkloadContract file changed; its schema, validation, domain, and scaffolding suites pass unchanged |

Against the parent story, after both of its changes:

| Parent-story criterion | State |
|---|---|
| A versioned schema and model with stable identifiers and compatibility rules | Met: the schema from the first change, the domain model and version handling from this one |
| Environment facts cannot silently override WorkloadContract-owned fields | Met at both layers: no shared field in either schema or in either domain tree, other than the environment key |
| Missing, malformed, unsupported, and conflicting bindings fail canonically | Met for the domain: malformed and unsupported by the parser and the validator, missing and conflicting by the five rules. Refusal at render time belongs to the renderer, which does not exist |
| Fixtures cover reference and negative cases | Met: the first change's two valid and eleven invalid fixtures, now also run through the parser. Set and selection cases are built in the tests from those fixtures rather than committed as fixtures, because a fixture is one document and each case is several |
| Domain objects avoid unnecessary Kubernetes and Argo coupling | Met |

## Decisions taken while writing, and what was left out on purpose

- **The selection rule.** The first change listed it as undecided. This change decides the
  smallest rule that never chooses: exactly one binding for the environment is selected
  without a name; more than one needs a name from the caller; a name found only in another
  environment is refused. The WorkloadContract has no field to carry a name, and adding
  one would change the released contract, so the name is the caller's.
- **Destination conflicts cross environments.** Two bindings writing generated state into
  one directory conflict whatever environments they serve. Directories are compared
  segment by segment, so `gitops/env` and `gitops/environments` do not conflict.
- **A conflicting set is not selected from**, even for a binding outside the conflict, so a
  caller cannot succeed on a set another caller would be refused on.
- **No credential heuristic for a binding.** The lowercase shapes the patterns cannot
  exclude are still accepted by the parser, as by the schema, and the first change's test
  that measures that gap is unchanged. Applying one would be a conditionally compatible
  change to single-document verdicts, and the validator, the bare schema, and the parser
  would have to change together.
- **No render context.** Selection returns a binding; it does not combine one with a
  contract into anything. That is the renderer's.
- **The offline validator and its command line were not extended.** They read one
  document; the new rules need several.
- **Parse errors carry a code; the WorkloadContract's do not.** The code is fixed by the
  error type, so carrying it costs nothing and spares a caller the mapping. The
  WorkloadContract's parse errors were left as they are.

## What the checks caught before the first commit

- **Two test defects, found on the first run of the new suite.** The attribute-name
  comparison descended into constrained string values and reported their shared `value`
  attribute as a name both trees own; it now stops at a value type. A determinism check
  compared two lists of exceptions with `==`, which compares identity; it now compares
  their dictionary forms.
- **Seven mypy errors at four sites.** A defensive runtime check on the bindings argument
  was typed so that mypy called its string and bytes branches unreachable (two); the helper
  now takes `object`. In the tests, a deliberate wrong-type call is now marked (one), a loop
  over argument tuples that mypy could not type was unrolled (three), and a dictionary
  index into an `object` was replaced by the attribute (one).
- **Four autofixable ruff findings** in the new tests, among them `SIM300` Yoda
  comparisons, fixed by ruff; two files reformatted.
- **The test inventory's number table stopped at fifty**, so the count test would have
  raised a key error for the fifty-first module rather than failing on a wrong word.
- **Two broken links**, to this page, from the changelog and the proof index, until this
  page existed.

## Checks that the new tests are not decorative

Seven edits were made to the domain package, the domain suite was run against each, and
the file was restored. Each edit was caught:

| Edit | Result |
|---|---|
| Accept `scaling`, a WorkloadContract field, under a binding's `spec` | 48 failed |
| Select the first binding when several serve the environment | 3 failed |
| Compare GitOps destinations as strings rather than directories | 2 failed |
| Raise the API replica ceiling to 32 | 2 failed |
| Select from a set that conflicts | 1 failed |
| Follow a named binding into another environment | 3 failed |
| Stop refusing a duplicated identity | 3 failed |

## Commands

Run from Git Bash, with `PYTHONDONTWRITEBYTECODE=1`, against the working tree with every
change staged, so that suites reading `git ls-files` saw the new files.

| Command | Result |
|---|---|
| `uv run --locked --offline --no-sync ruff format --check --no-cache .` | 541 files already formatted |
| `uv run --locked --offline --no-sync ruff check --no-cache .` | All checks passed |
| `uv run --locked --offline --no-sync python -B -m mypy` | No issues in 291 source files |
| `python -B -m pytest tests/domain/test_environment_binding_domain.py tests/contracts/test_environment_binding_v1alpha1.py -q -p no:cacheprovider` | 209 passed: 100 domain, 109 schema |
| `python -B -m pytest tests/contracts tests/domain tests/scaffolding tests/testing tests/security tests/architecture/test_domain_dependency_boundary.py -q -rs -p no:cacheprovider` | 9,268 passed, 25 skipped, 2 failed — the two links to this page, before it existed |
| `python -B -m tools.evidence_index --gate` | Exit 0; the six digests above, unchanged |
| `gitleaks dir <path> --config .gitleaks.toml --redact`, for each of the 20 files staged before this page existed, with gitleaks 8.30.1 (the version the workflow pins) | No leaks found in any. The new suite uses no credential-shaped value, so the secret-scanning allowlist document needed no change |
| `git diff --cached --check main` | Exit 0, no output |

The full default lane, the proof dashboard and evidence index checks, and a secret scan
covering this page were run after it was written; their results are below.

## Results after this page was written

| Command | Result |
|---|---|
| `uv run --locked --offline --no-sync python -B -m pytest -q -rs -p no:cacheprovider --basetemp=<scratch>` | **15,747 passed, 33 skipped, 14 deselected, none failed**, in 19 min 55 s |
| `python -B -m tools.proof_dashboard --check` | Exit 0: the dashboard is what the register produces |
| `python -B -m tools.evidence_index --check` | Exit 0: the index is what the register and the ledger produce |
| `python -B -m pytest tests/testing/test_document_links.py tests/testing/test_test_inventory.py tests/security -q -p no:cacheprovider` | 2,172 passed, with this page present |
| `git diff --cached --check main` | Exit 0, no output |
| `gitleaks dir <path> --config .gitleaks.toml --redact`, for each of the 22 files that differ from `main`, including this page and the schema suite whose anchor moved after the first scan | Exit 0 for every file: no leaks found |

A first full run was stopped before it finished, because the schema suite's anchor
sentence was edited while it ran; its tests were collected against the old text. (The
first commit's version of this page said it was stopped "after about two minutes"; it
was not timed, and the review pass removed the figure.) The run above started after every edit, with everything staged. It counts
125 more passes than the previous change's run: 100 are the new domain suite, and the
other 25 come from suites that parametrize over tracked files, documents, and inventory
entries, which this change adds to. That split is by subtraction; the 25 were not
enumerated one by one.

The 33 skips are the ones the previous change recorded, host state and fixture layering,
and none is in either binding suite: 25 WorkloadContract fixtures that a structural-only
or semantic-only check skips by design, four symbolic-link checks this Windows host does
not permit, three checks against the pinned telemetry collector image, which is not
present locally, and one POSIX signal check. The 14 deselections are the cluster,
real-runtime, failure, and load lanes. The workflow's separate gates — `helm lint`,
kubeconform, the Terraform and tflint checks, the expected-failure controls, the package
build, and the image build — were not run locally: this change touches no chart,
Terraform configuration, manifest, or workflow, and its one packaged addition is a
standard-library Python subpackage the default lane imports and type-checks.

## What the independent review found

A reviewer read the first commit, `60cc830`, against the code and the schema; reran the
two binding suites (209 passed, 100 and 109 by collection), the inventory, link, and
dependency-boundary suites (1,405 passed), and the domain, contract, scaffolding,
testing, security, and architecture directories (12,059 passed, 31 skipped, none
failed, every skip a documented host or fixture-layering one); reran `ruff check` and
mypy (clean, 291 source files); recounted the 22 changed files, the six `unit` modules,
the fifty-one modules without a claim, and the five rules against the document's table;
checked that no WorkloadContract file changed; read every refusal site for an
interpolated document value; swept the repository for statements this change made stale;
and grepped the diff for local paths, host and user names, and later story identifiers.
It found no critical, high, or medium defect, and two low ones:

- **A line-wrap slip** in `contracts/README.md`: two sentences joined onto one
  104-character line in a paragraph wrapped near 85.
- **The mutation table is not re-verifiable from the commit**, like the ruff and mypy
  counts before it. The reviewer did not rerun the mutations, since it was asked not to
  modify files, and instead read the tests it would rest on and found none vacuous.

It also noted that the new suite's import check reads only absolute imports; the
architecture suite's boundary check covers the whole package, so nothing is unchecked.
The two stale-sounding sentences it found are in the previous change's dated record and
changelog entry, which this project does not rewrite.

## After the independent review

- `contracts/README.md` is rewrapped.
- Rereading the page against the reviewer's notes found two statements of this change's
  own that said more than was measured. The first full run was described as stopped
  "after about two minutes", a figure nobody timed; it is removed above. The import
  check's docstring promised "no file-system dependency" while checking only for `os`
  and `pathlib` imports; it now says what it checks.
- The mutation table was not rerun; it stands as recorded, with the reviewer's reading as
  the corroboration it has.
- After these edits: `ruff format --check` (542 files already formatted) and `ruff check`
  clean; the two binding suites with the link, inventory, and security suites, 2,381
  passed; `gitleaks dir` over each of the three files this pass changed and
  `gitleaks git . --config .gitleaks.toml --redact` over the full history including
  `60cc830`, no leaks found; `git diff --cached --check`, no output. The full default lane
  was not rerun for a rewrap, a docstring, and this page.

## Privacy and publicability

The staged diff was read for private planning material, local paths, and credentials. It
names no private planning document or repository, no local filesystem path, no host or
account name, and no later story identifier; the one story identifier outside this story
and the previous one is `V1-S1-002`, in an existing line of context. The new tests carry
no credential-shaped string.

## What this does not establish

That any renderer will accept a selected binding, that the environment either fixture
describes is running, or that a release was ever installed with the values a binding
names. The domain reads bindings and chooses among them; nothing renders one.
