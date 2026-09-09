"""A parser for the subset of PromQL the verified correlation queries are written in.

**Why a parser exists here at all.** A query record could have listed, beside each
expression, the metrics it reads and the labels it groups by. That list would be a
second copy of the expression, maintained by hand, and the first edit that forgot to
update it would leave a record describing a query nobody runs. Everything the checker
in :mod:`tools.telemetry_correlation.core` knows about a query is derived from the
expression itself, so the two cannot disagree.

**The subset is declared, and an expression outside it is refused rather than
guessed at.** The grammar below accepts instant and range selectors, the five
aggregations :data:`AGGREGATIONS` names, the five functions :data:`FUNCTIONS` names,
the set operators, arithmetic, comparison, and explicit vector matching with ``on`` /
``ignoring`` and ``group_left`` / ``group_right``. It accepts nothing else -- no
subquery, no ``@`` modifier, no ``offset``, no ``topk``, no ``count_values`` -- and a
query using one raises :class:`PromQLError` instead of parsing to something
different. That is the whole safety argument for reading a query here instead of in
Prometheus: a form this cannot represent cannot be quietly mis-evaluated, because it
cannot be represented at all.

**This is not Prometheus.** It is a reader for a bounded query vocabulary that was
written to be read. :mod:`tools.telemetry_correlation.evaluate` states, rule by rule,
where its semantics differ from the engine's.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import dataclass, field
from typing import Final

__all__ = [
    "AGGREGATIONS",
    "BINARY_OPERATORS",
    "FUNCTIONS",
    "Aggregation",
    "Binary",
    "Call",
    "Expr",
    "Matcher",
    "NumberLiteral",
    "PromQLError",
    "Selector",
    "StringLiteral",
    "VectorMatch",
    "labels_read",
    "metrics_read",
    "parse",
]


class PromQLError(ValueError):
    """An expression outside the declared subset, or one that is not PromQL at all.

    The message names an offset and a token kind. It never echoes an arbitrary run of
    input, for the same reason :class:`tools.telemetry_collection.Finding` does not:
    this text reaches a terminal and a log.
    """


#: The aggregation operators the subset accepts. ``topk``, ``bottomk``, ``quantile``,
#: and ``count_values`` are deliberately absent: the first three select rather than
#: summarise, which makes a result depend on tie-breaking this evaluator does not
#: model, and the fourth writes a label out of a *value*, which is the one move the
#: telemetry catalog exists to prevent.
AGGREGATIONS: Final[frozenset[str]] = frozenset({"sum", "count", "avg", "min", "max"})

#: The functions the subset accepts, and their arities. Every one is used either by
#: the recording rules the chart renders or by a published correlation query.
FUNCTIONS: Final[dict[str, int]] = {
    "absent": 1,
    "rate": 1,
    "increase": 1,
    "histogram_quantile": 2,
    "label_replace": 5,
}

#: Binary operators, tightest binding first. Set operators bind loosest, which is
#: what makes ``a / b or c`` parse as ``(a / b) or c``.
BINARY_OPERATORS: Final[tuple[tuple[str, ...], ...]] = (
    ("*", "/", "%"),
    ("+", "-"),
    ("==", "!=", ">=", "<=", ">", "<"),
    ("and", "unless"),
    ("or",),
)

_METRIC_NAME = re.compile(r"[A-Za-z_:][A-Za-z0-9_:]*")
_LABEL_NAME = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
_NUMBER = re.compile(r"\d+(?:\.\d+)?")
_KEYWORDS: Final[frozenset[str]] = frozenset(
    {"by", "without", "on", "ignoring", "group_left", "group_right", "bool"}
)
_DURATION_SECONDS: Final[dict[str, int]] = {
    "s": 1,
    "m": 60,
    "h": 3600,
    "d": 86400,
    "w": 604800,
}
#: Multi-character punctuation first, so that ``=~`` is never read as ``=``.
_PUNCTUATION: Final[tuple[str, ...]] = (
    "=~",
    "!~",
    "!=",
    "==",
    ">=",
    "<=",
    "{",
    "}",
    "(",
    ")",
    "[",
    "]",
    ",",
    "=",
    ">",
    "<",
    "+",
    "-",
    "*",
    "/",
    "%",
)


@dataclass(frozen=True)
class _Token:
    kind: str
    text: str
    position: int


def _tokenize(source: str) -> list[_Token]:
    tokens: list[_Token] = []
    index = 0
    length = len(source)
    while index < length:
        character = source[index]
        if character in " \t\r\n":
            index += 1
            continue
        if character == "#":
            newline = source.find("\n", index)
            index = length if newline < 0 else newline
            continue
        if character == '"':
            end = index + 1
            chunks: list[str] = []
            while end < length and source[end] != '"':
                if source[end] == "\\":
                    if end + 1 >= length:
                        raise PromQLError(f"unterminated escape at offset {end}")
                    chunks.append(source[end + 1])
                    end += 2
                    continue
                chunks.append(source[end])
                end += 1
            if end >= length:
                raise PromQLError(f"unterminated string at offset {index}")
            tokens.append(_Token("string", "".join(chunks), index))
            index = end + 1
            continue
        name = _METRIC_NAME.match(source, index)
        if name:
            tokens.append(_Token("name", name.group(0), index))
            index = name.end()
            continue
        number = _NUMBER.match(source, index)
        if number:
            tokens.append(_Token("number", number.group(0), index))
            index = number.end()
            continue
        for punctuation in _PUNCTUATION:
            if source.startswith(punctuation, index):
                tokens.append(_Token(punctuation, punctuation, index))
                index += len(punctuation)
                break
        else:
            raise PromQLError(
                f"the character at offset {index} is not part of the accepted subset"
            )
    return tokens


@dataclass(frozen=True)
class Matcher:
    """One label matcher inside a selector's braces."""

    label: str
    operator: str
    value: str


