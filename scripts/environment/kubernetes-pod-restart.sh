#!/usr/bin/env bash
# Proves that the model artifact survives a Kubernetes pod restart: a known-good
# release, one deleted serving pod, a replacement the Deployment controller made,
# the same Terraform-owned claim remounted, the same bytes still there, and a
# real completion afterwards.
#
# This is the experiment V1-S3-003 owed and could not run. Its evidence stopped a
# container on the host and started another, and its own record says in as many
# words that it is not a pod restart -- correctly, because at the time no API
# image was published and the claim had never been filled, so nothing could have
# scheduled a replacement pod against a surviving claim. Both exist now.
#
# What a pod coming back does not establish. A pod always comes back: that is
# what a Deployment is for. The questions worth asking are whether it is a
# *different* pod, whether it mounted the *same* claim, whether the bytes on that
# claim are the *same* bytes, and whether anything quietly re-acquired 1.83 GB
# while nobody was watching -- and the last one is invisible from outside unless
# it is asked, because a re-acquired artifact has the same size and the same
# digest as the one it replaced. What it does not have is the same inode and the
# same modification time, and those are read either side of the replacement.
#
# What it operates, and what it does not. It applies the Terraform prerequisite
# layer through scripts/environment/terraform-prerequisites.sh, installs one Helm
# release named by INFEROPS_RELEASE_NAME in INFEROPS_RELEASE_NAMESPACE, deletes
# exactly one pod by name, opens one loopback forward to that release's API
# Service, and uninstalls the release when it is done. It never removes the
# namespace, never removes the model cache claim, and never removes the cluster:
# those outlive a release by design (docs/architecture/resource-ownership.md).
#
# The one delete it performs is addressed to one pod, by the name the cluster
# gave it. A pod is not a declared object -- no tool in the ownership inventory
# owns one -- and deleting it changes no Deployment, no claim, no release
# revision, nothing cluster-scoped, and nothing in another namespace. Each of
# those is asserted rather than asserted about.
#
# The assertions and the record are not here. They are in
# tools/kubernetes_pod_restart, which reads the committed descriptor, refuses a
# forward that is not loopback, refuses a replacement that is the same pod, and
# writes the labelled record. The split is deliberate: the guard that establishes
# which cluster is being acted on already lives in lib.sh beside every other
# script here, and a second implementation of it in Python would be a second
# guard.
#
# On failure it collects diagnostics into .artifacts/, leaves the release in
# place for inspection, and says how to remove it.
#
# Usage:
#   scripts/environment/kubernetes-pod-restart.sh check
#   scripts/environment/kubernetes-pod-restart.sh run --values PATH \
#     --confirm-real-kubernetes [--port N]

# shellcheck source=scripts/environment/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

readonly INFEROPS_EXPERIMENT_REL="deploy/serving/experiments/kubernetes-pod-restart.v1.json"
readonly INFEROPS_EXPERIMENT_MODULE="tools.kubernetes_pod_restart"

# The loopback port the forward is opened on. Not a threshold: a contributor may
# already be running the local composition or another experiment, either of which
# holds a port.
readonly INFEROPS_DEFAULT_FORWARD_PORT="18092"

# How much of each container's log a failure keeps. Also not a threshold.
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
      [ "$#" -ge 2 ] || inferops::fail "--values needs a path. Usage: kubernetes-pod-restart.sh run --values PATH --confirm-real-kubernetes"
      values_file="$2"
      shift 2
      ;;
    --port)
      [ "$#" -ge 2 ] || inferops::fail "--port needs a number."
      case "$2" in
        '' | *[!0-9]*) inferops::fail "--port must be a number, not '$2'." ;;
      esac
      # Zero is the one value every other check below would accept and still be
      # wrong: `kubectl port-forward` reads it as "pick an ephemeral port", this
      # script never parses the port it actually bound, and the run would fail
      # later as an unopened forward rather than here as a bad argument.
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
      inferops::fail "unknown argument '$1'. Usage: kubernetes-pod-restart.sh check|run [--values PATH] [--port N] [--confirm-real-kubernetes]"
      ;;
  esac
done

[ -n "${action}" ] ||
  inferops::fail "expected one of check, run. Usage: kubernetes-pod-restart.sh check|run [--values PATH] [--port N] [--confirm-real-kubernetes]"

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
  inferops::fail "run needs --confirm-real-kubernetes. It applies the Terraform prerequisites, installs a release, loads a real model, deletes a running pod, and sends real inference requests. Usage: kubernetes-pod-restart.sh run --values PATH --confirm-real-kubernetes"

[ -n "${values_file}" ] ||
  inferops::fail "--values is required. The chart's shipped defaults select no serving profile and are refused on purpose. See docs/serving/kubernetes-pod-restart-persistence.md."

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

inferops::section "Experiment descriptor"
(cd "${INFEROPS_ROOT}" && python -m "${INFEROPS_EXPERIMENT_MODULE}" check)

