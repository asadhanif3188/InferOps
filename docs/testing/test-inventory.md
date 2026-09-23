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
empty list. There are thirty-seven, and they are listed in their own section rather than
hidden in the data.

## Lanes and markers, as the inventory groups them

Every module belongs to exactly one layer, and the layer decides the lane. The
grouping below is the "CI test grouping" this story owes, and the honest form of
it. **This paragraph said "no continuous-integration service is configured" until
2026-09-21**, which stopped being true when
[ADR 0012](../architecture/decisions/ADR-0012-continuous-integration-service.md)
selected one and committed
[`.github/workflows/checks.yml`](../../.github/workflows/checks.yml). What is true
now: the `default-checks` lane is run by that workflow, as eleven gates mapped to it
in both directions by [the gate matrix](ci-gate-matrix.md); every other lane is still
run by hand, no job has ever reached a cluster, and the rule that produced this
sentence is unchanged -- a lane may claim automation only by naming a workflow file
that exists.

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

Twenty-three modules. The committed ownership inventory against the documents describing
it; the local cluster provider contract against its document, the ownership
inventory, the guard functions in `lib.sh`, and the Terraform module; every module under `src/inferops/` read for the imports the dependency rule
forbids; the cluster and release lifecycle scripts read for the safety rules
ADR 0001 and ADR 0004 state for them; the Terraform prerequisite layer against
the ownership boundary it implements; the Helm chart read against the release
half of the ownership inventory, its accepted pins, the mock and real boundary,
the accepted health records that decide what its probes may be, and the model
cache mount -- that it is scoped to the declared revision, that no values path
reaches that scoping, and that the file the init container verifies is the file
the runtime is given; and the three Kubernetes workflows -- the single-replica
certification, the multi-replica one, and the upgrade-and-rollback experiment --
each read as a descriptor, a script, and the documents a run would have written.
Two are the clean-clone workflow: its orchestrator executed in a sandbox
against recording stubs, and the rules of the ledger it keeps. The newest is the
operator runbook, read against the alert record, the scripts, the render, and the
records whose figures it quotes.

The count said two until `V1-S3-001-PR1`, then four, and it was wrong both times
and again before this story: seven modules existed while the sentence said four.
It is not machine-checked, which is why it keeps drifting, and it is recorded
here rather than quietly corrected. It drifted once more after that: by
`V1-S3-010-PR1` thirteen modules existed while the sentence said nine, and that
change added the fourteenth. It drifted again: by `V1-S4-003-PR1` sixteen modules
existed while the sentence said fourteen. That change added no module to this
layer and corrected the sentence. It drifted a fourth time, and `V1-S4-009-PR2`
found it: nineteen modules existed while the sentence said eighteen. That change
added no module to this layer either, corrected the sentence, and added the check
below, so this paragraph is the last entry this list can gain by drifting.
`V1-S5-001-PR1` added the twentieth and twenty-first.

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

Thirty-five modules. Committed machine-readable data checked against the documents
describing it: the test strategy, this inventory, the telemetry catalog, the cost
method, the security baseline, the inference API surface, and the selected model's
source and cache workflow, runtime profile, standalone package, C2 certification
descriptor, registered serving baseline, model lifecycle state model, and the
local runtime troubleshooting guide — and,
since the API began emitting, the catalog checked against what the distribution
declares rather than only against its own prose. The two most recent are the
Kubernetes telemetry collection record against the chart renders, and the
correlation queries against both of those and against synthetic stores. Then came
the repeatable LLM load profile: its agreement with the chart and the runtime
profile, the order every response is classified in, the accounting of every
dispatched request, and a rehearsal over loopback HTTP whose output is synthetic. The
next was the performance scenario matrix: its descriptor against that profile and the
chart, the record's placement and stability rules, and the committed real record
regenerating from its inputs. Then came the findings derived from that record:
derivation refused unless the record regenerates, and the published report's tables
held to the findings file. Then came the cost calculation: the estimated basis
applied to a declared input, its refusals, its arithmetic on synthetic fixtures held to
values worked out by hand, and every record it writes validated against the method's
record shape. The newest is the cost baseline: usage taken from the committed samples
only when the record regenerates, every value recomputed from the sample lines by a
second route, and the published report's figures held to its results. Then came
the claim and evidence matrix: every row held to its own limitation, its status held
to the strategy's, its level held to its evidence label's ceiling, and the README's
public entry points held to the rows that govern them. The newest is the proof
dashboard generated from that register: the committed page regenerated and compared,
every count on it recomputed, and each of the nine rules its generator applies driven
over a register corrupted to break it.

