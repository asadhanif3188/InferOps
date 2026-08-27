# V1-S0-012-PR1 change validation

What this record is: the checks run against the change that decided the V1 inference
API compatibility surface, with the exact command and result of each.

What it is **not**: evidence that the surface works. Nothing in this repository
listens on a port, registers a route, or answers a request, and no request was issued
to anything during this change. Every check below reads committed files.

## Classification

| Field | Value |
|---|---|
| Evidence class | **Repository-only machine check.** Committed files compared against each other and against records already committed beside them |
| What it may be cited for | That the decided surface is internally consistent, that it agrees with the runtime evidence and the telemetry catalog, and that the documents and the data publish the same thing |
| What it may **not** be cited for | Any behaviour of any API. No endpoint exists, no adapter exists, no request was served, and no measurement was taken |
| Ceiling | It cannot certify runtime behaviour, and it is not a mock result either — there is no mock. It is a consistency check over documents and data |

## Provenance

| Input | Value |
|---|---|
| Repository revision at branch point | `c35ecb6451c824fb7eac1a1d22e32b4d89234284` |
| Branch | `docs/v1-s0-012-inference-api-compatibility` |
| Runtime evidence read | [`v1-s0-003-pr2-runtime-feasibility.md`](v1-s0-003-pr2-runtime-feasibility.md), recorded 2026-08-24 |
| Runtime decision read | [ADR 0002](../../architecture/decisions/ADR-0002-model-and-serving-runtime.md) |
| Runtime image the evidence describes | `ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384`, build `b10588` |
| Model the evidence describes | `Qwen/Qwen3-1.7B-GGUF` at revision `90862c4b9d2787eaed51d12237eafdfe7c5f6077`, file `Qwen3-1.7B-Q8_0.gguf` |
| Python | 3.12.12 |
| uv | 0.9.16 |
| pytest | 8.4.2 |
| ruff | 0.16.4 |
| mypy | 2.3.1 |

Neither the runtime image nor the model was pulled, started, or contacted for this
change. They are named because the shapes this record decides were read from what
they returned on 2026-08-24, and a shape read from a specific build is only as
reproducible as the build is identified.

## Environment

| Field | Value |
|---|---|
| Host | The same Windows development host the repository's other records describe |
| Operating system | Windows 11 |
| Cluster | **None used.** No cluster was started, and no check below needs one |
| Network | **None used.** No check retrieves anything |
| Accelerator | None, and none required |

## Method

Commands in the order they were run, including the ones that failed.

### 1. Branch from the merged head

```sh
git checkout main && git pull origin main
git checkout -b docs/v1-s0-012-inference-api-compatibility
```

Result: fast-forwarded `46d0390..c35ecb6`, which brought in the V1-S0-011 toolchain
work. The branch was created from `c35ecb6`.

### 2. The serving-surface suite

```sh
python -m pytest tests/serving -q
```

Result on the first run: **4 failed, 174 passed**, from two distinct causes. Both
causes were real and are recorded here rather than repaired silently.

| Failure | What it found | What was changed |
|---|---|---|
| `test_an_observed_runtime_counterpart_appears_in_the_record[chat-completions]` | The surface claimed the trial observed `POST /v1/chat/completions`, and the **feasibility record does not contain that path**. The trial recorded the request and response bodies for that endpoint but never wrote the path; the path appears in ADR 0002's `T5` row instead | The check now reads the feasibility record **and** ADR 0002, which are the two sources the surface is permitted to read runtime behaviour from. Vendor documentation is still excluded, which is the property the check exists for |
| `test_the_document_publishes_every_capability_with_its_value` × 3 | The document publishes capabilities by the member name a response carries — `tokenUsage`, `deterministicSampling`, `multiModel` — and the check demanded the internal slug | The check now derives the member name from the capability's own `declaredAt` and looks for that, which is the name a reader needs |

