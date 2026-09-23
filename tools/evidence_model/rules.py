"""The evidence-level classification rules, as checks rather than as sentences.

[The specification](../../docs/testing/evidence-levels.md) says what `C0` to `C4`
mean. [The `v1alpha2` schema](../../docs/testing/claim-evidence-matrix.v1alpha2.schema.json)
encodes the parts of that which are the *shape* of one record. This module encodes
the parts a JSON schema cannot express: rules that compare two fields of one record,
compare a record with the claim that holds it, or compare a claim with the register
around it. [The rule catalogue](../../docs/testing/evidence-level-rules.md) lists
every rule, says which of the three places enforces it, and names the judgements
none of them can make.

The design decision worth reading first is **where materiality is declared**. The
schema lets a record say, per substitution, whether the replaced component was
material to its claim. That puts the one question that decides `C1` in the hands of
whoever writes the record, and a record that mocks the inference runtime and marks
the mock `claimMaterial: false` passes the schema at `C2`. So a claim now declares
its claim-material components once, in `claimMaterialComponents`, and every record
supporting it is checked against that one declaration: a record cannot substitute a
declared component and call it immaterial, cannot reach `C2` without executing every
declared component, and cannot reach `C1` by substituting something that was never
declared material -- which is how a synthetic prompt set dressed up as a substituted
"component" is refused.

**The declaration is the limit of all three.** A claim that under-declares -- names the
API and leaves the runtime out -- lets a record mock the runtime, flag the mock
immaterial, and pass at `C2`, and a test asserts that it still does. Whether the
declaration is complete is a reviewer's call, catalogued as
`the-declared-claim-material-components-are-the-right-ones`. What changed is where
that call is made: once per claim, in the open, rather than once per record by the
person who wants the record to pass.

Nothing here reads a committed register as `v1alpha2`, because no committed register
declares that version yet. What runs over committed data is the in-memory read in
`core.read_legacy_as_v1alpha2`, and a test holds it to zero refusals.
"""

from __future__ import annotations

from collections.abc import Callable, Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any, Final, Literal

from .core import Refusal, validate_claim, validate_record, validate_register

__all__ = [
    "LEGACY_CEILING_RANK",
    "RULES",
    "Rule",
    "check_claim",
    "check_record",
    "check_register",
    "rule",
    "unimplemented_rules",
]

Subject = Literal["record", "claim", "register"]
EnforcedBy = Literal["schema", "validator", "review"]

EXECUTING_LEVELS: Final = ("C1", "C2", "C3", "C4")
REAL_LEVELS: Final = ("C2", "C3", "C4")

#: What a `C0` record may have run. Static evidence is produced by something that
#: inspects artifacts; a record naming the runtime as executed has executed the
#: target behaviour, whatever its `targetBehaviourExecuted` flag says.
INSPECTION_ROLES: Final = frozenset({"validator", "tool"})

#: The superseded ranking, used only on carried `v1alpha1` values. `none` is the
#: absence of a level and sorts below `C0`, as it does in the register's own suite.
LEGACY_CEILING_RANK: Final[dict[str, int]] = {
    "none": -1,
    "C0": 0,
    "C1": 1,
    "C2": 2,
    "C3": 3,
    "C4": 4,
}

#: Sentences that occupy a limitation's slot while saying nothing. The check is a
#: heuristic and the rule catalogue says so: it refuses the empty gestures people
#: actually type, not every vacuous sentence a person could write.
_PLACEHOLDERS: Final = frozenset(
    {
        "-",
        "n/a",
        "na",
        "none",
        "nothing",
        "no limitations",
        "not applicable",
        "tbd",
        "todo",
        "unknown",
    }
)
_MINIMUM_STATEMENT: Final = 20

#: A tolerance for a duration stated alongside the timestamps it was computed from.
_DURATION_TOLERANCE_SECONDS: Final = 1.0


@dataclass(frozen=True)
class Rule:
    """One classification rule and the place that enforces it.

    `enforced_by` is the honest part. `schema` means the published schema refuses a
    violation; `validator` means a function in this module does; `review` means
    nothing does, and the catalogue says why a machine should not pretend to.
    """

    rule_id: str
    subject: Subject
    levels: tuple[str, ...]
    enforced_by: EnforcedBy
    statement: str


