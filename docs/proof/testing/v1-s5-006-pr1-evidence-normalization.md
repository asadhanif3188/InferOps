# V1-S5-006-PR1: the V1 evidence, normalized and indexed

Date: 2026-09-24

This record is what happened to the claim and evidence register after
[the `V1-S5-012-PR2` migration](v1-s5-012-pr2-migration-report.md). That audit read
every cited record against the current evidence-level definitions and listed, in a
section called *What the audit found and did not fix*, the citations, statements, and
records it questioned and left open. This change answered each of them, answered four
more its own reading found, and built [the V1 evidence index](../v1-evidence-index.md)
over the result.

The machine-readable form is
[`v1-s5-006-pr1-normalization.v1alpha1.json`](v1-s5-006-pr1-normalization.v1alpha1.json),
the normalization ledger: every finding with its one disposition, every register field
this change altered with its value before and after, every record it added whole, every
correction to a historical record with that record's content hash, and a reading of
the repository revision each executed record names.
[`tests/testing/test_evidence_index.py`](../../../tests/testing/test_evidence_index.py)
derives the counts on this page from the ledger and the register and fails if they
disagree, and
[`tests/testing/test_evidence_migration.py`](../../../tests/testing/test_evidence_migration.py)
undoes every change the ledger names before it compares the migration with
`v1alpha1`, so a change the ledger does not name fails there.

**This record is `C0` evidence about the normalization.** It is a reading of committed
files and of the repository's history. No cluster was contacted, no runtime was
started, no model was loaded, and nothing under `docs/proof/` was re-run or rewritten.
The levels are project-defined; they are not an ISO, NIST, regulatory, or industry
certification standard.

## Summary

| | |
|---|---|
| Findings answered | 21 |
| Findings from the migration audit | 17 |
| Findings this normalization made | 4 |
| Register changes named in the ledger | 25 |
| Claims whose register entry changed | 13 |
| Claim statements narrowed | 4 |
| Evidence records added | 3 |
| Evidence records removed | 0 |
| Corrections recorded beside historical records | 9 |
| Historical records rewritten | 0 |
| Claim statuses changed | 0 |
| Record levels changed | 0 |
| Findings carried to `V1-S5-006-PR2` as a release blocker | 1 |

Nothing was promoted. No status moved, no existing record's level moved, and every
added record is at a level its own files support: one `C0`, two `C2`, each passing the
schema and the evidence-level rules. Four statements got narrower; none got wider.

## How the findings were answered

Before anything was edited, every open item in the migration report's *What the audit
found and did not fix*, and the two limitations it left for this change, became one
finding with a verbatim quote of the audit's own sentence. Each was read against the
cited files in full and against the other committed records, and given exactly one of
five dispositions:

| Disposition | Meaning |
|---|---|
| `corrected-authoritative-metadata` | The register's own metadata or citations were wrong or incomplete, and were corrected — including by citing another committed record that supports the part of a claim no cited record did |
| `additive-historical-correction` | A historical record says something its own evidence or the repository's history contradicts; a correction is recorded beside it, and it is left exactly as written |
| `retained-with-narrower-claim-or-limitation` | Kept, with the statement narrowed to what the evidence supports or a limitation that says what it does not |
| `downgraded` | A status or a level lowered because the stronger statement is unsupported. **Used by no finding** |
| `carried-as-release-blocker` | Not closable by reading committed files; carried to `V1-S5-006-PR2`, which decides it before the evidence is frozen |

Three rules held throughout, taken from the change's own boundary:

- **A citation supports the exact part of the claim it is attached to.** Where another
  committed record supplied the missing part, it was cited as a record of its own;
  where none did, the statement was narrowed. Nothing was borrowed from a neighbouring
  record to fill a gap in the one cited.
- **No fact was inferred.** A provider, a revision, a digest, an executed component,
  or a result appears in the register only if a file the record cites states it. The
  closure run's provider stays `unrecorded`; the pod-restart record's revision stays a
  branch name; the collector's digest stays unrecorded although the chart pins one.
- **History is corrected beside itself, never inside itself.** Nine records carry a
  correction, and every one of them is byte-for-byte what it was; the ledger stores
  each record's content hash and a test recomputes it.

## Every finding and its disposition

