"""What the scaffolding command puts on a disk, and what it refuses to.

The rendering suite beside this one establishes that the template produces a
conforming document. This suite is about the half that was deferred out of
`V1-S1-006-PR1`: the command that writes one, and the three properties a writer
can get wrong that a renderer cannot.

* **A generated workload validates without a source edit.** Not the rendered
  string — the files. Every check that says "validates" here reads the document
  back off the disk the command wrote it to and puts it through
  `tools.contract_validation.validate`, the same function every committed fixture
  goes through, and then through the contract package's own pipeline.
* **A generated project runs unedited.** The generated test skeleton is executed
  by a real `python -m pytest` subprocess against the directory the command
  created, from a working directory that is not this repository. An in-process
  import proves the module is importable; only a subprocess proves the command
  the quick start prints is the command that works.
* **Nothing is left half-written and nothing is overwritten.** A write that fails
  partway is rolled back to the state it found, an occupied destination is
  refused with its contents untouched, and a refused parameter set creates
  nothing at all.

Every check reads and writes inside pytest's own temporary directory and files in
this repository, and nothing else. No network, no cluster, no model, no clock, no
randomness — the one subprocess is this interpreter running this repository's own
test suite against a directory this suite just created.
"""

from __future__ import annotations

import argparse
import builtins
import json
import os
import subprocess
import sys
from dataclasses import MISSING, fields, replace
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
    OPTIONAL_PARAMETERS,
    REQUIRED_PARAMETERS,
    InvalidTemplateParametersError,
    WorkloadTemplateParameters,
    render_workload,
    surviving_placeholders,
)
from tests.support.workload_template_cases import (
    MINIMAL_MOCK,
    MINIMAL_REAL,
    MOCK_CASES,
    REAL_CASES,
    REPRESENTATIVE_CASES,
    case_id,
)
from tools.contract_validation.workload import validate
from tools.workload_scaffold import (
    DestinationRefusedError,
    GenerationResult,
    PartialWriteError,
    build_parser,
    generate,
    parameters_from,
    plan_write,
)
from tools.workload_scaffold.__main__ import (
    EXIT_DESTINATION_REFUSED,
    EXIT_OK,
    EXIT_PARAMETERS_REFUSED,
    EXIT_USAGE,
    EXIT_WRITE_FAILED,
    main,
)
from tools.workload_scaffold.arguments import (
    NON_PARAMETER_OPTIONS,
    PARAMETER_OPTIONS,
)

pytestmark = pytest.mark.contract

REPO_ROOT = Path(__file__).resolve().parents[2]
CONTRACT_DIR = REPO_ROOT / "contracts" / "workload"
COMPATIBILITY_MATRIX_PATH = (
    CONTRACT_DIR / "compatibility" / "runtime-model-compatibility.v1alpha1.json"
)

#: The three files a generated workload is, whatever profile it is on.
EXPECTED_OUTPUT_PATHS = (
    "README.md",
    "tests/test_workload_contract.py",
    "workload.yaml",
)


# --------------------------------------------------------------------------
# Helpers
# --------------------------------------------------------------------------


@pytest.fixture
def matrix_loader() -> None:
    """Hand the domain pipeline the committed compatibility matrix.

    The domain does not read a file — a domain object must be constructible
    without a file system — so the matrix is supplied by the caller. Here that
    caller is a test, and reading a committed document is what a test is for.
    """
    document = json.loads(COMPATIBILITY_MATRIX_PATH.read_text(encoding="utf-8"))
    set_matrix_loader(CompatibilityMatrixLoader(document))


def scaffold(
    parameters: WorkloadTemplateParameters, into: Path, **kwargs: Any
) -> GenerationResult:
    """Generate one workload and return the result."""
    return generate(parameters, into, **kwargs)


def written_paths(workload_root: Path) -> tuple[str, ...]:
    """Every file under a generated workload, relative and in a stable order."""
    return tuple(
        sorted(
            path.relative_to(workload_root).as_posix()
            for path in workload_root.rglob("*")
            if path.is_file()
        )
    )


def contract_document(workload_root: Path) -> Any:
    """The generated contract, loaded from the file the command wrote."""
    text = (workload_root / "workload.yaml").read_text(encoding="utf-8")
    return yaml.safe_load(text)


