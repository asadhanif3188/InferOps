# TEMPLATE — environment record

This file is a **template**, not evidence. It records nothing and proves nothing.
Copy it to a filled record — for example
`docs/proof/environment/v1-sN-0NN-prN-<slug>.md` — and fill it in. Do not edit this
file to hold results.

Placeholders are written as `<...>`. A filled record contains none of them.

An environment record exists so that a later run can be compared to an earlier one.
Its value is entirely in how precisely it pins things: a record that says "Docker" is
a record that cannot tell you why the same command produced a different answer six
weeks later.

The section headings below are required and are checked by
[`tests/telemetry/`](../../../tests/telemetry/). Add sections freely; do not remove
one, and do not repeat one.

---

# `<work item>` environment

Date captured: `<YYYY-MM-DD>`

## Classification and certification

Evidence class: `<local-static | local-real-cpu | cloud-real-cpu | cloud-real-gpu>`

An environment record is a description of a machine, and on its own it certifies
nothing about behaviour. It carries a class because the results that cite it do.

Claim boundary: `<what this record is cited by, and what it does not itself establish>`

## Provenance

| Input | Immutable identifier |
|---|---|
| Repository revision | `<git commit sha>` |
| Container images present | `<name@sha256:..., one row each>` |
| Model artifacts present | `<repository, revision, per-file hash>` |
| Package versions | `<name and exact version, one row each>` |

Versions are read from the tools themselves, not from a document describing what
should be installed.

## Environment

| Property | Value |
|---|---|
| Host | `<make and model, or instance type>` |
| Processor | `<model, cores, threads, instruction set extensions that matter>` |
| Memory | `<total, and free at capture>` |
| Disk | `<total, free, and which volume the container engine uses>` |
| Operating system | `<name, edition, build number>` |
| Kernel or hypervisor | `<...>` |
| Container engine | `<name, version, storage driver, cgroup version>` |
| Kubernetes | `<distribution, server version, node count>` |
| Accelerator | `<model, driver, runtime — or "none; CPU only">` |
| Network | `<anything a result depends on: proxy, offline, egress restriction>` |

Number of hosts: `<...>`. Anything measured here is true of these hosts and no
others until it is repeated elsewhere.

## Method

How each value above was read:

```text
<the exact commands, in order>
```

A version reported by a package manager and a version reported by the binary can
differ. Say which one this is.

## Results

Anything that surprised the person capturing this, and anything a later reader would
otherwise reasonably assume:

- `<for example: cgroup v1, so container memory is reported differently from v2>`
- `<for example: no metrics server, so pod resource use has to be read by hand>`
- `<for example: a downloader that does not validate certificates>`

## Limitations

- `<what about this environment is unstable between captures>`
- `<what could not be read, and what was assumed instead>`
- `<what a result measured here cannot be generalised to>`

## Authorisation

Required: `<yes / no>`.

Granted by: `<who, and when — or "not required, nothing left this machine">`.

Sensitive values removed before committing: `<hostnames, usernames, absolute paths,
serial numbers, cluster endpoints, credentials>`. A personal filesystem path is not
evidence and does not belong in a public record.
