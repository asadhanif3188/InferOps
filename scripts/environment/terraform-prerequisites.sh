#!/usr/bin/env bash
# Runs the Terraform prerequisite layer against the project's own cluster, and
# refuses to run it against anything else.
#
# The configuration is infra/terraform/environments/local. It owns exactly what
# docs/architecture/resource-ownership.md gives Terraform: the platform
# namespace, its shared metadata, and the model cache claim. It owns no release
# object, creates no cluster, and provisions nothing outside a cluster.
#
# Why a wrapper exists at all. Terraform's own validation can check a name; it
# cannot check which cluster a kubeconfig context reaches, and `terraform apply`
# following a context left selected from other work is the accident that turns a
# local experiment into a namespace in somebody's real cluster. This script
# establishes cluster identity the same way every other script here does -- the
# API server's nodes have to be containers kind labelled for this project's
# cluster -- and then hands Terraform the kubeconfig and context explicitly
# rather than letting it inherit either.
#
# Creates (apply): one Namespace and one PersistentVolumeClaim.
# Removes (destroy): the same two, and by cascade anything installed into that
# namespace. That is not the routine uninstall path -- `helm uninstall` is --
# and it is the only operation in this repository that reclaims the roughly
# 1.71 GiB of model weights the claim holds.
#
# Usage:
#   scripts/environment/terraform-prerequisites.sh check
#   scripts/environment/terraform-prerequisites.sh plan
#   scripts/environment/terraform-prerequisites.sh apply
#   scripts/environment/terraform-prerequisites.sh destroy --confirm

# shellcheck source=scripts/environment/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

# The configuration this script operates, relative to the repository root. Both
# paths are constants here for the same reason the cluster name is one in
# lib.sh: a literal repeated in four commands survives a move of the directory.
readonly INFEROPS_TF_ROOT_REL="infra/terraform"
readonly INFEROPS_TF_ENV_REL="infra/terraform/environments/local"

action=""
confirmed=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    check | plan | apply | destroy)
      [ -z "${action}" ] ||
        inferops::fail "two actions were given ('${action}' and '$1'). This script performs one at a time, so that its output describes what it did."
      action="$1"
      shift
      ;;
    --confirm)
      confirmed=1
      shift
      ;;
    *)
      inferops::fail "unknown argument '$1'. Usage: terraform-prerequisites.sh check|plan|apply|destroy [--confirm]"
      ;;
  esac
done

[ -n "${action}" ] ||
  inferops::fail "expected one of check, plan, apply, destroy. Usage: terraform-prerequisites.sh check|plan|apply|destroy [--confirm]"

inferops::require_cmd terraform

tf_root_dir="${INFEROPS_ROOT}/${INFEROPS_TF_ROOT_REL}"
tf_env_dir="${INFEROPS_ROOT}/${INFEROPS_TF_ENV_REL}"
[ -d "${tf_env_dir}" ] ||
  inferops::fail "no Terraform environment at ${INFEROPS_TF_ENV_REL}"

tf_root_path="$(inferops::native_path "${tf_root_dir}")"
tf_env_path="$(inferops::native_path "${tf_env_dir}")"

# --- check: reads files, contacts nothing -----------------------------------
#
# `-backend=false` is what makes this runnable with no cluster and no state: it
# initialises the provider and the module and skips the backend entirely. A
# contributor with no cluster can still be told that this configuration is
# malformed.
if [ "${action}" = "check" ]; then
  inferops::section "terraform fmt"
  terraform fmt -check -recursive "${tf_root_path}"

  inferops::section "terraform init (no backend)"
  terraform -chdir="${tf_env_path}" init -backend=false -input=false

  inferops::section "terraform validate"
  terraform -chdir="${tf_env_path}" validate

  inferops::log "format and validation passed. Nothing was contacted and no state was read."
  exit 0
fi

# --- everything below reaches a cluster -------------------------------------

inferops::require_cmd kubectl
inferops::require_engine
inferops::assert_target_cluster

[ -f "${INFEROPS_KUBECONFIG_POSIX}" ] ||
  inferops::fail "no project kubeconfig at ${INFEROPS_KUBECONFIG_REL}. Bring the cluster up first: scripts/environment/cluster-up.sh"

# Terraform is given the target rather than allowed to find one. These are
# passed as TF_VAR_ environment variables instead of `-var` because a Windows
# kubeconfig path contains backslashes and `-var` values are HCL: `\8` in
# `D:\8...` is an invalid escape sequence there, and a check that failed on one
# contributor's directory layout would be worse than no check.
export TF_VAR_kubeconfig_path="${INFEROPS_KUBECONFIG}"
export TF_VAR_kube_context="${INFEROPS_KUBE_CONTEXT}"
export TF_VAR_namespace="${INFEROPS_RELEASE_NAMESPACE}"

inferops::section "terraform init"
terraform -chdir="${tf_env_path}" init -input=false

plan_dir="${INFEROPS_ARTIFACT_DIR}/terraform"
mkdir -p "${plan_dir}"
plan_file="$(inferops::native_path "${plan_dir}/prerequisites.tfplan")"

case "${action}" in
  plan)
    inferops::section "terraform plan"
    terraform -chdir="${tf_env_path}" plan -input=false -out="${plan_file}"
    inferops::log "plan written to .artifacts/terraform/prerequisites.tfplan. It is host state, not evidence, and .artifacts/ is ignored by version control."
    ;;

  apply)
    # Planned first and then applied from the saved plan, so that what is applied
    # is what was shown. `terraform apply` on its own re-plans, and the thing a
    # reader was shown is then not necessarily the thing that ran.
    inferops::section "terraform plan"
    terraform -chdir="${tf_env_path}" plan -input=false -out="${plan_file}"

    inferops::section "terraform apply"
    terraform -chdir="${tf_env_path}" apply -input=false "${plan_file}"

    inferops::log "prerequisites applied. Install a release into them with scripts/environment/helm-lifecycle.sh; never pass a flag that would let Helm create this namespace."
    ;;

  destroy)
    # A release still installed here would be destroyed by the namespace cascade
    # with its Helm state left claiming it exists. Uninstalling first is the
    # ordered path, and this refuses rather than doing it for the operator:
    # removing somebody's release is not a decision a prerequisite teardown gets
    # to take.
    if inferops::helm status "${INFEROPS_RELEASE_NAME}" \
      --namespace "${INFEROPS_RELEASE_NAMESPACE}" >/dev/null 2>&1; then
      inferops::fail "release '${INFEROPS_RELEASE_NAME}' is still installed in '${INFEROPS_RELEASE_NAMESPACE}'. Destroying the namespace would take it with it and leave Helm's own record claiming it exists. Uninstall it first, then run this again."
    fi

    inferops::warn "terraform destroy removes the namespace '${INFEROPS_RELEASE_NAMESPACE}' and the model cache claim. Deleting a namespace cascades: anything still inside it goes too."
    inferops::warn "This is the only operation in this repository that reclaims the model weights -- roughly 1.71 GiB -- and the next release will re-download them over a transport whose certificate this project does not validate."

    [ "${confirmed}" -eq 1 ] ||
      inferops::fail "destroy needs --confirm. Usage: terraform-prerequisites.sh destroy --confirm"

    inferops::section "terraform destroy"
    terraform -chdir="${tf_env_path}" destroy -input=false -auto-approve

    inferops::log "prerequisites destroyed. The cluster is untouched: removing it is scripts/environment/cluster-down.sh, and neither Terraform nor Helm may do it."
    ;;
esac
