# Pull request #103: out-of-band security maintenance, reconciled

Date: 2026-10-01

Classification: **documentation, `C0`.** This page records what one merged change
was, what it changed, and what a later change corrected in it. It was written from
that change's diff, its commits, and the records it published; nothing was executed
against a host, an image, or a cluster to write it. It certifies no published claim
and moves none.

The change is pull request #103, `fix(security): accept CVE-2026-84782 in the pinned
runtime image as EX-07`, merged into `main` on 2026-09-30 as `51cddd1` from two
commits, `1c9a686` and `98aa117`. It keeps that number, that title, and that history;
nothing here renumbers or rewrites it.

## What triggered it

On 2026-09-29 the vulnerability database gained `CVE-2026-84782`, a `HIGH`
out-of-bounds read in OpenSSL's DTLS handshake retransmission, in the `openssl` and
`libssl3t64` packages the pinned runtime image carries. On 2026-09-30 the
`dependency-and-image-scan` gate of the default-lane workflow failed on a pull request
that changed no image, no lockfile, and no script, and it would have failed the same
way on every branch, `main` included, from the next run. Nothing in the repository had
changed; what was known about the pinned bytes had.

## What kind of change it was

**Out-of-band security maintenance.** It was not one of the changes planned for the
first V2 sprint, and it adds no V2 capability: it renders nothing, records no release,
and touches no workload contract, published schema, domain package, chart, or manifest.
The one data shape it extended is the security baseline's, which gained one optional
field, below. It was made
because a gate that every change must pass had begun to fail for a reason outside the
repository, and it is recorded here as that rather than presented after the fact as
planned work.

## What it changed

| Area | Change |
|---|---|
| The exception | `EX-07` in [the security baseline](../../security/security-baseline.v1alpha1.json) and [the deferred-risk register](../../security/deferred-risks.md): one finding, `CVE-2026-84782`, in one image digest, owned by `security`, accepted on 2026-09-30 until 2026-10-30, with `pin-image-by-digest` as its compensating control. A baseline exception may now carry a `scanFinding` naming the finding, the image, the owner, and the deadline |
| The scan guards | `scripts/security/lib.sh` hands each scan its own committed ignore file and `--show-suppressed`, and refuses before scanning a missing ignore file, an entry that is not one identifier and an expiry, and an image exception assessed against any image but the pinned one. The runtime image's ignore file accepts `CVE-2026-84782 exp:2026-10-30`; the dependency scan's accepts nothing |
| Tests | `tests/security/test_vulnerability_scan_exceptions.py`, 29 tests, holds the ignore files and the baseline to each other in both directions and runs the guards against a recording stub. The baseline suite accepts the one optional field |
| Documents | [The assessment](ex-07-runtime-image-exception.md), the control matrix, the published security method and its data, the current counts in the README, `SECURITY.md`, the architecture index, and the register, the test inventory, the proof index, and the changelog. Four surfaces that said no continuous-integration service runs the scans were corrected: the two scan controls' statements of what they do not verify, in the baseline, and `docs/prerequisites.md` and the claim and test matrix, the last two each saying what it said before |

The guards' change also corrected a statement that had been false before it: both
scan controls said a guard blocks on a finding "not recorded as an accepted
exception", and neither had ever read one. The assessment records that correction.

## What it did not change

- **The runtime image.** The pin is the digest ADR 0002 selected, unchanged.
- **The severity policy.** Both guards still block on any `CRITICAL` or `HIGH` finding
  outside an unexpired entry, and a finding published after the assessment blocks like
  any other.
- **The other six exceptions**, the twelve deferred risks, and every control's
  derived status. The two scan controls' text changed, as above; their status did not.
- **The serving architecture, the evidence pack, and the claim register.** No evidence
  record pins a file this change touched: none names one as a script it ran by
  reference, a code identity, or an evidence path. Three records do name touched files
  in the text of the commands they ran - the scan record both scan scripts, one record
  the baseline suite, and one the inventory suite - and the register's test, implementation, and README references
  and its list of surfaces that claim nothing name others; none of those binds the
  file's content. The release gate prints the
  same released and current digests at #103's parent, at its merge, and at the change
  that restored the history below.
- **`v1.0.0`.** The tag and the release were not touched.

## Why the image was not rotated in that change

A patched upstream build existed and scanned with no `HIGH` or `CRITICAL` finding on
2026-09-30. Moving the pin to it was judged more than a change unblocking a gate
should carry: ADR 0002 selected the runtime at this digest and asks for a refresh
procedure the repository does not have yet, twenty-three evidence records across
sixteen claims name this digest as the runtime they measured, and roughly seven
hundred upstream builds separate the two images. (The assessment says twenty-three
records across seventeen claims. Recomputed from the claim register at #103's parent
and now, twenty-four records across seventeen claims name the digest: the twenty-three
that measured the runtime, and the scan record, which scanned the image rather than
measuring it.) Rotation is the remediation; the
exception holds the gate until it happens or until 2026-10-30, whichever is first.
[The assessment](ex-07-runtime-image-exception.md#why-the-pin-was-not-moved-instead)
gives the argument in full.

## The evidence and claim boundary

The assessment is local real evidence from one host on one day, plus a static reading
of the image's binaries; it certifies no published claim. No claim moved, in V1 or in
V2. No V2 capability, runtime, deployment, reliability, or production statement rests
on this change, and the exception is not a control: it is a recorded weakness with an
expiry the scanner applies.

## What it got wrong, and what was corrected later

**It rewrote V1 decision history in place.** ADR 0008 is an accepted V1 record. The
change replaced "Six exceptions are recorded" in `D11` and "six accepted exceptions"
in its consequences with "seven", so the record read as if `EX-07` had existed when
the decision was made. `V2-S1-004-PR2` restored both sentences to the wording
`v1.0.0` released and added a dated note after each that records `EX-07`, the date it
was accepted, and where the current count is kept.

**It had no record saying what kind of change it was.** Its commits and its
assessment say what it did and why, and nothing said that it was maintenance forced
by a new finding rather than planned work. This page is that record.

**One count it added to was already behind.** The test inventory's `documentation`
section lists, by change, which module each change added; this change added that
layer's forty-eighth module without extending the list. `V2-S1-004-PR2` extended it.

The surfaces that state the **current** register — the README, `SECURITY.md`, the
architecture index, the deferred-risk register, and the published security method and
its data — say seven, and seven is true. They were left as they are.

[`V2-S1-004-PR2`'s validation record](v2-s1-004-pr2-validation.md) says what was
restored, from which revision, and what was run to check it.
