# The test inventory

Status: **published inventory**, added by `V1-S1-007-PR1` under the strategy
[ADR 0005](../architecture/decisions/ADR-0005-test-ci-and-certification-strategy.md)
accepted. It lists every pytest module in this repository, the test layer it
belongs to, the lane that layer runs in, and the published claim each one
protects.

The authoritative form is
[`test-inventory.v1alpha1.json`](test-inventory.v1alpha1.json), and
[`tests/testing/test_test_inventory.py`](../../tests/testing/test_test_inventory.py)
compares it with the test tree and with
[the strategy data](test-strategy.v1alpha1.json) in both directions. A module
absent from it, a module whose recorded layer disagrees with the strategy's own
paths, a module naming a claim its layer does not support, and a claim no module
names are each a build failure.

## Why this exists

[The strategy](test-strategy.md) says which layers exist, which lane each runs
in, and what a result from each is allowed to certify.
[The claim and test matrix](claim-test-matrix.md) says which layers each public
claim rests on. Between them there was no way to ask the question a reviewer
actually asks: **if this claim stopped being true, which suite would fail?**
Answering it meant reading forty-odd modules and inferring.

This inventory answers it for every module and every claim, and the checks behind
it are the reason the answer stays true. It is a coverage record, **not a
certification record**: what a passing result may be used to claim is decided by
the layer's evidence class in the strategy, and nothing here raises a ceiling.

## How to read a row

Every module names a layer, that layer's marker, one sentence on what it
protects, and the claims it contributes to. Four rules are enforced rather than
intended:

1. every `test_*.py` under [`tests/`](../../tests/) appears exactly once, and
   every listed module exists;
2. the recorded layer is the one the strategy's declared paths give the module,
   and the recorded marker is that layer's, declared at module level in the file;
3. a module may name only claims whose layers include its own — so a `mock` suite
   cannot be recorded as defending a claim that requires a real runtime;
4. every claim is named by at least one module or recorded below as a gap with a
   reason, and never both.

A module that defends no published claim carries a written reason instead of an
empty list. There are fifteen, and they are listed in their own section rather than
hidden in the data.

## Lanes and markers, as the inventory groups them

Every module belongs to exactly one layer, and the layer decides the lane. The
grouping below is the "CI test grouping" this story owes, and the honest form of
it: **no continuous-integration service is configured**, every lane is run by
hand, and a lane may claim automation only by naming a workflow file that exists.

| Lane | Layers inventoried in it | Marker expression to run it | Needs |
|---|---|---|---|
| `default-checks` | `unit`, `contract-and-schema`, `architecture-inventory`, `adapter`, `mock-integration`, `documentation` | `python -m pytest -q` | a checkout and an interpreter |
| `real-runtime` | `real-runtime-smoke` | `python -m pytest -m realruntime -q` | the pinned model and runtime, on a capable host, deliberately |
| `cluster-smoke` | `kubernetes-smoke` | no pytest module; see the gaps below | a local Kubernetes cluster |
| `capacity` | `capacity-and-load` | deferred out of V1 | — |

The default lane is everything the marker expression in
[`pytest.ini`](../../pytest.ini) does not deselect. Two of the checks in the
inventory suite are about exactly that: every inventoried module whose layer
needs a cluster or a model carries a marker the default expression excludes, and
no module in the default lane is attributed to a layer that needs either.

Selecting one layer inside the default lane is a marker expression:

```sh
python -m pytest -q                       # the default lane
python -m pytest -m contract -q           # the contract and schema layer
python -m pytest -m adapter -q            # the serving adapter layer
python -m pytest -m mockintegration -q    # the API against the mock
python -m pytest -m unit -q               # the domain
python -m pytest -m architecture -q       # the ownership and dependency rules
python -m pytest -m docs -q               # published data against its documents
python -m pytest -m realruntime -q        # opt in, on a capable host
```

## What each group protects

The sentences below are summaries of the layer. The per-module sentence is in
[the data](test-inventory.v1alpha1.json), which is where a reader looking for one
module should go.

### `unit` — [`tests/domain/`](../../tests/domain/)

Five modules. The workload domain model — what parses, what is refused, and the
rule that a refusal never repeats a value read out of a document — the domain's
copy of the published contract compared against the schema, and the serving
protocol's own in-memory double against the shared conformance suite.

### `contract-and-schema` — [`tests/contracts/`](../../tests/contracts/), [`tests/scaffolding/`](../../tests/scaffolding/)

Six modules. The published schema, every valid and invalid fixture with the exact
refusal recorded for it, the workload template and the command that writes it to
a disk, and — added by this story — the agreement between the three surfaces that
read a WorkloadContract.

### `architecture-inventory` — [`tests/architecture/`](../../tests/architecture/)

