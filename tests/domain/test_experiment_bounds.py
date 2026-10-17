"""Q4, the derived experiment bounds: the formulas, the refusals, and the binding.

Every source record here is written by this suite under pytest's temporary
directory, beside stand-in freeze records. The suite holds the four bounds to
their fixed formulas, each refusal to its rule, and a bound record to the digest
of each source record and of its freeze record. It also holds the formulas to
the Q3 freeze record, which fixed them before any Q3 characterization ran, and
each committed bound record to what its source records give.
"""

from __future__ import annotations

import copy
import json
import re
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from tools import experiment_bounds as q4
from tools.experiment_bounds import __main__ as cli

pytestmark = pytest.mark.unit

ROOT = Path(__file__).resolve().parents[2]
STARTUP = "docs/proof/experiments/v2-q2/runs/q2-1/record.v1alpha1.json"
CALLER = "docs/proof/experiments/v2-q3/runs/q3-1/record.v1alpha1.json"
Q2_FREEZE = q4.STARTUP_FREEZE_RECORDS[0]
Q3_FREEZE = q4.CALLER_FREEZE_RECORDS[0]
Q2_FREEZE_TEXT = '{"stand-in": "Q2 revision 2"}\n'
Q3_FREEZE_TEXT = '{"stand-in": "Q3 revision 1"}\n'
SHARED = {
    "provider": "docker-desktop",
    "environmentSha256": "sha256:" + "2" * 64,
    "releaseId": "5" * 64,
    "qualification": {
        "qualificationId": "q1-1",
        "path": "docs/proof/experiments/v2-q1/runs/q1-1/record.v1alpha1.json",
        "contentSha256": "4" * 64,
    },
}


