# V1-S5-001-PR2 — the V1 journey from a clean clone

Date executed: 2026-09-18

Classification: **local real evidence.** Evidence class `local-real-cpu`, on the
`docker-desktop` provider, one Windows host, CPU only. The
[clean-clone workflow](../../environment/clean-clone.md) was run from a fresh clone
three times. The first two attempts stopped on defects of the repository; each was
fixed, and the third attempt, at the revision carrying those fixes, completed every
one of the checklist's 18 steps. Its ledger summarises as `complete` and
`certifies yes`.

The run was made by the author of this change -- an AI coding agent working on the
maintainer's workstation -- following the workflow's own page. **No second engineer
has repeated it**, and nothing here stands in for that.

## What was run

| Attempt | Revision | Clone | Outcome | Ledger |
|---|---|---|---|---|
| 1 | `ca2040c7bf878dc507c0fb6e62718c18350a9d7f` (`main`) | new, from the hosted repository | failed at `default-lane-checks` | [attempt 1](v1-s5-001-pr2-attempt-1-ledger.v1alpha1.json) |
| 2 | `4eea7d3adf43b3a49c552c36cb065374ba5dc046` | new, from the branch | failed at `helm-deployment` on two resumes, then cleaned up | [attempt 2](v1-s5-001-pr2-attempt-2-ledger.v1alpha1.json) |
| 3 | `1cb7d861a33df12c6568bd7630f57dc30397bfa5` | new, from the branch | **complete** | [attempt 3](v1-s5-001-pr2-attempt-3-ledger.v1alpha1.json) |

Each attempt was a new directory, cloned at the revision named, with no
uncommitted change and none of the state a previous run leaves -- the workflow's
`clean-checkout` step refuses anything else, and it passed on every invocation.
Attempts 2 and 3 were cloned from the working repository's branch rather than
from the hosted repository, because the branch had not been pushed; the revision
is what the ledger binds, and it is the same object either way.

The command, from Git Bash at the clone's root, on every invocation including the
resumes:

```text
INFEROPS_PROVIDER=docker-desktop INFEROPS_DISK_VOLUME=<the engine's drive> \
  scripts/environment/clean-clone.sh run \
  --confirm-downloads --confirm-real-runtime --confirm-real-kubernetes \
  --confirm-cleanup
```

