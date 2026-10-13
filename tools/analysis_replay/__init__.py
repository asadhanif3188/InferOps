"""The analysis of an experiment run, bound to its evidence and computed again.

A run analysis is one document for one run directory. It states the digest of
each evidence file that the reliability analysis read, the raw evidence digest
of the run, the declaration, the analysis, and the code that computed it: a
commit identifier and a digest of the source files. A replay computes the
document again from the manifest, the evidence files, and the stated
declaration, and it compares the two byte for byte. A stored document that a
replay does not reproduce is not an analysis of the run.

An aggregate reads the run directories of one experiment, takes each result
state from its manifest, and gives the median of three counted runs with each
run listed. The evidence index refuses a run whose analysis does not replay.
No command here registers a claim or changes a claim status.

See docs/testing/analysis-replay.md, which states the document, each rule,
the limits, and what a replay does not establish, and
tests/testing/test_analysis_replay.py.
"""

from . import core
from .core import *  # noqa: F403

__all__ = list(core.__all__)
