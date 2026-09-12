# V1-S3-003-PR2 — a Kubernetes pod restart, and what survived it

Date captured: 2026-09-12

Classification: **local real evidence**, redacted. Evidence class `local-real-cpu`,
certification ceiling `C2`. One serving runtime pod was deleted in a real
Kubernetes cluster, the Deployment controller replaced it, the replacement
mounted the same Terraform-owned claim, the artifact on that claim was the same
file, and a real completion came back. Nothing here is mock, synthetic, or
estimated.

Produced by:

```text
INFEROPS_PROVIDER=docker-desktop \
  scripts/environment/kubernetes-pod-restart.sh run \
    --values <host values file> --confirm-real-kubernetes
```

## The gap this closes

`V1-S3-003` asked whether model artifacts survive a pod restart.
[Its evidence](v1-s3-003-pr1-restart-reload.md) answered a narrower question and
said so in as many words:

> **It is not a pod restart.** No InferOps API image is published and the model
> cache claim is Terraform-owned and unwritten, so nothing has scheduled a
> replacement pod against a surviving claim.

That record stays exactly as it is. It was honest about what it measured — a
container stopped on the host and another started — and rewriting it to look like
this one would be rewriting history. What changed is that both of its stated
blockers are gone: an API image is built and loaded, and the claim is filled by
the release's own acquisition hook.

## Provenance

| Input | Immutable identifier |
|---|---|
| Repository revision | this change, on `test/v1-s3-011-lifecycle-cleanup-evidence-reconciliation` |
| Provider | `docker-desktop` (the V1 reference provider) |
| Kubernetes | server `v1.34.3`, one node, `desktop-control-plane` |
| Node image | `kindest/node@sha256:08497ee19eace7b4b5348db5c6a1591d7752b164530a36f855cb0f2bdcbadd48` — **Docker Desktop's choice, not an InferOps pin** |
| Chart | `inferops-llm-0.3.0` |
| Helm | `v3.19.0+g3d8990f` |
| kubectl | `v1.34.3` |
| Model artifact | `Qwen/Qwen3-1.7B-GGUF`, revision `90862c4b9d2787eaed51d12237eafdfe7c5f6077`, `Qwen3-1.7B-Q8_0.gguf`, `sha256:061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a`, 1 834 426 016 bytes |
| Serving runtime image | `ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384` |

## What was done

One release, installed from the real profile. One pod, deleted by name. Nothing
else was touched: the Deployment, the claim, the release revision, every
cluster-scoped object, and every other namespace were left alone, and the record
asserts each of those separately rather than leaving a reader to infer them.

```text
install -> baseline completion -> delete one pod -> replacement -> completion again -> uninstall
```

## Results

### The pod was genuinely replaced

| | before | after |
|---|---|---|
| Pod name | `…-runtime-75d47d6578-nfgxx` | `…-runtime-75d47d6578-vc7lk` |
| Pod UID | `4dca867e-0139-4d1e-a7ff-4e64273bd71e` | `e58792c0-1e9c-47d5-9927-8f4c7591faf4` |
| Owner | ReplicaSet `…-runtime-75d47d6578` | the same ReplicaSet |
| Node | `desktop-control-plane` | `desktop-control-plane` |
| Ready | yes | yes |

Different name **and** different UID. That distinction is the whole point of
this record: a container that restarted inside the same pod would show the same
UID, and that is a different experiment one layer down — the one
[Sprint 2 already ran](v1-s3-003-pr1-restart-reload.md).

The release revision was `1` before the deletion and `1` after it. Deleting a pod
is not a release change, and a revision that had moved would mean something else
had happened.

### The same claim came back, and so did the same file

| Fact | Value | Same either side |
|---|---|---|
| Claim | `inferops-model-cache`, Terraform-owned | yes |
| Claim UID | `646749a3-f0b8-40d9-949d-cc5b6e5a919e` | yes |
| Bound PersistentVolume | `pvc-646749a3-f0b8-40d9-949d-cc5b6e5a919e` | yes |
| Mount | read-only, `subPath` `Qwen--Qwen3-1.7B-GGUF/90862c4b…` | yes |
| Artifact byte count | 1 834 426 016 | yes |
| Artifact SHA-256 | `061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a` | yes |
| Artifact **inode** | `2118398` | yes |
| Artifact **mtime** | `1789203832` | yes |
| `verify-model` init container | ran, exit `0` | both pods |

The byte count and the digest were computed **inside the cluster**, by running
`sha256sum` in the serving container against the mounted artifact, before the
deletion and again after the replacement. Reading the pinned values out of the
values file and writing them into both sides would have compared a document with
itself.

