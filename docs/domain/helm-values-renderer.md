# Helm values renderer

Status: **implemented in the platform domain** by `V2-S2-001-PR1`, **bound to a
release** by `V2-S2-001-PR2`, and **verified once committed** by `V2-S2-002-PR1`. This
page says how a validated render context becomes the values of the existing
`inferops-llm` chart: where each value goes, what is refused, the canonical form the
values are written in, the RenderedWorkloadRelease that names them and the two files both
are written to, how a committed release is checked against its sources, what a
hand-written values file may still set, and how the result compares with the V1 real
release. A caller can write the values and their release to a directory it names. One
command [verifies every committed generated release](#verifying-a-committed-release)
against the inputs it is declared to be derived from, and regenerates a release a
contributor names. The one committed release is the reference release, a test fixture.
Nothing in this repository installs a generated release: the values a release is
installed with are still written by hand. Every check behind this page is static, at
evidence level C0, and so is every file it generates until a real deployment installs one.

| Property | Value |
|---|---|
| Module | [`src/inferops/domain/render/helm_values.py`](../../src/inferops/domain/render/helm_values.py), with the YAML form in [`values_yaml.py`](../../src/inferops/domain/render/values_yaml.py) |
| Entry points | `HelmValuesRenderer(revision).render(context)`, or `render_with(renderer, ...)` on documents; `generate_release(renderer, ...)` for the values and their release, and `write_release(generated, directory)` to write both; `admit_manual_values(values, manual)` to pair a hand-written file with them, and `manual_value_findings(manual)` for its findings |
| Input | A `RenderContext` from [the renderer input boundary](renderer-input-boundary.md), for a `synchronous-llm` contract |
| Output | `GeneratedHelmValues`: 25 chart values, as a read-only document and as canonical YAML; through `generate_release`, also the release naming them, as the two files `values.generated.yaml` and `rendered-workload-release.yaml` with their digests |
| Chart | `inferops-llm` `0.3.0`; a test fails if [`Chart.yaml`](../../charts/inferops-llm/Chart.yaml) names another |
| Refusal | `RenderRefused`, under the boundary's vocabulary; four rules are the renderer's own |
| Golden output | The release directory [`support-assistant-local-kind/`](../../tests/domain/fixtures/helm-values/support-assistant-local-kind/): [`values.generated.yaml`](../../tests/domain/fixtures/helm-values/support-assistant-local-kind/values.generated.yaml), and the release naming it, [`rendered-workload-release.yaml`](../../tests/domain/fixtures/helm-values/support-assistant-local-kind/rendered-workload-release.yaml) |
| Drift check | [`tools/generated_release`](../../tools/generated_release/core.py): `python -m tools.generated_release --check`, and `--write NAME` to regenerate |
| Tests | [`tests/domain/test_helm_values_renderer.py`](../../tests/domain/test_helm_values_renderer.py); for the release and the files, [`tests/domain/test_generated_release.py`](../../tests/domain/test_generated_release.py); for the drift check, [`tests/domain/test_generated_release_drift.py`](../../tests/domain/test_generated_release_drift.py) |
| Validation records | [`v2-s2-001-pr1-validation.md`](../proof/domain/v2-s2-001-pr1-validation.md), [`v2-s2-001-pr2-validation.md`](../proof/domain/v2-s2-001-pr2-validation.md), [`v2-s2-002-pr1-validation.md`](../proof/domain/v2-s2-002-pr1-validation.md), [`v2-s2-003-pr1-validation.md`](../proof/domain/v2-s2-003-pr1-validation.md) |

## What it is for

A V1 release is installed with a values file somebody wrote by hand, and that file
restates what the WorkloadContract already says: the runtime image, the model's pins, the
owner, the resources. Two copies of one intent drift, and nothing says which one a release
used. The renderer removes the second copy. It reads the context the boundary built - every
value with its one owner - and writes the chart values those owners decide, so the
contract is the only place the workload's intent is written.

It extends the chart's values contract rather than defining a format beside it. Every value
it writes is one [`values.schema.json`](../../charts/inferops-llm/values.schema.json)
already defines; every value it does not write keeps the chart's own default or comes from
a hand-written file. The chart, its templates, and its schema are unchanged.

## What it produces

For the reference workload - the [`synchronous-llm` contract fixture](../../contracts/workload/examples/valid/synchronous-llm-local.yaml)
on either [local binding](../../contracts/environment/examples/valid/local-kind.yaml), with
the chart's API defaults - the output is the committed golden file, byte for byte:

```yaml
# Generated Helm values for the inferops-llm chart, version 0.3.0.
# Do not edit by hand: change the WorkloadContract, the EnvironmentBinding, or
# the platform defaults they were rendered from, and render them again.
api:
  drainTimeoutMs: 15000
  maxOutputTokens: 128
  replicaCount: 1
  requestTimeoutMs: 120000
model:
  artifact:
    fileName: "Qwen3-1.7B-Q8_0.gguf"
    repository: "Qwen/Qwen3-1.7B-GGUF"
    sha256: "sha256:061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a"
    sizeBytes: 1834426016
  cache:
    claimName: "inferops-model-cache"
  identifier: "qwen3-1-7b-q8-0"
  revision: "90862c4b9d2787eaed51d12237eafdfe7c5f6077"
ownership:
  costCenter: "demo-cost-center"
  owner: "team-platform-demo"
  tenant: "demo"
  workloadId: "support-assistant"
  workloadVersion: "0.1.0"
profile: "real"
runtime:
  image:
    digest: "sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384"
    repository: "ghcr.io/ggml-org/llama.cpp"
  replicaCount: 1
  resources:
    limits:
      cpu: "6"
      memory: "3Gi"
security:
  secretRefs: []
telemetry:
  deploymentEnvironment: "local"
  enabled: true
```

The two local bindings render the same bytes. They differ only in the cluster provider and
the GitOps destination, and neither is a chart value. A test asserts both facts.

## Where every value goes

Every one of the context's 44 values has one disposition, and a test fails if the context
gains a value this table does not name:

- **`rendered`** - written to the chart values named. 24 values, written to 25 chart values:
  the runtime image reference is split at its digest.
- **`constrained`** - not written, because the chart has no setting for it, and refused
  unless it asks for what the chart already does. 8 values.
- **`not-rendered`** - not written, and no chart setting depends on it. 12 values.

A test compares this table with the code, row for row.

<!-- The table below is generated from HELM_VALUE_DISPOSITIONS. -->

| Context value | Disposition | Chart values | Why |
|---|---|---|---|
| `workload.id` | `rendered` | `ownership.workloadId` | The chart value of the same meaning |
| `workload.version` | `rendered` | `ownership.workloadVersion` | The chart value of the same meaning |
| `workload.owner` | `rendered` | `ownership.owner` | The chart value of the same meaning |
| `workload.profile` | `rendered` | `profile` | Synchronous-llm is the chart's real profile; the chart derives the serving capability and the adapter from it |
| `workload.environment` | `rendered` | `telemetry.deploymentEnvironment` | The environment every emitted record carries |
| `model.servingCapability` | `not-rendered` | - | The chart derives the capability from its profile, and the boundary already requires the native capability for this profile |
| `model.ref` | `rendered` | `model.identifier` | The platform identifier a caller's model member is checked against |
| `model.runtimeProfile` | `constrained` | - | The chart configures one runtime sizing, so only that sizing is accepted |
| `resources.cpu` | `rendered` | `runtime.resources.limits.cpu` | The ceiling the runtime runs under; the request stays the chart's |
| `resources.memory` | `rendered` | `runtime.resources.limits.memory` | The ceiling the runtime runs under; the request stays the chart's |
| `resources.accelerator.type` | `constrained` | - | The chart requests no accelerator, so only none is accepted |
| `resources.accelerator.count` | `constrained` | - | The chart requests no accelerator, so only a count of zero is accepted |
| `serving.replicas.minimum` | `rendered` | `runtime.replicaCount` | The chart runs a fixed replica count, so the range must be one number |
| `serving.replicas.maximum` | `constrained` | - | The chart has no autoscaler, so the maximum must equal the minimum |
| `integrations.telemetry.capabilityRef` | `rendered` | `telemetry.enabled` | The platform's telemetry is the chart's own, so declaring it enables it; another capability is refused |
| `integrations.telemetry.required` | `not-rendered` | - | Telemetry is enabled for every workload, which satisfies either answer |
| `integrations.modelAccess.capabilityRef` | `constrained` | - | The chart wires no model-access or evaluation capability, so declaring one is refused rather than dropped |
| `integrations.modelAccess.required` | `constrained` | - | The chart wires no model-access or evaluation capability, so declaring one is refused rather than dropped |
| `integrations.evaluation.capabilityRef` | `constrained` | - | The chart wires no model-access or evaluation capability, so declaring one is refused rather than dropped |
| `integrations.evaluation.required` | `constrained` | - | The chart wires no model-access or evaluation capability, so declaring one is refused rather than dropped |
| `security.dataClassification` | `not-rendered` | - | No chart setting acts on a classification, and no policy engine reads one |
| `security.secretRefs` | `rendered` | `security.secretRefs` | Rendered empty; a declared reference is refused, because no accepted rule maps a contract locator to the chart's secret binding |
| `attribution.tenant` | `rendered` | `ownership.tenant` | The chart value of the same meaning |
| `attribution.costCenter` | `rendered` | `ownership.costCenter` | The chart value of the same meaning |
| `evidence.runbookRef` | `not-rendered` | - | A documentation reference; no chart setting reads it |
| `evidence.proofRefs` | `not-rendered` | - | Documentation references; no chart setting reads them |
| `runtime.imageReference` | `rendered` | `runtime.image.repository`, `runtime.image.digest` | Split at its digest, because the chart pins the repository and the digest as two values |
| `model.artifact.repository` | `rendered` | `model.artifact.repository` | The chart value of the same meaning |
| `model.artifact.revision` | `rendered` | `model.revision` | The chart derives the in-claim directory from it |
| `model.artifact.file` | `rendered` | `model.artifact.fileName` | The chart value of the same meaning |
| `model.artifact.sizeBytes` | `rendered` | `model.artifact.sizeBytes` | The chart value of the same meaning |
| `model.artifact.sha256` | `rendered` | `model.artifact.sha256` | The chart value of the same meaning |
| `mock.ciOnly` | `not-rendered` | - | The mock profile's block; the renderer takes the synchronous profile only, so no context it renders holds one |
| `mock.determinism` | `not-rendered` | - | The mock profile's block; the renderer takes the synchronous profile only, so no context it renders holds one |
| `mock.fixtureRef` | `not-rendered` | - | The mock profile's block; the renderer takes the synchronous profile only, so no context it renders holds one |
| `api.requestTimeoutMs` | `rendered` | `api.requestTimeoutMs` | The chart value of the same meaning |
| `api.drainTimeoutMs` | `rendered` | `api.drainTimeoutMs` | The chart value of the same meaning |
| `api.maxOutputTokens` | `rendered` | `api.maxOutputTokens` | The chart value of the same meaning |
| `destination.clusterProvider` | `not-rendered` | - | Selects the cluster a release is installed into; not a chart value |
| `destination.namespace` | `not-rendered` | - | The release namespace is an install argument, not a value, and the chart checks its prefix itself |
| `modelCache.class` | `not-rendered` | - | The chart mounts an existing claim, the one class this binding version has |
| `modelCache.claimName` | `rendered` | `model.cache.claimName` | The existing claim the runtime mounts |
| `api.replicas` | `rendered` | `api.replicaCount` | The chart value of the same meaning |
| `gitops.destinationPath` | `not-rendered` | - | Where a release is written, not something a release reads |

## The canonical form

The values are YAML because Helm reads YAML. The distribution has no runtime dependency, so
[`values_yaml`](../../src/inferops/domain/render/values_yaml.py) writes it, with one
spelling for each value:

- mappings in block style, **keys sorted** by code point, two spaces per level; lists in
  block style, in order; `{}` and `[]` for empty ones;
- **every string double-quoted**, with only `\` and `"` escaped. A plain scalar is read by
  its shape - `yes` and `on` as booleans, `1e3` as a number, `2026-09-30` as a date - and
  quoting every string removes that question rather than answering it value by value;
- integers in decimal within +/-(2^53 - 1), booleans as `true` and `false`;
- LF line endings, one final newline, and the fixed three-line header above. The header
  holds no revision, date, or identifier.

What has no single spelling is refused, with its location and never its value: a string
holding anything but printable ASCII, a key that is not a plain identifier or is a word YAML
1.1 reads as a boolean or a null, `None`, a float, a nested list, or any other type. Nothing
the renderer writes needs one: every chart string it writes is ASCII by the chart's own
pattern. A test round-trips 29 strings that a plain scalar would misread.

The same context gives the same bytes: whatever order the bindings arrive in, under two hash
seeds in two interpreters, and with every clock, random source, and environment read patched
to fail. The renderer's revision names the commit it runs from and takes no part in the
values. `V2-S2-001-PR1` left open how the values file is hashed; `V2-S2-001-PR2` decided
it, by its bytes, and bound the values to a release - the next section.

## The generated release

`generate_release` runs the whole path, in [`generation`](../../src/inferops/domain/render/generation.py):
the boundary for the renderer's support, the renderer, and `record_release` with the
values file's name and digest. It returns a `GeneratedRelease` - the release, the values,
and both files' exact bytes - and writes nothing. Each stage runs only once the one before
it passed, so a refusal leaves nothing to write: `RenderRefused` from the boundary or the
renderer, with the caller's request context on every finding, or `ReleaseNotRecordedError`
when the values rendered and the release naming them would be refused - a binding named
with a credential-shaped part, for one, which no chart value carries and a release does.

**Two files, each in one spelling:**

| File | Holds | Digest |
|---|---|---|
| `values.generated.yaml` | The generated values, in the canonical form above | Recorded in the release as `output.helmValues.sha256` |
| `rendered-workload-release.yaml` | The RenderedWorkloadRelease naming them, in the same canonical form, under a fixed two-line header | Reported as `GeneratedRelease.release_sha256` |

Both digests are the SHA-256 of the file's exact bytes - what `sha256sum` prints. A source
document is hashed by its value because a person writes it; a generated file is hashed by
its bytes because the platform writes it in one spelling, so any edit, even one Helm would
read the same, moves the digest. The reasons are in [the release document](../contracts/rendered-workload-release.md#generated-files-and-their-digests).
That digest is not `canonical_release`'s, which hashes the release's JSON value to compare
two releases as documents; a test holds the two apart.

For the reference workload on the `local-kind` binding the release is the committed golden
file, byte for byte, in the release directory `support-assistant-local-kind/`. Its contract and binding digests are computed from the committed
fixtures; its two revisions are the suite's placeholders, so it is a test render, not the
record of a render at any commit:

```yaml
# Generated RenderedWorkloadRelease: what the values beside it were rendered from.
# Do not edit by hand: render the release again from the sources it names.
apiVersion: "inferops.io/v1alpha1"
kind: "RenderedWorkloadRelease"
metadata:
  releaseId: "b82be6908264d1ad088aec5a3e57930aeb1df3ea0967cd9e6951df84b5b6f79f"
  workloadId: "support-assistant"
  workloadVersion: "0.1.0"
output:
  helmValues:
    path: "values.generated.yaml"
    sha256: "137a97b9211a7e92ce82f8423063cfba6b828f51ac3a33fc2ab0d714396301d2"
source:
  contract:
    apiVersion: "inferops.io/v1alpha1"
    sha256: "56f73f78a6d741db15b28061b01f323935365c0d63b4d84b936e5ca6ca709c0d"
  environmentBinding:
    apiVersion: "inferops.io/v1alpha1"
    environment: "local"
    name: "local-kind"
    sha256: "1a6c9e9f3448e2a7a072ac653e1b180c9684814b26aff5842ecdb752923c0a7d"
  platformDefaults:
    revision: "bbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbbb"
  renderer:
    revision: "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"
```

**What a change moves.** A test makes nine changes one at a time and asserts exactly which
values and which release fields each moves. A claim-relevant intent - the contract's
replica count - moves `runtime.replicaCount`, the contract digest, the values digest, and
the release identifier, and nothing else. A contract or binding change no chart value
carries - the description, the runbook reference, the GitOps destination - moves the
source digest and the identifier, and the values not at all. A new renderer or
platform-defaults revision moves that revision and the identifier, and the values not at
all. One shape is measured rather than hidden, as a coverage limitation: platform-defaults
content changed while the caller **falsely retains the same stated revision** moves the
rendered values and their digest and **not** the release identifier. The caller supplies
the defaults and, separately, the revision they are said to come from, and nothing reads
the defaults from a committed source bound to that revision. So a release records the
**asserted** platform-defaults revision; it does not prove the defaults it was rendered
from were the ones at that revision. The test that measures this asserts the difference,
and is not to be turned into an equality: it changes when a later change reconstructs the
defaults from the revision a release names, and not before.

**Determinism.** Two generations written to two clean directories are the same bytes, whatever
order the bindings arrive in, in two interpreters under two hash seeds, and with every
clock, random source, and environment read patched to fail - the write included. No string
in either file is credential-shaped, and neither holds a timestamp or a random identifier.

### What a generated file can carry

The property claimed for both files is bounded, and it is the one the tests hold:

- **No supported secret-bearing field, and no secret reference, reaches either file.** A
  contract that declares a secret reference is refused before anything is generated, under
  `render-capability-unsupported`, and `security.secretRefs` is written empty.
- **Every string comes from an explicitly owned field.** The values file holds exactly the
  chart values the disposition table renders, and the release file exactly the fields
  [the provenance input-trust policy](../contracts/rendered-workload-release.md#provenance-input-trust)
  classifies; a test compares both files' leaves with the two tables. Markers planted in
  input content no row renders - the contract's description and annotations, the
  binding's owner, GitOps path, and namespace - reach neither file.
- **Known credential shapes are refused, and not quoted.** A string with a part beginning
  with a published credential prefix is refused by the renderer
  (`render-value-credential-shaped`) or when the release is recorded
  (`release-value-credential-shaped`), and neither refusal repeats it.
- **The golden files are scanned.** No path exception in the repository's secret-scanning
  configuration covers them, and a test holds that.

**The input-trust limitation stands.** Many rendered values and the release's
`public-identity` fields are names an author chose - a workload's name, version, owner,
tenant, and cost centre, a binding's name, a model's identifier - and they are public by
policy. A secret deliberately written as an otherwise valid value of one of them has that
value's shape, and syntax cannot prove it non-secret: a test generates a release whose
binding is named with a lowercase token that has no published credential prefix, and it
passes. So this page does not claim that a generated file contains no secret value. It
claims the four properties above.

### Writing it

`write_release(generated, directory)` in [`writing`](../../src/inferops/domain/render/writing.py),
the one module of the render package that touches a file, writes both files or neither:

- `directory` must not exist, and its parent must. An existing directory is refused,
  even an empty one, so an earlier release is never half-replaced.
- The files are written into a staging directory beside it, `.<name>.partial`, created
  exclusively; each file is created exclusively, written as bytes, and flushed; both are
  read back and compared with what was meant; then the staging directory is renamed to
  `directory` in one operation.
- If a step fails, what was staged is removed and the error raised. If that removal fails
  too, or the process is killed first, the staging directory is left under its own name,
  the error names it, and the next write to the same directory refuses to start until it
  is removed. A test removes it and writes again.

Both files or neither is a promise about a running system and a process that fails or is
killed, not about a crash. Each file's bytes are flushed, but no directory is - not the
staging directory, not the parent after the rename - so after a power loss or an
operating-system crash the output directory may be missing, a leftover staging directory
may hold both files, one, or none, and a file system that does not order its metadata
writes could show the output directory without both files. A release read after a crash
is checked against its digests rather than trusted because its directory exists. On POSIX
systems a rename replaces an *empty* directory created at the target between the check
and the rename. Where a release directory lives is the caller's choice.

**An exemption, stated.** Every other module under `src/inferops` opens no path, so the
distribution works from a wheel with no file system, and
[an architecture test](../../tests/architecture/test_domain_dependency_boundary.py) enforces
it. `writing` is exempt from that test by name, because writing a caller's files is its
purpose; the same suite holds that nothing it runs on import - a module-level
statement, a decorator, a default value - names a file-system operation, so it touches a
file only inside a function a caller invokes. The rule otherwise stands - an earlier change left a process
memory metric unemitted rather than read a path for it, and that reasoning is unchanged.

## Verifying a committed release

Added by `V2-S2-002-PR1`. A generated release committed to this repository is worth reading
only while it is what its sources produce. [`tools/generated_release`](../../tools/generated_release/core.py)
checks that. It is also the only path in this repository that regenerates a committed
release.

**Declared inputs.** `DECLARED_RELEASES` names each committed release directory and the
inputs it is derived from: the WorkloadContract, the EnvironmentBindings offered to the
boundary and the name of the one to select, the file the platform defaults are read from,
and the renderer and platform-defaults revisions. The check derives both files again from
those inputs through `generate_release` and compares the bytes. It trusts nothing in the
committed release: the revisions come from the declaration, not from the release. One
release is declared:

| Release | Contract | Binding | Platform defaults | Revisions |
|---|---|---|---|---|
| `support-assistant-local-kind` | `contracts/workload/examples/valid/synchronous-llm-local.yaml` | `local-kind`, the only binding offered | The `api` block of `charts/inferops-llm/values.yaml` | Placeholders: `a` and `b`, each repeated 40 times |

**The workflow.**

```sh
# Verify: compare every committed release with what its declared inputs derive.
uv run --locked python -m tools.generated_release --check
# After a deliberate change to a declared input: read the diff, then regenerate by name.
uv run --locked python -m tools.generated_release --write support-assistant-local-kind
# Print every declared release and its inputs.
uv run --locked python -m tools.generated_release --list
```

`--check` writes nothing and repairs nothing. It exits 0 when every release is what its
inputs derive, and 1 when one is not. It reports each drifted release with the rule it
breaks; each release field that differs, with what the difference means and both values;
a unified diff from the committed file to the derived one; and the command that
regenerates it. When a finding is one regeneration refuses - a stray entry, a left-over
staging directory, or sources that no longer render - it names what to resolve first
instead of the command. `--write` regenerates only the releases it is given by name. It
refuses a release path that is a file or a symbolic link, a directory that holds anything
the platform did not write, and a staging directory left beside one, and touches nothing.
Otherwise it removes the two committed files and their directory, then writes both files
again through `write_release`, which writes both or neither. The old release is therefore
gone before the new one is written: if that write fails, the command says so, the
directory is absent rather than half written, and running `--write` again, or restoring
the directory from Git, brings it back. Regeneration replaces a hand edit without asking,
so read the diff first. The default-lane test suite runs the same check over every
declared release, so a stale or hand-edited release fails the build that introduces it.

**The rules**, in the order a finding is reported:

| Rule | Statement |
|---|---|
| `generated-release-missing` | A declared release directory exists. |
| `generated-release-file-missing` | A release directory holds both generated files. |
| `generated-release-unexpected-entry` | A release path is a directory that holds the two generated files and nothing else. |
| `generated-release-staging-left` | No staging directory from an unfinished write is left beside a release. |
| `generated-release-sources-refused` | The declared sources of a release still derive a release. |
| `generated-release-values-unrecorded` | The committed values file's SHA-256 is the digest the committed release records. |
| `generated-release-field-drifted` | Each field of the committed release is the field its declared sources derive. |
| `generated-release-file-drifted` | Each committed file is, byte for byte, the file its declared sources derive. |

**What each kind of drift is reported as.** The suite plants each of these in a copy of
the declared inputs:

- **A hand edit to the values file** - a value, a comment, trailing whitespace, an
  unquoted string, or CRLF line endings - is `generated-release-file-drifted` and
  `generated-release-values-unrecorded`: the release no longer records those bytes. A
  CRLF checkout is named as a line-ending difference, without a diff.
- **A source changed after generation** is `generated-release-field-drifted` at
  `source.contract.sha256` or `source.environmentBinding.sha256`, with the recorded
  digest named as stale, and at `metadata.releaseId`. A change that moves a chart value,
  such as the contract's replica count, also moves `output.helmValues.sha256` and the
  values file.
- **A release edited to name other provenance** - either revision, the identifier, the
  binding's name, the contract digest, the values file's path or digest - is reported at
  that field. An edit no field shows, such as one to the header comment, is still a
  drifted file.
- **Values and a release edited to agree** are consistent with each other and not with
  their sources: both files and `output.helmValues.sha256` are reported.
- **A release path that is a file or a symbolic link**, and a generated file that is a
  symbolic link, are `generated-release-unexpected-entry`: the platform writes neither, so
  neither is followed or compared. A generated file that is a link is also
  `generated-release-file-missing`, reported first, because the directory then does not
  hold that file. The symbolic-link cases skip on a host that cannot
  create a link, as an unprivileged Windows account cannot; the Linux runner runs them.
- **Sources that no longer render** are `generated-release-sources-refused`, with the
  boundary's or the renderer's refusal. A missing input file is the same rule. Nothing is
  compared, because there is nothing to compare with.

**Platform defaults, measured.** The reference release reads its defaults from the
chart's `api` block, as the generated-release suite does. A change to one of those values
is drift: the values file and `output.helmValues.sha256` move. `metadata.releaseId` does
not move, because the platform-defaults revision is declared, not derived from the
content. This is the [limitation measured above](#the-generated-release), now visible as
drift in a committed release; it is not closed.

**Decided here.**

- A release's inputs are declared in code beside the check, not in a file in the release
  directory. The directory holds what `write_release` writes and nothing else, which is
  what `generated-release-unexpected-entry` holds.
- The reference release moved from two golden files named with a prefix to a directory in
  the layout `write_release` produces, so the release's `output.helmValues.path` names a
  file that is beside it.
- `--write` takes release names and has no default. A drift that nobody named is
  reported, never repaired.

**What it does not check.**

- **That either revision names a commit**, or that the platform defaults are the ones at
  the declared revision. Nothing reads Git history, and nothing reconstructs the defaults.
- **A release nobody declared.** A test lists every tracked file named like a generated
  file and fails unless each is in a declared directory. A file Git does not track is not
  checked.
- **Helm.** The check compares files. The generated-release suite renders the values with
  Helm when Helm is on `PATH`.
- **Anything at runtime.** A pass is `C0`: the committed files agree with their committed
  sources. It does not establish that anything was installed or served.

## What it refuses

A context reaches the renderer only after the boundary accepted it, so every refusal here is
about the chart rather than the input. Each finding names the input by its role -
`contract`, `binding` for the selected binding, `platformDefaults` - and the path inside it,
and never quotes a value. Every finding is reported at once, in the boundary's order.

| Rule | Category | Code | Refuses |
|---|---|---|---|
| `render-capability-unsupported` | `value-unsupported` | `capability-unavailable` | A replica range, since the chart has no autoscaler; an accelerator; a runtime sizing other than `resource-conscious`; a telemetry capability other than `platform-telemetry`; a `modelAccess` or `evaluation` integration; a secret reference |
| `render-value-unsupported` | `value-unsupported` | `capability-unavailable` | A value outside the chart schema's constraint on the value it would be written to; a CPU or memory limit below the chart's runtime request |
| `render-value-credential-shaped` | `semantic-invalid` | `contract-invalid` | A string the renderer would write with a part beginning with a published credential prefix |
| `render-profile-unsupported`, `render-contract-version-unsupported`, `render-binding-version-unsupported` | as published | as published | A context outside the renderer's support. `render_with` refuses it before calling the renderer; `render` refuses it again for a context built without that check |

**The chart is narrower than the contract.** `CHART_VALUE_CONSTRAINTS` copies the chart
schema's constraint for each of the 25 values written, and a test reads the schema and fails
if one keyword differs. The contract accepts more than the chart in these places, and each
is refused here rather than by Helm. A test refuses an example of each through
`render_with`, except the last row's, which no accepted input reaches today:

| Contract accepts | Chart accepts | Example refused |
|---|---|---|
| `spec.environment` of `staging` or `production` | `dev`, `ci`, `local`, `test` | `staging` |
| A semantic version with pre-release or build identifiers, or a digest-pinned image reference | `MAJOR.MINOR.PATCH` only | `1.0.0-rc.1` |
| Quantities in `P`, `E`, `Pi`, `Ei`, and CPU in any suffix | CPU in cores or `m`; memory up to `T` and `Ti` | CPU `2k`, memory `1Pi` |
| A model repository of any depth | `owner/name` | `Qwen/Qwen3/GGUF` |
| A file name up to 255 characters | Up to 253 | A 254-character file name |
| A revision of 40 to 64 hexadecimal characters | Exactly 40 | A 64-character revision |
| Up to 100 replicas | Up to 16 | 17 |
| An image reference up to 512 characters | A repository up to 255 | None today: the compatibility matrix registers one runtime repository, and the boundary refuses any other as `runtime-unregistered` before the renderer sees it. A test measures that, and the check stays for the day the matrix registers a longer one |

### Decisions this change made

Each is a decision rather than a fact, recorded so a later change can revisit it on purpose.

- **Resources mean limits.** The contract's `cpu` and `memory` render to
  `runtime.resources.limits`. The runtime's requests stay the chart's - one CPU and `2Gi` -
  because they reserve what a local cluster can schedule: a request of the contract's six
  CPUs would not schedule on a host the environment scripts accept, which need four logical
  CPUs. That is the V1 release's own split. A limit below the chart's request is refused,
  because Kubernetes refuses a container whose request exceeds its limit.
- **Telemetry is enabled for every workload.** Declaring `platform-telemetry` renders
  `telemetry.enabled: true`. `required` is not rendered: `true` and `false` are both
  satisfied by telemetry that is on, and the platform does not operate a workload it cannot
  observe.
- **A secret reference is refused, not rendered.** The chart binds a named Kubernetes
  Secret key to an environment variable of the API; a contract names a provider, a locator,
  an owner, and a rotation duty. No accepted rule maps one to the other - which provider
  becomes which Secret, which variable a logical name becomes - and inventing one here would
  render a binding nobody decided. `security.secretRefs` is rendered empty, and a contract
  declaring any reference is refused. The committed
  [secret-reference example](../../contracts/workload/examples/valid/synchronous-llm-secret-refs.yaml)
  is refused for that reason, and a test says so.
- **One runtime sizing.** The chart configures one runtime - one CPU process, one slot,
  the settings the [runtime profile record](../serving/runtime-profile.local.v1.json)
  publishes - and the renderer reads that as `resource-conscious`. `balanced` and
  `throughput-oriented` ask for sizing no chart setting changes, so they are refused.
- **The environment label is the contract's.** `spec.environment` renders to
  `telemetry.deploymentEnvironment`. The V1 real fixture labels the laptop run `dev`; the
  reference contract declares `local`, so the generated release is labelled `local`. That
  is the one difference from V1 below.
- **Generated values carry no credential shape.** Generated values are meant for Git, so a
  string the renderer would write is refused if any part of it begins with a published
  credential prefix, whichever input supplied it. A binding's claim name is checked here
  for the first time; a binding value no renderer writes still is not.

## Hand-written values

A release needs values no input owns: the API image a contributor built and loaded, the
model's alias, licence, and download URL, and how the release runs on a host - how the claim
is filled and verified, whether its collector runs. Those stay in a hand-written file,
installed after the generated one. The reference workload's is
[`support-assistant-local.manual-values.yaml`](../../tests/domain/fixtures/helm-values/support-assistant-local.manual-values.yaml),
copied from the V1 real fixture with every generated value removed.

**A hand-written file may not repeat contract intent.** Helm merges values files in order,
and the last one wins, so a hand-written file could replace a generated value - or remove it
with a `null` - and nothing would say so. `manual_value_findings` refuses, with
`render-manual-value-generated` and the value's path, a hand-written value that:

- sets a generated value;
- sits beneath one, which replaces it with a mapping; or
- sits above one as anything but a non-empty mapping - a scalar, a list, a `null`, or an
  empty mapping at a generated value itself.

An empty mapping above a generated value merges nothing and is accepted, and so is a
sibling: `model.artifact.sourceUrl` beside the generated `model.artifact.repository`. A test
sets each of the 25 generated values in the committed file and gets exactly one finding for
each; the committed file gets none.

**Where the check is applied.** `admit_manual_values(generated, manual)` pairs generated
values with a hand-written document only when it has no such finding, and refuses with
every finding at once - each naming the path, never the value, and carrying the caller's
request context. The pair, `AdmittedHelmValues`, holds the hand-written half read-only and
runs the check again when it is built, on a deep, read-only copy it takes and keeps,
so a pair holds no hand-written value that overrides a generated one, however it was
built: a live view, a nested object changed later, or a document that answers a second
reading differently all leave the pair holding what was checked. A refusal names the
generated value's path - not a key the hand-written file placed beneath it, which could
itself be a credential - and never the value. The V1 comparison below renders exactly what
was admitted, not the file beside it.

**Which hand-written files are supported.** A hand-written values file is supported beside
generated values only when its name ends in `.manual-values.yaml`, the suffix
`MANUAL_VALUES_SUFFIX` publishes. A test walks the repository - skipping version control,
tool caches, build output, and local machine state - finds every file with that suffix,
and fails, naming the file and the paths, if one is not admitted; a second test shows a
newly added file that repeats a generated value fails it. Today there is one such file,
the reference workload's.

**What is not controlled.** A values file named any other way, one outside the repository,
or a value given on Helm's command line - `--set`, `--set-string`, `--set-file`, or
`--set-json` - is not checked by anything here, and the check cannot stop one being passed
to Helm beside generated values. For an admitted pair, the order Helm is given the two
files decides nothing, since neither sets a value the other does. No supported path installs
generated values yet; the deployment path that does is where such files would have to be
refused.

**What the check cannot see.** The download URL repeats the repository, revision, and file
the contract pins, and nothing compares them: the acquisition job's content hash, which the
generated values supply, is what refuses a different file. And a hand-written
`runtime.resources.requests` above the generated limit is not refused here; Kubernetes
refuses it at install.

## Compared with the V1 real release

The generated file and the reference hand-written file together describe the V1 real
release, but for its environment label. Three tests check it, at two layers:

- **Values.** Merged over the chart's defaults the way Helm merges them, the two files equal
  the V1 [real fixture](../../charts/inferops-llm/ci/real-values.yaml) merged the same way,
  except `telemetry.deploymentEnvironment`: `dev` there, `local` here. Both merges validate
  against the chart's values schema, and so do the generated values alone over the defaults.
- **Render.** With `helm` on `PATH`, `helm template` of the two files is byte-identical to
  `helm template` of the V1 fixture with `telemetry.deploymentEnvironment=local`. Against the
  committed V1 render, exactly two lines move - the environment variable and the scrape
  relabel that carry the label - plus the three `inferops.io/configuration-checksum`
  annotations derived from the configuration that holds it.

Since `V2-S2-001-PR2` a test runs `helm template` over the values file `write_release`
wrote - the file on disk, not the text in memory - with the hand-written file as
`admit_manual_values` admitted it, and gets the same bytes as the V1 fixture with the
contract's environment. Both layers consume the reference hand-written file only through
that check.

That is compatibility of rendered manifests, at C0. **Nothing was installed.** Whether the
generated release serves the V1 workload on a cluster is for a later change to show,
on a cluster.

`V2-S2-003-PR1` records, value by value, who owns each value of that comparison now - the
contract, the binding, the platform defaults, or the hand-written file - in [V1 synchronous
compatibility](v1-synchronous-compatibility.md), and a test holds that record against the
code. It also renders the committed generated release with the hand-written file, and lints
the pair under `--strict`, in the chart suite, which the CI job that installs a pinned Helm
runs without a skip.

## Not applied yet

| Not applied | Why | What it needs |
|---|---|---|
| A delivery workflow writes a generated release | The one command that writes a release regenerates a declared release in this repository when a contributor names it; nothing writes one for delivery | A later change |
| A revision a release records names a commit | Neither the declaration nor the drift check reads Git history, and the reference release's revisions are placeholders | A check against the repository the release is committed in |
| A secret reference is rendered | No accepted mapping from a contract locator to the chart's secret binding | A decision on that mapping |
| The `mock-llm` profile is rendered | The renderer declares the synchronous profile only, as the story scopes it | A renderer, or a support change, for the mock profile |
| The platform defaults are read from a committed file | No defaults file exists; the caller supplies the defaults and states their revision, as at the boundary. Until then defaults content changed under a falsely retained revision moves the values digest and not the release identifier, and a test measures it | A change that reconstructs the defaults from a committed source bound to the revision a release records, before any source verification relies on that revision. The drift check reads the reference release's defaults from the chart's `api` block, so a change to them is reported as drift, and the declared revision does not move |
| A hand-written values file outside the supported suffix is checked | Only files named with `.manual-values.yaml` are found and admitted; nothing installs generated values, so there is no install path to refuse others on | The deployment path that installs generated values |
| The API image is generated | It is a contributor's local build, published to no registry | A published API image |
| The download URL agrees with the contract's pins | The contract has no field for it; the content hash is the check | A contract field for the source, or a derivation rule |
| A data classification changes a render | No chart setting or policy engine acts on one | A policy engine |

## What this does not establish

- **That anything was installed.** The renders were compared as files. No cluster read
  them, and no generated release has served a request.
- **That a release used generated values.** The values a release is installed with are
  still written by hand: generated values and their release are written only to a
  directory a caller names, and nothing installs from one.
  `deployment-values-derive-only-from-a-validated-document` stays planned.
- **That a release directory nobody declared is still what was written.** The writer reads
  both files back before it moves them into place, and the drift check compares every
  declared committed release with its sources. A directory outside the declaration, or
  outside Git, is not checked.
- **That the hand-written half is safe.** The check refuses a hand-written value that
  repeats a generated one; it does not judge the others. It is enforced for every
  repository file named as a supported hand-written values file, and for any document a
  caller admits; a values file passed to Helm by another route is not checked.
- **That a generated file holds no secret value.** What holds is the bounded property in
  [What a generated file can carry](#what-a-generated-file-can-carry): no supported
  secret-bearing field or secret reference, only owned fields, known credential shapes
  refused. A secret disguised as a valid public name is the input-trust limitation.
- **That the platform defaults came from the revision a release names.** The revision is
  the caller's assertion, and a test measures what that allows.
- **Anything beyond the reference inputs' shape.** The golden file and the V1 comparison
  are one contract on two bindings of one environment.

## Validation

```sh
uv run --locked python -m pytest tests/domain/test_helm_values_renderer.py tests/domain/test_generated_release.py tests/domain/test_generated_release_drift.py -q
uv run --locked python -m tools.generated_release --check
uv run --locked python -m pytest tests/domain tests/architecture -q
uv run --locked ruff check . && uv run --locked ruff format --check . && uv run --locked mypy
```
