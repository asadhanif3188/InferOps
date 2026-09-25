# V1-S5-007-PR2 — verification of the V1 engineering case study, kept a draft

Date: 2026-09-25

Change: [the V1 engineering case study](../../case-study/v1-engineering-case-study.md)
verified sentence by sentence against the evidence set as it stands, led with a
results-first summary, given three figures, and corrected where it, the README, and the
operator runbook said more than their records; with
[its data file](../../case-study/v1-engineering-case-study.v1alpha1.json) and
[`tests/testing/test_case_study.py`](../../../tests/testing/test_case_study.py) extended
to hold the new material.

This record describes a documentation change. Nothing it describes was executed for it:
no cluster was contacted, no model was loaded, no runtime was started, and no record
under `docs/proof/` other than this one was written or changed. Every figure the page
quotes was already committed. The page certifies nothing, and no claim's status and no
record's level moved.

## Why it is still a draft

This change was to publish the case study against a frozen evidence pack. The pack is
not frozen. On this branch, before any edit:

```text
$ uv run --locked python -m tools.evidence_index --gate
INCOMPLETE V1-S5-006: 5 release blockers
         b1-local-baseline-code-unidentified  a-local-serving-baseline-was-measured-under-a-method-registered-first
         b2-kind-helper-code-unidentified  a-local-cluster-is-created-and-removed-without-residue
         b3-helm-uninstall-survival-clause-code-unidentified  a-helm-release-installs-and-uninstalls-without-residue
         b4-upgrade-rollback-code-unidentified  a-controlled-release-change-can-be-reversed-and-real-inference-restored
         b5-pod-replacement-code-unidentified  the-model-artifact-survives-a-pod-replacement-on-a-terraform-owned-claim
exit=1
```

[The completeness ledger](../testing/v1-s5-006-pr2-completeness.v1alpha1.json) still
lists `V1-S5-007` in `consumersBlocked`. Nothing merged between `V1-S5-007-PR1` and this
change except `V1-S5-007-PR1` itself, so no blocker was closed and no status decision
was taken. Each blocker still needs a re-run from a fresh clone at a named commit,
recording `git rev-parse HEAD` and an empty `git status`, or a maintainer's status
decision; neither is this change's to make.

So the page keeps `Status: **draft**`, the README does not link to it, and
`tests/testing/test_case_study.py` still refuses any other status while the gate is
incomplete. What this change could do without the freeze, it did: verify the page
against the evidence set that exists, and fix the page so that publishing, once the
gate is complete, is a status change and a README link rather than a rewrite.

## The facts established before editing

1. **Freeze state.** Not frozen. The index's `evidenceSetSha256` is
   `1bf2a83ff0548a7d07e68fabdacd0d8b10c35d012b25c03b40bc469297fb5bec`, its release
   gate `incomplete`, and its blocker count 5. The page now names that digest, the data
   file records all three under `verifiedAgainst`, and a test fails when the index
   moves from any of them.
2. **Statements whose support changed since the draft.** None because of a blocker: no
   blocker was resolved. The changes below come from reading the records again, not
   from new evidence.
3. **The strongest findings still supported.** The declared-load result, the pod loss,
   the unready model, the clean-clone run, and the cost method's reading of measured
   use. Their claims are all certified and none is a release blocker.
4. **The limitation that travels with each.** In the summary's last column, and in the
   caption of each figure.
5. **Machine-checked figures and review-checked prose.** In the prose, every number
   written in digits beside a unit of time, a percentage, or a unit of memory; in the
   bodies of the two text figures, every numeral and every count written as a word,
   bar three HTTP statuses. Everything else is review-checked, and the page says which.
6. **README wording broader than the evidence.** Six places: "nobody intervened" in
   the pod-loss row of what V1 proves; "throughout" twice for the deleted pod's
   readiness; and "Executed once" for the performance scenarios, the pod recovery, and
   the unready model, each of which was executed more than once. All six are narrowed
   below; the last three were found by the independent review.
7. **Surfaces that must link to the case study once it is published.** The README,
   which must govern the link by a register row's `readmeRefs` or list it as a surface
   that claims nothing, and [the proof index](../README.md), which already indexes its
   validation records. Neither link is added while the page is a draft.

## What changed

