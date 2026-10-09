# V2-S4-005-PR2 validation

Status: **one reading of the Service endpoints of one cluster is committed. On
2026-10-09, on the `docker-desktop` provider, with the two-replica release
installed, the record states two Ready endpoints of two for the API Service and
two of two for the runtime Service. The result is `OBSERVED`. This is one
reading at evidence level C2, and it registers no claim.** No collector code,
tool code, chart file, or contract was changed. One suite gains one test, which
holds the committed reading.

> [!IMPORTANT]
> **This change supplies evidence that an earlier change owed, and the record
> says so.** [`V2-S4-004-PR1`](v2-s4-004-pr1-validation.md) added the collector
> and seven synthetic cases, and its record states that no Service and no
> EndpointSlice of a cluster was read. A review of the sprint on 2026-10-09
> reported that the endpoint observation sample was missing; it was reported to
> the author, and no file in this repository records that review. The earlier
> record is not edited.
>
> **The reading is what Kubernetes published. It is not what a caller
> received.** The run sent no request to the release. It deleted and evicted no
> pod, and it injected no fault.

| Property | Value |
|---|---|
| Date | 2026-10-09 |
| Base | `25f2cfbfe587e0e0c76ceb519cb90f6ef0e09810`, the merge of pull request #133 |
| Branch | `fix/v2-s4-live-service-endpoint-evidence` |
| Executing commit | `25f2cfbfe587e0e0c76ceb519cb90f6ef0e09810`. The working tree was clean when the run started and when the endpoint read started |
| Host | One Windows workstation, Git Bash; Python 3.12.12 from `uv` 0.9.16; Helm `v3.19.0`; Terraform `v1.15.8`; Docker engine `29.8.1`; `kubectl` client `v1.36.1` |
| Cluster | `docker-desktop`, one node, server `v1.36.1`. Before the run it held five namespaces of its own and no custom resource definition |
| Evidence level | C2 for the reading and for the two capacity readings: each is a read of a running cluster. Nothing here is representative evidence |
| Claim effect | None. No claim, ledger, register row, dashboard row, or evidence-index entry was added or changed |

## What was observed

