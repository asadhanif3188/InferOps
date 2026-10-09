# The single-runtime baseline profile

Status: **the profile exists as a generated release and a comparison record, and
a check holds both. This is evidence at C0. No Application reads the profile, and
no run installed the baseline release. The profile is an experiment baseline. It
is not a product tier, and it is not desired state.**

The desired-state release declares two platform API replicas and two serving
runtime replicas. A later experiment compares the loss of one runtime pod under
that topology with the loss of the one runtime pod under a baseline. That
comparison means something only while the runtime replica count is the one
variable that differs. This page describes the baseline, each difference that it
is permitted to have, the check that refuses any other difference, and what a
comparison record does not establish.

| Property | Value |
|---|---|
| Baseline topology | Two API replicas and one serving runtime replica |
| Target topology | Two API replicas and two serving runtime replicas: the [desired-state release](git-desired-state.md), key `local-docker-desktop/support-assistant` |
| Profile directory | `tests/domain/fixtures/experiment-profiles/single-runtime-baseline` |
| Comparison record | `tests/domain/fixtures/experiment-profiles/single-runtime-baseline.comparison.v1alpha1.json` |
| Tool | [`tools/baseline_profile`](../../tools/baseline_profile/core.py): `python -m tools.baseline_profile --check`, `--record`, and `--write` |
| Tests | [`tests/domain/test_baseline_profile.py`](../../tests/domain/test_baseline_profile.py), and one render comparison in [`tests/architecture/test_helm_chart.py`](../../tests/architecture/test_helm_chart.py) |
| Validation record | [`v2-s4-003-pr2-validation.md`](../proof/environment/v2-s4-003-pr2-validation.md) |
| Read by | Nothing. No Application reads the profile, and no procedure calls the tool |

## How the baseline is declared

**The baseline is the target's declaration with one input replaced.** The tool
takes the declaration of the desired-state release and replaces the contract and
the directory. It keeps the binding, the platform defaults, and both revisions.

| Declared input | Baseline | Target |
|---|---|---|
| Contract | [`synchronous-llm-local.yaml`](../../contracts/workload/examples/valid/synchronous-llm-local.yaml), version `0.1.0` | [`synchronous-llm-two-replicas.yaml`](../../contracts/workload/examples/valid/synchronous-llm-two-replicas.yaml), version `0.2.0` |
| Directory | The profile directory | `gitops/environments/local-docker-desktop/workloads/support-assistant` |
| Binding | `local-docker-desktop`, which states two API replicas | The same file |
| Platform defaults | The `api` block and `runtime.rollout` of `charts/inferops-llm/values.yaml` | The same file |
| Renderer revision and platform-defaults revision | The target's | `40803f2fe9a95753da6480de1e5321efafb3cbf0` for both |

**The change adds no contract.** Version `0.1.0` of the reference workload
declares a replica range of one and one. Version `0.2.0` declares two and two.
The two documents differ in the version, the description, and the replica range.
The baseline is version `0.1.0` rendered on the binding that the target uses.

**A workload version names one content.** The two contracts differ in content, so
they differ in version. The version is a rendered value. So the two releases
differ in two values and not in one: the runtime replica count, and the workload
version that follows it. A baseline that kept the target's version would give
one version two contents, and the check refuses it.

The baseline release identifier is
`acf6fbc799ea50ab43b76f5ab48e81bf82bb89bda808319c22f9ae42d22753fb`. The target
release identifier is
`79b1e3890f1f820a64115c4e5a362a6ddf114ba48cbeecf1788106a173e66812`.

## The permitted differences

The tool compares four layers: the two declarations, the two contract documents,
the two generated values documents, and the two release documents. A path is a
JSON pointer into the document of its layer. **A difference at a path that this
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

- `intended-variable`: the path carries the runtime replica count. One values
  path carries it, and the contract's replica range feeds that path.
- `identity-of-a-different-content`: the path is a version, a digest, or an
  identifier of a document that differs at a permitted path.
- `prose-not-rendered`: no render reads the path.
- `profile-declaration`: the field is what makes the declaration a profile.

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
compares the two committed values files as bytes: two lines differ.

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
| Probes, requests, images of the other tiers, Services | The chart's templates and its other defaults | One chart for both sides. A render comparison holds it: see below |

**Readiness inputs are not in the generated values.** The chart's templates and
defaults own each probe. Both sides are rendered by the one chart, so no path in
a profile selects another probe. The tool does not run Helm. One test of the
chart suite renders both releases with one hand-written values file and compares
every object. The two renders differ in three objects: one ConfigMap value that
carries the workload version, the configuration checksum annotation of the API
pod template and of the runtime pod template, and the `replicas` line of the
runtime Deployment. Each probe, each resource request and limit, each image, the
model mount, both rollout strategies, and both Services are rendered the same.

