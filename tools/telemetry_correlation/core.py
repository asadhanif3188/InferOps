"""The correlation query policy: what a published query may read, group, and join.

This reads the committed query record, parses every expression in it with the
declared PromQL subset, and refuses a query that could not answer the question it
claims to -- because it reads a series nothing in this release produces, groups by a
label no series carries, joins on a key one side cannot have, names a label the
telemetry catalog bars from a metric, or claims an answer a signal nothing emits
cannot give.

**What it establishes stops at the file, exactly as
:mod:`tools.telemetry_collection` does.** No collector, store, dashboard, or alerting
path is selected; nothing scrapes either InferOps endpoint; this chart has never been
installed; and no Prometheus has evaluated any expression here. A query this accepts
is a query that would be well formed against the labels the chart's rendered scrape
configuration would attach. That is a statement about two files.

Six rules, each named for the failure it prevents:

``query-expression-is-outside-the-verified-subset``
    The expression uses a PromQL form this repository cannot read. It is refused
    rather than published unchecked: an expression nothing here can parse is one
    every other rule would be vacuously satisfied by.

``query-names-a-label-the-catalog-bars-from-a-metric``
    A matcher, grouping, or join key names an attribute whose catalog placements
    include neither ``metric-label`` nor ``info-label``. A published query is where a
    forbidden label gets asked for, and a query asking for one is a request to start
    collecting it.

``query-names-a-label-nothing-in-this-release-carries``
    A label that is neither a permitted catalog attribute, nor a target label the
    collection record declares, nor ``le``. It would return an empty result forever,
    and an empty result reads as a healthy quiet system.

``query-reads-a-series-nothing-in-this-release-produces``
    A selector names something that is not a catalog metric, not a native runtime
    series the feasibility record observed, and not a recorded name the chart renders.

``query-claims-an-answer-a-signal-nothing-emits-cannot-give``
    A query declared answerable once collection exists reads a metric the catalog
    marks not emitted. The catalog is the authority on which those are, so a metric
    that starts emitting makes this rule stop firing without an edit here.

``join-matches-on-a-key-one-side-cannot-carry``
    A ``group_left`` or ``group_right`` whose ``on`` set names a label a metric on the
    one side does not have. This is the defect a static reading of a query record
    would miss and an operator would meet as an empty result.

    The rule reads the ``on`` set, so a group modifier written with ``ignoring``
    instead would have slipped past it unchecked. Independent review found exactly
    that, and the parser now refuses that combination outright: a rule that is
    enforced for half a syntax is a rule that reads as enforced and is not.
"""

from __future__ import annotations

import json
import re
from collections.abc import Iterable, Iterator, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final

import yaml

from .evaluate import (
    BUCKET_LABEL,
    NAME_LABEL,
    Series,
    Store,
    evaluate,
    format_vector,
)
from .promql import (
    Aggregation,
    Binary,
    Call,
    Expr,
    PromQLError,
    Selector,
    StringLiteral,
    labels_read,
    metrics_read,
    parse,
    walk,
)

__all__ = [
    "CATALOG_PATH",
    "COLLECTION_RECORD_PATH",
    "FIXTURE_DIR",
    "IDENTIFIER",
    "QUERY_RECORD_PATH",
    "RULE_IDS",
    "SAFE_MESSAGE_CHARACTERS",
    "SUBSTITUTE",
    "Finding",
    "apply_metric_relabel",
    "carriable_labels",
    "check_record",
    "collector_dropped_labels",
    "declared_metric_names",
    "evaluate_scenario",
    "load_fixture",
    "load_query_record",
    "not_emitted_metric_names",
    "observed_native_series",
    "permitted_query_labels",
    "recorded_series_names",
    "rendered_recording_rules",
    "with_recording_rules",
]

REPO_ROOT: Final = Path(__file__).resolve().parents[2]

