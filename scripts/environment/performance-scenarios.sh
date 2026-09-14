#!/usr/bin/env bash
# Runs the committed performance scenario matrix against one real release and keeps
# what it needs to be read later: the raw load records, the node's resource counters
# sampled alongside them, the release's own collector readings, and the environment
# the cluster reported -- each placed on one wall clock.
#
# What it establishes, and what it does not. It produces bounded observations of one
# executed matrix on one provider, one host, one single-replica release, one model,
# and one load profile (ADR 0013). It does not judge saturation, compare levels, or
# state a capacity: tools/performance_scenarios places a level's latency beside a
# tier's CPU and says nothing about what the two mean together.
#
# What it operates. It applies the Terraform prerequisite layer through
# scripts/environment/terraform-prerequisites.sh, installs one Helm release named by
# INFEROPS_RELEASE_NAME in INFEROPS_RELEASE_NAMESPACE, opens two loopback forwards
# (the API and the collector), sends the committed load profile through the first
# with tools.llm_load, and uninstalls the release when it is done. It never removes
# the namespace, the model cache claim, or the cluster: those outlive a release by
# design (docs/architecture/resource-ownership.md).
#
# What it reads, and how. Cluster state comes from kubectl and helm through the
# verified-target wrappers. Resource counters come from the verified node container's
# own cgroup v1 hierarchy through inferops::target_node_exec, one read-only `sh -c`
# per sample: the virtual machine's /proc/stat, the node's root cgroup, and the cgroup
# of each release pod, located once by the pod UID the API server reported. Reading a
# cgroup file changes nothing. The sampler's own `docker exec` runs inside the node,
# and the record says it is counted there.
#
# The assertions and the record are not here. They are in
# tools/performance_scenarios, which validates the committed descriptor, derives the
# load facts from the cluster's answers instead of an operator's typing, asks the
# collector over loopback, and builds the record from the committed inputs alone. The
# guard that establishes which cluster is being acted on stays in lib.sh.
#
# On failure it stops the sampler, closes both forwards, collects diagnostics into
# .artifacts/, leaves an installed release in place for inspection, and says how to
# remove it.
#
# Usage:
#   scripts/environment/performance-scenarios.sh check
#   scripts/environment/performance-scenarios.sh run --values PATH [--values PATH ...] \
#     --confirm-real-kubernetes

# shellcheck source=scripts/environment/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

readonly INFEROPS_EXPERIMENT_REL="deploy/serving/experiments/performance-scenarios.v1.json"
readonly INFEROPS_EXPERIMENT_MODULE="tools.performance_scenarios"

# Where tools.llm_load writes a real run's raw record set. Each repetition's set is
# copied out of here as soon as it is written, because the next one overwrites it.
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
      [ "$#" -ge 2 ] || inferops::fail "--values needs a path. Usage: performance-scenarios.sh run --values PATH [--values PATH ...] --confirm-real-kubernetes"
      values_files+=("$2")
      shift 2
      ;;
    --confirm-real-kubernetes)
      confirmed=1
      shift
      ;;
    *)
      inferops::fail "unknown argument '$1'. Usage: performance-scenarios.sh check|run [--values PATH ...] [--confirm-real-kubernetes]"
      ;;
  esac
done

[ -n "${action}" ] ||
  inferops::fail "expected one of check, run. Usage: performance-scenarios.sh check|run [--values PATH ...] [--confirm-real-kubernetes]"

inferops::require_cmd python

experiment_file="${INFEROPS_ROOT}/${INFEROPS_EXPERIMENT_REL}"
[ -f "${experiment_file}" ] ||
  inferops::fail "no experiment descriptor at ${INFEROPS_EXPERIMENT_REL}"

# --- check: reads files, contacts nothing -----------------------------------

if [ "${action}" = "check" ]; then
  inferops::section "Scenario matrix"
  (cd "${INFEROPS_ROOT}" && python -m "${INFEROPS_EXPERIMENT_MODULE}" check)
  inferops::log "the descriptor validated. Nothing was contacted and no release was installed."
  exit 0
fi

# --- everything below reaches a cluster and a real model --------------------

