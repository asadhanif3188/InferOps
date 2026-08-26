# V1 threat model

Status: **accepted**, in
[ADR 0008](../architecture/decisions/ADR-0008-v1-security-baseline.md). It names what
this project protects, who it is protected from, and where each boundary sits. It
does **not** establish that anything is defended, and roughly a third of the threats
below have no control at all.

> [!WARNING]
> Nothing in this repository authenticates a caller, authorises a request, enforces
> a network policy, or applies a security context to a pod it deployed — because
> nothing here deploys a pod or serves a request. No scanner has been run and
> recorded. No assessment by an outside party has ever been performed, and a
> document review is not one.
>
> What is really enforced is enforced over committed files, over five YAML
> manifests, and by two shell functions. That is a narrow and real thing, and the
> distance between it and a defended system is
> [the deferred-risk register](deferred-risks.md).

The authoritative form of everything here is
[`security-baseline.v1alpha1.json`](security-baseline.v1alpha1.json). This document
and that file are compared in both directions by
[`tests/security/`](../../tests/security/); neither can gain or lose a threat, a
control, or a risk without the other failing.

## What this document is for

A reviewer should be able to answer five questions from it without reading a plan:

1. What is worth protecting here, and who owns each of those things?
2. Who is trusted with what, and who is trusted with nothing?
3. Where are the boundaries, and which of them does the architecture already draw?
4. What can go wrong at each boundary, concretely enough to argue about?
5. For each of those, is there a control — and if not, who wrote down why not?

Question five is the one this project keeps answering in public.
[The control matrix](control-matrix.md) holds the answers where a control exists;
[the deferred-risk register](deferred-risks.md) holds them where one does not.

## Assets

Eleven things worth protecting. Each names the boundary it sits behind and the worst
outcome that follows from losing it — not a score, because a severity number here
would be invented and an invented number applied consistently still ranks nothing.

| Asset | What it is | Boundary | Owned by |
|---|---|---|---|
| `model-artifact` | One weight file, pinned by revision and per-file SHA-256 | B1 | An external publisher; this project owns only the pin |
| `runtime-image` | The serving runtime image index digest, and the utility image digest | B1 | An external publisher; this project owns only the digest |
| `workload-document` | A submitted contract describing a workload | B3 | The workload owner |
| `secret-material` | The values behind `spec.security.secretRefs` | B3 | The workload owner |
| `prompt-and-response-content` | Prompts, responses, and anything quoting them | B5 | The caller, and whoever the caller answers to |
| `telemetry-signals` | The metrics, logs, and spans a running V1 would emit | B3 | Security |
| `evidence-record` | A committed record a public claim rests on | B6 | Security |
| `public-history` | Every commit this project has pushed, including reverted ones | B6 | Security |
| `contributor-kubeconfig` | The project-scoped kubeconfig, carrying a client key | B2 | The contributor |
| `local-cluster` | The single-node cluster the environment scripts create | B2 | The contributor |
| `model-cache-volume` | A prerequisite volume holding one hash-verified artifact | B3 | Environment |

Two of them deserve a sentence beyond the row. **The evidence record is a stricter
surface than a log store, not a looser one** — it is public, permanent, and not
deletable in any useful sense, which is why a tenant identifier is excluded from one
and permitted in the other. And **the model cache outlives a release by design**,
which makes "verified once" and "verified" two different states that a future
consumer will be tempted to confuse.

## Actors

| Actor | Trusted to | Trusted with nothing when it comes to |
|---|---|---|
| Workload owner | Author a document and own the secret material its references point at | Asserting a tenant, a classification, or an entitlement. Each is a request written into a document |
| Platform contributor | Operate their own machine and their own cluster | Being incapable of a mistake. The guards exist for a stale context, not for an attacker |
| Artifact publisher | Nothing | Serving the same bytes twice under the same name |
| Artifact transport | Nothing | Being authenticated. In the one executed trial, certificate validation was reported as disabled |
| Caller | Nothing, and identified as nothing | Being who it says it is, because nothing asks |
| Public reader | Reading everything committed, forever, including what was later deleted | Being a party this project can ask to forget something |

