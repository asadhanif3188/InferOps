# V1-S3-006-PR2 validation — multi-replica Kubernetes inference certification

Change: the workflow that certifies **multi-replica** real inference through
Kubernetes exists. A committed descriptor fixes the replica counts, the capacity
the profile needs, the bounded request set, and every assertion; a shell script
measures host and cluster capacity before creating anything, applies the Terraform
prerequisites, installs the chart with at least two platform API replicas, waits
for every replica individually, drives a bounded set of real requests through the
release's API Service from a short-lived in-cluster Job, collects the replicas'
own structured records, and tears the release down; a Python module asserts over
all of it, correlates each successful request to the replica that recorded it, and
writes a machine-readable record labelled `local real Kubernetes`. This record is
what was run, what it found, and what it does not support.

**Evidence class.** Everything asserted here is `local-static`: files read,
compared, formatted, linted, type-checked, and driven through documents a run
would have written. **Nothing has been installed.** No cluster was contacted, no
`terraform apply` ran, no Helm release was installed, no Job was created, no
request was sent, no model byte was read, and no completion was generated. **No
multi-replica `C2` Kubernetes record exists**, and no published claim gains
evidence from this change.

## What the change is

**The request set is sent from inside the cluster, and that is the point.** The
[single-replica certification](../../serving/kubernetes-real-inference-certification.md)
sends its one request through a `kubectl port-forward` and states the bound: a
forward is served by the API server against **one selected endpoint**, so it never
traverses the Service's virtual IP. A forward cannot distribute anything, and a
multi-replica claim built on one would be a claim about a client. So this workflow
creates one bounded `batch/v1` Job in the namespace which addresses the API
Service by name, one connection per request, and `kube-proxy` picks each endpoint.

**The correlation is a surface this project already publishes, and no new one was
added for it.** Every `request.completed` record the InferOps API writes carries
`inferops.request.id` and `k8s.pod.name`; the telemetry catalog puts the pod name
on records and deliberately keeps it off every metric, and the chart already
supplies `INFEROPS_POD_NAME` through the downward API. The requests this run sends
are joined to the pod names the API itself logged. **No response header, body
member, or endpoint exposes pod identity**: a test that made a replica's name part
of the API's contract in order to observe it would have changed the product to
measure it.

**Desired replicas are never treated as evidence.** `spec.replicas: 2` is a
request to a controller, and `status.readyReplicas` is a controller's summary. The
workflow requires the per-pod list: exactly the expected number of API pods, each
individually ready inside its own budget, and every pod that served a request must
be one of those. A run whose successful requests all landed on one ready replica
**fails**, with a message saying that this is the Service's endpoint choice rather
than a defect, and it is not retried or downgraded.

**Capacity refuses before anything is created.** Two API replicas and one runtime
replica are 1,210 millicores and 2,320 MiB of requests, peaking at 4,160 MiB of
memory limits. A host that cannot hold that produces a `Pending` pod and a rollout
that expires — a readiness failure that is really a laptop. So the descriptor
declares the figures, the architecture suite computes them from the chart's own
resource blocks times the replica counts and fails if the two drift, and the
preflight measures the engine and the cluster's **uncommitted** allocatable
before the namespace has anything in it. Every shortfall is reported at once with
a remedy, and the exit code is its own (`5`), so a caller can tell "this host is
too small" from "the platform did not certify".

**The replica count is never reduced to fit.** The validator refuses a descriptor
asking for fewer than two API replicas, and the script refuses it again at the
point the count is handed to Helm — that is the one value whose downgrade would
turn this into the single-replica workflow wearing a multi-replica record. The
counts are passed with `--set` from the descriptor rather than read from the
operator's values file, so a values file saying `replicaCount: 1` cannot decide
this profile.

**The two descriptors cannot drift.** Loading the multi-replica descriptor loads
the single-replica one and refuses any disagreement about the cluster, the
release, the Services, the model cache, the shared budgets, the real path, or the
per-request budget — and requires that the two record file names differ, since
both write into the same ignored directory.

