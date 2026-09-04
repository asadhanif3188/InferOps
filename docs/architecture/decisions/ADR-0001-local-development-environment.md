# ADR 0001: Local development and Kubernetes environment

| Field | Value |
|---|---|
| Status | **Accepted in part** |
| Date proposed | 2026-08-23 |
| Date accepted | 2026-08-23, for D1, D2, D5, D6, and the minimum tier of D7 only |
| Decision owner | Unassigned; no public maintainer roster exists yet |
| Supersedes | None |
| Superseded by | [ADR 0009](ADR-0009-python-toolchain.md), for D3 and D4 only |

> [!IMPORTANT]
> This record is **accepted in part**. The container runtime, the local Kubernetes
> distribution, the isolation rules, the cleanup rules, and the minimum host tier
> were executed and are supported by
> [runtime evidence](../../proof/environment/v1-s0-002-pr2-cluster-smoke.md).
> The recommended host tier (D7) was **not** executed and remains proposed. The
> per-decision table below is authoritative; do not read the acceptance of one
> decision here as acceptance of its neighbours.
>
> D3 and D4 were proposed here and never executed, and both are now
> **superseded** by [ADR 0009](ADR-0009-python-toolchain.md), which decided the
> Python toolchain and ran every tool it named. ADR 0009 **rejects** the task
> runner D3 proposed and **accepts** the dependency manager D4 proposed. Read
> ADR 0009 for either; the sections below are kept for the alternatives they
> assessed and no longer state this project's decision.

## Decision status

| ID | Decision | Status | Evidence |
|---|---|---|---|
| D1 | Container runtime: a Docker-API-compatible engine | **Accepted**, for the reference implementation only | Engine reached, versions captured, cluster and workload run on it |
| D2 | Local Kubernetes distribution: kind | **Accepted** | Cluster created from a digest-pinned image four times; hello-world served a request twice |
| D3 | Task runner: Task (go-task) | **Superseded** by ADR 0009 D7, which rejects a task runner | None. Never installed, never run |
| D4 | Dependency installation: uv with a committed lockfile | **Superseded** by ADR 0009 D2 and D3, which accept and execute it | None here. The evidence is in ADR 0009 and its validation record |
| D5 | Isolation | **Accepted** | Scoping rules exercised; four attempts to act outside the project's own cluster were refused |
| D6 | Cleanup | **Accepted** | Full and partial teardown exercised; residue verified absent five times |
| D7 | Host resource requirements | **Minimum tier accepted; recommended tier proposed** | Minimum tier measured on one Windows host. The recommended tier remains an estimate |

Two decisions are accepted only for what was actually exercised. D1 is accepted
for the Docker-API-compatible engine that was measured; the permissively licensed
alternatives named under it remain unproven. D7's minimum tier is accepted on one
Windows host, one architecture, one point in time.

## Context

InferOps needs a local environment in which a Kubernetes-facing platform can be
developed, exercised, and torn down safely on a contributor's own machine. Until
that environment is chosen and proven, dependent work cannot honestly claim to run
anywhere.

The only host measured so far is recorded in
[the development host inventory](../../proof/environment/v1-s0-002-pr1-host-inventory.md),
and what was subsequently executed on it is recorded in
[the cluster smoke proof](../../proof/environment/v1-s0-002-pr2-cluster-smoke.md).
The facts that constrain this decision are:

- 14 physical and 20 logical processors, of which only 6 are performance cores with
  simultaneous multithreading; the other 8 are efficiency cores.
- 16 GiB of installed memory, 15.68 GiB of it visible to the operating system, in a
  single module and therefore on a single memory channel.
- The container virtual machine, not the host, sets the real memory ceiling. That
  ceiling has since been measured at 7.60 GiB, close to the 7.84 GiB the platform
  default implied, and well under half the installed memory.
- Approximately 23 GB free on the system volume, which is where container engines
  place their virtual disk by default, and approximately 36 GB free on a second
  volume. The two cannot be pooled.
- No discrete accelerator, and AVX-512 unavailable. Inference on this host is a
  CPU path on AVX2, unless an integrated-GPU path is deliberately exercised.
- A WSL 2 installation and an installed container engine. The engine daemon was
  not running at inventory time; it has since been started and its server reached,
  and it reports cgroup v1, which the chosen Kubernetes tool warns is deprecated.
  The WSL release remains substantially older than the operating-system build it
  runs on.
