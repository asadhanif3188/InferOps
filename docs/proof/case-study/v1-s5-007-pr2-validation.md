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
5. **Machine-checked figures and review-checked prose.** Every duration, percentage,
   and memory size, as before; in the two text figures, every number whatever its
   unit. Everything else is review-checked, and the page says which.
6. **README wording broader than the evidence.** Three places: "nobody intervened" in
   the pod-loss row of what V1 proves, and "throughout" twice for the deleted pod's
   readiness. All three are narrowed below.
7. **Surfaces that must link to the case study once it is published.** The README,
   which must govern the link by a register row's `readmeRefs` or list it as a surface
   that claims nothing, and [the proof index](../README.md), which already indexes its
   validation records. Neither link is added while the page is a draft.

## What changed

| File | Change |
|---|---|
| `docs/case-study/v1-engineering-case-study.md` | A status paragraph naming the evidence set; three unnumbered sections before section 1 — the results-first summary, what the evidence demonstrates, and how to read and check the page; Figure 1, the committed architecture image, in section 3; Figures 2 and 3 in section 7; the corrections listed below |
| `docs/case-study/v1-engineering-case-study.v1alpha1.json` | The three new sections; `verifiedIn` and `verifiedAgainst`; `validationRefs` in place of one `validationRef`; 13 figures added, for 37 in all; 2 re-anchored; a `visuals` list of the three figures; limitations rewritten for figures |
| `tests/testing/test_case_study.py` | Tests for the evidence set, the summary's place, length, and claims, the figures' numbers, sources, and captions, the architecture image, the count of claims holding no record, and the pod-loss intervention wording on three reader surfaces |
| `README.md` | Three pod-loss sentences narrowed to what the record establishes |
| `docs/environment/operator-runbook.md` | The same two narrowings in the pod-loss incident |
| `docs/testing/test-inventory.v1alpha1.json`, `docs/testing/test-inventory.md` | The case-study module's description, for what it now holds |
| `docs/proof/README.md` | This record, in the `Case study` row |
| `CHANGELOG.md` | One entry under `Unreleased` |
| `docs/proof/case-study/v1-s5-007-pr2-validation.md` | This record |

Nothing under `src/`, `tools/`, `charts/`, `infra/`, `deploy/`, or `scripts/` changed,
and neither did the register, the ledgers, the index, the proof dashboard, or any dated
record.

## Wording changed, narrowed, or re-anchored since the draft

Each of these was found by reading the cited record again, field by field.

1. **The deleted pod's readiness, section 1 and section 7.** The draft said the deleted
   pod reported `Ready: True` "for the whole outage". The record's readiness samples
   run from 1.4 s to 28.6 s after the delete, the caller-visible outage it defines
   begins 31 764 ms after the delete, and the next sample, at 33 665 ms, is the
   replacement's. So the samples show the deleted pod Ready from the first sample until the
   replacement was observed Ready, not across the outage. The record's own narrative
   uses the looser phrase; the case study now says what the samples show, and adds
   that which pod was Ready is the record's reading of a count, since the samples hold
   only how many pods were Ready.
2. **What a caller met after the replacement was Ready, section 7.** The draft left
   out that the outage ended 30 059 ms after the replacement was observed Ready
   (`serviceRestoredRelativeToObservedReadyMs`), by a request that took 30 287 ms.
   That is the second half of the readiness finding — a Ready replacement was not yet
   a served caller — and the record does not establish why that request took so long,
   which the page now says. The readiness sampler is several seconds wide, which
   Figure 3's caption states.
3. **Where the outage begins, section 7.** The draft gave the outage's length without
   its start. It begins 31 764 ms after the delete, when the in-flight request came
   back `500`, because the record measures it from the first unserved completion, not
   from the delete. Said now.
4. **Memory accounting, section 1.** The draft said a limit sized from the smaller
   memory figure "produces" page eviction and silent latency, in a list introduced as
   things found on this host. The feasibility record reasons that it would; it did
   not provoke it. The sentence now says the record reasons it without having provoked
   it.
5. **The unready model's completions, section 7.** The draft said every completion
   asked came back `runtime-unreachable`, without saying they were asked of the API pod
   through a forward, because neither Service had a ready endpoint. A caller arriving
   through the Service would have met no endpoint at all, which the record states
   rather than measures. Both are said now.
6. **Which signal tracked the caller, section 7.** The draft, following the record's
   narrative, said the Service's ready-endpoint count was the signal that tracked what
   a caller could reach. It tracked the loss: it read zero while the deleted pod still
   reported Ready. It did not track the recovery: the sample that saw the replacement
   Ready also saw one ready endpoint, and the outage ended 30 059 ms later. The page
   now says the count came closest and where it fell short, and the summary says only
   that it went to zero with the loss.
7. **"Pod readiness lied", section 8.** Narrowed to "reported a deleted pod as Ready",
   which is what the record shows.
8. **Two figures re-anchored.** The 1.71 GiB model size and the 7.60 GiB container
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
if the summary cites a blocker or an uncertified claim. The summary quotes no figure
the page did not already declare except 30 059 ms, which is declared and read back
like the rest. Status, boundary, and summary together are 804 words, and a test holds
them under 850 — a proxy for a reading of about three minutes, not a check that the
words are the right ones.

