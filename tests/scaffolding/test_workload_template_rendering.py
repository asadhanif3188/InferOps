"""What the workload template renders, checked against the published contract.

Every check here reads files from this repository and nothing else. No network,
no cluster, no model, no clock, no randomness: a run that passes today must pass
identically on a machine that has never had internet access.

The suite exists to make one sentence true by construction rather than by
review — **a generated workload validates without a source edit** — and to hold
the three properties that sentence hides:

* the rendered document passes the *published schema* and the *same semantic
  rules* the contract package applies to the repository's own fixtures;
* nothing template-shaped survives into the output;
* the mock and the real profile do not converge — different documents, different
  commands, and a mock that says so in its own contents.

What it does not establish: that a generated workload serves anything. Nothing
here starts a runtime, loads a model, or writes a file. Rendering returns text.
"""

from __future__ import annotations

import importlib.util
import json
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
import yaml

from inferops.domain.workload import (
    CompatibilityMatrixLoader,
    parse_workload_contract,
    set_matrix_loader,
    validate_workload_contract,
)
from inferops.scaffolding import (
    PINNED_MODEL_FILE,
    PINNED_MODEL_REPOSITORY,
    PINNED_MODEL_REVISION,
    PINNED_MODEL_SHA256,
    PINNED_MODEL_SIZE_BYTES,
    PINNED_RUNTIME_IMAGE_REFERENCE,
    REGISTERED_MODEL_REFS,
    SERVING_CAPABILITY_FOR,
    TEMPLATE_FILES,
    TEMPLATES,
    RenderedWorkload,
    WorkloadTemplateParameters,
    render_workload,
    substitutions,
    surviving_placeholders,
)
from tests.support.workload_template_cases import (
    MOCK_CASES,
    REAL_CASES,
    REPRESENTATIVE_CASES,
    case_id,
)
from tools.contract_validation.workload import validate

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
TEMPLATE_MODULE_DIR = REPO_ROOT / "src" / "inferops" / "scaffolding" / "templates"
CONTRACT_DIR = REPO_ROOT / "contracts" / "workload"
COMPATIBILITY_MATRIX_PATH = (
    CONTRACT_DIR / "compatibility" / "runtime-model-compatibility.v1alpha1.json"
)
SCHEMA_PATH = CONTRACT_DIR / "workload-contract.v1alpha1.schema.json"
REAL_FIXTURE_PATH = CONTRACT_DIR / "examples" / "valid" / "synchronous-llm-local.yaml"

#: The three files a generated workload is, whatever profile it is on.
EXPECTED_OUTPUT_PATHS = (
    "README.md",
    "tests/test_workload_contract.py",
    "workload.yaml",
)

# Field names that would be a natural home for a secret value. None may appear in
# a rendered document, and none may appear in a template either: a template is
# where a field like this would be introduced once and inherited by every
# workload generated afterwards.
FORBIDDEN_SECRET_KEYS = frozenset(
    {
        "value",
        "values",
        "secret",
        "secrets",
        "password",
        "passphrase",
        "token",
        "apikey",
        "api_key",
        "accesskey",
        "access_key",
        "privatekey",
        "private_key",
        "credential",
        "credentials",
        "bearer",
        "authorization",
    }
)

# The platform's own implementation packages. A generated workload declares; it
# does not carry a copy of the thing that serves it. The domain package is not
# here on purpose: reading the contract back is what the generated test does, and
# a typed read of a committed document is not platform implementation code.
PLATFORM_IMPLEMENTATION_MODULES = (
    "inferops.api",
    "inferops.adapters",
    "inferops.scaffolding",
    "tools.contract_validation",
)


def render(parameters: WorkloadTemplateParameters) -> RenderedWorkload:
    return render_workload(parameters)


def rendered_contract(parameters: WorkloadTemplateParameters) -> dict[str, Any]:
    document = yaml.safe_load(render(parameters).files["workload.yaml"])
    assert isinstance(document, dict)
    return document


def template_names() -> list[str]:
    return sorted(TEMPLATES)


def load_matrix() -> dict[str, Any]:
    return json.loads(COMPATIBILITY_MATRIX_PATH.read_text(encoding="utf-8"))