The last row is the one that shapes `B6`. A credential can be rotated after it is
published; a record cannot be unpublished, so the control has to be what gets
committed rather than what gets retracted.

## Trust boundaries

Five of these come from [the architecture](../architecture/system-architecture.md)
unchanged — what crosses each one and what is enforced at it are copied verbatim,
and a test compares the two documents rather than trusting that they agree. The
sixth is new here.

| Boundary | What crosses it | Enforced today | Owner |
|---|---|---|---|
| B1 artifact | Container images, model weights | Digest and hash pinning, hash verified before use | serving |
| B2 cluster | Every platform action on Kubernetes | Cluster identity guard and scoped teardown, in the environment scripts | environment |
| B3 namespace | Everything a release installs | Nothing. A network policy is planned and its enforcement by the local cluster's network plugin is untested | security |
| B4 workload | Process privilege inside a pod | Proven once for the runtime pod in a trial. Nothing enforces it for a pod this platform deploys, because it deploys none | security |
| B5 caller | Inference requests and their responses | **Nothing.** There is no authentication, no authorization, no rate limit, and no tenant isolation | security |
| B6 publication | Every file, record, and message this project commits or pushes in public | Ignore rules for host state and the project kubeconfig, a committed secret-scan configuration, and a suite that refuses a tenant identifier or a personal filesystem path in a committed file | security |

**B6 is not in the architecture, and the reason is stated rather than assumed.** That
document maps the five boundaries a running system crosses. This project crosses a
sixth on every commit, and it is the only boundary whose failures cannot be undone.
Folding it into B2 was rejected: B2 protects the contributor's cluster from this
project, and B6 protects everyone else from what this project publishes. They have
opposite shapes and cannot share a control set.

## Assumptions this model rests on

Each of these is a thing taken as true without checking it here. Where one turns out
to be false, the controls resting on it are worth no more than the assumption.

- **The committed hash is authentic**, because it is in this repository rather than
  fetched over the transport that delivers the file it describes. If the repository
  itself is compromised, every integrity argument at B1 fails at once.
- **The container runtime isolates a process it starts.** Nothing here tests that,
  and the eight pod-security assertions are meaningful only to the extent it holds.
- **A contributor's machine is theirs.** The cluster guard defends against a mistake
  on it, and nothing running on that machine could defend against its owner.
- **A published document is read by somebody who takes its qualifications with it.**
  This assumption is known to be weak, which is why the qualifications are structural
  — a derived status, an empty placement list, a reserved word list — rather than
  paragraphs a reader is asked to remember.
- **The local cluster behaves like Kubernetes** for the properties named here. The
  one property where this is explicitly *not* assumed is network-policy enforcement,
  which `DR-04` records as untested.

## Threats

Twenty-two, in six categories. Each names the asset, the boundary, the actor, the
controls that address it, and the deferred risk that carries whatever the controls do
not. A threat with neither a control nor a deferred risk is refused by a test,
because that is the shape of a threat nobody decided about.