read_descriptor() {
  inferops::python -c '
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

# The descriptor's entry for the provider that was actually verified, read as a
# lookup rather than as a path: the descriptor describes every provider this
# experiment supports, and a run is recorded against the one it is on.
read_provider_target() {
  inferops::python -c '
import json, sys
from pathlib import Path

record = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
wanted = sys.argv[2]
for provider in record["cluster"]["providers"]:
    if provider["providerId"] == wanted:
        print(provider["name"])
        print(provider["context"])
        break
else:
    raise SystemExit(
        f"the experiment descriptor does not describe provider {wanted!r}"
    )
' "$(inferops::native_path "${experiment_file}")" "$1"
}

if ! provider_target="$(read_provider_target "${INFEROPS_TARGET_PROVIDER}")"; then
  inferops::fail "refusing: this experiment's descriptor does not describe provider '${INFEROPS_TARGET_PROVIDER}'. Nothing was installed."
fi
{
  read -r descriptor_cluster
  read -r descriptor_context
} <<<"${provider_target}"

# Read into a variable first and check the status, rather than through a process
# substitution: a reader whose producer failed sees empty fields and no error,
# and an empty budget below becomes an arithmetic expression rather than a
# refusal.
if ! descriptor_fields="$(read_descriptor \
  release.name release.namespace release.apiServiceName release.apiServicePort \
  release.apiDeploymentName release.runtimeDeploymentName release.configMapName \
  release.runtimeComponent release.acquisitionComponent \
  modelCache.claimName modelCache.verificationInitContainer \
  readiness.installBudgetMs readiness.runtimeRolloutBudgetMs \
  readiness.apiRolloutBudgetMs readiness.releaseTestBudgetMs \
  readiness.forwardBudgetMs \
  readiness.replacementBudgetMs readiness.uninstallBudgetMs \
  observation.pollIntervalMs request.host request.readinessPath \
  evidence.lifecycleFile evidence.readinessFile evidence.cleanupFile)"; then
  inferops::fail "the experiment descriptor could not be read after it validated. Nothing was installed."
fi

{
  read -r descriptor_release
  read -r descriptor_namespace
  read -r descriptor_api_service
  read -r descriptor_api_port
  read -r descriptor_api_deployment
  read -r descriptor_runtime_deployment
  read -r descriptor_configmap
  read -r descriptor_runtime_component
  read -r descriptor_acquisition_component
  read -r descriptor_claim
  read -r descriptor_init_container
  read -r install_budget_ms
  read -r runtime_rollout_budget_ms
  read -r api_rollout_budget_ms
  read -r release_test_budget_ms
  read -r forward_budget_ms
  read -r replacement_budget_ms
  read -r uninstall_budget_ms
  read -r poll_interval_ms
  read -r descriptor_host
  read -r readiness_path
  read -r lifecycle_rel
  read -r readiness_rel
  read -r cleanup_rel
} <<<"${descriptor_fields}"

for field in descriptor_release descriptor_namespace descriptor_api_service \
  descriptor_api_port descriptor_api_deployment descriptor_runtime_deployment \
  descriptor_configmap descriptor_runtime_component \
  descriptor_acquisition_component descriptor_claim descriptor_init_container \
  install_budget_ms runtime_rollout_budget_ms api_rollout_budget_ms \
  release_test_budget_ms forward_budget_ms \
  replacement_budget_ms uninstall_budget_ms poll_interval_ms descriptor_host \
  readiness_path lifecycle_rel readiness_rel cleanup_rel; do
  [ -n "${!field}" ] ||
    inferops::fail "the experiment descriptor left '${field}' empty. Nothing was installed."
done

# Every value that reaches shell arithmetic or a timeout is held to being a
# number here, at the point of use. The Python validator already refuses a
# non-integer, but that is a different file: a guard whose correctness depends on
# the order two programs run in is a guard waiting to be reordered.
for number in descriptor_api_port install_budget_ms runtime_rollout_budget_ms \
  api_rollout_budget_ms release_test_budget_ms forward_budget_ms \
  replacement_budget_ms uninstall_budget_ms poll_interval_ms; do
  case "${!number}" in
    '' | *[!0-9]*)
      inferops::fail "the experiment descriptor's '${number}' is not a number. Nothing was installed."
      ;;
  esac
done

# A floor as well as a shape, for the value that reaches `sleep` after an integer
# division. Below a thousand milliseconds that division is zero and the readiness
# sampler becomes a busy poll against the API server.
[ "${poll_interval_ms}" -ge 1000 ] ||
  inferops::fail "the experiment descriptor samples readiness every ${poll_interval_ms} ms. Below 1000 ms the wait between samples truncates to zero and this loop would spin against the API server. Nothing was installed."

# The names that reach a label selector and a jsonpath filter are held to the
# shape of a Kubernetes name here, where they are about to be used.
for name in descriptor_runtime_component descriptor_acquisition_component \
  descriptor_init_container; do
  case "${!name}" in
    [a-z0-9]*[a-z0-9] | [a-z0-9]) ;;
    *) inferops::fail "the descriptor's '${name}' is '${!name}', which is not a DNS-1123 label. Nothing was installed." ;;
  esac
  case "${!name}" in
    *[!a-z0-9-]*) inferops::fail "the descriptor's '${name}' is '${!name}', which contains a character a DNS-1123 label may not. Nothing was installed." ;;
  esac
done

# The address the forward binds. The descriptor supplies it, the descriptor is a
# committed file, and neither of those makes it loopback -- so it is checked
# here, where it is about to be handed to `kubectl port-forward --address`. The
# API this forwards to carries no authentication and no authorization; binding it
# to anything but loopback would publish an unauthenticated LLM endpoint on every
# interface of the host, and every other guard in this file would still pass.
case "${descriptor_host}" in
  127.0.0.1 | ::1) ;;
  *) inferops::fail "the descriptor's request host is '${descriptor_host}'. This forward binds loopback only, because the API behind it is unauthenticated. Nothing was installed." ;;
esac

# Four records name one target, and they are compared rather than assumed. The
# first two compare the descriptor's entry for the selected provider against the
# target inferops::resolve_target just verified.
[ "${descriptor_cluster}" = "${INFEROPS_TARGET_CLUSTER_NAME}" ] ||
  inferops::fail "for provider '${INFEROPS_TARGET_PROVIDER}' the descriptor names cluster '${descriptor_cluster}' and the verified target is '${INFEROPS_TARGET_CLUSTER_NAME}'."
[ "${descriptor_context}" = "${INFEROPS_TARGET_CONTEXT}" ] ||
  inferops::fail "for provider '${INFEROPS_TARGET_PROVIDER}' the descriptor names context '${descriptor_context}' and the verified target is '${INFEROPS_TARGET_CONTEXT}'."
[ "${descriptor_release}" = "${INFEROPS_RELEASE_NAME}" ] ||
  inferops::fail "the descriptor names release '${descriptor_release}' and these scripts operate '${INFEROPS_RELEASE_NAME}'."
[ "${descriptor_namespace}" = "${INFEROPS_RELEASE_NAMESPACE}" ] ||
  inferops::fail "the descriptor names namespace '${descriptor_namespace}' and these scripts operate '${INFEROPS_RELEASE_NAMESPACE}'."

