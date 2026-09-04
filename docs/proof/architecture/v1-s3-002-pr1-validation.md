# V1-S3-002-PR1 change validation

Date: 2026-09-04

Classification: **local static**. Every command below reads files, renders
templates, or validates schemas. Nothing was applied to a cluster, no image was
pulled, no model byte was read, and no release was installed. A `helm template`
result is a file; it is not evidence that the objects in it schedule, become
ready, or can be removed.

Claim boundary: this record validates the chart, its values contract, its two
committed renders, the new suite, and the documents this change edits. It says
nothing about installation, upgrade, rollback, readiness, or inference. Those are
`V1-S3-002-PR2` and `V1-S3-006`, and neither has been run.

## Environment

| Component | Version |
|---|---|
| Operating system | Microsoft Windows 11 Enterprise, `10.0.26200` |
| GNU bash | `5.2.26(1)-release (x86_64-pc-msys)` |
| Python | `3.12.12`, through `uv run --locked` |
| uv | `0.9.16` |
| Helm | `v3.21.4+g813176c` |
| kubeconform | reports `development`; the binary already on the authoring host |
| Kubernetes schema target | `1.34.0`, the version this project pins |

Helm was not previously a prerequisite of this repository and was not installed
on the authoring host. It was fetched as a portable archive, used from a
temporary directory, and never placed on the system path or installed as a
service; no host-wide setting was changed. `docs/prerequisites.md` now records it
on the same terms as `shellcheck` and `kubeconform`: a separate install, not
pinned by anything here, and **not required** — the default lane passes without
it.

## Commands and results

### Python

```text
uv run --locked ruff check .           All checks passed!
uv run --locked ruff format --check .  275 files already formatted
uv run --locked python -m mypy         Success: no issues found in 149 source files
uv run --locked python -m pytest -q    5824 passed, 27 skipped, 14 deselected
```

The same suite with `helm` absent from the path, which is the state of a
contributor who has not installed it:

```text
uv run --locked python -m pytest -q    5822 passed, 29 skipped, 14 deselected
```

Two tests, and only two, change state between those runs: the drift comparison
for each profile. Everything else the new suite asserts runs either way.

The suite this change adds:

```text
uv run --locked python -m pytest tests/architecture/test_helm_chart.py -q   73 passed
```

### Helm

Both lints are run with a values file. The chart's shipped defaults select no
serving profile and are refused deliberately, so a lint with no `--values` is
**expected to fail**; that refusal is exercised below as a positive result.

```text
helm lint charts/inferops-llm --strict --namespace inferops-platform \
  --values charts/inferops-llm/ci/real-values.yaml
  ==> Linting charts/inferops-llm
  [INFO] Chart.yaml: icon is recommended
  1 chart(s) linted, 0 chart(s) failed

helm lint charts/inferops-llm --strict --namespace inferops-platform \
  --values charts/inferops-llm/ci/mock-values.yaml
  ==> Linting charts/inferops-llm
  [INFO] Chart.yaml: icon is recommended
  1 chart(s) linted, 0 chart(s) failed
```

The one informational finding is that no chart icon is set. No icon is set
because none exists to set; it is recorded rather than silenced.

### Rendered manifests against the pinned Kubernetes version

```text
helm template inferops charts/inferops-llm --namespace inferops-platform \
  --values charts/inferops-llm/ci/real-values.yaml \
  | kubeconform -strict -summary -kubernetes-version 1.34.0 -
  Summary: 6 resources found parsing stdin - Valid: 6, Invalid: 0, Errors: 0, Skipped: 0

helm template inferops charts/inferops-llm --namespace inferops-platform \
  --values charts/inferops-llm/ci/mock-values.yaml \
  | kubeconform -strict -summary -kubernetes-version 1.34.0 -
  Summary: 4 resources found parsing stdin - Valid: 4, Invalid: 0, Errors: 0, Skipped: 0
```

The committed renders validate identically, which is the check that they are the
same documents:

```text
kubeconform -strict -summary -kubernetes-version 1.34.0 \
  charts/inferops-llm/ci/rendered/real.expected.yaml
  Summary: 6 resources found in 1 file - Valid: 6, Invalid: 0, Errors: 0, Skipped: 0

kubeconform -strict -summary -kubernetes-version 1.34.0 \
  charts/inferops-llm/ci/rendered/mock.expected.yaml
  Summary: 4 resources found in 1 file - Valid: 4, Invalid: 0, Errors: 0, Skipped: 0
```

### The refusals, exercised

A guard nobody has provoked is a guard nobody has checked. Each row below was
run; each produced the refusal quoted, and each is also asserted by the suite.

| What was attempted | Result |
|---|---|
| `helm template` with the shipped defaults | `Error: ... profile is required and has no default. Set it to 'real' ... An omission is refused rather than treated as 'mock'` |
| Real profile with `model.identifier=mock-fixed-fixture` | `Error: ... a real release refuses a mock-labelled model identity, which starts with 'mock-'` |
| Mock profile with `model.revision` set to the real revision | `Error: ... model.revision must be empty under the mock profile` |
| `--namespace default` | `Error: ... the release namespace must be prefixed 'inferops-' (ADR 0001 D5) ... Never pass --create-namespace` |
| `api.extraEnv` naming `INFEROPS_SERVING_ADAPTER` with value `mock` | `Error: ... may not set a name this chart derives ... Refused name: INFEROPS_SERVING_ADAPTER` |
| `api.image.digest=latest` | `Error: values don't meet the specifications of the schema(s) ... at '/api/image/digest': 'latest' does not match pattern '^$\|^sha256:[0-9a-f]{64}$'` |

The last is refused by the values schema rather than by a template, which is the
division intended: the schema decides the shape of one value, and the templates
decide the rules that need to see two at once.

### The new suite is not vacuous

A suite of static assertions can pass because the property holds or because the
assertion never looks at anything. Seven rules were checked by breaking the thing
they defend, confirming a red result, and reverting.

| What was broken | Result |
|---|---|
| `values.yaml` default changed from `profile: ""` to `profile: "mock"` | `1 failed, 72 passed` |
| Runtime image digest altered by one character, so it no longer matches ADR 0002 | `1 failed, 72 passed` |
| `readOnlyRootFilesystem` flipped to `false` in one rendered container | `2 failed, 71 passed` |
| `model-acquisition-job` removed from the chart's deferred list, leaving a Helm-owned row unaccounted for | `1 failed, 72 passed` |
| A `livenessProbe` added to a rendered container | `2 failed, 71 passed` |
| A `Namespace` appended to a render | `6 failed, 69 passed` |
| All four files restored | `73 passed` |

The `Namespace` case failing six assertions rather than one is worth reading as a
result: an object Terraform owns fails the Terraform-disjointness check, the
row-mapping check, the label checks, and the object-count check together, because
each was written to catch it from a different direction.

### Diff hygiene

```text
git diff --check main...HEAD          clean, no output
git ls-files -z '*.md' | xargs -0 grep -n '[[:blank:]]$'
git ls-files -z '*.md' | xargs -0 grep -n "$(printf '\t')"
```

No hard tab anywhere. Trailing whitespace is reported in one file,
`docs/proof/serving/v1-s1-002-pr1-cumulative-review-fixes.md`, which this change
does not touch — `git diff main -- docs/proof/serving/` is empty. It is named
here so that the next contributor running the command from CONTRIBUTING is not
surprised by output this change did not cause, and it is left alone because
cleaning up unrelated files is outside this change's boundary.

The relative-link check reports one line, in the same category:

```text
BROKEN: docs/proof/README.md -> ...
```

That file is not touched by this change either, and the report is a false
positive. The line is prose about how a record cites a template, and it writes
the citation with an ellipsis standing in for the path a reader would supply. The
check has no way to tell a link whose target is an ellipsis from a link whose
target is a path, so it reports one. Every link this change adds resolves, and
this record is deliberately worded so that quoting the problem does not reproduce
it.

