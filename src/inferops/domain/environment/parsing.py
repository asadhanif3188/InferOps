"""Reading an EnvironmentBinding document into the platform's own objects.

The entry point is :func:`parse_environment_binding`. It takes the JSON wire form
of one document - a mapping, already loaded from YAML or JSON by whoever owns that
- and returns an :class:`~inferops.domain.environment.binding.EnvironmentBinding`,
or raises.

**What it enforces.** Everything the published schema does: the document is a
mapping; the version is one this package implements, and is read first; every
object carries only the fields this version defines and every one of them; every
value is of its JSON type and satisfies its vocabulary, format, length, or bound.
The binding schema has no conditional requirement and no semantic layer, so for a
single document this parser and the schema refuse exactly the same documents. A
test runs both over every committed fixture.

**What it does not.** Anything that needs a second document: whether two bindings
conflict, and which binding serves a WorkloadContract. Those are in ``selection``.

**It stops at the first problem**, like the workload parser, and for the same
reason: a parse answers whether the document can be read as a domain object. The
offline validator is the surface that reports every structural reason at once.

**A refusal names a field and a constraint, and never a value.** An undefined
field is not named either - a field name is author-supplied text - so the refusal
says how many undefined fields an object carries and lists the fields it defines.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from enum import StrEnum
from typing import Any

from ..context import NO_REQUEST_CONTEXT, RequestContext
from ..workload.errors import InvalidValueError
from ..workload.values import ConstrainedString, DnsLabel, Environment
from .binding import (
    BindingMetadata,
    BindingSpec,
    Destination,
    EnvironmentBinding,
    GitOpsDestination,
    ModelCache,
    PlatformSettings,
)
from .errors import MalformedEnvironmentBindingError, UnsupportedBindingVersionError
from .values import (
    API_REPLICAS_CEILING,
    API_REPLICAS_FLOOR,
    ClusterProvider,
    GitOpsPath,
    ModelCacheClass,
    ReleaseNamespace,
)
from .versions import ENVIRONMENT_BINDING_KIND, BindingVersion

# The fields each closed object defines, in the order the schema lists them. A
# test compares every list with the schema.
_ROOT_FIELDS = ("apiVersion", "kind", "metadata", "spec")
_METADATA_FIELDS = ("name", "owner")
_SPEC_FIELDS = ("environment", "destination", "modelCache", "platform", "gitops")
_DESTINATION_FIELDS = ("clusterProvider", "namespace")
_MODEL_CACHE_FIELDS = ("class", "claimName")
_PLATFORM_FIELDS = ("apiReplicas",)
_GITOPS_FIELDS = ("destinationPath",)


# --------------------------------------------------------------------------
# Reading primitives. Each one knows the field path it is reading at.
# --------------------------------------------------------------------------


def _refuse(
    field: str, reason: str, context: RequestContext
) -> MalformedEnvironmentBindingError:
    return MalformedEnvironmentBindingError(field, reason, context=context)


def _object(
    value: object, field: str, defined: Sequence[str], context: RequestContext
) -> Mapping[str, Any]:
    """A closed JSON object carrying every field it defines and no other."""
    if not isinstance(value, Mapping):
        raise _refuse(field, "value must be a JSON object", context)
    for key in value:
        if not isinstance(key, str):
            raise _refuse(field, "every field name must be a string", context)
    undefined = [key for key in value if key not in defined]
    if undefined:
        count = len(undefined)
        subject = "field" if count == 1 else "fields"
        raise _refuse(
            field,
            f"this object carries {count} {subject} that this binding version does "
            f"not define; the fields it defines are {', '.join(defined)}",
            context,
        )
    for key in defined:
        if key not in value:
            raise _refuse(f"{field}.{key}", "required field is missing", context)
    return value


def _string(value: object, field: str, context: RequestContext) -> str:
    if not isinstance(value, str):
        raise _refuse(field, "value must be of JSON type string", context)
    return value


def _constrained[StringT: ConstrainedString](
    kind: type[StringT], value: object, field: str, context: RequestContext
) -> StringT:
    """Build a checked value, turning its own refusal into a located one."""
    raw = _string(value, field, context)
    try:
        return kind(raw)
    except InvalidValueError as error:
        raise _refuse(field, error.reason, context) from error


def _permitted(members: Iterable[str]) -> str:
    return ", ".join(repr(member) for member in members)


def _vocabulary[VocabularyT: StrEnum](
    kind: type[VocabularyT], value: object, field: str, context: RequestContext
) -> VocabularyT:
    """One member of a controlled vocabulary, or a refusal listing the vocabulary."""
    raw = _string(value, field, context)
    try:
        return kind(raw)
    except ValueError as error:
        permitted = _permitted(member.value for member in kind.__members__.values())
        raise _refuse(
            field, f"value is not one of the permitted values: {permitted}", context
        ) from error


def _integer(
    value: object, field: str, context: RequestContext, *, floor: int, ceiling: int
) -> int:
    """One JSON integer, read the way JSON Schema 2020-12 defines the type.

    A boolean is not an integer in JSON although it is an ``int`` in Python, and
    ``2.0`` is an integer in JSON Schema 2020-12, which defines the type by value.
    Both are read the way the published validator reads them, so the domain is
    neither looser nor stricter than the schema it implements.
    """
    if isinstance(value, bool):
        raise _refuse(field, "value must be of JSON type integer", context)
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if not isinstance(value, int):
        raise _refuse(field, "value must be of JSON type integer", context)
    if value < floor:
        raise _refuse(field, f"value must be at least {floor}", context)
    if value > ceiling:
        raise _refuse(field, f"value must be at most {ceiling}", context)
    return value


# --------------------------------------------------------------------------
# The document
# --------------------------------------------------------------------------


def parse_environment_binding(
    document: object,
    *,
    context: RequestContext = NO_REQUEST_CONTEXT,
) -> EnvironmentBinding:
    """Read one EnvironmentBinding document into a domain object.

    Args:
        document: the JSON wire form of the document. This function does not read
            files and does not parse YAML.
        context: the request-scoped identifiers a trusted component assigned, when
            there is a request. They are attached to any error raised.

    Raises:
        UnsupportedBindingVersionError: the document declares no binding version,
            or one this package does not implement.
        MalformedEnvironmentBindingError: the document declares a supported
            version and cannot be read as one.
    """
    if not isinstance(document, Mapping):
        raise _refuse("$", "value must be a JSON object", context)

    # The version is read first and refused first: every path below it belongs to
    # a version this package implements.
    if "apiVersion" not in document:
        raise UnsupportedBindingVersionError(
            "$.apiVersion",
            "a binding must declare its version explicitly; a version is never "
            "inferred from the document's shape",
            context=context,
        )
    api_version = BindingVersion.parse(document["apiVersion"], context=context)

    root = _object(document, "$", _ROOT_FIELDS, context)
    kind = _string(root["kind"], "$.kind", context)
    if kind != ENVIRONMENT_BINDING_KIND:
        # A WorkloadContract declares the same apiVersion, so this is the check
        # that keeps one contract's document from being read as the other's.
        raise _refuse(
            "$.kind",
            f"value must be {ENVIRONMENT_BINDING_KIND!r} in this position",
            context,
        )

    return EnvironmentBinding(
        api_version=api_version,
        kind=kind,
        metadata=_parse_metadata(root["metadata"], context),
        spec=_parse_spec(root["spec"], context),
    )


def _parse_metadata(value: object, context: RequestContext) -> BindingMetadata:
    field = "$.metadata"
    metadata = _object(value, field, _METADATA_FIELDS, context)
    return BindingMetadata(
        name=_constrained(DnsLabel, metadata["name"], f"{field}.name", context),
        owner=_constrained(DnsLabel, metadata["owner"], f"{field}.owner", context),
    )


def _parse_spec(value: object, context: RequestContext) -> BindingSpec:
    field = "$.spec"
    spec = _object(value, field, _SPEC_FIELDS, context)
    return BindingSpec(
        environment=_vocabulary(
            Environment, spec["environment"], f"{field}.environment", context
        ),
        destination=_parse_destination(spec["destination"], context),
        model_cache=_parse_model_cache(spec["modelCache"], context),
        platform=_parse_platform(spec["platform"], context),
        gitops=_parse_gitops(spec["gitops"], context),
    )


def _parse_destination(value: object, context: RequestContext) -> Destination:
    field = "$.spec.destination"
    destination = _object(value, field, _DESTINATION_FIELDS, context)
    return Destination(
        cluster_provider=_vocabulary(
            ClusterProvider,
            destination["clusterProvider"],
            f"{field}.clusterProvider",
            context,
        ),
        namespace=_constrained(
            ReleaseNamespace, destination["namespace"], f"{field}.namespace", context
        ),
    )


def _parse_model_cache(value: object, context: RequestContext) -> ModelCache:
    field = "$.spec.modelCache"
    cache = _object(value, field, _MODEL_CACHE_FIELDS, context)
    return ModelCache(
        cache_class=_vocabulary(
            ModelCacheClass, cache["class"], f"{field}.class", context
        ),
        claim_name=_constrained(
            DnsLabel, cache["claimName"], f"{field}.claimName", context
        ),
    )


def _parse_platform(value: object, context: RequestContext) -> PlatformSettings:
    field = "$.spec.platform"
    platform = _object(value, field, _PLATFORM_FIELDS, context)
    return PlatformSettings(
        api_replicas=_integer(
            platform["apiReplicas"],
            f"{field}.apiReplicas",
            context,
            floor=API_REPLICAS_FLOOR,
            ceiling=API_REPLICAS_CEILING,
        )
    )


def _parse_gitops(value: object, context: RequestContext) -> GitOpsDestination:
    field = "$.spec.gitops"
    gitops = _object(value, field, _GITOPS_FIELDS, context)
    return GitOpsDestination(
        destination_path=_constrained(
            GitOpsPath, gitops["destinationPath"], f"{field}.destinationPath", context
        )
    )


__all__ = ["parse_environment_binding"]
