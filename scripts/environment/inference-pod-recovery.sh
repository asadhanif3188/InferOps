#!/usr/bin/env bash
# Deletes one inference pod while real traffic is running, and keeps enough to say
# what callers and operators saw: the raw load records either side of the deletion,
# what readiness looked like from the Service's own endpoints, the instants the
# replacement reached each stage, and what the release's collector could answer.
#
# What it establishes, and what it does not. It produces bounded observations of one
# serving runtime pod lost once, under one load profile, on one provider and one host
# (ADR 0013). It is not an availability figure, a service-level objective, an error
# budget, or a recovery benchmark, and tools/inference_pod_recovery refuses a record
# that does not carry that boundary.
#
# The question this asks, and the one it does not repeat. V1-S3-003-PR2 proved that
# the model artifact survives a pod replacement, and stated as its own limitation that
# nothing there measured the replacement window from a caller's side. This measures
# exactly that. It does not re-prove persistence: it never compares the artifact's
# inode or modification time, and the record says so rather than implying otherwise.
#
# Why the load runs twice. A refused request comes back far faster than a served one,
# so one run of the committed profile spends its whole remaining request budget within
# seconds of losing the pod and ends before anything is ready again. The first run is
# the disrupted one and measures what the loss cost callers; the second starts once the
# replacement reports Ready and measures what callers get back, at the same concurrency
# levels, which is what makes the before and after figures comparable at all.
#
# What it operates. It applies the Terraform prerequisite layer through
# scripts/environment/terraform-prerequisites.sh, installs one Helm release named by
# INFEROPS_RELEASE_NAME in INFEROPS_RELEASE_NAMESPACE, opens two loopback forwards
# (the API and the collector), sends the committed load profile through the first with
# tools.llm_load twice, deletes exactly one pod by name while the first of those is
# mid-flight, and uninstalls the release when it is done. It never removes the namespace, the model
# cache claim, or the cluster: those outlive a release by design
# (docs/architecture/resource-ownership.md).
#
# What the one delete touches. One pod, addressed by the name the cluster gave it,
# with --wait=false and no label selector. No Deployment, no claim, no release
# revision, no cluster-scoped object, and nothing in another namespace. The pod is
# located by counting rather than by indexing, so a release that somehow has two
# serving pods refuses instead of choosing one.
#
# What a person had to do. The two authorisations are given before the run: the
# confirmation flag and the values file. Between the delete and the uninstall this
# script issues no mutating command at all, which is what lets the record say the
# Deployment controller did the recovering. A test reads this file to establish it.
#
# The assertions and the record are not here. They are in
# tools/inference_pod_recovery, which reads the committed descriptor, refuses a
# collector URL that is not loopback, slices the raw load records against the instants
# below, and writes the labelled record. The split is the one the other Kubernetes
# workflows here use: the guard that establishes which cluster is being acted on
# already lives in lib.sh, and a second implementation of it in Python would be a
# second guard.
#
# On failure it collects diagnostics into .artifacts/, leaves the release in place for
# inspection, and says how to remove it.
#
# Usage:
#   scripts/environment/inference-pod-recovery.sh check
#   scripts/environment/inference-pod-recovery.sh run --values PATH [--values PATH ...] \
#     --confirm-real-kubernetes

# shellcheck source=scripts/environment/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

readonly INFEROPS_EXPERIMENT_REL="deploy/serving/experiments/inference-pod-recovery.v1.json"
readonly INFEROPS_EXPERIMENT_MODULE="tools.inference_pod_recovery"

# Where tools.llm_load writes a real run's raw record set. It is cleared before the
# run starts, because a set left by an earlier one would be copied as this run's.
readonly INFEROPS_LOAD_RAW_REL=".cache/inferops/load/real/raw.jsonl"

# How much of each container's log a failure keeps. Not a threshold.
readonly INFEROPS_LOG_TAIL="200"

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
      [ "$#" -ge 2 ] || inferops::fail "--values needs a path. Usage: inference-pod-recovery.sh run --values PATH [--values PATH ...] --confirm-real-kubernetes"
      values_files+=("$2")
      shift 2
      ;;
    --confirm-real-kubernetes)
      confirmed=1
      shift
      ;;
    *)
      inferops::fail "unknown argument '$1'. Usage: inference-pod-recovery.sh check|run [--values PATH ...] [--confirm-real-kubernetes]"
      ;;
  esac
done

[ -n "${action}" ] ||
  inferops::fail "expected one of check, run. Usage: inference-pod-recovery.sh check|run [--values PATH ...] [--confirm-real-kubernetes]"

inferops::require_cmd python

experiment_file="${INFEROPS_ROOT}/${INFEROPS_EXPERIMENT_REL}"
[ -f "${experiment_file}" ] ||
  inferops::fail "no experiment descriptor at ${INFEROPS_EXPERIMENT_REL}"