# Not input validation: the namespace is a readonly constant in lib.sh and
# nothing here can change it. It is here for the edit that changes that constant
# -- ADR 0001 (D5) makes the prefix the isolation rule.
case "${INFEROPS_RELEASE_NAMESPACE}" in
  inferops-*) ;;
  *) inferops::fail "the release namespace must be prefixed 'inferops-' (ADR 0001 D5). It is '${INFEROPS_RELEASE_NAMESPACE}', which means the constant in lib.sh was changed without this rule being reconsidered." ;;
esac

chart_dir="${INFEROPS_ROOT}/${INFEROPS_CHART_PATH}"
[ -d "${chart_dir}" ] || inferops::fail "no chart at ${INFEROPS_CHART_PATH}"

chart_path="$(inferops::native_path "${chart_dir}")"
values_path="$(inferops::native_path "$(cd "$(dirname "${values_file}")" && pwd)/$(basename "${values_file}")")"

diag_dir="${INFEROPS_ARTIFACT_DIR}/kubernetes-pod-restart"
lifecycle_file="${INFEROPS_ROOT}/${lifecycle_rel}"
readiness_file="${INFEROPS_ROOT}/${readiness_rel}"
cleanup_file="${INFEROPS_ROOT}/${cleanup_rel}"
# Appended to, not truncated: this workflow opens a forward twice -- once for
# the baseline completion and once after the replacement -- and a failure in
# the second one used to erase the first one's output.
forward_log="${diag_dir}/forward.log"

base_url="http://${descriptor_host}:${forward_port}"

forward_pid=""

# Wall-clock milliseconds. Over the minutes this experiment spans the record
# carries only differences, never a timestamp.
now_ms() { printf '%s' "$(($(date +%s%N) / 1000000))"; }

# --- diagnostics and teardown ------------------------------------------------

collect_diagnostics() {
  mkdir -p "${diag_dir}"
  inferops::warn "collecting diagnostics into .artifacts/kubernetes-pod-restart/"
  inferops::target_helm list --namespace "${INFEROPS_RELEASE_NAMESPACE}" >"${diag_dir}/releases.txt" 2>&1 || true
  inferops::target_helm history "${INFEROPS_RELEASE_NAME}" \
    --namespace "${INFEROPS_RELEASE_NAMESPACE}" >"${diag_dir}/history.txt" 2>&1 || true
  inferops::target_kubectl get all,configmap,serviceaccount,pvc,job \
    -n "${INFEROPS_RELEASE_NAMESPACE}" -o wide >"${diag_dir}/get-all.txt" 2>&1 || true
  inferops::target_kubectl describe pods -n "${INFEROPS_RELEASE_NAMESPACE}" >"${diag_dir}/describe-pods.txt" 2>&1 || true
  inferops::target_kubectl get events -n "${INFEROPS_RELEASE_NAMESPACE}" \
    --sort-by=.lastTimestamp >"${diag_dir}/events.txt" 2>&1 || true
  inferops::target_kubectl logs -n "${INFEROPS_RELEASE_NAMESPACE}" \
    -l "${INFEROPS_RELEASE_SELECTOR}" --all-containers --tail="${INFEROPS_LOG_TAIL}" >"${diag_dir}/release.log" 2>&1 || true
}

close_forward() {
  if [ -n "${forward_pid}" ] && kill -0 "${forward_pid}" 2>/dev/null; then
    kill "${forward_pid}" 2>/dev/null || true
    wait "${forward_pid}" 2>/dev/null || true
  fi
  forward_pid=""
}

on_exit() {
  local rc=$?
  close_forward
  if [ "${rc}" -ne 0 ]; then
    collect_diagnostics
    inferops::warn "the release was left in place for inspection. Remove it with: helm uninstall ${INFEROPS_RELEASE_NAME} --namespace ${INFEROPS_RELEASE_NAMESPACE}"
    inferops::warn "the prerequisites and the model cache claim were not touched and are not removed by that command."
  fi
  exit "${rc}"
}

# INT and TERM as well as EXIT, which is what the other two Kubernetes workflows
# here do: this one leaves a background forward and a real release behind, and on
# Git Bash signal delivery to a native child is less predictable than on Linux.
trap on_exit INT TERM EXIT

mkdir -p "${diag_dir}"

# --- prerequisites -----------------------------------------------------------

inferops::section "Applying the Terraform prerequisites"

bash "${INFEROPS_ROOT}/scripts/environment/terraform-prerequisites.sh" apply

# Asked through a function that separates "the answer is none" from "the question
# could not be asked": a swallowed error would make an unreachable API server
# indistinguishable from an empty namespace.
claim_count() {
  local output
  if ! output="$(inferops::target_kubectl get pvc \
    -n "${INFEROPS_RELEASE_NAMESPACE}" -o name)"; then
    return 1
  fi
  printf '%s' "${output}" | grep -c . || true
}

if ! claims_before="$(claim_count)"; then
  inferops::fail "could not count the persistent volume claims before installing. An unanswered query is not an empty result."
fi
inferops::log "persistent volume claims present before install: ${claims_before}"

if inferops::target_helm status "${INFEROPS_RELEASE_NAME}" \
  --namespace "${INFEROPS_RELEASE_NAMESPACE}" >/dev/null 2>&1; then
  inferops::fail "release '${INFEROPS_RELEASE_NAME}' already exists in '${INFEROPS_RELEASE_NAMESPACE}'. This experiment starts from an install, so an existing release would make its baseline something other than the one it reports. Remove it first: helm uninstall ${INFEROPS_RELEASE_NAME} --namespace ${INFEROPS_RELEASE_NAMESPACE}"
fi

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

# --- the known-good baseline -------------------------------------------------

inferops::section "Installing the known-good release"

# Deliberately without `--wait`, and deliberately without `--create-namespace`:
# the namespace is Terraform's, and Helm creating it would make this release's
# uninstall delete a prerequisite.
inferops::target_helm install "${INFEROPS_RELEASE_NAME}" "${chart_path}" \
  --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
  --values "${values_path}" \
  --timeout "$((install_budget_ms / 1000))s"

