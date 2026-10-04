# EnvironmentBinding examples

Fixtures for [the EnvironmentBinding v1alpha1 schema](../environment-binding.v1alpha1.schema.json).
Every file under `valid/` must validate and every file under `invalid/` must be
refused; a failure either way is a defect in the schema, the fixture, or the change
that broke one of them.

These are **contract examples, not configuration anything reads.** No controller or
script in this repository consumes a binding - the platform domain's render boundary
reads parsed bindings into a render context, and the Helm values renderer generates
values from that context, written only where a caller names - and the GitOps
destination of `local-docker-desktop` is the directory that holds one generated
release, under `workloads/<workload id>/`, while the `local-kind` destination names
no directory. Nothing reconciles either.
Nothing here has been deployed, and none of it is evidence about the environment it
describes.

| Fixture | Environment | Provider | What it demonstrates |
|---|---|---|---|
| [`valid/local-docker-desktop.yaml`](valid/local-docker-desktop.yaml) | `local` | `docker-desktop` | The facts of the V1 reference environment, each copied from the record that owns it |
| [`valid/local-kind.yaml`](valid/local-kind.yaml) | `local` | `kind` | A second binding for the same environment, differing only in provider and GitOps destination |

Each valid fixture is held to the records it copies: the namespace to the release
lifecycle's namespace and the prerequisite layer's default, the claim name to the
prerequisite layer's default and the chart's real render values, and the provider to
the providers the local cluster provider contract supports. A drift in any of them is
a test failure. A fixture's file name is its `metadata.name`.

## Invalid fixtures

Every file under `invalid/` must be refused for exactly the canonical error code, rule
identifier, and field location recorded in
[`invalid/expected-rejections.json`](invalid/expected-rejections.json), compared field
by field on every run.

Every rejection below is **structural**: the published JSON Schema alone refuses the
document, so any draft 2020-12 validator in any language reaches the same verdict. The
binding has no semantic layer yet, and
[the contract document](../../../docs/contracts/environment-binding.md#rules-that-are-not-applied-yet)
lists the rules that would need one.

| Fixture | Refused for |
|---|---|
| [`invalid/unsupported-api-version.yaml`](invalid/unsupported-api-version.yaml) | A binding version that does not exist. The one fixture carrying `version-unsupported` |
| [`invalid/not-an-environment-binding.yaml`](invalid/not-an-environment-binding.yaml) | A binding body labelled with another contract's `kind` |
| [`invalid/missing-required-values.yaml`](invalid/missing-required-values.yaml) | No owner, no namespace, and no platform block |
| [`invalid/malformed-identifiers.yaml`](invalid/malformed-identifiers.yaml) | Four identifiers malformed at once — name, owner, namespace, claim |
| [`invalid/unsupported-vocabulary.yaml`](invalid/unsupported-vocabulary.yaml) | An environment, a provider, and a cache class outside their vocabularies |
| [`invalid/api-replicas-out-of-range.yaml`](invalid/api-replicas-out-of-range.yaml) | Zero platform API replicas |
| [`invalid/api-replicas-not-an-integer.yaml`](invalid/api-replicas-not-an-integer.yaml) | A replica count written as a string |
| [`invalid/gitops-path-outside-the-repository.yaml`](invalid/gitops-path-outside-the-repository.yaml) | A GitOps destination that climbs out of the repository |
| [`invalid/workload-intent-in-binding.yaml`](invalid/workload-intent-in-binding.yaml) | A binding setting the serving replica range, the model, and the runtime's replica count — WorkloadContract values |
| [`invalid/secret-value-in-a-field.yaml`](invalid/secret-value-in-a-field.yaml) | A cluster token and repository credentials in fields a binding does not have |
| [`invalid/secret-value-in-an-identifier.yaml`](invalid/secret-value-in-an-identifier.yaml) | Two credential-shaped strings in identifier fields |

**No invalid fixture contains a credential.** Where one has to look like a credential,
it uses a vendor's own published placeholder, a public standard header, or a fixed
synthetic string, and its header says which.

## Adding a fixture

A valid fixture is picked up from `valid/*.yaml` by
[the binding suite](../../../tests/contracts/test_environment_binding_v1alpha1.py). It
must validate, stay inside the JSON-representable subset of YAML, contain no field name
that could hold a secret, be named after its `metadata.name`, and copy every
environment fact from the record that owns it.

An invalid fixture is picked up from `invalid/*.yaml`, and adding one means adding its
entry to the manifest in the same change. A fixture the manifest does not know about,
or a manifest entry with no fixture, is a test failure. A valid fixture is never edited
to make a change pass: a change that would invalidate one is breaking by definition.
