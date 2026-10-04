# ADR 0018: Generated releases are the Git desired state, one directory for one binding and one workload

| Field | Value |
|---|---|
| Status | **Accepted in part** |
| Date proposed | 2026-10-04 |
| Date accepted | 2026-10-04, for the decisions the table below marks accepted |
| Decision owner | [`repository-maintainer`](../../governance/decision-authority.md) |
| Supersedes | None |
| Amends | None. The ownership inventory gains one row, owned by `repository`, and no decision of [ADR 0004](ADR-0004-component-and-ownership-boundaries.md) changes |
| Superseded by | None |

> [!IMPORTANT]
> This record decides where V2 keeps the desired state of a workload, and what
> that directory may hold. **Nothing reconciles the directory.** No Application
> exists, no cluster was contacted, and nothing in the directory was installed.
>
> The directory is [`gitops/`](../../../gitops/README.md). It holds one generated
> release: the reference workload on the `local-docker-desktop` binding. The
> release is the two files the platform writes. No file in the tree is written by
> hand, except the page that says what the tree is.
>
> The generated values alone do not install the chart. The chart requires four
> values that no contract owns, and they are still written by hand. Where that
> hand-written file lives for an installed release is not decided here.
>
> The rules are explained in
> [the desired-state document](../../environment/git-desired-state.md) and checked
> by `tests/domain/test_gitops_desired_state.py`.

## Decision status

| ID | Decision | Status | What supports it |
|---|---|---|---|
| D1 | Desired state is kept in this repository, under `gitops/` | **Accepted** | [ADR 0017](ADR-0017-argocd-bootstrap-and-ownership.md) D1 selected the repository. This record names the directory. Review alone |
| D2 | A release directory is `<destinationPath>/workloads/<workloadId>` | **Accepted** | A check derives the path from the EnvironmentBinding and the WorkloadContract and refuses a release anywhere else |
| D3 | The tree holds generated releases and nothing written by hand | **Accepted** for the tree. Where a hand-written values file lives is **open** | A check walks the tree and refuses every entry that no declared release accounts for |
| D4 | One path exists: the reference workload on `local-docker-desktop`. No promotion ladder is created | **Accepted** as scope | A test pins the one declaration, and the check refuses a second environment directory that nobody declared |
| D5 | The desired state changes when a reviewed change is accepted into `main` | **Accepted** as a rule | Review alone. Nothing in this repository verifies that a merge was reviewed |
| D6 | A desired-state release records a full Git revision, not a placeholder, as its renderer and platform-defaults revision | **Accepted**, with a stated limit | A check holds the form of the revision and refuses one repeated character. A test compares the defaults at that commit with the defaults read today, in a full clone only. Nothing establishes that the revision names a commit |
| D7 | The releases are declared in a tool of their own, and derived through the existing drift check | **Accepted** | The tool calls the drift check and holds no second renderer. The first experiment's freeze record pins no file that this change edits |
| D8 | The Application, its project, its sync policy, and the followed revision are not decided here | **Accepted** as scope | The absence test of ADR 0017 still holds: no Argo CD custom resource is committed |

Seven of the eight decisions are accepted. D3 is accepted for the tree and open for
an installed release. That open part is why this record is accepted in part. No
decision is proposed.

## Context

Since `V2-S2-001` the platform generates a release from a validated
WorkloadContract, an EnvironmentBinding, and the platform defaults. Since
`V2-S2-002` a check compares each committed generated release with its declared
sources. The one committed release was a test fixture, at placeholder revisions.

[ADR 0017](ADR-0017-argocd-bootstrap-and-ownership.md) selected Argo CD as the
GitOps controller and decided how it is installed. Its D1 says that desired state
is kept in this repository, and that the record "does not decide the desired-state
layout or the Application". Its suite refused a `gitops/` directory, because no
record had decided one.

Each EnvironmentBinding already declares `spec.gitops.destinationPath`. Until this
record, that path named a directory that did not exist.

A controller needs a path to read. That path must hold what was reviewed, and a
reader must be able to say which inputs produced each file in it.

## Decision criteria

In order:

1. **One source for every value.** A value that a contract, a binding, or the
   platform defaults owns is written in one place. The desired state must not
   become a second place.
2. **A reviewer can read the change that a merge applies.** The generated
   difference is in the same change as its cause.
3. **A path is derived, not chosen.** The inputs of a release determine where it
   is committed.
4. **Nothing in the tree is unaccounted for.**
5. **The smallest layout that serves one workload on one environment binding.**

## D1 — The directory

**Accepted.**

Desired state is kept under `gitops/`, at the repository root. The destination
path of a binding that a declared release names is under `gitops/environments/`,
and the check refuses one that is not. The binding schema does not require it, so
a binding that no release names is not held to it. Nothing ties the directory's
name to the binding's name.

`gitops/` is a build directory. The suite that holds ADR 0017 reads it with the
other build directories, and refuses a file in it that names the controller.

## D2 — The path of a release

**Accepted.**

