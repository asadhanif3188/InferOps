"""The preregistration of the reliability experiments, checked against its sources.

The freeze records of V2-E02A, V2-E02B, V2-E02C, V2-E04, and V2-E05 fix each
experiment before its first result-bearing run. ``tools.experiment_freeze``
checks that every record answers every freeze field and is not edited after it
is registered. It does not read an answer. This module reads the answers that a
reliability experiment depends on, and compares each one with the committed
record that it names or with another of the five records.

**The environment is the qualified one.** Each record names one qualification
by identifier, path, and content digest. The qualification must be committed
with that digest and be ``QUALIFIED``, and it must state the provider, the
environment digest, the identity revision, the Kubernetes server version, the
node count, and the freeze record that the experiment record states.

**The bounds are the committed ones.** Each record names one bound record by
path and content digest, and states its four bounds. The bound record must be
the latest one committed, with that digest, and state the same four names,
formulas, and values. Its environment must be the record's, its qualification
the record's qualification, and its release the release that the qualification
qualified. A criterion that names a bound states the value of that bound.

**The controlled comparison differs in the runtime topology alone.** V2-E02A
and V2-E02B must state the same environment, caller profile, fault, repetition
count, collection, window, measurements, outcome rules, exclusion reasons,
abort conditions, cleanup, evidence layout, and intended level. Their
topologies may differ only in the members that :data:`PERMITTED_TOPOLOGY`
names. The values of those members must be what the committed baseline
comparison record states for its two sides, and that record must be
``COMPARABLE`` and have the content digest that both records state. V2-E02C,
V2-E04, and V2-E05 state the topology of V2-E02B.

**Every executable that a procedure names is pinned.** Each file that a record
lists in ``definition.executables`` must be a pinned input of the record, and
the material scope must name the record's ``procedure/`` directory. So a driver
that a later change adds there is listed as added by
``python -m tools.experiment_freeze --changes``.

**What this does not do.** It reads files and writes none. It runs no
experiment, contacts no cluster, and reads no Git history. It checks only the
latest revision of each experiment. It does not judge whether a statement of a
record is right: it checks that the values it compares agree. It does not
compare the pins of a record with the files of the tree: the freeze tool's
``--changes`` command does that.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Final

from tools.experiment_freeze.core import (
    RECORD_NAME,
    content_digest,
    load_registry,
    record_paths,
)
from tools.reliability_analysis.core import _reasons_problem

__all__ = [
    "BASELINE",
    "EXPERIMENTS",
    "PERMITTED_TOPOLOGY",
    "RECONCILIATION_COMPONENTS",
    "REPO_ROOT",
    "RULES",
    "SHARED_DEFINITION",
    "SHARED_FIELDS",
    "TARGET",
    "Experiment",
    "Finding",
    "check_repository",
    "latest_records",
]

REPO_ROOT: Final = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class Experiment:
    """One reliability experiment: its identifier and the directory of its records."""

    experiment_id: str
    directory: str
    run_prefix: str


#: The five experiments, in the order the records list them.
EXPERIMENTS: Final[tuple[Experiment, ...]] = (
    Experiment("V2-E02A", "docs/proof/experiments/v2-e02a", "e02a"),
    Experiment("V2-E02B", "docs/proof/experiments/v2-e02b", "e02b"),
    Experiment("V2-E02C", "docs/proof/experiments/v2-e02c", "e02c"),
    Experiment("V2-E04", "docs/proof/experiments/v2-e04", "e04"),
    Experiment("V2-E05", "docs/proof/experiments/v2-e05", "e05"),
)

#: The two sides of the controlled comparison.
BASELINE: Final = "V2-E02A"
TARGET: Final = "V2-E02B"

#: Where the bound records are committed, and the name of one.
BOUNDS_DIR: Final = "docs/proof/experiments/v2-q4"
BOUNDS_NAME: Final = re.compile(r"^bounds-r([1-9][0-9]*)\.v1alpha1\.json$")

#: The schema name of a bound record, and the result of a usable qualification.
BOUNDS_SCHEMA: Final = "inferops.io/experiment-bounds/v1alpha1"
QUALIFIED: Final = "QUALIFIED"
COMPARABLE: Final = "COMPARABLE"

#: The freeze fields that every one of the five records answers alike.
COMMON_FIELDS: Final = (
    "environmentIdentity",
    "callerProfileRevision",
    "intendedEvidenceLevel",
)

#: The freeze fields that V2-E02A and V2-E02B answer alike.
SHARED_FIELDS: Final = (
    "environmentIdentity",
    "callerProfileRevision",
    "fault",
    "repetitionCount",
    "derivedNumericBounds",
    "evidencePaths",
    "abortConditions",
    "cleanupProcedure",
    "intendedEvidenceLevel",
)

#: The members of ``definition`` that V2-E02A and V2-E02B state alike.
SHARED_DEFINITION: Final = (
    "preparation",
    "callerRun",
    "collection",
    "stablePreFaultWindow",
    "faultProcedure",
    "observation",
    "postRecoveryWindow",
    "window",
    "analysisDeclaration",
    "measurements",
    "outcomeRules",
    "repetitionRule",
    "executables",
)

#: The members of a bound value that differ between experiments: what each
#: experiment uses a bound for, and the reconciliation bound of V2-E05.
BOUND_MEMBERS_NOT_SHARED: Final = frozenset({"use", "reconciliationBound"})

#: The members of a topology in which V2-E02A may differ from V2-E02B. Every other
#: member is equal.
PERMITTED_TOPOLOGY: Final = frozenset(
    {"runtimeReplicas", "release", "runtimeDisruptionBudget", "statement"}
)

#: The members of the release of a topology.
RELEASE_MEMBERS: Final = frozenset(
    {
        "releaseId",
        "workloadVersion",
        "contract",
        "desiredStateFiles",
        "filesFrom",
        "helmValuesSha256",
    }
)

#: The reconciliation bound of V2-E05: the documented reconciliation timeout, the
#: documented maximum jitter, and an allowance, in milliseconds.
RECONCILIATION_COMPONENTS: Final[Mapping[str, int]] = {
    "reconciliationTimeoutMs": 120_000,
    "reconciliationJitterMaximumMs": 60_000,
    "allowanceMs": 30_000,
}
RECONCILIATION_BOUND: Final = "reconciliation_bound_ms"
RECONCILIATION_EXPERIMENT: Final = "V2-E05"

#: The entry module of this tool, which each record pins.
ENTRY_MODULE: Final = "tools.experiment_preregistration.__main__"


@dataclass(frozen=True)
class Finding:
    """One way a record breaks a rule."""

    rule_id: str
    record: str
    location: str
    detail: str


#: Each rule, with its statement, in report order.
RULES: Final[Mapping[str, str]] = {
    "prereg-record-missing": (
        "Each of the five experiments has a committed freeze record in its directory, "
        "and the record names that experiment."
    ),
    "prereg-record-shape": (
        "A record answers each field that this check reads with one value, in the "
        "form that the check reads."
    ),
    "prereg-qualification-incompatible": (
        "The qualification that a record names is committed with the stated digest, "
        "is QUALIFIED, and states the provider, the environment digest, the identity "
        "revision, the server version, the node count, the freeze record, and the "
        "release that the record states."
    ),
    "prereg-bounds-stale": (
        "The bound record that a record names is the latest committed one, has the "
        "stated digest, and states the four bounds of the record with the same names, "
        "formulas, and values."
    ),
    "prereg-bounds-incompatible": (
        "The bound record states the environment, the qualification, and the release "
        "that the record states."
    ),
    "prereg-criterion-bound-unknown": (
        "A criterion that names a bound names a bound of the record and states its "
        "value in milliseconds."
    ),
    "prereg-reconciliation-bound-differs": (
        "The reconciliation bound of V2-E05 is the sum of its three registered "
        "components."
    ),
    "prereg-shared-differs": (
        "The five records state one environment, one caller profile, and one "
        "intended level, and V2-E02A and V2-E02B state every shared field and "
        "definition alike."
    ),
    "prereg-baseline-difference-unpermitted": (
        "The topology of V2-E02A differs from that of V2-E02B only in the permitted "
        "members, and their values are those of the committed COMPARABLE baseline "
        "comparison and of the pinned desired-state files."
    ),
    "prereg-target-topology-differs": (
        "V2-E02C, V2-E04, and V2-E05 state the topology of V2-E02B."
    ),
    "prereg-executable-unpinned": (
        "Each executable that a record lists is a pinned input, and the material "
        "scope names this check, the record's procedure directory, the "
        "qualification, and the bound record."
    ),
    "prereg-exclusion-reasons-unsupported": (
        "A record registers exclusion reasons for its own experiment, in the form "
        "that the aggregate reads."
    ),
}


# --------------------------------------------------------------------------
# Reading
# --------------------------------------------------------------------------


def _read(root: Path, path: str) -> tuple[bytes, Any] | None:
    """The bytes and the JSON value of a committed file, or None."""
    target = root / path
    if not target.is_file():
        return None
    data = target.read_bytes()
    try:
        return data, json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError):
        return data, None


def latest_records(root: Path = REPO_ROOT) -> dict[str, tuple[str, Any]]:
    """The latest revision of each experiment's record, by experiment identifier."""
    found: dict[str, tuple[int, str, Any]] = {}
    paths = set(record_paths(root))
    for experiment in EXPERIMENTS:
        for path in sorted(paths):
            if PurePosixPath(path).parent.as_posix() != experiment.directory:
                continue
            match = RECORD_NAME.match(PurePosixPath(path).name)
            if match is None:
                continue
            revision = int(match.group(1))
            if experiment.experiment_id in found and (
                found[experiment.experiment_id][0] > revision
            ):
                continue
            read = _read(root, path)
            found[experiment.experiment_id] = (
                revision,
                path,
                None if read is None else read[1],
            )
    return {key: (path, document) for key, (_, path, document) in found.items()}


