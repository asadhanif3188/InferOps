# V2-S2-001-PR1 validation

Date: 2026-10-01

What this change checked before it was committed, and how. What it publishes is in
[the Helm values renderer](../../domain/helm-values-renderer.md); this page is about the
checks run over the repository after the code, its suite, and the documents were written.

The change executed nothing against a host: no cluster, runtime, or model was contacted,
and nothing was installed, provisioned, written to Git by the code, or published. `helm
template` ran locally, reading committed files and writing to standard output only. Every
check below is static, which is `C0` under [the evidence levels](../../testing/evidence-levels.md).
It proves what the renderer writes for the reference inputs, and nothing about a
deployment. It adds no record to the evidence pack and moves no claim.

## Eligibility, checked before anything was written

- **What it builds on is merged.** `main` was at `209ba1c`, the merge of `V2-S1-004-PR2`,
  so the render boundary, its refusals, the provenance input-trust policy, and the release
  domain were in place.
- **The gate and the pack.** `python -B -m tools.evidence_index --gate` exited 0 with
  `FROZEN` for `V1-S5-013-PR2`, `RELEASED v1.0.0` at `718ad2e0…` with the set `1d40b33f…`
  and the pack `652e9051…`, and `CURRENT` with the set `08d4868f…` and the pack
  `b958a724…`. None of the files this change touches is cited by a record.

## What changed

- **`src/inferops/domain/render/helm_values.py`** - `HelmValuesRenderer`,
  `GeneratedHelmValues`, the disposition table for all 44 context values, the chart
  constraints for the 25 values written, the renderer's support declaration, and
  `manual_value_findings`.
- **`src/inferops/domain/render/values_yaml.py`** - `canonical_yaml`, the one YAML form
  generated values are written in, and `ValuesFormError`.
- **`src/inferops/domain/render/errors.py`** - one category, `value-unsupported`, with the
  code `capability-unavailable`, and four rules: `render-value-unsupported`,
  `render-capability-unsupported`, `render-value-credential-shaped`, and
  `render-manual-value-generated`. No existing rule, code, or category changed.
- **`src/inferops/domain/render/__init__.py`** - exports the above.
- **`tests/domain/test_helm_values_renderer.py`** and two fixtures under
  `tests/domain/fixtures/helm-values/` - the golden generated values and the reference
  hand-written values; `.gitattributes` pins that directory to LF.
- **Two existing suites** had their pinned counts moved, with every assertion kept: the
  render package now has twelve modules, the package's own rules are ten, the categories
  eight, three rules carry `capability-unavailable`, and the boundary's one-case-per-rule
  test excludes the four rules no boundary step reaches.
- **Documents** - the new [renderer page](../../domain/helm-values-renderer.md); the
  [boundary page](../../domain/renderer-input-boundary.md), its refusal matrix and its
  "not applied yet" table; the pages that said no renderer exists - the binding and
  release documents, the contracts index, both example indexes, and, after the review below,
  the render and binding domains' docstrings, a release example's comment, the README, and
  two architecture pages; the test inventory, the
  secret-scanning allowlist, the proof index, and the changelog.

No schema, fixture under `contracts/`, chart file, template, ownership row, or provenance
policy changed.

## What the change was asked to reach, and what it reached

| Asked | Reached |
|---|---|
| Map accepted synchronous WorkloadContract fields, platform defaults, and the EnvironmentBinding into the existing Helm values contract | Yes: 24 context values to 25 chart values; the other 20 are constrained or not rendered, each with a reason, and a test holds the table to the context |
| Canonical YAML without nondeterministic ordering, timestamps, or random identifiers | Yes: sorted keys, fixed header, no clock or random read; two interpreters under two hash seeds write the golden bytes |
| Preserve the real-versus-mock boundary | Yes: the renderer takes `synchronous-llm` only and renders `profile: real`; a mock context is refused by `render_with` and by the renderer itself |
| Cover model and runtime identity, resources, replicas, environment, telemetry and security references, and API and platform settings | Yes, with two refusals rather than renders: a replica range has no chart setting, and a secret reference has no accepted mapping |
| Validate against the chart schema | Yes: the generated values over the chart's defaults, with and without the hand-written file, validate against `values.schema.json`, and `helm template` renders them |
| Extend the existing chart contract rather than invent a parallel format | Yes: no chart file changed; every value written is one the chart already defines |
| Story: identical inputs produce canonically identical values and provenance | Values: met for this renderer. Provenance: pending, owned by a later change |
| Story: generated values remain compatible with V1 synchronous real serving | Met statically: the rendered manifests equal the V1 release's but for the environment label. Not shown on a cluster; a later change owns that |
| Story: manual values do not duplicate claim-relevant contract intent | Met for the committed reference file, which a test checks: `manual_value_findings` refuses a hand-written value that sets, replaces, or removes a generated one. Nothing runs it on a release's values yet |
| Story: generated files contain no secret values | Met for what this change generates, in memory: no secret reference is rendered, and a credential-shaped string is refused. No file is written by the code yet |
| Story: release IDs and digests are deterministic | Pending: no release is bound to generated values here |

