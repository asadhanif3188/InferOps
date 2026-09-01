"""Which adapter a deployment serves, read from configuration and never defaulted.

The property this suite exists for is a single sentence:
**no configuration this API accepts can silently produce a mock.**
Boundary rule 5 forbids a mock that could become the live adapter by omission and
rule 4 forbids substituting a mock result for a missing real one, and a
configuration reader is exactly where both get broken quietly. So the tests below
are mostly refusals: an unset selection, an empty one, a misspelled one, and —
the case that matters most — a `real` selection whose runtime settings are absent
or malformed, which must refuse rather than fall back.

Nothing here opens a socket. A real selection composes the real adapter over a
transport this suite supplies, which is what makes a selection testable without a
runtime; **a real selection succeeding is not evidence that a runtime exists**,
and the `real-runtime` lane is where that question is answered.

The evidence class is `mock` for everything below, including the rows that
compose the real adapter: what they establish is the shape of the composition and
nothing about the thing on the other end of it.
"""

from __future__ import annotations

import json

import pytest

from inferops.adapters import MockServingAdapter
from inferops.adapters.llama_cpp import (
    ENV_CONTEXT_SIZE,
    ENV_ENDPOINT,
    ENV_METRICS_ENABLED,
    ENV_MODEL_ALIAS,
    ENV_MODEL_PATH,
    ENV_STARTUP_BUDGET_MS,
    ENV_THREADS,
    PINNED_MODEL_FILE,
    LlamaServerAdapter,
    RuntimeResponse,
)
from inferops.api import (
    ACCEPTED_ADAPTERS,
    ADAPTER_MOCK,
    ADAPTER_REAL,
    DEFAULT_DRAIN_TIMEOUT_MS,
    ENV_ADAPTER,
    ENV_DRAIN_TIMEOUT_MS,
    ENV_MAX_OUTPUT_TOKENS,
    ENV_MODEL_IDENTIFIER,
    ENV_REQUEST_TIMEOUT_MS,
    InferOpsApi,
    Selection,
    build,
    select,
)
from inferops.api.surface import CHAT_COMPLETIONS_PATH, EXTENSION_MEMBER
from inferops.domain.serving import ACCEPTED_ADAPTER_KINDS, InvalidAdapterConfigError
from tests.support import asgi_client

pytestmark = pytest.mark.mockintegration

#: The model identity a real deployment names. Not mock-labelled, because the
#: real adapter refuses one that is — which is the mirror of the mock adapter
#: refusing a real identity.
REAL_MODEL = "qwen3-1-7b-instruct"

#: A value that must never appear in a refusal. It stands in for the things these
#: variables genuinely carry: an endpoint, a mounted path, an operator's label.
CANARY = "SECRET-VALUE-9f2c"


class SilentTransport:
    """A transport that is never called, so a selection can be made with no runtime.

    It exists so that composing a real adapter in this lane cannot reach a
    network even by accident: every method raises. A selection performs no I/O,
    so a passing test here is one where nothing below was ever called.
    """

    async def get(self, url: str, *, timeout_s: float) -> RuntimeResponse:
        raise AssertionError("a selection must not contact the runtime")

    async def post_json(
        self, url: str, payload: object, *, timeout_s: float
    ) -> RuntimeResponse:
        raise AssertionError("a selection must not contact the runtime")

    async def close(self) -> None:
        return None


def mock_environment(**overrides: str) -> dict[str, str]:
    environment = {
        ENV_ADAPTER: ADAPTER_MOCK,
        ENV_MODEL_IDENTIFIER: "mock-fixed-fixture",
        ENV_REQUEST_TIMEOUT_MS: "5000",
    }
    environment.update(overrides)
    return environment


def real_environment(**overrides: str) -> dict[str, str]:
    environment = {
        ENV_ADAPTER: ADAPTER_REAL,
        ENV_MODEL_IDENTIFIER: REAL_MODEL,
        ENV_REQUEST_TIMEOUT_MS: "120000",
        ENV_ENDPOINT: "http://llama-server.inferops.svc:8080",
        ENV_MODEL_PATH: f"/models/{PINNED_MODEL_FILE}",
        ENV_MODEL_ALIAS: REAL_MODEL,
        ENV_CONTEXT_SIZE: "4096",
        ENV_THREADS: "6",
        ENV_STARTUP_BUDGET_MS: "600000",
    }
    environment.update(overrides)
    return environment


def select_real(**overrides: str) -> Selection:
    return select(real_environment(**overrides), transport=SilentTransport())


# --------------------------------------------------------------------------
# There is no default
# --------------------------------------------------------------------------


def test_an_unset_selection_selects_nothing() -> None:
    """The single most important refusal in this module.

    A reader who takes one thing from this suite should take this: omitting the
    variable does not produce a mock, and does not produce anything.
    """
    with pytest.raises(InvalidAdapterConfigError) as raised:
        select({ENV_MODEL_IDENTIFIER: "mock-fixed-fixture"})

    assert raised.value.field == ENV_ADAPTER


