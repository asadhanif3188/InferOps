# The control and verification matrix

Status: **accepted**, in
[ADR 0008](../architecture/decisions/ADR-0008-v1-security-baseline.md). It lists
every V1 security control, the boundary it acts at, what verifies it, who owns that
verification, and which record it rests on. Twenty-two of thirty-two controls are
enforced by something. The other ten are the reason
[the deferred-risk register](deferred-risks.md) exists.

The authoritative form is
[`security-baseline.v1alpha1.json`](security-baseline.v1alpha1.json). This document
and that file are compared in both directions by
[`tests/security/`](../../tests/security/); neither can gain or lose a control
without the other failing.

## How a status is reached

**A control does not choose its status.** It declares two things — how it is
verified, and where it acts — and the status is the value a committed table gives
for that pair. The suite recomputes every one of them, and a declared status that
disagrees with the derived one is a failing test rather than a judgement call.

| Enforcement kind | What it means | Level |
|---|---|---|
| `automated-test` | A test in this repository reads the thing and fails if the property stops holding. The control names the file and the function, and the suite fails if the function is not defined | automated |
| `script-guard` | A shell function in the environment scripts refuses to continue. The control names the script and the function | automated |
| `review` | A reviewer applies the rule. Nothing reads it | review |
| `none` | Nothing verifies this control | none |

| Runtime scope | Where the control acts |
|---|---|
| `repository-only` | On files committed here, and on nothing else |
| `host-scripts` | When a contributor runs the environment scripts on their own machine |
| `trial-apparatus` | On the manifests this repository publishes, every one of which is smoke or trial apparatus |
| `running-system` | Inside a system this platform deployed and is serving requests. **No control has this scope**, and a test refuses one that claims it |

The pair derives the status:

| Status | Meaning | May be called implemented |
|---|---|---|
| `enforced-over-documents` | A test fails if the property stops holding over committed files | yes |
| `enforced-over-manifests` | A test fails if any manifest here stops carrying the property. It says nothing about a pod this platform deployed | yes |
| `enforced-on-the-host` | An environment script refuses to continue, on the machine of whoever runs it | yes |
| `review-enforced` | A reviewer applies it. Nothing else does | no |
| `specified-only` | Decided and written down for a component that does not exist | no |
| `deferred` | V1 takes no action. The risk is carried and recorded rather than reduced | no |

An enforcement level of `none` derives `specified-only` when the control names the
component it is written for, and `deferred` when it names none. A control cannot be
both: a specification without a subject is a deferral wearing a specification's
clothes.

Two further rules the suite applies. A control whose status may be called
implemented has to name an evidence record committed under
[`docs/proof/`](../proof/), and every control has to state **what it does not
verify** — the field that stops a narrow check being read as a broad one.

## What is enforced over committed documents

Ten controls. A test in this repository reads the artifact and fails if the property
stops holding. Four of them were already enforced by suites that existed before this
baseline; naming them here puts them in the matrix rather than leaving them
remembered.