| File | Change |
|---|---|
| `docs/case-study/v1-engineering-case-study.md` | A status paragraph naming the evidence set; three unnumbered sections before section 1 — the results-first summary, what the evidence demonstrates, and how to read and check the page; Figure 1, the committed architecture image, in section 3; Figures 2 and 3 in section 7; the corrections listed below |
| `docs/case-study/v1-engineering-case-study.v1alpha1.json` | The three new sections; `verifiedIn` and `verifiedAgainst`; `validationRefs` in place of one `validationRef`; 13 figures added, for 37 in all; 2 re-anchored; a `visuals` list of the three figures, with the image's text alternative and each text figure's counts written as words; limitations rewritten for figures |
| `tests/testing/test_case_study.py` | Tests for the evidence set; the summary's place, length, claims, and links; that every figure on the page is declared; the figures' numerals, count words, sources, and captions; the architecture image and its text alternative; the count of claims holding no record; and the pod-loss intervention wording on four reader surfaces. The measurement check now knows seconds, minutes, hours, and decimal memory units, and counts a number as declared only where a figure quotes it beside a unit |
| `README.md` | Three pod-loss sentences narrowed to what the record establishes, and three entry points that said "Executed once" corrected to say how often each ran |
| `docs/environment/operator-runbook.md` | The same two narrowings in the pod-loss incident |
| `docs/testing/test-inventory.v1alpha1.json`, `docs/testing/test-inventory.md` | The case-study module's description, for what it now holds |
| `docs/proof/README.md` | This record, in the `Case study` row |
| `CHANGELOG.md` | One entry under `Unreleased` |
| `docs/proof/case-study/v1-s5-007-pr2-validation.md` | This record |

Nothing under `src/`, `tools/`, `charts/`, `infra/`, `deploy/`, or `scripts/` changed,
and neither did the register, the ledgers, the index, the proof dashboard, or any dated
record.

## Wording changed, narrowed, or re-anchored since the draft

Each of these was found by reading the cited record again, field by field; the ones
marked *review* were found by the independent review of this change's first commit,
and several of them correct that commit rather than the draft.

1. **The deleted pod's readiness, sections 1 and 7.** The draft said the deleted pod
   reported `Ready: True` "for the whole outage". The record's readiness samples run
   from 1.4 s to 28.6 s after the delete, the caller-visible outage it defines begins
   31 764 ms after the delete, and the next sample, at 33 665 ms, is the replacement's.
   The page now says "at every readiness sample before the replacement was observed
   Ready" — the first commit said "until", which claimed the unobserved seconds
   between samples too (*review*) — and that which pod was Ready is the record's
   reading of a count.
2. **Where the outage begins, section 7 and Figure 3.** The first commit said the
   outage began when the in-flight request came back `500`. It begins at the
   completion of the next request, the first refusal, 31 764 ms after the delete; the
   in-flight request is counted in the record's `before` window (*review*).
3. **How the outage ends, section 7 and Figure 3.** The first commit added that the
   outage ended 30 059 ms after the replacement was observed Ready and read it as "a
   Ready replacement was not yet a served caller", and, in its fix-up before the
   commit, that the endpoint count "did not track the recovery". Both overread one
   slow request. The request that ended the outage was the first one not refused; it
   was the only request in flight when the replacement was observed Ready, and took
   30 287 ms. The page now says exactly that, says the record does not establish why
   it was slow, and keeps the endpoint count as the signal that tracked what a caller
   could reach (*review*).
4. **Scrape health, the summary, sections 1, 7, and 8, and Figure 3.** The draft said
   scrape health "said the job was up throughout", and the first commit repeated it and
   drew it into Figure 3 as "unchanged". The record's narrative says so, but its
   committed telemetry does not: the serving runtime's `up` series read `0` at the
   collector's steps 32.3 s and 47.3 s after the delete, and the job's targets-up
   ratio read `0` at 47.3 s and 62.3 s, both inside the outage. What the telemetry
   shows is scrape health lagging the loss by a scrape or more, and the page now says
   that and names the disagreement with the record's narrative (*review*).
5. **What kept the unready model alive, the summary, the bridge, and sections 1 and
   7.** The draft credited the liveness probe at the socket, and the first commit
   called it "the probe split". The chart gives the runtime a startup probe on the
   model's health endpoint with a 600 000 ms budget, and Kubernetes asks neither
   liveness nor readiness until a startup probe passes; the process stayed alive
   because that budget had not run out. And no readiness probe "removed" the
   runtime's address: the pod never became Ready, so its Service never held one. The
   page now says both, and that the unready record credits the liveness probe
   (*review*).
