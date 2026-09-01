"""An in-process metric registry, and the exposition a scraper reads off it.

`ADR 0006` `D8` selected no SDK, exporter, collector, or store, and this module is
written so that instrumenting the API did not have to select one either. A pull
endpoint needs no exporter: the process holds its own series and renders them in
the Prometheus text exposition format when ``/metrics`` is scraped. What is still
unselected stays unselected -- nothing here ships a sample anywhere, and no
collector, store, dashboard, or alert exists.

**The registry enforces the placement rule rather than trusting it.**
:meth:`MetricRegistry.declare` refuses a label name that is not in
:data:`~inferops.telemetry.names.LABEL_SAFE_ATTRIBUTES`, so a correlation
identifier, a request identifier, a workload version, a tenant identifier, or a
measured duration cannot become a label by being passed to a constructor. That is
the catalog's ``no-request-identifier-is-a-metric-label`` and
``no-unbounded-value-is-a-metric-label`` moved from a document into the one place
a series is created. It also refuses a label **value** outside
:data:`LABEL_VALUE`, because a label value carrying a newline or a quote is an
exposition-format injection rather than a label.

**Every series a metric can produce is bounded by its declaration.** A metric
declares its label names once; recording against a different set of names is a
:class:`~inferops.domain.serving.errors.InvalidValueError` rather than a new
series. There is no dynamic label discovery here, on purpose: dynamic labels are
how a cardinality budget is spent without anyone deciding to.

**Nothing here is a benchmark.** The catalog's ``no-figure-here-is-a-published-benchmark``
still holds: these series exist to operate the platform, and V1 publishes no
figure derived from them.
"""

from __future__ import annotations

import math
import threading
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from re import compile as _compile
from types import MappingProxyType

from ..domain.serving.errors import InvalidValueError
from . import names

#: The content type of the Prometheus text exposition format. The version
#: parameter is part of the media type rather than decoration; a scraper reads it
#: to decide how to parse what follows.
EXPOSITION_CONTENT_TYPE = "text/plain; version=0.0.4; charset=utf-8"

#: What a label value may contain. Bounded in length and restricted in alphabet
#: for one reason: a value is written into the exposition between quotes, and a
#: newline, a quote, or a backslash there is an injected series rather than a
#: label. Values are validated rather than escaped, because a value that needed
#: escaping is a value that came from somewhere it should not have.
LABEL_VALUE = _compile(r"^[A-Za-z0-9][A-Za-z0-9._:/@+-]{0,127}$")

#: What an unknown identity is published as. Prometheus has no absent label, so
#: an identity a deployment did not state is the empty string, which every store
#: and query treats as "not set". Inventing a value would be worse: a
#: ``service.version`` of ``unknown`` is a version that sorts, groups, and reads
#: like a release nobody shipped.
UNKNOWN = ""

#: The bucket boundaries of the request-duration histogram, in seconds, and the
#: implicit ``+Inf`` bucket makes twelve -- which is the count the catalog
#: declares and recomputes its series budget from.
#:
#: They are chosen for the runtime `ADR 0002` selected, whose measured floor on
#: the trial host is tens of seconds on CPU, not for a hosted accelerator. A
#: default bucket set topping out at ten seconds would put every real request in
#: the overflow bucket and report a latency distribution with one bar.
REQUEST_DURATION_BUCKETS: tuple[float, ...] = (
    0.5,
    1.0,
    2.5,
    5.0,
    10.0,
    20.0,
    30.0,
    45.0,
    60.0,
    120.0,
    300.0,
)

#: The instrument kinds this registry renders, spelled as the exposition format
#: spells them.
COUNTER = "counter"
GAUGE = "gauge"
HISTOGRAM = "histogram"

INSTRUMENTS: tuple[str, ...] = (COUNTER, GAUGE, HISTOGRAM)


def _check_label_names(metric: str, labels: Sequence[str]) -> tuple[str, ...]:
    """Refuse a label the catalog does not permit on an operational metric."""
    seen: set[str] = set()
    for label in labels:
        if label in seen:
            raise InvalidValueError(f"{metric}: label {label!r} is declared twice")
        seen.add(label)
        if label in names.NEVER_A_LABEL:
            raise InvalidValueError(
                f"{metric}: {label!r} may not be a metric label; the telemetry "
                f"catalog places it in logs, traces, or an identity metric only"
            )
        if label not in names.LABEL_SAFE_ATTRIBUTES:
            raise InvalidValueError(
                f"{metric}: {label!r} is not an attribute the telemetry catalog "
                f"permits as an operational metric label"
            )
    return tuple(labels)


def _check_label_value(metric: str, label: str, value: str) -> str:
    if value == UNKNOWN:
        return value
    if LABEL_VALUE.match(value) is None:
        raise InvalidValueError(
            f"{metric}: the value of {label!r} is not a well-formed label value"
        )
    return value