**What the evidence demonstrates** is phrased as practices shown on this project's own
evidence, with a sentence saying they are not a result achieved anywhere else. Each
practice points at an experiment the page already describes. It adds no figure.

## The figures

| Figure | What it shows | Drawn from | How it is checked |
|---|---|---|---|
| 1 | The committed architecture image the README shows, with a caption correcting its register box: every certified claim holds a record, and fourteen uncertified claims hold none | `docs/architecture/inferops-v1-architecture.png`, and [the system architecture](../../architecture/system-architecture.md) | The image is committed and linked from section 3; the caption states its boundary; the count fourteen is recomputed from the register. Nothing reads the image's content |
| 2 | The declared load: callers, what the runtime deferred and processed, its processor share, the completed rate, and the median latency at each level | [performance findings](../serving/v1-s4-004-pr2-findings.v1alpha1.json), [narrative](../serving/v1-s4-004-pr2-performance-findings.md) | Every number is one of eight declared figures, read back by JSON pointer or verbatim; the caption must name the provider, the host, the prompt, what was not tested, and that it is not capacity |
| 3 | The pod loss as a timeline: what the caller got, how many pods reported Ready, and the Service's ready endpoints, from the delete to the end of the outage | [recovery record](../serving/v1-s4-006-pr1-recovery-record.v1alpha1.json), [narrative](../serving/v1-s4-006-pr1-inference-pod-recovery.md) | Every number is one of ten declared figures, or one of three HTTP statuses listed as unpoliced with a reason; the caption must name the provider, the host, one replica, the sampler's width, and that it is not an availability figure |

No figure introduces a value the records do not hold. Small counts in the figures —
one request at a time, at most three deferred, one pod Ready — are written in words,
read from the records, and checked by review. Figure 2 says what moved together and
its caption says the cause was not tested; Figure 3's "not sampled" cells mark moments
the readiness sampler did not observe, rather than leaving a reader to infer a value.

## The README and the reader path

- **Narrowed.** The pod-loss row of what V1 proves said "nobody intervened". The record
  establishes that the workflow issued no mutating command between the delete and its
  closing uninstall, and says that this does not establish that nothing outside it
  intervened; the row now says the former. The pod-loss row of the results and the
  inference-pod-recovery entry point said the deleted pod reported Ready "throughout";
  both now say until the replacement was observed Ready. The operator runbook carried
  the same two phrasings and is narrowed the same way. A test now refuses "nobody
  intervened" or "no one intervened" on the README, the case study, and the runbook.
- **Not changed, deliberately.** The dated [clean-clone run](../environment/v1-s5-001-pr2-clean-clone-run.md)
  also says "nobody intervened" of its second execution. It is a dated record, and
  historical proof is not rewritten here; the phrase is recorded as broader than its
  evidence, and the case study does not repeat it.
- **Not added.** A README link to the case study. The page is a draft; linking it
  from the README is publishing it. The reader path the page describes — README, case
  study, proof dashboard, records — is stated in the page itself, which says the
  README does not link there yet.

## Sentences carried to the change that publishes, again

- [The claim and evidence register](../../testing/claim-evidence-matrix.md) still says
  the case study "has not been written". A draft has existed since
  `V1-S5-007-PR1`, so the sentence is stale. An edit to the register needs a
  `set-register-field` operation in a ledger, and it moves the evidence-set digest this
  page is verified against. Whether the sentence becomes "a draft exists, unpublished"
  or goes away depends on publication, so it is carried with the README link to the
  change that publishes.
- The README entry point, which must be governed by a register row's `readmeRefs` or
  listed as a surface that claims nothing.

## How the checks were shown to bite

Seven mutations were made to working copies of the page, its data file, and the
README, the case-study suite run against each, and the files restored. Each failed the
test it was aimed at:

| Mutation | Test that failed |
|---|---|
| A number nothing declares drawn in Figure 2 | `test_every_number_in_a_text_figure_is_declared[declared-load]` |
| A declared number left out of Figure 3 | `test_every_number_in_a_text_figure_is_declared[pod-loss]`, `test_the_document_quotes_every_declared_figure` |
| The provider dropped from Figure 3's caption | `test_every_visual_has_a_caption_that_states_its_boundary[pod-loss]` |
| The evidence-set digest the data file states changed | `test_the_page_names_the_evidence_set_it_was_verified_against` |
| A release blocker cited in the summary | `test_the_summary_rests_on_no_release_blocker[at-a-glance]` |
| "Nobody intervened" restored to the README | `test_no_reader_surface_says_nobody_intervened_in_the_pod_loss[README.md]` |
| A duration with no source added to the summary | `test_no_measurement_is_quoted_without_a_declared_figure` |

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
| Figures are derived from evidence and do not overstate cause or scope | Figures 2 and 3 are checked number by number, and each caption states what was not tested or not sampled |
| README and case study agree on what both surface | Met for the pod loss, which is where they disagreed |
| Uses the current evidence-level model | Met; the page uses `C0` to `C4` only with their current meanings, and the repository's existing checks refuse a superseded pairing |
| Explains what evidence would justify a second version | Met, in section 13, unchanged |

For the parent story, the sign-off against a frozen evidence pack is **not met**: the
pack is not frozen, and the case study is not published.

## Not run

No real model, runtime, Kubernetes cluster, or destructive experiment was run, and none
was authorised. No paid service was used. Nothing was tagged, released, or published,
and no blocker was re-run.
