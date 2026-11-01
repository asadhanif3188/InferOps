# EX-08: CVE-2026-111497 in the pinned runtime image, and the renewal of EX-07

Date: 2026-11-01

Classification: **local real evidence, one host, one day,** plus a static reading of
the image's binaries. The scans below were executed with Trivy `0.74.0` against the
pinned runtime image and against two upstream builds, using the vulnerability database
as of `2026-11-01 01:13:06 UTC`. The reachability argument was read from the image's
files, fetched by digest from the registry, and not from a running process. No
container was started, no cluster was created, and no model was loaded. This record
certifies no published claim.

Claim boundary: the pinned runtime image carries two findings that the committed
severity policy blocks on. For each, the vulnerable code is present in the image and
this reading finds no path to it from the serving process. The repository owner
accepted both on 2026-11-01. The image guard accepts those two findings, for that one
image digest, until `2026-12-01`, and still blocks on everything else. The acceptances
are `EX-07`, renewed, and `EX-08`, new, in
[the deferred-risk register](../../security/deferred-risks.md) and in
[the security baseline](../../security/security-baseline.v1alpha1.json).

**What this record does not establish.** It does not establish that either finding is
unexploitable in every configuration of this image: the argument covers the committed
runtime arguments and the ELF files of the `linux/amd64` manifest. It does not read what
a library loads at run time by a path that it builds, and `libggml` imports `dlopen` to
load its back-ends. It does not consider what glibc itself may load while it runs, such
as name-service modules. It does not observe a running process. It does not establish that
the image is free of any other finding tomorrow. It does not state when the database
gained `CVE-2026-111497`: the entry was published on 2026-10-22, and the scan of `main`
passed on 2026-10-23. It verifies no build signature or attestation. It does not rotate
the image, and a rotation is still owed.

## What failed

On 2026-11-01 the `dependency and image vulnerability scan` job failed on pull request
#160, which changes no image, no lockfile, and no scan file. Each other job of that pull
request passed. The job had two reasons to fail, and only the first was visible in its
log:

| Finding | Why it blocked |
|---|---|
| `CVE-2026-84782` | The entry of `EX-07` expired on 2026-10-30, as designed. The guard logged the expiry |
| `CVE-2026-111497` | No entry accepts it. The log does not name it. A local scan, minutes later, with a fresh database, found it in the scan output. The artifact of the hosted job was not read |

Renewing `EX-07` alone would not have turned the gate green.

Between 2026-10-30 and this change, `EX-07` was not in force, and the gate blocked. Each
branch fails in the same way, `main` included, from its next run.

## The findings

| Field | `CVE-2026-84782` (`EX-07`) | `CVE-2026-111497` (`EX-08`) |
|---|---|---|
| Severity | `HIGH` | `HIGH` from Ubuntu, whose rating the scan uses |
| Other scores | CVSS 3.1 `7.4` from Red Hat | CVSS 3.1 `9.8` from the National Vulnerability Database, `8.1` from Red Hat |
| What it is | An out-of-bounds read in the DTLS handshake retransmission of OpenSSL | An out-of-bounds write in the Brotli decoder, `c/dec/decode.c`, for a crafted compressed stream. The advisory states memory corruption, disclosure, denial of service, and possible code execution |
| Packages | `libssl3t64`, `openssl` | `libbrotli1` |
| Installed | `3.0.13-0ubuntu3.12` | `1.1.0-2build2` |
| Fixed in | `3.0.13-0ubuntu3.16` | `1.1.0-2ubuntu0.1` |
| Published | 2026-09-29 | 2026-10-22 |

The image is
`ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384`.
With both entries in the ignore file, the scan reports no other finding at `HIGH` or
`CRITICAL`.

## Why the pin was not moved instead

A patched image exists, and the candidate has changed.

| Build | Digest | Built | `HIGH` and `CRITICAL` findings on 2026-11-01 |
|---|---|---|---|
| `server-b11277`, the candidate that `EX-07` named | `sha256:6d607629e3dd5e85f45c43d1494648126cb3f93f2122c9cd53f43242c94cde14` | 2026-09-30 | `CVE-2026-111497` in `libbrotli1` |
| The `server` tag on 2026-11-01, revision `1052f7e1d62611d328ccc65d38c77cd194ee59fc` | `sha256:d9e9e74ba3f7ef119b1939162b1631f99b75ec703c310d140cfa2fdac8907389` | 2026-10-31 | None |

The owner chose to accept the findings and to keep the pin, for these reasons:

- Before this change, 239 tracked files on `main` named this digest, among them
  fourteen experiment freeze records, and so did 18 of the 62 claims of the register.