The diff was searched for credentials, private planning content, personal
filesystem paths, generated artifacts, and unsupported capability claims. Nothing
was found. The only absolute URL added is this repository's own public origin, in
`Chart.yaml`'s `home` and `sources`.

## What is deliberately in the diff and might look wrong

**A placeholder image digest, in two committed values files.** The chart refuses
an unpinned image, and no InferOps API image exists to pin:
`platform-api-container-image` is `planned` in the ownership inventory and no
`Dockerfile` is committed anywhere in this repository. The fixtures therefore
carry `sha256:7961c9f9ce773095461498774bc2f25053bcba6d01c40d8448da65e217091e50`,
which is the SHA-256 of the ASCII string `inferops-api-image-not-yet-published`.
A reader can recompute it, and the suite does. A fixture that satisfied the
refusal with a movable tag would have taught the render check to accept one; a
fabricated but plausible digest would have satisfied the check while telling the
reader nothing. Both files say so at the top.

**No probe on any container.** The feasibility record shows the runtime's health
endpoint returning `503` during model load: correct readiness behaviour, wrong
liveness behaviour. Choosing the mapping is `V1-S3-002-PR2`'s work and the suite
fails if a probe appears before it.

**No `Role` and no `RoleBinding`.** The service account is created and bound to
nothing. Least-privilege RBAC is `V1-S3-004`'s.

## Limitations

- **Nothing was installed.** No `helm install`, no `helm upgrade`, no
  `helm uninstall`, no cluster contact of any kind. The chart is unproven as a
  release.
- **No image was pulled and no manifest was applied.** Whether the runtime image
  resolves from a cluster's engine, whether the model cache claim binds, and
  whether the API image exists at all are open.
- **The eight pod-security assertions the security suite applies to `deploy/`
  are applied to the chart's renders by a different suite.** The security suite
  scans `deploy/**/*.yaml`, and a Helm template is not parseable YAML, so the
  chart lives under `charts/` and its committed renders are checked by
  `tests/architecture/test_helm_chart.py` instead. The properties checked are the
  same and the file that checks them is not. Consolidating the two belongs with
  `V1-S3-004`, which owns security enforcement, and is recorded here rather than
  done here.
- **The render snapshots are only as current as the last regeneration.** Where
  `helm` is installed, a stale copy fails. Where it is not, a stale copy is
  invisible. That asymmetry is why regenerating them is part of a chart change
  rather than a follow-up, and it is stated in the README beside them.
- **`kubeconform` reports its version as `development`.** The binary was already
  on the authoring host. The Kubernetes schema version it validated against is
  pinned on the command line and is the number this repository publishes.
- **One informational lint finding is unresolved**: the chart sets no icon.

## Acceptance criteria

| Criterion | Status |
|---|---|
| Helm lint, render, and schema checks pass | **Met.** Both profiles lint under `--strict`, both render, both validate against Kubernetes `1.34.0`, and the values schema is applied by Helm on every operation |
| The chart configures API, runtime, model, resources, ownership, telemetry, and security | **Met.** Each is a values section, each reaches a rendered object, and the suite checks each |
| Real evidence values cannot silently select mock | **Met.** The selection has no default and one write site; the capability is derived with it; `extraEnv` is refused rather than merged if it names a derived variable; and each profile refuses the other's model identity, in the same direction the platform's own adapters do |
| No manual manifest editing is required | **Met** for what this PR renders. Two committed values files render the whole release with no edit to a template. It is **not** met for the release as a whole, because the release is incomplete: probes, the acquisition job, the network policy, and scrape configuration are absent by design |
| Install and uninstall succeed | **Not met, and not attempted.** This is `V1-S3-002-PR2`'s criterion. Nothing here has installed anything, and no result in this record may be read as evidence about it |

### The parent story

`V1-S3-002` is **not** complete. Two of its five criteria are open — install and
uninstall, and the whole-release half of "no manual manifest editing" — and both
are `PR2`'s. The story's evidence list asks for a rendered-manifest test and a
chart lifecycle log. The first exists, in the two committed renders and the suite
that reads them. The second does not exist and nothing here approximates it.
