# V2-S5-003-PR1 validation

Status: **the infrastructure timelines of an experiment run can be captured as
four streams: the Ready endpoints of the two Services, the pods of the two tiers,
the Deployment of each tier, and what the delivery controller reported about one
Application. The collector and the stream tool are checked at evidence level C0,
against collections that the suites build and against stand-ins for `kubectl`.
No cluster was read, no stream of a real run is committed, and no claim was
registered.**

| Property | Value |
|---|---|
| Date | 2026-10-12 |
| Base | `07689d1`, the merge of pull request #139 |
| Branch | `feat/v2-s5-003-k8s-argo-timelines` |
| Commits | `cfe78d0`: the tool, the collector, the two suites, and the pages. The second commit: the corrections of the two independent reviews, and this record of them |
| Host | One Windows workstation, Git Bash; Python 3.12.12 from `uv`; kubectl client `v1.36.1`. `shellcheck` and `gitleaks` are not installed |
| Evidence level | C0. Every check reads committed files, reads a directory that a suite wrote, or executes the script against stand-ins for `kubectl`, `kind`, `docker`, and `git`. A fifth stand-in records each call of `python` and passes it to the interpreter of the suite |
| Claim effect | None. No claim, ledger, register row, dashboard row, evidence-index entry, or freeze record was added or changed |

## What changed

- [`scripts/environment/experiment-timeline.sh`](../../../scripts/environment/experiment-timeline.sh)
  samples the release a bounded number of times and writes one collection
  directory. A sample is two reads. Each kubectl call that the script holds is a
  `get` with a request timeout. The target verification of the script library
  runs first and makes reads of its own.
- [`tools/experiment_timeline`](../../../tools/experiment_timeline/__init__.py)
  reads a collection and prints four streams, checks a stored stream against
  nine rules of form, and prints the changes between consecutive readings of a
  stored stream. The first commit held eight rules.
- Two suites:
  [`tests/domain/test_experiment_timeline.py`](../../../tests/domain/test_experiment_timeline.py)
  and
  [`tests/architecture/test_experiment_timeline_collector.py`](../../../tests/architecture/test_experiment_timeline_collector.py).
  Neither commits a collection.
- [The timelines page](../../environment/experiment-timelines.md), with the
  clocks, the states, the limits, and what a stream does not establish.
- Three architecture suites name the new script: the two lists of entry points,
  the list of read-only scripts, and the list of build files that may name the
  delivery controller, which now holds six files.
- One paragraph of the evidence layout page and one of the endpoint-state page
  are amended, because each said that no such tool exists. The contributor
  guide, the README, the proof index, and the test inventory each gain an entry.

No existing tool, script, chart, manifest, schema, or contract was changed.

## What the change was asked to reach, and what it reached

| Asked | Reached |
|---|---|
| Collectors for the Ready endpoints of the API Service and the runtime Service | Reached as a collector and a tool, at C0. The `endpoints` stream states, for each sample and each tier, the counts and the pod name and pod UID of each endpoint. The rules are those of the endpoint-state record |
| The UID, the revision, the Ready condition, the restarts, the deletion, and the replacement of each pod | Reached at C0, with two stated limits. The `pods` stream states each of the first five. The restarts are two sums, of the containers and of the init containers, and a restart of an ephemeral container is not read. A replacement is not stated: a pod that left a reading and a pod that entered it are two facts, and no reading pairs them |
| The replica states of each Deployment | Reached at C0. Eight counts, the revision, and two conditions. A count that the API omitted is `missing` and not zero |
| The desired revision, the observed revision, the sync state, and the health state of the Application, and their transitions | Reached at C0. The `argo` stream states thirteen fields. The `changes` command states each difference between two readings, with the two reads that bound it |
| Persisted timestamps are normalised to UTC, and the resolution and the skew limits are recorded | Reached. Each read states two host instants in UTC to one millisecond. Each cluster instant is normalised to UTC and states its resolution. The skew is stated as not measured, with two observations that a collection supports |
| Tests for missing fields | Reached. See the negative controls below |
| Safe identities | Reached for the members that the tests name. A stream holds an allowlist, and each text value is held to a form. It is not a scan for every secret |
| The collectors do not change the workload | Reached as text and as an executed run against stand-ins: each kubectl call that the script holds is a `get`, and an executed capture, with the calls of the target verification, makes no call that is not a known read. No cluster observed this |

### The criteria of the parent change

