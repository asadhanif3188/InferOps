# V1-S5-002-PR2 change validation

Date: 2026-09-19

Change: [the generated V1 proof dashboard](../dashboard.md) reconciled with the
clean-clone run and made the reviewer's index of V1, the capability selection and
the renderer behind it under [`tools/proof_dashboard/`](../../../tools/proof_dashboard/),
[the suite that regenerates the page and now also holds the README's route into
it](../../../tests/testing/test_proof_dashboard.py), that suite's row in
[the test inventory](../../testing/test-inventory.v1alpha1.json), the pointer
paragraph and the entry-point row in [the README](../../../README.md), and the
pointers in [the evidence index](../README.md).

Classification: **local static evidence.** Evidence class `local-static`. Every
result below was produced on one Windows host by running commands over files in
this repository. No cluster was selected or contacted, no model was loaded, no
runtime was started, no request was served, no Prometheus or Grafana was asked
anything, no container was built or run, and no job was executed on the
continuous-integration service.

**No product behaviour changed.** Nothing under `src/`, `charts/`, `infra/`,
`deploy/`, or `scripts/` is touched. The change under `tools/` is to a document
generator that reads two paths and may write one, `docs/proof/dashboard.md`.

Claim boundary: **the register is not edited by this change.** No status is
promoted, no certification level is raised, no evidence label or provider is
altered, no record is added to a claim, and no measurement is made. What changes
is which heading a reviewer finds each claim under, what the page says before its
first table, and which hand-written sentences in the README a test now holds to
the register.

**What this record does not establish.** It is not evidence that any statement on
the page is true. It establishes that the page is derived from the register, that
the README's route into it agrees with the register, and that the links involved
resolve. Whether a record says what the row citing it says it says is a reading;
the register carries that limitation and the page inherits it whole.

## Environment

| Component | Version |
|---|---|
| Windows | 11 Enterprise 10.0.26200 |
| Shell | GNU bash 5.2.26(1)-release (x86_64-pc-msys), Git Bash |
| Python, host | 3.12.6 |
| Python, locked environment | 3.12.12 |
| `uv` | 0.9.16 (a63e5b62e 2025-12-06) |
| `pytest` | 8.4.2 |
| `ruff` | 0.16.4 |
| `mypy` | 2.3.1 (compiled: yes) |
| Git | 2.45.1.windows.1 |
| Branch | `docs/v1-s5-002-proof-dashboard-release` |
| Base | `main` at `3937dc055ef0e8c9e39a1bca53de8ad851b01b1f` |

No Docker engine, Helm, Terraform, `kubectl`, `promtool`, or Grafana was used.
`shellcheck` is not installed on this host and no shell script changed, so it is
recorded as not run rather than as passing.

## What the clean-clone run changed, and what this change did about it

The register was compared, claim by claim, with the register at the commit that
merged the Sprint 4 dashboard (`dcf8f1d`). 58 claims then and 58 now; none added,
none removed; **one row differs**, and it was changed by
[`V1-S5-001-PR2`](../environment/v1-s5-001-pr2-clean-clone-run.md), not here:

| Field of `a-reviewer-can-reproduce-v1-from-a-clean-clone` | Sprint 4 dashboard | Now |
|---|---|---|
| Status | `planned` | `certified` |
| Certification level | none | `C2` |
| Evidence label | `documented-unexecuted` | `local-real-cpu` |
| Provider, environment | none, `capable-host` | `docker-desktop`, `local-kubernetes` |
| Records cited | 0 | 10 |

So the totals moved from 41 certified and 8 planned to 42 certified and 7 planned,
and the page followed, because it is generated. **What did not follow was the
reader's view of it.** The claim belonged to no capability group, so the strongest
single result V1 has -- the whole journey, from a fresh clone, on the reference
provider -- was on the proof page as one more in a count of "certified claims that
appear as a number only", and its ten records were linked from no row. That is the
reconciliation this change makes: the claim now has a capability group of its own,
third on the page, and its row carries all ten records and the limitation the
register gives it.