@pytest.mark.parametrize("value", ["", "   ", "Mock", "REAL", "mocked", "banana"])
def test_a_selection_outside_the_accepted_pair_is_refused(value: str) -> None:
    """Including the near-misses, which are the ones somebody actually types."""
    with pytest.raises(InvalidAdapterConfigError) as raised:
        select(mock_environment(**{ENV_ADAPTER: value}))

    assert raised.value.field == ENV_ADAPTER


def test_the_accepted_selections_are_the_domains_own_adapter_kinds() -> None:
    """A third kind cannot be introduced here without the domain admitting it."""
    assert set(ACCEPTED_ADAPTERS) == set(ACCEPTED_ADAPTER_KINDS)


# --------------------------------------------------------------------------
# A real selection never becomes a mock
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "missing",
    [
        ENV_ENDPOINT,
        ENV_MODEL_PATH,
        ENV_MODEL_ALIAS,
        ENV_CONTEXT_SIZE,
        ENV_THREADS,
        ENV_STARTUP_BUDGET_MS,
    ],
)
def test_a_real_selection_missing_one_setting_refuses_rather_than_falls_back(
    missing: str,
) -> None:
    """Rule 4: substituting a mock for a missing real one is a defect, not a fallback."""
    environment = real_environment()
    del environment[missing]

    with pytest.raises(InvalidAdapterConfigError) as raised:
        select(environment, transport=SilentTransport())

    assert raised.value.field == missing


def test_a_real_selection_with_a_malformed_endpoint_refuses() -> None:
    with pytest.raises(InvalidAdapterConfigError):
        select_real(**{ENV_ENDPOINT: "not-a-url"})


def test_a_real_selection_with_a_mock_labelled_identity_refuses() -> None:
    """The safeguard that makes a transcript's provider label mean something.

    The real adapter refuses a mock-labelled identity at initialization; the
    settings refuse a mock-labelled alias at construction, which is here.
    """
    with pytest.raises(InvalidAdapterConfigError) as raised:
        select_real(**{ENV_MODEL_ALIAS: "mock-fixed-fixture"})

    assert raised.value.field == "modelAlias"


def test_no_refusal_repeats_the_value_it_refused() -> None:
    """An endpoint is exactly where a credential arrives, and an error message is
    exactly where one gets published."""
    with pytest.raises(InvalidAdapterConfigError) as raised:
        select_real(**{ENV_CONTEXT_SIZE: CANARY})

    assert CANARY not in str(raised.value)
    assert raised.value.field == ENV_CONTEXT_SIZE


# --------------------------------------------------------------------------
# What each selection composes
# --------------------------------------------------------------------------


def test_a_mock_selection_composes_the_committed_mock_and_labels_it_mock() -> None:
    selection = select(mock_environment())

    assert isinstance(selection.adapter, MockServingAdapter)
    assert selection.adapter_kind == "mock"
    assert selection.is_mock is True


def test_a_real_selection_composes_the_real_adapter_and_labels_it_real() -> None:
    selection = select_real()

    assert isinstance(selection.adapter, LlamaServerAdapter)
    assert selection.adapter_kind == "real"
    assert selection.is_mock is False


def test_the_adapter_kind_is_derived_and_is_not_a_variable_of_its_own() -> None:
    """A second variable carrying the label would be a way to compose a real
    adapter and call it a mock, which is the one thing the label exists to stop."""
    environment = real_environment()
    environment["INFEROPS_ADAPTER_KIND"] = "mock"

    assert select(environment, transport=SilentTransport()).adapter_kind == "real"


def test_a_mock_selection_reads_no_runtime_setting() -> None:
    """A mock deployment needs no endpoint, no weights, and no threads."""
    selection = select(
        mock_environment(**{ENV_ENDPOINT: "http://ignored:8080"}),
    )

    assert isinstance(selection.adapter, MockServingAdapter)


def test_failure_injection_is_not_deployment_configuration() -> None:
    """The mock's scenario and latency are test inputs and have no variable.

    A variable that made a deployment produce a canonical error on demand would
    be one, and it would be reachable in whatever environment the deployment ran.
    """
    selection = select(mock_environment(**{"INFEROPS_MOCK_SCENARIO": "rate-limited"}))

    assert isinstance(selection.adapter, MockServingAdapter)
    assert selection.adapter.settings.scenario == "success"
    assert selection.adapter.settings.latency_ms == 0


# --------------------------------------------------------------------------
# The configuration each selection produces
# --------------------------------------------------------------------------


def test_the_request_timeout_is_required_and_is_carried_to_the_adapter() -> None:
    selection = select(mock_environment(**{ENV_REQUEST_TIMEOUT_MS: "1234"}))

    assert selection.adapter_configuration.timeout_ms == 1234


