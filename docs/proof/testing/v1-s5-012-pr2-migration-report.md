# V1-S5-012-PR2: the V1 evidence migration, claim by claim

Date: 2026-09-23

This record is the audit that moved the claim and evidence register from `v1alpha1`,
which stored one superseded level per claim, to `v1alpha2`, where every evidence record
carries its own level under [the current definitions](../../testing/evidence-levels.md).
It says how each record was read, what each one turned out to be, every level that
changed and why, every sentence of a claim that was corrected, the one status that
changed, and what the reading found and did not fix.

The machine-readable form is
[`v1-s5-012-pr2-migration.v1alpha1.json`](v1-s5-012-pr2-migration.v1alpha1.json): for
every claim that cited a record, the eight audit questions answered from the cited
files with verbatim quotes, and for every record the outcome and, where its level
changed, the justification. The migrated register is
[`claim-evidence-matrix.v1alpha2.json`](../../testing/claim-evidence-matrix.v1alpha2.json);
the register it was migrated from is
[`claim-evidence-matrix.v1alpha1.json`](../../testing/claim-evidence-matrix.v1alpha1.json),
kept unchanged as the starting point. A suite,
[`tests/testing/test_evidence_migration.py`](../../../tests/testing/test_evidence_migration.py),
derives every count on this page from those three files and fails if the page says
something else.

**This record is `C0` evidence about the migration.** It is a reading of committed
files. No cluster was contacted, no runtime was started, and no record under
`docs/proof/` was re-run; the levels below describe how each *cited* record was
obtained, and this audit obtained nothing new about the system.

**The levels are project-defined.** InferOps Evidence Levels are not an ISO, NIST,
regulatory, or industry certification standard, and no outside party has reviewed the
readings below.

## Summary

| | |
|---|---|
| Claims in the register | 59, unchanged in identity, statement, and area |
| Claims holding at least one evidence record | 45 |
| Claims holding more than one evidence record | 9 |
| Evidence records | 54 |
| Records left `legacy-unmigrated` | 0 |
| Records whose level changed from the one their claim carried | 8 |
| Claim statuses changed | 1 |
| Claims whose own limitation or boundary text was corrected | 11 |
| Claims whose real-behaviour flag was corrected | 1 |
| Claim statements changed | 0 |
| Records at `C3` or `C4` | 0 |

Every one of the 54 records now states what executed, what was substituted, where its
input came from, where it ran and on what, how to run it again, the identifiers it
pinned or the record that names them, what it found, its limitations, and what it does
not establish — and every command and every version identifier it quotes appears
verbatim in a file it cites, which a test checks.

## The audit method

The register's 59 claims were divided into eight areas and each area was read by an
independent reader who drafted the migrated records for it; the maintainer reconciled
the drafts, decided every case the method below leaves open, and wrote every
justification on this page. A reader had to read **every file a claim cites, in full**,
before deciding a level, and answer eight questions per claim: what exactly is claimed;
which components material to it executed; what was substituted; what workload or input
was used; where it ran and on what hardware and provider; which level the evidence
satisfies under the current definitions and why not the next; its limitations and what
it does not establish; and whether the metadata is sufficient or the record must stay
unmigrated. Each answer quotes the file it rests on, and every quote was checked
verbatim before the answers were committed.

Ten principles were fixed for every reader, so that one register would not hold eight
readings of the same definitions. The answers in the machine-readable record cite them
by number.

- **P1. A level is claim-relative.** Decide the claim's target behaviour, then ask
  whether it executed and whether anything material to it was replaced.
- **P2. A claim about committed artifacts is `C0`.** A schema, a contract document, a
  data file, a manifest, a rule set, a guide, the agreement of documents with data, a
  scan of a pinned image — checked by a deterministic tool reading files. The target
  behaviour is the platform behaviour those artifacts govern, and it did not run. The
  tools that read them are recorded as having executed, as validators or tools only.
- **P3. Product behaviour that executed is `C1` or `C2`.** When the statement is about
  what InferOps code or the serving stack does, and that code ran, the record is `C1` if
  a claim-material component was substituted and `C2` if none was. A legacy `C0` moves
  only if the record shows the claim's own subject executing; the `local-static` class
  ceiling is why a legacy level may understate, never itself a reason to move.
