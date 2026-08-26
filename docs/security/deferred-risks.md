# Deferred risks and accepted exceptions

Status: **accepted register**, in
[ADR 0008](../architecture/decisions/ADR-0008-v1-security-baseline.md). Twelve risks
V1 carries rather than reduces, and four weaknesses it accepts with a compensating
control. Ten of the twelve block production use.

This is the document that makes the rest of the security baseline honest. A control
list on its own describes what a project does; it takes a register to describe what
it does not, and a register is exactly the artifact that gets trimmed when a project
wants to look further along than it is. The rule against trimming it is written down
below, and it is one of the four this project cannot enforce with a test.

The authoritative form is
[`security-baseline.v1alpha1.json`](security-baseline.v1alpha1.json). This document
and that file are compared in both directions by
[`tests/security/`](../../tests/security/).

## How to read a register entry

Each entry declares five things, and a test requires all five:

- the **boundary** it sits at, and the threats it leaves open;
- **why V1 defers it**, which is a reason and never a schedule;
- **what would have to be true** to close it;
- **what may not be claimed** while it stands — the field that does the work, and
  the one a test requires to be phrased as a denial;
- whether it **blocks production use**, which ten of the twelve do.

An entry leaves this register when a control that reduces it is added in the same
change. It is never removed because the register had become an uncomfortable thing to
publish. No test can enforce that, and the rule is marked `review` in
[the control matrix](control-matrix.md) rather than dressed up as something stronger.

## The register

| ID | Risk | Boundary | Blocks production use |
|---|---|---|---|
| DR-01 | No caller is authenticated and no request is authorised | B5 | yes |
| DR-02 | There is no rate limit, quota, or concurrency limit | B5 | yes |
| DR-03 | A tenant identifier is never validated against an entitlement | B5 | yes |
| DR-04 | No network policy exists, and the local plugin's enforcement is untested | B3 | yes |
| DR-05 | No pod security property is enforced for a pod this platform deploys | B4 | yes |
| DR-06 | The transport delivering a model artifact is not authenticated | B1 | yes |
| DR-07 | There is no dependency lockfile and no packaging manifest | B1 | yes |
| DR-08 | No image is scanned and no provenance statement is verified | B1 | yes |
| DR-09 | Artifact availability is not defended | B1 | no |
| DR-10 | No secret manager, rotation policy, or expiry check exists | B3 | yes |
| DR-11 | No run of a secret scanner over this history is recorded | B6 | no |
| DR-12 | Nothing is logged, so nothing can be reconstructed | B5 | yes |

### DR-01 — No caller is authenticated and no request is authorised

**Why deferred.** V1's caller boundary is a port-forward from a machine that already
holds the cluster's credential. An authentication component would be a platform
capability with no consumer, designed against a deployment model this project does
not have — and the discarded design would have been published as a plan in the
meantime.

**What would have to be true.** An identity source, a decision point, a credential
lifecycle, and a deployment model in which the API is reachable by something other
than a port-forward.

**Not claimed.** No document in this repository may describe V1 as access-controlled,
protected, or restricted at the caller boundary. Least exposure is what exists there,
and it identifies nobody.

### DR-02 — There is no rate limit, quota, or concurrency limit

**Why deferred.** The one executed trial was single and sequential; the runtime
reported four slots and one was ever used. A limit set now would be a number with no
measurement behind it, and this project already refuses to publish figures derived
that way.

**What would have to be true.** A measurement of behaviour under concurrency, which
the deferred capacity-and-load layer would produce and which V1 does not run.

**Not claimed.** No availability, capacity, or resilience property is claimed at this
boundary.

### DR-03 — A tenant identifier is never validated against an entitlement

**Why deferred.** There is no entitlement source, no tenant registry, and no component
that would consult one. The rule is recorded so that the first component to read the
field inherits it rather than inventing its own handling.

**What would have to be true.** An authority that can answer whether a given author
may name a given tenant, and a component positioned to ask before the value is used.

**Not claimed.** No isolation, attribution, or multi-tenancy property is claimed. One
narrower property does hold and is worth separating from this deferral: a tenant
identifier has no permitted placement in a committed evidence record, because the
sensitivity class [the telemetry catalog](../telemetry/telemetry-catalog.md) gave it
allows none.

### DR-04 — No network policy exists, and the local plugin's enforcement is untested

**Why deferred.** A policy object belongs to a release, and no chart exists to carry
one. Committing a policy now would produce a manifest nothing installs and a control
nothing applies.