[ "${confirmed}" -eq 1 ] ||
  inferops::fail "run needs --confirm-real-kubernetes. It applies the Terraform prerequisites, installs a release, loads a real model, and sends real inference load for tens of minutes. Usage: performance-scenarios.sh run --values PATH [--values PATH ...] --confirm-real-kubernetes"

[ "${#values_files[@]}" -gt 0 ] ||
  inferops::fail "--values is required. The chart's shipped defaults select no serving profile and are refused on purpose. See docs/serving/performance-scenarios.md."

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

inferops::section "Scenario matrix"
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

# Read into a variable first and check the status: a reader whose producer failed
# sees empty fields and no error, and an empty budget becomes arithmetic.
if ! descriptor_fields="$(cd "${INFEROPS_ROOT}" && inferops::python -m "${INFEROPS_EXPERIMENT_MODULE}" fields \
  release.name release.namespace release.apiServiceName release.apiServicePort \
  release.runtimeDeploymentName release.apiDeploymentName release.collectorServiceName \
  release.collectorServicePort release.collectorDeploymentName release.configMapName \
  schedule.repetitions schedule.idleBaselineSeconds schedule.settleBetweenRunsSeconds \
  schedule.settleAfterLastRunSeconds resources.sampleIntervalMs \
  readiness.runtimeRolloutBudgetMs readiness.apiRolloutBudgetMs \
  readiness.collectorRolloutBudgetMs readiness.forwardBudgetMs readiness.uninstallBudgetMs \
  forwards.host forwards.apiPort forwards.collectorPort \
  evidence.directory evidence.windowsFile evidence.samplesFile)"; then
  inferops::fail "the experiment descriptor could not be read after it validated. Nothing was installed."
fi

{
  read -r descriptor_release
  read -r descriptor_namespace
  read -r api_service
  read -r api_service_port
  read -r runtime_deployment
  read -r api_deployment
  read -r collector_service
  read -r collector_service_port
  read -r collector_deployment
  read -r configmap_name
  read -r repetitions
  read -r idle_seconds
  read -r settle_between_seconds
  read -r settle_after_seconds
  read -r sample_interval_ms
  read -r runtime_rollout_budget_ms
  read -r api_rollout_budget_ms
  read -r collector_rollout_budget_ms
  read -r forward_budget_ms
  read -r uninstall_budget_ms
  read -r forward_host
  read -r api_forward_port
  read -r collector_forward_port
  read -r evidence_rel
  read -r windows_name
  read -r samples_name
} <<<"${descriptor_fields}"

# Every value that reaches arithmetic, a timeout, or a port is held to being a number
# here, at the point of use. The Python validator refuses the same, in another file.
for number in api_service_port collector_service_port repetitions idle_seconds \
  settle_between_seconds settle_after_seconds sample_interval_ms \
  runtime_rollout_budget_ms api_rollout_budget_ms collector_rollout_budget_ms \
  forward_budget_ms uninstall_budget_ms api_forward_port collector_forward_port; do
  case "${!number}" in
    '' | *[!0-9]*) inferops::fail "the experiment descriptor's '${number}' is not a number. Nothing was installed." ;;
  esac
done
[ "${sample_interval_ms}" -ge 1000 ] ||
  inferops::fail "the descriptor samples every ${sample_interval_ms} ms; below 1000 ms this loop would spin against the node. Nothing was installed."

for name in api_service runtime_deployment api_deployment collector_service \
  collector_deployment configmap_name; do
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
load_dir="${run_dir}/load"
samples_file="${run_dir}/${samples_name}"
windows_file="${run_dir}/${windows_name}"
stop_file="${run_dir}/sampler.stop"
diag_dir="${INFEROPS_ARTIFACT_DIR}/performance-scenarios"
forward_log="${diag_dir}/forward.log"

# A run directory is never overwritten. An earlier run's evidence is either already
# promoted or still wanted, and this script cannot tell which.
if [ -e "${run_dir}" ]; then
  inferops::fail "the run directory ${evidence_rel} already exists. Move it aside before a new run. Nothing was installed."
fi

