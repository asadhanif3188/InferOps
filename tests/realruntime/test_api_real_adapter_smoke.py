"""The API in front of the real adapter: one completion, through the whole stack.

The suite beside this one drives the `llama-server` adapter directly. This one
puts the InferOps API in front of it and drives *that*, composed the way a
deployment would be composed — from configuration, through
:func:`inferops.api.select`, with the adapter chosen because
``INFEROPS_SERVING_ADAPTER`` said ``real`` and for no other reason.

It is **deselected by default**. The committed marker expression in
[`pytest.ini`](../../pytest.ini) excludes ``realruntime``, so a contributor
reaches it only by naming the marker on the command line, which is what makes
"the default lane cannot execute a real model" a property of the configuration
rather than a promise in a document.

## What running it requires

A `llama-server` deployment holding the pinned model, reachable from wherever
`pytest` runs, with the six runtime variables
:mod:`inferops.adapters.llama_cpp.settings` publishes **and** the three
:mod:`inferops.api.selection` publishes. Every one is read from the process
environment only here and never inside the distribution, and this suite skips
rather than fails when they are absent: a missing endpoint means nobody asked for
a real run, not that a real run failed.

```sh
python -m pytest tests/realruntime -m realruntime -q
```

## What it may be used to claim

Nothing on its own. A passing run is one input to
[an evidence record](../../docs/proof/README.md) that also names the image digest,
the model revision and per-file hash, the environment, the exact commands, and the
results. **This suite has not been run against a runtime by the change that added
it**, and the record for that change says so rather than presenting a skipped
session as a green one.

## What it deliberately does not assert

**Determinism, latency, decode rate, or throughput** — for the same reasons the
adapter smoke suite gives, and because a test that measured one would be a
capacity claim arriving through a side door.

**The prompt below is fixed, neutral, and public.** Neither it nor the completion
is written to a file by this suite. Whoever produces the evidence record decides
what of a completion is safe to publish; a test does not decide that by writing it
somewhere.
"""

from __future__ import annotations

import json
import os

import pytest

from inferops.adapters.llama_cpp import (
    PINNED_MODEL_REVISION,
    LlamaServerAdapter,
)
from inferops.adapters.llama_cpp import (
    REQUIRED_ENVIRONMENT_VARIABLES as RUNTIME_VARIABLES,
)
from inferops.api import (
    ADAPTER_REAL,
    CORRELATION_ID_HEADER,
    ENV_ADAPTER,
    EXTENSION_MEMBER,
    REQUEST_ID_HEADER,
    Selection,
    select,
)
from inferops.api import (
    REQUIRED_ENVIRONMENT_VARIABLES as SELECTION_VARIABLES,
)
from inferops.api.surface import CHAT_COMPLETIONS_PATH, MODELS_PATH, READY_PATH
from tests.support import asgi_client

pytestmark = pytest.mark.realruntime

#: Every variable a real deployment of this API needs set.
ALL_VARIABLES: tuple[str, ...] = (*SELECTION_VARIABLES, *RUNTIME_VARIABLES)

#: A fixed, neutral, publishable prompt. The feasibility trial used this exact
#: question for the same reason: the answer is a plain factual sentence that is
#: safe to publish.
SMOKE_PROMPT = "In one sentence, what is Kubernetes?"

#: Identifiers a real run carries, so a completion can be correlated with a log.
SMOKE_REQUEST_ID = "v1-s1-005-pr2-smoke"
SMOKE_CORRELATION_ID = "v1-s1-005-pr2-smoke"


def _environment() -> dict[str, str]:
    """The deployment's configuration from the process environment, or a skip.

    ``INFEROPS_SERVING_ADAPTER`` must say ``real``. A run of this suite against a
    mock-configured environment would be a real-runtime record produced by a mock,
    which is the exact artifact boundary rule 4 exists to prevent — so it is a
    **failure** rather than a skip.
    """
    missing = [name for name in ALL_VARIABLES if not os.environ.get(name)]
    if missing:
        pytest.skip(
            "the real-runtime lane is authorization-gated and was not entered; "
            f"{len(missing)} of {len(ALL_VARIABLES)} required variables are unset"
        )
    selected = os.environ[ENV_ADAPTER]
    assert selected == ADAPTER_REAL, (
        f"{ENV_ADAPTER} must be {ADAPTER_REAL!r} for this suite; a real-runtime "
        f"record produced by a mock-configured deployment is what boundary rule 4 "
        f"forbids, and it was {selected!r}"
    )
    return {name: os.environ[name] for name in ALL_VARIABLES}


@pytest.fixture
def selection() -> Selection:
    """The deployment one environment describes, composed and not started."""
    return select(_environment())


