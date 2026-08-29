"""Runtime settings: what they refuse, and what they refuse to invent.

Two groups of obligation.

**Refusal.** An endpoint is where a credential arrives, a weight path is where a
traversal arrives, and a mock-labelled alias is where a real transcript stops
being real. Each is refused at construction rather than at first use, so that a
wrong setting is a startup failure with a field name rather than a runtime
failure inside a caller's request.

**Absence of invention.** `ADR 0002` records the context length, the KV budget,
the concurrency limit, and the sampling defaults as undecided. A default here
would become a project recommendation the moment somebody read it back out, so
there is none, and this suite is where "there is none" is enforced rather than
promised.

Every check reads objects from this distribution. No network, no cluster, no
model, no credential, no clock, no randomness, and no environment variable of the
running process is read: the environment is passed in as a mapping.
"""

from __future__ import annotations

import pytest

from inferops.adapters.llama_cpp import (
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
    PINNED_MODEL_FILE,
    PROPS_PATH,
    REQUIRED_ENVIRONMENT_VARIABLES,
    LlamaServerSettings,
)
from inferops.domain.serving import InvalidAdapterConfigError

pytestmark = pytest.mark.adapter

#: A complete, valid environment. Every test that needs an invalid one starts
#: from this and breaks exactly one entry, so a failure names one cause.
VALID_ENVIRONMENT = {
    ENV_ENDPOINT: "http://llama-server.inferops-serving.svc.cluster.local:80",
    ENV_MODEL_PATH: f"/models/{PINNED_MODEL_FILE}",
    ENV_MODEL_ALIAS: "qwen3-1.7b-q8_0",
    ENV_CONTEXT_SIZE: "4096",
    ENV_THREADS: "6",
    ENV_STARTUP_BUDGET_MS: "300000",
}


def settings(**overrides: object) -> LlamaServerSettings:
    """Valid settings, with named fields replaced."""
    values: dict[str, object] = {
        "endpoint": "http://llama-server.inferops-serving.svc.cluster.local:80",
        "model_path": f"/models/{PINNED_MODEL_FILE}",
        "model_alias": "qwen3-1.7b-q8_0",
        "context_size": 4096,
        "threads": 6,
        "startup_budget_ms": 300000,
    }
    values.update(overrides)
    return LlamaServerSettings(**values)  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# The endpoint
# --------------------------------------------------------------------------


def test_a_valid_in_cluster_endpoint_is_accepted() -> None:
    assert settings().endpoint.startswith("http://")


@pytest.mark.parametrize(
    "endpoint",
    [
        "",
        "llama-server:8080",
        "ftp://llama-server:8080",
        "file:///models",
        "http://",
    ],
    ids=["empty", "no-scheme", "wrong-scheme", "file-scheme", "no-host"],
)
def test_an_endpoint_that_is_not_an_absolute_http_url_is_refused(
    endpoint: str,
) -> None:
    with pytest.raises(InvalidAdapterConfigError) as caught:
        settings(endpoint=endpoint)
    assert caught.value.field == "endpoint"


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://operator:0000000000@llama-server:8080",
        "http://operator@llama-server:8080",
    ],
    ids=["user-and-password", "user-only"],
)
def test_an_endpoint_carrying_credentials_is_refused(endpoint: str) -> None:
    """A credential in a URL is a credential in every line that logs the URL."""
    with pytest.raises(InvalidAdapterConfigError) as caught:
        settings(endpoint=endpoint)
    assert caught.value.field == "endpoint"


def test_a_refusal_does_not_repeat_the_value_it_refused() -> None:
    """The message names the field and the constraint, and nothing else.

    This is the rule the domain's own errors hold to, and the endpoint is the
    single most important place to hold to it.
    """
    secret_shaped = "http://admin:ghp_0000000000000000000000000000000000@runtime:8080"
    with pytest.raises(InvalidAdapterConfigError) as caught:
        settings(endpoint=secret_shaped)
    assert "ghp_0000000000000000000000000000000000" not in str(caught.value)
    assert "ghp_0000000000000000000000000000000000" not in str(caught.value.as_dict())


