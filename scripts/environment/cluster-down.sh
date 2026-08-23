#!/usr/bin/env bash
# Removes everything this project created on the local machine, and nothing else.
#
# DESTRUCTIVE. It deletes the kind cluster named inferops-dev, the objects this
# project created inside it, and the project-scoped kubeconfig.
#
# It will not delete a cluster it did not create, will not touch the
# contributor's default kubeconfig, and will not prune the container engine.
# Those prohibitions are ADR 0001 (D6) and are enforced here rather than
# documented and hoped for.
#
# Usage:
#   scripts/environment/cluster-down.sh              # full teardown
#   scripts/environment/cluster-down.sh --workload   # delete only project objects, keep the cluster
#   scripts/environment/cluster-down.sh --purge-node-image
#          # full teardown, and additionally remove the cached node image

# shellcheck source=scripts/environment/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

# Every argument is inspected, not just the first. Silently ignoring a trailing
# argument on a destructive script means running something other than what the
# contributor asked for.
[ "$#" -le 1 ] ||
  inferops::fail "expected at most one argument, got $#: $*. See the usage note at the top of this script."

mode="full"
case "${1:-}" in
  --workload) mode="workload" ;;
  --purge-node-image) mode="purge" ;;
  "") ;;
  *) inferops::fail "unknown argument '$1'. See the usage note at the top of this script." ;;
esac

inferops::require_cmd kind
inferops::require_cmd kubectl

if [ "${mode}" = "workload" ]; then
  inferops::section "Partial teardown: project objects only"

  # Refuses outright if the reachable cluster is not ours.
  inferops::assert_target_cluster

  # Scoped by the project's own label, inside the project's own namespace. No
  # bare `delete namespace` of anything unprefixed, and no all-namespaces sweep.
  inferops::kubectl delete all,configmap \
    -n "${INFEROPS_NAMESPACE}" \
    -l "${INFEROPS_PART_OF_SELECTOR}" \
    --ignore-not-found=true --wait=true
  inferops::kubectl delete namespace "${INFEROPS_NAMESPACE}" \
    --ignore-not-found=true --wait=true

  inferops::log "project objects removed; cluster '${INFEROPS_CLUSTER_NAME}' left running."
  exit 0
fi

inferops::section "Full teardown"

if inferops::cluster_exists; then
  # Scoped delete before the cluster goes, so that the ordinary path is exercised
  # rather than only ever masked by cluster deletion.
  #
  # This sends a delete into whatever cluster the project kubeconfig reaches, so
  # it is gated on the same identity evidence as every other object-scoped
  # delete. When identity cannot be established the step is skipped and said so
  # aloud, rather than aborting: the cluster deletion below is scoped by kind's
  # own bookkeeping and remains safe regardless.
  if problem="$(inferops::target_cluster_problem)"; then
    inferops::kubectl delete namespace "${INFEROPS_NAMESPACE}" \
      --ignore-not-found=true --wait=false || true
  else
    inferops::warn "skipping the scoped namespace delete: ${problem}"
  fi

  inferops::log "deleting cluster '${INFEROPS_CLUSTER_NAME}'"
  kind delete cluster --name "${INFEROPS_CLUSTER_NAME}" --kubeconfig "${INFEROPS_KUBECONFIG}"
else
  inferops::log "cluster '${INFEROPS_CLUSTER_NAME}' does not exist; nothing to delete."
fi

if [ -f "${INFEROPS_KUBECONFIG_POSIX}" ]; then
  rm -f "${INFEROPS_KUBECONFIG_POSIX}"
  inferops::log "removed the project kubeconfig ${INFEROPS_KUBECONFIG_REL}"
fi
rmdir "$(dirname "${INFEROPS_KUBECONFIG_POSIX}")" 2>/dev/null || true

if [ "${mode}" = "purge" ]; then
  inferops::section "Reclaiming the cached node image"
  # Opt-in, because re-creating the cluster then has to download it again. It is
  # offered at all only because free disk space is a real constraint.
  # The likeliest failure here is not absence but another cluster still holding
  # a reference to the image, so the message must not assert absence.
  docker image rm "kindest/node@${INFEROPS_NODE_IMAGE_DIGEST}" ||
    inferops::warn "the cached node image was not removed. It is either absent already, or still referenced by another cluster."
fi

inferops::section "Verifying residue"

"$(dirname "${BASH_SOURCE[0]}")/verify-clean.sh"
