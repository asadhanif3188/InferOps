"""Serve the InferOps API inside a container, and drain when told to.

**The bind address is stated, never defaulted.** ``INFEROPS_BIND_HOST`` and
``INFEROPS_BIND_PORT`` are both required and neither has a fallback. That is the
whole reason this module exists rather than a flag on the host composition
runner. The host composition binds `127.0.0.1` and
:mod:`tools.local_composition.core` refuses a composition that does not -- a real
boundary, and one this module does not touch. A container has to be reachable
from a Service, so it binds an address that is not loopback; making that a
required, named, logged input is what keeps it a decision somebody took rather
than a default that eroded the host rule by proximity. An unset variable is a
refusal, not an occasion to guess.

**The pod is the boundary, not the bind address.** Binding `0.0.0.0` inside a
container publishes on the pod's own network namespace, which is what a
`ClusterIP` Service and the kubelet's probes reach. It does not publish on the
node or the host. The chart's NetworkPolicy is what decides who may connect, and
`docs/security/security-baseline.v1alpha1.json` records that the accepted local
cluster's plugin does not enforce one -- so this is stated as the pod's exposure
and not as isolation.

**Shutdown is the part a container gets wrong.** Kubernetes sends `SIGTERM` and
then waits `terminationGracePeriodSeconds` before `SIGKILL`. The chart sets a
`preStop` sleep so the endpoint is withdrawn before the signal lands, and a drain
budget the application honours on lifespan shutdown. This module turns the signal
into the same three-step stop the host runner uses -- stop accepting, join, then
close and drain -- and exits nonzero if the drain did not complete, because a
container that reports success after dropping in-flight work teaches its operator
the wrong thing.

**PID 1 has no default signal handlers.** A container process started as PID 1
ignores `SIGTERM` unless it installs a handler, which is exactly how a pod ends up
being `SIGKILL`ed after its full grace period on every single rollout. The handler
below is installed before the server starts.
"""

from __future__ import annotations

import os
import signal
import sys
import threading
from collections.abc import Mapping
from types import FrameType

from inferops.api import MAX_REQUEST_BYTES
from inferops.api.selection import build
from inferops.domain.serving import InvalidAdapterConfigError
from tools.api_carrier import LocalApiServer, LocalHttpServerError

ENV_BIND_HOST = "INFEROPS_BIND_HOST"
ENV_BIND_PORT = "INFEROPS_BIND_PORT"
ENV_REQUEST_TIMEOUT_MS = "INFEROPS_REQUEST_TIMEOUT_MS"
ENV_DRAIN_TIMEOUT_MS = "INFEROPS_DRAIN_TIMEOUT_MS"

# The carrier waits this much longer than the application's own drain budget
# before it gives up, so that a drain finishing at the last moment is recorded as
# a drain and not as a timeout. The same margin the host composition uses.
SHUTDOWN_MARGIN_SECONDS = 5.0

EXIT_OK = 0
EXIT_CONFIGURATION = 2
EXIT_SHUTDOWN = 3
EXIT_STARTUP = 4


class ContainerEntrypointError(RuntimeError):
    """The container could not be configured, started, or stopped cleanly."""


def _required(environment: Mapping[str, str], name: str) -> str:
    """One variable, or a refusal that names it and never prints its value."""
    value = environment.get(name, "").strip()
    if not value:
        raise ContainerEntrypointError(
            f"{name} is required and was empty or unset. "
            "The container's serving address is stated by the deployment, "
            "never defaulted here."
        )
    return value


def _port(environment: Mapping[str, str]) -> int:
    raw = _required(environment, ENV_BIND_PORT)
    if not raw.isdigit():
        raise ContainerEntrypointError(f"{ENV_BIND_PORT} is not a whole number")
    port = int(raw)
    if not 1 <= port <= 65535:
        raise ContainerEntrypointError(f"{ENV_BIND_PORT} is outside 1-65535")
    # A container running as a non-root user cannot bind a privileged port, and
    # the chart runs every container as 65534. Saying so here beats a bare
    # "permission denied" from the socket layer.
    if port < 1024:
        raise ContainerEntrypointError(
            f"{ENV_BIND_PORT} is privileged, and this image runs unprivileged"
        )
    return port


