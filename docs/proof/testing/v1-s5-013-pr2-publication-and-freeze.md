# V1-S5-013-PR2: publishing the V1 case study and freezing the evidence pack

Date: 2026-09-26

[The blocker closure](v1-s5-013-pr1-blocker-closure.md) closed the five release
blockers and left the evidence as a pre-publication freeze candidate. This change
published [the V1 engineering case study](../../case-study/v1-engineering-case-study.md),
made the register changes publishing it required, wrote corrections beside three dated
records whose narratives say more than their own data, reconciled the current surfaces
that describe the publication or the freeze, and froze the evidence pack.

**The decision: `V1-S5-013` is COMPLETE.** The release gate passes, the evidence pack is
frozen, and the case study is published and linked from the README. `V1-S5-008` may
begin, **only if every other P0 story and release gate also passes**; this change
decides the evidence freeze and nothing else, and it tags, releases, and publishes
nothing outside the repository.

The machine-readable form is
[`v1-s5-013-pr2-publication.v1alpha1.json`](v1-s5-013-pr2-publication.v1alpha1.json),
the publication ledger: every register change with its value before and after, the
corrections, the findings each answers, and the freeze.
[`tests/testing/test_evidence_publication.py`](../../../tests/testing/test_evidence_publication.py)
derives the counts on this page from the ledger, the register, and the index, and fails
if they disagree.

The levels are project-defined, under
[the evidence-level specification](../../testing/evidence-levels.md); they are not an
ISO, NIST, regulatory, or industry certification standard.

## Summary

| | |
|---|---|
| Register changes named in the ledger | 4 |
| Corrections written beside dated records | 4 |
| Findings answered | 7 |
| Claim statuses changed | 0 |
| Claim statements changed | 0 |
| Record levels changed | 0 |
| Evidence records added or removed | 0 |
| Release blockers open | 0 |

Recomputed from [the register](../../testing/claim-evidence-matrix.v1alpha2.json) after
this change: **59 claims** — 41 certified, 7 planned, 1 deferred, 10 not claimed — and
**64 evidence records** — 26 at `C0`, 8 at `C1`, 30 at `C2`, none at `C3` or `C4`. Of
the 38 executed records, 20 name the revision that ran. None of these counts moved:
publication changed wording and surfaces, not what is claimed or at what level.

## What was verified before anything was edited

1. **`V1-S5-013-PR1` is merged.** It is pull request #94, merged into `main` as
   `0e33a60fbd7890b62760ac7c63e1f7a6d05acf23`, the base of this change.
2. **The gate passed at that base.** `python -m tools.evidence_index --gate` printed
   `COMPLETE V1-S5-013` with each of `b1` to `b5` closed, and exited 0.
3. **The candidate's digest and what it covers.** The index's `evidenceSetSha256` was
   `1d40b33fd79d7b6436c35cfe1fc4ec943a8b82fc77ad1da7cd5d96bb2a5ac23a`, SHA-256 over the
   sorted lines `<sha256>  <path>` of the 85 files the records cite, all under
   `docs/proof/`. It covers nothing else: not the register, not a ledger.
4. **Which changes would move it.** None of the ones publishing needs. The
   `V1-S5-007-PR2` validation record said a register edit "moves the evidence-set
   digest", and the closure ledger that this change must recompute it; applying this
   change's four register changes left it exactly where it was. That is finding
   `p-f07-the-evidence-set-digest-does-not-cover-the-register`, and it is why the freeze
   below adds a second digest rather than re-quoting the first.
5. **The items `V1-S5-007-PR2` carried.** Three register or publication items, and
   three dated-record defects, each answered below.
6. **The case study's headline findings.** `V1-S5-013-PR1` narrowed no claim the
   summary cites, and none of the five closed blockers was one of them. The pod-loss
   reading this change narrowed in the register was already stated on the page as
   narrowly as the samples allow.
7. **The public counts that would change.** None of the claim or record counts. Two
   README counts were already stale and are corrected below.

## The register changes

Each is in the ledger with its whole value before and after.

