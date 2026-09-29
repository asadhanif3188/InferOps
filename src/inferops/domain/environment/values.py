"""The typed values an EnvironmentBinding is built out of.

Every constraint here is a *single-field structural* constraint the published
binding schema already declares: a controlled vocabulary, a format, a length, or a
bound. The rules that compare one binding with another, or a binding with a
WorkloadContract, are in ``selection``.

Two values are not redefined here, on purpose. The environment is the key a
binding is matched on, and it is the WorkloadContract's own
:class:`~inferops.domain.workload.values.Environment` rather than a second
enumeration that could drift from it. The identifiers a binding carries - its
name, its owner, its claim name - are the same DNS label the WorkloadContract
uses for ``workload_id``, and they are the same type.

The patterns, vocabularies, and bounds are written in Python for the reason the
workload domain gives: the domain cannot import a JSON Schema validator. A test
reads ``contracts/environment/environment-binding.v1alpha1.schema.json`` and fails
if any of them differs from what the schema publishes.
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Final

from ..workload.values import ConstrainedString

# --------------------------------------------------------------------------
# Controlled vocabularies
# --------------------------------------------------------------------------


class ClusterProvider(StrEnum):
    """``spec.destination.clusterProvider``. The local cluster providers supported.

    The vocabulary is the local cluster provider contract's. A binding records a
    selection; it verifies nothing about the cluster it names.
    """

    KIND = "kind"
    DOCKER_DESKTOP = "docker-desktop"


class ModelCacheClass(StrEnum):
    """``spec.modelCache.class``. How the model cache is provided."""

    EXISTING_CLAIM = "existing-claim"


# --------------------------------------------------------------------------
# Constrained strings
# --------------------------------------------------------------------------

# The schema's own patterns, character for character, compared by a test.
RELEASE_NAMESPACE_PATTERN: Final = re.compile(
    r"^inferops-[a-z0-9]([-a-z0-9]*[a-z0-9])?$"
)
LOWERCASE_REPOSITORY_PATH_PATTERN: Final = re.compile(
    r"^[a-z0-9]([-a-z0-9]*[a-z0-9])?(/[a-z0-9]([-a-z0-9]*[a-z0-9])?)*$"
)


class ReleaseNamespace(ConstrainedString):
    """A namespace a release installs into, carrying the chart's required prefix.

    Referenced, not owned: the prerequisite layer creates the namespace, and
    neither a binding nor a release does.
    """

    NAME = "a release namespace"
    PATTERN = RELEASE_NAMESPACE_PATTERN
    # The schema declares no minLength here; the pattern already needs more than
    # one character. The floor is the base class's, and the agreement test reads
    # an absent minLength as that floor.
    MAXIMUM_LENGTH = 63


class GitOpsPath(ConstrainedString):
    """A repository-relative directory written as lowercase DNS-label segments.

    Absolute paths, parent traversal, drive letters, dots, and uppercase are all
    outside the pattern, so a binding cannot carry a personal filesystem path.
    """

    NAME = "a lowercase repository path"
    PATTERN = LOWERCASE_REPOSITORY_PATH_PATTERN
    MAXIMUM_LENGTH = 255

    @property
    def segments(self) -> tuple[str, ...]:
        """The path's directory names, root first."""
        return tuple(self.value.split("/"))


# --------------------------------------------------------------------------
# Published numeric bounds
# --------------------------------------------------------------------------

#: ``spec.platform.apiReplicas``: the bounds the chart's values schema accepts for
#: the API tier. A test holds the binding schema and the chart to the same pair.
API_REPLICAS_FLOOR: Final = 1
API_REPLICAS_CEILING: Final = 16


__all__ = [
    "API_REPLICAS_CEILING",
    "API_REPLICAS_FLOOR",
    "LOWERCASE_REPOSITORY_PATH_PATTERN",
    "RELEASE_NAMESPACE_PATTERN",
    "ClusterProvider",
    "GitOpsPath",
    "ModelCacheClass",
    "ReleaseNamespace",
]
