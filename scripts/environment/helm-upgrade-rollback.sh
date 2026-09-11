#!/usr/bin/env bash
# Proves that a release change can be reversed: a known-good install, a
# controlled upgrade, an injected failure, a detection, a rollback, and a real
# completion afterwards -- with the version at each step and the recovery time
# recorded.
#
# This is the answer to "can we undo a bad release". `helm rollback` returning
# zero is not that answer: Helm records a revision, and a revision Helm recorded,
# a Deployment that never rolled, and a Service selecting a pod that loaded
# nothing all look identical from outside until something asks for a completion.
#
# What it operates, and what it does not. It applies the Terraform prerequisite
# layer through scripts/environment/terraform-prerequisites.sh, installs one Helm
# release named by INFEROPS_RELEASE_NAME in INFEROPS_RELEASE_NAMESPACE, upgrades
# it twice, rolls it back once, opens one loopback forward to that release's API
# Service, and uninstalls the release when it is done. It never removes the
# namespace, never removes the model cache claim, and never removes the cluster:
# those outlive a release by design (docs/architecture/resource-ownership.md).
#
# The fault it injects is a byte count the mounted artifact cannot match. It
# changes no image reference, pulls nothing, creates no object outside this
# release, reaches only the serving runtime's pod template, and is removed by the
# rollback rather than by a second edit. Nothing on the host is modified and no
# file in the model cache is touched: the claim is mounted read-only and the
# candidate that reads it never starts.
#
# The assertions and the record are not here. They are in
# tools/helm_upgrade_rollback, which reads the committed descriptor, refuses a
# forward that is not loopback, refuses a failure read off a workload the fault
# was not injected into, refuses a deadline reached sooner than a healthy rollout
# is allowed, and writes the labelled record. The split is deliberate: the guard
# that establishes which cluster is being acted on already lives in lib.sh beside
# every other script here, and a second implementation of it in Python would be a
# second guard.
#
# Every threshold this script applies comes from the descriptor, with two stated
# exceptions that are host conveniences rather than thresholds: the default
# loopback port, which moves when something else already holds one, and the tail
# length on collected container logs.
#
# On failure it collects diagnostics into .artifacts/, leaves the release in
# place for inspection, and says how to remove it. It does not tear down the
# evidence of its own failure.
#
# Usage:
#   scripts/environment/helm-upgrade-rollback.sh check
#   scripts/environment/helm-upgrade-rollback.sh run --values PATH \
#     --confirm-real-kubernetes [--port N]

# shellcheck source=scripts/environment/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

# The committed descriptor this workflow reads its own budgets and targets from,
# relative to the repository root. The Python tool refuses the descriptor if it
# disagrees with the Kubernetes certification about the cluster, the release, the
# request, or a shared budget.
readonly INFEROPS_EXPERIMENT_REL="deploy/serving/experiments/helm-upgrade-rollback.v1.json"
readonly INFEROPS_EXPERIMENT_MODULE="tools.helm_upgrade_rollback"

# The loopback port the forward is opened on. Not a threshold: a contributor may
# already be running the local composition, which holds the API's own port.
readonly INFEROPS_DEFAULT_FORWARD_PORT="18091"

# How much of each container's log a failure keeps. Also not a threshold: it
# bounds an artifact, not a decision.
readonly INFEROPS_LOG_TAIL="200"

action=""
values_file=""
confirmed=0
forward_port="${INFEROPS_DEFAULT_FORWARD_PORT}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    check | run)
      [ -z "${action}" ] ||
        inferops::fail "two actions were given ('${action}' and '$1'). This script performs one at a time, so that its output describes what it did."
      action="$1"
      shift
      ;;
    --values)
      [ "$#" -ge 2 ] || inferops::fail "--values needs a path. Usage: helm-upgrade-rollback.sh run --values PATH --confirm-real-kubernetes"
      values_file="$2"
      shift 2
      ;;
    --port)
      [ "$#" -ge 2 ] || inferops::fail "--port needs a number."
      case "$2" in
        '' | *[!0-9]*) inferops::fail "--port must be a number, not '$2'." ;;
      esac
      # A range as well as a shape. Zero is the one value that would be accepted
      # by every check below and still be wrong: `kubectl port-forward` reads it
      # as "pick an ephemeral port", this script never parses the port it
      # actually bound, and the run would fail later as an unopened forward
      # rather than here as a bad argument.
      if [ "$2" -lt 1 ] || [ "$2" -gt 65535 ]; then
        inferops::fail "--port must be between 1 and 65535, not '$2'."
      fi
      forward_port="$2"
      shift 2
      ;;
    --confirm-real-kubernetes)
      confirmed=1
      shift
      ;;
    *)
      inferops::fail "unknown argument '$1'. Usage: helm-upgrade-rollback.sh check|run [--values PATH] [--port N] [--confirm-real-kubernetes]"
      ;;
  esac
done

[ -n "${action}" ] ||
  inferops::fail "expected one of check, run. Usage: helm-upgrade-rollback.sh check|run [--values PATH] [--port N] [--confirm-real-kubernetes]"

inferops::require_cmd python

experiment_file="${INFEROPS_ROOT}/${INFEROPS_EXPERIMENT_REL}"
[ -f "${experiment_file}" ] ||
  inferops::fail "no experiment descriptor at ${INFEROPS_EXPERIMENT_REL}"

# --- check: reads files, contacts nothing -----------------------------------

if [ "${action}" = "check" ]; then
  inferops::section "Experiment descriptor"
  (cd "${INFEROPS_ROOT}" && python -m "${INFEROPS_EXPERIMENT_MODULE}" check)
  inferops::log "the descriptor validated. Nothing was contacted and no release was installed."
  exit 0
fi

# --- everything below reaches a cluster and a real model --------------------

[ "${confirmed}" -eq 1 ] ||
  inferops::fail "run needs --confirm-real-kubernetes. It applies the Terraform prerequisites, installs a release, loads a real model, deliberately breaks a candidate, rolls it back, and sends a real inference request. Usage: helm-upgrade-rollback.sh run --values PATH --confirm-real-kubernetes"

[ -n "${values_file}" ] ||
  inferops::fail "--values is required. The chart's shipped defaults select no serving profile and are refused on purpose, so there is no values file this script could reasonably assume. See docs/environment/helm-upgrade-rollback.md."

[ -f "${values_file}" ] ||
  inferops::fail "no such values file: ${values_file}"

inferops::require_cmd kubectl
inferops::require_cmd helm
inferops::require_cmd terraform
inferops::require_engine
# The provider-aware target this project consumes rather than creates
# (docs/environment/local-cluster-provider-contract.md): an explicit
# INFEROPS_PROVIDER, and for kind an explicit INFEROPS_KIND_CLUSTER_NAME, with
# no default, re-verified now rather than trusted from an earlier run.
inferops::resolve_target

