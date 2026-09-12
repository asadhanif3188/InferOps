# Sprint 3 completion review

Date: 2026-09-12

This record closes Sprint 3. It maps every Sprint 3 story and every amended exit
gate to the evidence that exists today, on the provider that produced it, and says
plainly where the evidence stops.

It is a reconciliation record. It publishes no new capability of its own: what it
adds is the judgement, and the judgement is only as good as the records it points
at.

## A. Scope

| Field | Value |
|---|---|
| Planning revision | `971e79e04beec4c2f96e7af52b44485e5585acb6` (private planning repository) |
| Implementation revision at branch point | `c702b984ffcdd6abacd20743699e3786b4ee846c` (`main`, the merge of `V1-S3-011-PR1`) |
| Branch | `test/v1-s3-011-lifecycle-cleanup-evidence-reconciliation` |
| Stories reviewed | `V1-S3-001` through `V1-S3-011` |
| PRs reviewed | every Sprint 3 PR, and in particular `V1-S3-010-PR1/PR2` and `V1-S3-011-PR1/PR2` |
| Executed provider | `docker-desktop` — the required V1 reference execution provider |
| Host | one Windows 11 machine, CPU only, no accelerator |

## B. Story matrix

| Story | Acceptance criterion | Evidence | Status | Limitation |
|---|---|---|---|---|
| **S3-001** | A local cluster is created and destroyed without residue | [cluster lifecycle](v1-s3-001-pr1-cluster-lifecycle.md) | **PASS, historical** | `kind` only, and its ownership assumption is superseded by S3-010. Kept as history, not rewritten |
| **S3-002** | Helm installs, upgrades, and uninstalls the release without manual manifests or residue | [paved road](v1-s3-011-pr1-docker-desktop-paved-road.md), [upgrade/rollback](v1-s3-011-pr2-upgrade-rollback.md), [scoped cleanup](v1-s3-011-pr2-scoped-cleanup.md) | **PASS** | `docker-desktop` only; one replica of each tier |
| **S3-003** | Model artifacts survive a pod restart on the Terraform-owned claim | [Kubernetes pod restart](../serving/v1-s3-003-pr2-kubernetes-pod-restart.md), with [the container-level measurement](../serving/v1-s3-003-pr1-restart-reload.md) beside it | **PASS** | One pod, deleted once. The claim's underlying storage durability is untested |
| **S3-004** | Kubernetes workload security defaults are explicit and rendered | [security validation](../security/v1-s3-004-pr1-validation.md), [NetworkPolicy enforcement](../security/v1-s3-004-pr1-network-policy-enforcement.md) | **PASS within documented local security limits** | NetworkPolicy objects are created and **not enforced**: the local plugin ignores them. No admission control exists |
| **S3-005** | Terraform provisions prerequisites, re-applies cleanly, and destroys safely | [paved road](v1-s3-011-pr1-docker-desktop-paved-road.md), [scoped cleanup](v1-s3-011-pr2-scoped-cleanup.md) | **PASS** | `docker-desktop` only; `rancher.io/local-path` storage only |
| **S3-006** | Real LLM inference through Kubernetes, single and multi replica | [paved road](v1-s3-011-pr1-docker-desktop-paved-road.md) | **PASS for single-replica C2; multi-replica correctly recorded as capacity-refused** | See §E. No multi-replica claim exists anywhere |
| **S3-007** | API and runtime telemetry is actually collected and correlated | [paved road](v1-s3-011-pr1-docker-desktop-paved-road.md), [telemetry during recovery](../telemetry/v1-s3-011-pr2-telemetry-during-recovery.md) | **PASS** | Collected into an `emptyDir` that goes with the collector pod. No dashboard, no alerting, no durable store |
| **S3-008** | A controlled upgrade fails, is detected, is rolled back, and real inference is restored | [upgrade/rollback](v1-s3-011-pr2-upgrade-rollback.md) | **PASS** | One injected fault; five attempts, four of which failed and are recorded |
| **S3-009** | Troubleshooting and cleanup are documented and consistent with what happened | [troubleshooting](../../environment/kubernetes-troubleshooting.md), reconciled in this PR | **PASS** | The commands have been executed; most individual symptoms remain derived rather than provoked, and the page says so |
| **S3-010** | Cluster lifecycle is external; both providers select explicitly and verify | [ADR 0011](../../architecture/decisions/ADR-0011-external-local-cluster-provider-contract.md), [provider contract](../../environment/local-cluster-provider-contract.md), [S3-010-PR1 validation](../architecture/v1-s3-010-pr1-validation.md) | **PASS** | Identity residual risks accepted as `EX-06` |
| **S3-011** | The whole paved road re-certified on the reference provider, with cleanup and reconciliation | all four records above, plus this one | **PASS** | Everything is `docker-desktop`'s |

