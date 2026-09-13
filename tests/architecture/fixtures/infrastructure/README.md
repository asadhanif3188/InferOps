# Infrastructure fixtures

Everything under this directory is **deliberately broken**, and each file or module
is broken in exactly one way. They are the negative inputs of the `helm-chart` and
`terraform` gates in [the gate matrix](../../../../docs/testing/ci-gate-matrix.md),
run by [`tools/ci_gates/infrastructure.py`](../../../../tools/ci_gates/infrastructure.py)
through the real tools.

| Directory | Tool that must refuse it | What it holds |
|---|---|---|
| [`helm-values/`](helm-values/) | `helm template`, or the workload policy after it | values overrides, each layered over `charts/inferops-llm/ci/real-values.yaml` so the override is the only difference |
| [`kubernetes-schema/`](kubernetes-schema/) | `kubeconform -strict` against the pinned schemas | manifests with an unknown field, a wrong type, a missing name, and an API removed before Kubernetes 1.34 |
| [`terraform/`](terraform/) | `terraform fmt`, `terraform validate`, or `tflint` | small modules in the standard three-file layout, so that the one rule each breaks is the only rule that fires |

Nothing here is installed, applied, rendered into a committed file, or referenced by any
chart, script, or document outside this directory and the runner. They live under
`tests/` rather than beside the chart or the configuration so that no command pointed
at `charts/` or `infra/terraform/` can pick one up.

## Refused for a reason, not merely refused

[`expected-refusals.json`](expected-refusals.json) records the text each refusal must
contain. A control passes only when the stage it names refuses, every earlier stage
succeeds, and that text is in the output. A fixture refused because a path was
misspelled or a tool failed to start is a failed control.

That rule earned itself while this directory was being written: on a Windows host the
three lint fixtures were refused by tflint for a path-resolution error that had
nothing to do with the rules they exercise, and only the recorded reason showed it.

## Two fixtures worth knowing about

- `helm-values/profile-empty.yaml` is refused by the chart's own guard, not the schema.
  `helm lint` reports that guard as `[INFO]` and exits 0, which is why these controls
  render rather than lint.
- `terraform/lint-undocumented-variable/` breaks `terraform_documented_variables`, a
  rule in the `all` preset the committed [`.tflint.hcl`](../../../../infra/terraform/.tflint.hcl)
  selects and not in tflint's default. It is refused only when that configuration was
  actually read.
