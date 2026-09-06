# V1-S3-004-PR1 validation — Kubernetes workload security defaults

Change: the chart gained one service account per workload, four network policy
objects, and a validator that refuses a rendered release which dropped any of the
controls the security baseline requires. This record is what was run, what it
found, and — the section that matters most for a security change — what it does
not support.

**Evidence class.** Everything asserted here is `local-static`: files read,
rendered, and compared, with a `C0` ceiling. **Nothing in this change has run
inside Kubernetes.** No cluster has installed the chart, no pod has presented
either service account, no network policy object has ever been applied, and no
connection has been attempted against one. The one experiment that would say
something about enforcement was not authorised for this story and was not run;
[the section below](#what-was-not-run-and-why) says so in the terms
`DR-04` uses.

## What the change is

Four things, and each answers one of the parent story's acceptance criteria.

**One identity per workload.** The chart rendered a single `ServiceAccount` that
both Deployments named. It now renders `<release>-api` and, under the real
profile, `<release>-runtime`. Neither is granted anything — no `Role`, no
`ClusterRole`, and no binding of either is rendered anywhere in the chart, and no
pod mounts a token — so the split changes no privilege that exists today. It
changes what the first grant can reach: a `RoleBinding` written for the API and
attached to a shared account is a grant to the serving runtime as well, made by
somebody who was not thinking about the serving runtime. `security.serviceAccount.name`
became `security.serviceAccount.api.name` and `.runtime.name`, and the chart
version moved to `0.2.0`.

**A network policy that starts from a denial.** Four objects. A deny of both
ingress and egress over every pod the release installs; the API reachable on its
own port from the release's own pods, permitted DNS and the runtime port; the
runtime reachable on its own port and permitted **nothing** outbound; and the
`helm test` pod permitted DNS and both service ports. The deny selects the
release's own pods rather than the namespace, because a `podSelector` of `{}`
would also deny for Terraform-owned prerequisites this chart does not own, and it
omits the component label so that a component added later arrives denied rather
than uncovered.

**A validator over rendered manifests.** `python -m tools.workload_policy` applies
twelve rules to a bundle: the six pod and container security properties, digest
pinning, least exposure, an explicit resource envelope on every container, a
dedicated service account, no credential-shaped environment name carrying a
literal, and a default-deny selecting every workload. Every rule identifier is a
control identifier in the committed baseline, and a test compares the two sets in
both directions.

**Nine fixtures that establish it refuses.** Each drops one control; a committed
record says which rules each must produce; the comparison runs in both
directions. This is the part that makes the other three falsifiable, and the
reason is not hypothetical — a validator whose rules all read the wrong field
passes on every run, and a passing run is what enforcement looks like.

## Commands and results

### Python

```text
uv run --locked ruff check .           All checks passed!
uv run --locked ruff format --check .  287 files already formatted
uv run --locked mypy .                 Success: no issues found in 153 source files
uv run --locked python -m pytest -q    6069 passed, 27 skipped, 14 deselected
```

The default lane went from 5,918 passing to 6,069. The `main` figure was measured
in a clean worktree checked out at `main` and removed afterwards, rather than by
stashing: several suites parametrise over the published Markdown files and over
the committed controls, so a stash that left this change's new documents in the
tree would return a baseline several too high. That mistake is recorded in
[the V1-S3-003 record](../architecture/v1-s3-003-pr1-validation.md) and this
measurement avoided it rather than rediscovering it.

The suites this change touches, before and after:

```text
tests/security/test_workload_policy.py          new         70 passed
tests/architecture/test_helm_chart.py           127  ->    154 passed
tests/security/                                 667  ->    772 passed
tests/architecture/                             676  ->    703 passed
tests/testing/                                 1052  ->   1071 passed
```

The chart figures are with `helm` on `PATH`. Without it the two render-drift
comparisons skip loudly and the rest still run, which is the arrangement
`kubeconform` and `shellcheck` already have.

### The workload policy, run directly

```text
uv run --locked python -m tools.workload_policy \
  charts/inferops-llm/ci/rendered/real.expected.yaml \
  charts/inferops-llm/ci/rendered/mock.expected.yaml
ok      2 file(s) satisfy the workload policy                    exit 0

uv run --locked python -m tools.workload_policy deploy
ok      6 file(s) satisfy the workload policy                    exit 0
```

Each of the nine fixtures, run on its own, refused with exactly the rules
[`expected-rejections.json`](../../../tests/security/fixtures/workload-policy/invalid/expected-rejections.json)
records for it and exit status 1:

| Fixture | Rules produced |
|---|---|
| `default-service-account.yaml` | `use-a-dedicated-service-account-per-workload` |
| `no-service-account-named.yaml` | `use-a-dedicated-service-account-per-workload` |
| `no-network-policy.yaml` | `network-policy-in-the-release-namespace` |
| `ingress-only-network-policy.yaml` | `network-policy-in-the-release-namespace` |
| `unbounded-resources.yaml` | `declare-explicit-resource-requests-and-limits` |
| `secret-value-in-a-manifest.yaml` | `no-secret-value-in-a-rendered-manifest` |
| `moving-image-tag.yaml` | `pin-image-by-digest` |
| `node-port-service.yaml` | `least-exposure-no-manifest-publishes-a-service` |
| `root-and-privileged-container.yaml` | `do-not-mount-a-service-account-token`, `drop-all-capabilities`, `forbid-privilege-escalation`, `read-only-root-filesystem`, `run-as-non-root`, `seccomp-runtime-default` |

Twelve rules, nine fixtures, and a test that fails if any rule is left
unexercised by all of them.

### Helm

`helm v3.19.0`, which is the version whose `helm template` output the committed
renders are byte for byte.

```text
helm lint charts/inferops-llm --strict --namespace inferops-platform \
  --values charts/inferops-llm/ci/real-values.yaml    1 chart(s) linted, 0 failed
helm lint charts/inferops-llm --strict --namespace inferops-platform \
  --values charts/inferops-llm/ci/mock-values.yaml    1 chart(s) linted, 0 failed
```

```text
helm template ... --values charts/inferops-llm/ci/real-values.yaml \
  | kubeconform -strict -summary -kubernetes-version 1.34.0 -
Summary: 12 resources found parsing stdin - Valid: 12, Invalid: 0, Errors: 0

helm template ... --values charts/inferops-llm/ci/mock-values.yaml \
  | kubeconform -strict -summary -kubernetes-version 1.34.0 -
Summary: 8 resources found parsing stdin - Valid: 8, Invalid: 0, Errors: 0

kubeconform -strict -summary -kubernetes-version 1.34.0 deploy/smoke/*.yaml
Summary: 5 resources found in 2 files - Valid: 5, Invalid: 0, Errors: 0
```

**The first version of this record said `kubeconform` was not run because it is
not installed on this host, and called the four new `NetworkPolicy` objects
unvalidated against the upstream schema.** Both halves were false, and
independent review of this change found it. `kubeconform` is on `PATH`, running
it was one command, and every object in both renders — the policies included —
validates against the Kubernetes 1.34 schemas. The correction is left visible
rather than quietly applied, because a record that misstates what a host has is
a record whose other statements a reader has no reason to trust, and this project
turns entirely on those statements being literally true.

Both renders were regenerated with the command
[the render README](../../../charts/inferops-llm/ci/rendered/README.md) publishes,
and the suite's own re-render comparison passes, so the committed files are the
output of that binary rather than a hand-edited copy of it.

The real profile now installs eleven objects and the mock seven, up from six and
four: four network policies and a second service account under `real`, three
network policies under `mock` — which renders no runtime and therefore no runtime
policy.

### Everything else

```text
git diff --check main...HEAD                                   no output
git ls-files -z '*.md' | xargs -0 grep -n '[[:blank:]]$'        pre-existing only
git ls-files -z '*.md' | xargs -0 grep -n "$(printf '\t')"      no matches
the relative-link check in CONTRIBUTING                         pre-existing only
```

Two of those need their result stated rather than summarised, because "no
matches" would have been false.

The trailing-whitespace scan reports twelve lines, all of them in
[`docs/proof/serving/v1-s1-002-pr1-cumulative-review-fixes.md`](../serving/v1-s1-002-pr1-cumulative-review-fixes.md),
which this change does not touch. No file this change adds or edits carries a
trailing blank or a hard tab; that was checked separately over the changed set.
The pre-existing lines are left alone: that record is a statement about a moment
that has passed, and reformatting it would be editing a record rather than fixing
a document.

The link scan reports **two** lines, `docs/proof/README.md -> ...` and
`docs/proof/security/v1-s3-004-pr1-validation.md -> ...`. Both are false
positives and the second is this record's own: `docs/proof/README.md` quotes the
literal string `Produced from [the raw-result template](...)` as an illustration
of what a promoted record carries, the scan cannot tell an illustration from a
link, and the sentence above — which quotes that illustration in order to explain
it — reproduces the false positive one document further on. The first version of
this section said "one line", which was true of the tree before this record was
written into it and false of the tree as committed. Every relative link in the
three documents this change adds resolves.

## What was not run, and why

**No cluster experiment.** The story authorised no Kubernetes experiment, and
none was performed. Nothing here was installed, applied, scheduled, or connected
to. Specifically not run: `helm install`, `helm test`, `kubectl apply` of any
policy object, and any attempt to make a connection a policy denies.

**`shellcheck` was not run.** It is not installed on this host, and this change
edits no shell script.

**No scanner was run for this change.** The image and dependency scans recorded in
[the V1-S2-006 record](v1-s2-006-pr1-validation.md) are unchanged by it: no image
reference and no dependency moved.

## What two independent reviews found

Both reviews ran before this branch was pushed and neither was given the answer
in advance. Between them they found six defects; all six are fixed in the second
commit on this branch, and they are listed because a review that finds nothing
and a review nobody ran produce the same record.

**A supported setting switched a control off.** `security.serviceAccount.create:
false` is documented and schema-legal, and with no names supplied it pointed
every pod at the namespace's `default` account — so the chart rendered a release
this story's own validator refuses, once per pod, and nothing anywhere said so. A
control a supported setting can switch off is a control that holds by default.
`create: false` now requires a name per workload and refuses the literal
`default`, the half the setting exists for still renders and still passes, and
three tests cover it. `security.networkPolicy.enabled: false` is the same shape
and is deliberately *not* refused — an operator on a cluster that ignores policy
objects may reasonably want none — but the render is refused by the validator
with one finding per workload, and a test asserts that rather than leaving the
trade to a sentence in a values file.

**A policy in one namespace was counted as covering a workload in another.** A
`NetworkPolicy`'s `podSelector` reaches only its own namespace. The rule compared
labels and never namespaces, so a fabricated bundle with a deny in `team-a` and a
compliant workload in `team-b` produced no finding at all — a workload reported
covered by a policy Kubernetes would never apply to it. Neither committed render
triggers it, because one `helm template` emits one namespace; the check over
`deploy/` is already a multi-file bundle, which is how it would have arrived.

**The credential-shaped name check missed the plural.** One regular expression
anchored on `_` or end-of-string let `DB_SECRETS`, `APP_CREDENTIALS`,
`clientSecret`, and `client-secret` carry a literal straight through. Matching is
now done over split tokens across four naming conventions, held by a committed
table of names that must and must not match — the second half of which exists
because `MAX_OUTPUT_TOKENS` is a chart value here and a token count, and a check
that refused it would fail for a reason unrelated to the property it defends.

**An omitted `policyTypes` was read as isolating nothing.** Kubernetes defaults
it to `Ingress`, plus `Egress` where an egress block is present. The old reading
was conservative, wrong, and invisible — it could only ever produce a finding.

**`kubeconform` was reported as absent when it was installed.** Corrected above,
and the correction closed the gap the record had described as unclosed.

**The stale boundary.** `B3` in the baseline still read "A network policy is
planned" and "No policy object exists", which this same change made false while
`DR-04` two hundred lines away recorded the truth. The boundary table and
[the architecture](../../architecture/system-architecture.md) carry that sentence
verbatim by design, so both were corrected together: the gap at `B3` is now an
untested enforcement rather than an absent object, which is a different gap and
not a smaller one.

## What this establishes, and what it does not

**Established.** Every workload the chart renders presents an identity of its own
and never the namespace's `default`; no `Role`, `ClusterRole`, or binding is
rendered anywhere in the chart and no pod mounts a token; every container states a
CPU and memory request and limit; secret material reaches a container as a
reference and no rendered manifest carries a credential-shaped name with a
literal; every pod this release installs is selected by a policy that denies both
directions before anything is opened; the runtime is given no egress allowance at
all; every egress rule that exists permits name resolution over both protocols;
no policy peer is an address range or a whole namespace; and a manifest that drops
any of it is refused, citing the rules it dropped and no others.

**Not established, and the distance is the point.**

*A policy object is not enforcement.* A `NetworkPolicy` is applied by the
cluster's network plugin rather than by the object. The accepted local cluster is
`kind` with its default CNI, whether that plugin applies a policy object **has
never been tested here**, and no cluster has installed this chart. What exists is
a rendered declaration. `DR-04` was rewritten to carry exactly that half — it was
"no network policy exists, and enforcement is untested" and is now "the rendered
policy's enforcement is untested" — and it still blocks production use. `EX-05`
records the exception, names `least-exposure-no-manifest-publishes-a-service` as
the compensating control, and states the residual risk: between pods in the
namespace, nothing is established at all.

*A validator that reads files is not admission control.* `DR-05` is unchanged in
substance. This platform deploys no pod, nothing here refuses one, and the module
that applies twelve rules holds no credential and contacts no cluster. Its
`whyDeferred` was extended to name the new check and its `whatWouldHaveToBeTrue`
now says outright that a validator reading a file is not what the risk turns on.

*Two names granted nothing are two names granted nothing.* The service account
split establishes no privilege difference today. What it establishes is that a
future binding written for one workload cannot reach the other.

*Two settings are a trade rather than a hole, and one is still a trade.*
`security.networkPolicy.enabled: false` renders no policy, and the validator then
refuses the release. That is the intended, visible consequence, and it means the
control is available to be switched off by whoever installs — with a refusal
attached, rather than silently.

*The trial apparatus is outside two rules.* The manifests under `deploy/` name no
service account and are covered by no network policy. The policy does not require
it of them — they are one-shot smoke and trial apparatus rather than a release —
and the exemption is read off the `inferops.io/lifecycle` label rather than chosen
by whoever runs the check, so no invocation can request the lighter policy. A test
holds it to exactly two rules. It is a real gap in a real set of committed
manifests and it is recorded as a limitation rather than left for a reader to
notice.

## What moved in the baseline

| | Before | After |
|---|---|---|
| Controls | 34 | 38 |
| Enforced by something | 24 | 29 |
| `enforced-over-manifests` | 10 | 15 |
| `specified-only` | 3 | 2 |
| Accepted exceptions | 4 | 5 |
| Deferred risks | 12 | 12 |

The deferred-risk count is the row worth reading. Nothing left the register. `DR-04`
was narrowed and rewritten, `DR-05` was extended, and both still block production
use — which is the outcome a story that adds security controls should expect when
none of them runs anywhere.

## Related records

| Topic | Document |
|---|---|
| The rules, the fixtures, and what a checked manifest establishes | [Workload policy](../../security/workload-policy.md) |
| Every control, its verification, and its status | [Control and verification matrix](../../security/control-matrix.md) |
| What is undefended, and the exceptions accepted | [Deferred risks and exceptions](../../security/deferred-risks.md) |
| The decision these controls belong to | [ADR 0008](../../architecture/decisions/ADR-0008-v1-security-baseline.md) |
| The chart these rules are applied to | [`charts/inferops-llm/README.md`](../../../charts/inferops-llm/README.md) |
| The change this one builds on | [V1-S3-003-PR1](../architecture/v1-s3-003-pr1-validation.md) |
