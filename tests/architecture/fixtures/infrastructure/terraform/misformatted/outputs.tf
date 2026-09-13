output "namespace" {
  description = "The namespace a release installs into."
  value       = local.namespace
}

output "release_name" {
  description = "The release that installs into it."
  value       = local.release_name
}
