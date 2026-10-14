#!/usr/bin/env bash
# Starts one RP-1 reliability run as a Kubernetes Job, reads its caller record,
# and removes it. This is the real path of the reliability runner. It runs only
# when an operator starts it.
#
# A run is one NetworkPolicy, one ConfigMap, and one Job in the namespace of the
# release. The NetworkPolicy admits the pod of the run, and no other pod, to the
# API pods on the API port: the policy of the release admits only its own pods
# and a named collector, and a cluster whose network plugin enforces it drops
# the requests of the runner otherwise. The pod
# of the Job executes one file, tools/reliability_runner/incluster.py, which
# sends the RP-1 request to the API Service by its cluster DNS name. The pod
# holds no service account token. It reads no Kubernetes API, no readiness
# answer, and no state of a delivery controller.
#
# This script does not wait for the release to be ready, and it does not look
# at a pod of the release. It reads one thing from the release when no image is
# given: the image that the API Deployment names. The runner uses that image as
# its interpreter, because a node that runs an API pod holds it. Nothing
# schedules the runner onto such a node. That read is of the Deployment's
# specification and not of its status.
#
# The four actions:
#
#   start     writes the plan and the manifest of the run under .artifacts/,
#             and creates the three objects. It refuses when an object of that
#             name exists. It returns when the Job is created. It does not
#             wait for the run.
#   status    prints the state of the Job. It changes nothing.
#   collect   reads the log of the pod, and checks it. It keeps the log as
#             the caller record only when each rule accepts it.
#   cleanup   deletes the Job, the ConfigMap, and the NetworkPolicy of the run,
#             by name.
#
# A run has four bounds: its duration, its request ceiling, the active
# deadline of the Job, and the time to live of the finished Job. Kubernetes
# documents that it deletes a finished Job and its pod after that time, and
# that a log does not outlive its pod. So collect the record within that
# time. The time to live does not delete the ConfigMap: cleanup does.
#
# This script was not executed against a cluster in the change that added it.
#
# Exit status: 0 when the action did what it states. For collect, 0 says that
# each rule accepted the record. It does not say that a request succeeded. 5
# when collect wrote a record that a rule refuses. 1 in each other case.
#
# Usage:
#   INFEROPS_PROVIDER=<provider> scripts/environment/reliability-runner.sh start \
#     --experiment-id ID --run-id ID --duration-seconds N \
#     [--request-ceiling N] [--release-id SHA256] [--image REPOSITORY@DIGEST]
#   INFEROPS_PROVIDER=<provider> scripts/environment/reliability-runner.sh status --run-id ID
#   INFEROPS_PROVIDER=<provider> scripts/environment/reliability-runner.sh collect --run-id ID
#   INFEROPS_PROVIDER=<provider> scripts/environment/reliability-runner.sh cleanup --run-id ID
#
# See docs/serving/reliability-runner.md.

# shellcheck source=scripts/environment/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

readonly USAGE="Usage: INFEROPS_PROVIDER=<provider> reliability-runner.sh start|status|collect|cleanup --run-id ID [start only: --experiment-id ID --duration-seconds N [--request-ceiling N] [--release-id SHA256] [--image REPOSITORY@DIGEST]]"
readonly RUNNER_MODULE="tools.reliability_runner"
readonly RUNS_REL=".artifacts/reliability-runner/runs"
readonly JOB_NAME_PREFIX="inferops-reliability-"
readonly API_COMPONENT_SELECTOR="${INFEROPS_RELEASE_SELECTOR},app.kubernetes.io/component=platform-api"
readonly REFUSED_EXIT=5
readonly TOOL_REFUSED_EXIT=3
# Above the termination grace period of the pod, which is one client deadline
# and 30 seconds. Kubernetes documents that a foreground deletion of a Job
# waits for its pod.
readonly DELETE_TIMEOUT="240s"

# --- Arguments --------------------------------------------------------------

action="${1:-}"
case "${action}" in
  start | status | collect | cleanup) shift ;;
  *) inferops::fail "unknown argument '${action}'. ${USAGE}" ;;
esac

run_id=""
experiment_id=""
duration_seconds=""
request_ceiling=""
release_id=""
image=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --run-id | --experiment-id | --duration-seconds | --request-ceiling | --release-id | --image)
      [ "$#" -ge 2 ] && [ -n "$2" ] || inferops::fail "$1 needs a value. ${USAGE}"
      case "$1" in
        --run-id) run_id="$2" ;;
        --experiment-id) experiment_id="$2" ;;
        --duration-seconds) duration_seconds="$2" ;;
        --request-ceiling) request_ceiling="$2" ;;
        --release-id) release_id="$2" ;;
        --image) image="$2" ;;
      esac
      shift 2
      ;;
    *)
      inferops::fail "unknown argument '$1'. ${USAGE}"
      ;;
  esac
done

# The run identifier is part of a path and of the name of the Job. The tool
# applies the same rule to the plan.
[[ "${run_id}" =~ ^[a-z0-9]([a-z0-9-]{0,38}[a-z0-9])?$ ]] ||
  inferops::fail "--run-id must be a lower-case DNS label of at most 40 characters. ${USAGE}"

