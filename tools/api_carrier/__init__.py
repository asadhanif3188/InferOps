"""The standard-library HTTP carrier for the InferOps ASGI application.

This package holds one thing and depends on almost nothing: the carrier, and
`inferops.api.application` for the type it serves. That is the whole point of its
existence as a package.

It used to live in `tools.local_composition`, whose `__init__` imports
`tools.model_acquisition`, `tools.runtime_configuration` and
`tools.runtime_packaging` -- a manifest reader, a profile loader and a container
packager, none of which a serving process has any business importing. Reaching
the carrier through that package meant dragging all of it along, and the API
container image would have had to ship a model downloader to serve a request.

So the carrier moved here and `tools/local_composition/http_server.py` became a
re-export. Nothing that imported it before has to change, every path named in the
proof records still resolves, and a container entrypoint can now import a carrier
without importing the host's tooling.

What this package does *not* decide is where the carrier binds. `LocalApiServer`
takes a host and a port and serves on them. The host composition passes loopback
and validates that it did -- `tools.local_composition.core` refuses a composition
whose API host is not `127.0.0.1` -- and the container entrypoint passes an
address reachable from a Service and says so explicitly. Neither rule lives in
here, because a carrier that silently preferred one would make the other's check
a formality.
"""

from __future__ import annotations

from .http_server import (
    BODY_READ_TIMEOUT_SECONDS,
    LIFESPAN_TIMEOUT_SECONDS,
    AsgiResponse,
    LocalApiServer,
    LocalHttpServerError,
)

__all__ = [
    "BODY_READ_TIMEOUT_SECONDS",
    "LIFESPAN_TIMEOUT_SECONDS",
    "AsgiResponse",
    "LocalApiServer",
    "LocalHttpServerError",
]
