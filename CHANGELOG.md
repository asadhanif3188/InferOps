# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project intends to follow [Semantic Versioning](https://semver.org/spec/v2.0.0.html)
once versioned releases begin.

## [Unreleased]

### Added

- **The default lane now runs on a continuous-integration service, and that changes
  nothing about what it may certify.**
  [ADR 0012](docs/architecture/decisions/ADR-0012-continuous-integration-service.md)
  selects GitHub Actions for the `default-checks` lane and commits
  [`.github/workflows/checks.yml`](.github/workflows/checks.yml): nine gates covering
  formatting, lint, typing, the whole default pytest lane, the expected-failure
  controls, documentation links and whitespace, the distribution build, the API
  container image, dependency and runtime-image vulnerability scans, CycloneDX bills
  of materials, and a secret scan over full history. It closes half of
  [ADR 0005](docs/architecture/decisions/ADR-0005-test-ci-and-certification-strategy.md)
  D6; the half that would label a capable runner stays open, and the three lanes that
  need one are still run by hand.

  **No job in it has run on the service.** Every command was executed by hand on one
  Windows host before it was written down. A committed workflow is a configuration,
  a configuration is not a result, and that is why the `security-scan` layer is still
  `planned` and the two claims resting on it are still uncertified.

- **A gate matrix that cannot outlive the workflow it describes.**
  [The matrix](docs/testing/ci-gate-matrix.md) is committed as data and as a document,
  and [`tests/testing/test_ci_gate_matrix.py`](tests/testing/test_ci_gate_matrix.py)
  compares it to the committed workflows in both directions — a job with no row and a
  row with no job each fail. Every gate names the claims it defends **or records why
  it defends none**; there is no third option, which is what makes the mapping
  complete rather than merely present. Every ceiling is inherited from the evidence
  class the strategy already gave the layer, so automating the mock lane cannot raise
  what a mock certifies.

  Four prohibitions are checked rather than reviewed: the normal lane may not invoke
  `kubectl`, `helm`, `terraform`, `kind`, or a provider selection; it may not fetch
  the pinned model artifact; every `uses:` reference must be forty hexadecimal
  characters, because a tag is a name somebody can move; and every workflow must
  declare its token permissions. The cluster check reads the file's text rather than
  its parsed steps, because a cluster can be reached from a script block, an action
  input, or an environment variable, and only the text sees all three.

- **The expected-failure controls are a command now, not only a test.**
  `python -m tools.ci_gates expected-failures` runs the published validation commands
  from a shell against thirty fixtures and reads the **exit status**, which is the
  only thing a continuous-integration job can read: every invalid contract document
  and insecure manifest bundle must exit non-zero, and every valid document and
  committed chart render must exit zero. The positive half is deliberate — a
  validator broken into refusing everything would pass a suite of negative controls
  perfectly — and each group declares a minimum count, so a glob that matched nothing
  fails rather than producing an empty, passing run.

### Fixed

- **The secret-scan configuration had never parsed, and nothing could have noticed.**
  The first run of `gitleaks` this repository has ever made refused
  [`.gitleaks.toml`](.gitleaks.toml) outright with eleven decoding errors and scanned
  nothing: the allowlist patterns were declared as tables carrying a `description` and
  a `regex`, and the tool requires `regexes` to be a list of strings. The file had
  been committed since `V1-S0-009` with a test reading it — a test that matched quoted
  lines with a regular expression and so never asked the question the tool asks.

  The configuration is rewritten as `[[allowlists]]` blocks, one per exemption, which
  is the schema gitleaks accepts and keeps each description beside the pattern it
  exempts. The exemptions are unchanged: the same two directories and the same eleven
  published placeholder values. The check now parses the file with `tomllib`, requires
  every allowlist to say what it exempts, requires every exempted path to exist, and
  compiles every pattern.

  The rerun is clean over 134 commits. It is the first recorded run of a secret
  scanner here, which moves the `security-scan` layer from `planned` to `implemented`
  — and the claim resting on that layer stays `planned`, because one run by hand on
  one host says nothing about the next change.

  This is what the distinction between a configuration and a result was for. Every
  document that said a scanner had never run is corrected, and every document that
  implied the configuration was doing something now says what it was actually doing.

- **Twelve lines of trailing whitespace that a published check said were not there.**
  `CONTRIBUTING` has stated since Sprint 0 that
  `git ls-files -z '*.md' | xargs -0 grep -n '[[:blank:]]$'` returns no matches. It
  returned twelve, all in
  [one Sprint 1 record](docs/proof/serving/v1-s1-002-pr1-cumulative-review-fixes.md)
  that used Markdown's trailing-two-space hard break for three runs of metadata
  lines. Those runs are lists now, which render the same way without the whitespace;
  no statement, result, or claim in the record is altered. The check is a gate from
  this change on, so the gap between what the document claims and what the command
  returns closes rather than reopening.

### Changed

- **The statement that every check is run by hand is no longer true for nine of
  them, and is corrected.** `CONTRIBUTING`, the test strategy, ADR 0005's status
  banner and D6 section, the README, and the architecture decision index all said no
  workflow file, runner, or automated lane existed. One lane of four is now
  automated; the other three are not, no runner is labelled capable, and every
  document says which is which. The local commands are unchanged and are still the
  ones a contributor runs before opening a change — what changed is that forgetting
  is now caught.
- **Sprint 3's public claims now say what the evidence says.** A reconciliation pass
  read every current-status document against the authoritative data and the executed
  records, and corrected what had drifted. The claim and test matrix and the README
  both published *twelve of twenty-one claims certified*; the strategy data holds
  **twenty-four — sixteen certified, seven planned, one deferred**, and the matrix's
  own tables already agreed with it. Only the prose was wrong, and nothing read the
  prose. Three tests now derive those counts from the data, and a fourth refuses a
  claim published under a heading its status does not name.
- **The network-policy experiment's provider was recorded backwards and is corrected.**
  The Sprint 3 completion review said it ran on a `kind` cluster and that Docker
  Desktop's plugin was never tested;
  [the record](docs/proof/security/v1-s3-004-pr1-network-policy-enforcement.md) says
  the opposite and always did — it ran on Docker Desktop's Kubernetes, because `kind`
  is not installed on this host. The finding is unchanged: `kindnetd` does not enforce
  a NetworkPolicy, and that is now correctly a result **on the reference provider** and
  **not** one on `kind`.
- **Four relative links did not resolve**, two of them inside evidence records this
  sprint produced, while `published-documents-link-only-to-things-that-exist` was
  certified at `C0` and checked only by a shell command somebody had to remember to
  run. The links are fixed and
  [`tests/testing/test_document_links.py`](tests/testing/test_document_links.py) walks
  every committed Markdown file, so the certified claim is defended by a module rather
  than by a habit.
- **Security wording caught up with the deployment without gaining an inch of ground.**
  Statements that nothing here *applies a security context to a pod it deployed,
  because nothing here deploys a pod* were false after `V1-S3-011`. They now say what
  is true: the rendered and deployed workloads carry the documented pod-security
  settings, and that establishes nothing about whether the running platform is
  defended — no check reads a running pod, no admission control exists, and the
  network policy the release creates is not enforced. Every deferred risk and accepted
  exception is unchanged.
- **Counts published as prose were re-derived from their own data**: six accepted
  security exceptions rather than four, thirty-eight controls with nine unenforced
  rather than thirty-two with ten, three test layers without code rather than five or
  six, eighteen telemetry rules rather than fifteen, and eleven ADRs tallied including
  the one that had been silently dropped.
- **Collector wording was reconciled in both directions.** Documents still saying no
  collector exists were corrected; every statement that its series are ephemeral and
  that no durable store, dashboard, or alerting path exists was kept, and the generator
  that writes a query-evaluation record no longer emits a stale sentence into it.

### Added

- **Sprint 3 is closed, and the verdict is published rather than implied.**
  V1-S3-011-PR2 executes the lifecycle and cleanup half of the Kubernetes paved road on
  the `docker-desktop` reference provider and reconciles the repository's public claims
  to what the runs actually produced.
  [The completion review](docs/proof/environment/sprint-3-completion-review.md) maps every
  Sprint 3 story and every amended exit-gate item to its evidence and ends **Sprint 3:
  PASS** — bounded to one provider, one Windows host, CPU only, single-replica, with the
  limitations named in full. Sprint 4 is not started.

- **A release is broken on purpose and rolled back, for real.** `V1-S3-008`'s experiment
  had been written and never run. It now installs a known-good release, upgrades it with
  a controlled change that reaches the workload, upgrades it again with a byte count the
  mounted artifact cannot match, detects
  `init-container-nonzero-exit` on `serving-runtime`/`verify-model` after 6 425 ms, rolls
  back to the last known-good revision in 1 512 ms, and serves a real completion again
  7 983 ms after detection — HTTP 200, adapter `real`, 35 tokens, content not retained.
  Three readiness probes across the failure window, all answered: the failing candidate
  never became ready, so the pod already serving kept serving.
  [The record](docs/proof/environment/v1-s3-011-pr2-upgrade-rollback.md) includes the four
  attempts that failed first, because a workflow that has only ever been read is not the
  same as one that works.

- **The pod-restart experiment `V1-S3-003` owed since Sprint 3 exists and has run.** Its
  earlier evidence stopped a container on the host and said in as many words that it was
  *not* a pod restart; that record stays exactly as it is. The new one deletes a serving
  pod in a real cluster and establishes what a returning pod does not: a different pod
  name **and** a different UID, the same Terraform-owned claim bound to the same
  PersistentVolume, the same artifact by byte count and SHA-256 **and by inode and
  modification time**, the integrity init container exiting zero, readiness observed at
  zero and then above it, and a real completion before and after. Zero acquisition Jobs
  either side: nothing re-fetched 1.83 GB.
  [The record](docs/proof/serving/v1-s3-003-pr2-kubernetes-pod-restart.md).

- **Telemetry is asked what it saw during a failure, and answers honestly.** The
  collector was queried before, during, and after a real pod replacement. Target
  availability, workload identity, request counters and readiness failures are
  **collected and queryable**; `inferops_model_ready` is **not emitted**; pod-restart
  counters have **no source**. `up` never reached zero during the replacement — it means
  "the scrape succeeded", not "the workload is ready" — and the record says so rather than
  reading it as no interruption.
  [The record](docs/proof/telemetry/v1-s3-011-pr2-telemetry-during-recovery.md).

- **The teardown is proven to be a guest's.** `helm uninstall` left zero objects carrying
  the release's instance label, by every kind; `terraform destroy` through the guarded
  wrapper removed exactly the namespace and the claim it owns; and afterwards the Docker
  Desktop cluster still answers, its node is still Ready, its other namespaces are
  untouched, and the provider still verifies. Exactly one namespace disappeared.
  [The record](docs/proof/environment/v1-s3-011-pr2-scoped-cleanup.md) also names the one
  piece of InferOps residue this teardown does *not* remove, rather than tidying it away.

### Changed

- **The upgrade/rollback workflow acts on the provider it verified.** It used to pass the
  provider-aware target guard and then refuse anything but the pinned kind cluster, which
  was honest while its descriptor and evidence tooling were kind-specific and is no longer
  true of either. The refusal is replaced rather than deleted: the descriptor's entry for
  the verified provider is looked up by provider id, a provider the experiment cannot
  describe is still refused, and every `kubectl` and `helm` call now goes through the
  target wrappers. A provider-owned node image — Docker Desktop chooses its own — is
  **recorded** in the evidence and not enforced as an InferOps pin; kind's stays a pin,
  because InferOps selects it.

- **Twenty ownership rows moved from `planned` to `implemented`, and each cites the run
  that moved it.** The prerequisite layer, every release object, and the controller-derived
  rows were all observed in a cluster. `implemented` is stated with its bounds:
  `docker-desktop` only, single-replica, and — for `workload-network-policy` — created by
  Helm but **not enforced** by the local network plugin, which remains a different claim
  and remains unproven.

- **Every now-false status statement about Sprint 3 has been corrected.** The README, the
  ownership document, the Terraform prerequisite guide, the Helm lifecycle and
  upgrade/rollback procedures, the Kubernetes troubleshooting page, both certification
  procedures, the model-cache, telemetry-collection and correlation-query documents, the
  claim/test matrix, the test inventory, and the chart's own `NOTES.txt` all said the
  release had never been installed, or that no API image existed. Statements that are
  still true were kept — the committed API digest is still a placeholder, because the
  image is host-local and published to no registry — and the honest limitations that
  survived execution were kept or sharpened rather than dropped.

### Fixed

Six defects, each found by running something that had only ever been read, and four of
them now have a guard test. Two more were found by independent review of this change
and are listed with them.

- **The model acquisition hook deleted an artifact it could not replace.** An artifact
  that did not match its pins was removed *before* anything had been acquired to replace
  it. The first real run of the upgrade/rollback experiment showed what that costs: the
  experiment's deliberately wrong byte count renders into the hook as well as into the
  serving runtime, so the hook discarded a 1.83 GB artifact and left the Terraform-owned
  claim empty. The replacement is now staged beside the artifact and moved over it only
  once it verifies, so a failed acquisition leaves the claim exactly as it found it.

- **The injected fault never reached the workload it was aimed at.** The same byte count
  renders into the acquisition hook, which runs `pre-upgrade` at weight `-5`, so the
  upgrade failed before any serving pod was created and there was nothing to detect or
  recover. The unhealthy-candidate upgrade now sets `model.acquisition.enabled=false`
  alongside the fault — declared in the descriptor, validated, and restored by the
  rollback — which puts the fault where the descriptor always said it lands.

- **An evidence variable collided with a `readonly` constant.** The record writer passed
  `INFEROPS_NAMESPACE`, which `lib.sh` freezes as the *smoke* namespace. Bash refused the
  assignment and the run died after a complete and successful lifecycle with no record
  written. Renamed in both Kubernetes experiments, and a test now refuses any environment
  script that assigns a name `lib.sh` declares `readonly`.

- **The release's configuration was read by label selector.** The release carried one
  ConfigMap when the workflow was written and carries three now; a selector returned all
  of them and the record took the collector's, which carries none of the fields it needed.
  Both experiments now read the ConfigMap the descriptor names.

- **The residue check raced the garbage collector.** Asked once, the instant
  `helm uninstall --wait` returned, it reported terminating pods as residue — the same
  defect both certification scripts had already been fixed for, in a workflow that had
  never been run. It now asks repeatedly inside the uninstall budget.

- **The impact prober was slower than the failure it sampled.** It asked every
  5 000 ms against a failure detected in about 7 000 ms, so it could not reach the three
  probes the descriptor requires. The interval is now 2 000 ms: the requirement is
  unchanged and the sampling is denser, which is more evidence rather than less.

- **A recovery figure was stamped before the thing it timed.** Found by review, not by
  a run. The pod-restart experiment stamped "deletion to a served completion" when its
  port-forward accepted a connection — which is earlier, and would not have moved if the
  model had taken another minute to load. The origin now comes from the operating script
  and the end is stamped by the tool, at the moment it has a completion in hand.

- **The replacement loop broke on the wrong readiness.** Also found by review. It read
  the Deployment's aggregate `readyReplicas`, which still counts a deleted pod inside its
  termination grace period, while its own comment claimed it was reading the
  replacement's. It now asks the replacement pod for its own `Ready` condition; the
  aggregate is still sampled, because that is the right signal for whether the Deployment
  noticed.

- **The Kubernetes paved road is certified on Docker Desktop, end to end, for the first
  time.** V1-S3-011-PR1 executes the post-S3-010 path on the V1 reference provider rather
  than rendering it: the target is verified, the API and model-seed images are prepared,
  Terraform applies and re-applies the prerequisites with no changes, Helm installs the
  real profile, the runtime loads the pinned weights from the claim, and one real
  completion returns through the release's own Service — HTTP 200, 43 tokens, content not
  retained, adapter kind `real`, artifact hash compared inside the cluster. The record
  names its provider (`kubernetes.cluster.provider: docker-desktop`) and may not be read
  as a kind result.
  [The full record is here](docs/proof/environment/v1-s3-011-pr1-docker-desktop-paved-road.md).

  **The two capabilities the contract owed this story are established, by measurement.**
  Docker Desktop's Kubernetes does *not* share the local engine's image store — an image
  the engine holds is invisible to the node by tag and by digest alike, and so is one the
  engine pulled from a registry. `kind load` is not the mechanism either, because the kind
  CLI finds nodes through `docker ps --filter` and Docker Desktop's API proxy filters its
  own containers out of `docker ps`. What works is importing into the node's own
  containerd and then creating the `repository@digest` *name* containerd resolves by —
  without that tag step the bytes are present, the digest is right, and the reference the
  chart pins still does not resolve. `inferops::target_load_image` now owns that choice
  for both providers, and `api-image.sh` and `model-seed-image.sh` no longer name a
  mechanism at all. Capacity is recorded too: the node is given effectively the whole
  Docker Desktop virtual machine, so a gate must read the node's own allocatable and what
  is already requested on it rather than the engine's total.

  **Docker Desktop's identity guard is no longer weaker in the way ADR 0011 left open.**
  The check the contract carried as `undecided` — binding the API server's nodes to
  containers on this machine's engine — is implemented: Docker Desktop provisions its
  Kubernetes with kind, and `desktop-control-plane` carries
  `io.x-k8s.kind.cluster=desktop`. Those labels are kind's own generic ones and settle
  nothing on their own — an ordinary `kind create cluster --name desktop` reproduces them
  exactly — so the check that carries the weight is a port: the container must publish
  the very API server port the verified kubeconfig dials, which ties the connection being
  verified to the container being inspected. That refuses a remote or foreign API server,
  and refuses a kind cluster under any name other than `desktop`. It **cannot** refuse a
  kind cluster the operator themselves named `desktop` reached through a context they
  named `docker-desktop`, because there that cluster genuinely is the one being dialled;
  nor does it pin `DOCKER_HOST`, so "this machine's engine" is really "the engine this
  `docker` CLI is configured to reach". Both are recorded in the check's own `gap` and
  accepted as **EX-06** in
  [the deferred-risk register](docs/security/deferred-risks.md) rather than left for a
  reader to notice. Asking *by name* instead of enumerating, which is what Docker
  Desktop's API proxy forces, is why the node-count and node-name checks are relied on
  together with it.

  **The certification workflows are provider-neutral.** `kubernetes-certification.sh` and
  `kubernetes-multi-replica-certification.sh` no longer refuse every target but the one
  kind cluster their descriptors named: both descriptors now describe every supported
  provider, a run is certified against the entry for the provider it verified, and the
  node image is a *pin* only where InferOps chose it — Docker Desktop's is recorded and
  not enforced, because comparing it to a digest this project never selected would be
  enforcing somebody else's. Every collected fact names the provider it was collected on.

  **Multi-replica certification refused at the capacity gate, and the refusal is the
  evidence.** The reference host is short by about 165 MiB of uncommitted cluster memory,
  held by an unrelated project's workloads that are not InferOps's to remove. The gate was
  not weakened, the replica count was not reduced to fit, and no multi-replica claim is
  made anywhere in this change. The refusal now *writes a record*: it previously printed
  to a terminal and left whatever diagnostics file an older run had put on disk as the
  only artefact, describing a different run on a different day.

  **The telemetry collector is proved to collect.** A new
  `scripts/environment/telemetry-collection-verify.sh` installs the release, sends a small
  number of real requests so that counters are non-zero, and asks the running collector
  whether it discovered and scraped both InferOps jobs and whether it can evaluate every
  accepted correlation query. Until now the query record's own `verificationStatus` said
  `collected: false` and "No Prometheus has parsed, loaded, or evaluated any expression in
  this record." Requests sent at this stage are not a measurement and no latency,
  throughput, or capacity figure is published from them.

- **Provider-aware cluster verification is implemented, for both `kind` and Docker
  Desktop.** V1-S3-010-PR2 builds the mechanism
  [ADR 0011](docs/architecture/decisions/ADR-0011-external-local-cluster-provider-contract.md)
  specified. Every platform workflow now takes an explicit `INFEROPS_PROVIDER` — `kind`
  or `docker-desktop`, with no default — and, for `kind`, an explicit
  `INFEROPS_KIND_CLUSTER_NAME`, and re-verifies that selection itself, every time,
  through one new entry point in `lib.sh`: `inferops::resolve_target`. It writes a fresh
  project-scoped kubeconfig from whichever context the operator's own kubeconfig names,
  never trusts one written by an earlier run, and refuses before any mutation on eight of
  the nine documented cases — the ninth, `unexpected-context`, is made impossible by
  construction rather than caught after the fact, because the kubeconfig it writes is
  never read back and compared. Docker Desktop gets a real, if narrower, identity guard:
  a context literally named `docker-desktop` and a node set matching the one shape this
  project has observed, `desktop-control-plane` running `kindest/kindnetd` — and
  deliberately nothing that binds those nodes to this machine's engine the way `kind`'s
  containers are bound, because whether that is even possible has not been established.
  `api-image.sh` and `model-seed-image.sh` refuse to load an image into a target whose
  `imagePreparation` capability is not `kind-load` rather than trying and failing inside
  the node; the Terraform environment root's `kube_context` validation accepts either
  provider's context instead of pinning `kind-inferops-dev`; and a new read-only
  `target-detect.sh` reports which providers a host can see without ever selecting one.
  **Three workflows are deliberately not ported**: `kubernetes-certification.sh`,
  `kubernetes-multi-replica-certification.sh`, and `helm-upgrade-rollback.sh` now require
  and re-verify an explicit target the same as everything else, and then refuse anything
  but the one kind cluster their committed descriptors still describe — a Docker Desktop
  target passes verification and is refused immediately after, by name, rather than
  certified against a descriptor that was never written for it. Porting those three, and
  making the evidence they write name the provider it ran on, is V1-S3-011.
  [A new behavioural suite](tests/architecture/test_target_verification.py) sources the
  real `lib.sh` against fake `kubectl`/`kind`/`docker` executables and exercises every
  refusal, for both providers, alongside a positive verified case for each — the
  companion to the existing static-reading suite, which cannot tell a refusal that fires
  from one that is merely written down. **No cluster was contacted; the kind helper
  scripts, their fixed `inferops-dev` cluster, and their own evidence are unchanged.**

