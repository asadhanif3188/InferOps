# V1-S0-006-PR1 change validation

Date: 2026-08-25

Classification: **local static evidence for the change itself.** Every result below
comes from reading and validating files in this repository and from running pytest
over them. No cluster was created, no model was downloaded, no runtime was started,
and no request was served. Nothing here is evidence that the test strategy is a good
one, and nothing here is evidence that any unwritten test layer will be written.

Claim boundary: the committed strategy is internally consistent under every rule the
suite states; forty-three deliberate corruptions of it — in the data, in the pytest
configuration, in three documents, and in an existing test module — are each refused;
the marker configuration and the strategy agree in both directions; every relative
link resolves; the existing suites are unchanged in behaviour; and the published diff
carries no private, generated, or overclaimed content.

**What this record does not establish.** Six of the eleven test layers the strategy
describes have no code, and this suite cannot distinguish an honestly planned layer
from one that will never be written. No continuous-integration lane exists, so
nothing here establishes that any lane runs anywhere but on this host, by hand. The
security-scan layer is recorded as planned rather than implemented for exactly this
reason: `gitleaks` is not installed here, no run of it is recorded, and a committed
configuration file is not a result.

## Environment

| Component | Version |
|---|---|
| Operating system | Microsoft Windows 11 Enterprise, `10.0.26200` |
| Python | `3.12.6` |
| `pytest` | `8.3.4` |
| `jsonschema` | `4.26.0` |
| `PyYAML` | `6.0.2` |
| `ruff` | `0.16.1` |
| Git | `2.45.1.windows.1` |
| GNU bash | `5.2.26(1)-release (x86_64-pc-msys)` |

`jsonschema` and `PyYAML` are listed because the full-suite run below includes the
contract tests, which need them. The strategy suite this change adds needs `pytest`
alone.

## Commands and results

### The strategy suite

```text
python -m pytest tests/testing -q
423 passed
```

Fifty-four test functions, parametrised across five certification levels, eight
evidence classes, seven evidence owners, four lanes, eleven layers, and eighteen
claims.

### The full suite, to show nothing else moved

```text
python -m pytest tests -q
971 passed, 7 skipped
```

Before this change the same command reported `548 passed, 7 skipped`. The seven skips
are the contract suite's existing, deliberate ones. This change adds no skip and
removes none.

Nothing is deselected by the new default marker expression, because no test in this
repository currently carries a deselected marker. That is the honest state: the
expression is a gate on tests that do not exist yet.

### Marker selection, layer by layer

```text
python -m pytest tests -q -m contract        191 passed, 7 skipped, 780 deselected
python -m pytest tests -q -m architecture    357 passed, 621 deselected
python -m pytest tests -q -m docs            423 passed, 555 deselected
python -m pytest tests -q -m unit            978 deselected
python -m pytest tests -q -m adapter         978 deselected
python -m pytest tests -q -m mockintegration 978 deselected
python -m pytest tests -q -m cluster         978 deselected
python -m pytest tests -q -m realruntime     978 deselected
python -m pytest tests -q -m failure         978 deselected
python -m pytest tests -q -m load            978 deselected
```

Three markers select the suites their layers name. Seven select nothing, because the
layers behind them have no code. The strategy records those seven layers as `planned`
or `deferred` and no claim rests on them as certified, so the empty selection is
consistent rather than a gap in the evidence.

### `--strict-markers` refuses an unregistered marker

A throwaway module carrying `@pytest.mark.notregistered` was collected once and then
deleted:

```text
'notregistered' not found in `markers` configuration option
ERROR tests/testing/test_strictmarker_demo.py
1 error in 0.24s
```

The module is not part of this change; only its result is recorded here.

### Deliberate corruption

Forty-three mutations were applied one at a time to the committed strategy, the
committed pytest configuration, the three published documents, and an existing test
module. Each was applied, the strategy suite was run, and the file was restored.

```text
43/43 refused
```

The full list, grouped by what each one attacks:

**The mock boundary (5).** A mock layer certifying C2; a mock layer claiming to need
a real model; a C2 claim satisfied only by a mock layer; a claim needing a real model
citing no layer that loads one; an active claim requiring C3.

**The default lane (5).** A layer needing a model placed in the default lane; the
default lane declaring a model download; a model-fetching lane without opt-in; a
model-fetching lane without authorization; the default lane declaring a longer
timeout than an opt-in lane.