RULES: Final[tuple[Rule, ...]] = (
    # ----------------------------------------------------------- the schema
    Rule(
        "an-evidence-level-belongs-to-an-evidence-record",
        "claim",
        (),
        "schema",
        "A claim carries no evidence level. Its records do, one each.",
    ),
    Rule(
        "a-classified-record-states-what-ran-where-and-how",
        "record",
        (),
        "schema",
        "A record carrying a level states what executed, its workload source, its "
        "environment, how to repeat it, an immutable identifier, and an artifact.",
    ),
    Rule(
        "a-classified-record-states-its-limitations-and-what-it-does-not-establish",
        "record",
        (),
        "schema",
        "A record carrying a level lists at least one limitation and at least one "
        "thing it does not establish.",
    ),
    Rule(
        "an-unmigrated-record-carries-no-level",
        "record",
        (),
        "schema",
        "A legacy-unmigrated record has a null level and keeps its superseded "
        "classification verbatim.",
    ),
    Rule(
        "a-c0-record-did-not-execute-the-target-behaviour",
        "record",
        ("C0",),
        "schema",
        "A C0 record states that the behaviour the claim is about did not run.",
    ),
    Rule(
        "an-executing-record-names-what-executed",
        "record",
        EXECUTING_LEVELS,
        "schema",
        "A record at C1 or above states that the target behaviour ran and names at "
        "least one component that executed.",
    ),
    Rule(
        "a-c1-record-names-a-claim-material-substitution",
        "record",
        ("C1",),
        "schema",
        "A C1 record names at least one substitution flagged claim-material.",
    ),
    Rule(
        "a-real-record-substitutes-nothing-claim-material",
        "record",
        REAL_LEVELS,
        "schema",
        "A record at C2 or above flags no substitution as claim-material.",
    ),
    Rule(
        "a-c3-record-declares-representativeness-and-criteria-before-the-run",
        "record",
        ("C3",),
        "schema",
        "A C3 record declares representativeness with written assumptions, a "
        "measurement method, results, and criteria each flagged declared before.",
    ),
    Rule(
        "a-c4-record-names-a-production-context-and-an-observation-period",
        "record",
        ("C4",),
        "schema",
        "A C4 record ran in organizational production and names the organization, "
        "the workload that depended on it, the period, known gaps, and results.",
    ),
    Rule(
        "a-planned-or-deferred-claim-cites-no-record",
        "claim",
        (),
        "schema",
        "A planned or deferred claim holds no evidence record.",
    ),
    # --------------------------------------------------------- the validator
    Rule(
        "a-component-either-executed-or-was-substituted",
        "record",
        (),
        "validator",
        "No component is named both as having executed and as having been "
        "substituted in the same record.",
    ),
    Rule(
        "a-c0-record-ran-only-inspection",
        "record",
        ("C0",),
        "validator",
        "A C0 record ran only validators or tools, substituted nothing, issued no "
        "workload, and names no production context.",
    ),
    Rule(
        "an-executing-record-ran-outside-the-repository",
        "record",
        EXECUTING_LEVELS,
        "validator",
        "A record at C1 or above names an environment other than repository-only.",
    ),
    Rule(
        "a-result-answers-a-criterion-the-record-declares",
        "record",
        (),
        "validator",
        "Criterion identifiers are unique, and a result that names a criterion "
        "names one the record declares.",
    ),
    Rule(
        "an-observation-period-ends-after-it-starts",
        "record",
        (),
        "validator",
        "Every observation period ends after it starts, and a stated duration "
        "agrees with the timestamps.",
    ),
    Rule(
        "a-limitation-says-something",
        "record",
        (),
        "validator",
        "No limitation or does-not-establish entry is a placeholder or shorter "
        "than twenty characters.",
    ),
    Rule(
        "a-c3-record-declares-its-workload-shape",
        "record",
        ("C3",),
        "validator",
        "A C3 record states at least one workload characteristic: concurrency, "
        "request count, prompt-size distribution, arrival pattern, or duration.",
    ),
    Rule(
        "a-c3-record-declares-the-conditions-it-represents",
        "record",
        ("C3",),
        "validator",
        "A C3 record describes, in its environment note, the infrastructure and "
        "conditions it was run on as representative ones.",
    ),
    Rule(
        "a-c3-record-measures-every-criterion-it-declares",
        "record",
        ("C3",),
        "validator",
        "Every C3 criterion has an outcome other than not-evaluated and at least "
        "one result that cites it, including the criteria that were not met.",
    ),
    Rule(
        "a-c4-record-observed-production-traffic",
        "record",
        ("C4",),
        "validator",
        "A C4 record's workload source is production traffic.",
    ),
    Rule(
        "a-c4-record-states-how-production-was-observed",
        "record",
        ("C4",),
        "validator",
        "A C4 record carries a measurement method: the production telemetry or "
        "observation its results were read from.",
    ),
    Rule(
        "a-record-names-the-claim-that-holds-it",
        "claim",
        (),
        "validator",
        "A record's claimId is the identifier of the claim that holds it.",
    ),
    Rule(
        "a-record-identifier-is-unique",
        "register",
        (),
        "validator",
        "No two records in a claim, or in a register, share a recordId.",
    ),
    Rule(
        "an-executed-claim-declares-its-claim-material-components",
        "claim",
        EXECUTING_LEVELS,
        "validator",
        "A claim holding a classified record at C1 or above declares the "
        "components material to evaluating it, in claimMaterialComponents.",
    ),
    Rule(
        "a-substituted-claim-material-component-is-flagged-material",
        "claim",
        (),
        "validator",
        "A record that substitutes a component its claim declares material flags "
        "the substitution claim-material. A record cannot call a mock of a declared "
        "component immaterial; a component the claim never declared is not caught.",
    ),
    Rule(
        "a-claim-material-substitution-replaces-a-declared-component",
        "claim",
        ("C1",),
        "validator",
        "A substitution flagged claim-material replaces a component the claim "
        "declares material. Input is not a component, so a synthetic workload "
        "cannot be the substitution that puts a record at C1.",
    ),
    Rule(
        "a-real-record-executed-every-claim-material-component",
        "claim",
        REAL_LEVELS,
        "validator",
        "A record at C2 or above names every component its claim declares "
        "material among the components that executed.",
    ),
    Rule(
        "a-certified-claim-rests-on-classified-evidence",
        "claim",
        (),
        "validator",
        "A certified claim holds at least one record with a level, or a carried "
        "legacy classification with one. A claim with no classified evidence is "
        "not published as a capability.",
    ),
    Rule(
        "a-real-behaviour-claim-rests-on-real-evidence",
        "claim",
        REAL_LEVELS,
        "validator",
        "A certified claim that asserts real behaviour holds a record at C2 or "
        "above, or a carried legacy classification whose evidence class may "
        "support real behaviour. A mock cannot establish what it replaced.",
    ),
    Rule(
        "a-statement-about-real-behaviour-declares-it",
        "claim",
        (),
        "validator",
        "A claim whose statement says it serves a real completion or real inference "
        "sets assertsRealBehaviour, so the real-evidence rule cannot be switched off "
        "by leaving one flag false. A phrase list, carried from the v1alpha1 register.",
    ),
    Rule(
        "a-claim-identifier-is-unique",
        "register",
        (),
        "validator",
        "No two claims in a register share a claimId.",
    ),
    Rule(
        "a-citation-is-a-plain-repository-path",
        "register",
        (),
        "validator",
        "No evidence reference, versions reference, or procedure workflow contains a "
        "'.' or '..' segment or an empty one, so no citation can detour into the "
        "template root or out of the evidence root while its prefix says otherwise.",
    ),
    Rule(
        "a-template-is-not-evidence",
        "register",
        (),
        "validator",
        "No evidence reference, versions reference, or procedure workflow names a "
        "file under the register's templateRoot.",
    ),
    Rule(
        "evidence-is-cited-from-the-evidence-root",
        "register",
        (),
        "validator",
        "Every evidence reference names a file under the register's evidenceRoot.",
    ),
    Rule(
        "a-cited-record-exists",
        "register",
        (),
        "validator",
        "Every evidence reference names a file that exists, when the check is "
        "given a repository to look in.",
    ),
    Rule(
        "a-legacy-classification-stays-under-its-legacy-ceiling",
        "register",
        (),
        "validator",
        "A carried v1alpha1 classification names an evidence class the register "
        "defines, and its level does not exceed that class's legacy ceiling. The "
        "old rule, applied to old data only.",
    ),
    # ----------------------------------------------------------- the review
    Rule(
        "the-declared-claim-material-components-are-the-right-ones",
        "claim",
        (),
        "review",
        "Whether claimMaterialComponents names what evaluating the claim actually "
        "requires. The validator holds records to the declaration; only a reader "
        "of the claim can hold the declaration to the claim.",
    ),
    Rule(
        "a-declared-representative-workload-represents-intended-use",
        "record",
        ("C3",),
        "review",
        "Whether the declared intended use, assumptions, and shape actually "
        "represent how the system is meant to be used.",
    ),
    Rule(
        "a-criterion-flagged-declared-before-was-registered-before",
        "record",
        ("C3",),
        "review",
        "Whether a criterion flagged declaredBefore was in fact registered before "
        "the run. The flag is required; its truth is in the history of the record.",
    ),
    Rule(
        "a-production-context-is-genuine",
        "record",
        ("C4",),
        "review",
        "Whether the organization and depending workload are real and depended on "
        "the system. A cloud experiment can be written in this shape; it cannot "
        "be made genuine by one.",
    ),
    Rule(
        "a-limitation-is-the-right-limitation",
        "record",
        (),
        "review",
        "Whether the limitations and does-not-establish entries name what a "
        "reader would otherwise over-read. The validator refuses placeholders, "
        "not omissions of substance.",
    ),
    Rule(
        "evidence-is-relevant-and-sufficient-for-its-claim",
        "claim",
        (),
        "review",
        "Whether the records a claim holds support its statement. A level says "
        "how evidence was obtained; it does not say the evidence is about the "
        "claim, and a higher level is not better evidence for every claim.",
    ),
)

