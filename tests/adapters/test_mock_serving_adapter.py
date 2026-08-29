"""What the mock serving adapter owes beyond protocol conformance.

Four groups of obligation, and the reason each one is a test rather than a
paragraph:

**Determinism.** ``spec.mockLlm.determinism`` is pinned to ``fixed-fixture``, and
a mock that varies is a mock nobody can assert against. The committed response
fixture is the source of truth and this suite reads it; the adapter carries the
same strings as constants because nothing in the distribution may read a file.

**Failure injection.** Each canonical error a caller has to handle is produced by
a scenario that names it. The scenario value and the error code are the same
string, so the two cannot drift.

**Mock identity.** Boundary rule 6 says a mock artifact declares itself in its own
contents. Here that is checked against the two committed files that publish the
mock identity — the compatibility matrix and the response fixture — rather than
against a constant this suite also wrote.

**Safeguards against false real-serving evidence.** The adapter refuses a real
model identity, declares real model inference unsupported, counts no tokens, and
declares an evidence class whose ceiling in the committed strategy is ``C1``. A
mock result cannot pass ``C2`` certification, and this is the mechanical half of
saying so.

Every check reads files from this repository and objects from this distribution.
No network, no cluster, no model, no credential, no clock, no randomness.
"""

from __future__ import annotations

import ast
import json
from pathlib import Path
from typing import Any

import pytest

from inferops.adapters import (
    MOCK_ADAPTER_KIND,
    MOCK_BOUNDARY_RULE_REF,
    MOCK_DETERMINISM,
    MOCK_EVIDENCE_CLASS,
    MOCK_FIXTURE_CONTENT,
    MOCK_FIXTURE_FINISH_REASON,
    MOCK_FIXTURE_REF,
    MOCK_MAX_CERTIFICATION,
    MOCK_MODEL_IDENTIFIER,
    MOCK_NOTICE,
    MOCK_RUNTIME_ID,
    MOCK_SERVING_CAPABILITY,
    MockAdapterSettings,
    MockScenario,
    MockServingAdapter,
)
from inferops.domain import RequestContext
from inferops.domain.serving import (
    AdapterConfiguration,
    CanonicalError,
    InternalError,
    InvalidAdapterConfigError,
    InvalidValueError,
    ModelNotReadyError,
    RateLimitedError,
    RequestTimeoutError,
    UpstreamTimeoutError,
)

pytestmark = pytest.mark.adapter

REPO_ROOT = Path(__file__).resolve().parents[2]
FIXTURE_PATH = REPO_ROOT / MOCK_FIXTURE_REF
COMPATIBILITY_PATH = (
    REPO_ROOT
    / "contracts"
    / "workload"
    / "compatibility"
    / "runtime-model-compatibility.v1alpha1.json"
)
STRATEGY_PATH = REPO_ROOT / "docs" / "testing" / "test-strategy.v1alpha1.json"
TELEMETRY_PATH = REPO_ROOT / "docs" / "telemetry" / "telemetry-catalog.v1alpha1.json"
MOCK_WORKLOAD_PATH = (
    REPO_ROOT / "contracts" / "workload" / "examples" / "valid" / "mock-llm-ci.yaml"
)
ADAPTER_SOURCE_PATH = REPO_ROOT / "src" / "inferops" / "adapters" / "mock_serving.py"

#: Every scenario that fails, the error it raises, and the code it carries.
FAILURE_SCENARIOS = (
    (MockScenario.MODEL_NOT_READY, ModelNotReadyError, "model-not-ready"),
    (MockScenario.REQUEST_TIMEOUT, RequestTimeoutError, "request-timeout"),
    (MockScenario.UPSTREAM_TIMEOUT, UpstreamTimeoutError, "upstream-timeout"),
    (MockScenario.RATE_LIMITED, RateLimitedError, "rate-limited"),
    (MockScenario.INTERNAL_ERROR, InternalError, "internal-error"),
)

#: Import roots that would mean the mock reaches outside the process. None of
#: them is in the standard library's forbidden list — the architecture suite
#: already refuses a third-party import — so this names the standard-library
#: modules a fixture replayer has no business using.
FORBIDDEN_STDLIB_ROOTS = frozenset(
    {
        "http",
        "urllib",
        "socket",
        "ssl",
        "ftplib",
        "smtplib",
        "subprocess",
        "shutil",
        "tempfile",
        "pathlib",
        "os",
        "random",
        "secrets",
        "time",
        "datetime",
    }
)

