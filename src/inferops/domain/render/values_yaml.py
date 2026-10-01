"""The canonical YAML form generated Helm values are written in.

Helm reads values as YAML, so generated values are YAML. The distribution carries
no runtime dependency, so this module writes it, and it writes one spelling of each
value so that two equal documents are always the same text:

- **mappings in block style, keys sorted** by code point, two spaces per level; an
  empty mapping is ``{}``;
- **lists in block style**, in the order given, a mapping item starting on its dash;
  an empty list is ``[]``;
- **every string double-quoted**, with only ``\\`` and ``"`` escaped. A plain
  scalar would be read by type - ``yes`` and ``on`` as booleans, ``1e3`` as a
  number, ``2026-09-30`` as a date - and quoting every string removes the question
  rather than answering it per value;
- **integers in decimal**, within +/-(2**53 - 1), the release domain's bound for a
  value every reader holds exactly; **booleans** as ``true`` and ``false``;
- **LF line endings** and one final newline, and an optional header of comment lines.

**Only what has one spelling.** A string is refused unless every character is
printable ASCII - a control character, a line break, or a character outside ASCII
has escapes that YAML readers do not all decode alike - and a key unless it is a
plain identifier and not one of the words YAML 1.1 reads as a boolean or a null.
``None``, a float, a date, a nested list, and any other type are refused rather
than written some way of their own. Generated values never need any of them: every
string a chart value takes is ASCII by its schema's own pattern.

Offline and deterministic: no clock, no file, no environment, no randomness.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from typing import Any, Final

from ..release.canonical import LARGEST_EXACT_INTEGER

#: A key written plain: a letter, then letters and digits.
_KEY: Final = re.compile(r"[A-Za-z][A-Za-z0-9]*", re.ASCII)

#: Plain words YAML 1.1 reads as a boolean or a null, compared case-insensitively.
_RESERVED_KEYS: Final = frozenset(
    {"y", "n", "yes", "no", "on", "off", "true", "false", "null"}
)

#: Every character a written string may hold: printable ASCII, space included.
_PRINTABLE: Final = re.compile(r"[\x20-\x7e]*", re.ASCII)

_INDENT: Final = "  "


class ValuesFormError(ValueError):
    """A value has no canonical YAML spelling. Names where, never the value."""

    def __init__(self, location: str, reason: str) -> None:
        super().__init__(f"{location}: {reason}")
        self.location = location
        self.reason = reason


def _key(key: object, location: str) -> str:
    if not isinstance(key, str):
        raise ValuesFormError(location, "a mapping key must be a string")
    if _KEY.fullmatch(key) is None:
        raise ValuesFormError(
            location, "a mapping key must be a letter followed by letters and digits"
        )
    if key.lower() in _RESERVED_KEYS:
        raise ValuesFormError(
            location, "a mapping key must not be a word YAML reads as a boolean or null"
        )
    return key


def _scalar(value: object, location: str) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        if abs(value) > LARGEST_EXACT_INTEGER:
            raise ValuesFormError(
                location, "an integer beyond 2**53 - 1 in magnitude has no exact form"
            )
        return str(value)
    if isinstance(value, str):
        if _PRINTABLE.fullmatch(value) is None:
            raise ValuesFormError(
                location, "a string must hold printable ASCII characters only"
            )
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    raise ValuesFormError(
        location, "only a string, an integer, or a boolean can be written as a value"
    )


def _is_list(value: object) -> bool:
    return isinstance(value, Sequence) and not isinstance(value, (str, bytes))


def _mapping_lines(
    mapping: Mapping[Any, object], depth: int, location: str
) -> list[str]:
    keys = {_key(key, f"{location}.{key}"): key for key in mapping}
    lines: list[str] = []
    for key in sorted(keys):
        lines.extend(_member(key, mapping[keys[key]], depth, f"{location}.{key}"))
    return lines


def _member(key: str, value: object, depth: int, location: str) -> list[str]:
    prefix = f"{_INDENT * depth}{key}:"
    if isinstance(value, Mapping):
        if not value:
            return [f"{prefix} {{}}"]
        return [prefix, *_mapping_lines(value, depth + 1, location)]
    if _is_list(value):
        assert isinstance(value, Sequence)
        if not value:
            return [f"{prefix} []"]
        return [prefix, *_list_lines(value, depth + 1, location)]
    return [f"{prefix} {_scalar(value, location)}"]


def _list_lines(items: Sequence[object], depth: int, location: str) -> list[str]:
    lines: list[str] = []
    dash = f"{_INDENT * (depth - 1)}- "
    for index, item in enumerate(items):
        where = f"{location}[{index}]"
        if isinstance(item, Mapping):
            if not item:
                lines.append(f"{dash}{{}}")
                continue
            # The first member sits on the dash; the rest align beneath it.
            members = _mapping_lines(item, depth, where)
            lines.append(dash + members[0].lstrip(" "))
            lines.extend(members[1:])
        elif _is_list(item):
            raise ValuesFormError(where, "a list directly inside a list is not written")
        else:
            lines.append(f"{dash}{_scalar(item, where)}")
    return lines


def canonical_yaml(
    document: Mapping[str, object], *, header: Sequence[str] = ()
) -> str:
    """The canonical YAML text of ``document``, a mapping at the top level.

    ``header`` lines are written first, each as a comment, and must themselves be
    printable ASCII.

    Raises:
        ValuesFormError: a key or a value has no canonical spelling; the location
            is a path of member names and list indices, and never quotes a value.
        TypeError: ``document`` is not a mapping.
    """
    if not isinstance(document, Mapping):
        raise TypeError("a values document must be a mapping")
    lines: list[str] = []
    for index, line in enumerate(header):
        if not isinstance(line, str) or _PRINTABLE.fullmatch(line) is None:
            raise ValuesFormError(
                f"header[{index}]", "a header line must be printable ASCII"
            )
        lines.append(f"# {line}" if line else "#")
    lines.extend(_mapping_lines(document, 0, "$") if document else ["{}"])
    return "\n".join(lines) + "\n"


__all__ = ["ValuesFormError", "canonical_yaml"]
