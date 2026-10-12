#!/usr/bin/env bash
# Asks the telemetry collector of the release a registered set of instant
# queries a bounded number of times, for one experiment run. It is the collector
# script of the telemetry streams.
#
# It changes nothing in the cluster. Each sample makes one read of the Service
# of the telemetry collector, and one read for each registered query. A query
# read is an HTTP GET of the query API of the collector, through the Service
# proxy of the API server. Each kubectl call that this script holds is a `get`.
# The target verification of the library runs first and makes reads of its own:
# `config`, `version`, and `get` of the nodes, of the system pods, and of the
# storage classes. The script sends no request to the API of the release and no
# request to the serving runtime.
#
# The queries are not written here. tools/experiment_telemetry registers them,
# and this script asks that tool for the request of each one. The script holds
# each request to a fixed form before it uses it.
#
# It writes what each read returned into a new directory under .artifacts/. The
# target verification writes the target's kubeconfig under .kube/, as it does
# for every platform workflow.
#
# tools/experiment_telemetry builds two streams from the directory: telemetry
# and resources. That tool reads the answers. This script reads none of them,
# and it judges no state.
#
# A read that does not answer is not an empty result. Its file is not written,
# the sample states the read as unanswered, and the streams state no result for
# it. A release with no telemetry collector answers no query: the streams then
# state each read as absent. That is not a value of zero.
#
# Each read has two instants: when it started and when it finished. Both are
# this host's wall clock, in UTC, to one millisecond. They are not the clock of
# the telemetry collector. The interval is the pause between two samples. It is
# not a period: a sample takes the time of its reads.
#
# The directory holds the whole answer of each read. The answer of the Service
# read holds an address. Do not commit the directory. The streams hold an
# allowlist, and they are the evidence files.
#
# Exit status: 0 when every sample was taken and the two streams were written.
# 1 when the script stopped before that: it refused its arguments or its
# target, the tool gave no usable request, or the tool gave no stream for a
# collection that is kept. Status 0 does not say that a read answered, that a
# target was scraped, or that a counter had any value.
#
# Usage: INFEROPS_PROVIDER=<provider> scripts/environment/experiment-telemetry.sh \
#          --experiment ID --run ID --samples COUNT --interval SECONDS [--into NAME]
#
# See docs/environment/experiment-telemetry.md.

# shellcheck source=scripts/environment/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

readonly USAGE="Usage: INFEROPS_PROVIDER=<provider> experiment-telemetry.sh --experiment ID --run ID --samples COUNT --interval SECONDS [--into NAME]"
readonly TELEMETRY_MODULE="tools.experiment_telemetry"
readonly COLLECTIONS_REL=".artifacts/experiment-telemetry/collections"
readonly COLLECTION_SCHEMA="inferops.io/experiment-telemetry-collection/v1alpha1"
readonly STREAM_NAMES="telemetry resources"
readonly MAX_SAMPLES=720
readonly MIN_INTERVAL_SECONDS=5
readonly MAX_INTERVAL_SECONDS=120
readonly REQUEST_TIMEOUT_SECONDS=10
# The Service of the telemetry collector that the chart installs, and the name
# of its port. A test compares the name with the collection verification.
readonly COLLECTOR_SERVICE="${INFEROPS_RELEASE_NAME}-inferops-llm-collector"
readonly COLLECTOR_PORT="http"
readonly PROXY_PATH="/api/v1/namespaces/${INFEROPS_RELEASE_NAMESPACE}/services/${COLLECTOR_SERVICE}:${COLLECTOR_PORT}/proxy"
readonly INSTANT_FORMAT="+%Y-%m-%dT%H:%M:%S.%3NZ"
readonly UNANSWERED="A read that did not answer is not an empty result. The streams state no result for this read."

# --- Arguments --------------------------------------------------------------

experiment_id=""
run_id=""
samples=""
interval=""
collection_name=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --experiment | --run | --samples | --interval | --into)
      [ "$#" -ge 2 ] && [ -n "$2" ] || inferops::fail "$1 needs a value. ${USAGE}"
      case "$1" in
        --experiment)
          [ -z "${experiment_id}" ] || inferops::fail "--experiment was given twice. ${USAGE}"
          experiment_id="$2"
          ;;
        --run)
          [ -z "${run_id}" ] || inferops::fail "--run was given twice. ${USAGE}"
          run_id="$2"
          ;;
        --samples)
          [ -z "${samples}" ] || inferops::fail "--samples was given twice. ${USAGE}"
          samples="$2"
          ;;
        --interval)
          [ -z "${interval}" ] || inferops::fail "--interval was given twice. ${USAGE}"
          interval="$2"
          ;;
        --into)
          [ -z "${collection_name}" ] || inferops::fail "--into was given twice. ${USAGE}"
          collection_name="$2"
          ;;
      esac
      shift 2
      ;;
    *)
      inferops::fail "unknown argument '$1'. ${USAGE}"
      ;;
  esac
