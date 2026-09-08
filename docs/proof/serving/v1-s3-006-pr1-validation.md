# V1-S3-006-PR1 validation — real Kubernetes inference certification

Change: the workflow that certifies real inference through Kubernetes exists. A
committed descriptor fixes every budget, target, and assertion; a shell script
applies the Terraform prerequisites, installs the chart, waits separately for
measured model readiness and API readiness, runs the release's own in-cluster
connection test, opens a bounded loopback forward, and tears the release down; a
Python tool asserts over what the release answered and writes a machine-readable
record labelled `local real Kubernetes`. This record is what was run, what it
found, and what it does not support.

**Evidence class.** Everything asserted here is `local-static`: files read,
compared, formatted, linted, type-checked, and driven through injected HTTP and
clock seams. **Nothing has been installed.** No cluster was contacted, no
`terraform apply` ran, no Helm release was installed, no forward was opened, no
model byte was read, and no completion was generated. **No `C2` Kubernetes record
exists**, and the claim `the-selected-runtime-serves-a-real-completion-in-a-cluster`
keeps the evidence it already had rather than gaining any from this change.

## What the change is

**The descriptor is the authority, and it cannot disagree with what already
decides it.** [`deploy/serving/certification/k8s-real-inference.v1.json`](../../../deploy/serving/certification/k8s-real-inference.v1.json)
holds the cluster and release targets, the model cache expectations, eight
readiness budgets, the request, the assertions, the evidence location, and the
cleanup policy. Loading it cross-checks the runtime profile's request budget and
the internal relations between the budgets, and refuses the descriptor rather than
a run when any of them disagrees. The architecture suite checks the rest against
the records that own them: the Service, Deployment, and ConfigMap names and the
component labels against the committed render; the API port, the replica count,
and all four readiness budgets against `values.yaml`; the claim name against the
values fixture and the Terraform variable; the cluster name, context, and node
image digest against `lib.sh`.

**The workflow provisions the prerequisites and installs the release, and the
split of who owns what is deliberate.** [`scripts/environment/kubernetes-certification.sh`](../../../scripts/environment/kubernetes-certification.sh)
performs every cluster operation, through the `lib.sh` wrappers that pin the
kubeconfig and context and after the guard that establishes the reachable cluster
is this project's. [`tools/kubernetes_certification`](../../../tools/kubernetes_certification)
performs no cluster operation at all. The target-cluster guard already exists
once, and a second implementation of it in another language would be a second
guard.

**Model readiness is measured rather than folded into an install.** `helm install`
runs **without** `--wait`, and the two rollouts are then waited on separately,
each against the chart's own progress deadline for that Deployment.

**Two requests are made, because neither one establishes what the other does.**
`helm test` asks both Services for their health endpoints from a pod inside the
cluster, which establishes that cluster DNS resolves the names and that the
Services select something. The certified completion is sent through a
`kubectl port-forward`, which reaches a ready endpoint behind the Service and
exercises the whole path to the loaded model — and which does **not** traverse the
Service's virtual IP and is **not** covered by the release's NetworkPolicy. Both
bounds are stated in
[the procedure](../../serving/kubernetes-real-inference-certification.md).

**Failure is bounded, and cleanup is scoped.** Every wait carries a timeout drawn
from the descriptor. A failure collects diagnostics into `.artifacts/`, leaves the
release installed for inspection, and says how to remove it. A success uninstalls
the release and then asks the cluster four questions: that nothing carrying the
release's instance label survived, claims included; that Helm reports no such
release; that the namespace survived; and that the claim count matches the one
taken before the install.

## Independent review, and what it found

An independent review ran before the second commit: three reviewers, on
correctness, on safety and information leakage, and on architecture and scope.
The safety review found no critical or high finding and confirmed the guard
ordering, the absence of an injection path, the loopback-only forward, and that
no document overclaimed. The other two found **nine defects worth fixing**, and
all nine are fixed in this change. They are recorded here rather than quietly
corrected, because a review that finds nothing is usually a review nobody did.