# Wall-clock milliseconds from bash's own clock, with no process started to read it.
# tools.llm_load reads the same host clock for startedAtEpochMs.
epoch_ms() {
  local micros="${EPOCHREALTIME/[.,]/}"
  printf '%s' "$((micros / 1000))"
}
[ -n "${EPOCHREALTIME:-}" ] ||
  inferops::fail "this shell has no EPOCHREALTIME (bash 5 or later is needed). Nothing was installed."

api_forward_pid=""
collector_forward_pid=""
sampler_pid=""
release_installed=0

# --- diagnostics and teardown ------------------------------------------------

collect_diagnostics() {
  mkdir -p "${diag_dir}"
  inferops::warn "collecting diagnostics into .artifacts/performance-scenarios/"
  inferops::target_helm list --namespace "${INFEROPS_RELEASE_NAMESPACE}" >"${diag_dir}/releases.txt" 2>&1 || true
  inferops::target_kubectl get all,configmap,pvc,job \
    -n "${INFEROPS_RELEASE_NAMESPACE}" -o wide >"${diag_dir}/get-all.txt" 2>&1 || true
  inferops::target_kubectl describe pods -n "${INFEROPS_RELEASE_NAMESPACE}" >"${diag_dir}/describe-pods.txt" 2>&1 || true
  inferops::target_kubectl get events -n "${INFEROPS_RELEASE_NAMESPACE}" \
    --sort-by=.lastTimestamp >"${diag_dir}/events.txt" 2>&1 || true
  inferops::target_kubectl logs -n "${INFEROPS_RELEASE_NAMESPACE}" \
    -l "${INFEROPS_RELEASE_SELECTOR}" --all-containers --tail="${INFEROPS_LOG_TAIL}" >"${diag_dir}/release.log" 2>&1 || true
}

stop_sampler() {
  if [ -n "${sampler_pid}" ]; then
    : >"${stop_file}"
    wait "${sampler_pid}" 2>/dev/null || true
  fi
  sampler_pid=""
}

close_forwards() {
  local pid
  for pid in "${api_forward_pid}" "${collector_forward_pid}"; do
    if [ -n "${pid}" ] && kill -0 "${pid}" 2>/dev/null; then
      kill "${pid}" 2>/dev/null || true
      wait "${pid}" 2>/dev/null || true
    fi
  done
  api_forward_pid=""
  collector_forward_pid=""
}

on_exit() {
  local rc=$?
  stop_sampler
  close_forwards
  if [ "${rc}" -ne 0 ]; then
    collect_diagnostics
    if [ "${release_installed}" -eq 1 ]; then
      inferops::warn "the release was left in place for inspection. Remove it with: helm uninstall ${INFEROPS_RELEASE_NAME} --namespace ${INFEROPS_RELEASE_NAMESPACE}"
    fi
    inferops::warn "whatever evidence was written is in ${evidence_rel}/ and is not a usable record."
  fi
  exit "${rc}"
}

trap on_exit INT TERM EXIT

mkdir -p "${diag_dir}" "${cluster_dir}" "${load_dir}"

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

# --- prerequisites and the release -------------------------------------------

inferops::section "Applying the Terraform prerequisites"

bash "${INFEROPS_ROOT}/scripts/environment/terraform-prerequisites.sh" apply

if ! claims_before="$(claim_count)"; then
  inferops::fail "could not count the persistent volume claims before installing. An unanswered query is not an empty result."
fi

if inferops::target_helm status "${INFEROPS_RELEASE_NAME}" --namespace "${INFEROPS_RELEASE_NAMESPACE}" >/dev/null 2>&1; then
  inferops::fail "release '${INFEROPS_RELEASE_NAME}' already exists in '${INFEROPS_RELEASE_NAMESPACE}'. This experiment starts from its own install, so that the environment it records is the one it made. Remove it first: helm uninstall ${INFEROPS_RELEASE_NAME} --namespace ${INFEROPS_RELEASE_NAMESPACE}"
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
# The node container runtime's own description of each template image reference.
# A pod's imageID names one of an image's digests, and one image can carry several --
# the same build imported twice under two index digests is one image with two names --
# so the binding from template to running bytes is made through this answer.
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
vm_cpus="$(require_query "the virtual machine's logical processors" inferops::target_node_exec nproc)"
vm_cpus="$(printf '%s' "${vm_cpus}" | tr -d '\r[:space:]')"

