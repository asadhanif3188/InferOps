"""The single-runtime baseline profile, and the comparison that keeps it controlled.

The baseline is two API replicas and one serving runtime replica. The target is
the desired-state release, with two of each. ``tools.baseline_profile`` derives
both releases and refuses each difference that is not the runtime replica count,
or an identity that follows it.

These tests hold four things.

1. **The committed profile.** The baseline release and the comparison record are
   what the tool derives, and the differences are the ones restated here.
2. **Each accidental change is refused.** A copy of the inputs is edited in one
   place: a resource ceiling, the runtime image, the model, the owner, a
   caller-facing API value, the binding, a revision, or a replica count. The
   comparison names the rule and the path.
3. **The profile is not desired state.** It is outside ``gitops/``, no
   desired-state release names it, and no Application reads it.
4. **The page says what the tool does.** Each rule and each permitted path is in
   the document.

Everything here reads files. Nothing contacts a cluster, and nothing runs Helm.
A test of the chart suite renders both releases with the chart tool.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest
import yaml

from tools.baseline_profile import (
    BASELINE_CONTRACT,
    CHECK_RULES,
    COMPARABLE,
    DOES_NOT_ESTABLISH,
    HELD,
    NOT_EVALUATED,
    NOT_HELD,
    PERMITTED,
    PROFILE_DIRECTORY,
    RECORD_PATH,
    RECORD_SCHEMA,
    REFUSED,
    REFUSED_EXIT,
    RESULT_STATES,
    RULES,
    TARGET_KEY,
    TOPOLOGY,
    WriteRefused,
    baseline_profile,
    build_record,
    record_text,
    target_release,
    verify_profile,
    write_profile,
)
from tools.baseline_profile.__main__ import main
from tools.generated_release import (
    DECLARED_RELEASES,
    GENERATED_FILES,
    MATRIX_PATH,
    REPO_ROOT,
)
from tools.gitops_desired_state import DESIRED_STATE_RELEASES, DESIRED_STATE_ROOT

pytestmark = pytest.mark.unit

DOCUMENT = REPO_ROOT / "docs" / "environment" / "single-runtime-baseline-profile.md"
APPLICATIONS_DIR = REPO_ROOT / "infra" / "argocd"

# Restated on purpose. A value read from the tool would agree with the tool by
# construction.
TARGET_DIRECTORY = (
    "gitops/environments/local-docker-desktop/workloads/support-assistant"
)
TARGET_CONTRACT = "contracts/workload/examples/valid/synchronous-llm-two-replicas.yaml"
BINDING = "contracts/environment/examples/valid/local-docker-desktop.yaml"
OTHER_BINDING = "contracts/environment/examples/valid/local-kind.yaml"
DEFAULTS = "charts/inferops-llm/values.yaml"
VALUES = "values.generated.yaml"
RELEASE = "rendered-workload-release.yaml"

#: Every difference of the committed comparison, by layer, as (path, baseline,
#: target). The release layer's digests are read from the committed files.
CONTRACT_DIFFERENCES = [
    (
        "/metadata/description",
        "Example synchronous LLM workload used to exercise the v1alpha1 contract.",
        "Example synchronous LLM workload that declares two serving runtime replicas.",
    ),
    ("/metadata/version", "0.1.0", "0.2.0"),
    ("/spec/scaling/maximumReplicas", 1, 2),
    ("/spec/scaling/minimumReplicas", 1, 2),
]
VALUES_DIFFERENCES = [
    ("/ownership/workloadVersion", "0.1.0", "0.2.0"),
    ("/runtime/replicaCount", 1, 2),
]
RELEASE_PATHS = [
    "/metadata/releaseId",
    "/metadata/workloadVersion",
    "/output/helmValues/sha256",
    "/source/contract/sha256",
]
RULE_IDS = [
    "baseline-declaration-differs",
    "baseline-sources-refused",
    "baseline-contract-differs",
    "baseline-values-differ",
    "baseline-release-differs",
    "baseline-topology-not-declared",
    "baseline-version-not-distinct",
]


# --------------------------------------------------------------------------
# A copy of the profile and of its declared inputs, to plant defects in
# --------------------------------------------------------------------------


def copy_inputs(root: Path) -> Path:
    """Copy the profile, the record, and every input either release is derived from."""
    relatives = {
        PROFILE_DIRECTORY,
        RECORD_PATH,
        MATRIX_PATH,
        BASELINE_CONTRACT,
        TARGET_CONTRACT,
        BINDING,
        OTHER_BINDING,
        DEFAULTS,
    }
    for relative in sorted(relatives):
        source, target = REPO_ROOT / relative, root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if source.is_dir():
            shutil.copytree(source, target)
        else:
            # LF on every host, so a copy holds the bytes that Git stores.
            target.write_bytes(source.read_bytes().replace(b"\r\n", b"\n"))
    return root


@pytest.fixture
def root(tmp_path: Path) -> Path:
    return copy_inputs(tmp_path / "repository")


def edit(path: Path, old: str, new: str) -> None:
    """Replace the one occurrence of ``old`` in a text file, keeping LF."""
    text = path.read_bytes().decode("utf-8").replace("\r\n", "\n")
    assert text.count(old) == 1, (path.name, old)
    path.write_bytes(text.replace(old, new).encode("utf-8"))


def found(record: dict[str, Any]) -> list[tuple[str, str]]:
    return [(finding["rule"], finding["subject"]) for finding in record["findings"]]


def states(record: dict[str, Any]) -> dict[str, str]:
    return {rule["id"]: rule["state"] for rule in record["rules"]}


def load(relative: str) -> Any:
    return yaml.safe_load((REPO_ROOT / relative).read_text(encoding="utf-8"))


# --------------------------------------------------------------------------
# 1. The committed profile
# --------------------------------------------------------------------------


def test_the_committed_profile_breaks_no_rule() -> None:
    assert verify_profile() == ()


def test_the_check_command_passes_on_the_committed_profile() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "tools.baseline_profile", "--check"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert f"OK       {PROFILE_DIRECTORY}" in result.stdout
    assert f"OK       {RECORD_PATH}" in result.stdout


def test_the_committed_record_is_the_record_the_tree_gives() -> None:
    committed = (REPO_ROOT / RECORD_PATH).read_bytes()
    assert b"\r" not in committed
    assert committed.decode("utf-8") == record_text(build_record())
    record = json.loads(committed)
    assert (
        record["apiVersion"]
        == RECORD_SCHEMA
        == ("inferops.io/baseline-profile-comparison/v1alpha1")
    )
    assert record["kind"] == "BaselineProfileComparison"
    assert record["result"] == COMPARABLE == "COMPARABLE"
    assert record["findings"] == []
    assert states(record) == dict.fromkeys(RULE_IDS, HELD)
    assert record["doesNotEstablish"] == list(DOES_NOT_ESTABLISH)
    assert RESULT_STATES == (COMPARABLE, REFUSED)


def test_the_declarations_are_the_ones_restated_here() -> None:
    """The baseline is the target's declaration with two fields replaced."""
    target, baseline = target_release(), baseline_profile()
    assert TARGET_KEY == "local-docker-desktop/support-assistant"
    assert target.directory == TARGET_DIRECTORY
    assert target.contract == TARGET_CONTRACT
    assert (
        baseline.directory
        == PROFILE_DIRECTORY
        == ("tests/domain/fixtures/experiment-profiles/single-runtime-baseline")
    )
    assert (
        baseline.contract
        == BASELINE_CONTRACT
        == ("contracts/workload/examples/valid/synchronous-llm-local.yaml")
    )
    assert replace(baseline, directory=target.directory, contract=target.contract) == (
        target
    )
    assert baseline.bindings == (BINDING,)
    assert baseline.binding_name == "local-docker-desktop"
    assert baseline.platform_defaults == DEFAULTS


