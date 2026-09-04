#!/usr/bin/env bash
# Establishes that the InferOps development cluster exists, is the cluster this
# project created, is running what the repository pinned, and is healthy.
#
# Read-only: it creates nothing, deletes nothing, and changes no host, engine, or
# cluster state. Running it twice gives the same answer, which is what makes
# "verify" a step a contributor can repeat rather than a side effect of creation.
#
# It runs every check before reporting, rather than stopping at the first
# failure, because a contributor whose cluster is wrong in three ways should be
# told all three once.
#
# Usage: scripts/environment/cluster-verify.sh

# shellcheck source=scripts/environment/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

[ "$#" -eq 0 ] ||
  inferops::fail "expected no arguments, got $#: $*. Usage: cluster-verify.sh"

inferops::require_cmd kind
inferops::require_cmd kubectl
inferops::require_engine

problems=0
note_problem() {
  inferops::warn "$1"
  problems=$((problems + 1))
}

# Set once the API server has been confirmed to be this project's cluster. The
# checks after that point ask the cluster questions, and asking them of a cluster
# whose identity is not established would be reporting on somebody else's.
identified=0

inferops::section "Cluster exists"

if inferops::cluster_exists; then
  inferops::log "kind reports a cluster named '${INFEROPS_CLUSTER_NAME}'."
else
  note_problem "no cluster named '${INFEROPS_CLUSTER_NAME}'. Create it with scripts/environment/cluster-up.sh."
fi

inferops::section "Kubeconfig and context"

if [ -f "${INFEROPS_KUBECONFIG_POSIX}" ]; then
  inferops::log "project kubeconfig present at ${INFEROPS_KUBECONFIG_REL}."
else
  note_problem "no project kubeconfig at ${INFEROPS_KUBECONFIG_REL}."
fi

# The same evidence every destructive step is gated on, applied here where it
# costs nothing: context name, then the node identity behind it.
if problem="$(inferops::target_cluster_problem)"; then
  identified=1
  inferops::log "context '${INFEROPS_KUBE_CONTEXT}' resolves to nodes kind labelled for '${INFEROPS_CLUSTER_NAME}'."
else
  note_problem "cluster identity not established: ${problem}"
fi

inferops::section "Pinned node image"

running_digest="$(inferops::running_node_digest)"
if [ "${running_digest}" = "${INFEROPS_NODE_IMAGE_DIGEST}" ]; then
  inferops::log "node image digest matches the pin: ${running_digest}"
elif [ -z "${running_digest}" ]; then
  # Absent, not different. An image built or loaded locally carries no repository
  # digest, and neither does a node container that is not there at all.
  inferops::warn "the running node reports no repository digest, so the pin could not be verified. This is expected of a locally built or loaded node image, and is what an absent node container looks like too."
else
  note_problem "node image digest mismatch: expected ${INFEROPS_NODE_IMAGE_DIGEST}, running ${running_digest}. This cluster is not the one the repository pins."
fi

inferops::section "Node readiness"

if [ "${identified}" -eq 1 ]; then
  inferops::kubectl get nodes -o wide

  # Bounded, and short. This is a verification of a cluster that is meant to be
  # up already, not the wait that follows creation; a node still coming up after
  # 60 seconds is a finding rather than something to sit through.
  if inferops::kubectl wait --for=condition=Ready node --all --timeout=60s; then
    inferops::log "every node reports Ready."
  else
    note_problem "not every node reached Ready within 60s."
  fi
else
  inferops::warn "skipped: the cluster's identity was not established, so nothing here would be a statement about this project's cluster."
fi

inferops::section "Control-plane workloads"

if [ "${identified}" -eq 1 ]; then
  inferops::kubectl get pods -n kube-system -o wide

  # Anything in kube-system that is neither running nor finished. A cluster whose
  # API server answers while its DNS or its CNI is crash-looping will schedule a
  # workload and then fail it in a way that looks like the workload's fault.
  unhealthy="$(inferops::kubectl get pods -n kube-system \
    --field-selector 'status.phase!=Running,status.phase!=Succeeded' \
    -o name 2>/dev/null || true)"
  if [ -n "${unhealthy}" ]; then
    note_problem "kube-system pods are not running: $(printf '%s' "${unhealthy}" | tr '\n' ' ')"
  else
    inferops::log "every kube-system pod is running or has completed."
  fi