#: Names and attributes that would open a file or read the environment. The
#: architecture suite refuses a file read anywhere under ``src/inferops/``; these
#: four are named here as well because a mock acquiring a credential is the
#: specific failure this adapter is supposed to make impossible.
FORBIDDEN_ACCESSORS = frozenset({"environ", "getenv", "open", "read_text"})


def load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


@pytest.fixture
def context() -> RequestContext:
    """Request identifiers a caller supplied."""
    return RequestContext(request_id="req-mock-001", correlation_id="corr-mock-002")


@pytest.fixture
def config() -> AdapterConfiguration:
    """A configuration the mock accepts."""
    return AdapterConfiguration(
        model_identifier=MOCK_MODEL_IDENTIFIER, timeout_ms=30000
    )


async def initialized(
    context: RequestContext,
    config: AdapterConfiguration,
    settings: MockAdapterSettings | None = None,
) -> MockServingAdapter:
    """A mock adapter that has been initialized with ``config``."""
    adapter = MockServingAdapter(settings)
    await adapter.initialize(config, context)
    return adapter


# --------------------------------------------------------------------------
# Determinism
# --------------------------------------------------------------------------


class TestDeterminism:
    """Identical input produces identical output, run after run."""

    async def test_repeated_inference_produces_an_identical_result(
        self,
        context: RequestContext,
        config: AdapterConfiguration,
    ) -> None:
        """The same adapter answering the same prompt twice answers the same."""
        adapter = await initialized(context, config)

        first = await adapter.infer("a prompt", context)
        second = await adapter.infer("a prompt", context)

        assert first == second

    async def test_two_instances_produce_an_identical_result(
        self,
        context: RequestContext,
        config: AdapterConfiguration,
    ) -> None:
        """Determinism survives the process boundary a fresh instance stands for."""
        first_adapter = await initialized(context, config)
        second_adapter = await initialized(context, config)

        assert await first_adapter.infer(
            "a prompt", context
        ) == await second_adapter.infer("a prompt", context)

    async def test_the_response_does_not_vary_with_the_prompt(
        self,
        context: RequestContext,
        config: AdapterConfiguration,
    ) -> None:
        """A fixed fixture is fixed.

        A mock whose output varied with the prompt would tempt a reader into
        reading the variation as behaviour, and there is no behaviour here.
        """
        adapter = await initialized(context, config)

        first = await adapter.infer("one prompt", context)
        second = await adapter.infer("an entirely different prompt", context)

        assert first.content == second.content

    async def test_the_prompt_is_not_echoed_into_the_result(
        self,
        context: RequestContext,
        config: AdapterConfiguration,
    ) -> None:
        """No prompt reaches a response, which is the redaction rule holding."""
        adapter = await initialized(context, config)
        prompt = "a distinctive prompt nobody should see again"

        result = await adapter.infer(prompt, context)

        assert prompt not in result.content
        assert prompt not in result.model


class TestFixtureAgreement:
    """The adapter and the committed fixture publish the same strings."""

    def test_the_committed_fixture_exists(self) -> None:
        """A fixture reference that does not resolve is a dangling contract."""
        assert FIXTURE_PATH.is_file(), MOCK_FIXTURE_REF

    def test_the_workload_example_points_at_the_same_fixture(self) -> None:
        """The mock-llm example and the adapter replay the same file."""
        document = MOCK_WORKLOAD_PATH.read_text(encoding="utf-8")

        assert MOCK_FIXTURE_REF in document
        assert MOCK_DETERMINISM in document

    async def test_the_content_is_the_content_of_the_fixture(
        self,
        context: RequestContext,
        config: AdapterConfiguration,
    ) -> None:
        """The distribution reads no file, so this suite reads it for it."""
        fixture = load_json(FIXTURE_PATH)
        expected = fixture["choices"][0]["message"]["content"]
        adapter = await initialized(context, config)

        result = await adapter.infer("a prompt", context)

        assert result.content == expected
        assert expected == MOCK_FIXTURE_CONTENT

    async def test_the_finish_reason_is_the_finish_reason_of_the_fixture(
        self,
        context: RequestContext,
        config: AdapterConfiguration,
    ) -> None:
        """The same agreement, for the field a caller branches on."""
        fixture = load_json(FIXTURE_PATH)
        adapter = await initialized(context, config)

        result = await adapter.infer("a prompt", context)

        assert result.finish_reason == fixture["choices"][0]["finish_reason"]
        assert fixture["choices"][0]["finish_reason"] == MOCK_FIXTURE_FINISH_REASON


