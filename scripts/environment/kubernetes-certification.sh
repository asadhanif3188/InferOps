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
# relative to the repository root. Nothing below invents a threshold: every one
# comes from here, and the Python tool refuses the descriptor if any of them
# disagrees with the runtime package, the composition, or the runtime profile.
readonly INFEROPS_CERTIFICATION_REL="deploy/serving/certification/k8s-real-inference.v1.json"

# The loopback port the forward is opened on. Overridable because a contributor
# may already be running the local composition, which holds the API's own port.
readonly INFEROPS_DEFAULT_FORWARD_PORT="18090"

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
inferops::assert_target_cluster

inferops::section "Certification descriptor"
(cd "${INFEROPS_ROOT}" && python -m tools.kubernetes_certification check)

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
' "$(inferops::native_path "${certification_file}")" "$@"
}

# Read into a variable first and check the status, rather than through a process
# substitution: a reader whose producer failed sees empty fields and no error,
# and an empty budget below becomes an arithmetic expression rather than a
# refusal.
if ! descriptor_fields="$(read_descriptor \
  release.name release.namespace release.apiServiceName release.apiServicePort \
  release.runtimeServiceName release.apiComponent release.runtimeComponent \
  readiness.installBudgetMs readiness.runtimeBudgetMs readiness.apiBudgetMs \
  readiness.releaseTestBudgetMs request.readinessPath evidence.factsFile)"; then
  inferops::fail "the certification descriptor could not be read after it validated. Nothing was installed."
fi

{
  read -r descriptor_release
  read -r descriptor_namespace
  read -r descriptor_api_service
  read -r descriptor_api_port
  read -r descriptor_runtime_service
  read -r descriptor_api_component
  read -r descriptor_runtime_component
  read -r install_budget_ms
  read -r runtime_budget_ms
  read -r api_budget_ms
  read -r release_test_budget_ms
  read -r readiness_path
  read -r facts_rel
} <<<"${descriptor_fields}"

for field in descriptor_release descriptor_namespace descriptor_api_service \
  descriptor_api_port descriptor_runtime_service descriptor_api_component \
  descriptor_runtime_component install_budget_ms runtime_budget_ms \
  api_budget_ms release_test_budget_ms readiness_path facts_rel; do
  [ -n "${!field}" ] ||
    inferops::fail "the certification descriptor left '${field}' empty. Nothing was installed."
done

for budget in install_budget_ms runtime_budget_ms api_budget_ms release_test_budget_ms; do
  case "${!budget}" in
    '' | *[!0-9]*)
      inferops::fail "the certification descriptor's '${budget}' is not a number of milliseconds. Nothing was installed."
      ;;
  esac
done

# Two records name the same release, and they are compared rather than assumed.
# lib.sh is what every script here acts through; the descriptor is what the
# record is written from. A run where they disagree would install one release
# and certify another.
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

configmap_name="${descriptor_api_service}-configuration"
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
  inferops::helm list --namespace "${INFEROPS_RELEASE_NAMESPACE}" >"${diag_dir}/releases.txt" 2>&1 || true
  inferops::helm history "${INFEROPS_RELEASE_NAME}" \
    --namespace "${INFEROPS_RELEASE_NAMESPACE}" >"${diag_dir}/history.txt" 2>&1 || true
  inferops::kubectl get all,configmap,serviceaccount,pvc,endpointslices \
    -n "${INFEROPS_RELEASE_NAMESPACE}" -o wide >"${diag_dir}/get-all.txt" 2>&1 || true
  inferops::kubectl describe pods -n "${INFEROPS_RELEASE_NAMESPACE}" >"${diag_dir}/describe-pods.txt" 2>&1 || true
  inferops::kubectl get events -n "${INFEROPS_RELEASE_NAMESPACE}" \
    --sort-by=.lastTimestamp >"${diag_dir}/events.txt" 2>&1 || true
  # Container logs, tail-bounded. The runtime prints its own load progress and
  # the API prints its structured records; both are the first place to look and
  # neither carries a prompt or a completion.
  inferops::kubectl logs -n "${INFEROPS_RELEASE_NAMESPACE}" \
    -l "${INFEROPS_RELEASE_SELECTOR}" --all-containers --tail=200 >"${diag_dir}/release.log" 2>&1 || true
  inferops::kubectl top pods -n "${INFEROPS_RELEASE_NAMESPACE}" >"${diag_dir}/top-pods.txt" 2>&1 || true
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

