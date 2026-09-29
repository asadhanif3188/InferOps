# V2-S1-001-PR1 validation

Date: 2026-09-29

What this change checked before it was committed, and how. What it publishes is in
[the EnvironmentBinding document](../../contracts/environment-binding.md); this page is
about the checks run over the repository after that document, the schema, and the
fixtures were written.

The change executed nothing against a host: no cluster, runtime, or model was contacted,
nothing was provisioned, and nothing was published. Every check below is static, which is
`C0` under [the evidence levels](../../testing/evidence-levels.md). It adds no record to
the evidence pack and moves no claim.

## Eligibility, checked before anything was written

- **The decision that opens the version is merged.** `main` was at `d8e3998`, the merge of
  `V2-S0-001-PR1`, which makes contract-to-deployment rendering the version's first
  capability.
- **The gate and the pack.** `python -m tools.evidence_index --gate` exited 0 with
  `FROZEN` for `V1-S5-013-PR2`, `RELEASED v1.0.0` with the set `1d40b33f…` and the pack
  `652e9051…`, and `CURRENT` with the set `08d4868f…` and the pack `b958a724…`. None of the
  files this change touches is cited by a record, so all three pairs stayed where they were,
  and the same command after the change printed the same six digests.
- **The WorkloadContract is the released one.** Its schema, fixtures, compatibility matrix,
  and domain model are unchanged by this change; the one edit to its validator is a
  refactor whose output is covered below.

## What changed

- **The schema.** `contracts/environment/environment-binding.v1alpha1.schema.json`:
  `apiVersion` `inferops.io/v1alpha1`, `kind` `EnvironmentBinding`; `metadata.name` and
  `metadata.owner`; and five required blocks under `spec` — `environment`, `destination`
  (`clusterProvider`, `namespace`), `modelCache` (`class`, `claimName`), `platform`
  (`apiReplicas`), and `gitops` (`destinationPath`). Every object is closed and every member
  required.
- **Fixtures.** Two valid bindings, `local-docker-desktop` and `local-kind`, and eleven
  invalid ones with a manifest of twenty-two expected findings.
- **A validator module.** `tools/contract_validation/environment_binding.py` applies the
  schema and translates each failure through the canonical error model. It adds no rule and
  no code.
- **A refactor of the WorkloadContract validator.** `structural_findings` now calls a new
  `findings_against(schema, document)`, and `validate` calls a new `ordered(findings)`;
  the private `_validator()` helper is gone. Both contracts share the translation from a
  schema keyword to a published rule. The WorkloadContract's own three suites and the
  domain and scaffolding suites pass unchanged, which is what shows its output did not
  move.
- **Tests.** `tests/contracts/test_environment_binding_v1alpha1.py`, inventoried in the
  `contract-and-schema` layer with no claim and a written reason.
- **Documents.** The binding's own document; the two contract indexes, the contract
  package changelog, the project changelog, the README's contracts row, the test inventory's
  data and page, and the proof index row that links here.

## What the change was asked to reach, and what it reached

| Asked | Reached here | How |
|---|---|---|
| A versioned binding with stable identifiers and compatibility rules | Yes | `apiVersion` + `kind`; `metadata.name`; the pair `spec.environment` + `metadata.name`; three compatibility classes and the no-break-without-a-new-version rule, in the document |
| Environment facts cannot silently override WorkloadContract fields | Yes, structurally | No property under a binding's `spec` is one a contract's `spec` defines, other than the shared key; a test reads both schemas. `invalid/workload-intent-in-binding.yaml` is refused at all three fields it tries to own |
| Missing, malformed, unsupported, and conflicting bindings fail canonically | For a single document | `field-required`, `value-malformed`, `version-unsupported`, `value-not-permitted`, `field-unknown`, each with a fixture. A conflict between two bindings, or between a contract and a binding, needs both documents and is **pending**: nothing reads two |
| Reference and negative fixtures | Yes | Two valid, eleven invalid, covering identifiers, required values, plaintext-secret attempts in fields and in identifiers, and an unsupported version |
| Domain objects avoid Kubernetes and Argo coupling | **Pending** | No domain object exists yet. The schema itself names no Kubernetes or Argo type: a provider, a namespace, a claim name, a count, and a path |
| Ownership relative to the WorkloadContract documented | Yes | Two tables in the document, each compared with a schema by a test |

## Decisions taken while writing, and what was left out on purpose

- **No revision field.** A number kept by hand beside the content can disagree with it.
  Content identity is a digest; how it is computed belongs to the release provenance
  artifact, which does not exist.
- **No storage class.** The prerequisite layer takes it as an input; a binding field for it
  would make two owners of one value.
- **No service exposure field.** Not needed by anything the binding must carry now; adding
  an optional field later is a compatible change.
- **No description and no annotations.** Every string is a lowercase identifier, a
  lowercase path, or a vocabulary value, so no field accepts free text a credential could be
  pasted into.
- **`clusterProvider`, not `provider`.** The WorkloadContract already defines `provider`,
  for a secret reference; the ownership test compares property names, and a shared name
  with a different meaning would have had to be excepted.
- **The claim name is a DNS label**, narrower than the DNS subdomain the chart accepts. The
  default claim fits it, and a narrower binding can be relaxed compatibly.