### The workflow could not have completed

1. **`kubectl version -o jsonpath=...` is not a valid invocation.** `kubectl
   version` accepts only `yaml` and `json` for `--output` and refuses `jsonpath`
   outright — verified by running it: `error: --output must be 'yaml' or 'json'`,
   exit 1. The failure would have landed at the *last* step before the inference
   request, after the Terraform apply, the install, the model load, and the
   in-cluster test had all already happened. Now read from `-o json` and parsed.

2. **`helm list -o json` reports a release revision as a string.** The reader
   demanded an `int`, so a real run would have failed at the `readiness` stage for
   a reason that had nothing to do with readiness. The reader now accepts a digit
   string and refuses a float, a boolean, or a non-numeric string.

Neither defect was reachable by reading either file alone: both halves looked
right and disagreed. So the script's embedded JSON writer is now **extracted by
the test suite and executed** against a representative environment — including a
realistic `helm list -o json` array with a string revision — and its output is fed
to the reader that consumes it.

### The pre-registered threshold was wrong

3. **The runtime readiness budget was pinned to the adapter's, not the chart's.**
   `startupBudgetMs` (300,000 ms) is how long the *adapter* waits for a runtime it
   started itself. The chart budgets the kubelet's startup probe at 600,000 ms and
   the rollout at 900,000 ms, and says why in its own comments: V1-S2-005 recorded
   a **358,735 ms cold load**, and "a probe budgeted at 300,000 ms would have
   killed the container mid-load". The workflow would have reported a normal cold
   load as a failure — the precise defect its own install-budget guard claimed to
   prevent. The budgets are now the chart's, a test compares each against
   `values.yaml`, and another asserts the slowest recorded load fits inside the
   budget.

4. **The API readiness budget was pinned to an unrelated quantity** — the
   composition's HTTP *response* budget, used as a *rollout* timeout. Now the
   chart's `api.probes.startup.budgetMs` and `progressDeadlineSeconds`.

### A record could have described something it did not establish

5. **The facts file path was an argument.** `--base-url` was guarded and
   `--cluster-facts` was not, while the entire cluster half of the record is
   copied out of that file. The flag is removed: the location is the descriptor's.

6. **`requiresVerifiedModelCache` was a boolean nothing enforced.** The chart
   permits `verifyOnStart: sha256 | size | none` under the real profile and the
   operator supplies the values file, so a release installed with `none` would
   load whatever bytes the claim held — while the record's provenance named a
   SHA-256. The run now reads the rendered init container's own command from the
   cluster and refuses unless the pinned digest appears in it, and the provenance
   names the hash beside the flag saying the run compared it.

7. **The node image digest was recorded and never compared** to the pin in
   `lib.sh`, which states the rule directly: "a pin checked one way at creation
   and another way afterwards is two pins." Now compared.

8. **Two facts were the descriptor round-tripped through a file.** The component
   labels were copied from the descriptor into the facts and then compared with
   the descriptor, so the check could not fail. They are now queried from the
   cluster, and a test installs a relabelled Deployment into the facts to show the
   check fails.

### Weaker than the procedure it sits beside

9. **Cleanup asserted half of what the descriptor claimed.** `helm-lifecycle.sh`
   counts claims before and after and includes `pvc` in its residue selector; this
   workflow — the one that writes the C2 record — did neither, and also skipped
   the post-uninstall `helm status` check. All three are now present.

Two further findings were fixed as hardening rather than defects: the script now
traps `INT` and `TERM` as well as `EXIT` (it leaves a background forward and a
real release behind, and Git Bash signal delivery to a native child is less
predictable than on Linux), and every descriptor value reaching shell arithmetic
or a port argument is checked at the point of use rather than relying on a
different program having run first.

One defect was introduced *while* fixing the others and caught before commit: the
descriptor field list and the positional `read` block fell out of alignment by
three entries, which silently shifts every value after the gap. The numeric guard
caught it at runtime; a test now compares the two lists directly, because a
positional read is a silent corruption waiting for an edit.

