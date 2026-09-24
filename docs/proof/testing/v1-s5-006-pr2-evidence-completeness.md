# V1-S5-006-PR2: is the V1 evidence complete enough to freeze

Date: 2026-09-24

This record is the check that stands between
[the normalized, indexed V1 evidence](v1-s5-006-pr1-evidence-normalization.md) and a
frozen evidence pack. It re-read every finding the normalization answered and gave each
one a final state, read how every executed record identifies the repository code that
ran, closed what committed evidence could close, and named what it could not.

The decision is **INCOMPLETE**. Five certified claims rest on evidence whose
repository code nothing identifies. Each is a release blocker below, with the run that
would close it and the decision that could replace the run. Until every one is closed,
the V1 evidence pack is not frozen, and `V1-S5-007` and `V1-S5-008`, which consume the
frozen pack, stay blocked. `python -m tools.evidence_index --gate` prints the same
decision and exits 1 while any blocker stands.

The machine-readable form is
[`v1-s5-006-pr2-completeness.v1alpha1.json`](v1-s5-006-pr2-completeness.v1alpha1.json),
the completeness ledger: the final state of every finding, the code identity of every
executed record and the rule it follows from, the content pins checked against the
repository's history, every register change with its value before and after, the
blockers, and the gate. [`tests/testing/test_evidence_completeness.py`](../../../tests/testing/test_evidence_completeness.py)
derives the counts on this page from the ledger and the index and fails if they
disagree, derives every code identity rather than reading it, and checks every
content pin against the commit that carried it.

**This record is `C0` evidence about the evidence.** It is a reading of committed
files and of the repository's history, plus one run of three committed test suites
in process, recorded separately in
[the pinned suite run](v1-s5-006-pr2-pinned-suite-run.md). No cluster was contacted, no
model was loaded, no runtime was started, and no record under `docs/proof/` was
rewritten. The levels are project-defined; they are not an ISO, NIST, regulatory, or
industry certification standard.

## Summary

| | |
|---|---|
| Findings given a final state | 27 |
| Findings the normalization answered | 21 |
| Findings this verification made | 6 |
| Final state `RESOLVED` | 11 |
| Final state `NARROWED` | 10 |
| Final state `DOWNGRADED` | 0 |
| Final state `HISTORICAL-CORRECTION` | 4 |
| Final state `BLOCKER` | 2 |
| Executed records | 34 |
| Code identity `stated-revision` | 16 |
| Code identity `content-pinned` | 4 |
| Code identity `no-repository-code` | 4 |
| Code identity `unidentified` | 10 |
| Register changes named in the ledger | 12 |
| Evidence records added | 3 |
| Claim statuses changed | 0 |
| Record levels changed | 0 |
| Release blockers | 5 |

Recomputed from [the register](../../testing/claim-evidence-matrix.v1alpha2.json) after
this change: **59 claims** — 42 certified, 7 planned, 1 deferred, 9 not claimed — and
**60 evidence records** — 26 at `C0`, 8 at `C1`, 26 at `C2`, none at `C3` or `C4`.
Nothing was promoted. The three records added are a `C2` and two `C1`, each at the
level the run it cites supports.

## How the verification was done

The normalization gave its 21 findings one of five dispositions. This change re-read
each of them against the cited files and the repository's history, independently of
the normalization's reasoning, and gave each exactly one **final state**:

| Final state | Meaning |
|---|---|
| `RESOLVED` | Committed evidence and citations now support the claim, or the finding was a record-keeping defect that has been corrected and verified |
| `NARROWED` | The statement or its limitation says only what the record supports, and the reduction is published where the claim is |
| `DOWNGRADED` | A status or a level was lowered because the stronger proof is not present. **Used by no finding** |
| `HISTORICAL-CORRECTION` | The record is kept exactly as written, and an additive correction beside it is authoritative for current use |
| `BLOCKER` | Required evidence is unavailable or contradictory, a certified claim depends on it, and the gate stays incomplete until a named run or a decision closes it |

One rule decided the blocker, and it is the rule the story's acceptance sets: **the
evidence must identify the code that ran.** A record that names no revision, or names
one it did not run, supports its statement as a historical observation and cannot bind
it to any code, which is what a frozen pack is for. The rule is applied to the code
that is **claim-material and executed**, because that is what the statement is about;
a tool that only measured is recorded but does not decide a level, and it does not
decide this either.

