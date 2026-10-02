"""The Helm values renderer: generated chart values from a validated render context.

Every check reads files from this repository and nothing else. No network, no
cluster, no clock, and no randomness; ``helm`` is run, with no shell and no
cluster, only by the tests that say so, and they skip when it is not on PATH.

Seven things are asserted:

1. **Golden output.** The reference workload on each local binding renders the
   committed golden file byte for byte, and both bindings render the same bytes.
2. **Deterministic and pure.** Equal inputs give equal values and text, whatever
   order the bindings arrive in, under two hash seeds, and with every clock,
   random source, and environment read patched to fail.
3. **Every value accounted for.** Each render-context value has one disposition;
   the values written are exactly the chart values the mapping names; the chart
   constraints the renderer checks are the chart schema's, keyword for keyword.
4. **The chart accepts the output.** The generated values, merged over the chart's
   defaults with and without the hand-written file - admitted beside them by
   ``admit_manual_values``, never loaded around it - validate against the chart's
   values schema; with ``helm`` present the admitted pair renders exactly what the
   V1 real fixture renders once its environment is the contract's.
5. **Every refusal has a case.** Each of the renderer's chart rules refuses
   twenty accepted contracts built for them, through ``render_with``, under exactly
   that rule, without quoting a value and without returning anything; the support
   checks ``render`` repeats are reached by calling it directly, the hand-written
   values rule through ``manual_value_findings``, and one gap is measured instead.
6. **Hand-written values cannot repeat contract intent.** Every file in the
   repository named as a supported hand-written values file is admitted beside the
   generated values, and a new one that is not fails this suite; setting,
   replacing, or removing a generated value is refused, through the admission and
   the finding function both, naming the path and never the value, and a sibling
   of one is not.
7. **One canonical YAML form.** Every string is quoted and round-trips; what has
   no single spelling is refused.
"""

from __future__ import annotations

import copy
import json
import os
import random
import re
import secrets
import shutil
import subprocess
import sys
import time
import uuid
from collections.abc import Callable, Mapping
from pathlib import Path
from types import MappingProxyType
from typing import Any

import jsonschema
import pytest
import yaml

from inferops.domain import RequestContext
from inferops.domain.environment import EnvironmentBinding, parse_environment_binding
from inferops.domain.environment.versions import SUPPORTED_BINDING_VERSIONS
from inferops.domain.release import GitRevision
from inferops.domain.render import (
    CAPABILITY_UNAVAILABLE,
    CHART_NAME,
    CHART_VALUE_CONSTRAINTS,
    CHART_VERSION,
    CONTRACT_INVALID,
    GENERATED_VALUE_PATHS,
    HELM_VALUE_DISPOSITIONS,
    HELM_VALUES_SUPPORT,
    MANUAL_VALUES_SUFFIX,
    RENDER_FIELD_OWNERSHIP,
    RENDER_RULES,
    AdmittedHelmValues,
    ApiDefaults,
    Disposition,
    GeneratedHelmValues,
    HelmValuesRenderer,
    PlatformDefaults,
    RefusalCategory,
    RenderContext,
    RenderRefused,
    ValuesFormError,
    admit_manual_values,
    build_render_context,
    canonical_yaml,
    manual_value_findings,
    render_with,
    validate_for_render,
)
from inferops.domain.render import helm_values as helm_values_module
from inferops.domain.workload import (
    CompatibilityMatrixLoader,
    DnsLabel,
    Profile,
    WorkloadContract,
    parse_workload_contract,
    set_matrix_loader,
)
from inferops.domain.workload.versions import SUPPORTED_CONTRACT_VERSIONS

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
CHART_DIR = REPO_ROOT / "charts" / "inferops-llm"
CHART_VALUES = CHART_DIR / "values.yaml"
CHART_SCHEMA = CHART_DIR / "values.schema.json"
REAL_VALUES = CHART_DIR / "ci" / "real-values.yaml"
REAL_RENDER = CHART_DIR / "ci" / "rendered" / "real.expected.yaml"
MATRIX_PATH = (
    REPO_ROOT
    / "contracts"
    / "workload"
    / "compatibility"
    / "runtime-model-compatibility.v1alpha1.json"
)
WORKLOAD_VALID_DIR = REPO_ROOT / "contracts" / "workload" / "examples" / "valid"
BINDING_VALID_DIR = REPO_ROOT / "contracts" / "environment" / "examples" / "valid"
FIXTURES = REPO_ROOT / "tests" / "domain" / "fixtures" / "helm-values"
GOLDEN = FIXTURES / "support-assistant-local-kind" / "values.generated.yaml"
MANUAL = FIXTURES / "support-assistant-local.manual-values.yaml"
DOC = REPO_ROOT / "docs" / "domain" / "helm-values-renderer.md"

DEFAULTS_REVISION = "b" * 40
RENDERER_REVISION = "a" * 40
LATER_VERSION = "inferops.io/v1alpha2"

#: The renderer's own rules, which no boundary step reaches.
RENDERER_RULES = (
    "render-value-unsupported",
    "render-capability-unsupported",
    "render-value-credential-shaped",
    "render-manual-value-generated",
)

set_matrix_loader(
    CompatibilityMatrixLoader(json.loads(MATRIX_PATH.read_text(encoding="utf-8")))
)


# --------------------------------------------------------------------------
# Inputs
# --------------------------------------------------------------------------


