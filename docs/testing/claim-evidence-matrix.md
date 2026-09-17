# The V1 claim and evidence matrix

Status: **published register**, and the authoritative form is
[`claim-evidence-matrix.v1alpha1.json`](claim-evidence-matrix.v1alpha1.json).
It holds 58 claims: 41 certified, 8 planned,
1 deferred, and 8 not claimed. The last group is the point of
the document. A register that listed only what worked would be an advertisement.

Each row binds one claim this project intends to publish to the implementation
behind it, the test modules that would fail if it stopped being true, the
continuous-integration gates that run them, the executed record that certifies
it, the environment and immutable versions that record names, the evidence label
that decides what the record may support, the limitation that travels with the
claim, and its status. The tables below carry the reader-facing columns; the
implementation, test, and gate references for every row are in the data file, and
[`tests/testing/test_claim_evidence_matrix.py`](../../tests/testing/test_claim_evidence_matrix.py)
compares the two in both directions.

This is not [the claim and test matrix](claim-test-matrix.md), and it does not
replace it. That document answers *which test layer would catch this claim
breaking*; this one answers *what has actually been run, where, and what the
result may be used to say*. Where a claim appears in both, this file names the
row there and a test refuses to let it carry a stronger status — more conservative
is allowed, bolder is not.

## How to read a row

Four things decide what a row means, and they are routinely collapsed into one.

**Status** says whether the claim may be published. **Certification level** says
how strong the proof is. **Evidence label** says what the proof ran against.
**Provider and environment** say where. A result can be real and weak, or
exhaustive and worthless; keeping the four apart is the only way to say so.

| Status | Meaning | May cite a record | May be published as a capability |
|---|---|---|---|
| `certified` | An executed record under docs/proof/ supports the statement at the level named, inside the boundary its limitation states. | yes | yes |
| `planned` | V1 intends it and nothing has proven it. It may be published only as an intention, and it may cite no evidence record. | no | no |
| `deferred` | Out of V1 scope by an accepted decision. It may not be published as a capability at all, and it may cite no evidence record. | no | no |
| `not-claimed` | A reader would reasonably expect it and V1 states that it does not have it. It may cite the record that measured the absence, because an absence somebody measured is worth more than one nobody mentions. | yes | no |

`not-claimed` is the state this repository added for its own use, and it is the
one that carries information the other three cannot. It is for a claim a reader
would reasonably expect and V1 does not make — and, unlike `planned`, it may cite
a record, because an absence somebody measured is worth more than one nobody
mentions. Two rows use that: multi-replica serving, refused at a capacity gate,
and the network policy, measured not to be enforced.

## Evidence labels, and the ceiling each carries

These are the classes
[the certification document](certification.md) defines, plus one it deliberately
leaves out of its own table.

| Label | Ceiling | May support a real-behaviour claim | Reached in V1 |
|---|---|---|---|
| `documented-unexecuted` | none | no | yes |
| `local-static` | C0 | no | yes |
| `mock` | C1 | no | yes |
| `synthetic` | C1 | no | yes |
| `estimated` | none | no | yes |
| `local-real-cpu` | C2 | yes | yes |
| `cloud-real-cpu` | C2 | yes | no |
| `cloud-real-gpu` | C2 | yes | no |
| `production-experience` | none | no | no |

`production-experience` is here and is absent from the strategy's class table,
and both are correct. No layer in this project can produce production experience —
there is no organizational production to draw it from, and public-cloud execution
is not production operation — so no layer may be assigned it. A public claim
register still has to be able to name a label and say it is unreachable, which is
what the last row of the table above does.

## The rules, and where they are enforced

10 rules hold this register to its own vocabulary. Every one is a test rather
than an intention, and each **names in the data the control that has been watched
refusing it**, because a rule nobody has watched fail may already be unreachable.

That naming is itself a correction. This paragraph used to assert that every rule
was driven over a row corrupted to break it, and an independent review found that
nine of the ten were — the tenth, `every-readme-entry-point-is-governed`, had no such
control at all. A test now refuses a rule whose named control is not a function in
the suite, and refuses two rules that share one.

| Rule | Statement |
|---|---|
| `a-row-may-not-outrank-the-claim-it-maps-to` | A row mapped to a claim in the test strategy may not carry a stronger status than that claim's own. It may be more conservative; it may never be bolder. |
| `a-real-behaviour-claim-needs-real-evidence` | A certified row asserting real serving, performance, or reliability behaviour must carry an evidence label whose class may support real behaviour, and must cite at least one record. |
| `no-estimate-is-a-bill` | No statement, limitation, or reason in this matrix describes an amount as billing, an invoice, a charge, or spend. The `actual` basis is unreachable in V1 and that vocabulary belongs to it alone. |
| `an-uncertified-claim-cites-no-record` | A `planned` or `deferred` row cites no evidence record and carries no certification level. A `not-claimed` row may cite the record that measured the absence, and carries no level either. |
| `a-level-may-not-exceed-its-labels-ceiling` | A row's certification level may not exceed the ceiling its evidence label carries. |
| `every-readme-entry-point-is-governed` | Every relative link target in the README's public entry-point table is either cited by a row or listed as a surface that makes no capability claim, with a reason. Neither list may name a path the other does. |
| `a-real-record-names-its-provider` | A row whose evidence is a real Kubernetes result declares the provider it ran on, and that provider is one the cluster provider contract publishes. Docker Desktop evidence certifies no other provider. |
| `every-row-states-what-it-does-not-establish` | Every row carries a limitation and a statement of what it does not establish, whatever its status. |
| `a-recorded-coverage-gap-is-restated-rather-than-papered-over` | A row mapping a claim the test inventory records as covered by no pytest module lists that gap and says so in its limitation. The modules such a row names are adjacent to the claim; citing them without the gap would let the register imply coverage the inventory denies. |
| `a-template-is-not-evidence` | No row cites a path under docs/proof/templates/. A format is not a record. |

