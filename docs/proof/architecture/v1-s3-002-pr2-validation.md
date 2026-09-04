# V1-S3-002-PR2 change validation

Date: 2026-09-04

Classification: **local static**, exactly as
[`V1-S3-002-PR1`](v1-s3-002-pr1-validation.md) was. Every command below reads
files, renders templates, validates schemas, or runs a Python suite. Nothing was
applied to a cluster, no cluster was created, no image was pulled, no model byte
was read, and no release was installed, upgraded, rolled back, or uninstalled.

Claim boundary, and it is the important part of this record: **this PR adds
probes, shutdown ordering, a `helm test` hook, and a release lifecycle script,
and none of them has been executed.** A probe compared against the record that
decides what it may be is a check on a file. A lifecycle script whose safety
properties are asserted by a suite that reads it as text is a check on a file.
Nothing here may be cited as evidence that this chart installs, becomes ready,
upgrades, rolls back, or uninstalls.

## The blocker, stated once

`scripts/environment/helm-lifecycle.sh` cannot be run, and the reason is not
authorisation:

**No InferOps API image is published.** Both profiles install an API container,
no `Dockerfile` is committed anywhere in this repository, and
`platform-api-container-image` is `planned` in the ownership inventory. A release
whose API image does not resolve never becomes ready, so `helm install --wait`
fails on the image pull. That is true of the mock profile as well as the real
one — the mock replaces the serving runtime, not the API.

The real profile has two further prerequisites that also do not exist: the model
cache `PersistentVolumeClaim` is Terraform's (`V1-S3-005`) and the job that fills
it is `V1-S3-003`'s.

Separately, no local Kubernetes cluster was created for this change. `kind` is
not installed on the authoring host, and creating a cluster was neither needed
nor authorised: with no API image, an install would fail on the first pull
whether or not a cluster existed. **The acceptance criterion "install and
uninstall succeed" is therefore not met and was not attempted.** It is reported
here rather than approximated.

## Environment

| Component | Version |
|---|---|
| Operating system | Microsoft Windows 11 Enterprise, `10.0.26200` |
| GNU bash | `5.2.26(1)-release (x86_64-pc-msys)` |
| Python | `3.12.12`, through `uv run --locked` |
| Helm | `v3.21.4+g813176c` |
| kubeconform | reports `development`; the binary already on the authoring host |
| Kubernetes schema target | `1.34.0`, the version this project pins |
| Container engine | Docker `29.7.2`, running; used only to read a registry manifest |
| kind | **not installed**; no cluster was created |

Helm is still not a prerequisite of this repository. It was fetched as a portable
archive, used from a temporary directory, and never placed on the system path;
no host-wide setting was changed. `shellcheck` is not installed on this host, so
the shell script added by this change was checked with `bash -n` and by the
static suite rather than by `shellcheck`.

## Commands and results

### Python

```text
uv run --locked ruff check .           All checks passed!
uv run --locked ruff format --check .  277 files already formatted
uv run --locked python -m mypy         Success: no issues found in 149 source files
uv run --locked python -m pytest -q    5886 passed, 27 skipped, 14 deselected
```

The same suite with `helm` absent from the path, which is the state of a
contributor who has not installed it:

```text
uv run --locked python -m pytest -q    5884 passed, 29 skipped, 14 deselected
```

Two tests, and only two, change state between those runs: the drift comparison
for each profile.

The two suites this change edits:

```text
uv run --locked python -m pytest tests/architecture/test_helm_chart.py -q               115 passed
uv run --locked python -m pytest tests/architecture/test_cluster_lifecycle_safety.py -q  79 passed
uv run --locked python -m pytest tests/architecture/ -q                                 664 passed
```

The chart suite went from 77 tests to 115.

### Helm

```text
helm lint charts/inferops-llm --strict --namespace inferops-platform --values ci/real-values.yaml
  1 chart(s) linted, 0 chart(s) failed
helm lint charts/inferops-llm --strict --namespace inferops-platform --values ci/mock-values.yaml
  1 chart(s) linted, 0 chart(s) failed
```

One informational finding is unresolved in both: the chart sets no icon.

```text
helm template ... --values ci/real-values.yaml | kubeconform -strict -summary -kubernetes-version 1.34.0 -
  7 resources found - Valid: 7, Invalid: 0, Errors: 0, Skipped: 0
helm template ... --values ci/mock-values.yaml | kubeconform -strict -summary -kubernetes-version 1.34.0 -
  5 resources found - Valid: 5, Invalid: 0, Errors: 0, Skipped: 0
```