def _value(document: Mapping[str, Any], field: str) -> Any:
    """The value of the one entry of a field, or None when it has no such entry."""
    entries = document.get("fields", {}).get(field)
    if not isinstance(entries, list) or len(entries) != 1:
        return None
    entry = entries[0]
    if not isinstance(entry, Mapping) or entry.get("status") != "value":
        return None
    return entry.get("value")


def _member(value: Any, name: str) -> Mapping[str, Any]:
    """The member ``name`` of ``value`` when both are objects, or an empty one."""
    if not isinstance(value, Mapping):
        return {}
    member = value.get(name)
    return member if isinstance(member, Mapping) else {}


def _canonical(value: Any) -> str:
    return json.dumps(value, sort_keys=True, ensure_ascii=False)


def _normalised(value: Any, experiment: Experiment) -> Any:
    """``value`` with the identifiers of its experiment replaced by fixed words.

    Two records of one comparison name their own directory, experiment, and run
    identifiers. The comparison reads every other character.
    """
    text = _canonical(value)
    for actual, word in (
        (experiment.directory, "<directory>"),
        (experiment.experiment_id, "<experiment>"),
        (f"{experiment.run_prefix}-", "<run>-"),
    ):
        text = text.replace(actual, word)
    return json.loads(text)


def _pins(document: Mapping[str, Any]) -> dict[str, str]:
    pinned = document.get("pinnedInputs")
    if not isinstance(pinned, list):
        return {}
    return {
        item["path"]: item["sha256"]
        for item in pinned
        if isinstance(item, Mapping)
        and isinstance(item.get("path"), str)
        and isinstance(item.get("sha256"), str)
    }


