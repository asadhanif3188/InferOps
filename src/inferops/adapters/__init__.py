"""Serving adapters: implementations of the interface the domain owns.

The architecture puts the interface in the platform domain and the
implementations here, outside it. That direction is the whole point of the rule
in ADR 0004: the domain depends on no adapter, an adapter depends on the domain,
and the composition point picks one at startup.

Two adapters are foreseen and exactly one exists. :class:`MockServingAdapter`
replays a committed fixture, loads no model, and is CI only. The adapter for the
runtime selected in ADR 0002 is not written; what exists for it is
:mod:`inferops.adapters.llama_cpp`, which holds that runtime's pins, settings,
configuration translation, capability declaration, metadata parsing, and
readiness mapping, and which the adapter will compose when it is written. That
package is imported by name rather than re-exported here, because a runtime's
vocabulary staying inside its own package is the isolation this layout exists
for.

Everything under this package inherits the dependency rule that applies to the
rest of the distribution — no Kubernetes client, no Helm library, no
serving-runtime SDK, no HTTP framework — and
``tests/architecture/test_domain_dependency_boundary.py`` reads every module here
and fails if one acquires an import outside the standard library and this
distribution. For the mock that is not a constraint it strains against: a
fixture replayer needs nothing.

**Nothing here certifies serving.** What the mock produces is `mock` evidence,
whose ceiling is `C1` in
``docs/testing/certification.md``, and the rule it obeys is
``docs/serving/mock-and-real-boundary.md``.
"""

from __future__ import annotations

from .mock_serving import (
    MOCK_ADAPTER_KIND,
    MOCK_BOUNDARY_RULE_REF,
    MOCK_CAPABILITIES,
    MOCK_DETERMINISM,
    MOCK_EVIDENCE_CLASS,
    MOCK_FIXTURE_CONTENT,
    MOCK_FIXTURE_FINISH_REASON,
    MOCK_FIXTURE_REF,
    MOCK_MAX_CERTIFICATION,
    MOCK_MODEL_IDENTIFIER,
    MOCK_MODEL_IDENTIFIER_PREFIX,
    MOCK_NOTICE,
    MOCK_RUNTIME_ID,
    MOCK_RUNTIME_VERSION,
    MOCK_SERVING_CAPABILITY,
    MockAdapterSettings,
    MockScenario,
    MockServingAdapter,
)

__all__ = [
    "MOCK_ADAPTER_KIND",
    "MOCK_BOUNDARY_RULE_REF",
    "MOCK_CAPABILITIES",
    "MOCK_DETERMINISM",
    "MOCK_EVIDENCE_CLASS",
    "MOCK_FIXTURE_CONTENT",
    "MOCK_FIXTURE_FINISH_REASON",
    "MOCK_FIXTURE_REF",
    "MOCK_MAX_CERTIFICATION",
    "MOCK_MODEL_IDENTIFIER",
    "MOCK_MODEL_IDENTIFIER_PREFIX",
    "MOCK_NOTICE",
    "MOCK_RUNTIME_ID",
    "MOCK_RUNTIME_VERSION",
    "MOCK_SERVING_CAPABILITY",
    "MockAdapterSettings",
    "MockScenario",
    "MockServingAdapter",
]
