# V2-S5-001-PR2 validation

Status: **RP-1 has an in-cluster runner, and a tool checks the caller record that a
run writes. This is static evidence at C0, with one rehearsal that is substituted
execution.** The runner is one file that a pod executes. It was run against scripted
answers and against a loopback server on the same host. **No run was started in a
cluster, no Job was applied, and no request was sent to a model.** No claim was
registered.

> [!IMPORTANT]
> **Nothing here is a caller's result.** The suite shows what the runner sends and
> what a record holds. It does not show that a runner pod reaches the API Service,
> and it does not show what a caller of a release saw. The script that applies the
> Job was read as text. It was not executed.

| Property | Value |
|---|---|
| Date | 2026-10-11 |
| Base | `d2b400372b63f80b36b33b25bd363da6e5916d97`, the merge of pull request #136 |
| Branch | `feat/v2-s5-001-reliability-runner` |
| Commits | The first commit: the runner file, the tool, the script, the suite, the pages, and the correction of eight stale statements. A second commit: the corrections of the independent review, and the default lane |
| Host | One Windows workstation, Git Bash (GNU bash 5.2.26); Python 3.12.12 from `uv` 0.9.16 |
| Container engine and cluster | Not used. The container engine of the host was not running, and no cluster was contacted |
| Evidence level | C0 for the suite and the checks. The rehearsal record is substituted execution: the loop of the runner ran, and each answer was scripted |
| Claim effect | None. No claim, ledger, register row, dashboard row, evidence-index entry, or experiment freeze record was added or changed |

## What changed

| Path | Change |
|---|---|
| [`tools/reliability_runner/incluster.py`](../../../tools/reliability_runner/incluster.py) | New. The one file that a runner pod executes: the plan check, the transport, the classification, the bounded closed loop, and the three kinds of record line. It imports the standard library only |
| [`tools/reliability_runner/core.py`](../../../tools/reliability_runner/core.py), `__main__.py`, `__init__.py` | New. The host tool: `plan`, `manifest`, `verify`, and `rehearse`. 16 rules |
| [`scripts/environment/reliability-runner.sh`](../../../scripts/environment/reliability-runner.sh) | New. The real path: `start`, `status`, `collect`, and `cleanup` |
| [`tests/serving/test_reliability_runner.py`](../../../tests/serving/test_reliability_runner.py) | New. 57 test functions, 170 cases |
| [`docs/serving/reliability-runner.md`](../../serving/reliability-runner.md) | New. The page of the runner |
| [`v2-s5-001-pr2-rehearsal-caller.jsonl`](v2-s5-001-pr2-rehearsal-caller.jsonl) | New. One rehearsal record |
| `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `docs/proof/README.md`, `docs/serving/llm-load-generation.md` | One paragraph or one entry each |
| `docs/serving/reliability-workload-rp-1.md`, `docs/environment/single-runtime-baseline-profile.md`, `tools/reliability_profile/core.py`, `docs/testing/test-inventory.v1alpha1.json` | Statements that this change made false. See [the stale statements](#the-stale-statements) |
| `docs/testing/test-inventory.md` and `.v1alpha1.json` | One row, and two written counts: eighty-two modules with no claim, and fifty-five modules in the documentation layer |
| `tests/architecture/test_cluster_lifecycle_safety.py`, `tests/architecture/test_local_cluster_provider_contract.py` | The new script is added to the three lists that classify each environment script |

The V1 load harness, `tools/llm_load`, is not changed. The chart, the desired state,
the RP-1 profile, and its registered digest are not changed.

## What the change was asked to reach, and what it reached

| Asked | Reached | How it is held |
|---|---|---|
| A Kubernetes Job or short-lived pod | One ConfigMap and one Job for each run, written by `manifest` | The suite reads the manifest as data. `kubeconform -strict` accepted the two objects on this host. The manifest was not applied |
| The target is the API Service DNS name | `http://inferops-inferops-llm.inferops-release.svc:8090`. The runner file refuses a URL of another form | The suite: 8 refused URLs, 25 refused plan values, and the Service name and port of the committed chart render |
| JSON lines with UTC times, request, run, and experiment identifiers, HTTP status, success, canonical error, latency, and release identity | The request line has those members, and 9 more | The suite, and 12 request lines of the committed rehearsal |
| No private prompt or response content | A line has no member that can hold either. The checker gives each line an exact member set and each text member a pattern | The suite: scripted answers hold marker texts, and no record holds one |
| A bounded duration and cleanup | A duration, a request ceiling, the active deadline of the Job, a time to live after it finishes, and `cleanup` | The suite holds the bounds with a clock that the test moves. `cleanup` was not executed |
| Deterministic test doubles | An injected transport, clock, wall clock, and sleep. `rehearse` uses the transport double | The suite |
| An opt-in real path | `scripts/environment/reliability-runner.sh`. Nothing starts it but an operator | Read as text. Not executed |
| No ingress and no gateway | The manifest holds a ConfigMap and a Job, and nothing else | The suite |
| Independence from readiness and from the delivery controller | No token, no probe, no init container, no Kubernetes API call, no readiness path, and no wait in the script | The suite: the first call of a run is the request, while the target answers nothing |

