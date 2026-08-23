#!/usr/bin/env bash
# Checks that this host can host the InferOps development cluster, and records
# what it found. Read-only: it installs nothing, starts nothing, and changes no
# host or engine setting.
#
# Usage: scripts/environment/preflight.sh

# shellcheck source=scripts/environment/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

failures=0
note_failure() {
  inferops::warn "$1"
  failures=$((failures + 1))
}

inferops::section "Tooling"

for cmd in docker kind kubectl; do
  if command -v "${cmd}" >/dev/null 2>&1; then
    inferops::log "${cmd}: present at $(command -v "${cmd}")"
  else
    note_failure "${cmd} is not on PATH."
  fi
done

if command -v kind >/dev/null 2>&1; then
  kind_version="$(kind version -q 2>/dev/null || true)"
  inferops::log "kind version: ${kind_version:-unknown} (pinned: ${INFEROPS_KIND_VERSION})"
  # A mismatch is reported, not enforced: another release may well work, and the
  # scripts should say what is unverified rather than refuse it outright.
  if [ "v${kind_version#v}" != "${INFEROPS_KIND_VERSION}" ]; then
    inferops::warn "kind ${kind_version:-unknown} differs from the pinned ${INFEROPS_KIND_VERSION}; results are unverified on it."
  fi
fi

inferops::section "Container engine"

if command -v docker >/dev/null 2>&1; then
  if server_version="$(docker version --format '{{.Server.Version}}' 2>/dev/null)"; then
    inferops::log "engine reachable; server version ${server_version}"
    inferops::log "engine API version: $(docker version --format '{{.Server.APIVersion}}')"
    inferops::log "engine platform: $(docker version --format '{{.Server.Os}}/{{.Server.Arch}}')"
    inferops::log "storage driver: $(docker info --format '{{.Driver}}')"
    inferops::log "cgroup version: $(docker info --format '{{.CgroupVersion}}')"
    inferops::log "kernel: $(docker info --format '{{.KernelVersion}}')"

    engine_cpus="$(docker info --format '{{.NCPU}}')"
    engine_mem="$(docker info --format '{{.MemTotal}}')"
    inferops::log "engine CPUs: ${engine_cpus}"
    inferops::log "engine memory: $(awk -v b="${engine_mem}" 'BEGIN { printf "%.2f GiB", b/1024/1024/1024 }') (${engine_mem} bytes)"

    # This is the binding constraint on Windows and macOS: the VM's allocation,
    # not the host's installed memory.
    if [ "${engine_mem}" -lt "${INFEROPS_MIN_ENGINE_MEM_BYTES}" ]; then
      note_failure "engine memory is below the $(awk -v b="${INFEROPS_MIN_ENGINE_MEM_BYTES}" 'BEGIN { printf "%.0f GiB", b/1024/1024/1024 }') minimum tier; raise the container VM allocation."
    fi
    if [ "${engine_cpus}" -lt 4 ]; then
      note_failure "engine sees ${engine_cpus} CPUs; the minimum tier is 4."
    fi
  else
    note_failure "the container engine is not reachable. Start it and retry."
  fi
fi

inferops::section "Cluster state"

if command -v kind >/dev/null 2>&1 && command -v docker >/dev/null 2>&1 &&
  docker version --format '{{.Server.Version}}' >/dev/null 2>&1; then
  if inferops::cluster_exists; then
    inferops::log "cluster '${INFEROPS_CLUSTER_NAME}' already exists."
  else
    inferops::log "cluster '${INFEROPS_CLUSTER_NAME}' does not exist yet."
  fi

  # ADR 0001 (D5) names this as a prerequisite the contributor performs
  # knowingly: the desktop application's own cluster competes for the same VM's
  # memory and binds the same local port.
  if docker ps --format '{{.Names}}' 2>/dev/null | grep -q '^k8s_'; then
    inferops::warn "containers from another Kubernetes installation are running; disable it before creating '${INFEROPS_CLUSTER_NAME}'."
  fi
fi

inferops::section "Client version skew"

if command -v kubectl >/dev/null 2>&1; then
  client_minor="$(kubectl version --client=true -o json 2>/dev/null |
    tr -d ' "' | grep -E '^minor:' | cut -d: -f2 | tr -cd '0-9')"
  if [ -n "${client_minor}" ]; then
    skew=$((client_minor - INFEROPS_SERVER_MINOR))
    [ "${skew}" -lt 0 ] && skew=$((-skew))
    inferops::log "kubectl minor ${client_minor} against node image minor ${INFEROPS_SERVER_MINOR}; skew ${skew}"
    if [ "${skew}" -gt "${INFEROPS_MAX_SKEW}" ]; then
      note_failure "kubectl is ${skew} minor versions from the pinned node image; the supported skew is ${INFEROPS_MAX_SKEW}."
    fi
  else
    inferops::warn "could not parse the kubectl client version; skew not checked."
  fi
fi

inferops::section "Result"

if [ "${failures}" -gt 0 ]; then
  inferops::fail "${failures} prerequisite check(s) failed. Nothing was changed."
fi

inferops::log "all prerequisite checks passed."
