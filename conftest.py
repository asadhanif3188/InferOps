"""Make the repository root importable so that `tools.*` resolves in tests.

The repository does have Python packaging now - ADR 0009 settled it - but `tools/`
is deliberately outside the distribution: it is repository tooling, and nothing
that installs `inferops` should acquire it. So there is still nothing to install
that would make `tools.contract_validation` importable, and this file remains the
smallest thing that lets `python -m pytest` from the repository root import the
contract validator without a `PYTHONPATH` incantation in every command.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