| Change | Field | What changed | Finding |
|---|---|---|---|
| `p01-case-study-published-limitation` | register `limitations` | The limitation that said the case study "has not been written", and that a case-study claim with no row would be caught by nothing, now says what binds the published page to the register and what nothing checks | `p-f01-register-says-the-case-study-is-unwritten` |
| `p02-case-study-is-a-non-claim-surface` | register `nonClaimSurfaces` | The case study added, with its reason: it adds no claim of its own, so no single row could govern it by `readmeRefs` | `p-f02-case-study-entry-point-is-ungoverned` |
| `p03-pod-loss-readiness-boundary` | the pod-loss claim's `doesNotEstablish` | "for the whole outage the deleted pod went on reporting `Ready: True`" became "at every readiness sample before the replacement was observed Ready", with when those samples were taken | `p-f03-pod-loss-readiness-is-broader-than-the-samples` |
| `p04-pod-loss-readiness-result` | the pod-loss record's `results` | The `readiness-disagreement` result narrowed the same way, and names the record's reading of which pod was Ready | `p-f03-pod-loss-readiness-is-broader-than-the-samples` |

The pod-loss claim's statement, status, limitation, and record are otherwise unchanged,
and so is every other claim.

## Corrections beside dated records

A dated record is not edited. Each correction sits in the ledger beside the file,
quotes the sentence it corrects verbatim, gives its basis as verbatim quotes from
committed files, and records the file's SHA-256, which a test holds to the file's
content now and at the base revision. The evidence index lists each against the file it
concerns.

| Correction | Record | What the record says | What its own data shows | Finding |
|---|---|---|---|---|
| `rc10-pod-recovery-scrape-health` | [pod recovery](../serving/v1-s4-006-pr1-inference-pod-recovery.md) | Scrape health and target availability "said the job was up throughout", and the up series "never went to zero for the job" | Both up series of the serving runtime job read `0` at the collector's steps 32.3 s and 47.3 s after the delete, and that job's targets-up ratio read `0` at 47.3 s and 62.3 s, while the API job's stayed `1`; all inside the outage | `p-f04-pod-recovery-scrape-health-contradicts-its-telemetry` |
| `rc11-pod-recovery-readiness-samples` | [pod recovery](../serving/v1-s4-006-pr1-inference-pod-recovery.md) | "For the whole outage, one runtime pod was reporting `Ready: True`" | The samples showing it started 1.4 s to 28.6 s after the delete and their reads had all finished by 30.6 s; the outage began at 31 764 ms, and the next sample is the replacement's | `p-f03-pod-loss-readiness-is-broader-than-the-samples` |
| `rc12-unready-liveness-was-not-asked` | [unready model](../serving/v1-s4-007-pr1-unready-model-recovery.md) | "Liveness did not restart a healthy process", crediting the TCP liveness probe | The runtime's startup probe never succeeded, and until it does Kubernetes asks neither liveness nor readiness; the 600 000 ms startup budget, unchanged by the overlay, is what held | `p-f05-unready-record-credits-a-liveness-probe-that-was-not-asked` |
| `rc13-clean-clone-intervention` | [clean-clone run](../environment/v1-s5-001-pr2-clean-clone-run.md) | "nobody intervened" in its pod-loss step | Its recovery record lists no intervention and says that means nothing in the workflow intervened, not that nothing outside it did | `p-f06-clean-clone-run-says-nobody-intervened` |

Both of the first two readings are re-derived by a test from the committed recovery
record and telemetry, so a correction cannot outlive the data it was read from.

## What this change found

- **`p-f07-the-evidence-set-digest-does-not-cover-the-register`.** The premise that
  publishing moves the evidence-set digest was false for the tooling as written. The
  digest binds the cited files; a freeze quoting it alone would not bind a claim's
  wording, a status, or a ledger's decision. The index now also carries
  `evidencePackSha256`, over the cited files together with the register and every
  ledger of register changes since the migration, and lists those as `packSources`. The evidence-set digest keeps its meaning
  and its value.
- **`p-f03-pod-loss-readiness-is-broader-than-the-samples`, sharpened.**
  `V1-S5-007-PR2` narrowed "for the whole outage" to "at every readiness sample before
  the replacement was observed Ready". Read against the outage again, none of those
  samples falls inside it: each is stamped when its reads start, as
  `scripts/environment/inference-pod-recovery.sh` writes them, and the last one's reads
  had finished by 30.6 s, before the outage began at 31 764 ms; the next, at 33.7 s,
  shows the replacement. So the register now says what the samples show and that the
  run does not establish what either reported between 28.6 s and 33.7 s.