Six installed objects plus one test hook under `real`; four plus one under
`mock`. The `lifecycle.preStop.sleep` action is accepted by the `1.34.0`
schemas, which is the version the chart's own `kubeVersion` floor names.

### Shell

```text
bash -n scripts/environment/helm-lifecycle.sh   (no output; parses)
```

`shellcheck` was **not** run: it is not installed on this host. The script is
covered by `tests/architecture/test_cluster_lifecycle_safety.py`, which reads it
as text — that is not a substitute, and the gap is recorded here rather than
elsewhere.

### Diff

```text
git diff --check main...HEAD   (no output)
```

## The refusals, exercised

Nine new refusals, each provoked against real Helm from the real fixture. Every
one refused the render; the message quoted is the first line of Helm's output.

| Provocation | Refused with |
|---|---|
| `--set runtime.probes.liveness.timeoutSeconds=10` | `runtime.probes.liveness.timeoutSeconds must be less than periodSeconds` |
| `--set runtime.probes.startup.budgetMs=200000` | `runtime.probes.startup.budgetMs must be at least runtime.startupBudgetMs` |
| `--set api.lifecycle.terminationGracePeriodSeconds=10` | `api.lifecycle.terminationGracePeriodSeconds must cover the preStop pause and the drain together, which is 20 seconds for the values given` |
| `--set runtime.lifecycle.terminationGracePeriodSeconds=5` | `runtime.lifecycle.terminationGracePeriodSeconds must be greater than preStopSleepSeconds` |
| `--set telemetry.enabled=false` (with scrape annotations on) | `telemetry.scrapeAnnotations requires telemetry.enabled` |
| `--set tests.image.digest=""` | `tests.image.repository and tests.image.digest are required while tests.enabled is true` |
| `--set-string commonAnnotations.prometheus\.io/port=nine` | `commonAnnotations may not set an annotation this chart derives. Refused annotation: prometheus.io/port` |
| `--set-string api.service.annotations.prometheus\.io/scrape=false` | `a per-object annotations map may not set an annotation this chart derives` |
| `--set commonAnnotations."prometheus\.io/port"=9999` | refused earlier, by the schema: an annotation value must be a string |
| `--set runtime.lifecycle.progressDeadlineSeconds=500` | `runtime.lifecycle.progressDeadlineSeconds must exceed the startup budget, which is 600 seconds for the values given` |
| `--set api.readinessPath=/health/live` | `api.readinessPath and api.livenessPath must be different paths` |

The last two were added after this record's first draft, for the reasons in the
next section. The fourteen refusals `V1-S3-002-PR1` added were not re-exercised
individually; they are covered by the suite and by both lints continuing to
pass.

## The suite is not vacuous

Twelve rules were broken one at a time, the suite was run, and the file was
restored. Every one turned red.

| What was broken | Test that failed |
|---|---|
| A workload container loses its liveness probe | `test_every_workload_container_is_probed` |
| The runtime liveness probe becomes an HTTP GET | `test_the_runtime_liveness_probe_is_the_one_the_record_publishes` |
| The API liveness probe is pointed at the readiness path | `test_the_api_probes_ask_the_paths_the_surface_record_assigns` |
| The startup budget drops to the adapter's published figure | `test_the_runtime_startup_budget_covers_the_largest_measured_load` |
| The API grace period no longer covers the drain | `test_the_grace_period_covers_the_pause_and_the_drain` |
| A Deployment selector acquires the chart version | `test_a_selector_is_drawn_only_from_things_a_rollback_cannot_change` |
| The test hook stops deleting itself | `test_the_only_hook_is_a_test_and_it_deletes_itself` |
| The scrape annotations disappear from the real render | `test_the_scrape_annotations_follow_the_switch_that_governs_them` |
| The configuration checksum stops rolling the pods | `test_the_configuration_object_is_named_stably` |
| An install is given `--create-namespace` | `test_nothing_that_runs_passes_create_namespace` |
| The rollout deadline is pulled inside the startup budget | `test_the_rollout_deadline_is_outside_the_startup_budget` |
| The test hook picks a different BusyBox from the one `deploy/` pins | `test_the_test_hook_image_is_the_pin_this_repository_already_carries` |

