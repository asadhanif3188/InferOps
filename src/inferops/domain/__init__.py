"""The InferOps platform domain.

This is the layer the architecture's dependency rule protects:

> Nothing in the platform domain may import a Kubernetes client, a Helm library,
> a serving-runtime SDK, or an HTTP framework.

The rule is in ADR 0004 and in ``docs/architecture/system-architecture.md``, and
it is checked rather than remembered:
``tests/architecture/test_domain_dependency_boundary.py`` reads every module under
this package and fails if one imports anything outside the standard library and
this distribution.

What lives here is the platform's own vocabulary — workload identity, ownership,
profile, model and runtime reference, resources, scaling, security
classification, attribution, and evidence references — expressed as typed objects
that know nothing about how a workload is deployed or served.

Today that is the workload contract domain model and nothing else. The
serving-adapter interface the domain will own is `V1-S1-002`, and no part of it
is anticipated here.
"""

from __future__ import annotations

from .context import NO_REQUEST_CONTEXT, RequestContext

__all__ = ["NO_REQUEST_CONTEXT", "RequestContext"]
