"""The alert policy: what may be alerted on, and what an alert owes its operator.

This reads the committed alert record and refuses an alert that would wake somebody
for nothing, or stay silent for something. Every expression in it is first held to
the correlation query policy in :mod:`tools.telemetry_correlation` -- the same
parser, the same catalog derivation, the same refusals -- so an alert cannot be
where a series nothing emits, or a label the catalog bars, gets read. On top of that
it adds the rules a query does not have to satisfy and an alert does:

``alert-expression-refused-by-the-correlation-policy``
    An expression one of the correlation rules refuses. The finding names that rule.

``alert-condition-is-not-a-comparison``
    An expression whose top level is not a comparison, or a boolean composition of
    comparisons. A bare selector fires on the existence of a sample, which is the
    difference between "the platform is refusing callers" and "the platform is
    running".

``alert-threshold-has-no-declared-source``
    A threshold that is a number somebody liked. Every alert names a
    ``thresholdBasis`` from the record's own closed list, every basis in that list
    says where such a number comes from, and ``measurement`` is not one of them: a
    figure this project measured on one host is not a threshold other installations
    inherit. The rationale must name the configuration key, the bucket boundary, or
    the zero it is derived from.

``scrape-signal-presented-as-workload-health``
    An alert reading ``up`` or an ``inferops:scrape_`` recorded series without
    declaring the ``scrape-reachability`` signal, or one that declares it and still
    describes a workload in its name, summary, or user impact. Scrape reachability
    has been observed wrong in both directions -- a deleted pod reading ``up`` for
    roughly fifty seconds, and a live process whose model was loading reading ``0``
    for six minutes -- so it may raise a collection alert and never a serving one.

``alert-names-a-job``
    A matcher on ``job``. Job names are release-qualified, so an alert naming one
    works in exactly one installation and is silent in every other.

``alert-has-no-operator-action``
    A missing owner, severity, condition, user impact, operator action, or runbook.
    An alert nobody owns and nobody can act on is a notification.

``alert-runbook-does-not-resolve``
    A runbook reference whose file is not committed, or whose fragment is not a
    heading in that file. A runbook link is the one field of an alert that is read
    at three in the morning, and a link check that stopped at the filename would
    pass for a section that was renamed.

``alert-is-not-validated``
    An alert with no scenario where it fires, no scenario where it is silent, or an
    expectation naming a scenario the record does not declare. An alert nothing has
    ever been shown to fire on is a hypothesis.

``alert-window-is-shorter-than-two-evaluations``
    A ``for`` shorter than twice the rule evaluation interval. One missed scrape,
    one restarted collector, or one slow endpoint must not be enough.

``alert-window-is-shorter-than-its-range-window``
    A ``for`` shorter than the longest range window the expression reads. One
    scrape interval's worth of trouble keeps a five-minute rate above zero for five
    minutes, so an alert with a shorter window pages for a single event that has
    already stopped. Every rate alert here failed this in an earlier draft.

``alert-identifier-is-malformed-or-repeated``
    An alert identifier that is not kebab-case, a name that is not the Prometheus
    ``CamelCase`` convention, or either one appearing twice.

``alert-record-is-malformed``
    A record whose ``alerts`` is not a list of objects, or is empty. This checker is
    a gate, and a gate that answered a malformed record with a traceback would be
    read as a gate that passed it.

**What it establishes stops at the file.** It starts no Prometheus and no
Alertmanager. An alert this accepts is an alert whose expression is well formed
against the labels the chart's rendered scrape configuration would attach, whose
threshold has a source outside this project's own measurements, and which fired and
stayed silent where the committed scenarios say it should. No receiver, routing
tree, or on-call rotation is selected, so an alert this accepts is an alert that has
never woken anybody.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

from tools.telemetry_correlation import (
    IDENTIFIER,
    SAFE_MESSAGE_CHARACTERS,
    PromQLError,
    Store,
    apply_metric_relabel,
    check_query,
    collector_dropped_labels,
    evaluate,
    format_vector,
    metrics_read,
    parse,
    with_recording_rules,
)
from tools.telemetry_correlation.core import SUBSTITUTE, _fixture_store
from tools.telemetry_correlation.promql import Binary, Expr, Selector, walk

__all__ = [
    "ALERT_RECORD_PATH",
    "FIXTURE_DIR",
    "RENDER_PATHS",
    "RULE_IDS",
    "Finding",
    "alert_queries",
    "check_alerts",
    "evaluate_alerts",
    "firing_instants",
    "load_alert_record",
    "runbook_anchors",
]

REPO_ROOT: Final = Path(__file__).resolve().parents[2]

ALERT_RECORD_PATH: Final = REPO_ROOT / "docs/telemetry/inference-alerts.v1alpha1.json"
FIXTURE_DIR: Final = REPO_ROOT / "tests/telemetry/fixtures/alerts"
RENDER_PATHS: Final[dict[str, Path]] = {
    "mock": REPO_ROOT / "deploy/prometheus/inferops-inference-alerts.mock.yaml",
    "real": REPO_ROOT / "deploy/prometheus/inferops-inference-alerts.real.yaml",
}

RULE_IDS: Final[tuple[str, ...]] = (
    "alert-condition-is-not-a-comparison",
    "alert-expression-refused-by-the-correlation-policy",
    "alert-has-no-operator-action",
    "alert-identifier-is-malformed-or-repeated",
    "alert-is-not-validated",
    "alert-names-a-job",
    "alert-record-is-malformed",
    "alert-runbook-does-not-resolve",
    "alert-threshold-has-no-declared-source",
    "alert-window-is-shorter-than-its-range-window",
    "alert-window-is-shorter-than-two-evaluations",
    "scrape-signal-presented-as-workload-health",
)

#: The two signals an alert may declare. ``workload`` is a claim about the platform
#: serving; ``scrape-reachability`` is a claim about the collector reaching a
#: process, and the record keeps them apart because the two have been observed
#: disagreeing in both directions.
SIGNALS: Final = frozenset({"workload", "scrape-reachability"})

#: Words a scrape-reachability alert may not use about itself. The same list the
#: dashboard policy holds a scrape panel to, and it carries the same limit: it is a
#: list, and meaning is not something a regular expression reads.
WORKLOAD_WORDS: Final = re.compile(
    r"\b(ready\w*|readiness|health\w*|avail\w*|alive|live\w*|online|"
    r"operational|functional|functioning|responsive|serving|serve\w*|working|"
    r"inference|model|callers?|requests?)\b",
    re.IGNORECASE,
)

SCRAPE_SERIES_PREFIX: Final = "inferops:scrape_"
SCRAPE_SERIES: Final = frozenset({"up", "scrape_duration_seconds"})

#: The Prometheus alert-name convention. A name is what an operator reads in a
#: notification and what a silence is written against, so it is checked rather than
#: left to whoever adds the next one.
ALERT_NAME: Final = re.compile(r"^InferOps[A-Z][A-Za-z0-9]*$")

JOB_LABEL: Final = "job"

#: Comparison operators. An alert condition is one of these at the top, or a
#: boolean composition whose every branch is.
COMPARISONS: Final = frozenset({"==", "!=", ">", "<", ">=", "<="})
BOOLEAN_OPERATORS: Final = frozenset({"and", "or", "unless"})

REQUIRED_TEXT_FIELDS: Final[tuple[str, ...]] = (
    "condition",
    "userImpact",
    "operatorAction",
    "emptyMeans",
    "whatItCannotSee",
)

#: A ``thresholdBasis`` an alert may never name, whatever the record's own list
#: says. A number this project measured on one host, on one day, is the one kind of
#: threshold that reads as universal and is not.
FORBIDDEN_BASIS: Final = "measurement"

#: ``docs/....md#a-fragment``.
RUNBOOK_REF: Final = re.compile(
    r"^(?P<path>[A-Za-z0-9_./-]+\.md)#(?P<fragment>[a-z0-9-]+)$"
)

HEADING: Final = re.compile(r"^#{1,6}\s+(?P<text>.+?)\s*$")
FENCE: Final = re.compile(r"^[ \t]*(```|~~~)")


@dataclass(frozen=True)
class Finding:
    """One refusal: the rule, the alert it was found on, and what is wrong.

    The same character bound as :class:`tools.telemetry_correlation.Finding`
    applies to every field, for the same reason: a checker that echoed a hostile
    identifier or expression would be the one place such a value reached a
    terminal.
    """

    rule: str
    subject: str
    field: str
    message: str

    def as_dict(self) -> dict[str, str]:
        return {
            "rule": self.rule,
            "subject": self.subject,
            "field": self.field,
            "message": self.message,
        }

    def __str__(self) -> str:
        return f"{self.rule}  {self.subject}  {self.field}  {self.message}"


def _safe(text: str) -> str:
    return "".join(
        character if character in SAFE_MESSAGE_CHARACTERS else SUBSTITUTE
        for character in text
    )


def load_alert_record(path: Path = ALERT_RECORD_PATH) -> dict[str, Any]:
    """The committed alert record."""
    record: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return record


def alert_queries(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Every alert expression in the shape the correlation policy reads.

    That shape is what lets the correlation checker apply to an alert exactly as it
    applies to a published query, rather than through a second derivation of the
    catalog that could drift from the first.
    """
    return [
        {
            "queryId": alert.get("alertId"),
            "expr": alert.get("expr"),
            "answerability": alert.get("answerability", "answerable-once-collected"),
            "profiles": alert.get("profiles"),
        }
        for alert in record.get("alerts") or []
    ]


