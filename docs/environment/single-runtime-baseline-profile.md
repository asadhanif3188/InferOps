# The single-runtime baseline profile

Status: **the profile exists as a generated release, an install description, and
a comparison record, and a check holds the three. This is evidence at C0. No
Application reads the profile, and no run installed the baseline release. The
profile is an experiment baseline. It is not a product tier, and it is not
desired state. A `COMPARABLE` record is a statement about committed inputs. It
is not eligibility for an experiment. Each side declares one API image digest
to the comparison. That digest is a declared comparison input. It is not an
install input, and it is not an observed runtime identity.**

The desired-state release declares two platform API replicas and two serving
runtime replicas. The baseline exists so that the loss of one runtime pod under
that topology can be compared with the loss of the one runtime pod of a release
with one. No experiment that makes that comparison is defined in this
repository. Such a comparison means something only while the runtime replica
count is the one variable that differs. This page describes the baseline, each difference that it
is permitted to have, the check that refuses any other difference, and what a
comparison record does not establish.

| Property | Value |
|---|---|
| Baseline topology | Two API replicas and one serving runtime replica |
| Target topology | Two API replicas and two serving runtime replicas: the [desired-state release](git-desired-state.md), key `local-docker-desktop/support-assistant` |
| Profile directory | `tests/domain/fixtures/experiment-profiles/single-runtime-baseline` |
| Comparison record | `tests/domain/fixtures/experiment-profiles/single-runtime-baseline.comparison.v1alpha1.json` |
| Install description | `tests/domain/fixtures/experiment-profiles/single-runtime-baseline.install.v1alpha1.yaml`. A person writes it |
| Declared comparison inputs | `tests/domain/fixtures/experiment-profiles/single-runtime-baseline.comparison-inputs.v1alpha1.yaml`. A person writes it. It states the API image digest of each side |
| Tool | [`tools/baseline_profile`](../../tools/baseline_profile/core.py): `python -m tools.baseline_profile --check`, `--record`, and `--write` |
| Tests | [`tests/domain/test_baseline_profile.py`](../../tests/domain/test_baseline_profile.py), and three render tests in [`tests/architecture/test_helm_chart.py`](../../tests/architecture/test_helm_chart.py) |
| Validation records | [`v2-s4-003-pr2-validation.md`](../proof/environment/v2-s4-003-pr2-validation.md), [`v2-s4-005-pr1-validation.md`](../proof/environment/v2-s4-005-pr1-validation.md) for the install and readiness inputs, and [`v2-s4-006-pr1-validation.md`](../proof/environment/v2-s4-006-pr1-validation.md) for the API image digest |
| Read by | No Application and no procedure. The two suites read the files |

## How the baseline is declared

**The baseline is the target's declaration with two fields replaced.** The tool
takes the declaration of the desired-state release and replaces the contract and
the directory. It keeps the binding, the platform defaults, and both revisions.
So the declarations agree by construction, and the first rule below is a
tripwire: it is not held when a later edit of the tool names another binding,
another defaults file, or another revision for the baseline.

| Declared input | Baseline | Target |
|---|---|---|
| Contract | [`synchronous-llm-local.yaml`](../../contracts/workload/examples/valid/synchronous-llm-local.yaml), version `0.1.0` | [`synchronous-llm-two-replicas.yaml`](../../contracts/workload/examples/valid/synchronous-llm-two-replicas.yaml), version `0.2.0` |
| Directory | The profile directory | `gitops/environments/local-docker-desktop/workloads/support-assistant` |
| Binding | `local-docker-desktop`, which states two API replicas | The same file |
| Platform defaults | The `api` block and `runtime.rollout` of `charts/inferops-llm/values.yaml` | The same file |
| Renderer revision and platform-defaults revision | The target's | `cdcfd62baf6fff56ca179711855510c93194ce80` for both |

**The change adds no contract.** Version `0.1.0` of the reference workload
declares a replica range of one and one. Version `0.2.0` declares two and two.
The two documents differ in the version, the description, and the replica range.
The baseline is version `0.1.0` rendered on the binding that the target uses.

**A workload version names one content.** The two contracts differ in content, so
they differ in version. The version is a rendered value. So the two releases
differ in two values and not in one: the runtime replica count, and the workload
version that follows it. A baseline that kept the target's version would give
one version two contents, and the check refuses it.

