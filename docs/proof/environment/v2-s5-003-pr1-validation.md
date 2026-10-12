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
| Commits | The first commit: the tool, the collector, the two suites, and the pages. The second commit: the corrections of the independent review |
| Host | One Windows workstation, Git Bash; Python 3.12.12 from `uv`; kubectl client `v1.36.1`. `shellcheck` and `gitleaks` are not installed |
| Evidence level | C0. Every check reads committed files, reads a directory that a suite wrote, or executes the script against stand-ins for `kubectl`, `kind`, `docker`, and `git` |
| Claim effect | None. No claim, ledger, register row, dashboard row, evidence-index entry, or freeze record was added or changed |

## What changed

- [`scripts/environment/experiment-timeline.sh`](../../../scripts/environment/experiment-timeline.sh)
  samples the release a bounded number of times and writes one collection
  directory. A sample is two reads. Each of its kubectl calls is a `get` with a
  read timeout.
- [`tools/experiment_timeline`](../../../tools/experiment_timeline/__init__.py)
  reads a collection and prints four streams, checks a stored stream against
  eight rules of form, and prints the changes between consecutive readings of a
  stored stream.
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
| The UID, the revision, the Ready condition, the restarts, the deletion, and the replacement of each pod | Reached at C0, with one stated limit. The `pods` stream states each of the first five. A replacement is not stated: a pod that left a reading and a pod that entered it are two facts, and no reading pairs them |
| The replica states of each Deployment | Reached at C0. Eight counts, the revision, and two conditions. A count that the API omitted is `missing` and not zero |
| The desired revision, the observed revision, the sync state, and the health state of the Application, and their transitions | Reached at C0. The `argo` stream states thirteen fields. The `changes` command states each difference between two readings, with the two reads that bound it |
| Persisted timestamps are normalised to UTC, and the resolution and the skew limits are recorded | Reached. Each read states two host instants in UTC to one millisecond. Each cluster instant is normalised to UTC and states its resolution. The skew is stated as not measured, with two observations that a collection supports |
| Tests for missing fields | Reached. See the negative controls below |
| Safe identities | Reached for the members that the tests name. A stream holds an allowlist, and each text value is held to a form. It is not a scan for every secret |
| The collectors do not change the workload | Reached as text and as an executed run against stand-ins: each kubectl call is a `get`, and an executed capture makes no call that is not a known read. No cluster observed this |

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
  whether its timeout ends a read that hangs were not observed.
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
   tool that the tool does not publish.
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
   `not-taken`. Only `answered` gives values.
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
13. **The bounds.** 1800 samples, a pause of 1 to 30 seconds, a read timeout of 10
    seconds, 64 pods of the two tiers, and 8 containers for one pod. No
    measurement set them. A result-bearing run of several minutes at a pause of
    1 or 2 seconds is inside them.
14. **The script is a sixth build file that names the delivery controller.** It
    reads one Application with a `get`, so it names the kind and the namespace. A
    test holds it to those two lines.
15. **The Application is the one of the `docker-desktop` provider, by name.** No
    other Application is committed. On another provider the reading states
    `absent`.

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