def walk(node: Any, path: str = "$") -> Iterator[tuple[str, str | None, Any]]:
    """Yield every (path, key, value) pair in a document."""
    if isinstance(node, dict):
        for key, value in node.items():
            yield f"{path}.{key}", key, value
            yield from walk(value, f"{path}.{key}")
    elif isinstance(node, list):
        for index, value in enumerate(node):
            yield f"{path}[{index}]", None, value
            yield from walk(value, f"{path}[{index}]")


# --------------------------------------------------------------------------
# Structure: what a render produces
# --------------------------------------------------------------------------


def test_every_published_template_is_reachable_and_non_empty() -> None:
    """Six templates, three per profile, each with text and an output path."""
    assert len(TEMPLATES) == 6, sorted(TEMPLATES)
    for name, (output_path, text) in TEMPLATES.items():
        assert output_path in EXPECTED_OUTPUT_PATHS, name
        assert text.strip(), name


def test_no_template_survives_as_a_file_beside_the_distribution() -> None:
    """The accepted rule: nothing under `src/inferops` reads a path.

    A template directory would have made this package the first exception to a
    rule that is checked, so the templates are module constants. A `.tmpl` file
    appearing here again is that decision being reversed without the record
    changing.
    """
    assert list(TEMPLATE_MODULE_DIR.rglob("*.tmpl")) == []


@pytest.mark.parametrize("parameters", REPRESENTATIVE_CASES, ids=case_id)
def test_a_render_produces_exactly_the_declared_files(
    parameters: WorkloadTemplateParameters,
) -> None:
    rendered = render(parameters)
    assert rendered.paths == EXPECTED_OUTPUT_PATHS
    assert rendered.directory_name == parameters.name


def test_both_profiles_produce_the_same_file_names() -> None:
    """Two generated workloads differ in what they say, never in what they are.

    A profile-shaped filename is a profile-shaped build step downstream: a check
    that looks for `workload.yaml` and finds `workload.mock.yaml` reports nothing
    rather than reporting a mock.
    """
    per_profile = {profile: sorted(files) for profile, files in TEMPLATE_FILES.items()}
    names = {profile: tuple(files) for profile, files in per_profile.items()}
    assert len(set(names.values())) == 1, names
    assert next(iter(names.values())) == EXPECTED_OUTPUT_PATHS


@pytest.mark.parametrize("parameters", REPRESENTATIVE_CASES, ids=case_id)
def test_rendering_is_deterministic(
    parameters: WorkloadTemplateParameters,
) -> None:
    assert render(parameters).files == render(parameters).files


@pytest.mark.parametrize("parameters", REPRESENTATIVE_CASES, ids=case_id)
def test_no_generated_file_is_empty(
    parameters: WorkloadTemplateParameters,
) -> None:
    for path, text in render(parameters).files.items():
        assert text.strip(), path
        assert text.endswith("\n"), f"{path} does not end with a newline"


# --------------------------------------------------------------------------
# The generated contract validates, without a source edit
# --------------------------------------------------------------------------


@pytest.mark.parametrize("parameters", REPRESENTATIVE_CASES, ids=case_id)
def test_the_generated_contract_passes_the_published_schema_and_semantic_rules(
    parameters: WorkloadTemplateParameters,
) -> None:
    """The acceptance criterion, applied by the repository's own validator.

    This is the same function `python -m tools.contract_validation` runs and the
    same one every committed fixture passes through, so a generated workload is
    held to the published contract rather than to a copy of it.
    """
    findings = validate(rendered_contract(parameters))
    assert findings == [], [found.as_dict() for found in findings]


@pytest.mark.parametrize("parameters", REPRESENTATIVE_CASES, ids=case_id)
def test_the_generated_contract_parses_into_a_domain_object(
    parameters: WorkloadTemplateParameters,
) -> None:
    contract = parse_workload_contract(rendered_contract(parameters))
    assert str(contract.metadata.name) == parameters.name
    assert str(contract.metadata.owner) == parameters.owner
    assert str(contract.spec.attribution.tenant) == parameters.tenant
    assert str(contract.spec.attribution.cost_center) == parameters.cost_center


@pytest.mark.parametrize("parameters", REPRESENTATIVE_CASES, ids=case_id)
def test_the_generated_contract_passes_the_domain_validation_pipeline(
    parameters: WorkloadTemplateParameters,
) -> None:
    """The contract package's own rules, not only the repository tool's.

    The accepted Sprint 0 input says generated output must pass *the same
    semantic rules the contract package publishes*. The package applies them
    against typed objects and a matrix it is handed, so this reads the committed
    matrix and hands it over rather than assuming the tool and the package agree.
    """
    set_matrix_loader(CompatibilityMatrixLoader(load_matrix()))
    contract = parse_workload_contract(rendered_contract(parameters))
    errors = validate_workload_contract(contract)
    assert errors == [], [error.as_dict() for error in errors]