def test_a_missing_request_timeout_is_refused_rather_than_defaulted() -> None:
    """`ADR 0002` decides no deadline, so this module invents none."""
    environment = mock_environment()
    del environment[ENV_REQUEST_TIMEOUT_MS]

    with pytest.raises(InvalidAdapterConfigError) as raised:
        select(environment)

    assert raised.value.field == ENV_REQUEST_TIMEOUT_MS


def test_an_absent_generation_ceiling_is_none_rather_than_a_number() -> None:
    """No operator limit means the adapter uses the runtime's configured default."""
    selection = select(mock_environment())

    assert selection.adapter_configuration.max_tokens is None


def test_the_generation_ceiling_is_passed_to_the_adapter() -> None:
    """The operator setting is deployment-wide, not a caller request control."""
    selection = select(mock_environment(**{ENV_MAX_OUTPUT_TOKENS: "512"}))

    assert selection.adapter_configuration.max_tokens == 512


def test_an_absent_drain_budget_takes_the_published_default() -> None:
    selection = select(mock_environment())

    assert selection.configuration.drain_timeout_ms == DEFAULT_DRAIN_TIMEOUT_MS


def test_a_configured_drain_budget_is_used() -> None:
    selection = select(mock_environment(**{ENV_DRAIN_TIMEOUT_MS: "2500"}))

    assert selection.configuration.drain_timeout_ms == 2500


#: Every numeric variable this module reads. Each is a duration or a token count,
#: so none of them has a meaning at zero or below.
NUMERIC_VARIABLES = [
    ENV_REQUEST_TIMEOUT_MS,
    ENV_MAX_OUTPUT_TOKENS,
    ENV_DRAIN_TIMEOUT_MS,
]


@pytest.mark.parametrize("variable", NUMERIC_VARIABLES)
def test_a_number_that_is_not_one_is_refused(variable: str) -> None:
    with pytest.raises(InvalidAdapterConfigError) as raised:
        select(mock_environment(**{variable: "12ms"}))

    assert raised.value.field == variable


@pytest.mark.parametrize("variable", NUMERIC_VARIABLES)
@pytest.mark.parametrize("value", ["0", "-1", "-9000"])
def test_a_number_at_or_below_zero_is_refused_and_names_the_variable(
    variable: str, value: str
) -> None:
    """A supplied value is never quietly replaced by a different one.

    ``0`` is the case worth writing down: an optional variable read with an
    ``or`` would treat a supplied zero as an unset variable and hand back the
    default, so an operator who typed a number would get one they did not. And
    the refusal has to come from **this** module, naming the environment variable
    an operator actually set — a value object downstream knows the constraint and
    not where the value came from, so its refusal names a constructor parameter
    nobody typed.
    """
    with pytest.raises(InvalidAdapterConfigError) as raised:
        select(mock_environment(**{variable: value}))

    assert raised.value.field == variable
    assert value not in str(raised.value)


def test_a_supplied_drain_budget_is_never_replaced_by_the_default() -> None:
    """The specific coercion the test above exists to prevent, stated directly."""
    with pytest.raises(InvalidAdapterConfigError):
        select(mock_environment(**{ENV_DRAIN_TIMEOUT_MS: "0"}))


def test_the_optional_runtime_metrics_flag_is_still_optional() -> None:
    """The one runtime setting with a default, and it stays where it was."""
    selection = select_real(**{ENV_METRICS_ENABLED: "false"})

    assert isinstance(selection.adapter, LlamaServerAdapter)
    assert selection.adapter.settings.metrics_enabled is False


# --------------------------------------------------------------------------
# Building the application
# --------------------------------------------------------------------------


def test_building_an_application_performs_no_input_or_output() -> None:
    """A real application composed over a transport that refuses to be called.

    Initialization is the application's, on lifespan startup. If anything here
    contacted the runtime, the transport would fail the test rather than the
    network.
    """
    api = build(real_environment(), transport=SilentTransport())

    assert isinstance(api, InferOpsApi)


async def test_an_application_built_from_configuration_answers_end_to_end() -> None:
    """The composition path a deployment would take, driven to a completion.

    This is the one row here that goes past construction, and it goes only as far
    as the mock: a real selection cannot be started without a runtime, which is
    the point of the lane that owns it.
    """
    api = build(mock_environment())
    await api.startup()

    response = await asgi_client.request(
        api,
        "POST",
        CHAT_COMPLETIONS_PATH,
        body=json.dumps(
            {
                "model": "mock-fixed-fixture",
                "messages": [{"role": "user", "content": "hello"}],
            }
        ).encode("utf-8"),
    )

    assert response.status == 200
    assert response.json()[EXTENSION_MEMBER]["adapterKind"] == "mock"