inferops::section "Waiting for the serving runtime to load the model"

inferops::target_kubectl rollout status "deployment/${descriptor_runtime_deployment}" \
  -n "${INFEROPS_RELEASE_NAMESPACE}" --timeout="$((runtime_rollout_budget_ms / 1000))s"

inferops::section "Waiting for the platform API"

inferops::target_kubectl rollout status "deployment/${descriptor_api_deployment}" \
  -n "${INFEROPS_RELEASE_NAMESPACE}" --timeout="$((api_rollout_budget_ms / 1000))s"

inferops::section "Running the release's connection test"

# Without `--logs`. The chart deletes a test pod that succeeded, so `--logs`
# then fails fetching logs from a pod that is gone and reports a passing test as
# a failure. scripts/environment/kubernetes-certification.sh states the whole of
# the argument beside its own call.
inferops::target_helm test "${INFEROPS_RELEASE_NAME}" \
  --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
  --timeout "$((release_test_budget_ms / 1000))s"

# --- reading one serving pod, as facts ---------------------------------------

# The name of the one serving runtime pod. This experiment is single-replica by
# the descriptor, and a namespace holding two would make "the pod" ambiguous --
# so it is counted rather than indexed into.
serving_pod_name() {
  local names count
  names="$(inferops::target_kubectl get pods \
    -n "${INFEROPS_RELEASE_NAMESPACE}" \
    -l "${INFEROPS_RELEASE_SELECTOR},app.kubernetes.io/component=${descriptor_runtime_component}" \
    -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}')" || return 1
  count="$(printf '%s' "${names}" | grep -c . || true)"
  [ "${count}" = "1" ] || {
    printf 'expected exactly one %s pod and found %s\n' \
      "${descriptor_runtime_component}" "${count}" >&2
    return 1
  }
  printf '%s' "${names}" | head -1
}

# Everything about one pod that this experiment compares across the replacement.
# The Kubernetes half comes from the API server; the three artifact facts come
# from inside the container, because the claim is what is being asked about and
# the API server has never read it.
#
# The digest is computed rather than assumed. Reading the pinned value out of the
# values file and writing it into both sides of the comparison would compare a
# document with itself.
pod_facts() {
  local pod="$1" json
  json="$(inferops::target_kubectl get pod "${pod}" \
    -n "${INFEROPS_RELEASE_NAMESPACE}" -o json)" || return 1

  local artifact_line
  # `sh -c` rather than three execs: one round trip, and the three values are
  # read from the same file at the same instant.
  artifact_line="$(inferops::target_kubectl exec -n "${INFEROPS_RELEASE_NAMESPACE}" \
    "${pod}" -c runtime -- sh -c '
set -eu
artifact="$(find /models -maxdepth 1 -type f -name "*.gguf" | head -1)"
[ -n "$artifact" ] || { echo "no artifact under /models" >&2; exit 1; }
printf "%s %s %s " "$artifact" "$(stat -c %s "$artifact")" "$(stat -c %i "$artifact")"
printf "%s " "$(stat -c %Y "$artifact")"
sha256sum "$artifact" | cut -d" " -f1
')" || return 1

  INFEROPS_POD_JSON="${json}" \
    INFEROPS_ARTIFACT_LINE="${artifact_line}" \
    INFEROPS_CLAIM="${descriptor_claim}" \
    INFEROPS_INIT_CONTAINER="${descriptor_init_container}" \
    inferops::python -c '
import json, os

pod = json.loads(os.environ["INFEROPS_POD_JSON"])
claim_name = os.environ["INFEROPS_CLAIM"]
init_name = os.environ["INFEROPS_INIT_CONTAINER"]
path, size, inode, mtime, digest = os.environ["INFEROPS_ARTIFACT_LINE"].split()

owner = (pod["metadata"].get("ownerReferences") or [{}])[0]

# The claim, and whether the serving container mounts it read only. Read off the
# container that serves rather than off the pod spec as a whole: the acquisition
# hook mounts the same claim writable by design, and a check that looked at any
# mount would find that one and report the wrong answer for this one.
volume = next(
    (
        entry
        for entry in pod["spec"].get("volumes", [])
        if entry.get("persistentVolumeClaim", {}).get("claimName") == claim_name
    ),
    None,
)
mount = None
if volume is not None:
    for container in pod["spec"].get("containers", []):
        if container.get("name") != "runtime":
            continue
        for candidate in container.get("volumeMounts", []):
            if candidate.get("name") == volume["name"]:
                mount = candidate

init_state = next(
    (
        entry
        for entry in pod["status"].get("initContainerStatuses", [])
        if entry.get("name") == init_name
    ),
    {},
)
terminated = (init_state.get("state") or {}).get("terminated") or {}
if not terminated:
    terminated = (init_state.get("lastState") or {}).get("terminated") or {}

ready = any(
    condition.get("type") == "Ready" and condition.get("status") == "True"
    for condition in pod["status"].get("conditions", [])
)

print(
    json.dumps(
        {
            "name": pod["metadata"]["name"],
            "uid": pod["metadata"]["uid"],
            "ownerKind": owner.get("kind", ""),
            "ownerName": owner.get("name", ""),
            "nodeName": pod["spec"].get("nodeName", ""),
            # What the pod carries, not what the descriptor says. Echoing the
            # descriptor back would make the comparison in
            # tools/kubernetes_pod_restart compare a document with itself.
            "claimName": (
                volume["persistentVolumeClaim"]["claimName"]
                if volume is not None
                else ""
            ),
            "claimReadOnly": bool(mount and mount.get("readOnly") is True),
            "boundVolumeName": volume["name"] if volume is not None else "",
            "initContainer": init_state.get("name", ""),
            "initExitCode": int(terminated.get("exitCode", -1)),
            "initFinished": bool(terminated),
            "artifactPath": path,
            "artifactSubPath": (mount or {}).get("subPath", ""),
            "artifactSizeBytes": int(size),
            "artifactSha256": "sha256:" + digest,
            "artifactInode": inode,
            "artifactMtimeEpoch": int(mtime),
            "ready": ready,
        }
    )
)
'
}

