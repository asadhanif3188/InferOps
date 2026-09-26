# V1-S5-013-PR1: closing the five V1 evidence blockers

Date: 2026-09-26

[The completeness check](v1-s5-006-pr2-evidence-completeness.md) left the V1 evidence
pack unfrozen on five release blockers. Each was a certified claim whose statement
rested on a record whose repository code nothing identified. This change closed all
five without rewriting any of those records, using one of three mechanisms per
blocker, each honest in its own way. It records each disposition, and the gate now passes.

The decision is **COMPLETE**. `python -m tools.evidence_index --gate` exits 0.
Four blockers were closed by a **rerun** from a fresh clone of `main` at a named
revision, with nothing uncommitted before the first step or after the last, each
producing a new record that identifies the code that ran. One was closed by a **claim
decision**: the optional `kind` helper's claim moved from certified to not claimed.
No older record was edited, dropped, or given a different level; each stays cited for
what it observed.

**The evidence set this change leaves is the pre-publication freeze candidate, not the
final freeze.** `V1-S5-013-PR2` changes the register to publish the case study, so it
must recompute the evidence-set digest and freeze that one before `V1-S5-008` consumes
it.

The machine-readable form is
[`v1-s5-013-pr1-closure.v1alpha1.json`](v1-s5-013-pr1-closure.v1alpha1.json), the
closure ledger: every register change with its value before and after, how each new
record identifies its code, one disposition per blocker, and the current gate.
[`tests/testing/test_evidence_closure.py`](../../../tests/testing/test_evidence_closure.py)
derives the counts on this page from the ledger, the register, and the index, and fails
if they disagree.

The levels are project-defined, under
[the evidence-level specification](../../testing/evidence-levels.md); they are not an
ISO, NIST, regulatory, or industry certification standard.

## Summary

| | |
|---|---|
| Blockers raised by `V1-S5-006-PR2` | 5 |
| Closed by a rerun | 4 |
| Closed by re-anchoring to evidence that already existed | 0 |
| Closed by a claim decision | 1 |
| Blockers still open | 0 |
| Register changes named in the ledger | 14 |
| Evidence records added | 4 |
| Claim statuses changed | 1 |
| Claim statements changed | 1 |
| Record levels changed | 0 |
| Records edited or removed | 0 |

Recomputed from [the register](../../testing/claim-evidence-matrix.v1alpha2.json) after
this change: **59 claims** — 41 certified, 7 planned, 1 deferred, 10 not claimed — and
**64 evidence records** — 26 at `C0`, 8 at `C1`, 30 at `C2`, none at `C3` or `C4`.
Of the **38 executed records**, **20** name the revision that ran, 4 are content-pinned,
4 run no repository code, and 10 leave their code unidentified. Nine of those ten are
under claims another record now settles, four of them by this change's reruns, and one
is under the claim this change stopped claiming. The four records added are `C2`, the level
their runs support; nothing was promoted.

## The decision, blocker by blocker

| Blocker | Affected claim | Existing record | What was missing | Claim-material repository code | Options | Disposition | Authorisation |
|---|---|---|---|---|---|---|---|
| `b1-local-baseline-code-unidentified` | `a-local-serving-baseline-was-measured-under-a-method-registered-first` | the 2026-09-03 baseline | its named commit is dated after the run, and the tree that ran is unpinned | the API and the real adapter | rerun, or move the status | **`closed-by-rerun`** | real runtime and model on this host; granted |
| `b2-kind-helper-code-unidentified` | `a-local-cluster-is-created-and-removed-without-residue` | the 2026-08-23 cluster smoke | no revision named; the helper is pinned by nothing | the `kind` helper | rerun on `kind`, or move the status | **`closed-by-claim-decision`**: certified → not claimed | a `kind` rerun would need `kind` installed and clusters created; **not granted** |
| `b3-helm-uninstall-survival-clause-code-unidentified` | `a-helm-release-installs-and-uninstalls-without-residue` | the 2026-09-12 scoped cleanup, and the paved-road run | survival of the cluster, node, and storage class rested on the record naming no revision | the chart and the Terraform prerequisites | rerun, or narrow the statement | **`closed-by-rerun`** | Kubernetes mutation on `docker-desktop`; granted |
| `b4-upgrade-rollback-code-unidentified` | `a-controlled-release-change-can-be-reversed-and-real-inference-restored` | the 2026-09-12 upgrade rollback | no revision named; chart and workflow known only by a version label | the chart and the rollback workflow | rerun, or move the status | **`closed-by-rerun`**; statement restated to the rerun's timings | Kubernetes mutation, a deliberate fault, and a real model on `docker-desktop`; granted |
| `b5-pod-replacement-code-unidentified` | `the-model-artifact-survives-a-pod-replacement-on-a-terraform-owned-claim` | the 2026-09-12 pod restart | a branch named, no commit; later recovery runs did not re-prove the artifact's survival | the chart and the Terraform prerequisites | rerun, or move the status | **`closed-by-rerun`** | a deleted pod and a real model on `docker-desktop`; granted |