## C. Exit-gate matrix

Every amended Sprint 3 exit-gate item, evaluated.

| # | Exit gate | Verdict | On what |
|---|---|---|---|
| 1 | Cluster lifecycle ownership is outside InferOps and documented consistently | **MET** | ADR 0011; no workflow creates, enables, resets, or deletes a cluster, and a test refuses a script that acquires the ability |
| 2 | `kind` and `docker-desktop` have explicit selection and safe verification | **MET** | Both guards exist, selection has no default, and every mutating workflow re-verifies before acting |
| 3 | Docker Desktop reference-provider verification is executed | **MET** | Verified at the start of every run in this PR, and again after the teardown |
| 4 | Real LLM inference works through local Kubernetes on the reference provider | **MET** | A real model-generated completion through the release's own Service |
| 5 | Single-replica serving is C2-certified on the reference provider | **MET** | `outcome: certified` |
| 6 | Multi-replica certified when capacity permits; otherwise the refusal is evidenced and no stronger claim is made | **MET — as a refusal** | See §E |
| 7 | Helm owns workloads and Terraform owns only in-cluster prerequisites | **MET** | `helm uninstall` left the namespace and claim; `terraform destroy` removed exactly those two |
| 8 | Probes represent model-load behaviour | **MET** | The runtime becomes ready only after the model loads; the `verify-model` init container gates the start |
| 9 | Security and resource defaults are explicit | **MET within local limits** | Rendered and applied; NetworkPolicy not enforced (gate 12 and §J) |
| 10 | Telemetry is actually collected on the reference provider | **MET** | A real Prometheus scraped both jobs and evaluated every accepted query, at rest and across a pod replacement |
| 11 | Upgrade/rollback and scoped cleanup workflows pass | **MET** | Both executed |
| 12 | Cleanup leaves the externally owned Kubernetes cluster intact | **MET** | See §H |
| 13 | Evidence records identify the provider and do not generalize across providers | **MET** | Every record names `docker-desktop`; the ownership rows cite the run that moved them |

## D. Provider boundary

Stated once, plainly, because everything above depends on it.

- **Docker Desktop is the executed V1 reference provider.** Every runtime result
  in Sprint 3's closure was produced on the Kubernetes cluster Docker Desktop
  provides, on one Windows host.
- **`kind` support is implemented separately.** Its verification guard, its
  image-preparation path, and its contract entry all exist and are unit- and
  architecture-tested. Its historical cluster-lifecycle and smoke evidence remains
  valid as the historical evidence it is.
- **Docker Desktop evidence does not certify `kind`.** No runtime certification
  has been re-executed on `kind` since the ownership realignment.
  [ADR 0011](../../architecture/decisions/ADR-0011-external-local-cluster-provider-contract.md)
  forbids borrowing one provider's answer for the other, and nothing in this PR
  does.
- **Cluster lifecycle is externally owned.** The operator provides the cluster.
  InferOps verifies it, consumes it, and owns only what the ownership inventory
  assigns to Terraform or Helm inside it.

`kind`'s status, in the vocabulary the story asks for:

| Aspect | `kind` |
|---|---|
| Provider verification | **implemented and tested** (unit, against fake tools) |
| Image preparation | **implemented and not executed** since the realignment |
| Cluster lifecycle | **historical evidence exists**; no longer a required workflow |
| Terraform apply / Helm install / certification / telemetry / upgrade-rollback / pod restart | **not executed** since the realignment |

## E. Multi-replica result

The capacity gate refused, before anything was installed:

```text
REFUSED multi-replica certification at stage capacity: this host cannot hold the
profile.
  uncommitted cluster memory: 8484278272 bytes available, 8657043456 bytes required.
```

Short by 172 765 184 bytes — about 165 MiB — held by workloads in another
namespace belonging to unrelated work that had been running for weeks before this
began.

