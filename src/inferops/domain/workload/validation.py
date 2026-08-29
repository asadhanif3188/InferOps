"""Semantic validation of a parsed WorkloadContract.

The parsing layer enforces single-field structural constraints: the document is a
mapping; every required field is present; every value is of the correct JSON type;
and every constrained value satisfies its format, length, or bound. This module
applies the cross-field and matrix rules that the contract publishes with rule
identifiers.

**Returns all errors at once.** A validation pipeline that stops at the first
problem leaves every problem after the first for the author to discover one at a
time. This module collects all violations and returns them together, so a
developer learns what is wrong all at once rather than in installments.

**A reason never repeats a value read from the document.** It names the field and
describes the constraint in the schema's own published vocabulary. The permitted
values of a closed vocabulary are safe to print because they come from the schema;
the value that failed to be one of them is not.

The rules implemented here are published in the schema and in the domain
documentation. A missing rule or a rule applied where it was not published is a
defect, not a decision.

**File I/O.** The compatibility matrix is loaded outside the domain module by
test suites and tools. The domain module accepts the matrix as a parameter and
does not read files, which keeps it testable from a wheel with no repository.
"""

from __future__ import annotations

import re
from typing import Any

from ..context import NO_REQUEST_CONTEXT, RequestContext
from .contract import WorkloadContract
from .errors import WorkloadValidationError


class CompatibilityMatrixLoader:
    """Accesses the runtime-model compatibility matrix (provided as a dict).

    The matrix is passed in at construction time. File I/O is the caller's
    responsibility, which keeps the domain module file-system-independent.
    """

    def __init__(self, matrix: dict[str, Any]) -> None:
        self._matrix = matrix

    @property
    def matrix(self) -> dict[str, Any]:
        """The parsed compatibility matrix."""
        return self._matrix

    def get_artifact_format_from_extension(self, filename: str) -> str | None:
        """Extract the artifact format from a filename extension.

        Returns the format name (e.g., 'gguf', 'safetensors', 'pytorch-bin')
        or None if the extension is not recognized.
        """
        formats = self.matrix.get("artifactFormats", {})
        if not isinstance(formats, dict):
            return None
        for extension, format_name in formats.items():
            if not isinstance(extension, str) or not isinstance(format_name, str):
                continue
            if filename.endswith(extension):
                return format_name
        return None

    def get_runtime_by_repository(self, repo: str) -> dict[str, Any] | None:
        """Find a runtime entry by image repository.

        Returns the runtime dict or None if not found.
        """
        runtimes = self.matrix.get("runtimes", [])
        if not isinstance(runtimes, list):
            return None
        for runtime in runtimes:
            if not isinstance(runtime, dict):
                continue
            image_repos = runtime.get("imageRepositories", [])
            if not isinstance(image_repos, list):
                continue
            if repo in image_repos:
                return runtime
        return None

    def is_runtime_registered(self, image_repo: str) -> bool:
        """Check if a runtime image repository is registered in the matrix."""
        return self.get_runtime_by_repository(image_repo) is not None

    def get_runtime_accepted_formats(self, image_repo: str) -> list[str] | None:
        """Get the list of artifact formats accepted by a runtime.

        Returns a list of format names or None if runtime is not found.
        """
        runtime = self.get_runtime_by_repository(image_repo)
        if runtime is None:
            return None
        formats = runtime.get("acceptedArtifactFormats", [])
        if not isinstance(formats, list):
            return None
        if not all(isinstance(f, str) for f in formats):
            return None
        return formats


# Global singleton instance (set by the caller, typically a test or tool)
_matrix_loader: CompatibilityMatrixLoader | None = None


def set_matrix_loader(loader: CompatibilityMatrixLoader) -> None:
    """Set the global matrix loader instance (for initialization)."""
    global _matrix_loader
    _matrix_loader = loader


def get_matrix_loader() -> CompatibilityMatrixLoader:
    """Get the global matrix loader instance.

    Raises ValueError if the loader has not been initialized by the caller.
    """
    global _matrix_loader
    if _matrix_loader is None:
        raise ValueError(
            "Matrix loader not initialized. Call set_matrix_loader() first, "
            "or pass the matrix to a validation function that loads it externally."
        )
    return _matrix_loader