| Criterion | State |
|---|---|
| Endpoint changes are timestamped | Reached at C0, as an interval. A change is not before the start of one read and not after the finish of the next. No stream states the instant of a change |
| The readiness, the revision, the deletion, and the replacement of a pod and of a Deployment are captured | Reached at C0, with the limit on replacement that the table above states |
| The state of the delivery controller is captured independently | Reached at C0. The Application read has its own state and its own instants, and a test holds that one read which did not answer leaves the other read's stream as it was |
| Prometheus preserves missing and zero as two states | Pending. This change reads no metric. Another change owns it |
| Operator fault, detection, and reversal events are aligned in UTC | Pending. This change records no operator event. Another change owns it |

The parent change also names a bounded integration capture as evidence. **It was
not made.** See the next section.

## What was not done

- **No cluster was read, and no capture was made.** On 2026-10-12 the
  `docker-desktop` context of this host refused the connection: three
  `kubectl get` calls, each of which changes nothing, returned
  `No connection could be made`. No cluster was started for this change. So what
  an API server returns to the collector, how long its two reads take, and
  whether the request timeout ends a request that hangs were not observed.
- **No stream of a run is committed, and no run directory holds one.**
- **No metric and no operator event.** Another change owns both.
- **No merge of a stream with a caller record, and no metric of an experiment.**
- **The evidence layout check was not changed.** It holds a stream file to its
  digest and does not read its form.
- **No freeze record was revised.** `tools.experiment_freeze --changes` lists 30
  material files that differ from freeze `r3` on the base and on this tree. This
  change moves none of them.

## Decisions taken in this change

1. **A new tool and a new script.** The endpoint-state tool, the Application
   procedure and its `observe` operation, and the reconciliation tool are not
   changed. The `endpoints` stream calls the endpoint-state tool for each sample,
   so one set of rules decides a tier in both. It imports one function of that
   tool that the tool does not publish. It does not copy the detail text of that
   tool into a stream: a detail can quote a name of an answer.
2. **One call reads the five workload kinds.** The Services, the EndpointSlices,
   the pods, the ReplicaSets, and the Deployments of a sample share one interval.
   The cost is that the call fails as a whole: a kind that does not answer leaves
   the sample with no workload reading.
3. **The Application is a second read.** It has its own two instants and its own
   state, so the state of the delivery controller does not depend on the workload
   read and the workload streams do not depend on it.
4. **The time basis is the collecting host's clock, to one millisecond.** It is
   the form of the caller record. A cluster instant is kept beside it with its
   own resolution, and it is not moved onto the host clock. The skew is not
   measured, and the header of each stream says so.
5. **Three field states, and none is a default.** `reported`, `missing`, and
   `malformed`. A status count that the API omitted is `missing`: Kubernetes
   omits a zero and an unwritten count alike, and the field cannot tell them
   apart.
6. **Five read states.** `answered`, `absent`, `unanswered`, `unreadable`, and
   `not-taken`. Only `answered` gives values. An answer that no stream can use
   is `unreadable` and is not counted as answered.
7. **The reads are polled, and the pause is not a period.** A watch was not used.
   A state that began and ended between two samples is in no reading, and the
   page says so.
8. **A stream is one file of JSON lines for each registered role.** The names are
   four raw roles that the evidence layout already registers, so no role was
   added.
9. **A collection is not committed.** It holds the whole answer of each read:
   addresses, node names, and the environment of each pod. The consequence is
   that a committed stream cannot be built again from committed files, and the
   `check` command reads the form of a stream and nothing else.
10. **An allowlist, and a form for each text value.** A stream holds no message
    and no free text of a cluster. A value of another form is `malformed` and is
    not copied.
11. **A change does not pair a pod that left with a pod that entered.** No field
    of the two objects links them.
12. **A deletion timestamp is not a clock observation.** Kubernetes sets it to
    the end of the grace period, so it can be later than the read on one clock.
    The first draft counted it as a sign of skew. The stream now states the grace
    period beside it and leaves it out of the count.
13. **The bounds.** 1800 samples, a pause of 1 to 30 seconds, a timeout of 10
    seconds for each request of a read, 64 pods of the two tiers, and 8
    containers for one status list of a pod. No measurement set them. A
    result-bearing run of several minutes at a pause of 1 or 2 seconds is inside
    them. The timeout does not bound a read, which makes more than one request.
