"""Contract-version handling, kept explicit and in one place.

``apiVersion`` is the compatibility axis of the WorkloadContract, and the contract
document states that it is *explicit on every document; never inferred*. This
module is that rule in code: the set of versions this package implements is a
constant a reader can see, and a document declaring anything else is refused
before a single field below it is read.

The refusal has to happen first. Every field path this package knows —
``$.spec.model.modelRef``, ``$.spec.synchronousLlm.modelArtifact.sha256`` — is a
path in ``v1alpha1``. Applying them to a document that declares ``v1alpha2`` would
produce complaints about a shape this package has no claim over, which is worse
than saying plainly that the version is not implemented.

One version exists today. The tuple is a tuple rather than a single string so that
supporting a second one is an entry rather than a rewrite; when that day comes,
the migration rules are in ``docs/contracts/workload-contract.md`` and adding an
entry here is the smallest part of it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from ..context import NO_REQUEST_CONTEXT, RequestContext
from .errors import UnsupportedContractVersionError

#: The ``kind`` every document this package reads must declare.
WORKLOAD_CONTRACT_KIND: Final = "WorkloadContract"

#: The API group the contract is published under.
CONTRACT_GROUP: Final = "inferops.io"

#: Every ``apiVersion`` this package implements, in maturity order.
SUPPORTED_CONTRACT_VERSIONS: Final[tuple[str, ...]] = ("inferops.io/v1alpha1",)


@dataclass(frozen=True, slots=True)
class ContractVersion:
    """One supported ``apiVersion``, split into the two parts it is made of."""

    group: str
    version: str

    def __post_init__(self) -> None:
        # Constructed directly rather than through `parse`, this would otherwise
        # be an object asserting a version nothing implements. Every other value
        # in this domain refuses itself at construction; this one does too.
        if str(self) not in SUPPORTED_CONTRACT_VERSIONS:
            supported = ", ".join(repr(entry) for entry in SUPPORTED_CONTRACT_VERSIONS)
            raise UnsupportedContractVersionError(
                "$.apiVersion",
                "the contract version named here is not one this package "
                f"implements; the supported versions are {supported}",
            )

    def __str__(self) -> str:
        return f"{self.group}/{self.version}"

    @classmethod
    def parse(
        cls,
        value: object,
        *,
        context: RequestContext = NO_REQUEST_CONTEXT,
    ) -> ContractVersion:
        """The declared version, or a refusal naming the versions that exist.

        The permitted values are printed because they are this package's own
        published vocabulary. The value that failed to be one of them is not, for
        the reason every message in this domain withholds one.
        """
        if not isinstance(value, str) or value not in SUPPORTED_CONTRACT_VERSIONS:
            supported = ", ".join(repr(entry) for entry in SUPPORTED_CONTRACT_VERSIONS)
            raise UnsupportedContractVersionError(
                "$.apiVersion",
                "the contract version declared here is not one this package "
                f"implements; the supported versions are {supported}",
                context=context,
            )
        group, _, version = value.partition("/")
        return cls(group=group, version=version)


def is_supported_contract_version(value: object) -> bool:
    """Whether a declared ``apiVersion`` is one this package implements."""
    return isinstance(value, str) and value in SUPPORTED_CONTRACT_VERSIONS
