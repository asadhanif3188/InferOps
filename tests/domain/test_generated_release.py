"""The generated release: values and the RenderedWorkloadRelease naming them, on disk.

Every check reads files from this repository and writes only under pytest's
temporary directory. No network, no cluster, no clock, and no randomness; ``helm``
is run, with no shell and no cluster, only by the test that says so, and it skips
when it is not on PATH.

Eight things are asserted:

1. **Golden output.** The reference workload writes the committed golden values
   file and the committed golden release byte for byte, and nothing else.
2. **Every digest is the rule's.** The source digests are the documents'; the
   values digest the release records is the SHA-256 of the values file's bytes;
   the release identifier is derived; the written release is one the published
   validator and the platform domain accept, and verifies against its sources.
3. **Deterministic, into clean directories.** Two generations written to two clean
   directories are the same bytes - whatever order the bindings arrive in, under
   two hash seeds in two interpreters, and with every clock, random source, and
   environment read patched to fail.
4. **Every change moves exactly what it owns.** A contract, binding, defaults, or
   revision change moves the values and the release fields it should, and nothing
   else - including the changes that move no chart value. Defaults content changed
   under a falsely retained revision is measured: the values digest moves and the
   release identifier does not.
5. **Refused means nothing to write.** A refused render or a refused release
   returns nothing, and the request context survives.
6. **The bounded secret property.** Each file holds exactly the fields its
   published table names; content no row names reaches neither; no string is
   credential-shaped, and one that would be is refused without being quoted; the
   golden files are not exempt from secret scanning. A secret written as an
   ordinary lowercase name passes, and the suite says so rather than claiming
   otherwise.
7. **All or nothing on disk.** The writer writes both files or neither, never into
   a directory that exists, and leaves a recoverable, named staging directory when
   it cannot clean up.
8. **The pages say what the code does.** File names, headers, and the decided
   digest rule are the code's.
"""

from __future__ import annotations

import hashlib
import json
import os
import random
import re
import secrets
import shutil
import subprocess
import sys
import time
import tomllib
import uuid
from collections.abc import Callable, Iterator, Mapping
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import yaml

from inferops.domain import RequestContext
from inferops.domain.environment import EnvironmentBinding, parse_environment_binding
from inferops.domain.release import (
    GitRevision,
    HelmValuesReference,
    ReleaseOutput,
    Sha256Hex,
    ValuesFileName,
    binding_digest,
    canonical_release,
    check_rendered_workload_release,
    contract_digest,
    derive_release_id,
    is_credential_shaped,
    output_digest,
    parse_rendered_workload_release,
    verify_release_sources,
)
from inferops.domain.render import (
    CHART_VALUE_CONSTRAINTS,
    RELEASE_FILE_NAME,
    RELEASE_HEADER,
    RELEASE_PROVENANCE,
    STAGING_SUFFIX,
    VALUES_FILE_NAME,
    ApiDefaults,
    ApiRolloutDefaults,
    GeneratedRelease,
    HelmValuesRenderer,
    PlatformDefaults,
    ReleaseNotRecordedError,
    RenderRefused,
    RuntimeDefaults,
    RuntimeRolloutDefaults,
    admit_manual_values,
    generate_release,
    release_text,
    staging_directory,
    values_text,
    write_release,
)
from inferops.domain.render import writing as writing_module
from inferops.domain.render.helm_values import VALUES_HEADER
from inferops.domain.workload import (
    CompatibilityMatrixLoader,
    DnsLabel,
    WorkloadContract,
    parse_workload_contract,
    set_matrix_loader,
)
from tools.contract_validation import rendered_workload_release as release_validator

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
CHART_DIR = REPO_ROOT / "charts" / "inferops-llm"
CHART_VALUES = CHART_DIR / "values.yaml"
REAL_VALUES = CHART_DIR / "ci" / "real-values.yaml"
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
GOLDEN_DIRECTORY = FIXTURES / "support-assistant-local-kind"
GOLDEN_VALUES = GOLDEN_DIRECTORY / "values.generated.yaml"
GOLDEN_RELEASE = GOLDEN_DIRECTORY / "rendered-workload-release.yaml"
MANUAL = FIXTURES / "support-assistant-local.manual-values.yaml"
RENDERER_DOC = REPO_ROOT / "docs" / "domain" / "helm-values-renderer.md"
RELEASE_DOC = REPO_ROOT / "docs" / "contracts" / "rendered-workload-release.md"
WRITING_PATH = REPO_ROOT / "src" / "inferops" / "domain" / "render" / "writing.py"
GITLEAKS_CONFIG = REPO_ROOT / ".gitleaks.toml"

DEFAULTS_REVISION = "b" * 40
RENDERER_REVISION = "a" * 40

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


def changed_contract(mutate: Callable[[dict[str, Any]], None]) -> WorkloadContract:
    document = contract_document()
    mutate(document)
    return parse_workload_contract(document)


def binding_document(name: str = "local-kind") -> dict[str, Any]:
    document: dict[str, Any] = load(BINDING_VALID_DIR / f"{name}.yaml")
    return document


def binding(name: str = "local-kind") -> EnvironmentBinding:
    return parse_environment_binding(binding_document(name))


def changed_binding(mutate: Callable[[dict[str, Any]], None]) -> EnvironmentBinding:
    document = binding_document()
    mutate(document)
    return parse_environment_binding(document)