`every-readme-entry-point-is-governed` is the completeness check. Every relative link in the README's public
entry-point table is either cited by a row here or listed as a surface that claims
nothing, with a reason — and a path may not appear in both lists, or in neither.
That is what makes "every planned public claim has evidence and a limitation" a
property rather than a promise: a new entry point in the README with no row here
fails the build.

`a-recorded-coverage-gap-is-restated-rather-than-papered-over` is the one this
register needed and did not have when it was first written. Five rows name test
modules for a claim
[the test inventory](test-inventory.md) records as covered by **no** pytest module
at all — the artifact hash, the cluster lifecycle, the Helm release lifecycle, the
upgrade and rollback, and the pod replacement. The modules they name are adjacent:
they check how the scripts are written, or the mechanics around the artifact. Citing
them without the gap lets a register imply coverage the inventory denies, so the gap
is now a field on the row, checked against the inventory in both directions, and the
row's limitation has to say it in words. Two further rows — the deferred capacity
claim and the credential-history claim — map a gapped claim and name no module at
all, and carry the gap for the same reason.

`no-estimate-is-a-bill` is narrower than it looks and it is worth stating why. A reserved word
survives inside a sentence that denies it and nowhere else. Banning the words
outright was tried first and was wrong: it makes the rule unsayable, and a
register that cannot name the vocabulary it refuses cannot tell a reader what the
refusal is.

## The claims

### Contracts and domain

| Claim | Status | Level | Evidence label | Where it ran | Record | Automated coverage |
|---|---|---|---|---|---|---|
| `an-invalid-workload-document-is-refused-with-a-published-reason` | certified | C0 | `local-static` | repository-only | [v1-s0-004-pr2-validation.md](../proof/contracts/v1-s0-004-pr2-validation.md) | 2 module(s) |
| `the-workload-contract-and-its-rejection-matrix-are-published` | certified | C0 | `local-static` | repository-only | [v1-s0-004-pr1-validation.md](../proof/contracts/v1-s0-004-pr1-validation.md), [v1-s0-004-pr2-validation.md](../proof/contracts/v1-s0-004-pr2-validation.md) | 2 module(s) |
| `the-workload-domain-parses-a-contract-document-into-typed-objects` | certified | C0 | `local-static` | repository-only | [v1-s1-001-pr1-validation.md](../proof/domain/v1-s1-001-pr1-validation.md), [v1-s1-001-pr2-validation.md](../proof/domain/v1-s1-001-pr2-validation.md) | 3 module(s) |
| `deployment-values-derive-only-from-a-validated-document` | planned | — | `documented-unexecuted` | repository-only | none, by rule | 2 module(s) |
| `the-platform-serves-a-workload-the-contract-describes` | planned | — | `documented-unexecuted` | capable-host | none, by rule | 2 module(s) |

The two planned rows here are the ones to read first, because they are the
distance between what this project publishes and what it does. A contract is
published, parsed, and refused with a reason; **nothing deploys from one**. The
chart's values are written by an operator. Until deployment rendering exists,
`the-platform-serves-a-workload-the-contract-describes` is an intention, and it
cites no record on purpose.

### Scaffolding and the quick start

| Claim | Status | Level | Evidence label | Where it ran | Record | Automated coverage |
|---|---|---|---|---|---|---|
| `a-workload-scaffold-is-generated-without-overwriting-anything` | certified | C0 | `local-static` | repository-only | [v1-s1-006-pr2-validation.md](../proof/scaffolding/v1-s1-006-pr2-validation.md), [v1-s1-006-independent-walkthrough.md](../proof/scaffolding/v1-s1-006-independent-walkthrough.md) | 3 module(s) |
| `the-developer-quick-start-runs-end-to-end-on-a-clean-checkout` | certified | C1 | `mock` | repository-only | [v1-s1-009-pr1-validation.md](../proof/quickstart/v1-s1-009-pr1-validation.md), [v1-s1-006-independent-walkthrough.md](../proof/scaffolding/v1-s1-006-independent-walkthrough.md), [v1-s1-real-runtime-closure.md](../proof/serving/v1-s1-real-runtime-closure.md) | 1 module(s) |
| `a-reviewer-can-reproduce-v1-from-a-clean-clone` | planned | — | `documented-unexecuted` | capable-host | none, by rule | none |

