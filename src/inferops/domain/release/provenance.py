"""The rules that judge a release the schema accepts, alone and beside its sources.

A release is refused by its parser when it is malformed. What a parser cannot see
is whether a well-formed release says something true. This module applies the
rules that decide that, and it is the only place they are applied.

**Two rules on one release** - :func:`check_rendered_workload_release`:

- ``release-id-not-derived`` - ``metadata.releaseId`` is not the digest its own
  workload identity and ``source`` derive. The schema accepts any 64 lowercase
  hexadecimal characters; only recomputing the rule tells a derived identifier
  from a random one of the right length.
- ``release-value-credential-shaped`` - an identifier, a version, or the values
  file name begins, or has a part that begins, with a prefix a credential issuer
  publishes as the start of its tokens. The prefixes are the WorkloadContract's
  heuristic's, applied unchanged; what is new is *where*: at the start of the
  value and after every ``-``, ``.``, ``+``, ``/``, ``@``, and ``:`` in it, so a
  token behind a version's pre-release separator is seen as well as one that
  begins a name.

**Five rules beside the documents a release names** -
:func:`verify_release_sources`, given the parsed WorkloadContract and
EnvironmentBinding:

- ``release-contract-mismatch`` - the workload identifier, workload version, or
  contract version is not the contract's;
- ``release-contract-digest-mismatch`` - the contract digest is not
  :func:`~inferops.domain.release.canonical.contract_digest` of the contract, so
  the contract changed after the release was recorded, or it is another contract;
- ``release-binding-mismatch`` - the binding version, environment, or name is not
  the binding's;
- ``release-binding-digest-mismatch`` - the binding digest is not
  :func:`~inferops.domain.release.canonical.binding_digest` of the binding;
- ``release-environment-mismatch`` - the contract and the binding serve different
  environments, so no release could have been rendered from the two together.

**What is not checked here, and why.** Whether the values digest is the digest of
the generated values file, and whether that file exists beside the release, need
the file and the rule for hashing it, and both belong to the story that generates
it. Whether the renderer and platform-defaults revisions name commits that exist
needs a repository. Neither is a document this module is given.

Everything is returned at once, sorted, and nothing is raised for a refusal: the
caller decides whether a refusal stops it. Offline and deterministic, like the
rest of the package.
"""

from __future__ import annotations

import re
from typing import Final

from ..context import NO_REQUEST_CONTEXT, RequestContext
from ..environment.binding import EnvironmentBinding
from ..workload.contract import WorkloadContract
from ..workload.validation import _looks_like_secret_value
from .canonical import binding_digest, contract_digest, derive_release_id
from .errors import ReleaseRefusal
from .release import RenderedWorkloadRelease

#: The characters after which a credential could begin inside a release value.
#: Every separator any accepted form of an identifier, a version, or a file name
#: admits, and nothing else: the patterns admit no other punctuation.
PART_SEPARATORS: Final = "-.+/@:"

_SEPARATOR = re.compile(f"[{re.escape(PART_SEPARATORS)}]")
_DIGIT_RUN = re.compile(r"(\d+)")


def _sort_key(refusal: ReleaseRefusal) -> tuple[object, ...]:
    """Order refusals by field, reading list indices as numbers rather than text."""
    parts = tuple(
        int(part) if part.isdigit() else part
        for part in _DIGIT_RUN.split(refusal.field)
    )
    return (parts, refusal.rule_id, refusal.reason)


def _require_release(release: object) -> None:
    if not isinstance(release, RenderedWorkloadRelease):
        raise TypeError(
            "release must be a RenderedWorkloadRelease produced by "
            "parse_rendered_workload_release, not a raw document"
        )


def credential_positions(value: str) -> tuple[str, ...]:
    """Every suffix a credential could begin at: the value, and after each separator."""
    starts = [0] + [match.end() for match in _SEPARATOR.finditer(value)]
    return tuple(value[start:] for start in starts if start < len(value))


def is_credential_shaped(value: str) -> bool:
    """Whether any part of a value begins as a published credential format does."""
    return any(_looks_like_secret_value(part) for part in credential_positions(value))


