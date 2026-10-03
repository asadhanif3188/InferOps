# V2-S3-001-PR2: the Argo CD bootstrap, executed on one provider

Date: 2026-10-03

This page records what the change that implements the Argo CD bootstrap executed,
what it observed, and what that does and does not establish. The decision is
[ADR 0017](../../architecture/decisions/ADR-0017-argocd-bootstrap-and-ownership.md).
The pins and the rules are in
[the Argo CD bootstrap record](../../environment/argocd-bootstrap.md). The procedure
is [`scripts/environment/argocd-bootstrap.sh`](../../../scripts/environment/argocd-bootstrap.sh).

> [!IMPORTANT]
> **One provider.** The procedure installed, verified, and removed Argo CD `v3.5.3`
> on the `docker-desktop` provider, on one host, on one day. It was not executed
> on `kind`. A run on one provider certifies no other provider.
>
> **No Application.** The run created no Application, AppProject, or
> ApplicationSet object. Argo CD reconciled nothing. No release was installed
> during the run, and no inference request was sent.
>
> **No claim moves.** This change adds no record to the evidence pack and registers
> no claim.

## Evidence levels on this page

Three kinds of evidence are on this page. They are not interchangeable.

| Evidence | Level | What executed |
|---|---|---|
| The static suite, `tests/architecture/test_argocd_bootstrap.py` | `C0` | Nothing. It reads the record, the inventory, and the procedure as text |
| The executed suite, `tests/architecture/test_argocd_bootstrap_procedure.py` | `C1` | The committed procedure, with `kubectl`, `kind`, `docker`, and `curl` replaced by recording stubs |
| The run below | `C2` | The committed procedure, with the real tools, on a real cluster of one provider |

The levels are defined in [the evidence levels](../../testing/evidence-levels.md).

## Eligibility, checked before anything was written

- **What it builds on is merged.** `main` was at `a932973`, the merge of pull
  request 117, which added ADR 0017 and the pins.
- **The gate and the pack.** `python -B -m tools.evidence_index --gate` exited 0
  with `FROZEN` for `V1-S5-013-PR2`, `RELEASED v1.0.0` at `718ad2e0…` with the set
  `1d40b33f…` and the pack `652e9051…`, and `CURRENT` with the set `0271ae27…` and
  the pack `222bc533…`. It reported the same five values after the change.
- **The cluster.** The `docker-desktop` cluster existed before the run. This
  change did not create, enable, reset, reconfigure, or delete it.

## The order of the work

ADR 0017 required the security baseline rows before the first install. The order
was:

1. The procedure and its executed suite were written. The executed suite passed
   against stubs.
