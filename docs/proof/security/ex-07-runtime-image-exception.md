# EX-07: CVE-2026-84782 in the pinned runtime image

Date: 2026-09-30

Classification: **local real evidence, one host, one day,** plus a static reading of
the image's binaries. The scans below were executed with Trivy `0.74.0` against the
pinned runtime image and against one newer upstream build, using the vulnerability
database as of `2026-09-30 07:10:47 UTC`. The reachability argument was read from the
image's files, fetched by digest from the registry, and not from a running process. No
container was started, no cluster was created, and no model was loaded. This record
certifies no published claim.

Claim boundary: the pinned runtime image carries one `HIGH` finding the committed
severity policy blocks on; the vulnerable code is present in the image and nothing in
the serving path calls it; the image guard now accepts that one finding, for that one
image digest, until `2026-10-30`, and still blocks on everything else. The acceptance
is `EX-07` in [the deferred-risk register](../../security/deferred-risks.md) and in
[the security baseline](../../security/security-baseline.v1alpha1.json).

**What this record does not establish.** It does not establish that the finding is
unexploitable in every configuration of this image: the argument covers the committed
runtime arguments and the files under `/app`, and a different entrypoint or argument
list is outside it. It does not establish that the image is free of any other finding
tomorrow; the database changes daily and a finding published after this assessment
blocks like any other. It verifies no build signature or attestation; `DR-08` still
carries that gap.

## The finding

| Field | Value |
|---|---|
| Identifier | `CVE-2026-84782` |
| Severity | `HIGH` (Ubuntu and Red Hat), CVSS 3.1 `7.4` from Red Hat, `AV:N/AC:H/PR:N/UI:N/S:U/C:H/I:N/A:H` |
| What it is | An out-of-bounds read in OpenSSL's **DTLS** handshake retransmission. A retransmission timer firing while a fragmented handshake write is suspended resends a message from the wrong buffer position, which can disclose heap memory to the peer or crash the process |
| Published | 2026-09-29, OpenSSL security advisory `20260929`, Ubuntu notice `USN-8847-1` |
| Image | `ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384`, built 2026-08-23 |
| Packages | `libssl3t64` and `openssl` |
| Installed | `3.0.13-0ubuntu3.12` |
| Fixed in | `3.0.13-0ubuntu3.16` |

It surfaced on 2026-09-30 in the `dependency and image vulnerability scan` gate of
the default-lane workflow, on a pull request that changes no image, no lockfile and
no script: the database gained the entry the day before, so every branch, `main`
included, fails the same gate from its next run. It was reproduced on this host with
a freshly downloaded database and the same Trivy version, with the same two findings
and nothing else at `HIGH` or `CRITICAL`.

## Why the pin was not moved instead

A patched image exists. Upstream's `server-b11277` build, which the `server` tag
pointed at on 2026-09-30,
`ghcr.io/ggml-org/llama.cpp@sha256:6d607629e3dd5e85f45c43d1494648126cb3f93f2122c9cd53f43242c94cde14`,
was built on 2026-09-30 and scanned with **no** `HIGH` or `CRITICAL` finding. Moving
the pin to it was checked first and judged impractical inside a change whose purpose
is to unblock a gate:

- The digest is the subject of an accepted decision. ADR 0002 selected the runtime at
  this digest and names, as a consequence, a documented refresh procedure the
  repository still does not have.
- Twenty-three evidence records, backing seventeen claims in the claim-evidence
  matrix, record this digest as the runtime they were measured on. Moving the pin
  makes each of them describe an image that is no longer deployed, so each claim
  would need re-measuring on the new image or relabelling.
- The pinned build reports `b10588`; the candidate is `b11277`. What changed in
  roughly seven hundred upstream builds, in flags, metrics names and the API the
  adapter reads, has to be established by running it, and no container engine was
  running on this host.

Rotating the pin is the remediation, and it is left to a change that can write the
refresh procedure and re-measure what rests on the image. The candidate above is
where that change would start.

## Reachability

Method: the image's `linux/amd64` manifest,
`sha256:fa09617a8e077f327dbf823fc1bafecc82c1bff6503a53416d8c2197d86c85ba`, was read
from the registry by the pinned index digest; its layers were extracted; and the
dynamic section and dynamic symbol table of every ELF file under `/app` were read
with `pyelftools`. The package versions were read from the image's own
`/var/lib/dpkg/status`.

| Question | Answer |
|---|---|
| Entrypoint | `/app/llama-server`, as the runtime contract also declares |
| ELF files under `/app` | 29 |
| Files linking `libssl.so.3` | Two: `libllama-common.so.0.2.0` and `libllama-server-impl.so`, which are also the only two linking `libcrypto.so.3`. The executable links neither and loads both through `libllama-server-impl.so`; the 14 CPU back-ends and the other 12 files link neither |
| OpenSSL method functions they import | `TLS_client_method` and `TLS_server_method`, and nothing else ending in `method` |
| DTLS functions they import | None. `libssl.so.3` exports `DTLS_method`, `DTLS_client_method`, `DTLS_server_method` and the `DTLSv1_2_*` variants, so the vulnerable code is present; nothing under `/app` imports any of them |
| A DTLS function looked up by name instead | None. Neither file imports `dlsym`, and neither contains the string `DTLS`; the only case-insensitive match is `get_mbedtls_verify_callback`, a cpp-httplib symbol for a different TLS library |
| Whether the TLS paths run at all | Not in the committed configuration. `TLS_server_method` serves HTTPS only when `--ssl-key-file` and `--ssl-cert-file` are passed, and the committed runtime arguments pass neither; `TLS_client_method` fetches a model over the network, and the committed arguments load a mounted file |

