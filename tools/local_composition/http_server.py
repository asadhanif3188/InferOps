"""The HTTP carrier, re-exported from where it now lives.

The carrier moved to :mod:`tools.api_carrier` so that something which is not the
host composition -- the API container entrypoint -- can import it without also
importing this package's `__init__`, and through it the model manifest reader,
the runtime profile loader and the container packager.

This module stays because every caller here imported the carrier from this path,
and because the proof records for `V1-S2-003`, `V1-S2-005` and `V1-S2-008` name
it. A record that described a file which no longer exists would be a record a
reader cannot check, and those records are history rather than documentation to
be edited. So the path keeps resolving and the implementation lives elsewhere.

New code should import from :mod:`tools.api_carrier` directly.
"""

from __future__ import annotations

from tools.api_carrier.http_server import (
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