`a-reviewer-can-reproduce-v1-from-a-clean-clone` is planned rather than certified
and the difference is not a formality. Every piece of the journey has been run;
none of them has been run in one sitting, from a clean clone, by somebody who did
not write it, with the manual steps and elapsed time recorded. The independent
walkthrough that exists was performed by a Codex reviewer rather than a human
second engineer, and its own record says so.

### The inference API and its adapters

| Claim | Status | Level | Evidence label | Where it ran | Record | Automated coverage |
|---|---|---|---|---|---|---|
| `a-mock-result-can-never-certify-real-runtime-behaviour` | certified | C0 | `local-static` | repository-only | [v1-s0-006-pr1-validation.md](../proof/testing/v1-s0-006-pr1-validation.md) | 1 module(s) |
| `the-inference-api-serves-five-routes-with-explicit-adapter-selection` | certified | C1 | `mock` | repository-only | [v1-s1-005-pr1-validation.md](../proof/serving/v1-s1-005-pr1-validation.md), [v1-s1-005-pr2-validation.md](../proof/serving/v1-s1-005-pr2-validation.md) | 4 module(s) |
| `a-model-that-is-not-ready-is-a-canonical-error` | planned | — | `documented-unexecuted` | capable-host | none, by rule | 2 module(s) |
| `an-unreachable-runtime-is-a-canonical-error` | planned | — | `documented-unexecuted` | capable-host | none, by rule | 2 module(s) |
| `the-mock-serving-path-identifies-itself-as-a-mock` | planned | — | `documented-unexecuted` | repository-only | none, by rule | 2 module(s) |

Three of these five are planned, and all three are planned for the same reason:
the mock layers establish that the API maps a condition to the right error, and
they cannot establish that the condition occurs. The unready-model experiment is
the sharpest illustration. It produced the real condition, and no caller ever
received `model-not-ready` — every completion came back `capability-unavailable`
with condition `runtime-unreachable`. That measurement is a reason to keep
`a-model-that-is-not-ready-is-a-canonical-error` planned, not a reason to promote
it.

### Real serving on a contributor's machine

| Claim | Status | Level | Evidence label | Where it ran | Record | Automated coverage |
|---|---|---|---|---|---|---|
| `a-local-serving-baseline-was-measured-under-a-method-registered-first` | certified | C2 | `local-real-cpu` | capable-host | [v1-s2-005-local-baseline-experiment.md](../proof/serving/v1-s2-005-local-baseline-experiment.md), [v1-s2-005-baseline-raw-results.md](../proof/serving/v1-s2-005-baseline-raw-results.md) | 1 module(s) |
| `a-runtime-and-model-pair-was-selected-by-a-recorded-feasibility-procedure` | certified | C2 | `local-real-cpu` | local-kubernetes, `docker-desktop` | [v1-s0-003-pr2-runtime-feasibility.md](../proof/serving/v1-s0-003-pr2-runtime-feasibility.md) | 2 module(s) |
| `local-runtime-diagnosis-is-machine-checked-against-the-records-it-quotes` | certified | C0 | `local-static` | repository-only | [v1-s2-008-pr1-validation.md](../proof/serving/v1-s2-008-pr1-validation.md) | 1 module(s) |
| `the-model-artifact-matches-its-published-hash` | certified | C2 | `local-real-cpu` | capable-host | [v1-s0-003-pr2-runtime-feasibility.md](../proof/serving/v1-s0-003-pr2-runtime-feasibility.md), [v1-s1-real-runtime-closure.md](../proof/serving/v1-s1-real-runtime-closure.md) | **recorded gap** |
| `the-model-lifecycle-states-were-measured-across-six-real-starts` | certified | C2 | `local-real-cpu` | capable-host | [v1-s2-007-pr1-cold-warm-start.md](../proof/serving/v1-s2-007-pr1-cold-warm-start.md), [v1-s2-007-cache-miss-observation.md](../proof/serving/v1-s2-007-cache-miss-observation.md) | 1 module(s) |
| `the-selected-model-serves-a-real-completion-through-the-inferops-api` | certified | C2 | `local-real-cpu` | capable-host | [v1-s2-004-c2-certification-result.md](../proof/serving/v1-s2-004-c2-certification-result.md), [v1-s1-real-runtime-closure.md](../proof/serving/v1-s1-real-runtime-closure.md) | 3 module(s) |

Five of these six are `C2` results from **one Windows host, on CPU**; the sixth is
a `C0` check over the troubleshooting guide. None of them is a result about a
cluster InferOps selected under the provider contract. The certification run, the
baseline and the lifecycle comparison were loopback compositions with no cluster at
all; the feasibility trial **was** a Kubernetes result — the runtime started in the
container desktop distribution's own single-node cluster and answered through
cluster DNS and a Service — but it ran before ADR 0011 existed, so its record names
that cluster descriptively rather than by provider identifier, and the provider in
its row is read from that description. An independent review caught this row calling
itself `not-applicable`, and caught this paragraph saying it was not a Kubernetes
result at all.