6. **Memory accounting, section 1.** The draft said a limit sized from the smaller
   memory figure "produces" page eviction and silent latency, in a list introduced as
   things found on this host. The feasibility record reasons that it would and did
   not provoke it; the page now says so.
7. **The unready model's completions, section 7.** The draft did not say they were
   asked of the API pod through a forward, because neither Service had a ready
   endpoint, or that a caller through the Service would have met no endpoint at all,
   which the record states rather than measures. Both are said now.
8. **The bridge, what the evidence demonstrates.** The first commit said each
   experiment "ran from a descriptor registered before it". Each descriptor was first
   committed together with its result, and the unready descriptor was amended after
   its run, so the page now says what the records do show: each names the digest of
   the descriptor it ran against, and the pod-loss code was corrected to its
   registration rather than the reverse. It also said "every statement a reader
   meets is a register row", which is true only of the claims the page cites, and
   "no amount of them is quoted", which is true of this page and not of the cost
   record (*review*).
9. **Smaller corrections.** "Pod readiness lied" is now "reported a deleted pod as
   Ready". The clean-clone run is attributed as its record attributes it, to the
   change's author, an AI coding agent. The 5.4 times figure is marked as the first
   run's (*review*). Figure 3 no longer calls the whole run "one request at a time";
   the caption says the delete landed in that phase (*review*).
10. **Two figures re-anchored.** The 1.71 GiB model size and the 7.60 GiB container
    memory were read from ADR 0002. Both are now read from
    [the feasibility record](../serving/v1-s0-003-pr2-runtime-feasibility.md), which
    measured them: the weight file on disk at 1,834,426,016 bytes, and the memory
    reaching the container virtual machine at 8158400512 bytes, each marked measured.

Nothing in the draft was found to depend on a release blocker without naming it.

## The results-first summary, and the evidence behind each row

| Row | Records it rests on | Claim |
|---|---|---|
| More callers, no more work | [performance findings](../serving/v1-s4-004-pr2-findings.v1alpha1.json) and [their narrative](../serving/v1-s4-004-pr2-performance-findings.md) | `a-bounded-local-performance-matrix-was-measured-and-a-degradation-point-observed` |
| Which signal tells the truth when the pod is lost | [the recovery record](../serving/v1-s4-006-pr1-recovery-record.v1alpha1.json) and [its narrative](../serving/v1-s4-006-pr1-inference-pod-recovery.md); the second execution in [the clean-clone run](../environment/v1-s5-001-pr2-clean-clone-run.md) | `caller-visible-impact-of-losing-the-inference-pod-was-measured-under-load` |
| A model that never finishes loading | [the unready-model record](../serving/v1-s4-007-pr1-unready-model-recovery.md) | `an-unready-model-was-held-unready-and-recovered-by-an-operator` |
| The whole path from nothing | [the clean-clone run](../environment/v1-s5-001-pr2-clean-clone-run.md) | `a-reviewer-can-reproduce-v1-from-a-clean-clone` |
| The cost of measured use | [the cost baseline](../cost/v1-s4-005-pr2-cost-baseline.md) | `the-cost-method-was-applied-to-use-taken-from-a-measured-run` |

Every one of the five claims is certified and none is a release blocker; a test fails
if the summary cites a blocker or an uncertified claim, and each row's link must reach
a heading inside the section it names. Status, boundary, and the at-a-glance summary
together are 785 words, counting tokens that hold a letter or a digit, and a test
holds them at or under 850 — a proxy for a reading of about three minutes, not a
check that the words are the right ones. The bridge that follows is outside the
budget.

**What the evidence demonstrates** is phrased as practices shown on this project's own
evidence, with a sentence saying they are not a result achieved anywhere else. Each
practice points at an experiment the page already describes. It adds no figure.

## The figures

