"""What a RenderedWorkloadRelease is refused with, and the rules that refuse it.

Three kinds of failure, kept apart the way the binding domain keeps them apart.

**Reading one document.** :class:`UnsupportedReleaseVersionError` and
:class:`MalformedReleaseError` are parse failures: the document cannot be turned
into a typed release at all. They carry a field, a reason, and the canonical code
their type maps to - ``version-unsupported`` and ``contract-invalid`` - and no rule
identifier: every one of them is a structural refusal the published schema already
makes, and the offline validator is what names the structural rule.

**Judging a document the schema accepts.** A release that parses can still carry a
release identifier its own inputs do not derive, or an identifier shaped like a
credential; and a release that is sound alone can disagree with the contract or
binding it names. Those refusals are :class:`ReleaseRefusal`, each under a rule
identifier in :data:`RELEASE_RULES` with the canonical code it maps to. No
canonical code was added: every one is ``contract-invalid``, and none becomes
valid on retry.

**Refusing a value that has no canonical form.** :class:`CanonicalFormError` is
raised when something asks for the canonical JSON of a value that JSON cannot
carry the same way in every serialiser - a float, a date, an integer beyond the
range every JSON reader holds exactly. It is a programming or input error rather
than a verdict on a release, so it carries a location and a reason and no code.

**A message never carries a value read out of a document.** An identifier, a
version, a file name are author-supplied text; a refusal names where the problem
is and which rule refused it, and leaves the value in the document.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

from ..context import NO_REQUEST_CONTEXT, RequestContext
from ..workload.errors import DomainError

#: The canonical codes a release refusal can carry. The same two the offline
#: contract validator publishes; a test holds this set inside that vocabulary.
CONTRACT_INVALID: Final = "contract-invalid"
VERSION_UNSUPPORTED: Final = "version-unsupported"


@dataclass(frozen=True, slots=True)
class ReleaseRule:
    """One published reason a release, or a release beside its sources, is refused."""

    identifier: str
    code: str
    summary: str


def _rule(identifier: str, summary: str) -> ReleaseRule:
    return ReleaseRule(identifier=identifier, code=CONTRACT_INVALID, summary=summary)


#: Every rule the release domain can cite, keyed by identifier. The release's
#: contract document publishes the same set as a table, and a test fails if the
#: two disagree or if an identifier here is one the offline validator also uses.
RELEASE_RULES: Final[dict[str, ReleaseRule]] = {
    rule.identifier: rule
    for rule in (
        _rule(
            "release-id-not-derived",
            "the release identifier is not the one its workload identity and "
            "source derive",
        ),
        _rule(
            "release-value-credential-shaped",
            "an identifier, version, or file name begins, or has a part that "
            "begins, with a published credential prefix",
        ),
        _rule(
            "release-contract-mismatch",
            "the workload identifier, workload version, or contract version is "
            "not the named contract's",
        ),
        _rule(
            "release-contract-digest-mismatch",
            "the contract digest is not the digest of the named contract",
        ),
        _rule(
            "release-binding-mismatch",
            "the binding version, environment, or name is not the named binding's",
        ),
        _rule(
            "release-binding-digest-mismatch",
            "the binding digest is not the digest of the named binding",
        ),
        _rule(
            "release-environment-mismatch",
            "the named contract and the named binding serve different environments",
        ),
    )
}


class ReleaseError(DomainError):
    """A release could not be read, or could not be accepted as given.

    Carries where the failure is, why, the canonical code, and the request-scoped
    identifiers a caller supplied. The domain never generates either identifier.
    """

    #: The canonical code this refusal maps to. Every release refusal is final:
    #: a document that is malformed or inconsistent does not change on retry.
    code: str = CONTRACT_INVALID

    def __init__(
        self,
        field: str,
        reason: str,
        *,
        context: RequestContext = NO_REQUEST_CONTEXT,
    ) -> None:
        super().__init__(f"{field}: {reason}")
        self.field = field
        self.reason = reason
        self.context = context

    @property
    def retryable(self) -> bool:
        """A release refusal does not resolve itself on retry."""
        return False

    def as_dict(self) -> dict[str, object]:
        """A safe, structured form: code, field, reason, and any identifiers."""
        return {
            "code": self.code,
            "retryable": self.retryable,
            "field": self.field,
            "reason": self.reason,
            **self.context.as_dict(),
        }


class UnsupportedReleaseVersionError(ReleaseError):
    """``apiVersion`` names a release version this package does not implement."""

    code = VERSION_UNSUPPORTED


class MalformedReleaseError(ReleaseError):
    """The document declares a supported version and does not satisfy it."""


class ReleaseRefusal(ReleaseError):
    """One published rule refused a release, or a release beside its sources.

    The field names the document by its role - ``release`` for the release, and
    ``contract`` or ``binding`` for a source it was compared with - and then the
    path inside it.
    """

    def __init__(
        self,
        field: str,
        rule_id: str,
        reason: str,
        *,
        context: RequestContext = NO_REQUEST_CONTEXT,
    ) -> None:
        # An unpublished identifier is a defect in this package, not a refusal of
        # a document, so it fails loudly here rather than reaching a caller.
        rule = RELEASE_RULES[rule_id]
        super().__init__(field, reason, context=context)
        self.rule_id = rule.identifier
        self.code = rule.code

    def as_dict(self) -> dict[str, object]:
        """A safe, structured form: code, rule, field, reason, and identifiers."""
        return {"ruleId": self.rule_id, **super().as_dict()}


class CanonicalFormError(DomainError):
    """A value has no canonical JSON form. Carries a location, never the value."""

    def __init__(self, location: str, reason: str) -> None:
        super().__init__(f"{location}: {reason}")
        self.location = location
        self.reason = reason


__all__ = [
    "CONTRACT_INVALID",
    "RELEASE_RULES",
    "VERSION_UNSUPPORTED",
    "CanonicalFormError",
    "MalformedReleaseError",
    "ReleaseError",
    "ReleaseRefusal",
    "ReleaseRule",
    "UnsupportedReleaseVersionError",
]