**What would have to be true.** A Helm chart, and an executed test showing that a
policy denies traffic on the cluster this project actually uses. The second is the
one that is easy to skip, and skipping it produces the worst outcome available here:
a policy object that looks like a control and is ignored by the plugin.

**Not claimed.** No network isolation property is claimed at any boundary.

### DR-05 — No pod security property is enforced for a pod this platform deploys

**Why deferred.** This platform deploys no pod. The eight pod-security assertions are
enforced over every manifest committed here, which is a property of five YAML files
rather than of a cluster.

**What would have to be true.** A rendering path that produces pod specifications,
and an admission policy in the cluster that refuses one which does not carry the
properties. Which of the two enforces it is `D14` in the decision record and is
explicitly not decided.

**Not claimed.** No document may describe a workload this platform deployed as
constrained, because it has deployed none. See `EX-04`.

### DR-06 — The transport delivering a model artifact is not authenticated

**Why deferred.** The downloader used in the one executed trial reports that
certificate validation is disabled. ADR 0002 accepted that with the published hash as
the compensating control, and replacing the downloader is serving work outside this
decision.

**What would have to be true.** An acquisition path that validates the transport, so
that the committed hash becomes a redundant check rather than the only one.

**Not claimed.** No supply-chain integrity property beyond the hash comparison is
claimed. See `EX-01`, which states the one reason the argument closes at all.

### DR-07 — There is no dependency lockfile and no packaging manifest

**Why deferred.** ADR 0001 D4 proposes an approach without accepting one, and ADR
0003 deliberately leaves the packaging tool open. Committing a lockfile would settle
both in passing, which is the kind of decision leak this project spends effort
avoiding.

**What would have to be true.** An accepted dependency-installation decision, and a
lockfile a check can run against.

**Not claimed.** No reproducibility property is claimed for the tool chain that runs
the checks. The recorded tool versions in each evidence record are the only trace of
what a result was produced with.

### DR-08 — No image is scanned and no provenance statement is verified

**Why deferred.** There is no continuous-integration lane to run a scanner in, and a
scan run once by hand ages into a claim that outlives its result.

**What would have to be true.** A configured lane, a scanner with a recorded version,
and a policy for what a finding blocks.

**Not claimed.** No vulnerability count, severity distribution, or scan score is
published, and none may be. A digest pin establishes *what* ran; it establishes
nothing about what is inside it or who built it.

### DR-09 — Artifact availability is not defended

**Why deferred.** [The architecture](../architecture/system-architecture.md) already
places publishers outside the availability boundary. Mirroring an artifact is a
distribution decision with a licence question attached, and V1 does not make one.

**What would have to be true.** A durable mirror this project is entitled to publish,
and a policy for what happens when a pinned revision disappears.

**Not claimed.** No availability or reproducibility-over-time property is claimed. If
the pinned revision stops being served, the reproduction path for every existing
serving record stops working — those records become unrepeatable, which is not the
same as becoming untrue.

### DR-10 — No secret manager, rotation policy, or expiry check exists

**Why deferred.** [The workload contract](../contracts/workload-contract.md)
publishes a locator and three provider kinds. Nothing in V1 resolves a reference, so
there is no consumer for a lifecycle.

**What would have to be true.** A component that resolves a reference, and an owner
accountable for what is behind it.

**Not claimed.** No secret-management property is claimed beyond the shape of a
locator. The platform can report a workload as correctly configured while its
credential is shared, permanent, or absent.

### DR-11 — No run of a secret scanner over this history is recorded

**Why deferred.** The scanner is not installed on the host this work was done on, and
there is no lane to run it in. A configuration file is committed, and a configuration
file is not a result.

**What would have to be true.** An executed run with a recorded scanner version and
its output, which would move the security-scan layer of
[the test strategy](../testing/test-strategy.md) from `planned` to `implemented`.

**Not claimed.** The claim `no-credential-or-model-artifact-enters-public-history`
stays `planned` and may not be cited. See `EX-03` for what the committed allowlist
would not have caught even if a run existed.

### DR-12 — Nothing is logged, so nothing can be reconstructed

**Why deferred.** No logger, formatter, or sink exists.
[The telemetry catalog](../telemetry/telemetry-catalog.md) specifies a log record for
a component that has not been written, and no log line has ever been inspected
because none has been written.

**What would have to be true.** A logger that emits the specified record, a store
with a stated retention window, and a test that a real record carries only permitted
fields.

**Not claimed.** No auditability, traceability, or incident-reconstruction property
is claimed, and no control in this baseline may be described as observed.