RULES_BY_ID: Final[dict[str, Rule]] = {entry.rule_id: entry for entry in RULES}

# ------------------------------------------------------------ the machinery

RecordCheck = Callable[[Mapping[str, Any], str], Iterator[Refusal]]
ClaimCheck = Callable[
    [Mapping[str, Any], str, Mapping[str, Mapping[str, Any]] | None],
    Iterator[Refusal],
]

_RECORD_CHECKS: dict[str, RecordCheck] = {}
_CLAIM_CHECKS: dict[str, ClaimCheck] = {}


def rule(rule_id: str) -> Rule:
    """The catalogue entry for one rule, or a KeyError naming it."""
    return RULES_BY_ID[rule_id]


def _record_check(rule_id: str) -> Callable[[RecordCheck], RecordCheck]:
    def register(function: RecordCheck) -> RecordCheck:
        assert RULES_BY_ID[rule_id].enforced_by == "validator", rule_id
        _RECORD_CHECKS[rule_id] = function
        return function

    return register


def _claim_check(rule_id: str) -> Callable[[ClaimCheck], ClaimCheck]:
    def register(function: ClaimCheck) -> ClaimCheck:
        assert RULES_BY_ID[rule_id].enforced_by == "validator", rule_id
        _CLAIM_CHECKS[rule_id] = function
        return function

    return register