def defaults(revision: str = DEFAULTS_REVISION, **overrides: int) -> PlatformDefaults:
    """The chart's own platform defaults, read at a placeholder revision."""
    chart = load(CHART_VALUES)["api"]
    runtime_rollout = load(CHART_VALUES)["runtime"]["rollout"]
    runtime = RuntimeDefaults(
        RuntimeRolloutDefaults(
            max_unavailable=overrides.pop(
                "runtime_max_unavailable", runtime_rollout["maxUnavailable"]
            ),
            max_surge=overrides.pop("runtime_max_surge", runtime_rollout["maxSurge"]),
        )
    )
    rollout = ApiRolloutDefaults(
        max_unavailable=overrides.pop(
            "max_unavailable", chart["rollout"]["maxUnavailable"]
        ),
        max_surge=overrides.pop("max_surge", chart["rollout"]["maxSurge"]),
    )
    settings = {
        "request_timeout_ms": chart["requestTimeoutMs"],
        "drain_timeout_ms": chart["drainTimeoutMs"],
        "max_output_tokens": chart["maxOutputTokens"],
        "rollout": rollout,
        **overrides,
    }
    return PlatformDefaults(
        "v1alpha1", GitRevision(revision), ApiDefaults(**settings), runtime
    )


def renderer(revision: str = RENDERER_REVISION) -> HelmValuesRenderer:
    return HelmValuesRenderer(GitRevision(revision))


def generate(
    workload: WorkloadContract | None = None,
    *,
    bindings: list[EnvironmentBinding] | None = None,
    binding_name: str | None = None,
    platform_defaults: PlatformDefaults | None = None,
    at_revision: str = RENDERER_REVISION,
    context: RequestContext | None = None,
) -> GeneratedRelease:
    return generate_release(
        renderer(at_revision),
        contract() if workload is None else workload,
        defaults() if platform_defaults is None else platform_defaults,
        [binding()] if bindings is None else bindings,
        binding_name=None if binding_name is None else DnsLabel(binding_name),
        **({} if context is None else {"context": context}),
    )


def written(directory: Path) -> dict[str, bytes]:
    """Every file under ``directory``, by its relative path, with its bytes."""
    return {
        path.relative_to(directory).as_posix(): path.read_bytes()
        for path in sorted(directory.rglob("*"))
        if path.is_file()
    }


def leaves(document: Mapping[str, Any], prefix: str = "") -> dict[str, Any]:
    """Every leaf of a document, by dotted path. No key here holds a dot."""
    found: dict[str, Any] = {}
    for key, value in document.items():
        path = f"{prefix}{key}"
        if isinstance(value, Mapping) and value:
            found |= leaves(value, f"{path}.")
        else:
            found[path] = value
    return found


def moved(before: Mapping[str, Any], after: Mapping[str, Any]) -> set[str]:
    old, new = leaves(before), leaves(after)
    assert set(old) == set(new)
    return {path for path in old if old[path] != new[path]}


def strings(document: Any) -> Iterator[str]:
    if isinstance(document, Mapping):
        for key, value in document.items():
            yield str(key)
            yield from strings(value)
    elif isinstance(document, list):
        for item in document:
            yield from strings(item)
    elif isinstance(document, str):
        yield document


# --------------------------------------------------------------------------
# 1. Golden output
# --------------------------------------------------------------------------


def test_the_reference_workload_writes_the_two_golden_files_and_nothing_else(
    tmp_path: Path,
) -> None:
    out = write_release(generate(), tmp_path / "release")
    assert out == tmp_path / "release"
    assert written(out) == {
        "values.generated.yaml": GOLDEN_VALUES.read_bytes(),
        "rendered-workload-release.yaml": GOLDEN_RELEASE.read_bytes(),
    }
    assert sorted(path.name for path in tmp_path.iterdir()) == ["release"]


def test_both_golden_files_are_lf_only_ascii_and_end_in_one_newline() -> None:
    for path in (GOLDEN_VALUES, GOLDEN_RELEASE):
        data = path.read_bytes()
        assert b"\r" not in data, path.name
        assert data.isascii(), path.name
        assert data.endswith(b"\n") and not data.endswith(b"\n\n"), path.name


def test_the_golden_release_holds_the_placeholder_revisions_the_suite_states() -> None:
    """The two revisions are this suite's, not commits: the golden file is a test
    render. Its three digests are computed, and the next section holds them."""
    document = load(GOLDEN_RELEASE)
    assert document["source"]["renderer"]["revision"] == RENDERER_REVISION
    assert document["source"]["platformDefaults"]["revision"] == DEFAULTS_REVISION


def test_the_second_local_binding_writes_its_replica_count_and_another_release() -> (
    None
):
    """The two local bindings differ in one rendered fact, the API replica count.

    So the values differ in that one value, and the release records another values
    digest beside the binding's own name and digest."""
    kind = generate()
    desktop = generate(bindings=[binding("local-docker-desktop")])
    assert moved(
        yaml.safe_load(kind.values_bytes), yaml.safe_load(desktop.values_bytes)
    ) == {"api.replicaCount"}
    assert yaml.safe_load(kind.values_bytes)["api"]["replicaCount"] == 1
    assert yaml.safe_load(desktop.values_bytes)["api"]["replicaCount"] == 2
    assert desktop.values_sha256 != kind.values_sha256
    assert moved(kind.release.as_document(), desktop.release.as_document()) == {
        "metadata.releaseId",
        "output.helmValues.sha256",
        "source.environmentBinding.name",
        "source.environmentBinding.sha256",
    }
    assert desktop.release_sha256 != kind.release_sha256


