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

# The Helm release, and the namespace it installs into. A separate namespace
# from the smoke one on purpose: the smoke workload and the InferOps release are
# different things with different lifetimes, and sharing a namespace would make
# "what did this release leave behind" unanswerable.
#
# ADR 0001 (D5) requires the `inferops-` prefix, and the chart refuses a release
# namespace without it.
readonly INFEROPS_RELEASE_NAME="inferops"
readonly INFEROPS_RELEASE_NAMESPACE="inferops-release"
readonly INFEROPS_CHART_PATH="charts/inferops-llm"

# What identifies one release's objects. Helm sets this label on everything it
# installs, so it is what a residue check asks about.
readonly INFEROPS_RELEASE_SELECTOR="app.kubernetes.io/instance=${INFEROPS_RELEASE_NAME}"

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

# The same tier's processor figure. It was a bare literal inside preflight until
# V1-S3-001; a documented requirement that lives in one script and not beside the
# requirement it enforces is a requirement waiting to disagree with itself.
readonly INFEROPS_MIN_ENGINE_CPUS="4"

# The same tier's disk figure: 20 GB free on one volume. Decimal GB, not GiB,
# because that is the unit D7's table states and the unit its measured column was
# recorded in. Converting it here to keep the arithmetic honest would silently
# raise the bar by 7%.
readonly INFEROPS_MIN_FREE_DISK_BYTES="20000000000"

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

# Which volume the disk requirement is measured on. It selects what is measured;
# it cannot lower the threshold or skip the check.
#
# Overridable because ADR 0001 (R1) names relocating the engine's virtual disk as
# one of the ways to satisfy this tier. Once it has been moved, the volume that
# constrains a cluster is no longer the default one, and measuring the default
# would fail a host that in fact has the room.
readonly INFEROPS_DISK_VOLUME="${INFEROPS_DISK_VOLUME:-}"

# --- Output -----------------------------------------------------------------

inferops::log() { printf '[inferops] %s\n' "$*"; }
inferops::warn() { printf '[inferops] WARNING: %s\n' "$*" >&2; }
inferops::fail() {
  printf '[inferops] FAILED: %s\n' "$*" >&2
  exit 1
}

inferops::section() { printf '\n[inferops] === %s ===\n' "$*"; }

# --- Measurement ------------------------------------------------------------

# Binary and decimal renderings of a byte count. Two functions rather than one,
# because D7 states memory in GiB and disk in GB, and printing either figure in
# the other unit would make a contributor compare a measurement against a
# threshold expressed differently.
inferops::gib() { awk -v b="$1" 'BEGIN { printf "%.2f GiB", b / 1024 / 1024 / 1024 }'; }
inferops::gb() { awk -v b="$1" 'BEGIN { printf "%.2f GB", b / 1000 / 1000 / 1000 }'; }

# The volume whose free space constrains a cluster on this host, as two fields:
# a word saying what the path is, then the path itself.
#
#   configured        INFEROPS_DISK_VOLUME was set, and names it.
#   engine-data-root  The engine's own data directory is visible out here, so the
#                     figure is the engine's own.
#   host-volume       It is not — on Windows and macOS it is a path inside a
#                     virtual machine — so the volume the engine places that
#                     machine's virtual disk on by default is measured instead.
#
# The distinction is reported rather than hidden because only the first two are
# the engine's actual storage. The third is a proxy, and it is the same proxy
# ADR 0001 (D7) states its own tier against and (R11) measured the reference host
# with, which is why a threshold may be applied to it at all.
#
# The word comes first and the path last so that `read -r kind path` puts the
# whole remainder — spaces and all — into the path. A contributor relocating the
# engine's virtual disk on Windows is likely to put it somewhere with a space in
# the name, and the other field order would truncate it at the first one, fail to
# measure it, and downgrade a threshold that must not be downgradable.
inferops::disk_probe_target() {
  if [ -n "${INFEROPS_DISK_VOLUME}" ]; then
    printf 'configured %s' "${INFEROPS_DISK_VOLUME}"
    return 0
  fi

  local engine_root=""
  if command -v docker >/dev/null 2>&1; then
    engine_root="$(docker info --format '{{.DockerRootDir}}' 2>/dev/null || true)"
  fi
  if [ -n "${engine_root}" ] && [ -d "${engine_root}" ]; then
    printf 'engine-data-root %s' "${engine_root}"
    return 0
  fi

  case "${OSTYPE:-}" in
    msys* | cygwin*) printf 'host-volume %s' "$(cygpath -u "${SYSTEMDRIVE:-C:}")" ;;
    *) printf 'host-volume /' ;;
  esac
}