def _refuse(rule_id: str, path: str, message: str) -> Refusal:
    return Refusal(path=path, message=message, rule=rule_id)


def _level(record: Mapping[str, Any]) -> str | None:
    """The level of a classified record, or None for an unmigrated one."""
    if record.get("migrationState") != "migrated":
        return None
    level = record.get("evidenceLevel")
    return level if isinstance(level, str) else None


def _list(node: Any) -> list[Any]:
    return list(node) if isinstance(node, list) else []


def _dict(node: Any) -> Mapping[str, Any]:
    return node if isinstance(node, Mapping) else {}


def _component_ids(entries: Iterable[Any]) -> list[str]:
    return [
        str(entry["componentId"])
        for entry in entries
        if isinstance(entry, Mapping) and "componentId" in entry
    ]


def _timestamp(value: Any) -> datetime | None:
    if not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


# ------------------------------------------------------------ record rules


@_record_check("a-component-either-executed-or-was-substituted")
def _executed_or_substituted(record: Mapping[str, Any], at: str) -> Iterator[Refusal]:
    if _level(record) is None:
        return
    execution = _dict(record.get("execution"))
    executed = set(_component_ids(_list(execution.get("executedComponents"))))
    for index, component in enumerate(
        _component_ids(_list(execution.get("substitutions")))
    ):
        if component in executed:
            yield _refuse(
                "a-component-either-executed-or-was-substituted",
                f"{at}.execution.substitutions[{index}]",
                f"{component!r} is named as having executed and as having been "
                "substituted; a replaced component did not run",
            )


@_record_check("a-c0-record-ran-only-inspection")
def _c0_ran_only_inspection(record: Mapping[str, Any], at: str) -> Iterator[Refusal]:
    if _level(record) != "C0":
        return
    rule_id = "a-c0-record-ran-only-inspection"
    execution = _dict(record.get("execution"))
    for index, component in enumerate(_list(execution.get("executedComponents"))):
        role = _dict(component).get("role")
        if role not in INSPECTION_ROLES:
            yield _refuse(
                rule_id,
                f"{at}.execution.executedComponents[{index}]",
                f"a C0 record ran a component in role {role!r}; static evidence "
                f"is produced by {sorted(INSPECTION_ROLES)} only",
            )
    if _list(execution.get("substitutions")):
        yield _refuse(
            rule_id,
            f"{at}.execution.substitutions",
            "a C0 record names a substitution, but nothing ran for it to replace",
        )
    source = _dict(record.get("workload")).get("source")
    if source is not None and source != "none":
        yield _refuse(
            rule_id,
            f"{at}.workload.source",
            f"a C0 record issued a {source!r} workload; issuing one executes the "
            "behaviour static evidence is defined by not executing",
        )
    if "productionContext" in record:
        yield _refuse(
            rule_id,
            f"{at}.productionContext",
            "a C0 record names a production context; production is not inspected "
            "statically",
        )


@_record_check("an-executing-record-ran-outside-the-repository")
def _ran_outside_repository(record: Mapping[str, Any], at: str) -> Iterator[Refusal]:
    if _level(record) not in EXECUTING_LEVELS:
        return
    environment = _dict(record.get("environment")).get("environmentId")
    if environment == "repository-only":
        yield _refuse(
            "an-executing-record-ran-outside-the-repository",
            f"{at}.environment.environmentId",
            f"a {_level(record)} record says the behaviour ran, and names "
            "repository-only as where; a repository does not execute anything",
        )


@_record_check("a-result-answers-a-criterion-the-record-declares")
def _result_answers_a_criterion(
    record: Mapping[str, Any], at: str
) -> Iterator[Refusal]:
    rule_id = "a-result-answers-a-criterion-the-record-declares"
    criteria = _list(record.get("acceptanceCriteria"))
    seen: set[str] = set()
    for index, criterion in enumerate(criteria):
        identifier = _dict(criterion).get("criterionId")
        if identifier in seen:
            yield _refuse(
                rule_id,
                f"{at}.acceptanceCriteria[{index}].criterionId",
                f"criterion {identifier!r} is declared twice",
            )
        if isinstance(identifier, str):
            seen.add(identifier)
    for index, result in enumerate(_list(record.get("results"))):
        cited = _dict(result).get("criterionId")
        if cited is not None and cited not in seen:
            yield _refuse(
                rule_id,
                f"{at}.results[{index}].criterionId",
                f"the result answers criterion {cited!r}, which the record does "
                "not declare",
            )


def _periods(record: Mapping[str, Any], at: str) -> Iterator[tuple[str, Any]]:
    measurement = _dict(record.get("measurement"))
    if "observationPeriod" in measurement:
        yield (
            f"{at}.measurement.observationPeriod",
            measurement["observationPeriod"],
        )
    production = _dict(record.get("productionContext"))
    if "observationPeriod" in production:
        yield (
            f"{at}.productionContext.observationPeriod",
            production["observationPeriod"],
        )