14. **The script is a sixth build file that names the delivery controller.** It
    reads one Application with a `get`, so it names the kind and the namespace. A
    test holds that those two lines are the only lines that match the pattern of
    the architecture suite. The stream name `argo` is also in the script, and
    that pattern does not match it.
15. **The Application is the one of the `docker-desktop` provider, by name.** No
    other Application is committed. On a cluster that has the resource type and
    no such object, the reading states `absent`. On a cluster without the
    resource type, the read does not answer and the reading states `unanswered`.
    The reconciliation record observed both for the same read. This collector
    observed neither.
16. **The restarts of init containers are a second sum.** The chart's runtime pod
    has an init container. Kubernetes reports its restarts in another list than
    the restarts of a container, so one sum over the containers states 0 for a
    pod whose init container restarts.

## The negative controls

Each row is a case that the tool is given and a value that it must not state.

| Case | What the stream states | What it does not state |
|---|---|---|
| A Deployment status with no `readyReplicas` | `missing` | Zero |
| A Deployment with no status | Each status count `missing`, and `specReplicas` reported | Zero replicas |
| A pod with no Ready condition | `ready` is `missing` | Not Ready |
| A Ready condition of `Unknown` | `Unknown` | False |
| A pod with no container status | `restartCount` is `missing` | Zero restarts |
| A container that states no restart count | The sum is `malformed` | A sum of the others |
| A pod whose init container restarted 7 times and whose container did not restart | `initRestartCount` is 7, and `restartCount` is 0 | One count of 0 for the pod |
| A pod with no init container status | `initRestartCount` is `missing` | Zero |
| A Service with a label key that looks like a credential and a value that is not text, and two Services with one name | The rule, and the number of faults | The label key, or the name |
| An answer that is a list of another kind | `unreadable` | An answered read |
| A pod whose ReplicaSet is not in the read | `revision` is `missing` | A revision of another object |
| An Application with no health state and no sync state | Both `missing` | Healthy, or Synced |
| A workload read that did not answer | Three readings with no value | An empty namespace |
| An Application read that did not answer | A reading with no field | An absent Application |
| An empty answer of the workload read | `unreadable` | No pod |
| An answer that is another object than the named Application | No field, and a fault | The fields of that object |
| A sample with no usable instants | `unreadable`, with no instant | A place on the timeline |
| A count that stops being reported between two readings | A change to `missing` | A change to zero |
| A reading that gave no value between two that did | A change to `not-collected` and a change from it | A value carried across |
| An address, a node name, an image, an environment value, a message, and a repository address with a credential in an answer | None of them | The value |

## Validation at the first commit

Each command ran on the tree of the first commit, before it was committed.

| Command | Result |
|---|---|
| `uv run --locked ruff check .` | No finding |
| `uv run --locked ruff format --check .` | 722 files already formatted |
| `uv run --locked python -m mypy` | No issue in 397 source files |
| `uv run --locked python -m mypy --platform linux` | No issue in 397 source files |
| `uv run --locked python -m pytest tests/domain/test_experiment_timeline.py -q` | 172 passed |
| `uv run --locked python -m pytest tests/architecture/test_experiment_timeline_collector.py -q` | 34 passed |
| `uv run --locked python -m pytest tests/architecture/test_cluster_lifecycle_safety.py tests/architecture/test_local_cluster_provider_contract.py tests/architecture/test_argocd_bootstrap.py tests/architecture/test_experiment_timeline_collector.py tests/architecture/test_service_endpoint_state_collector.py tests/domain/test_renderer_input_boundary.py tests/domain/test_experiment_timeline.py tests/domain/test_service_endpoint_state.py tests/security tests/testing -q` | 10,446 passed, 3 skipped, 1 failed. The failure is described below. After the correction, the two modules it touches passed: 273 passed |
| `uv run --locked python -m pytest -q` | Not run on the tree of the first commit. The default lane takes about 50 minutes on this host, and it ran once, on the tree of the second commit |
| `uv run --locked python -m tools.experiment_freeze --check` | `PASSED: 3 freeze record(s), every rule held` |
| `uv run --locked python -m tools.experiment_freeze --changes docs/proof/experiments/v2-e01/freeze-r3.v1alpha1.json` | 30 material files differ. The base holds the same 30 |
| `bash -n scripts/environment/experiment-timeline.sh` | No syntax error |
| `git diff --check` against the base | No whitespace error |

`shellcheck` is not installed on this host, and no workflow runs it over
`scripts/`. So the new script was not linted. `gitleaks` is not installed on this
host either, so no secret scan ran here. The hosted workflow did not run before
the push, so no hosted result is stated here.