# This experiment's own descriptor and evidence tooling below are still specific
# to the kind cluster this repository pins; porting them to a provider-neutral
# target is V1-S3-011. Re-verifying through inferops::resolve_target above
# closes `selection-is-explicit` for this workflow; this closes the rest of the
# gap honestly rather than silently: a Docker Desktop target passes the check
# above and is refused here instead of being run against a descriptor that does
# not describe it.
if [ "${INFEROPS_TARGET_PROVIDER}" != "kind" ] ||
  [ "${INFEROPS_TARGET_CLUSTER_NAME}" != "${INFEROPS_CLUSTER_NAME}" ]; then
  inferops::fail "refusing: capability-unknown-or-insufficient: this experiment's descriptor and evidence tooling are still specific to provider 'kind', cluster '${INFEROPS_CLUSTER_NAME}'. The selected target is provider '${INFEROPS_TARGET_PROVIDER}', cluster '${INFEROPS_TARGET_CLUSTER_NAME}'. Porting this workflow to a provider-neutral target is V1-S3-011."
fi

inferops::section "Experiment descriptor"
(cd "${INFEROPS_ROOT}" && python -m "${INFEROPS_EXPERIMENT_MODULE}" check)

# The descriptor's own values, read only after the tool above accepted it. A
# field read from a document nothing validated is a threshold with no authority.
read_descriptor() {
  python -c '
import json, sys
from pathlib import Path

record = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
for path in sys.argv[2:]:
    cursor = record
    for member in path.split("."):
        cursor = cursor[member]
    print(cursor)
' "$(inferops::native_path "${experiment_file}")" "$@"
}

# Read into a variable first and check the status, rather than through a process
# substitution: a reader whose producer failed sees empty fields and no error,
# and an empty budget below becomes an arithmetic expression rather than a
# refusal.
if ! descriptor_fields="$(read_descriptor \
  cluster.name cluster.context \
  release.name release.namespace \
  release.apiDeploymentName release.runtimeDeploymentName \
  release.apiComponent release.runtimeComponent \
  candidate.valuesPath candidate.candidateValue candidate.configMapKey \
  faultInjection.valuesPath faultInjection.injectedSizeBytes \
  faultInjection.failsInContainer \
  detection.pollIntervalMs \
  impact.probePath impact.probeIntervalMs impact.probeTimeoutMs \
  request.host readiness.installBudgetMs readiness.runtimeRolloutBudgetMs \
  readiness.apiRolloutBudgetMs readiness.releaseTestBudgetMs \
  readiness.forwardBudgetMs readiness.upgradeBudgetMs \
  readiness.failureDetectionBudgetMs readiness.rollbackBudgetMs \
  readiness.uninstallBudgetMs \
  evidence.lifecycleFile evidence.impactFile evidence.cleanupFile)"; then
  inferops::fail "the experiment descriptor could not be read after it validated. Nothing was installed."
fi

{
  read -r descriptor_cluster
  read -r descriptor_context
  read -r descriptor_release
  read -r descriptor_namespace
  read -r descriptor_api_deployment
  read -r descriptor_runtime_deployment
  read -r descriptor_api_component
  read -r descriptor_runtime_component
  read -r candidate_values_path
  read -r candidate_value
  read -r candidate_config_key
  read -r fault_values_path
  read -r fault_size_bytes
  read -r fault_container
  read -r detection_poll_ms
  read -r probe_path
  read -r probe_interval_ms
  read -r probe_timeout_ms
  read -r descriptor_host
  read -r install_budget_ms
  read -r runtime_rollout_budget_ms
  read -r api_rollout_budget_ms
  read -r release_test_budget_ms
  read -r forward_budget_ms
  read -r upgrade_budget_ms
  read -r detection_budget_ms
  read -r rollback_budget_ms
  read -r uninstall_budget_ms
  read -r lifecycle_rel
  read -r impact_rel
  read -r cleanup_rel
} <<<"${descriptor_fields}"

for field in descriptor_cluster descriptor_context descriptor_release \
  descriptor_namespace descriptor_api_deployment descriptor_runtime_deployment \
  descriptor_api_component descriptor_runtime_component candidate_values_path \
  candidate_value candidate_config_key fault_values_path fault_size_bytes \
  fault_container detection_poll_ms probe_path probe_interval_ms \
  probe_timeout_ms descriptor_host install_budget_ms \
  runtime_rollout_budget_ms api_rollout_budget_ms release_test_budget_ms \
  forward_budget_ms upgrade_budget_ms detection_budget_ms rollback_budget_ms \
  uninstall_budget_ms lifecycle_rel impact_rel cleanup_rel; do
  [ -n "${!field}" ] ||
    inferops::fail "the experiment descriptor left '${field}' empty. Nothing was installed."
done

# Every value that reaches shell arithmetic or a timeout is held to being a
# number here, at the point of use. The Python validator already refuses a
# non-integer, but that is a different file: a guard whose correctness depends on
# the order two programs run in is a guard waiting to be reordered.
for number in fault_size_bytes detection_poll_ms probe_interval_ms \
  probe_timeout_ms install_budget_ms runtime_rollout_budget_ms \
  api_rollout_budget_ms release_test_budget_ms forward_budget_ms \
  upgrade_budget_ms detection_budget_ms rollback_budget_ms \
  uninstall_budget_ms; do
  case "${!number}" in
    '' | *[!0-9]*)
      inferops::fail "the experiment descriptor's '${number}' is not a number. Nothing was installed."
      ;;
  esac
done

# A floor as well as a shape, for the one value that reaches `sleep` after an
# integer division. Below a thousand milliseconds that division is zero and the
# detection loop becomes a busy poll against the API server. The Python validator
# already refuses it, and the comment above says why that is not enough on its
# own: this is the magnitude half of the same argument.
[ "${detection_poll_ms}" -ge 1000 ] ||
  inferops::fail "the experiment descriptor polls for the failure every ${detection_poll_ms} ms. Below 1000 ms the wait between polls truncates to zero and this loop would spin against the API server. Nothing was installed."

# The two component names and the verification container name reach a label
# selector and a jsonpath filter, so they are held to the shape of a Kubernetes
# name here, where they are about to be used. The descriptor is a committed file
# and the Python validator already refuses an empty one, which makes this defence
# in depth rather than input validation -- but the same was true of the candidate
# value below, and a rule applied to one interpolation and not the next is a rule
# a later edit will read as optional.
for name in fault_container descriptor_api_component descriptor_runtime_component; do
  case "${!name}" in
    [a-z0-9]*[a-z0-9] | [a-z0-9]) ;;
    *) inferops::fail "the descriptor's '${name}' is '${!name}', which is not a DNS-1123 label. Nothing was installed." ;;
  esac
  case "${!name}" in
    *[!a-z0-9-]*) inferops::fail "the descriptor's '${name}' is '${!name}', which contains a character a DNS-1123 label may not. Nothing was installed." ;;
  esac
done