- **The command-line validator was not extended**, and the continuous-integration gate
  that runs it over the WorkloadContract's fixtures was not given the binding's. The binding
  fixtures run in the default pytest lane. The document says so.

## What the checks caught before the first commit

- **The document overstated the credential gap's coverage.** The first draft said the
  WorkloadContract's heuristic "would catch" every lowercase credential shape the patterns
  let through. Writing the test that measures it showed the heuristic tests for a prefix at
  the start of a value, so it misses a shape inside a GitOps path or behind the namespace's
  `inferops-` prefix. The document now states both outcomes, and the test asserts each per
  field and per shape.
- **A table reader in the test skipped the first row** of any table it was pointed at by
  its header line. It was re-anchored to the sentence before the table, before the suite was
  first run.
- **One unused import**, reported by `ruff check` and removed; one file reformatted by
  `ruff format`.
- **Two broken links**, to this page, from the changelog and the proof index, until this
  page existed.
- **A fixture placeholder was replaced before any scan**: the password in
  `invalid/secret-value-in-a-field.yaml` was first a longer phrase, and was shortened to a
  lower-entropy word in case the secret scanner's generic rule flagged it. A probe
  afterwards showed the scanner does not flag the longer phrase either; the change was a
  precaution, not a fix.
- **The expected-rejections manifest was generated from the validator's output**, not
  written by hand. Every entry was then compared with the refusal each fixture's header
  states it is for, and all twenty-two agree; that comparison was by reading, and a
  reviewer should repeat it rather than trust the generation.

## Checks that the new tests are not decorative

Five edits were made to a copy of the schema, the binding suite was run against each, and
the schema was restored. Each edit was caught:

| Edit | Result |
|---|---|
| Add a required `minimumReplicas` under `platform` — a WorkloadContract field | 35 failed |
| Open the `gitops` object | 2 failed |
| Add `minikube` to the provider vocabulary | 2 failed |
| Allow uppercase and underscores in every identifier | 8 failed |
| Raise the API replica maximum to 32 | 1 failed |

## Commands

Run from Git Bash, with `PYTHONDONTWRITEBYTECODE=1`, against the working tree with every
change staged, so that suites reading `git ls-files` saw the new files.

| Command | Result |
|---|---|
| `uv run --locked --offline --no-sync ruff format --check --no-cache .` | 532 files already formatted |
| `uv run --locked --offline --no-sync ruff check --no-cache .` | All checks passed |
| `uv run --locked --offline --no-sync python -B -m mypy` | No issues in 283 source files |
| `python -B -m pytest tests/contracts/test_environment_binding_v1alpha1.py -q -p no:cacheprovider` | 109 passed |
| `python -B -m pytest tests/contracts tests/domain tests/scaffolding tests/testing tests/security tests/serving -q -rs -p no:cacheprovider` | 10,058 passed, 27 skipped, 2 failed — the two links to this page, before it existed |
| `python -B -m tools.evidence_index --gate` | Exit 0; the six digests above, unchanged |
| `gitleaks dir <path> --config .gitleaks.toml --redact`, for each of the 29 staged files, with gitleaks 8.30.1 (the version the workflow pins; the Windows archive's SHA-256 checked against the release's checksum list) | No leaks found in any |

The full default lane, the proof dashboard and evidence index checks, and `git diff --check`
were run after this page was written; [their results](#results-after-this-page-was-written)
are below.

## Results after this page was written

| Command | Result |
|---|---|
| `uv run --locked --offline --no-sync python -B -m pytest -q -rs -p no:cacheprovider --basetemp=<scratch>` | **15,622 passed, 33 skipped, 14 deselected, none failed**, in 18 min 35 s |
| `python -B -m tools.proof_dashboard --check` | Exit 0: the dashboard is what the register produces |
| `python -B -m tools.evidence_index --check` | Exit 0: the index is what the register and the ledger produce |
| `git diff --cached --check` | Exit 0, no output |

The 33 skips are host state and fixture layering, not passes, and none is in the binding
suite: 25 WorkloadContract fixtures that a structural-only or semantic-only check skips by
design, four symbolic-link checks this Windows host does not permit, three checks against
the pinned telemetry collector image, which is not present locally, and one POSIX signal
check. The 14 deselections are the cluster, real-runtime, failure, and load lanes, which
the default marker expression excludes. Helm was on this host's path, so the chart's
render tests inside the suite ran rather than skipped. The workflow's separate gates —
`helm lint`, kubeconform, the Terraform and tflint checks, the expected-failure controls,
the package build, and the image build — were not run locally: this change touches no
chart, Terraform configuration, manifest, workflow, or packaged source outside the offline
validator, and those gates run on the hosted workflow.

## Privacy and publicability

The staged diff was read for private planning material, local paths, and credentials. It
names no private planning document or repository, no local filesystem path, no host or
account name, and no later story identifier. The only credential-shaped strings are the
published AWS placeholder key identifier, the public JWT header, a fixed synthetic
mixed-case string, and all-zero synthetic tokens in the test module, which sits under a
directory the secret scanner's configuration already exempts. Each is labelled where it
appears.

## What this does not establish

That any renderer will accept a binding, that the environment either fixture describes is
running, or that a release was ever installed with the values a binding names. Nothing reads
a binding.