| Finding | What was found | Disposition | What was done | Register changes and corrections |
|---|---|---|---|---|
| `f01-link-claim-cites-the-shell-check` | The link claim rests on a 2026-08-25 record that ran the contributor shell check rather than the suite the row names. | `corrected-authoritative-metadata` | The named suite did not exist on 2026-08-25; the V1-S5-002-PR2 record ran it by itself on 2026-09-19 and recorded 204 passed twice. That run is now a record of its own under the claim, and the shell-check record is kept for what it did. | `c01-link-suite-record` |
| `f02-gates-claim-states-a-service-result-no-record-promotes` | The eleven-gates claim's "nine have passed on the service" rests on job conclusions read from a public API, which its own record says certify nothing until a run is promoted into a record. | `retained-with-narrower-claim-or-limitation` | The clause was removed from the statement, which now says only what the two records establish. The limitation, which said the two infrastructure gates have never run on the service, is corrected: a committed read of the same API has shown all eleven concluding success since V1-S5-004-PR1, and that file, like the second record, states it certifies nothing. | `c02-gates-statement`, `c02-gates-limitation` |
| `f03-manifest-claim-cites-a-record-that-reads-no-pod` | The manifest-refusal claim cites the paved-road record, which reads no pod against the rules. | `corrected-authoritative-metadata` | The paved-road citation was removed from the record, whose statement the validator's own record supports in full, and the two limitations that described it as the second record cited now say why it is not. | `c03-manifest-citations`, `c03-manifest-record-limitation`, `c03-manifest-claim-limitation` |
| `f04-helm-claim-cites-only-the-uninstall` | The installs-and-uninstalls claim's statement and record cover only the uninstall; the install is in a record the claim does not cite. | `corrected-authoritative-metadata` | The paved-road run, which installed a release, passed its release test, and removed it with no release-labelled object left, is now a second C2 record under the claim, and the limitation says which record carries which half of the identifier. The statement is unchanged. | `c04-helm-install-record`, `c04-helm-claim-limitation` |
| `f05-k8s-identifier-says-more-than-its-statement` | The Kubernetes diagnosis claim is named *published-and-executed*, and its cited records executed two of the four cleanup radii; the statement says *machine-checked*, which is what is supported. | `retained-with-narrower-claim-or-limitation` | The identifier is kept, because it is the claim's identity on every surface that cites it, and the claim's limitation now says that the statement governs and which two radii were executed. | `c05-k8s-identifier-limitation` |
| `f06-podloss-statement-says-no-person-intervened` | The pod-loss statement says no person intervened; the record tabulates no intervention and says that "none" means nothing *in the workflow* intervened, not that nothing outside it did. | `retained-with-narrower-claim-or-limitation` | The statement now says the workflow issued no mutating command between the delete and its closing uninstall, which is what the record establishes. | `c06-podloss-statement` |
| `f07-baseline-statement-reads-as-a-registered-fixture` | The local baseline statement reads as though its fixture was registered before the run; the fixture that ran was rewritten after the registered one was refused, which the claim's limitation, and not its statement, discloses. | `retained-with-narrower-claim-or-limitation` | The statement now names what was registered first -- the warm-up, the measured count, and the five thresholds -- and says the fixture was rewritten after the registered one was refused. The identifier is kept, and the limitation says which part of it is exact. | `c07-baseline-statement`, `c07-baseline-identifier-limitation` |
| `f08-domain-record-disagrees-with-itself-on-a-count` | The domain `v1-s1-001-pr2` record's results line disagrees with its own evidence block on how many tests ran. | `additive-historical-correction` | The register already reports both figures and the disagreement. A correction beside the record says which figure is the tool's output, and the record is unchanged. | `rc01-domain-results-line` |
| `f09-troubleshooting-record-says-all-exit-zero` | The local-runtime troubleshooting record says every diagnostic exited `0` while its own table shows one exiting `5`, and it never ran the Linux branch of the processor-feature probe. | `retained-with-narrower-claim-or-limitation` | The statement said every diagnostic was executed and now excepts the Linux branch of the processor-feature probe. A correction beside the record states the exit code and what it means, and the claim's limitation points to it. | `c09-troubleshooting-statement`, `c09-troubleshooting-exit-limitation`, `rc02-troubleshooting-exit-codes` |
| `f10-closure-and-certification-name-the-model-differently` | The Sprint 1 closure run's response names the model `qwen3-1-7b-instruct` where the certification result names `qwen3-1-7b-q8-0`, and neither record explains the difference. | `additive-historical-correction` | Both names are values of the operator-set platform label INFEROPS_MODEL_IDENTIFIER, which is what the API reports as the model; the second is pinned by committed configuration, and both runs name the same model revision and artifact. A correction beside the closure record quotes the code and configuration, and the Kubernetes record carries a limitation saying so. | `c10-model-name-limitation`, `rc03-closure-model-name` |
| `f11-pod-restart-names-a-branch-not-a-commit` | The pod-restart record names a branch rather than a commit as its revision. | `retained-with-narrower-claim-or-limitation` | The commit that ran is not recorded and is not inferred from the commit that later added the record. The record carries a limitation saying so, and that it names no API image digest; the index reads its revision as a branch name only. What it does pin -- the runtime image, the model revision, and the artifact hash -- is unchanged. | `c11-pod-restart-revision-limitation`, `rc04-pod-restart-revision` |
| `f12-unready-record-carries-two-descriptor-digests` | The unready-model record was regenerated after the run and carries two descriptor digests; the migrated record pins the one that executed. | `corrected-authoritative-metadata` | Verified rather than changed: the descriptor as committed at the run's commit, be0fa9a, hashes to sha256:7220395254fe7da172d438df1252a59b66a376685937c94d5b7834276c4fdb59, the value the register pins as executed, and the record itself says in its own words that it was regenerated from unchanged inputs. | none |
| `f13-collector-per-query-results-are-host-state` | The collector claim's per-query results are in an ignored host directory rather than a committed record, and neither cited file records the collector's image digest. | `corrected-authoritative-metadata` | The clean-clone run's telemetry step committed a per-query outcome on the same provider with both jobs up, and it is now a second C2 record under the claim, carrying the unexplained sample as a limitation. The first record carries a limitation that no cited file records the collector's image digest; the chart's pin is not borrowed as if it were an observation. | `c13-collector-committed-queries-record`, `c13-collector-digest-limitation`, `c13-collector-claim-limitation` |
| `f14-clean-clone-telemetry-sample-is-unexplained` | The clean-clone run's telemetry record returned one sample for a query the correlation suite expects to be empty in a healthy run, while the same record shows both scrape jobs up. | `retained-with-narrower-claim-or-limitation` | Not explained: the committed file keeps counts, not samples, and explaining it needs a run that records what the query returned, which this change was not authorised to make. Both records that cite the file carry it as a limitation, and a correction beside the file says what its verified outcome does and does not check. No claim rests on the absence query reading empty. | `c14-clean-clone-sample-limitation`, `rc07-clean-clone-telemetry-outcome`, `rc08-clean-clone-run-page-telemetry` |
| `f15-alert-replay-inputs-not-cited` | The alert-replay claim cites one of the three experiment records whose captures it replayed, and its captures step at fifteen seconds over a thirty-second scrape. | `corrected-authoritative-metadata` | The record now cites all three experiment records and all three committed capture files the replay tool reads, and carries a limitation that a held count is a count of 15-second steps over a 30-second scrape rather than of independent observations. | `c15-replay-citations`, `c15-replay-cadence-limitation` |
| `f16-records-are-coarser-than-one-per-execution` | Records are as coarse as the `v1alpha1` rows made them. | `retained-with-narrower-claim-or-limitation` | Three records were added where a distinct execution supported a part of a claim no cited record did. No existing record was split: where one record covers several runs, the runs are the same procedure in the same environment, and splitting them would assign each a result its files do not report separately. The index instead lists every file a record cites with its own content hash and the date the file gives for itself, which is per-execution provenance without per-run facts nobody recorded. | none |
| `f17-closure-run-provider-is-unrecorded` | A fact that exists only in a record a claim does not cite was not used, which is why the closure run's provider is `unrecorded` although another record implies it. | `retained-with-narrower-claim-or-limitation` | Kept as unrecorded. The closure record does not name its provider, and borrowing one from a neighbouring record is the inference this normalization may not make. | none |
| `n01-baseline-revision-committed-after-the-run` | Both baseline records give d60407741101e3a2516870e40c869c91ab77ce40 as the revision at execution and say the fixes were in it before the run; the repository's history dates that commit at 2026-09-03T15:03:04Z, after the run's teardown at 14:59:42.090Z. | `additive-historical-correction` | A correction beside each record says what the history shows, the register record carries it as a limitation, and the index reads the revision as committed after the run. | `c07-baseline-revision-limitation`, `rc05-baseline-raw-results-revision`, `rc06-baseline-experiment-revision` |
| `n02-manifest-record-pins-another-changes-chart-version` | The manifest-refusal record pinned chart version inferops-llm-0.3.0, which appears only in the paved-road record; the validator's own record says the chart version moved to 0.2.0 in the change it validates. | `corrected-authoritative-metadata` | The record's chart version is now 0.2.0, the value its own file gives. Found because removing the paved-road citation left the old value in no file the record cites, which the register's suite refuses. | `c03-manifest-versions` |
| `n03-alert-validation-introduction-names-two-runs` | The alert validation record's introduction says the replay runs over the pod-loss and unready-model runs and that no alerting rule existed during either experiment, while its replay section runs over three captures. | `additive-historical-correction` | A correction beside the record says the replay covers three captures. The register already said three, and no figure depends on the wording. | `rc09-alert-validation-two-runs` |
| `n04-executed-records-do-not-name-the-revision-that-ran` | Of the records that executed their target behaviour, the index reads a stated repository revision in some; the others name a base revision, a revision with uncommitted changes, a commit made after the run, a branch, or nothing. | `carried-as-release-blocker` | Not closable by reading: the revision that ran was not recorded, and inferring it would manufacture provenance. For several of these records the code that ran is pinned another way -- a built image by digest, or the LF-normalised hashes of the files that decided the run -- and the index shows which identifiers each record does pin. Whether V1 freezes with these records as they are, with a limitation, or re-runs the ones a published claim depends on is the V1-S5-006-PR2 completeness decision. | none |