acquisition_job_count() {
  local output
  if ! output="$(inferops::target_kubectl get jobs \
    -n "${INFEROPS_RELEASE_NAMESPACE}" \
    -l "app.kubernetes.io/component=${descriptor_acquisition_component}" \
    -o name)"; then
    return 1
  fi
  printf '%s' "${output}" | grep -c . || true
}

acquisition_job_uid() {
  inferops::target_kubectl get jobs \
    -n "${INFEROPS_RELEASE_NAMESPACE}" \
    -l "app.kubernetes.io/component=${descriptor_acquisition_component}" \
    -o jsonpath='{.items[*].metadata.uid}' 2>/dev/null || true
}

release_revision() {
  inferops::target_helm list --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
    --filter "^${INFEROPS_RELEASE_NAME}\$" -o json |
    inferops::python -c '
import json, sys

releases = json.load(sys.stdin)
print(releases[0]["revision"] if releases else 0)
'
}

inferops::section "Reading the baseline pod"

baseline_pod="$(require_query "the serving runtime pod before the deletion" serving_pod_name)"
before_json="$(require_query "the baseline pod's facts" pod_facts "${baseline_pod}")"
inferops::log "baseline serving pod: ${baseline_pod}"

if ! jobs_before="$(acquisition_job_count)"; then
  inferops::fail "could not count the acquisition jobs before the deletion. An unanswered query is not an empty result, and the assertion that no hook ran depends on the difference."
fi
job_uid_before="$(acquisition_job_uid)"
revision_before="$(require_query "the release revision before the deletion" release_revision)"

# The hook's own output, when Helm has left it to be read. A successful hook is
# deleted by its `hook-succeeded` delete policy the moment it succeeds, so this
# is usually empty -- and it is an observation rather than an assertion for
# exactly that reason. What carries the weight is the inode and the modification
# time either side of the replacement, which no deletion policy can remove.
acquisition_log="$(inferops::target_kubectl logs -n "${INFEROPS_RELEASE_NAMESPACE}" \
  -l "app.kubernetes.io/component=${descriptor_acquisition_component}" \
  --tail=20 2>/dev/null || true)"

# --- the forward, and one real completion before anything is deleted ---------

open_forward() {
  inferops::target_kubectl port-forward "service/${descriptor_api_service}" \
    "${forward_port}:${descriptor_api_port}" \
    -n "${INFEROPS_RELEASE_NAMESPACE}" --address "${descriptor_host}" >>"${forward_log}" 2>&1 &
  forward_pid="$!"

  local deadline=$((SECONDS + forward_budget_ms / 1000))
  while [ "${SECONDS}" -lt "${deadline}" ]; do
    if ! kill -0 "${forward_pid}" 2>/dev/null; then
      inferops::fail "the port-forward exited before it accepted a connection. Its output is in .artifacts/kubernetes-pod-restart/forward.log."
    fi
    if python -c '
import socket, sys

try:
    socket.create_connection((sys.argv[1], int(sys.argv[2])), 2).close()
except OSError:
    sys.exit(1)
' "${descriptor_host}" "${forward_port}" 2>/dev/null; then
      inferops::log "forward open on ${base_url} (readiness path ${readiness_path})."
      return 0
    fi
    sleep 1
  done
  inferops::fail "the forward to '${descriptor_api_service}' did not accept a connection within $((forward_budget_ms / 1000)) s."
}