with a `kubectl` `v1.34.3` first on `PATH`. The manual actions around it are in
[their own section](#manual-actions).

## Environment

| Component | Version |
|---|---|
| Windows | 11 Enterprise 10.0.26200 |
| Shell | GNU bash 5.2.26(1)-release (x86_64-pc-msys), Git Bash |
| Python, host / locked environment | 3.12.6 / 3.12.12 |
| `uv` | 0.9.16 |
| Git | 2.45.1.windows.1 |
| Container engine | Docker Desktop `29.7.2`, 12 processors, 10 432 532 480 bytes; kernel `5.15.146.1-microsoft-standard-WSL2` |
| Kubernetes | Docker Desktop's cluster: one node `desktop-control-plane`, server and kubelet `v1.34.3`, containerd `2.2.0`, node image `sha256:08497ee19eace7b4b5348db5c6a1591d7752b164530a36f855cb0f2bdcbadd48` |
| `kubectl` | `v1.34.3` |
| Helm | `v3.19.0+g3d8990f` |
| Terraform | `1.15.8` |
| Model | `Qwen/Qwen3-1.7B-GGUF` at `90862c4b9d2787eaed51d12237eafdfe7c5f6077`, `Qwen3-1.7B-Q8_0.gguf`, 1 834 426 016 bytes, `sha256:061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a` |
| Serving runtime | `ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384` |
| API image, attempt 3 | `localhost/inferops-api@sha256:7755a501391c88954522109e45155db20ba86992aab7eb0dce61de3445affb4b` |
| Model seed image, attempt 3 | `localhost/inferops-model-seed@sha256:40b2758f68b6969fb2439c4e783cb500931a446167f1e108ef115984a8e17ae1` |

Before the run the cluster held seven namespaces: the five the platform itself
provides, `inferops-serving-feasibility` -- left by an earlier InferOps story and
not touched here -- and one belonging to unrelated work, which this record counts
and does not name. All seven were there afterwards.

## The complete run

Attempt 3, as its ledger holds it. Every step that runs a workflow of its own
passed through that workflow's own guards and consent; the "records" column names
what that workflow wrote, copied here unedited.

| Step | Attempts | Elapsed of the passing attempt | Records |
|---|---:|---:|---|
| `clean-checkout` | 3 | 533 ms | asked again on every invocation |
| `host-prerequisites` | 3 | 3 395 ms | asked again on every invocation |
| `toolchain-sync` | 1 | 19 046 ms | |
| `default-lane-checks` | 1 | 1 164 115 ms | |
| `workload-scaffold` | 1 | 4 114 ms | |
| `model-acquisition` | **3** | 768 808 ms | |
| `runtime-image` | 1 | 3 554 ms | |
| `local-real-inference` | 1 | 199 867 ms | [C2 smoke result](v1-s5-001-pr2-c2-smoke.json) |
| `provider-verification` | 1 | 10 533 ms | |
| `release-images` | 1 | 394 552 ms | |
| `terraform-prerequisites` | 1 | 53 554 ms | |
| `helm-deployment` | 1 | 129 821 ms | |
| `kubernetes-inference` | 1 | 72 581 ms | [Kubernetes C2 result](v1-s5-001-pr2-k8s-real-inference.json) |
| `telemetry-verification` | 1 | 71 563 ms | [collection verification](v1-s5-001-pr2-telemetry-verification.json) |
| `load` | 1 | 976 739 ms | [performance record](v1-s5-001-pr2-performance-record.v1alpha1.json) |
| `failure` | 1 | 904 142 ms | [recovery record](v1-s5-001-pr2-recovery-record.v1alpha1.json) |
| `cleanup` | 1 | 24 468 ms | |
| `cluster-survived` | 1 | 6 418 ms | |

### Elapsed time

| Measure | Value |
|---|---:|
| Wall clock, first step's start to last step's finish (the ledger's own figure) | **5 432 293 ms** (1 h 30 min 32 s) |
| Sum of every step attempt, failed ones included | 5 191 320 ms |
| Sum of the passing attempts only | 4 818 200 ms |
| Time between steps and between the three invocations | 240 973 ms |
| Invocations of `run` | 3: the first and second stopped in `model-acquisition` |
| Across all three attempts, first attempt's first step to the complete run's last | 4 h 57 min 50 s |

Three steps are close to two thirds of the passing attempts' time:
`default-lane-checks` and the two experiments, 3 044 996 ms of 4 818 200 ms. Their
durations are this host's and vary: `default-lane-checks` took 582 295 ms in
attempt 2 and 1 164 115 ms in attempt 3, on suites that differ only by the tests
this change adds.

`model-acquisition` needed three invocations because the transfer stopped twice,
after 320 406 ms and 52 714 ms, each time with the tool's own refusal: "model
transfer stopped; the verified cache was not changed and the partial file is
available for retry." It resumes with an HTTP Range request; the third invocation
completed it and verified the SHA-256.

### What each real step established

These are the steps' own records, quoted. Each keeps its own label and its own
limitations, and nothing here raises them.

- **Local real inference** -- certified at C2: the runtime ready in 183 015 ms
  against a 300 000 ms budget, the API in 235 ms, one completion `HTTP 200` in
  3 641 ms carrying 43 tokens, real identity asserted, API drained and runtime
  removed.
- **Kubernetes inference** -- certified at C2 on `docker-desktop`: release
  `inferops` revision 1 of `inferops-llm-0.3.0` deployed and its in-cluster test
  passed; one ready replica each of the API and the runtime; the artifact hash
  compared in the cluster; the runtime ready in 10 222 ms; one completion `HTTP 200`
  in 2 500 ms carrying 43 tokens.
- **Telemetry** -- `verified`: Prometheus `3.5.0` discovered one target for each of
  the two scrape jobs and both were up; 21 of the catalogue's 23 queries were asked
  and parsed, 7 returned samples, and the 2 not asked are the ones with no source.
- **Load** -- the performance scenarios' two repetitions each dispatched 183 requests
  and each received 183 `HTTP 200`s, with no timeout, transport error, or refused
  identity; all 8 of the experiment's checks passed and it recorded itself usable.
- **Failure** -- one serving pod deleted under load: the replacement was Ready
  12 042 ms after the delete, one request was refused, the caller-visible outage was
  2 832 ms, the service was restored 33 355 ms after the delete, nobody intervened,
  and all 23 of the experiment's checks passed.

The failure experiment's figures differ a great deal from
[`V1-S4-006-PR1`'s own execution](../serving/v1-s4-006-pr1-inference-pod-recovery.md),
which recorded forty-one refused requests in a 31 960 ms outage. That record stays
the certifying one for its claim. Two executions are not a distribution, both
records say their figures are not to be compared against anything, and this
record makes no statement about why they differ.

### Cleanup

Cleanup re-verified the cluster by provider, name, and `kube-system` UID, found no
release left in `inferops-release` -- the failure experiment uninstalls its own --
destroyed the Terraform prerequisites through the guarded wrapper, waited for the
namespace to finish terminating, and removed the run's workload scaffolds. The
cluster then verified, its node was Ready, every namespace present before the run
was present, and `inferops-release` was gone.

Kept, as [the workflow's page](../../environment/clean-clone.md#cleanup-and-what-it-keeps)
says it keeps them: the images loaded into the node, the images on the host's
engine, the model in the clone's cache, and every record.

Attempt 2's own cleanup, run by hand with `cleanup --confirm` after its forward
path had failed, passed as well, and so did its `cluster-survived`. That is the
case the cleanup exists for, and it is the one executed instance of it.

## Manual actions

Recorded in the ledger with `note`, as the workflow requires. Attempt 3 carries
five notes, one of which corrects another:

1. **A previous run's release namespace was removed before the first attempt.**
   The cluster still held `inferops-release` from an earlier story's run -- the
   model cache claim, no release -- and provider verification refuses a cluster
   that holds it. It was destroyed with `terraform-prerequisites.sh destroy
   --confirm` from the working checkout that had created it. Before attempt 3, the
   namespace was absent because attempt 2's own cleanup had removed it; the fifth
   note records that correction.
2. **A `kubectl` `v1.34.3` was placed first on `PATH`**, its SHA-256 checked against
   the checksum `dl.k8s.io` publishes. The only client Docker Desktop ships on this
   host is `v1.36.1`, two minors from the server, and `inferops::resolve_target`
   refuses that skew.
3. **`INFEROPS_DISK_VOLUME` was set to the drive holding the engine's storage.** The
   engine's storage was relocated off the system drive on this host, and the
   default probe, which cannot see that, measures the system drive instead. This
   corrects what is measured; it does not lower the ADR 0001 floor.
4. **The clone itself**, noted so that the ledger says why a third attempt exists.

The provider selection is part of the documented command rather than a manual
action, and so is resuming after a failed step.

Attempt 2 carries two notes more, about the diagnosis in
[the C2 section below](#2-the-c2-certification-called-a-spent-readiness-budget-unexpected);
one of them states a hypothesis that its next attempt disproved, and the ledger
keeps it as written.

## What the first two attempts found

Five defects, each fixed in this change and each at the revision the next attempt
ran. None was a host problem.

### 1. The target-guard suite inherited the operator's provider selection

Attempt 1 failed `default-lane-checks` with one test of 11 830:
`test_no_provider_selected_refuses`. The workflow exports `INFEROPS_PROVIDER` for
every step, the suite's helper copied the whole environment into the shell it
sources `lib.sh` in, and the no-selection refusal under test became a
missing-context one. Anybody with a provider exported in their shell would have
seen it too. The helper now drops every `INFEROPS_` variable it inherits, and a new
test exports a selection to show it does not reach the refusals. The other eight
suites that copy the environment into a subprocess were run with a selection
exported: 535 passed, 2 skipped. Fixed at `4eea7d3`.

### 2. The C2 certification called a spent readiness budget "unexpected"

Attempt 2's `local-real-inference` failed twice, after 359 204 ms and 345 594 ms,
and printed only `FAILED C2 certification: unexpected local failure` -- no stage,
no reason, no diagnostics record. The runtime package raises its own error when
the runtime does not become ready, the teardown after it succeeded, and nothing
between the composition and the command caught that error, so it reached the
command's catch-all. The existing test double raised the composition's error
where the real code raises the package's, which is why no test had seen it.

`certify()` now fails at the `compose` stage and names the reason, the catch-all
names the exception it did not expect, and the new tests raise the real error.
Fixed at `1cb7d86`.

**What the failure actually was is inferred, not observed.** The runtime package's
startup budget is 300 000 ms. The two failing attempts lasted 359 204 ms and
345 594 ms; the passing ones around them lasted 259 002 ms and, in attempt 3,
199 867 ms. That is what a spent readiness budget looks like, and nothing else in
the path has a bound in that range -- but the fix that would have named the reason
was not yet in the revision that failed, and the revision that has it passed the
first time.

The measured runtime readiness on this host on 2026-09-18, all from passing runs:

| Run | Runtime readiness | Source |
|---|---:|---|
| Direct, in attempt 2's clone, after its first failure | 264 563 ms | [attempt 2's ledger](v1-s5-001-pr2-attempt-2-ledger.v1alpha1.json), manual action |
| Direct, in the working checkout, with the fix | 252 547 ms | [attempt 2's ledger](v1-s5-001-pr2-attempt-2-ledger.v1alpha1.json), manual action |
| Attempt 2, the step's third attempt (the one that passed) | 228 937 ms | [attempt 2's own C2 result](v1-s5-001-pr2-attempt-2-c2-smoke.json) |
| Attempt 3 | 183 015 ms | [the certified C2 result](v1-s5-001-pr2-c2-smoke.json) |

against the 300 000 ms budget `docs/serving/runtime-profile.local.v1.json` pins,
which [ADR 0002](../../architecture/decisions/ADR-0002-model-and-serving-runtime.md)
accepted as "roughly twenty times" a 14 s load with the weights local. On this host
the local composition reads the weights across Docker Desktop's bind mount, and
the margin is not twenty times: [`V1-S2-004`'s record](../serving/v1-s2-004-c2-certification-result.md)
already called 285 828 ms "thin". The budget is an accepted value and this change
does not move it; [the limitations](#limitations) carry it forward.

The two direct runs were diagnosis, made outside the workflow and recorded in
attempt 2's ledger as manual actions. The first one's note says it "warmed the
model into the engine's cache before this step's retry"; the retry failed anyway,
so that was wrong, and it stays in the ledger as written.

### 3. A default-lane test wrote a diagnostics record into the checkout

After attempt 2's `default-lane-checks`, the clone's evidence directory held a
`k8s-real-inference-diagnostics.json` saying `not-certified` at stage
`prerequisites`. No Kubernetes step had run. A test called the Kubernetes
certification command with its consent flag, and the refusal it tested wrote its
record into the checkout's own `.cache/inferops/certification/`, where a later,
real certification would sit beside it. The test now redirects the evidence
directory to its temporary path. Attempt 3's evidence directory held only the two
real results. Fixed at `1cb7d86`.

### 4. `helm-lifecycle.sh` decided residue on one question asked once

Attempt 2's `helm-deployment` installed, tested, upgraded, rolled back, and
uninstalled the release, then failed: three pods carrying the release label had
"survived the uninstall". Asked a moment later, none were there. `helm uninstall
--wait` waits for the objects Helm deleted itself; a Deployment's pods are removed
afterwards by the garbage collector. The seven other workflows that report residue
already ask inside a bounded retry -- `V1-S3-011-PR2` recorded the same trap -- and
this one did not. It failed the same way on the next resume. It now asks inside
the uninstall's own 600 s budget, and a new test requires every workflow that
reports residue to. Fixed at `1cb7d86`.

### 5. A clean clone reaches three sources nobody consents to

Attempt 2's `terraform-prerequisites` failed once, in 2 405 ms: `terraform init`
could not resolve `registry.terraform.io`. It passed on the next invocation. The
failure was transient, but it showed that a fresh clone downloads the Kubernetes
provider plugin, and that `--confirm-downloads` -- which names only the model and
the runtime image -- is not the whole of what a run fetches. The workflow's page
now lists the other three sources. This is a documentation fix; no consent flag was
added.

## Hidden state this run did and did not depend on

The story asks that no local uncommitted or configuration state be required.

**Not required, and checked:** an uncommitted change, a previous run's state, a
previous run's model, a hand-edited manifest, a secret, or an ambient
`KUBECONFIG`. Every clone was new; the workflow refuses the rest before it
starts; the model was downloaded into each clone's own cache and hash-verified;
the values the release used were composed by the workflow from committed files;
and every cluster command used the project-scoped kubeconfig the target guard
writes.

**Present on the host, used, and not proven unnecessary:**

- **`uv`'s package cache.** `toolchain-sync` took 19 046 ms. A host without that
  cache fetches every locked package from the index.
- **The engine's build cache.** Every layer of both image builds was `CACHED`. The
  builds reproduced the committed Dockerfiles against cached layers; a cold build
  was not made.
- **The runtime image.** `runtime-image` found it already present ("Image is up to
  date"). It pulled by digest, so the bytes are the pinned ones either way.
- **The images already loaded in the node.** Import into the node's containerd is
  idempotent, and the workflow imports them on every run.

**Observed and not investigated:** the model seed image built in attempt 2 had the
digest `sha256:975dc1b47d6908b1891e17d74dbe3bc63780fed43a406c892a500b9b1c7a5373`
and the one built in attempt 3 had `sha256:40b2758f…`, from the same Dockerfile and
the same verified model bytes. The build is not byte-reproducible across clones.
Nothing here depends on it being so, because every reference the release uses is
the digest the build just printed.

## Limitations

- **One host, one executor.** One Windows workstation, one run, by the author of
  the change. No second engineer has followed the workflow. The story asks for that
  confirmation where it is available; it was not.
- **The runtime readiness margin.** On this host the local C2 step passes or fails
  on a 300 000 ms budget it sometimes exceeds. A second run of this journey could
  stop at `local-real-inference` and need a resume. Raising the budget is a change
  to an accepted runtime profile, and is not made here.
- **The network.** The run needs the model source, the package index, the base
  image registries, and the Terraform registry. Of the five transient failures
  the three attempts met, three were the network's -- two stopped model transfers
  and one name-resolution failure -- and two were the readiness budget.
- **Caches.** See the section above: the package cache, the build cache, and the
  runtime image were present.
- **Retries inside the complete run.** The complete ledger holds three invocations,
  and `model-acquisition` needed three attempts. A reader wanting "it completed in
  one command" does not have that here.
- **Only `docker-desktop`.** This certifies the checklist on the reference provider.
  Nothing here is a statement about `kind`, and the workflow would record a
  complete run there as certifying nothing.
- **The raw inputs of the two experiment records are not republished.** Each record
  names its raw load files, resource samples, and telemetry by SHA-256. Those files
  stayed in the clone; the experiments' own certifying records are
  [`V1-S4-004-PR1`'s](../serving/v1-s4-004-pr1-validation.md) and
  [`V1-S4-006-PR1`'s](../serving/v1-s4-006-pr1-inference-pod-recovery.md).

## What this does not establish

- That any step works on a host without the caches listed above.
- Anything about `kind`, another host, another operating system, a GPU, or more
  than one replica.
- That the journey completes in one invocation, or within any stated time.
- Any performance, availability, or recovery figure. The two experiments' figures
  are this run's observations and carry their own records' boundaries.
- That a second engineer can follow it.
