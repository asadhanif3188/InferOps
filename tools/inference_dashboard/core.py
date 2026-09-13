"""The dashboard policy: what a panel may read, and what it must show without a number.

This reads the committed dashboard record and refuses a panel that would mislead the
operator it is for. Every expression in it is first held to the correlation query
policy in :mod:`tools.telemetry_correlation` -- the same parser, the same catalog
derivation, the same refusals -- so a dashboard cannot be where a label the catalog
bars, or a series nothing emits, gets asked for. On top of that it adds the rules a
single query cannot break and a panel can:

``panel-query-refused-by-the-correlation-policy``
    An expression one of the correlation rules refuses. The finding names that rule.

``panel-query-drifted-from-the-accepted-query``
    A query that says it is an accepted correlation query and is not the same
    expression, or does not carry the same answerability class. A dashboard that
    quietly edited an accepted query would publish an unchecked one under a checked
    name.

``scrape-signal-presented-as-readiness``
    A panel reading ``up`` or an ``inferops:scrape_`` recorded series without
    declaring the ``scrape-reachability`` signal, or one that declares it under a
    title using a readiness or health word. Scrape reachability says a process
    answered; a deleted pod has been observed reading ``up`` after it was gone.

``panel-state-contradicts-its-queries``
    A panel whose declared signal the queries under it cannot support: a value panel
    reading a metric nothing emits, a not-emitted panel reading nothing not emitted,
    a not-answerable panel carrying a query or not saying what would answer it, a
    title that does not say which of those it is, or a zero-filled expression with
    no statement of what its zero means.

``panel-shows-missing-as-a-number``
    A panel with a query and no text for an empty result, or a text that reads as a
    number. An empty panel that shows ``0`` is the failure this dashboard exists to
    prevent.

``panel-reads-a-per-replica-label-without-declaring-it``
    ``instance`` is the pod name and the one unbounded label the collection record
    accepts. A panel may show it only by declaring ``perReplica``.

``legend-names-a-label-outside-the-query-vocabulary``
    A legend placeholder naming a label no published query may name.

``operational-question-has-no-panel``
    A declared question with nothing answering it, or a panel naming a question that
    is not declared.

``panel-identifier-is-malformed-or-repeated``
    A panel or question identifier that is not kebab-case, or appears twice.

**What it establishes stops at the file.** It starts no Grafana and no Prometheus. A
panel this accepts is a panel whose expressions would be well formed against the
labels the chart's rendered scrape configuration would attach, and whose empty state
says something other than zero.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Final

from tools.telemetry_correlation import (
    IDENTIFIER,
    PromQLError,
    check_query,
    evaluate_scenario,
    labels_read,
    load_query_record,
    metrics_read,
    parse,
    permitted_query_labels,
)
from tools.telemetry_correlation.core import SAFE_MESSAGE_CHARACTERS, SUBSTITUTE
from tools.telemetry_correlation.promql import Binary, NumberLiteral, walk

__all__ = [
    "DASHBOARD_RECORD_PATH",
    "RENDER_PATH",
    "RULE_IDS",
    "Finding",
    "check_dashboard",
    "evaluate_dashboard",
    "load_dashboard_record",
    "panel_queries",
]

REPO_ROOT: Final = Path(__file__).resolve().parents[2]

DASHBOARD_RECORD_PATH: Final = (
    REPO_ROOT / "docs/telemetry/inference-operations-dashboard.v1alpha1.json"
)
RENDER_PATH: Final = REPO_ROOT / "deploy/grafana/inferops-inference-operations.json"

RULE_IDS: Final[tuple[str, ...]] = (
    "legend-names-a-label-outside-the-query-vocabulary",
    "operational-question-has-no-panel",
    "panel-identifier-is-malformed-or-repeated",
    "panel-query-drifted-from-the-accepted-query",
    "panel-query-refused-by-the-correlation-policy",
    "panel-reads-a-per-replica-label-without-declaring-it",
    "panel-shows-missing-as-a-number",
    "panel-state-contradicts-its-queries",
    "scrape-signal-presented-as-readiness",
)

SIGNALS: Final = frozenset(
    {"value", "scrape-reachability", "not-emitted", "not-answerable"}
)
KINDS: Final = frozenset({"stat", "timeseries", "table", "text"})

#: Words a scrape-reachability title may not use. Each is a claim about the process
#: being able to serve, which a scrape cannot make.
READINESS_WORDS: Final = re.compile(
    r"\b(ready|readiness|health|healthy|available|availability|up|alive|live)\b",
    re.IGNORECASE,
)

#: ``up`` is the series Prometheus synthesises per target; every ``inferops:scrape_``
#: recorded series is derived from it.
SCRAPE_SERIES_PREFIX: Final = "inferops:scrape_"
SCRAPE_SERIES: Final = frozenset({"up", "scrape_duration_seconds"})

REF_ID: Final = re.compile(r"[A-Z]")
PER_REPLICA_LABEL: Final = "instance"
LEGEND_PLACEHOLDER: Final = re.compile(r"\{\{\s*([^}\s]*)\s*\}\}")
LOOKS_NUMERIC: Final = re.compile(r"^\s*[-+]?(\d|\.\d|nan\b|inf\b)", re.IGNORECASE)

#: A zero-filled expression multiplies a presence vector by zero. It is recognised
#: from the parsed tree rather than from the text, so spacing cannot hide one.
ZERO: Final = 0.0


@dataclass(frozen=True)
class Finding:
    """One refusal: the rule, the panel it was found on, and what is wrong.

    The same character bound as :class:`tools.telemetry_correlation.Finding` applies
    to every field, for the same reason: a checker that echoed a hostile identifier
    or expression would be the one place such a value reached a terminal.
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