# The candidate value reaches a `--set` argument and the record. A value that
# could be read as a flag or that carries shell metacharacters is refused here,
# where it is about to be used, rather than trusted for having come out of a
# committed file.
case "${candidate_value}" in
  [A-Za-z0-9]*) ;;
  *) inferops::fail "the descriptor's candidate value '${candidate_value}' does not begin with an alphanumeric character. Nothing was installed." ;;
esac
case "${candidate_value}" in
  *[!A-Za-z0-9._-]*) inferops::fail "the descriptor's candidate value '${candidate_value}' contains a character a plain identifier may not. Nothing was installed." ;;
esac

# The two values paths reach `--set` as the left-hand side. They are compared
# against the only two this experiment may change, because a `--set` whose path
# came from a document is a `--set` that could set anything.
[ "${candidate_values_path}" = "telemetry.serviceVersion" ] ||
  inferops::fail "the descriptor's controlled change is '${candidate_values_path}' and this script only sets 'telemetry.serviceVersion'. Nothing was installed."
[ "${fault_values_path}" = "model.artifact.sizeBytes" ] ||
  inferops::fail "the descriptor's injected fault is '${fault_values_path}' and this script only sets 'model.artifact.sizeBytes'. Nothing was installed."

# Four records name one target, and they are compared rather than assumed.
[ "${descriptor_cluster}" = "${INFEROPS_CLUSTER_NAME}" ] ||
  inferops::fail "the descriptor names cluster '${descriptor_cluster}' and these scripts operate '${INFEROPS_CLUSTER_NAME}'."
[ "${descriptor_context}" = "${INFEROPS_KUBE_CONTEXT}" ] ||
  inferops::fail "the descriptor names context '${descriptor_context}' and these scripts operate '${INFEROPS_KUBE_CONTEXT}'."
[ "${descriptor_release}" = "${INFEROPS_RELEASE_NAME}" ] ||
  inferops::fail "the descriptor names release '${descriptor_release}' and these scripts operate '${INFEROPS_RELEASE_NAME}'."
[ "${descriptor_namespace}" = "${INFEROPS_RELEASE_NAMESPACE}" ] ||
  inferops::fail "the descriptor names namespace '${descriptor_namespace}' and these scripts operate '${INFEROPS_RELEASE_NAMESPACE}'."

# Not input validation: the namespace is a readonly constant in lib.sh and
# nothing here can change it. It is here for the edit that changes that constant
# -- ADR 0001 (D5) makes the prefix the isolation rule, and the chart's own
# refusal only fires once a render has been reached.
case "${INFEROPS_RELEASE_NAMESPACE}" in
  inferops-*) ;;
  *) inferops::fail "the release namespace must be prefixed 'inferops-' (ADR 0001 D5). It is '${INFEROPS_RELEASE_NAMESPACE}', which means the constant in lib.sh was changed without this rule being reconsidered." ;;
esac

chart_dir="${INFEROPS_ROOT}/${INFEROPS_CHART_PATH}"
[ -d "${chart_dir}" ] || inferops::fail "no chart at ${INFEROPS_CHART_PATH}"

chart_path="$(inferops::native_path "${chart_dir}")"
values_path="$(inferops::native_path "$(cd "$(dirname "${values_file}")" && pwd)/$(basename "${values_file}")")"

diag_dir="${INFEROPS_ARTIFACT_DIR}/helm-upgrade-rollback"
stage_dir="${diag_dir}/stages"
lifecycle_file="${INFEROPS_ROOT}/${lifecycle_rel}"
impact_file="${INFEROPS_ROOT}/${impact_rel}"
cleanup_file="${INFEROPS_ROOT}/${cleanup_rel}"
forward_log="${diag_dir}/forward.log"
probe_flag="${diag_dir}/probing"

# Every process this script backgrounds, declared here rather than where each one
# is started. Two reasons, and the second is the load-bearing one: under `nounset`
# a cleanup function referring to a pid that has not been assigned yet is itself
# an error, and `stop_background` runs from the exit trap at points before all
# three exist.
forward_pid=""
prober_pid=""
fault_upgrade_pid=""

# --- bounded measurement ----------------------------------------------------

# Wall-clock milliseconds rather than a monotonic counter, because the impact
# prober is a separate process and the two have to share an origin. Over the
# minutes this experiment spans that is a duration and not a timestamp; the
# record carries only differences.
now_ms() { printf '%s' "$(($(date +%s%N) / 1000000))"; }

# --- diagnostics and teardown ------------------------------------------------

collect_diagnostics() {
  mkdir -p "${diag_dir}"
  inferops::warn "collecting diagnostics into .artifacts/helm-upgrade-rollback/"
  inferops::helm list --namespace "${INFEROPS_RELEASE_NAMESPACE}" >"${diag_dir}/releases.txt" 2>&1 || true
  inferops::helm history "${INFEROPS_RELEASE_NAME}" \
    --namespace "${INFEROPS_RELEASE_NAMESPACE}" >"${diag_dir}/history.txt" 2>&1 || true
  inferops::kubectl get all,configmap,serviceaccount,pvc \
    -n "${INFEROPS_RELEASE_NAMESPACE}" -o wide >"${diag_dir}/get-all.txt" 2>&1 || true
  inferops::kubectl describe pods -n "${INFEROPS_RELEASE_NAMESPACE}" >"${diag_dir}/describe-pods.txt" 2>&1 || true
  inferops::kubectl get events -n "${INFEROPS_RELEASE_NAMESPACE}" \
    --sort-by=.lastTimestamp >"${diag_dir}/events.txt" 2>&1 || true
  inferops::kubectl logs -n "${INFEROPS_RELEASE_NAMESPACE}" \
    -l "${INFEROPS_RELEASE_SELECTOR}" --all-containers --tail="${INFEROPS_LOG_TAIL}" >"${diag_dir}/release.log" 2>&1 || true
}

# Every backgrounded process, stopped in the order that leaves the least behind:
# the prober first because it only reads, then the failing upgrade, then the
# forward it was reading through.
#
# The upgrade is the one that matters and the one that is easy to forget. It is a
# `helm upgrade` against a real release, and a run that ended between backgrounding
# it and waiting for it -- an interrupt during the detection loop, or a refusal
# inside it -- would leave it running detached, still writing to that release's
# history, while this script printed the `helm uninstall` that would race it.
stop_background() {
  rm -f "${probe_flag}" 2>/dev/null || true
  if [ -n "${prober_pid}" ] && kill -0 "${prober_pid}" 2>/dev/null; then
    wait "${prober_pid}" 2>/dev/null || true
  fi
  if [ -n "${fault_upgrade_pid}" ] && kill -0 "${fault_upgrade_pid}" 2>/dev/null; then
    kill "${fault_upgrade_pid}" 2>/dev/null || true
    wait "${fault_upgrade_pid}" 2>/dev/null || true
  fi
  if [ -n "${forward_pid}" ] && kill -0 "${forward_pid}" 2>/dev/null; then
    kill "${forward_pid}" 2>/dev/null || true
    wait "${forward_pid}" 2>/dev/null || true
  fi
}