done

[[ "${experiment_id}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$ ]] ||
  inferops::fail "--experiment needs an experiment identifier: 1 to 63 letters, digits, '.', '_', and '-', with a letter or a digit first. Nothing was read. ${USAGE}"
[[ "${run_id}" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,62}$ ]] ||
  inferops::fail "--run needs a run identifier: 1 to 63 letters, digits, '.', '_', and '-', with a letter or a digit first. Nothing was read. ${USAGE}"
[[ "${samples}" =~ ^[1-9][0-9]{0,2}$ ]] && [ "${samples}" -le "${MAX_SAMPLES}" ] ||
  inferops::fail "--samples needs a whole number from 1 to ${MAX_SAMPLES}. A collection is bounded. Nothing was read. ${USAGE}"
[[ "${interval}" =~ ^[1-9][0-9]{0,2}$ ]] && [ "${interval}" -ge "${MIN_INTERVAL_SECONDS}" ] && [ "${interval}" -le "${MAX_INTERVAL_SECONDS}" ] ||
  inferops::fail "--interval needs a whole number of seconds from ${MIN_INTERVAL_SECONDS} to ${MAX_INTERVAL_SECONDS}. Nothing was read. ${USAGE}"

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
  inferops::fail "'${collection_rel}' already exists. A collection is one run of this script, and the script does not write into an earlier one. Give another name with --into."

inferops::require_cmd kubectl
inferops::require_cmd git
inferops::require_cmd sha256sum

# One instant, on this host's wall clock, in UTC, to one millisecond.
instant() {
  date -u "${INSTANT_FORMAT}"
}

# A `date` that does not give milliseconds prints the format letters instead.
[[ "$(instant)" =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\.[0-9]{3}Z$ ]] ||
  inferops::fail "the 'date' of this host does not state an instant to one millisecond. The streams need that form. Nothing was read."

# --- The registered requests ------------------------------------------------

# The tool registers the queries. Each line that it prints is held to a fixed
# form here, so no other text reaches a kubectl call.
if ! requests="$(cd "${INFEROPS_ROOT}" && inferops::python -m "${TELEMETRY_MODULE}" requests)"; then
  inferops::fail "the tool gave no registered request. Nothing was read."
fi
query_set=""
query_set_sha256=""
query_names=()
query_paths=()
while IFS=' ' read -r kind first second extra; do
  [ -n "${kind}" ] || continue
  [ -z "${extra}" ] ||
    inferops::fail "the tool printed a request line with more than three words. Nothing was read."
  case "${kind}" in
    query-set)
      [[ "${first}" =~ ^[a-z0-9][a-z0-9-]{0,62}$ ]] && [[ "${second}" =~ ^[0-9a-f]{64}$ ]] && [ -z "${query_set}" ] ||
        inferops::fail "the tool printed a query set that is not a name and a SHA-256, or it printed two. Nothing was read."
      query_set="${first}"
      query_set_sha256="${second}"
      ;;
    query)
      [[ "${first}" =~ ^[a-z][a-z0-9-]{0,62}$ ]] && [[ "${second}" =~ ^api/v1/query\?query=[A-Za-z0-9%._~-]+$ ]] && [ "${#second}" -le 512 ] ||
        inferops::fail "the tool printed a request that is not a query name and an encoded instant query. Nothing was read."
      query_names+=("${first}")
      query_paths+=("${second}")
      ;;
    *)
      inferops::fail "the tool printed a request line of an unknown kind. Nothing was read."
      ;;
  esac
done <<<"${requests}"
[ -n "${query_set}" ] && [ "${#query_names[@]}" -ge 1 ] && [ "${#query_names[@]}" -le 32 ] ||
  inferops::fail "the tool printed no query set, no query, or more than 32 queries. Nothing was read."

# --- The target -------------------------------------------------------------

inferops::resolve_target

inferops::section "Experiment telemetry on ${INFEROPS_TARGET_PROVIDER}"

