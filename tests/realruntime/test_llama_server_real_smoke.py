"""The real-runtime smoke test: one completion, from the real model, through the adapter.

This is the only executable check in this repository that talks to a running
`llama-server` holding the pinned model, and it is **deselected by default**. The
committed marker expression in [`pytest.ini`](../../pytest.ini) excludes
``realruntime``, so a contributor reaches this suite only by naming the marker on
the command line, which is what makes "the default lane cannot execute a real
model" a property of the configuration rather than a promise in a document.

## What running it requires

A `llama-server` deployment holding the pinned model, reachable from wherever
`pytest` runs, with the six required environment variables set — the same ones
:mod:`inferops.adapters.llama_cpp.settings` publishes. Every one of them is read
from the process environment **only here**, never inside the distribution, and
this suite skips rather than fails when they are absent: a missing endpoint means
nobody asked for a real run, not that a real run failed.

```sh
python -m pytest tests/realruntime -m realruntime -q
```

## What it may be used to claim

Nothing, on its own. A passing run is one input to
[an evidence record](../../docs/proof/README.md) that also names the image digest,
the model revision and per-file hash, the environment, the exact commands, and the
results. Boundary rule 3 in
[the mock and real boundary](../../docs/serving/mock-and-real-boundary.md) is
explicit: a real-runtime claim links to such a record, and a claim whose only
support is a document is `documented and unexecuted`.

## What it deliberately does not assert

**Determinism.** The trial observed byte-identical content across three runs at
temperature 0, and this adapter sends no temperature because `ADR 0002` leaves the
sampling defaults undecided. Asserting on generated text would therefore be
asserting on a model's output under sampling nobody has pinned.

**Latency, decode rate, or throughput.** V1 may publish no such figure, and a test
that measured one would be a capacity claim arriving through a side door.

**The prompt below is fixed, neutral, and public.** It carries no host detail and
no personal data, and neither the prompt nor the completion is written to a file
by this suite. Whoever produces the evidence record decides what of a completion
is safe to publish; a test does not decide that by writing it somewhere.
"""

from __future__ import annotations

import os

import pytest

from inferops.adapters.llama_cpp import (
    LLAMA_SERVER_ADAPTER_KIND,
    LLAMA_SERVER_RUNTIME_NAME,
    PINNED_MODEL_FILE,
    PINNED_MODEL_REVISION,
    REQUIRED_ENVIRONMENT_VARIABLES,
    HttpRuntimeTransport,
    LlamaServerAdapter,
    LlamaServerSettings,
)
from inferops.domain.context import RequestContext
from inferops.domain.serving import AdapterConfiguration

pytestmark = pytest.mark.realruntime

#: The platform model identity used for a smoke run. Kebab-case, and not
#: mock-labelled — the adapter refuses a mock-labelled identity, which is one of
#: the safeguards this run also exercises.
SMOKE_MODEL_IDENTIFIER = "qwen3-1-7b-instruct"

#: A fixed, neutral, publishable prompt. The feasibility trial used this exact
#: question for the same reason: the answer is a plain factual sentence that is
#: safe to publish, which is why it was chosen.
SMOKE_PROMPT = "In one sentence, what is Kubernetes?"

#: The generation bound. Bounded so a smoke run cannot become a capacity test.
SMOKE_MAX_TOKENS = 128

#: How long one smoke request may take. `ADR 0002` recorded 14.52 s worst case for
#: a 128-token completion on one host on one day, against a 120 s limit. This is
#: the limit rather than the measurement, and it is not a performance assertion.
SMOKE_TIMEOUT_MS = 120_000

#: Identifiers a real run carries, so a completion can be correlated with a log.
SMOKE_CONTEXT = RequestContext(
    request_id="v1-s1-004-pr2-smoke",
    correlation_id="v1-s1-004-pr2-smoke",
)


def _environment() -> dict[str, str]:
    """The runtime settings from the process environment, or a skip.

    The one place in this repository that reads the process environment for these
    variables. Everything in the distribution takes a mapping, so nothing there
    depends on ambient state; this suite is the edge where ambient state legally
    enters.
    """
    missing = [
        name for name in REQUIRED_ENVIRONMENT_VARIABLES if not os.environ.get(name)
    ]
    if missing:
        pytest.skip(
            "the real-runtime lane is authorization-gated and was not entered; "
            f"{len(missing)} of {len(REQUIRED_ENVIRONMENT_VARIABLES)} required "
            "runtime settings are unset"
        )
    return {name: os.environ[name] for name in REQUIRED_ENVIRONMENT_VARIABLES}


