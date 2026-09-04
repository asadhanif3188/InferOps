# Local runtime troubleshooting

Status: **every diagnostic command on this page was executed on one contributor
host and the results are recorded** in
[the change validation record](../proof/serving/v1-s2-008-pr1-validation.md). No
recovery step that starts a container, downloads a model, or runs a measurement
was executed by this change; each is marked where it appears.

This page is for the second engineer. It is organised by **what you observed**,
not by which component owns the fault, because the observation is the only thing
you have when you arrive. Each entry names the check that distinguishes the
plausible causes, the recovery that follows, and — where one exists — the
measured evidence behind the number it quotes.

Everything here is the host-local path: the
[model cache](model-acquisition.md), the
[standalone runtime package](local-runtime-package.md), the
[local real composition](local-real-composition.md), and the
[lifecycle](model-lifecycle.md) that spans them. **Kubernetes is deliberately out
of scope.** A chart exists — [`charts/inferops-llm/`](../../charts/inferops-llm/),
added by `V1-S3-002-PR1` — and no documented workflow installs it: it has no
probes, no lifecycle test, and no published API image to run. Nothing in this
repository deploys a manifest, so a troubleshooting section for a deployment path
nobody can follow would still be advice rather than documentation. It arrives
when the path does.

## Before anything else

Three rules, because each one is the difference between a diagnosis and a second
incident.

1. **Run every command from the repository root**, through `uv run --locked`. A
   command run from elsewhere reads a different cache path and reports a
   different state.
2. **No diagnostic on this page downloads, pulls, starts, or deletes anything.**
   The recovery steps that do are marked **destructive**, **network**, or
   **starts a container**, and each is a separate deliberate decision.
3. **Never paste a prompt, a completion, a runtime response body, or a runtime
   log line into an issue.** The
   [redaction rules](../telemetry/redaction.md) forbid content capture, and a
   troubleshooting report is not an exemption. The tooling on this page prints
   states, byte counts, statuses, and durations, and that is sufficient to
   diagnose everything below.

The commands here accept no token, header, password, or alternate URL, and the
repository holds none. If a step appears to need a credential, that is itself the
fault: stop and report it, because the selected model and image are both
anonymous.

## The four checks that localise almost everything

Run these in order. Each is offline, read-only, and takes under a second except
where noted.

```text
uv run --locked python -m tools.model_acquisition check
uv run --locked python -m tools.model_lifecycle cache
uv run --locked python -m tools.runtime_packaging check
uv run --locked python -m tools.local_composition check
```

| Command | Answers | Exit `0` means |
|---|---|---|
| `model_acquisition check` | Is the artifact present, and is there disk for the rest of it | Prerequisites and cache state readable |
| `model_lifecycle cache` | `hit`, `miss`, or `partial`, and which lifecycle state that is | **`hit` only.** Anything else exits `3` |
| `runtime_packaging check` | Does the container descriptor still agree with the profile and the pins | The package would run the command it publishes |
| `local_composition check` | Do the API and runtime halves still agree on ports, adapter, and order | The composition is internally consistent |

The second one is the one to read carefully: `model_lifecycle cache` is the only
check that exits non-zero for a *legitimate* state. A `miss` is not a broken
repository, it is an absent 1.71 GiB file, and the command is built to be usable
as a precondition guard for exactly that reason.

If all four pass and the runtime still will not serve, the fault is in the host,
the engine, or the run itself — continue to the symptom tables.

## Exit codes

Every command in this workflow uses the same vocabulary, so the number tells you
which half of the problem you have before you read the message.

| Code | Meaning | Where |
|---|---|---|
| `0` | Succeeded | all |
| `3` | **Refused** — a precondition was not met and nothing was attempted | all |
| `4` | Ran and **failed** | packaging, lifecycle, composition, certification, baseline |
| `5` | Composed but **not ready** | `local_composition status` |
| `6` | Ran, and the pre-registered **success criteria were not met** | `serving_baseline` |
| `130` | Interrupted with Ctrl-C | the attached commands |

`model_acquisition` splits the failure space further, because the stage that
refused is the thing you need: `3` prerequisite, `4` verification, `5` transfer,
`6` cleanup.

