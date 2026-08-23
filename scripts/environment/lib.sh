#!/usr/bin/env bash
# Shared definitions for the InferOps local environment scripts.
#
# Sourced, never executed. Every value the scripts treat as a target — the
# cluster name, the kubeconfig, the context, the pinned tool versions — is
# defined here once, so that no script can act on a target another script did
# not agree to.
#
# Sourcing it twice would re-declare readonly constants and, with errexit
# inherited, close the caller's shell. Guard against that, because someone will
# eventually source it interactively just to read the values out.

# This file is sourced, not executed, and most of what it defines is consumed by
# the scripts beside it rather than here. That is what SC2034 would report on
# every constant below, so it is disabled once for the file. The directive has to
# precede the first command to apply file-wide, which is why it sits up here.
# shellcheck shell=bash
# shellcheck disable=SC2034

# -E so that the ERR trap in smoke.sh is inherited by shell functions. Without it,
# a kubectl call failing inside inferops::kubectl exits the script without ever
# running the diagnostics collector, which is exactly when diagnostics matter.
if [ -n "${INFEROPS_LIB_SOURCED:-}" ]; then
  return 0
fi
INFEROPS_LIB_SOURCED=1

set -Eeuo pipefail

# Git Bash rewrites command-line arguments that look like POSIX paths before
# handing them to a Windows executable. Nothing here relies on that rewriting,
# and any argument that happens to resemble an absolute path — a label selector,
# a jsonpath expression, a resource name — would be silently corrupted by it.
# Disable it, and convert real paths deliberately through
# inferops::native_path below.
export MSYS_NO_PATHCONV=1
export MSYS2_ARG_CONV_EXCL='*'

# --- Targets ----------------------------------------------------------------

# The cluster this project owns. Nothing here may act on any other cluster.
readonly INFEROPS_CLUSTER_NAME="inferops-dev"

# kind derives the context name from the cluster name with a fixed prefix.
readonly INFEROPS_KUBE_CONTEXT="kind-${INFEROPS_CLUSTER_NAME}"

# ADR 0001 (D5): a project-scoped kubeconfig, never the contributor's default.
readonly INFEROPS_KUBECONFIG_REL=".kube/inferops-dev.config"

readonly INFEROPS_NAMESPACE="inferops-smoke"
readonly INFEROPS_PART_OF_SELECTOR="app.kubernetes.io/part-of=inferops"

# --- Pinned versions --------------------------------------------------------

# Checked, not assumed. A contributor running a different kind release is told
# so rather than left to discover it through a confusing failure later.
readonly INFEROPS_KIND_VERSION="v0.32.0"

# The node image is pinned by digest. The tag is a label for humans.
readonly INFEROPS_NODE_IMAGE_TAG="v1.34.8"
readonly INFEROPS_NODE_IMAGE_DIGEST="sha256:02722c2dedddcfc00febf5d27fbeb9b7b2c14294c82109ff4a85d89ac9ba3256"

# Kubernetes supports a kubectl that is at most one minor version away from the
# API server in either direction.
readonly INFEROPS_SERVER_MINOR="34"
readonly INFEROPS_MAX_SKEW="1"

# Below this the cluster and anything scheduled beside it will not fit. ADR 0001
# (D7) states the minimum tier as 6 GiB reaching the container VM.
readonly INFEROPS_MIN_ENGINE_MEM_BYTES="6442450944"

# --- Paths ------------------------------------------------------------------

inferops::repo_root() {
  # Derived from this file's own location rather than from the caller's working
  # directory, so the scripts behave the same wherever they are invoked from.
  cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd
}

# Windows builds of kubectl, kind, and docker need a native path. Under Git Bash
# an unconverted POSIX path silently resolves to the wrong place.
inferops::native_path() {
  case "${OSTYPE:-}" in
    msys* | cygwin*) cygpath -w "$1" ;;
    *) printf '%s' "$1" ;;
  esac
}

INFEROPS_ROOT="$(inferops::repo_root)"
readonly INFEROPS_ROOT
readonly INFEROPS_KUBECONFIG_POSIX="${INFEROPS_ROOT}/${INFEROPS_KUBECONFIG_REL}"
INFEROPS_KUBECONFIG="$(inferops::native_path "${INFEROPS_KUBECONFIG_POSIX}")"
readonly INFEROPS_KUBECONFIG
readonly INFEROPS_ARTIFACT_DIR="${INFEROPS_ROOT}/.artifacts"

# --- Output -----------------------------------------------------------------

