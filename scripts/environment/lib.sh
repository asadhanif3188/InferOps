#!/usr/bin/env bash
# Shared definitions for the InferOps local environment scripts.
#
# Sourced, never executed. Every value the scripts treat as a target — the
# cluster name, the kubeconfig, the context, the pinned tool versions — is
# defined here once, so that no script can act on a target another script did
# not agree to.

# This file is sourced, not executed, and most of what it defines is consumed by
# the scripts beside it rather than here. That is what SC2034 would report on
# every constant below, so it is disabled once for the file. The directive has to
# precede the first command to apply file-wide, which is why it sits up here.
# shellcheck shell=bash
# shellcheck disable=SC2034

set -euo pipefail

# Git Bash rewrites command-line arguments that look like POSIX paths before
# handing them to a Windows executable, which corrupts Kubernetes paths such as
# /index.html and /readyz. Disable that rewriting and pass native paths
# explicitly instead, via inferops::native_path below.
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

inferops::cluster_exists() {
  kind get clusters 2>/dev/null | grep -Fxq "${INFEROPS_CLUSTER_NAME}"
}

# Refuses to continue unless the reachable API server is the cluster this project
# created. Guards every destructive step: a mistyped or stale context must not be
# able to reach a contributor's real cluster.
inferops::assert_target_cluster() {
  [ -f "${INFEROPS_KUBECONFIG_POSIX}" ] ||
    inferops::fail "no project kubeconfig at ${INFEROPS_KUBECONFIG_REL}; the cluster is not up."

  local current
  current="$(kubectl --kubeconfig "${INFEROPS_KUBECONFIG}" config current-context 2>/dev/null || true)"
  [ "${current}" = "${INFEROPS_KUBE_CONTEXT}" ] ||
    inferops::fail "refusing to act: expected context '${INFEROPS_KUBE_CONTEXT}', found '${current:-none}'."

  # A context name is a label a human chose, not evidence. What follows is
  # evidence: every node the reachable API server reports must be a container
  # that kind itself labelled as belonging to this cluster. A cluster that is
  # not ours cannot satisfy that, whatever its context happens to be called.
  command -v docker >/dev/null 2>&1 ||
    inferops::fail "refusing to act: the container engine CLI is needed to confirm the cluster's identity."

  local api_nodes kind_nodes unmatched
  api_nodes="$(inferops::kubectl get nodes -o name 2>/dev/null | sed 's|^node/||' | sort)"
  [ -n "${api_nodes}" ] ||
    inferops::fail "refusing to act: the API server reported no nodes."

  kind_nodes="$(docker ps \
    --filter "label=io.x-k8s.kind.cluster=${INFEROPS_CLUSTER_NAME}" \
    --format '{{.Names}}' 2>/dev/null | sort)"

  # Whatever the API server reports that kind did not label for this cluster.
  unmatched="$(comm -23 <(printf '%s\n' "${api_nodes}") <(printf '%s\n' "${kind_nodes}"))"
  [ -z "${unmatched}" ] ||
    inferops::fail "refusing to act: the reachable cluster reports node(s) outside '${INFEROPS_CLUSTER_NAME}': $(printf '%s' "${unmatched}" | tr '\n' ' ')"
}
