# V1-S3-009-PR1 validation — the Kubernetes troubleshooting and cleanup guide

Change: a symptom-oriented troubleshooting and cleanup page for the Kubernetes
path, at
[`docs/environment/kubernetes-troubleshooting.md`](../../environment/kubernetes-troubleshooting.md),
and a suite that holds it to the repository it describes. This record is what was
run, what it found, and what none of it supports.

**Evidence class.** Everything asserted here is `local-static`: files read,
compared, rendered, formatted, linted, type-checked, and driven through a test
suite that contacts nothing. **No cluster was contacted.** No `kind` cluster was
created, no `terraform apply` ran, no Helm release was installed, upgraded,
broken, rolled back, or uninstalled, no port-forward was opened, no probe was
sent, no model byte was read, and no completion was generated. No claim in
[the matrix](../../testing/claim-test-matrix.md) gains evidence from this change.

**This is a documentation change.** No product behaviour was modified. The chart,
the values, the environment scripts, the Terraform configuration, and every tool
under `tools/` are byte-for-byte unchanged by this PR.

## What the change is

**A page organised by observation rather than by component.** When somebody
arrives at a broken cluster the only thing they have is what they saw, so every
entry names the symptom first, then the check that distinguishes the plausible
causes, then the recovery. It covers cluster and context, scheduling and
resources and out-of-memory, the model cache claim and its storage, slow and
failed model loads, probes, Service and network, the API's and the runtime's
logs, the telemetry scrape, the Helm release, Terraform state and ownership,
upgrade and rollback, and cleanup.

**The status is stated before the content, and it is two different statuses.**
The cluster half of the page was executed and evidenced — `preflight`,
`cluster-up`, `cluster-verify`, `smoke`, `cluster-down`, `verify-clean`, twice
from a clean state to a clean state — in
[the cluster smoke evidence](v1-s0-002-pr2-cluster-smoke.md) and
[the cluster lifecycle result](v1-s3-001-pr1-cluster-lifecycle.md). The release
half **has never been run by anybody, on any cluster**, for the one reason three
other documents already open with: `platform-api-container-image` is `planned` in
[the ownership inventory](../../architecture/resource-ownership.v1alpha1.json),
no `Dockerfile` is committed anywhere in this repository, and a release whose API
image does not resolve never becomes ready. Every release symptom on the page is
derived from the chart, the committed render, the descriptors, the scripts, and
the tooling, and the page says so in its own first paragraph rather than in a
footnote.

**Cleanup is four operations with four blast radii, and they are not a
sequence.** The acceptance criterion is the separation, so the page separates
them under four headings and states what each one leaves behind:

| | Reaches | Leaves |
|---|---|---|
| `helm uninstall` | the release | the namespace, its metadata, and the model cache |
| `terraform-prerequisites.sh destroy --confirm` | the namespace and the claim, cascading | the cluster |
| model cache deletion | in-cluster: **this is the operation above**. On the host: `model_acquisition clean --confirm`, which reaches nothing in a cluster | everything else |
| `cluster-down.sh` | the cluster, the kubeconfig, the context | the shared `kind` network and, unless `--purge-node-image`, the cached node image |

The third row is the one that needed writing down rather than inventing: **there
is no separate in-cluster cache deletion**, because the weights live inside the
Terraform-owned claim and reclaiming them *is* the Terraform destroy. Inventing a
third command would have been inventing a second owner for one resource.

**Two refusals are quoted as refusals rather than as errors.** The Terraform
wrapper refuses a destroy without `--confirm`, and refuses a destroy while a
release is still installed — because the cascade would take the release with it
and leave Helm's record claiming it exists. Both are guards doing their job and
the page says the recovery is to satisfy the precondition, never to bypass it.

**One section tells the reader to stop investigating.** The chart renders four
`NetworkPolicy` objects starting from a default deny, and on `kindnetd` none of
them is enforced. That was measured on 2026-09-06 and recorded in
[the enforcement result](../security/v1-s3-004-pr1-network-policy-enforcement.md);
a connection that fails on this cluster is a Service, a selector, a probe, or a
port, and time spent on the policy is time not spent on the fault.

**The distinction the page refuses to blur** is the one both certification
workflows are built on: a rollout Kubernetes reports as successful, a Service
selecting nothing, and a runtime that loaded no weights are indistinguishable
from outside until something asks for a completion. `helm rollback` returning
zero says a revision was recorded and nothing more, and `progress deadline
exceeded` is a deadline rather than a statement about health — a timeout cannot
tell a broken container from a model load this project has measured between
133,515 ms and 358,735 ms.

