# V1-S0-002-PR2 change validation

Date: 2026-08-23

Classification: local static evidence for the change itself. The runtime evidence
this change produced is separate, in
[the cluster smoke proof](v1-s0-002-pr2-cluster-smoke.md).

Claim boundary: validates the files this change adds and edits — that the scripts
parse and lint, that the manifests match the Kubernetes schema, that the documents
link correctly, and that nothing private or overclaimed is published. It says
nothing about cluster behaviour; that is the other record's job.

## Environment

| Component | Version |
|---|---|
| Operating system | Microsoft Windows 11, `10.0.26200` |
| Git | `2.45.1.windows.1` |
| Windows PowerShell | `5.1.26100.8875` |
| GNU bash | `5.2.26(1)-release (x86_64-pc-msys)` |
| Python | `3.12.6` |
| ShellCheck | `0.11.0` |
| kubeconform | development build |

## Commands and results

### Shell scripts

```text
bash -n scripts/environment/*.sh
shellcheck -x -S style scripts/environment/*.sh
```

Both clean, exit `0`. `shellcheck` was run at `style` severity, which is stricter
than its default, and every finding it raised was fixed rather than suppressed —
with one exception, recorded in the file itself: `lib.sh` disables SC2034 for the
whole file, because it is a sourced library whose constants are consumed by the
scripts beside it rather than within it.

### Kubernetes manifests

```text
kubeconform -strict -summary -kubernetes-version 1.34.0 deploy/smoke/hello-world.yaml deploy/smoke/verify-job.yaml
Summary: 5 resources found in 2 files - Valid: 5, Invalid: 0, Errors: 0, Skipped: 0
```

`-strict` rejects unknown fields, so a misspelled key fails rather than being
silently ignored. The version was matched to the pinned node image.

All three manifest files were additionally parsed with PyYAML, which reported six
documents across three files. The kind cluster definition is covered by that parse
and by the runtime evidence — it was used to create the cluster four times — but
not by `kubeconform`, whose schemas are Kubernetes' and not kind's.

### Line endings and file modes

This repository is configured with `core.autocrlf=true` and had no
`.gitattributes`. Shell scripts committed under that configuration are checked out
with CRLF on Windows, and a carriage return after the shebang becomes part of the
interpreter path, so every script in this change would have failed to run for the
next contributor to clone it. A `.gitattributes` now pins `*.sh` to LF and
normalises the rest.

Verified after renormalisation:

```text
git ls-files --eol scripts/environment/ deploy/
```

Every file reports `i/lf w/lf`, and the scripts report `attr/text eol=lf`.

The scripts are also recorded with mode `100755`, because the runbook invokes them
directly; `lib.sh` is `100644`, because it is sourced and never executed. Neither
was correct by default: Git on this host does not track the executable bit, so both
were set explicitly.

### Whitespace

```text
git diff --cached --check
git ls-files -z '*.md' | xargs -0 grep -n '[[:blank:]]$'
git ls-files -z '*.md' | xargs -0 grep -n "$(printf '\t')"
git ls-files -z '*.sh' '*.yaml' | xargs -0 grep -n '[[:blank:]]$'
```

All four produced no output. The fourth extends the published check to the file
types this change introduces.

### Relative Markdown links

The POSIX and PowerShell checks published in
[CONTRIBUTING.md](../../../CONTRIBUTING.md) were both executed verbatim against the
final tree. Both agree: **18 tracked Markdown files, 47 resolved relative links,
none broken.**

An earlier run of both reported one broken link — a governance page referencing this
file before it existed. That is recorded rather than quietly fixed, because it is
the only direct evidence in this change that the link check detects a real defect in
real use rather than only in a seeded control.

### Positive control

A check that silently passes is worse than no check, so each was made to fail on
purpose. A temporary file containing one broken relative link, one trailing space,
and one hard tab was tracked, and a manifest with a misspelled field and a script
with an unquoted expansion were validated alongside it.

Each check reported exactly its seeded defect and nothing else: the link check
found the broken link, the whitespace checks found the trailing space and the tab,
`kubeconform -strict` rejected the unknown field, and `shellcheck` raised SC2086.
The temporary files were then removed and the staged set confirmed back to the
intended files.