@_record_check("an-observation-period-ends-after-it-starts")
def _period_is_ordered(record: Mapping[str, Any], at: str) -> Iterator[Refusal]:
    rule_id = "an-observation-period-ends-after-it-starts"
    for path, period in _periods(record, at):
        start = _timestamp(_dict(period).get("start"))
        end = _timestamp(_dict(period).get("end"))
        if start is None or end is None:
            yield _refuse(
                rule_id, path, "the period's start or end is not an ISO 8601 time"
            )
            continue
        if start.tzinfo is None or end.tzinfo is None:
            yield _refuse(
                rule_id,
                path,
                "the period's start or end carries no UTC offset, so the "
                "interval between them is not defined",
            )
            continue
        if end <= start:
            yield _refuse(
                rule_id, path, f"the period ends at {end} and starts at {start}"
            )
            continue
        stated = _dict(period).get("durationSeconds")
        actual = (end - start).total_seconds()
        if (
            isinstance(stated, (int, float))
            and abs(stated - actual) > _DURATION_TOLERANCE_SECONDS
        ):
            yield _refuse(
                rule_id,
                f"{path}.durationSeconds",
                f"the period states {stated} seconds and its timestamps are "
                f"{actual} seconds apart",
            )


def _is_placeholder(sentence: Any) -> bool:
    if not isinstance(sentence, str):
        return True
    normalized = sentence.strip().rstrip(".").strip().lower()
    return normalized in _PLACEHOLDERS or len(sentence.strip()) < _MINIMUM_STATEMENT


@_record_check("a-limitation-says-something")
def _limitation_says_something(record: Mapping[str, Any], at: str) -> Iterator[Refusal]:
    if _level(record) is None:
        return
    for field in ("limitations", "doesNotEstablish"):
        for index, sentence in enumerate(_list(record.get(field))):
            if _is_placeholder(sentence):
                yield _refuse(
                    "a-limitation-says-something",
                    f"{at}.{field}[{index}]",
                    f"{sentence!r} fills the slot without stating a limit",
                )


_SHAPE_FIELDS: Final = (
    "concurrency",
    "requestCount",
    "promptSizeDistribution",
    "arrivalPattern",
    "durationSeconds",
)


@_record_check("a-c3-record-declares-its-workload-shape")
def _c3_workload_shape(record: Mapping[str, Any], at: str) -> Iterator[Refusal]:
    if _level(record) != "C3":
        return
    shape = _dict(_dict(record.get("workload")).get("shape"))
    if not any(field in shape for field in _SHAPE_FIELDS):
        yield _refuse(
            "a-c3-record-declares-its-workload-shape",
            f"{at}.workload",
            "a C3 record declares a representative workload and states none of "
            "its characteristics",
        )


@_record_check("a-c3-record-declares-the-conditions-it-represents")
def _c3_conditions(record: Mapping[str, Any], at: str) -> Iterator[Refusal]:
    if _level(record) != "C3":
        return
    note = _dict(record.get("environment")).get("note")
    if _is_placeholder(note):
        yield _refuse(
            "a-c3-record-declares-the-conditions-it-represents",
            f"{at}.environment",
            "a C3 record does not describe the infrastructure and conditions it "
            "claims are representative",
        )


@_record_check("a-c3-record-measures-every-criterion-it-declares")
def _c3_measures_every_criterion(
    record: Mapping[str, Any], at: str
) -> Iterator[Refusal]:
    if _level(record) != "C3":
        return
    rule_id = "a-c3-record-measures-every-criterion-it-declares"
    answered = {
        _dict(result).get("criterionId") for result in _list(record.get("results"))
    }
    for index, criterion in enumerate(_list(record.get("acceptanceCriteria"))):
        entry = _dict(criterion)
        identifier = entry.get("criterionId")
        if entry.get("outcome") == "not-evaluated":
            yield _refuse(
                rule_id,
                f"{at}.acceptanceCriteria[{index}].outcome",
                f"criterion {identifier!r} was declared and not evaluated",
            )
        if identifier not in answered:
            yield _refuse(
                rule_id,
                f"{at}.acceptanceCriteria[{index}]",
                f"no result cites criterion {identifier!r}, so its outcome is "
                "asserted rather than measured",
            )


@_record_check("a-c4-record-observed-production-traffic")
def _c4_production_traffic(record: Mapping[str, Any], at: str) -> Iterator[Refusal]:
    if _level(record) != "C4":
        return
    source = _dict(record.get("workload")).get("source")
    if source != "production-traffic":
        yield _refuse(
            "a-c4-record-observed-production-traffic",
            f"{at}.workload.source",
            f"a C4 record's workload was {source!r}; operational evidence is what "
            "genuine production traffic did",
        )


@_record_check("a-c4-record-states-how-production-was-observed")
def _c4_measurement(record: Mapping[str, Any], at: str) -> Iterator[Refusal]:
    if _level(record) != "C4":
        return
    if "measurement" not in record:
        yield _refuse(
            "a-c4-record-states-how-production-was-observed",
            at,
            "a C4 record reports results and does not say what telemetry or "
            "observation they were read from",
        )


# ------------------------------------------------------------- claim rules


def _material(claim: Mapping[str, Any]) -> set[str]:
    return {
        str(component)
        for component in _list(claim.get("claimMaterialComponents"))
        if isinstance(component, str)
    }


def _records(claim: Mapping[str, Any]) -> list[tuple[int, Mapping[str, Any]]]:
    return [
        (index, _dict(record))
        for index, record in enumerate(_list(claim.get("evidenceRecords")))
    ]


