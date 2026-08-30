# V1-S1-006-PR1 — The LLM workload template, change validation

The record behind [the workload template](../../scaffolding/workload-template.md).
It records what was run, on what, and what it may be used to claim — which is less
than a reader skimming a green session would assume. **Nothing here generated a
workload anybody kept, deployed one, served one, or started a runtime.** A
template rendered into memory, a validator agreed with it, and a test skeleton
imported and passed against the document rendered beside it. The
[limitations](#limitations) and [acceptance criteria](#acceptance-criteria)
sections are the parts that say so.

## Classification

| | |
|---|---|
| Evidence class | `local-static` for every check here |
| Ceiling | `C0` |
| What ran | The committed test suites, the linter, the formatter, the type checker, and a distribution build, from a checkout |
| What did not run | Any real model, runtime image, container engine, cluster, HTTP server, socket, paid service, scanner, or scaffolding command |
| Claims certified by this record | none |

`local-static` is the weakest label these checks support and it is the correct
one. Every check reads files from this repository, renders text in memory, and
compares it against documents also in this repository. No result here says
anything about serving, about a runtime, or about a workload that was deployed.

**No claim moves to `certified` in this change**, and no layer's status changes.
`contract-and-schema` was already `implemented`; what changed is that it now also
covers what the workload template renders, which is why the layer gained a second
path rather than a new layer being invented for it.

## Provenance

| Input | Value |
|---|---|
| Repository revision at branch point | `ab13c81` |
| Branch | `feat/v1-s1-006-llm-workload-template` |
| Distribution code added | `src/inferops/scaffolding/{__init__,parameters,template}.py`, `src/inferops/scaffolding/templates/` (seven modules) |
| Distribution code changed | none |
| Tests added | `tests/scaffolding/{test_workload_template_rendering,test_workload_template_parameters}.py`, `tests/support/workload_template_cases.py` |
| Documents added | [`docs/scaffolding/workload-template.md`](../../scaffolding/workload-template.md), this record |
| Accepted records updated to stay true | `docs/testing/test-strategy.{md,v1alpha1.json}` — the `contract-and-schema` layer gained a second path and a second command |
| Accepted records **not** changed | Every ADR, the workload contract schema, the compatibility matrix, every committed fixture, the telemetry catalog, the security baseline, the cost method, the inference API surface, and `pyproject.toml`. **No row of the contract, and no fixture, was edited** |
| Records the pinned values were copied from | [the compatibility matrix](../../../contracts/workload/compatibility/runtime-model-compatibility.v1alpha1.json) and [the committed valid fixture](../../../contracts/workload/examples/valid/synchronous-llm-local.yaml), and a test compares both directions |

## Environment

| | |
|---|---|
| Host | One Windows 11 development host |
| Interpreter | CPython 3.12, provisioned by `uv` from the committed [`.python-version`](../../../.python-version) |
| Dependency resolution | [`uv.lock`](../../../uv.lock), unchanged by this work; every command run with `--locked` |
| Network | Not used by any check |
| Model, runtime image, cluster | Not present, not required, not started |

## Method

Every command below was run from a checkout at the branch head, through
`uv run --locked` so that the versions are the committed ones rather than
whatever the host had.

The template was exercised from four representative parameter sets — a minimal
real workload, a minimal mock, and one of each with every optional parameter
supplied — held in `tests/support/workload_template_cases.py` and shared by both
suites so the two argue about the same inputs.

## Results

| Command | Result |
|---|---|
| `uv run --locked ruff check .` | `All checks passed!` |
| `uv run --locked ruff format --check .` | `184 files already formatted` |
| `uv run --locked python -m mypy` | `Success: no issues found in 99 source files` |
| `uv run --locked python -m pytest -q` | `4023 passed, 25 skipped, 14 deselected` |
| `uv run --locked python -m pytest tests/scaffolding -q` | `146 passed` |
| `uv run --locked python -m pytest tests/contracts -q` | `191 passed, 7 skipped` |
| `uv run --locked python -m pytest -m contract -q` | `337 passed, 7 skipped, 3718 deselected` |
| `uv run --locked python -m pytest tests/testing tests/architecture tests/domain -q` | `1352 passed, 18 skipped` |
| `uv build` | Wheel and source distribution built; the wheel carries the `inferops` package and its metadata and nothing else, including the seven new template modules |
| `git diff --check` | No output |
| Markdown trailing-whitespace and hard-tab checks | No match in any file this change touches |
| Relative-link check over every committed Markdown file | No broken link introduced by this change; the four pre-existing ones in `docs/proof/domain/v1-s1-001-pr2-validation.md` are unchanged and out of scope |

The `realruntime`, `cluster`, `failure`, and `load` markers were deselected by the
default expression, which is what the default lane is for. None was invoked.

## What the added checks establish

### A generated workload validates without a source edit

Each of the four cases is rendered and the resulting document is put through
`tools.contract_validation.validate` — the same function
`python -m tools.contract_validation` runs and the same one every committed
fixture passes through — and then through `inferops.domain.workload`'s own
parsing and validation pipeline with the committed compatibility matrix handed
to it. Both must return no findings. Applying the *published* rules rather than a
copy of them is the point: a template checked against its own idea of the
contract is a template checked against nothing.

### Nothing template-shaped survives into output

Substitution is total by construction — `string.Template.substitute` raises for a
placeholder it was given no value for — and the property is asserted anyway over
every rendered file, together with two checks that a copied-template failure
would trip: no rendered file names a `.tmpl`, and rendering one case produces
nothing that names another case's workload or owner. Two further checks close the
loop at the template rather than at the output: every placeholder a template names
has a value for its profile, and every value supplied is read by a template.

### A generated mock says so in its own contents

Asserted in three independent places: the document's `mockLlm` block with
`ciOnly: true`, the workload's own name — a `mock-llm` name must end in `-mock`,
and a parameter set without it is **refused** rather than silently corrected — and
the prose a reader meets first. A generated mock also declares no secret reference
and cites no proof, both of which the schema and the semantic rules already
enforce and which are asserted here because they are what the profile is for.

### Mock and real commands are distinct, in both directions

The real quick start offers `python -m pytest -m realruntime -q` and names
`INFEROPS_SERVING_ADAPTER=real`; the mock quick start offers neither and says why
it does not. A single comparison would miss half of that, so the check asserts the
absence as well as the presence.

### A generated workload cites no evidence it has not produced

`evidence.proofRefs` is absent from **both** profiles. Pre-filling the real
profile with the feasibility record would have handed every generated workload a
result produced by a different one, on a different host, for a different purpose.

### The pins have not drifted from the accepted decision

Every pinned value in a generated `synchronous-llm` workload — image digest,
model repository, upstream revision, filename, size, content hash — is compared
against the committed compatibility matrix's single executed pair and against the
committed valid fixture. The serving capability the template derives per profile
is compared against the schema's own conditional branches, and the two registered
model identities are compared against the two committed valid fixtures.

### The generated test skeleton is a test, not a paragraph shaped like one

Each case is written into pytest's temporary directory, the generated module is
imported from that tree, and every test function in it is called. A skeleton that
does not import is a file that looks like coverage.

### A refusal names the parameter and never the value

A parameter set with a credential-shaped string in twelve fields is refused, and
no refusal, no exception message, and no structured form contains that string. A
refusal may print a closed vocabulary, because those values come from the schema.

## Limitations

**No workload was generated anywhere a person would find it.** Rendering returns
text. The only writes in this work are into pytest's temporary directory, by a
test, to prove the generated skeleton runs. The scaffolding command is
`V1-S1-006-PR2`.

**This proves nothing about serving.** No runtime started, no model loaded, no
socket opened, no cluster existed. A generated `synchronous-llm` workload declares
a runtime image and a model artifact; nothing in this change resolved, pulled, or
executed either.

**The evidence class understates the suite's own registration, deliberately.**
`tests/scaffolding/` runs under the `contract` marker, and the
`contract-and-schema` layer carries the evidence class `local-static` and a `C0`
ceiling. That agrees; there is no gap to report here, unlike the `mock`/`local-static`
imprecision earlier records carry.

**"Validates without a source edit" is proved for four parameter sets, not for
every one.** The sets were chosen to span both profiles, both ends of the replica
range, an accelerator and no accelerator, and every optional parameter supplied or
defaulted. That is coverage by construction of the parameter space's edges, not
exhaustive enumeration of it.

**The second-engineer walkthrough the parent story asks for has not happened.** No
person who is not the author has generated a workload from this template. The
quick start is written; it is untested by its intended reader.

**The generated quick start assumes an InferOps checkout.** `tools/` is repository
tooling and is deliberately outside the distribution, so
`python -m tools.contract_validation` is available from a checkout rather than
from an installed wheel. That is stated in both generated READMEs rather than
being left for an author to discover, and it is a real constraint on how a
generated workload is used today.

**One accepted rule shaped the design rather than being changed by it.** Nothing
under `src/inferops` may read a path, and it is checked. The templates are
therefore module constants rather than files, which is recorded in the template
document as a decision with its reason, not as an implementation detail.

## Acceptance criteria

Applied to this PR's boundary and to the parent story. Criteria belonging to
`V1-S1-006-PR2` are reported as deferred, not implemented early.

| Criterion | Status | Where |
|---|---|---|
| User supplies workload name, owner, environment, model/runtime profile, resources, and attribution | **met** for the template's parameter set. Eleven required parameters, six with a published default, and a check that the two lists partition the object | `tests/scaffolding/test_workload_template_parameters.py` |
| Generated output validates without source edits | **met**, through the published schema and the semantic rules, by both the repository validator and the contract package | `tests/scaffolding/test_workload_template_rendering.py` |
| No stale placeholder survives | **met**, by construction and by assertion, and extended to template filenames and other cases' identifiers | `tests/scaffolding/test_workload_template_rendering.py` |
| Mock and real commands are distinct | **met**, asserted in both directions | `tests/scaffolding/test_workload_template_rendering.py` |
| Invalid name/profile/resources fail before files are written, or leave recoverable output | **met in this half, by construction**: validation completes before rendering begins, and rendering writes nothing, so there is no partial result. The *second* clause — recoverable output from a write that failed partway — belongs to `V1-S1-006-PR2`, which is the half that writes | `tests/scaffolding/test_workload_template_parameters.py` |
| Generated output must pass the same semantic rules the contract package publishes (Sprint 0 locked input) | **met**, by handing the committed matrix to `validate_workload_contract` rather than assuming the tool and the package agree | `tests/scaffolding/test_workload_template_rendering.py` |
| A generated mock workload must declare itself mock in its own contents (Sprint 0 locked input) | **met**, in three places | `tests/scaffolding/test_workload_template_rendering.py` |

Parent story `V1-S1-006` is **not complete**. Its second PR is not written, and
two of its three evidence items do not exist: no generated example workload is
committed anywhere, and no second-engineer walkthrough has happened. The third —
a generated-project test report — exists only in the form above, where the
generated skeleton is imported and run by a suite rather than by a project.

`BL-1`, which blocked this story, is cleared: `ADR 0009` settled the packaging,
dependency, lint, format, and type-check toolchain, and this change is built,
linted, typed, and tested by it without amending it.

## Deferred work

| Item | Owner | Why it is not here |
|---|---|---|
| The scaffolding command: reading parameters, choosing a destination, creating directories, refusing to overwrite | `V1-S1-006-PR2` | This PR's boundary is the template and its parameters; the brief says not to implement the next PR |
| Recoverable output when a write fails partway | `V1-S1-006-PR2` | There is no write in this half to fail |
| A committed generated example workload | `V1-S1-006-PR2` | Committing one before a command exists would commit output nothing produced |
| The second-engineer walkthrough | `V1-S1-006-PR2`, and a second engineer | A walkthrough the author performs is a review of their own understanding |
| A generated-project test *report* as the story's evidence item | `V1-S1-006-PR2` | What exists is a suite importing a generated skeleton, which is weaker and is labelled as such above |
| A second registered model or runtime pair | needs an entry in the compatibility matrix with evidence | The matrix records exactly one executed pair, and the template may not offer more than the platform has |
| Whether a generated workload should live inside an InferOps checkout or beside one | needs a decision in `V1-S1-006-PR2` | The quick start states the current constraint rather than deciding it away |
| Deploying a generated workload | not scheduled | No controller, chart, or reconciler consumes a WorkloadContract |

## Independent review

The change was reviewed by a second reader before it was finalised, against
`CONTRIBUTING.md`, [the mock and real boundary](../../serving/mock-and-real-boundary.md),
[the workload contract](../../contracts/workload-contract.md), and
[the test strategy](../../testing/test-strategy.md), with every command in
[Results](#results) re-run independently. The review disposition is recorded in
the pull request that carries this change.

## Authorisation

No authorisation-gated action was taken. No real model was downloaded, no runtime
image was pulled, no cluster was created, no paid service was used, no destructive
operation was run, and no socket was opened. The `realruntime` lane was not
invoked. The only file-system writes outside the repository working tree were into
pytest's temporary directory, and the `dist/` output of `uv build` was removed
after it was inspected.

## Related records

- [The workload template](../../scaffolding/workload-template.md) — what was built.
- [The workload contract](../../contracts/workload-contract.md) and
  [its schema](../../../contracts/workload/workload-contract.v1alpha1.schema.json) —
  what a generated workload must satisfy.
- [The mock and real boundary](../../serving/mock-and-real-boundary.md) — rule 1,
  which the mock name suffix and the three self-label assertions exist to hold.
- [ADR 0002](../../architecture/decisions/ADR-0002-model-and-serving-runtime.md) —
  the runtime and model a generated `synchronous-llm` workload pins.
- [ADR 0004](../../architecture/decisions/ADR-0004-component-and-ownership-boundaries.md) —
  the boundary that keeps platform implementation code out of a generated workload.
- [ADR 0009](../../architecture/decisions/ADR-0009-python-toolchain.md) — the
  toolchain that built, linted, typed, and tested this change, and the record that
  clears `BL-1`.
- [The test and CI strategy](../../testing/test-strategy.md) — the
  `contract-and-schema` layer, and what it may and may not certify.
- [V1-S1-001-PR2 validation](../domain/v1-s1-001-pr2-validation.md) — the
  validation pipeline this template's output is put through.
