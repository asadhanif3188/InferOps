"""The one way a WorkloadContract becomes render input: every published rule passes.

A :class:`~inferops.domain.workload.contract.WorkloadContract` is a document that
could be *read*. The render boundary takes only a
:class:`ValidatedWorkloadContract`, and :func:`validate_for_render` is the only
function that makes one. It applies two sets of rules and refuses the contract,
with every finding at once, if either finds anything:

1. **The domain's semantic pipeline**, :func:`validate_workload_contract`, unchanged:
   the replica range, the secret rules, and the compatibility matrix. The matrix is
   whatever the caller gave the workload package's loader; this package reads no
   file.
2. **The profile conditions** the published schema applies through the ``allOf``
   under ``spec`` and the domain does not. The parser reads whichever profile block
   is present and the pipeline above has no rule for the pairing, so a
   ``synchronous-llm`` contract with no runtime or model pin, and a ``mock-llm``
   contract carrying the real block, both pass the domain while the published
   validator refuses them. Each condition is refused here under the rule
   identifier and at the field the published validator uses, and a test compares
   the two on every condition.

**What "validated" does not mean.** It does not mean the offline validator ran: the
domain cannot import a JSON Schema validator, and the structural constraints are
the parser's, which a test holds to the schema. It does not mean a binding exists
for the contract, that a renderer supports its profile, or that a release can
record its version. Those are separate questions with separate owners.

**The guard is against accidents, not intent.** :class:`ValidatedWorkloadContract`
refuses construction without a private sentinel, and :func:`dataclasses.replace`
cannot carry one, so no ordinary code path produces a validated contract that did
not pass. Python cannot stop a caller who imports the private name, and a test
records that limit rather than hiding it.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import InitVar, dataclass
from typing import Final

from ..context import NO_REQUEST_CONTEXT, RequestContext
from ..workload.contract import WorkloadContract, WorkloadSpec
from ..workload.errors import WorkloadValidationError
from ..workload.validation import validate_workload_contract
from ..workload.values import AcceleratorType, Environment, Profile, ServingCapability
from .errors import WorkloadNotAcceptedError

#: Held only by this module. A value constructed without it is refused.
_ISSUED: Final = object()


@dataclass(frozen=True, slots=True)
class ProfileCondition:
    """One condition the schema applies to a profile, and how it is refused.

    ``holds`` answers for a parsed spec of that profile; ``field`` and ``rule_id``
    are the published validator's, with its ``$.`` prefix dropped to match the
    domain pipeline's field addresses.
    """

    profile: Profile
    field: str
    rule_id: str
    reason: str
    holds: Callable[[WorkloadSpec], bool]


_SYNC = Profile.SYNCHRONOUS_LLM
_MOCK = Profile.MOCK_LLM

#: Every condition under ``spec.allOf`` in the published schema, one per leaf.
PROFILE_CONDITIONS: Final[tuple[ProfileCondition, ...]] = (
    ProfileCondition(
        _SYNC,
        "spec.synchronousLlm",
        "field-required",
        "the synchronous-llm profile requires its own profile block",
        lambda spec: spec.synchronous_llm is not None,
    ),
    ProfileCondition(
        _SYNC,
        "spec",
        "value-not-permitted",
        "the synchronous-llm profile does not permit the mock-llm profile block",
        lambda spec: spec.mock_llm is None,
    ),
    ProfileCondition(
        _SYNC,
        "spec.model.servingCapability",
        "value-not-permitted",
        "the synchronous-llm profile requires 'inferops-native-serving'",
        lambda spec: spec.model.serving_capability is ServingCapability.NATIVE,
    ),
    ProfileCondition(
        _MOCK,
        "spec.mockLlm",
        "field-required",
        "the mock-llm profile requires its own profile block",
        lambda spec: spec.mock_llm is not None,
    ),
    ProfileCondition(
        _MOCK,
        "spec",
        "value-not-permitted",
        "the mock-llm profile does not permit the synchronous-llm profile block",
        lambda spec: spec.synchronous_llm is None,
    ),
    ProfileCondition(
        _MOCK,
        "spec.environment",
        "value-not-permitted",
        "the mock-llm profile requires the 'ci' environment",
        lambda spec: spec.environment is Environment.CI,
    ),
    ProfileCondition(
        _MOCK,
        "spec.model.servingCapability",
        "value-not-permitted",
        "the mock-llm profile requires 'inferops-mock-serving'",
        lambda spec: spec.model.serving_capability is ServingCapability.MOCK,
    ),
    ProfileCondition(
        _MOCK,
        "spec.resources.accelerator.type",
        "value-not-permitted",
        "the mock-llm profile requires accelerator type 'none'",
        lambda spec: spec.resources.accelerator.type is AcceleratorType.NONE,
    ),
    ProfileCondition(
        _MOCK,
        "spec.resources.accelerator.count",
        "value-not-permitted",
        "the mock-llm profile requires an accelerator count of 0",
        lambda spec: spec.resources.accelerator.count == 0,
    ),
    ProfileCondition(
        _MOCK,
        "spec.evidence.proofRefs",
        "value-out-of-range",
        "the mock-llm profile permits no proof references",
        lambda spec: not spec.evidence.proof_refs,
    ),
)


def profile_condition_findings(
    contract: WorkloadContract,
    context: RequestContext = NO_REQUEST_CONTEXT,
) -> list[WorkloadValidationError]:
    """Every profile condition the contract fails. Never repeats a document value."""
    return [
        WorkloadValidationError(
            condition.field, condition.rule_id, condition.reason, context=context
        )
        for condition in PROFILE_CONDITIONS
        if condition.profile is contract.spec.profile
        and not condition.holds(contract.spec)
    ]


@dataclass(frozen=True, slots=True)
class ValidatedWorkloadContract:
    """A WorkloadContract that passed every rule :func:`validate_for_render` applies.

    Constructed only by that function. Holds the contract it was given, unchanged
    and not copied.
    """

    contract: WorkloadContract
    issued: InitVar[object] = None

    def __post_init__(self, issued: object) -> None:
        if issued is not _ISSUED:
            raise TypeError(
                "a ValidatedWorkloadContract is produced by validate_for_render, "
                "never constructed directly"
            )


def validate_for_render(
    contract: WorkloadContract,
    *,
    context: RequestContext = NO_REQUEST_CONTEXT,
) -> ValidatedWorkloadContract:
    """The contract as render input, or every reason it cannot be.

    Raises:
        WorkloadNotAcceptedError: carrying every finding of both rule sets, sorted.
        TypeError: ``contract`` is not a parsed WorkloadContract.
        ValueError: a ``synchronous-llm`` contract was given and no compatibility
            matrix was supplied to the workload package's loader.
    """
    if not isinstance(contract, WorkloadContract):
        raise TypeError(
            "contract must be a WorkloadContract produced by parse_workload_contract, "
            "not a raw document"
        )
    findings = [
        *validate_workload_contract(contract, context),
        *profile_condition_findings(contract, context),
    ]
    if findings:
        raise WorkloadNotAcceptedError(tuple(findings))
    return ValidatedWorkloadContract(contract, _ISSUED)


__all__ = [
    "PROFILE_CONDITIONS",
    "ProfileCondition",
    "ValidatedWorkloadContract",
    "profile_condition_findings",
    "validate_for_render",
]