| ID | Threat | Category | Asset | Boundary | Actor | Controls | Deferred |
|---|---|---|---|---|---|---|---|
| T-01 | The weight file is substituted in transit | tampering | `model-artifact` | B1 | Transport | `verify-artifact-hash-before-use`, `pin-model-revision` | DR-06 |
| T-02 | A moving tag resolves to a different image | tampering | `runtime-image` | B1 | Publisher | `pin-image-by-digest`, `verify-artifact-provenance` | DR-08 |
| T-03 | A publisher withdraws or cannot serve an artifact | denial-of-service | `model-artifact` | B1 | Publisher | none | DR-09 |
| T-04 | A secret value is pasted into a workload document | information-disclosure | `secret-material` | B3 | Workload owner | `refuse-a-secret-value-in-a-contract` | — |
| T-05 | A refusal quotes the value it refused | information-disclosure | `secret-material` | B3 | Workload owner | `never-echo-a-document-value-in-a-refusal` | — |
| T-06 | A secret or a prompt is written to a log, a metric, or a trace | information-disclosure | `prompt-and-response-content` | B3 | Contributor | `no-secret-or-content-has-a-telemetry-placement`, `content-capture-is-disabled-and-has-no-enabling-path` | DR-12 |
| T-07 | An upstream error body is passed through verbatim | information-disclosure | `prompt-and-response-content` | B5 | Publisher | `do-not-pass-through-a-provider-error-body` | — |
| T-08 | A tenant identifier supplied by a caller is trusted | elevation-of-privilege | `workload-document` | B5 | Workload owner | `a-tenant-is-a-request-not-an-assertion`, `no-tenant-identifier-in-a-committed-record` | DR-03 |
| T-09 | An unidentified caller reaches the inference API | spoofing | `prompt-and-response-content` | B5 | Caller | `least-exposure-no-manifest-publishes-a-service`, `authenticate-and-authorise-a-caller` | DR-01 |
| T-10 | A caller exhausts the runtime's capacity | denial-of-service | `local-cluster` | B5 | Caller | `limit-what-one-caller-may-consume` | DR-02 |
| T-11 | A container runs with more privilege than it needs | elevation-of-privilege | `local-cluster` | B4 | Publisher | six pod-security controls | DR-05 |
| T-12 | A pod talks to anything it likes inside and outside the cluster | information-disclosure | `local-cluster` | B3 | Publisher | `network-policy-in-the-release-namespace` | DR-04 |
| T-13 | A platform action reaches a cluster this project did not create | elevation-of-privilege | `local-cluster` | B2 | Contributor | `refuse-to-act-on-a-cluster-this-project-did-not-create`, `scope-every-kubectl-call-to-the-project-kubeconfig` | — |
| T-14 | The project kubeconfig is committed | information-disclosure | `contributor-kubeconfig` | B6 | Contributor | `ignore-and-refuse-generated-host-state`, `no-credential-or-artifact-in-public-history` | DR-11 |
| T-15 | A credential or a model artifact enters public history | information-disclosure | `public-history` | B6 | Contributor | `no-credential-or-artifact-in-public-history`, `ignore-and-refuse-generated-host-state` | DR-11 |
| T-16 | Private planning material is published | information-disclosure | `public-history` | B6 | Contributor | `no-personal-filesystem-path-in-a-committed-file`, `review-the-public-diff-for-private-material` | — |
| T-17 | An evidence record discloses something permanently | information-disclosure | `evidence-record` | B6 | Contributor | `no-tenant-identifier-in-a-committed-record`, `redact-before-promoting-raw-output` | — |
| T-18 | A control is believed because it is written down | repudiation | `evidence-record` | B6 | Public reader | `derive-a-control-status-from-its-verification`, `no-security-claim-without-a-named-verification` | — |
| T-19 | A dependency is resolved rather than pinned | tampering | `public-history` | B1 | Publisher | `pin-every-dependency-with-a-committed-lockfile` | DR-07 |
| T-20 | Nothing records who did what | repudiation | `telemetry-signals` | B5 | Caller | `record-what-the-platform-did` | DR-12 |
| T-21 | A stale cache is trusted instead of a hash | tampering | `model-cache-volume` | B3 | Contributor | `verify-artifact-hash-before-use` | — |
| T-22 | A secret reference names a place nobody manages | information-disclosure | `secret-material` | B3 | Workload owner | `refuse-a-secret-value-in-a-contract` | DR-10 |

Six of the twenty-two name only a control with no verification at all —
`verify-artifact-provenance`, `authenticate-and-authorise-a-caller`,
`limit-what-one-caller-may-consume`, `pin-every-dependency-with-a-committed-lockfile`,
`record-what-the-platform-did`, and `network-policy-in-the-release-namespace`. Those
rows are naming the gap in the shape of a control so that the register has something
to point at, and the matrix marks every one of them `deferred` or `specified-only`.

## Five abuse cases worth reading in full

The table above is a map. These five are the ones where the mechanism, rather than
the category, is the point.

### T-18 — A control is believed because it is written down

There is no attacker. Somebody adds a control to a document, nobody records what
verifies it, and a reader six months later counts the list. The project ends up
publishing a posture nobody claimed in a sentence, assembled entirely out of true
rows.

