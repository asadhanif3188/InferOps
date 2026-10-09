# V2-S4-004-PR1 validation

Status: **the Ready endpoint state of the API Service and the runtime Service can
be captured as one record, and chart `0.6.0` renders a PodDisruptionBudget for a
tier of two or more replicas. Both are checked at evidence level C0, against
synthetic collections and rendered files. No endpoint of a cluster was read, no release that
renders a budget was installed, no eviction was requested, and no pod was
deleted. No claim was registered.**

| Property | Value |
|---|---|
| Date | 2026-10-09 |
| Base | `70f6138`, the merge of pull request #131 |
| Branch | `feat/v2-s4-004-endpoint-pdb-signals` |
| Commits | `cdcfd62b`: the two templates, chart `0.6.0`, the tool, the collector, the cases, the suites, and the pages. `ded96a9c`: the corrections of the independent review, and the desired-state release recorded at the first commit. A third commit: the default lane |
| Host | One Windows workstation, Git Bash; Python 3.12.12 from `uv`; Helm `v3.19.0`; a kubeconform binary that reports `development` on this host. The workflow pins kubeconform `v0.8.0` |
| Evidence level | C0. Every check reads committed files, renders them with the chart tool, or executes a script against stand-ins for `kubectl` |
| Claim effect | None. No claim, ledger, register row, dashboard row, or evidence-index entry was added or changed |

## What changed

**The endpoint-state record.**

- [`scripts/environment/service-endpoint-state.sh`](../../../scripts/environment/service-endpoint-state.sh)
  reads the Services of the release and the EndpointSlices of its namespace,
  once, and writes one collection directory. Each of its kubectl calls is a
  `get`.
- [`tools/service_endpoint_state`](../../../tools/service_endpoint_state/__init__.py)
  reads a collection and prints one record: for each of the two tiers, the
  number of endpoints, the number that are Ready, and the pod name and pod UID of
  each. 10 rules decide whether the result is `OBSERVED` or `REFUSED`. The first
  commit held 9.
- Seven synthetic cases, of which the first commit held six, under `tests/domain/fixtures/service-endpoint-state/`, two
  suites, and [the page](../../environment/service-endpoint-state.md).

**The disruption budgets.**

- Two templates. Each renders one `policy/v1` PodDisruptionBudget with
  `minAvailable: 1` when its tier declares two or more replicas.
- Chart `0.6.0`. No value and no member of the values schema changed.
- One row of the ownership inventory, `workload-disruption-budget`, with the
  status `planned`.
- The Argo CD project admits PodDisruptionBudget, the removal step of the
  Application procedure asks for budgets, and ADR 0019 carries a dated
  amendment.
- One workflow step validates a two-replica render against the pinned
  Kubernetes schemas.
- [The page](../../environment/disruption-budgets.md), and a section of the chart's
  README.

**What followed from the chart version.** The renderer's chart version constant,
the three generated values files and their release documents, the comparison
record of the baseline profile, the V1 compatibility record with a dated
amendment, the released-pin table of the release suite, and the pages that
restate the chart version.

## What the change was asked to reach, and what it reached

| Asked | Reached |
|---|---|
| The Ready endpoint counts and identities of the API Service and the runtime Service are capturable | Reached as a tool and a collector, at C0. A record states the counts and the pod name and pod UID of each endpoint, for both tiers. The collector was executed against stand-ins for `kubectl`. It was not executed against an API server, so what a cluster returns to it was not observed |
| A budget keeps at least one replica available through a voluntary disruption, where supported | Reached as a render, with a stated limit: on a cluster with one node a budget makes a drain wait, and it does not make a drain leave a caller served. A tier of two or more replicas renders `minAvailable: 1` over its Deployment's selector. The pinned `policy/v1` schema accepts both objects. No API server admitted one, and no eviction was requested, so that an eviction is refused was not observed |
| The documents state that a budget does not establish resilience to a direct pod deletion | Reached. The disruption budgets page, the chart's README, both templates, the values comments, the inventory row, and the changelog each state it |
| The signals are bounded in cardinality and hold nothing that must not be published | Reached for these properties of the record, at C0. Whether one record of one cluster is fit to publish is decided for that record: it states pod names, pod UIDs, the provider, and a commit. Two tiers, three tier states, two results, and at most 32 pods for one Service. A record holds no address, no node name, and no kubeconfig context, and a test holds each. A pod name and a pod UID are record values and not label values. No metric was added |
| A Prometheus scrape `up` series is not used in place of endpoint or caller health | Reached. The tool reads no metric. A test holds that the chart's scrape jobs discover pods and not Services, and the page states what `up` says |

## Decisions taken in this change