@pytest.mark.parametrize(
    "endpoint",
    [
        "http://llama-server:8080/v1",
        "http://llama-server:8080/?token=abc",
        "http://llama-server:8080/#fragment",
    ],
    ids=["path", "query", "fragment"],
)
def test_an_endpoint_that_is_not_a_bare_base_url_is_refused(endpoint: str) -> None:
    with pytest.raises(InvalidAdapterConfigError) as caught:
        settings(endpoint=endpoint)
    assert caught.value.field == "endpoint"


def test_a_trailing_slash_on_the_endpoint_is_accepted_and_not_doubled() -> None:
    built = settings(endpoint="http://llama-server:8080/").url_for(HEALTH_PATH)
    assert built == "http://llama-server:8080/health"


# --------------------------------------------------------------------------
# Runtime paths
# --------------------------------------------------------------------------


@pytest.mark.parametrize("path", sorted(ACCEPTED_RUNTIME_PATHS))
def test_every_published_runtime_path_builds_a_url(path: str) -> None:
    assert settings().url_for(path).endswith(path)


def test_a_path_this_adapter_does_not_publish_is_refused() -> None:
    """Otherwise this is a URL builder aimed at a host read from the environment."""
    with pytest.raises(InvalidAdapterConfigError) as caught:
        settings().url_for("/v1/chat/completions")
    assert caught.value.field == "path"


def test_the_inference_path_is_not_among_the_published_paths() -> None:
    """The call that generates a completion belongs to the inference client."""
    assert "/v1/chat/completions" not in ACCEPTED_RUNTIME_PATHS
    published = {HEALTH_PATH, PROPS_PATH, MODELS_PATH, METRICS_PATH}
    assert published == ACCEPTED_RUNTIME_PATHS


def test_the_metrics_path_is_refused_when_metrics_are_disabled() -> None:
    """The endpoint exists only when the runtime was started with its flag."""
    with pytest.raises(InvalidAdapterConfigError) as caught:
        settings(metrics_enabled=False).url_for(METRICS_PATH)
    assert caught.value.field == "metricsEnabled"


# --------------------------------------------------------------------------
# The weight path and the alias
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "model_path",
    [
        "models/Qwen3-1.7B-Q8_0.gguf",
        "/models/../etc/Qwen3-1.7B-Q8_0.gguf",
        "/models/Qwen3-1.7B.safetensors",
        "/models/",
    ],
    ids=["relative", "traversal", "wrong-format", "no-file"],
)
def test_a_weight_path_that_is_not_an_absolute_gguf_file_is_refused(
    model_path: str,
) -> None:
    with pytest.raises(InvalidAdapterConfigError) as caught:
        settings(model_path=model_path)
    assert caught.value.field == "modelPath"


def test_the_weight_file_name_is_derived_from_the_path() -> None:
    assert settings().model_file == PINNED_MODEL_FILE


def test_an_empty_alias_is_refused() -> None:
    with pytest.raises(InvalidAdapterConfigError) as caught:
        settings(model_alias="")
    assert caught.value.field == "modelAlias"


def test_a_mock_labelled_alias_is_refused() -> None:
    """The mirror of the mock adapter refusing a real model identity.

    Without this, a transcript from the real runtime could name a mock identity
    and be filed as mock evidence, or the reverse.
    """
    with pytest.raises(InvalidAdapterConfigError) as caught:
        settings(model_alias="mock-fixed-fixture")
    assert caught.value.field == "modelAlias"


# --------------------------------------------------------------------------
# The numbers ADR 0002 leaves undecided
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("field", "value", "expected_field"),
    [
        ("context_size", 0, "contextSize"),
        ("context_size", -1, "contextSize"),
        ("threads", 0, "threads"),
        ("startup_budget_ms", 0, "startupBudgetMs"),
    ],
)
def test_a_non_positive_number_is_refused(
    field: str, value: int, expected_field: str
) -> None:
    with pytest.raises(InvalidAdapterConfigError) as caught:
        settings(**{field: value})
    assert caught.value.field == expected_field