# --------------------------------------------------------------------------
# Evaluating an alert, including the window it has to hold across
# --------------------------------------------------------------------------


def _store(fixture: Mapping[str, Any]) -> Store:
    """One fixture as a store, relabelled and with the chart's recording rules.

    The same two steps ``evaluate_scenario`` performs, kept here because an alert is
    evaluated at many instants and that function evaluates at one.
    """
    profile = str(fixture["profile"])
    store = _fixture_store(fixture)
    if fixture.get("applyCollectorRelabel", True):
        store = apply_metric_relabel(store, collector_dropped_labels(profile))
    return with_recording_rules(store, profile)


def _instants(fixture: Mapping[str, Any]) -> list[float]:
    """Every instant this fixture is evaluated at, in order.

    A fixture declares the step its samples sit on and the first instant an
    expression may be asked at -- the point from which every range window inside an
    expression is full. Before that, a rate reads a window that starts before the
    fixture does, which is an artefact of the fixture rather than of the system.
    """
    step = float(fixture["stepSeconds"])
    first = float(fixture["firstEvaluationInstant"])
    last = float(fixture["evaluationInstant"])
    instants: list[float] = []
    instant = first
    while instant <= last + 1e-9:
        instants.append(instant)
        instant += step
    return instants


def firing_instants(
    alert: Mapping[str, Any], fixture: Mapping[str, Any]
) -> list[float]:
    """Every instant at which this alert would be firing over this fixture.

    An alert is *pending* from the first instant its expression returns anything and
    *firing* once it has returned something at every instant across ``for``. This
    reproduces that with the fixture's own step: the condition has to hold at every
    instant in the closed window ``[T - for, T]`` the fixture carries.

    **The step is the fixture's and not a collector's.** Where a fixture steps more
    coarsely than the 30-second rule evaluation a release configures, this
    establishes that the condition held at the instants the fixture carries and not
    at every instant a collector would have asked at.
    """
    profile = str(fixture["profile"])
    if profile not in (alert.get("profiles") or ["mock", "real"]):
        return []
    expression = parse(str(alert["expr"]))
    store = _store(fixture)
    instants = _instants(fixture)
    step = float(fixture["stepSeconds"])
    window = float(alert.get("forSeconds") or 0)
    needed = round(window / step)

    holding: list[bool] = []
    firing: list[float] = []
    for instant in instants:
        vector = evaluate(Store(store.series, instant), expression)
        holding.append(bool(vector))
        if len(holding) > needed and all(holding[-(needed + 1) :]):
            firing.append(instant)
    return firing