The `--create-namespace` row is worth reading twice. The first version of that
rule required `helm` and the flag on the same physical line, and a shell
continuation puts the flag on a line of its own — which is how a real one would
be written. The non-vacuity check caught it: the mutation stayed green. The rule
now reads any non-comment line, and the shape that got through is a committed
sample.

## What independent review found, and what it changed

Two independent reviews ran against the first commit before anything was pushed:
one general and one security-focused. **Neither found a `CRITICAL`.** The
security review found no `HIGH` either, and confirmed what it was asked to break:
no path in the new script can reach a cluster this project does not own — every
`helm` and `kubectl` call is pinned to the project kubeconfig and context, and
the identity guard runs before any mutating call — no secret, credential, or
personal path appears anywhere in the diff, and all six hardening properties are
present on both Deployments and the new hook pod.

Four things changed as a result, and one of them was my own repair of the first.

**`HIGH` — the residue assertions could pass on a question nobody answered.**
`kubectl get ... 2>/dev/null | wc -l || true` returns `0` when the query
*succeeds and finds nothing* and also when it *fails*. So a namespace whose API
server refused the query would have been reported as a clean removal. The
queries now go through a function that separates the two, and every caller stops
rather than continuing on an unanswered question.

**And the first fix for it had the same defect one level deeper.** Written as
`count="$(count_lines "$(release_objects pvc)")"`, a failing *inner* command
substitution never reaches the assignment's exit status, so the diagnostic
printed and the script carried on. Demonstrated both shapes in a scratch script —
the nested one reports `result=[0] script continued`, the unnested one aborts —
and the callers are now unnested, with a comment saying why the shape matters.

**`MEDIUM` — the API's two health paths were two free-form strings.** The values
file says liveness and readiness are "never pointed at the other's path", and
nothing refused it: `--set api.readinessPath=/health/live` rendered cleanly with
all three probes on one path, which is the runtime's defect written into the
other workload. A refusal now exists and is exercised above.

