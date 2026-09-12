#!/usr/bin/env bash
# Certifies the real Kubernetes inference path: prerequisites, release, measured
# model readiness, one real completion through the release's Service, a
# machine-readable record, and a scoped teardown.
#
# This is the answer to "does a real model answer through Kubernetes". Neither a
# render nor a lint nor an install answers it: `helm install` reports a rollout,
# and a rollout that Kubernetes reports as successful, a Service that selects
# nothing, and a runtime that loaded no weights look identical from outside until
# something asks for a completion.
#
# What it operates, and what it does not. It applies the Terraform prerequisite
# layer through scripts/environment/terraform-prerequisites.sh, installs one Helm
# release named by INFEROPS_RELEASE_NAME in INFEROPS_RELEASE_NAMESPACE, opens one
# loopback forward to that release's API Service, and uninstalls the release when
# it is done. It never removes the namespace, never removes the model cache
# claim, and never removes the cluster: those outlive a release by design
# (docs/architecture/resource-ownership.md), and reclaiming the claim is
# `terraform-prerequisites.sh destroy --confirm` and nothing else.
#
# The assertions and the record are not here. They are in
# tools/kubernetes_certification, which reads the committed descriptor, refuses a
# forward that is not loopback, refuses an answer carrying mock identity or mock
# capability metadata, and writes the labelled record. The split is deliberate:
# the guard that establishes which cluster is being acted on already lives in
# lib.sh beside every other script here, and a second implementation of it in
# Python would be a second guard.
#
# Every threshold this script applies comes from the descriptor, with two stated
# exceptions that are host conveniences rather than thresholds: the default
# loopback port, which moves when something else already holds one, and the
# tail length on collected container logs.
#
# On failure it collects diagnostics into .artifacts/, leaves the release in
# place for inspection, and says how to remove it. It does not tear down the
# evidence of its own failure.
#
# Usage:
#   scripts/environment/kubernetes-certification.sh check
#   scripts/environment/kubernetes-certification.sh certify --values PATH \
#     --confirm-real-kubernetes [--port N]

# shellcheck source=scripts/environment/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

# The committed descriptor this workflow reads its own budgets and targets from,
# relative to the repository root. The Python tool refuses the descriptor if any
# budget disagrees with the chart, the runtime package, or the runtime profile.
readonly INFEROPS_CERTIFICATION_REL="deploy/serving/certification/k8s-real-inference.v1.json"

# The loopback port the forward is opened on. Not a threshold: a contributor may
# already be running the local composition, which holds the API's own port.
readonly INFEROPS_DEFAULT_FORWARD_PORT="18090"

# How much of each container's log a failure keeps. Also not a threshold: it
# bounds an artifact, not a decision.
readonly INFEROPS_LOG_TAIL="200"

action=""
values_file=""
confirmed=0
forward_port="${INFEROPS_DEFAULT_FORWARD_PORT}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    check | certify)
      [ -z "${action}" ] ||
        inferops::fail "two actions were given ('${action}' and '$1'). This script performs one at a time, so that its output describes what it did."
      action="$1"
      shift
      ;;
    --values)
      [ "$#" -ge 2 ] || inferops::fail "--values needs a path. Usage: kubernetes-certification.sh certify --values PATH --confirm-real-kubernetes"
      values_file="$2"
      shift 2
      ;;
    --port)
      [ "$#" -ge 2 ] || inferops::fail "--port needs a number."
      case "$2" in
        '' | *[!0-9]*) inferops::fail "--port must be a number, not '$2'." ;;
      esac
      forward_port="$2"
      shift 2
      ;;
    --confirm-real-kubernetes)
      confirmed=1
      shift
      ;;
    *)
      inferops::fail "unknown argument '$1'. Usage: kubernetes-certification.sh check|certify [--values PATH] [--port N] [--confirm-real-kubernetes]"
      ;;
  esac
done

[ -n "${action}" ] ||
  inferops::fail "expected one of check, certify. Usage: kubernetes-certification.sh check|certify [--values PATH] [--port N] [--confirm-real-kubernetes]"

inferops::require_cmd python

certification_file="${INFEROPS_ROOT}/${INFEROPS_CERTIFICATION_REL}"
[ -f "${certification_file}" ] ||
  inferops::fail "no certification descriptor at ${INFEROPS_CERTIFICATION_REL}"

# --- check: reads files, contacts nothing -----------------------------------

if [ "${action}" = "check" ]; then
  inferops::section "Certification descriptor"
  (cd "${INFEROPS_ROOT}" && python -m tools.kubernetes_certification check)
  inferops::log "the descriptor validated. Nothing was contacted and no release was installed."
  exit 0
fi

# --- everything below reaches a cluster and a real model --------------------

[ "${confirmed}" -eq 1 ] ||
  inferops::fail "certify needs --confirm-real-kubernetes. It applies the Terraform prerequisites, installs a release, loads a real model, and sends a real inference request. Usage: kubernetes-certification.sh certify --values PATH --confirm-real-kubernetes"