def evaluate_alerts(
    record: Mapping[str, Any], fixture: Mapping[str, Any]
) -> dict[str, list[str]]:
    """Every alert's result over one fixture at its final instant, as stable lines.

    The lines are what the expression returns, not whether the alert fires: the
    firing question is :func:`firing_instants`, which needs the whole window. An
    alert whose declared profiles exclude the fixture's is absent rather than empty,
    because "this alert does not exist under this profile" and "this alert returned
    nothing" are different answers.
    """
    profile = str(fixture["profile"])
    store = _store(fixture)
    instants = _instants(fixture)
    at = Store(store.series, instants[-1]) if instants else store
    results: dict[str, list[str]] = {}
    for alert in record.get("alerts") or []:
        if profile not in (alert.get("profiles") or ["mock", "real"]):
            continue
        results[str(alert["alertId"])] = format_vector(
            evaluate(at, parse(str(alert["expr"])))
        )
    return results


# --------------------------------------------------------------------------
# The rules
# --------------------------------------------------------------------------


def _is_condition(node: Expr) -> bool:
    """Whether this expression filters by a comparison rather than by existence."""
    if not isinstance(node, Binary):
        return False
    if node.operator in COMPARISONS:
        return True
    if node.operator in BOOLEAN_OPERATORS:
        return _is_condition(node.left) and _is_condition(node.right)
    return False