# --- check: reads files, contacts nothing -----------------------------------

if [ "${action}" = "check" ]; then
  inferops::section "Recovery experiment"
  (cd "${INFEROPS_ROOT}" && python -m "${INFEROPS_EXPERIMENT_MODULE}" check)
  inferops::log "the descriptor validated. Nothing was contacted, no release was installed, and no pod was deleted."
  exit 0
fi

# --- everything below reaches a cluster, a real model, and one running pod ---

[ "${confirmed}" -eq 1 ] ||
  inferops::fail "run needs --confirm-real-kubernetes. It applies the Terraform prerequisites, installs a release, loads a real model, sends real inference load, and deletes a running pod. Usage: inference-pod-recovery.sh run --values PATH [--values PATH ...] --confirm-real-kubernetes"

[ "${#values_files[@]}" -gt 0 ] ||
  inferops::fail "--values is required. The chart's shipped defaults select no serving profile and are refused on purpose. See docs/serving/inference-pod-recovery.md."

values_arguments=()
for values_file in "${values_files[@]}"; do
  [ -f "${values_file}" ] || inferops::fail "no such values file: ${values_file}"
  values_arguments+=(--values "$(inferops::native_path "$(cd "$(dirname "${values_file}")" && pwd)/$(basename "${values_file}")")")
done

inferops::require_cmd kubectl
inferops::require_cmd helm
inferops::require_cmd terraform
inferops::require_engine
# The provider-aware target this project consumes rather than creates
# (docs/environment/local-cluster-provider-contract.md): an explicit
# INFEROPS_PROVIDER, re-verified now rather than trusted from an earlier run.
inferops::resolve_target

inferops::section "Recovery experiment"
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
  release.name release.namespace release.apiServiceName release.apiServicePort \
  release.apiDeploymentName release.runtimeDeploymentName release.runtimeServiceName \
  release.collectorServiceName release.collectorServicePort release.collectorDeploymentName \
  release.configMapName release.runtimeComponent release.acquisitionComponent \
  disruption.issueAfterLoadStartMs observation.pollIntervalMs observation.minimumSamples \
  schedule.idleBaselineSeconds schedule.settleBetweenRunsSeconds \
  schedule.settleAfterRunSeconds \
  readiness.runtimeRolloutBudgetMs readiness.apiRolloutBudgetMs \
  readiness.collectorRolloutBudgetMs readiness.forwardBudgetMs \
  readiness.replacementBudgetMs readiness.uninstallBudgetMs \
  forwards.host forwards.apiPort forwards.collectorPort \
  evidence.directory evidence.lifecycleFile evidence.readinessFile \
  evidence.disruptedRawFile evidence.recoveredRawFile)"; then
  inferops::fail "the experiment descriptor could not be read after it validated. Nothing was installed."
fi

{
  read -r descriptor_release
  read -r descriptor_namespace
  read -r api_service
  read -r api_service_port
  read -r api_deployment
  read -r runtime_deployment
  read -r runtime_service
  read -r collector_service
  read -r collector_service_port
  read -r collector_deployment
  read -r configmap_name
  read -r runtime_component
  read -r acquisition_component
  read -r disruption_offset_ms
  read -r poll_interval_ms
  read -r minimum_samples
  read -r idle_seconds
  read -r settle_between_seconds
  read -r settle_seconds
  read -r runtime_rollout_budget_ms
  read -r api_rollout_budget_ms
  read -r collector_rollout_budget_ms
  read -r forward_budget_ms
  read -r replacement_budget_ms
  read -r uninstall_budget_ms
  read -r forward_host
  read -r api_forward_port
  read -r collector_forward_port
  read -r evidence_rel
  read -r lifecycle_name
  read -r readiness_name
  read -r disrupted_raw_name
  read -r recovered_raw_name
} <<<"${descriptor_fields}"

# Every value that reaches arithmetic, a timeout, or a port is held to being a number
# here, at the point of use. The Python validator refuses the same, in another file: a
# guard whose correctness depends on the order two programs run in is a guard waiting
# to be reordered.
for number in api_service_port collector_service_port disruption_offset_ms \
  poll_interval_ms minimum_samples idle_seconds settle_between_seconds settle_seconds \
  runtime_rollout_budget_ms api_rollout_budget_ms collector_rollout_budget_ms \
  forward_budget_ms replacement_budget_ms uninstall_budget_ms \
  api_forward_port collector_forward_port; do
  case "${!number}" in
    '' | *[!0-9]*) inferops::fail "the experiment descriptor's '${number}' is not a number. Nothing was installed." ;;
  esac
done
[ "${poll_interval_ms}" -ge 1000 ] ||
  inferops::fail "the descriptor samples readiness every ${poll_interval_ms} ms; below 1000 ms this loop would spin against the API server. Nothing was installed."

