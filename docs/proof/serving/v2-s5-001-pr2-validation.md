# V2-S5-001-PR2 validation

Status: **RP-1 has an in-cluster runner, and a tool checks the caller record that a
run writes. No run was started in a cluster, no Job was created, and no request was
sent to a model.** The runner is one file that a pod executes. Its loop, its
classification, and its transport were executed against scripted answers and against
a loopback server on the same host: substituted execution, C1. The manifest, the
script, and the pages were read: C0. No claim was registered. Two independent
reviews read the first commit. They found that a worker failure could end a run with
exit status 0, that an early `collect` blocked each later one, that the checker
accepted lines the runner cannot write, and that several sentences said more than
the repository shows: see
[what the independent reviews found](#what-the-independent-reviews-found).

> [!IMPORTANT]
> **Nothing here is a caller's result.** The suite shows what the runner sends and
> what a record holds, with the API and the model replaced. It does not show that a
> runner pod reaches the API Service, and it does not show what a caller of a
> release saw. The script that creates the Job was not executed against a cluster.

| Property | Value |
|---|---|
| Date | 2026-10-11 |
| Base | `d2b400372b63f80b36b33b25bd363da6e5916d97`, the merge of pull request #136 |
| Branch | `feat/v2-s5-001-reliability-runner` |
| Commits | `80d83530`: the runner file, the tool, the script, the suite, the pages, and the correction of eight stale statements. A second commit: the corrections of the two independent reviews, and the default lane |
| Host | One Windows workstation, Git Bash (GNU bash 5.2.26); Python 3.12.12 from `uv` 0.9.16 |
| Container engine and cluster | Not used. The container engine of the host was not running, and no cluster was contacted |
| Evidence level | C1, substituted execution, for the loop, the classification, and the transport of the runner file, and for the committed rehearsal record: the API and the model were replaced. C0 for the manifest, the script, and the pages |
| Claim effect | None. No claim, ledger, register row, dashboard row, evidence-index entry, or experiment freeze record was added or changed |

## What changed

| Path | Change |
|---|---|
| [`tools/reliability_runner/incluster.py`](../../../tools/reliability_runner/incluster.py) | New. The one file that a runner pod executes: the plan check, the transport, the classification, the bounded closed loop, and the three kinds of record line. It imports the standard library only |
| [`tools/reliability_runner/core.py`](../../../tools/reliability_runner/core.py), `__main__.py`, `__init__.py` | New. The host tool: `plan`, `manifest`, `verify`, and `rehearse`. 16 rules |
| [`scripts/environment/reliability-runner.sh`](../../../scripts/environment/reliability-runner.sh) | New. The real path: `start`, `status`, `collect`, and `cleanup` |
| [`tests/serving/test_reliability_runner.py`](../../../tests/serving/test_reliability_runner.py) | New. 62 test functions, 185 cases, at the second commit |
| [`docs/serving/reliability-runner.md`](../../serving/reliability-runner.md) | New. The page of the runner |
| [`v2-s5-001-pr2-rehearsal-caller.jsonl`](v2-s5-001-pr2-rehearsal-caller.jsonl) | New. One rehearsal record. The second commit replaced it, because the runner file changed |
| `README.md`, `CHANGELOG.md`, `CONTRIBUTING.md`, `docs/proof/README.md`, `docs/serving/llm-load-generation.md` | One paragraph or one entry each |
| `docs/serving/reliability-workload-rp-1.md`, `docs/environment/single-runtime-baseline-profile.md`, `tools/reliability_profile/core.py`, `docs/testing/test-inventory.v1alpha1.json`, `docs/architecture/resource-ownership.md` | Statements that this change made false. See [the stale statements](#the-stale-statements) |
| `docs/testing/test-inventory.md` and `.v1alpha1.json` | One row, and two written counts: eighty-two modules with no claim, and fifty-five modules in the documentation layer |
| `tests/architecture/test_cluster_lifecycle_safety.py`, `tests/architecture/test_local_cluster_provider_contract.py` | The new script is added to the three lists that classify each environment script |

The V1 load harness, `tools/llm_load`, is not changed. The chart, the desired state,
the RP-1 profile, and its registered digest are not changed.

## What the change was asked to reach, and what it reached

| Asked | Reached | How it is held |
|---|---|---|
| A Kubernetes Job or short-lived pod | One ConfigMap and one Job for each run, written by `manifest` | The suite reads the manifest as data. `kubeconform -strict` accepted the two objects on this host. The manifest was not sent to a cluster |
| The target is the API Service DNS name | `http://inferops-inferops-llm.inferops-release.svc:8090`. The command has no option for the target, the runner file refuses a URL of another form, and the manifest builder and the record checker refuse another Service | The suite: 8 refused URLs, 25 refused plan values, one Job and one header of another Service, and the Service name and port of the committed chart render |
| JSON lines with UTC times, request, run, and experiment identifiers, HTTP status, success, canonical error, latency, and release identity | The request line has those members, and 9 more | The suite, and 12 request lines of the committed rehearsal |
| No private prompt or response content | A line has no member for either. A text member holds a registered value, a pattern, or at most 64 characters of `[a-z0-9._-]` | The suite: scripted answers hold marker texts, and no record holds one. No rule searches a record for a prompt |
| A bounded duration and cleanup | A duration, a request ceiling, the active deadline of the Job, a time to live after it finishes, and `cleanup` | The suite holds the two bounds of the loop with a clock that the test moves, and reads the two bounds of the Job from the manifest. `cleanup` was not executed |
| Deterministic test doubles | An injected transport, clock, wall clock, and sleep. `rehearse` replaces the transport, the wall clock, and the sleep | The suite |
| An opt-in real path | `scripts/environment/reliability-runner.sh`. Nothing starts it but an operator | Read as text. Not executed against a cluster |
| No ingress and no gateway | The manifest holds a ConfigMap and a Job, and nothing else | The suite |
| Independence from readiness and from the delivery controller | No token, no probe, no init container, no Kubernetes API call, no readiness path, and no wait in the script | The suite: the first call of a run is the request, while the target answers nothing |

### The criteria of the parent change

| Criterion | State |
|---|---|
| The prompt, output, timeout, randomness, and request settings of RP-1 are versioned | Reached by `V2-S5-001-PR1`. This change reads the profile and changes no value of it |
| Concurrency is fixed at 2 | Reached by `V2-S5-001-PR1`. The plan takes the value from the profile, and the command has no option for it |
| The runner targets the API Service, and not a pod or a port-forward | Reached in code. Not observed in a cluster |
| Caller results are machine-readable and public-safe | Reached in code. The one committed record is a rehearsal |
| The runner is experiment-scoped, and not a permanent serving dependency | Reached in code: the chart and the desired state do not hold it, and the Job of a run has a time to live |

## Decisions taken in this change

Each of these is a choice that this change made. Each is stated on
[the runner page](../../serving/reliability-runner.md).

1. **The runner file restates the V1 transport and classification, and it does not
   import them.** `tools.llm_load.core` reads the chart and the runtime profile when
   it loads, and it imports PyYAML. A pod holds neither. The alternative was to move
   both functions out of the V1 module. Two V1 experiment tools record the digest of
   `tools/llm_load/core.py` as the file that a run executed, so that move would
   change what their records name. The suite compares the two classifications over
   254 cases, each with the usage rule on and off, and the two transports over five
   paths of one loopback server.
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
   committed real render. One consequence is a limit: see the network policy below.
9. **The Job of a run has a time to live of 3,600 seconds after it finishes.** A
   record that is not collected in that time is lost.
10. **The target is not an option.** Since the second commit the command has no
    option for the Service name, the namespace, or the port.

## The negative controls

Each line is a case that the suite gives, and what must refuse it. The counts are of
the second commit.

| Case | Count | Refused by |
|---|---:|---|
| A plan with one unusable value: a run identifier, an experiment identifier, a duration, a ceiling, a release identifier, a port, a Service name, a namespace, or a mode | 25 | `runner-identifier-unsupported` or `runner-plan-refused` |
| A base URL that is a loopback address, a pod address, `https`, another port, another DNS form, a path, or credentials | 8 | The plan check of the runner file |
| A plan with one unsupported member | 19 | The plan check of the runner file |
| A Job of a plan with another Service, and a Job of a rehearsal plan | 2 | `runner-plan-refused` |
| An image named by a tag, by a short digest, by an upper-case digest, or by nothing | 6 | `runner-image-not-pinned` |
| A pull policy of `Always` | 1 | `runner-image-not-pinned` |
| A caller record with one defect | 55 | The rule that names the defect, over 11 of the 12 record rules |
| A text that is not lines of JSON | 7 | `caller-record-unreadable` |
| The runner file, alone, in isolated mode, with a plan it does not execute | 4 | Exit status 3, `REFUSED` on standard error, no traceback, and no output line |
| The runner file with no argument, and with an absent plan file | 2 | Exit status 3 |

The positive controls are a record of a run of the loop, which each rule accepts
before each defect is applied, and the committed rehearsal record.

## Validation at the first commit

Commands run from the repository root on the host above. `PY` is
`.venv/Scripts/python`, the interpreter of the locked environment.

| Command | Result |
|---|---|
| `PY -m ruff format --check .` | Passed. The first commit of this record wrote 701 files, which was the count before the last two pages were added |
| `PY -m ruff check .` | All checks passed |
| `PY -m mypy` and `PY -m mypy --platform linux` | Success: no issues found in 384 source files, twice |
| `PY -m pytest tests/serving/test_reliability_runner.py -q` | 170 passed |
| `PY -m pytest tests/architecture/test_cluster_lifecycle_safety.py tests/architecture/test_local_cluster_provider_contract.py tests/architecture/test_argocd_bootstrap.py tests/domain/test_renderer_input_boundary.py -q` | 681 passed |
| `bash -n scripts/environment/reliability-runner.sh` | Exit status 0 |
| `git diff --check` | No output |

The first commit of this record also wrote "2394 passed, 2 skipped" for
`tests/security tests/serving`. That run was made before the last page was added,
and the link suite has one case for each tracked page. The figure of the second
commit is below.

## What the independent reviews found

Two reviews read the first commit, `80d83530`. One read the code and ran it. One
read each statement against the code. Neither changed a file. The first found no
defect that it graded critical or high. It found four that it graded medium by
running the code, and one more by reading it. The second
found five statements or numbers that were false, and ten that said more than the
repository shows.

### What the code got wrong

| Finding | Correction |
|---|---|
| **A worker that failed could end a run with exit status 0.** The worker's failure asked for the state `interrupted`. When the other worker had already reached the ceiling, the state stayed `request-ceiling`, with one request line fewer than requests. The Job would then count as succeeded. The traceback also went to standard error, which a pod log holds | A fourth end state, `failed`, and exit status 4. The failure decides the state whatever the other worker reached. The message of the failure is not written. One test |
| **A `collect` before the end of a run blocked each later `collect`.** The log was written as `caller.jsonl`, the tool refused it, and the next `collect` refused because the file existed | The log is kept as `caller.jsonl` only when each rule accepts it. A refused log is kept as `caller.refused.jsonl`, and a later `collect` writes over that file |
| **The checker accepted lines that the runner cannot write**: a `timeout` with an answer inside the deadline, an error or a timeout that names another adapter, an error after the deadline, a transport error that names an adapter, an end at a ceiling or a duration that the counts did not reach, a run that ends before it starts, and a latency of thousands of digits | Each is refused. Nine defects were added to the table of the suite |
| **The target was a default and not a fixed value.** The command took a Service name, a namespace, and a port. A plan for the Service `kubernetes` in the namespace `default` gave a Job in that namespace, and the checker accepted a header of any Service | The command has no option for the target. The manifest builder and the checker refuse a target that is not the registered one |
| **`start` used `apply`, and the time to live of a Job does not delete the ConfigMap.** A later `start` under one run identifier could then create a Job that mounts an earlier plan | `start` reads whether an object of the name exists and refuses, and it uses `create` |
| The two environment variables of the Job did nothing, because `-I` makes the interpreter ignore them | Removed. The command is `python -I -u -B` |
| The wait of one second was eleven steps of a tenth, by a sum of fractions. No review found this. A new test of the correction above did | Ten whole steps |
| `start` had no check that `python` is on the path, and its message called each failure of the tool a refusal | Both corrected. The message after a failed creation says that the run identifier is spent |
| `cleanup` deleted the pod, and its log, with no warning when no accepted record was kept | It warns |

### What the suite got wrong

| Finding | Correction |
|---|---|
| **"729 cases" counted repetitions.** 486 of them had no answer, and the classification reads no status and no body of those. They were two cases | 252 answer cases and the two cases with no answer: 254. Each runs with the usage rule on and off, which the first commit did not vary. One body with an extension and with details was added |
| Two loop tests depended on the order in which threads ran. The reviewer made each fail by shortening the switch interval of the interpreter | The stop test holds a bound that is true in each order. The length of the wait is held on the wait function |
| The test of the script's reads of a status looked at the text before the `status` action only | It holds the whole script outside that action |
| The test of the two signal handlers holds that they are registered. It delivers no signal | The pages say so. No test was added |

### What the first commit said, and what is true

| The first commit said | What is true |
|---|---|
| "This is static evidence at C0, with one rehearsal that is substituted execution", in each file that states a level and in its commit message | The suite executes the loop, the classification, and the transport with the API and the model replaced. That is C1 by [the evidence levels](../../testing/evidence-levels.md). The label was too low, and it is corrected in each file. The commit message keeps its words |
| The checker refuses "a header that does not target the API Service" | It refused a header whose URL was not built from its own members. It now refuses another Service |
| "The clocks are real", of the rehearsal | The wall clock and the wait are replaced. In the first committed sample one worker sent each of the 12 requests. The rehearsal now makes the first two answers wait for each other |
| "701 files already formatted", and "2394 passed, 2 skipped" | Both were read before the last pages were added |
| Six cases of the runner file alone, each with three checks | Four cases have the three checks. Two have the exit status only |
| "A line has no member that can hold a prompt or a completion" | A token member accepts 64 characters of `[a-z0-9._-]`. The pages now state that bound |
| "No argument changes one", of the request values | True of the command. The function takes a profile, for the suite |
| "Each command stops at the first refusal, and the message starts with the rule" | The message starts with `REFUSED` |
| Request lines are "in the order in which the requests finished" | In the order in which the lines were written |
| The record is "standard output" | A pod log also holds standard error. The page states what then happens |
| Several statements of what Kubernetes does, written as fact | Each now says that Kubernetes documents it, or that it was not observed |
| "The runner is refused" by the network policy | The committed policy does not admit the runner. The outcome on an enforcing cluster is expected and was not run |
| The commit message and the changelog: the policy admits traffic "only from pods of the release" | And from a named collector |
| Two sentences on the resource ownership page, which the first commit did not edit: one workflow only creates an object that neither Terraform nor the chart owns, and each object of the project carries one label | Both are corrected |
| "The planning inputs" and "the story", in this record | Removed. This record names no source that is not in this repository |

### Noted, and not changed

- **The client deadline is the timeout of each socket operation.** The reviewer made
  the transport return after 2.61 s with a timeout of 0.3 s, against a server that
  sent its answer in slow parts. The V1 transport does the same. The runner file is
  not changed, so that it stays equal to the V1 transport. The page states the
  limit, and the active deadline of the Job has 120 seconds of margin and not 60.
- **The stop request is not atomic.** A signal that arrives while a worker sets the
  state `duration` can change the state. Each result is a true state.
- **`imagePullPolicy` is `Never`.** On a cluster with more than one node, the pod
  can be placed on a node without the image. The page states it.
- **The script was not executed against a cluster.** One reviewer ran the four
  actions outside the repository against stand-ins for `kubectl`, and reported that
  each sent the intended arguments. That run is not committed. It was of the first
  commit, and the second commit changed three of the four actions.
- **The query that reads the API image** has a filter expression. Whether the
  Windows `kubectl` receives it unchanged was not checked. A read that fails ends
  in a refusal.
- **`cleanup` asks once what is left.** The foreground deletion waits for the pod.
- **The manifest is not in the `kubeconform` gate of the chart.** It was checked
  once on this host.

## Validation at the second commit

| Command | Result |
|---|---|
| `PY -m ruff format --check .` | 702 files already formatted |
| `PY -m ruff check .` | All checks passed |
| `PY -m mypy` and `PY -m mypy --platform linux` | Success: no issues found in 384 source files, twice |
| `PY -m pytest tests/serving/test_reliability_runner.py -q` | 185 passed |
| `PY -m pytest tests/security tests/serving -q` | 2410 passed, 2 skipped |
| `PY -m pytest tests/architecture/test_cluster_lifecycle_safety.py tests/architecture/test_local_cluster_provider_contract.py tests/architecture/test_argocd_bootstrap.py tests/domain/test_renderer_input_boundary.py tests/architecture/test_resource_ownership.py tests/testing/test_test_inventory.py tests/testing/test_document_links.py -q` | 2963 passed |
| `bash -n scripts/environment/reliability-runner.sh` | Exit status 0 |
| `PY -m tools.reliability_runner verify docs/proof/serving/v2-s5-001-pr2-rehearsal-caller.jsonl` | Exit status 0: 12 requests, two of each outcome |
| `PY -m tools.reliability_runner plan ...`, then `manifest ...`, then `kubeconform -summary -strict` of the output | 2 resources found, 2 valid. The local `kubeconform` reports its version as `development` |
| `git diff --check` | No output |

Not run: `shellcheck`, which is not installed on this host. `helm`, `terraform`, and
the infrastructure gates, because this change edits no chart, no Terraform file, and
no desired state.

## The default lane

`PY -m pytest -q`, from the repository root, on the tree of the second commit before
it was committed, with each correction above in place:

| Result | Count |
|---|---:|
| Passed | 20,436 |
| Failed | 0 |
| Skipped | 40 |
| Deselected by the default marker expression | 14 |
| Time | 29 min 42 s |

The lane ran on the Windows host above. It contacts no cluster and reads no model
byte. This record does not list the reason of each skip. The hosted lane on Linux
ran no part of this change before the push.

## What stayed as it was

- **The V1 load harness and its profile.** Not edited.
- **The RP-1 profile and its registered digest.** Not edited. The docstring of the
  profile tool changed, and the digest is of the profile file.
- **The chart, its network policy, and the desired state.** Not edited.
- **The API image.** Not rebuilt.
- **The claim register, the dashboard, the evidence index, and each ledger.** Not
  edited.
- **The experiment freeze records.** No record selects RP-1 or the runner yet.

## The stale statements

This change made ten statements false, and it corrects each. The first commit
corrected eight. The second corrected the two of the resource ownership page.

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
| The resource ownership page, the cleanup section | The multi-replica workflow is the only one that creates an object which neither Terraform nor the chart owns | Two workflows do, and the two objects of a run have no row |
| The resource ownership page, the overlap section | Each object that this project creates carries `app.kubernetes.io/part-of: inferops` | The two objects of a run do not |

The `CHANGELOG.md` entry of `V2-S5-001-PR1` and its validation record keep their
words. They state what was true at that change.

## Privacy and publicability

- The diff holds no credential, no account identifier, no name of a host, and no
  path of a person's machine. The suite holds two addresses as values that a plan
  must refuse: `127.0.0.1` and `10.1.2.3`. `tests/security` passed.
- The prompt of RP-1 is public: `V2-S5-001-PR1` committed it. The rehearsal record
  holds no prompt and no completion, and a test holds that.
- The rehearsal record holds instants of this host's clock, to one millisecond.
  The first is the time of the rehearsal, and each later one is one millisecond
  after the one before it. It holds no host name.
- The plan and the manifest of a real run are written under `.artifacts/`, which
  version control ignores. None is committed.

## What this does not establish

- **That a runner pod runs.** No Job was created. The image, the mount, the
  command, the security context, and the log were not observed in a cluster.
- **That the script works against a cluster.** The suite reads its text: the calls
  it makes, the names it restates, and the order of the target verification.
- **That a cluster which enforces NetworkPolicy admits the runner.** The committed
  API policy admits pods of the release and a named collector. The runner is
  neither, and this change adds no allowance.
- **That a record of a long run is complete.** A rotated container log loses its
  first lines. The checker refuses such a record. It cannot recover it.
- **That a signal ends a run.** The suite calls the stop function.
- **That the release identifier names the release that answered.** It is declared.
- **Anything about a caller, a release, a latency, or a failure.** No request was
  sent to a model.
- **Anything about capacity or ownership.** The capacity preflight does not count
  the pod of a run, and the ownership inventory has no row for the two objects.
- **A representative workload, an overload point, or a production SLO.** A run
  under RP-1 cannot support C3.
