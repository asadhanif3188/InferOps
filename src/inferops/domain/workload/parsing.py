"""Reading a WorkloadContract document into the platform's own objects.

The entry point is :func:`parse_workload_contract`. It takes the JSON wire form of
a document — a mapping, already loaded from YAML or JSON by whoever owns that —
and returns a :class:`~inferops.domain.workload.contract.WorkloadContract`, or
raises.

**What it enforces, and what it deliberately does not.** The line is the same one
the contract document already publishes between its two validation layers:

- *enforced here*: the document is a mapping; every required field is present;
  every value is of the JSON type its field declares; every closed object carries
  only fields this contract version defines; and every value with a published
  vocabulary, format, length, or bound satisfies it. None of that is a policy
  choice — it is what having a typed object at all requires;
- *not enforced here*: every rule that compares two fields, consults the runtime
  and model compatibility matrix, or judges whether a value is plausible. The
  profile and its block, the replica range, the duplicate secret name, the pasted
  credential, the mock that declares a secret. Those are the published semantic
  rules, and the pipeline that applies them — with canonical error codes, rule
  identifiers, and a full finding set rather than one exception — is
  ``V1-S1-001-PR2``.

**It stops at the first problem.** A parse answers one question, "can this be read
as a domain object", and the answer is no as soon as one thing cannot be. The
validation pipeline is the surface that owes an author every reason at once; this
one owes them a value or an exception.

**A refusal names a field and a constraint, and never a value.** Two consequences
follow that are easier to notice here than to discover later. A refused enum lists
the permitted values, because those are the schema's own published vocabulary. An
unknown field is *not* named: an undefined field name is author-supplied text like
any other, this parser has no credential heuristic — that is the semantic layer's —
and so the refusal reports how many undefined fields an object carries and which
fields this version defines, leaving the reader to diff two lists that are both
safe to print. A consumer that needs the offending name located is running the
published schema validator, whose redaction rule for exactly this case is measured
in ``docs/contracts/workload-contract.md``.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping, Sequence
from enum import StrEnum
from types import MappingProxyType
from typing import Any

from ..context import NO_REQUEST_CONTEXT, RequestContext
from .contract import (
    Accelerator,
    Attribution,
    CapabilityDependency,
    EvidenceReferences,
    Integrations,
    MockLlmProfile,
    ModelArtifact,
    ModelReference,
    ResourceRequest,
    RuntimeImage,
    ScalingPolicy,
    SecretReference,
    SecurityPolicy,
    SynchronousLlmProfile,
    WorkloadContract,
    WorkloadMetadata,
    WorkloadSpec,
)
from .errors import (
    InvalidValueError,
    MalformedWorkloadContractError,
    UnsupportedContractVersionError,
)
from .values import (
    ACCELERATOR_COUNT_CEILING,
    ACCELERATOR_COUNT_FLOOR,
    ARTIFACT_SIZE_BYTES_FLOOR,
    MAXIMUM_PROOF_REFERENCES,
    MAXIMUM_REPLICAS_CEILING,
    MAXIMUM_REPLICAS_FLOOR,
    MAXIMUM_SECRET_REFERENCES,
    MINIMUM_REPLICAS_CEILING,
    MINIMUM_REPLICAS_FLOOR,
    AcceleratorType,
    AnnotationKey,
    AnnotationValue,
    ArtifactFile,
    ArtifactRepository,
    ConstrainedString,
    DataClassification,
    Description,
    DnsLabel,
    Environment,
    ImageReference,
    KebabCaseName,
    MockDeterminism,
    Profile,
    RepositoryPath,
    ResourceQuantity,
    RuntimeProfile,
    SecretLocator,
    SecretProvider,
    SecretRotation,
    ServingCapability,
    Sha256Digest,
    UpstreamRevision,
    WorkloadVersion,
)
from .versions import WORKLOAD_CONTRACT_KIND, ContractVersion

# The fields each closed object defines, in the order the schema lists them. They
# are used for two things: refusing a field this version does not define, and
# telling a reader which fields it does.
_ROOT_FIELDS = ("apiVersion", "kind", "metadata", "spec")
_METADATA_FIELDS = ("name", "version", "owner", "description", "annotations")
_SPEC_FIELDS = (
    "profile",
    "environment",
    "model",
    "resources",
    "scaling",
    "integrations",
    "security",
    "attribution",
    "evidence",
    "synchronousLlm",
    "mockLlm",
)
_MODEL_FIELDS = ("servingCapability", "modelRef", "runtimeProfile")
_RESOURCES_FIELDS = ("cpu", "memory", "accelerator")
_ACCELERATOR_FIELDS = ("type", "count")
_SCALING_FIELDS = ("minimumReplicas", "maximumReplicas")
_INTEGRATIONS_FIELDS = ("modelAccess", "telemetry", "evaluation")
_INTEGRATION_FIELDS = ("capabilityRef", "required")
_SECURITY_FIELDS = ("dataClassification", "secretRefs")
_SECRET_REFERENCE_FIELDS = ("name", "provider", "reference", "owner", "rotation")
_ATTRIBUTION_FIELDS = ("tenant", "costCenter")
_EVIDENCE_FIELDS = ("runbookRef", "proofRefs")
_SYNCHRONOUS_LLM_FIELDS = ("runtime", "modelArtifact")
_RUNTIME_FIELDS = ("imageReference",)
_MODEL_ARTIFACT_FIELDS = ("repository", "revision", "file", "sizeBytes", "sha256")
_MOCK_LLM_FIELDS = ("ciOnly", "determinism", "fixtureRef")


# --------------------------------------------------------------------------
# Reading primitives. Each one knows the field path it is reading at, because a
# refusal that cannot say where it happened makes the author bisect the document.
# --------------------------------------------------------------------------


def _refuse(
    field: str, reason: str, context: RequestContext
) -> MalformedWorkloadContractError:
    return MalformedWorkloadContractError(field, reason, context=context)


def _mapping(value: object, field: str, context: RequestContext) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise _refuse(field, "value must be a JSON object", context)
    for key in value:
        if not isinstance(key, str):
            raise _refuse(field, "every field name must be a string", context)
    return value


def _closed(
    mapping: Mapping[str, Any],
    field: str,
    defined: Sequence[str],
    context: RequestContext,
) -> None:
    """Refuse a field this contract version does not define, without naming it."""
    undefined = [key for key in mapping if key not in defined]
    if not undefined:
        return
    count = len(undefined)
    subject = "field" if count == 1 else "fields"
    raise _refuse(
        field,
        f"this object carries {count} {subject} that this contract version does "
        f"not define; the fields it defines are {', '.join(defined)}",
        context,
    )


def _required(
    mapping: Mapping[str, Any], field: str, key: str, context: RequestContext
) -> Any:
    if key not in mapping:
        raise _refuse(f"{field}.{key}", "required field is missing", context)
    return mapping[key]


def _string(value: object, field: str, context: RequestContext) -> str:
    if not isinstance(value, str):
        raise _refuse(field, "value must be of JSON type string", context)
    return value


def _boolean(value: object, field: str, context: RequestContext) -> bool:
    if not isinstance(value, bool):
        raise _refuse(field, "value must be of JSON type boolean", context)
    return value


def _integer(
    value: object,
    field: str,
    context: RequestContext,
    *,
    floor: int,
    ceiling: int | None = None,
) -> int:
    """One JSON integer, read the way JSON Schema defines the type.

    Two things about that definition are easy to get wrong in Python, and both
    would make this parser disagree with the published schema:

    - `True` is an instance of `int` here and is not an integer in JSON. Without
      the first branch the schema's numeric bounds would silently accept a
      boolean;
    - `5.0` **is** an integer in JSON Schema 2020-12, which defines the type by
      the value rather than by how it was written. The validator the contract
      tooling uses accepts it, so refusing it here would make the domain stricter
      than the contract it implements - a document the platform accepts that the
      domain cannot hold. It is read, and it is held as the integer it is, which
      means `as_document()` rebuilds it as `5` rather than as `5.0`.
    """
    if isinstance(value, bool):
        raise _refuse(field, "value must be of JSON type integer", context)
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if not isinstance(value, int):
        raise _refuse(field, "value must be of JSON type integer", context)
    if value < floor:
        raise _refuse(field, f"value must be at least {floor}", context)
    if ceiling is not None and value > ceiling:
        raise _refuse(field, f"value must be at most {ceiling}", context)
    return value


def _sequence(
    value: object, field: str, context: RequestContext, *, maximum_items: int
) -> Sequence[Any]:
    if not isinstance(value, list):
        raise _refuse(field, "value must be a JSON array", context)
    if len(value) > maximum_items:
        raise _refuse(
            field, f"array must carry at most {maximum_items} entries", context
        )
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
    """Read one member of a controlled vocabulary, or list the vocabulary.

    The permitted values are printed and the refused one is not. The permitted set
    is the schema's own published enumeration; the value that failed to be a
    member of it came out of the document.
    """
    raw = _string(value, field, context)
    try:
        return kind(raw)
    except ValueError as error:
        permitted = _permitted(member.value for member in kind.__members__.values())
        raise _refuse(
            field,
            f"value is not one of the permitted values: {permitted}",
            context,
        ) from error


# --------------------------------------------------------------------------
# The document
# --------------------------------------------------------------------------


def parse_workload_contract(
    document: object,
    *,
    context: RequestContext = NO_REQUEST_CONTEXT,
) -> WorkloadContract:
    """Read one WorkloadContract document into a domain object.

    Args:
        document: the JSON wire form of the document — a mapping, as produced by
            ``json.load`` or by a YAML loader restricted to the JSON-representable
            subset. This function does not read files and does not parse YAML: the
            authoring form is the contract tooling's concern, and a domain that
            loaded documents would be a domain with a file system.
        context: the request-scoped identifiers a trusted component assigned, when
            there is a request. They are attached to any error raised. Nothing here
            generates one.

    Returns:
        The document as typed domain objects.

    Raises:
        UnsupportedContractVersionError: the document declares no contract
            version, or one this package does not implement.
        MalformedWorkloadContractError: the document declares a supported version
            and cannot be read as one.
    """
    root = _mapping(document, "$", context)

    # The version is read first and refused first. Every field path below this
    # point is a path in a version this package implements, so applying one to a
    # document that declares another version would describe a shape this package
    # has no claim over.
    if "apiVersion" not in root:
        raise UnsupportedContractVersionError(
            "$.apiVersion",
            "a document must declare its contract version explicitly; a version "
            "is never inferred from the document's shape",
            context=context,
        )
    api_version = ContractVersion.parse(root["apiVersion"], context=context)

    _closed(root, "$", _ROOT_FIELDS, context)

    kind = _string(_required(root, "$", "kind", context), "$.kind", context)
    if kind != WORKLOAD_CONTRACT_KIND:
        raise _refuse(
            "$.kind",
            f"value must be {WORKLOAD_CONTRACT_KIND!r} in this position",
            context,
        )

    metadata = _parse_metadata(
        _mapping(_required(root, "$", "metadata", context), "$.metadata", context),
        context,
    )
    spec = _parse_spec(
        _mapping(_required(root, "$", "spec", context), "$.spec", context),
        context,
    )
    return WorkloadContract(
        api_version=api_version, kind=kind, metadata=metadata, spec=spec
    )


def _parse_metadata(
    metadata: Mapping[str, Any], context: RequestContext
) -> WorkloadMetadata:
    field = "$.metadata"
    _closed(metadata, field, _METADATA_FIELDS, context)

    name = _constrained(
        DnsLabel, _required(metadata, field, "name", context), f"{field}.name", context
    )
    raw_version = _string(
        _required(metadata, field, "version", context), f"{field}.version", context
    )
    try:
        version = WorkloadVersion.parse(raw_version)
    except InvalidValueError as error:
        raise _refuse(f"{field}.version", error.reason, context) from error
    owner = _constrained(
        DnsLabel,
        _required(metadata, field, "owner", context),
        f"{field}.owner",
        context,
    )

    description: Description | None = None
    if "description" in metadata:
        description = _constrained(
            Description, metadata["description"], f"{field}.description", context
        )

    annotations: Mapping[str, str] | None = None
    if "annotations" in metadata:
        annotations = _parse_annotations(
            _mapping(metadata["annotations"], f"{field}.annotations", context),
            f"{field}.annotations",
            context,
        )

    return WorkloadMetadata(
        name=name,
        version=version,
        owner=owner,
        description=description,
        annotations=annotations,
    )


def _parse_annotations(
    annotations: Mapping[str, Any], field: str, context: RequestContext
) -> Mapping[str, str]:
    """Check every key and value, and keep the mapping as the author wrote it.

    Annotations are the contract's one open map, so both halves of each entry are
    author-controlled text. The key format and the value length bound are the
    schema's, and neither the key nor the value is repeated in a refusal.
    """
    checked: dict[str, str] = {}
    for key, value in annotations.items():
        try:
            AnnotationKey(key)
        except InvalidValueError as error:
            raise _refuse(
                field,
                f"an annotation key is not well formed: {error.reason}",
                context,
            ) from error
        try:
            AnnotationValue(_string(value, field, context))
        except InvalidValueError as error:
            raise _refuse(
                field,
                f"an annotation value is not well formed: {error.reason}",
                context,
            ) from error
        checked[key] = value
    return MappingProxyType(checked)


def _parse_spec(spec: Mapping[str, Any], context: RequestContext) -> WorkloadSpec:
    field = "$.spec"
    _closed(spec, field, _SPEC_FIELDS, context)

    profile = _vocabulary(
        Profile, _required(spec, field, "profile", context), f"{field}.profile", context
    )
    environment = _vocabulary(
        Environment,
        _required(spec, field, "environment", context),
        f"{field}.environment",
        context,
    )
    model = _parse_model(
        _mapping(_required(spec, field, "model", context), f"{field}.model", context),
        context,
    )
    resources = _parse_resources(
        _mapping(
            _required(spec, field, "resources", context), f"{field}.resources", context
        ),
        context,
    )
    scaling = _parse_scaling(
        _mapping(
            _required(spec, field, "scaling", context), f"{field}.scaling", context
        ),
        context,
    )
    integrations = _parse_integrations(
        _mapping(
            _required(spec, field, "integrations", context),
            f"{field}.integrations",
            context,
        ),
        context,
    )
    security = _parse_security(
        _mapping(
            _required(spec, field, "security", context), f"{field}.security", context
        ),
        context,
    )
    attribution = _parse_attribution(
        _mapping(
            _required(spec, field, "attribution", context),
            f"{field}.attribution",
            context,
        ),
        context,
    )
    evidence = _parse_evidence(
        _mapping(
            _required(spec, field, "evidence", context), f"{field}.evidence", context
        ),
        context,
    )

    synchronous_llm: SynchronousLlmProfile | None = None
    if "synchronousLlm" in spec:
        synchronous_llm = _parse_synchronous_llm(
            _mapping(spec["synchronousLlm"], f"{field}.synchronousLlm", context),
            context,
        )
    mock_llm: MockLlmProfile | None = None
    if "mockLlm" in spec:
        mock_llm = _parse_mock_llm(
            _mapping(spec["mockLlm"], f"{field}.mockLlm", context), context
        )

    return WorkloadSpec(
        profile=profile,
        environment=environment,
        model=model,
        resources=resources,
        scaling=scaling,
        integrations=integrations,
        security=security,
        attribution=attribution,
        evidence=evidence,
        synchronous_llm=synchronous_llm,
        mock_llm=mock_llm,
    )


def _parse_model(model: Mapping[str, Any], context: RequestContext) -> ModelReference:
    field = "$.spec.model"
    _closed(model, field, _MODEL_FIELDS, context)
    return ModelReference(
        serving_capability=_vocabulary(
            ServingCapability,
            _required(model, field, "servingCapability", context),
            f"{field}.servingCapability",
            context,
        ),
        model_ref=_constrained(
            KebabCaseName,
            _required(model, field, "modelRef", context),
            f"{field}.modelRef",
            context,
        ),
        runtime_profile=_vocabulary(
            RuntimeProfile,
            _required(model, field, "runtimeProfile", context),
            f"{field}.runtimeProfile",
            context,
        ),
    )


def _parse_resources(
    resources: Mapping[str, Any], context: RequestContext
) -> ResourceRequest:
    field = "$.spec.resources"
    _closed(resources, field, _RESOURCES_FIELDS, context)
    accelerator_field = f"{field}.accelerator"
    accelerator = _mapping(
        _required(resources, field, "accelerator", context), accelerator_field, context
    )
    _closed(accelerator, accelerator_field, _ACCELERATOR_FIELDS, context)
    return ResourceRequest(
        cpu=_constrained(
            ResourceQuantity,
            _required(resources, field, "cpu", context),
            f"{field}.cpu",
            context,
        ),
        memory=_constrained(
            ResourceQuantity,
            _required(resources, field, "memory", context),
            f"{field}.memory",
            context,
        ),
        accelerator=Accelerator(
            type=_vocabulary(
                AcceleratorType,
                _required(accelerator, accelerator_field, "type", context),
                f"{accelerator_field}.type",
                context,
            ),
            count=_integer(
                _required(accelerator, accelerator_field, "count", context),
                f"{accelerator_field}.count",
                context,
                floor=ACCELERATOR_COUNT_FLOOR,
                ceiling=ACCELERATOR_COUNT_CEILING,
            ),
        ),
    )


def _parse_scaling(
    scaling: Mapping[str, Any], context: RequestContext
) -> ScalingPolicy:
    field = "$.spec.scaling"
    _closed(scaling, field, _SCALING_FIELDS, context)
    return ScalingPolicy(
        minimum_replicas=_integer(
            _required(scaling, field, "minimumReplicas", context),
            f"{field}.minimumReplicas",
            context,
            floor=MINIMUM_REPLICAS_FLOOR,
            ceiling=MINIMUM_REPLICAS_CEILING,
        ),
        maximum_replicas=_integer(
            _required(scaling, field, "maximumReplicas", context),
            f"{field}.maximumReplicas",
            context,
            floor=MAXIMUM_REPLICAS_FLOOR,
            ceiling=MAXIMUM_REPLICAS_CEILING,
        ),
    )


def _parse_integrations(
    integrations: Mapping[str, Any], context: RequestContext
) -> Integrations:
    field = "$.spec.integrations"
    _closed(integrations, field, _INTEGRATIONS_FIELDS, context)
    telemetry = _parse_integration(
        _mapping(
            _required(integrations, field, "telemetry", context),
            f"{field}.telemetry",
            context,
        ),
        f"{field}.telemetry",
        context,
    )
    model_access = (
        _parse_integration(
            _mapping(integrations["modelAccess"], f"{field}.modelAccess", context),
            f"{field}.modelAccess",
            context,
        )
        if "modelAccess" in integrations
        else None
    )
    evaluation = (
        _parse_integration(
            _mapping(integrations["evaluation"], f"{field}.evaluation", context),
            f"{field}.evaluation",
            context,
        )
        if "evaluation" in integrations
        else None
    )
    return Integrations(
        telemetry=telemetry, model_access=model_access, evaluation=evaluation
    )


def _parse_integration(
    integration: Mapping[str, Any], field: str, context: RequestContext
) -> CapabilityDependency:
    _closed(integration, field, _INTEGRATION_FIELDS, context)
    return CapabilityDependency(
        capability_ref=_constrained(
            KebabCaseName,
            _required(integration, field, "capabilityRef", context),
            f"{field}.capabilityRef",
            context,
        ),
        required=_boolean(
            _required(integration, field, "required", context),
            f"{field}.required",
            context,
        ),
    )


def _parse_security(
    security: Mapping[str, Any], context: RequestContext
) -> SecurityPolicy:
    field = "$.spec.security"
    _closed(security, field, _SECURITY_FIELDS, context)
    entries = _sequence(
        _required(security, field, "secretRefs", context),
        f"{field}.secretRefs",
        context,
        maximum_items=MAXIMUM_SECRET_REFERENCES,
    )
    secret_refs = tuple(
        _parse_secret_reference(
            _mapping(entry, f"{field}.secretRefs[{index}]", context),
            f"{field}.secretRefs[{index}]",
            context,
        )
        for index, entry in enumerate(entries)
    )
    return SecurityPolicy(
        data_classification=_vocabulary(
            DataClassification,
            _required(security, field, "dataClassification", context),
            f"{field}.dataClassification",
            context,
        ),
        secret_refs=secret_refs,
    )


def _parse_secret_reference(
    entry: Mapping[str, Any], field: str, context: RequestContext
) -> SecretReference:
    _closed(entry, field, _SECRET_REFERENCE_FIELDS, context)
    return SecretReference(
        name=_constrained(
            KebabCaseName,
            _required(entry, field, "name", context),
            f"{field}.name",
            context,
        ),
        provider=_vocabulary(
            SecretProvider,
            _required(entry, field, "provider", context),
            f"{field}.provider",
            context,
        ),
        reference=_constrained(
            SecretLocator,
            _required(entry, field, "reference", context),
            f"{field}.reference",
            context,
        ),
        owner=_constrained(
            DnsLabel,
            _required(entry, field, "owner", context),
            f"{field}.owner",
            context,
        ),
        rotation=_vocabulary(
            SecretRotation,
            _required(entry, field, "rotation", context),
            f"{field}.rotation",
            context,
        ),
    )


def _parse_attribution(
    attribution: Mapping[str, Any], context: RequestContext
) -> Attribution:
    field = "$.spec.attribution"
    _closed(attribution, field, _ATTRIBUTION_FIELDS, context)
    return Attribution(
        tenant=_constrained(
            DnsLabel,
            _required(attribution, field, "tenant", context),
            f"{field}.tenant",
            context,
        ),
        cost_center=_constrained(
            KebabCaseName,
            _required(attribution, field, "costCenter", context),
            f"{field}.costCenter",
            context,
        ),
    )


def _parse_evidence(
    evidence: Mapping[str, Any], context: RequestContext
) -> EvidenceReferences:
    field = "$.spec.evidence"
    _closed(evidence, field, _EVIDENCE_FIELDS, context)
    proof_refs: tuple[RepositoryPath, ...] | None = None
    if "proofRefs" in evidence:
        entries = _sequence(
            evidence["proofRefs"],
            f"{field}.proofRefs",
            context,
            maximum_items=MAXIMUM_PROOF_REFERENCES,
        )
        proof_refs = tuple(
            _constrained(RepositoryPath, entry, f"{field}.proofRefs[{index}]", context)
            for index, entry in enumerate(entries)
        )
    return EvidenceReferences(
        runbook_ref=_constrained(
            RepositoryPath,
            _required(evidence, field, "runbookRef", context),
            f"{field}.runbookRef",
            context,
        ),
        proof_refs=proof_refs,
    )


def _parse_synchronous_llm(
    block: Mapping[str, Any], context: RequestContext
) -> SynchronousLlmProfile:
    field = "$.spec.synchronousLlm"
    _closed(block, field, _SYNCHRONOUS_LLM_FIELDS, context)

    runtime_field = f"{field}.runtime"
    runtime = _mapping(
        _required(block, field, "runtime", context), runtime_field, context
    )
    _closed(runtime, runtime_field, _RUNTIME_FIELDS, context)

    artifact_field = f"{field}.modelArtifact"
    artifact = _mapping(
        _required(block, field, "modelArtifact", context), artifact_field, context
    )
    _closed(artifact, artifact_field, _MODEL_ARTIFACT_FIELDS, context)

    return SynchronousLlmProfile(
        runtime=RuntimeImage(
            image_reference=_constrained(
                ImageReference,
                _required(runtime, runtime_field, "imageReference", context),
                f"{runtime_field}.imageReference",
                context,
            )
        ),
        model_artifact=ModelArtifact(
            repository=_constrained(
                ArtifactRepository,
                _required(artifact, artifact_field, "repository", context),
                f"{artifact_field}.repository",
                context,
            ),
            revision=_constrained(
                UpstreamRevision,
                _required(artifact, artifact_field, "revision", context),
                f"{artifact_field}.revision",
                context,
            ),
            file=_constrained(
                ArtifactFile,
                _required(artifact, artifact_field, "file", context),
                f"{artifact_field}.file",
                context,
            ),
            size_bytes=_integer(
                _required(artifact, artifact_field, "sizeBytes", context),
                f"{artifact_field}.sizeBytes",
                context,
                floor=ARTIFACT_SIZE_BYTES_FLOOR,
            ),
            sha256=_constrained(
                Sha256Digest,
                _required(artifact, artifact_field, "sha256", context),
                f"{artifact_field}.sha256",
                context,
            ),
        ),
    )


def _parse_mock_llm(
    block: Mapping[str, Any], context: RequestContext
) -> MockLlmProfile:
    field = "$.spec.mockLlm"
    _closed(block, field, _MOCK_LLM_FIELDS, context)
    ci_only = _boolean(
        _required(block, field, "ciOnly", context), f"{field}.ciOnly", context
    )
    if ci_only is not True:
        # A constant in the schema, and carried rather than assumed: the label is
        # written into the artifact so that it survives being copied.
        raise _refuse(f"{field}.ciOnly", "value must be true in this position", context)
    return MockLlmProfile(
        ci_only=ci_only,
        determinism=_vocabulary(
            MockDeterminism,
            _required(block, field, "determinism", context),
            f"{field}.determinism",
            context,
        ),
        fixture_ref=_constrained(
            RepositoryPath,
            _required(block, field, "fixtureRef", context),
            f"{field}.fixtureRef",
            context,
        ),
    )


__all__ = ["parse_workload_contract"]
