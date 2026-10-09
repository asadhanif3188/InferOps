#!/usr/bin/env bash
# Reads whether the selected cluster can hold the two-replica release, before
# anything is installed. It is the collector of the V2 capacity gate.
#
# Read-only: it changes nothing in the cluster and nothing in the container
# engine. It reads the nodes, every pod, the quota and limit-range objects and
# the claims of the release namespace, the server version, and the engine's
# processor count and memory. It writes what each read returned into a new
# directory under .artifacts/, and it writes the gate record beside them.
#
# The target is verified first. The declared footprint is then written, from
# committed files, before the first read that this script collects.
# tools/capacity_preflight builds the record from the directory. That tool decides. This script decides nothing, and it lowers no
# figure.
#
# A read that does not answer is not an empty result. Its file is not written,
# and the record states the read as not made. A record with a read that was not
# made is REFUSED.
#
# Exit status: 0 when the record is ACCEPTED. 5 when the record is REFUSED. 1
# when no record was written.
#
# Usage: INFEROPS_PROVIDER=<provider> scripts/environment/capacity-preflight.sh [--into NAME]
#
# See docs/environment/capacity-preflight.md.

# shellcheck source=scripts/environment/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

readonly USAGE="Usage: INFEROPS_PROVIDER=<provider> capacity-preflight.sh [--into NAME]"
readonly PREFLIGHT_MODULE="tools.capacity_preflight"
readonly COLLECTIONS_REL=".artifacts/capacity-preflight/collections"
readonly COLLECTION_SCHEMA="inferops.io/capacity-preflight-collection/v1alpha1"
readonly REFUSED_EXIT=5
readonly UNANSWERED="A query that did not answer is not an empty result. The record states this read as not made."

# --- Arguments --------------------------------------------------------------

collection_name=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --into)
      [ "$#" -ge 2 ] && [ -n "$2" ] || inferops::fail "--into needs a value. ${USAGE}"
      [ -z "${collection_name}" ] || inferops::fail "--into was given twice. ${USAGE}"
      collection_name="$2"
      shift 2
      ;;
    *)
      inferops::fail "unknown argument '$1'. ${USAGE}"
      ;;
  esac
done

if [ -z "${collection_name}" ]; then
  collection_name="$(date -u +%Y%m%dT%H%M%SZ)"
fi
case "${collection_name}" in
  *[!A-Za-z0-9._-]* | .* | "")
    inferops::fail "the name '${collection_name}' is not usable. Use letters, digits, '.', '_', and '-', and do not start with '.'. ${USAGE}"
    ;;
esac

collection_rel="${COLLECTIONS_REL}/${collection_name}"
collection_dir="${INFEROPS_ROOT}/${collection_rel}"
[ ! -e "${collection_dir}" ] ||
  inferops::fail "'${collection_rel}' already exists. A collection is one reading, and this script does not write into an earlier one. Give another name with --into."

inferops::require_cmd kubectl
inferops::require_cmd git

# --- The target -------------------------------------------------------------

inferops::resolve_target

inferops::section "Capacity preflight on ${INFEROPS_TARGET_PROVIDER}"

if ! executing_commit="$(cd "${INFEROPS_ROOT}" && git rev-parse --verify HEAD 2>/dev/null)"; then
  inferops::fail "could not read the commit of this working tree. The collection names the commit that wrote it."
fi

mkdir -p "${collection_dir}"

# --- The declared footprint, before the first collected read ----------------

if ! (cd "${INFEROPS_ROOT}" && inferops::python -m "${PREFLIGHT_MODULE}" --footprint) \
  >"${collection_dir}/footprint.json"; then
  inferops::fail "the committed files give no footprint. No read was collected. Run: python -m ${PREFLIGHT_MODULE} --footprint"
fi

footprint_fields="$(cd "${INFEROPS_ROOT}" && inferops::python -c '
import json
import sys

release = json.load(open(sys.argv[1], encoding="utf-8"))["release"]
print(release["key"])
print(release["namespace"])
' "${collection_rel}/footprint.json")"
{
  read -r release_key
  read -r release_namespace
} <<<"${footprint_fields}"
[ -n "${release_key}" ] && [ -n "${release_namespace}" ] ||
  inferops::fail "the footprint names no release or no namespace."

inferops::log "release ${release_key}, namespace ${release_namespace}"