**PR1 is untouched.** `scripts/environment/kubernetes-certification.sh`,
`deploy/serving/certification/k8s-real-inference.v1.json`,
`tools/kubernetes_certification/__main__.py`, and its descriptor loader are
unchanged, and a test asserts the single-replica script names neither the new
descriptor nor the new module. The one edit inside `core.py` is the extraction of
the evidence-path safety check into `ensure_evidence_paths_safe`, so that the
second workflow writing into the same ignored directory uses **the same guard**
rather than a second copy of it. Behaviour is identical and PR1's own suite passes
unchanged.

**Nothing is retained that this project has no business retaining.** The driver
writes each response body to its own memory-backed scratch directory, matches it
for the markers a real answer carries, and never prints it; what it prints is the
identifier, the status, the adapter kind, the model identifier, and the three
token counts. The collected records are filtered to the requests this run sent and
to the fields the correlation reads. A test asserts the prompt appears nowhere in
the record.

## Files changed

| File | Change |
|---|---|
| [`deploy/serving/certification/k8s-multi-replica-inference.v1.json`](../../../deploy/serving/certification/k8s-multi-replica-inference.v1.json) | New. The descriptor: replica counts, capacity figures, budgets, the request set, the assertions, the evidence locations, the cleanup policy, and the limitations |
| [`tools/kubernetes_certification/multi_replica.py`](../../../tools/kubernetes_certification/multi_replica.py) | New. Descriptor loading and cross-checking, the capacity gate, the per-pod facts reader, the request-set assertions, the correlation, the cleanup check, and the record |
| [`tools/kubernetes_certification/multi_replica_cli.py`](../../../tools/kubernetes_certification/multi_replica_cli.py) | New. `check`, `preflight`, `certify`, `record-cleanup`, and the capacity exit code |
| [`tools/kubernetes_certification/core.py`](../../../tools/kubernetes_certification/core.py) | Evidence-path safety extracted to `ensure_evidence_paths_safe` so both workflows share one guard. No behaviour change |
| [`scripts/environment/kubernetes-multi-replica-certification.sh`](../../../scripts/environment/kubernetes-multi-replica-certification.sh) | New. Every cluster operation, and the three embedded writers |
| [`docs/serving/kubernetes-multi-replica-certification.md`](../../serving/kubernetes-multi-replica-certification.md) | New. The published procedure, its stages, its bounds, and what its record will not support |
| [`tests/architecture/test_kubernetes_multi_replica_certification.py`](../../../tests/architecture/test_kubernetes_multi_replica_certification.py) | New. 138 checks |
| [`docs/architecture/resource-ownership.md`](../../architecture/resource-ownership.md) | Three procedures now install the same release rather than two, and the one object this workflow creates that neither Terraform nor the chart owns is accounted for |
| [`tests/architecture/test_cluster_lifecycle_safety.py`](../../../tests/architecture/test_cluster_lifecycle_safety.py) | The new script inventoried; the deletion-scoping rule widened to the release namespace and to a double-quoted resource name, with the adversarial samples for both |
| [`tests/testing/test_test_inventory.py`](../../../tests/testing/test_test_inventory.py) | One number word |
| `docs/testing/test-inventory.*`, `docs/testing/test-strategy.*` | The new module inventoried; the real-runtime lane's commands and notes extended |
| [`CHANGELOG.md`](../../../CHANGELOG.md) | The entry for this change |

## Validation performed

Every command below was run from the repository root on Windows 11 with the
project's own virtual environment.

| Command | Result |
|---|---|
| `python -m ruff format --check .` | Passed; every file already formatted |
| `python -m ruff check .` | Passed; no findings |
| `python -m mypy` | `Success: no issues found in 161 source files` |
| `python -m pytest -q` | `6513 passed, 28 skipped, 14 deselected` |
| `python -m pytest tests/architecture/test_kubernetes_multi_replica_certification.py -q` | `138 passed, 1 skipped` |
| `python -m tools.kubernetes_certification.multi_replica_cli check` | Printed the profile, the assertions, and every limitation; contacted nothing |
| `bash -n scripts/environment/kubernetes-multi-replica-certification.sh` | Parsed |
| `git diff --check` | No whitespace findings |