- No Kubernetes distribution, task runner, or alternative container engine was
  installed at inventory time. The Kubernetes tool selected in D2 has since been
  installed at a pinned version and verified against its published checksum. No
  task runner and no alternative engine has been installed even now.

Two further constraints come from the project rather than the host. First, InferOps
produces Kubernetes-facing contracts, so divergence between the local cluster and
upstream Kubernetes is a correctness risk, not merely an inconvenience. Second, the
project is open source, so a mandatory commercially licensed dependency would
exclude contributors.

## Decision criteria

A candidate is judged against, in order:

1. **Fidelity** — does the local cluster behave like the Kubernetes a user would
   deploy to?
2. **Scoped teardown** — can the environment be removed completely without touching
   unrelated work on the contributor's machine?
3. **Reproducibility** — can the same versions be pinned and recreated by another
   contributor and, later, by an automated runner?
4. **Host fit** — does it fit within the measured memory and disk headroom?
5. **No mandatory paid dependency** — can a contributor use the project without a
   commercial licence?
6. **Cross-platform reach** — can Linux and macOS contributors follow the same
   instructions?

## Decisions

Each decision below carries its own status, given in the decision-status table
above. Cite them individually; several are still proposals.

> [!NOTE]
> The comparison tables describe third-party tools from their published
> documentation. Of everything compared below, only the selected container engine
> and the selected Kubernetes distribution have been installed and run here. Every
> other characterisation remains vendor-documented and unverified, including every
> alternative that was rejected — a rejection recorded from documentation is not
> the same as one recorded from a trial.

### D1 — Container runtime: a Docker-API-compatible engine

Status: **accepted** for the engine that was exercised. The alternatives in this
table remain unproven.

| Alternative | Assessment |
|---|---|
| Docker Desktop, WSL 2 backend | Installed on the measured host. Its engine has since been started, reached, and used to run the accepted cluster and workload, so its behaviour here is observed rather than assumed. Broadest ecosystem; every candidate Kubernetes tool targets its API. Subject to the subscription terms discussed below. |
| Podman Desktop | Apache-2.0 and rootless by default. The chosen Kubernetes tool supports it only through an environment variable that upstream itself labels experimental, and rootless operation carries further cgroup requirements. On Windows it runs a second Linux virtual machine rather than reusing the existing one. |
| Rancher Desktop | Open source and bundles its own Kubernetes, but takes ownership of host container configuration, which conflicts with the isolation goal in D5. |
| containerd with nerdctl inside WSL 2 | Minimal and dependency-light, but the most manual to set up and the least approachable for a new contributor. |
| Colima | Not applicable; it does not target the measured platform. |

**Decision:** depend on the Docker Engine API rather than on a specific vendor
product. Docker Desktop is the reference implementation on the measured Windows
host because it is the engine already installed there. Engine server `29.3.1`,
API `1.54`, storage driver `overlayfs`, cgroup v1 was the configuration under
which the accepted evidence was produced.

On licensing: Docker's subscription terms require a paid subscription for
professional use at organisations above a published employee-count or annual-revenue
threshold, and exempt personal use, education, and non-commercial open source.
Docker Engine itself is separately licensed under Apache-2.0. The constraint
therefore falls on individual contributors employed by large organisations rather
than on this project. Those terms change, so this must be re-read against Docker's
current agreement rather than treated as settled here.

The project must not require a paid subscription of anyone. Podman and Rancher
Desktop are therefore recorded as intended-supported alternatives whose
compatibility is unproven and must be verified before any such support is claimed.

### D2 — Local Kubernetes distribution: kind

Status: **accepted**, on the evidence recorded in the cluster smoke proof.

