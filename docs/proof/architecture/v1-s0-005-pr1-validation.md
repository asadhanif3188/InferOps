# V1-S0-005-PR1 change validation

Date: 2026-08-25

Classification: **local static evidence for the change itself.** Every result below
comes from reading and validating files in this repository. No cluster was created,
no Terraform was run, no chart was rendered, no model was loaded, and no request was
served. Nothing here is evidence that the architecture works, because almost none of
it is built.

Claim boundary: the committed ownership inventory is internally consistent under
every rule the suite states; twenty-nine deliberate corruptions of it are refused;
the architecture documents and the inventory cannot drift apart without a test
failing; every relative link resolves; and the published diff carries no private,
generated, or overclaimed content.

**What this record does not establish.** There is no Terraform configuration and no
Helm chart in this repository, so nothing compares the inventory to an
implementation. There is no platform API, adapter, or deployment rendering, so
nothing checks the component decomposition at all. Every diagram in this change is
reviewed, not verified.

## Environment

| Component | Version |
|---|---|
| Operating system | Microsoft Windows 11 Enterprise, `10.0.26200` |
| Python | `3.12.6` |
| `pytest` | `8.3.4` |
| `jsonschema` | `4.26.0` |
| `PyYAML` | `6.0.2` |
| `ruff` | `0.16.1` |
| Git | `2.45.1.windows.1` |
| GNU bash | `5.2.26(1)-release (x86_64-pc-msys)` |

`jsonschema` and `PyYAML` are listed because the full-suite run below includes the
contract tests, which need them. The architecture suite this change adds needs
`pytest` alone.

## Commands and results

### The architecture suite

```text
python -m pytest tests/architecture -q
326 passed
```

Twenty-five test functions, parametrised across eight owners and thirty resources.

### The full suite, to show nothing else moved

```text
python -m pytest tests -q
517 passed, 7 skipped
```

Before this change the same command reported `191 passed, 7 skipped`. The seven
skips are the contract suite's existing, deliberate ones: a test that asks what a
consumer validating against the bare schema sees, which only the structural
fixtures can answer. This change adds no skip and removes none.

### Linting and formatting

```text
ruff check .
All checks passed!

ruff format --check .
47 files already formatted
```

`ruff` is not a selected repository tool — no linter or continuous-integration lane
has been chosen — but the existing Python in this repository is clean under it, and
a new file that was not would be a gratuitous inconsistency.

### Inventory shape

```text
owners 8 resources 30
Counter({'helm': 9, 'contributor-host': 5, 'terraform': 4,
         'kubernetes-control-plane': 4, 'repository': 2, 'workload-owner': 2,
         'external-publisher': 2, 'undecided': 2})
Counter({'planned': 19, 'implemented': 8, 'deferred': 3})
```

Eight of thirty resources exist today and each cites the record that proves it.
Nineteen are planned and none of them cites anything. Three are deferred, two of
those because nobody owns them.

### Whitespace, tabs, and links

```text
git diff --check --cached
(no output)

git ls-files -z '*.md' | xargs -0 grep -n '[[:blank:]]$'
(no matches)

git ls-files -z '*.md' | xargs -0 grep -n "$(printf '\t')"
(no matches)
```

The relative-link scan from the contribution guide was run over every tracked
Markdown file and reported no broken target. It reported two while this record did
not yet exist — both pointing at this file — and none after it was written.

### Kubernetes manifests and shell scripts

Not run, and not skipped silently: this change adds no file under `deploy/` and no
file under `scripts/`, so `kubeconform` and `shellcheck` have nothing to look at.

## What the suite asserts

| Group | Checks |
|---|---|
| Shape | The inventory declares its identifier and contract version; every owner and every resource carries every required field and no undeclared one; no required string is empty; identifiers are unique and are lowercase hyphenated slugs |
| Single ownership | `owner` is one string and names a declared owner. A second owner is not expressible |
| The acceptance criterion | The set of Terraform-owned resources and the set of Helm-owned resources are disjoint, asserted directly rather than inferred from the field's type |
| Reference is not ownership | Every referrer is a declared owner, and no resource lists its own owner among its referrers |
| No dead owners | Every declared owner owns at least one resource, and every declared lifecycle is used |
| Lifecycle agreement | A resource's lifecycle is the lifecycle its owner declares |
| Survival | Survival claims are drawn from the declared operations, contain no duplicate, and never include the operation that destroys the resource |
| Tool ownership means tool destruction | A Terraform- or Helm-owned resource is created and destroyed by its own tool's commands, not by delegation |
| Layering | Every prerequisite survives `helm uninstall`; no release resource survives `terraform destroy` or a scoped object teardown |
| Derived objects | Every derived resource is owned by the control plane and is destroyed by no tool command |
| Status and evidence | `v1Status` is from the controlled vocabulary; an implemented resource cites a record that exists; a planned or deferred resource cites nothing; a resource with no owner is deferred out of V1 |
| Document agreement | The ownership document publishes every resource and every owner in the data, and both architecture documents cite the inventory rather than restating it |

