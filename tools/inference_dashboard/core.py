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
    A panel reading ``up`` or an ``inferops:scrape_`` recorded series -- by name or
    through a ``__name__`` matcher -- without declaring the ``scrape-reachability``
    signal, or one that declares it under a title using a word from
    :data:`READINESS_WORDS`, which is a list and has a list's limit. Scrape reachability says a process
    answered; a deleted pod has been observed reading ``up`` after it was gone.

``panel-state-contradicts-its-queries``
    A panel whose declared signal the queries under it cannot support: a value panel
    reading a metric nothing emits, a not-emitted panel reading nothing not emitted
    or carrying anything but that metric and its recorded absence,
    a not-answerable panel carrying a query or not saying what would answer it, a
    title that does not say which of those it is, or a zero-filled expression with
    no statement of what its zero means.

``panel-shows-missing-as-a-number``
    A panel with a query and no text for an empty result, or a text that reads as a
    number. An empty panel that shows ``0`` is the failure this dashboard exists to
    prevent.

``panel-reads-a-per-replica-label-without-declaring-it``
    ``instance`` is the pod name and the one unbounded label the collection record
    accepts. A panel may show it only by declaring ``perReplica``. It is found where
    a query names it, a legend shows it, or the result's label set can be derived
    and carries it; a result whose labels cannot be derived statically is covered by
    the suite's check over the evaluated scenarios, not by this rule.

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
from tools.telemetry_correlation.core import (
    SAFE_MESSAGE_CHARACTERS,
    SUBSTITUTE,
    _static_labels,
)
from tools.telemetry_correlation.promql import (
    Binary,
    Expr,
    NumberLiteral,
    Selector,
    walk,
)

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
#:
#: **A list, and so a list's limit.** Independent review renamed a scrape panel
#: "operational" and the first version of this list, which stopped at readiness and
#: health words, accepted it. The list now covers the words a reviewer and the
#: suite could think of, prefixes included -- ``health`` catches ``healthcheck`` --
#: and the suite commits a synonym it still accepts, so the gap stays visible
#: rather than assumed closed. Meaning is not something a regular expression reads.
READINESS_WORDS: Final = re.compile(
    r"\b(ready\w*|readiness|health\w*|avail\w*|up|alive|live\w*|online|"
    r"operational|functional|functioning|responsive|serving|working|ok|okay|"
    r"green|good|normal|status)\b",
    re.IGNORECASE,
)

#: ``up`` is the series Prometheus synthesises per target; every ``inferops:scrape_``
#: recorded series is derived from it.
SCRAPE_SERIES_PREFIX: Final = "inferops:scrape_"
SCRAPE_SERIES: Final = frozenset({"up", "scrape_duration_seconds"})

#: A recorded absence: ``inferops:<what>_absent:<tier>``. The one kind of answerable
#: series a not-emitted panel may carry beside the metric it reports as absent.
RECORDED_ABSENCE: Final = re.compile(r"^inferops:[a-z_]+_absent:[a-z_]+$")

REF_ID: Final = re.compile(r"[A-Z]")
PER_REPLICA_LABEL: Final = "instance"
LEGEND_PLACEHOLDER: Final = re.compile(r"\{\{\s*([^}\s]*)\s*\}\}")
LOOKS_NUMERIC: Final = re.compile(r"^\s*[-+]?(\d|\.\d|nan\b|inf\b)", re.IGNORECASE)

#: A zero-filled expression multiplies a presence vector by zero. It is recognised
#: from the parsed tree, with constant operands folded, so neither spacing nor a
#: spelling such as ``-0`` or ``(1 - 1)`` hides one. Independent review found the
#: first version reading only a bare literal, which ``* -0`` walked straight past.
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


def _constant(node: Expr) -> float | None:
    """The value of a subexpression built only from number literals, or ``None``."""
    if isinstance(node, NumberLiteral):
        return node.value
    if isinstance(node, Binary) and node.operator in {"+", "-", "*", "/"}:
        left, right = _constant(node.left), _constant(node.right)
        if left is None or right is None:
            return None
        if node.operator == "+":
            return left + right
        if node.operator == "-":
            return left - right
        if node.operator == "*":
            return left * right
        return None if right == ZERO else left / right
    return None


