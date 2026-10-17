# V2-S6-004-PR1 validation: the environment identity, and the corrected qualification path

Status: **the environment-identity decision is made, and the next qualification path is
frozen before it runs. No qualification or characterization ran.** [ADR
0021](../../architecture/decisions/ADR-0021-environment-identity-is-configuration-memory-is-capacity.md)
decides that the environment identity states the configuration and that memory is a
capacity fact. Three freeze revisions hold the next qualification, `q1-2`, and the next
Q2 and Q3 characterizations to the stable identity, and still hold each run to the
capacity gate on its own reading. `q1-1`, `q2-1`, and `q3-1` are built again unchanged
under the revisions they name, and `q3-1` stays `REFUSED`. No G and no Q4 bound record
exist, and `V2-S6-003` stays blocked. Evidence level C0 for the decision and the tools.
No claim is registered.

| Property | Value |
|---|---|
| Branch | `fix/v2-s6-004-environment-identity` |
| Base | `9c1cc120ef03b0cb9b236c92a8aa010c1227e42e`, the merge of `V2-S6-002-PR2` (pull request #150) |
| Decision record | [ADR 0021](../../architecture/decisions/ADR-0021-environment-identity-is-configuration-memory-is-capacity.md) |
| Freeze records | [`v2-q1/freeze-r2.v1alpha1.json`](../experiments/v2-q1/freeze-r2.v1alpha1.json), SHA-256 `add73e7e4e9ed20253b0e67734d463cf27f20d685014bae57c79ce241ea48d22`, 189 pinned inputs; [`v2-q2/freeze-r3.v1alpha1.json`](../experiments/v2-q2/freeze-r3.v1alpha1.json), SHA-256 `421628933641f8b7c064913c7af0b82d5f8663582e3dd1155a4ac2d8a6dc19af`, 194 pinned inputs; [`v2-q3/freeze-r2.v1alpha1.json`](../experiments/v2-q3/freeze-r2.v1alpha1.json), SHA-256 `f1ebcc296ebc81f0257e6b352f707dad6e635c46dbbd046dfc893eb8fc3f77ff`, 199 pinned inputs. All three registered by this change |
| Tools | [`tools/environment_qualification`](../../../tools/environment_qualification/core.py), [`tools/runtime_startup`](../../../tools/runtime_startup/core.py), [`tools/caller_characterization`](../../../tools/caller_characterization/core.py), and [`tools/experiment_bounds`](../../../tools/experiment_bounds/core.py) |
| Drivers | The Q1, Q2, and Q3 drivers name the new revisions. Their steps are unchanged |
| Suites | [`test_environment_qualification.py`](../../../tests/domain/test_environment_qualification.py), [`test_runtime_startup.py`](../../../tests/domain/test_runtime_startup.py), [`test_caller_characterization.py`](../../../tests/domain/test_caller_characterization.py), [`test_experiment_bounds.py`](../../../tests/domain/test_experiment_bounds.py), and [`test_experiment_freeze.py`](../../../tests/testing/test_experiment_freeze.py) |
| Runs | None. The next identifiers are `q1-2`, `q2-2`, and `q3-2`, and the next bound record is `v2-q4/bounds-r1.v1alpha1.json` |

## What the story asks of this change

`q3-1` was refused because the memory figure of its capacity reading differed from that
of `q1-1` by 12,288 bytes after the engine's virtual machine started again. No caller ran,
so G and the Q4 bounds are absent. The Q4 tool requires its Q2 and Q3 sources to state the
same provider, environment digest, release identifier, and qualification record, so no
later Q3 record can be combined with `q2-1` under a new identity.

This change decides what the environment identity states, implements it, and freezes
every affected step of the qualification path before another qualification runs. It runs
nothing. The next change of `V2-S6-004` runs the next qualification chain.

## The decision

[ADR 0021](../../architecture/decisions/ADR-0021-environment-identity-is-configuration-memory-is-capacity.md)
states it in full. In short:

| Question | Answer |
|---|---|
| What must the identity prove? | That two runs of one controlled comparison ran in the same configured environment, across what the experiment cannot control, such as a start of the virtual machine |
| Which inputs are stable identity facts? | The provider, the server version, each node with its kubelet version and the CPU and the pods that it allocates, and the CPU count of the engine |
| Which inputs are capacity facts? | The memory of the node and of the engine, read for each reading, and the gate's comparison of the declared limits and the reserve with it |
| Is the byte-exact memory figure identity? | No. It is a capacity fact. The stable identity holds no memory figure. No tolerance, rounding, or mask is applied to it |
| How is insufficient capacity still refused? | Q1-AC9 requires the gate's result `ACCEPTED`, and the Q2 and Q3 rules of the new revisions require it on each run's own reading, whatever its identity. A test runs the real gate on a copy of the `q1-1` collection with 8 GiB of memory: the gate refuses on `memory-limits-fit`, and the stable identity is unchanged |
| How do historical records rebuild? | Each tool builds a record under the freeze revision that its header names, with the qualification, the identity, and the rules of that revision |

The exact and the stable identities never share a digest: the stable one has the member
`identityRevision`, and the exact one has the two memory figures.

## What this change adds and changes

- **`tools/environment_qualification`.** `stable_environment_identity` states the stable
  identity. `environment_identity`, the exact identity, is unchanged. The tool registers
  revisions 1 and 2 of the Q1 freeze record (`FREEZE_RECORDS`, `REVISIONS`) and builds a
  record with the identity, the pins, and the list of what it does not establish of the
  revision that its header names. `identity_of` gives the identity of a Q1 revision.
- **`tools/runtime_startup` and `tools/caller_characterization`.** Each registers its
  revisions as lineages: Q2 revision 2 and Q3 revision 1 hold a characterization to
  `q1-1`, Q1 revision 1, and the exact identity; Q2 revision 3 and Q3 revision 2 hold it to
  `q1-2`, Q1 revision 2, and the stable identity. `environment-qualified` also requires the
  record of the qualification to be of the Q1 revision of the lineage. A record is built
  under the lineage that its header names, with its rules. This closes, for Q2, the gap
  that the Q2 page stated: a later revision no longer refuses `q2-1`.
- **`tools/experiment_bounds`.** It accepts a Q2 source of revision 3 and a Q3 source of
  revision 2. Its formulas and its comparison of the two sources are unchanged.
- **The three drivers.** Each names the new freeze revisions, and the Q2 and Q3 drivers'
  comments name `q1-2`. No step is changed.
- **Three freeze revisions**, each generated from the revision it supersedes, with every
  material file pinned and every moved pin classified.
- **Documents.** ADR 0021, the Q1, Q2, and Q3 pages, the experiments index, the
  architecture index, the decision-authority register, and the change log.

## Material-change inventory

| Revision | Moved pin | Material | Why |
|---|---|---|---|
| Q1 r2 | `tools/environment_qualification/core.py` | yes | The stable identity for revision 2, the exact one for revision 1, built under the header's revision |
| Q1 r2 | `tools/environment_qualification/__init__.py` | no | Exports only |
| Q1 r2 | `v2-q1/procedure/q1-driver.txt` | no | Names revision 2 |
| Q2 r3 | `tools/environment_qualification/core.py` | yes | As above |
| Q2 r3 | `tools/runtime_startup/core.py` | yes | The two lineages; `q1-2` and the stable identity for revision 3 |
| Q2 r3 | `v2-q1/freeze-r1.v1alpha1.json`, out; `v2-q1/freeze-r2.v1alpha1.json`, in | yes | The Q1 revision of the lineage |
| Q2 r3 | `v2-q1/runs/q1-1/record.v1alpha1.json`, out | yes | No longer the qualification. The record of `q1-2` does not exist yet, so it is not pinned; each characterization states its digest |
| Q2 r3 | the two `__init__.py`, the Q1 driver, the Q2 driver | no | Exports and revision names |
| Q3 r2 | `tools/environment_qualification/core.py`, `tools/caller_characterization/core.py` | yes | As for Q2 |
| Q3 r2 | `tools/experiment_bounds/core.py` | yes | Accepts the two new revisions |
| Q3 r2 | the Q1 freeze record and the record of `q1-1` | yes | As for Q2 |
| Q3 r2 | `tools/runtime_startup/core.py` | no | Q3 reads only its stream reader, which is unchanged |
| Q3 r2 | the three `__init__.py`, the Q1 driver, the Q3 driver | no | Exports and revision names |

The superseded revisions are kept unchanged. Their pinned inputs now differ: three for Q1
revision 1, six for Q2 revision 2, and nine for Q3 revision 1, each classified by the
revision that supersedes it. A run under a superseded revision is refused by the freeze
check of its driver.

## The historical records

No file under `docs/proof/experiments/*/runs/` is changed by this change, and no existing
freeze record is edited.

| Record | Revision it names | Result | Environment digest | `--check` |
|---|---|---|---|---|
| `q1-1` | Q1 r1 | `QUALIFIED` | `sha256:23db293eeac80960eb77eac228188ceb5ac2cd1c11a925636aa61f1318866461` (exact) | built again byte for byte |
| `q2-1` | Q2 r2 | `CHARACTERIZED`, S = 11,000 ms | the same, bound to `q1-1` | built again byte for byte |
| `q3-1` | Q3 r1 | `REFUSED` on `environment-qualified` | `sha256:ac3a1022e86facb519bb0820b57d7a7fb32c0c6ea1011a59e88b8c1aa4efd087` (exact) | built again byte for byte |

A test computes both identities of the committed capacity readings of `q1-1` and `q3-1`:
their exact digests are the two above, and their stable identities are one. This is the
observed drift under the decided semantics. It does not change `q3-1`, and it does not
make `q2-1` a source for a characterization of `q1-2`.

## Validation

All commands ran from Git Bash in the locked environment (`uv run --locked`).

| Check | Command | Result |
|---|---|---|
| Lint | `ruff check .` | clean |
| Format | `ruff format --check .` | clean |
| Types | `python -m mypy`, and again with `--platform linux` | clean on both, 430 source files |
| Driver syntax | `bash -n` on the three drivers | clean |
| Freeze records | `python -m tools.experiment_freeze --check` | PASSED, 12 records |
| Freeze changes | `python -m tools.experiment_freeze --changes` for Q1 r2, Q2 r3, and Q3 r2 | UNCHANGED for each |
| Committed qualifications | `python -m tools.environment_qualification --check`, `python -m tools.runtime_startup --check`, `python -m tools.caller_characterization --check` | PASSED, 1 each |
| Bound records | `python -m tools.experiment_bounds --check` | PASSED, 0 records |
| Evidence layout | `python -m tools.experiment_evidence repository` | 8 run directories: 3 qualifications with the text rules only (`q1-1`, `q2-1`, `q3-1`), 2 conforming, 3 pre-schema, 0 refused |
| Targeted suites | the four tool suites, `tests/testing`, and the decision-authority suite | 9,309 passed, 3 skipped, 1 failed: `test_analysis_replay` counted 9 committed freeze records, and there are 12. Its count and its docstring were corrected, and it passed |
| Default lane | `python -m pytest -q` | 22,803 passed, 42 skipped, 14 deselected, in 70 min, on the tree of this commit before this table's figures were written |
| Whitespace | `git diff --check` | clean |

The table above is the local validation of the first commit, and it stays as it ran.

## What the independent review found

An independent review read the first commit before the push. It ran the four `--check`
commands and two suites, and found no critical and no high finding. It confirmed that
every moved pin of the three revisions is classified, that `q1-1`, `q2-1`, and `q3-1`
rebuild under the revisions they name, that the capacity readings of all three have one
stable identity, and that the real-gate test is not vacuous.

| ID | Severity | Finding | What changed |
|---|---|---|---|
| M1 | medium | The first commit still said in two places, in the present tense, that the exact identity of `q1-1` is the selected environment of E02A and E02B, while two other places said it was so only until this change. A later freeze author could not tell which environment to name | The Q1 page and the experiments index now say that `q1-1` selects no environment since this change, and that the selection passes to `q1-2` only if it is `QUALIFIED` |
| L1 | low | The package docstrings of the Q2 and Q3 tools still said that the tools hold a run to `q1-1` | Each names both lineages. The two files are pinned, so the three revisions were generated again, after every correction below, and registered with their new digests: the digests in the table at the top are those of this second generation, and the first commit registered others. No run used either generation |
| L2 | low | The detail of a refused `procedure-frozen` in Q1 named only the current revision, although two are registered | It names both. A test holds it |
| L3 | low | The Q2 record stated the current freeze record when the header named an unregistered revision; the Q3 record states none | The Q2 record states none too. A test holds it |
| L4 | low | The docstring of a Q1 test said that `procedure-frozen` refuses a run under revision 1; the test held only that the freeze check lists a moved file | The docstring says what holds it: the driver, the freeze check, and the Q2 and Q3 revisions of the next lineage, which refuse a qualification that is not of revision 2. No Q1 rule refuses such a header on its own |
| L5 | low | The review read the Q4 lineage-mix test as also differing in the release identifier | No change: both lineages in that test state the same release identifier, and the existing refusal case "another environment" varies the environment digest alone |

After these corrections the affected suites ran again: the four tool suites, `tests/testing`, and the decision-authority suite, 9,314 passed and 3 skipped; ruff, mypy on win32 and linux, the freeze check (12 records), the three `--changes`, and the four `--check` commands were clean. The full local default lane did not run again.

## What is not established

- Why the engine and the node report other memory figures after each start of the
  virtual machine.
- That memory above the declared limits and the reserve has no effect on a startup
  interval or a caller gap.
- That `q1-2` will be `QUALIFIED`, or that a Q2 or a Q3 characterization of `q1-2` will be
  `CHARACTERIZED`.
- Any G, any Q4 bound, any result of a reliability experiment, or anything about another
  provider, node, Kubernetes version, or release.

## What the next change of this story must do

- Start from the merged revision of this change, with every freeze check unchanged.
- Run the next Q1 qualification once, as `q1-2`, under Q1 revision 2, and keep it whatever
  it shows. If it is not `QUALIFIED`, stop: no Q2 or Q3 run of this lineage follows it.
- Only after `q1-2` is `QUALIFIED`, run Q2 as `q2-2` under revision 3, and then Q3 as
  `q3-2` under revision 2, once each, and keep each.
- Only when `q2-2` and `q3-2` are both `CHARACTERIZED` with every rule held, build the Q4
  bound record `v2-q4/bounds-r1.v1alpha1.json` with the existing tool.

## The downstream state

`V2-S6-003` stays **BLOCKED**: no characterization of the next lineage exists, and no Q4
numeric bound record exists.