## Twenty-nine-mutation rejection spot check

A passing suite proves that the inventory as written satisfies it. It does not prove
the suite would notice if the inventory were wrong. Each mutation below was applied
to a copy of the inventory, the suite was run against it, and the original was
restored afterwards. Nothing in the mutation harness is committed.

| Mutation | Result |
|---|---|
| Move the namespace from Terraform to Helm | Refused |
| Move it and adjust its lifecycle so the obvious check passes | Refused |
| Let a release resource survive `terraform destroy` | Refused |
| Let a release resource survive a scoped object teardown | Refused |
| Let the model cache claim die with a release | Refused |
| Let a resource survive the operation that destroys it | Refused |
| Bring an unowned resource into V1 scope | Refused |
| Let a planned resource cite evidence | Refused |
| Remove the evidence an implemented resource cites | Refused |
| Point an evidence reference at a file that does not exist | Refused |
| Point the inventory's own document reference at a file that does not exist | Refused |
| List a resource's own owner among its referrers | Refused |
| Name an undeclared referrer | Refused |
| Duplicate a resource | Refused |
| Rename a resource so the document no longer publishes it | Refused |
| Add an owner nobody uses | Refused |
| Remove the last user of a declared lifecycle | Refused |
| Have a controller-derived object destroyed by `helm uninstall` | Refused |
| Delegate a Helm-owned resource's destruction to Terraform | Refused |
| Name an operation the inventory does not declare | Refused |
| Repeat an operation in a survival list | Refused |
| Use an undeclared lifecycle | Refused |
| Use a status outside the vocabulary | Refused |
| Empty a required field | Refused |
| Delete a required field | Refused |
| Add an undeclared field | Refused |
| Use an identifier that is not a slug | Refused |
| Change the inventory's schema identifier | Refused |
| Express `owner` as a list of two owners | Refused |

```text
accepted mutations: 0 of 29
```

The last row is the one worth reading twice. Making ownership a list of two owners
is the exact failure the acceptance criterion forbids, and the suite refuses the
*representation* rather than the value, which is why it cannot be worked around by
choosing two owners that happen not to overlap elsewhere.

What this spot check does **not** establish: that the rules the suite enforces are
the right rules. Twenty-nine refusals show the checks are live. They say nothing
about a boundary the inventory does not model at all.

## Private-information review of the diff

Every line of the change was read against
[the public-information boundary](../../governance/repository.md).

| Category | Result |
|---|---|
| Credentials, tokens, secret values | None. The change adds no fixture, no manifest, and no configuration; the only credential-adjacent text is the rule that a chart may never template a secret value |
| Personal filesystem paths, host identifiers | None. Every path in the diff is repository-relative |
| Generated or local state | None. The mutation harness was written and run outside the repository and is not committed |
| Model artifacts or outputs | None |
| Unpublished planning material, prompts, work queues, positioning | None. Future work is described as shapes of work — a gateway, deeper serving — using vocabulary this repository already published in ADR 0002, and no project, schedule, or plan is named |
| Capability claims without evidence | None found. Every component below the contract layer is marked unbuilt in the diagram that draws it, in the document that describes it, and in the record that decides it |

The review covered the lines this change adds and modifies. It is not an audit of
files this change does not touch.

## Limitations

- **The ownership inventory is checked against itself, not against reality.** No
  Terraform configuration and no Helm chart exists.
- **The component architecture is checked by nothing.** There is no code.
- **The diagrams are ASCII and unrendered.** Nothing validates that a diagram still
  matches the prose beside it; a reviewer does.
- **One host, one operating system, one point in time**, as with every record here.
  The suite reads only files and has no clock, network, or randomness, so it is
  expected to behave identically elsewhere — but it has been run on one machine.
- **The scoped-teardown overlap is recorded, not fixed.** The environment scripts
  are unchanged by this pull request, and the lifecycle label that resolves the
  overlap is specified and unimplemented.

## Acceptance criteria

| Criterion | Status |
|---|---|
| Architecture distinguishes platform, serving, infrastructure, telemetry, evidence, and integrations | **Met.** Six diagrams and their narrative, with a stated split between telemetry and evidence and an explicit statement that a declared integration is not a provided one |
| Terraform and Helm ownership do not overlap | **Met, and enforced.** Single ownership is unrepresentable otherwise, disjointness is asserted directly, and a two-owner mutation is refused |
| Native serving and future-project boundaries are explicit | **Met.** Two serving capabilities, three boundary rules, and a review checklist that turns them into questions |
| No resource has ambiguous lifecycle ownership | **Met, with the ambiguity named rather than hidden.** Two resources have no owner; both carry an explicit `undecided` owner and both are deferred out of V1, which a test enforces |