# --------------------------------------------------------------------------
# Failure injection
# --------------------------------------------------------------------------


class TestFailureInjection:
    """Each canonical failure a caller must handle is reachable on demand."""

    @pytest.mark.parametrize(
        ("scenario", "error_type", "code"),
        FAILURE_SCENARIOS,
        ids=[scenario.value for scenario, _, _ in FAILURE_SCENARIOS],
    )
    async def test_an_injected_scenario_raises_its_canonical_error(
        self,
        context: RequestContext,
        config: AdapterConfiguration,
        scenario: MockScenario,
        error_type: type[CanonicalError],
        code: str,
    ) -> None:
        """The scenario names the code, and the raised error carries it."""
        adapter = await initialized(
            context, config, MockAdapterSettings(scenario=scenario)
        )

        with pytest.raises(error_type) as raised:
            await adapter.infer("a prompt", context)

        assert raised.value.code == code

    @pytest.mark.parametrize(
        ("scenario", "error_type", "code"),
        FAILURE_SCENARIOS,
        ids=[scenario.value for scenario, _, _ in FAILURE_SCENARIOS],
    )
    async def test_an_injected_failure_carries_the_supplied_context(
        self,
        context: RequestContext,
        config: AdapterConfiguration,
        scenario: MockScenario,
        error_type: type[CanonicalError],
        code: str,
    ) -> None:
        """A refusal a caller cannot correlate is a refusal nobody can trace."""
        adapter = await initialized(
            context, config, MockAdapterSettings(scenario=scenario)
        )

        with pytest.raises(error_type) as raised:
            await adapter.infer("a prompt", context)

        assert raised.value.context.request_id == context.request_id
        assert raised.value.context.correlation_id == context.correlation_id

    @pytest.mark.parametrize(
        ("scenario", "error_type", "code"),
        FAILURE_SCENARIOS,
        ids=[scenario.value for scenario, _, _ in FAILURE_SCENARIOS],
    )
    async def test_an_injected_failure_is_reported_in_telemetry(
        self,
        context: RequestContext,
        config: AdapterConfiguration,
        scenario: MockScenario,
        error_type: type[CanonicalError],
        code: str,
    ) -> None:
        """The telemetry mapping names the same code the caller was given."""
        adapter = await initialized(
            context, config, MockAdapterSettings(scenario=scenario)
        )

        mapping = await adapter.get_telemetry_mapping()

        assert mapping.error_code == code

    async def test_a_succeeding_adapter_reports_no_error_code(
        self,
        context: RequestContext,
        config: AdapterConfiguration,
    ) -> None:
        """An absent error is absent, not an empty code."""
        adapter = await initialized(context, config)

        assert (await adapter.get_telemetry_mapping()).error_code is None

    async def test_a_not_ready_scenario_also_reports_not_ready(
        self,
        context: RequestContext,
        config: AdapterConfiguration,
    ) -> None:
        """Readiness and inference agree.

        An adapter that reports itself ready and then refuses every request is a
        state no runtime produces and no caller should be written against.
        """
        adapter = await initialized(
            context, config, MockAdapterSettings(scenario=MockScenario.MODEL_NOT_READY)
        )

        assert await adapter.is_ready(context) is False

    @pytest.mark.parametrize(
        ("scenario", "error_type", "code"),
        FAILURE_SCENARIOS,
        ids=[scenario.value for scenario, _, _ in FAILURE_SCENARIOS],
    )
    async def test_a_failure_message_repeats_nothing_from_the_request(
        self,
        context: RequestContext,
        config: AdapterConfiguration,
        scenario: MockScenario,
        error_type: type[CanonicalError],
        code: str,
    ) -> None:
        """A canonical message describes a condition; it does not quote one."""
        adapter = await initialized(
            context, config, MockAdapterSettings(scenario=scenario)
        )
        prompt = "a distinctive prompt nobody should see again"

        with pytest.raises(error_type) as raised:
            await adapter.infer(prompt, context)

        assert prompt not in raised.value.message


