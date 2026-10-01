"""The renderer interface: a normalized render context in, release output out.

A renderer is anything with a :attr:`~Renderer.revision` - the full commit it runs
from, which a release records in ``source.renderer.revision`` - and a
:meth:`~Renderer.render` method that takes a
:class:`~.normalization.RenderContext` and nothing else. It is not given a
WorkloadContract, a binding, a defaults set, a raw document, a path, or a client:
everything it may read is already in the context, with the layer that owns it.

**No renderer exists yet.** This module defines the shape one must have, and what
a renderer returns is a type parameter rather than a decision, because the output
- generated Helm values beside a release - is a later change. A renderer that
honours the boundary is a pure function of its context and its own revision: it
reads no clock, file, environment variable, or network, and it applies nothing.
Writing its output to a Git destination, and reconciling it into a cluster, are
other components' work.
"""

from __future__ import annotations

from typing import Protocol, TypeVar, runtime_checkable

from ..release.values import GitRevision
from .normalization import RenderContext

OutputT_co = TypeVar("OutputT_co", covariant=True)


@runtime_checkable
class Renderer(Protocol[OutputT_co]):
    """Turns one normalized render context into release output."""

    @property
    def revision(self) -> GitRevision:
        """The full commit the renderer runs from."""
        ...

    def render(self, context: RenderContext) -> OutputT_co:
        """The output for ``context``: the same output for an equal context."""
        ...


__all__ = ["Renderer"]