# --------------------------------------------------------------------------
# One record against its sources
# --------------------------------------------------------------------------


_ENVIRONMENT_MEMBERS: Final = frozenset(
    {
        "provider",
        "environmentSha256",
        "identityRevision",
        "kubernetesServerVersion",
        "nodeCount",
        "qualification",
        "qualificationFreezeRecord",
        "qualifiedRelease",
    }
)
_REFERENCE_MEMBERS: Final = frozenset({"path", "contentSha256"})


def _shape_problem(document: Any) -> str | None:
    """Why a record cannot be read by this check, or None."""
    if not isinstance(document, Mapping):
        return "the record is not one JSON object"
    environment = _value(document, "environmentIdentity")
    if (
        not isinstance(environment, Mapping)
        or not set(environment) >= _ENVIRONMENT_MEMBERS
    ):
        return "environmentIdentity states no environment in the form read here"
    qualification = environment["qualification"]
    if not isinstance(qualification, Mapping) or not {
        "qualificationId",
        "path",
        "contentSha256",
        "result",
    } <= set(qualification):
        return "the qualification is not named by identifier, path, digest, and result"
    bounds = _value(document, "derivedNumericBounds")
    if (
        not isinstance(bounds, Mapping)
        or not isinstance(bounds.get("boundRecord"), Mapping)
        or not set(bounds["boundRecord"]) >= _REFERENCE_MEMBERS
        or not isinstance(bounds.get("bounds"), list)
        or not all(
            isinstance(b, Mapping) and {"name", "formula", "valueMs"} <= set(b)
            for b in bounds["bounds"]
        )
    ):
        return "derivedNumericBounds names no bound record and no four bounds"
    topology = _value(document, "topology")
    if (
        not isinstance(topology, Mapping)
        or not isinstance(topology.get("release"), Mapping)
        or not set(topology["release"]) >= RELEASE_MEMBERS
    ):
        return "topology states no release in the form read here"
    definition = document.get("definition")
    if not isinstance(definition, Mapping) or not isinstance(
        definition.get("executables"), list
    ):
        return "definition lists no executables"
    criteria = _value(document, "acceptanceCriteria")
    if not isinstance(criteria, list):
        return "acceptanceCriteria is not a list of criteria"
    return None


