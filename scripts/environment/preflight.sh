#!/usr/bin/env bash
# Checks that this host can host the InferOps development cluster, and records
# what it found. Read-only: it installs nothing, starts nothing, and changes no
# host or engine setting.
#
# Usage: scripts/environment/preflight.sh

# shellcheck source=scripts/environment/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

# This script takes no options, so an argument is a contributor expecting
# something it will not do. Accepting it silently would report "all prerequisite
# checks passed" for a run that ignored what was asked of it.
[ "$#" -eq 0 ] ||
  inferops::fail "expected no arguments, got $#: $*. Usage: preflight.sh"

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
    inferops::log "engine memory: $(inferops::gib "${engine_mem}") (${engine_mem} bytes)"

    # This is the binding constraint on Windows and macOS: the VM's allocation,
    # not the host's installed memory.
    if [ "${engine_mem}" -lt "${INFEROPS_MIN_ENGINE_MEM_BYTES}" ]; then
      note_failure "engine memory is $(inferops::gib "${engine_mem}"), below the $(inferops::gib "${INFEROPS_MIN_ENGINE_MEM_BYTES}") minimum tier; raise the container VM allocation."
    fi
    if [ "${engine_cpus}" -lt "${INFEROPS_MIN_ENGINE_CPUS}" ]; then
      note_failure "engine sees ${engine_cpus} CPUs; the minimum tier is ${INFEROPS_MIN_ENGINE_CPUS}."
    fi
  else
    note_failure "the container engine is not reachable. Start it and retry."
  fi
fi

inferops::section "Disk"

# The third figure in D7's minimum tier, and the one that was never checked until
# V1-S3-001. It is not a static requirement met once: ADR 0001 (R11) records that
# a teardown does not return host free space, so a host that had room last month
# is not evidence that it has room now.
# The kind first and the path last, so that a path containing a space arrives
# whole rather than truncated at the first one.
read -r disk_kind disk_path <<<"$(inferops::disk_probe_target)"

if free_bytes="$(inferops::free_disk_bytes "${disk_path}")"; then
  inferops::log "measuring ${disk_path} (${disk_kind})"
  inferops::log "free space: $(inferops::gb "${free_bytes}") (${free_bytes} bytes)"

  case "${disk_kind}" in
    host-volume)
      # Said aloud every time, not only on failure. A figure whose meaning
      # depends on the platform has to carry that meaning with it, or the next
      # reader will take a proxy for a measurement of the engine's own storage.
      inferops::log "the engine's data root is not visible on this host's filesystem, so this is the volume its virtual disk sits on by default rather than the engine's own storage. Set INFEROPS_DISK_VOLUME if you have relocated it."
      ;;
  esac

  if [ "${free_bytes}" -lt "${INFEROPS_MIN_FREE_DISK_BYTES}" ]; then
    note_failure "free space on ${disk_path} is $(inferops::gb "${free_bytes}"), below the $(inferops::gb "${INFEROPS_MIN_FREE_DISK_BYTES}") minimum tier. The cluster costs roughly 1.1 GB while it exists and the node image a further 1.35 GB, and neither figure is the whole of what a serving path will need."
  fi
else
  # Not measured is not the same as not enough. Reporting it as a failure would
  # block a host that is fine on a volume this script could not read.
  inferops::warn "could not read free space on ${disk_path} (${disk_kind}); the $(inferops::gb "${INFEROPS_MIN_FREE_DISK_BYTES}") minimum tier was not checked."
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
  # `kubectl version` accepts only yaml and json, not jsonpath, so the value is
  # read out of the JSON. awk splitting on the quote character is indifferent to
  # how the document is indented; `exit` takes the first match, which is the
  # client's, and avoids a truncated pipe. `tr -cd` tolerates the vendor '34+'
  # form. `|| true` so that a kubectl which cannot report its version produces
  # the diagnosis below rather than aborting the script under errexit.
  client_minor="$(kubectl version --client=true -o json 2>/dev/null |
    awk -F'"' '/"minor"/ { print $4; exit }' | tr -cd '0-9' || true)"
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