**Three defects were found before the first commit, and none by a reviewer.**

- **A deletion timestamp was read as a sign of clock skew.** The first draft
  counted each cluster instant that is later than its read. Kubernetes sets the
  deletion timestamp of a pod to the end of its grace period, so that instant is
  later than the read on one clock too. The count now leaves it out, the stream
  states the grace period beside it, and a test holds both.
- **A test builder quoted the API version of a custom resource of the delivery
  controller.** `tests/architecture/test_argocd_bootstrap.py` pins the tracked
  files that hold one, and it failed. The tool does not read that member, and
  the builder no longer states it.
- **A test named an experiment that this repository does not publish.** The
  identifier is now a neutral one.

## What the independent reviews found

Two reviews read the first commit, `cfe78d0`. One read the tool and the script
and gave the tool hostile collections and hostile streams. The other compared
each sentence of the pages, the record, and the suites with the code. Neither
changed a file. The second commit corrects each finding below, except those in
the last subsection.

### What the code got wrong

- **Text of an answer reached a stream.** The `endpoints` stream copied the
  detail text of the endpoint-state tool into `faults`. That tool quotes a label
  key and an object name before it checks any form. A Service with the label key
  `AKIAIOSFODNN7EXAMPLE/token-hunter2` and two Services named `password-hunter2`
  each reached the stream. The first commit said that a stream holds no free
  text of a cluster. A fault of that stream now states the rule and a number, or
  the rule and the tier, and two tests hold it.
- **The restarts of an init container were not read.** A pod whose init
  container had restarted 7 times stated `restartCount` as a reported 0. The
  chart's runtime pod has an init container. The stream now states
  `initContainers` and `initRestartCount`, and a restart of an ephemeral
  container is stated as not read.
- **The `changes` command ended in an error on a stream that `check` accepted.**
  A stored stream with `"pods": "abc"`, a pod with no `ready`, a tier with no
  `endpoints`, or an Application that is a list each raised an error that no
  rule names, with exit status 1. A ninth rule, `timeline-reading-unsupported`,
  now holds each value that `changes` reads to its type, and 28 mutations are
  each refused with exit status 3.
- **An item whose `kind` is a list ended the build in an error.** It is now an
  item of a kind that was not asked for.
- **An answer that no stream can use was counted as answered.** A list of another
  kind, an item of another kind, and an object that is not the named Application
  each kept the read state `answered` with no value, and the end line counted
  them as answered. Each is now `unreadable`.
- **A stored `index` of `1.0`, and a count of `true` in the end line, were
  accepted.** Each is now refused.
- **Two readings that give no value had no change between them, also when their
  states differ.** A reading that was not collected and then a reading that was
  refused now give one change of the subject `reading`.
- **A year below 1000 was formatted by the C library,** which does not pad it on
  every host. The year is now formatted with four digits. This was found by
  reading. It was not reproduced, because this host pads the year.
- **A file of a sample that cannot be opened raised an error.** It is now an
  unreadable read.
- **The script logged an absent Application as answered.** It now logs
  `answered with no object`.

### What the pages got wrong

- **"Each read has a timeout of 10 seconds."** The flag is the timeout of each
  request, and the workload read makes one request for each kind. A read can
  take longer and still answer. The header member is now
  `requestTimeoutSeconds`, and the page, the script, the changelog, and a
  limitation of each stream say what the timeout is.
- **"On another provider the reading states `absent`."** The reconciliation
  record observed that the same read does not answer on a cluster without the
  resource type. The page and decision 15 now state both cases.
- **"Each kubectl call is a `get`."** That is true of the calls that the script
  holds. The target verification of the library makes `config`, `version`, and
  `get` calls before the first sample. The script, the page, and this record now
  say so.
- **"A test holds both"** was said of the deletion timestamp and the grace
  period. No test asserted a reported grace period. One does now.
- **Counts.** "A reading lists at most 10" faults: it lists 10 and one line that
  counts the others. "The three instants of the delivery controller": the stream
  holds five instants of the Application. Both are corrected.
- **The read-state table** listed three causes of `unreadable`, and the code has
  six. The table now lists each.
- **The Changes section** did not name the state `refused`, and used `absent`
  for two things without saying so.
- **Members that a stream holds and the page did not list:** five members of an
  `endpoints` tier, `tier` and `state` of a `deployments` tier, and two members
  of the header. The list of forms left out four forms.
