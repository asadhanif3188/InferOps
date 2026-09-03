"""The test inventory, held to the test tree and to the committed strategy.

The strategy beside this one says which layers exist, which lane each runs in,
and what each layer's result may be used to claim. It says nothing about which
suite defends which claim, and there was no way to ask: a reader wanting to know
what would break if a claim stopped being true had to read forty modules and
guess.

The inventory answers that, and this suite is what stops the answer going stale.
Four things are checked, and each corresponds to a way an inventory rots:

1. **A module missing from it.** Every ``test_*.py`` under ``tests/`` is listed,
   and every listed module exists. A suite nobody inventoried is a suite whose
   purpose is whatever a reader infers from its name.
2. **A layer disagreeing with the strategy.** The layer and marker recorded for a
   module are derived from the strategy's own paths and compared, so a module
   moved into another directory cannot keep its old attribution.
3. **A claim a layer cannot support.** A module may name only claims whose layers
   include its own. Without this, a `mock` suite could be recorded as defending a
   claim that requires a real runtime, which is the exact confusion the
   certification ceiling exists to prevent.
4. **A claim nothing defends.** Every claim in the strategy is either named by a
   module or recorded as a gap with a reason. A gap that quietly acquires a suite,
   or a claim that quietly loses one, fails here.

What this suite establishes is that the inventory describes the test tree. It
establishes nothing about whether a suite is any good, and nothing about what its
result may certify — that is the layer's evidence class, decided in the strategy
and enforced by ``test_test_strategy.py``.

Every check reads files from this repository and nothing else. No network, no
cluster, no model, no clock, no randomness.
"""

from __future__ import annotations

import ast
import json
import re
from pathlib import Path

import pytest

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]
TESTING_DIR = REPO_ROOT / "docs" / "testing"
INVENTORY_PATH = TESTING_DIR / "test-inventory.v1alpha1.json"
STRATEGY_PATH = TESTING_DIR / "test-strategy.v1alpha1.json"
TESTS_ROOT = REPO_ROOT / "tests"

EXPECTED_INVENTORY_ID = "https://inferops.io/testing/test-inventory.v1alpha1.json"
EXPECTED_CONTRACT_VERSION = "inferops.io/v1alpha1"

REQUIRED_MODULE_FIELDS = ("module", "layer", "marker", "protects", "claims", "note")
REQUIRED_GAP_FIELDS = ("claimId", "reason", "coveredBy")

INVENTORY = json.loads(INVENTORY_PATH.read_text(encoding="utf-8"))
STRATEGY = json.loads(STRATEGY_PATH.read_text(encoding="utf-8"))

MODULES: list[dict] = INVENTORY["modules"]
GAPS: list[dict] = INVENTORY["coverageGaps"]
LAYERS: list[dict] = STRATEGY["layers"]
CLAIMS: list[dict] = STRATEGY["claims"]

LAYER_BY_ID = {layer["layerId"]: layer for layer in LAYERS}
CLAIM_BY_ID = {claim["claimId"]: claim for claim in CLAIMS}
ENTRY_BY_MODULE = {entry["module"]: entry for entry in MODULES}


def collected_modules() -> set[str]:
    """Every module pytest would collect, as a repository-relative POSIX path."""
    return {
        path.relative_to(REPO_ROOT).as_posix() for path in TESTS_ROOT.rglob("test_*.py")
    }


def layer_for(module: str) -> str | None:
    """The layer whose declared paths contain this module, from the strategy.

    Derived rather than read from the inventory, because the whole point of the
    comparison below is that the two are independent.
    """
    for layer in LAYERS:
        for declared in layer["paths"]:
            if module.startswith(f"{declared}/"):
                return str(layer["layerId"])
    return None


COLLECTED = collected_modules()


def module_id(entry: dict) -> str:
    return str(entry["module"])


# --------------------------------------------------------------------------
# Shape
# --------------------------------------------------------------------------


def test_the_inventory_declares_its_identity_and_contract_version() -> None:
    assert INVENTORY["$id"] == EXPECTED_INVENTORY_ID
    assert INVENTORY["contractVersion"] == EXPECTED_CONTRACT_VERSION


def test_the_inventory_is_not_empty() -> None:
    assert MODULES, "an inventory of nothing would pass every check below"


def test_the_inventory_points_back_at_the_records_it_describes() -> None:
    for field in ("strategyRef", "documentRef", "matrixRef", "pytestConfigRef"):
        reference = INVENTORY[field]
        assert (REPO_ROOT / reference).is_file(), f"{field} -> {reference}"


@pytest.mark.parametrize("entry", MODULES, ids=module_id)
def test_every_entry_declares_every_required_field(entry: dict) -> None:
    for field in REQUIRED_MODULE_FIELDS:
        assert field in entry, (entry["module"], field)