- **P4. The labelled mock is a substitution** of the real adapter, the runtime, and the
  model, and is material wherever the statement depends on what the serving path
  returns.
- **P5. Workload origin decides nothing.** A generated prompt set is a workload source,
  never a substitution, and cannot put a record at `C1`.
- **P6. No `C3`, no `C4`.** A reader who believed a record met `C3` classified it `C2`
  and argued the case; the maintainer decided. None was accepted, for the reasons below.
- **P7. One record per claim by default,** split only where the cited files reached
  different levels for that claim or were independent runs in different environments,
  because a record has exactly one environment. A single journey through several
  environments stays one record.
- **P8. A claim holding a record at `C1` or above declares its claim-material
  components**, chosen from the statement rather than from what makes a record pass.
- **P9. A not-claimed claim's record is classified by what it actually did.** A refusal
  before anything ran did not execute the target behaviour; a measured refutation is
  evidence at the level it was obtained. The status never moves as a side effect.
- **P10. A record stays `legacy-unmigrated` only for a missing fact** the shape requires,
  and never gains one by inference.

The line P2 and P3 draw between them is the one judgement that decides most of the
register, and it is worth stating plainly. **A claim whose subject is committed
repository material, checked by repository tooling, is `C0`, even though a tool
executed.** The contract validator, the cost calculation, the alert evaluator, the link
check, and the strategy suites all ran, and every claim about them is about the files
they read. **A claim whose subject is InferOps product code in `src/` doing what the
statement says is `C1` or `C2`**, because that code is the target behaviour. The domain
parser and the scaffolding command are on that side of the line; the contract validator,
which its own record calls "contract tooling and not a platform component", is on the
other. A reader could draw the line elsewhere, and the list of judgement calls below says
where.

## Outcomes

Each record's outcome is derived by comparing its level in the migrated register with
the level its claim carried in `v1alpha1`, not taken from what a reader wrote.

| Outcome | Records | What it means |
|---|---|---|
| `retained-equivalent` | 43 | The record's level is the level its claim carried |
| `reclassified` | 8 | The record's level differs, justified by what it executed |
| `classified-from-no-legacy-level` | 2 | A not-claimed claim carried no level and cited a record; the record now has one |
| `added-by-the-migration` | 1 | The record did not exist before this change |
| `left-legacy-unmigrated` | 0 | A required fact was absent from the cited files |

**No record was left unmigrated.** Every record cited by a `v1alpha1` row names a
procedure — commands or a workflow — and a record that carries its versions, so the
fact P10 would have left out was present every time. Two records needed care rather
than omission: the Sprint 1 closure run names no cluster provider, and its two records
say `unrecorded` rather than borrowing `docker-desktop` from a neighbouring record.

### Levels the records reached

| Level | Records |
|---|---|
| `C0` | 25 |
| `C1` | 6 |
| `C2` | 23 |
| `C3` | 0 |
| `C4` | 0 |

## Every level that changed

Eight records sit at a level other than the one their claim carried. Three moved to a
higher-numbered level and five to a lower one. **None of the five lower ones weakened a
claim**: each was a weaker run that `v1alpha1` could not show, because it stored one
level per claim and a claim's strongest cited run set it. The claim's strongest record
is unchanged in every one of those five. The three higher ones are where the audit had
to be most careful, and each is justified by what the record shows executing.