def check_rendered_workload_release(
    release: RenderedWorkloadRelease,
    *,
    context: RequestContext = NO_REQUEST_CONTEXT,
) -> list[ReleaseRefusal]:
    """Apply the two rules a release is judged by on its own. Returns every refusal.

    Raises:
        TypeError: ``release`` is not a parsed release.
    """
    _require_release(release)
    refusals: list[ReleaseRefusal] = []

    metadata = release.metadata
    derived = derive_release_id(
        metadata.workload_id, metadata.workload_version, release.source
    )
    if metadata.release_id != derived:
        refusals.append(
            ReleaseRefusal(
                "release.metadata.releaseId",
                "release-id-not-derived",
                "the release identifier is not the SHA-256 of the canonical JSON of "
                "the release's workload identity and source",
                context=context,
            )
        )

    shaped = {
        "release.metadata.workloadId": str(metadata.workload_id),
        "release.metadata.workloadVersion": str(metadata.workload_version),
        "release.source.environmentBinding.name": str(
            release.source.environment_binding.name
        ),
        "release.output.helmValues.path": str(release.output.helm_values.path),
    }
    for field, value in shaped.items():
        if is_credential_shaped(value):
            refusals.append(
                ReleaseRefusal(
                    field,
                    "release-value-credential-shaped",
                    "a part of this value begins with the published prefix of a "
                    "credential format; provenance names things and never carries "
                    "a credential",
                    context=context,
                )
            )

    return sorted(refusals, key=_sort_key)


def verify_release_sources(
    release: RenderedWorkloadRelease,
    contract: WorkloadContract,
    binding: EnvironmentBinding,
    *,
    context: RequestContext = NO_REQUEST_CONTEXT,
) -> list[ReleaseRefusal]:
    """Compare a release with the contract and binding it names. Returns every refusal.

    Reads the two documents and changes neither. Applies neither of the rules
    :func:`check_rendered_workload_release` applies; a caller wanting both calls
    both.

    Raises:
        TypeError: any argument is a raw document rather than a parsed object.
    """
    _require_release(release)
    if not isinstance(contract, WorkloadContract):
        raise TypeError(
            "contract must be a WorkloadContract produced by parse_workload_contract"
        )
    if not isinstance(binding, EnvironmentBinding):
        raise TypeError(
            "binding must be an EnvironmentBinding produced by "
            "parse_environment_binding"
        )

    refusals: list[ReleaseRefusal] = []

    def refuse(field: str, rule_id: str, reason: str) -> None:
        refusals.append(ReleaseRefusal(field, rule_id, reason, context=context))

    metadata = release.metadata
    recorded_contract = release.source.contract
    if str(metadata.workload_id) != str(contract.workload_id):
        refuse(
            "release.metadata.workloadId",
            "release-contract-mismatch",
            "the workload identifier is not the contract's metadata.name",
        )
    if str(metadata.workload_version) != str(contract.metadata.version):
        refuse(
            "release.metadata.workloadVersion",
            "release-contract-mismatch",
            "the workload version is not the contract's metadata.version",
        )
    if str(recorded_contract.api_version) != str(contract.api_version):
        refuse(
            "release.source.contract.apiVersion",
            "release-contract-mismatch",
            "the contract version is not the contract's apiVersion",
        )
    if recorded_contract.sha256 != contract_digest(contract):
        refuse(
            "release.source.contract.sha256",
            "release-contract-digest-mismatch",
            "the contract digest is not the SHA-256 of the canonical JSON of the "
            "contract",
        )

    recorded_binding = release.source.environment_binding
    if str(recorded_binding.api_version) != str(binding.api_version):
        refuse(
            "release.source.environmentBinding.apiVersion",
            "release-binding-mismatch",
            "the binding version is not the binding's apiVersion",
        )
    if recorded_binding.environment is not binding.spec.environment:
        refuse(
            "release.source.environmentBinding.environment",
            "release-binding-mismatch",
            "the environment is not the binding's spec.environment",
        )
    if str(recorded_binding.name) != str(binding.metadata.name):
        refuse(
            "release.source.environmentBinding.name",
            "release-binding-mismatch",
            "the binding name is not the binding's metadata.name",
        )
    if recorded_binding.sha256 != binding_digest(binding):
        refuse(
            "release.source.environmentBinding.sha256",
            "release-binding-digest-mismatch",
            "the binding digest is not the SHA-256 of the canonical JSON of the "
            "binding",
        )

    if contract.spec.environment is not binding.spec.environment:
        refuse(
            "contract.spec.environment",
            "release-environment-mismatch",
            "the contract's environment is not the one the binding serves",
        )

    return sorted(refusals, key=_sort_key)


__all__ = [
    "PART_SEPARATORS",
    "check_rendered_workload_release",
    "credential_positions",
    "is_credential_shaped",
    "verify_release_sources",
]
