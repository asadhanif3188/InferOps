# The platform prerequisites: everything that outlives a release, and nothing
# else.
#
# Two resources and their metadata. The ownership inventory
# (docs/architecture/resource-ownership.v1alpha1.json) lists four rows against
# `terraform`; the fourth, `platform-resource-quota`, is deferred out of V1 and
# is deliberately absent here rather than added because it was easy. A row is
# named there so that if a quota is ever wanted it lands on this side of the
# boundary instead of inside a chart, which is where a quota is usually put by
# accident.
#
# What this module may not contain, ever:
#
#   * a Namespace anything else also creates -- Helm is never invoked with
#     `--create-namespace`, and that is checked by two suites;
#   * any object a release installs. Terraform never imports or adopts one: a
#     resource in both state and a chart is reconciled by both, and the loser is
#     whichever ran last;
#   * a cluster. Neither tool creates, reconfigures, or deletes one;
#   * a derived object -- a Pod, a ReplicaSet, an EndpointSlice, a bound
#     PersistentVolume. A controller keeps rewriting those, so adopting one is
#     taking ownership of something that will not hold still.

locals {
  # The label set is fixed rather than configurable, because it is the boundary
  # marker itself. `inferops.io/lifecycle: prerequisite` is what a scoped
  # teardown has to exclude: every object this project creates carries
  # `app.kubernetes.io/part-of: inferops`, so a sweep matching only that label
  # would delete these two and give one resource two destroyers.
  common_labels = {
    "app.kubernetes.io/part-of"    = "inferops"
    "app.kubernetes.io/managed-by" = "Terraform"
    "inferops.io/lifecycle"        = "prerequisite"
  }
}

# `platform-namespace` and `namespace-metadata` in the ownership inventory. They
# are one Kubernetes object and two inventory rows on purpose: the namespace is
# the container a release installs into, and its metadata is the marker that
# keeps a sweep away from it. Per-object metadata inside a release is Helm's.
resource "kubernetes_namespace_v1" "platform" {
  metadata {
    name = var.namespace

    labels = merge(local.common_labels, {
      "app.kubernetes.io/component" = "platform-namespace"
    })

    annotations = {
      # Read by a human during an incident, and by nothing else. It answers the
      # question a stray namespace always raises -- who made this, and what
      # removes it -- without requiring the reader to find this file first.
      "inferops.io/managed-by-configuration" = "infra/terraform/environments/local"
      "inferops.io/removed-by"               = "terraform destroy"
    }
  }
}

# `model-cache-volume-claim`. Terraform provisions it empty and never writes to
# it; a Helm-owned job fills it; the serving Deployment mounts it read-only at a
# revision-scoped subdirectory. Writing content is not owning the container, and
# that single sanctioned handoff is the reason this claim is here rather than in
# the chart: `helm uninstall` would otherwise destroy roughly 1.71 GiB whose
# transport this project has recorded as unauthenticated, and the next install
# would repeat the transfer and the exposure with it.
resource "kubernetes_persistent_volume_claim_v1" "model_cache" {
  # `false` by design, and the reason is in the variable's own description: the
  # accepted local provisioner binds on first consumer, so a claim nothing mounts
  # is `Pending` until a release arrives. Waiting here would turn a correct
  # prerequisite into an apply that hangs and then reports failure.
  wait_until_bound = var.wait_until_bound

  metadata {
    name      = var.model_cache_claim_name
    namespace = kubernetes_namespace_v1.platform.metadata[0].name

    labels = merge(local.common_labels, {
      "app.kubernetes.io/component" = "model-cache-volume-claim"
    })

    annotations = {
      "inferops.io/managed-by-configuration" = "infra/terraform/environments/local"
      "inferops.io/removed-by"               = "terraform destroy"
      # The one operating cost worth putting where an operator will find it: the
      # weights survive `helm uninstall` on purpose, and only `terraform destroy`
      # gives the space back.
      "inferops.io/retention" = "Holds model weights across helm uninstall. Reclaimed by terraform destroy, or by deleting the cluster this claim is stored inside."
    }
  }

  spec {
    # One node, one writer. The accepted local cluster is single-node and the
    # writer is a single Job; ReadWriteMany would claim a capability the local
    # provisioner does not have.
    access_modes = ["ReadWriteOnce"]

    # Null takes the cluster's default class. Naming one here would tie the
    # prerequisite layer to a distribution it does not own.
    storage_class_name = var.storage_class_name

    resources {
      requests = {
        storage = var.model_cache_size
      }
    }
  }
}
