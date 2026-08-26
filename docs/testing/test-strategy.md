# The V1 test and CI strategy

Status: **accepted strategy**, in
[ADR 0005](../architecture/decisions/ADR-0005-test-ci-and-certification-strategy.md),
effective for changes merged after this document is merged. It configures pytest and
publishes a machine-checked strategy. It does **not** configure a
continuous-integration service: there is no workflow file in this repository, and
nothing here claims one runs.

It exists because a test suite acquires its meaning from what it is allowed to
certify, and that is a decision, not a consequence. Left undecided, the decision
still gets made — by whichever suite happens to be cheap enough to run on every
change. That suite will be the mock one, and the project will end up certifying real
serving with a fake. This document decides it instead: eleven test layers, four
lanes, a ceiling on what each layer's evidence can support, and a marker expression
that makes the ceiling hold when nobody is watching.

The companion documents are
[the certification levels](certification.md), which say what C0, C1, and C2 mean and
why a mock stops at C1, and [the claim/test matrix](claim-test-matrix.md), which
lists every public claim with the layer, environment, and owner behind it. The
authoritative form of all three is
[`test-strategy.v1alpha1.json`](test-strategy.v1alpha1.json), which
[`tests/testing/`](../../tests/testing/) checks.

## The one rule the rest of this follows

**The lane every change goes through downloads no model, touches no cluster, and
needs nobody's authorization. Everything that does is opt-in, labelled, and unable
to run by accident.**

Everything below is either a consequence of that rule or a mechanism for enforcing
it.

## Lanes

A lane is a place tests run. It fixes the environment, the cost, and what the result
is allowed to mean.

| Lane | Trigger | Environment | Model | Cluster | Timeout | Artifacts kept |
|---|---|---|---|---|---|---|
| `default-checks` | every change, before review | a checkout and an interpreter | none | no | 15 min | 30 days |
| `cluster-smoke` | opt-in, on environment or manifest changes | local kind cluster | none | yes | 30 min | 30 days |
| `real-runtime` | manual, or a labelled authorized runner | capable host | full, hash-verified | yes | 90 min | 90 days |
| `capacity` | not triggered in V1 | capable host | full | yes | 240 min | 90 days |

None of these is automated. Every one is `manual` today except `capacity`, which is
`deferred`. A lane may only be marked automated once it names a workflow file that
exists, and a test enforces that — which is the mechanism that keeps this table
honest as CI arrives.

### Why four rather than two

Two lanes — cheap and expensive — is the obvious split and it is wrong in one
specific way. `cluster-smoke` needs a real Kubernetes cluster and no model at all;
`real-runtime` needs several gigabytes of weights and the disk to hold them. Folding
them together means either paying the model cost to test a cluster, or letting a
model-free cluster test sit in a lane that is nominally allowed to serve. The first
is waste; the second is the beginning of the failure this whole document is about.

`capacity` is separate for a different reason. It is not more expensive than
`real-runtime` by much. It is separate because V1 may publish nothing it produces,
and a lane whose output is unpublishable should be visibly walled off rather than
mixed into one that produces evidence.

### Prerequisites, diagnostics, and what a failure has to say

Each lane declares its prerequisites, its artifacts, and what a failure must report;
the authoritative list is in the strategy data. Two of those deserve to be stated
here because they were learned rather than assumed.

`real-runtime` must measure disk headroom on the real backing volume rather than
trusting what `df` reports inside the cluster. A trial on one host saw hundreds of
gigabytes reported free on a sparse virtual disk whose real backing volume had a
small fraction of that.

`real-runtime` must also record the readiness endpoint's status *over time* on a
model-load failure, not a single sample. The selected runtime answers 503 while
loading. That is correct readiness behaviour and wrong liveness behaviour, and a
single sample cannot distinguish "still loading" from "broken" — which is exactly
the confusion that restarts a pod mid-load forever.

## Layers

A layer is a kind of test. It fixes what the test exercises and, through its evidence
class, the strongest thing its result may be used to say.

