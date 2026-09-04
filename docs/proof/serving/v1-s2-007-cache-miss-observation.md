# `V1-S2-007` real model-cache miss observation

Date produced: 2026-09-04

Produced from [the raw-result template](../templates/TEMPLATE-raw-result.md).

`V1-S2-007-PR1` measured the cache **hit** path six times against a real runtime
and left its first acceptance criterion — *"cache hit/miss behaviour is documented
and measurable"* — marked **partially met**, because a real *miss* had never been
observed. Its own record put the reason plainly: a miss was believed to cost a
1.71 GiB download, and no such authorization existed.

That belief was half right. Recovering *from* a miss costs a download. Observing
one does not: `observe_cache` classifies an absent artifact with no network
connection at all, and `observe_start` refuses a measured start at a non-hit cache
**before** it creates a container. This record is that observation, executed for
real, with no byte transferred.

## Classification and certification

| Field | Value |
|---|---|
| Evidence class | `local-real-cpu` |
| Ceiling this class carries | `C2` |
| Level this record supports | `C2` for the miss classification and the refusal it triggers, and nothing wider |
| Evidence owner | serving |

**Claim boundary.** This record establishes, on one contributor host, on one day:

- that with the documented cache absent, `tools.model_lifecycle cache` classifies
  the state as `miss`, reports `0 of 1834426016` bytes, maps it to the
  `artifact-absent` lifecycle state, and exits `3`;
- that with the cache absent, `tools.model_lifecycle measure
  --confirm-real-runtime` **refuses**, names the explicit repair, exits `3`, and
  creates **no container**;
- that with the cache absent, `tools.model_acquisition check` reports
  `state absent (0 bytes present)` and the full remaining disk requirement;
- that after restoration the same artifact verifies byte-identical against its
  published SHA-256.

It establishes **nothing** about download behaviour, resumption, or recovery time.
No acquisition ran here. The real acquisition evidence is
[`V1-S2-005-PR2`](v1-s2-005-pr2-validation.md), which downloaded and hash-verified
this artifact from an absent cache.

## Provenance

| Input | Immutable identifier |
|---|---|
| Repository revision | `47478a49848f98a590016cd4bb693a5bc799277c` on `main`, the Sprint 2 head |
| Branch | `fix/sprint-2-completion-remediation` |
| Lifecycle record | [`model-lifecycle.v1.json`](../../../deploy/serving/lifecycle/model-lifecycle.v1.json) |
| Model source record | [`model-source.v1.json`](../../serving/model-source.v1.json) |
| Model artifact | `Qwen/Qwen3-1.7B-GGUF`, revision `90862c4b9d2787eaed51d12237eafdfe7c5f6077`, file `Qwen3-1.7B-Q8_0.gguf`, 1,834,426,016 bytes, `sha256:061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a` |
| Documented cache | `.cache/inferops/models`, pinned by `_assert_documented_cache`; the tool accepts no cache-root override |
| Dependencies | The committed `uv.lock`, consumed with `--locked` |

## Environment

Where this ran: `capable-host`. Windows 11, `AMD64`, Python 3.12.12, Docker 29.7.2,
20 logical CPUs and 8,158,400,512 bytes visible to the container engine, 80.00 GiB
free on the model-cache volume.

No hostname, username, absolute local path, or credential is recorded here.

### How the miss state was created, exactly

This is the part a reader must be able to check, so it is stated without
euphemism. **The artifact was not deleted and was not re-downloaded.** The
documented cache directory was renamed aside within the same ignored workspace
cache and renamed back afterwards:

```text
mv .cache/inferops/models .cache/inferops/models.aside
   ... observations ...
mv .cache/inferops/models.aside .cache/inferops/models
```

A rename within one volume moves a directory entry, not 1.71 GiB of data, so the
window was momentary and no transfer occurred. During that window the documented
cache genuinely did not exist, which is exactly the condition the miss path
describes — the tooling was not told it was a miss, it observed one.

