"""The provenance input-trust boundary: what a release may be recorded from.

Every check reads files from this repository and nothing else. No network, no
cluster, no clock, no randomness.

Six things are asserted:

1. **Every field is classified.** Every leaf of the release schema has exactly one
   row in the policy, in the schema's order, and every one is a public-safe
   identity or a derived digest - none is excluded content. Every value of the
   render context has exactly one classification, and only the workload's name
   and version are public. A copy of the schema or the ownership table with one
   field added is caught as unclassified.
2. **The supported path reads what its rows name, and nothing else.** Each field of
   a recorded release is the value of the source its row names, for every
   committed contract; the release passes both release checks and parses back to
   itself; a raw document, a dictionary, or a bare string is refused at every
   argument; and the function's body reaches the context only through the
   allowlisted reader and the sources.
3. **Excluded content has no way in.** A context whose every excluded value is a
   distinct marker records a release holding none of them, and so do real inputs
   carrying markers in their free text, secret references, owners, and
   environment facts. Opening a path in either policy table is refused at run
   time, and a deliberately opened one is seen by the same marker check, so the
   check is not decorative.
4. **Recording reads no environment variable and admits no payload.** The module
   imports nothing that could read one, recording succeeds with the environment
   made unreadable, and the signature takes typed references and a context only.
5. **Known credential shapes stay refused**, on this path, in every field that can
   hold one - the binding name the Sprint 1 review reached included - without
   quoting the value. A version the release cannot hold is refused too.
6. **The limit is measured and published.** A lowercase token with no published
   prefix, written as a workload name, is recorded: syntax cannot tell it from a
   name. The release document publishes both policy tables, compared with the
   code, and the completed record it corrects keeps its original wording.
"""

from __future__ import annotations

import ast
import copy
import json
import os
import re
import typing
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml

from inferops.domain import RequestContext
from inferops.domain.environment import EnvironmentBinding, parse_environment_binding
from inferops.domain.release import (
    GitRevision,
    HelmValuesReference,
    MalformedReleaseError,
    ReleaseRefusal,
    RenderedWorkloadRelease,
    RendererReference,
    Sha256Hex,
    ValuesFileName,
    canonical_release,
    check_rendered_workload_release,
    derive_release_id,
    parse_rendered_workload_release,
    verify_release_sources,
)
from inferops.domain.render import (
    CONTEXT_FIELD_TRUST,
    RECORDED_RELEASE_VERSION,
    RELEASE_PROVENANCE,
    RENDER_FIELD_OWNERSHIP,
    ApiDefaults,
    PlatformDefaults,
    ProvenanceOrigin,
    ProvenanceTrust,
    ReleaseNotRecordedError,
    RenderContext,
    RendererSupport,
    RenderField,
    build_render_context,
    prepare_render,
    provenance_field,
    record_release,
    validate_for_render,
)
from inferops.domain.render import normalization as normalization_module
from inferops.domain.render import recording as recording_module
from inferops.domain.workload import (
    CompatibilityMatrixLoader,
    DnsLabel,
    Profile,
    WorkloadContract,
    parse_workload_contract,
    set_matrix_loader,
)

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
RECORDING_PATH = REPO_ROOT / "src" / "inferops" / "domain" / "render" / "recording.py"
RELEASE_SCHEMA_PATH = (
    REPO_ROOT
    / "contracts"
    / "release"
    / "rendered-workload-release.v1alpha1.schema.json"
)
WORKLOAD_SCHEMA_PATH = (
    REPO_ROOT / "contracts" / "workload" / "workload-contract.v1alpha1.schema.json"
)
BINDING_SCHEMA_PATH = (
    REPO_ROOT / "contracts" / "environment" / "environment-binding.v1alpha1.schema.json"
)
MATRIX_PATH = (
    REPO_ROOT
    / "contracts"
    / "workload"
    / "compatibility"
    / "runtime-model-compatibility.v1alpha1.json"
)
WORKLOAD_VALID_DIR = REPO_ROOT / "contracts" / "workload" / "examples" / "valid"
BINDING_VALID_DIR = REPO_ROOT / "contracts" / "environment" / "examples" / "valid"
CHART_VALUES = REPO_ROOT / "charts" / "inferops-llm" / "values.yaml"
RELEASE_DOC = REPO_ROOT / "docs" / "contracts" / "rendered-workload-release.md"
COMPLETED_RECORD = (
    REPO_ROOT / "docs" / "proof" / "contracts" / "v2-s1-002-pr2-validation.md"
)

RENDERER = RendererReference(GitRevision("a" * 40))
HELM_VALUES = HelmValuesReference(
    ValuesFileName("values.generated.yaml"), Sha256Hex("5" * 64)
)