## Decisions taken while writing, and what was left out on purpose

Each is on the renderer page with its reason; listed here so a reviewer can disagree with
one by name.

1. Contract `cpu` and `memory` render to `runtime.resources.limits`; the chart's requests
   stay. A limit below the chart's request is refused.
2. `spec.environment` renders to `telemetry.deploymentEnvironment`, so the reference
   release is labelled `local` where the V1 fixture says `dev`.
3. Declaring `platform-telemetry` renders `telemetry.enabled: true`; `required` is not
   rendered.
4. A declared secret reference is refused, and `security.secretRefs` is rendered empty.
5. Only `resource-conscious` is accepted as a runtime sizing.
6. A `modelAccess` or `evaluation` integration is refused whether or not it is required.
7. A string the renderer would write is refused if any part begins with a published
   credential prefix, whichever input supplied it.
8. A hand-written empty mapping above a generated value is accepted; at or beneath one, it
   is refused.
9. The values file's header is fixed, three comment lines, with no revision or date.
10. Left out: writing a values file, hashing it, binding it to a release, committing
    generated values, a defaults file, the mock profile, and any change to the chart.

**Left stale on purpose.** The claim register's limitation for
`deployment-values-derive-only-from-a-validated-document` still reads "Deployment rendering
does not exist". It is now an understatement: values are derived, in memory. The claim does
not move - nothing installs generated values and no record cites them - and an edit to the
register is a ledger operation that moves the current evidence digests, which this change
has no record to justify. The same sentence is carried, unchanged, by the proof dashboard
and the V1 evidence index, which are generated from the register. The change that moves
the claim owns all three.

## What the checks caught before the first commit

Each was found by running the suite or re-reading the documents, and fixed before anything
was committed:

- **An overclaim in the first draft of the renderer page.** Its table of places where the
  contract is wider than the chart gave "a 256-character repository" as an example the
  renderer refuses. Measured, it never reaches the renderer: the compatibility matrix
  registers one runtime repository, so the boundary refuses any other as
  `runtime-unregistered` first. The row now says so, and a test asserts the boundary's
  refusal.
- **Later story identifiers in a public page.** The first draft named the changes that
  will bind the values to a release, verify committed state, and run the release on a
  cluster by their identifiers. Public files name only the current change and earlier
  ones; they now say "a later change".
- **A finding hidden by an early `continue`.** The first draft skipped the credential check
  for a value already refused as unsupported, so a value that was both would have reported
  one reason. Both are now reported.
- **A test helper that could not read the chart's values.** The values comparison walked
  dotted paths, and the chart's DNS selector keys contain dots
  (`kubernetes.io/metadata.name`). Paths are now tuples of keys.
- **The suite's own key was a reserved word.** The sort-order test used the key `y`, which
  YAML 1.1 reads as a boolean; `canonical_yaml` refused it, as designed, and the test now
  uses other keys.
- **A Windows newline in the hash-seed comparison.** The child interpreter wrote the YAML
  through a text-mode stream, which on Windows writes CRLF; it now writes bytes.
- **The suites' own counts.** The render package's import test, the refusal suite's own-rule,
  category, and code assertions, the published refusal matrix, and the inventory's counts
  each failed until they were updated.

## Checks that the new tests are not decorative

Ten defects were planted, one at a time, in an archived copy of the working tree - every
tracked and new file, copied outside the repository - never in the tree itself. Each edited
file was compiled before the suites ran, and the copy's package and suite were confirmed to
be the ones imported. The three suites that cover the renderer and the boundary - the new
one and the two whose counts moved, 547 tests - ran in full against each. The copy passed
all 547 before the first defect and again after the last was removed. Every defect was
caught:

| Defect, exactly as made | Of 547 |
|---|---|
| The below-request check becomes `elif False and _below(` | 6 failed |
| The credential check becomes `if False:` | 7 failed |
| The replica-range check becomes `if False:` | 5 failed |
| The secret-reference check becomes `if False:` | 4 failed |
| The environment constraint gains `staging` | 4 failed |
| The image reference is split with `rpartition(":")` instead of `rpartition("@")` | 45 failed |
| `render` stops re-checking support: `unsupported: list[RenderFinding] = []` | 2 failed |
| The manual check's above-a-generated-value branch becomes `if False:` | 2 failed |
| `canonical_yaml` writes an alphanumeric string unquoted | 9 failed |
| `canonical_yaml` writes keys in insertion order: `for key in keys:` | 6 failed |

Two defects are caught by two tests each. Those are the tests written for the property, and
the counts are stated so that nobody reads 159 new tests as 159 guards on each property.

## Commands

Run from Git Bash on Windows, with the locked environment.

| Command | Result |
|---|---|
| `uv run --locked ruff check --no-cache .` | All checks passed |
| `uv run --locked ruff format --check --no-cache .` | 584 files already formatted |
| `uv run --locked mypy` | No issues in 320 source files |
| `uv run --locked python -m pytest tests/domain/test_helm_values_renderer.py tests/domain/test_renderer_refusals.py tests/domain/test_renderer_input_boundary.py tests/testing/test_test_inventory.py -q -p no:cacheprovider` | 1,645 passed: 159 in the new suite |
| The ten planted defects, against an archived copy | Every one caught; see above |
| `python -B -m tools.evidence_index --gate` | Exit 0; the six digests above, unchanged |
| `helm template`, helm 3.19.0, through the new suite | Byte-identical to the V1 fixture with the contract's environment |
| `gitleaks dir <path> --config .gitleaks.toml --redact`, for every new source, test, fixture, and document, with gitleaks 8.30.1 (the version the workflow pins) | No leaks found in any |
| `git diff --check` | Exit 0, no output |

**The full default lane ran before the first commit**, with the new files registered with
Git so the link suite collected them:
`uv run --locked python -B -m pytest -q -rs -p no:cacheprovider --basetemp=<scratch>` gave
**17,021 passed, 1 failed, 33 skipped, 14 deselected**, in 12 min 1 s. The one failure was
this record: the suite that refuses a committed evidence record holding an unfilled
placeholder found the two placeholders this section and the one above stood in for while
the lane ran. They were filled with the results, and that suite was run again over the
record. The skips are the ones earlier records name, such as symbolic links this host
does not permit.

## What the independent review found

A reviewer outside the change read the first commit, `606e605`, re-ran the linters and the
four targeted suites, recounted every figure in this record and the documents, round-tripped
its own awkward inputs through `canonical_yaml`, probed `manual_value_findings` and the
quantity comparison at their edges, and scanned the added lines for private material. It
found nothing it rated critical or high, three findings it rated medium, and four low.
Every figure it recounted was correct.

**Medium - a renderer's refusal lost the caller's request context.** `render_with` called
`renderer.render(prepared)`, and the interface's `render` takes the context alone, so every
finding the Helm values renderer made through `render_with` carried an empty request
context while the boundary's findings carried the caller's. The one test of the request
context called `render` directly. *Fixed in code:* `render_with` now re-raises a renderer's
refusal with the caller's context attached to each finding that carries none, and leaves a
finding the renderer attached its own context to as it is. Two tests reach it through
`render_with`. The interface is unchanged, so every existing renderer double still fits it.

**Medium - "every page that said no renderer exists" was not true.** The first commit
corrected the pages it found, and the review found more:
`src/inferops/domain/render/renderer.py`, `support.py`, and the package docstring; the
binding domain's `selection.py`; a second bullet of the binding document; the contracts
index; and the comment in the release example fixture for `local-docker-desktop`. **What
the first commit got wrong** is its "What changed" list, which said every such page was
corrected - a sweep it had not made. That list is corrected in place, and each page is now
corrected; a search of `src`, `docs`, `contracts`, and the
README for "no renderer exists" finds only records of earlier changes.