**A refusal is not a bug.** Every `3` on this page is a guard doing its job, and
the recovery is to satisfy the precondition rather than to bypass the guard.
Nothing in this tooling has a force flag, and no step below tells you to add one.

## Prerequisites

### `uv` reports that the lockfile would change

The environment is not the recorded one. Run `uv sync --locked` from the
repository root; if it still refuses, your `pyproject.toml` differs from
[`uv.lock`](../../uv.lock) and that is a dependency change, not a runtime fault.
Do not refresh dependencies as part of diagnosing a runtime problem — a check
whose inputs were re-resolved measures the package index as much as the
repository. [CONTRIBUTING](../../CONTRIBUTING.md) owns that rule.

### `docker` is not found, or the engine is unreachable

Every real step needs a Docker-API-compatible engine already running. Confirm it
answers before blaming anything downstream:

```text
docker version --format "{{.Server.Version}}"
```

An error here means the engine is absent or not started. The tooling reports this
as a refusal (`3`) rather than attempting a start: nothing in this repository
installs, configures, or starts a container engine.

### The pinned image is not local

Nothing pulls implicitly, by design — an implicit pull is how a digest pin stops
meaning anything. Confirm the exact digest the package publishes is present:

```text
uv run --locked python -m tools.runtime_packaging check
docker image inspect <the digest printed above> --format "{{index .RepoDigests 0}}"
```

