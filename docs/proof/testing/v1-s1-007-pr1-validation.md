# V1-S1-007-PR1 change validation

Date: 2026-08-31

Classification: **local static evidence for the change itself.** Every result below
comes from reading files in this repository and running `pytest`, `ruff`, and `mypy`
over them. No cluster was created, no model was downloaded, no runtime was started,
no socket was opened, and no request left this process. Nothing here is evidence
that the platform serves anything, and nothing here raises what any existing suite
may certify.

Claim boundary: the three surfaces that read a WorkloadContract reach the same
verdict about every committed fixture and every generated workload; every serving
adapter this repository ships is discovered and held to the shared conformance
suite; every condition the API can refuse on is provoked or recorded unreachable,
and each provoked one matches the row that declares it; every pytest module in the
repository is inventoried with the claim it protects or a written reason for
protecting none; every published claim is covered by a module or recorded as a gap;
and ten deliberate corruptions of those properties are each refused.

**What this record does not establish.**

- **It certifies no new claim.** No row of
  [the claim and test matrix](../../testing/claim-test-matrix.md) changed status,
  and no evidence reference in
  [the strategy data](../../testing/test-strategy.v1alpha1.json) was edited. The
  suites added here contribute to claims that were already certified or already
  planned.
- **Nothing crosses a socket.** The API suites drive the application through the
  ASGI interface it implements. This repository ships no server.
- **The API's own condition table is not pinned by this change.** The checks drive
  the published table, so they establish that a refusal follows the row it names
  rather than that the row is right. Nine of the sixteen rows are pinned against
  the accepted record by an existing suite; the seven this API added carry an
  argued `basis` and nothing pins them. Corruption 8 below is the demonstration:
  changing a row changes the expectation with it, and only changing the *refusal
  site* is caught.
- **One divergence between two surfaces is recorded rather than closed.** The
  platform domain does not refuse `mock-presented-as-real.yaml`; the published
  schema does. See "Findings" below.
- **Two inventoried modules have never been executed.** Both
  [`tests/realruntime/`](../../../tests/realruntime/) modules are deselected by
  default and skip when their runtime settings are unset. This change did not run
  them and does not claim they pass.
- **No coverage percentage was measured.** No line or branch coverage is measured,
  reported, or required anywhere in this repository, and this change introduces
  none. "Coverage" here means which claim each suite protects, which is what the
  inventory records.

## Environment

| Component | Version |
|---|---|
| Operating system | Microsoft Windows 11 Enterprise, `10.0.26200` |
| Python | `3.12.12` |
| `pytest` | `8.4.2` |
| `pytest-asyncio` | `0.24.0` |
| `jsonschema` | `4.26.0` |
| `PyYAML` | `6.0.3` |
| `ruff` | `0.16.4` |
| `mypy` | `2.3.1` |
| Git | `2.45.1.windows.1` |
| GNU bash | `5.2.26(1)-release (x86_64-pc-msys)` |

Base revision: `be0acda5ecc2333ed9b8fedaf524ccff1150554c`.

## Commands and results

### The four modules this change adds

```text
python -m pytest tests/contracts/test_platform_contract_regression.py -q    68 passed
python -m pytest tests/adapters/test_adapter_contract_regression.py -q      13 passed
python -m pytest tests/api/test_api_contract_regression.py -q               97 passed
python -m pytest tests/testing/test_test_inventory.py -q                   446 passed
```

### The full default lane, before and after

```text
python -m pytest -q
4874 passed, 25 skipped, 14 deselected
```

Before this change the same command reported `4248 passed, 25 skipped, 14
deselected`. The change adds 626 tests, adds no skip, removes no skip, and removes
no test. The 25 skips and 14 deselections are pre-existing.

### The lane and marker grouping

Every layer selected by name, on the same tree:

```text
python -m pytest -q -m unit             398 passed,  18 skipped, 4497 deselected
python -m pytest -q -m contract         628 passed,   7 skipped, 4278 deselected
python -m pytest -q -m architecture     456 passed,             4457 deselected
python -m pytest -q -m adapter          578 passed,             4335 deselected
python -m pytest -q -m mockintegration  324 passed,             4589 deselected
python -m pytest -q -m docs            2490 passed,             2423 deselected
python -m pytest -q -m cluster                                  4913 deselected
python -m pytest -q -m realruntime                  14 skipped, 4899 deselected
python -m pytest -q -m failure                                  4913 deselected
python -m pytest -q -m load                                     4913 deselected
```

This is the separation the story's last acceptance criterion asks for, measured
rather than asserted. The default lane selects 4 874 tests and none of them is a
`cluster`, `realruntime`, `failure`, or `load` test; `realruntime` selects 14 and
every one of them skips, because no runtime settings are set on this host and the
suite skips rather than fails when they are absent.