- **The Kubernetes cluster is no longer InferOps's.**
  [ADR 0011](docs/architecture/decisions/ADR-0011-external-local-cluster-provider-contract.md)
  moves cluster lifecycle out of the project: the operator provides an existing cluster
  through one of two supported providers, `kind` or Docker Desktop's Kubernetes, selects
  it explicitly, and InferOps verifies and consumes it. Nothing on the platform path
  creates, enables, resets, reconfigures, or deletes a cluster, and
  [the provider contract](docs/environment/local-cluster-provider-contract.md) writes
  down the rest as data: no selection input has a default, detection may report and
  never select, every mutation re-verifies, Terraform and Helm are handed a kubeconfig
  path and a context and never the provider, nine cases refuse before anything is
  mutated, and seven capability questions are answered separately for each provider
  with how each answer is known. **It is a decision, not an implementation, and it says
  so row by row**: the only identity guard is the `kind` one, for the one name the
  scripts pin, so every script still refuses a Docker Desktop cluster — the correct
  failure until a positive check exists, and not support. Four of the nine refusals
  exist, for `kind` only; three of the fourteen rules are enforced by nothing and two by
  review alone; three Docker Desktop capabilities — image visibility, capacity, and what
  a reset removes — are recorded as unknown rather than borrowed from `kind`; and the
  engine binding that would make a Docker Desktop guard as strong as `kind`'s is
  **undecided**, which is why the record is accepted in part. Read across, the evidence
  says something easy to miss: ADR 0001's cluster evidence exists only for `kind`, and
  ADR 0002's in-cluster runtime evidence exists only for Docker Desktop, and neither
  certifies the other. ADR 0001 D2, D5, and D6 are superseded in part and ADR 0004 D3 is
  amended, without rewriting either; the ownership inventory gains `cluster-operator`
  and splits its cluster row into `kind-cluster`, `implemented`, and
  `docker-desktop-cluster`, `planned`; and the `kind` runbook is now an optional
  helper's. [The suite](tests/architecture/test_local_cluster_provider_contract.py)
  holds the contract to its document, the ownership inventory, the guard functions in
  `lib.sh`, and the Terraform module, reads every platform workflow for a cluster
  create, delete, or helper invocation — with a control case showing the pattern does
  catch the helper — and pins the open gaps, so closing one has to update the
  contract. **No script, chart, descriptor, or Terraform file changed, and no cluster
  was contacted.**

- **A troubleshooting page for the Kubernetes path, organised by what you saw rather
  than by which component owns the fault** — and honest about the fact that half of what
  it describes has never been installed. The
  [new guide](docs/environment/kubernetes-troubleshooting.md) covers cluster and context,
  scheduling and out-of-memory, the model cache claim, slow and failed model loads,
  probes, Service and network, the API's and the runtime's logs, the telemetry scrape,
  the Helm release, Terraform state and ownership, upgrade and rollback, and cleanup.
  **The cleanup is four operations with four blast radii and they are not a sequence**:
  `helm uninstall` leaves the namespace, its metadata, and the 1.71 GiB model cache
  standing, `terraform-prerequisites.sh destroy --confirm` cascades over the namespace
  and is the only thing that reclaims the weights **without destroying the cluster** —
  the node declares no `extraMounts`, so `cluster-down.sh` takes them along with the
  cluster — and there is deliberately **no separate in-cluster cache deletion**
  because the weights live inside the Terraform-owned claim and a third command would be
  a second owner for one resource. **One section tells the reader to stop investigating**:
  the chart renders four `NetworkPolicy` objects starting from a default deny and
  `kindnetd` enforces none of them, which was measured rather than assumed
  ([the record](docs/proof/security/v1-s3-004-pr1-network-policy-enforcement.md)), so a
  refused connection here is a Service, a selector, a probe, or a port. **The status is
  stated before the content and it is two different statuses**: the cluster half was
  executed and evidenced on one Windows host, and the release half has never been run by
  anybody, on any cluster, because `platform-api-container-image` is still `planned` and
  no `Dockerfile` is committed — so every release symptom is derived from the chart, the
  committed render, the descriptors and the scripts, and says so. It also refuses to blur
  the distinction both certifications are built on: `helm rollback` returning zero says a
  revision was recorded, and `progress deadline exceeded` is a deadline rather than a
  statement about health, because a timeout cannot tell a broken container from a model
  load this project has measured between 133,515 ms and 358,735 ms.
  [The suite](tests/architecture/test_kubernetes_troubleshooting.py) holds all of it to
  the repository in nine groups — every command against the module, subcommand, script or
  path it names, every target against `lib.sh`, every port, probe, budget, deadline,
  resource figure, claim size, byte count and forward port against the render, the values
  file, the Terraform variables or the model source record, the exit vocabulary against
  both Kubernetes tools, every quoted measurement against the proof record it is
  attributed to, every relative link, and the rules that keep every fenced `kubectl` and
  `helm` sample explicitly scoped to this project's kubeconfig and context, free of any
  credential-shaped flag, incapable of deleting a namespace by hand or pruning the
  engine, and labelled destructive wherever it deletes something. **Documentation only**:
  nothing under `charts/`, `deploy/`, `infra/`, `scripts/`, `src/`, or `tools/` is
  touched.

- **A release can now be broken on purpose and got back — on paper, because nothing
  has installed it.** `helm rollback` returning zero says a revision was recorded, and
  a Deployment that never rolled, a Service selecting a pod that loaded nothing, and a
  healthy release are indistinguishable from outside until something asks for a
  completion. So
  [the new experiment](deploy/serving/experiments/helm-upgrade-rollback.v1.json) asks
  four separate questions across four revisions: a known-good install, a **controlled**
  upgrade, a candidate the cluster cannot run, and a rollback — and it holds each one
  to the cluster rather than to Helm's own bookkeeping. **The controlled change is
  fixed in code rather than left to the descriptor**: `telemetry.serviceVersion` is
  inside `inferops-llm.derivedEnv`, whose rendering is hashed into every pod template's
  checksum, so setting it produces a real rollout; a value outside that block would
  make a revision Helm records and Kubernetes never acts on, and rolling *that* back
  would prove nothing. It is asserted twice over — the value reached the rendered
  ConfigMap **and** the serving pod is a different pod. **The injected fault is a byte
  count the mounted artifact cannot match**, which the chart compares in the
  `verify-model` init container *before* the SHA-256 read, so it fails fast and says
  why; six safety properties are declared beside it and each is refused if false — it
  changes no image reference, pulls nothing, creates no object outside the release,
  touches no cluster-scoped object and no claim, and is removed by the rollback rather
  than by a second edit. One of those is checked against the chart rather than taken on
  trust: the fault has to be a value the schema and `_validate.tpl` **accept**, because
  a fault Helm rejected is a run that never installed its own fault and would then
  report a detection it did not make. **Detection is evidence, never a clock.** The
  failing upgrade is deliberately not waited on, an init container that ran and exited
  non-zero is required, and `progress-deadline-exceeded` is recorded as the deadline it
  is and refused as a statement about health — the descriptor cannot even set a
  detection budget shorter than a healthy rollout, because this project has measured
  model loads from 133,515 ms to 358,735 ms and a timeout cannot tell one of those from
  a broken container. A candidate pod the host could not schedule is a **third** answer,
  `INCONCLUSIVE`, with a remedy: it never ran the fault, so the run observed its own
  capacity. Only pods that are *not* ready are inspected, because the pod still serving
  has a succeeded init container of the same name. **User impact is measured, not
  assumed** — a readiness probe every five seconds across the failure window, with a
  refused probe recorded rather than hidden and a window nobody sampled refused — and so
  is the recovery: whether the runtime had to reload the model at all is written down as
  `runtimeReloaded`, which is the difference between a recovery of seconds and one of
  minutes. Thirty-two ways of weakening the descriptor and thirty-nine ways of making
  a run look better than it was are each provoked by
  [the suite](tests/architecture/test_helm_upgrade_rollback.py) and each has to stop it.
  **Two independent reviews before push raised one HIGH, two MEDIUM and four LOW
  findings and all seven are fixed**, the HIGH being the one that mattered: the
  deliberately-failing `helm upgrade` is backgrounded so that the detection is not a
  timeout, and its pid was not in the cleanup path — a run interrupted during the
  detection loop would have left a `helm upgrade` running detached against a real
  release, still writing its history, while the script printed the `helm uninstall`
  that would race it. All three backgrounded pids are now declared together and reaped
  together, and a test derives that set from the script so a fourth cannot be added
  without joining it. The exit trap also named only `EXIT` where both sibling scripts
  name `INT TERM EXIT` for a reason one of them writes down, and `record_stage` turned
  an unanswered `kubectl` query into an empty value — which for the service version is
  precisely the difference between "the upgrade did not reach the workload" and
  "nobody asked". **Nothing has been installed, upgraded, broken, or rolled back**: every fact the
  module read in this change is a document the suite wrote, every answer the "restored"
  release gave is a dictionary it constructed, and the workflow **cannot** be run — no
  InferOps API image is published, which is the same one-line blocker that already stops
  the lifecycle procedure and both Kubernetes certifications.
  [The record](docs/proof/environment/v1-s3-008-pr1-validation.md) says so, and
  [the procedure](docs/environment/helm-upgrade-rollback.md) says so in its first
  paragraph.

- **The queries that would be asked of all that telemetry are now published, checked,
  and run — and still nothing has answered one.** A scrape configuration can attach
  every right label and a query can still return nothing, because it groups by a label
  the collector drops, joins on a key one side does not carry, reads a metric nothing
  emits, or uses a name nothing publishes. In a console all four look exactly like a
  healthy quiet system, which is the failure
  [the new query record](docs/telemetry/telemetry-correlation-queries.v1alpha1.json)
  exists to make impossible to write by accident: twenty-three questions, each with the
  PromQL it is asked in, the class that says whether it can be answered at all, and
  **the reason its result would be empty**. **Nothing about a query is declared beside
  it** — `tools/telemetry_correlation` parses every expression with a **declared subset
  of PromQL** and derives the metrics it reads and the labels it depends on from the
  expression itself, because a list maintained by hand beside an expression is a second
  copy and the first edit that forgets it leaves a record describing a query nobody
  runs. **An expression outside the subset is refused rather than published unchecked**,
  which is the whole safety argument for reading a query here instead of in Prometheus:
  a form this cannot represent cannot be quietly mis-evaluated. `topk`, `bottomk`, and
  `quantile` are out because they select rather than summarise; `count_values` is out
  because it writes a label out of a *value*, which is the one move the telemetry
  catalog exists to prevent. **The vocabulary a query may use is recomputed from the
  catalog on every run** — every attribute the catalog permits on a series, every
  target label the collection record declares, and `le` — and a test asserts it is the
  complement of the chart's rendered drop list, so a query can never ask for a label
  the collector removes. Six rules refuse the six ways a query lies, and **ten
  deliberately wrong queries are committed beside the good ones**, each naming the rule
  that refuses it: a per-request breakdown, a per-tenant filter, a group by
  `k8s_pod_name` (which is available as `instance` and by no other name), a group by
  HTTP status, a metric nothing declares, a label nothing carries, an honest expression
  with a dishonest answerability claim on it, a join on a key `inferops_build_info`
  cannot carry, a subquery, and a `topk`. **Then the queries are run**, against six
  synthetic stores whose series carry the label sets the committed renders would attach,
  through the `labeldrop` the chart actually renders and the recording rules read out of
  the render — and running them found three things reading could not have: the identity
  join **returns nothing rather than a partial answer** when a target is up and
  publishes no identity, so `inferops:build_info_absent:platform_api` is the query that
  explains it; **a cross-tier identity join is impossible** with more than one API
  replica, because `inferops_build_info` is one series per process and every replica
  shares the runtime's only join key, which is now published as a gap and driven into
  its many-to-many error by a test; and the chart's default leaves `service_version`
  **empty**, which Prometheus cannot tell from absent, so `group_left` copies nothing
  rather than a blank. **Four questions have an answer that is always empty and two have
  no expression at all** — container and pod resource use, and pod phase and restarts,
  have no source in the accepted local cluster — and each says what would provide it,
  because a question missing from a query catalogue is a question somebody writes badly.
  Every one of the eight metrics the catalog marks emitted is read by a published query,
  and the four catalog metrics no query reads each say why. **No Prometheus has parsed,
  loaded, or evaluated a single expression in this change**: every result in
  [the query evaluation record](docs/proof/telemetry/v1-s3-007-pr2-query-evaluation.md)
  came from this repository's own evaluator, whose differences from the engine —
  chiefly that `rate()` does not extrapolate — are declared rather than left to be
  discovered, and a cross-check against `promtool` is recorded as the first follow-up
  and was **not** done. **Independent review before push found ten defects, all
  fixed**, and three of them were claims this change made about itself that were not
  true: the rule that refuses a join on a key one side cannot carry read only the `on`
  set, so a `group_left` written with `ignoring` was *not checked at all* — the parser
  now refuses that combination outright, because a rule enforced for half a syntax
  reads as enforced and is not; a deeply nested expression raised `RecursionError`
  rather than the refusal the module promises, which is now a declared nesting bound;
  and `SAFE_MESSAGE_CHARACTERS` was enforced on a finding's message and not on its
  subject, which is a `queryId` and reached stdout unfiltered. A matcher regex was
  compiled straight from input and `(a+)+$` hung the process, so patterns are now held
  to a declared safe subset with no group to backtrack into. A comparison without
  `bool` dropped the metric name, which only the arithmetic operators do. And three
  were miscounts in published prose — nineteen barred labels written as twenty, and
  four always-empty queries written as three in two places.
  [The query document](docs/telemetry/telemetry-correlation-queries.md) states the
  workflow, the expected empty and error states, the four things that cannot be
  correlated, and the seven this does not establish.

- **The chart now renders a scrape configuration, and still nothing collects.**
  `telemetry-scrape-configuration` was the last Helm-owned row deferred to a story
  rather than to an unpublished image, and
  [`charts/inferops-llm/templates/telemetry-scrape-config.yaml`](charts/inferops-llm/templates/telemetry-scrape-config.yaml)
  renders it: a ConfigMap holding a Prometheus scrape configuration — one job for the
  platform API, and under the real profile a second for the serving runtime — and a
  set of recording rules. **It is a ConfigMap and not a `ServiceMonitor`**, because a
  custom resource would make this chart install only on a cluster carrying a
  Prometheus Operator nobody has chosen, and the collector is still the open question
  `ADR 0004` deliberately leaves open. **Nothing reads it**: neither Deployment mounts
  it, no collector, store, dashboard, or alerting path is selected, nothing scrapes
  either endpoint, and this chart has never been installed. **Discovery selects on
  Kubernetes labels rather than on `prometheus.io/*` annotations**, which are optional
  and off by default — a configuration keyed on them would have selected nothing in
  the default installation — and it is pinned to the release's own namespace and
  instance, so a second release installed beside this one is not scraped and
  attributed here. **The collector never attaches a label the emitter already
  publishes**, and `honor_labels: false` is written out rather than left to the
  default because it is the whole reason: a duplicate target label wins the collision
  and renames the emitter's to `exported_*`, so every query written against it starts
  reading a label that is no longer there. The API job therefore attaches Kubernetes
  context and nothing else, and workload, model, environment, and the immutable
  identity are read where `ADR 0006` D3 put them — on the series themselves and on
  `inferops_build_info`. The runtime job is the opposite case and says so:
  `llama-server` publishes bare series with no labels at all, so the collector supplies
  the four operating dimensions the catalog permits as metric labels and none of the
  identity ones, and `inferops_runtime_id` is **derived from the profile** rather than
  configured, for the same reason the capability identifier is. **One label here is
  unbounded and it is argued for rather than glossed**: Prometheus requires the targets
  of one job to differ in their label sets, so `instance` cannot be removed — it
  carries the pod name rather than the default `<podIP>:<port>`, its cost is stated as
  a multiplier over the store's retention window, and the cheap alternative was refused
  because collapsing it makes two replicas indistinguishable, which is the one question
  the multi-replica certification exists to answer. The catalog's rule that
  `k8s.pod.name` is not a metric label is an *emitter* rule and is untouched. **The
  drop list is derived, not copied**: every job drops every attribute whose catalog
  placements include neither `metric-label` nor `info-label`, and a test recomputes
  that list from the catalog on every run, so a placement decision taken there reaches
  the collector without anybody remembering to edit the chart. **Absence is made
  readable rather than left to `up == 0`**: a job whose discovery matched nothing
  produces no `up` series at all, so every query grouping by job returns an empty
  result that looks like a healthy quiet system — there is one `absent()` rule per job,
  one for an API that answered a scrape and published no identity, and one for
  `inferops_model_ready`, which **reads 1 today and will until the adapter that owns it
  emits**, because a rule that averaged a metric nothing produces would have published
  an empty series that reads as health. Six catalog signals and four kinds of
  Kubernetes resource context have **no source at all** and each says what would
  provide it. `python -m tools.telemetry_collection` applies the same rules to any
  render, and the new suite caught three defects in the first version of this change:
  the record widened `inferops.runtime.id` from the catalog's bound of three to five,
  a target label named `job` was declared in the data and published in neither
  document, and a recording-rule comment naming the serving-runtime adapter put the
  string `serving-runtime` into the *mock* render, which the existing suite that
  proves a mock carries no runtime refused. **Prometheus's own `promtool` accepts
  both profiles' configuration and rules**, which is a one-off check at a stated
  version rather than a gate — nothing here pins it, and accepting a configuration is
  not running one. **Independent review before push found six more defects, all
  fixed**, two of which were controls that read as controls and were not: the release
  name reached the `keep` filter's regex unescaped, so a release called `a.z` would
  have kept the pods of one called `aXz` installed beside it — the precise failure
  that selector exists to prevent — and the scrape jobs were named by a constant, so
  two releases' fragments could not be merged into one collector configuration at all
  (`promtool` reports `found multiple scrape configs with job name …`; the
  release-qualified names merge cleanly, and the two `absent()` rules over a metric
  are now scoped to the release namespace and tier for the same reason). The others:
  `values.yaml` still said the resource was deferred and unrendered thirteen lines
  above the block that renders it; the checker crashed on malformed embedded YAML
  instead of refusing it, which now has a seventh rule of its own; `Finding` claimed
  never to quote a manifest value while two rules named one, so the class now declares
  the character set a message may use and a test drives it over ANSI escapes, a
  carriage return, and a right-to-left override; and the collector pod selector
  constrained its label values and not its label keys.
  [The collection document](docs/telemetry/kubernetes-telemetry-collection.md) states
  what a collector would find, what each label would cost, and the eight things this
  does not establish.

- **A collector can be let through the release's default-deny, and by default none
  is.** `telemetry.collection.collector` names a namespace and a pod selector,
  required together, and renders one ingress rule on the API policy and one on the
  runtime policy. Both empty is the default and leaves the denial whole, because there
  is no collector to name and an allowance for an absent one is a hole with no purpose.
  The namespace selector and the pod selector are **one `from` item**, which means "a
  pod in that namespace with those labels"; written as two items they would mean "any
  pod in that namespace, **or** any pod anywhere with those labels", which is a
  materially wider hole and reads identically in a
  `kubectl get networkpolicy -o yaml`. A collector named while
  `security.networkPolicy.enabled` is false is refused rather than silently rendering
  nothing, because a release stating an allowance it did not render would read as a
  control it does not have. **None of it is enforced where this project runs**: the
  accepted local cluster's network plugin was tested and does not apply a
  NetworkPolicy at all, `DR-04` carries that and `EX-05` records it, and the metrics
  endpoint is unauthenticated (`DR-01`) whether or not a policy is applied.