| Alternative | Fidelity | Teardown scope | Assessment |
|---|---|---|---|
| kind | Provisions with `kubeadm`; it is the harness upstream Kubernetes uses to run its own conformance and end-to-end jobs | One named cluster; deleting it removes its node containers and its context, with the caveats in D6 | Best control-plane fidelity and exact cluster scoping. Ships no ingress controller and no `Service type=LoadBalancer` implementation, so both must be added deliberately before InferOps can exercise those contracts. Higher per-node memory than k3s. |
| k3d wrapping k3s | k3s is itself a CNCF Certified Kubernetes distribution. Its defaults substitute the datastore (SQLite through kine rather than etcd), the ingress controller, the service load balancer, and storage | Named cluster; comparable scope | Fastest and lightest, and out of the box it provides the ingress and load-balancer behaviour kind lacks. Every substitution except the datastore is removable with a disable flag, so the divergence is configurable rather than inherent. The datastore substitution is the one that genuinely differs. |
| minikube | Upstream, but addon-dependent | Per-profile deletion | Mature and flexible, at the cost of more drivers, more state, and more variance between contributors. |
| The container desktop application's bundled Kubernetes | Upstream; version bound to the desktop application release | The cluster is a machine-global singleton owned by the desktop application, not an object this project may create, name, or delete | Requires no extra install and is already enabled in stored settings. Recent releases offer a multi-node provisioner, so node count is not the objection; ownership is. The project cannot version-pin or dispose of a cluster it does not own, and two projects on one machine would collide in it. |
| k3s or MicroK8s directly inside WSL 2 | k3s as above. MicroK8s differs again: a dqlite datastore, a different default network plugin, and delivery as a snap | Manual | Both need init-system configuration inside the distribution. MicroK8s additionally depends on snap support, which is unreliable under WSL 2. More friction than kind for no fidelity gain. |

**Decision:** kind, at the pinned release `v0.32.0`, as a single-node cluster named
`inferops-dev`, created from a node image pinned by digest to
`kindest/node:v1.34.8@sha256:02722c2dedddcfc00febf5d27fbeb9b7b2c14294c82109ff4a85d89ac9ba3256`.
The definition lives in `deploy/kind/inferops-dev.yaml`.

Rationale: criterion 1 favours kind's control plane, because InferOps's product is
Kubernetes-facing and the datastore and control-plane components are where fidelity
matters most; criterion 2 is satisfied by a cluster that is one named, project-owned
object. The honest cost is criterion 1 in the other direction: kind provides no
ingress controller and no load-balancer implementation, so the moment InferOps needs
to exercise those contracts it must install them explicitly, whereas k3s would have
supplied opinionated versions of both. Nothing in the evidence changes that cost;
the accepted proof exercises a ClusterIP Service only.

**On the pinned Kubernetes version.** The node image is deliberately *not* this
kind release's default, which is a 1.36 build. It is a 1.34 build, chosen so that a
kubectl arriving bundled with the container desktop application stays inside the
supported one-minor-version client/server skew. The consequence this ADR predicted
— that a digest-pinned node image constrains which desktop-application versions
remain compatible — is therefore now a concrete constraint rather than a warning.
Measured skew on the reference host: 0.

**Recorded fallback.** If measurement shows the environment does not fit, switching
to k3d is *not* the first remedy. The idle-memory difference between the two is a
few hundred megabytes and cannot close a multi-gigabyte gap. The host-side remedies
come first: raise the container virtual machine's memory allocation, relocate the
engine's virtual disk off the constrained system volume, and reduce model size.
k3d is considered only if measurement shows the shortfall is genuinely within that
few-hundred-megabyte margin, and its datastore substitution would then have to be
documented as a known divergence rather than hidden.

### D3 — Task runner: Task (go-task)

Status: **superseded** by [ADR 0009](ADR-0009-python-toolchain.md) D7, which
rejects a task runner for V1. Nothing here was ever installed or run. The
alternatives assessed below stand and are the reason ADR 0009 does not repeat
them; the conclusion below does not.

| Alternative | Assessment |
|---|---|
| GNU Make | Ubiquitous and free on Linux and macOS, but absent on the measured host and without a first-party Windows distribution. It invokes the platform's default command interpreter unless `SHELL` is overridden, handles Windows drive-letter paths poorly in prerequisites, and is a file-dependency build engine used here as a task runner, which demands `.PHONY` discipline throughout. Shell availability is *not* the objection: the measured host already has a POSIX shell, supplied by the Git installation that every contributor needs anyway. |
| just | Single cross-platform binary with no runtime. One file-level shell directive gives identical recipe bodies across platforms using that same Git-provided shell. Very close to the selection below. |
| Task (go-task) | Single cross-platform binary that interprets recipe bodies with an embedded POSIX shell, so shell *syntax* behaves identically across platforms without depending on an external shell at all. |
| mise | Combines tool-version pinning and task running in one file, which would absorb part of D3 and part of the version-pinning risk. Younger, and a larger surface to adopt than a task runner alone. Worth revisiting if tool-version drift becomes the dominant problem. |
| Package-manager scripts of another language ecosystem | Would make an unrelated language runtime a required dependency of this project. |
| Python `invoke` or `nox` | Python-native, but couples the runner to the application's own dependency environment, which is exactly what the runner is needed to bootstrap. |