trap on_exit EXIT

# --- refuse to certify over an existing release ------------------------------

if inferops::helm status "${INFEROPS_RELEASE_NAME}" \
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

# --- install ----------------------------------------------------------------

inferops::section "Installing the release"

# Deliberately without `--wait`. `--wait` would fold the model load, the API
# start, and the install into one number, and this workflow's whole point is to
# measure model readiness separately from everything else. The rollout waits
# below are the bounded ones, each against the budget the descriptor publishes
# for that component.
#
# `--create-namespace` is absent and must stay absent: the namespace is
# Terraform's, and Helm creating it would make this release's uninstall delete a
# prerequisite.
install_started="$(now_ms)"
inferops::helm install "${INFEROPS_RELEASE_NAME}" "${chart_path}" \
  --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
  --values "${values_path}" \
  --timeout "$((install_budget_ms / 1000))s"
install_ms=$(($(now_ms) - install_started))
inferops::log "helm accepted the install in ${install_ms} ms."

# --- measured model readiness -----------------------------------------------

inferops::section "Waiting for the serving runtime to load the model"

# The long one, and the only one that contains a model load. The budget is the
# runtime package's own startup budget, which the descriptor is refused for
# disagreeing with. A timeout here is a failure with a place to look, not a hang.
runtime_started="$(now_ms)"
inferops::kubectl rollout status "deployment/${descriptor_runtime_service}" \
  -n "${INFEROPS_RELEASE_NAMESPACE}" --timeout="$((runtime_budget_ms / 1000))s"
runtime_ready_ms=$(($(now_ms) - runtime_started))
inferops::log "the serving runtime became ready in ${runtime_ready_ms} ms."

inferops::section "Waiting for the platform API"

api_started="$(now_ms)"
inferops::kubectl rollout status "deployment/${descriptor_api_service}" \
  -n "${INFEROPS_RELEASE_NAMESPACE}" --timeout="$((api_budget_ms / 1000))s"
api_ready_ms=$(($(now_ms) - api_started))
inferops::log "the platform API became ready in ${api_ready_ms} ms."

inferops::kubectl get deployments,services,pods,endpointslices \
  -n "${INFEROPS_RELEASE_NAMESPACE}" -l "${INFEROPS_RELEASE_SELECTOR}" -o wide

# --- the release's own in-cluster check --------------------------------------

inferops::section "Running the release's connection test"

# `helm test` runs one pod inside the cluster that asks both Services for their
# health endpoints over cluster DNS. It is the half a host-side forward cannot
# establish: that the Service names resolve, that the Services select something,
# and that what is behind them answers. The completion assertion below is the
# other half, and neither substitutes for the other.
release_test_started="$(now_ms)"
inferops::helm test "${INFEROPS_RELEASE_NAME}" \
  --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
  --logs \
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
  inferops::kubectl get "deployment/$1" -n "${INFEROPS_RELEASE_NAMESPACE}" \
    -o "jsonpath=$2"
}

configmap_field() {
  inferops::kubectl get "configmap/${configmap_name}" \
    -n "${INFEROPS_RELEASE_NAMESPACE}" -o "jsonpath=$1"
}

node_image_digest="$(inferops::running_node_digest)"
[ -n "${node_image_digest}" ] ||
  inferops::fail "the control-plane node's image digest could not be established. A C2 record names the cluster it ran on by digest, and a node image with no repository digest -- one built or loaded locally -- cannot be named that way."

INFEROPS_FACT_CLUSTER_NAME="${INFEROPS_CLUSTER_NAME}"
INFEROPS_FACT_CONTEXT="${INFEROPS_KUBE_CONTEXT}"
INFEROPS_FACT_SERVER_VERSION="$(require_query "the API server version" \
  inferops::kubectl version -o 'jsonpath={.serverVersion.gitVersion}')"
INFEROPS_FACT_NODE_DIGEST="${node_image_digest}"
INFEROPS_FACT_HELM="$(require_query "the helm version" inferops::helm version --short)"
INFEROPS_FACT_KUBECTL="$(require_query "the kubectl version" \
  inferops::kubectl version --client -o 'jsonpath={.clientVersion.gitVersion}')"
