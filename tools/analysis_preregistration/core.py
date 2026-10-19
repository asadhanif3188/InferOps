"""The preregistration of the two analysis experiments, checked against its sources.

V2-E03 (signal truthfulness) and V2-E06 (reliability resource and cost overhead)
run no fault and start no caller of their own. Each reads the evidence of the
runs of other experiments. So each freeze record names those experiments, its
sources, and fixes before any source run exists what it reads and how it
computes. ``tools.experiment_freeze`` checks that each record answers every
freeze field and is not edited after it is registered. This module reads the
answers, and each of the two records has its own rules.

**The sources are bound by digest.** Each record names each source experiment
by the path, the revision, and the content digest of its latest registered
freeze record. The digest must be that of the file and that of its registry
pin, and the revision must be the latest one committed. A later source revision
is therefore a finding of the latest analysis record until a later analysis
revision binds it. The record also states the digest of the clock policy that
every bound source states, and the environment, the caller profile, the
topology, the fault, the repetition count, and the bound record of each source,
as that source states them.

**V2-E03 states its population, its ten signals, and its rules.** The initial
population is the counted runs of V2-E02A, V2-E02B, and V2-E02C. The extension
adds the counted runs of V2-E04. V2-E05 is excluded with a reason. The ten
signals are those of :data:`E03_SIGNALS`, each read from a stream that every
bound source collects, at the interval that the source collects it, through a
reader that a tool registers. The API error rate is the operational signal
candidate. It is the comparator of the ranking and has no ranking preference.
The record states how the caller record identifies a failure that the API error
counter does not count, the computations, and the ranking rule.

**V2-E06 states its views, its metrics, and its labels.** View A compares the
requested resources of V2-E02A and V2-E02B. View B compares one API and one
runtime replica with two of each, by arithmetic. No view or metric that reads
only configuration is labeled measured. The utilization statistic, its stream,
its queries, and its source runs are fixed, and so are the cost basis and the
evidence target.

**It imports two private functions.** ``_contradictions`` and ``_strings_in`` of
``tools.experiment_preregistration`` read the text of a record for the phrases
that the clock rules of rule set 2 refuse, so both records are read for the same
contradictions as the records of their sources. A change to them moves a pin of
each record here. This module does not change that package, so it moves no pin
of a record that the package checks.

**What this does not do.** It reads files and writes none. It runs no analysis,
computes no figure, contacts no cluster, and reads no Git history. It reads text
only for the phrases that it names, and a paraphrase that no phrase names is not
refused. It does not check that a definition is right, that a source procedure
collects what its text says beyond the stream names and intervals that the text
states, or that the analysis code that a later change adds follows the record.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any, Final

from tools.experiment_freeze.core import (
    RECORD_NAME,
    check_record,
    content_digest,
    load_registry,
    record_paths,
)
from tools.experiment_preregistration.core import _contradictions, _strings_in
from tools.experiment_telemetry import QUERIES, QUERY_SET, RESOURCES, TELEMETRY
from tools.reliability_analysis import SIGNAL_SOURCES
from tools.reliability_runner.incluster import OUTCOME_HTTP_ERROR, OUTCOMES

__all__ = [
    "CONFIGURATION_READS",
    "E03",
    "E03_EXCLUDED",
    "E03_EXTENSION",
    "E03_INITIAL",
    "E03_SIGNALS",
    "E06",
    "E06_METRICS",
    "E06_SOURCES",
    "EXPERIMENTS",
    "LABELS",
    "REPO_ROOT",
    "RULES",
    "RUN_READS",
    "AnalysisExperiment",
    "Finding",
    "check_records",
    "check_repository",
    "policy_digest",
]

REPO_ROOT: Final = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class AnalysisExperiment:
    """One analysis experiment: its identifier, its directory, and its one part."""

    experiment_id: str
    directory: str
    part: str
    prefix: str


E03: Final = AnalysisExperiment("V2-E03", "docs/proof/experiments/v2-e03", "E03", "e03")
E06: Final = AnalysisExperiment("V2-E06", "docs/proof/experiments/v2-e06", "E06", "e06")

#: The two analysis experiments, in the order the check reports them.
EXPERIMENTS: Final[tuple[AnalysisExperiment, ...]] = (E03, E06)

#: The directory of the freeze records of each source experiment.
SOURCE_DIRECTORIES: Final[Mapping[str, str]] = {
    "V2-E02A": "docs/proof/experiments/v2-e02a",
    "V2-E02B": "docs/proof/experiments/v2-e02b",
    "V2-E02C": "docs/proof/experiments/v2-e02c",
    "V2-E04": "docs/proof/experiments/v2-e04",
    "V2-E05": "docs/proof/experiments/v2-e05",
}

#: The population of V2-E03. The initial analysis reads the counted runs of the
#: three pod-loss experiments, the extension adds those of V2-E04, and V2-E05 is
#: excluded from the ranking.
E03_INITIAL: Final = ("V2-E02A", "V2-E02B", "V2-E02C")
E03_EXTENSION: Final = ("V2-E04",)
E03_EXCLUDED: Final = ("V2-E05",)

#: The role of each source of each record.
E03_SOURCES: Final[Mapping[str, str]] = {
    **dict.fromkeys(E03_INITIAL, "initial"),
    **dict.fromkeys(E03_EXTENSION, "extension"),
}
E06_SOURCES: Final[Mapping[str, str]] = {"V2-E02A": "baseline", "V2-E02B": "target"}

#: The ten signals of V2-E03, by number: the identifier and the stream of each.
#: Signal 1 is the caller record, the reference. The other nine are candidates.
E03_SIGNALS: Final[Mapping[int, tuple[str, str]]] = {
    1: ("caller-outcome", "caller"),
    2: ("api-error-rate", "telemetry"),
    3: ("api-ready-endpoints", "endpoints"),
    4: ("runtime-ready-endpoints", "endpoints"),
    5: ("api-pod-readiness", "pods"),
    6: ("runtime-pod-readiness", "pods"),
    7: ("deployment-ready-replicas", "deployments"),
    8: ("scrape-up", "telemetry"),
    9: ("application-sync-state", "argo"),
    10: ("application-health-state", "argo"),
}
REFERENCE_SIGNAL: Final = 1
CANDIDATE_SIGNAL: Final = 2
REFERENCE: Final = "reference"
CANDIDATE: Final = "candidate"
COMPARATOR: Final = "comparator"
NO_PREFERENCE: Final = "none"

#: The streams of a source, by the member of ``definition.collection`` that
#: states them. The caller record is collected by ``definition.callerRun``.
CALLER_STREAM: Final = "caller"
COLLECTIONS: Final = ("timeline", "telemetry")

#: The phrases that the statements of the operational signal candidate hold.
#: The rule reads these phrases and no other prose.
CANDIDATE_PHRASES: Final[Mapping[str, tuple[str, ...]]] = {
    "comparatorCondition": ("compared with itself", "no ranking preference"),
    "statement": ("not a predetermined ranking winner",),
}

#: The members that would name a winner of the ranking.
WINNER_MEMBERS: Final = frozenset({"winner", "predeterminedWinner"})

#: The phrases of the rules that a later revision states, read in any letter case.
CODE_PHRASES: Final = ("before any", "later revision of this record")
LATER_REVISION_PHRASES: Final = ("later revision of this record", "--changes")
CLOUD_PHRASES: Final = ("later revision of this record",)

#: The members that a local cost basis never states.
PRICE_MEMBERS: Final = frozenset({"price", "charge", "currency", "amount"})

#: How each failed caller outcome states a canonical error code. The runner keeps
#: ``errorCode`` for an HTTP error answer alone.
WHEN_STATED: Final = "when-stated"
NEVER: Final = "never"
FAILED_OUTCOMES: Final = tuple(o for o in OUTCOMES if o != "success")

#: The two figures that the uncounted-failure rule reports for each run.
FAILURE_FIGURES: Final = (
    "failures-without-canonical-code",
    "failures-without-counter-change",
)
EVERY_FAILURE: Final = "every failed completion"

#: The computations that V2-E03 states, and the phrases that two of them hold.
COMPUTATIONS: Final = (
    "searchStart",
    "firstCallerImpact",
    "firstChange",
    "detectionLag",
    "falseHealthy",
    "falseUnavailable",
    "notObserved",
    "figures",
    "changed",
    "describes",
)
NEVER_HEALTHY: Final = "never healthy"
MARGIN_PHRASE: Final = (
    "the clock bound of the run plus the coarser resolution of the two sources"
)
NO_LEAD_OR_LAG: Final = "no lead or lag"
RANKING_MEMBERS: Final = (
    "earliest",
    "mostCallerTruthful",
    "tradeOff",
    "exploratory",
    "notObserved",
)
FIGURES: Final = ("inner", "outer")

#: The views of V2-E06 and the replica counts of each side.
VIEW_A: Final = "view-a"
VIEW_B: Final = "view-b"
SINGLE_PATH: Final = "single-path-equivalent"

#: The labels of a view or a metric, and what each reads.
MEASURED: Final = "measured"
STATIC: Final = "static-allocation"
UNAVAILABLE: Final = "unavailable"
LABELS: Final = (MEASURED, STATIC, UNAVAILABLE)
CONFIGURATION_READS: Final = frozenset(
    {"requests", "limits", "claim-request", "rollout-strategy"}
)
RUN_READS: Final = frozenset({"resources-stream"})

#: The six metrics of V2-E06.
E06_METRICS: Final = (
    "api-requests",
    "runtime-requests",
    "total-requests",
    "utilization",
    "model-cache-storage",
    "rollout-headroom",
)
UTILIZATION_QUERY: Final = "api-cpu-seconds"
UTILIZATION: Final = "utilization"
LOCAL: Final = "local"
EVIDENCE_TARGET: Final[Mapping[str, str]] = {"allocation": "C0", "runDerived": "C2"}

#: The entry module of this check, which each record pins.
ENTRY_MODULE: Final = "tools.analysis_preregistration.__main__"

_INTERVAL: Final = re.compile(r"--interval (\d+):")
#: The list of streams after ": the streams", up to ", from", a full stop, or the end.
_STREAMS: Final = re.compile(r": the streams (.*?)(?:, from |\.|$)")
_STREAM_NAME: Final = re.compile(r"[a-z]+")
_STREAM_SPLIT: Final = re.compile(r",\s*(?:and\s+)?|\s+and\s+")
_QUERY_SET: Final = re.compile(r"registered query set ([a-z0-9-]+)")


@dataclass(frozen=True)
class Finding:
    """One way a record breaks a rule."""

    rule_id: str
    record: str
    location: str
    detail: str


def _rules(prefix: str, name: str) -> dict[str, str]:
    return {
        f"{prefix}-record-missing": (
            f"{name} has a committed freeze record in its directory, and the record "
            "names that experiment."
        ),
        f"{prefix}-record-shape": (
            "The record states its version, its kind, its experiment, an integer "
            "revision, one part, and a definition object."
        ),
        f"{prefix}-fields-unanswered": (
            "Each freeze field has one entry for the one part, answered with a value "
            "or as not applicable with a reason, and never pending."
        ),
        f"{prefix}-sources-stale": (
            "The record binds each source experiment once, in its role, to the path, "
            "the revision, and the content digest of a registered freeze record of "
            "that experiment. The digest is that of the file and of its registry "
            "pin, and the latest record binds the latest revision."
        ),
        f"{prefix}-source-fields-differ": (
            "The environment, the caller profile, the topology, the fault, the "
            "repetition count, the bound record, and the clock policy digest that "
            "the record states for its sources are those that each bound source "
            "states."
        ),
        f"{prefix}-clock-contradiction": (
            "No text of the record states that the clock difference is not "
            "measured, orders instants by a time without the margin of the source "
            "clock policy, names synchronization or a guarantee in a sentence with "
            "no negation, or states that every run is INCONCLUSIVE, in the phrases "
            "that tools.experiment_preregistration names."
        ),
        f"{prefix}-analysis-code": (
            "The analysis-code rule of the record names its procedure directory and "
            "holds the phrases that this check names, and no other prose of it is "
            "read. The material scope names this check, the procedure directory, and "
            "every revision file of each source, and each executable that the record "
            "lists is pinned. Whether the procedure directory exists is not read."
        ),
    }


#: Each rule, with its statement, in report order. V2-E03 and V2-E06 each have
#: their own rules.
RULES: Final[Mapping[str, str]] = {
    **_rules("e03", "V2-E03"),
    "e03-population": (
        "The initial population is the counted runs of V2-E02A, V2-E02B, and "
        "V2-E02C. The extension is the counted runs of V2-E04. V2-E05 is excluded "
        "from the ranking with a reason. No experiment is in two of them, and the "
        "later-source-revision rule holds the phrases that this check names. No "
        "other prose of it is read."
    ),
    "e03-signal-set": (
        "The preregistered signals are the ten of the record, numbered 1 to 10, "
        "each with its identifier. Signal 1 is the caller reference and is not a "
        "candidate. A further signal is labeled exploratory, is a candidate with a "
        "number above 10, and is not ranked."
    ),
    "e03-signal-streams": (
        "Each signal reads the stream of its number. Every bound source collects "
        "that stream, and the signal states the interval at which the source "
        "collects it. A timeline signal names a source that tools.reliability_"
        "analysis registers for its stream, a telemetry signal names queries of "
        "the registered query set that the sources name, and each signal states "
        "its problem, healthy, and not-observed definitions."
    ),
    "e03-candidate": (
        "The operational signal candidate is signal 2, the API error rate. Its "
        "role is the comparator, it has no ranking preference, it is not declared "
        "a winner, and its statements hold the phrases that this check names. No "
        "member of the definition named winner or predeterminedWinner is other "
        "than false, and none named rankingPreference is other than none."
    ),
    "e03-ranking": (
        "The ranking rule states the earliest change, the most caller-truthful "
        "signal, the trade-off, the exploratory label, and the not-observed time. "
        "Its comparator is the candidate, and it is judged on the inner and the "
        "outer figure."
    ),
    "e03-caller-failures": (
        "The record states, for each failed caller outcome, how the caller record "
        "identifies it and whether it states a canonical error code, a "
        "false-healthy rule that holds the phrase that this check names, and the "
        "two figures that it reports for each run."
    ),
    "e03-computations": (
        "The record states each computation. Its not-observed computation holds "
        "the phrase never healthy, and its ordering rule holds the margin of the "
        "source clock policy and the phrase no lead or lag. No other prose of them "
        "is read."
    ),
    **_rules("e06", "V2-E06"),
    "e06-views": (
        "View A compares V2-E02A and V2-E02B with the replica counts that they "
        "state. View B compares one API and one runtime replica, reconstructed by "
        "arithmetic, with the two and two of V2-E02B."
    ),
    "e06-labels": (
        "Each view and each metric has one label of the three and reads only "
        "registered reads. A view or a metric that reads only configuration is not "
        "labeled measured, a measured one reads a run stream, and a static "
        "allocation reads configuration alone. The utilization "
        "metric is labeled measured or unavailable, and no other view or metric is "
        "labeled measured."
    ),
    "e06-metrics": (
        "The record states the six metrics, each with what it reads and a "
        "statement, and the rollout headroom definition."
    ),
    "e06-utilization": (
        "The utilization statistic, its stream, its query set, its queries, its "
        "source runs, its aggregate, and its no-series rule are stated."
    ),
    "e06-cost-basis": (
        "The cost basis is local, no cloud provider is used, its cloud rule holds "
        "the phrase that this check names, and no member of the cost basis is named "
        "price, charge, currency, or amount."
    ),
    "e06-evidence-target": (
        "The evidence target is C0 for the allocation arithmetic and C2 for the "
        "figures read from runs, and the confidence of a cost is stated apart."
    ),
}


# --------------------------------------------------------------------------
# Reading
# --------------------------------------------------------------------------


def _member(value: Any, name: str) -> Mapping[str, Any]:
    """The member ``name`` of ``value`` when both are objects, or an empty one."""
    if not isinstance(value, Mapping):
        return {}
    member = value.get(name)
    return member if isinstance(member, Mapping) else {}


def _text(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _contained(path: object) -> bool:
    return (
        isinstance(path, str)
        and bool(path)
        and not PurePosixPath(path).is_absolute()
        and ".." not in PurePosixPath(path).parts
        and "\\" not in path
        and ":" not in path
    )


def _read(root: Path, path: object) -> tuple[bytes, Any] | None:
    """The bytes and the JSON value of a committed file, or None."""
    if not _contained(path):
        return None
    target = root / str(path)
    if not target.is_file():
        return None
    data = target.read_bytes()
    try:
        return data, json.loads(data.decode("utf-8"))
    except (UnicodeDecodeError, ValueError, RecursionError):
        return data, None


def policy_digest(policy: Any) -> str:
    """The SHA-256 of a clock policy in canonical JSON: sorted keys, no spaces."""
    text = json.dumps(policy, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _revisions(root: Path, directory: str) -> dict[int, str]:
    found: dict[int, str] = {}
    for path in record_paths(root):
        if PurePosixPath(path).parent.as_posix() != directory:
            continue
        match = RECORD_NAME.match(PurePosixPath(path).name)
        if match is not None:
            found[int(match.group(1))] = path
    return found


def _value(document: Mapping[str, Any], field: str) -> Any:
    entries = _member(document, "fields").get(field)
    if not isinstance(entries, list) or len(entries) != 1:
        return None
    entry = entries[0]
    if not isinstance(entry, Mapping) or entry.get("status") != "value":
        return None
    return entry.get("value")


def _strings(value: Any) -> list[str] | None:
    """``value`` when it is a list of strings, and None otherwise.

    A list that holds a list or an object is None, so no set is built from an
    unhashable member.
    """
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        return None
    return value


def _named_members(
    value: Any, names: frozenset[str], location: str
) -> Iterator[tuple[str, Any]]:
    """The location and the value of each member of ``value`` with one of ``names``."""
    if isinstance(value, Mapping):
        for key, item in value.items():
            where = f"{location}.{key}"
            if key in names:
                yield where, item
            yield from _named_members(item, names, where)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            yield from _named_members(item, names, f"{location}[{index}]")


def _phrases(text: Any, phrases: Sequence[str]) -> list[str]:
    """The phrases of ``phrases`` that ``text`` does not hold, in any letter case."""
    if not isinstance(text, str):
        return list(phrases)
    return [phrase for phrase in phrases if phrase.lower() not in text.lower()]


# --------------------------------------------------------------------------
# The rules both records share
# --------------------------------------------------------------------------


def _shape_problem(document: Any, experiment: AnalysisExperiment) -> str | None:
    if not isinstance(document, Mapping):
        return "the record is a JSON object"
    metadata = document.get("metadata")
    parts = document.get("parts")
    if (
        document.get("apiVersion") != "inferops.io/v1alpha1"
        or document.get("kind") != "ExperimentFreeze"
        or not isinstance(metadata, Mapping)
        or metadata.get("experiment") != experiment.experiment_id
        or not isinstance(metadata.get("revision"), int)
        or isinstance(metadata.get("revision"), bool)
    ):
        return "apiVersion, kind, metadata.experiment, and an integer revision"
    if (
        not isinstance(parts, list)
        or len(parts) != 1
        or _member({"p": parts[0]}, "p").get("id") != experiment.part
    ):
        return f"one part, {experiment.part}"
    if not isinstance(document.get("definition"), Mapping):
        return "a definition object"
    return None


def _field_findings(
    name: str, document: Mapping[str, Any], experiment: AnalysisExperiment
) -> Iterator[Finding]:
    rule = f"{experiment.prefix}-fields-unanswered"
    try:
        checked = check_record(document, name)
    except (TypeError, AttributeError, ValueError) as error:
        # tools.experiment_freeze raises on some malformed members. It is not
        # edited here, because earlier records pin it.
        yield Finding(
            rule,
            name,
            "fields",
            f"the freeze check cannot read it: {type(error).__name__}",
        )
        checked = []
    for finding in checked:
        if finding.rule_id.startswith(
            ("freeze-field", "freeze-criteria", "freeze-evi")
        ):
            yield Finding(rule, name, finding.location, finding.detail)
    fields = _member(document, "fields")
    for key, entries in fields.items():
        if not isinstance(entries, list) or len(entries) != 1:
            yield Finding(rule, name, f"fields.{key}", "one entry for the one part")
            continue
        if _member({"e": entries[0]}, "e").get("status") == "pending":
            yield Finding(rule, name, f"fields.{key}", "a field is never pending")


def _binding_findings(
    root: Path,
    name: str,
    document: Mapping[str, Any],
    experiment: AnalysisExperiment,
    roles: Mapping[str, str],
    registry: Mapping[str, str],
    *,
    latest: bool,
) -> Iterator[tuple[Finding | None, str, Mapping[str, Any]]]:
    """Each finding of the source bindings, and each source that it read.

    Yields ``(finding, "", {})`` for a finding and ``(None, experiment, source)``
    for each bound source that holds every clause.
    """
    rule = f"{experiment.prefix}-sources-stale"
    sources = _member(document, "definition").get("sources")
    if not isinstance(sources, list):
        yield Finding(rule, name, "definition.sources", "a list of bindings"), "", {}
        return
    seen: list[str] = []
    for index, binding in enumerate(sources):
        where = f"definition.sources[{index}]"
        if not isinstance(binding, Mapping):
            yield Finding(rule, name, where, "a binding is an object"), "", {}
            continue
        source = binding.get("experiment")
        if not isinstance(source, str) or source not in roles:
            yield (
                Finding(rule, name, f"{where}.experiment", f"one of {sorted(roles)}"),
                "",
                {},
            )
            continue
        seen.append(source)
        if binding.get("role") != roles[source]:
            yield (
                Finding(rule, name, f"{where}.role", f"{source} is {roles[source]}"),
                "",
                {},
            )
        revision = binding.get("revision")
        path = binding.get("path")
        directory = SOURCE_DIRECTORIES[source]
        revisions = _revisions(root, directory)
        if (
            not isinstance(revision, int)
            or isinstance(revision, bool)
            or path != f"{directory}/freeze-r{revision}.v1alpha1.json"
            or revisions.get(revision) != path
        ):
            yield (
                Finding(
                    rule,
                    name,
                    f"{where}.path",
                    "a committed revision file of the source",
                ),
                "",
                {},
            )
            continue
        if latest and revision != max(revisions):
            yield (
                Finding(
                    rule,
                    name,
                    f"{where}.revision",
                    f"revision {revision} is superseded by revision {max(revisions)}",
                ),
                "",
                {},
            )
        read = _read(root, path)
        digest = binding.get("contentSha256")
        if read is None or read[1] is None or not isinstance(read[1], Mapping):
            yield (
                Finding(rule, name, f"{where}.path", "a readable freeze record"),
                "",
                {},
            )
            continue
        if digest != content_digest(read[0]) or registry.get(str(path)) != digest:
            yield (
                Finding(
                    rule,
                    name,
                    f"{where}.contentSha256",
                    "the digest of the file and of its registry pin",
                ),
                "",
                {},
            )
            continue
        if _member(read[1], "metadata").get("experiment") != source:
            yield Finding(rule, name, f"{where}.path", f"a record of {source}"), "", {}
            continue
        yield None, source, read[1]
    for source in sorted(set(roles) - set(seen)):
        yield (
            Finding(rule, name, "definition.sources", f"{source} is not bound"),
            "",
            {},
        )
    for source in sorted({s for s in seen if seen.count(s) > 1}):
        yield (
            Finding(rule, name, "definition.sources", f"{source} is bound twice"),
            "",
            {},
        )


def _source_field_findings(
    name: str,
    document: Mapping[str, Any],
    experiment: AnalysisExperiment,
    sources: Mapping[str, Mapping[str, Any]],
) -> Iterator[Finding]:
    """The values that the record states for its sources are those of the sources."""
    rule = f"{experiment.prefix}-source-fields-differ"
    environment = _value(document, "environmentIdentity")
    profile = _value(document, "callerProfileRevision")
    topology = _member(_value(document, "topology"), "sources")
    fault = _value(document, "fault")
    repetition = _member(_value(document, "repetitionCount"), "sources")
    bounds = _value(document, "derivedNumericBounds")
    policy = _member(document, "definition").get("sourceClockPolicy")
    if _member({"f": fault}, "f").get("injected") != "none":
        yield Finding(
            rule, name, "fields.fault", "injected is none: no fault of its own"
        )
    for source, record in sorted(sources.items()):
        identity = _value(record, "environmentIdentity")
        stated_environment = {
            "provider": _member({"e": environment}, "e").get("provider"),
            "environmentSha256": _member({"e": environment}, "e").get(
                "environmentSha256"
            ),
            "qualification": _member(environment, "qualification"),
        }
        source_qualification = _member(identity, "qualification")
        expected_environment = {
            "provider": _member({"e": identity}, "e").get("provider"),
            "environmentSha256": _member({"e": identity}, "e").get("environmentSha256"),
            "qualification": {
                key: source_qualification.get(key)
                for key in ("qualificationId", "path", "contentSha256")
            },
        }
        if stated_environment != expected_environment:
            yield Finding(rule, name, "fields.environmentIdentity", f"that of {source}")
        source_profile = _value(record, "callerProfileRevision")
        keys = ("profile", "revision", "path", "contentSha256")
        if {k: _member({"p": profile}, "p").get(k) for k in keys} != {
            k: _member({"p": source_profile}, "p").get(k) for k in keys
        }:
            yield Finding(
                rule, name, "fields.callerProfileRevision", f"that of {source}"
            )
        source_topology = _value(record, "topology")
        expected_topology = {
            "apiReplicas": _member({"t": source_topology}, "t").get("apiReplicas"),
            "runtimeReplicas": _member({"t": source_topology}, "t").get(
                "runtimeReplicas"
            ),
            "releaseId": _member(source_topology, "release").get("releaseId"),
        }
        if dict(_member(topology, source)) != expected_topology:
            yield Finding(
                rule, name, f"fields.topology.sources.{source}", f"that of {source}"
            )
        source_fault = _member({"f": _value(record, "fault")}, "f").get("type")
        if _member(fault, "sources").get(source) != source_fault:
            yield Finding(
                rule, name, f"fields.fault.sources.{source}", f"that of {source}"
            )
        if repetition.get(source) != _value(record, "repetitionCount"):
            yield Finding(
                rule,
                name,
                f"fields.repetitionCount.sources.{source}",
                f"that of {source}",
            )
        if dict(_member(bounds, "boundRecord")) != dict(
            _member(_value(record, "derivedNumericBounds"), "boundRecord")
        ):
            yield Finding(
                rule,
                name,
                "fields.derivedNumericBounds.boundRecord",
                f"that of {source}",
            )
        source_policy = _member(record, "definition").get("clockPolicy")
        if not isinstance(source_policy, Mapping) or _member({"p": policy}, "p").get(
            "sha256"
        ) != policy_digest(source_policy):
            yield Finding(
                rule,
                name,
                "definition.sourceClockPolicy.sha256",
                f"the digest of the clock policy of {source}",
            )


def _contradiction_findings(
    name: str, document: Mapping[str, Any], experiment: AnalysisExperiment
) -> Iterator[Finding]:
    rule = f"{experiment.prefix}-clock-contradiction"
    scanned = {k: v for k, v in document.items() if k != "pinnedInputs"}
    for location, text in _strings_in(scanned, ""):
        for detail in _contradictions(text):
            yield Finding(rule, name, location, detail)


def _code_findings(
    name: str,
    document: Mapping[str, Any],
    experiment: AnalysisExperiment,
    roles: Mapping[str, str],
) -> Iterator[Finding]:
    rule = f"{experiment.prefix}-analysis-code"
    definition = _member(document, "definition")
    code = _member(definition, "analysisCode")
    procedure = f"{experiment.directory}/procedure"
    if code.get("procedureDirectory") != procedure or _phrases(
        code.get("rule"), CODE_PHRASES
    ):
        yield Finding(
            rule,
            name,
            "definition.analysisCode",
            f"names {procedure} and states that the code is pinned before any figure",
        )
    scope = _member(document, "materialScope")
    entries = scope.get("entryModules")
    paths = scope.get("paths")
    if not isinstance(entries, list) or ENTRY_MODULE not in entries:
        yield Finding(rule, name, "materialScope.entryModules", f"names {ENTRY_MODULE}")
    required = [f"{procedure}/*"] + [
        f"{SOURCE_DIRECTORIES[s]}/freeze-r*.v1alpha1.json" for s in roles
    ]
    for pattern in required:
        if not isinstance(paths, list) or pattern not in paths:
            yield Finding(rule, name, "materialScope.paths", f"names {pattern}")
    pinned = document.get("pinnedInputs")
    pins = {
        item["path"]
        for item in (pinned if isinstance(pinned, list) else [])
        if isinstance(item, Mapping) and isinstance(item.get("path"), str)
    }
    executables = definition.get("executables")
    if not isinstance(executables, list) or not executables:
        yield Finding(rule, name, "definition.executables", "at least one executable")
        return
    for index, path in enumerate(executables):
        if not isinstance(path, str) or path not in pins:
            yield Finding(
                rule, name, f"definition.executables[{index}]", "a pinned input"
            )


# --------------------------------------------------------------------------
# V2-E03
# --------------------------------------------------------------------------


def _collected(record: Mapping[str, Any]) -> dict[str, tuple[str, int | None]]:
    """Each stream that a source collects, with its collection and interval in ms."""
    definition = _member(record, "definition")
    collection = _member(definition, "collection")
    found: dict[str, tuple[str, int | None]] = {}
    if _text(_member(definition, "callerRun").get("collect")):
        found[CALLER_STREAM] = ("caller", None)
    for member in COLLECTIONS:
        text = collection.get(member)
        if not isinstance(text, str):
            continue
        interval = _INTERVAL.search(text)
        streams = _STREAMS.search(text)
        if interval is None or streams is None:
            continue
        for stream in _STREAM_SPLIT.split(streams.group(1).strip()):
            if _STREAM_NAME.fullmatch(stream.strip()):
                found[stream.strip()] = (member, int(interval.group(1)) * 1000)
    return found


def _query_sets(record: Mapping[str, Any]) -> set[str]:
    text = _member(_member(record, "definition"), "collection").get("telemetry")
    return set(_QUERY_SET.findall(text)) if isinstance(text, str) else set()


def _population_findings(name: str, document: Mapping[str, Any]) -> Iterator[Finding]:
    rule = "e03-population"
    population = _member(_member(document, "definition"), "population")
    initial = _member(population, "initial").get("experiments")
    extension = _member(population, "extension").get("experiments")
    excluded = population.get("excluded")
    if initial != list(E03_INITIAL):
        yield Finding(
            rule, name, "definition.population.initial", f"exactly {list(E03_INITIAL)}"
        )
    if extension != list(E03_EXTENSION):
        yield Finding(
            rule,
            name,
            "definition.population.extension",
            f"exactly {list(E03_EXTENSION)}",
        )
    excluded_ids = [
        item.get("experiment") if isinstance(item, Mapping) else None
        for item in (excluded if isinstance(excluded, list) else [None])
    ]
    if excluded_ids != list(E03_EXCLUDED) or not all(
        isinstance(item, Mapping) and _text(item.get("reason"))
        for item in (excluded if isinstance(excluded, list) else [None])
    ):
        yield Finding(
            rule,
            name,
            "definition.population.excluded",
            f"exactly {list(E03_EXCLUDED)}, each with a reason",
        )
    named = [
        *(initial if isinstance(initial, list) else []),
        *(extension if isinstance(extension, list) else []),
        *excluded_ids,
    ]
    for experiment in sorted(
        {e for e in named if isinstance(e, str) and named.count(e) > 1}
    ):
        yield Finding(
            rule, name, "definition.population", f"{experiment} is in two of them"
        )
    for member in ("initial", "extension"):
        if not _text(_member(population, member).get("runs")):
            yield Finding(
                rule, name, f"definition.population.{member}.runs", "which runs"
            )
    if _phrases(population.get("laterSourceRevision"), LATER_REVISION_PHRASES):
        yield Finding(
            rule,
            name,
            "definition.population.laterSourceRevision",
            "a later source revision needs a later revision of this record",
        )


def _signals(document: Mapping[str, Any]) -> list[Any]:
    signals = _member(document, "definition").get("signals")
    return signals if isinstance(signals, list) else []


def _signal_set_findings(name: str, document: Mapping[str, Any]) -> Iterator[Finding]:
    rule = "e03-signal-set"
    signals = _member(document, "definition").get("signals")
    if not isinstance(signals, list):
        yield Finding(rule, name, "definition.signals", "a list of signals")
        return
    preregistered: list[tuple[Any, Any]] = []
    for index, signal in enumerate(signals):
        where = f"definition.signals[{index}]"
        if not isinstance(signal, Mapping):
            yield Finding(rule, name, where, "a signal is an object")
            continue
        if signal.get("exploratory") is True:
            if signal.get("ranked") is not False:
                yield Finding(
                    rule, name, f"{where}.ranked", "an exploratory signal is not ranked"
                )
            number = signal.get("number")
            if (
                not isinstance(number, int)
                or isinstance(number, bool)
                or number <= len(E03_SIGNALS)
            ):
                yield Finding(
                    rule, name, f"{where}.number", "an exploratory signal is above 10"
                )
            if signal.get("role") != CANDIDATE:
                yield Finding(
                    rule, name, f"{where}.role", "an exploratory signal is a candidate"
                )
            continue
        if "exploratory" in signal and signal.get("exploratory") is not False:
            yield Finding(rule, name, f"{where}.exploratory", "true or false")
        preregistered.append((signal.get("number"), signal.get("id")))
        number = signal.get("number")
        expected_role = REFERENCE if number == REFERENCE_SIGNAL else CANDIDATE
        if signal.get("role") != expected_role:
            yield Finding(
                rule, name, f"{where}.role", f"signal {number} is a {expected_role}"
            )
    expected = [(number, ident) for number, (ident, _) in E03_SIGNALS.items()]
    if preregistered != expected:
        missing = [
            n for n, _ in expected if (n, E03_SIGNALS[n][0]) not in preregistered
        ]
        extra = [item for item in preregistered if item not in expected]
        yield Finding(
            rule,
            name,
            "definition.signals",
            f"the ten signals in order; missing {missing}, unlabeled or other {extra}",
        )


def _signal_stream_findings(
    name: str, document: Mapping[str, Any], sources: Mapping[str, Mapping[str, Any]]
) -> Iterator[Finding]:
    rule = "e03-signal-streams"
    collected = {source: _collected(record) for source, record in sources.items()}
    query_sets = {source: _query_sets(record) for source, record in sources.items()}
    telemetry_queries = {q.name for q in QUERIES if q.stream == TELEMETRY}
    for index, signal in enumerate(_signals(document)):
        where = f"definition.signals[{index}]"
        if not isinstance(signal, Mapping):
            continue
        number = signal.get("number")
        stream = signal.get("stream")
        expected = E03_SIGNALS.get(number) if isinstance(number, int) else None
        if (
            signal.get("exploratory") is not True
            and expected is not None
            and stream != expected[1]
        ):
            yield Finding(rule, name, f"{where}.stream", expected[1])
        sampling = _member(signal, "sampling")
        for source, streams in sorted(collected.items()):
            if not isinstance(stream, str) or stream not in streams:
                yield Finding(
                    rule,
                    name,
                    f"{where}.stream",
                    f"{source} does not collect {stream!r}",
                )
                continue
            interval = streams[stream][1]
            if interval is None:
                if sampling.get("kind") != "per-request":
                    yield Finding(rule, name, f"{where}.sampling", "per-request")
            elif (
                sampling.get("kind") != "interval"
                or sampling.get("intervalMs") != interval
            ):
                yield Finding(
                    rule,
                    name,
                    f"{where}.sampling",
                    f"an interval of {interval} ms, as {source} collects {stream}",
                )
        derivation = _member(signal, "derivation")
        if stream == TELEMETRY:
            queries = derivation.get("queries")
            query_set = derivation.get("querySet")
            if query_set != QUERY_SET or any(
                query_set not in sets for sets in query_sets.values()
            ):
                yield Finding(
                    rule,
                    name,
                    f"{where}.derivation.querySet",
                    f"{QUERY_SET}, which each source names",
                )
            strings = _strings(queries)
            if not strings or not set(strings) <= telemetry_queries:
                yield Finding(
                    rule,
                    name,
                    f"{where}.derivation.queries",
                    "registered queries of the telemetry stream",
                )
        elif stream != CALLER_STREAM:
            source_name = derivation.get("analysisSource")
            if (
                not isinstance(source_name, str)
                or source_name not in SIGNAL_SOURCES
                or SIGNAL_SOURCES[source_name][0] != stream
            ):
                yield Finding(
                    rule,
                    name,
                    f"{where}.derivation.analysisSource",
                    f"a source that tools.reliability_analysis registers for {stream}",
                )
        for member in ("problem", "healthy", "notObserved"):
            if not _text(signal.get(member)):
                yield Finding(rule, name, f"{where}.{member}", "a definition")


def _candidate_findings(name: str, document: Mapping[str, Any]) -> Iterator[Finding]:
    rule = "e03-candidate"
    definition = _member(document, "definition")
    candidate = definition.get("operationalCandidate")
    where = "definition.operationalCandidate"
    if not isinstance(candidate, Mapping):
        yield Finding(rule, name, where, "the operational signal candidate is named")
        return
    expected_id = E03_SIGNALS[CANDIDATE_SIGNAL][0]
    if (
        candidate.get("signal") != CANDIDATE_SIGNAL
        or candidate.get("id") != expected_id
    ):
        yield Finding(
            rule, name, f"{where}.signal", f"signal {CANDIDATE_SIGNAL}, {expected_id}"
        )
    if candidate.get("role") != COMPARATOR:
        yield Finding(rule, name, f"{where}.role", COMPARATOR)
    if candidate.get("rankingPreference") != NO_PREFERENCE:
        yield Finding(rule, name, f"{where}.rankingPreference", NO_PREFERENCE)
    if candidate.get("predeterminedWinner") is not False:
        yield Finding(rule, name, f"{where}.predeterminedWinner", "false")
    for member, phrases in CANDIDATE_PHRASES.items():
        missing = _phrases(candidate.get(member), phrases)
        if missing:
            yield Finding(rule, name, f"{where}.{member}", f"holds {missing}")
    for location, value in _named_members(definition, WINNER_MEMBERS, "definition"):
        if value is not False:
            yield Finding(rule, name, location, "false: no signal is a winner")
    for location, value in _named_members(
        definition, frozenset({"rankingPreference"}), "definition"
    ):
        if value != NO_PREFERENCE and location != f"{where}.rankingPreference":
            yield Finding(
                rule, name, location, f"{NO_PREFERENCE}: no ranking preference"
            )


def _ranking_findings(name: str, document: Mapping[str, Any]) -> Iterator[Finding]:
    rule = "e03-ranking"
    ranking = _member(_member(document, "definition"), "ranking")
    for member in RANKING_MEMBERS:
        if not _text(ranking.get(member)):
            yield Finding(rule, name, f"definition.ranking.{member}", "a statement")
    if ranking.get("comparator") != E03_SIGNALS[CANDIDATE_SIGNAL][0]:
        yield Finding(
            rule,
            name,
            "definition.ranking.comparator",
            E03_SIGNALS[CANDIDATE_SIGNAL][0],
        )
    if ranking.get("figures") != list(FIGURES):
        yield Finding(rule, name, "definition.ranking.figures", f"{list(FIGURES)}")


def _caller_failure_findings(
    name: str, document: Mapping[str, Any]
) -> Iterator[Finding]:
    rule = "e03-caller-failures"
    failures = _member(document, "definition").get("callerFailures")
    where = "definition.callerFailures"
    if not isinstance(failures, Mapping):
        yield Finding(rule, name, where, "the uncounted-failure rule is stated")
        return
    outcomes = failures.get("outcomes")
    stated: list[Any] = []
    for index, item in enumerate(outcomes if isinstance(outcomes, list) else []):
        if not isinstance(item, Mapping):
            yield Finding(rule, name, f"{where}.outcomes[{index}]", "an object")
            continue
        outcome = item.get("outcome")
        stated.append(outcome)
        code = WHEN_STATED if outcome == OUTCOME_HTTP_ERROR else NEVER
        if item.get("canonicalErrorCode") != code:
            yield Finding(
                rule, name, f"{where}.outcomes[{index}].canonicalErrorCode", code
            )
        if not _text(item.get("identifiedBy")):
            yield Finding(
                rule, name, f"{where}.outcomes[{index}].identifiedBy", "a rule"
            )
    if stated != list(FAILED_OUTCOMES):
        yield Finding(
            rule, name, f"{where}.outcomes", f"exactly {list(FAILED_OUTCOMES)}"
        )
    if _phrases(failures.get("falseHealthy"), (EVERY_FAILURE,)):
        yield Finding(rule, name, f"{where}.falseHealthy", f"holds {EVERY_FAILURE!r}")
    report = failures.get("report")
    figures = [
        item.get("figure") if isinstance(item, Mapping) else None
        for item in (report if isinstance(report, list) else [])
    ]
    if figures != list(FAILURE_FIGURES) or not all(
        isinstance(item, Mapping) and _text(item.get("statement"))
        for item in (report if isinstance(report, list) else [None])
    ):
        yield Finding(rule, name, f"{where}.report", f"exactly {list(FAILURE_FIGURES)}")


def _computation_findings(name: str, document: Mapping[str, Any]) -> Iterator[Finding]:
    rule = "e03-computations"
    definition = _member(document, "definition")
    computations = _member(definition, "computations")
    for member in COMPUTATIONS:
        if not _text(computations.get(member)):
            yield Finding(
                rule, name, f"definition.computations.{member}", "a statement"
            )
    if _phrases(computations.get("notObserved"), (NEVER_HEALTHY,)):
        yield Finding(
            rule,
            name,
            "definition.computations.notObserved",
            f"holds {NEVER_HEALTHY!r}",
        )
    missing = _phrases(definition.get("ordering"), (MARGIN_PHRASE, NO_LEAD_OR_LAG))
    if missing:
        yield Finding(rule, name, "definition.ordering", f"holds {missing}")


# --------------------------------------------------------------------------
# V2-E06
# --------------------------------------------------------------------------


def _view_findings(
    name: str, document: Mapping[str, Any], sources: Mapping[str, Mapping[str, Any]]
) -> Iterator[Finding]:
    rule = "e06-views"
    views = _member(document, "definition").get("views")
    if not isinstance(views, list):
        yield Finding(rule, name, "definition.views", "a list of views")
        return
    if set(E06_SOURCES) - set(sources):
        # A source that is not bound has its own finding, and no side is read.
        return
    by_id = {
        v["id"]: v
        for v in views
        if isinstance(v, Mapping) and isinstance(v.get("id"), str)
    }
    if [v.get("id") if isinstance(v, Mapping) else None for v in views] != [
        VIEW_A,
        VIEW_B,
    ]:
        yield Finding(rule, name, "definition.views", f"exactly {[VIEW_A, VIEW_B]}")
    expected_a = []
    for source in E06_SOURCES:
        topology = _value(sources.get(source, {}), "topology")
        expected_a.append(
            {
                "experiment": source,
                "apiReplicas": _member({"t": topology}, "t").get("apiReplicas"),
                "runtimeReplicas": _member({"t": topology}, "t").get("runtimeReplicas"),
            }
        )
    keys = ("experiment", "apiReplicas", "runtimeReplicas")
    sides_a = by_id.get(VIEW_A, {}).get("sides")
    stated_a = [
        {k: side.get(k) for k in keys} if isinstance(side, Mapping) else None
        for side in (sides_a if isinstance(sides_a, list) else [])
    ]
    if stated_a != expected_a:
        yield Finding(rule, name, "definition.views[view-a].sides", f"{expected_a}")
    target = expected_a[-1]
    expected_b = [
        {
            "name": SINGLE_PATH,
            "apiReplicas": 1,
            "runtimeReplicas": 1,
            "reconstructed": True,
        },
        {
            "name": "target",
            "experiment": target["experiment"],
            "apiReplicas": target["apiReplicas"],
            "runtimeReplicas": target["runtimeReplicas"],
            "reconstructed": False,
        },
    ]
    sides_b = by_id.get(VIEW_B, {}).get("sides")
    stated_b = [
        {k: side.get(k) for k in expected_b[i]}
        if isinstance(side, Mapping) and i < len(expected_b)
        else None
        for i, side in enumerate(sides_b if isinstance(sides_b, list) else [])
    ]
    if stated_b != expected_b:
        yield Finding(rule, name, "definition.views[view-b].sides", f"{expected_b}")


def _label_findings(name: str, document: Mapping[str, Any]) -> Iterator[Finding]:
    rule = "e06-labels"
    definition = _member(document, "definition")
    for member in ("views", "metrics"):
        items = definition.get(member)
        for index, item in enumerate(items if isinstance(items, list) else []):
            where = f"definition.{member}[{index}]"
            if not isinstance(item, Mapping):
                continue
            label = item.get("label")
            reads = _strings(item.get("reads"))
            if label not in LABELS:
                yield Finding(rule, name, f"{where}.label", f"one of {list(LABELS)}")
                continue
            utilization = member == "metrics" and item.get("id") == UTILIZATION
            if utilization and label not in (MEASURED, UNAVAILABLE):
                yield Finding(
                    rule,
                    name,
                    f"{where}.label",
                    "the utilization is measured or unavailable",
                )
            elif not utilization and label == MEASURED:
                yield Finding(
                    rule, name, f"{where}.label", "only the utilization is measured"
                )
                continue
            if not reads or not set(reads) <= CONFIGURATION_READS | RUN_READS:
                yield Finding(
                    rule,
                    name,
                    f"{where}.reads",
                    f"reads of {sorted(CONFIGURATION_READS | RUN_READS)}",
                )
                continue
            if label == MEASURED and not set(reads) & RUN_READS:
                yield Finding(
                    rule,
                    name,
                    f"{where}.label",
                    f"it reads only {sorted(reads)}, so it is not measured",
                )
            if label == STATIC and not set(reads) <= CONFIGURATION_READS:
                yield Finding(
                    rule,
                    name,
                    f"{where}.label",
                    "a static allocation reads configuration alone",
                )


def _metric_findings(name: str, document: Mapping[str, Any]) -> Iterator[Finding]:
    rule = "e06-metrics"
    definition = _member(document, "definition")
    metrics = definition.get("metrics")
    ids = [
        m.get("id") if isinstance(m, Mapping) else None
        for m in (metrics if isinstance(metrics, list) else [])
    ]
    if ids != list(E06_METRICS):
        yield Finding(rule, name, "definition.metrics", f"exactly {list(E06_METRICS)}")
    for index, metric in enumerate(metrics if isinstance(metrics, list) else []):
        if isinstance(metric, Mapping) and not _text(metric.get("statement")):
            yield Finding(
                rule, name, f"definition.metrics[{index}].statement", "a statement"
            )
    if not _text(definition.get("rolloutHeadroom")):
        yield Finding(
            rule, name, "definition.rolloutHeadroom", "the headroom definition"
        )


def _utilization_findings(name: str, document: Mapping[str, Any]) -> Iterator[Finding]:
    rule = "e06-utilization"
    where = "definition.utilization"
    utilization = _member(document, "definition").get("utilization")
    if not isinstance(utilization, Mapping):
        yield Finding(rule, name, where, "the utilization statistic is stated")
        return
    resource_queries = {q.name for q in QUERIES if q.stream == RESOURCES}
    for member in ("statistic", "window", "aggregate", "noSeries"):
        if not _text(utilization.get(member)):
            yield Finding(rule, name, f"{where}.{member}", "a statement")
    if utilization.get("stream") != RESOURCES:
        yield Finding(rule, name, f"{where}.stream", RESOURCES)
    if utilization.get("querySet") != QUERY_SET:
        yield Finding(rule, name, f"{where}.querySet", QUERY_SET)
    queries = _strings(utilization.get("queries"))
    if (
        queries is None
        or UTILIZATION_QUERY not in queries
        or not set(queries) <= resource_queries
    ):
        yield Finding(
            rule,
            name,
            f"{where}.queries",
            f"registered resources queries with {UTILIZATION_QUERY}",
        )
    runs = _member(utilization, "sourceRuns")
    if runs.get("experiments") != list(E06_SOURCES) or not _text(runs.get("runs")):
        yield Finding(
            rule,
            name,
            f"{where}.sourceRuns",
            f"the counted runs of {list(E06_SOURCES)}",
        )


def _cost_findings(name: str, document: Mapping[str, Any]) -> Iterator[Finding]:
    rule = "e06-cost-basis"
    where = "definition.costBasis"
    basis = _member(document, "definition").get("costBasis")
    if not isinstance(basis, Mapping):
        yield Finding(rule, name, where, "the cost basis is stated")
        return
    if basis.get("basis") != LOCAL:
        yield Finding(rule, name, f"{where}.basis", LOCAL)
    cloud = _member(basis, "cloud")
    if cloud.get("used") is not False or _phrases(cloud.get("rule"), CLOUD_PHRASES):
        yield Finding(
            rule, name, f"{where}.cloud", "not used, with the rule for a later use"
        )
    if not _text(basis.get("statement")):
        yield Finding(rule, name, f"{where}.statement", "a statement")
    for location, _ in _named_members(basis, PRICE_MEMBERS, where):
        yield Finding(rule, name, location, "no price, charge, currency, or amount")


def _target_findings(name: str, document: Mapping[str, Any]) -> Iterator[Finding]:
    rule = "e06-evidence-target"
    target = _member(_member(document, "definition"), "evidenceTarget")
    for member, level in EVIDENCE_TARGET.items():
        if target.get(member) != level:
            yield Finding(rule, name, f"definition.evidenceTarget.{member}", level)
    if not _text(target.get("costConfidence")):
        yield Finding(
            rule, name, "definition.evidenceTarget.costConfidence", "a statement"
        )


# --------------------------------------------------------------------------
# The records
# --------------------------------------------------------------------------


def _record_findings(
    root: Path,
    name: str,
    document: Any,
    experiment: AnalysisExperiment,
    registry: Mapping[str, str],
    *,
    latest: bool,
) -> list[Finding]:
    if experiment not in EXPERIMENTS:
        raise ValueError(f"{experiment.experiment_id} is not an analysis experiment")
    problem = _shape_problem(document, experiment)
    if problem is not None:
        return [Finding(f"{experiment.prefix}-record-shape", name, "$", problem)]
    roles = E03_SOURCES if experiment == E03 else E06_SOURCES
    findings: list[Finding] = list(_field_findings(name, document, experiment))
    sources: dict[str, Mapping[str, Any]] = {}
    for finding, source, record in _binding_findings(
        root, name, document, experiment, roles, registry, latest=latest
    ):
        if finding is not None:
            findings.append(finding)
        else:
            sources[source] = record
    findings.extend(_source_field_findings(name, document, experiment, sources))
    findings.extend(_contradiction_findings(name, document, experiment))
    findings.extend(_code_findings(name, document, experiment, roles))
    if experiment == E03:
        findings.extend(_population_findings(name, document))
        findings.extend(_signal_set_findings(name, document))
        findings.extend(_signal_stream_findings(name, document, sources))
        findings.extend(_candidate_findings(name, document))
        findings.extend(_ranking_findings(name, document))
        findings.extend(_caller_failure_findings(name, document))
        findings.extend(_computation_findings(name, document))
    else:
        findings.extend(_view_findings(name, document, sources))
        findings.extend(_label_findings(name, document))
        findings.extend(_metric_findings(name, document))
        findings.extend(_utilization_findings(name, document))
        findings.extend(_cost_findings(name, document))
        findings.extend(_target_findings(name, document))
    return findings


def _sorted(findings: list[Finding]) -> list[Finding]:
    order = {rule: index for index, rule in enumerate(RULES)}
    return sorted(findings, key=lambda f: (order[f.rule_id], f.record, f.location))


def check_records(
    root: Path = REPO_ROOT, experiments: Sequence[AnalysisExperiment] = EXPERIMENTS
) -> list[Finding]:
    """Every finding of the committed records of ``experiments``.

    The latest revision of each is checked in full. A superseded revision is
    checked against every rule except that its sources are the latest ones. No
    rule reads which source revisions were the latest when it was registered.
    """
    try:
        registry: Mapping[str, str] = load_registry(root)
    except ValueError:
        registry = {}
    findings: list[Finding] = []
    for experiment in experiments:
        revisions = _revisions(root, experiment.directory)
        if not revisions:
            findings.append(
                Finding(
                    f"{experiment.prefix}-record-missing",
                    experiment.directory,
                    "$",
                    "no freeze record is committed",
                )
            )
            continue
        last = max(revisions)
        for revision, path in sorted(revisions.items()):
            read = _read(root, path)
            document = None if read is None else read[1]
            findings.extend(
                _record_findings(
                    root,
                    path,
                    document,
                    experiment,
                    registry,
                    latest=revision == last,
                )
            )
    return _sorted(findings)


def check_repository(root: Path = REPO_ROOT) -> list[Finding]:
    """Every finding of the committed V2-E03 and V2-E06 records."""
    return check_records(root)
