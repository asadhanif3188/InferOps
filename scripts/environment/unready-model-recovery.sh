#!/usr/bin/env bash
# Installs a release whose model does not become ready, holds it there, and keeps
# enough to say what readiness, liveness, the canonical error surface, the
# diagnostics, and the telemetry actually did -- then corrects one value, upgrades,
# and records what came back.
#
# What it establishes, and what it does not. It produces bounded observations of one
# release installed once with one runtime misconfiguration, on one provider and one
# host (ADR 0013). It is not an availability figure, a service-level objective, an
# error budget, a recovery-time objective, or a benchmark, and
# tools/unready_model_recovery refuses a record that does not carry that boundary.
#
# The question this asks, and the ones it does not repeat. ADR 0010 D8 publishes
# `model-not-ready` as the one row of the accepted error mapping anything ever
# observed, from a single control-plane line seen incidentally during the Sprint 0
# trial, and docs/serving/mock-and-real-boundary.md states as its rule
# that a mock may never certify real local runtime behaviour, which is what the mock
# adapter's MODEL_NOT_READY scenario would otherwise be doing here. This installs an
# unready model deliberately, on a real cluster. It is not V1-S3-008's artifact
# mismatch, which the `verify-model` init container refuses before the runtime
# container starts, and it is not V1-S4-006's deletion of a pod that was healthy.
#
# The disruption. One committed values overlay,
# deploy/serving/experiments/unready-model-values.v1.yaml, passed to the install and
# dropped from the upgrade. It sets the serving runtime container's processor request
# and limit and nothing else: no model value, no image, no probe, no profile. So the
# chart validates, the `verify-model` init container reads the same bytes it always
# reads and exits zero, `llama-server` starts and binds its port -- and the model load
# does not finish. The process is healthy and the model is not ready, which is the
# state nothing in this repository had ever produced against a real runtime.
#
# Why the forwards go to pods. A release whose model is not ready has no ready
# endpoint on the serving runtime Service *or* on the platform API Service: the API's
# readiness path is the conjunction of the API accepting work and its adapter
# reporting itself able. A Service forward would therefore measure kube-proxy refusing
# a connection rather than a workload answering, so both forwards address the pod.
#
# What a person had to do. Three authorisations are given before the run: the
# confirmation flag and the values files. After the install this script issues exactly
# two mutating commands -- the corrected upgrade and the uninstall -- and it records
# the first of them as the one intervention this experiment expects. A test reads this
# file to establish that there are no others.
#
# The assertions and the record are not here. They are in
# tools/unready_model_recovery, which reads the committed descriptor, refuses a
# collector URL that is not loopback, refuses any input carrying a host path or a
# credential, and writes the labelled record.
#
# On failure it collects diagnostics into .artifacts/, leaves the release in place for
# inspection, and says how to remove it.
#
# Usage:
#   scripts/environment/unready-model-recovery.sh check
#   scripts/environment/unready-model-recovery.sh run --values PATH [--values PATH ...] \
#     --confirm-real-kubernetes

# shellcheck source=scripts/environment/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

readonly INFEROPS_EXPERIMENT_REL="deploy/serving/experiments/unready-model-recovery.v1.json"
readonly INFEROPS_EXPERIMENT_MODULE="tools.unready_model_recovery"
readonly INFEROPS_UNREADY_OVERLAY_REL="deploy/serving/experiments/unready-model-values.v1.yaml"

# How much of each capture is kept in the record as an excerpt. The capture itself is
# written whole into the run directory; the excerpt is what a published record carries,
# and it is bounded because a log is not.
readonly INFEROPS_EXCERPT_LINES="12"

action=""
values_files=()
confirmed=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    check | run)
      [ -z "${action}" ] ||
        inferops::fail "two actions were given ('${action}' and '$1'). This script performs one at a time, so that its output describes what it did."
      action="$1"
      shift
      ;;
    --values)
      [ "$#" -ge 2 ] || inferops::fail "--values needs a path. Usage: unready-model-recovery.sh run --values PATH [--values PATH ...] --confirm-real-kubernetes"
      values_files+=("$2")
      shift 2
      ;;
    --confirm-real-kubernetes)
      confirmed=1
      shift
      ;;
    *)
      inferops::fail "unknown argument '$1'. Usage: unready-model-recovery.sh check|run [--values PATH ...] [--confirm-real-kubernetes]"
      ;;
  esac
done

[ -n "${action}" ] ||
  inferops::fail "expected one of check, run. Usage: unready-model-recovery.sh check|run [--values PATH ...] [--confirm-real-kubernetes]"

inferops::require_cmd python

experiment_file="${INFEROPS_ROOT}/${INFEROPS_EXPERIMENT_REL}"
[ -f "${experiment_file}" ] ||
  inferops::fail "no experiment descriptor at ${INFEROPS_EXPERIMENT_REL}"
overlay_file="${INFEROPS_ROOT}/${INFEROPS_UNREADY_OVERLAY_REL}"
[ -f "${overlay_file}" ] ||
  inferops::fail "no values overlay at ${INFEROPS_UNREADY_OVERLAY_REL}. It is the whole disruption; without it this would install an ordinary release."

# --- check: reads files, contacts nothing -----------------------------------

if [ "${action}" = "check" ]; then
  inferops::section "Unready model experiment"
  (cd "${INFEROPS_ROOT}" && python -m "${INFEROPS_EXPERIMENT_MODULE}" check)
  inferops::log "the descriptor validated. Nothing was contacted, no release was installed, and no model was loaded."
  exit 0
fi

# --- everything below reaches a cluster and a real model ---------------------

[ "${confirmed}" -eq 1 ] ||
  inferops::fail "run needs --confirm-real-kubernetes. It applies the Terraform prerequisites, installs a release that is deliberately misconfigured, loads a real model, sends real requests, upgrades the release, and removes it. Usage: unready-model-recovery.sh run --values PATH [--values PATH ...] --confirm-real-kubernetes"

[ "${#values_files[@]}" -gt 0 ] ||
  inferops::fail "--values is required. The chart's shipped defaults select no serving profile and are refused on purpose. See docs/serving/unready-model-recovery.md."

values_arguments=()
for values_file in "${values_files[@]}"; do
  [ -f "${values_file}" ] || inferops::fail "no such values file: ${values_file}"
  values_arguments+=(--values "$(inferops::native_path "$(cd "$(dirname "${values_file}")" && pwd)/$(basename "${values_file}")")")
done

# The overlay is appended by this script rather than passed by the operator, so that
# the file whose digest the record pins is the file that was installed. An operator
# who passed it themselves could pass a different one.
overlay_argument=(--values "$(inferops::native_path "${overlay_file}")")

inferops::require_cmd kubectl
inferops::require_cmd helm
inferops::require_cmd terraform
inferops::require_cmd curl
inferops::require_engine
# The provider-aware target this project consumes rather than creates
# (docs/environment/local-cluster-provider-contract.md): an explicit
# INFEROPS_PROVIDER, re-verified now rather than trusted from an earlier run.
inferops::resolve_target

inferops::section "Unready model experiment"
(cd "${INFEROPS_ROOT}" && python -m "${INFEROPS_EXPERIMENT_MODULE}" check)

# The descriptor's entry for the provider that was actually verified. A provider the
# descriptor does not describe is refused before anything is installed.
read_provider_target() {
  inferops::python -c '
import json, sys
from pathlib import Path

record = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
for provider in record["cluster"]["providers"]:
    if provider["providerId"] == sys.argv[2]:
        print(provider["name"])
        print(provider["context"])
        break
else:
    raise SystemExit(f"the descriptor does not describe provider {sys.argv[2]!r}")
' "$(inferops::native_path "${experiment_file}")" "$1"
}

if ! provider_target="$(read_provider_target "${INFEROPS_TARGET_PROVIDER}")"; then
  inferops::fail "refusing: this experiment's descriptor does not describe provider '${INFEROPS_TARGET_PROVIDER}'. Nothing was installed."
fi
{
  read -r descriptor_cluster
  read -r descriptor_context
} <<<"${provider_target}"

