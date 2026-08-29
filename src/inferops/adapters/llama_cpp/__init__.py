"""Configuration, capability, metadata, and readiness for the selected runtime.

`ADR 0002` selected llama.cpp `llama-server` and a pinned `Qwen3-1.7B` GGUF
artifact, and proved the pair in a cluster. This package is the platform's side
of that decision: everything InferOps needs in order to *configure and inspect*
that runtime, with the runtime's own vocabulary confined to these modules.

**Isolation is the whole design.** A context length, a thread count, a base URL,
a health status code, and a ``/props`` member are `llama.cpp` concepts. None of
them appears in the platform domain, in the workload contract, or in any value
object the serving interface publishes, and
``tests/architecture/test_domain_dependency_boundary.py`` holds every module here
to the same rule the domain obeys: standard library and this distribution only,
no serving-runtime SDK, no HTTP framework, and no file read at import.

**There is no adapter here yet, and that is deliberate.** This package
implements the configuration and inspection half of the story it belongs to. The
:class:`~inferops.domain.serving.ServingAdapter` implementation — the inference
client, the mapping from a runtime failure to a canonical error, the timeout, and
the executed record of one real generated response — is the second half, and
publishing a class that satisfied the protocol's shape while its ``infer`` could
not generate anything would be exactly the "silently fall back" failure the
project's own boundary rule forbids. What exists here is composed by that adapter
when it arrives.

This package's name is also the import name of the third-party
``llama-cpp-python`` distribution. Nothing collides today — every reference here
is a relative import, and the dependency rule forbids acquiring that package at
all — but an absolute ``import llama_cpp`` written inside this distribution would
resolve here rather than there, which is worth knowing before writing one.

**Nothing here has executed anything.** Every pin, capability, and status mapping
is copied from an accepted decision or from the Sprint 0 feasibility record, and
its evidence class is that of the record it came from — never this package's.
This package loads no model, opens no socket, and reads no file.

Six modules, one job each:

- :mod:`~inferops.adapters.llama_cpp.pins` — the runtime image digest, the model
  revision, file, size, and hash, and the records they were copied from.
- :mod:`~inferops.adapters.llama_cpp.settings` — the operator-supplied runtime
  settings, their environment variables, and the validation that refuses a
  credential-bearing endpoint or an invented default.
- :mod:`~inferops.adapters.llama_cpp.configuration` — platform configuration
  translated into runtime configuration, and a workload document checked against
  the pins.
- :mod:`~inferops.adapters.llama_cpp.readiness` — the health-status mapping, and
  a readiness that is false until an observation makes it true.
- :mod:`~inferops.adapters.llama_cpp.metadata` — what the runtime says about
  itself, read narrowly and never promoted into a pin.
- :mod:`~inferops.adapters.llama_cpp.capabilities` — what the runtime supports,
  declared with the basis for each entry.
"""

from __future__ import annotations