**Proposed, not accepted:** Task (go-task), at a pinned version, installed by each
contributor rather than vendored into the repository. No task runner has been
installed or exercised, and the environment scripts this repository ships are
POSIX shell precisely so that they do not depend on a decision that is still open.

Rationale, stated precisely because the imprecise version of it is wrong: Task's
embedded shell removes *shell syntax* divergence between a Windows development host
and a Linux runner. It does **not** ship the standard command-line utilities. Any
recipe that calls `rm`, `sed`, `mkdir -p`, `curl`, or similar still depends on
per-platform binaries, and on a bare Windows host several of those do not exist.
Recipes must therefore be written against a small, deliberately chosen command
vocabulary, or call the project's own cross-platform tools directly.

`just` reaches a comparable result with one shell directive and the Git-provided
shell. The margin between them is a preference for one fewer implicit dependency,
not a capability gap, and this decision should not be defended as though it were.

The design of automated check lanes is not decided here; it belongs to the test and
certification strategy.

### D4 — Dependency installation: uv with a committed lockfile

Status: **superseded** by [ADR 0009](ADR-0009-python-toolchain.md) D2 and D3,
which accept uv, commit a lockfile, pin the interpreter series, and record the
executed proof. Nothing here was exercised when this was written; the alternatives
assessed below stand, and ADR 0009 carries the decision and the evidence.

| Alternative | Assessment |
|---|---|
| `pip` with `venv` and a requirements file | Universally available, but produces no hash-pinned cross-platform lock by default and does not manage interpreter versions. |
| uv | Present on the measured host. Single binary; its lockfile is resolved across environment markers rather than per-platform, and records artifact hashes; it provisions interpreters itself; and it can export a `pip`-consumable requirements file. Younger than the alternatives. |
| Poetry | Mature with good ergonomics, and its lock is likewise cross-platform and hash-bearing. An extra install where uv is already present, with no advantage that outweighs that here. |
| PDM | Credible; no decisive advantage over uv for this scope. |
| pixi | The strongest alternative if InferOps later needs conda-forge-resolved accelerator runtimes or native numeric libraries in the contributor's own environment. Deferred rather than rejected. |
| conda | Valuable when native or accelerator toolchains must be resolved as dependencies rather than baked into an image. Its default channels carry organisation-size licensing terms that would need review before it could be made mandatory; the community channel does not. |

**Proposed, not accepted:** uv, with a `pyproject.toml`, a committed lockfile, a
`requires-python` constraint on the 3.12 series, and a `.python-version` pinning
that series rather than an exact patch release.

Two clarifications that the obvious phrasing gets wrong. First, uv provisions its
own redistributable interpreter build; it does not adopt the one already on the
host. The `3.12.6` measured on the host confirms the series is available but is not
itself what contributors would run, and the provisioned build is not byte-identical
to a system interpreter. Second, the exported requirements file is resolved for a
target platform, so the escape hatch may need one export per platform rather than a
single file.

pixi and conda are deferred on the basis that the current scope is pure Python and
that accelerator toolchains are expected to be pinned inside container images rather
than in a contributor's environment. That reasoning, not the absence of an
accelerator on a single measured host, is what should be revisited if it stops being
true.

Test-framework selection and coverage policy are not decided here; they belong to
the test and certification strategy.

### D5 — Isolation

Status: **accepted**. The rules below are implemented in `scripts/environment/`
and were exercised; the refusals were additionally attacked rather than assumed.

Accepted rules:

- The project creates its own cluster. It never installs into, reconfigures, or
  assumes a cluster the contributor already had.
- The cluster is written to a project-scoped kubeconfig file that is ignored by
  version control, rather than merged into the contributor's default kubeconfig.
