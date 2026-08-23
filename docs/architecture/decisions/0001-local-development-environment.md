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

- 14 physical and 20 logical processors, and 15.68 GiB of physical memory.
- 23.1 GB free on the system volume at inventory time, which is where container
  engines place their virtual disk by default.
- No discrete accelerator. Any inference proof on this host is CPU-only.
- A working WSL 2 installation and an installed container engine, though the engine
  daemon was not running when measured.
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

### D1 — Container runtime: a Docker-API-compatible engine

| Alternative | Assessment |
|---|---|
| Docker Desktop, WSL 2 backend | Present on the measured host. Broadest ecosystem; every candidate Kubernetes tool targets its API. Requires a paid subscription for larger organisations. |
| Podman Desktop | Permissively licensed and rootless by default. Kubernetes-in-container tooling supports it through a non-default provider setting, which is less exercised. |
| Rancher Desktop | Open source and bundles its own Kubernetes, but takes ownership of host container configuration, which conflicts with the isolation goal in D5. |
| containerd with nerdctl inside WSL 2 | Minimal and dependency-light, but the most manual to set up and the least approachable for a new contributor. |
| Colima | Not applicable; it does not target the measured platform. |

**Proposed:** depend on the Docker Engine API rather than on a specific vendor
product. Docker Desktop is the reference implementation on the measured Windows
host because it is already installed and its WSL 2 backend is working.

The project must not require a paid subscription. Podman and Rancher Desktop are
therefore recorded as intended-supported alternatives whose compatibility is
unproven and must be verified before any such support is claimed.

### D2 — Local Kubernetes distribution: kind

| Alternative | Fidelity | Teardown scope | Assessment |
|---|---|---|---|
| kind | Upstream kubeadm; used for upstream conformance testing | One named cluster; deleting it removes exactly its own containers | Best fidelity, exact teardown, supports multi-node and digest-pinned node images. Higher per-node memory than k3s. |
| k3d wrapping k3s | k3s substitutes several components, including ingress and load-balancer implementations | Named cluster; comparable scope | Fastest and lightest, but component substitution is a correctness risk for a project whose output is Kubernetes contracts. |
| minikube | Upstream, but addon-dependent | Per-profile deletion | Mature and flexible, at the cost of more drivers, more state, and more variance between contributors. |
| The container desktop application's bundled Kubernetes | Upstream, version bound to the desktop application release | Reset affects the shared engine, not a project-scoped object | Requires no extra install and is already enabled in stored settings, but is single-node only, cannot run isolated parallel clusters, and its reset is broader than this project should ever perform on a contributor's machine. |
| k3s or MicroK8s directly inside WSL 2 | k3s substitutions apply | Manual | Additional init-system configuration and more setup friction for no fidelity gain. |

**Proposed:** kind, as a single-node cluster named `inferops-dev`, created from a
node image pinned by digest.

Rationale: criterion 1 favours upstream fidelity because InferOps's product is
Kubernetes-facing; criterion 2 is satisfied exactly, because the cluster is one
named object whose deletion cannot reach unrelated containers; and the same
definition can later run on an automated runner.

Recorded fallback: if measurement in the follow-up proof shows that kind's footprint
does not leave room for real serving on the measured host, k3d is the first
fallback, and its component substitutions must then be documented as a known
divergence rather than hidden.

### D3 — Task runner: Task (go-task)

| Alternative | Assessment |
|---|---|
| GNU Make | Ubiquitous and free on Linux and macOS, but absent on the measured host and dependent on a POSIX shell that Windows contributors must supply themselves. Recipe bodies diverge per platform. |
| just | Single cross-platform binary with a simple model, but recipe bodies still run under a per-platform shell unless each recipe overrides it. |
| Task (go-task) | Single cross-platform binary with an embedded POSIX shell interpreter, so one recipe body executes identically on Windows and Linux without requiring a POSIX shell on Windows. Definitions are readable and checkable. |
| Package-manager scripts of another language ecosystem | Would make an unrelated language runtime a required dependency of this project. |
| Python `invoke` or `nox` | Python-native, but couples the runner to the application's own dependency environment, which is exactly what the runner is needed to bootstrap. |

**Proposed:** Task (go-task), at a pinned version, installed by each contributor
rather than vendored into the repository.

Rationale: the measured host is Windows and the eventual automated runner will be
Linux. Task is the only candidate that removes per-platform recipe divergence
without adding an unrelated language runtime.

The design of automated check lanes is not decided here; it belongs to the test and
certification strategy.

### D4 — Dependency installation: uv with a committed lockfile

| Alternative | Assessment |
|---|---|
| `pip` with `venv` and a requirements file | Universally available, but produces no hash-pinned cross-platform lock by default and does not manage interpreter versions. |
| uv | Present on the measured host. Single binary, cross-platform hash-pinned lockfile, manages interpreter versions itself, and can export a `pip`-consumable requirements file for environments that need one. Younger than the alternatives. |
| Poetry | Mature with good ergonomics, but an extra install and slower resolution, with no advantage that outweighs uv here. |
| PDM, pixi | Credible, but neither offers a decisive advantage over uv on this host. |
| conda | Valuable when native or accelerator toolchains must be resolved, which the CPU-only measured host does not require. Heavier, and default-channel terms would need review before it could be made mandatory. |