- The three runs of V2-E02A, in pull request #160, measured this image, and V2-E02B has
  not run. A rotation now changes the runtime between the two sides of that comparison.
- ADR 0002 names a refresh procedure that the repository still does not have.
- What changed in upstream's builds, in flags, metric names, and the API that the
  adapter reads, has to be established by running a build.

Rotating the pin is still the remediation. These exceptions expire, and the second
candidate above is where that change would start.

## Reachability

Method: [the reader](ex-08-reachability-reader.txt) fetched the `linux/amd64` manifest,
`sha256:fa09617a8e077f327dbf823fc1bafecc82c1bff6503a53416d8c2197d86c85ba`, from the
pinned index digest. It read the image configuration, each ELF file of the five layers
with `pyelftools`, and each `dpkg` entry from `/var/lib/dpkg/status`.
[Its output](ex-08-reachability-output.txt) is committed. It read 1,271 ELF files, 29 of
them under `/app`. It reads regular files and hard links, it does not read a symbolic
link as a file, and it applies the five whiteouts, so a file that a later layer removed
or replaced is not counted.

The closure below starts from all 29 files under `/app`, not from the executable alone,
so it covers each back-end that ggml can load from there. A soname is usually a symbolic
link, so the reader matches a soname to a file by name, in any directory: a name, or a
name followed by a version. That can include a file the loader would not choose, and it
cannot leave one out while each soname resolves. Each did. The reader does not read
`RUNPATH` or the loader's search order.

| Question | Answer |
|---|---|
| Entrypoint | `/app/llama-server`. The configuration of the image states it, `deploy/serving/runtime/container-package.v1.json` declares it, and the rendered chart sets it as the command |
| The closure outside `/app` | Eight files: `ld-linux-x86-64.so.2`, `libc.so.6`, `libcrypto.so.3`, `libgcc_s.so.1`, `libgomp.so.1.0.0`, `libm.so.6`, `libssl.so.3`, `libstdc++.so.6.0.33`. Each soname resolved to a file. These are the libraries that the `EX-07` assessment names |
| Files that link OpenSSL | Two: `libllama-common.so.0.2.0` and `libllama-server-impl.so`, as on 2026-09-30 |
| OpenSSL method functions they import | `TLS_client_method` and `TLS_server_method`, and nothing else ending in `method`, as on 2026-09-30 |
| Files that import a DTLS symbol | None, as on 2026-09-30 |
| Files that link a Brotli library | Under `/app`, none. Outside it, `libcurl.so.4.8.0`, `libfreetype.so.6.20.1`, `libjxl.so.0.7.0`, and the two Brotli libraries that depend on `libbrotlicommon` |
| Files that reach a Brotli library through `DT_NEEDED` | 59, and none under `/app`. No file of the closure is one of them |
| Files under `/app` that import a Brotli symbol | None |
| A decoder linked statically into a file under `/app` | None found: no file there holds the opening of the Brotli static dictionary, which each decoder carries with or without its symbols |
| Other text that matches `brotli` under `/app` | One symbol, `httplib::detail::is_brotli_encoding`, in the two files that link OpenSSL. It is a cpp-httplib helper that compares a header value. No decoder is present for it to call |
| Packages that depend on `libbrotli1` | `libcurl4t64`, `libfreetype6`, `libjxl0.7` |
| Whether the committed configuration runs a program that reaches Brotli | No. The container starts `/app/llama-server`, no probe of the chart runs a command in the runtime container, and no file under `charts` or `gitops` names `curl` or `ffmpeg` |

The vulnerable code of both findings ships in the image and is not on a path from the
serving process that this reading can see. The reasons differ. For OpenSSL the library
is loaded, and the DTLS code is not called. For Brotli no file of the closure names the
library.

**What remains.** The image ships `curl`, `ffmpeg`, `ffprobe`, the `fc-*` tools, and some
GTK tools, and these reach `libbrotli`. None is the entrypoint. The container runs
read-only, as uid `65534`, with each capability dropped, so reaching them means already
running a command inside the container. `libggml` imports `dlopen` and `dlsym`, and this
reading does not follow a path that it builds at run time; its back-ends are files under
`/app`, and those are in the closure. What glibc itself may load while it runs was not
considered. The argument is about these bytes: a different
image needs its own reading, which is why each exception is bound to the digest.

## The exceptions