**`MEDIUM` — the busybox claim in this record was false**, and is corrected in
[Diff hygiene](#diff-hygiene) below. Both reviews found it independently.

**`LOW`s, all acted on:** the measured-range figure was mislabelled (`215,672 ms`
is the cold arm's maximum across three comparisons, not the six-start maximum,
which is `215,906 ms`) and the `V1-S2-005` figures cite the first-attempt record
rather than the recorded run, which loaded in `269,079 ms`; the chart README did
not name the test image; the word "inert" overstated the scrape annotations,
which are the legacy Prometheus auto-discovery keys and would be read by any
collector using that convention; the namespace-prefix check in the script guards
a constant rather than operator input and now says so; and
`_dig(...) or {}` returned the `ABSENT` sentinel rather than an empty mapping,
which would have produced a stack trace instead of an assertion — every such use
now goes through `_mapping`.

**One finding was deliberately not acted on.** The security review noted that
`docs/security/security-baseline.v1alpha1.json`'s `pin-image-by-digest` control
names a verification symbol scoped to `deploy/`, so the chart's images are pinned
and checked by a different suite than the one the control cites. That is the same
`deploy/`-versus-`charts/` seam `V1-S3-002-PR1` recorded as a limitation and
assigned to `V1-S3-004`; editing an accepted security record is outside this PR's
boundary, so it is reported here instead.

**One defect was found without review, and is the reason to state the reviews did
not find everything.** `progressDeadlineSeconds` defaults to 600 seconds — the
same number as the runtime's startup budget — and the two are different clocks.
The kubelet can still be patiently waiting for a container the Deployment
controller has already marked `ProgressDeadlineExceeded`, so an `install --wait`
would report a failure that is a slow model load. Both Deployments now set it
explicitly and the chart refuses a value inside the startup budget.

None of these fixes changes a rendered manifest except the two
`progressDeadlineSeconds` lines: regenerating both renders after the review fixes
produces a diff of exactly those three lines against the first commit, which is
the check that the new guards refuse bad input rather than altering good output.

## What was found while writing this, and not changed

**The published adapter startup budget is smaller than two measured model
loads.** `docs/serving/runtime-profile.local.v1.json` publishes
`timeouts.startupBudgetMs` as `300000`. The
[`V1-S2-005` first attempt](../serving/v1-s2-005-baseline-raw-results-first-attempt.md)
recorded `358,735 ms` cold and `284,406 ms` warm on the reference host, and the
first of those exceeds the published budget. That record already says so — it
marks `T4` as failed cold and met warm — and
[the runtime troubleshooting document](../../serving/local-runtime-troubleshooting.md)
already publishes the comparison. What is new here is only that a Kubernetes
probe budget now has to be chosen against it.

This is a pre-existing inconsistency in an accepted record and **it was not
changed here**: changing an accepted contract is outside this PR's boundary. It
is reported instead, and the chart is built so that it cannot inherit the
problem — the Kubernetes startup budget is a separate value defaulting to
`600000 ms`, the chart refuses a value below the adapter's, and a test refuses a
default below the largest load this project has measured. Whether the adapter's
own budget should be raised belongs with `V1-S3-006`, which is the story that
would observe it.

## Evidence label

**Local static, and unexecuted.** The renders are real Helm output. The refusals
were really provoked. The suite really runs. None of that is runtime evidence:
no pod was scheduled, no probe was ever asked a question by a kubelet, no
`SIGTERM` was ever sent, and the lifecycle script has never run.

The `a-helm-release-installs-and-uninstalls-without-residue` claim remains a
recorded coverage gap, with its reason updated to say that a procedure now
exists and cannot be run.

## Diff hygiene

The public diff was read in full. It contains no credential, no personal
filesystem path, no private planning content, and no generated artifact.

It adds **no new external dependency.** The `helm test` hook needs an HTTP
client and uses BusyBox, and the digest it names —
`sha256:9db7b59979c38555a39def84a31fb98b5296952f9e3afd4f6f11f05b07adfab0` — is the
same `busybox:1.37.0` index digest four committed manifests under `deploy/`
already pin. An earlier draft of this record called it a new external reference;
that was wrong, and the correction produced a check rather than only a
retraction: a test now compares the chart's copy against the ones under
`deploy/` and fails if they diverge. The image has never been pulled into a
cluster by anything here.

Two pre-existing findings, in files this change does not touch, are unchanged:
trailing whitespace in `v1-s1-002-pr1-cumulative-review-fixes.md`, and a
link-check false positive in `docs/proof/README.md`.

## Limitations

- **Nothing was installed.** Restated because it is the whole of what this record
  does not establish.
- **No cluster was created.** `kind` is not installed here, and with no API image
  a cluster would not have changed any outcome.
- **`shellcheck` did not run.** Not installed on this host.
- **The probe timings are budgets, not observations.** They are derived from
  model-load measurements taken outside Kubernetes, on one host, on one day. No
  probe in this chart has ever been evaluated by a kubelet, and the numbers say
  nothing about serving performance or capacity.
- **The `helm test` hook has never run,** so nothing establishes that BusyBox's
  `wget` behaves as the template assumes under a read-only root filesystem and a
  non-root uid.
- **The `helm test` hook's container behaviour was checked outside Kubernetes.**
  Two BusyBox containers on a local Docker network, the client run with uid
  65534, a read-only root filesystem, and all capabilities dropped: `wget -q -T
  10 -O -` printed the body and exited `0` against a served path, and printed
  `server returned error: HTTP/1.1 404 Not Found` and exited `1` against a
  missing one. That is `local real` container evidence about BusyBox, and it is
  **not** evidence about a Kubernetes pod, a Service, or this chart.
- **The security baseline's `pin-image-by-digest` control does not cite the suite
  that checks this chart's images.** Reported above; not changed here.
- **Upgrade and rollback *safety* is not addressed.** The script establishes that
  a rollback is mechanically possible. What an upgrade does under load, and what
  it costs, is `V1-S3-008`'s.

## Acceptance criteria

| Criterion | Status |
|---|---|
| Helm lint/render/schema checks pass | **Met** |
| Chart configures API, runtime, model, resources, ownership, telemetry, and security | **Met**, and now also probes, shutdown ordering, and a release test |
| Real evidence values cannot silently select mock | **Met**, unchanged from `PR1` and re-checked |
| No manual manifest editing is required | **Met for what this chart renders.** The release still needs prerequisites nothing here creates |
| Install and uninstall succeed | **Not met, not attempted.** No InferOps API image is published; see the blocker above |

`V1-S3-002` is **not** complete. Its chart-lifecycle evidence does not exist, and
this record is not it.