```text
gitops/
└── environments/
    └── <environment binding>/            spec.gitops.destinationPath
        └── workloads/
            └── <workload id>/            the contract's metadata.name
                ├── rendered-workload-release.yaml
                └── values.generated.yaml
```

A release directory is `<destinationPath>/workloads/<workloadId>`. The selected
binding declares the destination path. The contract names the workload. The
directory is derived from those two documents, and a release committed at another
path is refused.

Three consequences follow:

- **The binding owns the environment's path.** If a binding changes its
  destination path, the committed release is at a path that nothing derives, and
  the check fails until the declaration and the release are both moved.
- **One binding may hold several workloads**, each in its own directory.
- **One workload may be released on two bindings.** The command therefore selects
  a release by `<binding name>/<workload id>`.

The first experiment's freeze record says that the generated release is committed
"at the binding's `spec.gitops.destinationPath`", in its procedure and in its
topology. This record reads that as the workload's directory beneath that path.
No freeze revision names the exact path yet. A later revision for the
real-deployment part must name it before a result-bearing run.

The same record says that a hand-written values file is admitted "beside" the
generated values. That is the admission rule's term: the two files are given to
Helm together. It does not place the file in the release directory, and D3 keeps
it out.

| Alternative | Assessment |
|---|---|
| **`<destinationPath>/workloads/<workloadId>`** | **Selected.** The binding's path stays an environment-level fact, and a second workload needs no second binding |
| The release at `<destinationPath>` itself | Not selected. One binding could then hold one workload, and a second workload would need a second binding with the same environment facts |
| `gitops/<workloadId>/<environment>` | Not selected. The binding already declares a path, and a layout that ignores it leaves a declared value that nothing reads |
| One values file with a per-environment overlay | Not selected. An overlay is a hand-written file that sets generated values. The renderer exists to remove that second copy |

## D3 — Generated files only

**Accepted for the tree.**

A release directory holds `values.generated.yaml` and
`rendered-workload-release.yaml`, and nothing else. The tree holds release
directories, the directories that lead to them, and `gitops/README.md`. The check
refuses every other entry: a hand-written values file, a copy of a release under
another name, an empty directory, and a symbolic link or a directory junction. A
link at a declared path is refused too, and a regeneration does not write through
one.

A file in the tree is changed only by regeneration. A contributor changes the
contract or the binding, regenerates the release by key, and commits both in one
change. A change to the platform defaults or to the renderer needs two commits,
and D6 says why.

**The generated values do not install the chart alone.** The chart's guards
require four values that no WorkloadContract owns: the API image repository and
digest, the model alias, and the licence identifier. A test in the chart suite
measures that list. For the reference workload they are in a hand-written file
that is a test fixture, and its API image digest is a placeholder.

**Where the hand-written file for an installed release lives is open.** It is not
in this tree. The change that adds the first Application decides its location and
how the Application reads it. Until then the tree is reviewable, and it is not
installable by itself.

| Alternative | Assessment |
|---|---|
| **Generated files only** | **Selected.** Every file in the tree is derived, so the drift check covers all of it |
| The admitted hand-written file beside the release | Not selected here. The drift check refuses any third file in a release directory, and the API image the file names is a contributor's local build. The decision belongs with the Application that reads the file |
| A hand-written `values.yaml` for each environment | Not selected. It would be a second authoritative source of values that a contract or a binding owns |

## D4 — One path

**Accepted as scope.**

One release is declared: the reference workload, `support-assistant`, on the
`local-docker-desktop` binding. That binding names the one provider on which the
Argo CD bootstrap was executed. No release is committed for `local-kind`, because
no bootstrap ran there.

No `dev`, `staging`, or `production` directory is created. An environment
directory exists only for a binding that a declared release names. A second path
is a second declaration, made on purpose, and a test pins the list.

## D5 — The promotion boundary

**Accepted as a rule.**

```text
change a contract, a binding, or the platform defaults
        |
regenerate the release                  python -m tools.gitops_desired_state --write KEY
        |
review the source change and the generated difference together
        |
the change is accepted into main        <- the promotion boundary
        |
a controller reads the new revision     NOT BUILT: no Application exists
```

The desired state is the content of `gitops/` on `main`. It changes when a
reviewed change is accepted into `main`, and by no other step. No second
promotion stage exists: one environment has one path.

A regeneration on a contributor's machine changes nothing until that change is
accepted. Verification writes nothing.

**What holds this rule is review.** The default-lane suite fails a change whose
release is stale, hand-edited, or at the wrong path. It does not establish that a
person reviewed the change. This repository does not claim that branch protection
is configured.

## D6 — The revisions a release records

**Accepted, with a stated limit.**

A RenderedWorkloadRelease records the revision of the renderer and of the platform
defaults. The reference release in the test fixtures records placeholders. A
desired-state release records a full Git revision that is not a placeholder, and
the check refuses one that is.

A release cannot name the commit that adds it. For a change that edits neither
the renderer nor the chart's `api` defaults, the revision is therefore the commit
that the generating change was based on. For the first release that is
`c056b9772a3de391fd61589649b1d3ed1c5ac7c4`.