INFEROPS_FACT_PROVIDER="${INFEROPS_TARGET_PROVIDER}" \
  INFEROPS_FACT_CLUSTER="${INFEROPS_TARGET_CLUSTER_NAME}" \
  INFEROPS_FACT_CONTEXT="${INFEROPS_TARGET_CONTEXT}" \
  INFEROPS_FACT_VERIFIED_AT="${INFEROPS_TARGET_VERIFIED_AT}" \
  INFEROPS_FACT_NODE_DIGEST="${INFEROPS_TARGET_NODE_IMAGE_DIGEST}" \
  INFEROPS_FACT_HELM="${helm_version}" \
  INFEROPS_FACT_ENGINE_VERSION="${engine_version}" \
  INFEROPS_FACT_ENGINE_CPUS="${engine_cpus}" \
  INFEROPS_FACT_ENGINE_MEMORY="${engine_memory}" \
  INFEROPS_FACT_VM_CPUS="${vm_cpus}" \
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
    "vmLogicalCpus": number("VM_CPUS"),
}
for name, document in (("target.json", target), ("engine.json", engine)):
    (directory / name).write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
    )
TARGET_PYTHON

(cd "${INFEROPS_ROOT}" && python -m "${INFEROPS_EXPERIMENT_MODULE}" repository --run-dir "$(inferops::native_path "${run_dir}")")
(cd "${INFEROPS_ROOT}" && python -m "${INFEROPS_EXPERIMENT_MODULE}" facts --run-dir "$(inferops::native_path "${run_dir}")")

# --- locating each release pod's cgroup --------------------------------------

inferops::section "Locating the release pods' cgroups inside the node"

# The one running pod of a tier, by the component label the chart sets. Counted
# rather than indexed into: two would make "the tier's cgroup" ambiguous.
tier_cgroup() {
  local component="$1"
  local uids uid count matches
  if ! uids="$(inferops::target_kubectl get pods -n "${INFEROPS_RELEASE_NAMESPACE}" \
    -l "app.kubernetes.io/component=${component},${INFEROPS_RELEASE_SELECTOR}" \
    --field-selector=status.phase=Running -o 'jsonpath={.items[*].metadata.uid}')"; then
    inferops::fail "could not ask for the running '${component}' pod."
  fi
  count="$(printf '%s\n' ${uids} | grep -c . || true)"
  [ "${count}" = "1" ] ||
    inferops::fail "the release has ${count} running '${component}' pod(s); this experiment is defined for exactly one."
  uid="${uids//-/_}"
  # A directory find cannot enter is not this pod's; the count below is what refuses.
  matches="$({ inferops::target_node_exec find /sys/fs/cgroup/cpuacct/kubelet.slice -maxdepth 3 -type d \
    -name "*pod${uid}.slice" 2>/dev/null || true; } | tr -d '\r')"
  [ "$(printf '%s\n' "${matches}" | grep -c . || true)" = "1" ] ||
    inferops::fail "the '${component}' pod has other than exactly one cgroup directory in the node; the sampler would read the wrong counters."
  matches="${matches#/sys/fs/cgroup/cpuacct/}"
  case "${matches}" in
    *[!A-Za-z0-9._/-]* | '') inferops::fail "the '${component}' cgroup path carries characters this sampler will not pass to a shell." ;;
  esac
  inferops::target_node_exec test -r "/sys/fs/cgroup/memory/${matches}/memory.stat" ||
    inferops::fail "the '${component}' pod has no readable memory cgroup at the same path."
  printf '%s' "${matches}"
}

api_cgroup="$(tier_cgroup platform-api)"
runtime_cgroup="$(tier_cgroup serving-runtime)"
collector_cgroup="$(tier_cgroup telemetry-collector)"
inferops::log "cgroups located for the api, runtime, and collector pods."

# --- the sampler ----------------------------------------------------------------

