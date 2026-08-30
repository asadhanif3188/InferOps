"""The contract a generated `synchronous-llm` workload declares.

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
# A synchronous-llm workload, bound to the runtime image digest and the model
# revision ADR 0002 selected. Those are the only runtime and model this project
# has executed against, so the template supplies them; a pair that is absent from
# contracts/workload/compatibility/runtime-model-compatibility.v1alpha1.json is
# unsupported until it is added there with evidence.
#
# This document declares a workload. It does not deploy one: no controller,
# chart, or reconciler in this repository acts on it.
#
# Generated from the InferOps workload template. Edit it as you would any other
# committed document; nothing regenerates it.
apiVersion: inferops.io/v1alpha1
kind: WorkloadContract

metadata:
  name: ${name}
  version: ${version}
  owner: ${owner}
  description: ${description_yaml}

spec:
  profile: synchronous-llm
  environment: ${environment}

  model:
    servingCapability: ${serving_capability}
    modelRef: ${model_ref}
    runtimeProfile: ${runtime_profile}

  resources:
    # There is no default. What is written here is what this workload asks the
    # scheduler for, not what any host was measured to deliver.
    cpu: "${cpu}"
    memory: "${memory}"
    accelerator:
      type: ${accelerator_type}
      count: ${accelerator_count}

  scaling:
    minimumReplicas: ${minimum_replicas}
    maximumReplicas: ${maximum_replicas}

  integrations:
    # Telemetry is not optional: a workload the platform cannot observe cannot be
    # operated. No model-access or evaluation capability exists in V1, so neither
    # is declared here.
    telemetry:
      capabilityRef: platform-telemetry
      required: true

  security:
    dataClassification: ${data_classification}
    # References to secrets, never secret values. Every member object is closed,
    # so there is no field a value could be written into. Add an entry as
    # {name, provider, reference, owner, rotation}; the shape example is
    # contracts/workload/examples/valid/synchronous-llm-secret-refs.yaml.
    secretRefs: []

  attribution:
    tenant: ${tenant}
    costCenter: ${cost_center}

  evidence:
    runbookRef: docs/serving/feasibility-workflow.md
    # proofRefs is deliberately absent. This workload has executed nothing and so
    # has no record to cite. Add one when it has produced its own; citing another
    # workload's feasibility record here would claim its result for this workload.

  synchronousLlm:
    runtime:
      imageReference: ${runtime_image_reference}
    modelArtifact:
      repository: ${model_repository}
      revision: ${model_revision}
      file: ${model_file}
      sizeBytes: ${model_size_bytes}
      sha256: ${model_sha256}
"""