### The acceptance criteria of the story

| Criterion | State |
|---|---|
| The prompt, output, timeout, randomness, and request settings of RP-1 are versioned | Reached by `V2-S5-001-PR1`. This change reads the profile and changes no value of it |
| Concurrency is fixed at 2 | Reached by `V2-S5-001-PR1`. The plan takes the value from the profile, and no argument changes it |
| The runner targets the API Service, and not a pod or a port-forward | Reached in code, at C0. Not observed in a cluster |
| Caller results are machine-readable and public-safe | Reached in code, at C0. The one committed record is a rehearsal |
| The runner is experiment-scoped, and not a permanent serving dependency | Reached in code, at C0: the chart and the desired state do not hold it, and a run has a time to live |

## Decisions taken in this change

Each of these is a choice that the planning inputs did not fix. Each is stated on
[the runner page](../../serving/reliability-runner.md).

1. **The runner file restates the V1 transport and classification, and it does not
   import them.** `tools.llm_load.core` reads the chart and the runtime profile when
   it loads, and it imports PyYAML. A pod holds neither. The alternative was to move
   both functions out of the V1 module. Two V1 experiment tools record the digest of
   `tools/llm_load/core.py` as the file that a run executed, so that move would
   change what their records name. The suite compares the two classifications over
   729 cases, and the two transports over one loopback server.
2. **No image is built.** The runner file reaches the pod in a ConfigMap, and the
   Job uses an image that holds Python 3.12. The API image of the release is one.
   So the API image, whose digest a committed comparison input states, is not
   rebuilt for the runner.
3. **A worker waits 1,000 ms after a request that is not a success.** The profile
   states no wait. Without one, a closed loop sends without a bound on its rate
   while the target refuses connections. The wait changes how many requests a run
   sends during a failure.
4. **The runner does not stop on an outcome.** The two stop rules of the V1 harness
   are not carried. `V2-S5-001-PR1` already stated that RP-1 carries neither.
5. **A request with no answer has the status `null`.** The V1 record writes 0.
6. **The release identifier is declared.** No answer of the API states one.
7. **The outcome names are the six V1 names.** `V2-S5-001-PR1` left them open.
8. **The runner is not a pod of the release.** Its labels match no selector of the
   release. One consequence is a limit: see the network policy below.
9. **A finished Job is deleted after 3,600 seconds.** A record that is not
   collected in that time is lost.

## The negative controls

Each line is a case that the suite gives, and what must refuse it.

| Case | Count | Refused by |
|---|---:|---|
| A plan with one unusable value: a run identifier, an experiment identifier, a duration, a ceiling, a release identifier, a port, a Service name, a namespace, or a mode | 25 | `runner-identifier-unsupported` or `runner-plan-refused` |
| A base URL that is a loopback address, a pod address, `https`, another port, another DNS form, a path, or credentials | 8 | The plan check of the runner file |
| A plan with one unsupported member | 19 | The plan check of the runner file |
| An image named by a tag, by a short digest, by an upper-case digest, or by nothing | 6 | `runner-image-not-pinned` |
| A pull policy of `Always` | 1 | `runner-image-not-pinned` |
| A caller record with one defect | 46 | The rule that names the defect, over 11 of the 12 record rules |
| A text that is not lines of JSON | 7 | `caller-record-unreadable` |
| The runner file, alone, in isolated mode, with a plan it does not execute | 6 | Exit status 3, with no traceback and no output line |

The positive controls are a record of a run of the loop, which each rule accepts
before each defect is applied, and the committed rehearsal record.

## Validation at the first commit

Commands run from the repository root on the host above. `PY` is
`.venv/Scripts/python`, the interpreter of the locked environment.

