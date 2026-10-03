"""The released V1 synchronous workload, rendered through V2: who owns each value now.

V1 installed its real release from a values file somebody wrote by hand, over the
chart's defaults. V2 renders the same workload from a WorkloadContract, an
EnvironmentBinding, and platform defaults, and keeps a hand-written file only for
what no input owns. The record
``docs/domain/v1-synchronous-compatibility.v1alpha1.json`` names, for every chart
value either release sets, where V1 took it from and who owns it in V2. This suite
holds that record against the code and the committed files, so it cannot describe a
migration that did not happen:

- every value either release sets has exactly one row, and no row names a value
  neither sets;
- a row's V1 source is where V1 took the value, and its V2 owner is the owner the
  renderer's disposition table and the boundary's ownership table give it;
- no value the contract owns is written by hand: the hand-written file is admitted
  beside the generated values, and every contract-owned chart value is generated,
  the two derived from the model pins included;
- the two releases merge to the same values except the differences the record
  states, with both values;
- no hand-written string restates a contract pin: that is measured, not assumed.

Every check here reads committed files and runs the render path in memory. Nothing is
installed, so a pass is C0: it says the V2 release input describes the V1 workload,
not that it serves it. The Helm lint and render of the same pair run in the chart
suite, ``tests/architecture/test_helm_chart.py``, where the CI job that installs a
pinned Helm forbids a skip.
"""

from __future__ import annotations

import copy
import json
import re
from collections.abc import Callable, Iterator, Mapping
from pathlib import Path
from typing import Any

import pytest
import yaml

from inferops.domain.render import admit_manual_values
from inferops.domain.render.helm_values import (
    DERIVED_HELM_VALUES,
    HELM_VALUE_DISPOSITIONS,
)
from inferops.domain.render.ownership import RENDER_FIELD_OWNERSHIP
from tools.generated_release import DECLARED_RELEASES, derive

pytestmark = pytest.mark.unit

REPO_ROOT = Path(__file__).resolve().parents[2]
RECORD_PATH = (
    REPO_ROOT / "docs" / "domain" / "v1-synchronous-compatibility.v1alpha1.json"
)
DOC = REPO_ROOT / "docs" / "domain" / "v1-synchronous-compatibility.md"

#: A hand-written string is checked for a contract pin only when the pin is at least
#: this long. Shorter contract values - ``local``, ``real``, ``demo``, ``6`` - occur
#: inside unrelated strings, ``localhost`` for one, and would be reported as pins.
PIN_MIN_LENGTH = 8


