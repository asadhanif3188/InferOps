# V2-S4-001-PR2 validation

Status: **the API's readiness status answers for the API, and the adapter's answer
is reported beside it. Nothing was built into an image and nothing was installed.**
The evidence level of everything below is C0: tests drove the application in
process, committed files were read, and `helm template` ran on a workstation. No
API image was built from this change. No cluster was contacted. No request crossed
a Kubernetes Service.

| Property | Value |
|---|---|
| Date | 2026-10-08 |
| Base | `e7852bb`, the merge of pull request #126 |
| Branch | `test/v2-s4-001-api-readiness-semantics` |
| Host | One Windows workstation, Git Bash; Python 3.12 from `uv`; Helm `v3.19.0` |
| Evidence level | C0, static. No claim was added or changed |
| Decision record | [ADR 0020](../../architecture/decisions/ADR-0020-api-readiness-is-the-apis-own-answer.md) |

## What the V1 behaviour was

`GET /health/ready` answered `200` only when the API accepted work and the selected
adapter reported itself ready. It answered `503` when either was false. The chart
points the API pod's readiness probe at that path, so an API pod failed its probe
whenever the runtime was unreachable or the model was loading.

[The unready-model run](v1-s4-007-pr1-unready-model-recovery.md) recorded that
behaviour on one provider. Its record tool asserts that the API's readiness path
answered `503` at every ask in the unready window, and that the API pod's `Ready`
condition agreed. That run asked the API through a forward to the pod.

## What changed

**The API.**

- The status of `/health/ready` is `200` if, and only if, the lifecycle state is
  `serving`. It is `503` while the API is starting, draining, or stopped.
- While the API accepts work, each readiness request asks the adapter. The body
  reports the answer in a new member, `adapterStatus`: `ready`, `not-ready`, or
  `not-asked`.
- The ask has a budget. `ApiConfiguration.adapter_readiness_timeout_ms` defaults to
  3,000. An ask that does not finish is cancelled and reported as `not-ready`. No
  environment variable sets the budget.
- The readiness counter is incremented as before, once for each readiness request
  in which a component said no. Its help text changed.
- Liveness, the five routes, the error contract, and the shutdown order are not
  changed.

**Two tools.**

- `tools/llm_load` refuses a target unless the readiness answer is `200` with
  `status` and `adapterStatus` both `ready`. Its rehearsal server answers with the
  four-member body.
- `tools/local_composition` waits while the body reports `adapterStatus` as
  `not-ready`, and refuses a `200` whose body is neither that body nor the ready one.

**Records and generated files.**

- The telemetry catalog, the alert record, and the dashboard record state the new
  meaning of the readiness counter. Both rule files and the Grafana JSON were
  regenerated with the repository's own commands. The alert expression, its
  threshold, and its scenario expectations are unchanged.
- The accepted API surface record states the amended rule for `health-ready`.
- ADR 0010 gains a dated note. The decision registries hold twenty records.

**The chart.** Comments in `values.yaml` and in three templates, and the words of
one template refusal, describe the new rule. No value, no schema rule, and no
rendered object changed. The chart version stays `0.4.0`.

## Decisions taken in this change

| Decision | Why |
|---|---|
| The path `/health/ready` is kept, and its status is redefined | The endpoint with the readiness role is the one the probe asks. A second path would add a sixth endpoint to an accepted surface of five and would change the rendered chart |
| The adapter is still asked on each readiness request | The real adapter observes the runtime through that ask. Without it, an adapter that first saw a loading model would keep refusing inference after the model finished loading. A test holds the sequence |
| The body gains one member, and `status` follows the HTTP status | A `200` whose `status` says `not-ready` would contradict itself |
| The ask is bounded at 3,000 ms by default | The adapter bounds its own probe by the request budget, which the chart defaults to 120 seconds. The chart's default probe timeout is 5 seconds |
| The load generator refuses a body with no `adapterStatus` | Nothing in such a body says the adapter is ready. The cost is stated: this revision of the tool refuses an API image built before this change |
| The chart version is not raised | No value, schema rule, or rendered object changed |
| Three V1 experiment tools and the unready-model descriptor are not changed | They are the tools of recorded runs. ADR 0020 R4, R5, and R6 state what each reads against a new image |

## What the change was asked to reach, and what it reached

