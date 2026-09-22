# V1-S5-004-PR1 validation — publishing the V1 security and observability methods

Change: [the V1 security method](../../security/security-method.md) and
[the V1 observability method](../../telemetry/observability-method.md), each with an
authoritative record beside it; a suite,
[`tests/testing/test_published_methods.py`](../../../tests/testing/test_published_methods.py),
that holds both records to the security baseline, the telemetry catalog, the alert
record, the claim and evidence register, and the committed workflow; and in-place
corrections to sixteen documents that had said things which stopped being true. This
record is what was run, what it found, and what none of it supports.

**Evidence class.** Everything this change asserts about the repository is
`local-static`: files read, compared, formatted, linted, type-checked, and driven
through suites that contact nothing. **No cluster was contacted.** No cluster was
created or selected, no release was installed, no model was downloaded, and no
inference request was sent. Every runtime fact the methods state is quoted from a record
made earlier and names that record. **No claim in
[the register](../../testing/claim-evidence-matrix.v1alpha1.json) gains, loses, or moves
evidence, and no control status or emission status moves.** The generated
[proof dashboard](../dashboard.md) is unchanged, because nothing it is generated from
changed.

One input is not `local-static` and is kept apart for that reason:
[the run list](v1-s5-004-pr1-hosted-runs.v1alpha1.json), which records what the
selected continuous-integration service **reported** about the default-lane runs on
`main`. It is a third party's statement, read through its public interface, and it
carries no evidence label from the register because every one of those labels
describes something this repository ran or calculated. It is the source for the
corrections below and supports nothing else.

**This is a documentation change.** No product behaviour was modified. `src/`,
`charts/`, `infra/`, `deploy/`, `scripts/`, `tools/`, and `.github/` are byte-for-byte
unchanged; the only executable file this change adds is a test.

## Part 1 — what the two methods are

Each method walks a fixed list of topics, and every topic has two tables:

- **Implemented** — a control whose derived status may be called implemented, or an
  item a certified claim covers. Each row names at least one test or gate **and** at
  least one committed record, and carries an evidence label from the register's
  vocabulary.
- **Not implemented** — a control that is review-enforced, specified only, or deferred,
  a register entry, an uncertified claim, a metric nothing emits, or a gap the record
  declares. Each row says what may not be claimed while it stands.

The security method has ten topics, 20 implemented items, and 19 items that are not.
The observability method has nine topics, 13 implemented items, and 12 that are not.
(The first draft of this paragraph said 19 and 20, and 13 and 13, and 186 references
below; each was typed before it was counted, and each is now read from the records.)
The topics are the subjects the story asks a V1 method to cover; the suite fixes the
list, so a record that dropped one would fail rather than read as complete.

**What decides which table a row is in.** Not the author. For every control a security
row names, the suite reads the baseline's derived status and requires implemented rows
to hold only statuses the baseline marks `mayBeCalledImplemented`, and the other table
to hold none. For every metric an observability row names, it reads the catalog's
`emission` field the same way. A row in the implemented table that rests on a claim the
register does not certify fails; so does a gap that rests on one it does.

**What the suite resolves.** 141 evidence references across the two records: a test
reference must name a function defined in the file, a gate must be a job in
[the workflow](../../../.github/workflows/checks.yml), a record must be committed under
`docs/proof/`, and code or configuration must be a committed file. Five of those
references were wrong in the first draft of the security record — two that named a
test file under the wrong name, two test functions guessed rather than read, and a
manifest path that does not exist — and the resolution check is what found them. The first draft
also said the chart's integrity init container compares the hash, citing only the
baseline test, which reads the feasibility apparatus and not the chart; the chart's own
test and the V1-S3-008-PR1 record are now cited beside it.

**Coverage.** All 38 controls, all 12 register entries, all 6 exceptions, all 16
catalog metrics, and all 6 alerts appear. Each document names, section by section,
exactly the control, claim, metric, alert, register, and exception identifiers its
record holds for that topic, and links every record the topic's implemented rows rest
on.

## Part 2 — what writing them found