@_claim_check("a-record-names-the-claim-that-holds-it")
def _record_names_its_claim(
    claim: Mapping[str, Any], at: str, _: Mapping[str, Mapping[str, Any]] | None
) -> Iterator[Refusal]:
    for index, record in _records(claim):
        if record.get("claimId") != claim.get("claimId"):
            yield _refuse(
                "a-record-names-the-claim-that-holds-it",
                f"{at}.evidenceRecords[{index}].claimId",
                f"the record says it supports {record.get('claimId')!r} and is "
                f"held by {claim.get('claimId')!r}",
            )


@_claim_check("a-record-identifier-is-unique")
def _record_identifiers_in_a_claim(
    claim: Mapping[str, Any], at: str, _: Mapping[str, Mapping[str, Any]] | None
) -> Iterator[Refusal]:
    seen: set[Any] = set()
    for index, record in _records(claim):
        identifier = record.get("recordId")
        if identifier is None:
            continue  # refused by the schema as missing, not as duplicated
        if identifier in seen:
            yield _refuse(
                "a-record-identifier-is-unique",
                f"{at}.evidenceRecords[{index}].recordId",
                f"record {identifier!r} appears twice in one claim",
            )
        seen.add(identifier)


@_claim_check("an-executed-claim-declares-its-claim-material-components")
def _declares_material(
    claim: Mapping[str, Any], at: str, _: Mapping[str, Mapping[str, Any]] | None
) -> Iterator[Refusal]:
    executing = [
        index for index, record in _records(claim) if _level(record) in EXECUTING_LEVELS
    ]
    if executing and not _material(claim):
        yield _refuse(
            "an-executed-claim-declares-its-claim-material-components",
            at,
            f"the claim holds executed evidence (records {executing}) and does not "
            "declare which components are material to it, so neither C1 nor C2 "
            "can be checked",
        )


@_claim_check("a-substituted-claim-material-component-is-flagged-material")
def _declared_component_is_material(
    claim: Mapping[str, Any], at: str, _: Mapping[str, Mapping[str, Any]] | None
) -> Iterator[Refusal]:
    material = _material(claim)
    for index, record in _records(claim):
        if _level(record) is None:
            continue
        execution = _dict(record.get("execution"))
        for position, substitution in enumerate(_list(execution.get("substitutions"))):
            entry = _dict(substitution)
            if (
                entry.get("componentId") in material
                and entry.get("claimMaterial") is not True
            ):
                yield _refuse(
                    "a-substituted-claim-material-component-is-flagged-material",
                    f"{at}.evidenceRecords[{index}].execution.substitutions[{position}]",
                    f"{entry.get('componentId')!r} is declared material to the "
                    "claim, was substituted, and is flagged immaterial",
                )


@_claim_check("a-claim-material-substitution-replaces-a-declared-component")
def _material_substitution_is_declared(
    claim: Mapping[str, Any], at: str, _: Mapping[str, Mapping[str, Any]] | None
) -> Iterator[Refusal]:
    material = _material(claim)
    if not material:
        # Refused by the declaration rule instead; one missing declaration is one
        # refusal, not one per substitution.
        return
    for index, record in _records(claim):
        if _level(record) is None:
            continue
        execution = _dict(record.get("execution"))
        for position, substitution in enumerate(_list(execution.get("substitutions"))):
            entry = _dict(substitution)
            if (
                entry.get("claimMaterial") is True
                and entry.get("componentId") not in material
            ):
                yield _refuse(
                    "a-claim-material-substitution-replaces-a-declared-component",
                    f"{at}.evidenceRecords[{index}].execution.substitutions[{position}]",
                    f"{entry.get('componentId')!r} is flagged claim-material and is "
                    f"not among the components the claim declares material "
                    f"({sorted(material)}); an input or an incidental component "
                    "is not the substitution that decides C1",
                )


@_claim_check("a-real-record-executed-every-claim-material-component")
def _real_record_executed_material(
    claim: Mapping[str, Any], at: str, _: Mapping[str, Mapping[str, Any]] | None
) -> Iterator[Refusal]:
    material = _material(claim)
    for index, record in _records(claim):
        if _level(record) not in REAL_LEVELS:
            continue
        executed = set(
            _component_ids(
                _list(_dict(record.get("execution")).get("executedComponents"))
            )
        )
        missing = sorted(material - executed)
        if missing:
            yield _refuse(
                "a-real-record-executed-every-claim-material-component",
                f"{at}.evidenceRecords[{index}].execution.executedComponents",
                f"a {_level(record)} record did not execute {missing}, which the "
                "claim declares material; real is relative to the claim",
            )


#: The phrases the `v1alpha1` register suite treats as a statement about real serving.
#: Carried rather than extended: a longer list would be a new heuristic, and this one
#: is only the replacement of the rule that already runs.
REAL_BEHAVIOUR_WORDS: Final = ("serves a real completion", "real inference")


@_claim_check("a-statement-about-real-behaviour-declares-it")
def _statement_declares_real_behaviour(
    claim: Mapping[str, Any], at: str, _: Mapping[str, Mapping[str, Any]] | None
) -> Iterator[Refusal]:
    statement = str(claim.get("statement", "")).lower()
    if (
        any(words in statement for words in REAL_BEHAVIOUR_WORDS)
        and claim.get("assertsRealBehaviour") is not True
    ):
        yield _refuse(
            "a-statement-about-real-behaviour-declares-it",
            f"{at}.assertsRealBehaviour",
            "the statement is about real serving and the claim does not assert real "
            "behaviour, which exempts it from the rule that it rest on real evidence",
        )