**A change to the `api` defaults or to the renderer is the exception.** The base
commit holds the old files. The declared revision must then be a commit of the
same change that already holds the new ones. That change needs two commits and a
merge that keeps them.

**The limit.** The revision is declared by the contributor. The check holds its
form: 40 lowercase hexadecimal characters, and not one repeated character. A
made-up revision of that form passes the check, and a test pins that.

One test reads the defaults file at the declared commit and compares it with the
defaults read today. It skips in a checkout that does not hold the commit. The
hosted default lane uses a shallow checkout, so the test skips there and runs
only in a full clone. A revision that names no commit skips the same test. It
does not fail it. No test compares the renderer's source at that commit with the
renderer that runs.

## D7 — Where the releases are declared

**Accepted.**

`tools/gitops_desired_state` declares each desired-state release and its inputs.
It derives and compares through `tools/generated_release`, the existing drift
check, and holds no second renderer.

The declarations are not added to the drift check's own list. The first
experiment's freeze record pins the files of that package, and a new entry there
would move a pin. The drift check's own test still requires that every tracked
generated file is declared, and it now reads both lists.

## D8 — What this record does not decide

**Accepted as scope.**

- **The Application and its project.** None is committed. ADR 0017 R5 and R6
  stay open.
- **The sync policy**: automated sync, self-heal, and pruning.
- **The revision the controller follows.**
- **What becomes of the `helm` rows** of the ownership inventory when a
  controller applies the chart.
- **A desired-state path for `kind`.**

## Consequences

- **A binding's destination path now names a directory that exists.** The binding
  document said that no such directory existed. It is updated.
- **A change to the reference contract, the `local-docker-desktop` binding, or the
  chart's `api` defaults now fails the suite until the release is regenerated.**
  That is the intended cost: the generated difference is reviewed with its cause.
- **The suite of ADR 0017 no longer refuses a `gitops/` directory.** It still
  refuses a committed Argo CD custom resource, anywhere in the repository.
- **A merge to the branch an Application follows will change a cluster**, once
  one follows this tree. ADR 0017 states the same consequence. D5 keeps the
  desired state on `main`, and D8 leaves the followed revision undecided. Review
  of a change to `gitops/` then becomes the approval of a deployment.
- **A committed release is public.** The generated files carry names an author
  chose, and the bounded property the renderer document states applies to them.

## Compatibility impact

No published contract, schema, or API changes. No chart, Terraform file, script,
or workflow changes. No file that the first experiment's freeze record pins
changes. The ownership inventory gains one row and loses none. A new tool and a
new top-level directory are added.

## Security considerations

This record asserts no new security property.

- **The tree becomes a path into a cluster** when an Application follows it.
  Whoever can change `gitops/` on the followed branch can then change what runs.
  ADR 0017 records that for the Git remote. No control is added here, because no
  Application exists.
- **Generated files are meant for Git.** A contract that declares a secret
  reference is refused before anything is generated, and a known credential shape
  is refused. A secret written as an otherwise valid public name is not detected.
  The renderer document states that limit, and it applies to this tree.
- **The check reads the working tree.** A file that Git ignores is still found. A
  second test reads the index, so a tracked file is found too. On a file system
  that ignores case, a root named `GitOps` passes the working-tree check, and the
  test that reads the index does not pass it.

## Evidence

`C0`, static, on 2026-10-04, under
[the evidence levels](../../testing/evidence-levels.md). **No cluster was
contacted and nothing was installed.** The full record is
[the V2-S3-002-PR1 change validation](../../proof/environment/v2-s3-002-pr1-validation.md).

What the suite establishes: that the committed release is at the path its binding
and contract derive; that it is, byte for byte, what its declared sources derive;
that the tree holds nothing else; and that each planted defect is refused under
its own rule. What it establishes about whether a controller reconciles the tree,
or whether the release serves a request: **nothing**. No claim is registered.

## Risks, assumptions, and open questions

| ID | Item | Status | Impact |
|---|---|---|---|
| R1 | The generated values do not install the chart alone | Open | Four hand-written values are required. The API image is a contributor's local build, published to no registry. The change that adds the first Application must say where those values come from |
| R2 | The recorded revision is a declaration | Accepted | A contributor can declare a commit at which the renderer differed, or a string that names no commit. The defaults at that commit are compared in a full clone, and not in the hosted lane. The renderer's source is not compared |
| R3 | Nothing verifies that a merge was reviewed | Open | The promotion boundary is a rule that review holds. Branch protection is not claimed as configured |
| R4 | The path rule reads "at the destination path" as "beneath it" | Open | The freeze record says "at" in its procedure and in its topology. A later freeze revision must name the exact path before a result-bearing run. None does yet |
| R5 | A release committed for one provider says nothing about another | Accepted | The one path is for `local-docker-desktop`. `kind` has no path and no bootstrap run |
| R6 | The check reports a file the operating system created | Accepted | The walk reads the working tree, so a stray file in `gitops/` fails the suite locally. It is removed, not exempted |