1. **A budget is derived from the replica count, and no value configures it.** A
   value for `minAvailable` could be set to the replica count, which refuses
   every eviction. The chart has no such value, and the schema refuses one. The
   cost is that an operator cannot turn a budget off.
2. **One replica renders no budget.** A budget of one available pod over one pod
   refuses every eviction of it. So the runtime tier of the single-runtime
   baseline is not bounded for an eviction, and the two-replica release's is.
   That is one more rendered difference between the two, and it follows from the
   replica count.
3. **`unhealthyPodEvictionPolicy` is not stated.** The Kubernetes default
   applies. No accepted record decides it, and a test fails when one is stated.
4. **The chart version moved to `0.6.0`.** The chart renders a kind that it did
   not render. The chart label is on every pod template, so an upgrade to
   `0.6.0` replaces every pod of a release, also at one replica.
5. **The Argo CD project admits a ninth kind.** ADR 0019 D3 says "eight". Its
   rule is that the project admits the kinds that the release renders. The
   change keeps the rule, changes the number, and records it as a dated
   amendment to the accepted text.
6. **A record refuses an unstated `ready`.** Kubernetes documents that a consumer
   reads it as true. A tool that counts Ready endpoints for an experiment does
   not count a pod as Ready on an absent member.
7. **A record does not judge a count.** It states no expected count and no
   threshold. Zero Ready endpoints is `OBSERVED`. An experiment decides what a
   count means.
8. **One reading for one run of the collector.** The collector takes no series
   of samples. The function `observe` is the part that a sampler can call for
   each sample.
9. **The header names no kubeconfig context.** A context name can hold an
   account identifier.
10. **The budgets are rendered although a drain then waits on the one recorded
    environment.** A drain marks the node unschedulable. On a cluster with one
    node, and for two runtime pods on one `ReadWriteOnce` claim, the replacement
    of the first evicted pod cannot become Ready, and the budget refuses the
    second eviction. Without a budget such a drain ends, and the tier has no pod.
    With a budget it waits, and one pod stays. The review found this, and the
    first commit did not state it. The change keeps the budgets and states the
    limit. The other answer is to render no budget for the runtime tier while its
    claim is `ReadWriteOnce`.
11. **The Argo CD sync policy is not changed.** It does not prune, so a budget
    stays in a cluster when its tier goes back to one replica. The change states
    that and changes no policy.
12. **The first experiment's freeze record is not revised.** This change moves
    pinned inputs of freeze `r3`: the chart, the renderer, the desired-state
    release, the project manifest, and the Application procedure. `r3` is not
    edited, and no run was started.

## What was not done

- **No Service and no EndpointSlice of a cluster was read.** Two calls were made
  to the `docker-desktop` cluster on 2026-10-09, each `kubectl get namespaces`,
  which changes nothing. Each listed five namespaces: `default`,
  `kube-node-lease`, `kube-public`, `kube-system`, and `local-path-storage`.
  Neither `inferops-release` nor `argocd` was among them. No transcript of the
  calls is committed. Nothing was installed for this change.
- **No eviction, no drain, and no pod deletion.**
- **No timeline collector.** A record is one reading.
- **No metric, no alert, and no dashboard row.**
- **No claim.**

## Validation at the first commit

Each command ran on the tree of the first commit, before it was committed.

| Command | Result |
|---|---|
| `uv run --locked ruff check .` | No finding |
| `uv run --locked ruff format --check .` | No file to reformat |
| `uv run --locked python -m mypy` | No issue in 375 source files |
| `uv run --locked python -m pytest tests/domain/test_service_endpoint_state.py -q` | 99 passed |
| `uv run --locked python -m pytest tests/architecture/test_helm_chart.py tests/architecture/test_argocd_application.py tests/architecture/test_resource_ownership.py tests/architecture/test_service_endpoint_state_collector.py tests/architecture/test_cluster_lifecycle_safety.py tests/architecture/test_local_cluster_provider_contract.py -q` | 1,403 passed |
| `uv run --locked python -m pytest tests/testing -q` | 8,059 passed, 1 skipped, 1 failed. The failure was the link from the proof index to this record, which did not exist yet. The link suite passed after this record was written |
| `uv run --locked python -m pytest tests/domain tests/contracts -q` | 3,104 passed, 31 skipped, 5 failed. Three failures restated the digest of the regenerated fixture values, on the renderer page and in the drift suite. They were corrected, and those suites then passed. Two failures are in the provenance suite, which reads the release at the commit that `HEAD` names: before the first commit, that commit holds chart `0.5.0` |
| `helm template` of the real fixture with two replicas for each tier, piped to `kubeconform -strict -kubernetes-version 1.34.0` with the pinned schema location | 25 resources, 25 valid. Both PodDisruptionBudgets valid |
| `helm template` of the chart at the `v1.0.0` tag and of this tree, with the V1 values file | The renders differ in the ten lines of the two strategies and in the chart label. Neither holds a PodDisruptionBudget |
| `uv run --locked python -m tools.service_endpoint_state --check` | `PASSED: 6 committed collection(s), each record is what its collection gives` |
| `uv run --locked python -m tools.gitops_desired_state --check` | `OK       the tree holds the declared releases and nothing else` |
| `uv run --locked python -m tools.generated_release --check` | `OK       support-assistant-local-kind: both files are what the declared sources derive` |
| `uv run --locked python -m tools.baseline_profile --check` | `OK       the baseline differs from the target only at the permitted paths` |
| `uv run --locked python -m tools.capacity_preflight --check` | `PASSED: 7 committed collection(s), each record is what its collection gives` |
| `uv run --locked python -m tools.experiment_freeze --check` | `PASSED: 3 freeze record(s), every rule held` |
| `uv run --locked python -m tools.experiment_freeze --changes docs/proof/experiments/v2-e01/freeze-r3.v1alpha1.json` | 30 material files differ. The base held 25 |
| `git diff --check` against the base | No whitespace error |