# The lifecycle facts are written twice: once now, so that the baseline probe can
# read the model identifier the cluster reports rather than be told one, and once
# after the replacement with everything else. The second write is the record's.
write_lifecycle_facts() {
  local after_json="$1" jobs_after="$2" job_uid_after="$3" revision_after="$4"
  local deleted_epoch_ms="$5" scheduled_ms="$6" ready_ms="$7"
  local claim_after_json="$8"

  mkdir -p "$(dirname "${lifecycle_file}")"
  INFEROPS_PROVIDER_FACT="${INFEROPS_TARGET_PROVIDER}" \
    INFEROPS_CLUSTER_NAME_FACT="${INFEROPS_TARGET_CLUSTER_NAME}" \
    INFEROPS_CONTEXT="${INFEROPS_TARGET_CONTEXT}" \
    INFEROPS_SERVER_VERSION="${server_version}" \
    INFEROPS_NODE_DIGEST="${node_digest}" \
    INFEROPS_HELM="${helm_version}" \
    INFEROPS_KUBECTL="${kubectl_version}" \
    INFEROPS_RELEASE_NAME_FACT="${INFEROPS_RELEASE_NAME}" \
    INFEROPS_NAMESPACE_FACT="${INFEROPS_RELEASE_NAMESPACE}" \
    INFEROPS_RELEASE_JSON="${release_json}" \
    INFEROPS_CONFIGMAP_JSON="${configured}" \
    INFEROPS_CLAIM_JSON="${claim_json}" \
    INFEROPS_CLAIM_AFTER_JSON="${claim_after_json}" \
    INFEROPS_BEFORE_JSON="${before_json}" \
    INFEROPS_AFTER_JSON="${after_json}" \
    INFEROPS_JOBS_BEFORE="${jobs_before}" \
    INFEROPS_JOBS_AFTER="${jobs_after}" \
    INFEROPS_JOB_UID_BEFORE="${job_uid_before}" \
    INFEROPS_JOB_UID_AFTER="${job_uid_after}" \
    INFEROPS_ACQUISITION_LOG="${acquisition_log}" \
    INFEROPS_REVISION_BEFORE="${revision_before}" \
    INFEROPS_REVISION_AFTER="${revision_after}" \
    INFEROPS_DELETED_EPOCH_MS="${deleted_epoch_ms}" \
    INFEROPS_SCHEDULED_MS="${scheduled_ms}" \
    INFEROPS_READY_MS="${ready_ms}" \
    python - "$(inferops::native_path "${lifecycle_file}")" <<'LIFECYCLE_PYTHON'
import json
import os
import sys
from pathlib import Path


def fact(name: str) -> str:
    return os.environ.get(f"INFEROPS_{name}", "")


def number(name: str) -> int:
    value = fact(name).strip()
    return int(value) if value.lstrip("-").isdigit() else 0


release = json.loads(fact("RELEASE_JSON") or "[]") or [{}]
data = json.loads(fact("CONFIGMAP_JSON") or "{}").get("data", {})
claim = json.loads(fact("CLAIM_JSON") or "{}")
claim_after = json.loads(fact("CLAIM_AFTER_JSON") or "{}")

document = {
    "cluster": {
        "provider": fact("PROVIDER_FACT"),
        "name": fact("CLUSTER_NAME_FACT"),
        "context": fact("CONTEXT"),
        "serverVersion": fact("SERVER_VERSION"),
        "nodeImageDigest": fact("NODE_DIGEST"),
    },
    "tooling": {"helm": fact("HELM"), "kubectl": fact("KUBECTL")},
    "release": {
        "name": fact("RELEASE_NAME_FACT"),
        "namespace": fact("NAMESPACE_FACT"),
        "chart": release[0].get("chart", ""),
        "profile": data.get("INFEROPS_SERVING_ADAPTER", ""),
        "revisionBefore": number("REVISION_BEFORE"),
        "revisionAfter": number("REVISION_AFTER"),
    },
    "configuration": {
        "modelIdentifier": data.get("INFEROPS_MODEL_IDENTIFIER", ""),
        "modelRevision": data.get("INFEROPS_MODEL_REVISION", ""),
    },
    "claim": {
        "uid": claim.get("metadata", {}).get("uid", ""),
        "boundVolumeBefore": claim.get("spec", {}).get("volumeName", ""),
        "boundVolumeAfter": claim_after.get("spec", {}).get("volumeName", ""),
    },
    "before": json.loads(fact("BEFORE_JSON") or "{}"),
    "after": json.loads(fact("AFTER_JSON") or "{}"),
    "acquisition": {
        "jobCountBefore": number("JOBS_BEFORE"),
        "jobCountAfter": number("JOBS_AFTER"),
        "jobUidBefore": fact("JOB_UID_BEFORE"),
        "jobUidAfter": fact("JOB_UID_AFTER"),
        "installLog": fact("ACQUISITION_LOG"),
    },
    # deletedAtMs is the origin every other offset is measured from, so it is
    # zero by construction. deletedAtEpochMs is the same instant in absolute
    # terms, and it is here because the recovery is stamped by
    # tools/kubernetes_pod_restart at the moment a completion comes back rather
    # than here at the moment a port-forward opens -- which is a different and
    # shorter interval, and was published as the longer one until V1-S3-011-PR2
    # was reviewed.
    "timings": {
        "deletedAtMs": 0,
        "deletedAtEpochMs": number("DELETED_EPOCH_MS"),
        "replacementScheduledAtMs": number("SCHEDULED_MS"),
        "replacementReadyAtMs": number("READY_MS"),
        "recoveredAtMs": 0,
    },
}

Path(sys.argv[1]).write_text(
    json.dumps(document, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
    newline="\n",
)
LIFECYCLE_PYTHON
}

inferops::section "Collecting cluster facts"

kube_versions() {
  inferops::target_kubectl version -o json 2>/dev/null | inferops::python -c '
import json, sys

document = json.load(sys.stdin)
print(document.get("clientVersion", {}).get("gitVersion", ""))
print(document.get("serverVersion", {}).get("gitVersion", ""))
'
}

if ! kube_version_lines="$(kube_versions)"; then
  inferops::fail "could not establish the kubectl and API server versions. A record names the environment it ran in."
fi
{
  read -r kubectl_version
  read -r server_version
} <<<"${kube_version_lines}"

[ -n "${kubectl_version}" ] && [ -n "${server_version}" ] ||
  inferops::fail "the kubectl or API server version came back empty. A record names the environment it ran in."

helm_version="$(require_query "the helm version" inferops::target_helm version --short)"

# The verified target's own node image digest, collected once by
# inferops::resolve_target. Recorded for every provider; enforced as a pin only
# where the descriptor says InferOps chose the image, which it does not for
# docker-desktop.
node_digest="${INFEROPS_TARGET_NODE_IMAGE_DIGEST}"
[ -n "${node_digest}" ] ||
  inferops::fail "the target node's image digest could not be established. A record names the cluster it ran on."

# By name, not by selector. The release carries three ConfigMaps -- the runtime
# configuration, the telemetry scrape configuration, and the collector's -- and
# the first one a selector returns is the collector's, which carries none of the
# fields read below. The upgrade/rollback experiment was written when there was
# one and lost a whole successful run to that assumption.
configured="$(require_query "the release's rendered configuration" \
  inferops::target_kubectl get configmap "${descriptor_configmap}" \
  -n "${INFEROPS_RELEASE_NAMESPACE}" -o json)"
release_json="$(require_query "the release's own status" \
  inferops::target_helm list --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
  --filter "^${INFEROPS_RELEASE_NAME}\$" -o json)"
# Read twice: once now, and once after the replacement. The claim's bound
# PersistentVolume is what "the same storage came back" means, and a single read
# could only ever report the binding from one side of the event.
read_claim() {
  inferops::target_kubectl get pvc "${descriptor_claim}" \
    -n "${INFEROPS_RELEASE_NAMESPACE}" -o json
}

claim_json="$(require_query "the model cache claim" read_claim)"

# Written once with the baseline in place, so the probe below reads the model
# identifier out of the cluster rather than out of an argument. The deletion has
# not happened yet, so its epoch is this moment; nothing reads the timings until
# the second write replaces them.
write_lifecycle_facts "${before_json}" "${jobs_before}" "${job_uid_before}" \
  "${revision_before}" "$(now_ms)" 0 0 "${claim_json}"

inferops::section "One real completion before anything is deleted"

open_forward

