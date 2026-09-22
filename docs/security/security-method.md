# The V1 security method

Status: **published method over an accepted baseline.** This document says how V1
approaches securing inference, topic by topic, and keeps two lists apart in every
topic: what is implemented, with the test, gate, and record behind it, and what is
not, with the register entry or unmet claim that carries it. It adds no control and
moves no status. Every control status below is derived by
[the security baseline](security-baseline.v1alpha1.json), and every certification
level is read from
[the claim and evidence register](../testing/claim-evidence-matrix.md).

> [!IMPORTANT]
> Nothing in this repository authenticates a caller, authorises a request, or admits
> a pod. Everything this method calls implemented acts over committed files, over the
> manifests and chart renders this repository publishes, or on a contributor's own
> machine. None of it has acted inside a system serving a request, and no outside
> party has assessed any of it.

The authoritative form is
[`security-method.v1alpha1.json`](security-method.v1alpha1.json).
[`tests/testing/test_published_methods.py`](../../tests/testing/test_published_methods.py)
holds the two in agreement and checks every reference the record makes: a test
function that is not defined, a workflow job that does not exist, or a record that is
not committed fails the build. The same suite puts each control on the side of the
line its own derived status allows, and refuses an item listed as implemented that
rests on an uncertified claim.

The companion for telemetry is [the V1 observability method](../telemetry/observability-method.md).

## How to read it

Each topic has two tables.

**Implemented** means the baseline derives a status for the control that may be called
implemented — enforced over documents, over manifests, or on the host — or, where no
control is named, that a certified claim covers the item. Each row names what verifies
it and the committed record it rests on, and carries an evidence label from the
register's vocabulary:

| Label | What it can support |
|---|---|
| `local-static` | A deterministic check over files in this repository. Certifies at most `C0` |
| `mock` | The API driven against the labelled mock adapter. Certifies at most `C1`, and never real runtime behaviour |
| `synthetic` | Generated inputs or a simulated environment. Certifies at most `C1` |
| `local-real-cpu` | The real component on a contributor's own machine, on CPU, with versions and commands recorded. Certifies at most `C2` |
| `estimated` | A calculation. Supports no claim about what anything costs |
| `production-experience` | Operating the thing in an organization's production. **Unreachable from this repository**, and used by no row here |

**Not implemented** means a control that is review-enforced, specified for a component
that does not exist, or deferred, or a risk carried in
[the deferred-risk register](deferred-risks.md). Each row says what may not be claimed
while it stands.

A reference resolving says the named thing exists. It does not say the test is a good
one, which is the same limitation the baseline declares for its own status derivation.

## 1. Assets and trust boundaries

[The threat model](threat-model.md) names eleven assets, six actors, six trust
boundaries and twenty-two threats. Five boundaries come from
[the architecture](../architecture/system-architecture.md) verbatim, and a test
compares the two. The sixth, B6, is the boundary every commit crosses, and it is the
only one whose failures cannot be undone.

**Implemented**

| What | Controls and claim | Verified by | Record | Label |
|---|---|---|---|---|
| Every control's status is derived from the verification it names, and every threat names a control or a register entry | `derive-a-control-status-from-its-verification`, `no-security-claim-without-a-named-verification`; claim `a-security-control-cannot-claim-enforcement-it-does-not-have` | `test_declared_control_status_equals_derived_control_status`, `test_every_threat_names_a_control_or_a_deferred_risk`, `test_a_mapped_boundary_matches_the_architecture_verbatim`; gate `default-lane-tests` | [v1-s0-009-pr1](../proof/security/v1-s0-009-pr1-validation.md) | `local-static` |
| At B6, a committed file may not be generated host state, carry a personal filesystem path, or put a tenant identifier in an evidence record | `ignore-and-refuse-generated-host-state`, `no-personal-filesystem-path-in-a-committed-file`, `no-tenant-identifier-in-a-committed-record` | `test_no_committed_file_is_generated_host_state`, `test_no_committed_file_carries_a_personal_filesystem_path`, `test_a_tenant_identifier_stays_out_of_metrics_and_evidence` | [v1-s0-009-pr1](../proof/security/v1-s0-009-pr1-validation.md) | `local-static` |

**Not implemented**