Result after both changes: **178 passed**. A later independent review found a third
defect in this same suite and in the record it checks; both the finding and what it
changed are in [what a second review found](#what-a-second-review-found).

The suite reports **184 passed** after the second pass, up from 178: the two response
fields that stopped claiming observation removed two parameter cases, and the checks
the second pass added — for the capability decisions, the republished values, the
compatibility target's own fields, the telemetry pointer, and the surface's own
description — added eight.

The first of those two is the one worth keeping in view. The check was written to stop
the surface citing an endpoint that only vendor documentation says exists, and the
first thing it caught was this record over-attributing an endpoint to the trial log.
It was not a false positive; the citation was wrong, and widening the permitted source
to the two records the story's brief names is the narrowest correct fix.

### 3. The full default lane

```sh
python -m pytest -q
uv run --locked python -m pytest -q
```

Result: **2513 passed, 7 skipped** at the end, from 2506 before this change added a
suite. The skips are the pre-existing ones the default marker expression produces;
this change adds none. The `uv run --locked` form
is the recorded one, because it resolves nothing and runs against the committed
lockfile.

The default expression deselects `cluster`, `realruntime`, `failure`, and `load`.
**Nothing in this change is capable of running in any of those lanes**, and none was
skipped for want of a capable host: there is no code to exercise.

### 4. Linter, formatter, type checker

```sh
uv run --locked ruff check .
uv run --locked ruff format --check .
uv run --locked python -m mypy
```

Result on the first run:

- `ruff check`: **1 error.** `SIM300`, a Yoda condition in
  `test_every_required_serving_role_is_covered`. Fixed with `ruff check --fix`;
  re-run clean.
- `ruff format --check`: **1 file would be reformatted.** A `next(...)` call the
  formatter joins onto one line. Fixed with `ruff format`. The final re-run reports
  **87 files already formatted**, which is 71 Markdown files and 16 Python files —
  `ruff format` reads both, and the count moved from 86 to 87 when the Markdown file
  you are reading was added.
- `mypy`: **Success, no issues found in 16 source files**, first run and final run.

The suite was re-run after both fixes, and again after every change the second review
prompted. Final: **2513 passed, 7 skipped**.

### 5. Whitespace, tabs, and links

```sh
git diff --check --cached
git ls-files -z '*.md' | xargs -0 grep -n '[[:blank:]]$'
git ls-files -z '*.md' | xargs -0 grep -n "$(printf '\t')"
```

Result: no whitespace errors, no trailing whitespace in any Markdown file, no hard
tabs. `git diff --check` reported only Git's own CRLF-normalisation warnings for the
new files, which are the `.gitattributes` policy working rather than a finding.

The relative-link check in CONTRIBUTING was run over every tracked Markdown file:

```sh
git ls-files -z '*.md' | while IFS= read -r -d '' f; do
  d=$(dirname "$f")
  awk '/^[ \t]*```/ { fence = !fence; next } !fence' "$f" |
    grep -oE '\]\([^)]+\)' | sed 's/^](//; s/)$//' |
    while read -r t; do
      case "$t" in http*|mailto:*|\#*) continue ;; esac
      p="${t%%#*}"
      [ -n "$p" ] && [ ! -e "$d/$p" ] && echo "BROKEN: $f -> $t"
    done
done
```

Result on the first run: **three broken links**, all three pointing at this record
before it was written — from the architecture index, from ADR 0010, and from the
evidence index. Re-run after writing it: clean.

**No external link was added by this change**, so none was checked and none is
claimed as checked.

### 6. JSON parse

```sh
python -c "import json; json.load(open('docs/serving/inference-api-surface.v1alpha1.json'))"
```

Result: parses. The suite then reads the same file, so a malformed document fails at
collection rather than in one assertion.

## Results

### What the machine check establishes

Grouped by the failure each group exists to prevent.

| Property | Checks | What it stops |
|---|---|---|
| Nothing claims to be served | `implementationStatus` is `nothing-serves`; every endpoint's `servedBy` starts with `none`; both documents refuse the claim in prose; `contracts/` carries no artifact for this surface | The single most likely drift for a record that describes an API in detail: a reader, or a later author, taking the description for an implementation |
| Every canonical code is accounted for | Thirteen codes transcribed independently into the suite; each must be mapped or refused, never both, never neither; every refusal states a reason over forty characters | A code disappearing by being forgotten, which produces a shorter list and no error |
| A `retryable` value that differs from the default is argued | Each mapped row's `retryable` is compared against the canonical default and must carry `retryableOverride` exactly when it differs; the one override is asserted to be the streaming refusal | A consumer written from the specification's default column silently retrying a request that can never succeed, with nothing in either record marking the difference |
| Observation is distinguished from specification | An observed **field** must appear as a JSON member key inside a fenced block of the feasibility record; an observed **endpoint** must be named by that record or ADR 0002; an unobserved capability must cite no evidence; exactly one error row may claim observation and it must be the 503; no field of `/v1/models` may claim it at all; and the fenced-block extraction is itself asserted non-empty | A shape written from expectation being read as a shape read from a response — the distinction this whole record rests on, and the one a substring check was not strong enough to protect |
| Capabilities are declared, not assumed | Each declares a question, a value, where it is published, and what supports it; streaming is required to assert nothing about the runtime; the streaming value is compared against the deferral reason already in the telemetry catalog | Two accepted records disagreeing about whether V1 streams, and a capability flag with nothing behind it |
| The serving contract's roles are covered | The five required roles must each be covered by an in-scope endpoint; graceful shutdown must appear as a stated equivalent naming `SIGTERM` | A required role being satisfied by silence |
| Dropped runtime fields were actually seen, and say why | Each of the three names a string the feasibility record contains and states a reason; none may also be a response field | A field being dropped without a record of what it was or why |
| The counter the runtime lacks is bound to something that exists | The two gauge series must appear in the record that measured them; the metric and error metric must exist in the telemetry catalog; the error metric must be labelled by `error-code` | The `T7` compensation being asserted here and existing nowhere, or a mapping nothing can be grouped by |
| The three documents agree | Every endpoint path, every mapped and refused code, and every capability member name must appear in the document and the decision; the decision must carry the seven sections a record here requires | The data and the prose drifting apart, which is how a decision quietly becomes two decisions |
| The suite is reachable | The documentation layer of the test strategy must name `tests/serving`, and this module must declare that layer's marker | A suite no lane runs, which passes by never being collected |

**184 checks. All pass.**

### What it does not establish

- **That any of this is correct as a design.** The suite checks the record against
  itself and against its neighbours. A surface that is internally consistent and
  wrong passes every check here.
- **That the compatibility target is the right choice.** That is an argument, made in
  ADR 0010 and open to being attacked on its own terms. No test can settle it.
- **That the eight unobserved error rows are what the runtime does.** They are
  specifications. The lane that would provoke a real failure is deselected by default
  and has no code, and this record does not create one.
- **That the extension namespace, the response `x_inferops` member, or `adapterKind`
  behave in any way.** Nothing emits them.
- **Anything about latency, throughput, concurrency, or load.** No request was issued.

## What the diff was reviewed for

The full staged diff was read before this record was written.

| Looked for | Result |
|---|---|
| Private planning content — backlog, prompts, story text, future-project queues, positioning, unpublished strategy | **Two leaks were found on the second pass and removed.** See [what a second review found](#what-a-second-review-found). What remains: story identifiers `V1-S0-012`, `V1-S1-002`, and `V1-S1-005`, which are **new to this repository** — only `V1-S0-001` through `V1-S0-011` appear on `main` — and are kept deliberately, with the reasoning below. No planning document is quoted, named, or paraphrased |
| Local filesystem paths, host names, user names | **None.** Every path in the diff is repository-relative |
| Credentials, tokens, keys | **None.** Nothing in this change authenticates to anything |
| Model artifacts, weights, generated state | **None.** No binary is added |
| Prompts or completions | One prompt and one completion are referenced by citation to the feasibility record, which already contains them and states why they are safe to publish. Neither is reproduced here |
| Unrelated changes | **None.** Every modified file is modified because this change requires it; see the note below on the test-strategy document |
| Scope expansion | **None.** No route, no handler, no OpenAPI document, no `contracts/` entry, and no Sprint 1 capability |
| A performance figure published as a claim | **None**, and one was actively refused: `timings` is recorded as not passed through precisely so that a per-request decode figure does not reach a public response |
| Reserved security vocabulary outside a denial | Clean. The suite that scans every Markdown file in the repository passes |

### The three forward story identifiers, and why they stay

`V1-S1-002` and `V1-S1-005` name work that has not started, and they appear here for
the first time in this repository. That is worth stopping on rather than waving
through, because "identifiers for unstarted work" is a fair description of a private
queue.

They stay, for two reasons and with one boundary:

- **They are load-bearing, not decorative.** The whole point of this decision is that
  it lands one story before an interface is frozen and two before an API is written.
  A record that says "a later story will freeze an adapter against this" and cannot
  say which one has removed the only detail that makes the timing checkable.
- **The scheme is already public.** Every evidence record in this repository is named
  after a story, `main` carries eleven of them, and the toolchain record already
  discusses Sprint 1 by name. What is new is two positions in a sequence, not the
  existence of the sequence.

**The boundary**: two identifiers and what this decision owes them. No list of Sprint 1
stories, no ordering, no dependency register, no dates, and nothing about any story
this decision does not directly constrain. An earlier draft crossed that line by
reproducing a dependency relation from the planning source, and the second pass
removed it.

### The one edit that is not a new file, and why it is in scope

`docs/testing/test-strategy.v1alpha1.json` gains `tests/serving` in the documentation
layer's `paths`, and `docs/testing/test-strategy.md` has its enumeration of those
directories rewritten.

That is a widening of an existing layer to include a new suite of the same kind — the
same lane, the same marker, the same environment, the same evidence class. It is not a
change to what the layer means.

**One pre-existing inaccuracy was corrected as a consequence**, and it is recorded
rather than left to be noticed. The document said the layer "covers three
directories" and listed three, while the data already named four: `tests/security`
was added by the security work and the sentence was not updated. Adding a fifth forced
the enumeration to be rewritten, and rewriting it correctly means it now lists five.
That correction is a side effect of an edit this change had to make, not an unrelated
cleanup, and the alternative — writing "five directories" above a list of three — was
not available.

## What a second review found

The change was read twice more: once against the acceptance criteria while it was being
written, and once by an independent review after the first commit. Both passes are
recorded, because what the second one found was more serious than what the first one
did.

### The first pass, before the first commit

| Found | Why it mattered | What was done |
|---|---|---|
| The root `README.md` map still said "Six decisions accepted in part" | The architecture index gained a seventh partial acceptance in this change, and the two would have disagreed on the first page a reader reaches | The count was corrected, and a row for the surface document was added to the same table |
| `docs/proof/README.md` listed the Serving row without this record | The evidence index is where a reader looks for what exists, and a record not indexed is a record nobody finds | The row now names this file |
| The `requestCounting` block had been drafted with a malformed key containing a space | It parsed as JSON but was dead data no check would ever read, which is the quiet form of an unenforced rule | Removed before the file was written; the suite now asserts the block's contents |
| Every reference to the private planning source carried a title-cased document name and a numbered section | The public repository's established convention is the lowercase, unnumbered phrase, and a section number publishes the internal structure of a document that is not public | Seven references in the data file and one in the ADR were rewritten to the existing convention |

### The second pass, after the first commit

**One finding was a genuine evidence-class violation, and it is the kind this record
exists to prevent.**

The `/v1/models` response fields `object` and `data` were marked **observed in the
trial**. They were not. The trial did call that endpoint, and the record shows what came
back — but what it shows is the runtime's own model metadata printed as text, not a list
envelope. Neither `object` nor `data` appears in it for that endpoint.

Worse, the check that was supposed to catch exactly this **passed them**, for two
different accidental reasons:

- `object` matched because the chat completion's own body carries that member. The
  check had no notion of which endpoint a field belonged to.
- `data` matched because the record contains the sentence "contains no host detail and
  no personal data". A word in prose was being accepted as evidence that a response
  carried a field.

What was done, in three parts rather than one:

| Part | Change |
|---|---|
| The claim | Both fields are now marked **not observed**, and the surface, the document, and the ADR each say why: the endpoint is evidenced, its response envelope is not |
| The check | An observed field must now appear as a **JSON member key inside a fenced block** of the record, not as a substring of the whole file. `data` no longer passes, and a word in prose no longer counts as a captured field |
| The guard | A test asserts the fenced-block extraction is non-empty and still finds a known member key, because a pattern that silently matches nothing turns every check built on it into a pass. It also fails deliberately if `data` ever does appear as a member key, so that the `/v1/models` rows are re-examined rather than left unobserved out of habit |

A dedicated test now pins the finding: no field of the `models-list` endpoint may claim
observation, and the endpoint itself carries `responseShapeObserved: false` with the
reason beside it.

The narrower fix — marking the two fields correctly and leaving the check alone — was
available and was rejected. The check had already been widened once during this change,
for a related over-attribution at the endpoint level, and widening it a second time
without also making it sharper would have been the second repair of the same weakness.

**Two private-information leaks, found only because the reviewer read the private
source alongside the public diff.** Both are the kind that a diff-only reading cannot
catch, and both are removed:

| Leak | What was published | What was done |
|---|---|---|
| An eight-word span reproduced verbatim from the private planning source, in ADR 0010's Context, together with a phrase naming that source by a distinctive fragment of its title | The sentence disclosed both the wording and the existence of a tracked blocker register | Rewritten in this record's own voice. The requirement is still stated; the source's wording and title are not |
| Two normative sentences of the integration specification reproduced near-verbatim in the surface data, differing only in spelling and casing | The repository's convention everywhere else is loose restatement in the record's own voice, never sentence-level reproduction | Restated in the record's own voice |

A third, smaller one was removed with them. Three files deferred asynchronous
inference by naming a later programme — a label that appears nowhere on `main` and
that the sentence did not need. All three now read "V1 serves one synchronous request
at a time and decides nothing about any other form", which says the same thing without
disclosing a roadmap to say it.

**Two capabilities were published with no decision behind them.** `/v1/models`
declares four capabilities and ADR 0010 decided two: `deterministicSampling` and
`multiModel` were named nowhere in the record that is supposed to have decided them.
D7 now covers all three of the non-streaming capabilities, with what supports each and
what it may not be read as, and a test requires every published capability to name its
declaration point in the decision. **That test fails against the previous commit**,
which is the property it exists for.

The proof record had also claimed the suite checked capability names and error codes
against the decision as well as the document. It did not — both checked the document
alone. Rather than soften the claim, the checks were made true: codes and capabilities
are now checked against both.

Three further findings from the same pass, all fixed:

| Found | What was wrong | What was done |
|---|---|---|
| ADR 0010's consequences said six unreachable codes were "two-thirds of the code list" | Six of thirteen is nearly half, not two-thirds. It was the one derived proportion in an otherwise exactly-counted record, and no test checked it | Rewritten as "six of the thirteen" and "nearly half" |
| The test strategy's documentation layer gained `tests/serving` in its `paths` but not in its `commands` | The machine-readable record would have named five directories and four commands. Nothing cross-checks the two, so the drift would have been silent | The command was added |
| One reference to the private specification survived with a section number, and the `prompt_tokens_details` note described a response field as though the request-refusal policy reached it | The first is the leak the first pass was meant to have finished; the second is a sentence that does not parse against D4 | Both rewritten |
| ADR 0010's Context said "nine decisions are accepted" | The index records two accepted outright, six in part, and one with a recorded exception, in a register whose whole point is that distinction | Rewritten to the actual breakdown |
| One test branch excused `/metrics` from the unobserved-counterpart check | The branch was unreachable, and had the flag ever been flipped it would have excused exactly the claim the check exists to refuse | The special case was removed and the check now holds in both directions |
| Nine keys in the surface data were read by no check, including the values `seenAs` republishes to a reader | Dead data is how a value drifts from the record it came from without anyone noticing, and `seenAs` carries the only observed values this surface prints | Every one is now asserted, and the five republished values are checked against the record that observed them |

**One gap is recorded rather than fixed.** Nothing cross-checks a test layer's `paths`
against its `commands`, so the drift above could recur. Closing that means changing the
suite that belongs to ADR 0005, which is outside this PR's boundary. It is reported here
rather than fixed quietly or left unsaid.

**What the second pass says about the first.** The first pass read the change against
its acceptance criteria and found four presentational defects. The second read it
against the private source and against the committed tree, and found a false evidence
claim, two leaks, two undecided capabilities, and two checks that did not do what this
record said they did. The difference is not diligence, it is standpoint: a reviewer who
only reads the diff cannot catch a sentence that is wrong about something outside it.
That is the argument for the second pass existing, and it is recorded because the first
pass's own summary would otherwise read as though the change had been nearly clean.

Two things were considered and deliberately **not** changed:

- **`contracts/` was not touched.** It is the obvious place to put a request schema,
  and putting one there is exactly what the story forbids. A test now refuses it.
- **No `retryAfterMs` value was specified for any retryable code.** A number here
  would be invented, and the canonical contract makes the field optional. It is left
  to the component that will know what it is retrying against.

## Limitations

- **This record covers a decision, not a system.** Every limitation of ADR 0002's
  evidence travels with it: one host, one operating system, one model, one
  quantisation, one day, and every request in that trial single and sequential.
- **The shapes were read from one runtime build.** A different build of the same
  runtime could return a different body, and nothing here would notice.
- **Eight of the nine error rows have never been provoked.** They are the most likely
  place this record is wrong, and the lane that would test them does not exist.
- **The document-agreement checks are substring checks.** They establish that the same
  identifier appears in the data and in the prose; they do not establish that the prose
  says the same thing about it.
- **The canonical code table is transcribed by hand into the suite.** That is
  deliberate — it gives the surface something independent to be checked against — but
  it means a change to the integration specification's code list has to be brought here
  by a person, and nothing detects that it has not been.
- **Nothing here is defended.** No authentication, no authorization, no rate limit, and
  no control of any kind is introduced or claimed.

## Authorisation

**Not required.** Nothing in this change cost money, downloaded an artifact, contacted
a network service, started a cluster, ran a model, or touched anything outside the
repository working tree. No paid service was used. No large artifact was fetched.