def _job_matchers(expression: str) -> bool:
    """Whether any selector in this expression matches on ``job``."""
    for node in walk(parse(expression)):
        if not isinstance(node, Selector):
            continue
        if any(matcher.label == JOB_LABEL for matcher in node.matchers):
            return True
    return False


def _reads_scrape_signal(expression: str) -> bool:
    names = metrics_read(parse(expression))
    return any(
        name in SCRAPE_SERIES or name.startswith(SCRAPE_SERIES_PREFIX) for name in names
    )


def runbook_anchors(path: Path) -> frozenset[str]:
    """Every fragment a reader can link to in one Markdown document.

    GitHub's own slug: the heading lowercased, everything but a word character,
    a space, or a hyphen removed, and the spaces turned into hyphens. Headings
    inside a fenced block are not headings.
    """
    anchors: set[str] = set()
    fenced = False
    for line in path.read_text(encoding="utf-8").splitlines():
        if FENCE.match(line):
            fenced = not fenced
            continue
        if fenced:
            continue
        match = HEADING.match(line)
        if match is None:
            continue
        text = match.group("text")
        text = re.sub(r"`([^`]*)`", r"\1", text)
        text = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", text)
        slug = re.sub(r"[^\w\s-]", "", text).strip().lower()
        anchors.add(re.sub(r"\s+", "-", slug))
    return frozenset(anchors)


def _check_identity(
    alert: Mapping[str, Any], seen_ids: set[str], seen_names: set[str]
) -> Iterator[Finding]:
    subject = _safe(str(alert.get("alertId", "<unnamed alert>")))
    identifier = alert.get("alertId")
    if not isinstance(identifier, str) or not IDENTIFIER.match(identifier):
        yield Finding(
            "alert-identifier-is-malformed-or-repeated",
            subject,
            "alertId",
            "an alert identifier is kebab-case",
        )
    elif identifier in seen_ids:
        yield Finding(
            "alert-identifier-is-malformed-or-repeated",
            subject,
            "alertId",
            "this identifier appears twice",
        )
    else:
        seen_ids.add(identifier)

    name = alert.get("name")
    if not isinstance(name, str) or not ALERT_NAME.match(name):
        yield Finding(
            "alert-identifier-is-malformed-or-repeated",
            subject,
            "name",
            "an alert name is InferOps followed by CamelCase",
        )
    elif name in seen_names:
        yield Finding(
            "alert-identifier-is-malformed-or-repeated",
            subject,
            "name",
            "this name appears twice",
        )
    else:
        seen_names.add(name)


def _check_action(
    alert: Mapping[str, Any],
    owners: frozenset[str],
    severities: frozenset[str],
) -> Iterator[Finding]:
    subject = _safe(str(alert.get("alertId", "<unnamed alert>")))
    if alert.get("owner") not in owners:
        yield Finding(
            "alert-has-no-operator-action",
            subject,
            "owner",
            "an alert names an owner the record declares",
        )
    if alert.get("severity") not in severities:
        yield Finding(
            "alert-has-no-operator-action",
            subject,
            "severity",
            "an alert names a severity the record declares",
        )
    if alert.get("signal") not in SIGNALS:
        yield Finding(
            "alert-has-no-operator-action",
            subject,
            "signal",
            f"an alert declares one of {sorted(SIGNALS)}",
        )
    for field in REQUIRED_TEXT_FIELDS:
        value = alert.get(field)
        if not isinstance(value, str) or not value.strip():
            yield Finding(
                "alert-has-no-operator-action",
                subject,
                field,
                "an alert says this in words an operator can act on",
            )


def _check_runbook(alert: Mapping[str, Any]) -> Iterator[Finding]:
    subject = _safe(str(alert.get("alertId", "<unnamed alert>")))
    reference = alert.get("runbookRef")
    if not isinstance(reference, str) or not reference.strip():
        yield Finding(
            "alert-has-no-operator-action",
            subject,
            "runbookRef",
            "an alert links to the section that says what to do",
        )
        return
    match = RUNBOOK_REF.match(reference)
    if match is None:
        yield Finding(
            "alert-runbook-does-not-resolve",
            subject,
            "runbookRef",
            "a runbook reference is a committed .md path and a heading fragment",
        )
        return
    path = REPO_ROOT / match.group("path")
    if not path.is_file():
        yield Finding(
            "alert-runbook-does-not-resolve",
            subject,
            "runbookRef",
            f"no such document: {_safe(match.group('path'))}",
        )
        return
    if match.group("fragment") not in runbook_anchors(path):
        yield Finding(
            "alert-runbook-does-not-resolve",
            subject,
            "runbookRef",
            f"no such heading: {_safe(match.group('fragment'))}",
        )


