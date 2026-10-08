"""Render refusals: what a render is refused with, and that nothing renders when it is.

Every check reads files from this repository and nothing else. No network, no
cluster, no clock, and no randomness. The renderers here are test doubles of the
interface's shape; the one real renderer, and the four rules only it applies, are
held by ``test_helm_values_renderer``.

Six things are asserted:

1. **One vocabulary.** Every rule a render can be refused under has one category
   and one canonical code; a rule another domain publishes keeps that domain's
   identifier and code; this package's own ten reuse no other identifier; the
   codes are inside the canonical vocabulary the API serves; no category exists
   without a rule; and the published refusal matrix is the code.
2. **Every rule refuses something.** One input per boundary rule, run through the
   canonical path, is refused under exactly that rule, its category, and its code,
   before anything is returned. The renderer's own four are reached by its suite.
3. **Every reason at once, in one order.** Findings from every step are gathered,
   sorted by category, field, and rule; the refusal's code is the first finding's;
   every refusal is non-retryable, carries the request context, and repeats no
   value read out of a document.
4. **No value has two owners.** For each of the 48 render values and each layer
   that does not own it, an input of that layer supplying it is refused as an
   ownership conflict naming the owner - neither value is chosen - and an input
   supplying a value nobody owns is refused rather than dropped. No committed
   valid input reaches the check, because each parser refuses a field its schema
   does not define, and a test says so.
5. **Unsupported versions and profiles are the renderer's to declare.** A
   declaration that cannot be meant is refused; one naming a version the domain
   does not implement is accepted, and refuses today's documents.
6. **Nothing is half-done.** A renderer is called only when every check passed;
   on a refusal it is never called. The reference workload's field-ownership
   matrix is the context the reference inputs produce.
"""

from __future__ import annotations

import copy
import json
import re
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest
import yaml

from inferops.api import errors as api_errors
from inferops.domain import RequestContext
from inferops.domain.environment import (
    BINDING_RULES,
    EnvironmentBinding,
    MalformedEnvironmentBindingError,
    parse_environment_binding,
)
from inferops.domain.release import RELEASE_RULES, GitRevision
from inferops.domain.render import (
    CAPABILITY_UNAVAILABLE,
    CONTRACT_INVALID,
    EXCLUDED_SOURCE_FIELDS,
    PROFILE_CONDITIONS,
    RENDER_FIELD_OWNERSHIP,
    RENDER_RULES,
    VERSION_UNSUPPORTED,
    ApiDefaults,
    ApiRolloutDefaults,
    Layer,
    PlatformDefaults,
    RefusalCategory,
    RenderContext,
    Renderer,
    RendererSupport,
    RenderFinding,
    RenderRefused,
    RuleOrigin,
    RuntimeDefaults,
    RuntimeRolloutDefaults,
    build_render_context,
    ownership_findings,
    prepare_render,
    render_with,
    validate_for_render,
)
from inferops.domain.render import conflicts as conflicts_module
from inferops.domain.workload import (
    CompatibilityMatrixLoader,
    DnsLabel,
    InvalidValueError,
    Profile,
    WorkloadContract,
    parse_workload_contract,
    set_matrix_loader,
)
from tools.contract_validation import RULES as OFFLINE_RULES

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
MATRIX_PATH = (
    REPO_ROOT
    / "contracts"
    / "workload"
    / "compatibility"
    / "runtime-model-compatibility.v1alpha1.json"
)
WORKLOAD_VALID_DIR = REPO_ROOT / "contracts" / "workload" / "examples" / "valid"
WORKLOAD_INVALID_DIR = REPO_ROOT / "contracts" / "workload" / "examples" / "invalid"
BINDING_VALID_DIR = REPO_ROOT / "contracts" / "environment" / "examples" / "valid"
BINDING_INVALID_DIR = REPO_ROOT / "contracts" / "environment" / "examples" / "invalid"
CHART_VALUES = REPO_ROOT / "charts" / "inferops-llm" / "values.yaml"
VALIDATION_MODULE = (
    REPO_ROOT / "src" / "inferops" / "domain" / "workload" / "validation.py"
)
WORKLOAD_DOC = REPO_ROOT / "docs" / "contracts" / "workload-contract.md"
BOUNDARY_DOC = REPO_ROOT / "docs" / "domain" / "renderer-input-boundary.md"

DEFAULTS_REVISION = "b" * 40
RENDERER_REVISION = "a" * 40
CONTRACT_VERSION = "inferops.io/v1alpha1"
BINDING_VERSION = "inferops.io/v1alpha1"
DEFAULTS_VERSION = "v1alpha1"
LATER_VERSION = "inferops.io/v1alpha2"

set_matrix_loader(
    CompatibilityMatrixLoader(json.loads(MATRIX_PATH.read_text(encoding="utf-8")))
)


# --------------------------------------------------------------------------
# Inputs
# --------------------------------------------------------------------------


