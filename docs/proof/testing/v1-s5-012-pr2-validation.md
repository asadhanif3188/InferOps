# V1-S5-012-PR2 validation: migrating V1 evidence and the public proof surfaces

Date: 2026-09-23

Change: the claim and evidence register moves from `v1alpha1` to `v1alpha2`, written
from a claim-by-claim reading of every record the `v1alpha1` rows cited; every consumer
of the register moves with it; the strategy data carries the current level names and
its `synthetic` class stops covering generated input; the certification document stops
publishing the superseded level table; the proof templates collect what a `v1alpha2`
record needs; and the audit is published as
[a report](v1-s5-012-pr2-migration-report.md) with
[a machine-readable record](v1-s5-012-pr2-migration.v1alpha1.json). This record says
what was run to validate the change, what it found, and what none of it supports.

**Evidence class: `local-static`; evidence level `C0`.** Every command this change
executed reads committed files, or files the suite writes into a pytest temporary
directory. **No cluster was contacted**, no runtime was started, no model was loaded,
and no record under `docs/proof/` was re-run or edited. The levels the migration
assigned describe how each *cited* record was obtained; this change obtained nothing new
about the system. The levels are project-defined, not an external certification
standard.

## What moved, and what did not

- **Moved:** [`claim-evidence-matrix.v1alpha2.json`](../../testing/claim-evidence-matrix.v1alpha2.json)
  is new and authoritative. One claim's status moved, from `certified` to
  `not-claimed`; one claim's `assertsRealBehaviour` flag moved to `true`, which makes the
  register stricter; eleven claims' limitation or boundary sentences were corrected.
  The strategy data's level names and meanings, and the `synthetic` class's meaning,
  moved. The proof dashboard page was regenerated.
- **Did not move:** no claim's identifier, area, statement, citations, or test, gate,
  and README references; [`claim-evidence-matrix.v1alpha1.json`](../../testing/claim-evidence-matrix.v1alpha1.json)
  is byte-for-byte unchanged; no record under `docs/proof/` other than the index, the
  dashboard, and the four templates is edited; no strategy identifier, rank, ceiling,
  scope flag, layer, lane, or gate moved; `contracts/`, `src/`, `charts/`, `deploy/`,
  `infra/`, and `scripts/` are unchanged.

## How the audit was done

The 59 claims were split into eight areas, and each area was read by an independent
reader who read every file its claims cite and drafted the migrated records under a
fixed method — the ten principles published in
[the report](v1-s5-012-pr2-migration-report.md#the-audit-method). Each draft was run
through a checker that applied the `v1alpha2` schema and every validator rule, and
required every command, every version identifier, and every quoted source to appear
verbatim in the file it names; all eight drafts reached zero problems. The maintainer
then reconciled the drafts: two cross-area disagreements were decided (the Sprint 1
closure run's provider, recorded as `unrecorded` because its file never names one, and
two component roles); one record that merged two runs in different environments was
split; one claim was demoted on a measurement; and every justification and correction
in the report was written by the maintainer, not a reader. Seven factual claims a
reader raised about specific records were checked against those records before the
report repeated them.

## Commands and results

`<results of the full suite, filled in from a run on the committed tree>`

## Checks not run, and why

- **No cluster or real-runtime lane.** The change reads and writes files; nothing it
  changes executes against a runtime, and no run was authorised or needed.
- **No hosted continuous-integration run is cited.** The branch is pushed for review;
  a hosted run, if one happens, is observed rather than recorded here.

## Limitations

- The levels in the register are readings. The validator holds every record consistent
  with its level and its claim's declaration; whether a declaration names the right
  components, whether a limitation is the right one, and whether a record is relevant
  to its claim are review judgements, and this change is one maintainer's review of
  eight readers' drafts.
- Records are as coarse as the `v1alpha1` rows made them: a claim citing two runs of
  the same kind in the same environment holds one record for both.
- The audit found defects in cited records and citations it does not fix; the report
  lists them.

## Authorisation

Not required. The change reads and writes committed files and contacts nothing outside
the repository.
