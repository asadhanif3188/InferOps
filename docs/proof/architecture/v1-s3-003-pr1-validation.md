# V1-S3-003-PR1 validation — model cache persistence

Change: the model cache mount became revision-scoped, the serving pod gained an
init container that verifies the artifact before the runtime loads it, and the
lifecycle tool gained a restart comparison. This record is what was run, what it
found, and what it does not support.

**Evidence class.** Everything asserted by a test here is `local-static`: files
read, rendered, and compared. The measured starts are `local-real-cpu` with a
`C2` ceiling, on one contributor host, on one day. **Nothing in this change has
run inside Kubernetes.** No cluster has installed the chart, the init container
has never been scheduled, and the Terraform-owned claim it mounts does not exist.

## What the change is

Three things, and each answers one of the parent story's acceptance criteria.

**The revision now decides which bytes a container can read.** The chart mounted
the claim at its root with a free-form `model.cache.subPath`, so `model.revision`
was required, compared against nothing, and had no bearing on the file the
runtime loaded. The claim is now mounted at the `<repository>/<revision>`
subdirectory the chart derives from `model.artifact.repository` and
`model.revision` — the same layout the model source record already publishes for
the workspace cache — and no values path reaches it. `model.containerPath` and
`model.cache.subPath` were removed from the values contract and are derived, so
the file the init container reads and the file the runtime is given are one
expression.

**The artifact is verified on every pod start.** An init container compares the
mounted file against the byte count and SHA-256 the model source record pins.
`model.integrity.verifyOnStart` is `sha256` by default; `size` and `none` are
explicit downgrades that keep the revision scoping — that is the mount rather
than a check — and still refuse an absent artifact.

**A restart comparison exists.** `python -m tools.model_lifecycle restart` is the
cold/warm comparison with its one variable removed: it reads nothing between the
two starts, so the only thing that changed is that a runtime stopped.

## Commands and results

### Python

```text
uv run --locked ruff check .           All checks passed!
uv run --locked ruff format --check .  280 files already formatted
uv run --locked python -m mypy         Success: no issues found in 149 source files
uv run --locked python -m pytest -q    5914 passed, 27 skipped, 14 deselected
```

The default lane went from 5,889 passing to 5,914, measured on this branch and
on `main` rather than quoted from the previous record. The two suites this change
edits:

```text
uv run --locked python -m pytest tests/architecture/test_helm_chart.py -q   127 passed
uv run --locked python -m pytest tests/serving/test_model_lifecycle.py -q    87 passed, 2 skipped
```

The chart suite went from 115 checks to 127 and the lifecycle suite from 74 to
87, both measured against `main`. The chart figure is with `helm` on `PATH`. Without it
the two render-drift comparisons skip loudly and the other 125 still run — the
arrangement `kubeconform` and `shellcheck` already have. The committed renders in
this change were produced by the same `helm` binary those comparisons re-run.

The lifecycle suite's two skips are pre-existing and unrelated to this change:
they create a symbolic link, which this host does not permit.

### Helm

`helm v3.19.0`, which is the version whose `helm template` output the committed
renders are byte for byte.

```text
helm lint charts/inferops-llm --strict --namespace inferops-platform --values ci/real-values.yaml
  1 chart(s) linted, 0 chart(s) failed
helm lint charts/inferops-llm --strict --namespace inferops-platform --values ci/mock-values.yaml
  1 chart(s) linted, 0 chart(s) failed
```

One informational finding is unresolved in both, unchanged from the previous
change: the chart sets no icon.

```text
helm template ... --values ci/real-values.yaml | kubeconform -strict -summary -kubernetes-version 1.34.0 -
  7 resources found - Valid: 7, Invalid: 0, Errors: 0, Skipped: 0
helm template ... --values ci/mock-values.yaml | kubeconform -strict -summary -kubernetes-version 1.34.0 -
  5 resources found - Valid: 5, Invalid: 0, Errors: 0, Skipped: 0
```

The object count is unchanged: an init container is a field of a pod template
rather than a resource.

### The refusals, exercised rather than asserted

Each was produced by rendering the real fixture with one value overridden. The
messages are quoted to their first clause.

| Override | Refused by | Message |
|---|---|---|
| `model.artifact.repository=` | template | *model.artifact.repository is required under the real profile* |
| `model.artifact.fileName=weights.bin` | template | *model.artifact.fileName must name a .gguf artifact* |
| `model.artifact.sizeBytes=0` | template | *model.artifact.sizeBytes is required under the real profile* |
| `model.artifact.sha256=` | template | *model.artifact.sha256 is required under the real profile* |
| `model.cache.readOnly=false` | template | *model.cache.readOnly must stay true* |
| `model.cache.mountPath=/` | **schema** | *does not match pattern* |
| `model.integrity.image.digest=` | template | *model.integrity.image.digest is required under the real profile* |

The root-directory case is refused by the schema before the template's own
refusal is reached. Both exist: the schema catches it during `helm lint` and the
template catches a form the pattern would admit.