- Every namespace the project creates is prefixed `inferops-`.
- Every object the project creates carries the label
  `app.kubernetes.io/part-of: inferops`, so that scoped selection and scoped
  deletion are always possible.
- Locally built images use a project image prefix and are loaded into the cluster
  directly rather than pushed to a shared registry during development.
- No step changes host-wide container-engine settings, installs a system service, or
  requires administrative rights — with the documented exceptions below.

**Documented exceptions.** Claiming no host-wide change would be false on the
measured platform, so the exceptions are named rather than discovered later. Each is
a prerequisite a contributor performs knowingly and once, not something the project
does silently on their behalf:

- Raising the container virtual machine's memory and processor allocation. Without
  it the D7 targets are unreachable on this platform, because the default ceiling is
  roughly half the installed memory.
- Raising the kernel's file-watch limits inside that virtual machine. Kubernetes
  nodes running as containers are known to exhaust the defaults once more than a few
  pods are scheduled.
- Contributors who have the container desktop application's own Kubernetes enabled
  must disable it before creating `inferops-dev`. It competes for the same virtual
  machine's memory and binds the same local port.

**How the refusals are enforced, and what defeated two naive versions of them.**
The first implementation checked that the reachable cluster's control-plane node
carried a kind cluster label. It does not: kind labels the node *container*, not
the Kubernetes node object, and the guard failed closed on the project's own
cluster. The check now requires every node the API server reports to be a
container that kind itself labelled for `inferops-dev`, and it was then tested
against a second, real cluster whose context had been renamed to this project's
context name. It refused. A correct context name is not evidence of identity,
because a context name is only what someone typed.

The second version was correct and applied in the wrong places. It guarded the
object-scoped teardown but not the equivalent delete on the *default* teardown
path — the one a contributor actually runs. Both are guarded now. Where identity
cannot be established, the object-scoped delete is skipped and the reason
reported, rather than aborting: deleting the cluster itself is scoped by kind's
own bookkeeping and stays safe either way.

The limit of all this is worth naming. Identity here means "a kind cluster kind
labelled `inferops-dev`". A second cluster deliberately created under that name
satisfies every check. The guard prevents reaching the wrong cluster by accident;
it cannot prevent a name collision made on purpose.

### D6 — Cleanup

Status: **accepted**. Full teardown was exercised five times and partial teardown
twice, with residue verified absent on every run.

Accepted rules:

- Full teardown is one named operation: delete the `inferops-dev` cluster. It removes
  the project's node containers and its kubeconfig context.
- Two artefacts survive that deletion by design, and are documented rather than
  quietly left behind: the shared container network the Kubernetes tool creates and
  manages, which other clusters may be using, and the cached node image, which is
  retained so that recreating the cluster does not download it again. Removing that
  cached image is offered as a separate, opt-in reclamation step, which matters given
  how little free space the measured host has.
- Partial teardown deletes only objects matching the project label selector inside
  `inferops-` namespaces.
- The project-scoped kubeconfig file is removed as part of full teardown.
- Whole-engine pruning, deletion of all namespaces, and deletion of contexts the
  project did not create are prohibited, because a contributor's machine hosts
  unrelated work.
- If a local registry container is later introduced to make image loading tolerable,
  it becomes a project-owned object and must be named, labelled, and removed by the
  same teardown operation. Otherwise it is exactly the residue this section claims
  cannot exist.
- Teardown is verified, not assumed: the cluster list, the context list, the
  engine's container list, and the engine's volume list — the last two filtered by
  the cluster's own label — must all show no residue afterwards.

**A third thing survives, and it was not predicted here.** Deleting the cluster
returns its roughly 1.1 GB of engine volume storage, but it does not return that
space to the host. The engine's virtual disk grows to accommodate the cluster and
does not shrink when the cluster is removed, so host free space fell by about
0.1 GB across a full create-and-destroy cycle and stayed down. Reclaiming it is a
container-engine maintenance operation. This teardown neither performs it nor
should: compacting an engine's virtual disk affects every other project on the
machine.

### Considered and not selected: a packaged development container

