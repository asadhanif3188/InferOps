# V1-S5-012-PR1 validation: the evidence-level classification rules

Change: the classification rules the `v1alpha2` schema cannot express, as a validator in
[`tools/evidence_model/rules.py`](../../../tools/evidence_model/rules.py); a published
[rule catalogue](../../testing/evidence-level-rules.md) saying which of the schema, the
validator, or review enforces each of forty-three rules; one optional field on the
`v1alpha2` claim, `claimMaterialComponents`; an illustrative register and fifty-one
committed mutations of it; and [a suite](../../../tests/testing/test_evidence_level_rules.py)
that watches every enforced rule refuse the mutation built to break it. This record
says what was run, what it found, and what none of it supports.

**Evidence class: `local-static`.** Every command this change executed reads committed
files, or files the suite writes into a pytest temporary directory, and contacts nothing
else. **No cluster was contacted.** No release was installed, upgraded, rolled back, or
uninstalled, no Terraform ran, no forward was opened, no model was loaded, and no
completion was generated. No cluster run was authorised for this change and none would
have established anything about it: the change publishes rules over data.

**Nothing is reclassified, and no register is migrated.**
[`claim-evidence-matrix.v1alpha1.json`](../../testing/claim-evidence-matrix.v1alpha1.json)
and [`test-strategy.v1alpha1.json`](../../testing/test-strategy.v1alpha1.json) are
byte-for-byte unchanged. No claim status, certification level, evidence class, or
evidence reference moves, and the proof dashboard page is unchanged. `contracts/`,
`src/`, `charts/`, `deploy/`, `infra/`, and `scripts/` are unchanged. Under `tools/`,
only [`tools/evidence_model`](../../../tools/evidence_model/) changes: `rules.py` is new
and `__init__.py` re-exports it. No record under `docs/proof/` is rewritten; one gains a
dated note, described below.

## What the change is

**The rules a schema cannot express.** `V1-S5-011-PR2`'s schema holds the shape of one
record at each level. What it cannot hold is anything that compares: two fields of one
record, a record with the claim that holds it, a claim with the register around it.
Twenty-six rules of that kind are now functions, each registered under a catalogue
identifier, and each refusal names the rule that made it. The eleven rules the schema
already enforced are catalogued beside them rather than re-implemented, because a
constraint expressed twice is a constraint that can disagree with itself.

**Where materiality is declared.** This is the decision the rest depends on. The
schema lets each substitution say whether the replaced component was material to the
claim, which puts the one question that decides `C1` in the hands of the record's author:
a record that replaces the runtime with the committed mock and flags the mock
`claimMaterial: false` passes the schema at `C2`. The claim now declares its
claim-material components once, in `claimMaterialComponents`, and three rules hold every
record to that declaration — a declared component that was substituted must be flagged
material, a record at `C2` or above must have executed every declared component, and a
substitution flagged material must replace a declared component. The third is the one
that refuses a real path classified `C1` because its prompts were generated: the prompt
set is input, not a component the claim declared.

The field is optional in the schema and additive. No committed document declares
`v1alpha2`, the compatibility reader does not produce the field, and a
`legacy-unmigrated` record carries no level for it to govern. The validator requires it
of any claim holding a classified record at `C1` or above.

**Six rules are left to review, and listed.** Whether the declared components are the
right ones, whether a workload represents intended use, whether a criterion flagged as
declared first was, whether a production context is genuine, whether a limitation is the
one that matters, and whether evidence is relevant to its claim. Each would have to be
decided by matching the words in a field. The catalogue says why each is a judgement,
and a test refuses a mutation that claims to break one.

## The rules each level now has to pass

| Level | What [the specification](../../testing/evidence-levels.md) requires | Schema | Validator |
|---|---|---|---|
| `C0` | target behaviour did not execute; static inspection only | `targetBehaviourExecuted` is `false` | only validators or tools ran, nothing substituted, no workload issued, no production context |
| `C1` | execution occurred; a claim-material component was substituted | something executed and is named; a substitution is flagged material | the claim declares its material components; the material substitution replaces one of them |
| `C2` | claim-material components executed; environment recorded; other substitutions disclosed; proof reference exists | no substitution flagged material; environment, procedure, identifier, artifact required | every declared component executed and none was substituted as "immaterial"; ran outside the repository; the cited file exists |
| `C3` | `C2`, plus declared representativeness, workload characteristics, representative conditions, criteria, method, results, limitations | representativeness with assumptions; method; results; criteria flagged declared before | a stated workload shape; a described environment; a result for every criterion, including the ones not met |
| `C4` | organizational production, genuine traffic, observation period, production telemetry, limitations | `organizational-production`; production context with period and known gaps; results | production traffic as the workload; a stated way production was observed; an ordered period |