2. The baseline rows were written: three threats, six controls, two deferred
   risks, and one asset. See [the security baseline](#the-security-baseline).
3. The first install was attempted.

Nothing checks this order. This page states it.

## The environment of the run

| Field | Value |
|---|---|
| Provider | `docker-desktop`, selected with `INFEROPS_PROVIDER=docker-desktop` |
| Cluster | One node, `desktop-control-plane` |
| Server version | `v1.34.3` |
| Container runtime | `containerd://2.2.0` |
| Node image digest | `sha256:08497ee19eace7b4b5348db5c6a1591d7752b164530a36f855cb0f2bdcbadd48` |
| Engine | Docker Engine `29.7.2`, in Docker Desktop on Windows 11 |
| `kubectl` client | `v1.34.3`, placed on `PATH` for the run. The host's default client is two minors from the server, and the target guard refuses it |
| Shell | Git Bash |
| Repository revision | `a932973`, with this change in the working tree and not committed |
| `lib.sh` SHA-256 | `b969003e21605e57bf4714a84cf021286846d8b3c87ac3363442027fd79a46bd`, unchanged by this change |

The run was made from a working tree, so a commit does not identify the bytes
that ran. Each operation therefore printed the SHA-256 of the procedure and of
`lib.sh`. The table under each attempt gives the procedure's digest.

## Attempt 1: the install failed at the download, and changed nothing

Transcript:
[`v2-s3-001-pr2-argocd-bootstrap-run-1-transcript.txt`](v2-s3-001-pr2-argocd-bootstrap-run-1-transcript.txt).
From 15:47:54Z to 15:49:59Z. Procedure SHA-256
`f4f568663855b37debf28b6b5338d115571cc073dcbd5c17250aaa5057bb74a1`.

**Observed.** The three target refusals and the two refusals before any install
behaved as in attempt 2. The install passed the tested-minor check and the
foreign-installation check, started the download, and stopped:

```text
curl: (23) Failure writing output to destination, passed 16384 returned 4294967295
[inferops] FAILED: the manifest could not be downloaded. Nothing was changed. ...
```

Every later step then reported that Argo CD was not installed. `kubectl`, asked
directly before and after, reported no namespace `argocd` and none of the five
cluster-scoped objects.

**Cause.** `lib.sh` turns off Git Bash's automatic path conversion. The procedure
passed the download path to `curl` without converting it. On this host `curl` is
a Windows program, and it could not open the path.

**Correction.** The procedure now converts the path with `inferops::native_path`,
as it already did for `kubectl`. That is the only difference between the two
procedure digests on this page.

**What the executed suite did not catch.** Its `curl` stub is a shell script,
which accepts the unconverted path. The suite passed before the attempt. It
cannot reproduce this defect, and it still cannot.

This attempt is kept because it is a failed run of the procedure. It is not
evidence that the procedure installs anything.

## Attempt 2: install, verify, install again, remove, install, remove

Transcript:
[`v2-s3-001-pr2-argocd-bootstrap-run-2-transcript.txt`](v2-s3-001-pr2-argocd-bootstrap-run-2-transcript.txt).
From 15:52:03Z to 15:57:30Z. Procedure SHA-256
`4c05c4925ed2ac14d877b2d9af5591aa4f1ab50e08a068a86995c24e5ca43fcf`, which is the
SHA-256 of the file as the first commit of this change stores it.

The steps were run by one driver,
[`v2-s3-001-pr2-argocd-bootstrap-run-driver.txt`](v2-s3-001-pr2-argocd-bootstrap-run-driver.txt),
in one pass. Nothing was retried.

| Step | Command | Exit | Observed |
|---:|---|---:|---|
| 0 | `kubectl`, directly | 0 | No namespace `argocd`. None of the five cluster-scoped objects |
| 1 | `install`, no provider | 1 | `no-provider-selected` |
| 2 | `install`, provider `kind`, no cluster name | 1 | `ambiguous-target` |
| 3 | `install`, provider `minikube` | 1 | `unsupported-provider` |
| 4 | `verify` | 1 | "no namespace 'argocd' exists" |
| 5 | `remove --confirm` | 1 | `refusing: foreign-argocd-present` |
| 6 | `install` | 0 | Manifest downloaded, SHA-256 equal to the pin. Namespace created. 34 objects applied. Four workloads rolled out. 5 cluster-scoped and 29 namespaced objects found. Six containers reported the pinned digests |
| 7 | `verify` | 0 | Marker and pin present. 5 and 29 objects. Six containers at the pinned digests. No custom resource |
| 8 | `install`, a second time | 0 | No download: the kept copy had the pinned SHA-256. Namespace not created or relabelled. 34 objects applied. Same checks passed |
| 9 | `verify` | 0 | As step 7 |
| 10 | `remove`, no `--confirm` | 1 | Refused. No call was made |
| 11 | `remove --confirm` | 0 | No custom resource. Four workloads deleted. No pod remained. No custom resource, again. Three definitions, the binding, and the role deleted. Namespace deleted. No residue |
| 12 | `kubectl`, directly | 0 | No namespace `argocd`. None of the five cluster-scoped objects. The namespace list equal to step 0 |
| 13 | `verify` | 1 | "no namespace 'argocd' exists" |
| 14 | `install`, after a removal | 0 | As step 8, and the namespace was created |
| 15 | `verify` | 0 | As step 7 |
| 16 | `remove --confirm` | 0 | As step 11 |
| 17 | `kubectl`, directly | 0 | As step 12 |

The cluster was left as it was found: without Argo CD. The two images stay in the
node's image store, as the record says.

### The image identities the runtime reported

Step 6, and every later check, printed the same six lines:

| Container | Reported identity |
|---|---|
| `argocd-application-controller` | `quay.io/argoproj/argocd@sha256:dd3f47d5a5e4da563a7a398506e892481b358a7cec50abdf320c71aa55904bfa` |
| `argocd-applicationset-controller` | the same |
| `argocd-repo-server` | the same |
| `copyutil`, an init container | the same |
| `secret-init`, an init container | the same |
| `redis` | `public.ecr.aws/docker/library/redis@sha256:08ad0b1d280850169a790dba1393ff7a90aef951fc19632cf4d3ce4f78e679ba` |

Both are the pinned digests. On this runtime the reported identity is the digest
of the multi-platform index, which is what the record pins.

### Objects the manifest does not declare

Step 7 listed the Secrets, Leases, and ConfigMaps in the namespace by name. Three
facts follow:

- `secret/argocd-redis` existed. The record inferred it; it is now observed. Its
  value was not read.
- No Lease existed. The record infers a leader-election Lease of the
  ApplicationSet controller. The run did not observe it, and the record still
  says inferred.
- `configmap/kube-root-ca.crt` existed. Kubernetes creates it in every namespace.

The heading the procedure prints over that list is wrong: it says "Objects the
manifest does not declare", and the list also holds the seven objects of those
kinds that the manifest does declare. The list is correct and the heading is not.

## What the run establishes

For the `docker-desktop` provider, server `v1.34.3`, on 2026-10-03:

- The pinned manifest was served at the pinned URL, and its SHA-256 was the pin.
- Server-side apply with `--force-conflicts` applied all 34 objects, with no
  conflict and no size error. ADR 0017 D8 was proposed until a run did this.
- The four workloads became ready inside the 900-second limit.
- Every container reported the pinned digest of its image at the moment of each
  check. ADR 0017 D6 left the mechanism open; this is the one the change chose.
- A second install on the same installation exited 0 and passed the same checks.
- The removal, in the order ADR 0017 D11 decides, left none of the listed objects,
  twice. An install after a removal succeeded.
- The provider's administrator credential was able to run all of it.

## What the run does not establish

- **Anything about `kind`.** The procedure was not executed there.
- **That Argo CD reconciles an Application.** None exists. ADR 0017 R6 infers that
  a core installation holds no project. The run did not test that.
- **That the removal refuses when an Application exists in a cluster.** Both
  removals ran with none. The refusal is executed against stubs only.
- **That the order avoids a stuck deletion.** No object with a finalizer existed.
- **That a foreign installation is refused in a cluster.** The run met none. The
  refusal is executed against stubs only. The only real refusal of this kind was
  step 5, where no namespace existed.
- **That a container runs the pinned digest after a restart.** No pod was
  restarted, and nothing reads the identity after the check.
- **That a request is served while Argo CD is present, absent, or stopped.** No
  release was installed and no request was sent.
- **That the host can run Argo CD beside a release.** No release was installed.
  No container declares a request or a limit.
- **That the release or the images are authentic.** No signature was verified.
  Neither image was scanned.
- **That a narrower credential can run the bootstrap.**
- **That upstream still serves the bytes.** The download succeeded once, at
  15:52Z on 2026-10-03.
- **How long an install takes on a node that holds neither image.** The run did
  not time the pulls, and attempt 2's later installs found the images present.

## The security baseline

Written before the first install, in
[the baseline data](../../security/security-baseline.v1alpha1.json):

| Kind | Rows |
|---|---|
| Asset | `gitops-controller-installation` |
| Threats | `T-23`, `T-24`, `T-25` |
| Controls enforced on the host | `verify-the-argocd-manifest-digest-before-apply`, `argocd-containers-run-their-pinned-digest-at-install`, `refuse-an-argocd-installation-this-project-did-not-create`, `refuse-argocd-removal-while-a-custom-resource-exists` |
| Control enforced over documents | `no-argocd-custom-resource-is-committed` |
| Control deferred | `narrow-the-argocd-controller-grant` |
| Deferred risks | `DR-13`, `DR-14` |

The baseline now holds forty-four controls, twenty-five threats, and fourteen
deferred risks. ADR 0008 keeps the text `v1.0.0` released, and gains one dated
note with the current count. `tests/security/test_security_maintenance_history.py`
registers that note by its SHA-256.

The four host controls cite this page. What this page supports for each:

| Control | Supported by |
|---|---|
| `verify-the-argocd-manifest-digest-before-apply` | Steps 6, 8, and 14 verified the pin. The refusal of other bytes is executed against stubs |
| `argocd-containers-run-their-pinned-digest-at-install` | Steps 6 to 9, 14, and 15 compared six identities. The refusal of another identity is executed against stubs |
| `refuse-an-argocd-installation-this-project-did-not-create` | Step 5, for an absent namespace. Every other case is executed against stubs |
| `refuse-argocd-removal-while-a-custom-resource-exists` | Steps 11 and 16 ran both checks and found nothing. The refusal is executed against stubs |
| `no-argocd-custom-resource-is-committed` | The static suite |

## What changed

- **[`scripts/environment/argocd-bootstrap.sh`](../../../scripts/environment/argocd-bootstrap.sh)**
  — new. Three operations: `install`, `verify`, and `remove --confirm`. It restates
  the record's pins and names as constants, and a test fails when one differs.
- **`tests/architecture/test_argocd_bootstrap_procedure.py`** — new. It executes the
  procedure against recording stubs.
- **`tests/architecture/test_argocd_bootstrap.py`** — the pins on "not built" moved,
  as they were written to. The suite now reads the procedure as text and holds it
  to the record.
- **`tests/architecture/test_cluster_lifecycle_safety.py`** — the procedure is an
  entry point. The deletion rule gains the four exact shapes the removal uses outside a
  namespace, and accepts the namespace `argocd` as a scope for a named deletion. Two tests hold
  those shapes to this one script and to its readonly constants. Seven samples
  that the rule must refuse were added, and seven that it must accept.
- **`tests/architecture/test_local_cluster_provider_contract.py`** — the procedure
  is classified as a mutating platform workflow, so the rule that the target is
  resolved before the first mutation reads it.
- **[The Argo CD bootstrap record](../../environment/argocd-bootstrap.md)** and its
  data — `implementationState` is `implemented`. The data gains `procedure`,
  `runs`, and `providersNotExecuted`. Six rules move from `not-implemented` to
  `tested`. One rule's statement is corrected: it said that the removal also
  computes the manifest's SHA-256, and the removal reads no manifest, as the
  record's own refusal table already said.
- **[The ownership inventory](../../architecture/resource-ownership.md)** — the
  four bootstrap rows and the upstream-release row move to `implemented` and cite
  this page. No row is added and no owner changes.
- **[ADR 0017](../../architecture/decisions/ADR-0017-argocd-bootstrap-and-ownership.md)**
  — amended in place, with the date, in D3, D5, D6, D8, D11, D12, the
  consequences, the evidence, and three risks. D8, and the mechanism of D6, are
  accepted for `docker-desktop`. The choice of the core profile in D5 stays
  proposed. ADR 0004 gains one sentence.
- **The security baseline** — the rows listed
  [above](#the-security-baseline), in the data, the threat model, the control
  matrix, the deferred-risk register, the security index, the security method,
  `SECURITY.md`, and the README. ADR 0008 gains one registered note.
- **The test inventory, the proof index, the claim and test matrix, the
  architecture pages, and the changelog** — brought in line.

No chart, Terraform file, workflow, or line of `lib.sh` changes. No file under
`src/` changes.

## What the change was asked to reach, and what it reached

| Asked | Reached |
|---|---|
| A repository-supported install, verify, and remove workflow for the selected Argo CD version | Yes. One procedure with three operations |
| The provider and target verification of V1, before any mutation | Yes. One call to `inferops::resolve_target`, before the first read of the cluster. Executed against stubs for four refusals, and on the provider for three |
| Static tests | Yes. See [results](#results) |
| A bounded install, with health and version verification | Yes, on `docker-desktop`. The version is verified as the image digest each container reports. The procedure runs nothing inside a container, so it does not ask the Argo CD binary for its version |
| A scoped removal, and a reinstall or an idempotence check | Yes, on `docker-desktop`: two removals, one second install on a live installation, and one install after a removal |
| The privileges and the ownership, recorded | Yes. The record and the inventory. The operator's lower bound stays inferred |
| A refusal of an ambiguous target | Yes. Step 2, and the executed suite |
| Evidence on one provider certifies no other provider | The record lists `kind` under `providersNotExecuted`, and a test holds that list to the supported providers |

The parent story's acceptance criteria, as far as this change reaches them:

| Criterion | State |
|---|---|
| The Argo CD version and source are pinned, and the bootstrap is reproducible | Reached on `docker-desktop`: three installs from the pinned bytes, with the same result. Not reached on `kind` |
| InferOps consumes an existing cluster that is explicitly selected and verified | Reached. The procedure has no default provider and creates no cluster |
| Terraform, the bootstrap, and Argo CD do not own the same resources | Reached for Terraform, Helm, and the bootstrap, by the inventory and its tests. For Argo CD it holds as an absence: no Application exists |
| Argo CD is not a synchronous request-path dependency | Held by a static test. No run measured a request |
| Cleanup and removal are scoped and documented | Reached on `docker-desktop`, with no Application present |

## Results

Run on the host of the run, from Git Bash, after attempt 2 and before this section
was written. This page changed after the lane ran; no other file did.

| Check | Result |
|---|---|
| `uv run --frozen python -m pytest -q -p no:cacheprovider`, the default lane | 18188 passed, 32 skipped, 14 deselected, in 36 min 17 s. No skip is in either Argo CD suite |
| `tests/architecture/test_argocd_bootstrap.py`, the static suite | 100 passed |
| `tests/architecture/test_argocd_bootstrap_procedure.py`, the executed suite | 65 passed, inside the lane |
| `tests/architecture/test_cluster_lifecycle_safety.py` | 157 passed |
| `tests/architecture/test_local_cluster_provider_contract.py` | 245 passed |
| `tests/architecture/test_resource_ownership.py` | 606 passed |
| `tests/security` | 1036 passed |
| `tests/testing/test_published_methods.py` | 450 passed |
| `tests/testing/test_test_inventory.py` | 1179 passed |
| `uv run --frozen ruff format --check .` | 621 files already formatted |
| `uv run --frozen ruff check .` | All checks passed |
| `uv run --frozen python -m mypy` | No issues in 340 source files |
| `python -B -m tools.evidence_index --gate` | Exit 0, with the five values under [eligibility](#eligibility-checked-before-anything-was-written) |
| `python -m tools.ci_gates expected-failures` | Exit 0 |
| Trailing whitespace and hard tabs in tracked Markdown, as the workflow checks them | None |
| `git diff --cached --check` | Clean |

The counts are of this host on this day. The executed suite is about three and a
half minutes of the lane here.

## What the independent review found

The independent review follows the first commit of this change. The second commit
records what it found here, and what the first commit got wrong.

## Gates that do not apply, and work not executed

- **A run on `kind`.** Not executed. The host has no `kind` CLI.
- **A removal with an Application present.** Not executed. Creating an Application
  is outside this change.
- **A request served with Argo CD present or absent.** Not executed. No release
  was installed.
- **An image scan of the two Argo CD images.** Not executed.
- **`shellcheck`.** It is not a gate of this repository. It was run once over the
  procedure from a container image and reported nothing but the unresolved
  `source` path. That result is not a record.
- **The Helm and Terraform gates.** This change touches no chart and no Terraform
  file.

## Privacy and publicability

- The two transcripts are the output of the driver, with one change: one line of
  each namespace listing named a namespace that is not this project's, and it is
  replaced by a marker. The line count is unchanged.
- The transcripts hold no Secret value. The procedure reads Secret names only.
- The transcripts hold no filesystem path of the host. The procedure prints
  repository-relative paths.
- The downloaded manifest is not committed. It is kept in an ignored directory.

## What this does not establish

The list under [what the run does not establish](#what-the-run-does-not-establish)
applies to this whole page. In addition:

- The executed suite replaces every external tool. It establishes what the
  procedure does with the answers a test gives it, and nothing about a cluster.
- The static suite reads text. It does not establish that a command does what
  its text says.
- No count on this page is a claim about another host.
