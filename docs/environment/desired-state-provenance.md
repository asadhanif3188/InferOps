# Desired-state provenance

Status: **a tool resolves a Git commit to the release identity, and every check of
it is static.** `V2-S3-003-PR1` added
[`tools/desired_state_provenance`](../../tools/desired_state_provenance/core.py) and
[its suite](../../tests/domain/test_desired_state_provenance.py). The tool reads Git
objects of this repository. It reads no cluster. Every check on this page is at
evidence level `C0`.

**This change adds no label, no annotation, and no metric label.** It changes no
chart template, no manifest, and no procedure. No cluster was contacted.

| Property | Value |
|---|---|
| Tool | [`tools/desired_state_provenance`](../../tools/desired_state_provenance/core.py): `python -m tools.desired_state_provenance --revision COMMIT` |
| Input | One full commit identifier: the commit that Argo CD reports that it resolved |
| Output | One JSON record for each [desired-state release](git-desired-state.md), with the schema identifier `inferops.io/desired-state-provenance/v1alpha1` |
| Reads | Git objects of this repository, at the given commit |
| Writes | Nothing |
| Tests | [`tests/domain/test_desired_state_provenance.py`](../../tests/domain/test_desired_state_provenance.py) |
| Validation record | [`v2-s3-003-pr1-validation.md`](../proof/environment/v2-s3-003-pr1-validation.md) |

## The problem

[The Argo CD Application](argocd-application.md) follows `main`. A branch name is
not an identity. After the next merge, `main` names another commit.

Argo CD resolves `main` to a commit and reports that commit. A commit identifier
does not move. It identifies every file in the repository at that commit: the chart,
the generated values, and the release document that says what the values were
rendered from.

The tool starts from that commit.

## The trace

```text
an applied object
        |   it is in the namespace and the release that the Application names
        |   (not checked here)
the Application
        |   Argo CD reports the commit it resolved `main` to
        |   (not collected here: the commit is given to the tool)
a full commit identifier                     <- the immutable Git identity
        |   python -m tools.desired_state_provenance --revision COMMIT
the release document at that commit
        |
release identifier, values digest, contract digest, binding digest,
renderer revision, workload identity, chart version
```

1. **Read the commit that Argo CD reports.**
   `scripts/environment/argocd-application.sh verify` prints the commit that
   Argo CD resolved and the commit of the last sync operation.
2. **Resolve the commit.**

   ```sh
   uv run --locked python -m tools.desired_state_provenance --revision <the 40-character commit>
   ```

3. **Read the record.** It names the release that the commit holds.

The command exits 0 and prints the records when every selected release resolved. It
exits 1 when one was refused. It then prints each refusal to the standard error
stream and prints no record. It exits 2 when the arguments are not usable: no
revision, or an unknown key. A key, `<binding name>/<workload>`, selects one
release.

## The record

```json
{
  "schema": "inferops.io/desired-state-provenance/v1alpha1",
  "git": { "revision": "293767b6c27d858e911e5e43104ad74fbfac4b02" },
  "desiredState": {
    "key": "local-docker-desktop/support-assistant",
    "directory": "gitops/environments/local-docker-desktop/workloads/support-assistant",
    "releasePath": "gitops/environments/local-docker-desktop/workloads/support-assistant/rendered-workload-release.yaml",
    "valuesPath": "gitops/environments/local-docker-desktop/workloads/support-assistant/values.generated.yaml"
  },
  "release": {
    "releaseId": "eeda9493e0ffca2af499342e2850c63e30ff7254d094016c816d7fbe23fc01ae",
    "workloadId": "support-assistant",
    "workloadVersion": "0.1.0",
    "valuesSha256": "1849af0c88c2ef646b4f6eddfb515ba5fd3f3cbc5ac44950a35b9bf8cec864ce",
    "contractSha256": "56f73f78a6d741db15b28061b01f323935365c0d63b4d84b936e5ca6ca709c0d",
    "environmentBinding": {
      "name": "local-docker-desktop",
      "environment": "local",
      "sha256": "afaabe71a3b8cd83f4b19dd076341b611a184b02c8ad7a4eb0ed3e16054f1251"
    },
    "rendererRevision": "c056b9772a3de391fd61589649b1d3ed1c5ac7c4",
    "platformDefaultsRevision": "c056b9772a3de391fd61589649b1d3ed1c5ac7c4"
  },
  "chart": {
    "path": "charts/inferops-llm",
    "name": "inferops-llm",
    "version": "0.3.0",
    "appVersion": "0.1.0"
  },
  "workloadLabels": {
    "helm.sh/chart": "inferops-llm-0.3.0",
    "app.kubernetes.io/version": "0.1.0",
    "inferops.io/workload": "support-assistant"
  }
}
```