The count said seventeen until this story and had been wrong since `V1-S3-007-PR1`
added the eighteenth. It is not machine-checked, which is why it drifted — the same
way `architecture-inventory`'s did, and it is recorded here for the same reason. It
drifted once more: by `V1-S4-003-PR1` twenty-five modules existed while the sentence
said nineteen. That change added the twenty-sixth and corrected the count.
`V1-S4-004-PR1` added the twenty-seventh, `V1-S4-004-PR2` the twenty-eighth,
`V1-S4-005-PR1` the twenty-ninth, `V1-S4-005-PR2` the thirtieth,
`V1-S4-009-PR1` the thirty-second, `V1-S4-009-PR2` the thirty-third, and
`V1-S5-004-PR1` the thirty-fourth, which holds the two published V1 methods to the
records they summarise, and `V1-S5-011-PR1` the thirty-fifth, which holds the
evidence-level specification to the documents it supersedes.

That sentence is itself a correction. `V1-S4-009-PR1` added a module and wrote
"thirty-first", and an independent review of `V1-S4-009-PR2` found thirty-two
modules behind it: the count had drifted once more before `V1-S4-009-PR1` added
to it, and adding one to a wrong number kept it wrong. Both layers' counts are
now recomputed from the data by
[`tests/testing/test_test_inventory.py`](../../tests/testing/test_test_inventory.py),
which is the thing every one of these paragraphs said was missing.

One is the odd one in this layer: `tests/security/test_workload_policy.py`
reads manifests rather than a record, applying
[the workload policy](../security/workload-policy.md) to the chart's two committed
renders, to the manifests under `deploy/`, and to nine deliberately broken fixtures
that each drop one control. It sits here rather than in `architecture-inventory`
because what it defends is a security document's claim about itself, and its
evidence class is the same either way. It still reads files: it installs nothing and
contacts no cluster.

### `real-runtime-smoke` — [`tests/realruntime/`](../../tests/realruntime/)

Two modules, both deselected by default and **neither has ever been run against a
runtime**. They read their runtime settings from the process environment and skip
when those are unset, so naming the marker without a runtime produces a skip
rather than a failure. The evidence cited for the serving claims stays the manual
trial recorded under [`docs/proof/serving/`](../proof/serving/).

## Modules that defend no published claim

Thirty-four suites protect something no row of the claim matrix names. (This sentence
said twenty-four while the table below held twenty-five rows; `V1-S4-003-PR1` added
the twenty-sixth row and corrected it. `V1-S4-004-PR1` added the twenty-seventh and
first left this sentence at twenty-six; its review corrected it. `V1-S4-004-PR2` added
the twenty-eighth, and `V1-S4-006-PR1` the twenty-ninth. It drifted again: by
`V1-S5-001-PR1` the table held thirty-one rows while this sentence said thirty. That
change added the thirty-second and thirty-third and corrected it. `V1-S5-003-PR1` added the
thirty-fourth, and `V1-S5-004-PR1` the thirty-fifth. The machine-checked count is the one in the opening section.) Each carries its
reason in the data; they are collected here because a reader deciding whether the
matrix is complete needs to see them together.