And across all levels: a mock cannot establish the behaviour it replaced; a claim cannot
exceed its evidence (a certified real-behaviour claim needs a record at `C2` or above, or
a carried legacy class that may support one); a template is not evidence; limitations and
what a record does not establish are required and may not be placeholders; an unsupported
claim is not certified; claim status is not an evidence level.

## Negative tests, and why each must fail

Fifty-one mutations in
[`mutations.json`](../../../tests/testing/fixtures/evidence-level-rules/mutations.json),
fifteen against schema rules and thirty-six against validator rules. Each corrupts the
illustrative register to break one rule, names the place the refusal must land, and says
in words why it must happen; the suite asserts the refusal comes from that rule at that
place — and, for a schema rule, from the JSON Schema keyword the entry names. Every rule marked `schema` or `validator` has at least one. The cases the rules
exist for, named:

| Case | Mutation | Refused by |
|---|---|---|
| A mock-backed record marked `C2`, honestly flagged | `a-mock-backed-record-honestly-flagged-and-marked-c2` | the schema: a `C2` record flags a substitution material |
| The same record, with the mock flagged immaterial | `a-mock-backed-record-flagged-immaterial-and-marked-c2` | `a-substituted-claim-material-component-is-flagged-material` and `a-real-record-executed-every-claim-material-component`; the schema alone accepts it, and a test asserts that |
| A `C1` record with no material substitution | `a-c1-record-with-no-substitution` | the schema |
| A `C3` record without representativeness, criteria, workload shape, or declared conditions | four mutations | the schema for the first two, the validator for the second two |
| A cloud experiment marked `C4` | `a-cloud-experiment-marked-c4`, `a-c4-record-without-a-production-context`, `a-c4-record-under-synthetic-load` | the schema for the first two, `a-c4-record-observed-production-traffic` for the third |
| An important record without limitations or a boundary | four mutations, two empty and two placeholders | the schema for the empty ones, `a-limitation-says-something` for `None.` and `N/A` |
| A real API, adapter, runtime, and model classified `C1` because its prompts were synthetic | `a-real-path-classified-c1-because-its-prompts-were-synthetic` | `a-claim-material-substitution-replaces-a-declared-component`; the schema alone accepts it, and a test asserts that |

Every mutation was also run and its full refusal set printed, to check that each is
refused *for the reason declared* rather than by an unrelated rule that happened to
fire at the same path. Forty-two of the fifty-one produce exactly one refusal. The
other nine produce two or three, and every extra refusal is a true consequence of the
same corruption — removing the model from what executed also leaves the claim's
declaration unmet; copying a record into a planned claim also files it under the wrong
claim and duplicates its identifier.

## Positive tests

- **One claim, three valid records at three levels** (`C0`, `C1`, `C2`) passes every
  rule, and the illustrative register holds a record at each of the five levels.
- **Synthetic input imposes no ceiling.** Every executed record below `C4` passes
  unchanged with its workload origin set to `synthetic`, `captured`, or
  `operator-issued` — nine combinations. A second test reads the module's source and
  asserts the only record rules that read the origin are the `C0` and `C4` ones, which
  are defined partly by their input.
- **The published shapes still pass.** Every valid record shape from `V1-S5-011-PR2`
  passes the record rules, and every invalid one is still refused.
- **The committed register, read into the new shape in memory, passes every rule**, with
  every cited file required to exist in this repository: 59 claims, 45 records, 62
  distinct evidence paths, zero refusals. Two of the `v1alpha1` suite's negative
  controls — a mock certified at `C2`, and a real-behaviour claim resting on a static
  label — are repeated against the replacement and refused by it.

## The decision this record exists to explain: the ceiling did not move

Four files said this change would fire the tripwire in
[`test_evidence_levels.py`](../../../tests/testing/test_evidence_levels.py) — that module,
both halves of the test inventory, and [the `V1-S5-011-PR1` record](v1-s5-011-pr1-validation.md)'s
dated note — and ADR 0016 D3 said the `synthetic → C1` ceiling in
`test-strategy.v1alpha1.json` stays "until `V1-S5-012-PR1` replaces the mechanism". The
mechanism is replaced. The ceiling did not move and the tripwire did not fire, deliberately.