def tree_snapshot(root: Path) -> dict[str, str]:
    """Every file under ``root``, by relative path, with its exact content.

    Used to assert that a refusal changed nothing: comparing the mapping before
    and after is a stronger statement than counting files, because it also
    catches a file that was rewritten with the same name.
    """
    return {
        path.relative_to(root).as_posix(): path.read_text(encoding="utf-8")
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def cli_arguments(parameters: WorkloadTemplateParameters, into: Path) -> list[str]:
    """The command line that supplies one parameter set in full.

    Every parameter is passed explicitly, including the optional ones, so that
    the command's surface is exercised rather than its defaults.
    """
    return [
        "--name",
        parameters.name,
        "--owner",
        parameters.owner,
        "--environment",
        parameters.environment,
        "--profile",
        parameters.profile,
        "--runtime-profile",
        parameters.runtime_profile,
        "--cpu",
        parameters.cpu,
        "--memory",
        parameters.memory,
        "--tenant",
        parameters.tenant,
        "--cost-center",
        parameters.cost_center,
        "--data-classification",
        parameters.data_classification,
        "--description",
        parameters.description,
        "--version",
        parameters.version,
        "--model-ref",
        parameters.resolved_model_ref(),
        "--accelerator-type",
        parameters.accelerator_type,
        "--accelerator-count",
        str(parameters.accelerator_count),
        "--minimum-replicas",
        str(parameters.minimum_replicas),
        "--maximum-replicas",
        str(parameters.maximum_replicas),
        "--into",
        str(into),
    ]


# --------------------------------------------------------------------------
# What a generation writes
# --------------------------------------------------------------------------


@pytest.mark.parametrize("parameters", REPRESENTATIVE_CASES, ids=case_id)
def test_a_generation_writes_exactly_the_three_files_it_declares(
    parameters: WorkloadTemplateParameters, tmp_path: Path
) -> None:
    result = scaffold(parameters, tmp_path)
    assert result.workload_root == tmp_path / parameters.name
    assert written_paths(result.workload_root) == EXPECTED_OUTPUT_PATHS
    assert tuple(sorted(path.name for path in result.files)) == (
        "README.md",
        "test_workload_contract.py",
        "workload.yaml",
    )


@pytest.mark.parametrize("parameters", REPRESENTATIVE_CASES, ids=case_id)
def test_what_is_written_is_byte_for_byte_what_was_rendered(
    parameters: WorkloadTemplateParameters, tmp_path: Path
) -> None:
    """The writer adds nothing to the text and loses nothing from it.

    Including the line endings: the files are opened with an explicit newline so
    that a document generated on Windows is the document generated on Linux.
    """
    rendered = render_workload(parameters)
    result = scaffold(parameters, tmp_path)
    for relative, expected in rendered.files.items():
        actual = (result.workload_root / relative).read_bytes()
        assert actual == expected.encode("utf-8"), relative


@pytest.mark.parametrize("parameters", REPRESENTATIVE_CASES, ids=case_id)
def test_no_placeholder_survives_into_any_written_file(
    parameters: WorkloadTemplateParameters, tmp_path: Path
) -> None:
    result = scaffold(parameters, tmp_path)
    for path in result.files:
        assert surviving_placeholders(path.read_text(encoding="utf-8")) == (), path


@pytest.mark.parametrize("parameters", REPRESENTATIVE_CASES, ids=case_id)
def test_the_written_contract_passes_the_published_schema_and_semantic_rules(
    parameters: WorkloadTemplateParameters, tmp_path: Path
) -> None:
    """Read off the disk, through the validator every committed fixture uses."""
    result = scaffold(parameters, tmp_path)
    findings = validate(contract_document(result.workload_root))
    assert not findings, [finding.as_dict() for finding in findings]


@pytest.mark.parametrize("parameters", REPRESENTATIVE_CASES, ids=case_id)
def test_the_written_contract_passes_the_domain_validation_pipeline(
    parameters: WorkloadTemplateParameters, tmp_path: Path, matrix_loader: None
) -> None:
    """The tool and the contract package must both be satisfied, not either."""
    result = scaffold(parameters, tmp_path)
    contract = parse_workload_contract(contract_document(result.workload_root))
    validate_workload_contract(contract)


@pytest.mark.parametrize("parameters", REPRESENTATIVE_CASES, ids=case_id)
def test_a_generated_workload_declares_the_identity_it_was_generated_with(
    parameters: WorkloadTemplateParameters, tmp_path: Path
) -> None:
    result = scaffold(parameters, tmp_path)
    document = contract_document(result.workload_root)
    assert document["metadata"]["name"] == parameters.name
    assert document["metadata"]["owner"] == parameters.owner
    assert document["metadata"]["version"] == parameters.version
    assert document["metadata"]["description"] == parameters.description
    assert document["spec"]["profile"] == parameters.profile
    assert document["spec"]["attribution"]["tenant"] == parameters.tenant
    assert document["spec"]["attribution"]["costCenter"] == parameters.cost_center


# --------------------------------------------------------------------------
# More than one workload, into the same destination
# --------------------------------------------------------------------------


def test_generating_several_workloads_into_one_destination_keeps_them_apart(
    tmp_path: Path,
) -> None:
    """Four workloads, one destination, no shared state and no cross-talk.

    The failure this catches is a scaffolder that carries something from the
    previous generation — a cached substitution, a reused directory — into the
    next one. It is invisible when a suite generates one workload per test.
    """
    results = [scaffold(parameters, tmp_path) for parameters in REPRESENTATIVE_CASES]

    roots = {result.workload_root for result in results}
    assert len(roots) == len(REPRESENTATIVE_CASES)

    identifiers = {parameters.name for parameters in REPRESENTATIVE_CASES} | {
        parameters.owner for parameters in REPRESENTATIVE_CASES
    }
    for parameters, result in zip(REPRESENTATIVE_CASES, results, strict=True):
        assert written_paths(result.workload_root) == EXPECTED_OUTPUT_PATHS
        findings = validate(contract_document(result.workload_root))
        assert not findings, [finding.as_dict() for finding in findings]
        # A case name that is a substring of this one — `support-assistant`
        # inside `support-assistant-mock` — is the mock suffix rule, not a leak.
        mine = (parameters.name, parameters.owner, parameters.tenant)
        foreign = {
            other for other in identifiers if not any(other in own for own in mine)
        }
        assert foreign, "the cases share every identifier, so this proves nothing"
        for path in result.files:
            body = path.read_text(encoding="utf-8")
            for name in sorted(foreign):
                assert name not in body, (path.name, name)


def test_the_destination_holds_only_the_workloads_that_were_generated(
    tmp_path: Path,
) -> None:
    for parameters in REPRESENTATIVE_CASES:
        scaffold(parameters, tmp_path)
    generated = sorted(entry.name for entry in tmp_path.iterdir())
    assert generated == sorted(parameters.name for parameters in REPRESENTATIVE_CASES)


def test_a_missing_destination_is_created_and_a_nested_one_too(tmp_path: Path) -> None:
    destination = tmp_path / "workloads" / "team-platform"
    result = scaffold(MINIMAL_REAL, destination)
    assert destination.is_dir()
    assert written_paths(result.workload_root) == EXPECTED_OUTPUT_PATHS


# --------------------------------------------------------------------------
# The generated project runs, unedited
# --------------------------------------------------------------------------


def _pytest_environment() -> dict[str, str]:
    """An environment in which `inferops` and `yaml` import from this checkout.

    The subprocess runs outside this repository on purpose — a generated
    workload is not in it — so the distribution is put on the path explicitly
    rather than relied on being installed.
    """
    environment = dict(os.environ)
    existing = environment.get("PYTHONPATH", "")
    source_root = str(REPO_ROOT / "src")
    environment["PYTHONPATH"] = (
        f"{source_root}{os.pathsep}{existing}" if existing else source_root
    )
    return environment


@pytest.mark.parametrize("parameters", REPRESENTATIVE_CASES, ids=case_id)
def test_the_generated_test_skeleton_passes_under_a_real_pytest_run(
    parameters: WorkloadTemplateParameters, tmp_path: Path
) -> None:
    """The command a generated quick start prints, run against what was written.

    Not an import: a subprocess, with this repository outside the working
    directory and outside the rootdir, so that what is proven is the generated
    project rather than this suite's own environment. No file is edited between
    the generation and the run.
    """
    scaffold(parameters, tmp_path)
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "pytest",
            f"{parameters.name}/tests",
            "-q",
            "-p",
            "no:cacheprovider",
        ],
        cwd=tmp_path,
        env=_pytest_environment(),
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout + completed.stderr
    assert "passed" in completed.stdout