for name in api_service api_deployment runtime_deployment runtime_service \
  collector_service collector_deployment configmap_name runtime_component \
  acquisition_component; do
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
lifecycle_file="${run_dir}/${lifecycle_name}"
readiness_file="${run_dir}/${readiness_name}"
readiness_samples="${run_dir}/readiness-samples.txt"
disrupted_raw_file="${run_dir}/${disrupted_raw_name}"
recovered_raw_file="${run_dir}/${recovered_raw_name}"
diag_dir="${INFEROPS_ARTIFACT_DIR}/inference-pod-recovery"
forward_log="${diag_dir}/forward.log"
load_log="${diag_dir}/load.log"

# A run directory is never overwritten. An earlier run's evidence is either already
# promoted or still wanted, and this script cannot tell which.
if [ -e "${run_dir}" ]; then
  inferops::fail "the run directory ${evidence_rel} already exists. Move it aside before a new run. Nothing was installed."
fi

# Wall-clock milliseconds from bash's own clock, with no process started to read it.
# tools.llm_load reads the same host clock for startedAtEpochMs, which is what lets a
# request be placed against the moment the delete was issued.
epoch_ms() {
  local micros="${EPOCHREALTIME/[.,]/}"
  printf '%s' "$((micros / 1000))"
}
[ -n "${EPOCHREALTIME:-}" ] ||
  inferops::fail "this shell has no EPOCHREALTIME (bash 5 or later is needed). Nothing was installed."

api_forward_pid=""
collector_forward_pid=""
load_pid=""
release_installed=0

# --- diagnostics and teardown ------------------------------------------------

collect_diagnostics() {
  mkdir -p "${diag_dir}"
  inferops::warn "collecting diagnostics into .artifacts/inference-pod-recovery/"
  inferops::target_helm list --namespace "${INFEROPS_RELEASE_NAMESPACE}" >"${diag_dir}/releases.txt" 2>&1 || true
  inferops::target_kubectl get all,configmap,pvc,job,endpointslices \
    -n "${INFEROPS_RELEASE_NAMESPACE}" -o wide >"${diag_dir}/get-all.txt" 2>&1 || true
  inferops::target_kubectl describe pods -n "${INFEROPS_RELEASE_NAMESPACE}" >"${diag_dir}/describe-pods.txt" 2>&1 || true
  inferops::target_kubectl get events -n "${INFEROPS_RELEASE_NAMESPACE}" \
    --sort-by=.lastTimestamp >"${diag_dir}/events.txt" 2>&1 || true
  inferops::target_kubectl logs -n "${INFEROPS_RELEASE_NAMESPACE}" \
    -l "${INFEROPS_RELEASE_SELECTOR}" --all-containers --tail="${INFEROPS_LOG_TAIL}" >"${diag_dir}/release.log" 2>&1 || true
}

# Waits for a child to exit for at most the given seconds, then kills it. Cleanup runs
# inside the EXIT trap, and an unbounded wait on a wedged port-forward or a load run
# that will never finish would hang the very path that collects diagnostics.
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

stop_load() {
  if [ -n "${load_pid}" ] && kill -0 "${load_pid}" 2>/dev/null; then
    kill "${load_pid}" 2>/dev/null || true
    wait_bounded "${load_pid}" 30
  fi
  load_pid=""
}

close_forwards() {
  local pid
  for pid in "${api_forward_pid}" "${collector_forward_pid}"; do
    if [ -n "${pid}" ] && kill -0 "${pid}" 2>/dev/null; then
      kill "${pid}" 2>/dev/null || true
      wait_bounded "${pid}" 10
    fi
  done
  api_forward_pid=""
  collector_forward_pid=""
}

