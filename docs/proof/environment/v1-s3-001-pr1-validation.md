# V1-S3-001-PR1 change validation

Date: 2026-09-04

Classification: local static evidence for the change itself. The runtime evidence
this change produced is separate, in
[the cluster lifecycle result](v1-s3-001-pr1-cluster-lifecycle.md).

Claim boundary: validates the files this change adds and edits — that the scripts
parse and lint, that the new suite passes and is not vacuous, that the default
lane is still green, that the documents link correctly, and that nothing private
or overclaimed is published. It says nothing about cluster behaviour; that is the
other record's job.

## Environment

| Component | Version |
|---|---|
| Operating system | Microsoft Windows 11 Enterprise, `10.0.26200` |
| GNU bash | `5.2.26(1)-release (x86_64-pc-msys)` |
| Python | `3.12` (`uv run --locked`) |
| ShellCheck | `0.11.0` |
| kind | `v0.32.0` |
| kubectl client | `v1.36.1` |
| Container engine server | `29.7.2` |

## Commands and results

### Shell scripts

```text
bash -n scripts/environment/*.sh scripts/security/*.sh
shellcheck -x -S style scripts/environment/*.sh
```

Both clean, exit `0`. `shellcheck` was run at `style` severity, which is stricter
than its default, and the new `cluster-verify.sh` and the edits to `lib.sh`,
`preflight.sh`, `cluster-up.sh`, `cluster-down.sh`, `proof.sh`, `smoke.sh`, and
`verify-clean.sh` raised no finding.

One pre-existing observation, recorded rather than fixed: running the same command
over `scripts/security/*.sh` reports `SC1091` (info) three times, because those
scripts source their library through a variable and carry no
`# shellcheck source=` directive. Those files are untouched by this change —
`git diff main -- scripts/security/` is empty — and cleaning up unrelated code is
outside this change's boundary. It is named here so that the next contributor
running the command from CONTRIBUTING is not surprised by a non-zero exit that
this change did not cause.

### Python

```text
uv run --locked ruff check .          All checks passed!
uv run --locked ruff format --check . 270 files already formatted
uv run --locked python -m mypy        Success: no issues found in 148 source files
uv run --locked python -m pytest -q   5729 passed, 27 skipped, 14 deselected in 78.92s
```

The suite this change adds:

```text
uv run --locked python -m pytest tests/architecture -q   523 passed in 1.52s
```

### The new suite is not vacuous

A suite of static assertions can pass because the property holds or because the
assertion never looks at anything. Five of its rules were checked by breaking the
thing they defend and confirming a red result, then reverting:

| Rule | Break introduced | Result |
|---|---|---|
| Deletions are scoped | *(found in the first run)* `cluster-down.sh`'s label-scoped delete read one physical line at a time | Failed, correctly, and the check was fixed to join shell continuations rather than the script relaxed |
| Every script refuses an unknown argument | *(found in the first run)* `preflight.sh`, `smoke.sh`, and `verify-clean.sh` had no argument guard | Failed on all three. **The scripts were fixed**, not the rule |
| No command hardcodes the cluster name | *(found in the first run)* the check flagged `deploy/kind/inferops-dev.yaml` in a path assignment | Failed on a false positive, and the rule was narrowed to lines that invoke a tool |
| The disk threshold is the documented one | `INFEROPS_MIN_FREE_DISK_BYTES` temporarily raised to `900000000000` | Failed, naming both figures. Reverted |
| The pin is one value wherever published | *(exercised during the 1.36.1 experiment)* the pin moved in `lib.sh` and the kind config but not in the ADR or the runbook | Failed on the two documents that still carried the old value |

The first three rows are the ones that matter most: three of the suite's rules
failed on the code as committed before this change, and two of those were fixed in
the scripts rather than in the test.

### Documentation

The repository-wide link and whitespace checks run inside the default lane and
passed with it. The POSIX link check in CONTRIBUTING was additionally run over
every document this change touches and reported nothing.

Every command printed in the runbook was executed during this change: `preflight`,
`cluster-up`, `cluster-verify`, `smoke`, `cluster-down`, `cluster-down --workload`,
and `verify-clean`. `proof.sh --cycles N` was **not** executed, because it runs
preflight first and preflight refuses this host; that is recorded in the lifecycle
record along with why.

The elapsed times published in the runbook are the measured figures from that run,
and the "13-16 s across four creations" row is quoted from ADR 0001 rather than
re-measured here.

### Private-information review

The diff was read for anything that should not be published. Checked and clear:

- No absolute filesystem path, workspace directory name, host name, or user
  account appears in any added or edited file. The scripts derive their root from
  `BASH_SOURCE`, and every path in a document is repository-relative.
- No content from any private planning document was copied. Story and PR
  identifiers appear as identifiers only.
- No credential, token, registry secret, or model artifact.
- The one absolute path this change can print at runtime — the volume the disk
  check measured — is emitted to a terminal and written to no committed file.
  `INFEROPS_DISK_VOLUME=/d` in the runbook is an illustration, not a real path
  from this host.
- The two node-image digests published here are public content-addresses of a
  public image.

## Acceptance criteria

| Criterion | Status | Where |
|---|---|---|
| Create and verify are repeatable | Met | `cluster-verify.sh` is read-only and was run five times across three cluster states with identical output; `cluster-up.sh --recreate` recreates from any state |
| Destroy targets only the named InferOps cluster | Met, and now tested | Unchanged behaviour from Sprint 0, plus static rules that every cluster deletion names the cluster and every object deletion is namespaced and label-scoped or named |
| Required host resources are checked | Met | Processors, memory reaching the container VM, and free disk, each compared against ADR 0001 (D7)'s minimum tier, with the constants held to that table by test |
| Failure leaves actionable diagnostics | Met | `cluster-verify.sh` reports every problem in one run and prints the cluster list, labelled containers, and recent `kube-system` events before exiting non-zero; five injected failures are recorded in the lifecycle result |

## What this does not establish

- That the scripts do what they say when run. This record is static; the runtime
  result is the record beside it, and it is one host's.
- That the disk figure measured on Windows is the engine's own storage. It is the
  volume the engine places its virtual disk on by default, and both the script and
  the runbook say so every time they report it.
- Anything about Linux or macOS, Helm, Terraform, or serving.