Three constraints held throughout, the same ones the normalization held: no fact was
inferred from a file a record does not cite; a record under `docs/proof/` was never
edited; and where a gap could be closed by running something, only a run that needed
no authorisation — three committed test suites, in process — was made.

## Every finding and its final state

The migration audit's open items, grouped the way this change checked them. Every audit
finding is in exactly one group, and a test holds that.

| Group | Findings |
|---|---|
| A citation supports less of a statement than it is cited for | `f01`, `f02`, `f03`, `f04` |
| A claim's identifier says more than its statement | `f05` |
| The pod-loss statement said more about intervention than its record | `f06` |
| The baseline statement read as though its fixture was registered first | `f07` |
| A record disagrees with itself on a test count or an exit code | `f08`, `f09` |
| Two records name the model differently | `f10` |
| The pod-restart record names a branch as its revision | `f11` |
| The unready-model record carries two descriptor digests | `f12` |
| Collector results held outside the repository, and no collector image digest | `f13` |
| One clean-clone telemetry sample nobody explained | `f14` |
| Alert-replay inputs not cited, and its capture cadence | `f15` |
| Records coarser than one per execution, and a provider no cited file names | `f16`, `f17` |

| Finding | Disposition in the normalization | Final state | What this verification found |
|---|---|---|---|
| `f01-link-claim-cites-the-shell-check` | corrected metadata | `RESOLVED` | The link claim holds a record of its own for the document-link suite, citing the record that states 204 passed twice |
| `f02-gates-claim-states-a-service-result-no-record-promotes` | narrowed | `NARROWED` | The statement no longer says nine gates passed on the service, and a suite refuses that sentence in any current document |
| `f03-manifest-claim-cites-a-record-that-reads-no-pod` | corrected metadata | `RESOLVED` | The record cites only the validator's own record, which supports the whole statement |
| `f04-helm-claim-cites-only-the-uninstall` | corrected metadata | `RESOLVED` | The install half is cited. The claim is a blocker for a different reason, under `n04` |
| `f05-k8s-identifier-says-more-than-its-statement` | narrowed | `NARROWED` | The limitation says the statement, machine-checked, is what is certified, and names the two radii executed |
| `f06-podloss-statement-says-no-person-intervened` | narrowed | `NARROWED` | The statement says what the record establishes, and no current document says no person intervened |
| `f07-baseline-statement-reads-as-a-registered-fixture` | narrowed | `NARROWED` | The statement says the fixture was rewritten. The claim is a blocker for a different reason, under `n04` |
| `f08-domain-record-disagrees-with-itself-on-a-count` | historical correction | `HISTORICAL-CORRECTION` | The record is unchanged by hash. The pinned run reports a later count at a named revision and does not replace the historical one |
| `f09-troubleshooting-record-says-all-exit-zero` | narrowed | `NARROWED` | The statement excepts the Linux probe branch; the correction states the one exit `5` |
| `f10-closure-and-certification-name-the-model-differently` | historical correction | `HISTORICAL-CORRECTION` | Both names are values of the operator-set identifier for one model revision; the correction is unchanged |
| `f11-pod-restart-names-a-branch-not-a-commit` | narrowed | `BLOCKER` | Nothing identifies the code it ran, and both later recovery runs say in their own records that they did not re-prove the artifact's survival |
| `f12-unready-record-carries-two-descriptor-digests` | corrected metadata | `RESOLVED` | The executed descriptor's digest is the file's LF content at `be0fa9adf623`, checked against the repository's history |
| `f13-collector-per-query-results-are-host-state` | corrected metadata | `NARROWED` | A committed per-query result exists, and the collector is identified by the version and build revision it reported, `3.5.0` at `8be3a9560fbdd18a94dedec4b747c35178177202`. No record observed its image digest, and both records say so |
| `f14-clean-clone-telemetry-sample-is-unexplained` | narrowed | `NARROWED` | A mechanism in committed code accounts for it, unconfirmed, and neither certified statement rests on it; see below |
| `f15-alert-replay-inputs-not-cited` | corrected metadata | `RESOLVED` | All three captures and their records are cited; the statement counts alerts and captures, not held steps |
| `f16-records-are-coarser-than-one-per-execution` | narrowed | `RESOLVED` | Where a distinct run supports part of a claim no cited record does, it is now a record, including the three added here |
| `f17-closure-run-provider-is-unrecorded` | narrowed | `NARROWED` | Still unrecorded, and no statement that cites the record names a provider |
| `n01-baseline-revision-committed-after-the-run` | historical correction | `HISTORICAL-CORRECTION` | Re-checked against the history; the corrections are unchanged. What it means for the claim is under `n04` |
| `n02-manifest-record-pins-another-changes-chart-version` | corrected metadata | `RESOLVED` | The chart version is the one the record's only file gives |
| `n03-alert-validation-introduction-names-two-runs` | historical correction | `HISTORICAL-CORRECTION` | Unchanged by hash; the correction says three captures |
| `n04-executed-records-do-not-name-the-revision-that-ran` | carried as a release blocker | `BLOCKER` | Decided record by record below: 13 of the 18 records no longer leave a claim's code unidentified, and 5 certified claims are blockers |