class TestLatency:
    """Latency is an input to a test. It is never a measurement."""

    async def test_a_configured_latency_is_accepted(
        self,
        context: RequestContext,
        config: AdapterConfiguration,
    ) -> None:
        """A short latency delays the answer and changes nothing about it."""
        adapter = await initialized(context, config, MockAdapterSettings(latency_ms=1))

        result = await adapter.infer("a prompt", context)

        assert result.content == MOCK_FIXTURE_CONTENT

    async def test_a_latency_reaching_the_timeout_is_a_request_timeout(
        self,
        context: RequestContext,
    ) -> None:
        """The one place the two configured numbers interact, made explicit."""
        config = AdapterConfiguration(
            model_identifier=MOCK_MODEL_IDENTIFIER, timeout_ms=10
        )
        adapter = await initialized(context, config, MockAdapterSettings(latency_ms=10))

        with pytest.raises(RequestTimeoutError):
            await adapter.infer("a prompt", context)

    def test_a_negative_latency_refuses_itself(self) -> None:
        """A setting that cannot be honoured is refused at construction."""
        with pytest.raises(InvalidValueError):
            MockAdapterSettings(latency_ms=-1)


class TestLifecycle:
    """States the protocol can reach that are not a scenario."""

    async def test_an_uninitialized_adapter_is_not_ready(
        self,
        context: RequestContext,
    ) -> None:
        """Readiness before configuration is false rather than optimistic."""
        assert await MockServingAdapter().is_ready(context) is False

    async def test_an_uninitialized_adapter_refuses_inference(
        self,
        context: RequestContext,
    ) -> None:
        """The refusal is canonical, not an attribute error from inside."""
        with pytest.raises(ModelNotReadyError):
            await MockServingAdapter().infer("a prompt", context)

    async def test_a_shut_down_adapter_stops_answering(
        self,
        context: RequestContext,
        config: AdapterConfiguration,
    ) -> None:
        """Shutdown means shut down, and says so canonically."""
        adapter = await initialized(context, config)
        await adapter.shutdown(context)

        assert await adapter.is_ready(context) is False
        with pytest.raises(ModelNotReadyError):
            await adapter.infer("a prompt", context)


# --------------------------------------------------------------------------
# Mock identity
# --------------------------------------------------------------------------