That ceiling constrains what a test *layer* may certify, and the only register it governs
is the committed `v1alpha1` one. Those rows carry no substitution metadata, so the
replacement rules have nothing to read on them. Lifting the ceiling now would remove the
guard from exactly the data the replacement cannot see — the failure
[ADR 0016](../../architecture/decisions/ADR-0016-inferops-evidence-level-model.md) D3
itself warns about. Moving it would also have been the first step of migrating the
strategy data's level names, which belongs with the register in `V1-S5-012-PR2`, in a
change that reclassifies nothing. So the ceiling moves with the register, and the
tripwire fires in `V1-S5-012-PR2`.

This is the second time that prediction has been wrong. `V1-S5-011-PR1` named
`V1-S5-011-PR2`; that record's correction named this change. The prediction is corrected
in the module's docstrings, in the test inventory's row for it, in a dated note in ADR
0016 beside the first one, and in a second dated note in
[the `V1-S5-011-PR1` record](v1-s5-011-pr1-validation.md). The accepted text of the ADR
and of that record is left as written.

A related statement is only half true.
[The `V1-S5-011-PR2` record](v1-s5-011-pr2-validation.md) says applying the rules "to
committed evidence is `V1-S5-012-PR1`". This change applies them to the committed register
only through the in-memory read, where every record is `legacy-unmigrated` and only the
legacy-ceiling, real-behaviour, citation, and identifier rules have anything to check. The
level rules reach committed evidence when `V1-S5-012-PR2` gives a record a level. That
record is left as written; this paragraph is the correction.

The two register-bound `v1alpha1` guards — the matrix suite's ceiling test and the proof
dashboard's `a-level-may-not-exceed-its-labels-ceiling` — keep running on the committed
register. Their replacement exists beside them, which is the ordering
[the model document](../../testing/evidence-record-model.md) said the migration needs.

## What the independent review found

The change was committed once, then reviewed by two independent reviewers: one probing
the validator adversarially by running documents against it, one recomputing every
figure and statement in these pages. The second found every number reproduced and one
stale sentence. The first found real defects. What the first draft got wrong:

- **A path could detour past both citation rules.** The template and evidence-root rules
  compared string prefixes without normalising `.` and `..`, and the schema's path
  pattern allows both. `docs/proof/x/../templates/TEMPLATE-claim-evidence.md` — the
  template itself — passed as evidence, and `docs/proof/../../CHANGELOG.md` passed as a
  record under the evidence root, including the existence check, because the file
  system resolves `..` when it looks. A new rule, `a-citation-is-a-plain-repository-path`,
  refuses any citation with a `.`, `..`, or empty segment, and two mutations drive it.
- **The flagship case was described as closed and is not, entirely.** This record's
  first draft, the catalogue, the module docstring, and the commit message said a record
  could no longer mock the runtime and call the mock immaterial at `C2`. It can, if the
  claim leaves the runtime out of `claimMaterialComponents`; every rule that refuses the
  case reads that declaration, and its completeness is a review rule. Each of those
  pages now says so. A test asserts the gap still passes, and a second measures its
  edge: in a claim that also holds a `C1` record substituting the runtime as material,
  the under-declaration is refused, because that record then names an undeclared
  component. The rule statement for
  `a-substituted-claim-material-component-is-flagged-material` was narrowed to match.
- **A real-serving statement could opt out of needing real evidence.** The
  real-evidence rule fires only when `assertsRealBehaviour` is set, and nothing tied the
  flag to the statement. The `v1alpha1` register suite already did, with a two-phrase
  heuristic, so a replacement without it was weaker than what it replaces. The same
  heuristic is now `a-statement-about-real-behaviour-declares-it`, with the same two
  phrases and its limit stated in the catalogue.
- **The entry points raised on a non-object.** `check_record`, `check_claim`, and
  `check_register` promised refusals and raised `AttributeError` on a list, a string, or
  `None`, and `check_claim` raised `KeyError` on an evidence class with no `classId`.
  Each now returns the schema's refusal, and twelve parametrised cases hold it.
- **Two missing identifiers were reported as one duplicate.** Two records each lacking
  a `recordId` produced a refusal saying record `None` was held twice. Missing
  identifiers are now left to the schema's `required` refusal.
- **A schema mutation could pass by tripping the wrong clause.** The suite matched a
  schema refusal by place alone. Each of the fifteen schema mutations now names the
  keyword that must refuse it, and the suite requires that keyword.