## What the suite checks

[`tests/architecture/test_kubernetes_troubleshooting.py`](../../../tests/architecture/test_kubernetes_troubleshooting.py)
holds the page to the files that own what it quotes, in nine groups:

1. **Commands.** Every `python -m tools.<module>` the page prints names a module
   that exists and either a subcommand its parser accepts — read out of the AST
   rather than by executing a parser that reads committed JSON at import — or a
   path that is really in the checkout. Every repository-tool sample runs under
   `uv run --locked`.
2. **Scripts.** Every `scripts/environment/*.sh` named exists, the five a
   diagnosis or a cleanup decision depends on are all named, and a printed
   `terraform destroy` carries `--confirm`.
3. **Targets.** The cluster name, context, kubeconfig path, both namespaces, the
   release name, the chart path, the project label selector, the kind version,
   and the node image tag and digest are compared against `lib.sh`, which is the
   one place they are defined. The context is derived there from the cluster
   name, so the suite expands the reference rather than copying the resolved
   string into itself.
4. **Numbers.** Service ports and types, every probe path, period, and failure
   threshold, both startup budgets and their ordering, both progress deadlines,
   every resource request and limit for all three containers, the claim's name
   and size defaults, the artifact's byte count, its revision, its in-claim path,
   the cache root, and the certification script's default forward port — each
   read from the record that owns it: the committed real render, `values.yaml`,
   the Terraform variables, `model-source.v1.json`, `lib.sh`, or the script
   itself. Every `.artifacts/` directory the page names is one a script actually
   writes.
5. **Exit codes.** The vocabulary table is compared against the `EXIT_*`
   constants both Kubernetes tools define, in both directions, and the page's
   attribution of `5` to `tools.helm_upgrade_rollback` alone is checked against
   the fact that the certification tool does not define it.
6. **Measurements.** Every model-load figure quoted must appear in the proof
   record the page attributes it to. The network-policy answer is checked against
   the experiment that produced it, and the four rendered policy objects the page
   calls inert are counted in the render.
7. **Links.** Every relative Markdown target outside a fenced block resolves,
   including this record and the suite itself.
8. **Sample safety.** No fenced block carries a token, header, password, auth,
   bearer, credential, `--server`, `--insecure-skip-tls-verify`, or `--force`
   flag; every fenced `kubectl` and `helm` command — including the ones split
   across continuation lines — names both `--kubeconfig` and a context flag; no
   sample deletes a namespace by hand, prunes the engine, or sweeps all
   namespaces; and every block containing an uninstall, a destroy, a teardown, or
   a confirmed clean is labelled destructive.
9. **Claims.** Seven sentences the page is not entitled to drop, the four cleanup
   headings, and the twelve section headings the parent story's coverage
   criterion names.

## Files changed

New:

- `docs/environment/kubernetes-troubleshooting.md` — the guide.
- `tests/architecture/test_kubernetes_troubleshooting.py` — 104 checks.
- `docs/proof/environment/v1-s3-009-pr1-validation.md` — this record.

Changed:

- `docs/testing/test-inventory.v1alpha1.json`, `docs/testing/test-inventory.md` —
  the new module inventoried, the counts corrected.
- `README.md` — a public entry point for the new page.
- `docs/serving/local-runtime-troubleshooting.md` — its Kubernetes exclusion now
  points at the page that covers it, instead of saying the path does not exist.
- `CHANGELOG.md`.

No file under `charts/`, `deploy/`, `infra/`, `scripts/`, `src/`, or `tools/` is
touched by this change.

## Validation performed

Every command below was run from the repository root on the reference host on
2026-09-09.

