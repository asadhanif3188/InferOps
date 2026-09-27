# V1-S5-009-PR1 validation

Date: 2026-09-27

What this change checked before it was committed, and how. What it decided is in
[the decision whether a second version should proceed](../../governance/v2-investment-decision.md);
this page is about the checks run over the repository after that page was written.

This change executed nothing against a host: no cluster, runtime, or model was
contacted, and nothing was published. It reads the frozen evidence and adds none. Every
figure the decision quotes was already committed and declared by the case study.

## Eligibility, checked before anything was written

- **The gate and the freeze.** On `main` at `718ad2e`, `python -m tools.evidence_index
  --gate` exited 0 with the gate complete and the pack frozen, the evidence set
  `1d40b33f…` and the evidence pack `652e9051…`.
- **The release.** `git tag -l v1.0.0` printed the tag, and it resolves to `718ad2e`,
  the merge of `V1-S5-008-PR1`. Both stories this one depends on are merged.
- **What the pack covers.** Every file a record cites, the register, and its four
  ledgers. The decision's page and data, the README, the governance table, the
  changelog, and the test inventory are outside it, so the change could leave both
  digests where they were frozen; it touches no file inside the pack.

## What changed

- **The decision.** `docs/governance/v2-investment-decision.md` and the data it is held
  to, `v2-investment-decision.v1alpha1.json`: eleven findings with the register rows
  behind each, ten problems each asked three questions, three options compared on the
  same fields, six entry gates, the eighteen uncertified claims placed, figures, a
  review date and triggers, and one surface left standing.
- **Links to it.** A bullet in the README's roadmap and a row in the governance table,
  both in prose; the README's entry-point table is governed by the register, which is
  inside the frozen pack, so the decision is not added there.
- **The changelog.** One entry under the unreleased section.
- **Tests.** `tests/testing/test_v2_investment_decision.py` is new. The test inventory
  lists it, which makes forty-five documentation modules and forty-seven that defend no
  claim. The documentation layer's narrative sentence had stopped at the forty-third
  module; `V1-S5-008-PR1` added the forty-fourth without extending it, and this change
  extends it for both.

## What the checks caught before the first commit

- **Formatting.** `ruff format --check` refused the new module until it was reformatted.
- **Mutations.** Eighteen deliberate corruptions of the data and the page were applied
  one at a time by a script kept outside the repository, and the module was run after
  each: an outcome that opens a version while gates are unmet, a finding's status or
  record levels differing from the register, a record its finding's claims do not
  cite, an uncertified claim dropped or placed in something that does not exist, an
  expected `C4`, a review date a year out, an option missing a field, a wrong digest, a
  wrong tag commit, a stray measurement, a gate state or a problem answer differing
  between page and data, a broken fragment, a forbidden phrase, the selected marker on
  no option, and a status wrong in the page's findings table. Each was refused, and the
  files were restored after each.

## Commands

From Git Bash at the repository root, with every file of this change staged so that the
suites that read `git ls-files` see it. `uv` ran with `--offline` against its cache, as
in `V1-S5-008-PR1`; the lock is unchanged.

```text
uv run --locked --offline ruff format --check .
uv run --locked --offline ruff check .
uv run --locked --offline python -m mypy
uv run --locked --offline python -m pytest tests/testing/test_v2_investment_decision.py -q -rs
uv run --locked --offline python -m pytest tests/testing tests/security tests/architecture -q
uv run --locked --offline python -m tools.proof_dashboard --check
uv run --locked --offline python -m tools.evidence_index --check
uv run --locked --offline python -m tools.evidence_index --gate
uv run --locked --offline python -m pytest -q
git diff --cached --check
```

## Results

On 2026-09-27, on one Windows host, before the first commit:

| Command | Result |
|---|---|
| `ruff format --check .` | 523 files already formatted, after one reformat of the new module |
| `ruff check .` | All checks passed |
| `python -m mypy` | No issues in 279 source files |
| `pytest tests/testing/test_v2_investment_decision.py -q -rs` | 69 passed, none skipped |
| `pytest tests/testing tests/security tests/architecture -q` | 10658 passed, 3 skipped, in 8 min 24 s |
| `python -m tools.proof_dashboard --check` | `OK       dashboard.md is what the register produces` |
| `python -m tools.evidence_index --check` | `OK       v1-evidence-index.v1alpha1.json is what the register and ledger produce` |
| `python -m tools.evidence_index --gate` | Exit 0, `FROZEN   V1-S5-013-PR2` with the evidence set `1d40b33fd79d7b6436c35cfe1fc4ec943a8b82fc77ad1da7cd5d96bb2a5ac23a` and the evidence pack `652e9051161d38e6dd2e77306a431bf96d863a262cc4b0dab15c0518ba920ad2`: both unchanged from `main` |
| `pytest -q`, the default lane | 15372 passed, 30 skipped, 14 deselected, in 13 min 38 s |
| `git diff --cached --check` | Clean |

The Helm and Terraform gates were not run: nothing under `charts/` or `infra/` changed.
The hosted `checks` workflow runs on the pull request and is not quoted here. The default
lane ran before one sentence of the decision page was reworded — it had said the
record draws its entry gates from the case study, when three of the six come from there —
which changed prose only; the decision, security-baseline, and link suites passed again
afterwards.

## Privacy and publicability

The staged diff was searched for a drive-letter or home-directory path, a scratch
directory, an e-mail address, a credential-shaped string, and the name of any private
planning document or any other project. None is present. The decision describes where
work belongs by the boundary rules this repository already publishes, and names no
other project. No model artifact, generated render, built distribution, or machine
state is added.