Every document the methods summarise was read against the repository. Five kinds of
statement had stopped being true. None was caught by a test, because none is the kind of
thing the existing suites read: they compare data to data and data to a table's first
column, and a paragraph beside the table drifts freely.

| Where | What it said | What is true | Since |
|---|---|---|---|
| `SECURITY.md`; `CONTRIBUTING.md`; the security README banner; the threat model banner; the claim and test matrix; `ADR-0008` "What must not be inferred"; `DR-11`; the baseline limitation `no-scanner-run` | No job in the default-lane workflow had executed on the selected service | The three scan gates passed there on all nineteen pushes to `main` from `f212090` to `4f3532a` | 2026-09-13 |
| The threat model's T-15 abuse case | "nothing makes the run recur" | The `secret-scan` gate recurs on every change | 2026-09-13 |
| `DR-08`, register document and data; the control matrix's host-scan paragraph | No continuous-integration lane existed and ADR 0005 D6 left the service undecided | ADR 0012 selected one and committed the workflow | 2026-09-12 |
| The control matrix, the paragraph after the documents table | The secret-scan control does not verify a scanner has run "because none has" | One run is recorded by hand, and the gate runs on every change | `V1-S4-001-PR1` |
| `EX-03`, document and data | A scanner run would miss the allowlisted paths "if one were ever run, which it has not been" | The same | `V1-S4-001-PR1` |
| `DR-11` and `DR-12` in the baseline data | The scanner was not installed and there was no lane; no logger, formatter, or sink existed | The register document had been narrowed by `V1-S4-001-PR1` and `V1-S1-008-PR1` and the data had not. The data is the authoritative form, so it was the stale half, and the suite that compares the two reads only identifiers | `V1-S1-008-PR1`, `V1-S4-001-PR1` |
| `DR-12` in the register document; `ADR-0006`'s amendment; the redaction rules; the API instrumentation document | No record had been produced against a real runtime | Three committed files from two runs quote records the API wrote with the real adapter: the first attempt of the V1-S2-005 local baseline, and V1-S4-007-PR1's diagnostics and record. No suite reads one for content, which is the part that stays true | 2026-09-03 |
| The register table's `DR-12` row, and the baseline's `DR-12` statement | "Nothing is logged, so nothing can be reconstructed" | The entry's own heading already said records are written and nothing keeps them | `V1-S1-008-PR1` |
| `DR-11`'s title, in the table, the heading, and the data | "No run of a secret scanner over this history is recorded" | One run is recorded, two paragraphs below the title | `V1-S4-001-PR1` |
| `ADR-0008` D6 and its "What it does not change" paragraph; the baseline's `T-06` residual risk and the `whatItDoesNotVerify` of `no-secret-or-content-has-a-telemetry-placement` | No logger, formatter, or sink existed, no log line had been inspected, "nothing is logged" | The API writes records and its suites read them back; what stays true is that they read only the mock's, and that nothing keeps a record | `V1-S1-008-PR1` |
| `ADR-0009`, "What it does not decide" | "no scanner is configured and no cadence is set" | That record configured no scanner; `V1-S2-006-PR1` added one and ADR 0012 runs it as a gate. No cadence is set, which stays true | `V1-S2-006-PR1` |
| The CI gate matrix's "What is not here" row for this correction | "Not scheduled" | Done here. Its data was updated in the first commit and its document was not, which made the two disagree | this change |
| The telemetry index's status paragraph | The two rendered rule files were something "nothing has loaded" | The pinned collector's own `promtool` loads both, and a test has run it since `V1-S4-008` | 2026-09-17 |

Every one is corrected **in place with the date the sentence was replaced**, so a reader
arriving from an old link finds the correction rather than a silent edit. `ADR 0008`'s
correction is marked as an amendment of a statement of fact and says the decision is
unchanged. [The CI gate matrix](../../testing/ci-gate-matrix.v1alpha1.json) had
recorded the first row as a debt it would not pay inside a CI change; that entry now
names this change as where it was paid.