**Medium - "nothing turns a validated document into release values" was left in the README
and two architecture pages.** It is now false: values are derived, in memory. Each now says
deployment rendering is unbuilt *end to end*, that the renderer derives values in memory,
and that the values a release is installed with are written by hand.

**Low.** The claim register's stale limitation is also carried, unchanged, by the proof
dashboard and the evidence index, which are generated from it; the paragraph above now names
them. The sentence leading the renderer page's "narrower than the contract" table now says
plainly that the last row is not reached. The new suite's docstring no longer says every
rule is refused through `render_with`. And the manual-values criterion is met for the
committed reference file, which a test checks: nothing runs the check on a release's values,
and the renderer page now says so.

**Run again after the fixes:** `ruff check`, `ruff format --check --no-cache`, `mypy`, the
domain, testing, architecture, and contract suites, the gate, gitleaks over every changed
path, `git diff --check`, and the full default lane, with the results below.

| Command, after the fixes | Result |
|---|---|
| `uv run --locked ruff check .` | All checks passed |
| `uv run --locked ruff format --check --no-cache .` | 584 files already formatted |
| `uv run --locked mypy` | No issues in 320 source files |
| `uv run --locked python -m pytest tests/domain tests/testing tests/architecture tests/contracts -q -p no:cacheprovider` | 12,006 passed, 31 skipped; the new suite alone 161 passed |
| `python -B -m tools.evidence_index --gate` | Exit 0; the six digests above, unchanged |
| gitleaks 8.30.1 over every path changed since `209ba1c` | No leaks found in any |
| `git diff --check` | Exit 0, no output |
| The full default lane, the command above | **17,024 passed, 33 skipped, 14 deselected, none failed**, in 9 min 55 s: the first run's 17,021, the record test that had found the placeholders, and the two new request-context tests |

This record's table was filled after that run; the record and link suites were run again
over it.

## Privacy and publicability

The diff was read for private planning material, local paths, and credentials. It names no
private planning document or repository, no local filesystem path, no host or account
name, and no later story identifier. The credential-shaped strings in the new suite are
published prefixes followed by ordinary lowercase words - `glpat-platform`,
`hf_weights.gguf`, `sk-model-cache`, `inferops-sk-live`, and `ghp_leaked` - which the
secret-scanning allowlist now lists; none is a credential or the length of one, and
gitleaks reports nothing for the file. The hand-written fixture repeats the API image
placeholder digest and the public model URLs the V1 real fixture already carries.

## What this does not establish

That a generated release installs, becomes ready, or serves a request on any cluster; that
a release was installed with generated values; that the values file's digest names
anything, since none is computed; that a hand-written value the check does not cover is
safe; that an identifier an author chose is not a secret written to look like one; or
anything about the mock profile, which the renderer does not take.

## Later correction

Added on 2026-10-02 by `V2-S2-001-PR2`, before that change merged. Nothing above this
heading was changed; it is this change's record as it was merged.

Two acceptance rows above say more than the checks behind them showed.

- **"Story: generated files contain no secret values"** reads *met for what this change
  generates*. As worded, the criterion cannot be met by any check here: a secret
  deliberately written as an otherwise valid name the renderer copies - a workload's name
  or owner, a tenant, a cost centre - has the shape of a name, and syntax cannot prove it
  non-secret, which is the input-trust limitation the release document already states for
  provenance. What holds is a bounded property: no supported secret-bearing field or
  secret reference reaches a generated file, every string in one comes from an owned field,
  and a known credential shape is refused. It is stated, with its tests, in [What a
  generated file can carry](../../domain/helm-values-renderer.md#what-a-generated-file-can-carry).
- **"Story: manual values do not duplicate claim-relevant contract intent"** reads *met for
  the committed reference file*, and says nothing runs the check on a release's values. The
  strongest fact was that one file passed one function. Since `V2-S2-001-PR2` the check is
  applied at a boundary, `admit_manual_values`, which the V1 comparison renders through, and
  a test admits every repository file named as a supported hand-written values file;
  [the renderer page](../../domain/helm-values-renderer.md#hand-written-values) states what
  is still not controlled.

What was run for both is in [the `V2-S2-001-PR2` record](v2-s2-001-pr2-validation.md).