A DTLS connection needs an `SSL_CTX` created from a DTLS method; a context made from
`TLS_client_method` or `TLS_server_method` speaks TLS over a stream and never runs the
DTLS retransmission timer this finding lives in. So the vulnerable code is shipped and
not called.

**What remains.** The image also ships the `openssl` command-line tool, which can
speak DTLS. It is not the entrypoint, and the container runs read-only, as uid
`65534`, with every capability dropped, so reaching it means already running a
command inside the container. The argument is about these bytes: a different image
needs its own reading, which is why the exception is bound to the digest.

## The exception

| Field | Value |
|---|---|
| Identifier | `EX-07` |
| Accepted on | 2026-09-30 |
| Owner | `security`, the evidence owner of both scan controls |
| Compensating control | `pin-image-by-digest`: the bytes the argument was read from are the only bytes the platform names |
| Review deadline | **2026-10-30**, enforced: the ignore entry carries `exp:2026-10-30`, after which Trivy stops suppressing it and the gate blocks again |
| Bound to | the pinned digest above, enforced twice: the image guard refuses to scan when the runtime contract pins any other image while the ignore file accepts a finding, and a test fails in the same case |
| Scope | this one identifier, in the runtime image's ignore file only. The dependency scan has its own file, which accepts nothing |

## How the guard reads it

`scripts/security/lib.sh` now hands each scan its own committed ignore file:
[`runtime-image.trivyignore`](../../../scripts/security/runtime-image.trivyignore) and
[`dependencies.trivyignore`](../../../scripts/security/dependencies.trivyignore). Before
calling Trivy it refuses a missing file, an entry that is anything but one finding
identifier followed by `exp:YYYY-MM-DD`, and, for the image, an ignore file that
accepts a finding while naming an assessed image other than the one pinned. It passes
`--show-suppressed`, so an accepted finding stays in the published scan output.

Observed with Trivy `0.74.0` against the pinned image, with the database above:

| Ignore file | Trivy exit | What it reported |
|---|---|---|
| `CVE-2026-84782 exp:2026-10-30` | `0` | No finding at `HIGH` or `CRITICAL`; both packages listed under `ExperimentalModifiedFindings` as `ignored`, with the ignore file as the source |
| `CVE-2026-84782 exp:2026-09-29`, a date already past | `1` | The finding blocks again |
| Comments only | `1` | The finding blocks |
| The same entry with CRLF line endings | `0` | As the first row |
| A path that does not exist | Fatal error | Trivy stops before scanning, which the guard now refuses first, with its own message |

Run end to end through the committed scripts, from Git Bash, against the real Trivy
and the pinned image:

```text
[inferops-security] scanning ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384 for CRITICAL,HIGH findings
[inferops-security] no CRITICAL,HIGH finding in the pinned runtime image outside the accepted exceptions in scripts/security/runtime-image.trivyignore
[inferops-security] scanning uv.lock (including the test and checks groups) for CRITICAL,HIGH findings
[inferops-security] no CRITICAL,HIGH finding in uv.lock outside the accepted exceptions in scripts/security/dependencies.trivyignore
```

Both exited `0`, and `.artifacts/security/runtime-image-scan.json` lists
`CVE-2026-84782` against `libssl3t64` and `openssl` as `ignored`, sourced from the
runtime ignore file. The success line used to read "no CRITICAL,HIGH finding in the
pinned runtime image", which would now be false; both scripts name the ignore file
instead.

## Environment

| Component | Version |
|---|---|
| Operating system | Microsoft Windows 11 Enterprise, `10.0.26200` |
| Shell | GNU bash `5.2.26`, Git for Windows |
| Python | `3.12.12` |
| `pytest` | `8.4.2` |
| `ruff` | `0.16.4` |
| `mypy` | `2.3.1` |
| Trivy | `0.74.0`, database updated `2026-09-30 07:10:47 UTC` |
| `gitleaks` | `8.30.1` |
| ShellCheck | `0.11.0`, from the `shellcheck-py` wheel |
| `pyelftools` | `0.33`, for the reachability reading only; not a project dependency |

## What changed