def test_the_two_sides_differ_in_the_stated_paths_and_in_no_other() -> None:
    record = build_record()
    differences = record["differences"]
    assert list(differences) == ["declaration", "contract", "values", "release"]
    assert [
        (d["path"], d["baseline"], d["target"]) for d in differences["declaration"]
    ] == [
        ("/contract", BASELINE_CONTRACT, TARGET_CONTRACT),
        ("/directory", PROFILE_DIRECTORY, TARGET_DIRECTORY),
    ]
    assert [
        (d["path"], d["baseline"], d["target"]) for d in differences["contract"]
    ] == CONTRACT_DIFFERENCES
    assert [
        (d["path"], d["baseline"], d["target"]) for d in differences["values"]
    ] == VALUES_DIFFERENCES
    assert [d["path"] for d in differences["release"]] == RELEASE_PATHS
    for layer, entries in differences.items():
        assert all(entry["permitted"] for entry in entries), layer
        assert [entry["path"] for entry in entries] == sorted(PERMITTED[layer])
    # Every permitted path is used, so none can outlive the difference it names.
    assert record["permittedDifferences"] == {
        layer: dict(sorted(paths.items())) for layer, paths in PERMITTED.items()
    }


def test_the_intended_variable_is_the_runtime_replica_count_alone() -> None:
    """One values path carries the variable, and the contract's range feeds it."""
    intended = {
        layer: sorted(
            path for path, reason in paths.items() if reason == "intended-variable"
        )
        for layer, paths in PERMITTED.items()
    }
    assert intended == {
        "declaration": [],
        "contract": ["/spec/scaling/maximumReplicas", "/spec/scaling/minimumReplicas"],
        "values": ["/runtime/replicaCount"],
        "release": [],
    }
    record = build_record()
    assert record["intendedVariable"] == {
        "name": "serving runtime replica count",
        "baseline": 1,
        "target": 2,
    }
    assert record["topology"] == {
        "baseline": {"apiReplicas": 2, "runtimeReplicas": 1},
        "target": {"apiReplicas": 2, "runtimeReplicas": 2},
    }
    assert record["topology"] == {side: dict(TOPOLOGY[side]) for side in TOPOLOGY}


