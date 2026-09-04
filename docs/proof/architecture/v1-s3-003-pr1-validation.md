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
cold/warm comparison without the read that one adds between its arms. It does not
make the interval read-free — the start procedure hash-verifies the artifact
before every start — and both the code and the record now say so.

## Commands and results

### Python

```text
uv run --locked ruff check .           All checks passed!
uv run --locked ruff format --check .  280 files already formatted
uv run --locked python -m mypy         Success: no issues found in 149 source files
uv run --locked python -m pytest -q    5918 passed, 27 skipped, 14 deselected
```

The default lane went from 5,886 passing to 5,918. The `main` figure is from a
clean worktree checked out at `main`, and it is stated that precisely because the
first attempt at it was wrong: measuring `main` by stashing left this change's
three new documents in the tree, and three suites parametrise over the published
markdown files, so the baseline came back three too high. The two suites this
change edits:

```text
uv run --locked python -m pytest tests/architecture/test_helm_chart.py -q   127 passed
uv run --locked python -m pytest tests/serving/test_model_lifecycle.py -q    91 passed, 2 skipped
```

The chart suite went from 115 checks to 127 and the lifecycle suite from 74 to
91, both measured against `main`. The chart figure is with `helm` on `PATH`. Without it
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
| `model.cache.mountPath=/` | schema | *does not match pattern* |
| `model.cache.mountPath=/models/../etc` | schema | *does not match pattern* |
| `model.cache.mountPath=/x";exit${IFS}0;#` | schema | *does not match pattern* |
| `model.integrity.image.digest=` | template | *model.integrity.image.digest is required under the real profile* |

The three `mountPath` rows are all the schema's, and the template carries no
second refusal for them. It did carry one — a `mountPath == "/"` check — and that
check could not fire, because the pattern already rejects every string it would
have caught. It was removed rather than kept as an enforcement claim nothing
enforces. The last row is the injection payload independent review constructed;
it is exercised here rather than described.

### The init container's script was executed, outside Kubernetes

Not read, and not reasoned about. The script was extracted from the committed
render and run in the pinned BusyBox image **under the container's own security
context** — `--user 65534:65534`, `--read-only`, a `tmpfs` for `/tmp`, and the
artifact directory bind-mounted read only — against four different mounts. All
four outcomes are what the pod would need them to be:

| Mounted directory | Result |
|---|---|
| The real 1,834,426,016-byte artifact | `…gguf: OK`, `model artifact verified: byte count and SHA-256`, **exit 0** |
| Empty | `REFUSED: the mounted model cache holds no artifact for the declared revision`, **exit 1** |
| A 13-byte file with the right name | `REFUSED: the mounted model artifact does not match the pinned byte count`, **exit 1** |
| A file of exactly the right length and the wrong content | `…gguf: FAILED`, `sha256sum: WARNING: 1 of 1 computed checksums did NOT match`, **exit 1** |

The last row is the one that matters most, because it is the only one a byte
count alone would have passed. A same-length substitution is refused by the
digest and by nothing else, which is why `sha256` is the default and `size` is a
stated downgrade.

**What this still does not establish** is that Kubernetes schedules it: no pod
has run, no claim has been bound, and an init container that works under
`docker run` with the same uid, the same read-only root, and the same read-only
mount is one strong indication and not a cluster.

One incidental finding came out of running it. The extracted script failed with
`set: line 1: illegal option -` until its line endings were normalised — the
extraction had written CRLF. That is a property of the extraction and not of the
chart: `helm template` emits no carriage return anywhere in its output on this
host, which was checked directly, and a YAML parser normalises line breaks in a
block scalar in any case.

One rendering defect was found this way and fixed. The pinned byte count reached
the template as a float and rendered as `1.834426016e+09`, which no `wc -c`
output will ever equal — a comparison that could not have failed and could not
have passed. It is now rendered through `int64`, and a test asserts the integer
form appears in the script.

## What independent review found, and what was done about it

Three reviewers read this change before it was finished: one on the chart, one on
the Python, one auditing the documents against the things they describe. Three
findings survived; all three were real, and all three are fixed here rather than
recorded as accepted.

