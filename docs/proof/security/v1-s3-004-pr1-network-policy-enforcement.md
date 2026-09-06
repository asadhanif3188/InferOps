# V1-S3-004-PR1 raw result — is a NetworkPolicy enforced?

Executed 2026-09-06. This is the experiment `DR-04` has named since it was
written: install a default-deny and find out whether traffic is actually refused.

**The answer is no.** A `NetworkPolicy` denying all ingress and all egress was
applied, and pod-to-pod traffic, DNS resolution, and a direct query to CoreDNS
all continued to work. `kindnetd` — the network plugin a `kind` cluster ships —
does not enforce NetworkPolicy in the build tested, and runs with no feature gate
that would ask it to.

The four policy objects [the chart renders](../../../charts/inferops-llm/templates/networkpolicy.yaml)
are therefore **inert** on this plugin. They are correct, they validate, and
nothing applies them.

## Evidence class, and the cluster this was not run on

`local-real`, on a real cluster, on one host, on one day. It is **not the accepted
cluster**, and the difference is stated before the results rather than after them.

| | Accepted ([ADR 0001](../../architecture/decisions/ADR-0001-local-development-environment.md) D2) | What this ran on |
|---|---|---|
| Provisioner | `kind`, cluster `inferops-dev` | Docker Desktop's Kubernetes |
| Node image | `kindest/node:v1.34.8@sha256:02722c2d…` | `desktop-control-plane`, Debian 12, not the pinned image |
| Kubernetes | 1.34 | v1.34.3 |
| Container runtime | — | containerd 2.2.0 |
| Network plugin | `kindnetd` (kind's default) | `kindest/kindnetd:v20251212-v0.29.0-alpha-105-g20ccfc88` |
| Docker | — | 29.7.2 |

**What transfers.** The network plugin is the same implementation. Docker
Desktop provisions its Kubernetes the same way `kind` does — the node is named
`desktop-control-plane` and the CNI DaemonSet is `kindest/kindnetd` — so a
finding about whether kindnetd enforces a policy is a finding about the plugin
the accepted cluster also runs.

**What does not transfer.** This is a different cluster, a different node image,
and a specific kindnetd build. A kindnetd release that enabled policy enforcement
by default, or an `inferops-dev` cluster configured with the feature gate set,
would behave differently and this record would not cover it. The experiment was
run here because `kind` is not installed on this host, and substituting a cluster
is a substitution rather than an equivalence.

## Procedure

Namespace `inferops-np-probe`, two BusyBox pods pinned to the digest this
repository already pins, one serving `httpd` on 8080 and one idle. Every command
named `--context docker-desktop` explicitly; no other context was touched.

Traffic was tested **by pod IP** rather than by Service name, deliberately. A
denied egress also breaks DNS, so a name-based test failing would not say whether
the packet was refused or the name simply did not resolve.

## Results

### Baseline, with no policy present

```text
client -> 10.244.0.10:8080 (pod IP)        alive          exit 0
nslookup kubernetes.default.svc            Address: 10.96.0.1   exit 0
server pod Ready                           True
```

The last line matters on its own: with no policy, the kubelet's readiness probe
reaches the pod, which is the control this experiment needs in order to say
anything about probes later.

### With a default-deny applied

The policy, exactly as the API server stored it:

```yaml
spec:
  podSelector: {}
  policyTypes:
  - Ingress
  - Egress
```

`podSelector: {}` selects every pod in the namespace and both directions are
declared with no rules beneath them, which is a total denial. Then:

```text
client -> 10.244.0.10:8080 (pod IP)        alive          exit 0
  ... retested after a 20-second settle    alive
nslookup kubernetes.default.svc            exit 0
nslookup ... 10.96.0.10 (CoreDNS directly) exit 0
server pod Ready                           True
```

**Nothing was refused.** Ingress was not blocked, egress was not blocked, and
name resolution was unaffected.

### Why

```text
kindnetd args:  (none)
kindnetd env:   HOST_IP, POD_IP, POD_SUBNET, CONTROL_PLANE_ENDPOINT
```

No `--feature-gates` argument and nothing enabling a policy controller. The
plugin is not configured to enforce NetworkPolicy and does not.

## What this establishes

- **A rendered NetworkPolicy on this plugin is a declaration and nothing else.**
  `EX-05` said a policy object the cluster ignores looks exactly like a control.
  That was written as a hypothetical and is now an observation.
- `DR-04` moves from *untested* to *tested, and the plugin does not enforce*.
  That is a worse position than the register recorded, not a better one, and it
  is the reason the risk still blocks production use.

## What this does NOT establish

- **Nothing about the probe path.** The kubelet-probe question — whether a
  default-deny would starve a pod of its readiness probe — cannot be answered on
  a plugin that enforces nothing. The server stayed `Ready` with the deny in
  place because the deny did nothing. That question is still open and still needs
  a policy-capable CNI to answer.
- **Nothing about whether the policies are correct.** They were not exercised.
  Their correctness rests on
  [the render checks](../../../tests/architecture/test_helm_chart.py) and on
  server-side validation, not on this.
- **Nothing about the accepted cluster's exact configuration.** See the table
  above.
- **Nothing about a release.** No InferOps API image is published, so no release
  was installed and none could be.

## The separate result: server-side validation

Both committed renders were applied with `--dry-run=server` against this API
server, which is a stronger check than `kubeconform` because it runs admission,
defaulting, and field semantics rather than a schema:

```text
real render   11 installed objects + the helm test hook pod   all accepted
mock render    7 installed objects + the helm test hook pod   all accepted
```

The first attempt reported the hook pod forbidden, because a server dry-run
creates no ServiceAccount for it to reference. Re-running with the account
present accepted it, so that was an artifact of dry-running an entire release at
once rather than a defect in the manifest.

## Cleanup

Both scratch namespaces (`inferops-np-probe`, `inferops-platform`) were deleted
and their removal confirmed. The pre-existing `inferops-serving-feasibility`
namespace was not created, modified, or removed by this experiment. No other
kubeconfig context was contacted.

## What would close DR-04

One of two things, and the project has to pick:

1. **A policy-capable CNI on the accepted cluster** — `kind` supports disabling
   the default CNI and installing one that enforces policy, at the cost of a
   heavier local environment.
2. **kindnetd with policy enforcement switched on**, if the pinned kindnetd
   release supports the feature gate and the accepted
   [cluster definition](../../../deploy/kind/inferops-dev.yaml) is changed to set
   it.

Either is a change to an accepted environment decision and belongs to a decision
record rather than to this one. Until one happens, the honest position is that
the chart renders a correct policy that nothing applies.
