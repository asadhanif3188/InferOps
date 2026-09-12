#!/usr/bin/env bash
# Establishes that the telemetry collector this release installs actually
# discovers and scrapes the two InferOps endpoints, and that the accepted
# correlation queries return what the query record says they return -- asked of a
# running Prometheus rather than of a fixture.
#
# Why this exists. V1-S3-007 rendered a scrape configuration, the Sprint 3
# remediation gave it a collector that reads it, and
# tools/telemetry_correlation evaluates every accepted query against fixture
# stores written by hand. All three are real work and none of them answers the
# question this script asks. A fixture store is a file somebody wrote to look
# like what a scrape would produce; `docs/telemetry/telemetry-correlation-queries.v1alpha1.json`
# says so in its own `verificationStatus`, which recorded `collected: false` and
# "No Prometheus has parsed, loaded, or evaluated any expression in this record."
# The gap between "this expression is well-formed against a catalog" and "this
# expression returns something when a real Prometheus evaluates it against a real
# scrape" is exactly the gap V1-S3-011 exists to close.
#
# What it operates. It applies the Terraform prerequisites through
# scripts/environment/terraform-prerequisites.sh, installs one Helm release,
# sends a small number of real inference requests so that the counters have
# something to count, reads the collector's own API through a loopback forward,
# and uninstalls the release when it is done. It never removes the namespace, the
# model cache claim, or the cluster.
#
# What it does not establish. Nothing about throughput, latency, capacity, or any
# other host: the requests exist to move counters off zero, and their timings are
# not recorded and may not be read as measurements. It establishes discovery,
# scraping, and query answerability, and those only on the provider it names.
#
# Usage:
#   scripts/environment/telemetry-collection-verify.sh verify --values PATH \
#     --confirm-real-kubernetes [--port N] [--collector-port N]

# shellcheck source=scripts/environment/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

# The loopback ports the two forwards are opened on. Host conveniences, not
# thresholds: both move when something else already holds one.
readonly INFEROPS_DEFAULT_API_PORT="18091"
readonly INFEROPS_DEFAULT_COLLECTOR_PORT="19090"

# How many requests are sent before the counters are read. Small on purpose: this
# is the smallest number that can move a per-outcome counter off zero and still
# be defensibly described as "not a measurement of anything".
readonly INFEROPS_REQUEST_COUNT="3"

# How long the collector is given to complete a first scrape of both jobs. The
# rendered configuration's scrape interval is what this has to exceed, several
# times over, and a target that has not answered by then has not answered.
readonly INFEROPS_SCRAPE_BUDGET_SECONDS="120"

readonly INFEROPS_INSTALL_TIMEOUT="15m"
readonly INFEROPS_ROLLOUT_TIMEOUT="900s"
readonly INFEROPS_EVIDENCE_REL=".artifacts/telemetry-collection/verification.json"

action=""
values_file=""
confirmed=0
api_port="${INFEROPS_DEFAULT_API_PORT}"
collector_port="${INFEROPS_DEFAULT_COLLECTOR_PORT}"

while [ "$#" -gt 0 ]; do
  case "$1" in
    verify)
      [ -z "${action}" ] ||
        inferops::fail "two actions were given ('${action}' and '$1'). This script performs one at a time."
      action="$1"
      shift
      ;;
    --values)
      [ "$#" -ge 2 ] || inferops::fail "--values needs a path."
      values_file="$2"
      shift 2
      ;;
    --port)
      [ "$#" -ge 2 ] || inferops::fail "--port needs a number."
      case "$2" in '' | *[!0-9]*) inferops::fail "--port must be a number, not '$2'." ;; esac
      api_port="$2"
      shift 2
      ;;
    --collector-port)
      [ "$#" -ge 2 ] || inferops::fail "--collector-port needs a number."
      case "$2" in '' | *[!0-9]*) inferops::fail "--collector-port must be a number, not '$2'." ;; esac
      collector_port="$2"
      shift 2
      ;;
    --confirm-real-kubernetes)
      confirmed=1
      shift
      ;;
    *)
      inferops::fail "unknown argument '$1'. Usage: telemetry-collection-verify.sh verify --values PATH --confirm-real-kubernetes [--port N] [--collector-port N]"
      ;;
  esac
done

[ "${action}" = "verify" ] ||
  inferops::fail "expected 'verify'. Usage: telemetry-collection-verify.sh verify --values PATH --confirm-real-kubernetes"
[ "${confirmed}" -eq 1 ] ||
  inferops::fail "verify needs --confirm-real-kubernetes. It applies the Terraform prerequisites, installs a release, loads a real model, and sends real inference requests."
[ -n "${values_file}" ] ||
  inferops::fail "--values is required. The chart's shipped defaults select no serving profile and are refused on purpose."
[ -f "${values_file}" ] || inferops::fail "no such values file: ${values_file}"

inferops::require_cmd python
inferops::require_cmd kubectl
inferops::require_cmd helm
inferops::require_cmd terraform
inferops::require_engine

