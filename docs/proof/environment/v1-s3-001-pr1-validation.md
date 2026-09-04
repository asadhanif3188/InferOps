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
uv run --locked ruff format --check . 271 files already formatted
uv run --locked python -m mypy        Success: no issues found in 148 source files
uv run --locked python -m pytest -q   5738 passed, 27 skipped, 14 deselected
```

The suite this change adds:

```text
uv run --locked python -m pytest tests/architecture -q   531 passed
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

The suite now also carries its own adversarial inputs. Nine lines written to break
a rule are asserted to be refused, and four lines the scripts legitimately contain
are asserted to be accepted — because a rule that refuses everything is as useless
as one that refuses nothing. Two of the nine are the exact shapes an earlier
version of this module let through, named below.

### What a second review found

The change was reviewed independently before it was finished. Three findings were
material and all three are fixed here; they are recorded rather than quietly
absorbed, because two of them were holes in checks whose whole purpose is to be
trusted.

| Finding | Why it mattered | Fix |
|---|---|---|
| `read -r disk_path disk_kind <<<"$(inferops::disk_probe_target)"` put the path first, so `read` truncated any path containing a space and glued the tag onto the remainder | `INFEROPS_DISK_VOLUME` is the documented way to point the check at a relocated engine disk, and on Windows those paths routinely contain a space. The truncated path would not resolve, the measurement would be skipped, and a threshold that must not be skippable would be — silently | The word comes first and the path last, so the whole remainder including spaces lands in the path. Verified against a real directory whose name contains a space |
| The "is this delete named" rule used `[\w-]+` for the resource name, which accepts `--all`, so `kubectl delete pod --all -n <ns>` read as a named deletion | A rule written to catch a dropped `-l` accepted the most dangerous shape in the vocabulary. Nothing in the scripts uses it, so it was a hole in a guarantee rather than a live defect — but the guarantee is what the documents claim | The name may not begin with a hyphen, `--all` on a delete is refused outright, and the scoping rule now requires namespaced **and** selected rather than either. Both shapes are in the adversarial inputs |
| The all-namespaces rule matched the substring `"-A "`, which cannot match the flag at the end of a line | Same class of hole: `kubectl delete pods -A` would have passed | Matched as a token in either spelling. Narrowed at the same time to commands that change something: `smoke.sh` reads `kubectl top pods -A`, and a read across namespaces has no blast radius, so refusing it would have been a rule broader than its own rationale |

Two smaller findings were also acted on: the runbook's timing table mixed figures
from different invocations and now labels the certifying run and the spread
separately, and "verified five times with identical output" overstated what the
fifth run does — it runs against the torn-down cluster and correctly fails.

### Documentation

The repository-wide link and whitespace checks run inside the default lane and
passed with it. The POSIX link check in CONTRIBUTING was additionally run over
every document this change touches and reported nothing.

Every command printed in the runbook was executed during this change: `preflight`,
`cluster-up`, `cluster-verify`, `smoke`, `cluster-down`, `cluster-down --workload`,
and `verify-clean`. `proof.sh --cycles N` was **not** executed, because it runs
preflight first and preflight refuses this host; that is recorded in the lifecycle
record along with why.

The elapsed times published in the runbook are the certifying run's own figures,
in a column labelled as such, beside a second column giving the spread across the
three runs of the same sequence made while this was written. The one row that is
not a measurement from here — "13-16 s" for the control plane reaching Ready — is
labelled on the page as quoted from ADR 0001.

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
| Create and verify are repeatable | Met | `cluster-verify.sh` is read-only. Four of its five runs were against a live cluster and all four passed; the two run back to back against the same state were compared with `diff` and were byte-identical. The fifth ran against the torn-down state and correctly failed. `cluster-up.sh --recreate` recreates from any state |
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
