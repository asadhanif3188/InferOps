"""Make the repository root importable so that `tools.*` resolves in tests.

The repository has no Python packaging yet - ADR 0003 explicitly does not settle
one - so there is nothing to install and no entry point to rely on. This file is
the smallest thing that lets `python -m pytest` from the repository root import
the contract validator without a `PYTHONPATH` incantation in every command.
"""

from __future__ import annotations

import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent

if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