Two figures are worth carrying out of the table. The certification run had 14,172 ms of headroom
against a 300,000 ms readiness budget — under five per cent, and its record says
the budget is not comfortable. And the cold-and-warm comparison found warm
*slower* in all three pairs, with a within-arm spread larger than every delta, so
it claims no cold-start effect at all.

### Kubernetes deployment and lifecycle

| Claim | Status | Level | Evidence label | Where it ran | Record | Automated coverage |
|---|---|---|---|---|---|---|
| `a-controlled-release-change-can-be-reversed-and-real-inference-restored` | certified | C2 | `local-real-cpu` | local-kubernetes, `docker-desktop` | [v1-s3-011-pr2-upgrade-rollback.md](../proof/environment/v1-s3-011-pr2-upgrade-rollback.md) | **recorded gap** |
| `a-helm-release-installs-and-uninstalls-without-residue` | certified | C2 | `local-real-cpu` | local-kubernetes, `docker-desktop` | [v1-s3-011-pr2-scoped-cleanup.md](../proof/environment/v1-s3-011-pr2-scoped-cleanup.md) | **recorded gap** |
| `a-local-cluster-is-created-and-removed-without-residue` | certified | C2 | `local-real-cpu` | local-kubernetes, `kind` | [v1-s0-002-pr2-cluster-smoke.md](../proof/environment/v1-s0-002-pr2-cluster-smoke.md) | **recorded gap** |
| `inferops-consumes-an-operator-owned-cluster-and-verifies-it-before-mutating` | certified | C2 | `local-real-cpu` | local-kubernetes, `docker-desktop` | [v1-s3-011-pr1-docker-desktop-paved-road.md](../proof/environment/v1-s3-011-pr1-docker-desktop-paved-road.md), [v1-s3-010-pr1-validation.md](../proof/architecture/v1-s3-010-pr1-validation.md) | 4 module(s) |
| `kubernetes-diagnosis-and-four-cleanup-radii-are-published-and-executed` | certified | C0 | `local-static` | repository-only | [v1-s3-009-pr1-validation.md](../proof/environment/v1-s3-009-pr1-validation.md), [v1-s3-011-pr1-docker-desktop-paved-road.md](../proof/environment/v1-s3-011-pr1-docker-desktop-paved-road.md), [v1-s3-011-pr2-scoped-cleanup.md](../proof/environment/v1-s3-011-pr2-scoped-cleanup.md) | 1 module(s) |
| `the-model-artifact-survives-a-pod-replacement-on-a-terraform-owned-claim` | certified | C2 | `local-real-cpu` | local-kubernetes, `docker-desktop` | [v1-s3-003-pr2-kubernetes-pod-restart.md](../proof/serving/v1-s3-003-pr2-kubernetes-pod-restart.md) | **recorded gap** |
| `the-selected-runtime-serves-a-real-completion-in-a-cluster` | certified | C2 | `local-real-cpu` | local-kubernetes, `docker-desktop` | [v1-s3-011-pr1-docker-desktop-paved-road.md](../proof/environment/v1-s3-011-pr1-docker-desktop-paved-road.md), [v1-s0-003-pr2-runtime-feasibility.md](../proof/serving/v1-s0-003-pr2-runtime-feasibility.md) | 3 module(s) |
| `multi-replica-serving-is-certified` | not-claimed | — | `local-real-cpu` | local-kubernetes, `docker-desktop` | [v1-s3-011-pr1-docker-desktop-paved-road.md](../proof/environment/v1-s3-011-pr1-docker-desktop-paved-road.md) | 1 module(s) |

Seven certified rows and one refusal. Five of the seven ran on `docker-desktop`,
one on `kind`, and one is a `C0` check over the troubleshooting guide.
`docker-desktop` is the executed V1 reference provider and **certifies nothing
about `kind`** — the only `kind` result in this matrix is the 2026-08-23 cluster
smoke, whose workload was a static-text HTTP server. Docker Desktop chooses its
own Kubernetes version and node image, and InferOps pins neither.

The `not-claimed` row is the one that matters most here. Multi-replica serving
was attempted on the reference host and refused at the capacity gate, 165 MiB
short, before anything was installed. The gate was not weakened and the replica
count was not reduced to fit. **A refusal is the evidence, and it is not a weaker
form of a certification.**

### Load and performance

| Claim | Status | Level | Evidence label | Where it ran | Record | Automated coverage |
|---|---|---|---|---|---|---|
| `a-bounded-local-performance-matrix-was-measured-and-a-degradation-point-observed` | certified | C2 | `local-real-cpu` | local-kubernetes, `docker-desktop` | [v1-s4-004-pr1-validation.md](../proof/serving/v1-s4-004-pr1-validation.md), [v1-s4-004-pr2-performance-findings.md](../proof/serving/v1-s4-004-pr2-performance-findings.md) | 2 module(s) |
| `repeatable-llm-load-can-be-generated-from-a-versioned-profile` | certified | C2 | `local-real-cpu` | local-kubernetes, `docker-desktop` | [v1-s4-004-pr1-validation.md](../proof/serving/v1-s4-004-pr1-validation.md), [v1-s4-003-pr1-validation.md](../proof/serving/v1-s4-003-pr1-validation.md) | 1 module(s) |
| `sustained-throughput-and-capacity-under-load` | deferred | — | `documented-unexecuted` | capable-host | none, by rule | **recorded gap** |

