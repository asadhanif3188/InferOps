"""Which adapter is live, read from configuration and refused when unstated.

`V1-S1-005-PR1` built the composition point with **no default adapter** and no way
to read one out of configuration, because a mock that could become the live
adapter by omission is what
[the mock and real boundary](../../../docs/serving/mock-and-real-boundary.md)
rule 5 forbids. This module is the configuration reader that change deferred, and
it is written so that the same rule still holds after it exists.

**There is no default and there is no fallback.** ``INFEROPS_SERVING_ADAPTER`` is
required and takes one of two values. Unset is a refusal, empty is a refusal, and
a value outside the pair is a refusal — none of them selects the mock. A `real`
selection whose runtime settings are missing or malformed is a refusal too:
**nothing here ever answers a failed real selection with a mock**, which is the
property :func:`select` exists to make structural rather than remembered. Rule 4
of the boundary is explicit that substituting a mock result for a missing real one
is a defect and not a fallback, and a composition function that quietly degraded
would commit that defect once per deployment rather than once per test.

**The adapter kind is derived from the selection, never configured beside it.**
:class:`~inferops.api.application.ApiConfiguration` takes an ``adapter_kind``
because the serving protocol publishes no method for it, and a second environment
variable carrying that label would be a way to compose a real adapter and label
it ``mock``, or the reverse. So the selection decides both, and the application's
own check — that every result an adapter returns declares the kind the deployment
was composed with — is what catches the remaining case.

**The environment is an argument, not ambient state.** Every function here takes a
mapping. Nothing reads :data:`os.environ`, so a selection made in a test and one
made at startup take the same path, and the one place ambient state legally enters
is a caller that passes ``os.environ`` in deliberately.

**A refusal names the variable and never its value.** An endpoint is exactly where
a credential arrives and an error message is exactly where one gets published, so
the refusals here name the variable and state the constraint — the same division
of labour :mod:`inferops.adapters.llama_cpp.settings` already uses, and the reason
:class:`~inferops.domain.serving.InvalidAdapterConfigError` is what they raise.

**Selecting composes; it performs no I/O.** Neither adapter contacts anything at
construction, the real adapter's transport holds no connection between calls, and
initialization happens on lifespan startup rather than here. So a selection that
succeeds has validated configuration and reached nothing — and a real selection
succeeding is **not** evidence that a runtime exists, which is why the
`real-runtime` lane is where that question is answered.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

from ..adapters import MOCK_ADAPTER_KIND, MockServingAdapter
from ..adapters.llama_cpp import (
    LLAMA_SERVER_ADAPTER_KIND,
    HttpRuntimeTransport,
    LlamaServerAdapter,
    LlamaServerSettings,
    RuntimeTransport,
)
from ..domain.serving import (
    AdapterConfiguration,
    InvalidAdapterConfigError,
    ServingAdapter,
)
from .application import ApiConfiguration, InferOpsApi
from .lifecycle import DEFAULT_DRAIN_TIMEOUT_MS

# -- the variables ----------------------------------------------------------

#: Which adapter this deployment serves. Required, with no default: see the
#: module docstring for why an omission may not select anything.
ENV_ADAPTER = "INFEROPS_SERVING_ADAPTER"

#: The platform model identity this deployment serves. It is the identifier a
#: caller's ``model`` member is checked against, and the one the mock adapter
#: requires to be mock-labelled and the real adapter requires not to be.
ENV_MODEL_IDENTIFIER = "INFEROPS_MODEL_IDENTIFIER"

#: How long one inference request may take. Required: `ADR 0002` decides no
#: deadline, so there is no number this module could supply that would not read
#: back later as a recommendation nobody made.
ENV_REQUEST_TIMEOUT_MS = "INFEROPS_REQUEST_TIMEOUT_MS"

#: The ceiling a request's ``max_tokens`` may not exceed. Optional, and absent
#: means this deployment configures none — which is the accurate default, because
#: the accepted surface records the ceiling as depending on a context length
#: `ADR 0002` left undecided.
ENV_MAX_OUTPUT_TOKENS = "INFEROPS_MAX_OUTPUT_TOKENS"

#: The budget a graceful shutdown gives in-flight work. Optional, defaulting to
#: :data:`~inferops.api.lifecycle.DEFAULT_DRAIN_TIMEOUT_MS`, which is itself a
#: default rather than a decision.
ENV_DRAIN_TIMEOUT_MS = "INFEROPS_DRAIN_TIMEOUT_MS"

#: The value that selects the committed mock adapter.
ADAPTER_MOCK = "mock"

#: The value that selects the adapter for the runtime `ADR 0002` chose.
ADAPTER_REAL = "real"

#: The two values :data:`ENV_ADAPTER` accepts, in the order a refusal names them.
#: Each names an adapter this distribution ships, and :data:`ADAPTER_KIND_FOR`
#: maps it to the kind that adapter's own package declares — so the label a
#: deployment carries comes from the adapter rather than from a second list
#: maintained here, and the agreement suite checks that both entries are members
#: of the domain's closed adapter vocabulary.
ACCEPTED_ADAPTERS: tuple[str, ...] = (ADAPTER_MOCK, ADAPTER_REAL)

#: Every variable this module reads, whichever adapter is selected.
REQUIRED_ENVIRONMENT_VARIABLES: tuple[str, ...] = (
    ENV_ADAPTER,
    ENV_MODEL_IDENTIFIER,
    ENV_REQUEST_TIMEOUT_MS,
)

#: Every variable this module reads that may be absent.
OPTIONAL_ENVIRONMENT_VARIABLES: tuple[str, ...] = (
    ENV_MAX_OUTPUT_TOKENS,
    ENV_DRAIN_TIMEOUT_MS,
)

#: What the adapter kind is for each selection. It is derived rather than
#: configured, and each value is the adapter package's own constant rather than a
#: literal repeated here.
ADAPTER_KIND_FOR: Mapping[str, str] = {
    ADAPTER_MOCK: MOCK_ADAPTER_KIND,
    ADAPTER_REAL: LLAMA_SERVER_ADAPTER_KIND,
}


@dataclass(frozen=True, slots=True)
class Selection:
    """One resolved deployment: an adapter, its configuration, and this API's.

    Attributes:
        adapter: The adapter this deployment serves. Constructed and not
            initialized — initialization is the application's, on lifespan
            startup.
        adapter_configuration: What the adapter is initialized with.
        configuration: What this API needs to know, including the adapter kind
            derived from the selection.
        selected: The value :data:`ENV_ADAPTER` carried, for a caller that wants
            to record which selection a deployment made.
    """

    adapter: ServingAdapter
    adapter_configuration: AdapterConfiguration
    configuration: ApiConfiguration
    selected: str

    @property
    def adapter_kind(self) -> str:
        """The kind this deployment was composed with."""
        return self.configuration.adapter_kind

    @property
    def is_mock(self) -> bool:
        """Whether this deployment serves the mock adapter.

        Named so that a caller producing a record can label it from the selection
        rather than from the directory the record sits in, which is boundary
        rule 1.
        """
        return self.selected == ADAPTER_MOCK


def select(
    environment: Mapping[str, str],
    *,
    transport: RuntimeTransport | None = None,
) -> Selection:
    """Resolve one deployment from configuration, or refuse it.

    Args:
        environment: The variables to read. A mapping rather than the process
            environment, so that this is a function of its argument.
        transport: The transport a real adapter issues its requests over. Given
            rather than built so that a suite can exercise a real selection
            against a controlled transport without opening a socket; ``None``
            builds the standard-library one, which holds no connection until a
            request is made.

    Raises:
        InvalidAdapterConfigError: If the selection is unstated, is outside the
            accepted pair, or if the selected adapter's configuration is missing
            or malformed. **No refusal falls back to another adapter.**
    """
    selected = _required(environment, ENV_ADAPTER)
    if selected not in ACCEPTED_ADAPTERS:
        raise InvalidAdapterConfigError(
            ENV_ADAPTER,
            f"must name one of the adapters this platform serves: "
            f"{', '.join(ACCEPTED_ADAPTERS)}",
        )

    adapter_configuration = AdapterConfiguration(
        model_identifier=_required(environment, ENV_MODEL_IDENTIFIER),
        timeout_ms=_required_int(environment, ENV_REQUEST_TIMEOUT_MS),
        max_tokens=_optional_int(environment, ENV_MAX_OUTPUT_TOKENS),
    )
    # The drain budget is the one value with a default, and "absent" is the only
    # thing that takes it. A supplied value is used whatever it is, so that an
    # operator who typed one is never quietly given a different one — which is
    # why this is an explicit `None` check rather than an `or`, where a supplied
    # `0` would be indistinguishable from an unset variable.
    supplied_drain = _optional_int(environment, ENV_DRAIN_TIMEOUT_MS)
    configuration = ApiConfiguration(
        adapter_kind=ADAPTER_KIND_FOR[selected],
        max_output_tokens=adapter_configuration.max_tokens,
        drain_timeout_ms=(
            DEFAULT_DRAIN_TIMEOUT_MS if supplied_drain is None else supplied_drain
        ),
    )

    adapter: ServingAdapter
    if selected == ADAPTER_MOCK:
        # No settings are read for the mock, and none is offered. Failure
        # injection and latency are test inputs rather than deployment
        # configuration, and an environment variable that made a deployment
        # produce a canonical error on demand would be one.
        adapter = MockServingAdapter()
    else:
        adapter = LlamaServerAdapter(
            LlamaServerSettings.from_environment(environment),
            transport if transport is not None else HttpRuntimeTransport(),
        )

    return Selection(
        adapter=adapter,
        adapter_configuration=adapter_configuration,
        configuration=configuration,
        selected=selected,
    )


def build(
    environment: Mapping[str, str],
    *,
    transport: RuntimeTransport | None = None,
) -> InferOpsApi:
    """The application one environment describes, composed and not started.

    The adapter is initialized on lifespan startup, so nothing here contacts
    anything. A caller that wants the selection itself — to record which adapter a
    deployment composed — calls :func:`select` and constructs the application from
    what it returns.
    """
    selection = select(environment, transport=transport)
    return InferOpsApi(
        adapter=selection.adapter,
        adapter_configuration=selection.adapter_configuration,
        configuration=selection.configuration,
    )


# -- reading one variable ---------------------------------------------------


def _required(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name, "").strip()
    if not value:
        raise InvalidAdapterConfigError(name, "is required and is not set")
    return value


def _required_int(environment: Mapping[str, str], name: str) -> int:
    return _whole_number(_required(environment, name), name)


def _optional_int(environment: Mapping[str, str], name: str) -> int | None:
    value = environment.get(name, "").strip()
    if not value:
        return None
    return _whole_number(value, name)


def _whole_number(value: str, name: str) -> int:
    """One positive whole number, or a refusal naming the variable.

    Every number this module reads is a duration or a token count, and none of
    them has a meaning at zero or below. They are refused **here**, naming the
    environment variable, rather than left to the value objects downstream: those
    know the constraint and not where the value came from, so the refusal they
    raise names a constructor parameter an operator never typed and carries a
    different exception type from the one this module's callers are told to
    catch.
    """
    try:
        number = int(value)
    except ValueError:
        raise InvalidAdapterConfigError(
            name, "must be a whole number written in decimal"
        ) from None
    if number <= 0:
        raise InvalidAdapterConfigError(name, "must be a positive whole number")
    return number
