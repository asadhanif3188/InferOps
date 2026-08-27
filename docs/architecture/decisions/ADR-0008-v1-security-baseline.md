# ADR 0008: V1 threat model and security baseline

| Field | Value |
|---|---|
| Status | **Accepted in part** |
| Date proposed | 2026-08-26 |
| Date accepted | 2026-08-26, for D1 through D12 only |
| Decision owner | Unassigned; no public maintainer roster exists yet |
| Supersedes | None |
| Superseded by | None |

> [!IMPORTANT]
> This record decides what V1 protects, from whom, at which boundary, and which
> controls this repository really enforces. It does **not** make anything safe. No
> component here authenticates a caller, authorises a request, enforces a network
> policy, or applies a security context to a pod it deployed, because none of them
> deploys a pod or serves a request. No scanner has been run and recorded, and no
> assessment by an outside party has ever been performed. A document review is not
> an assessment, and this record is a document review.
>
> Most of it is machine-checked. The baseline is committed as data and validated by
> `tests/security/test_security_baseline.py`, which derives each control's status
> from the verification it names, refuses a control whose named test function or
> shell guard does not exist, refuses a control claiming an implemented status
> without a committed evidence record, holds every manifest here to six
> pod-security properties and to a digest pin, refuses any manifest that would
> expose a service outside the cluster, and refuses the vocabulary of a security
> posture in any sentence that is not denying it. Four of the fifteen rules are
> enforced by **review alone** and are marked as such.
>
> D13 and D14 are **not decided**: nobody signs off a control, and where a
> pod-security property would be enforced once a rendering path exists is left to
> ADR 0004's open ownership question rather than answered in passing here.

## Decision status

| ID | Decision | Status | What supports it |
|---|---|---|---|
| D1 | Six trust boundaries: the architecture's five, plus the publication boundary | **Accepted** | A test comparing each mapped boundary against the architecture verbatim, and refusing an unmapped one that does not say why it is here |
| D2 | A control's status is derived from its verification, never asserted | **Accepted** | The derivation table is committed and the suite recomputes every status from it |
| D3 | Six pod-security properties, enforced over every manifest this repository publishes | **Accepted** as a repository property | A test over every parsed pod specification and container under `deploy/` |
| D4 | Least exposure at the caller boundary, and no authentication in V1 | **Accepted** | A test refusing an Ingress, a NodePort, or a LoadBalancer, plus a deferred risk that says what is undefended |
| D5 | A contract carries secret references and never a secret, and a refusal never echoes a value | **Accepted** | Two existing contract tests this baseline names and the suite confirms exist |
| D6 | Content and secrets have no telemetry placement, and capture has no enabling path | **Accepted** | Two existing telemetry tests, plus a check that the forbidden classes still have an empty placement list |
| D7 | Supply chain: pin the digest, pin the revision, verify the hash before use | **Accepted** as far as it goes | A test over every image reference and over the acquisition job; provenance and scanning are deferred with a stated reason |
| D8 | The cluster boundary is guarded by identity rather than by a name | **Accepted** | The guard exists in the environment scripts and the suite confirms it; its bypass is recorded as an exception |
| D9 | The publication boundary is defended by what is committed, because nothing published can be withdrawn | **Accepted** | Tests over host state, personal paths, model artifacts, and the scan configuration's allowlist |
| D10 | A deferred risk is a register entry with a stated reason, not an omission | **Accepted** | Every deferred risk declares why, what would have to be true, and what is not claimed; a test requires all three |
| D11 | An exception names a compensating control and its residual risk | **Accepted** | A test over every recorded exception |
| D12 | The vocabulary of a security posture is reserved and may appear only in a denial | **Accepted** | A sentence-level test over these documents and over the committed data |
| D13 | Who signs off a control and its evidence | **Not decided** | Nothing. There is no public maintainer roster to name |
| D14 | Whether a rendering path or an admission policy enforces a pod-security property | **Not decided, and not this record's to decide** | ADR 0004 leaves the equivalent ownership question open; this record does not fill it in |

## Context

