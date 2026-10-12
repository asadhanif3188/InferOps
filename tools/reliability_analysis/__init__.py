"""The reliability metrics of one experiment run, computed from its stored evidence.

The inputs are the caller record of the reliability runner, the timeline
streams, the log of operator events, and a declaration that states the
observation window, the expected state, and the signals. The output is one
analysis document: the caller failure episodes, the maximum success gap, the
intervals with no Ready endpoint, the detection lag and the two disagreement
times of each declared signal, and the stabilized recovery. A value that was not
read is not read as zero or as healthy, and the document lists each metric that
has no value. An analysis document states no result state, no percentage, and
no confidence interval.

See docs/testing/reliability-analysis.md, which states each definition, each
endpoint of each figure, the clocks, and the limits, and
tests/domain/test_reliability_analysis.py.
"""

from . import core
from .core import *  # noqa: F403

__all__ = list(core.__all__)