# --------------------------------------------------------------------------
# Nothing is overwritten
# --------------------------------------------------------------------------


def test_an_occupied_destination_is_refused_and_left_exactly_as_it_was(
    tmp_path: Path,
) -> None:
    scaffold(MINIMAL_REAL, tmp_path)
    edited = tmp_path / MINIMAL_REAL.name / "workload.yaml"
    edited.write_text("# an author's edit\n", encoding="utf-8")
    before = tree_snapshot(tmp_path)

    with pytest.raises(DestinationRefusedError) as refusal:
        scaffold(MINIMAL_REAL, tmp_path)

    assert refusal.value.path == tmp_path / MINIMAL_REAL.name
    assert "overwrites" in refusal.value.reason
    assert tree_snapshot(tmp_path) == before


def test_a_destination_that_is_a_file_is_refused_before_anything_is_created(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "not-a-directory"
    destination.write_text("occupied\n", encoding="utf-8")

    with pytest.raises(DestinationRefusedError) as refusal:
        scaffold(MINIMAL_REAL, destination)

    assert refusal.value.path == destination
    assert destination.read_text(encoding="utf-8") == "occupied\n"


def test_an_empty_directory_with_the_workload_name_is_still_refused(
    tmp_path: Path,
) -> None:
    """Refusing only a *non-empty* directory would be a rule with a case in it."""
    (tmp_path / MINIMAL_REAL.name).mkdir()
    with pytest.raises(DestinationRefusedError):
        scaffold(MINIMAL_REAL, tmp_path)


def test_a_second_generation_under_a_different_name_is_not_refused(
    tmp_path: Path,
) -> None:
    scaffold(MINIMAL_REAL, tmp_path)
    other = replace(MINIMAL_REAL, name="support-assistant-two")
    result = scaffold(other, tmp_path)
    assert written_paths(result.workload_root) == EXPECTED_OUTPUT_PATHS


# --------------------------------------------------------------------------
# Nothing is written before a refusal
# --------------------------------------------------------------------------


def test_an_invalid_parameter_set_creates_nothing_and_reports_every_reason(
    tmp_path: Path,
) -> None:
    """The acceptance criterion's first clause, asserted against a file system."""
    broken = replace(
        MINIMAL_REAL,
        name="Not A DNS Label",
        environment="nowhere",
        cost_center="Not Kebab Case",
        maximum_replicas=0,
    )

    with pytest.raises(InvalidTemplateParametersError) as refusal:
        scaffold(broken, tmp_path)

    refused = {entry["parameter"] for entry in refusal.value.as_dicts()}
    assert {"name", "environment", "cost_center", "maximum_replicas"} <= refused
    assert list(tmp_path.iterdir()) == []


def test_a_refused_parameter_set_does_not_create_the_destination(
    tmp_path: Path,
) -> None:
    destination = tmp_path / "workloads"
    broken = replace(MINIMAL_REAL, name="Not A DNS Label")

    with pytest.raises(InvalidTemplateParametersError):
        scaffold(broken, destination)

    assert not destination.exists()


@pytest.mark.parametrize("parameters", MOCK_CASES, ids=case_id)
def test_a_mock_profile_rule_is_refused_before_a_file_is_written(
    parameters: WorkloadTemplateParameters, tmp_path: Path
) -> None:
    """The mock name suffix is a refusal, never a silent rename of the output."""
    without_suffix = replace(parameters, name=parameters.name.removesuffix("-mock"))
    with pytest.raises(InvalidTemplateParametersError) as refusal:
        scaffold(without_suffix, tmp_path)
    assert any(entry["parameter"] == "name" for entry in refusal.value.as_dicts())
    assert list(tmp_path.iterdir()) == []


# --------------------------------------------------------------------------
# A write that fails partway
# --------------------------------------------------------------------------


def test_a_write_that_fails_partway_is_rolled_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """The acceptance criterion's second clause: recoverable output.

    The failure is injected at the *second* file, so that the rollback has a
    written file and two created directories to take back rather than nothing.
    """
    import tools.workload_scaffold.generation as generate_module

    written: list[str] = []

    def failing_open(file: Any, *args: Any, **kwargs: Any) -> Any:
        written.append(str(file))
        if len(written) == 2:
            raise OSError("the disk went away")
        return builtins.open(file, *args, **kwargs)

    monkeypatch.setattr(generate_module, "open", failing_open, raising=False)

    with pytest.raises(PartialWriteError) as failure:
        scaffold(MINIMAL_REAL, tmp_path)

    assert failure.value.unremoved == ()
    assert failure.value.removed
    assert list(tmp_path.iterdir()) == []


def test_a_rollback_removes_only_what_the_command_created(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A directory that was already there was never the command's to remove."""
    destination = tmp_path / "workloads"
    destination.mkdir()
    keep = destination / "already-here.txt"
    keep.write_text("not the command's\n", encoding="utf-8")

    import tools.workload_scaffold.generation as generate_module

    seen: list[str] = []

    def failing_open(file: Any, *args: Any, **kwargs: Any) -> Any:
        seen.append(str(file))
        if len(seen) == 2:
            raise OSError("the disk went away")
        return builtins.open(file, *args, **kwargs)

    monkeypatch.setattr(generate_module, "open", failing_open, raising=False)

    with pytest.raises(PartialWriteError):
        scaffold(MINIMAL_REAL, destination)

    assert destination.is_dir()
    assert keep.read_text(encoding="utf-8") == "not the command's\n"
    assert sorted(entry.name for entry in destination.iterdir()) == ["already-here.txt"]


def test_output_that_does_not_verify_after_the_write_is_rolled_back(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """A file that does not read back as it was written is not left behind.

    The read-back is what turns "the string validated" into "the file
    validates", so a read-back that disagrees has to be a refusal rather than a
    warning nobody sees.
    """
    import tools.workload_scaffold.generation as generate_module

    def corrupt(plan: generate_module.WritePlan) -> None:
        raise OSError("the file did not read back as it was written")

    monkeypatch.setattr(generate_module, "_verify", corrupt)

    with pytest.raises(PartialWriteError) as failure:
        scaffold(MINIMAL_REAL, tmp_path)

    assert "did not verify" in failure.value.reason
    assert failure.value.unremoved == ()
    assert list(tmp_path.iterdir()) == []


# --------------------------------------------------------------------------
# The plan, and the dry run that stops at it
# --------------------------------------------------------------------------


@pytest.mark.parametrize("parameters", REPRESENTATIVE_CASES, ids=case_id)
def test_a_dry_run_reports_the_paths_and_writes_nothing(
    parameters: WorkloadTemplateParameters, tmp_path: Path
) -> None:
    result = scaffold(parameters, tmp_path, dry_run=True)
    assert result.dry_run
    assert list(tmp_path.iterdir()) == []
    assert tuple(sorted(path.name for path in result.files)) == (
        "README.md",
        "test_workload_contract.py",
        "workload.yaml",
    )


@pytest.mark.parametrize("parameters", REPRESENTATIVE_CASES, ids=case_id)
def test_a_dry_run_plans_exactly_what_a_real_run_writes(
    parameters: WorkloadTemplateParameters, tmp_path: Path
) -> None:
    """The two must not be separate implementations of the same decision."""
    planned = scaffold(parameters, tmp_path, dry_run=True)
    written = scaffold(parameters, tmp_path)
    assert planned.files == written.files
    assert planned.directories == written.directories


def test_a_dry_run_refuses_an_occupied_destination_too(tmp_path: Path) -> None:
    scaffold(MINIMAL_REAL, tmp_path)
    with pytest.raises(DestinationRefusedError):
        scaffold(MINIMAL_REAL, tmp_path, dry_run=True)


def test_a_plan_orders_its_directories_shallowest_first(tmp_path: Path) -> None:
    """The order the rollback depends on: a parent may not be removed first."""
    plan = plan_write(render_workload(MINIMAL_REAL), tmp_path / "a" / "b")
    depths = [len(directory.parts) for directory in plan.directories]
    assert depths == sorted(depths)
    assert plan.directories[-1] == plan.workload_root / "tests"


# --------------------------------------------------------------------------
# The command line
# --------------------------------------------------------------------------


def test_the_command_line_offers_one_option_per_template_parameter() -> None:
    """A parameter with no option, and an option with no parameter, both fail.

    The drift this catches is a parameter added to the template and never
    reachable from the command that is supposed to gather it. The parser is
    generated from this table, so the table is the command line rather than a
    description of it.
    """
    declared = {option.parameter for option in PARAMETER_OPTIONS}
    assert declared == set(REQUIRED_PARAMETERS) | set(OPTIONAL_PARAMETERS)
    assert not declared & set(NON_PARAMETER_OPTIONS)


def test_the_required_and_optional_split_is_the_template_s_own() -> None:
    """An option that made a required parameter optional would default it.

    A default is a decision this repository has published. Inventing one at the
    command line is how a workload acquires a classification nobody chose.
    """
    required = {option.parameter for option in PARAMETER_OPTIONS if option.required}
    optional = {option.parameter for option in PARAMETER_OPTIONS if not option.required}
    assert required == set(REQUIRED_PARAMETERS)
    assert optional == set(OPTIONAL_PARAMETERS)


def test_every_optional_default_is_the_one_the_template_holds() -> None:
    """The table may not hold a second opinion about a published default."""
    declared = {
        entry.name: entry.default
        for entry in fields(WorkloadTemplateParameters)
        if entry.default is not MISSING
    }
    for option in PARAMETER_OPTIONS:
        if option.required:
            continue
        assert option.default == declared[option.parameter], option.parameter


def test_an_option_flag_is_its_parameter_name_in_kebab_case() -> None:
    """`cost_center` is `--cost-center`, mechanically, with no exceptions."""
    for option in PARAMETER_OPTIONS:
        assert option.flag == "--" + option.parameter.replace("_", "-")


def test_every_template_parameter_is_reachable_from_the_namespace() -> None:
    """What the parser produces builds the parameter set with nothing missing."""
    parser = build_parser()
    namespace = parser.parse_args(cli_arguments(MINIMAL_REAL, Path()))
    built = parameters_from(namespace)
    for entry in fields(WorkloadTemplateParameters):
        if entry.name == "model_ref":
            # The command line passes the resolved identity, so the case's `None`
            # — meaning "the catalogue entry for this profile" — is compared
            # against what that default resolves to rather than against itself.
            assert built.resolved_model_ref() == MINIMAL_REAL.resolved_model_ref()
            continue
        assert getattr(built, entry.name) == getattr(MINIMAL_REAL, entry.name), (
            entry.name
        )


def test_the_command_line_defaults_are_the_published_ones() -> None:
    """A default typed into the parser that the template does not hold is drift."""
    parser = build_parser()
    minimal = [
        "--name",
        MINIMAL_REAL.name,
        "--owner",
        MINIMAL_REAL.owner,
        "--environment",
        MINIMAL_REAL.environment,
        "--profile",
        MINIMAL_REAL.profile,
        "--runtime-profile",
        MINIMAL_REAL.runtime_profile,
        "--cpu",
        MINIMAL_REAL.cpu,
        "--memory",
        MINIMAL_REAL.memory,
        "--tenant",
        MINIMAL_REAL.tenant,
        "--cost-center",
        MINIMAL_REAL.cost_center,
        "--data-classification",
        MINIMAL_REAL.data_classification,
        "--description",
        MINIMAL_REAL.description,
    ]
    built = parameters_from(parser.parse_args(minimal))
    assert built == MINIMAL_REAL


@pytest.mark.parametrize("parameters", REPRESENTATIVE_CASES, ids=case_id)
def test_the_command_generates_a_validating_workload_and_exits_zero(
    parameters: WorkloadTemplateParameters,
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    status = main(cli_arguments(parameters, tmp_path))
    assert status == EXIT_OK
    workload_root = tmp_path / parameters.name
    assert written_paths(workload_root) == EXPECTED_OUTPUT_PATHS
    assert not validate(contract_document(workload_root))
    assert parameters.name in capsys.readouterr().out


def test_the_command_emits_stable_json(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    status = main([*cli_arguments(MINIMAL_MOCK, tmp_path), "--json"])
    assert status == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["generated"]["workload"] == MINIMAL_MOCK.name
    assert payload["generated"]["profile"] == MINIMAL_MOCK.profile
    assert payload["generated"]["dryRun"] is False
    assert payload["generated"]["contractValidatedFrom"] == "the written file"
    assert len(payload["generated"]["files"]) == len(EXPECTED_OUTPUT_PATHS)


def test_the_command_reports_every_refusal_and_exits_one(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    broken = replace(MINIMAL_REAL, name="Not A DNS Label", environment="nowhere")
    status = main([*cli_arguments(broken, tmp_path), "--json"])
    assert status == EXIT_PARAMETERS_REFUSED
    payload = json.loads(capsys.readouterr().out)
    assert payload["refused"] == "parameters"
    refused = {entry["parameter"] for entry in payload["refusals"]}
    assert {"name", "environment"} <= refused
    assert list(tmp_path.iterdir()) == []


def test_the_command_refuses_an_occupied_destination_and_exits_three(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(cli_arguments(MINIMAL_REAL, tmp_path)) == EXIT_OK
    status = main(cli_arguments(MINIMAL_REAL, tmp_path))
    assert status == EXIT_DESTINATION_REFUSED
    assert "REFUSED" in capsys.readouterr().out


def test_the_command_exits_five_when_a_write_fails(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    import tools.workload_scaffold.generation as generate_module

    def failing_open(file: Any, *args: Any, **kwargs: Any) -> Any:
        raise OSError("the disk went away")

    monkeypatch.setattr(generate_module, "open", failing_open, raising=False)

    status = main([*cli_arguments(MINIMAL_REAL, tmp_path), "--json"])
    assert status == EXIT_WRITE_FAILED
    payload = json.loads(capsys.readouterr().out)
    assert payload["refused"] == "write"
    assert payload["write"]["rolledBack"] is True
    assert list(tmp_path.iterdir()) == []


def test_a_missing_required_option_is_a_usage_error(tmp_path: Path) -> None:
    """`argparse` names every missing option at once, which is the same rule."""
    with pytest.raises(SystemExit) as exit_status:
        main(["--name", "support-assistant", "--into", str(tmp_path)])
    assert exit_status.value.code == EXIT_USAGE
    assert list(tmp_path.iterdir()) == []


def test_a_dry_run_from_the_command_line_writes_nothing(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    status = main([*cli_arguments(MINIMAL_REAL, tmp_path), "--dry-run", "--json"])
    assert status == EXIT_OK
    payload = json.loads(capsys.readouterr().out)
    assert payload["generated"]["dryRun"] is True
    assert payload["generated"]["contractValidatedFrom"] == "the rendered text"
    assert list(tmp_path.iterdir()) == []


def test_a_mistyped_vocabulary_is_refused_with_the_others_not_alone(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """A vocabulary enforced by `argparse` reports one problem and exits.

    The whole point of the template's validator is that an author learns every
    reason in one pass, so the closed vocabularies deliberately arrive unchecked
    and are refused together in the schema's own words.
    """
    broken = replace(
        MINIMAL_REAL,
        environment="nowhere",
        runtime_profile="fast",
        data_classification="secret",
        accelerator_type="quantum",
    )
    status = main([*cli_arguments(broken, tmp_path), "--json"])
    assert status == EXIT_PARAMETERS_REFUSED, "a vocabulary was enforced by argparse"
    payload = json.loads(capsys.readouterr().out)
    refused = {entry["parameter"] for entry in payload["refusals"]}
    assert {
        "environment",
        "runtime_profile",
        "data_classification",
        "accelerator_type",
    } <= refused
    assert list(tmp_path.iterdir()) == []


# --------------------------------------------------------------------------
# The mock and real boundary survives the write
# --------------------------------------------------------------------------


@pytest.mark.parametrize("parameters", MOCK_CASES, ids=case_id)
def test_a_written_mock_declares_itself_a_mock_in_its_own_files(
    parameters: WorkloadTemplateParameters, tmp_path: Path
) -> None:
    result = scaffold(parameters, tmp_path)
    document = contract_document(result.workload_root)
    assert document["spec"]["profile"] == "mock-llm"
    assert document["spec"]["mockLlm"]["ciOnly"] is True
    assert document["metadata"]["name"].endswith("-mock")
    assert not document["spec"]["security"]["secretRefs"]
    assert "proofRefs" not in document["spec"]["evidence"]

    readme = (result.workload_root / "README.md").read_text(encoding="utf-8")
    assert "mock workload" in readme
    # The mock quick start names the real lane once, to say it has none. What it
    # must not do is offer it as a command, so the commands are what is checked.
    commands = [line for line in readme.splitlines() if line.startswith("python -m")]
    assert commands, readme
    assert not any("realruntime" in line for line in commands)
    assert "INFEROPS_SERVING_ADAPTER=real" not in readme


@pytest.mark.parametrize("parameters", REAL_CASES, ids=case_id)
def test_a_written_real_workload_offers_the_real_lane_and_is_not_a_mock(
    parameters: WorkloadTemplateParameters, tmp_path: Path
) -> None:
    result = scaffold(parameters, tmp_path)
    document = contract_document(result.workload_root)
    assert document["spec"]["profile"] == "synchronous-llm"
    assert "mockLlm" not in document["spec"]
    assert "proofRefs" not in document["spec"]["evidence"]

    readme = (result.workload_root / "README.md").read_text(encoding="utf-8")
    commands = [line for line in readme.splitlines() if line.startswith("python -m")]
    assert any("realruntime" in line for line in commands), readme
    assert "INFEROPS_SERVING_ADAPTER=real" in readme


def test_the_two_profiles_write_the_same_file_names_and_different_contents(
    tmp_path: Path,
) -> None:
    real = scaffold(MINIMAL_REAL, tmp_path)
    mock = scaffold(MINIMAL_MOCK, tmp_path)
    assert written_paths(real.workload_root) == written_paths(mock.workload_root)
    for relative in EXPECTED_OUTPUT_PATHS:
        assert (real.workload_root / relative).read_text(encoding="utf-8") != (
            mock.workload_root / relative
        ).read_text(encoding="utf-8"), relative


# --------------------------------------------------------------------------
# What this command is not
# --------------------------------------------------------------------------


def test_the_command_writes_no_kubernetes_manifest(tmp_path: Path) -> None:
    """The template scope is three files. A chart is not among them.

    No controller, chart, or reconciler in this repository acts on a
    WorkloadContract, so a generated manifest would be a deployment artifact
    nothing deploys and a claim nothing supports.
    """
    result = scaffold(MINIMAL_REAL, tmp_path)
    for path in result.files:
        assert path.suffix not in {".tpl"}
        if path.suffix in {".yaml", ".yml"}:
            document = yaml.safe_load(path.read_text(encoding="utf-8"))
            assert document["apiVersion"] == "inferops.io/v1alpha1"
            assert document["kind"] == "WorkloadContract"
    assert not (result.workload_root / "Chart.yaml").exists()
    assert not (result.workload_root / "templates").exists()


def test_no_argument_default_names_a_path_outside_the_working_directory() -> None:
    """The destination defaults to where the author is, and to nowhere else."""
    parser = build_parser()
    namespace = parser.parse_args(cli_arguments(MINIMAL_REAL, Path()))
    assert namespace.into == Path()


def test_the_generation_result_reports_nothing_it_did_not_do(tmp_path: Path) -> None:
    """Every path a result names exists, and every file it created is listed."""
    result = scaffold(MINIMAL_REAL, tmp_path)
    for path in result.files:
        assert path.is_file()
    for directory in result.directories:
        assert directory.is_dir()
    assert set(result.files) == {
        path for path in result.workload_root.rglob("*") if path.is_file()
    }


def test_an_argparse_namespace_is_all_the_command_needs(tmp_path: Path) -> None:
    """`parameters_from` reads a namespace and nothing else — no environment.

    A scaffolder that reached for an environment variable would generate two
    different workloads from one command line.
    """
    namespace = argparse.Namespace(
        **{
            entry.name: getattr(MINIMAL_MOCK, entry.name)
            for entry in fields(WorkloadTemplateParameters)
        }
    )
    assert parameters_from(namespace) == MINIMAL_MOCK