if ! executing_commit="$(cd "${INFEROPS_ROOT}" && git rev-parse --verify HEAD 2>/dev/null)"; then
  inferops::fail "could not read the commit of this working tree. The collection names the commit that wrote it."
fi
procedure_sha256="$(sha256sum "${BASH_SOURCE[0]}" | awk '{ print $1 }')"
library_sha256="$(sha256sum "$(dirname "${BASH_SOURCE[0]}")/lib.sh" | awk '{ print $1 }')"

mkdir -p "$(dirname "${collection_dir}")"
mkdir "${collection_dir}" ||
  inferops::fail "'${collection_rel}' was created while this script started. Give another name with --into. No sample was taken."

# The header names the provider and not the kubeconfig context. A context name
# can hold an account identifier.
INFEROPS_TELEMETRY_SCHEMA="${COLLECTION_SCHEMA}" \
  INFEROPS_TELEMETRY_EXPERIMENT="${experiment_id}" \
  INFEROPS_TELEMETRY_RUN="${run_id}" \
  INFEROPS_TELEMETRY_PROVIDER="${INFEROPS_TARGET_PROVIDER}" \
  INFEROPS_TELEMETRY_SERVER_VERSION="${INFEROPS_TARGET_SERVER_VERSION:-}" \
  INFEROPS_TELEMETRY_NAMESPACE="${INFEROPS_RELEASE_NAMESPACE}" \
  INFEROPS_TELEMETRY_RELEASE="${INFEROPS_RELEASE_NAME}" \
  INFEROPS_TELEMETRY_COLLECTOR_SERVICE="${COLLECTOR_SERVICE}" \
  INFEROPS_TELEMETRY_COLLECTOR_PORT="${COLLECTOR_PORT}" \
  INFEROPS_TELEMETRY_QUERY_SET="${query_set}" \
  INFEROPS_TELEMETRY_QUERY_SET_SHA256="${query_set_sha256}" \
  INFEROPS_TELEMETRY_COMMIT="${executing_commit}" \
  INFEROPS_TELEMETRY_PROCEDURE_SHA256="${procedure_sha256}" \
  INFEROPS_TELEMETRY_LIBRARY_SHA256="${library_sha256}" \
  INFEROPS_TELEMETRY_SAMPLES="${samples}" \
  INFEROPS_TELEMETRY_INTERVAL="${interval}" \
  INFEROPS_TELEMETRY_REQUEST_TIMEOUT="${REQUEST_TIMEOUT_SECONDS}" \
  inferops::python -c '
import json
import os

print(
    json.dumps(
        {
            "schema": os.environ["INFEROPS_TELEMETRY_SCHEMA"],
            "experimentId": os.environ["INFEROPS_TELEMETRY_EXPERIMENT"],
            "runId": os.environ["INFEROPS_TELEMETRY_RUN"],
            "provider": os.environ["INFEROPS_TELEMETRY_PROVIDER"],
            "serverVersion": os.environ["INFEROPS_TELEMETRY_SERVER_VERSION"],
            "namespace": os.environ["INFEROPS_TELEMETRY_NAMESPACE"],
            "release": os.environ["INFEROPS_TELEMETRY_RELEASE"],
            "collectorService": os.environ["INFEROPS_TELEMETRY_COLLECTOR_SERVICE"],
            "collectorPort": os.environ["INFEROPS_TELEMETRY_COLLECTOR_PORT"],
            "querySet": os.environ["INFEROPS_TELEMETRY_QUERY_SET"],
            "querySetSha256": os.environ["INFEROPS_TELEMETRY_QUERY_SET_SHA256"],
            "executingCommit": os.environ["INFEROPS_TELEMETRY_COMMIT"],
            "procedureSha256": os.environ["INFEROPS_TELEMETRY_PROCEDURE_SHA256"],
            "librarySha256": os.environ["INFEROPS_TELEMETRY_LIBRARY_SHA256"],
            "requestedSamples": int(os.environ["INFEROPS_TELEMETRY_SAMPLES"]),
            "intervalSeconds": int(os.environ["INFEROPS_TELEMETRY_INTERVAL"]),
            "requestTimeoutSeconds": int(os.environ["INFEROPS_TELEMETRY_REQUEST_TIMEOUT"]),
        },
        indent=2,
        sort_keys=True,
    )
)
' >"${collection_dir}/collection.json"

