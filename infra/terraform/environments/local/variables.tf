variable "kubeconfig_path" {
  description = <<-EOT
    The project kubeconfig, written by `scripts/environment/cluster-up.sh`. It
    holds a client certificate and key, it is git-ignored, and cluster teardown
    removes it.

    The default is relative to this directory so that a checkout anywhere works
    and no contributor's absolute path is ever committed.
  EOT
  type        = string
  default     = "../../../../.kube/inferops-dev.config"
}

variable "kube_context" {
  description = <<-EOT
    The kubeconfig context to act through.

    The validation below is a name check and nothing more: it refuses a context
    that does not match one of the two providers ADR 0011 supports, which stops
    the common accident of an apply following a context left selected from other
    work. It cannot establish that the cluster on the other end is really the
    selected provider's -- a context can be named anything. That check is the
    provider-aware target verification in `scripts/environment/lib.sh`
    (`inferops::resolve_target`), run by
    `scripts/environment/terraform-prerequisites.sh`, which is how this
    configuration is meant to be run.
  EOT
  type        = string
  default     = "kind-inferops-dev"

  validation {
    condition     = can(regex("^kind-.+$", var.kube_context)) || var.kube_context == "docker-desktop"
    error_message = "The context must be a kind cluster's context ('kind-<name>') or exactly 'docker-desktop'. ADR 0011 supports exactly these two local Kubernetes providers, and every script in this repository names the project context explicitly rather than inheriting one."
  }
}

variable "namespace" {
  description = "The platform namespace. Must match INFEROPS_RELEASE_NAMESPACE in scripts/environment/lib.sh, which is the namespace the release lifecycle installs into."
  type        = string
  default     = "inferops-release"
}

variable "model_cache_claim_name" {
  description = "The claim the chart mounts. Must match `model.cache.claimName` in the values file a release is installed with."
  type        = string
  default     = "inferops-model-cache"
}

variable "model_cache_size" {
  description = "How large the model cache claim is requested. Reclaimed by `terraform destroy`, or by deleting the cluster."
  type        = string
  default     = "4Gi"
}

variable "storage_class_name" {
  description = "The storage class for the model cache claim, or null for the cluster default."
  type        = string
  default     = null
}