| What | Carried by | Not claimed |
|---|---|---|
| B5, the caller boundary, enforces nothing: no authentication, no authorisation, no rate limit, no tenant isolation | DR-01, DR-02, DR-03; claim `a-deployed-inferops-workload-is-defended` is not claimed | No property at the caller boundary; V1 is not access-controlled there |
| Whether a diff carries unpublished strategy, and whether a promoted record was redacted, is decided by a reviewer | `review-the-public-diff-for-private-material`, `redact-before-promoting-raw-output`, both review-enforced | Nothing reads either, so neither is called implemented |

## 2. Model and image supply chain

One weight file and two image digests cross B1. The integrity argument rests on one
fact worth keeping in view: the expected hash is **committed in this repository**, not
fetched over the transport that delivers the file it describes.

**Implemented**

| What | Controls and claim | Verified by | Record | Label |
|---|---|---|---|---|
| The model is pinned by revision and per-file SHA-256, and compared before anything reads it — by the acquisition job, and by the chart's `verify-model` init container on every pod start | `pin-model-revision`, `verify-artifact-hash-before-use` | `test_the_model_acquisition_job_pins_a_revision_and_verifies_a_hash`, `test_the_integrity_check_runs_before_the_runtime_and_on_every_start` | [runtime feasibility](../proof/serving/v1-s0-003-pr2-runtime-feasibility.md), [v1-s3-008-pr1](../proof/environment/v1-s3-008-pr1-validation.md) | `local-static` |
| Every image a committed manifest or render names is pinned by digest | `pin-image-by-digest` | `test_every_manifest_image_is_pinned_by_digest`, `test_every_rendered_image_is_pinned_by_digest`; gate `default-lane-tests` | [v1-s0-009-pr1](../proof/security/v1-s0-009-pr1-validation.md) | `local-static` |
| The pinned runtime image and the committed lockfile are scanned against one committed blocking severity, and a CycloneDX bill of materials is generated for each | `scan-the-pinned-runtime-image-for-known-vulnerabilities`, `scan-python-dependencies-for-known-vulnerabilities`; claim `the-pinned-image-and-the-locked-dependencies-were-scanned-and-a-bill-of-materials-published` | the shared library in [`scripts/security/lib.sh`](../../scripts/security/lib.sh), `test_the_image_scan_reads_the_digest_the_manifests_already_pin`; gates `dependency-and-image-scan`, `software-bill-of-materials` | [v1-s2-006-pr1](../proof/security/v1-s2-006-pr1-validation.md) | `local-static` |

**Not implemented**

| What | Carried by | Not claimed |
|---|---|---|
| No signature or build attestation is verified before the image runs; the publisher emits none | `verify-artifact-provenance`, deferred; DR-08 | No provenance or build identity. A digest says what ran and not who built it |
| The model transport reported certificate validation as disabled | DR-06 | No integrity property beyond the hash comparison |
| Nothing records that a given check resolved from the committed lockfile, and the non-Python tools are pinned in prose | `pin-every-dependency-with-a-committed-lockfile`, deferred; DR-07 | No reproducibility property for the tool chain |
| A publisher that stops serving the pinned revision stops every serving record being reproducible | DR-09 | No availability property for an external artifact |

## 3. Secrets

V1 holds no secret. A workload contract carries a **locator** for one and never a
value, and nothing in V1 resolves a locator, so the controls here are about keeping a
value out of every place a value could land.

**Implemented**

| What | Controls and claim | Verified by | Record | Label |
|---|---|---|---|---|
| A credential-shaped locator is refused, and a refusal names the field and the rule and never the value | `refuse-a-secret-value-in-a-contract`, `never-echo-a-document-value-in-a-refusal` | `test_a_credential_shaped_locator_is_caught`, `test_no_finding_quotes_a_value_from_the_document` | [v1-s0-004-pr2](../proof/contracts/v1-s0-004-pr2-validation.md) | `local-static` |
| A committed render carrying a secret value is refused | `no-secret-value-in-a-rendered-manifest`; claim `a-workload-manifest-that-omits-a-required-security-control-is-refused` | `test_an_insecure_fixture_is_refused_by_exactly_the_rules_it_records`; gate `expected-failures` | [v1-s3-004-pr1](../proof/security/v1-s3-004-pr1-validation.md) | `local-static` |
| A secret-scan configuration is committed and its allowlist resolves, and the scanner reads the whole history as a gate | `no-credential-or-artifact-in-public-history` | `test_the_secret_scan_configuration_is_committed_and_its_allowlist_resolves`; gate `secret-scan` | [v1-s4-001-pr1](../proof/testing/v1-s4-001-pr1-validation.md) | `local-static` |

