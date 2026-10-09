# V2-S4-003-PR1 validation

Status: **the capacity gate for the two-replica release is implemented, and
synthetic cases show one acceptance and each kind of refusal. This is evidence at
C0.** One reading of the `docker-desktop` provider, with no release and no Argo CD installation on it, is committed, and its record has the result `ACCEPTED`. That reading is not a qualification of that host. No chart file, contract, binding, Terraform file,
Application, or freeze record was changed, and no claim was registered. The
controlled baseline profile with one serving runtime replica is not in this
change. An independent review found that the first commit could accept a cluster
from documents it did not read correctly, and that it overstated what it
checked: see [what the independent review found](#what-the-independent-review-found).

| Property | Value |
|---|---|
| Date | 2026-10-09 |
| Base | `e515776cfb6ebf6ca97085f5d0da8b6af6524dcb`, the merge of pull request #129 |
| Branch | `feat/v2-s4-003-capacity-preflight` |
| Commits | `170a96c7`: the gate, the cases, the suites, and the page. `479ffda5`: the corrections of the independent review. A third commit: one reading of a cluster, made from the second commit, and the default lane |
| Host | One Windows workstation, Git Bash (GNU bash 5.2.26); Python 3.12.12 from `uv` 0.9.16; Helm `v3.19.0`; Docker engine `29.8.1`; `kubectl` client `v1.36.1` |
| Evidence level | C0 for the two suites and the six synthetic cases. The one reading read a real cluster and ran no workload. It is assigned no level, and it is not evidence that a pod runs |
| Claim effect | None. No claim, ledger, register row, dashboard row, or evidence-index entry was added or changed |

## What changed

- `tools/capacity_preflight` is new. It reads one collection directory and prints
  one record, whose result is `ACCEPTED` or `REFUSED`. It reads files and contacts
  no cluster. [The capacity preflight page](../../environment/capacity-preflight.md)
  describes the footprint, the collection, the units, the 13 rules, and what a
  record does not establish.
- `scripts/environment/capacity-preflight.sh` is new. It verifies the selected
  target, refuses a working tree that differs from its commit, writes the
  declared footprint, reads the cluster, and writes one collection under
  `.artifacts/`. Each cluster call that the script holds is a `kubectl get` or a
  `kubectl version`. It exits 0 for an acceptance, 5 for a refusal, and 1 when no
  record was written.
- `tests/domain/fixtures/capacity-preflight/` holds six synthetic collections,
  each with its record: one acceptance, two refusals as `insufficient`, and three
  refusals as `ambiguous`.
- `tests/domain/test_capacity_preflight.py` and
  `tests/architecture/test_capacity_preflight_collector.py` are new.
- Three existing suites are edited. The script is added to the entry points and
  the read-only scripts of `test_cluster_lifecycle_safety.py`, and to the platform
  workflows of `test_local_cluster_provider_contract.py`. Two number words are
  added to `test_test_inventory.py`.
- These pages state the gate: `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, the
  chart's README, the architecture index, the system architecture, the Git
  desired-state page, and the proof index. The model cache observation page gains
  one dated note. The test inventory gains two modules. The new page and this
  record are added.

## What the change was asked to reach, and what it reached

| Asked | Reached |
|---|---|
| The preflight records allocatable resources, reservations, footprint, requests, and rollout headroom | Reached. A record states the node's allocatable and capacity figures, the requests of the unfinished pods by namespace, the footprint with the requests and the memory limit of each container, the surge pods as rollout headroom, and each comparison with its unit |
| Insufficient capacity is refused and the gate is not weakened | Reached at C0. Each figure is refused one unit below the requirement. A stored footprint with a lowered reserve, requirement, pod figure, or headroom is not a collection. A footprint for fewer replicas is refused by the command |
| An ambiguous environment is refused before a mutation | Reached at C0. Nine rules refuse as `ambiguous`, and a read that was not made refuses. The script holds no call that changes the cluster. No procedure calls the gate, so nothing prevents an install after a refusal |
| Deterministic accept and refuse fixtures | Reached. Six committed cases, and `--check` builds each record again |
| A controlled profile of two API replicas and one runtime replica exists | Not in this change |
| The baseline and the target differ only in the runtime replica count | Not in this change |

## Decisions taken in this change

Each of these was open. The page states each as a property of the gate.

1. **The requirement is derived, and not written down.** The V1 preflight reads
   figures from a descriptor, and a test holds them to the chart. This gate reads
   the Application, the chart's defaults, and the generated values, and restates
   which pods the chart renders. A test compares that restatement with a render.
2. **Memory is held on the limits.** This is the V1 rule. The record states the
   memory requests, and no rule reads them.
3. **The reserve is the V1 headroom: 500 millicores and 512 MiB.** It is not
   derived from a measurement.
4. **Rollout headroom is the surge pods that each Deployment's bounds permit.**
   The API surges by one pod and the runtime by none, as the chart states. The
   collector's Deployment states no strategy, so the gate uses the default that
   the Kubernetes documentation states: one pod.
5. **A pod that is terminating is not counted.** The Kubernetes documentation
   states that a terminating pod is not counted against the rollout bounds. So a
   rollout can hold a third runtime pod for up to the termination grace period,
   and the gate requires no room for it. The chart keeps the runtime's surge at
   zero so that a rollout creates no pod above the replica count. Requiring a
   third runtime here would be a larger requirement than that design states. The
   limit is stated in each record.
6. **The hook pod and the test pod are counted beside the surge pods.** Whether
   those pods exist at one time was not observed.
7. **The gate decides for one schedulable node.** More than one is refused as
   ambiguous, because the model cache claim is `ReadWriteOnce` and the gate places
   no pod among nodes.
8. **A pod that states no request is counted as zero.** The sum is a sum of
   stated requests. The record states how many such pods it counted.
9. **A release that is already installed is refused.** Its pods are in the node's
   figures, and the gate would count the release two times.
10. **The model cache rule is not required.** The gate can run before the
    prerequisite layer creates the claim. A claim that is `Lost`, or smaller than
    the artifact, refuses.
11. **The engine minimum of V1 is not a rule here.** The engine's figures are
    stated in the record. For memory, a node that this gate accepts allocates more
    than the V1 engine minimum. **For the processor it can allocate less**: the
    gate requires 3,110 millicores that no counted pod requests, and V1 requires 4
    engine processors.
12. **The tool reads the Application, and it imports no release declaration.**
    The repository's boundary check refuses a script that names a tool which
    reaches the render package. The collector is a script, so the tool it calls
    holds its own table of Applications. A test compares that table with the
    declared desired state.
13. **The command compares the stored footprint with the files of the tree.** The
    record of a collection is built from the footprint that the collection stores.
    Without the comparison, a collection written for fewer replicas would give an
    acceptance for another release.
14. **The script refuses a working tree that differs from its commit.** The
    footprint is read from files, and the collection names a commit. The review
    showed that an edited values file gave an acceptance that named the unedited
    commit.
15. **The gate does not compare its commit with the revision that the Application
    names.** That revision is a branch of a remote repository. A reading made from
    a checkout that is behind that branch decides for another release. The limit
    is stated in each record.

## Two readings during development that are not recorded

The collector was run two times against the local `docker-desktop` cluster while
it was written. Each run was made from a working tree that was not a commit, so
neither directory is committed and neither is a record of this repository. They
are stated here because they were made. The script now refuses such a tree.

- **The first run made no read.** The script could not read the commit of the
  working tree: it gave `git` a POSIX path that the Windows `git` did not
  resolve. The script was corrected to change directory first.
- **The second run printed `ACCEPTED`.** The cluster held one node, nine system
  pods, no Argo CD installation, and no release. The node allocated 12,000
  millicores and 10,430,672,896 bytes. The nine pods requested 950 millicores and
  304,087,040 bytes. The gate required 3,110 millicores and 9,865,003,008 bytes
  of memory limits, and 10,126,585,856 bytes were available: 261,582,848 bytes
  more than required. The model cache claim did not exist, so its rule was
  `not-observed`.

The synthetic case `accepted-one-node` was written with the figures of that
second run. No file of that run is in the case.

**This is not a qualification of that host.** It is one reading of a cluster that
ran nothing of this project. It states that the stated figures fit on that day.
It does not establish that two runtime pods start there, and Argo CD, which a
reconciled release needs, stated no request on 2026-10-08 and would be counted as
zero.

## The one committed reading

After the second commit, the collector was run once against the local
`docker-desktop` cluster, from a clean working tree at
`479ffda591b484edcd9ee19e1e040b6aee542124`. It made reads only.
[The collection and its record](v2-s4-003-pr1-capacity-preflight-run-1/record.v1alpha1.json)
and [the transcript](v2-s4-003-pr1-capacity-preflight-run-1-transcript.txt) are
committed. It was the first run of the corrected script, and it was not repeated.

- **The record has the result `ACCEPTED`.** 12 rules are `held`. The claim rule
  is `not-observed`: the read of the release namespace returned no claim.
- **The figures are those of the second development reading.** The node
  allocated 12,000 millicores and 10,430,672,896 bytes, nine system pods
  requested 950 millicores and 304,087,040 bytes, and 261,582,848 bytes of
  memory were available beyond the requirement.
- **The commit is a commit of this branch.** The Application names `main`. The
  chart's values, its `Chart.yaml`, the generated values, and the Application are
  the same files at both.

**This is not a qualification of that host, and it is not the result of an
experiment.** The cluster held no Argo CD installation and no pod of this
project. [The page](../../environment/capacity-preflight.md#the-one-committed-reading)
states what the reading does not establish. The memory margin is smaller than
the reserve, and an Argo CD installation that states no request would be counted
as zero.

## What the independent review found

Two automated reviewing sessions read the first commit, read-only. One built
collections of its own to make the tool print `ACCEPTED` for a cluster that was
short. One compared each statement with the code and the committed files. Neither
contacted a cluster.

Neither found a wrong `ACCEPTED` from a well-formed read of a cluster, made from a
clean tree at the commit that the Application deploys. Each wrong `ACCEPTED`
below needed an edited tree, an edited Application, or a document that an API
server does not return.

### What the tool got wrong

**Each of these gave `ACCEPTED`, or exit status 0, for a cluster that the
arithmetic refuses, or for a requirement that was lowered. Each now refuses.**

- **The footprint was read from an edited working tree.** With one replica count
  changed in an uncommitted values file, the reviewer's record was `ACCEPTED`
  on a node of 2,500 millicores and 6 GiB, and it named the unedited commit. The
  comparison with "the committed files" compared the footprint with the same
  edited tree. The script now refuses a working tree that differs from its
  commit.
- **A node without a name, and a pod with an odd node name, made every
  reservation vanish.** Three pods that requested 6 processors on a node of 4
  were counted as pods of another node. A node, or an unfinished pod, whose
  kind, name, or member has another type is now refused under a new rule,
  `reads-well-formed`. A pod that names a node the read does not hold is refused
  too.
- **A member of another type was read as absent.** A container list that was a
  mapping, a request block that was a list, a taint list that was a mapping, a
  taint effect in another case, a cordon inside a list, and a condition stated
  two times each gave `ACCEPTED`. The same rule now refuses each.
- **An empty pod list was read as a cluster that holds nothing.** It is now
  refused.
- **A pressure condition that a node did not report was read as no pressure.**
  The node rule now requires each of the three as `False`.
- **The Application was read for a few members, and any other was ignored.** A
  second source and a file parameter left the footprint unchanged. A values
  object that was not a mapping made the collector's pod disappear from the
  footprint. The tool now reads the Application against a list of members and
  gives no footprint for another one.
- **A resource other than processor and memory was dropped from the
  requirement.** The tool now gives no footprint for one.
- **The model cache rule held for a claim in the phase `Lost`, and for a claim
  whose request was below the artifact.** It now refuses a `Lost` claim, and it
  compares the smaller of the capacity and the request.
- **With `--as-collected`, exit status 0 was printed for a footprint that no tree
  was compared with.** With that option, exit status 0 now says only that a
  record was printed.
- **A pod's init container that stated no request was not in the count of pods
  that state none.** It now is.
- **A claim of another namespace was not refused when the quota read was
  absent.** The two reads are now checked separately.

### What the first commit said, and what is true

- It said that the footprint is "read from committed files". It was read from
  files of the working tree, and nothing compared the tree with a commit.
- It said that the runtime's surge of zero means "no third runtime is required",
  and that the sum of the surge pods and the hook pods "is an upper bound". The
  Kubernetes documentation states that a terminating pod is not counted against
  the rollout bounds, so a third runtime pod can hold its request for a time.
  The sum is not an upper bound.
- It said that the script "only reads" and "changes nothing". The target
  verification writes the target's kubeconfig under `.kube/`. The script changes
  nothing in the cluster or the engine.
- Two texts said that the footprint is written "before the first read of the
  cluster". The target verification reads the cluster first.
- It said that no rule reads the node's capacity and ephemeral storage. An
  unreadable one fails `quantities-readable`.
- It said "the node is not Ready or is tainted". Only a taint with the effect
  `NoSchedule` or `NoExecute` refuses, and a pressure condition refuses too.
- It said that the three figures each include the reserve. The pod count has
  none.
- It said that the record states "how many pods state none". The count left out
  init containers.
- It said that a quantity the V1 program cannot read makes that program fail.
  The V1 program reads a blank as zero.
- It said that each requirement is larger than the V1 figure "for the same
  Deployments". The V1 figure also holds one pod with the test pod's resources.
- It said that the six cases are synthetic and did not say that one of them
  carries the figures of the unrecorded reading.
- The record of the committed case with two nodes stated that nine pods were "on
  another node" and that no pod was unfinished. Both counts were artefacts. With
  no one node, a record now states no count.
- This record gave "8,182 passed, 1 skipped" for one command at the first commit.
  That run was made before this record and the proof index edit were tracked,
  and the link suite has one case for each tracked page. At the first commit the
  same command collects 8,184 tests.
- This record said "three tables of two existing suites" and "seven pages". It
  left out the number words of a third suite and the proof index.
- The Git desired-state page kept the sentence "nothing in this tree refuses a
  cluster that cannot schedule them" beside the new one.
- Several statements about Kubernetes were not attributed. Each is now
  attributed, or is stated as a property of the chart.

### Noted, and not changed

- **The check of a committed collection does not verify where it came from.** It
  does not compare the digests in the footprint with the files of the commit
  that the header names. That needs the history of the commit, which a shallow
  clone does not hold. The page states the limit.
- **A request below one millicore is rounded up for the pod, and not for each
  container.** The page states it.
- **No procedure calls the gate.** It is run by an operator.
- **The procedure that applies the Application adds one Helm parameter that the
  committed file does not hold.** The tool reads the committed file. It does not
  read the applied object.
- **The test that reads the script for mutating calls reads the script.** The
  target verification is a library function. The executed tests hold that no
  kubectl call of a run is outside a list of reads.
- **`docs/environment/runtime-model-cache-observation.md` keeps the sentence "No
  capacity gate exists for the V2 topology" in the present tense.** It describes
  `run-1`, and a dated note above it states the change.

## Validation at the first commit

Each command ran on the host of the table above.

| Command | Result |
|---|---|
| `uv run --locked ruff check .` | No finding |
| `uv run --locked ruff format --check .` | No file to reformat |
| `uv run --locked python -m mypy` | No issue in 366 source files |
| `uv run --locked python -m pytest tests/domain/test_capacity_preflight.py -q` | 227 passed. The comparison with a render ran: `helm` is installed |
| `uv run --locked python -m pytest tests/architecture/test_capacity_preflight_collector.py -q` | 21 passed. `bash` is installed |
| `uv run --locked python -m pytest tests/architecture/test_cluster_lifecycle_safety.py tests/architecture/test_local_cluster_provider_contract.py -q` | 416 passed |
| `uv run --locked python -m pytest tests/testing tests/domain/test_renderer_input_boundary.py -q` | 8,182 passed, 1 skipped, before two pages were tracked. See the review section |
| `uv run --locked python -m tools.capacity_preflight --check` | `PASSED: 6 committed collection(s), each record is what its collection gives` |
| `bash -n scripts/environment/capacity-preflight.sh` | No syntax error |
| `git diff --check` against the base | No whitespace error |

**Not run at the first commit.** The whole default lane was started and was
stopped before it finished, because the review's corrections changed the tree.
`shellcheck` is not installed on this host, so the script was not linted here.
`gitleaks` is not installed on this host. Hosted CI was not read: no pull request
existed.

## Validation at the second commit

Each command ran on the same host, from the working tree that the second commit
holds.

| Command | Result |
|---|---|
| `uv run --locked ruff check .` | No finding |
| `uv run --locked ruff format --check .` | No file to reformat |
| `uv run --locked python -m mypy` | No issue in 366 source files |
| `uv run --locked python -m pytest tests/domain/test_capacity_preflight.py tests/architecture/test_cluster_lifecycle_safety.py tests/architecture/test_local_cluster_provider_contract.py -q` | 693 passed. The gate's suite is 277 of them |
| `uv run --locked python -m pytest tests/architecture/test_capacity_preflight_collector.py -q` | 24 passed |
| `uv run --locked python -m pytest tests/testing tests/domain/test_renderer_input_boundary.py -q` | 8,183 passed, 1 skipped |
| `uv run --locked python -m tools.capacity_preflight --check` | `PASSED: 6 committed collection(s), each record is what its collection gives` |
| `bash -n scripts/environment/capacity-preflight.sh` | No syntax error |
| `git diff --check` against the base | No whitespace error |

The six cases were written again by the suite's builders, because the record
gained a rule, two limits, and two members. Each case has the result and the
refusing rules it had, except that the case without `pods.json` now also names
`reads-well-formed`.

**Not run at the second commit.** The whole default lane, `shellcheck`, and
`gitleaks`, for the reasons above. Hosted CI was not read.

## The default lane

`uv run --locked python -m pytest -q` ran once on the working tree of the third
commit, before the correction below: 19,691 passed, 2 failed, 37 skipped, and 14
deselected, in 28 minutes.

**Both failures were one finding, and neither targeted run had shown it.**
`tests/architecture/test_argocd_bootstrap.py` holds a list of the build files
that may name Argo CD: the two manifests, and the two procedures. The tool names
one manifest by its path, because it reads the values that the Application gives
the chart. So the tool was a fifth file, and two tests failed. The first two
commits carry that failure.

**The list was changed on purpose, and not the tool.** The tool is added to the
list. A new test holds that each place where the tool's text names Argo CD is
the path of one of the two manifests, so an address, an API group, or a command
of the controller in the tool fails. The tool reads a committed file. It
addresses no controller. After the correction, that suite gave 101 passed, and
`ruff` and `mypy` gave no finding. The whole lane was not run again after this
one edit of one test module.

The 37 skipped tests are the ones that the lane skipped before this change: 25
fixtures that are not of the layer a test reads, 10 that need a symbolic link
that this host does not permit, 1 that needs a signal that Windows does not
deliver, and 1 that a later pin supersedes. No test of
this change was skipped: `helm` and `bash` are installed.

[The Argo CD bootstrap page](../../environment/argocd-bootstrap.md) still says
that a test "fails when a second build file names Argo CD". That sentence was
already behind the list, which held four files. It is not edited here.

## Privacy and publicability

The diff was read for private material.

- The six cases are synthetic. Their node is named `node-a`, their provider is
  `synthetic`, and their commit is forty zeros. No cluster produced them.
- The committed reading holds the node's name, two addresses of the node inside
  the engine's network, pod addresses, image names, and the server version. Each
  names an object of the local cluster. None is a path of the workstation. The
  images that the node lists are images of this project and of the cluster.
- The transcript is what the script printed, with one line added that states
  the exit status.
- No credential, secret value, cloud account identifier, model artifact, or path
  of the workstation is in the diff.
- No planning text, prompt, or identifier of a later change is in the diff.

## What this does not establish

- **That a cluster can hold the release.** One reading is committed. It compares stated figures on one day, on a cluster that ran nothing of this project. The cases are synthetic.
- **That a pod of the release is scheduled, starts, or becomes Ready.** The gate
  compares stated figures.
- **That the reserve is enough.** It is a fixed figure.
- **Anything about memory or processor time in use.** The gate reads no usage.
- **That the release fits during a rollout.** A pod that is terminating is not
  counted.
- **That the footprint is the release a controller applies.** The gate does not
  compare its commit with the revision that the Application names.
- **Anything about a caller, a rollout, or the loss of a pod or a node.**