- **Multi-replica Kubernetes inference is certified as a separate profile, and
  nothing has run it either.** The single-replica certification could not answer
  whether requests reach more than one replica and said so: its one request goes
  through a `kubectl port-forward`, which the API server serves against **one
  selected endpoint** and which therefore traverses no virtual IP.
  [`scripts/environment/kubernetes-multi-replica-certification.sh`](scripts/environment/kubernetes-multi-replica-certification.sh)
  answers it instead — it installs the chart with at least two platform API
  replicas, waits for **every replica individually** rather than for a
  controller's summary count, and drives a bounded set of real requests through
  the API Service from a short-lived in-cluster Job, one connection per request,
  so that `kube-proxy` picks each endpoint.
  [`tools/kubernetes_certification/multi_replica.py`](tools/kubernetes_certification/multi_replica.py)
  then joins each successful request to the replica that recorded it, using the
  `inferops.request.id` and `k8s.pod.name` fields the API's own structured logs
  already carry — **no response header, body member, or endpoint exposes pod
  identity**, because a test that made a replica's name part of the API's
  contract in order to observe it would have changed the product to measure it.
  A request nobody recorded, a request two replicas both claim, a record from a
  pod that was never a ready replica, and every record landing on one replica
  are each a failure with a named stage; the last says plainly that it is the
  Service's endpoint choice rather than a defect, and it is not retried or
  downgraded. **Capacity refuses before anything is created**: two API replicas
  and two runtime replicas are 2,310 millicores and 4,496 MiB of requests
  peaking at 7,744 MiB of limits, the figures are the chart's own resource
  blocks times
  the replica counts and a test fails if the two drift, and a host that cannot
  hold them gets every shortfall at once with a remedy and its own exit code —
  because a host that is too small and a platform that did not certify are
  different answers. **The replica count is never reduced to fit**, and it comes
  from the descriptor with `--set` rather than from the operator's values file,
  so a file saying `replicaCount: 1` cannot decide this profile. **Both tiers
  are multi-replica, by two different kinds of evidence** — the second added by
  the Sprint 3 completion remediation, which found that this workflow had been
  certifying two front ends in front of **one** model server under a title that
  names model-serving replicas. The API tier is certified per request. The
  serving tier is certified per replica over a window: each `llama-server`'s own
  `llamacpp:n_decode_total` is read from that pod before and after the request
  set, and a run in which any ready serving replica decoded nothing fails. It
  cannot be a per-request join, and the reason is a property of Kubernetes rather
  than a gap: the API dials the runtime's ClusterIP and the socket keeps that
  address rather than the endpoint `kube-proxy` translated it to, so no request
  can be attributed to a runtime pod from the API's side — and `llama-server`
  puts no per-instance identity in a completion either. The record says so in a
  field of its own, `requestAttributedToServingReplica: false`, so that a reader
  who sees only the record cannot mistake one claim for the other. The single-replica
  certification is unchanged and independently runnable; the one edit to its
  module extracts the evidence-path safety check so that both workflows share one
  guard instead of two copies. **It has not been run, and today it could not
  complete**, for the same reason as PR1: no InferOps API image is published.
  An independent review before push found no defect in what the certification
  establishes, and three that were wrong anyway: the driver's completion was
  waited on with a call that cannot observe a failed Job, so a crash in the first
  second would have been reported half an hour later; a driver Job whose removal
  had not finished would have been counted as the release's own residue and
  failed the run with the wrong diagnosis; and three documents rounded a capacity
  figure down by a percent. All three are fixed, each with a test, and the
  repository's own lifecycle safety suite caught a fourth in the first version of
  the second fix — a line that both removed an object and printed the command to
  remove it, which it reads as an unscoped deletion, and which was reworded
  rather than exempted.
  [The procedure](docs/serving/kubernetes-multi-replica-certification.md) states
  why a forward could not answer the question, which tier is certified and why
  only one, what the capacity gate measures, and what the record will not
  support.

- **The Kubernetes half of real inference is automated, and nothing has run it.**
  [`scripts/environment/kubernetes-certification.sh`](scripts/environment/kubernetes-certification.sh)
  applies the Terraform prerequisites, installs the chart from an explicit real
  values file, waits **separately** for measured model readiness and API
  readiness against the budgets
  [the committed descriptor](deploy/serving/certification/k8s-real-inference.v1.json)
  publishes, runs the release's own in-cluster connection test, opens one bounded
  loopback forward, and uninstalls the release — then asks the cluster whether
  anything carrying the release label survived (claims included), whether Helm
  still reports the release, whether the namespace survived, and whether the claim
  count matches the one taken before the install.
  [`tools/kubernetes_certification`](tools/kubernetes_certification) performs no
  cluster operation at all: it validates the descriptor, holds the collected
  cluster facts to it rather than trusting them, refuses a base URL that is not
  the loopback forward, refuses mock identity or mock capability metadata, and
  writes a record labelled `local real Kubernetes` that carries no prompt and no
  completion. The evidence **class** is still `local-real-cpu`; a new class would
  have raised a ceiling by writing a string, and the new *label* is registered in
  the vocabularies [CONTRIBUTING](CONTRIBUTING.md) and
  [the mock and real boundary](docs/serving/mock-and-real-boundary.md) publish.
  `helm install` deliberately runs without `--wait`, because `--wait` folds the
  install, the model load, and the API start into one number and the model load is
  the measurement this story is about. **The readiness budgets are the chart's,
  not the adapter's**: `startupBudgetMs` is how long the adapter waits for a
  runtime it started, and the chart budgets the kubelet at twice that because a
  358,735 ms cold load has been recorded — a workflow pinned to the smaller figure
  would report a normal cold load as a failure. `requiresVerifiedModelCache` is a
  check rather than a declaration: the run reads the rendered init container's own
  command from the cluster and refuses unless the pinned SHA-256 appears in it, so
  a release installed with `verifyOnStart: none` cannot produce a record whose
  provenance names a hash nothing computed. Cleanup removes the release and
  **nothing else**. **It has not been run, and today it could not complete**: no
  InferOps API image is published, so an authorized run stops at the `release`
  stage with a pull failure and a diagnostics record — which is the workflow
  behaving correctly. An independent review before merge found nine defects, two
  of which would each independently have broken a real run after the model had
  already loaded; all nine are fixed and recorded in
  [the validation record](docs/proof/serving/v1-s3-006-pr1-validation.md), and the
  seam they hid in — the script writes a JSON document that the Python tool reads
  — is now covered by a test that executes the script's own writer and feeds its
  output to the reader.
  [The procedure](docs/serving/kubernetes-real-inference-certification.md) states
  the blocker, the stage vocabulary, which record decides each budget, and the two
  things a port-forward does not prove.

- **The prerequisite half of the ownership boundary is written, and nothing has
  applied it.** [`infra/terraform/`](infra/terraform/) declares the three
  resources the inventory gives Terraform — the platform namespace, its shared
  metadata, and the model cache claim — as a module and one local environment,
  and declares nothing else. The fourth Terraform-owned row is deferred out of V1
  and a test fails if it appears. `tests/architecture/test_terraform_prerequisites.py`
  is the comparison [the ownership document](docs/architecture/resource-ownership.md)
  said could not exist yet: it reads the prerequisite table and refuses a
  configuration that declares something the document does not give Terraform,
  that declares a release or derived object, that adds a second provider or a
  `helm_release`, or that leaves a prerequisite row undeclared — with the
  declared kinds checked as an allowlist as well as a denylist, so a kind nobody
  thought to forbid still fails. The lifecycle marker ADR 0004 specified and
  nothing implemented, `inferops.io/lifecycle: prerequisite`, is now set on both
  objects; **the scoped sweep that must exclude it is still not written**, and
  the ownership document now says which half is done. The provider is pinned
  exactly, with a lock covering six platforms because `terraform init` records
  only its own. [`scripts/environment/terraform-prerequisites.sh`](scripts/environment/terraform-prerequisites.sh)
  establishes cluster identity before Terraform reaches a cluster, hands it the
  kubeconfig and context rather than letting it inherit either, and refuses a
  destroy without `--confirm` or underneath an installed release. **Every
  Terraform row in the inventory is still `planned`**: no `plan`, `apply`, or
  `destroy` has been run against any cluster, and
  [the prerequisite document](docs/environment/platform-prerequisites.md) labels
  its apply and re-apply table as derived from provider semantics rather than
  observed. An independent review before merge found four defects, and all four
  are fixed and recorded in
  [the validation record](docs/proof/environment/v1-s3-005-pr1-validation.md):
  the ownership patterns were anchored at column 0, so a resource block indented
  by one space was invisible to every rule including the allowlist called the
  backstop; a size validation threw a raw function-call diagnostic beside its
  own message; three documents said the lock covered five platforms where it
  covers six; and three files elsewhere in the repository still said this
  Terraform did not exist.

- **Every workload the chart installs presents an identity of its own, and the
  release starts from a network denial.** The chart rendered one `ServiceAccount`
  that both Deployments named; it now renders one per workload. Neither is
  granted anything — no `Role`, no `ClusterRole`, and no binding of either is
  rendered anywhere in this chart, and no pod mounts a token — so the split
  changes no privilege today. It changes what the first grant can reach: a
  `RoleBinding` written for the API and attached to a shared account is a grant to
  the serving runtime as well, made by somebody who was not thinking about the
  serving runtime. Beside them the chart now renders four `NetworkPolicy` objects:
  a deny of both ingress and egress over every pod the release installs, and one
  rule each for the API, the runtime, and the `helm test` pod. The API is
  reachable on its own port from the release's own pods and may resolve DNS and
  reach the runtime; the runtime is reachable on its own port and may reach
  nothing, because `llama-server` reads a mounted file and answers a socket. The
  deny selects the release's own pods rather than the namespace, so a
  Terraform-owned prerequisite beside it is untouched, and it omits the component
  label so that a component added later arrives denied rather than uncovered.
  `security.serviceAccount.name` became `security.serviceAccount.api.name` and
  `.runtime.name`, and the chart version moved to `0.2.0`; nothing has installed
  `0.1.0`, so no upgrade path is owed to anyone.

- **A workload policy that reads rendered manifests, and nine fixtures that
  establish it refuses.** `python -m tools.workload_policy` applies twelve rules to
  a bundle of Kubernetes manifests — the six pod and container security properties,
  digest pinning, least exposure, an explicit resource envelope on every container,
  a dedicated service account, no credential-shaped environment name carrying a
  literal, and a default-deny selecting every workload. Every rule identifier is a
  control identifier in [the security baseline](docs/security/security-baseline.v1alpha1.json),
  and a test compares the two sets in both directions. Two rules apply to a release
  and not to the one-shot apparatus under `deploy/`, and the scope is read off the
  `inferops.io/lifecycle` label rather than chosen by whoever runs the check, so no
  invocation can ask for the lighter policy; a test holds the exemption to exactly
  two rules. Nine committed fixtures each drop one control and a committed record
  says which rules each must produce, compared in both directions — because a
  validator with no failing input can have every rule reading the wrong field and
  pass on every run, which is the outcome that looks exactly like enforcement.
  [The policy document](docs/security/workload-policy.md) publishes the rules and
  states what checking a manifest does not establish.

- **The model cache mount is scoped to the declared revision, and a release can
  no longer read bytes it did not name.** The chart mounted the Terraform-owned
  claim at its root with a free-form `subPath`, so `model.revision` was required,
  compared against nothing, and had no bearing on which bytes a container read.
  The claim is now mounted at the `<repository>/<revision>` subdirectory the
  chart derives from `model.artifact.repository` and `model.revision` — the same
  layout [the model source record](docs/serving/model-source.v1.json) already
  publishes for the workspace cache — and no values path reaches it. A release
  declaring one revision cannot see another revision's directory at all. The path
  the runtime is given as `--model` is derived from the same pair, so the file
  that is verified and the file that is served cannot be two files.
  [The storage document](docs/environment/model-cache-storage.md) has the layout,
  the ownership boundary, and what each teardown operation does to the bytes.

- **The serving pod verifies the artifact before it loads it, on every start.**
  An init container reads the mounted file and compares its byte count and
  SHA-256 against the pins the model source record publishes; a mismatch fails
  the pod rather than starting a runtime on it. It runs on every pod start and
  therefore on every restart, which is what makes it a restart property: a
  verification performed once at install time says nothing about the pod that
  replaced the one it ran in. `model.integrity.verifyOnStart` is `sha256` by
  default, with `size` and `none` as explicit downgrades that still keep the
  revision scoping — that is the mount rather than a check — and still refuse an
  absent artifact. The mock profile must state `none`, because a mock mounts no
  artifact and a render describing a verification that could not have happened is
  the same defect as a mock transcript naming a real model. The container is the
  BusyBox pin this repository already carries, is given no environment at all, and
  **has never been scheduled**.

- **A restart comparison, which adds no read of its own between the two
  starts.** `python -m tools.model_lifecycle restart --confirm-real-runtime`
  starts the pinned runtime, stops and removes it, and starts it again against
  the bytes it left behind. The classification taken between the starts stats
  the file and does not open it, and this comparison's own digest read is left
  until after both starts — where the cold/warm comparison deliberately reads
  the artifact end to end between its arms to warm the host file cache.

  It does **not** make the interval read-free, and an earlier draft of this
  entry said it did. `runtime_packaging.preflight` hash-verifies the artifact
  before every start, so a full read precedes each arm. Two consequences travel
  with that and are now stated wherever the comparison is: **no start this tool
  measures is cache-cold**, and **`createMs` and `readyMs` include that read**
  because the clock starts before it. Each of the three restart
  properties the lifecycle record claims is measured rather than restated: the
  artifact survives, readiness resets — read off the *first* probe sample of the
  restarted runtime, so a process that came back already ready would be visible —
  and the restart proceeds from a hit, which is the only state that needs no
  network. Results are written under their own two file names beside the other
  comparison, because a restart summary written over a cold/warm summary would
  not be a corrupted file but a readable one describing an experiment that was
  never run — and `results` reports each comparison separately, saying "not run"
  for an absent one while letting a corrupt one refuse with its own message.

  **It was executed**, and all five properties held; the figures and the six
  attempts it took are in
  [the restart record](docs/proof/serving/v1-s3-003-pr1-restart-reload.md). It is
  a *container* restart, not a pod restart — nothing here has run in Kubernetes —
  and its `readyMs` delta establishes nothing, because the same experiment on the
  same host on the same day spread further than the delta. The record also names
  a conflict this found and did not resolve: the accepted 300,000 ms
  `startup.budgetMs` is below loads this host produces **when its container
  virtual machine is left at the platform default**, and the chart's own kubelet
  budget is already 600,000 ms for that reason. Raising the allocation from
  7.60 GiB to 9.716 GiB took the same load to 202,984–224,562 ms and the
  measurement then passed twice with no warm-up; `docs/prerequisites.md` records
  what the smaller allocation costs.

- **The release now says how it starts and how it stops, and the one probe that
  is not an HTTP GET is the point.** The chart configures a startup, readiness,
  and liveness probe for each workload, and the mapping is read out of accepted
  records rather than chosen: the API's liveness and readiness paths are the two
  [the API surface record](docs/serving/inference-api-surface.v1alpha1.json)
  assigns those roles, and **the serving runtime's liveness probe is a TCP
  connect**. Its `/health` endpoint answers `503` for the whole of a model load —
  correct readiness behaviour, fatal liveness behaviour — and
  [the cold and warm start observation](docs/proof/serving/v1-s2-007-pr1-cold-warm-start.md)
  recorded 2,753 samples across six starts in which a healthy loading process
  would have been failing an HTTP liveness probe.
  [`runtime-profile.local.v1.json`](docs/serving/runtime-profile.local.v1.json)
  publishes `health.liveness.kind` as `tcp` for that reason, and a test compares
  the chart against it. The startup budget is `600,000 ms` rather than the
  `300,000 ms` the adapter's own `startupBudgetMs` publishes, because the
  measured loads do not fit in the smaller number; the chart refuses a Kubernetes
  budget below the adapter's, and a test refuses a default below the largest load
  this project has measured. Shutdown follows the order
  [`src/inferops/api/lifecycle.py`](src/inferops/api/lifecycle.py) fixes —
  readiness false, drain, exit — behind a `preStop` sleep action for the endpoint
  race, with a termination grace period the chart refuses unless it covers the
  pause and the drain together.

- **The chart has a test, and the release has a lifecycle procedure.**
  `helm test` runs a hook pod that asks every Service the release renders for its
  health endpoint, which is the one check that separates a rollout Kubernetes
  called successful from a release that answers.
  [`scripts/environment/helm-lifecycle.sh`](scripts/environment/helm-lifecycle.sh)
  installs, tests, upgrades, asserts the upgrade reached the rendered
  configuration, rolls back to revision 1, asserts the rollback undid it,
  uninstalls, and then asserts both halves of removal: that no object carrying
  the release label survived, and that the namespace and every
  `PersistentVolumeClaim` did. It is documented in
  [the lifecycle record](docs/environment/helm-release-lifecycle.md) and its
  safety properties — every `helm` call through a wrapper that names the
  kubeconfig and context, every release operation naming a namespace, and no
  command anywhere passing `--create-namespace` — are asserted by
  [the script suite](tests/architecture/test_cluster_lifecycle_safety.py).

- **Optional scrape annotations, and nothing that collects them.**
  `telemetry.scrapeAnnotations` adds `prometheus.io/scrape`, `port`, and `path`
  to every pod. It is off by default and inert either way: no scrape resource is
  rendered and `telemetry-scrape-configuration` stays deferred to `V1-S3-007`.
  All three keys are refused in `commonAnnotations` and in every per-object
  annotation map whether or not they are switched on, for the same duplicate-key
  reason the identity labels are.

### Removed

- **`model.containerPath` and `model.cache.subPath` are gone from the chart's
  values contract.** Both are now derived — the first from `model.cache.mountPath`
  and `model.artifact.fileName`, the second from `model.artifact.repository` and
  `model.revision` — because a settable in-claim path is how a release comes to
  read a revision it did not declare, and a settable container path is how the
  file that was verified and the file that was served come to be two files. The
  chart has never been installed anywhere, so no release is affected; a values
  file written against the previous contract is refused by the schema rather than
  silently accepted.

### Fixed

- **Five defects that only an execution could find, and one the tests could not see.**
  Each was invisible to a render, a lint, or a schema check, and each was found by
  V1-S3-011-PR1 installing this chart into a real cluster for the first time.

  1. **Embedded Python readers returned a trailing carriage return on Windows.** A Windows
     Python writes CRLF from `print`, and every value these readers produce goes straight
     into a shell variable; only the last field of a multi-line read escapes it. The
     symptom was "the certification descriptor's `descriptor_api_port` is not a number",
     which reads like a descriptor defect and is not one. Fixed once, in
     `inferops::python`, and routed through it at every reader that produces a value. The
     loopback socket probes are deliberately left alone: they answer with an exit status
     and print nothing.
  2. **The chart's `pre-install` hook named a ServiceAccount that did not exist yet.** Helm
     applies a phase's hooks before the release manifest, so the runtime account the model
     acquisition Job named had not been created when the Job was: the API server refused
     the Job outright and the install failed reporting only `failed pre-install: timed out
     waiting for the condition`. **On a cluster with no prior release this chart could not
     install at all.** The Job now has its own account, created by the same hook phase at
     a lower weight and removed by the same delete policy, so its lifetime is the hook's
     and `helm uninstall` has nothing of it left to remove.
  3. **The telemetry collector could never start.** It was passed
     `--web.enable-lifecycle=false`; Prometheus parses its command line with kingpin,
     where a boolean flag takes no value, so the process exited with `unexpected false`
     before it opened a port. Every probe failed and the release's connection test reported
     a refused connection to the collector Service — three steps from the cause. Both
     refusals are now spelled `--no-<flag>`, checked against the pinned image.
  4. **`helm test --logs` reported a passing test as a failure.** The chart deletes a test
     pod that succeeded, so `--logs` then failed fetching logs from a pod that was gone.
     The two settings contradicted each other directly. `--logs` is dropped from all seven
     call sites; a failed test pod is still kept, and the diagnostics collector reads it.
  5. **The residue check raced Kubernetes' garbage collector.** `helm uninstall --wait`
     waits for the objects Helm deleted itself, and a Deployment's pods are removed
     afterwards by the garbage collector on its own schedule — so asking the instant Helm
     returned counted three terminating pods as residue. Both certification scripts now
     ask repeatedly inside the uninstall budget their descriptors already state; anything
     present at that deadline is still residue.
  6. **A collected fact that was assigned and not exported reached the writer as empty.**
     The existing round-trip test could not see it, because it supplies the writer's
     environment itself rather than inheriting what the script exports. Both certification
     test files now assert that every `INFEROPS_FACT_*` a script assigns is also exported.

- **`test_no_state_and_no_plan_was_committed` failed on any machine that had actually run
  Terraform.** It globbed the filesystem for `*.tfstate`, which exists — ignored and
  untracked — the moment somebody applies the prerequisites locally, so it passed on the
  machines that had not done the thing this repository is trying to get done. It now asks
  `git ls-files`, which is the question its name always claimed to ask, and additionally
  asserts that the ignore rules keeping a careless `git add` from tracking one are in
  place.

- **The network policy this release renders is not enforced, and now the register
  says so.** `DR-04` had carried one question since it was written: does the local
  cluster's network plugin actually refuse traffic a policy denies. It was run. A
  `NetworkPolicy` denying all ingress and all egress was applied to a real cluster
  running `kindnetd` — the plugin a `kind` cluster ships — and pod-to-pod traffic
  by IP, DNS resolution, and a direct query to CoreDNS all continued to work. The
  plugin runs with no feature gate enabling policy enforcement and does not
  enforce. So the four objects the chart renders are a **correct policy that
  nothing applies** where this project runs.

  `DR-04` moved from *untested* to *tested and negative*, which is a worse position
  than the register previously recorded, and it still blocks production use.
  `EX-05`'s residual risk — that a policy the cluster ignores looks exactly like a
  control — was written as a hypothetical and is now an observation. Every sentence
  in the chart, the values file, the schema, the security documents, and the three
  copies of the `B3` boundary row that described this enforcement as *untested* has
  been corrected, because they became false the moment the test ran.
  [The raw result](docs/proof/security/v1-s3-004-pr1-network-policy-enforcement.md)
  records the procedure, the cluster it ran on, and what does and does not
  transfer to the accepted one. Closing it needs a policy-capable CNI, or kindnetd
  with enforcement switched on — both changes to an accepted environment decision.

  The kubelet-probe caveat could not be settled by the same run: a deny that is not
  enforced starves nothing, so the probe kept working for the wrong reason.

  Separately, both committed renders were applied against a real API server with
  `--dry-run=server`, which runs admission and defaulting rather than a schema.
  All eleven real-profile objects, all seven mock-profile objects, and the `helm
  test` hook pod were accepted.

### Fixed