Seven decisions are accepted, one contract is published, four suites run, one
serving runtime has been proven once, a telemetry catalog says what a running V1
would report about itself, and a cost method says what any of it would be worth.
[The architecture](../system-architecture.md) mapped five trust boundaries and said
plainly that naming a boundary is not defending it, leaving three of the five owned
by "the security baseline decision". This is that decision.

The gap it fills is not a gap in controls. It is a gap in **what may be said about
them**. A project at this stage has a small number of real properties — a digest
pin, a hash comparison, a guard in a shell script, an empty placement list — and an
unbounded appetite for describing them as a posture. The failure mode is specific
and it is not lying:

**A control gets written down, and being written down is mistaken for being
enforced.** Nobody decides this. A document lists twenty controls, four of them have
tests, and six months later a reader counts twenty. The list is the artifact that
travels; the qualification stays in the paragraph above it.

**A property of a repository is read as a property of a system.** Every manifest
here sets `runAsNonRoot`. That is true, checkable, and worth having. It is also a
statement about five YAML files, none of which this platform deploys, and the
distance between those two sentences is the distance between a check and a claim.

**A deferral disappears.** A risk nobody wrote down is a risk nobody has to explain,
and the register that would have carried it is exactly the artifact somebody trims
when it makes the project look unfinished. It *is* unfinished, and a register that
shrinks for that reason is the one document whose shrinking means nothing good.

Two constraints come from outside this record. [The certification
document](../../testing/certification.md) already fixes that a claim needs an
executed record and that documentation certifies at `C0` and no higher, which caps
what any of this can support. And [SECURITY.md](../../../SECURITY.md) records that
no private reporting channel exists, which means this project cannot receive a
confidential report about any gap named here — a constraint that shapes what is
responsible to publish, and the answer is everything, because a gap nobody can
report privately is a gap that should at least be public.

## Decision criteria

| Criterion | Why it matters |
|---|---|
| A written control cannot become an enforced one | The failure is a list, not a lie, so the separation has to be mechanical |
| A repository property is never a cluster property | Both are real; only one of them is about a system, and the words for them are almost identical |
| Every gap is visible as a gap | A deferral that is not written down is indistinguishable from a control nobody thought of |
| The boundaries match the architecture exactly | Two documents drawing different boundaries produce a control at neither of them |
| Nothing borrows credibility from a component that does not exist | A specification for an unbuilt component is a specification, and it certifies nothing |
| An exception is argued, not absorbed | An accepted weakness with no compensating control and no residual-risk statement is an unexamined one |
| No example teaches a bad habit | An illustration built from a real credential, prompt, or incident is a disclosure with a pedagogical excuse |
| No decision leaks into an adjacent one | Choosing a control set must not silently choose a component owner, a toolchain, or a deployment model |

## D1 — Six boundaries: the architecture's five, and one it does not draw

`B1` artifact, `B2` cluster, `B3` namespace, `B4` workload, and `B5` caller are
taken from [the architecture](../system-architecture.md) unchanged. What crosses
each one and what is enforced at it are copied verbatim, and a test compares the two
documents rather than trusting that they agree. Two documents that drift produce a
control positioned at a boundary the other one does not have.

`B6`, the publication boundary, is new here. The architecture maps the boundaries a
running system crosses; this project crosses a sixth on every commit, and it is the
only boundary whose failures cannot be undone. A credential can be rotated. A
published record cannot be unpublished, and a reader who already has it is not a
party this project can ask to forget.

The alternative was to fold publication into `B2`, on the grounds that both concern
a contributor's machine. It was rejected because the two have opposite shapes: `B2`
protects the contributor's cluster from this project, and `B6` protects everyone
else from what this project publishes. A boundary defined by which machine it runs
on would have put them together and given them one control set.

## D2 — A control's status is derived, not asserted

Every control declares an enforcement kind — an automated test, a script guard, a
review, or nothing — and a runtime scope. Those two values determine its status
through a table committed beside the controls, and the suite recomputes every one of
them. A control that names an automated test names the file and the function, and
the suite fails if the function is not defined. A control whose status is one the
data marks as implementable names an evidence record, and the suite fails if the
record is not committed under `docs/proof/`.