# The provider-aware target this project consumes rather than creates
# (docs/environment/local-cluster-provider-contract.md): an explicit
# INFEROPS_PROVIDER, re-verified now rather than trusted from an earlier run.
inferops::resolve_target

chart_dir="${INFEROPS_ROOT}/${INFEROPS_CHART_PATH}"
[ -d "${chart_dir}" ] || inferops::fail "no chart at ${INFEROPS_CHART_PATH}"
chart_path="$(inferops::native_path "${chart_dir}")"
values_path="$(inferops::native_path "$(cd "$(dirname "${values_file}")" && pwd)/$(basename "${values_file}")")"

evidence_file="${INFEROPS_ROOT}/${INFEROPS_EVIDENCE_REL}"
diag_dir="${INFEROPS_ARTIFACT_DIR}/telemetry-collection"
api_forward_pid=""
collector_forward_pid=""

readonly INFEROPS_API_JOB="${INFEROPS_RELEASE_NAME}-inferops-llm-platform-api"
readonly INFEROPS_RUNTIME_JOB="${INFEROPS_RELEASE_NAME}-inferops-llm-serving-runtime"

# --- forwards and teardown ---------------------------------------------------

close_forwards() {
  for pid in "${collector_forward_pid}" "${api_forward_pid}"; do
    [ -n "${pid}" ] || continue
    kill "${pid}" 2>/dev/null || true
    wait "${pid}" 2>/dev/null || true
  done
  collector_forward_pid=""
  api_forward_pid=""
}

collect_diagnostics() {
  mkdir -p "${diag_dir}"
  inferops::warn "collecting diagnostics into ${INFEROPS_EVIDENCE_REL%/*}/"
  inferops::target_kubectl get all,configmap -n "${INFEROPS_RELEASE_NAMESPACE}" -o wide \
    >"${diag_dir}/get-all.txt" 2>&1 || true
  inferops::target_kubectl describe pods -n "${INFEROPS_RELEASE_NAMESPACE}" \
    >"${diag_dir}/describe-pods.txt" 2>&1 || true
  inferops::target_kubectl logs -n "${INFEROPS_RELEASE_NAMESPACE}" \
    -l "${INFEROPS_RELEASE_SELECTOR}" --all-containers --tail=200 \
    >"${diag_dir}/release.log" 2>&1 || true
}

on_failure() {
  local status=$?
  [ "${status}" -eq 0 ] && return 0
  close_forwards
  collect_diagnostics
  inferops::warn "the release was left in place for inspection. Remove it with: helm uninstall ${INFEROPS_RELEASE_NAME} --namespace ${INFEROPS_RELEASE_NAMESPACE}"
  return "${status}"
}
trap on_failure EXIT

# Opens a loopback forward to $1 on port $2 and waits for it to accept a
# connection. The same shape kubernetes-certification.sh uses, and for the same
# reason: `kubectl port-forward` returns before the listener is up, so a request
# sent immediately after it is a race rather than a test.
open_forward() {
  local service="$1" local_port="$2" remote_port="$3" log="$4"
  mkdir -p "${diag_dir}"
  inferops::target_kubectl port-forward "svc/${service}" \
    "${local_port}:${remote_port}" -n "${INFEROPS_RELEASE_NAMESPACE}" \
    >"${log}" 2>&1 &
  local pid=$!
  local deadline=$((SECONDS + 30))
  while [ "${SECONDS}" -lt "${deadline}" ]; do
    if ! kill -0 "${pid}" 2>/dev/null; then
      inferops::fail "the port-forward to '${service}' exited before it accepted a connection. Its output is in ${log#"${INFEROPS_ROOT}/"}."
    fi
    if python -c '
import socket, sys

try:
    socket.create_connection((sys.argv[1], int(sys.argv[2])), 2).close()
except OSError:
    sys.exit(1)
' 127.0.0.1 "${local_port}" 2>/dev/null; then
      printf '%s' "${pid}"
      return 0
    fi
    sleep 1
  done
  kill "${pid}" 2>/dev/null || true
  inferops::fail "the port-forward to '${service}' did not accept a connection within 30 s."
}

# --- prerequisites and release ----------------------------------------------

inferops::section "Applying the Terraform prerequisites"
bash "${INFEROPS_ROOT}/scripts/environment/terraform-prerequisites.sh" apply

inferops::section "Installing the release"

# Never --create-namespace: Terraform owns the namespace and two tools owning one
# resource is the ownership confusion docs/architecture/resource-ownership.md exists
# to prevent.
inferops::target_helm install "${INFEROPS_RELEASE_NAME}" "${chart_path}" \
  --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
  --values "${values_path}" \
  --timeout "${INFEROPS_INSTALL_TIMEOUT}"