[ -n "${values_file}" ] ||
  inferops::fail "--values is required. The chart's shipped defaults select no serving profile and are refused on purpose, so there is no values file this script could reasonably assume. See docs/serving/kubernetes-real-inference-certification.md."

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

inferops::section "Certification descriptor"
(cd "${INFEROPS_ROOT}" && python -m tools.kubernetes_certification check)

# The descriptor's own values, read only after the tool above accepted it. A
# field read from a document nothing validated is a threshold with no authority.
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
' "$(inferops::native_path "${certification_file}")" "$@"
}

# The descriptor's entry for the provider that was actually verified. It is read
# separately from the flat fields below because selecting it is a lookup, not a
# path: the descriptor describes every provider this certification supports, and
# a run is certified against the one it is on. A provider the descriptor does
# not describe stops here rather than being certified against somebody else's
# entry.
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
        f"the certification descriptor does not describe provider {wanted!r}"
    )
' "$(inferops::native_path "${certification_file}")" "$1"
}

if ! provider_target="$(read_provider_target "${INFEROPS_TARGET_PROVIDER}")"; then
  inferops::fail "this certification's descriptor does not describe provider '${INFEROPS_TARGET_PROVIDER}'. Nothing was installed."
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
  readiness.installBudgetMs readiness.runtimeRolloutBudgetMs \
  readiness.apiRolloutBudgetMs readiness.releaseTestBudgetMs \
  readiness.forwardBudgetMs readiness.uninstallBudgetMs \
  request.host request.readinessPath evidence.factsFile)"; then
  inferops::fail "the certification descriptor could not be read after it validated. Nothing was installed."
fi

{
  read -r descriptor_release
  read -r descriptor_namespace
  read -r descriptor_api_service
  read -r descriptor_api_port
  read -r descriptor_api_deployment
  read -r descriptor_runtime_deployment
  read -r descriptor_configmap
  read -r install_budget_ms
  read -r runtime_rollout_budget_ms
  read -r api_rollout_budget_ms
  read -r release_test_budget_ms
  read -r forward_budget_ms
  read -r uninstall_budget_ms
  read -r descriptor_host
  read -r readiness_path
  read -r facts_rel
} <<<"${descriptor_fields}"

for field in descriptor_cluster descriptor_context descriptor_release \
  descriptor_namespace descriptor_api_service descriptor_api_port \
  descriptor_api_deployment descriptor_runtime_deployment descriptor_configmap \
  install_budget_ms runtime_rollout_budget_ms api_rollout_budget_ms \
  release_test_budget_ms forward_budget_ms uninstall_budget_ms descriptor_host \
  readiness_path facts_rel; do
  [ -n "${!field}" ] ||
    inferops::fail "the certification descriptor left '${field}' empty. Nothing was installed."
done

# Every value that reaches shell arithmetic or a port argument is held to being
# a number here, at the point of use. The Python validator already refuses a
# non-integer, but that is a different file: a guard whose correctness depends
# on the order two programs run in is a guard waiting to be reordered.
for number in descriptor_api_port install_budget_ms runtime_rollout_budget_ms \
  api_rollout_budget_ms release_test_budget_ms forward_budget_ms \
  uninstall_budget_ms; do
  case "${!number}" in
    '' | *[!0-9]*)
      inferops::fail "the certification descriptor's '${number}' is not a number. Nothing was installed."
      ;;
  esac
done

# Three records name one target, and they are compared rather than assumed.
# lib.sh is what every script here acts through; the descriptor is what the
# record is written from. A run where they disagree would install one release
# and certify another, or describe a cluster it did not act on.
[ "${descriptor_cluster}" = "${INFEROPS_TARGET_CLUSTER_NAME}" ] ||
  inferops::fail "for provider '${INFEROPS_TARGET_PROVIDER}' the descriptor names cluster '${descriptor_cluster}' and the verified target is '${INFEROPS_TARGET_CLUSTER_NAME}'."
[ "${descriptor_context}" = "${INFEROPS_TARGET_CONTEXT}" ] ||
  inferops::fail "for provider '${INFEROPS_TARGET_PROVIDER}' the descriptor names context '${descriptor_context}' and the verified target is '${INFEROPS_TARGET_CONTEXT}'."
[ "${descriptor_release}" = "${INFEROPS_RELEASE_NAME}" ] ||
  inferops::fail "the descriptor names release '${descriptor_release}' and these scripts operate '${INFEROPS_RELEASE_NAME}'."
[ "${descriptor_namespace}" = "${INFEROPS_RELEASE_NAMESPACE}" ] ||
  inferops::fail "the descriptor names namespace '${descriptor_namespace}' and these scripts operate '${INFEROPS_RELEASE_NAMESPACE}'."

chart_dir="${INFEROPS_ROOT}/${INFEROPS_CHART_PATH}"
[ -d "${chart_dir}" ] || inferops::fail "no chart at ${INFEROPS_CHART_PATH}"