Both certified rows are bounded observations under
[ADR 0013](../architecture/decisions/ADR-0013-bounded-local-performance-observations.md),
and the deferred row is what they are bounded away from. `0.554 to 0.575 requests
per second` is a thing that happened on one host on 2026-09-14 with a shared node,
a cached prompt, and a port-forward inside every latency. It is not a rate anything
supports. The portable claim stays deferred, written down rather than omitted, so
that publishing a capacity figure would mean deleting a deferral in public.

### Failure and recovery

| Claim | Status | Level | Evidence label | Where it ran | Record | Automated coverage |
|---|---|---|---|---|---|---|
| `an-unready-model-was-held-unready-and-recovered-by-an-operator` | certified | C2 | `local-real-cpu` | local-kubernetes, `docker-desktop` | [v1-s4-007-pr1-unready-model-recovery.md](../proof/serving/v1-s4-007-pr1-unready-model-recovery.md) | 1 module(s) |
| `caller-visible-impact-of-losing-the-inference-pod-was-measured-under-load` | certified | C2 | `local-real-cpu` | local-kubernetes, `docker-desktop` | [v1-s4-006-pr1-inference-pod-recovery.md](../proof/serving/v1-s4-006-pr1-inference-pod-recovery.md) | 1 module(s) |

Both rows measure what a caller experienced, and both refuse to turn that into a
figure about availability. The pod-loss run's most useful result is a
disagreement rather than a duration: for the whole 31,960 ms outage the **deleted**
pod went on reporting `Ready: True` while the Service had no ready endpoint at
all. One replica is the cause of the outage, and nothing here is an availability
figure, a service-level objective, an error budget, or a recovery-time objective.

### Telemetry, dashboard, and alerts

| Claim | Status | Level | Evidence label | Where it ran | Record | Automated coverage |
|---|---|---|---|---|---|---|
| `a-release-scoped-collector-scrapes-both-inferops-jobs-on-the-reference-provider` | certified | C2 | `local-real-cpu` | local-kubernetes, `docker-desktop` | [v1-s3-011-pr2-telemetry-during-recovery.md](../proof/telemetry/v1-s3-011-pr2-telemetry-during-recovery.md), [v1-s3-011-pr1-docker-desktop-paved-road.md](../proof/environment/v1-s3-011-pr1-docker-desktop-paved-road.md) | 4 module(s) |
| `six-v1-alerts-carry-an-owner-a-severity-an-evidence-query-and-a-runbook-link` | certified | C0 | `local-static` | repository-only | [v1-s4-008-pr1-alert-validation.md](../proof/telemetry/v1-s4-008-pr1-alert-validation.md), [v1-s4-008-pr1-validation.md](../proof/telemetry/v1-s4-008-pr1-validation.md) | 2 module(s) |
| `the-api-emits-catalog-metrics-and-structured-request-records` | certified | C1 | `mock` | repository-only | [v1-s1-008-pr1-validation.md](../proof/telemetry/v1-s1-008-pr1-validation.md) | 3 module(s) |
| `the-inference-operations-dashboard-was-asked-of-a-real-prometheus-and-rendered` | certified | C2 | `local-real-cpu` | local-kubernetes, `docker-desktop` | [v1-s4-002-pr2-dashboard-validation.md](../proof/telemetry/v1-s4-002-pr2-dashboard-validation.md), [v1-s4-002-pr1-validation.md](../proof/telemetry/v1-s4-002-pr1-validation.md) | 2 module(s) |
| `the-telemetry-catalog-cannot-admit-a-prompt-or-an-unbounded-label` | certified | C0 | `local-static` | repository-only | [v1-s0-007-pr1-validation.md](../proof/telemetry/v1-s0-007-pr1-validation.md), [v1-s1-008-pr1-validation.md](../proof/telemetry/v1-s1-008-pr1-validation.md) | 2 module(s) |
| `the-v1-alerts-were-replayed-over-the-telemetry-three-real-experiments-recorded` | certified | C0 | `local-static` | repository-only | [v1-s4-008-pr1-alert-validation.md](../proof/telemetry/v1-s4-008-pr1-alert-validation.md), [v1-s4-007-pr1-unready-model-recovery.md](../proof/serving/v1-s4-007-pr1-unready-model-recovery.md) | 1 module(s) |
| `no-prompt-response-or-secret-reaches-a-log-or-a-metric` | planned | — | `documented-unexecuted` | capable-host | none, by rule | 2 module(s) |
| `an-alert-reaches-somebody` | not-claimed | — | `documented-unexecuted` | local-kubernetes | none, by rule | none |

The alert rows are two claims rather than one, deliberately. The alert *set* is a
`local-static` result over synthetic fixtures; the *replay* reads telemetry that
three real `docker-desktop` experiments captured, and is **also** `local-static`,
because the evaluator over those captures is this repository's own and its record
classifies itself that way. The replay row claimed `local-real-cpu` at `C2` until an
independent review compared it with the record it cites. Neither row reaches the
thing a reader will assume: **nothing evaluates or routes any of it.** There is no
receiver, no routing tree, and nobody on the other end, which is why
`an-alert-reaches-somebody` is a row here and its status is `not-claimed`.