- **One current-state sentence was stale.** The ADR 0016 row of the decision index in
  [the architecture README](../../architecture/README.md) still said replacing the
  ceiling mechanism *is* `V1-S5-012-PR1`, while the same file's narrative paragraph
  had been corrected. It now says what was done.

The fixes added two rules, three mutations, and twenty tests to the numbers the first
commit recorded: forty-one rules became forty-three, forty-eight mutations became
fifty-one, and the module's 113 tests became 133.

## What the checks caught

**The `V1-S5-011-PR2` valid shapes cite a template as their evidence.** Every one names
`docs/proof/templates/TEMPLATE-claim-evidence.md` in `evidenceRefs`, and the `C4` shape
names it as its procedure too. They passed because a lone record has no `templateRoot`
to compare against. A register holding them is refused by `a-template-is-not-evidence`,
once per shape. They were **not** rewritten to pass a rule written after them: a test
now builds that register and asserts the refusal, so the gap is measured in the suite
rather than hidden by an edit.

**The `C3` shape could not pass the rule for declared conditions.** It named its
environment without describing it. It gained a one-sentence environment note; nothing
else in it changed.

**A test that could not fail.** The first draft of the check that no rule below `C4`
reads the workload origin asserted the set of readers was a *subset* of the two allowed
ones, which an empty set satisfies — so a broken pattern that matched nothing would have
passed. It now asserts equality, and the pattern was run by hand and found both.

## Commands and results

Run from the repository root on Windows, in Git Bash, against the staged tree.

| Command | Result |
|---|---|
| `python -m pytest tests/testing/test_evidence_level_rules.py -q` | 133 passed |
| `python -m pytest tests/testing/test_evidence_record_model.py -q` | 119 passed |
| `python -m pytest tests/testing/test_evidence_levels.py -q` | 40 passed |
| `python -m pytest tests/testing tests/security -q` | 5589 passed |
| `python -m pytest tests/telemetry -q` | 1218 passed, as `CONTRIBUTING.md` requires of a change touching `docs/proof/README.md` |
| `python -m pytest -q` | 13203 passed, 33 skipped, 14 deselected |
| `uv run ruff check .` | All checks passed |
| `uv run ruff format --check .` | 488 files already formatted |
| `uv run mypy` | Success: no issues found in 268 source files |
| `git diff --cached --check` | clean |

The fourteen deselected tests are the `cluster`, `realruntime`, `failure`, and `load`
markers, which `pytest.ini` deselects by default. None of them was run, and none would
have established anything about this change.

## Existing records left for `V1-S5-012-PR2`

All of them. Every one of the 45 records the compatibility reader produces is
`legacy-unmigrated` with a null level, and 14 claims carry a claim-level legacy
classification because they cite no record. None has a `claimMaterialComponents`
declaration, and none needs one until it holds a classified record. Reading each claim,
declaring what it depends on, and deciding each record's level against the definitions
is `V1-S5-012-PR2`, as is moving the `synthetic` ceiling and the strategy data's level
names.

## What this record does not establish

- **That any evidence is classified correctly.** No committed record carries a current
  level, and none was given one. The rules have run over an illustrative register, the
  published shapes, and the committed register read in memory.
- **That the six review rules hold.** The schema makes each impossible to leave out; the
  validator cannot make any of them true.
- **That the heuristics are complete.** `a-limitation-says-something` refuses
  placeholders and short entries, and a test asserts that *"Limitations are recorded
  here."* passes it. `a-c0-record-ran-only-inspection` reads roles its author chose.
- **That `C3` or `C4` evidence exists here.** The illustrative register holds both
  shapes. Nothing committed reaches either level under either vocabulary.
- **That the committed register is enforced by these rules.** It is `v1alpha1`, and it
  is enforced by the `v1alpha1` rules it always was.

## Related records

| Topic | Document |
|---|---|
| The rules, and who enforces each | [Evidence-level classification rules](../../testing/evidence-level-rules.md) |
| What the levels mean | [InferOps Evidence Levels (C0–C4)](../../testing/evidence-levels.md) |
| The shape the rules constrain | [The claim and evidence data model, `v1alpha2`](../../testing/evidence-record-model.md) |
| The decision behind both | [ADR 0016](../../architecture/decisions/ADR-0016-inferops-evidence-level-model.md) |
| The validation of the schema this builds on | [`v1-s5-011-pr2-validation.md`](v1-s5-011-pr2-validation.md) |
| The validation of the definitions, with its dated notes | [`v1-s5-011-pr1-validation.md`](v1-s5-011-pr1-validation.md) |
