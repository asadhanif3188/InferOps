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
# and it reclaims the roughly 1.71 GiB of model weights the claim holds while
# leaving the cluster standing. Deleting the cluster reclaims them too: the
# claim is backed by local-path storage inside the kind node container, and
# scripts/environment/cluster-down.sh removes that container. Those are the two
# ways, and neither of them is `helm uninstall`.
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
    #
    # What that refusal needs is absence, positively established. The earlier
    # form asked `helm status` and read any nonzero exit as "nothing installed".
    # A nonzero exit says the question went unanswered, and the reasons it goes
    # unanswered -- helm absent from PATH, the API server unreachable, RBAC
    # forbidding the read, a release record that will not deserialise -- are
    # exactly the conditions under which destroying a namespace is least safe.
    # An unanswered query is not an empty namespace. Every one of them refuses
    # here, and the `terraform destroy` below is never reached.
    inferops::require_cmd helm

    # `list` rather than `status`, because absence is the thing that has to be
    # shown and `list` shows it: a successful call whose answer does not contain
    # the release. `--all` so that a failed, pending-install, pending-upgrade,
    # pending-rollback, uninstalling or superseded release counts as present --
    # the cascade takes those exactly as it takes a healthy one, and a plain
    # `helm list` reports only the deployed ones. `--short` prints one release
    # name per line and nothing else.
    #
    # stderr is sent to a file rather than into the capture, so that a routine
    # Helm warning cannot arrive on the same stream as a release name. The file
    # is a diagnostic for the refusal message and sits in the ignored artifact
    # directory.
    helm_diag="${plan_dir}/helm-list.stderr"
    releases=""
    if ! releases="$(inferops::helm list --all \
      --namespace "${INFEROPS_RELEASE_NAMESPACE}" --short 2>"${helm_diag}")"; then
      inferops::fail "could not read Helm's releases in '${INFEROPS_RELEASE_NAMESPACE}', so whether destroying it would take one with it is unknown. Helm said: $(tr -d '\r' <"${helm_diag}" | tr '\n' ' ' | cut -c 1-300). Refusing: an unanswered query is not an empty namespace. This refusal is by design and there is no flag that overrides it."
    fi

    # A release name is a Kubernetes name. Anything else on that stream is output
    # this script does not understand, and output it does not understand cannot
    # be read as evidence that the namespace holds nothing.
    installed=""
    while IFS= read -r release_line; do
      release_line="${release_line%$'\r'}"
      [ -n "${release_line}" ] || continue
      case "${release_line}" in
        *[!a-z0-9.-]* | -* | .* | *- | *.)
          inferops::fail "'helm list --short' returned a line that is not a release name: '${release_line}'. Refusing: output this script cannot parse is not evidence that '${INFEROPS_RELEASE_NAMESPACE}' holds no release."
          ;;
      esac
      installed="${installed}${release_line} "
    done <<<"${releases}"

    if printf '%s\n' ${installed} | grep -Fxq "${INFEROPS_RELEASE_NAME}"; then
      inferops::fail "release '${INFEROPS_RELEASE_NAME}' is still installed in '${INFEROPS_RELEASE_NAMESPACE}'. Destroying the namespace would take it with it and leave Helm's own record claiming it exists. Uninstall it first, then run this again."
    fi

    # Not only this project's release: the cascade is indifferent to whose
    # release it takes, so anything Helm tracks here stops the teardown.
    if [ -n "${installed}" ]; then
      inferops::fail "Helm still tracks release(s) in '${INFEROPS_RELEASE_NAMESPACE}': ${installed}. Destroying the namespace would take them with it and leave Helm's own records claiming they exist. Uninstall them first, then run this again."
    fi

    inferops::warn "terraform destroy removes the namespace '${INFEROPS_RELEASE_NAMESPACE}' and the model cache claim. Deleting a namespace cascades: anything still inside it goes too."
    inferops::warn "This reclaims the model weights -- roughly 1.71 GiB -- and so does deleting the cluster, because the claim is backed by local-path storage inside the kind node container. The next release re-downloads them over a transport whose certificate this project does not validate."

    [ "${confirmed}" -eq 1 ] ||
      inferops::fail "destroy needs --confirm. Usage: terraform-prerequisites.sh destroy --confirm"

    inferops::section "terraform destroy"
    terraform -chdir="${tf_env_path}" destroy -input=false -auto-approve

    inferops::log "prerequisites destroyed. The cluster is untouched: removing it is scripts/environment/cluster-down.sh, and neither Terraform nor Helm may do it."
    ;;
esac
