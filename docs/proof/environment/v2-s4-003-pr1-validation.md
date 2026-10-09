# V2-S4-003-PR1 validation

Status: **the capacity gate for the two-replica release is implemented, and
synthetic cases show one acceptance and each kind of refusal. This is evidence at
C0.** No chart file, contract, binding, Terraform file, Application, or freeze
record was changed, and no claim was registered. The controlled baseline profile
with one serving runtime replica is not in this change.

| Property | Value |
|---|---|
| Date | 2026-10-09 |
| Base | `e515776cfb6ebf6ca97085f5d0da8b6af6524dcb`, the merge of pull request #129 |
| Branch | `feat/v2-s4-003-capacity-preflight` |
| Host | One Windows workstation, Git Bash (GNU bash 5.2.26); Python 3.12.12 from `uv` 0.9.16; Helm `v3.19.0`; Docker engine `29.8.1`; `kubectl` client `v1.36.1` |
| Evidence level | C0 for the two suites and the six synthetic cases |
| Claim effect | None. No claim, ledger, register row, dashboard row, or evidence-index entry was added or changed |

## What changed

- `tools/capacity_preflight` is new. It reads one collection directory and prints
  one record, whose result is `ACCEPTED` or `REFUSED`. It reads files and contacts
  no cluster. [The capacity preflight page](../../environment/capacity-preflight.md)
  describes the footprint, the collection, the units, the 12 rules, and what a
  record does not establish.
- `scripts/environment/capacity-preflight.sh` is new. It verifies the selected
  target, writes the declared footprint, reads the cluster, and writes one
  collection under `.artifacts/`. Each of its cluster calls is a `kubectl get` or a
  `kubectl version`. It exits 0 for an acceptance, 5 for a refusal, and 1 when no
  record was written.
- `tests/domain/fixtures/capacity-preflight/` holds six synthetic collections,
  each with its record: one acceptance, two refusals as `insufficient`, and three
  refusals as `ambiguous`.
- `tests/domain/test_capacity_preflight.py` and
  `tests/architecture/test_capacity_preflight_collector.py` are new.
- The script is added to three tables of two existing suites: the entry points,
  the read-only scripts, and the platform workflows.
- Seven pages state the gate: `README.md`, `CONTRIBUTING.md`, `CHANGELOG.md`, the
  chart's README, the architecture index, the system architecture, and the Git
  desired-state page. The model cache observation page gains one dated note. The
  test inventory gains two modules.

## What the change was asked to reach, and what it reached

| Asked | Reached |
|---|---|
| The preflight records allocatable resources, reservations, footprint, requests, and rollout headroom | Reached. A record states the node's allocatable and capacity figures, the requests of the unfinished pods by namespace, the footprint with the requests and the memory limit of each container, the surge pods as rollout headroom, and each comparison with its unit |
| Insufficient capacity is refused and the gate is not weakened | Reached at C0. Each figure is refused one unit below the requirement. A stored footprint with a lowered reserve, requirement, pod figure, or headroom is not a collection. A footprint for fewer replicas is refused by the command |
| An ambiguous environment is refused before a mutation | Reached at C0. Eight rules refuse as `ambiguous`, and a read that was not made refuses. The script makes no call that changes the cluster |
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
4. **Rollout headroom is the surge pods of each Deployment.** The API surges by
   one pod and the runtime by none, as the chart states. The collector's
   Deployment states no strategy, so the gate uses the default that the Kubernetes
   documentation states: one pod.
5. **The hook pod and the test pod are counted beside the surge pods.** That sum
   is an upper bound. Whether those pods exist at one time was not observed.
6. **The gate decides for one schedulable node.** More than one is refused as
   ambiguous, because the model cache claim is `ReadWriteOnce` and the gate places
   no pod among nodes.
7. **A pod that states no request is counted as zero.** The sum is a sum of
   stated requests. The record states how many such pods it counted.
8. **A release that is already installed is refused.** Its pods are in the node's
   figures, and the gate would count the release two times.
9. **The model cache rule is not required.** The gate can run before the
   prerequisite layer creates the claim. A claim that exists and is smaller than
   the artifact refuses.
