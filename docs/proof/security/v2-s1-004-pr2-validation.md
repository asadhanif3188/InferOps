# V2-S1-004-PR2 validation

Date: 2026-10-01

What this change checked before it was committed, and how. What it publishes is
[the reconciliation of pull request #103](v2-s1-004-pr2-security-maintenance-reconciliation.md),
two dated notes in [ADR 0008](../../architecture/decisions/ADR-0008-v1-security-baseline.md),
and a dated correction to [the `EX-07` assessment](ex-07-runtime-image-exception.md); this
page is about the findings it closes and the checks run over the repository after they were
written.

The change executed nothing against a host: no cluster, runtime, image, or scanner was
run, and nothing was provisioned, tagged, released, or published. Every check below is
static, which is `C0` under [the evidence levels](../../testing/evidence-levels.md). It
adds no record to the evidence pack and moves no claim.

## The findings this closes

The independent collective review of the first V2 sprint returned *blocked*. Its
highest-severity finding was closed by `V2-S1-004-PR1`. Two more were about pull request
#103, the change that accepted `EX-07` on 2026-09-30:

- **It edited an accepted V1 decision in place.** ADR 0008's `D11` said "Six exceptions are
  recorded" and its consequences "six accepted exceptions"; #103 changed both to seven, with
  no note, so the record read as if `EX-07` had existed when the decision was made.
- **It had no record saying what kind of change it was.** It was necessary - the image scan
  gate had begun failing on every branch for a reason outside the repository - but nothing
  public said it was maintenance rather than planned V2 work.

## Eligibility, checked before anything was written

- **What it builds on is merged.** `main` was at `3de7d01`, the merge of `V2-S1-004-PR1`, and
  #103 had merged as `51cddd1`.
- **The gate and the pack.** `python -B -m tools.evidence_index --gate` exited 0 with
  `FROZEN` for `V1-S5-013-PR2`, `RELEASED v1.0.0` at `718ad2e0…` with the set `1d40b33f…` and
  the pack `652e9051…`, and `CURRENT` with the set `08d4868f…` and the pack `b958a724…` - the
  six digests `V2-S1-004-PR1` recorded. No record in the pack cites ADR 0008, the `EX-07`
  assessment, or any file #103 touched; each of #103's 24 paths was searched for in the
  committed index and none is there.

## What was restored, and from which revision

#103 changed exactly two lines of ADR 0008, both in prose, and nothing else in it:

| Where | Released wording, restored | What #103 had made it |
|---|---|---|
| `D11 — An exception is argued, not absorbed`, first sentence | Six exceptions are recorded. | Seven exceptions are recorded. |
| `Consequences`, the register bullet | Twelve deferred risks, ten of them blocking production use, and six accepted exceptions. | … and seven accepted exceptions. |

The source of the restored wording was read from Git, not retyped:

| Identity | Value |
|---|---|
| Tag | `v1.0.0`, tag object `17c9bbd71ffaeaf286f7949a1c91624bbcfe3e04`, commit `718ad2e0fac8ae70c6d053a2decb00e61ff3de39` |
| ADR 0008 at the tag | blob `c1f8d9778a825ca1bacf3d95a53cd2f7eae371bf`, SHA-256 `cbcbb4579449e361f399423b40787bc7b8093aeed9e71b1fd0eeea20c0fa535d` |
| ADR 0008 just before #103 (`51cddd1^1`) | blob `0fd2dfa734ce197ad63cd5793d729e97030e1c24`, SHA-256 `677eef26691a8537a1057218b033777b9cbbe05d898d1935fcd0d5af97a9e4d3`: the tag's text plus the note `V1-S5-009-PR1` added on 2026-09-27, after the release |
| ADR 0008 as #103 left it (`51cddd1`) | blob `b2a631a67dbd2afecd1479445a36e8a776312515` |

After the change, ADR 0008 with this change's two notes taken out is byte for byte the
pre-#103 blob, and with the 2026-09-27 post-release note taken out as well it is byte for
byte the tag's blob; both comparisons were made over the file's text with LF line endings,
and the second is what the new suite asserts.

**How far back "restored" reaches.** The released wording is not the wording of 2026-08-26,
when `D11` was accepted. The sentence then said "Four exceptions are recorded", and a V1
change on 2026-09-12, `2194261`, brought it to six in place, before the release, after
`EX-05` (2026-09-06) and `EX-06` (earlier on 2026-09-12) had been added without it. This change restores the text `v1.0.0` released, which is
the V1 history the release identifies, and does not reach behind it: undoing a pre-release
edit would make the record match neither the release nor the present, and nothing in the
finding asked for it. It is stated here so that "restored" is not read as "as first
accepted".

## What represents the current state

- **Two dated notes in ADR 0008**, in the record's own idiom - the one its 2026-09-27 notes
  use. The first follows `D11`'s paragraphs and says that "six" was true at the release,
  that `EX-07` was accepted on 2026-09-30 until 2026-10-30 and bound to the image digest,
  that the register now records seven, where the current count is kept, what #103 did to
  this record, and that the decision is unchanged. The second follows the consequences and
  points to the first. No header row, decision status, or other text changed; the
  `Amended by` row still names only ADR 0015, because no decision was amended.
- **The current-facing surfaces are unchanged and say seven**: the README, `SECURITY.md`, the
  architecture index, the deferred-risk register, and the security method and its data. A
  test now recomputes each of those counts from the baseline, so the restoration cannot be
  mistaken for rolling them back.
- **The `EX-07` assessment** gains a `Later correction` section, dated, after everything it
  said when merged; its *What changed* row about ADR 0008 is left as it was, since it is
  what #103 did.

## The reconciliation, and why #103 is not a V2 capability change

[The reconciliation](v2-s1-004-pr2-security-maintenance-reconciliation.md) records #103 by
its number, title, merge, and two commits. It states the trigger (a finding published on
2026-09-29 and the gate failure it caused on 2026-09-30), the classification (out-of-band
security maintenance, not one of the sprint's planned changes, no V2 capability), what it
changed in substance (the bounded exception and the guards that now read it), what it left
alone, why the image was not rotated, the evidence boundary, and what it got wrong. #103 adds
nothing to the V2 platform: it touches no contract, schema, domain package, chart, or
manifest, and renders or records nothing.

## Security behaviour: preserved, and checked to be

This change edits no script, ignore file, or baseline row. `EX-07` is the same one finding,
`CVE-2026-84782`, in the same packages of the same image digest, owned by `security`,
accepted on 2026-09-30 until 2026-10-30; the runtime image's ignore file holds that one
entry and the dependency scan's holds none; the image pin is unchanged. The new suite pins
that scope, so a later change that broadens or extends it fails here and has to say so in
its own record. No other exception, risk, control, or status moved.

## What changed

- **`docs/architecture/decisions/ADR-0008-v1-security-baseline.md`**: the two sentences
  restored; two dated notes added.
- **`docs/proof/security/v2-s1-004-pr2-security-maintenance-reconciliation.md`** (new).
- **`docs/proof/security/ex-07-runtime-image-exception.md`**: a dated *Later correction*
  appended. Nothing above it changed, and a test holds that text to the digest of the
  merged record.
- **`tests/security/test_security_maintenance_history.py`** (new).
- **This record** (new), the proof index's security row, the changelog, the test
  inventory's data and page (the fifty-eighth module without a claim, the forty-ninth
  `documentation` module), and its number words. The inventory page's list of which change
  added which `documentation` module stopped at the forty-seventh; #103 added the
  forty-eighth without extending it, and this change extends it with both.

## What the change was asked to reach, and what it reached

| Asked | Reached here | How |
|---|---|---|
| ADR 0008's text changed by #103 is restored to the accepted V1 wording | Yes, to the wording `v1.0.0` released | Both sentences; the file without this change's notes is the pre-#103 blob, and without every post-release note the tag's blob, byte for byte |
| The later `EX-07` state is represented by a dated, additive amendment and by current-facing sources | Yes | Two dated notes after the sentences they amend; the current surfaces keep seven, and a test recomputes their counts from the baseline |
| #103 is traceable as out-of-band security maintenance, not as planned V2 work | Yes | [The reconciliation](v2-s1-004-pr2-security-maintenance-reconciliation.md), linked from the note, the assessment's correction, the proof index, and the changelog |
| `EX-07` stays narrowly scoped and visible; no unrelated security policy changes | Yes | No script, ignore file, or baseline row edited; the scope is pinned by a test |
| Tests guard the historical and current distinction | Yes | See [the planted defects](#checks-that-the-new-tests-are-not-decorative) |
| The released V1 tag and evidence identity are unchanged | Yes | `v1.0.0` still resolves to the tag object and commit above; the gate prints the same six digests; no file the pack cites is touched |
| No V2 runtime, deployment, reliability, `C3`/`C4`, or production claim moves | Yes | The register, the dashboard, and the evidence index are untouched; their checks regenerate them unchanged |

## Decisions taken while writing

- **A digest, not a sentence list.** The new suite could have pinned the two restored
  sentences only. It pins the whole released text instead, with every post-release note
  registered by its opening and the change that added it, so an in-place edit anywhere in
  ADR 0008 fails, not only one to these two sentences. The cost is deliberate: the next
  change that has something to add to this record adds a dated note and a row to that
  table, which is the convention the record already follows.
- **The released text is identified by a pinned digest, not read from the tag.** A test
  that ran `git` would depend on a full clone with tags, which the hosted checkout does not
  guarantee; the digest and the blob it was taken from are recorded above.
- **`EX-07`'s scope is pinned as a tripwire.** When the image is rotated or `EX-07` retired,
  the scope test fails; that change records it in its own record and updates the pinned
  table. The reconciliation keeps what was true on 2026-10-01.
- **The assessment is corrected after its text, not in it.** Its *What changed* row is what
  #103 did; the correction says that for ADR 0008 it was the wrong edit, and the test holds
  the merged text to its digest.
- **No `Amended by` entry.** That row names a decision record that amends a decision. These
  notes amend a count, not `D11`, and the record already carries two notes in this form.

## Checks that the new tests are not decorative

Twelve defects were planted, one at a time, in an archived copy of the working tree -
every tracked and new file, copied outside the repository - never in the tree itself. The
new suite and the two security suites that read the same data, 889 tests, ran in full
against each, and the copy was confirmed back to 889 passed after the last one. Every one
was caught:

| Defect, exactly as made | Of 889 |
|---|---|
| ADR 0008: "Six exceptions are recorded." becomes "Seven exceptions are recorded.", both notes kept - #103's own edit | 5 failed |
| ADR 0008: "and six accepted exceptions." becomes "and seven accepted exceptions.", both notes kept | 5 failed |
| ADR 0008: the `D11` note is deleted | 4 failed |
| ADR 0008: the `D11` note is moved to before the sentence it amends | 1 failed |
| ADR 0008: an unrelated released sentence is edited, `D10`'s "Twelve risks are carried" becoming "Thirteen" | 1 failed |
| ADR 0008: a dated note nobody registered is added before `D12` | 1 failed |
| ADR 0008: the `D11` note's "accepted until 2026-10-30" becomes "2026-11-30", disagreeing with the data | 1 failed |
| README: "Twelve risks and seven accepted exceptions" rolled back to six | 1 failed |
| `EX-07`'s deadline moved to 2026-11-30 in the baseline and the ignore file together | 5 failed |
| A second identifier added under `EX-07` in the runtime image's ignore file | 3 failed |
| The `EX-07` assessment above its correction: "Date: 2026-09-30" becomes "Date: 2026-10-01" | 1 failed |
| The reconciliation loses "**Out-of-band security maintenance.**" | 1 failed |

Seven of the twelve are caught by one test each. That test is the one written for the
property, and the counts are stated so that nobody reads 23 new tests as 23 guards on each
property.

## Commands

Run from Git Bash on Windows, with the locked environment.

| Command | Result |
|---|---|
| `uv run --locked ruff check .` | All checks passed |
| `uv run --locked ruff format --check --no-cache .` | 579 files already formatted, after the formatter rewrapped the new suite once |
| `uv run --locked mypy` | No issues in 317 source files |
| `uv run --locked python -m pytest tests/security/test_security_maintenance_history.py -q -p no:cacheprovider` | 23 passed |
| `uv run --locked python -m pytest tests/security/ tests/testing/test_test_inventory.py tests/testing/test_document_links.py tests/architecture/test_decision_authority.py tests/testing/test_published_methods.py tests/telemetry/test_telemetry_catalog.py -q -p no:cacheprovider` | 3,396 passed |
| The twelve planted defects, against an archived copy | Every one caught; see above |
| `python -B -m tools.evidence_index --check` | Exit 0; the committed index is what the register and ledgers produce |
| `python -B -m tools.evidence_index --gate` | Exit 0; the six digests above, unchanged |
| `python -B -m tools.proof_dashboard --check` | Exit 0; the dashboard is what the register produces |
| `gitleaks dir <path> --config .gitleaks.toml --redact`, for every changed and new file, with gitleaks 8.30.1 (the version the workflow pins) | No leaks found in any |
| `git diff --check` | Exit 0, no output |

**The full default lane ran before the first commit**, with the new files registered with
Git so the link suite collected them:
`uv run --locked python -B -m pytest -q -rs -p no:cacheprovider --basetemp=<scratch>` gave
**16,846 passed, 33 skipped, 14 deselected, none failed**, in 11 min 36 s. That is 36 more
than the 16,810 `V2-S1-004-PR1` recorded: the new suite's 23, and 13 more cases in suites
parametrized over the inventory's modules and the repository's files. The skips are the
ones earlier records name, such as symbolic links this host does not permit. This record's
command table and this paragraph were completed after that run; the link, placeholder, and
history suites were run again over it.

Not run: `helm lint`, kubeconform, Terraform and TFLint, ShellCheck, the package build, the
image build, and both vulnerability scans. This change touches no chart, manifest,
Terraform, workflow, script, package, or image, and `EX-07`'s behaviour is the scan guards',
which it leaves unchanged; those gates run on the selected service.

## Privacy and publicability

The diff was read for private planning material, local paths, credentials, and later story
identifiers. It names no private planning document or repository, no local filesystem path,
no host or account name, and no story after this one. It quotes the review's findings by
what they were about, not in its words. The only finding identifier is `CVE-2026-84782`,
already published here. The digests and Git identities are this repository's own.

## What this does not establish

That any other V1 record is unedited since `v1.0.0` - only ADR 0008 is held to its released
text; that a note's prose is accurate beyond the facts the suite compares; that `EX-07`'s
reachability argument still holds, or that the image has no other finding today - nothing
was scanned; or anything about the sprint's re-review, which is a separate act.