CATALOG_PATH: Final = REPO_ROOT / "docs/telemetry/telemetry-catalog.v1alpha1.json"
COLLECTION_RECORD_PATH: Final = (
    REPO_ROOT / "docs/telemetry/kubernetes-telemetry-collection.v1alpha1.json"
)
QUERY_RECORD_PATH: Final = (
    REPO_ROOT / "docs/telemetry/telemetry-correlation-queries.v1alpha1.json"
)
FIXTURE_DIR: Final = REPO_ROOT / "tests/telemetry/fixtures/correlation"
RENDERED_DIR: Final = REPO_ROOT / "charts/inferops-llm/ci/rendered"

RULE_IDS: Final[tuple[str, ...]] = (
    "join-matches-on-a-key-one-side-cannot-carry",
    "query-claims-an-answer-a-signal-nothing-emits-cannot-give",
    "query-expression-is-outside-the-verified-subset",
    "query-names-a-label-nothing-in-this-release-carries",
    "query-names-a-label-the-catalog-bars-from-a-metric",
    "query-reads-a-series-nothing-in-this-release-produces",
)

#: Every character a finding message may contain, for the reason
#: :class:`tools.telemetry_collection.Finding` gives: a message names rules, query
#: identifiers, label names, and series names drawn from closed vocabularies, and a
#: checker that echoed an arbitrary expression would be the one place a forbidden
#: value got published -- and an unconstrained echo is also how an escape sequence
#: reaches a terminal or a forged line reaches a log.
SAFE_MESSAGE_CHARACTERS: Final = frozenset(
    "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 .,:;'\"()[]{}=~/_-+?"
)

#: What :func:`_safe` puts where a character outside the set was. It is in the set,
#: it is printable, and it is not a character any identifier here uses -- so a
#: substitution is visible rather than disguised as part of a name.
SUBSTITUTE: Final = "?"

#: The suffixes a Prometheus histogram publishes beside its declared name.
HISTOGRAM_SUFFIXES: Final[tuple[str, ...]] = ("_bucket", "_count", "_sum")

#: The series Prometheus synthesises for every target it scrapes. It is not in the
#: catalog because nothing in this repository emits it, and every missing-scrape rule
#: the chart renders reads it.
SYNTHETIC_SERIES: Final[frozenset[str]] = frozenset({"up", "scrape_duration_seconds"})


