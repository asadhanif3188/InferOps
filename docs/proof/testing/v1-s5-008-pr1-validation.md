# V1-S5-008-PR1 validation

Date: 2026-09-27

What this change checked before it was committed, and how. What it prepared is in
[the `v1.0.0` release notes](../../releases/v1.0.0.md) and
[the release checklist](../../releases/v1.0.0-checklist.md); this page is about the
checks run over the repository after those changes were made.

This change executed nothing against a host: no cluster, runtime, or model was
contacted, no tag was created, and nothing was published. Every figure the release
notes quote was already committed and declared by the case study.

## Eligibility, checked before anything was written

- **The gate.** On `main` at `742355b`, `python -m tools.evidence_index --gate` exited 0
  and printed `COMPLETE V1-S5-013` with 5 of 5 blockers closed, `FROZEN V1-S5-013-PR2`,
  the evidence set `1d40b33f…` and the evidence pack `652e9051…`; `--check` printed
  `OK`.
- **The P0 stories.** Every V1 story before this one was matched to the pull requests
  that merged it, from `git log --merges`. Two have none, and the release data says why:
  `V1-S0-010` changed no file in this repository, and `V1-S1-008`'s two commits were
  made on `main` directly.
- **What the pack covers.** The pack is every file a record cites, all under
  `docs/proof/`, with the register and its four ledgers. `pyproject.toml`, the README,
  the changelog, the release pages, and the case study are outside it, so this change
  could leave both digests where they were frozen; it touches no file inside the pack.
- **Two conditions the repository set for itself.** `SECURITY.md` said the missing
  private reporting channel had to be resolved before a versioned release, and
  `CODE_OF_CONDUCT.md` said the conduct deferral had to be revisited first. Both were
  put to the maintainer before any release file was written. The maintainer chose to
  enable GitHub private vulnerability reporting, and to revisit the conduct deferral
  and keep it. The setting lives on the hosting service; it could not be read from this
  host when the change was written, so the checklist reads it before the tag.

## What changed

- **The version.** `pyproject.toml` `1.0.0`, and the lock's record of the project; the
  development-status classifier `3 - Alpha`. ADR 0009 carries a dated note, and its
  decision is unchanged. The local composition's `service.version` label is `1.0.0`,
  because the composition tool requires it to be the declared version.
- **The release pages.** Notes, checklist, and the data they are held to, under
  `docs/releases/`, linked from the release process, the README's first screen, the
  changelog, and the governance table.
- **The changelog.** The unreleased history became `1.0.0`, under a new, empty
  unreleased section, with link references.
- **Reporting and conduct.** `SECURITY.md` names GitHub private vulnerability reporting
  and a supported-version table; the governance table, `CONTRIBUTING.md`, the security
  index, the deferred-risk register, and the security baseline's status and one
  limitation follow it; `CODE_OF_CONDUCT.md` records the revisit.
- **Tests.** `tests/testing/test_release.py` is new. `test_toolchain.py` expects
  `1.0.0` and refuses a production classifier; `test_security_baseline.py` holds the
  policy to naming its channel and promising no response time. The test inventory
  lists the new module, which makes forty-four documentation modules and forty-six
  that defend no claim, and `test_test_inventory.py` knows the words up to fifty; it
  stopped at forty-five and raised on forty-six.

## What the checks caught before the first commit

- **The composition's version.** The first draft left `INFEROPS_SERVICE_VERSION` at
  `0.0.0` and wrote, in the release data and notes, that `service.version` was a label
  set at deployment rather than read from the distribution, and that `0.0.0` was what
  the baseline rerun ran. The architecture suite refused to collect:
  `tools/local_composition` requires the label to equal the version `pyproject.toml`
  declares. The label moved to `1.0.0`, the claim was withdrawn, and the notes now list
  it as a difference from what was measured. No committed record quotes the label's
  value, so "what the baseline rerun ran" is now stated as what the composition said at
  that revision.
- **The measurement scan.** `test_release.py`'s own check that its pattern finds the
  sentences it is for failed on a percentage: a trailing word boundary never matches
  after `%`. Without that check, any percentage in the notes would have passed unread.

## Commands

From Git Bash at the repository root, with every file of this change staged so that
the suites that read `git ls-files` see it. A first `uv lock` against the package index
had not finished after two minutes on this host's network and was stopped, so `uv` ran
with `--offline` against its cache from then on; the lock resolved 23 packages and
changed only the project's own version. `uv build` wrote to a scratch directory outside
the checkout, and nothing it built was kept.

```text
uv lock --offline
uv run --locked --offline ruff format --check .
uv run --locked --offline ruff check .
uv run --locked --offline python -m mypy
uv run --locked --offline python -m pytest tests/testing/test_release.py -q -rs
uv run --locked --offline python -m pytest tests/testing tests/security tests/architecture -q
uv run --locked --offline python -m tools.proof_dashboard --check
uv run --locked --offline python -m tools.evidence_index --check
uv run --locked --offline python -m tools.evidence_index --gate
uv build --offline
uv run --locked --offline python -m pytest -q
git diff --cached --check
```

## Results

On 2026-09-27, on one Windows host, before the first commit:

| Command | Result |
|---|---|
| `uv lock --offline` | Resolved 23 packages; `inferops` `0.0.0` to `1.0.0`, and nothing else |
| `ruff format --check .` | 519 files already formatted, after one reformat of `test_release.py` |
| `ruff check .` | All checks passed |
| `python -m mypy` | No issues in 278 source files |
| `pytest tests/testing/test_release.py -q -rs` | 40 passed, none skipped |
| `pytest tests/testing tests/security tests/architecture -q` | 10558 passed, 3 skipped, 4 failed on its first run, which began before the inventory entry and the validation record existed; the three inventory modules and the link check then passed, 1264 tests, once both were written and the number words extended |
| `python -m tools.proof_dashboard --check` | `OK       dashboard.md is what the register produces` |
| `python -m tools.evidence_index --check` | `OK       v1-evidence-index.v1alpha1.json is what the register and ledger produce` |
| `python -m tools.evidence_index --gate` | `COMPLETE V1-S5-013`, 5 of 5 closed, and `FROZEN   V1-S5-013-PR2` with the evidence set `1d40b33fd79d7b6436c35cfe1fc4ec943a8b82fc77ad1da7cd5d96bb2a5ac23a` and the evidence pack `652e9051161d38e6dd2e77306a431bf96d863a262cc4b0dab15c0518ba920ad2`, exit 0: both unchanged from `main` |
| `uv build --offline` | `inferops-1.0.0.tar.gz` and `inferops-1.0.0-py3-none-any.whl`; the wheel's metadata says `Version: 1.0.0`, `Private :: Do Not Upload`, and `Development Status :: 3 - Alpha` |
| `pytest -q`, the default lane | 15287 passed, 30 skipped, 14 deselected, in 16 min 47 s |
| `git diff --cached --check` | Clean |

The Helm and Terraform gates were not run: nothing under `charts/` or `infra/` changed.
The hosted `checks` workflow runs on the pull request and is not quoted here; the
checklist requires it again on the merge commit. The default lane ran before two
sentences of the release notes were reworded, which changed prose only, and
`test_release.py` passed again afterwards.

## Privacy and publicability

The staged diff was searched for a drive-letter or home-directory path, a scratch
directory, an e-mail address, a credential-shaped string, and the name of any private
planning document. None is present; the only addresses are the repository's own public
URLs. One note in the first draft of the release data described a story by what it had
done outside this repository; it now says only that the story changed no file here. No
model artifact, generated render, built distribution, or machine state is added.