# Free bytes on the volume holding a path. Prints nothing and returns 1 when the
# figure cannot be read, so that a caller can say "not measured" rather than
# treat an unreadable volume as an empty one and fail a host that is fine.
#
# `df -P` is the POSIX-specified single-line-per-filesystem form; without it a
# long device name wraps onto its own line and the field indices below shift.
# `-k` fixes the block size at 1024 bytes rather than inheriting whatever
# BLOCK_SIZE or POSIXLY_CORRECT happens to be set to in the caller's environment.
inferops::free_disk_bytes() {
  local blocks
  blocks="$(df -P -k "$1" 2>/dev/null | awk 'NR == 2 { print $4 }' || true)"
  case "${blocks}" in
    '' | *[!0-9]*) return 1 ;;
  esac
  printf '%s' "$((blocks * 1024))"
}

# The repository digest of the image the control-plane node is actually running,
# or nothing when the engine cannot tell us.
#
# The repository digest, not the container's image ID: the two are only
# incidentally equal and on some engines never are, so comparing the wrong one
# reports a mismatch that does not exist. An image built or loaded locally has no
# repository digest at all, and that case is empty rather than mismatched — a
# caller has to distinguish "different" from "unknowable".
#
# This lives here rather than in the script that creates the cluster because
# creation and verification must compare the pin the same way. A pin checked one
# way at creation and another way afterwards is two pins.
inferops::running_node_digest() {
  local node_image
  node_image="$(docker inspect "${INFEROPS_CLUSTER_NAME}-control-plane" \
    --format '{{.Config.Image}}' 2>/dev/null || true)"
  [ -n "${node_image}" ] || return 0
  docker image inspect "${node_image}" \
    --format '{{range .RepoDigests}}{{.}}{{"\n"}}{{end}}' 2>/dev/null |
    sed -n 's|^kindest/node@||p' | head -1 || true
}

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

# The same argument for helm, and a sharper one. Helm reads KUBECONFIG exactly
# as kubectl does, and `helm uninstall` against an inherited context deletes a
# release on whatever cluster that context happens to name. Every helm call in
# these scripts goes through this wrapper, and a test asserts it.
inferops::helm() {
  helm --kubeconfig "${INFEROPS_KUBECONFIG}" --kube-context "${INFEROPS_KUBE_CONTEXT}" "$@"
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

# --- Provider-aware target verification (ADR 0011) --------------------------
#
# The functions above are the kind helper's own: fixed to the one cluster name
# this repository pins, `inferops-dev`, and used only by cluster-up.sh,
# cluster-down.sh, cluster-verify.sh, and proof.sh. They are unchanged by
# everything below.
#
# What follows is the mechanism docs/environment/local-cluster-provider-contract.md
# describes: every platform workflow (terraform-prerequisites.sh,
# helm-lifecycle.sh, api-image.sh, model-seed-image.sh, and the certification and
# experiment scripts) is given an explicit provider through INFEROPS_PROVIDER --
# `kind` or `docker-desktop`, with no default -- and for `kind`, an explicit
# INFEROPS_KIND_CLUSTER_NAME. Neither variable is read anywhere above this
# point, so the kind helper's own fixed cluster is never affected by either one
# being set, unset, or wrong.
#
# `inferops::resolve_target` is the one entry point. It re-runs the selected
# provider's identity checks against the operator's own kubeconfig every time it
# is called, writes a fresh project-scoped kubeconfig holding exactly the one
# context it just verified, and sets the INFEROPS_TARGET_* variables every
# platform workflow acts through afterwards. A target resolved by an earlier
# call, or recorded in a file, is never trusted: `verification-precedes-every-mutation`.

readonly INFEROPS_SUPPORTED_PROVIDERS="kind docker-desktop"

# Distinct from INFEROPS_KUBECONFIG_REL above on purpose. That one belongs to the
# kind helper's own fixed cluster; this one belongs to whichever target the
# operator explicitly selected, kind or Docker Desktop, and is rewritten by every
# call to inferops::resolve_target.
readonly INFEROPS_TARGET_KUBECONFIG_REL=".kube/inferops-target.config"

# Overridable for the same reason INFEROPS_DISK_VOLUME above is: a test exercising
# inferops::resolve_target against fake kubectl/kind/docker executables must not
# write into this checkout's real .kube/ directory, which a concurrent real
# workflow run in the same checkout could be reading at the same time.
readonly INFEROPS_TARGET_KUBECONFIG_POSIX_PATH="${INFEROPS_TARGET_KUBECONFIG_POSIX_PATH:-${INFEROPS_ROOT}/${INFEROPS_TARGET_KUBECONFIG_REL}}"

inferops::_provider_supported() {
  case " ${INFEROPS_SUPPORTED_PROVIDERS} " in
    *" $1 "*) return 0 ;;
    *) return 1 ;;
  esac
}

