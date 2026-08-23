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

Both reported no broken links, and both agree on the same totals: 15 tracked
Markdown files and 30 resolved relative links.

### Positive control

A silent no-op would make every result above meaningless, so a control file
containing one broken relative link, one trailing space, and one hard tab was
temporarily tracked and the checks were rerun. Each check reported exactly the
seeded defect, and no other. The control file was then removed and the staged set
was confirmed to be back to the intended files.

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
labelled estimates in the table itself and under a warning notice, and each row of
the host inventory is labelled measured or documented.

## Independent review and what it changed

The change was reviewed by three independent reviewers before it was finalised: one
against the work item's own boundary, one for public-information safety and
overclaiming, and one for technical accuracy of the third-party comparisons and the
host readings. Their findings are summarised here because several of them were
correct and material, and a record that hid them would be worth less than one that
does not.

Defects found and corrected:

1. The counts reported in an earlier revision of this file did not match a rerun of
   the commands it documents. The document whose purpose is to certify that no check
   silently passed had itself mis-transcribed its own result. Corrected, and the
   commands were rerun against the final tree.
2. ADR 0001 stated that the container engine's virtualization backend "is working."
   Nothing of the sort was observed; the engine was not running. The claim
   contradicted this repository's own evidence and was removed.
3. The central argument for the proposed task runner was overstated. Its embedded
   shell removes divergence in shell *syntax*; it does not supply the standard
   command-line utilities, so recipes calling them remain platform-dependent. The
   rationale now says what is actually true, and records that the runner-up reaches
   a comparable result.
4. The criticism of the alternative task runner claimed Windows contributors would
   have to supply a POSIX shell themselves. The host inventory in this same change
   records that one is already present, supplied by Git. The claim was contradicted
   by adjacent evidence and was replaced with the accurate objections.
5. The comparison between the proposed Kubernetes distribution and its main
   alternative was one-sided. It named the alternative's removable substitutions
   while omitting the one that actually differs, credited the proposal with a
   certification the alternative in fact holds, and did not admit that the proposal
   ships neither an ingress controller nor a load-balancer implementation. All three
   were corrected, including against the proposal's own favour.
6. The recorded fallback was mis-targeted: the difference between the two options is
   a few hundred megabytes and cannot close a multi-gigabyte shortfall. The fallback
   now names the host-side remedies first.
7. The characterisation of the container desktop application's bundled Kubernetes
   was out of date on node count and overstated the blast radius of its reset. The
   objection was rewritten around ownership, which is the accurate one.
8. The rule that no host-wide change is required was false on the measured platform.
   Three exceptions are now named explicitly rather than discovered later.
9. The teardown guarantee claimed more than the operation delivers. Two artefacts
   survive by design and are now documented, along with the residue a future local
   registry would create.
10. The resource table did not answer its own host-fit criterion. It now uses
    explicit minimum and recommended tiers, separates host memory from the share
    that must reach the container virtual machine, and states plainly that the
    measured host does not meet the recommended tier.
11. The dependency count omitted `kubectl`, which on the measured host arrives
    bundled with a third-party application and is therefore unpinned.
12. Several smaller corrections: the interpreter-pinning rationale, which assumed a
    provisioning behaviour that does not occur; the dismissal of two dependency
    managers on grounds that do not generalise beyond one host; the description of a
    second Kubernetes distribution as though it shared another's substitutions; the
    understatement of an experimental provider's status; and the total capacities of
    both disk volumes, removed from the inventory because only free space bears on
    the decision.

Two readings of the host were also corrected. The inventory had listed one memory
measurement twice as though it were two facts, and had described a processor
virtualization reading as inconclusive when the evidence in fact establishes the
opposite of its literal value by inference.

### Additional measurements taken during review

Two gaps the reviewers identified were closed by measuring rather than by hedging:

```text
Get-CimInstance Win32_PhysicalMemory
kernel32!IsProcessorFeaturePresent
```

- Installed memory is 16 GiB in a single module at 3200 MT/s, so one memory channel
  is populated. The previously recorded 15.68 GiB is the operating-system visible
  figure, not the installed capacity.
- Processor feature probe: SSE 4.2, AVX, and AVX2 available; AVX-512 foundation
  **not** available. These are measured. The AVX-VNNI and AMX rows in the inventory
  remain labelled documented, because that probe cannot report them.

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
  independently reproducible from this repository by rerunning the commands above.
- The published link checks are documentation aids, not hardened tooling. A relative
  link target containing a parenthesis is truncated at the first closing parenthesis
  in both variants, as the contribution guide states.
- The reviewers read the documents; they did not run the tools those documents
  describe, because nothing was authorised to be run. A documentation-derived
  comparison can still be wrong in ways only execution would reveal, which ADR 0001
  records as a risk against itself.