@pytest.mark.parametrize("gap", GAPS, ids=lambda gap: gap["claimId"])
def test_every_gap_declares_every_required_field(gap: dict) -> None:
    for field in REQUIRED_GAP_FIELDS:
        assert field in gap, (gap["claimId"], field)


def test_no_module_is_inventoried_twice() -> None:
    listed = [entry["module"] for entry in MODULES]
    assert len(listed) == len(set(listed)), sorted(
        name for name in set(listed) if listed.count(name) > 1
    )


# --------------------------------------------------------------------------
# The inventory and the test tree
# --------------------------------------------------------------------------


def test_every_collected_module_is_inventoried() -> None:
    """A suite nobody inventoried is a suite whose purpose is inferred from its name.

    This is the check that makes the inventory a description of the test tree
    rather than a description of the part of it somebody remembered.
    """
    listed = set(ENTRY_BY_MODULE)
    assert listed >= COLLECTED, sorted(COLLECTED - listed)


def test_every_inventoried_module_exists() -> None:
    """The other direction, which catches a module renamed or deleted."""
    listed = set(ENTRY_BY_MODULE)
    assert listed <= COLLECTED, sorted(listed - COLLECTED)


@pytest.mark.parametrize("entry", MODULES, ids=module_id)
def test_every_entry_says_what_it_protects(entry: dict) -> None:
    """An empty sentence here is an entry that satisfies the count and nothing else."""
    protects = entry["protects"]
    assert isinstance(protects, str) and protects.strip(), entry["module"]


# --------------------------------------------------------------------------
# The inventory and the strategy
# --------------------------------------------------------------------------


@pytest.mark.parametrize("entry", MODULES, ids=module_id)
def test_every_entry_records_the_layer_the_strategy_gives_its_path(entry: dict) -> None:
    """A module moved to another directory cannot keep its old attribution.

    The layer is derived from the strategy's own declared paths and compared,
    rather than read from the inventory and trusted.
    """
    assert entry["layer"] == layer_for(entry["module"]), {
        "module": entry["module"],
        "inventory": entry["layer"],
        "strategy": layer_for(entry["module"]),
    }


@pytest.mark.parametrize("entry", MODULES, ids=module_id)
def test_every_entry_records_the_marker_its_layer_declares(entry: dict) -> None:
    layer = LAYER_BY_ID[entry["layer"]]
    assert entry["marker"] == layer["marker"], (entry["module"], layer["marker"])


@pytest.mark.parametrize("entry", MODULES, ids=module_id)
def test_every_module_declares_its_layer_marker_at_module_level(entry: dict) -> None:
    """The same rule the strategy suite applies, applied through the inventory.

    The strategy suite reaches a module through a layer's paths. This reaches it
    through the inventory entry, so a module inventoried under a layer whose
    marker it does not declare fails even if the layer's path glob would have
    missed it.
    """
    declaration = f"pytestmark = pytest.mark.{entry['marker']}"
    source = (REPO_ROOT / entry["module"]).read_text(encoding="utf-8")
    assert declaration in source, (entry["module"], declaration)


@pytest.mark.parametrize("entry", MODULES, ids=module_id)
def test_every_claim_an_entry_names_is_a_claim_the_strategy_publishes(
    entry: dict,
) -> None:
    for claim_id in entry["claims"]:
        assert claim_id in CLAIM_BY_ID, (entry["module"], claim_id)


@pytest.mark.parametrize("entry", MODULES, ids=module_id)
def test_a_module_names_only_claims_its_own_layer_supports(entry: dict) -> None:
    """A `mock` suite may not be recorded as defending a claim needing a runtime.

    The claim matrix decides which layers a claim rests on, and the certification
    ceiling decides what each layer's result may support. An inventory free to
    attribute any claim to any suite would route around both.
    """
    for claim_id in entry["claims"]:
        supporting = CLAIM_BY_ID[claim_id]["layers"]
        assert entry["layer"] in supporting, {
            "module": entry["module"],
            "layer": entry["layer"],
            "claim": claim_id,
            "layers the claim rests on": supporting,
        }


@pytest.mark.parametrize("entry", MODULES, ids=module_id)
def test_an_entry_naming_no_claim_says_why(entry: dict) -> None:
    """A suite defending no published claim is a fact worth reading, not a blank.

    Several suites here protect a repository decision rather than a product
    claim. Recording the reason is what keeps "no claim" distinguishable from
    "nobody filled this in".
    """
    if entry["claims"]:
        return
    note = entry["note"]
    assert isinstance(note, str) and note.strip(), entry["module"]