**What the workload version reaches.** The chart gives the version to the API as
one ConfigMap value, `INFEROPS_WORKLOAD_VERSION`. The API states it as the
resource attribute `inferops.workload.version` of its telemetry. So a telemetry
record of the baseline states `0.1.0` and one of the target states `0.2.0`. The
telemetry names keep the version off every operational metric series: it may
label the identity metric only. No module of the API's request handling reads
it. The ConfigMap
value is hashed into the configuration checksum annotation of the API pod
template and of the runtime pod template. So a change of one installed release
from one side to the other gives the API Deployment a new pod template too, and
not the runtime Deployment alone. Both statements are read from the chart and
the API's source. Neither was observed on a cluster.

**The baseline follows the target only while the two contracts stay equal
elsewhere.** A change to the target's contract at a path that is not permitted,
such as a resource ceiling in a later version, gives `REFUSED`. The `0.1.0`
contract is a pinned input of the first experiment's freeze record and the
contract of the reference release in the test fixtures. So the remedy then is a
decision: the same change to that contract, or another baseline contract.

The baseline release identifier is
`ecc4b9cf2d8c2e137e743dcf9e99dcdad12ec297821bc0115694dc703f88a465`. The target
release identifier is
`b5457f49092c578496738973a8786a95428517e7ddf755303b4f6842dcb8c9db`.

> **Note, 2026-10-09 (`V2-S4-004-PR1`).** Chart `0.6.0` renders one
> [PodDisruptionBudget](disruption-budgets.md) for a tier of two or more replicas. So
> the target renders a budget for the runtime tier, and the baseline, with one runtime
> replica, renders none. Both render the same budget for the API tier. This is a
> difference of rendered objects and not of values: it follows from the runtime replica
> count, which is the one intended variable. The comparison record compares values and
> documents, and it compares no rendered object. One test of the chart suite renders
> both sides and holds this difference. A budget bounds a voluntary eviction and not a
> pod deletion. Both identifiers above moved with that change, because the two revisions
> of the target moved.

## The install inputs

> **Note, 2026-10-09 (`V2-S4-005-PR1`).** Until this change the baseline named no
> chart, no hand-written values, no release name, and no namespace, and the
> record compared none of them. A probe timeout set in the target's Application
> alone left the record as it was and the result `COMPARABLE`. The comparison
> now reads an install description of each side, and it refuses that edit.

A release is installed from more than its generated values. **Each side states
its install inputs, and the tool compares the two statements.**

| Install input | Baseline | Target |
|---|---|---|
| Where it is stated | `tests/domain/fixtures/experiment-profiles/single-runtime-baseline.install.v1alpha1.yaml` | The Application at `infra/argocd/local-docker-desktop-support-assistant.yaml` |
| Chart repository, revision, and path | `chart.repository`, `chart.revision`, `chart.path` | `spec.source.repoURL`, `spec.source.targetRevision`, `spec.source.path` |
| Release name | `release.name` | `spec.source.helm.releaseName` |
| Namespace | `release.namespace` | `spec.destination.namespace` |
| Cluster address | `release.server` | `spec.destination.server` |
| Generated values file | `valuesFile` | The one entry of `spec.source.helm.valueFiles` |
| Hand-written values | `handWrittenValues` | `spec.source.helm.valuesObject` |
| Chart version and chart content | Read from the chart at the stated path | Read from the chart at the stated path |

**The baseline's description is written by hand.** No command writes it. A change
to an install input of the target is made in the description too, in the same
change. `--check` refuses until both state it.

**What the tool reads of each description, and what it refuses.** An absent
file, a file that is not YAML, a key that is stated twice, a document that
refers to itself, an absent member of the table above, and an empty text each
give `baseline-install-inputs-refused`. The tool takes no install input from a
default when a description does not state it.

- **The baseline's description** states the members of the table and no other.
  Another member refuses the comparison.
- **The Application** is read in six blocks: the document, `metadata`, `spec`,
  `spec.source`, `spec.source.helm`, and `spec.destination`. Another member in
  one of them refuses the comparison. So a Helm parameter, a second values
  file, a second source, an annotation, or a top-level `operation` refuses it:
  each is an input that the tool cannot compare.
- **Three members of the Application are stated and not compared:**
  `metadata.name`, `spec.project`, and `spec.syncPolicy`. They are how the
  target is delivered, and the baseline names no controller. The record states
  them under `targetDelivery`, so a change to one makes the record stale and
  does not refuse the comparison.
- **The tool does not read** the Application's `apiVersion`, its
  `metadata.namespace`, or its `metadata.labels`.