def _exposition_name(label: str) -> str:
    """The exposition spelling of an attribute name.

    Attribute names are dotted, as the OpenTelemetry conventions spell them, and
    the Prometheus text format admits only ``[a-zA-Z0-9_]`` in a label name. The
    translation is mechanical and total -- every dot becomes an underscore -- so
    a reader holding one name can compute the other, and the catalog stays the
    single place the names are decided.
    """
    return label.replace(".", "_")


@dataclass(frozen=True, slots=True)
class MetricSpec:
    """One metric's declaration: everything about it that does not change.

    Attributes:
        name: The metric name, copied from the catalog.
        instrument: ``counter``, ``gauge``, or ``histogram``.
        unit: The unit the catalog declares, for the reader of this file.
        help_text: The ``HELP`` line. It is the question the catalog says the
            metric answers, so a scraper's own documentation is the accepted
            record's words rather than a second description.
        labels: The label names, in the order the exposition writes them.
        buckets: A histogram's finite bucket boundaries, and ``None`` otherwise.
        identity: Whether this is the identity metric, which emits exactly one
            series per process whatever its labels say. Identity attributes are
            permitted as its labels and nowhere else.
    """

    name: str
    instrument: str
    unit: str
    help_text: str
    labels: tuple[str, ...] = ()
    buckets: tuple[float, ...] | None = None
    identity: bool = False

    def __post_init__(self) -> None:
        if not self.name:
            raise InvalidValueError("a metric name must not be empty")
        if self.instrument not in INSTRUMENTS:
            raise InvalidValueError(
                f"{self.name}: instrument must be one of {sorted(INSTRUMENTS)}"
            )
        if not self.help_text.strip():
            raise InvalidValueError(
                f"{self.name}: a metric states the question it answers"
            )
        if (self.buckets is not None) != (self.instrument == HISTOGRAM):
            raise InvalidValueError(
                f"{self.name}: a histogram declares buckets and nothing else does"
            )
        if self.buckets is not None and list(self.buckets) != sorted(self.buckets):
            raise InvalidValueError(f"{self.name}: bucket boundaries must ascend")
        if not self.identity:
            _check_label_names(self.name, self.labels)


@dataclass
class _Series:
    """The samples one label combination holds."""

    value: float = 0.0
    count: int = 0
    total: float = 0.0
    buckets: list[int] = field(default_factory=list)


class Metric:
    """One declared metric and every series recorded against it."""

    def __init__(self, spec: MetricSpec, lock: threading.Lock) -> None:
        self._spec = spec
        self._lock = lock
        self._series: dict[tuple[str, ...], _Series] = {}

    @property
    def spec(self) -> MetricSpec:
        return self._spec

    @property
    def series_count(self) -> int:
        """How many label combinations this metric currently holds."""
        return len(self._series)

    def _key(self, labels: Mapping[str, str]) -> tuple[str, ...]:
        declared = self._spec.labels
        if set(labels) != set(declared):
            raise InvalidValueError(
                f"{self._spec.name}: expected labels {sorted(declared)}, "
                f"got {sorted(labels)}"
            )
        return tuple(
            _check_label_value(self._spec.name, name, labels[name]) for name in declared
        )

    def _slot(self, labels: Mapping[str, str]) -> _Series:
        key = self._key(labels)
        found = self._series.get(key)
        if found is None:
            found = _Series(
                buckets=[0] * (len(self._spec.buckets or ()) + 1)
                if self._spec.buckets is not None
                else []
            )
            self._series[key] = found
        return found

    def add(
        self, amount: float = 1.0, labels: Mapping[str, str] = MappingProxyType({})
    ) -> None:
        """Increment a counter. A counter never decreases, so a negative is a defect."""
        if self._spec.instrument != COUNTER:
            raise InvalidValueError(f"{self._spec.name}: not a counter")
        if amount < 0:
            raise InvalidValueError(f"{self._spec.name}: a counter cannot decrease")
        with self._lock:
            self._slot(labels).value += amount

    def sample(
        self, value: float, labels: Mapping[str, str] = MappingProxyType({})
    ) -> None:
        """Set a counter from a source that is already cumulative.

        A process's own processor clock is monotonic for the life of the process,
        so adding a delta on every scrape would count whatever elapsed between two
        scrapes twice. Setting it is the correct reading and a decrease is still a
        defect, because a counter that went backwards is a counter that was reset
        by something nobody told the store about.
        """
        if self._spec.instrument != COUNTER:
            raise InvalidValueError(f"{self._spec.name}: not a counter")
        with self._lock:
            slot = self._slot(labels)
            if value < slot.value:
                raise InvalidValueError(f"{self._spec.name}: a counter cannot decrease")
            slot.value = value

    def set(
        self, value: float, labels: Mapping[str, str] = MappingProxyType({})
    ) -> None:
        """Set a gauge to a measured value.

        On an identity metric this **replaces** whatever series was there rather
        than adding one beside it. That is what ``one-per-process`` means: the
        identity labels are resolved in two steps -- what configuration stated,
        then what the adapter reported -- and a metric that kept both would
        publish two contradictory identities for one process, which is worse than
        publishing none.
        """
        if self._spec.instrument != GAUGE:
            raise InvalidValueError(f"{self._spec.name}: not a gauge")
        with self._lock:
            if self._spec.identity:
                self._series.clear()
            self._slot(labels).value = value

    def adjust(
        self, delta: float, labels: Mapping[str, str] = MappingProxyType({})
    ) -> None:
        """Move a gauge by a delta, for the in-flight count."""
        if self._spec.instrument != GAUGE:
            raise InvalidValueError(f"{self._spec.name}: not a gauge")
        with self._lock:
            self._slot(labels).value += delta

    def observe(
        self, value: float, labels: Mapping[str, str] = MappingProxyType({})
    ) -> None:
        """Record one observation into a histogram."""
        if self._spec.instrument != HISTOGRAM:
            raise InvalidValueError(f"{self._spec.name}: not a histogram")
        if math.isnan(value):
            raise InvalidValueError(f"{self._spec.name}: not a measurement")
        boundaries = self._spec.buckets or ()
        with self._lock:
            slot = self._slot(labels)
            slot.count += 1
            slot.total += value
            for index, boundary in enumerate(boundaries):
                if value <= boundary:
                    slot.buckets[index] += 1
            slot.buckets[len(boundaries)] += 1

    def samples(self) -> list[tuple[dict[str, str], _Series]]:
        """Every series, with its labels, in a stable order."""
        with self._lock:
            rows = sorted(self._series.items())
        return [
            (dict(zip(self._spec.labels, key, strict=True)), row) for key, row in rows
        ]


