# Every input this module takes, and the refusal attached to each one.
#
# The validations here are name checks. They can tell that a namespace is not
# the smoke namespace and that a claim is large enough for the pinned artifact.
# They cannot tell which cluster the provider is pointed at -- that is
# `scripts/environment/terraform-prerequisites.sh`, which establishes cluster
# identity from the container labels before it lets Terraform run at all.

# The platform namespace. Terraform creates it and Helm installs into it. The
# flag that would let Helm create it too is named in the environment scripts, in
# CONTRIBUTING, and in the ownership document, and is deliberately not written
# anywhere in this configuration: an architecture suite refuses it as code here.
variable "namespace" {
  description = <<-EOT
    The platform namespace. Terraform creates it; a release installs into it and
    must never be allowed to create it.
  EOT
  type        = string
  default     = "inferops-release"

  validation {
    condition     = can(regex("^inferops-[a-z0-9]([-a-z0-9]*[a-z0-9])?$", var.namespace))
    error_message = "The namespace must be a DNS-1123 label prefixed 'inferops-'. ADR 0001 (D5) makes that prefix the isolation rule: a scoped teardown finds this project's objects by it."
  }

  validation {
    condition     = length(var.namespace) <= 63
    error_message = "A namespace is a DNS-1123 label and cannot exceed 63 characters."
  }

  validation {
    condition     = var.namespace != "inferops-smoke"
    error_message = "'inferops-smoke' belongs to scripts/environment/cluster-down.sh, which deletes it outright. ADR 0004 requires the platform namespace to be distinct from it, because a prerequisite inside a namespace another tool deletes has two destroyers."
  }
}

variable "model_cache_claim_name" {
  description = <<-EOT
    The PersistentVolumeClaim that holds model weights. Terraform provisions it
    empty; a Helm-owned job fills it; the serving Deployment mounts it read-only.
    It must be the name the chart's values file mounts.
  EOT
  type        = string
  default     = "inferops-model-cache"

  validation {
    condition     = can(regex("^[a-z0-9]([-a-z0-9]*[a-z0-9])?$", var.model_cache_claim_name))
    error_message = "The claim name must be a DNS-1123 label."
  }
}

variable "model_cache_size" {
  description = <<-EOT
    How large the model cache claim is requested. The pinned artifact is
    1,834,426,016 bytes -- about 1.71 GiB -- and the layout inside the claim is
    keyed by revision, so a second pinned revision lands beside the first rather
    than replacing it. The default holds two of them with room to spare.

    This is the figure `terraform destroy` reclaims without destroying the
    cluster; deleting the cluster reclaims it too.
  EOT
  type        = string
  default     = "4Gi"

  validation {
    condition     = can(regex("^[1-9][0-9]*Gi$", var.model_cache_size))
    error_message = "The size must be a whole number of gibibytes written as, for example, '4Gi'. Kubernetes memory and storage quantities are binary: 4Gi is four gibibytes and never four gigabytes."
  }

  # The `can()` is not decoration. Terraform evaluates every validation block,
  # not only the ones before the first failure, so an unguarded `regex()` here
  # threw a raw "Call to function regex failed" diagnostic alongside the friendly
  # message from the rule above whenever the value was malformed. A guard that
  # explains itself and a stack trace beside it is worse than the guard alone.
  validation {
    condition = (
      can(regex("^[1-9][0-9]*Gi$", var.model_cache_size)) &&
      tonumber(regex("^([1-9][0-9]*)Gi$", var.model_cache_size)[0]) >= 4
    )
    error_message = "The pinned model artifact is 1,834,426,016 bytes and the acquisition hook stages a replacement beside it, renaming it over the top only once it verifies -- so a claim has to hold two copies transiently and one below 4Gi cannot. The floor was 2Gi while the hook deleted the old artifact first; V1-S3-011-PR2 stopped it doing that, because a failed acquisition then left the claim empty."
  }
}

variable "storage_class_name" {
  description = <<-EOT
    The storage class the claim asks for, or null to take the cluster default.

    Null is the default on purpose. The accepted local cluster ships exactly one
    provisioner and naming it here would make this configuration specific to a
    distribution the ownership boundary says Terraform does not own.
  EOT
  type        = string
  default     = null
}

variable "wait_until_bound" {
  description = <<-EOT
    Whether `terraform apply` blocks until the claim is bound.

    False, and it has to be. The local provisioner binds a claim on first
    consumer, so a claim nothing mounts stays `Pending` by design; waiting for it
    would hang an apply until the timeout and report a correctly-provisioned
    prerequisite as a failure. The claim binds when the release that mounts it is
    installed, and `bound-persistent-volume` is owned by a controller rather than
    by this configuration.
  EOT
  type        = bool
  default     = false
}