| Control | Boundary | Verified by | Owner | Evidence |
|---|---|---|---|---|
| `refuse-a-secret-value-in-a-contract` | B3 | `test_a_credential_shaped_locator_is_caught` | contracts | [contracts](../proof/contracts/v1-s0-004-pr2-validation.md) |
| `never-echo-a-document-value-in-a-refusal` | B3 | `test_no_finding_quotes_a_value_from_the_document` | contracts | [contracts](../proof/contracts/v1-s0-004-pr2-validation.md) |
| `no-secret-or-content-has-a-telemetry-placement` | B3 | `test_a_forbidden_field_is_allowed_nowhere` | security | [telemetry](../proof/telemetry/v1-s0-007-pr1-validation.md) |
| `content-capture-is-disabled-and-has-no-enabling-path` | B5 | `test_content_capture_is_disabled_and_has_no_policy_to_enable_it` | security | [telemetry](../proof/telemetry/v1-s0-007-pr1-validation.md) |
| `no-tenant-identifier-in-a-committed-record` | B6 | `test_no_committed_record_carries_a_tenant_identifier` | security | [cost](../proof/cost/v1-s0-008-pr1-validation.md) |
| `ignore-and-refuse-generated-host-state` | B6 | `test_no_committed_file_is_generated_host_state` | security | [security](../proof/security/v1-s0-009-pr1-validation.md) |
| `no-credential-or-artifact-in-public-history` | B6 | `test_the_secret_scan_configuration_is_committed_and_its_allowlist_resolves` | security | [security](../proof/security/v1-s0-009-pr1-validation.md) |
| `no-personal-filesystem-path-in-a-committed-file` | B6 | `test_no_committed_file_carries_a_personal_filesystem_path` | security | [security](../proof/security/v1-s0-009-pr1-validation.md) |
| `derive-a-control-status-from-its-verification` | B6 | `test_declared_control_status_equals_derived_control_status` | security | [security](../proof/security/v1-s0-009-pr1-validation.md) |
| `no-security-claim-without-a-named-verification` | B6 | `test_a_reserved_term_appears_only_where_it_is_denied` | security | [security](../proof/security/v1-s0-009-pr1-validation.md) |

The seventh row is the one to read carefully, and its own `whatItDoesNotVerify`
field says so: it verifies that a secret-scan configuration is committed and that its
allowlist resolves. It does **not** verify that a scanner has ever been run, because
none has. A configuration file is not a result.

## What is enforced over the manifests

Ten controls, over every YAML document under [`deploy/`](../../deploy/). The suite
parses each one, walks every pod specification and container, and fails on a missing
or wrong field.

| Control | Boundary | Verified by | Owner | Evidence |
|---|---|---|---|---|
| `pin-image-by-digest` | B1 | `test_every_manifest_image_is_pinned_by_digest` | serving | [security](../proof/security/v1-s0-009-pr1-validation.md) |
| `pin-model-revision` | B1 | `test_the_model_acquisition_job_pins_a_revision_and_verifies_a_hash` | serving | [serving](../proof/serving/v1-s0-003-pr2-runtime-feasibility.md) |
| `verify-artifact-hash-before-use` | B1 | `test_the_model_acquisition_job_pins_a_revision_and_verifies_a_hash` | serving | [serving](../proof/serving/v1-s0-003-pr2-runtime-feasibility.md) |
| `run-as-non-root` | B4 | `test_every_pod_spec_carries_every_required_pod_security_field` | security | [security](../proof/security/v1-s0-009-pr1-validation.md) |
| `seccomp-runtime-default` | B4 | `test_every_pod_spec_carries_every_required_pod_security_field` | security | [security](../proof/security/v1-s0-009-pr1-validation.md) |
| `do-not-mount-a-service-account-token` | B4 | `test_every_pod_spec_carries_every_required_pod_security_field` | security | [security](../proof/security/v1-s0-009-pr1-validation.md) |
| `forbid-privilege-escalation` | B4 | `test_every_container_carries_every_required_container_security_field` | security | [security](../proof/security/v1-s0-009-pr1-validation.md) |
| `read-only-root-filesystem` | B4 | `test_every_container_carries_every_required_container_security_field` | security | [security](../proof/security/v1-s0-009-pr1-validation.md) |
| `drop-all-capabilities` | B4 | `test_every_container_carries_every_required_container_security_field` | security | [security](../proof/security/v1-s0-009-pr1-validation.md) |
| `least-exposure-no-manifest-publishes-a-service` | B5 | `test_no_manifest_exposes_a_service_outside_the_cluster` | security | [security](../proof/security/v1-s0-009-pr1-validation.md) |

**Every manifest here is smoke or trial apparatus.** That sentence is why this status
exists as something separate from `enforced-over-documents`, and it is what `EX-04`
records. This platform deploys none of these as a serving path, so nothing in this
block establishes a property of a pod it deployed — it has deployed none — and no
admission control exists to establish one for a pod it does not own. `DR-05` carries
that gap.