@pytest.mark.parametrize("entry", MODULES, ids=module_id)
def test_an_entry_names_each_claim_once(entry: dict) -> None:
    assert len(entry["claims"]) == len(set(entry["claims"])), entry["module"]


# --------------------------------------------------------------------------
# Coverage, in both directions
# --------------------------------------------------------------------------


def covered_claims() -> set[str]:
    return {claim_id for entry in MODULES for claim_id in entry["claims"]}


def test_every_claim_is_covered_by_a_module_or_recorded_as_a_gap() -> None:
    """The question the inventory exists to answer, asked of every claim.

    A claim no module names and no gap records is a claim whose defence nobody
    can point at — which is the state this file was written to make impossible to
    reach quietly.
    """
    accounted = covered_claims() | {gap["claimId"] for gap in GAPS}
    assert set(CLAIM_BY_ID) == accounted, {
        "neither covered nor recorded as a gap": sorted(set(CLAIM_BY_ID) - accounted),
        "recorded and not a claim": sorted(accounted - set(CLAIM_BY_ID)),
    }


def test_no_claim_is_both_covered_and_recorded_as_a_gap() -> None:
    """A gap that acquired a suite is a gap that should have been closed in writing."""
    overlap = covered_claims() & {gap["claimId"] for gap in GAPS}
    assert not overlap, sorted(overlap)


@pytest.mark.parametrize("gap", GAPS, ids=lambda gap: gap["claimId"])
def test_every_gap_names_a_claim_and_says_why(gap: dict) -> None:
    assert gap["claimId"] in CLAIM_BY_ID, gap["claimId"]
    assert isinstance(gap["reason"], str) and gap["reason"].strip(), gap["claimId"]


@pytest.mark.parametrize("gap", GAPS, ids=lambda gap: gap["claimId"])
def test_a_gap_covered_by_something_names_it(gap: dict) -> None:
    """`coveredBy` is either absent or a thing, never an empty reassurance."""
    covered_by = gap["coveredBy"]
    if covered_by is None:
        return
    assert isinstance(covered_by, str) and covered_by.strip(), gap["claimId"]


@pytest.mark.parametrize("layer", LAYERS, ids=lambda layer: layer["layerId"])
def test_a_layer_with_test_paths_has_at_least_one_inventoried_module(
    layer: dict,
) -> None:
    """A layer naming a directory that contributes nothing to the inventory.

    The strategy already refuses a layer whose declared path holds no module.
    This is the same property read from the other side, and it is what catches a
    layer whose modules were all inventoried under something else.
    """
    if not layer["paths"]:
        return
    attributed = [entry for entry in MODULES if entry["layer"] == layer["layerId"]]
    assert attributed, layer["layerId"]


# --------------------------------------------------------------------------
# The document beside the data
# --------------------------------------------------------------------------


@pytest.fixture(scope="module")
def inventory_document() -> str:
    return (TESTING_DIR / "test-inventory.md").read_text(encoding="utf-8")


def test_the_document_names_every_layer_the_inventory_attributes_to(
    inventory_document: str,
) -> None:
    """A reader arriving at the document sees every grouping the data uses."""
    for layer_id in sorted({entry["layer"] for entry in MODULES}):
        assert layer_id in inventory_document, layer_id


def test_the_document_names_every_recorded_gap(inventory_document: str) -> None:
    """A gap recorded only in the data is a gap a reader will not find."""
    for gap in GAPS:
        assert gap["claimId"] in inventory_document, gap["claimId"]


def test_the_document_names_every_module_that_defends_no_claim(
    inventory_document: str,
) -> None:
    """The honest half of the inventory is the half most worth publishing."""
    for entry in MODULES:
        if entry["claims"]:
            continue
        assert entry["module"] in inventory_document, entry["module"]


def test_the_document_counts_the_modules_that_defend_no_claim_correctly(
    inventory_document: str,
) -> None:
    """A published count is a claim, and this one drifted before it was checked.

    Independent review of this change found the document saying "five" while the
    data held six and the section below it said six. Naming every module is not
    the same as counting them, and a reader who trusts the count reads a
    different document from the one the data describes.
    """
    without_claims = [entry for entry in MODULES if not entry["claims"]]
    written = NUMBER_WORDS[len(without_claims)]
    assert re.search(rf"\bThere are {written}\b", inventory_document), {
        "modules defending no claim": len(without_claims),
        "the document should say": written,
    }


def test_the_document_counts_the_coverage_gaps_correctly(
    inventory_document: str,
) -> None:
    written = NUMBER_WORDS[len(GAPS)]
    assert re.search(
        rf"\b{written.capitalize()} claims are not defended\b", inventory_document
    ), {"gaps": len(GAPS), "the document should say": written}


# --------------------------------------------------------------------------
# How many layers exist, in every living document that says
# --------------------------------------------------------------------------