This is the threat the whole baseline is shaped around, and the control is
arithmetic: a status is derived from the enforcement kind and runtime scope a control
declares, the named test function has to exist, and a status the data marks as
implementable has to name a committed evidence record. What the derivation cannot do
is judge a test's quality, and that limitation is written into the register rather
than left for a reader to discover.

### T-11 — A container runs with more privilege than it needs

The abuse case is a manifest with no security context: the image's own defaults
apply, which means root, a writable root filesystem, the default capability set, and
a mounted service account token. A compromised process starts from root with a
cluster credential already in the filesystem.

Every manifest here sets all eight properties, and a test parses them rather than
trusting the habit. The exact wording of what that establishes matters, and `EX-04`
carries it: these are properties of **five committed YAML files**, all of them smoke
or trial apparatus. This platform deploys none of them as a serving path, so nothing
here constrains a pod it deployed, and no admission control exists to constrain one
it does not own.

### T-08 — A tenant identifier supplied by a caller is trusted

A workload document names a tenant. A component reads it and uses the value for
isolation, attribution, or authorisation without asking whether the author was
entitled to name it. One tenant's activity becomes another's.

Nothing validates a tenant, because there is no entitlement source and no component
that would consult one. What exists instead is two narrower properties: the rule is
written down for the first component that reads the field, and the sensitivity class
the telemetry catalog already assigned means a tenant identifier has no permitted
placement in a committed record, so it cannot reach the one surface that is
permanent. `DR-03` carries the rest.

### T-01 — The weight file is substituted in transit

The acquisition job fetches roughly 1.7 GiB over a transport that, in the one
executed trial, reported certificate validation as disabled. Anything on that path
can return a different file of the same name, and every result produced afterwards
describes a model nobody selected.

The compensating control is a SHA-256 comparison before any consumer reads the bytes.
The argument closes for exactly one reason, and it is worth being precise about: the
expected hash is **committed in this repository** rather than fetched alongside the
file. A hash published beside the artifact it describes defends against corruption
and against nothing else. `EX-01` records the exception; `DR-06` records what stays
open.

### T-15 — A credential or a model artifact enters public history

A fixture, a debugging file, or a downloaded weight file is committed and later
deleted, which removes it from the tree and not from the history. A published
credential has to be rotated rather than retracted; a published artifact cannot be
either.

Four properties are tested: ignored paths are ignored and nothing is committed under
them, no file carries a personal filesystem path, no file carries a model artifact
extension, and the secret-scan configuration's allowlist resolves. The fifth thing a
reader will assume is tested is not: **no run of the scanner is recorded**, the
security-scan layer of [the test strategy](../testing/test-strategy.md) is `planned`
for that reason, and `DR-11` carries it. A configuration file is not a result.

## What this model does not do

- **It does not score anything.** No threat carries a likelihood, a severity, or a
  risk rating. Every such number here would be invented, and a test refuses one.
- **It is not exhaustive.** Twenty-two threats were enumerated because each is a
  failure somebody would plausibly reach. A threat nobody thought of is a threat
  nobody modelled, and nothing in the method guarantees coverage.
- **It does not describe an attack that has happened.** No incident, real credential,
  real prompt, or real host appears as an illustration. Every abuse case is built out
  of this project's own assets, deliberately.
- **It certifies nothing about a running system.** The claim it supports is
  `a-security-control-cannot-claim-enforcement-it-does-not-have`, certified at `C0`
  by the documentation layer, and that claim is about a committed baseline.

## Related records

| Topic | Document |
|---|---|
| The decision this document implements | [ADR 0008](../architecture/decisions/ADR-0008-v1-security-baseline.md) |
| Every control, its verification, and its owner | [Control matrix](control-matrix.md) |
| What is undefended, and the exceptions accepted | [Deferred risks and exceptions](deferred-risks.md) |
| The authoritative form of all of it | [`security-baseline.v1alpha1.json`](security-baseline.v1alpha1.json) |
| The boundaries this adopts | [System architecture](../architecture/system-architecture.md) |
| What may never be written about a request | [Redaction rules](../telemetry/redaction.md) |
| What a result may be used to claim | [Certification levels](../testing/certification.md) |
| How to report a problem, and why you cannot yet | [SECURITY.md](../../SECURITY.md) |