@pytest.mark.parametrize("parameters", REPRESENTATIVE_CASES, ids=case_id)
def test_the_generated_contract_says_back_what_it_was_generated_from(
    parameters: WorkloadTemplateParameters,
) -> None:
    document = rendered_contract(parameters)
    spec = document["spec"]
    assert document["metadata"]["name"] == parameters.name
    assert document["metadata"]["owner"] == parameters.owner
    assert document["metadata"]["version"] == parameters.version
    assert document["metadata"]["description"] == parameters.description
    assert spec["profile"] == parameters.profile
    assert spec["environment"] == parameters.environment
    assert spec["model"]["modelRef"] == parameters.resolved_model_ref()
    assert spec["model"]["runtimeProfile"] == parameters.runtime_profile
    assert spec["resources"]["cpu"] == parameters.cpu
    assert spec["resources"]["memory"] == parameters.memory
    assert spec["resources"]["accelerator"]["type"] == parameters.accelerator_type
    assert spec["resources"]["accelerator"]["count"] == parameters.accelerator_count
    assert spec["scaling"]["minimumReplicas"] == parameters.minimum_replicas
    assert spec["scaling"]["maximumReplicas"] == parameters.maximum_replicas
    assert spec["security"]["dataClassification"] == parameters.data_classification


@pytest.mark.parametrize("parameters", REPRESENTATIVE_CASES, ids=case_id)
def test_a_resource_quantity_survives_as_a_string(
    parameters: WorkloadTemplateParameters,
) -> None:
    """`cpu: 6` is an integer in YAML and a refusal in the schema.

    The template quotes both quantities for that reason, and this is the check
    that notices if a quote is removed.
    """
    resources = rendered_contract(parameters)["spec"]["resources"]
    assert isinstance(resources["cpu"], str)
    assert isinstance(resources["memory"], str)


# --------------------------------------------------------------------------
# Nothing template-shaped survives
# --------------------------------------------------------------------------


@pytest.mark.parametrize("parameters", REPRESENTATIVE_CASES, ids=case_id)
def test_no_placeholder_survives_into_generated_output(
    parameters: WorkloadTemplateParameters,
) -> None:
    for path, text in render(parameters).files.items():
        assert surviving_placeholders(text) == (), path


@pytest.mark.parametrize("parameters", REPRESENTATIVE_CASES, ids=case_id)
def test_no_generated_file_mentions_the_template_that_produced_it(
    parameters: WorkloadTemplateParameters,
) -> None:
    """A generated file naming a `.tmpl` is a file that was copied, not rendered."""
    for path, text in render(parameters).files.items():
        assert ".tmpl" not in text, path


@pytest.mark.parametrize("parameters", REPRESENTATIVE_CASES, ids=case_id)
def test_no_other_representative_name_leaks_into_a_generated_workload(
    parameters: WorkloadTemplateParameters,
) -> None:
    """The stale-name failure, stated as a property rather than as a spot check.

    A template built by copying a real workload keeps that workload's name in a
    comment, a label, or a path. Rendering one case must produce nothing that
    names another.
    """
    mine = (parameters.name, parameters.owner, parameters.tenant)
    others = {case.name for case in REPRESENTATIVE_CASES} | {
        case.owner for case in REPRESENTATIVE_CASES
    }
    # A case name that is a substring of this one - `support-assistant` inside
    # `support-assistant-mock` - is not a leak, it is the mock suffix rule.
    stale_names = {other for other in others if not any(other in own for own in mine)}
    assert stale_names, "the cases share every identifier, so this proves nothing"
    for path, text in render(parameters).files.items():
        for stale in sorted(stale_names):
            assert stale not in text, f"{path} names '{stale}'"