class TestMockIdentity:
    """The mock declares itself, in its own contents, everywhere it can."""

    async def test_every_result_declares_the_mock_adapter_kind(
        self,
        context: RequestContext,
        config: AdapterConfiguration,
    ) -> None:
        """Provenance travels with the result, not with the directory."""
        adapter = await initialized(context, config)

        assert (await adapter.infer("a prompt", context)).adapter_kind == "mock"
        assert MOCK_ADAPTER_KIND == "mock"

    async def test_runtime_metadata_names_the_registered_mock_runtime(
        self,
        context: RequestContext,
        config: AdapterConfiguration,
    ) -> None:
        """The identity is the one the compatibility matrix already publishes."""
        matrix = load_json(COMPATIBILITY_PATH)
        registered = {runtime["runtimeId"]: runtime for runtime in matrix["runtimes"]}
        adapter = await initialized(context, config)

        metadata = await adapter.get_runtime_metadata()

        assert metadata.name == MOCK_RUNTIME_ID
        assert MOCK_RUNTIME_ID in registered
        assert registered[MOCK_RUNTIME_ID]["status"] == "ci-only"
        assert registered[MOCK_RUNTIME_ID]["acceptedArtifactFormats"] == []

    async def test_the_mock_runtime_row_declares_the_mock_serving_capability(
        self,
        context: RequestContext,
        config: AdapterConfiguration,
    ) -> None:
        """The capability the adapter names is the capability the matrix names."""
        matrix = load_json(COMPATIBILITY_PATH)
        row = next(
            runtime
            for runtime in matrix["runtimes"]
            if runtime["runtimeId"] == MOCK_RUNTIME_ID
        )

        assert row["servingCapability"] == MOCK_SERVING_CAPABILITY

    async def test_capabilities_declare_real_model_inference_unsupported(
        self,
        context: RequestContext,
        config: AdapterConfiguration,
    ) -> None:
        """The capability layer says what the adapter kind says."""
        adapter = await initialized(context, config)

        declared = {
            capability.name: capability.supported
            for capability in await adapter.get_capabilities()
        }

        assert declared["real-model-inference"] is False
        assert declared["deterministic-fixture-replay"] is True
        assert declared["streaming"] is False
        assert declared["token-counting"] is False

    async def test_no_token_usage_is_reported(
        self,
        context: RequestContext,
        config: AdapterConfiguration,
    ) -> None:
        """A count nobody measured is absent rather than invented.

        A real runtime's counts come from its own tokeniser. A mock's would be
        numbers its author chose, and a chosen number that looks like a measured
        one is the worst kind of evidence.
        """
        adapter = await initialized(context, config)

        assert (await adapter.infer("a prompt", context)).usage is None
        assert (await adapter.get_telemetry_mapping()).token_usage is False

    async def test_no_model_revision_is_invented(
        self,
        context: RequestContext,
        config: AdapterConfiguration,
    ) -> None:
        """There is no model, so there is no revision, so the field is absent."""
        adapter = await initialized(context, config)

        assert (await adapter.get_model_metadata()).revision is None

    def test_the_identity_block_matches_the_committed_fixture(self) -> None:
        """Boundary rule 6, checked against the artifact that already obeys it."""
        fixture = load_json(FIXTURE_PATH)
        declared = MockServingAdapter().mock_identity()

        assert declared["isMock"] is True
        assert declared["notice"] == fixture["_inferopsMock"]["notice"]
        assert declared["boundaryRule"] == fixture["_inferopsMock"]["boundaryRule"]
        assert fixture["_inferopsMock"]["notice"] == MOCK_NOTICE
        assert fixture["_inferopsMock"]["boundaryRule"] == MOCK_BOUNDARY_RULE_REF

    def test_the_identity_block_names_the_rule_document_that_exists(self) -> None:
        """A boundary reference that does not resolve is a reference to nothing."""
        assert (REPO_ROOT / MOCK_BOUNDARY_RULE_REF).is_file()

    async def test_telemetry_identity_uses_only_catalog_attributes(
        self,
        context: RequestContext,
        config: AdapterConfiguration,
    ) -> None:
        """Mock identity travels as attributes the catalog already publishes.

        The catalog's note on ``inferops.runtime.id`` is the mechanism: the
        registered runtime identifier includes the mock runtime, which is how a
        mock result stays visibly a mock result wherever it is read.
        """
        catalog = load_json(TELEMETRY_PATH)
        published = {
            attribute["name"]: attribute for attribute in catalog["attributes"]
        }
        adapter = await initialized(context, config)

        identity = adapter.telemetry_identity()

        assert identity
        for name in identity:
            assert name in published, name
            placements = published[name]["placements"]
            assert "log-field" in placements, name
            assert "evidence-field" in placements, name

    async def test_telemetry_identity_names_the_mock_runtime_and_capability(
        self,
        context: RequestContext,
        config: AdapterConfiguration,
    ) -> None:
        """The values, not just the keys, are what make the label legible."""
        adapter = await initialized(context, config)

        identity = adapter.telemetry_identity()

        assert identity["inferops.runtime.id"] == MOCK_RUNTIME_ID
        assert identity["inferops.capability.id"] == MOCK_SERVING_CAPABILITY
        assert identity["inferops.model.id"] == MOCK_MODEL_IDENTIFIER


# --------------------------------------------------------------------------
# Safeguards against false real-serving evidence
# --------------------------------------------------------------------------


