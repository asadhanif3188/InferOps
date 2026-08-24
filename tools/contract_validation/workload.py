"""Validation of a WorkloadContract document, structural and semantic.

Two layers, deliberately separated.

**Structural** validation is the published JSON Schema, applied by an off-the-shelf
draft 2020-12 validator. Every consumer in every language gets this layer for free
by validating against the schema file, which is the whole point of publishing one.

**Semantic** validation is the set of rules JSON Schema cannot express: comparing
two sibling values, consulting a compatibility matrix, or judging whether a string
that matches a locator pattern is in fact a pasted credential. ADR 0003 accepted
that split knowingly. This module is the second half of it, and it is the reason
the contract document can say which rules a raw-schema consumer does *not* get.

Everything here is offline and deterministic. It reads the document it was given,
the schema, and the compatibility matrix. No network, no cluster, no clock, no
randomness. The same document produces the same findings in the same order.

This is not a platform component. Nothing in this repository reads a
WorkloadContract at runtime, and this module does not change that: it validates
documents that live in this repository.
"""

from __future__ import annotations

import json
import math
import re
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator

from .errors import Finding, finding

REPO_ROOT = Path(__file__).resolve().parents[2]
SCHEMA_PATH = (
    REPO_ROOT / "contracts" / "workload" / "workload-contract.v1alpha1.schema.json"
)
COMPATIBILITY_MATRIX_PATH = (
    REPO_ROOT
    / "contracts"
    / "workload"
    / "compatibility"
    / "runtime-model-compatibility.v1alpha1.json"
)

SUPPORTED_API_VERSION = "inferops.io/v1alpha1"

# A JSON Schema keyword answers "what shape was wrong". It does not answer "which
# published rule refused this", which is what a reader needs. This table is that
# translation, and an unmapped keyword falls to contract-structure-invalid rather
# than inventing a rule identifier at runtime.
_KEYWORD_RULES: dict[str, str] = {
    "required": "field-required",
    "additionalProperties": "field-unknown",
    "unevaluatedProperties": "field-unknown",
    "propertyNames": "value-malformed",
    "enum": "value-not-permitted",
    "const": "value-not-permitted",
    "pattern": "value-malformed",
    "format": "value-malformed",
    "type": "value-wrong-type",
    "minLength": "value-out-of-range",
    "maxLength": "value-out-of-range",
    "minimum": "value-out-of-range",
    "maximum": "value-out-of-range",
    "exclusiveMinimum": "value-out-of-range",
    "exclusiveMaximum": "value-out-of-range",
    "minItems": "value-out-of-range",
    "maxItems": "value-out-of-range",
    "multipleOf": "value-out-of-range",
    "uniqueItems": "value-not-permitted",
    "not": "value-not-permitted",
    "oneOf": "value-not-permitted",
    "anyOf": "value-not-permitted",
    "allOf": "value-not-permitted",
}

_REQUIRED_NAME = re.compile(r"'([^']+)' is a required property")
_QUOTED_NAME = re.compile(r"'([^']+)'")


@lru_cache(maxsize=1)
def load_schema() -> dict[str, Any]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_compatibility_matrix() -> dict[str, Any]:
    return json.loads(COMPATIBILITY_MATRIX_PATH.read_text(encoding="utf-8"))


def _validator() -> Draft202012Validator:
    return Draft202012Validator(load_schema())


# --------------------------------------------------------------------------
# Structural layer
# --------------------------------------------------------------------------


def _permitted(values: Any) -> str:
    """Render a schema-declared vocabulary. Schema values are safe to print."""
    if isinstance(values, list):
        return ", ".join(json.dumps(value) for value in values)
    return json.dumps(values)


def _safe_message(error: Any) -> str:
    """Describe a structural failure without quoting anything from the document.

    The validator's own message embeds the offending value. That is helpful in a
    terminal and unacceptable in an error body, because the field most likely to
    be rejected for looking wrong is the field most likely to hold a secret.
    """
    keyword = error.validator
    if _is_property_name_error(error):
        return "property name does not match the required format for this object"
    if keyword == "required":
        return "required field is missing"
    if keyword in ("additionalProperties", "unevaluatedProperties"):
        return "field is not defined by this contract version"
    if keyword == "propertyNames":
        return "property name does not match the required format"
    if keyword == "enum":
        return (
            "value is not one of the permitted values: "
            f"{_permitted(error.validator_value)}"
        )
    if keyword == "const":
        return f"value must be {_permitted(error.validator_value)} in this position"
    if keyword == "type":
        return f"value must be of JSON type {_permitted(error.validator_value)}"
    if keyword in ("pattern", "format"):
        return "value does not match the required format for this field"
    if keyword in (
        "minLength",
        "maxLength",
        "minimum",
        "maximum",
        "exclusiveMinimum",
        "exclusiveMaximum",
        "minItems",
        "maxItems",
        "multipleOf",
    ):
        return f"value violates {keyword} {_permitted(error.validator_value)}"
    if keyword == "uniqueItems":
        return "array entries must be unique"
    if keyword in ("not", "oneOf", "anyOf", "allOf"):
        return "value is not permitted by this contract version in this position"
    return "value violates a structural constraint of this contract version"


