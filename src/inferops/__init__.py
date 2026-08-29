"""The InferOps distribution root.

This package holds the platform domain and nothing else. The packaging layout it
sits in — the src layout, the build backend, and the wheel this repository
produces — was decided and executed in ADR 0009 while this directory was still
empty; :mod:`inferops.domain` is what it was emptied for.

The dependency rule from ADR 0004 applies to everything under here: no Kubernetes
client, no Helm library, no serving-runtime SDK, no HTTP framework. The
distribution declares no runtime dependency at all, and
``tests/architecture/test_domain_dependency_boundary.py`` fails if a module
acquires one.

Repository tooling under ``tools/`` and the test suites under ``tests/`` are
deliberately outside the distribution and are not installed by it.

The distribution version is declared once, in ``pyproject.toml``. It is not
repeated here, because two places to change a version is one place to forget.
"""

from __future__ import annotations

__all__: list[str] = []