## What this change does not establish

- **That any of it works.** Whether the chart installs, whether the model loads
  inside its budget, whether a completion returns, and whether the teardown leaves
  no residue are runtime questions. A static reading of a workflow is not a
  substitute for running it — and this change is the second time that has been
  demonstrated concretely.
- **That the workflow could be run today.** See the blocker below.
- **Anything about multiple replicas.** This PR certifies a single-replica release
  and refuses any other replica count rather than reporting a stronger result than
  it measured.
- **That the NetworkPolicy protects the forwarded request.** It does not name it,
  and the accepted local CNI enforces no policy at all.

## The blocker: no InferOps API image is published

An authorized run would stop at the `release` stage with an image pull failure.
`platform-api-container-image` is `planned` in
[the ownership inventory](../../architecture/resource-ownership.md), no Dockerfile
is committed anywhere in this repository, and the API digest in
[`ci/real-values.yaml`](../../../charts/inferops-llm/ci/real-values.yaml) is a
documented placeholder that exists only so the chart's refusal of an unpinned
image has something to accept in a render fixture.

This is reported rather than worked around. Building and publishing an API image
is a different piece of work, owned by `contributor-host` in the inventory, and
pulling it into this PR would have changed the boundary.

## Commands and results

Run from the repository root on Windows 11 with Git Bash, Python 3.12,
`kubectl v1.36.1`, `helm v3.19.0`, and `Terraform v1.15.8` present. The container
engine was **not** running and `kind` was **not** on `PATH`, which is consistent
with every command below: none of them needs either.

### Python

```text
$ python -m ruff format --check .
297 files already formatted

$ python -m ruff check .
All checks passed!

$ python -m mypy
Success: no issues found in 158 source files

$ python -m pytest -q
6358 passed, 27 skipped, 14 deselected in 34.05s

$ python -m pytest tests/architecture/test_kubernetes_certification.py -q
163 passed in 2.40s
```

The 14 deselected are the `cluster`, `realruntime`, `failure`, and `load` lanes,
which the default marker expression excludes. Nothing in this change is in them.

### Shell

```text
$ bash -n scripts/environment/*.sh scripts/security/*.sh
(no output)

$ shellcheck -x -S style scripts/environment/*.sh scripts/security/*.sh
SC1091 (info) x3 in scripts/security/*.sh: not following ./lib.sh
```

The three findings are pre-existing, are in files this change does not touch, and
are the analyser declining to follow a dynamically composed `source` path. Every
script under `scripts/environment/`, including the new one, is clean at style
level. `shellcheck` is not vendored; it was run through
`uv tool run --from shellcheck-py shellcheck`.

### Establishing one of the two blocking defects

```text
$ kubectl version --client -o 'jsonpath={.clientVersion.gitVersion}'
error: --output must be 'yaml' or 'json'
(exit 1)
```

This is the whole of finding 1, reproduced against the installed client. The
second blocking defect was established from Helm's published output shape and is
now covered by the round-trip test rather than by argument.

### The workflow's own offline validation

```text
$ bash scripts/environment/kubernetes-certification.sh check

[inferops] === Certification descriptor ===
certification inferops-c2-kubernetes-real-inference (C2; local-real-cpu)
lane          real-runtime; outside the default check lane
chart         charts/inferops-llm; profile real
release       inferops in inferops-release; 1 replica(s) of platform-api and serving-runtime
service       inferops-inferops-llm:8090, forwarded to 127.0.0.1
readiness     install 120000 ms; runtime startup 600000 ms within a 900000 ms rollout;
              api startup 60000 ms within a 300000 ms rollout; release test 300000 ms
request       POST /v1/chat/completions; identity GET /v1/models; budget 120000 ms
model cache   claim inferops-model-cache, mounted read-only, verified by the
              'verify-model' init container
cluster       inferops-dev on the pinned node image sha256:02722c2ded...
assertions    real adapter kind, pinned model revision, digest-pinned images, pinned
              node image, every replica ready, artifact hash compared in cluster,
              runtime-derived counts, non-empty content; mock identity refused
evidence      .cache/inferops/certification/k8s-real-inference.json; labelled local
              real Kubernetes; generated text never retained
cleanup       uninstalls the release; removes neither the Terraform prerequisites nor
              the cluster
execution     not started (offline certification validation only)
[inferops] the descriptor validated. Nothing was contacted and no release was installed.
```

