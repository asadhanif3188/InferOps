# V1-S0-005-PR1 change validation

Date: 2026-08-25

Classification: **local static evidence for the change itself.** Every result below
comes from reading and validating files in this repository. No cluster was created,
no Terraform was run, no chart was rendered, no model was loaded, and no request was
served. Nothing here is evidence that the architecture works, because almost none of
it is built.

Claim boundary: the committed ownership inventory is internally consistent under
every rule the suite states; thirty-two deliberate corruptions of it are refused;
the architecture documents and the inventory cannot drift apart in either direction
without a test failing; every relative link resolves; and the published diff carries
no private, generated, or overclaimed content.

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
357 passed
```

Twenty-seven test functions, parametrised across eight owners and thirty resources.

### The full suite, to show nothing else moved

```text
python -m pytest tests -q
548 passed, 7 skipped
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
48 files already formatted
```

`ruff` is not a selected repository tool — no linter or continuous-integration lane
has been chosen — but the existing Python in this repository is clean under it, and
a new file that was not would be a gratuitous inconsistency. The count is 48 rather
than the nine tracked Python files because `ruff format` also inspects Markdown for
embedded Python; nothing in this repository's Markdown contains any, so every one of
the 39 Markdown files reports formatted without anything being reformatted.

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
| The property that matters most | The set of Terraform-owned resources and the set of Helm-owned resources are disjoint, asserted directly rather than inferred from the field's type |
| Reference is not ownership | Every referrer is a declared owner, and no resource lists its own owner among its referrers |
| No dead owners | Every declared owner owns at least one resource, and every declared lifecycle is used |
| Lifecycle agreement | A resource's lifecycle is the lifecycle its owner declares |
| Survival | Survival claims are drawn from the declared operations, contain no duplicate, and never include the operation that destroys the resource |
| Blast radius | A survival list is a prefix of the operation ordering, which escalates from a pod restart to deleting the cluster. A resource that survives a wider operation must survive every narrower one |
| Tool ownership means tool destruction | A Terraform- or Helm-owned resource is created and destroyed by its own tool's commands, not by delegation |
| Layering | Every prerequisite survives `helm uninstall`; no release resource survives `terraform destroy` or a scoped object teardown |
| Derived objects | Every derived resource is owned by the control plane and is destroyed by no tool command |
| Status and evidence | `v1Status` is from the controlled vocabulary; an implemented resource cites a record that exists; a planned or deferred resource cites nothing; a resource with no owner is deferred out of V1 |
| Document agreement | Both directions. The ownership document publishes every resource and every owner in the data, and every identifier the document publishes in a table's first column exists in the data. Both architecture documents cite the inventory rather than restating it |

Two of these are weaker than they look, and the suite says so in its own docstrings
rather than leaving a reader to find out. **The "never survives what destroys it"
check can only fail where `destroyedBy` names one of the five declared operations**;
for roughly half the inventory it is descriptive prose — a contributor, a controller,
an upstream publisher — and the assertion is vacuous for those rows. The blast-radius
check was added for exactly that reason and is the one that bites on every row. And
**the document-agreement check reads identifiers, not prose**: a table row whose
description has drifted from the `handoff` text in the data passes.

## Thirty-two-mutation rejection spot check

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
| Let a resource skip an operation and claim a wider one | Refused |
| Reorder a survival list so it is no longer a prefix of the ordering | Refused |
| Delete a resource from the data and leave it in the document | Refused |
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
accepted mutations: 0 of 32
```

The last row is the one worth reading twice. Making ownership a list of two owners
is the exact failure this change is measured against, and the suite refuses the
*representation* rather than the value, which is why it cannot be worked around by
choosing two owners that happen not to overlap elsewhere.

Three of these mutations were added after a review found the suite weaker than the
document beside it claimed. Deleting a resource from the data while leaving it in
the prose was **accepted** by the first version of this suite, and the document said
it would not be — that is the defect the reverse check and this row now close.

What this spot check does **not** establish: that the rules the suite enforces are
the right rules. Thirty-two refusals show the checks are live. They say nothing
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

## What this change set out to do, and whether it did

| Goal | Status |
|---|---|
| A reader can tell the platform, the serving path, the infrastructure beneath it, telemetry, evidence, and declared integrations apart | **Met.** Six diagrams and their narrative, with telemetry and evidence deliberately separated and an explicit statement that a capability a contract may name is not one this project provides |
| Two tools never contend for one resource | **Met, and enforced.** A second owner is not expressible; disjointness is asserted directly anyway; and a mutation that tries to express two owners is refused |
| The one serving path this project owns is distinguishable from work that belongs elsewhere | **Met.** Two serving capabilities, three boundary rules with the reasoning behind each, and a checklist that turns them into questions a reviewer can answer |
| Every resource has an unambiguous lifecycle owner | **Met, with the ambiguity named rather than hidden.** Two resources have no owner. Both carry an explicit `undecided` owner and both are deferred out of V1, which a test enforces rather than a convention |
