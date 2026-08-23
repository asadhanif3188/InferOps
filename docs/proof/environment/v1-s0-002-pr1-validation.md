# V1-S0-002-PR1 documentation validation

Date: 2026-08-23

Classification: local static documentation evidence

Claim boundary: validates the documents this change adds. It is not runtime,
cluster, container, benchmark, security, or production proof, and it does not
support any statement made inside ADR 0001 about how a tool behaves.

## What was validated

The change adds a proposed decision record, a redacted host inventory, and a
decision-record index, and it updates the changelog, the entry-point table, the
prerequisites page, and the governance decision table.

Only the documents were checked. Nothing they describe was executed.

## Environment

| Component | Version |
|---|---|
| Operating system | Microsoft Windows 11, `10.0.26200` |
| Git | `2.45.1.windows.1` |
| Windows PowerShell | `5.1.26100.8875` |
| GNU bash | `5.2.26(1)-release (x86_64-pc-msys)` |
| Python | `3.12.6` |

These describe the check environment only.

## Commands and results

### Whitespace

```text
git diff --cached --check
git ls-files -z '*.md' | xargs -0 grep -n '[[:blank:]]$'
git ls-files -z '*.md' | xargs -0 grep -n "$(printf '\t')"
```

All three produced no output.

### Relative Markdown links

The POSIX and PowerShell link checks published in
[CONTRIBUTING.md](../../../CONTRIBUTING.md) were both executed verbatim.

Both reported no broken links, and both agree on the same totals: 14 tracked
Markdown files and 28 resolved relative links.

### Positive control

A silent no-op would make every result above meaningless, so a control file
containing one broken relative link, one trailing space, and one hard tab was
temporarily tracked and the checks were rerun. Each check reported exactly the
seeded defect. The control file was then removed and the staged set was confirmed
to be back to the seven intended files.

### External links

```text
curl -s -o /dev/null -w "%{http_code}" -L --max-time 20 <url>
```

This change adds no new external link. The two existing external links were
re-checked on 2026-08-23 and both returned HTTP `200`.

### Public-information review

The full staged diff was scanned for private keys, tokens, credential-shaped
assignments, personal filesystem paths, account names, host names, and mail
addresses. No finding.

The diff was scanned separately for restricted planning identifiers. The only
matches were this project's own work-item identifier, which already appears in
public branch names and in the previously merged evidence record. No plan text,
work queue, positioning material, or unpublished strategy is present.

The changed Markdown was then compared against the restricted planning source for
verbatim phrase reuse. An earlier revision of two files matched at a six-word window
on generic technical phrasing; those sentences were rewritten. The final revision
has no overlap at either an eight-word or a six-word window.

Restricted-source comparison inputs, paths, and identifiers are intentionally not
reproduced in this public record.

### Claim review

Every capability, support, and resource statement in the changed files was read
against what the repository can actually demonstrate. The proposed record is marked
proposed in its status field, in a prominent notice, in the index, in the changelog,
in the prerequisites page, and in the governance table. Its resource figures are
labelled estimates in the table itself and under a warning notice.

## Limitations and skipped checks

- No repository-approved Markdown linter, link-checking tool, or task runner exists
  yet, so the checks are manual shell commands rather than committed tooling. That
  gap is one of the things ADR 0001 proposes to close, and it cannot be closed by
  the same change that proposes it.
- No continuous-integration workflow exists, so this evidence is local and is not a
  remote required check.
- Checks ran on one Windows host. The POSIX variant ran under MSYS2 bash on that
  same host and has not been executed on Linux or macOS.
- No container engine, cluster, workload, model, benchmark, or security scan was
  run. Every acceptance criterion of the parent story that requires runtime proof
  is untouched by this record.
- The restricted-source comparison cannot be reproduced from this repository alone,
  because its inputs are deliberately withheld. Every other result here is
  independently reproducible from this repository.
- The published link checks are documentation aids, not hardened tooling. A relative
  link target containing a parenthesis is truncated at the first closing parenthesis
  in both variants, as the contribution guide states.
