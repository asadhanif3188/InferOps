# V1-S0-002-PR1 development host inventory

Date: 2026-08-23

Classification: measured local host inventory, redacted

Claim boundary: describes one development host at one point in time. This is not a
supported-platform statement, a benchmark, a capacity model, a cluster proof, or
evidence that any tool works. No container was built, no cluster was created, and no
workload was run.

## Why this record exists

[ADR 0001](../../architecture/decisions/0001-local-development-environment.md)
proposes a local development and Kubernetes environment. Its acceptance criteria
require host facts to be measured rather than guessed. This file separates what was
measured from what the ADR assumes, so a reviewer can tell the two apart.

## Redaction

Host name, user account, domain membership, serial numbers, network addresses, and
filesystem paths are deliberately excluded. Volumes are described by role rather
than by drive letter. The remaining values are hardware and software facts that a
reader needs in order to judge whether the proposed environment is feasible.

## Method

Read-only queries were issued from Windows PowerShell on the host. No package was
installed, no service was started or stopped, and no host configuration was changed.

## Measured facts

### Operating system and virtualization

| Property | Measured value |
|---|---|
| Operating system | Microsoft Windows 11 Enterprise |
| Version and build | `10.0.26200`, build `26200` |
| Architecture | x64 |
| Hypervisor present | Yes |
| WSL version | `2.1.5.0` |
| WSL kernel | `5.15.146.1-2` |
| WSL default version | 2 |
| WSL distributions present | one container-engine utility distribution, stopped |

Firmware virtualization and second-level address translation were reported as
disabled by the processor query. That reading is unreliable while a hypervisor is
already active, because the query then reports from inside the virtualized view.
`HypervisorPresent = True` and a functioning WSL 2 installation are the load-bearing
facts; the firmware flags are recorded as inconclusive rather than as a limitation.

### Processor

| Property | Measured value |
|---|---|
| Model | 13th Gen Intel Core i7-13700H |
| Physical cores | 14 |
| Logical processors | 20 |
| Base clock | 2400 MHz |

The reported base clock is not a sustained-throughput figure. This chip uses a
hybrid performance/efficiency core layout, so core count alone does not predict
inference throughput.

### Memory

| Property | Measured value |
|---|---|
| Total physical memory | 16836890624 bytes (15.68 GiB) |
| Operating-system visible memory | 15.68 GiB |
| Free physical memory at inventory time | 2.45 GiB |

The free-memory figure is a single instantaneous sample taken while an interactive
desktop session was running. It is not a floor, a ceiling, or an average, and it
must not be treated as the memory available to a future cluster.

### Storage

| Volume role | Capacity | Free at inventory time | Filesystem |
|---|---|---|---|
| System volume | 199 GB | 23.1 GB | NTFS |
| Secondary volume | 276.7 GB | 36.4 GB | NTFS |

Free space is an instantaneous sample. Container engines on this platform place
their virtual disk on the system volume by default.

### Graphics and accelerators

| Property | Measured value |
|---|---|
| Display adapter | Intel UHD Graphics (integrated) |
| Driver version | `32.0.101.7082` |
| Discrete accelerator | None detected |

No CUDA-capable, ROCm-capable, or other discrete accelerator is present on this
host.

### Tooling present

| Tool | Version | Notes |
|---|---|---|
| Docker Desktop | `4.67.0.222858` | Installed |
| Docker CLI | `29.3.1` | Client only; see below |
| kubectl | `v1.34.1` | `windows/amd64`; bundled with the container desktop app |
| Git | `2.45.1.windows.1` | |
| Python | `3.12.6` | |
| uv | `0.9.16` | |
| Go | `1.24.5` | |
| Node.js | `22.14.0` | |
| Windows PowerShell | `5.1.26100.8875` | |
| GNU bash | `5.2.26(1)-release (x86_64-pc-msys)` | Provided by the Git installation |

The container daemon was **not running** at inventory time. A client-side version
query failed to reach the engine socket, so no server version, image list, or
runtime capability was observed. The container desktop application's stored settings
report its bundled Kubernetes as enabled; that setting was read from configuration
and was **not** verified against a running cluster.

### Tooling absent

No `podman`, `nerdctl`, `kind`, `minikube`, `k3d`, `helm`, `make`, `just`, `task`,
`pipx`, `poetry`, `conda`, `colima`, `vagrant`, or `multipass` executable was
resolvable on the command path.

This matters for ADR 0001: the proposed Kubernetes distribution, task runner, and
several compared alternatives are not installed, so none of them has been exercised
on this host.

### Host configuration not overridden

No WSL configuration file was present, so WSL 2 resource limits are at their
platform defaults. The default memory and processor allocation was **not** measured
and is treated by ADR 0001 as an assumption.

## What this evidence does and does not support

Supported by this record:

- The host has enough processors and physical memory to make a single-node local
  Kubernetes cluster plausible.
- The host has a working WSL 2 installation and an installed container engine.
- The host has no discrete accelerator, so any real inference proof performed here
  is a CPU-only result.
- Free disk space on the system volume is limited enough to be a real constraint.

Not supported by this record:

- That any cluster can be created, that a workload can be scheduled, or that
  cleanup is complete.
- That the container engine functions, since it was not running.
- Any minimum or recommended resource requirement. Those values in ADR 0001 are
  labelled estimates and remain estimates until measured.
- Any claim about Linux or macOS hosts. Neither was measured.

## Limitations

- One host, one operating system, one point in time.
- Instantaneous free-memory and free-disk samples, not sustained measurements.
- No permission was granted to install software, start a service, bring up a
  cluster, or alter the host's settings, so no runtime behaviour was observed.
- Processor firmware virtualization flags were inconclusive, as explained above.