def _milliseconds(environment: Mapping[str, str], name: str) -> int:
    raw = _required(environment, name)
    if not raw.isdigit() or int(raw) <= 0:
        raise ContainerEntrypointError(f"{name} is not a positive whole number")
    return int(raw)


def _log(event: str, **fields: object) -> None:
    """A startup line on stderr, where a container's logs are read from.

    Deliberately not the application's structured record sink: these describe the
    process around the application, and the sink belongs to the application's own
    telemetry. Keeping them apart is what stops a carrier line being read as an
    InferOps telemetry record.
    """
    rendered = " ".join(f"{key}={value}" for key, value in sorted(fields.items()))
    print(f"[inferops-api] {event} {rendered}".rstrip(), file=sys.stderr, flush=True)


def serve(environment: Mapping[str, str]) -> int:
    """Compose, serve, and drain. Returns the process exit status."""
    host = _required(environment, ENV_BIND_HOST)
    port = _port(environment)
    drain_ms = _milliseconds(environment, ENV_DRAIN_TIMEOUT_MS)
    response_ms = _milliseconds(environment, ENV_REQUEST_TIMEOUT_MS)

    application = build(environment)
    server = LocalApiServer(
        application,
        host=host,
        port=port,
        request_body_limit_bytes=MAX_REQUEST_BYTES,
        response_timeout_seconds=response_ms / 1000,
        shutdown_timeout_seconds=drain_ms / 1000 + SHUTDOWN_MARGIN_SECONDS,
    )

    # Installed before the socket exists, so a signal arriving during startup is
    # not the one signal this process ignores.
    #
    # `request_stop` is a no-op until the serving thread is actually alive, so a
    # signal is recorded here as well as acted on. Between `start()` returning
    # and `serve_in_background()`'s thread coming up there is a window in which
    # acting alone would do nothing, and the process would then block in `join()`
    # with nothing left to wake it -- deaf until SIGKILL, which is the exact
    # failure this module exists to prevent. The flag is re-read below, after the
    # thread exists, and the handler acts on every delivery rather than only the
    # first so that a repeated signal is not swallowed by the record of the one
    # that did nothing.
    stopping = threading.Event()

    def _on_signal(number: int, _frame: FrameType | None) -> None:
        if not stopping.is_set():
            stopping.set()
            _log("signal.received", signal=signal.Signals(number).name)
        server.request_stop()

    for received in (signal.SIGTERM, signal.SIGINT):
        signal.signal(received, _on_signal)

    server.start()
    _log("listening", host=host, port=server.bound_port, drainTimeoutMs=drain_ms)
    try:
        server.serve_in_background()
        if stopping.is_set():
            # A signal landed before there was a thread to stop. There is one now.
            server.request_stop()
        server.join()
    finally:
        server.request_stop()
        server.join()
        try:
            server.close()
        except LocalHttpServerError:
            _log("shutdown.incomplete", drained="false")
            return EXIT_SHUTDOWN
    _log("shutdown.complete", drained="true")
    return EXIT_OK


def main(environment: Mapping[str, str] | None = None) -> int:
    chosen = os.environ if environment is None else environment
    try:
        return serve(chosen)
    except (ContainerEntrypointError, InvalidAdapterConfigError) as error:
        # The adapter selection refuses a deployment that names no adapter or
        # names one whose settings are missing. Both are configuration, and both
        # exit distinctly from a shutdown failure so that a crash loop is
        # diagnosable from the exit status alone.
        _log("configuration.refused", reason=type(error).__name__)
        print(f"[inferops-api] FAILED: {error}", file=sys.stderr, flush=True)
        return EXIT_CONFIGURATION
    except LocalHttpServerError as error:
        # The carrier could not open its socket or bring up its event loop: a
        # port already taken, an address that does not exist on this interface.
        # It cleans up after itself, so there is nothing to unwind here -- but
        # letting it out would exit 1 with a traceback, and a crash-looping pod
        # is the worst place to have to read one to learn what happened.
        _log("startup.failed", reason=type(error).__name__)
        print(f"[inferops-api] FAILED: {error}", file=sys.stderr, flush=True)
        return EXIT_STARTUP


if __name__ == "__main__":
    raise SystemExit(main())
