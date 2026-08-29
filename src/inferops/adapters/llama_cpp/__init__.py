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

**The adapter is here now, and it generates text or it fails.** The first half of
this story shipped no :class:`~inferops.domain.serving.ServingAdapter` on the
ground that a class whose ``infer`` could not generate anything would be exactly
the "silently fall back" failure the project's own boundary rule forbids. The
second half adds the transport seam, the inference client, the bounded deadlines,
and the mapping from a runtime failure to a canonical error, and
:class:`~inferops.adapters.llama_cpp.adapter.LlamaServerAdapter` composes the
modules below into the protocol implementation.

**That the adapter exists is not a claim that anything ran.** The default lane
exercises it against a controlled transport, which establishes the shape of the
call and nothing about the thing on the other end of it. A real-runtime record is
produced by the `real-runtime` lane, which is manual and authorization-gated, and
that record — not this package — is what may support a serving claim.

This package's name is also the import name of the third-party
``llama-cpp-python`` distribution. Nothing collides today — every reference here
is a relative import, and the dependency rule forbids acquiring that package at
all — but an absolute ``import llama_cpp`` written inside this distribution would
resolve here rather than there, which is worth knowing before writing one.

**Every pin, capability, and status mapping is copied** from an accepted decision
or from the Sprint 0 feasibility record, and its evidence class is that of the
record it came from — never this package's. Nothing here loads a model or reads a
file, and exactly one module opens a socket:
:mod:`~inferops.adapters.llama_cpp.http_transport`, which is the concrete side of
a seam the adapter is given rather than builds.

Nine modules, one job each:

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
- :mod:`~inferops.adapters.llama_cpp.transport` — the seam a request crosses,
  as a protocol and three failure kinds that carry no text from the far side.
- :mod:`~inferops.adapters.llama_cpp.http_transport` — that seam implemented with
  the standard library's own HTTP, because the dependency rule leaves no other.
- :mod:`~inferops.adapters.llama_cpp.inference` — the request sent, the response
  read, and the accepted mapping from a condition to a canonical code.
- :mod:`~inferops.adapters.llama_cpp.adapter` — the protocol implementation that
  composes all of the above.
"""

from __future__ import annotations

from .adapter import (
    COMPLETION_ALIAS_DISAGREEMENT,
    NOT_INITIALIZED_MESSAGE,
    SHUT_DOWN_MESSAGE,
    LlamaServerAdapter,
)
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
from .http_transport import (
    BASE_HEADERS,
    JSON_MEDIA_TYPE,
    MAX_RESPONSE_BYTES,
    HttpRuntimeTransport,
)
from .inference import (
    ENABLE_THINKING_KEY,
    ENABLE_THINKING_VALUE,
    ERROR_CODE_BY_CONDITION,
    ERROR_CONDITIONS,
    ROLE_USER,
    SURFACE_DATA_REF,
    SURFACE_DECISION_REF,
    UNREADABLE_RESPONSE_MESSAGE,
    ErrorCondition,
    NormalizedCompletion,
    build_request,
    error_for_status,
    error_for_transport_failure,
    is_success,
    normalize_response,
    request_deadline_error,
    unreachable_error,
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
    CHAT_COMPLETIONS_PATH,
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
from .transport import (
    RuntimeResponse,
    RuntimeTransport,
    TransportError,
    TransportProtocolError,
    TransportTimeout,
    TransportUnreachable,
)

__all__ = [
    "ACCEPTED_ENDPOINT_SCHEMES",
    "ACCEPTED_RUNTIME_PATHS",
    "ALIAS_DISAGREEMENT",
    "BASE_HEADERS",
    "CAPABILITY_DETERMINISTIC_FIXTURE_REPLAY",
    "CAPABILITY_REAL_MODEL_INFERENCE",
    "CAPABILITY_STREAMING",
    "CAPABILITY_TOKEN_COUNTING",
    "CHAT_COMPLETIONS_PATH",
    "COMPATIBILITY_MATRIX_REF",
    "COMPLETION_ALIAS_DISAGREEMENT",
    "ENABLE_THINKING_KEY",
    "ENABLE_THINKING_VALUE",
    "ENV_CONTEXT_SIZE",
    "ENV_ENDPOINT",
    "ENV_METRICS_ENABLED",
    "ENV_MODEL_ALIAS",
    "ENV_MODEL_PATH",
    "ENV_STARTUP_BUDGET_MS",
    "ENV_THREADS",
    "ERROR_CODE_BY_CONDITION",
    "ERROR_CONDITIONS",
    "HEALTH_LOADING_STATUS",
    "HEALTH_PATH",
    "HEALTH_READY_STATUS",
    "JSON_MEDIA_TYPE",
    "LLAMA_SERVER_ADAPTER_KIND",
    "LLAMA_SERVER_CAPABILITIES",
    "LLAMA_SERVER_CAPABILITY_BASES",
    "LLAMA_SERVER_RUNTIME_ID",
    "LLAMA_SERVER_RUNTIME_NAME",
    "LLAMA_SERVER_SERVING_CAPABILITY",
    "MAX_RESPONSE_BYTES",
    "METRICS_PATH",
    "MODELS_PATH",
    "MODEL_FILE_DISAGREEMENT",
    "NOT_INITIALIZED_MESSAGE",
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
    "ROLE_USER",
    "RUNTIME_DECISION_REF",
    "RUNTIME_FEASIBILITY_REF",
    "SHUT_DOWN_MESSAGE",
    "SURFACE_DATA_REF",
    "SURFACE_DECISION_REF",
    "UNREADABLE_RESPONSE_MESSAGE",
    "CapabilityBasis",
    "ErrorCondition",
    "HttpRuntimeTransport",
    "LlamaServerAdapter",
    "LlamaServerConfiguration",
    "LlamaServerSettings",
    "ModelPin",
    "NormalizedCompletion",
    "ObservedRuntimeIdentity",
    "ReadinessState",
    "ReadinessTracker",
    "RuntimePin",
    "RuntimeResponse",
    "RuntimeTransport",
    "TransportError",
    "TransportProtocolError",
    "TransportTimeout",
    "TransportUnreachable",
    "annotations",
    "build_request",
    "describe_model",
    "describe_runtime",
    "error_for_status",
    "error_for_transport_failure",
    "identity_disagreements",
    "is_ready",
    "is_success",
    "map_health_status",
    "normalize_response",
    "observe",
    "parse_models_payload",
    "parse_props_payload",
    "readiness_error",
    "request_deadline_error",
    "translate",
    "unreachable_error",
    "verify_workload",
]