**A command injection that would have disabled the whole feature.**
`model.cache.mountPath` was schema-constrained to "no whitespace", and it is
interpolated into the shell script the init container runs. A values file setting
it to `/x";exit${IFS}0;#` passed every refusal and rendered a script whose first
executed statement was `exit 0` — an integrity check that reports success without
reading anything, plus arbitrary command execution in the init container. The
pattern is now a closed character class,
`^(/[A-Za-z0-9][A-Za-z0-9._-]*)+$`, which is the same treatment
`artifact.repository`, `artifact.fileName`, `revision`, and `sha256` already had
and which `mountPath` was simply missed out of. The assignment in the script is
single-quoted as a second line. The reviewer's exact payload was re-run against
the fix and is refused by the schema.

**A claim about the measurement that was false.** The restart comparison
documented itself as reading nothing between its two starts. It does not:
`runtime_packaging.preflight` hash-verifies the artifact before every start, so a
full 1.71 GiB read precedes each arm. Worse, the test that was supposed to prove
the claim monkeypatched that read to a silent no-op, so it could not have caught
it — a test asserting the absence of something it had arranged not to see. The
claim is narrowed everywhere it appeared to what is true (*this comparison adds
no read of its own*), two consequences are now stated wherever a figure is
(no start measured here is cache-cold, and `createMs`/`readyMs` include that
read), and the test now instruments **both** read sites and asserts the whole
ordered sequence including the preflight reads.

**A refusal that could not fire, and an error that hid a corrupt file.** The
`model.cache.mountPath == "/"` refusal in `_validate.tpl` was unreachable behind
the schema pattern, so it was removed rather than left as an enforcement claim
nothing enforces. Separately, the new `results` subcommand caught every
`ModelLifecycleError` and printed "not run", which would have reported a
malformed result file or an undeclared observation as a clean empty state; an
absent result now has its own exception type and everything else refuses with its
own message.

### Three assertions were verified by breaking what they defend

A test that cannot fail is worth nothing, and two of the new ones make claims
strong enough to be worth checking that way.

| Mutation | Test | Result |
|---|---|---|
| Move the comparison's end-to-end digest read from after both starts to between them | `test_a_restart_comparison_adds_no_read_of_its_own_between_the_two_starts` | **Failed**, as it must |
| Drop the after-restart verification in `compare_restart` | `test_a_restart_comparison_reports_the_artifact_as_surviving_the_stop` | **Failed** |
| Restore the broad `except ModelLifecycleError` in the `results` subcommand | `test_the_results_command_does_not_report_a_corrupt_result_as_not_run` | **Failed** — the corrupt file was reported as `not run` |

The first of those was weaker when it was written: it counted the reads rather
than placing them, and a read moved between the starts is still one read. It was
rewritten to assert the whole ordered sequence of probes and reads — and that
rewrite is what made the preflight read visible in the first place. The mutations
were reverted and the suite re-run.

The second mutation was also, briefly, run against the wrong function: the first
attempt edited `compare_starts` rather than `compare_restart`, the test passed,
and the passing result was nearly recorded as evidence that the assertion was
weak. It is noted because a mutation applied to the wrong line looks exactly like
a test that cannot fail.

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
on the same host on the same day spread from 129,328 ms to 338,375 ms — a range
of 209,047 ms, which is 8.2 times the 25,563 ms difference between the two arms.

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
  About 1.71 GiB. The two host-side digest reads this project has timed are
  3,500 ms and 4,781 ms, and those are Python reading the file directly rather
  than BusyBox reading it across a bind mount inside a pod — the container-side
  cost is not measured. Model loads on the same host have run between 129,328 ms
  and 358,735 ms. On a host with
  slower storage that ratio is different, and nothing here measures a cluster.
- **The values contract changed.** `model.containerPath` and
  `model.cache.subPath` are gone and `model.artifact` and `model.integrity` are
  new. The chart has never been installed anywhere, so no release is affected,
  but a values file written against the previous contract is refused by the
  schema rather than silently accepted.
