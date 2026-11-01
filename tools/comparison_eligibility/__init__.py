"""The classification of the V2-E02A runs and their comparison eligibility.

The package reads the three run directories of V2-E02A, holds each to a replay of
its run analysis, and applies the eligibility rule of revision 4 of the record. It
states each run, the permitted medians, the verdict, and the handoff of rule G3.

It registers no claim and no freeze record, and it computes no percentage. No freeze
record pins it, and no tool that a run executes imports it.

See docs/testing/comparison-eligibility.md and
tests/testing/test_comparison_eligibility.py.
"""

from . import core
from .core import *  # noqa: F403

__all__ = list(core.__all__)