## The four statements that were narrowed

A claim's statement is the sentence published as a capability. Each of these said
something its records did not support, and each now says what they do.

**`eleven-default-lane-gates-are-committed-and-mapped-to-the-claims-they-defend`**

> Before: Eleven gates are committed as one workflow and as a matrix that maps each to the claims it defends or to a recorded reason it defends none, compared with the workflow in both directions; nine of them have passed on the selected service.
>
> After: Eleven gates are committed as one workflow and as a matrix that maps each to the claims it defends or to a recorded reason it defends none, compared with the workflow in both directions.

The removed clause said nine gates have passed on the selected service. The only support was job conclusions read from the service's public API, which the cited record itself says certify nothing until a run is promoted into a record, and no run has been. The rest of the statement is what the two records establish.

**`caller-visible-impact-of-losing-the-inference-pod-was-measured-under-load`**

> Before: One serving pod deleted by name mid-load produced a 31,960 ms caller-visible outage in which 40 of 41 dispatched requests were refused with `capability-unavailable`, the replacement reported itself Ready 33,665 ms after the delete, and no person intervened.
>
> After: One serving pod deleted by name mid-load produced a 31,960 ms caller-visible outage in which 40 of 41 dispatched requests were refused with `capability-unavailable`, the replacement reported itself Ready 33,665 ms after the delete, and the workflow issued no mutating command between the delete and its closing uninstall.

