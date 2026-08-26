# V1-S0-009-PR1 change validation

Date: 2026-08-26

Classification: **local static evidence for the change itself.** Every result below
comes from reading and validating files in this repository and from running pytest
over them. No cluster was created, no model was downloaded, no runtime was started, no
request was served, **no secret scanner, image scanner, or dependency auditor was
run**, and **no assessment by an outside party was performed**. Nothing here is
evidence that this project is defended, and a document review is not a security
assessment.

Claim boundary: the committed security baseline is internally consistent under every
rule the suite states; every control's status is recomputed from the enforcement kind
and runtime scope it declares, through a table committed beside the controls; every
named test function and shell guard exists, and every cited evidence record is
committed under `docs/proof/`; every threat names a control or the deferred risk that
carries it, and the references agree in both directions; every YAML document under
`deploy/` is pinned by digest, carries eight pod-security assertions, and declares no
Ingress, NodePort, or LoadBalancer; the five boundaries the architecture maps are
reproduced verbatim and the sixth says why it extends them; a set of deliberate
corruptions of all of it are each refused; every relative link resolves; the existing
suites are unchanged in behaviour; and the published diff carries no private,
generated, or overclaimed content.

**What this record does not establish.** Nothing in this repository authenticates a
caller, authorises a request, enforces a network policy, or applies a security context
to a pod it deployed, because nothing here deploys a pod or serves a request. Ten of
the thirty-two controls have no verification at all. Twelve risks are carried rather
than reduced, ten of them blocking production use. The eight manifest assertions hold
over five YAML files that are smoke and trial apparatus, not over a serving path.
Four of the fifteen rules are enforced by review alone and are marked as such. No
scanner run is recorded, which is why the `security-scan` layer stays `planned` and
the claim it would support may not be cited.

## Environment

| Component | Version |
|---|---|
| Operating system | Microsoft Windows 11 Enterprise, `10.0.26200` |
| Python | `3.12.6` |
| `pytest` | `8.3.4` |
| `PyYAML` | `6.0.2` |
| `jsonschema` | `4.26.0` |
| `ruff` | `0.16.1` |
| `kubeconform` | `development` |
| Git | `2.45.1.windows.1` |
| GNU bash | `5.2.26(1)-release (x86_64-pc-msys)` |

`jsonschema` is listed because the full-suite run below includes the contract tests,
which need it. The security suite this change adds needs `pytest` and `PyYAML` alone:
`PyYAML` because the pod-security and exposure checks parse every manifest under
`deploy/` rather than matching text in them.

## Commands and results

### The security suite

```text
python -m pytest tests/security -q
509 passed
```

### The strategy suite, which this change adds a claim and a path to

```text
python -m pytest tests/testing -q
453 passed
```

### The full suite, to show nothing else moved

```text
python -m pytest -q
2206 passed, 7 skipped
```

The seven skips are the pre-existing ones: layers whose markers are deselected by
default because they need a cluster or a model. This change registers no new marker
and deselects nothing.

### Formatting and lint

```text
python -m ruff check tests tools conftest.py
All checks passed!

python -m ruff format --check tests/security tests/cost tests/telemetry tests/testing tests/contracts tests/architecture
7 files already formatted
```

### JSON well-formedness

```text
python -m json.tool docs/security/security-baseline.v1alpha1.json
python -m json.tool docs/testing/test-strategy.v1alpha1.json
(both parse; output discarded)
```

### Kubernetes manifests

No file under `deploy/` is modified by this change. The manifests were validated
anyway, because the security suite now asserts properties of them and a manifest that
does not validate is a poor thing to assert properties about:

```text
kubeconform -strict -summary -kubernetes-version 1.34.0 deploy/smoke/*.yaml
Summary: 5 resources found in 2 files - Valid: 5, Invalid: 0, Errors: 0, Skipped: 0
```

The kind cluster definition is excluded because its schema is kind's rather than
Kubernetes'.

### Whitespace

```text
git diff --check main...HEAD
(no output)

git ls-files -z '*.md' | xargs -0 grep -n '[[:blank:]]$'
(no matches)

git ls-files -z '*.md' | xargs -0 grep -n "$(printf '\t')"
(no matches)
```

### Links

The relative-link check from CONTRIBUTING, run over every tracked Markdown file:

```text
(no BROKEN lines)
```

Every relative link in the six new Markdown documents and the eight modified ones
resolves from the directory of the file containing it. No external link was added by this
change.

### Shell scripts

Not run, and not applicable: this change touches no file under `scripts/`. Two
existing shell functions are **named** by controls, and the suite confirms that
`scripts/environment/lib.sh` defines both; it does not execute either.

### Secret scan

