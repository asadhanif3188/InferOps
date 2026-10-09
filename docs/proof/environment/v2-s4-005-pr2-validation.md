# V2-S4-005-PR2 validation

Status: **one reading of the Service endpoints of one cluster is committed. On
2026-10-09, on the `docker-desktop` provider, with the two-replica release
installed, the record states two Ready endpoints of two for the API Service and
two of two for the runtime Service. The result is `OBSERVED`. This is one
reading at evidence level C2, and it registers no claim.** No collector code,
tool code, chart file, or contract was changed. One suite gains one test, which
holds the committed reading. An independent review found that the first commit
graded two capacity readings at a level that their own records refuse, stated a
download and a cleanup more strongly than the transcript shows, and left six
statements elsewhere stale: see
[what the independent review found](#what-the-independent-review-found).

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
| Evidence level | C2 for the endpoint reading: the pods behind the endpoints ran the API image built at the executing commit, the pinned runtime image, and the pinned model, on a real cluster. The two capacity readings are assigned no level: a capacity record states that it does not establish one. Nothing here is representative evidence |
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
| [`v2-s4-005-pr2-service-endpoint-state-run-1-transcript.txt`](v2-s4-005-pr2-service-endpoint-state-run-1-transcript.txt) | What the three invocations of the driver printed, with four lines at its head, one line that names each phase, and one `driver exit` line after each phase. The command that ran each phase added those lines, and that command is not committed |
| [`v2-s4-005-pr2-service-endpoint-state-run-driver.txt`](v2-s4-005-pr2-service-endpoint-state-run-driver.txt) | The driver, as it ran. Its SHA-256 is in the transcript: `4f1ca97e6df4bacee757e3cd92903b0a2cb7f7a9cf14544923355b4243a704cd` |
| [`v2-s4-005-pr2-capacity-preflight-run-1-before-install/`](v2-s4-005-pr2-capacity-preflight-run-1-before-install/record.v1alpha1.json) | The capacity gate's reading before anything was installed |
| [`v2-s4-005-pr2-capacity-gate-before-apply/`](v2-s4-005-pr2-capacity-gate-before-apply/record.v1alpha1.json) | The capacity gate's reading before the Application was applied: its record, its header, its footprint, and five of its six reads. Its read of every pod of the cluster is not committed. See below |

**No observation output was edited by hand.** Each kept file is the file that a
script wrote, copied with carriage returns removed. The transcript is redacted,
and it says how in its first lines: terminal colour codes are removed, the
absolute path of the checkout is written as `<repository>`, and carriage returns
and spaces at the end of a line are removed.

**Two kinds of digest in the transcript need a note.** The digest of the driver
is of its bytes with LF, and the attribute file pins the committed driver to
LF. The digests of the four Python files are of this host's working tree, which
holds them with CRLF. They are not the digests of the committed bytes, and a
host that checks out LF does not reproduce them. The digests of the scripts,
the manifests, and the chart file are of LF bytes.

**One read of the second capacity reading is not committed, and so its record
cannot be built again from this repository.** That read, `pods.json`, holds the
whole specification of every pod of the cluster, with the four pods of the
controller. A container of the controller mounts paths under a home directory,
and the repository's publication check refuses a committed file that holds such
a path. The check was not changed, and the read was not edited. The file is
left out. Its SHA-256, with LF, is
`d389914d8600534261ed852d9a4c77ee7c96fc4940d0ce45a09ab92f21af759d`. The record
that the gate built from it is committed as the gate wrote it, in a directory
whose name the capacity tool's check does not match. So `--check` does not hold
that record. The first capacity reading is committed whole, and `--check` holds
it.

`python -m tools.service_endpoint_state --check` builds the record again from
the committed reads and compares it. The driver did the same once in the run,
and the two records were equal.

## What the run did, in order

One attempt was made, and it is the committed one. No earlier attempt of this
change read a cluster. That is the author's statement: no committed file can
show the absence of another attempt. The first step of the transcript shows a
cluster with no release namespace and no controller namespace.

**Whether a model was downloaded is not shown.** The run was written to
download none: the preparation release fills the claim from the seed image. The
Application's release then runs the chart's acquisition hook with the
`download` source against the filled claim. The chart's hook is written to
acquire nothing when the artifact is present and verified. The transcript keeps
the output of neither hook, so neither statement is observed here.

| Step | What happened |
|---|---|
| Start | `2026-10-09T14:23:24Z`. The executing commit and the remote `main` were one commit. The tree was clean |
| Capacity gate, before any install | `ACCEPTED`. 12 rules `held`. The claim rule is `not-observed`, because the namespace did not exist |
| Images | The API image was built at the executing commit and loaded into the node. The model seed image was built from an artifact that the host already held, and loaded. Both builds read base-image metadata from a registry |
| Prerequisites | Terraform created the release namespace and the model cache claim |
| Preparation release | One Helm release, with the V1 real values, the API image digest, the seed image as the acquisition source, and one override that no committed file holds: `model.acquisition.resources.limits.memory=2Gi`. It ran one API replica and one runtime replica, and was uninstalled. A query of eleven kinds by the instance label then returned nothing, and the claim stayed. It is not the release that was observed. The capacity gate reads the footprint of the two-replica release, so it did not evaluate this release |
| Controller | The bootstrap procedure installed and verified the controller |
| Capacity gate, before the apply | `ACCEPTED`. Each of the 13 rules `held`. 9,865,003,008 bytes of memory limits required and 10,126,585,856 available |
| Apply | The Application procedure applied the project and the Application, with the API image digest as its one parameter |
| Rollouts | Both `kubectl rollout status` commands reported success by `14:32:13Z` |
| Controller's report | Revision `25f2cfbf`, `Synced`, `Healthy`, operation `Succeeded` |
| Pods read | Between `14:32:56Z` and `14:33:15Z`. The read has no time of its own. Five pods, each Ready |
| Endpoint read | `14:33:15Z` to `14:33:16Z`. `OBSERVED` |
| Pods read again | The same five names and UIDs, each Ready. The two reads differ in the resource version of the two API pods and in one more address of their node |
| Cleanup | The Application and what it applied, the controller, and the prerequisites were removed. The namespaces and the custom resource definitions after the run are the ones before it, and no persistent volume is left. The API image and the model seed image stay in the node's image store, and no procedure of this project removes them. Ended `14:35:16Z` |

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
| `uv run --locked python -m tools.capacity_preflight --check` | `PASSED: 9 committed collection(s)` at the first commit, which held both readings whole. It was 7 |
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

## What the independent review found

Two reviewers read the first commit. Neither was given this record's
conclusions. One compared each statement with the committed files. One read
every evidence file for material that must not be public, and for a sign that a
file was edited after the run. **Neither found a credential, a Secret value, a
path of the workstation, or an edited read.** One rebuilt the transcript from
the uncommitted logs and compared each raw read with the file the run wrote:
each is the same, with carriage returns removed. Both rebuilt the record from
the committed reads.

### What the first commit said, and what is true

- **It graded the two capacity readings at C2.** A capacity record states that
  it does not establish an evidence level, and the change that added the gate
  assigned its reading none. The first of the two readings read nine pods of
  the cluster's own system. This record now assigns them no level. The endpoint
  reading stays at C2, and the reason is stated: the pods behind the endpoints
  ran the pinned images and the pinned model. "A read of a running cluster" was
  not that reason.
- **"No model was downloaded" was not shown.** The transcript keeps the output
  of neither acquisition hook, and the Application's hook runs with the
  `download` source. This record now says what the run was written to do, and
  that it was not observed.
- **"Removes what it installed" was too strong.** The two loaded images stay in
  the node's image store. The comparison after the run reads namespaces, custom
  resource definitions, labelled objects, claims, and persistent volumes.
- **The preparation release was described as the V1 real values.** It also took
  an override of the hook's memory limit that no committed file holds, and the
  capacity gate did not evaluate it.
- **"It left no object" rested on one printed line.** The row now says what was
  queried.
- **The transcript was said to be changed in two ways.** Spaces at the end of a
  line were removed too, and ten lines were added by the command that ran each
  phase. The transcript's first lines and this record say so.
- **The digests of four Python files in the transcript are of CRLF bytes.**
  This record says so. The driver is now pinned to LF.
- **The privacy section named less than the files hold.** It now names the
  node's identifiers, the image store, the pod specifications of the whole
  cluster, the annotations, and the local time.
- **The time of the pod read was stated as a range that it was read "from" and
  "to".** The read has no time of its own.
- **Six statements elsewhere were stale.** The budgets page, the architecture
  index, the chart's page, both ownership inventory files, and the name and the
  text of one test of the chart suite each said that no release that renders a
  budget was installed, or that no cluster has held one. One cluster held both
  for one run. Each now says that, and that no eviction was requested. The row
  of the inventory stays `planned` and cites no evidence: the run did not test
  a budget.
- **The suite's own text was stale.** The module of the endpoint suite said
  that every collection is written by the suite and that no record states what
  a cluster did. The inventory's note said the same. Both are corrected.
- **The new test said that the record "is what that cluster published".** It
  holds that the record is what the tool gives for the committed reads, and
  that those reads agree with each other. It now says that, and it asserts the
  absence of each kind of address that the reads hold.

### What the default lane found after the review

- **A publication check refused one raw read.** The read of every pod, in the
  second capacity reading, holds container paths under a home directory of the
  controller's image. The check reads each committed file for a personal path,
  and it has no exception. The check is right to have none. The file is left
  out, and "What is committed" states the cost.
- **A wording check refused one word of this record**, in the list of what the
  reading does not establish. The line is reworded.
- **One test of an unrelated suite failed once and passed alone.** It moves a
  file aside on this host's file system, and the move was refused once.

### Noted, and not changed

- **The driver is committed as it ran.** Its header is wrong in two places, and
  "Limits of the driver" states them.
- **`down` has no check of its own.** Each procedure that it calls verifies the
  target.
- **No committed file shows that only one attempt was made.**
- **The capacity page keeps the heading "The one committed reading"** for the
  section about the first reading. An earlier record links to it. A section
  above it states the two later readings.
- **Earlier evidence directories of this kind are not pinned to LF.** Their
  checks remove carriage returns before they compare.

## Validation at the second commit

Each command ran on the same host, from the working tree that the second commit
holds.

| Command | Result |
|---|---|
| `uv run --locked ruff check .` | No finding |
| `uv run --locked ruff format --check .` | 688 files already formatted |
| `uv run --locked python -m mypy` | No issue in 375 source files |
| `uv run --locked python -m tools.service_endpoint_state --check` | `PASSED: 8 committed collection(s)` |
| `uv run --locked python -m tools.capacity_preflight --check` | `PASSED: 8 committed collection(s)`: the seven of the base, and the first reading of this run |
| `uv run --locked python -m pytest tests/security tests/testing/test_document_links.py tests/domain/test_service_endpoint_state.py tests/domain/test_capacity_preflight.py tests/architecture/test_helm_chart.py -q` | 2,040 passed |
| `uv run --locked python -m tools.baseline_profile --check`, `tools.generated_release --check`, `tools.gitops_desired_state --check`, `tools.experiment_freeze --check`, `tools.evidence_index --gate`, and `tools.proof_dashboard --check` | Exit status 0 for each |
| `uv run --locked python -m tools.experiment_freeze --changes docs/proof/experiments/v2-e01/freeze-r3.v1alpha1.json` | 30 material files differ, as at the base |
| `git diff --check` against the base | No whitespace error |

## The default lane

`uv run --locked python -m pytest -q` ran twice.

**The first run failed three tests**, on the tree with the corrections of the
review: 20,051 passed, 3 failed, 37 skipped, and 14 deselected, in 35 minutes.
"What the default lane found after the review" states each. Two were defects of
this change, and both are corrected. The third passed when it ran alone.

**The second run passed**, on the working tree of the second commit before this
section was written: 20,054 passed, 37 skipped, and 14 deselected, in 29
minutes. No test failed. The 37 skips are the ones of the earlier changes of
this sprint on this host.

This section and the section above are the one edit after that run. They change
this page only. The link suite ran again for this page afterwards.

**Not run.** `gitleaks` is not installed on this host, so no secret scan ran.
Hosted CI was not read: no pull request existed. The first commit of this
change does not pass the publication check, because it holds the file that the
second commit leaves out.

## What stayed as it was

- **The collector, the tool, and the chart's templates and values.** The diff
  holds pages, evidence files, the attribute file, and two suites. One sentence
  of the chart's page is corrected. `tests/domain/test_service_endpoint_state.py` gains one
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
  name `desktop-control-plane`, the node's cluster addresses in two address
  families, and the node's kernel string. Every address is in a private range.
- The capacity reads hold more about the node: its machine identifier, system
  identifier, and boot identifier, its operating system image and container
  runtime version, its pod address range, and the list of images in its image
  store, with the digests of images built on this host. They hold the node's
  allocatable figures and the engine's processor count and memory.
- The first capacity reading holds the whole specification of the nine pods
  of the cluster's own system. Those hold host paths of the node and paths of
  key files of the cluster's own components. They hold no key material and no
  value of a Secret. The first commit also held that read for the second
  reading, with the four pods of the controller, the names of its Secret
  objects, and one key name. The second commit leaves that file out.
- The reads of the release hold the applied configuration of each Deployment as
  an annotation, the tracking identifier that the controller writes, owner
  references, and image identifiers.
- The capacity records and the transcript name the kubeconfig context
  `docker-desktop`, which is the provider's fixed name and holds no account
  identifier. The endpoint record names no context.
- The transcript holds no path of the workstation: the checkout's path is
  written as `<repository>`. It names two Secret objects of the controller by
  name, and it prints no value of one. It prints one local time of the host,
  which shows its time zone, the identifiers of two local image builds, and the
  platform strings of the tools.
- A reviewer compared these with the evidence that earlier changes committed.
  The node's identifiers, its kernel string, a local time, and build links are
  in earlier files. The identifiers of this run's namespace and claim are not
  in an earlier file. The pod specifications of the controller were not either,
  and they are no longer committed.
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
- Its header says that `up` and `down` change the cluster through the
  repository's own procedures. The preparation release is installed and
  removed with `helm` directly, with the context given. The header also says
  that both images are built from the local build cache: four layers of the API
  image were built again.
- `down` does not check that `up` ran. It removes a Helm release named
  `inferops` if one exists, the controller, and the prerequisites. In this run
  the first step showed that none of them existed before. Its `helm uninstall`
  line printed that the release was uninstalled, although the Application
  creates no Helm release: that line is not evidence that one existed.
- It leaves the two loaded images in the node, and files in the ignored
  directory.
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
- **Latency, throughput, or whether an objective is met.**
- **What happens when a pod is deleted, evicted, or replaced, or when a node is
  lost.** No fault was injected, and the cluster has one node.
- **That a budget refuses an eviction.** None was requested.
- **Anything about another provider, another cluster, or another release.**
  One local cluster was read.
- **That the host is qualified for the release.** Two capacity readings were
  accepted and one install succeeded, once.
- **A refusal of the collector against an API server.** The reading is
  `OBSERVED`. Each refusal is shown by a synthetic case.