The clean-clone run re-executed the local and Kubernetes C2 certifications, the
telemetry verification, the load scenarios, and the pod-loss experiment. **None of
those re-executions moves another claim, and none is cited by one.** The register
cites them only from the clean-clone claim, the earlier records stay the certifying
ones for their own claims, and the clean-clone record says of the pod-loss figures
that two executions are not a distribution. The page therefore shows, for pod loss,
the 31 960 ms outage the certifying record measured and not the 2 832 ms the
clean-clone run observed, and that is the register's decision rather than this
page's.

No correction from the clean-clone attempts changes a claim either. Its five
defects were in a test helper, an error path, a test's output directory, a residue
check, and a consent list; each was fixed in that change and none was a capability
the register had certified.

## What the page holds

| Fact | Sprint 4 dashboard | Now |
|---|---|---|
| Source of every status and count | the register | the register, unchanged |
| Claims in the register | 58 | 58 |
| Certified, planned, deferred, not claimed | 41, 8, 1, 8 | 42, 7, 1, 8 |
| Capability groups | 11 | 14 |
| Claims shown under a capability group | 41 | 58 |
| Certified claims in no group, shown as a number only | 7 | 0 |
| Distinct evidence records linked | 41 | 61, every record the register cites |
| Rules applied before the page renders | 11 | 11 |
| Page size | 303 lines | 420 lines |

Between those two columns the clean-clone change made the number-only count 8; this
change makes it 0.

The three new groups, and why each exists:

- **Clean-clone reproduction** holds the one claim above.
- **Contracts, scaffolding, and the safe quick start** holds the five certified
  claims behind the mock path and the three `planned` ones beside them. A reviewer
  who runs the quick start the README offers had no row saying what it proved, and
  its strongest level is `C1` on `mock` evidence, which the overview now shows
  beside the `C2` groups rather than leaving it to be inferred.
- **Release and production use** holds two `not-claimed` rows and nothing else: no
  release has been published, and InferOps is not a portable production platform.
  They were already in the table of what V1 does not claim; they are now also a
  heading with a tally of zero certified, because those are the two absences a
  reader is likeliest to assume away.

Four existing groups gained the rows that belonged with them: the two `planned`
canonical-error claims and the local runtime diagnosis under real serving, the
`planned` redaction claim under telemetry, the `planned` public-history claim under
the security boundary, and resource ownership under the group that says who checks
the rest, renamed to say so. Placing a `planned` row beside the certified rows of
its capability is deliberate: the capability table is where a reader forms a view,
and a view formed without the row that says "not yet" is the overstatement this
page exists to prevent.

## Reviewer navigation added

| From | To | How it is held |
|---|---|---|
| README, *What V1 proves* | the proof dashboard, in the paragraph under the strongest-evidence table | a test requires the link in that section |
| README, *Five minutes, in order*, step 4 | the proof dashboard | a test requires the link in that section |
| README, *What V1 proves* table | nine records | each must exist, be cited by a certified claim, and be linked on the dashboard |
| Dashboard, *Five minutes, in order* | the overview, the capabilities, what V1 does not claim, where V1 stands, what the page is not | every fragment must be a heading the page carries |
| Dashboard, *The capabilities at a glance* | each of the 14 capability sections | every row's fragment must be a heading the page carries |
| Dashboard, every certified row | its records under `docs/proof/` | the generator refuses a missing record; the suite resolves each link |
| Dashboard, *What this page is not* | the Grafana screenshots and the real-Prometheus record, labelled operations evidence | both targets must exist and the label must be present |

The README already linked the dashboard from both sections before this change;
[`V1-S5-002-PR1`](../quickstart/v1-s5-002-pr1-validation.md) wrote them. What this
change adds on that side is the checks: until now nothing would have noticed the
link being edited out, or the README going on saying "42 certified" after the
register stopped saying it.

## How the page stays a projection of the register