This entry is written last and is arguably first in importance. **A control whose
failure leaves no trace cannot be shown to have held.** Every other entry here
describes something that is missing; this one describes why the things that are
present cannot be demonstrated in operation.

## Accepted exceptions

Four weaknesses this project accepts rather than fixes. Each names where it was
accepted, the compensating control that makes it tolerable, what remains undefended
anyway, and the condition under which it should be revisited. A test refuses an
exception missing any of them, and refuses one whose compensating control is not a
control the baseline declares.

| ID | Exception | Compensating control | Register entry |
|---|---|---|---|
| EX-01 | The model download's transport reports certificate validation as disabled | `verify-artifact-hash-before-use` | DR-06 |
| EX-02 | The cluster identity guard is satisfied by a second cluster given this project's name | `refuse-to-act-on-a-cluster-this-project-did-not-create` | — |
| EX-03 | The secret-scan allowlist covers two directories wholesale | `no-credential-or-artifact-in-public-history` | DR-11 |
| EX-04 | The pod-security properties are enforced over apparatus, not over a serving path | `run-as-non-root` | DR-05 |

### EX-01 — The transport is not authenticated

Accepted in
[ADR 0002](../architecture/decisions/ADR-0002-model-and-serving-runtime.md).

**Residual risk.** The published SHA-256 is the entire integrity argument for the
transfer rather than a redundant check on it. It closes for exactly one reason, and
that reason is worth keeping in view: the expected hash is **committed in this
repository**, not fetched over the same transport. A hash published alongside the
file it describes would defend against corruption and against nothing else.

**Revisit when** the acquisition path is replaced by one that validates the
transport.

### EX-02 — The identity guard defends against a mistake, not against intent

Accepted in
[ADR 0001](../architecture/decisions/ADR-0001-local-development-environment.md).

**Residual risk.** The guard confirms that every node the reachable API server
reports is a container the cluster tool labelled for this project's cluster. A second
cluster deliberately given the same name satisfies it. That is accepted rather than
fixed, because the threat it exists for is a stale context and a mistyped command on
a contributor's own machine, and nothing running on that machine could defend against
its owner.

**Revisit when** the scripts act on a cluster somebody other than the contributor
owns, which V1 does not do.

### EX-03 — The allowlist covers two directories wholesale

Accepted in
[the secret-scanning allowlist](../../.github/secret-scanning-allowlist.md).

**Residual risk.** A real credential committed under either allowlisted path would
not be flagged by a run of the scanner — if one were ever run, which it has not been.
The allowlist exists because the fixtures in those directories are deliberately
credential-shaped, which is the right shape for a fixture and the wrong shape for a
directory-wide exemption.

**Revisit when** a scanner run is recorded, at which point the allowlist should narrow
from two directories to the specific fixture values it exists for.

### EX-04 — The pod-security properties are properties of apparatus

Accepted in
[ADR 0008](../architecture/decisions/ADR-0008-v1-security-baseline.md).

**Residual risk.** The enforcement is real and its subject is small. Every manifest
this repository publishes carries the eight assertions, and this repository publishes
no manifest that serves a V1 workload. Nothing here constrains a pod this platform
deployed, and no admission control exists to constrain one it does not own.

**Revisit when** a rendering path produces pod specifications, at which point the
check must move from committed manifests to rendered output and be joined by
admission control.

## What this register does not do

- **It does not rank anything.** No entry carries a likelihood, a severity, or a risk
  score. Every such number here would be invented, and a test refuses one.
- **It does not schedule anything.** "What would have to be true" is a condition, not
  a plan, and no entry names a date or a release.
- **It is not exhaustive.** A risk nobody thought of is a risk nobody registered, and
  the same limitation applies to it as to
  [the threat model's twenty-two threats](threat-model.md).
- **It cannot be reported against privately.** There is no private vulnerability
  reporting channel, which [SECURITY.md](../../SECURITY.md) records and
  [the governance document](../governance/repository.md) carries as a blocker. A
  reader who finds a real problem in any entry here has nowhere confidential to send
  it, and that is the reason everything here is published rather than held.

## Related records

| Topic | Document |
|---|---|
| The decision this register implements | [ADR 0008](../architecture/decisions/ADR-0008-v1-security-baseline.md) |
| What can go wrong, and where | [Threat model](threat-model.md) |
| Every control and what verifies it | [Control matrix](control-matrix.md) |
| The authoritative form of all of it | [`security-baseline.v1alpha1.json`](security-baseline.v1alpha1.json) |
| How to report a problem, and why you cannot yet | [SECURITY.md](../../SECURITY.md) |
