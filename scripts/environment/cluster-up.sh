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

# The digest the node container actually runs, read back from the engine. If it
# differs from the pin above, the pin did not take effect and the run is not
# reproducible.
running_digest="$(docker inspect "${INFEROPS_CLUSTER_NAME}-control-plane" \
  --format '{{index .Image}}' 2>/dev/null || true)"
inferops::log "node container image id: ${running_digest:-unknown}"

inferops::kubectl version -o yaml | sed -n '1,80p'

inferops::section "Node and control-plane health"

inferops::kubectl get nodes -o wide
inferops::kubectl wait --for=condition=Ready node --all --timeout=180s
inferops::kubectl get pods -n kube-system -o wide

inferops::section "Ready"

inferops::log "cluster '${INFEROPS_CLUSTER_NAME}' is up."
inferops::log "kubeconfig: ${INFEROPS_KUBECONFIG_REL} (project-scoped, git-ignored)"
inferops::log "use it with: kubectl --kubeconfig ${INFEROPS_KUBECONFIG_REL} --context ${INFEROPS_KUBE_CONTEXT} ..."