def _qualification_findings(
    name: str, document: Mapping[str, Any], root: Path, target_release: str | None
) -> Iterator[Finding]:
    rule = "prereg-qualification-incompatible"
    environment = _value(document, "environmentIdentity")
    named = environment["qualification"]
    where = "fields.environmentIdentity"
    read = _read(root, str(named["path"]))
    if read is None or read[1] is None:
        yield Finding(rule, name, where, "the qualification is not committed")
        return
    data, record = read
    if content_digest(data) != named["contentSha256"]:
        yield Finding(rule, name, where, "the qualification has another digest")
    if not isinstance(record, Mapping):
        yield Finding(rule, name, where, "the qualification is not one JSON object")
        return
    stated = record.get("environment") if isinstance(record, Mapping) else None
    identities = record.get("identities")
    collection = record.get("collection")
    stated = stated if isinstance(stated, Mapping) else {}
    identities = identities if isinstance(identities, Mapping) else {}
    collection = collection if isinstance(collection, Mapping) else {}
    nodes = stated.get("nodes")
    comparisons = (
        ("result", record.get("result"), QUALIFIED),
        ("the stated result", named["result"], QUALIFIED),
        (
            "qualificationId",
            collection.get("qualificationId"),
            named["qualificationId"],
        ),
        (
            "environmentSha256",
            record.get("environmentSha256"),
            environment["environmentSha256"],
        ),
        ("provider", stated.get("provider"), environment["provider"]),
        (
            "identityRevision",
            stated.get("identityRevision"),
            environment["identityRevision"],
        ),
        (
            "kubernetesServerVersion",
            stated.get("kubernetesServerVersion"),
            environment["kubernetesServerVersion"],
        ),
        (
            "nodeCount",
            len(nodes) if isinstance(nodes, list) else None,
            environment["nodeCount"],
        ),
        (
            "the freeze record",
            identities.get("freezeRecord"),
            environment["qualificationFreezeRecord"],
        ),
        (
            "the qualified release",
            identities.get("releaseId"),
            environment["qualifiedRelease"],
        ),
    )
    for label, actual, expected in comparisons:
        if _canonical(actual) != _canonical(expected):
            yield Finding(rule, name, where, f"{label} differs from the qualification")
    if target_release is not None and environment["qualifiedRelease"] != target_release:
        yield Finding(
            rule, name, where, "the qualified release is not the target release"
        )
    freeze = environment["qualificationFreezeRecord"]
    try:
        registry = load_registry(root)
    except ValueError:
        registry = {}
    if not isinstance(freeze, Mapping) or registry.get(
        str(freeze.get("path"))
    ) != freeze.get("contentSha256"):
        yield Finding(
            rule, name, where, "the qualification freeze record is not registered"
        )