**The default marker expression was not changed.** The accepted Sprint 0 input says
this story extends the expression rather than redesigning it; nothing this change
adds needs a cluster or a model, so there was nothing to extend, and
[`pytest.ini`](../../../pytest.ini) is untouched.

### Formatting, linting, and typing

```text
python -m ruff check .          All checks passed!
python -m ruff format --check . 197 files already formatted
python -m mypy                  Success: no issues found in 108 source files
```

### Diff hygiene

```text
git diff --check                (no output)
git ls-files -z '*.md' | xargs -0 grep -n "$(printf '\t')"     (no match)
```

Two pre-existing findings are reported rather than fixed, because both are in files
this change does not touch and fixing them would widen the diff beyond the story:

- `docs/proof/serving/v1-s1-002-pr1-cumulative-review-fixes.md` carries trailing
  whitespace on twelve lines;
- `docs/proof/domain/v1-s1-001-pr2-validation.md` carries four relative links that
  do not resolve.

Both are present on `main` at the base revision above, verified by running the same
two checks against a clean checkout of it. No file changed by this PR carries
either.

### Relative links in the changed documents

The repository-wide link check reports only the four pre-existing failures named
above. Every relative link in the two documents this change adds and the five it edits
resolves.

## Negative validation

A suite that cannot fail proves nothing. Ten properties were each broken on
purpose, the affected module was run, and the source was restored. Every number
below is re-taken at the branch head, after the second-review fixes, so a reader
reproducing one gets the count printed here.

| # | Corruption | Result |
|---|---|---|
| 1 | The domain stops applying `mock-secret-ref-declared` | `4 failed, 64 passed` in the contract regression module |
| 2 | The domain declares a second supported `apiVersion` the schema does not | `5 failed, 63 passed` |
| 3 | The published schema renames one serving-capability token | `11 failed, 57 passed` |
| 4 | One module is removed from the inventory | `1 failed, 436 passed` in the inventory module |
| 5 | One module is filed under a layer whose paths do not contain it | `2 failed, 444 passed` |
| 6 | A `mock`-layer module is credited with a claim only the real-runtime layer supports | `2 failed, 444 passed` |
| 7 | The inventory document’s count of modules defending no claim goes stale | `1 failed, 445 passed` |
| 8 | A living document’s count of how many test layers exist goes stale | `1 failed, 445 passed` |
| 9 | The mock adapter’s conformance subclass stops inheriting the shared suite | `2 failed, 11 passed` in the adapter regression module |
| 10 | A condition is added to the API’s table and never provoked | `1 failed, 96 passed` in the API regression module |

One further corruption is recorded because it **did not** fail, and the reason is a
limitation rather than a defect: editing a condition’s declared HTTP status in
`inferops.api.errors` changes the expectation along with the behaviour, so the
table-driven checks still pass — `97 passed`. Corrupting the *refusal site* instead
— making an oversized body refuse on `request-outside-subset` rather than
`request-too-large` — produces `1 failed, 96 passed`. The checks hold the API to its
published table; they do not decide what the table should say.

## Independent review

A second engineer reviewed the first commit against the diff and re-ran every
command that commit's version of this record cited, reproducing each count
exactly. Three findings, all addressed in the second commit; every count in this
record has since been re-taken at the branch head, because the fixes added eight
tests:

- **One factual error.** `docs/testing/test-inventory.md` said "There are five"
  modules defending no published claim while its own section below listed six and
  the data held six. Corrected, and **now checked**: the count is compared with the
  data, and so is the coverage-gap count, because naming every module is not the
  same as counting them. Corruption 7 above is the demonstration.
- **One stale count in an edited file.** `docs/testing/README.md` said seven of
  eleven test layers exist; the strategy document and its data both say eight, and
  CONTRIBUTING says three have no code. It predates this change. Corrected, and
  **now checked** across all five living documents that state the figure — in both
  forms they use, "N of eleven exist" and "N of the eleven have no code".
  Corruption 8 is the demonstration. Records under `docs/proof/` and entries in the
  changelog are deliberately excluded from that check: both are statements about a
  moment that has passed, and rewriting one to match today would falsify a record.
- **One latent vacuity.** Three kind checks in the adapter module are parametrised
  over the domain’s accepted adapter kinds with no assertion that the set is
  non-empty. An emptied set would retire three checks silently rather than fail
  one. A guard was added.

Beyond those three, the review found no critical or high-severity issue, no
vacuous assertion, no duplicated test, and no scope violation. It could not re-run
the corruptions above in its own sandbox and said so rather than implying it had;
the counts in that table are this author's, re-taken at the branch head.

## Findings

### One divergence between two contract surfaces, recorded rather than closed

`contracts/workload/examples/invalid/mock-presented-as-real.yaml` is refused by the
published JSON Schema and by the offline validator, and is **accepted by the
platform domain**, which parses it into a typed object and returns no validation
error.