| Layer | Lane | Marker | Evidence class | Ceiling | Status |
|---|---|---|---|---|---|
| `unit` | `default-checks` | `unit` | local-static | C0 | planned |
| `contract-and-schema` | `default-checks` | `contract` | local-static | C0 | implemented |
| `architecture-inventory` | `default-checks` | `architecture` | local-static | C0 | implemented |
| `documentation` | `default-checks` | `docs` | local-static | C0 | implemented |
| `security-scan` | `default-checks` | none | local-static | C0 | planned |
| `adapter` | `default-checks` | `adapter` | mock | C1 | planned |
| `mock-integration` | `default-checks` | `mockintegration` | mock | C1 | planned |
| `kubernetes-smoke` | `cluster-smoke` | `cluster` | local-real-cpu | C2 | implemented |
| `real-runtime-smoke` | `real-runtime` | `realruntime` | local-real-cpu | C2 | implemented |
| `failure-and-resilience` | `real-runtime` | `failure` | local-real-cpu | C2 | planned |
| `capacity-and-load` | `capacity` | `load` | local-real-cpu | C2 | deferred |

Read the ceiling column as a limit, not a target. A layer whose ceiling is C1 cannot
support a C2 claim no matter how thorough it is, and
[the certification document](certification.md) argues why that is a property of what
the layer runs against rather than of how well it is written.

Five of eleven layers exist. Registering the other six now is deliberate: a marker
that exists is a marker the first test of that kind gets written under, and a marker
that does not exist is a test that ends up in whichever suite was already open.

### What each layer is for

`unit` exercises one domain rule with no adapter, no cluster, and no runtime. The
architecture's dependency rule — nothing in the platform domain imports a Kubernetes
client, a Helm library, a runtime SDK, or an HTTP framework — exists so that this
layer is possible. A domain that cannot be tested without a runtime will be tested
with a mock, and then somebody will call that certification.

`contract-and-schema` validates the published schema, every valid and invalid
fixture, and the exact refusal each rule produces. It runs today.

`architecture-inventory` holds the committed ownership boundary to its own rules. It
runs today.

`documentation` checks that every relative link resolves, that no published file
carries trailing whitespace or a hard tab, and that the machine-readable strategy and
the documents describing it publish the same identifiers. It covers three directories —
[`tests/testing/`](../../tests/testing/) for this strategy,
[`tests/telemetry/`](../../tests/telemetry/) for
[the telemetry catalog](../telemetry/telemetry-catalog.md), and
[`tests/cost/`](../../tests/cost/) for
[the cost method](../cost/cost-method.md) — because each is committed data
checked against the documents that describe it. Its pytest half runs
today; its link and whitespace half is the shell check in
[CONTRIBUTING](../../CONTRIBUTING.md).

`security-scan` refuses a change carrying a credential, a model artifact, generated
host state, or a personal path into public history. A scan configuration and an
allowlist are committed. **No recorded run of the scanner exists**, so the layer is
`planned`, not `implemented`. A configuration file is not a result, and the strategy
data is not permitted to say otherwise.

`adapter` proves each adapter implements the interface the domain owns, including the
mock adapter's obligation to identify itself as a mock. Its ceiling is C1 even for the
real adapter, because what it exercises is the shape of the call rather than the thing
on the other end of it.

`mock-integration` runs the API end to end against the mock adapter: correlation
propagation, canonical errors, redaction, the not-ready path. This is the layer most
at risk of being read as more than it is.

`kubernetes-smoke` proves the cluster half of the environment — created, workload
answering, torn down with residue verified absent. Real, and about the environment
only. A cluster smoke result may never be cited in support of a serving claim.

`real-runtime-smoke` is the only layer that may support a C2 serving claim. It has
run once, on one host, on one day, and its record says which of its own thresholds it
failed.

`failure-and-resilience` provokes the failures the architecture names as canonical
errors — model not ready, runtime unreachable, timeout — against the real runtime
rather than against an anticipated mock. Full C3 certification is out of V1 scope;
what V1 needs is that each canonical error is produced by the condition it names.

`capacity-and-load` is defined and deferred. V1 may publish no throughput, latency,
capacity, or benchmark figure, so this layer exists in order that adding one is a
visible decision rather than an accident.