# --------------------------------------------------------------------------
# 2. Every digest is the rule's
# --------------------------------------------------------------------------


def test_the_recorded_values_digest_is_the_sha256_of_the_written_file(
    tmp_path: Path,
) -> None:
    generated = generate()
    out = write_release(generated, tmp_path / "release")
    on_disk = (out / str(VALUES_FILE_NAME)).read_bytes()
    recorded = load(out / RELEASE_FILE_NAME)["output"]["helmValues"]
    assert recorded["path"] == "values.generated.yaml"
    assert recorded["sha256"] == hashlib.sha256(on_disk).hexdigest()
    assert recorded["sha256"] == str(generated.values_sha256)


def test_the_release_digest_is_the_sha256_of_the_written_release(
    tmp_path: Path,
) -> None:
    generated = generate()
    out = write_release(generated, tmp_path / "release")
    on_disk = (out / RELEASE_FILE_NAME).read_bytes()
    assert str(generated.release_sha256) == hashlib.sha256(on_disk).hexdigest()
    assert (
        str(generated.release_sha256)
        == hashlib.sha256(GOLDEN_RELEASE.read_bytes()).hexdigest()
    )


def test_the_release_digest_is_not_the_canonical_json_digest() -> None:
    """Two digests of a release exist and they differ, so they are named apart:
    the file's, which a release generation reports, and its JSON value's, which
    ``canonical_release`` gives for comparing two releases as documents."""
    generated = generate()
    value_digest = hashlib.sha256(canonical_release(generated.release)).hexdigest()
    assert str(generated.release_sha256) != value_digest


def test_the_source_digests_and_identifier_are_the_release_domains_own() -> None:
    generated = generate()
    source = generated.release.source
    assert source.contract.sha256 == contract_digest(contract())
    assert source.environment_binding.sha256 == binding_digest(binding())
    assert str(source.renderer.revision) == RENDERER_REVISION
    assert str(source.platform_defaults.revision) == DEFAULTS_REVISION
    metadata = generated.release.metadata
    assert metadata.release_id == derive_release_id(
        metadata.workload_id, metadata.workload_version, source
    )


def test_the_written_release_is_accepted_by_the_validator_and_the_domain(
    tmp_path: Path,
) -> None:
    generated = generate()
    out = write_release(generated, tmp_path / "release")
    document = load(out / RELEASE_FILE_NAME)
    assert release_validator.validate(document) == []
    parsed = parse_rendered_workload_release(document)
    assert canonical_release(parsed) == canonical_release(generated.release)
    assert check_rendered_workload_release(parsed) == []
    assert verify_release_sources(parsed, contract(), binding()) == []


def test_the_written_values_parse_to_the_rendered_values(tmp_path: Path) -> None:
    generated = generate()
    out = write_release(generated, tmp_path / "release")
    assert load(out / str(VALUES_FILE_NAME)) == generated.values.as_document()


def test_output_digest_hashes_bytes_and_refuses_text() -> None:
    assert str(output_digest(b"")) == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )
    assert output_digest(b"a\n") != output_digest(b"a\r\n")
    with pytest.raises(TypeError):
        output_digest("a\n")  # type: ignore[arg-type]


def test_a_release_naming_other_values_cannot_be_held_with_these_bytes() -> None:
    """A GeneratedRelease is checked when it is made, whoever makes it."""
    generated = generate()
    other_digest = HelmValuesReference(VALUES_FILE_NAME, Sha256Hex("c" * 64))
    other_name = HelmValuesReference(
        ValuesFileName("other.yaml"), generated.values_sha256
    )
    for reference in (other_digest, other_name):
        release = replace(generated.release, output=ReleaseOutput(reference))
        with pytest.raises(ValueError):
            GeneratedRelease(
                release, generated.values, generated.values_bytes, release_text(release)
            )
    with pytest.raises(ValueError):
        replace(generated, values_bytes=generated.values_bytes + b"# edited\n")
    with pytest.raises(ValueError):
        replace(
            generated, release_bytes=generated.release_bytes.replace(b"\n", b"\r\n")
        )


def test_a_generated_release_refuses_bytes_that_could_change_after_the_check() -> None:
    """A bytearray equal to the canonical bytes passes an equality check and can be
    edited afterwards, so only immutable bytes are held."""
    generated = generate()
    with pytest.raises(TypeError):
        replace(generated, values_bytes=bytearray(generated.values_bytes))  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        replace(generated, release_bytes=bytearray(generated.release_bytes))  # type: ignore[arg-type]


# --------------------------------------------------------------------------
# 3. Deterministic, into clean directories
# --------------------------------------------------------------------------


def test_two_generations_into_two_clean_directories_are_the_same_bytes(
    tmp_path: Path,
) -> None:
    first = write_release(generate(), tmp_path / "first")
    second = write_release(generate(), tmp_path / "second")
    assert written(first) == written(second)


def test_the_binding_order_moves_nothing() -> None:
    forward = [binding("local-kind"), binding("local-docker-desktop")]
    first = generate(bindings=forward, binding_name="local-kind")
    second = generate(bindings=list(reversed(forward)), binding_name="local-kind")
    assert first.files() == second.files()
    assert first == second