def load(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def contract_document(name: str = "synchronous-llm-local") -> dict[str, Any]:
    return load(WORKLOAD_VALID_DIR / f"{name}.yaml")


def contract(name: str = "synchronous-llm-local") -> WorkloadContract:
    return parse_workload_contract(contract_document(name))


def invalid_contract(name: str) -> WorkloadContract:
    return parse_workload_contract(load(WORKLOAD_INVALID_DIR / f"{name}.yaml"))


def binding(name: str = "local-docker-desktop") -> EnvironmentBinding:
    return parse_environment_binding(load(BINDING_VALID_DIR / f"{name}.yaml"))


def binding_for(environment: str, name: str | None = None) -> EnvironmentBinding:
    """A binding serving an environment no committed fixture serves."""
    document = load(BINDING_VALID_DIR / "local-kind.yaml")
    document["metadata"]["name"] = name or f"{environment}-kind"
    document["spec"]["environment"] = environment
    document["spec"]["gitops"]["destinationPath"] = (
        f"gitops/environments/{name or environment}-kind"
    )
    return parse_environment_binding(document)


def defaults(version: str = DEFAULTS_VERSION) -> PlatformDefaults:
    """The chart's own defaults, read at a placeholder revision."""
    chart = load(CHART_VALUES)["api"]
    runtime = load(CHART_VALUES)["runtime"]["rollout"]
    return PlatformDefaults(
        version,
        GitRevision(DEFAULTS_REVISION),
        ApiDefaults(
            request_timeout_ms=chart["requestTimeoutMs"],
            drain_timeout_ms=chart["drainTimeoutMs"],
            max_output_tokens=chart["maxOutputTokens"],
            rollout=ApiRolloutDefaults(
                max_unavailable=chart["rollout"]["maxUnavailable"],
                max_surge=chart["rollout"]["maxSurge"],
            ),
        ),
        RuntimeDefaults(
            RuntimeRolloutDefaults(
                max_unavailable=runtime["maxUnavailable"],
                max_surge=runtime["maxSurge"],
            )
        ),
    )


def support(
    *,
    contract_versions: frozenset[str] = frozenset({CONTRACT_VERSION}),
    binding_versions: frozenset[str] = frozenset({BINDING_VERSION}),
    platform_defaults_versions: frozenset[str] = frozenset({DEFAULTS_VERSION}),
    profiles: frozenset[Profile] = frozenset(Profile),
) -> RendererSupport:
    return RendererSupport(
        contract_versions=contract_versions,
        binding_versions=binding_versions,
        platform_defaults_versions=platform_defaults_versions,
        profiles=profiles,
    )


def environment_bindings(workload: WorkloadContract) -> list[EnvironmentBinding]:
    """One binding serving the contract's environment."""
    environment = workload.spec.environment.value
    if environment == "local":
        return [binding()]
    return [binding_for(environment)]


def prepare(
    workload: WorkloadContract,
    *,
    bindings: list[EnvironmentBinding] | None = None,
    platform_defaults: PlatformDefaults | None = None,
    renderer_support: RendererSupport | None = None,
    binding_name: str | None = None,
    context: RequestContext | None = None,
) -> RenderContext:
    return prepare_render(
        workload,
        defaults() if platform_defaults is None else platform_defaults,
        environment_bindings(workload) if bindings is None else bindings,
        support=support() if renderer_support is None else renderer_support,
        binding_name=None if binding_name is None else DnsLabel(binding_name),
        context=RequestContext() if context is None else context,
    )


def refused(**kwargs: Any) -> Callable[[WorkloadContract], RenderRefused]:
    """A function that prepares a contract with ``kwargs`` and returns its refusal."""

    def run(workload: WorkloadContract) -> RenderRefused:
        with pytest.raises(RenderRefused) as raised:
            prepare(workload, **kwargs)
        return raised.value

    return run


# --------------------------------------------------------------------------
# Inputs that carry one more value than their schema has
# --------------------------------------------------------------------------


def _set(document: dict[str, Any], path: str, value: Any) -> None:
    *parents, last = path.split(".")
    node = document
    for step in parents:
        node = node.setdefault(step, {})
    node[last] = value


def carrying[T](original: T, path: str, value: Any) -> T:
    """``original``, whose JSON form carries ``value`` at ``path`` as well.

    The parsers refuse such a document, so this is the only way to build one: a
    subclass of the input's own type, with the same slots, whose ``as_document``
    adds the value. It stands for an input whose type gained a field nobody gave
    an owner - a later version, a new defaults setting - and it passes every
    ``isinstance`` check the boundary makes, as such an input would.
    """
    base = type(original)

    class Carrying(base):  # type: ignore[valid-type, misc]
        __slots__ = ()

        def as_document(self) -> dict[str, Any]:
            document = copy.deepcopy(super().as_document())
            _set(document, path, copy.deepcopy(value))
            return document

    clone = copy.copy(original)
    object.__setattr__(clone, "__class__", Carrying)
    return clone


def supplier(layer: Layer, path: str, value: Any = 7) -> dict[str, Any]:
    """Keyword arguments for :func:`prepare` with ``layer``'s input carrying a value."""
    if layer is Layer.WORKLOAD_INTENT:
        return {"workload": carrying(contract(), path, value)}
    if layer is Layer.PLATFORM_DEFAULTS:
        return {"platform_defaults": carrying(defaults(), path, value)}
    return {"bindings": [carrying(binding(), path, value)]}


def refusal_of(layer: Layer, path: str, value: Any = 7) -> RenderRefused:
    arguments = supplier(layer, path, value)
    workload = arguments.pop("workload", contract())
    with pytest.raises(RenderRefused) as raised:
        prepare(workload, **arguments)
    return raised.value


ROLE = {
    Layer.WORKLOAD_INTENT: "contract",
    Layer.PLATFORM_DEFAULTS: "platformDefaults",
    Layer.ENVIRONMENT_BINDING: "bindings[0]",
}


# --------------------------------------------------------------------------
# 1. One vocabulary
# --------------------------------------------------------------------------


def pipeline_rule_ids() -> set[str]:
    """Every rule identifier the workload's semantic pipeline can cite."""
    source = VALIDATION_MODULE.read_text(encoding="utf-8")
    return set(re.findall(r'rule_id="([a-z-]+)"', source))


def workload_matrix() -> dict[str, tuple[str, str]]:
    """The contract document's rule matrix: rule -> (code, layer)."""
    text = WORKLOAD_DOC.read_text(encoding="utf-8")
    section = text.split("### The rule matrix", 1)[1].split("\n\n|", 1)[1]
    found: dict[str, tuple[str, str]] = {}
    for line in ("|" + section).splitlines()[2:]:
        if not line.startswith("|"):
            break
        cells = [cell.strip() for cell in line.strip("|").split("|")]
        found[cells[0].strip("`")] = (cells[1].strip("`"), cells[2])
    return found


def rules_of(origin: RuleOrigin) -> set[str]:
    return {key for key, rule in RENDER_RULES.items() if rule.origin is origin}


def test_every_rule_is_keyed_by_its_own_identifier() -> None:
    for key, rule in RENDER_RULES.items():
        assert key == rule.identifier
        assert rule.summary and rule.summary == rule.summary.strip()


def test_the_reused_workload_rules_are_exactly_those_the_contract_gate_cites() -> None:
    """The pipeline's seven and the profile conditions' three, and nothing else."""
    cited = pipeline_rule_ids() | {c.rule_id for c in PROFILE_CONDITIONS}
    assert len(pipeline_rule_ids()) == 7
    assert rules_of(RuleOrigin.WORKLOAD_CONTRACT) == cited
    assert len(cited) == 10


def test_each_reused_workload_rule_keeps_its_published_code_and_layer() -> None:
    """A structural rule is a shape refusal here; a semantic one is not."""
    matrix = workload_matrix()
    for identifier in rules_of(RuleOrigin.WORKLOAD_CONTRACT):
        code, layer = matrix[identifier]
        rule = RENDER_RULES[identifier]
        assert rule.code == code, identifier
        assert (rule.category is RefusalCategory.SHAPE_INVALID) == (
            layer == "Structural"
        ), identifier
        assert identifier in OFFLINE_RULES, identifier


def test_the_matrix_rules_are_the_model_and_runtime_category() -> None:
    assert {
        key
        for key, rule in RENDER_RULES.items()
        if rule.category is RefusalCategory.MODEL_RUNTIME_INCOMPATIBLE
    } == {
        "runtime-unregistered",
        "model-artifact-format-unknown",
        "runtime-model-incompatible",
    }


def test_the_reused_binding_rules_are_the_binding_domains_with_their_codes() -> None:
    assert rules_of(RuleOrigin.ENVIRONMENT_BINDING) == set(BINDING_RULES)
    for identifier, rule in BINDING_RULES.items():
        assert RENDER_RULES[identifier].code == rule.code


def test_this_packages_rules_reuse_no_other_vocabularys_identifier() -> None:
    own = rules_of(RuleOrigin.RENDER)
    assert len(own) == 10
    assert all(identifier.startswith("render-") for identifier in own)
    taken = set(OFFLINE_RULES) | set(BINDING_RULES) | set(RELEASE_RULES)
    assert own.isdisjoint(taken)


def test_every_code_is_in_the_canonical_vocabulary_the_api_serves() -> None:
    served = {
        api_errors.CONTRACT_INVALID,
        api_errors.VERSION_UNSUPPORTED,
        api_errors.CAPABILITY_UNAVAILABLE,
    }
    assert {CONTRACT_INVALID, VERSION_UNSUPPORTED, CAPABILITY_UNAVAILABLE} == served
    assert {rule.code for rule in RENDER_RULES.values()} == served


def test_capability_unavailable_is_for_what_a_renderer_was_not_built_for() -> None:
    """The one code beyond the offline two: a profile, a value, or a capability."""
    assert [
        key for key, rule in RENDER_RULES.items() if rule.code == CAPABILITY_UNAVAILABLE
    ] == [
        "render-profile-unsupported",
        "render-value-unsupported",
        "render-capability-unsupported",
    ]


def test_each_category_has_one_code() -> None:
    codes: dict[RefusalCategory, set[str]] = {}
    for rule in RENDER_RULES.values():
        codes.setdefault(rule.category, set()).add(rule.code)
    assert all(len(found) == 1 for found in codes.values()), codes


def test_every_category_has_a_rule_and_none_is_for_policy() -> None:
    """A category with no rule would claim a check nothing makes."""
    assert {rule.category for rule in RENDER_RULES.values()} == set(RefusalCategory)
    assert len(RefusalCategory) == 8
    assert not any("policy" in category.value for category in RefusalCategory)


def published_table(heading: str) -> list[list[str]]:
    text = BOUNDARY_DOC.read_text(encoding="utf-8")
    section = text.split(heading, 1)[1]
    lines = section.split("\n\n|", 1)[1]
    table = []
    for line in ("|" + lines).splitlines()[2:]:
        if not line.startswith("|"):
            break
        table.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    return table


def test_the_published_refusal_matrix_is_the_code() -> None:
    published = [
        (*(cell.strip("`") for cell in row[:4]), row[4])
        for row in published_table("## The refusal matrix")
    ]
    assert published == [
        (
            key,
            rule.category.value,
            rule.code,
            rule.origin.value,
            rule.summary[0].upper() + rule.summary[1:],
        )
        for key, rule in RENDER_RULES.items()
    ]


def test_the_matrix_lists_rules_in_category_order() -> None:
    order = list(RefusalCategory)
    positions = [order.index(rule.category) for rule in RENDER_RULES.values()]
    assert positions == sorted(positions)


def test_a_finding_under_an_unpublished_rule_is_a_defect() -> None:
    with pytest.raises(KeyError):
        RenderFinding("render-made-up", "contract", "no such rule")


def test_a_refusal_needs_a_finding() -> None:
    with pytest.raises(ValueError):
        RenderRefused([])


# --------------------------------------------------------------------------
# 2. Every rule refuses something
# --------------------------------------------------------------------------


def _with(name: str, mutate: Callable[[dict[str, Any]], None]) -> WorkloadContract:
    document = contract_document(name)
    mutate(document)
    return parse_workload_contract(document)


def _local_pair_sharing(path_from: str) -> list[EnvironmentBinding]:
    first = binding("local-kind")
    document = load(BINDING_VALID_DIR / "local-kind.yaml")
    if path_from == "identity":
        document["spec"]["gitops"]["destinationPath"] = "gitops/environments/other"
    else:
        document["metadata"]["name"] = "local-other"
    return [first, parse_environment_binding(document)]


#: One input per rule: the contract, and how it is prepared.
REFUSAL_CASES: dict[str, tuple[Callable[[], WorkloadContract], dict[str, Any]]] = {
    "render-contract-version-unsupported": (
        contract,
        {"renderer_support": support(contract_versions=frozenset({LATER_VERSION}))},
    ),
    "render-binding-version-unsupported": (
        contract,
        {"renderer_support": support(binding_versions=frozenset({LATER_VERSION}))},
    ),
    "render-defaults-version-unsupported": (
        contract,
        {
            "renderer_support": support(
                platform_defaults_versions=frozenset({"v1alpha2"})
            )
        },
    ),
    "render-profile-unsupported": (
        contract,
        {"renderer_support": support(profiles=frozenset({Profile.MOCK_LLM}))},
    ),
    "field-required": (
        lambda: _with(
            "synchronous-llm-local", lambda d: d["spec"].pop("synchronousLlm")
        ),
        {},
    ),
    "value-not-permitted": (
        lambda: _with(
            "synchronous-llm-local",
            lambda d: d["spec"]["model"].__setitem__(
                "servingCapability", "inferops-mock-serving"
            ),
        ),
        {},
    ),
    "value-out-of-range": (
        lambda: _with(
            "mock-llm-ci",
            lambda d: d["spec"]["evidence"].__setitem__(
                "proofRefs", ["docs/proof/README.md"]
            ),
        ),
        {},
    ),
    "replica-range-inverted": (lambda: invalid_contract("replica-range-inverted"), {}),
    "secret-value-in-locator": (
        lambda: invalid_contract("secret-value-in-locator"),
        {},
    ),
    "secret-ref-name-duplicated": (
        lambda: invalid_contract("duplicate-secret-ref-name"),
        {},
    ),
    "mock-secret-ref-declared": (lambda: invalid_contract("mock-with-secret-refs"), {}),
    "binding-identity-duplicated": (
        contract,
        {"bindings": _local_pair_sharing("identity"), "binding_name": "local-kind"},
    ),
    "binding-destination-overlaps": (
        contract,
        {"bindings": _local_pair_sharing("destination"), "binding_name": "local-kind"},
    ),
    "runtime-unregistered": (lambda: invalid_contract("runtime-unregistered"), {}),
    "model-artifact-format-unknown": (
        lambda: invalid_contract("model-artifact-format-unrecognised"),
        {},
    ),
    "runtime-model-incompatible": (
        lambda: invalid_contract("runtime-model-incompatible"),
        {},
    ),
    "binding-not-found": (contract, {"bindings": []}),
    "binding-selection-ambiguous": (
        contract,
        {"bindings": [binding("local-kind"), binding("local-docker-desktop")]},
    ),
    "binding-environment-mismatch": (
        contract,
        {"bindings": [binding(), binding_for("ci")], "binding_name": "ci-kind"},
    ),
    "render-ownership-conflict": (
        lambda: carrying(contract(), "spec.platform.apiReplicas", 3),
        {},
    ),
    "render-value-unowned": (
        lambda: carrying(contract(), "spec.scaling.targetReplicas", 3),
        {},
    ),
}


#: The rules only the Helm values renderer applies. No boundary step reaches them,
#: so each has its case in ``test_helm_values_renderer`` instead.
RENDERER_RULES = (
    "render-value-unsupported",
    "render-capability-unsupported",
    "render-value-credential-shaped",
    "render-manual-value-generated",
)


def test_every_rule_has_a_case() -> None:
    assert list(REFUSAL_CASES) == [
        key for key in RENDER_RULES if key not in RENDERER_RULES
    ]


@pytest.mark.parametrize("rule", list(REFUSAL_CASES))
def test_each_rule_refuses_its_case_and_nothing_else(rule: str) -> None:
    build, arguments = REFUSAL_CASES[rule]
    refusal = refused(**arguments)(build())
    assert set(refusal.rule_ids()) == {rule}
    assert refusal.category is RENDER_RULES[rule].category
    assert refusal.code == RENDER_RULES[rule].code
    assert refusal.retryable is False


@pytest.mark.parametrize(
    "rule",
    [
        "binding-not-found",
        "binding-selection-ambiguous",
        "binding-environment-mismatch",
        "render-ownership-conflict",
        "render-value-unowned",
    ],
)
def test_the_validated_path_refuses_the_same_way(rule: str) -> None:
    """``build_render_context`` refuses selection and ownership as the full path does."""
    build, arguments = REFUSAL_CASES[rule]
    workload = build()
    with pytest.raises(RenderRefused) as raised:
        build_render_context(
            validate_for_render(workload),
            defaults(),
            arguments.get("bindings", environment_bindings(workload)),
            binding_name=(
                DnsLabel(arguments["binding_name"])
                if "binding_name" in arguments
                else None
            ),
        )
    assert set(raised.value.rule_ids()) == {rule}


def test_the_profile_conditions_are_all_refused_as_shape() -> None:
    """Two mock profile breaks, each refused as shape and as nothing else.

    The other profile breaks are refused under the same three structural rules, and
    the rule-by-rule cases above hold each rule to the shape category.
    """
    for workload in (
        _with("mock-llm-ci", lambda d: d["spec"].__setitem__("environment", "dev")),
        _with("mock-llm-ci", lambda d: d["spec"].pop("mockLlm")),
    ):
        refusal = refused(bindings=environment_bindings(workload))(workload)
        assert {f.category for f in refusal.findings} == {RefusalCategory.SHAPE_INVALID}


# --------------------------------------------------------------------------
# 3. Every reason at once, in one order
# --------------------------------------------------------------------------


def everything_wrong() -> RenderRefused:
    """A renderer for mocks only, given an inverted contract and no binding."""
    return refused(
        bindings=[],
        renderer_support=support(
            contract_versions=frozenset({LATER_VERSION}),
            profiles=frozenset({Profile.MOCK_LLM}),
        ),
    )(invalid_contract("replica-range-inverted"))


def test_every_step_is_reported_at_once() -> None:
    assert everything_wrong().rule_ids() == (
        "render-contract-version-unsupported",
        "render-profile-unsupported",
        "replica-range-inverted",
        "binding-not-found",
    )


def test_the_refusal_takes_the_first_findings_code_and_category() -> None:
    refusal = everything_wrong()
    assert refusal.code == VERSION_UNSUPPORTED
    assert refusal.category is RefusalCategory.VERSION_UNSUPPORTED
    assert refusal.as_dict()["code"] == VERSION_UNSUPPORTED


def test_the_order_does_not_depend_on_the_order_findings_arrive() -> None:
    findings = everything_wrong().findings
    assert RenderRefused(reversed(findings)).findings == findings


def test_list_indices_sort_as_numbers() -> None:
    later = RenderFinding("render-value-unowned", "contract.spec.items[10]", "x")
    earlier = RenderFinding("render-value-unowned", "contract.spec.items[2]", "x")
    padded = RenderFinding("render-value-unowned", "contract.spec.items[007]", "x")
    assert RenderRefused([later, padded, earlier]).findings == (earlier, padded, later)


def test_within_a_category_the_field_orders_before_the_rule() -> None:
    """Field order and rule order disagree here; the field wins."""
    first = RenderFinding("render-value-unowned", "contract.a", "x")
    second = RenderFinding("render-ownership-conflict", "contract.b", "x")
    assert first.category is second.category
    assert RenderRefused([second, first]).findings == (first, second)


@pytest.mark.parametrize(
    "key",
    ["contract.a1²", "contract.a٣", "contract.a" + "9" * 5000],
)
def test_a_field_key_cannot_turn_a_refusal_into_a_crash(key: str) -> None:
    """A non-ASCII digit, or a digit run past Python's integer-text limit, still sorts.

    The field of an unowned value is a key read from an input, so ordering it must
    not convert it to an integer.
    """
    findings = [
        RenderFinding("render-value-unowned", key, "x"),
        RenderFinding("render-value-unowned", "contract.a2", "x"),
    ]
    refusal = RenderRefused(findings)
    assert {finding.field for finding in refusal.findings} == {key, "contract.a2"}


def test_the_same_inputs_are_refused_identically() -> None:
    assert everything_wrong().as_dict() == everything_wrong().as_dict()


def test_the_structured_form_carries_every_finding_and_the_request() -> None:
    request = RequestContext(request_id="req-1", correlation_id="corr-1")
    refusal = refused(bindings=[], context=request)(contract())
    body: dict[str, Any] = refusal.as_dict()
    assert body["retryable"] is False
    assert body["category"] == "binding-missing"
    [finding] = body["findings"]
    assert finding == {
        "ruleId": "binding-not-found",
        "category": "binding-missing",
        "code": "contract-invalid",
        "field": "contract.spec.environment",
        "reason": refusal.findings[0].reason,
        "requestId": "req-1",
        "correlationId": "corr-1",
    }


def test_every_finding_of_every_step_carries_the_request() -> None:
    """Support, the contract's rules, the binding's version, ownership, and selection."""
    request = RequestContext(request_id="req-2", correlation_id="corr-2")
    refusal = refused(
        bindings=[carrying(binding(), "spec.scaling.x", 1)],
        context=request,
        renderer_support=support(
            profiles=frozenset({Profile.MOCK_LLM}),
            binding_versions=frozenset({LATER_VERSION}),
        ),
    )(invalid_contract("replica-range-inverted"))
    assert refusal.rule_ids() == (
        "render-binding-version-unsupported",
        "render-profile-unsupported",
        "replica-range-inverted",
        "render-value-unowned",
    )
    assert {finding.context for finding in refusal.findings} == {request}
    selection = refused(bindings=[], context=request)(contract())
    assert {finding.context for finding in selection.findings} == {request}


def test_the_validated_path_and_render_with_carry_the_request() -> None:
    request = RequestContext(request_id="req-3", correlation_id="corr-3")
    stray = [carrying(binding(), "spec.scaling.x", 1)]
    with pytest.raises(RenderRefused) as built:
        build_render_context(
            validate_for_render(contract()), defaults(), stray, context=request
        )
    renderer = _RecordingRenderer()
    with pytest.raises(RenderRefused) as rendered:
        render_with(renderer, contract(), defaults(), stray, context=request)
    for refusal in (built.value, rendered.value):
        assert refusal.rule_ids() == ("render-value-unowned",)
        assert {finding.context for finding in refusal.findings} == {request}
    assert renderer.calls == []


def test_contract_findings_are_addressed_by_role() -> None:
    refusal = refused()(invalid_contract("replica-range-inverted"))
    assert [finding.field for finding in refusal.findings] == ["contract.spec.scaling"]


def strings(node: Any) -> set[str]:
    if isinstance(node, dict):
        return set().union(*(strings(value) for value in node.values()))
    if isinstance(node, list):
        return set().union(*(strings(value) for value in node))
    return {node} if isinstance(node, str) else set()


@pytest.mark.parametrize("rule", list(REFUSAL_CASES))
def test_no_reason_repeats_a_value_read_from_an_input(rule: str) -> None:
    """No string of eight characters or more from any input appears in a reason.

    The schema vocabulary the reasons are written in is excluded, as the contract
    document's own check excludes it.
    """
    build, arguments = REFUSAL_CASES[rule]
    workload = build()
    refusal = refused(**arguments)(workload)
    supplied = strings(workload.as_document()) | strings(defaults().as_document())
    for entry in arguments.get("bindings", environment_bindings(workload)):
        supplied |= strings(entry.as_document())
    vocabulary = {profile.value for profile in Profile} | {
        "inferops-native-serving",
        "inferops-mock-serving",
    }
    for finding in refusal.findings:
        for value in supplied - vocabulary:
            if len(value) >= 8:
                assert value not in finding.reason, (rule, value)


# --------------------------------------------------------------------------
# 4. No value has two owners
# --------------------------------------------------------------------------


CROSS = [
    (row, layer)
    for row in RENDER_FIELD_OWNERSHIP
    for layer in Layer
    if layer is not row.layer
]


@pytest.mark.parametrize(
    ("row", "layer"),
    CROSS,
    ids=[f"{row.name}<-{layer.value}" for row, layer in CROSS],
)
def test_a_value_supplied_by_a_layer_that_does_not_own_it_is_refused(
    row: Any, layer: Layer
) -> None:
    """Every value, from each of the two layers that do not own it, by its name."""
    refusal = refusal_of(layer, row.name)
    [finding] = refusal.findings
    assert finding.rule_id == "render-ownership-conflict"
    assert finding.field == f"{ROLE[layer]}.{row.name}"
    assert f"'{row.name}'" in finding.reason
    assert f"which {row.layer.value} owns" in finding.reason


def test_the_conflict_matrix_covers_every_value_from_both_other_layers() -> None:
    assert len(CROSS) == 2 * len(RENDER_FIELD_OWNERSHIP) == 96


SHARED_PATHS = {"metadata.name", "metadata.owner", "spec.environment"}


@pytest.mark.parametrize(
    ("row", "layer"),
    [
        (row, layer)
        for row, layer in CROSS
        if {row.layer, layer} == {Layer.WORKLOAD_INTENT, Layer.ENVIRONMENT_BINDING}
    ],
    ids=lambda value: getattr(value, "name", getattr(value, "value", "")),
)
def test_a_value_supplied_at_its_owners_path_is_refused_unless_the_path_is_shared(
    row: Any, layer: Layer
) -> None:
    """The contract and the binding share three paths, which mean their own things.

    A binding's ``metadata.name`` is its own name, its ``metadata.owner`` its own
    owner, and its ``spec.environment`` the selection key: a binding carrying them
    is a binding, not a claim on the workload's values. Every other owner path is a
    conflict.
    """
    if row.source in SHARED_PATHS:
        prepared = prepare(contract(), **supplier(layer, row.source, row.source))
        assert isinstance(prepared, RenderContext)
        return
    [finding] = refusal_of(layer, row.source).findings
    assert finding.rule_id == "render-ownership-conflict", row.name
    assert finding.field == f"{ROLE[layer]}.{row.source}"


def test_exactly_three_owner_paths_are_shared() -> None:
    contract_paths = {
        row.source
        for row in RENDER_FIELD_OWNERSHIP
        if row.layer is Layer.WORKLOAD_INTENT
    }
    binding_known = {
        row.source
        for row in RENDER_FIELD_OWNERSHIP
        if row.layer is Layer.ENVIRONMENT_BINDING
    } | set(EXCLUDED_SOURCE_FIELDS[Layer.ENVIRONMENT_BINDING])
    assert contract_paths & binding_known == SHARED_PATHS


def test_neither_value_is_chosen_when_two_layers_claim_one() -> None:
    """The binding says five serving replicas, the contract one: nothing is built."""
    claim = carrying(binding(), "spec.scaling.minimumReplicas", 5)
    with pytest.raises(RenderRefused) as raised:
        prepare(contract(), bindings=[claim])
    assert raised.value.rule_ids() == ("render-ownership-conflict",)
    assert "serving.replicas.minimum" in raised.value.findings[0].reason


@pytest.mark.parametrize(
    ("layer", "path"),
    [
        (Layer.ENVIRONMENT_BINDING, "spec.platform.minimumReplicas"),
        (Layer.ENVIRONMENT_BINDING, "api.replicas.extra"),
        (Layer.PLATFORM_DEFAULTS, "api.streaming"),
        (Layer.WORKLOAD_INTENT, "spec.gitops"),
    ],
)
def test_a_value_nobody_owns_is_refused_rather_than_dropped(
    layer: Layer, path: str
) -> None:
    [finding] = refusal_of(layer, path).findings
    assert finding.rule_id == "render-value-unowned"
    assert finding.field == f"{ROLE[layer]}.{path}"


def test_a_layers_own_value_at_a_path_it_is_not_read_from_is_unowned() -> None:
    """A binding writing ``api.replicas`` at the top level would not be read."""
    [finding] = refusal_of(Layer.ENVIRONMENT_BINDING, "api.replicas").findings
    assert finding.rule_id == "render-value-unowned"


def test_an_empty_object_is_a_value() -> None:
    [finding] = refusal_of(Layer.ENVIRONMENT_BINDING, "spec.extra", {}).findings
    assert finding.rule_id == "render-value-unowned"
    assert finding.field == "bindings[0].spec.extra"


def test_every_conflict_from_every_input_is_reported() -> None:
    workload = carrying(contract(), "spec.platform.apiReplicas", 2)
    with pytest.raises(RenderRefused) as raised:
        prepare(
            workload,
            bindings=[carrying(binding(), "spec.scaling.maximumReplicas", 2)],
            platform_defaults=carrying(defaults(), "api.replicas", 2),
        )
    assert [finding.field for finding in raised.value.findings] == [
        "bindings[0].spec.scaling.maximumReplicas",
        "contract.spec.platform.apiReplicas",
        "platformDefaults.api.replicas",
    ]


def test_the_binding_is_addressed_by_its_position_among_those_supplied() -> None:
    claim = carrying(binding_for("local", "local-other"), "spec.scaling", {"x": 1})
    with pytest.raises(RenderRefused) as raised:
        prepare(
            contract(),
            bindings=[binding(), claim],
            binding_name="local-other",
        )
    assert raised.value.findings[0].field == "bindings[1].spec.scaling.x"


def test_annotations_are_left_out_whole() -> None:
    """The contract's extension point is never a claim, whatever its keys say."""
    document = contract_document()
    document["metadata"]["annotations"] = {"example.com/api.replicas": "9"}
    assert isinstance(prepare(parse_workload_contract(document)), RenderContext)


def test_no_path_names_two_values() -> None:
    claimable = conflicts_module._CLAIMABLE
    assert set(claimable) == {row.name for row in RENDER_FIELD_OWNERSHIP} | {
        row.source for row in RENDER_FIELD_OWNERSHIP
    }
    assert all(claimable[row.name] is row for row in RENDER_FIELD_OWNERSHIP)


def every_valid_input() -> list[tuple[WorkloadContract, EnvironmentBinding]]:
    found: list[tuple[WorkloadContract, EnvironmentBinding]] = []
    for path in sorted(WORKLOAD_VALID_DIR.glob("*.yaml")):
        workload = parse_workload_contract(load(path))
        if workload.spec.environment.value == "local":
            found.extend(
                (workload, parse_environment_binding(load(entry)))
                for entry in sorted(BINDING_VALID_DIR.glob("*.yaml"))
            )
        else:
            found.append((workload, binding_for(workload.spec.environment.value)))
    return found


def test_no_committed_valid_input_reaches_the_ownership_check() -> None:
    """Every pairing of a valid contract and a binding serving it: no finding."""
    pairs = every_valid_input()
    assert len(pairs) == 6
    for workload, entry in pairs:
        owners = {
            Layer.WORKLOAD_INTENT: workload.as_document(),
            Layer.PLATFORM_DEFAULTS: defaults().as_document(),
            Layer.ENVIRONMENT_BINDING: entry.as_document(),
        }
        assert ownership_findings(owners, ROLE) == []


def test_a_parsed_binding_cannot_carry_workload_intent() -> None:
    """Why nothing parsed reaches the check: the parser refuses the field first."""
    with pytest.raises(MalformedEnvironmentBindingError):
        parse_environment_binding(
            load(BINDING_INVALID_DIR / "workload-intent-in-binding.yaml")
        )


# --------------------------------------------------------------------------
# 5. Unsupported versions and profiles are the renderer's to declare
# --------------------------------------------------------------------------


@pytest.mark.parametrize(
    "change",
    [
        {"contract_versions": frozenset()},
        {"binding_versions": frozenset()},
        {"platform_defaults_versions": frozenset()},
        {"profiles": frozenset()},
        {"contract_versions": {CONTRACT_VERSION}},
        {"binding_versions": (BINDING_VERSION,)},
        {"platform_defaults_versions": frozenset({""})},
        {"contract_versions": frozenset({1})},
        {"profiles": frozenset({"synchronous-llm"})},
        {"profiles": [Profile.MOCK_LLM]},
    ],
)
def test_a_declaration_that_cannot_be_meant_is_refused(change: dict[str, Any]) -> None:
    with pytest.raises(InvalidValueError):
        support(**change)


def test_a_declaration_may_name_a_version_the_domain_does_not_implement() -> None:
    later = support(contract_versions=frozenset({LATER_VERSION}))
    assert later.contract_versions == frozenset({LATER_VERSION})


@pytest.mark.parametrize("name", ["synchronous-llm-local", "mock-llm-ci"])
def test_a_renderer_for_the_other_profile_refuses_this_one(name: str) -> None:
    workload = contract(name)
    other = frozenset(Profile) - {workload.spec.profile}
    refusal = refused(renderer_support=support(profiles=other))(workload)
    assert refusal.rule_ids() == ("render-profile-unsupported",)
    assert refusal.findings[0].field == "contract.spec.profile"


def test_the_binding_version_is_checked_on_the_selected_binding_only() -> None:
    refusal = refused(
        bindings=[binding("local-kind"), binding("local-docker-desktop")],
        binding_name="local-docker-desktop",
        renderer_support=support(binding_versions=frozenset({LATER_VERSION})),
    )(contract())
    assert [finding.field for finding in refusal.findings] == ["bindings[1].apiVersion"]


@pytest.mark.parametrize(("workload", "entry"), every_valid_input())
def test_a_full_support_renderer_gets_the_context_the_boundary_builds(
    workload: WorkloadContract, entry: EnvironmentBinding
) -> None:
    prepared = prepare(workload, bindings=[entry])
    built = build_render_context(validate_for_render(workload), defaults(), [entry])
    assert prepared == built
    assert prepared.digest() == built.digest()


@pytest.mark.parametrize(
    ("argument", "value"),
    [
        ("contract", {"apiVersion": CONTRACT_VERSION}),
        ("platform_defaults", {"version": DEFAULTS_VERSION}),
        ("support", {"profiles": ["synchronous-llm"]}),
        ("bindings", [{"kind": "EnvironmentBinding"}]),
    ],
)
def test_raw_input_cannot_take_the_canonical_path(argument: str, value: Any) -> None:
    arguments: dict[str, Any] = {
        "contract": contract(),
        "platform_defaults": defaults(),
        "bindings": [binding()],
        "support": support(),
    }
    arguments[argument] = value
    with pytest.raises(TypeError):
        prepare_render(
            arguments["contract"],
            arguments["platform_defaults"],
            arguments["bindings"],
            support=arguments["support"],
        )


def test_the_canonical_path_takes_a_parsed_contract_not_a_validated_one() -> None:
    with pytest.raises(TypeError):
        prepare_render(
            validate_for_render(contract()),  # type: ignore[arg-type]
            defaults(),
            [binding()],
            support=support(),
        )


# --------------------------------------------------------------------------
# 6. Nothing is half-done
# --------------------------------------------------------------------------


class _RecordingRenderer:
    """A renderer of the interface's shape that records each context it is given."""

    revision = GitRevision(RENDERER_REVISION)

    def __init__(self, renderer_support: RendererSupport | None = None) -> None:
        self.support = support() if renderer_support is None else renderer_support
        self.calls: list[RenderContext] = []

    def render(self, context: RenderContext) -> str:
        self.calls.append(context)
        return str(context.digest())


def test_a_renderer_is_called_once_with_the_prepared_context() -> None:
    renderer = _RecordingRenderer()
    assert isinstance(renderer, Renderer)
    output = render_with(renderer, contract(), defaults(), [binding()])
    assert renderer.calls == [prepare(contract())]
    assert output == str(prepare(contract()).digest())


@pytest.mark.parametrize("rule", list(REFUSAL_CASES))
def test_a_refused_render_never_calls_the_renderer(rule: str) -> None:
    build, arguments = REFUSAL_CASES[rule]
    workload = build()
    renderer = _RecordingRenderer(arguments.get("renderer_support"))
    name = arguments.get("binding_name")
    with pytest.raises(RenderRefused) as raised:
        render_with(
            renderer,
            workload,
            defaults(),
            arguments.get("bindings", environment_bindings(workload)),
            binding_name=None if name is None else DnsLabel(name),
        )
    assert renderer.calls == []
    assert rule in raised.value.rule_ids()
    assert "fields" not in raised.value.as_dict()


def test_render_with_refuses_what_is_not_a_renderer() -> None:
    class _NoSupport:
        revision = GitRevision(RENDERER_REVISION)

        def render(self, context: RenderContext) -> str:
            return ""

    with pytest.raises(TypeError):
        render_with(_NoSupport(), contract(), defaults(), [binding()])  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# The field-ownership matrix for the reference workload
# --------------------------------------------------------------------------


def reference_context() -> RenderContext:
    """The reference workload: the synchronous fixture on the V1 reference binding."""
    return prepare(
        contract("synchronous-llm-local"), bindings=[binding("local-docker-desktop")]
    )


COLUMNS = (Layer.WORKLOAD_INTENT, Layer.PLATFORM_DEFAULTS, Layer.ENVIRONMENT_BINDING)


def matrix_row(row: Any, context: RenderContext) -> list[str]:
    cells = [f"`{row.name}`"]
    for layer in COLUMNS:
        cells.append(f"**owns** `{row.source}`" if layer is row.layer else "refused")
    if row.name in context.names():
        value = context.entry(row.name).as_document()["value"]
        cells.append(f"`{json.dumps(value, separators=(',', ':'))}`")
    else:
        cells.append("absent")
    return cells


def test_the_published_reference_matrix_is_the_reference_context() -> None:
    context = reference_context()
    expected = [matrix_row(row, context) for row in RENDER_FIELD_OWNERSHIP]
    assert (
        published_table("## Field-ownership matrix for the reference workload")
        == expected
    )


def test_the_reference_matrix_has_every_value_and_its_absences_are_optional() -> None:
    context = reference_context()
    rows = published_table("## Field-ownership matrix for the reference workload")
    assert len(rows) == len(RENDER_FIELD_OWNERSHIP) == 48
    absent = [row for row in RENDER_FIELD_OWNERSHIP if row.name not in context.names()]
    assert all(not row.required for row in absent)
    assert len(absent) == 7
    assert len(context.names()) == 41


def test_the_reference_matrix_names_the_reference_inputs() -> None:
    context = reference_context()
    assert str(context.sources.environment_binding.name) == "local-docker-desktop"
    assert context.value("workload.id") == "support-assistant"