def validate_workload_contract(
    contract: WorkloadContract,
    context: RequestContext = NO_REQUEST_CONTEXT,
) -> list[WorkloadValidationError]:
    """Apply semantic validation rules to a parsed workload contract.

    Returns a list of validation errors. An empty list means the contract passed
    all semantic validation rules. Multiple errors are returned together, so a
    developer learns what is wrong all at once.

    Args:
        contract: The parsed workload contract to validate.
        context: Optional request context with requestId and correlationId.

    Returns:
        A list of WorkloadValidationError objects (may be empty).
    """
    errors: list[WorkloadValidationError] = []

    # Rule 1: replica-range-inverted
    if contract.spec.scaling.minimum_replicas > contract.spec.scaling.maximum_replicas:
        errors.append(
            WorkloadValidationError(
                field="spec.scaling",
                rule_id="replica-range-inverted",
                reason="minimumReplicas must not exceed maximumReplicas",
                context=context,
            )
        )

    # Rule 2: secret-value-in-locator
    # A secret locator that looks like a pasted credential has published prefixes
    # or an opaque segment that suggests it is a secret value, not a reference.
    for i, secret_ref in enumerate(contract.spec.security.secret_refs):
        if _looks_like_secret_value(str(secret_ref.reference)):
            errors.append(
                WorkloadValidationError(
                    field=f"spec.security.secretRefs[{i}].reference",
                    rule_id="secret-value-in-locator",
                    reason="secret reference looks like a pasted credential",
                    context=context,
                )
            )

    # Rule 3: secret-ref-name-duplicated
    secret_names = [str(ref.name) for ref in contract.spec.security.secret_refs]
    seen_names = set()
    for i, name in enumerate(secret_names):
        if name in seen_names:
            errors.append(
                WorkloadValidationError(
                    field=f"spec.security.secretRefs[{i}].name",
                    rule_id="secret-ref-name-duplicated",
                    reason="secret reference names must be unique",
                    context=context,
                )
            )
        seen_names.add(name)

    # Rule 4: mock-secret-ref-declared
    if contract.is_mock and len(contract.spec.security.secret_refs) > 0:
        errors.append(
            WorkloadValidationError(
                field="spec.security.secretRefs",
                rule_id="mock-secret-ref-declared",
                reason="this workload must not declare secret references",
                context=context,
            )
        )

    # Rules 5, 6, 7: Runtime and model compatibility (only for synchronous-llm)
    if not contract.is_mock and contract.spec.synchronous_llm is not None:
        matrix_loader = get_matrix_loader()

        # Extract runtime image repository from the pinned image reference
        runtime_image = str(contract.spec.synchronous_llm.runtime.image_reference)
        runtime_repo = _extract_repository_from_image(runtime_image)

        # Rule 5: runtime-unregistered
        if not matrix_loader.is_runtime_registered(runtime_repo):
            errors.append(
                WorkloadValidationError(
                    field="spec.synchronousLlm.runtime.imageReference",
                    rule_id="runtime-unregistered",
                    reason="runtime image repository is not registered in the compatibility matrix",
                    context=context,
                )
            )

        # Rule 6: model-artifact-format-unknown
        artifact_file = str(contract.spec.synchronous_llm.model_artifact.file)
        artifact_format = matrix_loader.get_artifact_format_from_extension(
            artifact_file
        )
        if artifact_format is None:
            errors.append(
                WorkloadValidationError(
                    field="spec.synchronousLlm.modelArtifact.file",
                    rule_id="model-artifact-format-unknown",
                    reason="artifact filename has no recognized format extension",
                    context=context,
                )
            )

        # Rule 7: runtime-model-incompatible
        # Only check this if both the runtime and format are recognized
        if (
            matrix_loader.is_runtime_registered(runtime_repo)
            and artifact_format is not None
        ):
            accepted_formats = (
                matrix_loader.get_runtime_accepted_formats(runtime_repo) or []
            )
            if artifact_format not in accepted_formats:
                errors.append(
                    WorkloadValidationError(
                        field="spec.synchronousLlm.modelArtifact.file",
                        rule_id="runtime-model-incompatible",
                        reason="pinned runtime does not accept the model artifact format",
                        context=context,
                    )
                )

    return errors


def _looks_like_secret_value(locator: str) -> bool:
    """Heuristic: does a locator look like a pasted credential?

    Mirrors the published validator in tools/contract_validation/workload.py.
    Checks for published credential prefixes or opaque segments that look like
    credentials. This must be aligned with the published validator.
    """
    # Published credential prefixes (39 total) from tools/contract_validation/workload.py
    credential_prefixes = (
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

    for prefix in credential_prefixes:
        if locator.startswith(prefix):
            return True

    return _looks_like_high_entropy_token(locator)


def _looks_like_high_entropy_token(text: str) -> bool:
    """Check if a string looks like a high-entropy token (mixed case and digits).

    Tokens like API keys, session IDs, and access tokens typically have:
    - Both uppercase and lowercase letters
    - Digits
    - A segment that is at least 20 characters of such mixed content

    This catches patterns like "Zx4Kq9TbLm2Rd7Wf1Hs3Nv8Yc6Ej0Pa" from the fixture.
    """
    # Look for segments of at least 20 characters with mixed case and digits
    # Split by common delimiters to isolate segments
    segments = re.split(r"[/_:-]", text)

    for segment in segments:
        if len(segment) >= 20:
            has_upper = any(c.isupper() for c in segment)
            has_lower = any(c.islower() for c in segment)
            has_digit = any(c.isdigit() for c in segment)

            # If a segment has all three characteristics, it looks like a token
            if has_upper and has_lower and has_digit:
                return True

    return False


def _extract_repository_from_image(image_ref: str) -> str:
    """Extract the repository part from a digest-pinned image reference.

    A digest-pinned image reference looks like:
        ghcr.io/ggml-org/llama.cpp@sha256:100de626...

    This extracts the repository part (everything before the @sha256).
    """
    if "@" in image_ref:
        return image_ref.split("@")[0]
    return image_ref


__all__ = [
    "CompatibilityMatrixLoader",
    "WorkloadValidationError",
    "get_matrix_loader",
    "validate_workload_contract",
]
