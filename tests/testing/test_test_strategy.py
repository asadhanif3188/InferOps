"""Deterministic checks over the V1 test, lane, and certification strategy.

Every check here reads files from this repository and nothing else. No network,
no cluster, no model, no clock, no randomness.

What this suite establishes is that the strategy is internally consistent and that
it agrees with the pytest configuration actually committed beside it: that every
claim names a test layer, an environment, and an evidence owner; that no layer
certifies above the ceiling its evidence class allows, so a mock cannot support a
C2 claim however faithful it is; that no layer needing a cluster or a model sits in
the default lane; that every marker belonging to such a layer is deselected by the
committed default marker expression; that a claim may cite evidence only once it is
certified and only from layers that are implemented; and that the documents and the
data publish the same identifiers in both directions.

What it does not establish is that any of these tests exist. Most layers here have
no code behind them, and this suite cannot tell the difference between a layer that
is honestly planned and one that will never be written. It stops the strategy
drifting; it does not implement it.
"""

from __future__ import annotations

import configparser
import json
import re
import shlex
from pathlib import Path

import pytest

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
TESTING_DIR = REPO_ROOT / "docs" / "testing"
STRATEGY_PATH = TESTING_DIR / "test-strategy.v1alpha1.json"
PYTEST_INI_PATH = REPO_ROOT / "pytest.ini"

EXPECTED_STRATEGY_ID = "https://inferops.io/testing/test-strategy.v1alpha1.json"
EXPECTED_CONTRACT_VERSION = "inferops.io/v1alpha1"

# Identifiers are lowercase, hyphen-separated, and safe anywhere a name is needed.
SLUG = re.compile(r"^[a-z0-9]([a-z0-9-]*[a-z0-9])?$")

# Certification levels are the published C0..C4 labels, not slugs.
LEVEL_ID = re.compile(r"^C[0-9]$")

# A marker has to be a bare word: pytest markers are attribute names.
MARKER = re.compile(r"^[a-z][a-z0-9]*$")

# An identifier as a document publishes it: an inline code span in the first
# column of a Markdown table row.
FIRST_TABLE_COLUMN = re.compile(
    r"^\|\s*`([A-Za-z0-9][A-Za-z0-9-]*)`\s*\|", flags=re.MULTILINE
)

REQUIRED_LEVEL_FIELDS = ("levelId", "name", "meaning", "rank", "v1Scope")

REQUIRED_CLASS_FIELDS = ("classId", "meaning", "maxCertification")

REQUIRED_OWNER_FIELDS = ("ownerId", "name", "responsibility")

REQUIRED_LANE_FIELDS = (
    "laneId",
    "name",
    "purpose",
    "trigger",
    "environment",
    "modelDownload",
    "clusterRequired",
    "authorizationRequired",
    "optIn",
    "timeoutMinutes",
    "prerequisites",
    "artifacts",
    "artifactRetentionDays",
    "failureDiagnostics",
    "automated",
    "workflowRef",
    "v1Status",
    "notes",
)

REQUIRED_LAYER_FIELDS = (
    "layerId",
    "name",
    "purpose",
    "lane",
    "environment",
    "marker",
    "paths",
    "commands",
    "evidenceClass",
    "maxCertification",
    "requiresModel",
    "requiresCluster",
    "publishable",
    "v1Status",
    "evidenceRef",
    "notes",
)

REQUIRED_CLAIM_FIELDS = (
    "claimId",
    "statement",
    "layers",
    "environment",
    "requiredCertification",
    "requiresRealModel",
    "evidenceOwner",
    "v1Status",
    "evidenceRef",
    "deferralReason",
)

REQUIRED_RETENTION_FIELDS = (
    "certifyingRecordRoot",
    "certifyingRecords",
    "laneArtifacts",
    "promotion",
    "supersession",
)

LANE_STATUSES = frozenset({"manual", "automated", "planned", "deferred"})
LAYER_STATUSES = frozenset({"implemented", "planned", "deferred"})
CLAIM_STATUSES = frozenset({"certified", "planned", "deferred"})