Four modules. The committed ownership inventory against the documents describing
it; every module under `src/inferops/` read for the imports the dependency rule
forbids; the cluster and release lifecycle scripts read for the safety rules
ADR 0001 and ADR 0004 state for them; and the Helm chart read against the release
half of the ownership inventory, its accepted pins, the mock and real boundary,
the accepted health records that decide what its probes may be, and the model
cache mount -- that it is scoped to the declared revision, that no values path
reaches that scoping, and that the file the init container verifies is the file
the runtime is given.

The count said two until this story and had been wrong since `V1-S3-001-PR1`
added the third. It is not machine-checked, which is why it drifted.

### `adapter` — [`tests/adapters/`](../../tests/adapters/)

Thirteen modules. The committed mock and the adapter for the selected runtime,
each against the shared conformance suite, plus the pins, settings, transport,
readiness, capability, and metadata behaviour each one owes. This story added the
check that the set of adapters covered is the set of adapters shipped.

### `mock-integration` — [`tests/api/`](../../tests/api/)

Ten modules. The API driven against the committed mock and controlled doubles:
the success shape, canonical errors, configuration-driven adapter selection, and
drain order. The local-composition module also crosses a loopback socket into the
real adapter type over a synthetic transport; it loads no model, contacts no real
runtime, and remains `C1` evidence.

### `documentation` — [`tests/testing/`](../../tests/testing/), [`tests/telemetry/`](../../tests/telemetry/), [`tests/cost/`](../../tests/cost/), [`tests/security/`](../../tests/security/), [`tests/serving/`](../../tests/serving/)

Sixteen modules. Committed machine-readable data checked against the documents
describing it: the test strategy, this inventory, the telemetry catalog, the cost
method, the security baseline, the inference API surface, and the selected model's
source and cache workflow, runtime profile, standalone package, C2 certification
descriptor, registered serving baseline, model lifecycle state model, and the
local runtime troubleshooting guide — and,
since the API began emitting, the catalog checked against what the distribution
declares rather than only against its own prose.

### `real-runtime-smoke` — [`tests/realruntime/`](../../tests/realruntime/)

Two modules, both deselected by default and **neither has ever been run against a
runtime**. They read their runtime settings from the process environment and skip
when those are unset, so naming the marker without a runtime produces a skip
rather than a failure. The evidence cited for the serving claims stays the manual
trial recorded under [`docs/proof/serving/`](../proof/serving/).

## Modules that defend no published claim

Fifteen suites protect something no row of the claim matrix names. Each carries its
reason in the data; they are collected here because a reader deciding whether the
matrix is complete needs to see them together.

| Module | What it protects instead |
|---|---|
| [`tests/architecture/test_cluster_lifecycle_safety.py`](../../tests/architecture/test_cluster_lifecycle_safety.py) | How the local cluster lifecycle scripts are written: scoped deletions, no ambient kubeconfig, no engine-wide prune, and thresholds that match the tier they enforce. The claim that a cluster is created and removed without residue belongs to the cluster-smoke layer, which runs the scripts instead of reading them |
| [`tests/architecture/test_domain_dependency_boundary.py`](../../tests/architecture/test_domain_dependency_boundary.py) | The dependency rule. An architecture decision rather than a product claim — and the reason the `unit` layer is possible at all |
| [`tests/adapters/test_llama_server_pins.py`](../../tests/adapters/test_llama_server_pins.py) | That a constant copied out of an accepted decision still matches its source. The claim about the artifact's hash is certified by a manual procedure, not by this module |
| [`tests/api/test_api_lifecycle.py`](../../tests/api/test_api_lifecycle.py) | The order of start, drain, and stop. ADR 0010 chose a graceful drain over a remote-stop endpoint and the matrix has no row for it |
| [`tests/api/test_local_real_composition.py`](../../tests/api/test_local_real_composition.py) | Real-only local wiring, readiness order, reverse cleanup, authorization refusal, and the tooling HTTP carrier through controlled seams; no real-runtime claim can rest on generated transport responses |
| [`tests/serving/test_model_acquisition.py`](../../tests/serving/test_model_acquisition.py) | The selected source record and cache mechanics using tiny synthetic bytes. The real model's integrity remains certified by the authorization-gated procedure, not by this suite |
| [`tests/serving/test_runtime_configuration.py`](../../tests/serving/test_runtime_configuration.py) | The pinned local runtime profile, its external model boundary, resources, defaults, health semantics, secret boundary, and compatibility with the real adapter. Runtime startup remains for local-real packaging evidence |
| [`tests/serving/test_runtime_packaging.py`](../../tests/serving/test_runtime_packaging.py) | The standalone Docker descriptor and guarded lifecycle through injected command and HTTP seams. It proves package mechanics, not a real startup or completion |
| [`tests/serving/test_runtime_certification.py`](../../tests/serving/test_runtime_certification.py) | The C2 certification descriptor, its refusal of a weakened level or waived assertion, the hardware refusal, the mock-identity prohibition, and the record it writes. The `local-real-cpu` label it exercises is truthful only for an authorized run |
| [`tests/serving/test_serving_baseline.py`](../../tests/serving/test_serving_baseline.py) | The registered baseline's agreement with the composition it measures, its percentile arithmetic, and its deterministic summary. Every request is answered by an injected seam, so no latency here is a serving measurement |
| [`tests/serving/test_model_lifecycle.py`](../../tests/serving/test_model_lifecycle.py) | The accepted lifecycle state model against the package, the model record, and the API's drain budget; the rule that liveness passes while readiness is false during a load; and two measurements whose every timing is arithmetic on a fake clock, including that the restart comparison reads the artifact after both starts rather than between them |
| [`tests/serving/test_local_runtime_troubleshooting.py`](../../tests/serving/test_local_runtime_troubleshooting.py) | The published troubleshooting guide against the tools, descriptors, and records it quotes. It establishes that the guide has not drifted, never that following one of its recoveries repairs a fault |
| [`tests/serving/test_inference_api_surface.py`](../../tests/serving/test_inference_api_surface.py) | The committed API compatibility surface against its document |
| [`tests/serving/test_inference_api_implementation_agreement.py`](../../tests/serving/test_inference_api_implementation_agreement.py) | Every constant in the API package that repeats a row of that record |
| [`tests/testing/test_toolchain.py`](../../tests/testing/test_toolchain.py) | The accepted toolchain decision against the configuration implementing it, including the rule that keeps the pytest configuration out of `pyproject.toml` |

