# Independent review of the correction of V2-E02A

Date: 2026-11-02

This page reports the review of the correction that `V2-S7-004-PR1` makes. It is not a review of a
new run, and no run executed. One machine-readable record of each run states the findings with the
digest of each file of that run: [`e02a-1`](e02a-1-review-2.v1alpha1.json),
[`e02a-2`](e02a-2-review-2.v1alpha1.json), and [`e02a-3`](e02a-3-review-2.v1alpha1.json). This page
adds the outcome of each round and what could not be verified.

A review record is not evidence of a run. It states what the reviewers found in the committed files.

> [!IMPORTANT]
> **The first review found the correction not fit to register, and so did the third.** Rounds 3 and
> 4 found defects in the fixes of the rounds before them. The fourth review, a narrow re-check,
> found it fit to register, with no high or medium finding.
>
> **Each figure held.** With code of its own, the first reviewer computed each reading figure from
> the raw streams, and each equals the adjudicated record. No historical file moved.
>
> **Each reviewer is an automated session.** Each is another session of the assistant that drove
> the runs and wrote the correction. None is a person, and none is outside the project.
>
> **The four rounds came before the ledger.** Later reviews read the ledger after it was written,
> and their findings changed its wording. The
> [validation record](../../../environment/v2-s7-004-pr1-validation.md) states them. So no record
> establishes that a review of the wording of the ledger preceded the register change.

## What was reviewed

| Round | Reviewer's focus | Commit | Outcome |
|---|---|---|---|
| 1 | The statements, against the raw files, the requirements, and the repository | `5878ee4` | Not fit to register: three high, six medium, and eight low findings |
| 2 | The code and the tests, with 33 mutations and 31 malformed inputs | `5878ee4` | No critical finding: two high, five medium, and five low findings. Some of them repeat round 1 |
| 3 | Whether each finding was closed, with no sight of the earlier reports | `9e22110` | Not fit to register: one high finding, in the fix of an earlier one, two medium, and nine low |
| 4 | Whether the blocking findings were closed | `f6b8f39` | Fit to register: six low findings |

The rounds ran from 2026-11-02T08:45:55Z to 2026-11-02T11:31:07Z, as the reviewers reported. The
contract of the tool held in each round: the classification record keeps its bytes, and no input
gave a verdict other than `not-decided`.

## Findings

| Finding | Round and severity, as the reviewer gave them | Summary | Disposition |
|---|---|---|---|
| F1 | round 1, high, and round 2, medium | The proof index still said that each run is valid. The check of the pages did not read that page. | corrected: the proof index, and the list of current pages |
| F2 | round 1, high | Current pages presupposed an authorization of G1, or said that a change merges only with an authorization, and the deviation page said that no page does. | corrected: the experiments page, the desired-state page, the profile page, the baseline report, the README, and the deviation page |
| F3 | round 1, high | The adjudication misstated who set it up, what its note said, and what was searched, and it omitted the candidates of its prompt, two commits outside its export, the first draft of the criterion, the strongest source against the ruling, and half of its sources. | corrected: the adjudication |
| F4 | round 3, high | The record said that no source selects the two runtime counts. Revision 4 predates the first fault and reads them, so the sentence was false as worded and leaned towards the stream reading. A confirming review found this in the fix of an earlier finding. | corrected: the record, its statement, and each page that repeated the sentence |
| F5 | round 1, medium | "The field scope holds in 0 of 3" rested on two counts that no source selects for the criterion, and each other count but unavailableReplicas is reported in each reading. | corrected: the members of the record, and each page |
| F6 | rounds 1 and 2, medium | The reuse guard refused only a caller who passed the adjudicated record. The classification record, which a freeze record binds, gave its figures. | corrected: usable_baseline, which reads the adjudicated record itself. A reader that opens the classification record directly still gets eligible, and the tool page says so |
| F7 | rounds 1 and 2, medium | The consumers overstated what is enforced, and they gave V2-E02B a population statement. | corrected: each consumer states its decision and that no tool enforces it |
| F8 | round 1, medium | Statements about the authorization of a switch did not name the merge commit and the deviation. | corrected: each current page that mentions a switch. A later review found that this fix had narrowed the rule on the deviation page, and a later commit restored it |
| F9 | round 1, medium | A page said without a condition that V2-E02B computes an improvement after its own runs. | corrected: the baseline report |
| F10 | round 1, medium | The deviation page was stronger than its search, and it did not attribute it. | corrected: the deviation page, whose counts and times were then read from the GitHub API |
| F11 | round 2, high, and round 3, medium | Malformed stream lines, tiers, windows, instants, and registries raised uncaught exceptions, so a crash looked like a finding of the check. | corrected: the tool. Malformed corrections and a registry nested too deeply for tools/experiment_freeze are not corrected |
| F12 | round 2, high | judge_reading assumed the order of time. A descending stream gave a negative gap and held. | corrected: the tool |
| F13 | round 2, medium | Five mutants survived, among them the four variants of the reading scope through reading_of, and the limit plus 1 ms. | corrected: the suite. A later review reports each requested mutant killed |
| F14 | round 2, medium | The check of the pages had false positives and cheap bypasses. | corrected: the patterns, and the tool page states that the check matches sentences |
| F15 | round 3, medium | The validation record did not list each page that the change corrects. | corrected: the validation record |
| F16 | rounds 1 to 4, low | Low findings: eight in round 1, five in round 2, nine in round 3, and six in round 4. They are stale wording, labels, a note in the wrong place, a wider exception of the check of the pages, and a record that omitted that the review chose the two counts after the evidence was read. | corrected, but for two: the commits named in this record. A malformed correction, and a registry nested too deeply for tools/experiment_freeze, are not corrected |

## What the reviewers could not verify

- The words and the time of the statement of 2026-10-30, and the scope of the search for an
  authorization. They rest on the report of the repository owner.
- What the context of the adjudicator held.
- That `python -m tools.analysis_replay verify` reproduces each run analysis. No reviewer ran it
  directly, and `--check` of the tool reads it.
- Each page-reading suite in the third round: the disk of the host filled, so that review stopped
  that run. Its 21 failures in one earlier run of the eligibility suite are inferred to be from
  the disk, and they are not proved to be. The next runs passed.

## What this review does not establish

- That a person reviewed the correction.
- That a reviewer is independent of the assistant that drove the runs.
- That any run is valid, or that any run is not valid.
- Which reading of `E02A-AC2` is right.
- That the register statements that the ledger writes are correct. These four rounds did not read
  them.
- That the commit `63a953b` is correct. These four rounds did not read it.