| Record | Claim carried | Record now | Why |
|---|---|---|---|
| `the-workload-domain-parses-a-contract-document-into-typed-objects-c2` | `C0` | `C2` | The domain parser in `src/inferops/domain` is the claim's subject, and the records show it parsing every committed valid fixture, refusing unsupported versions, and applying the semantic rules, with nothing substituted. The `C0` was the unit layer's class ceiling. `C2` says the parser ran and nothing about a platform, which nothing builds |
| `a-workload-scaffold-is-generated-without-overwriting-anything-c2` | `C0` | `C2` | The scaffolding command is the claim's subject; the walkthrough ran both documented commands against a real file system and the suite ran the occupied-destination refusal unpatched. The one substitution is a writer stub the rollback tests inject, not material to the claim |
| `the-developer-quick-start-runs-end-to-end-on-a-clean-checkout-real-smoke-c2` | `C1` | `C2` | The claim's second clause says the real-runtime smoke was executed and recorded separately; the Sprint 1 closure run executed the API, real adapter, pinned runtime, and verified model with nothing substituted. `v1alpha1` recorded the weakest of three paths. The mock-workflow record stays `C1`, and this one says it did not exercise the quick start's scaffold commands |
| `the-model-lifecycle-states-were-measured-across-six-real-starts-cache-miss-c0` | `C2` | `C0` | The cache-miss observation started no runtime; its tools read the host's cache state. The six-start record keeps `C2` |
| `inferops-consumes-an-operator-owned-cluster-and-verifies-it-before-mutating-c0-contract` | `C2` | `C0` | A static suite over the provider contract that contacted no cluster. The paved-road run of the real guard keeps `C2` |
| `the-selected-runtime-serves-a-real-completion-in-a-cluster-c1-feasibility` | `C2` | `C1` | The feasibility trial served a real completion through hand-written trial manifests, not the Helm release and Terraform-owned claim the statement names, so both were substituted for this claim. The paved-road record keeps `C2` |
| `repeatable-llm-load-can-be-generated-from-a-versioned-profile-c1-stub-rehearsal` | `C2` | `C1` | The load tool's rehearsal ran against an in-process stub for the API, runtime, and model. The real load keeps `C2`; the deadline, transport-loss, and error classifications have met only the stub |
| `the-inference-operations-dashboard-was-asked-of-a-real-prometheus-and-rendered-c0-definition` | `C2` | `C0` | The definition's validation record states that no Grafana or Prometheus ran. The real run keeps `C2` |

Two not-claimed claims carried no level and cited a record; both records are now
classified, and **neither claim's status moved**:

- **`multi-replica-serving-is-certified` holds a `C0` record.** The workflow refused at
  the capacity gate before it installed anything, so the behaviour never ran. The record
  measures an absence of capacity and is not a weaker form of the capability.
- **`the-rendered-network-policy-is-enforced-by-the-cluster` holds a `C1` record.** The
  experiment observed a real cluster refuse nothing, but it applied a hand-written
  total-denial policy rather than the objects the chart renders, which the statement
  names. It is a measured refutation obtained with a substitute, and it stays visible
  exactly where the claim says the policy is not enforced.

## The status that changed

**`every-certifying-record-lives-under-docs-proof-and-declares-its-own-boundary` moved
from `certified` to `not-claimed`.** Its statement says evidence that certifies a claim
carries classification, provenance, environment, method, results, limitations, and
authorisation. Of the **52** Markdown records cited by the **43** claims the `v1alpha1`
register held as certified, **20** contain no statement about authorisation of any
kind, and the one record the claim cited checks the four templates, not any record
produced from them. The statement was kept and the status moved, for the reason the
claim-evidence template gives in its own words: a claim edited to fit its evidence is a
claim nobody tested. The count is a new record, held by the migration suite, which
recounts it from the frozen register on every run; twenty is a lower bound, because a
record that merely mentions the word is counted as carrying the section.

No status moved upward, and no other status moved.

## Claims whose own prose was corrected

A claim keeps its statement. Where its limitation or boundary said something the audit
found untrue — usually because the repository moved after the row was written — the
sentence was corrected, never widened. The before and after text of every correction is
in the machine-readable record.

| Claim | What was wrong |
|---|---|
| `inferops-is-a-portable-production-platform` | Stated the superseded meaning of `C4`, "not reachable because there is no second project"; it is unreachable because there is no organizational production |
| `eleven-default-lane-gates-are-committed-and-mapped-to-the-claims-they-defend` | Spoke of a "certification ceiling above `C1`", a class ceiling applied to records; a mock-backed record is `C1` because it substitutes the runtime |
| `the-published-strategy-and-its-data-cannot-drift-apart` | Said most layers have no code behind them; nine of the eleven exist |
| `no-resource-in-the-architecture-has-two-owners` | Counted thirty-five resources, thirty implemented; the inventory holds thirty-nine, thirty-four implemented |
| `the-model-artifact-matches-its-published-hash` | Said resumption was proved only synthetically and that the comparison ran on the host; both cited runs resumed for real and compared the hash inside a cluster |
| `the-selected-model-serves-a-real-completion-through-the-inferops-api` | Described one run and "nothing about a cluster" while citing a second run against a runtime in a cluster |
| `a-workload-scaffold-is-generated-without-overwriting-anything` | Said the walkthrough is what supports the row; it never tried an occupied destination, and the refusal rests on the suite |
| `multi-replica-serving-is-certified` | Said no multi-replica claim appears anywhere, in the row that is one; it means no certified one |
| `the-selected-runtime-serves-a-real-completion-in-a-cluster` | Described only the paved-road run while citing the feasibility trial as well |
| `a-mock-result-can-never-certify-real-runtime-behaviour` | Said a record nominates its own class; a `v1alpha2` record carries a level held to its claim's declaration |
| `every-certifying-record-lives-under-docs-proof-and-declares-its-own-boundary` | Did not say that the record it cites checks the templates rather than records produced from them |

