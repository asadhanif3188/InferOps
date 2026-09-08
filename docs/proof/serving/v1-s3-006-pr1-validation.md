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

Five things, and each answers one of the parent story's acceptance criteria for
this PR's boundary.

**The descriptor is the authority, and it cannot disagree with what already
decides it.** [`deploy/serving/certification/k8s-real-inference.v1.json`](../../../deploy/serving/certification/k8s-real-inference.v1.json)
holds the release target, the four readiness budgets, the request, the
assertions, the evidence location, and the cleanup policy. Loading it
cross-checks the runtime budget against the runtime package's startup budget, the
API budget against the composition's response budget, and the request budget
against the runtime profile — and refuses the descriptor rather than a run when
any of them disagrees. The architecture suite checks the rest against the chart
itself: the Service names, the Deployment names, the component labels, and the
published API port are read out of the committed render rather than guessed, and
the release name and namespace are compared with `lib.sh`.

**The workflow provisions the prerequisites and installs the release, and the
split of who owns what is deliberate.** [`scripts/environment/kubernetes-certification.sh`](../../../scripts/environment/kubernetes-certification.sh)
performs every cluster operation, through the `lib.sh` wrappers that pin the
kubeconfig and context and after the guard that establishes the reachable cluster
is this project's. [`tools/kubernetes_certification`](../../../tools/kubernetes_certification)
performs no cluster operation at all. The reason is written in both files: the
target-cluster guard already exists once, and a second implementation of it in
another language would be a second guard.

**Model readiness is measured rather than folded into an install.** `helm install`
is run **without** `--wait`, and the two rollouts are then waited on separately,
each against its own budget — the runtime's is the runtime package's startup
budget, which contains the model load. `--wait` would have produced one number
covering the install, the load, and the API start, and this story is about the
load.

**Two requests are made, because neither one establishes what the other does.**
The release's own `helm test` hook asks both Services for their health endpoints
from a pod **inside** the cluster, which is what establishes that cluster DNS
resolves the names and that the Services select something. The certified
completion is sent through a `kubectl port-forward` to the API Service, which
reaches a ready endpoint behind that Service and exercises the whole path to the
loaded model — and which does **not** traverse the Service's virtual IP and is
**not** covered by the release's NetworkPolicy. Both bounds are stated in
[the procedure document](../../serving/kubernetes-real-inference-certification.md)
rather than left to be discovered.

**Failure is bounded, and cleanup is scoped.** Every wait carries a timeout drawn
from the descriptor. A failure collects diagnostics into `.artifacts/`, leaves
the release installed for inspection, and says how to remove it. A success
uninstalls the release and asserts both halves: that nothing carrying the
release's instance label survived, and that the namespace did. The descriptor
refuses a cleanup policy that would remove the Terraform prerequisites or the
cluster, and the script contains no `terraform destroy`, no `kind delete`, and no
namespace deletion — which a test checks by reading it.

## What this change does not establish

- **That any of it works.** Whether the chart installs, whether the model loads
  inside the budget, whether a completion returns, and whether the teardown
  leaves no residue are runtime questions. A static reading of a workflow is not
  a substitute for running it.
- **That the workflow could be run today.** See the blocker below.
- **Anything about multiple replicas.** This PR certifies a single-replica
  release and refuses any other replica count rather than reporting a stronger
  result than it measured. Request distribution across replicas is out of this
  PR's boundary.
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
pulling it into this PR would have changed the boundary. What this change does is
make the workflow fail the way it should when the image is absent: bounded, at a
named stage, with diagnostics collected and a diagnostics record written.

## Commands and results

Run from the repository root on Windows 11 with Git Bash, Python 3.12,
`kubectl v1.36.1`, `helm v3.19.0`, and `Terraform v1.15.8` present. The container
engine was **not** running and `kind` was **not** on `PATH`, which is consistent
with every command below: none of them needs either.

### Python

```text
$ python -m ruff format --check .
296 files already formatted

$ python -m ruff check .
All checks passed!

$ python -m mypy
Success: no issues found in 158 source files

$ python -m pytest -q
6314 passed, 27 skipped, 14 deselected in 64.64s

$ python -m pytest tests/architecture/test_kubernetes_certification.py -q
120 passed in 1.32s
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

### The workflow's own offline validation

```text
$ bash scripts/environment/kubernetes-certification.sh check