The statement said no person intervened. The record establishes that the operating workflow issued no mutating command between the delete and the uninstall, and says in its own words that this does not establish that nothing outside the workflow intervened.

**`a-local-serving-baseline-was-measured-under-a-method-registered-first`**

> Before: A local serving baseline was executed against a fixture, a warm-up, and five thresholds registered before the run, and all thirty measured requests succeeded with every threshold met.
>
> After: A local serving baseline was executed under a warm-up, a measured count, and five thresholds registered before the run, against a fixture rewritten after the registered one was refused, and all thirty measured requests succeeded with every threshold met.

The statement said the fixture was registered before the run. The fixture that ran was rewritten after the registered one was refused on every request of the prior attempt; the thresholds, warm-up, measured count, and procedure were registered first and did not change. The limitation disclosed this; the statement now says it.

**`local-runtime-diagnosis-is-machine-checked-against-the-records-it-quotes`**

> Before: The local runtime troubleshooting guide's symptoms, commands, and quoted figures are checked against the repository and the evidence records they come from, and every diagnostic in it was executed on one host.
>
> After: The local runtime troubleshooting guide's symptoms, commands, and quoted figures are checked against the repository and the evidence records they come from, and every read-only diagnostic in it except the Linux branch of the processor-feature probe was executed on one Windows host.