**One flag was corrected, and it makes the register stricter.**
`the-developer-quick-start-runs-end-to-end-on-a-clean-checkout` now declares
`assertsRealBehaviour`. Its statement says the authorization-gated real-runtime smoke
was executed, which is an assertion about real behaviour; under `v1alpha1` the row's
`mock` label made the flag look consistent at `false`. Declaring it means the rule that
a real-behaviour claim holds a record at `C2` or above now reaches this claim, and the
claim satisfies it with the closure run's record.

## Judgement calls that could have gone the other way

These are the places a second reader could reasonably classify differently. Each is
recorded so that a disagreement can be had about a named decision rather than
discovered in a number.

- **The P2/P3 line.** The contract validator is `C0` and the domain parser is `C2`,
  although both are code that ran over committed fixtures. A reader who put the
  validator on the product side would move one more claim to `C2`; one who put the
  parser on the tooling side would move one back to `C0`.
- **The quick start's declaration.** It declares the API, the real adapter, the runtime,
  and the model material, and leaves out the scaffolding command, which is material to
  the claim's first clause. Declaring it would leave the real-smoke run unclassifiable
  for this claim, because that run never scaffolds. The cleaner fix is two claims, and
  splitting a claim is outside a migration.
- **Runtime materiality for the API.** The five-routes claim and the metrics claim
  declare the runtime material, which keeps both `C1`. A reader who read either as
  purely about the API's own contract would declare only the API, and the same records
  would be `C2` with the mock recorded as immaterial.
- **The network-policy declaration.** It declares the chart material, because the
  statement names the objects the chart renders. Declaring only the cluster would make
  the same refutation `C2`.
- **The alert replay.** It stays `C0`: the claim is about a replay by the repository's
  own evaluator over committed captures. A reader could call the evaluator a simulator
  of Prometheus and the record `C1`.
- **`C3`, argued and not accepted.** The unready-model experiment registered all four of
  its expectations before the run and measured all four, which is what `C3` asks of
  criteria. It declares nothing representative — a ten-millicore limit is an induced
  fault, not a representative condition — and its record says nothing in it is portable
  to another provider, host, replica count, model, or runtime configuration. The local
  serving baseline and the feasibility procedure registered thresholds first as well,
  and neither declares representativeness. All three are `C2`.
- **Records kept although they support little.** The dashboard's static definition
  record and the operator-cluster contract record are kept as `C0` records under
  claims they barely support, rather than dropped, because the migration moves
  citations and does not remove them. A reviewer may prefer to drop them.

## What the audit found and did not fix

The migration reclassifies and corrects; it does not re-run anything, and it does not
rewrite a record under `docs/proof/`. What the reading turned up beyond that is listed
here so that it is not lost, and each item is open.

- **Citations that do not support part of a statement.** The link claim rests on a
  2026-08-25 record that ran the contributor shell check rather than the suite the row
  names. The eleven-gates claim's "nine have passed on the service" rests on job
  conclusions read from a public API, which its own record says certify nothing until a
  run is promoted into a record. The manifest-refusal claim cites the paved-road record,
  which reads no pod against the rules. The installs-and-uninstalls claim's statement and
  record cover only the uninstall; the install is in a record the claim does not cite.
- **Claim identifiers that say more than their statements.** The Kubernetes diagnosis
  claim is named *published-and-executed*, and its cited records executed two of the
  four cleanup radii; the statement says *machine-checked*, which is what is supported.