**Two titles changed, and no identifier did.** `DR-11` is now "No recurring run of a
secret scanner is recorded" and `DR-12` is "Records are written and nothing keeps them,
so nothing can be reconstructed", in the table, the heading, and the data. Neither entry
was retired or narrowed in what it defers: `DR-11` still blocks nothing and still keeps
`no-credential-or-model-artifact-enters-public-history` planned, and `DR-12` still
blocks production use.

**The retired sentences are now refused.** The suite searches twenty governed
documents for thirteen retired phrases and fails on any of them. That guard found the row
above the telemetry index's: the first draft of this change corrected `DR-12` and missed
the same stale sentence in two places in ADR 0008 and two fields of the baseline data,
and the guard's first run over the finished draft failed on them. Evidence records and the
changelog are not searched: both describe a moment that has passed, and rewriting one to
match today would be falsifying a record rather than fixing a document.

## Part 3 — how the hosted runs were read

On 2026-09-22 the GitHub Actions REST API was asked, without authentication, for the
workflow runs of this repository on branch `main` with event `push`, and then for the
jobs of each run. It returned nineteen runs of the `checks` workflow, from `f212090` on
2026-09-13 to `4f3532a` on 2026-09-21, every one concluding `success`.
[The run list](v1-s5-004-pr1-hosted-runs.v1alpha1.json) carries each run's identifier,
head commit, creation time, and conclusion, and every job's name and conclusion.

| Job | Runs it appeared in | Concluded `success` |
|---|---|---|
| format, lint, and types | 19 | 19 |
| default-lane test suite | 19 | 19 |
| expected-failure controls | 19 | 19 |
| documentation links and whitespace | 19 | 19 |
| distribution build | 19 | 19 |
| API container image | 19 | 19 |
| dependency and image vulnerability scan | 19 | 19 |
| software bill of materials | 19 | 19 |
| secret scan | 19 | 19 |
| Helm chart and rendered manifests | 18 | 18 |
| Terraform format, validation, and lint | 18 | 18 |

The two infrastructure jobs are absent from the first run because `V1-S4-001-PR2` added
them after it.

**What this is not.** No log, scan output, finding, or artifact was read — only the
conclusion the service reports per job. It is not a promotion under ADR 0005 D5, it
certifies nothing, and it does not say any scan is clean today: two of these gates block
on a vulnerability database that moves daily. Pull-request runs were not read.

## Part 4 — what this change leaves open

Recorded rather than fixed, because each belongs to a different boundary than this one:

- **The CI gate matrix, ADR 0012, the README's test-strategy row, and the claim
  register's CI row still say the two infrastructure gates have never run on the
  service.** The run list above shows each passing eighteen times. That is a correction
  to the CI records and their claim, and the claim register and the generated dashboard
  would move with it; it is left to a change whose subject is the CI lane. This change
  corrects only the security records' statements about the scan gates, and phrases them
  so they do not contradict what the CI records still say.
- **`EX-03`'s revisit condition was met and not acted on.** `V1-S4-001-PR1` recorded a
  scanner run, and the allowlist still covers two directories wholesale. The exception
  now says so. Narrowing the allowlist changes scanner configuration and is not a method.
- **A tool docstring carries the same stale sentence as the telemetry index.**
  `tools/telemetry_collection/__init__.py` says no collector is selected and that an
  accepted configuration is one "nothing has loaded". It is left untouched so that no
  file under `tools/` changes in a documentation change.
- **The AI attributes follow no published convention.** No mapping to the OpenTelemetry
  generative-AI semantic conventions is recorded. The observability method names it as a
  gap; deciding one is a catalog decision under ADR 0006.
- **Cost.** The story's criterion that a cost estimate cannot be mistaken for billing
  belongs to `V1-S5-004-PR2`, which publishes the cost and capacity method. Nothing here
  implements it early; the observability method says only that cost is not something
  this telemetry produces.

## Part 5 — checks run

Run from Git Bash on one Windows host, against the working tree with every change
committed.