def load(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def contract_document(name: str = "synchronous-llm-local") -> dict[str, Any]:
    document: dict[str, Any] = load(WORKLOAD_VALID_DIR / f"{name}.yaml")
    return document


def contract(name: str = "synchronous-llm-local") -> WorkloadContract:
    return parse_workload_contract(contract_document(name))


def changed(mutate: Callable[[dict[str, Any]], None]) -> WorkloadContract:
    document = contract_document()
    mutate(document)
    return parse_workload_contract(document)


def binding_document(name: str = "local-kind") -> dict[str, Any]:
    document: dict[str, Any] = load(BINDING_VALID_DIR / f"{name}.yaml")
    return document


def binding(name: str = "local-kind") -> EnvironmentBinding:
    return parse_environment_binding(binding_document(name))


def binding_for(environment: str) -> EnvironmentBinding:
    """A binding serving an environment no committed fixture serves."""
    document = binding_document()
    document["metadata"]["name"] = f"{environment}-kind"
    document["spec"]["environment"] = environment
    document["spec"]["gitops"]["destinationPath"] = f"gitops/environments/{environment}"
    return parse_environment_binding(document)


def bindings_for(workload: WorkloadContract) -> list[EnvironmentBinding]:
    environment = workload.spec.environment.value
    return [binding()] if environment == "local" else [binding_for(environment)]


def defaults(**overrides: int) -> PlatformDefaults:
    """The chart's own API defaults, read at a placeholder revision."""
    chart = load(CHART_VALUES)["api"]
    settings = {
        "request_timeout_ms": chart["requestTimeoutMs"],
        "drain_timeout_ms": chart["drainTimeoutMs"],
        "max_output_tokens": chart["maxOutputTokens"],
        **overrides,
    }
    return PlatformDefaults(
        "v1alpha1", GitRevision(DEFAULTS_REVISION), ApiDefaults(**settings)
    )


def renderer() -> HelmValuesRenderer:
    return HelmValuesRenderer(GitRevision(RENDERER_REVISION))


def render(
    workload: WorkloadContract | None = None,
    *,
    bindings: list[EnvironmentBinding] | None = None,
    binding_name: str | None = None,
    platform_defaults: PlatformDefaults | None = None,
) -> GeneratedHelmValues:
    workload = contract() if workload is None else workload
    return render_with(
        renderer(),
        workload,
        defaults() if platform_defaults is None else platform_defaults,
        bindings_for(workload) if bindings is None else bindings,
        binding_name=None if binding_name is None else DnsLabel(binding_name),
    )


def refusal_of(workload: WorkloadContract, **kwargs: Any) -> RenderRefused:
    with pytest.raises(RenderRefused) as raised:
        render(workload, **kwargs)
    return raised.value


def deep_merge(*documents: Mapping[str, Any]) -> dict[str, Any]:
    """Values files merged as Helm merges them: maps deeply, anything else replaced."""
    merged: dict[str, Any] = {}
    for document in documents:
        for key, value in document.items():
            if isinstance(value, Mapping) and isinstance(merged.get(key), dict):
                merged[key] = deep_merge(merged[key], value)
            else:
                merged[key] = copy.deepcopy(value)
    return merged


def admitted(manual: Path = MANUAL) -> AdmittedHelmValues:
    """The reference values and a hand-written file, paired by the admission check."""
    return admit_manual_values(render(), load(manual))


def admitted_files(directory: Path, manual: Path = MANUAL) -> tuple[Path, Path]:
    """The admitted pair written as Helm reads it: generated first, then hand-written.

    Helm is given what was admitted, not the file on disk beside it, so what it
    renders is what the check passed.
    """
    pair = admitted(manual)
    generated = directory / "values.generated.yaml"
    generated.write_bytes(pair.generated.to_yaml().encode("utf-8"))
    hand_written = directory / "admitted.manual-values.yaml"
    hand_written.write_text(
        yaml.safe_dump(pair.documents()[1], sort_keys=True), encoding="utf-8"
    )
    return generated, hand_written


#: Top-level directories no supported hand-written values file lives in: version
#: control, tool caches, build output, and local machine state, all untracked.
#: Skipped at the repository's root only, so a directory with one of these names
#: deeper in the tree is still searched.
_NOT_SEARCHED_AT_ROOT = frozenset(
    {
        ".artifacts",
        ".cache",
        ".git",
        ".kube",
        ".mypy_cache",
        ".pytest_cache",
        ".ruff_cache",
        ".venv",
        "dist",
    }
)

#: Directories skipped at any depth: interpreter and tool state that never holds a
#: file anybody wrote.
_NOT_SEARCHED_ANYWHERE = frozenset({"__pycache__", ".terraform", "node_modules"})


def supported_manual_values_files(root: Path) -> list[Path]:
    """Every file under ``root`` named as a supported hand-written values file.

    Found by the name the platform publishes, ``MANUAL_VALUES_SUFFIX``, rather than
    listed here, so a new file is checked the moment it exists.
    """
    found: list[Path] = []
    for directory, subdirectories, files in os.walk(root):
        skipped = _NOT_SEARCHED_ANYWHERE | (
            _NOT_SEARCHED_AT_ROOT if Path(directory) == root else frozenset()
        )
        subdirectories[:] = sorted(
            name for name in subdirectories if name not in skipped
        )
        found.extend(
            Path(directory) / name
            for name in sorted(files)
            if name.endswith(MANUAL_VALUES_SUFFIX)
        )
    return found


def unadmitted_manual_values(root: Path) -> list[tuple[str, list[str]]]:
    """Each supported hand-written file under ``root`` the admission refuses, with why."""
    generated = render()
    refused: list[tuple[str, list[str]]] = []
    for path in supported_manual_values_files(root):
        try:
            admit_manual_values(generated, load(path))
        except RenderRefused as refusal:
            refused.append(
                (
                    path.relative_to(root).as_posix(),
                    [finding.field for finding in refusal.findings],
                )
            )
    return refused


def leaf_paths(
    document: Mapping[str, Any], prefix: tuple[str, ...] = ()
) -> set[tuple[str, ...]]:
    """Every leaf, as a tuple of keys: a chart key such as a label name holds dots."""
    paths: set[tuple[str, ...]] = set()
    for key, value in document.items():
        if isinstance(value, Mapping) and value:
            paths |= leaf_paths(value, (*prefix, key))
        else:
            paths.add((*prefix, key))
    return paths


def dotted(paths: set[tuple[str, ...]]) -> set[str]:
    return {".".join(path) for path in paths}


def at(document: Mapping[str, Any], path: tuple[str, ...] | str) -> Any:
    node: Any = document
    for part in path.split(".") if isinstance(path, str) else path:
        node = node[part]
    return node


# --------------------------------------------------------------------------
# 1. Golden output
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["local-kind", "local-docker-desktop"])
def test_the_reference_workload_renders_the_committed_golden_file(name: str) -> None:
    bindings = [binding("local-kind"), binding("local-docker-desktop")]
    values = render(bindings=bindings, binding_name=name)
    assert values.to_yaml() == GOLDEN.read_bytes().decode("utf-8")


def test_the_golden_file_is_lf_only_and_parses_to_the_values() -> None:
    raw = GOLDEN.read_bytes()
    assert b"\r" not in raw
    assert yaml.safe_load(raw) == render().as_document()


def test_two_bindings_that_differ_only_in_unrendered_facts_render_the_same_bytes() -> (
    None
):
    """Provider and GitOps destination are not chart values, so they move nothing."""
    kind, desktop = binding("local-kind"), binding("local-docker-desktop")
    differing = dotted(
        {
            path
            for path in leaf_paths(kind.as_document())
            if at(kind.as_document(), path) != at(desktop.as_document(), path)
        }
    )
    assert differing == {
        "metadata.name",
        "spec.destination.clusterProvider",
        "spec.gitops.destinationPath",
    }
    both = [kind, desktop]
    assert (
        render(bindings=both, binding_name="local-kind").to_yaml()
        == render(bindings=both, binding_name="local-docker-desktop").to_yaml()
    )


def test_every_generated_value_is_the_inputs_own() -> None:
    """Each value written is read from its owner, and never invented."""
    workload = contract_document()
    sync = workload["spec"]["synchronousLlm"]
    kind = binding_document()
    chart_api = load(CHART_VALUES)["api"]
    values = render().as_document()
    repository, digest = sync["runtime"]["imageReference"].split("@")
    assert values == {
        "profile": "real",
        "api": {
            "replicaCount": kind["spec"]["platform"]["apiReplicas"],
            "requestTimeoutMs": chart_api["requestTimeoutMs"],
            "drainTimeoutMs": chart_api["drainTimeoutMs"],
            "maxOutputTokens": chart_api["maxOutputTokens"],
        },
        "runtime": {
            "replicaCount": workload["spec"]["scaling"]["minimumReplicas"],
            "image": {"repository": repository, "digest": digest},
            "resources": {
                "limits": {
                    "cpu": workload["spec"]["resources"]["cpu"],
                    "memory": workload["spec"]["resources"]["memory"],
                }
            },
        },
        "model": {
            "identifier": workload["spec"]["model"]["modelRef"],
            "revision": sync["modelArtifact"]["revision"],
            "artifact": {
                "repository": sync["modelArtifact"]["repository"],
                "fileName": sync["modelArtifact"]["file"],
                "sizeBytes": sync["modelArtifact"]["sizeBytes"],
                "sha256": sync["modelArtifact"]["sha256"],
            },
            "cache": {"claimName": kind["spec"]["modelCache"]["claimName"]},
        },
        "ownership": {
            "owner": workload["metadata"]["owner"],
            "workloadId": workload["metadata"]["name"],
            "workloadVersion": workload["metadata"]["version"],
            "tenant": workload["spec"]["attribution"]["tenant"],
            "costCenter": workload["spec"]["attribution"]["costCenter"],
        },
        "telemetry": {
            "deploymentEnvironment": workload["spec"]["environment"],
            "enabled": True,
        },
        "security": {"secretRefs": []},
    }