# Read into a variable first and check the status: a reader whose producer failed sees
# empty fields and no error, and an empty budget becomes arithmetic.
if ! descriptor_fields="$(cd "${INFEROPS_ROOT}" && inferops::python -m "${INFEROPS_EXPERIMENT_MODULE}" fields \
  release.name release.namespace release.apiServiceName release.apiContainerPort \
  release.apiDeploymentName release.runtimeDeploymentName release.runtimeServiceName \
  release.runtimeContainerPort release.collectorServiceName release.collectorServicePort \
  release.collectorDeploymentName release.configMapName release.apiComponent \
  release.runtimeComponent release.acquisitionComponent \
  observation.pollIntervalMs observation.minimumSamples observation.unreadyWindowSeconds \
  observation.recoveredWindowSeconds probes.roundIntervalMs probes.requestTimeoutMs \
  diagnostics.logTailLines schedule.idleBaselineSeconds schedule.settleAfterRecoverySeconds \
  readiness.runtimeContainerRunningBudgetMs readiness.apiContainerRunningBudgetMs \
  readiness.collectorRolloutBudgetMs readiness.forwardBudgetMs \
  readiness.recoveryRolloutBudgetMs readiness.uninstallBudgetMs \
  forwards.host forwards.apiPort forwards.runtimePort \
  forwards.recoveredRuntimePort forwards.collectorPort \
  evidence.directory evidence.lifecycleFile evidence.readinessFile evidence.probesFile \
  evidence.diagnosticsFile)"; then
  inferops::fail "the experiment descriptor could not be read after it validated. Nothing was installed."
fi

{
  read -r descriptor_release
  read -r descriptor_namespace
  read -r api_service
  read -r api_container_port
  read -r api_deployment
  read -r runtime_deployment
  read -r runtime_service
  read -r runtime_container_port
  read -r collector_service
  read -r collector_service_port
  read -r collector_deployment
  read -r configmap_name
  read -r api_component
  read -r runtime_component
  read -r acquisition_component
  read -r poll_interval_ms
  read -r minimum_samples
  read -r unready_window_seconds
  read -r recovered_window_seconds
  read -r round_interval_ms
  read -r request_timeout_ms
  read -r log_tail_lines
  read -r idle_seconds
  read -r settle_seconds
  read -r runtime_running_budget_ms
  read -r api_running_budget_ms
  read -r collector_rollout_budget_ms
  read -r forward_budget_ms
  read -r recovery_rollout_budget_ms
  read -r uninstall_budget_ms
  read -r forward_host
  read -r api_forward_port
  read -r runtime_forward_port
  read -r recovered_runtime_forward_port
  read -r collector_forward_port
  read -r evidence_rel
  read -r lifecycle_name
  read -r readiness_name
  read -r probes_name
  read -r diagnostics_name
} <<<"${descriptor_fields}"

# Every value that reaches arithmetic, a timeout, or a port is held to being a number
# here, at the point of use. The Python validator refuses the same, in another file: a
# guard whose correctness depends on the order two programs run in is a guard waiting
# to be reordered.
for number in api_container_port runtime_container_port collector_service_port \
  poll_interval_ms minimum_samples unready_window_seconds recovered_window_seconds \
  round_interval_ms request_timeout_ms log_tail_lines idle_seconds settle_seconds \
  runtime_running_budget_ms api_running_budget_ms collector_rollout_budget_ms \
  forward_budget_ms recovery_rollout_budget_ms uninstall_budget_ms \
  api_forward_port runtime_forward_port recovered_runtime_forward_port \
  collector_forward_port; do
  case "${!number}" in
    '' | *[!0-9]*) inferops::fail "the experiment descriptor's '${number}' is not a number. Nothing was installed." ;;
  esac
done
[ "${poll_interval_ms}" -ge 1000 ] ||
  inferops::fail "the descriptor samples readiness every ${poll_interval_ms} ms; below 1000 ms this loop would spin against the API server. Nothing was installed."

for name in api_service api_deployment runtime_deployment runtime_service \
  collector_service collector_deployment configmap_name api_component \
  runtime_component acquisition_component; do
  case "${!name}" in
    *[!a-z0-9-]* | '') inferops::fail "the descriptor's '${name}' is '${!name}', which is not a Kubernetes name. Nothing was installed." ;;
  esac
done

# The API behind the forward carries no authentication, so binding it anywhere but
# loopback would publish an unauthenticated LLM endpoint on every interface.
[ "${forward_host}" = "127.0.0.1" ] ||
  inferops::fail "the descriptor's forward host is '${forward_host}'. These forwards bind 127.0.0.1 only. Nothing was installed."

[ "${descriptor_cluster}" = "${INFEROPS_TARGET_CLUSTER_NAME}" ] ||
  inferops::fail "for provider '${INFEROPS_TARGET_PROVIDER}' the descriptor names cluster '${descriptor_cluster}' and the verified target is '${INFEROPS_TARGET_CLUSTER_NAME}'."
[ "${descriptor_context}" = "${INFEROPS_TARGET_CONTEXT}" ] ||
  inferops::fail "for provider '${INFEROPS_TARGET_PROVIDER}' the descriptor names context '${descriptor_context}' and the verified target is '${INFEROPS_TARGET_CONTEXT}'."
[ "${descriptor_release}" = "${INFEROPS_RELEASE_NAME}" ] ||
  inferops::fail "the descriptor names release '${descriptor_release}' and these scripts operate '${INFEROPS_RELEASE_NAME}'."
[ "${descriptor_namespace}" = "${INFEROPS_RELEASE_NAMESPACE}" ] ||
  inferops::fail "the descriptor names namespace '${descriptor_namespace}' and these scripts operate '${INFEROPS_RELEASE_NAMESPACE}'."

case "${INFEROPS_RELEASE_NAMESPACE}" in
  inferops-*) ;;
  *) inferops::fail "the release namespace must be prefixed 'inferops-' (ADR 0001 D5). It is '${INFEROPS_RELEASE_NAMESPACE}'." ;;
esac