def test_generating_and_writing_read_no_clock_no_random_source_and_no_environment(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def forbidden(*_args: Any, **_kwargs: Any) -> Any:
        raise AssertionError("generation consulted a clock, a random source, or os")

    workload, platform, bound = contract(), defaults(), [binding()]
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
    generated = generate_release(renderer(), workload, platform, bound)
    out = write_release(generated, tmp_path / "release")
    monkeypatch.undo()
    assert written(out)[RELEASE_FILE_NAME] == GOLDEN_RELEASE.read_bytes()


WRITE_PROGRAM = """
import sys
sys.path[:0] = [{root!r}, {src!r}]
import tests.domain.test_generated_release as suite
from inferops.domain.render import write_release
write_release(suite.generate(), sys.argv[1])
"""


def test_two_interpreters_under_two_hash_seeds_write_the_same_directory(
    tmp_path: Path,
) -> None:
    program = WRITE_PROGRAM.format(root=str(REPO_ROOT), src=str(REPO_ROOT / "src"))
    outputs = []
    for seed in ("0", "4242"):
        out = tmp_path / f"seed-{seed}"
        subprocess.run(
            [sys.executable, "-c", program, str(out)],
            capture_output=True,
            check=True,
            cwd=REPO_ROOT,
            env={**os.environ, "PYTHONHASHSEED": seed},
            timeout=120,
        )
        outputs.append(written(out))
    assert (
        outputs[0]
        == outputs[1]
        == {
            "values.generated.yaml": GOLDEN_VALUES.read_bytes(),
            "rendered-workload-release.yaml": GOLDEN_RELEASE.read_bytes(),
        }
    )


def test_neither_file_holds_a_timestamp_or_a_random_identifier() -> None:
    for data in generate().files():
        text = data[1].decode("ascii")
        assert re.search(r"\d{4}-\d{2}-\d{2}|\d{2}:\d{2}:\d{2}|GMT", text) is None
        assert (
            re.search(
                r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", text
            )
            is None
        )


# --------------------------------------------------------------------------
# 4. Every change moves exactly what it owns
# --------------------------------------------------------------------------


def _scaled(count: int) -> Callable[[dict[str, Any]], None]:
    def mutate(document: dict[str, Any]) -> None:
        document["spec"]["scaling"] = {
            "minimumReplicas": count,
            "maximumReplicas": count,
        }

    return mutate


def _set(*path_and_value: Any) -> Callable[[dict[str, Any]], None]:
    *path, value = path_and_value

    def mutate(document: dict[str, Any]) -> None:
        node = document
        for part in path[:-1]:
            node = node[part]
        node[path[-1]] = value

    return mutate


_CONTRACT = {"metadata.releaseId", "source.contract.sha256"}
_BINDING = {"metadata.releaseId", "source.environmentBinding.sha256"}
_VALUES = {"output.helmValues.sha256"}

#: One change at a time: what it is, the inputs after it, the generated values it
#: moves, and the release fields it moves.
MUTATIONS: dict[str, tuple[Callable[[], GeneratedRelease], set[str], set[str]]] = {
    "contract replica count, a claim-relevant intent": (
        lambda: generate(changed_contract(_scaled(2))),
        {"runtime.replicaCount"},
        _CONTRACT | _VALUES,
    ),
    "contract memory": (
        lambda: generate(changed_contract(_set("spec", "resources", "memory", "4Gi"))),
        {"runtime.resources.limits.memory"},
        _CONTRACT | _VALUES,
    ),
    "contract description, which no chart value carries": (
        lambda: generate(
            changed_contract(_set("metadata", "description", "Another description."))
        ),
        set(),
        _CONTRACT,
    ),
    "contract runbook reference, which no chart value carries": (
        lambda: generate(
            changed_contract(
                _set("spec", "evidence", "runbookRef", "docs/serving/README.md")
            )
        ),
        set(),
        _CONTRACT,
    ),
    "binding model cache claim": (
        lambda: generate(
            bindings=[
                changed_binding(
                    _set("spec", "modelCache", "claimName", "another-cache")
                )
            ]
        ),
        {"model.cache.claimName"},
        _BINDING | _VALUES,
    ),
    "binding GitOps destination, which no chart value carries": (
        lambda: generate(
            bindings=[
                changed_binding(
                    _set("spec", "gitops", "destinationPath", "gitops/elsewhere")
                )
            ]
        ),
        set(),
        _BINDING,
    ),
    "platform defaults revision alone": (
        lambda: generate(platform_defaults=defaults("c" * 40)),
        set(),
        {"metadata.releaseId", "source.platformDefaults.revision"},
    ),
    "platform defaults and their revision": (
        lambda: generate(platform_defaults=defaults("c" * 40, max_output_tokens=256)),
        {"api.maxOutputTokens"},
        {"metadata.releaseId", "source.platformDefaults.revision"} | _VALUES,
    ),
    "renderer revision": (
        lambda: generate(at_revision="d" * 40),
        set(),
        {"metadata.releaseId", "source.renderer.revision"},
    ),
}


@pytest.mark.parametrize("case", list(MUTATIONS))
def test_one_change_moves_exactly_its_values_and_its_release_fields(
    case: str,
) -> None:
    make, values_moved, release_moved = MUTATIONS[case]
    before, after = generate(), make()
    assert moved(before.values.as_document(), after.values.as_document()) == (
        values_moved
    )
    assert (before.values_bytes == after.values_bytes) is (not values_moved)
    assert (
        moved(before.release.as_document(), after.release.as_document())
        == release_moved
    )
    assert after.release_sha256 != before.release_sha256


def test_defaults_content_changed_under_a_falsely_retained_revision_moves_the_values_digest_and_not_the_release_id() -> (
    None
):
    """A coverage limitation, measured rather than hidden.

    The caller supplies the platform defaults and, separately, the revision they
    are said to come from, and nothing reconstructs the defaults from that
    revision. So changing the defaults' content while stating the same revision
    renders different values, records a different values digest, and records the
    same release identifier: the release records the asserted revision, and does
    not prove the defaults were the ones at it. Do not make this assert equality;
    it changes when the defaults are read from a committed source bound to the
    revision, and not before.
    """
    before = generate()
    after = generate(platform_defaults=defaults(max_output_tokens=256))
    assert after.values_bytes != before.values_bytes
    assert after.values_sha256 != before.values_sha256
    assert moved(before.release.as_document(), after.release.as_document()) == (_VALUES)
    assert (
        after.release.source.platform_defaults.revision
        == before.release.source.platform_defaults.revision
        == GitRevision(DEFAULTS_REVISION)
    )
    assert after.release.metadata.release_id == before.release.metadata.release_id


def test_a_change_after_recording_is_refused_against_the_changed_source() -> None:
    """A release written before a contract change does not verify against it."""
    release = generate().release
    after = changed_contract(_scaled(2))
    refusals = verify_release_sources(release, after, binding())
    assert [refusal.rule_id for refusal in refusals] == [
        "release-contract-digest-mismatch"
    ]


# --------------------------------------------------------------------------
# 5. Refused means nothing to write
# --------------------------------------------------------------------------


def test_a_declared_secret_reference_is_refused_and_returns_nothing_to_write() -> None:
    """The secret-reference example's references, on the reference contract: the
    example itself serves ``dev``, so with a local binding it would be refused for
    the binding instead and never reach the renderer."""
    references = contract_document("synchronous-llm-secret-refs")["spec"]["security"][
        "secretRefs"
    ]
    with pytest.raises(RenderRefused) as raised:
        generate(changed_contract(_set("spec", "security", "secretRefs", references)))
    assert {finding.rule_id for finding in raised.value.findings} == {
        "render-capability-unsupported"
    }
    assert {finding.field for finding in raised.value.findings} == {
        "contract.spec.security.secretRefs"
    }


def test_a_release_refused_after_the_values_rendered_returns_nothing_to_write() -> None:
    """A binding name no chart value carries can still not be recorded."""
    named = changed_binding(_set("metadata", "name", "sk-local-kind"))
    with pytest.raises(ReleaseNotRecordedError) as raised:
        generate(bindings=[named])
    assert [refusal.as_dict().get("ruleId") for refusal in raised.value.refusals] == [
        "release-value-credential-shaped"
    ]
    assert "sk-local-kind" not in str(raised.value)
    assert "sk-local-kind" not in json.dumps(raised.value.as_dict())


def test_the_renderers_refusal_carries_the_callers_request_context() -> None:
    request = RequestContext(correlation_id="generation-request")
    with pytest.raises(RenderRefused) as raised:
        generate(
            changed_contract(_set("spec", "scaling", "maximumReplicas", 2)),
            context=request,
        )
    assert raised.value.findings
    assert all(finding.context == request for finding in raised.value.findings)


def test_generation_refuses_what_is_not_its_input() -> None:
    with pytest.raises(TypeError):
        generate_release(
            object(),  # type: ignore[arg-type]
            contract(),
            defaults(),
            [binding()],
        )
    with pytest.raises(TypeError):
        generate_release(
            renderer(),
            contract_document(),  # type: ignore[arg-type]
            defaults(),
            [binding()],
        )


# --------------------------------------------------------------------------
# 6. No secret in a generated file
# --------------------------------------------------------------------------


@pytest.mark.parametrize("name", ["local-kind", "local-docker-desktop"])
def test_no_string_in_either_file_is_credential_shaped(name: str) -> None:
    generated = generate(bindings=[binding(name)])
    for file_name, data in generated.files():
        found = list(strings(yaml.safe_load(data.decode("ascii"))))
        assert found, file_name
        assert [value for value in found if is_credential_shaped(value)] == []


def test_the_written_values_carry_no_secret_reference() -> None:
    assert generate().values.as_document()["security"]["secretRefs"] == []


def test_each_file_holds_exactly_the_fields_its_published_table_names() -> None:
    """Every string a generated file carries comes from a row the platform publishes:
    a chart value the renderer's disposition table renders, or a release field the
    provenance table classifies. Nothing else has a place to land."""
    generated = generate()
    assert set(leaves(generated.values.as_document())) == set(CHART_VALUE_CONSTRAINTS)
    assert set(leaves(generated.release.as_document())) == {
        row.field for row in RELEASE_PROVENANCE
    }


def test_input_content_no_row_names_reaches_neither_file() -> None:
    """Free text, annotations, owners and placement no row renders, as real inputs."""
    document = contract_document()
    document["metadata"]["description"] = "Free text zqmarkdesc for a reader."
    document["metadata"]["annotations"] = {"inferops.io/example": "zqmarkannotation"}
    bound = binding_document()
    bound["metadata"]["owner"] = "zqmarkbindingowner"
    bound["spec"]["gitops"]["destinationPath"] = "gitops/zqmarkpath"
    bound["spec"]["destination"]["namespace"] = "inferops-zqmarknamespace"
    workload = parse_workload_contract(document)
    environment = parse_environment_binding(bound)
    planted = json.dumps([workload.as_document(), environment.as_document()])
    assert len(set(re.findall(r"zqmark[a-z]+", planted))) == 5
    generated = generate(workload, bindings=[environment])
    for file_name, data in generated.files():
        assert b"zqmark" not in data, file_name


def test_a_credential_shaped_value_is_refused_without_being_quoted() -> None:
    leaked = "glpat-" + "zqleakedtokenvalue"
    with pytest.raises(RenderRefused) as raised:
        generate(changed_contract(_set("metadata", "owner", leaked)))
    assert {finding.rule_id for finding in raised.value.findings} == {
        "render-value-credential-shaped"
    }
    assert leaked not in str(raised.value)
    assert leaked not in json.dumps(
        [finding.as_dict() for finding in raised.value.findings]
    )


def test_the_golden_files_are_not_exempt_from_secret_scanning() -> None:
    """The repository's scanner reads both golden files: no path exception covers them."""
    config = tomllib.loads(GITLEAKS_CONFIG.read_text(encoding="utf-8"))
    # Every place gitleaks reads a path exception from: the global allowlists, in
    # the plural form this file uses and the legacy singular table, and each rule's.
    allowlists = [*config.get("allowlists", []), config.get("allowlist", {})]
    for rule in config.get("rules", []):
        allowlists += [*rule.get("allowlists", []), rule.get("allowlist", {})]
    exempt = [
        pattern for allowlist in allowlists for pattern in allowlist.get("paths", [])
    ]
    assert exempt, "the configuration's path exceptions were not found"
    for golden in (GOLDEN_VALUES, GOLDEN_RELEASE):
        relative = golden.relative_to(REPO_ROOT).as_posix()
        assert [p for p in exempt if re.search(p, relative)] == [], relative


def test_a_secret_written_as_an_ordinary_lowercase_name_passes() -> None:
    """The input-trust limitation, measured: syntax cannot tell it from a name.

    A lowercase value with no published credential prefix, chosen as a binding's
    name, is recorded in the release like any name. Nothing here claims that a
    generated file holds no secret; what is claimed is the bounded property the
    tests above hold.
    """
    disguised = "q7f3k9x2m4p8w6z1"
    assert not is_credential_shaped(disguised)
    named = changed_binding(_set("metadata", "name", disguised))
    generated = generate(bindings=[named])
    assert disguised.encode("ascii") in generated.release_bytes


# --------------------------------------------------------------------------
# 7. All or nothing on disk
# --------------------------------------------------------------------------


def nothing_staged(monkeypatch: pytest.MonkeyPatch) -> list[Path]:
    """Records every file the writer starts, so a test can require that it starts none.

    A rename onto an existing directory fails on Windows anyway, so a refusal there
    proves nothing about the check before staging; this does."""
    started: list[Path] = []
    real = writing_module._write_file

    def spy(path: Path, data: bytes) -> None:
        started.append(path)
        real(path, data)

    monkeypatch.setattr(writing_module, "_write_file", spy)
    return started


def test_an_existing_output_directory_is_never_written_into(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    started = nothing_staged(monkeypatch)
    target = tmp_path / "release"
    target.mkdir()
    (target / "keep.txt").write_bytes(b"kept")
    with pytest.raises(FileExistsError, match="already exists"):
        write_release(generate(), target)
    assert started == []
    assert written(target) == {"keep.txt": b"kept"}
    assert not staging_directory(target).exists()


def test_an_existing_empty_directory_or_file_is_refused_too(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    started = nothing_staged(monkeypatch)
    empty = tmp_path / "empty"
    empty.mkdir()
    afile = tmp_path / "afile"
    afile.write_bytes(b"")
    for target in (empty, afile):
        with pytest.raises(FileExistsError, match="already exists"):
            write_release(generate(), target)
    assert started == []
    assert sorted(path.name for path in tmp_path.iterdir()) == ["afile", "empty"]


def test_a_missing_parent_or_an_unnamed_directory_is_refused(tmp_path: Path) -> None:
    with pytest.raises(FileNotFoundError):
        write_release(generate(), tmp_path / "absent" / "release")
    for unnamed in (Path("."), tmp_path / ".."):
        with pytest.raises(ValueError):
            write_release(generate(), unnamed)
    # A path ending in "." is the directory before it, which exists.
    with pytest.raises(FileExistsError):
        write_release(generate(), tmp_path / ".")
    assert list(tmp_path.iterdir()) == []


def test_only_a_generated_release_is_written(tmp_path: Path) -> None:
    with pytest.raises(TypeError):
        write_release(dict(generate().files()), tmp_path / "release")  # type: ignore[arg-type]
    assert list(tmp_path.iterdir()) == []


def test_the_staging_directory_is_named_for_the_output(tmp_path: Path) -> None:
    assert staging_directory(tmp_path / "release") == tmp_path / ".release.partial"
    assert STAGING_SUFFIX == ".partial"


def test_a_failure_while_writing_leaves_no_output_and_no_staging(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    real = writing_module._write_file
    calls: list[str] = []

    def second_fails(path: Path, data: bytes) -> None:
        calls.append(path.name)
        if len(calls) == 2:
            raise OSError("simulated: the device is full")
        real(path, data)

    monkeypatch.setattr(writing_module, "_write_file", second_fails)
    with pytest.raises(OSError, match="simulated"):
        write_release(generate(), tmp_path / "release")
    assert calls == [str(VALUES_FILE_NAME), RELEASE_FILE_NAME]
    assert list(tmp_path.iterdir()) == []


def test_a_file_that_reads_back_differently_is_never_moved_into_place(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    real = Path.read_bytes

    def altered(self: Path) -> bytes:
        data = real(self)
        return data.replace(b"\n", b"\r\n") if self.name == RELEASE_FILE_NAME else data

    monkeypatch.setattr(Path, "read_bytes", altered)
    with pytest.raises(OSError, match="did not read back"):
        write_release(generate(), tmp_path / "release")
    monkeypatch.undo()
    assert list(tmp_path.iterdir()) == []


def test_a_failed_move_into_place_leaves_no_output_and_no_staging(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def refuse(_source: Any, _target: Any) -> None:
        raise PermissionError("simulated: the rename was refused")

    monkeypatch.setattr(os, "rename", refuse)
    with pytest.raises(PermissionError):
        write_release(generate(), tmp_path / "release")
    assert list(tmp_path.iterdir()) == []


def test_an_interrupted_write_stays_named_and_blocks_the_next_until_removed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The recoverable path: the staging directory cannot be removed, so it is
    named on the error, refuses the next write by name, and once it is removed a
    write succeeds."""
    target = tmp_path / "release"
    staging = staging_directory(target)

    def refuse(_source: Any, _target: Any) -> None:
        raise PermissionError("simulated: the rename was refused")

    def stuck(_self: Path) -> None:
        raise PermissionError("simulated: the directory is held open")

    monkeypatch.setattr(os, "rename", refuse)
    monkeypatch.setattr(Path, "rmdir", stuck)
    with pytest.raises(PermissionError) as raised:
        write_release(generate(), target)
    monkeypatch.undo()
    assert any(str(staging) in note for note in raised.value.__notes__)
    assert staging.is_dir() and not target.exists()

    with pytest.raises(FileExistsError, match="did not finish"):
        write_release(generate(), target)
    assert not target.exists()

    shutil.rmtree(staging)
    write_release(generate(), target)
    assert written(target)[RELEASE_FILE_NAME] == GOLDEN_RELEASE.read_bytes()


def test_a_staging_directory_left_by_a_killed_write_refuses_the_next(
    tmp_path: Path,
) -> None:
    target = tmp_path / "release"
    staging = staging_directory(target)
    staging.mkdir()
    (staging / str(VALUES_FILE_NAME)).write_bytes(b"half")
    with pytest.raises(FileExistsError) as raised:
        write_release(generate(), target)
    assert str(staging) in str(raised.value)
    assert not target.exists()
    assert written(staging) == {str(VALUES_FILE_NAME): b"half"}


def test_a_directory_that_appears_before_the_move_is_kept_and_the_write_refused(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    target = tmp_path / "release"
    real = os.rename

    def raced(source: Any, destination: Any) -> None:
        Path(destination).mkdir()
        (Path(destination) / "theirs.txt").write_bytes(b"theirs")
        real(source, destination)

    monkeypatch.setattr(os, "rename", raced)
    with pytest.raises(OSError):
        write_release(generate(), target)
    monkeypatch.undo()
    assert written(target) == {"theirs.txt": b"theirs"}
    assert not staging_directory(target).exists()


def test_an_interrupt_mid_write_is_cleaned_up_and_raised(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    def interrupted(_path: Path, _data: bytes) -> None:
        raise KeyboardInterrupt

    monkeypatch.setattr(writing_module, "_write_file", interrupted)
    with pytest.raises(KeyboardInterrupt):
        write_release(generate(), tmp_path / "release")
    assert list(tmp_path.iterdir()) == []


def test_an_interrupt_after_the_move_leaves_the_complete_release_alone(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """The release is in place once the rename returns; nothing is discarded, and
    no note calls a complete release incomplete."""
    target = tmp_path / "release"
    real = os.rename

    def moved_then_interrupted(source: Any, destination: Any) -> None:
        real(source, destination)
        raise KeyboardInterrupt

    monkeypatch.setattr(os, "rename", moved_then_interrupted)
    with pytest.raises(KeyboardInterrupt) as raised:
        write_release(generate(), target)
    monkeypatch.undo()
    assert getattr(raised.value, "__notes__", []) == []
    assert written(target)[RELEASE_FILE_NAME] == GOLDEN_RELEASE.read_bytes()
    assert not staging_directory(target).exists()


def test_the_writer_imports_the_file_system_and_nothing_that_reads_the_host() -> None:
    """The one module of the render package that touches a file: ``os`` and
    ``pathlib`` only, and no name that reads the environment, a clock, a random
    source, or a process."""
    import ast

    tree = ast.parse(WRITING_PATH.read_text(encoding="utf-8"))
    roots: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            roots.add((node.module or "").split(".")[0])
    assert roots == {"__future__", "os", "pathlib", "typing"}
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    attributes = {
        node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)
    }
    assert (names | attributes).isdisjoint(
        {
            "environ",
            "getenv",
            "urandom",
            "system",
            "popen",
            "spawnl",
            "execv",
            "__import__",
            "eval",
            "exec",
        }
    )


# --------------------------------------------------------------------------
# V1 compatibility of the written file
# --------------------------------------------------------------------------


def helm_template(*values: Path, overrides: tuple[str, ...] = ()) -> bytes:
    """`helm template` over values files, with no shell and no cluster."""
    helm = shutil.which("helm")
    if helm is None:
        pytest.skip("helm is not on PATH; see CONTRIBUTING.md for the commands")
    argv = [helm, "template", "inferops", str(CHART_DIR)]
    argv += ["--namespace", "inferops-platform"]
    for path in values:
        argv += ["--values", str(path)]
    for override in overrides:
        argv += ["--set", override]
    result = subprocess.run(argv, capture_output=True, check=False, timeout=120)
    assert result.returncode == 0, result.stderr.decode("utf-8", "replace")
    return result.stdout.replace(b"\r\n", b"\n")


def test_helm_renders_the_written_values_as_it_renders_v1_with_the_contracts_environment(
    tmp_path: Path,
) -> None:
    """The written values file, beside the hand-written file as admitted next to it."""
    generated = generate()
    out = write_release(generated, tmp_path / "release")
    pair = admit_manual_values(generated.values, load(MANUAL))
    assert (out / str(VALUES_FILE_NAME)).read_bytes() == (
        pair.generated.to_yaml().encode("ascii")
    )
    hand_written = tmp_path / "admitted.manual-values.yaml"
    hand_written.write_text(
        yaml.safe_dump(pair.documents()[1], sort_keys=True), encoding="utf-8"
    )
    assert helm_template(out / str(VALUES_FILE_NAME), hand_written) == helm_template(
        REAL_VALUES, overrides=("telemetry.deploymentEnvironment=local",)
    )


# --------------------------------------------------------------------------
# 8. The pages say what the code does
# --------------------------------------------------------------------------


def test_the_file_names_and_headers_are_the_published_ones() -> None:
    assert str(VALUES_FILE_NAME) == "values.generated.yaml"
    assert RELEASE_FILE_NAME == "rendered-workload-release.yaml"
    assert values_text(generate().values).startswith(
        "".join(f"# {line}\n" for line in VALUES_HEADER).encode("ascii")
    )
    assert GOLDEN_RELEASE.read_bytes().startswith(
        "".join(f"# {line}\n" for line in RELEASE_HEADER).encode("ascii")
    )
    text = RENDERER_DOC.read_text(encoding="utf-8")
    for name in (str(VALUES_FILE_NAME), RELEASE_FILE_NAME, f".<name>{STAGING_SUFFIX}"):
        assert f"`{name}`" in text, name


def test_the_renderer_page_shows_the_golden_release_byte_for_byte() -> None:
    text = RENDERER_DOC.read_text(encoding="utf-8")
    golden = GOLDEN_RELEASE.read_text(encoding="utf-8")
    assert f"```yaml\n{golden}```" in text


def test_the_release_document_states_the_decided_values_digest_rule() -> None:
    text = " ".join(RELEASE_DOC.read_text(encoding="utf-8").split())
    assert "SHA-256 of the values file's exact bytes" in text
    assert "Not decided here: how the values file is hashed" not in text


PR1_RECORD = REPO_ROOT / "docs" / "proof" / "domain" / "v2-s2-001-pr1-validation.md"


def test_the_pages_claim_the_bounded_secret_property_and_not_the_absolute_one() -> None:
    """The criterion as worded cannot be shown; the pages say what is shown instead."""
    renderer_page = " ".join(RENDERER_DOC.read_text(encoding="utf-8").split())
    assert "### What a generated file can carry" in RENDERER_DOC.read_text(
        encoding="utf-8"
    )
    for phrase in (
        "No supported secret-bearing field, and no secret reference, reaches either file.",
        "Every string comes from an explicitly owned field.",
        "Known credential shapes are refused, and not quoted.",
        "The input-trust limitation stands.",
        "this page does not claim that a generated file contains no secret value",
    ):
        assert phrase in renderer_page, phrase
    release_page = " ".join(RELEASE_DOC.read_text(encoding="utf-8").split())
    assert "expose no supported secret-bearing field or secret reference" in (
        release_page
    )


def test_the_pages_state_the_platform_defaults_limitation_as_measured() -> None:
    text = " ".join(RENDERER_DOC.read_text(encoding="utf-8").split())
    assert "falsely retains the same stated revision" in text
    assert "a release records the **asserted** platform-defaults revision" in text


def test_the_merged_pr1_record_keeps_its_rows_and_adds_a_dated_correction() -> None:
    """The correction is additive: the original rows stay, then a dated note."""
    text = PR1_RECORD.read_text(encoding="utf-8")
    originals = (
        "| Story: generated files contain no secret values | Met for what this change "
        "generates, in memory: no secret reference is rendered, and a credential-shaped "
        "string is refused. No file is written by the code yet |",
        "| Story: manual values do not duplicate claim-relevant contract intent | Met for "
        "the committed reference file, which a test checks:",
    )
    addendum = text.index("\n## Later correction\n")
    for original in originals:
        assert text.count(original) == 1, original
        assert text.index(original) < addendum
    note = text[addendum:]
    assert "Added on 2026-10-02 by `V2-S2-001-PR2`" in note
    assert "v2-s2-001-pr2-validation.md" in note