On this particular host the artifact additionally carries a **second hard link
outside the checkout**, so the bytes were referenced twice throughout and were
never at risk. That host arrangement is described in
[the Sprint 2 completion review](sprint-2-completion-review.md); it is a property
of this machine, not of the repository, and no repository behaviour depends on it.

## Method

Run from the public repository root, in this order:

```text
uv run --locked python -m tools.model_lifecycle cache
mv .cache/inferops/models .cache/inferops/models.aside
uv run --locked python -m tools.model_lifecycle cache
uv run --locked python -m tools.model_lifecycle measure --confirm-real-runtime
uv run --locked python -m tools.model_acquisition check
mv .cache/inferops/models.aside .cache/inferops/models
uv run --locked python -m tools.model_lifecycle cache --verify
```

`docker ps -a` was sampled immediately before and immediately after the `measure`
invocation.

What would have falsified this observation: a cache state other than `miss` while
the directory was absent; a zero exit from either command; a container appearing
during the refused measurement; a network connection opened by either read-only
command; or a digest mismatch after restoration.

## Results

Verdict: **supported**. Every expectation held.

| Step | Command | Observed | Exit |
|---|---|---|---|
| Before | `model_lifecycle cache` | `hit`; `1834426016 of 1834426016`; maps to `artifact-verified` | `0` |
| Miss | `model_lifecycle cache` | `miss`; `0 of 1834426016`; maps to `artifact-absent` | `3` |
| Miss | `model_lifecycle measure --confirm-real-runtime` | `REFUSED model lifecycle: a measured start requires the pinned artifact already in the cache; acquire it explicitly first` | `3` |
| Miss | `model_acquisition check` | `state absent (0 bytes present)`; `80.00 GiB free; 1.77 GiB required` | `0` |
| After | `model_lifecycle cache --verify` | `hit`; `1834426016 of 1834426016`; `integrity verified` | `0` |

**No container was created by the refused measurement.** `docker ps -a` was empty
before the command and empty after it. The refusal happens ahead of any engine
call, which is the property worth having: a miss costs nothing rather than costing
a started container that must then be cleaned up.

**The artifact survived intact.** The post-restoration verification read all
1,834,426,016 bytes and matched the published digest. Link count was 2 before the
rename, 2 during it, and 2 after it, on both names.

### What this changes about the story's acceptance

`V1-S2-007-PR1` recorded its first criterion as met for hit and partially met for
miss. With this record the miss half is met by observation rather than by
synthetic test, and the criterion is **met**. The amended table is in
[the `V1-S2-007-PR1` record](v1-s2-007-pr1-validation.md), which now cites this
document.

## Limitations

- **One host, one day, one observation of each state.** No variance is established.
- **The miss was created by renaming, not by a fresh machine.** A cache that never
  existed and a cache renamed aside are indistinguishable to the tooling — that is
  precisely why the observation is valid — but this record does not simulate a
  first-run contributor's full experience, and does not claim to.
- **No acquisition was performed here.** The recovery path from miss to hit is
  evidenced by [`V1-S2-005-PR2`](v1-s2-005-pr2-validation.md), not by this record.
- **The `partial` cache state was not observed here.** A `.part` file was not
  created, so `artifact-partial` remains covered by synthetic tests only.
- **This record stops being true** if the documented cache path, the pinned byte
  count, or the refusal ordering in `observe_start` changes.

## Authorisation

Required: **yes** — the sequence manipulates the location of a 1.71 GiB artifact
and invokes a command guarded by `--confirm-real-runtime`.

Granted by: the host owner, on 2026-09-04, in the Sprint 2 completion review, after
being shown the exact rename-and-restore sequence, the second hard link protecting
the bytes, and the fact that no download would be performed.

Cost: none. No cloud capacity, no paid service, and no network transfer. The
`--verify` read is local disk I/O.

Review: recorded in
[the Sprint 2 completion review](sprint-2-completion-review.md).