This is the mechanism the whole record turns on, and it is borrowed rather than
invented: [the cost method](../../cost/cost-method.md) already derives a record's
confidence from its own inputs rather than reading a field its producer filled in,
for the same reason. A status somebody types is the status they wanted.

Its honest cost is stated rather than discovered: the derivation confirms that a
named verification **exists**. It cannot tell a strong test from a weak one, and a
control pointing at a test that asserts almost nothing satisfies it exactly as well
as one pointing at a test that asserts a great deal. What it removes is the failure
where nothing is pointed at, which is the common one.

The alternative was a two-column table of control and status, filled in by whoever
added the row. It was rejected because such a table has never once been observed to
lose a row.

## D3 — Six pod-security properties, over manifests rather than over pods

Every pod specification in this repository sets `runAsNonRoot`, a numeric user, and
the container runtime's default seccomp profile, and mounts no service account
token. Every container forbids privilege escalation, mounts its root filesystem
read-only, drops all Linux capabilities, and adds none back. A test parses every
YAML document under `deploy/` and fails if any of the eight assertions stops holding.

All of this was already true before this record; every manifest here was written
that way. What changes is that it was a habit and is now a property. A habit is
enforced by whoever writes the next manifest remembering it.

The wording of what this establishes is deliberate and it is the whole reason `EX-04`
exists: these are properties of **five committed YAML files that are smoke and trial
apparatus**, and this platform deploys none of them as a serving path. Nothing here
constrains a pod this platform deployed, because it has deployed none, and no
admission control exists to constrain one it does not own. `DR-05` carries that gap.

The alternative was to write a Kubernetes admission policy now. It was rejected
because a policy object nothing installs is a control nothing applies, and because
the local cluster's ability to enforce one has never been tested — the same untested
assumption `DR-04` records about network policy.

## D4 — Least exposure, and no authentication

No manifest here declares an Ingress, a NodePort, or a LoadBalancer service. Both
services are `ClusterIP`. Reaching anything requires a deliberate port-forward from
a machine that already holds the cluster's credential, and a test refuses a change
that would widen that.

What this is **not** is an access control, and the distinction is worth being exact
about because least exposure is the control most often described as though it were
one. It reduces what can reach the socket. It identifies nobody, authorises nothing,
and limits nothing once something is inside. `T-09` describes an unidentified caller
reaching the API and `DR-01` carries the deferral; `T-10` describes one exhausting
the runtime and `DR-02` carries that.

Authentication is deferred rather than designed, and the reason is not that it is
hard. It is that a design would have to assume a deployment model — who the callers
are, where an identity comes from, how a credential is issued and revoked — and V1's
deployment model is a port-forward on a contributor's laptop. A component designed
against that assumption would be discarded, and the discarded design would have been
published as a plan in the meantime.

## D5 — A contract carries a reference, never a secret

Already accepted in [the workload contract](../../contracts/workload-contract.md)
and already tested; this record names it as a control so that it appears in the
matrix rather than being remembered. Two properties matter here: a locator shaped
like a pasted credential is refused with a published rule identifier, and a refusal
publishes the field location and the rule, never the value it refused.

The second is the more interesting one, because it is the precedent the redaction
rules already borrow: an error message is the surface most likely to be read,
copied, and kept, and the value most likely to be in it is the one somebody put in
the wrong field. The residual risk is recorded honestly in `T-04` — the heuristic
catches a published credential prefix and a high-entropy opaque segment, and a
short, low-entropy secret has the shape of a name and passes.

## D6 — Content and secrets have nowhere to be written

Also already accepted, in [the telemetry catalog](../../telemetry/telemetry-catalog.md)
and [the redaction rules](../../telemetry/redaction.md). A prompt, a completion, a
provider error body, a secret value, an authorization header, and a document value
belong to two sensitivity classes whose permitted placement list is **empty**, so
each has nowhere it may be written, and capture is not a flag that defaults to off
but an absence with five prerequisites that do not exist.

This record adds one thing: a test that the two classes still have an empty list, so
that a future change which gives either of them a placement fails here as well as
there. A control that lives in one suite is a control one refactor away from
disappearing.