The one recorded scan of the history is the hand run in
[the V1-S4-001-PR1 record](../proof/testing/v1-s4-001-pr1-validation.md), which is
also the run that found the committed configuration had never parsed.

**Not implemented**

| What | Carried by | Not claimed |
|---|---|---|
| No secret manager, rotation policy, or expiry check exists, because nothing resolves a reference | DR-10 | No secret-management property beyond the shape of a locator |
| The gate's runs on the selected service are observed and not promoted into a record | DR-11; claim `no-credential-or-model-artifact-enters-public-history` stays planned | That no credential or model artifact enters public history is not certified and may not be cited |

## 4. API and network exposure

The API is reachable in two ways: through a port-forward, and from any pod in the
cluster. Nothing on either path identifies a caller.

**Implemented**

| What | Controls and claim | Verified by | Record | Label |
|---|---|---|---|---|
| Both Services are `ClusterIP`, no Ingress is declared, and no node port is pinned | `least-exposure-no-manifest-publishes-a-service` | `test_no_manifest_exposes_a_service_outside_the_cluster` | [v1-s0-009-pr1](../proof/security/v1-s0-009-pr1-validation.md) | `local-static` |
| The chart renders a default-deny of both directions over every pod the release installs, and a render not denied both ways is refused | `network-policy-in-the-release-namespace`; claim `a-workload-manifest-that-omits-a-required-security-control-is-refused` | `test_every_committed_render_satisfies_the_workload_policy`; gate `helm-chart` | [v1-s3-004-pr1](../proof/security/v1-s3-004-pr1-validation.md) | `local-static` |

Least exposure is a reduction in reachability and not an access control: it
identifies nobody and limits nothing once something is inside.

**Not implemented**

| What | Carried by | Not claimed |
|---|---|---|
| No caller is authenticated, no request is authorised, nothing limits one caller, and a tenant is a request rather than an assertion checked against anything | `authenticate-and-authorise-a-caller`, `limit-what-one-caller-may-consume` (deferred), `a-tenant-is-a-request-not-an-assertion` (specified only); DR-01, DR-02, DR-03 | No access control, rate limit, isolation, or multi-tenancy |
| The accepted local cluster's network plugin was measured not to apply the rendered policy | DR-04; claim `the-rendered-network-policy-is-enforced-by-the-cluster` is not claimed | No network isolation; the rendered policy may not be described as a control |
| The metrics route sits behind the same absent boundary and publishes the deployment's build, model revision, and runtime image digest | DR-01 | No control over who reads the metrics endpoint |

## 5. Container and Kubernetes controls

Every pod-security assertion reads a file: the smoke and trial apparatus under
`deploy/`, and the chart's two committed renders. A release has been installed from
those renders, so the workloads it deployed carried the settings — and no check here
read a pod that resulted.

**Implemented**

| What | Controls and claim | Verified by | Record | Label |
|---|---|---|---|---|
| Every pod specification and container runs as non-root with the runtime-default seccomp profile, mounts no service account token, forbids privilege escalation, has a read-only root filesystem, and drops every capability | `run-as-non-root`, `seccomp-runtime-default`, `do-not-mount-a-service-account-token`, `forbid-privilege-escalation`, `read-only-root-filesystem`, `drop-all-capabilities` | `test_every_pod_spec_carries_every_required_pod_security_field`, `test_every_container_carries_every_required_container_security_field` | [v1-s0-009-pr1](../proof/security/v1-s0-009-pr1-validation.md) | `local-static` |
| A render that drops a dedicated service account or an explicit resource envelope is refused, and nine insecure fixtures each prove a rule fires | `use-a-dedicated-service-account-per-workload`, `declare-explicit-resource-requests-and-limits`, `refuse-a-workload-manifest-that-omits-a-required-control`; claim `a-workload-manifest-that-omits-a-required-security-control-is-refused` | `test_the_fixtures_between_them_exercise_every_rule`, `test_an_insecure_fixture_is_refused_by_exactly_the_rules_it_records`; gates `expected-failures`, `helm-chart` | [v1-s3-004-pr1](../proof/security/v1-s3-004-pr1-validation.md) | `local-static` |
| A platform action reaches only a cluster the operator selected and verified, through the project kubeconfig | `refuse-to-act-on-a-cluster-this-project-did-not-create`, `scope-every-kubectl-call-to-the-project-kubeconfig` | the guards in [`scripts/environment/lib.sh`](../../scripts/environment/lib.sh), `test_a_mutating_kubectl_call_goes_through_the_wrapper` | [cluster smoke](../proof/environment/v1-s0-002-pr2-cluster-smoke.md) | `local-real-cpu` |

