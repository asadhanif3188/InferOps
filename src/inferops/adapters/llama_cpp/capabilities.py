"""What the selected runtime can be asked for, and what supports each answer.

The serving contract requires capabilities to be *declared* rather than assumed,
and the reason is the one the mock adapter states for itself: a caller that has
to guess whether token counts are available is a caller that will eventually put
a guessed number in a record. This module holds that declaration for the runtime
`ADR 0002` selected, with the basis for each entry beside it.

**A declaration is not an execution.** Every supported entry below cites the
record that observed the behaviour, and every one of those records is the Sprint
0 feasibility trial rather than anything this package has run. The adapter that
reports these capabilities through the protocol does not exist yet; it arrives
with the inference client, and its own evidence arrives with it.
"""

from __future__ import annotations

from dataclasses import dataclass

from ...domain.serving import AdapterCapability
from .pins import RUNTIME_FEASIBILITY_REF

#: Streaming. Declared unsupported for the same reason the mock declares it so:
#: V1's protocol is synchronous and contains no streaming method, so a supported
#: declaration would promise a call nobody can make. This says nothing about
#: whether the runtime itself can stream.
CAPABILITY_STREAMING = "streaming"

#: Token counting. The runtime derives counts from its own tokeniser and returns
#: them in the response body.
CAPABILITY_TOKEN_COUNTING = "token-counting"

#: Whether a model produced the response. This is the capability layer stating
#: what ``adapter_kind`` states, in the place a caller inspecting capabilities
#: will look.
CAPABILITY_REAL_MODEL_INFERENCE = "real-model-inference"

#: Fixture replay, which is the mock's capability and is unsupported here.
CAPABILITY_DETERMINISTIC_FIXTURE_REPLAY = "deterministic-fixture-replay"


@dataclass(frozen=True, slots=True)
class CapabilityBasis:
    """One declared capability and what the project has to support declaring it.

    ``evidence_ref`` is required for a supported capability and absent for an
    unsupported one. Declaring an absence needs no evidence; declaring a presence
    does, and a supported capability with nothing behind it is the overclaim this
    structure exists to make visible.
    """

    capability: AdapterCapability
    basis: str
    evidence_ref: str | None = None


#: The declaration, with its basis. Read this rather than the tuple below when
#: the question is *why* an entry says what it says.
LLAMA_SERVER_CAPABILITY_BASES: tuple[CapabilityBasis, ...] = (
    CapabilityBasis(
        capability=AdapterCapability(name=CAPABILITY_STREAMING, supported=False),
        basis=(
            "V1's serving protocol is synchronous and publishes no streaming "
            "method, so no adapter may declare streaming supported. This is a "
            "statement about the contract, not about the runtime."
        ),
    ),
    CapabilityBasis(
        capability=AdapterCapability(name=CAPABILITY_TOKEN_COUNTING, supported=True),
        basis=(
            "The runtime returns token counts derived from its own tokeniser in "
            "the response body. The feasibility trial read them there."
        ),
        evidence_ref=RUNTIME_FEASIBILITY_REF,
    ),
    CapabilityBasis(
        capability=AdapterCapability(
            name=CAPABILITY_REAL_MODEL_INFERENCE, supported=True
        ),
        basis=(
            "The pinned runtime holding the pinned model answered inference "
            "requests inside a cluster. That is a property of the runtime and "
            "the model; whether this project's adapter reaches it is a separate "
            "question, answered by the adapter's own record."
        ),
        evidence_ref=RUNTIME_FEASIBILITY_REF,
    ),
    CapabilityBasis(
        capability=AdapterCapability(
            name=CAPABILITY_DETERMINISTIC_FIXTURE_REPLAY, supported=False
        ),
        basis=(
            "This runtime generates text. Replaying a fixture is the mock's "
            "capability and declaring it here would erase the distinction the "
            "mock and real boundary rests on."
        ),
    ),
)

#: The declaration itself, in the form the protocol's ``get_capabilities``
#: returns. A tuple rather than a list, so that no caller can mutate the
#: declaration every other caller reads.
LLAMA_SERVER_CAPABILITIES: tuple[AdapterCapability, ...] = tuple(
    entry.capability for entry in LLAMA_SERVER_CAPABILITY_BASES
)