[inferops] === Certification descriptor ===
certification inferops-c2-kubernetes-real-inference (C2; local-real-cpu)
lane          real-runtime; outside the default check lane
chart         charts/inferops-llm; profile real
release       inferops in inferops-release; 1 replica(s) of platform-api and serving-runtime
service       inferops-inferops-llm:8090, forwarded to 127.0.0.1
readiness     install 900000 ms; runtime 300000 ms; api 122000 ms; release test 300000 ms
request       POST /v1/chat/completions; identity GET /v1/models; budget 120000 ms
assertions    real adapter kind, pinned model revision, digest-pinned images, every
              replica ready, runtime-derived counts, non-empty content; mock identity refused
evidence      .cache/inferops/certification/k8s-real-inference.json; labelled local real
              Kubernetes; generated text never retained
cleanup       uninstalls the release; removes neither the Terraform prerequisites nor the cluster
execution     not started (offline certification validation only)
[inferops] the descriptor validated. Nothing was contacted and no release was installed.
```

Two lines are wrapped above for width; the command prints each on one line.

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

No finding is in a file this change adds or modifies. The pre-existing ones are
left alone rather than fixed here, because they are outside this PR's boundary.

### Not run, and why

| Check | Why |
|---|---|
| `bash scripts/environment/kubernetes-certification.sh certify` | Needs authorization, a running engine, a cluster, the model artifact, and an API image. None was present and none was requested |
| `terraform plan` / `apply` / `destroy` | Reaches a cluster. Not authorized by this change |
| `helm install` / `helm test` / `helm uninstall` | Same |
| `python -m pytest -m realruntime` / `-m cluster` | Capable-host lanes, deselected by default and not authorized |
| `gitleaks detect --config .gitleaks.toml` | Not installed on this host. The diff was scanned by hand for credentials, absolute host paths, planning-document content, and model artifacts; it carries none |

## Private-information inspection

The diff was read for anything that belongs to the private requirements
repository or to this contributor's machine: planning-document text, backlog or
roadmap material, positioning language, absolute filesystem paths, user names,
credentials, tokens, and model bytes. It carries none. Every path in the change
is repository-relative, every host-specific value the workflow needs is read at
run time from the cluster or from `lib.sh`, and the one file that records host
state — `.artifacts/kubernetes-certification/cluster-facts.json` — is written
into a directory version control ignores and is labelled host state rather than
evidence wherever it is mentioned.

## Acceptance criteria

For this PR's boundary:

| Criterion | Status |
|---|---|
| Workflow provisions prerequisites and installs Helm release | Implemented; **unexecuted**. The script applies the Terraform layer and installs the chart, refuses to install over an existing release, and never passes `--create-namespace` |
| It waits for actual model readiness | Implemented; **unexecuted**. Install runs without `--wait`; the runtime rollout is waited on separately against the runtime package's startup budget |
| A real model-generated response returns through Kubernetes Service | Implemented; **unexecuted and currently blocked**. The assertions exist and refuse a mock answer; no API image exists to install |
| Model/runtime/workload versions are recorded | Implemented; **unexecuted**. The record names the cluster and node image digest, the tool versions, the release revision and chart version, every workload's digest-pinned images, and the configured model identifier and revision |
| Failure is bounded and diagnostic | Implemented; **unexecuted**. Every wait has a timeout from the descriptor; a failure names its stage, collects diagnostics, and leaves the release in place |
| Evidence is labelled local real Kubernetes | Implemented. The label is fixed in the descriptor and refused if changed; the evidence class stays `local-real-cpu`, because a new class would have raised a ceiling by writing a string |

Deferred to `V1-S3-006-PR2`, and not implemented here: two-or-more-replica
deployment, per-replica readiness, proof that requests reach multiple replicas,
and the bounded failure handling that goes with it.

Parent-story status is unchanged: **not certified**. Certification needs an
authorized run, and an authorized run needs an API image.