def _legacy_values(claim: Mapping[str, Any]) -> list[Mapping[str, Any]]:
    carried = [
        _dict(record.get("legacyClassification"))
        for _, record in _records(claim)
        if record.get("migrationState") == "legacy-unmigrated"
    ]
    if "legacyClassification" in claim:
        carried.append(_dict(claim["legacyClassification"]))
    return [value for value in carried if value]


@_claim_check("a-certified-claim-rests-on-classified-evidence")
def _certified_rests_on_evidence(
    claim: Mapping[str, Any], at: str, _: Mapping[str, Mapping[str, Any]] | None
) -> Iterator[Refusal]:
    if claim.get("status") != "certified":
        return
    classified = any(_level(record) for _, record in _records(claim))
    carried = any(value.get("certificationLevel") for value in _legacy_values(claim))
    if not (classified or carried):
        yield _refuse(
            "a-certified-claim-rests-on-classified-evidence",
            f"{at}.evidenceRecords",
            "the claim is certified and none of its records carries a level, "
            "current or legacy; an unsupported claim is not published",
        )


@_claim_check("a-real-behaviour-claim-rests-on-real-evidence")
def _real_claim_rests_on_real_evidence(
    claim: Mapping[str, Any],
    at: str,
    classes: Mapping[str, Mapping[str, Any]] | None,
) -> Iterator[Refusal]:
    if (
        claim.get("status") != "certified"
        or claim.get("assertsRealBehaviour") is not True
    ):
        return
    if any(_level(record) in REAL_LEVELS for _, record in _records(claim)):
        return
    for value in _legacy_values(claim):
        label = classes.get(str(value.get("evidenceLabel"))) if classes else None
        if (
            label is not None
            and label.get("maySupportRealBehaviour") is True
            and value.get("certificationLevel")
        ):
            return
    detail = (
        ""
        if classes is not None
        else "; a carried legacy classification cannot be read without the "
        "register's evidence classes, so it was not counted"
    )
    yield _refuse(
        "a-real-behaviour-claim-rests-on-real-evidence",
        f"{at}.evidenceRecords",
        "the claim is certified, asserts real behaviour, and holds no record at C2 "
        f"or above and no carried classification that may support one{detail}",
    )


# ---------------------------------------------------------- register rules


def _references(record: Mapping[str, Any], at: str) -> Iterator[tuple[str, str]]:
    for index, reference in enumerate(_list(record.get("evidenceRefs"))):
        yield f"{at}.evidenceRefs[{index}]", str(reference)
    if isinstance(record.get("versionsRecordedIn"), str):
        yield f"{at}.versionsRecordedIn", record["versionsRecordedIn"]
    workflow = _dict(record.get("procedure")).get("workflowRef")
    if isinstance(workflow, str):
        yield f"{at}.procedure.workflowRef", workflow


def _under(path: str, root: str) -> bool:
    return path.startswith(root.rstrip("/") + "/")


def _is_plain(path: str) -> bool:
    """No `.`, `..`, or empty segment: the prefix of the string is where it points."""
    return all(segment not in ("", ".", "..") for segment in path.split("/"))


def _register_refusals(
    document: Mapping[str, Any], repo_root: Path | None
) -> Iterator[Refusal]:
    claims = _list(document.get("claims"))
    evidence_root = str(document.get("evidenceRoot", ""))
    template_root = str(document.get("templateRoot", ""))
    classes = {
        str(_dict(entry).get("classId")): _dict(entry)
        for entry in _list(document.get("evidenceClasses"))
    }

    seen_claims: set[Any] = set()
    seen_records: dict[Any, str] = {}
    for claim_index, raw_claim in enumerate(claims):
        claim = _dict(raw_claim)
        claim_at = f"$.claims[{claim_index}]"
        if claim.get("claimId") in seen_claims:
            yield _refuse(
                "a-claim-identifier-is-unique",
                f"{claim_at}.claimId",
                f"claim {claim.get('claimId')!r} appears twice",
            )
        seen_claims.add(claim.get("claimId"))

        if "legacyClassification" in claim:
            yield from _legacy_ceiling(
                _dict(claim["legacyClassification"]),
                f"{claim_at}.legacyClassification",
                classes,
            )

        for record_index, record in _records(claim):
            at = f"{claim_at}.evidenceRecords[{record_index}]"
            identifier = record.get("recordId")
            if (
                identifier is not None
                and identifier in seen_records
                and not seen_records[identifier].startswith(f"{claim_at}.")
            ):
                yield _refuse(
                    "a-record-identifier-is-unique",
                    f"{at}.recordId",
                    f"record {identifier!r} is also held at {seen_records[identifier]}",
                )
            if identifier is not None:
                seen_records.setdefault(identifier, at)

            if "legacyClassification" in record:
                yield from _legacy_ceiling(
                    _dict(record["legacyClassification"]),
                    f"{at}.legacyClassification",
                    classes,
                )

            for path, reference in _references(record, at):
                if not _is_plain(reference):
                    yield _refuse(
                        "a-citation-is-a-plain-repository-path",
                        path,
                        f"{reference!r} has a '.', '..', or empty segment, so where it "
                        "points is not what its prefix says",
                    )
                    continue
                if template_root and _under(reference, template_root):
                    yield _refuse(
                        "a-template-is-not-evidence",
                        path,
                        f"{reference!r} is a template under {template_root!r}; a "
                        "template is the shape of a record, not a record",
                    )
                if (
                    path.split(".")[-1].startswith("evidenceRefs")
                    and evidence_root
                    and not _under(reference, evidence_root)
                ):
                    yield _refuse(
                        "evidence-is-cited-from-the-evidence-root",
                        path,
                        f"{reference!r} is not under the evidence root "
                        f"{evidence_root!r}",
                    )
                if repo_root is not None and not (repo_root / reference).is_file():
                    yield _refuse(
                        "a-cited-record-exists",
                        path,
                        f"{reference!r} does not exist in {repo_root}",
                    )

        yield from _claim_rule_refusals(claim, claim_at, classes)