| File | Change |
|---|---|
| `scripts/security/lib.sh` | Each guard hands Trivy its own ignore file and `--show-suppressed`; a new `accepted_findings_file` refuses a missing file, a malformed entry, and an image exception assessed against another image |
| `scripts/security/runtime-image.trivyignore` | New: the assessed image and `CVE-2026-84782 exp:2026-10-30` under `# EX-07` |
| `scripts/security/dependencies.trivyignore` | New: accepts nothing |
| `scripts/security/scan-runtime-image.sh`, `scan-dependencies.sh` | The success line names the ignore file instead of claiming no finding |
| `docs/security/security-baseline.v1alpha1.json` | `EX-07`, with a `scanFinding`; both scan controls' `whatItDoesNotVerify` corrected about continuous integration and extended to accepted findings |
| `docs/security/deferred-risks.md` | `EX-07`'s row and section; the count |
| `docs/security/control-matrix.md` | How a scan exception is recorded and read; the correction below |
| `docs/security/security-method.md` and its data | `EX-07` carried as an exception, and the exception mechanism as an implemented item |
| `tests/security/test_vulnerability_scan_exceptions.py` | New, 24 tests |
| `tests/security/test_security_baseline.py` | An exception may carry `scanFinding`; `seven` added to the number words |
| The README, `SECURITY.md`, the architecture index, ADR 0008 | "six" exceptions become "seven" |
| The test inventory and its data, `tests/testing/test_test_inventory.py` | The new module, with no claim and its reason |
| `docs/proof/README.md`, `CHANGELOG.md` | This record, and a `Security` entry |

**A correction, made in place.** The control matrix said the scan guards block on a
finding "with no recorded exception", and both scan controls said a guard refuses
success when a finding "is not recorded as an accepted exception". Neither guard
consulted any exception, so an exception recorded in the baseline would have been
argued and ignored, and the gate would have kept blocking. The ignore files are what
make those sentences true; the matrix says what it said before.

## Mutation check

Each defect was applied to the committed file alone, the new module was run, and the
file was restored byte for byte. Every defect fails at least one test.

| Defect | Failed of 24 |
|---|---|
| The image guard stops passing `--ignorefile` | 2 |
| The image guard stops passing `--show-suppressed` | 1 |
| The image guard stops passing the pinned image to the check | 1 |
| The expiry becomes optional | 1 |
| A carriage return is no longer stripped | 1 |
| A missing ignore file is not checked | 2 |
| A Trivy failure is swallowed | 1 |
| The dependency guard stops passing `--ignorefile` | 1 |
| The ignore entry's expiry moves off the review deadline | 1 |
| The ignore entry sits under another exception's comment | 1 |
| The `assessed-image` line names another digest | 3 |
| The runtime pin moves | 3 |

## What was caught before the first commit

- **The central edit was held back once,** because it stops a scanner blocking on a
  `HIGH` finding. It was made only after a patched image had been looked for first and
  the exception had been authorized for this one finding and this one digest.
- **The count of evidence resting on the image was wrong.** The draft said twenty-four
  evidence entries; that was the number of times the digest appears in the matrix, one
  of them in a statement's prose. It is twenty-three records across seventeen claims.
- **The file count in the reachability table did not add up.** It said "the other 11
  files"; twenty-nine less two, less the executable, less fourteen back-ends is twelve.
- **The register first called `EX-07` the only exception a tool acts on.** The secret
  scanner reads `EX-03`'s allowlist, so that was false. What is unique is that a tool
  enforces `EX-07`'s revisit.
- **The scripts' success lines would have claimed no finding** while one was being
  accepted. Found by reading their output after the real run.
- **The published security method did not carry `EX-07`,** which
  `test_every_accepted_exception_is_carried_in_the_exception_topic` caught in the full
  lane.
- **The inventory's opening sentence still said fifty-two** modules defend no claim
  after the table gained the fifty-third, which
  `test_the_document_counts_the_modules_that_defend_no_claim_correctly` caught in the
  second full lane.

## Validation

Run from Git Bash with `PYTHONDONTWRITEBYTECODE=1`.

| Check | Result |
|---|---|
| `ruff format --check .` | 549 files already formatted |
| `ruff check .` | All checks passed |
| `mypy` | No issues in 294 source files |
| `shellcheck -x -P SCRIPTDIR scripts/security/*.sh` | Clean |
| `pytest tests/security/test_vulnerability_scan_exceptions.py` | 24 passed, none skipped |
| Full default lane, second run | 15,961 passed, 1 failed, 33 skipped, 14 deselected, in 18 min 46 s. The failure was the inventory sentence above |
| `pytest tests/testing/ tests/security/`, after that fix | 7,965 passed |
| `scripts/security/scan-runtime-image.sh`, `scan-dependencies.sh`, real Trivy | Both exit `0`; the accepted finding is in the scan output |
| `python -m tools.evidence_index --gate` | Exit `0`; released pair `1d40b33f…` and `652e9051…`, current pair `08d4868f…` and `b958a724…`, unchanged |
| `gitleaks` `8.30.1` over every changed and new file, with the committed configuration | No leaks found |
| `git diff --check` | Clean |

Not run: `helm lint`, kubeconform, Terraform and TFLint, the package build and the image
build. This change touches no chart, manifest, Terraform, workflow, package or image;
those gates run on the selected service.