- **Two README counts were stale.** It said nine things were not claimed; since
  `V1-S5-013-PR1` moved the `kind` helper there are ten. It said fourteen decision
  records; there are sixteen. Both are corrected. Neither is checked by a test.

## The case study

Verified against the frozen pack and published. Every governed value was recomputed by
[`tests/testing/test_case_study.py`](../../../tests/testing/test_case_study.py): each
claim it cites is a register row, each appendix cell is what the register and the
ledgers say, every declared figure reads back from its committed file, and every count
it states is recomputed. What changed on the page:

- **Status.** `draft` became `published`, and the paragraph names the gate, the freeze,
  both digests, and the superseded candidate. The data file's `status` is `published`,
  and it records both digests and the freeze under `verifiedAgainst`; a test fails when
  any of them moves, and fails if the page is a draft once the pack is frozen, as it
  failed if the page was published before.
- **Wording that assumed a draft.** "The pack is a freeze candidate" became "The pack is
  frozen"; section 13 no longer lists the freeze as still to come; the appendix is the
  claims "this case study relies on"; and sections 6 and 7 point at the corrections now
  beside the pod-recovery and unready-model records.
- **No figure, finding, or boundary changed.** The summary rows, what the evidence
  demonstrates, and Figures 1 to 3 still read what their records hold; the
  one-provider, one-host, CPU, one-replica boundary stays in the box at the top; cost
  stays method-only.

**The README entry point.** The README links the case study once after its concise
results, as the next thing to read, once in its five-minute reading path, and once in
its entry-point table, which the register governs through `nonClaimSurfaces`. The path
it describes is the README's results, then the case study, then
[the proof dashboard](../dashboard.md), then the records and the decision records. A
test holds the README to linking the page if and only if it is published.

## Current surfaces reconciled

| Surface | What changed |
|---|---|
| [README](../../../README.md) | The case-study link and entry-point row; the evidence index row now states the freeze and the two digests; the matrix row names this change; the two stale counts |
| [Claim and evidence matrix](../../testing/claim-evidence-matrix.md) | The pod-loss paragraph, the case study's limitation and non-claim row, the non-claim count, and a paragraph on this change |
| [Evidence index page](../v1-evidence-index.md) | Four ledgers, the freeze, both digests, the corrected-file count |
| [Proof README](../README.md) | The gate paragraph, the testing and case-study rows |
| [Testing README](../../testing/README.md), [evidence-record model](../../testing/evidence-record-model.md) | The freeze, and that publishing added no field to a record |
| [Test inventory](../../testing/test-inventory.md) | The new module, and the case-study module no longer described as a draft |
| [Unready-model serving page](../../serving/unready-model-recovery.md) | The sentence that tied the TCP liveness probe to the loading socket, narrowed as `rc12` reads it |
| [Proof dashboard](../dashboard.md) | Unchanged: `python -m tools.proof_dashboard --check` passes, because nothing it renders moved |

Two places keep the liveness reading `rc12` corrects and are deliberately not edited:
the unready experiment's values overlay, whose comment is part of a file the dated
record pins by digest, and a check's detail string in the tool that wrote that record.

A test scans the current surfaces for wording that describes the publication or the
freeze as still to come, and is shown to find the sentences it is for. Dated records
under `docs/proof/` and the changelog keep the words they were written with.

## The freeze

Both digests are in the index's summary, produced by `python -m tools.evidence_index`.

| | Evidence set | Evidence pack |
|---|---|---|
| Covers | Every file a record cites | Those files, the register, and the four ledgers |
| Pre-publication candidate, at `0e33a60` | `1d40b33fd79d7b6436c35cfe1fc4ec943a8b82fc77ad1da7cd5d96bb2a5ac23a` | `39415d7ad20ff6f84aaaeabe87e022ebfa44f3639a82aa9bd3bc45eaf5523c1b` |
| **Frozen, by this change** | `1d40b33fd79d7b6436c35cfe1fc4ec943a8b82fc77ad1da7cd5d96bb2a5ac23a` | `652e9051161d38e6dd2e77306a431bf96d863a262cc4b0dab15c0518ba920ad2` |