def test_the_committed_values_are_the_targets_but_for_two_lines() -> None:
    """The comparison read as bytes: two lines differ, and every other line is one."""
    baseline = (REPO_ROOT / PROFILE_DIRECTORY / VALUES).read_bytes()
    target = (REPO_ROOT / TARGET_DIRECTORY / VALUES).read_bytes()
    assert b"\r" not in baseline
    ours, theirs = baseline.decode().splitlines(), target.decode().splitlines()
    assert len(ours) == len(theirs)
    assert [(a, b) for a, b in zip(ours, theirs, strict=True) if a != b] == [
        ('  workloadVersion: "0.1.0"', '  workloadVersion: "0.2.0"'),
        ("  replicaCount: 1", "  replicaCount: 2"),
    ]
    values = yaml.safe_load(baseline)
    assert values["api"]["replicaCount"] == 2
    assert values["runtime"]["replicaCount"] == 1
    # The rollout bounds are the target's. At one replica they permit the one
    # runtime pod to be removed before its replacement exists.
    assert values["runtime"]["rollout"] == {"maxUnavailable": 1, "maxSurge": 0}
    assert values["api"]["rollout"] == {"maxUnavailable": 0, "maxSurge": 1}


def test_the_committed_release_names_the_inputs_the_record_states() -> None:
    record = json.loads((REPO_ROOT / RECORD_PATH).read_text(encoding="utf-8"))
    baseline = load(f"{PROFILE_DIRECTORY}/{RELEASE}")
    target = load(f"{TARGET_DIRECTORY}/{RELEASE}")
    assert record["releases"] == {"baseline": baseline, "target": target}
    assert baseline["metadata"]["workloadId"] == target["metadata"]["workloadId"]
    for member in ("environmentBinding", "platformDefaults", "renderer"):
        assert baseline["source"][member] == target["source"][member], member
    assert baseline["metadata"]["releaseId"] != target["metadata"]["releaseId"]
    assert sorted(p.name for p in (REPO_ROOT / PROFILE_DIRECTORY).iterdir()) == sorted(
        GENERATED_FILES
    )


def test_the_comparison_reads_every_leaf_of_each_document() -> None:
    """A count taken here, so a layer that read nothing would not pass as equal."""

    def leaves(document: Any) -> int:
        if isinstance(document, dict) and document:
            return sum(leaves(value) for value in document.values())
        if isinstance(document, list) and document:
            return sum(leaves(value) for value in document)
        return 1

    compared = build_record()["pathsCompared"]
    assert compared["declaration"] == 7
    for layer, relative in (
        ("contract", BASELINE_CONTRACT),
        ("values", f"{PROFILE_DIRECTORY}/{VALUES}"),
        ("release", f"{PROFILE_DIRECTORY}/{RELEASE}"),
    ):
        # Both sides hold the same paths, so the union is one side's count.
        assert compared[layer] == leaves(load(relative)), layer
    assert compared["values"] > 20


# --------------------------------------------------------------------------
# 2. Each accidental change is refused
# --------------------------------------------------------------------------

#: One edit of the baseline contract, and each finding it must give. The edited
#: contract still renders, so the comparison reaches every layer.
CONTRACT_EDITS = [
    pytest.param(
        ('cpu: "6"', 'cpu: "4"'),
        [
            ("baseline-contract-differs", "contract: /spec/resources/cpu"),
            ("baseline-values-differ", "values: /runtime/resources/limits/cpu"),
        ],
        id="resources-cpu",
    ),
    pytest.param(
        ("memory: 3Gi", "memory: 2Gi"),
        [
            ("baseline-contract-differs", "contract: /spec/resources/memory"),
            ("baseline-values-differ", "values: /runtime/resources/limits/memory"),
        ],
        id="resources-memory",
    ),
    pytest.param(
        (
            "sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384",
            "sha256:" + "1" * 64,
        ),
        [
            (
                "baseline-contract-differs",
                "contract: /spec/synchronousLlm/runtime/imageReference",
            ),
            ("baseline-values-differ", "values: /runtime/image/digest"),
        ],
        id="runtime-image",
    ),
    pytest.param(
        ("modelRef: qwen3-1-7b-q8-0", "modelRef: other-model"),
        [
            ("baseline-contract-differs", "contract: /spec/model/modelRef"),
            ("baseline-values-differ", "values: /model/identifier"),
        ],
        id="model-identifier",
    ),
    pytest.param(
        ("owner: team-platform-demo", "owner: team-other-demo"),
        [
            ("baseline-contract-differs", "contract: /metadata/owner"),
            ("baseline-values-differ", "values: /ownership/owner"),
        ],
        id="workload-owner",
    ),
    pytest.param(
        ("tenant: demo", "tenant: other"),
        [
            ("baseline-contract-differs", "contract: /spec/attribution/tenant"),
            ("baseline-values-differ", "values: /ownership/tenant"),
        ],
        id="workload-tenant",
    ),
    pytest.param(
        ("name: support-assistant", "name: other-assistant"),
        [
            ("baseline-contract-differs", "contract: /metadata/name"),
            ("baseline-values-differ", "values: /ownership/workloadId"),
            ("baseline-release-differs", "release: /metadata/workloadId"),
            ("baseline-version-not-distinct", "contract: /metadata/name"),
        ],
        id="workload-name",
    ),
    pytest.param(
        (
            "runbookRef: docs/serving/feasibility-workflow.md",
            "runbookRef: docs/serving/inference-api.md",
        ),
        [("baseline-contract-differs", "contract: /spec/evidence/runbookRef")],
        id="contract-member-no-render-reads",
    ),
    pytest.param(
        ("dataClassification: internal", "dataClassification: public"),
        [("baseline-contract-differs", "contract: /spec/security/dataClassification")],
        id="security-classification",
    ),
]