10. **The engine minimum of V1 is not a rule here.** The engine's figures are
    stated in the record. For memory, a node that this gate accepts allocates more
    than the V1 engine minimum. **For the processor it can allocate less**: the
    gate requires 3,110 millicores that no counted pod requests, and V1 requires 4
    engine processors.
11. **The tool reads the Application, and it imports no release declaration.**
    The repository's boundary check refuses a script that names a tool which
    reaches the render package. The collector is a script, so the tool it calls
    holds its own table of Applications. A test compares that table with the
    declared desired state.
12. **The command compares the stored footprint with the committed files.** The
    record of a collection is built from the footprint that the collection stores.
    Without the comparison, a collection written for fewer replicas would give an
    acceptance for another release.

## Two readings during development that are not recorded

The collector was run two times against the local `docker-desktop` cluster while
it was written. Each run was made from a working tree that was not a commit, so
neither directory is committed and neither is a record of this repository. They
are stated here because they were made.

- **The first run made no read.** The script could not read the commit of the
  working tree: it gave `git` a POSIX path that the Windows `git` did not
  resolve. The script was corrected to change directory first.
- **The second run printed `ACCEPTED`.** The cluster held one node, nine pods of
  its control plane, no Argo CD installation, and no release. The node allocated
  12,000 millicores and 10,430,672,896 bytes. The nine pods requested 950
  millicores and 304,087,040 bytes. The gate required 3,110 millicores and
  9,865,003,008 bytes of memory limits, and 10,126,585,856 bytes were available:
  261,582,848 bytes more than required. The model cache claim did not exist, so
  its rule was `not-observed`.

**This is not a qualification of that host.** It is one reading of a cluster that
ran nothing of this project. It states that the stated figures fit on that day.
It does not establish that two runtime pods start there, and Argo CD, which a
reconciled release needs, states no request and would be counted as zero.

## Validation at the first commit

Each command ran on the host of the table above, from the working tree that the
first commit holds.

| Command | Result |
|---|---|
| `uv run --locked ruff check .` | No finding |
| `uv run --locked ruff format --check .` | No file to reformat |
| `uv run --locked python -m mypy` | No issue in 366 source files |
| `uv run --locked python -m pytest tests/domain/test_capacity_preflight.py -q` | 227 passed. The comparison with a render ran: `helm` is installed |
| `uv run --locked python -m pytest tests/architecture/test_capacity_preflight_collector.py -q` | 21 passed. `bash` is installed |
| `uv run --locked python -m pytest tests/architecture/test_cluster_lifecycle_safety.py tests/architecture/test_local_cluster_provider_contract.py -q` | 416 passed |
| `uv run --locked python -m pytest tests/testing tests/domain/test_renderer_input_boundary.py -q` | 8,182 passed, 1 skipped. The boundary suite alone gave 154 passed |
| `uv run --locked python -m tools.capacity_preflight --check` | `PASSED: 6 committed collection(s)` |
| `bash -n scripts/environment/capacity-preflight.sh` | No syntax error |
| `git diff --check` against the base | No whitespace error |

**Not run at the first commit.** The whole default lane had not finished when the
first commit was made. `shellcheck` is not installed on this host, so the script
was not linted here. `gitleaks` is not installed on this host. Hosted CI was not
read: no pull request existed.

## Privacy and publicability

The diff was read for private material.

- The six cases are synthetic. Their node is named `node-a`, their provider is
  `synthetic`, and their commit is forty zeros. No cluster produced them.
- No credential, secret value, cloud account identifier, model artifact, or path
  of the workstation is in the diff.
- No planning text, prompt, or identifier of a later change is in the diff.

## What this does not establish

- **That a cluster can hold the release.** No reading of a cluster is recorded.
  The cases are synthetic.
- **That a pod of the release is scheduled, starts, or becomes Ready.** The gate
  compares stated figures.
- **That the reserve is enough.** It is a fixed figure.
- **Anything about memory or processor time in use.** The gate reads no usage.
- **That the collector works on a provider.** The executed tests use stubs.
- **Anything about a caller, a rollout, or the loss of a pod or a node.**