| Command | Result |
|---|---|
| `uv run --locked python -m pytest tests/architecture/test_kubernetes_troubleshooting.py -q` | 104 passed |
| `uv run --locked python -m pytest -q` | 7,205 passed, 29 skipped, 14 deselected |
| `uv run --locked python -m ruff check .` | `All checks passed!` |
| `uv run --locked python -m ruff format --check .` | `325 files already formatted` |
| `uv run --locked python -m mypy` | `Success: no issues found in 176 source files` |
| `uv run --locked python -m tools.workload_policy charts/inferops-llm/ci/rendered` | `ok 2 file(s) satisfy the workload policy`, exit `0` |
| `uv run --locked python -m tools.telemetry_collection charts/inferops-llm/ci/rendered` | `ok 2 file(s) satisfy the collection policy`, exit `0` |
| `uv run --locked python -m tools.helm_upgrade_rollback check` | descriptor accepted; `execution not started (offline descriptor validation only)`, exit `0` |
| `scripts/environment/terraform-prerequisites.sh check` | `format and validation passed. Nothing was contacted and no state was read.`, exit `0` |
| `helm lint charts/inferops-llm --values charts/inferops-llm/ci/real-values.yaml` | `1 chart(s) linted, 0 chart(s) failed`, exit `0` |
| `helm template inferops charts/inferops-llm --namespace inferops-platform --values charts/inferops-llm/ci/real-values.yaml` | rendered, and identical to the committed `real.expected.yaml` |
| `git diff --check` | no whitespace errors |

The two remaining documented commands could not be executed on this host, and
that is reported rather than glossed:

| Command | Why not |
|---|---|
| `scripts/environment/cluster-verify.sh` | refused with `'kind' is not on PATH`. `kind` is not installed here |
| `scripts/environment/verify-clean.sh` | the same refusal, for the same reason |

Both refusals are the guard the scripts are supposed to apply, and both name the
document that says how to install the missing tool. Neither was overridden.
`preflight.sh`, `cluster-up.sh`, `smoke.sh`, `cluster-down.sh`, `proof.sh`,
`helm-lifecycle.sh`, `kubernetes-certification.sh`,
`kubernetes-multi-replica-certification.sh`, and `helm-upgrade-rollback.sh` were
**not run**: the first four need `kind`, and the last five additionally need an
API image that does not exist.

## What was verified about the commands, and what was not

**Verified**: that every documented command names a module, subcommand, script,
or path that exists; that the four offline checks the page opens with run and
exit `0`; that the chart the page describes lints and renders and that its render
is the committed one; that the Terraform configuration the page describes
formats, initialises, and validates; and that the two cluster-dependent read-only
scripts refuse cleanly rather than misbehaving when their tool is absent.

**Not verified**: that any of the recoveries recovers. Every `helm install`,
`helm upgrade`, `helm rollback`, `helm uninstall`, `terraform apply`,
`terraform destroy`, `kubectl port-forward`, `kubectl logs` against a real pod,
probe, scrape, and completion the page describes is unexecuted — by this change
and by anybody. A described recovery and an executed one are different kinds of
statement, and
[the certification levels](../../testing/certification.md) are where that
distinction is defined.

## Limitations

- **One host, one platform.** The executed evidence behind this page is from one
  Windows host with a container desktop application providing the engine. Nothing
  here is a statement about Linux or macOS.
- **One node.** Every capacity statement is about a single-node `kind` cluster.
- **The network policy answer is from a near-neighbour cluster.** The enforcement
  experiment ran on Docker Desktop's Kubernetes with the same `kindnetd`
  implementation, not on the accepted `inferops-dev` cluster. What transfers is
  the plugin; the cluster is not the accepted one, and the record it comes from
  says so before it says anything else.
- **The measured model loads are host-local, not in-cluster.** Every figure the
  page quotes was measured outside Kubernetes. No model has been loaded inside a
  pod, so the probe budgets the page explains are budgets rather than
  observations.
- **A static reading of a document is not a diagnosis.** The suite establishes
  that the page has not drifted from the repository. It establishes nothing about
  whether following the page fixes anything.
- **The suite cannot read prose.** A symptom row whose description has drifted
  from the behaviour it describes will not fail a check, in the same way the
  ownership document's own tests cannot read its handoff text.

## Acceptance criteria

Parent story `V1-S3-009` — Document Kubernetes Troubleshooting and Cleanup:

| Criterion | Status |
|---|---|
| Covers scheduling, OOM, model load, probes, service, telemetry, Helm, Terraform, and storage | **Met.** Each is a section, and the section headings are asserted |
| Cleanup distinguishes workload, prerequisites, cache, and cluster | **Met.** Four headings, four blast radii, stated not to be a sequence, and asserted |
| Commands are safe and verified | **Met as far as this host permits.** Every command exists and is scoped; the offline ones were executed and exit `0`; the two cluster-dependent read-only scripts refused because `kind` is absent, and that is recorded above rather than claimed as a pass |

Story evidence — "Documentation command-check log": this record's validation
table is it.