| Command | Result |
|---|---|
| `uv run --locked python -m pytest tests/testing/test_published_methods.py -q` | 281 passed (276 at the first commit, before the review widened the guard) |
| `uv run --locked python -m pytest tests/security tests/telemetry tests/testing -q` | 6274 passed (6269 at the first commit) |
| `uv run --locked python -m pytest -q` | 12439 passed, 33 skipped, 14 deselected, in 19 min 56 s (12434 at the first commit). The skips are the existing ones that need a pinned image, a tool, or a host capability absent here, including both `promtool` checks: the pinned collector image is not pulled on this host, so this change did not re-establish that the rule files load, and the methods quote that fact from the V1-S4-008 record |
| `uv run --locked ruff format --check .` | 470 files already formatted, after `ruff format` reformatted the new suite once |
| `uv run --locked ruff check .` | All checks passed |
| `uv run --locked python -m mypy` | Success: no issues found in 261 source files |
| `git diff --check` | clean |

Not run: anything that needs a cluster, a model, or the network, because nothing here
touches one. The run list is the one network read this change made, and it is described
above rather than repeated.

**Private-information inspection.** The full diff was read for planning material,
prompts, host paths, host names, credentials, and tenant identifiers. Nothing was found: no planning document, prompt, filesystem path, host name, user name, or credential. The run list carries run identifiers, commit hashes, timestamps, and conclusions, and deliberately not the actor who triggered each run.

## Part 6 — acceptance status

| Criterion | Status in this change |
|---|---|
| Implemented controls and deferred risks are separate | **Met**, and enforced: the side of the line is derived from the baseline's status and the catalog's emission field, not chosen |
| Telemetry semantics and dashboard interpretation are clear | **Met** for V1: the four panel states, why a zero is a count and never a rate, scrape reachability kept apart from readiness, and what each alert cannot see. Whether a reader finds it clear is a review question no test answers |
| Prompt/response handling is documented | **Met**: the security method's section 8 and the observability method's section 2, over the redaction rules. The claim that no prompt reaches a log or a metric stays `planned` |
| Cost estimates cannot be mistaken for billing | **Not in this change.** `V1-S5-004-PR2` |
| All methods link to tests/evidence | **Met** for the two methods here: every implemented item names a resolving test or gate and a committed record, and every section links its records |

The parent story, `V1-S5-004`, is **not complete**: its cost and capacity method is
`V1-S5-004-PR2`.

## Part 7 — what the independent review found

An independent review read the first commit (`489b485`) against the repository before
anything was pushed. It recounted every figure the change introduces — the item counts,
the 141 references, the 38, 12, 6, 16, and 6 coverage totals, the nineteen runs and their
per-job counts, the inventory counts, and the three files from two runs — and every one
held. It confirmed that no path under `src/`, `charts/`, `infra/`, `deploy/`, `scripts/`,
`tools/`, or `.github/` changed and that nothing from the cost method was pulled forward.

It found three things the first commit got wrong, and all three were the exact failure
this change exists to remove:

- **`CONTRIBUTING.md` still said no job in the workflow had run on the service**, word for
  word the sentence the first commit corrected in six other places.
- **ADR 0006 still said no record had been produced against a real runtime** — the
  decision the observability method is published under.
- **The CI gate matrix's document and data disagreed because of the first commit.** Its
  data marked the security correction done; its document still said "Not scheduled".

It also noted that the corrected sentences did not link the run list they rest on.

Sweeping the repository for the same phrasings after that found two more the review had
not listed: the claim and test matrix, which said the same thing as `CONTRIBUTING.md`, and
ADR 0009, which said "no scanner is configured" in the present tense. So the first
commit's "eleven documents" was sixteen, its "six places" for the scan statement was
eight, and its real-runtime correction missed one document of four. All five are corrected
in place with the date. The guard now searches twenty documents for thirteen phrases,
covering each of them, and `SECURITY.md`, `CONTRIBUTING.md`, the claim and test matrix,
and the CI gate matrix now link the run list.

The lesson is the one the guard exists for, applied to the guard itself: the first
commit listed the documents it had already corrected as the ones to protect, so it could
not catch a document nobody had read.

## What none of this supports

That anything is defended, observed in operation, or ready for production use. A method
summarises records other documents own; a reference resolving says the named thing
exists and not that it is a strong check. Nothing here is an outside assessment.