Several lines are wrapped above for width and the node digest is abbreviated; the
command prints each on one line and in full.

### Documentation and diff

```text
$ git diff --check
(no output)

$ git ls-files -z '*.md' | xargs -0 grep -n '[[:blank:]]$'
12 pre-existing matches, all in docs/proof/serving/v1-s1-002-pr1-cumulative-review-fixes.md

$ git ls-files -z '*.md' | xargs -0 grep -n "$(printf '\t')"
(no output)

$ (the relative-link scan published in CONTRIBUTING.md)
4 pre-existing findings, all in files this change does not touch
```

No finding is in a file this change adds or modifies.

### Not run, and why

| Check | Why |
|---|---|
| `bash scripts/environment/kubernetes-certification.sh certify` | Needs authorization, a running engine, a cluster, the model artifact, and an API image. None was present and none was requested |
| `terraform plan` / `apply` / `destroy` | Reaches a cluster. Not authorized by this change |
| `helm install` / `helm test` / `helm uninstall` | Same |
| `python -m pytest -m realruntime` / `-m cluster` | Capable-host lanes, deselected by default and not authorized |
| `gitleaks detect --config .gitleaks.toml` | Not installed on this host. The diff was scanned by hand for credentials, absolute host paths, planning-document content, and model artifacts; it carries none |

## Private-information inspection

The diff was read for anything belonging to the private requirements repository or
to this contributor's machine: planning-document text, backlog or roadmap
material, positioning language, absolute filesystem paths, user names,
credentials, tokens, and model bytes. It carries none. Every path in the change is
repository-relative, every host-specific value the workflow needs is read at run
time from the cluster or from `lib.sh`, and the one file that records host state —
`.artifacts/kubernetes-certification/cluster-facts.json` — is written into a
directory version control ignores and is labelled host state rather than evidence
wherever it is mentioned. The record's own field set is fixed and carries no node
name, kubeconfig path, user, or host directory.

## Acceptance criteria

For this PR's boundary:

| Criterion | Status |
|---|---|
| Workflow provisions prerequisites and installs Helm release | Implemented; **unexecuted**. Applies the Terraform layer, refuses to install over an existing release, never passes `--create-namespace` |
| It waits for actual model readiness | Implemented; **unexecuted**. Install runs without `--wait`; the runtime rollout is waited on separately against the chart's own progress deadline |
| A real model-generated response returns through Kubernetes Service | Implemented; **unexecuted and currently blocked**. The assertions exist and refuse a mock answer; no API image exists to install |
| Model/runtime/workload versions are recorded | Implemented; **unexecuted**. The record names the cluster and node image digest, the tool versions, the release revision and chart version, every workload's digest-pinned images, the model cache mounting, and the configured model identifier and revision |
| Failure is bounded and diagnostic | Implemented; **unexecuted**. Every wait has a timeout from the descriptor; a failure names its stage, collects diagnostics, and leaves the release in place |
| Evidence is labelled local real Kubernetes | Implemented. The label is fixed in the descriptor, refused if changed, and now registered in the vocabularies [CONTRIBUTING](../../../CONTRIBUTING.md) and [the mock and real boundary](../../serving/mock-and-real-boundary.md) publish. The evidence class stays `local-real-cpu` |

Deferred to `V1-S3-006-PR2`, and not implemented here: two-or-more-replica
deployment, per-replica readiness, proof that requests reach multiple replicas,
and the bounded failure handling that goes with it.

Parent-story status is unchanged: **not certified**. Certification needs an
authorized run, and an authorized run needs an API image.