#: Credential shapes the schema cannot refuse, shortened: a published prefix and
#: four zeros, which is all the rule looks at. None is a credential.
LOWERCASE_SHAPES = ["sk-0000", "glpat-0000", "gldt-0000", "xoxb-0000"]

#: A lowercase token with no published prefix. Synthetic; the same value the
#: release domain's suite measures. Nothing about its syntax marks it a secret.
UNPREFIXED = "q7x2k9m4v8c1z6b3n5w0"

HEXADECIMAL = re.compile(r"[0-9a-f]{40}|[0-9a-f]{64}")

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


def binding_document(name: str = "local-kind") -> dict[str, Any]:
    return load(BINDING_VALID_DIR / f"{name}.yaml")


def binding_serving(
    environment: str, document: dict[str, Any] | None = None
) -> dict[str, Any]:
    """The local-kind binding, moved to serve another environment."""
    moved = binding_document() if document is None else document
    moved["metadata"]["name"] = f"{environment}-kind"
    moved["spec"]["environment"] = environment
    moved["spec"]["gitops"]["destinationPath"] = (
        f"gitops/environments/{environment}-kind"
    )
    return moved


def platform_defaults() -> PlatformDefaults:
    api = load(CHART_VALUES)["api"]
    return PlatformDefaults(
        "v1alpha1",
        GitRevision("b" * 40),
        ApiDefaults(
            api["requestTimeoutMs"], api["drainTimeoutMs"], api["maxOutputTokens"]
        ),
    )


def context_for(
    workload: WorkloadContract, binding: EnvironmentBinding
) -> RenderContext:
    return build_render_context(
        validate_for_render(workload), platform_defaults(), [binding]
    )


def inputs(name: str) -> tuple[WorkloadContract, EnvironmentBinding]:
    """Each committed contract with a binding serving its environment."""
    workload = parse_workload_contract(contract_document(name))
    environment = workload.spec.environment.value
    document = (
        binding_document() if environment == "local" else binding_serving(environment)
    )
    return workload, parse_environment_binding(document)


CONTRACT_NAMES = sorted(path.stem for path in WORKLOAD_VALID_DIR.glob("*.yaml"))


def recorded(name: str = "synchronous-llm-local") -> RenderedWorkloadRelease:
    return record_release(
        context_for(*inputs(name)), renderer=RENDERER, helm_values=HELM_VALUES
    )


def schema_leaves(schema: dict[str, Any]) -> Iterator[str]:
    """Every leaf path of an object schema, resolving local references."""

    def walk(node: dict[str, Any], prefix: str) -> Iterator[str]:
        if "$ref" in node:
            node = schema["$defs"][node["$ref"].rsplit("/", 1)[-1]]
        if node.get("type") == "object" and "properties" in node:
            for key, member in node["properties"].items():
                yield from walk(member, f"{prefix}.{key}" if prefix else key)
        else:
            yield prefix

    yield from walk(schema, "")


def document_leaves(node: Any, prefix: str = "") -> Iterator[str]:
    if isinstance(node, dict):
        for key, value in node.items():
            yield from document_leaves(value, f"{prefix}.{key}" if prefix else key)
    else:
        yield prefix


def get_path(document: dict[str, Any], path: str) -> Any:
    node: Any = document
    for key in path.split("."):
        node = node[key]
    return node


def classification_gaps(
    release_schema: dict[str, Any], context_names: list[str]
) -> list[str]:
    """Every release field and render value the policy does not classify, by name."""
    rows = [row.field for row in RELEASE_PROVENANCE]
    gaps = [
        f"release:{leaf}" for leaf in schema_leaves(release_schema) if leaf not in rows
    ]
    gaps += [
        f"context:{name}" for name in context_names if name not in CONTEXT_FIELD_TRUST
    ]
    return gaps


def ownership_names() -> list[str]:
    return [row.name for row in RENDER_FIELD_OWNERSHIP]


# --------------------------------------------------------------------------
# 1. Every field is classified
# --------------------------------------------------------------------------


def test_every_release_field_is_classified_in_the_schemas_order():
    schema = load(RELEASE_SCHEMA_PATH)
    assert [row.field for row in RELEASE_PROVENANCE] == list(schema_leaves(schema))


def test_every_attribute_of_a_recorded_release_is_classified():
    """The typed release's own fields, not only the schema's, are the policy's."""
    leaves = list(document_leaves(recorded().as_document()))
    assert leaves == [row.field for row in RELEASE_PROVENANCE]


