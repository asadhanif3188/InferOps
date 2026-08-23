# ADR 0001: Local development and Kubernetes environment

| Field | Value |
|---|---|
| Status | **Proposed** |
| Date proposed | 2026-08-23 |
| Date accepted | Not accepted |
| Decision owner | Unassigned; no public maintainer roster exists yet |
| Supersedes | None |
| Superseded by | None |

> [!IMPORTANT]
> This decision is **proposed, not accepted**. Nothing in it has been executed. No
> cluster was created, no container was built, and no workload was run. Contributors
> must not treat any option below as a supported environment, and must not implement
> against it as though it were settled.

## Context

InferOps needs a local environment in which a Kubernetes-facing platform can be
developed, exercised, and torn down safely on a contributor's own machine. Until
that environment is chosen and proven, dependent work cannot honestly claim to run
anywhere.

The only host measured so far is recorded in
[the development host inventory](../../proof/environment/v1-s0-002-pr1-host-inventory.md).
The facts that constrain this decision are:

- 14 physical and 20 logical processors, of which only 6 are performance cores with
  simultaneous multithreading; the other 8 are efficiency cores.
- 16 GiB of installed memory, 15.68 GiB of it visible to the operating system, in a
  single module and therefore on a single memory channel.
- The container virtual machine, not the host, sets the real memory ceiling. At the
  platform default that ceiling is approximately 7.84 GiB, well under half the
  installed memory.
- Approximately 23 GB free on the system volume, which is where container engines
  place their virtual disk by default, and approximately 36 GB free on a second
  volume. The two cannot be pooled.
- No discrete accelerator, and AVX-512 unavailable. Inference on this host is a
  CPU path on AVX2, unless an integrated-GPU path is deliberately exercised.
- A WSL 2 installation and an installed container engine, though the engine daemon
  was not running when measured and the WSL release is substantially older than the
  operating-system build it runs on.
- No Kubernetes distribution, task runner, or alternative container engine
  installed.

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

## Proposed decisions

Each decision below is individually proposed. None may be cited as accepted.

> [!NOTE]
> The comparison tables describe third-party tools from their published
> documentation. None of the compared tools was installed or run on the measured
> host, and the host inventory records that most of them are absent from it. Read
> every characterisation below as vendor-documented and unverified here.

### D1 — Container runtime: a Docker-API-compatible engine

| Alternative | Assessment |
|---|---|
| Docker Desktop, WSL 2 backend | Installed on the measured host, though its daemon was not running when measured, so nothing about its behaviour was observed. Broadest ecosystem; every candidate Kubernetes tool targets its API. Subject to the subscription terms discussed below. |
| Podman Desktop | Apache-2.0 and rootless by default. The chosen Kubernetes tool supports it only through an environment variable that upstream itself labels experimental, and rootless operation carries further cgroup requirements. On Windows it runs a second Linux virtual machine rather than reusing the existing one. |
| Rancher Desktop | Open source and bundles its own Kubernetes, but takes ownership of host container configuration, which conflicts with the isolation goal in D5. |
| containerd with nerdctl inside WSL 2 | Minimal and dependency-light, but the most manual to set up and the least approachable for a new contributor. |
| Colima | Not applicable; it does not target the measured platform. |

**Proposed:** depend on the Docker Engine API rather than on a specific vendor
product. Docker Desktop is the reference implementation on the measured Windows
host because it is the engine already installed there.

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