# The operator's own kubeconfig context names, or nothing if none can be read.
# This is the one place anything here reads the ambient kubeconfig instead of the
# project-scoped one it is about to write, and it only ever reads: nothing here
# acts through what it finds. `access-never-inherits-an-ambient-context` is a
# rule about acting, and naming a context to decide whether the selected target
# exists at all is not that.
inferops::_operator_contexts() {
  kubectl config get-contexts -o name 2>/dev/null || true
}

# How many kind clusters are named exactly $1. Kind cluster names are unique by
# construction, so this is normally 0 or 1; it is counted rather than tested as a
# boolean so that `ambiguous-target` stays a distinct refusal from `target-missing`.
inferops::_kind_cluster_matches() {
  kind get clusters 2>/dev/null | grep -Fxc "$1" || true
}

# Writes the project-scoped, single-context kubeconfig every platform workflow
# acts through, from the one context named $1 in the operator's own kubeconfig.
# `--minify` with `--context` reads that context without switching the
# operator's own current one, so this never mutates the file it reads from.
inferops::_write_target_kubeconfig() {
  local context="$1"
  mkdir -p "$(dirname "${INFEROPS_TARGET_KUBECONFIG_POSIX_PATH}")"
  kubectl --context "${context}" config view --minify --flatten \
    >"${INFEROPS_TARGET_KUBECONFIG_POSIX_PATH}.tmp" 2>/dev/null || return 1
  [ -s "${INFEROPS_TARGET_KUBECONFIG_POSIX_PATH}.tmp" ] || {
    rm -f "${INFEROPS_TARGET_KUBECONFIG_POSIX_PATH}.tmp"
    return 1
  }
  mv "${INFEROPS_TARGET_KUBECONFIG_POSIX_PATH}.tmp" "${INFEROPS_TARGET_KUBECONFIG_POSIX_PATH}"
}