@dataclass(frozen=True)
class VectorMatch:
    """The ``on``/``ignoring`` and ``group_left``/``group_right`` clause of a binary."""

    on: tuple[str, ...] | None = None
    ignoring: tuple[str, ...] | None = None
    card: str | None = None
    include: tuple[str, ...] = ()


@dataclass(frozen=True)
class Selector:
    """An instant or range vector selector."""

    name: str | None
    matchers: tuple[Matcher, ...] = ()
    range_seconds: int | None = None


@dataclass(frozen=True)
class NumberLiteral:
    value: float


@dataclass(frozen=True)
class StringLiteral:
    value: str


@dataclass(frozen=True)
class Call:
    function: str
    arguments: tuple[Expr, ...]


@dataclass(frozen=True)
class Aggregation:
    operator: str
    argument: Expr
    grouping: tuple[str, ...] = ()
    without: bool = False


@dataclass(frozen=True)
class Binary:
    operator: str
    left: Expr
    right: Expr
    matching: VectorMatch = field(default_factory=VectorMatch)
    bool_modifier: bool = False


Expr = Selector | NumberLiteral | StringLiteral | Call | Aggregation | Binary

_TOP = len(BINARY_OPERATORS) - 1


class _Parser:
    def __init__(self, tokens: list[_Token]) -> None:
        self._tokens = tokens
        self._index = 0

    def _peek(self, offset: int = 0) -> _Token | None:
        position = self._index + offset
        return self._tokens[position] if position < len(self._tokens) else None

    def _kind(self, offset: int = 0) -> str | None:
        token = self._peek(offset)
        return token.kind if token is not None else None

    def _next(self) -> _Token:
        token = self._peek()
        if token is None:
            raise PromQLError("the expression ended before it was complete")
        self._index += 1
        return token

    def _accept(self, kind: str, text: str | None = None) -> _Token | None:
        token = self._peek()
        if token is None or token.kind != kind:
            return None
        if text is not None and token.text != text:
            return None
        self._index += 1
        return token

    def _expect(self, kind: str) -> _Token:
        token = self._next()
        if token.kind != kind:
            raise PromQLError(
                f"expected {kind!r} at offset {token.position}, found {token.kind!r}"
            )
        return token

    def parse(self) -> Expr:
        expression = self._binary(_TOP)
        remaining = self._peek()
        if remaining is not None:
            raise PromQLError(
                f"trailing input at offset {remaining.position}: {remaining.kind!r} "
                "does not begin an operator the subset accepts"
            )
        return expression

    def _binary(self, level: int) -> Expr:
        if level < 0:
            return self._unary()
        operators = BINARY_OPERATORS[level]
        left = self._binary(level - 1)
        while True:
            token = self._peek()
            if token is None:
                return left
            if token.kind == "name":
                if token.text not in operators:
                    return left
            elif token.kind not in operators:
                return left
            self._index += 1
            bool_modifier = self._accept("name", "bool") is not None
            matching = self._vector_match()
            right = self._binary(level - 1)
            left = Binary(
                operator=token.text,
                left=left,
                right=right,
                matching=matching,
                bool_modifier=bool_modifier,
            )

    def _vector_match(self) -> VectorMatch:
        on: tuple[str, ...] | None = None
        ignoring: tuple[str, ...] | None = None
        token = self._peek()
        if (
            token is not None
            and token.kind == "name"
            and token.text in {"on", "ignoring"}
        ):
            self._index += 1
            labels = self._label_list()
            if token.text == "on":
                on = labels
            else:
                ignoring = labels
        card: str | None = None
        include: tuple[str, ...] = ()
        token = self._peek()
        if (
            token is not None
            and token.kind == "name"
            and token.text
            in {
                "group_left",
                "group_right",
            }
        ):
            self._index += 1
            card = token.text
            if self._kind() == "(":
                include = self._label_list()
        if card is not None and on is None and ignoring is None:
            raise PromQLError(
                "a group_left or group_right without an on or ignoring clause is "
                "outside the accepted subset: the join key has to be written down"
            )
        return VectorMatch(on=on, ignoring=ignoring, card=card, include=include)

    def _label_list(self) -> tuple[str, ...]:
        self._expect("(")
        labels: list[str] = []
        if self._kind() == ")":
            self._index += 1
            return ()
        while True:
            token = self._expect("name")
            if not _LABEL_NAME.fullmatch(token.text):
                raise PromQLError(
                    f"the name at offset {token.position} is not a label name"
                )
            labels.append(token.text)
            if self._accept(",") is None:
                break
        self._expect(")")
        return tuple(labels)

    def _unary(self) -> Expr:
        if self._accept("-") is not None:
            return Binary("-", NumberLiteral(0.0), self._unary())
        if self._accept("+") is not None:
            return self._unary()
        return self._primary()

    def _primary(self) -> Expr:
        token = self._peek()
        if token is None:
            raise PromQLError("the expression ended before it was complete")
        if token.kind == "number":
            self._index += 1
            return NumberLiteral(float(token.text))
        if token.kind == "string":
            self._index += 1
            return StringLiteral(token.text)
        if token.kind == "(":
            self._index += 1
            inner = self._binary(_TOP)
            self._expect(")")
            return inner
        if token.kind == "{":
            return self._selector(None)
        if token.kind == "name":
            if token.text in _KEYWORDS:
                raise PromQLError(
                    f"the keyword at offset {token.position} cannot begin an expression"
                )
            following = self._peek(1)
            if (
                token.text in AGGREGATIONS
                and following is not None
                and (following.kind == "(" or following.text in {"by", "without"})
            ):
                return self._aggregation()
            if following is not None and following.kind == "(":
                return self._call()
            self._index += 1
            return self._selector(token.text)
        raise PromQLError(
            f"the token at offset {token.position} cannot begin an expression"
        )

    def _aggregation(self) -> Aggregation:
        operator = self._expect("name").text
        token = self._peek()
        if (
            token is not None
            and token.kind == "name"
            and token.text in {"by", "without"}
        ):
            self._index += 1
            grouping = self._label_list()
            return Aggregation(
                operator,
                self._parenthesised_single_argument(),
                grouping,
                token.text == "without",
            )
        argument = self._parenthesised_single_argument()
        token = self._peek()
        if (
            token is not None
            and token.kind == "name"
            and token.text in {"by", "without"}
        ):
            self._index += 1
            return Aggregation(
                operator, argument, self._label_list(), token.text == "without"
            )
        return Aggregation(operator, argument)

    def _parenthesised_single_argument(self) -> Expr:
        self._expect("(")
        argument = self._binary(_TOP)
        if self._kind() == ",":
            raise PromQLError(
                "an aggregation taking more than one argument is outside the "
                "accepted subset"
            )
        self._expect(")")
        return argument

    def _call(self) -> Call:
        token = self._expect("name")
        name = token.text
        if name not in FUNCTIONS:
            raise PromQLError(
                f"the function named at offset {token.position} is not one of the "
                f"{len(FUNCTIONS)} the subset accepts"
            )
        self._expect("(")
        arguments: list[Expr] = []
        if self._kind() == ")":
            self._index += 1
        else:
            while True:
                arguments.append(self._binary(_TOP))
                if self._accept(",") is None:
                    break
            self._expect(")")
        if len(arguments) != FUNCTIONS[name]:
            raise PromQLError(
                f"the call at offset {token.position} passes {len(arguments)} "
                f"argument(s) where {FUNCTIONS[name]} is the arity"
            )
        return Call(name, tuple(arguments))

    def _selector(self, name: str | None) -> Selector:
        matchers: list[Matcher] = []
        if self._kind() == "{":
            self._index += 1
            if self._kind() == "}":
                self._index += 1
            else:
                while True:
                    label = self._expect("name")
                    if not _LABEL_NAME.fullmatch(label.text):
                        raise PromQLError(
                            f"the name at offset {label.position} is not a label name"
                        )
                    operator = self._next()
                    if operator.kind not in {"=", "!=", "=~", "!~"}:
                        raise PromQLError(
                            f"the token at offset {operator.position} is not a label "
                            "matcher operator"
                        )
                    value = self._expect("string")
                    matchers.append(Matcher(label.text, operator.kind, value.text))
                    if self._accept(",") is None:
                        break
                self._expect("}")
        range_seconds: int | None = None
        if self._kind() == "[":
            self._index += 1
            range_seconds = self._duration()
            self._expect("]")
        if name is None and not matchers:
            raise PromQLError("a selector must name a metric or carry a matcher")
        return Selector(name, tuple(matchers), range_seconds)

    def _duration(self) -> int:
        """A range duration, which the tokenizer reads as a number then a unit name.

        Whole units only. A fractional or compound duration is refused rather than
        rounded, because a range this evaluator read differently from the engine is
        the one difference a reader would never think to check.
        """
        number = self._next()
        unit = self._peek()
        if (
            number.kind != "number"
            or "." in number.text
            or unit is None
            or unit.kind != "name"
            or unit.text not in _DURATION_SECONDS
        ):
            raise PromQLError(
                f"the range at offset {number.position} is not a whole number of "
                "seconds, minutes, hours, days, or weeks"
            )
        self._index += 1
        return int(number.text) * _DURATION_SECONDS[unit.text]