from .capabilities import (
    CAPABILITY_DETERMINISTIC_FIXTURE_REPLAY,
    CAPABILITY_REAL_MODEL_INFERENCE,
    CAPABILITY_STREAMING,
    CAPABILITY_TOKEN_COUNTING,
    LLAMA_SERVER_CAPABILITIES,
    LLAMA_SERVER_CAPABILITY_BASES,
    CapabilityBasis,
)
from .configuration import (
    LlamaServerConfiguration,
    translate,
    verify_workload,
)
from .metadata import (
    ALIAS_DISAGREEMENT,
    MODEL_FILE_DISAGREEMENT,
    ObservedRuntimeIdentity,
    describe_model,
    describe_runtime,
    identity_disagreements,
    observe,
    parse_models_payload,
    parse_props_payload,
)
from .pins import (
    COMPATIBILITY_MATRIX_REF,
    LLAMA_SERVER_ADAPTER_KIND,
    LLAMA_SERVER_RUNTIME_ID,
    LLAMA_SERVER_RUNTIME_NAME,
    LLAMA_SERVER_SERVING_CAPABILITY,
    OBSERVED_BUILD_INFO,
    PINNED_ARTIFACT_FORMAT,
    PINNED_IMAGE_DIGEST,
    PINNED_IMAGE_REFERENCE,
    PINNED_IMAGE_REPOSITORY,
    PINNED_MODEL,
    PINNED_MODEL_FILE,
    PINNED_MODEL_REPOSITORY,
    PINNED_MODEL_REVISION,
    PINNED_MODEL_SHA256,
    PINNED_MODEL_SIZE_BYTES,
    PINNED_RUNTIME,
    RUNTIME_DECISION_REF,
    RUNTIME_FEASIBILITY_REF,
    ModelPin,
    RuntimePin,
)
from .readiness import (
    HEALTH_LOADING_STATUS,
    HEALTH_READY_STATUS,
    NOT_READY_MESSAGES,
    ReadinessState,
    ReadinessTracker,
    is_ready,
    map_health_status,
    readiness_error,
)
from .settings import (
    ACCEPTED_ENDPOINT_SCHEMES,
    ACCEPTED_RUNTIME_PATHS,
    ENV_CONTEXT_SIZE,
    ENV_ENDPOINT,
    ENV_METRICS_ENABLED,
    ENV_MODEL_ALIAS,
    ENV_MODEL_PATH,
    ENV_STARTUP_BUDGET_MS,
    ENV_THREADS,
    HEALTH_PATH,
    METRICS_PATH,
    MODELS_PATH,
    OPTIONAL_ENVIRONMENT_VARIABLES,
    PROPS_PATH,
    REQUIRED_ENVIRONMENT_VARIABLES,
    LlamaServerSettings,
)

__all__ = [
    "ACCEPTED_ENDPOINT_SCHEMES",
    "ACCEPTED_RUNTIME_PATHS",
    "ALIAS_DISAGREEMENT",
    "CAPABILITY_DETERMINISTIC_FIXTURE_REPLAY",
    "CAPABILITY_REAL_MODEL_INFERENCE",
    "CAPABILITY_STREAMING",
    "CAPABILITY_TOKEN_COUNTING",
    "COMPATIBILITY_MATRIX_REF",
    "ENV_CONTEXT_SIZE",
    "ENV_ENDPOINT",
    "ENV_METRICS_ENABLED",
    "ENV_MODEL_ALIAS",
    "ENV_MODEL_PATH",
    "ENV_STARTUP_BUDGET_MS",
    "ENV_THREADS",
    "HEALTH_LOADING_STATUS",
    "HEALTH_PATH",
    "HEALTH_READY_STATUS",
    "LLAMA_SERVER_ADAPTER_KIND",
    "LLAMA_SERVER_CAPABILITIES",
    "LLAMA_SERVER_CAPABILITY_BASES",
    "LLAMA_SERVER_RUNTIME_ID",
    "LLAMA_SERVER_RUNTIME_NAME",
    "LLAMA_SERVER_SERVING_CAPABILITY",
    "METRICS_PATH",
    "MODELS_PATH",
    "MODEL_FILE_DISAGREEMENT",
    "NOT_READY_MESSAGES",
    "OBSERVED_BUILD_INFO",
    "OPTIONAL_ENVIRONMENT_VARIABLES",
    "PINNED_ARTIFACT_FORMAT",
    "PINNED_IMAGE_DIGEST",
    "PINNED_IMAGE_REFERENCE",
    "PINNED_IMAGE_REPOSITORY",
    "PINNED_MODEL",
    "PINNED_MODEL_FILE",
    "PINNED_MODEL_REPOSITORY",
    "PINNED_MODEL_REVISION",
    "PINNED_MODEL_SHA256",
    "PINNED_MODEL_SIZE_BYTES",
    "PINNED_RUNTIME",
    "PROPS_PATH",
    "REQUIRED_ENVIRONMENT_VARIABLES",
    "RUNTIME_DECISION_REF",
    "RUNTIME_FEASIBILITY_REF",
    "CapabilityBasis",
    "LlamaServerConfiguration",
    "LlamaServerSettings",
    "ModelPin",
    "ObservedRuntimeIdentity",
    "ReadinessState",
    "ReadinessTracker",
    "RuntimePin",
    "describe_model",
    "describe_runtime",
    "identity_disagreements",
    "is_ready",
    "map_health_status",
    "observe",
    "parse_models_payload",
    "parse_props_payload",
    "readiness_error",
    "translate",
    "verify_workload",
]