INFEROPS_FACT_TERRAFORM="$(require_query "the terraform version" \
  terraform version -json)"
INFEROPS_FACT_RELEASE_NAME="${INFEROPS_RELEASE_NAME}"
INFEROPS_FACT_NAMESPACE="${INFEROPS_RELEASE_NAMESPACE}"
INFEROPS_FACT_RELEASE_JSON="$(require_query "the installed release's own metadata" \
  inferops::helm list --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
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

INFEROPS_FACT_API_NAME="${descriptor_api_service}"
INFEROPS_FACT_API_COMPONENT="${descriptor_api_component}"
INFEROPS_FACT_API_IMAGES="$(require_query "the API images" deployment_field \
  "${descriptor_api_service}" \
  '{.spec.template.spec.initContainers[*].image} {.spec.template.spec.containers[*].image}')"
INFEROPS_FACT_API_DESIRED="$(require_query "the API replica count" deployment_field \
  "${descriptor_api_service}" '{.spec.replicas}')"
INFEROPS_FACT_API_READY="$(deployment_field "${descriptor_api_service}" '{.status.readyReplicas}' || true)"

INFEROPS_FACT_RUNTIME_NAME="${descriptor_runtime_service}"
INFEROPS_FACT_RUNTIME_COMPONENT="${descriptor_runtime_component}"
INFEROPS_FACT_RUNTIME_IMAGES="$(require_query "the runtime images" deployment_field \
  "${descriptor_runtime_service}" \
  '{.spec.template.spec.initContainers[*].image} {.spec.template.spec.containers[*].image}')"
INFEROPS_FACT_RUNTIME_DESIRED="$(require_query "the runtime replica count" deployment_field \
  "${descriptor_runtime_service}" '{.spec.replicas}')"
INFEROPS_FACT_RUNTIME_READY="$(deployment_field "${descriptor_runtime_service}" '{.status.readyReplicas}' || true)"

INFEROPS_FACT_PREREQUISITES_MS="${prerequisites_ms}"
INFEROPS_FACT_INSTALL_MS="${install_ms}"
INFEROPS_FACT_API_READY_MS="${api_ready_ms}"
INFEROPS_FACT_RUNTIME_READY_MS="${runtime_ready_ms}"
INFEROPS_FACT_RELEASE_TEST_MS="${release_test_ms}"
INFEROPS_FACT_RELEASE_TEST_PASSED="${release_test_passed}"

export INFEROPS_FACT_CLUSTER_NAME INFEROPS_FACT_CONTEXT INFEROPS_FACT_SERVER_VERSION \
  INFEROPS_FACT_NODE_DIGEST INFEROPS_FACT_HELM INFEROPS_FACT_KUBECTL \
  INFEROPS_FACT_TERRAFORM INFEROPS_FACT_RELEASE_NAME INFEROPS_FACT_NAMESPACE \
  INFEROPS_FACT_RELEASE_JSON INFEROPS_FACT_PROFILE INFEROPS_FACT_SERVICE_VERSION \
  INFEROPS_FACT_MODEL_IDENTIFIER INFEROPS_FACT_MODEL_REVISION INFEROPS_FACT_ENVIRONMENT \
  INFEROPS_FACT_API_NAME INFEROPS_FACT_API_COMPONENT INFEROPS_FACT_API_IMAGES \
  INFEROPS_FACT_API_DESIRED INFEROPS_FACT_API_READY INFEROPS_FACT_RUNTIME_NAME \
  INFEROPS_FACT_RUNTIME_COMPONENT INFEROPS_FACT_RUNTIME_IMAGES \
  INFEROPS_FACT_RUNTIME_DESIRED INFEROPS_FACT_RUNTIME_READY \
  INFEROPS_FACT_PREREQUISITES_MS INFEROPS_FACT_INSTALL_MS INFEROPS_FACT_API_READY_MS \
  INFEROPS_FACT_RUNTIME_READY_MS INFEROPS_FACT_RELEASE_TEST_MS \
  INFEROPS_FACT_RELEASE_TEST_PASSED

mkdir -p "$(dirname "${facts_file}")"