`gitleaks` is not installed on this host and no run of it is recorded. That is the
whole content of `DR-11`, and this change does not alter it: the `security-scan` layer
remains `planned`, the claim
`no-credential-or-model-artifact-enters-public-history` remains `planned`, and a test
added here now fails if either is quietly promoted. What the suite does check is that
the configuration is committed and that every path its allowlist names exists — which
is a check on a configuration and explicitly not a scan result.

The diff was reviewed by hand instead, and what that review covered is in the section
below.

## What the suite establishes

### The derivation

Thirty-two controls. Each declares an enforcement kind (`automated-test`,
`script-guard`, `review`, or `none`) and a runtime scope (`repository-only`,
`host-scripts`, `trial-apparatus`, or `running-system`). The suite maps the kind to an
enforcement level through the committed vocabulary, looks the pair up in the committed
derivation table, and compares the result against the status the control declares:

| Enforcement level | Runtime scope | Derived status | Controls |
|---|---|---|---|
| automated | repository-only | `enforced-over-documents` | 10 |
| automated | trial-apparatus | `enforced-over-manifests` | 10 |
| automated | host-scripts | `enforced-on-the-host` | 2 |
| review | any | `review-enforced` | 3 |
| none, with a component named | — | `specified-only` | 3 |
| none, with no component named | — | `deferred` | 4 |

Alongside it: every `automated-test` control names a file that exists and a `def` the
file defines; every `script-guard` control names a shell function the script defines;
every control whose status the data marks as implementable names an evidence record
committed under `docs/proof/`, and one whose status is not implementable names none;
no control declares `running-system`, and the five counters in the `securityStatus`
block are all zero.

### The manifests

Six YAML files under `deploy/` parse into twelve documents, from which five pod
specifications, five containers, and six image references are extracted. The sixth
image is the kind node image, which lives under `nodes[].image` rather than in a pod
specification — the walk finds an `image` key at any depth, which is why it is covered
by the same assertion.

| Assertion | Where | Subjects checked |
|---|---|---|
| Image named by `@sha256:` and 64 hex digits | Every `image` key at any depth | 6 |
| `automountServiceAccountToken: false` | Every pod specification | 5 |
| `securityContext.runAsNonRoot: true` | Every pod specification | 5 |
| `securityContext.runAsUser` present | Every pod specification | 5 |
| `securityContext.seccompProfile.type: RuntimeDefault` | Every pod specification | 5 |
| `securityContext.allowPrivilegeEscalation: false` | Every container | 5 |
| `securityContext.readOnlyRootFilesystem: true` | Every container | 5 |
| `securityContext.capabilities.drop: ["ALL"]`, nothing added back | Every container | 5 |
| No `kind: Ingress`, no `type: NodePort`, no `type: LoadBalancer`, no `nodePort` | Every document | 12 |

All of this was already true before this change; every manifest here was written that
way. What the change adds is that it stops being a habit. **It establishes nothing
about a pod this platform deployed**, because it has deployed none: `EX-04` records
that and `DR-05` carries the gap.

### Agreement with what already existed

- The five boundaries the architecture maps are compared **verbatim** — both the
  `whatCrosses` and `enforcedToday` strings have to appear in
  `docs/architecture/system-architecture.md` — and the architecture's boundary table
  is parsed in the other direction so it cannot gain a boundary this baseline does not
  model.
- The two sensitivity classes the telemetry catalog gives an empty placement list are
  confirmed still empty, and every field the catalog forbids is confirmed to belong to
  one of them and to be named in this baseline.
- Every control and boundary owner is one of the seven evidence owners the test
  strategy declares.
- The new claim is confirmed to name only the documentation layer, to require `C0`,
  to be owned by security, and to cite a record that exists; the layer is confirmed to
  reach `C0` and to carry the `local-static` evidence class.
- The two planned security claims are confirmed still `planned` with no evidence
  record, so this change cannot be read as having certified either.

### Overclaiming

Twelve reserved terms, checked sentence by sentence over four security documents, the
decision record, and every prose string in the committed data — with fenced code
skipped, and with identifier, path, and symbol fields excluded because a reserved word
inside a test function name asserts nothing. A term in a sentence carrying no denial
fails the suite.

Also checked: no threat carries a likelihood, severity, or risk score; every deferred
risk states what may not be claimed, in a sentence that denies something; at least one
rule admits it is enforced by review alone; and no string anywhere in the baseline
matches a published credential prefix.

## Deliberate corruptions, each refused

Each corruption was applied to a file in this repository, the suite was run, and the
file was restored. A corruption the suite does not refuse would be a gap in the suite,
not a pass.

Eighty-eight corruptions were applied and **eighty-eight were refused**. Two of the
first eighty-five survived and both are recorded below rather than quietly fixed.

### The derivation — 10