If `docker image inspect` reports no such image, pull that exact digest yourself.
That is a **network** step, it is the one documented in
[the package prerequisites](local-runtime-package.md#prerequisites-for-a-real-run),
and it is deliberately yours to authorise.

### The host cannot meet the profile at all

See [when the hardware is the answer](#when-the-hardware-is-the-answer) below,
and check it *before* spending twenty minutes on a download.

## Model acquisition, revision, and integrity

| Symptom | What it means | Next step |
|---|---|---|
| `state  absent` | Nothing cached. A start will refuse | An explicit `acquire` — **network**, 1,834,426,016 bytes |
| `state  partial (N bytes present)` | A transfer was interrupted | Rerun `acquire`. It requests the remaining range; it never promotes unverified bytes |
| `state  verified` but a start still refuses | The artifact is fine; the fault is downstream | Continue to [ports](#ports-and-endpoints) or [readiness](#readiness-and-slow-model-load) |
| Exit `4` from `verify` | The cached bytes do not match the pinned size or SHA-256 | [Cache corruption](#cache-corruption-and-staleness) below |
| Exit `5` from `acquire` | The transfer itself failed | Rerun it. Repeated failure at the same offset is a network or source problem, not a repository one |
| A refusal naming an inconsistent range | The source answered a resumed request incorrectly | The partial is **retained on purpose** so the state can be inspected. Use the guarded cleanup before retrying |

Verify what is already there without touching the network:

```text
uv run --locked python -m tools.model_acquisition verify
```

That reads 1.71 GiB end to end and compares the digest. It is the authoritative
integrity answer, and it is the reason
[`model_lifecycle cache`](model-lifecycle.md#cache-hit-miss-and-partial) leaves
digest verification off by default: reading the artifact warms the host's own file
cache, which is exactly the variable a cold-start measurement is trying not to
disturb.

Two failure shapes worth telling apart. A **size or digest mismatch on a partial**
discards the partial: those bytes were never trusted. A **mismatch on the final
cache entry** refuses and *retains* the file, because a final entry that changed
under you is a fact about the host worth seeing rather than deleting.

There is no way to point this workflow at a different revision, URL, or file. The
pins live in [`model-source.v1.json`](model-source.v1.json) and
[ADR 0002](../architecture/decisions/ADR-0002-model-and-serving-runtime.md), and
a check that could be redirected would certify nothing.

## Disk

`model_acquisition check` prints free space against what the remaining transfer
needs. A fresh cache needs about 1.77 GiB — the artifact plus 64 MiB of headroom
— and the runtime image is a further ~293 MiB that this figure does **not**
include.

Read the free space on the volume that actually holds the cache:

```text
uv run --locked python -c "import shutil; u = shutil.disk_usage('.cache'); print(f'{u.free / 1024**3:.2f} GiB free of {u.total / 1024**3:.2f} GiB')"
```

Two things a disk-constrained host should know before it starts freeing space:

- A Docker Desktop **virtual disk does not return space to the host** when
  containers or images are removed. Reclaiming inside the engine does not
  reclaim outside it. [The prerequisites](../prerequisites.md) record the same
  caveat for the local cluster.
- The model cache is the largest single thing this repository writes, and it is
  the one thing every cleanup here refuses to touch. Removing it is
  [its own confirmed operation](model-acquisition.md#workspace-scoped-cleanup)
  and costs a 1.71 GiB re-download.

## Ports and endpoints

Two loopback ports are in play, and nothing publishes beyond loopback:

| Port | Owner | Set by |
|---|---|---|
| `8080` | The `llama-server` container | [`container-package.v1.json`](../../deploy/serving/runtime/container-package.v1.json) |
| `8090` | The InferOps API's tooling HTTP carrier | [`composition.v1.json`](../../deploy/serving/local/composition.v1.json) |

Check both without binding anything:

```text
uv run --locked python -c "import socket
for port in (8080, 8090):
    with socket.socket() as probe:
        probe.settimeout(1)
        print(port, 'in use' if probe.connect_ex(('127.0.0.1', port)) == 0 else 'free')"
```

A port reported **in use** before you start anything is the fault. The most
common cause is a previous run that was not torn down; check that first, because
the recovery differs:

```text
docker ps -a --filter label=io.inferops.package=llama-cpp-local-runtime --format "{{.Names}} {{.Status}}"
```

- **A row is printed.** A previous run left its container behind. Use the
  [scoped cleanup](#shutdown-and-cleanup) below. Do not `docker rm` by hand;
  the guarded path verifies ownership first.
- **Nothing is printed and `8080` is still busy.** Something outside this
  workflow holds the port. Neither the package nor the composition has a port
  override — the value is pinned in the descriptor and cross-checked — so the
  recovery is to free the port, not to move the service.

`start` refuses to run beside an existing container carrying the package's own
name. That refusal is deliberate: a second container on the same pinned port
would produce a measurement of whichever one answered first.

## Memory and out-of-memory

The container is capped at a 3,072 MiB limit against a 2,048 MiB request, sized
from a measured 2.167 GiB worst case on one host. The figures and their
limitations are in [the prerequisites](../prerequisites.md#serving-and-model-prerequisites).

| Symptom | Likely cause |
|---|---|
| The container exits almost immediately after `start` | The engine could not satisfy the memory request, or the image/command is wrong. `start` reports the exit rather than waiting for a readiness that will never come |
| The container is killed partway through the load | The engine's memory ceiling, not the limit in the descriptor |
| Load takes minutes and the host is swapping | Host memory pressure — see [slow model load](#readiness-and-slow-model-load) |

Read what the engine itself believes it has:

```text
docker info --format "{{.NCPU}} CPUs; {{.MemTotal}} bytes"
```

On Windows and macOS this is the **binding limit**, not the host's installed
memory, and it defaults to roughly half of it. A host with 16 GiB installed can
easily present under 8 GiB here. [ADR 0001](../architecture/decisions/ADR-0001-local-development-environment.md)
records that as the constraint it is.

Do not size the container from the runtime's *private* memory. The weights are
memory-mapped; the runtime's private working set on the measured host was
531 MiB while its worst-case charge was 2.167 GiB, and sizing from the first
number produces a limit that kills the process.

## Readiness and slow model load

This is the section most likely to be misread as a hang.

**A `503` on `GET /health` is the model loading.** It is correct readiness
reporting, it is not a fault, and it must not restart anything. That is why
liveness is a TCP connection to the port and readiness is the HTTP endpoint —
the two disagree throughout the load *by design*, and the
[lifecycle record](model-lifecycle.md#why-liveness-and-readiness-must-disagree)
enforces it rather than describing it.

| Symptom | Reading |
|---|---|
| `503` on `/health`, TCP connects | `runtime-loading`. Wait, inside the 300,000 ms startup budget |
| TCP refuses and `/health` is unreachable | The process is not up. Check the container's status and exit |
| `200` on `/health`, but API `/health/ready` is false | The API half has not observed the runtime yet, or the adapter identity does not match |
| Readiness was true and is now false | Correct. A ready runtime that answers `503` again becomes not-ready rather than latching |
| The startup budget elapsed | See below — this may be the host rather than a fault |

**Measured load times on the one host this project has evidence from:**

| Run | Model load | Against a 300,000 ms budget |
|---|---|---|
| [`V1-S2-005` first attempt](../proof/serving/v1-s2-005-baseline-raw-results.md) | 358,735 ms | **Exceeded** |
| [`V1-S2-005` recorded run](../proof/serving/v1-s2-005-baseline-raw-results.md) | 269,079 ms | Met, by 30.9 s |
| [`V1-S2-007` cold arm](../proof/serving/v1-s2-007-pr1-cold-warm-start.md) | 133,515–215,672 ms | Met |

Read that table before concluding that a slow start is broken. **The budget is
not comfortably met on every attempt on that host**, the spread between identical
runs reached 82,157 ms, and a load of two to four minutes for a 1.7 B-parameter
Q8 model is consistent with a memory-constrained host and a virtual-machine bind
mount rather than with the model's size. If your startup budget elapses once,
retry before investigating; if it elapses repeatedly, the host is the finding.

Do not raise `INFEROPS_LLAMA_SERVER_STARTUP_BUDGET_MS` to make a slow host look
healthy. The budget is a published bound, and a deployment that needs a larger
one has told you something about the hardware.

## Timeouts

Three separate budgets, and confusing them is the usual reason a timeout is
"fixed" in the wrong place.

| Budget | Required? | Bounds |
|---|---|---|
| `INFEROPS_LLAMA_SERVER_STARTUP_BUDGET_MS` | **Required. No default** | How long the model may take to become ready |
| `INFEROPS_REQUEST_TIMEOUT_MS` | **Required. No default** | How long one inference request may take |
| `INFEROPS_DRAIN_TIMEOUT_MS` | Optional; defaults to 15,000 ms | How long a graceful shutdown gives in-flight work |

**Only the drain budget has a fallback.** Omit either of the other two and the
deployment refuses at startup, naming the variable — it does not quietly adopt a
number. The 300,000 ms and 120,000 ms figures quoted elsewhere on this page are
what this deployment's descriptors *select*; they are not values the distribution
would supply on your behalf.

The two required budgets have no default on purpose:
[ADR 0002](../architecture/decisions/ADR-0002-model-and-serving-runtime.md)
decides no deadline, and a number invented by the API would be read back as a
recommendation nobody made. The drain budget's 15,000 ms is itself described as a
default rather than a decision.

Sizing it from the only measured evidence this project has — thirty single,
sequential requests on one CPU host, which is **not** a benchmark and may not be
published as one — the recorded latencies were P50 6,422 ms, P95 17,718 ms, P99
23,516 ms, max 23,516 ms. A budget below roughly 30 s on a comparable host will
convert ordinary slowness into timeouts.

| What you see | Canonical error | Status |
|---|---|---|
| The runtime did not answer inside its budget | `upstream-timeout` | 504 |
| The caller's own deadline elapsed first | `request-timeout` | 504 |
| The model is still loading | `model-not-ready` | 503 |
| The runtime is unreachable | `capability-unavailable` | 503 |

The full mapping is in [the inference API](inference-api.md). A canonical error
is the deployment telling you which of those four happened; it is not a generic
failure and it is worth reading before changing a number.

## Cache corruption and staleness

| Symptom | Meaning |
|---|---|
| `verify` exits `4` on the **final** artifact | The cached bytes changed. The file is retained, not deleted, so you can see what happened |
| `acquire` reports `cache hit` when you expected a download | The bytes are already present and verified. This is the intended fast path and needs no network |
| `model_lifecycle cache` says `partial` after a completed download | A `.part` file survived. The final entry is never overwritten by a transfer |
| The cache path looks wrong | The path is revision-scoped and cross-checked against [`model-source.v1.json`](model-source.v1.json); a different path means a different revision |

Recovery for a corrupt final entry is the guarded cleanup, and it is
**destructive** and costs a 1.71 GiB re-download:

```text
uv run --locked python -m tools.model_acquisition clean
uv run --locked python -m tools.model_acquisition clean --confirm
```

The first form changes nothing and prints exactly what would go. The command
refuses a target outside `.cache/inferops/models`, a path resolving outside the
checkout, and a symbolic link in or above the managed tree. It has no path
override. It does not remove images, cluster volumes, other `.cache` content, or
anything else.

**Do not delete the cache to fix a problem you have not localised.** A `miss` is
the most expensive state in this workflow to be in.

Stale *results* are a different and much cheaper problem. Measurement output
lives under `.cache/inferops/lifecycle`, `.cache/inferops/baseline`,
`.cache/inferops/composition`, and `.cache/inferops/certification`, all ignored
by Git. The lifecycle cleanup reaches its own directory and cannot reach the
model cache — that refusal is checked first, ahead of every other guard:

```text
uv run --locked python -m tools.model_lifecycle clean
uv run --locked python -m tools.model_lifecycle clean --confirm
```

## API-to-runtime connectivity

The composition refuses an incomplete real configuration and **never falls back
to the mock**. That is the behaviour, not a limitation: a mock answering in place
of an absent runtime would produce evidence that certifies nothing while looking
exactly like evidence that certifies something.

Ask whether the deployment configuration would be accepted, without binding a
port, starting a process, or contacting the runtime:

```text
uv run --locked python -c "import os
from inferops.api.selection import select
try:
    selection = select(os.environ)
except Exception as refusal:
    print(f'refused: {type(refusal).__name__}: {refusal}')
else:
    print(f'accepted: {selection.adapter_kind}')"
```

It names the first variable it refuses, one at a time. Executed against an empty
environment it reports `INFEROPS_SERVING_ADAPTER: is required and is not set`;
against `real` with the runtime variables absent it names
`INFEROPS_LLAMA_SERVER_ENDPOINT` next.

| Refusal | Cause |
|---|---|
| `INFEROPS_SERVING_ADAPTER: is required and is not set` | Unset or empty. **It does not select the mock** |
| `must name one of the adapters this platform serves` | A near miss — `Mock`, `mocked`, `Real`. These are the ones people actually type |
| A named `INFEROPS_LLAMA_SERVER_*` variable is required | A real selection with an incomplete runtime configuration |
| `modelPath: must be an absolute path inside the serving container` | The path is not container-absolute — **but read the next section before believing it** |

### The Git Bash path rewrite, on Windows

`INFEROPS_LLAMA_SERVER_MODEL_PATH` is a path *inside the serving container*, and
Git Bash on Windows rewrites a leading `/` into a Windows path before the process
ever sees it. `/models/Qwen3-1.7B-Q8_0.gguf` arrives as
`C:/Program Files/Git/models/Qwen3-1.7B-Q8_0.gguf`, and the refusal that follows
names the value you did not type.

**This was reproduced and confirmed on the host this page was written on.** Set
`MSYS_NO_PATHCONV=1` for the command, or use PowerShell, where the rewrite does
not happen:

```text
MSYS_NO_PATHCONV=1 INFEROPS_LLAMA_SERVER_MODEL_PATH=/models/Qwen3-1.7B-Q8_0.gguf ...
```

With the rewrite suppressed, the same configuration is accepted and reports
`real`. If you see a refusal naming a path with `Program Files` in it, this is
what happened, and nothing about the container or the model is wrong.

### Once both halves are running

`status` inspects Docker and the real endpoints, so it needs the confirmation
flag even though it changes nothing. `logs` reads only this workflow's own
bounded structured records and needs no runtime access:

```text
uv run --locked python -m tools.local_composition status --confirm-real-runtime
uv run --locked python -m tools.local_composition logs --lines 100
```

Those records carry operational identifiers and outcomes — never prompts,
completions, runtime response bodies, Docker output, credentials, or model bytes
— which is what makes them safe to attach to a report.

Exit `5` from `status` is **composed but not ready**, which is a different fault
from exit `3` (refused) and exit `4` (failed). Read the code before the message.

## Shutdown and cleanup

Shutdown is ordered, and the order is the property:

1. stop accepting new work and report readiness false;
2. drain accepted work inside the 15,000 ms budget, recording whether it
   finished;
3. close the adapter transport;
4. stop and remove **only** the ownership-labelled container.

A drain that is truncated is recorded rather than hidden, because the requests it
abandoned were real.

| Symptom | Next step |
|---|---|
| Ctrl-C left a container behind | `local_composition cleanup --confirm-real-runtime`, or `runtime_packaging stop --confirm-real-runtime` for a standalone run |
| Cleanup reports it removed nothing | Confirm ownership first with the `docker ps -a --filter label=...` command [above](#ports-and-endpoints). Absence is only reported after a successful inventory |
| A container exists with the right name but no ownership label | **Not ours.** Every cleanup refuses it, deliberately. Investigate before removing anything by hand |
| `stop` reports a failure | A failed cleanup is a failed command, by design. Do not treat a leaked container as a successful run |

There is **no shutdown endpoint**, and there will not be one.
[ADR 0010](../architecture/decisions/ADR-0010-inference-api-compatibility-surface.md)
declined it: an HTTP route that stops a process is an unauthenticated remote-stop
control on a surface
[ADR 0008](../architecture/decisions/ADR-0008-v1-security-baseline.md) accepts
with no authentication in V1.

No cleanup on this page removes the model cache, removes the pinned image, prunes
the container engine, or touches a container the ownership check does not claim.

## When the hardware is the answer

Some symptoms are not faults. The `C2` certification workflow encodes the floor
below which the profile should not be attempted, and it checks capacity **before**
it verifies the artifact hash, precisely so a host that cannot serve the workload
learns that before reading two gigabytes:

| Prerequisite | Required |
|---|---|
| Logical CPUs visible to the engine | 6 |
| Memory reaching the engine | 4,294,967,296 bytes (4 GiB) |
| Free disk on the cache volume | 2,147,483,648 bytes (2 GiB) |
| Container engine | reachable |
| Pinned image | already local |
| Model artifact | present and hash-verified |

The CPU path also requires **AVX2**. AVX-512 is not required, and no accelerator
is needed or used. Probe it on the host:

```text
uv run --locked python -c "import ctypes, sys
if sys.platform == 'win32':
    print('AVX2', bool(ctypes.windll.kernel32.IsProcessorFeaturePresent(40)))
else:
    print('AVX2', 'avx2' in open('/proc/cpuinfo').read())"
```

Read the honest conclusion before sizing anything from the table: **these are
observations from one Windows host, not supported-platform minima.** No second
host has ever run this workflow. The Linux branch of the probe above is
documented and has never been executed here.

Three known unresolved limitations, stated because each one will otherwise be
diagnosed repeatedly as a bug:

- **The startup budget is not comfortably met on the measured host.** One
  recorded run exceeded 300,000 ms. This is unresolved: the budget has not been
  raised, because raising it would hide the finding.
- **The model crosses a virtual-machine bind mount on Docker Desktop.** That path
  is why load takes minutes rather than seconds, and no change in this repository
  can shorten it. A host-side file cache may not warm what the guest reads at
  all.
- **A real cache miss has never been measured.** Every recorded start was a
  cache hit. The miss and partial paths are documented and exercised
  synthetically; no measured figure for a cold acquisition exists, and none may
  be quoted.

## What this page is evidence of

The diagnostics here were **executed**; the recoveries that start a container,
transfer bytes, or measure a start were **not executed by this change**. The
distinction is the whole point of
[the certification levels](../testing/certification.md), and it survives into a
troubleshooting guide: a command that was run and a command that was written down
are different kinds of statement.

- `local-static` — every check, probe, and read-only inspection on this page,
  executed on one host and recorded in
  [the validation record](../proof/serving/v1-s2-008-pr1-validation.md).
- `local-real-cpu`, from prior authorised runs — every measured figure quoted
  here. Each links to the record that produced it. None of them is a benchmark,
  and [the project boundaries](../architecture/project-boundaries.md) forbid
  publishing one from V1.
- **Unexecuted here** — `acquire`, `start`, `smoke`, `certify`, `measure`, and
  `run`. They are described, bounded, and authorisation-gated; this page did not
  run them and claims nothing from them.

[`tests/serving/test_local_runtime_troubleshooting.py`](../../tests/serving/test_local_runtime_troubleshooting.py)
holds this page to the repository: every tool command it prints must name a real
module and a real subcommand, every exit code it publishes must be the one the
tool returns, every port, byte count, and budget must match the record that owns
it, and no fenced block may contain a credential-shaped flag. A guide whose
commands have drifted is worse than no guide, because it is read at three in the
morning by someone who trusts it.