def _is_property_name_error(error: Any) -> bool:
    """True when the failure is about a key rather than about a value.

    A `propertyNames` subschema is descended into, so the error that surfaces
    carries the inner keyword - `pattern`, usually - and nothing in `validator`
    says the instance is a key. The schema path is what says it.
    """
    return "propertyNames" in list(error.schema_path)


def _fields_for(error: Any) -> list[str]:
    """Where the failure is, one entry per field the error actually names."""
    base = error.json_path
    if error.validator == "required":
        match = _REQUIRED_NAME.search(error.message)
        return [f"{base}.{match.group(1)}"] if match else [base]
    if error.validator in ("additionalProperties", "unevaluatedProperties"):
        names = sorted(set(_QUOTED_NAME.findall(error.message)))
        return [f"{base}.{name}" for name in names] or [base]
    if _is_property_name_error(error) and isinstance(error.instance, str):
        # The instance under a propertyNames constraint is the offending key
        # itself. Naming it turns "something in annotations is wrong" into an
        # address. A key is a field name, never a value, so printing it is safe.
        return [f"{base}.{error.instance}"]
    return [base]


def structural_findings(document: Any) -> list[Finding]:
    """Findings from the published schema, translated into canonical rules."""
    findings: list[Finding] = []
    for error in _validator().iter_errors(document):
        rule = _KEYWORD_RULES.get(error.validator, "contract-structure-invalid")
        if error.json_path == "$.apiVersion" and error.validator == "const":
            rule = "contract-version-unsupported"
        message = _safe_message(error)
        findings.extend(finding(rule, field, message) for field in _fields_for(error))
    return findings


# --------------------------------------------------------------------------
# Semantic layer
# --------------------------------------------------------------------------

# Prefixes that are, by their issuer's own published format, the first characters
# of a credential and of nothing else. A locator never begins with one.
_CREDENTIAL_PREFIXES: tuple[str, ...] = (
    "-----BEGIN",
    "ABIA",
    "ACCA",
    "AGPA",
    "AIDA",
    "AIPA",
    "AIza",
    "AKIA",
    "ANPA",
    "ANVA",
    "AROA",
    "ASCA",
    "ASIA",
    "SG.",
    "doo_v1_",
    "dop_v1_",
    "eyJ",
    "ghp_",
    "ghr_",
    "ghs_",
    "ghu_",
    "gho_",
    "github_pat_",
    "gldt-",
    "glpat-",
    "hf_",
    "npm_",
    "pk_live_",
    "rk_live_",
    "shpat_",
    "shpss_",
    "sk-",
    "sk_live_",
    "sk_test_",
    "xoxa-",
    "xoxb-",
    "xoxp-",
    "xoxr-",
    "xoxs-",
    "ya29.",
)

_LOCATOR_SEGMENT = re.compile(r"[/#:._\-]")

# A locator segment is a name somebody chose. A credential is a string nobody
# chose. The thresholds below are what separates the two, and each is here to
# stop a specific false positive rather than because it sounded strict:
# the length bound clears "inferops-serving" and "model-registry"; the mixed-case
# and digit bounds together clear "TelemetryIngestPathForServing", which has case
# variation but no digits because a person typed it; and the entropy bound clears
# names built from repeated English-like letter frequencies.
_MIN_OPAQUE_LENGTH = 20
_MIN_OPAQUE_ENTROPY = 3.5


def _shannon_entropy(text: str) -> float:
    counts = Counter(text)
    length = len(text)
    return -sum(
        (count / length) * math.log2(count / length) for count in counts.values()
    )


def looks_like_a_pasted_credential(value: str) -> str | None:
    """Return a reason this locator looks like a credential, or None.

    The reason never contains the value. What this can and cannot catch is
    measured and published in the contract document rather than asserted here.
    """
    for prefix in _CREDENTIAL_PREFIXES:
        if value.startswith(prefix):
            return (
                f"the value begins with {prefix!r}, which is the published prefix "
                "of a credential format and is not part of any locator scheme"
            )
    for segment in _LOCATOR_SEGMENT.split(value):
        if len(segment) < _MIN_OPAQUE_LENGTH:
            continue
        if not (
            any(c.islower() for c in segment) and any(c.isupper() for c in segment)
        ):
            continue
        if not any(c.isdigit() for c in segment):
            continue
        if _shannon_entropy(segment) < _MIN_OPAQUE_ENTROPY:
            continue
        return (
            f"the value contains an opaque segment of {len(segment)} characters "
            "with mixed case, digits, and high character entropy, which is the "
            "shape of an issued credential rather than of a chosen name"
        )
    return None


def _artifact_format(filename: str, matrix: dict[str, Any]) -> str | None:
    for extension, name in sorted(matrix["artifactFormats"].items()):
        if filename.lower().endswith(extension):
            return name
    return None


def _runtime_for(image_reference: str, matrix: dict[str, Any]) -> dict[str, Any] | None:
    repository = image_reference.split("@", 1)[0]
    for runtime in matrix["runtimes"]:
        if repository in runtime["imageRepositories"]:
            return runtime
    return None


