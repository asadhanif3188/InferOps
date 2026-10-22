"""The control of one V2-E02A run: the loss of the one runtime pod.

The package runs the procedure of the latest registered V2-E02A freeze record, in
its order, and decides each step from the record. ``core`` holds the decisions,
``control`` the order of the steps, and ``ports`` the reads and the acts. A dry run
reads a scenario file, executes nothing, and has no fault.

See docs/proof/experiments/v2-e02a/procedure/e02a-driver.txt, which is the one file
that runs a cluster command, docs/testing/experiment-e02a-control.md, and
tests/testing/test_experiment_e02a_control.py.
"""

from . import core
from .core import *  # noqa: F403

__all__ = list(core.__all__)