on_exit() {
  local rc=$?
  stop_background
  if [ "${rc}" -ne 0 ]; then
    collect_diagnostics
    inferops::warn "the release was left in place. Remove it with: helm uninstall ${INFEROPS_RELEASE_NAME} --namespace ${INFEROPS_RELEASE_NAMESPACE}"
    inferops::warn "the prerequisites and the model cache claim were not touched and are not removed by that command."
  fi
  exit "${rc}"
}

# INT and TERM as well as EXIT, which is the convention both Kubernetes
# certification scripts already follow. Bash normally runs an EXIT trap when a
# signal terminates the shell, but this workflow leaves a background forward, a
# background prober, a background upgrade, and a real release behind, and on Git
# Bash signal delivery to a native child is less predictable than on Linux.
# Naming the signals costs nothing and removes the need to rely on that.
trap on_exit INT TERM EXIT

mkdir -p "${stage_dir}"
rm -f "${stage_dir}"/*.json 2>/dev/null || true

# --- prerequisites -----------------------------------------------------------

inferops::section "Applying the Terraform prerequisites"

bash "${INFEROPS_ROOT}/scripts/environment/terraform-prerequisites.sh" apply

inferops::claim_count() {
  local output
  if ! output="$(inferops::kubectl get pvc \
    -n "${INFEROPS_RELEASE_NAMESPACE}" -o name)"; then
    return 1
  fi
  printf '%s' "${output}" | grep -c . || true
}

if ! claims_before="$(inferops::claim_count)"; then
  inferops::fail "could not count the persistent volume claims before installing. An unanswered query is not an empty result, and the assertion that this experiment left the claim alone depends on the difference."
fi
inferops::log "persistent volume claims present before install: ${claims_before}"

if inferops::helm status "${INFEROPS_RELEASE_NAME}" \
  --namespace "${INFEROPS_RELEASE_NAMESPACE}" >/dev/null 2>&1; then
  inferops::fail "release '${INFEROPS_RELEASE_NAME}' already exists in '${INFEROPS_RELEASE_NAMESPACE}'. This experiment starts from an install, so an existing release would make its first revision something other than the known-good one it reports. Remove it first: helm uninstall ${INFEROPS_RELEASE_NAME} --namespace ${INFEROPS_RELEASE_NAMESPACE}"
fi

# --- collecting one revision as a fact ---------------------------------------

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

# The byte count the cluster will actually compare against, read out of the
# rendered init container command rather than out of the values file or out of
# `helm get values`. Both of those are Helm's bookkeeping; this is the workload.
runtime_verify_command() {
  inferops::kubectl get deployment "${descriptor_runtime_deployment}" \
    -n "${INFEROPS_RELEASE_NAMESPACE}" \
    -o "jsonpath={.spec.template.spec.initContainers[?(@.name==\"${fault_container}\")].command[2]}"
}

# The ready pod of one component, or nothing when none is ready. Used to tell a
# rollout that replaced a pod from one that did not, and to name the pod that
# kept serving while the unhealthy candidate failed.
ready_pod_of() {
  local component="$1"
  local pods
  pods="$(inferops::kubectl get pods \
    -n "${INFEROPS_RELEASE_NAMESPACE}" \
    -l "${INFEROPS_RELEASE_SELECTOR},app.kubernetes.io/component=${component}" \
    -o json)" || return 1
  INFEROPS_PODS_JSON="${pods}" python -c '
import json, os

pods = json.loads(os.environ["INFEROPS_PODS_JSON"]).get("items", [])
for pod in pods:
    conditions = pod.get("status", {}).get("conditions", [])
    ready = any(c.get("type") == "Ready" and c.get("status") == "True" for c in conditions)
    if ready:
        print(pod.get("metadata", {}).get("name", ""))
        break
'
}

record_stage() {
  local stage="$1" outcome="$2" elapsed_ms="$3" ready_ms="$4" test_passed="$5"
  local release_json service_version verify_command runtime_pod api_pod

  release_json="$(require_query "the release's own status" \
    inferops::helm list --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
    --filter "^${INFEROPS_RELEASE_NAME}\$" -o json)"

  # Each of these four may legitimately come back empty and none of them may
  # legitimately go unasked, so the status is checked and the value is not.
  #
  # `${candidate_config_key}` is empty in the known-good release and carries the
  # candidate value afterwards, which is the whole of the assertion that the
  # upgrade reached the workload; a query the API server refused would be
  # recorded as that empty string and the run would then report that the change
  # never arrived, which names the wrong thing entirely. The two pod names are
  # empty whenever no pod of that component is ready -- which is the expected
  # state during the unhealthy stage -- and that is a different fact from a
  # query nobody answered.
  if ! service_version="$(inferops::kubectl get configmap \
    -n "${INFEROPS_RELEASE_NAMESPACE}" -l "${INFEROPS_RELEASE_SELECTOR}" \
    -o "jsonpath={.items[*].data.${candidate_config_key}}")"; then
    inferops::fail "could not read ${candidate_config_key} from the release's rendered configuration at the '${stage}' stage. An unanswered query is not an empty value, and whether the upgrade reached the workload is decided by the difference."
  fi
  if ! verify_command="$(runtime_verify_command)"; then
    inferops::fail "could not read the '${fault_container}' init container's command at the '${stage}' stage. An unanswered query is not an empty command, and the byte count this experiment injects and rolls back is read out of it."
  fi
  if ! runtime_pod="$(ready_pod_of "${descriptor_runtime_component}")"; then
    inferops::fail "could not ask which ${descriptor_runtime_component} pod is ready at the '${stage}' stage. An unanswered query is not an absent pod, and whether a rollout replaced the serving pod is decided by the difference."
  fi
  if ! api_pod="$(ready_pod_of "${descriptor_api_component}")"; then
    inferops::fail "could not ask which ${descriptor_api_component} pod is ready at the '${stage}' stage. An unanswered query is not an absent pod."
  fi

  INFEROPS_STAGE="${stage}" \
    INFEROPS_OUTCOME="${outcome}" \
    INFEROPS_ELAPSED_MS="${elapsed_ms}" \
    INFEROPS_READY_MS="${ready_ms}" \
    INFEROPS_TEST_PASSED="${test_passed}" \
    INFEROPS_RELEASE_JSON="${release_json}" \
    INFEROPS_SERVICE_VERSION="${service_version}" \
    INFEROPS_VERIFY_COMMAND="${verify_command}" \
    INFEROPS_RUNTIME_POD="${runtime_pod}" \
    INFEROPS_API_POD="${api_pod}" \
    python - "$(inferops::native_path "${stage_dir}/${stage}.json")" <<'STAGE_PYTHON'
import json
import os
import re
import sys
from pathlib import Path


def fact(name: str) -> str:
    return os.environ.get(f"INFEROPS_{name}", "")


def number(name: str) -> int:
    value = fact(name).strip()
    return int(value) if value.isdigit() else 0


release = json.loads(fact("RELEASE_JSON") or "[]") or [{}]

# The byte count the pod will compare against, taken from the command the
# cluster holds. The chart renders it as a shell comparison against a quoted
# literal, so the literal is what a pod would actually enforce -- and reading it
# here rather than reading the values file is the difference between "the
# operator asked for this" and "the workload carries it".
match = re.search(r'!=\s*"(\d+)"', fact("VERIFY_COMMAND"))

document = {
    "stage": fact("STAGE"),
    "revision": release[0].get("revision", 0),
    "status": release[0].get("status", ""),
    "outcome": fact("OUTCOME"),
    "serviceVersion": fact("SERVICE_VERSION"),
    "artifactSizeBytes": int(match.group(1)) if match else 0,
    "elapsedMs": number("ELAPSED_MS"),
    "readyMs": number("READY_MS"),
    "releaseTestPassed": fact("TEST_PASSED") == "true",
    "runtimePod": fact("RUNTIME_POD"),
    "apiPod": fact("API_POD"),
}

Path(sys.argv[1]).write_text(
    json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
)
STAGE_PYTHON
  inferops::log "recorded the '${stage}' stage."
}

# --- the known-good release --------------------------------------------------

inferops::section "Installing the known-good release"

# Deliberately without `--wait`, so that readiness is measured separately rather
# than folded into an install. `--create-namespace` is absent and must stay
# absent: the namespace is Terraform's, and Helm creating it would make this
# release's uninstall delete a prerequisite.
baseline_started="$(now_ms)"
inferops::helm install "${INFEROPS_RELEASE_NAME}" "${chart_path}" \
  --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
  --values "${values_path}" \
  --timeout "$((install_budget_ms / 1000))s"

baseline_ready_started="$(now_ms)"
inferops::kubectl rollout status "deployment/${descriptor_runtime_deployment}" \
  -n "${INFEROPS_RELEASE_NAMESPACE}" --timeout="$((runtime_rollout_budget_ms / 1000))s"
inferops::kubectl rollout status "deployment/${descriptor_api_deployment}" \
  -n "${INFEROPS_RELEASE_NAMESPACE}" --timeout="$((api_rollout_budget_ms / 1000))s"
baseline_ready_ms=$(($(now_ms) - baseline_ready_started))

inferops::helm test "${INFEROPS_RELEASE_NAME}" \
  --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
  --logs \
  --timeout "$((release_test_budget_ms / 1000))s"

baseline_ms=$(($(now_ms) - baseline_started))
record_stage baseline healthy "${baseline_ms}" "${baseline_ready_ms}" true

# --- the controlled candidate ------------------------------------------------

inferops::section "Upgrading to the controlled candidate"

# `telemetry.serviceVersion` is used because it reaches the rendered ConfigMap
# and therefore the pod-template checksum: an upgrade that set something inert
# would produce a revision Helm records and Kubernetes never acts on, and rolling
# that back would prove nothing about whether the workload followed.
candidate_started="$(now_ms)"
inferops::helm upgrade "${INFEROPS_RELEASE_NAME}" "${chart_path}" \
  --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
  --values "${values_path}" \
  --set "${candidate_values_path}=${candidate_value}" \
  --timeout "$((upgrade_budget_ms / 1000))s"

candidate_ready_started="$(now_ms)"
inferops::kubectl rollout status "deployment/${descriptor_runtime_deployment}" \
  -n "${INFEROPS_RELEASE_NAMESPACE}" --timeout="$((runtime_rollout_budget_ms / 1000))s"
inferops::kubectl rollout status "deployment/${descriptor_api_deployment}" \
  -n "${INFEROPS_RELEASE_NAMESPACE}" --timeout="$((api_rollout_budget_ms / 1000))s"
candidate_ready_ms=$(($(now_ms) - candidate_ready_started))

inferops::helm test "${INFEROPS_RELEASE_NAME}" \
  --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
  --logs \
  --timeout "$((release_test_budget_ms / 1000))s"

candidate_ms=$(($(now_ms) - candidate_started))
record_stage candidate healthy "${candidate_ms}" "${candidate_ready_ms}" true

# Captured first and parsed second, rather than piped straight into python. A
# pipeline aborts correctly either way -- `pipefail` carries the failure through
# the assignment -- but with the pipe, a `helm list` that did not answer still
# runs python against empty input, and the operator sees a JSON traceback stacked
# on top of the refusal that explains it. Two failures for one cause reads as two
# causes.
candidate_release_json="$(require_query "the known-good revision to roll back to" \
  inferops::helm list --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
  --filter "^${INFEROPS_RELEASE_NAME}\$" -o json)"
candidate_revision="$(INFEROPS_RELEASE_JSON="${candidate_release_json}" python -c '
import json, os

print(json.loads(os.environ["INFEROPS_RELEASE_JSON"])[0]["revision"])
')"
case "${candidate_revision}" in
  '' | *[!0-9]*) inferops::fail "the known-good revision is not a number, so there is nothing this run could safely roll back to." ;;
esac
inferops::log "the last known-good revision is ${candidate_revision}."

# --- the forward the impact probe and the verification both use --------------

inferops::section "Forwarding the API Service"

api_service="$(require_query "the release's API Service name" \
  read_descriptor release.apiServiceName)"
api_port="$(require_query "the release's API Service port" \
  read_descriptor release.apiServicePort)"

mkdir -p "${diag_dir}"
inferops::kubectl port-forward "service/${api_service}" \
  "${forward_port}:${api_port}" \
  -n "${INFEROPS_RELEASE_NAMESPACE}" --address "${descriptor_host}" >"${forward_log}" 2>&1 &
forward_pid="$!"

forward_deadline=$((SECONDS + forward_budget_ms / 1000))
forward_open=0
while [ "${SECONDS}" -lt "${forward_deadline}" ]; do
  if ! kill -0 "${forward_pid}" 2>/dev/null; then
    inferops::fail "the port-forward exited before it accepted a connection. Its output is in .artifacts/helm-upgrade-rollback/forward.log."
  fi
  if INFEROPS_FORWARD_HOST="${descriptor_host}" INFEROPS_FORWARD_PORT="${forward_port}" python -c '
import os, socket, sys

host = os.environ["INFEROPS_FORWARD_HOST"]
port = int(os.environ["INFEROPS_FORWARD_PORT"])
try:
    with socket.create_connection((host, port), timeout=1):
        sys.exit(0)
except OSError:
    sys.exit(1)
'; then
    forward_open=1
    break
  fi
  sleep 1
done
[ "${forward_open}" -eq 1 ] ||
  inferops::fail "the forward did not accept a connection within ${forward_budget_ms} ms."

base_url="http://${descriptor_host}:${forward_port}"
inferops::log "the API Service is forwarded to ${base_url}."

# --- the unhealthy candidate -------------------------------------------------

inferops::section "Upgrading to a candidate the cluster cannot run"

inferops::log "injecting ${fault_values_path}=${fault_size_bytes}, which the mounted artifact cannot match."
inferops::log "this changes no image reference, pulls nothing, creates no object outside the release, and is removed by the rollback."

fault_started="$(now_ms)"

# The impact prober runs beside the failing rollout rather than after it: what a
# caller saw is only answerable while the candidate is failing. It asks the
# release's own readiness path through the forward, which is the answer a caller
# in front of the Service would get.
: >"${probe_flag}"
INFEROPS_PROBE_URL="${base_url}${probe_path}" \
  INFEROPS_PROBE_INTERVAL_MS="${probe_interval_ms}" \
  INFEROPS_PROBE_TIMEOUT_MS="${probe_timeout_ms}" \
  INFEROPS_PROBE_ORIGIN_MS="${fault_started}" \
  INFEROPS_PROBE_PATH="${probe_path}" \
  INFEROPS_PROBE_FLAG="$(inferops::native_path "${probe_flag}")" \
  python - "$(inferops::native_path "${impact_file}")" <<'PROBE_PYTHON' &
import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

url = os.environ["INFEROPS_PROBE_URL"]
interval = int(os.environ["INFEROPS_PROBE_INTERVAL_MS"]) / 1000
timeout = int(os.environ["INFEROPS_PROBE_TIMEOUT_MS"]) / 1000
origin_ms = int(os.environ["INFEROPS_PROBE_ORIGIN_MS"])
flag = Path(os.environ["INFEROPS_PROBE_FLAG"])
target = Path(sys.argv[1])


def now_ms() -> int:
    return int(time.time() * 1000) - origin_ms


def probe() -> tuple[int, bool]:
    """One readiness answer. A status of zero is 'nothing answered at all'."""
    try:
        with urllib.request.urlopen(url, timeout=timeout) as response:
            return response.status, response.status == 200
    except urllib.error.HTTPError as error:
        return error.code, False
    except OSError:
        return 0, False


started = now_ms()
probes: list[dict[str, object]] = []
while flag.exists():
    at = now_ms()
    status, ok = probe()
    probes.append({"atMs": at, "status": status, "ok": ok})
    # The flag is checked again before sleeping, so a stop signal does not have
    # to wait out a whole interval before the record is written.
    if not flag.exists():
        break
    time.sleep(interval)

document = {
    "probePath": os.environ["INFEROPS_PROBE_PATH"],
    "window": {"startedMs": started, "endedMs": now_ms()},
    "probes": probes,
}
target.parent.mkdir(parents=True, exist_ok=True)
target.write_text(
    json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
)
PROBE_PYTHON
prober_pid="$!"

# Deliberately without `--wait` and without a rollout wait. This upgrade is
# expected to fail, and waiting for it would turn the detection into a timeout --
# which is the one reading this experiment refuses, because a deadline is a
# statement about elapsed time rather than about health.
inferops::helm upgrade "${INFEROPS_RELEASE_NAME}" "${chart_path}" \
  --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
  --values "${values_path}" \
  --set "${candidate_values_path}=${candidate_value}" \
  --set "${fault_values_path}=${fault_size_bytes}" \
  --timeout "$((upgrade_budget_ms / 1000))s" &
fault_upgrade_pid="$!"

inferops::section "Watching for the failure"

detection_signal=""
detection_exit_code=""
detection_reason=""
detection_pod=""
serving_pod=""
detected_at_ms=0
detection_deadline=$((SECONDS + detection_budget_ms / 1000))

while [ "${SECONDS}" -lt "${detection_deadline}" ]; do
  pods_json="$(inferops::kubectl get pods \
    -n "${INFEROPS_RELEASE_NAMESPACE}" \
    -l "${INFEROPS_RELEASE_SELECTOR},app.kubernetes.io/component=${descriptor_runtime_component}" \
    -o json)" || pods_json=""
  deployment_json="$(inferops::kubectl get deployment "${descriptor_runtime_deployment}" \
    -n "${INFEROPS_RELEASE_NAMESPACE}" -o json)" || deployment_json=""
  finding="$(INFEROPS_PODS_JSON="${pods_json}" \
    INFEROPS_DEPLOYMENT_JSON="${deployment_json}" \
    INFEROPS_VERIFY_CONTAINER="${fault_container}" \
    python - <<'DETECT_PYTHON'
import json
import os

pods = json.loads(os.environ.get("INFEROPS_PODS_JSON") or "{}").get("items", [])
deployment = json.loads(os.environ.get("INFEROPS_DEPLOYMENT_JSON") or "{}")
container = os.environ["INFEROPS_VERIFY_CONTAINER"]


def ready(pod: dict) -> bool:
    return any(
        condition.get("type") == "Ready" and condition.get("status") == "True"
        for condition in pod.get("status", {}).get("conditions", [])
    )


def unschedulable(pod: dict) -> bool:
    return any(
        condition.get("type") == "PodScheduled"
        and condition.get("status") == "False"
        and condition.get("reason") == "Unschedulable"
        for condition in pod.get("status", {}).get("conditions", [])
    )


serving = next((pod["metadata"]["name"] for pod in pods if ready(pod)), "")

# Only pods that are NOT ready are inspected. The pod still serving has a
# succeeded init container of the same name, and reading its terminated state
# would report a zero exit code as a detection.
for pod in pods:
    if ready(pod):
        continue
    name = pod.get("metadata", {}).get("name", "")
    if unschedulable(pod):
        print(
            json.dumps(
                {
                    "signal": "candidate-pod-unschedulable",
                    "container": container,
                    "exitCode": 0,
                    "reason": "Unschedulable",
                    "pod": name,
                    "serving": serving,
                }
            )
        )
        break
    for status in pod.get("status", {}).get("initContainerStatuses", []):
        if status.get("name") != container:
            continue
        terminated = status.get("state", {}).get("terminated") or {}
        waiting = status.get("state", {}).get("waiting") or {}
        last = (status.get("lastState", {}).get("terminated")) or {}
        exit_code = terminated.get("exitCode", last.get("exitCode", 0))
        if waiting.get("reason") == "CrashLoopBackOff" and exit_code:
            print(
                json.dumps(
                    {
                        "signal": "init-container-crash-loop",
                        "container": container,
                        "exitCode": exit_code,
                        "reason": waiting.get("reason", ""),
                        "pod": name,
                        "serving": serving,
                    }
                )
            )
            break
        if terminated and terminated.get("exitCode", 0) != 0:
            print(
                json.dumps(
                    {
                        "signal": "init-container-nonzero-exit",
                        "container": container,
                        "exitCode": terminated.get("exitCode", 0),
                        "reason": terminated.get("reason", ""),
                        "pod": name,
                        "serving": serving,
                    }
                )
            )
            break
    else:
        continue
    break
else:
    for condition in deployment.get("status", {}).get("conditions", []):
        if (
            condition.get("type") == "Progressing"
            and condition.get("reason") == "ProgressDeadlineExceeded"
        ):
            print(
                json.dumps(
                    {
                        "signal": "progress-deadline-exceeded",
                        "container": container,
                        "exitCode": 0,
                        "reason": condition.get("reason", ""),
                        "pod": "",
                        "serving": serving,
                    }
                )
            )
            break
DETECT_PYTHON
  )" || finding=""
  if [ -n "${finding}" ]; then
    detected_at_ms=$(($(now_ms) - fault_started))
    # Read into a variable first and check the status. Every other query in this
    # file does that; this one did not, and it is the one running while a
    # backgrounded `helm upgrade` is still writing to the release -- so a failure
    # here that aborted the script mid-loop is exactly the case the cleanup path
    # has to survive.
    if ! finding_fields="$(INFEROPS_FINDING="${finding}" python -c '
import json, os

finding = json.loads(os.environ["INFEROPS_FINDING"])
for member in ("signal", "exitCode", "reason", "pod", "serving"):
    print(finding.get(member, ""))
')"; then
      inferops::fail "a failure signal was found and could not be read. The release is left in place and diagnostics are in .artifacts/helm-upgrade-rollback/."
    fi
    {
      read -r detection_signal
      read -r detection_exit_code
      read -r detection_reason
      read -r detection_pod
      read -r serving_pod
    } <<<"${finding_fields}"
    break
  fi
  sleep "$((detection_poll_ms / 1000))"
done

# The failing upgrade is still running; it is waited on rather than left behind,
# and its non-zero status is expected. `helm upgrade` is what created the
# candidate, so abandoning the process would leave a release lock behind.
#
# The pid is cleared afterwards so that the exit trap does not reach for a job
# that has already been reaped, the same way the prober's is cleared below.
wait "${fault_upgrade_pid}" 2>/dev/null || true
fault_upgrade_pid=""

rm -f "${probe_flag}"
wait "${prober_pid}" 2>/dev/null || true
prober_pid=""

[ -n "${detection_signal}" ] ||
  inferops::fail "no failure was detected within ${detection_budget_ms} ms. Either the fault did not reach the cluster or this run cannot read the signal it produced; the release is left in place and diagnostics are in .artifacts/helm-upgrade-rollback/."

inferops::log "detected '${detection_signal}' on ${detection_pod} after ${detected_at_ms} ms (exit ${detection_exit_code}, ${detection_reason})."
inferops::log "the pod still serving is ${serving_pod:-none}."

fault_ms=$(($(now_ms) - fault_started))
record_stage unhealthy-candidate failed "${fault_ms}" 0 false

# --- the rollback ------------------------------------------------------------

inferops::section "Rolling back to revision ${candidate_revision}"

rollback_started_at_ms=$(($(now_ms) - fault_started))
rollback_started="$(now_ms)"
inferops::helm rollback "${INFEROPS_RELEASE_NAME}" "${candidate_revision}" \
  --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
  --timeout "$((rollback_budget_ms / 1000))s"

rollback_ready_started="$(now_ms)"
inferops::kubectl rollout status "deployment/${descriptor_runtime_deployment}" \
  -n "${INFEROPS_RELEASE_NAMESPACE}" --timeout="$((runtime_rollout_budget_ms / 1000))s"
inferops::kubectl rollout status "deployment/${descriptor_api_deployment}" \
  -n "${INFEROPS_RELEASE_NAMESPACE}" --timeout="$((api_rollout_budget_ms / 1000))s"
rollback_ready_ms=$(($(now_ms) - rollback_ready_started))
rollback_finished_at_ms=$(($(now_ms) - fault_started))

inferops::helm test "${INFEROPS_RELEASE_NAME}" \
  --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
  --logs \
  --timeout "$((release_test_budget_ms / 1000))s"

rollback_ms=$(($(now_ms) - rollback_started))
verified_at_ms=$(($(now_ms) - fault_started))
record_stage rollback healthy "${rollback_ms}" "${rollback_ready_ms}" true

inferops::helm history "${INFEROPS_RELEASE_NAME}" \
  --namespace "${INFEROPS_RELEASE_NAMESPACE}"

# --- the collected record ----------------------------------------------------

inferops::section "Collecting lifecycle facts"

server_version_json="$(require_query "the API server's version" \
  inferops::kubectl version -o json)"
server_version="$(INFEROPS_VERSION_JSON="${server_version_json}" python -c '
import json, os

print(json.loads(os.environ["INFEROPS_VERSION_JSON"])["serverVersion"]["gitVersion"])
')"
helm_version="$(require_query "the helm version" \
  inferops::helm version --short)"
kubectl_version_json="$(require_query "the kubectl version" \
  inferops::kubectl version --client -o json)"
kubectl_version="$(INFEROPS_VERSION_JSON="${kubectl_version_json}" python -c '
import json, os

print(json.loads(os.environ["INFEROPS_VERSION_JSON"])["clientVersion"]["gitVersion"])
')"
node_digest="$(inferops::running_node_digest)"
configured="$(require_query "the release's rendered configuration" \
  inferops::kubectl get configmap -n "${INFEROPS_RELEASE_NAMESPACE}" \
  -l "${INFEROPS_RELEASE_SELECTOR}" -o json)"
release_json="$(require_query "the release's own status" \
  inferops::helm list --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
  --filter "^${INFEROPS_RELEASE_NAME}\$" -o json)"

mkdir -p "$(dirname "${lifecycle_file}")"

INFEROPS_CLUSTER_NAME_FACT="${INFEROPS_CLUSTER_NAME}" \
  INFEROPS_CONTEXT="${INFEROPS_KUBE_CONTEXT}" \
  INFEROPS_SERVER_VERSION="${server_version}" \
  INFEROPS_NODE_DIGEST="${node_digest}" \
  INFEROPS_HELM="${helm_version}" \
  INFEROPS_KUBECTL="${kubectl_version}" \
  INFEROPS_RELEASE_NAME_FACT="${INFEROPS_RELEASE_NAME}" \
  INFEROPS_NAMESPACE="${INFEROPS_RELEASE_NAMESPACE}" \
  INFEROPS_RELEASE_JSON="${release_json}" \
  INFEROPS_CONFIGMAP_JSON="${configured}" \
  INFEROPS_STAGE_DIR="$(inferops::native_path "${stage_dir}")" \
  INFEROPS_DETECTION_SIGNAL="${detection_signal}" \
  INFEROPS_DETECTION_WORKLOAD="${descriptor_runtime_component}" \
  INFEROPS_DETECTION_CONTAINER="${fault_container}" \
  INFEROPS_DETECTION_EXIT_CODE="${detection_exit_code}" \
  INFEROPS_DETECTION_REASON="${detection_reason:-none}" \
  INFEROPS_DETECTION_POD="${detection_pod:-none}" \
  INFEROPS_SERVING_POD="${serving_pod:-none}" \
  INFEROPS_DETECTED_AT_MS="${detected_at_ms}" \
  INFEROPS_ROLLBACK_STARTED_MS="${rollback_started_at_ms}" \
  INFEROPS_ROLLBACK_FINISHED_MS="${rollback_finished_at_ms}" \
  INFEROPS_VERIFIED_AT_MS="${verified_at_ms}" \
  python - "$(inferops::native_path "${lifecycle_file}")" <<'LIFECYCLE_PYTHON'
import json
import os
import sys
from pathlib import Path

ORDER = ("baseline", "candidate", "unhealthy-candidate", "rollback")


def fact(name: str) -> str:
    return os.environ.get(f"INFEROPS_{name}", "")


def number(name: str) -> int:
    value = fact(name).strip()
    return int(value) if value.lstrip("-").isdigit() else 0


stage_dir = Path(fact("STAGE_DIR"))
stages = []
for name in ORDER:
    path = stage_dir / f"{name}.json"
    if not path.is_file():
        raise SystemExit(f"the '{name}' stage was never recorded")
    stages.append(json.loads(path.read_text(encoding="utf-8")))

release = json.loads(fact("RELEASE_JSON") or "[]") or [{}]
configmaps = json.loads(fact("CONFIGMAP_JSON") or "{}").get("items", [])
data = configmaps[0].get("data", {}) if configmaps else {}

document = {
    "cluster": {
        "name": fact("CLUSTER_NAME_FACT"),
        "context": fact("CONTEXT"),
        "serverVersion": fact("SERVER_VERSION"),
        "nodeImageDigest": fact("NODE_DIGEST"),
    },
    "tooling": {"helm": fact("HELM"), "kubectl": fact("KUBECTL")},
    "release": {
        "name": fact("RELEASE_NAME_FACT"),
        "namespace": fact("NAMESPACE"),
        "chart": release[0].get("chart", ""),
        "profile": data.get("INFEROPS_SERVING_ADAPTER", ""),
    },
    "configuration": {
        "modelIdentifier": data.get("INFEROPS_MODEL_IDENTIFIER", ""),
        "modelRevision": data.get("INFEROPS_MODEL_REVISION", ""),
        "deploymentEnvironment": data.get("INFEROPS_DEPLOYMENT_ENVIRONMENT", ""),
    },
    "stages": stages,
    "detection": {
        "signal": fact("DETECTION_SIGNAL"),
        "workload": fact("DETECTION_WORKLOAD"),
        "container": fact("DETECTION_CONTAINER"),
        "exitCode": number("DETECTION_EXIT_CODE"),
        "reason": fact("DETECTION_REASON"),
        "detectedAfterMs": number("DETECTED_AT_MS"),
        "candidatePod": fact("DETECTION_POD"),
        "servingPod": fact("SERVING_POD"),
    },
    "recovery": {
        "injectedAtMs": 0,
        "detectedAtMs": number("DETECTED_AT_MS"),
        "rollbackStartedAtMs": number("ROLLBACK_STARTED_MS"),
        "rollbackFinishedAtMs": number("ROLLBACK_FINISHED_MS"),
        "verifiedAtMs": number("VERIFIED_AT_MS"),
    },
}

Path(sys.argv[1]).write_text(
    json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
)
LIFECYCLE_PYTHON

inferops::log "lifecycle facts written to ${lifecycle_rel}. They are host state, not evidence, and .artifacts/ is ignored by version control."

# --- the assertions, and the record ------------------------------------------

inferops::section "Evaluating the experiment"

(cd "${INFEROPS_ROOT}" && python -m "${INFEROPS_EXPERIMENT_MODULE}" evaluate \
  --confirm-real-kubernetes --base-url "${base_url}")

# --- teardown ----------------------------------------------------------------

inferops::section "Uninstalling"

stop_background

uninstall_started="$(now_ms)"
inferops::helm uninstall "${INFEROPS_RELEASE_NAME}" \
  --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
  --wait \
  --timeout "$((uninstall_budget_ms / 1000))s"
uninstall_ms=$(($(now_ms) - uninstall_started))

remaining="$(inferops::kubectl get \
  deployments,replicasets,services,configmaps,serviceaccounts,pods,pvc \
  -n "${INFEROPS_RELEASE_NAMESPACE}" -l "${INFEROPS_RELEASE_SELECTOR}" -o name)" ||
  inferops::fail "could not ask what survived the uninstall. An unanswered query is not an empty result."
remaining_count="$(printf '%s' "${remaining}" | grep -c . || true)"

helm_present=false
if inferops::helm status "${INFEROPS_RELEASE_NAME}" \
  --namespace "${INFEROPS_RELEASE_NAMESPACE}" >/dev/null 2>&1; then
  helm_present=true
fi

namespace_present=false
if inferops::kubectl get namespace "${INFEROPS_RELEASE_NAMESPACE}" >/dev/null 2>&1; then
  namespace_present=true
fi

if ! claims_after="$(inferops::claim_count)"; then
  inferops::fail "could not count the persistent volume claims after uninstalling. An unanswered query is not an empty result."
fi

mkdir -p "$(dirname "${cleanup_file}")"
INFEROPS_UNINSTALL_MS="${uninstall_ms}" \
  INFEROPS_REMAINING="${remaining_count}" \
  INFEROPS_HELM_PRESENT="${helm_present}" \
  INFEROPS_NAMESPACE_PRESENT="${namespace_present}" \
  INFEROPS_CLAIMS_BEFORE="${claims_before}" \
  INFEROPS_CLAIMS_AFTER="${claims_after}" \
  python - "$(inferops::native_path "${cleanup_file}")" <<'CLEANUP_PYTHON'
import json
import os
import sys
from pathlib import Path


def fact(name: str) -> str:
    return os.environ.get(f"INFEROPS_{name}", "")


def number(name: str) -> int:
    value = fact(name).strip()
    return int(value) if value.isdigit() else 0


document = {
    "uninstallMs": number("UNINSTALL_MS"),
    "releaseObjectsRemaining": number("REMAINING"),
    "helmReleasePresent": fact("HELM_PRESENT") == "true",
    "namespacePresent": fact("NAMESPACE_PRESENT") == "true",
    "claimsBefore": number("CLAIMS_BEFORE"),
    "claimsAfter": number("CLAIMS_AFTER"),
}

Path(sys.argv[1]).write_text(
    json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
)
CLEANUP_PYTHON

inferops::section "Recording the cleanup outcome"

# The record is written a second time rather than mutated. The first write is the
# experiment; this one adds the cleanup member and the assertions over it, which
# could not exist before the teardown. Nothing else in the record is re-derived.
(cd "${INFEROPS_ROOT}" && python -m "${INFEROPS_EXPERIMENT_MODULE}" record-cleanup)

inferops::section "Result"
inferops::log "install, upgrade, break, detect, roll back, verify, uninstall: all completed."
inferops::log "the namespace and every claim survived; no release object did."
inferops::log "the record is in .cache/inferops/experiments/ and is ignored by version control."