# `kind`'s three identity checks, generalised to the selected cluster name rather
# than the pinned one above: the project kubeconfig names the kind context, every
# node the reachable API server reports is a container kind labelled for that
# cluster, and a context name alone never passes either question. Prints why not
# and returns 1 when the target cannot be established; prints nothing and
# returns 0 when it can.
inferops::_kind_target_problem() {
  if [ -z "${INFEROPS_KIND_CLUSTER_NAME:-}" ]; then
    printf 'ambiguous-target: provider "kind" was selected with no INFEROPS_KIND_CLUSTER_NAME. Several kind clusters can exist on one engine, and choosing among them is exactly the decision that must not be made on the operators behalf.'
    return 1
  fi

  inferops::require_cmd kind

  local matches
  matches="$(inferops::_kind_cluster_matches "${INFEROPS_KIND_CLUSTER_NAME}")"
  case "${matches}" in
    0)
      printf "target-missing: kind does not list a cluster named '%s'." "${INFEROPS_KIND_CLUSTER_NAME}"
      return 1
      ;;
    1) ;;
    *)
      printf "ambiguous-target: kind lists '%s' %s times, not exactly once." \
        "${INFEROPS_KIND_CLUSTER_NAME}" "${matches}"
      return 1
      ;;
  esac

  local expected_context="kind-${INFEROPS_KIND_CLUSTER_NAME}"
  if ! inferops::_operator_contexts | grep -Fxq "${expected_context}"; then
    printf "target-missing: no context named '%s' in the operator's kubeconfig." "${expected_context}"
    return 1
  fi

  if ! inferops::_write_target_kubeconfig "${expected_context}"; then
    printf "target-missing: could not read context '%s' from the operator's kubeconfig." "${expected_context}"
    return 1
  fi

  # Windows kubectl needs a native path, the same as every other invocation in
  # this file: under Git Bash an unconverted POSIX path silently resolves to
  # the wrong place, which here would mean every read below finding nothing --
  # a kubeconfig this function itself just wrote a moment earlier.
  local target_kubeconfig_native
  target_kubeconfig_native="$(inferops::native_path "${INFEROPS_TARGET_KUBECONFIG_POSIX_PATH}")"

  local current
  current="$(kubectl --kubeconfig "${target_kubeconfig_native}" config current-context 2>/dev/null || true)"
  if [ "${current}" != "${expected_context}" ]; then
    printf "unexpected-context: expected '%s', the project-scoped kubeconfig holds '%s'." \
      "${expected_context}" "${current:-none}"
    return 1
  fi

  if ! command -v docker >/dev/null 2>&1; then
    printf 'target-unreachable: the container engine CLI is needed to confirm the cluster identity.'
    return 1
  fi

  local api_nodes kind_nodes unmatched
  api_nodes="$(kubectl --kubeconfig "${target_kubeconfig_native}" --context "${expected_context}" \
    get nodes -o name 2>/dev/null | sed 's|^node/||' | sort || true)"
  if [ -z "${api_nodes}" ]; then
    printf 'target-unreachable: the API server reported no nodes, or could not be reached.'
    return 1
  fi

  kind_nodes="$(docker ps \
    --filter "label=io.x-k8s.kind.cluster=${INFEROPS_KIND_CLUSTER_NAME}" \
    --format '{{.Names}}' 2>/dev/null | sort || true)"

  unmatched="$(comm -23 <(printf '%s\n' "${api_nodes}") <(printf '%s\n' "${kind_nodes}"))"
  if [ -n "${unmatched}" ]; then
    printf "provider-mismatch: the reachable cluster reports node(s) outside '%s': %s" \
      "${INFEROPS_KIND_CLUSTER_NAME}" "$(printf '%s' "${unmatched}" | tr '\n' ' ')"
    return 1
  fi

  return 0
}

# Docker Desktop's two implemented identity checks: the operator's kubeconfig
# holds a context literally named `docker-desktop`, and every node the reachable
# API server reports matches the one shape this project has observed and
# recorded -- a single node named `desktop-control-plane`. A node set of any
# other shape is refused until it has been observed and recorded, rather than
# accepted because it might be legitimate.
#
# What this does not check: whether those nodes are actually bound to this
# machine's Docker Desktop virtual machine, the way the kind check above binds
# nodes to containers kind itself labelled. Whether that is even observable has
# not been established (docs/environment/local-cluster-provider-contract.md,
# `the-nodes-are-bound-to-the-local-engine`), so this guard is a name-and-shape
# check rather than kind's stronger one, and is recorded as a security exception
# rather than presented as equal to it.
inferops::_docker_desktop_target_problem() {
  local expected_context="docker-desktop"

  local matches
  matches="$(inferops::_operator_contexts | grep -Fxc "${expected_context}" || true)"
  case "${matches}" in
    0)
      printf "target-missing: no context named '%s' in the operator's kubeconfig." "${expected_context}"
      return 1
      ;;
    1) ;;
    *)
      printf "ambiguous-target: the operator's kubeconfig holds '%s' %s times, not exactly once." \
        "${expected_context}" "${matches}"
      return 1
      ;;
  esac

  if ! inferops::_write_target_kubeconfig "${expected_context}"; then
    printf "target-missing: could not read context '%s' from the operator's kubeconfig." "${expected_context}"
    return 1
  fi

  # See the matching comment in inferops::_kind_target_problem: Windows kubectl
  # needs a native path, not the POSIX one this file otherwise uses throughout.
  local target_kubeconfig_native
  target_kubeconfig_native="$(inferops::native_path "${INFEROPS_TARGET_KUBECONFIG_POSIX_PATH}")"

  local api_nodes node_count
  api_nodes="$(kubectl --kubeconfig "${target_kubeconfig_native}" --context "${expected_context}" \
    get nodes -o name 2>/dev/null | sed 's|^node/||' | sort || true)"
  if [ -z "${api_nodes}" ]; then
    printf 'target-unreachable: the API server reported no nodes, or could not be reached.'
    return 1
  fi

  node_count="$(printf '%s\n' "${api_nodes}" | grep -c . || true)"
  if [ "${node_count}" -ne 1 ] || [ "${api_nodes}" != "desktop-control-plane" ]; then
    printf "provider-mismatch: this project has only observed a single 'desktop-control-plane' node as Docker Desktop's shape; the reachable cluster reports: %s" \
      "$(printf '%s' "${api_nodes}" | tr '\n' ' ')"
    return 1
  fi

  return 0
}

