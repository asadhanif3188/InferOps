# Model acquisition and verification

InferOps retrieves one selected open model into a cache scoped to this checkout.
The workflow is repository tooling: it does not package or start a serving runtime,
does not contact a cluster, and does not make a real-serving claim.

The machine-readable [model source record](model-source.v1.json) and
[ADR 0002](../architecture/decisions/ADR-0002-model-and-serving-runtime.md) agree on
the artifact identity:

| Field | Selected value |
|---|---|
| Source repository | `Qwen/Qwen3-1.7B-GGUF` |
| Revision | `90862c4b9d2787eaed51d12237eafdfe7c5f6077` |
| File | `Qwen3-1.7B-Q8_0.gguf` |
| Expected size | 1,834,426,016 bytes (about 1.71 GiB) |
| SHA-256 | `061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a` |
| Licence | Apache-2.0; [text at the selected revision](https://huggingface.co/Qwen/Qwen3-1.7B-GGUF/blob/90862c4b9d2787eaed51d12237eafdfe7c5f6077/LICENSE) |
| Download | [file at the selected revision](https://huggingface.co/Qwen/Qwen3-1.7B-GGUF/resolve/90862c4b9d2787eaed51d12237eafdfe7c5f6077/Qwen3-1.7B-Q8_0.gguf?download=true) |
| Cache root | `.cache/inferops/models` from the repository root |
| Cached artifact | `.cache/inferops/models/Qwen--Qwen3-1.7B-GGUF/90862c4b9d2787eaed51d12237eafdfe7c5f6077/Qwen3-1.7B-Q8_0.gguf` |

The revision pins the publisher's repository state. Size and SHA-256 verify the
bytes that arrive. A revision without a computed content hash is not accepted as
integrity evidence.

## Prerequisites

- Python 3.12 and the locked repository environment described in
  [CONTRIBUTING](../../CONTRIBUTING.md).
- HTTPS access to `huggingface.co`; the selected file is public and requires no
  account, token, licence click-through, or other credential.
- At least the remaining transfer size plus 64 MiB of filesystem headroom. A fresh
  cache therefore requires about 1.77 GiB free. Serving runtime images and runtime
  working space are separate disk assumptions and are not covered here.

Run the offline prerequisite and cache-state check first:

```sh
uv run --locked python -m tools.model_acquisition check
```

It reads committed state and local disk metadata only. It does not open a network
connection or download model bytes.

## Acquire, retry, and verify

A real download is explicit and transfers 1,834,426,016 bytes:

```sh
uv run --locked python -m tools.model_acquisition acquire
```

The transfer is written beside the final artifact as
`Qwen3-1.7B-Q8_0.gguf.part`. If the connection ends early, rerun the same command.
It requests the remaining byte range. If the source ignores a valid range request,
the partial file is restarted rather than appended to a full response. An
inconsistent range is refused and the partial is retained for diagnosis.

The final cache entry is never overwritten by a transfer. The partial becomes the
final file through an atomic same-directory rename only after the expected size and
SHA-256 match. An oversized or hash-invalid partial is untrusted and is discarded;
an existing invalid final file is retained and refused so that an unexpected cache
mutation is visible. Use guarded cleanup before trying again.

Verify an existing cache entry without network access:

```sh
uv run --locked python -m tools.model_acquisition verify
```

A subsequent `acquire` also verifies the existing bytes and reports `cache hit`
without opening a network connection. What a hit, a miss, and a partial each mean
for a runtime start — and how each is classified without a network connection — is
in [the model lifecycle](model-lifecycle.md#cache-hit-miss-and-partial).

## Workspace-scoped cleanup

Preview the exact cache and byte count; this changes nothing:

```sh
uv run --locked python -m tools.model_acquisition clean
```

Remove it only with confirmation:

```sh
uv run --locked python -m tools.model_acquisition clean --confirm
```

The command has no cache-path override. It refuses a target outside
`.cache/inferops/models`, a cache path resolving outside the checkout, and symbolic
links in or above the managed tree. It does not remove serving images, cluster
volumes, other `.cache` content, or any file outside the documented model cache.

## Failure and log safety

The command exits non-zero and identifies the refusing stage for a prerequisite,
size, digest, transfer, or cleanup failure. It accepts no token, password, header,
or alternate URL and logs none. Network failures are reported without echoing
third-party response bodies or exception text. The public pinned source and licence
URLs are the only network locations it prints.

Repository tests use tiny synthetic byte strings and never download the model. A
passing repository-only test proves the retry, verification, and cleanup mechanics;
it is `local-static` evidence and does not prove that the real artifact is available
or that a runtime can serve it.