def _latest_bound_record(root: Path) -> str | None:
    base = root / BOUNDS_DIR
    if not base.is_dir():
        return None
    numbered = sorted(
        (int(match.group(1)), f"{BOUNDS_DIR}/{path.name}")
        for path in base.iterdir()
        if path.is_file() and (match := BOUNDS_NAME.match(path.name)) is not None
    )
    return numbered[-1][1] if numbered else None


def _bound_findings(
    name: str, document: Mapping[str, Any], root: Path, target_release: str | None
) -> Iterator[Finding]:
    value = _value(document, "derivedNumericBounds")
    reference = value["boundRecord"]
    where = "fields.derivedNumericBounds"
    stale = "prereg-bounds-stale"
    if reference["path"] != _latest_bound_record(root):
        yield Finding(
            stale, name, where, "the bound record is not the latest committed"
        )
    read = _read(root, str(reference["path"]))
    if read is None or not isinstance(read[1], Mapping):
        yield Finding(stale, name, where, "the bound record is not committed")
        return
    data, record = read
    if content_digest(data) != reference["contentSha256"]:
        yield Finding(stale, name, where, "the bound record has another digest")
    if record.get("schema") != BOUNDS_SCHEMA:
        yield Finding(stale, name, where, "the named file is not a bound record")
        return
    stated = [(b["name"], b["formula"], b["valueMs"]) for b in value["bounds"]]
    committed = [
        (b.get("name"), b.get("formula"), b.get("valueMs"))
        for b in record.get("bounds", [])
        if isinstance(b, Mapping)
    ]
    if _canonical(stated) != _canonical(committed):
        yield Finding(
            stale, name, where, "the bounds differ from those of the bound record"
        )
    incompatible = "prereg-bounds-incompatible"
    environment = _value(document, "environmentIdentity")
    bound_environment = record.get("environment")
    bound_environment = (
        bound_environment if isinstance(bound_environment, Mapping) else {}
    )
    qualification = environment["qualification"]
    for label, actual, expected in (
        ("provider", bound_environment.get("provider"), environment["provider"]),
        (
            "environmentSha256",
            bound_environment.get("environmentSha256"),
            environment["environmentSha256"],
        ),
        (
            "the qualification",
            bound_environment.get("qualification"),
            {
                "contentSha256": qualification["contentSha256"],
                "path": qualification["path"],
                "qualificationId": qualification["qualificationId"],
            },
        ),
        (
            "the release",
            bound_environment.get("releaseId"),
            environment["qualifiedRelease"],
        ),
        (
            "the source release",
            value.get("sourceRelease"),
            environment["qualifiedRelease"],
        ),
    ):
        if _canonical(actual) != _canonical(expected):
            yield Finding(incompatible, name, where, f"{label} differs")
    if (
        target_release is not None
        and bound_environment.get("releaseId") != target_release
    ):
        yield Finding(
            incompatible, name, where, "the bounds are not of the target release"
        )


def _bound_values(document: Mapping[str, Any]) -> dict[str, int]:
    value = _value(document, "derivedNumericBounds")
    values = {
        str(b["name"]): b["valueMs"]
        for b in value["bounds"]
        if isinstance(b.get("valueMs"), int)
    }
    reconciliation = value.get("reconciliationBound")
    if isinstance(reconciliation, Mapping) and isinstance(
        reconciliation.get("valueMs"), int
    ):
        values[str(reconciliation.get("name"))] = reconciliation["valueMs"]
    return values


def _criterion_findings(name: str, document: Mapping[str, Any]) -> Iterator[Finding]:
    values = _bound_values(document)
    for index, criterion in enumerate(_value(document, "acceptanceCriteria")):
        if not isinstance(criterion, Mapping) or "bound" not in criterion:
            continue
        where = f"fields.acceptanceCriteria[0].value[{index}]"
        bound = criterion["bound"]
        if bound not in values:
            yield Finding(
                "prereg-criterion-bound-unknown",
                name,
                where,
                "it names no bound of the record",
            )
        elif f"{values[bound]:,} ms" not in str(criterion.get("statement")):
            yield Finding(
                "prereg-criterion-bound-unknown",
                name,
                where,
                f"its statement does not state {values[bound]:,} ms",
            )


