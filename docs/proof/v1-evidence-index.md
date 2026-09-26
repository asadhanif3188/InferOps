# The V1 evidence index

Status: **generated, and checked against its sources on every run of the suite.** The
index is [`v1-evidence-index.v1alpha1.json`](v1-evidence-index.v1alpha1.json), produced
by `python -m tools.evidence_index --write` from
[the claim and evidence register](../testing/claim-evidence-matrix.v1alpha2.json),
[the `V1-S5-006-PR1` normalization ledger](testing/v1-s5-006-pr1-normalization.v1alpha1.json),
[the `V1-S5-006-PR2` completeness ledger](testing/v1-s5-006-pr2-completeness.v1alpha1.json),
[the `V1-S5-013-PR1` closure ledger](testing/v1-s5-013-pr1-closure.v1alpha1.json), and
[the `V1-S5-013-PR2` publication ledger](testing/v1-s5-013-pr2-publication.v1alpha1.json).
It states nothing they do not, and
[`tests/testing/test_evidence_index.py`](../../tests/testing/test_evidence_index.py)
regenerates it and fails on any difference.

The register is organised by claim, which is the right shape for deciding what may be
said. A release needs the other view as well: **one entry per evidence record**, saying
what ran, what was substituted, where, at which revision, with which immutable
identifiers, and which committed files hold the evidence — each file bound to its
content by a hash and to its repository object by name, so that a file changed after
the index was written is caught rather than trusted. That is this index, and it is the
V1 evidence manifest. [The proof dashboard](dashboard.md) answers *what has been
proven*; this answers *what exactly is the evidence, and can it be pinned*.

> [!IMPORTANT]
> The levels in this index are the register's, defined by
> [the evidence-level specification](../testing/evidence-levels.md). They are
> project-defined, and they are not an ISO, NIST, regulatory, or industry
> certification standard. Nothing in this index raises a level or promotes a claim;
> it has no field that could.

## The freeze decision

For V1, the release gate is **complete**, with **0 release blockers**.
`V1-S5-006-PR2` raised 5 — the local serving baseline, the kind cluster helper, the
Helm uninstall's survival clause, the upgrade rollback, and the pod replacement, each a
certified claim whose statement rested on a record whose repository code nothing
identified — and [the closure report](testing/v1-s5-013-pr1-blocker-closure.md) closed
every one: 4 by a rerun from a fresh clone at a named revision, whose new record
identifies the code that ran, and 1 by moving the `kind` helper's claim to
not-claimed. No older record was edited or dropped; each stays cited for what it
observed. `python -m tools.evidence_index --gate` prints the decision and each
blocker's closure, exits 0 now, and exits 1 if a blocker stands or if any blocker
`V1-S5-006-PR2` raised is left without a disposition.

**The evidence pack is frozen.** `V1-S5-013-PR2` changed the register to publish the
case study, wrote four corrections beside dated records, and declared the freeze in
[the publication ledger](testing/v1-s5-013-pr2-publication.v1alpha1.json). The index
derives the freeze rather than reading it: a ledger that declares `frozen` beside an
open blocker is refused. `--gate` now also prints both digests below, and exits 1 if
the committed index is not what the register and the ledgers produce, so a freeze is
never read from a stale digest. The pre-publication freeze candidate that
`V1-S5-013-PR1` named is superseded; [the publication report](testing/v1-s5-013-pr2-publication-and-freeze.md)
compares the two. `V1-S5-008` may consume this freeze only if every other P0 story and
release gate also passes.

How the 38 records that executed their target behaviour identify the repository code
that ran:

| Code identity | Records | Meaning |
|---|---|---|
| `stated-revision` | 20 | The record names the commit that ran |
| `content-pinned` | 4 | A named base commit, plus the LF-normalised SHA-256 of every file that decided the run, each equal to that file at a named commit |
| `no-repository-code` | 4 | No repository code among the claim-material components that executed; the third-party ones are pinned |
| `unidentified` | 10 | Repository code executed and nothing the record cites identifies which; nine of these are under claims another record settles, four of those by a `V1-S5-013-PR1` rerun, and one is under the `kind` helper's claim, which is now not claimed |

Two digests, both in the index's summary:

- **The evidence set,
  `1d40b33fd79d7b6436c35cfe1fc4ec943a8b82fc77ad1da7cd5d96bb2a5ac23a`**, the index's
  `evidenceSetSha256`: SHA-256 over the sorted lines `<sha256>  <path>` of every cited
  file. Publication changed no cited file, so it is the value `V1-S5-013-PR1` named.
  It does not cover the register or the ledgers, so no change to a claim's wording, a
  status, or a ledger's decision can move it.
- **The evidence pack,
  `4242e29fd853f655422a5344d30a576ee65c3ca6a04aab6d764ab25b74e83c6e`**, the index's
  `evidencePackSha256`: the same lines for every cited file together with the register
  and the four ledgers, which the index lists as `packSources`. That is everything the
  index is built from, so any change to what V1 says about its evidence moves it. **It
  is the digest a release quotes.** Neither covers the index itself, which states both,
  or a page that reads the register, such as the README, the proof dashboard, or the
  case study.

## What one entry holds

For each of the **64 evidence records** in the register:

| Field | What it says | Where it comes from |
|---|---|---|
| `claimId`, `claimStatus`, `evidenceLevel` | The claim the record supports, the claim's status, and the record's own level | The register |
| `registerPointer`, `registerEntrySha256` | Where the record sits in the register, and a SHA-256 of its entry in canonical JSON | Computed from the register |
| `execution` | Whether the claim's target behaviour ran, the components that executed, and every substitution with its kind and whether it is claim-material | The register |
| `workload` | The input's source, whether the record declares it representative, and its shape where recorded | The register |
| `environment` | The environment, provider, hardware class, and region | The register |
| `identifiers` | Every immutable identifier the record pins, grouped by kind: commit, image digest, model revision, artifact hash, chart version, package version | The register, which a test holds verbatim to the cited files |
| `codeRevision` | For a record that executed its target behaviour: every repository revision it names, and how that revision relates to what ran | The ledgers' reading of the cited files, each quoted verbatim |
| `codeIdentity` | For a record that executed its target behaviour: how it identifies the repository code that ran, and which claim-material repository components executed | The completeness ledger, and derived again by a test |
| `procedure`, `acceptanceCriteria`, `observationPeriod`, `results` | How to repeat it, what was registered and whether before the run, when it was observed, and what it found, failures included | The register |
| `limitations`, `doesNotEstablish` | The record's own boundary | The register |
| `evidence` | Every cited file: its path, its SHA-256, its git blob name, the date the file gives for itself and the words it uses for that date, whether it has an authorisation section, and any correction recorded beside it | Read from the file; corrections from the ledgers |
| `findings` | The findings of any ledger that concern the record | The ledgers |

Claim entries carry the statement, status, limitation, `doesNotEstablish`, the
declared claim-material components, the levels the claim's records reached, the record
identifiers, the claim's code-identity decision where one was needed, its open release
blockers, and the blockers closed on it. A summary block carries the counts below, the
gate, the freeze, and both digests, and `packSources` binds the register and each
ledger to its content by SHA-256 and git blob name, as a cited file is bound.

**What an entry does not hold.** No record in this repository names an owner, so the
index has no owner field and does not invent one. A date is taken only from a line the
file itself writes — `Date:`, `Date captured:`, `Date produced:`, and so on, with the
label kept, because a record produced on one day may describe a run on another — and
never from a filename or from git; a JSON result file carries no such line and gets
none. **A chart version is a label, not a pin**: `inferops-llm-0.3.0` has been carried
by ten different trees of the chart, so no entry is read as identifying its chart by
version.

## What the index shows today

- **64 evidence records** under 59 claims: 26 at `C0`, 8 at `C1`, 30 at `C2`, and none
  at `C3` or `C4`. Every one of the **41 certified claims** holds at least one record,
  and every record states its limitations and what it does not establish.
- **85 distinct committed files** are cited, all under `docs/proof/`, each hashed and
  each named by its git blob. Eleven of them carry a correction recorded beside them
  rather than inside them.
- **38 records executed their target behaviour, and 20 of them name the repository
  revision that ran.** The other 18 name the base their working tree started from, a
  revision with the change's own files uncommitted, a commit the repository's history
  dates after the run, a branch, or nothing at all. The table above says which of them
  still leave their code unidentified.
- **Workload source and substitution are separate fields.** 5 records use a
  synthetic workload; 8 have a claim-material substitution, and 1 more has a
  substitution recorded as immaterial. Neither field decides the other.

## How the hashes are taken

SHA-256 over the committed content. A text file — Markdown, JSON, JSON Lines, YAML,
CSV, or plain text — is hashed with CRLF normalised to LF, because the repository
stores text with LF and a Windows checkout rewrites it; hashing the checkout's bytes
would give two answers for one committed file. Anything else is hashed as it is. A
register entry is hashed as JSON with keys sorted, no insignificant whitespace, UTF-8.

The **git blob name** is the object name git gives the committed content — SHA-1 over
`blob <length>`, a NUL byte, and the content in its LF form — which is what
`git ls-files -s` and `git ls-tree` print. A test checks every one against what git
holds, so a release commit can be compared with the index without trusting a checkout.

The hash of a historical record that carries a correction is also written into the
ledger beside the correction, so the claim that the record was left as it was written
is checked, not asserted.

## Commands

```text
python -m tools.evidence_index            # the summary counts
python -m tools.evidence_index --print    # the whole index, written nowhere
python -m tools.evidence_index --check    # compare the committed index; exit 1 on drift
python -m tools.evidence_index --write    # regenerate it
python -m tools.evidence_index --gate     # the release gate and the freeze; exit 1 while a blocker stands, one is unaccounted for, or the index is stale
```

Every mode reads files. None contacts a cluster, a runtime, a model, or the network.

## What this index does not establish

- **That any record is right.** The index copies what the register says and hashes
  what the records are. Whether a level, a limitation, or a citation is the right one is
  a reading, and [the publication report](testing/v1-s5-013-pr2-publication-and-freeze.md),
  [the closure report](testing/v1-s5-013-pr1-blocker-closure.md),
  [the completeness report](testing/v1-s5-006-pr2-evidence-completeness.md),
  [the normalization report](testing/v1-s5-006-pr1-evidence-normalization.md), and
  [the migration report](testing/v1-s5-012-pr2-migration-report.md) are where the
  readings are.
- **That the frozen evidence is right.** The freeze binds the pack's files to their
  content; it says nothing about whether a file should have said more, and the
  corrections beside dated records are what later reading found. No release exists:
  a freeze is what `V1-S5-008` may quote, not a release.
- **That a revision the index lists as stated is the tree that ran.** It is the record's
  own word, quoted, as a content pin is. The index distinguishes the words a record
  used; it cannot re-run a build to check them.