The statement said every diagnostic was executed. The record's own limitation says the Linux branch of the AVX2 probe has never been run, because no Linux host ran any of it.


Three claim identifiers also say more than their statements —
`kubernetes-diagnosis-and-four-cleanup-radii-are-published-and-executed`,
`a-local-serving-baseline-was-measured-under-a-method-registered-first`, and
`a-helm-release-installs-and-uninstalls-without-residue`. The identifiers were kept, because an identifier is a claim's
identity on every surface that cites it, and renaming one would break those references
without making any of them truer. Each claim's limitation now says which part of its
identifier is exact.

## The three records that were added

| Record | Level | What it supports that no cited record did |
|---|---|---|
| `published-documents-link-only-to-things-that-exist-c0-suite` | `C0` | The link claim's automated test is the document-link suite, which did not exist when the only cited record ran the contributor shell check. The V1-S5-002-PR2 record ran that suite by itself, twice, and recorded 204 passed |
| `a-helm-release-installs-and-uninstalls-without-residue-c2-paved-road` | `C2` | The install the identifier promises. The paved-road run installed a release, passed its release test, and removed it with no release-labelled object left; the scoped-cleanup record, still cited, carries what survived the teardown |
| `a-release-scoped-collector-scrapes-both-inferops-jobs-on-the-reference-provider-c2-clean-clone` | `C2` | A committed per-query result. The first run's was written to an ignored host path; the clean-clone run's telemetry step committed its own, on the same provider, with both jobs up. It also carries the one sample nobody has explained, as a limitation |

**No existing record was split.** The migration left records coarser than one per
execution, and the change's boundary asked for a split where it makes provenance
materially clearer and not where the evidence cannot support one. Where a record
covers several runs, they are the same procedure in the same environment, and their
files do not report results per run that a split could use; splitting would have
invented the facts it was meant to expose. The index gives the per-execution view
another way: every file a record cites is listed with its own content hash and the
date the file gives for itself.

## Corrections beside historical records