def _check_threshold(
    alert: Mapping[str, Any], bases: frozenset[str]
) -> Iterator[Finding]:
    subject = _safe(str(alert.get("alertId", "<unnamed alert>")))
    basis = alert.get("thresholdBasis")
    if basis == FORBIDDEN_BASIS:
        yield Finding(
            "alert-threshold-has-no-declared-source",
            subject,
            "thresholdBasis",
            "a figure measured on one host is not a threshold anything inherits",
        )
    elif basis not in bases:
        yield Finding(
            "alert-threshold-has-no-declared-source",
            subject,
            "thresholdBasis",
            "an alert names a threshold basis the record declares",
        )
    rationale = alert.get("thresholdRationale")
    if not isinstance(rationale, str) or not rationale.strip():
        yield Finding(
            "alert-threshold-has-no-declared-source",
            subject,
            "thresholdRationale",
            "an alert says where its number comes from",
        )


def _check_expression(alert: Mapping[str, Any], profile: str) -> Iterator[Finding]:
    subject = _safe(str(alert.get("alertId", "<unnamed alert>")))
    expression = alert.get("expr")
    if not isinstance(expression, str) or not expression.strip():
        yield Finding(
            "alert-condition-is-not-a-comparison",
            subject,
            "expr",
            "an alert carries an expression; a deferred one belongs in deferredAlerts",
        )
        return
    for finding in check_query(
        {
            "queryId": alert.get("alertId"),
            "expr": expression,
            "answerability": alert.get("answerability", "answerable-once-collected"),
            "profiles": alert.get("profiles"),
        },
        profile,
    ):
        yield Finding(
            "alert-expression-refused-by-the-correlation-policy",
            subject,
            "expr",
            f"{finding.rule}: {finding.message}",
        )
    try:
        node = parse(expression)
    except PromQLError:
        return
    if not _is_condition(node):
        yield Finding(
            "alert-condition-is-not-a-comparison",
            subject,
            "expr",
            "an alert condition compares; a selector fires on a sample existing",
        )
    if _job_matchers(expression):
        yield Finding(
            "alert-names-a-job",
            subject,
            "expr",
            "job names are release-qualified; an alert reads a recorded name",
        )


def _check_scrape_signal(alert: Mapping[str, Any]) -> Iterator[Finding]:
    subject = _safe(str(alert.get("alertId", "<unnamed alert>")))
    expression = alert.get("expr")
    if not isinstance(expression, str):
        return
    try:
        reads_scrape = _reads_scrape_signal(expression)
    except PromQLError:
        return
    declared = alert.get("signal") == "scrape-reachability"
    if reads_scrape and not declared:
        yield Finding(
            "scrape-signal-presented-as-workload-health",
            subject,
            "signal",
            "this reads a scrape signal and claims to see the workload",
        )
    if not declared:
        return
    if not reads_scrape:
        yield Finding(
            "scrape-signal-presented-as-workload-health",
            subject,
            "signal",
            "this declares scrape reachability and reads no scrape signal",
        )
    for field in ("name", "condition", "userImpact"):
        value = alert.get(field)
        if isinstance(value, str) and WORKLOAD_WORDS.search(value):
            yield Finding(
                "scrape-signal-presented-as-workload-health",
                subject,
                field,
                "a scrape alert may not describe itself as a workload alert",
            )


def _longest_range(expression: str) -> int:
    """The longest range window any selector in this expression reads, in seconds."""
    return max(
        (
            node.range_seconds
            for node in walk(parse(expression))
            if isinstance(node, Selector) and node.range_seconds is not None
        ),
        default=0,
    )