The one skip is the symlink refusal, which is skipped on a host that does not
permit creating a symlink.

**What was deliberately not run**, and is reported rather than worked around:

- no `terraform apply`, no `helm install`, no `kubectl` command, no cluster
  operation of any kind;
- no model download, no model load, no inference request, no Job;
- nothing that costs money and nothing that provisions anything.

`scripts/environment/kubernetes-multi-replica-certification.sh certify` was not
run, and could not complete today for the same reason PR1 could not: **no InferOps
API image is published**, so an authorized run stops at the `release` stage with a
pull failure and a diagnostics record. That is the workflow behaving correctly.

## What the suite establishes, and what it cannot

It establishes that the descriptor agrees with the chart, `lib.sh`, the model
source record, the runtime package, and the single-replica descriptor; that every
weakening of the descriptor is refused; that the capacity figures are the chart's
resources times the replica counts and that each shortfall is found, named, and
reported before an install; that the collected facts are held per pod rather than
per controller summary; that a failed request, an unplanned request set,
inconsistent token counts, mock identity, an uncorrelated request, a doubly
claimed request, a record from an unknown pod, a non-completion record, and a
single-replica distribution each stop the run at a named stage; that cleanup is
held to the ownership boundary; that the record carries no generated text and
names its own limitations; and that the script preflights before it installs,
asserts before it tears down, creates one bounded unprivileged driver that never
prints a body, and removes nothing it does not own.

It establishes **nothing** about whether a release installs with two replicas,
whether both load the model inside their budgets, whether `kube-proxy`
distributes anything, or whether a teardown leaves no residue. Those are runtime
questions and only an authorized run answers them.

## What independent review found, and what changed

The change was reviewed independently before it was pushed. It found no defect in
the certification's correctness — nothing that would let a run be certified on
weaker evidence than it claims, and no error in the capacity arithmetic or in the
four shell-to-Python seams, which is where the previous PR's defects had been. It
found three things that were wrong anyway, and all three are fixed:

**The driver's completion was waited on with a call that cannot see a failure.**
`kubectl wait --for=condition=complete job/…` watches one condition becoming
true and has no notion of "finished either way". The driver is `backoffLimit: 0`
and `restartPolicy: Never`, so any crash of its shell fails the Job in the first
second — and that call would have blocked for the full 1,800,000 ms distribution
budget before reporting it. Half an hour to report a failure that already
happened is a hang with a timeout on it, not the bounded failure the acceptance
criteria ask for. It is now a poll for **both** terminal conditions, which also
covers the Job's own `activeDeadlineSeconds`, and a query that cannot be answered
fails the run immediately rather than being read as a Job still running.

**A driver Job that would not go could have been misdiagnosed as release
residue.** The removal swallowed its own status with `|| true` and cleared
`driver_created` regardless. The Job deliberately carries this release's instance
label — that is what makes the release's own NetworkPolicy describe it — and that
is the label the residue check after the uninstall selects on, with `jobs` in its
resource list. A delete accepted but not finished would have been counted as an
object of the *release* surviving its own uninstall, failing the run with the
wrong diagnosis. The removal now returns its status, clears `driver_created` only
when the object is actually gone, and is refused on the success path; only the
already-failing trap continues past it, and it warns rather than going quiet.

**Three documents rounded a capacity figure down by a percent.** The descriptor's
`requestedMemoryBytes` is 2,320 MiB and the prose said "2.25 GiB". The descriptor
itself was correct — the architecture suite already derives that number from the
chart — but nothing compared prose to data. The figures are now stated in
mebibytes and a test derives all three from the descriptor and requires them in
the procedure document, this record, and the changelog.