#: The documents that describe the current state of the test layers. A record
#: under ``docs/proof/`` and an entry in the changelog are deliberately excluded:
#: both are statements about a moment that has passed, and rewriting one to match
#: today would be falsifying a record rather than fixing a document.
LIVING_DOCUMENTS = (
    "README.md",
    "CONTRIBUTING.md",
    "docs/testing/README.md",
    "docs/testing/test-strategy.md",
    "docs/testing/test-inventory.md",
)

#: Written-out numbers, because these documents write them out. Only as far as
#: the layer count can reach.
NUMBER_WORDS: dict[int, str] = {
    0: "zero",
    1: "one",
    2: "two",
    3: "three",
    4: "four",
    5: "five",
    6: "six",
    7: "seven",
    8: "eight",
    9: "nine",
    10: "ten",
    11: "eleven",
    12: "twelve",
    13: "thirteen",
    14: "fourteen",
    15: "fifteen",
}

WORD_NUMBERS: dict[str, int] = {word: value for value, word in NUMBER_WORDS.items()}

#: "Eight of eleven test layers exist", "Three of the eleven layers ... have no
#: code" — the two forms these documents use, with the clause that decides which
#: number is being claimed captured alongside.
LAYER_COUNT = re.compile(
    r"\b(?P<count>[A-Za-z]+) of (?:the )?(?P<total>[a-z]+) (?:test )?layers\b"
    r"(?P<tail>[^.]*)",
)


@pytest.mark.parametrize("document", LIVING_DOCUMENTS, ids=LIVING_DOCUMENTS)
def test_a_document_counting_the_layers_counts_them_correctly(document: str) -> None:
    """Four documents state how many test layers exist, and nothing compared them.

    They drifted: one said seven while two said eight and the data said eight.
    The sentence is a claim about the strategy data, so it is checked against the
    strategy data — in both forms these documents use, "N of eleven exist" and
    "N of the eleven have no code".
    """
    text = (REPO_ROOT / document).read_text(encoding="utf-8")
    implemented = sum(1 for layer in LAYERS if layer["v1Status"] == "implemented")

    for match in LAYER_COUNT.finditer(text):
        count_word = match.group("count").lower()
        total_word = match.group("total").lower()
        if count_word not in WORD_NUMBERS or total_word not in WORD_NUMBERS:
            continue
        assert WORD_NUMBERS[total_word] == len(LAYERS), {
            "document": document,
            "sentence": match.group(0),
            "layers in the data": len(LAYERS),
        }
        tail = match.group("tail").lower()
        if "no code" in tail:
            expected = len(LAYERS) - implemented
        elif "exist" in tail:
            expected = implemented
        else:
            continue
        assert WORD_NUMBERS[count_word] == expected, {
            "document": document,
            "sentence": match.group(0),
            "the data says": expected,
        }


# --------------------------------------------------------------------------
# The lane separation the inventory reports
# --------------------------------------------------------------------------


def test_a_module_outside_the_default_lane_is_deselected_by_the_default_expression() -> (
    None
):
    """The story's own criterion, read through the inventory rather than the config.

    ``test_test_strategy.py`` asserts that every marker belonging to a layer
    outside the default lane appears in the default exclusion. This asserts the
    consequence for the modules themselves: every inventoried module whose layer
    needs a cluster or a model carries a marker the default lane excludes.
    """
    import configparser

    parser = configparser.ConfigParser()
    parser.read_string((REPO_ROOT / "pytest.ini").read_text(encoding="utf-8"))
    addopts = parser["pytest"]["addopts"]

    for entry in MODULES:
        layer = LAYER_BY_ID[entry["layer"]]
        if not (layer["requiresModel"] or layer["requiresCluster"]):
            continue
        assert f"not {entry['marker']}" in addopts, entry["module"]


def test_a_default_lane_module_needs_no_model_or_cluster() -> None:
    """The other half: nothing in the default lane is attributed to a costly layer."""
    default_lane = next(lane for lane in STRATEGY["lanes"] if not lane["optIn"])
    for entry in MODULES:
        layer = LAYER_BY_ID[entry["layer"]]
        if layer["lane"] != default_lane["laneId"]:
            continue
        assert not layer["requiresModel"], entry["module"]
        assert not layer["requiresCluster"], entry["module"]


def test_the_inventory_reads_as_python_it_did_not_execute() -> None:
    """Every inventoried module parses, which is what makes the marker check real.

    A module the inventory names that cannot be parsed would still pass the
    textual marker check above by accident. Parsing it is cheap and turns that
    into a fact about the module rather than about its bytes.
    """
    for entry in MODULES:
        path = REPO_ROOT / entry["module"]
        ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
