# V1-S0-003-PR2 change validation

Date: 2026-08-24

Classification: **local static evidence for the change itself.** It validates the
files this change adds and edits. It is *not* the runtime evidence — that is
[the feasibility record](v1-s0-003-pr2-runtime-feasibility.md), which is kept
separate on purpose, because a document mixing "the Markdown is well formed" with
"a model answered a request" lets a reader carry the stronger claim away from the
weaker check.

Claim boundary: whitespace, line endings, link resolution, manifest schema
validity, and the absence of private or overclaimed content in the published diff.
It says nothing about whether the runtime works; that question is settled elsewhere
and by different evidence.

## Environment

| Component | Version |
|---|---|
| Operating system | Microsoft Windows 11 Enterprise, `10.0.26200` |
| Git | `2.45.1.windows.1` |
| GNU bash | `5.2.26(1)-release (x86_64-pc-msys)` |
| kubeconform | development build |

## Commands and results

### Whitespace

```text
git diff --cached --check
git diff --check main...HEAD
```

Both clean, exit `0`. No trailing whitespace, no whitespace-before-tab, no
conflict marker.

### Trailing blanks and hard tabs in Markdown

The two checks from [CONTRIBUTING](../../../CONTRIBUTING.md) were run over every
tracked Markdown file in the repository, not only the changed ones. **No match in
either.**

### Relative link resolution

The POSIX link check from [CONTRIBUTING](../../../CONTRIBUTING.md) was run over
every tracked Markdown file. **No broken target.**

This mattered more than usual, because the two architecture decision records were
renamed to an `ADR-` filename prefix while this change was in progress. Every
reference to them across eleven files was checked, and all resolve.

### In-page anchors

The link check skips in-page anchors by design, and this change introduces ten of
them — more than any previous change — so they were verified separately: every
heading was extracted, the standard slug transformation applied, and each anchor
compared against the result. Fenced code blocks were excluded so that a `#` inside
a sample could not be mistaken for a heading.

**Ten anchors checked, zero broken.**

### Kubernetes manifests

```text
kubeconform -strict -summary -kubernetes-version 1.34.0 deploy/smoke/*.yaml deploy/serving/feasibility/*.yaml
Summary: 11 resources found in 5 files - Valid: 11, Invalid: 0, Errors: 0, Skipped: 0
```

Every container image in the new manifests is pinned by digest, as
[CONTRIBUTING](../../../CONTRIBUTING.md) requires. There is no tag-only reference.

### Line endings, and a check this change specifically needed

```text
git ls-files --eol deploy/serving/feasibility/ docs/serving/ docs/proof/serving/
```

Every new file reports `i/lf`. The working-tree column shows `w/crlf` after Git
normalises them, matching every existing YAML file in `deploy/`.

That is normally cosmetic. Here it is not, because the new manifests **embed shell
scripts inside YAML block scalars**, and a carriage return reaching `sh` would
break the script for every contributor who checks the repository out on Windows.
Rather than assume the YAML parser normalises line breaks, it was tested: a CRLF
copy of `inference-probe.yaml` was passed through
`kubectl apply --dry-run=client -o json` and the resulting `args` string inspected.

```text
carriage returns in embedded script: 0
first line repr: 'set -eu'
```

The parser normalises them, so no `.gitattributes` rule is needed. Recorded so the
next person adding an embedded script does not have to re-derive it, and because
"we assumed it was fine" is not a validation result.

### Checks not run, and why

| Check | Status | Reason |
|---|---|---|
| `bash -n`, `shellcheck` | **Not run** | No file under `scripts/` is changed. The shell in the new manifests is embedded in YAML and is not reachable by either tool |
| Schema, contract, or unit tests | **Not run** | None exists in this repository yet, and this change adds no code |
| Image vulnerability scan, supply-chain attestation | **Not run** | The runtime image was pulled and executed but never scanned. Recorded as an open item in ADR 0002's security section rather than silently skipped |
| Cross-platform validation | **Not run** | One Windows host, as with every other record here |

No repository task runner, linter, or continuous-integration lane is selected yet,
so every check above was run by hand. That remains the known gap ADR 0001 D3 and D4
record.

## Diff inspection

The full staged diff — 1,916 lines across 15 Markdown files and 3 manifests — was
read and searched.

| Looked for | Found |
|---|---|
| Local filesystem paths, drive letters, home directories | None. Two pattern hits were `containerd://2.2.0` and an `http://` URL resembling a drive letter |
| Host name, user name, account identifiers, email addresses | None |
| IP addresses | None. The only hits were the bind address `0.0.0.0` and a kernel version string |
| Credentials, keys, tokens, bearer values | None. The single match is the row recording that **no** credential was required |
| Private planning material, prompts, roadmaps, strategy, or certification schemes | None. The only matches are work-item identifiers of the form already published here |
| Model weights, binaries, or generated host state | None. The change is 15 `.md` and 3 `.yaml` files and nothing else |
| Overclaimed capability | None found; see below |

