# RenderedWorkloadRelease examples

Fixtures for [the RenderedWorkloadRelease v1alpha1 schema](../rendered-workload-release.v1alpha1.schema.json).
Every file under `valid/` must validate and every file under `invalid/` must be
refused; a failure either way is a defect in the schema, the fixture, or the change
that broke one of them.

These are **contract examples, not records of a release.** Nothing produced them - they
were written by hand, with placeholder digests, before anything generated a release - no
values file sits beside them, and nothing was installed or run with either. None of them is evidence about the workload or the
environment it names.

| Fixture | Workload | Binding | What it demonstrates |
|---|---|---|---|
| [`valid/support-assistant-local-docker-desktop.yaml`](valid/support-assistant-local-docker-desktop.yaml) | `support-assistant` `0.1.0` | `local` / `local-docker-desktop` | The provenance a release of the committed synchronous contract fixture, rendered with the reference provider's binding fixture, would carry |
| [`valid/support-assistant-local-kind.yaml`](valid/support-assistant-local-kind.yaml) | `support-assistant` `0.1.0` | `local` / `local-kind` | The same contract with the other binding: the binding's name and digest differ, and so does the release ID |

**The identities are real and the digests are not.** Each valid fixture's workload ID
and version are the committed synchronous WorkloadContract fixture's, and its binding
reference is a committed EnvironmentBinding fixture's identity; a test holds all three
there. Every digest and revision is a single repeated character — well formed, naming
nothing — because they were written by hand before anything generated a release. The
one release generated for values a renderer produced is a test's golden file, under
`tests/domain/fixtures/helm-values/`, at placeholder revisions of its own. How a
contract or a binding is hashed is now [decided](../../../docs/contracts/rendered-workload-release.md#canonical-form-and-source-digests),
and the fixtures were deliberately not changed to carry real digests: beside the
documents they name, the platform domain refuses each for exactly its two placeholder
digests, and a test asserts that, so neither can be read as the record of a render.
Each release ID is
the one [the published derivation rule](../../../docs/contracts/rendered-workload-release.md#release-identity)
gives for the values above it, and a test recomputes it. A fixture's file name is its
workload ID and its binding's name.

## Invalid fixtures

Every file under `invalid/` must be refused for exactly the canonical error code, rule
identifier, and field location recorded in
[`invalid/expected-rejections.json`](invalid/expected-rejections.json), compared field
by field on every run.

Every rejection below is **structural**: the published JSON Schema alone refuses the
document, so any draft 2020-12 validator in any language reaches the same verdict. The
rules that need a recomputation or a second document are the platform domain's, not the
schema's, and have no fixture here;
[the contract document](../../../docs/contracts/rendered-workload-release.md#provenance-rules-the-platform-domain-applies)
lists them, and the rules nothing applies yet.

| Fixture | Refused for |
|---|---|
| [`invalid/unsupported-api-version.yaml`](invalid/unsupported-api-version.yaml) | A release version that does not exist. The one fixture carrying `version-unsupported` |
| [`invalid/not-a-rendered-release.yaml`](invalid/not-a-rendered-release.yaml) | A release body labelled with another contract's `kind` |
| [`invalid/missing-required-values.yaml`](invalid/missing-required-values.yaml) | No release ID, no renderer, and a values file named but not pinned |
| [`invalid/uncontrolled-timestamp.yaml`](invalid/uncontrolled-timestamp.yaml) | A render timestamp beside the release identity and in a block of its own |
| [`invalid/random-release-id.yaml`](invalid/random-release-id.yaml) | A release ID that is a random UUID |
| [`invalid/malformed-digests.yaml`](invalid/malformed-digests.yaml) | Three digests in the wrong spelling — uppercase, `sha256:`-prefixed, SHA-1 length |
| [`invalid/mutable-revisions.yaml`](invalid/mutable-revisions.yaml) | Inputs named by labels that move — `latest`, a branch, an abbreviated commit |
| [`invalid/malformed-identifiers.yaml`](invalid/malformed-identifiers.yaml) | A workload ID and a binding name that are not DNS labels |
| [`invalid/identifier-too-long.yaml`](invalid/identifier-too-long.yaml) | A workload ID and a binding name one character over the DNS label bound |
| [`invalid/unsupported-vocabulary.yaml`](invalid/unsupported-vocabulary.yaml) | A contract version, a binding version, and an environment outside their vocabularies |
| [`invalid/wrong-json-types.yaml`](invalid/wrong-json-types.yaml) | An unquoted digest read as a number, and a revision written as a list |
| [`invalid/values-outside-the-release.yaml`](invalid/values-outside-the-release.yaml) | A values reference that climbs out of the release's directory |
| [`invalid/document-content-in-release.yaml`](invalid/document-content-in-release.yaml) | A binding's facts and the generated values copied in beside their digests |
| [`invalid/secret-value-in-a-field.yaml`](invalid/secret-value-in-a-field.yaml) | A token and a password in fields a release does not have |
| [`invalid/secret-value-in-an-identifier.yaml`](invalid/secret-value-in-an-identifier.yaml) | Three credential-shaped strings in identity fields |

**No invalid fixture contains a credential.** Where one has to look like a credential,
it uses a vendor's own published placeholder, a public standard header, or a
zero-padded synthetic value, and its header says which. The UUID and the abbreviated
commit identifier are fixed strings that identify nothing.

## Adding a fixture

A valid fixture is picked up from `valid/*.yaml` by
[the release suite](../../../tests/contracts/test_rendered_workload_release_v1alpha1.py).
It must validate, stay inside the JSON-representable subset of YAML, contain no field
name that could hold a secret, be named after its workload ID and binding name, name a
committed contract and binding fixture, and carry the release ID the derivation rule
gives.

An invalid fixture is picked up from `invalid/*.yaml`, and adding one means adding its
entry to the manifest in the same change. A fixture the manifest does not know about,
or a manifest entry with no fixture, is a test failure. A valid fixture is never edited
to make a change pass: a change that would invalidate one is breaking by definition.