(cd "${INFEROPS_ROOT}" && python -m "${INFEROPS_EXPERIMENT_MODULE}" probe \
  --confirm-real-kubernetes \
  --base-url "${base_url}")

# The forward is closed across the deletion and reopened afterwards. It is bound
# to the API pod the Service selected when it opened, and the API is not what
# this experiment deletes -- but a forward held open across a serving outage is
# a connection whose behaviour this record would then have to explain, and it
# does not measure the outage from a caller's side and does not claim to.
close_forward

# --- the deletion ------------------------------------------------------------

inferops::section "Deleting one serving runtime pod"

inferops::log "deleting pod '${baseline_pod}'. This changes no Deployment, no claim, and no release revision: the Deployment controller creates the replacement."

deleted_at_ms="$(now_ms)"
# The same instant, absolutely. Every other figure is an offset from the
# relative origin; this one exists so the Python can stamp the recovery from
# its own completion rather than from anything this script observes.
deleted_at_epoch_ms="${deleted_at_ms}"
# `--wait=false` on purpose: the clock above starts at the request, and the
# replacement is watched below rather than waited for here. No `--timeout` goes
# with it, because `--timeout` only means something while kubectl is waiting --
# one was passed until V1-S3-011-PR2's review pointed out that it bounded
# nothing.
inferops::target_kubectl delete pod "${baseline_pod}" \
  -n "${INFEROPS_RELEASE_NAMESPACE}" --wait=false

# --- watching the replacement ------------------------------------------------

inferops::section "Watching for the replacement"

# Readiness is sampled from the Deployment rather than from a caller: the
# question is whether the serving Deployment noticed, and a caller's view would
# additionally describe the forward, the Service, and the API in front of it.
#
# The first sample is taken immediately, before any wait, because the interesting
# one is the one where readiness has already dropped and the replacement has not
# yet arrived.
readiness_samples="[]"
replacement_pod=""
scheduled_at_ms=0
ready_at_ms=0
replacement_deadline=$((SECONDS + replacement_budget_ms / 1000))

while :; do
  sample_at=$(($(now_ms) - deleted_at_ms))
  ready_replicas="$(inferops::target_kubectl get deployment "${descriptor_runtime_deployment}" \
    -n "${INFEROPS_RELEASE_NAMESPACE}" \
    -o jsonpath='{.status.readyReplicas}' 2>/dev/null || true)"
  [ -n "${ready_replicas}" ] || ready_replicas=0

  # The replacement, by exclusion: every serving-runtime pod that is not the one
  # that was deleted. A terminating pod keeps its name until it is gone, so this
  # is the only way to name the new one without guessing.
  current_pod="$(inferops::target_kubectl get pods \
    -n "${INFEROPS_RELEASE_NAMESPACE}" \
    -l "${INFEROPS_RELEASE_SELECTOR},app.kubernetes.io/component=${descriptor_runtime_component}" \
    -o jsonpath='{range .items[*]}{.metadata.name}{"\n"}{end}' 2>/dev/null |
    grep -v "^${baseline_pod}\$" | head -1 || true)"

  # And its own readiness, read off that pod rather than off the Deployment.
  #
  # An earlier version broke the loop on the Deployment's `.status.readyReplicas`
  # while its comment claimed it was reading the replacement's, and the two are
  # not the same: `readyReplicas` is an aggregate that still counts the deleted
  # pod for as long as it is Ready inside its termination grace period. The loop
  # could therefore end at "a replacement object exists" AND "the *old* pod is
  # still ready", and the figure it stamped would have measured nothing. The
  # aggregate is still sampled below -- it is the right signal for "did the
  # Deployment notice" -- but it no longer decides when to stop.
  current_pod_ready=false
  if [ -n "${current_pod}" ]; then
    if [ "$(inferops::target_kubectl get pod "${current_pod}" \
      -n "${INFEROPS_RELEASE_NAMESPACE}" \
      -o 'jsonpath={.status.conditions[?(@.type=="Ready")].status}' \
      2>/dev/null || true)" = "True" ]; then
      current_pod_ready=true
    fi
  fi

  readiness_samples="$(INFEROPS_SAMPLES="${readiness_samples}" \
    INFEROPS_AT_MS="${sample_at}" \
    INFEROPS_READY="${ready_replicas}" \
    INFEROPS_POD="${current_pod}" \
    inferops::python -c '
import json, os

samples = json.loads(os.environ["INFEROPS_SAMPLES"])
samples.append(
    {
        "atMs": int(os.environ["INFEROPS_AT_MS"]),
        "readyReplicas": int(os.environ["INFEROPS_READY"]),
        "podName": os.environ["INFEROPS_POD"],
    }
)
print(json.dumps(samples))
')"

  if [ -n "${current_pod}" ] && [ "${scheduled_at_ms}" -eq 0 ]; then
    scheduled_at_ms=$(($(now_ms) - deleted_at_ms))
    replacement_pod="${current_pod}"
    inferops::log "a replacement pod exists: ${replacement_pod}"
  fi

  if [ -n "${replacement_pod}" ] && [ "${current_pod_ready}" = "true" ]; then
    ready_at_ms=$(($(now_ms) - deleted_at_ms))
    inferops::log "the replacement became ready ${ready_at_ms} ms after the deletion."
    break
  fi

  if [ "${SECONDS}" -ge "${replacement_deadline}" ]; then
    inferops::fail "no ready replacement pod within the ${replacement_budget_ms} ms this experiment allows it."
  fi
  sleep "$((poll_interval_ms / 1000))"
done

mkdir -p "$(dirname "${readiness_file}")"
INFEROPS_SAMPLES="${readiness_samples}" \
  python - "$(inferops::native_path "${readiness_file}")" <<'READINESS_PYTHON'
import json
import os
import sys
from pathlib import Path

Path(sys.argv[1]).write_text(
    json.dumps({"samples": json.loads(os.environ["INFEROPS_SAMPLES"])}, indent=2)
    + "\n",
    encoding="utf-8",
    newline="\n",
)
READINESS_PYTHON