**Not implemented**

| What | Carried by | Not claimed |
|---|---|---|
| Nothing reads a pod this platform deployed, and no admission control constrains one | DR-05; claim `a-deployed-inferops-workload-is-defended` is not claimed | No deployed workload may be described as constrained |

## 6. Scan and policy gates

Three scanners and two policy checks run as gates in
[the default-lane workflow](../../.github/workflows/checks.yml), on every pull request
and every push to `main`, through the same committed scripts and the same severity
policy a contributor runs by hand. [The gate matrix](../testing/ci-gate-matrix.md) maps
each gate to the claims it defends and holds the workflow to it in both directions.

**Implemented**

| What | Controls and claim | Verified by | Record | Label |
|---|---|---|---|---|
| The dependency and image scan, the bill of materials, and the secret scan run on every change | `scan-the-pinned-runtime-image-for-known-vulnerabilities`, `scan-python-dependencies-for-known-vulnerabilities`, `no-credential-or-artifact-in-public-history`; claim `the-pinned-image-and-the-locked-dependencies-were-scanned-and-a-bill-of-materials-published` | gates `dependency-and-image-scan`, `software-bill-of-materials`, `secret-scan`; `test_the_matrix_and_the_workflow_declare_the_same_jobs` | [v1-s4-001-pr2](../proof/testing/v1-s4-001-pr2-validation.md) | `local-static` |
| The committed invalid contracts and insecure manifests are run through the validators on every change, and each must be refused | `refuse-a-workload-manifest-that-omits-a-required-control`; claim `a-workload-manifest-that-omits-a-required-security-control-is-refused` | gate `expected-failures`; `test_the_fixtures_between_them_exercise_every_rule` | [v1-s4-001-pr1](../proof/testing/v1-s4-001-pr1-validation.md) | `local-static` |