This is not a hole. [The contract document](../../contracts/workload-contract.md)
publishes the mock-and-real boundary as four *structural* constraints conditioned on
`spec.profile`, applied by the schema and therefore by every consumer in any
language. The domain's parsing layer applies single-field structural constraints and
its validation layer applies the published semantic rules; neither reaches a
profile-conditional constraint. So the document is refused by the platform, by the
surface the contract says refuses it.

It is recorded in `DOMAIN_DOES_NOT_REFUSE` in
[`tests/contracts/test_platform_contract_regression.py`](../../../tests/contracts/test_platform_contract_regression.py)
with that reason, and two checks hold it: the set of invalid fixtures the domain
accepts must equal that constant exactly in both directions, and every fixture in it
must still be refused by the schema. **No product behaviour was changed.** Adding a
domain rule for it would mean adding a rule identifier to the published rejection
matrix, which is a change to an accepted contract and is outside this PR's boundary.

### Six coverage gaps in the claim matrix

The inventory records six published claims that no pytest module defends. Two of
them are **certified**, and their evidence is a procedure rather than a suite:

- `published-documents-link-only-to-things-that-exist` — the whole-repository link
  sweep is the shell check in [CONTRIBUTING](../../../CONTRIBUTING.md);
- `the-model-artifact-matches-its-published-hash` — the comparison happens in the
  download step of [the feasibility workflow](../../serving/feasibility-workflow.md),
  and the runtime exposes no hash of the file it loaded, so no suite can reach it.

Both are legitimate and neither was known to be un-suited before this change. The
other four (`a-local-cluster-is-created-and-removed-without-residue`,
`no-credential-or-model-artifact-enters-public-history`,
`a-helm-release-installs-and-uninstalls-without-residue`, and
`sustained-throughput-and-capacity-under-load`) rest on layers with no pytest paths,
a planned layer, or a deferred one.

### Six modules that defend no published claim

Six suites protect something no row of the claim matrix names: the dependency rule,
the adapter's pins, the API lifecycle order, the two inference-API-surface suites,
and the toolchain suite. The two API-surface suites are the interesting pair — the
matrix's drift claim is written about the test strategy's own identifiers, so a
structurally identical property for a different published record has no row. That
is a gap in the matrix rather than in the suites, and it is recorded rather than
closed by widening a claim's wording.

### One stale statement in `CONTRIBUTING.md`, corrected

The test-lane section said that `mockintegration` and `realruntime` "currently
select nothing, because the layers behind them have no code yet". Both acquired code
in `V1-S1-004-PR2` and `V1-S1-005-PR1`. The sentence is corrected, and the
`realruntime` correction states that the suite is written and has never been run.

### One stale statement left alone, and why

[The contract document](../../contracts/workload-contract.md) says of the platform
domain that "the semantic rules below are not implemented in that package".
`V1-S1-001-PR2` implemented all seven of them there, and this PR's checks assert
exactly that in both directions. The sentence is an *under*claim rather than an
overclaim, and correcting it edits an accepted contract document outside this PR's
boundary. It is reported here and left for the story that owns that document.

## Acceptance criteria

| Criterion | Status |
|---|---|
| Common adapter suite runs against mock and real-adapter test doubles | Met, and now enforced. The two subclasses existed; `tests/adapters/test_adapter_contract_regression.py` discovers every shipped adapter and fails when one has no suite, and asserts every accepted adapter kind has one |
| API contract tests verify canonical success/error shapes | Met. All sixteen conditions accounted for — fifteen provoked and held to their row, one recorded unreachable with a reason — and every published route driven for the success shape, the identifiers, and the adapter kind |
| Scaffolding output runs the same contract validation | Met, and extended. The existing suites validate generated output; this change asserts the bare published schema agrees, and that a generated mock workload cannot be edited into real serving by any of the four edits the contract names |
| Unsupported contract version is covered | Met. Refused by all three surfaces; the offline validator produces exactly one finding on `$.apiVersion`; the domain refuses before reading a field below it; the refusal names the supported versions and not the declared one; and the three constants that hold the supported set are compared |
| Test markers separate normal CI from real-runtime execution | Met, measured above. Ten marker selections recorded; the default lane selects no test from any deselected layer. The default expression was not changed, because nothing this change adds needs a cluster or a model |

## Parent story

`V1-S1-007` is complete with this PR. Its two evidence obligations are discharged
by [the test inventory](../../testing/test-inventory.md) — the coverage and test
inventory — and by the lane and marker grouping in that document plus the measured
selections above, which is the "CI test grouping documentation" the story asks for
in the only honest form available: **no continuous-integration service is
configured, every lane is run by hand, and a lane may claim automation only by
naming a workflow file that exists.**
