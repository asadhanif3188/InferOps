#!/usr/bin/env bash
# Creates the InferOps development cluster from the digest-pinned definition in
# deploy/kind/inferops-dev.yaml and records what was actually created.
#
# Creates: one kind cluster named inferops-dev, and a project-scoped kubeconfig
# at .kube/inferops-dev.config. Touches nothing else. It does not write to the
# contributor's default kubeconfig.
#
# Usage: scripts/environment/cluster-up.sh [--recreate]

# shellcheck source=scripts/environment/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

[ "$#" -le 1 ] ||
  inferops::fail "expected at most one argument, got $#: $*. Usage: cluster-up.sh [--recreate]"

recreate=0
case "${1:-}" in
  --recreate) recreate=1 ;;
  "") ;;
  *) inferops::fail "unknown argument '$1'. Usage: cluster-up.sh [--recreate]" ;;
esac

inferops::require_cmd docker
inferops::require_cmd kind
inferops::require_cmd kubectl

docker version --format '{{.Server.Version}}' >/dev/null 2>&1 ||
  inferops::fail "the container engine is not reachable. Start it and retry."

if inferops::cluster_exists; then
  if [ "${recreate}" -eq 1 ]; then
    inferops::log "cluster '${INFEROPS_CLUSTER_NAME}' exists; deleting it first because --recreate was given."
    "$(dirname "${BASH_SOURCE[0]}")/cluster-down.sh"
  else
    # Silently reusing an existing cluster would make "repeatable" mean nothing:
    # the second run would inherit the first run's state.
    inferops::fail "cluster '${INFEROPS_CLUSTER_NAME}' already exists. Use --recreate to replace it, or cluster-down.sh to remove it."
  fi
fi

inferops::section "Creating cluster '${INFEROPS_CLUSTER_NAME}'"

mkdir -p "$(dirname "${INFEROPS_KUBECONFIG_POSIX}")"

config_path="$(inferops::native_path "${INFEROPS_ROOT}/deploy/kind/inferops-dev.yaml")"

# --wait makes the control plane's readiness part of this command's contract
# rather than something the next script has to discover.
kind create cluster \
  --name "${INFEROPS_CLUSTER_NAME}" \
  --config "${config_path}" \
  --kubeconfig "${INFEROPS_KUBECONFIG}" \
  --wait 300s

inferops::assert_target_cluster

inferops::section "Recorded versions"

inferops::log "kind: $(kind version -q)"
inferops::log "engine server: $(docker version --format '{{.Server.Version}}')"
inferops::log "node image (pinned): kindest/node:${INFEROPS_NODE_IMAGE_TAG}@${INFEROPS_NODE_IMAGE_DIGEST}"

inferops::kubectl version -o yaml | sed -n '1,80p'

# Every remaining question about the new cluster — is it ours, is it running the
# pinned image, are its nodes Ready, is its control plane healthy, do the client
# and server versions agree — is the same question cluster-verify.sh answers, so
# it is asked by running that script rather than by a second implementation here.
# Two implementations of one check drift, and the one that drifts is always the
# one nobody runs on its own.
inferops::section "Verifying the new cluster"

"$(dirname "${BASH_SOURCE[0]}")/cluster-verify.sh"

inferops::section "Ready"

inferops::log "cluster '${INFEROPS_CLUSTER_NAME}' is up."
inferops::log "kubeconfig: ${INFEROPS_KUBECONFIG_REL} (project-scoped, git-ignored)"
inferops::log "use it with: kubectl --kubeconfig ${INFEROPS_KUBECONFIG_REL} --context ${INFEROPS_KUBE_CONTEXT} ..."