### On the capability claim specifically

This is the first change in the repository that can honestly say a model was
served, so the wording was checked in both directions rather than only for
overclaiming:

- The README banner still states that no deployable platform, supported contract,
  or released capability exists, and now adds that a runtime was proven **once, on
  one host**, and that the trial's manifests are apparatus rather than a product.
- ADR 0002's status is `Accepted, with one recorded exception`, not `Accepted`. The
  failed threshold is named in the status banner, argued in its own section, and
  listed among the consequences.
- The feasibility record's classification is `local real runtime` — the correct
  label from [CONTRIBUTING](../../../CONTRIBUTING.md), and not the strongest one
  available.
- Every derived figure, meaning the decode rates, is labelled derived and carries
  an explicit instruction that it must not be published as a benchmark.

### The prompt and response published here

The trial's prompt and the model's response are reproduced verbatim in the
feasibility record. Both were chosen so that publishing them is safe: the prompt is
a neutral factual question containing no host detail and no personal data, and the
response is one sentence about Kubernetes. The only value redacted from the
response body is the generated completion identifier.

## Files changed

| File | Change |
|---|---|
| `docs/architecture/decisions/ADR-0002-model-and-serving-runtime.md` | Renamed, and moved from proposed to accepted with one recorded exception |
| `docs/architecture/decisions/ADR-0001-local-development-environment.md` | Renamed only; content byte-identical |
| `docs/proof/serving/v1-s0-003-pr2-runtime-feasibility.md` | Added — the runtime evidence |
| `docs/proof/serving/v1-s0-003-pr2-validation.md` | Added — this record |
| `docs/serving/mock-and-real-boundary.md` | Added — the accepted mock and real rule |
| `docs/serving/feasibility-workflow.md` | Executed; four bounds and one prerequisite corrected by running it |
| `deploy/serving/feasibility/weights.yaml` | Added — namespace, weight claim, resumable hash-verifying fetch |
| `deploy/serving/feasibility/llama-server.yaml` | Added — digest-pinned runtime Deployment and Service |
| `deploy/serving/feasibility/inference-probe.yaml` | Added — in-cluster probe job |
| `docs/architecture/README.md` | ADR 0002 status; defined `Accepted, with one recorded exception` |
| `docs/prerequisites.md` | Measured serving requirements replace the estimate |
| `README.md` | Status banner and entry points |
| `CHANGELOG.md` | Recorded the above |
| Six further files | Link updates from the ADR rename only |

## Scope note: the ADR rename

Renaming the two decision records was **not** part of this work item. It was made
outside this change while the change was in progress, and it was kept at the
repository owner's direction rather than reverted.

Its consequences are confined to filenames and references: `ADR-0001` is
byte-identical to its predecessor, and the six out-of-boundary files it touches
change by exactly one or two link paths each. That was verified file by file rather
than asserted.

One edit made by the rename was **reverted**, and it is why this section exists.
The rename also rewrote two pieces of *historical* content inside the
V1-S0-003-PR1 validation record: a transcript of a command that was actually run,
and a table row naming the file that change had added. Both said
`0002-model-and-serving-runtime.md`, because that was the name at the time.
Rewriting them would have made a past evidence record describe a command nobody
ran. The transcript is restored, and the table row now records the original name
with a note that a later change renamed it.

An automated rename that updates links is helpful. The same rename reaching into a
historical record and quietly correcting the past is not, and it is the kind of
thing only a diff review catches.

## Review pass

This change was reviewed a second time after it was written and committed, against
the evidence it cites rather than against itself. The pass was told to look for
figures that disagree between files, claims stronger than one trial supports,
status blurring, leakage, and manifests whose comments describe behaviour they do
not have.

It found **four defects, all real**, and they are recorded in full in
[the feasibility record's corrections section](v1-s0-003-pr2-runtime-feasibility.md#failures-surprises-and-corrections):
one figure that disagreed with its own derivation, one verdict claiming a larger
sample than was measured, and two cases of a document describing a correction that
the manifest beside it had never received.

The last two are the useful ones, and they share a shape. In both, the prose was
correct about what *should* be true and the artifact had not been updated to match,
so the two halves of the change disagreed while each looked right on its own. That
is not a class of defect a link checker, a schema validator, or a whitespace check
can find, and it is the argument for the second pass existing at all.

It found no leakage, no status blurring, and no overclaiming in `README.md` or
`docs/prerequisites.md`.

## Limitations

- Static checks on text, and schema validation on manifests. They establish that
  the documents are well formed and safe to publish, and nothing else.
- `kubeconform` validates a manifest against the Kubernetes schema. It does not
  establish that the workload behaves correctly; the feasibility record does that,
  by running it.
- One Windows host, one point in time, as with every other record here.