## Markers, and how the rule is enforced

[`pytest.ini`](../../pytest.ini) registers every marker a layer declares, turns on
`--strict-markers` so an unregistered one is an error rather than a typo, and sets a
default marker expression:

```text
-m "not cluster and not realruntime and not failure and not load"
```

That expression is the enforcement. A test needing a cluster or a model cannot run in
the default lane by accident; it runs only when somebody names its marker on the
command line. Selecting one lane is then just a marker expression:

```sh
python -m pytest -q                    # the default lane
python -m pytest -m contract -q        # one layer inside it
python -m pytest -m realruntime -q     # opt in, on a capable host, deliberately
```

Three checks in `tests/testing/` keep the configuration and the strategy from
disagreeing:

1. the registered markers and the markers the layers declare are the same set, in
   both directions;
2. every marker belonging to a layer **outside** the default lane appears in the
   default exclusion, and no marker belonging to a layer **inside** it appears there
   at all;
3. every test module under a layer's declared paths carries that layer's marker at
   module level — because a marker nothing is marked with selects nothing, silently.

The third is the one that catches the realistic mistake. The first two can pass while
`pytest -m contract` collects zero tests.

`pytest.ini` rather than `pyproject.toml` is deliberate. A `pyproject.toml` would
quietly settle the packaging and dependency questions that
[ADR 0001](../architecture/decisions/ADR-0001-local-development-environment.md) and
[ADR 0003](../architecture/decisions/ADR-0003-workload-contract-schema-tooling.md)
both leave open. This file configures pytest and nothing else.

## Evidence and retention

Two kinds of output, two lifetimes, and the distinction matters more than the
durations:

**A lane's raw output expires.** It exists to diagnose a failure. It is kept for the
period the lane declares — 30 days for the cheap lanes, 90 for the expensive ones —
and then it is gone. **Nothing may cite an expiring artifact as the evidence for a
published claim.** An artifact store that expires cannot support a claim that does
not.

**A certifying record does not expire.** A record that certifies a public claim is
committed under [`docs/proof/`](../proof/) and retained in the repository's history
for as long as the claim stands. Raw output a claim depends on is promoted into such
a record before the lane's retention window closes, with prompts, completions,
credentials, and host identifiers removed.

A claim whose evidence was never promoted is uncertified, and the correct response is
to rerun the lane — not to describe what the expired artifact used to say. A
superseded record is kept and marked rather than deleted, so a reader arriving from
an old link finds the correction rather than a missing file.

Two rules in the strategy data enforce the boundary mechanically: a claim may cite a
record only when it is certified, and a certified claim may rest only on layers that
are actually implemented. The second is the one that stops a claim being marked
certified on the strength of a layer nobody has written.

## What this strategy does not do

- **It configures no continuous integration.** There is no workflow file, no runner,
  and no automated lane. Every lane is run by hand today. The strategy is written so
  that adding CI is a matter of pointing a workflow at a marker expression that
  already exists.
- **It does not certify anything by existing.** Six of eleven layers have no code.
  The suite that checks this document cannot tell an honestly planned layer from one
  that will never be written.
- **It does not select a task runner, a packaging tool, or a linter.** Those remain
  open where the records that own them left them open.
- **It labels no runner as capable.** The `real-runtime` lane's only reproducible
  path today is
  [the manual feasibility workflow](../serving/feasibility-workflow.md), which has
  been executed once.

## Related records

- [ADR 0005](../architecture/decisions/ADR-0005-test-ci-and-certification-strategy.md)
  — the decision, its alternatives, and its consequences.
- [The certification levels](certification.md) — what C0 to C2 mean, and why a mock
  stops at C1.
- [The claim/test matrix](claim-test-matrix.md) — every public claim, with its layer,
  environment, and owner.
- [The mock and real serving boundary](../serving/mock-and-real-boundary.md) — the
  accepted rule this strategy makes mechanical.
- [Project boundaries](../architecture/project-boundaries.md) — the rule that defers
  `capacity-and-load` out of V1.
- [CONTRIBUTING](../../CONTRIBUTING.md) — the checks a contributor runs, and the
  evidence vocabulary.