chart_path="$(inferops::native_path "${chart_dir}")"
values_path="$(inferops::native_path "$(cd "$(dirname "${values_file}")" && pwd)/$(basename "${values_file}")")"

diag_dir="${INFEROPS_ARTIFACT_DIR}/kubernetes-certification"
facts_file="${INFEROPS_ROOT}/${facts_rel}"
forward_log="${diag_dir}/forward.log"
base_url="http://${descriptor_host}:${forward_port}"
forward_pid=""

# --- bounded measurement ----------------------------------------------------

# Milliseconds since an arbitrary epoch. `date +%s%N` is nanoseconds and is what
# Git Bash, macOS with coreutils, and Linux all provide; the division is done in
# the shell so that no locale-dependent formatting reaches an integer.
now_ms() { printf '%s' "$(($(date +%s%N) / 1000000))"; }

# --- diagnostics and teardown ------------------------------------------------

collect_diagnostics() {
  mkdir -p "${diag_dir}"
  inferops::warn "collecting diagnostics into .artifacts/kubernetes-certification/"
  inferops::target_helm list --namespace "${INFEROPS_RELEASE_NAMESPACE}" >"${diag_dir}/releases.txt" 2>&1 || true
  inferops::target_helm history "${INFEROPS_RELEASE_NAME}" \
    --namespace "${INFEROPS_RELEASE_NAMESPACE}" >"${diag_dir}/history.txt" 2>&1 || true
  inferops::target_kubectl get all,configmap,serviceaccount,pvc,endpointslices \
    -n "${INFEROPS_RELEASE_NAMESPACE}" -o wide >"${diag_dir}/get-all.txt" 2>&1 || true
  inferops::target_kubectl describe pods -n "${INFEROPS_RELEASE_NAMESPACE}" >"${diag_dir}/describe-pods.txt" 2>&1 || true
  inferops::target_kubectl get events -n "${INFEROPS_RELEASE_NAMESPACE}" \
    --sort-by=.lastTimestamp >"${diag_dir}/events.txt" 2>&1 || true
  # Container logs, tail-bounded. The runtime prints its own load progress and
  # the API prints its structured records; both are the first place to look and
  # neither carries a prompt or a completion.
  inferops::target_kubectl logs -n "${INFEROPS_RELEASE_NAMESPACE}" \
    -l "${INFEROPS_RELEASE_SELECTOR}" --all-containers --tail="${INFEROPS_LOG_TAIL}" >"${diag_dir}/release.log" 2>&1 || true
  inferops::target_kubectl top pods -n "${INFEROPS_RELEASE_NAMESPACE}" >"${diag_dir}/top-pods.txt" 2>&1 || true
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
    inferops::warn "the Terraform prerequisites and the cluster were not touched by this failure."
  fi
  exit "${rc}"
}

# INT and TERM as well as EXIT. Bash normally runs an EXIT trap when a signal
# terminates the shell, but this workflow leaves a background forward and a real
# release behind, and on Git Bash signal delivery to a native child is less
# predictable than on Linux. Naming the signals costs nothing and removes the
# need to rely on that.
trap on_exit INT TERM EXIT

# --- refuse to certify over an existing release ------------------------------

if inferops::target_helm status "${INFEROPS_RELEASE_NAME}" \
  --namespace "${INFEROPS_RELEASE_NAMESPACE}" >/dev/null 2>&1; then
  # Upgrading an existing release would make this record mean something other
  # than what it says: it reports on an install of a known-good chart into a
  # freshly provisioned prerequisite layer.
  inferops::fail "release '${INFEROPS_RELEASE_NAME}' already exists in '${INFEROPS_RELEASE_NAMESPACE}'. Remove it first: helm uninstall ${INFEROPS_RELEASE_NAME} --namespace ${INFEROPS_RELEASE_NAMESPACE}"
fi

# --- prerequisites ----------------------------------------------------------

inferops::section "Applying the Terraform prerequisites"

prerequisites_started="$(now_ms)"
bash "${INFEROPS_ROOT}/scripts/environment/terraform-prerequisites.sh" apply
prerequisites_ms=$(($(now_ms) - prerequisites_started))
inferops::log "prerequisites applied in ${prerequisites_ms} ms."

# The claim is Terraform's and must outlive this release. Counted before the
# install so that the count after the uninstall means something.
#
# Asked through a function that separates "the answer is none" from "the question
# could not be asked", because a swallowed error would make an unreachable API
# server indistinguishable from an empty namespace -- and the residue assertion
# would then certify a clean removal on the strength of a question nobody
# answered.
inferops::claim_count() {
  local output
  if ! output="$(inferops::target_kubectl get pvc \
    -n "${INFEROPS_RELEASE_NAMESPACE}" -o name)"; then
    return 1
  fi
  printf '%s' "${output}" | grep -c . || true
}