# Runs inside the node. Prints one line: the node clock, the virtual machine's
# aggregate /proc/stat jiffies, then cpu,memory-usage,inactive-file for the node's
# root cgroup and each release pod. A file that cannot be read prints `missing`.
# shellcheck disable=SC2016
readonly SAMPLE_SCRIPT='
read_value() { v=$(cat "$1" 2>/dev/null) || v=""; [ -n "$v" ] || v=missing; printf "%s" "$v"; }
tier() {
  cpu=$(read_value "/sys/fs/cgroup/cpuacct/$1/cpuacct.usage")
  usage=$(read_value "/sys/fs/cgroup/memory/$1/memory.usage_in_bytes")
  inactive=missing
  if [ -r "/sys/fs/cgroup/memory/$1/memory.stat" ]; then
    while read -r key value; do
      if [ "$key" = total_inactive_file ]; then inactive=$value; fi
    done <"/sys/fs/cgroup/memory/$1/memory.stat"
  fi
  printf "%s,%s,%s" "$cpu" "$usage" "$inactive"
}
clock=$(date +%s%N)
read -r _ user nice system idle iowait irq softirq steal _rest </proc/stat
printf "node_ns=%s vm=%s,%s,%s,%s,%s,%s,%s,%s node=%s api=%s runtime=%s collector=%s\n" \
  "$clock" "$user" "$nice" "$system" "$idle" "$iowait" "$irq" "$softirq" "$steal" \
  "$(tier .)" "$(tier "$1")" "$(tier "$2")" "$(tier "$3")"
'

sample_sleep="$((sample_interval_ms / 1000)).$(printf '%03d' $((sample_interval_ms % 1000)))"

sampler_loop() {
  local before after line
  while [ ! -e "${stop_file}" ]; do
    before="${EPOCHREALTIME/[.,]/}"
    if line="$(inferops::target_node_exec sh -c "${SAMPLE_SCRIPT}" sh \
      "${api_cgroup}" "${runtime_cgroup}" "${collector_cgroup}" 2>/dev/null | tr -d '\r')"; then
      after="${EPOCHREALTIME/[.,]/}"
      printf '%s %s %s\n' "${before}" "${after}" "${line}" >>"${samples_file}"
    fi
    sleep "${sample_sleep}"
  done
}

inferops::section "Starting the resource sampler"
first_sample="$(inferops::target_node_exec sh -c "${SAMPLE_SCRIPT}" sh \
  "${api_cgroup}" "${runtime_cgroup}" "${collector_cgroup}" | tr -d '\r')"
case "${first_sample}" in
  *missing*) inferops::fail "a first sample could not read every counter: ${first_sample}" ;;
esac
sampler_loop &
sampler_pid="$!"

# --- the forwards ------------------------------------------------------------