**The digest a release quotes is the evidence pack's.** The evidence set's did not move,
because publication changed no cited file; the pack's did, because the register changed
and a fourth ledger was added. `V1-S5-013-PR1` named only the set digest; its pack
digest in the table is computed with this change's tooling over the register and the
three ledgers as they stood at the base, and a test recomputes it from the repository's
objects at that commit. That test, and the ones that compare the register and the
corrected records with the base, skip in a clone that does not hold the commit, which
includes the shallow checkout the continuous-integration job makes; they ran in full
on the local clone. The pre-publication candidate is superseded for release use.

The ledger does not state the frozen pack digest, because the ledger is one of the files
it covers. `--gate` prints it from the committed index, after checking that the index is
what the register and the ledgers produce. Neither digest covers the index itself, or a
page that reads the register, such as the README, the dashboard, or the case study.

## The gate

```text
$ python -m tools.evidence_index --gate
COMPLETE V1-S5-013: no release blocker; 5 of 5 raised by V1-S5-006 closed; the evidence pack may be frozen
         b1-local-baseline-code-unidentified  closed-by-rerun
         b2-kind-helper-code-unidentified  closed-by-claim-decision
         b3-helm-uninstall-survival-clause-code-unidentified  closed-by-rerun
         b4-upgrade-rollback-code-unidentified  closed-by-rerun
         b5-pod-replacement-code-unidentified  closed-by-rerun
FROZEN   V1-S5-013-PR2: the committed index is current
         evidence set   1d40b33fd79d7b6436c35cfe1fc4ec943a8b82fc77ad1da7cd5d96bb2a5ac23a
         evidence pack  652e9051161d38e6dd2e77306a431bf96d863a262cc4b0dab15c0518ba920ad2
```

Exit status `0`. The gate was made stricter, not looser: it now also refuses a ledger
that declares a freeze beside an open blocker or with a decision it does not know, and
exits 1 if the committed index is not what the register and the ledgers produce, so a
freeze is never read from a stale digest.

## Closure of the residual conditions

| Item | Final disposition |
|---|---|
| `b1-local-baseline-code-unidentified` | Closed by a rerun at a named revision, in `V1-S5-013-PR1` |
| `b2-kind-helper-code-unidentified` | Closed by a claim decision: the `kind` helper's claim moved to not claimed, in `V1-S5-013-PR1` |
| `b3-helm-uninstall-survival-clause-code-unidentified` | Closed by a rerun at a named revision, in `V1-S5-013-PR1` |
| `b4-upgrade-rollback-code-unidentified` | Closed by a rerun at a named revision, in `V1-S5-013-PR1` |
| `b5-pod-replacement-code-unidentified` | Closed by a rerun at a named revision, in `V1-S5-013-PR1` |
| `V1-S5-006` residual: the evidence could not be frozen while five blockers stood | **Closed.** The blockers were closed by `V1-S5-013-PR1`, and this change freezes the pack. No third `V1-S5-006` change was made |
| `V1-S5-007` residual: the verified case study stayed a draft while the pack was unfrozen | **Closed.** This change publishes it at [`docs/case-study/v1-engineering-case-study.md`](../../case-study/v1-engineering-case-study.md), status `published`, linked from the README. No third `V1-S5-007` change was made |

## What was not done

- **Nothing was executed.** No cluster, runtime, or model was contacted, and no
  experiment was run again; every figure is one already committed.
- **No dated record was edited.** The four corrections sit beside three of them.
- **No release.** Nothing was tagged, released, or published outside the repository,
  and no `V1-S5-008` work was begun.
- **No claim was promoted.** No record reaches `C3` or `C4`; nothing here is a
  capacity, a service-level objective, an availability figure, a cost, or a statement
  about production.

## Limitations

- **A freeze binds files, not readings.** The digests prove that the pack is these
  bytes. Whether a record says what a claim says it says, whether a correction is the
  right reading, and whether the case study's prose says what its records say are
  readings, done by this change and its review.
- **The pack is not the repository.** It covers the cited files, the register, and the
  ledgers. The code that produced the records is identified record by record, as the
  completeness check and the closure established, and not by these digests.
- **One author.** This change was written by the author of the change, an AI coding
  agent, with an independent review before push; no second engineer has repeated it.
- **Every limitation of the evidence stands.** One provider, one Windows host, CPU
  only, one replica, and each experiment run once or twice.

## What the independent review found

