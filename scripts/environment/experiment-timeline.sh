#!/usr/bin/env bash
# Samples the infrastructure state of the release a bounded number of times, for
# one experiment run. It is the collector of the timeline streams.
#
# It changes nothing in the cluster. Each sample makes two reads. The workload
# read asks for the Services, the EndpointSlices, the pods, the ReplicaSets, and
# the Deployments of the release namespace in one call. The Application read
# asks for the one Application that delivers the release. Each kubectl call is a
# `get`. The script sends no request to the release.
#
# It writes what each read returned into a new directory under .artifacts/. The
# target verification writes the target's kubeconfig under .kube/, as it does
# for every platform workflow.
#
# tools/experiment_timeline builds four streams from the directory: endpoints,
# pods, deployments, and argo. That tool reads the answers. This script reads
# none of them, and it judges no state.
#
# A read that does not answer is not an empty result. Its file is not written,
# the sample states the read as unanswered, and the streams state no value for
# it. A read that does not answer within the read timeout is unanswered.
#
# Each read has two instants: when it started and when it finished. Both are
# this host's wall clock, in UTC, to one millisecond. They are not a clock of
# the cluster. The interval is the pause between two samples. It is not a
# period: a sample takes the time of its two reads.
#
# The directory holds the whole answer of each read. An answer holds addresses,
# node names, and the environment of each pod. Do not commit the directory. The
# streams hold an allowlist, and they are the evidence files.
#
# Exit status: 0 when every sample was taken and the four streams were written.
# 1 otherwise. Status 0 does not say that a read answered, that an endpoint was
# Ready, or that a state was healthy.
#
# Usage: INFEROPS_PROVIDER=<provider> scripts/environment/experiment-timeline.sh \
#          --experiment ID --run ID --samples COUNT --interval SECONDS [--into NAME]
#
# See docs/environment/experiment-timelines.md.

# shellcheck source=scripts/environment/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

readonly USAGE="Usage: INFEROPS_PROVIDER=<provider> experiment-timeline.sh --experiment ID --run ID --samples COUNT --interval SECONDS [--into NAME]"
readonly TIMELINE_MODULE="tools.experiment_timeline"
readonly COLLECTIONS_REL=".artifacts/experiment-timeline/collections"
readonly COLLECTION_SCHEMA="inferops.io/experiment-timeline-collection/v1alpha1"
readonly STREAM_NAMES="endpoints pods deployments argo"
readonly MAX_SAMPLES=1800
readonly MAX_INTERVAL_SECONDS=30
readonly READ_TIMEOUT_SECONDS=10
readonly WORKLOAD_KINDS="services,endpointslices.discovery.k8s.io,pods,replicasets.apps,deployments.apps"
# The Application that delivers the release, as the Application procedure names
# it. A test compares the three values with that procedure.
readonly APPLICATION_KIND="applications.argoproj.io"
readonly APPLICATION_NAME="local-docker-desktop-support-assistant"
readonly APPLICATION_NAMESPACE="argocd"
readonly INSTANT_FORMAT="+%Y-%m-%dT%H:%M:%S.%3NZ"
readonly UNANSWERED="A query that did not answer is not an empty result. The streams state no value for this read."

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
[[ "${samples}" =~ ^[1-9][0-9]{0,3}$ ]] && [ "${samples}" -le "${MAX_SAMPLES}" ] ||
  inferops::fail "--samples needs a whole number from 1 to ${MAX_SAMPLES}. A collection is bounded. Nothing was read. ${USAGE}"
[[ "${interval}" =~ ^[1-9][0-9]?$ ]] && [ "${interval}" -le "${MAX_INTERVAL_SECONDS}" ] ||
  inferops::fail "--interval needs a whole number of seconds from 1 to ${MAX_INTERVAL_SECONDS}. Nothing was read. ${USAGE}"

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

# --- The target -------------------------------------------------------------

inferops::resolve_target

inferops::section "Experiment timeline on ${INFEROPS_TARGET_PROVIDER}"

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
INFEROPS_TIMELINE_SCHEMA="${COLLECTION_SCHEMA}" \
  INFEROPS_TIMELINE_EXPERIMENT="${experiment_id}" \
  INFEROPS_TIMELINE_RUN="${run_id}" \
  INFEROPS_TIMELINE_PROVIDER="${INFEROPS_TARGET_PROVIDER}" \
  INFEROPS_TIMELINE_SERVER_VERSION="${INFEROPS_TARGET_SERVER_VERSION:-}" \
  INFEROPS_TIMELINE_NAMESPACE="${INFEROPS_RELEASE_NAMESPACE}" \
  INFEROPS_TIMELINE_RELEASE="${INFEROPS_RELEASE_NAME}" \
  INFEROPS_TIMELINE_APPLICATION="${APPLICATION_NAME}" \
  INFEROPS_TIMELINE_APPLICATION_NAMESPACE="${APPLICATION_NAMESPACE}" \
  INFEROPS_TIMELINE_COMMIT="${executing_commit}" \
  INFEROPS_TIMELINE_PROCEDURE_SHA256="${procedure_sha256}" \
  INFEROPS_TIMELINE_LIBRARY_SHA256="${library_sha256}" \
  INFEROPS_TIMELINE_SAMPLES="${samples}" \
  INFEROPS_TIMELINE_INTERVAL="${interval}" \
  INFEROPS_TIMELINE_READ_TIMEOUT="${READ_TIMEOUT_SECONDS}" \
  inferops::python -c '
import json
import os

