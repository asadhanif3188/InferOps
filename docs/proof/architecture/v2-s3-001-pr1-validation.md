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
  — a new decision record, accepted in part. Thirteen decisions: ten accepted,
  most of them as a rule or a pin; two accepted with a part proposed, the manifest
  pin with its choice of profile and the image digests with their mechanism; and
  one, the apply mechanism, proposed. The first commit counted eleven accepted;
  see [the review](#what-the-independent-review-found).
- **[`argocd-bootstrap.v1alpha1.json`](../../environment/argocd-bootstrap.v1alpha1.json)**
  and [its document](../../environment/argocd-bootstrap.md) — the pinned release,
  manifest and images; the namespace; the manifest's 34 objects with the ownership
  row that holds each; the privileges; six refusals; eight removal steps with four
  known gaps; and thirteen rules, each with what enforces it. The first commit had
  five refusals, six steps, and twelve rules.
- **The ownership inventory**, in
  [data](../../architecture/resource-ownership.v1alpha1.json) and in
  [prose](../../architecture/resource-ownership.md) — one owner, `argocd-bootstrap`;
  one lifecycle, `bootstrap`; and six rows. Four rows are cluster objects and are
  `planned`. One is the upstream release, owned by `external-publisher`, and is
  `planned`. One is the committed record, owned by `repository`, and is
  `implemented` in the sense that the record exists and is checked. The inventory
  had 39 rows and has 45. No existing row, owner, lifecycle, or operation changed.
- **`tests/architecture/test_argocd_bootstrap.py`** — the new suite: 62 tests in
  the first commit, 80 after the review fixes below.
- **Documents** — [the system architecture](../../architecture/system-architecture.md),
  with the decided path drawn and marked as not built;
  [the architecture index](../../architecture/README.md) and
  [the decision-authority register](../../governance/decision-authority.md), with
  the seventeenth record; the root README's two counts of decision records; the
  test inventory, with the new module; and the changelog. After the review:
  a dated amendment note in ADR 0004 D3, the boundary review checklist's count of
  suites, one paragraph in the deferred-risk register that points at ADR 0017, and
  one docstring in `tools/ci_gates/ownership_overlap.py`.

No script, chart, Terraform file, workflow, contract, or package source file
changed. The one file under `tools/` changed in a docstring only.

## What was read from upstream

All of it on 2026-10-03, over HTTPS, without credentials. Nothing was written to
any remote.

| Read | From | Result |
|---|---|---|
| The release list | The GitHub API for `argoproj/argo-cd` | `v3.5.3`, published 2026-09-14, was the newest release that was not a pre-release |
| The commit the tag names | The GitHub API, `git/ref/tags/v3.5.3` | `c9c369efcc5b2a0bd720803f8d14a1c3eaddf579`, a commit, not a tag object |
| `manifests/core-install.yaml`, by the tag | `raw.githubusercontent.com` | 1,882,880 bytes, SHA-256 `1a87025d…5c448` |
| The same file, by the commit | `raw.githubusercontent.com` | The same SHA-256 |
| The tested Kubernetes versions page, by the tag and then by the commit | `raw.githubusercontent.com` | Argo CD 3.5: v1.36, v1.35, v1.34, v1.33, in both reads |
| `server/server.go`, `docs/operator-manual/core.md`, and `docs/getting_started.md`, by the commit, after the review | `raw.githubusercontent.com` | The API server creates the `default` project. Upstream's core command is a server-side apply with `--force-conflicts`. Upstream names the ApplicationSet definition as exceeding the annotation limit |
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
| Cleanup is scoped and documented | Reached as a documented rule: eight steps, three refusals that apply to removal, four known gaps, and a list of what removal does not touch. **Pending** as behaviour: no removal procedure exists, and no run tried the order |
| The ownership and architecture documents are amended | Reached |
| The record states that the cluster already exists and is selected and verified before mutation | Reached, in ADR 0017 D3 and in the record's refusals |
| No workload Application is created | Reached, and held by a test |
| No app-of-apps, ApplicationSet object, second cluster, or service mesh | Reached. The upstream manifest installs the ApplicationSet controller, which is recorded as installed and unused |

## Results

| Check | Result |
|---|---|
| `ruff format --check`, `ruff check`, `mypy` | Clean: 618 files formatted, no lint finding, no type error in 339 source files |
| `tests/architecture/test_argocd_bootstrap.py` | 62 passed at the first commit, and 80 after the review's fixes |
| `tools.ci_gates.ownership_overlap` over both committed renders and `infra/terraform` | Exit 0: 32 rendered objects and 2 Terraform resources share no kind and cross no owner. The gate reads Helm's and Terraform's rows only, so the new rows do not change its answer |
| `tools.evidence_index --check` | Exit 0: the index is what the register and ledgers produce |
| `tools.evidence_index --gate` | Exit 0, with the five values above unchanged |
| `tools.proof_dashboard --check` | Exit 0: the dashboard is what the register produces |
| `tools.generated_release --check` | Exit 0: the reference release is what its declared sources derive |
| `tools.experiment_freeze --check` | Exit 0: 2 freeze records, every rule held |
| `terraform fmt -check -recursive infra/terraform` | Exit 0. No Terraform file changed |
| The default lane, `pytest -q -rs`, at the first commit | 17,978 passed, none failed, 35 skipped, 14 deselected, in 22 minutes 4 seconds, with every file of the change staged. The 35 skips are the ones the lane had before this change: host symlink privileges, POSIX signals on Windows, an absent collector image, and fixtures a test does not apply to. The 14 deselected tests are the lanes that need a cluster or a runtime |
| The same gates and the default lane, after the review's fixes | Every gate above gave the same result, and the five evidence values were unchanged. 17,996 passed, none failed, 35 skipped, 14 deselected, in 11 minutes 41 seconds, with every file of the change staged |
| `git diff --check` | Clean |
| Tag `v1.0.0` | Tag object `17c9bbd7…`, commit `718ad2e0…`, as before |
| `gitleaks` | Not run: it is not installed on this host. The hosted CI job runs it over the full history |
| Hosted CI | Not read: the hosted checks of this change's pull request cannot be read from this host |

## What the independent review found

Two independent reviews read the first commit's tree before this record was
finished. Each fetched the upstream files again. Both reproduced every pin, the
object list by kind and name, the cluster role's rules, and the image references.
Neither found private text. Together they found the defects below, and the second
commit corrects them. The first commit is kept as it was.

| Found | What the first commit said | Corrected to |
|---|---|---|
| Removal deleted cluster-scoped objects before it checked ownership | Step 4 deleted "the objects the verified manifest declares, in the namespace argocd", and step 5 checked the marker. Five of those objects are not in a namespace, and the ADR said the marker refusal came "before any deletion" | The marker refusal is step 2. A test orders every removal refusal before the first deletion |
| Removal deleted the definitions while the controllers ran | The manifest lists the definitions first. An Application created between the check and the delete would be deleted with its definition while the controller could still act on its finalizer | The controllers are stopped first, the check is repeated, and the definitions are deleted after. Four gaps that remain are listed with the steps |
| The removal refusal omitted AppProject | `applications-present` named Application and ApplicationSet | `argocd-custom-resources-present` names all three kinds |
| Removal depended on upstream | It refused on a manifest digest mismatch, so a withdrawn manifest would make the installation unremovable by the procedure | Removal deletes by the kinds and names the record lists and needs no download |
| The foreign-installation refusal was narrower than its rule | It read the namespace and the definitions. A cluster role of the same name, a different installed pin, and a hand-deleted namespace were not covered | The refusal also reads the cluster role and binding by name, a new refusal `installed-pin-differs` reads an annotation the bootstrap writes, and the remaining gaps are stated |
| D6 and D5 contradicted each other | D5 was accepted as "applied unmodified". D6 offered a mechanism that rewrites the manifest, and its other mechanism does not hold after a restart, because four containers pull by tag on every start | D6 is a rule for the moment the bootstrap reports success. The ADR states that the rewrite would amend D5, and that the pin does not hold after a restart |
| The choice of the core profile was marked accepted | It depends on runtime behaviour. By inference from upstream source, a core installation holds no project, so it may not reconcile an Application as installed | D5 is accepted as a pin of the bytes, and the choice of profile is proposed. R6 cites the source |
| The namespace boundary had an unstated exception | "Told apart by namespace" covered every namespaced object in `argocd`. An Application or an AppProject would be there too, and the bootstrap does not own it | The boundary excludes `argoproj.io` kinds, and R5 carries the open question |
| The reason for server-side apply named the wrong definition | "the `Application` definition is larger than the annotation" | Upstream names the ApplicationSet definition. The ADR also records the `--force-conflicts` flag upstream pairs with it |
| Two absence rules were labelled `tested` | The machine-readable enforcement did not distinguish a rule held by an absence | A fourth value, `tested-absence`, and the page counts it separately: four tested, two tested only as an absence |
| The absence test read eight directories | A manifest under `docs/`, `tests/`, or a new top-level directory passed. A cluster registration, which is a Secret, could not be matched at all. The limit said "the committed tree" | It reads every tracked file except the suite, and matches the registration label. The limit names what a template can still hide |
| The reference pattern missed the underscore | `argo_cd` and `ARGO_CD_URL` did not match, and `src/` is Python | The pattern matches seven spellings, and a test trips it with each |
| The not-implemented pin read file names in one directory | A procedure under another name, in `lib.sh`, or under `tools/` passed it, while the page said the test forces the record to move | It reads every tracked file under the build directories by path and content. It caught one of this change's own edits, a docstring under `tools/` that named the controller |
| The tested-minor check did not check the minor | It checked that the list was sorted | It checks that the minor both providers last reported is in the list |
| "Not on the request path" read as "cannot affect serving" | D10 said only that a stopped controller does not stop serving | D10, the rule's limit, and the architecture page say that a running controller can change, restart, or delete serving objects, and that its pods share the node |
| The obligation to add security rows was prose only | The ADR said the installing change "must add the rows" | A thirteenth rule, marked not implemented, and a paragraph in the deferred-risk register |
| A field read as an observation | `"appliedUnmodified": true`, when nothing was applied | `mustBeAppliedUnmodified`, with `"applied": false`, and a test pins both |
| The test inventory overstated the suite | It said the index and the ownership document publish "the same pins, identifiers, and counts". The suite checks them for a link only, and checks no count in the ADR's prose | The row says what is checked and that prose counts are not |
| "The first record of a V2 decision" | False: the record that opened V2 is earlier | "The first decision record that decides a V2 design", and the register's heading no longer says "V1 decision" |
| ADR 0004 was amended and not annotated | ADR 0017 said it amends D3, and D3 carried no note | A dated amendment note in D3's row and body |
| Wrong counts and stale sentences | The index paragraph said "four `planned` rows" of six rows, five of them planned. The checklist said "five suites". The sweep was described as selecting in `inferops-` namespaces, and the implemented one runs in one namespace. One run-time object was listed where the same inference gives at least two | Each corrected in place |
| The comparison tables left out facts | The Flux row did not say its controller holds a cluster-wide grant too. The `namespace-install` row did not say that profile adds the API server | Both stated. The ADR also says the comparison was written after the choice |
| A placeholder was staged | The lane row held a token while the lane was still running | Replaced with the lane's result before the first commit |

Two findings were not corrected, and stay as stated limits. A test that compares
the recorded cluster role with itself cannot detect a wrong record, because the
manifest is not committed. And a chart template branch that the committed renders
do not take, or a Terraform `kubernetes_manifest` resource, hides a kind from the
ownership test; the rule's limit now says so.

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
- **That removal leaves no residue**, that its order avoids a stuck deletion, or
  that any of the six refusals refuses.
- **That a container runs the pinned image after a later restart.**
- **That the core profile reconciles an Application.** By inference from upstream
  source, a core installation holds no project.
- **That the reference host has the capacity** to run Argo CD beside a release.
- **Any evidence level above `C0`**, or any change to a claim.