`shellcheck` is not installed on this host, and no workflow runs it over
`scripts/`. So the new script was not linted. `bash -n` accepts it.

**The first commit broke one suite that was not run before it.**
`tests/architecture/test_argocd_bootstrap.py` holds that no file of the chart and
no tool but two names the GitOps controller. The chart's README and the new tool's
text each named it. The default lane would have reported this. The second commit
removes both names.

**The release names an earlier commit at the first commit.** The desired-state
release was regenerated for chart `0.6.0`, and its two revisions still name
`40803f2f`, where the renderer states chart `0.5.0`. That statement is false for
the first commit. The second commit records the first commit as both revisions,
which moves the release identifier to `b5457f49…` and no value.

**One defect of an existing test was corrected.** `test_each_tier_block_requires_a_rollout`
deleted the `rollout` block from a shallow copy of the chart's defaults, so it
removed the block from the defaults that every later test of the module reads.
No earlier test read the block after it. A new test did, and failed. The test now
deletes from a deep copy.

## What the independent review found

Three reviewers read the first commit. One read the tool and the collector, one
read the chart, the budgets, and the Argo CD files, and one read the documents
against the code. None found a record that states a Ready endpoint that its
collection does not hold. They found one wrong count, one design limit that no
page stated, and false or stale statements.

### What the tool got wrong

- **A slice that named no Service was left out of every count.** A slice with no
  labels, or without the service-name label, belonged to no tier. So a read that
  held two Ready endpoints in such a slice gave a tier that was `observed` with
  zero endpoints. The shape rule now refuses a slice that does not name its
  Service.
- **A Service with no slice was read as zero endpoints.** The first commit held a
  test that required this. A read with no slice of a Service states nothing: the
  slices can be not written yet. A tenth rule, `the-service-has-a-slice`, now
  refuses it, and a seventh case shows it. A slice with no endpoint is still a
  reading of zero.
- **Three inputs ended in an exception and no record.** Two Services with one
  name, and a read or a header nested too deeply to parse, each raised an error
  that the command did not catch. Each is now a refusal.
- **A list of another kind was read.** A `PodList` that held Service items was
  accepted. The shape rule now reads the kind of the list.
- **A finding contradicted its tier.** When one tier had no Service, the later
  rules were stated as not observed, with no tier named, while the other tier was
  `observed` under those rules. A finding now names the tier that its rule was
  not read for, and the tier that it is held for.
- **A docstring overstated the order of the rules.** It said that a rule is not
  evaluated after an earlier one is not held. That is so only for the Service
  rule.

Noted, and not changed: one pod UID in both tiers is accepted, and the collector
does not state why a read did not answer.

### What the budgets did not say

- **On a cluster with one node, a budget makes a drain wait without end.** The
  first commit said that a drain "evicts one, and waits for its replacement to be
  available before it evicts the other". On one node there is no place for the
  replacement. The two runtime pods also mount one `ReadWriteOnce` claim, so the
  same holds for them wherever they run. The page has a section for this, and the
  templates, the values comments, the chart's README, the changelog, and decision
  10 state it. The budgets are kept.
- **Under the Application, a budget outlives its tier's second replica.** The
  sync policy does not prune. The first commit said only that one replica renders
  no budget. The page and the Application page now state it.