@dataclass(frozen=True)
class Finding:
    """One refusal: the rule, the query it was found on, and what is wrong.

    The message may name a rule, a query identifier, a label name, or a series name,
    and never repeats a matcher's *value* or an expression read out of the record.
    :data:`SAFE_MESSAGE_CHARACTERS` bounds what may appear and a test drives the
    checker over deliberately hostile records to prove it.

    That bound covers **every** field, ``subject`` included. It did not at first:
    ``subject`` is the record's own ``queryId``, it was interpolated unfiltered, and
    independent review pointed out that a hostile one would have reached a terminal
    through :meth:`__str__`. :func:`_safe` is what closes it, and the suite now
    drives a hostile identifier as well as a hostile expression.
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


#: The shape a query, refusal, or scenario identifier must have. Kebab-case ASCII
#: and nothing else, so that an identifier can be written into a terminal, a log
#: line, a markdown heading, and a test id without any of them having to escape it.
IDENTIFIER = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def _safe(text: str) -> str:
    """``text`` with every character outside the declared set replaced.

    :class:`Finding` promises its *message* never carries a value out of the record.
    Independent review found the promise did not extend to its *subject*, which is
    the record's own ``queryId`` and was interpolated unfiltered into
    :meth:`Finding.__str__` and from there into stdout -- so a hostile identifier
    could have carried an escape sequence to a terminal or forged a line in a log.
    Every identifier in the committed record is already kebab-case, and
    :data:`IDENTIFIER` is asserted over all of them by the suite; this is the second
    line, for a caller passing a query of its own.
    """
    return "".join(
        character if character in SAFE_MESSAGE_CHARACTERS else SUBSTITUTE
        for character in text
    )


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _prometheus_form(attribute_name: str) -> str:
    return attribute_name.replace(".", "_")


def load_query_record() -> dict[str, Any]:
    """The committed correlation query record."""
    record: dict[str, Any] = _load(QUERY_RECORD_PATH)
    return record


# --------------------------------------------------------------------------
# What the release produces, derived from the accepted records
# --------------------------------------------------------------------------


def declared_metric_names() -> frozenset[str]:
    """Every metric name the telemetry catalog declares, emitted or not."""
    return frozenset(metric["name"] for metric in _load(CATALOG_PATH)["metrics"])


def not_emitted_metric_names() -> frozenset[str]:
    """Every catalog metric nothing currently emits."""
    return frozenset(
        metric["name"]
        for metric in _load(CATALOG_PATH)["metrics"]
        if metric["emission"] != "emitted"
    )


def observed_native_series() -> frozenset[str]:
    """Every ``llamacpp:`` series the runtime feasibility record actually observed."""
    native = _load(CATALOG_PATH)["runtimeNativeSeries"]
    groups: Sequence[Mapping[str, Any]] = (
        native if isinstance(native, list) else [native]
    )
    return frozenset(
        entry["seriesName"] for group in groups for entry in group["series"]
    )


def forbidden_metric_labels() -> frozenset[str]:
    """Every label the catalog bars from a metric, in Prometheus form.

    Derived from the catalog on every run, exactly as the chart's drop list is, so
    that one placement decision reaches the emitter, the collector, and the query
    vocabulary without three edits.
    """
    return frozenset(
        _prometheus_form(attribute["name"])
        for attribute in _load(CATALOG_PATH)["attributes"]
        if "metric-label" not in attribute["placements"]
        and "info-label" not in attribute["placements"]
    )


def permitted_query_labels() -> frozenset[str]:
    """Every label a published query may name.

    Three sources and no fourth: an attribute the catalog permits on a metric or an
    identity series; a target label the collection record says the collector
    attaches; and ``le``, which is Prometheus's own and is what makes a histogram a
    distribution rather than a set of counters.
    """
    catalog = _load(CATALOG_PATH)
    permitted = {
        _prometheus_form(attribute["name"])
        for attribute in catalog["attributes"]
        if "metric-label" in attribute["placements"]
        or "info-label" in attribute["placements"]
    }
    permitted.update(
        row["labelName"] for row in _load(COLLECTION_RECORD_PATH)["targetLabels"]
    )
    permitted.add(BUCKET_LABEL)
    return frozenset(permitted)


def _metric_rows() -> dict[str, Mapping[str, Any]]:
    return {metric["name"]: metric for metric in _load(CATALOG_PATH)["metrics"]}


def _attribute_names_by_id() -> dict[str, str]:
    return {
        attribute["attributeId"]: _prometheus_form(attribute["name"])
        for attribute in _load(CATALOG_PATH)["attributes"]
    }


def _target_labels_by_job_suffix() -> dict[str, frozenset[str]]:
    record = _load(COLLECTION_RECORD_PATH)
    return {
        job["jobNameSuffix"]: frozenset(job["attachedTargetLabels"]) | {"job"}
        for job in record["jobs"]
    }


def _base_name(series_name: str) -> str:
    """The catalog name behind an exposed series name.

    ``inferops_inference_request_duration_seconds_bucket`` is the histogram's bucket
    series and ``inferops_inference_request_duration_seconds`` is the row that
    declares it. The catalog names the instrument; a query reads the exposition.

    A suffix is stripped only when what is left is a metric the catalog actually
    declares. Stripping unconditionally would silently mis-map a future metric whose
    own name ended in ``_count`` or ``_sum`` onto a base that does not exist -- a
    trap independent review pointed out, and one that costs a set lookup to close.
    """
    declared = declared_metric_names()
    if series_name in declared:
        return series_name
    for suffix in HISTOGRAM_SUFFIXES:
        if series_name.endswith(suffix) and series_name[: -len(suffix)] in declared:
            return series_name[: -len(suffix)]
    return series_name


def recorded_series_names(profile: str = "real") -> frozenset[str]:
    """Every ``inferops:`` name the chart's rendered recording rules publish."""
    return frozenset(rule["record"] for _, rule in rendered_recording_rules(profile))