This is the record at the commit that Argo CD reported in the three runs of
2026-10-04. The command prints a list of such records, with sorted keys.

- **The record holds identifiers and digests only.** It holds no timestamp, no host
  name, and no path outside the repository. One commit and one release give one
  document.
- **`git.revision` is the input.** The tool does not find a commit. It is given
  one, and it does not establish that a controller reported it.
- **`release` is read from the release document at the commit.** The tool does not
  compute a release identifier of its own.
- **`chart` is read from `Chart.yaml` at the commit.**
- **`workloadLabels` is derived.** It is the value of three labels that the chart
  already sets: `helm.sh/chart`, `app.kubernetes.io/version`, and
  `inferops.io/workload`. The chart sets the first two on every object, and the
  third when the values name a workload, which generated values do. The chart
  label is formed as the chart's helper forms it, and a test holds that.

## What the tool checks at the commit

- The release document parses, and its identifier is the one that its workload
  identity and source derive. It names `values.generated.yaml`, and the release
  domain's rule finds no credential-shaped identifier in it.
- The values file hashes to the digest that the release records.
- The contract and the binding at the commit are the ones that the release names,
  by identity and by digest.
- The values name the workload identifier and the workload version that the release
  names.
- The chart declares a name, a version, and an application version.

The tool reads five kinds of file at the commit: the release document, the values
file, the contract, each declared binding, and `Chart.yaml`. Each is read as the
Git object that the commit holds. An uncommitted edit of one of those files
changes nothing.

**The declaration and the rules are the checkout's, and not the commit's.** Which
paths are read comes from the declared release in the code that runs. The parsers
and the rules are that code too.

**A commit from before a declaration change is refused under the new declaration.**
Since `V2-S4-002-PR1` the declared release is derived from another contract document,
[`synchronous-llm-two-replicas.yaml`](../../contracts/workload/examples/valid/synchronous-llm-two-replicas.yaml).
A commit made before that change does not hold that file. The command reads every
commit with the declaration of the checkout it runs from, so it refuses such a commit
under `desired-state-absent-at-revision` and names the contract path. It does not try
an earlier declaration. The commit that the recorded runs reported is such a commit.
A test reads it through the library function, with the declaration that held at that
commit, and it still resolves to the release identifier the records state. The command
has no option for an earlier declaration.

The tool runs one Git subcommand, `cat-file`, in two read-only forms. It disables
Git replacement objects and lazy fetching, and it removes the caller's `GIT_*`
variables, so a `GIT_DIR` that a hook sets does not replace the repository it was
given. A test reads the tool's source for the two forms. It observes no process.

## The rules

The first seven rules refuse a record. The last three compare a record with an
observation that a caller supplies.