@pytest.fixture
def settings() -> LlamaServerSettings:
    """Settings built from the environment, validated before anything is dialled."""
    return LlamaServerSettings.from_environment(_environment())


@pytest.fixture
async def adapter(settings: LlamaServerSettings):
    """An initialized adapter over the standard-library transport.

    Shut down after the test whatever it did, so a failing assertion does not
    leave a connection or a readiness observation behind.
    """
    instance = LlamaServerAdapter(settings, HttpRuntimeTransport())
    await instance.initialize(
        AdapterConfiguration(
            model_identifier=SMOKE_MODEL_IDENTIFIER,
            timeout_ms=SMOKE_TIMEOUT_MS,
            max_tokens=SMOKE_MAX_TOKENS,
        ),
        SMOKE_CONTEXT,
    )
    try:
        yield instance
    finally:
        await instance.shutdown(SMOKE_CONTEXT)


async def test_the_runtime_reports_itself_ready(adapter: LlamaServerAdapter) -> None:
    """Readiness before inference, because the runtime answers 503 while loading.

    A failure here is a *stage*, not a mystery: the runtime was reachable and said
    it could not serve, or it could not be reached at all, and
    ``adapter.readiness_state`` says which.
    """
    ready = await adapter.is_ready(SMOKE_CONTEXT)

    assert ready is True, adapter.readiness_state


async def test_the_runtime_serves_the_model_it_was_configured_with(
    adapter: LlamaServerAdapter,
) -> None:
    """Identity, read from the runtime and compared to the configuration.

    The echoed alias proves the flag was accepted and proves nothing about which
    bytes were loaded — the runtime exposes no hash of the file it loaded, and
    this assertion does not pretend otherwise.
    """
    observed = await adapter.observe_identity(SMOKE_CONTEXT)

    assert adapter.disagreements == (), observed
    assert observed.model_file == PINNED_MODEL_FILE
    assert observed.model_alias == adapter.settings.model_alias


async def test_the_runtime_reports_a_build_this_record_can_name(
    adapter: LlamaServerAdapter,
) -> None:
    """A version identifier for the evidence record, whatever it turns out to be.

    Not compared to the observed build string in the feasibility record: that was
    one image on one day, and a newer digest reporting a newer build is a fact to
    record rather than a failure.
    """
    await adapter.observe_identity(SMOKE_CONTEXT)
    metadata = await adapter.get_runtime_metadata()

    assert metadata.name == LLAMA_SERVER_RUNTIME_NAME
    assert metadata.version


async def test_one_response_is_generated_by_the_real_model(
    adapter: LlamaServerAdapter,
) -> None:
    """The story's acceptance criterion, executed.

    Content is asserted non-empty and nothing more. What the model said is a
    matter for the evidence record, and a test that asserted on generated text
    would be asserting on sampling this project has not pinned.
    """
    result = await adapter.infer(SMOKE_PROMPT, SMOKE_CONTEXT)

    assert result.content.strip()
    assert result.adapter_kind == LLAMA_SERVER_ADAPTER_KIND
    assert result.adapter_kind == "real"
    assert result.model == SMOKE_MODEL_IDENTIFIER


async def test_the_completion_carries_token_counts_the_runtime_derived(
    adapter: LlamaServerAdapter,
) -> None:
    """`ADR 0002`'s `T5` required `usage` as a blocking threshold, and the
    capability declaration says it is supported. This is where that declaration
    is held to a real response."""
    result = await adapter.infer(SMOKE_PROMPT, SMOKE_CONTEXT)

    assert result.usage is not None
    assert result.usage.input_tokens > 0
    assert result.usage.output_tokens > 0
    assert result.usage.total_tokens == (
        result.usage.input_tokens + result.usage.output_tokens
    )


async def test_the_generation_bound_is_honoured(adapter: LlamaServerAdapter) -> None:
    """A configured ceiling that the runtime ignored would be worth knowing."""
    result = await adapter.infer(SMOKE_PROMPT, SMOKE_CONTEXT)

    assert result.usage is not None
    assert result.usage.output_tokens <= SMOKE_MAX_TOKENS


async def test_the_model_metadata_names_the_pinned_revision(
    adapter: LlamaServerAdapter,
) -> None:
    """Configured, not attested. The revision is a pin this project holds; the
    runtime attests no such thing and this assertion claims no more than that."""
    metadata = await adapter.get_model_metadata()

    assert metadata.identifier == SMOKE_MODEL_IDENTIFIER
    assert metadata.revision == PINNED_MODEL_REVISION
