"""The canonical form a release is compared and hashed in, and the digests it records.

**One serialisation.** The canonical JSON form of a value is its JSON text with
keys sorted, no insignificant whitespace, non-ASCII characters written as
themselves, and the whole encoded as UTF-8. It is the form the evidence index
already hashes register entries in, reused rather than invented; the domain cannot
import the repository's ``tools`` package, so it is written again here and a test
holds the two byte for byte.

**Only values every JSON reader holds the same way.** A canonical form is only
canonical if another serialiser can reproduce it, so :func:`canonical_json`
refuses what JSON does not carry identically everywhere, rather than writing it
some way of its own:

- a **float** - its text differs between serialisers, and ``2.0`` and ``2`` are
  one value to JSON Schema and two to a byte comparison. No document this module
  hashes holds one: the contract and binding schemas declare integers only, and
  their parsers read an integral ``2.0`` as ``2`` before anything is hashed;
- an **integer** beyond +/-(2**53 - 1), which a reader that holds numbers as
  doubles cannot represent exactly;
- a **date, a time, or any other object** YAML can produce and JSON cannot. An
  unquoted ``2026-09-30`` in a YAML file loads as a date; it is refused here
  rather than written as text, so a timestamp cannot enter a canonical form by
  accident of quoting;
- a **mapping key that is not a string**, and a string UTF-8 cannot encode.

Nothing is normalised: two strings that differ only in Unicode normalisation are
two values. Every string a release can hold is ASCII by its pattern, so that can
only matter for the text of a contract.

**How a source document is hashed - decided here.** A release records the digest
of the WorkloadContract and of the EnvironmentBinding it was rendered from. That
digest is the SHA-256 of the canonical JSON form of the document *as the platform
domain reads it* - :func:`contract_digest` and :func:`binding_digest` take the
parsed object and hash its wire form. So the digest names the document's value,
not its bytes: YAML comments, key order, indentation, quoting style, and an
integral ``2.0`` written for ``2`` do not move it, and any change to a value does.
A document that does not parse has no digest.

**How the release identifier is derived.** The rule is the contract document's:
the SHA-256 of the canonical JSON of
``{"metadata": {"workloadId": ..., "workloadVersion": ...}, "source": ...}``. The
output is not an input to it, and neither is the identifier itself.

Offline and deterministic: no file system, network, clock, or randomness. A test
replaces the clock, the random sources, and the identifier generators with
functions that fail, and computes every value here under them.
"""

from __future__ import annotations

import hashlib
import json
from typing import Final

from ..environment.binding import EnvironmentBinding
from ..workload.contract import WorkloadContract
from ..workload.values import DnsLabel
from .errors import CanonicalFormError
from .release import Document, ReleaseSource, RenderedWorkloadRelease
from .values import ReleaseId, ReleaseWorkloadVersion, Sha256Hex

#: The largest magnitude an integer can have and still be held exactly by a JSON
#: reader that stores numbers as IEEE 754 doubles.
LARGEST_EXACT_INTEGER: Final = 2**53 - 1


def _check(value: object, location: str) -> None:
    """Refuse anything that has no single JSON spelling. Never quotes the value."""
    if value is None or isinstance(value, bool):
        return
    if isinstance(value, int):
        if abs(value) > LARGEST_EXACT_INTEGER:
            raise CanonicalFormError(
                location,
                "an integer beyond 2**53 - 1 in magnitude has no exact JSON form "
                "every reader shares",
            )
        return
    if isinstance(value, float):
        raise CanonicalFormError(
            location,
            "a float has no canonical JSON form; no document this rule hashes "
            "declares one",
        )
    if isinstance(value, str):
        try:
            value.encode("utf-8")
        except UnicodeEncodeError:
            raise CanonicalFormError(
                location, "the string cannot be encoded as UTF-8"
            ) from None
        return
    if isinstance(value, dict):
        for key, member in value.items():
            if not isinstance(key, str):
                raise CanonicalFormError(
                    location, "every member name of an object must be a string"
                )
            _check(key, location)
            _check(member, f"{location}.{key}")
        return
    if isinstance(value, list):
        for index, member in enumerate(value):
            _check(member, f"{location}[{index}]")
        return
    raise CanonicalFormError(
        location,
        f"a {type(value).__name__} has no JSON form; a date or time loaded from "
        "unquoted YAML is refused here rather than written as text",
    )


def canonical_json(value: object) -> bytes:
    """The canonical JSON form of a JSON value, as UTF-8 bytes.

    Raises:
        CanonicalFormError: the value, or something inside it, has no canonical
            JSON form. The error names where, never what.
    """
    _check(value, "$")
    text = json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    )
    return text.encode("utf-8")


def canonical_sha256(value: object) -> Sha256Hex:
    """The SHA-256 of a value's canonical JSON form, as 64 lowercase hex digits."""
    return Sha256Hex(hashlib.sha256(canonical_json(value)).hexdigest())


def contract_digest(contract: WorkloadContract) -> Sha256Hex:
    """The digest a release records for a WorkloadContract: of its value, not its bytes."""
    if not isinstance(contract, WorkloadContract):
        raise TypeError(
            "a contract digest is taken of a WorkloadContract produced by "
            "parse_workload_contract, not of a raw document"
        )
    return canonical_sha256(contract.as_document())


def binding_digest(binding: EnvironmentBinding) -> Sha256Hex:
    """The digest a release records for an EnvironmentBinding: of its value."""
    if not isinstance(binding, EnvironmentBinding):
        raise TypeError(
            "a binding digest is taken of an EnvironmentBinding produced by "
            "parse_environment_binding, not of a raw document"
        )
    return canonical_sha256(binding.as_document())


def release_identity(
    workload_id: DnsLabel,
    workload_version: ReleaseWorkloadVersion,
    source: ReleaseSource,
) -> Document:
    """The object a release identifier is the digest of. The output is not in it."""
    return {
        "metadata": {
            "workloadId": str(workload_id),
            "workloadVersion": str(workload_version),
        },
        "source": source.as_document(),
    }


def derive_release_id(
    workload_id: DnsLabel,
    workload_version: ReleaseWorkloadVersion,
    source: ReleaseSource,
) -> ReleaseId:
    """The release identifier the published rule gives for these inputs."""
    identity = release_identity(workload_id, workload_version, source)
    return ReleaseId(hashlib.sha256(canonical_json(identity)).hexdigest())


def canonical_release(release: RenderedWorkloadRelease) -> bytes:
    """The canonical JSON form of a whole release, output included.

    Two releases are the same document exactly when these bytes are equal. Two
    releases with the same identifier and different bytes here were rendered from
    the same inputs and produced different output.
    """
    return canonical_json(release.as_document())


__all__ = [
    "LARGEST_EXACT_INTEGER",
    "binding_digest",
    "canonical_json",
    "canonical_release",
    "canonical_sha256",
    "contract_digest",
    "derive_release_id",
    "release_identity",
]