And the six this verification made:

| Finding | Final state | What was found, and what was done |
|---|---|---|
| `p01-strategy-data-pairs-c3-with-failure` | `RESOLVED` | The failure-and-resilience layer's note in the strategy data said full `C3` failure certification was out of scope — a superseded meaning in a current data file, which the Markdown guard could not see. The note now names no level, and a test reads every current JSON data file for the superseded pairings |
| `p02-content-pinned-records-do-not-cite-their-pins` | `RESOLVED` | Four records' pins were in their run's environment file, which none of them cited. Each now cites it |
| `p03-a-chart-version-is-a-label-not-a-pin` | `NARROWED` | `inferops-llm-0.3.0` is named by twelve records, and ten different trees of the chart in the history carry it. No record is treated as identifying its chart by a version |
| `p04-the-experiment-api-image-names-no-source` | `NARROWED` | The four content-pinned runs deployed an API image pinned by digest in the chart values they hashed; no record says which source built it |
| `p05-current-pages-described-the-freeze-as-undecided` | `RESOLVED` | The index page, the README, and the indexes said the freeze was an open decision; they now state it |
| `p06-a-feasibility-record-quotes-its-test-prompt` | `RESOLVED` | One Sprint 0 record quotes a fixed, project-authored test prompt and the model's reply. Examined, not sensitive, and left as written |

### The unexplained telemetry sample

The clean-clone run's telemetry file has `serving-runtime-scrape-job-absent` returning
one sample and `scrape-target-health-by-job` one row, while both scrape jobs were
discovered and up. The brief for this change allowed three answers: explain it from
committed evidence, show it does not affect a certified claim, or carry it as a
blocker or a narrowing reason. This change does the second, and records a candidate for
the first.

**A mechanism in committed code accounts for both readings.** The verification tool,
`tools/telemetry_collection/verify.py`, polls the collector's targets API every 5 s
until both jobs report a target up, and then asks every query at once. The two
queries that read unexpectedly are recording rules — `inferops:scrape_job_absent:serving_runtime`
and `inferops:scrape_targets_up:sum / inferops:scrape_targets:count` — that the chart
evaluates in the `inferops-collection-health` group every 30 s. A rule evaluation that
ran before the serving-runtime target's first scrape would record the absence as `1`
and count only the API job, which is exactly what the file shows, and nothing would
have replaced it until the next evaluation. **This is consistent with the record and
not confirmed by it:** the file keeps a count per query, not labels, values, or
timestamps, so which evaluation was read cannot be shown.

**Neither certified statement rests on either query.** The collector claim's
discovery and scraping rest on the targets API's own answer — one target discovered
and up for each job — and its evaluation clause on every asked query parsing. The
clean-clone claim's telemetry step rests on the same. Both records keep the sample as a
limitation, and neither says it was explained.

## How each executed record identifies the code that ran

Every one of the 34 executed records is read into exactly one code identity. The test
suite derives each from the register, the revision readings, and the pins, and fails
if the ledger says otherwise.

| Identity | Meaning | Records |
|---|---|---|
| `stated-revision` | The record names the commit that ran | 16 |
| `content-pinned` | The record names a base commit with its change's files uncommitted, and a file of the same run it cites lists the LF-normalised SHA-256 of every file that decided the run, each equal to that path at a named commit | 4 |
| `no-repository-code` | No repository code is among the claim-material components that executed, and each third-party one carries the identifiers its kind requires | 4 |
| `unidentified` | Repository code among the claim-material components executed, and nothing the record cites identifies which | 10 |

**The 18 records the normalization carried here,** one by one:

| Record | What it names | Identity | How its claim is settled |
|---|---|---|---|
| Domain parser, `C2` | a branch point | `unidentified` | A new record: the same suites at a named revision |
| API routes and selection, `C1` | two branch points | `unidentified` | A new record: the same suites at a named revision |
| API metrics and records, `C1` | a base revision | `unidentified` | A new record: the same two suites at a named revision |
| Runtime and model selection, `C2` | nothing | `no-repository-code` | The runtime image digest, model revision, and artifact hash |
| Model hash, feasibility, `C2` | nothing | `unidentified` | The closure record under the same claim names its revision |
| Load generator, stub rehearsal, `C1` | a branch | `unidentified` | The real-load record under the same claim is content-pinned |
| Load generator, real load, `C2` | a base, uncommitted | `content-pinned` | Its own pins |
| Performance matrix, `C2` | a base, uncommitted | `content-pinned` | Its own pins, from the same run |
| Pod loss under load, `C2` | a base, uncommitted | `content-pinned` | Its own pins |
| Unready model, `C2` | a base, uncommitted | `content-pinned` | Its own pins |
| Model lifecycle, six starts, `C2` | a base | `no-repository-code` | The runtime image digest, model revision, and artifact hash |
| Runtime in a cluster, feasibility, `C1` | nothing | `no-repository-code` | Its own pins; the paved-road record under the claim also names its revision |
| Network policy, `C1` | nothing | `no-repository-code` | Under a claim V1 does not make |
| Local serving baseline, `C2` | a commit made after the run | `unidentified` | **Blocker `b1`** |
| kind cluster helper, `C2` | nothing | `unidentified` | **Blocker `b2`** |
| Helm uninstall, scoped cleanup, `C2` | nothing | `unidentified` | **Blocker `b3`** |
| Upgrade rollback, `C2` | nothing | `unidentified` | **Blocker `b4`** |
| Pod replacement, `C2` | a branch | `unidentified` | **Blocker `b5`** |

### The four content pins

Each of these runs wrote, in its environment file, the base revision it started from,
that the change's own files were uncommitted, and the LF-normalised SHA-256 of every
file that decided what it did. Every one of the 34 hashes equals that file's content at
the commit that first carried the run's files; the test re-reads each from the
repository's history, and skips only if the commit is not in the clone.

| Records | Base revision | Files | Each equal to the file at |
|---|---|---|---|
| Real load; performance matrix | `53492c5ddf20f982690dc3e8c4b0c982e7585c48` | 12 | `8e31d494264fffd2afb7f6f961d5a23c73f59daa` |
| Pod loss under load | `7a9ff83d96959671d1d2491d5d09228fe63bf6df` | 12 | `bfdfcc6f28c256bd1e3599f325de0f90f6490e41` |
| Unready model | `0c784d8b3fd939fec1ce0e47f846368e28b08f02` | 10 | `be0fa9adf623af6bbb129fc9eb167df1f18b8dac` |

Read beside the history, the pin reaches further than the hashed files. Each commit
that carried a run's files has that run's base revision as its only parent, and under
`charts/`, `src/`, `infra/`, `scripts/`, `tools/`, and `deploy/` it changes only the
files the run hashed and one package `__init__.py` that re-exports them. So the chart
templates, the Terraform, and the API source those runs used are the base revision's,
on the record's word that no other file was uncommitted — the same word a stated
revision rests on. A test re-reads the parent and the changed paths from the history.
The pin does not cover the API image, which the next section is about.

### What a pin does not reach

- **A chart version is a label.** Twelve records name `inferops-llm-0.3.0`, and the
  repository's history holds ten different trees of the chart that carry it. So no
  record here identifies its chart by version. The four content-pinned runs identify
  theirs by their base revision, as above; the three blocked Kubernetes records have
  nothing else.
- **The experiment API image names no source.** The four content-pinned runs deployed
  `localhost/inferops-api@sha256:9687e1bb11bd2b728bd61fd1338718a6816efa65958b9366cdf536fe8fdfc087`,
  pinned in the chart values they hashed, and the same digest appears in three runs at
  three base revisions. The digest identifies the image that ran, which is what the
  story asks of an image, and the image was published to no registry; which source tree
  built it is recorded nowhere. This is a limitation, not a blocker, and a stricter
  reader would put these four runs under the rule too. The clean-clone run built its own
  image from its clone, at a named revision.
- **A host-local digest cannot be fetched.** The API images above and the model seed
  images are immutable names for bytes that existed on one host. They identify what
  ran; they do not let anyone else run it.

## The release blockers

