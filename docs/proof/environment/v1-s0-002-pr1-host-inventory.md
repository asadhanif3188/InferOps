# V1-S0-002-PR1 development host inventory

Date: 2026-08-23

Classification: measured local host inventory, redacted

Claim boundary: describes one development host at one point in time. This is not a
supported-platform statement, a benchmark, a capacity model, a cluster proof, or
evidence that any tool works. No container was built, no cluster was created, and no
workload was run.

## Why this record exists

[ADR 0001](../../architecture/decisions/ADR-0001-local-development-environment.md)
proposes a local development and Kubernetes environment. Its acceptance criteria
require host facts to be measured rather than guessed. This file separates what was
measured from what the ADR assumes, so a reviewer can tell the two apart.

## Redaction

Host name, user account, domain membership, serial numbers, network addresses, and
filesystem paths are deliberately excluded. Volumes are described by role rather
than by drive letter, and their free space is rounded and their total capacity
omitted, because only free space bears on the decision. The remaining values are
hardware and software facts that a reader needs in order to judge whether the
proposed environment is feasible.

## Method

Read-only queries were issued from Windows PowerShell on the host. No package was
installed, no service was started or stopped, and nothing about the machine's
settings was altered.

Each row below is labelled **measured** or **documented**. A documented row is a
published property of the named hardware or software, recorded because the decision
depends on it, and it was *not* verified on this host.

## Measured facts

### Operating system and virtualization

| Property | Value | Source |
|---|---|---|
| Operating system | Microsoft Windows 11 Enterprise | Measured |
| Version and build | `10.0.26200`, build `26200` | Measured |
| Architecture | x64 | Measured |
| Hypervisor present | Yes | Measured |
| WSL version | `2.1.5.0` | Measured |
| WSL kernel | `5.15.146.1-2` | Measured |
| WSL default version | 2 | Measured |
| WSL distributions present | One container-engine utility distribution, stopped | Measured |
| Container virtual machine memory limit | Not measured. No WSL configuration file is present, so the platform default applies: the lesser of half the installed memory or 8 GB, which is approximately 7.84 GiB here | Documented |

Firmware virtualization and second-level address translation were reported as
disabled by the processor query. That reading is an artefact, not a finding: once
the platform hypervisor is loaded, the operating system runs above it and these
properties stop reporting the underlying firmware state. The correct conclusion is
the opposite of the literal reading. The hypervisor cannot load without both
features enabled in firmware, and WSL 2 cannot run without that hypervisor, so
`HypervisorPresent = True` together with a functioning WSL 2 installation
establishes that both are in fact enabled. Recorded as established by inference
rather than by direct query.

The installed WSL release and kernel are substantially older than the
operating-system build they run on. This is recorded because behaviour relevant to
running Kubernetes nodes as containers — control-group handling, init-system
support, and networking modes — changed in later WSL releases. If a future cluster
proof fails, the WSL version should be eliminated as a cause before the Kubernetes
distribution is blamed.

### Processor

| Property | Value | Source |
|---|---|---|
| Model | 13th Gen Intel Core i7-13700H | Measured |
| Physical cores | 14 | Measured |
| Logical processors | 20 | Measured |
| Base clock | 2400 MHz | Measured |
| Core layout | 6 performance cores with simultaneous multithreading, plus 8 efficiency cores without it | Documented |
| SSE 4.2 | Available | Measured |
| AVX | Available | Measured |
| AVX2 | Available | Measured |
| AVX-512 foundation | **Not available** | Measured |
| AVX-VNNI | Present on this processor family; not probed here | Documented |
| AMX | Not present on client parts of this family | Documented |

The reported base clock is not a sustained-throughput figure, and core count alone
does not predict inference throughput. For a CPU inference path the vector and
neural instruction support above, together with memory bandwidth, bound throughput
more tightly than core count does. Thread counts for CPU inference are normally set
from the performance cores rather than from all 20 logical processors.

### Memory

| Property | Value | Source |
|---|---|---|
| Installed physical memory | 16 GiB in a single module, at 3200 MT/s | Measured |
| Memory channels populated | One | Measured |
| Operating-system visible memory | 15.68 GiB; the roughly 327 MiB difference is firmware- and device-reserved, consistent with the integrated graphics adapter's shared-memory aperture | Measured |
| Free physical memory at inventory time | 2.45 GiB | Measured |