class TestRealServingSafeguards:
    """What stops a mock transcript being read as a real one."""

    @pytest.mark.parametrize(
        "identifier",
        [
            "Qwen/Qwen3-1.7B-GGUF",
            "llama-cpp-server",
            "gpt-4",
            "real-model",
            "fixed-fixture",
        ],
    )
    async def test_a_non_mock_model_identity_is_refused(
        self,
        context: RequestContext,
        identifier: str,
    ) -> None:
        """A transcript naming a real model is the artifact somebody misreads.

        The refusal is at configuration time, because by the time a result
        exists the identity is already in it.
        """
        config = AdapterConfiguration(model_identifier=identifier, timeout_ms=30000)

        with pytest.raises(InvalidAdapterConfigError) as raised:
            await MockServingAdapter().initialize(config, context)

        assert raised.value.field == "model_identifier"

    async def test_a_refused_identity_is_not_repeated_in_the_refusal(
        self,
        context: RequestContext,
    ) -> None:
        """The refusal names the field and the constraint, not the value."""
        identifier = "Qwen/Qwen3-1.7B-GGUF"
        config = AdapterConfiguration(model_identifier=identifier, timeout_ms=30000)

        with pytest.raises(InvalidAdapterConfigError) as raised:
            await MockServingAdapter().initialize(config, context)

        assert identifier not in str(raised.value.as_dict())

    async def test_a_mock_labelled_identity_is_accepted(
        self,
        context: RequestContext,
    ) -> None:
        """The rule is a prefix, not a single hard-coded name."""
        config = AdapterConfiguration(
            model_identifier="mock-another-fixture", timeout_ms=30000
        )
        adapter = MockServingAdapter()

        await adapter.initialize(config, context)

        assert (await adapter.get_model_metadata()).identifier == "mock-another-fixture"

    def test_the_adapter_declares_the_mock_evidence_class(self) -> None:
        """The class is the mock class, and the class carries the ceiling."""
        assert MOCK_EVIDENCE_CLASS == "mock"
        assert MOCK_MAX_CERTIFICATION == "C1"

    def test_the_declared_ceiling_is_the_one_the_strategy_publishes(self) -> None:
        """The adapter does not get to nominate its own strength.

        The committed strategy assigns a ceiling to the evidence class, and this
        asserts the adapter's declaration equals it rather than restating it.
        """
        strategy = load_json(STRATEGY_PATH)
        classes = {entry["classId"]: entry for entry in strategy["evidenceClasses"]}

        assert (
            classes[MOCK_EVIDENCE_CLASS]["maxCertification"] == MOCK_MAX_CERTIFICATION
        )

    def test_the_adapter_layer_is_ceilinged_at_the_mock_class(self) -> None:
        """The layer this suite belongs to cannot certify above C1 either."""
        strategy = load_json(STRATEGY_PATH)
        layer = next(
            entry for entry in strategy["layers"] if entry["layerId"] == "adapter"
        )

        assert layer["evidenceClass"] == MOCK_EVIDENCE_CLASS
        assert layer["maxCertification"] == MOCK_MAX_CERTIFICATION
        assert layer["requiresModel"] is False
        assert layer["requiresCluster"] is False

    def test_no_c2_claim_rests_on_the_adapter_layer_alone(self) -> None:
        """A C2 claim citing this layer cites a real one as well.

        The strategy suite already refuses a real claim reaching its level
        through an unreal layer. This states the consequence from the mock's
        side: every claim that names the adapter layer and requires C2 also
        names a layer that loads a model.
        """
        strategy = load_json(STRATEGY_PATH)
        layers = {entry["layerId"]: entry for entry in strategy["layers"]}

        for claim in strategy["claims"]:
            if "adapter" not in claim["layers"]:
                continue
            if claim["requiredCertification"] in {"C0", "C1"}:
                continue
            assert any(
                layers[layer_id]["evidenceClass"] not in {"mock", "synthetic"}
                for layer_id in claim["layers"]
            ), claim["claimId"]


class TestNoExternalDependency:
    """No credential, no model file, no network, and nothing that varies.

    The architecture suite already refuses a third-party import anywhere under
    ``src/inferops/``. This adds the standard-library half for this module: a
    fixture replayer that opened a socket, read an environment variable, or
    consulted a clock would satisfy that rule and still be something other than
    a deterministic mock.
    """

    def test_the_adapter_imports_nothing_that_reaches_outside_the_process(
        self,
    ) -> None:
        """The import list, read from the source rather than from memory."""
        tree = ast.parse(ADAPTER_SOURCE_PATH.read_text(encoding="utf-8"))
        roots: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                roots |= {alias.name.split(".")[0] for alias in node.names}
            elif (
                isinstance(node, ast.ImportFrom)
                and node.level == 0
                and node.module is not None
            ):
                roots.add(node.module.split(".")[0])

        assert not roots & FORBIDDEN_STDLIB_ROOTS, sorted(
            roots & FORBIDDEN_STDLIB_ROOTS
        )

    def test_the_adapter_names_no_environment_or_file_access(self) -> None:
        """A credential arrives through the environment or through a file.

        Neither route exists here, and the source is where that is checked: no
        name and no attribute in this module is one of the four that would open
        one. Prose in a docstring is not code, so this reads the parse tree
        rather than the text.
        """
        tree = ast.parse(ADAPTER_SOURCE_PATH.read_text(encoding="utf-8"))
        used: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Name):
                used.add(node.id)
            elif isinstance(node, ast.Attribute):
                used.add(node.attr)

        assert not used & FORBIDDEN_ACCESSORS, sorted(used & FORBIDDEN_ACCESSORS)
