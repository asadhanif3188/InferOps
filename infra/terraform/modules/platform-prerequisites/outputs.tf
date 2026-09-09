# What a caller needs in order to install a release into what this module made,
# and nothing a caller could use to reach past the boundary.

# Pass this to a release's `--namespace`. The flag that would let the release
# create the namespace instead is refused as code throughout this configuration.
output "namespace" {
  description = "The platform namespace a release installs into and must not create."
  value       = kubernetes_namespace_v1.platform.metadata[0].name
}

output "model_cache_claim_name" {
  description = "The claim the chart mounts as `model.cache.claimName`. This module creates it; the chart must not."
  value       = kubernetes_persistent_volume_claim_v1.model_cache.metadata[0].name
}

output "model_cache_size" {
  description = "The requested size of the model cache claim. Reclaimed by `terraform destroy`, or by deleting the cluster."
  value       = var.model_cache_size
}

output "prerequisite_label_selector" {
  description = <<-EOT
    The selector that identifies a prerequisite. A scoped teardown must exclude
    it: every object in this project carries `app.kubernetes.io/part-of=inferops`,
    so a sweep matching only that label would delete what this module owns.
  EOT
  value       = "inferops.io/lifecycle=prerequisite"
}