inferops::section "Waiting for the workloads"
for deployment in \
  "${INFEROPS_RELEASE_NAME}-inferops-llm-runtime" \
  "${INFEROPS_RELEASE_NAME}-inferops-llm" \
  "${INFEROPS_RELEASE_NAME}-inferops-llm-collector"; do
  inferops::target_kubectl rollout status "deployment/${deployment}" \
    -n "${INFEROPS_RELEASE_NAMESPACE}" --timeout="${INFEROPS_ROLLOUT_TIMEOUT}"
done

# --- traffic, so that the counters have something to count -------------------

inferops::section "Sending ${INFEROPS_REQUEST_COUNT} real inference request(s)"

api_forward_pid="$(open_forward "${INFEROPS_RELEASE_NAME}-inferops-llm" \
  "${api_port}" 8090 "${diag_dir}/api-forward.log")"

# Not a measurement. These exist so that a per-outcome counter is non-zero when
# the queries below are asked, and their timings are deliberately neither
# recorded nor reported: ADR 0005 refuses a published latency or throughput
# figure for V1, and a number in an evidence file is published whatever the
# sentence beside it says.
# The model name the release was actually configured with, read from the cluster
# rather than written here. The API refuses a completion naming any other model,
# and the identifier is not the alias: a literal in this script would be a second
# place that has to agree with the values file, and the first time it disagreed
# the answer would be an HTTP 400 three steps from the cause.
model_identifier="$(inferops::target_kubectl get \
  "configmap/${INFEROPS_RELEASE_NAME}-inferops-llm-configuration" \
  -n "${INFEROPS_RELEASE_NAMESPACE}" \
  -o 'jsonpath={.data.INFEROPS_MODEL_IDENTIFIER}')"
[ -n "${model_identifier}" ] ||
  inferops::fail "the release's rendered configuration names no model identifier."

# The child's variable is named separately from the constant above, because a
# `NAME=value command` prefix is an assignment and the constant is readonly:
# reusing the name aborts the script rather than passing the value.
INFEROPS_REQUESTS_TO_SEND="${INFEROPS_REQUEST_COUNT}" \
  INFEROPS_MODEL_IDENTIFIER="${model_identifier}" \
  INFEROPS_API_BASE_URL="http://127.0.0.1:${api_port}" \
  inferops::python -c '
import json
import os
import urllib.error
import urllib.request

base = os.environ["INFEROPS_API_BASE_URL"]
count = int(os.environ["INFEROPS_REQUESTS_TO_SEND"])
sent = 0
for index in range(1, count + 1):
    body = json.dumps(
        {
            "model": os.environ["INFEROPS_MODEL_IDENTIFIER"],
            "messages": [{"role": "user", "content": "Reply with one short word."}],
        }
    ).encode("utf-8")
    request = urllib.request.Request(
        f"{base}/v1/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "X-Request-Id": f"v1-s3-011-pr1-telemetry-{index:03d}",
            "X-Correlation-Id": "v1-s3-011-pr1-telemetry",
        },
    )
    with urllib.request.urlopen(request, timeout=180) as response:
        if response.status != 200:
            raise SystemExit(f"request {index} answered {response.status}")
        response.read()
    sent += 1
print(sent)
' >/dev/null

inferops::log "${INFEROPS_REQUEST_COUNT} request(s) answered. Their timings are not recorded and are not a measurement."

# --- the collector's own view ------------------------------------------------

inferops::section "Reading the collector"

collector_forward_pid="$(open_forward "${INFEROPS_RELEASE_NAME}-inferops-llm-collector" \
  "${collector_port}" 9090 "${diag_dir}/collector-forward.log")"

mkdir -p "$(dirname "${evidence_file}")"

# Exported rather than passed as a `NAME=value command` prefix: several of these
# are `readonly`, and a prefix is an assignment, which aborts the script instead
# of passing the value. Exporting a readonly variable is allowed and is what was
# meant.
INFEROPS_COLLECTOR_BASE_URL="http://127.0.0.1:${collector_port}"
export INFEROPS_COLLECTOR_BASE_URL
export INFEROPS_API_JOB INFEROPS_RUNTIME_JOB INFEROPS_SCRAPE_BUDGET_SECONDS
export INFEROPS_TARGET_PROVIDER INFEROPS_TARGET_CLUSTER_NAME
export INFEROPS_TARGET_SERVER_VERSION INFEROPS_RELEASE_NAMESPACE

(cd "${INFEROPS_ROOT}" && python -m tools.telemetry_collection.verify \
  --evidence "$(inferops::native_path "${evidence_file}")")

close_forwards

# --- teardown ----------------------------------------------------------------

inferops::section "Uninstalling the release"

inferops::target_helm uninstall "${INFEROPS_RELEASE_NAME}" \
  --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
  --wait \
  --timeout "5m"

inferops::section "Result"
inferops::log "the collector discovered and scraped both InferOps jobs, the accepted correlation queries were evaluated by a real Prometheus, and the release was removed."
inferops::log "record        ${INFEROPS_EVIDENCE_REL} (host state; .artifacts/ is ignored by version control)"
inferops::log "the namespace and the model cache claim survived. Reclaiming them is scripts/environment/terraform-prerequisites.sh destroy --confirm."
