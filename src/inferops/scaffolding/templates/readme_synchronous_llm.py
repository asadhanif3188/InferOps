"""The quick start a generated `synchronous-llm` workload carries.

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

${description_markdown}

| | |
|---|---|
| Owner | `${owner}` |
| Profile | `synchronous-llm` |
| Environment | `${environment}` |
| Serving capability | `${serving_capability}` |
| Model identity | `${model_ref}` |
| Runtime profile | `${runtime_profile}` |
| Runtime image | `${runtime_image_reference}` |
| Model artifact | `${model_repository}` at `${model_revision}`, file `${model_file}` |
| Tenant | `${tenant}` |
| Cost centre | `${cost_center}` |
| Data classification | `${data_classification}` |
| Evidence this workload has produced | none |

## Quick start

This workload is a directory named `${name}`. Run the first two commands from the
directory that contains it, inside an InferOps checkout with the development
dependency group installed: `tools/` is repository tooling and is deliberately
outside the distribution, so the validator comes from a checkout rather than from
an installed wheel.

Validate the contract against the published schema and every semantic rule,
including the runtime-and-model compatibility matrix:

```sh
python -m tools.contract_validation ${name}/workload.yaml
```

Run this workload's own contract test:

```sh
python -m pytest ${name}/tests -q
```

**Real serving is a third command, and it is opt-in.** It needs the pinned model
artifact and the pinned runtime image on a capable host, and it is deselected
from the default lane on purpose, so it runs only when it is named:

```sh
python -m pytest -m realruntime -q
```

That command is the one difference that matters between this quick start and a
`mock-llm` workload's. A mock has no real-runtime lane and never acquires one;
running the mock's two commands proves the contract and proves nothing about a
runtime.

## Before the third command

The real lane reads its configuration from the environment. `INFEROPS_SERVING_ADAPTER=real`
is what makes the InferOps API compose the real adapter, and the six
`INFEROPS_LLAMA_SERVER_*` variables tell it where the runtime is and what it was
started with. There is no default and no fallback: a `real` selection whose
settings are missing is refused rather than answered with a mock. The variables,
what each one means, and how to bring the runtime up are in
`docs/serving/real-runtime-configuration.md` in the InferOps repository.

Set none of them in a shared shell history, a committed file, or a manifest. This
contract has no field a secret value could be written into, and the reason is the
same one that applies to the environment: a value that is pasted is a value that
is kept.

## What this workload declares

- **Bytes, not a name.** `spec.synchronousLlm.modelArtifact` pins the upstream
  revision *and* the content hash. A revision names what was published; a hash
  names what arrived. Either alone is insufficient.
- **A digest, not a tag.** The runtime image is pinned by digest, because a tag is
  a label that can be moved and a digest is what the engine actually resolves.
- **A compatible pair.** The runtime and the artifact format are checked against
  `contracts/workload/compatibility/runtime-model-compatibility.v1alpha1.json`. A
  pair that is absent from that file is unsupported until it is added there with
  evidence — the validator refuses it rather than assuming it works.
- **No proof references.** This workload has executed nothing, so it cites
  nothing. Add a record to `evidence.proofRefs` when it has produced its own;
  citing another workload's feasibility record would claim that result for this
  workload.

## Changing it

`workload.yaml` is an ordinary committed document. Edit it, then re-run the first
two commands; the validator is the one the repository's own fixtures pass
through, so a change that breaks a rule is refused here rather than discovered
later. Nothing regenerates this directory and nothing overwrites your edits.

Changing the runtime image or the model artifact changes what this workload
serves. Both are pinned to the pair ADR 0002 selected and the feasibility trial
executed; a different pair needs its own entry in the compatibility matrix and
its own evidence before this document should carry it.
"""