- **Statements whose scope is narrower in the record.** The pod-loss statement says no
  person intervened; the record tabulates no intervention and says that "none" means
  nothing *in the workflow* intervened, not that nothing outside it did. The local
  baseline statement reads as though its fixture was registered before the run; the
  fixture that ran was rewritten after the registered one was refused, which the
  claim's limitation, and not its statement, discloses.
- **Record-level defects.** The domain `v1-s1-001-pr2` record's results line disagrees
  with its own evidence block on how many tests ran. The local-runtime troubleshooting
  record says every diagnostic exited `0` while its own table shows one exiting `5`, and
  it never ran the Linux branch of the processor-feature probe. The Sprint 1 closure
  run's response names the model `qwen3-1-7b-instruct` where the certification result
  names `qwen3-1-7b-q8-0`, and neither record explains the difference. The pod-restart
  record names a branch rather than a commit as its revision. The unready-model record
  was regenerated after the run and carries two descriptor digests; the migrated record
  pins the one that executed.
- **Evidence held outside the repository.** The collector claim's per-query results are
  in an ignored host directory rather than a committed record, and neither cited file
  records the collector's image digest.
- **An unexamined signal.** The clean-clone run's telemetry record returned one sample
  for a query the correlation suite expects to be empty in a healthy run, while the same
  record shows both scrape jobs up. The record still says `verified`. It does not change
  any level, and nobody has explained it.
- **Replay inputs not cited.** The alert-replay claim cites one of the three experiment
  records whose captures it replayed, and its captures step at fifteen seconds over a
  thirty-second scrape.

## What this migration changed, beyond the register

- **The strategy data's level names** in
  [`test-strategy.v1alpha1.json`](../../testing/test-strategy.v1alpha1.json) are the
  current ones, and **the `synthetic` class no longer covers generated input**: it names
  a simulated environment, which is a substitution, and keeps its `C1` ceiling for that.
  No layer and no gate uses the class, so no layer's ceiling moved. Identifiers, ranks,
  ceilings, and scope flags are unchanged, and no consumer compares the names.
- **Every consumer reads `v1alpha2`.** The proof dashboard renders each claim's records
  with their own levels, environments, providers, and substitutions, runs the
  register's evidence rules again before it renders anything, and shows every claim
  whose records now sit at a level other than the one it carried.
- **The certification document no longer publishes the superseded level table.** The
  mapping from each old meaning to the current one is in
  [the specification](../../testing/evidence-levels.md#what-this-supersedes-and-what-it-does-not)
  and in ADR 0016.
- **The four proof templates** collect claims, the evidence level, what executed, what
  was substituted, the workload, the environment, versions, procedure, acceptance
  criteria, results, observation period, limitations, and what a record does not
  establish, under the section headings every existing record already carries.

## Is `V1-S5-006` unblocked

Yes, with its inputs stated. The register is on the final model; every record carries a
level reached by reading it; the dashboard is generated from the register and cannot
promote a claim on its own; and no current surface presents `C0`–`C4` as an external
standard. What `V1-S5-006` inherits is listed above: records that are coarser than one
per execution, several claims whose citations or statements the audit questions, and no
record anywhere at `C3` or `C4`.

## Limitations

- The levels are readings. The validator holds each record consistent with its level
  and with its claim's declaration; whether a declaration names the right components,
  whether a limitation is the one that matters, and whether a record is relevant to its
  claim are review judgements, and this audit is one review by one maintainer.
- Records are as coarse as the `v1alpha1` rows made them. A claim citing two runs of the
  same kind in the same environment holds one record for both, and normalising records
  to one per execution is `V1-S5-006-PR1`.
- The authorisation count is a word match and a lower bound.
- The readers drafted from the cited files and nothing else. A fact that exists only in
  a record a claim does not cite was not used, which is why the closure run's provider
  is `unrecorded` although another record implies it.

## How to repeat the counts

Every number on this page, including the authorisation count, is recomputed from the
two registers, the machine-readable record, and the committed records by:

```text
uv run --locked python -m pytest tests/testing/test_evidence_migration.py -q
```

The suite reads files and contacts nothing. It fails if this page, the machine-readable
record, or the migrated register disagrees with what it recomputes.

## Authorisation

Not required. This audit read committed files and contacted nothing outside the
repository.