What none of it establishes is stated in `DR-12`: no logger, formatter, or sink
exists, no log line has ever been inspected, and the property that would matter —
that a real record carries only permitted fields — has no test because it has no
subject.

## D7 — Pin the digest, pin the revision, verify the hash

Every image reference in every manifest here carries a digest. The model acquisition
job pins a forty-character revision and compares a computed SHA-256 against a value
committed in this repository before any consumer reads the bytes. A test checks all
three.

`EX-01` records what this does not close. The downloader used in the one executed
trial reports that certificate validation is disabled, which ADR 0002 accepted with
the published hash as the compensating control. The argument closes only because the
hash is **committed here** rather than fetched over the same transport, and that is
the sentence worth keeping, because a hash published alongside the file it describes
defends against corruption and against nothing else.

Two further supply-chain gaps are deferred rather than papered over. Nothing scans an
image or verifies a build attestation (`DR-08`), and no check is verified to have run
from the committed dependency lockfile (`DR-07`).

`DR-07` was narrowed on 2026-08-27 rather than retired.
[ADR 0009](ADR-0009-python-toolchain.md) accepted a dependency manager and committed
a hash-bearing lockfile, so the half of that risk which said no lockfile exists is
gone. The half that remains is the half that mattered: nothing here observes which
inputs a check actually resolved, the non-Python tools this project depends on are
pinned by prose rather than by that file, and no dependency scanner has ever been
run. The control `pin-every-dependency-with-a-committed-lockfile` therefore stays
`deferred`, because a committed file is not a result.

## D8 — The cluster boundary is guarded by identity, not by a name

The environment scripts confirm that every node the reachable API server reports is a
container the cluster tool labelled for this project's cluster, and refuse to
continue otherwise. Every `kubectl` call goes through a wrapper that passes this
project's kubeconfig and context explicitly, so no invocation inherits an ambient one.

`EX-02` records the bypass in the open: a second cluster deliberately given this
project's name satisfies every check. That is accepted rather than fixed, because the
threat this guard exists for is a stale context and a mistyped command on the
contributor's own machine, and nothing running on that machine can defend against
the contributor who owns it.

## D9 — The publication boundary is defended by what is committed

Four properties, all tested: nothing under the project kubeconfig, diagnostics, or
tool cache directories is committed and each of those paths is ignored; no file
carries a Windows user directory or a POSIX home directory; no file carries a model
artifact extension; and the secret-scan configuration is committed with an allowlist
whose every path resolves.

The fourth is the one that has to be described precisely, and `T-15` does: **no run
of the scanner is recorded.** A configuration file is not a result. The security-scan
layer of [the test strategy](../../testing/test-strategy.md) stays `planned` for
exactly that reason, the claim it would support stays `planned` and may not be cited,
and `DR-11` carries the gap. `EX-03` records that the allowlist covers two
directories wholesale, which is the right shape for the credential-shaped fixtures in
them and the wrong shape for a real credential committed beside one.

Private planning material is the part of this boundary a test cannot reach. A path is
a pattern; unpublished strategy is not. That control is a reviewer reading the diff,
and it is marked `review-enforced` rather than promoted.

## D10 — A deferred risk is a register entry, not an omission

Twelve risks are carried rather than reduced. Each declares the boundary it sits at,
the threats it leaves open, why V1 defers it, what would have to be true to close it,
and — the field that does the work — **what may not be claimed while it stands**. A
test requires all of them, and requires the last one to be phrased as a denial.

Ten of the twelve are marked as blocking production use. That is not a schedule; it
is the honest reading of a system with no authentication, no rate limit, no network
policy, no audit trail, and no dependency pinning.

The rule a test cannot enforce is the one that matters most, and it is written down
as `review` rather than dressed up: a risk leaves this register when a control
reduces it, and never because the register had become an uncomfortable thing to
publish.

## D11 — An exception is argued, not absorbed

Four exceptions are recorded. Each names where it was accepted, the compensating
control that makes it tolerable, what remains undefended anyway, and the condition
under which it should be revisited. A test refuses an exception missing any of them
and refuses one whose compensating control is not a control this baseline declares.