A review-only control declaring an enforced status; a deferred control declaring an
enforced status; a manifest control relabelled as a document control; a host-script
control claiming the manifest status; a specification relabelled `deferred` while
still naming its component; a deferral claiming to be a specification without naming
one; a control declaring the `running-system` scope; the derivation table itself
rewritten to promote a review to an enforcement; `securityStatus` claiming three
controls enforced at runtime; and `securityStatus` claiming that something enforces at
runtime at all.

The eighth is the one worth calling out. A derivation whose table can be edited is a
derivation somebody can widen, and the suite refuses it because the vocabulary
declares which enforcement levels exist and the status a review may reach is fixed
against that vocabulary rather than read out of the table alone.

### A named verification that is not there — 10

A control naming a test function that does not exist; naming a test file that does not
exist; naming a shell guard the script does not define; a review-only control
smuggling in a symbol; a control citing an evidence record that is not committed;
citing evidence outside `docs/proof/`; an implemented control dropping its evidence
record entirely; a rule claiming a test this module does not define; a review-only
rule promoted to a test; and every review-only rule promoted at once, which is the
shape a tidy-up takes.

### Threats, controls, and risks that do not line up — 15

A threat naming a control, boundary, asset, or actor that does not exist; a threat
losing both its control and its deferred risk; a control naming a threat that does not
name it back; a control addressing no threat at all; a control or a boundary naming an
owner the test strategy does not declare; a deferred risk naming a threat that does
not exist; a deferred risk nothing points at; an exception naming a compensating
control that does not exist, an acceptance record that is not committed, or dropping
its residual-risk statement; and a document reference pointing at a file that is not
committed.

### Overclaiming — 13

The baseline calling the project secure; a limitation rewritten to claim a hardened
system; a control claiming the caller boundary is production-ready; a deferred risk
claiming images are audited; a threat's residual risk claiming compliance; a deferred
risk that stops saying what may not be claimed; a threat acquiring an invented
severity; the no-severity limitation removed; `securityStatus` claiming an assessment,
a scanner run, or a private reporting channel; the scan-configuration control dropping
its disclaimer; and a synthetic credential written into the baseline data.

### Boundaries drifting from the architecture — 5

A mapped boundary rewriting what crosses it; a mapped boundary claiming something is
enforced at it; the publication boundary dropping its explanation for extending the
architecture; the publication boundary claiming the architecture maps it; and a
boundary the architecture maps being dropped from the baseline entirely.

### Shape — 6

A control, a threat, and a deferred risk each losing a required field; two controls
sharing an identifier; a control identifier that stops being a slug; and a declared
control status becoming unused because every control carrying it was rewritten.

### The manifests — 11

The runtime image named by a tag instead of a digest; a pod that stops requiring a
non-root user, drops its seccomp profile, or mounts a service account token; a
container that allows privilege escalation, gets a writable root filesystem, keeps one
capability instead of dropping all, or adds a capability back after dropping all; a
service exposed as a NodePort; another exposed as a LoadBalancer; and the acquisition
job that stops comparing a computed hash against the published one.

### The publication boundary — 3

The project kubeconfig no longer ignored; a tool cache no longer ignored; and the
secret-scan allowlist naming a path that does not exist.

### Documents against data — 8

The control matrix losing a control the data declares; the threat model losing a
threat; the register losing a risk; the register keeping an exception's summary row
while deleting the section that argues it; a security document calling the project
hardened; the threat model claiming a penetration test; the decision record losing a
required section; and `SECURITY.md` quietly publishing a reporting channel that does
not exist.

### The test strategy — 6

The documentation layer no longer collecting this suite; the layer no longer running
its command; the baseline claim promoted above what its layer can reach, reassigned to
a layer that is not implemented, stripped of its evidence record, or given a different
owner; and a planned security claim marked certified.

### The architecture — 1

The architecture's own boundary table rewritten so that it no longer says what the
baseline says it says.

## What a second review found

The first pass produced eighty-five corruptions, of which **two survived**. Both are
worth recording because they are different kinds of finding.

**One was a real gap in the suite.** The register's exception check asserted only that
each exception identifier appeared *somewhere* in the document. Deleting the section
that argues `EX-03` — its residual risk, its compensating control, and when it should
be revisited — left the summary row intact and the suite passed. That is precisely the
failure this whole record is built to prevent: an index entry surviving while the
argument behind it is deleted reads as handled and is not. The check now requires both
the table row and a section heading, and two corruptions cover it.

**One was a broken corruption rather than a surviving defect.** The mutation that was
supposed to promote the baseline claim to `C2` inserted a duplicate JSON key ahead of
the real one, and the later key won, so the file was never actually changed. A
corruption that does not corrupt anything proves nothing, and counting it as a pass
would have been the more comfortable reading. It was rewritten to parse the strategy
data and edit the value, and four further strategy corruptions were added alongside
it — reassigning the claim to a layer that is not implemented, stripping its evidence
record, changing its owner, and removing the suite's command from the layer. All five
are refused.