inferops::log() { printf '[inferops] %s\n' "$*"; }
inferops::warn() { printf '[inferops] WARNING: %s\n' "$*" >&2; }
inferops::fail() {
  printf '[inferops] FAILED: %s\n' "$*" >&2
  exit 1
}

inferops::section() { printf '\n[inferops] === %s ===\n' "$*"; }

# --- Guards -----------------------------------------------------------------

inferops::require_cmd() {
  command -v "$1" >/dev/null 2>&1 ||
    inferops::fail "'$1' is not on PATH. See docs/environment/local-cluster.md."
}

# kubectl is only ever invoked through this wrapper, so no invocation can reach
# a context this project does not own by inheriting an ambient KUBECONFIG.
inferops::kubectl() {
  kubectl --kubeconfig "${INFEROPS_KUBECONFIG}" --context "${INFEROPS_KUBE_CONTEXT}" "$@"
}

# Fails loudly rather than reporting "no clusters" when the engine cannot be
# reached. A query that cannot run must never be mistaken for a query that ran
# and found nothing: that reading turns an unreachable engine into a false
# all-clear, and the cleanup evidence depends on this answer.
inferops::require_engine() {
  inferops::require_cmd docker
  docker version --format '{{.Server.Version}}' >/dev/null 2>&1 ||
    inferops::fail "the container engine is not reachable, so its state cannot be inspected. Start it and retry."
}

inferops::cluster_exists() {
  local clusters
  clusters="$(kind get clusters 2>/dev/null || true)"
  printf '%s\n' "${clusters}" | grep -Fxq "${INFEROPS_CLUSTER_NAME}"
}

# Establishes whether the reachable API server really is the cluster this project
# created. Prints why not and returns 1 when it cannot be established; prints
# nothing and returns 0 when it can.
#
# It reports rather than exits so that each caller can decide what a mismatch
# means. Sending an object-scoped delete to an unidentified cluster is
# unacceptable and must abort. Deleting the cluster itself is a different case:
# kind scopes that by its own bookkeeping rather than by whatever the kubeconfig
# happens to point at, so it stays safe even when identity cannot be confirmed.
inferops::target_cluster_problem() {
  if [ ! -f "${INFEROPS_KUBECONFIG_POSIX}" ]; then
    printf 'no project kubeconfig at %s; the cluster is not up.' "${INFEROPS_KUBECONFIG_REL}"
    return 1
  fi

  local current
  current="$(kubectl --kubeconfig "${INFEROPS_KUBECONFIG}" config current-context 2>/dev/null || true)"
  if [ "${current}" != "${INFEROPS_KUBE_CONTEXT}" ]; then
    printf "expected context '%s', found '%s'." "${INFEROPS_KUBE_CONTEXT}" "${current:-none}"
    return 1
  fi

  # A context name is a label a human chose, not evidence. What follows is
  # evidence: every node the reachable API server reports must be a container
  # that kind itself labelled as belonging to this cluster. A cluster that is
  # not ours cannot satisfy that, whatever its context happens to be called.
  if ! command -v docker >/dev/null 2>&1; then
    printf "the container engine CLI is needed to confirm the cluster's identity."
    return 1
  fi

  # `|| true` on each capture, because under `pipefail` a failing query would
  # otherwise abort the script before the diagnosis below could be printed —
  # which is precisely when a contributor needs to be told what went wrong.
  local api_nodes kind_nodes unmatched
  api_nodes="$(inferops::kubectl get nodes -o name 2>/dev/null | sed 's|^node/||' | sort || true)"
  if [ -z "${api_nodes}" ]; then
    printf 'the API server reported no nodes, or could not be reached.'
    return 1
  fi

  kind_nodes="$(docker ps \
    --filter "label=io.x-k8s.kind.cluster=${INFEROPS_CLUSTER_NAME}" \
    --format '{{.Names}}' 2>/dev/null | sort || true)"

  # Whatever the API server reports that kind did not label for this cluster.
  unmatched="$(comm -23 <(printf '%s\n' "${api_nodes}") <(printf '%s\n' "${kind_nodes}"))"
  if [ -n "${unmatched}" ]; then
    printf "the reachable cluster reports node(s) outside '%s': %s" \
      "${INFEROPS_CLUSTER_NAME}" "$(printf '%s' "${unmatched}" | tr '\n' ' ')"
    return 1
  fi

  return 0
}

# Refuses to continue unless the reachable API server is the cluster this project
# created. Guards every step that deletes objects inside a cluster: a mistyped or
# stale context must not be able to reach a contributor's real cluster.
inferops::assert_target_cluster() {
  local problem
  if ! problem="$(inferops::target_cluster_problem)"; then
    inferops::fail "refusing to act: ${problem}"
  fi
}