| Figure | What it shows | Drawn from | How it is checked |
|---|---|---|---|
| 1 | The committed architecture image the README shows, with a caption correcting its register box: every certified claim holds a record, and fourteen uncertified claims hold none | `docs/architecture/inferops-v1-architecture.png`, and [the system architecture](../../architecture/system-architecture.md) | The image is tracked, shown in section 3, and has a text alternative there; the caption states its boundary; the count fourteen is recomputed from the register and must be in the caption. Nothing reads the image's content |
| 2 | The declared load: callers, what the runtime deferred and processed, its processor share, the completed rate, and the median latency at each level | [performance findings](../serving/v1-s4-004-pr2-findings.v1alpha1.json), [narrative](../serving/v1-s4-004-pr2-performance-findings.md) | Every numeral in its body is one of eight declared figures, read back by JSON pointer or verbatim, and every count word one of four declared phrases read by pointer; the caption must name the provider, the host, the prompt, what was not tested, and that it is not capacity |
| 3 | The pod loss as a timeline: what the caller got, how many pods reported Ready, and the Service's ready endpoints, from the delete to the end of the outage | [recovery record](../serving/v1-s4-006-pr1-recovery-record.v1alpha1.json), [narrative](../serving/v1-s4-006-pr1-inference-pod-recovery.md) | Every numeral in its body is one of ten declared figures, or one of three HTTP statuses listed as unpoliced with a reason, and every count word one of five declared phrases read by pointer; the caption must name the provider, the host, one replica, the sampler's width, and that it is not an availability figure |

No figure introduces a value the records do not hold. Each figure's first line, which
names its setup, is checked by review. Figure 2 says what moved together and
its caption says the cause was not tested; Figure 3's "not sampled" cells mark moments
the readiness sampler did not observe, rather than leaving a reader to infer a value.

## The README and the reader path

- **Narrowed.** The pod-loss row of what V1 proves said "nobody intervened". The record
  establishes that the workflow issued no mutating command between the delete and its
  closing uninstall, and says that this does not establish that nothing outside it
  intervened; the row now says the former. The pod-loss row of the results and the
  inference-pod-recovery entry point said the deleted pod reported Ready "throughout";
  both now say at every readiness sample before the replacement was observed Ready.
  The operator runbook carried the same two phrasings and is narrowed the same way. A
  test now refuses "nobody intervened", "no person intervened", "without
  intervention", and their near relatives on the README, the case study, the runbook,
  and the pod-recovery page.
- **Corrected.** Three entry points said "Executed once on `docker-desktop`". The
  performance scenarios ran again in the clean-clone run; the pod recovery ran after a
  first attempt whose figures were wrong, and again in the clean-clone run; and the
  unready model's record describes an earlier execution. Each now says so.
- **Not added.** A README link to the case study. The page is a draft; linking it
  from the README is publishing it. The reader path the page describes — README, case
  study, proof dashboard, records — is stated in the page itself, which says the
  README does not link there yet.

## Sentences carried, and defects in dated records

Carried to the change that publishes, because each is a register edit or a
publication step:

- [The claim and evidence register](../../testing/claim-evidence-matrix.md) still says
  the case study "has not been written". A draft has existed since `V1-S5-007-PR1`.
  An edit to the register needs a `set-register-field` operation in a ledger, and it
  moves the evidence-set digest this page is verified against.
- The register also still says, of the pod-loss claim, that the deleted pod reported
  `Ready: True` "for the whole 31,960 ms outage", in the matrix and in the claim's
  `doesNotEstablish` and result, which the evidence index mirrors. The same ledger
  cost applies (*review*).
- The README entry point, which must be governed by a register row's `readmeRefs` or
  listed as a surface that claims nothing.

Found in dated records, and not rewritten here, because historical proof is corrected
by an additive note, not an edit:

- [The pod-recovery record](../serving/v1-s4-006-pr1-inference-pod-recovery.md) says
  scrape health "never went to zero for the job" and "said the job was up
  throughout". Its own committed telemetry reads `0` for the serving runtime's job
  inside the outage.
- [The unready-model record](../serving/v1-s4-007-pr1-unready-model-recovery.md)
  says liveness "did not restart a healthy process" and credits the socket-level
  liveness probe. While the startup probe had not passed, Kubernetes did not ask the
  liveness probe; what held was the startup budget.
- [The clean-clone run](../environment/v1-s5-001-pr2-clean-clone-run.md) says
  "nobody intervened" of its pod-loss execution, which is broader than what its
  workflow records.

## How the checks were shown to bite

Thirteen mutations were made to working copies of the page, its data file, and the
README, the case-study suite run against each, and the files restored. Each failed
the test it was aimed at. The first seven were run before the first commit; the last
six after the review, each against a bypass the review demonstrated on the first
commit's tests:

| Mutation | Test that failed |
|---|---|
| A number nothing declares drawn in Figure 2 | `test_every_number_in_a_text_figure_is_declared[declared-load]` |
| A declared number left out of Figure 3 | `test_every_number_in_a_text_figure_is_declared[pod-loss]`, `test_the_document_quotes_every_declared_figure` |
| The provider dropped from Figure 3's caption | `test_every_visual_has_a_caption_that_states_its_boundary[pod-loss]` |
| The evidence-set digest the data file states changed | `test_the_page_names_the_evidence_set_it_was_verified_against` |
| A release blocker cited in the summary | `test_the_summary_rests_on_no_release_blocker[at-a-glance]` |
| "Nobody intervened" restored to the README | `test_no_reader_surface_says_nobody_intervened_in_the_pod_loss[README.md]` |
| A duration with no source added to the summary | `test_no_measurement_is_quoted_without_a_declared_figure` |
| "At most three seen" changed to "at most nine seen" in Figure 2 | `test_every_count_a_text_figure_writes_in_words_is_declared[declared-load]` |
| A summary link pointed at a missing anchor, labelled with the wrong section | `test_the_summary_links_every_finding_to_its_section` |
| An undeclared fenced figure and a `Figure 4` caption added | `test_every_figure_the_page_shows_is_declared` |
| "Without intervention" added to the README | `test_no_reader_surface_says_nobody_intervened_in_the_pod_loss[README.md]` |
| "4 seconds" added to the summary | `test_no_measurement_is_quoted_without_a_declared_figure` |
| A digit glued to a letter, `p99`, drawn in Figure 2 | `test_every_number_in_a_text_figure_is_declared[declared-load]` |

The "4 seconds" mutation passed the first version of the strengthened test, because
the number 4 is declared elsewhere, as a concurrency level. A number now counts as
declared for that check only where a figure quotes it beside a unit.

## What the independent review found

Two reviewers read the first commit independently: one fact-checked every new or
changed sentence, cell, and figure line against the records it rests on, reading the
raw load records and the committed telemetry where the narrative records were not
enough; the other reviewed the tests and the bookkeeping, and demonstrated each
bypass it reported by mutating a working copy. Every finding was verified against the
files before it was acted on, and none was dismissed.

**The first commit said more than its records in five places**, each corrected above:
the outage's start was pinned on the wrong request (item 2); one slow request was read
as a Ready replacement not yet serving, and the endpoint count as failing to track the
recovery (item 3); scrape health was said to stay up, repeating a record narrative its
own telemetry contradicts (item 4); the liveness probe, and then "the probe split",
was credited with what the startup budget did (item 5); and the README's "Executed
once" appeared three times where each experiment ran more than once, while this record
said the README and the case study agreed.

**The first commit's tests were weaker than their descriptions in four places**:
counts written as words escaped the check that "every number" in a figure is declared;
the measurement check knew only ms, %, GiB, and MiB while the page said "every
duration"; the summary's links were checked for their shape and not for resolving; and
an undeclared figure could be added without failing anything. Each is now a test, and
each bypass is a row in the mutation table above.

**Smaller findings, each fixed:** the word budget measured less than "the summary" and
counted table pipes as words; two tests chose sections by position rather than by
identifier; figure numerals were read across line breaks; a digit glued to a letter was
not read; the claim-count test searched the whole page rather than Figure 1's caption;
fences were recognised more narrowly than the link checker recognises them; the image
test accepted a plain link and an untracked file; an unpoliced number could outlive the
number it exempted; the intervention wording was refused on three surfaces and missed
"no person intervened", the phrase this repository has used before; the bridge said
"registered before it", "every statement", and "no amount of them"; the clean-clone
run's author and the cost ratio's run were left unstated; and this record said "three
reader surfaces" and "under 850".

What the reviewers confirmed rather than corrected: every range and maximum in Figure 2;
every sample, interval, and count in Figure 3 other than the outage's start; every
summary figure; the memory sentence; Figure 1's caption and the count fourteen; the
gate, the digest, and the blocker count; the figure, re-anchoring, and per-figure
counts in this record; the README and runbook "no mutating command" wording; and the
absence of private information in the diff.

## Validation

From Git Bash at the repository root, with every file of this change staged so that
the suites that read `git ls-files` see it:

```text
uv run --locked ruff format --check .
uv run --locked ruff check .
uv run --locked python -m mypy
uv run --locked python -m pytest tests/testing/test_case_study.py -q
uv run --locked python -m pytest tests/testing tests/security tests/architecture -q
uv run --locked python -m tools.proof_dashboard --check
uv run --locked python -m tools.evidence_index --check
uv run --locked python -m pytest -q
uv run --locked python -m tools.evidence_index --gate
git diff --cached --check
```

Results are recorded in [the results section](#results).

### Results

On 2026-09-25, on one Windows host, before the first commit:

| Command | Result |
|---|---|
| `ruff format --check .` | 506 files already formatted, after one reformat of the test module |
| `ruff check .` | All checks passed |
| `python -m mypy` | No issues in 275 source files |
| `pytest tests/testing/test_case_study.py -q` | 183 passed |
| `pytest tests/testing tests/security tests/architecture -q` | 10294 passed, 6 skipped, run again after the last wording edits |
| `python -m tools.proof_dashboard --check` | `OK       dashboard.md is what the register produces` |
| `python -m tools.evidence_index --check` | `OK       v1-evidence-index.v1alpha1.json is what the register and ledger produce` |
| `pytest -q`, the default lane | 15008 passed, 33 skipped, 14 deselected, in 16 min 46 s |
| `python -m tools.evidence_index --gate` | `INCOMPLETE V1-S5-006: 5 release blockers`, exit 1, as intended |
| `git diff --cached --check` | Clean |

The default lane ran before the last wording edits to the page, the validation record,
and the changelog, which changed prose only; the documentation suites were run again
after them. The Helm and Terraform gates were not run: nothing under `charts/` or
`infra/` changed.

After the review's fixes, before the second commit: formatting, lint, and types clean
again, 506 files formatted and no issues in 275 source files; the case-study suite 187
passed, the four added tests being the check that every figure is declared, the
count-word check for each of the two text figures, and the fourth reader surface, the
pod-recovery page; the resolving summary-link check replaced the shape-only one; `git diff --cached --check` clean; and the default lane 15012 passed,
33 skipped, 14 deselected, in 19 min 39 s.

## Privacy and publicability

The staged diff was searched for a drive-letter or home-directory path, a scratch
directory, an e-mail address, a credential-shaped string, and the name of any private
planning document. None is present. No model artifact, generated render, or machine
state is added.

## Acceptance criteria

For this change:

| Criterion | State |
|---|---|
| Published as final only against a frozen, release-eligible pack; otherwise draft with the blocker reported | **Met by staying a draft.** The gate is incomplete on five blockers, named above, and a test holds the status |
| Explains why LLM serving needs a paved road | Met, in section 1, with the memory sentence narrowed |
| Connects architecture to measured reliability and bounded, provider-labelled performance evidence | Met, in the summary, sections 3, 5, and 7, and Figures 1 to 3, each figure's caption naming the provider and host |
| Cost limited to the synthetic method; no real-provider figure | Met, and held by a test that refuses any amount from a cost result |
| States constraints and alternative decisions | Met, in sections 2, 4, and 11, unchanged |
| No fabricated, generalized, capacity, SLO, availability, or client-outcome result | Every figure reads back from a committed file, and the summary and bridge each say what they do not establish; whether the prose generalizes is a reading, done by this change and its review |
| The first 60–180 seconds expose the strongest findings, their implications, and the boundary | The summary is the first section and is bounded by a word budget; whether it reads well in three minutes is a reader's judgement |
| The deep narrative remains, and links to the proof dashboard and the records | Met; sections 1 to 13 and the appendix are kept, and every section still ends in its evidence |
| Figures are derived from evidence and do not overstate cause or scope | Figures 2 and 3 are checked numeral by numeral and count word by count word, and each caption states what was not tested or not sampled; Figure 3's scrape-health and outage-end rows were corrected after review |
| README and case study agree on what both surface | Met for the pod loss and for how often the three experiments ran, which is where they disagreed; the register's own "whole outage" wording is carried, as above |
| Uses the current evidence-level model | Met; the page uses `C0` to `C4` only with their current meanings, and the repository's existing checks refuse a superseded pairing |
| Explains what evidence would justify a second version | Met, in section 13, unchanged |

For the parent story, the sign-off against a frozen evidence pack is **not met**: the
pack is not frozen, and the case study is not published.

## Not run

No real model, runtime, Kubernetes cluster, or destructive experiment was run, and none
was authorised. No paid service was used. Nothing was tagged, released, or published,
and no blocker was re-run.