The two API-surface rows are the interesting pair. The matrix's drift claim,
`the-published-strategy-and-its-data-cannot-drift-apart`, is written about the
test strategy's own lane, layer, and claim identifiers. These two suites protect
the same *kind* of property for a different record, and the matrix has no row for
it — which is a gap in the matrix rather than in the suites, and it is recorded
here rather than closed by widening a claim's wording.

## Coverage gaps

Six claims are not defended by any module here. Each is recorded with a reason
and, where something outside pytest defends it, what that is.

| Claim | Why no module | Defended by |
|---|---|---|
| `published-documents-link-only-to-things-that-exist` | No pytest module walks every relative link in every published document. The data suites each assert that their own record's references resolve, which is a subset of the claim | The link and whitespace check published in [CONTRIBUTING](../../CONTRIBUTING.md), run by hand |
| `the-model-artifact-matches-its-published-hash` | No pytest module computes or compares the hash. The real-runtime suite drives a running runtime, and the runtime exposes no hash of the file it loaded | The download step of [the feasibility workflow](../serving/feasibility-workflow.md), with both hashes recorded in [its evidence record](../proof/serving/v1-s0-003-pr2-runtime-feasibility.md) |
| `a-local-cluster-is-created-and-removed-without-residue` | The `kubernetes-smoke` layer declares no test paths | [`scripts/environment/`](../../scripts/environment/), run by hand, with the record under [`docs/proof/environment/`](../proof/environment/) |
| `no-credential-or-model-artifact-enters-public-history` | The `security-scan` layer is planned. A configuration and an allowlist are committed and no recorded run of a scanner exists | Nothing yet |
| `a-helm-release-installs-and-uninstalls-without-residue` | A chart and a lifecycle procedure exist and nothing has installed anything; the layer the claim names declares no test paths | Nothing yet. [`scripts/environment/helm-lifecycle.sh`](../../scripts/environment/helm-lifecycle.sh) would answer it and cannot be run until an InferOps API image exists |
| `sustained-throughput-and-capacity-under-load` | Deferred out of V1. A module here would produce output nothing may publish | Nothing, deliberately |

The first two rows are the ones worth reading twice. Both claims are
**certified**, and the evidence for each is a procedure rather than a suite — a
shell check for the first, a manual download for the second. Both are legitimate,
and both are exactly the kind of thing an inventory of pytest modules would
otherwise imply was missing.

## What this inventory does not do

- **It certifies nothing.** A module listed against a claim contributes to it; it
  does not raise what the layer's evidence class permits. Two of the modules here
  have never been executed at all.
- **It does not judge a suite.** A module with a confident sentence beside it may
  still be shallow. Nothing here reads an assertion.
- **It is not a coverage percentage.** No line or branch coverage is measured,
  reported, or required anywhere in this repository, and this file does not
  introduce one.
- **It configures no continuous integration.** The lane table above is a grouping
  and a set of commands. There is no workflow file, and the strategy suite refuses
  to let any lane claim otherwise.