on_exit() {
  local rc=$?
  stop_load
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

# INT and TERM as well as EXIT: this run leaves a background load generator, two
# forwards, and a real release behind, and on Git Bash signal delivery to a native
# child is less predictable than on Linux.
trap on_exit INT TERM EXIT

mkdir -p "${diag_dir}" "${cluster_dir}"

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

# --- prerequisites and the release -------------------------------------------

if inferops::target_helm status "${INFEROPS_RELEASE_NAME}" --namespace "${INFEROPS_RELEASE_NAMESPACE}" >/dev/null 2>&1; then
  inferops::fail "release '${INFEROPS_RELEASE_NAME}' already exists in '${INFEROPS_RELEASE_NAMESPACE}'. This experiment starts from its own install, so that the environment it records is the one it made. Remove it first: helm uninstall ${INFEROPS_RELEASE_NAME} --namespace ${INFEROPS_RELEASE_NAMESPACE}"
fi

inferops::section "Applying the Terraform prerequisites"

bash "${INFEROPS_ROOT}/scripts/environment/terraform-prerequisites.sh" apply

if ! claims_before="$(claim_count)"; then
  inferops::fail "could not count the persistent volume claims before installing. An unanswered query is not an empty result."
fi

inferops::section "Installing the release"

# Without --wait and without --create-namespace: the namespace is Terraform's, and
# each tier's readiness is waited for below, one budget each.
release_installed=1
inferops::target_helm install "${INFEROPS_RELEASE_NAME}" "${chart_path}" --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
  "${values_arguments[@]}"

inferops::section "Waiting for the serving runtime to load the model"
inferops::target_kubectl rollout status "deployment/${runtime_deployment}" \
  -n "${INFEROPS_RELEASE_NAMESPACE}" --timeout="$((runtime_rollout_budget_ms / 1000))s"

inferops::section "Waiting for the platform API"
inferops::target_kubectl rollout status "deployment/${api_deployment}" \
  -n "${INFEROPS_RELEASE_NAMESPACE}" --timeout="$((api_rollout_budget_ms / 1000))s"

inferops::section "Waiting for the collector"
inferops::target_kubectl rollout status "deployment/${collector_deployment}" \
  -n "${INFEROPS_RELEASE_NAMESPACE}" --timeout="$((collector_rollout_budget_ms / 1000))s"

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
dump_json helm-release.json inferops::target_helm list --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
  --filter "^${INFEROPS_RELEASE_NAME}\$" -o json
dump_json deployments.json inferops::target_kubectl get deployments \
  -n "${INFEROPS_RELEASE_NAMESPACE}" -l "${INFEROPS_RELEASE_SELECTOR}" -o json
dump_json configmap.json inferops::target_kubectl get configmap "${configmap_name}" \
  -n "${INFEROPS_RELEASE_NAMESPACE}" -o json
dump_json pods-before.json inferops::target_kubectl get pods \
  -n "${INFEROPS_RELEASE_NAMESPACE}" -l "${INFEROPS_RELEASE_SELECTOR}" -o json

# The node container runtime's own description of each template image reference. A
# pod's imageID names one of an image's digests, and one image can carry several -- the
# same build imported twice under two index digests is one image with two names -- so
# the binding from template to running bytes is made through this answer.
template_image() {
  local deployment="$1" container="$2"
  inferops::target_kubectl get deployment "${deployment}" -n "${INFEROPS_RELEASE_NAMESPACE}" \
    -o "jsonpath={.spec.template.spec.containers[?(@.name==\"${container}\")].image}"
}
api_template_image="$(require_query "the API template image" template_image "${api_deployment}" api)"
runtime_template_image="$(require_query "the runtime template image" template_image "${runtime_deployment}" runtime)"
dump_json image-api.json inferops::target_node_exec crictl inspecti "${api_template_image}"
dump_json image-runtime.json inferops::target_node_exec crictl inspecti "${runtime_template_image}"

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
(cd "${INFEROPS_ROOT}" && python -m "${INFEROPS_EXPERIMENT_MODULE}" facts --run-dir "$(inferops::native_path "${run_dir}")")

# --- the forwards ------------------------------------------------------------

# Called directly, never inside a command substitution: the forward must be a child of
# this shell, or close_forwards could neither signal nor wait for it. The pid is handed
# back through `opened_forward_pid`.
opened_forward_pid=""
open_forward() {
  local service="$1" service_port="$2" local_port="$3"
  inferops::target_kubectl port-forward "service/${service}" "${local_port}:${service_port}" \
    -n "${INFEROPS_RELEASE_NAMESPACE}" --address "${forward_host}" >>"${forward_log}" 2>&1 &
  opened_forward_pid="$!"
  local deadline=$((SECONDS + forward_budget_ms / 1000))
  while [ "${SECONDS}" -lt "${deadline}" ]; do
    kill -0 "${opened_forward_pid}" 2>/dev/null ||
      inferops::fail "the port-forward to '${service}' exited before it accepted a connection. Its output is in .artifacts/inference-pod-recovery/forward.log."
    if python -c '
import socket, sys

try:
    socket.create_connection((sys.argv[1], int(sys.argv[2])), 2).close()
except OSError:
    sys.exit(1)
' "${forward_host}" "${local_port}" 2>/dev/null; then
      inferops::log "forward open on http://${forward_host}:${local_port} to service/${service}."
      return 0
    fi
    sleep 1
  done
  inferops::fail "the forward to '${service}' did not accept a connection within $((forward_budget_ms / 1000)) s."
}

inferops::section "Opening the API and collector forwards"
open_forward "${api_service}" "${api_service_port}" "${api_forward_port}"
api_forward_pid="${opened_forward_pid}"
open_forward "${collector_service}" "${collector_service_port}" "${collector_forward_port}"
collector_forward_pid="${opened_forward_pid}"

# The forward to the API is held open across the disruption on purpose. It reaches the
# platform API, which is not the tier this experiment deletes, so what the load records
# afterwards is the API's own answer while its upstream was gone rather than a
# connection that died underneath it.

# --- the baseline, and the pod that will be deleted ---------------------------

inferops::section "Idle baseline (${idle_seconds} s, no load)"
idle_start="$(epoch_ms)"
sleep "${idle_seconds}"
idle_end="$(epoch_ms)"

# The one running serving runtime pod, counted rather than indexed into: a release with
# two would make "the inference pod" ambiguous, and choosing one is exactly the
# decision that must not be made silently.
runtime_pod_names() {
  inferops::target_kubectl get pods -n "${INFEROPS_RELEASE_NAMESPACE}" \
    -l "app.kubernetes.io/component=${runtime_component},${INFEROPS_RELEASE_SELECTOR}" \
    --field-selector=status.phase=Running \
    -o 'jsonpath={range .items[*]}{.metadata.name}{"\n"}{end}' | tr -d '\r'
}

count_lines() { printf '%s\n' "$1" | grep -c . || true; }

if ! baseline_names="$(runtime_pod_names)"; then
  inferops::fail "could not ask which serving runtime pod is running. Nothing was deleted."
fi
baseline_count="$(count_lines "${baseline_names}")"
[ "${baseline_count}" = "1" ] ||
  inferops::fail "expected exactly one running '${runtime_component}' pod and found ${baseline_count}. Nothing was deleted."
baseline_pod="$(printf '%s\n' "${baseline_names}" | head -1)"
case "${baseline_pod}" in
  *[!a-z0-9.-]* | '') inferops::fail "the running '${runtime_component}' pod is named '${baseline_pod}', which is not a name this script will pass to a delete. Nothing was deleted." ;;