| Criterion of the story | State after this change |
|---|---|
| The reference API replica count is 2 | Reached by the earlier change, as configuration. Not touched here |
| The API rollout uses `maxUnavailable: 0` and `maxSurge: 1` | Reached by the earlier change, as configuration. Not touched here |
| API readiness reflects the API's ability to honor its contract, and does not mirror runtime readiness | **Reached in the application, at C0.** Not observed in a deployed release |
| The Ready endpoints of the API Service are observable | **Not reached, and not attempted.** No collector of endpoint state exists, and no endpoint was read |
| No path-level resilience claim precedes the experiment that tests it | Held. No claim was added or changed |

## Results

### At the first commit

| Check | Result |
|---|---|
| `ruff check`, `ruff format --check` | Clean: 658 files formatted, no lint finding |
| `mypy`, and `mypy --platform linux` | No type error in 357 source files, on each platform |
| `tests/api/test_api_readiness_semantics.py`, the new suite | 24 passed |
| `tests/api`, the whole directory | 402 passed |
| The load-generator suite, the two suites that use its identity probe, `tests/telemetry`, the runbook suite, the decision-authority suite, the inventory suite, and the two API surface suites | 3,564 passed, 1 failed. The failure was a placeholder in this record, which this section replaces |
| `tests/architecture/test_helm_chart.py` | 225 passed |
| `helm template`, both committed fixtures | Each render is the committed render, byte for byte, after the comment edits |
| `helm template`, real fixture, with `api.livenessPath=/health/ready` | Refused by the template, with the reworded message |
| `helm lint --strict`, real fixture | Exit 0 |
| `tools.inference_alerts`, and `--rules mock` and `--rules real` | 6 alerts satisfy the policy. Each rule file is what the record renders |
| `tools.inference_dashboard`, and `--grafana` | 29 panels satisfy the policy. The Grafana JSON is what the record renders |
| `tools.generated_release --check`, `tools.gitops_desired_state --check` | Exit 0 for each. No release was regenerated: the chart's `api` values did not change |
| `tools.experiment_freeze --check`, `tools.experiment_e01 --check` | Exit 0 for each |
| `tools.evidence_index --check` and `--gate`, `tools.proof_dashboard --check` | Exit 0 for each. The evidence pack is `06e214dc…3d0720`, as before |
| `git diff --check` | Clean |
| The default lane | Started on the working tree before the first commit, and not finished when the first commit was made. Its result is recorded with the second commit |
| `gitleaks` | Not run: it is not installed on this host. The hosted CI job runs it |
| Hosted CI | Not read: no pull request existed when this record was written |

## The first experiment's freeze

The freeze records of the first experiment pin the content of files as they were
when each record was registered. This change edits files that those records pin.

| Freeze revision | Pinned files that differ, at the base | After this change | Files this change moved |
|---|---|---|---|
| 1 | 13 | 14 | `charts/inferops-llm/templates/_helpers.tpl` |
| 2 | 13 | 14 | The same file |
| 3 | 17 | 22 | The same file, and `application.py`, `lifecycle.py`, `observability.py`, and `responses.py` under `src/inferops/api/` |

The other chart files this change edits had already moved before it. No freeze
revision was written here, and no committed freeze record was edited.
`tools.experiment_freeze --changes` exits 1 for revisions 2 and 3, as it did at the
base, and it lists each moved file. A result-bearing run of that experiment is
refused until a merged freeze revision classifies each one. The four API sources
are what an API image is built from, so a later revision must classify them as a
change to the code the experiment ran.

## Privacy and publicability

The diff was read for private material before each commit. It holds no credential,
no secret value, no personal path, no cloud account identifier, no model artifact,
and no generated machine state. The address in the controlled transport of the new
suite, `10.0.0.7:8080`, is an invented value: the suite uses it to show that a
transport's message does not reach a response.

## What this does not establish

- That a Kubernetes Service keeps an API endpoint while the runtime is unavailable.
  The rule is in the application. No kubelet asked it.
- What a caller receives through a Service while the runtime is unavailable.
- That any deployed release answers under this rule. No API image was built from
  this change, and the image a release runs is pinned by digest outside Git.
- That the 3,000 ms budget is shorter than a probe timeout in an installation. The
  comparison is between two default values.
- That two API replicas stay available when a pod is lost. Replica count and a
  readiness rule are configuration and code, and neither is an availability result.
- Anything about the runtime's own readiness, which is not changed.