| Rule | Statement |
|---|---|
| `revision-not-immutable` | A revision is 40 lowercase hexadecimal characters and not one repeated character. A branch name, a tag name, and an abbreviated commit are not identities. |
| `revision-not-readable` | Git is available, and it reports that the repository at the root holds the revision as a commit object. |
| `desired-state-absent-at-revision` | The commit holds both generated files of the release, each contract and binding the release is declared from, and the chart's Chart.yaml. |
| `release-not-accepted` | The release document at the commit parses, names the generated values file, holds no credential-shaped identifier, and has the identifier its workload identity and source derive. |
| `values-digest-mismatch` | The values file at the commit hashes to the digest the release records. |
| `release-sources-mismatch` | The contract and the binding at the commit are the ones the release names, by identity and by digest, and the values name the workload the release names. |
| `chart-identity-unreadable` | The chart at the commit declares a name, a version, and an application version, each as a non-empty string. |
| `source-not-the-release` | An Application reads the chart the release was rendered for from this repository, and its one value file is the values file of the release. |
| `observed-revision-mismatch` | Each commit a controller reports is the commit the record was read at. |
| `workload-metadata-mismatch` | An applied object carries the chart label, the application-version label, and the workload label that the record derives. |

**A branch name is refused before Git runs.** `main`, `HEAD`, a tag name, a
seven-character commit, and an uppercase commit are each
`revision-not-immutable`. The tool resolves no name. If it resolved `main`, it would
report the commit that `main` names on the contributor's machine, which may not be
the commit that Argo CD resolved.

**A shallow clone holds only the commits it fetched.** A commit that the clone does
not hold is `revision-not-readable`. Fetch the commit, or use a full clone.

**The identifier of a tag object is refused.** Git reads a tag object as the commit
it points at. The tool asks Git for the type of the object and refuses any type
other than a commit, so the record never names an identifier that is not a
commit. The same refusal covers a tree, a file, and a directory that is not a
repository.

## The comparisons

Three functions compare a record with an observation. Each takes plain values. The
tool collects no observation.

| Function | Compares the record with | Rule |
|---|---|---|
| `source_findings` | What an Application declares that it reads: the repository, the chart path, and the value files. A second value file is a finding, because a later file overrides the generated values. Inline values and parameters are not compared | `source-not-the-release` |
| `observed_revision_findings` | The commits that a controller reported. No reported commit is one finding | `observed-revision-mismatch`, `revision-not-immutable` |
| `metadata_findings` | The `metadata.labels` of one applied object | `workload-metadata-mismatch` |

The suite uses each function on committed files:

- **The committed Application.** Its source is the repository, the chart path, and
  the values file that the record names. It follows `main`, and the tool refuses
  `main` as a revision.
- **The three recorded runs.** Each transcript of
  [the runs of 2026-10-04](../proof/environment/v2-s3-002-pr2-argocd-application-run.md)
  reports one commit as the commit that Argo CD resolved, synced, and applied:
  `293767b6c27d858e911e5e43104ad74fbfac4b02`. That commit resolves to the release
  identifier `eeda9493e0ffca2af499342e2850c63e30ff7254d094016c816d7fbe23fc01ae`.
  The third run was driven from a checkout at another commit, `f2ef48f`, so the
  commit that Argo CD resolved does not identify the manifest that was applied.
  The test reads the transcripts as files. It skips in a checkout that does not
  hold the commit.
- **A render.** Every object and every pod template of the chart, rendered from the
  generated values, the Application's hand-written values, and a placeholder API
  image digest, carries the three labels that the record derives. That test runs
  `helm template` and skips when Helm is absent. A second test reads the chart's
  committed real render and needs no Helm.

In the suite, no function is given a value that was read from a cluster. Since
`V2-S3-003-PR2`, [the reconciliation evidence tool](reconciliation-evidence.md)
gives the three functions what an `observe` collection read. On 2026-10-05, on
one provider, it gave them what Argo CD reported and the labels of the applied
objects, and no function reported a finding.
[The record of those runs](../proof/environment/v2-s3-003-pr2-reconciliation-observation-run.md)
holds the samples. The evidence tool does not give the commit that Argo CD
resolved to `observed_revision_findings`: the record is read at that commit.

## Why no label was added

**The three labels are not an identity.** Two releases of one workload on one chart
version carry the same three labels. The labels are a consistency check. The
identity is the commit.

Three alternatives were considered and not taken.

- **A release-identifier label or annotation on every object.** The release
  identifier would have to be a generated value, and the chart would have to render
  it. That changes the renderer and the chart. The freeze records of the first
  experiment pin both, so the change needs a freeze revision first. This change
  does not make it.