print(
    json.dumps(
        {
            "schema": os.environ["INFEROPS_TIMELINE_SCHEMA"],
            "experimentId": os.environ["INFEROPS_TIMELINE_EXPERIMENT"],
            "runId": os.environ["INFEROPS_TIMELINE_RUN"],
            "provider": os.environ["INFEROPS_TIMELINE_PROVIDER"],
            "serverVersion": os.environ["INFEROPS_TIMELINE_SERVER_VERSION"],
            "namespace": os.environ["INFEROPS_TIMELINE_NAMESPACE"],
            "release": os.environ["INFEROPS_TIMELINE_RELEASE"],
            "application": os.environ["INFEROPS_TIMELINE_APPLICATION"],
            "applicationNamespace": os.environ["INFEROPS_TIMELINE_APPLICATION_NAMESPACE"],
            "executingCommit": os.environ["INFEROPS_TIMELINE_COMMIT"],
            "procedureSha256": os.environ["INFEROPS_TIMELINE_PROCEDURE_SHA256"],
            "librarySha256": os.environ["INFEROPS_TIMELINE_LIBRARY_SHA256"],
            "requestedSamples": int(os.environ["INFEROPS_TIMELINE_SAMPLES"]),
            "intervalSeconds": int(os.environ["INFEROPS_TIMELINE_INTERVAL"]),
            "readTimeoutSeconds": int(os.environ["INFEROPS_TIMELINE_READ_TIMEOUT"]),
        },
        indent=2,
        sort_keys=True,
    )
)
' >"${collection_dir}/collection.json"

inferops::log "experiment ${experiment_id}, run ${run_id}"
inferops::log "release ${INFEROPS_RELEASE_NAME}, namespace ${INFEROPS_RELEASE_NAMESPACE}"
inferops::log "samples: ${samples}, with a pause of ${interval}s between two, into ${collection_rel}"

# --- The samples ------------------------------------------------------------

# One read into one file. A read that fails leaves no file.
collect() {
  local file="$1"
  shift
  if inferops::target_kubectl "$@" --request-timeout "${READ_TIMEOUT_SECONDS}s" -o json >"${file}" 2>/dev/null; then
    return 0
  fi
  rm -f "${file}"
  return 1
}

unanswered=0
for ((index = 1; index <= samples; index++)); do
  stem="${collection_dir}/$(printf 'sample-%04d' "${index}")"

  workload_read="answered"
  workload_started_at="$(instant)"
  collect "${stem}.workload.json" get "${WORKLOAD_KINDS}" --namespace "${INFEROPS_RELEASE_NAMESPACE}" ||
    workload_read="unanswered"
  workload_finished_at="$(instant)"

  # An absent Application answers with no output. It is an answer.
  application_read="answered"
  application_started_at="$(instant)"
  collect "${stem}.application.json" get "${APPLICATION_KIND}" "${APPLICATION_NAME}" --namespace "${APPLICATION_NAMESPACE}" --ignore-not-found ||
    application_read="unanswered"
  application_finished_at="$(instant)"

  printf 'workloadRead=%s\nworkloadStartedAt=%s\nworkloadFinishedAt=%s\napplicationRead=%s\napplicationStartedAt=%s\napplicationFinishedAt=%s\n' \
    "${workload_read}" "${workload_started_at}" "${workload_finished_at}" \
    "${application_read}" "${application_started_at}" "${application_finished_at}" >"${stem}.meta"

  if [ "${workload_read}" != "answered" ] || [ "${application_read}" != "answered" ]; then
    unanswered=$((unanswered + 1))
    inferops::warn "sample ${index} of ${samples} at ${workload_started_at}: workload read ${workload_read}, Application read ${application_read}. ${UNANSWERED}"
  else
    inferops::log "sample ${index} of ${samples} at ${workload_started_at}: workload read ${workload_read}, Application read ${application_read}"
  fi
  [ "${index}" -ge "${samples}" ] || sleep "${interval}"
done
printf 'completedSamples=%s\n' "${samples}" >"${collection_dir}/collection.end"

# --- The streams ------------------------------------------------------------

mkdir "${collection_dir}/streams"
stream_files=()
for name in ${STREAM_NAMES}; do
  status=0
  (cd "${INFEROPS_ROOT}" && inferops::python -m "${TIMELINE_MODULE}" stream "${collection_rel}" "${name}") \
    >"${collection_dir}/streams/${name}.jsonl" || status=$?
  if [ "${status}" -ne 0 ]; then
    rm -f "${collection_dir}/streams/${name}.jsonl"
    inferops::fail "the tool wrote no ${name} stream for '${collection_rel}' (exit ${status}). The reads are kept in that directory."
  fi
  stream_files+=("${collection_rel}/streams/${name}.jsonl")
done

(cd "${INFEROPS_ROOT}" && inferops::python -m "${TIMELINE_MODULE}" check "${stream_files[@]}") | sed 's/^/[inferops] /' ||
  inferops::fail "the tool refused a stream that it wrote for '${collection_rel}'. The reads are kept in that directory."

inferops::section "Result"
inferops::log "${samples} sample(s) were taken, and the four streams are in ${collection_rel}/streams. This script judged none of them."
if [ "${unanswered}" -gt 0 ]; then
  inferops::warn "${unanswered} sample(s) hold a read that did not answer. Such a read gave no state. It is not a healthy state, and it is not zero."
fi
inferops::log "The streams state what the cluster published and what the delivery controller reported. They are not a request that a caller sent."
inferops::log "The directory holds the whole answer of each read. Do not commit it. The four files under streams/ are the evidence files."