esac

pod_field() {
  inferops::target_kubectl get pod "$1" -n "${INFEROPS_RELEASE_NAMESPACE}" -o "jsonpath=$2" | tr -d '\r'
}

baseline_uid="$(require_query "the baseline pod uid" pod_field "${baseline_pod}" '{.metadata.uid}')"
baseline_owner_kind="$(require_query "the baseline pod owner kind" pod_field "${baseline_pod}" '{.metadata.ownerReferences[0].kind}')"
baseline_owner_name="$(require_query "the baseline pod owner name" pod_field "${baseline_pod}" '{.metadata.ownerReferences[0].name}')"
baseline_node="$(require_query "the baseline pod node" pod_field "${baseline_pod}" '{.spec.nodeName}')"

if ! jobs_before="$(acquisition_job_count)"; then
  inferops::fail "could not count the acquisition Jobs before the deletion. The assertion that no hook ran depends on the difference."
fi
revision_before="$(require_query "the release revision before the deletion" release_revision)"

# --- the load, and the one delete --------------------------------------------

inferops::section "Starting the committed load profile (run 1 of 2, the disrupted one)"

load_raw="${INFEROPS_ROOT}/${INFEROPS_LOAD_RAW_REL}"
: >"${load_log}"

# A raw set left by an earlier run would be copied as this one's if this run wrote
# none, so the one path tools.llm_load writes is cleared before each run.
start_load() {
  rm -f "${load_raw}"
  (cd "${INFEROPS_ROOT}" && python -m tools.llm_load run \
    --target-url "http://${forward_host}:${api_forward_port}" \
    --environment-facts "$(inferops::native_path "${run_dir}/facts.json")" \
    --confirm-real-load) >>"${load_log}" 2>&1 &
  load_pid="$!"
}

# Waits for the running load generator, copies its raw set out, and hands back the
# exit code through `finished_exit_code`. The copy happens whatever the exit code,
# because a run that failed is still the run this record has to describe.
finished_exit_code=""
finished_at_ms=""
finish_load() {
  local destination="$1"
  set +e
  wait "${load_pid}"
  finished_exit_code=$?
  set -e
  load_pid=""
  finished_at_ms="$(epoch_ms)"
  [ -f "${load_raw}" ] ||
    inferops::fail "the load run exited ${finished_exit_code} and wrote no raw record set."
  cp "${load_raw}" "${destination}"
}

disrupted_launched="$(epoch_ms)"
start_load
inferops::log "load running in the background; its output is in .artifacts/inference-pod-recovery/load.log."

# Wait out the registered offset rather than watching for a phase to begin: the offset
# is what the descriptor pre-registered, and which phase the delete landed in is a
# result the record reads off the raw set afterwards rather than a thing arranged here.
sleep "$((disruption_offset_ms / 1000))"

kill -0 "${load_pid}" 2>/dev/null ||
  inferops::fail "the load generator exited before the disruption was due. Its output is in .artifacts/inference-pod-recovery/load.log. Nothing was deleted."