| Alternative | Fidelity | Teardown scope | Assessment |
|---|---|---|---|
| kind | Provisions with `kubeadm`; it is the harness upstream Kubernetes uses to run its own conformance and end-to-end jobs | One named cluster; deleting it removes its node containers and its context, with the caveats in D6 | Best control-plane fidelity and exact cluster scoping. Ships no ingress controller and no `Service type=LoadBalancer` implementation, so both must be added deliberately before InferOps can exercise those contracts. Higher per-node memory than k3s. |
| k3d wrapping k3s | k3s is itself a CNCF Certified Kubernetes distribution. Its defaults substitute the datastore (SQLite through kine rather than etcd), the ingress controller, the service load balancer, and storage | Named cluster; comparable scope | Fastest and lightest, and out of the box it provides the ingress and load-balancer behaviour kind lacks. Every substitution except the datastore is removable with a disable flag, so the divergence is configurable rather than inherent. The datastore substitution is the one that genuinely differs. |
| minikube | Upstream, but addon-dependent | Per-profile deletion | Mature and flexible, at the cost of more drivers, more state, and more variance between contributors. |
| The container desktop application's bundled Kubernetes | Upstream; version bound to the desktop application release | The cluster is a machine-global singleton owned by the desktop application, not an object this project may create, name, or delete | Requires no extra install and is already enabled in stored settings. Recent releases offer a multi-node provisioner, so node count is not the objection; ownership is. The project cannot version-pin or dispose of a cluster it does not own, and two projects on one machine would collide in it. |
| k3s or MicroK8s directly inside WSL 2 | k3s as above. MicroK8s differs again: a dqlite datastore, a different default network plugin, and delivery as a snap | Manual | Both need init-system configuration inside the distribution. MicroK8s additionally depends on snap support, which is unreliable under WSL 2. More friction than kind for no fidelity gain. |

**Proposed:** kind, as a single-node cluster named `inferops-dev`, created from a
node image pinned by digest.

Rationale: criterion 1 favours kind's control plane, because InferOps's product is
Kubernetes-facing and the datastore and control-plane components are where fidelity
matters most; criterion 2 is satisfied by a cluster that is one named, project-owned
object. The honest cost is criterion 1 in the other direction: kind provides no
ingress controller and no load-balancer implementation, so the moment InferOps needs
to exercise those contracts it must install them explicitly, whereas k3s would have
supplied opinionated versions of both.

**Recorded fallback.** If measurement shows the environment does not fit, switching
to k3d is *not* the first remedy. The idle-memory difference between the two is a
few hundred megabytes and cannot close a multi-gigabyte gap. The host-side remedies
come first: raise the container virtual machine's memory allocation, relocate the
engine's virtual disk off the constrained system volume, and reduce model size.
k3d is considered only if measurement shows the shortfall is genuinely within that
few-hundred-megabyte margin, and its datastore substitution would then have to be
documented as a known divergence rather than hidden.

### D3 — Task runner: Task (go-task)

| Alternative | Assessment |
|---|---|
| GNU Make | Ubiquitous and free on Linux and macOS, but absent on the measured host and without a first-party Windows distribution. It invokes the platform's default command interpreter unless `SHELL` is overridden, handles Windows drive-letter paths poorly in prerequisites, and is a file-dependency build engine used here as a task runner, which demands `.PHONY` discipline throughout. Shell availability is *not* the objection: the measured host already has a POSIX shell, supplied by the Git installation that every contributor needs anyway. |
| just | Single cross-platform binary with no runtime. One file-level shell directive gives identical recipe bodies across platforms using that same Git-provided shell. Very close to the selection below. |
| Task (go-task) | Single cross-platform binary that interprets recipe bodies with an embedded POSIX shell, so shell *syntax* behaves identically across platforms without depending on an external shell at all. |
| mise | Combines tool-version pinning and task running in one file, which would absorb part of D3 and part of the version-pinning risk. Younger, and a larger surface to adopt than a task runner alone. Worth revisiting if tool-version drift becomes the dominant problem. |
| Package-manager scripts of another language ecosystem | Would make an unrelated language runtime a required dependency of this project. |
| Python `invoke` or `nox` | Python-native, but couples the runner to the application's own dependency environment, which is exactly what the runner is needed to bootstrap. |

**Proposed:** Task (go-task), at a pinned version, installed by each contributor
rather than vendored into the repository.

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