**Proposed:** uv, with a `pyproject.toml`, a committed lockfile, and a pinned
interpreter version consistent with the Python `3.12.6` measured on the host.

An export to a `pip`-installable requirements file is the documented escape hatch, so
that uv does not become the only possible entry point.

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
  requires administrative rights.

### D6 — Cleanup

Proposed rules, none yet exercised:

- Full teardown is one named operation: delete the `inferops-dev` cluster. It
  removes the project's cluster and nothing else.
- Partial teardown deletes only objects matching the project label selector inside
  `inferops-` namespaces.
- The project-scoped kubeconfig file is removed as part of full teardown.
- Whole-engine pruning, deletion of all namespaces, and deletion of contexts the
  project did not create are prohibited, because a contributor's machine hosts
  unrelated work.
- Teardown is verified, not assumed: the cluster list, the context list, and the
  engine's container list filtered by the cluster's own label must all show no
  residue afterwards.

### D7 — Host resource requirements

> [!WARNING]
> Every number in this section is an estimate. Only the host inventory is measured.
> These values must be replaced by measurement before they are published as
> supported prerequisites.

| Scope | Logical CPUs | Memory | Free disk | Basis |
|---|---:|---:|---:|---|
| Documentation and governance contributions | 2 | 4 GiB | 5 GB | Accepted today; see [prerequisites](../../prerequisites.md) |
| Single-node cluster with a mock serving path | 4 | 8 GiB | 20 GB | Estimate |
| Cluster plus real model serving | 8 | 16 GiB | 60 GB | Estimate; owned by the model and serving-runtime decision |

Supported operating systems:

- Measured: Windows 11 x64 with WSL 2. One host only, and not yet exercised.
- Intended but untested: Linux x86_64 and macOS. Neither was measured, so neither
  may be described as supported.

A CPU-only path is mandatory. The measured host has no discrete accelerator, so no
accelerator requirement may be introduced without a second host to prove it on.

## Consequences

If accepted as proposed:

- Contributors gain one reproducible cluster lifecycle rather than per-machine
  improvisation, and teardown becomes a stated guarantee instead of a hope.
- The project takes on four pinned tool dependencies — a container engine, kind,
  Task, and uv — each of which becomes a version the project must maintain.
- Building on upstream Kubernetes costs more memory than the lightest alternative.
  If the measured host cannot absorb that alongside real serving, the fallback in D2
  is taken and the resulting divergence must be documented.
- Depending on an engine API rather than a product keeps a permissively licensed
  path open, but that path is unproven and must not be advertised until it is
  exercised.

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
  compromise, which is why D5 rules it out.
- The prohibition in D6 on whole-engine pruning exists to protect data on a
  contributor's machine that the project does not own.

Threat modelling and scanner selection are out of scope here and belong to the
security baseline decision.

## Proof plan

This ADR moves to accepted only after the following are executed and recorded as
evidence, and only if they succeed:

1. Container engine reachable, with server version and engine information captured.
2. Cluster created from a digest-pinned node image into a project-scoped kubeconfig.
3. Node and control-plane health captured, with the server version recorded.
4. A hello-world workload deployed, reaching a ready state, and answering a request.
5. Idle cluster memory, processor, and disk consumption measured on the host.
6. The workload and cluster torn down, with residue verified absent.
7. The full sequence repeated from a clean state to show it is reproducible.

If any step fails, the failure and its diagnostics are recorded and this ADR stays
proposed.

## Risks, assumptions, and open questions

| ID | Item | Impact |
|---|---|---|
| R1 | 23.1 GB free on the measured system volume, where the engine's virtual disk lives by default | A cluster, its images, and a real model may not fit together. May block the model and serving-runtime decision. |
| R2 | No discrete accelerator on the measured host | Real inference proof from this host is CPU-only, and no accelerator claim can be made from it. |
| R3 | Free memory at inventory time was 2.45 GiB on a live desktop session | Headroom for a cluster plus a model is unproven and may be insufficient. |
| R4 | The container engine was not running when measured | Every runtime statement in this ADR is unverified. |
| R5 | WSL 2 resource limits are at platform defaults, which were not measured | The effective memory ceiling for containers is an assumption. |
| R6 | No public maintainer roster exists | This ADR has no named decision owner and cannot be formally approved by one. |
| R7 | Tool and node-image versions are not yet pinned to digests | Reproducibility is stated as an intent, not yet as a property. |
| R8 | Only one host, one operating system, and one architecture were measured | Cross-platform support is an aspiration, not a finding. |

Open questions carried forward: whether the permissively licensed engine
alternatives behave identically for the chosen Kubernetes distribution, and whether
the measured host can hold a cluster and a real model at the same time.