if ! claims_before="$(inferops::claim_count)"; then
  inferops::fail "could not count the persistent volume claims before installing. An unanswered query is not an empty result, and the assertion that this release left the claim alone depends on the difference."
fi
inferops::log "persistent volume claims present before install: ${claims_before}"

# --- install ----------------------------------------------------------------

inferops::section "Installing the release"

# Deliberately without `--wait`. `--wait` would fold the model load, the API
# start, and the install into one number, and this workflow's whole point is to
# measure model readiness separately from everything else. The rollout waits
# below are the bounded ones, each against the budget the descriptor publishes
# for that component -- and those are the chart's budgets, not the adapter's.
#
# `--create-namespace` is absent and must stay absent: the namespace is
# Terraform's, and Helm creating it would make this release's uninstall delete a
# prerequisite.
install_started="$(now_ms)"
inferops::target_helm install "${INFEROPS_RELEASE_NAME}" "${chart_path}" \
  --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
  --values "${values_path}" \
  --timeout "$((install_budget_ms / 1000))s"
install_ms=$(($(now_ms) - install_started))
inferops::log "helm accepted the install in ${install_ms} ms."

# --- measured model readiness -----------------------------------------------

inferops::section "Waiting for the serving runtime to load the model"

# The long one, and the only one that contains a model load. The budget is the
# chart's own progress deadline for this Deployment, which covers scheduling,
# the image pull, the init container's hash read of a 1.83 GB artifact, and the
# load itself. A timeout here is a failure with a place to look, not a hang.
runtime_started="$(now_ms)"
inferops::target_kubectl rollout status "deployment/${descriptor_runtime_deployment}" \
  -n "${INFEROPS_RELEASE_NAMESPACE}" --timeout="$((runtime_rollout_budget_ms / 1000))s"
runtime_ready_ms=$(($(now_ms) - runtime_started))
inferops::log "the serving runtime became ready in ${runtime_ready_ms} ms."

inferops::section "Waiting for the platform API"

api_started="$(now_ms)"
inferops::target_kubectl rollout status "deployment/${descriptor_api_deployment}" \
  -n "${INFEROPS_RELEASE_NAMESPACE}" --timeout="$((api_rollout_budget_ms / 1000))s"
api_ready_ms=$(($(now_ms) - api_started))
inferops::log "the platform API became ready in ${api_ready_ms} ms."

inferops::target_kubectl get deployments,services,pods,endpointslices \
  -n "${INFEROPS_RELEASE_NAMESPACE}" -l "${INFEROPS_RELEASE_SELECTOR}" -o wide

# --- the release's own in-cluster check --------------------------------------

inferops::section "Running the release's connection test"

# `helm test` runs one pod inside the cluster that asks both Services for their
# health endpoints over cluster DNS. It is the half a host-side forward cannot
# establish: that the Service names resolve, that the Services select something,
# and that what is behind them answers. The completion assertion below is the
# other half, and neither substitutes for the other.
#
# Without `--logs`, and that is not an oversight. The chart deletes a test pod
# that succeeded -- `hook-delete-policy: hook-succeeded`, so that a passing test
# leaves no residue -- and keeps one that failed, because its logs are the only
# record of what did not answer. `helm test --logs` fetches the pod's logs after
# the test completes, by which time Helm has already deleted the pod it is
# asking about, and the command fails with `unable to get pod logs ... not
# found`. A test that passed is then reported as a failed certification.
#
# So the two settings were in direct contradiction and only an execution could
# show it: V1-S3-011 hit it on the first run that got this far. The logs are not
# lost. The failure path is where they are wanted, the pod is still there on
# that path, and collect_diagnostics above reads every pod carrying the release
# selector -- the test pod included.
release_test_started="$(now_ms)"
inferops::target_helm test "${INFEROPS_RELEASE_NAME}" \
  --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
  --timeout "$((release_test_budget_ms / 1000))s"
release_test_ms=$(($(now_ms) - release_test_started))
release_test_passed="true"
inferops::log "the in-cluster connection test passed in ${release_test_ms} ms."

# --- what ran, as facts ------------------------------------------------------

inferops::section "Collecting cluster facts"

# Asked through a function that separates "the answer is empty" from "the
# question could not be asked". A record that silently carried an empty field
# because an API call failed would be a C2 record certifying an environment
# nobody measured.
require_query() {
  local description="$1"
  local value
  shift
  if ! value="$("$@")"; then
    inferops::fail "could not establish ${description}. A certification record names the environment it ran in, and an unanswered query is not a measurement."
  fi
  [ -n "${value}" ] ||
    inferops::fail "${description} came back empty. A certification record names the environment it ran in, and an empty field is not a measurement."
  printf '%s' "${value}"
}

deployment_field() {
  inferops::target_kubectl get "deployment/$1" -n "${INFEROPS_RELEASE_NAMESPACE}" \
    -o "jsonpath=$2"
}

