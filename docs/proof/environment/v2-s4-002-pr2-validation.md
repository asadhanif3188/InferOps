# V2-S4-002-PR2 validation

Status: **one run observed two serving runtime replicas that read one verified
artifact from the one Terraform-owned claim, on the `docker-desktop` provider. The
record of that run has the result `PASSED`.** Both runtime pods ran on one node.
The run establishes nothing about the loss of that node. No chart value, rendered
byte, contract field, binding, or Terraform file was changed, and no claim was
registered. The tool was corrected after the run, and the record was built again
from the committed collection: see
[what the independent review found](#what-the-independent-review-found).

| Property | Value |
|---|---|
| Date | 2026-10-08 |
| Base | `4df31fd86363a6ee5b5b6a0023f3355f5c1bfc5f`, the merge of pull request #128 |
| Branch | `test/v2-s4-002-multi-runtime-model-cache` |
| Commits | `c04bc776`: the tool, the rules, and the static tests. `c12f3829`: the run's evidence. A third commit: the corrections of the independent review |
| Host | One Windows workstation, Git Bash; Python 3.12.12 from `uv` 0.9.16; Helm `v3.19.0`; Terraform `v1.15.8`; Docker engine `29.8.1`; `kubectl` client `v1.36.1` |
| Cluster | Docker Desktop Kubernetes, context `docker-desktop`, server `v1.36.1`, one node, default storage class `standard` |
| Evidence level | C0 for the static tests. C2 for the one run: the pinned runtime image and the pinned model ran on a real cluster |
| Claim effect | None. No claim, ledger, register row, dashboard row, or evidence-index entry was added or changed |

## What changed

- `tools/runtime_model_cache` is new. It reads one collection directory and prints
  one record. It reads files and contacts no cluster.
  [The observation page](../../environment/runtime-model-cache-observation.md)
  describes the collection, the 17 rules, the result states, and what a record
  does not establish.
- `tests/domain/test_runtime_model_cache.py` is new. It holds the tool to
  collections that the suite writes, and it builds the record of the committed run
  again from the committed collection.
- `tests/architecture/test_helm_chart.py` gained two tests on the desired-state
  render.
- The run is committed: its driver, its transcript, its collection, and its record.
- Statements that the run made stale gained a dated statement of what it observed:
  on the README, on the chart's README, in one chart template comment, in the
  comments of one contract fixture and one binding fixture, and on ten pages under
  `docs/` and `contracts/`. Five index pages gained a row or a paragraph: the
  architecture index, the system architecture, the proof index, the contributing
  guide, and the test inventory.
- `tools/runtime_model_cache` joined the list of repository checks in
  `tests/domain/test_renderer_input_boundary.py`, because it names the drift check
  and the desired-state tool.

**The chart README, one template comment, and the comments of two fixtures were
edited. Nothing that a release is derived from changed.** The chart's templates
render the committed renders, byte for byte. The contract fixture's two comment
blocks changed, and `tools.gitops_desired_state --check` still exits 0.

## Decisions taken in this change

| # | Decision | Why | What it costs |
|---|---|---|---|
| 1 | The storage boundary is reused as it is. No second claim, no `ReadWriteMany`, no per-replica cache, no chart value | The pod template already mounts the Terraform-owned claim read only and verifies the artifact in each pod. The requirement names reuse | The claim is `ReadWriteOnce`. See [the access mode](../../environment/runtime-model-cache-observation.md#the-claims-access-mode) |
| 2 | The observation is a tool and a run driver. It is not a new procedure under `scripts/environment/` | One run was needed. A later change owns endpoint collection and the experiment evidence layout | A second run needs the driver to be copied and run by hand. The driver names the `docker-desktop` context in each `kubectl` and `helm` call. The five scripts it calls verify the target themselves |
| 3 | The expected identity is read from committed files before any pod is read, and the collection stores it | A record must not compare the cluster with itself | A record states the identity of the tree it ran from. A later tree may declare another |
| 4 | The rules were committed before the run, in commit `c04bc776`. The run executed at that commit with a clean working tree | A criterion written after the observation is not a criterion | Three commits instead of two. **Eight rules were then made stricter after the run, by the review.** The record states which |
| 5 | The V1 multi-replica capacity preflight ran before the Application was applied, with its own measuring program and its own figures. No capacity gate for the V2 topology was written | It is the one accepted capacity rule for two API replicas and two runtime replicas. A test holds that its figures are this release's sums plus one small pod. Another change owns the V2 gate | The reading does not include rollout headroom or the acquisition hook's pod, and it counts a pod with no request as zero. See [the capacity reading](#the-capacity-reading) |
| 6 | Each runtime pod was sent one model listing and one completion through a port-forward to that pod | A Service cannot be asked which replica answered. The V1 multi-replica procedure states why | The two completions are not caller requests. They bypass the API and the Service |
| 7 | The mount table and the artifact's file identity were read with `kubectl exec` | The pod specification states a mode. The mount table states the option in effect, and one inode states that the two containers see one file | `kubectl exec` is not a read request. It runs `cat` and `stat` in the runtime container |
| 8 | The collection is committed, and the record is built from it | `--check` and one test build the record again. A reader can check the record against the reads. A correction of the tool can be applied to the same reads | 19 files of the collection, and the record. The pod listing holds pod addresses and container identifiers of a cluster that no longer holds them |
| 9 | No claim is registered | The contributing guide registers an executed result in a change of its own, after review | The register does not say that the model cache was observed under two replicas |

## The run

Run `run-1`, 2026-10-08. The driver printed its first time at 09:52:51Z and its
last at 10:58:27Z. The header of the collection states 09:52:59Z, the time step P1
ended.

| Item | Value |
|---|---|
| Executing commit | `c04bc77647fcfe15634012c688f39e95ba8d93ad`, with a clean working tree |
| Commit the controller reported | `4df31fd86363a6ee5b5b6a0023f3355f5c1bfc5f`, which `refs/heads/main` on the remote named. `git diff` between the two commits printed nothing for `charts`, `gitops`, and `infra/argocd`, before the run and after the apply |
| Driver | [`v2-s4-002-pr2-runtime-model-cache-run-driver.txt`](v2-s4-002-pr2-runtime-model-cache-run-driver.txt), SHA-256 `6901285ac913e4d1885e240f7264e270eb49b420e7235b9c92913afb4e6413f9`. It ran from a copy in a directory that Git ignores |
| Transcript | [`v2-s4-002-pr2-runtime-model-cache-run-1-transcript.txt`](v2-s4-002-pr2-runtime-model-cache-run-1-transcript.txt) |
| Collection and record | [`v2-s4-002-pr2-runtime-model-cache-run-1/`](v2-s4-002-pr2-runtime-model-cache-run-1/record.v1alpha1.json) |
| Tool at the run | `tools/runtime_model_cache/core.py`, SHA-256 `b194252a348a19422df5a8864638bf2cf0831d415c0e2253d721234ae8a5ea24`. The committed record is the output of a later, corrected tool |
| Values file of the release | SHA-256 `314a34829e7b44c62402249f1e93ba4493ec5b019ca7becdd1a5595025d6b6f9` |
| API image | `localhost/inferops-api@sha256:d3a3112a56e91812d0627115776c23b483f8141e15b6aab05e965fcf240f4413`, built at the executing commit. The build printed one cached step |
| Model seed image | `localhost/inferops-model-seed@sha256:fb68b706718132f8e580d92f5db88575d07b0ef0cefe0be873c4ef1023a00430` |
| Download | None by the preparation release: it read the artifact from the seed image. The Application's hook ran on a filled claim. Its log was not read |

**What the driver ran, as the transcript prints it.**

1. Five repository scripts, each of which verifies the target: the API image, the
   seed image, the prerequisite layer, the bootstrap, and the Application.
2. `helm install` and `helm uninstall`, run by the driver itself with
   `--kube-context docker-desktop`. This preparation release used the V1 real
   values file, two generated values files for the two local images, and
   `--set model.acquisition.resources.limits.memory=2Gi`. No committed values file
   states that limit. An earlier run record states why it is set on this cluster
   version.
3. The V1 capacity preflight.
4. The Application procedure's `apply`, and two bounded `kubectl rollout status`
   waits.
5. The collection, and then the removal of the Application, Argo CD, and the
   prerequisite layer.

**The preparation release loaded no model.** Its acquisition hook filled the claim.
Its runtime pod was stopped at 10:31:01Z while its `verify-model` container still
ran, and its API pod ran for 30 seconds. It is not a one-runtime comparison for
anything below.

**The `collect` invocation started before the `up` invocation ended.** The operator
started `collect` at 10:49:06Z, when both rollouts had returned and the driver was
in step D3. The `up` invocation printed its last time at 10:49:43Z. So the pod
listing, the claims, the volumes, and the events were read while step D3 was
still reading the Application. The transcript prints the phases one after the
other. Step D3 writes nothing to the cluster. The header of the collection was
written last by `collect`, at 10:50:18Z.

**`collect` ran once.** The driver was written so that `collect` could run again
after a defect. It did not need to.

**The cluster after the run.** The namespaces and the custom resource definitions
are the ones the run found: `diff` printed nothing for either. No PersistentVolume
is left. The seed-image procedure states that the two loaded images stay in the
node's image store. That was not read after the cleanup.

### The capacity reading

| Reading | Value |
|---|---|
| Engine | 12 processors, 10,430,685,184 bytes. The profile's floor is 4 and 9,126,805,504 |
| Allocatable, one schedulable node | 12,000 millicores, 10,430,685,184 bytes |
| Already requested | 950 millicores, 304,087,040 bytes |
| Uncommitted | 11,050 millicores, 10,126,598,144 bytes |
| Required by the V1 profile, with headroom | 2,810 millicores, 8,657,043,456 bytes |
| Preflight | Exit 0: `capacity      sufficient; nothing has been installed` |

The reading was taken after Argo CD was installed and before the Application was
applied. **The preflight counts requests, and a pod that states none counts as
zero.** The requests of the Argo CD pods were not read directly. After the release
was up, `kubectl describe node` reported 3,250 millicores and 4,770 MiB of
requests. That is the 950 millicores and 290 MiB of the reading plus the 2,300
millicores and 4,480 MiB of this release's three Deployments, so no other pod
stated a request. The same read reported limits of 15,100 millicores, 125 percent
of the node, and 8,070 MiB of memory, 81 percent. It was made by hand after the
collection. What any pod used was not read.

The V1 record of 2026-09 refused this provider for this shape, 172,765,184 bytes
short, with workloads of another namespace on the cluster. This reading is of
another day and another cluster state. **Neither reading is a capacity gate for
this topology.**

### What the record states

All 17 rules are `held`. The result is `PASSED`.

| Subject | Observed |
|---|---|
| Replicas | 2 serving runtime pods, `…-dk2nc` and `…-j82km`. Each reports Ready since 10:48:11Z and 0 restarts |
| Placement | Both on `desktop-control-plane`, the one node |
| Runtime image | Each pod declares, and each reports, `ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384` |
| Model argument | Each is given one `--model` argument, `/models/Qwen3-1.7B-Q8_0.gguf`, and one `--alias` argument, `qwen3-1.7b-q8_0` |
| Claim | `inferops-model-cache`: Bound, `ReadWriteOnce`, class `standard`, managed by Terraform with the `prerequisite` lifecycle, with no Helm label or annotation. It is the one claim of the namespace. Its volume is a host path with a required node affinity to `desktop-control-plane` and the reclaim policy `Delete` |
| Declared mode | `readOnly: true` on the volume, on the runtime mount, and on the verification mount, in each pod. The kubelet reports `readOnly: true` and `recursiveReadOnly: Disabled` for each runtime mount. No rule reads what the kubelet reports |
| Option in effect | The mount table of each runtime container holds one line for `/models`, with the mount options `ro,relatime`, on device `8:48`, file system `ext4`. The same line shows the file system's own option `rw` |
| Directory | The two roots are equal, compared whole by SHA-256. Each ends in `…_inferops-release_inferops-model-cache/Qwen--Qwen3-1.7B-GGUF/90862c4b9d2787eaed51d12237eafdfe7c5f6077` |
| File | Each runtime container sees device 2096, inode 1097160, and 1,834,426,016 bytes: one file, with the pinned byte count |
| Verification | In each pod `verify-model` exited 0, at 10:44:47Z and 10:44:49Z. Each script holds the three lines that compare the pinned byte count and give the pinned SHA-256 `061b54da…6590cb1a` to `sha256sum`. Each log holds `/models/Qwen3-1.7B-Q8_0.gguf: OK` and `model artifact verified: byte count and SHA-256` |
| Model listing | Each runtime answered 200 with the alias and the same metadata: 1,720,574,976 parameters, 1,828,474,880 bytes, vocabulary 151,936, type `Q8_0` |
| Completion | Each runtime answered 200 with 16 completion tokens and 15 prompt tokens, finish reason `length` |
| Not ready while it started | 31 samples for each pod. In 22 of them the runtime container was running, not started, and not ready, from the sample stamped 10:44:55Z. The first sample that shows ready is stamped 10:48:10Z. A stamp is taken before its read, so it is earlier than the 10:48:11Z the kubelet reports. The events hold 19 answers of 503 to the startup probe of each pod. **No answer to a readiness probe was collected** |

The runtime containers started at 10:44:51Z and 10:44:53Z.

### What the run showed that no rule reads

**Both API pods were restarted once by their startup probe.** These are read from
the pod events in the collection and from one read by hand.

- Each API container started at 10:43:29Z or 10:43:30Z.
- The kubelet reported `Container api failed startup probe, will be restarted` for
  both at 10:44:25Z. That is inside the interval in which the two `verify-model`
  containers read the artifact, which ended at 10:44:47Z and 10:44:49Z. Neither
  runtime container had started.
- Each API process logged `deployment.started` at 10:44:37.87Z, which is 68 seconds
  after its container started and after the kubelet's decision. The chart's API
  startup budget is 60,000 ms.
- Each first container ended at 10:44:57Z or 10:44:58Z with exit code 137. Each
  second container started at 10:45:08Z.
- The events hold 17 and 15 failed startup probes for the two pods, the last at
  10:45:30Z and 10:45:21Z, and one readiness-probe timeout and one liveness-probe
  timeout for each pod at 10:45:41Z or 10:45:42Z.
- Afterwards each pod reported `1/1 Running` with a restart count of 1. No event
  states that a probe passed.
- The collector pod had 16 failed startup probes, from 10:43:36Z to 10:44:51Z, and
  no restart.

**The cause was not measured.** No processor, memory, or disk reading was taken.
The V1 records are of one API replica beside one runtime, and this run holds no
comparison with them. The read was made by hand between the collection and the
cleanup, with read requests. It is in the transcript under its own heading, where
each command is described and not printed.

**Two control-plane pods restarted four times each during the run.** Before the
run `kube-controller-manager` and `kube-scheduler` each reported 2 restarts. After
it each reported 6, the last about 31 minutes before 10:58Z. That is about
10:27Z, before the Application was applied at 10:35:27Z. The transcript has no
other reading of them, and the cause was not read.

**What Argo CD reported.** After the apply the procedure polled the Application.
For 18 polls it printed the sync state `Unknown` and the health state `Healthy`,
with a comparison at 10:37:02Z. Then it printed `OutOfSync` and `Missing` at a
comparison of 10:41:54Z, and `Synced` and `Progressing` at 10:43:21Z. The pods of
the release were created about 8 minutes after the apply began. After both
rollouts returned, `verify` printed `Synced`, `Progressing`, and a last comparison
at 10:46:07Z, and the driver's own read printed the same two states. No later
reading was taken, so the run holds no reading of the health state `Healthy` for
the applied release.

**The import of the seed image into the node printed `elapsed: 1411.0s`.** The
transcript prints no UTC time between 09:52:51Z and 10:35:27Z. One Helm line
prints a local time. No time in this record is a measurement.

## What the driver does not hold

The driver is the file of one run, and it was not changed after the run. The
independent review read it and found these weaknesses. None of them changed what
`run-1` collected, as far as the transcript shows. A later run must not reuse the
driver without correcting them.

- `collect` does not remove the files of an earlier `collect`. If a read fails on a
  second `collect`, the earlier file stays and the tool reads it. `collect` ran
  once here.
- The read of the commit that the controller reported is printed and not checked.
  A failed read would give an empty commit in the header. Here the transcript
  prints the commit and an empty `git diff`.
- The sampler and a port-forward are not stopped if the driver is interrupted.
- The sample query joins the values of every container of a pod with no separator.
  The runtime pod has one container.
- Each request goes to `127.0.0.1`. A listener of another process on that port
  would be attributed to the pod. The transcript prints `Forwarding from` for each
  port before each request.
- The header's comment says that `up` and `down` change the cluster through the
  repository's own procedures. They also run `helm install` and `helm uninstall`
  directly.

## What the change was asked to reach, and what it reached

| Asked | Reached |
|---|---|
| Reuse the Terraform-owned claim | Reached, and observed once: the one claim of the namespace carries the prerequisite layer's labels and no release marker, and both runtime pods mount it |
| Mount read only where supported | Reached as configuration before this change. Observed once on this provider's `standard` class: the mount option in effect is `ro` in each runtime container. **No write was attempted** |
| Preserve the model SHA and revision verification | Not changed. Observed once for two pods: each pod's own init container compared the pinned digest and exited 0 before its runtime started |
| Tests that both replicas use one model identity | Reached as static tests on the render, and as rules of the record |
| On a capable environment, both become Ready | Observed once: both Ready at 10:48:11Z, and each answered one completion afterwards |
| If capacity refuses, preserve the refusal | The V1 preflight did not refuse. The driver would have ended before the apply, and the tool would have given `REFUSED`. That path is held by a test, and it was not executed |

| Parent-story criterion | State after this change |
|---|---|
| The reference runtime replica count is 2 | Declared by the earlier change. Observed once here |
| Both replicas use the same pinned real runtime and model identity | Observed once on one provider: one image digest, one file, one verification per pod, one reported model |
| The runtime rollout uses `maxUnavailable` 1 and `maxSurge` 0 | Rendered by the earlier change. The live Deployment was not read for it, and **no rollout ran** |
| The runtime's readiness stays false until real inference is possible | Partly observed. In 22 samples each runtime container was running, not started, and not ready, and the startup probe of each got 19 answers of 503. Each runtime answered a completion after it was Ready. **No readiness-probe answer was collected, and no request was sent to a runtime that was not ready** |
| The V1 model-cache ownership and integrity are preserved | Observed once: Terraform's claim, no second claim, read-only mounts, and the pinned digest verified in each pod |

## What the independent review found

Two automated reviewing sessions read the first two commits, read-only. Neither is
a person. One read the tool, the tests, and the driver, and built collections of
its own outside the repository to make the tool give a wrong answer. One compared
each statement of the change with the transcript, the collection, and the
repository. Each ran one targeted test selection. Neither ran the default lane.

### What the tool got wrong

**Each of these gave `held`, or the result `PASSED`, for evidence that did not
show it.** None was the case in `run-1`: the corrected tool gives each of the 17
rules as `held` for the committed collection, and the result is unchanged. The
collection was not edited. The record was built again, and it differs from the
record of the second commit in the members named below.

| # | The tool at the run | What is true | Corrected |
|---|---|---|---|
| 1 | `one-directory` compared the mount's root after it was cut at 240 characters. The root of `run-1` has 256 | Two roots that differ after character 240 compared equal. In `run-1` the cut copy lacks the last 16 characters of the revision | The rule compares the SHA-256 of the whole root. The two whole roots of `run-1` are equal |
| 2 | The expected identity was read from the collection and used as it was | An empty digest is in every script, and an absent member equals an absent read. A collection with such a file passed | A collection whose expected identity lacks a member, or holds one of another form, is refused. `--check` compares the expected identity of a committed run with the two pin records |
| 3 | Two entries of one pod counted as two replicas | Each comparing rule compared the pod with itself | `replica-count` is not held when names repeat, and a comparing rule needs two distinct names |
| 4 | `read-only-in-effect` read the first line of the mount table for the mount point | A later line is mounted over an earlier one | Every line for the mount point must list `ro`, and `one-directory` reads the last. `run-1` has one line |
| 5 | `one-reported-model` held when both listings held no metadata, and when the listing and the pod both held no alias | `None` equals `None` | A listing without an alias text or without metadata is not held or not observed |
| 6 | A digit that is not ASCII, a number of 5,000 digits, and JSON nested 200,000 deep ended the tool with a traceback | A file the tool cannot read as a value is a read that was not made | Each gives `not-read`, and its rule is `not-observed` |
| 7 | The verification rule looked for the digest and the byte count anywhere in the script, accepted an exit code of `false`, accepted a log with a failed checksum beside a passed one, and read 8 lines of the log | A comment that names the pins is not a comparison | The rule requires the chart's three script lines, an exit code that is the number 0, one checksum result, `OK`, for the expected path, and it reads the whole log. A chart test holds those three lines to the render |
| 8 | A preflight that ended with any status other than 0 gave `REFUSED` when no pod was read, and exit 0 was `held` without the facts file | Only exit 5 is the preflight's refusal. A crash is not a refusal | Exit 5 is not held. Another status, and exit 0 without its seven facts, are `not-observed` |
| 9 | The rule's statement said the preflight ran "before the release was applied" | The tool compares no time | The statement no longer says so, and the limits say that the order is the driver's |
| 10 | The rule was named `artifact-verified-on-each-start` | The init container runs when a pod starts, and not when a runtime container restarts. No rule reads the restart count | The rule is `artifact-verified-in-each-pod`, and the limits state it |
| 11 | The record copied the expected identity and the capacity facts whole | The page called the record an allowlisted reduction | The record holds their declared members only |
| 12 | The first of two `--model` arguments was read | A second argument was not seen | The rule requires one `--model` and one `--alias` argument |
| 13 | A sample with an empty ready value counted as not ready | An empty value is not `false` | Only `false` counts |
| 14 | Every record stated the evidence level C2 | A record that read no pod observed no runtime | Such a record states no level |
| 15 | One test of the pod-name check passed with the check removed | The path it built could not resolve | A test now builds a path that resolves without the check |

Forty-nine test cases were added to the tool's suite for these, and the suite holds
134. Each case that the review constructed, and that the tool now answers in
another way, is one of them.

### What the second commit said, and what is true

| # | The second commit said | What is true | Corrected |
|---|---|---|---|
| 1 | Nothing: the default lane was not run | `test_nothing_on_a_delivery_path_reaches_the_repository_check` failed at both commits. The tool names two repository checks and was not on their list | The list, its comment, and the boundary page, which now says six tools |
| 2 | "See the later section of this record" for the default lane | The record had no such section | [The default lane](#the-default-lane) |
| 3 | The README, the Application page, the contract examples page, one binding fixture, one test docstring, and one test comment said that no release with two replicas had been installed | The run applied one | Each place |
| 4 | "No chart file, contract, binding, or Terraform file is edited", in the CHANGELOG and in this record's status | True of the first commit only. The second edited the chart README, one template comment, and one contract fixture's comments | Both places |
| 5 | "The preparation release of this run, with one of each, restarted no API pod" | Its API pod ran for 30 seconds, and its runtime pod was stopped during verification. Its restart count was not read | Removed. The record says that it is not a comparison |
| 6 | The seed-image step "ran for about 25 minutes", from the operator's clock, and "the transcript prints no time" in that interval | The transcript prints `elapsed: 1411.0s` for the import | The section above |
| 7 | "What ran, in order" | `collect` started 37 seconds before `up` printed its last time | The section above, and the head of the transcript |
| 8 | The capacity reading was taken with "no other workload on the cluster", here and on the desired-state page | Argo CD ran. Its pods state no request | Both places |
| 9 | "Each runtime was not ready in 22 samples while it ran and answered 503" | In those samples the container was not yet started, and the 503 answers are to the startup probe. No readiness-probe answer was collected | Each place, and one more limit on the observation page |
| 10 | "At 10:44:51Z both runtimes began to load it", and "while the two runtime pods started" | The containers started at 10:44:51Z and 10:44:53Z. The kubelet's decision came during verification, before either started. A load was not observed to begin | Each place |
| 11 | "Two control-plane pods restarted during the run" | Each restarted four times, the last before the apply | The section above |
| 12 | Argo CD "reported the health state `Progressing`" | It also reported `Unknown` for 18 polls, and then `OutOfSync` and `Missing` | The section above |
| 13 | Three dated notes said the run "installed chart `0.5.0` once" | Twice: once with Helm and one runtime replica, and once through Argo CD with two | The three notes |
| 14 | "Eight pages" gained a dated statement, and "four index pages" | The counts were wrong, and they left out the test inventory | The list under "What changed" |
| 15 | A link to a section of this record about the access mode | This record has no such section | The link names the observation page |
| 16 | The observation page said that on a cluster with more nodes the second pod "may be placed where it cannot mount the claim" | That is neither observed nor attributed | The page says that it was not observed |
| 17 | The observation page said the samples "are taken every five seconds" | The driver waits five seconds between two samples. In `run-1` they were 6 to 24 seconds apart | The page |
| 18 | The observation page said a record's level is C2 "when the pods ran the pinned runtime and the pinned model" | The tool wrote C2 in every record | The tool and the page |
| 19 | The API image was "built from the build cache" | The build printed one cached step | The table above |
| 20 | The driver calls "three procedures" | Five scripts, and Helm directly | Decision 2, and the list of what the driver ran |

**Noted, and not changed.**

- **The driver.** Its weaknesses are listed above. It is the file of the run.
- **`charts/inferops-llm/templates/api-deployment.yaml` says in a comment that the
  chart has not been installed.** That was not true before this change either. It
  is not corrected here.
- **Four results of this record cannot be checked from the repository**: the test
  counts, the `mypy` and `ruff` results, the `helm template` comparison, and the
  listing of the freeze records at the base. The `ruff` file count includes files
  that Git does not track.
- **The transcript holds pod and node addresses, the node's kernel string, two
  build identifiers of the container engine, and one local time.** None is a
  credential or a path of the workstation.

## Validation at the first commit

Commit `c04bc776`. These ran on the working tree that became that commit.

| Check | Result |
|---|---|
| `ruff check`, `ruff format --check` | Clean |
| `mypy` | No type error in 361 source files |
| `tests/testing`, `tests/security`, the new suite, and the chart suite | 9,396 passed, 1 skipped, in 7 minutes 2 seconds |
| `tools.runtime_model_cache --check` | Exit 0: no committed run existed |
| `git diff --check` | Clean |
| The default lane | Not run. One of its tests failed at this commit: see above |

## Validation at the second commit

Commit `c12f3829`.

| Check | Result |
|---|---|
| `tools.runtime_model_cache --check` | Exit 0: 1 committed run |
| `tools.gitops_desired_state --check`, `tools.generated_release --check`, `tools.evidence_index --check`, `tools.experiment_freeze --check` | Exit 0 for each |
| `helm template`, the real fixture | The committed render, after the comment edit |
| `ruff`, `mypy` | Clean |
| The new suite, and the link, inventory, and two evidence suites | 2,298 passed and 1 failed. The failure was a wrong file count in the new suite's own test. After the correction the new suite and the link suite passed: 390 |
| The default lane | Not run. One of its tests failed at this commit: see above |

## The default lane

The lane ran once, on the working tree that became the third commit, with every
change staged: `uv run --locked python -m pytest -q -rs`. No file was edited while
it ran. Afterwards this section was written, and nothing else was changed.

| Result | Count |
|---|---|
| Passed | 19,365 |
| Failed | 0 |
| Skipped | 37 |
| Deselected | 14 |
| Duration | 46 minutes 21 seconds |

The test that failed at the first two commits passed. The skips are the 37 that
the earlier change's record lists by cause: fixtures that one validation layer does
not read, symbolic links that this host cannot create, one POSIX signal case, and
one freeze comparison that reports that the desired-state release changed after
revision 3 pinned it.

`ruff check`, `ruff format --check`, and `mypy` were clean on the same tree, and
`tools.runtime_model_cache --check`, `tools.gitops_desired_state --check`, and
`tools.evidence_index --check` each exited 0. The lane was not run at the first or
the second commit, and it was not run again after this section was written. The
link suite and the tool's suite were.

## The first experiment's freeze

This change edits two files that the freeze records of the first experiment pin:
the chart's `README.md` and `templates/runtime-deployment.yaml`. Both were listed
as moved at the base. `tools.experiment_freeze --check` exits 0, and no freeze
record, run, or review record was edited.

## Privacy and publicability

The diff, the transcript, and the collection were read for private material.

- The transcript is changed in two ways: terminal colour codes are removed, and
  the absolute path of the checkout, which Terraform prints twice, is written as
  `<repository>`.
- The transcript and the collection hold pod addresses, a node address, container
  identifiers, and a volume path inside the engine's virtual machine. Each names
  an object of a cluster state that the cleanup removed. None is a path of the
  workstation. The transcript also holds the node's kernel string, two build
  identifiers of the container engine, and one local time.
- No response body was kept. The two completion files hold a status, a model
  name, a finish reason, and two token counts.
- No credential, secret value, cloud account identifier, or model artifact is in
  the diff.
- `gitleaks` was not run: it is not installed on this host. The hosted CI job runs
  it. Hosted CI was not read: no pull request existed when this record was written.

## What this does not establish

- **Node-loss resilience.** Both runtime pods ran on the one node, and the claim's
  volume has a required node affinity to it. Same-node pod redundancy says nothing
  about the loss of that node.
- **That a caller is served when one runtime pod is unavailable.** No pod was
  removed. No request was sent through the API or through a Service by the
  collection.
- **Anything about a rollout.** No pod template changed.
- **That readiness is false whenever inference is impossible.** No readiness-probe
  answer was collected, and no request was sent to a runtime that was not ready.
- **That the cache cannot be written.** No write was attempted from a runtime
  container. The acquisition hook mounts the claim writable.
- **That the acquisition hook can mount the claim while two runtime pods hold it.**
  The hook ran before the Deployments existed. An upgrade was not run.
- **That two runtime pods start beside two API pods without a restart.** Both API
  pods were restarted once in this run.
- **That Argo CD reports the applied release as healthy.** The last reading was
  `Progressing`.
- **Capacity.** One reading of a V1 preflight passed on one host on one day.
- **Any performance figure.** No time in this record is a latency, a throughput,
  or a model-load measurement.
- **Another provider, storage class, or node count.** The run was on Docker
  Desktop Kubernetes with one node and the `standard` class. `kind` executed
  none of it.
- **That the collection is what the cluster held.** The record is the tool's
  output for the committed files. The driver wrote those files once.
- **A second run.** One run exists. Its result was not repeated.