**Re-anchoring was considered for each and used for none.** For `b5`, the two later
pod-loss runs identify their code, but each says in its own record that it did not
re-prove the artifact's survival, so citing them would have closed the blocker with
evidence that does not support the statement. For `b3`, the paved-road run identifies
its code and supports every clause but survival. The narrowing
`V1-S5-006-PR2` wrote down was available and was not needed once the run was
authorised.

## The reruns

**Authorisation.** The maintainer, who is the host owner the records name, authorised, in the session that ran them, every
rerun this closure needed on the `docker-desktop` provider and none on `kind`: a real
runtime and the pinned model on this host, Terraform prerequisites applied and
destroyed, releases installed, upgraded, rolled back, and uninstalled, one serving pod
deleted, and one deliberate fault injected. No model was downloaded: the verified
artifact already on the host was copied into the clone and its SHA-256 checked against
the pin.

**One revision, named before anything ran.** Every rerun ran from one fresh clone of
the public repository's `main` at `bcad343133ba6fddfe38832a2694e71777cdd006`, the tip
of `main` when this change began. No repository code was changed, so every workflow,
tool, chart, and Terraform file that ran is that revision's. Two pieces of scaffolding
that ran were not repository code: the driver that printed each stage's stamps,
revision, and status, and the script that took `b3`'s cluster readings, which sources
the committed `lib.sh`. Both are committed as evidence in
[the operating scripts](../environment/v1-s5-013-pr1-operating-scripts.txt), redacted
of the clone's, the scratch directory's, and one host tool directory's paths. Before
and after every stage the operating shell printed `git rev-parse HEAD` and `git status --porcelain --untracked-files=all`:
the revision every time, and an empty status every time. Each stage's transcript is
committed beside its record with those lines in it.

| Blocker | Run | Record | Result |
|---|---|---|---|
| `b1` | the registered baseline, `tools.serving_baseline` | [baseline rerun](../serving/v1-s5-013-pr1-baseline-rerun.md) | all five pre-registered thresholds met: 30 of 30 measured requests, model load 221 000 ms against 300 000 ms, P99 3.47 times P50 |
| `b5` | `scripts/environment/kubernetes-pod-restart.sh` | [pod restart rerun](../serving/v1-s5-013-pr1-kubernetes-pod-restart.md) | a different pod against the same claim; byte count, SHA-256, inode, and modification time unchanged; no acquisition Job; a real completion before and after |
| `b4` | `scripts/environment/helm-upgrade-rollback.sh` | [upgrade rollback rerun](../environment/v1-s5-013-pr1-upgrade-rollback.md) | fault detected 6 949 ms after injection, rolled back in 1 986 ms, a real completion 11 053 ms after detection |
| `b3` | `scripts/environment/helm-lifecycle.sh`, then the guarded `terraform destroy` | [scoped cleanup rerun](../environment/v1-s5-013-pr1-scoped-cleanup.md) | no release-labelled object left; namespace and claim intact until Terraform was asked; the cluster, its node, and its storage classes unchanged after the uninstall and after the destroy |

The Kubernetes reruns share
[a preparation transcript](../environment/v1-s5-013-pr1-cluster-prepare-transcript.txt):
the API image and the model seed image built from the clone and imported into the
node, the values merged by `python -m tools.clean_clone values`, and the prerequisites
applied. **So the API image these runs deployed has a known source**, the named
revision, which the earlier Kubernetes records could not say of theirs.

Environment, for all four: one Windows 11 workstation, CPU only; the baseline in a
local container with no cluster; the rest on Docker Desktop's Kubernetes, server
`v1.34.3`, one node, one replica of each tier. `kubectl` `v1.34.3`, Helm
`v3.19.0+g3d8990f`, Terraform `1.15.8`.

## The claim decision

`a-local-cluster-is-created-and-removed-without-residue` moved from `certified` to
`not-claimed`. Its only record, the 2026-08-23 run of the optional `kind` helper,
names no revision of this repository, and nothing else identifies the helper code
that ran. A rerun needs `kind`, which the reference host does not have. ADR 0011 D11
made the helper optional and not the platform path, and ADR 0011 forbids reading
Docker Desktop evidence across to `kind`. The maintainer decided the release would not
install `kind` to re-prove it.

