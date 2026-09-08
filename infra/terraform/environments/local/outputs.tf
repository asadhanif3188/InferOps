output "namespace" {
  description = "The platform namespace a release installs into."
  value       = module.platform_prerequisites.namespace
}

output "model_cache_claim_name" {
  description = "The claim a release mounts and never creates."
  value       = module.platform_prerequisites.model_cache_claim_name
}

output "model_cache_size" {
  description = "The requested size of the model cache claim."
  value       = module.platform_prerequisites.model_cache_size
}

output "prerequisite_label_selector" {
  description = "The selector a scoped teardown must exclude."
  value       = module.platform_prerequisites.prerequisite_label_selector
}