# The document is assembled by a JSON writer reading the environment rather than
# by string concatenation here. A version string with a quote in it, an image
# reference with a backslash, a version banner spanning lines: each of those
# produces a malformed document when a shell builds JSON by hand, and a
# malformed facts file is a certification that stops for the wrong reason.
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


def images(name: str) -> list[str]:
    return [reference for reference in fact(name).split() if reference]


release = json.loads(fact("RELEASE_JSON")) or [{}]
terraform = json.loads(fact("TERRAFORM")) if fact("TERRAFORM") else {}

document = {
    "cluster": {
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
            "images": images("API_IMAGES"),
            "replicasDesired": number("API_DESIRED"),
            "replicasReady": number("API_READY"),
        },
        {
            "name": fact("RUNTIME_NAME"),
            "component": fact("RUNTIME_COMPONENT"),
            "images": images("RUNTIME_IMAGES"),
            "replicasDesired": number("RUNTIME_DESIRED"),
            "replicasReady": number("RUNTIME_READY"),
        },
    ],
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
inferops::kubectl port-forward "service/${descriptor_api_service}" \
  "${forward_port}:${descriptor_api_port}" \
  -n "${INFEROPS_RELEASE_NAMESPACE}" --address 127.0.0.1 >"${INFEROPS_ARTIFACT_DIR}/kubernetes-certification-forward.log" 2>&1 &
forward_pid="$!"

base_url="http://127.0.0.1:${forward_port}"

# Bounded: a forward that never comes up must fail this script rather than leave
# the request to time out against a closed port and report that as the model's
# fault.
forward_deadline=$((SECONDS + 30))
forward_open=0
while [ "${SECONDS}" -lt "${forward_deadline}" ]; do
  if ! kill -0 "${forward_pid}" 2>/dev/null; then
    inferops::fail "the port-forward exited before it accepted a connection. Its output is in .artifacts/kubernetes-certification-forward.log."
  fi
  if python -c "
import socket, sys
try:
    socket.create_connection(('127.0.0.1', ${forward_port}), 2).close()
except OSError:
    sys.exit(1)
" 2>/dev/null; then
    forward_open=1
    break
  fi
  sleep 1
done

[ "${forward_open}" -eq 1 ] ||
  inferops::fail "the forward to '${descriptor_api_service}' did not accept a connection within 30 s."

inferops::log "forward open on ${base_url} (readiness path ${readiness_path})."

inferops::section "Certifying one real completion"

(cd "${INFEROPS_ROOT}" && python -m tools.kubernetes_certification observe \
  --confirm-real-kubernetes \
  --base-url "${base_url}" \
  --cluster-facts "${facts_rel}")

close_forward

# --- teardown ----------------------------------------------------------------

inferops::section "Uninstalling the release"

inferops::helm uninstall "${INFEROPS_RELEASE_NAME}" \
  --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
  --wait \
  --timeout 10m

# Everything Helm installs carries the release's instance label, so this is the
# question "did uninstall remove the release" asked of the cluster rather than
# of Helm's own bookkeeping.
if ! remaining="$(inferops::kubectl get \
  deployments,replicasets,services,configmaps,serviceaccounts,pods,networkpolicies \
  -n "${INFEROPS_RELEASE_NAMESPACE}" -l "${INFEROPS_RELEASE_SELECTOR}" -o name)"; then
  inferops::fail "could not ask what survived the uninstall. An unanswered query is not an empty result."
fi
if [ -n "${remaining}" ]; then
  printf '%s\n' "${remaining}"
  inferops::fail "objects labelled '${INFEROPS_RELEASE_SELECTOR}' survived the uninstall."
fi

inferops::kubectl get namespace "${INFEROPS_RELEASE_NAMESPACE}" >/dev/null 2>&1 ||
  inferops::fail "namespace '${INFEROPS_RELEASE_NAMESPACE}' was removed by an uninstall. It is a Terraform prerequisite and must outlive the release."

inferops::section "Result"
inferops::log "the release installed, the model loaded, a real completion returned through the API Service, and the release removed cleanly."
inferops::log "record        .cache/inferops/certification/k8s-real-inference.json (labelled local real Kubernetes)"
inferops::log "the namespace and the model cache claim survived. Reclaiming them is scripts/environment/terraform-prerequisites.sh destroy --confirm, and nothing here does it for you."
