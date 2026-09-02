# The LLM workload template

Status: **implemented**, as a template, a rendering library, and the command that
writes a workload from it. Both halves are exercised by
[`tests/scaffolding/`](../../tests/scaffolding/), and **no generated workload is
committed anywhere in this repository** — the suite generates into a temporary
directory and nothing survives the run.

The outcome behind it is that a second engineer can produce a valid, owned,
attributed, correctly labelled LLM workload **without editing platform
implementation code**. This document is what that template contains, what it asks
for, what it refuses, what the command does with it, and what a generated
workload is and is not.

Generating one is [one command](#generating-a-workload). It writes three files,
validates the contract it wrote, and refuses rather than overwriting anything.

## Generating a workload

One command, from a checkout, through `uv` so the versions are the committed ones:

```sh
uv run --locked python -m tools.workload_scaffold --help
```

It lives in [`tools/workload_scaffold/`](../../tools/workload_scaffold/) rather
than in the distribution, for the reason the template modules live where they do:
**nothing under `src/inferops` reads a path**, and validating a generated project
needs the published JSON Schema and a YAML loader — a file and a development
dependency nothing that installs `inferops` should inherit. So the writer sits
beside [`tools/contract_validation/`](../../tools/contract_validation/), whose
validator it uses and whose command a generated quick start already tells its
author to run.

### A real workload

```sh
uv run --locked python -m tools.workload_scaffold \
  --name support-assistant \
  --owner team-platform \
  --environment local \
  --profile synchronous-llm \
  --runtime-profile resource-conscious \
  --cpu 6 \
  --memory 3Gi \
  --tenant demo \
  --cost-center demo-cost-center \
  --data-classification internal \
  --description "Answers support questions from the product knowledge base." \
  --into workloads
```

```text
ok      generated workloads/support-assistant
        workloads/support-assistant/README.md
        workloads/support-assistant/tests/test_workload_contract.py
        workloads/support-assistant/workload.yaml
        the contract was validated from disk against the published schema and every semantic rule
```

### A mock workload

Three parameters are not free under `mock-llm`, and each is a refusal rather than
a silent correction: the name must end in `-mock`, the environment is `ci`, and
the accelerator is `none`.

```sh
uv run --locked python -m tools.workload_scaffold \
  --name support-assistant-mock \
  --owner team-platform \
  --environment ci \
  --profile mock-llm \
  --runtime-profile resource-conscious \
  --cpu 250m \
  --memory 128Mi \
  --tenant demo \
  --cost-center demo-cost-center \
  --data-classification public \
  --description "Deterministic contract-test double. Never evidence of real serving." \
  --into workloads
```

Then, from the directory holding it, the two commands the generated quick start
prints:

```sh
python -m tools.contract_validation workloads/support-assistant-mock/workload.yaml
python -m pytest workloads/support-assistant-mock/tests -q
```

`--dry-run` validates and prints the paths it would write without creating any of
them. `--json` emits the result, or the refusal, as a stable document.

### What the command does, in order

1. **Refuses the parameter set**, with every reason at once and none of them
   repeating a value. Nothing has been rendered.
2. **Renders into memory.** Still nothing on a disk.
3. **Validates the rendered contract** through `tools.contract_validation` — the
   same function every committed fixture goes through.
4. **Plans the write**, and refuses if the workload's directory already exists.
5. **Writes**, recording every directory and file it creates as it creates them.
6. **Reads it all back**, comparing each file to what was rendered, checking that
   no placeholder survived, and validating the contract again *from disk*.

Steps 1 to 4 are why an invalid name, profile, or resource declaration fails
before a file exists. Step 6 is why "the generated workload validates" is a
statement about the files rather than about the strings that produced them.

### Exit status

| | |
|---|---|
| `0` | generated, and the contract validated on disk |
| `1` | the parameter set was refused. Nothing written |
| `2` | a usage error, from `argparse` |
| `3` | the destination was refused. Nothing written |
| `4` | the generated contract did not validate. Nothing written |
| `5` | a write failed partway and was rolled back |

A closed vocabulary is deliberately **not** enforced by `argparse`. A `choices=`
would turn a mistyped environment into a usage error that exits before the other
ten parameters are looked at, and the whole point of the validator is that an
author learns every reason in one pass. The four counts are the exception: they
are integers, because "not a number at all" is a usage error rather than a
statement about a workload, and their bounds are still applied with everything
else.

### Nothing is overwritten

A generated workload is an ordinary committed directory the moment it exists.
Re-running the command over one is refused — there is no flag that would make it
overwrite, and its contents are not read, moved, or touched. If a workload should
change, edit it and re-run the two commands its quick start prints.

### What a failure leaves behind

Nothing. Every directory and file the command creates is recorded as it is
created, and a failure anywhere in the sequence removes them in reverse order,
taking back only what the command itself made — a directory that was already
there was never its to remove. If a rollback cannot remove something it says so
rather than reporting a clean undo it did not achieve.

The same rollback covers the read-back: output that does not verify after it was
written is removed rather than left behind for somebody to find later and trust.

One asymmetry is worth stating, because the destination refusal reads as though
there is none. **Only the destination directory itself is type-checked while
planning.** An *ancestor* of it that is a regular file is not, and surfaces as a
write failure rather than as a planning refusal. The guarantee still holds — the
rollback runs and the destination is left as it was found, and a check asserts
that — but the refusal arrives from the writer rather than from the planner.

## What a generated workload is

Three files, and the same three whatever profile it is on:

| File | What it is |
|---|---|
| `workload.yaml` | The [WorkloadContract](../contracts/workload-contract.md) this workload declares |
| `README.md` | The quick start: what this workload is, and the exact commands for it |
| `tests/test_workload_contract.py` | A test skeleton that reads the contract back and asserts it still says what it was generated to say |

The output paths are identical across profiles on purpose. A profile-shaped
filename becomes a profile-shaped build step downstream, and a check that looks
for `workload.yaml` and finds `workload.mock.yaml` reports nothing rather than
reporting a mock.

**No platform implementation code is copied into a workload.** A workload
declares; the platform serves. The generated test imports
`inferops.domain.workload` to read the document into typed objects, and imports
nothing from the API, the adapters, or the scaffolder itself — a check asserts
that over every rendered file.

## Where the templates live

In [`src/inferops/scaffolding/templates/`](../../src/inferops/scaffolding/templates/),
one module per template, each holding its output path and its text as constants.
Not as `.tmpl` files beside them, and the reason is an accepted rule rather than a
preference: **nothing under `src/inferops` reads a path**. That is checked — no
`open`, no `read_text`, anywhere in the distribution — and it exists so the
distribution is usable from a wheel with no repository around it. A template
directory would have made this package the first exception to a rule that is
checked, and an exception to a checked rule is a rule that stops being checked. It
also settles the packaging question in passing: a module ships wherever the package
ships.

A test asserts that no `.tmpl` file reappears there, so reversing the decision means
changing the record rather than adding a file.

## What a generated workload is not

- **It is not evidence.** A generated workload has executed nothing, so it cites
  nothing: `evidence.proofRefs` is absent from both profiles. Pre-filling it with
  the feasibility record would hand every generated workload a result produced by
  a different one.
- **It is not deployed.** No controller, chart, or reconciler in this repository
  acts on a WorkloadContract. Generating one produces a document and a test.
- **It is not regenerated.** The files are ordinary committed files after they
  are written. Nothing overwrites an author's edits, and re-running the
  scaffolder is not part of the change loop.

## Parameters

Eleven are required. Six carry a default, and a default is present only where the
repository has already published the decision behind it.

| Parameter | Required | Constraint | Notes |
|---|---|---|---|
| `name` | yes | DNS-safe, 1–63 characters | `workload_id`. A `mock-llm` workload's must end in `-mock` |
| `owner` | yes | DNS-safe, 1–63 characters | `owner_id`. A workload without an owner has nobody to page |
| `environment` | yes | `ci`, `local`, `dev`, `staging`, `production` | Pinned to `ci` for `mock-llm` |
| `profile` | yes | `synchronous-llm` or `mock-llm` | Decides which contract, quick start, and skeleton are rendered |
| `runtime_profile` | yes | `resource-conscious`, `balanced`, `throughput-oriented` | The sizing *intent*, not a measured result |
| `cpu` | yes | Kubernetes quantity, e.g. `6`, `250m` | No default: an unsized workload is refused rather than guessed at |
| `memory` | yes | Kubernetes quantity, e.g. `3Gi` | As above |
| `tenant` | yes | DNS-safe | `tenant_id`, as declared |
| `cost_center` | yes | kebab-case | Attribution |
| `data_classification` | yes | `public`, `internal`, `confidential`, `restricted` | Not defaulted: a guessed classification is the one nobody re-reads |
| `description` | yes | 1–500 characters | A generated workload that cannot say what it is gives a reviewer nothing to check the rest against |
| `version` | no — `0.1.0` | Semantic version | `workload_version` |
| `model_ref` | no — the profile's catalogue entry | A model identity the catalogue publishes | See below |
| `accelerator_type` | no — `none` | `none`, `integrated-gpu`, `nvidia-gpu`, `amd-gpu` | `none` is the only shape this project has executed against |
| `accelerator_count` | no — `0` | 0–64 | Must be `0` for `none`, and at least `1` otherwise |
| `minimum_replicas` | no — `1` | 0–100 | Must not exceed `maximum_replicas` |
| `maximum_replicas` | no — `1` | 1–100 | |

Every format, vocabulary, and bound above is imported from
`inferops.domain.workload.values`, which is itself compared against the published
schema by a test. The template cannot accept a value the contract would refuse.
It refuses one thing the contract would accept — a `description` that is not a
single line of printable text — and that, with the three other tightenings, is
listed below rather than left for a reader to discover.

### The model identity is a closed set

`model_ref` is optional because the platform catalogue holds exactly one entry per
serving capability today:

| Serving capability | Model identity | Where it comes from |
|---|---|---|
| `inferops-native-serving` | `qwen3-1-7b-q8-0` | The model [ADR 0002](../architecture/decisions/ADR-0002-model-and-serving-runtime.md) selected and the feasibility trial executed |
| `inferops-mock-serving` | `mock-fixed-fixture` | The committed response fixture the mock replays |

Supplying anything else is refused, including the *other* profile's identity. A
`synchronous-llm` workload naming `mock-fixed-fixture` is a single-word edit away
from a valid document and would put a mock label on a real serving path.

### The runtime and the bytes are not parameters

A generated `synchronous-llm` workload carries the runtime image digest, the model
repository, the upstream revision, the filename, the size, and the content hash
that ADR 0002 selected. They are template-owned rather than typed by an author,
because a digest an author pastes is a digest nobody checked. A test compares every
one of them against
[the compatibility matrix](../../contracts/workload/compatibility/runtime-model-compatibility.v1alpha1.json)
and [the committed valid fixture](../../contracts/workload/examples/valid/synchronous-llm-local.yaml),
so a drift between this template and the accepted decision is a test failure rather
than something a reader has to notice.

Serving a different pair is not a parameter either. It needs an entry in the
compatibility matrix with evidence behind it first.

## Rules stricter than the schema

Four, and each is a refusal rather than a silent correction.

1. **A `mock-llm` workload's name must end in `-mock`.** Rule 1 of
   [the mock and real serving boundary](../serving/mock-and-real-boundary.md) is
   that a mock artifact must be identifiable as a mock *from the artifact itself,
   not from the directory it happens to sit in*, and a workload's name travels
   further than any of its other fields — it is what a dashboard row, a log line,
   and a page carry. A scaffolder that quietly appended the suffix would teach
   nobody the rule, so the parameter set is refused instead.
2. **An accelerator declaration may not contradict itself.** `type: none` with a
   non-zero count, or a named device with a count of zero, are both accepted by
   the schema and are incoherent: the second asks for nothing while saying it
   needs something.
3. **`description` is required.** The schema makes it optional. A generated
   workload with no description gives a reviewer nothing to check the rest of the
   document against.

4. **`description` must be a single line of printable text.** The schema puts
   no character constraint on it. A line break, a tab, or a control character is
   a structural change in the YAML, the Markdown, and the Python a description is
   rendered into rather than a character in a sentence, and the section on free
   text below is what that costs when it is not refused.

Everything else the template refuses, the contract refuses too.

## Free text, and the three formats it lands in

`description` is the only parameter that is prose. Every other one is constrained
to a character set that is inert wherever it is rendered: DNS labels, kebab-case
names, semantic versions, Kubernetes quantities, and closed vocabularies. A
description is not, because a description is a sentence and sentences contain
colons.

**Prose substituted raw into a YAML document is not prose, it is YAML.** Three
things go wrong, and all three were reachable before the emitters below existed:

| Description | What the generated document did |
|---|---|
| `chat: escalates below confidence 0.5` | Failed to parse at all. `yaml.safe_load` raises `mapping values are not allowed here` |
| `summarises a claim narrative # for a human reviewer` | Parsed, validated, and **silently** carried `description: summarises a claim narrative` — everything after the `#` read as a YAML comment |
| A description with a newline, two spaces, and `annotations:` | Parsed, **validated with zero findings**, and carried a `metadata.annotations` entry nobody declared. `annotations` is a legitimate extension point, so an injected one is indistinguishable from a real one to every validator in the pipeline |

Two defences now stand in front of that, and they protect against different
mistakes.

**The gate.** `description` must be a single line of printable text. A line
break, a tab, or a control character is a *structural* change in the YAML, in the
Markdown, and in the Python this value is rendered into, rather than a character
in a sentence, so the parameter set is refused and the author is told. This is the
fourth rule stricter than the schema.

**The emitters.** `substitutions()` never hands a template the raw string. It
publishes `description_yaml`, `description_markdown`, and `description_python`,
each already escaped for where it is going — a YAML double-quoted scalar,
Markdown with its inline-active characters escaped, and a Python source literal
from `repr`. There is no key that would render prose into a document unescaped,
which is what makes the escaping impossible to forget rather than merely
documented.

A colon, a `#`, a quote, a backslash, a pipe, a brace, and a 500-character
description are all ordinary input and all round-trip character for character. A
suite asserts that over both profiles: that the value comes back out of the YAML
exactly as it went in, that the generated document's `metadata` gains no key
nobody declared, that the document still validates, that the generated test
skeleton still compiles, and that the quick start keeps its structure.

## Refusals

Every reason arrives at once. An author fixing a parameter set learns all of it in
one pass rather than one problem per attempt, which is the same rule the domain's
validation pipeline follows.

**No reason repeats the value it refused.** A refusal names the parameter and
describes the constraint in the schema's own published vocabulary. The permitted
values of a closed vocabulary are safe to print because they come from the schema;
the value that failed to be one of them is not. A refusal is the surface most
likely to be logged, pasted into a ticket, and kept.

**Nothing is written before the refusal.** Rendering returns text in memory:
`render_workload` validates the whole parameter set and then produces a mapping of
path to content. There is no partial result to clean up because that layer has no
file to write, and the command that does write keeps the order — refuse, render,
validate, *then* plan a write. What happens when a write fails halfway is
[below](#what-a-failure-leaves-behind).

## Secrets

**No template contains a field a secret value could be written into**, and a test
asserts that at the template rather than only at the output — a field introduced
in a template is inherited by every workload generated after it, and the author of
the tenth one would reasonably assume the platform meant it to be filled in.

Both profiles render `secretRefs: []`. The contract's secret block holds locators,
owners, and rotation responsibility; every member object is closed, so there is no
field a value could go in. The shape example is
[`synchronous-llm-secret-refs.yaml`](../../contracts/workload/examples/valid/synchronous-llm-secret-refs.yaml).
A `mock-llm` workload may not declare one at all: it replays a fixture and reaches
nothing that needs a credential, and the `mock-secret-ref-declared` rule refuses it.

## Mock and real commands are distinct

A generated quick start carries the commands for its own profile, and the two do
not overlap:

| | `mock-llm` | `synchronous-llm` |
|---|---|---|
| Validate the contract | yes | yes |
| Run the workload's own test | yes | yes |
| `python -m pytest -m realruntime -q` | **no such lane** | yes, opt-in, on a capable host |
| `INFEROPS_SERVING_ADAPTER` | not mentioned | `real`, with the six `INFEROPS_LLAMA_SERVER_*` variables |

The mock quick start does not offer the real lane and says why. A mock has no
real-runtime lane and never acquires one; running its two commands proves the
contract and proves nothing about a runtime.

Both quick starts are run from an InferOps checkout with the development
dependency group installed. `tools/` is repository tooling and is deliberately
outside the distribution, so `python -m tools.contract_validation` comes from a
checkout rather than from an installed wheel. The generated test needs only
`pyyaml` and an importable `inferops`.

## What the checks establish

[`tests/scaffolding/`](../../tests/scaffolding/) runs in the default lane under
the `contract` marker. It establishes that:

- a render produces exactly three files, deterministically, for both profiles;
- the rendered contract passes the published JSON Schema **and** the semantic
  rules — through `tools.contract_validation`, the same function every committed
  fixture goes through, and through `inferops.domain.workload`'s own validation
  pipeline, so the tool and the contract package are both satisfied;
- no placeholder, no template filename, and no other case's identifiers survive
  into rendered output;
- every placeholder a template names has a value, and every value supplied is used
  by a template;
- a generated mock declares itself a mock in its document, its name, and its prose,
  and cites no runtime proof;
- the generated test skeleton **imports and passes** against the workload rendered
  beside it — a skeleton that does not run is a file that looks like coverage;
- a description that is ordinary prose — a colon, a `#`, a quote, a backslash, a
  pipe, a brace, five hundred characters — round-trips out of the generated YAML
  character for character, adds no field nobody declared, still validates, and
  still compiles inside the generated test skeleton.

And, for the command that writes one:

- four workloads generated into **one** destination stay apart: each validates,
  and none of them names another's workload, owner, or tenant;
- what is written is byte for byte what was rendered, line endings included, and
  the contract validates when it is read back **off the disk**;
- the generated test skeleton passes under a real `python -m pytest` subprocess,
  run against the directory the command created, from a working directory outside
  this repository, with no file edited in between — an import proves a module is
  importable, and only a subprocess proves the command a quick start prints;
- an invalid parameter set creates nothing at all, not even the destination
  directory, and reports every reason;
- an occupied destination is refused and the file already there is byte-identical
  afterwards, including when the directory is empty;
- a write that fails partway removes what it created and leaves what was already
  there, and so does output that fails its read-back, and so does a destination
  whose parent turns out to be a file;
- a contract that does not validate is refused before the write, and one that
  stops validating between the write and the read-back is rolled back — both by
  injection, because an unexercised guard is a comment;
- `--dry-run` plans exactly what a real run writes, and writes nothing;
- the command's option table and the template's parameter set agree in both
  directions, including which parameters are required and what each default is.

It establishes nothing about serving. Nothing here starts a runtime, loads a
model, binds a socket, or reaches a cluster.

## Deferred

Nothing in this story's scope remains. What is *out* of it, and stays out:

- **Kubernetes generation.** A generated workload is three files. No chart, no
  manifest, no `templates/` directory — nothing in this repository acts on a
  WorkloadContract, so a generated manifest would be a deployment artifact
  nothing deploys. A check asserts the absence.
- **Serving anything.** Generating a workload starts no runtime, loads no model,
  binds no socket, and reaches no cluster. That is the API's and the adapters'
  half of the platform, and none of it is invoked here.
- **Human acceptance of the independent walkthrough.** An independent Codex
  reviewer completed both published profiles from a clean detached worktree; the
  [walkthrough record](../proof/scaffolding/v1-s1-006-independent-walkthrough.md)
  preserves the commands, results, and the explicit limitation that the executor
  was not a human second engineer. Whether that distinction satisfies the review
  gate remains a human decision rather than a check this repository can pass.