def _is_zero_fill(expression: str) -> bool:
    """Whether an expression multiplies something by a constant that folds to zero."""
    try:
        tree = parse(expression)
    except PromQLError:
        return False
    for node in walk(tree):
        if not isinstance(node, Binary) or node.operator != "*":
            continue
        for side in (node.left, node.right):
            if _constant(side) == ZERO:
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


def _series_named(tree: Expr) -> frozenset[str]:
    """Every series name an expression selects, including through ``__name__``."""
    names = set(metrics_read(tree))
    for node in walk(tree):
        if isinstance(node, Selector):
            names.update(
                matcher.value
                for matcher in node.matchers
                if matcher.label == "__name__" and matcher.operator == "="
            )
    return frozenset(names)


def _reads_scrape_signal(expression: str) -> bool:
    try:
        read = _series_named(parse(expression))
    except PromQLError:
        return False
    return any(
        name in SCRAPE_SERIES or name.startswith(SCRAPE_SERIES_PREFIX) for name in read
    )


def _shape(record: Mapping[str, Any]) -> list[Finding]:
    """Refusals for a record whose shape the rules cannot read at all.

    The rules below assume lists of objects. A wrong-typed field used to raise an
    ``AttributeError`` out of the gate instead of a finding -- independent review
    drove ``{"panels": [null]}`` and a string ``queries`` through it -- so the shape
    is checked first, and a record that fails it is refused and read no further.
    """
    findings: list[Finding] = []
    for collection, rule in (
        ("questions", "operational-question-has-no-panel"),
        ("panels", "panel-identifier-is-malformed-or-repeated"),
    ):
        entries = record.get(collection)
        if entries is None:
            continue
        if not isinstance(entries, list) or not all(
            isinstance(entry, Mapping) for entry in entries
        ):
            findings.append(
                Finding(
                    rule=rule,
                    subject=collection,
                    field=collection,
                    message=f"{collection} must be a list of objects",
                )
            )
    panels = record.get("panels")
    if isinstance(panels, list):
        for panel in panels:
            if not isinstance(panel, Mapping):
                continue
            queries = panel.get("queries")
            if queries is None:
                continue
            if not isinstance(queries, list) or not all(
                isinstance(query, Mapping) for query in queries
            ):
                findings.append(
                    Finding(
                        rule="panel-state-contradicts-its-queries",
                        subject=_safe(str(panel.get("panelId", ""))) or "<unnamed>",
                        field="queries",
                        message="queries must be a list of objects",
                    )
                )
    return findings


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
        for query in queries:
            if query.get("answerability") == "not-answerable-nothing-emits":
                continue
            try:
                read = _series_named(parse(str(query.get("expr"))))
            except PromQLError:
                read = frozenset()
            if not read or not all(RECORDED_ABSENCE.match(name) for name in read):
                yield Finding(
                    rule="panel-state-contradicts-its-queries",
                    subject=subject,
                    field=f"queries[{_safe(str(query.get('refId', '?')))}]",
                    message=(
                        "a not-emitted panel carries only the metric that is not "
                        "emitted and the recorded absence of it. A live figure under "
                        "a not-emitted title is the contradiction this refuses"
                    ),
                )
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
            tree = parse(expression)
            named = labels_read(tree)
            # The labels the result can carry, where they can be derived. A bare
            # selector returns every label on the series, `instance` included, and
            # names none of them: independent review showed a table over
            # `inferops_build_info` passing as not per replica. Where the set cannot
            # be derived statically, the suite checks the evaluated results instead.
            carried = _static_labels(tree, profile) or frozenset()
        except PromQLError:
            named = carried = frozenset()
        legend_labels = frozenset(
            LEGEND_PLACEHOLDER.findall(str(query.get("legend") or ""))
        )
        if PER_REPLICA_LABEL in (named | legend_labels | carried) and not per_replica:
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
    shape = _shape(document)
    if shape:
        return sorted(shape, key=lambda f: (f.rule, f.subject, f.field, f.message))
    findings: list[Finding] = [*_identifiers(document), *_questions(document)]
    for panel in document.get("panels") or []:
        if isinstance(panel, Mapping):
            findings.extend(_panel(panel, accepted, permitted))
    return sorted(findings, key=lambda f: (f.rule, f.subject, f.field, f.message))