if ! current_names="$(runtime_pod_names)"; then
  inferops::fail "could not ask which serving runtime pod is running. Nothing was deleted."
fi
current_count="$(count_lines "${current_names}")"
[ "${current_count}" = "1" ] ||
  inferops::fail "expected exactly one running '${runtime_component}' pod at the moment of the deletion and found ${current_count}. Nothing was deleted."
[ "$(printf '%s\n' "${current_names}" | head -1)" = "${baseline_pod}" ] ||
  inferops::fail "the running '${runtime_component}' pod is no longer the one this run measured a baseline against. Nothing was deleted."

inferops::section "Deleting one serving runtime pod"
inferops::log "deleting pod '${baseline_pod}'. This changes no Deployment, no claim, and no release revision: the Deployment controller creates the replacement."

deleted_at_ms="$(epoch_ms)"
inferops::target_kubectl delete pod "${baseline_pod}" \
  -n "${INFEROPS_RELEASE_NAMESPACE}" --wait=false

# --- watching the replacement, from the Service's own endpoints ---------------

inferops::section "Watching for the replacement"

# What a caller can reach: the number of endpoints the runtime Service is willing to
# send traffic to. V1-S3-011-PR2 established that `up` and the Deployment's aggregate
# both keep counting a pod that is terminating, so neither is a caller's view.
ready_endpoint_count() {
  inferops::target_kubectl get endpointslices -n "${INFEROPS_RELEASE_NAMESPACE}" \
    -l "kubernetes.io/service-name=${runtime_service}" \
    -o 'jsonpath={range .items[*].endpoints[*]}{.conditions.ready}{"\n"}{end}' |
    tr -d '\r' | grep -c '^true$' || true
}

runtime_pod_states() {
  inferops::target_kubectl get pods -n "${INFEROPS_RELEASE_NAMESPACE}" \
    -l "app.kubernetes.io/component=${runtime_component},${INFEROPS_RELEASE_SELECTOR}" \
    -o 'jsonpath={range .items[*]}{.metadata.name}{":"}{range .status.conditions[?(@.type=="Ready")]}{.status}{end}{"\n"}{end}' |
    tr -d '\r'
}

: >"${readiness_samples}"
replacement_pod=""
replacement_observed_ms=""
replacement_ready_ms=""
sample_count=0
sample_sleep="$((poll_interval_ms / 1000)).$(printf '%03d' $((poll_interval_ms % 1000)))"
replacement_deadline=$((SECONDS + replacement_budget_ms / 1000))

while :; do
  sample_start="$(epoch_ms)"
  states="$(runtime_pod_states || true)"
  endpoints="$(ready_endpoint_count || true)"
  sample_end="$(epoch_ms)"
  case "${endpoints}" in
    '' | *[!0-9]*) endpoints=0 ;;
  esac
  states_field="$(printf '%s\n' "${states}" | grep . | paste -sd, - || true)"
  [ -n "${states_field}" ] || states_field="none"
  pods_ready="$(printf '%s\n' "${states}" | grep -c ':True$' || true)"
  printf '%s %s %s %s %s\n' "${sample_start}" "$((sample_end - sample_start))" \
    "${endpoints}" "${pods_ready}" "${states_field}" >>"${readiness_samples}"
  sample_count=$((sample_count + 1))

  # The replacement is the running serving pod that is not the one that was deleted.
  # Its own Ready condition is what ends the replacement interval -- not the
  # Deployment's aggregate, which still counts the deleted pod inside its termination
  # grace period, and not the forward accepting a connection, which is an interval
  # that ends before a request is even sent.
  candidate="$(printf '%s\n' "${states}" | grep -v "^${baseline_pod}:" | head -1 || true)"
  if [ -n "${candidate}" ]; then
    if [ -z "${replacement_observed_ms}" ]; then
      replacement_pod="${candidate%%:*}"
      replacement_observed_ms="${sample_start}"
      inferops::log "replacement pod '${replacement_pod}' first seen."
    fi
    if [ -z "${replacement_ready_ms}" ] && [ "${candidate}" = "${replacement_pod}:True" ]; then
      replacement_ready_ms="${sample_start}"
      inferops::log "replacement pod '${replacement_pod}' reports itself Ready."
    fi
  fi

  if [ -n "${replacement_ready_ms}" ] && [ "${sample_count}" -ge "${minimum_samples}" ]; then
    break
  fi
  if [ "${SECONDS}" -ge "${replacement_deadline}" ]; then
    inferops::fail "no ready replacement pod within the $((replacement_budget_ms / 1000)) s this experiment allows it."
  fi
  sleep "${sample_sleep}"
done

[ -n "${replacement_pod}" ] ||
  inferops::fail "no pod other than the deleted one appeared; nothing was replaced."