The collector row carries the other correction worth making in public. Telemetry
did **not** detect the release failure Sprint 3 injected — the Kubernetes API's
init-container exit status did. `inferops_model_ready` was not emitted at all, and
`kube_pod_container_status_restarts_total` had no source.

### Cost

| Claim | Status | Level | Evidence label | Where it ran | Record | Automated coverage |
|---|---|---|---|---|---|---|
| `a-cost-figure-cannot-be-presented-as-a-bill` | certified | C0 | `local-static` | repository-only | [v1-s0-008-pr1-validation.md](../proof/cost/v1-s0-008-pr1-validation.md), [v1-s4-005-pr1-validation.md](../proof/cost/v1-s4-005-pr1-validation.md) | 3 module(s) |
| `the-cost-method-was-applied-to-use-taken-from-a-measured-run` | certified | C0 | `local-static` | repository-only | [v1-s4-005-pr2-cost-baseline.md](../proof/cost/v1-s4-005-pr2-cost-baseline.md), [v1-s4-005-pr2-validation.md](../proof/cost/v1-s4-005-pr2-validation.md) | 1 module(s) |
| `what-running-an-inference-workload-costs-on-a-provider` | not-claimed | — | `estimated` | repository-only | none, by rule | none |

The certified rows are about **method**, not money, and both are file-reading
operations. One certifies that the vocabulary of a provider statement is refused to
any basis that has not earned it; the other certifies that two cost records take
their use from committed samples by tool rather than from a typed-in figure, and
regenerate from their own inputs. The samples themselves were measured on
`docker-desktop`; that measurement is the performance row, not this one. Every price behind them comes from a
synthetic rate card, so both records carry confidence `none` and certify nothing
themselves. Nothing here has ever been paid for, so `actual` is unreachable and
`what-running-an-inference-workload-costs-on-a-provider` is not claimed.

### Security

| Claim | Status | Level | Evidence label | Where it ran | Record | Automated coverage |
|---|---|---|---|---|---|---|
| `a-security-control-cannot-claim-enforcement-it-does-not-have` | certified | C0 | `local-static` | repository-only | [v1-s0-009-pr1-validation.md](../proof/security/v1-s0-009-pr1-validation.md) | 1 module(s) |
| `a-workload-manifest-that-omits-a-required-security-control-is-refused` | certified | C0 | `local-static` | repository-only | [v1-s3-004-pr1-validation.md](../proof/security/v1-s3-004-pr1-validation.md), [v1-s3-011-pr1-docker-desktop-paved-road.md](../proof/environment/v1-s3-011-pr1-docker-desktop-paved-road.md) | 1 module(s) |
| `the-pinned-image-and-the-locked-dependencies-were-scanned-and-a-bill-of-materials-published` | certified | C0 | `local-static` | repository-only | [v1-s2-006-pr1-validation.md](../proof/security/v1-s2-006-pr1-validation.md) | 1 module(s) |
| `no-credential-or-model-artifact-enters-public-history` | planned | — | `documented-unexecuted` | repository-only | none, by rule | **recorded gap** |
| `a-deployed-inferops-workload-is-defended` | not-claimed | — | `documented-unexecuted` | local-kubernetes | none, by rule | none |
| `the-rendered-network-policy-is-enforced-by-the-cluster` | not-claimed | — | `local-real-cpu` | local-kubernetes, `docker-desktop` | [v1-s3-004-pr1-network-policy-enforcement.md](../proof/security/v1-s3-004-pr1-network-policy-enforcement.md) | 1 module(s) |

Three certified rows, one planned, and two not claimed — a ratio that is the
honest shape of V1's security position. The certified rows are about documents,
YAML, and one day's scanner output: a control cannot assert a status it has not
earned, a manifest dropping a required control is refused, and the pinned image
and the locked dependencies were each scanned once, by hand. None of them reads a
running pod.

`the-rendered-network-policy-is-enforced-by-the-cluster` is the row this project
would most like to delete. It cites a record because the answer was measured and
the answer was **no**: a total-denial policy was applied and nothing was refused,
because the observed network plugin runs with no policy controller. That moved
`DR-04` from untested to tested-and-not-enforced — a worse position than the
register had recorded.

### Tests, continuous integration, and evidence