| Command | Result |
|---|---|
| `PY -m ruff format --check .` | 701 files already formatted |
| `PY -m ruff check .` | All checks passed |
| `PY -m mypy` | Success: no issues found in 384 source files |
| `PY -m mypy --platform linux` | Success: no issues found in 384 source files |
| `PY -m pytest tests/serving/test_reliability_runner.py -q` | 170 passed |
| `PY -m pytest tests/security tests/serving -q` | 2394 passed, 2 skipped |
| `PY -m pytest tests/architecture/test_cluster_lifecycle_safety.py tests/architecture/test_local_cluster_provider_contract.py tests/architecture/test_argocd_bootstrap.py tests/domain/test_renderer_input_boundary.py -q` | 681 passed |
| `bash -n scripts/environment/reliability-runner.sh` | Exit status 0 |
| `PY -m tools.reliability_runner rehearse`, then `verify` of its output | Exit status 0 twice: 12 requests, two of each outcome |
| `PY -m tools.reliability_runner plan ...`, then `manifest ...`, then `kubeconform -summary -strict` of the output | 2 resources found, 2 valid. The local `kubeconform` reports its version as `development` |
| `git diff --check` | No output |

Not run: `shellcheck`, which is not installed on this host. `helm`, `terraform`, and
the infrastructure gates, because this change edits no chart, no Terraform file, and
no desired state.

## What stayed as it was

- **The V1 load harness and its profile.** Not edited.
- **The RP-1 profile and its registered digest.** Not edited. Its docstring changed,
  and the digest is of the profile file.
- **The chart, its network policy, and the desired state.** Not edited.
- **The API image.** Not rebuilt.
- **The claim register, the dashboard, the evidence index, and each ledger.** Not
  edited.
- **The experiment freeze records.** No record selects RP-1 or the runner yet.

## The stale statements

This change made eight statements false, and it corrects each:

| Where | It said | It now says |
|---|---|---|
| `README.md` | No runner reads the profile yet | A runner sends it, and no run was started in a cluster |
| The RP-1 page, status | No runner reads it yet | The runner reads it since this change |
| The RP-1 page, the prompt | The format of a result is not decided here | The runner page states the format |
| The RP-1 page, the rules | No runner exists yet | The profile tool inspects no runner, and the runner suite holds what the runner sends |
| The RP-1 page, what it does not establish | No tool sends RP-1 yet | The profile tool inspects no runner. The runner page states what the runner does |
| The baseline profile page | No runner sends it | A runner sends it since this change. The baseline tool reads neither |
| `tools/reliability_profile/core.py`, docstring | No runner reads it yet | `tools.reliability_runner` reads it to build a plan |
| The test inventory, the note of the RP-1 suite | No runner exists | The runner suite holds what the runner sends |

The `CHANGELOG.md` entry of `V2-S5-001-PR1` and its validation record keep their
words. They state what was true at that change.

## Privacy and publicability

- The diff holds no credential, no account identifier, no address of a host, and no
  path of a person's machine. `tests/security` passed.
- The prompt of RP-1 is public: `V2-S5-001-PR1` committed it. The rehearsal record
  holds no prompt and no completion, and a test holds that.
- The rehearsal record holds instants of this host's clock, to one millisecond.
  The first is the time of the rehearsal, and each later one is one millisecond
  after the one before it. It holds no host name.
- The plan and the manifest of a real run are written under `.artifacts/`, which
  version control ignores. None is committed.

## What this does not establish

- **That a runner pod runs.** No Job was applied. The image, the mount, the
  command, the security context, and the log were not observed in a cluster.
- **That the script works.** Its four actions were not executed. The suite reads
  its text: the calls it makes, the names it restates, and the order of the target
  verification.
- **That a cluster which enforces NetworkPolicy admits the runner.** The committed
  API policy admits pods of the release and a named collector. The runner is
  neither, and this change adds no allowance.
- **That a record of a long run is complete.** A rotated container log loses its
  first lines. The checker refuses such a record. It cannot recover it.
- **That the release identifier names the release that answered.** It is declared.
- **Anything about a caller, a release, a latency, or a failure.** No request was
  sent to a model.
- **Anything about capacity or ownership.** The capacity preflight does not count
  the pod of a run, and the ownership inventory has no row for the two objects.
- **A representative workload, an overload point, or a production SLO.** A run
  under RP-1 cannot support C3.