def test_no_release_field_is_excluded_content():
    assert {row.trust for row in RELEASE_PROVENANCE} == {
        ProvenanceTrust.PUBLIC_IDENTITY,
        ProvenanceTrust.DERIVED_DIGEST,
    }


def test_the_trust_vocabulary_is_closed_at_three():
    assert [entry.value for entry in ProvenanceTrust] == [
        "public-identity",
        "derived-digest",
        "excluded",
    ]


def test_every_render_value_is_classified_exactly_once():
    names = ownership_names()
    assert len(names) == len(set(names))
    assert sorted(CONTEXT_FIELD_TRUST) == sorted(names)


def test_only_the_workload_identity_is_a_public_render_value():
    public = {
        name
        for name, entry in CONTEXT_FIELD_TRUST.items()
        if entry.trust is ProvenanceTrust.PUBLIC_IDENTITY
    }
    assert public == {"workload.id", "workload.version"}
    assert {entry.trust for entry in CONTEXT_FIELD_TRUST.values()} == {
        ProvenanceTrust.PUBLIC_IDENTITY,
        ProvenanceTrust.EXCLUDED,
    }
    assert all(entry.reason for entry in CONTEXT_FIELD_TRUST.values())


def test_the_secret_references_are_classified_sensitive():
    entry = CONTEXT_FIELD_TRUST["security.secretRefs"]
    assert entry.trust is ProvenanceTrust.EXCLUDED
    assert entry.reason.startswith("sensitive:")
    sensitive = [
        name
        for name, value in CONTEXT_FIELD_TRUST.items()
        if value.reason.startswith("sensitive:")
    ]
    assert sensitive == ["security.secretRefs"]


def test_every_value_row_reads_a_public_render_value():
    for row in RELEASE_PROVENANCE:
        if row.origin is ProvenanceOrigin.CONTEXT_VALUE:
            assert row.trust is ProvenanceTrust.PUBLIC_IDENTITY, row.field
            assert (
                CONTEXT_FIELD_TRUST[row.source].trust is ProvenanceTrust.PUBLIC_IDENTITY
            ), row.field


def test_every_derived_field_holds_hexadecimal_only():
    document = recorded().as_document()
    for row in RELEASE_PROVENANCE:
        if row.trust is ProvenanceTrust.DERIVED_DIGEST:
            assert HEXADECIMAL.fullmatch(get_path(document, row.field)), row.field


def test_the_policy_as_committed_has_no_gap():
    assert classification_gaps(load(RELEASE_SCHEMA_PATH), ownership_names()) == []


def test_an_added_release_field_is_caught_as_unclassified():
    """Mutation: a schema copy with one more member under ``metadata``."""
    schema = copy.deepcopy(load(RELEASE_SCHEMA_PATH))
    metadata = schema["properties"]["metadata"]
    if "$ref" in metadata:
        metadata = schema["$defs"][metadata["$ref"].rsplit("/", 1)[-1]]
    metadata["properties"]["note"] = {"type": "string"}
    assert classification_gaps(schema, ownership_names()) == ["release:metadata.note"]


def test_an_added_render_value_is_caught_as_unclassified():
    """Mutation: an ownership table with one more context value."""
    names = [*ownership_names(), "workload.notes"]
    assert classification_gaps(load(RELEASE_SCHEMA_PATH), names) == [
        "context:workload.notes"
    ]


def test_a_release_field_with_no_row_cannot_be_read():
    with pytest.raises(KeyError):
        provenance_field("metadata.note")


# --------------------------------------------------------------------------
# 2. The supported path reads what its rows name, and nothing else
# --------------------------------------------------------------------------


def expected_value(
    row: Any, context: RenderContext, release: RenderedWorkloadRelease
) -> Any:
    """What a row says a field holds, computed from the row and not from the code."""
    if row.origin is ProvenanceOrigin.RELEASE:
        return {
            "apiVersion": RECORDED_RELEASE_VERSION,
            "kind": "RenderedWorkloadRelease",
        }[row.source]
    if row.origin is ProvenanceOrigin.CONTEXT_VALUE:
        return context.value(row.source)
    if row.origin is ProvenanceOrigin.CONTEXT_SOURCE:
        return get_path(
            context.sources.release_source(RENDERER).as_document(), row.source
        )
    if row.origin is ProvenanceOrigin.RENDERER:
        return get_path(RENDERER.as_document(), row.source)
    if row.origin is ProvenanceOrigin.HELM_VALUES:
        return get_path(HELM_VALUES.as_document(), row.source)
    assert row.origin is ProvenanceOrigin.DERIVATION
    return str(
        derive_release_id(
            release.metadata.workload_id,
            release.metadata.workload_version,
            release.source,
        )
    )


