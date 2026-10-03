# V2-S3-001-PR1 validation

Date: 2026-10-03

What this change checked before it was committed, and how. What it decides is in
[ADR 0017](../../architecture/decisions/ADR-0017-argocd-bootstrap-and-ownership.md),
and what it pins is in
[the Argo CD bootstrap record](../../environment/argocd-bootstrap.md). This page is
about the checks run over the repository after the record, its suite, and the
documents were written.

**The change installed nothing.** No cluster was contacted. No bootstrap procedure
exists, and no Argo CD object is committed. Every check below is static, which is
`C0` under [the evidence levels](../../testing/evidence-levels.md). The change adds
no record to the evidence pack and moves no claim.

The change did read from the network, and only read. That is described under
[what was read from upstream](#what-was-read-from-upstream).

## Eligibility, checked before anything was written

- **What it builds on is merged.** `main` was at `51ac513`, the merge of pull
  request 116.
- **The gate and the pack.** `python -B -m tools.evidence_index --gate` exited 0
  with `FROZEN` for `V1-S5-013-PR2`, `RELEASED v1.0.0` at `718ad2e0…` with the set
  `1d40b33f…` and the pack `652e9051…`, and `CURRENT` with the set `0271ae27…` and
  the pack `222bc533…`. It reported the same five values after the change: no file
  this change touches is cited by a record.
- **The ownership contract it extends.** ADR 0004 and ADR 0011 are accepted, the
  ownership inventory is machine-checked, and both supported providers have an
  identity guard.

## What changed

- **[ADR 0017](../../architecture/decisions/ADR-0017-argocd-bootstrap-and-ownership.md)**
  — a new decision record, accepted in part. Thirteen decisions: eleven accepted,
  most of them as a rule or a pin; one, the image digests, accepted as a rule with
  its mechanism proposed; and one, the apply mechanism, proposed.
- **[`argocd-bootstrap.v1alpha1.json`](../../environment/argocd-bootstrap.v1alpha1.json)**
  and [its document](../../environment/argocd-bootstrap.md) — the pinned release,
  manifest and images; the namespace; the manifest's 34 objects with the ownership
  row that holds each; the privileges; five refusals; the removal steps; and twelve
  rules, each with what enforces it.
- **The ownership inventory**, in
  [data](../../architecture/resource-ownership.v1alpha1.json) and in
  [prose](../../architecture/resource-ownership.md) — one owner, `argocd-bootstrap`;
  one lifecycle, `bootstrap`; and six rows. Four rows are cluster objects and are
  `planned`. One is the upstream release, owned by `external-publisher`, and is
  `planned`. One is the committed record, owned by `repository`, and is
  `implemented` in the sense that the record exists and is checked. The inventory
  had 39 rows and has 45. No existing row, owner, lifecycle, or operation changed.
- **`tests/architecture/test_argocd_bootstrap.py`** — the new suite: 62 tests in
  the first commit.
- **Documents** — [the system architecture](../../architecture/system-architecture.md),
  with the decided path drawn and marked as not built;
  [the architecture index](../../architecture/README.md) and
  [the decision-authority register](../../governance/decision-authority.md), with
  the seventeenth record; the root README's two counts of decision records; the
  test inventory, with the new module; and the changelog.

No script, chart, Terraform file, workflow, contract, or source file changed.

## What was read from upstream

All of it on 2026-10-03, over HTTPS, without credentials. Nothing was written to
any remote.

| Read | From | Result |
|---|---|---|
| The release list | The GitHub API for `argoproj/argo-cd` | `v3.5.3`, published 2026-09-14, was the newest release that was not a pre-release |
| The commit the tag names | The GitHub API, `git/ref/tags/v3.5.3` | `c9c369efcc5b2a0bd720803f8d14a1c3eaddf579`, a commit, not a tag object |
| `manifests/core-install.yaml`, by the tag | `raw.githubusercontent.com` | 1,882,880 bytes, SHA-256 `1a87025d…5c448` |
| The same file, by the commit | `raw.githubusercontent.com` | The same SHA-256 |
| The tested Kubernetes versions page, by the tag | `raw.githubusercontent.com` | Argo CD 3.5: v1.36, v1.35, v1.34, v1.33 |
| The licence file, by the commit | `raw.githubusercontent.com` | Apache License 2.0 |
| The digest of `quay.io/argoproj/argocd:v3.5.3` | The registry's manifest endpoint, a `HEAD` request | `sha256:dd3f47d5…4bfa`, a manifest list |
| The digest of `public.ecr.aws/docker/library/redis:8.2.3-alpine` | The registry's manifest endpoint, a `HEAD` request with an anonymous token | `sha256:08ad0b1d…79ba`, an image index |

The full values are in the record. The manifest was parsed with a YAML reader to
count its objects by kind and to read its roles, image references, and namespace
references. The two other upstream install manifests were downloaded for the
comparison in ADR 0017 D5 and are not pinned.

Three limits on this section:

- **Nothing was authenticated.** No signature, attestation, or provenance
  statement was verified. A digest establishes that later bytes are the same
  bytes.
- **No image was pulled and none was scanned.** Only the digest header was read.
- **The reads are not repeated by any test.** The suite contacts no network. A
  reader who repeats them later may receive a different answer for a tag, and
  should receive the same bytes for the commit.

## What the change was asked to reach, and what it reached

| Asked | Reached |
|---|---|
| The Argo CD version and source are pinned | Reached: the release by tag and commit, the manifest by commit and SHA-256, and the images by digest. A test checks the form of each pin and that they agree |
| The bootstrap is reproducible | **Pending.** No bootstrap procedure exists. The inputs a procedure needs are pinned |
| InferOps consumes an existing, explicitly selected and verified cluster | Reached as a rule: ADR 0017 D3 puts the bootstrap and the removal under ADR 0011. **Pending** as behaviour: nothing calls the guard for a bootstrap |
| Terraform, the bootstrap, and Argo CD do not own the same resources | Reached for Terraform, Helm, and the bootstrap: the inventory and two tests. Reached for Argo CD only as an absence: no Application is committed. The restriction on what an Application may target is **pending** |
| Argo CD is not a synchronous request-path dependency | Reached as a rule and a static check: no file under `src`, `charts`, or `deploy` refers to Argo CD. **Not measured:** no run served a request with Argo CD absent |
| Cleanup is scoped and documented | Reached as a documented rule: six steps, four refusals that apply to removal, and a list of what removal does not touch. **Pending** as behaviour: no removal procedure exists |
| The ownership and architecture documents are amended | Reached |
| The record states that the cluster already exists and is selected and verified before mutation | Reached, in ADR 0017 D3 and in the record's refusals |
| No workload Application is created | Reached, and held by a test |
| No app-of-apps, ApplicationSet object, second cluster, or service mesh | Reached. The upstream manifest installs the ApplicationSet controller, which is recorded as installed and unused |

## Results

| Check | Result |
|---|---|
| `ruff format --check`, `ruff check`, `mypy` | Clean: 618 files formatted, no lint finding, no type error in 339 source files |
| `tests/architecture/test_argocd_bootstrap.py` | 62 passed at the first commit |
| `tools.ci_gates.ownership_overlap` over both committed renders and `infra/terraform` | Exit 0: 32 rendered objects and 2 Terraform resources share no kind and cross no owner. The gate reads Helm's and Terraform's rows only, so the new rows do not change its answer |
| `tools.evidence_index --check` | Exit 0: the index is what the register and ledgers produce |
| `tools.evidence_index --gate` | Exit 0, with the five values above unchanged |
| `tools.proof_dashboard --check` | Exit 0: the dashboard is what the register produces |
| `tools.generated_release --check` | Exit 0: the reference release is what its declared sources derive |
| `tools.experiment_freeze --check` | Exit 0: 2 freeze records, every rule held |
| `terraform fmt -check -recursive infra/terraform` | Exit 0. No Terraform file changed |
| The default lane, `pytest -q -rs`, at the first commit | 17,978 passed, none failed, 35 skipped, 14 deselected, in 22 minutes 4 seconds, with every file of the change staged. The 35 skips are the ones the lane had before this change: host symlink privileges, POSIX signals on Windows, an absent collector image, and fixtures a test does not apply to. The 14 deselected tests are the lanes that need a cluster or a runtime |
| `git diff --check` | Clean |
| Tag `v1.0.0` | Tag object `17c9bbd7…`, commit `718ad2e0…`, as before |
| `gitleaks` | Not run: it is not installed on this host. The hosted CI job runs it over the full history |
| Hosted CI | Not read: the hosted checks of this change's pull request cannot be read from this host |

## Gates that do not apply, and work not executed

- **Helm render and Kubernetes schema.** Not applicable: this change touches no
  file under `charts/` or `deploy/`.
- **Terraform validate and lint.** Not applicable: this change touches no file
  under `infra/`. `tflint` is not installed on this host.
- **An Argo CD static check.** Not applicable: the repository holds no Argo CD
  manifest, Application, or project. The pinned manifest is upstream's and is not
  committed.
- **A cluster run.** Not executed, and not asked of this change: no bootstrap,
  no apply, no removal. Both supported providers were left untouched.
- **An image scan of the two pinned images.** Not executed. The image guard in
  this repository scans the serving runtime image only.

## Privacy and publicability

The diff was read for private planning text, local paths, credentials, account
identifiers, and story identifiers that are not merged. Files are named by
repository path. Every external URL is a public upstream address. The one story
identifier that is not merged is this change's own.

## What this does not establish

- **That Argo CD is installed, runs, or reconciles anything.**
- **That the pinned manifest applies** to either supported provider's cluster, or
  that server-side apply is the mechanism that applies it.
- **That the pinned bytes are authentic**, or that upstream still serves them.
- **That a pinned image is free of known vulnerabilities.**
- **That Argo CD reconciles nothing another owner holds, once an Application
  exists.** Today no Application exists. The upstream controller holds every verb
  on every resource.
- **That a request is served while Argo CD is absent or stopped.**
- **That removal leaves no residue**, or that any of the five refusals refuses.
- **That the reference host has the capacity** to run Argo CD beside a release.
- **Any evidence level above `C0`**, or any change to a claim.
