# V1-S3-005-PR1 validation — Terraform platform prerequisites

Change: the platform prerequisite layer exists. A Terraform module and a local
environment declare the namespace, its shared metadata, and the model cache
claim; a wrapper script runs them against this project's cluster and refuses to
run them against anything else; and an architecture suite compares the
configuration against the ownership inventory in both directions. This record is
what was run, what it found, and what it does not support.

**Evidence class.** Everything asserted here is `local-static`: files read,
compared, formatted, and validated. **Nothing has been applied.** No
`terraform plan`, `terraform apply`, or `terraform destroy` was run against any
cluster, by this change or by anyone, so no namespace was created, no claim was
provisioned, and no state file exists. Every Terraform-owned row in the ownership
inventory is still `planned`, and a test in this change enforces that it stays
`planned` until an apply is recorded.

## What the change is

Four things, and each answers one of the parent story's acceptance criteria.

**Terraform owns three documented prerequisites and nothing else.** The module
declares `kubernetes_namespace_v1.platform` and
`kubernetes_persistent_volume_claim_v1.model_cache`, which are the inventory rows
`platform-namespace`, `namespace-metadata`, and `model-cache-volume-claim`. The
fourth Terraform-owned row, `platform-resource-quota`, is deferred out of V1 and
is deliberately absent; a test fails if it appears. There is one provider, it
talks to one local cluster, and no cloud resource of any kind is declared.

**Helm workload resources are excluded, and the exclusion is checked rather than
promised.** `tests/architecture/test_terraform_prerequisites.py` compares the
declared resource set against the inventory in both directions and refuses a
release object, a derived object, a second provider, a `helm_release`, or
anything that would create a cluster. The declared kinds are checked as an
allowlist as well as a denylist, so a kind nobody thought to forbid still fails.
This is the check
[the ownership document](../../architecture/resource-ownership.md) said could not
exist yet; its closing paragraph has been rewritten to say what the check now
covers and what it still cannot.

**The lifecycle marker specified in ADR 0004 is finally set.** Every object this
project creates carries `app.kubernetes.io/part-of: inferops`, so a scoped
teardown matching only that label would delete a prerequisite and give one
resource two destroyers. The resolution was a second label, specified in ADR 0004
and implemented nowhere. Terraform now sets
`inferops.io/lifecycle: prerequisite` on the namespace and on the claim. **The
matching exclusion in the environment scripts is still not implemented**, and the
ownership document now says so explicitly rather than describing the whole
resolution as pending.

**Nothing inherits an ambient target.** The provider names both the kubeconfig
and the context, a variable validation refuses a context that is not one of this
project's kind clusters, and the wrapper establishes cluster identity from the
node containers' kind labels before Terraform is invoked at all. The Terraform
half is a name check and the configuration says so; the identity check is the
wrapper's.

## Commands and results

### Python

```text
uv run --locked ruff check .           All checks passed!
uv run --locked ruff format --check .  291 files already formatted
uv run --locked python -m mypy         Success: no issues found in 154 source files
uv run --locked python -m pytest -q    6180 passed, 27 skipped, 14 deselected
```

The default lane runs 6,180 on this branch against 6,070 on `main`. The
`main` figure is from a clean worktree checked out at `main` rather than from a
stash, for the reason the `V1-S3-003` record gives: several suites parametrise
over committed files, so a stash that leaves new documents in the tree returns a
baseline that is too high.

The two suites this change adds to or edits:

```text
uv run --locked python -m pytest tests/architecture/test_terraform_prerequisites.py -q   96 passed
uv run --locked python -m pytest tests/architecture/test_cluster_lifecycle_safety.py -q  82 passed
uv run --locked python -m pytest tests/architecture/test_helm_chart.py -q               154 passed
```

The new suite is 96 rather than the 87 it was first written with. The nine
additions are the adversarial tests described under the review below: they put
each ownership rule to a violation and require it to fire.

The safety suite went from 72 to 82 because `terraform-prerequisites.sh` was
added to its entry-point list, which subjects the new script to every rule the
other environment scripts already obey: it sources the shared library, hardcodes
no cluster name, refuses an argument it does not understand, prunes nothing,
sweeps no namespace, and writes to no default kubeconfig.

### Terraform

```text
terraform version                                                    Terraform v1.15.8 on windows_386
terraform fmt -check -recursive infra/terraform                      exit 0, no output
terraform -chdir=infra/terraform/environments/local init -backend=false -input=false
                                                                     Installed hashicorp/kubernetes v2.38.0 (signed by HashiCorp)
                                                                     Terraform has been successfully initialized!
terraform -chdir=infra/terraform/environments/local validate         Success! The configuration is valid.
```

`-backend=false` is what makes the second command offline with respect to state:
it initialises the provider and the module and skips the backend entirely. It is
not offline with respect to the registry — it downloads the provider — and that
is the one network access this validation performs.

The lock file was generated for six platforms rather than for the one this ran
on:

```text
terraform -chdir=infra/terraform/environments/local providers lock \
  -platform=linux_amd64 -platform=linux_arm64 \
  -platform=darwin_amd64 -platform=darwin_arm64 \
  -platform=windows_amd64 -platform=windows_386
```

`windows_386` is in that list because it is what this host's Terraform build
reports, and a lock that omitted the platform it was generated on would be a lock
for other people and not for the person who wrote it. A clean re-initialisation
with the six-platform lock in place was run and succeeded.

### What was not run, and why

| Not run | Why |
|---|---|
| `terraform plan` | Needs a cluster. There is none on this host: `kind` is not installed, the container engine was not running, and the project kubeconfig `.kube/inferops-dev.config` does not exist |
| `terraform apply` | Same, and the brief authorises an apply only where a local cluster is available and safe |
| `terraform destroy` | Same. It is also the widest operation in this layer and there is nothing to destroy |
| A re-apply idempotency measurement | Requires an apply to have happened |
| `shellcheck -x -S style scripts/environment/*.sh` | `shellcheck` is not installed on this host. The new script was checked with `bash -n` only, which parses and does not lint |
| `kubeconform` | This change adds no Kubernetes manifest. Terraform declares resources through a provider rather than through YAML, and there is nothing under `deploy/` to validate |
| A cluster-side check of the prerequisite label | Needs an applied namespace |

The apply table in
[the prerequisite document](../../environment/platform-prerequisites.md) is
derived from the provider's documented semantics and is labelled there as
expectation rather than measurement. It should be replaced with observed
behaviour by whichever change first applies this against a cluster.

## Design decisions worth recording

**The claim is Terraform's, not the chart's.** This follows ADR 0004 (D4) and
costs what that decision says it costs: `helm uninstall` leaves roughly 1.71 GiB
occupied until `terraform destroy` runs. The alternative — a Helm-owned claim —
was already paid for once in the feasibility trial, where scoped teardown
destroyed the weights and re-running cost the full download again over a
transport that does not validate certificates.

**`wait_until_bound` is false.** The accepted local provisioner binds a claim on
first consumer, so a claim nothing mounts is `Pending` by design. The provider's
own default is to wait, which would hang an apply until its timeout and then
report a correctly-provisioned prerequisite as a failure. This is the single
most likely way for the first real apply of this configuration to look broken
while being correct, which is why it is a variable with its reasoning attached
rather than an inline literal.

**The provider pin is exact, and on the 2.x line.** A range resolves to whatever
was published most recently, which makes "it worked yesterday" a statement about
the registry. The 3.x line exists; crossing a provider major version changes
resource schemas and how state represents them, and that is a decision to take
with a plan against a real cluster in front of you. Nothing here has been
applied, so this change is in no position to take it.

**State is a local file and there is no backend block.** A remote backend needs a
bucket, a lock table, and credentials, for a cluster that lives inside one
laptop's container engine and is deleted by a script; adding one would be
provisioning paid infrastructure to hold the record of a namespace. The stated
cost is that two contributors have two unrelated state files and neither knows
about the other — correct with one cluster each, and wrong the moment a shared
cluster exists, which V1 does not have.

**The two names that make the handoff work are compared, not trusted.** The
namespace default is checked against `INFEROPS_RELEASE_NAMESPACE` in
`scripts/environment/lib.sh` and the claim name against `model.cache.claimName`
in the chart's real values file. If those drift, the release does not fail at
render time; it fails at schedule time with a claim that does not exist.

## Private-information review of the diff

The diff was read in full for host paths, credentials, planning content, and
generated artifacts.

- **No absolute path.** The kubeconfig default is relative to the configuration
  directory, and a test refuses a Windows drive letter, a `/home/`, a `/Users/`,
  or a `/mnt/<letter>/` path anywhere in the configuration.
- **No credential.** A test refuses `client_certificate`, `client_key`,
  `cluster_ca_certificate`, `password`, `token`, and an `exec` credential plugin
  in the configuration. The provider reads a kubeconfig by path; that file is
  git-ignored and is never copied into state.
- **No state and no plan.** `.gitignore` gained `.terraform/`, `*.tfstate`,
  `*.tfstate.*`, `*.tfplan`, `*.auto.tfvars`, `terraform.tfvars`, and Terraform's
  crash logs; the lock file is deliberately not ignored, and a test asserts both
  halves of that.
- **No planning material.** No requirement text, backlog item, sprint identifier
  beyond the story and PR identifiers this repository already publishes, or
  future-project content appears in the diff.
- **`git diff --check`** reports no whitespace error.

## What an independent review found, and what was done about it

The change was reviewed independently before it was pushed, against this
repository's own bar rather than a generic one. It found one HIGH and three
MEDIUM defects. All four were reproduced and all four are fixed; they are
recorded here rather than quietly corrected, because a review that finds nothing
and a review nobody reports are indistinguishable afterwards.