# The dispatcher every refusal that does not name a provider goes through first:
# `no-provider-selected` and `unsupported-provider` apply before either
# provider's own checks could even run.
inferops::_target_problem() {
  if [ -z "${INFEROPS_PROVIDER:-}" ]; then
    printf 'no-provider-selected: no INFEROPS_PROVIDER was given. Set it to "kind" or "docker-desktop"; there is no default.'
    return 1
  fi

  if ! inferops::_provider_supported "${INFEROPS_PROVIDER}"; then
    printf "unsupported-provider: '%s' is neither 'kind' nor 'docker-desktop'." "${INFEROPS_PROVIDER}"
    return 1
  fi

  inferops::require_cmd kubectl

  case "${INFEROPS_PROVIDER}" in
    kind) inferops::_kind_target_problem ;;
    docker-desktop) inferops::_docker_desktop_target_problem ;;
  esac
}

# Every kubectl and helm call a platform workflow makes after resolving a target
# goes through these two, so neither an ambient KUBECONFIG nor the operator's own
# current context can redirect it -- the same property inferops::kubectl and
# inferops::helm give the kind helper, applied to whichever target was selected.
inferops::target_kubectl() {
  kubectl --kubeconfig "${INFEROPS_TARGET_KUBECONFIG}" --context "${INFEROPS_TARGET_CONTEXT}" "$@"
}

inferops::target_helm() {
  helm --kubeconfig "${INFEROPS_TARGET_KUBECONFIG}" --kube-context "${INFEROPS_TARGET_CONTEXT}" "$@"
}

# Refuses before any mutation when the target cannot supply a capability a
# workflow depends on -- including a capability this contract records as
# `unknown` for the selected provider, which is refused rather than assumed.
inferops::require_target_capability() {
  local capability="$1" required="$2" actual="$3"
  [ "${actual}" = "${required}" ] ||
    inferops::fail "refusing: capability-unknown-or-insufficient: this workflow needs '${capability}' to be '${required}'; provider '${INFEROPS_TARGET_PROVIDER}' reports '${actual}'. See docs/environment/local-cluster-provider-contract.md."
}

