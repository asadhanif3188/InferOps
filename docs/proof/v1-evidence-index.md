# The V1 evidence index

Status: **generated, and checked against its sources on every run of the suite.** The
index is [`v1-evidence-index.v1alpha1.json`](v1-evidence-index.v1alpha1.json), produced
by `python -m tools.evidence_index --write` from
[the claim and evidence register](../testing/claim-evidence-matrix.v1alpha2.json) and
[the `V1-S5-006-PR1` normalization ledger](testing/v1-s5-006-pr1-normalization.v1alpha1.json).
It states nothing either of them does not, and
[`tests/testing/test_evidence_index.py`](../../tests/testing/test_evidence_index.py)
regenerates it and fails on any difference.

The register is organised by claim, which is the right shape for deciding what may be
said. A release needs the other view as well: **one entry per evidence record**, saying
what ran, what was substituted, where, at which revision, with which immutable
identifiers, and which committed files hold the evidence — each file bound to its
content by a hash, so that a file changed after the index was written is caught rather
than trusted. That is this index. [The proof dashboard](dashboard.md) answers *what has
been proven*; this answers *what exactly is the evidence, and can it be pinned*.

> [!IMPORTANT]
> The levels in this index are the register's, defined by
> [the evidence-level specification](../testing/evidence-levels.md). They are
> project-defined, and they are not an ISO, NIST, regulatory, or industry
> certification standard. Nothing in this index raises a level or promotes a claim;
> it has no field that could.

## What one entry holds

For each of the **57 evidence records** in the register:

| Field | What it says | Where it comes from |
|---|---|---|
| `claimId`, `claimStatus`, `evidenceLevel` | The claim the record supports, the claim's status, and the record's own level | The register |
| `registerPointer`, `registerEntrySha256` | Where the record sits in the register, and a SHA-256 of its entry in canonical JSON | Computed from the register |
| `execution` | Whether the claim's target behaviour ran, the components that executed, and every substitution with its kind and whether it is claim-material | The register |
| `workload` | The input's source, whether the record declares it representative, and its shape where recorded | The register |
| `environment` | The environment, provider, hardware class, and region | The register |
| `identifiers` | Every immutable identifier the record pins, grouped by kind: commit, image digest, model revision, artifact hash, chart version, package version | The register, which a test holds verbatim to the cited files |
| `codeRevision` | For a record that executed its target behaviour: every repository revision it names, and how that revision relates to what ran | The ledger's reading of the cited files, each quoted verbatim |
| `procedure`, `acceptanceCriteria`, `observationPeriod`, `results` | How to repeat it, what was registered and whether before the run, when it was observed, and what it found, failures included | The register |
| `limitations`, `doesNotEstablish` | The record's own boundary | The register |
| `evidence` | Every cited file: its path, its SHA-256, the date the file gives for itself and the words it uses for that date, whether it has an authorisation section, and any correction recorded beside it | Read from the file; corrections from the ledger |
| `findings` | The normalization findings that concern the record | The ledger |

Claim entries carry the statement, status, limitation, `doesNotEstablish`, the
declared claim-material components, the levels the claim's records reached, and the
record identifiers. A summary block carries the counts below.

**What an entry does not hold.** No record in this repository names an owner, so the
index has no owner field and does not invent one. A date is taken only from a line the
file itself writes — `Date:`, `Date captured:`, `Date produced:`, and so on, with the
label kept, because a record produced on one day may describe a run on another — and
never from a filename or from git; a JSON result file carries no such line and gets
none.

## What the index shows today

- **57 evidence records** under 59 claims: 26 at `C0`, 6 at `C1`, 25 at `C2`, and none
  at `C3` or `C4`. Every one of the **42 certified claims** holds at least one record,
  and every record states its limitations and what it does not establish.
- **67 distinct committed files** are cited, all under `docs/proof/`, each hashed.
  Nine of them carry a correction recorded beside them rather than inside them.
- **31 records executed their target behaviour, and 13 of them name the repository
  revision that ran.** The other 18 name the base their working tree started from, a
  revision with the change's own files uncommitted, a commit the repository's history
  dates after the run, a branch, or nothing at all. For several of those the code that
  ran is pinned another way — a built image by digest, or the hashes of the files that
  decided the run — and the entry's `identifiers` shows which. Whether V1 freezes with
  those 18 as they are is the open decision the normalization carried to
  `V1-S5-006-PR2`; this index records the gap and does not close it.
- **Workload source and substitution are separate fields.** 5 records use a
  synthetic workload; 6 have a claim-material substitution, and 1 more has a
  substitution recorded as immaterial. Neither field decides the other.

## How the hashes are taken

SHA-256 over the committed content. A text file — Markdown, JSON, JSON Lines, YAML,
CSV, or plain text — is hashed with CRLF normalised to LF, because the repository
stores text with LF and a Windows checkout rewrites it; hashing the checkout's bytes
would give two answers for one committed file. Anything else is hashed as it is. A
register entry is hashed as JSON with keys sorted, no insignificant whitespace, UTF-8.

The hash of a historical record that carries a correction is also written into the
ledger beside the correction, so the claim that the record was left as it was written
is checked, not asserted.

## Commands

```text
python -m tools.evidence_index            # the summary counts
python -m tools.evidence_index --print    # the whole index, written nowhere
python -m tools.evidence_index --check    # compare the committed index; exit 1 on drift
python -m tools.evidence_index --write    # regenerate it
```

Every mode reads files. None contacts a cluster, a runtime, a model, or the network.

## What this index does not establish

- **That any record is right.** The index copies what the register says and hashes
  what the records are. Whether a level, a limitation, or a citation is the right one is
  a reading, and [the normalization report](testing/v1-s5-006-pr1-evidence-normalization.md)
  and [the migration report](testing/v1-s5-012-pr2-migration-report.md) are where the
  readings are.
- **That the evidence is complete or frozen.** It is the input to that decision, which
  is `V1-S5-006-PR2`'s. A hash binds a file to its content today; it says nothing about
  whether the file should have said more.
- **That a revision the index lists as stated is the tree that ran.** It is the record's
  own word, quoted. The index distinguishes the words a record used; it cannot re-run
  a build to check them.