`not-claimed` rather than `planned` or `deferred`, for the reason the register's own
status vocabulary gives: `planned` and `deferred` may cite no evidence, and removing
the 2026-08-23 record would hide what it observed. `not-claimed` may keep it, as
`V1-S5-012-PR2` kept the records under the claim it demoted. The record keeps the `C2`
it was given. The test strategy, whose own vocabulary has no `not-claimed`, now lists
the same claim as `deferred` with the same reason, so no current surface counts it as
certified. This is a release-scope decision driven by evidence quality, not a failed
result: the helper did what its record says, once, on code nothing identifies.

## What else changed, and what did not

- **One statement changed.** The rollback claim quoted the 2026-09-12 run's three
  timings. It now quotes the rerun's, and its limitation names the earlier ones. The
  two runs are not a trend or a spread.
- **Every other statement is unchanged**, because each rerun supports it as written.
- **The rollback claim's boundary** names both runs' probe counts, three and four,
  where it named the first run's alone.
- **Four limitations** now say how their blocker was closed and which run identifies
  the code, and the `kind` claim's says why it is not claimed. The sentence
  `Release blocker since V1-S5-006-PR2` is gone from every claim, and a test holds that
  it may appear only on a blocker still open.
- **Nothing under `docs/proof/` that existed before this change was edited**, except
  the generated dashboard, the generated index and its page, and the proof README,
  whose index of records and release-gate paragraph were updated.

## What this closure found

Three observations, each in the ledger's `findings`:

- **The 2026-09-03 baseline hashed its descriptor from a checkout.** Its records give
  `ea98ce3f…eecdddea`, which is the SHA-256 of the descriptor committed in `d604077`
  with CRLF line endings; the committed content hashes to
  `03ea54d5eb321dacd95637484c6727e95f3c2c2cd52c00e58fe088e9d72a9c7c`, and the file is
  unchanged since. So the rerun used the method the 2026-09-03 run registered. The old
  record is left as written.
- **The API image these reruns deployed names its source.** The completeness check
  recorded that the experiment API image names none; for the three Kubernetes reruns
  it is the named revision.
- **The survival reading stops at an absent namespace.** The script that read the
  cluster, committed as evidence with the operating driver, sources the repository's
  `lib.sh`, which stops a script at a failed
  command, so with the release namespace absent it printed nothing after that lookup.
  The scoped-cleanup record says which lines are missing and why; no statement rests
  on them.

## The gate

```text
$ python -m tools.evidence_index --gate
COMPLETE V1-S5-013: no release blocker; 5 of 5 raised by V1-S5-006 closed; the evidence pack may be frozen
         b1-local-baseline-code-unidentified  closed-by-rerun
         b2-kind-helper-code-unidentified  closed-by-claim-decision
         b3-helm-uninstall-survival-clause-code-unidentified  closed-by-rerun
         b4-upgrade-rollback-code-unidentified  closed-by-rerun
         b5-pod-replacement-code-unidentified  closed-by-rerun
```

Exit status `0`. The gate was not weakened to pass; it was made stricter. It now reads
the closure ledger, and it exits 1 if a blocker stands, if the ledger's stated
decision disagrees with its blockers, or if any blocker the completeness ledger raised
has no disposition, has two, or is disposed of by a mechanism outside the three.

## The freeze candidate

[The V1 evidence index](../v1-evidence-index.md) is the manifest: for each of the 64
records its level, claim, status, what executed and was substituted, the environment,
every immutable identifier, the revision it names and its code identity, and for each
of the **85 cited files** its path, SHA-256, and git blob name.

**Freeze-candidate digest:**
`1d40b33fd79d7b6436c35cfe1fc4ec943a8b82fc77ad1da7cd5d96bb2a5ac23a`, the index's
`evidenceSetSha256`, over the sorted lines `<sha256>  <path>` of every cited file.
A test holds this page to the index's value. `V1-S5-013-PR2` must recompute it after
its own register changes and freeze that value, not this one.

## What was not re-proven

- **None of the historical runs.** Each rerun identifies its own code. None of them
  says what the 2026-08-23, 2026-09-03, or 2026-09-12 runs executed, and each new
  record says so in its own words.
- **The `kind` helper**, on any revision.
- **Anything beyond the five blockers.** No other experiment was run, and the claims
  whose code a content pin identifies were left as `V1-S5-006-PR2` judged them.

## Limitations

- **One host, one provider, one run each.** Every rerun is one execution on one
  Windows workstation; the Kubernetes ones are on `docker-desktop` only.
