# V2-S1-003-PR2 validation

Date: 2026-10-01

What this change checked before it was committed, and how. What it publishes is in
[the renderer input boundary](../../domain/renderer-input-boundary.md#what-a-render-is-refused-with);
this page is about the checks run over the repository after the code, its suite, and the
document were written.

The change executed nothing against a host: no cluster, runtime, or model was contacted,
and nothing was rendered, provisioned, written to Git, or published. Every check below is
static, which is `C0` under [the evidence levels](../../testing/evidence-levels.md). It
proves what a render is refused with and that a refused render produces nothing, and
nothing about a deployment. It adds no record to the evidence pack and moves no claim.

## Eligibility, checked before anything was written

- **What it builds on is merged.** `main` was at `7f80ad9`, the merge of `V2-S1-003-PR1`,
  so the render package, its ownership table, its profile conditions, and its context
  were in place, beside the workload, binding, and release domains.
- **The gate and the pack.** `python -B -m tools.evidence_index --gate` exited 0 with
  `FROZEN` for `V1-S5-013-PR2`, `RELEASED v1.0.0` with the set `1d40b33f…` and the pack
  `652e9051…`, and `CURRENT` with the set `08d4868f…` and the pack `b958a724…` — the six
  digests `V2-S1-003-PR1` recorded. None of the files this change touches is cited by a
  record.

## What changed

- **`src/inferops/domain/render/`**, two new modules and four changed. `errors` now holds
  the refusal vocabulary: seven categories, the 21-rule table, `RenderFinding`, and
  `RenderRefused`. `conflicts` (new) refuses an input that supplies a value it does not own.
  `support` (new) holds `RendererSupport`. `normalization` refuses a selection failure and an
  ownership conflict canonically in `build_render_context`, and adds `prepare_render`.
  `renderer` gives the interface a `support` and adds `render_with`. `ownership` loses the
  sentence that called conflict detection a later change. The package is nine modules.
- **`tests/domain/test_renderer_refusals.py`** (new): 54 test functions, 264 tests
  once parametrized.
- **`tests/domain/test_renderer_input_boundary.py`**: three of its tests changed, because
  the behaviour they pinned changed on purpose. The selection test asserted the binding
  domain's error passed through unchanged; it now asserts a render refusal under the same
  rule identifier and field, categorised `binding-missing`. The module count went from seven
  to nine. The conforming test renderer gained a `support`, and the non-conforming one now
  has a render method and lacks only that, so it fails on the new member alone. Still 119
  tests.
- **[`docs/domain/renderer-input-boundary.md`](../../domain/renderer-input-boundary.md)**:
  the refusal model, the refusal matrix, the ownership-conflict rule, the field-ownership
  matrix for the reference workload, and the renderer's declared support are new sections.
  The status line, the property table, the path, the precedence paragraph, the renderer
  interface, the "refused today" table, the "not applied yet" table, and "does not
  establish" are corrected in place. Both matrices are compared with the code by the suite.
- **Statements this change made stale, corrected in place:** the binding document's
  paragraph on what selection merges, the contracts index's status, and the test inventory's
  entry for the boundary suite, which said a selection refusal passes through unchanged.
- **Inventory:** the test inventory's data and page carry the new module as the
  fifty-sixth with no claim, the unit lane's paragraph names it as the ninth domain module,
  and `NUMBER_WORDS` reaches 56.
- The changelog entry and the proof index's domain row.

Nothing in the workload, binding, or release packages, either schema, any fixture, the
offline validator, or the API changed.

## What the change was asked to reach, and what it reached

| Asked | Reached here | How |
|---|---|---|
| Refusal for a missing binding | Yes | The binding domain's three selection rules, categorised `binding-missing`; one test input each |
| Refusal for an unsupported profile or version | Yes, for a renderer's declaration | `RendererSupport`; four `render-*` rules for the contract, binding, and defaults versions and the profile. No renderer exists, so every declaration is a test's |
| Refusal for an incompatible model and runtime selection | Yes | The workload pipeline's three compatibility-matrix rules, categorised `model-runtime-incompatible` |
| Refusal for ownership conflicts among contract, defaults, and binding | Yes | `render-ownership-conflict` and `render-value-unowned` over every leaf of all three inputs; 88 cross-layer cases. No parsed input reaches it today, and a test says so |
| Stable, actionable errors | Yes | A category, a canonical code, a rule identifier, a role-prefixed field, and a reason per finding, sorted; non-retryable; request context carried; no input value repeated |
| No partial committed output | Yes | A refused render never calls the renderer, for every rule; the package writes nothing |
| A field-ownership matrix for the reference workload | Yes | 44 rows, compared with the context the reference inputs produce |
| No silent last-value-wins | Yes | A value supplied by a second layer refuses the render, neither value chosen |

### The parent story's acceptance criteria

| Criterion | State | Where |
|---|---|---|
| The supported renderer accepts validated typed inputs rather than arbitrary raw dictionaries | Met for the boundary and the canonical path; no renderer exists | `V2-S1-003-PR1`, and this change for `prepare_render` and `render_with` |
| Workload intent, platform defaults, and environment binding have explicit ownership and precedence | Met | `V2-S1-003-PR1`, and the reference matrix here |
| Incompatible ownership fails before output | Met | This change |
| Unsupported profile or version, and a missing binding, fail canonically | Met, against a renderer's declared support | This change |
| The renderer remains separate from GitOps and Kubernetes application | Met for the boundary: it imports nothing that could apply anything, and nothing on a delivery path imports it | `V2-S1-003-PR1`, re-run here |

## Decisions taken while writing, and what was left out on purpose

- **Categories are a third dimension, not new codes.** The canonical code is coarse by
  design and does not grow with rules, so it cannot tell a missing binding from an
  ownership conflict. A category per rule does, without touching the code vocabulary.
- **Reuse before adding.** Fifteen of the 21 rules are identifiers the workload contract or
  the binding domain already publish, with their codes. A second name for the same refusal
  would be two vocabularies for one fact.
- **`capability-unavailable` for an unsupported profile.** The contract is valid and its
  version supported; the renderer lacks the capability. ADR 0010 already answers a
  capability never built that way, non-retryable. It is the first domain refusal beyond the
  two offline codes, and the boundary document says so and why.
- **No policy category.** Nothing can refuse on policy. A category with no rule would be a
  claim that something checks.
- **Profile and version are separate categories.** The requirement groups them; an operator
  fixes them differently, so the matrix keeps them apart.
- **Ownership is checked on every leaf, not only on the table's paths.** Checking only the
  table's own sources would never find a value the table does not know about, which is the
  case that matters when an input gains a field.
- **A shared path means the input's own thing.** A binding's `metadata.name`,
  `metadata.owner`, and `spec.environment` are its own name, owner, and selection key, not
  claims on the workload's.
- **Support is declared by the renderer and may name a version the domain does not
  implement.** That is also how the version refusals are reachable while the domain
  implements one version of each input.
- **`build_render_context` changed its refusal.** It raised the binding domain's error
  unchanged; it now raises `RenderRefused`. The package has no consumer outside the
  domain, so nothing else had to change.

## What the checks caught before the first commit

Each was found by running the suite or the linters, and fixed before anything was
committed:

- The first draft of the test that no reason repeats an input value counted the inputs'
  field names as values. Field names such as `environment` and `platform` appear in the
  reasons on purpose, so the case of every rule whose inputs held such a name failed. The
  test now compares string values only, as the contract document's own check does.
- A docstring in the new suite said it covered "the nine mutations" when the test exercises
  two. It now says what it covers.
- `ruff` flagged import order in two modules and asked for a PEP 695 type parameter on
  `render_with`; `mypy` found three typing faults in the new suite. None was in behaviour.

## Checks that the new tests are not decorative

Fourteen defects were planted in the package, one at a time, before the first commit. Each
edited file was compiled before the suites ran, so no row below measures a `NameError` or
an import failure instead of its defect, and none of the runs raised one. Both render
suites, 383 tests, were run in full against each defect, and the file was restored byte for
byte, its SHA-256 checked afterwards. Every one was caught:

| Defect, exactly as made | Of 383 |
|---|---|
| `conflicts`: the owner check becomes `claimed.layer is layer`, so a value another layer owns is reported as unowned | 131 failed |
| `conflicts`: an empty object is walked into instead of being a leaf (`or not value` removed) | 1 failed |
| `conflicts`: the layer loop iterates over `()`, so the check finds nothing | 143 failed |
| `conflicts`: a value is claimable by its name only, not by its source path | 43 failed |
| `errors`: `render-profile-unsupported` carries `contract-invalid` | 3 failed |
| `errors`: `binding-selection-ambiguous` is categorised `semantic-invalid` | 3 failed |
| `errors`: findings sort by field, ignoring category | 1 failed |
| `errors`: the refusal's code is its last finding's | 1 failed |
| `errors`: a contract finding loses its `contract.` prefix | 1 failed |
| `normalization`: `prepare_render` drops the contract's own findings (`pass` in the handler) | 34 failed |
| `normalization`: `prepare_render` does not check the selected binding's version | 4 failed |
| `normalization`: `build_render_context` skips the ownership check | 2 failed |
| `support`: the profile check becomes `if False` | 7 failed |
| `renderer`: `render_with` builds a support from the inputs instead of the renderer's own | 4 failed |

Four defects are caught by exactly one test each. That test is the one written for the
property, and the count is stated so that nobody reads 264 new tests as 264 guards on each
property.

## Commands

Run from Git Bash on Windows, with the locked environment.

| Command | Result |
|---|---|
| `uv run --locked ruff check .` | All checks passed |
| `uv run --locked ruff format --check --no-cache .` | 572 files already formatted |
| `uv run --locked mypy` | No issues in 314 source files |
| `uv run --locked python -m pytest tests/domain/test_renderer_refusals.py tests/domain/test_renderer_input_boundary.py -q -p no:cacheprovider` | 383 passed: 264 and 119 |
| `uv run --locked python -m pytest tests/testing/test_test_inventory.py -q -p no:cacheprovider` | 1,071 passed |
| `python -B -m tools.evidence_index --gate` | Exit 0; the six digests above, unchanged |
| `gitleaks dir <path> --config .gitleaks.toml --redact`, for the render package, both suites, the boundary document, the changelog, the inventory page, and the contracts documents, with gitleaks 8.30.1 (the version the workflow pins) | No leaks found in any |
| `git diff --cached --check` | Exit 0, no output |

**The full default lane ran before the first commit**, with the new files registered with
Git so the link suite collected them:
`uv run --locked python -B -m pytest -q -rs -p no:cacheprovider --basetemp=<scratch>` gave
**16,701 passed, 33 skipped, 14 deselected, none failed**, in 8 min 33 s. The skips are the
ones earlier records name, such as symbolic links this host does not permit. The record's
own text was completed after that run; the link suite was run again over it.

## Privacy and publicability

The diff was read for private planning material before committing: no planning document,
prompt, private requirement identifier, later story identifier, local path, account
identifier, credential, or model artifact appears in it. The only identifiers it names are
this change's and earlier ones. The values in the reference matrix are a committed
fixture's. The suite uses no synthetic credential, so the secret-scanning allowlist is
unchanged.

## What this does not establish

- That anything is rendered. No renderer exists, no values file or release is written, and
  `deployment-values-derive-only-from-a-validated-document` stays planned.
- That a real input has carried an ownership conflict. No parsed input can; the check is
  exercised with inputs built to carry one.
- That any renderer supports anything. Every support declaration is a test's.
- That a policy refusal exists. None does.
- That generated values will not duplicate contract intent a hand-written values file also
  sets. No values are generated.
