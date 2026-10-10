"""The single-runtime baseline profile, and the comparison that keeps it controlled.

The baseline is two API replicas and one serving runtime replica. The target is
the desired-state release, with two of each. ``tools.baseline_profile`` derives
both releases, reads the install description of each side, and refuses each
difference that is not the runtime replica count, an identity that follows it,
or the generated values file that each side reads. It reads the API image
digest that each side declares, and it refuses a digest that is absent,
malformed, or not the digest of the other side.

These tests hold six things.

1. **The committed profile.** The baseline release and the comparison record are
   what the tool derives, and the differences are the ones restated here.
2. **Each accidental change is refused.** A copy of the inputs is edited in one
   place: a resource ceiling, the runtime image, the model, the owner, a
   caller-facing API value, the binding, a revision, or a replica count. The
   comparison names the rule and the path.
3. **Each one-sided install or readiness input is refused.** The baseline
   states its install inputs in one file, and the target states them in its
   Application. A copy of either is edited in one place: a probe setting, a
   hand-written value, the release name, the namespace, or the chart. An absent
   description, a description that does not parse, and an absent readiness
   input each refuse the comparison too.
4. **The API image digest of each side is required, valid, and equal.** The
   declared comparison inputs state one digest for each side. A copy is edited
   so that a digest is absent, malformed, or another digest, on one side or on
   both. Two equal texts that are not digests are refused too.
5. **The profile is not desired state.** It is outside ``gitops/``, no
   desired-state release names it, and no Application reads it.
6. **The page says what the tool does.** Each rule and each permitted path is in
   the document.

Everything here reads files. Nothing contacts a cluster, and nothing runs Helm.
A test of the chart suite renders both releases with the chart tool.
"""

from __future__ import annotations

import hashlib
import json
import re
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
    COMPARISON_INPUTS_PATH,
    COMPARISON_INPUTS_SCHEMA,
    DIGEST_CATEGORY,
    DIGEST_STATES,
    DOES_NOT_ESTABLISH,
    ELIGIBILITY,
    HELD,
    INSTALL_PATH,
    INSTALL_SCHEMA,
    NOT_EVALUATED,
    NOT_HELD,
    PERMITTED,
    PROFILE_DIRECTORY,
    READINESS_INPUTS,
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
    regenerate,
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
CHART = "charts/inferops-llm"
DEFAULTS = f"{CHART}/values.yaml"
APPLICATION = "infra/argocd/local-docker-desktop-support-assistant.yaml"
INSTALL = (
    "tests/domain/fixtures/experiment-profiles/"
    "single-runtime-baseline.install.v1alpha1.yaml"
)
INPUTS = (
    "tests/domain/fixtures/experiment-profiles/"
    "single-runtime-baseline.comparison-inputs.v1alpha1.yaml"
)
#: The digest that the committed comparison inputs declare for both sides, and
#: the retained read that it was taken from.
DECLARED_DIGEST = (
    "sha256:244251f76e5959c58e52689337298a24af46b34d8fd36b097cb638671eccda56"
)
DIGEST_ORIGIN = (
    "docs/proof/environment/v2-s4-005-pr2-service-endpoint-state-run-1/pods-before.json"
)
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
    "baseline-install-inputs-refused",
    "baseline-install-differs",
    "baseline-effective-values-differ",
    "baseline-readiness-input-unusable",
    "baseline-api-image-digest-unbound",
    "baseline-api-image-digest-contradicted",
]
UNBOUND, CONTRADICTED = RULE_IDS[11:]
#: The rules that need a derived release of each side. The rule that reads the
#: declared digests needs neither a release nor a description.
DERIVED_RULES = [*RULE_IDS[2:7], *RULE_IDS[9:11], CONTRADICTED]
#: The rules that need the install description of each side.
INSTALL_RULES = [*RULE_IDS[8:11], CONTRADICTED]


# --------------------------------------------------------------------------
# A copy of the profile and of its declared inputs, to plant defects in
# --------------------------------------------------------------------------


def copy_inputs(root: Path) -> Path:
    """Copy the profile, the record, and every input of either side.

    The inputs are the files that each release is derived from, the chart, the
    install description of each side, and the declared comparison inputs.
    """
    relatives = {
        PROFILE_DIRECTORY,
        RECORD_PATH,
        MATRIX_PATH,
        BASELINE_CONTRACT,
        TARGET_CONTRACT,
        BINDING,
        OTHER_BINDING,
        TARGET_DIRECTORY,
        CHART,
        APPLICATION,
        INSTALL,
        INPUTS,
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


def with_effective(expected: list[tuple[str, str]]) -> list[tuple[str, str]]:
    """The findings of a changed generated value, with its effective value.

    No hand-written value of either side replaces a generated value. So a
    generated value that differs is a value that the chart receives, and it is
    refused in that layer too, after every earlier rule.
    """
    return expected + [
        ("baseline-effective-values-differ", subject.replace("values:", "effective:"))
        for rule, subject in expected
        if rule == "baseline-values-differ"
    ]


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
    assert f"OK       {INSTALL_PATH}" in result.stdout


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
    assert list(differences) == [
        "declaration",
        "contract",
        "values",
        "release",
        "install",
        "effective",
    ]
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
    assert [
        (d["path"], d["baseline"], d["target"]) for d in differences["install"]
    ] == [
        ("/valuesFile", f"{PROFILE_DIRECTORY}/{VALUES}", f"{TARGET_DIRECTORY}/{VALUES}")
    ]
    # The chart receives the two generated differences, and no other.
    assert [
        (d["path"], d["baseline"], d["target"]) for d in differences["effective"]
    ] == VALUES_DIFFERENCES
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
        "install": [],
        "effective": ["/runtime/replicaCount"],
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
    assert record["effectiveTopology"] == record["topology"]


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
    # The install layer: the description's leaves, and the two chart identities.
    description = load(INSTALL)
    stated = {
        name: description[name]
        for name in ("chart", "release", "valuesFile", "handWrittenValues")
    }
    assert compared["install"] == leaves(stated) + 2
    # The effective layer holds every default of the chart, so it is the largest.
    assert compared["effective"] >= leaves(load(DEFAULTS)) > 100


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
    expected = with_effective(expected)
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
    assert found(refused_by(root)) == with_effective(
        [
            ("baseline-contract-differs", "contract: /spec/resources/cpu"),
            ("baseline-values-differ", "values: /runtime/resources/limits/cpu"),
        ]
    )


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
        **dict.fromkeys(RULE_IDS, HELD),
        "baseline-sources-refused": NOT_HELD,
        **dict.fromkeys(DERIVED_RULES, NOT_EVALUATED),
    }
    # The install descriptions do not need a derived release, so they are compared.
    assert record["differences"].keys() == {"declaration", "install"}
    assert record["releases"] == {} and record["topology"] == {}
    assert record["readinessInputs"] == {} and record["effectiveTopology"] == {}


def test_a_missing_baseline_contract_refuses_the_comparison(root: Path) -> None:
    (root / BASELINE_CONTRACT).unlink()
    record = refused_by(root)
    assert found(record) == [("baseline-sources-refused", "baseline: declared inputs")]
    # The reason names the file under the root, and no path of this host.
    assert BASELINE_CONTRACT in record["findings"][0]["detail"]
    assert str(root) not in json.dumps(record)
    assert states(record) == {
        **dict.fromkeys(RULE_IDS, HELD),
        "baseline-sources-refused": NOT_HELD,
        **dict.fromkeys(DERIVED_RULES, NOT_EVALUATED),
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
        ("baseline-effective-values-differ", "effective: baseline runtimeReplicas"),
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
        ("baseline-effective-values-differ", "effective: baseline apiReplicas"),
        ("baseline-effective-values-differ", "effective: target apiReplicas"),
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
        ("baseline-effective-values-differ", "effective: /api/requestTimeoutMs"),
    ]