A single populated channel matters more here than the capacity does. CPU inference
is usually memory-bandwidth bound, so a throughput figure measured on this host
would be a lower bound relative to a dual-channel machine and must not be
generalised.

The integrated graphics adapter takes its framebuffer from system memory
dynamically, so the amount available to containers is not a fixed number.

The free-memory figure is a single instantaneous sample taken while an interactive
desktop session was running. It is not a floor, a ceiling, or an average, and it
must not be treated as the memory available to a future cluster. The binding limit
is in any case the container virtual machine's allocation, not this figure.

### Storage

| Volume role | Free at inventory time | Filesystem | Source |
|---|---|---|---|
| System volume | Approximately 23 GB | NTFS | Measured |
| Secondary volume | Approximately 36 GB | NTFS | Measured |

Free space is an instantaneous sample. Container engines on this platform place
their virtual disk on the system volume by default. The two volumes are separate and
their free space cannot be pooled.

### Graphics and accelerators

| Property | Value | Source |
|---|---|---|
| Display adapter | Intel UHD Graphics, integrated | Measured |
| Discrete accelerator | None detected | Measured |

No CUDA-capable, ROCm-capable, or other discrete accelerator is present. Note that
this is not the same as saying the host is CPU-only: an integrated-GPU compute path
exists in principle through vendor runtimes under WSL 2. That path was not measured,
nothing in ADR 0001 depends on it, and no claim rests on it.

### Tooling present

| Tool | Version |
|---|---|
| Docker Desktop | `4.67.0.222858` |
| Docker CLI | `29.3.1` |
| kubectl | `v1.34.1`, `windows/amd64`; bundled with the container desktop application |
| Git | `2.45.1.windows.1` |
| Python | `3.12.6` |
| uv | `0.9.16` |
| Go | `1.24.5` |
| Node.js | `22.14.0` |
| Windows PowerShell | `5.1.26100.8875` |
| GNU bash | `5.2.26(1)-release (x86_64-pc-msys)`, provided by the Git installation |

Two consequences worth stating. The container daemon was **not running** at
inventory time: a client-side version query failed to reach the engine socket, so no
server version, image list, or runtime capability was observed. And `kubectl` is not
independently installed; it arrives with the container desktop application and moves
with it, which is why ADR 0001 treats it as an unpinned dependency.

The container desktop application's stored settings report its bundled Kubernetes as
enabled. That setting was read from configuration and was **not** verified against a
running cluster.

A POSIX shell is present, supplied by the Git installation rather than by a separate
package. ADR 0001 relies on this when comparing task runners.

### Tooling absent

No `podman`, `nerdctl`, `kind`, `minikube`, `k3d`, `helm`, `make`, `just`, `task`,
`pipx`, `poetry`, `conda`, `colima`, `vagrant`, or `multipass` executable was
resolvable on the command path.

This matters for ADR 0001: the proposed Kubernetes distribution, the proposed task
runner, and most of the compared alternatives are not installed, so none of them has
been exercised on this host and every comparison in that record is
documentation-derived.

## What this evidence does and does not support

Supported by this record:

- The host has enough processors and installed memory to make a single-node local
  Kubernetes cluster plausible.
- The host has a WSL 2 installation and an installed container engine.
- The host has no discrete accelerator and no AVX-512, so any real inference proof
  performed here would be an AVX2 CPU result on a single memory channel.
- Free disk space on the system volume, and the default container virtual machine
  memory ceiling, are both real constraints on what can be proven here.

Not supported by this record:

- That any cluster can be created, that a workload can be scheduled, or that
  cleanup is complete.
- That the container engine functions, since it was not running.
- Any minimum or recommended resource requirement. Those values in ADR 0001 are
  labelled estimates and remain estimates until measured.
- Any claim about Linux or macOS hosts. Neither was measured.
- Any claim about the tools ADR 0001 proposes. None of them is installed here.

## Limitations

- One host, one operating system, one architecture, one point in time.
- Instantaneous free-memory and free-disk samples, not sustained measurements.
- No permission was granted to install software, start a service, bring up a
  cluster, or alter the host's settings, so no runtime behaviour was observed.
- The container virtual machine's actual memory and processor allocation was not
  measured; the platform default is recorded instead, and it is the binding limit on
  everything ADR 0001 proposes.
- Rows marked documented are published properties recorded for the decision's sake.
  They were not verified here and should be treated as weaker than the measured
  rows beside them.
