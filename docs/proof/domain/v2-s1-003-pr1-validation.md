# V2-S1-003-PR1 validation

Date: 2026-10-01

What this change checked before it was committed, and how. What it publishes is in
[the renderer input boundary](../../domain/renderer-input-boundary.md); this page is about
the checks run over the repository after the package, its suite, and the document were
written.

The change executed nothing against a host: no cluster, runtime, or model was contacted,
and nothing was rendered, provisioned, written to Git, or published. Every check below is
static, which is `C0` under [the evidence levels](../../testing/evidence-levels.md). It
proves what the boundary admits and how it gathers its input, and nothing about a
deployment. It adds no record to the evidence pack and moves no claim.

## Eligibility, checked before anything was written

- **What it builds on is merged.** `main` was at `b670a04`, the merge of `V2-S1-002-PR2`,
  so the WorkloadContract domain and its semantic pipeline, the EnvironmentBinding domain
  and its selection rule, and the RenderedWorkloadRelease domain with its canonical form
  and source digests were all in place.
- **The gate and the pack.** `python -B -m tools.evidence_index --gate` exited 0 with
  `FROZEN` for `V1-S5-013-PR2`, `RELEASED v1.0.0` with the set `1d40b33f…` and the pack
  `652e9051…`, and `CURRENT` with the set `08d4868f…` and the pack `b958a724…` — the six
  digests `V2-S1-002-PR2` recorded. None of the files this change touches is cited by a
  record.

## What changed

- **`src/inferops/domain/render/`**, seven modules: `acceptance` (the validated contract
  and the ten profile conditions), `defaults` (versioned platform defaults), `ownership`
  (the 44-row ownership table, the eleven exclusions, and the empty override set),
  `normalization` (the render context and the boundary function), `renderer` (the
  interface), `errors` (the one refusal the boundary raises itself), and `__init__`.
- **`tests/domain/test_renderer_input_boundary.py`**: 59 test functions, 111 tests once
  parametrized.
- **[`docs/domain/renderer-input-boundary.md`](../../domain/renderer-input-boundary.md)**,
  the published document. Its ownership and profile-condition tables are compared with the
  code by the suite.
- **Statements this change made stale, corrected in place:** the EnvironmentBinding
  document's status line, its paragraph on what selection merges, its not-applied row, and
  its "does not do" item; the RenderedWorkloadRelease document's status line and "does not
  do" item; the contracts index's status, its binding row, and its paragraph on the schemas
  published before their consumer; the root README's contracts row; and the domain
  package's docstring.
- **The workload domain model's document** gains one paragraph: the profile conditions are
  not among its pipeline's rules. Nothing in the workload package, its tests, either schema,
  any fixture, or the offline validator changed.
- **Inventory:** the test inventory's data and page carry the module as the fifty-fifth
  with no claim, the unit lane's paragraph names it as the eighth domain module, and
  `NUMBER_WORDS` reaches 55.
- The changelog entry and the proof index's domain row.

## What the change was asked to reach, and what it reached

| Asked | Reached here | How |
|---|---|---|
| A pure renderer boundary consuming a validated WorkloadContract domain object | Yes | `validate_for_render` is the only producer of a `ValidatedWorkloadContract`; `build_render_context` refuses anything else with a `TypeError` |
| Versioned platform defaults | Yes, three settings | `PlatformDefaults` `v1alpha1`: version, full revision, and three API-tier settings whose bounds and defaults are the chart's |
| A validated EnvironmentBinding | Yes | The binding is chosen by the binding domain's own set rules and selection; a raw document is refused |
| Explicit ownership and precedence metadata | Yes | `RENDER_FIELD_OWNERSHIP` (44 rows, one owner each), `EXCLUDED_SOURCE_FIELDS` (11, each with a reason), and `OVERRIDES` (empty: no layer overrides another) |
| A normalized render context | Yes | `RenderContext`: every value with its owner and source, read-only, sorted, with the input identities a release records and a canonical digest |
| No Git writes, `kubectl`, Helm, cluster discovery, network, or wall clock | Yes | Seven standard-library imports, no dynamic import route, a run with every clock, random source, and `os.getenv` failing, and nothing outside the domain imports the package |
| Tests that raw or unvalidated input cannot use the supported path | Yes | Raw contracts, defaults, and bindings, and a parsed contract that skipped validation, are each refused; a contract failing a semantic rule or a profile condition is refused with every finding |

### The parent story's acceptance criteria

| Criterion | State | Where |
|---|---|---|
| The supported renderer accepts validated typed inputs rather than arbitrary raw dictionaries | Met for the boundary; no renderer exists yet | This change |
| Workload intent, platform defaults, and environment binding have explicit ownership and precedence | Met | This change |
| Incompatible ownership fails before output | **Pending.** No input can attempt it today — no layer has a field for another's value — and detecting an attempt is not built | A later change |
| Unsupported profile or version, and a missing binding, fail canonically | **Pending.** Each is refused today with the vocabulary it already has — the selection rules for a binding, construction for a defaults version — and no canonical render code exists | A later change |
| The renderer remains separate from GitOps and Kubernetes application | Met for the boundary: it imports nothing that could apply anything, and nothing on a delivery path imports it | This change |

## Decisions taken while writing, and what was left out on purpose

- **Precedence is "none", not an order.** The binding schema already has no field for a
  contract value. Extending that to the defaults made a precedence order unnecessary, and
  an empty override set is testable where a precedence order would have to be defended
  case by case.