def load_dashboard_record(path: Path = DASHBOARD_RECORD_PATH) -> dict[str, Any]:
    """The committed dashboard record."""
    record: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return record


def panel_queries(record: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Every panel query as a correlation-shaped query, identified ``panel/refId``.

    That shape is what lets :func:`tools.telemetry_correlation.evaluate_scenario`
    evaluate a panel exactly as it evaluates an accepted query, profile filter
    included, rather than through a second evaluator path.
    """
    queries: list[dict[str, Any]] = []
    for panel in record.get("panels") or []:
        for query in panel.get("queries") or []:
            queries.append(
                {
                    "queryId": f"{panel.get('panelId')}/{query.get('refId')}",
                    "expr": query.get("expr"),
                    "answerability": query.get("answerability"),
                    "profiles": query.get("profiles"),
                }
            )
    return queries


def evaluate_dashboard(
    record: Mapping[str, Any], fixture: Mapping[str, Any]
) -> dict[str, list[str]]:
    """Every panel query's result over one scenario fixture, keyed ``panel/refId``."""
    return evaluate_scenario(fixture, panel_queries(record))


# --------------------------------------------------------------------------
# The rules
# --------------------------------------------------------------------------


def _is_zero_fill(expression: str) -> bool:
    """Whether an expression multiplies something by the literal zero."""
    try:
        tree = parse(expression)
    except PromQLError:
        return False
    for node in walk(tree):
        if not isinstance(node, Binary) or node.operator != "*":
            continue
        for side in (node.left, node.right):
            if isinstance(side, NumberLiteral) and side.value == ZERO:
                return True
    return False


@lru_cache(maxsize=512)
def _policy_refusals(
    expression: str, answerability: str, profile: str
) -> tuple[tuple[str, str], ...]:
    """The correlation policy's refusals of one expression, as (rule, message) pairs.

    Cached because the policy re-derives the catalog and re-reads the committed render
    for every expression, and the files it reads do not change during a process. The
    key is the whole input the policy reads from the panel, so a cached answer is the
    answer.
    """
    return tuple(
        (finding.rule, finding.message)
        for finding in check_query(
            {"queryId": "panel", "expr": expression, "answerability": answerability},
            profile,
        )
    )


def _reads_scrape_signal(expression: str) -> bool:
    try:
        read = metrics_read(parse(expression))
    except PromQLError:
        return False
    return any(
        name in SCRAPE_SERIES or name.startswith(SCRAPE_SERIES_PREFIX) for name in read
    )


def _identifiers(record: Mapping[str, Any]) -> Iterator[Finding]:
    for collection, key in (("questions", "questionId"), ("panels", "panelId")):
        seen: set[str] = set()
        for entry in record.get(collection) or []:
            identifier = str(entry.get(key, ""))
            subject = _safe(identifier) or "<unnamed>"
            if not IDENTIFIER.match(identifier):
                yield Finding(
                    rule="panel-identifier-is-malformed-or-repeated",
                    subject=subject,
                    field=key,
                    message="an identifier must be kebab-case ASCII and nothing else",
                )
            if identifier in seen:
                yield Finding(
                    rule="panel-identifier-is-malformed-or-repeated",
                    subject=subject,
                    field=key,
                    message=(
                        "this identifier appears twice, so a finding or a rendered "
                        "panel naming it could mean either"
                    ),
                )
            seen.add(identifier)
    for panel in record.get("panels") or []:
        references = [
            str(query.get("refId", "")) for query in panel.get("queries") or []
        ]
        subject = _safe(str(panel.get("panelId", ""))) or "<unnamed>"
        if any(not REF_ID.fullmatch(reference) for reference in references) or len(
            set(references)
        ) != len(references):
            yield Finding(
                rule="panel-identifier-is-malformed-or-repeated",
                subject=subject,
                field="refId",
                message="a query reference is one capital letter, unique in its panel",
            )


def _questions(record: Mapping[str, Any]) -> Iterator[Finding]:
    declared = [str(q.get("questionId")) for q in record.get("questions") or []]
    answered = {str(p.get("questionId")) for p in record.get("panels") or []}
    for question in declared:
        if question not in answered:
            yield Finding(
                rule="operational-question-has-no-panel",
                subject=_safe(question),
                field="questionId",
                message=(
                    "no panel answers this question. A question missing from a "
                    "dashboard is a question somebody answers with a query they wrote "
                    "by hand"
                ),
            )
    for panel in record.get("panels") or []:
        if str(panel.get("questionId")) not in declared:
            yield Finding(
                rule="operational-question-has-no-panel",
                subject=_safe(str(panel.get("panelId"))),
                field="questionId",
                message="this panel names a question the record does not declare",
            )


def _panel(
    panel: Mapping[str, Any],
    accepted: Mapping[str, Mapping[str, Any]],
    permitted: frozenset[str],
) -> Iterator[Finding]:
    subject = _safe(str(panel.get("panelId", "<unnamed panel>")))
    signal = panel.get("signal")
    kind = panel.get("kind")
    title = str(panel.get("title") or "")
    queries: Sequence[Mapping[str, Any]] = panel.get("queries") or []

    if signal not in SIGNALS or kind not in KINDS:
        yield Finding(
            rule="panel-state-contradicts-its-queries",
            subject=subject,
            field="signal",
            message="the signal or the panel kind is outside the declared vocabulary",
        )
        return

    # --- not-answerable: a text panel, no query, and what would answer it.
    if signal == "not-answerable":
        if queries or kind != "text":
            yield Finding(
                rule="panel-state-contradicts-its-queries",
                subject=subject,
                field="queries",
                message=(
                    "a not-answerable panel is a text panel with no query. One with a "
                    "query is an empty panel, and an empty panel reads as health"
                ),
            )
        if not str(panel.get("wouldRequire") or "").strip():
            yield Finding(
                rule="panel-state-contradicts-its-queries",
                subject=subject,
                field="wouldRequire",
                message="a not-answerable panel says what would have to exist first",
            )
        if "not answerable" not in title.lower():
            yield Finding(
                rule="panel-state-contradicts-its-queries",
                subject=subject,
                field="title",
                message="a not-answerable panel says so in its title",
            )
        return

    if not queries or kind == "text":
        yield Finding(
            rule="panel-state-contradicts-its-queries",
            subject=subject,
            field="queries",
            message="a panel that is not a not-answerable text panel carries a query",
        )
        return

    when_missing = str(panel.get("whenMissing") or "")
    if not when_missing.strip() or LOOKS_NUMERIC.match(when_missing):
        yield Finding(
            rule="panel-shows-missing-as-a-number",
            subject=subject,
            field="whenMissing",
            message=(
                "an empty result needs text that cannot be read as a number, or the "
                "panel shows missing telemetry the way it shows zero"
            ),
        )

    classes = {str(query.get("answerability")) for query in queries}
    if signal == "not-emitted":
        if "not-answerable-nothing-emits" not in classes:
            yield Finding(
                rule="panel-state-contradicts-its-queries",
                subject=subject,
                field="signal",
                message=(
                    "a not-emitted panel reads the metric that is not emitted, so the "
                    "panel is empty for the reason it says"
                ),
            )
        if "not emitted" not in title.lower():
            yield Finding(
                rule="panel-state-contradicts-its-queries",
                subject=subject,
                field="title",
                message="a not-emitted panel says so in its title",
            )
    elif "not-answerable-nothing-emits" in classes:
        yield Finding(
            rule="panel-state-contradicts-its-queries",
            subject=subject,
            field="signal",
            message=(
                "this panel reads a metric nothing emits and does not declare the "
                "not-emitted signal, so its empty result would read as a quiet system"
            ),
        )

    per_replica = panel.get("perReplica") is True
    for query in queries:
        expression = query.get("expr")
        ref = _safe(str(query.get("refId", "?")))
        where = f"queries[{ref}]"
        if not isinstance(expression, str):
            yield Finding(
                rule="panel-state-contradicts-its-queries",
                subject=subject,
                field=where,
                message="a panel query carries an expression",
            )
            continue

        profile = "real" if "real" in (query.get("profiles") or ["real"]) else "mock"
        for rule, message in _policy_refusals(
            expression, str(query.get("answerability")), profile
        ):
            yield Finding(
                rule="panel-query-refused-by-the-correlation-policy",
                subject=subject,
                field=where,
                message=f"refused by {rule}: {message}",
            )

        reference = query.get("queryRef")
        if reference is not None:
            original = accepted.get(str(reference))
            if (
                original is None
                or original.get("expr") != expression
                or original.get("answerability") != query.get("answerability")
            ):
                yield Finding(
                    rule="panel-query-drifted-from-the-accepted-query",
                    subject=subject,
                    field=where,
                    message=(
                        "this query names an accepted correlation query and is not "
                        "that query's expression and answerability, verbatim"
                    ),
                )

        if _reads_scrape_signal(expression) and signal != "scrape-reachability":
            yield Finding(
                rule="scrape-signal-presented-as-readiness",
                subject=subject,
                field=where,
                message=(
                    "this panel reads a scrape signal and does not declare "
                    "scrape-reachability, so it can be read as the process being able "
                    "to serve"
                ),
            )

        if _is_zero_fill(expression) and not str(panel.get("zeroMeans") or "").strip():
            yield Finding(
                rule="panel-state-contradicts-its-queries",
                subject=subject,
                field="zeroMeans",
                message=(
                    "this expression fills a zero, and a zero nobody defined is the "
                    "one this dashboard exists to keep apart from missing"
                ),
            )

        try:
            named = labels_read(parse(expression))
        except PromQLError:
            named = frozenset()
        legend_labels = frozenset(
            LEGEND_PLACEHOLDER.findall(str(query.get("legend") or ""))
        )
        if PER_REPLICA_LABEL in (named | legend_labels) and not per_replica:
            yield Finding(
                rule="panel-reads-a-per-replica-label-without-declaring-it",
                subject=subject,
                field=where,
                message=(
                    "instance is the pod name and unbounded over a store's retention. "
                    "A panel shows it only by declaring perReplica"
                ),
            )
        for label in sorted(legend_labels - permitted):
            yield Finding(
                rule="legend-names-a-label-outside-the-query-vocabulary",
                subject=subject,
                field=where,
                message=(
                    f"the legend names {_safe(label)!r}, which no published query may "
                    "name, so it would render empty or render a label the catalog bars"
                ),
            )

    if signal == "scrape-reachability":
        if "scrape" not in title.lower() or READINESS_WORDS.search(title):
            yield Finding(
                rule="scrape-signal-presented-as-readiness",
                subject=subject,
                field="title",
                message=(
                    "a scrape-reachability title says scrape and uses no readiness or "
                    "health word"
                ),
            )
        if not any(
            isinstance(query.get("expr"), str)
            and _reads_scrape_signal(str(query["expr"]))
            for query in queries
        ):
            yield Finding(
                rule="panel-state-contradicts-its-queries",
                subject=subject,
                field="signal",
                message="a scrape-reachability panel reads a scrape signal",
            )


def check_dashboard(record: Mapping[str, Any] | None = None) -> list[Finding]:
    """Every refusal in the dashboard record, sorted so output is stable."""
    document = dict(record) if record is not None else load_dashboard_record()
    accepted = {
        str(query["queryId"]): query for query in load_query_record()["queries"]
    }
    permitted = permitted_query_labels()
    findings: list[Finding] = [*_identifiers(document), *_questions(document)]
    for panel in document.get("panels") or []:
        if isinstance(panel, Mapping):
            findings.extend(_panel(panel, accepted, permitted))
    return sorted(findings, key=lambda f: (f.rule, f.subject, f.field, f.message))