if [ "${action}" = "start" ]; then
  [ -n "${experiment_id}" ] || inferops::fail "start needs --experiment-id. ${USAGE}"
  [ -n "${duration_seconds}" ] || inferops::fail "start needs --duration-seconds. ${USAGE}"
elif [ -n "${experiment_id}${duration_seconds}${request_ceiling}${release_id}${image}" ]; then
  inferops::fail "${action} takes --run-id and no other option. ${USAGE}"
fi

job_name="${JOB_NAME_PREFIX}${run_id}"
run_rel="${RUNS_REL}/${run_id}"
run_dir="${INFEROPS_ROOT}/${run_rel}"

inferops::require_cmd kubectl
inferops::require_cmd python

# --- The target -------------------------------------------------------------

inferops::resolve_target

case "${action}" in
  start)
    inferops::section "Reliability run ${run_id} on ${INFEROPS_TARGET_PROVIDER}: start"

    [ ! -e "${run_dir}" ] ||
      inferops::fail "'${run_rel}' already exists. One run identifier is one run, and this script does not start a second one under it."

    if [ -z "${image}" ]; then
      # The specification of the Deployment, and not its status: the read does
      # not ask whether a pod is ready.
      image="$(inferops::target_kubectl get deployments \
        --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
        --selector "${API_COMPONENT_SELECTOR}" \
        -o jsonpath='{.items[*].spec.template.spec.containers[?(@.name=="api")].image}' 2>/dev/null |
        tr -d '\r' || true)"
      case "${image}" in
        "" | *" "*)
          inferops::fail "could not read one API image from the release in '${INFEROPS_RELEASE_NAMESPACE}'. The runner uses that image as its interpreter. Install the release, or give an image that holds Python 3.12 with --image REPOSITORY@DIGEST."
          ;;
      esac
    fi

    # An object of this name is an earlier run, or what the time to live of an
    # earlier Job left. A Job that mounted an earlier ConfigMap would run an
    # earlier plan under this run identifier.
    if ! existing="$(inferops::target_kubectl get jobs,configmaps,networkpolicies \
      --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
      --field-selector "metadata.name=${job_name}" -o name 2>/dev/null | tr -d '\r')"; then
      inferops::fail "could not read whether '${job_name}' exists in '${INFEROPS_RELEASE_NAMESPACE}'. A read that did not answer is not a result of nothing there. Nothing was created."
    fi
    [ -z "${existing}" ] ||
      inferops::fail "an object named '${job_name}' exists in '${INFEROPS_RELEASE_NAMESPACE}'. Remove it with 'cleanup', and start the run under another run identifier. Nothing was created."

    mkdir -p "${run_dir}"

    plan_arguments=(plan --experiment-id "${experiment_id}" --run-id "${run_id}"
      --duration-seconds "${duration_seconds}")
    [ -z "${request_ceiling}" ] || plan_arguments+=(--request-ceiling "${request_ceiling}")
    [ -z "${release_id}" ] || plan_arguments+=(--release-id "${release_id}")

    if ! (cd "${INFEROPS_ROOT}" && python -m "${RUNNER_MODULE}" "${plan_arguments[@]}") \
      >"${run_dir}/plan.json"; then
      rm -f "${run_dir}/plan.json"
      rmdir "${run_dir}" 2>/dev/null || true
      inferops::fail "the tool wrote no plan. Its message is above. Nothing was created."
    fi
    if ! (cd "${INFEROPS_ROOT}" && python -m "${RUNNER_MODULE}" manifest \
      --plan "${run_rel}/plan.json" --image "${image}") >"${run_dir}/manifest.json"; then
      rm -f "${run_dir}/plan.json" "${run_dir}/manifest.json"
      rmdir "${run_dir}" 2>/dev/null || true
      inferops::fail "the tool wrote no manifest. Its message is above. Nothing was created."
    fi

    inferops::log "plan and manifest are in ${run_rel}"
    inferops::log "image ${image}"

    # create and not apply: an object that exists is a refusal, and not a change.
    inferops::target_kubectl create -f "$(inferops::native_path "${run_dir}/manifest.json")" ||
      inferops::fail "the three objects were not all created. Remove what was created with 'cleanup'. The run identifier '${run_id}' is spent: '${run_rel}' is kept, and a new start needs another identifier."

    inferops::log "job ${job_name} is created in ${INFEROPS_RELEASE_NAMESPACE}. This script does not wait for it."
    inferops::log "the run sends requests when its pod starts. It does not wait for the release to be ready."
    ;;

  status)
    inferops::section "Reliability run ${run_id} on ${INFEROPS_TARGET_PROVIDER}: status"
    inferops::target_kubectl get job "${job_name}" \
      --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
      -o jsonpath='{"active="}{.status.active}{" succeeded="}{.status.succeeded}{" failed="}{.status.failed}{" started="}{.status.startTime}{" completed="}{.status.completionTime}{"\n"}' ||
      inferops::fail "could not read job ${job_name}. A read that did not answer is not a job that does not exist."
    ;;

  collect)
    inferops::section "Reliability run ${run_id} on ${INFEROPS_TARGET_PROVIDER}: collect"

    [ -f "${run_dir}/plan.json" ] ||
      inferops::fail "'${run_rel}/plan.json' does not exist. 'collect' checks the record against the plan that 'start' wrote on this host."
    [ ! -e "${run_dir}/caller.jsonl" ] ||
      inferops::fail "'${run_rel}/caller.jsonl' already exists. An accepted record is kept, and this script does not write over it."

    # The log of a pod that is still running is a record with no end line, and
    # the tool refuses it. The script does not wait for the Job. A log that the
    # tool refuses is kept under another name, so a later collect can run.
    if ! inferops::target_kubectl logs "job/${job_name}" \
      --namespace "${INFEROPS_RELEASE_NAMESPACE}" --container runner |
      tr -d '\r' >"${run_dir}/caller.partial.jsonl"; then
      rm -f "${run_dir}/caller.partial.jsonl"
      inferops::fail "could not read the log of job ${job_name}. A read that did not answer is not an empty record."
    fi

    status=0
    (cd "${INFEROPS_ROOT}" && inferops::python -m "${RUNNER_MODULE}" verify \
      "${run_rel}/caller.partial.jsonl" --plan "${run_rel}/plan.json") \
      >"${run_dir}/summary.json" || status=$?

    case "${status}" in
      0)
        mv "${run_dir}/caller.partial.jsonl" "${run_dir}/caller.jsonl"
        rm -f "${run_dir}/caller.refused.jsonl"
        sed 's/^/[inferops] /' "${run_dir}/summary.json"
        inferops::log "the caller record is in ${run_rel}/caller.jsonl. Each rule accepted it. That does not say that a request succeeded: read the outcomes."
        ;;
      "${TOOL_REFUSED_EXIT}")
        rm -f "${run_dir}/summary.json"
        mv -f "${run_dir}/caller.partial.jsonl" "${run_dir}/caller.refused.jsonl"
        inferops::warn "the tool refused the log. It is kept as ${run_rel}/caller.refused.jsonl, and a later collect writes over that file. A record with no end line is the log of a run that has not ended, or of a pod that was stopped. A line that is not JSON can be a line that the runner wrote to standard error."
        exit "${REFUSED_EXIT}"
        ;;
      *)
        rm -f "${run_dir}/summary.json"
        mv -f "${run_dir}/caller.partial.jsonl" "${run_dir}/caller.refused.jsonl"
        inferops::fail "the tool did not check the log (exit ${status}). It is kept as ${run_rel}/caller.refused.jsonl."
        ;;
    esac
    ;;

  cleanup)
    inferops::section "Reliability run ${run_id} on ${INFEROPS_TARGET_PROVIDER}: cleanup"
    # By name, and in the namespace of the release. Kubernetes documents that
    # the deletion of a Job deletes its pod, and that a log does not outlive
    # its pod.
    [ -f "${run_dir}/caller.jsonl" ] ||
      inferops::warn "'${run_rel}/caller.jsonl' does not exist: no accepted record of this run is kept on this host. The log of the pod is not readable after this deletion."
    inferops::target_kubectl delete job "${job_name}" -n "${INFEROPS_RELEASE_NAMESPACE}" \
      --ignore-not-found --cascade=foreground --wait --timeout "${DELETE_TIMEOUT}" ||
      inferops::fail "job ${job_name} was not deleted."
    inferops::target_kubectl delete configmap "${job_name}" -n "${INFEROPS_RELEASE_NAMESPACE}" \
      --ignore-not-found --wait --timeout "${DELETE_TIMEOUT}" ||
      inferops::fail "configmap ${job_name} was not deleted."
    # After the Job: the pod that the policy admits is gone first.
    inferops::target_kubectl delete networkpolicy "${job_name}" -n "${INFEROPS_RELEASE_NAMESPACE}" \
      --ignore-not-found --wait --timeout "${DELETE_TIMEOUT}" ||
      inferops::fail "networkpolicy ${job_name} was not deleted."

    if ! remaining="$(inferops::target_kubectl get jobs,configmaps,pods,networkpolicies \
      --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
      --selector "inferops.io/run-id=${run_id},app.kubernetes.io/name=inferops-reliability-runner" \
      -o name 2>/dev/null | tr -d '\r')"; then
      inferops::fail "the objects of the run were deleted, and the read that looks for what is left did not answer. That is not a result of nothing left."
    fi
    if [ -n "${remaining}" ]; then
      inferops::warn "still present: ${remaining//$'\n'/ }"
      inferops::fail "an object of run ${run_id} is still present. A pod can take its termination grace period to stop. Run cleanup again."
    fi
    inferops::log "no object of run ${run_id} is left in ${INFEROPS_RELEASE_NAMESPACE}. The files under ${run_rel} are kept."
    ;;
esac