# Called directly, never inside a command substitution: the forward must be a child
# of this shell, or close_forwards could neither signal nor wait for it. The pid is
# handed back through `opened_forward_pid`.
opened_forward_pid=""
open_forward() {
  local service="$1" service_port="$2" local_port="$3"
  inferops::target_kubectl port-forward "service/${service}" "${local_port}:${service_port}" \
    -n "${INFEROPS_RELEASE_NAMESPACE}" --address "${forward_host}" >>"${forward_log}" 2>&1 &
  opened_forward_pid="$!"
  local deadline=$((SECONDS + forward_budget_ms / 1000))
  while [ "${SECONDS}" -lt "${deadline}" ]; do
    kill -0 "${opened_forward_pid}" 2>/dev/null ||
      inferops::fail "the port-forward to '${service}' exited before it accepted a connection. Its output is in .artifacts/performance-scenarios/forward.log."
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

# --- idle baseline, then the repetitions -------------------------------------

inferops::section "Idle baseline (${idle_seconds} s, no load)"
idle_start="$(epoch_ms)"
sleep "${idle_seconds}"
idle_end="$(epoch_ms)"

load_raw="${INFEROPS_ROOT}/${INFEROPS_LOAD_RAW_REL}"
run_lines=""
for repetition in $(seq 1 "${repetitions}"); do
  inferops::section "Load run ${repetition} of ${repetitions}"
  # A raw set left by an earlier run would be copied as this one's if this run
  # wrote none, so the one path this run writes is cleared first.
  rm -f "${load_raw}"
  launched="$(epoch_ms)"
  set +e
  (cd "${INFEROPS_ROOT}" && python -m tools.llm_load run \
    --target-url "http://${forward_host}:${api_forward_port}" \
    --environment-facts "$(inferops::native_path "${run_dir}/facts.json")" \
    --confirm-real-load)
  exit_code=$?
  set -e
  exited="$(epoch_ms)"
  [ -f "${load_raw}" ] ||
    inferops::fail "load run ${repetition} exited ${exit_code} and wrote no raw record set."
  cp "${load_raw}" "${load_dir}/run-${repetition}-raw.jsonl"
  run_lines="${run_lines}${repetition} ${launched} ${exited} ${exit_code}"$'\n'
  [ "${exit_code}" -eq 0 ] ||
    inferops::fail "load run ${repetition} did not complete (exit ${exit_code}). Its raw set is kept in ${evidence_rel}/load/."
  if [ "${repetition}" -lt "${repetitions}" ]; then
    inferops::log "settling ${settle_between_seconds} s so the collector scrapes every counter before the next run"
    sleep "${settle_between_seconds}"
  fi
done

inferops::log "settling ${settle_after_seconds} s after the last run"
sleep "${settle_after_seconds}"
settled="$(epoch_ms)"

stop_sampler

dump_json pods-after.json inferops::target_kubectl get pods \
  -n "${INFEROPS_RELEASE_NAMESPACE}" -l "${INFEROPS_RELEASE_SELECTOR}" -o json

INFEROPS_IDLE_START="${idle_start}" INFEROPS_IDLE_END="${idle_end}" \
  INFEROPS_RUN_LINES="${run_lines}" INFEROPS_SETTLED="${settled}" \
  python - "$(inferops::native_path "${windows_file}")" <<'WINDOWS_PYTHON'
import json
import os
import sys
from pathlib import Path

runs = []
for line in os.environ["INFEROPS_RUN_LINES"].splitlines():
    if not line.strip():
        continue
    repetition, launched, exited, code = (int(value) for value in line.split())
    runs.append(
        {
            "repetition": repetition,
            "rawFile": f"run-{repetition}-raw.jsonl",
            "launchedEpochMs": launched,
            "exitedEpochMs": exited,
            "exitCode": code,
        }
    )
document = {
    "idleBaseline": {
        "startEpochMs": int(os.environ["INFEROPS_IDLE_START"]),
        "endEpochMs": int(os.environ["INFEROPS_IDLE_END"]),
    },
    "runs": runs,
    "settledEpochMs": int(os.environ["INFEROPS_SETTLED"]),
}
Path(sys.argv[1]).write_text(
    json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
)
WINDOWS_PYTHON

inferops::section "Asking the collector what it recorded"
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
    deployments,replicasets,services,configmaps,serviceaccounts,pods,networkpolicies,jobs \
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
  inferops::fail "the claim count changed across the release: ${claims_before} before, ${claims_after} after. This chart must neither create nor delete a claim."
inferops::log "no object with the release's instance label remains; the namespace and the model cache claim were left in place."

# --- the record ----------------------------------------------------------------

inferops::section "Building the record"

set +e
(cd "${INFEROPS_ROOT}" && python -m "${INFEROPS_EXPERIMENT_MODULE}" record --run-dir "$(inferops::native_path "${run_dir}")")
record_code=$?
set -e

case "${record_code}" in
  0) inferops::log "the record is usable: every stability, coverage, and reconciliation check passed." ;;
  6) inferops::fail "the record was written and is not usable; its checks name what failed. The release is already uninstalled." ;;
  *) inferops::fail "the record could not be built (exit ${record_code}). The run's inputs are kept in ${evidence_rel}/." ;;
esac

inferops::section "Result"
inferops::log "record        ${evidence_rel}/record/performance-record.v1alpha1.json (labelled local real Kubernetes)"
inferops::log "every figure in it is a bounded observation of this run and judges no saturation."
inferops::log "the namespace and the model cache claim survived. Reclaiming them is scripts/environment/terraform-prerequisites.sh destroy --confirm, and nothing here does it for you."
