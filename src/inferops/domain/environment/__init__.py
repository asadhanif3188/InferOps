"""The EnvironmentBinding as a platform domain object.

A binding carries the facts one environment supplies to a workload release that
are not the workload's intent: the cluster provider and namespace a release goes
to, the existing model cache claim it mounts, the platform API's replica count,
and where generated desired state is to be written. This package reads one into
typed objects and applies the rules that need more than one document. It deploys
nothing, renders nothing, and verifies nothing about a cluster.

Start at :func:`parse_environment_binding` for one document, and at
:func:`select_environment_binding` to find the binding that serves a
WorkloadContract among several. The objects are in ``binding``, the values they
are built from in ``values``, the supported versions in ``versions``, and every
refusal and published rule in ``errors``.

The published document is ``docs/contracts/environment-binding.md`` and the schema
is ``contracts/environment/environment-binding.v1alpha1.schema.json``. The domain
reads neither at run time; a test compares this package's copy of every pattern,
vocabulary, bound, and field list with the schema.
"""

from __future__ import annotations

from .binding import (
    BindingIdentity,
    BindingMetadata,
    BindingSpec,
    Destination,
    EnvironmentBinding,
    GitOpsDestination,
    ModelCache,
    PlatformSettings,
)
from .errors import (
    BINDING_RULES,
    BindingRefusal,
    BindingRule,
    BindingSelectionError,
    EnvironmentBindingError,
    MalformedEnvironmentBindingError,
    UnsupportedBindingVersionError,
)
from .parsing import parse_environment_binding
from .selection import select_environment_binding, validate_environment_bindings
from .values import (
    API_REPLICAS_CEILING,
    API_REPLICAS_FLOOR,
    ClusterProvider,
    GitOpsPath,
    ModelCacheClass,
    ReleaseNamespace,
)
from .versions import (
    ENVIRONMENT_BINDING_KIND,
    SUPPORTED_BINDING_VERSIONS,
    BindingVersion,
    is_supported_binding_version,
)

__all__ = [
    "API_REPLICAS_CEILING",
    "API_REPLICAS_FLOOR",
    "BINDING_RULES",
    "ENVIRONMENT_BINDING_KIND",
    "SUPPORTED_BINDING_VERSIONS",
    "BindingIdentity",
    "BindingMetadata",
    "BindingRefusal",
    "BindingRule",
    "BindingSelectionError",
    "BindingSpec",
    "BindingVersion",
    "ClusterProvider",
    "Destination",
    "EnvironmentBinding",
    "EnvironmentBindingError",
    "GitOpsDestination",
    "GitOpsPath",
    "MalformedEnvironmentBindingError",
    "ModelCache",
    "ModelCacheClass",
    "PlatformSettings",
    "ReleaseNamespace",
    "UnsupportedBindingVersionError",
    "is_supported_binding_version",
    "parse_environment_binding",
    "select_environment_binding",
    "validate_environment_bindings",
]