Fixing the second of those produced a fourth finding, from the repository's own
lifecycle safety suite rather than from a person: the first version of the fix
wrote `remove_driver || inferops::fail "…kubectl delete job…"`, and a line that
both removes an object and prints the command to remove it is a line that suite
reads as an unscoped deletion. It is right to. The deletion rules have no message
exemption — the helm rules do — and widening one to accommodate a message would
have been weakening a deletion rule for convenience, so the messages were
reworded to name the object and its namespace without spelling a command, and a
test holds them there.

Review also prompted one correction found while it ran:
[the ownership document](../../architecture/resource-ownership.md) still said
**two** procedures install and uninstall this release, and said nothing about the
transient `batch/v1` Job this workflow creates. Both are now stated, including
why that Job is deliberately not a row in any ownership table.

## Deferred, and depended on

- **An InferOps API image.** `platform-api-container-image` is `planned` in the
  ownership inventory and no Dockerfile is committed. Until one exists, neither
  Kubernetes certification can complete.
- **Runtime-tier multi-replica proof.** Not attempted, and not because it was
  forgotten: `llama-server` publishes no per-request, pod-aware record, and the
  two ways to invent one — a pod identity in the API's contract, or an inference
  from a desired replica count — are both refused by this PR's boundary. A future
  story that wants it needs a mechanism decision first.
- **Load, autoscaling, routing, and failure experiments.** Out of this PR's
  boundary by name, and out of `V1-S3-006` entirely.

## Acceptance criteria

### This PR

| Criterion | Status |
|---|---|
| The approved certification profile requests at least two real serving replicas | Met. `release.apiReplicas` is 2 and a lower value is refused at load and again before `helm install` |
| Every expected replica reaches actual model readiness within a bounded timeout | Met as a check. Per-pod readiness is collected and each pod is held to the rollout budget; API readiness is false unless its adapter is able. Unexecuted |
| A bounded request set succeeds through the Kubernetes Service | Met as a check. Ten requests, each held to status 200 with real adapter kind and consistent runtime-derived counts. Unexecuted |
| Non-sensitive correlation evidence proves successful requests reached at least two distinct serving replicas | Met as a check, for the platform API tier, using `inferops.request.id` and `k8s.pod.name` from the API's own structured logs. Unexecuted |
| Evidence records requested/ready counts, per-replica readiness, request distribution, versions, resources, time window, and limitations | Met. Every member is in the record and a test reads each one |
| Insufficient capacity, single-replica fallback, missing correlation, or mock capability causes a clear non-zero failure | Met. Exit 5 for capacity; exit 4 for the others; each with a named stage and a test |
| Cleanup is safe, scoped, repeatable, and recorded | Met. The driver and the release are removed; the namespace, the claim, the prerequisites, and the cluster are not; the outcome is asserted and written into the record |
| Evidence is labelled local real Kubernetes and does not imply production high availability or autoscaling | Met. The label is the descriptor's and the five limitations are copied into every record |

### The parent story, V1-S3-006

| Criterion | Status |
|---|---|
| Workflow provisions prerequisites and installs Helm release | Implemented in both PRs. Unexecuted |
| It waits for actual model readiness | Implemented in both PRs. Unexecuted |
| A real model-generated response returns through Kubernetes Service | Implemented in both PRs. Unexecuted |
| Model/runtime/workload versions are recorded | Implemented. Unexecuted |
| Failure is bounded and diagnostic | Implemented. Every wait carries a descriptor budget and every failure names a stage |
| Evidence is labelled local real Kubernetes | Implemented |
| The approved multi-replica profile supports at least two real serving replicas, and both become ready | Implemented as a check, for the API tier. Unexecuted |
| Requests are proven to reach multiple serving replicas using non-sensitive correlation evidence | Implemented as a check, for the API tier. Unexecuted |
| Multi-replica evidence records the replica count, per-replica readiness, request distribution, and applicable local resource limitations | Implemented |

**The story's evidence — single- and multi-replica Kubernetes C2 certification
records — does not exist.** Both workflows are committed, validated, and
unexecuted, and both are blocked on the same unpublished API image. No claim in
the matrix moves.