**The marker configuration (6).** Removing `not realruntime` from the default
expression; dropping `--strict-markers`; adding a default-lane marker to the
exclusion; registering a marker no layer owns; pointing `testpaths` elsewhere;
removing a module-level marker from an existing test module.

**Evidence honesty (7).** A planned claim citing evidence; a certified claim losing
its evidence; a certified claim resting on a planned layer; an implemented layer
citing no evidence; evidence cited from outside the proof tree; evidence cited from a
record that does not exist; a certifying record root that is not a directory.

**Deferral and the capacity boundary (3).** An active claim resting on the deferred
capacity layer; a deferred claim giving no reason; an unpublishable layer that is not
deferred.

**Attribution and completeness (7).** A claim naming no layer; a claim naming an
undeclared owner; a claim naming an undeclared environment; a layer cited by no
claim; an owner owning no claim; a layer naming a path that does not exist; two
layers sharing a marker.

**Overclaiming automation and retention (4).** A lane claiming automation with no
workflow file; a lane keeping artifacts with no retention period; a lane declaring
zero retention days; a layer declaring an unregistered marker.

**Document and data drift (3).** A claim removed from the matrix; a lane removed from
the strategy document; an evidence class removed from the certification document.

**Shape (3).** A layer carrying an undeclared field; certification ranks that stop
being a contiguous order; a second lane declaring no opt-in.

The mutation harness is not committed. It is a throwaway script that edits a file,
runs the suite, and restores the file; committing it would add a second thing to
maintain and would not make the result more reproducible than the list above.

### Linting and formatting

```text
ruff check .
All checks passed!

ruff format --check .
55 files already formatted
```

`ruff` is not a selected repository tool — no linter has been chosen, and this change
does not choose one — but the existing Python here is clean under it and a new file
that was not would be a gratuitous inconsistency. The count is 55 rather than the ten
tracked Python files because `ruff format` also inspects Markdown for embedded
Python; nothing in this repository's Markdown contains any.

One finding was raised and fixed during the change: `C401`, an unnecessary generator
where a set comprehension was meant.

### Documentation checks

```text
git ls-files '*.md' | xargs grep -n '[[:blank:]]$'
(no matches)

git ls-files '*.md' | xargs grep -n <TAB>
(no matches)
```

The same two checks were run over the files this change adds, which are not yet
tracked, with no matches.

The relative-link check from CONTRIBUTING was run over every tracked Markdown file
and over the six files this change adds:

```text
link check complete
(no BROKEN lines)
```

```text
git diff --check
(no output)
```

### Strategy shape

```text
levels 5  classes 8  environments 3  owners 7  lanes 4  layers 11  claims 18
lane status    {'manual': 3, 'deferred': 1}
layer status   {'implemented': 5, 'planned': 5, 'deferred': 1}
layer class    {'local-static': 5, 'local-real-cpu': 4, 'mock': 2}
claim status   {'certified': 9, 'planned': 8, 'deferred': 1}
claim level    {'C0': 7, 'C1': 2, 'C2': 9}
```

Nine claims are certified and each cites a record already in this repository. No new
runtime evidence was produced by this change; the three C2 claims marked certified
rest on the cluster smoke record and the runtime feasibility record, both of which
predate it.

## Checks not run, and why

| Check | Why not |
|---|---|
| `gitleaks detect` | Not installed on this host. The configuration and allowlist are committed and unchanged by this change; the strategy records the security-scan layer as `planned` accordingly |
| `shellcheck` | Not installed on this host, and no file under `scripts/` changed |
| `kubeconform` | No file under `deploy/` changed |
| Any cluster, runtime, or model operation | Out of this PR's boundary. No authorization was sought and none is needed, because nothing here claims a runtime result |

## Limitations

- **The suite checks a strategy, not a test suite.** Six of eleven layers have no
  code. Their consistency is checked; their existence is not.
- **A mislabelled evidence class defeats the ceiling.** The checks catch a layer
  placed in the wrong lane or certifying above its class. They cannot catch a
  deliberate misstatement of what a suite runs against; that remains a review
  question and is on the boundary review checklist.
- **The mutation result is a lower bound.** Forty-three corruptions were refused.
  That is evidence that the stated rules are enforced, not that the rules are
  complete.
- **One host, one operating system.** Every command above was run on one Windows
  machine. Nothing here covers another platform, and the strategy's own claim that
  the default lane needs only a checkout and an interpreter is an argument from what
  the suite reads, not a result from a second machine.