**The gate itself succeeded.** It read the node's own allocatable memory minus
what was already requested on it, rather than the engine's total — which on this
host is the difference between passing and refusing — and it stopped the run
before it could install a profile the host could not hold.

**No multi-replica serving is claimed anywhere.** The gate was not weakened, the
replica count was not reduced to fit, and no unrelated workload was stopped to
make room. A certification of fewer replicas than the profile requests is not that
certification.

## F. S3-003 pod-restart result

One serving pod deleted; the Deployment replaced it.

| | before | after |
|---|---|---|
| Pod name | `…-runtime-75d47d6578-nfgxx` | `…-runtime-75d47d6578-vc7lk` |
| Pod UID | `4dca867e-…` | `e58792c0-…` |
| Claim / bound volume | `inferops-model-cache` / `pvc-646749a3-…` | the same |
| Artifact bytes / SHA-256 | 1 834 426 016 / `061b54da…` | the same |
| Artifact **inode / mtime** | `2118398` / `1789203832` | **the same** |
| `verify-model` init container | exit `0` | exit `0` |
| Real completion | HTTP 200, 53 tokens, adapter `real` | HTTP 200, 53 tokens, adapter `real` |

Acquisition Jobs before and after: **0 and 0**. Release revision before and after:
**1 and 1**. Readiness observed at zero and then above zero across five samples.

The inode and modification time are what separate "the same file survived" from
"an identical file was put back": a re-acquired artifact reproduces the byte count
and the digest, and cannot reproduce the file's identity.

Timings — `2 070` ms to a replacement pod, `14 533` ms to ready, `19 952` ms to a
served completion — are **one observation on one host** and are published as such.
They are not a restart benchmark.

## G. S3-008 rollback result

| Stage | Revision | Outcome |
|---|---:|---|
| baseline | 1 | healthy, release test passed |
| candidate | 2 | healthy, the change reached the workload (new ReplicaSet, new pod) |
| unhealthy-candidate | 3 | **failed** |
| rollback | 4 | healthy, restored revision 2 |

Detection: `init-container-nonzero-exit`, exit 1, on `serving-runtime`/`verify-model`
— the workload the fault was injected into — after `6 425` ms. A deadline was not
accepted as a detection.

Recovery: rollback `1 512` ms; detection to a served completion `7 983` ms. Real
inference afterwards: HTTP 200, adapter `real`, 35 tokens, pinned model revision.

Impact: 3 readiness probes across the failure window, **3 answered, 0 refused** —
the failing candidate never became ready, so the pod already serving kept serving.
That is a property of this fault, not of resilience.

**Four failed attempts preceded the passing one and are recorded, not hidden.**
They found: an acquisition hook that deleted a 1.83 GB artifact it could not
replace; a facts variable colliding with a `readonly` constant; a ConfigMap read by
label selector when the release has three; an impact sampler too slow for a fast
failure; and a residue check that raced the garbage collector. Each is fixed, and
four of the five now have a guard test.

## H. Cleanup result

| Question | Answer |
|---|---|
| Helm-owned objects after `helm uninstall` | **0**, by every kind, after 9 s |
| Helm releases in the namespace | **0** |
| Telemetry collector objects | **0** |
| Terraform-owned namespace and claim, before `terraform destroy` | **present** |
| Both, after `terraform destroy` | **gone** |
| Terraform state or plan artefacts tracked by git | **0** |
| Docker Desktop API server afterwards | responds, `v1.34.3` |
| Node afterwards | `desktop-control-plane`, **Ready** |
| Namespaces removed | **exactly one** — the one Terraform owns |
| Unrelated workloads | untouched, never stopped |
| Docker Desktop reset, disabled, or reconfigured | **no**, and no workflow can |

One piece of InferOps residue is named rather than tidied away:
`inferops-serving-feasibility`, from the Sprint 0 feasibility workflow, still
exists in the operator's cluster. Neither `helm uninstall` nor `terraform destroy`
owns it, so neither removes it; that it has no owning teardown in any committed
workflow is a real gap and is recorded as one in
[the cleanup record](v1-s3-011-pr2-scoped-cleanup.md).

## I. Test and verification results

Run from Git Bash at the repository root, on the branch head.