def refused_by(root: Path) -> dict[str, Any]:
    record = build_record(root)
    assert record["result"] == REFUSED
    return record


@pytest.mark.parametrize(("change", "expected"), CONTRACT_EDITS)
def test_an_accidental_change_to_the_baseline_contract_is_refused(
    root: Path, change: tuple[str, str], expected: list[tuple[str, str]]
) -> None:
    edit(root / BASELINE_CONTRACT, *change)
    record = refused_by(root)
    assert found(record) == expected
    broken = {rule for rule, _subject in expected}
    assert states(record) == {
        rule: NOT_HELD if rule in broken else HELD for rule in RULE_IDS
    }
    # The same edit is drift in the committed release, because the release
    # records the contract's digest, and the record is stale.
    check = {finding.rule_id for finding in verify_profile(root)}
    assert {"baseline-release-drifted", "baseline-record-stale"} <= check
    with pytest.raises(WriteRefused):
        write_profile(root)


def test_the_same_change_on_the_target_side_is_refused_too(root: Path) -> None:
    """The comparison has no trusted side: an edit of the target is a difference."""
    edit(root / TARGET_CONTRACT, 'cpu: "6"', 'cpu: "8"')
    assert found(refused_by(root)) == [
        ("baseline-contract-differs", "contract: /spec/resources/cpu"),
        ("baseline-values-differ", "values: /runtime/resources/limits/cpu"),
    ]


#: An edit of the baseline contract that the render boundary refuses. Nothing is
#: compared then, and the refusal is the finding.
REFUSED_AT_RENDER = [
    pytest.param(
        (
            "revision: 90862c4b9d2787eaed51d12237eafdfe7c5f6077",
            "revision: " + "9" * 40,
        ),
        id="model-revision",
    ),
    pytest.param(("minimumReplicas: 1", "minimumReplicas: 0"), id="replica-range"),
]


@pytest.mark.parametrize("change", REFUSED_AT_RENDER)
def test_a_baseline_contract_that_does_not_render_refuses_the_comparison(
    root: Path, change: tuple[str, str]
) -> None:
    edit(root / BASELINE_CONTRACT, *change)
    record = refused_by(root)
    assert found(record) == [("baseline-sources-refused", "baseline: declared inputs")]
    assert states(record) == {
        "baseline-declaration-differs": HELD,
        "baseline-sources-refused": NOT_HELD,
        **dict.fromkeys(RULE_IDS[2:], NOT_EVALUATED),
    }
    assert record["differences"].keys() == {"declaration"}
    assert record["releases"] == {} and record["topology"] == {}


def test_a_missing_baseline_contract_refuses_the_comparison(root: Path) -> None:
    (root / BASELINE_CONTRACT).unlink()
    record = refused_by(root)
    assert found(record) == [("baseline-sources-refused", "baseline: declared inputs")]
    # The reason names the file under the root, and no path of this host.
    assert BASELINE_CONTRACT in record["findings"][0]["detail"]
    assert str(root) not in json.dumps(record)
    assert states(record) == {
        "baseline-declaration-differs": HELD,
        "baseline-sources-refused": NOT_HELD,
        **dict.fromkeys(RULE_IDS[2:], NOT_EVALUATED),
    }


def test_a_missing_shared_input_refuses_both_sides(root: Path) -> None:
    """Both sides read the one binding, so each side derives nothing."""
    (root / BINDING).unlink()
    record = refused_by(root)
    assert found(record) == [
        ("baseline-sources-refused", "baseline: declared inputs"),
        ("baseline-sources-refused", "target: declared inputs"),
    ]
    assert all(BINDING in finding["detail"] for finding in record["findings"])