# The Deployment's own wait as well as the sampled one. The sampler establishes
# that readiness left true and came back; this establishes that the controller
# considers the rollout complete, which is a different statement.
inferops::target_kubectl rollout status "deployment/${descriptor_runtime_deployment}" \
  -n "${INFEROPS_RELEASE_NAMESPACE}" --timeout="$((runtime_rollout_budget_ms / 1000))s"

inferops::section "Reading the replacement pod"

# Asked until the deleted pod has gone, not once. `rollout status` returns when
# the Deployment reports its replicas ready, which can be true while the pod that
# was deleted is still terminating -- and `serving_pod_name` refuses unless
# exactly one pod matches. A complete, successful run would then abort here with
# "expected exactly one serving-runtime pod and found 2". This is the same
# garbage-collector race the residue checks already wait out, in the one place it
# had not been applied.
settle_deadline=$((SECONDS + replacement_budget_ms / 1000))
while :; do
  if after_pod="$(serving_pod_name 2>/dev/null)" && [ -n "${after_pod}" ]; then
    break
  fi
  if [ "${SECONDS}" -ge "${settle_deadline}" ]; then
    after_pod="$(require_query "the serving runtime pod after the replacement" serving_pod_name)"
    break
  fi
  sleep 2
done
[ "${after_pod}" != "${baseline_pod}" ] ||
  inferops::fail "the pod after the deletion carries the same name as the one that was deleted. Nothing was replaced."
after_json="$(require_query "the replacement pod's facts" pod_facts "${after_pod}")"

if ! jobs_after="$(acquisition_job_count)"; then
  inferops::fail "could not count the acquisition jobs after the replacement. An unanswered query is not an empty result."
fi
job_uid_after="$(acquisition_job_uid)"
revision_after="$(require_query "the release revision after the replacement" release_revision)"

# --- real inference again ----------------------------------------------------

inferops::section "Asking the release for a completion again"

open_forward

claim_after_json="$(require_query "the model cache claim after the replacement" \
  read_claim)"

# No recovery stamp here. A forward accepting a connection is not a served
# completion, and stamping it as one is the defect this workflow's review
# found: the record published "deletion to a served completion" for an
# interval that ended before the request was sent. The origin goes in; the end
# is stamped by tools/kubernetes_pod_restart, at the moment it has a
# completion in hand.
write_lifecycle_facts "${after_json}" "${jobs_after}" "${job_uid_after}" \
  "${revision_after}" "${deleted_at_epoch_ms}" "${scheduled_at_ms}" \
  "${ready_at_ms}" "${claim_after_json}"

(cd "${INFEROPS_ROOT}" && python -m "${INFEROPS_EXPERIMENT_MODULE}" evaluate \
  --confirm-real-kubernetes \
  --base-url "${base_url}")

close_forward

# --- teardown ----------------------------------------------------------------

inferops::section "Uninstalling the release"

inferops::target_helm uninstall "${INFEROPS_RELEASE_NAME}" \
  --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
  --wait \
  --timeout "$((uninstall_budget_ms / 1000))s"

inferops::section "Residue"

# Asked repeatedly inside the uninstall budget rather than once: `helm uninstall
# --wait` waits for the objects Helm deleted itself, and a Deployment's pods are
# removed afterwards by the garbage collector on the controller manager's
# schedule. Anything still present at that deadline is residue.
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
    break
  fi
  sleep 2
done

release_removed="true"
if inferops::target_helm status "${INFEROPS_RELEASE_NAME}" \
  --namespace "${INFEROPS_RELEASE_NAMESPACE}" >/dev/null 2>&1; then
  release_removed="false"
fi

namespace_present="true"
inferops::target_kubectl get namespace "${INFEROPS_RELEASE_NAMESPACE}" >/dev/null 2>&1 ||
  namespace_present="false"

claim_present="true"
inferops::target_kubectl get pvc "${descriptor_claim}" \
  -n "${INFEROPS_RELEASE_NAMESPACE}" >/dev/null 2>&1 || claim_present="false"

mkdir -p "$(dirname "${cleanup_file}")"
INFEROPS_RELEASE_REMOVED="${release_removed}" \
  INFEROPS_REMAINING="${remaining_count}" \
  INFEROPS_CLAIM_PRESENT="${claim_present}" \
  INFEROPS_NAMESPACE_PRESENT="${namespace_present}" \
  python - "$(inferops::native_path "${cleanup_file}")" <<'CLEANUP_PYTHON'
import json
import os
import sys
from pathlib import Path

Path(sys.argv[1]).write_text(
    json.dumps(
        {
            "releaseRemoved": os.environ["INFEROPS_RELEASE_REMOVED"] == "true",
            "releaseObjectsRemaining": int(os.environ["INFEROPS_REMAINING"]),
            "claimPresent": os.environ["INFEROPS_CLAIM_PRESENT"] == "true",
            "namespacePresent": os.environ["INFEROPS_NAMESPACE_PRESENT"] == "true",
        },
        indent=2,
        sort_keys=True,
    )
    + "\n",
    encoding="utf-8",
    newline="\n",
)
CLEANUP_PYTHON

(cd "${INFEROPS_ROOT}" && python -m "${INFEROPS_EXPERIMENT_MODULE}" record-cleanup)

if ! claims_after="$(claim_count)"; then
  inferops::fail "could not count the persistent volume claims after uninstalling. An unanswered query is not an empty result."
fi
[ "${claims_after}" = "${claims_before}" ] ||
  inferops::fail "the claim count changed across the release: ${claims_before} before, ${claims_after} after. This chart must neither create nor delete a claim, and the model cache is Terraform's."

inferops::section "Result"
inferops::log "one serving pod was deleted, the Deployment replaced it, the replacement mounted the same Terraform-owned claim, the artifact was still there and still verified, and a real completion came back."
inferops::log "record        .cache/inferops/experiments/kubernetes-pod-restart.json (labelled local real Kubernetes)"
inferops::log "the namespace and the model cache claim survived. Reclaiming them is scripts/environment/terraform-prerequisites.sh destroy --confirm, and nothing here does it for you."
