# The local environment: the only environment this repository has, and the only
# one V1 will have.
#
# State is a file on the contributor's disk, deliberately. There is no backend
# block: a remote backend needs a bucket, a lock table, and credentials, and none
# of the three exists for a cluster that lives inside one laptop's container
# engine and is deleted by a script. `terraform.tfstate` beside this file is host
# state -- it is git-ignored, it is not evidence, and losing it costs one
# `terraform import` of a namespace and a claim rather than any data.
#
# What that state contains is worth stating rather than assuming: the metadata of
# one Namespace and one PersistentVolumeClaim. No credential, no token, no
# kubeconfig, and no model bytes. The kubeconfig is read by path and never copied
# into state.
terraform {
  required_version = ">= 1.9.0"

  required_providers {
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "2.38.0"
    }
  }
}

# The provider never inherits an ambient kubeconfig.
#
# This is the same rule every script in this repository already follows: each
# `kubectl` and `helm` call names the project kubeconfig and the project context
# explicitly, because `KUBECONFIG` and a current-context are process state, and
# an apply that silently followed them would be an apply against whichever
# cluster the terminal happened to be pointed at. `terraform apply` creating a
# namespace in a production cluster because a context was left selected is the
# accident this block exists to make impossible.
provider "kubernetes" {
  config_path    = var.kubeconfig_path
  config_context = var.kube_context
}