[ "${replacement_pod}" != "${baseline_pod}" ] ||
  inferops::fail "the pod after the deletion carries the same name as the one that was deleted. Nothing was replaced."

replacement_uid="$(require_query "the replacement pod uid" pod_field "${replacement_pod}" '{.metadata.uid}')"
replacement_owner_kind="$(require_query "the replacement pod owner kind" pod_field "${replacement_pod}" '{.metadata.ownerReferences[0].kind}')"
replacement_owner_name="$(require_query "the replacement pod owner name" pod_field "${replacement_pod}" '{.metadata.ownerReferences[0].name}')"
replacement_node="$(require_query "the replacement pod node" pod_field "${replacement_pod}" '{.spec.nodeName}')"
replacement_started_at="$(require_query "the replacement container start time" pod_field "${replacement_pod}" '{.status.containerStatuses[?(@.name=="runtime")].state.running.startedAt}')"
replacement_ready_at="$(require_query "the replacement readiness transition time" pod_field "${replacement_pod}" '{.status.conditions[?(@.type=="Ready")].lastTransitionTime}')"
replacement_init_name="$(require_query "the replacement integrity init container" pod_field "${replacement_pod}" '{.status.initContainerStatuses[0].name}')"
replacement_init_exit="$(require_query "the replacement integrity init exit code" pod_field "${replacement_pod}" '{.status.initContainerStatuses[0].state.terminated.exitCode}')"
replacement_restarts="$(require_query "the replacement restart count" pod_field "${replacement_pod}" '{.status.containerStatuses[?(@.name=="runtime")].restartCount}')"

# --- letting the load finish --------------------------------------------------

inferops::section "Letting the disrupted load run finish"

finish_load "${disrupted_raw_file}"
disrupted_exit_code="${finished_exit_code}"
disrupted_exited="${finished_at_ms}"
tail -n 20 "${load_log}" || true
[ "${disrupted_exit_code}" -eq 0 ] ||
  inferops::fail "the disrupted load run did not complete (exit ${disrupted_exit_code}). Its raw set is kept in ${evidence_rel}/."

inferops::log "settling ${settle_between_seconds} s before the second run"
sleep "${settle_between_seconds}"

inferops::section "Starting the committed load profile again (run 2 of 2, after the recovery)"
recovered_launched="$(epoch_ms)"
start_load
finish_load "${recovered_raw_file}"
recovered_exit_code="${finished_exit_code}"
recovered_exited="${finished_at_ms}"
tail -n 20 "${load_log}" || true
[ "${recovered_exit_code}" -eq 0 ] ||
  inferops::fail "the recovered load run did not complete (exit ${recovered_exit_code}). Its raw set is kept in ${evidence_rel}/."

inferops::log "settling ${settle_seconds} s so the collector scrapes every counter"
sleep "${settle_seconds}"
settled_ms="$(epoch_ms)"

dump_json pods-after.json inferops::target_kubectl get pods \
  -n "${INFEROPS_RELEASE_NAMESPACE}" -l "${INFEROPS_RELEASE_SELECTOR}" -o json

if ! jobs_after="$(acquisition_job_count)"; then
  inferops::fail "could not count the acquisition Jobs after the replacement. An unanswered query is not an empty result."
fi
revision_after="$(require_query "the release revision after the replacement" release_revision)"

# --- what the script stamped ---------------------------------------------------

