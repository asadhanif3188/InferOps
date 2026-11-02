# The G1 and G3 switches: two merges with no pre-merge authorization found

Dated 2026-11-02. This page is not backdated, and it cures nothing.

**No explicit authorization of the repository owner was found before either switch merged.** Rule
G4 of [the V2-E02A freeze record](../experiments/v2-e02a/freeze-r4.v1alpha1.json) requires that
authorization for each switch, and an implementation instruction or an open pull request is not
that authorization. The repository owner accepted on 2026-11-02 that the requirement was not met
at merge time. No later statement changes that.

## The two merges

| | G1 | G3 |
|---|---|---|
| Pull request | [#159](https://github.com/asadhanif3188/InferOps/pull/159), `V2-S7-003-PR1` | [#163](https://github.com/asadhanif3188/InferOps/pull/163), `V2-S7-003-PR2` |
| Merge commit | `ff45093b2a9bf2cdbcde5fee453fbc6b64f2e53b` | `a3ed8129f482820a503d6c37ea3d1395f2a7c269` |
| Merged at, as GitHub states it | 2026-10-23T15:06:40Z | 2026-11-01T16:53:26Z |
| Effect | The desired state became 2 API + 1 runtime, and revision 4 of V2-E02A was registered in the same merge | The desired state returned to 2 API + 2 runtime in Git, and revision 3 of V2-E02B was registered in the same merge |
| Comments, review comments, and reviews on the pull request, read from GitHub on 2026-11-02 | 0, 0, and 0 | 0, 0, and 0 |
| The authorization item of the pull request | Unticked | Unticked |
| Pre-merge authorization | None found | None found |
| Later statement | On 2026-10-30T11:08:08Z, after the merge of 2026-10-23, the repository owner selected "Yes, #159 was my authorization" | None before this page |

The repository owner reports the search for an authorization. It covered the repository, the two
pull requests, and the local session records. It did not cover other conversations or email. So
"None found" is bounded by that search, and no file of this repository proves it. The time and the
words of the later statement come from a local session record that is not committed. The page of
the G1 observation confirms the date.

## What the later statement is

The statement of 2026-10-30 is after the G1 merge. It is before the first installation of the
release and before the first fault. It is not a pre-merge authorization.
[The G1 observation](v2-s7-001-pr2-g1-observation/observation.md) and
[the validation of the runs](v2-s7-001-pr2-validation.md) treated it as meeting the prerequisite,
and each now carries a dated note. So does [the validation of the G1 switch](v2-s7-003-pr1-validation.md),
which said that the review of the change and the record of the merge state the authorization.

The acceptance below is not an authorization of the G3 merge either, and it does not say that one
existed.

## Facts that limit the effect

These facts limit the effect. They do not cure the timing.

- **G1.** Attempt `g1-1` on 2026-10-30 stopped before any release was installed. The first
  installation of the release was attempt `g1-2` on 2026-10-31. The three runs of V2-E02A followed
  that observation, and each run removed the release.
- **G3.** No record shows an installation after the removal in `e02a-3`, so no record shows that
  the merge reached a cluster. The merge restored the two desired-state files byte for byte.
  [Its validation record](v2-s7-003-pr2-validation.md) states that it contacted no cluster.

## The disposition

On 2026-11-02 the repository owner accepted both deviations prospectively, as recorded deviations
with stated limits. The acceptance covers these two merges only.

- A current page does not state or imply that either switch was authorized before its merge. A
  page of a past change keeps its text, and the pages named above carry a dated note.
- A statement about either switch names the merge commit and this page. A current page that
  mentions a switch does that in its text or in a dated line under its title.
- No second merge is created to imitate a missing authorization.
- This page does not state that the 2+2 desired state is delivered on a cluster. No record in this
  repository shows that delivery at the G3 merge.

## The control from 2026-11-02

A state-changing merge changes the desired state that the Argo CD Application follows. Before such
a merge, the repository owner writes the authorization as a comment on that pull request, naming
the head commit, and ticks the authorization item in its body. The pull request template has no
such item, so the author of that pull request adds it to the body.

No tool reads this control, and it applies to later merges only.

## What this page does not establish

- That either merge was authorized.
- That a later statement replaces a pre-merge authorization.
- That any run of V2-E02A is valid. [The adjudicated record](../experiments/v2-e02a/eligibility-adjudicated.v1alpha1.json)
  states the current verdict.
- That the desired state is delivered on a cluster.
- An authorization of any later merge, run, or sprint.