| Claim | Status | Level | Evidence label | Where it ran | Record | Automated coverage |
|---|---|---|---|---|---|---|
| `eleven-default-lane-gates-are-committed-and-mapped-to-the-claims-they-defend` | certified | C0 | `local-static` | repository-only | [v1-s4-001-pr1-validation.md](../proof/testing/v1-s4-001-pr1-validation.md), [v1-s4-001-pr2-validation.md](../proof/testing/v1-s4-001-pr2-validation.md) | 2 module(s) |
| `every-certifying-record-lives-under-docs-proof-and-declares-its-own-boundary` | certified | C0 | `local-static` | repository-only | [v1-s0-007-pr1-validation.md](../proof/telemetry/v1-s0-007-pr1-validation.md) | 1 module(s) |
| `no-resource-in-the-architecture-has-two-owners` | certified | C0 | `local-static` | repository-only | [v1-s0-005-pr1-validation.md](../proof/architecture/v1-s0-005-pr1-validation.md), [v1-s3-002-pr2-validation.md](../proof/architecture/v1-s3-002-pr2-validation.md), [v1-s3-010-pr1-validation.md](../proof/architecture/v1-s3-010-pr1-validation.md) | 3 module(s) |
| `published-documents-link-only-to-things-that-exist` | certified | C0 | `local-static` | repository-only | [v1-s0-006-pr1-validation.md](../proof/testing/v1-s0-006-pr1-validation.md) | 1 module(s) |
| `the-default-lane-cannot-execute-a-real-model` | certified | C0 | `local-static` | repository-only | [v1-s0-006-pr1-validation.md](../proof/testing/v1-s0-006-pr1-validation.md), [v1-s4-001-pr2-validation.md](../proof/testing/v1-s4-001-pr2-validation.md) | 2 module(s) |
| `the-published-strategy-and-its-data-cannot-drift-apart` | certified | C0 | `local-static` | repository-only | [v1-s0-006-pr1-validation.md](../proof/testing/v1-s0-006-pr1-validation.md), [v1-s1-007-pr1-validation.md](../proof/testing/v1-s1-007-pr1-validation.md), [v1-s4-001-pr1-validation.md](../proof/testing/v1-s4-001-pr1-validation.md), [v1-s4-009-pr1-validation.md](../proof/testing/v1-s4-009-pr1-validation.md) | 4 module(s) |
| `a-cluster-or-real-runtime-lane-runs-in-continuous-integration` | not-claimed | — | `documented-unexecuted` | repository-only | none, by rule | none |
| `a-v1-release-has-been-published` | not-claimed | — | `documented-unexecuted` | repository-only | none, by rule | none |
| `inferops-is-a-portable-production-platform` | not-claimed | — | `production-experience` | repository-only | none, by rule | none |

Six of these nine certify properties of this repository's own discipline, which is
the weakest kind of claim and the one most easily mistaken for a strong one.
Eleven gates are committed and nine have passed on the selected service; that
automates the mock lane and **raises no ceiling at all**. A mock is still `C1`,
and the claims about a real runtime and a real cluster take no support from that
workflow.

The last row in the table is the one every other row exists to support. It is not
claimed, it never will be inside V1, and saying so in a register is cheaper than
arguing about it later.

## What V1 does not claim

8 rows carry `not-claimed`. They are collected here because a reader looking
for what is missing should not have to read eleven tables to find it.

| Claim | Why it is not claimed |
|---|---|
| `multi-replica-serving-is-certified` | The workflow was run on the reference host and refused at the capacity gate before it installed anything: 8,484,278,272 bytes of uncommitted cluster memory available against 8,657,043,456 required, a shortfall of about 165 MiB held by unrelated workloads that were not this project's to remove. The gate was not weakened and the replica count was not reduced to fit. |
| `an-alert-reaches-somebody` | No alert manager, receiver, routing tree, or notification path is committed or installed. The rules render into the chart and nothing evaluates or routes them. |
| `what-running-an-inference-workload-costs-on-a-provider` | Nothing here has ever been paid for. It runs on a local single-node cluster on a contributor's own machine, no provider account exists, and the `actual` basis is therefore unreachable in V1. |
| `the-rendered-network-policy-is-enforced-by-the-cluster` | An executed experiment on 2026-09-06 applied a total-denial policy and nothing was refused: pod-to-pod by address, a DNS lookup, and a direct query to CoreDNS all succeeded, because the observed network plugin runs with no policy controller enabled. The four policy objects the chart renders are inert on that plugin. |
| `a-deployed-inferops-workload-is-defended` | Nothing in this repository authenticates a caller, authorises a request, or admits a pod. There is no admission control, no gateway, and no multi-tenancy. Twelve risks are carried rather than reduced and ten of them block production use. |
| `a-cluster-or-real-runtime-lane-runs-in-continuous-integration` | No workflow for a cluster lane is committed, only the rules one must satisfy. No runner is labelled capable and no hosted runner is authorized to hold the pinned model artifact; ADR 0005 D6 leaves that half open on purpose. |
| `a-v1-release-has-been-published` | The release process is documented and no release has been executed. The changelog holds unreleased changes only. |
| `inferops-is-a-portable-production-platform` | `production-experience` is unreachable from this repository: there is no organizational production to draw it from, and public-cloud execution is not production operation. Every executed result is one Windows host, one provider, CPU, one replica of each tier, started by hand under explicit authorization against a cluster the operator already owns. |

Two of them cite a record. `multi-replica-serving-is-certified` cites the run that
was refused at the capacity gate, and
`the-rendered-network-policy-is-enforced-by-the-cluster` cites the experiment that
applied a total-denial policy and watched nothing be refused. Neither record makes
the claim weaker than silence would; both make the absence checkable.

## Surfaces that make no capability claim

8 public entry points in the README are reference, policy, or a
projection of this register rather than a claim about what the software does. They
are listed rather than skipped, so that the completeness check has something to
compare against and the exclusion list cannot quietly grow.