# --------------------------------------------------------------------------
# 2. Deterministic and pure
# --------------------------------------------------------------------------


def test_equal_inputs_render_equal_values_whatever_the_binding_order() -> None:
    forward = [binding("local-kind"), binding("local-docker-desktop")]
    first = render(bindings=forward, binding_name="local-kind")
    second = render(bindings=list(reversed(forward)), binding_name="local-kind")
    assert first == second
    assert first.to_yaml() == second.to_yaml()


def moved(before: GeneratedHelmValues, after: GeneratedHelmValues) -> set[str]:
    old, new = before.as_document(), after.as_document()
    assert leaf_paths(old) == leaf_paths(new)
    return dotted({path for path in leaf_paths(old) if at(old, path) != at(new, path)})


@pytest.mark.parametrize(
    ("mutate", "expected"),
    [
        (
            lambda d: d["spec"]["model"].__setitem__("modelRef", "another-model"),
            {"model.identifier"},
        ),
        (
            lambda d: d["spec"]["attribution"].__setitem__("tenant", "other"),
            {"ownership.tenant"},
        ),
        (
            lambda d: d["spec"]["resources"].__setitem__("memory", "4Gi"),
            {"runtime.resources.limits.memory"},
        ),
        (
            lambda d: d["spec"]["synchronousLlm"]["runtime"].__setitem__(
                "imageReference", "ghcr.io/ggml-org/llama.cpp@sha256:" + "c" * 64
            ),
            {"runtime.image.digest"},
        ),
    ],
)
def test_one_contract_change_moves_exactly_the_values_it_owns(
    mutate: Callable[[dict[str, Any]], None], expected: set[str]
) -> None:
    """A controlled intent mutation moves its own generated values and nothing else."""
    assert moved(render(), render(changed(mutate))) == expected


def test_one_binding_change_moves_exactly_the_values_it_owns() -> None:
    document = binding_document()
    document["spec"]["modelCache"]["claimName"] = "another-cache"
    document["spec"]["platform"]["apiReplicas"] = 2
    after = render(bindings=[parse_environment_binding(document)])
    assert moved(render(), after) == {"model.cache.claimName", "api.replicaCount"}


def test_a_defaults_change_moves_only_its_own_value() -> None:
    after = render(platform_defaults=defaults(request_timeout_ms=60000))
    assert moved(render(), after) == {"api.requestTimeoutMs"}


def test_the_renderer_revision_takes_no_part_in_the_values() -> None:
    context = reference_context()
    first = HelmValuesRenderer(GitRevision("a" * 40)).render(context)
    second = HelmValuesRenderer(GitRevision("c" * 40)).render(context)
    assert first.to_yaml() == second.to_yaml()


def reference_context() -> RenderContext:
    return build_render_context(
        validate_for_render(contract()),
        defaults(),
        [binding("local-kind")],
    )


def test_rendering_reads_no_clock_no_random_source_and_no_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("the renderer consulted a clock, a random source, or os")

    context = reference_context()
    expected = GOLDEN.read_bytes().decode("utf-8")
    for owner, name in [
        (time, "time"),
        (time, "time_ns"),
        (time, "monotonic"),
        (time, "perf_counter"),
        (time, "localtime"),
        (time, "gmtime"),
        (uuid, "uuid1"),
        (uuid, "uuid4"),
        (os, "urandom"),
        (os, "getenv"),
        (random, "random"),
        (random, "getrandbits"),
        (random, "randbytes"),
        (secrets, "token_bytes"),
        (secrets, "token_hex"),
    ]:
        monkeypatch.setattr(owner, name, forbidden)
    assert renderer().render(context).to_yaml() == expected


RENDER_PROGRAM = """
import sys
sys.path[:0] = [{root!r}, {src!r}]
import tests.domain.test_helm_values_renderer as suite
sys.stdout.buffer.write(suite.render().to_yaml().encode("utf-8"))
"""


def test_two_interpreters_under_two_hash_seeds_write_the_same_bytes() -> None:
    program = RENDER_PROGRAM.format(root=str(REPO_ROOT), src=str(REPO_ROOT / "src"))
    answers = []
    for seed in ("0", "4242"):
        result = subprocess.run(
            [sys.executable, "-c", program],
            capture_output=True,
            check=True,
            cwd=REPO_ROOT,
            env={**os.environ, "PYTHONHASHSEED": seed},
            timeout=120,
        )
        answers.append(result.stdout)
    assert answers[0] == answers[1] == GOLDEN.read_bytes()