A development container would define the whole toolchain once and give Windows,
macOS, Linux, and an automated runner the same environment, which is close to this
ADR's stated goal. It is not proposed, for two reasons specific to this project.
The environment must itself run a Kubernetes cluster made of containers, so the
development container would be nesting or reaching out to the host engine, which
adds a layer exactly where fidelity matters most. And it does not remove any of the
four tool decisions above; it relocates them into an image definition that still has
to pin the same versions.

It remains the strongest single alternative to D3 plus D5, and should be revisited
if per-contributor setup proves to be the dominant cost.

### D7 — Host resource requirements

Status: **minimum tier accepted; recommended tier still an estimate.**

> [!WARNING]
> The recommended tier below has not been measured. It describes serving a real
> model, which nothing in this repository has yet done, and it must not be
> published as a supported prerequisite until it is.

Memory is stated as **host total**, with the share that must reach the container
virtual machine given separately, because on Windows and macOS the desktop session
and the virtual machine's own overhead consume the difference.

| Tier | Logical CPUs | Host memory | Must reach the container VM | Free disk, one volume | Basis |
|---|---:|---:|---:|---:|---|
| Documentation and governance contributions | 2 | 4 GiB | n/a | 5 GB | Accepted; see [prerequisites](../../prerequisites.md) |
| **Minimum** — single-node cluster, no serving path | 4 | 8 GiB on Linux; 16 GiB on Windows or macOS | 6 GiB | 20 GB | **Measured** on one Windows host |
| **Recommended** — cluster plus real serving of a small quantised model | 8, of which at least 4 performance cores | 16 GiB on Linux; 24 GiB on Windows or macOS | 12 GiB | 60 GB | Estimate; the model side is owned by the model and serving-runtime decision |

What the minimum tier now rests on, from the cluster smoke proof:

| Measured | Value |
|---|---|
| Memory reaching the container VM on the reference host | 7.60 GiB |
| Idle memory consumed by the cluster's node | 712–720 MiB, about 9% of that allocation |
| Engine volume storage while the cluster exists | ~1.1 GB, returned on teardown |
| Cached node image | ~1.35 GB, retained by design |
| Control-plane ready, warm | 13–16 s across four creations |

The minimum tier's 6 GiB figure is therefore a headroom decision, not a fit
decision: the cluster itself needs well under 1 GiB, and the rest is there for
whatever is scheduled beside it. The tier was measured in the sense that a host
meeting it was shown to run the cluster; it has not been probed downward to find
where the cluster stops working.

Note that the tier's description has changed. It previously read "single-node
cluster with a mock serving path". No mock serving path exists or was run, so the
tier now claims only what was proven.

**Host-fit verdict for the measured host: it meets the minimum tier and does not
meet the recommended tier.** The minimum tier is no longer a projection — this
host ran the cluster. The recommended tier remains out of reach: the container
virtual machine holds 7.60 GiB against a 12 GiB figure, and neither volume has
60 GB free, nor can the two be pooled to reach it. Real serving therefore still
cannot be proven on this host without raising the virtual machine's memory
allocation, relocating the engine's virtual disk, choosing a smaller model, or
using a second host.

Supported operating systems:

- Measured and exercised: Windows 11 x64 with WSL 2. One host only.
- Intended but untested: Linux x86_64 and macOS. Neither was measured, so neither
  may be described as supported.

A CPU path is mandatory, and on the measured host that means AVX2 without AVX-512.
There is no discrete accelerator, so no accelerator requirement may be introduced
without a second host to prove it on.

## Consequences

For the decisions now accepted:

- Contributors gain one reproducible cluster lifecycle rather than per-machine
  improvisation, and teardown is an asserted result rather than a hope. The
  lifecycle is implemented in `scripts/environment/` and documented in
  [the local cluster runbook](../../environment/local-cluster.md).
- The project takes on five pinned tool dependencies — a container engine, kind,
  `kubectl`, Task, and uv — plus Git as an unpinned prerequisite, and of those only
  the first two were accepted and in use when this was written. Of the other two,
  [ADR 0009](ADR-0009-python-toolchain.md) later accepted uv and rejected Task. `kubectl` matters more than its size
  suggests: on the measured host the only one present is bundled with the desktop
  application and moves with it. The project has taken the second of the two paths
  it named — it does not pin its own `kubectl`, and instead pins a node image whose
  Kubernetes version keeps the bundled client in skew, and checks that skew on every
  preflight. That is a live constraint, not a hypothetical: the pinned node image is
  two minor versions behind the kind release's own default for exactly this reason.
