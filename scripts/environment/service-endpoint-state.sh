#!/usr/bin/env bash
# Reads the Ready endpoint state of the API Service and the serving runtime
# Service of the release, once. It is the collector of the endpoint-state
# record.
#
# It changes nothing in the cluster. It reads the Services of the release and
# the EndpointSlices of the release namespace. It writes what each read returned
# into a new directory under .artifacts/, and it writes the record beside them.
# The target verification writes the target's kubeconfig under .kube/, as it
# does for every platform workflow.
#
# tools/service_endpoint_state builds the record from the directory. That tool
# counts. This script counts nothing, and it sends no request to the release.
#
# A read that does not answer is not an empty result. Its file is not written,
# and the record states the read as not made. A record with a read that was not
# made is REFUSED. It does not state zero endpoints.
#
# One run is one reading. It is not a timeline. The two reads are two calls, and
# the two instants are this host's clock, to one second.
#
# Exit status: 0 when the record is OBSERVED. 5 when the record is REFUSED. 1
# when no record was written. Status 0 does not say that a Service has a Ready
# endpoint: a record with zero Ready endpoints is OBSERVED.
#
# Usage: INFEROPS_PROVIDER=<provider> scripts/environment/service-endpoint-state.sh [--into NAME]
#
# See docs/environment/service-endpoint-state.md.

# shellcheck source=scripts/environment/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

readonly USAGE="Usage: INFEROPS_PROVIDER=<provider> service-endpoint-state.sh [--into NAME]"
readonly STATE_MODULE="tools.service_endpoint_state"
readonly COLLECTIONS_REL=".artifacts/service-endpoint-state/collections"
readonly COLLECTION_SCHEMA="inferops.io/service-endpoint-state-collection/v1alpha1"
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

inferops::section "Service endpoint state on ${INFEROPS_TARGET_PROVIDER}"

if ! executing_commit="$(cd "${INFEROPS_ROOT}" && git rev-parse --verify HEAD 2>/dev/null)"; then
  inferops::fail "could not read the commit of this working tree. The collection names the commit that wrote it."
fi

mkdir -p "${collection_dir}"

inferops::log "release ${INFEROPS_RELEASE_NAME}, namespace ${INFEROPS_RELEASE_NAMESPACE}"

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

read_started_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"
collect services.json get services --namespace "${INFEROPS_RELEASE_NAMESPACE}" --selector "${INFEROPS_RELEASE_SELECTOR}"
collect endpointslices.json get endpointslices.discovery.k8s.io --namespace "${INFEROPS_RELEASE_NAMESPACE}"
read_finished_at="$(date -u +%Y-%m-%dT%H:%M:%SZ)"

# The header names the provider and not the kubeconfig context. A context name
# can hold an account identifier.
INFEROPS_STATE_SCHEMA="${COLLECTION_SCHEMA}" \
  INFEROPS_STATE_PROVIDER="${INFEROPS_TARGET_PROVIDER}" \
  INFEROPS_STATE_RELEASE="${INFEROPS_RELEASE_NAME}" \
  INFEROPS_STATE_NAMESPACE="${INFEROPS_RELEASE_NAMESPACE}" \
  INFEROPS_STATE_COMMIT="${executing_commit}" \
  INFEROPS_STATE_STARTED="${read_started_at}" \
  INFEROPS_STATE_FINISHED="${read_finished_at}" \
  inferops::python -c '
import json
import os

print(
    json.dumps(
        {
            "schema": os.environ["INFEROPS_STATE_SCHEMA"],
            "provider": os.environ["INFEROPS_STATE_PROVIDER"],
            "release": os.environ["INFEROPS_STATE_RELEASE"],
            "namespace": os.environ["INFEROPS_STATE_NAMESPACE"],
            "executingCommit": os.environ["INFEROPS_STATE_COMMIT"],
            "readStartedAt": os.environ["INFEROPS_STATE_STARTED"],
            "readFinishedAt": os.environ["INFEROPS_STATE_FINISHED"],
        },
        indent=2,
        sort_keys=True,
    )
)
' >"${collection_dir}/run.json"

# --- The record -------------------------------------------------------------

status=0
(cd "${INFEROPS_ROOT}" && inferops::python -m "${STATE_MODULE}" "${collection_rel}") \
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
for tier in record["tiers"]:
    figures = tier["endpoints"]
    if figures is None:
        print("{:<16} {}: no figure is stated".format(tier["tier"], tier["state"]))
    else:
        print(
            "{:<16} {}: {} Ready of {} endpoint(s), {} terminating".format(
                tier["tier"],
                tier["state"],
                figures["ready"],
                figures["total"],
                figures["terminating"],
            )
        )
for finding in record["findings"]:
    if finding["state"] != "held":
        print("{:<13} {}: {}".format(finding["state"], finding["ruleId"], finding["detail"]))
print("result: " + record["result"])
' "${collection_rel}/record.v1alpha1.json") | sed 's/^/[inferops] /'

inferops::log "the collection and its record are in ${collection_rel}"

if [ "${status}" -eq "${REFUSED_EXIT}" ]; then
  inferops::warn "the reading is REFUSED. It states no endpoint count for a tier that a rule refuses. The refusal is a result: keep the directory."
  exit "${REFUSED_EXIT}"
fi

inferops::log "the reading is OBSERVED. It is one reading of what the cluster published. It is not a request that a caller sent."