configmap_field() {
  inferops::target_kubectl get "configmap/${descriptor_configmap}" \
    -n "${INFEROPS_RELEASE_NAMESPACE}" -o "jsonpath=$1"
}

# `kubectl version` accepts only `yaml` and `json` for --output; it refuses
# `jsonpath` outright. The version is therefore taken from the JSON document,
# which is also the only form that reports both the client and the server in one
# call.
kube_versions() {
  inferops::target_kubectl version -o json 2>/dev/null | inferops::python -c '
import json, sys

document = json.load(sys.stdin)
print(document.get("clientVersion", {}).get("gitVersion", ""))
print(document.get("serverVersion", {}).get("gitVersion", ""))
'
}

if ! kube_version_lines="$(kube_versions)"; then
  inferops::fail "could not establish the kubectl and API server versions. A certification record names the environment it ran in."
fi
{
  read -r kubectl_version
  read -r server_version
} <<<"${kube_version_lines}"

[ -n "${kubectl_version}" ] && [ -n "${server_version}" ] ||
  inferops::fail "the kubectl or API server version came back empty. A certification record names the environment it ran in."

node_image_digest="${INFEROPS_TARGET_NODE_IMAGE_DIGEST}"
[ -n "${node_image_digest}" ] ||
  inferops::fail "the control-plane node's image digest could not be established. A C2 record names the cluster it ran on by digest, and a node image with no repository digest -- one built or loaded locally -- cannot be named that way."

INFEROPS_FACT_PROVIDER="${INFEROPS_TARGET_PROVIDER}"
INFEROPS_FACT_CLUSTER_NAME="${INFEROPS_TARGET_CLUSTER_NAME}"
INFEROPS_FACT_CONTEXT="${INFEROPS_TARGET_CONTEXT}"
INFEROPS_FACT_SERVER_VERSION="${server_version}"
INFEROPS_FACT_NODE_DIGEST="${node_image_digest}"
INFEROPS_FACT_KUBECTL="${kubectl_version}"
INFEROPS_FACT_HELM="$(require_query "the helm version" inferops::target_helm version --short)"
INFEROPS_FACT_TERRAFORM="$(require_query "the terraform version" \
  terraform version -json)"
INFEROPS_FACT_RELEASE_NAME="${INFEROPS_RELEASE_NAME}"
INFEROPS_FACT_NAMESPACE="${INFEROPS_RELEASE_NAMESPACE}"
INFEROPS_FACT_RELEASE_JSON="$(require_query "the installed release's own metadata" \
  inferops::target_helm list --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
  --filter "^${INFEROPS_RELEASE_NAME}\$" -o json)"
INFEROPS_FACT_PROFILE="$(require_query "the rendered serving profile" \
  configmap_field '{.metadata.labels.inferops\.io/profile}')"
INFEROPS_FACT_SERVICE_VERSION="$(configmap_field '{.data.INFEROPS_SERVICE_VERSION}' || true)"
INFEROPS_FACT_MODEL_IDENTIFIER="$(require_query "the configured model identifier" \
  configmap_field '{.data.INFEROPS_MODEL_IDENTIFIER}')"
INFEROPS_FACT_MODEL_REVISION="$(require_query "the configured model revision" \
  configmap_field '{.data.INFEROPS_MODEL_REVISION}')"
INFEROPS_FACT_ENVIRONMENT="$(require_query "the deployment environment" \
  configmap_field '{.data.INFEROPS_DEPLOYMENT_ENVIRONMENT}')"

# The component labels are read from the cluster rather than copied from the
# descriptor. A fact that is the descriptor round-tripped through a file cannot
# disagree with it, so the check comparing the two could never fail -- and a
# chart that relabelled a Deployment would go on certifying under the old label.
INFEROPS_FACT_API_NAME="${descriptor_api_deployment}"
INFEROPS_FACT_API_COMPONENT="$(require_query "the API component label" \
  deployment_field "${descriptor_api_deployment}" \
  '{.metadata.labels.app\.kubernetes\.io/component}')"
INFEROPS_FACT_API_IMAGES="$(require_query "the API images" deployment_field \
  "${descriptor_api_deployment}" \
  '{.spec.template.spec.initContainers[*].image} {.spec.template.spec.containers[*].image}')"
INFEROPS_FACT_API_DESIRED="$(require_query "the API replica count" deployment_field \
  "${descriptor_api_deployment}" '{.spec.replicas}')"
INFEROPS_FACT_API_READY="$(deployment_field "${descriptor_api_deployment}" '{.status.readyReplicas}' || true)"

INFEROPS_FACT_RUNTIME_NAME="${descriptor_runtime_deployment}"
INFEROPS_FACT_RUNTIME_COMPONENT="$(require_query "the runtime component label" \
  deployment_field "${descriptor_runtime_deployment}" \
  '{.metadata.labels.app\.kubernetes\.io/component}')"
