# Workflow-boundary fixtures

These are **not workflows**. They are YAML files shaped like GitHub Actions workflows,
kept under `tests/` where the service never looks, and they exist to be read by
[`tools/ci_gates/workflow_boundary.py`](../../../../tools/ci_gates/workflow_boundary.py).
Nothing runs them, and no runner is labelled to.

Each one declares the lane whose rules apply in an `# inferops-lane:` header, because a
workflow file has no field for a lane and a fixture is not in
[the gate matrix](../../../../docs/testing/ci-gate-matrix.md).

## `valid/`

Two shapes the rules accept: a `cluster-smoke` workflow and a `real-runtime` workflow,
each dispatched by hand, given a provider with no default, reaching its cluster only
through scripts that call the provider guard, and — for the real-runtime lane — waiting
on an explicit authorization input.

They are the answer to "what would a compliant cluster workflow look like", and they
are deliberately not a working lane. The cluster-smoke shape uses `target-detect.sh`
and `helm-lifecycle.sh` because the lane's own scripts do not call the provider guard
yet, and nothing here has been dispatched against a cluster.

## `invalid/`

Twenty-one workflows, each breaking one rule.
[`expected-rejections.json`](invalid/expected-rejections.json) records which rule each
must produce, and
[`tests/testing/test_infrastructure_gates.py`](../../test_infrastructure_gates.py)
compares the checker's output with it in both directions — and requires every rule the
checker can raise to be broken by at least one fixture, so a rule nobody has watched
fire cannot sit in the checker unnoticed.

No fixture carries a credential, a real runner label, or a real cluster name. The one
kubeconfig path that appears is the project-scoped relative path the environment
scripts already publish.