- **Semantic names.** A context value is named for what it means (`api.replicas`) rather
  than where it was read (`spec.platform.apiReplicas`), so two layers claiming the same
  meaning would collide on one name — the property conflict detection will need.
- **The profile conditions live in the render package.** The gap is in the workload
  pipeline, and changing that pipeline would change a component outside this change's
  boundary. A test asserts the pipeline still accepts all nine mutations, so the day it
  gains the rules, the duplicate fails loudly instead of lingering.
- **Field addresses follow the pipeline.** Profile-condition findings drop the published
  validator's `$.` prefix to sit beside the pipeline's findings in one refusal; the parity
  test compares after the same normalisation.
- **Three defaults, not the chart's every setting.** Each is a chart value, outside both
  schemas, and the same in every committed values file. More would decide the defaults
  layer's shape ahead of the change that renders it.
- **No defaults file and no defaults digest.** A release names defaults by revision alone,
  so the context does too, and the limit that two value sets can share one revision is
  asserted rather than papered over.
- **No render refusal codes.** A vocabulary with no refusal that needs it yet would be
  guessed; the refusals keep the contract, binding, and value vocabularies they have.
- **The guard's limit is recorded.** A test forges a validated contract by importing the
  private sentinel, and the document says the guard stops accidents, not intent.

## What the checks caught before the first commit

Each was found by running the suite or the linters, and fixed before anything was
committed:

- The suite asserted the binding document's "may not carry" table had nine rows; it has
  ten (`spec.mockLlm` was missed). The table was right and the test was corrected.
- The same test matched `spec.model` against the binding's `spec.modelCache` by a bare
  string prefix; it now compares segment by segment.
- The suite rendered the `synchronous-llm-secret-refs` fixture with the `local`
  bindings, but that fixture serves `dev`; selection refused it, as it should. The suite
  now builds a `dev` binding for it, as it builds a `ci` one for the mock.
- The check that nothing outside the domain imports the package first matched
  `from .render import` in `tools/inference_alerts`, an unrelated module of the same name.
  The pattern now names the domain package only.
- `ruff` flagged one comparison style, and `mypy` four typing faults in the suite, all
  in test code; none was in the package.

## Checks that the new tests are not decorative

Thirteen defects were planted in the package, one at a time, the suite run in full, and
the file restored byte for byte (its SHA-256 checked afterwards). Every one was caught:

| Defect, exactly as made | Of 111 |
|---|---|
| The mock proof-reference condition is assigned to `synchronous-llm` instead | 38 failed |
| `validate_for_render` drops the semantic pipeline's findings | 2 failed |
| `model.ref` is read from `spec.model.runtimeProfile` | 3 failed |
| `OVERRIDES` lets the binding override workload intent | 1 failed |
| The validated contract's sentinel check becomes `if False` | 1 failed |
| The context keeps table order instead of sorting by name | 4 failed |
| `OUTPUT_TOKENS_CEILING` becomes 65536 | 1 failed |
| The boundary takes `bindings[0]` instead of selecting | 12 failed |
| `build_render_context` reads `time.time()` | 2 failed |
| The binding digest is taken of `bindings[0]` | 4 failed |
| `evidence.proofRefs` is marked always present | 10 failed |
| `metadata.owner` is dropped from the binding exclusions | 1 failed |
| The boundary also accepts an unvalidated `WorkloadContract` | 35 failed |

Four defects are caught by exactly one test each. That test is the one written for the
property, and the count is stated so nobody reads 111 tests as 111 guards on each.

## Commands

Run from Git Bash on Windows, with the locked environment.

| Command | Result |
|---|---|
| `uv run --locked ruff check .` | All checks passed |
| `uv run --locked ruff format --check .` | 568 files already formatted |
| `uv run --locked mypy` | No issues in 311 source files |
| `uv run --locked python -m pytest tests/domain/test_renderer_input_boundary.py -q -p no:cacheprovider` | 111 passed |
| `uv run --locked python -m pytest tests/domain tests/architecture tests/contracts tests/testing tests/security -q -p no:cacheprovider` | 12,352 passed, 31 skipped, and 2 failed: the link checks of the changelog and the proof index, which pointed at this record before it was written. Both resolve once it exists |
| `python -B -m tools.evidence_index --gate` | Exit 0; the six digests above, unchanged |
| `gitleaks dir <path> --config .gitleaks.toml --redact`, for the new package, the new suite, and the new document, with gitleaks 8.30.1 (the version the workflow pins) | No leaks found in any |
| `git diff --cached --check` | Exit 0, no output |

**Not run before the first commit:** the full default lane. It runs after the commit, so
the link suite collects the new files, and its result is recorded with the independent
review.

## Privacy and publicability

The diff was read for private planning material before committing: no planning document,
prompt, private requirement identifier, later story identifier, local path, account
identifier, credential, or model artifact appears in it. The only identifiers it names are
this change's and earlier ones. The suite uses no synthetic credential, so the secret-scanning
allowlist is unchanged.

## What this does not establish

- That anything is rendered. No renderer exists, no values file or release is written,
  and `deployment-values-derive-only-from-a-validated-document` stays planned.
- That a defaults revision names the values a caller supplied, or that the cluster,
  namespace, and claim a selected binding names exist.
- That the profile conditions are applied anywhere but on the way into a render. The
  workload pipeline still accepts every one, as a test asserts.
- That the offline validator and the domain agree on every document. The parity this
  change measured is on the profile conditions and the committed fixtures, not on every
  possible document.