def test_the_values_hold_no_timestamp_and_no_random_identifier() -> None:
    text = render().to_yaml()
    assert re.search(r"\d{4}-\d{2}-\d{2}|\d{2}:\d{2}:\d{2}|GMT", text) is None
    assert (
        re.search(r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", text)
        is None
    )


# --------------------------------------------------------------------------
# 3. Every value accounted for
# --------------------------------------------------------------------------


def test_every_context_value_has_exactly_one_disposition() -> None:
    assert list(HELM_VALUE_DISPOSITIONS) == [row.name for row in RENDER_FIELD_OWNERSHIP]


def test_the_disposition_counts_are_the_published_ones() -> None:
    counts = {
        disposition: sum(
            1
            for row in HELM_VALUE_DISPOSITIONS.values()
            if row.disposition is disposition
        )
        for disposition in Disposition
    }
    assert counts == {
        Disposition.RENDERED: 24,
        Disposition.CONSTRAINED: 8,
        Disposition.NOT_RENDERED: 12,
    }


def test_only_a_rendered_value_names_a_target_and_every_target_is_constrained() -> None:
    targets = [
        target for row in HELM_VALUE_DISPOSITIONS.values() for target in row.targets
    ]
    for row in HELM_VALUE_DISPOSITIONS.values():
        assert bool(row.targets) == (row.disposition is Disposition.RENDERED)
        assert row.reason
    assert len(targets) == len(set(targets)) == 25
    assert set(targets) == set(CHART_VALUE_CONSTRAINTS)
    assert {".".join(path) for path in GENERATED_VALUE_PATHS} == set(targets)


def test_a_render_writes_every_generated_value_and_nothing_else() -> None:
    assert set(render().paths()) == set(CHART_VALUE_CONSTRAINTS)


def resolve(schema: dict[str, Any], node: dict[str, Any]) -> dict[str, Any]:
    while "$ref" in node:
        node = schema["$defs"][node["$ref"].rsplit("/", 1)[1]]
    return node


def schema_node(path: str) -> dict[str, Any]:
    schema = json.loads(CHART_SCHEMA.read_text(encoding="utf-8"))
    node = schema
    for part in path.split("."):
        node = resolve(schema, resolve(schema, node)["properties"][part])
    return resolve(schema, node)


@pytest.mark.parametrize("path", sorted(CHART_VALUE_CONSTRAINTS))
def test_each_chart_constraint_is_the_chart_schemas_own(path: str) -> None:
    node = schema_node(path)
    constraint = CHART_VALUE_CONSTRAINTS[path]
    published = {
        key: node.get(key)
        for key in (
            "type",
            "pattern",
            "maxLength",
            "enum",
            "minimum",
            "maximum",
            "maxItems",
        )
    }
    assert published == {
        "type": constraint.kind,
        "pattern": constraint.pattern,
        "maxLength": constraint.max_length,
        "enum": None if constraint.enum is None else list(constraint.enum),
        "minimum": constraint.minimum,
        "maximum": constraint.maximum,
        "maxItems": constraint.max_items,
    }
    # No keyword the renderer does not check applies to a value it writes. The one
    # exception is the secret list's item shape, which an empty list - the only
    # list the renderer writes - satisfies whatever it says.
    vacuous = {"items"} if path == "security.secretRefs" else set()
    assert set(node) - {"description", *published} == vacuous


def test_the_chart_identity_and_runtime_requests_are_the_charts() -> None:
    chart = load(CHART_DIR / "Chart.yaml")
    assert (chart["name"], chart["version"]) == (CHART_NAME, CHART_VERSION)
    requests = load(CHART_VALUES)["runtime"]["resources"]["requests"]
    assert dict(helm_values_module.CHART_RUNTIME_REQUESTS) == requests


def test_the_renderer_takes_todays_versions_and_the_synchronous_profile_only() -> None:
    assert HELM_VALUES_SUPPORT.contract_versions == frozenset(
        SUPPORTED_CONTRACT_VERSIONS
    )
    assert HELM_VALUES_SUPPORT.binding_versions == frozenset(SUPPORTED_BINDING_VERSIONS)
    assert HELM_VALUES_SUPPORT.platform_defaults_versions == frozenset({"v1alpha1"})
    assert HELM_VALUES_SUPPORT.profiles == frozenset({Profile.SYNCHRONOUS_LLM})
    assert renderer().support is HELM_VALUES_SUPPORT


def test_the_published_disposition_table_is_the_code() -> None:
    text = DOC.read_text(encoding="utf-8")
    section = text.split("## Where every value goes", 1)[1]
    rows = []
    for line in section.split("\n\n|", 1)[1].splitlines()[2:]:
        if not line.startswith("|"):
            break
        rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    assert [(row[0].strip("`"), row[1].strip("`"), row[2], row[3]) for row in rows] == [
        (
            name,
            entry.disposition.value,
            ", ".join(f"`{target}`" for target in entry.targets) or "-",
            entry.reason[0].upper() + entry.reason[1:],
        )
        for name, entry in HELM_VALUE_DISPOSITIONS.items()
    ]


def test_the_published_rule_table_names_the_renderers_rules_with_their_codes() -> None:
    text = DOC.read_text(encoding="utf-8")
    section = text.split("## What it refuses", 1)[1]
    rows = []
    for line in section.split("\n\n|", 1)[1].splitlines()[2:]:
        if not line.startswith("|"):
            break
        rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
    own = {
        row[0].strip("`"): (row[1].strip("`"), row[2].strip("`")) for row in rows[:3]
    }
    assert own == {
        key: (RENDER_RULES[key].category.value, RENDER_RULES[key].code)
        for key in RENDERER_RULES[:3]
    }


# --------------------------------------------------------------------------
# 4. The chart accepts the output
# --------------------------------------------------------------------------


def chart_validator() -> jsonschema.protocols.Validator:
    schema = json.loads(CHART_SCHEMA.read_text(encoding="utf-8"))
    validator_class = jsonschema.validators.validator_for(schema)
    validator_class.check_schema(schema)
    return validator_class(schema)


def test_the_generated_values_over_the_chart_defaults_satisfy_the_chart_schema() -> (
    None
):
    merged = deep_merge(load(CHART_VALUES), render().as_document())
    assert list(chart_validator().iter_errors(merged)) == []


def test_the_installable_values_satisfy_the_chart_schema() -> None:
    merged = deep_merge(load(CHART_VALUES), *admitted().documents())
    assert list(chart_validator().iter_errors(merged)) == []


def test_the_installable_values_are_the_v1_real_values_but_for_the_environment() -> (
    None
):
    """V1 compatibility at the values layer, without Helm.

    The generated file and the hand-written one, as admitted beside it, merge to
    exactly what the V1 real fixture merges to, except the environment label: V1's
    fixture labels the laptop run ``dev``, and the contract declares ``local``.
    """
    defaults_doc = load(CHART_VALUES)
    generated = deep_merge(defaults_doc, *admitted().documents())
    v1 = deep_merge(defaults_doc, load(REAL_VALUES))
    differing = dotted(
        {
            path
            for path in leaf_paths(v1) | leaf_paths(generated)
            if at(v1, path) != at(generated, path)
        }
    )
    assert differing == {"telemetry.deploymentEnvironment"}
    assert at(v1, "telemetry.deploymentEnvironment") == "dev"
    assert at(generated, "telemetry.deploymentEnvironment") == "local"


def helm_template(*values: Path, overrides: tuple[str, ...] = ()) -> bytes:
    """`helm template` over values files, with no shell and no cluster."""
    helm = shutil.which("helm")
    if helm is None:
        pytest.skip("helm is not on PATH; see CONTRIBUTING.md for the commands")
    argv = [
        helm,
        "template",
        "inferops",
        str(CHART_DIR),
        "--namespace",
        "inferops-platform",
    ]
    for path in values:
        argv.extend(["--values", str(path)])
    for override in overrides:
        argv.extend(["--set", override])
    result = subprocess.run(argv, capture_output=True, check=False, timeout=120)
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    return result.stdout.replace(b"\r\n", b"\n")


def test_helm_renders_the_generated_values_as_it_renders_v1_with_the_contracts_environment(
    tmp_path: Path,
) -> None:
    assert helm_template(*admitted_files(tmp_path)) == helm_template(
        REAL_VALUES, overrides=("telemetry.deploymentEnvironment=local",)
    )


def test_against_the_committed_v1_render_only_the_environment_and_its_checksums_move(
    tmp_path: Path,
) -> None:
    ours = helm_template(*admitted_files(tmp_path)).decode("utf-8").splitlines()
    v1 = REAL_RENDER.read_bytes().replace(b"\r\n", b"\n").decode("utf-8").splitlines()
    assert len(ours) == len(v1)
    moved = [
        (old.strip(), new.strip())
        for old, new in zip(v1, ours, strict=True)
        if old != new
    ]
    assert [pair for pair in moved if "configuration-checksum" not in pair[0]] == [
        (
            'INFEROPS_DEPLOYMENT_ENVIRONMENT: "dev"',
            'INFEROPS_DEPLOYMENT_ENVIRONMENT: "local"',
        ),
        ('replacement: "dev"', 'replacement: "local"'),
    ]
    assert sum(1 for pair in moved if "configuration-checksum" in pair[0]) == 3


# --------------------------------------------------------------------------
# 5. Every refusal has a case
# --------------------------------------------------------------------------


def _artifact(field: str, value: Any) -> Callable[[dict[str, Any]], None]:
    return lambda d: d["spec"]["synchronousLlm"]["modelArtifact"].__setitem__(
        field, value
    )


def _spec(block: str, field: str, value: Any) -> Callable[[dict[str, Any]], None]:
    return lambda d: d["spec"][block].__setitem__(field, value)


#: One contract per finding: the mutation, the rule, and the field it is refused at.
CASES: dict[str, tuple[Callable[[dict[str, Any]], None], str, str]] = {
    "replica range": (
        _spec("scaling", "maximumReplicas", 2),
        "render-capability-unsupported",
        "contract.spec.scaling.maximumReplicas",
    ),
    "accelerator type": (
        lambda d: d["spec"]["resources"]["accelerator"].__setitem__(
            "type", "nvidia-gpu"
        ),
        "render-capability-unsupported",
        "contract.spec.resources.accelerator.type",
    ),
    "accelerator count": (
        lambda d: d["spec"]["resources"]["accelerator"].__setitem__("count", 1),
        "render-capability-unsupported",
        "contract.spec.resources.accelerator.count",
    ),
    "runtime sizing": (
        _spec("model", "runtimeProfile", "throughput-oriented"),
        "render-capability-unsupported",
        "contract.spec.model.runtimeProfile",
    ),
    "telemetry capability": (
        lambda d: d["spec"]["integrations"]["telemetry"].__setitem__(
            "capabilityRef", "team-telemetry"
        ),
        "render-capability-unsupported",
        "contract.spec.integrations.telemetry.capabilityRef",
    ),
    "model access": (
        _spec(
            "integrations",
            "modelAccess",
            {"capabilityRef": "registry", "required": False},
        ),
        "render-capability-unsupported",
        "contract.spec.integrations.modelAccess.capabilityRef",
    ),
    "evaluation": (
        _spec(
            "integrations", "evaluation", {"capabilityRef": "evals", "required": True}
        ),
        "render-capability-unsupported",
        "contract.spec.integrations.evaluation.capabilityRef",
    ),
    "secret reference": (
        _spec(
            "security",
            "secretRefs",
            [
                {
                    "name": "model-registry-token",
                    "provider": "kubernetes-secret",
                    "reference": "inferops-serving/model-registry#token",
                    "owner": "team-platform-demo",
                    "rotation": "owner-managed",
                }
            ],
        ),
        "render-capability-unsupported",
        "contract.spec.security.secretRefs",
    ),
    "environment": (
        lambda d: d["spec"].__setitem__("environment", "staging"),
        "render-value-unsupported",
        "contract.spec.environment",
    ),
    "pre-release version": (
        lambda d: d["metadata"].__setitem__("version", "1.0.0-rc.1"),
        "render-value-unsupported",
        "contract.metadata.version",
    ),
    "cpu form": (
        _spec("resources", "cpu", "2k"),
        "render-value-unsupported",
        "contract.spec.resources.cpu",
    ),
    "memory form": (
        _spec("resources", "memory", "1Pi"),
        "render-value-unsupported",
        "contract.spec.resources.memory",
    ),
    "cpu below the request": (
        _spec("resources", "cpu", "500m"),
        "render-value-unsupported",
        "contract.spec.resources.cpu",
    ),
    "memory below the request": (
        _spec("resources", "memory", "2047Mi"),
        "render-value-unsupported",
        "contract.spec.resources.memory",
    ),
    "replica count": (
        lambda d: d["spec"].__setitem__(
            "scaling", {"minimumReplicas": 17, "maximumReplicas": 17}
        ),
        "render-value-unsupported",
        "contract.spec.scaling.minimumReplicas",
    ),
    "nested repository": (
        _artifact("repository", "Qwen/Qwen3/GGUF"),
        "render-value-unsupported",
        "contract.spec.synchronousLlm.modelArtifact.repository",
    ),
    "long file name": (
        _artifact("file", "a" * 249 + ".gguf"),
        "render-value-unsupported",
        "contract.spec.synchronousLlm.modelArtifact.file",
    ),
    "long revision": (
        _artifact("revision", "9" * 64),
        "render-value-unsupported",
        "contract.spec.synchronousLlm.modelArtifact.revision",
    ),
    "credential-shaped tenant": (
        _spec("attribution", "tenant", "glpat-platform"),
        "render-value-credential-shaped",
        "contract.spec.attribution.tenant",
    ),
    "credential-shaped file": (
        _artifact("file", "hf_weights.gguf"),
        "render-value-credential-shaped",
        "contract.spec.synchronousLlm.modelArtifact.file",
    ),
}


def mutated(case: str) -> WorkloadContract:
    return changed(CASES[case][0])


@pytest.mark.parametrize("case", list(CASES))
def test_each_case_is_refused_under_its_rule_at_its_field_and_nothing_else(
    case: str,
) -> None:
    _, rule, field = CASES[case]
    workload = mutated(case)
    refusal = refusal_of(workload)
    assert [(f.rule_id, f.field) for f in refusal.findings] == [(rule, field)]
    assert refusal.code == RENDER_RULES[rule].code
    assert refusal.category is RENDER_RULES[rule].category
    assert refusal.retryable is False


@pytest.mark.parametrize("case", list(CASES))
def test_no_refusal_quotes_the_value_it_refused(case: str) -> None:
    workload = mutated(case)
    refusal = refusal_of(workload)
    text = json.dumps(refusal.as_dict()) + str(refusal)
    before = contract().as_document()
    after = workload.as_document()
    for path in leaf_paths(after):
        try:
            old = at(before, path)
        except (KeyError, TypeError):
            old = None
        value = at(after, path)
        if value != old and isinstance(value, str) and len(value) > 3:
            assert value not in text, path


def test_every_case_passes_the_boundary_and_is_refused_by_the_renderer_alone() -> None:
    """Each case is an accepted input: the boundary builds a context for it."""
    for case in CASES:
        workload = mutated(case)
        context = build_render_context(
            validate_for_render(workload), defaults(), bindings_for(workload)
        )
        with pytest.raises(RenderRefused):
            renderer().render(context)


def test_an_over_long_runtime_repository_never_reaches_the_renderer() -> None:
    """A gap measured, not a check exercised: the matrix refuses it first.

    The chart's repository is shorter than the contract's image reference allows,
    and the renderer checks it. No accepted input reaches that check today: the
    compatibility matrix registers one runtime repository, and the boundary refuses
    every other as unregistered before the renderer is called.
    """
    long_reference = "ghcr.io/" + "a" * 250 + "@sha256:" + "0" * 64
    workload = changed(
        lambda d: d["spec"]["synchronousLlm"]["runtime"].__setitem__(
            "imageReference", long_reference
        )
    )
    assert len(long_reference.split("@")[0]) > 255
    assert refusal_of(workload).rule_ids() == ("runtime-unregistered",)


def test_a_credential_shaped_binding_value_is_refused_where_it_would_be_written() -> (
    None
):
    document = binding_document()
    document["spec"]["modelCache"]["claimName"] = "sk-model-cache"
    refusal = refusal_of(contract(), bindings=[parse_environment_binding(document)])
    assert [(f.rule_id, f.field) for f in refusal.findings] == [
        ("render-value-credential-shaped", "binding.spec.modelCache.claimName")
    ]


def test_a_credential_shaped_binding_value_that_is_not_written_is_not_refused() -> None:
    """The namespace is an install argument, not a value, so nothing writes it."""
    document = binding_document()
    document["spec"]["destination"]["namespace"] = "inferops-sk-live"
    assert render(bindings=[parse_environment_binding(document)]) == render()


def test_every_finding_is_reported_at_once_in_category_order() -> None:
    def everything(d: dict[str, Any]) -> None:
        for case in ("replica range", "accelerator type", "cpu below the request"):
            CASES[case][0](d)
        d["spec"]["attribution"]["tenant"] = "glpat-platform"

    refusal = refusal_of(changed(everything))
    assert refusal.rule_ids() == (
        "render-capability-unsupported",
        "render-value-unsupported",
        "render-capability-unsupported",
        "render-value-credential-shaped",
    )
    assert [f.field for f in refusal.findings] == [
        "contract.spec.resources.accelerator.type",
        "contract.spec.resources.cpu",
        "contract.spec.scaling.maximumReplicas",
        "contract.spec.attribution.tenant",
    ]
    assert refusal.code == CAPABILITY_UNAVAILABLE
    assert refusal.category is RefusalCategory.VALUE_UNSUPPORTED


def test_the_secret_reference_example_is_refused_rather_than_rendered() -> None:
    workload = contract("synchronous-llm-secret-refs")
    refusal = refusal_of(workload)
    assert ("render-capability-unsupported", "contract.spec.security.secretRefs") in [
        (f.rule_id, f.field) for f in refusal.findings
    ]
    assert "model-registry" not in str(refusal)


def test_a_mock_context_is_refused_by_the_renderer_itself() -> None:
    """``render_with`` refuses a mock first; a context built without it is refused too."""
    workload = contract("mock-llm-ci")
    with pytest.raises(RenderRefused) as through_boundary:
        render(workload)
    assert through_boundary.value.rule_ids() == ("render-profile-unsupported",)
    context = build_render_context(
        validate_for_render(workload), defaults(), bindings_for(workload)
    )
    with pytest.raises(RenderRefused) as direct:
        renderer().render(context)
    assert [(f.rule_id, f.field) for f in direct.value.findings] == [
        ("render-profile-unsupported", "contract.spec.profile")
    ]


def test_a_context_of_versions_the_renderer_does_not_take_is_refused(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The version checks ``render`` repeats, reached by narrowing the declaration."""
    narrowed = type(HELM_VALUES_SUPPORT)(
        contract_versions=frozenset({LATER_VERSION}),
        binding_versions=frozenset({LATER_VERSION}),
        platform_defaults_versions=HELM_VALUES_SUPPORT.platform_defaults_versions,
        profiles=HELM_VALUES_SUPPORT.profiles,
    )
    monkeypatch.setattr(helm_values_module, "HELM_VALUES_SUPPORT", narrowed)
    with pytest.raises(RenderRefused) as raised:
        renderer().render(reference_context())
    assert [(f.rule_id, f.field) for f in raised.value.findings] == [
        ("render-binding-version-unsupported", "binding.apiVersion"),
        ("render-contract-version-unsupported", "contract.apiVersion"),
    ]


def test_the_renderer_refuses_what_is_not_its_input() -> None:
    with pytest.raises(TypeError):
        HelmValuesRenderer("a" * 40)  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        renderer().render({"fields": {}})  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        manual_value_findings([("api", {})])  # type: ignore[arg-type]


def test_a_refusal_carries_the_request_context() -> None:
    context = build_render_context(
        validate_for_render(mutated("replica range")), defaults(), [binding()]
    )
    request = RequestContext()
    with pytest.raises(RenderRefused) as raised:
        renderer().render(context, request=request)
    assert all(finding.context is request for finding in raised.value.findings)


def test_render_with_attaches_the_callers_request_to_the_renderers_findings() -> None:
    """A request identifier supplied at the edge survives a refusal from the renderer."""
    request = RequestContext(request_id="req-render", correlation_id="corr-render")
    workload = mutated("replica range")
    with pytest.raises(RenderRefused) as raised:
        render_with(
            renderer(), workload, defaults(), bindings_for(workload), context=request
        )
    assert raised.value.rule_ids() == ("render-capability-unsupported",)
    assert all(finding.context == request for finding in raised.value.findings)
    assert raised.value.findings[0].as_dict()["requestId"] == "req-render"


def test_render_with_keeps_a_context_the_renderer_already_attached() -> None:
    """Only a finding with no request context is given the caller's."""

    class Attaching:
        revision = GitRevision(RENDERER_REVISION)
        support = HELM_VALUES_SUPPORT

        def render(self, context: RenderContext) -> GeneratedHelmValues:
            return renderer().render(context, request=RequestContext(request_id="own"))

    workload = mutated("replica range")
    with pytest.raises(RenderRefused) as raised:
        render_with(
            Attaching(),
            workload,
            defaults(),
            bindings_for(workload),
            context=RequestContext(request_id="edge"),
        )
    assert [f.context.request_id for f in raised.value.findings] == ["own"]


def test_the_renderers_rules_are_published_with_their_categories_and_codes() -> None:
    assert {
        key: (RENDER_RULES[key].category, RENDER_RULES[key].code)
        for key in RENDERER_RULES
    } == {
        "render-value-unsupported": (
            RefusalCategory.VALUE_UNSUPPORTED,
            CAPABILITY_UNAVAILABLE,
        ),
        "render-capability-unsupported": (
            RefusalCategory.VALUE_UNSUPPORTED,
            CAPABILITY_UNAVAILABLE,
        ),
        "render-value-credential-shaped": (
            RefusalCategory.SEMANTIC_INVALID,
            CONTRACT_INVALID,
        ),
        "render-manual-value-generated": (
            RefusalCategory.OWNERSHIP_CONFLICT,
            CONTRACT_INVALID,
        ),
    }
    reached = {CASES[case][1] for case in CASES} | {"render-manual-value-generated"}
    assert reached == set(RENDERER_RULES)


# --------------------------------------------------------------------------
# 6. Hand-written values cannot repeat contract intent
# --------------------------------------------------------------------------


def test_the_committed_hand_written_file_sets_no_generated_value() -> None:
    manual = load(MANUAL)
    assert manual_value_findings(manual) == []
    assert dotted(leaf_paths(manual)).isdisjoint(set(CHART_VALUE_CONSTRAINTS))


def test_every_supported_hand_written_file_in_the_repository_is_admitted() -> None:
    """Found by name, not listed: a new supported file is checked as soon as it exists."""
    found = supported_manual_values_files(REPO_ROOT)
    assert MANUAL in found
    assert unadmitted_manual_values(REPO_ROOT) == []


def test_a_new_supported_file_that_repeats_contract_intent_fails_the_search(
    tmp_path: Path,
) -> None:
    """What a contributor adding such a file would see: this suite fails, naming it."""
    nested = tmp_path / "deploy" / "values"
    nested.mkdir(parents=True)
    (nested / f"another{MANUAL_VALUES_SUFFIX}").write_text(
        "runtime:\n  replicaCount: 3\n  image:\n    pullPolicy: Always\n",
        encoding="utf-8",
    )
    (nested / f"fine{MANUAL_VALUES_SUFFIX}").write_text(
        "runtime:\n  image:\n    pullPolicy: Always\n", encoding="utf-8"
    )
    (nested / "unsupported.values.yaml").write_text(
        "runtime:\n  replicaCount: 3\n", encoding="utf-8"
    )
    cache = tmp_path / ".venv"
    cache.mkdir()
    (cache / f"ignored{MANUAL_VALUES_SUFFIX}").write_text(
        "profile: real\n", encoding="utf-8"
    )
    assert [path.name for path in supported_manual_values_files(tmp_path)] == [
        f"another{MANUAL_VALUES_SUFFIX}",
        f"fine{MANUAL_VALUES_SUFFIX}",
    ]
    assert unadmitted_manual_values(tmp_path) == [
        (
            f"deploy/values/another{MANUAL_VALUES_SUFFIX}",
            ["manualValues.runtime.replicaCount"],
        )
    ]


@pytest.mark.parametrize(
    ("manual", "refused"),
    [
        # 1. A generated scalar, set.
        ({"runtime": {"replicaCount": 3}}, ["manualValues.runtime.replicaCount"]),
        # 2. A child beneath a generated scalar.
        (
            {"model": {"revision": {"pinned": "main"}}},
            ["manualValues.model.revision"],
        ),
        # 3. A parent of generated values, replaced by a scalar, a list, or a null.
        ({"runtime": "none"}, ["manualValues.runtime"]),
        ({"ownership": ["a", "b"]}, ["manualValues.ownership"]),
        ({"model": {"artifact": None}}, ["manualValues.model.artifact"]),
        # 4. A generated value removed with a null.
        ({"telemetry": {"enabled": None}}, ["manualValues.telemetry.enabled"]),
        # Every finding at once, in path order.
        (
            {"profile": "real", "api": {"replicaCount": 2}},
            ["manualValues.api.replicaCount", "manualValues.profile"],
        ),
    ],
)
def test_admission_refuses_a_hand_written_file_that_sets_replaces_or_removes_a_generated_value(
    manual: dict[str, Any], refused: list[str]
) -> None:
    request = RequestContext(correlation_id="manual-values-admission")
    with pytest.raises(RenderRefused) as raised:
        admit_manual_values(render(), manual, context=request)
    findings = raised.value.findings
    assert [finding.field for finding in findings] == refused
    assert {finding.rule_id for finding in findings} == {
        "render-manual-value-generated"
    }
    assert all(finding.context == request for finding in findings)


@pytest.mark.parametrize(
    "manual",
    [
        # 5. A sibling of a generated value.
        {"runtime": {"image": {"pullPolicy": "Always"}}},
        {"model": {"artifact": {"sourceUrl": "https://example.invalid/m"}}},
        # 6. An empty mapping above a generated value merges nothing into it.
        {"runtime": {}},
        {"runtime": {"resources": {}}},
        {},
    ],
)
def test_admission_accepts_a_sibling_and_an_empty_mapping_above_a_generated_value(
    manual: dict[str, Any],
) -> None:
    pair = admit_manual_values(render(), manual)
    assert pair.documents() == (render().as_document(), manual)


def test_an_admission_refusal_names_the_path_and_never_the_value() -> None:
    """8. The value set at a generated path may be anything, a credential included."""
    leaked = "hf_" + "leakedvaluefromahandwrittenfile"
    with pytest.raises(RenderRefused) as raised:
        admit_manual_values(render(), {"model": {"identifier": leaked}})
    assert [finding.field for finding in raised.value.findings] == [
        "manualValues.model.identifier"
    ]
    assert leaked not in str(raised.value)
    assert leaked not in json.dumps(
        [finding.as_dict() for finding in raised.value.findings]
    )


class _ShiftingMapping(Mapping[str, Any]):
    """A mapping that answers the first reading of its items one way and later ones
    another: harmless when checked, overriding a generated value when read again."""

    def __init__(self) -> None:
        self.reads = 0

    def _current(self) -> dict[str, Any]:
        self.reads += 1
        if self.reads == 1:
            return {"runtime": {"image": {"pullPolicy": "Always"}}}
        return {"runtime": {"replicaCount": 3}}

    def __getitem__(self, key: str) -> Any:
        return self._current()[key]

    def __iter__(self) -> Any:
        return iter(self._current())

    def __len__(self) -> int:
        return 1

    def items(self) -> Any:
        return self._current().items()


def test_an_admitted_pair_holds_what_was_checked_and_cannot_be_built_around_it() -> (
    None
):
    manual: dict[str, Any] = {"runtime": {"image": {"pullPolicy": "Always"}}}
    pair = admit_manual_values(render(), manual)
    manual["runtime"]["replicaCount"] = 3
    assert pair.documents()[1] == {"runtime": {"image": {"pullPolicy": "Always"}}}
    with pytest.raises(TypeError):
        pair.manual["runtime"] = {}  # type: ignore[index]
    with pytest.raises(RenderRefused):
        AdmittedHelmValues(render(), {"runtime": {"replicaCount": 3}})
    with pytest.raises(TypeError):
        AdmittedHelmValues(render(), [("runtime", {})])  # type: ignore[arg-type]
    with pytest.raises(RenderRefused):
        AdmittedHelmValues(
            render(),
            MappingProxyType({"runtime": MappingProxyType({"replicaCount": 3})}),
        )
    with pytest.raises(TypeError):
        admit_manual_values(render().as_document(), {})  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        admit_manual_values(render(), [("api", {})])  # type: ignore[arg-type]


def test_a_pair_built_from_a_live_view_keeps_the_copy_it_checked() -> None:
    """The public constructor takes a copy: a proxy is a view, not a copy."""
    outer: dict[str, Any] = {}
    pair = AdmittedHelmValues(render(), MappingProxyType(outer))
    outer["runtime"] = {"replicaCount": 3}
    assert pair.documents()[1] == {}

    inner: dict[str, Any] = {"image": {"pullPolicy": "Always"}}
    nested = AdmittedHelmValues(render(), MappingProxyType({"runtime": inner}))
    inner["replicaCount"] = 3
    assert nested.documents()[1] == {"runtime": {"image": {"pullPolicy": "Always"}}}
    assert manual_value_findings(nested.manual) == []


@pytest.mark.parametrize(
    "build",
    [
        lambda manual: AdmittedHelmValues(render(), MappingProxyType(manual)),
        lambda manual: admit_manual_values(render(), manual),
    ],
    ids=["constructor", "admission"],
)
def test_a_document_that_changes_between_readings_is_read_once(
    build: Callable[[Mapping[str, Any]], AdmittedHelmValues],
) -> None:
    """Whatever was checked is what the pair holds, so a second reading cannot
    smuggle in an override."""
    pair = build(_ShiftingMapping())
    held = pair.documents()[1]
    assert held == {"runtime": {"image": {"pullPolicy": "Always"}}}
    assert manual_value_findings(pair.manual) == []


def test_a_key_beneath_a_generated_value_is_not_repeated_in_the_finding() -> None:
    """A key the file chose could itself be a credential; the finding names the
    generated value it lands on instead."""
    leaked = "hf_" + "akeychosenbythefilesauthor"
    with pytest.raises(RenderRefused) as raised:
        admit_manual_values(render(), {"model": {"identifier": {leaked: "x"}}})
    assert [finding.field for finding in raised.value.findings] == [
        "manualValues.model.identifier"
    ]
    assert leaked not in str(raised.value)
    assert leaked not in json.dumps(
        [finding.as_dict() for finding in raised.value.findings]
    )


def test_two_keys_beneath_one_generated_value_are_one_finding() -> None:
    findings = manual_value_findings({"runtime": {"replicaCount": {"a": 1, "b": 2}}})
    assert [finding.field for finding in findings] == [
        "manualValues.runtime.replicaCount"
    ]


def test_the_search_agrees_with_git_where_git_is_available() -> None:
    """Every tracked file with the suffix is one the search finds."""
    try:
        listed = subprocess.run(
            ["git", "-C", str(REPO_ROOT), "ls-files", "--", f"*{MANUAL_VALUES_SUFFIX}"],
            capture_output=True,
            check=True,
            timeout=60,
        ).stdout.decode("utf-8")
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git is not available to list tracked files")
    tracked = {REPO_ROOT / line for line in listed.splitlines() if line}
    assert tracked, "git lists no supported hand-written values file"
    assert tracked <= set(supported_manual_values_files(REPO_ROOT))


def test_a_directory_named_like_a_cache_below_the_root_is_still_searched(
    tmp_path: Path,
) -> None:
    deep = tmp_path / "deploy" / "dist"
    deep.mkdir(parents=True)
    (deep / f"x{MANUAL_VALUES_SUFFIX}").write_text("profile: real\n", encoding="utf-8")
    top = tmp_path / "dist"
    top.mkdir()
    (top / f"y{MANUAL_VALUES_SUFFIX}").write_text("profile: real\n", encoding="utf-8")
    assert unadmitted_manual_values(tmp_path) == [
        (f"deploy/dist/x{MANUAL_VALUES_SUFFIX}", ["manualValues.profile"])
    ]


@pytest.mark.parametrize("path", sorted(CHART_VALUE_CONSTRAINTS))
def test_setting_any_generated_value_by_hand_is_refused(path: str) -> None:
    manual = load(MANUAL)
    *parents, last = path.split(".")
    node = manual
    for part in parents:
        node = node.setdefault(part, {})
    node[last] = "x"
    findings = manual_value_findings(manual)
    assert [(f.rule_id, f.field) for f in findings] == [
        ("render-manual-value-generated", f"manualValues.{path}")
    ]


@pytest.mark.parametrize(
    ("manual", "refused"),
    [
        ({"model": {"artifact": None}}, ["manualValues.model.artifact"]),
        ({"runtime": {"resources": "none"}}, ["manualValues.runtime.resources"]),
        ({"profile": {"name": "real"}}, ["manualValues.profile"]),
        ({"profile": {}}, ["manualValues.profile"]),
        ({"security": {"secretRefs": []}}, ["manualValues.security.secretRefs"]),
        ({"runtime": {"resources": {}}}, []),
        ({"model": {"artifact": {"sourceUrl": "https://example.invalid/m"}}}, []),
        ({"runtime": {"resources": {"requests": {"cpu": "2"}}}}, []),
        ({"api": {"image": {"digest": "sha256:" + "0" * 64}}}, []),
    ],
)
def test_replacing_or_removing_a_generated_value_is_refused_and_a_sibling_is_not(
    manual: dict[str, Any], refused: list[str]
) -> None:
    assert [f.field for f in manual_value_findings(manual)] == refused


def test_a_manual_finding_names_the_path_and_never_the_value() -> None:
    findings = manual_value_findings({"ownership": {"tenant": "ghp_leaked"}})
    assert len(findings) == 1
    assert "ghp_leaked" not in json.dumps(findings[0].as_dict())


# --------------------------------------------------------------------------
# 7. One canonical YAML form
# --------------------------------------------------------------------------


AWKWARD_STRINGS = [
    "",
    "yes",
    "no",
    "on",
    "off",
    "null",
    "~",
    "true",
    "1e3",
    "0x1F",
    "0o17",
    "2026-09-30",
    "12:30:00",
    "- item",
    ": colon",
    "# hash",
    "'single'",
    '"double"',
    "back\\slash",
    " leading",
    "trailing ",
    "&anchor",
    "*alias",
    "!tag",
    "{a: 1}",
    "[1, 2]",
    "%directive",
    "@at",
    "`tick`",
]


def test_awkward_strings_round_trip_as_strings() -> None:
    document = {
        "values": {f"k{index}": text for index, text in enumerate(AWKWARD_STRINGS)}
    }
    assert yaml.safe_load(canonical_yaml(document)) == document


def test_the_form_is_sorted_quoted_and_independent_of_insertion_order() -> None:
    first = canonical_yaml({"b": {"q": 1, "p": "2"}, "a": [], "c": {}, "d": True})
    second = canonical_yaml({"d": True, "c": {}, "a": [], "b": {"p": "2", "q": 1}})
    assert first == second == 'a: []\nb:\n  p: "2"\n  q: 1\nc: {}\nd: true\n'


def test_a_list_of_mappings_is_written_in_block_style_and_round_trips() -> None:
    document = {
        "security": {
            "secretRefs": [
                {"name": "TOKEN", "secretName": "registry", "key": "token"},
                {},
                {"name": "OTHER", "secretName": "other", "key": "k"},
            ],
            "names": ["a", "b"],
        }
    }
    text = canonical_yaml(document)
    assert text == (
        "security:\n"
        "  names:\n"
        '  - "a"\n'
        '  - "b"\n'
        "  secretRefs:\n"
        '  - key: "token"\n'
        '    name: "TOKEN"\n'
        '    secretName: "registry"\n'
        "  - {}\n"
        '  - key: "k"\n'
        '    name: "OTHER"\n'
        '    secretName: "other"\n'
    )
    assert yaml.safe_load(text) == document


def test_a_header_is_written_as_comments_and_ignored_by_a_reader() -> None:
    text = canonical_yaml({"a": 1}, header=("first", "", "third"))
    assert text == "# first\n#\n# third\na: 1\n"
    assert yaml.safe_load(text) == {"a": 1}
    assert canonical_yaml({}) == "{}\n"


@pytest.mark.parametrize(
    ("document", "location"),
    [
        ({"a": 1.5}, "$.a"),
        ({"a": None}, "$.a"),
        ({"a": "café"}, "$.a"),
        ({"a": "line\nbreak"}, "$.a"),
        ({"a": "tab\there"}, "$.a"),
        ({"a": 2**53}, "$.a"),
        ({"a": [[1]]}, "$.a[0]"),
        ({"a": [{"b": 1.0}]}, "$.a[0].b"),
        ({"on": 1}, "$.on"),
        ({"Yes": 1}, "$.Yes"),
        ({"with-dash": 1}, "$.with-dash"),
        ({"1a": 1}, "$.1a"),
        ({"a": b"bytes"}, "$.a"),
    ],
)
def test_what_has_no_single_spelling_is_refused_at_its_location(
    document: dict[str, Any], location: str
) -> None:
    with pytest.raises(ValuesFormError) as raised:
        canonical_yaml(document)
    assert raised.value.location == location


def test_a_refused_value_is_never_quoted_and_a_bad_header_or_top_level_is_refused() -> (
    None
):
    with pytest.raises(ValuesFormError) as raised:
        canonical_yaml({"a": "sécret"})
    assert "sécret" not in str(raised.value)
    with pytest.raises(ValuesFormError):
        canonical_yaml({"a": 1}, header=("bad\nline",))
    with pytest.raises(TypeError):
        canonical_yaml(["a"])  # type: ignore[arg-type]
    with pytest.raises(ValuesFormError):
        canonical_yaml({1: "a"})  # type: ignore[dict-item]