@pytest.mark.parametrize("name", [ENV_CONTEXT_SIZE, ENV_THREADS, ENV_STARTUP_BUDGET_MS])
def test_a_number_adr_0002_leaves_undecided_has_no_default(name: str) -> None:
    """Omitting it is a refusal naming the variable, not a value nobody chose."""
    environment = dict(VALID_ENVIRONMENT)
    del environment[name]
    with pytest.raises(InvalidAdapterConfigError) as caught:
        LlamaServerSettings.from_environment(environment)
    assert caught.value.field == name


# --------------------------------------------------------------------------
# Construction from the environment
# --------------------------------------------------------------------------


def test_a_complete_environment_produces_settings() -> None:
    built = LlamaServerSettings.from_environment(VALID_ENVIRONMENT)
    assert built.context_size == 4096
    assert built.threads == 6
    assert built.startup_budget_ms == 300000
    assert built.metrics_enabled is True


def test_the_required_variables_are_exactly_those_without_a_default() -> None:
    """The published list and the behaviour cannot say different things."""
    for name in REQUIRED_ENVIRONMENT_VARIABLES:
        environment = dict(VALID_ENVIRONMENT)
        del environment[name]
        with pytest.raises(InvalidAdapterConfigError):
            LlamaServerSettings.from_environment(environment)


def test_every_required_variable_is_present_in_the_valid_environment() -> None:
    assert set(REQUIRED_ENVIRONMENT_VARIABLES) == set(VALID_ENVIRONMENT)


def test_no_variable_is_both_required_and_optional() -> None:
    assert not set(REQUIRED_ENVIRONMENT_VARIABLES) & set(OPTIONAL_ENVIRONMENT_VARIABLES)


def test_an_empty_required_variable_is_the_same_as_an_absent_one() -> None:
    environment = dict(VALID_ENVIRONMENT) | {ENV_ENDPOINT: ""}
    with pytest.raises(InvalidAdapterConfigError) as caught:
        LlamaServerSettings.from_environment(environment)
    assert caught.value.field == ENV_ENDPOINT


def test_a_non_numeric_variable_is_refused_without_echoing_it() -> None:
    environment = dict(VALID_ENVIRONMENT) | {ENV_THREADS: "six"}
    with pytest.raises(InvalidAdapterConfigError) as caught:
        LlamaServerSettings.from_environment(environment)
    assert caught.value.field == ENV_THREADS
    assert "six" not in caught.value.reason


@pytest.mark.parametrize("value", ["0", "false", "FALSE", "no", "off"])
def test_metrics_can_be_turned_off_explicitly(value: str) -> None:
    """Off is the deviation from ADR 0002's position, so off is what is written."""
    environment = dict(VALID_ENVIRONMENT) | {ENV_METRICS_ENABLED: value}
    assert LlamaServerSettings.from_environment(environment).metrics_enabled is False


@pytest.mark.parametrize("value", ["1", "true", "TRUE", "yes", "on"])
def test_metrics_can_be_turned_on_explicitly(value: str) -> None:
    environment = dict(VALID_ENVIRONMENT) | {ENV_METRICS_ENABLED: value}
    assert LlamaServerSettings.from_environment(environment).metrics_enabled is True


def test_an_unreadable_boolean_is_refused_rather_than_treated_as_false() -> None:
    """Silently reading an unknown word as ``false`` disables metrics quietly."""
    environment = dict(VALID_ENVIRONMENT) | {ENV_METRICS_ENABLED: "maybe"}
    with pytest.raises(InvalidAdapterConfigError) as caught:
        LlamaServerSettings.from_environment(environment)
    assert caught.value.field == ENV_METRICS_ENABLED


def test_settings_are_immutable() -> None:
    built = settings()
    with pytest.raises(AttributeError):
        built.endpoint = "http://elsewhere:8080"  # type: ignore[misc]