def test_every_placeholder_a_template_uses_has_a_value_for_its_profile() -> None:
    """A template may not name a value the parameter set cannot supply.

    Rendering already raises for a missing one; this fails at the template rather
    than at the first author unlucky enough to pick that profile.
    """
    for profile, files in TEMPLATE_FILES.items():
        example = next(
            case for case in REPRESENTATIVE_CASES if case.profile == profile.value
        )
        supplied = set(substitutions(example))
        for template_name in files.values():
            text = TEMPLATES[template_name][1]
            named = {
                placeholder.strip("${}") for placeholder in surviving_placeholders(text)
            }
            assert named <= supplied, (
                f"{template_name} names {sorted(named - supplied)}, which "
                f"{profile.value} parameters do not supply"
            )


def test_every_supplied_value_is_used_by_at_least_one_template() -> None:
    """A parameter no template reads is a parameter an author fills in for nothing."""
    for profile, files in TEMPLATE_FILES.items():
        example = next(
            case for case in REPRESENTATIVE_CASES if case.profile == profile.value
        )
        used: set[str] = set()
        for template_name in files.values():
            text = TEMPLATES[template_name][1]
            used |= {
                placeholder.strip("${}") for placeholder in surviving_placeholders(text)
            }
        unused = set(substitutions(example)) - used
        assert unused == set(), f"{profile.value} supplies unused values: {unused}"


# --------------------------------------------------------------------------
# The mock and real boundary, in what is generated
# --------------------------------------------------------------------------


@pytest.mark.parametrize("parameters", MOCK_CASES, ids=case_id)
def test_a_generated_mock_declares_itself_a_mock_in_its_own_contents(
    parameters: WorkloadTemplateParameters,
) -> None:
    """Boundary rule 1, applied to generated output.

    The label has to be readable from the artifact rather than from the directory
    it sits in, so it is asserted in three independent places: the document's own
    profile block, the identity the document carries, and the prose a reader
    meets first.
    """
    rendered = render(parameters)
    document = yaml.safe_load(rendered.files["workload.yaml"])
    assert document["spec"]["profile"] == "mock-llm"
    assert document["spec"]["mockLlm"]["ciOnly"] is True
    assert document["spec"]["mockLlm"]["determinism"] == "fixed-fixture"
    assert "synchronousLlm" not in document["spec"]
    assert document["metadata"]["name"].endswith("-mock")
    assert "MOCK" in rendered.files["workload.yaml"].upper().split("APIVERSION")[0]
    assert "mock workload" in rendered.files["README.md"].lower()


@pytest.mark.parametrize("parameters", MOCK_CASES, ids=case_id)
def test_a_generated_mock_cites_no_runtime_proof_and_declares_no_secret(
    parameters: WorkloadTemplateParameters,
) -> None:
    spec = rendered_contract(parameters)["spec"]
    assert spec["security"]["secretRefs"] == []
    assert "proofRefs" not in spec["evidence"]


@pytest.mark.parametrize("parameters", REAL_CASES, ids=case_id)
def test_a_generated_real_workload_cites_no_proof_it_has_not_produced(
    parameters: WorkloadTemplateParameters,
) -> None:
    """A generated workload has executed nothing, so it may cite nothing.

    Pre-filling `proofRefs` with the feasibility record would hand every
    generated workload a claim produced by a different one, which is the
    overclaim the evidence rules exist to prevent.
    """
    spec = rendered_contract(parameters)["spec"]
    assert "proofRefs" not in spec["evidence"]
    assert spec["evidence"]["runbookRef"] == "docs/serving/feasibility-workflow.md"


@pytest.mark.parametrize("parameters", REAL_CASES, ids=case_id)
def test_a_generated_real_workload_does_not_present_itself_as_a_mock(
    parameters: WorkloadTemplateParameters,
) -> None:
    document = rendered_contract(parameters)
    assert document["spec"]["profile"] == "synchronous-llm"
    assert "mockLlm" not in document["spec"]
    assert not document["metadata"]["name"].endswith("-mock")


def test_the_mock_and_real_quick_starts_are_not_the_same_document() -> None:
    """Acceptance: mock and real commands are distinct.

    Distinct in both directions, which is the part a single comparison misses: a
    mock quick start must not offer the real lane, and a real one must offer it.
    """
    mock_readme = render(MOCK_CASES[0]).files["README.md"]
    real_readme = render(REAL_CASES[0]).files["README.md"]

    assert "-m realruntime" in real_readme
    assert "-m realruntime -q" in real_readme
    assert "INFEROPS_SERVING_ADAPTER=real" in real_readme

    assert "INFEROPS_SERVING_ADAPTER=real" not in mock_readme
    mock_command_lines = [
        line for line in mock_readme.splitlines() if line.startswith("python -m")
    ]
    real_command_lines = [
        line for line in real_readme.splitlines() if line.startswith("python -m")
    ]
    assert mock_command_lines, mock_readme
    assert len(real_command_lines) == len(mock_command_lines) + 1
    assert not any("realruntime" in line for line in mock_command_lines)
    assert any("realruntime" in line for line in real_command_lines)