# The one entry point every platform workflow calls before its first mutation.
# Re-runs the selected provider's identity checks against the operator's own
# kubeconfig, writes a fresh project-scoped kubeconfig holding exactly the
# context just verified, and sets every INFEROPS_TARGET_* variable a consumer in
# docs/environment/local-cluster-provider-contract.md reads. Nothing here is
# cached from an earlier call: verification-precedes-every-mutation.
#
# None of the INFEROPS_TARGET_* variables it sets are `readonly`: every call
# site here invokes this exactly once, but a second call in the same shell --
# a future workflow re-verifying mid-run, an interactive or test harness
# calling it twice -- must re-verify and overwrite rather than abort on a
# readonly-variable error the second time.
inferops::resolve_target() {
  local problem
  if ! problem="$(inferops::_target_problem)"; then
    inferops::fail "refusing to select a target: ${problem}"
  fi

  case "${INFEROPS_PROVIDER}" in
    kind)
      INFEROPS_TARGET_PROVIDER="kind"
      INFEROPS_TARGET_CLUSTER_NAME="${INFEROPS_KIND_CLUSTER_NAME}"
      INFEROPS_TARGET_CONTEXT="kind-${INFEROPS_KIND_CLUSTER_NAME}"
      INFEROPS_TARGET_IMAGE_PREPARATION="kind-load"
      ;;
    docker-desktop)
      INFEROPS_TARGET_PROVIDER="docker-desktop"
      INFEROPS_TARGET_CLUSTER_NAME="docker-desktop"
      INFEROPS_TARGET_CONTEXT="docker-desktop"
      # Not established (docs/environment/local-cluster-provider-contract.md):
      # whether a locally built image is visible to this cluster without a load
      # step has not been observed, and `kind load` is not assumed to apply.
      INFEROPS_TARGET_IMAGE_PREPARATION="not-established"
      ;;
  esac

  INFEROPS_TARGET_KUBECONFIG_POSIX="${INFEROPS_TARGET_KUBECONFIG_POSIX_PATH}"
  INFEROPS_TARGET_KUBECONFIG="$(inferops::native_path "${INFEROPS_TARGET_KUBECONFIG_POSIX}")"

  # client-outside-skew. Read from the target's own reported server version
  # rather than from the node-image pin the kind helper checks: the selected
  # cluster's server version is whatever the operator's provider gives it.
  local version_json server_minor client_minor
  version_json="$(inferops::target_kubectl version -o json 2>/dev/null || true)"
  INFEROPS_TARGET_SERVER_VERSION="$(printf '%s' "${version_json}" |
    awk -F'"' '/"serverVersion"/ { server = 1 } server && /"gitVersion"/ { print $4; exit }')"
  server_minor="$(printf '%s' "${version_json}" |
    awk -F'"' '/"serverVersion"/ { server = 1 } server && /"minor"/ { print $4; exit }' | tr -cd '0-9')"
  client_minor="$(kubectl version --client=true -o json 2>/dev/null |
    awk -F'"' '/"minor"/ { print $4; exit }' | tr -cd '0-9')"
  if [ -n "${server_minor}" ] && [ -n "${client_minor}" ]; then
    local skew=$((client_minor - server_minor))
    [ "${skew}" -lt 0 ] && skew=$((-skew))
    if [ "${skew}" -gt "${INFEROPS_MAX_SKEW}" ]; then
      inferops::fail "refusing: client-outside-skew: kubectl minor ${client_minor} is ${skew} minor version(s) from the target's ${server_minor}; the supported skew is ${INFEROPS_MAX_SKEW}."
    fi
  fi

  INFEROPS_TARGET_NODE_NAMES="$(inferops::target_kubectl get nodes -o name 2>/dev/null |
    sed 's|^node/||' | sort || true)"
  INFEROPS_TARGET_CONTAINER_RUNTIME="$(inferops::target_kubectl get nodes \
    -o jsonpath='{.items[0].status.nodeInfo.containerRuntimeVersion}' 2>/dev/null || true)"
  INFEROPS_TARGET_NETWORK_PLUGIN="$(inferops::target_kubectl get pods -n kube-system \
    -o jsonpath='{range .items[*]}{.spec.containers[0].image}{"\n"}{end}' 2>/dev/null |
    grep -m1 -i 'kindnetd' || true)"
  # Both supported providers' network plugin is not enforced
  # (docs/environment/local-cluster-provider-contract.md, `networkPolicyEnforcement`):
  # an inference for kind, an observation for docker-desktop, never `enforced`
  # unless an enforcement experiment on the selected provider has said so.
  INFEROPS_TARGET_NETWORK_POLICY_ENFORCEMENT="not-enforced"
  INFEROPS_TARGET_DEFAULT_STORAGE_CLASS="$(inferops::target_kubectl get storageclass \
    -o jsonpath='{range .items[?(@.metadata.annotations.storageclass\.kubernetes\.io/is-default-class=="true")]}{.metadata.name}{" "}{.provisioner}{end}' \
    2>/dev/null || true)"

  local engine_cpus engine_mem
  engine_cpus="$(docker info --format '{{.NCPU}}' 2>/dev/null || true)"
  engine_mem="$(docker info --format '{{.MemTotal}}' 2>/dev/null || true)"
  INFEROPS_TARGET_ENGINE_CAPACITY="cpus=${engine_cpus:-unknown} memoryBytes=${engine_mem:-unknown}"

  INFEROPS_TARGET_VERIFIED_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
  INFEROPS_TARGET_VERIFIED_REVISION="$(cd "${INFEROPS_ROOT}" && git rev-parse HEAD 2>/dev/null || echo unknown)"

  inferops::log "target verified: provider=${INFEROPS_TARGET_PROVIDER} cluster=${INFEROPS_TARGET_CLUSTER_NAME} context=${INFEROPS_TARGET_CONTEXT}"
}