- **A commit annotation, given to the chart as a parameter that Argo CD fills.** The
  chart sets its common annotations on the pod templates of the API Deployment and
  the runtime Deployment too. A commit annotation would change those two pod
  templates at every merge to `main`, including a merge that changes no workload
  file. A changed pod template rolls a Deployment. This was not executed, and it
  was not taken.
- **A release-identifier annotation on the Application.** The Application is not
  desired state. An operator applies it, and it then follows `main`. After a merge
  that regenerates the release, the annotation would name the previous release while
  Argo CD applies the new one.

**This change adds no metric label.** A commit of this repository and the release
identifier of a release document are unbounded values, and this change puts
neither on a series. The build-information series already carries a label named
`inferops.release.id`. Its value is the Helm release name, and not the release
identifier in the record. The chart's scrape configuration reads three pod labels,
the part-of label, the instance label, and the component label, and a test holds
that it reads none of the three provenance labels.

## Not applied yet

| Not applied | Why | What it needs |
|---|---|---|
| A finding of one of the three comparisons on a cluster | `V2-S3-003-PR2` added [the collection](reconciliation-evidence.md), and two runs on one provider compared their samples. Every comparison agreed | An observation of a state that disagrees |
| The release identifier of the release document on an applied object | The renderer and the chart are pinned by the first experiment's freeze records | A freeze revision, then a generated value and a chart label |
| The render repeated at the commit | The tool reads five kinds of file and renders nothing | A check that derives the release from the sources at the commit |
| A check that the commit is on `main` | The tool reads objects and no branch | A decision on which remote reference is authoritative |
| A way to suspend reconciliation for a manual change | [The boundary](reconciliation-evidence.md#the-boundary-for-a-manual-change) is stated, and it decides no mechanism | A decision record |

## What this does not establish

- **That an applied object was rendered at the commit.** Argo CD reports the commit
  that it compared and the commit of its last sync operation. The record relates a
  commit to the release that the commit holds. It relates no object to either.
- **That a controller reported the commit.** The commit is an input.
- **That the commit declares the same release paths as the checkout that ran the
  tool.** The declaration and the rules are the checkout's.
- **That two commits with one record hold the same chart.** The record names the
  chart version and no digest of the templates. The commits `293767b` and `b2be70b`
  give the same `release` and `chart` sections. The commit identifies the
  templates. The record does not.
- **That the renderer revision and the platform-defaults revision name commits.**
  The tool copies both from the release document.
- **That the commit is reachable from a branch or a remote.** A commit that exists
  only in the local clone resolves.
- **That a cluster carries the labels.** The labels were read from a render. The
  transcripts of the recorded runs hold no label of an applied object.
- **That Argo CD reports the commit that it applied.**
- **Anything about the API image.** Its digest is not in Git. An operator gives it
  to the procedure, and the record does not name it.
- **Anything about the hand-written values.** They are in the Application manifest,
  which an operator applies from a working tree. The commit that Argo CD resolved
  does not identify the manifest that was applied.
- **That the values file is what the recorded renderer revision derives.** The
  default lane derives the release from the sources of the checked-out commit. This
  tool does not repeat that at the given commit.
- **That the commit is on `main`, or that the merge was reviewed.**
- **That the record holds no secret.** It is built from identifiers and digests. A
  test applies the release domain's credential-prefix heuristic to every value, and
  a heuristic knows only the prefixes it was given.
- **Anything about a caller.** A commit, a sync state, and a label say nothing about
  whether a request was answered.
- **Anything about `kind`.** One release is declared, for the `local-docker-desktop`
  binding.

## Validation

```sh
uv run --locked python -m pytest tests/domain/test_desired_state_provenance.py -q
uv run --locked python -m tools.desired_state_provenance --revision "$(git rev-parse HEAD)"
uv run --locked python -m tools.gitops_desired_state --check
uv run --locked ruff check . && uv run --locked ruff format --check . && uv run --locked mypy
```