The first commit, `b3c4985`, was read before push by two independent reviewers: one
fact-checked every figure, digest, count, and sentence against the records, the raw
telemetry and recovery record, the chart, and the registers at the base and at the
commit, and recomputed both digests and the superseded one from the repository's
objects; the other reviewed the tooling and the tests by mutating the ledgers and pages
in memory and in a shallow clone. Every count, digest, and quote they recomputed
matched, and no private value was found. They found these, each corrected in the second
commit:

| Severity | What the first commit said or did | What was true, and the fix |
|---|---|---|
| Medium | `rc10` said the telemetry shows scrape health "lagging the loss by a scrape or more", and the case study said so in three places | The collector scrapes every 30 s and the file reads it at 15 s steps, each the latest scrape, so a reading after the delete may come from a scrape before it; the file bounds the first zero at 32.3 s and shows no lag of any length. `rc10`, its `stillUnknown`, which called the query step the collector's, and the case study now say only what the readings show |
| Medium | `test_no_status_statement_level_or_record_moved` compared the register with itself with the ledger undone, so a direct edit outside the ledger passed on both sides | It now requires the register with the ledger undone to equal the register committed at the base revision |
| Medium | The base-revision checks skip in a clone without that commit, and the continuous-integration job checks out shallowly, so they skip there; nothing said so | The skip is stated in the validation record and beside the freeze below; the checks ran in full on the local clone |
| Low | The pod-loss boundary said no sample was taken inside the outage "until the replacement's" and so nothing was established "while the outage lasted" | The replacement's sample, at 33.7 s, is inside the outage and establishes what it shows; the boundary is now the seconds between 28.6 s and 33.7 s |
| Low | The evidence index's non-claim reason still said it was built from the normalization ledger alone | Rewritten through `p02` to name the four ledgers |
| Low | The changelog said no record moved, and this page that every current surface was reconciled | One record's result was narrowed, and the changelog says so. The serving page for the unready model still tied the TCP liveness probe to the loading socket and is narrowed; the experiment's values overlay and a check's detail string in the tool that wrote the record keep the reading and are not edited, because the record pins the overlay by digest and the tool is what produced the record |
| Low | The evidence index page said any change to what V1 says about its evidence moves the pack digest | Only a change to the register, a ledger, or a cited file does; the README, the dashboard, and the case study are outside it, and the page, the tool's docstring, and its hashing note now say so |
| Low | The scrape-health and readiness re-derivations checked less than their corrections state, and one could read a missing reading as a zero | Each now asserts the exact zero readings, the API job's steady ratio, and that the sample after the disagreement no longer lists the deleted pod |
| Low | The README check for a link before the architecture accepted one inside an HTML comment or a fence, and a renamed heading made it vacuous | Comments and fences are stripped, and a missing heading fails |
| Low | The stale-wording scan missed seven trivial rewordings | Six patterns added, and six of those rewordings are now sentences a test requires the scan to find; one first-commit sentence of the proof index, "not yet frozen", was reworded |
| Low | The test that the ledger states no digest it is covered by could not fail | Replaced by one that reads every pack source and cited file for the pack digest |
| Low | `--gate` over a `not-frozen` ledger exited 0 and said nothing of the freeze; a ledger without a freeze block raised a traceback; a blocker listed in the publication ledger was ignored | The gate prints `NOT FROZEN`, which a test drives, and `evidence_freeze` refuses the other two, which the gate reports as a `MISMATCH`; a test drives each refusal |
| Low | `pack_sources` read this checkout's files whatever root it was given | It reads each path under the root it is given, and a test changes one ledger under another root |
| Low | `test_evidence_completeness.py` still undid only the closure to reach the register as `V1-S5-006-PR2` left it | It undoes the publication and then the closure |
| Low | The first commit's message says no sample falls inside the outage | The replacement's sample does; the ledger's own wording was qualified. The message cannot be edited without rewriting history, so the correction is here |

## How to repeat it

```text
uv run --locked python -m pytest tests/testing/test_evidence_publication.py tests/testing/test_evidence_closure.py tests/testing/test_evidence_index.py tests/testing/test_case_study.py -q
python -m tools.evidence_index --check
python -m tools.evidence_index --gate
```

Every command reads files and the repository's history. None contacts anything else.

## Authorisation

Required: **no**. This change executed nothing against a host, a cluster, a runtime, or
a model, and used no paid service.