| Surface | Why it claims nothing |
|---|---|
| [CONTRIBUTING.md](../../CONTRIBUTING.md) | Contribution and review convention. It states how a change is validated and how evidence is labelled, and asserts no capability. |
| [docs/governance/repository.md](../governance/repository.md) | Repository governance for this skeleton. It describes how the repository is run rather than what the software does. |
| [docs/architecture/README.md](../architecture/README.md) | The index of accepted decisions. Each ADR is a decision; the capabilities they enable are claimed by the rows above. |
| [docs/architecture/decisions/ADR-0009-python-toolchain.md](../architecture/decisions/ADR-0009-python-toolchain.md) | A toolchain decision. It is a condition every other result is read under rather than a published capability. |
| [SECURITY.md](../../SECURITY.md) | Reporting expectations, and a recorded gap: no private channel is published. The gap belongs to the security rows above. |
| [CODE_OF_CONDUCT.md](../../CODE_OF_CONDUCT.md) | Interim conduct expectations, with a formal policy deferred. |
| [LICENSE](../../LICENSE) | The MIT licence text. It grants permission and disclaims warranty, which is a legal statement rather than a claim about what this software does. |
| [docs/proof/dashboard.md](../proof/dashboard.md) | A generated projection of this register. Every status, certification level, evidence label, provider, environment, record, and limitation it shows is read from this file when the page is rendered, and a test regenerates the page and fails if the two disagree. It asserts no capability of its own; the rows above assert all of them. |

## What this matrix does not do

- It does not establish that any statement in it is true. The suite checks
  references, ranks, ceilings, and vocabulary. Whether a record says what the row
  citing it says it says is a reading, and no test performs one.
- It does not raise any certification level. Levels are reached by records, and a
  row here restates one rather than granting it.
- It does not replace the per-claim evidence record. The
  [`claim-evidence` template](../proof/templates/TEMPLATE-claim-evidence.md) has
  still produced nothing, and binding claims in a table is a weaker form than the
  one-claim-per-record document that template exists to enforce.
- It does not cover the case study, which has not been written. Its claims are
  expected to be drawn from these rows; until it exists, the README is the only
  published surface a row is bound to, and a future case-study claim with no row
  here would be caught by nothing.

## Limitations

- This matrix is maintained by hand and checked by a suite. The suite
  establishes that a row's references resolve, that its status is not stronger
  than the strategy's, that its level fits its label, and that every README
  entry point is governed. It cannot establish that a statement is true, that a
  limitation is complete, or that a record says what the row says it says. Those
  remain a reading, and the reading is the work.
- Every real result cited here comes from one Windows host. Most are on the
  `docker-desktop` provider; the C2 certification, the serving baseline, and the
  lifecycle comparison are loopback compositions rather than Kubernetes results,
  the feasibility trial ran inside the container desktop distribution's own
  cluster before the provider contract existed, and the cluster smoke is the
  only `kind` result in the table. None of them generalizes to another provider,
  another host, a GPU, or more than one replica.
- The bounded performance, recovery, and cost figures quoted in these rows are
  published under ADR 0013 and ADR 0014 as observations of one declared local
  experiment. They are not capacity, service-level objectives, availability
  figures, error budgets, recovery-time objectives, benchmarks, or costs.
- The statuses here are the repository's own. No outside party has reviewed a
  claim against its evidence, and no maintainer roster exists to arbitrate a
  dispute — the same governance gap that stops an owner being named as a person.
- The `claim-evidence` template under docs/proof/templates/ has still produced
  no record. This matrix binds claims to evidence in a table, which is a weaker
  form than the one-claim-per-record document that template exists to enforce,
  and it does not raise that count.
- A row's automated tests name modules rather than test functions. A module that
  protects a claim may protect several, and nothing here says which function
  would fail first if the claim stopped being true. Five rows name modules for a
  claim the inventory records as covered by none; those rows carry the gap in
  `recordedCoverageGaps` and in their limitation, and the modules they name are
  adjacent to the claim rather than proof of it.
- Nine of the eleven continuous-integration gates have passed on the selected
  service and no log from those runs is promoted into a record. Every other
  check cited here was run by hand, on one host, by the author.
- Twenty-two of the fifty-eight rows were corrected before this register was
  merged, and fourteen of those shared one shape: the row stated the
  repository's state today while citing a record that froze an earlier one — the
  security control counts, the ownership row counts, the gate counts, the
  template counts, the strategy-drift scope, and the claim that a release had
  been installed among them. Each was fixed by citing the later record as well,
  or by restating the figure the cited record actually holds; four more were
  misreadings of a record, and four could not be fixed by re-citing at all.
  Nothing in the suite would have caught any of them: they are exactly what the
  first limitation above describes, and they were found by an independent reader
  opening all forty-six cited records and comparing them with the rows citing
  them.
- The case study this matrix is meant to govern has not been written. Its claims
  are expected to be drawn from these rows; until it exists, `readmeRefs` is the
  only surface binding a row to published text, and a future case-study claim
  with no row here would be caught by nothing.
