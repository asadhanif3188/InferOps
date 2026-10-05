# Reconciliation evidence

Status: **implemented, and executed on one provider.** `V2-S3-003-PR2` added
the `observe` operation of [the Application procedure](argocd-application.md),
the tool
[`tools/reconciliation_evidence`](../../tools/reconciliation_evidence/core.py), and
the boundary for a manual change on this page. On 2026-10-05, on the
`docker-desktop` provider, `observe` read one Application while the procedure
applied it, after the apply, and while the procedure removed it, in two runs.
[The record of the runs](../proof/environment/v2-s3-003-pr2-reconciliation-observation-run.md)
says what ran, including one aborted attempt. The operation was not executed on
`kind`.

The suites execute the operation against stub tools and give the tool
directories that they write. Those are `C1` and `C0`. The runs are `C2`, bounded
to one provider, one host, one day, and one commit.

> [!IMPORTANT]
> **What Argo CD reports is reconciliation evidence. It is not a caller outcome.**
> A commit, a sync state, and a health state say what the controller did and what
> it derives from Kubernetes objects. The only evidence that the workload serves
> a request is a request that a caller sent. No field of the record on this page
> is read from a caller, and no caller measurement reads this record.

| Property | Value |
|---|---|
| Collection | [`scripts/environment/argocd-application.sh`](../../scripts/environment/argocd-application.sh): `observe --samples COUNT --interval SECONDS --into NAME` |
| Collection reads | The Application, and the kind, name, and labels of the workload objects. It changes nothing in the cluster |
| Collection writes | A new directory, `.artifacts/argocd-application/observations/NAME/`. Git ignores it |
| Evidence tool | [`tools/reconciliation_evidence`](../../tools/reconciliation_evidence/core.py): `python -m tools.reconciliation_evidence DIRECTORY` |
| Evidence tool reads | The directory, and Git objects of this repository. It reads no cluster and writes nothing |
| Output | One JSON record, with the schema identifier `inferops.io/reconciliation-observation/v1alpha1` |
| Tests | [`tests/domain/test_reconciliation_evidence.py`](../../tests/domain/test_reconciliation_evidence.py), and the `observe` cases of [`test_argocd_application_procedure.py`](../../tests/architecture/test_argocd_application_procedure.py) |
| Validation record | [`v2-s3-003-pr2-validation.md`](../proof/environment/v2-s3-003-pr2-validation.md) |
| Run record | [`v2-s3-003-pr2-reconciliation-observation-run.md`](../proof/environment/v2-s3-003-pr2-reconciliation-observation-run.md) |

## The two steps

```text
the cluster
    |   observe: a bounded number of reads, each written as it was returned
a directory under .artifacts/
    |   python -m tools.reconciliation_evidence DIRECTORY
one record: what was reported, what was not, and what changed
```

The steps are separate on purpose. The collection is the only step that reaches
a cluster, and it runs behind the provider and target verification of
[the provider contract](local-cluster-provider-contract.md). It judges nothing.
The evidence tool reads files, so a test can give it every missing and
unavailable field without a cluster.

```sh
export INFEROPS_PROVIDER=docker-desktop
scripts/environment/argocd-application.sh observe --samples 30 --interval 2 --into drift-check-1
uv run --locked python -m tools.reconciliation_evidence .artifacts/argocd-application/observations/drift-check-1
```

## The collection

`observe` takes three options, and it has no default for any of them.

| Option | Bound |
|---|---|
| `--samples COUNT` | A whole number from 1 to 120 |
| `--interval SECONDS` | A whole number from 1 to 30. It is the wait after a sample, and not the time between two samples |
| `--into NAME` | Up to 63 lowercase letters, digits, and hyphens. It names a directory that does not exist yet |

The largest observation makes 240 reads and waits 119 times 30 seconds. The
operation does not bound the time that one read takes.

Each sample is two reads:

1. The Application, as JSON. An absent Application answers with no output.
2. The kind, the name, and the labels of each object in the destination
   namespace that carries the release label.

For each sample the operation writes what each read returned, and a status file
that says whether each read answered. **A read that fails is written as
`unanswered`, and its output is not kept as an answer.** The observation then
continues: an unanswered read is a sample. The operation writes an end file only
after the last sample.

`observe` does not require that the Application exists, and it does not require
the bootstrap marker. An absent Application is an observation. On a cluster
without the Application's resource type, the read does not answer. Each run
observed both: three samples of an absent Application, and two unanswered
samples on a cluster where Argo CD was not installed.