**One runtime replica under the target's rollout bounds.** The baseline keeps
`runtime.rollout.maxUnavailable` 1 and `runtime.rollout.maxSurge` 0. With one
replica, those bounds permit a rollout to remove the one runtime pod before its
replacement exists. That is read from the render. It was not observed on a
cluster.

## The rules

A comparison record states seven rules, in this order:

| Rule | Statement |
|---|---|
| `baseline-declaration-differs` | The baseline declaration states the bindings, the binding name, the platform defaults, and both revisions that the target declaration states, and its directory is outside the Git desired state. |
| `baseline-sources-refused` | The declared sources of the baseline and of the target each derive a release. |
| `baseline-contract-differs` | The two contract documents differ only in the replica range, the workload version, and the description. |
| `baseline-values-differ` | The two generated values documents differ only in the runtime replica count and the workload version. |
| `baseline-release-differs` | The two release documents differ only in the release identifier, the workload version, the contract digest, and the values digest. |
| `baseline-topology-not-declared` | The baseline states two API replicas and one runtime replica. The target states two API replicas and two runtime replicas. Each contract states a replica range of one number. |
| `baseline-version-not-distinct` | The baseline and the target name one workload and two workload versions. |

The state of a rule is `held`, `not-held`, or `not-evaluated`. When the sources
of one side derive no release, the last five rules are `not-evaluated`, and the
result is `REFUSED`.

`--check` adds two rules for the committed files:

| Rule | Statement |
|---|---|
| `baseline-release-drifted` | The committed baseline release is, byte for byte, what its declared sources derive. |
| `baseline-record-stale` | The committed comparison record is, byte for byte, the record that the files of this tree give. |

**A change to both sides is comparable, and it is still reported.** A platform
default moves both releases alike. The comparison holds. The committed baseline
release and the committed record then no longer describe the tree, so `--check`
fails until a person reads the difference and writes them again. The record
states the digests and the identifiers of both releases, so a change to the
target alone makes the record stale too.

**What each accidental change is reported as.** The suite plants each of these
in a copy of the inputs:

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
  release field that moves with it is refused under its own rule.
- **A profile directory inside `gitops/`** is `baseline-declaration-differs`.
- **A hand edit of the committed baseline values, or a file beside the two
  generated files,** is `baseline-release-drifted`.
- **An edited or a missing record** is `baseline-record-stale`.

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

`--write` writes the baseline release and the record again. It refuses to write
when the comparison is `REFUSED`, and it refuses a profile directory that holds
a file the platform did not write. A write replaces a hand edit without asking,
so read the `--check` output first.

Exit status 2 says that the arguments are not usable.

**A refusal is a result.** Do not add a path to the permitted differences to
obtain `COMPARABLE`. A new permitted path is a second variable of the
comparison, and it is a decision.

## Not applied yet

| Not applied | Why | What it needs |
|---|---|---|
| An Application, or a desired-state path, for the baseline | No Application reads the profile. The one Application reads the target, and the Git desired state holds one release | A decision on how a run selects the baseline in the environment that the experiment names |
| Hand-written values for the baseline | The target's hand-written values are inside its Application. The baseline declares none | The same values for both sides, where a run applies the baseline |
| A caller profile | No caller profile exists in this repository | A caller profile, and a check that both sides are given the one revision of it |
| The footprint of the baseline in the capacity preflight | [The capacity preflight](capacity-preflight.md) derives the footprint from the Application of the target | An Application for the baseline, or a footprint that the gate derives another way |
| A run of the baseline | The profile is a render | An environment that holds it, and a frozen experiment record |
| A frozen experiment that names the profile | No experiment that uses the baseline is frozen | A freeze record that pins the profile's inputs |

## What a record does not establish

- That a cluster ran the baseline. No Application reads the profile directory,
  and no run installed the baseline release.
- What a caller observes when the one runtime pod of the baseline stops, or when
  one of the two runtime pods of the target stops.
- That the two releases install with equal hand-written values. The baseline
  declares none. A run must give both sides the values that the target's
  Application states.
- That one caller profile is applied to both sides. No caller profile exists in
  this repository.
- That a cluster holds the baseline. The capacity preflight derives the
  footprint of the target only.
- That either recorded revision is the commit a release was rendered at, or that
  it names a commit.

The record also does not compare a comment of a contract, because a comment is
not part of the parsed document. It does not compare the chart's templates,
because both sides name the one chart.

## Where the profile is checked

```sh
uv run --locked python -m tools.baseline_profile --check
uv run --locked python -m pytest tests/domain/test_baseline_profile.py -q
uv run --locked python -m pytest tests/architecture/test_helm_chart.py -q -k baseline_profile
uv run --locked python -m pytest tests/domain/test_generated_release_drift.py tests/domain/test_renderer_input_boundary.py -q
```

The default-lane suite holds each of these test modules, and one test runs the
`--check` command. The render comparison needs the chart tool. It skips on a
host without it.