# --- The reads --------------------------------------------------------------

# One read into one file. A read that fails leaves no file.
collect() {
  local file="$1"
  shift
  if inferops::target_kubectl "$@" -o json >"${collection_dir}/${file}" 2>/dev/null; then
    inferops::log "read ${file}"
  else
    rm -f "${collection_dir}/${file}"
    inferops::warn "'kubectl $*' did not answer. ${UNANSWERED}"
  fi
}

collect nodes.json get nodes
collect pods.json get pods --all-namespaces
collect namespace-limits.json get resourcequotas,limitranges --namespace "${release_namespace}"
collect claims.json get persistentvolumeclaims --namespace "${release_namespace}"
collect version.json version

# The engine's figures are stated in the record. No rule reads them: the node's
# allocatable figures are what the scheduler places against.
engine_cpus="$(docker info --format '{{.NCPU}}' 2>/dev/null || true)"
engine_memory="$(docker info --format '{{.MemTotal}}' 2>/dev/null || true)"
case "${engine_cpus}:${engine_memory}" in
  *[!0-9:]* | :* | *:)
    inferops::warn "the container engine did not report its processor count and its memory. The record states no engine figure."
    ;;
  *)
    printf '{"cpus": %s, "memoryBytes": %s}\n' "${engine_cpus}" "${engine_memory}" \
      >"${collection_dir}/engine.json"
    inferops::log "read engine.json"
    ;;
esac

INFEROPS_PREFLIGHT_SCHEMA="${COLLECTION_SCHEMA}" \
  INFEROPS_PREFLIGHT_PROVIDER="${INFEROPS_TARGET_PROVIDER}" \
  INFEROPS_PREFLIGHT_CONTEXT="${INFEROPS_TARGET_CONTEXT}" \
  INFEROPS_PREFLIGHT_RELEASE="${release_key}" \
  INFEROPS_PREFLIGHT_NAMESPACE="${release_namespace}" \
  INFEROPS_PREFLIGHT_COMMIT="${executing_commit}" \
  INFEROPS_PREFLIGHT_AT="$(date -u +%Y-%m-%dT%H:%M:%SZ)" \
  inferops::python -c '
import json
import os

print(
    json.dumps(
        {
            "schema": os.environ["INFEROPS_PREFLIGHT_SCHEMA"],
            "provider": os.environ["INFEROPS_PREFLIGHT_PROVIDER"],
            "context": os.environ["INFEROPS_PREFLIGHT_CONTEXT"],
            "releaseKey": os.environ["INFEROPS_PREFLIGHT_RELEASE"],
            "namespace": os.environ["INFEROPS_PREFLIGHT_NAMESPACE"],
            "executingCommit": os.environ["INFEROPS_PREFLIGHT_COMMIT"],
            "collectedAt": os.environ["INFEROPS_PREFLIGHT_AT"],
        },
        indent=2,
        sort_keys=True,
    )
)
' >"${collection_dir}/run.json"

# --- The record -------------------------------------------------------------

status=0
(cd "${INFEROPS_ROOT}" && inferops::python -m "${PREFLIGHT_MODULE}" "${collection_rel}") \
  >"${collection_dir}/record.v1alpha1.json" || status=$?

case "${status}" in
  0 | "${REFUSED_EXIT}") ;;
  *)
    rm -f "${collection_dir}/record.v1alpha1.json"
    inferops::fail "the tool wrote no record for '${collection_rel}' (exit ${status}). The reads are kept in that directory."
    ;;
esac

(cd "${INFEROPS_ROOT}" && inferops::python -c '
import json
import sys

record = json.load(open(sys.argv[1], encoding="utf-8"))
for finding in record["findings"]:
    print("{:<13} {}: {}".format(finding["state"], finding["ruleId"], finding["detail"]))
print("result: " + record["result"])
' "${collection_rel}/record.v1alpha1.json") | sed 's/^/[inferops] /'

inferops::log "the collection and its record are in ${collection_rel}"

if [ "${status}" -eq "${REFUSED_EXIT}" ]; then
  inferops::warn "the cluster is REFUSED for this release. Nothing was installed, and no figure was lowered. The refusal is a result: keep the directory."
  exit "${REFUSED_EXIT}"
fi

inferops::log "the cluster is ACCEPTED for this release. This is one reading of stated figures. It does not establish that a pod starts."