INFEROPS_FACT_RUNTIME_IMAGES="$(require_query "the runtime images" deployment_field \
  "${descriptor_runtime_deployment}" \
  '{.spec.template.spec.initContainers[*].image} {.spec.template.spec.containers[*].image}')"
INFEROPS_FACT_RUNTIME_DESIRED="$(require_query "the runtime replica count" deployment_field \
  "${descriptor_runtime_deployment}" '{.spec.replicas}')"
INFEROPS_FACT_RUNTIME_READY="$(deployment_field "${descriptor_runtime_deployment}" '{.status.readyReplicas}' || true)"

# How the release is actually reading the weights. The chart permits
# `verifyOnStart: sha256 | size | none` under the real profile and the operator
# supplies the values file, so a run that only compared a byte count would
# otherwise still produce a record whose provenance names a SHA-256.
INFEROPS_FACT_CLAIM_NAME="$(require_query "the mounted model cache claim" \
  deployment_field "${descriptor_runtime_deployment}" \
  '{.spec.template.spec.volumes[?(@.name=="model-cache")].persistentVolumeClaim.claimName}')"
INFEROPS_FACT_VOLUME_READ_ONLY="$(deployment_field "${descriptor_runtime_deployment}" \
  '{.spec.template.spec.volumes[?(@.name=="model-cache")].persistentVolumeClaim.readOnly}' || true)"
INFEROPS_FACT_MOUNT_READ_ONLY="$(deployment_field "${descriptor_runtime_deployment}" \
  '{.spec.template.spec.containers[*].volumeMounts[?(@.name=="model-cache")].readOnly}' || true)"
INFEROPS_FACT_INIT_CONTAINERS="$(require_query "the runtime init containers" \
  deployment_field "${descriptor_runtime_deployment}" \
  '{.spec.template.spec.initContainers[*].name}')"
# The init container's own command, so that whether it compares a hash is read
# out of what the cluster will run rather than assumed from the values file.
INFEROPS_FACT_INIT_COMMAND="$(require_query "the model verification command" \
  deployment_field "${descriptor_runtime_deployment}" \
  '{.spec.template.spec.initContainers[*].command}')"

INFEROPS_FACT_PREREQUISITES_MS="${prerequisites_ms}"
INFEROPS_FACT_INSTALL_MS="${install_ms}"
INFEROPS_FACT_API_READY_MS="${api_ready_ms}"
INFEROPS_FACT_RUNTIME_READY_MS="${runtime_ready_ms}"
INFEROPS_FACT_RELEASE_TEST_MS="${release_test_ms}"
INFEROPS_FACT_RELEASE_TEST_PASSED="${release_test_passed}"
INFEROPS_FACT_MODEL_SHA256="$(require_query "the pinned model hash" inferops::python -c '
import sys
sys.path.insert(0, sys.argv[1])
from tools.model_acquisition import load_manifest

print(load_manifest().sha256)
' "$(inferops::native_path "${INFEROPS_ROOT}")")"

export INFEROPS_FACT_PROVIDER \
  INFEROPS_FACT_CLUSTER_NAME INFEROPS_FACT_CONTEXT INFEROPS_FACT_SERVER_VERSION \
  INFEROPS_FACT_NODE_DIGEST INFEROPS_FACT_HELM INFEROPS_FACT_KUBECTL \
  INFEROPS_FACT_TERRAFORM INFEROPS_FACT_RELEASE_NAME INFEROPS_FACT_NAMESPACE \
  INFEROPS_FACT_RELEASE_JSON INFEROPS_FACT_PROFILE INFEROPS_FACT_SERVICE_VERSION \
  INFEROPS_FACT_MODEL_IDENTIFIER INFEROPS_FACT_MODEL_REVISION INFEROPS_FACT_ENVIRONMENT \
  INFEROPS_FACT_API_NAME INFEROPS_FACT_API_COMPONENT INFEROPS_FACT_API_IMAGES \
  INFEROPS_FACT_API_DESIRED INFEROPS_FACT_API_READY INFEROPS_FACT_RUNTIME_NAME \
  INFEROPS_FACT_RUNTIME_COMPONENT INFEROPS_FACT_RUNTIME_IMAGES \
  INFEROPS_FACT_RUNTIME_DESIRED INFEROPS_FACT_RUNTIME_READY \
  INFEROPS_FACT_CLAIM_NAME INFEROPS_FACT_VOLUME_READ_ONLY \
  INFEROPS_FACT_MOUNT_READ_ONLY INFEROPS_FACT_INIT_CONTAINERS \
  INFEROPS_FACT_INIT_COMMAND INFEROPS_FACT_MODEL_SHA256 \
  INFEROPS_FACT_PREREQUISITES_MS INFEROPS_FACT_INSTALL_MS INFEROPS_FACT_API_READY_MS \
  INFEROPS_FACT_RUNTIME_READY_MS INFEROPS_FACT_RELEASE_TEST_MS \
  INFEROPS_FACT_RELEASE_TEST_PASSED

mkdir -p "$(dirname "${facts_file}")"