case "${evidence_rel}" in
  .cache/inferops/experiments/*) ;;
  *) inferops::fail "the descriptor writes run evidence to '${evidence_rel}', outside .cache/inferops/experiments/. Nothing was installed." ;;
esac

chart_dir="${INFEROPS_ROOT}/${INFEROPS_CHART_PATH}"
[ -d "${chart_dir}" ] || inferops::fail "no chart at ${INFEROPS_CHART_PATH}"
chart_path="$(inferops::native_path "${chart_dir}")"

run_dir="${INFEROPS_ROOT}/${evidence_rel}"
cluster_dir="${run_dir}/cluster"
capture_dir="${run_dir}/captures"
lifecycle_file="${run_dir}/${lifecycle_name}"
readiness_file="${run_dir}/${readiness_name}"
readiness_samples="${run_dir}/readiness-samples.txt"
probes_file="${run_dir}/${probes_name}"
diagnostics_file="${run_dir}/${diagnostics_name}"
diag_dir="${INFEROPS_ARTIFACT_DIR}/unready-model-recovery"
forward_log="${diag_dir}/forward.log"

# A run directory is never overwritten. An earlier run's evidence is either already
# promoted or still wanted, and this script cannot tell which.
if [ -e "${run_dir}" ]; then
  inferops::fail "the run directory ${evidence_rel} already exists. Move it aside before a new run. Nothing was installed."
fi

# Wall-clock milliseconds from bash's own clock, with no process started to read it.
epoch_ms() {
  local micros="${EPOCHREALTIME/[.,]/}"
  printf '%s' "$((micros / 1000))"
}
[ -n "${EPOCHREALTIME:-}" ] ||
  inferops::fail "this shell has no EPOCHREALTIME (bash 5 or later is needed). Nothing was installed."

api_forward_pid=""
runtime_forward_pid=""
collector_forward_pid=""
release_installed=0

# --- diagnostics and teardown ------------------------------------------------

collect_diagnostics() {
  mkdir -p "${diag_dir}"
  inferops::warn "collecting diagnostics into .artifacts/unready-model-recovery/"
  inferops::target_helm list --namespace "${INFEROPS_RELEASE_NAMESPACE}" >"${diag_dir}/releases.txt" 2>&1 || true
  inferops::target_kubectl get all,configmap,pvc,job,endpointslices \
    -n "${INFEROPS_RELEASE_NAMESPACE}" -o wide >"${diag_dir}/get-all.txt" 2>&1 || true
  inferops::target_kubectl describe pods -n "${INFEROPS_RELEASE_NAMESPACE}" >"${diag_dir}/describe-pods.txt" 2>&1 || true
  inferops::target_kubectl get events -n "${INFEROPS_RELEASE_NAMESPACE}" \
    --sort-by=.lastTimestamp >"${diag_dir}/events.txt" 2>&1 || true
  inferops::target_kubectl logs -n "${INFEROPS_RELEASE_NAMESPACE}" \
    -l "${INFEROPS_RELEASE_SELECTOR}" --all-containers --tail="${log_tail_lines}" >"${diag_dir}/release.log" 2>&1 || true
}

# Waits for a child to exit for at most the given seconds, then kills it. Cleanup runs
# inside the EXIT trap, and an unbounded wait on a wedged port-forward would hang the
# very path that collects diagnostics.
wait_bounded() {
  local pid="$1" seconds="$2"
  local deadline=$((SECONDS + seconds))
  while kill -0 "${pid}" 2>/dev/null; do
    if [ "${SECONDS}" -ge "${deadline}" ]; then
      kill -9 "${pid}" 2>/dev/null || true
      break
    fi
    sleep 1
  done
  wait "${pid}" 2>/dev/null || true
}

close_forwards() {
  local pid
  for pid in "${api_forward_pid}" "${runtime_forward_pid}" "${collector_forward_pid}"; do
    if [ -n "${pid}" ] && kill -0 "${pid}" 2>/dev/null; then
      kill "${pid}" 2>/dev/null || true
      wait_bounded "${pid}" 10
    fi
  done
  api_forward_pid=""
  runtime_forward_pid=""
  collector_forward_pid=""
}

on_exit() {
  local rc=$?
  close_forwards
  if [ "${rc}" -ne 0 ]; then
    collect_diagnostics
    if [ "${release_installed}" -eq 1 ]; then
      inferops::warn "the release was left in place for inspection. Remove it with: helm uninstall ${INFEROPS_RELEASE_NAME} --namespace ${INFEROPS_RELEASE_NAMESPACE}"
      inferops::warn "the prerequisites and the model cache claim were not touched and are not removed by that command."
    fi
    inferops::warn "whatever evidence was written is in ${evidence_rel}/ and is not a usable record."
  fi
  exit "${rc}"
}

# INT and TERM as well as EXIT: this run leaves three forwards and a real release
# behind, and on Git Bash signal delivery to a native child is less predictable than
# on Linux.
trap on_exit INT TERM EXIT

mkdir -p "${diag_dir}" "${cluster_dir}" "${capture_dir}"

require_query() {
  local description="$1"
  local value
  shift
  if ! value="$("$@")"; then
    inferops::fail "could not establish ${description}. A record names the environment it ran in, and an unanswered query is not a measurement."
  fi
  [ -n "${value}" ] ||
    inferops::fail "${description} came back empty. A record names the environment it ran in, and an empty field is not a measurement."
  printf '%s' "${value}"
}

claim_count() {
  local output
  if ! output="$(inferops::target_kubectl get pvc -n "${INFEROPS_RELEASE_NAMESPACE}" -o name)"; then
    return 1
  fi
  printf '%s' "${output}" | grep -c . || true
}

acquisition_job_count() {
  local output
  if ! output="$(inferops::target_kubectl get jobs -n "${INFEROPS_RELEASE_NAMESPACE}" \
    -l "app.kubernetes.io/component=${acquisition_component}" -o name)"; then
    return 1
  fi
  printf '%s' "${output}" | grep -c . || true
}

release_revision() {
  inferops::target_kubectl get secret -n "${INFEROPS_RELEASE_NAMESPACE}" \
    -l "owner=helm,name=${INFEROPS_RELEASE_NAME},status=deployed" \
    -o 'jsonpath={.items[0].metadata.labels.version}'
}

component_pod_names() {
  inferops::target_kubectl get pods -n "${INFEROPS_RELEASE_NAMESPACE}" \
    -l "app.kubernetes.io/component=$1,${INFEROPS_RELEASE_SELECTOR}" \
    -o 'jsonpath={range .items[*]}{.metadata.name}{"\n"}{end}' | tr -d '\r'
}

pod_field() {
  inferops::target_kubectl get pod "$1" -n "${INFEROPS_RELEASE_NAMESPACE}" -o "jsonpath=$2" | tr -d '\r'
}

count_lines() { printf '%s\n' "$1" | grep -c . || true; }

# The pods of a tier that are not on their way out. A pod carrying a deletion stamp
# is still listed, still has an address, and is still counted by anything that asks how
# many there are -- and for a few seconds after an upgrade there are two.
live_pod_names() {
  inferops::target_kubectl get pods -n "${INFEROPS_RELEASE_NAMESPACE}" \
    -l "app.kubernetes.io/component=$1,${INFEROPS_RELEASE_SELECTOR}" \
    -o 'jsonpath={range .items[*]}{.metadata.name}{" "}{.metadata.deletionTimestamp}{"\n"}{end}' |
    tr -d '\r' | awk 'NF == 1 { print $1 }'
}

# The one surviving pod of a tier, counted rather than indexed into: a release with two
# would make "the serving runtime pod" ambiguous, and choosing one is exactly the
# decision that must not be made silently. It waits, because an upgrade's predecessor
# is not gone the moment its replacement reports Ready -- the first execution of this
# experiment reached here with two and refused, correctly and uselessly.
one_pod_of() {
  local component="$1"
  local deadline=$((SECONDS + recovery_rollout_budget_ms / 1000))
  local names count pod
  while :; do
    if ! names="$(live_pod_names "${component}")"; then
      inferops::fail "could not ask which '${component}' pod exists."
    fi
    count="$(count_lines "${names}")"
    if [ "${count}" = "1" ]; then
      pod="$(printf '%s\n' "${names}" | head -1)"
      case "${pod}" in
        *[!a-z0-9.-]* | '') inferops::fail "the '${component}' pod is named '${pod}', which is not a name this script will address." ;;
      esac
      printf '%s' "${pod}"
      return 0
    fi
    [ "${SECONDS}" -lt "${deadline}" ] ||
      inferops::fail "expected exactly one '${component}' pod that is not terminating, and found ${count} after waiting $((recovery_rollout_budget_ms / 1000)) s."
    sleep 3
  done
}

# --- prerequisites and the misconfigured release ------------------------------

if inferops::target_helm status "${INFEROPS_RELEASE_NAME}" --namespace "${INFEROPS_RELEASE_NAMESPACE}" >/dev/null 2>&1; then
  inferops::fail "release '${INFEROPS_RELEASE_NAME}' already exists in '${INFEROPS_RELEASE_NAMESPACE}'. This experiment starts from its own install, so that the environment it records is the one it made. Remove it first: helm uninstall ${INFEROPS_RELEASE_NAME} --namespace ${INFEROPS_RELEASE_NAMESPACE}"
fi

inferops::section "Applying the Terraform prerequisites"

bash "${INFEROPS_ROOT}/scripts/environment/terraform-prerequisites.sh" apply

if ! claims_before="$(claim_count)"; then
  inferops::fail "could not count the persistent volume claims before installing. An unanswered query is not an empty result."
fi
if ! jobs_before="$(acquisition_job_count)"; then
  inferops::fail "could not count the acquisition Jobs before installing."
fi

inferops::section "Installing the release with the model it cannot load in time"
inferops::log "the overlay ${INFEROPS_UNREADY_OVERLAY_REL} sets the serving runtime's processor request and limit and nothing else. The chart validates, the integrity init container passes, and the model load does not finish."

# Without --wait and without --create-namespace: the namespace is Terraform's, and
# --wait would block for the whole of a rollout that is never going to complete.
release_installed=1
install_issued_ms="$(epoch_ms)"
inferops::target_helm install "${INFEROPS_RELEASE_NAME}" "${chart_path}" --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
  "${values_arguments[@]}" "${overlay_argument[@]}"

# --- waiting for a container that starts and a model that does not ------------
#
# `kubectl rollout status` is deliberately not used for the two tiers this experiment
# misconfigures. A rollout completes when a pod is *ready*, and the whole point is
# that neither of them will be. What is waited for instead is the container being
# reported running, which is the state in which the socket is open and the model is
# still loading.

wait_for_container_running() {
  local component="$1" container="$2" budget_ms="$3" label="$4"
  local deadline=$((SECONDS + budget_ms / 1000))
  local pod started
  while [ "${SECONDS}" -lt "${deadline}" ]; do
    if names="$(component_pod_names "${component}")" && [ "$(count_lines "${names}")" = "1" ]; then
      pod="$(printf '%s\n' "${names}" | head -1)"
      started="$(pod_field "${pod}" "{.status.containerStatuses[?(@.name==\"${container}\")].state.running.startedAt}" || true)"
      if [ -n "${started}" ]; then
        # To stderr, deliberately: this function's stdout is the pod name, and a log
        # line on it would be read back as part of that name.
        inferops::log "${label} container is running in pod '${pod}'." >&2
        printf '%s' "${pod}"
        return 0
      fi
    fi
    sleep 2
  done
  inferops::fail "no running ${label} container within $((budget_ms / 1000)) s."
}

inferops::section "Waiting for the serving runtime container to start"
unready_runtime_pod="$(require_query "the running serving runtime pod" \
  wait_for_container_running "${runtime_component}" runtime "${runtime_running_budget_ms}" "serving runtime")"
runtime_pod="${unready_runtime_pod}"
runtime_container_running_ms="$(epoch_ms)"

inferops::section "Waiting for the platform API container to start"
api_pod="$(require_query "the running platform API pod" \
  wait_for_container_running "${api_component}" api "${api_running_budget_ms}" "platform API")"

inferops::section "Waiting for the collector"
inferops::target_kubectl rollout status "deployment/${collector_deployment}" \
  -n "${INFEROPS_RELEASE_NAMESPACE}" --timeout="$((collector_rollout_budget_ms / 1000))s"

runtime_pod_uid="$(require_query "the serving runtime pod uid" pod_field "${runtime_pod}" '{.metadata.uid}')"
runtime_started_at="$(require_query "the serving runtime container start time" pod_field "${runtime_pod}" '{.status.containerStatuses[?(@.name=="runtime")].state.running.startedAt}')"
runtime_init_name="$(require_query "the integrity init container" pod_field "${runtime_pod}" '{.status.initContainerStatuses[0].name}')"
runtime_init_exit="$(require_query "the integrity init exit code" pod_field "${runtime_pod}" '{.status.initContainerStatuses[0].state.terminated.exitCode}')"
revision_before="$(require_query "the release revision before the fix" release_revision)"

# --- what the cluster reported -----------------------------------------------

inferops::section "Recording what the cluster reports"

dump_json() {
  local name="$1"
  shift
  local output
  if ! output="$("$@")"; then
    inferops::fail "could not read '${name}' from the cluster. A record names the environment it ran in."
  fi
  [ -n "${output}" ] || inferops::fail "'${name}' came back empty."
  printf '%s\n' "${output}" | tr -d '\r' >"${cluster_dir}/${name}"
}

node_name="$(printf '%s\n' "${INFEROPS_TARGET_NODE_NAMES}" | head -1)"
[ -n "${node_name}" ] || inferops::fail "the verified target reported no node name."

dump_json version.json inferops::target_kubectl version -o json
dump_json node.json inferops::target_kubectl get node "${node_name}" -o json
dump_json configmap.json inferops::target_kubectl get configmap "${configmap_name}" \
  -n "${INFEROPS_RELEASE_NAMESPACE}" -o json
dump_json deployments-unready.json inferops::target_kubectl get deployments \
  -n "${INFEROPS_RELEASE_NAMESPACE}" -l "${INFEROPS_RELEASE_SELECTOR}" -o json
dump_json pods-unready.json inferops::target_kubectl get pods \
  -n "${INFEROPS_RELEASE_NAMESPACE}" -l "${INFEROPS_RELEASE_SELECTOR}" -o json

# Read across namespaces and counted, never named: the record keeps how many other
# pods shared the node, not what they were.
dump_json running-pods.json inferops::target_kubectl get pods --all-namespaces \
  --field-selector=status.phase=Running -o json

helm_version="$(require_query "the helm version" inferops::target_helm version --short)"
engine_version="$(require_query "the container engine version" docker version --format '{{.Server.Version}}')"
engine_cpus="$(require_query "the engine's processors" docker info --format '{{.NCPU}}')"
engine_memory="$(require_query "the engine's memory" docker info --format '{{.MemTotal}}')"

INFEROPS_FACT_PROVIDER="${INFEROPS_TARGET_PROVIDER}" \
  INFEROPS_FACT_CLUSTER="${INFEROPS_TARGET_CLUSTER_NAME}" \
  INFEROPS_FACT_CONTEXT="${INFEROPS_TARGET_CONTEXT}" \
  INFEROPS_FACT_VERIFIED_AT="${INFEROPS_TARGET_VERIFIED_AT}" \
  INFEROPS_FACT_NODE_DIGEST="${INFEROPS_TARGET_NODE_IMAGE_DIGEST}" \
  INFEROPS_FACT_HELM="${helm_version}" \
  INFEROPS_FACT_ENGINE_VERSION="${engine_version}" \
  INFEROPS_FACT_ENGINE_CPUS="${engine_cpus}" \
  INFEROPS_FACT_ENGINE_MEMORY="${engine_memory}" \
  python - "$(inferops::native_path "${cluster_dir}")" <<'TARGET_PYTHON'
import json
import os
import sys
from pathlib import Path


def fact(name: str) -> str:
    return os.environ.get(f"INFEROPS_FACT_{name}", "").strip()


def number(name: str) -> int:
    value = fact(name)
    if not value.isdigit():
        raise SystemExit(f"the {name.lower()} reading is not a number")
    return int(value)


directory = Path(sys.argv[1])
target = {
    "provider": fact("PROVIDER"),
    "cluster": fact("CLUSTER"),
    "context": fact("CONTEXT"),
    "verifiedAt": fact("VERIFIED_AT"),
    "nodeImageDigest": fact("NODE_DIGEST"),
    "helmVersion": fact("HELM"),
}
engine = {
    "serverVersion": fact("ENGINE_VERSION"),
    "cpus": number("ENGINE_CPUS"),
    "memoryBytes": number("ENGINE_MEMORY"),
}
for name, document in (("target.json", target), ("engine.json", engine)):
    (directory / name).write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
TARGET_PYTHON

(cd "${INFEROPS_ROOT}" && python -m "${INFEROPS_EXPERIMENT_MODULE}" repository --run-dir "$(inferops::native_path "${run_dir}")")

# --- the forwards -------------------------------------------------------------
#
# To pods, not to Services, for the reason stated at the top of this file: a release
# whose model is not ready has no ready endpoint on either workload Service. The
# collector is the exception and is reached through its Service, because it is the one
# tier that is ready.

# Waits until nothing is listening on a local port.
#
# Closing a forward kills the process; it does not make the operating system release
# the socket, and on this host it does not do so immediately. A run that opened the
# next forward straight away found the new `kubectl port-forward` refusing to bind --
# `Only one usage of each socket address` -- exiting, and the connection check below
# succeeding against the *previous* forward, which was still listening and still
# pointed at the pod the upgrade had replaced. Three probe rounds were then recorded
# against the misconfigured pod: one answered `Loading model` and two found nothing
# there at all. So the port is waited for rather than assumed.
wait_for_port_free() {
  local host="$1" port="$2"
  local deadline=$((SECONDS + forward_budget_ms / 1000))
  while [ "${SECONDS}" -lt "${deadline}" ]; do
    if ! python -c '
import socket, sys

try:
    socket.create_connection((sys.argv[1], int(sys.argv[2])), 2).close()
except OSError:
    sys.exit(1)
' "${host}" "${port}" 2>/dev/null; then
      return 0
    fi
    sleep 1
  done
  inferops::fail "something is still listening on ${host}:${port} after $((forward_budget_ms / 1000)) s. A forward opened onto it would be measuring whatever that is."
}

opened_forward_pid=""
open_forward() {
  local object="$1" remote_port="$2" local_port="$3"
  wait_for_port_free "${forward_host}" "${local_port}"
  inferops::target_kubectl port-forward "${object}" "${local_port}:${remote_port}" \
    -n "${INFEROPS_RELEASE_NAMESPACE}" --address "${forward_host}" >>"${forward_log}" 2>&1 &
  opened_forward_pid="$!"
  local deadline=$((SECONDS + forward_budget_ms / 1000))
  while [ "${SECONDS}" -lt "${deadline}" ]; do
    kill -0 "${opened_forward_pid}" 2>/dev/null ||
      inferops::fail "the port-forward to '${object}' exited before it accepted a connection. Its output is in .artifacts/unready-model-recovery/forward.log."
    if python -c '
import socket, sys

try:
    socket.create_connection((sys.argv[1], int(sys.argv[2])), 2).close()
except OSError:
    sys.exit(1)
' "${forward_host}" "${local_port}" 2>/dev/null; then
      # Asked again after the connection succeeded, and not only before it: the
      # listener that accepted it is this forward's only if this forward is still
      # running.
      kill -0 "${opened_forward_pid}" 2>/dev/null ||
        inferops::fail "something accepted a connection on ${forward_host}:${local_port} and it was not the forward to '${object}', which had already exited. Its output is in .artifacts/unready-model-recovery/forward.log."
      inferops::log "forward open on http://${forward_host}:${local_port} to ${object}."
      return 0
    fi
    sleep 1
  done
  inferops::fail "the forward to '${object}' did not accept a connection within $((forward_budget_ms / 1000)) s."
}

# The instant the serving runtime first answered anything on its own port. It is
# evidence rather than plumbing: the chart's liveness probe is a TCP connect, so the
# moment the socket opens is the moment liveness starts being satisfied, and every
# statement this experiment makes about liveness not killing a healthy process is
# made about the window that begins here.
#
# The forward is re-opened if it died, because `kubectl port-forward` ends when the
# container is not listening yet and a dead forward would be recorded as a runtime
# that refused.
runtime_socket_open_ms=""
# Which local port the serving runtime is asked on. It moves once, when the upgrade
# replaces the pod behind it.
runtime_probe_port="${runtime_forward_port}"
open_runtime_forward_when_listening() {
  local deadline=$((SECONDS + runtime_running_budget_ms / 1000))
  local status
  while [ "${SECONDS}" -lt "${deadline}" ]; do
    if [ -z "${runtime_forward_pid}" ] || ! kill -0 "${runtime_forward_pid}" 2>/dev/null; then
      runtime_forward_pid=""
      open_forward "pod/${runtime_pod}" "${runtime_container_port}" "${runtime_probe_port}"
      runtime_forward_pid="${opened_forward_pid}"
    fi
    status="$(curl -sS -o /dev/null -w '%{http_code}' --max-time 5 \
      "http://${forward_host}:${runtime_probe_port}${runtime_health_path}" \
      2>>"${forward_log}" || true)"
    case "${status}" in
      '' | 0 | 000)
        sleep 3
        ;;
      *)
        runtime_socket_open_ms="$(epoch_ms)"
        inferops::log "the serving runtime answered ${status} on its own port; its socket is open."
        return 0
        ;;
    esac
  done
  inferops::fail "the serving runtime never accepted a connection on its own port within $((runtime_running_budget_ms / 1000)) s. A TCP liveness probe would have been failing as well, which is a different experiment from this one."
}

# The three forwards this run opens, once. Only the serving runtime's is opened a
# second time, after the upgrade replaces the pod behind it.
open_forwards() {
  open_forward "pod/${api_pod}" "${api_container_port}" "${api_forward_port}"
  api_forward_pid="${opened_forward_pid}"
  open_runtime_forward_when_listening
}

# --- the probe surfaces, read from the descriptor -----------------------------

if ! probe_rows="$(cd "${INFEROPS_ROOT}" && inferops::python -m "${INFEROPS_EXPERIMENT_MODULE}" surfaces)"; then
  inferops::fail "the descriptor's probe surfaces could not be read."
fi
[ -n "${probe_rows}" ] || inferops::fail "the descriptor registers no probe surface."

runtime_health_path="$(printf '%s\n' "${probe_rows}" | awk '$2 == "serving-runtime" { print $4; exit }')"
case "${runtime_health_path}" in
  /*) ;;
  *) inferops::fail "the descriptor registers no serving runtime request path, so this script has nothing to wait for the runtime's socket with." ;;
esac

open_collector_forward() {
  open_forward "service/${collector_service}" "${collector_service_port}" "${collector_forward_port}"
  collector_forward_pid="${opened_forward_pid}"
}

inferops::section "Opening the loopback forwards"
open_forwards
# Kept now, because the runtime's forward is opened again after the upgrade and stamps
# `runtime_socket_open_ms` a second time, and what the lifecycle records is when the
# *misconfigured* runtime first answered.
install_socket_open_ms="${runtime_socket_open_ms}"
open_collector_forward

: >"${probes_file}"
: >"${readiness_samples}"

# One request, classified into one JSONL line. The body is never kept: the descriptor
# sets retainGeneratedText false, and a completion body is generated text. What is kept
# is the status, the canonical code the API reported in its own error envelope, whether
# it said the request could be retried, a bounded detail, the body's length and digest,
# and the output token count -- which is what establishes that a completion was really
# served rather than merely answered 200.
probe_once() {
  local phase="${1:?probe_once needs a phase}"
  local round="${2:?probe_once needs a round number}"
  local probe_id="${3:?probe_once needs a probe id}"
  local tier="${4:?probe_once needs a tier}"
  local method="${5:?probe_once needs a method}"
  local path="${6:?probe_once needs a request path}"
  local base body body_native status started ended
  case "${tier}" in
    platform-api) base="http://${forward_host}:${api_forward_port}" ;;
    serving-runtime) base="http://${forward_host}:${runtime_probe_port}" ;;
    *) inferops::fail "probe '${probe_id}' names tier '${tier}', which this script does not address." ;;
  esac
  body="${capture_dir}/body-${phase}-${round}-${probe_id}.json"
  body_native="$(inferops::native_path "${body}")"
  started="$(epoch_ms)"
  if [ "${method}" = "POST" ]; then
    # `model` and `messages`, and nothing else. `max_tokens` and `temperature` are
    # outside the frozen request subset src/inferops/api/validation.py accepts, and a
    # request carrying either is refused `contract-invalid` before readiness is ever
    # consulted -- which is a fact about the request, not about the model. The first
    # execution of this experiment sent both and recorded sixteen 400s for it.
    status="$(curl -sS -o "${body_native}" -w '%{http_code}' \
      --max-time "$((request_timeout_ms / 1000))" \
      -X POST "${base}${path}" \
      -H 'Content-Type: application/json' \
      -d '{"model":"'"${model_identifier}"'","messages":[{"role":"user","content":"Reply with the single word: ready."}]}' \
      2>>"${forward_log}" || true)"
  else
    status="$(curl -sS -o "${body_native}" -w '%{http_code}' \
      --max-time "$((request_timeout_ms / 1000))" \
      "${base}${path}" 2>>"${forward_log}" || true)"
  fi
  ended="$(epoch_ms)"
  [ -f "${body}" ] || : >"${body}"

  INFEROPS_PROBE_PHASE="${phase}" \
    INFEROPS_PROBE_ROUND="${round}" \
    INFEROPS_PROBE_ID="${probe_id}" \
    INFEROPS_PROBE_TIER="${tier}" \
    INFEROPS_PROBE_METHOD="${method}" \
    INFEROPS_PROBE_PATH="${path}" \
    INFEROPS_PROBE_AT="${started}" \
    INFEROPS_PROBE_LATENCY="$((ended - started))" \
    INFEROPS_PROBE_STATUS="${status:-0}" \
    python - "$(inferops::native_path "${body}")" >>"${probes_file}" <<'PROBE_PYTHON'
import hashlib
import json
import os
import sys
from pathlib import Path

raw = Path(sys.argv[1]).read_bytes()
detail = "no body"
code = None
condition = None
retryable = None
tokens = None
document = None
if raw:
    try:
        document = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        document = None

if isinstance(document, dict):
    nested = document.get("error")
    if isinstance(document.get("code"), str):
        # The platform API's canonical envelope, which is flat: the code, the
        # message, and the retryable flag are members of the body itself, and the
        # condition that produced them is under "details". The request and
        # correlation identifiers beside them are deliberately not read: they are
        # per-request values and this record is published.
        code = str(document["code"])
        flag = document.get("retryable")
        retryable = flag if isinstance(flag, bool) else None
        details = document.get("details")
        if isinstance(details, dict) and isinstance(details.get("conditionId"), str):
            condition = str(details["conditionId"])
        detail = str(document.get("message") or code)
    elif isinstance(nested, dict):
        # llama.cpp's own envelope, which is nested and whose "code" is a status
        # number rather than a canonical code. It is kept apart from the API's on
        # purpose: reading it as a canonical code would put a runtime's vocabulary
        # into a field this repository defines.
        detail = str(nested.get("message") or nested.get("type") or "error")
        condition = str(nested.get("type")) if nested.get("type") else None
    elif isinstance(document.get("status"), str):
        # Either health surface. The API adds the adapter kind and its lifecycle
        # state, and both say which half of the readiness conjunction was false.
        parts = [str(document["status"])]
        for key in ("adapterKind", "state"):
            if isinstance(document.get(key), str):
                parts.append(f"{key}={document[key]}")
        detail = ", ".join(parts)
    elif isinstance(document.get("choices"), list) and document["choices"]:
        usage = document.get("usage") or {}
        raw_tokens = usage.get("completion_tokens") if isinstance(usage, dict) else None
        tokens = int(raw_tokens) if isinstance(raw_tokens, int) else None
        choice = document["choices"][0]
        reason = choice.get("finish_reason") if isinstance(choice, dict) else None
        # The completion's text is deliberately not read, not hashed into this field,
        # and not written anywhere this workflow keeps.
        detail = f"served, finish_reason={reason}"
    else:
        detail = "object with no code, error, status, or choices"

line = {
    "phase": os.environ["INFEROPS_PROBE_PHASE"],
    "round": int(os.environ["INFEROPS_PROBE_ROUND"]),
    "probeId": os.environ["INFEROPS_PROBE_ID"],
    "tier": os.environ["INFEROPS_PROBE_TIER"],
    "method": os.environ["INFEROPS_PROBE_METHOD"],
    "path": os.environ["INFEROPS_PROBE_PATH"],
    "atEpochMs": int(os.environ["INFEROPS_PROBE_AT"]),
    "latencyMs": int(os.environ["INFEROPS_PROBE_LATENCY"]),
    "status": int(os.environ["INFEROPS_PROBE_STATUS"]),
    "errorCode": code,
    "conditionId": condition,
    "retryable": retryable,
    "detail": detail[:200],
    "bodyBytes": len(raw),
    "bodySha256": hashlib.sha256(raw).hexdigest() if raw else None,
    "outputTokens": tokens,
}
sys.stdout.write(json.dumps(line, sort_keys=True) + "\n")
PROBE_PYTHON
}

probe_round() {
  local phase="${1:?probe_round needs the phase it is asking in}"
  local round="${2:?probe_round needs its round number}"
  local row
  while IFS= read -r row; do
    [ -n "${row}" ] || continue
    # shellcheck disable=SC2086
    set -- ${row}
    probe_once "${phase}" "${round}" "$1" "$2" "$3" "$4"
  done <<<"${probe_rows}"
}

model_identifier="$(require_query "the model identity the API checks against" \
  inferops::target_kubectl get configmap "${configmap_name}" -n "${INFEROPS_RELEASE_NAMESPACE}" \
  -o 'jsonpath={.data.INFEROPS_MODEL_IDENTIFIER}')"

# --- readiness sampling, from four places that disagree -----------------------

ready_endpoint_count() {
  inferops::target_kubectl get endpointslices -n "${INFEROPS_RELEASE_NAMESPACE}" \
    -l "kubernetes.io/service-name=$1" \
    -o 'jsonpath={range .items[*].endpoints[*]}{.conditions.ready}{"\n"}{end}' |
    tr -d '\r' | grep -c '^true$' || true
}

component_ready_count() {
  inferops::target_kubectl get pods -n "${INFEROPS_RELEASE_NAMESPACE}" \
    -l "app.kubernetes.io/component=$1,${INFEROPS_RELEASE_SELECTOR}" \
    -o 'jsonpath={range .items[*]}{range .status.conditions[?(@.type=="Ready")]}{.status}{end}{"\n"}{end}' |
    tr -d '\r' | grep -c '^True$' || true
}

component_restart_count() {
  inferops::target_kubectl get pods -n "${INFEROPS_RELEASE_NAMESPACE}" \
    -l "app.kubernetes.io/component=$1,${INFEROPS_RELEASE_SELECTOR}" \
    -o "jsonpath={range .items[*]}{.status.containerStatuses[?(@.name==\"$2\")].restartCount}{\"\n\"}{end}" |
    tr -d '\r' | awk 'BEGIN { total = 0 } /^[0-9]+$/ { if ($1 > total) total = $1 } END { print total }'
}

number_or_zero() {
  case "$1" in
    '' | *[!0-9]*) printf '0' ;;
    *) printf '%s' "$1" ;;
  esac
}

sample_readiness() {
  local phase="${1:?sample_readiness needs the phase it is sampling}"
  local start end runtime_present runtime_ready runtime_endpoints
  local api_ready api_endpoints runtime_restarts api_restarts names
  start="$(epoch_ms)"
  names="$(component_pod_names "${runtime_component}" || true)"
  runtime_present="$(count_lines "${names}")"
  runtime_ready="$(component_ready_count "${runtime_component}" || true)"
  runtime_endpoints="$(ready_endpoint_count "${runtime_service}" || true)"
  api_ready="$(component_ready_count "${api_component}" || true)"
  api_endpoints="$(ready_endpoint_count "${api_service}" || true)"
  runtime_restarts="$(component_restart_count "${runtime_component}" runtime || true)"
  api_restarts="$(component_restart_count "${api_component}" api || true)"
  end="$(epoch_ms)"
  printf '%s %s %s %s %s %s %s %s %s %s\n' \
    "${start}" "$((end - start))" "${phase}" \
    "$(number_or_zero "${runtime_present}")" \
    "$(number_or_zero "${runtime_ready}")" \
    "$(number_or_zero "${runtime_endpoints}")" \
    "$(number_or_zero "${api_ready}")" \
    "$(number_or_zero "${api_endpoints}")" \
    "$(number_or_zero "${runtime_restarts}")" \
    "$(number_or_zero "${api_restarts}")" >>"${readiness_samples}"
}

# One loop, two cadences. Readiness is sampled every poll interval and a probe round
# is sent whenever a round interval has elapsed since the last one, so the two are on
# one clock and a sample is never taken between two halves of a round.
observe_window() {
  local phase="${1:?observe_window needs the phase it is observing}"
  local window_seconds="${2:?observe_window needs a window length}"
  local deadline=$((SECONDS + window_seconds))
  local round=0
  local next_round_at=0
  local sample_sleep="$((poll_interval_ms / 1000)).$(printf '%03d' $((poll_interval_ms % 1000)))"
  while :; do
    sample_readiness "${phase}"
    if [ "${SECONDS}" -ge "${next_round_at}" ]; then
      round=$((round + 1))
      probe_round "${phase}" "${round}"
      next_round_at=$((SECONDS + round_interval_ms / 1000))
    fi
    [ "${SECONDS}" -lt "${deadline}" ] || break
    sleep "${sample_sleep}"
  done
  inferops::log "${phase}: ${round} probe round(s) over ${window_seconds} s."
}

inferops::section "Idle baseline (${idle_seconds} s, no requests)"
idle_start="$(epoch_ms)"
sleep "${idle_seconds}"
idle_end="$(epoch_ms)"

inferops::section "Holding the release unready for ${unready_window_seconds} s"
inferops::log "sampling readiness every ${poll_interval_ms} ms and asking every registered surface every ${round_interval_ms} ms. Nothing is changed while this runs."
unready_start_ms="$(epoch_ms)"
observe_window unready "${unready_window_seconds}"
unready_end_ms="$(epoch_ms)"

# --- the diagnostics an operator would look at --------------------------------

inferops::section "Capturing diagnostics"

capture() {
  local capture_id="${1:?capture needs a capture id}"
  local phase="${2:?capture needs the phase it was taken in}"
  shift 2
  local path="${capture_dir}/${capture_id}.txt"
  if ! "$@" >"${path}" 2>&1; then
    inferops::warn "the '${capture_id}' capture reported a failure; what it wrote is kept."
  fi
  tr -d '\r' <"${path}" >"${path}.clean" && mv "${path}.clean" "${path}"
  printf '%s %s %s\n' "${capture_id}" "${phase}" "$(inferops::native_path "${path}")" >>"${capture_dir}/index.txt"
}

: >"${capture_dir}/index.txt"
capture runtime-describe unready inferops::target_kubectl describe pod "${runtime_pod}" \
  -n "${INFEROPS_RELEASE_NAMESPACE}"
capture runtime-log unready inferops::target_kubectl logs "${runtime_pod}" -c runtime \
  -n "${INFEROPS_RELEASE_NAMESPACE}" --tail="${log_tail_lines}"
capture api-log unready inferops::target_kubectl logs "${api_pod}" -c api \
  -n "${INFEROPS_RELEASE_NAMESPACE}" --tail="${log_tail_lines}"
capture api-readiness-body unready curl -sS --max-time "$((request_timeout_ms / 1000))" \
  "http://${forward_host}:${api_forward_port}/health/ready"
capture runtime-resources unready inferops::target_kubectl get deployment "${runtime_deployment}" \
  -n "${INFEROPS_RELEASE_NAMESPACE}" \
  -o 'jsonpath={range .spec.template.spec.containers[*]}{.name}{" requests="}{.resources.requests}{" limits="}{.resources.limits}{"\n"}{end}'

# Built by the record tool rather than here, because deciding what of a capture is
# publishable is the same decision the record's own privacy check makes, and there
# may be only one definition of it.
(cd "${INFEROPS_ROOT}" && python -m "${INFEROPS_EXPERIMENT_MODULE}" diagnostics --run-dir "$(inferops::native_path "${run_dir}")" --excerpt-lines "${INFEROPS_EXCERPT_LINES}")

# --- the fix: one value, one upgrade, the same release ------------------------

inferops::section "Correcting the values and upgrading"
inferops::log "the same release, the same namespace, the same claim, and the same model. The overlay is dropped and nothing else changes."

# The forwards are left open across the upgrade. The API's pod and the collector's are
# not replaced by it, so their forwards are still pointed at the right thing
# afterwards; only the serving runtime's pod is replaced, and only its forward is
# re-opened -- on a port of its own, because the one it is using now will not be free.
upgrade_issued_ms="$(epoch_ms)"
inferops::target_helm upgrade "${INFEROPS_RELEASE_NAME}" "${chart_path}" --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
  "${values_arguments[@]}"

# Waits for the tier to have exactly one pod that is not terminating and for *that*
# pod to report itself Ready. When a fourth argument is given, that pod must also not
# be the one it names.
#
# Not "any ready pod of this component", which is what an earlier version asked and
# which a complete execution of this experiment caught being wrong: the predecessor is
# still there during a rolling update, and the serving runtime's predecessor here is a
# pod whose starved load can finish while the replacement's has not started. Waiting on
# the aggregate stamped the recovery from the misconfigured pod and let it serve the
# completions that were supposed to establish the fix.
#
# The fourth argument is given for the serving runtime and withheld for the platform
# API, and the difference is a fact about the chart rather than a convenience. The
# overlay changes the runtime container's resources, so the runtime's pod template
# changes and its pod is replaced. It changes nothing the API's template or its
# configuration checksum is built from, so the API's pod is the same pod throughout and
# becomes Ready when its adapter can reach a runtime that is -- and a second execution
# of this experiment waited fifteen minutes for an API pod that was never going to be
# replaced before it was stopped by hand.
wait_for_replacement_ready() {
  local component="$1" budget_ms="$2" label="$3" previous="${4:-}"
  local deadline=$((SECONDS + budget_ms / 1000))
  local names count pod ready
  while [ "${SECONDS}" -lt "${deadline}" ]; do
    if names="$(live_pod_names "${component}")"; then
      count="$(count_lines "${names}")"
      pod="$(printf '%s\n' "${names}" | head -1)"
      if [ "${count}" = "1" ] && [ "${pod}" != "${previous}" ]; then
        ready="$(pod_field "${pod}" '{range .status.conditions[?(@.type=="Ready")]}{.status}{end}' || true)"
        if [ "${ready}" = "True" ]; then
          inferops::log "${label} pod '${pod}' reports itself Ready."
          return 0
        fi
      fi
    fi
    sleep 5
  done
  inferops::fail "no ready ${label} within $((budget_ms / 1000)) s of the upgrade."
}

inferops::section "Waiting for the model to load"
wait_for_replacement_ready "${runtime_component}" "${recovery_rollout_budget_ms}" \
  "the serving runtime" "${unready_runtime_pod}"
runtime_ready_ms="$(epoch_ms)"

inferops::section "Waiting for the platform API to report its adapter able"
wait_for_replacement_ready "${api_component}" "${recovery_rollout_budget_ms}" \
  "the platform API"
api_ready_ms="$(epoch_ms)"

# The serving runtime's pod is replaced by the upgrade and the API's is not, so the
# runtime's is looked up again and only its forward is re-opened. The API's forward is
# still pointed at the pod it was pointed at before, which is the pod that is there.
runtime_pod="$(require_query "the replaced serving runtime pod" one_pod_of "${runtime_component}")"
inferops::section "Opening a forward against the replaced serving runtime pod"
if [ -n "${runtime_forward_pid}" ] && kill -0 "${runtime_forward_pid}" 2>/dev/null; then
  kill "${runtime_forward_pid}" 2>/dev/null || true
fi
runtime_forward_pid=""
runtime_probe_port="${recovered_runtime_forward_port}"
open_runtime_forward_when_listening

recovered_runtime_uid="$(require_query "the recovered serving runtime pod uid" pod_field "${runtime_pod}" '{.metadata.uid}')"
recovered_init_name="$(require_query "the recovered integrity init container" pod_field "${runtime_pod}" '{.status.initContainerStatuses[0].name}')"
recovered_init_exit="$(require_query "the recovered integrity init exit code" pod_field "${runtime_pod}" '{.status.initContainerStatuses[0].state.terminated.exitCode}')"

inferops::section "Asking the same surfaces again for ${recovered_window_seconds} s"
recovered_start_ms="$(epoch_ms)"
observe_window recovered "${recovered_window_seconds}"
recovered_end_ms="$(epoch_ms)"

dump_json deployments-recovered.json inferops::target_kubectl get deployments \
  -n "${INFEROPS_RELEASE_NAMESPACE}" -l "${INFEROPS_RELEASE_SELECTOR}" -o json
dump_json pods-recovered.json inferops::target_kubectl get pods \
  -n "${INFEROPS_RELEASE_NAMESPACE}" -l "${INFEROPS_RELEASE_SELECTOR}" -o json
dump_json helm-release.json inferops::target_helm list --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
  --filter "^${INFEROPS_RELEASE_NAME}\$" -o json

inferops::log "settling ${settle_seconds} s so the collector scrapes every counter"
sleep "${settle_seconds}"
settled_ms="$(epoch_ms)"

if ! jobs_after="$(acquisition_job_count)"; then
  inferops::fail "could not count the acquisition Jobs after the upgrade."
fi
revision_after="$(require_query "the release revision after the fix" release_revision)"

# --- what the script stamped ---------------------------------------------------

INFEROPS_IDLE_START="${idle_start}" \
  INFEROPS_IDLE_END="${idle_end}" \
  INFEROPS_INSTALL_ISSUED="${install_issued_ms}" \
  INFEROPS_RUNTIME_RUNNING="${runtime_container_running_ms}" \
  INFEROPS_RUNTIME_SOCKET_OPEN="${install_socket_open_ms}" \
  INFEROPS_UNREADY_START="${unready_start_ms}" \
  INFEROPS_UNREADY_END="${unready_end_ms}" \
  INFEROPS_UPGRADE_ISSUED="${upgrade_issued_ms}" \
  INFEROPS_RUNTIME_READY="${runtime_ready_ms}" \
  INFEROPS_API_READY="${api_ready_ms}" \
  INFEROPS_RECOVERED_START="${recovered_start_ms}" \
  INFEROPS_RECOVERED_END="${recovered_end_ms}" \
  INFEROPS_SETTLED="${settled_ms}" \
  INFEROPS_UNREADY_POD_NAME="${unready_runtime_pod}" \
  INFEROPS_UNREADY_POD_UID="${runtime_pod_uid}" \
  INFEROPS_UNREADY_STARTED_AT="${runtime_started_at}" \
  INFEROPS_UNREADY_INIT_NAME="${runtime_init_name}" \
  INFEROPS_UNREADY_INIT_EXIT="${runtime_init_exit}" \
  INFEROPS_RECOVERED_POD_NAME="${runtime_pod}" \
  INFEROPS_RECOVERED_POD_UID="${recovered_runtime_uid}" \
  INFEROPS_RECOVERED_INIT_NAME="${recovered_init_name}" \
  INFEROPS_RECOVERED_INIT_EXIT="${recovered_init_exit}" \
  INFEROPS_REVISION_BEFORE="${revision_before}" \
  INFEROPS_REVISION_AFTER="${revision_after}" \
  INFEROPS_JOBS_BEFORE="${jobs_before}" \
  INFEROPS_JOBS_AFTER="${jobs_after}" \
  INFEROPS_CLAIMS_BEFORE="${claims_before}" \
  python - "$(inferops::native_path "${lifecycle_file}")" <<'LIFECYCLE_PYTHON'
import json
import os
import sys
from pathlib import Path


def fact(name: str) -> str:
    return os.environ.get(f"INFEROPS_{name}", "").strip()


def number(name: str) -> int:
    value = fact(name)
    if not value.lstrip("-").isdigit():
        raise SystemExit(f"the {name.lower()} stamp is not a number: {value!r}")
    return int(value)


document = {
    "idleBaseline": {
        "startEpochMs": number("IDLE_START"),
        "endEpochMs": number("IDLE_END"),
    },
    "install": {
        "issuedEpochMs": number("INSTALL_ISSUED"),
        "runtimeContainerRunningEpochMs": number("RUNTIME_RUNNING"),
        "runtimeSocketOpenEpochMs": number("RUNTIME_SOCKET_OPEN"),
        "runtimePodName": fact("UNREADY_POD_NAME"),
        "runtimePodUid": fact("UNREADY_POD_UID"),
        "runtimeContainerStartedAt": fact("UNREADY_STARTED_AT"),
        "initContainerName": fact("UNREADY_INIT_NAME"),
        "initExitCode": number("UNREADY_INIT_EXIT"),
    },
    "unreadyWindow": {
        "startEpochMs": number("UNREADY_START"),
        "endEpochMs": number("UNREADY_END"),
    },
    "upgrade": {
        "issuedEpochMs": number("UPGRADE_ISSUED"),
        "runtimeReadyEpochMs": number("RUNTIME_READY"),
        "apiReadyEpochMs": number("API_READY"),
        "runtimePodName": fact("RECOVERED_POD_NAME"),
        "runtimePodUid": fact("RECOVERED_POD_UID"),
        "initContainerName": fact("RECOVERED_INIT_NAME"),
        "initExitCode": number("RECOVERED_INIT_EXIT"),
    },
    "recoveredWindow": {
        "startEpochMs": number("RECOVERED_START"),
        "endEpochMs": number("RECOVERED_END"),
    },
    "settledEpochMs": number("SETTLED"),
    "release": {
        "revisionBefore": number("REVISION_BEFORE"),
        "revisionAfter": number("REVISION_AFTER"),
    },
    "acquisition": {
        "jobCountBefore": number("JOBS_BEFORE"),
        "jobCountAfter": number("JOBS_AFTER"),
    },
    # The claim count after the uninstall is written by the teardown below; this run
    # has not reached it yet, so the before figure stands in for both and the teardown
    # overwrites the pair.
    "claims": {
        "countBefore": number("CLAIMS_BEFORE"),
        "countAfter": number("CLAIMS_BEFORE"),
    },
    # Exactly one, registered in advance. A model that cannot load is not a state the
    # Deployment controller reverses, so this experiment does not pretend it expected
    # nobody to act; it names what the one action was. A test reads this script to
    # establish that the upgrade and the uninstall are the only mutating commands
    # after the install.
    "interventions": ["corrected-the-values-and-upgraded"],
}
Path(sys.argv[1]).write_text(
    json.dumps(document, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
    newline="\n",
)
LIFECYCLE_PYTHON

python - "$(inferops::native_path "${readiness_samples}")" "$(inferops::native_path "${readiness_file}")" <<'READINESS_PYTHON'
import json
import sys
from pathlib import Path

samples = []
for line in Path(sys.argv[1]).read_text(encoding="utf-8").splitlines():
    if not line.strip():
        continue
    (
        at,
        took,
        phase,
        runtime_present,
        runtime_ready,
        runtime_endpoints,
        api_ready,
        api_endpoints,
        runtime_restarts,
        api_restarts,
    ) = line.split(" ")
    samples.append(
        {
            "atEpochMs": int(at),
            "readTookMs": int(took),
            "phase": phase,
            "runtimePodsPresent": int(runtime_present),
            "runtimePodsReady": int(runtime_ready),
            "runtimeEndpointsReady": int(runtime_endpoints),
            "apiPodsReady": int(api_ready),
            "apiEndpointsReady": int(api_endpoints),
            "runtimeRestartCount": int(runtime_restarts),
            "apiRestartCount": int(api_restarts),
        }
    )
Path(sys.argv[2]).write_text(
    json.dumps({"readiness": {"samples": samples}}, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
    newline="\n",
)
READINESS_PYTHON

inferops::section "Asking the collector what it saw"
(cd "${INFEROPS_ROOT}" && python -m "${INFEROPS_EXPERIMENT_MODULE}" telemetry \
  --run-dir "$(inferops::native_path "${run_dir}")" \
  --collector-url "http://${forward_host}:${collector_forward_port}")

close_forwards

# --- teardown ----------------------------------------------------------------

inferops::section "Uninstalling the release"

inferops::target_helm uninstall "${INFEROPS_RELEASE_NAME}" --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
  --wait --timeout "$((uninstall_budget_ms / 1000))s"
release_installed=0

inferops::section "Residue"

residue_deadline=$((SECONDS + uninstall_budget_ms / 1000))
remaining_count=0
while :; do
  if ! remaining="$(inferops::target_kubectl get \
    deployments,replicasets,services,configmaps,serviceaccounts,pods,networkpolicies,jobs,roles,rolebindings \
    -n "${INFEROPS_RELEASE_NAMESPACE}" -l "${INFEROPS_RELEASE_SELECTOR}" -o name)"; then
    inferops::fail "could not ask what survived the uninstall. An unanswered query is not an empty result."
  fi
  remaining_count="$(printf '%s' "${remaining}" | grep -c . || true)"
  [ "${remaining_count}" != "0" ] || break
  if [ "${SECONDS}" -ge "${residue_deadline}" ]; then
    printf '%s\n' "${remaining}"
    inferops::fail "${remaining_count} object(s) carrying the release's instance label survived the uninstall."
  fi
  sleep 2
done

if ! claims_after="$(claim_count)"; then
  inferops::fail "could not count the persistent volume claims after uninstalling. An unanswered query is not an empty result."
fi
[ "${claims_after}" = "${claims_before}" ] ||
  inferops::fail "the claim count changed across the release: ${claims_before} before, ${claims_after} after. This chart must neither create nor delete a claim, and the model cache is Terraform's."

INFEROPS_CLAIMS_AFTER="${claims_after}" \
  python - "$(inferops::native_path "${lifecycle_file}")" <<'CLAIMS_PYTHON'
import json
import os
import sys
from pathlib import Path

path = Path(sys.argv[1])
document = json.loads(path.read_text(encoding="utf-8"))
document["claims"]["countAfter"] = int(os.environ["INFEROPS_CLAIMS_AFTER"])
path.write_text(
    json.dumps(document, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
    newline="\n",
)
CLAIMS_PYTHON

inferops::log "no object with the release's instance label remains; the namespace and the model cache claim were left in place."

# --- the record ----------------------------------------------------------------

inferops::section "Building the record"

set +e
(cd "${INFEROPS_ROOT}" && python -m "${INFEROPS_EXPERIMENT_MODULE}" record --run-dir "$(inferops::native_path "${run_dir}")")
record_code=$?
set -e

case "${record_code}" in
  0) inferops::log "the record is usable: every readiness, liveness, refusal, diagnostic, and recovery check passed." ;;
  6) inferops::fail "the record was written and is not usable; its checks name what failed. The release is already uninstalled." ;;
  *) inferops::fail "the record could not be built (exit ${record_code}). The run's inputs are kept in ${evidence_rel}/." ;;
esac

inferops::section "Result"
inferops::log "record        ${evidence_rel}/record/unready-model-record.v1alpha1.json (labelled local real Kubernetes)"
inferops::log "one release was installed with a model it could not load in time, held there while every registered surface was asked, and got back by correcting one value and upgrading. Nothing in it is an availability figure, a service-level objective, or a recovery-time objective."
inferops::log "the namespace and the model cache claim survived. Reclaiming them is scripts/environment/terraform-prerequisites.sh destroy --confirm, and nothing here does it for you."
