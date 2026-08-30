"""The contract a generated `mock-llm` workload declares.

One template, held as text rather than as a file beside this module. Nothing
under ``src/inferops`` reads a path — that is an accepted architecture rule, and
it is what keeps this distribution usable from a wheel with no repository around
it — so the template travels as a module constant.

Rendered by :mod:`inferops.scaffolding.template`. Every placeholder below is a
:class:`string.Template` placeholder and must have a value in that module's
substitution mapping; a test asserts both directions, and a placeholder with no
value raises rather than surviving into generated output.
"""

from __future__ import annotations

from typing import Final

#: Where this template's output goes inside a generated workload.
OUTPUT_PATH: Final = "workload.yaml"

TEMPLATE: Final = """
# THIS IS A MOCK WORKLOAD. It replays a committed fixture and loads no weights.
# It cannot certify real serving behaviour, and the schema is built so that it
# cannot be edited into something that looks as though it could: the mock-llm
# profile is pinned to the ci environment and to the mock serving capability, and
# it is forbidden from citing real-runtime proof.
#
# The rule this document obeys is in docs/serving/mock-and-real-boundary.md.
# Generated from the InferOps workload template. Edit it as you would any other
# committed document; nothing regenerates it.
apiVersion: inferops.io/v1alpha1
kind: WorkloadContract

metadata:
  name: ${name}
  version: ${version}
  owner: ${owner}
  description: ${description}

spec:
  profile: mock-llm
  environment: ${environment}

  model:
    servingCapability: ${serving_capability}
    modelRef: ${model_ref}
    runtimeProfile: ${runtime_profile}

  resources:
    # Sized for a fixture replayer, not for a model. No weights are loaded.
    cpu: "${cpu}"
    memory: "${memory}"
    accelerator:
      type: ${accelerator_type}
      count: ${accelerator_count}

  scaling:
    minimumReplicas: ${minimum_replicas}
    maximumReplicas: ${maximum_replicas}

  integrations:
    telemetry:
      capabilityRef: platform-telemetry
      required: true

  security:
    # A mock never holds real data and never requires real credentials. There is
    # no field in this contract a secret value could be written into, and a
    # mock-llm workload that declared a secret reference would be refused by the
    # `mock-secret-ref-declared` rule.
    dataClassification: ${data_classification}
    secretRefs: []

  attribution:
    tenant: ${tenant}
    costCenter: ${cost_center}

  evidence:
    runbookRef: docs/serving/mock-and-real-boundary.md
    # proofRefs is deliberately absent. Under the mock-llm profile the schema caps
    # it at zero entries, so this workload cannot cite runtime proof at all.

  mockLlm:
    ciOnly: true
    determinism: fixed-fixture
    fixtureRef: contracts/workload/fixtures/mock-llm-chat-completion.response.json
"""