@pytest.mark.parametrize("name", CONTRACT_NAMES)
def test_each_field_is_the_value_its_row_names(name: str):
    context = context_for(*inputs(name))
    release = record_release(context, renderer=RENDERER, helm_values=HELM_VALUES)
    document = release.as_document()
    for row in RELEASE_PROVENANCE:
        assert get_path(document, row.field) == expected_value(row, context, release), (
            row.field
        )


@pytest.mark.parametrize("name", CONTRACT_NAMES)
def test_a_recorded_release_passes_both_checks_and_reads_back_as_itself(name: str):
    workload, binding = inputs(name)
    release = record_release(
        context_for(workload, binding), renderer=RENDERER, helm_values=HELM_VALUES
    )
    assert check_rendered_workload_release(release) == []
    assert verify_release_sources(release, workload, binding) == []
    assert parse_rendered_workload_release(release.as_document()) == release


def test_recording_the_same_inputs_twice_gives_one_release():
    first, second = recorded(), recorded()
    assert first == second
    assert canonical_release(first) == canonical_release(second)


@pytest.mark.parametrize(
    "argument",
    ["render_context", "renderer", "helm_values"],
)
@pytest.mark.parametrize("form", ["document", "string"])
def test_a_raw_argument_cannot_take_the_supported_path(argument: str, form: str):
    context = context_for(*inputs("synchronous-llm-local"))
    raw: dict[str, Any] = {
        "render_context": context.as_document(),
        "renderer": RENDERER.as_document(),
        "helm_values": HELM_VALUES.as_document(),
    }
    arguments: dict[str, Any] = {
        "render_context": context,
        "renderer": RENDERER,
        "helm_values": HELM_VALUES,
    }
    arguments[argument] = (
        raw[argument] if form == "document" else json.dumps(raw[argument])
    )
    with pytest.raises(TypeError):
        record_release(
            arguments["render_context"],
            renderer=arguments["renderer"],
            helm_values=arguments["helm_values"],
        )


#: Bare strings where a constrained type belongs. Typed as `Any` because the
#: point is that the dataclasses accept what their annotations do not.
BARE: Any = str


@pytest.mark.parametrize(
    ("renderer", "helm_values"),
    [
        (RendererReference(BARE("a" * 40)), HELM_VALUES),
        (
            RENDERER,
            HelmValuesReference(BARE("values.generated.yaml"), Sha256Hex("5" * 64)),
        ),
        (
            RENDERER,
            HelmValuesReference(
                BARE("Free text, not a file name"), Sha256Hex("5" * 64)
            ),
        ),
        (
            RENDERER,
            HelmValuesReference(
                ValuesFileName("values.generated.yaml"), BARE("5" * 64)
            ),
        ),
    ],
    ids=["bare-revision", "bare-path", "free-text-path", "bare-digest"],
)
def test_a_reference_built_around_bare_strings_is_refused(
    renderer: RendererReference, helm_values: HelmValuesReference
):
    """The references are dataclasses and check nothing; their members must.

    Without this, free text passed as a values path would reach the release as
    long as no part of it began with a published credential prefix.
    """
    with pytest.raises(TypeError):
        record_release(
            context_for(*inputs("synchronous-llm-local")),
            renderer=renderer,
            helm_values=helm_values,
        )


@pytest.mark.parametrize("name", ["contract", "validated"])
def test_a_contract_is_not_a_render_context(name: str):
    workload, _ = inputs("synchronous-llm-local")
    value = workload if name == "contract" else validate_for_render(workload)
    with pytest.raises(TypeError):
        record_release(value, renderer=RENDERER, helm_values=HELM_VALUES)  # type: ignore[arg-type]


def record_release_body() -> ast.FunctionDef:
    tree = ast.parse(RECORDING_PATH.read_text(encoding="utf-8"))
    return next(
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == "record_release"
    )


def test_the_function_reaches_the_context_only_through_the_allowlist():
    """A tripwire on the body: one attribute, and one reader, and nothing else.

    ``render_context.sources`` is the typed identity of every input; every other
    read goes through ``_public_context_value``, which consults both policy
    tables. A change that read ``render_context.value``, ``.entry``, ``.fields``,
    ``.owned_by``, or ``.as_document`` here would fail this test.
    """
    body = record_release_body()
    attributes = {
        node.attr
        for node in ast.walk(body)
        if isinstance(node, ast.Attribute)
        and isinstance(node.value, ast.Name)
        and node.value.id == "render_context"
    }
    assert attributes == {"sources"}
    callers = {
        node.func.id
        for node in ast.walk(body)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and any(
            isinstance(arg, ast.Name) and arg.id == "render_context"
            for arg in node.args
        )
    }
    assert callers == {"isinstance", "_public_context_value"}