- **The project must be applied before the revision.** The first commit said that
  Argo CD "refuses to sync a kind". A sync that holds a kind outside the project
  is expected to fail as a whole, so later revisions would not be applied either.
  The pages say so, and say that it was not observed.
- **How Argo CD reports a budget's health was not stated.** The source of the
  pinned version was read, and the page states what it holds.
- **The default of `unhealthyPodEvictionPolicy` was named, and its effect was
  not.** The page now states it.

### What the first commit said, and what is true

| The first commit said | What is true |
|---|---|
| The README: a budget "keeps one pod available through a voluntary eviction" | A budget makes the eviction API refuse a request. Nothing was observed. The sentence now states what Kubernetes documents |
| This record: "The workflow lints it", of the new script | No workflow runs `shellcheck` |
| This record: kubeconform `v0.8.0` | The binary on this host reports `development`. `v0.8.0` is the workflow's pin |
| This record and three pages: "no cluster was read", then "the one local cluster held no release" | Two `kubectl get namespaces` calls were made. They show that two namespaces were absent, and no more |
| The budgets page: a budget "admits one eviction" | At N replicas it admits N-1 |
| The budgets page: at any replica count, a replacement's load leaves one available pod | That is so at two replicas |
| The budgets page: a container killed for its memory limit and a failed probe are involuntary disruptions that Kubernetes documents | Kubernetes lists neither. Such a pod is not Ready, and is not counted as available |
| The values comment: a rolling update "does not use the eviction API", as documented | Kubernetes documents that a Deployment is not limited by a budget when it rolls pods |
| "A node drain uses that API" | `kubectl drain` does, unless it is told to delete |
| The endpoint-state page: a refused tier states null for each member | It states its Service when one Service carries the tier |
| The endpoint-state page: the suite holds the page's rule table | The suite holds that the page names each rule |
| Six pages and records outside the diff: the project admits "eight namespaced kinds" | Nine. Each present statement is corrected. The accepted text of two decision records is not changed |
| The inventory rows of the chart suite and of the Application suite | Each described the tests as they were before this change. Both are corrected |
| The baseline profile page and the desired-state page | Neither stated chart `0.6.0` or the budgets. Both do now |
| A test name: a budget "keeps one pod ... available" | The test reads a stated bound. It is renamed |

### Noted, and not changed

- A release name long enough to truncate gives the two Deployments, the two
  Services, and now the two budgets one name. The defect is older than this
  change, and no test covers it.
- The suite of the Application compares the project with eight rendered kinds
  and one named kind. Only the chart suite, which needs Helm, renders the
  desired-state release and compares its kinds with the project.
- The workflow validates the real profile with two replicas, and not the mock
  profile with two.

## Validation at the second commit

Each command ran on the tree of the second commit, before it was committed.

| Command | Result |
|---|---|
| `uv run --locked ruff check .` | No finding |
| `uv run --locked ruff format --check .` | No file to reformat |
| `uv run --locked python -m mypy` | No issue in 375 source files |
| `uv run --locked python -m pytest tests/domain/test_service_endpoint_state.py -q` | 110 passed. The first commit held 99 |
| `uv run --locked python -m tools.service_endpoint_state --check` | `PASSED: 7 committed collection(s), each record is what its collection gives` |
| `uv run --locked python -m tools.gitops_desired_state --check` | `OK       the tree holds the declared releases and nothing else` |
| `uv run --locked python -m tools.baseline_profile --check` | `OK       the baseline differs from the target only at the permitted paths` |
| `git diff --check` against the base | No whitespace error |

The default lane is recorded after the second commit, because two suites read the
commit that `HEAD` names.

## The default lane

The lane ran on the committed tree of the second commit, `ded96a9c`, with a clean
working tree.

| Command | Result |
|---|---|
| `uv run --locked python -m pytest -q` | 19,975 passed, 37 skipped, 14 deselected, 0 failed, in 49 minutes |

The lane holds the two provenance tests that failed before the first commit, and
the suite that the first commit broke. Both passed. The lane ran on one Windows
host. The skipped tests are the ones that this host cannot run, and the
deselected tests need a cluster or a model. The workflow did not run before the
push, so no hosted result is stated here.

## Privacy and publicability

The committed cases hold invented pod names, UIDs, and addresses. The changed
files hold no personal path, no credential, no account identifier, and no host
name. The diff against the base was read for each.

## What this does not establish

- That an API server admits either budget, or that an eviction is refused.
- That a caller is served when a pod of either tier is deleted, evicted, or
  replaced, or when a node is lost. A budget is not evidence for any of these.
- What a cluster returns to the collector, or how long its two reads take.
- That a Ready endpoint serves a request. A record is not a caller's result.
- Anything about a rollout. The rollout bounds are not changed.
