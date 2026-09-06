# The workload policy, and what checking a manifest establishes

Status: **implemented for the release layer**, in V1-S3-004. It publishes the
rules [`tools/workload_policy/`](../../tools/workload_policy/) applies to a
bundle of Kubernetes manifests, which fixtures establish that it refuses, and —
the section a reader should not be able to skip — the distance between a manifest
that satisfies these rules and a workload that is constrained by them.

## What this is

A validator that reads YAML. It parses a bundle of manifests — the two committed
chart renders, the manifests under [`deploy/`](../../deploy/), or the output of a
`helm template` somebody is about to install — and refuses one whose workloads
have dropped a control [the security baseline](control-matrix.md) says every
InferOps workload carries.

```sh
python -m tools.workload_policy charts/inferops-llm/ci/rendered/real.expected.yaml
python -m tools.workload_policy deploy
```

Exit status is 0 when the bundle satisfies the policy and 1 when anything is
refused, so it is usable as a gate. Everything named in one invocation is one
bundle, because one of the rules cannot be answered by a single document: whether
a workload is denied by default is a property of the policy objects installed
beside it, and a Deployment read on its own can never answer it.

## What this is not

**It reads files.** It holds no credential, contacts no cluster, and stops
nothing being applied. No admission controller in any cluster applies these
rules, this platform has deployed no pod, and no cluster has installed the chart
whose renders it checks. A pod running with a property this policy would refuse
is a pod this policy will never see.

That is `DR-05` in [the deferred-risk register](deferred-risks.md), and nothing
here narrows it. What V1-S3-004 changed is `network-policy-in-the-release-namespace`,
which was `specified-only` — decided and written down for a chart that had not
been written — and is now enforced over the chart's committed renders. It is
enforced *over manifests*, which is a repository property. It is not a cluster
property, and the two sentences are almost identical, which is exactly why
[ADR 0008](../architecture/decisions/ADR-0008-v1-security-baseline.md) D2 makes a
control's status derive from what verifies it rather than from what it says.

Why bother, then. Because `T-18` is the threat this project keeps meeting: a
control gets written down, and being written down is mistaken for being enforced.
The six pod-security properties held over every manifest here by convention until
a test made them a property; a convention is enforced by whoever writes the next
manifest remembering it. The chart is now a rendering path, it produces pod
specifications nobody hand-writes, and the same convention applied to its output
— which is to say the same absence of one.

## The rules

Every identifier below is a control identifier in
[`security-baseline.v1alpha1.json`](security-baseline.v1alpha1.json), and
[`tests/security/test_workload_policy.py`](../../tests/security/test_workload_policy.py)
compares the two sets in both directions. A rule the validator invents, and a
control that names this module with no rule behind it, are each a failing test.

| Rule | What it refuses |
|---|---|
| `run-as-non-root` | A pod specification that does not set `runAsNonRoot: true`, or that sets it without a numeric uid and leaves the image to choose one |
| `seccomp-runtime-default` | A pod specification without the container runtime's default seccomp profile |
| `do-not-mount-a-service-account-token` | A pod specification that mounts its service account token. No workload here talks to the Kubernetes API |
| `forbid-privilege-escalation` | A container that may acquire more privilege than it started with |
| `read-only-root-filesystem` | A container that may write its own root filesystem |
| `drop-all-capabilities` | A container that does not drop `ALL`, and a container that drops `ALL` and adds one back |
| `declare-explicit-resource-requests-and-limits` | A container missing a CPU or memory request or limit. No request means scheduled anywhere; no limit means bounded by nothing |
| `use-a-dedicated-service-account-per-workload` | A workload that names the namespace's `default` service account, or names none and is given it |
| `no-secret-value-in-a-rendered-manifest` | A credential-shaped environment **name** carrying a literal instead of a `secretKeyRef` |
| `pin-image-by-digest` | An image reference named by tag. A tag is a label somebody can move; a digest is what the engine resolves |
| `least-exposure-no-manifest-publishes-a-service` | A `NodePort`, a `LoadBalancer`, an `ExternalName`, a pinned node port, or an Ingress |
| `network-policy-in-the-release-namespace` | A workload no policy in the bundle selects and denies **both** ingress and egress for |

Init containers are containers. They run with the pod's privileges before
anything else does, which makes them the ones most worth checking and the ones
most often left out of a checklist written from the `containers` key.

The secret rule fires on the **name carrying a value** and never on the shape of
a value. A rule that matched value shapes would be a rule that reads secrets, and
its findings would be where they got published. No finding this validator emits
carries a value read out of the manifest — the same rule
[the contract validator](../contracts/workload-contract.md) already follows, for
the same reason: the field most likely to hold something sensitive is the one
that was refused for looking wrong.

### Two rules apply to a release and not to the apparatus

`use-a-dedicated-service-account-per-workload` and
`network-policy-in-the-release-namespace` apply to an installed release. The
manifests under [`deploy/`](../../deploy/) are smoke and trial apparatus — Jobs
that run once by hand in a smoke namespace, with no service to reach and nothing
reaching them — and giving each of them a dedicated identity and a policy pair
would be four objects defending a Job that exits. **Every other rule applies to
everything**, and a test establishes that the exemption is exactly two rules wide
and no wider.

