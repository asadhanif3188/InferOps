"""The renderer interface: a normalized render context in, release output out.

A renderer is anything with a :attr:`~Renderer.revision` - the full commit it runs
from, which a release records in ``source.renderer.revision`` - a
:attr:`~Renderer.support` naming the versions and profiles it takes, and a
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

**Refused before it runs.** :func:`render_with` is the one way to call a renderer on
documents: it asks :func:`~.normalization.prepare_render` for the context, with the
renderer's own support, and calls :meth:`~Renderer.render` only when every check has
passed. A refusal leaves nothing behind: the renderer is never called, so there is
no partial output to discard, and nothing here writes anywhere.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import Protocol, TypeVar, runtime_checkable

from ..context import NO_REQUEST_CONTEXT, RequestContext
from ..environment.binding import EnvironmentBinding
from ..release.values import GitRevision
from ..workload.contract import WorkloadContract
from ..workload.values import DnsLabel
from .defaults import PlatformDefaults
from .normalization import RenderContext, prepare_render
from .support import RendererSupport

OutputT_co = TypeVar("OutputT_co", covariant=True)


@runtime_checkable
class Renderer(Protocol[OutputT_co]):
    """Turns one normalized render context into release output."""

    @property
    def revision(self) -> GitRevision:
        """The full commit the renderer runs from."""
        ...

    @property
    def support(self) -> RendererSupport:
        """The contract, binding, and defaults versions and the profiles it takes."""
        ...

    def render(self, context: RenderContext) -> OutputT_co:
        """The output for ``context``: the same output for an equal context."""
        ...


def render_with[OutputT](
    renderer: Renderer[OutputT],
    contract: WorkloadContract,
    platform_defaults: PlatformDefaults,
    bindings: Sequence[EnvironmentBinding],
    *,
    binding_name: DnsLabel | None = None,
    context: RequestContext = NO_REQUEST_CONTEXT,
) -> OutputT:
    """The renderer's output for these inputs, or every reason it cannot render them.

    Raises:
        RenderRefused: every finding :func:`~.normalization.prepare_render` makes,
            before the renderer is called.
        TypeError: ``renderer`` does not have the interface's shape, or an input
            is a raw document.
    """
    if not isinstance(renderer, Renderer):
        raise TypeError("renderer must have a revision, a support, and a render method")
    prepared = prepare_render(
        contract,
        platform_defaults,
        bindings,
        support=renderer.support,
        binding_name=binding_name,
        context=context,
    )
    return renderer.render(prepared)


__all__ = ["Renderer", "render_with"]