**HIGH — the ownership check could be defeated by one leading space.**
`RESOURCE_BLOCK` and `PROVIDER_BLOCK` were anchored at column 0. A resource block
indented by a single space — from a bad merge, a pasted example, or an editor —
was therefore invisible to every ownership rule in the suite, **including the
allowlist that the module's own docstring called the backstop**. A
`kubernetes_secret` or a `helm_release` written that way would have passed all 87
tests. The only check that would have caught it was `terraform fmt`, which skips
where the binary is absent, so the central acceptance criterion of this PR rested
on a tool that may not be installed.

Fixed by allowing leading horizontal whitespace in all three block patterns, and
by adding nine adversarial tests that feed each rule the shapes it exists to
refuse — a forbidden resource at four indents, a forbidden `provider` block at
two, and a forbidden `required_providers` entry at two — plus one that requires
the rules to still accept what the committed configuration legitimately declares,
so that tightening a pattern until it fires on everything cannot look like a
pass. Every rule above them passed over the committed files, which is also what a
rule that reads nothing at all does; these are what separates the two.

**MEDIUM — a malformed size threw a raw Terraform diagnostic beside the friendly
one.** The second `model_cache_size` validation called `regex()` without `can()`.
Terraform evaluates every validation block rather than stopping at the first
failure, so `model_cache_size = "abc"` produced the intended message *and* a
`Call to function "regex" failed` error. Reproduced with `terraform plan` against
the extracted variable; fixed by guarding the call, and re-checked: the same
input now produces the two validation messages and no function-call diagnostic.

**MEDIUM — the lock file covers six platforms and three documents said five.**
The committed lock carries six `h1:` hashes, the sixth being `windows_386`. This
record disclosed that; `docs/environment/platform-prerequisites.md` (three
places), `CONTRIBUTING.md`'s regeneration command, and the test inventory's
description had not been updated with it, so a contributor following CONTRIBUTING
literally would have produced a lock the document called complete and this
repository would not. All four corrected, and `REQUIRED_LOCK_PLATFORMS` raised
from a floor of five to six so the suite holds the number the documents publish.

**MEDIUM — three live files still said Terraform did not exist.** The change
updated the ownership document, the storage document, the lifecycle document, and
the lifecycle script, and missed
`tests/architecture/test_helm_chart.py`'s label docstring,
`charts/inferops-llm/templates/_helpers.tpl`, and `charts/inferops-llm/README.md`
— each of which stated that the prerequisite half is unwritten and that
`V1-S3-005` owns it. As of this commit that is false. All three now say the layer
exists, has never been applied, and that the sweep still does not exclude the
marker.

One review suggestion was **not** taken. It proposed making `terraform fmt` and
`terraform validate` fail rather than skip where the binary is absent. This
repository skips loudly for `helm`, `kubeconform`, and `shellcheck` on the same
reasoning — an absent tool is a fact about a machine — and making Terraform the
one exception would break the default lane for contributors who have no reason to
install it. The HIGH finding is closed by making the Python checks correct on
their own rather than by promoting the tool they were leaning on; the skip
remains, and it remains stated.

## Acceptance criteria

For this PR's boundary:

| Criterion | Status |
|---|---|
| Terraform owns only documented prerequisites | Met, and checked in both directions against the inventory |
| Helm workload resources are excluded | Met, by an allowlist and a denylist, and by refusing a `helm_release` and a second provider |
| Format/validate/security checks pass | Format and validate: met, with the exact commands above. Security: the configuration is checked for committed credentials, host paths, and state by tests; no external Terraform security scanner was run, because none is installed here and none is pinned by this repository |
| Apply/re-apply is explainable | **Explained and not demonstrated.** The document states what an apply, a re-apply, a namespace-name change, and a size change are expected to do and labels every row as derived from provider semantics. No apply has run |
| Cleanup/state handling are documented | Met. State location, contents, absence of a backend, recovery cost, and the blast-radius ordering are published, and the destroy path refuses without `--confirm` and refuses underneath an installed release |

For the parent story, `V1-S3-005`: the ownership and documentation criteria are
met by this PR. The criterion that the layer's apply and re-apply behaviour is
demonstrated is **not met and is not claimed**; it needs a local cluster and
belongs with the Kubernetes serving integration that first brings one up.

## What this does not establish

- **That this configuration applies.** Nothing has run it. A passing suite here
  says the files agree with the inventory and with each other.
- **That the claim binds, or holds anything.** Binding needs a pod; no pod has
  mounted it.
- **That a re-apply is a no-op.** It is expected to be. Expectation is not
  measurement.
- **That the prerequisite label protects anything.** It is set. The scoped sweep
  that must exclude it has not been written, and until then the label is a marker
  with nothing enforcing it.
- **Anything about the new script's behaviour.** `terraform-prerequisites.sh`
  has never been executed. It was parsed, and it was read by the safety suite as
  text. Both are checks on a file.