**The Application that a cluster holds is not the committed one.** The procedure
that applies the Application adds the API image digest as one Helm parameter.
The tool reads the committed file, which states no parameter. So neither
description states the digest, and each side declares it in another file: see
[the API image digest](#the-api-image-digest).

**The chart is stated by its version and by one digest.** The digest is the
SHA-256 of one line for each file of the chart directory, in the order of the
paths, but for the chart's page `README.md` and its render fixtures under
`ci/`. A line is the SHA-256 of the file, two spaces, and the path in the chart.
So the digest holds `Chart.yaml`, `values.yaml`, `values.schema.json`, each
template, and `.helmignore`, and it would hold a subchart. Both descriptions
name one chart path, so both sides state one digest: the comparison of the two
digests is equal by construction, and the comparison of the two paths is the
check. The digest makes the committed record stale when a chart file changes.
It is of the files of the tree that the tool read. Each description names a
branch as the chart revision, and nothing here reads what that branch names on
a remote. A chart path in another spelling than the tree has, such as another
case, is refused.

**Effective values are derived. They are not read from a cluster.** The tool
merges the chart's defaults, then the derived generated values of the side,
then its hand-written values, as Helm merges values documents: a mapping is
merged member by member, another value replaces the earlier one, and a null
removes the member. The tool does not open the values file that a description
names. It compares the name with the generated values file of that side's
release, and `--check` holds that each committed values file is the derived
one: `baseline-release-drifted` for the baseline, and
`baseline-target-release-drifted` for the target. The two documents of
effective values may differ at the two paths where the generated values differ,
and at no other. The replica counts are read from the effective values again,
so a hand-written `runtime.replicaCount` that replaces the generated count is
refused, on one side or on both.

**Both sides read one defaults file.** So a chart default cannot differ between
the sides. The effective layer finds a hand-written value, or a null, that
moves one side away from the other, and a hand-written replica count.

**A description is parsed as YAML 1.1.** Helm's parser reads some plain scalars
in another way: a plain `n` is a text here and false there. The tool does not
model that. A readiness input must have a usable type, so such a text is
refused there. For another value the tool can report equal values that Helm
reads as two.

### The readiness inputs

The chart's two probe templates read 23 values. The chart's validation compares
three more with a startup budget: `runtime.startupBudgetMs`, and the
`lifecycle.progressDeadlineSeconds` of each tier. The list names the first of
the three, so it names 24 values. The two deadlines are compared as effective
values, and nothing requires that they are stated.

**The effective values of each side must hold each of the 24 with a usable
value, and the record states the value of each.** Two absent values are not read
as two equal values: an absent input gives `baseline-readiness-input-unusable`
for each side that lacks it. A usable value is a text that starts with a slash
for a path, true or false for `enabled`, and a whole number above zero for each
other setting. Today the chart's defaults supply all 24 for both sides, and
neither description states one. So the rule is broken by a null, by a changed
chart default, or by a hand-written value of another type. Probes that both
sides switch off with `enabled: false` are comparable: the record states the
value, and no rule requires a probe.

| Readiness input | Value on both sides |
|---|---|
| `/api/readinessPath` | `/health/ready` |
| `/api/livenessPath` | `/health/live` |
| `/api/probes/enabled` | `true` |
| `/api/probes/startup/budgetMs` | `60000` |
| `/api/probes/startup/periodSeconds` | `5` |
| `/api/probes/startup/timeoutSeconds` | `2` |
| `/api/probes/readiness/periodSeconds` | `10` |
| `/api/probes/readiness/timeoutSeconds` | `5` |
| `/api/probes/readiness/failureThreshold` | `3` |
| `/api/probes/liveness/periodSeconds` | `10` |
| `/api/probes/liveness/timeoutSeconds` | `2` |
| `/api/probes/liveness/failureThreshold` | `3` |
| `/runtime/healthPath` | `/health` |
| `/runtime/startupBudgetMs` | `300000` |
| `/runtime/probes/enabled` | `true` |
| `/runtime/probes/startup/budgetMs` | `600000` |
| `/runtime/probes/startup/periodSeconds` | `10` |
| `/runtime/probes/startup/timeoutSeconds` | `3` |
| `/runtime/probes/readiness/periodSeconds` | `10` |
| `/runtime/probes/readiness/timeoutSeconds` | `3` |
| `/runtime/probes/readiness/failureThreshold` | `3` |
| `/runtime/probes/liveness/periodSeconds` | `10` |
| `/runtime/probes/liveness/timeoutSeconds` | `3` |
| `/runtime/probes/liveness/failureThreshold` | `3` |

A startup probe gates the other two, and a liveness probe restarts a container,
so the settings of all three probes are named. The record states what the chart
receives. It does not state a rendered probe, and no probe was observed.

### The API image digest

> **Note, 2026-10-10 (`V2-S4-006-PR1`).** Until this change no committed file
> stated an API image digest for either side. The record listed the digest as
> unresolved, and the result was `COMPARABLE`. Two descriptions that both
> stated the text `abc` as the digest gave `COMPARABLE` too. The digest is now
> a required input of each side. An absent digest, a malformed digest, and two
> digests that differ each give `REFUSED`.

**Each side declares one API image digest, and the tool requires two usable,
equal digests.** The declarations are in one file that a person writes:
`tests/domain/fixtures/experiment-profiles/single-runtime-baseline.comparison-inputs.v1alpha1.yaml`. It states `apiImageDigest.baseline` and `apiImageDigest.target`.

**Why the digest is not in a description.** No InferOps API image is published,
so a digest names one build on one host. The Application states no digest, and
the procedure that applies it adds the digest as one Helm parameter. This change
keeps that design. It edits no Application, no procedure, and no chart file.

**A usable digest is `sha256:` and 64 lowercase hexadecimal digits.** That is
the form that the procedure that applies the Application accepts for its digest
argument. The tool classifies the declared digest of each side:

| State | Meaning | Result |
|---|---|---|
| `valid` | The file states a text of the usable form for the side | The rule holds when the other side is `valid` with the same digest |
| `absent` | The file states no member for the side, or a null. A file with no `apiImageDigest` block, or an empty one, states no member for both sides | `REFUSED` |
| `malformed` | The file states another value: a text of another form, an empty text, a number, a list, or a mapping | `REFUSED` |
| `not-read` | The file is absent, is not YAML, states a key twice, is of another schema or kind, or states a member that the tool does not read | `REFUSED`, for both sides |

- **Equality is not validity.** Two sides that state one malformed text are
  refused: each side is `malformed`.
- **No default.** The tool takes no digest from a default, from the other side,
  or from the chart. The chart's default for `api.image.digest` is the empty
  text, which states no digest.
- **Two valid digests that differ are refused.**
- **A description may state the digest too, and then it must state the declared
  one.** The tool reads `/api/image/digest` of the effective values of each
  side. An empty text or an absent value states none. Another value that is
  not the declared digest of that side gives
  `baseline-api-image-digest-contradicted`. A digest that one description
  states alone is also a one-sided hand-written value, and
  `baseline-install-differs` refuses it as before.

**The digest has one category: `declared-comparison-input`.** A digest can be
one of three things, and a record states which one it holds.

| Category | What it is | Does a record state it |
|---|---|---|
| Declared comparison input | A value that a committed comparison input states | Yes, under `apiImageIdentity` |
| Install input | The value that an operator gives to the procedure that applies the Application | No. The tool reads no procedure and no applied object |
| Observed runtime identity | A value that a cluster reported for a running pod | No. The tool reads no cluster |

**The origin of the committed value.** Both sides declare
`sha256:244251f76e5959c58e52689337298a24af46b34d8fd36b097cb638671eccda56`. A cluster reported that value as the `imageID` of the two API pods
of the target in one retained read:
[`pods-before.json`](../proof/environment/v2-s4-005-pr2-service-endpoint-state-run-1/pods-before.json),
at `docs/proof/environment/v2-s4-005-pr2-service-endpoint-state-run-1/pods-before.json`. In that read the value is an observed runtime identity of the
target, of one local build, on one host, on 2026-10-09. In the comparison
inputs it is a declared value, copied by hand. No run installed the baseline,
so the value was not observed for the baseline. One test holds that the
declared value is the one that the read reports.

**A `COMPARABLE` record does not establish that a run installs either side with
the declared digest.** Another build of the API image has another digest. An
operator who applies the Application gives the digest of the image on that
host, and that procedure does not read the comparison inputs. A later
experiment that uses the baseline must not read `COMPARABLE` as an installed
identity. It needs a record of the digest that each side's pods reported, and
a check of that digest against the declared one. Nothing in this repository
makes that check.

A record states the identity under `apiImageIdentity`: the category, the source
file, the usable form, the state of each side, the digest of each `valid` side,
each digest that the effective values state, whether the identity is bound, and
the bound digest when it is.

### Unresolved inputs and eligibility

**`COMPARABLE` says that the committed inputs of the two sides are comparable.**
It does not say that a run may use the baseline. Every record states
`experimentEligibility` as `not-established`, and it lists each input that no
committed file resolves under `unresolvedInputs`:

| Input | Path | Statement |
|---|---|---|
| `caller-profile` | None | No caller profile exists in this repository. A run must give both sides one revision of one caller profile. |

The caller profile is listed in every record, because this tool reads none.
The record of the committed tree lists no other input: the API image digest is
bound. A record whose API image digest is not bound lists `api-image-digest`
too, with the sides that state no usable digest, and that record is `REFUSED`.

## The permitted differences

The tool compares six layers: the two declarations, the two contract documents,
the two generated values documents, the two release documents, the two install
descriptions, and the two documents of effective values. A path is a JSON
pointer into the document of its layer. **A difference at a path that this
table does not state refuses the comparison.**

| Layer | Path | Reason |
|---|---|---|
| declaration | `/contract` | `profile-declaration` |
| declaration | `/directory` | `profile-declaration` |
| contract | `/metadata/description` | `prose-not-rendered` |
| contract | `/metadata/version` | `identity-of-a-different-content` |
| contract | `/spec/scaling/maximumReplicas` | `intended-variable` |
| contract | `/spec/scaling/minimumReplicas` | `intended-variable` |
| values | `/ownership/workloadVersion` | `identity-of-a-different-content` |
| values | `/runtime/replicaCount` | `intended-variable` |
| release | `/metadata/releaseId` | `identity-of-a-different-content` |
| release | `/metadata/workloadVersion` | `identity-of-a-different-content` |
| release | `/output/helmValues/sha256` | `identity-of-a-different-content` |
| release | `/source/contract/sha256` | `identity-of-a-different-content` |
| install | `/valuesFile` | `profile-declaration` |
| effective | `/ownership/workloadVersion` | `identity-of-a-different-content` |
| effective | `/runtime/replicaCount` | `intended-variable` |

- `intended-variable`: the path carries the runtime replica count. One values
  path carries it, and the contract's replica range feeds that path.
- `identity-of-a-different-content`: the path is a version, a digest, or an
  identifier of a document that differs at a permitted path.
- `prose-not-rendered`: no render reads the path.
- `profile-declaration`: the field is what makes the declaration a profile. In
  the install layer it is the generated values file that each side reads.

A permitted path may differ only to the declared counts. The baseline must state
one runtime replica and the target two, and each side must state two API
replicas. A baseline with three runtime replicas is refused.

**Each release is derived again for the comparison.** The tool reads no committed
generated file when it compares. So an edit of a committed values file does not
change the comparison. A second rule compares the committed baseline release with
the derived one, byte for byte.

**The comparison has no trusted side.** An edit of the target's contract is a
difference, as an edit of the baseline's contract is.

## What the two releases share

The generated values of the two sides are equal at every path but two. A test
compares the two committed values files as bytes: two lines differ. Each row but
the last four is about the members that the generated values hold.

| Input | Where it is | State |
|---|---|---|
| Workload identity, owner, tenant, and cost centre | `ownership` in the generated values | Equal, but for the workload version |
| Model identifier, revision, artifact pins, and cache claim | `model` in the generated values | Equal |
| Runtime image digest and repository | `runtime.image` | Equal |
| Runtime CPU and memory ceiling | `runtime.resources.limits` | Equal |
| Runtime rollout bounds | `runtime.rollout`: one pod unavailable, no pod above the count | Equal |
| API replica count and API rollout bounds | `api.replicaCount`, `api.rollout` | Equal: two replicas |
| The API values that a caller meets: request timeout, drain timeout, and output-token ceiling | `api` | Equal |
| Telemetry and secret references | `telemetry`, `security` | Equal |
| Probe settings, requests, and images of the other tiers | The chart's defaults, and the hand-written values of each side | Equal as values: the effective values of the two sides differ at two paths only, and each of the 24 readiness inputs is stated |
| Hand-written values, release name, namespace, and the chart's repository, revision, path, and version | The install description of each side | Equal. See [the install inputs](#the-install-inputs) |
| API image digest | The declared comparison inputs | Equal as declared values. Not an install input and not an observed identity. See [the API image digest](#the-api-image-digest) |
| The chart's templates, and so each rendered object | The chart files | One digest for both sides. The tool compares no rendered object: see below |
| The runtime tier's PodDisruptionBudget | The chart renders one for a tier of two or more replicas | Not equal, since chart `0.6.0`: the target renders it, and the baseline does not. It follows from the runtime replica count. See the note of 2026-10-09 above |

**Readiness inputs are not in the generated values. The tool compares them as
values, and it renders nothing.** The chart's defaults state each probe setting,
and the hand-written values of a side can replace one. The tool compares the
values that the chart receives on each side. It does not run Helm, so it does
not compare a rendered probe.

Three tests of the chart suite render. Each renders a side with the hand-written
values of its own install description, the release name and the namespace that
the description states, and one placeholder API image digest for both sides.
The placeholder is not the declared digest, and the render tests do not read
the comparison inputs.

- **The two sides as described.** The two renders differ in three objects of
  the same name: one
  ConfigMap value that carries the workload version, the configuration checksum
  annotation of the API pod template and of the runtime pod template, and the
  `replicas` line of the runtime Deployment. The target also renders the runtime
  tier's budget. Each probe, each resource request and limit, each image, the
  model mount, both rollout strategies, and both Services are rendered the same.
- **A readiness timeout changed on one side.** The rendered readiness probe of
  the API differs, and the comparison record refuses the same edit.
- **Scrape annotations switched off on one side.** The pod templates of that
  side lose the scrape annotations, so the renders differ beyond the stated
  differences. The record refuses the same edit.

The render tests need the chart tool, and they skip on a host without it.

**One runtime replica under the target's rollout bounds.** The baseline keeps
`runtime.rollout.maxUnavailable` 1 and `runtime.rollout.maxSurge` 0. Under
`maxSurge` 0 a rollout creates no pod above the replica count. So with one
replica, a rollout removes the one runtime pod before its replacement is
created, and no runtime pod is Ready until the replacement loads the model.
[The chart's page](../../charts/inferops-llm/README.md) states the same for its
default of one replica. That is read from the render and from what Kubernetes
documents. It was not observed on a cluster.

## The rules

A comparison record states 13 rules, in this order:

| Rule | Statement |
|---|---|
| `baseline-declaration-differs` | The baseline declaration states the bindings, the binding name, the platform defaults, and both revisions that the target declaration states, and its directory is outside the Git desired state. |
| `baseline-sources-refused` | The declared sources of the baseline and of the target each derive a release. |
| `baseline-contract-differs` | The two contract documents differ only in the replica range, the workload version, and the description. |
| `baseline-values-differ` | The two generated values documents differ only in the runtime replica count and the workload version. |
| `baseline-release-differs` | The two release documents differ only in the release identifier, the workload version, the contract digest, and the values digest. |
| `baseline-topology-not-declared` | The baseline states two API replicas and one runtime replica. The target states two API replicas and two runtime replicas. Each contract states a replica range of one number. |
| `baseline-version-not-distinct` | The baseline and the target name one workload and two workload versions. |
| `baseline-install-inputs-refused` | The install description of the baseline and of the target is each a file that parses, that states each member this tool compares, and that states no other member in a block this tool reads. Each names a chart of this tree. |
| `baseline-install-differs` | The two install descriptions differ only in the generated values file, and each names the generated values file of its own release. |
| `baseline-effective-values-differ` | The effective values of the two sides differ only in the runtime replica count and the workload version, and they state the replica counts of each side. They are the chart's defaults, then the derived generated values, then the hand-written values. |
| `baseline-readiness-input-unusable` | The effective values of each side hold each of 24 readiness inputs with a usable value: the 23 values that the two probe templates read, and the startup budget of the runtime. |
| `baseline-api-image-digest-unbound` | The declared comparison inputs are a file that parses and that states no member this tool does not read. They state one API image digest for the baseline and one for the target. Each digest is sha256: and 64 lowercase hexadecimal digits, and the two digests are equal. |
| `baseline-api-image-digest-contradicted` | The effective values of each side state no API image digest, or they state the declared digest of that side. |

The state of a rule is `held`, `not-held`, or `not-evaluated`. When the sources
of one side derive no release, eight rules are `not-evaluated`: the third to the
seventh, the tenth, the eleventh, and the last. When the install description of
one side is not read whole, four rules are `not-evaluated`: the ninth to the
eleventh, and the last. The result is `REFUSED` in both cases. The twelfth rule
reads the declared comparison inputs alone, so it is evaluated in every record.

`--check` adds three rules for the committed files:

| Rule | Statement |
|---|---|
| `baseline-release-drifted` | The committed baseline release is, byte for byte, what its declared sources derive. |
| `baseline-target-release-drifted` | The committed target release is, byte for byte, what its declared sources derive. So the values file that the target's description names holds the generated values that were compared. |
| `baseline-record-stale` | The committed comparison record is, byte for byte, the record that the files of this tree give. |

**A change to both sides is comparable, and it is still reported.** A platform
default moves both releases alike. The comparison holds. The committed baseline
release and the committed record then no longer describe the tree, so `--check`
fails until a person reads the difference and writes them again. The committed
target release no longer describes the tree either, and
`baseline-target-release-drifted` reports it. This tool does not write the
target's release: `python -m tools.gitops_desired_state --write` with the
release's key does. The record
states the digests and the identifiers of both releases, so a change to the
target alone makes the record stale too.

**What each accidental change is reported as.** The suite plants each of these.
A contract, a binding, a platform default, and a committed file are edited in a
copy of the inputs. Another binding, another defaults file, another revision,
and another directory are given as a replaced declaration, because the tool's
own declaration cannot state them.

- **A resource ceiling, the runtime image digest, the model identifier, the
  owner, or the tenant of the baseline contract** is `baseline-contract-differs`
  at the contract path and `baseline-values-differ` at the values path.
- **Another workload name** is those two rules, `baseline-release-differs`, and
  `baseline-version-not-distinct`.
- **A contract member that no render reads**, such as the runbook reference or
  the data classification, is `baseline-contract-differs` alone.
- **A model revision or a replica range that the render boundary refuses** is
  `baseline-sources-refused`, and nothing is compared.
- **Another runtime replica count** is `baseline-topology-not-declared`.
- **One API replica in the binding** is `baseline-topology-not-declared` for both
  sides.
- **Another binding, another platform-defaults file, or another revision in the
  baseline declaration** is `baseline-declaration-differs`, and the value or the
  release field that moves with it is refused under its own rule. The other
  binding states one API replica, so it is `baseline-topology-not-declared` too.
- **A profile directory inside `gitops/`** is `baseline-declaration-differs`. So
  is a directory that is not one relative POSIX path of plain segments, such as
  `./gitops/...` or a path with a backslash, and `GitOps/...` in another case.
- **A list entry that one contract lacks** is `baseline-contract-differs` at the
  entry's index.
- **A probe setting or another hand-written value that one description states
  alone** is `baseline-install-differs` at the path in the description, and
  `baseline-effective-values-differ` at the path in the values when the chart
  then receives another value. A value that the chart's default already states
  is `baseline-install-differs` alone.
- **Another release name, namespace, cluster address, chart repository, chart
  revision, or chart path in one description** is `baseline-install-differs`.
- **A baseline description that names the target's generated values file** is
  `baseline-install-differs`.
- **A hand-written runtime replica count** is `baseline-effective-values-differ`
  for the side that then states another count than its topology, whether one
  description states it or both do.
- **A null that removes a readiness input on one side** is
  `baseline-install-differs`, `baseline-effective-values-differ`, and
  `baseline-readiness-input-unusable`.
- **A readiness input that the chart's defaults no longer state, or state with
  a value of another type,** is `baseline-readiness-input-unusable` for both
  sides.
- **An absent description, a description that does not parse, a key stated
  twice, a description that refers to itself, an absent member, another member
  in a block that the tool reads, or a chart without a template, a values
  schema, or a version** is `baseline-install-inputs-refused`.
- **A declared API image digest that is absent or malformed, on one side or on
  both, one malformed text on both sides, two valid digests that differ, or
  comparison inputs that are not read whole** is
  `baseline-api-image-digest-unbound`.
- **One digest in both descriptions that is not the declared one**, valid or
  not, is `baseline-api-image-digest-contradicted` for both sides. A digest in
  one description alone is that rule for the one side, with
  `baseline-install-differs` and `baseline-effective-values-differ`.
- **Another valid digest declared for both sides** is comparable, and
  `baseline-record-stale` reports it.
- **One change made to both descriptions, a changed chart file that moves no
  effective value, or a changed project or sync policy of the Application** is
  comparable, and `baseline-record-stale` reports it.
- **A hand edit of the committed target values, or a missing target values
  file,** is `baseline-target-release-drifted`. The comparison itself does not
  change, because it derives the values.
- **A hand edit of the committed baseline values or of the committed release
  document, or a file beside the two generated files,** is
  `baseline-release-drifted`.
- **An edited record, a missing record, a record with another line ending, or a
  directory at the record's path** is `baseline-record-stale`.

**The comparison's walk does not rest on the parsers.** A release is derived
before it is compared, so a contract that the render boundary refuses is never
compared. The walk of two documents still tells apart a sequence and a mapping
whose keys spell its indexes, a mapping with a key that is not text, and a whole
number and a fraction of equal value. A test gives it each.

## How to run it

```sh
# Verify the committed profile. Writes nothing.
uv run --locked python -m tools.baseline_profile --check
# Print the comparison record that the files of this tree give.
uv run --locked python -m tools.baseline_profile --record
# After a deliberate change to an input: read the findings, then write again.
uv run --locked python -m tools.baseline_profile --write
```

`--check` exits 0 when no rule is broken, and 1 when one is. It writes nothing.

`--record` prints one JSON record. Exit status 0 says that the result is
`COMPARABLE`. Exit status 5 says that the result is `REFUSED`.

**A current record and a refused comparison are two outcomes.** Exit status 0
of `--check` says that the committed record is the record of this tree and that
the comparison holds. A refusal is exit status 5 of `--record`, and exit status
1 of `--check` with the rule that refuses. A stale record alone is exit status
1 of `--check` with `baseline-record-stale`, while `--record` still exits 0.

`--write` writes the baseline release and the record again. It does not write
the install description or the declared comparison inputs. It refuses to write
when the comparison is `REFUSED`, and it refuses a profile directory that holds
a file the platform did not write. A write replaces a hand edit without asking,
so read the `--check` output first. It writes the release before the record. If
the record cannot be written, the two are out of step: `--check` reports it, and
a second `--write` repairs it.

Exit status 2 says that the arguments are not usable.

**A refusal is a result.** Do not add a path to the permitted differences to
obtain `COMPARABLE`. A new permitted path is a second variable of the
comparison, and it is a decision.

## Not applied yet

| Not applied | Why | What it needs |
|---|---|---|
| An Application, or a desired-state path, for the baseline | No Application reads the profile. The one Application reads the target, and the Git desired state holds one release | A decision on how a run selects the baseline in the environment that the experiment names |
| A procedure that installs the baseline from its install description | The description is compared, and nothing reads it to install a release | A decision on how a run selects the baseline, and a check that the run's inputs are the described ones |
| A check that a run installs both sides with the declared API image digest | The digest is a declared comparison input. The procedure that applies the Application takes its digest from the operator, and it does not read the comparison inputs | A run that gives both sides the declared digest, a record of the digest that each side's pods reported, and a check of the two |
| A caller profile | No caller profile exists in this repository | A caller profile, and a check that both sides are given the one revision of it |
| The footprint of the baseline in the capacity preflight | [The capacity preflight](capacity-preflight.md) derives the footprint from the Application of the target | An Application for the baseline, or a footprint that the gate derives another way |
| A run of the baseline | The profile is a render | An environment that holds it, and a frozen experiment record |
| A frozen experiment that names the profile | No experiment that uses the baseline is frozen | A freeze record that pins the profile's inputs |
| A baseline that follows a changed target contract | The baseline is the `0.1.0` contract, which a freeze record pins | A decision, when the target's contract changes at a path that is not permitted |
| A profile directory in the desired state | A rule and a test refuse it | A change of that rule, of the record, and of this page, with the decision on how a run selects the baseline |

## What a record does not establish

- That a cluster ran the baseline. No Application reads the profile directory,
  and no run installed the baseline release.
- What a caller observes when the one runtime pod of the baseline stops, or when
  one of the two runtime pods of the target stops.
- That the baseline is eligible for an experiment. The result is a statement
  about committed inputs, and every record states the eligibility as
  not-established.
- That a run installs either release with the install inputs that this record
  states. The record compares two committed descriptions. No procedure reads the
  baseline's description, and nothing compares a cluster with either.
- That a run installs either release with the declared API image digest. The
  digest is a declared comparison input: a committed file states it. The
  procedure that applies the target takes its digest from the operator, and it
  does not read that file. No procedure installs the baseline.
- That a cluster ran a pod of the declared API image on either side. The record
  states no observed runtime identity, and no cluster was read.
- That the declared API image digest names an image that exists, an image that
  was built from this tree, or the image that a later build gives. The tool
  checks the form of the digest, and it reads no image.
- That a cluster reads the chart files whose digest this record states. Each
  description names a branch as the chart revision, and the digest is of the
  files of the tree that the tool read.
- That the two releases render equal probes. The record compares effective
  values and one digest of the chart files. This tool does not run Helm, and it
  parses a description as YAML 1.1, which Helm's parser does not do for every
  plain scalar.
- That the baseline is delivered as the target is. The record states the
  project, the sync policy, and the name of the target's Application, and it
  compares none of them. The baseline names no controller.
- That an applied Application is the committed one. The procedure that applies
  it adds the API image digest as one Helm parameter, and this tool reads the
  committed file.
- That a probe behaves as its settings state, or that a pod was Ready. No
  cluster was read.
- That the model cache claim is in one state for both sides. The claim's name
  and its mount are compared. Its content and its state are not.
- That one caller profile is applied to both sides. No caller profile exists in
  this repository, and the record lists it as unresolved.
- That telemetry of the two sides is equal. The workload version differs, and it
  is a resource attribute of the API's telemetry.
- That a cluster holds the baseline. The capacity preflight derives the
  footprint of the target only.
- That either recorded revision is the commit a release was rendered at, or that
  it names a commit.

The record also does not compare a comment of a contract, because a comment is
not part of the parsed document.

## Where the profile is checked

```sh
uv run --locked python -m tools.baseline_profile --check
uv run --locked python -m pytest tests/domain/test_baseline_profile.py -q
uv run --locked python -m pytest tests/architecture/test_helm_chart.py -q -k baseline
uv run --locked python -m pytest tests/domain/test_generated_release_drift.py tests/domain/test_renderer_input_boundary.py -q
```

The default-lane suite holds each of these test modules, and one test runs the
`--check` command. The render comparisons need the chart tool. They skip on a
host without it.