def _reconciliation_findings(
    name: str, experiment: str, document: Mapping[str, Any]
) -> Iterator[Finding]:
    reconciliation = _value(document, "derivedNumericBounds").get("reconciliationBound")
    where = "fields.derivedNumericBounds.reconciliationBound"
    rule = "prereg-reconciliation-bound-differs"
    if experiment != RECONCILIATION_EXPERIMENT:
        if reconciliation is not None:
            yield Finding(
                rule, name, where, "only V2-E05 states a reconciliation bound"
            )
        return
    if not isinstance(reconciliation, Mapping):
        yield Finding(rule, name, where, "V2-E05 states no reconciliation bound")
        return
    components = reconciliation.get("components")
    if (
        reconciliation.get("name") != RECONCILIATION_BOUND
        or _canonical(components) != _canonical(dict(RECONCILIATION_COMPONENTS))
        or reconciliation.get("valueMs") != sum(RECONCILIATION_COMPONENTS.values())
    ):
        yield Finding(
            rule, name, where, "the bound is not the sum of its registered components"
        )


def _executable_findings(
    name: str, experiment: Experiment, document: Mapping[str, Any]
) -> Iterator[Finding]:
    rule = "prereg-executable-unpinned"
    pins = _pins(document)
    for path in document["definition"]["executables"]:
        if path not in pins:
            yield Finding(rule, name, "definition.executables", f"{path} is not pinned")
    scope = document.get("materialScope")
    scope = scope if isinstance(scope, Mapping) else {}
    listed = scope.get("paths")
    paths: list[Any] = listed if isinstance(listed, list) else []
    modules = scope.get("entryModules")
    modules = modules if isinstance(modules, list) else []
    environment = _value(document, "environmentIdentity")
    bounds = _value(document, "derivedNumericBounds")
    for required in (
        f"{experiment.directory}/procedure/*",
        environment["qualification"]["path"],
        bounds["boundRecord"]["path"],
    ):
        if required not in paths:
            yield Finding(
                rule, name, "materialScope.paths", f"the scope does not name {required}"
            )
    if ENTRY_MODULE not in modules:
        yield Finding(
            rule,
            name,
            "materialScope.entryModules",
            "the scope does not name this check",
        )


def _exclusion_findings(
    name: str, experiment: str, document: Mapping[str, Any]
) -> Iterator[Finding]:
    rule = "prereg-exclusion-reasons-unsupported"
    policy = document.get("exclusionReasons")
    problem = _reasons_problem(policy)
    if problem is not None:
        yield Finding(rule, name, "exclusionReasons", problem)
    elif _member(document, "exclusionReasons").get("experimentId") != experiment:
        yield Finding(
            rule, name, "exclusionReasons", "the reasons name another experiment"
        )


# --------------------------------------------------------------------------
# The records against each other
# --------------------------------------------------------------------------


def _shared_findings(
    records: Mapping[str, tuple[str, Mapping[str, Any]]],
) -> Iterator[Finding]:
    rule = "prereg-shared-differs"
    reference = records.get(TARGET)
    if reference is None:
        return
    for path, document in records.values():
        for field in COMMON_FIELDS:
            if _canonical(_value(document, field)) != _canonical(
                _value(reference[1], field)
            ):
                yield Finding(
                    rule, path, f"fields.{field}", f"it differs from {TARGET}"
                )
        bounds = {
            key: value
            for key, value in _value(document, "derivedNumericBounds").items()
            if key not in BOUND_MEMBERS_NOT_SHARED
        }
        target_bounds = {
            key: value
            for key, value in _value(reference[1], "derivedNumericBounds").items()
            if key not in BOUND_MEMBERS_NOT_SHARED
        }
        if _canonical(bounds) != _canonical(target_bounds):
            yield Finding(
                rule, path, "fields.derivedNumericBounds", f"it differs from {TARGET}"
            )
    if BASELINE not in records:
        return
    by_id = {e.experiment_id: e for e in EXPERIMENTS}
    path, baseline = records[BASELINE]
    target = reference[1]
    pairs: list[tuple[str, Any, Any]] = []
    for field in SHARED_FIELDS:
        pairs.append(
            (f"fields.{field}", _value(baseline, field), _value(target, field))
        )
    for member in SHARED_DEFINITION:
        pairs.append(
            (
                f"definition.{member}",
                baseline["definition"].get(member),
                target["definition"].get(member),
            )
        )
    pairs.append(
        (
            "fields.acceptanceCriteria (validity)",
            _validity(baseline),
            _validity(target),
        )
    )
    pairs.append(
        (
            "exclusionReasons.reasons",
            (baseline.get("exclusionReasons") or {}).get("reasons"),
            (target.get("exclusionReasons") or {}).get("reasons"),
        )
    )
    for location, left, right in pairs:
        if location == "fields.derivedNumericBounds":
            left = {k: v for k, v in (left or {}).items() if k != "use"}
            right = {k: v for k, v in (right or {}).items() if k != "use"}
        if left is None or _canonical(_normalised(left, by_id[BASELINE])) != _canonical(
            _normalised(right, by_id[TARGET])
        ):
            yield Finding(rule, path, location, f"it differs from {TARGET}")