**The inode and the modification time are the rows that carry the weight**, and
it is worth being explicit about why. A re-acquired artifact has the *same* byte
count and the *same* digest as the one it replaced — that is what "acquire the
pinned artifact" means, so neither of those can tell the two cases apart. What an
acquisition cannot reproduce is the file's identity: the hook writes a temporary
file beside the artifact and renames it over the top, which allocates a new inode
and stamps a new mtime. Both were unchanged, so the replacement read the file
that was already there.

### Nothing re-acquired the model

| Question | Answer |
|---|---|
| Acquisition Jobs in the namespace before the deletion | 0 |
| Acquisition Jobs after the replacement | 0 |
| Job identity changed | no |
| Artifact inode / mtime changed | no |

The structural reason: the acquisition hook is `pre-install,pre-upgrade`, and a
pod deletion is neither. The `hook-succeeded` delete policy also means a
*successful* hook removes itself the moment it succeeds, which is why the install
hook's own log is recorded as **not observed** in the record rather than asserted
on — `installLogObserved: false`. That is a deliberate weakening of one signal and
a strengthening of another: the file-identity comparison above does not depend on
a log Helm is entitled to delete.

### Readiness reset, and came back

Five samples of the serving Deployment's `readyReplicas` across the window: four
at zero, one above zero. A replacement nobody saw happen is a replacement this
record could not describe, so the sampler runs from the moment of deletion and
the first sample is taken before any wait.

### Real inference, before and after

| | before the deletion | after the replacement |
|---|---|---|
| HTTP | 200 | 200 |
| Adapter kind | `real` | `real` |
| Prompt / completion / total tokens | 24 / 29 / 53 | 24 / 29 / 53 |
| Runtime | `llama.cpp llama-server` at the pinned digest | the same |
| Model revision | `90862c4b…` | the same |
| Content | not retained | not retained |

"Succeeds again" needs a *before*, and the release's own in-cluster connection
test is not one: it asks two Services for a health endpoint, which a runtime that
loaded no weights would still answer. Both calls above are the same pair of
requests through the same loopback forward.

### Timing — one run, on one host

| | ms |
|---|---:|
| Deletion to a replacement pod existing | 2 070 |
| Deletion to the replacement ready | 14 533 |
| Deletion to a served completion | 19 952 |

**These are not a benchmark.** One pod, deleted once, on one Windows host, at one
moment, with a host file cache in whatever state the preceding run left it. They
are not a restart benchmark, a service-level objective, an availability figure, or
a number anything may be compared against. [ADR 0005](../../architecture/decisions/ADR-0005-evidence-and-measurement.md)
is why they are published as a single observation rather than as a measurement.

### Cleanup

`helm uninstall` removed every object carrying the release's instance label — 0
remaining — and the Terraform-owned namespace and claim both survived, which is
the boundary [the ownership inventory](../../architecture/resource-ownership.md)
states.

## Defects this run found

Two, both in this change's own new tooling and both invisible to a test:

1. **The bound-volume comparison compared two different things.** `boundVolumeName`
   is the handle the *pod* gives the volume in its own spec; the claim's bound
   PersistentVolume is a cluster-scoped name. Comparing one against the other
   refused a replacement that had mounted exactly the right volume. The claim is
   now read either side of the replacement and compared against itself, and the
   pod's own volume name is compared separately.
2. **The ConfigMap was read by label selector.** The release carries three
   ConfigMaps — the runtime configuration, the telemetry scrape configuration, and
   the collector's — and the first one a selector returns is the collector's,
   which carries none of the fields the record needs. It is now read by the name
   the descriptor gives it. The same defect existed in the upgrade/rollback
   experiment, which had never been run either.

## Limitations

- **One provider.** `docker-desktop`, and nothing here certifies `kind`.
- **One pod, once.** The figures describe that one replacement.
- **A deleted pod is not a lost node.** Nothing here says anything about a node
  that goes away, a claim that fails to reattach, or a volume that is corrupted.
- **One replica.** The replacement window is an outage for any caller reaching
  that Service. Nothing here measures that outage from a caller's side and
  nothing here claims high availability.
- **The claim's storage was not tested for durability.** The comparison
  establishes the bytes the replacement loaded, not that the underlying
  `rancher.io/local-path` volume survives a host failure or a Docker Desktop
  reset. What a reset reclaims is still recorded as unknown.
- **Acquisition is proven not to repeat for a pod replacement**, because the hook
  runs on install and upgrade and a deletion is neither. Nothing here says what an
  upgrade would re-acquire.

## Authorisation

Required: **yes**. The run installs into a cluster the operator owns, loads a real
model, deletes a running pod, and sends real inference requests.

Granted by: the host owner, in the session that ran it, for the `docker-desktop`
provider specifically. No workload outside the InferOps release was touched, and
Docker Desktop was never reset, disabled, or reconfigured.

Sensitive values removed before committing: host name, user account, absolute
filesystem paths, the operator's kubeconfig and its path, the API server address,
and any certificate, key, or token. The generated completion text was never
retained by the workflow and does not appear here.