INFEROPS_IDLE_START="${idle_start}" \
  INFEROPS_IDLE_END="${idle_end}" \
  INFEROPS_DISRUPTED_LAUNCHED="${disrupted_launched}" \
  INFEROPS_DISRUPTED_EXITED="${disrupted_exited}" \
  INFEROPS_DISRUPTED_EXIT_CODE="${disrupted_exit_code}" \
  INFEROPS_DISRUPTED_RAW="${disrupted_raw_name}" \
  INFEROPS_RECOVERED_LAUNCHED="${recovered_launched}" \
  INFEROPS_RECOVERED_EXITED="${recovered_exited}" \
  INFEROPS_RECOVERED_EXIT_CODE="${recovered_exit_code}" \
  INFEROPS_RECOVERED_RAW="${recovered_raw_name}" \
  INFEROPS_SETTLED="${settled_ms}" \
  INFEROPS_DELETED_AT="${deleted_at_ms}" \
  INFEROPS_REQUESTED_OFFSET="${disruption_offset_ms}" \
  INFEROPS_BASELINE_POD="${baseline_pod}" \
  INFEROPS_BASELINE_UID="${baseline_uid}" \
  INFEROPS_BASELINE_OWNER_KIND="${baseline_owner_kind}" \
  INFEROPS_BASELINE_OWNER_NAME="${baseline_owner_name}" \
  INFEROPS_BASELINE_NODE="${baseline_node}" \
  INFEROPS_MATCHED="${current_count}" \
  INFEROPS_REPLACEMENT_POD="${replacement_pod}" \
  INFEROPS_REPLACEMENT_UID="${replacement_uid}" \
  INFEROPS_REPLACEMENT_OWNER_KIND="${replacement_owner_kind}" \
  INFEROPS_REPLACEMENT_OWNER_NAME="${replacement_owner_name}" \
  INFEROPS_REPLACEMENT_NODE="${replacement_node}" \
  INFEROPS_REPLACEMENT_OBSERVED="${replacement_observed_ms}" \
  INFEROPS_REPLACEMENT_READY="${replacement_ready_ms}" \
  INFEROPS_REPLACEMENT_STARTED_AT="${replacement_started_at}" \
  INFEROPS_REPLACEMENT_READY_AT="${replacement_ready_at}" \
  INFEROPS_REPLACEMENT_INIT_NAME="${replacement_init_name}" \
  INFEROPS_REPLACEMENT_INIT_EXIT="${replacement_init_exit}" \
  INFEROPS_REPLACEMENT_RESTARTS="${replacement_restarts}" \
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
    "runs": [
        {
            "role": "disrupted",
            "rawFile": fact("DISRUPTED_RAW"),
            "launchedEpochMs": number("DISRUPTED_LAUNCHED"),
            "exitedEpochMs": number("DISRUPTED_EXITED"),
            "exitCode": number("DISRUPTED_EXIT_CODE"),
        },
        {
            "role": "recovered",
            "rawFile": fact("RECOVERED_RAW"),
            "launchedEpochMs": number("RECOVERED_LAUNCHED"),
            "exitedEpochMs": number("RECOVERED_EXITED"),
            "exitCode": number("RECOVERED_EXIT_CODE"),
        },
    ],
    "settledEpochMs": number("SETTLED"),
    "deletion": {
        "name": fact("BASELINE_POD"),
        "uid": fact("BASELINE_UID"),
        "ownerKind": fact("BASELINE_OWNER_KIND"),
        "ownerName": fact("BASELINE_OWNER_NAME"),
        "nodeName": fact("BASELINE_NODE"),
        "issuedEpochMs": number("DELETED_AT"),
        "requestedAfterLoadStartMs": number("REQUESTED_OFFSET"),
        "podsMatchingSelector": number("MATCHED"),
    },
    "replacement": {
        "name": fact("REPLACEMENT_POD"),
        "uid": fact("REPLACEMENT_UID"),
        "ownerKind": fact("REPLACEMENT_OWNER_KIND"),
        "ownerName": fact("REPLACEMENT_OWNER_NAME"),
        "nodeName": fact("REPLACEMENT_NODE"),
        "observedEpochMs": number("REPLACEMENT_OBSERVED"),
        "readyEpochMs": number("REPLACEMENT_READY"),
        "containerStartedAt": fact("REPLACEMENT_STARTED_AT"),
        "readyConditionAt": fact("REPLACEMENT_READY_AT"),
        "initContainerName": fact("REPLACEMENT_INIT_NAME"),
        "initExitCode": number("REPLACEMENT_INIT_EXIT"),
        "restartCount": number("REPLACEMENT_RESTARTS"),
    },
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
    # Nothing between the delete and the uninstall changed anything, which is what
    # lets the record say the Deployment controller did the recovering. The list is
    # written empty here and a test reads this script to establish that it is true.
    "interventionsAfterDeletion": [],
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
    at, took, endpoints, ready, states = line.split(" ", 4)
    names = [] if states == "none" else [entry.split(":", 1)[0] for entry in states.split(",")]
    samples.append(
        {
            "atEpochMs": int(at),
            "readTookMs": int(took),
            "runtimeEndpointsReady": int(endpoints),
            "runtimePodsReady": int(ready),
            "runtimePodNames": names,
        }
    )
Path(sys.argv[2]).write_text(
    json.dumps({"samples": samples}, indent=2, sort_keys=True) + "\n",
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
  0) inferops::log "the record is usable: every safety, recovery, and coverage check passed." ;;
  6) inferops::fail "the record was written and is not usable; its checks name what failed. The release is already uninstalled." ;;
  *) inferops::fail "the record could not be built (exit ${record_code}). The run's inputs are kept in ${evidence_rel}/." ;;
esac

inferops::section "Result"
inferops::log "record        ${evidence_rel}/record/recovery-record.v1alpha1.json (labelled local real Kubernetes)"
inferops::log "one serving pod was deleted under load, the Deployment controller replaced it, and the record says what callers saw before the delete, during the outage, and in a second run of the same profile after the recovery. Nothing in it is an availability figure or a service-level objective."
inferops::log "the namespace and the model cache claim survived. Reclaiming them is scripts/environment/terraform-prerequisites.sh destroy --confirm, and nothing here does it for you."