MODEL_DOWNLOADS = frozenset({"none", "full"})

# The classes whose whole point is that they are not the real thing.
UNREAL_CLASSES = frozenset({"mock", "synthetic", "estimated", "documented-unexecuted"})


def load_strategy() -> dict:
    return json.loads(STRATEGY_PATH.read_text(encoding="utf-8"))


STRATEGY = load_strategy()
LEVELS = STRATEGY["certificationLevels"]
CLASSES = STRATEGY["evidenceClasses"]
OWNERS = STRATEGY["evidenceOwners"]
LANES = STRATEGY["lanes"]
LAYERS = STRATEGY["layers"]
CLAIMS = STRATEGY["claims"]
ENVIRONMENTS = STRATEGY["environments"]
RETENTION = STRATEGY["evidenceRetention"]

LEVEL_BY_ID = {level["levelId"]: level for level in LEVELS}
CLASS_BY_ID = {cls["classId"]: cls for cls in CLASSES}
OWNER_BY_ID = {owner["ownerId"]: owner for owner in OWNERS}
LANE_BY_ID = {lane["laneId"]: lane for lane in LANES}
LAYER_BY_ID = {layer["layerId"]: layer for layer in LAYERS}


def rank(level_id: str | None) -> int:
    """Certification strength as a number. `None` certifies nothing."""
    return -1 if level_id is None else LEVEL_BY_ID[level_id]["rank"]


def default_lane() -> dict:
    lanes = [lane for lane in LANES if not lane["optIn"]]
    assert len(lanes) == 1, "there must be exactly one lane nobody has to opt into"
    return lanes[0]


def layers_in(lane_id: str) -> list[dict]:
    return [layer for layer in LAYERS if layer["lane"] == lane_id]


def cited_layers(claim: dict) -> list[dict]:
    return [LAYER_BY_ID[layer_id] for layer_id in claim["layers"]]


def read_pytest_ini() -> configparser.ConfigParser:
    parser = configparser.ConfigParser()
    parser.read_string(PYTEST_INI_PATH.read_text(encoding="utf-8"))
    return parser


PYTEST_INI = read_pytest_ini()


def registered_markers() -> set[str]:
    raw = PYTEST_INI["pytest"]["markers"]
    return {line.split(":", 1)[0].strip() for line in raw.splitlines() if line.strip()}


def addopts_tokens() -> list[str]:
    return shlex.split(PYTEST_INI["pytest"]["addopts"])


def default_marker_expression() -> str:
    tokens = addopts_tokens()
    assert "-m" in tokens, "the default lane declares no marker expression"
    return tokens[tokens.index("-m") + 1]


def expression_excludes(marker: str) -> bool:
    return (
        re.search(rf"\bnot\s+{re.escape(marker)}\b", default_marker_expression())
        is not None
    )


def expression_mentions(marker: str) -> bool:
    return (
        re.search(rf"\b{re.escape(marker)}\b", default_marker_expression()) is not None
    )