@pytest.mark.parametrize(
    ("change", "stated"),
    [
        (
            (
                "minimumReplicas: 1\n    maximumReplicas: 1",
                "minimumReplicas: 2\n    maximumReplicas: 2",
            ),
            2,
        ),
        (
            (
                "minimumReplicas: 1\n    maximumReplicas: 1",
                "minimumReplicas: 3\n    maximumReplicas: 3",
            ),
            3,
        ),
    ],
    ids=["two-runtime-replicas", "three-runtime-replicas"],
)
def test_a_baseline_with_another_runtime_replica_count_is_refused(
    root: Path, change: tuple[str, str], stated: int
) -> None:
    """The permitted paths may differ, and only to the declared counts."""
    edit(root / BASELINE_CONTRACT, *change)
    record = refused_by(root)
    assert found(record) == [
        ("baseline-topology-not-declared", "contract: baseline /spec/scaling"),
        ("baseline-topology-not-declared", "values: baseline runtimeReplicas"),
    ]
    assert record["topology"]["baseline"] == {
        "apiReplicas": 2,
        "runtimeReplicas": stated,
    }


def test_a_baseline_that_keeps_the_targets_version_is_refused(root: Path) -> None:
    """One version would name two contents."""
    edit(root / BASELINE_CONTRACT, "version: 0.1.0", "version: 0.2.0")
    assert found(refused_by(root)) == [
        ("baseline-version-not-distinct", "contract: /metadata/version")
    ]


def test_a_target_with_one_api_replica_is_refused(root: Path) -> None:
    """Both sides read one binding, so the count moves on both, and neither is 2."""
    edit(root / BINDING, "apiReplicas: 2", "apiReplicas: 1")
    record = refused_by(root)
    assert found(record) == [
        ("baseline-topology-not-declared", "values: baseline apiReplicas"),
        ("baseline-topology-not-declared", "values: target apiReplicas"),
    ]
    assert record["differences"]["values"] == build_record()["differences"]["values"]


def test_a_baseline_on_another_binding_is_refused(root: Path) -> None:
    """The other binding states one API replica, so the API tier would differ too."""
    baseline = replace(
        baseline_profile(), bindings=(OTHER_BINDING,), binding_name="local-kind"
    )
    record = build_record(root, baseline=baseline)
    assert record["result"] == REFUSED
    subjects = found(record)
    assert ("baseline-declaration-differs", "declaration: /bindings/0") in subjects
    assert ("baseline-declaration-differs", "declaration: /bindingName") in subjects
    assert ("baseline-values-differ", "values: /api/replicaCount") in subjects
    assert (
        "baseline-topology-not-declared",
        "values: baseline apiReplicas",
    ) in subjects
    assert (
        "baseline-release-differs",
        "release: /source/environmentBinding/name",
    ) in subjects


@pytest.mark.parametrize(
    ("field", "path"),
    [
        ("renderer_revision", "rendererRevision"),
        ("platform_defaults_revision", "platformDefaultsRevision"),
    ],
)
def test_a_baseline_at_another_revision_is_refused(
    root: Path, field: str, path: str
) -> None:
    other = "0123456789abcdef" * 2 + "01234567"
    if field == "renderer_revision":
        baseline, member = (
            replace(baseline_profile(), renderer_revision=other),
            ("renderer"),
        )
    else:
        baseline, member = (
            replace(baseline_profile(), platform_defaults_revision=other),
            "platformDefaults",
        )
    record = build_record(root, baseline=baseline)
    assert found(record) == [
        ("baseline-declaration-differs", f"declaration: /{path}"),
        ("baseline-release-differs", f"release: /source/{member}/revision"),
    ]


def test_a_baseline_with_other_platform_defaults_is_refused(root: Path) -> None:
    """A second defaults file is a second set of caller-facing API values."""
    other = "charts/inferops-llm/other-values.yaml"
    shutil.copyfile(root / DEFAULTS, root / other)
    edit(root / other, "requestTimeoutMs: 120000", "requestTimeoutMs: 60000")
    record = build_record(
        root, baseline=replace(baseline_profile(), platform_defaults=other)
    )
    assert found(record) == [
        ("baseline-declaration-differs", "declaration: /platformDefaults"),
        ("baseline-values-differ", "values: /api/requestTimeoutMs"),
    ]


def test_a_baseline_inside_the_desired_state_is_refused(root: Path) -> None:
    """An Application reads that tree. The baseline is not desired state."""
    inside = (
        f"{DESIRED_STATE_ROOT}/environments/local-docker-desktop/workloads/baseline"
    )
    record = build_record(root, baseline=replace(baseline_profile(), directory=inside))
    assert found(record) == [
        ("baseline-declaration-differs", "declaration: /directory")
    ]
    assert "inside the Git desired state" in record["findings"][0]["detail"]


def test_a_change_to_both_sides_is_comparable_and_is_still_reported(root: Path) -> None:
    """A platform default moves both releases alike. The comparison holds, and the
    committed release and record no longer describe the tree, so the check fails
    until a person writes them again."""
    edit(root / DEFAULTS, "requestTimeoutMs: 120000", "requestTimeoutMs: 60000")
    record = build_record(root)
    assert record["result"] == COMPARABLE
    rules = [finding.rule_id for finding in verify_profile(root)]
    assert set(rules) == {"baseline-release-drifted", "baseline-record-stale"}
    assert write_profile(root) == (True, True)
    assert verify_profile(root) == ()
    assert write_profile(root) == (False, False)