| Correction | Record | What the record says | What is true |
|---|---|---|---|
| `rc01-domain-results-line` | [v1-s1-001-pr2-validation.md](../domain/v1-s1-001-pr2-validation.md) | **Results**: 56 tests passing, 18 skipped (structural layer fixtures) | The pytest output in the same record's evidence block reports 49 passed and 18 skipped for tests/domain/test_workload_validation.py. That output is the count to read; no committed file records a run that produced 56. |
| `rc02-troubleshooting-exit-codes` | [v1-s2-008-pr1-validation.md](../serving/v1-s2-008-pr1-validation.md) | Every diagnostic in the table above was run and exited `0`. | One diagnostic exited 5, not 0: local_composition status --confirm-real-runtime, as the record's own table and prose report. Exit 5 is the documented composed-but-not-ready code, and nothing was composed, so 5 was the correct answer. The Linux branch of the processor-feature probe was never run, as the record's own limitations say. |
| `rc03-closure-model-name` | [v1-s1-real-runtime-closure.md](../serving/v1-s1-real-runtime-closure.md) | \| `model` \| `qwen3-1-7b-instruct` \| | The model field an InferOps response carries is the platform identifier the operator configures in INFEROPS_MODEL_IDENTIFIER, not the runtime alias or the artifact's file name. The certification result's qwen3-1-7b-q8-0 is the value committed composition configuration pins; this run's value was set by its operator and is recorded only by the response. Both records name the same model revision. |
| `rc04-pod-restart-revision` | [v1-s3-003-pr2-kubernetes-pod-restart.md](../serving/v1-s3-003-pr2-kubernetes-pod-restart.md) | \| Repository revision \| this change, on `test/v1-s3-011-lifecycle-cleanup-evidence-reconciliation` \| | A branch name is not a revision. The commit that ran is not recorded, and the commit that later added this record is not evidence of it. The record also names no digest for the InferOps API image it built and loaded; the identifiers it does pin are the node image, the runtime image, the chart version, and the model revision and artifact hash. |
| `rc05-baseline-raw-results-revision` | [v1-s2-005-baseline-raw-results.md](../serving/v1-s2-005-baseline-raw-results.md) | All three are fixed on this branch, commit `d604077`, before this run: | The repository's history records commit d60407741101e3a2516870e40c869c91ab77ce40 as created at 2026-09-03T20:03:04+05:00, which is 15:03:04Z, and this record's own span ends at 2026-09-03T14:59:42.090Z. The fixes were in the working tree when the run executed and were committed afterwards. |
| `rc06-baseline-experiment-revision` | [v1-s2-005-local-baseline-experiment.md](../serving/v1-s2-005-local-baseline-experiment.md) | \| Repository revision at execution \| `d60407741101e3a2516870e40c869c91ab77ce40` (branch `fix/v1-s2-005-baseline-tooling-defects`, a descendant of the row above) \| | The commit this row names was created at 2026-09-03T15:03:04Z, after the run's teardown at 14:59:42.090Z, so it is the commit the executed working tree was later recorded as, not a revision that existed when the run executed. |
| `rc07-clean-clone-telemetry-outcome` | [v1-s5-001-pr2-telemetry-verification.json](../environment/v1-s5-001-pr2-telemetry-verification.json) | "outcome": "verified" | verified means every asked query parsed and no query the catalogue marks as reading nothing returned a sample. It does not check absence queries. serving-runtime-scrape-job-absent returned one sample, which the correlation suite expects to be empty on a healthy release, while both scrape jobs were discovered and up, and scrape-target-health-by-job returned one row for two jobs. The file keeps counts rather than samples, so neither can be examined, and neither is explained. |
| `rc08-clean-clone-run-page-telemetry` | [v1-s5-001-pr2-clean-clone-run.md](../environment/v1-s5-001-pr2-clean-clone-run.md) | **Telemetry** -- `verified`: Prometheus `3.5.0` discovered one target for each of the two scrape jobs and both were up | The step's verified outcome does not check absence queries, and one of them, serving-runtime-scrape-job-absent, returned a sample while both jobs were up; see the correction beside the telemetry file. |
| `rc09-alert-validation-two-runs` | [v1-s4-008-pr1-alert-validation.md](../telemetry/v1-s4-008-pr1-alert-validation.md) | no alerting rule existed during either experiment | The replay section of the same record runs the alerts over three captures, v1-s4-004-pr1, v1-s4-006-pr1, and v1-s4-007-pr1, and the introduction names two. No alerting rule existed during any of the three. |

## What the index says about revisions

For every record that executed its target behaviour, the ledger quotes every
repository revision the cited files name and says how it relates to what ran. The
relation is the record's own word, quoted; this change did not re-run a build to check
it.

| The closest revision a record names | Meaning | Executed records |
|---|---|---|
| `stated-revision` | The record names this commit as the revision it ran, without saying the tree carried changes over it. | 13 |
| `stated-revision-with-uncommitted-changes` | The record names this commit and says the change's own files were uncommitted when it ran. | 4 |
| `commit-created-after-the-run` | The record names this commit as what ran, and the repository's history dates it after the run. | 1 |
| `base-revision` | The record names this commit as the base or branch point of the working tree that ran, not as the tree itself. | 4 |
| `branch-name-only` | The record names a branch and no commit. | 2 |
| none | The cited files name no revision of this repository. | 7 |

**13 of the 31 executed records name the revision that ran.** The other 18 are the
finding carried to `V1-S5-006-PR2`. Some of them pin the code another way — a built
image by digest, or the hashes of the files that decided the run — and the index shows
each record's identifiers beside its revision. None of them can be given a revision by
reading: the revision was not recorded, and inferring one is exactly what this change
may not do.

## Current-facing statements corrected

- **[The evidence-record model](../../testing/evidence-record-model.md)** said nothing
  committed derives a claim's strongest level and that the proof dashboard still reads
  `v1alpha1`. The dashboard has read `v1alpha2` and derived levels at render time since
  `V1-S5-012-PR2`; the page says so, and says the index lists them too.
- **[The architecture index](../../architecture/README.md)**, in its ADR 0016 row, said
  nothing is enforced yet and that migrating the register is `V1-S5-012-PR2`'s job. It
  now says the definition is applied to the evidence and which change did what.