- **"The tool refuses a header with a member of another form"** has one
  exception, the server version, which is kept as `malformed`.
- **The rule `timeline-reading-out-of-sequence` said that no line follows the end
  line.** A line after the end line is refused by `timeline-end-missing`. The two
  statements are corrected.
- **Three sentences of an architecture suite said that one build file names the
  delivery controller.** They were false before this change, which edited the
  comment beside them. They now name the list.
- **The architecture index and the question table** did not list the new page.
- **Smaller points:** the stand-in for `python` was not stated; the exit status 1
  of the script was described too narrowly; the layout page said that the tool
  writes the stream files, and the script does; the test of a Deployment with no
  status read three of the six status counts; one assertion could not fail and
  was removed.

### Noted, and not changed

- **`Collection.complete` is true when each sample was written, also when each
  read is `unreadable`.** It states that the collector finished, and the page
  says that.
- **More than 64 pods of the two tiers leave a reading with no pod.** A pod that
  failed or was evicted stays in the read and counts. The page now says so.
- **The deletion timestamp of a pod that is not being deleted is `missing`.** A
  reading cannot tell that from a field that was dropped.
- **The word "interval"** is the `--interval` argument, which is a pause, and
  also the time between two reads. The argument keeps its name, which the
  Application procedure also uses.
- **The stand-in for `kubectl` answers a call it does not know with nothing and
  exit status 0.** The suites read the recorded calls. The inventory now says so.

## Validation at the second commit

Each command ran on the tree of the second commit, before it was committed.

| Command | Result |
|---|---|
| `uv run --locked ruff check .` | No finding |
| `uv run --locked ruff format --check .` | 722 files already formatted |
| `uv run --locked python -m mypy` | No issue in 397 source files. The first run of this command on the corrected tree reported one error in a new test, which was corrected |
| `uv run --locked python -m mypy --platform linux` | No issue in 397 source files |
| `uv run --locked python -m pytest tests/domain/test_experiment_timeline.py -q` | 220 passed. The first commit held 172 |
| `uv run --locked python -m pytest tests/architecture/test_experiment_timeline_collector.py -q` | 34 passed |
| `uv run --locked python -m tools.experiment_freeze --changes docs/proof/experiments/v2-e01/freeze-r3.v1alpha1.json` | 30 material files differ, the same 30 as on the base |
| `bash -n scripts/environment/experiment-timeline.sh` | No syntax error |
| `git diff --check` against the base | No whitespace error |

## The default lane

| Command | Result |
|---|---|
| `uv run --locked python -m pytest -q` | 21,277 passed, 42 skipped, 14 deselected, 1 failed, in 28 minutes |

The lane ran once, on the tree of the second commit, before this section was
filled in. It ran on one Windows host. The skipped tests are the ones that this
host cannot run, and the deselected tests need a cluster or a model.

**One test failed in the lane, and it is not a test of this change.**
`test_a_live_object_that_is_not_the_committed_one_is_a_finding[project-spec-apply]`
in `tests/architecture/test_argocd_application_procedure.py` executes the
Application procedure against stand-ins. In the lane its run of the procedure
printed nothing, and the test found no finding in an empty output. This change
does not edit that suite, that procedure, or the script library. The eight cases
of that test were then run alone three times, and each run passed: 8 passed,
three times. The cause of the empty output was not found. The lane was not run
again, so no run of the whole lane with no failure is stated here. The hosted
workflow did not run before the push.

## Privacy and publicability

The suites build every collection with invented names, UIDs, and addresses, in a
temporary directory. No collection and no stream is committed. The changed files
hold no personal path, no credential, no account identifier, and no host name.
The diff against the base was read for each.

## What the evidence establishes

- The tool gives one text for one collection, and it states a state and no value
  for each field and each read that the cases above name.
- The script, as committed, asks a cluster for two reads for each sample with
  `get` and no other verb, and writes what the stand-ins answer.
- The page, the tool, and the script agree on the names, the bounds, the rules,
  the limitations, and the boundaries that the two suites compare.

## What the evidence does not establish

- What a cluster returns to the collector, how long a sample takes, or the
  shortest interval that a host supports.
- That the read timeout ends a read that hangs.
- That a stream of a real run is correct. None exists.
- The difference between the host clock and a cluster clock on any environment.
- That the allowlist excludes every secret. The test names the members it covers.
- Anything about a caller. A stream is not a caller's result.
- Anything about an experiment. No run started, and no criterion was read.