def _load_yaml(path: Path) -> Any:
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def load_record() -> dict[str, Any]:
    document = json.loads(RECORD_PATH.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    return document


def leaves(document: Any, prefix: str = "") -> Iterator[tuple[str, Any]]:
    """Every leaf of a values document by dotted path. An empty mapping is a leaf."""
    if isinstance(document, Mapping) and document:
        for key, value in document.items():
            yield from leaves(value, f"{prefix}{key}.")
    else:
        yield prefix.rstrip("."), document


def deep_merge(base: Mapping[str, Any], *overlays: Mapping[str, Any]) -> dict[str, Any]:
    """Values files merged the way Helm merges them: mappings by key, the rest replaced."""
    merged: dict[str, Any] = copy.deepcopy(dict(base))
    for overlay in overlays:
        for key, value in overlay.items():
            current = merged.get(key)
            if isinstance(current, Mapping) and isinstance(value, Mapping):
                merged[key] = deep_merge(current, value)
            else:
                merged[key] = copy.deepcopy(value)
    return merged


OWNER_OF = {row.name: row.layer.value for row in RENDER_FIELD_OWNERSHIP}
TARGETS_OF = {name: d.targets for name, d in HELM_VALUE_DISPOSITIONS.items()}
DERIVED_FROM = {path: d.sources for path, d in DERIVED_HELM_VALUES.items()}


def contract_owned_targets() -> set[str]:
    """Every chart value the contract owns: rendered from a contract value, or derived
    from contract values only."""
    rendered = {
        target
        for name, targets in TARGETS_OF.items()
        if OWNER_OF.get(name) == "workload-intent"
        for target in targets
    }
    derived = {
        path
        for path, sources in DERIVED_FROM.items()
        if all(OWNER_OF.get(source) == "workload-intent" for source in sources)
    }
    return rendered | derived


class Files:
    """The committed files a record names, read once."""

    def __init__(self, record: Mapping[str, Any]) -> None:
        target, v2 = record["target"], record["v2"]
        self.chart_defaults = _load_yaml(REPO_ROOT / target["chartDefaults"])
        self.v1_values = _load_yaml(REPO_ROOT / target["valuesFile"])
        release_dir = REPO_ROOT / v2["generatedRelease"]
        self.generated = _load_yaml(release_dir / "values.generated.yaml")
        self.hand_written = _load_yaml(REPO_ROOT / v2["handWrittenValues"])
        self.v1_leaves = dict(leaves(self.v1_values))
        self.generated_leaves = dict(leaves(self.generated))
        self.hand_written_leaves = dict(leaves(self.hand_written))


FILES = Files(load_record())


def _restated_pins(
    value: Any, generated: Mapping[str, Any], rows: Mapping[str, Mapping[str, Any]]
) -> list[str]:
    """The contract-owned generated chart values a hand-written string contains."""
    if not isinstance(value, str):
        return []
    return sorted(
        path
        for path, pin in generated.items()
        if rows.get(path, {}).get("owner") == "workload-intent"
        and isinstance(pin, str)
        and len(pin) >= PIN_MIN_LENGTH
        and pin in value
    )


def record_problems(record: Mapping[str, Any], files: Files = FILES) -> list[str]:
    """Every way the record disagrees with the code and the committed files."""
    problems: list[str] = []
    rows_list = record["rows"]
    rows = {row["chartValue"]: row for row in rows_list}
    if len(rows) != len(rows_list):
        problems.append("a chart value has more than one row")

    every = (
        set(files.v1_leaves)
        | set(files.generated_leaves)
        | set(files.hand_written_leaves)
    )
    for path in sorted(every - set(rows)):
        problems.append(f"{path}: set by a release and has no row")
    for path in sorted(set(rows) - every):
        problems.append(f"{path}: has a row and neither release sets it")

    classes = record["handWrittenClasses"]
    for path, row in sorted(rows.items()):
        if path not in every:
            continue
        expected_v1 = "values-file" if path in files.v1_leaves else "chart-default"
        if row["v1"] != expected_v1:
            problems.append(f"{path}: V1 took it from {expected_v1}, not {row['v1']}")
        if expected_v1 == "chart-default" and path not in dict(
            leaves(files.chart_defaults)
        ):
            problems.append(f"{path}: V1 set nothing and the chart has no default")

        generated = path in files.generated_leaves
        hand_written = path in files.hand_written_leaves
        if generated and hand_written:
            problems.append(f"{path}: both generated and hand-written")
        if row["v2"] == "generated":
            if not generated:
                problems.append(f"{path}: row says generated, and it is not")
            if "derivedFrom" in row or path in DERIVED_FROM:
                sources = tuple(row.get("derivedFrom", ()))
                if DERIVED_FROM.get(path) != sources or "contextValue" in row:
                    problems.append(
                        f"{path}: derived from {list(DERIVED_FROM.get(path, ()))}, "
                        f"and the row says {list(sources)}"
                    )
                else:
                    owners = {OWNER_OF[source] for source in sources}
                    if owners != {row.get("owner")}:
                        problems.append(
                            f"{path}: its sources are owned by {sorted(owners)}, "
                            f"not {row.get('owner')}"
                        )
            else:
                context_value = row.get("contextValue")
                if path not in TARGETS_OF.get(context_value, ()):
                    problems.append(f"{path}: {context_value} does not render to it")
                elif row.get("owner") != OWNER_OF[context_value]:
                    problems.append(
                        f"{path}: {context_value} is owned by "
                        f"{OWNER_OF[context_value]}, not {row.get('owner')}"
                    )
            if "class" in row or "restates" in row:
                problems.append(f"{path}: a generated row has a hand-written class")
        elif row["v2"] == "hand-written":
            if not hand_written:
                problems.append(f"{path}: row says hand-written, and it is not")
            if row.get("class") not in classes:
                problems.append(f"{path}: hand-written under no published class")
            if "contextValue" in row or "owner" in row or "derivedFrom" in row:
                problems.append(f"{path}: a hand-written row names an owner")
            measured = _restated_pins(
                files.hand_written_leaves.get(path), files.generated_leaves, rows
            )
            if row.get("restates", []) != measured:
                problems.append(
                    f"{path}: restates {measured}, and the row says {row.get('restates', [])}"
                )
        else:
            problems.append(f"{path}: unknown V2 source {row['v2']!r}")

    v1 = dict(leaves(deep_merge(files.chart_defaults, files.v1_values)))
    v2 = dict(
        leaves(deep_merge(files.chart_defaults, files.generated, files.hand_written))
    )
    differing = {path for path in set(v1) | set(v2) if v1.get(path) != v2.get(path)}
    recorded = {path for path, row in rows.items() if "difference" in row}
    for path in sorted(differing - recorded):
        problems.append(
            f"{path}: the releases differ and the record states no difference"
        )
    for path in sorted(recorded - differing):
        problems.append(f"{path}: a difference is recorded and the releases agree")
    for path in sorted(recorded & differing):
        stated = rows[path]["difference"]
        if (stated.get("v1"), stated.get("v2")) != (v1.get(path), v2.get(path)):
            problems.append(f"{path}: the recorded values are not the releases' values")
        if not str(stated.get("reason", "")).strip():
            problems.append(f"{path}: a difference without a reason")
    return problems


# --------------------------------------------------------------------------
# 1. The record names the committed inputs
# --------------------------------------------------------------------------


def test_every_file_the_record_names_exists() -> None:
    record = load_record()
    for section in ("target", "v2"):
        for key, value in record[section].items():
            if key in {"description", "release", "chartVersion"}:
                continue
            assert (REPO_ROOT / value).exists(), f"{section}.{key}: {value}"


def test_the_target_is_the_chart_version_the_record_names() -> None:
    record = load_record()
    chart = _load_yaml(REPO_ROOT / record["target"]["chart"] / "Chart.yaml")
    assert chart["version"] == record["target"]["chartVersion"]


def test_the_v2_inputs_are_the_declared_reference_release() -> None:
    """The record's V2 side is the release the drift check holds to its sources."""
    v2 = load_record()["v2"]
    declared = [d for d in DECLARED_RELEASES if d.directory == v2["generatedRelease"]]
    assert len(declared) == 1
    assert declared[0].contract == v2["contract"]
    assert declared[0].bindings == (v2["binding"],)
    assert declared[0].platform_defaults == v2["platformDefaults"]


# --------------------------------------------------------------------------
# 2. The record agrees with the code and the files
# --------------------------------------------------------------------------


def test_the_record_agrees_with_the_code_and_the_committed_files() -> None:
    assert record_problems(load_record()) == []


def test_every_value_either_release_sets_has_exactly_one_row() -> None:
    rows = [row["chartValue"] for row in load_record()["rows"]]
    every = (
        set(FILES.v1_leaves)
        | set(FILES.generated_leaves)
        | set(FILES.hand_written_leaves)
    )
    assert sorted(rows) == sorted(every)
    assert rows == sorted(rows), "rows are kept in chart-value order"


def test_the_record_measures_the_migration_it_publishes() -> None:
    """The counts the page states, from the record: 40 values, 27 of them generated,
    2 of those derived."""
    rows = load_record()["rows"]
    generated = [row for row in rows if row["v2"] == "generated"]
    assert len(rows) == 40
    assert len(generated) == 27
    assert len(FILES.generated_leaves) == 27
    assert sorted(row["chartValue"] for row in generated if "derivedFrom" in row) == [
        "model.artifact.sourceUrl",
        "model.license.reference",
    ]
    by_owner = {
        owner: sum(1 for row in generated if row["owner"] == owner)
        for owner in ("workload-intent", "environment-binding", "platform-defaults")
    }
    assert by_owner == {
        "workload-intent": 22,
        "environment-binding": 2,
        "platform-defaults": 3,
    }
    from_values_file = [row for row in generated if row["v1"] == "values-file"]
    assert len(from_values_file) == 19
    assert len([row for row in rows if row["v2"] == "hand-written"]) == 13


# --------------------------------------------------------------------------
# 3. No claim-relevant workload intent is written by hand
# --------------------------------------------------------------------------


def test_the_hand_written_file_is_admitted_beside_the_generated_values() -> None:
    """Admission refuses a hand-written value that sets, replaces, or removes a
    generated one; the reference file has none."""
    generated = derive(DECLARED_RELEASES[0]).values
    admitted = admit_manual_values(generated, FILES.hand_written)
    assert admitted.documents()[1] == FILES.hand_written


def test_every_contract_owned_chart_value_is_generated_and_none_is_hand_written() -> (
    None
):
    contract_targets = contract_owned_targets()
    assert len(contract_targets) == 22
    assert contract_targets <= set(FILES.generated_leaves)
    for target in contract_targets:
        for path in FILES.hand_written_leaves:
            assert not (
                path == target
                or path.startswith(f"{target}.")
                or target.startswith(f"{path}.")
            ), f"{path} is hand-written over the contract-owned {target}"


def test_v1_wrote_contract_intent_by_hand_that_v2_generates() -> None:
    """The migration itself: 18 contract-owned values V1's file set by hand, and 4
    more V1 left to the chart's defaults, are now generated from the contract."""
    rows = load_record()["rows"]
    moved = [
        row["chartValue"]
        for row in rows
        if row.get("owner") == "workload-intent" and row["v1"] == "values-file"
    ]
    defaulted = [
        row["chartValue"]
        for row in rows
        if row.get("owner") == "workload-intent" and row["v1"] == "chart-default"
    ]
    assert len(moved) == 18
    assert sorted(defaulted) == [
        "runtime.replicaCount",
        "runtime.resources.limits.cpu",
        "runtime.resources.limits.memory",
        "security.secretRefs",
    ]


def test_the_generated_digest_decides_which_bytes_the_acquisition_accepts() -> None:
    """The committed V1 render's acquisition compares what it fetched with the digest
    the generated values set, and the download location, now generated too, appears
    only in the download command."""
    render = (REPO_ROOT / load_record()["target"]["committedRender"]).read_text(
        encoding="utf-8"
    )
    digest = FILES.generated_leaves["model.artifact.sha256"].removeprefix("sha256:")
    assert f"want_sha='{digest}'" in render
    url = FILES.generated_leaves["model.artifact.sourceUrl"]
    lines = [line for line in render.splitlines() if url in line]
    assert len(lines) == 1 and "wget" in lines[0]


def test_no_hand_written_string_restates_a_contract_pin() -> None:
    """Closed, and measured: the two strings that used to repeat the model's
    repository, revision, and file are generated now. No row restates a pin, and the
    record check measures every hand-written string against every contract-owned
    generated value."""
    rows = {row["chartValue"]: row for row in load_record()["rows"]}
    assert [path for path, row in rows.items() if "restates" in row] == []
    for path, row in rows.items():
        if row["v2"] == "hand-written":
            assert (
                _restated_pins(
                    FILES.hand_written_leaves.get(path), FILES.generated_leaves, rows
                )
                == []
            ), path


# --------------------------------------------------------------------------
# 4. The one difference is stated, with both values
# --------------------------------------------------------------------------


def test_the_only_difference_is_the_environment_label() -> None:
    rows = load_record()["rows"]
    differences = {
        row["chartValue"]: row["difference"] for row in rows if "difference" in row
    }
    assert list(differences) == ["telemetry.deploymentEnvironment"]
    stated = differences["telemetry.deploymentEnvironment"]
    assert (stated["v1"], stated["v2"]) == ("dev", "local")
    assert FILES.chart_defaults["telemetry"]["deploymentEnvironment"] == "dev"


# --------------------------------------------------------------------------
# 5. The checks are not decorative
# --------------------------------------------------------------------------


def _row(record: dict[str, Any], path: str) -> dict[str, Any]:
    return next(row for row in record["rows"] if row["chartValue"] == path)


MUTATIONS: dict[str, tuple[Callable[[dict[str, Any]], None], str]] = {
    "a row removed": (
        lambda r: r["rows"].remove(_row(r, "model.alias")),
        "model.alias: set by a release and has no row",
    ),
    "a row for a value nobody sets": (
        lambda r: r["rows"].append(
            {
                "chartValue": "model.nickname",
                "v1": "values-file",
                "v2": "hand-written",
                "class": "model-metadata",
            }
        ),
        "model.nickname: has a row and neither release sets it",
    ),
    "the wrong owner": (
        lambda r: _row(r, "api.replicaCount").__setitem__("owner", "workload-intent"),
        "api.replicaCount: api.replicas is owned by environment-binding",
    ),
    "the wrong context value": (
        lambda r: _row(r, "runtime.replicaCount").__setitem__(
            "contextValue", "serving.replicas.maximum"
        ),
        "runtime.replicaCount: serving.replicas.maximum does not render to it",
    ),
    "the wrong V1 source": (
        lambda r: _row(r, "runtime.replicaCount").__setitem__("v1", "values-file"),
        "runtime.replicaCount: V1 took it from chart-default",
    ),
    "a generated value called hand-written": (
        lambda r: _row(r, "profile").update(
            {"v2": "hand-written", "class": "host-operation"}
        ),
        "profile: row says hand-written, and it is not",
    ),
    "an unpublished class": (
        lambda r: _row(r, "model.alias").__setitem__("class", "convenience"),
        "model.alias: hand-written under no published class",
    ),
    "a derived value called hand-written": (
        lambda r: _row(r, "model.license.reference").update(
            {"v2": "hand-written", "class": "model-metadata"}
        ),
        "model.license.reference: row says hand-written, and it is not",
    ),
    "a derived value with the wrong sources": (
        lambda r: _row(r, "model.artifact.sourceUrl").__setitem__(
            "derivedFrom", ["model.artifact.repository"]
        ),
        "model.artifact.sourceUrl: derived from",
    ),
    "a restated pin left unsaid": (
        lambda r: _row(r, "model.alias").__setitem__("restates", ["model.revision"]),
        "model.alias: restates",
    ),
    "the difference left out": (
        lambda r: _row(r, "telemetry.deploymentEnvironment").pop("difference"),
        "telemetry.deploymentEnvironment: the releases differ",
    ),
    "a difference with the wrong value": (
        lambda r: _row(r, "telemetry.deploymentEnvironment")["difference"].__setitem__(
            "v1", "ci"
        ),
        "telemetry.deploymentEnvironment: the recorded values",
    ),
    "a difference without a reason": (
        lambda r: _row(r, "telemetry.deploymentEnvironment")["difference"].__setitem__(
            "reason", " "
        ),
        "telemetry.deploymentEnvironment: a difference without a reason",
    ),
}


@pytest.mark.parametrize("name", sorted(MUTATIONS))
def test_a_record_that_misstates_the_migration_is_caught(name: str) -> None:
    mutate, expected = MUTATIONS[name]
    record = load_record()
    mutate(record)
    problems = record_problems(record)
    assert any(problem.startswith(expected) for problem in problems), problems


def test_a_hand_written_copy_of_a_derived_value_is_caught_by_the_record_check() -> None:
    """The F1 regression at the record layer: the old hand-written download URL,
    restored beside the generated one, is both generated and hand-written."""
    files = Files(load_record())
    files.hand_written = deep_merge(
        files.hand_written,
        {
            "model": {
                "artifact": {
                    "sourceUrl": FILES.generated_leaves["model.artifact.sourceUrl"]
                }
            }
        },
    )
    files.hand_written_leaves = dict(leaves(files.hand_written))
    assert (
        "model.artifact.sourceUrl: both generated and hand-written"
        in record_problems(load_record(), files)
    )


def test_a_hand_written_contract_value_is_caught_by_the_record_check() -> None:
    """If the hand-written file set a contract-owned value again, the record could
    not describe the releases: the value would be both generated and hand-written."""
    files = Files(load_record())
    files.hand_written = deep_merge(
        files.hand_written, {"model": {"revision": "f" * 40}}
    )
    files.hand_written_leaves = dict(leaves(files.hand_written))
    assert "model.revision: both generated and hand-written" in record_problems(
        load_record(), files
    )


# --------------------------------------------------------------------------
# 6. The published page is the record
# --------------------------------------------------------------------------


def _note(row: Mapping[str, Any]) -> str:
    if "difference" in row:
        d = row["difference"]
        return f"V1 `{d['v1']}`, V2 `{d['v2']}`: intended"
    if "restates" in row:
        return "Repeats " + ", ".join(f"`{p}`" for p in row["restates"])
    if "derivedFrom" in row:
        return "Derived from " + ", ".join(f"`{p}`" for p in row["derivedFrom"])
    return ""


def published_rows_table(record: Mapping[str, Any]) -> str:
    lines = [
        "| Chart value | V1 took it from | V2 | Owner or class | Note |",
        "|---|---|---|---|---|",
    ]
    for row in record["rows"]:
        if row["v2"] != "generated":
            who = f"`{row['class']}`"
        elif "derivedFrom" in row:
            who = f"`{row['owner']}` (derived)"
        else:
            who = f"`{row['owner']}` (`{row['contextValue']}`)"
        lines.append(
            f"| `{row['chartValue']}` | `{row['v1']}` | `{row['v2']}` | {who} | {_note(row)} |"
        )
    return "\n".join(lines)


def _published_table(marker: str) -> str:
    text = DOC.read_text(encoding="utf-8").replace("\r\n", "\n")
    match = re.search(
        rf"<!-- {re.escape(marker)} -->\n\n(\|.*?)\n\n", text, flags=re.DOTALL
    )
    assert match, f"the page has no table after the {marker!r} marker"
    return match.group(1)


def published_classes_table(record: Mapping[str, Any]) -> str:
    rows = record["rows"]
    lines = ["| Class | Values | What it is |", "|---|---:|---|"]
    for name, meaning in record["handWrittenClasses"].items():
        count = sum(1 for row in rows if row.get("class") == name)
        lines.append(f"| `{name}` | {count} | {meaning} |")
    return "\n".join(lines)


def test_the_published_tables_are_the_record() -> None:
    record = load_record()
    assert _published_table("The table below is generated from the record.") == (
        published_rows_table(record)
    )
    assert _published_table("The classes below are generated from the record.") == (
        published_classes_table(record)
    )
