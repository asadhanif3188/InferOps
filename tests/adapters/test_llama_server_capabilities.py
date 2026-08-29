"""The capability declaration, and the rule that a presence needs a record.

The serving contract requires capabilities to be declared rather than assumed.
This suite holds the declaration for the selected runtime to three things:

- both optional capabilities the contract names are declared, so no caller has to
  guess about token metrics;
- streaming is unsupported, because V1's protocol has no streaming method and a
  supported declaration would promise a call nobody can make;
- **every supported capability cites a committed record**, and every unsupported
  one cites none. Declaring an absence needs no evidence; declaring a presence
  does, and a supported capability with nothing behind it is exactly the
  overclaim this project treats as a defect.

Every check reads files from this repository and objects from this distribution.
No network, no cluster, no model, no clock, no randomness. Nothing here observes
a capability; it checks that a declaration says what a record supports.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from inferops.adapters.llama_cpp import (
    CAPABILITY_DETERMINISTIC_FIXTURE_REPLAY,
    CAPABILITY_REAL_MODEL_INFERENCE,
    CAPABILITY_STREAMING,
    CAPABILITY_TOKEN_COUNTING,
    LLAMA_SERVER_CAPABILITIES,
    LLAMA_SERVER_CAPABILITY_BASES,
    RUNTIME_FEASIBILITY_REF,
    CapabilityBasis,
)
from inferops.domain.serving import AdapterCapability

pytestmark = pytest.mark.adapter

REPO_ROOT = Path(__file__).resolve().parents[2]

DECLARED = {entry.name: entry for entry in LLAMA_SERVER_CAPABILITIES}


def test_the_declaration_is_domain_objects_rather_than_loose_strings() -> None:
    assert LLAMA_SERVER_CAPABILITIES
    assert all(
        isinstance(entry, AdapterCapability) for entry in LLAMA_SERVER_CAPABILITIES
    )


def test_the_declaration_is_immutable() -> None:
    """One caller mutating a list every other caller reads is the bug avoided."""
    assert isinstance(LLAMA_SERVER_CAPABILITIES, tuple)
    assert isinstance(LLAMA_SERVER_CAPABILITY_BASES, tuple)


def test_no_capability_is_declared_twice() -> None:
    names = [entry.name for entry in LLAMA_SERVER_CAPABILITIES]
    assert len(names) == len(set(names))


def test_both_optional_capabilities_the_contract_names_are_declared() -> None:
    """Not declaring one leaves a caller to guess, and a guess becomes a number."""
    assert CAPABILITY_STREAMING in DECLARED
    assert CAPABILITY_TOKEN_COUNTING in DECLARED


def test_streaming_is_declared_unsupported() -> None:
    """V1's protocol publishes no streaming method for a caller to reach."""
    assert DECLARED[CAPABILITY_STREAMING].supported is False


def test_token_counting_is_declared_supported() -> None:
    """The runtime derives counts from its own tokeniser and returns them."""
    assert DECLARED[CAPABILITY_TOKEN_COUNTING].supported is True


def test_real_model_inference_is_declared_supported() -> None:
    assert DECLARED[CAPABILITY_REAL_MODEL_INFERENCE].supported is True


def test_fixture_replay_is_declared_unsupported() -> None:
    """Replaying a fixture is the mock's capability, and the two stay apart."""
    assert DECLARED[CAPABILITY_DETERMINISTIC_FIXTURE_REPLAY].supported is False


def test_the_declaration_and_its_bases_describe_the_same_capabilities() -> None:
    assert tuple(entry.capability for entry in LLAMA_SERVER_CAPABILITY_BASES) == (
        LLAMA_SERVER_CAPABILITIES
    )


@pytest.mark.parametrize(
    "entry", LLAMA_SERVER_CAPABILITY_BASES, ids=lambda e: e.capability.name
)
def test_every_declaration_states_why_it_says_what_it_says(
    entry: CapabilityBasis,
) -> None:
    assert entry.basis.strip()


@pytest.mark.parametrize(
    "entry", LLAMA_SERVER_CAPABILITY_BASES, ids=lambda e: e.capability.name
)
def test_a_supported_capability_cites_a_record_and_an_unsupported_one_does_not(
    entry: CapabilityBasis,
) -> None:
    """A presence needs evidence; an absence does not."""
    if entry.capability.supported:
        assert entry.evidence_ref, entry.capability.name
    else:
        assert entry.evidence_ref is None, entry.capability.name


@pytest.mark.parametrize(
    "entry", LLAMA_SERVER_CAPABILITY_BASES, ids=lambda e: e.capability.name
)
def test_every_cited_record_is_committed(entry: CapabilityBasis) -> None:
    if entry.evidence_ref is None:
        return
    assert (REPO_ROOT / entry.evidence_ref).is_file(), entry.evidence_ref


def test_every_supported_capability_rests_on_the_executed_trial() -> None:
    """The only record this project has that observed the runtime at all."""
    cited = {
        entry.evidence_ref
        for entry in LLAMA_SERVER_CAPABILITY_BASES
        if entry.capability.supported
    }
    assert cited == {RUNTIME_FEASIBILITY_REF}