else
  inferops::warn "skipped: the cluster's identity was not established."
fi

inferops::section "Server version"

if [ "${identified}" -eq 1 ]; then
  # The live server, not the pinned expectation. preflight.sh compares kubectl
  # against the minor the repository pins, which is the right question before a
  # cluster exists. Once one does, the question is what it is actually running.
  #
  # Anchored on the enclosing key rather than on the order the keys happen to
  # appear in, so a release that adds a version block ahead of the server's does
  # not silently start reporting somebody else's number.
  server_minor="$(inferops::kubectl version -o json 2>/dev/null |
    awk -F'"' '/"serverVersion"/ { server = 1 } server && /"minor"/ { print $4; exit }' |
    tr -cd '0-9' || true)"
  client_minor="$(kubectl version --client=true -o json 2>/dev/null |
    awk -F'"' '/"minor"/ { print $4; exit }' | tr -cd '0-9' || true)"

  if [ -n "${server_minor}" ]; then
    inferops::log "server minor ${server_minor} (pinned node image: ${INFEROPS_SERVER_MINOR})"
    if [ "${server_minor}" != "${INFEROPS_SERVER_MINOR}" ]; then
      note_problem "the server reports minor ${server_minor}; the pinned node image is minor ${INFEROPS_SERVER_MINOR}. This cluster is not running what the repository pins."
    fi
  else
    inferops::warn "could not read the server version; it was not compared against the pin."
  fi

  # Reported, not judged. The client's version is a property of the contributor's
  # workstation rather than of the cluster, and preflight.sh already refuses a
  # host whose kubectl is outside the supported window. Failing here as well
  # would mean one prerequisite refused by two scripts, and a contributor being
  # told to fix it by whichever one they happened to run.
  if [ -n "${server_minor}" ] && [ -n "${client_minor}" ]; then
    skew=$((client_minor - server_minor))
    [ "${skew}" -lt 0 ] && skew=$((-skew))
    inferops::log "kubectl minor ${client_minor} against server minor ${server_minor}; skew ${skew}"
    if [ "${skew}" -gt "${INFEROPS_MAX_SKEW}" ]; then
      inferops::warn "kubectl is ${skew} minor versions from the server; the supported skew is ${INFEROPS_MAX_SKEW}. Output from this client against this server is unverified. scripts/environment/preflight.sh owns this prerequisite and refuses it."
    fi
  fi
else
  inferops::warn "skipped: the cluster's identity was not established."
fi

inferops::section "Result"

if [ "${problems}" -gt 0 ]; then
  # Printed rather than collected into a file: this script changes nothing, so
  # there is no state to preserve for later, and everything below can be re-read
  # by running the same commands.
  inferops::section "Diagnostics"
  inferops::log "clusters kind knows about:"
  kind get clusters 2>&1 | sed 's/^/  /' || true
  inferops::log "containers kind labelled for '${INFEROPS_CLUSTER_NAME}':"
  docker ps -a --filter "label=io.x-k8s.kind.cluster=${INFEROPS_CLUSTER_NAME}" \
    --format '{{.Names}}\t{{.Status}}\t{{.Image}}' 2>&1 | sed 's/^/  /' || true
  if [ "${identified}" -eq 1 ]; then
    inferops::log "recent events in kube-system:"
    inferops::kubectl get events -n kube-system --sort-by=.lastTimestamp 2>&1 |
      tail -20 | sed 's/^/  /' || true
  fi

  inferops::fail "${problems} verification check(s) failed. Nothing was changed. Recover with scripts/environment/cluster-up.sh --recreate, or remove the cluster with scripts/environment/cluster-down.sh."
fi

inferops::log "cluster '${INFEROPS_CLUSTER_NAME}' is present, identified, pinned, and healthy."