- **One author.** The reruns and this page were made by the author of this change, an
  AI coding agent, in one session, with an independent review before push; no second
  engineer has repeated them.
- **A revision is the record's word.** Each rerun's revision and empty status are
  printed in its transcript by the operating shell. That is stronger than a record
  written afterwards, and it is still a transcript this change committed.
- **The clone is not transcribed.** It was made before the first transcript begins,
  so no transcript shows the clone or its remote; each shows the revision it held.
- **Some observations are not transcribed.** The baseline's hash comparison before
  its run and its composition's teardown events were read in the operating shell; the
  records say which, and where a later transcript shows the same fact.
- **Host-local digests.** The API and seed images exist on one host and in no
  registry; their digests identify what ran, not something anyone else can fetch.

## What the independent review found

The first commit, `33e4465`, was read before push by two independent reviewers: one
fact-checked every figure, UID, digest, count, and sentence against the transcripts,
the tool-written records, the register, and the index, and one reviewed the gate code
and the tests by mutating the ledgers in memory. Every count and figure they recomputed
matched, and no private value was found. They found these, each corrected in the
second commit:

| Severity | What the first commit said or did | What was true, and the fix |
|---|---|---|
| High | `open_blockers` checked only blocker identifiers, so a disposition naming the wrong claim still produced `COMPLETE`; only a test bound to today's ledger noticed | It now refuses a disposition or an open blocker whose claim is not the one the blocker was raised on, and a blocker listed open that was never raised, and a test drives both mutations |
| High | This page said nothing ran on uncommitted code | The operating driver and the cluster-reading script were not repository code, and `b3`'s survival table is what the reading script printed. Both are now committed as evidence and cited by every rerun record, and the page says which code is the named revision's and which is not |
| Medium | A record read a second time for its code identity silently overrode the first reading, and the closure could re-decide a claim no blocker was raised on; "read once" was a comment | `merged_identities` refuses both, and a test holds that the closure re-decides exactly the blocked claims |
| Medium | `--write` and `--check` crashed with a traceback on a ledger `--gate` rejected cleanly | Every mode now prints the same `MISMATCH` line and exits 1 |
| Medium | The baseline record said the model's hash was checked before the run and its composition cleaned up, citing a transcript that shows neither | It says both were observed in the operating shell and not transcribed, and names the later transcript that verifies the same cached file |
| Medium | The validation record said the cluster was returned to its starting state, and this page that nothing outside the release was touched | Two images stay imported in the node's container store; both pages say so |
| Medium | The scoped-cleanup record said all seven namespaces kept their UIDs | The transcripts show six; the seventh, unrelated work, was compared before redaction, and the record and its register result say so |
| Medium | The rollback claim's boundary still said caller impact was three probes | It names three and four, for the two runs; a fourteenth register change |
| Medium | The index summary kept `BLOCKER: 2` beside a complete gate without saying whose states they are | A field names `V1-S5-006-PR2` as the ledger that decided them |
| Low | The transcript test counted identity blocks without requiring a before and an after | It reads each block's side, requires a first `before` and a last `after`, and refuses a status section that never closes |
| Low | The first commit's message said the node was unchanged by UID | No reading prints a node UID; the node was the same name, Ready, on the same kubelet. The message cannot be edited without rewriting history, so the correction is here |
| Low | This page named the maintainer and the records the host owner as the authoriser; the proof README's edit was undersold; the test inventory still derived the case study's appendix from the completeness ledger alone | Harmonised and corrected |

## How to repeat it

```text
uv run --locked python -m pytest tests/testing/test_evidence_closure.py tests/testing/test_evidence_completeness.py tests/testing/test_evidence_index.py tests/testing/test_evidence_migration.py -q
python -m tools.evidence_index --check
python -m tools.evidence_index --gate
```

The first two read files and the repository's history; the third prints the gate. None
contacts anything else. To repeat a rerun itself, follow the procedure in its record
from a fresh clone at `bcad343133ba6fddfe38832a2694e71777cdd006`, with
[the operating scripts](../environment/v1-s5-013-pr1-operating-scripts.txt), which also
take `b3`'s cluster readings.

## Authorisation

Required: **yes**, for the reruns, and granted by the maintainer in the session that
ran them, for `docker-desktop` and the local runtime and not for `kind`. Writing this
page, the ledger, the tests, and the generated surfaces needed none. No paid service
was used, and Docker Desktop was never reset or reconfigured. Apart from the InferOps
releases and their Terraform prerequisites, which were removed, the only change to the
cluster was the API and model seed images imported into the node's container store,
which stay there, as the image scripts warn.