def _write(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = value if isinstance(value, str) else json.dumps(value, indent=2) + "\n"
    path.write_text(text, encoding="utf-8", newline="\n")


def _source(
    schema: str, identifier: str, symbol: str, value: int, freeze: str, text: str
) -> dict[str, Any]:
    bound: dict[str, Any] = {"symbol": symbol, "valueMs": value}
    if symbol == "S":
        bound["rule"] = "the maximum startToReadyMs of every observation"
    else:
        bound.update(rule="p99", percentileMeaningful=True, successes=180)
    return {
        "schema": schema,
        "result": "CHARACTERIZED",
        "collection": {"characterizationId": identifier},
        "identities": {
            **copy.deepcopy(SHARED),
            "executingCommit": "1" * 40,
            "freezeRecord": {
                "path": freeze,
                "contentSha256": q4.lf_digest(text.encode()),
            },
        },
        "bound": bound,
        "findings": [
            {"ruleId": "a", "state": "held"},
            {"ruleId": "b", "state": "held"},
        ],
    }


@pytest.fixture
def root(tmp_path: Path) -> Path:
    checkout = tmp_path / "checkout"
    _write(checkout / Q2_FREEZE, Q2_FREEZE_TEXT)
    _write(checkout / Q3_FREEZE, Q3_FREEZE_TEXT)
    _write(
        checkout / STARTUP,
        _source(q4.STARTUP_SCHEMA, "q2-1", "S", 11_000, Q2_FREEZE, Q2_FREEZE_TEXT),
    )
    _write(
        checkout / CALLER,
        _source(q4.CALLER_SCHEMA, "q3-1", "G", 1_900, Q3_FREEZE, Q3_FREEZE_TEXT),
    )
    return checkout


def _values(record: dict[str, Any]) -> dict[str, int]:
    return {item["name"]: item["valueMs"] for item in record["bounds"]}


def test_the_four_bounds_follow_the_fixed_formulas(root: Path) -> None:
    record = q4.build_record(STARTUP, CALLER, root)
    assert _values(record) == {
        "runtime_start_bound_ms": 11_000,
        "caller_gap_reference_ms": 1_900,
        "reversal_recovery_bound_ms": 52_000,
        "caller_total_unavailability_bound_ms": 5_000,
    }
    assert [item["formula"] for item in record["bounds"]] == [
        "S",
        "G",
        "(2 * S) + 30000",
        "max(2 * G, 5000)",
    ]


@pytest.mark.parametrize(
    ("s_ms", "g_ms", "recovery", "unavailability"),
    [
        (11_000, 1_900, 52_000, 5_000),
        (11_000, 2_500, 52_000, 5_000),
        (11_000, 2_501, 52_000, 5_002),
        (61_000, 9_000, 152_000, 18_000),
        (1, 0, 30_002, 5_000),
    ],
)
def test_the_formulas(s_ms: int, g_ms: int, recovery: int, unavailability: int) -> None:
    assert q4.stated_bounds(s_ms, g_ms) == {
        "runtime_start_bound_ms": s_ms,
        "caller_gap_reference_ms": g_ms,
        "reversal_recovery_bound_ms": recovery,
        "caller_total_unavailability_bound_ms": unavailability,
    }


def test_a_record_binds_each_bound_to_its_sources(root: Path) -> None:
    record = q4.build_record(STARTUP, CALLER, root)
    assert record["inputs"]["S"]["record"] == {
        "path": STARTUP,
        "contentSha256": q4.lf_digest((root / STARTUP).read_bytes()),
    }
    assert record["inputs"]["G"]["freezeRecord"] == {
        "path": Q3_FREEZE,
        "contentSha256": q4.lf_digest(Q3_FREEZE_TEXT.encode()),
    }
    assert record["inputs"]["G"]["rule"] == "p99"
    assert record["inputs"]["G"]["percentileMeaningful"] is True
    assert record["environment"] == SHARED
    assert record["boundary"] == q4.BOUNDARY
    assert "not service levels" in q4.BOUNDARY
    for sentence in q4.DOES_NOT_ESTABLISH:
        assert sentence.startswith("A record does not establish "), sentence


def _change(
    path: str, edit: Callable[[dict[str, Any]], None]
) -> Callable[[Path], None]:
    def apply(root: Path) -> None:
        document = json.loads((root / path).read_text(encoding="utf-8"))
        edit(document)
        _write(root / path, document)

    return apply


REFUSALS: list[tuple[str, str, Callable[[Path], None]]] = [
    ("absent", "bounds-source-unreadable", lambda r: (r / CALLER).unlink()),
    (
        "not JSON",
        "bounds-source-unreadable",
        lambda r: _write(r / STARTUP, "not json\n"),
    ),
    (
        "another characterization named",
        "bounds-source-misplaced",
        _change(STARTUP, lambda d: d["collection"].update(characterizationId="q2-2")),
    ),
    (
        "inconclusive",
        "bounds-source-not-characterized",
        _change(CALLER, lambda d: d.update(result="INCONCLUSIVE")),
    ),
    (
        "a rule not held",
        "bounds-source-not-characterized",
        _change(CALLER, lambda d: d["findings"][1].update(state="not-observed")),
    ),
    (
        "another schema",
        "bounds-source-not-characterized",
        _change(STARTUP, lambda d: d.update(schema=q4.CALLER_SCHEMA)),
    ),
    (
        "no value",
        "bounds-source-not-characterized",
        _change(CALLER, lambda d: d["bound"].update(valueMs=None)),
    ),
    (
        "S of zero",
        "bounds-source-not-characterized",
        _change(STARTUP, lambda d: d["bound"].update(valueMs=0)),
    ),
    (
        "a value as text",
        "bounds-source-not-characterized",
        _change(STARTUP, lambda d: d["bound"].update(valueMs="11000")),
    ),
    (
        "Q2 revision 1",
        "bounds-source-unfrozen",
        _change(
            STARTUP,
            lambda d: d["identities"]["freezeRecord"].update(
                path="docs/proof/experiments/v2-q2/freeze-r1.v1alpha1.json"
            ),
        ),
    ),
    (
        "a freeze record edited",
        "bounds-source-unfrozen",
        lambda r: _write(r / Q3_FREEZE, '{"stand-in": "edited"}\n'),
    ),
    (
        "another environment",
        "bounds-environment-differs",
        _change(
            CALLER,
            lambda d: d["identities"].update(environmentSha256="sha256:" + "9" * 64),
        ),
    ),
    (
        "another release",
        "bounds-environment-differs",
        _change(STARTUP, lambda d: d["identities"].update(releaseId="8" * 64)),
    ),
]


@pytest.mark.parametrize(
    ("label", "rule", "apply"),
    [pytest.param(*case, id=case[0]) for case in REFUSALS],
)
def test_each_refusal_names_its_rule_and_states_no_bound(
    root: Path, label: str, rule: str, apply: Callable[[Path], None]
) -> None:
    apply(root)
    with pytest.raises(q4.BoundsRefused) as refused:
        q4.build_record(STARTUP, CALLER, root)
    assert refused.value.rule == rule, label
    assert rule in q4.RULES


def test_a_record_of_another_kind_in_the_place_of_a_source_is_refused(
    root: Path,
) -> None:
    with pytest.raises(q4.BoundsRefused) as refused:
        q4.build_record(CALLER, STARTUP, root)
    assert refused.value.rule == "bounds-source-misplaced"


def test_check_builds_each_committed_bound_record_again(root: Path) -> None:
    path = root / "docs/proof/experiments/v2-q4/bounds-r1.v1alpha1.json"
    _write(path, q4.record_text(q4.build_record(STARTUP, CALLER, root)))
    assert q4.check_committed(root) == []
    _change(CALLER, lambda d: d["bound"].update(valueMs=2_600))(root)
    assert q4.check_committed(root) == [
        "docs/proof/experiments/v2-q4/bounds-r1.v1alpha1.json: is not what its "
        "source records give"
    ]
    _change(CALLER, lambda d: d.update(result="REFUSED"))(root)
    (finding,) = q4.check_committed(root)
    assert "refused: bounds-source-not-characterized" in finding


def test_the_command_prints_a_record_refuses_and_checks(
    root: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    original = q4.core.build_record
    monkeypatch.setattr(cli, "build_record", lambda a, b: original(a, b, root))
    assert cli.main([STARTUP, CALLER]) == 0
    assert _values(json.loads(capsys.readouterr().out))[
        "reversal_recovery_bound_ms"
    ] == (52_000)
    _change(CALLER, lambda d: d.update(result="INCONCLUSIVE"))(root)
    assert cli.main([STARTUP, CALLER]) == q4.REFUSED_EXIT
    assert "bounds-source-not-characterized" in capsys.readouterr().err
    with pytest.raises(SystemExit) as usage:
        cli.main([STARTUP])
    assert usage.value.code == 2


def test_the_command_has_no_option_that_changes_a_formula() -> None:
    text = (ROOT / "tools/experiment_bounds/__main__.py").read_text(encoding="utf-8")
    assert sorted(set(re.findall(r'"(--[a-z-]+)"', text))) == ["--check"]


def test_the_command_runs_as_a_module() -> None:
    result = subprocess.run(
        [sys.executable, "-m", "tools.experiment_bounds", "--check"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_the_q3_freeze_record_fixed_the_formulas_that_the_tool_computes() -> None:
    record = json.loads((ROOT / Q3_FREEZE).read_text(encoding="utf-8"))
    (bounds,) = record["fields"]["derivedNumericBounds"]
    q4_part = bounds["value"]["Q4"]
    assert q4_part["formulas"] == dict(q4.FORMULAS)
    assert list(q4_part["formulas"]) == list(q4.BOUND_NAMES)
    pinned = {item["path"] for item in record["pinnedInputs"]}
    assert "tools/experiment_bounds/core.py" in pinned


def test_each_committed_bound_record_is_what_its_sources_give() -> None:
    assert q4.check_committed() == []


def test_the_committed_bound_record_r1_binds_q2_2_and_q3_2_of_the_q1_2_lineage() -> (
    None
):
    """V2-S6-004-PR2 built bounds-r1 with the tool from q2-2 and q3-2. Each value
    is recomputed here from the formulas written out, not from the tool, and each
    source is bound by the digest of its committed bytes. Both sources name q1-2
    and its stable environment identity, so the pair is of one lineage."""
    (path,) = q4.committed_records()
    assert path == ROOT / "docs/proof/experiments/v2-q4/bounds-r1.v1alpha1.json"
    record = json.loads(path.read_text(encoding="utf-8"))
    startup_path = "docs/proof/experiments/v2-q2/runs/q2-2/record.v1alpha1.json"
    caller_path = "docs/proof/experiments/v2-q3/runs/q3-2/record.v1alpha1.json"
    startup = json.loads((ROOT / startup_path).read_text(encoding="utf-8"))
    caller = json.loads((ROOT / caller_path).read_text(encoding="utf-8"))
    s_ms, g_ms = startup["bound"]["valueMs"], caller["bound"]["valueMs"]
    assert (s_ms, g_ms) == (11_000, 10_113)
    assert {item["name"]: item["valueMs"] for item in record["bounds"]} == {
        "runtime_start_bound_ms": s_ms,
        "caller_gap_reference_ms": g_ms,
        "reversal_recovery_bound_ms": 2 * s_ms + 30_000,
        "caller_total_unavailability_bound_ms": max(2 * g_ms, 5_000),
    }
    for symbol, source_path, freeze_path in (
        ("S", startup_path, "docs/proof/experiments/v2-q2/freeze-r3.v1alpha1.json"),
        ("G", caller_path, "docs/proof/experiments/v2-q3/freeze-r2.v1alpha1.json"),
    ):
        stated = record["inputs"][symbol]
        assert stated["record"] == {
            "path": source_path,
            "contentSha256": q4.lf_digest((ROOT / source_path).read_bytes()),
        }
        assert stated["freezeRecord"] == {
            "path": freeze_path,
            "contentSha256": q4.lf_digest((ROOT / freeze_path).read_bytes()),
        }
    qualification = record["environment"]["qualification"]
    assert qualification["qualificationId"] == "q1-2"
    assert qualification["path"] == (
        "docs/proof/experiments/v2-q1/runs/q1-2/record.v1alpha1.json"
    )
    assert record["environment"]["environmentSha256"] == (
        "sha256:6a219b3ff959a0020d982d967abeed6696aa0f0d1b594bdf3ad86b9aeda8cd5c"
    )
    for source in (startup, caller):
        assert source["identities"]["qualification"] == qualification
        assert (
            source["identities"]["environmentSha256"]
            == (record["environment"]["environmentSha256"])
        )


def test_the_tool_refuses_q2_1_with_q3_2_because_the_lineages_differ() -> None:
    """q2-1 is bound to q1-1 and its exact identity. It cannot be combined with a
    Q3 characterization of q1-2, so S and G of one bound record share a lineage."""
    with pytest.raises(q4.BoundsRefused) as refused:
        q4.build_record(
            "docs/proof/experiments/v2-q2/runs/q2-1/record.v1alpha1.json",
            "docs/proof/experiments/v2-q3/runs/q3-2/record.v1alpha1.json",
        )
    assert refused.value.rule == "bounds-environment-differs"


def test_the_tool_imports_no_network_or_process_module() -> None:
    for name in ("core.py", "__main__.py", "__init__.py"):
        text = (ROOT / "tools/experiment_bounds" / name).read_text(encoding="utf-8")
        for module in ("subprocess", "socket", "urllib", "http", "requests"):
            assert not re.search(rf"^\s*(import|from)\s+{module}\b", text, re.MULTILINE)


# --------------------------------------------------------------------------
# Two lineages: q1-1 with the exact identity, q1-2 with the stable identity
# --------------------------------------------------------------------------

Q2_R3 = "docs/proof/experiments/v2-q2/freeze-r3.v1alpha1.json"
Q3_R2 = "docs/proof/experiments/v2-q3/freeze-r2.v1alpha1.json"
NEXT_STARTUP = "docs/proof/experiments/v2-q2/runs/q2-2/record.v1alpha1.json"
NEXT_CALLER = "docs/proof/experiments/v2-q3/runs/q3-2/record.v1alpha1.json"
#: What a characterization of q1-2 states: the stable identity has another
#: digest than any exact identity, and the qualification is another record.
NEXT_SHARED = {
    "provider": "docker-desktop",
    "environmentSha256": "sha256:" + "3" * 64,
    "releaseId": "5" * 64,
    "qualification": {
        "qualificationId": "q1-2",
        "path": "docs/proof/experiments/v2-q1/runs/q1-2/record.v1alpha1.json",
        "contentSha256": "6" * 64,
    },
}


def _next_lineage(root: Path) -> None:
    """Write a Q2 source of revision 3 and a Q3 source of revision 2, of q1-2."""
    for freeze_path, text in ((Q2_R3, "Q2 revision 3"), (Q3_R2, "Q3 revision 2")):
        _write(root / freeze_path, f'{{"stand-in": "{text}"}}\n')
    for path, schema, identifier, symbol, value, freeze_path, text in (
        (NEXT_STARTUP, q4.STARTUP_SCHEMA, "q2-2", "S", 12_000, Q2_R3, "Q2 revision 3"),
        (NEXT_CALLER, q4.CALLER_SCHEMA, "q3-2", "G", 1_800, Q3_R2, "Q3 revision 2"),
    ):
        source = _source(
            schema,
            identifier,
            symbol,
            value,
            freeze_path,
            f'{{"stand-in": "{text}"}}\n',
        )
        source["identities"].update(copy.deepcopy(NEXT_SHARED))
        _write(root / path, source)


def test_the_revisions_of_each_lineage_may_govern_a_source() -> None:
    assert q4.STARTUP_FREEZE_RECORDS == (
        "docs/proof/experiments/v2-q2/freeze-r2.v1alpha1.json",
        Q2_R3,
    )
    assert q4.CALLER_FREEZE_RECORDS == (
        "docs/proof/experiments/v2-q3/freeze-r1.v1alpha1.json",
        Q3_R2,
    )


def test_two_sources_of_the_q1_2_lineage_give_a_record(root: Path) -> None:
    _next_lineage(root)
    record = q4.build_record(NEXT_STARTUP, NEXT_CALLER, root)
    assert _values(record)["runtime_start_bound_ms"] == 12_000
    assert _values(record)["caller_gap_reference_ms"] == 1_800


@pytest.mark.parametrize(
    ("startup", "caller"),
    [
        pytest.param(STARTUP, NEXT_CALLER, id="q2-of-q1-1-with-q3-of-q1-2"),
        pytest.param(NEXT_STARTUP, CALLER, id="q2-of-q1-2-with-q3-of-q1-1"),
    ],
)
def test_a_source_of_one_lineage_is_never_combined_with_one_of_the_other(
    root: Path, startup: str, caller: str
) -> None:
    """q2-1 is bound to q1-1 and its exact identity. A Q3 characterization of
    q1-2 states another environment digest and another qualification record, so
    the comparison refuses the pair, whatever the two bounds are."""
    _next_lineage(root)
    with pytest.raises(q4.BoundsRefused) as refused:
        q4.build_record(startup, caller, root)
    assert refused.value.rule == "bounds-environment-differs"


def test_a_shared_digest_with_another_qualification_record_is_still_refused(
    root: Path,
) -> None:
    """The qualification record is compared by its identifier, path, and content
    digest, apart from the environment digest."""
    _next_lineage(root)
    _change(
        NEXT_CALLER,
        lambda d: d["identities"]["qualification"].update(contentSha256="7" * 64),
    )(root)
    with pytest.raises(q4.BoundsRefused) as refused:
        q4.build_record(NEXT_STARTUP, NEXT_CALLER, root)
    assert refused.value.rule == "bounds-environment-differs"
