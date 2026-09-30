"""Reading a RenderedWorkloadRelease document into the platform's own objects.

The entry point is :func:`parse_rendered_workload_release`. It takes the JSON
wire form of one document - a mapping, already loaded from YAML or JSON by
whoever owns that - and returns a
:class:`~inferops.domain.release.release.RenderedWorkloadRelease`, or raises.

**What it enforces.** Everything the published schema does: the document is a
mapping; the version is one this package implements, and is read first; every
object carries only the fields this version defines and every one of them; every
value is of its JSON type and satisfies its vocabulary, format, or length. The
release schema has no conditional requirement, so for a single document this
parser and the schema refuse exactly the same documents. A test runs both over
every committed fixture.

**What it does not.** Whether the release identifier is the derived one, whether a
value is shaped like a credential, and whether the release agrees with the
documents it names. Those are ``provenance``'s, and a release that parses has not
been judged by any of them.

**It stops at the first problem**, like the workload and binding parsers. The
offline validator is the surface that reports every structural reason at once.

**A refusal names a field and a constraint, and never a value.** An undefined
field is not named either - a field name is author-supplied text, and the field a
timestamp or a credential was pasted under is exactly the one a reader should not
see repeated - so the refusal says how many undefined fields an object carries and
lists the fields it defines.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from enum import StrEnum
from typing import Any

from ..context import NO_REQUEST_CONTEXT, RequestContext
from ..environment.versions import BindingVersion
from ..workload.errors import InvalidValueError
from ..workload.values import ConstrainedString, DnsLabel, Environment
from ..workload.versions import ContractVersion
from .errors import MalformedReleaseError, UnsupportedReleaseVersionError
from .release import (
    ContractReference,
    EnvironmentBindingReference,
    HelmValuesReference,
    PlatformDefaultsReference,
    ReleaseMetadata,
    ReleaseOutput,
    ReleaseSource,
    RenderedWorkloadRelease,
    RendererReference,
)
from .values import (
    GitRevision,
    ReleaseId,
    ReleaseWorkloadVersion,
    Sha256Hex,
    ValuesFileName,
    parse_release_workload_version,
)
from .versions import (
    RECORDABLE_BINDING_VERSIONS,
    RECORDABLE_CONTRACT_VERSIONS,
    RENDERED_WORKLOAD_RELEASE_KIND,
    ReleaseVersion,
)

# The fields each closed object defines, in the order the schema lists them. A
# test compares every list with the schema.
_ROOT_FIELDS = ("apiVersion", "kind", "metadata", "source", "output")
_METADATA_FIELDS = ("workloadId", "workloadVersion", "releaseId")
_SOURCE_FIELDS = ("contract", "environmentBinding", "renderer", "platformDefaults")
_CONTRACT_FIELDS = ("apiVersion", "sha256")
_BINDING_FIELDS = ("apiVersion", "environment", "name", "sha256")
_REVISION_FIELDS = ("revision",)
_OUTPUT_FIELDS = ("helmValues",)
_HELM_VALUES_FIELDS = ("path", "sha256")


# --------------------------------------------------------------------------
# Reading primitives. Each one knows the field path it is reading at.
# --------------------------------------------------------------------------


def _refuse(field: str, reason: str, context: RequestContext) -> MalformedReleaseError:
    return MalformedReleaseError(field, reason, context=context)


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
            f"this object carries {count} {subject} that this release version does "
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


def _recordable(
    value: object, field: str, permitted: Sequence[str], context: RequestContext
) -> str:
    """A source version this release version can record, or a refusal listing them."""
    raw = _string(value, field, context)
    if raw not in permitted:
        raise _refuse(
            field,
            f"value is not one of the permitted values: {_permitted(permitted)}",
            context,
        )
    return raw


def _workload_version(
    value: object, field: str, context: RequestContext
) -> ReleaseWorkloadVersion:
    raw = _string(value, field, context)
    try:
        return parse_release_workload_version(raw)
    except InvalidValueError as error:
        raise _refuse(field, error.reason, context) from error


# --------------------------------------------------------------------------
# The document
# --------------------------------------------------------------------------


def parse_rendered_workload_release(
    document: object,
    *,
    context: RequestContext = NO_REQUEST_CONTEXT,
) -> RenderedWorkloadRelease:
    """Read one RenderedWorkloadRelease document into a domain object.

    Args:
        document: the JSON wire form of the document. This function does not read
            files and does not parse YAML.
        context: the request-scoped identifiers a trusted component assigned, when
            there is a request. They are attached to any error raised.

    Raises:
        UnsupportedReleaseVersionError: the document declares no release version,
            or one this package does not implement.
        MalformedReleaseError: the document declares a supported version and
            cannot be read as one.
    """
    if not isinstance(document, Mapping):
        raise _refuse("$", "value must be a JSON object", context)

    # The version is read first and refused first: every path below it belongs to
    # a version this package implements.
    if "apiVersion" not in document:
        raise UnsupportedReleaseVersionError(
            "$.apiVersion",
            "a release must declare its version explicitly; a version is never "
            "inferred from the document's shape",
            context=context,
        )
    api_version = ReleaseVersion.parse(document["apiVersion"], context=context)

    root = _object(document, "$", _ROOT_FIELDS, context)
    kind = _string(root["kind"], "$.kind", context)
    if kind != RENDERED_WORKLOAD_RELEASE_KIND:
        # A WorkloadContract and a binding declare the same apiVersion, so this is
        # the check that keeps either from being read as a release.
        raise _refuse(
            "$.kind",
            f"value must be {RENDERED_WORKLOAD_RELEASE_KIND!r} in this position",
            context,
        )

    return RenderedWorkloadRelease(
        api_version=api_version,
        kind=kind,
        metadata=_parse_metadata(root["metadata"], context),
        source=_parse_source(root["source"], context),
        output=_parse_output(root["output"], context),
    )


def _parse_metadata(value: object, context: RequestContext) -> ReleaseMetadata:
    field = "$.metadata"
    metadata = _object(value, field, _METADATA_FIELDS, context)
    return ReleaseMetadata(
        workload_id=_constrained(
            DnsLabel, metadata["workloadId"], f"{field}.workloadId", context
        ),
        workload_version=_workload_version(
            metadata["workloadVersion"], f"{field}.workloadVersion", context
        ),
        release_id=_constrained(
            ReleaseId, metadata["releaseId"], f"{field}.releaseId", context
        ),
    )


def _parse_source(value: object, context: RequestContext) -> ReleaseSource:
    field = "$.source"
    source = _object(value, field, _SOURCE_FIELDS, context)
    return ReleaseSource(
        contract=_parse_contract(source["contract"], context),
        environment_binding=_parse_binding(source["environmentBinding"], context),
        renderer=RendererReference(
            revision=_parse_revision(source["renderer"], f"{field}.renderer", context)
        ),
        platform_defaults=PlatformDefaultsReference(
            revision=_parse_revision(
                source["platformDefaults"], f"{field}.platformDefaults", context
            )
        ),
    )


def _parse_contract(value: object, context: RequestContext) -> ContractReference:
    field = "$.source.contract"
    contract = _object(value, field, _CONTRACT_FIELDS, context)
    version = _recordable(
        contract["apiVersion"],
        f"{field}.apiVersion",
        RECORDABLE_CONTRACT_VERSIONS,
        context,
    )
    return ContractReference(
        api_version=ContractVersion.parse(version, context=context),
        sha256=_constrained(Sha256Hex, contract["sha256"], f"{field}.sha256", context),
    )


def _parse_binding(
    value: object, context: RequestContext
) -> EnvironmentBindingReference:
    field = "$.source.environmentBinding"
    binding = _object(value, field, _BINDING_FIELDS, context)
    version = _recordable(
        binding["apiVersion"],
        f"{field}.apiVersion",
        RECORDABLE_BINDING_VERSIONS,
        context,
    )
    return EnvironmentBindingReference(
        api_version=BindingVersion.parse(version, context=context),
        environment=_vocabulary(
            Environment, binding["environment"], f"{field}.environment", context
        ),
        name=_constrained(DnsLabel, binding["name"], f"{field}.name", context),
        sha256=_constrained(Sha256Hex, binding["sha256"], f"{field}.sha256", context),
    )


def _parse_revision(value: object, field: str, context: RequestContext) -> GitRevision:
    revision = _object(value, field, _REVISION_FIELDS, context)
    return _constrained(GitRevision, revision["revision"], f"{field}.revision", context)


def _parse_output(value: object, context: RequestContext) -> ReleaseOutput:
    field = "$.output"
    output = _object(value, field, _OUTPUT_FIELDS, context)
    values_field = f"{field}.helmValues"
    values = _object(output["helmValues"], values_field, _HELM_VALUES_FIELDS, context)
    return ReleaseOutput(
        helm_values=HelmValuesReference(
            path=_constrained(
                ValuesFileName, values["path"], f"{values_field}.path", context
            ),
            sha256=_constrained(
                Sha256Hex, values["sha256"], f"{values_field}.sha256", context
            ),
        )
    )


__all__ = ["parse_rendered_workload_release"]