@pytest.mark.parametrize("parameters", REPRESENTATIVE_CASES, ids=case_id)
def test_a_quick_start_command_names_the_directory_the_workload_is_generated_into(
    parameters: WorkloadTemplateParameters,
) -> None:
    readme = render(parameters).files["README.md"]
    assert f"python -m tools.contract_validation {parameters.name}/workload.yaml" in (
        readme
    )
    assert f"python -m pytest {parameters.name}/tests -q" in readme


# --------------------------------------------------------------------------
# A generated workload carries no platform code and no secret field
# --------------------------------------------------------------------------


@pytest.mark.parametrize("parameters", REPRESENTATIVE_CASES, ids=case_id)
def test_a_generated_workload_carries_no_platform_implementation_code(
    parameters: WorkloadTemplateParameters,
) -> None:
    """The boundary the platform rests on: a workload declares, it does not serve."""
    generated_test = render(parameters).files["tests/test_workload_contract.py"]
    for module in PLATFORM_IMPLEMENTATION_MODULES:
        assert f"import {module}" not in generated_test
        assert f"from {module}" not in generated_test
    assert "from inferops.domain.workload import" in generated_test


@pytest.mark.parametrize("parameters", REPRESENTATIVE_CASES, ids=case_id)
def test_no_generated_document_carries_a_field_a_secret_could_be_written_into(
    parameters: WorkloadTemplateParameters,
) -> None:
    document = rendered_contract(parameters)
    for path, key, _ in walk(document):
        if key is None:
            continue
        assert key.lower() not in FORBIDDEN_SECRET_KEYS, path


@pytest.mark.parametrize("template_name", template_names())
def test_no_template_offers_a_place_to_paste_a_secret(template_name: str) -> None:
    """Checked at the template, because a template is inherited.

    A field like this introduced here would appear in every workload generated
    afterwards, and the author of the tenth one would reasonably assume the
    platform meant it to be filled in.
    """
    text = TEMPLATES[template_name][1].lower()
    for forbidden in sorted(FORBIDDEN_SECRET_KEYS):
        assert f"{forbidden}:" not in text, forbidden
    if "secretrefs" in text:
        assert "secretrefs: []" in text, (
            "a template may declare an empty secret reference list and nothing else"
        )


# --------------------------------------------------------------------------
# The pins have not drifted from the accepted decision
# --------------------------------------------------------------------------


def test_the_pinned_pair_is_the_one_the_project_executed() -> None:
    """A drift between this template and ADR 0002 fails here, not in a review."""
    executed = load_matrix()["executedPairs"]
    assert len(executed) == 1, executed
    pair = executed[0]
    assert pair["imageReference"] == PINNED_RUNTIME_IMAGE_REFERENCE
    assert pair["modelRepository"] == PINNED_MODEL_REPOSITORY
    assert pair["modelRevision"] == PINNED_MODEL_REVISION
    assert pair["modelFile"] == PINNED_MODEL_FILE


def test_the_pinned_artifact_size_and_hash_are_the_committed_ones() -> None:
    """The two values the matrix does not carry, taken from the committed fixture."""
    fixture = yaml.safe_load(REAL_FIXTURE_PATH.read_text(encoding="utf-8"))
    artifact = fixture["spec"]["synchronousLlm"]["modelArtifact"]
    assert artifact["sizeBytes"] == PINNED_MODEL_SIZE_BYTES
    assert artifact["sha256"] == PINNED_MODEL_SHA256
    runtime = fixture["spec"]["synchronousLlm"]["runtime"]
    assert runtime["imageReference"] == PINNED_RUNTIME_IMAGE_REFERENCE


