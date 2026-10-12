"""The operator events of one experiment run, as one log.

The control of a run and an operator record events that no cluster object and
no metric holds: a fault injection, a reviewed detection, a reversal that was
decided, created, and accepted, an abort, and a manual action. This package
appends one line for each event to one log, with the instant of the record in
UTC, and it holds a stored log to its form. A log holds no free text.

See docs/environment/experiment-operator-events.md, which describes the kinds,
the members, the clocks, and the limits, and
tests/domain/test_experiment_events.py.
"""

from . import core
from .core import *  # noqa: F403

__all__ = list(core.__all__)