1. `tools/proof_dashboard` holds no status, level, label, provider, record, or
   count. It holds a selection -- which claim identifiers a reviewer is shown under
   which heading -- and fixed prose.
2. Eleven rules are applied to the register before anything renders, and no mode of
   the command reaches the renderer past a finding.
3. The committed page is compared with what the register renders today, in the
   suite and by `python -m tools.proof_dashboard --check`.
4. The overview is new and is held the same way: each row's four counts, its
   strongest level, and its providers are recomputed in the suite from the group's
   own register rows, the four columns must sum to the register's status totals,
   and a group with no certified row must show no level.
5. The README is written by hand, so it is checked instead of generated: the status
   counts it quotes, the number of capability groups it names, and the records its
   first table links.

The overview was the one addition that could have become a second source of truth,
because it is the table a summary colour gets added to. It has no status column. A
group is four counts, and the suite's existing check that no group is given a status
of its own still holds.

## Commands, and what they returned

Run from the repository root, in Git Bash.

| Command | Result |
|---|---|
| `python -m tools.proof_dashboard` | `OK       58 claims satisfy 11 dashboard rules` |
| `python -m tools.proof_dashboard --json` | `[]`, exit 0 |
| `python -m tools.proof_dashboard --check` | `OK       dashboard.md is what the register produces` |
| `python -m pytest tests/testing/test_proof_dashboard.py -q` | `168 passed` |
| `python -m pytest tests/testing/test_document_links.py -q` | `204 passed` |
| `python -m pytest tests/testing tests/security -q` | `4743 passed` |
| `uv run --locked ruff format --check .` | `462 files already formatted` |
| `uv run --locked ruff check .` | `All checks passed!` |
| `uv run --locked python -m mypy` | `Success: no issues found in 259 source files` |
| `uv run --locked python -m pytest -q` | `11900 passed, 30 skipped, 14 deselected in 682.86s`, on the tree as first committed |
| `git diff --check main...HEAD` | no output, exit 0 |
| `git ls-files -z '*.md' \| xargs -0 grep -n '[[:blank:]]$'` | no match |
| `git ls-files -z '*.md' \| xargs -0 grep -n "$(printf '\t')"` | no match |

The dashboard suite no longer skips anything. Its seven skips were the certified
claims no group named, which the per-record link check passed over by name; every
claim is now in a group, so every certified claim's records are resolved.

## Reviewer checklist

Walked by the author against the rendered page and the README, after the run above.

| Check | Result |
|---|---|
| The README's first screen reaches the proof dashboard in one link | Yes, from the paragraph under the strongest-evidence table |
| The dashboard says what it is and what it is not before its first table | Yes: generated, not a monitoring view, and the headline count |
| A reviewer can find a capability without reading the page | Yes: the overview, one row per group, each linking its section |
| Each of the README's nine strongest-evidence rows is on the dashboard under a certified claim | Yes, and checked per record |
| The clean-clone journey is a row, with its records and its limitation | Yes, third group on the page |
| Mock and real are distinguishable | Yes: the quick-start group's strongest level is `C1` in the overview, and its rows' evidence classes are `local-static`, `mock`, and `documented-unexecuted` |
| Planned, deferred, and not-claimed rows are visible inside capability groups | Yes: 7 planned, 1 deferred, and 8 not claimed, each under a group and again in the derived table |
| Multi-replica and production use read as absences | Yes: both groups show 0 certified and no level |
| Provider boundaries are visible | Yes: a provider column in the overview and in every row, and the sentence refusing to generalise one provider to another |
| Operations evidence is not presented as proof state | Yes: labelled, linked, and stated not to be a certification |
| No freshness, fleet, continuous-verification, or promotion-gate feature is implied | Yes: each is listed as not built, not planned for V1, and not a claim |

## What this change does not add

- **No claim, status, level, or record.** The register's claims are byte for byte
  what `main` holds.