Each is a certified claim whose statement rests on a record whose repository code
nothing identifies. Each claim's limitation in the register now says so, which is why
[the proof dashboard](../dashboard.md) and [the index](../v1-evidence-index.md) show it.
None was closed by running it: each needs a real model, a Kubernetes cluster, or both,
and none was authorised for this change.

Every rerun below starts the same way and ends the same way, because none of these
workflows records its revision or a clean tree itself:

```text
git rev-parse HEAD && git status --porcelain --untracked-files=all
```

run from a fresh clone, or a detached worktree, at a named commit, before the first
step and after the last, with both outputs in the record.

**`b1-local-baseline-code-unidentified`** —
`a-local-serving-baseline-was-measured-under-a-method-registered-first`. The record names
`d60407741101e3a2516870e40c869c91ab77ce40` as the revision at execution, and the
history dates that commit after the run; the tree that ran was a working tree, and
neither the API and adapter code it measured nor any file that decided the run is
pinned by content. To close it, repeat the baseline:

```text
uv run --locked python -m tools.serving_baseline check
uv run --locked python -m tools.serving_baseline environment
uv run --locked python -m tools.serving_baseline run --confirm-real-runtime
uv run --locked python -m tools.serving_baseline summarize
```

Or decide the claim's status again; no record under it identifies its code, so no
narrower statement is supported.

**`b2-kind-helper-code-unidentified`** —
`a-local-cluster-is-created-and-removed-without-residue`. The node image and the kind
binary are pinned; the helper that created and removed the clusters is repository code,
and nothing identifies it. To close it:

```text
scripts/environment/proof.sh --cycles 2
```

Or decide the claim's status again. The helper has been optional since ADR 0011, and
nothing else exercises it.

**`b3-helm-uninstall-survival-clause-code-unidentified`** —
`a-helm-release-installs-and-uninstalls-without-residue`. The paved-road record names its
revision and supports every clause but one: the survival of the operator's cluster, its
node, and its storage class rests only on the scoped-cleanup record, which names no
revision and identifies the chart by a version label. To close it, install a release
as the paved road does, then:

```text
helm uninstall inferops --namespace inferops-release --wait --timeout 600s
scripts/environment/terraform-prerequisites.sh
```

recording the release-labelled objects left and the Terraform namespace and claim before
Terraform is asked, and afterwards that the API server answers, the node is Ready, and
the default storage class is unchanged. **Or narrow the statement** to what the
paved-road record supports: `helm uninstall` removes every object carrying the release's
instance label and leaves the Terraform-owned namespace and model cache claim intact.

**`b4-upgrade-rollback-code-unidentified`** —
`a-controlled-release-change-can-be-reversed-and-real-inference-restored`. The runtime
image, the node image, and the model are pinned; the chart and the rollback workflow
are identified only by a version label. To close it:

```text
scripts/environment/helm-upgrade-rollback.sh
```

Or decide the claim's status again.

**`b5-pod-replacement-code-unidentified`** —
`the-model-artifact-survives-a-pod-replacement-on-a-terraform-owned-claim`. The record
names a branch and no commit. The two later recovery runs name their revisions, and
each says in its own record that it did not re-prove the artifact's survival — they
support that no acquisition Job appeared and the replacement served, which is a weaker
statement. To close it:

```text
scripts/environment/kubernetes-pod-restart.sh
```

recording the artifact's byte count, SHA-256, inode, and modification time either side
of the replacement. Or decide the claim's status again.

**Why not narrow or downgrade now.** For four of the five, no record under the claim
identifies its code, so there is no narrower true statement to fall back to, and the
status vocabulary has no value for "certified on unpinned code": `planned` may cite no
evidence, and `not-claimed` says V1 does not have the behaviour, which is not what the
records show. Choosing between a rerun and a status decision is the maintainer's, and
each blocker names both. For the Helm claim a narrowing exists and is written above;
applying it is left to the same decision so that the five are decided together.

## Immutability

[The index](../v1-evidence-index.md) is the evidence manifest. For every one of the 60
records it holds the record's level, claim, and status; what executed and was
substituted; the workload source; the environment and provider; every immutable
identifier the record pins, grouped by kind — commit, image digest, model revision,
artifact hash, chart version, package version; the register contract version; the
revision the record names and, now, its code identity. For every one of the **71 cited
files** it holds the path, the SHA-256 of the committed content, and — new here — the
**git blob name**, the object the repository stores for that content. A test checks
every blob name against what git holds for the path, so a release commit can be checked
against the index by `git ls-tree` without trusting a checkout.