def rendered_recording_rules(
    profile: str = "real",
) -> list[tuple[str, dict[str, Any]]]:
    """Every recording rule in a committed render, as ``(group name, rule)`` pairs.

    Read from the render rather than from the record, because the render is what a
    collector would be given and the record is a description of it.
    """
    documents = [
        document
        for document in yaml.safe_load_all(
            (RENDERED_DIR / f"{profile}.expected.yaml").read_text(encoding="utf-8")
        )
        if document
    ]
    rules: list[tuple[str, dict[str, Any]]] = []
    for document in documents:
        if not isinstance(document, Mapping):
            continue
        metadata = document.get("metadata")
        labels = metadata.get("labels") if isinstance(metadata, Mapping) else None
        if not isinstance(labels, Mapping):
            continue
        if (
            labels.get("app.kubernetes.io/component")
            != "telemetry-scrape-configuration"
        ):
            continue
        data = document.get("data")
        if not isinstance(data, Mapping):
            continue
        parsed = yaml.safe_load(data["recording-rules.yaml"])
        for group in parsed["groups"]:
            for rule in group["rules"]:
                rules.append((group["name"], rule))
    return rules


def collector_dropped_labels(profile: str = "real") -> frozenset[str]:
    """Every label the rendered ``labeldrop`` rules remove, read as an alternation.

    The regex is read the way :mod:`tools.telemetry_collection` reads it -- as the
    alternation the chart writes -- rather than executed. Running a pattern read out
    of a manifest against a name list would be deciding what is dropped by running
    the input this is supposed to be checking.
    """
    documents = [
        document
        for document in yaml.safe_load_all(
            (RENDERED_DIR / f"{profile}.expected.yaml").read_text(encoding="utf-8")
        )
        if document
    ]
    dropped: set[str] = set()
    for document in documents:
        if not isinstance(document, Mapping):
            continue
        metadata = document.get("metadata")
        labels = metadata.get("labels") if isinstance(metadata, Mapping) else None
        if not isinstance(labels, Mapping):
            continue
        if (
            labels.get("app.kubernetes.io/component")
            != "telemetry-scrape-configuration"
        ):
            continue
        data = document.get("data")
        if not isinstance(data, Mapping):
            continue
        for job in yaml.safe_load(data["scrape-config.yaml"])["scrape_configs"]:
            for rule in job.get("metric_relabel_configs") or []:
                if rule.get("action") != "labeldrop":
                    continue
                pattern = rule.get("regex")
                if isinstance(pattern, str):
                    dropped.update(pattern.strip("()").split("|"))
    return frozenset(dropped)


def carriable_labels(series_name: str, profile: str = "real") -> frozenset[str] | None:
    """Every label a series of this name can carry, or ``None`` when it is not known.

    ``None`` is a real answer and not a failure: a recorded series whose expression
    uses a form :func:`_static_labels` does not model has an unknown label set, and a
    rule that guessed would refuse a correct query.
    """
    metrics = _metric_rows()
    attributes = _attribute_names_by_id()
    jobs = _target_labels_by_job_suffix()
    base = _base_name(series_name)
    if base in metrics:
        row = metrics[base]
        own = {attributes[label] for label in row["labels"]}
        if series_name.endswith("_bucket"):
            own.add(BUCKET_LABEL)
        return frozenset(own | jobs.get("platform-api", frozenset()))
    if series_name in observed_native_series():
        return jobs.get("serving-runtime", frozenset())
    if series_name in SYNTHETIC_SERIES:
        # A synthesised series carries whatever the relabelling attached to its
        # target, which differs between the two jobs, so this is the union.
        return frozenset().union(*jobs.values()) if jobs else frozenset()
    for _, rule in rendered_recording_rules(profile):
        if rule.get("record") == series_name:
            try:
                return _static_labels(parse(rule["expr"]), profile)
            except PromQLError:
                return None
    return None


