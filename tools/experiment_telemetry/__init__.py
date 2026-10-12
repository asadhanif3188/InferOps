"""The telemetry readings of one experiment run, as two streams.

A collector script asks the telemetry collector of the release a registered set
of instant queries, a bounded number of times, and writes each read into one
directory. This package reads that directory and returns two streams:
``telemetry`` and ``resources``. Each reading states the two instants of its
read in UTC. A read that did not answer has a state and no result, and an
answer with no series is not a value of zero.

See docs/environment/experiment-telemetry.md, which describes the queries, the
collection, the streams, the clocks, and the limits, and
tests/domain/test_experiment_telemetry.py.
"""

from . import core
from .core import *  # noqa: F403

__all__ = list(core.__all__)