| Module | What it protects instead |
|---|---|
| [`tests/architecture/test_cluster_lifecycle_safety.py`](../../tests/architecture/test_cluster_lifecycle_safety.py) | How the local cluster lifecycle scripts are written: scoped deletions, no ambient kubeconfig, no engine-wide prune, and thresholds that match the tier they enforce. The claim that a cluster is created and removed without residue belongs to the cluster-smoke layer, which runs the scripts instead of reading them |
| [`tests/architecture/test_domain_dependency_boundary.py`](../../tests/architecture/test_domain_dependency_boundary.py) | The dependency rule. An architecture decision rather than a product claim — and the reason the `unit` layer is possible at all |
| [`tests/architecture/test_decision_authority.py`](../../tests/architecture/test_decision_authority.py) | That no V1 architectural decision is left without an accountable owner, and that no document still says one is. Deliberately no claim: exercising any of the four authorities ADR 0015 declares changes no status, no certification level and no evidence class, so a row in the claim register would assert the opposite of what that record decided |
| [`tests/adapters/test_llama_server_pins.py`](../../tests/adapters/test_llama_server_pins.py) | That a constant copied out of an accepted decision still matches its source. The claim about the artifact's hash is certified by a manual procedure, not by this module |
| [`tests/api/test_api_lifecycle.py`](../../tests/api/test_api_lifecycle.py) | The order of start, drain, and stop. ADR 0010 chose a graceful drain over a remote-stop endpoint and the matrix has no row for it |
| [`tests/api/test_local_real_composition.py`](../../tests/api/test_local_real_composition.py) | Real-only local wiring, readiness order, reverse cleanup, authorization refusal, and the tooling HTTP carrier through controlled seams; no real-runtime claim can rest on generated transport responses |
| [`tests/serving/test_model_acquisition.py`](../../tests/serving/test_model_acquisition.py) | The selected source record and cache mechanics using tiny synthetic bytes. The real model's integrity remains certified by the authorization-gated procedure, not by this suite |
| [`tests/serving/test_runtime_configuration.py`](../../tests/serving/test_runtime_configuration.py) | The pinned local runtime profile, its external model boundary, resources, defaults, health semantics, secret boundary, and compatibility with the real adapter. Runtime startup remains for local-real packaging evidence |
| [`tests/serving/test_runtime_packaging.py`](../../tests/serving/test_runtime_packaging.py) | The standalone Docker descriptor and guarded lifecycle through injected command and HTTP seams. It proves package mechanics, not a real startup or completion |
| [`tests/serving/test_runtime_certification.py`](../../tests/serving/test_runtime_certification.py) | The C2 certification descriptor, its refusal of a weakened level or waived assertion, the hardware refusal, the mock-identity prohibition, and the record it writes. The `local-real-cpu` label it exercises is truthful only for an authorized run |
| [`tests/serving/test_serving_baseline.py`](../../tests/serving/test_serving_baseline.py) | The registered baseline's agreement with the composition it measures, its percentile arithmetic, and its deterministic summary. Every request is answered by an injected seam, so no latency here is a serving measurement |
| [`tests/serving/test_llm_load.py`](../../tests/serving/test_llm_load.py) | The repeatable LLM load profile's agreement with the chart and the runtime profile, the fixed order every response is classified in, exactly one outcome for every dispatched request, the raw reader's refusals, and a rehearsal over loopback HTTP. Every answer comes from an injected function or an in-process stub, so no latency here describes serving and the committed example is synthetic |
| [`tests/serving/test_performance_scenarios.py`](../../tests/serving/test_performance_scenarios.py) | The performance scenario matrix's agreement with the load profile and chart it pins, the load facts and environment derived from the cluster's own answers, the node cgroup sample parser, CPU placed strictly inside each phase window, a record that is not usable when pods change, counters disagree, or samples leave a gap, and the committed record regenerating from its inputs. Every raw set, cluster answer, and collector reading in its other tests is constructed, so no figure they produce describes serving; the committed record it regenerates is local real evidence and certifies no claim |
| [`tests/serving/test_performance_findings.py`](../../tests/serving/test_performance_findings.py) | The figures derived from the committed performance record and the report publishing them: derivation refused unless the record regenerates from its inputs, is usable, and claims no benchmark, capacity, or saturation judgement; the ratio, gap, gauge, and counter arithmetic; every row of its results tables, its setup table's figures, and the figures its prose quotes agreeing with the findings file. The record is local real evidence; the report's degradation statement is checked by review only and certifies no claim |
| [`tests/serving/test_model_lifecycle.py`](../../tests/serving/test_model_lifecycle.py) | The accepted lifecycle state model against the package, the model record, and the API's drain budget; the rule that liveness passes while readiness is false during a load; and two measurements whose every timing is arithmetic on a fake clock, including the full ordered sequence of probes and artifact reads a restart comparison performs — which is what shows that the start procedure reads the artifact before every start |
| [`tests/serving/test_local_runtime_troubleshooting.py`](../../tests/serving/test_local_runtime_troubleshooting.py) | The published troubleshooting guide against the tools, descriptors, and records it quotes. It establishes that the guide has not drifted, never that following one of its recoveries repairs a fault |
| [`tests/serving/test_inference_api_surface.py`](../../tests/serving/test_inference_api_surface.py) | The committed API compatibility surface against its document |
| [`tests/serving/test_inference_api_implementation_agreement.py`](../../tests/serving/test_inference_api_implementation_agreement.py) | Every constant in the API package that repeats a row of that record |
| [`tests/testing/test_toolchain.py`](../../tests/testing/test_toolchain.py) | The accepted toolchain decision against the configuration implementing it, including the rule that keeps the pytest configuration out of `pyproject.toml` |
| [`tests/testing/test_published_methods.py`](../../tests/testing/test_published_methods.py) | The published V1 security, observability, and cost and capacity methods against the records they summarise: every implemented item resolves to a defined test or an existing gate and a committed record and rests only on certified claims, every gap names what carries it and rests on no certified one, every control, register entry, exception, metric, alert, cost rule, basis, cost limitation, and open cost question appears on the side its own record puts it, every figure the cost method quotes reads back from the committed file it names, and the corrected statements stay corrected. Deliberately no claim: a method restates statuses other records own, and a row in the claim register would certify a summary rather than a property |
| [`tests/testing/test_evidence_levels.py`](../../tests/testing/test_evidence_levels.py) | The InferOps evidence-level model against the documents that publish it: that [the specification](evidence-levels.md) is the only document binding `C0` to `C4` to their current names, that a superseded meaning survives only in a mapping document or on a surface registered as awaiting migration and carrying a supersession notice, that the legacy mapping and the project-defined disclaimer are published, that ADR 0005 D4's accepted text is annotated rather than rewritten, and that the enforcing strategy data still carries the superseded names the specification says it carries -- a tripwire that fails when `V1-S5-011-PR2` versions the data model, so the page describing the old state is corrected in the same change. Deliberately no claim: it establishes that the repository states one definition, never that the definition is a good one or that any record is classified correctly under it |
| [`tests/architecture/test_kubernetes_certification.py`](../../tests/architecture/test_kubernetes_certification.py) | The Kubernetes real-inference certification read as committed data and text: the descriptor against the chart and the accepted budgets, the collected cluster facts against the descriptor, the refusal of mock identity and of a forward that is not loopback, and the safety properties of the operating script. The claim that the selected runtime serves a real completion in a cluster belongs to the real-runtime layer, which runs the workflow instead of reading it |
| [`tests/architecture/test_kubernetes_multi_replica_certification.py`](../../tests/architecture/test_kubernetes_multi_replica_certification.py) | The multi-replica Kubernetes certification read as committed data and text: the descriptor against the chart, the accepted budgets, and the single-replica descriptor it may not disagree with; the capacity gate that refuses before anything is installed; the per-pod readiness and per-replica correlation refusals that stop a multi-replica claim being made on a controller's summary count or on requests nobody recorded; the serving-tier refusals that stop the same claim being made about model servers on a counter snapshot that is missing a replica, a counter that fell across a restart, a replica that decoded nothing, or runtimes reporting less work than the driver was told about; the safety properties of the operating script, its request driver, and its per-pod counter forward; and the counter reader run against the runtime's own recorded exposition body rather than against an assumption about its shape. The claim that requests reach two replicas in a cluster belongs to the real-runtime layer, which runs the workflow instead of reading it |
| [`tests/architecture/test_helm_upgrade_rollback.py`](../../tests/architecture/test_helm_upgrade_rollback.py) | The Helm upgrade and rollback experiment read as committed data and text: the descriptor against the chart, the model source record, and the Kubernetes certification it may not disagree with; the refusals that stop a rollback being claimed on Helm's own bookkeeping, a deadline being read as a detection of health, a candidate that never scheduled being read as a detected fault, and a mock answering after the rollback; and the safety properties of the operating script. The claim that a release upgrades and rolls back safely belongs to the real-runtime layer, which runs the workflow instead of reading it -- and which cannot, because no InferOps API image exists |
| [`tests/architecture/test_kubernetes_pod_restart.py`](../../tests/architecture/test_kubernetes_pod_restart.py) | The Kubernetes pod-restart persistence experiment read as committed data and text: the descriptor against the real-inference certification it may not disagree with; the refusals that stop a pod coming back being read as a model surviving -- the same pod, the same UID, a different claim, a rebound volume, a writable remount, changed bytes, a re-acquired artifact carrying a new inode or modification time, an acquisition job that appeared, an integrity init container that never ran, a moved release revision, readiness that never dropped, and a mock answering afterwards; and the safety properties of the operating script, including that it issues exactly one delete and that the delete names one pod. The claim that the artifact survives a real pod replacement belongs to the real-runtime layer, which runs the workflow instead of reading it |
| [`tests/architecture/test_inference_pod_recovery.py`](../../tests/architecture/test_inference_pod_recovery.py) | The inference pod recovery experiment read as committed data and text: the descriptor against the load profile it pins; the refusals that stop one pod lost once being read as an availability figure, a benchmark, or a portable capacity claim; the two stamps an independent review of `V1-S3-003-PR2` corrected -- a recovery stamped from a forward accepting a connection and a replacement stamped from the Deployment's aggregate -- refused here by name; a record that is not usable when the selector matched two pods, the replacement carries the deleted pod's identity, the Service never lost an endpoint, the readiness samples leave a gap, a registered absence answered, or nothing came back served afterwards; and the safety properties of the operating script, including that it issues exactly one delete naming one pod and no mutating command at all between that delete and the uninstall. The claim that an inference pod is lost and recovered under real traffic belongs to a layer that runs the workflow instead of reading it |
| [`tests/architecture/test_unready_model_recovery.py`](../../tests/architecture/test_unready_model_recovery.py) | The unready model experiment read as committed data and text: the descriptor against the values overlay it pins, and that overlay read as text so that an overlay touching a model value is refused rather than merely re-hashed; the refusals that stop one release misconfigured once being read as an availability figure, a recovery-time objective, or a benchmark; the rule that both canonical codes `ADR 0010` D8 maps this situation to stay in the registered vocabulary, because which one a caller met is the result and not the arrangement; a record that is not usable when a readiness sample inside the window reported a ready pod, when the serving runtime container restarted, when the integrity init container did not exit zero, when a completion came back 200 with no output tokens, or when an intervention other than the one registered fix was recorded; and the safety properties of the operating script, including that it deletes nothing at all and that exactly two mutating commands follow the install. The claim that a real model is held unready on a real cluster and got back belongs to a layer that runs the workflow instead of reading it |
| [`tests/architecture/test_kubernetes_troubleshooting.py`](../../tests/architecture/test_kubernetes_troubleshooting.py) | The published Kubernetes troubleshooting and cleanup guide against the repository it describes: every command it prints against the module, subcommand, script, or path it names; every target against `lib.sh`; every port, probe, budget, deadline, resource figure, claim name and size, byte count, and in-claim path against the committed render, the values file, the Terraform variables, or the model source record; the exit vocabulary against both Kubernetes tools; every quoted measurement against the proof record it is attributed to; and the rules that keep its samples scoped, credential-free, and labelled where they are destructive. It establishes that the guide has not drifted, never that following one of its recoveries repairs a fault — no cluster has installed the release |
| [`tests/architecture/test_operator_runbook.py`](../../tests/architecture/test_operator_runbook.py) | The published V1 operator runbook against the repository it tells an operator to act on: every required incident answering the same six questions and stating the recovery its record gives it; every alert pointing at its own section, from the alert record, the alert document, and both rendered rule files; every command against the module, subcommand, or script it names, scoped to the target, and labelled for what it changes; every target, object name, port, and default against the file that owns it; and every quoted figure read back from its record. It establishes that the runbook has not drifted, never that following it repairs a fault. No procedure on it was run as a drill |
| [`tests/architecture/test_api_container_image.py`](../../tests/architecture/test_api_container_image.py) | The API container build path the chart depended on and did not have: the committed Dockerfile and its digest-pinned base, the unprivileged user and bytecode-free filesystem the chart's security context requires, the exec-form entrypoint that lets PID 1 receive SIGTERM, the copy list and ignore file that keep the host's model downloader and container packager out of a serving image, the carrier import that pulls none of them, the entrypoint's refusal of an unstated or impossible bind address, and the rule that no unverified digest replaces the labelled placeholder in the committed values. That the image runs belongs to a layer that starts one; this module builds nothing |
| [`tests/architecture/test_model_acquisition_job.py`](../../tests/architecture/test_model_acquisition_job.py) | The writing side of the model cache handoff, run rather than read: an empty claim populated and verified, a verified artifact reused with no transfer at all, an artifact of the right length and the wrong content replaced rather than reused, another revision's directory left alone, a failed acquisition leaving neither the artifact nor its temporary file behind, and a failed acquisition over an existing artifact leaving that artifact byte for byte as it found it. Whether the job schedules in a cluster belongs to a layer that installs one |
| [`tests/architecture/test_local_cluster_provider_contract.py`](../../tests/architecture/test_local_cluster_provider_contract.py) | The provider contract `ADR 0011` accepted: exactly two providers, no selection default, Terraform and Helm handed an address rather than a provider, an identity check, refusal, or rule claimed as enforced only where `lib.sh` or a test really defines it, every capability answer labelled with how it is known, each provider's cluster owned by its operator, and no platform workflow that creates or deletes a cluster. It also pins the open gaps. That a cluster is correctly identified or refused belongs to `test_target_verification.py`, which contacts a fake one, or to a layer that contacts a real one |
| [`tests/architecture/test_target_verification.py`](../../tests/architecture/test_target_verification.py) | The provider-aware target guard in `lib.sh`, executed against fake `kubectl`/`kind`/`docker` rather than read as text: every documented refusal a fake tool can exercise, for both `kind` and `docker-desktop`, one positive verified case per provider, the target facts a verified run reports, and the capability refusal `api-image.sh`/`model-seed-image.sh` depend on. It contacts no real cluster, so it says nothing about whether a real one is identified or a real wrong one refused |
| [`tests/architecture/test_inference_alert_rules.py`](../../tests/architecture/test_inference_alert_rules.py) | The alert definitions as the owned artifact the `ADR 0004` `D7` amendment of 2026-09-17 made them: a repository artifact that survives every teardown, a handoff saying `implemented` means a checked definition and not a firing alert, and `telemetry-backend` still holding the receiver and the routing tree. Its one executable check runs the pinned collector's own `promtool check rules` over both committed rule files, which establishes that they load and nothing about whether any alert would ever be true |
| [`tests/architecture/test_clean_clone_workflow.py`](../../tests/architecture/test_clean_clone_workflow.py) | The clean-clone orchestrator, run in a sandbox against recording stubs: the checklist's order, each workflow handed its own consent, a certification run refused before it writes anything, a preparation run recording what it was not authorized to run, resumption that re-verifies the cluster -- by provider, name, and `kube-system` UID, so a cluster reset under its name is refused -- and a cleanup that removes only what the run created and proves the cluster survived. The claim that a reviewer can reproduce V1 from a clean clone is planned in the claim and evidence register and needs a real run; every answer here comes from a stub |
| [`tests/architecture/test_clean_clone_ledger.py`](../../tests/architecture/test_clean_clone_ledger.py) | The rules of the clean-clone ledger: when a step may be recorded as not run, the order steps may pass in, intervals, resumption, manual actions without host paths, and which complete run certifies anything. It establishes what a record may say, never that a run said it |
| [`tests/architecture/test_telemetry_collector.py`](../../tests/architecture/test_telemetry_collector.py) | The collector `ADR 0004` `D7` was amended to allow: owned but still `planned`, off by default, reading the scrape ConfigMap rather than a second copy of it, projecting an expiring token instead of automounting one, and storing series in a bounded `emptyDir`. Its one executable check runs the pinned collector's own `promtool` over the committed render, which establishes that the configuration loads and nothing about whether anything was collected |