The corruption count is therefore eighty-eight rather than the eighty-five of the
first pass, and one test is stricter than it was.

## What the diff was reviewed for

| Checked for | Result |
|---|---|
| Credentials, tokens, keys | None. No credential appears in any new file, and a test now refuses a published credential prefix anywhere in the baseline data |
| Private planning content, prompts, or unpublished strategy | None. No planning document is quoted, summarised, or referenced, and no sprint, backlog, or roadmap vocabulary appears |
| Personal filesystem paths, hostnames, usernames | None. Every path in the diff is repository-relative, and a test now checks every file in the working tree for a personal path |
| Generated files or host state | None. Cache directories remain ignored, and a test now refuses a committed file under any of them |
| Model artifacts | None, and a test now refuses a file with a model artifact extension |
| Real vulnerabilities, incidents, or exploit detail | None. Every abuse case is built out of this project's own assets, and no real credential, customer, prompt, host, or incident appears as an illustration |
| A capability claim not supported by evidence | None found. Every document states that nothing here defends a running system, and ten controls are published as having no verification at all |
| Scope beyond this pull request | None. No component, chart, policy object, scanner configuration, or admission rule is added |

Nine additions deserve naming explicitly because they touch files this change does
not own:

- `docs/testing/test-strategy.v1alpha1.json` gains one path and one command on the
  existing documentation layer, and one claim row. No layer, lane, marker, evidence
  class, or certification level changes, and no existing claim's status moves.
- `docs/testing/claim-test-matrix.md` gains the row that goes with it and two
  paragraphs describing its scope, plus a corrected count in its opening line.
- `docs/architecture/system-architecture.md` has three owner cells that pointed at
  "the security baseline decision" and now point at ADR 0008, a warning that now names
  the record that was made, one paragraph noting where the tenant rule now lives, and
  one row in its related-records table. **No boundary changes what crosses it or what
  is enforced at it** — a test would refuse that, because it compares the two
  documents verbatim.
- `docs/architecture/README.md` gains the ADR 0008 row, a paragraph describing it, an
  entry in the architecture-documents table, and two corrected counts.
- `docs/proof/README.md` gains one record row.
- `README.md` gains two entry-point rows and has three status cells corrected.
- `SECURITY.md` gains a table linking the three new documents and a paragraph stating
  what they do not establish. **Its reporting section is unchanged**: no private
  channel is published, and a test now fails if that sentence is quietly removed.
- `CONTRIBUTING.md` gains a section describing the suite and what a change to it must
  do, and one sentence added to the existing digest-pinning rule noting that a test now
  checks it.
- `CHANGELOG.md` gains ten entries under Unreleased.

No file under `deploy/`, `scripts/`, `contracts/`, or `tools/` is modified. The
manifests are read by the new suite and not changed by it, which is deliberate: a
change that both asserts a property and edits the thing it asserts it about proves
less than it appears to.

## Limitations

- **Nothing runs.** No control here has ever acted inside a system serving a request.
  The check that would matter — that a control holds under load, under failure, or
  against an adversary — needs components that do not exist.
- **No scanner was run.** `gitleaks` is not installed on this host, no image scanner
  or dependency auditor is configured, and a committed configuration file is not a
  result.
- **No assessment was performed.** Nobody outside this project has looked at any of
  it, and reading a document is not the same activity.
- **The manifests are apparatus.** Every file the pod-security assertions act on is
  smoke or trial apparatus. None is a V1 serving path.
- **One host, one trial.** The runtime observations behind `B1` and `B4` come from one
  trial, on one Windows host, on one day. Nothing has been reproduced on a second
  machine or a second operating system.
- **The derivation checks existence, not quality.** It confirms that a named test
  function exists and that a status matches its enforcement kind. It cannot tell a
  strong test from a weak one, and a control pointing at a weak test satisfies it
  exactly as well as one pointing at a strong test.
- **The threat set is not exhaustive.** Twenty-two threats were enumerated because
  each is a failure somebody would plausibly reach. A threat nobody thought of is a
  threat nobody modelled.
- **The corruption set is not exhaustive either.** Each corruption represents a
  mistake somebody would plausibly make; a corruption nobody thought of is a
  corruption that was not tested.
- **The reserved-term check is narrow.** It catches a listed word in six documents. A
  claim made in a word nobody listed, or made in a slide, survives it untouched.
- **Four rules are enforced by review alone**, and a review is enforced only when the
  reviewer remembers it.
- **There is nowhere to report a problem privately.** A reader who finds a real gap in
  any of this has no confidential channel to use, which is recorded in `SECURITY.md`
  and is the reason everything here is published rather than held.
