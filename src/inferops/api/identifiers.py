"""Where a request identifier and a correlation identifier come from.

The architecture assigns the correlation identifier at the edge, and this module
is that edge. Two rules decide what it does with one a caller supplied.

**A supplied identifier is validated, never trusted for its own sake.** The
integration specification requires that a security-sensitive value is validated
or injected by a trusted component rather than believed because a client sent a
header, and an identifier that reaches a log field, a metric label, and an error
body is exactly such a value. A header matching :data:`IDENTIFIER` is accepted;
anything else is replaced by a generated one.

**A malformed identifier is replaced rather than refused.** Refusing an inference
request because its observability metadata was ill-formed would make a header
nobody is required to send into a way to fail. The replacement is silent in the
response body — the identifiers a response carries are the ones this API used —
and it is silent on purpose: echoing what was rejected would put a caller-supplied
value back into the body the validation exists to keep it out of.

The generated form is a UUID version 4 with no host, process, or timestamp
component. That is deliberate: an identifier derived from a machine is an
identifier that describes one, and nothing here needs it to.
"""

from __future__ import annotations

import re
import uuid

from .surface import COMPLETION_ID_PREFIX

#: What an accepted identifier looks like. Bounded in length because it becomes a
#: log field, and restricted in alphabet because it is echoed in a response
#: header, where a control character or a newline is a header injection rather
#: than an identifier.
#:
#: **It carries no anchors, and it is matched with** :meth:`re.Pattern.fullmatch`.
#: That is not a style choice. Python's ``$`` matches at the end of a string *or
#: immediately before a single trailing newline*, so ``^...$`` with
#: :meth:`re.Pattern.match` accepts a value ending in one newline — which is
#: exactly the value this pattern exists to refuse, and precisely the one that
#: turns an echoed header into a header injection. An unanchored pattern matched
#: in full has no such edge, and
#: ``test_an_identifier_ending_in_a_newline_is_replaced`` holds it there.
IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9._:-]{0,63}")


def generate() -> str:
    """A fresh identifier: a UUID version 4, and nothing else."""
    return str(uuid.uuid4())


def accept_or_generate(supplied: str | None) -> str:
    """The identifier this request will be known by.

    Returns the supplied one when it is well-formed, and a generated one
    otherwise — including when nothing was supplied at all.
    """
    if supplied is not None and IDENTIFIER.fullmatch(supplied) is not None:
        return supplied
    return generate()


def completion_id() -> str:
    """An identifier for one completion, generated here rather than passed through.

    The accepted surface says the completion identifier is InferOps's, not the
    runtime's. The prefix is the one the recorded runtime response carried, so a
    client that pattern-matches on it is not surprised by the platform in front.
    """
    return f"{COMPLETION_ID_PREFIX}{uuid.uuid4().hex}"
