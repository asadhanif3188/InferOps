# The V1 proof dashboard

Status: **generated page**. It is produced by
`python -m tools.proof_dashboard` from
[the claim and evidence register](../testing/claim-evidence-matrix.v1alpha2.json),
and [`tests/testing/test_proof_dashboard.py`](../../tests/testing/test_proof_dashboard.py)
regenerates it and fails if the committed page and the register disagree.
**Do not edit it by hand.** An edit here would be the only place in this
repository where a capability status was asserted instead of derived, and it
would survive exactly until the next check.

This page answers one question: **what has this project actually proven?**
It is not a monitoring view. What is happening inside a running release is
[the inference operations dashboard](../telemetry/inference-operations-dashboard.md),
which is asked of a Prometheus and shows nothing when nothing is running. This
page reads committed files, says the same thing on every machine, and does not
change when a cluster does.

**Certified: 41 of 59 claims.** The remaining 18 are the rows worth
reading, and they are listed in full under [what V1 does not
claim](#what-v1-does-not-claim) rather than summarised away. Every number on
this page is counted from the register at render time; there is no field
anywhere in this tool that a count could be typed into.

> [!IMPORTANT]
> **A claim's status and an evidence level are different things.** The status
> says whether this project publishes a property at all. A level belongs to
> one evidence record — 64 of them sit behind these claims — and
> says only how that record was obtained. The levels `C0` to `C4` are
> [InferOps Evidence Levels](../testing/evidence-levels.md): **project-defined,
> and not an ISO, NIST, regulatory, or industry certification standard.** Nobody
> outside this repository has reviewed a claim or a record on this page.

## Five minutes, in order

1. **Read the overview.** [The capabilities at a
   glance](#the-capabilities-at-a-glance) is one row per capability: how many
   of its claims are certified, planned, deferred, or not claimed, the
   highest level any record behind a certified claim reached, and the
   provider the real results came from.
2. **Open the capability you came for.** Each row of the overview links to
   its section under [the capabilities](#the-capabilities), where every claim
   is shown with its status, every evidence record behind it — each with its
   own level, where it ran, what it substituted, and its files — and the
   limitation that travels with the claim.
3. **Follow a record.** Every certified row links the committed records under
   `docs/proof/` that support it. A record carries the commands, the
   versions, the host, and what it does not establish; the row is a summary
   of it and never more than it.
4. **Read what is absent.** [What V1 does not claim](#what-v1-does-not-claim)
   lists every claim that is not certified, derived from the register.
5. **Read the boundary.** [Where V1 stands](#where-v1-stands) says what each
   status and each level may and may not be read as, and
   [what this page is not](#what-this-page-is-not) says what the page itself
   cannot tell you.

## The capabilities at a glance

14 capability groups, each linking to its own section below.
Every count is the group's own rows. *Highest level reached* is the
highest-numbered level any record behind a certified row reached — the one
nearest the intended operating context, which is not the same as the best
evidence for any one claim — and a group with no certified row shows none. A
provider is named only where a record names one, and a result on one
provider certifies that provider alone.

| Capability | Certified | Planned | Deferred | Not claimed | Highest level reached | Provider named |
|---|---|---|---|---|---|---|
| [Real serving](#real-serving) | 5 | 2 | 0 | 0 | `C2` | `docker-desktop` |
| [Kubernetes deployment](#kubernetes-deployment) | 4 | 0 | 0 | 1 | `C2` | `docker-desktop`, `kind` |
| [Clean-clone reproduction](#clean-clone-reproduction) | 1 | 0 | 0 | 0 | `C2` | `docker-desktop` |
| [Model integrity](#model-integrity) | 4 | 0 | 0 | 0 | `C2` | `docker-desktop` |
| [Pod recovery](#pod-recovery) | 2 | 0 | 0 | 0 | `C2` | `docker-desktop` |
| [Rollback and release recovery](#rollback-and-release-recovery) | 1 | 0 | 0 | 0 | `C2` | `docker-desktop` |
| [Telemetry, dashboard, and alerts](#telemetry-dashboard-and-alerts) | 6 | 1 | 0 | 1 | `C2` | `docker-desktop` |
| [Performance evidence](#performance-evidence) | 3 | 0 | 1 | 0 | `C2` | `docker-desktop` |
| [Cost method](#cost-method) | 2 | 0 | 0 | 1 | `C0` | none named |
| [Security boundary](#security-boundary) | 3 | 1 | 0 | 2 | `C0` | `docker-desktop` |
| [Multi-replica serving](#multi-replica-serving) | 0 | 0 | 0 | 1 | — | `docker-desktop` |
| [Contracts, scaffolding, and the safe quick start](#contracts-scaffolding-and-the-safe-quick-start) | 5 | 3 | 0 | 0 | `C2` | none named |
| [Release and production use](#release-and-production-use) | 0 | 0 | 0 | 2 | — | none named |
| [Ownership, tests, continuous integration, and evidence](#ownership-tests-continuous-integration-and-evidence) | 5 | 0 | 0 | 2 | `C0` | none named |

## Where V1 stands

Four states, and the difference between the last three is the difference
between a promise, a decision, and a measured absence.

| Status | Claims | May be published as a capability | What it means |
|---|---|---|---|
| `certified` | 41 | yes | An executed record under docs/proof/ supports the statement at the level named, inside the boundary its limitation states. |
| `planned` | 7 | no | V1 intends it and nothing has proven it. It may be published only as an intention, and it may cite no evidence record. |
| `deferred` | 1 | no | Out of V1 scope by an accepted decision. It may not be published as a capability at all, and it may cite no evidence record. |
| `not-claimed` | 10 | no | A reader would reasonably expect it and V1 states that it does not have it. It may cite the record that measured the absence, because an absence somebody measured is worth more than one nobody mentions. |

### The levels the evidence records reached

A level belongs to one evidence record and says how it was obtained:
statically, with a component material to the claim substituted, or with
the real components running. The definitions are in
[the evidence-level specification](../testing/evidence-levels.md). A claim
may hold several records at several levels, so the two columns count
different things: records, and the certified claims holding at least one
record at that level.

| Evidence level | Records | Certified claims holding one | Defined as |
|---|---|---|---|
| `C0` | 26 | 22 | [Static Evidence](../testing/evidence-levels.md#c0--static-evidence) |
| `C1` | 8 | 5 | [Substituted Execution Evidence](../testing/evidence-levels.md#c1--substituted-execution-evidence) |
| `C2` | 30 | 20 | [Runtime Evidence](../testing/evidence-levels.md#c2--runtime-evidence) |
| `C3` | 0 | 0 | [Representative Evidence](../testing/evidence-levels.md#c3--representative-evidence) |
| `C4` | 0 | 0 | [Operational Evidence](../testing/evidence-levels.md#c4--operational-evidence) |

Every record carries a level: none was left `legacy-unmigrated`.

**`C0` to `C4` is not a maturity score.** The numbering tracks closeness to
the intended operating context, and a record with a higher number is not
better evidence for every claim: a static check is the right evidence for
a claim about a schema, and no runtime record would be. Nothing in this
repository is `C3` or `C4`; `C4` needs organizational production, and
there is none.

### Where the records ran

Two records at the same level in different environments are not
interchangeable, so the environment is counted per record.

| Environment | Provider | Hardware | Records |
|---|---|---|---|
| `local-container` | `not-applicable` | `cpu` | 4 |
| `local-kubernetes` | `docker-desktop` | `cpu` | 22 |
| `local-kubernetes` | `kind` | `cpu` | 1 |
| `local-kubernetes` | `unrecorded` | `cpu` | 3 |
| `local-process` | `not-applicable` | `cpu` | 10 |
| `repository-only` | `not-applicable` | `not-applicable` | 24 |

### Which provider the real results came from

Only the records that name a provider are counted here. The rest named
none because no provider produced them, and folding those in would make
the reference provider look like a minority of the evidence rather than
all of it.

| Provider | Records naming it | Claims holding one |
|---|---|---|
| `docker-desktop` | 22 | 16 |
| `kind` | 1 | 1 |

3 records ran on a Kubernetes cluster whose source
record never names the provider. They say `unrecorded` rather than
borrowing a provider from a neighbouring record, and they are counted
under no provider here.

A result on one provider certifies that provider. It does not certify
another provider, a cloud cluster, a GPU, another host, another model,
another runtime, or production, and no row on this page may be read as
though it did. The providers themselves are published in
[the local cluster provider contract](../environment/local-cluster-provider-contract.md).

### What the migration changed

Until `V1-S5-012-PR2` the register stored one level per claim, under
meanings ADR 0016 supersedes. Every claim still carries that value as
history, and the levels on its records are the result of reading each
record against the current definitions. 43 claims carried a level;
10 claims now hold records at a level other than the one they
carried, or hold a level where they carried none. They are listed here, and
[the migration report](testing/v1-s5-012-pr2-migration-report.md) says why each one moved.

This table cannot show a status that moved, because a claim carries its
superseded level and not its superseded status. The migration report lists
every status the migration changed, with the measurement that required it.

| Claim | Status | Carried before (superseded meanings) | Levels its records hold |
|---|---|---|---|
| A contract document is parsed into typed domain objects with explicit contract-version handling, and seven semantic validation rules are applied to what parsing produced. | `certified` | `C0` | `C2` |
| The scaffolding command renders a workload project for the mock and synchronous profiles and refuses to overwrite a file that already exists. | `certified` | `C0` | `C2` |
| The published developer quick start was followed on a clean checkout and its mock workflow completed, and the authorization-gated real-runtime smoke it points at has been executed and recorded separately. | `certified` | `C1` | `C1`, `C2` |
| The published model lifecycle ordering — liveness holding while the model loads, readiness false until it is ready, the artifact surviving a restart, and a cache hit in both arms — held in all three cold and warm comparisons measured. | `certified` | `C2` | `C0`, `C2` |
| InferOps requires an explicitly selected, already existing local cluster, positively verifies the target before it mutates anything, and creates, resets, reconfigures, or deletes no cluster. | `certified` | `C2` | `C0`, `C2` |
| A Helm release installed into the operator's Kubernetes cluster loads the pinned model from a Terraform-owned claim and serves a real completion through the release's own Service. | `certified` | `C2` | `C1`, `C2` |
| Two real serving replicas are certified to serve real inference in a cluster. | `not-claimed` | none | `C0` |
| A versioned load profile with a warm-up, rising concurrency levels, duration and request bounds, a client deadline above the API's, and a fixed response classification generates repeatable load and a raw record set whose accounting is checked on read. | `certified` | `C2` | `C1`, `C2` |
| A real Prometheus parsed and evaluated all 30 panel expressions in nine states and refused none, and a real Grafana imported the generated JSON and rendered all 29 panels. | `certified` | `C2` | `C0`, `C2` |
| The NetworkPolicy objects the chart renders restrict traffic in the clusters this project runs on. | `not-claimed` | none | `C1` |

## The capabilities

Each group is a question a reviewer asks, and the rows under it are the
register's answer with what a summary usually loses kept beside each one:
every evidence record the claim holds, with its level, the environment and
provider it ran on, the workload's origin where one was issued, anything it
substituted, and its files; and the limitation that travels with the claim.
A group's tally is counted from its own rows, and a group is never given a
single colour, because a group holding one certified row and one measured
absence is not one status.

### Real serving

*Has a real model ever answered a request through this API?*

**Tally:** 5 `certified`, 2 `planned`.

| Claim | Status | Evidence records | Limitation |
|---|---|---|---|
| The pinned runtime loads the hash-verified model and the InferOps API returns a real completion from it, on a contributor's own machine, certified at `C2` by one authorized run. | `certified` | `C2` · `local-container`, `cpu` · workload `operator-issued` · [`serving/v1-s2-004-c2-certification-result.md`](serving/v1-s2-004-c2-certification-result.md)<br>`C2` · `local-kubernetes`, provider not named by its record, `cpu` · workload `operator-issued` · [`serving/v1-s1-real-runtime-closure.md`](serving/v1-s1-real-runtime-closure.md) | The certification run: one host, one run, one day on 2026-09-04, CPU only, loopback composition rather than Kubernetes, one fixed request. Runtime readiness was 285,828 ms against a pinned 300,000 ms budget — under five per cent of headroom — and the record says the budget is not comfortable. The request and correlation identifiers were not echoed back. The second record cited is the 2026-09-02 Sprint 1 closure run, in which the API ran in the test process against the runtime in a local cluster whose provider that record does not name. |
| A Helm release installed into the operator's Kubernetes cluster loads the pinned model from a Terraform-owned claim and serves a real completion through the release's own Service. | `certified` | `C2` · `local-kubernetes` on `docker-desktop`, `cpu` · workload `operator-issued` · [`environment/v1-s3-011-pr1-docker-desktop-paved-road.md`](environment/v1-s3-011-pr1-docker-desktop-paved-road.md)<br>`C1` · `local-kubernetes` on `docker-desktop`, `cpu` · workload `operator-issued` · substituted `inferops-llm-chart` (fixture, claim-material), `terraform-prerequisites` (fixture, claim-material) · [`serving/v1-s0-003-pr2-runtime-feasibility.md`](serving/v1-s0-003-pr2-runtime-feasibility.md) | One provider, `docker-desktop`; one Windows host; one Docker Desktop installation; CPU; one replica of each tier; one moment on 2026-09-12. Docker Desktop chooses its own Kubernetes version and node image and InferOps pins neither. Three inference requests were sent and their timings were deliberately not recorded. The second record cited is the 2026-08-24 feasibility trial, which served a completion from the same runtime and model through hand-written trial manifests rather than the chart and a Terraform-owned claim, and so is substituted evidence for this statement. |
| The InferOps inference API implements five ASGI routes and selects the mock or the real serving adapter explicitly, never by falling back. | `certified` | `C1` · `local-process`, `cpu` · workload `operator-issued` · substituted `llama-cpp-server` (stub, claim-material), `qwen3-1-7b-q8-0` (mock) · [`serving/v1-s1-005-pr1-validation.md`](serving/v1-s1-005-pr1-validation.md), [`serving/v1-s1-005-pr2-validation.md`](serving/v1-s1-005-pr2-validation.md)<br>`C1` · `local-process`, `cpu` · workload `operator-issued` · substituted `llama-cpp-server` (stub, claim-material), `qwen3-1-7b-q8-0` (mock) · [`testing/v1-s5-006-pr2-pinned-suite-run.md`](testing/v1-s5-006-pr2-pinned-suite-run.md) | The published surface is five endpoints served in part. The distribution carries no server dependency; the repository's loopback-only HTTP carrier is tooling rather than a product. |
| A mock, a simulation, or an estimate certifies at most `C1` however faithful it is, and the ceiling is enforced in the strategy data rather than asked for in review. | `certified` | `C0` · `repository-only` · [`testing/v1-s0-006-pr1-validation.md`](testing/v1-s0-006-pr1-validation.md) | The ceiling is enforced over the committed strategy data. It stops a layer certifying above its class; it cannot tell an honestly planned layer from one nobody will write. |
| The local runtime troubleshooting guide's symptoms, commands, and quoted figures are checked against the repository and the evidence records they come from, and every read-only diagnostic in it except the Linux branch of the processor-feature probe was executed on one Windows host. | `certified` | `C0` · `repository-only` · [`serving/v1-s2-008-pr1-validation.md`](serving/v1-s2-008-pr1-validation.md) | The authorization-gated recoveries are described rather than run, and the check establishes that a command and a figure match the repository rather than that following the guide fixes anything. The record's criteria table says every diagnostic exited `0`; its own diagnostics table shows `local_composition status --confirm-real-runtime` exiting `5`, the documented composed-but-not-ready code, and a correction beside the record says so. |
| A model that is not ready produces a canonical error rather than an unhandled failure or a fabricated answer. | `planned` | none, and a `planned` claim may hold none | The unready-model experiment measured the real condition and found that no caller ever received `model-not-ready`: all eight completions came back `capability-unavailable` with condition `runtime-unreachable`. That is a measured fact about the deployed shape, and it is a reason this claim stays planned rather than a reason to promote it. |
| A runtime that cannot be reached produces a canonical error rather than an unhandled failure. | `planned` | none, and a `planned` claim may hold none | The mock layers show the API maps the condition to the right error. They cannot show the condition occurs, or that the runtime produces it in the way the mock's author imagined. |

### Kubernetes deployment

*Does a release install, serve, and leave without residue?*

**Tally:** 4 `certified`, 1 `not-claimed`.

| Claim | Status | Evidence records | Limitation |
|---|---|---|---|
| InferOps requires an explicitly selected, already existing local cluster, positively verifies the target before it mutates anything, and creates, resets, reconfigures, or deletes no cluster. | `certified` | `C2` · `local-kubernetes` on `docker-desktop`, `cpu` · workload `operator-issued` · [`environment/v1-s3-011-pr1-docker-desktop-paved-road.md`](environment/v1-s3-011-pr1-docker-desktop-paved-road.md)<br>`C0` · `repository-only` · [`architecture/v1-s3-010-pr1-validation.md`](architecture/v1-s3-010-pr1-validation.md) | `docker-desktop` is the executed V1 reference provider, verified by binding the node container's published API-server port to the port the verified kubeconfig dials. `kind` is supported by a guard and is certified by none of this evidence. Two things the Docker Desktop identity check cannot refuse are accepted as `EX-06`. |
| `helm uninstall` removes every object the release owns and leaves the operator's cluster, its node, its storage class, and the Terraform-owned prerequisites intact. | `certified` | `C2` · `local-kubernetes` on `docker-desktop`, `cpu` · workload `operator-issued` · [`environment/v1-s3-011-pr2-scoped-cleanup.md`](environment/v1-s3-011-pr2-scoped-cleanup.md)<br>`C2` · `local-kubernetes` on `docker-desktop`, `cpu` · workload `operator-issued` · [`environment/v1-s3-011-pr1-docker-desktop-paved-road.md`](environment/v1-s3-011-pr1-docker-desktop-paved-road.md)<br>`C2` · `local-kubernetes` on `docker-desktop`, `cpu` · workload `operator-issued` · [`environment/v1-s5-013-pr1-scoped-cleanup.md`](environment/v1-s5-013-pr1-scoped-cleanup.md), [`environment/v1-s5-013-pr1-scoped-cleanup-transcript.txt`](environment/v1-s5-013-pr1-scoped-cleanup-transcript.txt), [`environment/v1-s5-013-pr1-cluster-prepare-transcript.txt`](environment/v1-s5-013-pr1-cluster-prepare-transcript.txt) | One provider, one host, two teardowns, on 2026-09-12 and 2026-09-26. Survival was checked immediately afterwards and nothing is known about days later. `terraform destroy` reclaims the model weights, so the next real run re-acquires them. This claim is a recorded coverage gap in the test inventory: no pytest module proves it, the modules named here are adjacent to it, and what proves it is the executed records. The statement names only the uninstall; the install the identifier names is in the second record cited, the paved-road run, which installed a release, passed its release test, and removed it with no release-labelled object left behind. Release blocker b3-helm-uninstall-survival-clause-code-unidentified closed by V1-S5-013-PR1 with a rerun from a fresh clone at bcad343133ba6fddfe38832a2694e71777cdd006, whose status was empty before the first step and after the last: the lifecycle workflow's uninstall left no release-labelled object and the Terraform-owned namespace and claim intact, and the cluster, its node, and its storage classes were unchanged after the uninstall and again after terraform destroy; the 2026-09-12 scoped-cleanup record stays cited for what it observed. |
| The optional `kind` helper creates a local development cluster, runs a workload inside it, and removes it leaving no residue the verifier can find. | `not-claimed` | `C2` · `local-kubernetes` on `kind`, `cpu` · workload `operator-issued` · [`environment/v1-s0-002-pr2-cluster-smoke.md`](environment/v1-s0-002-pr2-cluster-smoke.md) | One Windows host on WSL 2, one architecture, one point in time on 2026-08-23, on cgroup v1, with a static-text HTTP server as the workload. Since ADR 0011 this helper is optional and InferOps no longer creates a cluster for its own workflows. About 0.1 GB of host free space was not returned, and the node image is retained by design. This claim is a recorded coverage gap in the test inventory: no pytest module proves it, the modules named here are adjacent to it, and what proves it is the executed record. Release blocker b2-kind-helper-code-unidentified closed by V1-S5-013-PR1 by a claim decision rather than a run, moving the claim from certified to not-claimed: the record describes what the helper did once, on code nothing identifies, and kind was not run again. |
| A symptom-oriented Kubernetes troubleshooting guide covering cluster, scheduling, memory, storage, model load, probe, Service, telemetry, Helm, and Terraform faults, with four separated cleanup radii, is published and machine-checked against the repository. | `certified` | `C0` · `repository-only` · [`environment/v1-s3-009-pr1-validation.md`](environment/v1-s3-009-pr1-validation.md), [`environment/v1-s3-011-pr1-docker-desktop-paved-road.md`](environment/v1-s3-011-pr1-docker-desktop-paved-road.md), [`environment/v1-s3-011-pr2-scoped-cleanup.md`](environment/v1-s3-011-pr2-scoped-cleanup.md) | Every command is checked against the repository, which is a property of strings rather than of a cluster. The record that machine-checks the guide contacted no cluster, and states that when it was written the release half had never been run by anybody; `V1-S3-011` ran that half afterwards, on one Windows host, on `docker-desktop`, and those two records are cited beside it. The identifier says executed and the statement, which is what is certified, says machine-checked: of the four cleanup radii, `helm uninstall` and the guarded `terraform destroy` were executed in the cited records, and the host model-cache clean and `cluster-down.sh` were not executed in any record this claim cites. The identifier is kept because it is the claim's identity on every surface that cites it. |
| A V1 operator runbook gives pod loss, an unready model, latency and errors, resource pressure and out-of-memory, a telemetry gap, a bad release, model and cache faults, and a cost anomaly each a procedure answering detection, user impact, automatic recovery, human action, validation, and escalation; states for each whether anything recovers it without a person; routes every one of the six alerts to its own section; and is machine-checked against the repository. | `certified` | `C0` · `repository-only` · [`environment/v1-s5-005-pr1-validation.md`](environment/v1-s5-005-pr1-validation.md) | Every check reads files. The offline commands on the page were executed; no command that contacts a cluster was, and no procedure was followed as a drill. Three procedures rest on executed local-real experiments on docker-desktop, one Windows host and one replica; the other five are described and were never provoked. |

### Clean-clone reproduction

*Can a reviewer walk the whole V1 journey from a fresh clone?*

**Tally:** 1 `certified`.

| Claim | Status | Evidence records | Limitation |
|---|---|---|---|
| A reviewer starting from a clean clone reaches mock tests, model acquisition, local real inference, a Kubernetes deployment, telemetry, load, a failure experiment, and a scoped cleanup, with every manual step and the elapsed time recorded. | `certified` | `C2` · `local-kubernetes` on `docker-desktop`, `cpu` · workload `synthetic` · [`environment/v1-s5-001-pr2-clean-clone-run.md`](environment/v1-s5-001-pr2-clean-clone-run.md), [`environment/v1-s5-001-pr2-attempt-1-ledger.v1alpha1.json`](environment/v1-s5-001-pr2-attempt-1-ledger.v1alpha1.json), [`environment/v1-s5-001-pr2-attempt-2-ledger.v1alpha1.json`](environment/v1-s5-001-pr2-attempt-2-ledger.v1alpha1.json), [`environment/v1-s5-001-pr2-attempt-3-ledger.v1alpha1.json`](environment/v1-s5-001-pr2-attempt-3-ledger.v1alpha1.json), [`environment/v1-s5-001-pr2-attempt-2-c2-smoke.json`](environment/v1-s5-001-pr2-attempt-2-c2-smoke.json), [`environment/v1-s5-001-pr2-c2-smoke.json`](environment/v1-s5-001-pr2-c2-smoke.json), [`environment/v1-s5-001-pr2-k8s-real-inference.json`](environment/v1-s5-001-pr2-k8s-real-inference.json), [`environment/v1-s5-001-pr2-telemetry-verification.json`](environment/v1-s5-001-pr2-telemetry-verification.json), [`environment/v1-s5-001-pr2-performance-record.v1alpha1.json`](environment/v1-s5-001-pr2-performance-record.v1alpha1.json), [`environment/v1-s5-001-pr2-recovery-record.v1alpha1.json`](environment/v1-s5-001-pr2-recovery-record.v1alpha1.json) | One complete run, on docker-desktop, on one Windows host, made by the author of the change that ran it -- after two attempts, at two earlier revisions, that stopped on defects this change fixed. One execution is not a distribution and does not establish that the journey completes reliably or on another host. No second engineer has repeated it; the story asks for that confirmation where available, and it is not available here. |

### Model integrity

*Is the artifact that gets loaded the artifact that was published?*

**Tally:** 4 `certified`.

| Claim | Status | Evidence records | Limitation |
|---|---|---|---|
| The model artifact this project uses is acquired revision-pinned and resumable, and its bytes are compared against the published SHA-256 before anything loads it. | `certified` | `C2` · `local-kubernetes` on `docker-desktop`, `cpu` · [`serving/v1-s0-003-pr2-runtime-feasibility.md`](serving/v1-s0-003-pr2-runtime-feasibility.md)<br>`C2` · `local-kubernetes`, provider not named by its record, `cpu` · [`serving/v1-s1-real-runtime-closure.md`](serving/v1-s1-real-runtime-closure.md) | The downloader does not validate TLS certificates, so the published hash is the whole integrity argument for the transfer rather than a redundant check on it. Resumption after interruption is proved synthetically by the suite and was also exercised for real: the first acquisition was interrupted at 353,249,411 bytes and resumed, and the second took 866 seconds over three bounded resume attempts on one host. Both comparisons ran inside a cluster, in the acquisition Job, before the file was mounted; the first record describes Docker Desktop's cluster and the second names no provider. This claim is a recorded coverage gap in the test inventory: no pytest module proves it, the modules named here are adjacent to it, and what proves it is the executed record. |
| A deleted serving pod is replaced against the surviving Terraform-owned claim, with the artifact's byte count, SHA-256, inode, and mtime unchanged and no re-acquisition Job created. | `certified` | `C2` · `local-kubernetes` on `docker-desktop`, `cpu` · workload `operator-issued` · [`serving/v1-s3-003-pr2-kubernetes-pod-restart.md`](serving/v1-s3-003-pr2-kubernetes-pod-restart.md)<br>`C2` · `local-kubernetes` on `docker-desktop`, `cpu` · workload `operator-issued` · [`serving/v1-s5-013-pr1-kubernetes-pod-restart.md`](serving/v1-s5-013-pr1-kubernetes-pod-restart.md), [`serving/v1-s5-013-pr1-kubernetes-pod-restart.v1alpha1.json`](serving/v1-s5-013-pr1-kubernetes-pod-restart.v1alpha1.json), [`serving/v1-s5-013-pr1-kubernetes-pod-restart-transcript.txt`](serving/v1-s5-013-pr1-kubernetes-pod-restart-transcript.txt), [`environment/v1-s5-013-pr1-cluster-prepare-transcript.txt`](environment/v1-s5-013-pr1-cluster-prepare-transcript.txt) | One provider, one host, one replica, and one pod deleted once in each of two runs, on 2026-09-12 and 2026-09-26. The 2026-09-12 run found four defects: two by running it, and two more by an independent review of the change afterwards, both of the second pair defects in a published figure rather than in a run that failed, which is why running it did not find them. This claim is a recorded coverage gap in the test inventory: no pytest module proves it, the modules named here are adjacent to it, and what proves it is the executed records. Release blocker b5-pod-replacement-code-unidentified closed by V1-S5-013-PR1 with a rerun from a fresh clone at bcad343133ba6fddfe38832a2694e71777cdd006, whose status was empty before the first step and after the last, in which the byte count, SHA-256, inode, and modification time were unchanged across a replacement pod with a different UID and no acquisition Job ran; the 2026-09-12 record stays cited for what it observed. |
| One serving runtime and one model revision were selected by a published feasibility procedure executed once against twelve pre-registered thresholds, eleven met and one recorded as failed. | `certified` | `C2` · `local-kubernetes` on `docker-desktop`, `cpu` · workload `operator-issued` · [`serving/v1-s0-003-pr2-runtime-feasibility.md`](serving/v1-s0-003-pr2-runtime-feasibility.md) | One host, one architecture, one point in time on 2026-08-24, single-request throughout. `T7` — a cumulative request counter — is a blocking threshold recorded as not met as written, and ADR 0002 accepted the pair with that exception. The runtime was started in the container desktop distribution's own single-node cluster and answered through cluster DNS and a Service, so this is a Kubernetes result; the record predates ADR 0011 and names that cluster descriptively rather than by provider identifier, and the provider here is read from its description rather than from a field the record carries. |
| The published model lifecycle ordering — liveness holding while the model loads, readiness false until it is ready, the artifact surviving a restart, and a cache hit in both arms — held in all three cold and warm comparisons measured. | `certified` | `C2` · `local-container`, `cpu` · workload `operator-issued` · [`serving/v1-s2-007-pr1-cold-warm-start.md`](serving/v1-s2-007-pr1-cold-warm-start.md)<br>`C0` · `local-process`, `cpu` · [`serving/v1-s2-007-cache-miss-observation.md`](serving/v1-s2-007-cache-miss-observation.md) | Six starts on one host on 2026-09-03, CPU only. The cold arm was not cold — Windows offers no supported page-cache drop — and the host was memory-constrained throughout, with 904 to 1,725 MiB free of 16,057 MiB. The cache-miss observation cited beside it is from 2026-09-04 and establishes the miss classification and the refusal it triggers; it says nothing about the six starts or either arm. |

### Pod recovery

*What does a caller see when the serving pod goes away?*

**Tally:** 2 `certified`.

| Claim | Status | Evidence records | Limitation |
|---|---|---|---|
| One serving pod deleted by name mid-load produced a 31,960 ms caller-visible outage in which 40 of 41 dispatched requests were refused with `capability-unavailable`, the replacement reported itself Ready 33,665 ms after the delete, and the workflow issued no mutating command between the delete and its closing uninstall. | `certified` | `C2` · `local-kubernetes` on `docker-desktop`, `cpu` · workload `synthetic` · [`serving/v1-s4-006-pr1-inference-pod-recovery.md`](serving/v1-s4-006-pr1-inference-pod-recovery.md), [`serving/v1-s4-006-pr1-environment.v1alpha1.json`](serving/v1-s4-006-pr1-environment.v1alpha1.json) | One provider, one host, one single-replica release, one load profile, one pod lost once on 2026-09-16, as a bounded observation under ADR 0013. One replica is the cause of the outage. The forward is in every latency, and the readiness sampler takes 1.7 to 5.4 seconds to answer. |
| A release starved of processor time started, bound its port, began loading the model and did not finish for 179,755 ms; four request surfaces were asked and readiness sampled from four places throughout; and dropping the overlay and upgrading returned it to a served completion. | `certified` | `C2` · `local-kubernetes` on `docker-desktop`, `cpu` · workload `operator-issued` · [`serving/v1-s4-007-pr1-unready-model-recovery.md`](serving/v1-s4-007-pr1-unready-model-recovery.md), [`serving/v1-s4-007-pr1-environment.v1alpha1.json`](serving/v1-s4-007-pr1-environment.v1alpha1.json) | One provider, one host, one single-replica release, one misconfiguration applied once on 2026-09-16, as a bounded observation under ADR 0013. The model did not become ready inside the registered observation window, which is not the same as proving it never would: the load was starved rather than failed. The recovery is an operator changing a value and issuing an upgrade. |

### Rollback and release recovery

*Can a bad release be taken back, with real inference restored?*

**Tally:** 1 `certified`.

| Claim | Status | Evidence records | Limitation |
|---|---|---|---|
| A deliberately broken release revision was detected by an init container's non-zero exit 6,949 ms after the fault, rolled back in 1,986 ms, and served a real completion 11,053 ms after detection. | `certified` | `C2` · `local-kubernetes` on `docker-desktop`, `cpu` · workload `operator-issued` · [`environment/v1-s3-011-pr2-upgrade-rollback.md`](environment/v1-s3-011-pr2-upgrade-rollback.md)<br>`C2` · `local-kubernetes` on `docker-desktop`, `cpu` · workload `operator-issued` · [`environment/v1-s5-013-pr1-upgrade-rollback.md`](environment/v1-s5-013-pr1-upgrade-rollback.md), [`environment/v1-s5-013-pr1-upgrade-rollback.v1alpha1.json`](environment/v1-s5-013-pr1-upgrade-rollback.v1alpha1.json), [`environment/v1-s5-013-pr1-upgrade-rollback-transcript.txt`](environment/v1-s5-013-pr1-upgrade-rollback-transcript.txt), [`environment/v1-s5-013-pr1-cluster-prepare-transcript.txt`](environment/v1-s5-013-pr1-cluster-prepare-transcript.txt) | One provider, one host, one replica of each tier, and one injected fault — an artifact byte-count mismatch — in each of two runs. On 2026-09-12 five attempts were made and four failed for reasons that record lists, and it measured 6,425, 1,512, and 7,983 ms for the three intervals on code nothing identifies; the statement's timings are the 2026-09-26 run's, one attempt at a named revision. The two runs are not a trend or a spread. Detection and rollback were both performed by an operating script a person started. This claim is a recorded coverage gap in the test inventory: no pytest module proves it, the modules named here are adjacent to it, and what proves it is the executed records. Release blocker b4-upgrade-rollback-code-unidentified closed by V1-S5-013-PR1 with a rerun from a fresh clone at bcad343133ba6fddfe38832a2694e71777cdd006, whose status was empty before the first step and after the last, which detected the fault, rolled the release back, and served a real completion again; the 2026-09-12 record stays cited for what it observed. |

### Telemetry, dashboard, and alerts

*What can be seen while it runs, and what reaches a person?*

**Tally:** 6 `certified`, 1 `planned`, 1 `not-claimed`.

| Claim | Status | Evidence records | Limitation |
|---|---|---|---|
| The InferOps API emits eight catalog metrics and structured request records when its ASGI interface is exercised, each inside a declared series budget. | `certified` | `C1` · `local-process`, `cpu` · workload `operator-issued` · substituted `llama-cpp-adapter` (mock, claim-material), `llama-cpp-server` (mock, claim-material), `qwen3-1-7b-q8-0` (mock, claim-material) · [`telemetry/v1-s1-008-pr1-validation.md`](telemetry/v1-s1-008-pr1-validation.md)<br>`C1` · `local-process`, `cpu` · workload `operator-issued` · substituted `llama-cpp-adapter` (mock, claim-material), `llama-cpp-server` (mock, claim-material), `qwen3-1-7b-q8-0` (mock, claim-material) · [`testing/v1-s5-006-pr2-pinned-suite-run.md`](testing/v1-s5-006-pr2-pinned-suite-run.md) | Repository-local, mock-backed evidence, and at the date of the record nothing collected any of it — no exporter, collector, store, dashboard, or alert was selected. A release-scoped collector has since scraped these metrics, which is a separate row with its own record. No component emits a span. |
| The collector the release installs discovered and scraped both InferOps scrape jobs on `docker-desktop`, and a real Prometheus evaluated every accepted correlation query against what it collected. | `certified` | `C2` · `local-kubernetes` on `docker-desktop`, `cpu` · workload `operator-issued` · [`telemetry/v1-s3-011-pr2-telemetry-during-recovery.md`](telemetry/v1-s3-011-pr2-telemetry-during-recovery.md), [`environment/v1-s3-011-pr1-docker-desktop-paved-road.md`](environment/v1-s3-011-pr1-docker-desktop-paved-road.md)<br>`C2` · `local-kubernetes` on `docker-desktop`, `cpu` · workload `operator-issued` · [`environment/v1-s5-001-pr2-telemetry-verification.json`](environment/v1-s5-001-pr2-telemetry-verification.json), [`environment/v1-s5-001-pr2-clean-clone-run.md`](environment/v1-s5-001-pr2-clean-clone-run.md), [`environment/v1-s5-001-pr2-attempt-3-ledger.v1alpha1.json`](environment/v1-s5-001-pr2-attempt-3-ledger.v1alpha1.json) | One provider, one Windows host, one moment, one replica of each tier, sampled every five seconds. The collector's series are ephemeral and no durable store exists. The first run's per-query result was written to an ignored host path; the committed per-query result is the second record's, from the clean-clone run, which also returned one sample nobody has explained for a query expected to be empty. |
| A real Prometheus parsed and evaluated all 30 panel expressions in nine states and refused none, and a real Grafana imported the generated JSON and rendered all 29 panels. | `certified` | `C2` · `local-kubernetes` on `docker-desktop`, `cpu` · workload `operator-issued` · [`telemetry/v1-s4-002-pr2-dashboard-validation.md`](telemetry/v1-s4-002-pr2-dashboard-validation.md)<br>`C0` · `repository-only` · [`telemetry/v1-s4-002-pr1-validation.md`](telemetry/v1-s4-002-pr1-validation.md) | One provider, one host, one single-replica release, one Grafana version, one run of about twelve minutes on 2026-09-14. Grafana ran as a local container outside the cluster and no server runs it. Of 270 readings, 152 were a value, 81 empty and 37 zero. |
| Six alerts are published, each with an owner, a severity, the condition, what a caller is experiencing, an evidence query repeated verbatim from an accepted correlation query, an operator action, a runbook link, a declared threshold basis, and what it will be quiet for; five conditions are deferred — three because nothing emits the signal, one because no chart here installs the exporter that would, and one because no error budget is decided anywhere in this project — and eight more are refused by a named rule. | `certified` | `C0` · `repository-only` · [`telemetry/v1-s4-008-pr1-alert-validation.md`](telemetry/v1-s4-008-pr1-alert-validation.md), [`telemetry/v1-s4-008-pr1-validation.md`](telemetry/v1-s4-008-pr1-validation.md) | The scenario fixtures are synthetic — every number in them was written by hand — and the evaluator is not Prometheus. The pinned collector's own `promtool` loads both rendered rule files, which is a smaller thing than evaluating them. No threshold is a figure this project measured. |
| Five of the six alerts were replayed over the telemetry captured by three real `docker-desktop` experiments; one fired, over one capture, and every silence carries the reason it was silent. | `certified` | `C0` · `repository-only` · [`telemetry/v1-s4-008-pr1-alert-validation.md`](telemetry/v1-s4-008-pr1-alert-validation.md), [`serving/v1-s4-007-pr1-unready-model-recovery.md`](serving/v1-s4-007-pr1-unready-model-recovery.md), [`serving/v1-s4-006-pr1-inference-pod-recovery.md`](serving/v1-s4-006-pr1-inference-pod-recovery.md), [`serving/v1-s4-004-pr1-validation.md`](serving/v1-s4-004-pr1-validation.md), [`serving/v1-s4-007-pr1-telemetry.v1alpha1.json`](serving/v1-s4-007-pr1-telemetry.v1alpha1.json), [`serving/v1-s4-006-pr1-telemetry.v1alpha1.json`](serving/v1-s4-006-pr1-telemetry.v1alpha1.json), [`serving/v1-s4-004-pr1-telemetry.v1alpha1.json`](serving/v1-s4-004-pr1-telemetry.v1alpha1.json) | The captures are real, from `docker-desktop`, and they step at 15 seconds; the replay over them is this repository's own evaluator, which its record classifies `local-static` — so this row is a `C0` claim about a replay, not a `C2` claim about a runtime. The 60-second step belongs to the synthetic fixtures rather than to these captures. One alert missed the same run by one evaluation, and that is recorded rather than tuned away. |
| A prompt, a response, a provider error body, and a secret have no permitted placement in the committed telemetry catalog at all, and a tenant identifier, a correlation identifier, and any unbounded or measured value are excluded from metric labels. | `certified` | `C0` · `repository-only` · [`telemetry/v1-s0-007-pr1-validation.md`](telemetry/v1-s0-007-pr1-validation.md), [`telemetry/v1-s1-008-pr1-validation.md`](telemetry/v1-s1-008-pr1-validation.md) | Content capture is disabled at the API's metric-declaration and structured-record sinks and has no policy that could enable it. The first record cited predates every one of those sinks — when it was written nothing in this repository emitted a metric, a log record, or a span, and it checks the committed catalog alone; the second is where the sinks arrive. The check is over committed data and the sinks that read it. |
| In a real run, no prompt, response, or secret reaches a log or a metric. | `planned` | none, and a `planned` claim may hold none | The mock-integration suite checks that forbidden content reaches neither sink. The claim requires `C2` and a real layer, and no record binds it. |
| An operator is notified when an InferOps alert fires. | `not-claimed` | none recorded | The gap is published in the alerts document rather than left to be discovered. |

### Performance evidence

*What was measured under load, and what does it not mean?*

**Tally:** 3 `certified`, 1 `deferred`.

| Claim | Status | Evidence records | Limitation |
|---|---|---|---|
| A versioned load profile with a warm-up, rising concurrency levels, duration and request bounds, a client deadline above the API's, and a fixed response classification generates repeatable load and a raw record set whose accounting is checked on read. | `certified` | `C1` · `local-process`, `cpu` · workload `synthetic` · substituted `inferops-api` (stub, claim-material), `llama-cpp-server` (stub, claim-material), `qwen3-1-7b-q8-0` (stub, claim-material) · [`serving/v1-s4-003-pr1-validation.md`](serving/v1-s4-003-pr1-validation.md)<br>`C2` · `local-kubernetes` on `docker-desktop`, `cpu` · workload `synthetic` · [`serving/v1-s4-004-pr1-validation.md`](serving/v1-s4-004-pr1-validation.md), [`serving/v1-s4-004-pr1-environment.v1alpha1.json`](serving/v1-s4-004-pr1-environment.v1alpha1.json) | The tool's own rehearsal is synthetic — an in-process stub whose latencies are a 20 ms sleep plus loopback and thread scheduling — and it says so. Its first real load was sent by the performance scenarios, on `docker-desktop`, on one host, twice, in one window. |
| The load profile ran twice against a release the workflow installs, all 366 requests answered HTTP 200, and for that one single-slot release and fixed prompt the observed degradation point is concurrency 2: completed requests stayed between 0.554 and 0.575 per second from concurrency 1 to 4 while median latency rose about twofold and fourfold. | `certified` | `C2` · `local-kubernetes` on `docker-desktop`, `cpu` · workload `synthetic` · [`serving/v1-s4-004-pr1-validation.md`](serving/v1-s4-004-pr1-validation.md), [`serving/v1-s4-004-pr2-performance-findings.md`](serving/v1-s4-004-pr2-performance-findings.md), [`serving/v1-s4-004-pr1-environment.v1alpha1.json`](serving/v1-s4-004-pr1-environment.v1alpha1.json) | One provider, one host, one release, one prompt, two repetitions in one window on 2026-09-14, published as a bounded local observation under ADR 0013. The node was shared with twelve other running pods, every latency includes a loopback port-forward, the prompt cache serves nearly all of every prompt after the first, and the repository was not committed when the run was made. |
| A local serving baseline was executed under a warm-up, a measured count, and five thresholds registered before the run, against a fixture rewritten after the registered one was refused, and all thirty measured requests succeeded with every threshold met. | `certified` | `C2` · `local-container`, `cpu` · workload `operator-issued` · [`serving/v1-s2-005-local-baseline-experiment.md`](serving/v1-s2-005-local-baseline-experiment.md), [`serving/v1-s2-005-baseline-raw-results.md`](serving/v1-s2-005-baseline-raw-results.md)<br>`C2` · `local-container`, `cpu` · workload `operator-issued` · [`serving/v1-s5-013-pr1-baseline-rerun.md`](serving/v1-s5-013-pr1-baseline-rerun.md), [`serving/v1-s5-013-pr1-baseline-raw.jsonl`](serving/v1-s5-013-pr1-baseline-raw.jsonl), [`serving/v1-s5-013-pr1-baseline-summary.json`](serving/v1-s5-013-pr1-baseline-summary.json), [`serving/v1-s5-013-pr1-baseline-transcript.txt`](serving/v1-s5-013-pr1-baseline-transcript.txt) | One host, two runs, on 2026-09-03 and 2026-09-26, CPU only, concurrency one, one request shape. The five thresholds were registered before the run; the fixture was not the one registered — the original two-message fixture was refused by the API on all thirty requests of the prior attempt and was rewritten to be answerable before this run, which the experiment record states in its own correction section. The record's own warning is that V1 publishes no throughput, latency, capacity, or benchmark figure from these results, and its periodic processor sampler read 0.83 per cent while a live poll during generation read 801.97 per cent, so its processor figures materially understate the load; the 2026-09-26 run's sampler read at most 0.01 per cent for the same reason. The identifier's method registered first is true of the thresholds, the warm-up, the measured count, and the procedure, and not of the fixture, which the statement names. Release blocker b1-local-baseline-code-unidentified closed by V1-S5-013-PR1 with a rerun from a fresh clone at bcad343133ba6fddfe38832a2694e71777cdd006, whose status was empty before the first step and after the last, which met all five thresholds against the same registered descriptor; the claim's code identity rests on that run, and the 2026-09-03 record stays cited for what it observed. |
| InferOps sustains a stated throughput and capacity under load. | `deferred` | none, and a `deferred` claim may hold none | Deferred out of V1 by the project boundaries and left deferred by ADR 0013, which narrowed the rule only far enough to allow a bounded observation of one declared, authorized local experiment. This is the portable claim, and it stays deferred. It is also a recorded coverage gap in the test inventory: the capacity layer declares no test paths and its marker is deselected by default, so no pytest module would notice if it were promoted. |

### Cost method

*What does this project say a run costs?*

**Tally:** 2 `certified`, 1 `not-claimed`.

| Claim | Status | Evidence records | Limitation |
|---|---|---|---|
| Two committed cost records derive their processor and memory use by tool from the committed samples of the `V1-S4-004` performance run rather than from a typed-in figure, and each regenerates from its own input and the committed method. | `certified` | `C0` · `repository-only` · [`cost/v1-s4-005-pr2-cost-baseline.md`](cost/v1-s4-005-pr2-cost-baseline.md), [`cost/v1-s4-005-pr2-validation.md`](cost/v1-s4-005-pr2-validation.md) | What is certified here is a file-reading operation: that the use is taken from committed samples by tool rather than typed in, and that each record regenerates from its own input and the committed method. The samples themselves are local real CPU evidence measured on `docker-desktop` during `V1-S4-004` — one host, one release, one prompt, two runs — and that measurement is a different row with its own record; every price is from the synthetic rate card, so both cost records carry confidence `none` and certify nothing themselves. The window is a load span rather than an accounting hour, the collector is left on the unallocated line by a choice rather than a measurement, and the owner is declared rather than observed. |
| Every amount declares its basis, no amount whose basis is not `actual` may carry the vocabulary or the reference of an invoice, every unit cost carries the count it was divided by and vanishes below a declared minimum, and a record's confidence is recomputed from its own inputs rather than read from a field its producer filled in. | `certified` | `C0` · `repository-only` · [`cost/v1-s0-008-pr1-validation.md`](cost/v1-s0-008-pr1-validation.md), [`cost/v1-s4-005-pr1-validation.md`](cost/v1-s4-005-pr1-validation.md) | The only rate card committed is synthetic and says so in its own contents, so every record it prices has confidence `none`. ADR 0014 narrows V1 to the estimated basis; the allocated basis stays specified and unreachable. |
| Running this inference workload costs a stated amount on a real provider. | `not-claimed` | none recorded | The arithmetic that would consume a real rate card is specified and tested against synthetic fixtures. Nothing else about the figure would be different; the price would. |

### Security boundary

*What is enforced, and what is only rendered?*

**Tally:** 3 `certified`, 1 `planned`, 2 `not-claimed`.

| Claim | Status | Evidence records | Limitation |
|---|---|---|---|
| Every control in the committed security baseline derives its status from the verification it names, a control naming an automated test or a shell guard names one that exists, and no control claims to act inside a running system. | `certified` | `C0` · `repository-only` · [`security/v1-s0-009-pr1-validation.md`](security/v1-s0-009-pr1-validation.md) | The cited record measured ten of thirty-two controls with no verification at all. The committed baseline has since grown to thirty-eight, of which six have no verification and nine are enforced by nothing automated; those three figures are properties of the data committed today rather than of the record, and the suite that reads it is what holds them. Twelve risks are carried rather than reduced, and ten of the twelve block production use. |
| A committed manifest dropping a required workload security control is refused citing the rules it drops and no others, checked in both directions against nine fixtures that each drop one control. | `certified` | `C0` · `repository-only` · [`security/v1-s3-004-pr1-validation.md`](security/v1-s3-004-pr1-validation.md) | The validator reads YAML. It holds no credential, contacts no cluster, and stops nothing being applied; no admission control applies any of its rules to a pod. When the record cited was written no release had been installed and none could be, because no API image was published; `V1-S3-011` installed one afterwards, and no committed record reads a pod that resulted against these rules, which is why the paved-road record that installed it is not cited here. |
| An image scanner and a dependency auditor were each run once by hand against the pinned runtime image and the committed lockfile at the committed severity threshold, and two CycloneDX bills of materials were published. | `certified` | `C0` · `repository-only` · [`security/v1-s2-006-pr1-validation.md`](security/v1-s2-006-pr1-validation.md) | One host, one day on 2026-09-03, against one vulnerability database version. A rerun tomorrow can find something today's run did not, so a green result dates rather than proves. The dependency scan covers Python distributions only. No provenance is verified and `DR-08` still carries that gap. The record describes itself as local real evidence in the older vocabulary; the strategy assigns the `security-scan` layer the `local-static` class with a `C0` ceiling, and this row follows the strategy, because reading a pinned image is not running one. |
| The NetworkPolicy objects the chart renders restrict traffic in the clusters this project runs on. | `not-claimed` | `C1` · `local-kubernetes` on `docker-desktop`, `cpu` · workload `operator-issued` · substituted `inferops-llm-chart` (fixture, claim-material) · [`security/v1-s3-004-pr1-network-policy-enforcement.md`](security/v1-s3-004-pr1-network-policy-enforcement.md) | One host, one day, on Docker Desktop's Kubernetes rather than the cluster ADR 0001 accepted, and the record says substituting a cluster is a substitution rather than an equivalence. |
| No credential and no model artifact enters this repository's public history. | `planned` | none, and a `planned` claim may hold none | A secret scanner has run once by hand from its published container image, over 134 commits, and found no leaks; the gate that installs the pinned release archive has since passed on the service, but that run is observed rather than recorded. The claim stays planned on the strength of one run. It is a recorded coverage gap in the test inventory: no pytest module scans history for a credential, and the suite that reads the scanner configuration checks only that it is committed, parses, and exempts things that exist. |
| A deployed InferOps workload is authenticated, authorized, isolated, and defended. | `not-claimed` | none recorded | The rendered pod-security settings are carried by workloads a release deployed. That is a property of the manifests, and no check reads a pod that resulted. |

### Multi-replica serving

*Has more than one serving replica ever been certified?*

**Tally:** 1 `not-claimed`.

| Claim | Status | Evidence records | Limitation |
|---|---|---|---|
| Two real serving replicas are certified to serve real inference in a cluster. | `not-claimed` | `C0` · `local-kubernetes` on `docker-desktop`, `cpu` · [`environment/v1-s3-011-pr1-docker-desktop-paved-road.md`](environment/v1-s3-011-pr1-docker-desktop-paved-road.md) | The refusal is the evidence. It is recorded in the paved-road record and it is not a weaker form of a certification. |

### Contracts, scaffolding, and the safe quick start

*What does the mock path prove, and what does it never prove?*

**Tally:** 5 `certified`, 3 `planned`.

| Claim | Status | Evidence records | Limitation |
|---|---|---|---|
| InferOps publishes a `WorkloadContract` `v1alpha1` schema with valid and invalid fixtures, versioning and compatibility rules, and a canonical rejection matrix. | `certified` | `C0` · `repository-only` · [`contracts/v1-s0-004-pr1-validation.md`](contracts/v1-s0-004-pr1-validation.md), [`contracts/v1-s0-004-pr2-validation.md`](contracts/v1-s0-004-pr2-validation.md) | The schema and its fixtures are files. No runtime component consumes the contract, so publishing it establishes nothing about what a deployment does with one. |
| Every document the validator refuses is refused with a canonical error code, a stable rule identifier, and a field location that the contract document publishes. | `certified` | `C0` · `repository-only` · [`contracts/v1-s0-004-pr2-validation.md`](contracts/v1-s0-004-pr2-validation.md) | A refusal is a property of the validator reading a file. The controls behind it in the default lane are fixtures compared against a committed record of which rule each must produce. |
| A contract document is parsed into typed domain objects with explicit contract-version handling, and seven semantic validation rules are applied to what parsing produced. | `certified` | `C2` · `local-process`, `cpu` · workload `operator-issued` · [`domain/v1-s1-001-pr1-validation.md`](domain/v1-s1-001-pr1-validation.md), [`domain/v1-s1-001-pr2-validation.md`](domain/v1-s1-001-pr2-validation.md)<br>`C2` · `local-process`, `cpu` · workload `operator-issued` · [`testing/v1-s5-006-pr2-pinned-suite-run.md`](testing/v1-s5-006-pr2-pinned-suite-run.md) | Parsing, version handling, and the semantic rules are implemented and tested; what the domain model describes and nothing builds is the rendering of a deployment from what they produce. The record that carries the immutable versions is the first of the two cited: the second records no environment table of its own, and its results section disagrees with its own evidence block on how many tests ran. |
| The scaffolding command renders a workload project for the mock and synchronous profiles and refuses to overwrite a file that already exists. | `certified` | `C2` · `local-process`, `cpu` · workload `operator-issued` · substituted `scaffold-file-write-path` (stub) · [`scaffolding/v1-s1-006-pr2-validation.md`](scaffolding/v1-s1-006-pr2-validation.md), [`scaffolding/v1-s1-006-independent-walkthrough.md`](scaffolding/v1-s1-006-independent-walkthrough.md) | The walkthrough was executed on one Windows host by an independent Codex reviewer rather than a human second engineer, and the record says so. The synchronous profile was generated and validated, never deployed. The walkthrough never scaffolded into an occupied destination: the refusal to overwrite rests on the suite in the change-validation record cited beside it, which states that it certifies no claim in the test matrix and moves no layer. |
| The published developer quick start was followed on a clean checkout and its mock workflow completed, and the authorization-gated real-runtime smoke it points at has been executed and recorded separately. | `certified` | `C1` · `local-process`, `cpu` · workload `operator-issued` · substituted `llama-cpp-adapter` (mock, claim-material), `llama-cpp-server` (mock, claim-material), `qwen3-1-7b-q8-0` (mock, claim-material) · [`quickstart/v1-s1-009-pr1-validation.md`](quickstart/v1-s1-009-pr1-validation.md), [`scaffolding/v1-s1-006-independent-walkthrough.md`](scaffolding/v1-s1-006-independent-walkthrough.md)<br>`C2` · `local-kubernetes`, provider not named by its record, `cpu` · workload `operator-issued` · [`serving/v1-s1-real-runtime-closure.md`](serving/v1-s1-real-runtime-closure.md) | One Windows host, one executor, mock adapter throughout. The API was driven in process through ASGI and no network socket was opened. In the quick start's own record the real-runtime lane is seven skips, because the runtime settings were absent, and a skipped session is not a smoke run; the execution is the third record cited, which is a separate authorized run on a capable host. |
| The mock serving path declares its own kind and refuses a model identity that is not mock-labelled, so a mock result cannot be mistaken for a real one. | `planned` | none, and a `planned` claim may hold none | The behaviour is implemented and exercised by the adapter and mock-integration layers. The claim and test matrix has not promoted it, and no evidence record binds it. |
| Deployment values are derived only from a document that has passed validation. | `planned` | none, and a `planned` claim may hold none | Deployment rendering does not exist. The chart's values are written by an operator, not derived from a document. |
| A workload described by a `WorkloadContract` document is served by the platform that document configures. | `planned` | none, and a `planned` claim may hold none | Every real run so far deployed the runtime from a feasibility manifest or from the Helm chart, not from a generated `WorkloadContract`. The mock layers show the API maps the call; they cannot show a document drove the deployment. |

### Release and production use

*Is there a release, and can somebody else run this in production?*

**Tally:** 2 `not-claimed`.

| Claim | Status | Evidence records | Limitation |
|---|---|---|---|
| InferOps has published a versioned V1 release. | `not-claimed` | none recorded | Semantic versioning is an intention that begins when versioned releases begin. |
| InferOps is a production-ready, portable inference platform someone can deploy for someone else. | `not-claimed` | none recorded | The evidence levels define `C3` and `C4` so the ceiling is visible rather than implied. No V1 record is above `C2`, and `C4` Operational Evidence is not reachable at all, because there is no organizational production to observe. |

### Ownership, tests, continuous integration, and evidence

*Who owns each resource, who checks the rows above, and where does the proof live?*

**Tally:** 5 `certified`, 2 `not-claimed`.

| Claim | Status | Evidence records | Limitation |
|---|---|---|---|
| Every resource in the committed ownership inventory has exactly one owner, and since the chart and the Terraform configuration exist the inventory is compared with them in both directions. | `certified` | `C0` · `repository-only` · [`architecture/v1-s0-005-pr1-validation.md`](architecture/v1-s0-005-pr1-validation.md), [`architecture/v1-s3-002-pr2-validation.md`](architecture/v1-s3-002-pr2-validation.md), [`architecture/v1-s3-010-pr1-validation.md`](architecture/v1-s3-010-pr1-validation.md) | When the first record cited was written there was no Terraform configuration and no Helm chart, so nothing compared the inventory to an implementation and its own dump counted nineteen planned rows against eight implemented. The committed inventory held thirty-nine resources when this row was migrated, thirty-four implemented, three deferred and two planned; those figures belong to the data rather than to any record cited here, the suite that reads the inventory is what holds them, and each implemented row cites the run that moved it. Deployment rendering is still not built. |
| Eleven gates are committed as one workflow and as a matrix that maps each to the claims it defends or to a recorded reason it defends none, compared with the workflow in both directions. | `certified` | `C0` · `repository-only` · [`testing/v1-s4-001-pr1-validation.md`](testing/v1-s4-001-pr1-validation.md), [`testing/v1-s4-001-pr2-validation.md`](testing/v1-s4-001-pr2-validation.md) | The first record cited committed nine gates and no job had then executed on the service; its one hosted run failed three jobs. The second is where the count reaches eleven and where nine gates' job conclusions were read back from the service's public API on 2026-09-13, when the two infrastructure gates had not yet run there. A later committed read of the same API, `docs/proof/security/v1-s5-004-pr1-hosted-runs.v1alpha1.json`, lists nineteen pushes to `main` in which every job concluded `success`, the two infrastructure gates in the eighteen runs that carry them; it and the second record both state that they promote no run and certify nothing, so this claim states no service result and rests on neither. No log or artifact from any run is promoted into a record and the logs expire, and two gates are not deterministic because a vulnerability database moves daily. |
| The default test lane downloads no model and reaches no cluster, because every marker belonging to a layer that needs one is deselected by the committed default marker expression and a test compares that expression with the strategy in both directions. | `certified` | `C0` · `repository-only` · [`testing/v1-s0-006-pr1-validation.md`](testing/v1-s0-006-pr1-validation.md), [`testing/v1-s4-001-pr2-validation.md`](testing/v1-s4-001-pr2-validation.md) | The marker expression is what the first record cited establishes, and when it was written no continuous-integration lane existed at all. Helm and Terraform arrived with the second: they run in the lane only as subcommands that read files, and a check refuses anything else it can recognise. The lane is cheap and reproducible rather than hermetic — five gates consume the network — and three lanes still run entirely by hand. |
| Evidence that certifies a claim is committed under `docs/proof/`, carries classification, provenance, environment, method, results, limitations, and authorisation, and is produced by a reviewed change rather than by a job. | `not-claimed` | `C0` · `repository-only` · [`telemetry/v1-s0-007-pr1-validation.md`](telemetry/v1-s0-007-pr1-validation.md)<br>`C0` · `repository-only` · [`testing/v1-s5-012-pr2-migration-report.md`](testing/v1-s5-012-pr2-migration-report.md) | The first record cited is from the day the four templates were published, when they had produced nothing; it checks the templates' required sections, not any record produced since. Two have produced records since — one experiment record and five raw-result records, counted by a suite from the declarations those records carry — and `environment` and `claim-evidence` still have none. This matrix does not change that: binding claims in a table is not the one-claim-per-record form the fourth template exists to enforce. |
| Every relative link in every committed Markdown document resolves from the directory of the file that contains it. | `certified` | `C0` · `repository-only` · [`testing/v1-s0-006-pr1-validation.md`](testing/v1-s0-006-pr1-validation.md)<br>`C0` · `repository-only` · [`testing/v1-s5-002-pr2-validation.md`](testing/v1-s5-002-pr2-validation.md) | It establishes that a path resolves, and nothing more. It runs over committed Markdown only, reads a target up to its first closing parenthesis, and skips fenced blocks, so a command sample is never mistaken for a link and a link inside one is never checked. |
| The test strategy, the claim and test matrix, the test inventory, the gate matrix, this claim and evidence matrix, and the pytest configuration are compared with their committed data in both directions, so none can gain or lose an identifier without a failing build. | `certified` | `C0` · `repository-only` · [`testing/v1-s0-006-pr1-validation.md`](testing/v1-s0-006-pr1-validation.md), [`testing/v1-s1-007-pr1-validation.md`](testing/v1-s1-007-pr1-validation.md), [`testing/v1-s4-001-pr1-validation.md`](testing/v1-s4-001-pr1-validation.md), [`testing/v1-s4-009-pr1-validation.md`](testing/v1-s4-009-pr1-validation.md) | It stops each document drifting from its data. The four records cited arrive in that order — the strategy, the inventory, the gate matrix, this register — because the first covers the strategy and its three documents alone and nothing else existed to compare when it was written. Two of the eleven layers still have no code behind them, and the suite cannot tell an honestly planned layer from one that will never be written. |
| A continuous-integration lane installs a release into a cluster or executes a real model. | `not-claimed` | none recorded | Normal continuous integration must not discover an ambient cluster and mutate it, and the lane is checked to be unable to reach one. |

## What V1 does not claim

18 claims, derived from the register rather than listed here: a
claim that stops being certified joins this table without anybody adding it.
That is deliberate. A page that can only be complete about its successes is
an advertisement. A record beside a claim here is the measurement of an
absence or a refusal, at the level that measurement was obtained; it is not a
weaker form of the capability.

| Claim | Status | Why it is not certified | Evidence records, where any exist |
|---|---|---|---|
| A workload described by a `WorkloadContract` document is served by the platform that document configures. | `planned` | Every real run so far deployed the runtime from a feasibility manifest or from the Helm chart, not from a generated `WorkloadContract`. The mock layers show the API maps the call; they cannot show a document drove the deployment. | none, and a `planned` claim may hold none |
| Deployment values are derived only from a document that has passed validation. | `planned` | Deployment rendering does not exist. The chart's values are written by an operator, not derived from a document. | none, and a `planned` claim may hold none |
| The mock serving path declares its own kind and refuses a model identity that is not mock-labelled, so a mock result cannot be mistaken for a real one. | `planned` | The behaviour is implemented and exercised by the adapter and mock-integration layers. The claim and test matrix has not promoted it, and no evidence record binds it. | none, and a `planned` claim may hold none |
| A model that is not ready produces a canonical error rather than an unhandled failure or a fabricated answer. | `planned` | The unready-model experiment measured the real condition and found that no caller ever received `model-not-ready`: all eight completions came back `capability-unavailable` with condition `runtime-unreachable`. That is a measured fact about the deployed shape, and it is a reason this claim stays planned rather than a reason to promote it. | none, and a `planned` claim may hold none |
| A runtime that cannot be reached produces a canonical error rather than an unhandled failure. | `planned` | The mock layers show the API maps the condition to the right error. They cannot show the condition occurs, or that the runtime produces it in the way the mock's author imagined. | none, and a `planned` claim may hold none |
| The optional `kind` helper creates a local development cluster, runs a workload inside it, and removes it leaving no residue the verifier can find. | `not-claimed` | V1 does not claim that the optional kind helper creates and removes a local cluster without residue at any identified revision of this repository. Its only run, on 2026-08-23, names no revision, and nothing else identifies the helper code that ran. V1-S5-013-PR1 did not run it again: the reference host has no kind CLI, ADR 0011 D11 made the helper optional and not the platform path, the maintainer decided the release would not install kind to re-prove it, and ADR 0011 forbids reading Docker Desktop evidence across to kind. The 2026-08-23 record stays cited for what it observed, at the level it was given. | `C2` · `local-kubernetes` on `kind`, `cpu` · workload `operator-issued` · [`environment/v1-s0-002-pr2-cluster-smoke.md`](environment/v1-s0-002-pr2-cluster-smoke.md) |
| Two real serving replicas are certified to serve real inference in a cluster. | `not-claimed` | The workflow was run on the reference host and refused at the capacity gate before it installed anything: 8,484,278,272 bytes of uncommitted cluster memory available against 8,657,043,456 required, a shortfall of about 165 MiB held by unrelated workloads that were not this project's to remove. The gate was not weakened and the replica count was not reduced to fit. | `C0` · `local-kubernetes` on `docker-desktop`, `cpu` · [`environment/v1-s3-011-pr1-docker-desktop-paved-road.md`](environment/v1-s3-011-pr1-docker-desktop-paved-road.md) |
| InferOps sustains a stated throughput and capacity under load. | `deferred` | Deferred out of V1 by the project boundaries and left deferred by ADR 0013, which narrowed the rule only far enough to allow a bounded observation of one declared, authorized local experiment. This is the portable claim, and it stays deferred. It is also a recorded coverage gap in the test inventory: the capacity layer declares no test paths and its marker is deselected by default, so no pytest module would notice if it were promoted. | none, and a `deferred` claim may hold none |
| In a real run, no prompt, response, or secret reaches a log or a metric. | `planned` | The mock-integration suite checks that forbidden content reaches neither sink. The claim requires `C2` and a real layer, and no record binds it. | none, and a `planned` claim may hold none |
| An operator is notified when an InferOps alert fires. | `not-claimed` | No alert manager, receiver, routing tree, or notification path is committed or installed. The rules render into the chart and nothing evaluates or routes them. | none recorded |
| Running this inference workload costs a stated amount on a real provider. | `not-claimed` | Nothing here has ever been paid for. It runs on a local single-node cluster on a contributor's own machine, no provider account exists, and the `actual` basis is therefore unreachable in V1. | none recorded |
| The NetworkPolicy objects the chart renders restrict traffic in the clusters this project runs on. | `not-claimed` | An executed experiment on 2026-09-06 applied a total-denial policy and nothing was refused: pod-to-pod by address, a DNS lookup, and a direct query to CoreDNS all succeeded, because the observed network plugin runs with no policy controller enabled. The four policy objects the chart renders are inert on that plugin. | `C1` · `local-kubernetes` on `docker-desktop`, `cpu` · workload `operator-issued` · substituted `inferops-llm-chart` (fixture, claim-material) · [`security/v1-s3-004-pr1-network-policy-enforcement.md`](security/v1-s3-004-pr1-network-policy-enforcement.md) |
| No credential and no model artifact enters this repository's public history. | `planned` | A secret scanner has run once by hand from its published container image, over 134 commits, and found no leaks; the gate that installs the pinned release archive has since passed on the service, but that run is observed rather than recorded. The claim stays planned on the strength of one run. It is a recorded coverage gap in the test inventory: no pytest module scans history for a credential, and the suite that reads the scanner configuration checks only that it is committed, parses, and exempts things that exist. | none, and a `planned` claim may hold none |
| A deployed InferOps workload is authenticated, authorized, isolated, and defended. | `not-claimed` | Nothing in this repository authenticates a caller, authorises a request, or admits a pod. There is no admission control, no gateway, and no multi-tenancy. Twelve risks are carried rather than reduced and ten of them block production use. | none recorded |
| A continuous-integration lane installs a release into a cluster or executes a real model. | `not-claimed` | No workflow for a cluster lane is committed, only the rules one must satisfy. No runner is labelled capable and no hosted runner is authorized to hold the pinned model artifact; ADR 0005 D6 leaves that half open on purpose. | none recorded |
| Evidence that certifies a claim is committed under `docs/proof/`, carries classification, provenance, environment, method, results, limitations, and authorisation, and is produced by a reviewed change rather than by a job. | `not-claimed` | Measured in V1-S5-012-PR2: of the 52 Markdown records cited by the claims the v1alpha1 register held as certified, 20 contain no statement about authorisation of any kind, so the sentence that every certifying record carries one is not true of the records committed. The templates require the section; the records produced before them, and several since, do not have it. Nothing checks that a record was produced by a reviewed change rather than by a job. | `C0` · `repository-only` · [`telemetry/v1-s0-007-pr1-validation.md`](telemetry/v1-s0-007-pr1-validation.md)<br>`C0` · `repository-only` · [`testing/v1-s5-012-pr2-migration-report.md`](testing/v1-s5-012-pr2-migration-report.md) |
| InferOps has published a versioned V1 release. | `not-claimed` | The release process is documented and no release has been executed. The changelog holds unreleased changes only. | none recorded |
| InferOps is a production-ready, portable inference platform someone can deploy for someone else. | `not-claimed` | `production-experience` is unreachable from this repository: there is no organizational production to draw it from, and public-cloud execution is not production operation. Every executed result is one Windows host, one provider, CPU, one replica of each tier, started by hand under explicit authorization against a cluster the operator already owns. | none recorded |

## What this page is not

- **It is not a monitoring dashboard.** It reads committed files and asks
  nothing of a cluster. The operations view is
  [the inference operations dashboard](../telemetry/inference-operations-dashboard.md);
  the two answer different questions and neither substitutes for the other.
- **Operations evidence is kept apart from it.** The Grafana screenshots in
  [`telemetry/v1-s4-002-pr2-screenshots/`](telemetry/v1-s4-002-pr2-screenshots/)
  and the record of
  [the dashboard asked of a real Prometheus](telemetry/v1-s4-002-pr2-dashboard-validation.md)
  are **operations evidence**: what a running release showed on one day, on
  one host. The record is linked from the telemetry rows above and the
  screenshots are linked from the record; neither is a proof state, and no
  panel in them is a certification.
- **It is not a second source of truth.** Every status, level, environment,
  provider, substitution, record, and limitation above is read from
  [the register](../testing/claim-evidence-matrix.md) when the page is
  generated, and the register's own evidence rules are run again before a
  page is produced. This tool holds one thing the register does not: which
  claims a reviewer is shown under which heading.
- **It is not an external certification.** The levels are project-defined,
  and no outside party has reviewed the register, a record, or this page.
- **It is not a freshness or assurance signal.** Nothing here says when a
  result was last re-run, whether the environment that produced it still
  exists, or whether it would reproduce today. A record's own date and
  provenance sections are the only answer to that, and they are in the record.
- **It is not a release gate.** No check consumes this page to decide whether
  anything may ship. The gates are in
  [the continuous-integration gate matrix](../testing/ci-gate-matrix.md).

## Limitations

- The page inherits every limitation the register carries, including the
  largest: the checks establish that references resolve, that every record
  carries what its level requires and passes the evidence-level rules, and
  that the page and the register agree. None of them establishes that a
  statement is true, that a record says what the row citing it says it says,
  or that a claim declared the right components material — those are review
  judgements, listed in [the rule catalogue](../testing/evidence-level-rules.md).
- Every real result behind these rows was produced on one Windows host, by
  one author, by hand. No outside party has reviewed a claim against its
  evidence.
- The capability grouping is a reading. Which claims belong under *model
  integrity* rather than *real serving* is a judgement made in
  `tools/proof_dashboard/core.py`, and no check decides it.
- **Every one of the 59 claims is shown as a row.** Each
  is named by exactly one capability group, so nothing on this page is
  counted in a total and absent from every table. That is a property of the
  grouping today, not a rule: a claim added to the register and named by no
  group would still be counted in every total, would still appear under what
  V1 does not claim if it were uncertified, and this sentence would change to
  say how many certified claims had no row.
- The bounded performance, recovery, and cost figures quoted in these rows
  are observations of declared local experiments under
  [ADR 0013](../architecture/decisions/ADR-0013-bounded-local-performance-observations.md)
  and
  [ADR 0014](../architecture/decisions/ADR-0014-v1-cost-calculation-reaches-the-estimated-basis.md).
  They are not capacity, service-level objectives, availability figures,
  error budgets, recovery-time objectives, benchmarks, or costs.

## What a later version of this page might do, and V1 does not

These are features of an assurance dashboard in an organisation that runs
many environments. None is built, none is planned for V1, none is a claim,
and this list exists so that their absence is read as a decision rather than
an oversight.

- **Freshness and expiry.** Nothing here ages a result. A record from
  2026-08 and one from 2026-09 are shown alike, and no row says when it would
  stop being believed.
- **Fleet and environment comparison.** Every row names at most one
  provider, and no claim here was run on two. A page that compared the same
  claim across providers, hosts, or clusters would need that claim's result
  from more than one of each, and V1 has no claim with more than one.
- **Continuous verification.** No schedule re-runs a record and no lane
  reports that a certified claim still holds; every real result is a run
  somebody made by hand and wrote down.
- **Promotion gates.** No check reads this page to decide whether a change,
  a release, or an environment may advance. The gates that exist are in
  [the continuous-integration gate matrix](../testing/ci-gate-matrix.md) and
  none of them consumes a proof state.