def test_a_hand_edit_of_the_committed_baseline_values_is_refused(root: Path) -> None:
    edit(root / PROFILE_DIRECTORY / VALUES, "replicaCount: 1", "replicaCount: 2")
    findings = verify_profile(root)
    assert {finding.rule_id for finding in findings} == {"baseline-release-drifted"}
    assert all(finding.subject.startswith(PROFILE_DIRECTORY) for finding in findings)


def test_a_file_beside_the_generated_files_is_refused(root: Path) -> None:
    (root / PROFILE_DIRECTORY / "values.yaml").write_text("runtime: {}\n")
    findings = verify_profile(root)
    assert {finding.rule_id for finding in findings} == {"baseline-release-drifted"}
    with pytest.raises(Exception) as refused:
        write_profile(root)
    assert type(refused.value).__name__ == "RegenerationRefused"
    assert (root / PROFILE_DIRECTORY / "values.yaml").is_file()


def test_an_edited_record_is_refused(root: Path) -> None:
    edit(root / RECORD_PATH, '"result": "COMPARABLE"', '"result": "REFUSED"')
    assert [(f.rule_id, f.subject) for f in verify_profile(root)] == [
        ("baseline-record-stale", RECORD_PATH)
    ]


def test_a_missing_record_is_refused_and_a_write_restores_it(root: Path) -> None:
    (root / RECORD_PATH).unlink()
    assert [(f.rule_id, f.subject) for f in verify_profile(root)] == [
        ("baseline-record-stale", RECORD_PATH)
    ]
    assert write_profile(root) == (False, True)
    assert (root / RECORD_PATH).read_bytes() == (REPO_ROOT / RECORD_PATH).read_bytes()


def test_a_missing_profile_directory_is_refused_and_a_write_restores_it(
    root: Path,
) -> None:
    shutil.rmtree(root / PROFILE_DIRECTORY)
    assert {f.rule_id for f in verify_profile(root)} == {"baseline-release-drifted"}
    assert write_profile(root) == (True, False)
    for name in GENERATED_FILES:
        assert (root / PROFILE_DIRECTORY / name).read_bytes() == (
            REPO_ROOT / PROFILE_DIRECTORY / name
        ).read_bytes()


def test_a_hand_edit_of_the_committed_baseline_release_is_refused(
    root: Path,
) -> None:
    edit(
        root / PROFILE_DIRECTORY / RELEASE,
        'workloadVersion: "0.1.0"',
        'workloadVersion: "0.2.0"',
    )
    findings = verify_profile(root)
    assert {finding.rule_id for finding in findings} == {"baseline-release-drifted"}


def test_a_record_with_another_line_ending_is_refused(root: Path) -> None:
    """Byte for byte: the tool does not normalise the record before it compares."""
    path = root / RECORD_PATH
    path.write_bytes(path.read_bytes().replace(b"\n", b"\r\n"))
    assert [(f.rule_id, f.subject) for f in verify_profile(root)] == [
        ("baseline-record-stale", RECORD_PATH)
    ]
    assert write_profile(root) == (False, True)
    assert verify_profile(root) == ()


def test_a_record_path_that_is_a_directory_is_refused_and_not_written(
    root: Path,
) -> None:
    (root / RECORD_PATH).unlink()
    (root / RECORD_PATH).mkdir()
    assert [(f.rule_id, f.subject) for f in verify_profile(root)] == [
        ("baseline-record-stale", RECORD_PATH)
    ]
    with pytest.raises(WriteRefused):
        write_profile(root)
    assert (root / RECORD_PATH).is_dir()


@pytest.mark.parametrize(
    "directory",
    [
        "gitops/environments/local-docker-desktop/workloads/baseline",
        "GitOps/environments/local-docker-desktop/workloads/baseline",
        "./gitops/environments/local-docker-desktop/workloads/baseline",
        "tests/../gitops/environments/local-docker-desktop/workloads/baseline",
        "gitops\\environments\\local-docker-desktop\\workloads\\baseline",
        "/gitops/environments/local-docker-desktop/workloads/baseline",
        "C:/gitops/baseline",
        "tests//baseline",
        "",
    ],
)
def test_each_spelling_of_a_directory_in_the_desired_state_is_refused(
    root: Path, directory: str
) -> None:
    """The directory is one spelling, so no second spelling names that tree."""
    record = build_record(
        root, baseline=replace(baseline_profile(), directory=directory)
    )
    assert found(record) == [
        ("baseline-declaration-differs", "declaration: /directory")
    ]