# The document is assembled by a JSON writer reading the environment rather than
# by string concatenation here. A version string with a quote in it, an image
# reference with a backslash, a version banner spanning lines: each of those
# produces a malformed document when a shell builds JSON by hand, and a
# malformed facts file is a certification that stops for the wrong reason.
#
# tests/architecture/test_kubernetes_certification.py extracts this program and
# runs it against a representative environment, then feeds its output to the
# reader that consumes it -- because a shape agreed by inspection is a shape
# nobody checked.
python - "$(inferops::native_path "${facts_file}")" <<'PYTHON'
import json
import os
import sys
from pathlib import Path


def fact(name: str) -> str:
    return os.environ.get(f"INFEROPS_FACT_{name}", "")


def number(name: str) -> int:
    value = fact(name).strip()
    return int(value) if value.isdigit() else 0


def words(name: str) -> list[str]:
    return [word for word in fact(name).split() if word]


def every_true(name: str) -> bool:
    """A jsonpath over a list yields one word per match, and all must agree.

    An empty result is `False` rather than vacuously true: no match means the
    volume or the mount this asks about was not found, which is not the same as
    finding it and seeing it read-only.
    """
    values = words(name)
    return bool(values) and all(value == "true" for value in values)


release = json.loads(fact("RELEASE_JSON")) or [{}]
terraform = json.loads(fact("TERRAFORM")) if fact("TERRAFORM") else {}

# `helm list -o json` serialises a revision as a string. It is passed through as
# collected rather than coerced here, because the reader that consumes this file
# is where a value is interpreted, and a shell-side coercion would hide a change
# in what helm reports.
document = {
    "cluster": {
        "provider": fact("PROVIDER"),
        "name": fact("CLUSTER_NAME"),
        "context": fact("CONTEXT"),
        "serverVersion": fact("SERVER_VERSION"),
        "nodeImageDigest": fact("NODE_DIGEST"),
    },
    "tooling": {
        "helm": fact("HELM"),
        "kubectl": fact("KUBECTL"),
        "terraform": terraform.get("terraform_version", ""),
    },
    "release": {
        "name": fact("RELEASE_NAME"),
        "namespace": fact("NAMESPACE"),
        "revision": release[0].get("revision", 0),
        "status": release[0].get("status", ""),
        "chart": release[0].get("chart", ""),
        "profile": fact("PROFILE"),
        "testPassed": fact("RELEASE_TEST_PASSED") == "true",
    },
    "workloads": [
        {
            "name": fact("API_NAME"),
            "component": fact("API_COMPONENT"),
            "images": words("API_IMAGES"),
            "replicasDesired": number("API_DESIRED"),
            "replicasReady": number("API_READY"),
        },
        {
            "name": fact("RUNTIME_NAME"),
            "component": fact("RUNTIME_COMPONENT"),
            "images": words("RUNTIME_IMAGES"),
            "replicasDesired": number("RUNTIME_DESIRED"),
            "replicasReady": number("RUNTIME_READY"),
        },
    ],
    "modelCache": {
        "claimName": fact("CLAIM_NAME"),
        "volumeReadOnly": every_true("VOLUME_READ_ONLY"),
        "mountReadOnly": every_true("MOUNT_READ_ONLY"),
        "initContainers": words("INIT_CONTAINERS"),
        # What the cluster will actually run, asked of the rendered command
        # rather than of the values file: the pinned digest has to appear in it
        # and something has to compare it.
        "artifactHashCompared": (
            fact("MODEL_SHA256").removeprefix("sha256:") in fact("INIT_COMMAND")
            and "sha256sum" in fact("INIT_COMMAND")
        ),
    },
    "configuration": {
        "serviceVersion": fact("SERVICE_VERSION"),
        "modelIdentifier": fact("MODEL_IDENTIFIER"),
        "modelRevision": fact("MODEL_REVISION"),
        "deploymentEnvironment": fact("ENVIRONMENT"),
    },
    "timings": {
        "prerequisitesMs": number("PREREQUISITES_MS"),
        "installMs": number("INSTALL_MS"),
        "apiReadyMs": number("API_READY_MS"),
        "runtimeReadyMs": number("RUNTIME_READY_MS"),
        "releaseTestMs": number("RELEASE_TEST_MS"),
    },
}

Path(sys.argv[1]).write_text(
    json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8", newline="\n"
)
PYTHON

inferops::log "cluster facts written to ${facts_rel}. They are host state, not evidence, and .artifacts/ is ignored by version control."

# --- the real request --------------------------------------------------------

inferops::section "Forwarding the API Service"

