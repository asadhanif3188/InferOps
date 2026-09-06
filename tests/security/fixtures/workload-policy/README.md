# Workload-policy fixtures

Manifests under [`invalid/`](invalid/) are **deliberately broken**. Each one is a
release bundle that has dropped exactly one control the V1 workload policy
requires, and each exists so that
[`tests/security/test_workload_policy.py`](../../test_workload_policy.py) can
establish that the validator refuses it — with the rules it is supposed to cite
and no others.

Nothing here is deployed, installed, applied, or referenced by any chart, script,
or document outside this directory and its test. They live under `tests/` rather
than under `deploy/` for that reason: every manifest under `deploy/` is held to
the six pod-security properties by the security suite, and a file that must fail
that check has no business sitting beside files that must pass it.

## Why a fixture that fails is a control

A validator with no failing input is a validator nobody has watched refuse
anything. It can be silently broken — a rule that reads the wrong field, a
finding list that is always empty, a return value nobody checks — and every run
of it will pass, which is the outcome that looks exactly like enforcement. `T-18`
in [the threat model](../../../../docs/security/threat-model.md) is that failure
in general; this directory is the specific answer to it for this policy.

[`invalid/expected-rejections.json`](invalid/expected-rejections.json) records
which rule identifiers each fixture must produce. The test compares the set the
validator emits against the set recorded there, in both directions, so a fixture
that starts failing for a *different* reason is a failure rather than a pass. The
arrangement is copied from
[`contracts/workload/examples/invalid/`](../../../../contracts/workload/examples/invalid/),
which already does this for the workload contract.

## What is deliberately not here

No fixture carries a real credential, a real hostname, a real registry
coordinate, or anything else that would be a disclosure with a pedagogical
excuse. The one fixture about secret material carries a placeholder that is not a
credential of any kind, because the rule it exercises fires on an environment
**name** carrying a literal and never on the shape of a value — a rule that
matched value shapes would be a rule that reads secrets.

## The gap this does not close

Every fixture here is a file, and so is every passing input. The validator has no
cluster, no credential, and no way to stop anything being applied, so a refusal
here is a refusal of a manifest and never of a workload. See
[the workload policy document](../../../../docs/security/workload-policy.md),
which states the distance, and `DR-05`, which carries it.