| Alternative | Assessment |
|---|---|
| `pip` with `venv` and a requirements file | Universally available, but produces no hash-pinned cross-platform lock by default and does not manage interpreter versions. |
| uv | Present on the measured host. Single binary; its lockfile is resolved across environment markers rather than per-platform, and records artifact hashes; it provisions interpreters itself; and it can export a `pip`-consumable requirements file. Younger than the alternatives. |
| Poetry | Mature with good ergonomics, and its lock is likewise cross-platform and hash-bearing. An extra install where uv is already present, with no advantage that outweighs that here. |
| PDM | Credible; no decisive advantage over uv for this scope. |
| pixi | The strongest alternative if InferOps later needs conda-forge-resolved accelerator runtimes or native numeric libraries in the contributor's own environment. Deferred rather than rejected. |
| conda | Valuable when native or accelerator toolchains must be resolved as dependencies rather than baked into an image. Its default channels carry organisation-size licensing terms that would need review before it could be made mandatory; the community channel does not. |

**Proposed:** uv, with a `pyproject.toml`, a committed lockfile, a `requires-python`
constraint on the 3.12 series, and a `.python-version` pinning that series rather
than an exact patch release.

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

Proposed rules, none yet exercised:

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

### D6 — Cleanup

Proposed rules, none yet exercised:

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
- Teardown is verified, not assumed: the cluster list, the context list, and the
  engine's container list filtered by the cluster's own label must all show no
  residue afterwards.

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

> [!WARNING]
> Every number in this section is an estimate. Only the host inventory is measured.
> These values must be replaced by measurement before they are published as
> supported prerequisites.

Memory is stated as **host total**, with the share that must reach the container
virtual machine given separately, because on Windows and macOS the desktop session
and the virtual machine's own overhead consume the difference.

| Tier | Logical CPUs | Host memory | Must reach the container VM | Free disk, one volume | Basis |
|---|---:|---:|---:|---:|---|
| Documentation and governance contributions | 2 | 4 GiB | n/a | 5 GB | Accepted today; see [prerequisites](../../prerequisites.md) |
| **Minimum** — single-node cluster with a mock serving path | 4 | 8 GiB on Linux; 16 GiB on Windows or macOS | 6 GiB | 20 GB | Estimate |
| **Recommended** — cluster plus real serving of a small quantised model | 8, of which at least 4 performance cores | 16 GiB on Linux; 24 GiB on Windows or macOS | 12 GiB | 60 GB | Estimate; the model side is owned by the model and serving-runtime decision |

**Host-fit verdict for the measured host: it does not meet the recommended tier.**
This is stated plainly because criterion 4 exists to be answered, not gestured at.
The host has 15.68 GiB visible against a 16 GiB figure; its container virtual
machine sits at a platform default of roughly 7.84 GiB against a 12 GiB figure; and
neither volume has 60 GB free, nor can the two be pooled to reach it. Real serving
therefore cannot be proven on this host without raising the virtual machine's
memory allocation, relocating the engine's virtual disk, choosing a smaller model,
or using a second host. The minimum tier looks reachable; the recommended tier does
not.

Supported operating systems:

- Measured: Windows 11 x64 with WSL 2. One host only, and not yet exercised.
- Intended but untested: Linux x86_64 and macOS. Neither was measured, so neither
  may be described as supported.

A CPU path is mandatory, and on the measured host that means AVX2 without AVX-512.
There is no discrete accelerator, so no accelerator requirement may be introduced
without a second host to prove it on.

## Consequences

If accepted as proposed:

- Contributors gain one reproducible cluster lifecycle rather than per-machine
  improvisation, and teardown becomes a stated guarantee instead of a hope.
- The project takes on five pinned tool dependencies — a container engine, kind,
  `kubectl`, Task, and uv — plus Git as an unpinned prerequisite. `kubectl` matters
  more than its size suggests: on the measured host the only one present is bundled
  with the desktop application and moves with it, so the project must either pin its
  own or accept that the digest-pinned node image constrains which desktop-application
  versions stay within the supported client-server version skew.