- **Two independent reviews of the workload-policy change found six defects, and
  all six are fixed.** The one worth naming first is the shape rather than the
  instance: `security.serviceAccount.create: false` is documented and
  schema-legal, and with no names supplied it pointed every pod at the
  namespace's `default` account — so the chart rendered a release that its own
  new validator refuses, once per pod, and nothing said so. **A control a
  supported setting can switch off is a control that holds by default.**
  `create: false` now requires a name per workload and refuses the literal
  `default`; the case the setting exists for still renders and still passes.
  `security.networkPolicy.enabled: false` is the same shape and is deliberately
  not refused — an operator on a cluster that ignores policy objects may
  reasonably want none — but the render is then refused by the validator with one
  finding per workload, and a test asserts that rather than leaving the trade to
  a comment. The validator also compared pod labels without comparing
  namespaces, so a deny in one namespace was counted as covering a workload in
  another, which is a policy Kubernetes would never apply; read an omitted
  `policyTypes` as isolating nothing rather than as the `Ingress` Kubernetes
  defaults it to; and matched credential-shaped names with one regular
  expression that let `DB_SECRETS`, `APP_CREDENTIALS`, `clientSecret`, and
  `client-secret` carry a literal straight through. Matching is now done over
  split tokens across four naming conventions and held by a committed table of
  names that must and must not match — the second half of which exists because
  `MAX_OUTPUT_TOKENS` is a chart value here and a token count, not a credential.

- **The `B3` boundary said "No policy object exists" while the same file's own
  risk register said the chart renders four.** The baseline's boundary table and
  [the architecture](docs/architecture/system-architecture.md) carry that
  sentence verbatim by design, so both were corrected together: the gap at the
  namespace boundary is now an untested enforcement rather than an absent
  object, which is a different gap and not a smaller one.

- **The evidence record claimed `kubeconform` was not run because it is not
  installed.** It is installed, running it was one command, and every object in
  both renders — the four new `NetworkPolicy` objects included — validates
  against the Kubernetes 1.34 schemas. The record now carries the result and
  keeps the correction visible, because a record that misstates what a host has
  is a record whose other statements a reader has no reason to trust.

### Changed

- **`network-policy-in-the-release-namespace` moved out of `specified-only`, and
  what moved is the policy rather than its enforcement.** The control was decided
  for a chart nobody had written; the chart now renders the policy and a test
  refuses a render whose workloads are not described as denied in both directions,
  so it is `enforced-over-manifests`. A `NetworkPolicy` is applied by the cluster's
  network plugin and not by the object, no cluster has installed this chart, and
  whether the accepted local cluster's plugin applies one **has never been tested
  here**. `DR-04` is rewritten to carry exactly that half and still blocks
  production use; `EX-05` records the exception with its compensating control and
  its residual risk. The baseline gains four further controls — a dedicated
  identity per workload, an explicit resource envelope, no secret value in a
  rendered manifest, and the fixture check itself — taking it from thirty-four
  controls to thirty-eight and from twenty-four enforced to twenty-nine, with every
  count each document states recomputed from the data.

- **The chart suite went from 115 checks to 127 and the lifecycle suite from 74
  to 91.** The new chart properties are the model cache ones: that the mount is
  scoped to the declared revision, that no values path reaches that scoping, that
  the file the init container verifies is the file the runtime is given, that the
  pinned byte count survives the render as an integer, that the init container is
  given no environment, and that the acquisition row is declared deferred rather
  than forgotten. The new lifecycle properties are the restart comparison's: that
  it reads the artifact after both starts rather than between them, that a
  restarted runtime which came back already ready is reported as **not** a reset,
  and that scoped cleanup reaches both comparisons' results and still cannot
  reach the model cache. Two defects were found by writing them: the pinned byte
  count reached the template as a float and rendered as `1.834426016e+09`, so the
  comparison it fed could neither pass nor fail; and the entry below this one
  said the previous change took the chart suite to 112 checks when it took it to
  115, which is corrected here because two adjacent entries about one suite
  cannot both be right.

- **The chart suite went from 77 checks to 115, and the script suite learned
  about Helm.** New properties: that every workload container is probed, that the
  probe mapping matches the accepted health records, that the rendered startup
  threshold really grants the configured budget, that no probe timeout is as long
  as its own period, that a grace period covers what it has to contain, that the
  only hook is a test that deletes itself, that a `Deployment` selector is drawn
  only from things a rollback cannot change, and that nothing that runs passes
  `--create-namespace`. Ten of them were verified by breaking what they defend;
  one of the ten — the `--create-namespace` rule — was found to be wrong by that
  check and widened, because a shell continuation puts the flag on a line of its
  own. Two independent reviews then ran before anything was pushed, and neither
  found a `CRITICAL`. What they did find was a residue check that returned the
  same answer whether the cluster said "nothing" or said nothing at all; an API
  liveness and readiness path pair that no rule kept apart, so one `--set` could
  point all three probes at the readiness answer; and a claim in this project's
  own evidence record that the test image was a new external dependency, when
  four committed manifests under `deploy/` already pin that exact digest. All
  three are fixed, and the last produced a test comparing the chart's copy of the
  pin against theirs. A fourth defect was found without review:
  `progressDeadlineSeconds` defaults to 600 seconds, the same number as the
  runtime's startup budget, so the Deployment controller can fail a rollout the
  kubelet is still waiting on — both workloads now set it explicitly and the
  chart refuses a value inside the budget. **Still nothing has installed this chart**, and it cannot be installed:
  both profiles run an API container and no InferOps API image is published.
  [The validation record](docs/proof/architecture/v1-s3-002-pr2-validation.md)
  states that blocker, the nine refusals exercised against real Helm, and one
  finding it deliberately did not act on — the adapter's published startup budget
  is smaller than two model loads this project has measured, which is an accepted
  record and not this PR's to change.

### Security

