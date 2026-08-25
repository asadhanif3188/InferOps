# Boundary review checklist

Status: **accepted review convention**, in
[ADR 0004](decisions/ADR-0004-component-and-ownership-boundaries.md), effective for
changes merged after it. It is the human half of the architecture boundary; the
mechanical half is `tests/architecture/test_resource_ownership.py`.

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
- [ ] **B5.** Does the API reach the serving runtime over the cluster network, rather
      than in-process or over a shared volume?

## C. Serving and evidence claims

- [ ] **C1.** Does any claim in this change rest on a mock, a document, or an
      estimate while reading as real-runtime proof?
- [ ] **C2.** Is every real-runtime claim backed by a record naming the image digest,
      the model revision and hash, the environment, the exact commands, and the
      results?
- [ ] **C3.** Does this change publish a throughput, latency, capacity, or benchmark
      figure? V1 may not.
- [ ] **C4.** Is every new component, resource, or capability marked as implemented,
      planned, or deferred, with evidence cited only where it is implemented?
- [ ] **C5.** Does anything in a cluster write into `docs/proof/`?

## D. Scope

- [ ] **D1.** Does this change route between model providers, hold provider
      credentials, issue keys, or enforce budgets or rate limits? That is gateway
      work and does not belong here.
- [ ] **D2.** Does it add multi-model serving, batching, autoscaling on
      inference-specific signals, or accelerator capacity work? That is deeper
      serving work and does not belong here.
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

## What this checklist cannot do

It cannot tell whether the ownership inventory describes the Terraform and Helm that
eventually get written, because neither exists. It cannot tell whether a diagram is
still accurate after code lands under it. Both gaps close by reconciling the
implemented architecture against these records once there is an implementation, and
until then they are open by construction rather than by oversight.