- Choosing kind buys control-plane fidelity and pays for it in memory, and in having
  to install an ingress controller and a load-balancer implementation explicitly
  before those contracts can be exercised at all.
- Depending on an engine API rather than a product keeps a permissively licensed
  path open, but that path is unproven. It also narrows if the D2 fallback is ever
  taken, because the fallback's support for the permissively licensed engine is
  weaker than kind's.

## Compatibility impact

None. There is no accepted public contract, released version, or supported
environment for this decision to break. It introduces no schema, no API surface, and
no runtime behaviour.

## Security considerations

This ADR asserts no security property. Three points are recorded because the
decisions make them relevant later:

- Pinning node images and tool versions by digest is what makes an environment
  auditable; pinning by mutable tag is not.
- Requiring administrative rights would widen the blast radius of a local
  compromise, which is why D5 confines host-wide changes to a short, named list
  rather than allowing them freely.
- The prohibition in D6 on whole-engine pruning exists to protect data on a
  contributor's machine that the project does not own.

Threat modelling and scanner selection are out of scope here and belong to the
security baseline decision.

## Proof plan

This ADR moves to accepted only after the following are executed and recorded as
evidence, and only if they succeed:

1. Container engine reachable, with server version and engine information captured.
2. The container virtual machine's actual memory and processor allocation measured,
   rather than assumed from the platform default.
3. Cluster created from a digest-pinned node image into a project-scoped kubeconfig.
4. Node and control-plane health captured, with the server version recorded and the
   client-server version skew checked.
5. A hello-world workload deployed, reaching a ready state, and answering a request.
6. Idle cluster memory, processor, and disk consumption measured on the host.
7. The workload and cluster torn down, with residue verified absent and the surviving
   artefacts named in D6 confirmed to be the only things left.
8. The full sequence repeated from a clean state to show it is reproducible.

If any step fails, the failure and its diagnostics are recorded and this ADR stays
proposed.

## Risks, assumptions, and open questions

| ID | Item | Impact |
|---|---|---|
| R1 | Approximately 23 GB free on the measured system volume, where the engine's virtual disk lives by default, and no single volume with 60 GB free | The recommended tier is unreachable on this host as configured. Directly affects the model and serving-runtime decision. |
| R2 | No discrete accelerator, and AVX-512 measured as unavailable | Real inference proof from this host is an AVX2 CPU path, or an unmeasured integrated-GPU path. No accelerator claim can be made from it. |
| R3 | Installed memory is a single module, so a single memory channel | CPU inference throughput is usually memory-bandwidth bound. Any measurement taken here is a lower bound relative to a dual-channel host, and must not be generalised. |
| R4 | The container engine was not running when measured | Every runtime statement in this ADR is unverified. |
| R5 | The container virtual machine's memory limit is at the platform default, approximately half the installed memory, and was not measured | The effective ceiling for the whole environment is an assumption, and it is the binding constraint. |
| R6 | The installed WSL release and kernel are substantially older than the operating-system build they run on | Behaviour relevant to running Kubernetes nodes as containers changed in later releases. If the proof plan fails, this must be eliminated as a cause before the Kubernetes distribution is blamed. |
| R7 | No public maintainer roster exists | This ADR has no named decision owner and cannot be formally approved by one. |
| R8 | Tool and node-image versions are not yet pinned to digests, and `kubectl` currently arrives bundled with a third-party application | Reproducibility is stated as an intent, not yet as a property. |
| R9 | Only one host, one operating system, and one architecture were measured | Cross-platform support is an aspiration, not a finding. |
| R10 | Every third-party comparison here is documentation-derived; none of the compared tools was run | The comparison could be wrong in ways only execution would reveal. |

Open questions carried forward: whether the permissively licensed engine
alternatives behave identically for the chosen Kubernetes distribution; whether the
measured host can hold a cluster and a real model at the same time once the virtual
machine's memory allocation is raised; and what installing an ingress controller and
a load-balancer implementation into kind costs, given that those are the contracts
InferOps most needs to exercise.
