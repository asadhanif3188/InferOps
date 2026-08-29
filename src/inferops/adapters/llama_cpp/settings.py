"""Runtime-specific settings for `llama-server`, kept where they cannot leak.

This is the module the platform/domain boundary exists for. A context length, a
thread count, a bind endpoint, and a weight-file path are `llama.cpp` concepts;
none of them appears in :class:`~inferops.domain.serving.AdapterConfiguration`,
in the workload contract, or in any domain object, and the direction of that
dependency is `ADR 0004`'s rather than a convenience.

**Nothing here has a default that stands in for a decision.** `ADR 0002` records
that the context length, the KV budget, the concurrency limit, and the sampling
defaults remain undecided, and that the 4096 context and 6 threads the trial ran
were stated inputs so its numbers could be interpreted — not recommended values.
So the context size and the thread count are required inputs with no default. An
operator supplies them and owns them; this module refuses to invent one and then
have it read back later as a project recommendation.

The one setting that does carry a default is ``metrics_enabled``. `ADR 0002`'s
`T7` exception is argued on the runtime exposing its own metrics endpoint with no
exporter and no sidecar, and that endpoint exists only when the runtime is
started with its metrics flag. Leaving it on is therefore the accepted position
and turning it off is the deviation, so the deviation is the one that has to be
written down.

**No value read from configuration is ever repeated in an error.** A refusal
names the field or the environment variable and states the constraint, in the
same division of labour the domain's own errors use: an endpoint is exactly where
a credential arrives, and an error message is exactly where one gets published.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from urllib.parse import urlsplit

from ...domain.serving import InvalidAdapterConfigError

#: Where InferOps reaches the runtime. A base URL, with no path of its own: the
#: endpoint paths below are appended to it.
ENV_ENDPOINT = "INFEROPS_LLAMA_SERVER_ENDPOINT"

#: The absolute path of the weight file *inside the serving container*. It is a
#: container path and never a contributor's own path, which is the difference
#: between a value that can be committed and one that cannot.
ENV_MODEL_PATH = "INFEROPS_LLAMA_SERVER_MODEL_PATH"

#: The operator-supplied label the runtime echoes back as the model identifier.
#: The echo proves the flag was accepted and proves nothing about which bytes
#: were loaded.
ENV_MODEL_ALIAS = "INFEROPS_LLAMA_SERVER_MODEL_ALIAS"

#: The context length. Undecided by ADR 0002 and therefore required here.
ENV_CONTEXT_SIZE = "INFEROPS_LLAMA_SERVER_CONTEXT_SIZE"

#: The thread count. Undecided by ADR 0002 and therefore required here.
ENV_THREADS = "INFEROPS_LLAMA_SERVER_THREADS"

#: How long the model may take to become ready before the platform stops
#: waiting. Distinct from a request timeout: one bounds a load, the other bounds
#: a call.
ENV_STARTUP_BUDGET_MS = "INFEROPS_LLAMA_SERVER_STARTUP_BUDGET_MS"

#: Whether the runtime was started with its own metrics endpoint. Optional, and
#: the only optional one.
ENV_METRICS_ENABLED = "INFEROPS_LLAMA_SERVER_METRICS_ENABLED"

#: Every variable a caller must set. Absence of any one is a refusal, not a
#: default.
REQUIRED_ENVIRONMENT_VARIABLES: tuple[str, ...] = (
    ENV_ENDPOINT,
    ENV_MODEL_PATH,
    ENV_MODEL_ALIAS,
    ENV_CONTEXT_SIZE,
    ENV_THREADS,
    ENV_STARTUP_BUDGET_MS,
)

#: Every variable a caller may set.
OPTIONAL_ENVIRONMENT_VARIABLES: tuple[str, ...] = (ENV_METRICS_ENABLED,)

#: Readiness. Returns 200 once the model can answer and 503 while it loads.
HEALTH_PATH = "/health"

#: The runtime's own description of the process and the file it loaded.
PROPS_PATH = "/props"

#: The model list, which echoes the configured alias.
MODELS_PATH = "/v1/models"

#: The runtime's Prometheus endpoint, present only when metrics are enabled.
METRICS_PATH = "/metrics"

#: Every runtime path this adapter is permitted to build a URL for. Inference is
#: absent on purpose: the call that generates a completion belongs to the
#: inference client, and adding its path here before that client exists would put
#: the door in the wall ahead of the room.
ACCEPTED_RUNTIME_PATHS = frozenset({HEALTH_PATH, PROPS_PATH, MODELS_PATH, METRICS_PATH})

#: The URL schemes an endpoint may use. ``https`` is admitted because refusing
#: it would make the safer choice the impossible one; V1's own serving path is
#: in-cluster and plaintext, and `ADR 0008` is where that is argued.
ACCEPTED_ENDPOINT_SCHEMES = frozenset({"http", "https"})

#: The prefix that marks a mock identity. A real runtime's alias may not carry
#: it, which is the mirror of the mock adapter refusing a real model identity.
#: The two adapters hold this string separately because neither may import the
#: other, and ``tests/adapters/test_llama_server_agreement.py`` compares the two
#: copies so that renaming one and not the other is a failing assertion rather
#: than a silently broken safeguard.
#:
#: The comparison here is case-insensitive while the mock's is not, and the
#: asymmetry is deliberate: the mock *requires* the prefix, so a strict match is
#: the safe direction there, and this one *refuses* it, so the permissive match
#: is the safe direction here.
MOCK_IDENTITY_PREFIX = "mock-"

#: The suffix of the only artifact format this runtime loads.
GGUF_SUFFIX = ".gguf"

#: Characters an endpoint may not contain at all. ``?`` and ``#`` open a query
#: and a fragment, and an *empty* one of either passes every structural check
#: while still swallowing the path this adapter appends — ``http://host?`` plus
#: ``/health`` is a request for ``/`` with ``/health`` as its query string. A
#: backslash is refused because ``urlsplit`` leaves it inside the authority
#: while some HTTP clients read it as a separator, and a value two parsers
#: disagree about is a value neither should be trusted on.
FORBIDDEN_ENDPOINT_CHARACTERS = ("?", "#", "\\")

#: Values accepted for the optional boolean variable, lowercased.
TRUE_VALUES = frozenset({"1", "true", "yes", "on"})
FALSE_VALUES = frozenset({"0", "false", "no", "off"})


@dataclass(frozen=True, slots=True)
class LlamaServerSettings:
    """One deployment of `llama-server`, as the values needed to talk to it.

    Immutable, and validated at construction rather than at first use: a setting
    that is wrong is wrong before any request arrives, and finding out at the
    first request means finding out in a caller's trace instead of at startup.

    Attributes:
        endpoint: Base URL of the runtime, with no path, query, fragment, or
            credentials.
        model_path: Absolute container path of the ``.gguf`` weight file.
        model_alias: The label the runtime is started with and echoes back.
        context_size: Context length, in tokens. Required; ADR 0002 decides none.
        threads: Thread count. Required; ADR 0002 decides none.
        startup_budget_ms: How long the model may take to become ready.
        metrics_enabled: Whether the runtime exposes its own metrics endpoint.
    """

    endpoint: str
    model_path: str
    model_alias: str
    context_size: int
    threads: int
    startup_budget_ms: int
    metrics_enabled: bool = True

    def __post_init__(self) -> None:
        self._validate_endpoint()
        self._validate_model_path()
        self._validate_model_alias()
        _require_positive(self.context_size, "contextSize")
        _require_positive(self.threads, "threads")
        _require_positive(self.startup_budget_ms, "startupBudgetMs")

    # -- derived values --------------------------------------------------

    def url_for(self, path: str) -> str:
        """The absolute URL of one runtime path, joined to the endpoint.

        Only the paths this module publishes are accepted. An arbitrary path
        would make this a general-purpose URL builder aimed at a host read from
        the environment, which is a request-forgery primitive rather than a
        configuration helper.
        """
        if path not in ACCEPTED_RUNTIME_PATHS:
            raise InvalidAdapterConfigError(
                "path", "must be one of the runtime paths this adapter publishes"
            )
        if path == METRICS_PATH and not self.metrics_enabled:
            raise InvalidAdapterConfigError(
                "metricsEnabled",
                "the runtime metrics path is unavailable when metrics are disabled",
            )
        return f"{self.base_url}{path}"

    @property
    def base_url(self) -> str:
        """The endpoint reduced to scheme and authority, and nothing else.

        Rebuilt from the parsed parts rather than trimmed from the string the
        caller supplied. Appending a path to a string that was merely *checked*
        leaves whatever the check tolerated in front of the path; appending it to
        one that was *reconstructed* cannot.
        """
        parts = urlsplit(self.endpoint)
        return f"{parts.scheme}://{parts.netloc}"

    @property
    def model_file(self) -> str:
        """The weight file's own name, without the directory it is mounted in."""
        return self.model_path.rsplit("/", 1)[-1]

    # -- validation ------------------------------------------------------

    def _validate_endpoint(self) -> None:
        if not self.endpoint:
            raise InvalidAdapterConfigError("endpoint", "must not be empty")
        for character in FORBIDDEN_ENDPOINT_CHARACTERS:
            if character in self.endpoint:
                raise InvalidAdapterConfigError(
                    "endpoint",
                    "must contain no query, fragment, or backslash character, "
                    "even an empty one: each would capture the runtime path this "
                    "adapter appends",
                )
        parts = urlsplit(self.endpoint)
        if parts.scheme not in ACCEPTED_ENDPOINT_SCHEMES:
            raise InvalidAdapterConfigError(
                "endpoint",
                "must be an absolute URL whose scheme is 'http' or 'https'",
            )
        if not parts.hostname:
            raise InvalidAdapterConfigError("endpoint", "must name a host")
        if parts.username is not None or parts.password is not None:
            raise InvalidAdapterConfigError(
                "endpoint",
                "must not carry credentials; a credential in a URL is a "
                "credential in every log line that records the URL",
            )
        if parts.query or parts.fragment:
            raise InvalidAdapterConfigError(
                "endpoint", "must carry no query string and no fragment"
            )
        if parts.path not in {"", "/"}:
            raise InvalidAdapterConfigError(
                "endpoint",
                "must be a base URL with no path; the runtime paths are appended "
                "to it by this adapter",
            )

    def _validate_model_path(self) -> None:
        if not self.model_path.startswith("/"):
            raise InvalidAdapterConfigError(
                "modelPath", "must be an absolute path inside the serving container"
            )
        if ".." in self.model_path.split("/"):
            raise InvalidAdapterConfigError(
                "modelPath", "must not traverse upwards with '..'"
            )
        if not self.model_path.endswith(GGUF_SUFFIX):
            raise InvalidAdapterConfigError(
                "modelPath",
                f"must name a '{GGUF_SUFFIX}' file, the only artifact format this "
                "runtime loads",
            )

    def _validate_model_alias(self) -> None:
        if not self.model_alias:
            raise InvalidAdapterConfigError("modelAlias", "must not be empty")
        if self.model_alias.lower().startswith(MOCK_IDENTITY_PREFIX):
            raise InvalidAdapterConfigError(
                "modelAlias",
                "a real runtime may not serve a mock-labelled identity, which "
                f"starts with '{MOCK_IDENTITY_PREFIX}'",
            )

    # -- construction from the environment -------------------------------

    @classmethod
    def from_environment(cls, environment: Mapping[str, str]) -> LlamaServerSettings:
        """Build settings from a mapping of environment variables.

        The mapping is passed in rather than read from the process, so that this
        is a function of its argument: a settings object built in a test and one
        built at startup take the same path, and nothing here depends on ambient
        state.
        """
        return cls(
            endpoint=_required(environment, ENV_ENDPOINT),
            model_path=_required(environment, ENV_MODEL_PATH),
            model_alias=_required(environment, ENV_MODEL_ALIAS),
            context_size=_required_int(environment, ENV_CONTEXT_SIZE),
            threads=_required_int(environment, ENV_THREADS),
            startup_budget_ms=_required_int(environment, ENV_STARTUP_BUDGET_MS),
            metrics_enabled=_optional_bool(
                environment, ENV_METRICS_ENABLED, default=True
            ),
        )


def _require_positive(value: int, field: str) -> None:
    if value <= 0:
        raise InvalidAdapterConfigError(field, "must be a positive whole number")


def _required(environment: Mapping[str, str], name: str) -> str:
    value = environment.get(name, "")
    if not value:
        raise InvalidAdapterConfigError(name, "is required and is not set")
    return value


def _required_int(environment: Mapping[str, str], name: str) -> int:
    value = _required(environment, name)
    try:
        return int(value)
    except ValueError:
        raise InvalidAdapterConfigError(
            name, "must be a whole number written in decimal"
        ) from None


def _optional_bool(environment: Mapping[str, str], name: str, *, default: bool) -> bool:
    value = environment.get(name)
    if value is None or value == "":
        return default
    lowered = value.strip().lower()
    if lowered in TRUE_VALUES:
        return True
    if lowered in FALSE_VALUES:
        return False
    raise InvalidAdapterConfigError(
        name,
        f"must be one of {sorted(TRUE_VALUES)} or {sorted(FALSE_VALUES)}",
    )