- **[The README](../../../README.md)** and
  **[the inference pod recovery page](../../serving/inference-pod-recovery.md)** said no
  person intervened in the pod-loss run; they now say what the record establishes.
- **The suite** refuses those stale sentences returning to a current document, and the
  superseded level meanings stay governed by
  [`tests/testing/test_evidence_levels.py`](../../../tests/testing/test_evidence_levels.py).
  ADR 0016's own present-tense banner is left as accepted, because its dated notes say
  it describes the day it was accepted.

## What `V1-S5-006-PR2` inherits

- **The release blocker:** the 18 executed records that do not name the revision that
  ran. PR2 decides whether V1 freezes with them as they are and a stated limitation, or
  re-runs the ones a published claim depends on. Re-running anything was outside this
  change's authority.
- **Open, not blocking:** the unexplained telemetry sample. It is a limitation of the
  two records that cite it, no claim rests on the absence query reading empty, and
  explaining it needs a run that records what the query returned.
- **The completeness and immutability checks** the index was built to feed: whether the
  identifiers each level requires are present, and whether every hash in the index
  still matches when the evidence is frozen.

## Judgement calls that could have gone the other way

- **Narrowing rather than downgrading.** Every certified claim kept its status, because
  in each case the narrowed statement is fully supported by the records it cites. A
  reviewer who thinks a claim should say the stronger thing or nothing would downgrade
  instead; the ledger holds the old statements so that argument can be had.
- **Adding records rather than editing the existing ones.** The link, Helm, and
  collector claims each gained a record for a separate run rather than an extra citation
  on the old one, because one record has one environment, one procedure, and one set of
  results, and the added runs differ in at least one.
- **Stated revision, taken at the record's word.** A record that names its revision
  without mentioning uncommitted changes is read as naming the tree that ran. One such
  record, the loopback certification, names a branch beside its revision without
  saying whether the branch carried changes over it, and the ledger's note says so.
- **The collector's runtime.** The added collector record lists `llama-server` as
  executed because its serving-runtime job had a target up and the run's own
  environment table, which it cites, names the pinned `llama.cpp` image as the serving
  runtime for the whole run. The telemetry step did not record the image itself; a
  reader who wants a per-step identification would call that component unrecorded.

## What the independent review found

The first commit was reviewed before push by an independent reviewer who read every
changed file and the records it cites, and recomputed the counts. No count was wrong,
and no disposition was disputed. Two defects were found, both in one record this change
added, and both were facts that no file the record cited stated:

- **The collector record's runtime was identified from the chart.** Its note said the
  chart installs a serving runtime only under its real profile — true, and not in any
  file the record cites, while this report's own rules say an executed component
  appears only if a cited file states it. The note now rests on the cited run page's
  environment table, and the judgement call above says what that does and does not
  establish.
- **Its environment note quoted step times from a file it did not cite.** The times
  come from attempt 3's ledger, which the record now cites, and the note quotes them
  exactly as that ledger writes them; the first draft had also truncated them.

Neither was caught by a test, because the suite checked quotes in the ledger and not
the free text of a record's notes. It now does, for every record this change added:
every date, time, digest, and commit identifier in such a record has to appear in a
file the record cites.

This report also said, in the judgement call above, that two stated-revision records
sit beside an unexplained branch name. One does; the sentence was found wrong while
the review's fixes were made, and is corrected.

## Limitations

- This is one maintainer's reading, assisted by independent readers who investigated
  the findings and reported verbatim quotes; every quote the ledger rests on is checked
  by a test, and the judgements are not.
- A content hash binds a file to its content today. It establishes nothing about
  whether the file should have said more, and nothing about files the register does not
  cite.
- The revision reading covers executed records only. A `C0` record's subject is
  committed files, which the content hashes bind; its own branch or base revision was
  not read.
- The index takes a record's date from a line the record writes for itself. A JSON
  result file has none, and some Markdown records have none either; neither case is
  filled in from git.

## How to repeat the counts

```text
uv run --locked python -m pytest tests/testing/test_evidence_index.py tests/testing/test_evidence_migration.py -q
python -m tools.evidence_index --check
```

Both read files and the repository's history, and contact nothing else.

## Authorisation

Not required. This change read committed files and the repository's history, wrote
documents, data, and tests, and contacted nothing outside the repository. No real
model, cluster, paid service, or destructive operation was used.