def _validity(document: Mapping[str, Any]) -> list[Any] | None:
    """The statements of the validity criteria of a record, in order.

    A validity criterion decides whether a run answers its question, and the two
    sides of the comparison hold a run to the same ones. A pass criterion of the
    target is a criterion of the reliability claim, and the baseline has none.
    """
    criteria = _value(document, "acceptanceCriteria")
    if not isinstance(criteria, list):
        return None
    statements = [
        c.get("statement")
        for c in criteria
        if isinstance(c, Mapping) and c.get("kind") == "validity"
    ]
    return statements or None


def _comparison_findings(
    records: Mapping[str, tuple[str, Mapping[str, Any]]], root: Path
) -> Iterator[Finding]:
    rule = "prereg-baseline-difference-unpermitted"
    if BASELINE not in records or TARGET not in records:
        return
    path, baseline = records[BASELINE]
    target = records[TARGET][1]
    sides = {
        "baseline": _value(baseline, "topology"),
        "target": _value(target, "topology"),
    }
    for member in sorted(set(sides["baseline"]) | set(sides["target"])):
        if member in PERMITTED_TOPOLOGY:
            continue
        if _canonical(sides["baseline"].get(member)) != _canonical(
            sides["target"].get(member)
        ):
            yield Finding(
                rule,
                path,
                f"fields.topology.{member}",
                "it is not a permitted difference",
            )
    for side in ("baseline", "target"):
        release = sides[side]["release"]
        if set(release) != RELEASE_MEMBERS:
            yield Finding(
                rule, path, f"fields.topology.release ({side})", "it has other members"
            )
    reference = sides["baseline"].get("comparison")
    if not isinstance(reference, Mapping) or not set(reference) >= _REFERENCE_MEMBERS:
        yield Finding(
            rule, path, "fields.topology.comparison", "it names no comparison"
        )
        return
    read = _read(root, str(reference["path"]))
    if read is None or not isinstance(read[1], Mapping):
        yield Finding(rule, path, "fields.topology.comparison", "it is not committed")
        return
    data, comparison = read
    if content_digest(data) != reference["contentSha256"]:
        yield Finding(
            rule,
            path,
            "fields.topology.comparison",
            "the comparison has another digest",
        )
    if comparison.get("result") != COMPARABLE:
        yield Finding(
            rule, path, "fields.topology.comparison", "the comparison is not COMPARABLE"
        )
    if _canonical(reference.get("permittedDifferences")) != _canonical(
        comparison.get("permittedDifferences")
    ):
        yield Finding(
            rule,
            path,
            "fields.topology.comparison",
            "the permitted differences are not those of the comparison",
        )
    for side, document in (("baseline", baseline), ("target", target)):
        topology = sides[side]
        release = topology["release"]
        stated = _member(_member(comparison, "releases"), side)
        metadata = _member(stated, "metadata")
        values = _member(_member(stated, "output"), "helmValues")
        declared = _member(_member(comparison, "declarations"), side)
        replicas = _member(_member(comparison, "effectiveTopology"), side)
        pins = _pins(document)
        contract = _member(release, "contract")
        files = _member(release, "desiredStateFiles")
        directory = release["filesFrom"]
        checks = (
            ("releaseId", release["releaseId"], metadata.get("releaseId")),
            (
                "workloadVersion",
                release["workloadVersion"],
                metadata.get("workloadVersion"),
            ),
            ("helmValuesSha256", release["helmValuesSha256"], values.get("sha256")),
            ("contract", contract.get("path"), declared.get("contract")),
            (
                "contract digest",
                contract.get("contentSha256"),
                pins.get(str(contract.get("path"))),
            ),
            ("filesFrom", directory, declared.get("directory")),
            (
                "runtimeReplicas",
                topology.get("runtimeReplicas"),
                replicas.get("runtimeReplicas"),
            ),
            ("apiReplicas", topology.get("apiReplicas"), replicas.get("apiReplicas")),
            (
                "the values file",
                files.get("values.generated.yaml"),
                release["helmValuesSha256"],
            ),
        )
        for label, actual, expected in checks:
            if actual is None or _canonical(actual) != _canonical(expected):
                yield Finding(
                    rule,
                    path,
                    f"fields.topology.release ({side})",
                    f"{label} is not the one of the comparison",
                )
        for file_name, digest in files.items():
            if pins.get(f"{directory}/{file_name}") != digest:
                yield Finding(
                    rule,
                    path,
                    f"fields.topology.release ({side})",
                    f"{file_name} is not pinned with the stated digest",
                )