The two refusals of `observe` are in
[the refusal table of the procedure](argocd-application.md#refusals). Both come
before the target is verified, so a refused `observe` reads no cluster. The
first version of the procedure checked the directory after it had verified the
target, and it then printed that nothing was read.

## The record

```json
{
  "schema": "inferops.io/reconciliation-observation/v1alpha1",
  "collection": {
    "provider": { "state": "reported", "value": "docker-desktop" },
    "requestedSamples": 2,
    "completedSamples": { "state": "reported", "value": 2 },
    "complete": true
  },
  "samples": [
    {
      "index": 1,
      "observedAt": { "state": "reported", "value": "2026-01-01T00:00:01Z" },
      "applicationRead": "reported",
      "fields": {
        "syncStatus": { "state": "reported", "value": "Synced" },
        "resolvedRevision": { "state": "reported", "value": "1234567890abcdef1234567890abcdef12345678" },
        "healthStatus": { "state": "missing" },
        "operationPhase": { "state": "reported", "value": "Succeeded" },
        "operationRevision": { "state": "reported", "value": "1234567890abcdef1234567890abcdef12345678" }
      },
      "notReported": ["healthStatus"],
      "settled": { "value": false, "reasons": ["healthStatus is missing"] },
      "objectsRead": "collected",
      "objectSet": "4f53cda18c2baa0c",
      "objectCount": 0,
      "consistency": { "state": "not-compared", "reason": "no provenance was asked for" }
    }
  ],
  "objectSets": { "4f53cda18c2baa0c": [] },
  "transitions": [],
  "summary": { "samples": 2, "samplesSettled": 0 },
  "doesNotEstablish": ["..."]
}
```

This example is shortened, and it is written by hand. It is not an observation.

### The read of the Application

| `applicationRead` | Meaning |
|---|---|
| `reported` | The read answered with one JSON object |
| `absent` | The read answered with no object |
| `unanswered` | The read did not answer |
| `unreadable` | The read answered with bytes that are not one JSON object |
| `not-taken` | The collection was asked for this sample and did not write it |

### The state of a field

| State | Meaning | Carries a value |
|---|---|---|
| `reported` | The object holds the field, with the expected type | Yes |
| `missing` | The object was read, and it does not hold the field, or holds a null | No |
| `malformed` | The object holds a value of another type, or an empty string | No |
| `not-collected` | No object was read: the read is `absent`, `unanswered`, `unreadable`, or `not-taken` | No |

### The fields

Five fields are required before a sample can be settled.

| Field | Read from | What it is |
|---|---|---|
| `syncStatus` | `status.sync.status` | Whether the controller found a difference between the commit and the cluster |
| `resolvedRevision` | `status.sync.revision` | The commit that the controller resolved the followed revision to. The observed revision |
| `healthStatus` | `status.health.status` | The health that the controller derives from the Kubernetes objects |
| `operationPhase` | `status.operationState.phase` | The phase of the last sync operation |
| `operationRevision` | `status.operationState.syncResult.revision` | The commit of the last sync operation |

The other fields do not change whether a sample is settled.

| Field | Read from |
|---|---|
| `repository` | `spec.source.repoURL` |
| `followedRevision` | `spec.source.targetRevision`. The desired revision. It is a branch name, and not an identity |
| `chartPath` | `spec.source.path` |
| `valueFiles` | `spec.source.helm.valueFiles` |
| `automatedSelfHeal` | `spec.syncPolicy.automated.selfHeal` |
| `automatedPrune` | `spec.syncPolicy.automated.prune` |
| `reconciledAt` | `status.reconciledAt` |
| `operationStartedAt` | `status.operationState.startedAt` |
| `operationFinishedAt` | `status.operationState.finishedAt` |
| `operationAutomated` | `status.operationState.operation.initiatedBy.automated` |
| `deletionTimestamp` | `metadata.deletionTimestamp` |
| `historyId`, `historyRevision`, `historyDeployedAt` | The last entry of `status.history` |

The record also holds the type and a bounded message of each condition, up to
ten, the message of the last operation, and three labels of each workload
object, up to 200 objects.

**Each distinct list of objects is held once.** Most samples of one observation
read the same objects with the same labels. `objectSets` holds each distinct
list under a name, which is the first 16 characters of the SHA-256 of the list's
JSON. A sample names the list that it read, as `objectSet`. A sample whose
object read did not answer names no list. A read that returned no object names
the empty list.

## A field that was not reported

**A missing field is missing. It is not healthy.**

- No function of the tool replaces a field with a default.
- Only the state `reported` carries a value. A test reads every field of a
  record for that.
- **A collection is complete only when it holds exactly the samples that were
  asked for.** A sample that is absent, a sample beyond the count, a status file
  that the tool does not read, and an absent end file each make it not complete.
- **A count is not given where nothing was read.** `objectCount` is null for a
  sample whose object read did not answer. Zero is a count.
- **`settled` reads five fields and the deletion timestamp, and nothing else.**
  It reads no condition and no queued operation, and it does not check the kind
  or the name of the object. An object without metadata is not settled.
- `settled` is true only when all five required fields are reported, the sync
  state is `Synced`, the health state is `Healthy`, the operation phase is
  `Succeeded`, the resolved revision is a full commit identifier, the last
  operation is at that revision, and the Application has no deletion timestamp.
  Otherwise it is false, and `reasons` names each condition that does not hold.
- A test builds every combination of absent required fields, 31 of them, beside
  settled values for the others. None is settled.
- The command exits 0 when it printed a record. **Exit status 0 does not say
  that the controller reported anything.** A record of unanswered reads is a
  record.

`settled` says what the controller reported. It is not a caller outcome.

## Transitions

A transition is a difference in one field between two consecutive samples. The
tool tracks eight fields: `syncStatus`, `resolvedRevision`, `healthStatus`,
`operationPhase`, `operationRevision`, `operationStartedAt`,
`operationFinishedAt`, and `historyId`. It also tracks the read of the
Application, as `applicationRead`.

- **A value is not carried across a sample that did not report it.** A reported
  value followed by an unanswered read is a transition to `not-collected`.
- **A sample that was not taken is not an observation.** No transition leads to
  a `not-taken` sample or from one.
- **A change of the objects alone is not a transition.** A sample names the list
  of objects that it read. The tool tracks no field of an object.
- **The interval bounds what a transition can show.** A state that began and
  ended between two samples leaves no transition. The time of a transition is
  known only as the two sample times around it.
- **A new operation is visible as a change of `operationStartedAt`.** The
  controller starts an operation when it applies a new commit, and when
  self-heal reverts a change. `operationAutomated` says whether the controller
  started it. Each run observed the first operation of a new Application, which
  the controller started. No sample has shown an operation for a later commit
  or for a reverted change.

## The comparisons

Given the commit that a sample reports, the tool reads
[the provenance](desired-state-provenance.md) of the desired-state release at
that commit. A sample for which it read one has the state `provenance-resolved`.
The tool then makes three comparisons, and each has a state of its own.

| Comparison | Compared | With | Rule |
|---|---|---|---|
| `revisions` | The revision of the last operation, and the revision of the last history entry | The commit the provenance was read at | `observed-revision-mismatch`, `revision-not-immutable` |
| `source` | The repository, the chart path, and the value files that the live Application declares | The release the commit holds | `source-not-the-release` |
| `labels` | The three provenance labels of each workload object | The labels the provenance derives | `workload-metadata-mismatch` |

**A comparison that could not be made is recorded as `not-compared`, with the
reason.** No comparison is recorded as consistent by default.

- A sample with no reported commit, and a commit that the clone does not hold,
  make no comparison at all.
- `revisions` is not compared when the sample reports neither of the two
  revisions. **The resolved revision is not compared.** The provenance was read
  at it, so that comparison would compare a value with itself. The first version
  of the tool made it, and reported a sample with no other revision as compared
  with no finding.
- `source` is not compared when one of its fields, or the followed revision, was
  not reported. The followed revision is a branch name, and it is not compared.
- `labels` is not compared when the object read did not answer, or returned no
  object. **When the read returned more than 200 objects, the state is
  `compared-in-part`,** and `objectsNotCompared` counts the rest. The first
  version of the tool reported those labels as compared.

The two revisions can be missing or different while an operation is in progress.
In the runs of 2026-10-05 they were missing in the first samples of an operation,
and never different.

## What the runs of 2026-10-05 observed

[The record of the runs](../proof/environment/v2-s3-003-pr2-reconciliation-observation-run.md) holds the samples of one aborted attempt and two
runs. Five observations bear on the rules of this page.

- **A new Application reported nothing for a time.** The object existed and held
  no sync state, no health state, and no operation, in six samples of run 2 and
  in thirteen samples of run 3. The first and the last of those samples are 19
  seconds apart in run 2, and 46 seconds apart in run 3. The tool holds each
  field as `missing`, and none of those samples is settled.
- **One sample of each run reported `Healthy` beside `OutOfSync`,** and the
  samples after it reported `Progressing`. The observation reads no pod state,
  so it does not show whether a pod was ready. The sample is not settled.
- **An Application with a deletion timestamp still reported `Synced` and
  `Healthy`,** in two samples of run 2. The tool that ran then counted both as
  settled. The tool now reads the deletion timestamp, and it counts neither.
  Run 3 has no such sample.
- **Every comparison with the provenance agreed.** In 61 samples of the
  observation beside the apply of run 3, the release objects carried the three
  labels that the provenance derives. In 62, the live Application declared the
  source of the release. No comparison on the cluster reported a finding.
- **In the aborted attempt, no sample is settled.** Argo CD reported `OutOfSync`
  and `Missing` beside a `Running` operation, and an operation message that
  names what it could not apply.

One caller request was sent in each run, between the observation after the apply
and the observation beside the removal. Each was answered, in 0.73 seconds and in
10.85 seconds. No sample was taken while a request was sent.

## Bounded diagnostics

**The record is built from an allowlist.** It holds the fields in the tables
above and no other part of an object. A test plants a marker in the inline
values, the parameters, the annotations, the managed fields, and the resource
list of an Application, and in two other labels of an object. The marker does
not reach the record.

- **Every text value is bounded.** A text field longer than 256 characters is
  `malformed`, and so is a list of value files with more than 20 entries. The
  kind and the name of an object are cut to 256 characters. The first version of
  the tool bounded a message only.
- **The user part of an address is replaced in every text value,** and a text
  value that the release domain's prefix heuristic calls credential-shaped is
  `malformed`. The first version of the tool copied a repository address with a
  credential in it into the record.
- **A message is one line of at most 240 characters.** A condition message and an
  operation message are cut. A word that the heuristic calls credential-shaped
  is replaced.
- **The redaction is a heuristic, and it has known gaps.** It knows only the
  prefixes it was given. It does not replace the user part of an address that
  has no `//` before it, or that holds a `/`. It does not know a value that
  follows `password=`.
- **The collection requests no Secret and no log.** The object read requests
  whole objects of ten kinds, pods and ConfigMaps included, and `kubectl` writes
  only the kind, the name, and the labels of each. No pod specification and no
  ConfigMap content is written to the directory.
- **The directory under `.artifacts/` is not evidence, and it is not
  committed.** The Application file in it is the whole object. It holds the
  hand-written values and the API image digest. The record is what a run
  commits.
- **The diagnostics of a failed `apply` are unchanged.** They are written under
  `.artifacts/argocd-application/`, and they are not committed either.

## The boundary for a manual change

On a cluster where the Application is applied, Git is the desired state, and
self-heal is configured. Each of the three runs of 2026-10-04 observed one change
to a replica count reverted. The runs of 2026-10-05 made no manual change.
[ADR 0019](../architecture/decisions/ADR-0019-argocd-application-and-sync-policy.md)
decided that an operator who must change a managed object by hand removes the
Application first, and it decided no break-glass procedure. This section states
the boundary. It decides no new mechanism.

**A manual `kubectl` change to an object that the Application manages is not
the release path.** It belongs to one of two cases: an experiment that froze
the change first, or a break-glass action.

| Rule | Statement | How it is held |
|---|---|---|
| `change-through-git` | A change to a managed object is a change to a contract, a binding, or the platform defaults. It is regenerated and accepted into `main` | review. Nothing prevents a `kubectl` change. Each of the three runs of 2026-10-04 made one change, and the Deployment declared its committed value again within 2 to 4 seconds |
| `experiment-mutation-is-frozen-first` | An experiment that changes a managed object by hand names the object, the field, the bound, and the revert in its frozen record before the run | review. No experiment with a manual change has a frozen record yet |
| `break-glass-removes-the-application-first` | Outside an experiment, an operator who must change a managed object by hand removes the Application first, with the procedure | not enforced. The removal deletes the workload objects, so this rule gives no way to change a running workload by hand and keep it running |
| `break-glass-is-recorded` | A break-glass action is recorded: who acted, when, on which object and field, why, and the commit that Argo CD reported before it | not enforced. No record format and no check exists. `observe` can collect the state before and after |
| `manual-change-returns-to-git` | After a break-glass action, the change is made in Git and accepted, or it is discarded. The procedure then applies the Application again | review |
| `controller-state-is-not-edited` | An operator does not edit the live Application or the live project, for example to turn automated sync off | tested: against stubs. `verify` compares the whole live spec with the committed manifest, and it finds an edit only when somebody runs it |

**Three rules of this table are in no decision record:**
`experiment-mutation-is-frozen-first`, `break-glass-is-recorded`, and
`manual-change-returns-to-git`. This document proposes them. ADR 0019 states the
removal rule without an exception, and the exception for a frozen experiment is
also proposed here. ADR 0019 still records that the break-glass boundary is not
decided. A decision record has to accept or change these rules before a
procedure depends on one.

**No admission control exists.** The operator's credential is the cluster
administrator's. The boundary is a rule for people, and review holds it. The
table says which part a test or a run holds.

**Suspending reconciliation is not decided.** No supported way exists to stop
Argo CD from reverting a change while the workload keeps running. Editing the
live Application to do that breaks `controller-state-is-not-edited`.

**The drift experiment is not this change.** A later experiment makes a bounded
manual change under its own frozen record, and it measures caller outcomes apart
from what Argo CD reports. The collection on this page is one of its inputs.

## Not applied yet

| Not applied | Why | What it needs |
|---|---|---|
| An observed transition for a later commit or a reverted change | Each run observed an apply and a removal of one commit, and made no manual change | A run that merges a change, or that changes the cluster under a frozen record, during an observation |
| An unanswered read beside a running Argo CD | Every read answered while Argo CD ran | An observation during a fault of the API server |
| A finding on a cluster | Every comparison on the cluster agreed | An observation of a state that disagrees |
| Records that a reader can build again | The directories that `observe` writes are not committed | A decision on which part of an Application an evidence record may hold |
| The time one read takes, bounded | `observe` bounds the count and the interval | A request timeout on the two reads |
| A sample of the hand-written values and the API image digest | They are not in the allowlist | A decision on which of them an evidence record may hold |
| The release identifier of the release document on an applied object | The renderer and the chart are pinned by the first experiment's freeze records | A freeze revision, then a generated value and a chart label |
| A record format for a break-glass action | Not decided | A decision record |
| A decision on the three proposed rules of the boundary | This document proposes them | A decision record |
| The acquisition job within its memory limit on Kubernetes v1.36.1 | One preparation of 2026-10-05 failed at the chart's limit. [The Application document](argocd-application.md#not-applied-yet) holds the row | An investigation, and a chart change under a freeze revision |
| A way to suspend reconciliation | Not decided | A decision record |
| `observe` on `kind` | No Application is declared for that provider | A release path for `kind` |

## What this does not establish

Every record carries these seven statements:

- That a caller request was answered. A sync state and a health state are what
  the controller reports. They are not a caller outcome.
- That a field with a state other than reported had any value. A field that was
  not reported is not healthy, not synced, and not unhealthy.
- What happened between two samples. A state that began and ended between two
  samples leaves no transition.
- That the controller applied the commit it reports, or that an applied object
  was rendered at that commit.
- That the reported commit is on a branch, or that a merge was reviewed.
- Anything about the API image or the hand-written values. Neither is read from
  the reported commit.
- That the record holds no secret. It is built from an allowlist of fields, and
  a message is cut and passed through a prefix heuristic.

This change also does not establish:

- **That `observe` works on another cluster.** It ran on one provider, on one
  Kubernetes version, against one Argo CD release.
- **That a read which fails beside a running Argo CD is recorded as
  unanswered.** That case ran against stubs only.
- **That another Argo CD release writes the fields at these paths.** In the runs
  of 2026-10-05, Argo CD 3.5.3 reported each of the nineteen fields of the two
  tables in at least one sample. No sample held a condition, so the reading of
  a condition was executed on directories that the suite wrote, and on no
  sample from a cluster.
- **That a manual change is found.** `verify` finds an edit of the Application
  or the project when somebody runs it. Nothing watches.
- **That the boundary is followed.** Review holds it.
- **Anything about `kind`.**

## Validation

```sh
uv run --locked python -m pytest tests/domain/test_reconciliation_evidence.py tests/architecture/test_argocd_application_procedure.py tests/architecture/test_argocd_application.py -q
bash -n scripts/environment/argocd-application.sh
uv run --locked ruff check . && uv run --locked ruff format --check . && uv run --locked mypy
```
