"""Platform configuration translated into `llama-server` configuration.

This is the translation the serving-adapter responsibility list names first:
*translate the platform model into runtime configuration*. It runs in two
directions and both matter.

**Downwards**, an :class:`~inferops.domain.serving.AdapterConfiguration` — model
identity, request timeout, an optional generation bound — is joined to the
operator's :class:`~inferops.adapters.llama_cpp.settings.LlamaServerSettings` and
to the pins, producing one value that carries everything a caller needs and
nothing a caller may invent.

**Upwards**, a `WorkloadContract` that names this runtime is checked against the
pins before anything acts on it. A document that names a different image digest,
a different model revision, or a different weight file is refused rather than
served, because a workload that says one thing while the platform serves another
is the failure mode that makes a pinned artifact worthless. `ADR 0002` records
that the runtime publishes from a branch tip with no versioned tag scheme, which
is precisely the situation in which "the digest in the document" and "the digest
that is running" drift apart quietly.

Every refusal is an
:class:`~inferops.domain.serving.InvalidAdapterConfigError` carrying the field
path the contract publishes for the field, the constraint that was not met, and
the request identifiers the caller supplied. **No refusal repeats a value read
from the document**, which is the same rule the workload validator holds itself
to and the reason a digest mismatch names the field rather than printing both
digests.

Two spellings of a field name appear across this package, and the split is not an
oversight. **A field name in an error is the name its owner publishes**, not the
name this module would prefer: a workload document is named in the contract's
camelCase (``spec.synchronousLlm.modelArtifact.file``), a platform configuration
in the domain's own attribute names (``model_identifier``, ``max_tokens``), and a
runtime setting in the camelCase
:mod:`~inferops.adapters.llama_cpp.settings` publishes (``modelPath``). A reader
given a field name can then look it up where it is defined.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from ...domain.context import NO_REQUEST_CONTEXT, RequestContext
from ...domain.serving import AdapterConfiguration, InvalidAdapterConfigError
from ...domain.workload import Profile, ServingCapability, WorkloadContract
from .pins import PINNED_MODEL, PINNED_RUNTIME, ModelPin, RuntimePin
from .settings import MOCK_IDENTITY_PREFIX, LlamaServerSettings

#: The `llama-server` flags this adapter generates. Written down as constants so
#: that a reader comparing them against the trial manifest is comparing strings
#: rather than reading two spellings of the same intent.
ARGUMENT_MODEL = "--model"
ARGUMENT_ALIAS = "--alias"
ARGUMENT_CONTEXT_SIZE = "--ctx-size"
ARGUMENT_THREADS = "--threads"
ARGUMENT_METRICS = "--metrics"


@dataclass(frozen=True, slots=True)
class LlamaServerConfiguration:
    """One resolved configuration: platform, runtime, and pins in one value.

    Construct it through :func:`translate`. Constructing it directly skips the
    checks, and the checks are the point.
    """

    adapter: AdapterConfiguration
    settings: LlamaServerSettings
    runtime: RuntimePin = field(default=PINNED_RUNTIME)
    model: ModelPin = field(default=PINNED_MODEL)

    @property
    def platform_model_identifier(self) -> str:
        """The identity the platform configured, and the one metadata reports."""
        return self.adapter.model_identifier

    @property
    def runtime_model_alias(self) -> str:
        """The identity the runtime was started with, and the one it echoes."""
        return self.settings.model_alias

    def model_serving_arguments(self) -> tuple[str, ...]:
        """The `llama-server` arguments this configuration determines.

        The bind address and port are **not** generated. Where the runtime
        listens is a property of the deployment that runs it — a container port,
        a Service, and a probe configuration — and generating one here from the
        endpoint this platform dials would be deriving a server's binding from a
        client's address. They agree in the trial manifest by construction and
        they do not have to in general.

        Sampling parameters are absent for the reason `ADR 0002` gives: the
        sampling defaults remain undecided, and a default emitted here would be
        read back later as a recommendation nobody made.
        """
        arguments = [
            ARGUMENT_MODEL,
            self.settings.model_path,
            ARGUMENT_ALIAS,
            self.settings.model_alias,
            ARGUMENT_CONTEXT_SIZE,
            str(self.settings.context_size),
            ARGUMENT_THREADS,
            str(self.settings.threads),
        ]
        if self.settings.metrics_enabled:
            arguments.append(ARGUMENT_METRICS)
        return tuple(arguments)


def translate(
    adapter_configuration: AdapterConfiguration,
    settings: LlamaServerSettings,
    *,
    context: RequestContext = NO_REQUEST_CONTEXT,
    runtime: RuntimePin = PINNED_RUNTIME,
    model: ModelPin = PINNED_MODEL,
) -> LlamaServerConfiguration:
    """Join platform configuration to runtime settings, or refuse the pair.

    Raises:
        InvalidAdapterConfigError: If the platform identity is mock-labelled, if
            the configured generation bound exceeds the context the runtime was
            given, or if the weight file the settings name is not the pinned one.
    """
    if adapter_configuration.model_identifier.lower().startswith(MOCK_IDENTITY_PREFIX):
        raise InvalidAdapterConfigError(
            "model_identifier",
            "a real serving adapter refuses a mock-labelled model identity, "
            f"which starts with '{MOCK_IDENTITY_PREFIX}'",
            context=context,
        )
    if (
        adapter_configuration.max_tokens is not None
        and adapter_configuration.max_tokens > settings.context_size
    ):
        raise InvalidAdapterConfigError(
            "max_tokens",
            "must not exceed the context length the runtime was started with",
            context=context,
        )
    if settings.model_file != model.file:
        raise InvalidAdapterConfigError(
            "modelPath",
            "must name the weight file pinned by the accepted runtime and model "
            "decision",
            context=context,
        )
    return LlamaServerConfiguration(
        adapter=adapter_configuration,
        settings=settings,
        runtime=runtime,
        model=model,
    )


def verify_workload(
    contract: WorkloadContract,
    *,
    context: RequestContext = NO_REQUEST_CONTEXT,
    runtime: RuntimePin = PINNED_RUNTIME,
    model: ModelPin = PINNED_MODEL,
) -> None:
    """Check that a workload document names the runtime and model this serves.

    The document has already been parsed and validated by the platform before it
    reaches here; what this adds is the one question only the adapter can answer,
    which is whether the pinned artifacts the document names are the pinned
    artifacts this adapter is configured for.

    Raises:
        InvalidAdapterConfigError: On the first disagreement, naming the field
            path the contract publishes and never the value found there.
    """
    if contract.spec.profile is not Profile.SYNCHRONOUS_LLM:
        raise InvalidAdapterConfigError(
            "spec.profile",
            "must be 'synchronous-llm' for a workload served by a real runtime",
            context=context,
        )
    if contract.spec.model.serving_capability is not ServingCapability.NATIVE:
        raise InvalidAdapterConfigError(
            "spec.model.servingCapability",
            f"must be '{ServingCapability.NATIVE.value}' for this runtime",
            context=context,
        )
    profile = contract.spec.synchronous_llm
    if profile is None:
        raise InvalidAdapterConfigError(
            "spec.synchronousLlm",
            "must be present for a workload served by a real runtime",
            context=context,
        )
    if str(profile.runtime.image_reference) != runtime.reference:
        raise InvalidAdapterConfigError(
            "spec.synchronousLlm.runtime.imageReference",
            "must be the runtime image digest the accepted decision pins",
            context=context,
        )
    artifact = profile.model_artifact
    for value, expected, path in (
        (
            str(artifact.repository),
            model.repository,
            "spec.synchronousLlm.modelArtifact.repository",
        ),
        (
            str(artifact.revision),
            model.revision,
            "spec.synchronousLlm.modelArtifact.revision",
        ),
        (str(artifact.file), model.file, "spec.synchronousLlm.modelArtifact.file"),
        (
            str(artifact.sha256),
            model.sha256,
            "spec.synchronousLlm.modelArtifact.sha256",
        ),
    ):
        if value != expected:
            raise InvalidAdapterConfigError(
                path,
                "must be the model artifact the accepted decision pins",
                context=context,
            )
    if artifact.size_bytes != model.size_bytes:
        raise InvalidAdapterConfigError(
            "spec.synchronousLlm.modelArtifact.sizeBytes",
            "must be the model artifact size the accepted decision pins",
            context=context,
        )