def _target_findings(
    records: Mapping[str, tuple[str, Mapping[str, Any]]],
) -> Iterator[Finding]:
    if TARGET not in records:
        return
    target = _value(records[TARGET][1], "topology")
    for experiment, (path, document) in records.items():
        if experiment in (BASELINE, TARGET):
            continue
        if _canonical(_value(document, "topology")) != _canonical(target):
            yield Finding(
                "prereg-target-topology-differs",
                path,
                "fields.topology",
                f"it differs from {TARGET}",
            )


# --------------------------------------------------------------------------
# The whole check
# --------------------------------------------------------------------------


def check_repository(root: Path = REPO_ROOT) -> list[Finding]:
    """Every way the latest records of the five experiments break a rule."""
    findings: list[Finding] = []
    found = latest_records(root)
    usable: dict[str, tuple[str, Mapping[str, Any]]] = {}
    for experiment in EXPERIMENTS:
        if experiment.experiment_id not in found:
            findings.append(
                Finding(
                    "prereg-record-missing",
                    experiment.directory,
                    "$",
                    "no freeze record is committed",
                )
            )
            continue
        path, document = found[experiment.experiment_id]
        if (
            not isinstance(document, Mapping)
            or document.get("metadata", {}).get("experiment")
            != experiment.experiment_id
        ):
            findings.append(
                Finding(
                    "prereg-record-missing",
                    path,
                    "metadata.experiment",
                    f"the record does not name {experiment.experiment_id}",
                )
            )
            continue
        problem = _shape_problem(document)
        if problem is not None:
            findings.append(Finding("prereg-record-shape", path, "$", problem))
            continue
        usable[experiment.experiment_id] = (path, document)
    target_release = None
    if TARGET in usable:
        target_release = _value(usable[TARGET][1], "topology")["release"]["releaseId"]
    by_id = {e.experiment_id: e for e in EXPERIMENTS}
    for experiment_id, (path, document) in usable.items():
        findings.extend(_qualification_findings(path, document, root, target_release))
        findings.extend(_bound_findings(path, document, root, target_release))
        findings.extend(_criterion_findings(path, document))
        findings.extend(_reconciliation_findings(path, experiment_id, document))
        findings.extend(_executable_findings(path, by_id[experiment_id], document))
        findings.extend(_exclusion_findings(path, experiment_id, document))
    findings.extend(_shared_findings(usable))
    findings.extend(_comparison_findings(usable, root))
    findings.extend(_target_findings(usable))
    order = {rule: index for index, rule in enumerate(RULES)}
    return sorted(findings, key=lambda f: (order[f.rule_id], f.record, f.location))


def rule_statements() -> Sequence[tuple[str, str]]:
    """Each rule and its statement, in report order."""
    return tuple(RULES.items())