# --------------------------------------------------------------------------
# 3. Excluded content has no way in
# --------------------------------------------------------------------------


def marker(index: int) -> str:
    """A distinct, DNS-safe marker: one a copied value could be recorded as."""
    return f"zqmark{index:02d}"


def marked_context(context: RenderContext) -> tuple[RenderContext, list[str]]:
    """The same context with every excluded value replaced by its own marker.

    Built with the module's private sentinel, which the render suite already
    records as a guard against accidents rather than intent.
    """
    fields: list[RenderField] = []
    markers: list[str] = []
    for index, entry in enumerate(context.fields):
        if CONTEXT_FIELD_TRUST[entry.name].trust is ProvenanceTrust.EXCLUDED:
            markers.append(marker(index))
            entry = RenderField(entry.name, entry.layer, entry.source, marker(index))
        fields.append(entry)
    return (
        RenderContext(tuple(fields), context.sources, normalization_module._ISSUED),
        markers,
    )


@pytest.mark.parametrize("name", CONTRACT_NAMES)
def test_no_excluded_render_value_reaches_a_release(name: str):
    context, markers = marked_context(context_for(*inputs(name)))
    assert len(markers) == len(context.fields) - 2
    release = record_release(context, renderer=RENDERER, helm_values=HELM_VALUES)
    recorded_bytes = canonical_release(release).decode()
    assert [value for value in markers if value in recorded_bytes] == []


def test_markers_in_real_inputs_reach_no_release():
    """Free text, secret references, owners, and environment facts, as documents."""
    document = contract_document("synchronous-llm-secret-refs")
    document["metadata"]["description"] = "Free text zqmarkdesc for a reader."
    document["metadata"]["annotations"] = {"inferops.io/example": "zqmarkannotation"}
    document["metadata"]["owner"] = "team-zqmarkowner"
    document["spec"]["security"]["secretRefs"][0]["reference"] = (
        "inferops-serving/zqmarksecret#token"
    )
    document["spec"]["attribution"]["tenant"] = "zqmarktenant"
    document["spec"]["attribution"]["costCenter"] = "zqmarkcost"
    binding = binding_serving("dev")
    binding["metadata"]["owner"] = "zqmarkbindingowner"
    binding["spec"]["gitops"]["destinationPath"] = "gitops/zqmarkpath"
    workload = parse_workload_contract(document)
    parsed_binding = parse_environment_binding(binding)
    planted = json.dumps([workload.as_document(), parsed_binding.as_document()])
    markers = sorted(set(re.findall(r"zqmark[a-z]+", planted)))
    assert len(markers) == 8, "every marker reached a parsed input"
    release = record_release(
        context_for(workload, parsed_binding),
        renderer=RENDERER,
        helm_values=HELM_VALUES,
    )
    assert "zqmark" not in canonical_release(release).decode()


def test_a_public_row_pointed_at_an_excluded_value_is_refused(monkeypatch):
    """Mutation: the workload identifier read from the tenant instead."""
    rows = tuple(
        recording_module.ProvenanceField(
            row.field, row.trust, row.origin, "attribution.tenant"
        )
        if row.field == "metadata.workloadId"
        else row
        for row in RELEASE_PROVENANCE
    )
    monkeypatch.setattr(recording_module, "RELEASE_PROVENANCE", rows)
    with pytest.raises(AssertionError, match="not classified a public identity"):
        recorded()


def test_a_public_value_reclassified_excluded_is_refused(monkeypatch):
    """Mutation: the workload's own name classified excluded."""
    table = dict(CONTEXT_FIELD_TRUST)
    table["workload.id"] = recording_module.ContextFieldTrust(
        ProvenanceTrust.EXCLUDED, "reclassified"
    )
    monkeypatch.setattr(recording_module, "CONTEXT_FIELD_TRUST", table)
    with pytest.raises(AssertionError, match="not classified a public identity"):
        recorded()


def test_a_derived_row_cannot_be_read_as_a_value(monkeypatch):
    """Mutation: the workload identifier's row marked derived rather than public."""
    rows = tuple(
        recording_module.ProvenanceField(
            row.field, ProvenanceTrust.DERIVED_DIGEST, row.origin, row.source
        )
        if row.field == "metadata.workloadId"
        else row
        for row in RELEASE_PROVENANCE
    )
    monkeypatch.setattr(recording_module, "RELEASE_PROVENANCE", rows)
    with pytest.raises(AssertionError, match="is not classified a public identity"):
        recorded()