| Command | Result |
|---|---|
| `uv run --locked python -m pytest -q` | **7876 passed, 30 skipped, 14 deselected** |
| `uv run --locked python -m ruff check .` | **All checks passed** |
| `uv run --locked python -m ruff format --check .` | **clean** |
| `uv run --locked python -m mypy` | **no issues in 192 source files** |
| `git diff --check` | **clean** |
| `helm lint charts/inferops-llm` (both profiles) | **passed** |
| `helm template` against both committed value files | **renders; matches the committed renders byte for byte** |
| `terraform fmt -check -recursive` / `terraform validate` | **passed** |
| `bash -n` on every environment script | **passed** |
| `kubeconform -strict -kubernetes-version 1.34.0` on both committed renders | **mock: 9 valid, 0 invalid; real: 23 valid, 0 invalid** |
| `promtool check config`, run from the pinned collector image over the committed render | **passed**, as `test_the_pinned_collector_loads_the_configuration_the_chart_writes` |

The real-runtime and Kubernetes workflows are outside the default lane by design
and were run explicitly, under authorization, against the reference provider. Each
one's exact command is in its own record.

**The one tool that could not be run, and why:** `shellcheck` is **not installed
on this host**. The shell scripts were syntax-checked with `bash -n`, held to the
architecture suite's rules about wrappers, selectors, deletes and budgets, and
reviewed — but they were not linted, and that is not the same thing.
`shellcheck` is not reported as passed.

`promtool` is not on the host either, and that is deliberate rather than a gap:
the check runs it **from the collector image the chart pins**, so the binary is
the one the collector actually runs rather than whatever a host happens to have.
It establishes that the configuration loads and the recording rules parse, and
nothing about whether a target was discovered.

## J. Remaining limitations

1. **One Windows host.** Nothing here has run on Linux or macOS.
2. **One provider for every runtime result.** `docker-desktop`. `kind` runtime
   certification has **not** been re-executed under the provider model.
3. **CPU only. No GPU evidence of any kind.**
4. **Multi-replica serving is not certified.** The capacity gate refused.
5. **NetworkPolicy is rendered and created, not enforced.** The local network
   plugin ignores it; no admission control exists. `DR-04`, `DR-05`, `EX-05`.
6. **No production HA.** One replica of each tier, one node, no anti-affinity, no
   disruption budget.
7. **No production network exposure.** ClusterIP only, no Ingress, no load
   balancer, no TLS, no authentication, no authorization. Every host-side call is
   a loopback port-forward.
8. **No general performance or capacity claim.** Every timing published is a
   single observation on one host. No throughput, latency distribution, or
   concurrency figure exists.
9. **Provider identity residual risks are accepted, not closed.** A `kind` cluster
   an operator named `desktop`, reached through a context named `docker-desktop`,
   passes the Docker Desktop guard; and "this machine's engine" is really "the
   engine this CLI is configured to reach". Both are `EX-06`.
10. **Telemetry is not durable and not actionable.** The collector's series live in
    an `emptyDir` and go with its pod. No dashboard, no alerting rule, no receiver,
    no runbook link.
11. **Telemetry did not detect the failure.** No expression went to zero or to an
    error state when the serving pod was deleted; `up` means "the scrape
    succeeded", not "the workload is ready". The detection in the rollback
    experiment came from the Kubernetes API, not from a metric.
12. **No CI service is selected.** Every gate above was run by hand. `V1-S4-001`
    is where that would change.
13. **Storage durability is untested.** The claim survived a pod replacement on
    `rancher.io/local-path`; nothing says what survives a host failure, another
    provisioner, or a Docker Desktop reset — and what a reset reclaims is still
    unknown.
14. **Two contract-level rows remain `planned`** — `workload-contract-document`
    and `workload-secret-material` — because they are supplied out of band by a
    workload owner and no workload owner exists.

## K. Final verdict

Every Sprint 3 story has an acceptance criterion backed by an executed record on
the reference provider, every amended exit-gate item is met, the repository's
public claims have been reconciled to what those records actually say, and the
limitations above are published rather than implied.

```text
Sprint 3: PASS
```

The PASS is bounded by §D and §J and by nothing else. It is a PASS for the
`docker-desktop` provider, on one host, at single-replica, with the limitations
named — not a claim that InferOps is a portable production Kubernetes platform.

Sprint 4 has not been started.