| Field | `EX-07`, renewed | `EX-08`, new |
|---|---|---|
| Finding | `CVE-2026-84782` | `CVE-2026-111497` |
| Accepted on | 2026-09-30, lapsed on 2026-10-30, renewed on 2026-11-01 | 2026-11-01 |
| Accepted by | The repository owner, on 2026-11-01. No tool reads that acceptance | The same |
| Owner | `security` | `security` |
| Compensating control | `pin-image-by-digest` | `pin-image-by-digest` |
| Review deadline | **2026-12-01**, enforced: the entry carries `exp:2026-12-01`. The last accepted day is 2026-11-30 | The same |
| Bound to | The pinned digest above, enforced by the guard and by a test | The same |
| Scope | This identifier, in the runtime image's ignore file alone | The same |

The window is 30 days. A test limits it to 31. The baseline states `2026-11-01` as the
`acceptedOn` of `EX-07`, because that test measures the window from that field. The
first acceptance date stays in [the assessment](ex-07-runtime-image-exception.md), in
the register, and in the note under `D11` of ADR 0008.

## How the guard reads them

Observed with Trivy `0.74.0` against the pinned image, with the database above and with
`--skip-db-update`, so each row read the same database:

| Ignore file | Trivy exit | Blocked | Suppressed |
|---|---|---|---|
| Both entries, `exp:2026-12-01` | `0` | None | `libbrotli1`, `libssl3t64`, `openssl` |
| The `CVE-2026-84782` entry alone | `1` | `libbrotli1` | `libssl3t64`, `openssl` |
| The `CVE-2026-111497` entry alone | `1` | `libssl3t64`, `openssl` | `libbrotli1` |
| Comments only | `1` | All three | None |
| Both entries, `exp:2026-10-30`, a date already past | `1` | All three | None |
| Both entries, `exp:2026-11-01`, the day of the run | `1` | All three | None |
| Both entries with CRLF line endings | `0` | None | All three |

The committed ignore file before this change held the `CVE-2026-84782` entry with
`exp:2026-10-30` and no entry for the second finding, and the committed script exited
`1` on it. The row for the day of the run confirms again that an entry stops suppressing
on its expiry date itself.

Run through the committed scripts, from Git Bash, against the real Trivy and the pinned
image:

```text
[inferops-security] scanning ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384 for CRITICAL,HIGH findings
[inferops-security] accepting CVE-2026-84782 as listed in scripts/security/runtime-image.trivyignore; it blocks again from 2026-12-01
[inferops-security] accepting CVE-2026-111497 as listed in scripts/security/runtime-image.trivyignore; it blocks again from 2026-12-01
[inferops-security] no CRITICAL,HIGH finding in the pinned runtime image outside the accepted exceptions in scripts/security/runtime-image.trivyignore
[inferops-security] scanning uv.lock (including the test and checks groups) for CRITICAL,HIGH findings
[inferops-security] no CRITICAL,HIGH finding in uv.lock outside the accepted exceptions in scripts/security/dependencies.trivyignore
```

Both exited `0`.

## Environment

| Component | Version |
|---|---|
| Operating system | Microsoft Windows 11 Enterprise, `10.0.26300` |
| Shell | GNU bash `5.2.26`, Git for Windows |
| Python | `3.12.12` |
| `pytest` | `8.4.2` |
| `ruff` | `0.16.4` |
| `mypy` | `2.3.1` |
| Trivy | `0.74.0`, database updated `2026-11-01 01:13:06 UTC` |
| `pyelftools` | `0.33`, for the reachability reading only; not a project dependency |

## What changed

| File | Change |
|---|---|
| `scripts/security/runtime-image.trivyignore` | The entry of `EX-07` expires on 2026-12-01, and the entry of `EX-08` is new |
| `docs/security/security-baseline.v1alpha1.json` | `EX-07` has its new dates and the new candidate. `EX-08` is new |
| `docs/security/deferred-risks.md` | The rows, the count, the section of `EX-07`, and a section for `EX-08` |
| `docs/security/control-matrix.md`, `docs/security/security-method.md` and its data | The two exceptions and the count |
| The README, `SECURITY.md`, the architecture index | "seven" exceptions become "eight" |
| ADR 0008 | A new dated note after the `D11` note. The released text and each earlier note are unchanged |
| `docs/proof/security/ex-07-runtime-image-exception.md` | A dated `Renewal` section at the end. The text above it is unchanged |
| This record, its reader, and its output | New |
| `tests/security/test_security_maintenance_history.py` | The new note is registered. The two tripwires compare the renewed scope, as their comment requires of a change that moves the deadline, and one is renamed for that reason |
| `docs/proof/README.md`, `docs/testing/test-inventory.md` and its data, `CHANGELOG.md` | This record, the changed test, and a `Security` entry |