def _static_labels(node: Expr, profile: str) -> frozenset[str] | None:
    """The label set an expression's result can carry, without evaluating it.

    Handled: an aggregation with ``by``, ``absent`` over a selector, ``label_replace``
    over a known inner set, the set operators, an explicit ``on`` join, and a plain
    selector. Anything else returns ``None``.
    """
    if isinstance(node, Selector):
        if node.name is None:
            return None
        return carriable_labels(node.name, profile)
    if isinstance(node, Aggregation):
        if node.without:
            return None
        return frozenset(node.grouping)
    if isinstance(node, Call):
        if node.function == "absent":
            argument = node.arguments[0]
            if isinstance(argument, Selector):
                return frozenset(
                    matcher.label
                    for matcher in argument.matchers
                    if matcher.operator == "="
                )
            return None
        if node.function in {"rate", "increase"}:
            return _static_labels(node.arguments[0], profile)
        if node.function == "label_replace":
            inner = _static_labels(node.arguments[0], profile)
            destination = node.arguments[1]
            if inner is None or not isinstance(destination, StringLiteral):
                return None
            return inner | {destination.value}
        return None
    if isinstance(node, Binary):
        left = _static_labels(node.left, profile)
        right = _static_labels(node.right, profile)
        if node.operator == "or":
            # An element of an `or` carries one side's labels or the other's, never
            # their union, so this is an upper bound rather than an exact set. It is
            # only ever read to decide whether a join key is carriable, where an
            # upper bound can miss a refusal and can never invent one. The one rule
            # this is used on today -- the runtime token mapping -- has identical
            # label sets on both branches, so the bound is exact there.
            return None if left is None or right is None else left | right
        if node.operator in {"and", "unless"}:
            return left
        if node.matching.on is not None:
            return frozenset(node.matching.on) | frozenset(node.matching.include)
        # A one-to-one match with no `on` keeps whatever both sides share, which is
        # not decidable from the names alone. Unknown is the honest answer.
        return None
    return None


# --------------------------------------------------------------------------
# The rules
# --------------------------------------------------------------------------


def _known_series(profile: str) -> frozenset[str]:
    names: set[str] = set(SYNTHETIC_SERIES)
    for metric in declared_metric_names():
        names.add(metric)
        names.update(metric + suffix for suffix in HISTOGRAM_SUFFIXES)
    names.update(observed_native_series())
    names.update(recorded_series_names(profile))
    return frozenset(names)