def test_a_list_entry_that_one_side_lacks_is_refused(root: Path) -> None:
    edit(
        root / BASELINE_CONTRACT,
        "      - docs/proof/serving/v1-s0-003-pr2-runtime-feasibility.md",
        "      - docs/proof/serving/v1-s0-003-pr2-runtime-feasibility.md\n"
        "      - docs/proof/serving/v1-s1-real-runtime-closure.md",
    )
    record = refused_by(root)
    assert found(record) == [
        ("baseline-contract-differs", "contract: /spec/evidence/proofRefs/1")
    ]
    [entry] = [d for d in record["differences"]["contract"] if not d["permitted"]]
    assert "baseline" in entry and "target" not in entry


#: Two documents that one flat list of pointers would read as equal.
ALIASES = [
    pytest.param(
        {"a": ["x", "y"]}, {"a": {"0": "x", "1": "y"}}, "/a", id="list-and-keys"
    ),
    pytest.param(
        {"a": {1: "evil", "1": "same"}}, {"a": {"1": "same"}}, "/a", id="number-key"
    ),
    pytest.param({None: "x"}, {"None": "x"}, "", id="null-key"),
    pytest.param({"a": 1}, {"a": True}, "/a", id="number-and-boolean"),
    pytest.param({"a": 1}, {"a": 1.0}, "/a", id="whole-and-fraction"),
    pytest.param({"a": {}}, {"a": []}, "/a", id="empty-mapping-and-sequence"),
    pytest.param({"a/b": 1}, {"a": {"b": 1}}, None, id="escaped-key"),
]


@pytest.mark.parametrize(("ours", "theirs", "path"), ALIASES)
def test_two_documents_of_another_shape_are_never_read_as_equal(
    ours: Any, theirs: Any, path: str | None
) -> None:
    """The comparison's walk, given documents that no parser of this tree lets
    through. It does not rest on the parsers to tell them apart."""
    from tools.baseline_profile.core import _differences

    differences, _count = _differences("contract", ours, theirs)
    assert differences, "the two documents were read as equal"
    assert all(not entry["permitted"] for entry in differences)
    if path is not None:
        assert [entry["path"] for entry in differences] == [path]


def test_a_replica_range_that_is_not_a_whole_number_is_shown_as_stated(
    root: Path,
) -> None:
    edit(
        root / BASELINE_CONTRACT,
        "minimumReplicas: 1\n    maximumReplicas: 1",
        "minimumReplicas: 1.0\n    maximumReplicas: 1.0",
    )
    record = build_record(root)
    assert record["result"] == REFUSED
    details = " ".join(finding["detail"] for finding in record["findings"])
    assert "null" not in details


# --------------------------------------------------------------------------
# The command
# --------------------------------------------------------------------------