def _scaling_findings(spec: dict[str, Any]) -> list[Finding]:
    scaling = spec.get("scaling")
    if not isinstance(scaling, dict):
        return []
    minimum = scaling.get("minimumReplicas")
    maximum = scaling.get("maximumReplicas")
    if isinstance(minimum, bool) or isinstance(maximum, bool):
        return []
    if not isinstance(minimum, int) or not isinstance(maximum, int):
        return []
    if minimum <= maximum:
        return []
    return [
        finding(
            "replica-range-inverted",
            "$.spec.scaling",
            "minimumReplicas is greater than maximumReplicas, so the declared "
            "replica range is empty and no replica count satisfies it",
        )
    ]


def _secret_findings(spec: dict[str, Any]) -> list[Finding]:
    security = spec.get("security")
    if not isinstance(security, dict):
        return []
    refs = security.get("secretRefs")
    if not isinstance(refs, list):
        return []

    findings: list[Finding] = []
    seen: dict[str, int] = {}
    for index, ref in enumerate(refs):
        if not isinstance(ref, dict):
            continue
        where = f"$.spec.security.secretRefs[{index}]"

        reference = ref.get("reference")
        if isinstance(reference, str):
            reason = looks_like_a_pasted_credential(reference)
            if reason is not None:
                findings.append(
                    finding(
                        "secret-value-in-locator",
                        f"{where}.reference",
                        f"a secret reference must be a locator, not a secret: {reason}",
                    )
                )

        name = ref.get("name")
        if isinstance(name, str):
            if name in seen:
                findings.append(
                    finding(
                        "secret-ref-name-duplicated",
                        f"{where}.name",
                        "this logical secret name is already declared earlier in "
                        f"secretRefs, at index {seen[name]}, so which of the two a "
                        "workload would consume is undefined",
                    )
                )
            else:
                seen[name] = index

    if spec.get("profile") == "mock-llm" and refs:
        findings.append(
            finding(
                "mock-secret-ref-declared",
                "$.spec.security.secretRefs",
                "a mock-llm workload replays a fixture and reaches nothing that "
                "needs a credential, so declaring a secret reference either "
                "misdescribes the mock or points a continuous-integration "
                "workload at a real secret",
            )
        )
    return findings


def _runtime_model_findings(spec: dict[str, Any]) -> list[Finding]:
    if spec.get("profile") != "synchronous-llm":
        return []
    block = spec.get("synchronousLlm")
    if not isinstance(block, dict):
        return []
    runtime_block = block.get("runtime")
    artifact = block.get("modelArtifact")
    if not isinstance(runtime_block, dict) or not isinstance(artifact, dict):
        return []
    image = runtime_block.get("imageReference")
    filename = artifact.get("file")
    if not isinstance(image, str) or not isinstance(filename, str):
        return []

    matrix = load_compatibility_matrix()
    runtime = _runtime_for(image, matrix)
    if runtime is None:
        return [
            finding(
                "runtime-unregistered",
                "$.spec.synchronousLlm.runtime.imageReference",
                "this image repository has no entry in the published runtime and "
                "model compatibility matrix, so what it accepts is unknown; an "
                "uncharacterised combination is unsupported until it is added "
                "there with evidence",
            )
        ]

    artifact_format = _artifact_format(filename, matrix)
    if artifact_format is None:
        return [
            finding(
                "model-artifact-format-unknown",
                "$.spec.synchronousLlm.modelArtifact.file",
                "the artifact filename ends in no extension the compatibility "
                "matrix recognises, so the format a runtime would have to load "
                "cannot be determined",
            )
        ]

    if artifact_format not in runtime["acceptedArtifactFormats"]:
        accepted = ", ".join(runtime["acceptedArtifactFormats"]) or "no artifact format"
        return [
            finding(
                "runtime-model-incompatible",
                "$.spec.synchronousLlm.modelArtifact.file",
                f"runtime {runtime['runtimeId']!r} accepts {accepted}, and this "
                f"workload pins a {artifact_format} artifact",
            )
        ]
    return []


def semantic_findings(document: Any) -> list[Finding]:
    """Rules the schema cannot express, applied only to a version we understand."""
    if not isinstance(document, dict):
        return []
    if document.get("apiVersion") != SUPPORTED_API_VERSION:
        # Every rule below is written against v1alpha1 field paths. Applying them
        # to a document that declares another version would produce findings about
        # a shape this validator has no claim over.
        return []
    spec = document.get("spec")
    if not isinstance(spec, dict):
        return []
    return [
        *_scaling_findings(spec),
        *_secret_findings(spec),
        *_runtime_model_findings(spec),
    ]


# --------------------------------------------------------------------------
# Public entry point
# --------------------------------------------------------------------------


def validate(document: Any) -> list[Finding]:
    """Validate one contract document. Returns findings, sorted, possibly empty.

    Sorting is part of the contract this function offers: two runs over the same
    document return the same list in the same order, so a result is quotable in a
    review and comparable in a test.
    """
    return sorted([*structural_findings(document), *semantic_findings(document)])


def is_valid(document: Any) -> bool:
    return not validate(document)
