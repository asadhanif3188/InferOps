#!/usr/bin/env bash
# Reports which supported local Kubernetes providers this host can currently
# see. Never selects one: `detection-never-selects`
# (docs/environment/local-cluster-provider-contract.md). Every mutating
# workflow still requires an explicit INFEROPS_PROVIDER -- and for kind, an
# explicit INFEROPS_KIND_CLUSTER_NAME -- and re-verifies it itself through
# inferops::resolve_target before acting. This script's answer is advisory
# only, is never written to a file, and is never read back by another script.
#
# Read-only: it creates nothing and changes no host, engine, or cluster state.
#
# Usage: scripts/environment/target-detect.sh

# shellcheck source=scripts/environment/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

[ "$#" -eq 0 ] ||
  inferops::fail "expected no arguments, got $#: $*. Usage: target-detect.sh"

inferops::section "kind"

if command -v kind >/dev/null 2>&1; then
  clusters="$(kind get clusters 2>/dev/null || true)"
  if [ -n "${clusters}" ]; then
    inferops::log "kind reports:"
    printf '%s\n' "${clusters}" | sed 's/^/  /'
  else
    inferops::log "kind reports no clusters."
  fi
else
  inferops::log "the kind CLI is not on PATH; not checked."
fi

inferops::section "docker-desktop"

if kubectl config get-contexts -o name 2>/dev/null | grep -Fxq "docker-desktop"; then
  inferops::log "the operator's kubeconfig holds a context named 'docker-desktop'."
else
  inferops::log "no 'docker-desktop' context was found in the operator's kubeconfig."
fi

inferops::section "Result"

inferops::log "this is a report, not a selection. A context existing is not the same as identity being established: every mutating workflow still needs an explicit INFEROPS_PROVIDER, and for kind an INFEROPS_KIND_CLUSTER_NAME, and re-verifies the target itself before acting."