inferops::log "experiment ${experiment_id}, run ${run_id}"
inferops::log "release ${INFEROPS_RELEASE_NAME}, namespace ${INFEROPS_RELEASE_NAMESPACE}, collector Service ${COLLECTOR_SERVICE}"
inferops::log "query set ${query_set}: ${#query_names[@]} queries"
inferops::log "samples: ${samples}, with a pause of ${interval}s between two, into ${collection_rel}"

# --- The samples ------------------------------------------------------------

# One read into one file. A read that fails leaves no file.
collect() {
  local file="$1"
  shift
  if inferops::target_kubectl get "$@" --request-timeout "${REQUEST_TIMEOUT_SECONDS}s" >"${file}" 2>/dev/null; then
    return 0
  fi
  rm -f "${file}"
  return 1
}

incomplete=0
for ((index = 1; index <= samples; index++)); do
  stem="${collection_dir}/$(printf 'sample-%04d' "${index}")"

  # An absent Service answers with no output. It is an answer.
  collector_read="answered"
  collector_started_at="$(instant)"
  collect "${stem}.collector.json" service "${COLLECTOR_SERVICE}" --namespace "${INFEROPS_RELEASE_NAMESPACE}" --ignore-not-found -o json ||
    collector_read="unanswered"
  collector_finished_at="$(instant)"
  meta="$(printf 'collectorRead=%s\ncollectorStartedAt=%s\ncollectorFinishedAt=%s' \
    "${collector_read}" "${collector_started_at}" "${collector_finished_at}")"

  answered=0
  for position in "${!query_names[@]}"; do
    name="${query_names[${position}]}"
    query_read="answered"
    query_started_at="$(instant)"
    if collect "${stem}.query.${name}.json" --raw "${PROXY_PATH}/${query_paths[${position}]}"; then
      answered=$((answered + 1))
    else
      query_read="unanswered"
    fi
    query_finished_at="$(instant)"
    meta="$(printf '%s\nquery.%s.read=%s\nquery.%s.startedAt=%s\nquery.%s.finishedAt=%s' \
      "${meta}" "${name}" "${query_read}" "${name}" "${query_started_at}" "${name}" "${query_finished_at}")"
  done
  # The status file is written last, so a sample that was interrupted has none.
  printf '%s\n' "${meta}" >"${stem}.meta"

  if [ "${collector_read}" != "answered" ] || [ "${answered}" -ne "${#query_names[@]}" ]; then
    incomplete=$((incomplete + 1))
    inferops::warn "sample ${index} of ${samples} at ${collector_started_at}: Service read ${collector_read}, ${answered} of ${#query_names[@]} queries answered. ${UNANSWERED}"
  else
    inferops::log "sample ${index} of ${samples} at ${collector_started_at}: Service read ${collector_read}, ${answered} of ${#query_names[@]} queries answered"
  fi
  [ "${index}" -ge "${samples}" ] || sleep "${interval}"
done
printf 'completedSamples=%s\n' "${samples}" >"${collection_dir}/collection.end"

# --- The streams ------------------------------------------------------------

mkdir "${collection_dir}/streams"
stream_files=()
for name in ${STREAM_NAMES}; do
  status=0
  (cd "${INFEROPS_ROOT}" && inferops::python -m "${TELEMETRY_MODULE}" stream "${collection_rel}" "${name}") \
    >"${collection_dir}/streams/${name}.jsonl" || status=$?
  if [ "${status}" -ne 0 ]; then
    rm -f "${collection_dir}/streams/${name}.jsonl"
    inferops::fail "the tool wrote no ${name} stream for '${collection_rel}' (exit ${status}). The reads are kept in that directory."
  fi
  stream_files+=("${collection_rel}/streams/${name}.jsonl")
done

(cd "${INFEROPS_ROOT}" && inferops::python -m "${TELEMETRY_MODULE}" check "${stream_files[@]}") | sed 's/^/[inferops] /' ||
  inferops::fail "the tool refused a stream that it wrote for '${collection_rel}'. The reads are kept in that directory."

inferops::section "Result"
inferops::log "${samples} sample(s) were taken, and the two streams are in ${collection_rel}/streams. This script judged none of them."
if [ "${incomplete}" -gt 0 ]; then
  inferops::warn "${incomplete} sample(s) hold a read that did not answer. Such a read gave no result. It is not a value of zero, and it is not a healthy state."
fi
inferops::log "The streams state what the telemetry collector stored. They are not a request that a caller sent."
inferops::log "An answer with no series is not a value of zero. The streams state it as no-series."
inferops::log "The directory holds the whole answer of each read. Do not commit it. The two files under streams/ are the evidence files."
