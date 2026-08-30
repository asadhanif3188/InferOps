"""The quick start a generated `mock-llm` workload carries.

One template, held as text rather than as a file beside this module. Nothing
under ``src/inferops`` reads a path — that is an accepted architecture rule, and
it is what keeps this distribution usable from a wheel with no repository around
it — so the template travels as a module constant.

Rendered by :mod:`inferops.scaffolding.template`. Every placeholder below is a
:class:`string.Template` placeholder and must have a value in that module's
substitution mapping; a test asserts both directions, and a placeholder with no
value raises rather than surviving into generated output.
"""

from __future__ import annotations

from typing import Final

#: Where this template's output goes inside a generated workload.
OUTPUT_PATH: Final = "README.md"

TEMPLATE: Final = """
# ${name}

> **This is a mock workload.** It replays the committed response fixture, loads
> no weights, reaches no runtime, and answers instantly. Nothing it produces may
> be used as evidence of real serving behaviour — not a weaker claim, no claim.
> The rule is `docs/serving/mock-and-real-boundary.md` in the InferOps repository.

${description_markdown}

| | |
|---|---|
| Owner | `${owner}` |
| Profile | `mock-llm` |
| Environment | `${environment}` |
| Serving capability | `${serving_capability}` |
| Model identity | `${model_ref}` |
| Runtime profile | `${runtime_profile}` |
| Tenant | `${tenant}` |
| Cost centre | `${cost_center}` |
| Data classification | `${data_classification}` |
| Evidence this workload has produced | none |

## Quick start

This workload is a directory named `${name}`. Run both commands from the
directory that contains it, inside an InferOps checkout with the development
dependency group installed: `tools/` is repository tooling and is deliberately
outside the distribution, so the validator comes from a checkout rather than from
an installed wheel.

Validate the contract against the published schema and every semantic rule:

```sh
python -m tools.contract_validation ${name}/workload.yaml
```

Run this workload's own contract test:

```sh
python -m pytest ${name}/tests -q
```

**These are the mock commands, and they are the whole lane for this workload.** A
mock-llm workload has no real-runtime lane: `python -m pytest -m realruntime` is
the wrong command to run against it, and there is nothing here for it to select.
A workload on the `synchronous-llm` profile is generated with that third command
and with the runtime configuration it needs. The difference between the two
quick starts is the boundary, not an omission from this one.

## What this workload declares

- **A fixture, not a model.** `spec.mockLlm.fixtureRef` names the committed
  deterministic response this mock replays. `determinism: fixed-fixture` is the
  only value the schema permits, because a mock that varies is a mock nobody can
  assert against.
- **`ciOnly: true`, written into the document.** The label is in the artifact
  rather than inferred from the directory it sits in, so it survives being copied.
- **No secret references.** A fixture replayer reaches nothing that needs a
  credential; declaring one would either misdescribe the mock or point a
  continuous-integration workload at a real secret, and the
  `mock-secret-ref-declared` rule refuses it.
- **No proof references.** Under this profile the schema caps `evidence.proofRefs`
  at zero entries, so this workload cannot cite runtime proof at all.

## Changing it

`workload.yaml` is an ordinary committed document. Edit it, then re-run both
commands above; the validator is the one the repository's own fixtures pass
through, so a change that breaks a rule is refused here rather than discovered
later. Nothing regenerates this directory and nothing overwrites your edits.

If this workload should serve a real model, it is a different profile and a
different document. Generate a `synchronous-llm` workload rather than editing the
`mockLlm` block out of this one.
"""