The whole set also has one digest, `evidenceSetSha256`, over the sorted lines
`<sha256>  <path>` that `sha256sum -c` reads. The index page gives today's value. A
tag that quotes it pins the evidence set as a whole.

What is not immutable, and is said so where it appears: the two records that name a
branch rather than a commit, the chart version label, and host-local image digests that
identify bytes nobody else can fetch. No certified claim rests on an external URL; every
cited file is committed under `docs/proof/`, which the index suite enforces.

## One current state

Checked mechanically, by the suites named:

- **One register.** Every tool reads `claim-evidence-matrix.v1alpha2.json`; the only
  code that loads `v1alpha1` is the migration's history comparison, and a test keeps it
  out of every other tool.
- **Counts agree.** The index summary, the dashboard, the matrix page, and the README
  are recomputed from the register by their suites; the dashboard's `--check` is clean
  after regeneration.
- **The blockers are visible.** Each blocked claim's limitation carries the blocker, and
  a test finds that sentence on the generated dashboard and the blockers in the index.
- **No stale state.** Current pages no longer describe the freeze as undecided, the
  dashboard as reading `v1alpha1`, or the migration as pending, and suites refuse each of
  those sentences.
- **No superseded meaning in data.** The prose guard reads Markdown for the two
  superseded level names; this change found one of them paired with its level in the
  strategy data, removed it, and added a guard over every current JSON data file.

## History

Every historical record is as it was. The nine records that carry a correction still
match the content hash the normalization stored beside each. No record under
`docs/proof/` that existed before this change was edited except the generated dashboard
and index, the index's own page, and the evidence records index. The three records this change adds
are additive: the older records under the same claims stay cited for what they did, and
the new one says in its own words that it does not recover what the older ones ran.

## Privacy and publicability

Every cited file, the ledgers, the index, and this change's files were scanned for
private keys, cloud and service tokens, bearer headers, assignments of passwords or API
keys, drive-letter and home-directory paths, the private planning repository, the host
account, and prompt or response content. What it found: two documented placeholder
strings shaped like an access key, one test sample path, model file *names* rather than
files, one historical record that names the private planning repository only to say
nothing from it was copied, and the feasibility record's test prompt, finding `p06`. No
model artifact is tracked, and the largest tracked file is a 913 227-byte bill of
materials.

## Judgement calls that could have gone the other way

- **The code-identity rule reads claim-material components.** A reader who holds the
  measuring tool material — the lifecycle command, the feasibility procedure's scripts —
  would add the model-lifecycle and runtime-selection claims to the blockers.
- **A content pin counts as identifying the code.** It is the record's word that the
  hashed files are the ones that decided the run, as a stated revision is its word that
  the tree was clean. A reader who requires a clean commit would add the four
  content-pinned runs to the blockers.
- **The experiment API image is a limitation, not a blocker.** Its digest is immutable
  and is what ran; its source is not recorded.
- **Blockers rather than downgrades.** Every blocked claim keeps its status, because its
  statement is still what its record observed, and deciding between a rerun and a status
  change is the maintainer's. The gate is what stops them being used as frozen.
- **Adding records rather than annotating old ones.** The three claims whose suites
  were re-run each gained a record, because the run is a different execution with its
  own environment and results; the older records stay for what they did.

## Limitations

- One maintainer's reading, with an independent review before push; every quote and
  every count the ledger rests on is checked by a test, and the judgements are not.
- The pinned run says what three suites report at one revision today. It does not say
  the trees the earlier records ran were that revision.
- A content hash and a blob name bind a file to its content. They establish nothing
  about whether the file should have said more.
- The telemetry mechanism is a candidate. Confirming it needs a run that records each
  query's samples and timestamps, or one that waits for a rule evaluation before asking.

## How to repeat it

```text
uv run --locked python -m pytest tests/testing/test_evidence_completeness.py tests/testing/test_evidence_index.py tests/testing/test_evidence_migration.py -q
python -m tools.evidence_index --check
python -m tools.evidence_index --gate
```

The first two read files and the repository's history; the third prints the gate and
exits 1 while any blocker stands. None contacts anything else.

## Authorisation

Not required. This change read committed files and the repository's history, ran three
committed test suites in process in a detached worktree, wrote documents, data, code, and
tests, and contacted nothing outside the repository. No real model, cluster, paid
service, or destructive operation was used, and none of the five reruns above was made.