def test_a_deliberately_opened_path_is_seen_by_the_marker_check(monkeypatch):
    """Positive control: the exclusion tests above can fail.

    Open a path - classify the tenant public and read the workload identifier
    from it - and the tenant's marker appears in the recorded release, which is
    exactly what the exclusion tests assert never happens on the real tables.
    """
    table = dict(CONTEXT_FIELD_TRUST)
    table["attribution.tenant"] = recording_module.ContextFieldTrust(
        ProvenanceTrust.PUBLIC_IDENTITY, "opened on purpose"
    )
    rows = tuple(
        recording_module.ProvenanceField(
            row.field, row.trust, row.origin, "attribution.tenant"
        )
        if row.field == "metadata.workloadId"
        else row
        for row in RELEASE_PROVENANCE
    )
    monkeypatch.setattr(recording_module, "CONTEXT_FIELD_TRUST", table)
    monkeypatch.setattr(recording_module, "RELEASE_PROVENANCE", rows)
    document = contract_document()
    document["spec"]["attribution"]["tenant"] = "zqmarktenant"
    release = record_release(
        context_for(
            parse_workload_contract(document),
            parse_environment_binding(binding_document()),
        ),
        renderer=RENDERER,
        helm_values=HELM_VALUES,
    )
    assert "zqmarktenant" in canonical_release(release).decode()


# --------------------------------------------------------------------------
# 4. Recording reads no environment variable and admits no payload
# --------------------------------------------------------------------------