This mirrors the status ADR 0002 already reaches — `Accepted, with one recorded
exception` — and for the same reason. The alternatives are both dishonest: leaving
the weakness out implies it was handled, and refusing the decision denies work that
was really done.

## D12 — Reserved vocabulary

Twelve terms — the adjectives of a posture rather than the names of properties — may
appear in **every Markdown document committed here**, and in the committed data, only
inside a sentence that denies them. A test joins wrapped lines back into sentences,
skips fenced code, and fails on a reserved term in a sentence carrying no denial.

The list is not a style preference. Each term is one somebody reaches for while
writing a heading, none of them changes a property, and each converts a set of
narrow checks into a claim about a system. It is the same mechanism [the cost
method](../../cost/cost-method.md) uses to keep the vocabulary of an invoice
attached to the one basis entitled to it.

**The scope of the scan is itself a decision, and the first version of it was
wrong.** This rule was originally enforced over the four security documents and this
record — which would have passed while the top-level README, `SECURITY.md`, or an
architecture record described a posture this project does not have. Those are the
documents a reader reaches first, and none of them lives under `docs/security/`. A
check scoped to the documents least likely to overclaim is the failure `T-18` names,
occurring inside the control for `T-18`. The scan now reads every Markdown document
committed here, and a second test fails if that coverage narrows.

Its limits are still real and worth stating: it catches a listed word in a Markdown
document. A claim made in a word nobody listed, in a file that is not Markdown, or in
a slide survives it untouched, and `the-vocabulary-check-reads-markdown-only` records
that as a limitation rather than leaving it implied.

## D13 — Who signs off a control: not decided

No public maintainer roster or `CODEOWNERS` file exists, which is a governance gap
already recorded in [CONTRIBUTING](../../../CONTRIBUTING.md) and
[the repository governance document](../../governance/repository.md). The seven
evidence owners this baseline assigns are the ones
[the test strategy](../../testing/test-strategy.md) declares, and they are **roles**.
An owner here identifies which area a control's evidence belongs to, not who signs it
off. Naming a person is blocked on the same gap that blocks naming a reviewer, and
inventing one would be worse than the gap.

## D14 — Where a pod-security property is enforced: not decided here

When a rendering path exists, a pod-security property could be enforced by the
renderer, by an admission policy in the cluster, or by both. Answering it now would
decide a component boundary that ADR 0004 owns, and ADR 0004 deliberately leaves the
equivalent ownership question open. `EX-04` records that the check must move from
committed manifests to rendered output at that point, which is the part this record
can commit to without deciding who does it.

## Consequences

- **Three trust boundaries the architecture left unowned now have an owner**, and
  `B3`, `B4`, and `B5` point at this record instead of forward at a decision that had
  not been made.
- **Thirty-two controls exist, and twenty-two of them are enforced by something.**
  Ten act over committed documents, ten over manifests, two on the host through the
  environment scripts, three by review alone, three are specified for components that
  do not exist, and four are deferred outright. The distribution is the finding.
- **A habit became a property.** The eight pod-security assertions and the digest pin
  held over every manifest here before this change, by convention. A convention is
  enforced by memory; this is now enforced by a suite.
- **The register is long and it is meant to be.** Twelve deferred risks, ten of them
  blocking production use, and four accepted exceptions. A shorter register at this
  stage of a project would mean less enumeration, not less risk.
- **One new public claim, at the narrowest level that is honest.** The claim and test
  matrix gains `a-security-control-cannot-claim-enforcement-it-does-not-have`,
  certified at `C0` by the documentation layer. It certifies a committed baseline and
  nothing about whether anything is defended.
- **Two existing security claims stay `planned`, and a test now holds them there.**
  `no-prompt-response-or-secret-reaches-a-log-or-a-metric` needs components that do
  not exist, and `no-credential-or-model-artifact-enters-public-history` needs a
  scanner run nobody has performed.
- **Four of fifteen rules are enforced by review alone**, and a review is enforced
  only when the reviewer remembers it. They are marked rather than promoted, which is
  the less comfortable and more true option.

## Compatibility impact