The last row is the other one worth reading precisely. Least exposure means both
services are `ClusterIP`, no Ingress is declared, and no node port is pinned.
Reaching anything requires a deliberate port-forward from a machine that already
holds the cluster's credential. It is a reduction in reachability and it is not an
access control: it identifies nobody and limits nothing once something is inside.

## What is enforced on the contributor's host

| Control | Boundary | Verified by | Owner | Evidence |
|---|---|---|---|---|
| `refuse-to-act-on-a-cluster-this-project-did-not-create` | B2 | `inferops::assert_target_cluster` in [`lib.sh`](../../scripts/environment/lib.sh) | environment | [environment](../proof/environment/v1-s0-002-pr2-cluster-smoke.md) |
| `scope-every-kubectl-call-to-the-project-kubeconfig` | B2 | `inferops::kubectl` in [`lib.sh`](../../scripts/environment/lib.sh) | environment | [environment](../proof/environment/v1-s0-002-pr2-cluster-smoke.md) |

The first confirms that every node the reachable API server reports is a container
the cluster tool labelled for this project's cluster. A context name is a label
somebody chose; the container label is what the guard actually reads. `EX-02` records
its bypass in the open: a second cluster deliberately given this project's name
satisfies every check, and nothing running on a contributor's machine could defend
against the contributor who owns it.

## What is enforced by review alone

Three controls. Marking them as tested would be the more comfortable option and the
less true one.

| Control | Boundary | Owner | Why no test reaches it |
|---|---|---|---|
| `do-not-pass-through-a-provider-error-body` | B5 | platform | The adapter that would do this has not been written, so there is nothing to read |
| `review-the-public-diff-for-private-material` | B6 | security | A path is a pattern and is checkable; unpublished strategy is not |
| `redact-before-promoting-raw-output` | B6 | security | Nothing reads a promoted record against the raw output it came from |

## What is specified for a component that does not exist

Three controls. The rule is decided so that the first component to touch the surface
inherits it, and nothing enforces it because there is nothing to enforce it on.

| Control | Boundary | Specified for | Owner |
|---|---|---|---|
| `a-tenant-is-a-request-not-an-assertion` | B5 | The platform API, which does not exist; the domain carries a declared tenant and checks no entitlement | platform |
| `network-policy-in-the-release-namespace` | B3 | The Helm chart, which has not been written | platform |
| `record-what-the-platform-did` | B5 | The platform API, which does not exist | security |

The middle one carries a second gap beyond its own absence: whether the local
cluster's network plugin would enforce a policy object at all has never been tested.
`DR-04` records both halves, because a chart that installs a policy the cluster
ignores is worse than no chart, in that it looks like a control.

## What is deferred outright

Four controls. V1 takes no action, and each has a register entry stating why, what
would have to be true, and what may not be claimed while it stands.

| Control | Boundary | Owner | Register entry |
|---|---|---|---|
| `authenticate-and-authorise-a-caller` | B5 | platform | [DR-01](deferred-risks.md) |
| `limit-what-one-caller-may-consume` | B5 | platform | [DR-02](deferred-risks.md) |
| `verify-artifact-provenance` | B1 | serving | [DR-08](deferred-risks.md) |
| `pin-every-dependency-with-a-committed-lockfile` | B1 | environment | [DR-07](deferred-risks.md) |

## Owners

Seven evidence owners are declared in
[the test strategy data](../testing/test-strategy.v1alpha1.json), and this matrix
uses five of them: contracts, environment, serving, platform, and security. A test
refuses a control naming an owner the strategy does not declare.

These are **roles, not people**. No public maintainer roster or `CODEOWNERS` file
exists — a governance gap recorded in [CONTRIBUTING](../../CONTRIBUTING.md) — so an
owner here identifies which area a control's evidence belongs to, not who signs it
off. That is `D13` in the decision record, and it is explicitly not decided.

## The rules, and whether each is really enforced