def test_the_recording_module_imports_nothing_that_reads_the_host():
    forbidden_modules = {"os", "sys", "subprocess", "pathlib", "io", "socket"}
    forbidden_names = {
        "environ",
        "getenv",
        "open",
        "input",
        "__import__",
        "eval",
        "exec",
    }
    tree = ast.parse(RECORDING_PATH.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots = {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            roots = {(node.module or "").split(".")[0]}
        else:
            roots = set()
        assert roots.isdisjoint(forbidden_modules), roots
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    attributes = {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    assert (names | attributes).isdisjoint(forbidden_names)


class _UnreadableEnvironment:
    """Stands in for ``os.environ``: any read fails the test."""

    def __getattr__(self, name: str) -> Any:
        raise AssertionError("recording read the process environment")

    def __getitem__(self, key: str) -> Any:
        raise AssertionError("recording read the process environment")

    def __contains__(self, key: object) -> bool:
        raise AssertionError("recording read the process environment")

    def __iter__(self) -> Any:
        raise AssertionError("recording read the process environment")


def test_recording_succeeds_with_the_environment_unreadable(monkeypatch):
    context = context_for(*inputs("synchronous-llm-local"))
    expected = record_release(context, renderer=RENDERER, helm_values=HELM_VALUES)
    monkeypatch.setenv("INFEROPS_WORKLOAD_ID", "zqmarkenv")

    def unreadable(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError("recording read the process environment")

    # Restored in `finally`, not after the call: pytest itself writes to the
    # environment between phases, so a failure that left it unreadable would
    # surface as hundreds of errors in unrelated tests instead of this one.
    monkeypatch.setattr(os, "environ", _UnreadableEnvironment())
    monkeypatch.setattr(os, "getenv", unreadable)
    try:
        release = record_release(context, renderer=RENDERER, helm_values=HELM_VALUES)
    finally:
        monkeypatch.undo()
    assert release == expected
    assert "zqmarkenv" not in canonical_release(release).decode()


def test_the_signature_takes_a_context_and_typed_references_only():
    """No parameter could carry a prompt, a response, free text, or a document."""
    hints = typing.get_type_hints(record_release)
    assert hints == {
        "render_context": RenderContext,
        "renderer": RendererReference,
        "helm_values": HelmValuesReference,
        "context": RequestContext,
        "return": RenderedWorkloadRelease,
    }


PAYLOAD_WORDS = ("prompt", "response", "completion", "message", "body", "payload")


def test_no_input_document_has_a_prompt_or_response_field_to_read():
    """A tripwire: such a field would have to be classified, and only excluded."""
    for path in (WORKLOAD_SCHEMA_PATH, BINDING_SCHEMA_PATH, RELEASE_SCHEMA_PATH):
        text = json.dumps(load(path)).lower()
        properties = set(re.findall(r'"([a-z0-9]+)": \{', text))
        assert [p for p in properties if p.startswith(PAYLOAD_WORDS)] == [], path.name
    assert [
        n for n in CONTEXT_FIELD_TRUST if any(w in n.lower() for w in PAYLOAD_WORDS)
    ] == []


# --------------------------------------------------------------------------
# 5. Known credential shapes stay refused on this path
# --------------------------------------------------------------------------


def refusal(error: ReleaseNotRecordedError) -> list[tuple[str, str]]:
    return [
        (
            entry.rule_id
            if isinstance(entry, ReleaseRefusal)
            else type(entry).__name__,
            entry.field,
        )
        for entry in error.refusals
    ]


@pytest.mark.parametrize("shape", LOWERCASE_SHAPES, ids=lambda s: s.split("-")[0])
@pytest.mark.parametrize("template", ["{}", "local-{}"])
def test_a_credential_shaped_binding_name_is_refused_when_recorded(
    template: str, shape: str
):
    """The Sprint 1 review's case: the render boundary takes it, provenance does not."""
    document = binding_document()
    document["metadata"]["name"] = template.format(shape)
    document["spec"]["gitops"]["destinationPath"] = f"gitops/{template.format(shape)}"
    context = context_for(
        parse_workload_contract(contract_document()),
        parse_environment_binding(document),
    )
    with pytest.raises(ReleaseNotRecordedError) as caught:
        record_release(context, renderer=RENDERER, helm_values=HELM_VALUES)
    assert refusal(caught.value) == [
        ("release-value-credential-shaped", "release.source.environmentBinding.name")
    ]
    assert template.format(shape) not in json.dumps(caught.value.as_dict())
    assert template.format(shape) not in str(caught.value)


@pytest.mark.parametrize("shape", LOWERCASE_SHAPES, ids=lambda s: s.split("-")[0])
@pytest.mark.parametrize(
    ("member", "template", "field"),
    [
        ("name", "{}", "release.metadata.workloadId"),
        ("name", "support-{}", "release.metadata.workloadId"),
        ("version", "0.1.0-{}", "release.metadata.workloadVersion"),
        ("version", "0.1.0+{}", "release.metadata.workloadVersion"),
    ],
)
def test_a_credential_shaped_workload_identity_is_refused_when_recorded(
    member: str, template: str, field: str, shape: str
):
    document = contract_document()
    document["metadata"][member] = template.format(shape)
    context = context_for(
        parse_workload_contract(document), parse_environment_binding(binding_document())
    )
    with pytest.raises(ReleaseNotRecordedError) as caught:
        record_release(context, renderer=RENDERER, helm_values=HELM_VALUES)
    assert refusal(caught.value) == [("release-value-credential-shaped", field)]
    assert template.format(shape) not in json.dumps(caught.value.as_dict())


@pytest.mark.parametrize("shape", LOWERCASE_SHAPES, ids=lambda s: s.split("-")[0])
def test_a_credential_shaped_values_file_name_is_refused_when_recorded(shape: str):
    values = HelmValuesReference(ValuesFileName(f"{shape}.yaml"), Sha256Hex("5" * 64))
    with pytest.raises(ReleaseNotRecordedError) as caught:
        record_release(
            context_for(*inputs("synchronous-llm-local")),
            renderer=RENDERER,
            helm_values=values,
        )
    assert refusal(caught.value) == [
        ("release-value-credential-shaped", "release.output.helmValues.path")
    ]


def test_every_refusal_is_reported_at_once_and_carries_the_request_context():
    document = binding_document()
    document["metadata"]["name"] = "sk-0000"
    request = RequestContext(request_id="req-1", correlation_id="corr-1")
    values = HelmValuesReference(ValuesFileName("sk-0000.yaml"), Sha256Hex("5" * 64))
    with pytest.raises(ReleaseNotRecordedError) as caught:
        record_release(
            context_for(
                parse_workload_contract(contract_document()),
                parse_environment_binding(document),
            ),
            renderer=RENDERER,
            helm_values=values,
            context=request,
        )
    assert refusal(caught.value) == [
        ("release-value-credential-shaped", "release.output.helmValues.path"),
        ("release-value-credential-shaped", "release.source.environmentBinding.name"),
    ]
    assert all(entry.context == request for entry in caught.value.refusals)
    assert caught.value.code == "contract-invalid"
    assert caught.value.retryable is False


def test_a_version_the_release_cannot_hold_is_refused_without_its_value():
    """An uppercase pre-release is a valid contract version and no release version."""
    document = contract_document()
    document["metadata"]["version"] = "1.0.0-RC.1"
    context = context_for(
        parse_workload_contract(document), parse_environment_binding(binding_document())
    )
    with pytest.raises(ReleaseNotRecordedError) as caught:
        record_release(context, renderer=RENDERER, helm_values=HELM_VALUES)
    assert refusal(caught.value) == [
        ("MalformedReleaseError", "release.metadata.workloadVersion")
    ]
    assert isinstance(caught.value.refusals[0], MalformedReleaseError)
    assert "RC" not in json.dumps(caught.value.as_dict())


def test_the_render_boundary_still_hands_such_a_binding_to_a_renderer():
    """Measured, not closed here: the boundary takes the binding, provenance refuses it.

    Every binding value but its name is excluded from provenance, so this path
    cannot reach a release; whether a renderer may write such a value into
    generated output is a rule of the change that generates values.
    """
    document = binding_document()
    document["metadata"]["name"] = "sk-0000"
    document["spec"]["gitops"]["destinationPath"] = "gitops/sk-0000"
    support = RendererSupport(
        contract_versions=frozenset({"inferops.io/v1alpha1"}),
        binding_versions=frozenset({"inferops.io/v1alpha1"}),
        platform_defaults_versions=frozenset({"v1alpha1"}),
        profiles=frozenset(Profile),
    )
    context = prepare_render(
        parse_workload_contract(contract_document()),
        platform_defaults(),
        [parse_environment_binding(document)],
        support=support,
        binding_name=DnsLabel("sk-0000"),
    )
    assert context.value("gitops.destinationPath") == "gitops/sk-0000"
    with pytest.raises(ReleaseNotRecordedError):
        record_release(context, renderer=RENDERER, helm_values=HELM_VALUES)


# --------------------------------------------------------------------------
# 6. The limit is measured and published
# --------------------------------------------------------------------------


def test_an_unprefixed_token_written_as_a_name_is_recorded():
    """The input-trust limitation, measured on the supported path.

    A workload name is public by policy. A token with no published prefix, in
    lowercase letters and digits, is a valid DNS label, and nothing about its
    syntax tells it from a name - so it is recorded. The release document states
    this as an assumption rather than a guarantee; the day a change closes it, it
    has to say so here and there.
    """
    document = contract_document()
    document["metadata"]["name"] = UNPREFIXED
    release = record_release(
        context_for(
            parse_workload_contract(document),
            parse_environment_binding(binding_document()),
        ),
        renderer=RENDERER,
        helm_values=HELM_VALUES,
    )
    assert UNPREFIXED in canonical_release(release).decode()
    assert check_rendered_workload_release(release) == []


def published_table(marker_sentence: str) -> list[list[str]]:
    text = RELEASE_DOC.read_text(encoding="utf-8")
    start = text.index(marker_sentence)
    rows: list[list[str]] = []
    in_table = False
    for line in text[start:].splitlines()[1:]:
        if line.startswith("|"):
            in_table = True
            cells = [cell.strip() for cell in line.strip().strip("|").split("|")]
            if not all(set(cell) <= set("-: ") for cell in cells):
                rows.append(cells)
        elif in_table:
            break
    return rows[1:]


def test_the_document_publishes_every_release_field_with_its_class_and_origin():
    rows = published_table("The table below classifies every field a release has.")
    published = [
        (
            cells[0].strip("`"),
            cells[1].strip("`"),
            cells[2].strip("`"),
            cells[3].strip("`"),
        )
        for cells in rows
    ]
    assert published == [
        (row.field, row.trust.value, row.origin.value, row.source)
        for row in RELEASE_PROVENANCE
    ]


def test_the_document_publishes_every_render_value_with_its_class_and_reason():
    rows = published_table(
        "The table below classifies every value of the render context."
    )
    published: dict[str, tuple[str, str]] = {}
    for cells in rows:
        trust, reason, names = cells[0].strip("`"), cells[1], cells[2]
        for name in re.findall(r"`([^`]+)`", names):
            assert name not in published, name
            published[name] = (trust, reason)
    assert published == {
        name: (entry.trust.value, entry.reason)
        for name, entry in CONTEXT_FIELD_TRUST.items()
    }


def test_the_document_states_the_limit_and_the_separate_scanning_control():
    text = RELEASE_DOC.read_text(encoding="utf-8")
    section = text[text.index("## Provenance input trust") : text.index("## Secrets")]
    assert "cannot be proven" in section
    assert "secret scanning" in section
    # The absolute sentence the section used to open with survives only as quoted
    # history, never again as a bold claim.
    assert (
        "**A release references nothing secret and carries nothing secret.**"
        not in text
    )


def test_the_completed_record_keeps_its_original_acceptance_row():
    """The correction is additive: the original row is still there, then a dated note."""
    text = COMPLETED_RECORD.read_text(encoding="utf-8")
    original = (
        "| Sensitive data cannot enter provenance | Met structurally and by the "
        "credential rule, except the measured remainder above | Both changes |"
    )
    assert text.count(original) == 1
    addendum = text.index("## Later correction")
    assert addendum > text.index(original)
    assert "v2-s1-004-pr1-validation.md" in text[addendum:]