- **Two host-run scan guards now cover the pinned runtime image and the
  committed dependency lockfile.** `scripts/security/scan-runtime-image.sh`
  and `scripts/security/scan-dependencies.sh` run Trivy against, respectively,
  the runtime image `deploy/serving/runtime/container-package.v1.json` pins by
  digest and `uv.lock` (including its test and checks groups, the only Python
  dependencies this repository pins), and refuse to report success when a
  `CRITICAL` or `HIGH` finding turns up with no recorded exception.
  `scripts/security/generate-sbom.sh` produces a CycloneDX SBOM for each,
  promoted copies of which are committed under
  [`docs/proof/security/sbom/`](docs/proof/security/sbom/). Both guards were
  executed for real on an authorized host: neither target carried a `CRITICAL`
  or `HIGH` finding, so no exception was recorded, and the full result —
  including the recorded `MEDIUM` and `LOW` findings — is in
  [the validation record](docs/proof/security/v1-s2-006-pr1-validation.md).
  Neither guard runs continuously: no continuous-integration service is
  selected ([ADR 0005](docs/architecture/decisions/ADR-0005-test-ci-and-certification-strategy.md)
  D6 stays undecided), so a result is current only as of the day a
  contributor produced it — the severity policy in
  [the control matrix](docs/security/control-matrix.md#the-vulnerability-scan-severity-policy)
  says so explicitly. `DR-07` and `DR-08` in
  [the deferred-risk register](docs/security/deferred-risks.md) are narrowed
  to what remains: no lane verifies that a check's own environment resolved
  from the scanned lockfile, and no build signature or provenance attestation
  is verified for the runtime image. No InferOps-owned container image exists
  in V1 — no `Dockerfile` is committed anywhere in this repository — so the
  "InferOps-owned image is non-root" acceptance criterion for this story is
  recorded as not applicable rather than satisfied; the only image any
  manifest references is the third-party runtime image the pre-existing
  pod- and container-security controls already cover.

### Fixed

- **The Sprint 2 completion review's blockers are closed and five stale claims
  are corrected.** The `V1-S2-004` certification workflow has now been *run*:
  one authorized invocation of `tools.runtime_certification certify
  --confirm-real-runtime` certified at `C2`, with the runtime ready in
  285,828 ms against a 300,000 ms budget, one real completion returned in
  3,140 ms with runtime-derived token counts, and verified teardown. The
  result is promoted to
  [a reviewed record](docs/proof/serving/v1-s2-004-c2-certification-result.md),
  which also reports the two observations that disagree with expectation: the
  readiness margin is under five per cent, and neither the request nor the
  correlation identifier was echoed. A real model-cache **miss** was observed
  for the first time and is recorded in
  [its own document](docs/proof/serving/v1-s2-007-cache-miss-observation.md);
  observing a miss turns out to cost no download, because the classifier reads
  no network and the measured start refuses before creating a container, so
  `V1-S2-007`'s first acceptance criterion moves from *partially met* to
  **met**. `V1-S2-001`'s story evidence is reconciled in place against the real
  acquisition performed by `V1-S2-005-PR2` and a re-executed absent-state check
  and verified cache hit, and it now says plainly that resumption against the
  real source is still proved synthetically only. Five `README.md` status
  entries that described what one past change did — including "the experiment
  was not executed and no measured baseline exists", which stopped being true
  when `V1-S2-005-PR2` merged — now describe the repository. The security
  paragraph in
  [the claim and test matrix](docs/testing/claim-test-matrix.md) no longer says
  no image scanner or dependency auditor has been run, which stopped being true
  when `V1-S2-006-PR1` merged; a secret scanner genuinely has not been run and
  the corrected wording still says so. The whole reconciliation, including the
  governance deviation that `V1-S2-005` consumed three merged PRs where the
  locked plan allows two, is in
  [the Sprint 2 completion review](docs/proof/serving/sprint-2-completion-review.md).

- **A test was enforcing a claim the repository had outgrown.** The telemetry
  and evidence catalog declared `recordsProduced: 0` for all four evidence
  templates and `tests/telemetry/test_telemetry_catalog.py` asserted that zero,
  so the count could not be corrected without the suite failing. It was true
  when [ADR 0006](docs/architecture/decisions/ADR-0006-telemetry-and-evidence-catalog.md)
  was accepted and false from the moment `V1-S2-005` published an experiment
  record and raw results in those formats. A record now declares its source
  template in one line beside its title, the catalog states one `experiment`
  record and five `raw-result` records, and the suite derives the count from the
  declarations instead of asserting a constant. Counting by section headings was
  considered and rejected: all four templates share the same required headings,
  so a structural match cannot tell an experiment record from an environment
  one. `environment` and `claim-evidence` have still produced nothing, and a
  test now fails if that stops being visible.

- **The registered local serving baseline is unblocked and has produced its
  first measured result.** An authorized execution found the experiment
  `V1-S2-005-PR1` registered could not succeed: the fixture sent a `system`
  message and a `user` message while the InferOps API accepts exactly one
  `user` message, and even a successful run would never have returned, because
  `run` blocked on `server.join()` after the measured phase instead of
  requesting its own server's stop. Both are fixed. The fixture now sends one
  message with the system instruction folded in — disclosed and defended in
  [the experiment record](docs/proof/serving/v1-s2-005-local-baseline-experiment.md#correction-to-the-registered-fixture)
  as a binary-acceptance correction rather than a measured-value change — and
  `tools.serving_baseline.core.load_experiment` now validates the committed
  fixture against `inferops.api.validation.parse_chat_completion` offline, so a
  fixture the API would refuse fails `check` rather than reaching an authorized
  run again. `execute` now requests its own server's stop from within
  `on_ready`, the pattern `tools.runtime_certification.certify` already used
  for the same reason, rather than changing the shared
  `tools.local_composition.run_foreground`. A third, pre-existing defect
  surfaced by the same run is also fixed: a security test's filesystem walk did
  not know `.cache/` was ignored, so it flagged the acquired model artifact as
  a candidate for publication; its ignore list and `.gitignore`'s own
  convention are now aligned.

  **The corrected experiment was executed on an authorized host, and all five
  pre-registered thresholds are met:** 33 of 33 requests succeeded (3 warm-up,
  30 measured), model load 269,079 ms against a 300,000 ms budget, P50
  6,422 ms / P95 17,718 ms / P99 23,516 ms, 0.121 requests/s, 2.067 output
  tokens/s. Full evidence, including an independently recomputed percentile
  check and a named limitation in the periodic CPU sampling, is in
  [the raw result record](docs/proof/serving/v1-s2-005-baseline-raw-results.md).
  As before, none of this is a benchmark and none may be published as one.

### Added

- **The InferOps LLM stack is packaged as a Helm chart, and the chart cannot
  quietly install the wrong one.** [`charts/inferops-llm/`](charts/inferops-llm/)
  renders the platform API and — under the real profile — the `llama.cpp` server
  [ADR 0002](docs/architecture/decisions/ADR-0002-model-and-serving-runtime.md)
  selected, as one release: a ServiceAccount, a ConfigMap, and one Deployment and
  Service per workload. It renders exactly the rows
  [the ownership inventory](docs/architecture/resource-ownership.md) gives Helm,
  it renders **no** `Namespace` and **no** `PersistentVolumeClaim` because those
  are Terraform's, and the three Helm-owned rows it does not render —
  `model-acquisition-job`, `workload-network-policy`, and
  `telemetry-scrape-configuration` — are declared as deferred in the chart's own
  metadata, so a row that is neither rendered nor declared fails the build.
  `values.schema.json` is applied by Helm on every install, upgrade, template,
  and lint: every image is a `sha256` digest and a tag is refused wherever it is
  written, every workload states both a request and a limit, and a secret
  reference has a name, a Secret, and a key and no member that could hold a
  value. `profile` is `mock` or `real`, **has no default**, and an omission
  renders nothing — which is
  [rule 5 of the mock and real boundary](docs/serving/mock-and-real-boundary.md)
  made structural rather than remembered. The adapter selection is written in one
  template helper from `profile` and from nothing else, the serving capability is
  derived with it and appears nowhere in the values contract, and `extraEnv` is
  *refused* rather than merged if it names any variable the chart derives —
  because a merge that lands last is exactly how a real release comes to publish
  `mock`. **Every** free-form values map that reaches a rendered object is
  refused rather than merged when it collides with a derived name — `extraEnv`,
  `secretRefs`, `commonLabels`, `commonAnnotations`, and the three per-object
  annotation maps — because appending a label a mapping already carries produces
  the key twice and every parser keeps the appended one. That covers
  `inferops.io/profile`, and it covers `app.kubernetes.io/part-of` and
  `inferops.io/lifecycle`, which are the labels a scoped teardown is planned to
  select on. A real release refuses a `mock-`labelled model identity and a mock
  release refuses a model revision, an alias, a container path, a cache claim, or
  a secret reference at all, which are the refusals
  `src/inferops/adapters/` already raises at start-up, moved to render time so
  the release is never built. The label half of that guard was missing from the
  first draft and independent review broke the claim with a single schema-valid
  `--set`; the chart was fixed rather than the claim narrowed, and
  [the validation record](docs/proof/architecture/v1-s3-002-pr1-validation.md)
  records what was found, including two smaller identity holes — the pod name
  supplied through the downward API could be overwritten by `extraEnv`, and
  sprig's `merge` gave a per-object annotation map precedence over the derived
  attribution, so one release could disagree with itself about its own tenant. Both profiles lint under `--strict` and validate
  against Kubernetes `1.34.0`; the exercised refusals, the seven checks that the
  new suite is not vacuous, and everything this change did **not** do are in
  [the validation record](docs/proof/architecture/v1-s3-002-pr1-validation.md).
  **Nothing has installed this chart.** No InferOps API image is published — no
  `Dockerfile` is committed anywhere in this repository, so both committed values
  files carry an image digest that is the SHA-256 of a stated string and resolves
  to nothing — and no cluster has seen any of it. Probes and the release
  lifecycle arrived in `V1-S3-002-PR2`, below, and
  `a-helm-release-installs-and-uninstalls-without-residue` remains a recorded
  coverage gap.

- **The Helm chart is checked against the ownership inventory on every run of the
  default lane, on a machine with no Helm.**
  [`tests/architecture/test_helm_chart.py`](tests/architecture/test_helm_chart.py)
  reads the chart and two committed `helm template` renders of it and holds them
  to the release half of the inventory, to the accepted pins, and to the six pod
  and container security properties every workload manifest here carries. The
  runtime image digest, the model revision, and the exact argument vector the
  chart passes the runtime are compared against
  `deploy/serving/runtime/container-package.v1.json`,
  `docs/serving/model-source.v1.json`, and
  `docs/serving/runtime-profile.local.v1.json`, so a fixture drifting from an
  accepted decision fails the build rather than sitting unread. Where `helm` is
  installed the suite additionally re-renders and compares, which is what keeps
  the snapshots output rather than prose; where it is not, those two tests skip
  and everything else still runs. `helm` joins `shellcheck` and `kubeconform` in
  [the prerequisites](docs/prerequisites.md) as a separate, unpinned, and
  **optional** install. The suite reads files: it installs nothing, contacts no
  cluster, and certifies nothing about a release.

- **The local cluster can now be verified as a step of its own, and the host's
  disk is checked before anything is created.**
  `scripts/environment/cluster-verify.sh` answers five questions about a cluster
  and changes nothing: does kind report one by this project's name; is the
  project-scoped kubeconfig present and does its context resolve to node
  containers kind labelled for this cluster; is the node running the pinned
  image digest; is every node Ready and every `kube-system` pod running or
  completed; and does the server report the minor version the pin should
  produce. It runs all five before reporting, so a cluster that is wrong in
  three ways says so once, and on failure it prints the cluster list, the
  labelled containers, and recent `kube-system` events before exiting non-zero.
  `cluster-up.sh` now verifies the cluster it just created by running that
  script rather than by a second copy of the same checks, and
  `proof.sh` runs it again standalone in each cycle — because "verify is
  repeatable" is a result only if the same read-only script reaches the same
  answer twice. It was run five times in
  [the lifecycle result](docs/proof/environment/v1-s3-001-pr1-cluster-lifecycle.md):
  four against a live cluster in three different states, all passing, with the two
  run back to back byte-identical under `diff`; and once against the torn-down
  cluster, where it correctly reported three problems at once and failed.

  `preflight.sh` now checks the third figure of
  [ADR 0001](docs/architecture/decisions/ADR-0001-local-development-environment.md)
  (D7)'s minimum tier, which had never been checked: **20 GB free on one
  volume**. Where the container engine's data directory exists on the host
  filesystem that directory is measured; on Windows and macOS it does not exist
  out here, so the volume the engine places its virtual disk on by default is
  measured instead and reported as the proxy it is. `INFEROPS_DISK_VOLUME`
  selects a different volume for a contributor who has relocated the virtual
  disk; it cannot lower the threshold or skip the check. The processor figure
  moved out of a bare literal in `preflight.sh` and into `lib.sh` beside the
  other two, and all three are now held to D7's table by test rather than by
  memory.

  Three scripts silently ignored arguments — `preflight.sh`, `smoke.sh`, and
  `verify-clean.sh` — and now refuse them. On a script that deletes things, the
  difference between a partial teardown and a full one should never be decided
  by a typo nobody was told about. The gap was found by the new test suite, not
  by review.

- **The cluster lifecycle scripts' safety rules are now enforced by a test
  rather than by review.**
  [`tests/architecture/test_cluster_lifecycle_safety.py`](tests/architecture/test_cluster_lifecycle_safety.py)
  reads every script under `scripts/environment/` as text and holds it to what
  ADR 0001 (D5, D6) says about it: every `kind delete cluster` names the
  cluster, every object deletion is namespaced and either label-selected or
  named, every mutating `kubectl` call goes through the wrapper that pins
  `--kubeconfig` and `--context`, nothing prunes the engine or sweeps all
  namespaces or writes to the default kubeconfig, the read-only scripts contain
  no mutating verb at all, every script refuses an argument it does not
  understand, and the node-image pin is one value in `lib.sh`, the kind config,
  the ADR, and the runbook. It executes nothing; what the scripts do to a real
  cluster stays the cluster-smoke layer's evidence. Three of its rules failed on
  the code as it stood, and two of those were fixed in the scripts.

- **A second engineer can now diagnose a local runtime failure from what they
  observed.** [The local runtime troubleshooting guide](docs/serving/local-runtime-troubleshooting.md)
  is organised by symptom rather than by component, because the symptom is the
  only input available on arrival. It covers prerequisites, model acquisition and
  integrity, disk, ports, memory and OOM, slow model load, readiness, the three
  separate timeout budgets, cache corruption and staleness, API-to-runtime
  connectivity, shutdown and cleanup, and the case where the honest answer is
  that the host cannot support the profile. **Every diagnostic on it was
  executed** on one host and recorded in
  [the validation record](docs/proof/serving/v1-s2-008-pr1-validation.md); the
  recoveries that start a container, transfer 1.71 GiB, or take a measurement
  remain authorization-gated and were **not** run, and the page labels each one.
  Kubernetes is excluded deliberately: no chart exists and no documented workflow
  deploys a manifest, so a section for it would be advice rather than
  documentation.

  One host behaviour was reproduced rather than inferred and is published because
  it costs a second engineer an hour: **Git Bash on Windows rewrites
  `INFEROPS_LLAMA_SERVER_MODEL_PATH`**, so a correct container-absolute
  `/models/Qwen3-1.7B-Q8_0.gguf` arrives as a Windows path and the adapter
  refuses it, naming a value nobody typed. `MSYS_NO_PATHCONV=1` or PowerShell
  avoids it. No code changed for this; it is a shell behaviour, and the guide now
  says so.

  The guide is machine-checked rather than proofread.
  [`tests/serving/test_local_runtime_troubleshooting.py`](tests/serving/test_local_runtime_troubleshooting.py)
  holds every command it prints to a module and subcommand that exist, every exit
  code to the constant the tool returns, and every port, byte count, budget,
  memory bound, cache root, ownership label, and capacity floor to the record
  that owns it. It also refuses a credential-shaped flag or value anywhere in the
  file and reads the port tuple out of the diagnostic a reader actually pastes
  into a shell, rather than settling for the number appearing somewhere on the
  page. Independent review before merge caught the guide calling
  `INFEROPS_LLAMA_SERVER_STARTUP_BUDGET_MS` a 300,000 ms *default* when the code
  requires it with none — a reader who trusted that row would have omitted it and
  got a refusal — and the check that now compares each row's requirement claim
  with the set of variables the distribution refuses to run without exists
  because every individual number on the page had been correct while the sentence
  around one of them was not. The guide additionally publishes an unresolved
  limitation instead of hiding it: one recorded run on the measured host exceeded the 300,000 ms
  startup budget, and the budget has **not** been raised, because raising it
  would hide the finding.

- **One ordered model lifecycle state model now spans the cache and the runtime,
  and a measured cold and warm start comparison exists.** The versioned
  [lifecycle record](deploy/serving/lifecycle/model-lifecycle.v1.json) and
  [`tools.model_lifecycle`](tools/model_lifecycle/) command publish eight states —
  three describing what the cache holds, five describing a process — with the
  answer each probe gives in each one, the transitions between them, and the
  startup, shutdown, and restart ordering. Loading the record refuses drift from
  the container package's probe ports, statuses, budgets, and stop timeout, from
  the model source record's cache root, and from
  [`inferops.api.lifecycle`](src/inferops/api/lifecycle.py)'s own drain budget, so
  the numbers have one home rather than four. It also refuses the record's central
  invariant being broken: **`runtime-loading` and `runtime-draining` must pass
  liveness while reporting readiness false.** A record that lets those agree
  describes a deployment a liveness probe restarts mid-load, which is exactly what
  a probe pointed at the runtime's `503`-while-loading health endpoint would do.
  Cache hit, miss, and partial are classified offline and only a hit proceeds
  without a network connection; a start from a miss refuses rather than
  downloading. Documented in
  [the model lifecycle guide](docs/serving/model-lifecycle.md).

- **The comparison was executed three times on an authorized CPU host, and it
  does not show a cold/warm speedup.** Each run starts the pinned container,
  samples liveness and readiness *together* until ready, issues one bounded
  single-token inference probe, and removes the container in a `finally`; the
  artifact is re-read and its SHA-256 re-compared between and after the two
  starts. Every acceptance property held in all three runs: every start was a
  cache hit, liveness passed in all 2,753 loading observations across the six
  starts with no drop in any of them, readiness stayed false until the runtime
  answered `200`, and the artifact verified unchanged after every restart.
  **The timing halves did not reproduce.** The warm start was slower every time,
  by 234 ms, 16,032 ms, and 68,532 ms, while the cold arm alone spread 82,157 ms
  across the three runs — larger than every delta measured within one. **No
  cold/warm effect is claimed in either direction.** The figures, and why this
  host cannot resolve one, are in
  [the cold and warm start record](docs/proof/serving/v1-s2-007-pr1-cold-warm-start.md).

- **The registered local serving baseline was executed on an authorized CPU
  host, and it failed — this repository still holds no measured baseline.** A
  model was downloaded and hash-verified, the pinned runtime was started, and
  thirty-three real requests were sent through the real InferOps API. **All
  thirty-three were refused with HTTP 400 `contract-invalid` before reaching the
  runtime, no inference ran, and no result file was produced.** Two defects in
  the baseline tooling cause this, both open and neither fixed here: the
  registered fixture sends a `system` message and a `user` message while the API
  accepts exactly one `user` message, and the `run` command blocks on
  `server.join()` after its final request so it never writes its raw records or
  summary. A third, pre-existing defect surfaced alongside them: a security test
  walks the filesystem without consulting git and so fails on any host that has
  actually acquired the model into the ignored cache. The evidence, including
  the verbatim refusal records and an offline reproduction that needs no
  container, is in
  [the raw result record](docs/proof/serving/v1-s2-005-baseline-raw-results-first-attempt.md)
  (the file this entry originally cited was superseded by the successful
  re-execution below and renamed to keep both records); the analysis and the
  follow-up work are in
  [the change-validation record](docs/proof/serving/v1-s2-005-pr2-validation.md).
  The only real timings the run produced are model-load times — 358,735 ms cold,
  which exceeds the 300,000 ms startup budget and fails the run outright, and
  284,406 ms warm — and neither is a benchmark of anything. `V1-S2-005` remains
  incomplete.

- **A repeatable local serving baseline experiment, registered before it is
  run.** The versioned
  [baseline descriptor](deploy/serving/baseline/local-baseline.v1.json) and
  [`tools.serving_baseline`](tools/serving_baseline/) command fix the request
  fixture, generation settings, warm-up, measured request count, concurrency,
  timeouts, and success criteria; capture a sanitized environment and the
  immutable model, image, and runtime pins; and turn one authorized run into a
  JSON Lines raw record set plus a deterministic summary that can be regenerated
  from it. Latency percentiles use nearest rank, so every reported figure is a
  value a request actually produced, and warm-up requests are recorded and then
  excluded from every distribution. Loading refuses a descriptor that drifts from
  the composition, the runtime profile, or the model record, and any answer
  carrying mock identity aborts a run rather than being recorded. The method is
  pre-registered in
  [the experiment record](docs/proof/serving/v1-s2-005-local-baseline-experiment.md)
  and documented in [the baseline guide](docs/serving/local-serving-baseline.md).
  **The experiment was not executed by this change and this repository holds no
  measured baseline.** The baseline is descriptive and may never be published as
  a benchmark.

- **A repeatable C2 real-runtime smoke certification for the composed serving
  path.** The versioned
  [certification descriptor](deploy/serving/certification/c2-smoke.v1.json) and
  [`tools.runtime_certification`](tools/runtime_certification/) command refuse a
  host below the selected package's engine CPU, engine memory, and free-disk
  needs before any container exists, wait for both bounded readiness boundaries
  through the existing local composition, send one fixed public request through
  the InferOps API, and refuse any answer carrying mock identity or mock
  capability metadata. A certified run writes a `local-real-cpu` record labelled
  `local real runtime`; a failure exits non-zero and stores diagnostics naming
  the stage. Neither record retains a prompt, a completion, or a host identifier.
  Default tests drive the workflow through injected seams only. **No authorized
  real run was performed by this change, so no `C2` claim is made.**

- **One guarded host-local workflow composes the InferOps API with the selected
  real runtime.** The versioned
  [composition descriptor](deploy/serving/local/composition.v1.json) and
  [`tools.local_composition`](tools/local_composition/) command validate exact
  real-adapter configuration, start and ready the pinned runtime before the
  loopback API, keep the process attached, and drain the API before
  ownership-scoped runtime cleanup. Default tests cover rendering and lifecycle
  through controlled seams, including a loopback HTTP request to the real adapter
  type over a synthetic transport. No real runtime or model was executed by this
  change.

- **A repeatable standalone package for the selected local runtime.** The
  [package descriptor](deploy/serving/runtime/container-package.v1.json) and
  [`tools.runtime_packaging`](tools/runtime_packaging/) command pin the image and
  process, mount only the hash-verified external model, publish only loopback,
  constrain resources and process privileges, and provide guarded startup,
  readiness, bounded inference smoke, and ownership-scoped shutdown. Repository
  tests exercise the lifecycle through synthetic seams; this change did not pull
  the image, download the model, or execute the real runtime.
- **A digest-pinned local CPU profile for the selected LLM runtime.** The
  [machine-readable profile](docs/serving/runtime-profile.local.v1.json) fixes the
  `llama-server` executable and arguments, external read-only model mount, port,
  CPU and memory envelope, context and generation defaults, timeouts, readiness,
  liveness, metrics, and no-embedded-secret boundary. The offline
  [`tools.runtime_configuration`](tools/runtime_configuration/) check validates
  the record against the runtime/model pins and the real adapter without pulling
  an image, reading model bytes, or starting a process. Runtime packaging and
  local-real startup/readiness evidence remain deferred.
- **Revision-pinned, resumable acquisition for the selected open model.** The new
  [model source record](docs/serving/model-source.v1.json) makes the upstream
  repository, immutable revision, Apache-2.0 licence reference, expected byte
  count, SHA-256, and workspace cache layout explicit. The
  [`tools.model_acquisition`](tools/model_acquisition/) command checks prerequisites
  without network access, safely resumes a `.part` transfer, verifies size and hash
  before atomic promotion, reports verified cache hits, and removes only the
  documented cache after explicit confirmation. Model artifacts are ignored by
  Git, and repository tests exercise the workflow with tiny synthetic bytes; this
  change does not download the selected model or package its serving runtime.
- **A verified Sprint 1 developer quick start.**
  [`docs/developer-quick-start.md`](docs/developer-quick-start.md) gives the shortest
  repository setup, workload scaffolding, validation, generated-contract test, and
  mock API workflow. It also publishes the optional real-adapter smoke boundary:
  the run is manual and authorization-gated, a skip is not a pass, and this change
  did not download a model, start a runtime, or produce real-runtime evidence.
  Cleanup and platform-specific shell forms are included.
- **The InferOps API emits telemetry. It is the first component here that emits
  anything at all.** The accepted catalog assigns nine metrics to the
  `inferops-api` emitter and, until now, every one of them was a specification for
  a component that did not instrument itself: `emissionStatus` read `nothing-emits`
  and the `/metrics` endpoint served a body of comments explaining why. Eight of
  those metrics are now produced — the request counter, the error counter, the
  latency histogram, the in-flight gauge, the readiness-failure counter, the token
  counter, the process CPU counter, and the identity metric — rendered on
  `GET /metrics` in the Prometheus text exposition format, and the API writes the
  structured log record the catalog specifies for every request it receives and
  every request it closes. [What it emits](docs/telemetry/api-instrumentation.md)
  is published with a real scrape, real records, and the variables a deployment
  states its identity in.
- **`ADR 0002`'s `T7` obligation is discharged.** The selected runtime exposes no
  cumulative request counter; that was measured, it is the threshold the record
  documents as failed, and the compensating plan was that the component receiving
  the requests would count them. `inferops_inference_requests_total` now does.
  Nothing about the runtime is fixed, and the limitation saying so stays.
- **A refused request is counted like any other.** The close is in a `finally`, so
  a body outside the frozen subset, a refusal from the adapter, a drain, and an
  unexpected failure each increment the counter, decrement the in-flight gauge, and
  produce a latency observation. A counter that only counts the paths somebody
  remembered is a success rate that flatters the platform. A timeout is a separate
  outcome from a server error, decided by the condition rather than the status,
  because a caller's deadline and a runtime's deadline carry different statuses and
  are the same operational event.
- **The placement rules stopped being a property of a document.** A metric
  declaration naming a label the catalog does not permit — a correlation
  identifier, a request identifier, a workload version, an owner, a pod, a measured
  duration, or any identity attribute — is refused when the metric is declared,
  before a series can exist. A label value that could inject a series into the
  exposition is refused too.
- **Redaction stopped being a rule and became a sink.** A log record is built
  through an allowlist of the attribute names the catalog publishes, and there is
  no name in it for a prompt, a completion, a provider error body, a secret, an
  authorization header, or a value read out of a submitted document — no message
  field, no `extra` mapping, no pass-through to the encoder. A rejected field is
  named in the refusal and its value never is. The suites now drive the application
  with a real prompt and a real adapter message and assert that neither reaches any
  record or any series, which is the check
  [the redaction rules](docs/telemetry/redaction.md) previously recorded as absent.
- **Mock telemetry says it is mock, in three places.** The exposition opens with a
  comment naming the mock adapter and stating that it certifies no serving runtime,
  the identity metric carries `inferops.adapter.kind="mock"`, and every operational
  series and every record carries the mock runtime's registered identifier. The
  adapter kind is derived from the adapter selection and never configured beside
  it: a second variable carrying that label would be a way to compose a real
  adapter and publish `mock`.
- **A deployment states its own identity, and an unstated one stays empty.** Ten
  optional variables carry the service version, environment, capability, release,
  pod, model revision, runtime image digest, workload, workload version, and owner.
  A deployment that states none of them still starts, still serves, and still
  emits, with its identity labels visibly empty — because a `service.version` of
  `unknown` sorts, groups, and reads like a release somebody shipped. The workload
  identity is configuration and **not** a caller's header: a workload identifier
  read off a request would be an unbounded metric label wearing a bounded one's
  name.
- **The catalog and the code are compared in both directions.**
  [`tests/telemetry/test_api_telemetry_agreement.py`](tests/telemetry/test_api_telemetry_agreement.py)
  reads the accepted record and the distribution's declarations and fails when they
  disagree on a name, an instrument, a label set, a bucket count, or which metrics
  are emitted at all.
  [`tests/api/test_api_observability.py`](tests/api/test_api_observability.py)
  drives the application and asserts on what it actually emitted.

- **The three surfaces that read a WorkloadContract are compared, not just each
  checked.** The published JSON Schema, the offline validator, and the platform
  domain each had a correct suite of its own and nothing compared two of them,
  which is where drift actually appears: a rule tightened on one side, an
  identifier renamed on another, a supported version added to one constant.
  [`tests/contracts/test_platform_contract_regression.py`](tests/contracts/test_platform_contract_regression.py)
  asserts that all three accept every valid fixture and every generated workload,
  that the platform refuses every invalid one, that the layer recorded for each
  refusal is the layer that actually produces it, that every rule identifier the
  domain cites is a published semantic rule and every published semantic rule is
  one it implements, and that the three constants naming the supported contract
  version agree. One divergence is recorded rather than hidden: the domain does
  not refuse the mock-dressed-as-real fixture, the schema does, and a two-way set
  assertion means that fact cannot change silently in either direction.
- **A generated mock workload cannot be edited into real serving.** The four
  edits the contract document names — the environment, the serving capability, the
  accelerator, and a cited real-runtime proof — were already refused on the
  *committed* mock fixture. They are now refused on the scaffolder's own output,
  which is the document most likely to be edited after generation and the one
  nobody reviewed.
- **Every serving adapter this repository ships is discovered and held to the
  shared conformance suite.** The two subclasses existed; nothing asserted that
  the set of adapters covered was the set of adapters shipped, so an adapter added
  without a suite would have passed every check here.
  [`tests/adapters/test_adapter_contract_regression.py`](tests/adapters/test_adapter_contract_regression.py)
  walks the adapters package for classes that structurally implement the protocol,
  fails when one has no conformance suite, and compares the adapter-kind
  vocabulary across the three places it is written down — the kinds the domain
  accepts, the kinds the adapters declare, and the kinds the API can compose.
- **Every condition the API can refuse on is provoked, or recorded as unreachable
  with a reason.** The refusal sites were each exercised by hand, which left a
  condition added and never provoked passing every check in the repository.
  [`tests/api/test_api_contract_regression.py`](tests/api/test_api_contract_regression.py)
  drives the published table instead: fifteen of sixteen conditions are provoked
  and held to the code, flag, status, and identifier their own row declares, the
  sixteenth carries the reason no request can reach it, and the mapping is
  asserted exhaustive in both directions before any of it runs. Every published
  route is driven for the success shape, the correlation identifier, and the
  adapter kind.
- **A test inventory, and the checks that stop it going stale.**
  [The inventory](docs/testing/test-inventory.md) lists every pytest module in the
  repository, the layer and lane it belongs to, and the claim it protects — the
  answer to "if this claim stopped being true, which suite would fail", which
  previously meant reading forty modules and guessing.
  [`tests/testing/test_test_inventory.py`](tests/testing/test_test_inventory.py)
  compares it with the test tree and the committed strategy in both directions: a
  module absent from it fails, a module filed under a layer whose paths do not
  contain it fails, a module credited with a claim its layer cannot support fails,
  and a claim that no module names and no recorded gap explains fails.
- **Two published counts are now compared with the data that decides them.**
  Independent review of this change found the new inventory document saying "five"
  modules defend no published claim while its own section listed six, and found
  `docs/testing/README.md` saying seven of eleven test layers exist while the
  strategy document and its data said eight. Both are corrected and both are now
  checked: the inventory's two counts against the inventory data, and the layer
  count across the five living documents that state it, in both forms they use.
  Records under `docs/proof/` and changelog entries are deliberately excluded —
  both are statements about a moment that has passed, and rewriting one to match
  today would falsify a record rather than fix a document.
- **What the inventory found is published rather than quietly fixed.** Six claims
  have no pytest module behind them — two of them certified, defended by a shell
  check and by a manual download step — and six suites defend no published claim at
  all. Both lists are in the document with a reason each.

- **The command that generates a workload, and validates the one it wrote.**
  `python -m tools.workload_scaffold` gathers the parameter set, renders the
  template, and writes three files — then reads all three back, compares them to
  what was rendered, and validates the written contract *from disk* through the
  same function every committed fixture goes through. "A generated workload
  validates without a source edit" is now a statement about files rather than
  about the strings that produced them. Documented in
  [the template document](docs/scaffolding/workload-template.md), with a mock and
  a real example.
- **Nothing is written before a refusal, and nothing is overwritten.** The order
  is refuse, render, validate, plan, write, read back, so an invalid name,
  profile, or resource declaration fails while there is nothing to clean up — and
  the check for it asserts that the destination directory was never *created*,
  not merely that it is empty. An occupied destination is refused with its
  contents untouched: a generated workload is an ordinary committed directory the
  moment it exists, and there is no flag that would overwrite one.
- **A write that fails partway leaves what it found.** Every directory and file
  the command creates is recorded as it is created and removed in reverse order
  on any failure, including a failure of the read-back, taking back only what the
  command itself made. A rollback that cannot remove something says so rather
  than reporting a clean undo it did not achieve.
- **The generated project is proven by running it.** The suite executes the
  generated test skeleton under a real `python -m pytest` subprocess, against the
  directory the command created, from a working directory outside this
  repository, with no file edited in between. An import proves a module is
  importable; only a subprocess proves the command a generated quick start
  prints.
- **The command line is generated from a published option table**, so the flags
  and the template's parameter set cannot disagree — in either direction,
  including which parameters are required and what each default is. A closed
  vocabulary is deliberately not enforced by `argparse`: a `choices=` would turn
  a mistyped environment into a usage error that exits before the other ten
  parameters are read, and the whole point of the validator is that an author
  learns every reason in one pass. Exit status says which stage refused, so the
  command is usable as a gate.

- **A reusable LLM workload template, in two profiles, with a declared parameter
  set in front of it.** A generated workload is three files — the contract it
  declares, the quick start a second engineer reads, and a test skeleton that
  reads the contract back — and the same three whatever profile it is on, because
  a profile-shaped filename becomes a profile-shaped build step downstream.
  Rendering returns text: `render_workload` validates the whole parameter set,
  refuses it with **every** reason at once, and then produces a mapping of path to
  content. There is no partial result to clean up because this half has no file to
  write; the command that writes one is `V1-S1-006-PR2`. Described in
  [the template document](docs/scaffolding/workload-template.md).
- **What the template renders is held to the published contract, not to a copy of
  it.** The suite puts every rendered document through
  `tools.contract_validation` — the same function every committed fixture goes
  through — and then through `inferops.domain.workload`'s own validation pipeline,
  so "generated output validates without a source edit" is a checked property
  rather than a claim. Every format, vocabulary, and bound the parameter set
  applies is imported from the domain's value objects, which are themselves
  compared against the schema, so the template cannot accept a value the contract
  would refuse.
- **A generated mock says it is a mock in three places, and a generated workload
  cites no evidence it has not produced.** The profile block, the workload's own
  name — a `mock-llm` name must end in `-mock`, refused rather than silently
  appended — and the prose a reader meets first. `evidence.proofRefs` is absent
  from **both** profiles: a generated workload has executed nothing, and
  pre-filling it with the feasibility record would hand every generated workload a
  result produced by a different one. The mock and real quick starts stay distinct
  in both directions, and a check asserts the mock does not offer the
  real-runtime lane.
- **Three rules stricter than the schema, each a refusal rather than a silent
  correction**: the mock name suffix, an accelerator declaration that contradicts
  itself, and a required `description`. Each is documented as a tightening, because
  a tightening nobody wrote down is a tightening nobody can argue with. No refusal
  repeats the value it refused, for the reason the domain's errors give.
- **The one free-text parameter is escaped for each format it lands in, and
  gated in front of that.** `description` is prose, and prose substituted raw
  into YAML is YAML: a colon makes the document unparseable, a `#` truncates it
  silently, and a newline followed by an indented key adds a `metadata.annotations`
  entry nobody declared to a document that then **validates with zero findings**.
  All three were reachable and are now not. `substitutions()` publishes
  `description_yaml`, `description_markdown`, and `description_python` and never
  the raw string, so there is no key that would render prose unescaped; and the
  parameter gate refuses a description that is not a single line of printable
  text, so an author is told rather than handed a document with a `\n` in the
  middle of a sentence. A suite asserts the round trip character for character,
  over both profiles, for eleven descriptions a person would plausibly type — six
  of which fail without the emitters.
- **The runtime image digest and the model bytes are template-owned, not typed by
  an author.** A digest an author pastes is a digest nobody checked, so a generated
  `synchronous-llm` workload carries the pair ADR 0002 selected, and a test
  compares every pinned value against the committed compatibility matrix and the
  committed valid fixture. `modelRef` is a closed set for the same reason: the
  catalogue holds one entry per serving capability, and naming the other profile's
  identity is a single-word edit away from a document that would put a mock label
  on a real serving path.
- **The canonical error contract, served in full and keyed on a condition rather
  than a code.** Every refusal now carries `code`, `message`, `requestId`,
  `correlationId`, `retryable`, and `details`, and `retryAfterMs` where a delay was
  decided. The unit is a **condition** because the accepted record maps
  `capability-unavailable` twice — to a runtime that cannot be reached, which is
  retryable and a `503`, and to a caller asking for streaming, which is not and is
  a `400` — so a code-keyed table would have to answer one of them wrongly. Nine
  conditions are copied from
  [the accepted record](docs/serving/inference-api-surface.v1alpha1.json) and
  compared against it by a test; seven are this API's own, for routing, an
  oversized body, a draining deployment, and an adapter contradicting its own
  deployment, and each is marked as added rather than presented as accepted.
  Described in [the API document](docs/serving/inference-api.md#errors).
- **An adapter's own message no longer reaches a caller.** The previous change
  forwarded it, which was safe because every canonical message in this repository
  happens to be a constant — safe by review rather than by construction. An adapter
  is the component closest to a runtime's error text, a mounted weight-file path,
  an endpoint, and a prompt, and
  [the redaction rules](docs/telemetry/redaction.md) name a provider error body as
  the surface most likely to be logged, pasted into a ticket, and kept. A canonical
  error raised below the edge is now answered with this API's own message for its
  condition, and a suite raises messages carrying a path, a host, and a prompt
  fragment to assert none of it comes back.
- **Configuration-driven adapter selection, with no default and no fallback.**
  `INFEROPS_SERVING_ADAPTER` is required and takes `mock` or `real`; unset, empty,
  and unrecognised all select **nothing**, and a `real` selection whose runtime
  settings are missing or malformed is **refused rather than answered with a
  mock**. That is boundary rules 5 and 4 held at the one place a deployment is
  assembled, and the suite for it is mostly refusals for that reason. The adapter
  kind is **derived** from the selection rather than configured beside it, so no
  configuration can compose a real adapter and label it `mock`; the existing check
  that every adapter result declares the deployment's own kind catches the rest.
  The mock's failure injection and latency get no variable at all — those are test
  inputs, and a variable that made a deployment produce a canonical error on demand
  would be reachable wherever the deployment ran.
- **`version-unsupported` is reachable, from the only place a caller can name a
  version.** A request to `/v2/chat/completions` names an API version this
  deployment does not serve, which is a different refusal from `/healthz` — a path
  nobody publishes. This surface reads no version header and the accepted record
  defines no request-body extension member, so the path is where it is decided.
- **End-to-end suites for both halves of the boundary.**
  [`tests/api/test_api_end_to_end_mock.py`](tests/api/test_api_end_to_end_mock.py)
  drives configuration to response for a success and for every failure the mock
  can produce — reading the scenarios from the mock's own enumeration, whose
  failing members *are* the canonical codes, so a code the domain gains will fail
  the suite until this API maps it. Its real counterpart,
  [`tests/realruntime/test_api_real_adapter_smoke.py`](tests/realruntime/test_api_real_adapter_smoke.py),
  puts the API in front of the real adapter composed from configuration and is
  **deselected by default**. **It has not been run against a runtime**: the lane is
  authorization-gated and was not entered, and
  [the validation record](docs/proof/serving/v1-s1-005-pr2-validation.md) says so
  rather than presenting a skipped session as a green one.

- **The user-facing InferOps API, which is the first component here that answers a
  request.** [`src/inferops/api/`](src/inferops/api/) registers the five endpoints
  [ADR 0010](docs/architecture/decisions/ADR-0010-inference-api-compatibility-surface.md)
  decided a story earlier and answers each of them through the serving adapter it
  is composed with: a synchronous chat completion, the model list with the runtime
  descriptor beside it, liveness, readiness, and metrics. The compatibility shape
  is admitted at the edge and translated there, so nothing compatibility-shaped
  crosses into the platform domain and nothing runtime-shaped crosses back out.
  Described in [the InferOps inference API](docs/serving/inference-api.md).
- **It imports no HTTP framework, because the dependency rule leaves no room for
  one.** The application implements the ASGI calling convention directly — a
  callable over a scope, a receive, and a send — which is a convention rather than
  a package, so
  [ADR 0004](docs/architecture/decisions/ADR-0004-component-and-ownership-boundaries.md)
  is obeyed without a framework-shaped hole in the design, and the distribution
  still declares no runtime dependency at all. **This repository ships no ASGI
  server**, so nothing here has bound a socket: the suites drive the application
  through its own interface, which establishes what the application decides and
  nothing about HTTP, and
  [the validation record](docs/proof/serving/v1-s1-005-pr1-validation.md) says so
  rather than presenting a green session as a served API.
- **A composition point with no default adapter.** The adapter is handed to the
  application in code. A mock that could become the live adapter by omission is
  what [the boundary rule](docs/serving/mock-and-real-boundary.md) forbids, so
  there is nothing to omit — and the kind the deployment was composed with is
  checked against every result the adapter returns, so a `mock` deployment serving
  a `real`-labelled result is refused rather than published with a label nobody
  can rely on. Selecting that adapter from configuration is the entry above.
- **The strict unknown-member policy, enforced rather than described.** A member
  outside the frozen subset is refused and the refusal names the member and never
  its value — including the upstream defaults a client library sends by habit,
  which is the cost the accepted record chose openly. Three refusal suites carry a
  canary value in the position a naive implementation would echo, and assert it is
  absent from the response.
- **Graceful shutdown as the equivalent the record chose over an endpoint.**
  Readiness goes false *before* anything drains, in-flight work finishes under a
  bounded budget that reports whether it ran out, and the adapter is released last.
  An HTTP route that stopped the process would be an unauthenticated remote-stop
  control on a surface with no authentication in V1.
- **The `mock-integration` test layer, which was registered and empty since
  `V1-S0-006`.** [`tests/api/`](tests/api/) now runs the API end to end against the
  labelled mock adapter and against controlled doubles, under the `mockintegration`
  marker the default lane already selects. A request stays counted until its
  response has been handed to the server rather than until the adapter answered,
  because a drain that returned in the gap between those two would report a clean
  shutdown over a response nobody received — and the suite reads the in-flight
  count from inside the send, which is the only place that distinction is visible.

- **The serving adapter for the selected real runtime, which generates text or
  fails.** The previous change deliberately shipped no `ServingAdapter` for
  `llama-server`, on the ground that a class satisfying the protocol's shape while
  its `infer` could not generate anything would be a mock wearing a real adapter's
  name. `LlamaServerAdapter` is the other half: it composes the pins, settings,
  configuration translation, readiness mapping, metadata parsers, and capability
  declaration that package already held, and adds a transport seam, an inference
  client, two bounded deadlines, and the mapping from a runtime failure to a
  canonical error. It is held to the same conformance suite the mock adapter and
  the in-memory double inherit. Described in
  [executing real inference through the adapter](docs/serving/real-runtime-inference.md).
- **A transport that is a parameter rather than a private method.** The adapter is
  constructed with one, so composing an adapter is where the decision to open
  sockets is made, a suite can exercise every branch against controlled responses
  without intercepting the standard library, and the object that could manufacture
  a `real`-labelled result without a runtime lives in the test file that uses it
  rather than in the distribution. The concrete transport is built from
  `http.client` — the standard library's own HTTP, not a client library — because
  [the dependency rule](docs/architecture/decisions/ADR-0004-component-and-ownership-boundaries.md)
  forbids anything else, and that constraint produced three properties worth
  having: no redirect is followed, so a request body cannot be moved to a host the
  settings never validated; a response body is read under a 1 MiB bound, so a peer
  cannot decide how much a 3 GiB pod allocates; and a connection is opened per
  request and closed in a `finally`.
- **An error mapping copied from the record that decided it, not invented.** Every
  condition the adapter can reach carries the identifier
  [the accepted API surface](docs/serving/inference-api-surface.v1alpha1.json)
  publishes for it, and a test reads that file and fails when a copy drifts. One
  of the six was ever observed happening — the `503` the runtime answers while it
  loads — and the table says which, because five mappings and one observation are
  not six equal facts. `rate-limited` is never produced: V1 has no rate limiter,
  the accepted record lists the code among those this platform does not emit, and
  a runtime answering `429` is an `internal-error` like any other unexpected
  status rather than an observation of a limiter that does not exist.
- **Two deadlines, and the outer one is deliberately the longer.** The transport is
  handed the configured budget; the call is wrapped in a backstop of that budget
  plus a grace. The inner produces `upstream-timeout` — the runtime ran out of
  time — and the backstop produces `request-timeout`, and it exists because a
  transport is a value a caller supplies and a protocol cannot enforce the promise
  it asks for. The grace is what makes the pair work: both clocks would otherwise
  be set to the same duration while the outer one starts first, so it would win by
  the dispatch cost every time and `upstream-timeout` would be a code nothing
  could produce. Every runtime call is under both, the readiness probe included,
  because that probe is reached implicitly by the first inference call. A fired
  deadline closes the socket, since a thread cannot be cancelled and the worker
  would otherwise hold its socket until the far side chose to answer.
- **A real-runtime smoke suite that has not been run.**
  [`tests/realruntime/`](tests/realruntime/) drives the adapter against a live
  `llama-server` holding the pinned model, under the `realruntime` marker the
  default expression deselects. It reads its settings from the process environment
  and **skips** when they are unset, because a missing endpoint means nobody asked
  for a real run rather than that a real run failed. The lane is manual and
  authorization-gated and was not entered, so the story's criterion requiring one
  real generated response through the adapter is **still unmet** and
  [the validation record](docs/proof/serving/v1-s1-004-pr2-validation.md) says so
  rather than presenting the code as the proof.
- **The configuration and inspection half of connecting InferOps to the selected
  runtime — and no adapter, deliberately.**
  [`src/inferops/adapters/llama_cpp/`](src/inferops/adapters/llama_cpp/) holds the
  runtime image digest and the model revision, file, size, and published hash from
  ADR 0002; the operator settings and environment variables that configure a
  `llama-server` deployment; the translation from platform configuration into
  runtime configuration and back; the health-status mapping; the metadata parsers;
  and the capability declaration. There is no `ServingAdapter` implementation in
  it, because a class satisfying the protocol's shape while its `infer` could not
  generate anything would be a mock wearing a real adapter's name — and
  substituting a mock for a missing real result is a defect under
  [the boundary rule](docs/serving/mock-and-real-boundary.md) rather than a
  fallback. Described in
  [the runtime configuration document](docs/serving/real-runtime-configuration.md).
- **Readiness that is false until the runtime says otherwise.** The selected
  runtime answers `503` while it loads its weights and `200` once it can serve, and
  that is the behaviour the Sprint 0 trial found which no mock could have
  surfaced. A readiness tracker starts in `not-probed`, exposes no setter, and
  reaches `ready` only through an observed `200`; a later `503` takes readiness
  away again, because a replaced pod is a fresh process with a fresh load. Any
  other status is `unexpected-status` rather than `loading`, since treating an
  unknown answer as temporary is how a permanently broken runtime gets waited on
  forever.
- **Pins that are compared to their sources instead of trusted.** Every constant
  copied out of ADR 0002, the feasibility record, and the compatibility matrix is
  asserted against the file it came from, including field by field against the
  committed `synchronous-llm` example, so a drift between the accepted decision and
  the code is a failing assertion rather than something a reader has to notice. A
  workload document naming a different image digest, model revision, weight file,
  size, or hash is refused with the field path the contract publishes and without
  the value it refused.
- **Nothing ADR 0002 left undecided acquired a default.** The context length and
  the thread count are required inputs with no default, because that record states
  they remain undecided and that the values the trial ran were stated inputs rather
  than recommendations. Omitting one is a refusal naming the variable. The single
  setting that does default is the runtime's own metrics endpoint, which defaults
  to on because ADR 0002's `T7` exception is argued on its existence — so turning
  it off is the deviation, and the deviation is what gets written down.
- **A deterministic mock serving adapter, and the safeguards that stop it being
  read as a real one.** [`src/inferops/adapters/`](src/inferops/adapters/) holds the
  first implementation of the serving interface the domain owns. It replays
  [one committed response fixture](contracts/workload/fixtures/mock-llm-chat-completion.response.json),
  requires no model file, credential, container engine, cluster, or network, and
  produces the same answer every time. Each canonical failure a caller has to handle
  — `model-not-ready`, `request-timeout`, `upstream-timeout`, `rate-limited`,
  `internal-error` — is reachable by construction, and the scenario's name *is* the
  code it produces, so the two cannot drift apart. What it refuses to do is the other
  half: it declines a model identity that is not mock-labelled, declares real model
  inference and token counting unsupported rather than inventing either, reports no
  model revision, and carries its own `mock` label in every result, in its runtime
  identity, in its telemetry attributes, and in a self-describing block that matches
  the one the fixture already carries. Described in
  [the mock serving adapter document](docs/serving/mock-serving-adapter.md).
- **The `adapter` test layer, registered and empty since `V1-S0-006`, now runs.**
  Seven of eleven layers exist. Its 76 checks live in
  [`tests/adapters/`](tests/adapters/) under the `adapter` marker rather than beside
  the domain suite, because the two layers carry different evidence classes and a
  mock result filed under a `local-static` layer is a misfiled result. Its ceiling is
  `C1` and the suite asserts that ceiling against the committed strategy data rather
  than restating it, so making the mock more faithful still raises nothing.
- **A conformance suite that is inherited rather than copied.** The obligations the
  `ServingAdapter` protocol publishes are written once in
  `tests/support/serving_conformance.py`; the in-memory double and the mock adapter
  each subclass it and supply an adapter. A new obligation is added in one place and
  every adapter is held to it in the same commit, which is what "reusable harness"
  had to mean to be worth the name.
- **The first InferOps-owned code that is part of the distribution**, in
  [`src/inferops/domain/workload/`](src/inferops/domain/workload/) and described in
  [the workload domain model](docs/domain/workload-domain-model.md). A
  `WorkloadContract v1alpha1` document becomes a tree of frozen, typed platform
  objects — workload identity, owner, profile, model and runtime reference,
  resources, scaling, integrations, security classification, attribution, and
  evidence references — with every identifier and formatted value carrying its own
  type rather than being a string that looked right when it was read.
- **The architecture's dependency rule, checked from the source instead of at review
  time.** `tests/architecture/test_domain_dependency_boundary.py` parses every
  module under `src/inferops/` and fails if one imports anything outside the
  standard library and this distribution. It is an allowlist rather than a list of
  forbidden packages, because the rule is about everything the domain is not,
  including whatever ships next year; a second check names the Kubernetes, Helm,
  Terraform, runtime-SDK, and HTTP-framework families in ADR 0004's own words. The
  domain declares no runtime dependency and reads no file, so a domain object is
  constructible from a wheel with no repository around it.
- **A round-trip property that makes "the domain loses nothing" checkable.**
  `WorkloadContract.as_document()` rebuilds the wire form, and a test asserts over
  every committed valid fixture that it rebuilds the document it was given exactly.
  A field the parser forgot to read is a field missing from the result; a field it
  defaulted is one that appears where the author wrote none. Absence is preserved
  for the same reason: an absent `proofRefs` and a declared empty one are different
  documents, both comply, and rendering one as the other would make a document say
  something its author did not write.
- **Contract-version handling that is explicit and first.** The supported
  `apiVersion` set is a constant with one entry, and a document declaring another
  version — or none — is refused before any field below it is read, because every
  field path this package knows is a path in `v1alpha1`.
- **A drift test between the published schema and the domain's copy of it.** The
  domain cannot import a JSON Schema validator, so the patterns, vocabularies, and
  bounds are written twice; `tests/domain/test_workload_schema_agreement.py` reads
  the schema and fails if a single one of them disagrees in either direction, and
  additionally deletes each *unconditionally* required field from a committed
  fixture in turn and requires a refusal at that field's own address. The
  conditionally required profile block is a cross-field rule and is deliberately
  not enforced.
- **The `unit` test layer, which was registered and empty since `V1-S0-006`, now
  runs.** Six of eleven layers exist. Its 271 checks cover what parses, what is
  refused, and what a refusal is allowed to say — including that no message repeats
  a value read out of the document, asserted over every string of eight characters
  or more in a refused document, and that a refusal carries the `requestId` and
  `correlationId` a caller supplied and invents neither.
- **A stated boundary, with tests that assert the absence rather than leaving it to
  be discovered.** This change implements **no** semantic validation rule: the
  profile and its block are not paired, an inverted replica range is not refused, a
  duplicate secret name is not detected, and no canonical error code or rule
  identifier is assigned. Those are the published semantic layer and they remain the
  complete property of
  [`tools/contract_validation/`](tools/contract_validation/) until `V1-S1-001-PR2`
  brings them into the domain. Two tests parse documents that the published rules
  refuse, so that the line cannot move quietly in either direction.

- **A decided inference API surface, one story before anything freezes against it**,
  in [ADR 0010](docs/architecture/decisions/ADR-0010-inference-api-compatibility-surface.md)
  and [the surface document](docs/serving/inference-api-surface.md). The user-facing
  API is a **frozen subset** of the OpenAI HTTP API shape at the `/v1` prefix: five
  endpoints, the request and response fields of each, and everything outside it
  recorded as out of scope with a reason rather than left unmentioned. This is the
  decision `V1-S1-002` would otherwise have made by guessing an adapter signature and
  `V1-S1-005` would have made by typing a route.
- **A compatibility target that is a shape read on a date, not a promise to track
  one.** The strongest objection to adopting a compatible surface is that it is not
  this project's to version, so upstream movement becomes a break imposed on it. The
  answer is the freeze: the field lists are enumerated here, read from the response
  bodies the runtime actually returned on 2026-08-24 rather than from vendor
  documentation, and anything upstream adds later arrives only if a superseding record
  decides it should. The project-native alternative is compared on six criteria rather
  than dismissed, and the criterion it wins is recorded as won.
- **Streaming and token usage as declared capabilities rather than assumptions.**
  Streaming is `false`, published where a caller can read it, and refused with an
  explicit `retryable: false` because retrying does not make a capability appear.
  Token usage is `true` on the strength of the `usage` object the trial recorded, and
  it is `null` rather than estimated or zero-filled when an adapter does not supply
  it. Whether the selected runtime *can* stream was never exercised by the trial, and
  the record asserts nothing about it in either direction.
- **A canonical error mapping in which one row was observed and eight are
  specifications**, marked either way, plus **six of the thirteen canonical codes
  recorded as never emitted in V1** — each with a reason, because a code listed with
  no condition behind it is a claim that something checks for it. A test refuses a
  code that is neither mapped nor refused, refuses one that is both, and refuses a row
  claiming an observation the feasibility record does not contain.
- **ADR 0002's `T7` exception carried forward as an obligation rather than discharged.**
  The selected runtime exposes no cumulative request counter, so InferOps owes one.
  This record binds `inferops_inference_requests_total` and
  `inferops_inference_errors_total` — which already exist in the telemetry catalog
  with that reason in their notes — to this surface and to these codes. It adds no
  metric, and neither is emitted by anything.
- **An extension namespace, and the two halves of it kept apart.** `x_inferops` is one
  object-valued body member carrying what the compatibility target has no place for;
  `X-InferOps-` is the header prefix carrying transport metadata. No request-body
  extension member is defined, because correlation and workload metadata belong in
  headers a trusted component validates. Every response names the `adapterKind` that
  served it, which is the mock and real boundary made visible at the one place a
  reader looks.
- **`tests/serving/test_inference_api_surface.py`**, 184 checks over the committed
  surface, the decision, the document, the feasibility record, and the telemetry
  catalog. It also refuses a contract artifact for this surface appearing under
  `contracts/`, which is the rule the whole record is built around: **nothing is
  published until something serves it.** Nothing in this
  repository listens on a port, registers a route, or answers a request.

- **A Python toolchain that was executed before it was accepted**, in
  [ADR 0009](docs/architecture/decisions/ADR-0009-python-toolchain.md). A packaging
  layout, a dependency manager, a lockfile policy, a linter, a formatter, and a type
  checker are each named, each configured in a committed file, and each run on this
  repository with its command and result recorded. This is the decision Sprint 1
  would otherwise have made by writing its first package, and the two halves of
  ADR 0001 that proposed a task runner and a dependency manager and never installed
  either are superseded by it.
- **A distribution that exists rather than a layout that is described.**
  `src/inferops/` is a deliberately empty package, and a wheel and a source
  distribution were built from it and their contents inspected. The wheel contains
  `inferops/__init__.py` and its metadata and nothing else; `tools/` and `tests/`
  stay outside it on purpose, and the source distribution's include patterns are
  anchored to the repository root because an unanchored one ships whatever it found
  at any depth.
- **A committed `uv.lock` with 136 artifact hashes**, resolved across environment
  markers rather than for the platform that ran the resolver, plus a
  `requires-python` constraint on the 3.12 series and a `.python-version` that pins
  the series rather than a patch release. The recorded way to run a check is
  `uv run --locked`, which fails rather than silently re-resolving.
- **A rejection recorded as a decision.** No task runner is adopted. ADR 0009 D7
  argues it out — ADR 0001's own record said the margin between its candidates was
  preference rather than capability, `uv run --locked` already supplies the command
  prefix a runner would have wrapped, and a runner does not ship the utilities its
  recipes call — and a test refuses a `Taskfile`, a `justfile`, a `Makefile`, a
  `noxfile.py`, or a `tasks.py` appearing without that record changing.
- **The record is checked against the configuration it decided.**
  `tests/testing/test_toolchain.py` reads the two tables ADR 0009 publishes and
  compares them against `pyproject.toml` and `uv.lock`. A dependency bumped without
  updating the record fails; a version typed into the record that the lockfile does
  not pin fails. It also asserts what did **not** move: `pyproject.toml` declares no
  pytest table, and the eleven markers and the default marker expression are still
  in `pytest.ini`.

- **A threat model in which a control cannot claim enforcement it does not have**, in
  [ADR 0008](docs/architecture/decisions/ADR-0008-v1-security-baseline.md) and three
  documents under `docs/security/`. Every control declares how it is verified and
  where it acts, and its status is the value a committed table gives for that pair —
  never a word somebody typed. A control naming an automated test names the file and
  the function, and the suite fails if the function is not defined; a control claiming
  an implemented status names an evidence record, and the suite fails if the record is
  not committed. The failure this exists for is not a false claim: it is a list of
  twenty controls, four of which have tests, being counted as twenty by a reader six
  months later.
- **Thirty-two controls, twenty-two of them enforced by something, and the split
  published.** Ten act over committed documents, ten over manifests, two on the host
  through the environment scripts, three by review alone, three are specified for
  components that do not exist, and four are deferred outright. The distribution is
  the finding, and no status that may be called implemented exists without a record
  behind it.
- **Eight pod-security assertions and a digest pin, promoted from habit to property.**
  Every YAML document under `deploy/` was already non-root, read-only-rooted,
  capability-dropped, seccomp-profiled, token-free, escalation-free, and pinned by
  digest. A test now parses every one of them and fails if that stops being true. What
  it establishes is stated exactly: these are properties of five committed files that
  are smoke and trial apparatus, and this platform deploys none of them.
- **Least exposure at the caller boundary, and no pretence that it is access
  control.** No manifest here declares an Ingress, a NodePort, or a LoadBalancer, and
  a test refuses one that would. Reaching anything needs a deliberate port-forward
  from a machine that already holds the cluster's credential. It identifies nobody and
  limits nothing once something is inside, which is why authentication and rate
  limiting are register entries rather than paragraphs.
- **A sixth trust boundary, for publication.** The architecture maps the five a
  running system crosses; this project crosses a sixth on every commit, and it is the
  only one whose failures cannot be undone. Four properties are tested at it: nothing
  generated is committed, no file carries a personal filesystem path, no file carries
  a model artifact extension, and the secret-scan allowlist resolves. The fifth thing
  a reader would assume is tested is not — **no run of the scanner is recorded**, and
  a configuration file is not a result.
- **A deferred-risk register that is long on purpose.** Twelve risks V1 carries rather
  than reduces — no authentication, no rate limit, no tenant validation, no network
  policy, no admission control, an unauthenticated artifact transport, no dependency
  lockfile, no image scanning, no artifact availability, no secret lifecycle, no
  recorded scanner run, and nothing logged at all. Ten of the twelve block production
  use. Each declares why, what would have to be true, and — the field that does the
  work — what may not be claimed while it stands.
- **Four exceptions argued rather than absorbed.** The model download's transport
  reports certificate validation as disabled; the cluster identity guard is satisfied
  by a second cluster given this project's name; the secret-scan allowlist covers two
  directories wholesale; and the pod-security properties hold over apparatus rather
  than over a serving path. Each names a compensating control that exists, what
  remains undefended anyway, and when it should be revisited.
- **Twelve reserved terms that may appear only inside a denial.** The adjectives of a
  posture rather than the names of properties, refused by a sentence-level test over
  **every Markdown document committed here** and the committed data. The first version
  read only the security documents, which would have passed while the top-level README
  or `SECURITY.md` described a posture this project does not have — the exact failure
  the baseline exists to prevent, occurring inside the control against it. A second
  test now fails if that coverage narrows.
- **Every count these documents state in prose is recomputed from the data.** A table
  row was already compared by identifier; a sentence saying "twenty-two of thirty-two"
  was compared by nothing. Ten such sentences now fail the suite if the data moves
  underneath them, which is the rule the cost method already applies to a figure.
- **Three trust boundaries that pointed forward now point at a record.** `B3`, `B4`,
  and `B5` in the system architecture were owned by "the security baseline decision".
  That decision now exists, and a test compares the two documents verbatim so they
  cannot drift.
- **One new public claim, at the narrowest level that is honest.** The claim and test
  matrix gains `a-security-control-cannot-claim-enforcement-it-does-not-have`,
  certified at C0 by the documentation layer and owned by security. It certifies a
  committed baseline and nothing about whether anything is defended. Two existing
  security claims stay `planned`, and a test now holds them there.

- **A cost method in which an estimate cannot become a bill by accident**, in
  [ADR 0007](docs/architecture/decisions/ADR-0007-inference-cost-method.md) and two
  documents under `docs/cost/`. Every amount declares a basis — an invoice, an
  allocation, or an estimate — and only an invoice-backed basis may carry the
  vocabulary or the reference of one. Two of the three bases are unreachable here and
  the method says why: `actual` needs a provider account this project has never had,
  and `estimated` needs utilisation telemetry no component emits.
- **Allocation by what a workload reserved, with the honest cost written down.** A
  workload is charged for its processor, memory, and accelerator requests times its
  replicas times the window, because reserved capacity is what the scheduler withholds
  from everything else and because it is the only quantity a validated workload
  document can supply. A workload reserving four cores and using a tenth of one is
  charged what a workload saturating four is charged, which makes these figures
  capacity accounting and not efficiency accounting.
- **Idle capacity as a line rather than an absence.** Capacity nobody reserved is
  reported separately, and the workload lines plus that residual must close against
  the machine exactly — a test requires it. In the worked example the residual is 69
  per cent of the node, the largest number on the page and the one both alternative
  treatments would have hidden inside a unit cost.
- **Confidence that is derived rather than asserted.** Four levels, six ceiling rules,
  and a derivation the suite recomputes from each record's own inputs. The consequence
  is stated rather than softened: every cost figure this project can produce today has
  confidence `none`, because the reachable basis is an allocation and the only rate
  card committed here is synthetic.
- **Prices committed, versioned, dated, and invented.** Nothing fetches a price at
  runtime, because a price that moves makes a figure irreproducible. One rate card is
  published, `synthetic-illustrative-v1`, whose every rate is made up and which says so
  inside the artifact rather than in the directory holding it. A provider card would be
  a number with the shape of evidence for a provider this project has never used, and a
  development host has no hourly price at all.
- **A missing input as a null with a reason, never a zero.** Six reason codes, a
  correspondence checked in both directions, and a minimum denominator — 100 requests
  or 10,000 tokens — below which a unit cost is null rather than a rate. Both minimums
  are recorded as declared rather than derived, because they are.
- **A worked synthetic example that is arithmetic rather than typing.** One hour, one
  node, two workloads, a residual, and a prerequisite storage line; every amount,
  share, and unit cost recomputed in exact decimal by
  [`tests/cost/`](tests/cost/). Money is a decimal string at a scale of six, rounded
  half-even once, and a test walks the whole method to establish that not one binary
  float appears in it.
- **A tenant identifier that cannot reach a committed record, by derivation.** Whether
  a cost-record field may appear in a record committed here is read from the
  sensitivity class the telemetry catalog already gave it, so `identity.tenantId` is
  absent from the worked example because its class has no evidence placement — not
  because somebody remembered to remove it.
- **One new public claim, at the narrowest level that is honest.** The claim and test
  matrix gains `a-cost-figure-cannot-be-presented-as-a-bill`, certified at C0 by the
  documentation layer. It certifies a committed method and nothing about what anything
  costs, because no component computes a cost record and no invoice has ever been read.

- **A telemetry catalog in which a field's placement is derived rather than chosen**,
  in [ADR 0006](docs/architecture/decisions/ADR-0006-telemetry-and-evidence-catalog.md)
  and two documents under `docs/telemetry/`. Every attribute declares a sensitivity
  class and a cardinality class, and its permitted placements are the intersection of
  what those two allow. The two content classes have an **empty** placement list, so
  "no prompt in telemetry" is arithmetic rather than a rule a reviewer applies to the
  seventh field somebody adds.
- **Thirteen metrics for seven required signal families, and a budget that is
  counted.** Availability, errors, latency, throughput, model load, tokens, and
  resource use each have at least one active metric; an eighth family, identity, is
  carried by a single `_build_info` gauge so that immutable versions are recorded
  without multiplying every other series by them. Each metric's maximum series count
  is recomputed by the suite from its labels and bucket count — 5,519 against a
  ceiling of 10,000 — so adding a label is a visible number in a diff.
- **Five fields refused as metric labels, each for a stated reason.** A correlation
  identifier because uniqueness is its purpose; a tenant identifier because a metrics
  store labelled by tenant is a customer list; a pod name and a workload version
  because both grow without bound over a retention window; a duration because a
  measurement is a value and never a key. Three of them are bounded and safe-looking,
  which is why the class does the deciding.
- **A log record with no free-form message field.** Records are identified by a
  bounded event identifier and carry named fields. Prose that varies per request is
  the field into which a caller's data eventually arrives, and the field no query can
  match on reliably.
- **The runtime's measured series, mapped, including the one that is absent.** Fifteen
  native series from the selected serving runtime are published with what each maps
  to, and a test compares every name against
  [the trial that measured them](docs/proof/serving/v1-s0-003-pr2-runtime-feasibility.md).
  The missing cumulative request counter — the threshold ADR 0002 records as failed —
  is recorded as absent, with the platform metric that covers it named beside it.
- **Content capture that has no flag to turn it on.** Prompts and responses are not
  captured, and enabling capture would need a classification, a redaction
  specification, a retention window, an access control, and a lawful basis with a
  deletion path. None exists, and a flag would have been the whole decision delegated
  to whoever set it during an incident.
- **Four evidence templates with seven mandatory sections**, under
  `docs/proof/templates/`, indexed by a new [`docs/proof/README.md`](docs/proof/README.md).
  Classification, provenance, environment, method, results, limitations, and
  authorisation, each checked by a test that reads the template. The experiment
  template registers the method and the failure condition before the run.
- **Two rules that admit they are enforced by review alone.** That an upstream error
  body is not passed through verbatim, and that no operating figure is published as a
  benchmark. Thirteen others name a test, and the suite fails if a rule names a test
  that does not exist.
- **One new public claim, at the narrowest level that is honest.** The claim and test
  matrix gains `the-telemetry-catalog-cannot-admit-a-prompt-or-an-unbounded-label`,
  certified at C0 by the documentation layer. It certifies a committed document and
  nothing about a running system, because nothing in this repository emits a single
  signal.

- **A test and certification strategy that decides what a passing test may be used
  to claim**, in [ADR 0005](docs/architecture/decisions/ADR-0005-test-ci-and-certification-strategy.md)
  and three documents under `docs/testing/`. Eleven test layers, four lanes,
  certification at C0 to C2, and a claim/test matrix in which every public claim names
  a test layer, an environment, a required level, and an evidence owner. Nine of
  eighteen claims are certified today and each cites a record already in this
  repository.
- **The mock boundary as a mechanism rather than a rule.** Each layer declares what it
  runs against as an evidence class, and each class carries a hard ceiling on the
  certification level a result from it may support. A mock stops at C1. Three tests
  enforce it: no layer may certify above its class, no claim requiring C2 may be
  satisfied by a mock or a simulation, and a layer labelled with an unreal class may
  not also declare that it needs a real model. The rule was already accepted in words;
  this is the first time it holds without anybody remembering it.
- **A committed pytest configuration whose default lane cannot run a real model.**
  [`pytest.ini`](pytest.ini) registers a marker for every layer, refuses an
  unregistered one, and deselects `cluster`, `realruntime`, `failure`, and `load` by
  default. A test compares that expression against the strategy in both directions: a
  marker belonging to a layer outside the default lane must be excluded, and a marker
  belonging to a layer inside it must not be. Seven of the ten markers currently select
  nothing, because the layers behind them have no code, and the strategy says so
  rather than implying otherwise.
- **A check that catches the mistake the other checks cannot.** Every test module under
  a layer's declared paths must carry that layer's marker at module level, because a
  marker nothing is marked with selects nothing, silently. The markers and the strategy
  can agree perfectly while `pytest -m contract` collects zero tests.
- **An evidence retention rule with a boundary in it.** A lane's raw output expires —
  30 days for the cheap lanes, 90 for the expensive ones — and may never be cited as
  the evidence for a published claim. A record that certifies a claim is committed
  under `docs/proof/` and kept for as long as the claim stands. Raw output a claim
  depends on is promoted into such a record, redacted, before the window closes. Two
  tests hold the line: a claim may cite a record only when it is certified, and a
  certified claim may rest only on layers that are actually implemented.
- **A capacity lane that is defined precisely so that it stays shut.** V1 may publish
  no throughput, latency, capacity, or benchmark figure. The load layer, its lane, and
  the claim it would support are all written down and all deferred, so publishing a
  capacity figure means deleting a deferral in three places rather than adding a test.
- **Two deliberate refusals to overclaim.** A lane may call itself automated only by
  naming a workflow file that exists, and no workflow file exists — so every lane is
  recorded as run by hand. And the security-scan layer is recorded as `planned` rather
  than `implemented`, because a committed scan configuration is not a recorded run.
- **Forty-three deliberate corruptions, each refused.** Mutations across the strategy
  data, the pytest configuration, the three published documents, and an existing test
  module were applied one at a time; every one failed the suite. They are listed by
  category in
  [the change validation record](docs/proof/testing/v1-s0-006-pr1-validation.md).

- **A V1 system architecture**, in six diagrams with the narrative behind each:
  system context, components and the direction dependencies may point, the
  inference request flow including what happens when the model is not ready, the
  workload deployment flow with ownership bands, the telemetry and evidence flow,
  and a trust boundary map. Every component below the contract layer is marked
  unbuilt, because it is.
- **A resource ownership inventory as data, not prose**, under
  `docs/architecture/`. Thirty resources, each with exactly one owner, a lifecycle,
  what creates and destroys it, which teardown operations it survives, who
  references it without owning it, and the handoff rule that applies at its edge.
- **A test suite that makes the ownership boundary a property rather than an
  intention.** It asserts single ownership, that the Terraform and Helm sets do not
  intersect, that a resource's lifecycle is one its owner actually has, that no
  resource claims to survive the operation that destroys it, that a survival list is
  a prefix of the teardown blast-radius ordering — the check that catches a
  plausible-looking claim rather than a malformed one — that prerequisites outlive
  releases and release resources do not outlive prerequisites, that a derived object
  has no tool owner, that a resource with no owner is deferred out of V1, that
  evidence is cited only by rows marked implemented, and that the ownership document
  and the data publish the same identifiers in both directions.
- **ADR 0004**, deciding component decomposition and dependency direction, the
  serving runtime as a separate deployment rather than a sidecar, the
  Terraform/Helm/controller ownership split, the model cache as a prerequisite, the
  trust boundary map, and where this project stops — after comparing a
  Helm-owns-everything layout, a Terraform-owns-everything layout, a GitOps
  controller, Kustomize, a Kubernetes controller with a custom resource, and four
  placements for the model cache.
- **An explicit non-decision inside that record.** Nobody owns a telemetry
  collector, and nobody owns an ingress controller or load-balancer implementation.
  Both are recorded with an `undecided` owner and deferred, and a test refuses to
  let an unowned resource sit inside V1 scope.
- **An overlap found by drawing the boundary, and specified rather than fixed.** The
  accepted cleanup rules let a label-scoped teardown delete any project-labelled
  object, which would put a Terraform-owned prerequisite inside the blast radius of
  a routine partial teardown. It is not a live defect — the implemented teardown is
  bound to one smoke-test namespace — and the resolution, a lifecycle label a sweep
  must exclude, is written down as a constraint on work that has not started. It is
  implemented nowhere, the environment scripts are unchanged, and it is carried as
  an open risk rather than as a fix.
- **A project boundaries document**, stating that this project owns exactly two
  serving capabilities, that standing in front of a choice of providers is gateway
  work, that engineering the runtime's own behaviour is deeper serving work, and
  that V1 may publish no throughput, latency, capacity, or benchmark figure at all.
- **A boundary review checklist** of twenty-six questions across ownership,
  component boundaries, serving and evidence claims, scope, and public safety — the
  human half of a boundary whose mechanical half is a test.
- **Enforcement of the workload-contract rules JSON Schema cannot express.** A
  semantic validation layer above the published schema now applies replica-range
  ordering, a runtime and model compatibility matrix, duplicate secret names, the
  rule that a mock may not declare a credential, and a heuristic that refuses a
  secret pasted into a locator field. Two of these were published as *not enforced*
  when the schema landed and are enforced now; the pasted-secret rule was published
  as *partly* enforced and is now enforced as far as a shape heuristic can reach,
  with the remaining gap measured and tested rather than described. Rules that
  remain unenforced are still named in the same table that states them.
- **A published rejection interface for the contract.** Every refusal carries a
  canonical error code, a stable rule identifier, and a field location such as
  `$.spec.security.secretRefs[1].name`. All fifteen rules are listed in the
  contract document, and a test fails if the validator can cite one the document
  does not publish.
- **Sixteen invalid fixtures**, each with its expected code, rule, field, and
  validation layer committed beside it. The manifest is compared field by field on
  every run, so a change to what a consumer is told fails the build instead of
  passing as a refactor.
- **A test that checks which layer refuses each fixture.** A fixture marked
  `semantic` must be *accepted* by the bare schema; if the schema ever grows strict
  enough to refuse one, that is a strengthening and a compatibility event rather
  than a silent improvement. Seven of the sixteen fixtures are semantic-only
  today, which is the measured cost of validating against the raw schema alone.
- **A runtime and model compatibility matrix**, as data rather than code. It
  records what each serving runtime loads, marks vLLM's CPU backend as a recorded
  fallback nobody has run, deliberately omits vLLM's experimental GGUF path
  because no trial supports listing it, and carries exactly one executed pair —
  the runtime digest and model revision ADR 0002 selected, tied to its feasibility
  record by a test.
- **Compatibility classes for contract changes: compatible, conditionally
  compatible, and breaking.** The middle class is the addition. It names the
  changes that get merged as harmless and discovered later — a new semantic rule, a
  narrowed matrix row, a moved error code — and requires each to be announced.
- **Fixture ownership rules.** A fixture belongs to the rule it demonstrates: a new
  semantic rule must add one, a removed rule takes its own with it, and a valid
  fixture is never edited to make a change pass.
- A command-line entry point, `python -m tools.contract_validation`, for validating
  a document that is not a committed fixture. Sorted output, exit `1` on refusal.
- A change-validation record for this change, listing all sixteen refusals with
  their layer, measuring the credential heuristic in both directions — what it
  catches, what it deliberately leaves alone, and what it still misses — examining
  every credential-shaped string the change commits, and recording the seven
  defects a second review found in its own first draft.
- Identical findings are collapsed, and findings sort by array index as a number,
  so `secretRefs[10]` follows `secretRefs[2]` rather than preceding it.
- An offending annotation key is named in a field location only when it is short
  and does not itself look like a credential. `metadata.annotations` is the
  contract's one open map, so its keys are as author-controlled as any value.

- **The first public contract: WorkloadContract `v1alpha1`.** A JSON Schema draft
  2020-12 document under `contracts/workload/` covering workload identity, owner,
  profile, environment, model and runtime reference, resources, replica bounds,
  platform integrations, security classification, secret references, attribution,
  and evidence links. It describes a workload; nothing in this repository reads one.
- A closed additional-property policy on every object in that schema, so an unknown
  field is a validation error rather than a silently accepted typo, and a test that
  fails if any object is ever added without declaring its policy.
- Structural pinning for the real serving profile: the runtime image by digest, and
  the model by upstream revision **and** per-file content hash. The valid fixture
  carries the exact digest and revision ADR 0002 selected, and a test fails if the
  fixture and the accepted decision ever disagree.
- A `mock-llm` profile that cannot be edited into something that reads as real
  serving: the schema confines it to the `ci` environment and the mock serving
  capability, requires it to label itself in its own contents, and caps its
  real-runtime proof references at zero. Three tests assert each rejection.
- A secret-reference block requiring a provider, a locator, an owner, and a rotation
  responsibility — and no field anywhere in the schema that a secret value could be
  written into.
- `metadata.annotations` as the contract's single, explicitly non-normative
  extension point, with keys namespaced to a DNS domain.
- Published versioning and compatibility rules for the contract, including the
  deliberate refusal of the usual alpha licence to break compatibility freely: a
  breaking change gets a new `apiVersion` even at alpha maturity.
- A rejection table that names, for every rule the platform must enforce, whether it
  is enforced by the schema today or is not yet enforced at all, and maps each to its
  canonical error code.
- Valid fixtures for the `synchronous-llm` and `mock-llm` profiles, a
  secret-reference shape example, and a deterministic mock chat-completion response
  fixture that identifies itself as a mock from its own contents.
- A deterministic contract test suite under `tests/contracts/`, reading only files in
  this repository: no network, no cluster, no model, no clock, no randomness.
- ADR 0003, selecting JSON Schema draft 2020-12, YAML authoring restricted to the
  JSON-representable subset, an off-the-shelf conformant validator, and no code
  generation in V1 — after comparing CUE, OpenAPI schema objects, Protocol Buffers,
  Kubernetes CRD schemas, and draft-07.
- A contract-package changelog, versioned separately from the project.
- A change-validation record for this change, including a thirty-four-mutation
  rejection spot check whose three accepted mutations are the three rules the
  contract document already declares unenforced, and a measurement of how much of
  the secret-locator gap the schema's pattern already closes — which turned out to
  be more than the first draft claimed for padded base64 and less than it claimed
  for alphanumeric credentials.
- Public repository purpose and status without functional capability claims.
- MIT license and contribution, review, commit, conduct, and release conventions.
- Public indexes for prerequisites, contracts, architecture decisions, and governance.
- Security-reporting expectations, including the unresolved private-channel blocker.
- Reproducible POSIX and PowerShell documentation link checks in the contribution guide.
- A pull-request template covering scope, decision impact, validation, and evidence.
- An explicit record that no public maintainer roster or `CODEOWNERS` file exists yet.
- A decision-record convention and index under `docs/architecture/decisions/`.
- ADR 0001, comparing alternatives for the container runtime, the local Kubernetes
  distribution, the task runner, how dependencies are installed, how the project's
  workspace stays isolated, how it is torn down, and what a host needs. Added as a
  proposal; see **Changed** below for the status it now holds.
- A redacted inventory of the one development host measured for that decision, with
  every row marked as either measured or documented.
- Minimum and recommended CPU, memory, and disk figures, kept separate from the
  prerequisites this repository actually supports.
- A stated verdict that the one measured host does not meet the recommended tier,
  rather than an estimate left unchecked against the evidence beside it.
- A reproducible local development cluster: prerequisite checks, cluster creation
  from a digest-pinned node image, a hello-world smoke test verified from inside
  the cluster, scoped teardown, and residue verification, under
  `scripts/environment/` and `deploy/`.
- A runbook for that cluster, including what it creates, what survives teardown,
  and what it does not establish.
- Real-runtime evidence that the cluster can be created, exercised, and removed
  repeatably on one Windows host, including four attempts to make the teardown act
  outside its own cluster, all of which were refused.
- ADR 0002, comparing serving runtimes and open models against the memory, disk,
  and instruction-set limits the cluster evidence measured. Added as a proposal
  that selects nothing: it names a proposed primary and a recorded fallback for
  both runtime and model, and states what would have to be measured to accept
  either.
- Twelve numbered pass/fail thresholds, fixed before any candidate is run, and
  separated into those that disqualify a candidate outright and those that send the
  trial to a smaller model first.
- A dated source table behind every third-party claim in ADR 0002, so that a reader
  can tell a vendor-documented characterisation from a tested one.
- A bounded feasibility workflow for the trial that would settle ADR 0002:
  authorisation gate, download and free-space budgets, a stage-by-stage procedure,
  a one-step step-down rule, explicit abort conditions, and a statement of what the
  workflow cannot establish even when it passes.
- An evidence template for recording that trial, requiring an explicit verdict
  against every threshold, both attempts when a step-down occurs, and a section for
  what went wrong.
- **A real inference, served locally.** A serving runtime was started in a
  Kubernetes cluster, loaded an open model whose bytes were verified against the
  publisher's published SHA-256, and answered chat-completion requests reaching it
  through cluster DNS and a Service. Recorded in the V1-S0-003-PR2 feasibility
  record with the runtime's verbatim response, its reported token counts, and every
  measurement behind the verdicts.
- Trial manifests under `deploy/serving/feasibility/` — namespace, weight-cache
  claim, a resumable and hash-verifying acquisition job, the runtime Deployment
  pinned by image digest, its Service, and an in-cluster probe job. They are
  apparatus for the trial, not a serving path, and say so in their own comments.
- Tested hardware requirements for serving this model with this runtime, replacing
  estimates: AVX2 without AVX-512, no accelerator, a 3 GiB pod memory limit against
  a 2.167 GiB worst-case charge, ~2.0 GiB of disk, and a 14 s worst-case model load.
- A change-validation record for this change, kept separate from the runtime
  evidence so that a static check can never be mistaken for a served request.
- A published rule for the boundary between mock and real serving evidence,
  explaining why a mock can never certify real runtime behaviour, what a mock is
  legitimately for, and five boundary rules that make the distinction operational.

### Changed

- **Five documents stopped saying that no Helm chart exists, because one does.**
  Each said it as a present-tense fact and each is now accurate about what
  arrived and what did not.
  [ADR 0004](docs/architecture/decisions/ADR-0004-component-and-ownership-boundaries.md)'s
  status note said the record decided boundaries for components that do not
  exist; it now names the two that do and says plainly that no decision in it has
  changed. [The ownership document](docs/architecture/resource-ownership.md)
  opened by saying nothing described in it is implemented, and closed by saying
  no check could compare the inventory against the Terraform and Helm that get
  written; the release half of that check now exists and is named, the Terraform
  half is still a commitment, and every row in the release table is still
  `planned` — a chart renders objects, and a rendered object is a file.
  [CONTRIBUTING](CONTRIBUTING.md) said the architecture suite checks a design
  commitment and not an implementation, and that it needs `pytest` alone; it now
  says which half is which and names the two libraries the chart suite added.
  [The runtime troubleshooting document](docs/serving/local-runtime-troubleshooting.md)
  said Kubernetes is out of scope because no chart exists; the reason is now that
  no documented workflow installs the one that does. `DR-04` and `DR-05` in
  [the deferred-risk register](docs/security/deferred-risks.md) said a policy has
  no chart to live in and that no rendering path produces pod specifications;
  both facts changed and **neither risk did** — the chart carries no policy
  because `V1-S3-004` owns it, and no admission control refuses a specification
  that omits the properties.

- **The test inventory's architecture layer said two modules and had meant three
  since `V1-S3-001-PR1`.** It says four now, and names what each protects. The
  count is prose rather than data and nothing recomputes it, which is why it
  drifted; the drift is recorded in the document rather than quietly repaired.
  The coverage gap for
  `a-helm-release-installs-and-uninstalls-without-residue` no longer says no
  chart exists — it says a chart exists and nothing installs it, which is the
  same gap for a different reason.


- The architecture summary, claim/test matrix, and root status table now describe
  the API's emitted metrics, structured records, and enforced redaction boundary
  without overstating them as deployed or real-runtime evidence.
- **Unsupported caller generation controls are now refused rather than silently
  ignored.** ADR 0010 narrows the V1 chat request subset to `model`, `messages`,
  and optional `stream`; `max_tokens` and `temperature` now follow the strict
  unknown-member policy. The deployment-wide `INFEROPS_MAX_OUTPUT_TOKENS` setting
  remains an adapter configuration. The versioned surface JSON is formally
  designated and tested as the canonical API snapshot without claiming OpenAPI,
  JSON Schema, generated-client compatibility, or an artifact under `contracts/`.
- The four broken relative links in the V1-S1-001 PR2 validation record now resolve,
  and the contributor guide accurately describes the repository's narrowly coded
  test-only `# type: ignore[...]` directives.
- **The telemetry catalog moved off `nothing-emits`.** `emissionStatus` now reads
  `partially-emits`, names the emitter and the transport, and every metric carries
  an `emission` field so that a reader learns what is really there from the record
  rather than by scraping and comparing. Five active metrics are marked
  `not-emitted` with a reason each: four belong to the serving-runtime adapter or
  the contract validator, neither of which is instrumented, and
  `inferops_process_resident_memory_bytes` is the API's own and has no source this
  distribution may read — the only per-process memory figure the standard library
  exposes is a file, and no module under `src/inferops` may read one. The endpoint
  names that absence in a comment rather than publishing a zero, because a zero
  would be a measurement claiming the process holds no memory.
- **The catalog gained two attributes it did not have, because it predates the
  API.** `inferops.request.id` — the identifier the API mints at the edge and
  echoes in a header and in every response body — was unpublished, so a record
  could not be joined to the response a caller holds; it is classified like the
  correlation identifier, so it is a log field and never a label.
  `inferops.adapter.kind` is a two-valued identity attribute, so it reaches metrics
  only through the identity metric. Neither changes the cardinality budget.
- **Three rules the catalog previously stated are now enforced by a test**, and are
  recorded that way rather than left claiming less than they do: an emitted signal
  agrees with the catalog, an emitted label is one the catalog permits, and an
  emitted record carries only published fields. The two rules enforced by review
  alone stay review-only, including the one about upstream error bodies — the API
  already refuses to forward an adapter's words, and the rule is about an adapter
  that is not instrumented yet.
- **`DR-12` in the deferred-risk register is narrowed rather than closed.** A
  logger, a formatter, and a redacting sink now exist and real records are
  inspected. No log store, shipper, retention window, or access rule does, so
  nothing is reconstructible and no auditability property is claimed.
- **`DR-01` in the deferred-risk register records what the absent authentication
  boundary now costs.** `/metrics` sits behind it and published nothing at all
  before this change; it now publishes the build, capability, release, environment,
  adapter kind, model identity, runtime identity, and image digest of the
  deployment, plus live operational counters. No control is added and the entry is
  not reopened — a register that describes what a missing control costs has to be
  updated when the cost grows, not only when it is paid.
- Three living documents that said this repository emits nothing —
  `CONTRIBUTING.md`, the inference API document, and the API surface document — are
  corrected. `ADR 0006` is deliberately **not** edited: an ADR is a decision at a
  date, and the catalog's `emissionStatus` is where that record itself said the
  question would be settled.

- **The contributor guide no longer says two markers select nothing.**
  `mockintegration` acquired code in `V1-S1-005-PR1` and `realruntime` in
  `V1-S1-004-PR2`, and the test-lane section still listed both as empty. The
  correction says which story gave each one code, and it says of `realruntime`
  what the strategy already says: the suite is written and has never been run
  against a runtime. The same section now records that a new test module must be
  inventoried, and that a change adding, renaming, moving, or removing any test
  module anywhere in the tree has to pass `tests/testing`.

- **The accepted inference API surface no longer says nothing serves it**, because
  something does. `implementationStatus` moves from `nothing-serves` to
  `served-in-part`, each endpoint names what serves it and what about it is
  unfinished, and the suite that checked "nothing serves this" now checks the
  record against the code that implements it, in both directions. What has not
  changed is the part that matters most: no OpenAPI document, no request or
  response schema, and nothing added to [`contracts/`](contracts/). Serving a shape
  and publishing it as something a client may bind to are different acts, and only
  the first has happened.
- **`DR-07` is narrowed rather than retired, and its control stays deferred.** The
  register entry used to say no dependency lockfile and no packaging manifest
  existed; both now exist, so that half is gone. The half that remains is stated
  instead: nothing here observes which inputs a check actually resolved, the
  non-Python tools are pinned by prose rather than by the lockfile, and no
  dependency scanner has ever been run. `pin-every-dependency-with-a-committed-lockfile`
  therefore keeps its `deferred` status, because a committed file is not a result.
  Twelve risks, thirty-two controls, and every published count are unchanged.
- **The publication boundary now knows about `.venv/`, `build/`, and `dist/`.** The
  security suite walked all three as candidates for publication, so a project
  virtual environment created by the newly adopted dependency manager would have
  failed two of its checks on files belonging to third-party packages. All three are
  ignored by version control and the test that says so now covers them.
- **Four Python files were edited to satisfy the linter and the type checker**, and
  none of them changed behaviour: two list concatenations, one if-else assignment, a
  generator annotated as returning `object`, a `sum()` with no typed start value, and
  a validator keyword the stubs type as possibly unset being used as a dictionary
  key. The suite passes with the same test count it had before.
- **Four records that a second review found disagreeing with themselves.** Narrowing
  `DR-07` left the threat that references it, `T-19`, still saying that no lockfile
  and no packaging manifest exist — a single machine-checked JSON document
  contradicting itself, with no test cross-checking a threat's prose against the risk
  it links to. The architecture index's status line said "one accepted" above a table
  listing two. The governance index still reported ADR 0001 D3 and D4 as proposed and
  unrun, and now carries two rows because the two halves are decided in opposite
  directions. And the toolchain validation record contradicted its own command
  output by one test. ADR 0009 D9 is also relabelled from "Not decided" to "Accepted
  as a boundary", the status ADR 0003 D6 already established for a scope statement,
  with the record saying why its own status is `Accepted` rather than `Accepted in
  part`. The service behind D9 remains undecided.
- **`uv.lock` is pinned to LF in `.gitattributes`**, for the same reason the
  existing shell-script rule is there: `uv` writes it with LF on every platform, and
  a Windows checkout under `text=auto` would receive CRLF and have the whole file
  rewritten by the next `uv lock`.
- **`pytest.ini` and `conftest.py` carry accurate reasons.** Both explained
  themselves by reference to a packaging decision that had not been made. Both now
  explain themselves by reference to the one that has: the pytest configuration
  stays where it is because ADR 0005 made it load-bearing, and the root `conftest.py`
  stays because `tools/` is deliberately outside the distribution.

- Two deferrals in the telemetry catalog keep their status and lose a reason that is no
  longer true. `inferops.cost.record.id` and `inferops_cost_records_total` were
  deferred on the grounds that no cost method existed;
  [ADR 0007](docs/architecture/decisions/ADR-0007-inference-cost-method.md) defines
  one, so both are now deferred on the accurate grounds that nothing computes or emits
  a cost record. No name, class, placement, or budget changes, and neither signal
  becomes active.
- Three existing test modules now declare the marker of the layer that owns them.
  No assertion in them changed, and `python -m pytest tests -q` collects and reports
  exactly what it did before, plus this change's own suite.
- CONTRIBUTING gains a lane and marker section, a strategy-suite section, and a
  pointer from its evidence vocabulary to the ceiling each label carries. The two
  vocabularies are reconciled where they differ rather than left to contradict each
  other: `local-static` is added for a deterministic check over repository files, and
  `production experience` is recorded as a label V1 cannot reach rather than silently
  dropped. The statement that no continuous-integration lane is selected is unchanged,
  because it is still true.
- The governance decision table records the test and certification strategy as
  accepted in part, and records the continuous-integration service and capable-runner
  labelling as not selected rather than leaving them unmentioned.

- The architecture index no longer says that no infrastructure ownership boundary
  and no application architecture is selected. Both are now selected, for components
  that do not exist, and the index says that too.
- The governance decision table records the component and ownership boundary as
  accepted in part, and records telemetry collection and ingress ownership as not
  selected rather than leaving them unmentioned.
- The contribution guide gains the architecture suite, what it checks, and the
  explicit statement that it checks a design commitment rather than an
  implementation.
- **A contract validation message no longer repeats any value read out of the
  document.** The underlying validator embeds the offending value in its own
  message; the contract validator now writes its own text instead, because the
  field most likely to be refused for looking wrong is the field most likely to
  hold a secret, and an error body is the surface most likely to be logged, pasted
  into a ticket, and kept. A test asserts it for every invalid fixture.
- The workload-contract rejection table gains a layer column and a rule
  identifier for every row. Of its five incompletely enforced entries, the replica
  range and the runtime and model combination move from "not yet" to enforced, and
  the pasted secret moves from "partly" to a semantic check whose limits are
  measured. The remaining two — undeclared required capability and policy
  exception — are unchanged, and are now stated as blocked on a named missing
  capability rather than merely deferred.
- The contracts index no longer lists a compatibility matrix among the artifacts
  that do not exist, and says how the matrix that now exists is narrower than the
  cross-project one the integration specification calls for.
- The contracts index moves from "no public contract accepted" to indexing one
  accepted contract, and now requires an entry to state which of its rules are not
  yet enforced in the same place it states the rule.
- The repository entry points and status banner record one published contract schema
  and keep saying that no component consumes it.
- The decision-record conventions now name the `ADR-NNNN-short-slug.md` filename
  form the records already use.
- The contribution guide gains the contract-schema validation commands and the
  packages they need, alongside the existing shell and manifest checks.
- ADR 0002 moves from proposed to **accepted, with one recorded exception**. One
  runtime image digest and one immutable model revision are selected, with source
  and licence for each, on executed proof. Everything written before the trial is
  preserved unedited, including the thresholds the trial went on to fail.
- The decision-record conventions define `Accepted, with one recorded exception`,
  which requires the failed criterion to be named in the record's status banner,
  argued where a reader will find it, and listed among the consequences.
- The feasibility workflow moves from "never been run" to executed, and four parts
  of it were corrected by running it: the cluster bound now permits a single-node
  local cluster the host already runs; the 30-minute stage bound is split so that a
  bulk transfer is bounded by size and retries rather than by a wall clock; the
  free-space bound now requires measuring the host volume rather than a container's
  view of a sparse virtual disk; and the claim that cached weights survive teardown
  is corrected to say that where the cache lives decides it.
- The architecture index, repository entry points, and prerequisites now describe a
  selected runtime and model instead of an unexecuted comparison, and the
  prerequisites carry measured serving figures with their limits stated.
- The two architecture decision records are renamed to an `ADR-` filename prefix.
  Contents are unchanged by the rename and every reference to them was updated.
- ADR 0001 moves from proposed to **accepted in part**. The container runtime, the
  local Kubernetes distribution, the isolation rules, the cleanup rules, and the
  minimum host tier are accepted on executed evidence. The task runner, the
  dependency installation approach, and the recommended host tier are not, and stay
  proposed.
- The minimum host tier's CPU, memory, and disk figures are now measured rather
  than estimated, and its description no longer mentions a mock serving path that
  does not exist. The recommended tier remains an estimate.
- The container virtual machine's memory ceiling is measured at 7.60 GiB, replacing
  the assumed platform default, and the risk that recorded it as unmeasured is
  closed.
- Prerequisites now state a supported local development environment alongside the
  documentation path, and separate both from serving, which remains unsupported.
- The decision-record conventions define `Accepted in part`, which requires a
  per-decision status table.
- The architecture index, the repository entry points, and the prerequisites now
  point at the model and serving-runtime evaluation and say plainly that it selects
  nothing. Serving remains unsupported, and the prerequisites gain no new tool.

### Fixed

- **A caller-supplied identifier ending in a newline was accepted and echoed into
  a response header.** Python's `$` matches at the end of a string *or immediately
  before a single trailing newline*, so `IDENTIFIER.match()` against a `^...$`
  pattern accepted `"req-abc123\n"` and returned it unchanged — into
  `X-InferOps-Request-ID`, which is a header injection rather than an identifier,
  and which that module's own docstring said the pattern existed to prevent. The
  defect predates this change; it is fixed here because this change is what began
  writing those identifiers into every log record. The pattern lost its anchors and
  is matched with `fullmatch`.
- **The same defect in the metric-label validator**, which every telemetry
  environment variable and every label value passes through. A value ending in one
  newline was written raw between quotes into the exposition, splitting a sample
  line in two — and a scraper rejects the whole target rather than the one series,
  so a trailing newline in `INFEROPS_RELEASE_ID` would have blacked out a
  deployment's metrics for the life of the process. Same fix, and both patterns are
  now anchorless and matched in full so the two cannot drift apart.
- **A failing log sink stranded the in-flight gauge and failed the request.** The
  gauge was raised outside the `try` whose `finally` lowers it, so a sink raising
  between the two left it raised forever and took the request with it. The
  increment moved inside the guarded region, and — the load-bearing half — a sink
  failure is now caught, counted, and not raised: a deployment that refused every
  caller because its log destination went away would be telemetry deciding
  availability. A record that fails to *build* still raises, because the allowlist
  refusing a forbidden field is the error that may never be swallowed. The scrape
  names a non-zero drop count.
- **A scrape read the live series rather than a snapshot**, so a scrape concurrent
  with an observation could publish a histogram whose `count` had advanced past the
  `sum` beside it. `Metric.samples()` now takes an immutable reading inside the
  lock, and `series_count` no longer reads outside it.
- **The registry enforced the placement rule on operational metrics and claimed
  both kinds.** An identity metric skipped the label check entirely, so
  `MetricSpec(identity=True, labels=(CORRELATION_ID,))` would have constructed —
  while the module said a correlation identifier "cannot become a label by being
  passed to a constructor". It was an overclaim before it was a bug: nothing
  emitted such a label. The permitted set is now derived per metric kind and both
  are checked.
- **A test that could not fail.** The latency check advanced its clock by zero and
  asserted a duration was non-negative, which the production code guarantees by
  clamping. It now drives an adapter that advances the monotonic clock while
  serving and asserts the histogram sum, the record's duration, and the buckets the
  observation lands in.

- Threshold `T7` was too broad as written. It bundled "the runtime exposes native
  metrics", which is the runtime's job, with "the runtime counts requests", which is
  not. The selected runtime provides native token counters and no cumulative request
  counter, so the threshold failed; it is narrowed for future trials and the
  request count becomes an obligation on this platform. The narrowing happened after
  the measurement, and ADR 0002 records that weakness rather than hiding it.
- Two teardown claims that the evidence contradicted: the engine's virtual disk
  does not return space to the host when a cluster is deleted, and a cluster
  identity check based on a Kubernetes node label does not work, because the label
  is on the node container rather than on the node object.
- Defects in the environment scripts that review found and that every passing run
  had hidden: the diagnostics collector could never run, because an `ERR` trap is
  not reached when a failure occurs inside a shell function; the residue verifier
  certified a clean teardown when the container engine was merely unreachable; the
  cluster identity guard did not cover the default teardown path; and the node
  image digest read-back compared the pin against a value that is only
  incidentally equal to it.
- Slow and nondeterministic failure behaviour in the smoke test: a failed
  verification now reports in about 25 seconds rather than after a 180-second
  timeout, and job retries are disabled so the assertion always reads the log it
  was meant to read.
- Argument handling on the destructive scripts: a second, ignored argument and a
  valueless `--cycles` are now refused rather than silently doing something other
  than what was asked.

ADR 0001 is accepted only for what was executed, on one Windows host, one
architecture, one point in time. Linux and macOS remain untested. No model, serving
runtime, inference, benchmark, ingress, or load-balancing behaviour is proven by
any entry above, and no V1 product capability or versioned release is included.