**What has been run, and what that is.** Each scanner has one recorded run, by hand:
the image and dependency scans in
[the V1-S2-006-PR1 record](../proof/security/v1-s2-006-pr1-validation.md), and the
secret scan in [the V1-S4-001-PR1 record](../proof/testing/v1-s4-001-pr1-validation.md).
The three gates have also passed on the selected service, on every one of the
nineteen pushes to `main` from `f212090` on 2026-09-13 to `4f3532a` on 2026-09-21.
[The run list](../proof/security/v1-s5-004-pr1-hosted-runs.v1alpha1.json) carries the
conclusion the service reported for every job of every one of those runs, and
[this change's validation record](../proof/security/v1-s5-004-pr1-validation.md) says
how it was read. Those conclusions are the service's statements, read through its
public interface; no log or scan output is promoted into a record, so no row above
rests on a hosted run.

**Not implemented**

| What | Carried by | Not claimed |
|---|---|---|
| The workflow runs on a change and not on a schedule, so a vulnerability database that moves between changes is not read, and no hosted scan is promoted into a record | DR-08, DR-11 | No vulnerability count, severity distribution, or scan score as a durable posture; a green run is not current past the day it ran |

## 7. Accepted exceptions

Six weaknesses are accepted rather than fixed. Each names where it was accepted, a
compensating control the baseline declares, the residual risk, and when to revisit it,
and the four are enforced by a test.

**Implemented**

| What | Controls and claim | Verified by | Record | Label |
|---|---|---|---|---|
| Every exception names a compensating control, a residual risk, and a revisit condition, and each is published under its own heading | claim `a-security-control-cannot-claim-enforcement-it-does-not-have` | `test_every_exception_names_a_compensating_control_and_a_residual_risk`, `test_the_exceptions_are_published_where_a_reader_will_find_them` | [v1-s0-009-pr1](../proof/security/v1-s0-009-pr1-validation.md) | `local-static` |

**Not implemented**

| What | Carried by | Not claimed |
|---|---|---|
| EX-01: the model transport is unauthenticated, and the committed hash is the whole argument | DR-06 | — |
| EX-02: the `kind` identity guard is satisfied by a second cluster given this project's name | — | — |
| EX-03: the secret-scan allowlist covers two directories wholesale | DR-11 | — |
| EX-04: the pod-security properties are properties of files, not of pods | DR-05 | — |
| EX-05: the local network plugin was measured to ignore the rendered policy | DR-04 | — |
| EX-06: Docker Desktop's guard cannot tell its own `kind` cluster from one the operator named `desktop` | — | — |
| **All six** | | No exception is described as closed, and none is cited as a control in its own right |

EX-03 set its own revisit condition — a recorded scanner run — and V1-S4-001-PR1 met it
without narrowing the allowlist. That is recorded as a gap in
[the register](deferred-risks.md) rather than closed here.

## 8. Prompt and response handling

Prompts, responses, chat histories, and provider error bodies are **not captured** —
not sampled, not truncated, not hashed. The mechanism is an absence rather than a
filter: the six excluded fields have empty placement lists in the catalog, and the API
builds every record through an allowlist that has no name for any of them. The full
reasoning is in [the redaction rules](../telemetry/redaction.md).

**Implemented**

| What | Controls and claim | Verified by | Record | Label |
|---|---|---|---|---|
| A prompt, a completion, a provider error body, a secret value, an authorization header, and a value read out of a document have nowhere they may be placed, and capture has no switch | `no-secret-or-content-has-a-telemetry-placement`, `content-capture-is-disabled-and-has-no-enabling-path`; claim `the-telemetry-catalog-cannot-admit-a-prompt-or-an-unbounded-label` | `test_a_forbidden_field_is_allowed_nowhere`, `test_content_capture_is_disabled_and_has_no_policy_to_enable_it` | [v1-s0-007-pr1](../proof/telemetry/v1-s0-007-pr1-validation.md) | `local-static` |
| The API is driven and what it wrote is read back: no record or series repeats the prompt or the completion, no record repeats an adapter's message, and no refusal carries the prompt or an adapter's message to the caller | claim `the-api-emits-catalog-metrics-and-structured-request-records` | `test_no_record_or_series_repeats_the_prompt`, `test_no_record_repeats_the_completion_the_caller_received`, `test_no_record_repeats_an_adapter_message`, `test_an_adapters_message_never_reaches_a_caller`, `test_no_failure_response_carries_the_prompt_that_produced_it` | [v1-s1-008-pr1](../proof/telemetry/v1-s1-008-pr1-validation.md) | `mock` |

**Enabling capture** would need five artifacts first, and none exists: a data
classification, a redaction specification, a retention window shorter than the metric
store's, an access control, and a lawful basis with a subject-deletion path. There is
no flag, because a flag would be the whole decision taken by whoever set it.

**Not implemented**

| What | Carried by | Not claimed |
|---|---|---|
| Every record a suite reads for content comes from the mock. Records the API wrote with the real adapter are quoted in three committed files from two runs, and no test reads one | DR-12; claim `no-prompt-response-or-secret-reaches-a-log-or-a-metric` stays planned | That no prompt, response, or secret reaches a log or a metric is not certified |
| That no upstream error body is logged verbatim anywhere, including by the serving-runtime adapter, is a review rule; the API's half is tested and the whole is not | `do-not-pass-through-a-provider-error-body`, review-enforced | The adapter's handling of a runtime's error text is not called implemented |
| What the platform did is specified for a platform API that does not exist, and records go to a stream nothing keeps | `record-what-the-platform-did`, specified only; DR-12 | No auditability, traceability, or incident reconstruction |

## 9. Deferred risks

[The deferred-risk register](deferred-risks.md) is the distance between what is
implemented and a defended system, and it is published in full rather than trimmed.

**Implemented**

| What | Controls and claim | Verified by | Record | Label |
|---|---|---|---|---|
| Every entry names its boundary, why V1 defers it, what would have to be true, whether it blocks production use, and what may not be claimed, in a sentence that denies | claim `a-security-control-cannot-claim-enforcement-it-does-not-have` | `test_every_deferred_risk_states_what_is_not_claimed`, `test_every_deferred_risk_is_reached_by_a_threat` | [v1-s0-009-pr1](../proof/security/v1-s0-009-pr1-validation.md) | `local-static` |

**Not implemented**

| ID | Risk | Blocks production use |
|---|---|---|
| DR-01 | No caller is authenticated and no request is authorised | yes |
| DR-02 | There is no rate limit, quota, or concurrency limit | yes |
| DR-03 | A tenant identifier is never validated against an entitlement | yes |
| DR-04 | The local plugin does not enforce the rendered network policy | yes |
| DR-05 | No pod security property is enforced for a pod this platform deploys | yes |
| DR-06 | The transport delivering a model artifact is not authenticated | yes |
| DR-07 | No check is verified to have resolved from the committed lockfile | yes |
| DR-08 | No provenance statement is verified, and no scan is continuous | yes |
| DR-09 | Artifact availability is not defended | no |
| DR-10 | No secret manager, rotation policy, or expiry check exists | yes |
| DR-11 | No recurring run of a secret scanner is recorded | no |
| DR-12 | Records are written and nothing keeps them, so nothing can be reconstructed | yes |

Twelve risks are carried rather than reduced, and ten block production use. No entry is
described as reduced, and an entry leaves the register only with the control that
reduces it — a rule no test can enforce, and which is marked review-only for that reason.

## 10. Production-oriented design is not production certification

The controls are shaped the way a production deployment would need them: digests
rather than tags, a default-deny rather than an allow-list, a status derived rather than
asserted. **Shaped for it is not certified for it.** No control has been exercised by a
production deployment, and the `production-experience` label is unreachable from this
repository.

**Implemented**

| What | Controls and claim | Verified by | Record | Label |
|---|---|---|---|---|
| Twelve posture terms may appear in a committed Markdown document only in a sentence that denies them, and the scan reads every Markdown file here | `no-security-claim-without-a-named-verification`; claim `a-security-control-cannot-claim-enforcement-it-does-not-have` | `test_a_reserved_term_appears_only_where_it_is_denied`, `test_the_vocabulary_check_reaches_the_documents_a_reader_meets_first` | [v1-s0-009-pr1](../proof/security/v1-s0-009-pr1-validation.md) | `local-static` |

**Not implemented**

| What | Carried by | Not claimed |
|---|---|---|
| No control is observed in operation, no outside party has assessed anything, and nothing here is certified for production | claim `a-deployed-inferops-workload-is-defended` is not claimed | No production-readiness, compliance, or assessment property, and no control described as observed in operation |

## What publishing this corrected

Writing the method meant reading every document it summarises against the repository,
and five kinds of statement had stopped being true. Each is corrected in place with the date,
and the record lists them:

- **Six places said no job in the default-lane workflow had run on the selected
  service**: the security index, the threat model, SECURITY.md, ADR 0008, one register
  entry, and a baseline limitation. The three scan gates passed there on all nineteen
  pushes to `main` from 2026-09-13 to 2026-09-21.
- **One register entry and the control matrix said no continuous-integration lane
  existed**, and that ADR 0005 D6 left the service undecided. ADR 0012 selected one on
  2026-09-12.
- **The baseline data for two register entries still carried their original text** —
  that the scanner was not installed, and that no logger existed — while their document
  had been narrowed twice. The data is the authoritative form, so it was the stale half.
  One threat's residual risk, one control's `whatItDoesNotVerify`, and two paragraphs of
  ADR 0008 said the same about the logger.
- **One register entry, the redaction rules, and the API instrumentation document said
  no record had been produced against a real runtime.** Three committed files,
  from two runs, quote records the API wrote with the real adapter.
- **One register row carried a title its own heading had replaced**, and another
  entry's title said no scan was recorded two paragraphs above the sentence recording
  one.

## Related records

| Topic | Document |
|---|---|
| The decision this method is published under | [ADR 0008](../architecture/decisions/ADR-0008-v1-security-baseline.md) |
| What can go wrong, and where | [Threat model](threat-model.md) |
| Every control and its derived status | [Control matrix](control-matrix.md) |
| What is undefended, and the exceptions accepted | [Deferred risks and exceptions](deferred-risks.md) |
| The rules a rendered manifest is held to | [Workload policy](workload-policy.md) |
| What may never be written about a request | [Redaction rules](../telemetry/redaction.md) |
| Which claims hold a level, and on what | [Claim and evidence register](../testing/claim-evidence-matrix.md) |
| The observability half | [The V1 observability method](../telemetry/observability-method.md) |