| Question | Answer |
|---|---|
| What exactly was observed | The Services of the release `inferops` and the EndpointSlices of the namespace `inferops-release`, read once each with `kubectl get`, by [`scripts/environment/service-endpoint-state.sh`](../../../scripts/environment/service-endpoint-state.sh) |
| What produced the record | [`tools/service_endpoint_state`](../../../tools/service_endpoint_state/core.py), from the two reads. Neither the script nor the tool was changed for this run |
| The environment | The `docker-desktop` provider: one cluster, one node, on one workstation |
| The time and the revision | The reads are between `2026-10-09T14:33:15Z` and `2026-10-09T14:33:16Z` on the collecting host's clock. The collector ran at commit `25f2cfbf`, and the controller reported `25f2cfbf` as the revision it read, `Synced` and `Healthy` |
| What it establishes | At that time that cluster published, for each of the two Services, one `IPv4` slice with two endpoints, both Ready, none terminating. Those endpoints were the two pods of each Deployment |
| What it does not establish | See [the last section](#what-this-does-not-establish) |

| Tier | Service | Endpoints | Ready | Not Ready | Terminating | Ready pods |
|---|---|---|---|---|---|---|
| `platform-api` | `inferops-inferops-llm` | 2 | 2 | 0 | 0 | `inferops-inferops-llm-b5fd5846f-m87hp`, `inferops-inferops-llm-b5fd5846f-rv46m` |
| `serving-runtime` | `inferops-inferops-llm-runtime` | 2 | 2 | 0 | 0 | `inferops-inferops-llm-runtime-79846f98f6-7kms9`, `inferops-inferops-llm-runtime-79846f98f6-gc7pq` |

Each of the 10 rules of the record is `held`.

**The identities were compared with the pods, without the tool.** The driver
read the pods of the release before the endpoint read and after it. A script
that is not committed read `pods-before.json`, `pods-after.json`, and the
record. For each tier, the set of pod name and pod UID that the record states as
Ready is the set of pods of that component whose `Ready` condition is `True` and
that are not being deleted, in both reads. The transcript also prints each pod
with its UID, its component, and its `Ready` condition.

**The topology and the images of the release, as the cluster reported them.**

| Deployment | Replicas | Ready | Image |
|---|---|---|---|
| `inferops-inferops-llm` | 2 | 2 | `localhost/inferops-api@sha256:244251f76e5959c58e52689337298a24af46b34d8fd36b097cb638671eccda56`, built on this host at the executing commit |
| `inferops-inferops-llm-runtime` | 2 | 2 | `ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384` |
| `inferops-inferops-llm-collector` | 1 | 1 | `prom/prometheus@sha256:63805ebb8d2b3920190daf1cb14a60871b16fd38bed42b857a3182bc621f4996` |

No container of the five pods had restarted when the pods were read.

## What is committed

| Path | What it is |
|---|---|
| [`v2-s4-005-pr2-service-endpoint-state-run-1/`](v2-s4-005-pr2-service-endpoint-state-run-1/record.v1alpha1.json) | The collection: `services.json`, `endpointslices.json`, `run.json`, and `record.v1alpha1.json`, as the collector wrote them, with LF line ends. Beside them, three reads that the driver made: `pods-before.json`, `pods-after.json`, and `deployments.json` |
| [`v2-s4-005-pr2-service-endpoint-state-run-1-transcript.txt`](v2-s4-005-pr2-service-endpoint-state-run-1-transcript.txt) | What the three invocations of the driver printed |
| [`v2-s4-005-pr2-service-endpoint-state-run-driver.txt`](v2-s4-005-pr2-service-endpoint-state-run-driver.txt) | The driver, as it ran. Its SHA-256 is in the transcript: `4f1ca97e6df4bacee757e3cd92903b0a2cb7f7a9cf14544923355b4243a704cd` |
| [`v2-s4-005-pr2-capacity-preflight-run-1-before-install/`](v2-s4-005-pr2-capacity-preflight-run-1-before-install/record.v1alpha1.json) | The capacity gate's reading before anything was installed |
| [`v2-s4-005-pr2-capacity-preflight-run-1-before-apply/`](v2-s4-005-pr2-capacity-preflight-run-1-before-apply/record.v1alpha1.json) | The capacity gate's reading before the Application was applied |

**No observation output was edited by hand.** Each kept file is the file that a
script wrote, copied with carriage returns removed. The transcript is redacted
in two ways, and it says so in its first lines: terminal colour codes are
removed, and the absolute path of the checkout is written as `<repository>`.

`python -m tools.service_endpoint_state --check` builds the record again from
the committed reads and compares it. The driver did the same once in the run,
and the two records were equal.

## What the run did, in order

One attempt was made, and it is the committed one. No earlier attempt of this
change read a cluster.

| Step | What happened |
|---|---|
| Start | `2026-10-09T14:23:24Z`. The executing commit and the remote `main` were one commit. The tree was clean |
| Capacity gate, before any install | `ACCEPTED`. 12 rules `held`. The claim rule is `not-observed`, because the namespace did not exist |
| Images | The API image was built at the executing commit and loaded into the node. The model seed image was built from the local cache and loaded. No model was downloaded |
| Prerequisites | Terraform created the release namespace and the model cache claim |
| Preparation release | One Helm release with the V1 real values, one API replica and one runtime replica, filled the claim from the seed image, and was uninstalled. It left no object. It is not the release that was observed |
| Controller | The bootstrap procedure installed and verified the controller |
| Capacity gate, before the apply | `ACCEPTED`. Each of the 13 rules `held`. 9,865,003,008 bytes of memory limits required and 10,126,585,856 available |
| Apply | The Application procedure applied the project and the Application, with the API image digest as its one parameter |
| Rollouts | Both `kubectl rollout status` commands reported success by `14:32:13Z` |
| Controller's report | Revision `25f2cfbf`, `Synced`, `Healthy`, operation `Succeeded` |
| Pods read | `14:32:56Z` to `14:33:15Z`: five pods, each Ready |
| Endpoint read | `14:33:15Z` to `14:33:16Z`. `OBSERVED` |
| Pods read again | The same five pods, each Ready |
| Cleanup | The Application and what it applied, the controller, and the prerequisites were removed. The namespaces and the custom resource definitions after the run are the ones before it, and no persistent volume is left. Ended `14:35:16Z` |

**The chart with two budgets was installed for the first time here.** The
transcript lists both PodDisruptionBudget objects, each with `minAvailable` 1
and one allowed disruption. No eviction was requested, so that listing
establishes nothing about what a budget refuses.

## Validation

Each command ran on the host of the table above, on the working tree of the
first commit.

| Command | Result |
|---|---|
| `uv run --locked python -m tools.service_endpoint_state --check` | `PASSED: 8 committed collection(s)`. It was 7 |
| `uv run --locked python -m tools.capacity_preflight --check` | `PASSED: 9 committed collection(s)`. It was 7 |
| `uv run --locked ruff check .` | No finding |
| `uv run --locked ruff format --check .` | 688 files already formatted |
| `uv run --locked python -m mypy` | No issue in 375 source files |
| `uv run --locked python -m pytest tests/domain/test_service_endpoint_state.py -q` | 111 passed. The suite held 110 tests at the base |
| `uv run --locked python -m pytest tests/domain/test_service_endpoint_state.py tests/architecture/test_service_endpoint_state_collector.py tests/domain/test_capacity_preflight.py tests/architecture/test_capacity_preflight_collector.py tests/architecture/test_argocd_bootstrap.py tests/architecture/test_argocd_application.py tests/testing/test_document_links.py tests/testing/test_test_inventory.py -q`, before the suite was edited | 2,167 passed and 2 failed. Both failures were tests of the endpoint suite that state the committed collections as the seven cases. They are the two tests that this change edits |
| The same command, after the edit | 2,170 passed, none skipped |
| `uv run --locked python -m tools.baseline_profile --check`, `tools.generated_release --check`, `tools.gitops_desired_state --check`, `tools.runtime_model_cache --check`, `tools.experiment_freeze --check`, `tools.experiment_e01 --check`, `tools.evidence_index --check`, `tools.evidence_index --gate`, and `tools.proof_dashboard --check` | Exit status 0 for each |
| `git diff --check` against the base | No whitespace error |

**Not run at the first commit.** The whole default lane, which runs at the
second commit. `gitleaks` is not installed on this host, so no secret scan ran.
Hosted CI was not read: no pull request existed. No Helm command of the chart
suite ran here beyond the suites above, because no chart file changed.

## What stayed as it was

- **The collector, the tool, and the chart.** The diff holds pages, evidence
  files, and one suite. `tests/domain/test_service_endpoint_state.py` gains one
  test that holds the committed reading, and two of its tests now count that
  reading among the committed collections. No assertion about a synthetic case
  changed.
- **The seven synthetic cases and the earlier validation record of the
  collector.** Not edited.
- **Released V1 evidence and history, the first experiment, and the other
  evidence of this sprint.** No such file is in the diff.

## Privacy and publicability

The diff was read for private material.

- The raw reads hold pod and Service addresses of one local cluster, the node
  name `desktop-control-plane`, the node's cluster address, and the node's
  kernel string. The capacity reads hold the node's allocatable figures and the
  engine's processor count and memory. Each describes one local cluster on one
  workstation.
- The capacity records name the kubeconfig context `docker-desktop`, which is
  the provider's fixed name and holds no account identifier. The endpoint
  record names no context.
- The transcript holds no path of the workstation: the checkout's path is
  written as `<repository>`. It names two Secret objects of the controller by
  name, and it prints no value of one.
- No credential, token, kubeconfig content, model artifact, prompt, or
  response is in the diff. The run sent no request to the release.
- No planning text and no identifier of a later change is in the diff.

## Limits of the driver

- It was written for this one run. It was copied to a directory that Git
  ignores before it ran, and it is committed after the run, as it ran.
- It has no cleanup on interruption. A phase that stops leaves the cluster as
  it is, and the operator runs `down`.
- It installs the chart twice: once as the preparation release, and once
  through the Application.
- It reads the endpoint state about one minute after the second rollout
  reported success. It does not show how long the endpoints took to become
  Ready, and it sampled nothing in between.
- It keeps the two capacity collections in the ignored directory until the
  `collect` phase, because the gate refuses a working tree that differs from
  its commit.

## What this does not establish

- **That a caller was answered.** No request was sent to the release, through
  a Service or to a pod.
- **Availability, reliability, high availability, or zero downtime.** The
  record is one reading. It holds no transition and no period.
- **That requests are routed to both endpoints, or routed correctly.**
- **Latency, throughput, or compliance with an objective.**
- **What happens when a pod is deleted, evicted, or replaced, or when a node is
  lost.** No fault was injected, and the cluster has one node.
- **That a budget refuses an eviction.** None was requested.
- **Anything about another provider, another cluster, or another release.**
  One local cluster was read.
- **That the host is qualified for the release.** Two capacity readings were
  accepted and one install succeeded, once.
- **A refusal of the collector against an API server.** The reading is
  `OBSERVED`. Each refusal is shown by a synthetic case.