def _check_window(alert: Mapping[str, Any], interval: float) -> Iterator[Finding]:
    subject = _safe(str(alert.get("alertId", "<unnamed alert>")))
    window = alert.get("forSeconds")
    if not isinstance(window, int) or window <= 0:
        yield Finding(
            "alert-window-is-shorter-than-two-evaluations",
            subject,
            "forSeconds",
            "an alert declares the window its condition holds across",
        )
        return
    if window < 2 * interval:
        yield Finding(
            "alert-window-is-shorter-than-two-evaluations",
            subject,
            "forSeconds",
            f"one missed evaluation would fire this; the interval is {interval:g}s",
        )
    expression = alert.get("expr")
    if not isinstance(expression, str):
        return
    try:
        longest = _longest_range(expression)
    except PromQLError:
        return
    if window < longest:
        yield Finding(
            "alert-window-is-shorter-than-its-range-window",
            subject,
            "forSeconds",
            f"one sample keeps a {longest:g}s window true for {longest:g}s",
        )


def _check_validation(
    alert: Mapping[str, Any], scenarios: Mapping[str, str]
) -> Iterator[Finding]:
    subject = _safe(str(alert.get("alertId", "<unnamed alert>")))
    expectations = alert.get("scenarioExpectations")
    if not isinstance(expectations, Mapping) or not expectations:
        yield Finding(
            "alert-is-not-validated",
            subject,
            "scenarioExpectations",
            "an alert says what it does over every declared scenario",
        )
        return
    unknown = sorted(set(expectations) - set(scenarios))
    if unknown:
        yield Finding(
            "alert-is-not-validated",
            subject,
            "scenarioExpectations",
            f"no such scenario: {_safe(unknown[0])}",
        )
    profiles = set(alert.get("profiles") or ["mock", "real"])
    applicable = {
        scenario for scenario, profile in scenarios.items() if profile in profiles
    }
    missing = sorted(applicable - set(expectations))
    if missing:
        yield Finding(
            "alert-is-not-validated",
            subject,
            "scenarioExpectations",
            f"no expectation for {_safe(missing[0])}",
        )
    values = {expectations[key] for key in expectations if key in applicable}
    if "fires" not in values:
        yield Finding(
            "alert-is-not-validated",
            subject,
            "scenarioExpectations",
            "an alert nothing fires it is a hypothesis",
        )
    if "silent" not in values:
        yield Finding(
            "alert-is-not-validated",
            subject,
            "scenarioExpectations",
            "an alert nothing keeps silent has not been shown to discriminate",
        )
    if not values <= {"fires", "silent"}:
        yield Finding(
            "alert-is-not-validated",
            subject,
            "scenarioExpectations",
            "an expectation is 'fires' or 'silent'",
        )


def _declared(record: Mapping[str, Any], key: str, field: str) -> frozenset[str]:
    entries = record.get(key)
    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
        return frozenset()
    return frozenset(
        str(entry[field])
        for entry in entries
        if isinstance(entry, Mapping) and field in entry
    )


def check_alerts(record: Mapping[str, Any], profile: str = "real") -> list[Finding]:
    """Every refusal on the whole record, sorted so two runs read the same."""
    owners = _declared(record, "owners", "ownerId")
    severities = _declared(record, "severities", "severityId")
    bases = _declared(record, "thresholdBases", "basisId")
    scenarios = {
        str(scenario["scenarioId"]): str(scenario.get("profile"))
        for scenario in record.get("scenarios") or []
        if isinstance(scenario, Mapping) and "scenarioId" in scenario
    }
    interval = float(
        (record.get("evaluation") or {}).get("ruleEvaluationIntervalSeconds") or 0
    )

    findings: list[Finding] = []
    seen_ids: set[str] = set()
    seen_names: set[str] = set()
    entries = record.get("alerts")
    if not isinstance(entries, Sequence) or isinstance(entries, (str, bytes)):
        entries = []
    if not entries:
        findings.append(
            Finding(
                "alert-record-is-malformed",
                "<record>",
                "alerts",
                "an alert record carries a non-empty list of alerts",
            )
        )
    for alert in entries:
        if not isinstance(alert, Mapping):
            findings.append(
                Finding(
                    "alert-record-is-malformed",
                    "<not an alert>",
                    "alerts",
                    "an entry in alerts is an object",
                )
            )
            continue
        findings.extend(_check_identity(alert, seen_ids, seen_names))
        findings.extend(_check_action(alert, owners, severities))
        findings.extend(_check_runbook(alert))
        findings.extend(_check_threshold(alert, bases))
        findings.extend(_check_expression(alert, profile))
        findings.extend(_check_scrape_signal(alert))
        findings.extend(_check_window(alert, interval))
        findings.extend(_check_validation(alert, scenarios))
    return sorted(findings, key=lambda f: (f.rule, f.subject, f.field, f.message))