### External links

```text
curl -s -o /dev/null -w "%{http_code}" -L --max-time 30 <url>
```

Three external links exist in the repository, all checked on 2026-08-23:

| URL | Result |
|---|---|
| The pinned kind release page | `200` — new in this change |
| Keep a Changelog | `200` |
| Semantic Versioning | `200` |

The two pre-existing links returned `000` on a first pass and `200` on retry with a
longer timeout. That was local transport, not a broken link, and is recorded so the
first result is not mistaken for a finding.

### Public-information review

The full staged diff was scanned for private keys, tokens, credential-shaped
assignments, personal filesystem paths, account names, host names, and mail
addresses.

One class of finding, and it was real. The tools used during the runtime proof
print an absolute path to the project kubeconfig on every cluster creation, and the
raw transcript therefore contains a personal filesystem path several times. Those
lines are excluded from the published evidence, and the redaction is stated in that
record rather than left implicit. The published files were rechecked afterwards and
contain no absolute path, host name, or account name.

The diff was scanned separately for restricted planning identifiers. The only
matches are this project's own work-item identifier, which already appears in public
branch names and in previously merged evidence. No plan text, work queue,
positioning material, or unpublished strategy is present.

The changed files were then compared against the restricted planning source for
verbatim phrase reuse. **The lines this change adds have zero overlap at both an
eight-word and a six-word window.**

Comparing whole files rather than added lines surfaces four six-word matches, all
of them in text merged by an earlier change and none in this one. They are generic
evidence-labelling and branch-naming phrases in the contribution guide. They are
reported here rather than omitted, because a reader who reruns the comparison at
file granularity will see them and should know they were looked at.

Restricted-source comparison inputs, paths, and identifiers are intentionally not
reproduced in this public record.

### Generated and local state

The cluster run produces a project kubeconfig containing a client certificate and
key, and may produce a diagnostics directory. Both are now ignored by version
control, and `git status` was confirmed clean of them after a full proof cycle. No
model artifact, container image, or node image is committed; images are referenced
by digest only.

### Claim review

Every capability, support, and resource statement in the changed files was read
against what this repository can now demonstrate.

The distinction that needed the most care is between what was executed and what was
not. ADR 0001 decides seven things; the evidence covers five of them. Rather than
mark the whole record accepted, it carries a per-decision status table, and the task
runner, the dependency installation approach, and the recommended host tier are
still labelled proposed in the record, in the index, in the governance table, in the
prerequisites page, and in the changelog.

Three specific claims were weakened against their author's convenience:

- The minimum host tier previously described "a single-node cluster with a mock
  serving path". No mock serving path exists or was run. The tier now claims only
  the cluster.
- The tier is described as measured in the sense that a host meeting it ran the
  cluster. It was never probed downward to find where the cluster stops working,
  and the record says so.
- Teardown is described as returning storage to the container engine, not to the
  host, because measurement showed host free space does not come back.

## Limitations and skipped checks

- No repository task runner or continuous-integration lane exists yet, so these are
  manual commands rather than an automated required check. The task runner decision
  is one of the two this change deliberately did **not** accept.
- `shellcheck` and `kubeconform` are not vendored, pinned, or installed by this
  repository. A contributor without them cannot reproduce those two checks, and the
  contribution guide now says where they are needed rather than pretending they are
  optional.
- Checks ran on one Windows host. The POSIX variants ran under MSYS2 bash on that
  same host. Nothing was executed on Linux or macOS.
- The kind cluster definition is not schema-validated by any tool here.
- No security scanner, dependency audit, or container image scan was run. Image
  provenance rests on digest pinning and on the published checksum verified for the
  kind binary.
- The restricted-source comparison cannot be reproduced from this repository alone,
  because its inputs are deliberately withheld. Every other result here is
  reproducible from this repository by rerunning the commands above.
- The published link checks remain documentation aids rather than hardened tooling,
  with the parenthesis limitation the contribution guide already states.
