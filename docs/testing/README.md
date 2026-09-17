# Testing and certification

Status: entry point established; the strategy is accepted in part — five of the six
decisions in [ADR 0005](../architecture/decisions/ADR-0005-test-ci-and-certification-strategy.md),
with the choice of continuous-integration service and capable runner explicitly not
made. Nine of eleven test layers exist, and one continuous-integration lane is
configured, with eleven gates that reach no cluster.

This directory answers four questions that are easy to answer badly: what kinds of
test this project runs, where each one runs, what a passing result is allowed to be
used to claim, and which suite would fail if a published claim stopped being true.
The third is the one that matters most, because a suite acquires its meaning from
what it may certify — and if that is left undecided, the cheapest suite decides it.
The fourth is the one nobody could answer before `V1-S1-007`, and
[the inventory](test-inventory.md) is that answer.

A fifth question arrived with Sprint 4, and it is the one a reader outside this
project actually asks: **what has been run, where, and what may it be used to say?**
[The claim and evidence matrix](claim-evidence-matrix.md) is that answer, and it is
the only document here that carries claims this project deliberately does **not**
make. [The V1 proof dashboard](../proof/dashboard.md) is the same answer in one
page, generated from the matrix's data rather than written beside it.

## Documents

| Document | What it covers |
|---|---|
| [Test and CI strategy](test-strategy.md) | Eleven test layers, four lanes, markers, prerequisites, timeouts, artifacts, failure diagnostics, and evidence retention |
| [Certification levels](certification.md) | What C0 to C2 mean, what each evidence class may support, why a mock stops at C1, and what a real record must contain |
| [Claim and test matrix](claim-test-matrix.md) | Every public claim, with its layers, environment, required level, and evidence owner |
| [Claim and evidence matrix](claim-evidence-matrix.md) | Every claim V1 intends to publish, with its implementation, tests, gates, executed record, evidence label, limitation, and status — including the ones that are planned, deferred, and not claimed |
| [Test inventory](test-inventory.md) | Every pytest module, its layer and lane, the claim it protects, and the claims no module protects |
| [`test-strategy.v1alpha1.json`](test-strategy.v1alpha1.json) | The authoritative form of the first three, validated by [`tests/testing/`](../../tests/testing/) |
| [`test-inventory.v1alpha1.json`](test-inventory.v1alpha1.json) | The authoritative form of the inventory, compared with the test tree and the strategy in both directions |
| [`claim-evidence-matrix.v1alpha1.json`](claim-evidence-matrix.v1alpha1.json) | The authoritative form of the claim and evidence matrix, compared with its document, the strategy, the inventory, the gate matrix, and the README in both directions |

The same `docs` marker also collects [`tests/telemetry/`](../../tests/telemetry/),
which holds [the telemetry catalog](../telemetry/telemetry-catalog.md) to its own
rules. Both are committed data checked against the documents describing them.

## The short version

The lane every change goes through downloads no model, touches no cluster, and needs
nobody's authorization. Everything that does is opt-in and cannot run by accident,
because [`pytest.ini`](../../pytest.ini) deselects its marker by default.

A mock may never certify real runtime behaviour, however faithful it is. That is an
[accepted rule](../serving/mock-and-real-boundary.md); what this directory adds is a
ceiling in the data and three tests that enforce it, so the rule holds without
anybody remembering it.

Evidence that certifies a claim is committed under [`docs/proof/`](../proof/) and
kept for as long as the claim stands. A lane's raw output expires and may never be
cited as the evidence for a published claim.

## Running the checks

```sh
python -m pytest -q                    # the default lane
python -m pytest -m contract -q        # one layer inside it
python -m pytest -m realruntime -q     # opt in, on a capable host, deliberately
```

The full contributor check set, including the link, whitespace, shell, and manifest
checks that are not pytest, is in [CONTRIBUTING](../../CONTRIBUTING.md).

## What is not here

No workflow file, no runner, and no automated lane. Every check is run by hand
today, and the strategy data is not permitted to say otherwise: a lane may claim
automation only by naming a workflow file that exists, and a test enforces it.
