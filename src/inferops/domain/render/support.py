"""What a renderer declares it can render, and the refusal when an input is outside it.

The domain reads every version it implements, but a renderer is built for some of
them: one written against today's contract cannot be assumed to render a later
version correctly, and one built for the ``synchronous-llm`` profile has nothing to
say about a ``mock-llm`` workload. So a renderer states, in a
:class:`RendererSupport`, the contract versions, binding versions, platform-defaults
versions, and profiles it takes, and an input outside any of them is refused before
the renderer is given anything.

**The declaration is the renderer's, not the domain's.** A version is a string the
renderer names, and it may name one the domain does not implement yet: a renderer
built for a later contract version refuses today's documents, which is the correct
outcome rather than an error in the declaration. What is refused at construction is
a declaration that cannot be meant - an empty set, or a member that is not a
non-empty string or a :class:`~inferops.domain.workload.values.Profile` - because a
renderer that supports nothing is a renderer that was not configured.

**One declaration exists in the repository**, the Helm values renderer's
``HELM_VALUES_SUPPORT``; the tests build every other.
"""

from __future__ import annotations

from dataclasses import dataclass

from ..context import NO_REQUEST_CONTEXT, RequestContext
from ..environment.binding import EnvironmentBinding
from ..workload.contract import WorkloadContract
from ..workload.errors import InvalidValueError
from ..workload.values import Profile
from .defaults import PlatformDefaults
from .errors import RenderFinding


def _versions(value: object, what: str) -> None:
    if not isinstance(value, frozenset) or not value:
        raise InvalidValueError(f"{what} must be a non-empty frozenset")
    for member in value:
        if not isinstance(member, str) or not member:
            raise InvalidValueError(f"each of {what} must be a non-empty string")


@dataclass(frozen=True, slots=True)
class RendererSupport:
    """The inputs one renderer takes. Every set is required and non-empty."""

    contract_versions: frozenset[str]
    binding_versions: frozenset[str]
    platform_defaults_versions: frozenset[str]
    profiles: frozenset[Profile]

    def __post_init__(self) -> None:
        _versions(self.contract_versions, "the contract versions a renderer takes")
        _versions(self.binding_versions, "the binding versions a renderer takes")
        _versions(
            self.platform_defaults_versions,
            "the platform-defaults versions a renderer takes",
        )
        if not isinstance(self.profiles, frozenset) or not self.profiles:
            raise InvalidValueError(
                "the profiles a renderer takes must be a non-empty frozenset"
            )
        for profile in self.profiles:
            if not isinstance(profile, Profile):
                raise InvalidValueError(
                    "each profile a renderer takes must be a Profile"
                )


def unsupported_contract_findings(
    support: RendererSupport,
    contract: WorkloadContract,
    platform_defaults: PlatformDefaults,
    context: RequestContext = NO_REQUEST_CONTEXT,
) -> list[RenderFinding]:
    """Every way the contract or the defaults are outside what the renderer takes.

    Each reason names the field and the rule, and leaves the version or profile in
    the input: a version string is author-supplied text.
    """
    findings: list[RenderFinding] = []
    if str(contract.api_version) not in support.contract_versions:
        findings.append(
            RenderFinding(
                "render-contract-version-unsupported",
                "contract.apiVersion",
                "the renderer does not take this contract version",
                context,
            )
        )
    if contract.spec.profile not in support.profiles:
        findings.append(
            RenderFinding(
                "render-profile-unsupported",
                "contract.spec.profile",
                "the renderer was not built for this profile",
                context,
            )
        )
    if platform_defaults.version not in support.platform_defaults_versions:
        findings.append(
            RenderFinding(
                "render-defaults-version-unsupported",
                "platformDefaults.version",
                "the renderer does not take this platform-defaults version",
                context,
            )
        )
    return findings


def unsupported_binding_findings(
    support: RendererSupport,
    binding: EnvironmentBinding,
    index: int,
    context: RequestContext = NO_REQUEST_CONTEXT,
) -> list[RenderFinding]:
    """The selected binding's version, if the renderer does not take it."""
    if str(binding.api_version) in support.binding_versions:
        return []
    return [
        RenderFinding(
            "render-binding-version-unsupported",
            f"bindings[{index}].apiVersion",
            "the renderer does not take this binding version",
            context,
        )
    ]


__all__ = [
    "RendererSupport",
    "unsupported_binding_findings",
    "unsupported_contract_findings",
]