The two API-surface rows are the interesting pair. The matrix's drift claim,
`the-published-strategy-and-its-data-cannot-drift-apart`, is written about the
test strategy's own lane, layer, and claim identifiers. These two suites protect
the same *kind* of property for a different record, and the matrix has no row for
it — which is a gap in the matrix rather than in the suites, and it is recorded
here rather than closed by widening a claim's wording.

## Coverage gaps

Seven claims are not defended by any module here. Each is recorded with a reason
and, where something outside pytest defends it, what that is.

| Claim | Why no module | Defended by |
|---|---|---|
| `the-model-artifact-matches-its-published-hash` | No pytest module computes or compares the hash. The real-runtime suite drives a running runtime, and the runtime exposes no hash of the file it loaded | The download step of [the feasibility workflow](../serving/feasibility-workflow.md), with both hashes recorded in [its evidence record](../proof/serving/v1-s0-003-pr2-runtime-feasibility.md) |
| `a-local-cluster-is-created-and-removed-without-residue` | The `kubernetes-smoke` layer declares no test paths | [`scripts/environment/`](../../scripts/environment/), run by hand, with the record under [`docs/proof/environment/`](../proof/environment/) |
| `no-credential-or-model-artifact-enters-public-history` | The `security-scan` layer is planned. A configuration and an allowlist are committed and no recorded run of a scanner exists | Nothing yet |
| `a-helm-release-installs-and-uninstalls-without-residue` | The layer the claim names declares no test paths; no pytest module installs or uninstalls anything | [`scripts/environment/helm-lifecycle.sh`](../../scripts/environment/helm-lifecycle.sh) and the certification workflows, run by hand on `docker-desktop` with a locally built and loaded API image, with the executed results in [the paved road](../proof/environment/v1-s3-011-pr1-docker-desktop-paved-road.md) and [the scoped cleanup record](../proof/environment/v1-s3-011-pr2-scoped-cleanup.md) |
| `a-controlled-release-change-can-be-reversed-and-real-inference-restored` | No pytest module upgrades a release, breaks it, or rolls it back. [`test_helm_upgrade_rollback.py`](../../tests/architecture/test_helm_upgrade_rollback.py) reads the descriptor, the script, and documents a run would have written, and contacts no cluster — so it can refuse a bad record and cannot produce a good one | [`scripts/environment/helm-upgrade-rollback.sh`](../../scripts/environment/helm-upgrade-rollback.sh), run by hand, with the executed result in [its record](../proof/environment/v1-s3-011-pr2-upgrade-rollback.md) |
| `the-model-artifact-survives-a-pod-replacement-on-a-terraform-owned-claim` | No pytest module deletes a pod or reads a mounted claim. [`test_kubernetes_pod_restart.py`](../../tests/architecture/test_kubernetes_pod_restart.py) reads committed files only | [`scripts/environment/kubernetes-pod-restart.sh`](../../scripts/environment/kubernetes-pod-restart.sh), run by hand, with the executed result in [its record](../proof/serving/v1-s3-003-pr2-kubernetes-pod-restart.md) |
| `sustained-throughput-and-capacity-under-load` | Deferred out of V1. A module here would produce output nothing may publish | Nothing, deliberately |

