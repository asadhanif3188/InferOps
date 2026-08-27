"""The InferOps distribution root.

This package is deliberately empty. It exists so that the packaging layout
decided in ADR 0009 is a built artifact rather than a described intention: the
src layout, the build backend, and the wheel this repository produces were all
executed against this directory before the decision was recorded as accepted.

The first InferOps-owned module belongs here. Repository tooling under
``tools/`` and the test suites under ``tests/`` are deliberately outside the
distribution and are not installed by it.

The distribution version is declared once, in ``pyproject.toml``. It is not
repeated here, because two places to change a version is one place to forget.
"""

from __future__ import annotations

__all__: list[str] = []
