# Ownership-overlap fixtures

Each file or directory here reaches across the boundary
[the ownership inventory](../../../../docs/architecture/resource-ownership.md) draws
between Helm and Terraform, in exactly one way. They are read by
[`tools/ci_gates/ownership_overlap.py`](../../../../tools/ci_gates/ownership_overlap.py),
which must refuse every one of them and must accept the committed chart renders with
the committed Terraform configuration.

## `release-renders/`

Renders the chart must never produce, each checked against the committed
configuration:

- a `Namespace` — the state `helm install --create-namespace` produces without any
  template saying so;
- the model cache `PersistentVolumeClaim`, which `helm uninstall` would delete with the
  weights inside it;
- a `ResourceQuota`, whose inventory row is deferred and still belongs to Terraform;
- a `ReplicaSet`, which the control plane derives and a release must not adopt.

## `terraform-declares/`

Configurations Terraform must never hold, each checked against the committed real
render. They are **read as text and never initialised**: a `kubernetes_deployment_v1`,
whose kind the inventory gives to Helm, and a `helm_release`, which is not a
Kubernetes kind the inventory can place and is a release two tools would reconcile. The
Deployment block is indented on purpose — the first resource pattern in the Terraform
suite could not see an indented block, and this keeps the new one honest.

The check compares kinds, not names, because the inventory assigns kinds.