class MetricRegistry:
    """Every metric one process holds, and the exposition it renders.

    The registry is the process's own store. It is not a client of anything: no
    sample leaves it except through a scrape of ``/metrics``, which is what makes
    instrumenting the API possible without selecting the exporter and collector
    `ADR 0006` `D8` deliberately left open.
    """

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._metrics: dict[str, Metric] = {}

    def declare(self, spec: MetricSpec) -> Metric:
        """Register one metric. A name declared twice is a defect, not an alias."""
        if spec.name in self._metrics:
            raise InvalidValueError(f"{spec.name}: declared twice")
        metric = Metric(spec, self._lock)
        self._metrics[spec.name] = metric
        return metric

    def __getitem__(self, name: str) -> Metric:
        return self._metrics[name]

    @property
    def names(self) -> tuple[str, ...]:
        """Every declared metric name, in declaration order."""
        return tuple(self._metrics)

    def series_total(self) -> int:
        """How many series this process currently holds, across every metric."""
        return sum(metric.series_count for metric in self._metrics.values())

    def exposition(self, *, preamble: Iterable[str] = ()) -> str:
        """Render every declared metric in the Prometheus text exposition format.

        Args:
            preamble: Comment lines written before the first family. It is where
                a deployment states something a scraper's reader needs and a
                series cannot carry -- that this process serves a mock adapter,
                for instance. Each line is written as a comment; a comment is not
                a metric, and nothing here turns one into a sample.
        """
        lines: list[str] = [f"# {line}" for line in preamble]
        for metric in self._metrics.values():
            lines.extend(_render(metric))
        return "\n".join(lines) + "\n"


def _render(metric: Metric) -> list[str]:
    spec = metric.spec
    kind = GAUGE if spec.instrument == GAUGE else spec.instrument
    lines = [
        f"# HELP {spec.name} {spec.help_text}",
        f"# TYPE {spec.name} {kind}",
    ]
    for labels, series in metric.samples():
        if spec.instrument == HISTOGRAM:
            lines.extend(_render_histogram(spec, labels, series))
        else:
            lines.append(f"{spec.name}{_labels(labels)} {_number(series.value)}")
    return lines


def _render_histogram(
    spec: MetricSpec, labels: dict[str, str], series: _Series
) -> list[str]:
    boundaries = list(spec.buckets or ())
    lines: list[str] = []
    for index, boundary in enumerate(boundaries):
        bucket = dict(labels, le=_number(boundary))
        lines.append(f"{spec.name}_bucket{_labels(bucket)} {series.buckets[index]}")
    overflow = dict(labels, le="+Inf")
    lines.append(
        f"{spec.name}_bucket{_labels(overflow)} {series.buckets[len(boundaries)]}"
    )
    lines.append(f"{spec.name}_sum{_labels(labels)} {_number(series.total)}")
    lines.append(f"{spec.name}_count{_labels(labels)} {series.count}")
    return lines


def _labels(labels: Mapping[str, str]) -> str:
    if not labels:
        return ""
    pairs = ",".join(
        f'{_exposition_name(name)}="{value}"' for name, value in labels.items()
    )
    return "{" + pairs + "}"


def _number(value: float) -> str:
    """A number as the exposition format writes it.

    Whole numbers are written without a fractional part, which is what a counter
    reads as everywhere else, and everything else keeps enough digits that a
    duration in seconds is not rounded into a different measurement.
    """
    if value == int(value) and abs(value) < 1e15:
        return str(int(value))
    return repr(value)
