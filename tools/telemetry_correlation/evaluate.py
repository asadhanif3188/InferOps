"""An evaluator for the declared PromQL subset, over a fixture store.

**What this is for.** A query can be checked statically -- that it reads a metric the
catalog declares, groups by a label the series carries, and joins on a key both sides
have -- and still return nothing, because the join key was right in the record and
wrong in the store. The only way to tell those apart is to run the query. There is no
store to run it against, so the store is a fixture: a set of series with the exact
label sets the chart's rendered scrape configuration would attach, and values chosen
so that each query's answer is one somebody can check by hand.

**What this is not.** It is not Prometheus, and a result here is not a measurement.
Nothing is scraped here and every series below was written into a fixture file by
hand. A real collector has since been installed and queried on one provider; that
record is separate and this module establishes nothing about it. The known differences from the engine are declared
rather than left to be discovered:

``rate`` and ``increase`` do not extrapolate
    Prometheus extrapolates a rate to the edges of its window when the first and last
    samples sit inside it. This takes the plain delta over the observed samples
    divided by the observed interval. Fixtures are written with samples on the window
    boundaries, where the two agree, and :data:`EXTRAPOLATION` records the rule.

counter resets are corrected, decreases are not otherwise interpreted
    A sample below its predecessor is read as a reset and the predecessor is added
    back, which is the engine's rule.

staleness is a lookback and nothing more
    An instant selector takes the newest sample in the **half-open** window
    ``(T - LOOKBACK_SECONDS, T]``: a sample exactly :data:`LOOKBACK_SECONDS` old is
    outside it. That boundary is stated exactly rather than as "no older than",
    which independent review read -- reasonably -- as inclusive. Which side
    Prometheus falls on at exactly the boundary has not been checked against the
    engine here, so it is declared as a difference this repository has not verified
    rather than as agreement it has. No fixture places a sample on the boundary, and
    a test pins the behaviour so a change to it cannot be silent. Prometheus's stale
    markers do not exist here either, because nothing writes one into a fixture.

a matcher's regular expression must be inside a declared safe subset
    A literal run, an escaped character, ``|``, and at most
    :data:`MAX_PATTERN_WILDCARDS` ``.`` or ``.*`` wildcards. A group, a character
    class, and every other quantifier are refused, so a pattern cannot backtrack
    into itself and hang the process evaluating it. Prometheus uses RE2, which
    accepts more and is linear; this accepts less and says so.

``absent`` reproduces only the labels of equality matchers
    Which is the engine's rule, and the only part of it these queries depend on.

a comparison without ``bool`` filters, and keeps the left element unchanged
    Including its metric name. Only the arithmetic operators drop the name, which is
    the engine's rule; an earlier version of this module dropped it for every
    operator and independent review caught it.

``histogram_quantile`` interpolates linearly inside the chosen bucket
    The engine's rule, including its treatment of a quantile at or below the lowest
    finite bucket. Buckets whose counts are not monotonic are not repaired.

no instant is a range
    There is one evaluation instant per run, so no query here can be evaluated over a
    range, and no subquery form is in the subset.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from typing import Final

from .promql import (
    Aggregation,
    Binary,
    Call,
    Expr,
    Matcher,
    NumberLiteral,
    PromQLError,
    Selector,
    StringLiteral,
    VectorMatch,
)

__all__ = [
    "EXTRAPOLATION",
    "LOOKBACK_SECONDS",
    "MAX_PATTERN_WILDCARDS",
    "EvaluationError",
    "Sample",
    "Series",
    "Store",
    "evaluate",
    "format_vector",
]

#: How far back an instant selector may reach for a sample. Prometheus's default.
LOOKBACK_SECONDS: Final = 300

#: Recorded as data so that the document and the evidence can quote the rule rather
#: than paraphrase it.
EXTRAPOLATION: Final = (
    "none. rate() and increase() take the delta between the first and last samples "
    "inside the window, divided by the interval between them, with counter resets "
    "added back. Prometheus extrapolates to the window edges; the fixtures place "
    "samples on the boundaries, where the two agree."
)

#: The label that carries a metric's name, as Prometheus spells it.
NAME_LABEL: Final = "__name__"

#: The label histogram buckets are keyed by.
BUCKET_LABEL: Final = "le"


class EvaluationError(ValueError):
    """A store or an expression this evaluator refuses to guess at.

    Duplicate series, a many-to-many vector match with no grouping modifier, a
    non-numeric literal where a number belongs. Each of them is a case Prometheus
    also refuses; refusing them here keeps a fixture that would not load into a real
    store from producing a result in this one.
    """


@dataclass(frozen=True)
class Sample:
    """One instant-vector element: a label set and a value."""

    labels: tuple[tuple[str, str], ...]
    value: float

    @property
    def mapping(self) -> dict[str, str]:
        return dict(self.labels)

    def name(self) -> str | None:
        return self.mapping.get(NAME_LABEL)


@dataclass(frozen=True)
class Series:
    """One fixture series: a label set and the samples observed on it."""

    labels: tuple[tuple[str, str], ...]
    points: tuple[tuple[float, float], ...]

    @property
    def mapping(self) -> dict[str, str]:
        return dict(self.labels)


@dataclass(frozen=True)
class Store:
    """A set of fixture series, and the instant a query is evaluated at."""

    series: tuple[Series, ...]
    evaluation_instant: float

    def with_series(self, extra: Iterable[Series]) -> Store:
        return Store(self.series + tuple(extra), self.evaluation_instant)


Vector = list[Sample]


def _labels(mapping: Mapping[str, str]) -> tuple[tuple[str, str], ...]:
    return tuple(sorted(mapping.items()))


def _without_name(mapping: Mapping[str, str]) -> dict[str, str]:
    return {key: value for key, value in mapping.items() if key != NAME_LABEL}


#: Every pattern this evaluator will compile: a literal run, an escaped character as
#: ``regexQuoteMeta`` writes one, the ``.*`` wildcard, a bare ``.``, and ``|`` to
#: alternate between them. A group is the thing deliberately missing -- no ``(``,
#: ``)``, ``[``, ``]``, ``{`` or ``}``, and no ``+``, ``?`` or ``*`` except in ``.*``
#: -- which is what makes catastrophic backtracking impossible rather than unlikely:
#: there is no repeated group for a pattern to backtrack into.
#:
#: It admits everything this repository writes: the chart's own filters are an
#: alternation of ``regexQuoteMeta`` names, and ``label_replace`` is used with the
#: empty pattern. Anything else is refused, for the reason
#: :mod:`tools.telemetry_collection` gives for reading a labeldrop regex rather than
#: running it -- a checker that ran an arbitrary regex out of the input it is checking
#: is deciding the answer by running the question. Independent review found
#: ``(a+)+$`` hanging this module on a thirty-five character label value.
_SAFE_PATTERN = re.compile(r"^(?:[A-Za-z0-9_:/@ ,=|-]|\\.|\.\*|\.)*$")

#: An escaped character, which is one literal and contributes no wildcard.
_ESCAPED = re.compile(r"\\.")

#: How many wildcards one pattern may use. Without a group there is no catastrophic
#: backtracking, but a pattern of many ``.*`` runs against a long non-matching string
#: still costs a power of its length, and a bound is cheaper than an argument about
#: how long a label value can be.
MAX_PATTERN_WILDCARDS: Final = 4


def _compiled(pattern: str, where: str) -> re.Pattern[str]:
    """A matcher pattern, refused unless it is inside the declared safe subset."""
    if _SAFE_PATTERN.fullmatch(pattern) is None:
        raise EvaluationError(
            f"the {where} pattern uses a regular-expression form outside the "
            "accepted subset. A group, a character class, and every quantifier but "
            "the .* wildcard are refused, because a pattern that can backtrack into "
            "itself can hang whatever evaluates it"
        )
    if _ESCAPED.sub("", pattern).count(".") > MAX_PATTERN_WILDCARDS:
        raise EvaluationError(
            f"the {where} pattern uses more than {MAX_PATTERN_WILDCARDS} wildcards. "
            "There is no group for it to backtrack into, and matching it against a "
            "long value still costs a power of that value's length"
        )
    return re.compile(f"^(?:{pattern})$")


def _matches(mapping: Mapping[str, str], matcher: Matcher) -> bool:
    value = mapping.get(matcher.label, "")
    if matcher.operator == "=":
        return value == matcher.value
    if matcher.operator == "!=":
        return value != matcher.value
    found = _compiled(matcher.value, "matcher").match(value) is not None
    return found if matcher.operator == "=~" else not found


def _selected(store: Store, selector: Selector) -> list[Series]:
    chosen: list[Series] = []
    for series in store.series:
        mapping = series.mapping
        if selector.name is not None and mapping.get(NAME_LABEL) != selector.name:
            continue
        if all(_matches(mapping, matcher) for matcher in selector.matchers):
            chosen.append(series)
    return chosen


def _instant(store: Store, selector: Selector) -> Vector:
    horizon = store.evaluation_instant - LOOKBACK_SECONDS
    samples: Vector = []
    for series in _selected(store, selector):
        newest = [
            point
            for point in series.points
            if horizon < point[0] <= store.evaluation_instant
        ]
        if not newest:
            continue
        samples.append(Sample(series.labels, max(newest, key=lambda p: p[0])[1]))
    return _checked(samples)


def _range(
    store: Store, selector: Selector
) -> list[tuple[Series, list[tuple[float, float]]]]:
    if selector.range_seconds is None:  # pragma: no cover - guarded by the caller
        raise EvaluationError("a range function was given an instant selector")
    start = store.evaluation_instant - selector.range_seconds
    windows: list[tuple[Series, list[tuple[float, float]]]] = []
    for series in _selected(store, selector):
        points = sorted(
            point
            for point in series.points
            if start <= point[0] <= store.evaluation_instant
        )
        windows.append((series, points))
    return windows


def _checked(samples: Vector) -> Vector:
    """The vector, refused if two elements carry the same label set.

    A store holding one label set twice is not a store Prometheus would have
    accepted, and a duplicate is exactly the mistake a hand-written fixture makes.
    """
    seen: set[tuple[tuple[str, str], ...]] = set()
    for sample in samples:
        if sample.labels in seen:
            raise EvaluationError(
                "two elements of one vector carry the same label set, which no "
                "store can hold"
            )
        seen.add(sample.labels)
    return samples


def _counter_delta(points: Sequence[tuple[float, float]]) -> float:
    total = 0.0
    previous = points[0][1]
    for _, value in points[1:]:
        total += value - previous if value >= previous else value
        previous = value
    return total


def _rate(store: Store, selector: Selector, as_increase: bool) -> Vector:
    samples: Vector = []
    for series, points in _range(store, selector):
        if len(points) < 2:
            continue
        span = points[-1][0] - points[0][0]
        if span <= 0:
            continue
        delta = _counter_delta(points)
        value = delta if as_increase else delta / span
        samples.append(Sample(_labels(_without_name(series.mapping)), value))
    return _checked(samples)


def _absent(inner: Vector, argument: Expr) -> Vector:
    if inner:
        return []
    mapping: dict[str, str] = {}
    if isinstance(argument, Selector):
        mapping = {
            matcher.label: matcher.value
            for matcher in argument.matchers
            if matcher.operator == "="
        }
    return [Sample(_labels(mapping), 1.0)]


def _histogram_quantile(quantile: float, buckets: Vector) -> Vector:
    grouped: dict[tuple[tuple[str, str], ...], list[tuple[float, float]]] = {}
    for sample in buckets:
        mapping = _without_name(sample.mapping)
        boundary = mapping.pop(BUCKET_LABEL, None)
        if boundary is None:
            continue
        upper = math.inf if boundary in {"+Inf", "Inf"} else float(boundary)
        grouped.setdefault(_labels(mapping), []).append((upper, sample.value))
    samples: Vector = []
    for labels, pairs in grouped.items():
        pairs.sort()
        # The +Inf bucket is what makes the counts a distribution: without it there
        # is no total to take a fraction of, and the engine returns NaN rather than
        # treating the largest finite bucket as the whole.
        total = pairs[-1][1]
        if not math.isinf(pairs[-1][0]) or total <= 0:
            samples.append(Sample(labels, math.nan))
            continue
        rank = quantile * total
        index = next(
            (position for position, pair in enumerate(pairs) if pair[1] >= rank),
            len(pairs) - 1,
        )
        upper, cumulative = pairs[index]
        if math.isinf(upper):
            samples.append(Sample(labels, pairs[max(index - 1, 0)][0]))
            continue
        lower, below = (
            (0.0, 0.0) if index == 0 else (pairs[index - 1][0], pairs[index - 1][1])
        )
        width = cumulative - below
        fraction = 0.0 if width <= 0 else (rank - below) / width
        samples.append(Sample(labels, lower + (upper - lower) * fraction))
    return samples


def _expand(replacement: str, match: re.Match[str]) -> str:
    """``$1`` and friends in a label_replace replacement, filled from the match.

    A group that matched nothing contributes an empty string, which is the engine's
    rule and is also what makes an empty result remove the destination label rather
    than set it to nothing.
    """
    return re.sub(
        r"\$(\d+)",
        lambda reference: match.group(int(reference.group(1))) or "",
        replacement,
    )


def _label_replace(
    inner: Vector, destination: str, replacement: str, source: str, pattern: str
) -> Vector:
    compiled = _compiled(pattern, "label_replace")
    samples: Vector = []
    for sample in inner:
        mapping = sample.mapping
        match = compiled.match(mapping.get(source, ""))
        if match is None:
            samples.append(sample)
            continue
        value = _expand(replacement, match)
        updated = dict(mapping)
        if value:
            updated[destination] = value
        else:
            updated.pop(destination, None)
        samples.append(Sample(_labels(updated), sample.value))
    return _checked(samples)


#: The five aggregations the subset accepts. Each takes the group's values and
#: returns one number; none of them can look at a label, which is why `count_values`
#: is not among them.
_AGGREGATORS: Final[dict[str, Callable[[Sequence[float]], float]]] = {
    "sum": math.fsum,
    "count": lambda values: float(len(values)),
    "avg": lambda values: math.fsum(values) / len(values),
    "min": min,
    "max": max,
}


def _aggregate(node: Aggregation, inner: Vector) -> Vector:
    grouped: dict[tuple[tuple[str, str], ...], list[float]] = {}
    for sample in inner:
        mapping = _without_name(sample.mapping)
        if node.without:
            key = {k: v for k, v in mapping.items() if k not in node.grouping}
        else:
            key = {k: mapping[k] for k in node.grouping if k in mapping}
        grouped.setdefault(_labels(key), []).append(sample.value)
    reducer = _AGGREGATORS[node.operator]
    return [
        Sample(labels, float(reducer(values))) for labels, values in grouped.items()
    ]


_ARITHMETIC: Final[dict[str, Callable[[float, float], float]]] = {
    "+": lambda a, b: a + b,
    "-": lambda a, b: a - b,
    "*": lambda a, b: a * b,
    "/": lambda a, b: math.nan if b == 0 else a / b,
    "%": lambda a, b: math.nan if b == 0 else math.fmod(a, b),
}
_COMPARISON: Final[dict[str, Callable[[float, float], bool]]] = {
    "==": lambda a, b: a == b,
    "!=": lambda a, b: a != b,
    ">": lambda a, b: a > b,
    "<": lambda a, b: a < b,
    ">=": lambda a, b: a >= b,
    "<=": lambda a, b: a <= b,
}


def _match_key(
    mapping: Mapping[str, str], matching: VectorMatch
) -> tuple[tuple[str, str], ...]:
    without_name = _without_name(mapping)
    if matching.on is not None:
        return _labels({k: without_name[k] for k in matching.on if k in without_name})
    ignoring = set(matching.ignoring or ())
    return _labels({k: v for k, v in without_name.items() if k not in ignoring})


def _scalar(node: Expr, value: Vector | float) -> float:
    if isinstance(value, float):
        return value
    raise EvaluationError(
        f"{type(node).__name__} produced a vector where a number belongs"
    )


def _binary_vectors(node: Binary, left: Vector, right: Vector) -> Vector:
    operator = node.operator
    matching = node.matching
    if operator in {"and", "unless", "or"}:
        left_keys = {_match_key(sample.mapping, matching) for sample in left}
        right_keys = {_match_key(sample.mapping, matching) for sample in right}
        if operator == "and":
            return [s for s in left if _match_key(s.mapping, matching) in right_keys]
        if operator == "unless":
            return [
                s for s in left if _match_key(s.mapping, matching) not in right_keys
            ]
        extra = [s for s in right if _match_key(s.mapping, matching) not in left_keys]
        return _checked(list(left) + extra)

    many, one = (left, right)
    if matching.card == "group_right":
        many, one = (right, left)
    index: dict[tuple[tuple[str, str], ...], Sample] = {}
    for sample in one:
        key = _match_key(sample.mapping, matching)
        if key in index:
            raise EvaluationError(
                "the one side of this vector match carries a duplicate join key, "
                "which makes the match many-to-many"
            )
        index[key] = sample
    samples: Vector = []
    for sample in many:
        counterpart = index.get(_match_key(sample.mapping, matching))
        if counterpart is None:
            continue
        mapping = (
            {k: v for k, v in sample.mapping.items() if k != NAME_LABEL}
            if matching.card is not None
            else _match_key_mapping(sample.mapping, matching)
        )
        if matching.card is not None:
            for label in matching.include:
                if label in counterpart.mapping:
                    mapping[label] = counterpart.mapping[label]
                else:
                    mapping.pop(label, None)
        left_value = (
            sample.value if matching.card != "group_right" else counterpart.value
        )
        right_value = (
            counterpart.value if matching.card != "group_right" else sample.value
        )
        if operator in _COMPARISON:
            keep = _COMPARISON[operator](left_value, right_value)
            if node.bool_modifier:
                # `bool` computes, so the result is a new series and loses the name.
                samples.append(Sample(_labels(mapping), 1.0 if keep else 0.0))
            elif keep:
                # A comparison without `bool` *filters*: Prometheus returns the
                # left-hand element unchanged, metric name included, because nothing
                # was computed. Only the arithmetic operators drop the name.
                # Independent review found this returning the join key instead.
                samples.append(
                    sample if matching.card != "group_right" else counterpart
                )
            continue
        samples.append(
            Sample(_labels(mapping), _ARITHMETIC[operator](left_value, right_value))
        )
    return _checked(samples)


def _match_key_mapping(
    mapping: Mapping[str, str], matching: VectorMatch
) -> dict[str, str]:
    """The label set a one-to-one match keeps: the join key and nothing else."""
    return dict(_match_key(mapping, matching))


def _binary_scalar(
    node: Binary, vector: Vector, scalar: float, scalar_on_left: bool
) -> Vector:
    samples: Vector = []
    for sample in vector:
        left = scalar if scalar_on_left else sample.value
        right = sample.value if scalar_on_left else scalar
        mapping = _without_name(sample.mapping)
        if node.operator in _COMPARISON:
            keep = _COMPARISON[node.operator](left, right)
            if node.bool_modifier:
                samples.append(Sample(_labels(mapping), 1.0 if keep else 0.0))
            elif keep:
                samples.append(sample)
            continue
        samples.append(
            Sample(_labels(mapping), _ARITHMETIC[node.operator](left, right))
        )
    return samples


def _evaluate(store: Store, node: Expr) -> Vector | float:
    if isinstance(node, NumberLiteral):
        return node.value
    if isinstance(node, StringLiteral):
        raise EvaluationError("a string literal is only an argument to label_replace")
    if isinstance(node, Selector):
        if node.range_seconds is not None:
            raise EvaluationError(
                "a range selector is only an argument to rate or increase"
            )
        return _instant(store, node)
    if isinstance(node, Aggregation):
        inner = _evaluate(store, node.argument)
        if isinstance(inner, float):
            raise EvaluationError("an aggregation was given a number, not a vector")
        return _aggregate(node, inner)
    if isinstance(node, Call):
        return _call(store, node)
    if isinstance(node, Binary):
        left = _evaluate(store, node.left)
        right = _evaluate(store, node.right)
        if isinstance(left, float) and isinstance(right, float):
            if node.operator in _COMPARISON:
                return 1.0 if _COMPARISON[node.operator](left, right) else 0.0
            return _ARITHMETIC[node.operator](left, right)
        if isinstance(left, float):
            assert not isinstance(right, float)
            return _binary_scalar(node, right, left, scalar_on_left=True)
        if isinstance(right, float):
            return _binary_scalar(node, left, right, scalar_on_left=False)
        return _binary_vectors(node, left, right)
    raise PromQLError(f"{type(node).__name__} is outside the accepted subset")


def _call(store: Store, node: Call) -> Vector | float:
    if node.function in {"rate", "increase"}:
        argument = node.arguments[0]
        if not isinstance(argument, Selector) or argument.range_seconds is None:
            raise EvaluationError(f"{node.function} takes a range selector")
        return _rate(store, argument, as_increase=node.function == "increase")
    if node.function == "absent":
        inner = _evaluate(store, node.arguments[0])
        if isinstance(inner, float):
            raise EvaluationError("absent was given a number, not a vector")
        return _absent(inner, node.arguments[0])
    if node.function == "histogram_quantile":
        quantile = _scalar(node.arguments[0], _evaluate(store, node.arguments[0]))
        buckets = _evaluate(store, node.arguments[1])
        if isinstance(buckets, float):
            raise EvaluationError("histogram_quantile was given a number, not a vector")
        return _histogram_quantile(quantile, buckets)
    if node.function == "label_replace":
        inner = _evaluate(store, node.arguments[0])
        if isinstance(inner, float):
            raise EvaluationError("label_replace was given a number, not a vector")
        literals = []
        for argument in node.arguments[1:]:
            if not isinstance(argument, StringLiteral):
                raise EvaluationError("label_replace takes four string literals")
            literals.append(argument.value)
        return _label_replace(inner, *literals)
    raise PromQLError(f"{node.function} is outside the accepted subset")


def evaluate(store: Store, node: Expr) -> Vector:
    """The instant vector this expression produces over this store, sorted.

    Sorted by label set so that a result is comparable between runs: Prometheus
    returns an instant vector unordered, and an evidence record that changed with
    dictionary iteration order would be a record nobody could diff.
    """
    result = _evaluate(store, node)
    if isinstance(result, float):
        raise EvaluationError("this expression produces a number rather than a vector")
    return sorted(result, key=lambda sample: sample.labels)


def format_vector(vector: Vector) -> list[str]:
    """One stable line per sample: ``{a="1", b="2"} 3``.

    The metric name, when a sample still carries one, is written as the first label
    rather than in front of the braces, so that a line is one syntax rather than two.
    """
    lines: list[str] = []
    for sample in vector:
        rendered = ", ".join(f'{key}="{value}"' for key, value in sample.labels)
        value = sample.value
        if math.isnan(value):
            text = "NaN"
        elif value == int(value) and abs(value) < 1e15:
            text = str(int(value))
        else:
            text = f"{value:.6g}"
        lines.append(f"{{{rendered}}} {text}")
    return sorted(lines)
