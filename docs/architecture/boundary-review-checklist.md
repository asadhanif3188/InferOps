# Boundary review checklist

Status: **accepted review convention**, in
[ADR 0004](decisions/ADR-0004-component-and-ownership-boundaries.md), effective for
changes merged after it. It is the human half of the architecture boundary. The
mechanical half is five suites, not the one this line used to name:
`tests/architecture/test_resource_ownership.py` for the inventory and the document
beside it, `test_terraform_prerequisites.py` and `test_helm_chart.py` for each tool
against its half of the ownership split, `test_local_cluster_provider_contract.py`
for the provider boundary, and `test_decision_authority.py` for decision ownership
and sign-off authority.

Use it when a change touches components, ownership, deployment, telemetry, trust
boundaries, or scope. A change that touches none of those does not need it.

Answer every applicable question with **yes**, **no**, or **not applicable**. A
**no** is not automatically a blocker — it is a thing the pull request has to argue
for in writing rather than pass over.

## A. Ownership

- [ ] **A1.** Does every resource this change adds or moves appear in
      [`resource-ownership.v1alpha1.json`](resource-ownership.v1alpha1.json) with
      exactly one owner?
- [ ] **A2.** If it is a prerequisite, does it survive `helm uninstall`, and is that
      recorded rather than assumed?
- [ ] **A3.** If it is part of a release, is it absent from Terraform entirely — not
      merely absent from Terraform state today?
- [ ] **A4.** Does any command in this change invoke Helm with `--create-namespace`,
      or import a release object into Terraform state?
- [ ] **A5.** Does this change make one component write into a resource another owns?
      If so, is that handoff named in the owning resource's own row?
- [ ] **A6.** Does it adopt a derived object — a pod, replica set, endpoint slice, or
      provisioned volume — into a chart or into state?
- [ ] **A7.** Does it create, reconfigure, or delete a cluster, or write to the
      contributor's default kubeconfig?

## B. Component boundaries

- [ ] **B1.** Does the platform domain remain free of any Kubernetes client, Helm
      library, serving-runtime SDK, or HTTP framework?
- [ ] **B2.** Does an adapter leak a runtime-specific field, error, or vocabulary to
      a caller without namespacing it?
- [ ] **B3.** Is the set of places that know which adapter is live still exactly one?
- [ ] **B4.** Does anything other than deployment rendering write chart values?
      Deployment rendering is still unbuilt, so the honest answer today is that a
      values file is written by hand; what this question is for is catching a
      *second* writer appearing before the first one is built.
- [ ] **B5.** Does the API reach the serving runtime over the cluster network, rather
      than in-process or over a shared volume?

## C. Serving and evidence claims

- [ ] **C1.** Does any claim in this change rest on a mock, a document, or an
      estimate while reading as real-runtime proof?
- [ ] **C2.** Is every real-runtime claim backed by a record naming the image digest,
      the model revision and hash, the environment, the exact commands, and the
      results?
- [ ] **C3.** Does this change publish a throughput, latency, capacity, or benchmark
      figure? V1 may not. Since
      [ADR 0013](decisions/ADR-0013-bounded-local-performance-observations.md), a
      bounded figure from a declared, authorized local experiment may be, with its
      provider, host, model, runtime, profile, and evidence class named; a portable
      capacity, SLO, or benchmark figure still may not.
- [ ] **C4.** Is every new component, resource, or capability marked as implemented,
      planned, or deferred, with evidence cited only where it is implemented?
- [ ] **C5.** Does anything in a cluster write into `docs/proof/`?
- [ ] **C6.** If this change adds or moves a published claim, does the claim and
      evidence register carry the row, and does the generated proof dashboard agree
      with the register?
- [ ] **C7.** If this change adds a behaviour under failure, upgrade, or load, is it
      represented in the architecture's own flows rather than only in `tools/` and a
      proof record?

## D. Scope

- [ ] **D1.** Does this change put a choice between model providers, custody of a
      provider's credential, or a spend or request limit inside this project? That
      is gateway work and does not belong here.
- [ ] **D2.** Does it engineer the runtime's own behaviour — several models in one
      process, more throughput from one, traffic handed between versions, hardware
      allocated to demand? That is deeper serving work and does not belong here.
- [ ] **D3.** Does any V1 code path require a capability this project does not
      implement?
- [ ] **D4.** Does it publish a contract for a capability that does not exist yet?

## E. Trust boundaries and public safety

- [ ] **E1.** Does this change name a control that is not implemented without
      labelling it as unimplemented?
- [ ] **E2.** Does it place a prompt, a response, a correlation identifier, a tenant
      string, or any other high-cardinality or caller-supplied value into a metric
      label?
- [ ] **E3.** Does it template a secret value anywhere, or add a field a secret value
      could be written into?
- [ ] **E4.** Does it treat a tenant identifier supplied by a caller as an assertion
      rather than a request?
- [ ] **E5.** Does the diff contain a credential, a personal filesystem path, a host
      identifier, generated local state, a model artifact, or unpublished planning
      material?

## F. Decisions and ownership

- [ ] **F1.** If this change adds a decision record, does it have an entry in
      [`decision-authority.v1alpha1.json`](../governance/decision-authority.v1alpha1.json)
      naming a declared role, and does its own `Decision owner` row say the same?
- [ ] **F2.** If this change alters an accepted decision, does it use the repository's
      amendment or supersession mechanism rather than rewriting the historical text?
- [ ] **F3.** Does anything in this change describe an internal approval as an
      external review, or let a sign-off raise a certification level or an evidence
      class?

## What this checklist cannot do

It cannot tell whether a diagram is still accurate after code lands under it. That
limit is the reason this section used to end by saying the reconciliation of the
implemented architecture against these records was **due**. It was carried out on
2026-09-21, and it found what a checklist with no mechanical half for prose was
always going to let through: five statements in the system architecture that were
true when written and had since become false, a diagram box contradicting the
machine-checked inventory beside it, three committed artifacts acting with no
ownership row, two whole capability classes — failure and recovery, and the
claim-to-dashboard path — drawn nowhere, and fourteen decision records with no owner.

None of that was caught by a test, because none of it is the kind of thing these
tests read. The inventory suites compare data to data and data to a first table
column; a paragraph beside the table can drift freely, and
[the ownership document](resource-ownership.md) says so in its own words. Five
questions were added here — **C6**, **C7**, **F1**, **F2** and **F3** — to make the
classes that drifted reviewable, and one register, decision ownership, moved from
prose to a machine-checked file. **The diagram gap itself stays open by construction**: no
test reads an ASCII box, and a reviewer answering **C7** is the only thing standing
between a built capability and a diagram that does not mention it.