- Choosing kind buys control-plane fidelity and pays for it in memory, and in having
  to install an ingress controller and a load-balancer implementation explicitly
  before those contracts can be exercised at all.
- Depending on an engine API rather than a product keeps a permissively licensed
  path open, but that path is unproven. It also narrows if the D2 fallback is ever
  taken, because the fallback's support for the permissively licensed engine is
  weaker than kind's.

## Compatibility impact

None. There is no accepted public contract, released version, or supported
environment for this decision to break. It introduces no schema and no API surface.

It does now introduce runtime behaviour on a contributor's machine, in
`scripts/environment/`, but nothing in the repository depends on that behaviour and
nothing external consumes it. Changing or withdrawing it would break no consumer.

## Security considerations

This ADR asserts no security property. Three points are recorded because the
decisions make them relevant later:

- Pinning node images and tool versions by digest is what makes an environment
  auditable; pinning by mutable tag is not. The node image is now pinned by digest
  and the pin is verified against what the engine actually ran, so this is a
  property rather than an intention.
- The kind binary is downloaded from a release page and then creates containers on
  the contributor's machine. Its published checksum is therefore verified before it
  is run, and the runbook states that verifying it is not optional.
- Requiring administrative rights would widen the blast radius of a local
  compromise, which is why D5 confines host-wide changes to a short, named list
  rather than allowing them freely. No step in the accepted evidence required
  administrative rights.
- The prohibition in D6 on whole-engine pruning exists to protect data on a
  contributor's machine that the project does not own. The identity guard that
  enforces it was tested against a real foreign cluster, not merely written down.
- The project-scoped kubeconfig contains a client certificate and key for the local
  cluster. It is written inside the repository working tree, so it is explicitly
  ignored by version control, and it is deleted on teardown.

Threat modelling and scanner selection are out of scope here and belong to the
security baseline decision.

## Proof plan and results

The plan this ADR set for itself, and what happened. Full detail, including exact
commands and output, is in
[the cluster smoke proof](../../proof/environment/v1-s0-002-pr2-cluster-smoke.md).

| # | Planned step | Result |
|---|---|---|
| 1 | Container engine reachable, with server version and engine information captured | **Passed.** Server `29.3.1`, API `1.54`, `overlayfs`, cgroup v1 |
| 2 | The container virtual machine's actual memory and processor allocation measured | **Passed.** 7.60 GiB and 20 CPUs, replacing the platform-default assumption |
| 3 | Cluster created from a digest-pinned node image into a project-scoped kubeconfig | **Passed.** Running image read back and matched the pin on every creation |
| 4 | Node and control-plane health captured, server version recorded, skew checked | **Passed.** Node `Ready`, all eight system pods `Running`, skew 0 |
| 5 | A hello-world workload deployed, reaching a ready state, and answering a request | **Passed.** Answered from inside the cluster through cluster DNS and a ClusterIP Service |
| 6 | Idle cluster memory, processor, and disk consumption measured on the host | **Passed**, with a caveat. Memory and disk measured; CPU is an instantaneous engine-reported sample rather than a sustained figure |
| 7 | Workload and cluster torn down, residue verified absent, survivors confirmed | **Passed.** Five full teardowns, no unexpected residue |
| 8 | The full sequence repeated from a clean state to show it is reproducible | **Passed.** Two cycles in one invocation, plus further independent runs |

Two things the plan did not ask for were done as well, because the plan was
incomplete without them. The refusals promised by D5 and D6 were attacked — four
attempts to act outside the project's own cluster, including one using a second
real cluster wearing this project's context name, all refused. And the disk
measurement was taken across a whole cycle rather than only while the cluster
existed, which is what revealed that host free space is not returned by teardown.

Steps 1–8 cover D1, D2, D5, D6, and the minimum tier of D7. They do not touch D3
or D4, which is why those were left proposed here. Both were settled later, with
their own evidence and their own change, in
[ADR 0009](ADR-0009-python-toolchain.md).

## Risks, assumptions, and open questions