The first row is the one worth reading twice. The claim is **certified**, and its
evidence is a manual download rather than a suite — legitimate, and exactly the kind
of thing an inventory of pytest modules would otherwise imply was missing.

One row left this table in this change. `published-documents-link-only-to-things-that-exist`
was certified while the only thing that checked it was a shell command in
[CONTRIBUTING](../../CONTRIBUTING.md) that somebody had to remember to run, and four
links in this repository had been broken long enough for that to matter.
[`test_document_links.py`](../../tests/testing/test_document_links.py) now walks every
committed Markdown file, so the claim is defended by a module rather than by a habit.

## What this inventory does not do

- **It certifies nothing.** A module listed against a claim contributes to it; it
  does not raise what the layer's evidence class permits. Two of the modules here
  have never been executed at all.
- **It does not judge a suite.** A module with a confident sentence beside it may
  still be shallow. Nothing here reads an assertion.
- **It is not a coverage percentage.** No line or branch coverage is measured,
  reported, or required anywhere in this repository, and this file does not
  introduce one.
- **It does not configure continuous integration.** The lane table above is a
  grouping and a set of commands. One workflow file exists, committed by
  [ADR 0012](../architecture/decisions/ADR-0012-continuous-integration-service.md)
  and running the `default-checks` lane; this inventory does not define it, and the
  strategy suite still refuses to let any lane claim automation by naming a workflow
  that does not exist. (This bullet said "there is no workflow file" until
  2026-09-21.)