@pytest.mark.parametrize("parameters", REAL_CASES, ids=case_id)
def test_a_generated_real_workload_pins_bytes_and_a_digest(
    parameters: WorkloadTemplateParameters,
) -> None:
    profile_block = rendered_contract(parameters)["spec"]["synchronousLlm"]
    assert profile_block["runtime"]["imageReference"] == PINNED_RUNTIME_IMAGE_REFERENCE
    artifact = profile_block["modelArtifact"]
    assert artifact["repository"] == PINNED_MODEL_REPOSITORY
    assert artifact["revision"] == PINNED_MODEL_REVISION
    assert artifact["file"] == PINNED_MODEL_FILE
    assert artifact["sizeBytes"] == PINNED_MODEL_SIZE_BYTES
    assert artifact["sha256"] == PINNED_MODEL_SHA256


def test_the_serving_capability_for_each_profile_is_the_one_the_schema_fixes() -> None:
    """The template derives the capability; the schema decides it."""
    schema = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))
    conditionals = schema["$defs"]["spec"]["allOf"]
    fixed_by_schema = {
        branch["if"]["properties"]["profile"]["const"]: branch["then"]["properties"][
            "model"
        ]["properties"]["servingCapability"]["const"]
        for branch in conditionals
    }
    derived = {
        profile.value: capability.value
        for profile, capability in SERVING_CAPABILITY_FOR.items()
    }
    assert derived == fixed_by_schema


def test_every_registered_model_identity_is_one_the_repository_publishes() -> None:
    """The catalogue is closed, and its two members are checked against the source.

    The real identity is the one the committed valid fixture declares; the mock
    identity is the one the committed mock fixture declares. A third entry added
    here without a fixture behind it fails.
    """
    real_fixture = yaml.safe_load(REAL_FIXTURE_PATH.read_text(encoding="utf-8"))
    mock_fixture = yaml.safe_load(
        (CONTRACT_DIR / "examples" / "valid" / "mock-llm-ci.yaml").read_text(
            encoding="utf-8"
        )
    )
    published = {
        real_fixture["spec"]["model"]["servingCapability"]: real_fixture["spec"][
            "model"
        ]["modelRef"],
        mock_fixture["spec"]["model"]["servingCapability"]: mock_fixture["spec"][
            "model"
        ]["modelRef"],
    }
    registered = {
        capability.value: refs for capability, refs in REGISTERED_MODEL_REFS.items()
    }
    assert set(registered) == set(published)
    for capability, refs in registered.items():
        assert refs == (published[capability],), capability


# --------------------------------------------------------------------------
# The generated test skeleton is a test, not a paragraph shaped like one
# --------------------------------------------------------------------------


def materialise(parameters: WorkloadTemplateParameters, root: Path) -> Path:
    """Write a rendered workload under ``root`` and return its directory.

    The only place in this suite that touches a file system, and it touches
    pytest's temporary directory. The scaffolding command that writes a workload
    where an author asked for it is `V1-S1-006-PR2`; this is a test putting a
    rendered result somewhere it can be run.
    """
    workload_root = root / parameters.name
    for path, text in render(parameters).files.items():
        target = workload_root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
    return workload_root


@pytest.mark.parametrize("parameters", REPRESENTATIVE_CASES, ids=case_id)
def test_the_generated_test_skeleton_imports_and_passes(
    parameters: WorkloadTemplateParameters, tmp_path: Path
) -> None:
    """A skeleton that does not run is a file that looks like coverage.

    The generated module is imported from the rendered tree and every test
    function in it is called directly. No subprocess, no collection, no network:
    the module reads the `workload.yaml` beside it and asserts against it, which
    is the whole of what it claims to do.
    """
    workload_root = materialise(parameters, tmp_path)
    module_path = workload_root / "tests" / "test_workload_contract.py"
    module_name = f"generated_workload_{parameters.name.replace('-', '_')}"

    spec = importlib.util.spec_from_file_location(module_name, module_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    cases = sorted(
        name
        for name, value in vars(module).items()
        if name.startswith("test_") and callable(value)
    )
    assert len(cases) >= 6, cases
    for name in cases:
        getattr(module, name)()


@pytest.mark.parametrize("parameters", REPRESENTATIVE_CASES, ids=case_id)
def test_a_generated_workload_writes_only_the_three_files_it_declares(
    parameters: WorkloadTemplateParameters, tmp_path: Path
) -> None:
    workload_root = materialise(parameters, tmp_path)
    written = sorted(
        path.relative_to(workload_root).as_posix()
        for path in workload_root.rglob("*")
        if path.is_file()
    )
    assert tuple(written) == EXPECTED_OUTPUT_PATHS
