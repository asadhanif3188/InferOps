# Refused: Terraform declares a Deployment, and the inventory gives Deployments
# to Helm. Read as text with the committed real render; never initialised.
resource "kubernetes_namespace_v1" "platform" {
  metadata {
    name = "inferops-platform"
  }
}

  resource "kubernetes_deployment_v1" "api" {
  metadata {
    name      = "inferops-inferops-llm-api"
    namespace = "inferops-platform"
  }
}