Fifteen rules. Eleven are enforced by a test over the committed baseline. Four are
enforced by review alone, and are marked as such rather than quietly promoted.

| Rule | Enforced by |
|---|---|
| `no-security-posture-is-claimed` | a test |
| `documented-is-not-implemented` | a test |
| `a-configuration-is-not-a-result` | a test |
| `no-control-claims-a-record-that-does-not-exist` | a test |
| `no-control-acts-inside-a-running-system` | a test |
| `no-user-content-or-secret-is-recorded` | a test |
| `no-manifest-exposes-a-service` | a test |
| `no-personal-path-or-host-state-is-committed` | a test |
| `every-exception-carries-a-compensating-control-and-a-residual-risk` | a test |
| `every-threat-is-controlled-or-deferred-in-public` | a test |
| `no-security-claim-outruns-its-certification-level` | a test |
| `a-tenant-supplied-value-is-never-trusted` | **review only** |
| `no-vulnerability-figure-is-published` | **review only** |
| `a-deferred-risk-leaves-the-register-only-with-a-control` | **review only** |
| `no-sensitive-example-is-used` | **review only** |

Each tested rule names its test, and the suite fails if a rule names one this module
does not define. A rule cannot claim enforcement it does not have — which is the
rule the whole document is an instance of, and which an independent review of this
change caught it breaking: two of the rules above described a scope wider than the
test behind them actually read. Both the tests and the statements were corrected
rather than one of them.

The four review-only ones are the four that need either a component or a person's
judgement. Two are about what an unwritten component does with a value; one is about
what somebody puts in a document or a slide; and the last is about whether a register
entry is removed for the right reason. None of them can be read by a test, and a
review is enforced only when the reviewer remembers it.

## Reserved vocabulary

Twelve terms may appear in every Markdown document committed here, and in the
committed data, only inside a sentence that denies them. A test joins wrapped lines
back into sentences, skips fenced code, and fails on a reserved term in a sentence
carrying no denial.

The scan reads every Markdown file in this repository rather than only the security
documents, and a second test fails if that coverage narrows. The narrower version was
the first one written, and it would have passed while the top-level README described a
posture this project does not have.

| Term | Why it is reserved |
|---|---|
| `secure` | It is the word a reader takes as the whole conclusion, and nothing here supports it |
| `secured` | The same claim in a past tense that implies somebody finished the job; nobody did |
| `hardened` | It describes a process applied to a system, and no such system exists |
| `audited` | It names an activity by an outside party that has never happened here |
| `compliant` | It implies a named regime and an assessment against it. No regime is named and no assessment was performed |
| `compliance` | The same claim in a noun, which is how it usually arrives, and it is no more supported |
| `enterprise-grade` | It is a claim about an audience rather than a property, and a claim that names no property cannot be checked |
| `production-ready` | V1 is single node, single replica, single model, on one host, with no control at the caller boundary |
| `zero trust` | It names an architecture with identity at its centre, and there is no identity here at all |
| `penetration test` | None has been performed, and the phrase reads as a result even in a sentence about scheduling one |
| `battle-tested` | It claims operational history this project does not have |
| `bank-grade` | It claims a standard nobody defines and nobody assessed |

The list catches a listed word in a Markdown document. A claim made in a word nobody
listed, in a file that is not Markdown, or in a slide is not caught by anything here.

## Related records

| Topic | Document |
|---|---|
| The decision this document implements | [ADR 0008](../architecture/decisions/ADR-0008-v1-security-baseline.md) |
| What can go wrong, and where | [Threat model](threat-model.md) |
| What is undefended, and the exceptions accepted | [Deferred risks and exceptions](deferred-risks.md) |
| The authoritative form of all of it | [`security-baseline.v1alpha1.json`](security-baseline.v1alpha1.json) |
| What a passing check may be used to claim | [Certification levels](../testing/certification.md) |
| Which claims currently hold a level | [Claim and test matrix](../testing/claim-test-matrix.md) |
