# Local real composition

Status: **implemented and validated offline and through controlled seams; no real
runtime or model was executed by this change**.

The versioned
[`composition.v1.json`](../../deploy/serving/local/composition.v1.json) and
[`tools.local_composition`](../../tools/local_composition/) command provide one
host-local workflow for the InferOps API and the selected
[runtime package](local-runtime-package.md). The runtime remains the pinned Docker
container on `127.0.0.1:8080`; the API uses a narrow repository-tooling HTTP
carrier on `127.0.0.1:8090`. Neither endpoint is published beyond loopback.

This is local development tooling, not Kubernetes packaging or a production
server. It provides no TLS, caller authentication, proxy handling, multi-process
supervision, or remote exposure. The installable InferOps distribution still has
no server dependency.

## Validate without execution

From the repository root:

```text
uv run --locked python -m tools.local_composition check
```

The check reads only committed configuration. It cross-checks the runtime package,
model and image pins, API limits, telemetry identity, loopback addresses, real
adapter selection, disabled mock fallback, startup order, shutdown order, and the
absence of embedded secret values. It does not contact Docker, read model bytes,
bind a port, pull an image, or download a model.

## Run on an explicitly authorized capable host

First satisfy the runtime package's [prerequisites](local-runtime-package.md#prerequisites-for-a-real-run):
the exact image digest must already be local and the selected model must already
exist in the verified workspace cache. The composition never downloads either.

Start the attached workflow:

```text
uv run --locked python -m tools.local_composition start --confirm-real-runtime
```

Startup is deliberately ordered:

1. create the ownership-labelled runtime container;
2. wait for runtime `GET /health` to return `200`;
3. start the InferOps API with `INFEROPS_SERVING_ADAPTER=real` and the runtime
   package's loopback endpoint;
4. wait for API `GET /health/ready` to return the exact real-adapter identity.

There is no mock fallback. Runtime `503` while the model loads keeps API readiness
false; it is not promoted to ready and does not start a mock. Once both components
are ready, the command stays attached in the foreground.

In another terminal, inspect the composed state or call the API:

```text
uv run --locked python -m tools.local_composition status --confirm-real-runtime
curl --fail http://127.0.0.1:8090/health/ready
curl --fail http://127.0.0.1:8090/v1/models
```

An inference request goes to `POST http://127.0.0.1:8090/v1/chat/completions` using
the [published API subset](inference-api-surface.md). A response is visibly from
the selected path only when its `x-inferops.adapterKind` is `real`. Do not treat
the controlled default-lane test as real-runtime evidence.

## Status, logs, and cleanup

`status` is read-only but still requires the confirmation flag because it inspects
Docker and the selected real endpoints. `logs` reads only the bounded structured
records owned by this workflow and needs no runtime access:

```text
uv run --locked python -m tools.local_composition status --confirm-real-runtime
uv run --locked python -m tools.local_composition logs --lines 100
```

Records live at `.cache/inferops/composition/local-real.jsonl`, an ignored,
workspace-scoped path. They carry operational identifiers and outcomes, never
prompts, completions, runtime response bodies, Docker output, credentials, or
model bytes.

Press Ctrl+C in the attached `start` terminal. Shutdown stops the API accepting
work, drains in-flight requests, closes its adapter transport, and only then stops
and removes the exact ownership-labelled runtime container. A failed cleanup is a
failed command. After the foreground process has stopped, remove a verified
residual runtime container with:

```text
uv run --locked python -m tools.local_composition cleanup --confirm-real-runtime
```

Cleanup does not delete the model cache, remove the pinned image, prune Docker, or
touch a container without the runtime package's exact name and ownership label.

## Evidence boundary

The default tests validate configuration rendering and the full order through
synthetic command seams. A lightweight test binds a loopback port and reaches the
real adapter type through a controlled transport response; it loads no model and
contacts no real runtime. Those results stop at `C1`.

A real run requires separate authorization and a completed evidence record naming
the source revision, image digest, model revision and hash, host environment,
commands, readiness, inference result with content removed, and verified cleanup.
No such run was authorized for this change, so it makes no new real-serving or
performance claim.