@pytest.fixture(scope="module")
def strategy_document() -> str:
    return (TESTING_DIR / "test-strategy.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def certification_document() -> str:
    return (TESTING_DIR / "certification.md").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def matrix_document() -> str:
    return (TESTING_DIR / "claim-test-matrix.md").read_text(encoding="utf-8")


# --------------------------------------------------------------------------
# Shape
# --------------------------------------------------------------------------


def test_strategy_declares_its_identity_and_contract_version() -> None:
    assert STRATEGY["$id"] == EXPECTED_STRATEGY_ID
    assert STRATEGY["contractVersion"] == EXPECTED_CONTRACT_VERSION


def test_strategy_is_not_empty() -> None:
    assert LEVELS, "a strategy with no certification levels cannot grade anything"
    assert LANES, "a strategy with no lanes cannot say where a test runs"
    assert LAYERS, "a strategy with no layers cannot say how a claim is proven"
    assert CLAIMS, "a strategy proving no claim proves nothing"


@pytest.mark.parametrize("level", LEVELS, ids=lambda level: level["levelId"])
def test_every_level_declares_every_required_field(level: dict) -> None:
    assert set(level) == set(REQUIRED_LEVEL_FIELDS), level["levelId"]
    assert LEVEL_ID.match(level["levelId"]), level["levelId"]
    assert isinstance(level["rank"], int)
    assert isinstance(level["v1Scope"], bool)


@pytest.mark.parametrize("cls", CLASSES, ids=lambda cls: cls["classId"])
def test_every_evidence_class_declares_every_required_field(cls: dict) -> None:
    assert set(cls) == set(REQUIRED_CLASS_FIELDS), cls["classId"]
    assert SLUG.match(cls["classId"]), cls["classId"]
    assert cls["meaning"].strip()
    assert cls["maxCertification"] is None or cls["maxCertification"] in LEVEL_BY_ID


@pytest.mark.parametrize("owner", OWNERS, ids=lambda owner: owner["ownerId"])
def test_every_owner_declares_every_required_field(owner: dict) -> None:
    assert set(owner) == set(REQUIRED_OWNER_FIELDS), owner["ownerId"]
    assert SLUG.match(owner["ownerId"]), owner["ownerId"]
    for field in REQUIRED_OWNER_FIELDS:
        assert owner[field].strip(), f"owner '{owner['ownerId']}' leaves {field} empty"


@pytest.mark.parametrize("lane", LANES, ids=lambda lane: lane["laneId"])
def test_every_lane_declares_every_required_field(lane: dict) -> None:
    assert set(lane) == set(REQUIRED_LANE_FIELDS), lane["laneId"]
    assert SLUG.match(lane["laneId"]), lane["laneId"]
    for field in ("name", "purpose", "trigger", "failureDiagnostics"):
        assert lane[field].strip(), f"lane '{lane['laneId']}' leaves {field} empty"
    for field in ("clusterRequired", "authorizationRequired", "optIn", "automated"):
        assert isinstance(lane[field], bool), f"lane '{lane['laneId']}' {field}"
    assert lane["modelDownload"] in MODEL_DOWNLOADS, lane["modelDownload"]
    assert lane["v1Status"] in LANE_STATUSES, lane["v1Status"]
    assert lane["prerequisites"], f"lane '{lane['laneId']}' declares no prerequisites"


@pytest.mark.parametrize("layer", LAYERS, ids=lambda layer: layer["layerId"])
def test_every_layer_declares_every_required_field(layer: dict) -> None:
    assert set(layer) == set(REQUIRED_LAYER_FIELDS), layer["layerId"]
    assert SLUG.match(layer["layerId"]), layer["layerId"]
    for field in ("name", "purpose"):
        assert layer[field].strip(), f"layer '{layer['layerId']}' leaves {field} empty"
    for field in ("requiresModel", "requiresCluster", "publishable"):
        assert isinstance(layer[field], bool), f"layer '{layer['layerId']}' {field}"
    assert layer["v1Status"] in LAYER_STATUSES, layer["v1Status"]
    assert layer["commands"], f"layer '{layer['layerId']}' names no way to run it"


@pytest.mark.parametrize("claim", CLAIMS, ids=lambda claim: claim["claimId"])
def test_every_claim_declares_every_required_field(claim: dict) -> None:
    assert set(claim) == set(REQUIRED_CLAIM_FIELDS), claim["claimId"]
    assert SLUG.match(claim["claimId"]), claim["claimId"]
    assert claim["statement"].strip(), f"claim '{claim['claimId']}' states nothing"
    assert isinstance(claim["requiresRealModel"], bool)
    assert claim["v1Status"] in CLAIM_STATUSES, claim["v1Status"]


def test_identifiers_are_unique() -> None:
    for collection, key in (
        (LEVELS, "levelId"),
        (CLASSES, "classId"),
        (OWNERS, "ownerId"),
        (LANES, "laneId"),
        (LAYERS, "layerId"),
        (CLAIMS, "claimId"),
    ):
        ids = [item[key] for item in collection]
        assert len(ids) == len(set(ids)), f"duplicate {key}"


def test_certification_levels_are_a_total_order_from_zero() -> None:
    ranks = [level["rank"] for level in LEVELS]
    assert ranks == sorted(ranks), "levels are not published in ascending order"
    assert ranks == list(range(len(LEVELS))), "ranks are not a contiguous run from 0"


def test_evidence_retention_is_defined() -> None:
    assert set(RETENTION) == set(REQUIRED_RETENTION_FIELDS)
    for field in REQUIRED_RETENTION_FIELDS:
        assert RETENTION[field].strip(), f"retention leaves {field} empty"
    assert (REPO_ROOT / RETENTION["certifyingRecordRoot"]).is_dir()


# --------------------------------------------------------------------------
# Everything a claim needs: a test level, an environment, and an owner
# --------------------------------------------------------------------------


@pytest.mark.parametrize("claim", CLAIMS, ids=lambda claim: claim["claimId"])
def test_every_claim_names_a_layer_an_environment_and_an_owner(claim: dict) -> None:
    assert claim["layers"], f"claim '{claim['claimId']}' names no test layer"
    for layer_id in claim["layers"]:
        assert layer_id in LAYER_BY_ID, f"claim '{claim['claimId']}' -> {layer_id}"
    assert len(set(claim["layers"])) == len(claim["layers"]), claim["claimId"]
    assert claim["environment"] in ENVIRONMENTS, claim["environment"]
    assert claim["evidenceOwner"] in OWNER_BY_ID, claim["evidenceOwner"]
    assert claim["requiredCertification"] in LEVEL_BY_ID, claim["claimId"]


@pytest.mark.parametrize("layer", LAYERS, ids=lambda layer: layer["layerId"])
def test_every_layer_names_a_declared_lane_environment_and_class(layer: dict) -> None:
    assert layer["lane"] in LANE_BY_ID, layer["lane"]
    assert layer["environment"] in ENVIRONMENTS, layer["environment"]
    assert layer["evidenceClass"] in CLASS_BY_ID, layer["evidenceClass"]
    assert layer["maxCertification"] in LEVEL_BY_ID, layer["maxCertification"]


@pytest.mark.parametrize("lane", LANES, ids=lambda lane: lane["laneId"])
def test_every_lane_names_a_declared_environment(lane: dict) -> None:
    assert lane["environment"] in ENVIRONMENTS, lane["environment"]


def test_no_layer_is_defined_for_its_own_sake() -> None:
    """A test level nothing claims is a test somebody has to justify later."""
    cited = {layer_id for claim in CLAIMS for layer_id in claim["layers"]}
    assert set(LAYER_BY_ID) == cited, sorted(set(LAYER_BY_ID) - cited)


def test_no_lane_is_defined_for_its_own_sake() -> None:
    hosting = {layer["lane"] for layer in LAYERS}
    assert set(LANE_BY_ID) == hosting, sorted(set(LANE_BY_ID) - hosting)


def test_every_declared_owner_owns_a_claim() -> None:
    owning = {claim["evidenceOwner"] for claim in CLAIMS}
    assert set(OWNER_BY_ID) == owning, sorted(set(OWNER_BY_ID) - owning)


def test_every_declared_environment_is_used() -> None:
    used = {layer["environment"] for layer in LAYERS} | {
        lane["environment"] for lane in LANES
    }
    assert set(ENVIRONMENTS) == used, sorted(set(ENVIRONMENTS) - used)


# --------------------------------------------------------------------------
# A mock cannot certify real runtime behaviour
# --------------------------------------------------------------------------


@pytest.mark.parametrize("layer", LAYERS, ids=lambda layer: layer["layerId"])
def test_no_layer_certifies_above_its_evidence_class(layer: dict) -> None:
    ceiling = CLASS_BY_ID[layer["evidenceClass"]]["maxCertification"]
    assert ceiling is not None, (
        f"layer '{layer['layerId']}' claims an evidence class that certifies nothing"
    )
    assert rank(layer["maxCertification"]) <= rank(ceiling), (
        f"layer '{layer['layerId']}' certifies to {layer['maxCertification']} on "
        f"{layer['evidenceClass']} evidence, whose ceiling is {ceiling}"
    )


@pytest.mark.parametrize("layer", LAYERS, ids=lambda layer: layer["layerId"])
def test_a_mock_layer_stops_at_c1(layer: dict) -> None:
    """The rule the whole strategy exists to make unrepresentable.

    This restates the ceiling check above for the one class where the mistake is
    tempting. It stays because a future loosening of the class table would have to
    delete this test rather than quietly pass it.
    """
    if layer["evidenceClass"] not in UNREAL_CLASSES:
        return
    assert rank(layer["maxCertification"]) <= rank("C1"), layer["layerId"]
    assert not layer["requiresModel"], (
        f"layer '{layer['layerId']}' is labelled {layer['evidenceClass']} and "
        "claims to need a real model"
    )


@pytest.mark.parametrize("layer", LAYERS, ids=lambda layer: layer["layerId"])
def test_a_c2_layer_runs_against_something_real(layer: dict) -> None:
    if rank(layer["maxCertification"]) < rank("C2"):
        return
    assert layer["requiresModel"] or layer["requiresCluster"], (
        f"layer '{layer['layerId']}' certifies real controlled behaviour without "
        "needing a cluster or a model"
    )


@pytest.mark.parametrize("claim", CLAIMS, ids=lambda claim: claim["claimId"])
def test_a_claim_is_backed_by_a_layer_that_can_reach_its_level(claim: dict) -> None:
    required = claim["requiredCertification"]
    reaching = [
        layer
        for layer in cited_layers(claim)
        if rank(layer["maxCertification"]) >= rank(required)
    ]
    assert reaching, (
        f"claim '{claim['claimId']}' requires {required} and cites no layer that "
        "can reach it"
    )


@pytest.mark.parametrize("claim", CLAIMS, ids=lambda claim: claim["claimId"])
def test_no_real_claim_rests_on_an_unreal_layer(claim: dict) -> None:
    """C2 and above cannot be reached by a mock, a simulation, or an estimate."""
    if rank(claim["requiredCertification"]) < rank("C2"):
        return
    reaching = [
        layer
        for layer in cited_layers(claim)
        if rank(layer["maxCertification"]) >= rank(claim["requiredCertification"])
    ]
    for layer in reaching:
        assert layer["evidenceClass"] not in UNREAL_CLASSES, (
            f"claim '{claim['claimId']}' would be certified by "
            f"'{layer['layerId']}', which is {layer['evidenceClass']}"
        )


@pytest.mark.parametrize("claim", CLAIMS, ids=lambda claim: claim["claimId"])
def test_a_claim_needing_a_real_model_cites_a_layer_that_loads_one(claim: dict) -> None:
    if not claim["requiresRealModel"]:
        return
    assert any(layer["requiresModel"] for layer in cited_layers(claim)), (
        f"claim '{claim['claimId']}' needs a real model and no cited layer loads one"
    )


@pytest.mark.parametrize("claim", CLAIMS, ids=lambda claim: claim["claimId"])
def test_an_active_claim_stays_inside_the_v1_certification_range(claim: dict) -> None:
    if claim["v1Status"] == "deferred":
        return
    level = LEVEL_BY_ID[claim["requiredCertification"]]
    assert level["v1Scope"], (
        f"claim '{claim['claimId']}' requires {level['levelId']}, which V1 does not "
        "claim; defer the claim or lower the level"
    )


# --------------------------------------------------------------------------
# Normal CI does not download a model
# --------------------------------------------------------------------------


def test_the_default_lane_needs_no_model_cluster_or_authorization() -> None:
    lane = default_lane()
    assert lane["modelDownload"] == "none", (
        "the lane every change goes through downloads a model"
    )
    assert not lane["clusterRequired"]
    assert not lane["authorizationRequired"]


@pytest.mark.parametrize("layer", LAYERS, ids=lambda layer: layer["layerId"])
def test_nothing_needing_a_capable_host_sits_in_the_default_lane(layer: dict) -> None:
    if layer["lane"] != default_lane()["laneId"]:
        return
    assert not layer["requiresModel"], layer["layerId"]
    assert not layer["requiresCluster"], layer["layerId"]


@pytest.mark.parametrize("layer", LAYERS, ids=lambda layer: layer["layerId"])
def test_a_layer_gets_the_lane_it_needs(layer: dict) -> None:
    lane = LANE_BY_ID[layer["lane"]]
    if layer["requiresModel"]:
        assert lane["modelDownload"] == "full", (
            f"layer '{layer['layerId']}' needs a model in a lane that fetches none"
        )
    if layer["requiresCluster"]:
        assert lane["clusterRequired"], layer["layerId"]


@pytest.mark.parametrize("lane", LANES, ids=lambda lane: lane["laneId"])
def test_a_lane_that_fetches_a_model_is_opt_in_and_authorized(lane: dict) -> None:
    if lane["modelDownload"] != "full":
        return
    assert lane["optIn"], f"lane '{lane['laneId']}' fetches a model without opt-in"
    assert lane["authorizationRequired"], lane["laneId"]


def test_the_default_lane_is_the_cheapest_one() -> None:
    default = default_lane()
    for lane in LANES:
        assert default["timeoutMinutes"] <= lane["timeoutMinutes"], lane["laneId"]


@pytest.mark.parametrize("lane", LANES, ids=lambda lane: lane["laneId"])
def test_every_lane_declares_a_positive_timeout(lane: dict) -> None:
    assert isinstance(lane["timeoutMinutes"], int)
    assert lane["timeoutMinutes"] > 0, lane["laneId"]


# --------------------------------------------------------------------------
# The committed pytest configuration, compared to the strategy in both directions
# --------------------------------------------------------------------------


def test_markers_are_registered_and_unregistered_ones_are_refused() -> None:
    tokens = addopts_tokens()
    assert "--strict-markers" in tokens, (
        "without --strict-markers an unregistered marker is a silent typo"
    )
    assert "--strict-config" in tokens


def test_every_layer_marker_is_registered_and_every_registered_marker_is_used() -> None:
    declared = {layer["marker"] for layer in LAYERS if layer["marker"] is not None}
    assert declared == registered_markers(), {
        "declared but not registered": sorted(declared - registered_markers()),
        "registered but unused": sorted(registered_markers() - declared),
    }


def test_no_two_layers_share_a_marker() -> None:
    markers = [layer["marker"] for layer in LAYERS if layer["marker"] is not None]
    assert len(markers) == len(set(markers)), "two layers select the same tests"
    for marker in markers:
        assert MARKER.match(marker), marker


@pytest.mark.parametrize("layer", LAYERS, ids=lambda layer: layer["layerId"])
def test_a_capable_host_marker_is_deselected_by_default(layer: dict) -> None:
    """The acceptance criterion, as a property of the committed configuration.

    A layer outside the default lane must be excluded by the default marker
    expression. If it is not, a test needing a cluster or a model runs in the lane
    every change goes through, which is exactly the failure this strategy exists to
    prevent.
    """
    if layer["lane"] == default_lane()["laneId"] or layer["marker"] is None:
        return
    assert expression_excludes(layer["marker"]), (
        f"marker '{layer['marker']}' selects layer '{layer['layerId']}', which needs "
        f"the {layer['lane']} lane, and the default expression does not exclude it"
    )


@pytest.mark.parametrize("layer", LAYERS, ids=lambda layer: layer["layerId"])
def test_a_default_lane_marker_is_not_deselected(layer: dict) -> None:
    if layer["lane"] != default_lane()["laneId"] or layer["marker"] is None:
        return
    assert not expression_mentions(layer["marker"]), (
        f"marker '{layer['marker']}' belongs to the default lane and the default "
        "expression mentions it"
    )


def test_the_test_paths_setting_points_at_the_test_tree() -> None:
    assert PYTEST_INI["pytest"]["testpaths"].strip() == "tests"


@pytest.mark.parametrize("layer", LAYERS, ids=lambda layer: layer["layerId"])
def test_every_path_a_layer_names_exists(layer: dict) -> None:
    for path in layer["paths"]:
        assert (REPO_ROOT / path).exists(), f"layer '{layer['layerId']}' -> {path}"


@pytest.mark.parametrize("layer", LAYERS, ids=lambda layer: layer["layerId"])
def test_an_implemented_layer_names_where_its_tests_live(layer: dict) -> None:
    if layer["v1Status"] != "implemented":
        return
    assert layer["paths"] or layer["commands"], layer["layerId"]


@pytest.mark.parametrize("layer", LAYERS, ids=lambda layer: layer["layerId"])
def test_every_module_under_a_layer_carries_that_layer_marker(layer: dict) -> None:
    """A marker nothing is marked with selects nothing, silently.

    Registering a marker and writing it into the strategy is cheap. What makes the
    lane real is that running `pytest -m <marker>` actually collects the suite the
    layer names, and the only way to check that without running it is to require
    every module under the layer's paths to declare the marker at module level.
    """
    if layer["marker"] is None or not layer["paths"]:
        return
    declaration = f"pytestmark = pytest.mark.{layer['marker']}"
    for path in layer["paths"]:
        modules = sorted((REPO_ROOT / path).rglob("test_*.py"))
        assert modules, f"layer '{layer['layerId']}' names an empty path: {path}"
        for module in modules:
            assert declaration in module.read_text(encoding="utf-8"), (
                f"{module.relative_to(REPO_ROOT).as_posix()} is collected by layer "
                f"'{layer['layerId']}' and does not declare `{declaration}`"
            )


# --------------------------------------------------------------------------
# Evidence: cited only when it exists, and only by something that produced it
# --------------------------------------------------------------------------


@pytest.mark.parametrize("claim", CLAIMS, ids=lambda claim: claim["claimId"])
def test_a_claim_cites_evidence_exactly_when_it_is_certified(claim: dict) -> None:
    if claim["v1Status"] == "certified":
        assert claim["evidenceRef"], (
            f"claim '{claim['claimId']}' is certified and cites nothing"
        )
    else:
        assert claim["evidenceRef"] is None, (
            f"claim '{claim['claimId']}' is {claim['v1Status']} and cites evidence"
        )


@pytest.mark.parametrize("layer", LAYERS, ids=lambda layer: layer["layerId"])
def test_a_layer_cites_evidence_exactly_when_it_is_implemented(layer: dict) -> None:
    if layer["v1Status"] == "implemented":
        assert layer["evidenceRef"], layer["layerId"]
    else:
        assert layer["evidenceRef"] is None, layer["layerId"]


@pytest.mark.parametrize(
    "row",
    [*LAYERS, *CLAIMS],
    ids=lambda row: row.get("layerId") or row["claimId"],
)
def test_every_cited_record_exists_where_certifying_records_live(row: dict) -> None:
    ref = row["evidenceRef"]
    if ref is None:
        return
    assert ref.startswith(RETENTION["certifyingRecordRoot"] + "/"), ref
    assert (REPO_ROOT / ref).is_file(), ref


@pytest.mark.parametrize("claim", CLAIMS, ids=lambda claim: claim["claimId"])
def test_a_certified_claim_rests_only_on_implemented_layers(claim: dict) -> None:
    if claim["v1Status"] != "certified":
        return
    for layer in cited_layers(claim):
        assert layer["v1Status"] == "implemented", (
            f"claim '{claim['claimId']}' is certified by '{layer['layerId']}', "
            f"which is {layer['v1Status']}"
        )


@pytest.mark.parametrize("lane", LANES, ids=lambda lane: lane["laneId"])
def test_artifact_retention_is_declared_exactly_when_there_are_artifacts(
    lane: dict,
) -> None:
    if lane["artifacts"]:
        assert isinstance(lane["artifactRetentionDays"], int), lane["laneId"]
        assert lane["artifactRetentionDays"] > 0, lane["laneId"]
    else:
        assert lane["artifactRetentionDays"] is None, lane["laneId"]


@pytest.mark.parametrize("lane", LANES, ids=lambda lane: lane["laneId"])
def test_a_lane_claims_automation_only_with_a_workflow_that_exists(lane: dict) -> None:
    """No continuous-integration lane is configured, and nothing may say otherwise."""
    if lane["automated"]:
        assert lane["workflowRef"], lane["laneId"]
        assert (REPO_ROOT / lane["workflowRef"]).is_file(), lane["workflowRef"]
        assert lane["v1Status"] == "automated", lane["laneId"]
    else:
        assert lane["workflowRef"] is None, lane["laneId"]
        assert lane["v1Status"] != "automated", lane["laneId"]


# --------------------------------------------------------------------------
# Deferral, and the capacity boundary it protects
# --------------------------------------------------------------------------


@pytest.mark.parametrize("claim", CLAIMS, ids=lambda claim: claim["claimId"])
def test_a_deferred_claim_says_why(claim: dict) -> None:
    if claim["v1Status"] == "deferred":
        assert claim["deferralReason"], claim["claimId"]
    else:
        assert claim["deferralReason"] is None, claim["claimId"]


@pytest.mark.parametrize("layer", LAYERS, ids=lambda layer: layer["layerId"])
def test_a_deferred_layer_is_cited_only_by_deferred_claims(layer: dict) -> None:
    if layer["v1Status"] != "deferred":
        return
    for claim in CLAIMS:
        if layer["layerId"] in claim["layers"]:
            assert claim["v1Status"] == "deferred", (
                f"claim '{claim['claimId']}' is {claim['v1Status']} and rests on "
                f"deferred layer '{layer['layerId']}'"
            )


@pytest.mark.parametrize("layer", LAYERS, ids=lambda layer: layer["layerId"])
def test_an_unpublishable_result_is_a_deferred_one(layer: dict) -> None:
    """A layer whose output V1 may not publish must not be quietly runnable."""
    if not layer["publishable"]:
        assert layer["v1Status"] == "deferred", layer["layerId"]
        assert layer["marker"] is not None, (
            f"layer '{layer['layerId']}' cannot be deselected without a marker"
        )


@pytest.mark.parametrize("lane", LANES, ids=lambda lane: lane["laneId"])
def test_a_deferred_lane_hosts_only_deferred_layers(lane: dict) -> None:
    if lane["v1Status"] != "deferred":
        return
    for layer in layers_in(lane["laneId"]):
        assert layer["v1Status"] == "deferred", layer["layerId"]


# --------------------------------------------------------------------------
# The documents and the data, compared in both directions
# --------------------------------------------------------------------------


def published_ids(document: str) -> set[str]:
    return set(FIRST_TABLE_COLUMN.findall(document))


def test_the_strategy_document_publishes_every_lane_and_layer(
    strategy_document: str,
) -> None:
    published = published_ids(strategy_document)
    expected = set(LANE_BY_ID) | set(LAYER_BY_ID)
    assert not expected - published, sorted(expected - published)
    stray = published - expected - registered_markers()
    assert not stray, sorted(stray)


def test_the_certification_document_publishes_every_level_and_class(
    certification_document: str,
) -> None:
    published = published_ids(certification_document)
    assert published == set(LEVEL_BY_ID) | set(CLASS_BY_ID), {
        "in the data only": sorted((set(LEVEL_BY_ID) | set(CLASS_BY_ID)) - published),
        "in the document only": sorted(
            published - (set(LEVEL_BY_ID) | set(CLASS_BY_ID))
        ),
    }


def test_the_matrix_publishes_every_claim_and_only_claims(
    matrix_document: str,
) -> None:
    published = published_ids(matrix_document)
    assert published == {claim["claimId"] for claim in CLAIMS}, {
        "in the data only": sorted({claim["claimId"] for claim in CLAIMS} - published),
        "in the document only": sorted(
            published - {claim["claimId"] for claim in CLAIMS}
        ),
    }


def test_the_data_points_back_at_the_documents_that_describe_it() -> None:
    for field in (
        "decisionRef",
        "documentRef",
        "certificationRef",
        "matrixRef",
        "pytestConfigRef",
    ):
        ref = STRATEGY[field]
        assert (REPO_ROOT / ref).is_file(), f"{field} -> {ref}"
