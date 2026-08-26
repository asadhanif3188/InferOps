# The claim and test matrix

Status: **accepted matrix**, in
[ADR 0005](../architecture/decisions/ADR-0005-test-ci-and-certification-strategy.md).
It lists every public claim V1 intends to make, the test layers behind it, the
environment it is proven in, the certification level it needs, and who owns its
evidence. Eleven of twenty claims are certified today. The rest are commitments, and
the difference is the point of the table.

The authoritative form is
[`test-strategy.v1alpha1.json`](test-strategy.v1alpha1.json). This document and that
file are compared in both directions by
[`tests/testing/`](../../tests/testing/); neither can gain or lose a claim without
the other failing.

Layer names, lane names, and what each layer may certify are in
[the test strategy](test-strategy.md). Level meanings are in
[the certification document](certification.md).

## How to read a row

Every claim names at least one test layer, an environment, a required level, and an
evidence owner. Four rules are enforced rather than intended:

1. a claim requiring `C2` or above must cite a layer that can reach it, and that
   layer may not be a mock, a simulation, or an estimate;
2. a claim needing a real model must cite a layer that actually loads one;
3. a claim may cite an evidence record only when it is certified — a planned claim
   citing a record is a failure, not an optimism;
4. a certified claim may rest only on layers that are implemented.

The fourth is the one that catches the realistic mistake. It is easy to mark a claim
certified because a record exists somewhere nearby; it is not possible to do so while
the layer that would have produced it has no code.

## Certified

Each of these rests on an executed record in [`docs/proof/`](../proof/).

| Claim | Layers | Environment | Level | Owner |
|---|---|---|---|---|
| `an-invalid-workload-document-is-refused-with-a-published-reason` | contract-and-schema | repository-only | C0 | contracts |
| `the-rejection-interface-cannot-change-without-a-failing-build` | contract-and-schema | repository-only | C0 | contracts |
| `no-resource-in-the-architecture-has-two-owners` | architecture-inventory | repository-only | C0 | architecture |
| `published-documents-link-only-to-things-that-exist` | documentation | repository-only | C0 | documentation |
| `the-published-strategy-and-its-data-cannot-drift-apart` | documentation | repository-only | C0 | documentation |
| `the-default-lane-cannot-execute-a-real-model` | documentation | repository-only | C0 | documentation |
| `the-telemetry-catalog-cannot-admit-a-prompt-or-an-unbounded-label` | documentation | repository-only | C0 | security |
| `a-cost-figure-cannot-be-presented-as-a-bill` | documentation | repository-only | C0 | documentation |
| `a-local-cluster-is-created-and-removed-without-residue` | kubernetes-smoke | local-kubernetes | C2 | environment |
| `the-selected-runtime-serves-a-real-completion-in-a-cluster` | real-runtime-smoke | capable-host | C2 | serving |
| `the-model-artifact-matches-its-published-hash` | real-runtime-smoke | capable-host | C2 | serving |

The cost row is the newest, and its scope is exactly the committed method. It
certifies that every amount there declares a basis, that only an invoice-backed basis
may carry the vocabulary or the reference of an invoice, that every unit cost carries
the count it was divided by and vanishes below a declared minimum, that a record's
confidence is recomputed from its own inputs rather than read from a field its
producer filled in, and that the worked example's arithmetic closes against the
capacity it allocates. It certifies **nothing about what anything costs**: the only
rate card in this repository is synthetic, no invoice has ever been read, and no
component computes a cost record. The example's own confidence is `none`, derived
rather than assigned.

The telemetry row is narrow in the same way, and its wording is exact for a
reason. A prompt, a response, a provider error body, and a secret have **no**
permitted placement in the committed catalog at all. A tenant identifier, a
correlation or trace identifier, and any unbounded or measured value are a narrower
case: they are permitted in logs and traces and excluded from metric labels, with a
tenant identifier excluded from committed evidence records as well. Collapsing the
two into "cannot admit" would overclaim the second half. The row also certifies that
every metric stays inside a declared series budget — and it establishes nothing about
a running system, because nothing in this repository emits a single signal.

Three of the others are worth reading with their limitations attached. The cluster claim
was executed on **one** Windows host and covers no other operating system. The two
serving claims come from **one** trial, on one host, on one day, whose record is
accepted with a pre-registered threshold explicitly not met. And the hash claim is
load-bearing in a way the others are not: the downloader does not validate TLS
certificates, so the published hash is the entire integrity argument for the
transfer rather than a redundant check on it.

## Planned

Nothing below is proven. Each row states what will have to be true, and none of them
may be cited as evidence of anything today.

| Claim | Layers | Environment | Level | Owner |
|---|---|---|---|---|
| `the-platform-serves-a-workload-the-contract-describes` | unit, adapter, mock-integration, real-runtime-smoke | capable-host | C2 | platform |
| `deployment-values-derive-only-from-a-validated-document` | unit, mock-integration | repository-only | C1 | platform |
| `the-mock-serving-path-identifies-itself-as-a-mock` | adapter, mock-integration | repository-only | C1 | serving |
| `a-model-that-is-not-ready-is-a-canonical-error` | adapter, mock-integration, failure-and-resilience | capable-host | C2 | platform |
| `an-unreachable-runtime-is-a-canonical-error` | adapter, mock-integration, failure-and-resilience | capable-host | C2 | platform |
| `no-prompt-response-or-secret-reaches-a-log-or-a-metric` | unit, mock-integration, security-scan, real-runtime-smoke | capable-host | C2 | security |
| `no-credential-or-model-artifact-enters-public-history` | security-scan | repository-only | C0 | security |
| `a-helm-release-installs-and-uninstalls-without-residue` | kubernetes-smoke | local-kubernetes | C2 | environment |

Two of these rows show the mock boundary doing its work. Both canonical-error claims
cite the mock layers *and* a real one, and they require `C2`. The mock layers will
demonstrate that the API maps the condition to the right error; they cannot establish
that the condition occurs, or that the runtime produces it in the way the mock's
author imagined. Only the real layer can, and the matrix will not let the claim reach
`C2` without it.

The last row is a reminder that "real" and "serving" are different axes. Installing
and uninstalling a Helm release is a `C2` claim proven in a cluster with no model in
it at all.

## Deferred

| Claim | Layers | Environment | Level | Owner |
|---|---|---|---|---|
| `sustained-throughput-and-capacity-under-load` | capacity-and-load | capable-host | C2 | serving |

V1 may publish no throughput, latency, capacity, or benchmark figure. Making one
runtime work is not the same as engineering the runtime, and a capacity claim would
be a claim about a runtime this project did not write —
[the project boundaries document](../architecture/project-boundaries.md) states the
rule and this row is what it looks like applied.

The claim is written down rather than omitted so that publishing a capacity figure
means deleting a deferral in public. A test refuses to let any non-deferred claim
rest on the deferred layer, and the layer's marker is deselected by default, so the
boundary holds in three places at once: the matrix, the strategy data, and the pytest
configuration.

## Owners

Seven evidence owners are declared in the strategy data: contracts, architecture,
environment, serving, platform, security, and documentation. Each owns at least one
claim, and a test refuses an owner who owns none.

These are **roles, not people**. No public maintainer roster or `CODEOWNERS` file
exists — a known governance gap recorded in [CONTRIBUTING](../../CONTRIBUTING.md) —
so an owner here identifies which area a claim's evidence belongs to, not who signs
it off. Naming a person is blocked on the same gap that blocks naming a reviewer.