The reconciliation of 2026-10-01 and the note of that date under `D11` stay as written,
and the pinned scope stays in the test beside the renewed one. No image, chart, contract,
script, workflow, or tool changed. Revision 4 of the V2-E02A record is unchanged:
`--changes` prints `UNCHANGED`. Among the experiment records, only revision 3 of V2-E01,
whose runs are complete, names a file that this change edits. No claim moved.

## What the independent review found

Two reviewers read the first commit, `c36dd1b`. Neither found a way to make the guard
accept more than these two findings, for another image, or past the deadline. Each count
and date of this record that they recomputed agreed.

| Finding | Severity | What the first commit had | What was done |
|---|---|---|---|
| The reader skipped hard links, and the record said that it read each ELF file | medium-low | `member.isfile()` is false for a hard link, so the count was 1,270 | The reader follows hard links. The count is 1,271. No other line of the output changed |
| The reader ignored whiteouts, and the record did not say so | low | A file that a later layer removed stayed in the sets. That can only over-include, and the record was silent | The reader applies them, and the record states what it reads |
| `lstrip("./")` strips characters, not a prefix | low | A name that starts with a dot at the root loses it, which hides a root whiteout | `removeprefix` |
| The entrypoint row did not follow from the output | low | The reader never read the image configuration. The row was true, from other files | The reader prints the configuration, and the row names its three sources |
| The closing argument named `dlopen` alone | low | It left out what glibc may load, which the `EX-07` assessment states. "Not linked at all" said more than a `DT_NEEDED` reading shows | The caveat is carried over, and the sentence states what was read |
| The first commit said that each probe is `httpGet` | low | The liveness probe of the runtime is `tcpSocket` | The row now says that no probe runs a command in the runtime container |
| The inventory data was not edited | medium | `test-inventory.md` had the renewal, and its data did not | The data states it |
| The name of one tripwire was no longer true | low | `test_ex07_keeps_the_scope_it_was_reconciled_with` compared the renewed scope | Renamed, and its docstring and two references follow |
| The change column of the note used a branch name | cosmetic | A branch name does not last | `EX-08` |

Before the first commit, the reader's closure left out `libstdc++` and `libgomp`,
because a soname is usually a symbolic link. The difference from the `EX-07` assessment
showed the defect.

## Mutation check

Each defect was applied to one committed file alone, four modules were run, and the file
was restored byte for byte. The modules are
`test_vulnerability_scan_exceptions.py`, `test_security_maintenance_history.py`,
`test_security_baseline.py`, and `test_published_methods.py`, 1,502 tests.

| Defect | Failed |
|---|---|
| The entry of `EX-08` expires a day later than its deadline | 2 |
| The entry of `EX-08` is removed | 2 |
| The entry of `EX-07` goes back to `exp:2026-10-30` | 2 |
| The entry of `EX-08` sits under no comment of its own | 1 |
| A third finding is accepted in the ignore file | 3 |
| The window of `EX-07` is measured from 2026-09-30 | 2 |
| `EX-08` names another image | 2 |
| The note of 2026-11-01 under `D11` is edited | 1 |
| The note of 2026-10-01 is rewritten to say eight | 2 |
| The `Renewal` section loses its date | 1 |
| The `EX-07` assessment above its correction is edited | 1 |
| This record loses the fixed version of `libbrotli1` | 1 |
| The heading of `EX-08` in the register is renamed | 1 |
| The README goes back to seven | 1 |
| The published method drops `EX-08` | 2 |

One defect survived. A section of the register that moves from `###` to `####` still
passes, because the check looks for `### EX-08 ` as a substring. The section is still
there, so this change leaves the check as it is.

## Validation

Run from Git Bash, at `f12f371`, the commit before the one that adds this table. That
commit changes this file only. The last three rows were run on the tree with this table.

| Check | Result |
|---|---|
| `pytest`, the default lane, in a clean clone | 23,505 passed, 42 skipped, 14 deselected, in 1:09:37 |
| `ruff check .` | All checks passed |
| `ruff format --check .` | 810 files already formatted |
| `scripts/security/scan-runtime-image.sh`, `scan-dependencies.sh`, Trivy 0.74.0, database of `2026-11-01 01:13:06 UTC` | Both exit `0` |
| `python -m tools.evidence_index --gate` | Exit `0` |
| `python -m tools.experiment_freeze --check` | 32 records, each rule held |
| `--changes` of revision 4 of V2-E02A | `UNCHANGED` |
| `pytest tests/security tests/testing/test_published_methods.py tests/testing/test_test_inventory.py tests/testing/test_document_links.py` | 3,393 passed |
| `mypy`, and `mypy --platform linux` | No issue in 448 source files, each |
| `uv build --wheel` | Built |

The hosted checks start when the pull request opens, and this record does not state them.
