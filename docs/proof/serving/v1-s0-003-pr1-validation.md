# V1-S0-003-PR1 change validation

Date: 2026-08-23

Classification: **local static evidence for the change itself.** This change adds
documents only. It produced no runtime evidence, because it ran no runtime.

Claim boundary: validates the files this change adds and edits — that they contain
no whitespace defects, that every relative link resolves, that line endings are
normalised, and that nothing private or overclaimed is published. It says nothing
about any serving runtime or model, and its existence must not be read as evidence
that a candidate was tested. Nothing in
[ADR 0002](../../architecture/decisions/0002-model-and-serving-runtime.md) has been
executed.

## Environment

| Component | Version |
|---|---|
| Operating system | Microsoft Windows 11, `10.0.26200` |
| Git | `2.45.1.windows.1` |
| GNU bash | `5.2.26(1)-release (x86_64-pc-msys)` |

## Commands and results

### Whitespace

```text
git diff --check main...HEAD
git diff --cached --check
```

Both clean, exit `0`. No trailing whitespace, no whitespace-before-tab, no
conflict marker.

### Trailing blanks and hard tabs in Markdown

```text
git ls-files -z '*.md' | xargs -0 grep -n '[[:blank:]]$'
git ls-files -z '*.md' | xargs -0 grep -n "$(printf '\t')"
```

Both returned no matches across every tracked Markdown file in the repository, not
only the changed ones.

### Relative link resolution

The POSIX link check from [CONTRIBUTING](../../../CONTRIBUTING.md) was run over
every tracked Markdown file. It reported no broken target.

That check skips in-page anchors, so the one anchor this change introduces was
verified by hand: `#sources-and-when-they-were-read` in ADR 0002 resolves to the
heading `## Sources and when they were read` in the same file.

### Line endings

```text
git ls-files --eol docs/serving/ docs/proof/serving/ docs/architecture/decisions/0002-model-and-serving-runtime.md
```

Every new file reports `i/lf w/lf`. Markdown is covered by the `* text=auto` rule
in `.gitattributes` rather than by an explicit `eol` attribute, which is correct —
the LF-pinning rule exists for shell scripts, where a carriage return becomes part
of the interpreter path. No shell script is touched by this change.

### External links

ADR 0002 cites fifteen external sources. Every one was retrieved on **2026-08-23**,
which is the date recorded in the record itself. They are the only external links
this change adds; no other document in the change contains one.

One correction came out of that retrieval and is recorded here because the record
would otherwise look as though it had always been right: the Llama 3.2 licence URL
returns a `301` to a `developer.meta.com` address. Both are cited, in that order,
rather than silently replacing the one Meta still publishes.

### Checks not run, and why

| Check | Status | Reason |
|---|---|---|
| `bash -n`, `shellcheck` | **Not run** | No file under `scripts/` is changed |
| `kubeconform` | **Not run** | No file under `deploy/` is changed |
| Schema, contract, unit, or integration tests | **Not run** | None exists in this repository yet, and this change adds no code |
| Any runtime, cluster, model, or inference check | **Not run** | Out of this change's boundary. Running one is the next stage of work, and it needs authorisation this change did not have |

No repository task runner, linter, or CI lane is selected yet, so every check above
was run by hand. That remains the known gap ADR 0001 D3 and D4 record.

## Diff inspection

The full staged diff was read and searched for local filesystem paths, host and
user names, credentials, API keys, private planning material, model or generated
artifacts, and capability claims the repository cannot support.

| Looked for | Found |
|---|---|
| Local filesystem paths, drive letters, home directories | None |
| Host name, user name, account identifiers, email addresses | None |
| Credentials, keys, tokens, bearer values | None. Every match for "token" is the language-model sense of the word, in threshold text or in the evidence template |
| Private planning documents, prompts, roadmaps, or strategy | None |
| Model weights, binaries, or generated host state | None. This change adds seven text files and no artifact |
| Overclaimed capability | None found. Every new document opens by stating that nothing in it has been executed |

The model cache location the feasibility workflow requires is described as "a
directory outside the repository working tree", reached through the acquisition
tool's own cache environment variable. No path is named, because the path is a
property of whoever runs the trial and not of this project.

## Files changed

| File | Change |
|---|---|
| `docs/architecture/decisions/0002-model-and-serving-runtime.md` | Added — proposed, selects nothing |
| `docs/serving/feasibility-workflow.md` | Added — procedure, never run |
| `docs/proof/serving/TEMPLATE-runtime-feasibility.md` | Added — template, holds no results |
| `docs/proof/serving/v1-s0-003-pr1-validation.md` | Added — this record |
| `docs/architecture/README.md` | Indexed ADR 0002 as proposed |
| `docs/prerequisites.md` | Recorded that ADR 0002 adds no prerequisite |
| `README.md` | Added an entry point; corrected the ADR status line |
| `CHANGELOG.md` | Recorded the above |

## Review pass

The change was reviewed a second time after it was first written, against the
accepted evidence it quotes rather than against itself. Three corrections came out
of that pass, and they are recorded here because a record that lists only its
successes is the less useful kind:

| Finding | Correction |
|---|---|
| ADR 0002 quoted the idle cluster's memory as `0.72 GiB`. The source records `712–720 MiB`, which is `0.695–0.703 GiB` — outside the range it was meant to summarise | Quoted the measured range directly. The figure derived from it, "roughly 6.9 GiB remaining", was already correct and is unchanged |
| ADR 0002 said a GPU path "cannot be proven at all on this host". ADR 0001 leaves an integrated-GPU path open in principle and rules out only a discrete accelerator | Narrowed the claim to what ADR 0001 actually supports |
| The feasibility workflow listed the **minimum** host tier as a prerequisite, which a reader could take as a claim that the minimum tier is enough to serve a model | Stated that the minimum tier is the floor for running the cluster, and that whether it can serve is what `T3` and `T4` exist to determine |

The first of these is the reason the check exists. It was a transcription error that
every internal consistency check passed, because the wrong number was used
consistently.

The same pass found no private information, no credential, no local path, no
reference to material outside this repository, and no sentence claiming that a
model was downloaded, a runtime was run, or a candidate was selected.

## Limitations

- Static checks on text. They establish that the documents are well-formed and safe
  to publish, and nothing else.
- Every third-party fact in ADR 0002 was read from published documentation on one
  day. Documentation changes, and two of the projects cited publish from a branch
  tip rather than a release, so a claim that is accurate today may not be accurate
  when the trial runs. Re-reading is part of the workflow's first stage for exactly
  this reason.
- Four rows in the runtime table — LocalAI, SGLang, llamafile, and the serving
  platforms — are marked "not verified here" rather than sourced, because none is
  the proposed primary or its fallback. That is a deliberate gap, recorded in the
  record itself.
- One Windows host, one point in time, as with every other record in this
  repository.