| ID | Item | Status | Impact |
|---|---|---|---|
| R1 | Approximately 23 GB free on the measured system volume, where the engine's virtual disk lives by default, and no single volume with 60 GB free | Open, and now sharper | The recommended tier is unreachable on this host as configured. Teardown was also shown not to return host disk space, so repeated cycles erode the margin. Directly affects the model and serving-runtime decision. |
| R2 | No discrete accelerator, and AVX-512 measured as unavailable | Open | Real inference proof from this host is an AVX2 CPU path, or an unmeasured integrated-GPU path. No accelerator claim can be made from it. |
| R3 | Installed memory is a single module, so a single memory channel | Open | CPU inference throughput is usually memory-bandwidth bound. Any measurement taken here is a lower bound relative to a dual-channel host, and must not be generalised. |
| R4 | The container engine was not running when measured | **Closed** | The engine has since been started, reached, and used to run the accepted evidence. |
| R5 | The container virtual machine's memory limit was assumed from the platform default and not measured | **Closed** | Measured at 7.60 GiB, close to the 7.84 GiB assumed. It remains the binding constraint, but it is no longer an assumption. |
| R6 | The installed WSL release and kernel are substantially older than the operating-system build they run on | Open, and the date has arrived | The cluster still works on the pinned 1.34 node image. The engine reports cgroup v1, and as of `2026-09-04` that is no longer only a deprecation warning: creating a cluster from kind `v0.32.0`'s own default 1.36.1 node image on this host fails during `kubeadm init`, with the kubelet refusing outright — `kubelet is configured to not run on a host using cgroup v1`. The pin therefore cannot move forward on this host at all until the engine provides cgroup v2. Executed and recorded in [the cluster lifecycle result](../../proof/environment/v1-s3-001-pr1-cluster-lifecycle.md). |
| R7 | No public maintainer roster exists | Open | This ADR has no named decision owner and cannot be formally approved by one. Its partial acceptance rests on evidence, not on an approval that nobody is currently able to give. |
| R8 | Tool and node-image versions are not pinned to digests, and `kubectl` arrives bundled with a third-party application | **Partly closed, and the residue has fired** | The node image is pinned by digest and the pin was verified against the running container; the kind binary is pinned by release and verified by checksum. `kubectl` remains unpinned and bundled, mitigated only by a skew check — and as of `2026-09-04` that skew check refuses the reference host, whose bundled client has moved to `v1.36.1`, two minors from the pinned image. Because of R6 the pin cannot be moved to meet it, so the mitigation now blocks rather than warns, and a contributor has to install a kubectl inside the window themselves. |
| R9 | Only one host, one operating system, and one architecture were measured | Open | Cross-platform support is an aspiration, not a finding. The scripts have never run on Linux or macOS. |
| R10 | Every third-party comparison here is documentation-derived; none of the compared tools was run | **Partly closed** | The two selected tools have now been run. Every rejected alternative is still rejected on documentation alone, so the comparison could still be wrong in the direction of the roads not taken. |
| R11 | The engine's virtual disk grows to hold the cluster and does not shrink when it is removed | New | Host free space is not returned by teardown. On a host with roughly 23 GB free, repeated create-and-destroy cycles are not free, and reclaiming the space needs an engine maintenance operation this project must not perform on a contributor's behalf. |
| R12 | kind ships no ingress controller and no `Service type=LoadBalancer`, and neither was installed | New | The accepted evidence covers a ClusterIP Service only. The contracts InferOps most needs to exercise are still unexercised, and what installing them costs on this host is unknown. |
| R13 | The environment scripts require the `docker` CLI specifically, not merely a Docker-API-compatible engine | New | D1 selects the engine API, but cluster identity is established by querying the engine for kind's container labels, and only the Docker CLI form of that query exists. Podman and the other permissively licensed alternatives are further from working than D1's wording implies. |
| R14 | Cluster identity is a project-chosen name | New | A second kind cluster deliberately named `inferops-dev` would pass every guard and be deleted. Accidental misdirection is defended against; a deliberate collision is not. |

Open questions carried forward: whether the permissively licensed engine
alternatives behave identically for the chosen Kubernetes distribution; whether the
measured host can hold a cluster and a real model at the same time once the virtual
machine's memory allocation is raised; what installing an ingress controller and a
load-balancer implementation into kind costs, given that those are the contracts
InferOps most needs to exercise; and how far below the stated minimum tier a host
can go before the cluster stops working, which was never probed.