### The one thing about the init container that was checked outside Kubernetes

The script needs two BusyBox applets. They were confirmed present in the pinned
image rather than assumed:

```text
docker run --rm --entrypoint /bin/sh docker.io/library/busybox@sha256:9db7b599...  -c
  'command -v sha256sum; command -v wc; ... | sha256sum -c ...'
  /bin/sha256sum
  /bin/wc
  -: OK
```

That establishes the applets exist and that `sha256sum -c` reports `OK` on a
matching digest. **It does not establish that the init container works**: it ran
as root with a writable root filesystem and no volume, and the pod runs it as uid
65534 with a read-only root filesystem over a mounted claim. That gap needs a
cluster.

One rendering defect was found this way and fixed. The pinned byte count reached
the template as a float and rendered as `1.834426016e+09`, which no `wc -c`
output will ever equal — a comparison that could not have failed and could not
have passed. It is now rendered through `int64`, and a test asserts the integer
form appears in the script.

## The restart comparison

It was run, and it took six attempts. Four were refused by the accepted
300,000 ms startup budget, two no-budget diagnostics measured the actual load at
305,296 ms and 338,375 ms, and the sixth ran immediately after the second
diagnostic and succeeded. The full account, the disclosure that a warm-up start
preceded the successful run, and the budget conflict this uncovered are in
[the restart record](../serving/v1-s3-003-pr1-restart-reload.md).

```text
cold     ready 154891 ms; create 8500 ms; first liveness 8829 ms; stop 1328 ms
restart  ready 129328 ms; create 4859 ms; first liveness 4984 ms; stop 1296 ms
between  cache hit; 1834426016 bytes (stat only, not read)
verify   3500 ms (SHA-256 re-read, after both starts)
delta    -25563 ms restart minus cold
accept   artifactSurvivedRestart True, readinessResetOnRestart True,
         restartNeededNoNetwork True, livenessHeldWhileLoading True,
         readinessFalseUntilReady True
```

All five properties held. **The delta establishes nothing**: the same experiment
on the same host on the same day spread from 129,328 ms to 338,375 ms, which is
an order of magnitude more than the difference between the two arms.

**A conflict was found and is reported rather than resolved.** The accepted
300,000 ms `startup.budgetMs` is below loads this host produces, and the chart's
own kubelet budget is already 600,000 ms for that reason — so the release layer
and the accepted runtime record disagree about what a plausible load is. Raising
a budget the container package pins is a change to an accepted decision and is
outside this PR's boundary. Nothing here changed it.

## Acceptance criteria

| Criterion | Status |
|---|---|
| Storage ownership and lifecycle are explicit | **Met.** [The storage document](../../environment/model-cache-storage.md) states the three roles, the five teardown operations, and the 1.71 GiB the claim holds until `terraform destroy`. The inventory rows are unchanged and now agree with an implementation |
| Cache reuse does not bypass model revision verification | **Met at the release layer.** The mount is revision-scoped and no values path reaches the scoping; the artifact is verified against its pinned hash on every pod start. Not enforced by a cluster, because no cluster has installed it |
| Pod restart behavior is measured | **Met at the container level, and not in Kubernetes.** A stop and the start that followed it were measured on real bytes, and all five properties the lifecycle record claims about a restart held. A *pod* restart is not measurable here at all: no InferOps API image is published and the claim is Terraform-owned and unwritten, so nothing can schedule a replacement pod against a surviving claim |
| Cleanup is safe and scoped | **Met.** The restart results land inside the directory the lifecycle cleanup already guards, and a test asserts both that they do and that the cleanup still cannot reach the model cache |

## Deferred, and why

- **`model-acquisition-job` stays deferred.** It is the writing half of the
  handoff and it needs a container image nobody has published plus a 1.71 GiB
  transfer from inside a cluster. It is declared in `Chart.yaml`, a test asserts
  the declaration, and the note in the runtime deployment that used to say
  `V1-S3-003` owns it now says where it actually lands.
- **The Kubernetes pod restart.** It arrives with the serving integration, which
  is when an API image, a bound claim, and a scheduled pod first exist together.
- **A NetworkPolicy, RBAC, and admission enforcement** remain `V1-S3-004`'s.

## Risks and limitations

- **A rendered manifest is a file.** Every property this record reports about the
  chart is a property of files.
- **`size` and `none` are weaker than the default.** `size` catches truncation
  and absence; a same-length substitution passes it. Both are stated choices
  rather than defaults, and both keep the revision scoping.
- **The integrity check costs a full read per pod start under the default.**
  About 1.71 GiB, measured at 3,500 ms and 4,781 ms on the reference host
  against model loads this project has measured between 129,328 ms and
  358,735 ms. On a host with
  slower storage that ratio is different, and nothing here measures a cluster.
- **The values contract changed.** `model.containerPath` and
  `model.cache.subPath` are gone and `model.artifact` and `model.integrity` are
  new. The chart has never been installed anywhere, so no release is affected,
  but a values file written against the previous contract is refused by the
  schema rather than silently accepted.