@pytest.fixture
async def api(selection: Selection):
    """The application, started over the real adapter and shut down afterwards.

    Shut down whatever the test did, so a failing assertion does not leave a
    connection or a readiness observation behind.
    """
    from inferops.api import InferOpsApi

    instance = InferOpsApi(
        adapter=selection.adapter,
        adapter_configuration=selection.adapter_configuration,
        configuration=selection.configuration,
    )
    await instance.startup()
    try:
        yield instance
    finally:
        await instance.shutdown()


async def _complete(api) -> asgi_client.Response:
    body = json.dumps(
        {
            "model": os.environ["INFEROPS_MODEL_IDENTIFIER"],
            "messages": [{"role": "user", "content": SMOKE_PROMPT}],
        }
    ).encode("utf-8")
    return await asgi_client.request(
        api,
        "POST",
        CHAT_COMPLETIONS_PATH,
        body=body,
        headers=[
            (REQUEST_ID_HEADER, SMOKE_REQUEST_ID),
            (CORRELATION_ID_HEADER, SMOKE_CORRELATION_ID),
        ],
    )


def test_the_selection_composed_the_real_adapter_because_configuration_said_so(
    selection: Selection,
) -> None:
    """The property the whole lane rests on: what is behind this API is real
    because the configuration named it, and the label says the same thing."""
    assert isinstance(selection.adapter, LlamaServerAdapter)
    assert selection.adapter_kind == "real"
    assert selection.is_mock is False


async def test_readiness_reflects_the_real_backend(api) -> None:
    """Readiness before inference, because the runtime answers 503 while loading."""
    response = await asgi_client.request(api, "GET", READY_PATH)

    assert response.status == 200
    assert response.json() == {
        "status": "ready",
        "adapterKind": "real",
        "state": "serving",
    }


async def test_the_model_list_describes_the_real_runtime(api) -> None:
    response = await asgi_client.request(api, "GET", MODELS_PATH)
    body = response.json()

    assert response.status == 200
    assert body[EXTENSION_MEMBER]["adapterKind"] == "real"
    assert body[EXTENSION_MEMBER]["runtime"]["version"]
    assert body[EXTENSION_MEMBER]["runtime"]["modelRevision"] == PINNED_MODEL_REVISION


async def test_one_completion_is_generated_by_the_real_model_through_the_api(
    api,
) -> None:
    """The parent story's remaining criterion, executed through the API.

    Content is asserted non-empty and nothing more. What the model said is a
    matter for the evidence record, and a test that asserted on generated text
    would be asserting on sampling this project has not pinned.
    """
    response = await _complete(api)
    body = response.json()

    assert response.status == 200
    assert body["choices"][0]["message"]["content"].strip()
    assert body[EXTENSION_MEMBER]["adapterKind"] == "real"


async def test_the_completion_carries_the_counts_the_runtime_derived(api) -> None:
    """`ADR 0002` `T5` required `usage` as a blocking threshold, and this is where
    the capability declaration is held to a real response through the API."""
    body = (await _complete(api)).json()

    assert body["usage"] is not None
    assert body["usage"]["prompt_tokens"] > 0
    assert body["usage"]["completion_tokens"] > 0
    assert body["usage"]["total_tokens"] == (
        body["usage"]["prompt_tokens"] + body["usage"]["completion_tokens"]
    )


async def test_the_identifiers_survive_the_whole_real_path(api) -> None:
    """Caller to API to adapter to runtime and back, which is the only place this
    can be observed rather than inferred."""
    response = await _complete(api)
    body = response.json()

    assert response.header(REQUEST_ID_HEADER) == SMOKE_REQUEST_ID
    assert response.header(CORRELATION_ID_HEADER) == SMOKE_CORRELATION_ID
    assert body[EXTENSION_MEMBER]["requestId"] == SMOKE_REQUEST_ID
    assert body[EXTENSION_MEMBER]["correlationId"] == SMOKE_CORRELATION_ID


async def test_a_real_deployment_still_refuses_what_the_subset_refuses(api) -> None:
    """The strict policy is not relaxed by the backend behind it, and the refusal
    is the canonical body rather than whatever the runtime would have said."""
    body = json.dumps(
        {
            "model": os.environ["INFEROPS_MODEL_IDENTIFIER"],
            "messages": [{"role": "user", "content": SMOKE_PROMPT}],
            "top_p": 0.9,
        }
    ).encode("utf-8")

    response = await asgi_client.request(api, "POST", CHAT_COMPLETIONS_PATH, body=body)
    payload = response.json()

    assert response.status == 400
    assert payload["code"] == "contract-invalid"
    assert payload["retryable"] is False
    assert payload["details"]["adapterKind"] == "real"
    assert payload["details"]["member"] == "top_p"