def parse(expression: str) -> Expr:
    """The expression as a syntax tree, or :class:`PromQLError` if it is outside the subset."""
    return _Parser(_tokenize(expression)).parse()


def walk(node: Expr) -> Iterator[Expr]:
    """Every node in the tree, the root first."""
    yield node
    if isinstance(node, Call):
        for argument in node.arguments:
            yield from walk(argument)
    elif isinstance(node, Aggregation):
        yield from walk(node.argument)
    elif isinstance(node, Binary):
        yield from walk(node.left)
        yield from walk(node.right)


def metrics_read(node: Expr) -> frozenset[str]:
    """Every metric or recorded series name a selector in the tree reads."""
    return frozenset(
        subnode.name
        for subnode in walk(node)
        if isinstance(subnode, Selector) and subnode.name is not None
    )


def labels_read(node: Expr) -> frozenset[str]:
    """Every label name the expression names, in any position that depends on it.

    Matchers, aggregation groupings, ``on`` and ``ignoring`` sets, ``group_left`` and
    ``group_right`` inclusions, and the destination and source labels of a
    ``label_replace``. The catalog's placement rules are applied to this set, so a
    label appearing anywhere here is one the query depends on.
    """
    names: set[str] = set()
    for subnode in walk(node):
        if isinstance(subnode, Selector):
            names.update(matcher.label for matcher in subnode.matchers)
        elif isinstance(subnode, Aggregation):
            names.update(subnode.grouping)
        elif isinstance(subnode, Binary):
            names.update(subnode.matching.on or ())
            names.update(subnode.matching.ignoring or ())
            names.update(subnode.matching.include)
        elif isinstance(subnode, Call) and subnode.function == "label_replace":
            for position in (1, 3):
                argument = subnode.arguments[position]
                if isinstance(argument, StringLiteral) and _LABEL_NAME.fullmatch(
                    argument.value
                ):
                    names.add(argument.value)
    return frozenset(names)