def _check_query(
    query: Mapping[str, Any],
    forbidden: frozenset[str],
    permitted: frozenset[str],
    known: frozenset[str],
    not_emitted: frozenset[str],
    profile: str,
) -> Iterator[Finding]:
    subject = _safe(str(query.get("queryId", "<unnamed query>")))
    expression = query.get("expr")
    if not isinstance(expression, str):
        return
    try:
        tree = parse(expression)
    except PromQLError as error:
        yield Finding(
            rule="query-expression-is-outside-the-verified-subset",
            subject=subject,
            field="expr",
            message=(
                f"this expression cannot be read by the declared PromQL subset "
                f"({error.args[0] if error.args else 'no reason given'}). It is "
                "refused rather than published unchecked: an expression nothing "
                "here can parse is one every other rule would be vacuously "
                "satisfied by"
            ),
        )
        return

    named = labels_read(tree)
    for label in sorted(named & forbidden):
        yield Finding(
            rule="query-names-a-label-the-catalog-bars-from-a-metric",
            subject=subject,
            field="expr",
            message=(
                f"this query names {label!r}, which the telemetry catalog permits "
                "in neither a metric label nor an identity label. A published query "
                "is where a forbidden label gets asked for, and the collector drops "
                "it on the way in, so the query would return nothing forever"
            ),
        )
    for label in sorted(named - permitted - forbidden):
        yield Finding(
            rule="query-names-a-label-nothing-in-this-release-carries",
            subject=subject,
            field="expr",
            message=(
                f"this query names {label!r}, which is neither an attribute the "
                "catalog permits on a series nor a target label the collection "
                "record says the collector attaches. It would return an empty "
                "result forever, and an empty result reads as a healthy quiet system"
            ),
        )

    read = metrics_read(tree)
    for series in sorted(read - known):
        yield Finding(
            rule="query-reads-a-series-nothing-in-this-release-produces",
            subject=subject,
            field="expr",
            message=(
                f"this query reads {series!r}, which is not a metric the catalog "
                "declares, not a native runtime series the feasibility record "
                "observed, and not a recorded name the chart renders"
            ),
        )

    if query.get("answerability") == "answerable-once-collected":
        for series in sorted(read):
            if _base_name(series) in not_emitted:
                yield Finding(
                    rule="query-claims-an-answer-a-signal-nothing-emits-cannot-give",
                    subject=subject,
                    field="answerability",
                    message=(
                        f"this query is declared answerable once collection exists "
                        f"and reads {series!r}, which the catalog marks not emitted. "
                        "Nothing would put a sample in the store, so the answer "
                        "would be empty rather than late"
                    ),
                )

    yield from _check_joins(tree, subject, profile)


def _check_joins(tree: Expr, subject: str, profile: str) -> Iterator[Finding]:
    for node in walk(tree):
        if not isinstance(node, Binary) or node.matching.card is None:
            continue
        keys = frozenset(node.matching.on or ())
        if not keys:
            continue
        one = node.right if node.matching.card == "group_left" else node.left
        for series in sorted(metrics_read(one)):
            carriable = carriable_labels(series, profile)
            if carriable is None:
                continue
            for label in sorted(keys - carriable):
                yield Finding(
                    rule="join-matches-on-a-key-one-side-cannot-carry",
                    subject=subject,
                    field="expr",
                    message=(
                        f"the join matches on {label!r}, which {series!r} on the one "
                        "side of the match cannot carry. Prometheus finds no "
                        "counterpart for any element, so the whole query returns "
                        "nothing -- the failure an operator meets as an empty panel"
                    ),
                )


def check_record(record: Mapping[str, Any] | None = None) -> list[Finding]:
    """Every refusal in the committed query record, sorted so output is stable."""
    document = dict(record) if record is not None else load_query_record()
    forbidden = forbidden_metric_labels()
    permitted = permitted_query_labels()
    not_emitted = not_emitted_metric_names()
    findings: list[Finding] = []
    for query in document.get("queries") or []:
        if not isinstance(query, Mapping):
            continue
        profile = "real" if "real" in (query.get("profiles") or ["real"]) else "mock"
        findings.extend(
            _check_query(
                query,
                forbidden,
                permitted,
                _known_series(profile),
                not_emitted,
                profile,
            )
        )
    return sorted(findings, key=lambda f: (f.rule, f.subject, f.field, f.message))


def check_query(query: Mapping[str, Any], profile: str = "real") -> list[Finding]:
    """Every refusal on one query, for the negative catalogue and for ad-hoc use."""
    return sorted(
        _check_query(
            query,
            forbidden_metric_labels(),
            permitted_query_labels(),
            _known_series(profile),
            not_emitted_metric_names(),
            profile,
        ),
        key=lambda f: (f.rule, f.subject, f.field, f.message),
    )


# --------------------------------------------------------------------------
# Fixtures, and the collector steps a fixture has to go through
# --------------------------------------------------------------------------