# Both Services are ClusterIP and no Ingress exists, so a forward is the only
# way anything outside the cluster reaches this API. What that forward proves is
# bounded and is stated in the procedure document: it resolves the Service and
# reaches an endpoint behind it. It does not traverse the Service's virtual IP,
# and it is not covered by the release's own NetworkPolicy -- which is why the
# in-cluster connection test above is run as well rather than instead.
mkdir -p "${diag_dir}"
inferops::target_kubectl port-forward "service/${descriptor_api_service}" \
  "${forward_port}:${descriptor_api_port}" \
  -n "${INFEROPS_RELEASE_NAMESPACE}" --address "${descriptor_host}" >"${forward_log}" 2>&1 &
forward_pid="$!"

# Bounded by the descriptor's forward budget: a forward that never comes up must
# fail this script rather than leave the request to time out against a closed
# port and report that as the model's fault.
forward_deadline=$((SECONDS + forward_budget_ms / 1000))
forward_open=0
while [ "${SECONDS}" -lt "${forward_deadline}" ]; do
  if ! kill -0 "${forward_pid}" 2>/dev/null; then
    inferops::fail "the port-forward exited before it accepted a connection. Its output is in .artifacts/kubernetes-certification/forward.log."
  fi
  if python -c '
import socket, sys

try:
    socket.create_connection((sys.argv[1], int(sys.argv[2])), 2).close()
except OSError:
    sys.exit(1)
' "${descriptor_host}" "${forward_port}" 2>/dev/null; then
    forward_open=1
    break
  fi
  sleep 1
done

[ "${forward_open}" -eq 1 ] ||
  inferops::fail "the forward to '${descriptor_api_service}' did not accept a connection within $((forward_budget_ms / 1000)) s."

inferops::log "forward open on ${base_url} (readiness path ${readiness_path})."

inferops::section "Certifying one real completion"

(cd "${INFEROPS_ROOT}" && python -m tools.kubernetes_certification observe \
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

# Everything Helm installs carries the release's instance label, so this is the
# question "did uninstall remove the release" asked of the cluster rather than
# of Helm's own bookkeeping. `pvc` is in the list on purpose: a chart that
# created a claim would show up here, and this chart must neither create one nor
# delete one.
#
# Asked repeatedly inside a budget rather than once, because `helm uninstall
# --wait` does not answer it. Helm waits for the objects it deleted itself --
# the Deployments, the Services -- and a Deployment's pods are not among them:
# they are removed by the garbage collector once their owner is gone, on the
# controller manager's schedule and not on Helm's. Asking the instant Helm
# returns therefore reports three terminating pods as residue, which is what
# V1-S3-011's first uninstall did. They were gone moments later.
#
# The budget is the uninstall budget, reused rather than invented: the same
# descriptor field bounds how long the removal may take, and a pod still present
# at that deadline is residue by any reading. Nothing here is waived -- what
# changes is when the question is final, not what counts as an answer.
residue_deadline=$((SECONDS + uninstall_budget_ms / 1000))
while :; do
  if ! remaining="$(inferops::target_kubectl get \
    deployments,replicasets,services,configmaps,serviceaccounts,pods,networkpolicies,pvc \
    -n "${INFEROPS_RELEASE_NAMESPACE}" -l "${INFEROPS_RELEASE_SELECTOR}" -o name)"; then
    inferops::fail "could not ask what survived the uninstall. An unanswered query is not an empty result."
  fi
  [ -n "${remaining}" ] || break
  if [ "${SECONDS}" -ge "${residue_deadline}" ]; then
    printf '%s\n' "${remaining}"
    inferops::fail "objects labelled '${INFEROPS_RELEASE_SELECTOR}' survived the uninstall by more than the ${uninstall_budget_ms} ms this certification allows it."
  fi
  sleep 2
done

if inferops::target_helm status "${INFEROPS_RELEASE_NAME}" \
  --namespace "${INFEROPS_RELEASE_NAMESPACE}" >/dev/null 2>&1; then
  inferops::fail "helm still reports a release named '${INFEROPS_RELEASE_NAME}' after the uninstall."
fi

inferops::target_kubectl get namespace "${INFEROPS_RELEASE_NAMESPACE}" >/dev/null 2>&1 ||
  inferops::fail "namespace '${INFEROPS_RELEASE_NAMESPACE}' was removed by an uninstall. It is a Terraform prerequisite and must outlive the release."

if ! claims_after="$(inferops::claim_count)"; then
  inferops::fail "could not count the persistent volume claims after uninstalling. An unanswered query is not an empty result."
fi
[ "${claims_after}" = "${claims_before}" ] ||
  inferops::fail "the claim count changed across the release: ${claims_before} before, ${claims_after} after. This chart must neither create nor delete a claim, and the model cache is Terraform's."

inferops::log "persistent volume claims: ${claims_after}, unchanged by the release."

inferops::section "Result"
inferops::log "the release installed, the model loaded, a real completion returned through the API Service, and the release removed cleanly."
inferops::log "record        .cache/inferops/certification/k8s-real-inference.json (labelled local real Kubernetes)"
inferops::log "the namespace and the model cache claim survived. Reclaiming them is scripts/environment/terraform-prerequisites.sh destroy --confirm, and nothing here does it for you."