def _legacy_ceiling(
    carried: Mapping[str, Any],
    at: str,
    classes: Mapping[str, Mapping[str, Any]],
) -> Iterator[Refusal]:
    rule_id = "a-legacy-classification-stays-under-its-legacy-ceiling"
    label = str(carried.get("evidenceLabel"))
    if label not in classes:
        yield _refuse(
            rule_id,
            f"{at}.evidenceLabel",
            f"the carried label {label!r} is not an evidence class this register "
            "defines, so its ceiling cannot be read",
        )
        return
    level = carried.get("certificationLevel")
    if level is None:
        return
    ceiling = str(classes[label].get("legacyCeiling", "none"))
    if LEGACY_CEILING_RANK.get(str(level), 99) > LEGACY_CEILING_RANK.get(ceiling, -1):
        yield _refuse(
            rule_id,
            f"{at}.certificationLevel",
            f"the carried level {level!r} exceeds the {label!r} class's legacy "
            f"ceiling {ceiling!r}",
        )


# ------------------------------------------------------------ entry points


def _record_rule_refusals(record: Mapping[str, Any], at: str) -> Iterator[Refusal]:
    for check in _RECORD_CHECKS.values():
        yield from check(record, at)


def _claim_rule_refusals(
    claim: Mapping[str, Any],
    at: str,
    classes: Mapping[str, Mapping[str, Any]] | None,
) -> Iterator[Refusal]:
    for index, record in _records(claim):
        yield from _record_rule_refusals(record, f"{at}.evidenceRecords[{index}]")
    for check in _CLAIM_CHECKS.values():
        yield from check(claim, at, classes)


def _sorted(found: Iterable[Refusal]) -> list[Refusal]:
    return sorted(found, key=lambda refusal: (refusal.path, refusal.rule))


def check_record(record: Mapping[str, Any]) -> list[Refusal]:
    """Every way one record fails the schema or a record rule. Empty means it passes.

    The claim-relative rules -- the ones that decide whether a substitution was
    material -- need the claim, and do not run here. A record that passes this
    check has a coherent shape; whether it supports its claim at its level is
    `check_claim`'s question.
    """
    # A non-object is refused by the schema; the rules read it as empty rather than
    # raising, so a caller always gets refusals back.
    return _sorted(
        [*validate_record(record), *_record_rule_refusals(_dict(record), "$")]
    )


def check_claim(
    claim: Mapping[str, Any],
    *,
    evidence_classes: Sequence[Mapping[str, Any]] | None = None,
) -> list[Refusal]:
    """The same for one claim and every record it holds.

    `evidence_classes` is the register's class vocabulary. Without it a carried
    legacy classification cannot be read, and a real-behaviour claim resting only
    on one is refused with a message that says so.
    """
    classes = (
        {str(_dict(entry).get("classId")): _dict(entry) for entry in evidence_classes}
        if evidence_classes is not None
        else None
    )
    return _sorted(
        [*validate_claim(claim), *_claim_rule_refusals(_dict(claim), "$", classes)]
    )


def check_register(
    document: Mapping[str, Any], *, repo_root: Path | None = None
) -> list[Refusal]:
    """The same for a whole `v1alpha2` document.

    With `repo_root`, every cited path must also exist under it. Without it, the
    existence rule is not applied, which is what lets an illustrative fixture cite
    a record nobody has written.
    """
    return _sorted(
        [*validate_register(document), *_register_refusals(_dict(document), repo_root)]
    )


#: The rules `_register_refusals` enforces inline rather than through a registered
#: function, because they need the whole document.
_REGISTER_RULES: Final = frozenset(
    {
        "a-claim-identifier-is-unique",
        "a-record-identifier-is-unique",
        "a-citation-is-a-plain-repository-path",
        "a-template-is-not-evidence",
        "evidence-is-cited-from-the-evidence-root",
        "a-cited-record-exists",
        "a-legacy-classification-stays-under-its-legacy-ceiling",
    }
)


def unimplemented_rules() -> list[str]:
    """Validator rules the catalogue names and no code enforces. Should be empty."""
    implemented = set(_RECORD_CHECKS) | set(_CLAIM_CHECKS) | _REGISTER_RULES
    return sorted(
        entry.rule_id
        for entry in RULES
        if entry.enforced_by == "validator" and entry.rule_id not in implemented
    )