def test_a_baseline_inside_the_desired_state_is_refused(root: Path) -> None:
    """An Application reads that tree. The baseline is not desired state."""
    inside = (
        f"{DESIRED_STATE_ROOT}/environments/local-docker-desktop/workloads/baseline"
    )
    record = build_record(root, baseline=replace(baseline_profile(), directory=inside))
    # The description names the values file of the committed profile, so it no
    # longer names the values file of a release in another directory.
    assert found(record) == [
        ("baseline-declaration-differs", "declaration: /directory"),
        ("baseline-install-differs", "install: baseline /valuesFile"),
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
    assert set(rules) == {
        "baseline-release-drifted",
        "baseline-target-release-drifted",
        "baseline-record-stale",
    }
    assert write_profile(root) == (True, True)
    # This tool does not write the target's release. Its own command does.
    assert {finding.rule_id for finding in verify_profile(root)} == {
        "baseline-target-release-drifted"
    }
    assert regenerate(target_release(), root) is True
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
    # The description names the values file of the committed profile, so it no
    # longer names the values file of a release in another directory.
    assert found(record) == [
        ("baseline-declaration-differs", "declaration: /directory"),
        ("baseline-install-differs", "install: baseline /valuesFile"),
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
    assert {f.rule_id for f in verify_profile(root)} == {
        "baseline-record-stale",
        "baseline-target-release-drifted",
    }
    assert write_profile(root) == (False, True)
    assert regenerate(target_release(), root) is True
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
# 3. Each one-sided install or readiness input is refused
# --------------------------------------------------------------------------
#
# The baseline states its install inputs in one file. The target states them in
# its Application. Each test below edits a copy of one of the two, or of the
# chart, and reads the record. Nothing here installs a release or runs Helm.

REFUSED_TIMEOUT = [
    (
        "baseline-install-differs",
        "install: /handWrittenValues/api/probes/readiness/timeoutSeconds",
    ),
    (
        "baseline-effective-values-differ",
        "effective: /api/probes/readiness/timeoutSeconds",
    ),
]


def chart_digest(root: Path) -> str:
    """The digest of the chart's files, computed here again.

    Each file of the chart directory but its page and its render fixtures.
    """
    chart = root / CHART
    names = sorted(
        path.relative_to(chart).as_posix()
        for path in chart.rglob("*")
        if path.is_file()
        and path.relative_to(chart).parts[0] not in ("README.md", "ci")
    )
    assert {"Chart.yaml", "values.yaml", "values.schema.json", ".helmignore"} <= set(
        names
    )
    lines = [
        f"{hashlib.sha256((chart / name).read_bytes()).hexdigest()}  {name}\n"
        for name in names
    ]
    return hashlib.sha256("".join(lines).encode()).hexdigest()


def test_the_two_install_descriptions_state_one_set_of_install_inputs() -> None:
    """Both files are read here without the tool, and compared member by member."""
    baseline, application = load(INSTALL), load(APPLICATION)
    assert INSTALL == INSTALL_PATH
    assert (
        baseline["apiVersion"]
        == INSTALL_SCHEMA
        == ("inferops.io/baseline-install-inputs/v1alpha1")
    )
    assert baseline["kind"] == "BaselineInstallInputs"
    source = application["spec"]["source"]
    assert baseline["chart"] == {
        "repository": source["repoURL"],
        "revision": source["targetRevision"],
        "path": source["path"],
    }
    assert baseline["chart"]["path"] == CHART
    assert baseline["release"] == {
        "name": source["helm"]["releaseName"],
        "namespace": application["spec"]["destination"]["namespace"],
        "server": application["spec"]["destination"]["server"],
    }
    assert baseline["release"] == {
        "name": "inferops",
        "namespace": "inferops-release",
        "server": "https://kubernetes.default.svc",
    }
    assert baseline["handWrittenValues"] == source["helm"]["valuesObject"]
    assert baseline["valuesFile"] == f"{PROFILE_DIRECTORY}/{VALUES}"
    assert source["helm"]["valueFiles"] == [f"/{TARGET_DIRECTORY}/{VALUES}"]
    # No hand-written value replaces a generated one, so the generated topology
    # is the topology that the chart receives.
    generated = load(f"{PROFILE_DIRECTORY}/{VALUES}")
    assert "replicaCount" not in json.dumps(baseline["handWrittenValues"])
    assert generated["runtime"]["replicaCount"] == 1


def test_the_record_states_the_install_inputs_of_each_side() -> None:
    record = build_record()
    assert record["installSources"] == {"baseline": INSTALL, "target": APPLICATION}
    install = record["installInputs"]
    assert install.keys() == {"baseline", "target"}
    description = load(INSTALL)
    for side in ("baseline", "target"):
        assert install[side]["chart"] == {
            **description["chart"],
            "version": load(f"{CHART}/Chart.yaml")["version"],
            "contentSha256": chart_digest(REPO_ROOT),
        }
        assert install[side]["release"] == description["release"]
        assert install[side]["handWrittenValues"] == description["handWrittenValues"]
    assert install["baseline"]["valuesFile"] == f"{PROFILE_DIRECTORY}/{VALUES}"
    assert install["target"]["valuesFile"] == f"{TARGET_DIRECTORY}/{VALUES}"


def test_the_record_states_each_readiness_input_of_each_side() -> None:
    record = build_record()
    readiness = record["readinessInputs"]
    assert len(READINESS_INPUTS) == len(set(READINESS_INPUTS)) == 24
    for side in ("baseline", "target"):
        assert list(readiness[side]) == list(READINESS_INPUTS)
    assert readiness["baseline"] == readiness["target"]
    stated = readiness["baseline"]
    # Restated from the chart's defaults. No other document states a probe.
    assert stated["/api/readinessPath"] == "/health/ready"
    assert stated["/api/livenessPath"] == "/health/live"
    assert stated["/api/probes/readiness/timeoutSeconds"] == 5
    assert stated["/api/probes/startup/budgetMs"] == 60000
    assert stated["/runtime/healthPath"] == "/health"
    assert stated["/runtime/probes/startup/budgetMs"] == 600000
    assert stated["/runtime/probes/readiness/timeoutSeconds"] == 3
    assert stated["/runtime/startupBudgetMs"] == 300000
    assert stated["/api/probes/enabled"] is True
    assert stated["/runtime/probes/enabled"] is True


def test_the_readiness_inputs_are_the_values_the_probe_templates_read() -> None:
    """A tripwire. A probe value that the chart starts to read is named here."""
    helpers = (REPO_ROOT / CHART / "templates" / "_helpers.tpl").read_text(
        encoding="utf-8"
    )
    read = set()
    for tier, block in re.findall(
        r'define "inferops-llm\.(api|runtime)\.probes" -}}(.*?){{- end -}}',
        helpers,
        flags=re.DOTALL,
    ):
        names = set(re.findall(rf"\.Values\.{tier}\.([A-Za-z.]+)", block))
        assert names, tier
        read |= {f"/{tier}/{name.replace('.', '/')}" for name in names}
    assert len(read) == 23, sorted(read)
    # The chart's validation compares the runtime's probe budget with this value.
    assert set(READINESS_INPUTS) - read == {"/runtime/startupBudgetMs"}
    assert read <= set(READINESS_INPUTS)


def test_every_record_states_eligibility_as_not_established() -> None:
    """COMPARABLE is about committed inputs. No file resolves the caller profile."""
    record = build_record()
    assert record["result"] == COMPARABLE
    assert record["experimentEligibility"] == ELIGIBILITY == "not-established"
    assert [
        (entry["input"], entry["sides"]) for entry in record["unresolvedInputs"]
    ] == [
        ("caller-profile", ["baseline", "target"]),
    ]


#: An addition to the hand-written values of one description, by the file and
#: the line it follows.
TARGET_API_IMAGE = "            pullPolicy: Never\n"
BASELINE_API_IMAGE = "      pullPolicy: Never\n"
BASELINE_RUNTIME_IMAGE = "      pullPolicy: IfNotPresent\n"

#: One edit of one description, and each finding it must give.
ONE_SIDED = [
    pytest.param(
        APPLICATION,
        TARGET_API_IMAGE,
        TARGET_API_IMAGE
        + "          probes:\n            readiness:\n              timeoutSeconds: 1\n",
        REFUSED_TIMEOUT,
        id="target-api-readiness-timeout",
    ),
    pytest.param(
        INSTALL,
        BASELINE_API_IMAGE,
        BASELINE_API_IMAGE
        + "    probes:\n      readiness:\n        timeoutSeconds: 1\n",
        REFUSED_TIMEOUT,
        id="baseline-api-readiness-timeout",
    ),
    pytest.param(
        INSTALL,
        BASELINE_RUNTIME_IMAGE,
        BASELINE_RUNTIME_IMAGE
        + "    probes:\n      startup:\n        budgetMs: 900000\n",
        [
            (
                "baseline-install-differs",
                "install: /handWrittenValues/runtime/probes/startup/budgetMs",
            ),
            (
                "baseline-effective-values-differ",
                "effective: /runtime/probes/startup/budgetMs",
            ),
        ],
        id="baseline-runtime-startup-budget",
    ),
    pytest.param(
        INSTALL,
        BASELINE_API_IMAGE,
        BASELINE_API_IMAGE
        + "    probes:\n      readiness:\n        timeoutSeconds: null\n",
        [
            *REFUSED_TIMEOUT,
            (
                "baseline-readiness-input-unusable",
                "effective: baseline /api/probes/readiness/timeoutSeconds",
            ),
        ],
        id="baseline-removes-a-readiness-input",
    ),
    pytest.param(
        INSTALL,
        BASELINE_API_IMAGE,
        "      pullPolicy: Always\n",
        [
            (
                "baseline-install-differs",
                "install: /handWrittenValues/api/image/pullPolicy",
            ),
            ("baseline-effective-values-differ", "effective: /api/image/pullPolicy"),
        ],
        id="baseline-hand-written-value",
    ),
    pytest.param(
        APPLICATION,
        "            mountPath: /models\n",
        "",
        # The chart's default is the removed value, so the chart receives one
        # value on both sides. The two descriptions still differ.
        [
            (
                "baseline-install-differs",
                "install: /handWrittenValues/model/cache/mountPath",
            )
        ],
        id="target-lacks-a-hand-written-value",
    ),
    pytest.param(
        INSTALL,
        BASELINE_API_IMAGE,
        BASELINE_API_IMAGE + "      digest: sha256:" + "a" * 64 + "\n",
        [
            (
                "baseline-install-differs",
                "install: /handWrittenValues/api/image/digest",
            ),
            ("baseline-effective-values-differ", "effective: /api/image/digest"),
            (CONTRADICTED, "effective: baseline /api/image/digest"),
        ],
        id="baseline-api-image-digest",
    ),
    pytest.param(
        INSTALL,
        BASELINE_RUNTIME_IMAGE,
        BASELINE_RUNTIME_IMAGE + "    replicaCount: 2\n",
        # The hand-written count replaces the generated one, so the chart
        # receives two runtime replicas on both sides.
        [
            (
                "baseline-install-differs",
                "install: /handWrittenValues/runtime/replicaCount",
            ),
            ("baseline-effective-values-differ", "effective: baseline runtimeReplicas"),
        ],
        id="baseline-hand-written-replica-count",
    ),
    pytest.param(
        INSTALL,
        "    scrapeAnnotations: true\n",
        "    scrapeAnnotations: false\n",
        [
            (
                "baseline-install-differs",
                "install: /handWrittenValues/telemetry/scrapeAnnotations",
            ),
            (
                "baseline-effective-values-differ",
                "effective: /telemetry/scrapeAnnotations",
            ),
        ],
        id="baseline-scrape-annotations",
    ),
    pytest.param(
        APPLICATION,
        "server: https://kubernetes.default.svc",
        "server: https://other-cluster.example:6443",
        [("baseline-install-differs", "install: /release/server")],
        id="target-cluster-address",
    ),
    pytest.param(
        INSTALL,
        "  name: inferops\n",
        "  name: inferops-baseline\n",
        [("baseline-install-differs", "install: /release/name")],
        id="baseline-release-name",
    ),
    pytest.param(
        APPLICATION,
        "namespace: inferops-release",
        "namespace: inferops-other",
        [("baseline-install-differs", "install: /release/namespace")],
        id="target-namespace",
    ),
    pytest.param(
        INSTALL,
        "revision: main",
        "revision: v1.0.0",
        [("baseline-install-differs", "install: /chart/revision")],
        id="baseline-chart-revision",
    ),
    pytest.param(
        APPLICATION,
        "repoURL: https://github.com/asadhanif3188/InferOps.git",
        "repoURL: https://example.invalid/other.git",
        [("baseline-install-differs", "install: /chart/repository")],
        id="target-chart-repository",
    ),
    pytest.param(
        INSTALL,
        f"valuesFile: {PROFILE_DIRECTORY}/{VALUES}",
        f"valuesFile: {TARGET_DIRECTORY}/{VALUES}",
        [("baseline-install-differs", "install: baseline /valuesFile")],
        id="baseline-names-the-targets-values-file",
    ),
]


@pytest.mark.parametrize(("relative", "old", "new", "expected"), ONE_SIDED)
def test_a_one_sided_install_or_readiness_input_is_refused(
    root: Path, relative: str, old: str, new: str, expected: list[tuple[str, str]]
) -> None:
    edit(root / relative, old, new)
    record = refused_by(root)
    assert found(record) == expected
    broken = {rule for rule, _subject in expected}
    assert states(record) == {
        rule: NOT_HELD if rule in broken else HELD for rule in RULE_IDS
    }
    # The generated releases did not move, so the comparison of them holds.
    assert record["differences"]["values"] == build_record()["differences"]["values"]
    rules = {finding.rule_id for finding in verify_profile(root)}
    assert rules == broken | {"baseline-record-stale"}
    with pytest.raises(WriteRefused):
        write_profile(root)


def test_a_readiness_input_changed_in_the_target_alone_is_refused_by_the_command(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """One probe timeout is set in the target's Application, and nowhere else.

    Before the install descriptions were compared, this edit left the record as
    it was, the result ``COMPARABLE``, and the check at exit status 0.
    """
    before = build_record(root)
    application = yaml.safe_load((root / APPLICATION).read_text(encoding="utf-8"))
    hand_written = application["spec"]["source"]["helm"]["valuesObject"]
    hand_written["api"]["probes"] = {"readiness": {"timeoutSeconds": 1}}
    (root / APPLICATION).write_text(
        yaml.safe_dump(application, sort_keys=False), encoding="utf-8"
    )
    after = build_record(root)
    assert (before["result"], after["result"]) == (COMPARABLE, REFUSED)
    assert found(after) == REFUSED_TIMEOUT
    [entry] = [d for d in after["differences"]["effective"] if not d["permitted"]]
    assert (entry["baseline"], entry["target"]) == (5, 1)
    assert after["readinessInputs"]["baseline"] != after["readinessInputs"]["target"]
    assert main(["--record", "--root", str(root)]) == REFUSED_EXIT
    capsys.readouterr()
    assert main(["--check", "--root", str(root)]) == 1
    printed = capsys.readouterr().out
    assert "REFUSED  baseline-install-differs" in printed
    assert "REFUSED  baseline-effective-values-differ" in printed
    assert main(["--write", "--root", str(root)]) == 1
    assert "REFUSED  nothing was written" in capsys.readouterr().out


def test_one_change_to_both_descriptions_is_comparable_and_is_still_reported(
    root: Path,
) -> None:
    """Both sides are given one probe timeout. The comparison holds, and the
    committed record no longer states the inputs of the tree."""
    addition = "probes:\n{0}  readiness:\n{0}    timeoutSeconds: 4\n"
    edit(
        root / APPLICATION,
        TARGET_API_IMAGE,
        TARGET_API_IMAGE + " " * 10 + addition.format(" " * 10),
    )
    edit(
        root / INSTALL,
        BASELINE_API_IMAGE,
        BASELINE_API_IMAGE + " " * 4 + addition.format(" " * 4),
    )
    record = build_record(root)
    assert record["result"] == COMPARABLE
    for side in ("baseline", "target"):
        assert (
            record["readinessInputs"][side]["/api/probes/readiness/timeoutSeconds"] == 4
        )
    assert [f.rule_id for f in verify_profile(root)] == ["baseline-record-stale"]
    assert write_profile(root) == (False, True)
    assert verify_profile(root) == ()


def test_a_hand_written_replica_count_on_both_sides_is_refused(root: Path) -> None:
    """Two equal descriptions that both replace the variable leave no baseline."""
    edit(
        root / APPLICATION,
        "            pullPolicy: IfNotPresent\n",
        "            pullPolicy: IfNotPresent\n          replicaCount: 2\n",
    )
    edit(
        root / INSTALL,
        BASELINE_RUNTIME_IMAGE,
        BASELINE_RUNTIME_IMAGE + "    replicaCount: 2\n",
    )
    record = refused_by(root)
    assert found(record) == [
        ("baseline-effective-values-differ", "effective: baseline runtimeReplicas")
    ]
    assert record["differences"]["install"] == build_record()["differences"]["install"]
    assert record["topology"]["baseline"]["runtimeReplicas"] == 1
    assert record["effectiveTopology"]["baseline"]["runtimeReplicas"] == 2


def restate(root: Path, digest: str) -> None:
    """State one API image digest in the hand-written values of both descriptions."""
    line = f"digest: {digest}\n"
    edit(root / APPLICATION, TARGET_API_IMAGE, TARGET_API_IMAGE + " " * 12 + line)
    edit(root / INSTALL, BASELINE_API_IMAGE, BASELINE_API_IMAGE + " " * 6 + line)


def test_two_descriptions_that_state_the_declared_digest_are_comparable(
    root: Path,
) -> None:
    """A description may state the digest too. It must be the declared one."""
    restate(root, DECLARED_DIGEST)
    record = build_record(root)
    assert record["result"] == COMPARABLE
    assert record["apiImageIdentity"]["statedByEffectiveValues"] == {
        "baseline": DECLARED_DIGEST,
        "target": DECLARED_DIGEST,
    }
    assert [entry["input"] for entry in record["unresolvedInputs"]] == [
        "caller-profile"
    ]
    assert record["experimentEligibility"] == "not-established"


def test_a_digest_in_a_description_that_is_not_read_does_not_leave_it_bound(
    root: Path,
) -> None:
    """The target states another digest, and the baseline's description is absent.

    No effective values are derived, so the rule on them is not evaluated. A
    record of that state must not say that the digest is bound.
    """
    line = "digest: sha256:" + "b" * 64 + "\n"
    edit(root / APPLICATION, TARGET_API_IMAGE, TARGET_API_IMAGE + " " * 12 + line)
    (root / INSTALL).unlink()
    record = refused_by(root)
    assert states(record)[UNBOUND] == HELD
    assert states(record)[CONTRADICTED] == NOT_EVALUATED
    identity = record["apiImageIdentity"]
    assert identity["bound"] is False and "digest" not in identity
    assert identity["effectiveValuesCompared"] is False
    assert record["unresolvedInputs"][0]["input"] == "api-image-digest"


@pytest.mark.parametrize("stated", ['""', "null"], ids=["empty-text", "null"])
def test_an_empty_or_removed_digest_in_both_descriptions_states_no_digest(
    root: Path, stated: str
) -> None:
    """An empty text is the chart's default, and a null removes the member.

    Neither states a digest, so neither contradicts the declared one. The
    chart refuses to render a release whose digest is empty, and this tool
    renders nothing: the page states that limit.
    """
    restate(root, stated)
    record = build_record(root)
    assert record["result"] == COMPARABLE
    assert record["apiImageIdentity"]["statedByEffectiveValues"] == {}


@pytest.mark.parametrize(
    "stated",
    ["' '", "|\n" + " " * 14 + DECLARED_DIGEST],
    ids=["a-space", "the-declared-digest-and-a-newline"],
)
def test_a_text_near_the_declared_digest_in_both_descriptions_is_refused(
    root: Path, stated: str
) -> None:
    restate(root, stated)
    assert found(refused_by(root)) == [
        (CONTRADICTED, "effective: baseline /api/image/digest"),
        (CONTRADICTED, "effective: target /api/image/digest"),
    ]


def test_two_descriptions_that_state_another_valid_digest_are_refused(
    root: Path,
) -> None:
    """Two descriptions agree with each other and not with the declared digest.

    The install layer and the effective layer hold, because the two sides are
    equal there. The comparison is refused, because two digests are stated for
    each side.
    """
    restate(root, "sha256:" + "b" * 64)
    record = refused_by(root)
    assert found(record) == [
        (CONTRADICTED, "effective: baseline /api/image/digest"),
        (CONTRADICTED, "effective: target /api/image/digest"),
    ]
    assert states(record) == {**dict.fromkeys(RULE_IDS, HELD), CONTRADICTED: NOT_HELD}
    assert record["apiImageIdentity"]["bound"] is False
    assert "digest" not in record["apiImageIdentity"]
    assert record["unresolvedInputs"][0]["sides"] == ["baseline", "target"]


def cut(path: Path, start: str, end: str | None) -> None:
    """Remove the text from ``start`` up to ``end``, or up to the end of the file."""
    text = path.read_bytes().decode("utf-8")
    assert text.count(start) == 1, start
    head, tail = text.split(start)
    kept = "" if end is None else end + tail.split(end, 1)[1]
    path.write_bytes((head + kept).encode("utf-8"))


def hand_written_as_a_list(path: Path) -> None:
    cut(path, "handWrittenValues:\n", None)
    path.write_bytes(path.read_bytes() + b"handWrittenValues: []\n")


def replaced(old: str, new: str) -> Any:
    return lambda path: edit(path, old, new)


#: One description that is not read whole, and a part of the reason.
UNREADABLE = [
    pytest.param(
        "baseline", Path.unlink, "is not a regular file", id="baseline-absent"
    ),
    pytest.param(
        "baseline",
        lambda path: path.write_bytes(b"chart: [\n"),
        "is not YAML",
        id="baseline-not-yaml",
    ),
    pytest.param(
        "baseline",
        lambda path: path.write_bytes(b"\xff\xfe\x00"),
        "is not UTF-8 text",
        id="baseline-not-text",
    ),
    pytest.param(
        "baseline",
        lambda path: path.write_bytes(b""),
        "states no mapping at the document",
        id="baseline-empty",
    ),
    pytest.param(
        "baseline",
        replaced(
            "kind: BaselineInstallInputs", "kind: BaselineInstallInputs\nparameters: []"
        ),
        "does not read: parameters",
        id="baseline-states-another-member",
    ),
    pytest.param(
        "baseline",
        lambda path: cut(path, "release:\n", "valuesFile:"),
        "states no mapping at release",
        id="baseline-states-no-release",
    ),
    pytest.param(
        "baseline",
        replaced("  namespace: inferops-release\n", ""),
        "states no text at namespace of release",
        id="baseline-states-no-namespace",
    ),
    pytest.param(
        "baseline",
        replaced("revision: main", 'revision: ""'),
        "states no text at revision of chart",
        id="baseline-states-an-empty-revision",
    ),
    pytest.param(
        "baseline",
        replaced("/v1alpha1\n", "/v1alpha9\n"),
        "is not a BaselineInstallInputs document",
        id="baseline-of-another-schema",
    ),
    pytest.param(
        "baseline",
        lambda path: cut(path, "handWrittenValues:\n", None),
        "states no mapping at handWrittenValues",
        id="baseline-states-no-hand-written-values",
    ),
    pytest.param(
        "baseline",
        replaced(f"path: {CHART}", f"path: ../{CHART}"),
        "a chart path that is not one relative POSIX path",
        id="baseline-chart-path-leaves-the-tree",
    ),
    pytest.param(
        "baseline",
        replaced(f"path: {CHART}", "path: charts/absent"),
        "charts/absent is not a directory of this tree",
        id="baseline-chart-is-absent",
    ),
    pytest.param(
        "baseline",
        replaced(
            f"valuesFile: {PROFILE_DIRECTORY}", f"valuesFile: /{PROFILE_DIRECTORY}"
        ),
        "a values file that is not one relative POSIX path",
        id="baseline-values-file-is-absolute",
    ),
    pytest.param(
        "baseline",
        replaced("  name: inferops\n", "  name: inferops\n  name: other\n"),
        "states the key name twice",
        id="baseline-states-a-key-twice",
    ),
    pytest.param(
        "baseline",
        replaced(
            "handWrittenValues:\n", "handWrittenValues: &again\n  again: *again\n"
        ),
        "refers to itself or is nested too deeply",
        id="baseline-refers-to-itself",
    ),
    pytest.param(
        "baseline",
        replaced(f"path: {CHART}", "path: Charts/inferops-llm"),
        "Charts/inferops-llm",
        id="baseline-chart-path-in-another-case",
    ),
    pytest.param(
        "baseline",
        hand_written_as_a_list,
        "states no mapping at handWrittenValues",
        id="baseline-hand-written-values-are-a-list",
    ),
    pytest.param("target", Path.unlink, "is not a regular file", id="target-absent"),
    pytest.param(
        "target",
        lambda path: path.write_bytes(
            path.read_bytes() + b"operation:\n  sync:\n    revision: other\n"
        ),
        "does not read: operation",
        id="target-states-an-operation",
    ),
    pytest.param(
        "target",
        replaced(
            "  labels:\n", "  annotations:\n    example.invalid/option: x\n  labels:\n"
        ),
        "does not read: annotations",
        id="target-states-an-annotation",
    ),
    pytest.param(
        "target",
        replaced("    server: https://kubernetes.default.svc\n", ""),
        "states no text at server of spec.destination",
        id="target-states-no-cluster-address",
    ),
    pytest.param(
        "target",
        replaced(
            "      releaseName: inferops\n",
            "      releaseName: inferops\n      releaseName: other\n",
        ),
        "states the key releaseName twice",
        id="target-states-a-key-twice",
    ),
    pytest.param(
        "target",
        replaced("      valueFiles:\n        - /", "      valueFiles:\n        - "),
        "does not name one values file",
        id="target-values-file-is-not-from-the-root",
    ),
    pytest.param(
        "target",
        replaced("kind: Application", "kind: ApplicationSet"),
        "is not an Application",
        id="target-of-another-kind",
    ),
    pytest.param(
        "target",
        replaced(
            "      releaseName: inferops\n",
            "      releaseName: inferops\n      parameters:\n"
            "        - name: api.probes.readiness.timeoutSeconds\n"
            '          value: "1"\n',
        ),
        "does not read: parameters",
        id="target-states-a-parameter",
    ),
    pytest.param(
        "target",
        replaced("  source:\n", "  sources:\n"),
        "does not read: sources",
        id="target-states-several-sources",
    ),
    pytest.param(
        "target",
        replaced("      valueFiles:\n", "      valueFiles:\n        - /other.yaml\n"),
        "does not name one values file",
        id="target-reads-two-values-files",
    ),
    pytest.param(
        "target",
        lambda path: cut(path, "      valuesObject:\n", "  destination:"),
        "states no mapping at valuesObject",
        id="target-states-no-hand-written-values",
    ),
    pytest.param(
        "target",
        replaced("    namespace: inferops-release\n", ""),
        "states no text at namespace of spec.destination",
        id="target-states-no-namespace",
    ),
]


@pytest.mark.parametrize(("side", "damage", "reason"), UNREADABLE)
def test_a_description_that_is_not_read_whole_refuses_the_comparison(
    root: Path, side: str, damage: Any, reason: str
) -> None:
    """An absent or malformed description is not read as an equal one."""
    damage(root / (INSTALL if side == "baseline" else APPLICATION))
    record = refused_by(root)
    assert found(record) == [
        ("baseline-install-inputs-refused", f"{side}: install inputs")
    ]
    assert reason in record["findings"][0]["detail"]
    assert states(record) == {
        **dict.fromkeys(RULE_IDS, HELD),
        "baseline-install-inputs-refused": NOT_HELD,
        **dict.fromkeys(INSTALL_RULES, NOT_EVALUATED),
    }
    other = "target" if side == "baseline" else "baseline"
    assert list(record["installInputs"]) == [other]
    assert record["differences"].keys() == {
        "declaration",
        "contract",
        "values",
        "release",
    }
    assert record["readinessInputs"] == {} and record["effectiveTopology"] == {}
    # The declared digests are valid. No effective values exist, so nothing
    # compared a description with them, and the digest is not bound.
    identity = record["apiImageIdentity"]
    assert {stated["state"] for stated in identity["sides"].values()} == {"valid"}
    assert identity["effectiveValuesCompared"] is False
    assert identity["bound"] is False and "digest" not in identity
    assert [(e["input"], e["sides"]) for e in record["unresolvedInputs"]] == [
        ("api-image-digest", ["baseline", "target"]),
        ("caller-profile", ["baseline", "target"]),
    ]
    # No path of this host is stated.
    assert str(root) not in json.dumps(record)
    assert "baseline-install-inputs-refused" in {
        finding.rule_id for finding in verify_profile(root)
    }
    with pytest.raises(WriteRefused):
        write_profile(root)


@pytest.mark.parametrize(
    ("damage", "reason"),
    [
        (lambda chart: shutil.rmtree(chart / "templates"), "holds no template"),
        (
            lambda chart: (chart / "values.schema.json").unlink(),
            f"{CHART}/values.schema.json is not a regular file",
        ),
        (
            lambda chart: (chart / "Chart.yaml").write_text("- 1\n"),
            f"{CHART}/Chart.yaml is not a mapping",
        ),
        (
            lambda chart: edit(chart / "Chart.yaml", "\nversion: ", "\nchartVersion: "),
            "states no text at version of the chart document",
        ),
    ],
    ids=["no-template", "no-schema", "chart-document-is-a-list", "no-version"],
)
def test_a_chart_that_is_not_read_whole_refuses_both_sides(
    root: Path, damage: Any, reason: str
) -> None:
    """Both descriptions name the one chart, so neither side states a chart."""
    damage(root / CHART)
    record = refused_by(root)
    assert found(record) == [
        ("baseline-install-inputs-refused", "baseline: install inputs"),
        ("baseline-install-inputs-refused", "target: install inputs"),
    ]
    assert all(reason in finding["detail"] for finding in record["findings"])
    assert record["installInputs"] == {}
    assert states(record) == {
        **dict.fromkeys(RULE_IDS, HELD),
        "baseline-install-inputs-refused": NOT_HELD,
        **dict.fromkeys(INSTALL_RULES, NOT_EVALUATED),
    }
    assert str(root) not in json.dumps(record)


def test_an_absent_readiness_input_is_not_read_as_an_equal_one(root: Path) -> None:
    """The chart's defaults lose one probe setting. Both sides then lack it, the
    two documents of effective values are equal there, and both are refused."""
    edit(root / DEFAULTS, "      timeoutSeconds: 5\n", "")
    record = refused_by(root)
    pointer = "/api/probes/readiness/timeoutSeconds"
    assert found(record) == [
        ("baseline-readiness-input-unusable", f"effective: baseline {pointer}"),
        ("baseline-readiness-input-unusable", f"effective: target {pointer}"),
    ]
    assert all(entry["permitted"] for entry in record["differences"]["effective"])
    for side in ("baseline", "target"):
        assert pointer not in record["readinessInputs"][side]
        assert len(record["readinessInputs"][side]) == 23


def test_the_chart_digest_follows_the_files_a_render_reads(root: Path) -> None:
    before = build_record(root)["installInputs"]["target"]["chart"]["contentSha256"]
    assert before == chart_digest(root) == chart_digest(REPO_ROOT)
    # A page of the chart and a render fixture are not read by a render.
    (root / CHART / "README.md").write_text("another page\n", encoding="utf-8")
    (root / CHART / "ci" / "real-values.yaml").write_text("{}\n", encoding="utf-8")
    assert build_record(root) == build_record()
    digests = [before]
    #: A file of the chart, what is written to it, and whether it is appended.
    edits = [
        ("templates/api-service.yaml", b"# one more line\n", True),
        # The ignore file decides which templates a render reads.
        (".helmignore", b"networkpolicy.yaml\n", True),
        # A subchart and a definition file are read by a render too.
        ("charts/other/templates/x.yaml", b"a: 1\n", False),
        ("crds/x.yaml", b"a: 1\n", False),
    ]
    for name, data, appended in edits:
        path = root / CHART / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes((path.read_bytes() if appended else b"") + data)
        record = build_record(root)
        assert record["result"] == COMPARABLE
        for side in ("baseline", "target"):
            after = record["installInputs"][side]["chart"]["contentSha256"]
            assert after == chart_digest(root)
        assert after not in digests
        digests.append(after)
    assert [f.rule_id for f in verify_profile(root)] == ["baseline-record-stale"]


def test_another_chart_path_on_one_side_is_refused(root: Path) -> None:
    """A second chart directory with the same files. The two paths differ, and the
    two digests do not."""
    shutil.copytree(root / CHART, root / "charts" / "other")
    edit(root / INSTALL, f"path: {CHART}", "path: charts/other")
    record = refused_by(root)
    assert found(record) == [("baseline-install-differs", "install: /chart/path")]
    charts = [record["installInputs"][side]["chart"] for side in ("baseline", "target")]
    assert charts[0]["contentSha256"] == charts[1]["contentSha256"]


def test_how_the_target_is_delivered_is_stated_and_not_compared(root: Path) -> None:
    """The project and the sync policy of the Application. The baseline names no
    controller, so a change is not a difference. It makes the record stale."""
    assert build_record()["targetDelivery"] == {
        "application": "local-docker-desktop-support-assistant",
        "project": "inferops-workloads",
        "syncPolicy": {"automated": {"prune": False, "selfHeal": True}},
    }
    for old, new, member, stated in (
        ("project: inferops-workloads", "project: default", "project", "default"),
        (
            "selfHeal: true",
            "selfHeal: false",
            "syncPolicy",
            {"automated": {"prune": False, "selfHeal": False}},
        ),
    ):
        edit(root / APPLICATION, old, new)
        record = build_record(root)
        assert record["result"] == COMPARABLE
        assert record["targetDelivery"][member] == stated
        assert [f.rule_id for f in verify_profile(root)] == ["baseline-record-stale"]


def test_a_hand_edit_of_the_committed_target_values_is_refused(root: Path) -> None:
    """The comparison derives the generated values. The check holds that the file
    the target's description names is the derived one."""
    path = root / TARGET_DIRECTORY / VALUES
    edit(path, "  replicaCount: 2\n  resources:", "  replicaCount: 7\n  resources:")
    assert build_record(root) == build_record()
    assert {f.rule_id for f in verify_profile(root)} == {
        "baseline-target-release-drifted"
    }
    path.unlink()
    assert {f.rule_id for f in verify_profile(root)} == {
        "baseline-target-release-drifted"
    }


@pytest.mark.parametrize(
    ("old", "new", "pointer", "stated"),
    [
        (
            "      timeoutSeconds: 5\n",
            '      timeoutSeconds: "5"\n',
            "/api/probes/readiness/timeoutSeconds",
            "5",
        ),
        (
            "      timeoutSeconds: 5\n",
            "      timeoutSeconds: 0\n",
            "/api/probes/readiness/timeoutSeconds",
            0,
        ),
        (
            "      timeoutSeconds: 5\n",
            "      timeoutSeconds: []\n",
            "/api/probes/readiness/timeoutSeconds",
            [],
        ),
        (
            "  readinessPath: /health/ready\n",
            '  readinessPath: ""\n',
            "/api/readinessPath",
            "",
        ),
        (
            "  healthPath: /health\n",
            "  healthPath: health\n",
            "/runtime/healthPath",
            "health",
        ),
    ],
    ids=["text-for-a-number", "zero", "list", "empty-path", "path-without-a-slash"],
)
def test_a_readiness_input_of_an_unusable_value_is_refused_on_both_sides(
    root: Path, old: str, new: str, pointer: str, stated: Any
) -> None:
    """Both sides hold one value, and it is not a value that a probe can use."""
    edit(root / DEFAULTS, old, new)
    record = refused_by(root)
    assert found(record) == [
        ("baseline-readiness-input-unusable", f"effective: baseline {pointer}"),
        ("baseline-readiness-input-unusable", f"effective: target {pointer}"),
    ]
    for side in ("baseline", "target"):
        assert record["readinessInputs"][side][pointer] == stated


def test_probes_switched_to_a_text_on_both_sides_are_refused(root: Path) -> None:
    """A plain ``n`` is a text for this parser and false for another one."""
    addition = "probes:\n{0}  enabled: n\n"
    edit(
        root / APPLICATION,
        "            pullPolicy: IfNotPresent\n",
        "            pullPolicy: IfNotPresent\n" + " " * 10 + addition.format(" " * 10),
    )
    edit(
        root / INSTALL,
        BASELINE_RUNTIME_IMAGE,
        BASELINE_RUNTIME_IMAGE + " " * 4 + addition.format(" " * 4),
    )
    assert found(refused_by(root)) == [
        (
            "baseline-readiness-input-unusable",
            "effective: baseline /runtime/probes/enabled",
        ),
        (
            "baseline-readiness-input-unusable",
            "effective: target /runtime/probes/enabled",
        ),
    ]


def test_one_text_that_is_not_a_digest_in_both_descriptions_is_refused(
    root: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """Both descriptions state ``abc`` as the API image digest.

    Until the digest was a required input, this edit gave ``COMPARABLE`` and
    exit status 0, and this test expected that. Two equal texts are not one
    usable digest.
    """
    restate(root, "abc")
    record = refused_by(root)
    assert found(record) == [
        (CONTRADICTED, "effective: baseline /api/image/digest"),
        (CONTRADICTED, "effective: target /api/image/digest"),
    ]
    assert record["apiImageIdentity"]["statedByEffectiveValues"] == {
        "baseline": "abc",
        "target": "abc",
    }
    assert main(["--record", "--root", str(root)]) == REFUSED_EXIT
    capsys.readouterr()
    assert main(["--check", "--root", str(root)]) == 1
    assert f"REFUSED  {CONTRADICTED}" in capsys.readouterr().out
    with pytest.raises(WriteRefused):
        write_profile(root)


# --------------------------------------------------------------------------
# 4. The API image digest of each side is required, valid, and equal
# --------------------------------------------------------------------------

OTHER_DIGEST = "sha256:" + "c" * 64
BASELINE_LINE = f"  baseline: {DECLARED_DIGEST}\n"
TARGET_LINE = f"  target: {DECLARED_DIGEST}\n"
AT_BASELINE = (UNBOUND, "comparison inputs: /apiImageDigest/baseline")
AT_TARGET = (UNBOUND, "comparison inputs: /apiImageDigest/target")


def declare(root: Path, baseline: str | None, target: str | None) -> None:
    """State the API image digest of each side again. ``None`` states no member."""
    for line, name, value in (
        (BASELINE_LINE, "baseline", baseline),
        (TARGET_LINE, "target", target),
    ):
        edit(root / INPUTS, line, "" if value is None else f"  {name}: {value}\n")


def test_the_committed_inputs_declare_one_valid_digest_for_both_sides() -> None:
    """The positive case: two equal valid digests bind the API image identity."""
    declared = load(INPUTS)
    assert declared == {
        "apiVersion": COMPARISON_INPUTS_SCHEMA,
        "kind": "BaselineComparisonInputs",
        "apiImageDigest": {"baseline": DECLARED_DIGEST, "target": DECLARED_DIGEST},
    }
    assert INPUTS == COMPARISON_INPUTS_PATH
    assert re.fullmatch(r"sha256:[0-9a-f]{64}", DECLARED_DIGEST)
    record = build_record()
    assert record["result"] == COMPARABLE
    identity = record["apiImageIdentity"]
    assert identity["bound"] is True
    assert identity["digest"] == DECLARED_DIGEST
    assert identity["sides"] == {
        side: {"state": "valid", "digest": DECLARED_DIGEST}
        for side in ("baseline", "target")
    }
    assert identity["source"] == INPUTS
    assert identity["effectiveValuesCompared"] is True
    assert identity["statedByEffectiveValues"] == {}
    assert states(record)[UNBOUND] == states(record)[CONTRADICTED] == HELD
    assert DIGEST_STATES == ("valid", "absent", "malformed", "not-read")


def test_another_valid_digest_on_both_sides_is_comparable_and_is_still_reported(
    root: Path,
) -> None:
    """Any one usable digest binds the identity. The committed record is then stale."""
    declare(root, OTHER_DIGEST, OTHER_DIGEST)
    record = build_record(root)
    assert record["result"] == COMPARABLE
    assert record["apiImageIdentity"]["digest"] == OTHER_DIGEST
    assert [f.rule_id for f in verify_profile(root)] == ["baseline-record-stale"]


def test_the_digest_is_stated_as_a_declared_comparison_input_and_as_no_other() -> None:
    """The record names the category, and it names neither other category as its own."""
    identity = build_record()["apiImageIdentity"]
    assert identity["category"] == DIGEST_CATEGORY == "declared-comparison-input"
    assert "not an install input" in identity["boundary"]
    assert "not an observed runtime identity" in identity["boundary"]
    limits = " ".join(DOES_NOT_ESTABLISH)
    assert "That a run installs either release with the declared API image" in limits
    assert "That a cluster ran a pod of the declared API image" in limits
    # Neither install description states the digest, and the Application holds
    # no parameter. The declared inputs are the one committed statement of it.
    application = load(APPLICATION)["spec"]["source"]["helm"]
    assert "parameters" not in application
    assert "digest" not in application["valuesObject"]["api"]["image"]
    assert "digest" not in load(INSTALL)["handWrittenValues"]["api"]["image"]


def test_the_declared_digest_is_the_one_the_retained_read_reports() -> None:
    """A tripwire on the stated origin of the committed value.

    The comparison inputs say that a cluster reported the digest as the image
    of the API pods in one retained read. This test holds that statement. A
    change that declares another digest must state the origin of that digest in
    the file and on the page, and it must move this test.
    """
    read = json.loads((REPO_ROOT / DIGEST_ORIGIN).read_text(encoding="utf-8"))
    reported = {
        status["imageID"]
        for pod in read["items"]
        for status in pod["status"]["containerStatuses"]
        if status["name"] == "api"
    }
    assert reported == {f"localhost/inferops-api@{DECLARED_DIGEST}"}
    assert DIGEST_ORIGIN in (REPO_ROOT / INPUTS).read_text(encoding="utf-8")
    assert DIGEST_ORIGIN in DOCUMENT.read_text(encoding="utf-8")


UNUSABLE_DIGESTS = [
    pytest.param(
        None, DECLARED_DIGEST, [AT_BASELINE], ["baseline"], id="baseline-absent"
    ),
    pytest.param(DECLARED_DIGEST, None, [AT_TARGET], ["target"], id="target-absent"),
    pytest.param(
        None, None, [AT_BASELINE, AT_TARGET], ["baseline", "target"], id="both-absent"
    ),
    pytest.param(
        "abc", DECLARED_DIGEST, [AT_BASELINE], ["baseline"], id="baseline-malformed"
    ),
    pytest.param(
        DECLARED_DIGEST, "abc", [AT_TARGET], ["target"], id="target-malformed"
    ),
    pytest.param(
        "abc",
        "abc",
        [AT_BASELINE, AT_TARGET],
        ["baseline", "target"],
        id="one-malformed-text-on-both-sides",
    ),
    pytest.param(
        DECLARED_DIGEST,
        OTHER_DIGEST,
        [(UNBOUND, "comparison inputs: /apiImageDigest")],
        ["baseline", "target"],
        id="two-valid-digests-that-differ",
    ),
]


@pytest.mark.parametrize(("baseline", "target", "expected", "sides"), UNUSABLE_DIGESTS)
def test_a_declared_digest_that_is_absent_malformed_or_unequal_is_refused(
    root: Path,
    capsys: pytest.CaptureFixture[str],
    baseline: str | None,
    target: str | None,
    expected: list[tuple[str, str]],
    sides: list[str],
) -> None:
    declare(root, baseline, target)
    record = refused_by(root)
    assert found(record) == expected
    assert states(record) == {**dict.fromkeys(RULE_IDS, HELD), UNBOUND: NOT_HELD}
    identity = record["apiImageIdentity"]
    assert identity["bound"] is False
    assert "digest" not in identity
    for side, value in (("baseline", baseline), ("target", target)):
        wanted = (
            {"state": "absent"}
            if value is None
            else {"state": "malformed", "stated": json.dumps(value)}
            if value == "abc"
            else {"state": "valid", "digest": value}
        )
        assert identity["sides"][side] == wanted
    # The digest is listed as unresolved again, and the caller profile stays.
    assert [(e["input"], e["sides"]) for e in record["unresolvedInputs"]] == [
        ("api-image-digest", sides),
        ("caller-profile", ["baseline", "target"]),
    ]
    assert record["experimentEligibility"] == "not-established"
    # Every other layer is compared as before.
    assert record["differences"] == build_record()["differences"]
    # The refusal exit of the record, and the failed check, are two outcomes.
    assert main(["--record", "--root", str(root)]) == REFUSED_EXIT
    capsys.readouterr()
    assert main(["--check", "--root", str(root)]) == 1
    assert f"REFUSED  {UNBOUND}" in capsys.readouterr().out
    with pytest.raises(WriteRefused):
        write_profile(root)


NOT_DIGESTS = [
    pytest.param('""', '""', id="empty-text"),
    pytest.param("sha256:" + "A" * 64, "sha256:" + "A" * 64, id="uppercase"),
    pytest.param("sha256:" + "a" * 63, "sha256:" + "a" * 63, id="63-digits"),
    pytest.param("sha256:" + "a" * 65, "sha256:" + "a" * 65, id="65-digits"),
    pytest.param("a" * 64, "a" * 64, id="no-algorithm"),
    pytest.param("sha512:" + "a" * 64, "sha512:" + "a" * 64, id="another-algorithm"),
    pytest.param(
        "localhost/inferops-api@" + DECLARED_DIGEST,
        "localhost/inferops-api@" + DECLARED_DIGEST,
        id="an-image-reference",
    ),
    pytest.param(f'"{DECLARED_DIGEST} "', f'"{DECLARED_DIGEST} "', id="trailing-space"),
    pytest.param(
        f"|\n    {DECLARED_DIGEST}", f"|\n    {DECLARED_DIGEST}", id="a-newline"
    ),
    pytest.param("12", "12", id="a-number"),
    pytest.param("true", "true", id="a-boolean"),
    pytest.param("[a]", "[a]", id="a-list"),
    pytest.param("{a: b}", "{a: b}", id="a-mapping"),
    # One document cannot state one anchor twice, so the two names differ.
    pytest.param("&a [*a]", "&b [*b]", id="a-value-that-refers-to-itself"),
]


@pytest.mark.parametrize(("baseline", "target"), NOT_DIGESTS)
def test_two_equal_values_that_are_not_digests_are_refused(
    root: Path, baseline: str, target: str
) -> None:
    """Equality is not validity: each pair is equal, and neither value is usable."""
    declare(root, baseline, target)
    record = refused_by(root)
    assert found(record) == [AT_BASELINE, AT_TARGET]
    for side in ("baseline", "target"):
        assert record["apiImageIdentity"]["sides"][side]["state"] == "malformed"
    json.dumps(record)
    assert record["experimentEligibility"] == "not-established"
    assert record["unresolvedInputs"][-1]["input"] == "caller-profile"


@pytest.mark.parametrize(
    "block",
    ["apiImageDigest:\n  baseline: null\n  target: ~\n", "apiImageDigest: {}\n", ""],
    ids=["two-nulls", "an-empty-block", "no-block"],
)
def test_a_digest_that_no_member_states_is_absent_and_is_given_no_default(
    root: Path, block: str
) -> None:
    edit(root / INPUTS, "apiImageDigest:\n" + BASELINE_LINE + TARGET_LINE, block)
    record = refused_by(root)
    assert found(record) == [AT_BASELINE, AT_TARGET]
    for side in ("baseline", "target"):
        assert record["apiImageIdentity"]["sides"][side] == {"state": "absent"}
    assert "no default is assumed" in record["findings"][0]["detail"]
    assert record["experimentEligibility"] == "not-established"
    assert record["unresolvedInputs"][-1]["input"] == "caller-profile"


UNREAD_INPUTS = [
    pytest.param(lambda path: path.unlink(), "is not a regular file", id="absent"),
    pytest.param(
        lambda path: path.write_bytes(b"apiImageDigest: [\n"),
        "is not YAML",
        id="not-yaml",
    ),
    pytest.param(
        lambda path: path.write_bytes(b"\xff\xfe"), "is not UTF-8 text", id="not-text"
    ),
    pytest.param(
        replaced(BASELINE_LINE, BASELINE_LINE + BASELINE_LINE),
        "states the key baseline twice",
        id="a-key-stated-twice",
    ),
    pytest.param(
        replaced("kind: BaselineComparisonInputs", "kind: BaselineInstallInputs"),
        "is not a BaselineComparisonInputs document",
        id="another-kind",
    ),
    pytest.param(
        replaced("/v1alpha1\n", "/v1alpha2\n"),
        "is not a BaselineComparisonInputs document",
        id="another-schema",
    ),
    pytest.param(
        replaced(TARGET_LINE, TARGET_LINE + "  canary: abc\n"),
        "a member of apiImageDigest that this tool does not read: canary",
        id="another-side",
    ),
    pytest.param(
        replaced("kind: ", "origin: a build\nkind: "),
        "a member of the document that this tool does not read: origin",
        id="another-member",
    ),
    pytest.param(
        replaced(
            "apiImageDigest:\n" + BASELINE_LINE + TARGET_LINE,
            f"apiImageDigest: {DECLARED_DIGEST}\n",
        ),
        "states no mapping at apiImageDigest",
        id="one-digest-for-no-side",
    ),
    pytest.param(
        lambda path: path.write_bytes(b""),
        "states no mapping at the document",
        id="empty",
    ),
]


@pytest.mark.parametrize(("damage", "reason"), UNREAD_INPUTS)
def test_comparison_inputs_that_are_not_read_whole_refuse_the_comparison(
    root: Path, damage: Any, reason: str
) -> None:
    """A file that was not read states no digest, and no side is read as equal."""
    damage(root / INPUTS)
    record = refused_by(root)
    assert found(record) == [(UNBOUND, "comparison inputs")]
    assert reason in record["findings"][0]["detail"]
    assert record["apiImageIdentity"]["sides"] == {
        "baseline": {"state": "not-read"},
        "target": {"state": "not-read"},
    }
    assert record["unresolvedInputs"][0]["sides"] == ["baseline", "target"]
    assert record["experimentEligibility"] == "not-established"
    assert record["unresolvedInputs"][-1]["input"] == "caller-profile"
    assert str(root) not in json.dumps(record)
    with pytest.raises(WriteRefused):
        write_profile(root)


def test_the_declared_digests_are_read_when_no_release_is_derived(root: Path) -> None:
    """The rule on the declared digests needs no release and no description."""
    (root / BASELINE_CONTRACT).unlink()
    declare(root, "abc", DECLARED_DIGEST)
    record = refused_by(root)
    assert ("baseline-sources-refused", "baseline: declared inputs") in found(record)
    assert AT_BASELINE in found(record)
    assert states(record)[UNBOUND] == NOT_HELD
    assert states(record)[CONTRADICTED] == NOT_EVALUATED
    assert record["apiImageIdentity"]["effectiveValuesCompared"] is False


def test_the_target_has_one_application_and_an_undeclared_one_is_refused(
    root: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import tools.baseline_profile.core as core
    from tools.capacity_preflight import APPLICATIONS

    assert APPLICATIONS[TARGET_KEY] == APPLICATION
    monkeypatch.setattr(core, "APPLICATIONS", {})
    record = refused_by(root)
    assert found(record) == [
        ("baseline-install-inputs-refused", "target: install inputs")
    ]
    assert "no Application is declared for the key" in record["findings"][0]["detail"]
    assert record["targetDelivery"] == {}


def test_the_values_merge_is_the_one_the_capacity_preflight_uses() -> None:
    """Two tools read one Application. Each holds its own copy of the merge, and
    this holds the two copies equal in what they give."""
    from tools.baseline_profile.core import _merged as ours
    from tools.capacity_preflight.core import _merged as theirs

    base = {"a": {"b": 1, "c": 2}, "d": [1, 2], "e": "x", "f": {"g": 1}}
    overs: tuple[dict[str, Any], ...] = (
        {"a": {"b": 9}},
        {"a": {"b": None}},
        {"a": None},
        {"a": "scalar"},
        {"d": [3]},
        {"e": {"now": "a mapping"}},
        {"f": {}},
        {"new": {"h": None}},
    )
    for over in overs:
        assert ours(base, over) == theirs(base, over), over
    assert ours(base, {"a": {"b": None}})["a"] == {"c": 2}
    assert ours(base, {"f": {}})["f"] == {"g": 1}


# --------------------------------------------------------------------------
# 5. The profile is not desired state
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
    paths.extend([RECORD_PATH, INSTALL_PATH, COMPARISON_INPUTS_PATH])
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
# 6. The page says what the tool does
# --------------------------------------------------------------------------


def test_the_page_states_each_rule() -> None:
    page = DOCUMENT.read_text(encoding="utf-8")
    assert [rule.rule_id for rule in RULES] == RULE_IDS
    assert [rule.rule_id for rule in CHECK_RULES] == [
        "baseline-release-drifted",
        "baseline-target-release-drifted",
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
    assert f"`{INSTALL_PATH}`" in page
    assert f"`{COMPARISON_INPUTS_PATH}`" in page
    assert f"`{DIGEST_CATEGORY}`" in page
    assert f"`{DECLARED_DIGEST}`" in page


def test_the_page_states_each_readiness_input_and_each_unresolved_input() -> None:
    page = " ".join(DOCUMENT.read_text(encoding="utf-8").split())
    for pointer in READINESS_INPUTS:
        assert f"`{pointer}`" in page, pointer
    record = build_record()
    for entry in record["unresolvedInputs"]:
        assert f"`{entry['input']}`" in page, entry["input"]
        assert entry["statement"] in page, entry["input"]
    assert f"`{ELIGIBILITY}`" in page