None to any published contract. This record adds no field to the workload contract,
no signal to the telemetry catalog, no term to the cost method, and no schema of its
own. `docs/security/security-baseline.v1alpha1.json` carries the `v1alpha1` contract
version because every machine-readable artifact in this repository does, and it is
**not** published as a contract: nothing consumes it, no compatibility obligation
attaches to it, and [the contracts index](../../contracts/README.md) does not list it.

Three existing artifacts are edited rather than replaced. The test strategy data
gains one path, one command, and one claim; the claim and test matrix gains the row
that goes with it; and the architecture's boundary table has three owner cells that
pointed at "the security baseline decision" and now point at this record. No layer,
lane, marker, evidence class, or certification level moves, and no boundary changes
what crosses it or what is enforced at it.

## Security considerations

This record is the security consideration for the repository, so the section states
what deciding it changes and what it does not.

**What it changes.** Three unowned boundaries acquire an owner. Twenty-two controls
acquire a verification that a test confirms exists. Eight pod-security assertions and
a digest pin become properties a change has to break deliberately. Twelve risks move
from unstated to registered, each with what may not be claimed while it stands.

**What it does not change.** Nothing here defends a running system, because there is
none. The most consequential controls in the register are the ones with no
verification at all — no caller is identified, no request is authorised, no traffic
is policed, and nothing is logged, so a failure of any control here would leave no
trace to find it by. `DR-12` is written last in the register and is arguably first in
importance: a control whose failure is invisible cannot be shown to have held.

**What publishing this costs.** A threat model is a map of where to push. This one is
published anyway, for two reasons. The system it maps does not exist and cannot be
attacked, and the alternative — a project that knows its gaps and publishes only its
controls — is the failure this record was written to prevent. The one thing that
genuinely follows is that a reader who finds a real problem here has nowhere private
to report it, which is why the missing reporting channel appears in the register as
`DR-11`'s neighbour rather than as a footnote.

**What must not be inferred.** No control here has ever acted inside a serving
system. No scanner, image scanner, or dependency auditor has been run and recorded.
No assessment by an outside party has ever been performed. Every runtime observation
behind `B1` and `B4` comes from one trial, on one host, on one day.

## Evidence

| Claim | Evidence | Class | Ceiling |
|---|---|---|---|
| The baseline is internally consistent and derives every control status | [`tests/security/`](../../../tests/security/) over the committed data | `local-static` | `C0` |
| Every manifest is digest-pinned and carries eight pod-security assertions | The same suite, over every YAML document under `deploy/` | `local-static` | `C0` |
| No manifest exposes a service outside the cluster | The same suite | `local-static` | `C0` |
| The five mapped boundaries match the architecture | The same suite, comparing the two documents verbatim | `local-static` | `C0` |
| The change itself was validated | [Change validation record](../../proof/security/v1-s0-009-pr1-validation.md) | `local-static` | `C0` |
| The runtime pod ran non-root with a read-only root filesystem, once | [Runtime feasibility record](../../proof/serving/v1-s0-003-pr2-runtime-feasibility.md) | `local-real-cpu` | `C2`, for one host on one day |
| The cluster guard refuses a cluster this project did not create | [Cluster smoke record](../../proof/environment/v1-s0-002-pr2-cluster-smoke.md) | `local-real-cpu` | `C2`, for one host |

**No evidence exists for anything else here.** There is no scanner output, no
assessment report, no admission-control result, no log record, and no observation of
any control acting inside a system serving a request.

## Related records

| Topic | Document |
|---|---|
| The threat model this decision implements | [Threat model](../../security/threat-model.md) |
| Every control, its verification, and its owner | [Control matrix](../../security/control-matrix.md) |
| What V1 does not defend, and the exceptions it accepts | [Deferred risks and exceptions](../../security/deferred-risks.md) |
| The boundaries this record adopts | [System architecture](../system-architecture.md) |
| What may never be written down about a request | [Redaction rules](../../telemetry/redaction.md) |
| What a result may be used to claim | [Certification levels](../../testing/certification.md) |
| How to report a problem, and why you cannot yet | [SECURITY.md](../../../SECURITY.md) |