def test_the_record_command_prints_the_record_and_exits_zero(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--record", "--root", str(root)]) == 0
    assert capsys.readouterr().out == record_text(build_record(root))


def test_the_record_command_exits_five_when_the_result_is_refused(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    edit(root / BASELINE_CONTRACT, 'cpu: "6"', 'cpu: "4"')
    assert REFUSED_EXIT == 5
    assert main(["--record", "--root", str(root)]) == REFUSED_EXIT
    assert json.loads(capsys.readouterr().out)["result"] == REFUSED


def test_the_check_command_names_each_rule_it_refuses_under(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    edit(root / BASELINE_CONTRACT, 'cpu: "6"', 'cpu: "4"')
    assert main(["--check", "--root", str(root)]) == 1
    printed = capsys.readouterr().out
    statements = {rule.rule_id: rule.statement for rule in (*RULES, *CHECK_RULES)}
    for rule in (
        "baseline-contract-differs",
        "baseline-values-differ",
        "baseline-release-drifted",
        "baseline-record-stale",
    ):
        assert f"REFUSED  {rule}" in printed
        assert statements[rule] in printed
    assert "findings in the baseline profile" in printed


def test_the_write_command_writes_nothing_for_a_refused_comparison(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    edit(root / BASELINE_CONTRACT, 'cpu: "6"', 'cpu: "4"')
    before = {
        path: path.read_bytes()
        for path in (root / "tests").rglob("*")
        if path.is_file()
    }
    assert main(["--write", "--root", str(root)]) == 1
    printed = capsys.readouterr().out
    assert "REFUSED  nothing was written" in printed
    assert "baseline-contract-differs" in printed
    assert before == {
        path: path.read_bytes()
        for path in (root / "tests").rglob("*")
        if path.is_file()
    }


def test_the_write_command_changes_nothing_in_a_current_tree(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    assert main(["--write", "--root", str(root)]) == 0
    assert capsys.readouterr().out.splitlines() == [
        f"UNCHANGED {PROFILE_DIRECTORY}",
        f"UNCHANGED {RECORD_PATH}",
    ]


def test_a_failed_write_prints_no_path_of_the_host(
    root: Path, capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """The release is written before the record. A record that cannot be written
    leaves the two out of step, and the command says so."""
    edit(root / DEFAULTS, "requestTimeoutMs: 120000", "requestTimeoutMs: 60000")
    written = Path.write_bytes

    def refuse(self: Path, data: bytes) -> int:
        if self.name.endswith(".comparison.v1alpha1.json"):
            raise PermissionError(13, "Permission denied", str(self))
        return written(self, data)

    monkeypatch.setattr(Path, "write_bytes", refuse)
    assert main(["--write", "--root", str(root)]) == 1
    printed = capsys.readouterr().out
    assert "FAILED   PermissionError: Permission denied" in printed
    assert "out of step" in printed
    assert str(root) not in printed
    monkeypatch.undo()
    assert {f.rule_id for f in verify_profile(root)} == {"baseline-record-stale"}
    assert write_profile(root) == (False, True)
    assert verify_profile(root) == ()


def test_the_command_refuses_when_the_target_is_not_declared(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    import tools.baseline_profile.__main__ as command

    def missing() -> None:
        raise KeyError("local-docker-desktop/support-assistant")

    monkeypatch.setattr(command, "target_release", missing)
    assert main(["--check"]) == 1
    assert "REFUSED  no desired-state release has the key" in capsys.readouterr().out


def test_the_command_takes_one_mode() -> None:
    for arguments in ([], ["--check", "--write"], ["--record", "extra"]):
        with pytest.raises(SystemExit) as stopped:
            main(arguments)
        assert stopped.value.code == 2


# --------------------------------------------------------------------------
# 3. The profile is not desired state
# --------------------------------------------------------------------------


def test_the_profile_is_outside_the_desired_state_and_no_release_declares_it() -> None:
    assert not PROFILE_DIRECTORY.startswith(f"{DESIRED_STATE_ROOT}/")
    declared = [
        release.directory for release in (*DECLARED_RELEASES, *DESIRED_STATE_RELEASES)
    ]
    assert PROFILE_DIRECTORY not in declared
    # One desired-state release exists, and it is the target.
    assert [release.directory for release in DESIRED_STATE_RELEASES] == [
        TARGET_DIRECTORY
    ]


def test_the_profile_and_the_record_are_pinned_to_lf() -> None:
    """A checkout that wrote CRLF would change the values digest and the record."""
    git = shutil.which("git")
    if git is None:
        pytest.skip("git is not on PATH")
    paths = [f"{PROFILE_DIRECTORY}/{name}" for name in GENERATED_FILES]
    paths.append(RECORD_PATH)
    result = subprocess.run(
        [git, "check-attr", "eol", "--", *paths],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    assert result.stdout.splitlines() == [f"{path}: eol: lf" for path in paths]


def test_no_application_reads_the_profile() -> None:
    """A tripwire. The baseline is applied nowhere, and the page says so. A change
    that gives it an Application must move this test and that statement."""
    manifests = sorted(APPLICATIONS_DIR.glob("*.yaml"))
    assert manifests, "the Application directory holds no manifest"
    for manifest in manifests:
        text = manifest.read_text(encoding="utf-8")
        assert "experiment-profiles" not in text, manifest.name
        assert "single-runtime-baseline" not in text, manifest.name
    page = DOCUMENT.read_text(encoding="utf-8")
    assert "No Application reads the profile" in page


def test_the_profile_adds_no_contract_document() -> None:
    """The baseline reuses the one-replica contract. It adds no contract document."""
    names = sorted(
        path.name
        for path in (REPO_ROOT / "contracts" / "workload" / "examples" / "valid").glob(
            "*.yaml"
        )
    )
    assert names == [
        "mock-llm-ci.yaml",
        "synchronous-llm-local.yaml",
        "synchronous-llm-secret-refs.yaml",
        "synchronous-llm-two-replicas.yaml",
    ]


# --------------------------------------------------------------------------
# 4. The page says what the tool does
# --------------------------------------------------------------------------


def test_the_page_states_each_rule() -> None:
    page = DOCUMENT.read_text(encoding="utf-8")
    assert [rule.rule_id for rule in RULES] == RULE_IDS
    assert [rule.rule_id for rule in CHECK_RULES] == [
        "baseline-release-drifted",
        "baseline-record-stale",
    ]
    for rule in (*RULES, *CHECK_RULES):
        assert f"| `{rule.rule_id}` | {rule.statement} |" in page, rule.rule_id


def test_the_page_states_each_permitted_path_and_each_limit() -> None:
    page = DOCUMENT.read_text(encoding="utf-8")
    for layer, paths in PERMITTED.items():
        for path, reason in paths.items():
            assert f"| {layer} | `{path}` | `{reason}` |" in page, (layer, path)
    for line in DOES_NOT_ESTABLISH:
        assert line in " ".join(page.split()), line


def test_the_page_states_the_identities_of_the_committed_release() -> None:
    page = DOCUMENT.read_text(encoding="utf-8")
    baseline = load(f"{PROFILE_DIRECTORY}/{RELEASE}")
    target = load(f"{TARGET_DIRECTORY}/{RELEASE}")
    assert f"`{baseline['metadata']['releaseId']}`" in page
    assert f"`{target['metadata']['releaseId']}`" in page
    assert f"`{PROFILE_DIRECTORY}`" in page
    assert f"`{RECORD_PATH}`" in page
