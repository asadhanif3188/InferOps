# Refused: a helm_release is not a Kubernetes kind the inventory can place, and a
# Terraform-managed release is a release two tools reconcile. Read as text only.
resource "kubernetes_namespace_v1" "platform" {
  metadata {
    name = "inferops-platform"
  }
}

resource "helm_release" "inferops" {
  name  = "inferops"
  chart = "charts/inferops-llm"
}