**The scope is read off the manifest and is not a flag.** A bundle is a release
when something in it carries `inferops.io/lifecycle: release`, which the chart
writes on every object it renders and a test already holds it to. No invocation
can ask for the lighter policy; a workload that wanted it would have to leave the
release it is part of.

What this leaves standing is stated rather than left implicit: the apparatus
under `deploy/` names no service account and is covered by no network policy.
That is a real gap in a real set of committed manifests, it is accepted because
those manifests are one-shot apparatus rather than a serving path, and it is
written here so that a reader counting controls does not count it twice.

## The fixtures, and why a failing input is the control

A validator with no failing input is a validator nobody has watched refuse
anything. Every rule could read the wrong field, or the finding list could be
unconditionally empty, and every run would pass — which is the outcome that looks
exactly like enforcement.

[`tests/security/fixtures/workload-policy/invalid/`](../../tests/security/fixtures/workload-policy/invalid/)
holds nine bundles, each dropping one control, and
[`expected-rejections.json`](../../tests/security/fixtures/workload-policy/invalid/expected-rejections.json)
records which rules each must produce. The test compares the two sets in **both**
directions, so a fixture that starts failing for a different reason is a failure
rather than a pass, and a test asserts that the fixtures between them exercise
every rule the validator can cite.

Three of them are worth naming.

`root-and-privileged-container.yaml` is the canonical insecure workload: root,
escalation permitted, a writable root filesystem, `NET_ADMIN` added back, no
seccomp profile, and a mounted service account token. Six refusals from one file.

`ingress-only-network-policy.yaml` is the subtle one, and it is the reason the
ingress and egress halves of a deny are computed separately rather than as one
boolean. Its policy declares only `Ingress` in `policyTypes`, so it denies
everything arriving and leaves **egress completely unrestricted** — and it reads,
in a diff, exactly like a default-deny. A check that asked "is there a deny
policy?" would have answered yes.

`no-service-account-named.yaml` is the same failure as
`default-service-account.yaml` arriving by omission rather than by statement,
because an absent field and a wrong field are different mistakes and neither one
is acceptable.

## The network policy the chart renders

Four objects, when `security.networkPolicy.enabled` is on: a default-deny over
every pod the release installs, an API rule, a runtime rule, and a rule for the
`helm test` pod. The API is reachable on its own port from the release's own pods
and may resolve DNS and reach the runtime; the runtime is reachable on its own
port from the release's own pods and may reach **nothing at all**, because
`llama-server` reads a mounted file and answers a socket and an egress allowance
it never uses is a hole with no purpose.

The deny selects the release's own pods rather than the namespace. A `podSelector`
of `{}` would deny for every pod in the namespace, including Terraform-owned
prerequisites and anything else installed beside this release, and this chart owns
the release layer and nothing else. The selector omits the component label on
purpose: a deny naming the components would stop covering the day a component is
added, and the pod that stopped being covered would be the new one nobody had
written a rule for.

A `kubectl port-forward` is not covered by the API ingress rule and is not meant
to be. That traffic arrives from the node rather than from a pod, whether a plugin
permits it is the plugin's answer rather than this object's, and it is the only
way anything outside the cluster reaches the API at all — which
`least-exposure-no-manifest-publishes-a-service` already carries and this policy
does not replace.

### The part that is not enforcement

**A NetworkPolicy is applied by the cluster's network plugin, not by the object.**
The accepted local cluster ([ADR 0001](../architecture/decisions/ADR-0001-local-development-environment.md)
D2) is `kind` with its default CNI, and whether that plugin applies a policy
object **has never been tested here**. No cluster has installed this chart, and
no run of anything on a cluster is recorded for this story.

So what exists is a rendered declaration whose enforcement is unverified. `DR-04`
still stands and still blocks production use; `EX-05` records the exception with
its compensating control and its residual risk. The reason this is written in
three places rather than one is that a policy the cluster ignores looks exactly
like a control, and the object is the artifact that travels.

What would close it is one executed test on the cluster this project actually
uses: install the release, attempt a connection the policy denies, and record
that it was refused. That is a cluster experiment, it was not authorised for this
story, and it is recorded as not run rather than described as pending.

## Related records

| Topic | Document |
|---|---|
| The decision these controls belong to | [ADR 0008](../architecture/decisions/ADR-0008-v1-security-baseline.md) |
| Every control, its verification, and its status | [Control and verification matrix](control-matrix.md) |
| What is undefended, and the exceptions accepted | [Deferred risks and exceptions](deferred-risks.md) |
| What can go wrong, and where | [Threat model](threat-model.md) |
| Who renders what, and who owns it | [Resource ownership](../architecture/resource-ownership.md) |
| The chart these rules are applied to | [`charts/inferops-llm/README.md`](../../charts/inferops-llm/README.md) |
| What a passing check may be used to claim | [Certification levels](../testing/certification.md) |
