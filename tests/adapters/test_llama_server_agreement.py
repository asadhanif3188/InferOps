"""The strings the two adapters must agree on, compared rather than trusted.

Neither adapter may import the other. The mock replays a fixture and the
`llama.cpp` package configures a real runtime; coupling them would make the mock
depend on a runtime it has nothing to do with, and the composition point is what
chooses between them. So each holds its own copy of a small number of strings.

**A copy nobody compares to its source drifts**, and two of these copies are
safeguards rather than conveniences. The mock refuses a model identity that is
*not* mock-labelled; the real path refuses one that *is*. Together they mean a
transcript cannot name the wrong kind of provider in either direction — but only
while both are looking for the same prefix. Renaming one and not the other would
leave both refusals passing their own suites and the mutual exclusion silently
gone, which is exactly the failure this module exists to turn into a red test.

The capability names are here for the weaker version of the same reason: a caller
inspecting capabilities across both adapters is comparing strings, and two
spellings of `token-counting` would make one adapter's declaration invisible to
a reader of the other's.

Every check reads objects from this distribution. No network, no cluster, no
model, no clock, no randomness.
"""

from __future__ import annotations

import pytest

from inferops.adapters import mock_serving
from inferops.adapters.llama_cpp import capabilities, settings

pytestmark = pytest.mark.adapter


def test_both_adapters_look_for_the_same_mock_prefix() -> None:
    """The safeguard is mutual, and it only works if the string is one string."""
    assert settings.MOCK_IDENTITY_PREFIX == mock_serving.MOCK_MODEL_IDENTIFIER_PREFIX


@pytest.mark.parametrize(
    ("real_name", "mock_name"),
    [
        (capabilities.CAPABILITY_STREAMING, mock_serving.CAPABILITY_STREAMING),
        (
            capabilities.CAPABILITY_TOKEN_COUNTING,
            mock_serving.CAPABILITY_TOKEN_COUNTING,
        ),
        (
            capabilities.CAPABILITY_REAL_MODEL_INFERENCE,
            mock_serving.CAPABILITY_REAL_MODEL_INFERENCE,
        ),
        (
            capabilities.CAPABILITY_DETERMINISTIC_FIXTURE_REPLAY,
            mock_serving.CAPABILITY_DETERMINISTIC_FIXTURE_REPLAY,
        ),
    ],
    ids=["streaming", "token-counting", "real-model-inference", "fixture-replay"],
)
def test_both_adapters_spell_a_capability_the_same_way(
    real_name: str, mock_name: str
) -> None:
    assert real_name == mock_name


def test_both_adapters_declare_the_same_set_of_capabilities() -> None:
    """Not the same answers — the same questions.

    What each adapter *says* about a capability is its own business and the two
    disagree on three of the four. Which capabilities they answer for is not: a
    caller that can ask the mock about fixture replay and cannot ask the real
    adapter has to special-case one of them.
    """
    real = {entry.name for entry in capabilities.LLAMA_SERVER_CAPABILITIES}
    mock = {entry.name for entry in mock_serving.MOCK_CAPABILITIES}
    assert real == mock


def test_the_two_adapters_disagree_where_they_should() -> None:
    """The declarations are opposites on everything that separates them.

    Asserted so that a change making the real declaration a copy of the mock's —
    or the reverse — fails here rather than passing as a tidy-up.
    """
    real = {
        entry.name: entry.supported for entry in capabilities.LLAMA_SERVER_CAPABILITIES
    }
    mock = {entry.name: entry.supported for entry in mock_serving.MOCK_CAPABILITIES}

    assert real[capabilities.CAPABILITY_REAL_MODEL_INFERENCE] is True
    assert mock[mock_serving.CAPABILITY_REAL_MODEL_INFERENCE] is False

    assert real[capabilities.CAPABILITY_DETERMINISTIC_FIXTURE_REPLAY] is False
    assert mock[mock_serving.CAPABILITY_DETERMINISTIC_FIXTURE_REPLAY] is True

    assert real[capabilities.CAPABILITY_TOKEN_COUNTING] is True
    assert mock[mock_serving.CAPABILITY_TOKEN_COUNTING] is False


def test_neither_adapter_declares_streaming() -> None:
    """V1's protocol has no streaming method, so this is the one they share."""
    real = {
        entry.name: entry.supported for entry in capabilities.LLAMA_SERVER_CAPABILITIES
    }
    mock = {entry.name: entry.supported for entry in mock_serving.MOCK_CAPABILITIES}
    assert real[capabilities.CAPABILITY_STREAMING] is False
    assert mock[mock_serving.CAPABILITY_STREAMING] is False


def test_the_two_adapter_kinds_are_the_closed_vocabulary_and_are_distinct() -> None:
    """Neither adapter may be configured into the other's kind."""
    from inferops.adapters.llama_cpp import LLAMA_SERVER_ADAPTER_KIND
    from inferops.domain.serving import ACCEPTED_ADAPTER_KINDS

    assert LLAMA_SERVER_ADAPTER_KIND != mock_serving.MOCK_ADAPTER_KIND
    assert {
        LLAMA_SERVER_ADAPTER_KIND,
        mock_serving.MOCK_ADAPTER_KIND,
    } == set(ACCEPTED_ADAPTER_KINDS)


def test_the_two_runtime_identities_are_distinct() -> None:
    """A mock result and a real one must not name the same runtime."""
    from inferops.adapters.llama_cpp import (
        LLAMA_SERVER_RUNTIME_ID,
        LLAMA_SERVER_SERVING_CAPABILITY,
    )

    assert LLAMA_SERVER_RUNTIME_ID != mock_serving.MOCK_RUNTIME_ID
    assert LLAMA_SERVER_SERVING_CAPABILITY != mock_serving.MOCK_SERVING_CAPABILITY