def load_fixture(path: Path) -> dict[str, Any]:
    """One scenario fixture: a synthetic store and what it is meant to show."""
    document: dict[str, Any] = yaml.safe_load(path.read_text(encoding="utf-8"))
    return document


def _fixture_store(document: Mapping[str, Any]) -> Store:
    series: list[Series] = []
    for entry in document["series"]:
        labels = dict(entry.get("labels") or {})
        labels[NAME_LABEL] = entry["name"]
        points = tuple((float(t), float(v)) for t, v in entry["points"])
        series.append(Series(tuple(sorted(labels.items())), points))
    return Store(tuple(series), float(document["evaluationInstant"]))


def apply_metric_relabel(store: Store, dropped: Iterable[str]) -> Store:
    """The store as the collector's ``metric_relabel_configs`` would leave it.

    Only ``labeldrop`` is modelled, because that is the only metric-relabel action
    the chart renders. A drop that would leave two series sharing one label set is
    refused rather than silently collapsed: Prometheus reports a duplicate and keeps
    one, and a fixture that depended on which one it kept would be a fixture nobody
    could reason about.
    """
    removed = frozenset(dropped)
    seen: dict[tuple[tuple[str, str], ...], None] = {}
    kept: list[Series] = []
    for entry in store.series:
        labels = tuple(
            (key, value) for key, value in entry.labels if key not in removed
        )
        if labels in seen:
            raise ValueError(
                "dropping the collector's barred labels would leave two series "
                "sharing one label set; write the fixture so that it does not"
            )
        seen[labels] = None
        kept.append(Series(labels, entry.points))
    return Store(tuple(kept), store.evaluation_instant)


def with_recording_rules(store: Store, profile: str = "real") -> Store:
    """The store with every series the chart's rendered recording rules would add.

    Each rule is evaluated at every instant the fixture carries a sample for, in the
    order the render lists them, so that a rule reading an earlier rule's output sees
    the history it would have had. That is the same order a collector evaluates a
    group in; what it is not is a claim that a collector has.
    """
    instants = sorted({point[0] for entry in store.series for point in entry.points})
    accumulated: dict[tuple[str, str], list[tuple[float, float]]] = {}
    rules = rendered_recording_rules(profile)

    def recorded() -> tuple[Series, ...]:
        return tuple(
            Series(tuple(sorted(json.loads(labels).items())), tuple(points))
            for (_, labels), points in accumulated.items()
        )

    for instant in instants:
        for _, rule in rules:
            working = Store(store.series + recorded(), instant)
            for sample in evaluate(working, parse(rule["expr"])):
                labels = dict(sample.labels)
                labels[NAME_LABEL] = rule["record"]
                key = (rule["record"], json.dumps(labels, sort_keys=True))
                accumulated.setdefault(key, []).append((instant, sample.value))
    return Store(store.series + recorded(), store.evaluation_instant)


def evaluate_scenario(
    document: Mapping[str, Any],
    queries: Sequence[Mapping[str, Any]],
) -> dict[str, list[str]]:
    """Every query's result over one scenario, as stable formatted lines.

    A query whose declared profiles do not include the scenario's is not evaluated
    and is absent from the result, rather than present and empty: "this query does
    not exist under this profile" and "this query returned nothing" are different
    answers and an evidence record that spelled them the same would be worthless.
    """
    profile = str(document["profile"])
    store = _fixture_store(document)
    if document.get("applyCollectorRelabel", True):
        store = apply_metric_relabel(store, collector_dropped_labels(profile))
    store = with_recording_rules(store, profile)
    results: dict[str, list[str]] = {}
    for query in queries:
        if query.get("expr") is None:
            continue
        if profile not in (query.get("profiles") or ["mock", "real"]):
            continue
        results[str(query["queryId"])] = format_vector(
            evaluate(store, parse(str(query["expr"])))
        )
    return results