- **No new rule in the generator.** "Every claim is in a group" is a check in the
  suite and not a twelfth rule, on purpose: a rule would refuse to render the page
  the day somebody adds a claim to the register, and a page that stops rendering is
  a worse failure than a page that says one certified claim has no row. The
  renderer keeps both sentences and the suite renders the other one by removing a
  group.
- **No freshness or expiry, no fleet or environment comparison, no continuous
  verification, and no promotion gate.** The page now says so in its own last
  section, as absences and not as a roadmap; nothing in the register plans them.
- **No application framework.** The page is still one Markdown file rendered by one
  Python module.
- **No tag, release, or external publication.**

## Acceptance criteria

| Criterion | Status |
|---|---|
| Reviewer README exposes a direct path to the Proof Dashboard | Met, and now checked in the two sections that carry it |
| Dashboard reflects the final current V1 claim state and clean-clone evidence available at this stage | Met. The page is what the register renders today, and the clean-clone claim is a row with its ten records |
| Every certified reviewer-facing capability resolves to supporting evidence | Met. All 42 certified claims are rows, each linking records that exist; the README's nine leading records are each cited by a certified claim |
| Planned, deferred, and not-claimed capabilities remain visible and cannot be mistaken for certification | Met. All 16 are rows under a group and again in the derived table; a group with no certified row shows no level, and no group carries a status |
| Provider/environment/certification boundaries are visible | Met. Overview column, per-row scope, and the provider paragraph; the evidence-label table states each ceiling |
| Automated checks prevent dashboard/claim-matrix drift and broken evidence links | Met. Byte-for-byte regeneration, recomputed overview, resolved links and fragments, and the README's counts and records |
| Presentation is lightweight, static/repository-friendly, and suitable for the five-minute reviewer walkthrough | Met. One generated Markdown file, opening with a five-step route and a fourteen-row overview |

Parent story `V1-S5-002`, as far as this change can speak to it:

| Story criterion | Status |
|---|---|
| Reviewer README links directly to the Proof Dashboard as the visual index | Met |
| The Sprint 4 dashboard is reconciled against the final clean-clone state without a second source of truth | Met |
| Every reviewer-facing capability state links to a claim or evidence record, or is labelled planned, deferred, or not claimed | Met |
| Mock and real paths are unmistakable | Met on this page; the README's own labelling is `V1-S5-002-PR1`'s |
| Production limitations are visible | Met: a capability group of its own, with zero certified |
| First screen, quick start, and strongest-evidence links | `V1-S5-002-PR1`'s, unchanged here |

## Limitations

- **The grouping is still a reading.** Fourteen headings and which claim sits under
  which are judgements in `tools/proof_dashboard/core.py`. The suite checks that
  every claim is somewhere and nowhere twice; it does not check that a claim is
  under the heading a reader would look for it.
- **The page is longer.** 420 lines where it was 303, and the clean-clone row links
  ten records in one cell. The overview is what keeps it a five-minute page, and a
  reader who skips the overview has a longer read than before.
- **The README checks are narrow.** They hold one sentence of counts, one phrase
  naming the number of groups, two links, and the records in one table. Every other
  figure in the README is quoted by hand from a record, and nothing compares those.
- **The fragment check uses this repository's own slug rule**, written to match the
  one the hosting service applies to simple headings. It was not checked against a
  rendered page, and a heading with punctuation the rule does not anticipate could
  pass here and miss there.
- **The page inherits the register's first limitation whole**: nothing here
  establishes that a statement is true, only that it is the register's statement.
- **Every real result behind these rows was produced on one Windows host, by one
  author, by hand**, almost all of it on the `docker-desktop` reference provider. No
  second engineer has repeated the clean-clone journey and no outside party has
  reviewed a claim against its evidence.
- Nothing runs this generator automatically. It is a contributor command and a
  test.

## Authorisation

Not required. No command in this record contacts a network, selects or mutates a
cluster, downloads or loads a model artifact, provisions anything that costs money,
or runs a destructive operation. The only file written by a command here is
`docs/proof/dashboard.md`, by `python -m tools.proof_dashboard --write`.
