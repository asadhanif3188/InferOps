#!/usr/bin/env bash
# Asserts that a full teardown left nothing behind except the two artefacts
# ADR 0001 (D6) says survive by design.
#
# Read-only: it deletes nothing. Teardown that is asserted rather than assumed is
# the whole point of running it separately.
#
# Usage: scripts/environment/verify-clean.sh

# shellcheck source=scripts/environment/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

inferops::require_cmd kind

# Not just "is the CLI installed" but "does the engine answer". Every check below
# asks the engine a question and treats an empty answer as proof of absence. With
# the engine down, every question returns empty and this script would certify a
# clean teardown while the cluster sat untouched on disk. A verification script
# that cannot fail is worse than none.
inferops::require_engine

residue=0
report_residue() {
  inferops::warn "$1"
  residue=$((residue + 1))
}

inferops::section "Cluster list"

clusters="$(kind get clusters 2>/dev/null || true)"
if printf '%s' "${clusters}" | grep -Fxq "${INFEROPS_CLUSTER_NAME}"; then
  report_residue "cluster '${INFEROPS_CLUSTER_NAME}' still exists."
else
  inferops::log "no cluster named '${INFEROPS_CLUSTER_NAME}'."
fi

inferops::section "Node containers"

# Filtered by kind's own cluster label, so a container belonging to somebody
# else's cluster is neither reported nor at risk.
node_containers="$(docker ps -a \
  --filter "label=io.x-k8s.kind.cluster=${INFEROPS_CLUSTER_NAME}" \
  --format '{{.Names}}' 2>/dev/null || true)"
if [ -n "${node_containers}" ]; then
  report_residue "node containers remain: ${node_containers}"
else
  inferops::log "no node containers labelled for '${INFEROPS_CLUSTER_NAME}'."
fi

inferops::section "Kubeconfig and context"

if [ -f "${INFEROPS_KUBECONFIG_POSIX}" ]; then
  report_residue "the project kubeconfig ${INFEROPS_KUBECONFIG_REL} still exists."
else
  inferops::log "no project kubeconfig at ${INFEROPS_KUBECONFIG_REL}."
fi

# The contributor's default kubeconfig is inspected but never written. Nothing
# in this project can put a context there, so a match is somebody else's cluster
# that happens to share the name — worth saying aloud, but not this project's
# residue and not grounds for failing a teardown that did its job.
if command -v kubectl >/dev/null 2>&1; then
  default_contexts="$(kubectl config get-contexts -o name 2>/dev/null || true)"
  if printf '%s\n' "${default_contexts}" | grep -Fxq "${INFEROPS_KUBE_CONTEXT}"; then
    inferops::warn "a '${INFEROPS_KUBE_CONTEXT}' context exists in the default kubeconfig. This project never writes there, so it is not residue from this teardown — but it points at a cluster that no longer exists."
  else
    inferops::log "no '${INFEROPS_KUBE_CONTEXT}' context in the default kubeconfig."
  fi
fi

inferops::section "Volumes"

orphan_volumes="$(docker volume ls \
  --filter "label=io.x-k8s.kind.cluster=${INFEROPS_CLUSTER_NAME}" \
  --format '{{.Name}}' 2>/dev/null || true)"
if [ -n "${orphan_volumes}" ]; then
  report_residue "volumes remain: ${orphan_volumes}"
else
  inferops::log "no volumes labelled for '${INFEROPS_CLUSTER_NAME}'."
fi

inferops::section "Surviving by design"

# Named rather than hidden. Neither is residue this project may remove: the
# network can be in use by another cluster, and the cached image is retained
# deliberately.
if docker network ls --format '{{.Name}}' 2>/dev/null | grep -Fxq 'kind'; then
  inferops::log "the shared 'kind' network is still present, as ADR 0001 (D6) states it will be."
fi
if docker image ls --format '{{.Repository}}' 2>/dev/null | grep -Fxq 'kindest/node'; then
  inferops::log "the cached node image is retained, as ADR 0001 (D6) states it will be."
  inferops::log "remove it with: scripts/environment/cluster-down.sh --purge-node-image"
fi

inferops::section "Result"

if [ "${residue}" -gt 0 ]; then
  inferops::fail "${residue} item(s) of unexpected residue remain."
fi

inferops::log "teardown verified: no residue beyond the artefacts ADR 0001 (D6) documents."
