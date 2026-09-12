#!/usr/bin/env bash
# Certifies the multi-replica Kubernetes serving path: a capacity preflight that
# refuses before anything is created, a release with two or more platform API
# replicas **and two or more serving runtime replicas**, measured per-replica
# readiness, a bounded set of real inference requests sent through the release's
# API Service from inside the cluster, a per-replica correlation drawn from the
# API's own structured logs, a per-replica counter delta read from each
# `llama-server`, a machine-readable record, and a scoped teardown.
#
# This is the answer to "do requests through the Service actually reach more than
# one replica". `kubernetes-certification.sh` does not answer it and says so: its
# one request goes through a `kubectl port-forward`, which the API server serves
# against a single selected endpoint, so it never traverses the Service's virtual
# IP and could not distribute anything if it wanted to. That is why the request
# set here is driven by a short-lived pod in the namespace, one connection per
# request, and why `kube-proxy` rather than this script picks each endpoint.
#
# **The two tiers are measured differently, and a forward is the right tool for
# exactly one of them.** No request can be attributed to a serving replica from
# the API's side: the API dials the runtime's ClusterIP and the socket keeps that
# address rather than the endpoint kube-proxy translated it to, and llama-server
# puts no per-instance identity in a completion. So each runtime pod is asked for
# its own /metrics, before and after the request set, through a forward -- and
# here selecting one endpoint is the point, because the question is what *this*
# replica did. The tool refuses a run in which any of them decoded nothing.
#
# What it operates, and what it does not. It applies the Terraform prerequisite
# layer through scripts/environment/terraform-prerequisites.sh, installs one Helm
# release named by INFEROPS_RELEASE_NAME in INFEROPS_RELEASE_NAMESPACE with the
# replica counts the descriptor requests, creates one Job that sends the request
# set, deletes that Job, and uninstalls the release. It never removes the
# namespace, never removes the model cache claim, and never removes the cluster:
# those outlive a release by design (docs/architecture/resource-ownership.md).
#
# The assertions and the record are not here. They are in
# tools/kubernetes_certification/multi_replica.py, which reads the committed
# descriptor, refuses a capacity shortfall before anything is installed, refuses
# a run whose successful requests do not correlate to at least two distinct ready
# API replicas, refuses a run in which any ready serving replica decoded nothing,
# and writes the labelled record. The split is the one
# `kubernetes-certification.sh` already makes and for the same reason: the guard
# that establishes which cluster is being acted on lives in lib.sh, and a second
# implementation of it in Python would be a second guard.
#
# The replica counts come from the descriptor and are passed to Helm with
# `--set`, rather than being read out of the operator's values file. That is
# deliberate: the profile is what this certification is about, and a values file
# that happened to say `replicaCount: 1` would otherwise produce a run that
# quietly certified something else.
#
# On failure it collects diagnostics into .artifacts/, leaves the release in
# place for inspection, and says how to remove it. It does not tear down the
# evidence of its own failure.
#
# Usage:
#   scripts/environment/kubernetes-multi-replica-certification.sh check
#   scripts/environment/kubernetes-multi-replica-certification.sh certify \
#     --values PATH --confirm-real-kubernetes

# shellcheck source=scripts/environment/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

# The committed descriptor this workflow reads its own budgets, replica counts,
# and request set from, relative to the repository root.
readonly INFEROPS_MULTI_CERTIFICATION_REL="deploy/serving/certification/k8s-multi-replica-inference.v1.json"

# The Python entry point that owns every assertion and the record.
readonly INFEROPS_MULTI_MODULE="tools.kubernetes_certification.multi_replica_cli"

# How much of each container's log a failure keeps. Not a threshold: it bounds an
# artifact, not a decision.
readonly INFEROPS_LOG_TAIL="200"

# How long to wait for the request driver's pod to be created and scheduled,
# before the request set itself starts. Also not a threshold: the request set is
# bounded by the descriptor's own distribution budget, and this covers only the
# gap between `kubectl apply` and a pod existing.
readonly INFEROPS_DRIVER_START_SECONDS="120"

# How often the driver Job is asked whether it has finished, and how long its
# removal may take. Neither is a threshold: the first bounds a poll interval and
# the second bounds a delete, and the decisions in this workflow are the
# descriptor's.
readonly INFEROPS_DRIVER_POLL_SECONDS="5"
readonly INFEROPS_DRIVER_DELETE_SECONDS="120"

# Where the per-replica counter forward listens. Loopback, because nothing off
# this host has any business reading a serving replica's counters, and one port
# because the replicas are forwarded one at a time and each forward is closed
# before the next opens. Neither is a threshold; the budget that bounds a forward
# is the descriptor's.
readonly INFEROPS_COUNTER_FORWARD_HOST="127.0.0.1"
readonly INFEROPS_COUNTER_FORWARD_PORT="18099"

# Whether something is already listening on the counter forward's port. Asked
# before each forward is opened, because the script otherwise establishes only
# that *a* listener answers -- not that it is the one this run started. A
# squatter normally makes `kubectl port-forward` fail to bind and the liveness
# check catches it, but "normally" is not the standard the rest of this workflow
# holds itself to, and a run that read another process's answers would produce
# evidence rather than an error.
port_in_use() {
  python -c '
import socket, sys

try:
    socket.create_connection((sys.argv[1], int(sys.argv[2])), 2).close()
except OSError:
    sys.exit(1)
' "$1" "$2" 2>/dev/null
}

# Reading one serving replica's counters. It is written once and run twice per
# replica -- before and after the request set -- rather than inlined at both
# call sites, because two copies of a parser are two things to keep agreeing.
#
# `http.client` rather than a client library: this is the standard library's own
# HTTP and ADR 0004's dependency rule leaves nothing else. The body is bounded
# before it is parsed for the same reason the adapter's transport bounds one.
#
# A counter the runtime did not publish is a failure here rather than a zero.
# Absent and zero are different facts and only one of them means the replica
# served nothing; defaulting would turn a scrape that failed into a replica that
# idled, and then into a certification that failed for a reason nobody can act
# on. A labelled series lands in the same place: `llamacpp:n_decode_total{...}`
# does not match the bare name, so it is reported missing rather than misread.
readonly INFEROPS_COUNTER_PROGRAM='
import http.client
import json
import os
import sys

names = os.environ["INFEROPS_COUNTER_NAMES"].split()
connection = http.client.HTTPConnection(
    os.environ["INFEROPS_COUNTER_HOST"],
    int(os.environ["INFEROPS_COUNTER_PORT"]),
    timeout=30,
)
try:
    connection.request("GET", os.environ["INFEROPS_COUNTER_PATH"])
    response = connection.getresponse()
    status = response.status
    body = response.read(1048576).decode("utf-8", "replace")
finally:
    connection.close()

if status != 200:
    print(f"the runtime answered {status} for its counters", file=sys.stderr)
    raise SystemExit(1)

counters = {}
labelled = []
for line in body.splitlines():
    line = line.strip()
    if not line or line.startswith("#"):
        continue
    # Split on whitespace rather than on the first space. The exposition format
    # permits `name value timestamp`, and reading the value as everything after
    # the first space would turn a legal sample into an unparseable one -- which
    # then reads as a counter the runtime did not publish, and fails a correct
    # run with the wrong reason.
    fields = line.split()
    if len(fields) < 2:
        continue
    name = fields[0]
    if name not in names:
        # A labelled series does not match a bare name, and it must not be
        # reported as an absence either: "the runtime published none of these"
        # would send a reader looking for a missing feature rather than for a
        # renamed one. The three this reads are unlabelled in the recorded
        # sample from the pinned image; if that ever changes, say so.
        if name.partition("{")[0] in names:
            labelled.append(name)
        continue
    try:
        number = float(fields[1])
    except ValueError:
        continue
    # All three are counts of things. A fractional value would mean the series
    # read is not the series named, and it is carried through as a float so that
    # the reader refuses it rather than this program rounding it away.
    counters[name] = int(number) if number.is_integer() else number

if labelled:
    print(
        f"the runtime publishes {sorted(set(labelled))} as labelled series, and "
        "this certification reads them unlabelled",
        file=sys.stderr,
    )
    raise SystemExit(1)

missing = [name for name in names if name not in counters]
if missing:
    print(f"the runtime published none of {missing}", file=sys.stderr)
    raise SystemExit(1)

print(
    json.dumps(
        {"podName": os.environ["INFEROPS_COUNTER_POD"], "counters": counters},
        sort_keys=True,
    )
)
'

action=""
values_file=""
confirmed=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    check | certify)
      [ -z "${action}" ] ||
        inferops::fail "two actions were given ('${action}' and '$1'). This script performs one at a time, so that its output describes what it did."
      action="$1"
      shift
      ;;
    --values)
      [ "$#" -ge 2 ] || inferops::fail "--values needs a path. Usage: kubernetes-multi-replica-certification.sh certify --values PATH --confirm-real-kubernetes"
      values_file="$2"
      shift 2
      ;;
    --confirm-real-kubernetes)
      confirmed=1
      shift
      ;;
    *)
      inferops::fail "unknown argument '$1'. Usage: kubernetes-multi-replica-certification.sh check|certify [--values PATH] [--confirm-real-kubernetes]"
      ;;
  esac
done

[ -n "${action}" ] ||
  inferops::fail "expected one of check, certify. Usage: kubernetes-multi-replica-certification.sh check|certify [--values PATH] [--confirm-real-kubernetes]"

inferops::require_cmd python

certification_file="${INFEROPS_ROOT}/${INFEROPS_MULTI_CERTIFICATION_REL}"
[ -f "${certification_file}" ] ||
  inferops::fail "no multi-replica certification descriptor at ${INFEROPS_MULTI_CERTIFICATION_REL}"

# --- check: reads files, contacts nothing -----------------------------------

if [ "${action}" = "check" ]; then
  inferops::section "Multi-replica certification descriptor"
  (cd "${INFEROPS_ROOT}" && python -m "${INFEROPS_MULTI_MODULE}" check)
  inferops::log "the descriptor validated. Nothing was contacted and no release was installed."
  exit 0
fi

# --- everything below reaches a cluster and a real model --------------------

[ "${confirmed}" -eq 1 ] ||
  inferops::fail "certify needs --confirm-real-kubernetes. It applies the Terraform prerequisites, installs a multi-replica release, loads a real model, and sends a bounded set of real inference requests. Usage: kubernetes-multi-replica-certification.sh certify --values PATH --confirm-real-kubernetes"

[ -n "${values_file}" ] ||
  inferops::fail "--values is required. The chart's shipped defaults select no serving profile and are refused on purpose, so there is no values file this script could reasonably assume. See docs/serving/kubernetes-multi-replica-certification.md."

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


inferops::section "Multi-replica certification descriptor"
(cd "${INFEROPS_ROOT}" && python -m "${INFEROPS_MULTI_MODULE}" check)

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

# Read into a variable first and check the status, rather than through a process
# substitution: a reader whose producer failed sees empty fields and no error,
# and an empty budget below becomes an arithmetic expression rather than a
# refusal.
# The descriptor's entry for the provider that was actually verified. Selecting
# it is a lookup rather than a path, for the reason
# scripts/environment/kubernetes-certification.sh states beside its own copy:
# the descriptor describes every provider this certification supports, and a run
# is certified against the one it is on.
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

if ! descriptor_fields="$(read_descriptor \
  release.name release.namespace release.apiServiceName release.apiServicePort \
  release.apiDeploymentName release.runtimeDeploymentName release.configMapName \
  release.apiComponent release.runtimeComponent \
  release.apiReplicas release.runtimeReplicas \
  readiness.installBudgetMs readiness.runtimeRolloutBudgetMs \
  readiness.apiRolloutBudgetMs readiness.releaseTestBudgetMs \
  readiness.distributionBudgetMs readiness.uninstallBudgetMs \
  distribution.driverName distribution.driverImage distribution.driverComponent \
  distribution.path distribution.prompt distribution.requestCount \
  distribution.requestIdPrefix distribution.correlationId \
  distribution.requestTimeoutMs \
  runtimeDistribution.metricsPath runtimeDistribution.decodeCounter \
  runtimeDistribution.predictedTokenCounter \
  runtimeDistribution.promptTokenCounter \
  runtimeDistribution.minimumServingReplicas \
  runtimeDistribution.forwardBudgetMs \
  evidence.capacityFile evidence.factsFile evidence.observationsFile \
  evidence.runtimeCountersFile evidence.cleanupFile)"; then
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
  read -r descriptor_api_component
  read -r descriptor_runtime_component
  read -r api_replicas
  read -r runtime_replicas
  read -r install_budget_ms
  read -r runtime_rollout_budget_ms
  read -r api_rollout_budget_ms
  read -r release_test_budget_ms
  read -r distribution_budget_ms
  read -r uninstall_budget_ms
  read -r driver_name
  read -r driver_image
  read -r driver_component
  read -r request_path
  read -r request_prompt
  read -r request_count
  read -r request_id_prefix
  read -r request_correlation_id
  read -r request_timeout_ms
  read -r metrics_path
  read -r decode_counter
  read -r predicted_counter
  read -r prompt_counter
  read -r minimum_serving_replicas
  read -r counter_forward_budget_ms
  read -r capacity_rel
  read -r facts_rel
  read -r observations_rel
  read -r counters_rel
  read -r cleanup_rel
} <<<"${descriptor_fields}"

for field in descriptor_cluster descriptor_context descriptor_release \
  descriptor_namespace descriptor_api_service descriptor_api_port \
  descriptor_api_deployment \
  descriptor_runtime_deployment descriptor_configmap descriptor_api_component \
  descriptor_runtime_component api_replicas runtime_replicas install_budget_ms \
  runtime_rollout_budget_ms api_rollout_budget_ms release_test_budget_ms \
  distribution_budget_ms uninstall_budget_ms driver_name driver_image \
  driver_component request_path request_prompt request_count \
  request_id_prefix request_correlation_id request_timeout_ms metrics_path \
  decode_counter predicted_counter prompt_counter minimum_serving_replicas \
  counter_forward_budget_ms capacity_rel \
  facts_rel observations_rel counters_rel cleanup_rel; do
  [ -n "${!field}" ] ||
    inferops::fail "the certification descriptor left '${field}' empty. Nothing was installed."
done

# Every value that reaches shell arithmetic, a replica count, or a timeout is
# held to being a number here, at the point of use. The Python validator already
# refuses a non-integer, but that is a different file: a guard whose correctness
# depends on the order two programs run in is a guard waiting to be reordered.
for number in descriptor_api_port api_replicas runtime_replicas \
  install_budget_ms runtime_rollout_budget_ms api_rollout_budget_ms \
  release_test_budget_ms distribution_budget_ms uninstall_budget_ms \
  request_count request_timeout_ms minimum_serving_replicas \
  counter_forward_budget_ms; do
  case "${!number}" in
    '' | *[!0-9]*)
      inferops::fail "the certification descriptor's '${number}' is not a number. Nothing was installed."
      ;;
  esac
done

# The driver's name reaches a manifest and a `kubectl delete`, so it is held to
# being a DNS-1123 label here rather than trusted for having come out of a
# committed file. A name that could be read as a flag is the shape that turns a
# scoped deletion into an unscoped one, and this is where it is refused.
case "${driver_name}" in
  [a-z0-9]*[a-z0-9] | [a-z0-9]) ;;
  *) inferops::fail "the descriptor's request driver name '${driver_name}' is not a DNS-1123 label. Nothing was installed." ;;
esac
case "${driver_name}" in
  *[!a-z0-9-]*) inferops::fail "the descriptor's request driver name '${driver_name}' contains a character a DNS-1123 label may not. Nothing was installed." ;;
esac

# The refusal this whole workflow exists to make impossible to skip. The Python
# validator refuses a descriptor asking for fewer than two API replicas; this
# repeats it where the count is about to be handed to Helm, because that is the
# single value whose downgrade would turn this into the single-replica
# certification wearing a multi-replica record.
[ "${api_replicas}" -ge 2 ] ||
  inferops::fail "the descriptor requests ${api_replicas} platform API replica(s). A multi-replica certification requests at least two, and this script does not reduce the count to fit a host. Nothing was installed."

# And the same refusal for the tier this certification is named after. Two API
# replicas in front of one model server is a single-replica serving path with a
# load balancer on it, and it was what this workflow certified until the Sprint 3
# remediation. The count is checked here because this is where it is handed to
# Helm.
[ "${runtime_replicas}" -ge 2 ] ||
  inferops::fail "the descriptor requests ${runtime_replicas} serving runtime replica(s). Multi-replica *inference* requests at least two model servers, and this script does not reduce the count to fit a host. Nothing was installed."

# Three records name one target, and they are compared rather than assumed.
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

diag_dir="${INFEROPS_ARTIFACT_DIR}/kubernetes-multi-replica-certification"
capacity_file="${INFEROPS_ROOT}/${capacity_rel}"
facts_file="${INFEROPS_ROOT}/${facts_rel}"
observations_file="${INFEROPS_ROOT}/${observations_rel}"
counters_file="${INFEROPS_ROOT}/${counters_rel}"
cleanup_file="${INFEROPS_ROOT}/${cleanup_rel}"
driver_created=0
forward_pid=""


# --- bounded measurement ----------------------------------------------------

now_ms() { printf '%s' "$(($(date +%s%N) / 1000000))"; }

# RFC 3339 in UTC, which is the form the record's time window is written in and
# the only form that can be joined with anything else this project emits.
now_rfc3339() { date -u +%Y-%m-%dT%H:%M:%SZ; }

# --- diagnostics and teardown ------------------------------------------------

collect_diagnostics() {
  mkdir -p "${diag_dir}"
  inferops::warn "collecting diagnostics into .artifacts/kubernetes-multi-replica-certification/"
  inferops::target_helm list --namespace "${INFEROPS_RELEASE_NAMESPACE}" >"${diag_dir}/releases.txt" 2>&1 || true
  inferops::target_helm history "${INFEROPS_RELEASE_NAME}" \
    --namespace "${INFEROPS_RELEASE_NAMESPACE}" >"${diag_dir}/history.txt" 2>&1 || true
  inferops::target_kubectl get all,configmap,serviceaccount,pvc,endpointslices \
    -n "${INFEROPS_RELEASE_NAMESPACE}" -o wide >"${diag_dir}/get-all.txt" 2>&1 || true
  inferops::target_kubectl describe pods -n "${INFEROPS_RELEASE_NAMESPACE}" >"${diag_dir}/describe-pods.txt" 2>&1 || true
  inferops::target_kubectl get events -n "${INFEROPS_RELEASE_NAMESPACE}" \
    --sort-by=.lastTimestamp >"${diag_dir}/events.txt" 2>&1 || true
  inferops::target_kubectl logs -n "${INFEROPS_RELEASE_NAMESPACE}" \
    -l "${INFEROPS_RELEASE_SELECTOR}" --all-containers --tail="${INFEROPS_LOG_TAIL}" >"${diag_dir}/release.log" 2>&1 || true
  inferops::target_kubectl top pods -n "${INFEROPS_RELEASE_NAMESPACE}" >"${diag_dir}/top-pods.txt" 2>&1 || true
}

# Removes the driver Job, and says whether it actually went.
#
# The status is returned rather than swallowed, and `driver_created` is cleared
# only on success, because of what the driver's own labels mean downstream. It
# deliberately carries this release's instance label so that the release's
# network policy describes it, and that is the same label the residue check after
# the uninstall selects on -- with `jobs` in its resource list. A delete that was
# accepted but had not finished would therefore be counted as an object of the
# *release* surviving its own uninstall, and the run would fail blaming the
# teardown for the workflow's own artifact. So a removal that does not complete
# is reported here, as itself.
# A forward is a background process this script owns, so every path out of the
# script closes it -- including the signal paths, which is why `on_exit` is
# trapped on INT and TERM as well as EXIT.
close_forward() {
  if [ -n "${forward_pid}" ] && kill -0 "${forward_pid}" 2>/dev/null; then
    kill "${forward_pid}" 2>/dev/null || true
    wait "${forward_pid}" 2>/dev/null || true
  fi
  forward_pid=""
}

remove_driver() {
  [ "${driver_created}" -eq 1 ] || return 0
  # `--ignore-not-found` so that a second call after a successful removal is not
  # itself a failure, and `--wait` so that the residue assertion below is asked
  # of a namespace the driver has actually left rather than one it is leaving.
  if inferops::target_kubectl delete job "${driver_name}" \
    -n "${INFEROPS_RELEASE_NAMESPACE}" --ignore-not-found --wait \
    --timeout="${INFEROPS_DRIVER_DELETE_SECONDS}s" >/dev/null 2>&1; then
    driver_created=0
    return 0
  fi
  return 1
}

on_exit() {
  local rc=$?
  close_forward
  if [ "${rc}" -ne 0 ]; then
    collect_diagnostics
    # Swallowed here and nowhere else: this path is already failing, and a
    # removal that did not complete must not replace the exit code that says
    # why. The message below names the release; a driver Job that outlived it
    # is visible in the diagnostics.
    if ! remove_driver; then
      inferops::warn "the request driver Job '${driver_name}' could not be removed from '${INFEROPS_RELEASE_NAMESPACE}'. Remove it by hand before the next run: it carries this release's instance label, so a later run's residue check would count it as an object of the release."
    fi

    inferops::warn "the release was left in place for inspection. Remove it with: helm uninstall ${INFEROPS_RELEASE_NAME} --namespace ${INFEROPS_RELEASE_NAMESPACE}"
    inferops::warn "the Terraform prerequisites and the cluster were not touched by this failure."
  fi
  exit "${rc}"
}

trap on_exit INT TERM EXIT

# --- refuse to certify over an existing release ------------------------------

if inferops::target_helm status "${INFEROPS_RELEASE_NAME}" \
  --namespace "${INFEROPS_RELEASE_NAMESPACE}" >/dev/null 2>&1; then
  inferops::fail "release '${INFEROPS_RELEASE_NAME}' already exists in '${INFEROPS_RELEASE_NAMESPACE}'. Remove it first: helm uninstall ${INFEROPS_RELEASE_NAME} --namespace ${INFEROPS_RELEASE_NAMESPACE}"
fi

# --- capacity preflight, before anything is created --------------------------

inferops::section "Capacity preflight"

# This is the one measurement that has to happen with the namespace still empty.
# Two replicas of each tier is roughly four and a quarter gibibytes of requests
# and seven of limits, because a second model server is a second copy of the
# model in memory rather than a second process sharing one. A host that cannot
# hold it produces a Pending pod and a rollout that fails for a reason a record
# would describe as readiness. So it is asked here, and a shortfall is reported
# in full rather than one item at a time.
mkdir -p "$(dirname "${capacity_file}")"

if ! engine_cpus="$(docker info --format '{{.NCPU}}' 2>/dev/null)" ||
  [ -z "${engine_cpus}" ]; then
  inferops::fail "the container engine did not report its processor count. An unanswered query is not a measurement, and this preflight is what stands between a small host and a release it cannot schedule."
fi
if ! engine_memory="$(docker info --format '{{.MemTotal}}' 2>/dev/null)" ||
  [ -z "${engine_memory}" ]; then
  inferops::fail "the container engine did not report its memory. An unanswered query is not a measurement."
fi

if ! node_json="$(inferops::target_kubectl get nodes -o json)"; then
  inferops::fail "could not read the cluster's nodes. An unanswered query is not an empty cluster."
fi
if ! pod_json="$(inferops::target_kubectl get pods --all-namespaces -o json)"; then
  inferops::fail "could not read what is already scheduled on the cluster. Capacity that is not measured is capacity nobody may assume."
fi

INFEROPS_CAPACITY_ENGINE_CPUS="${engine_cpus}"
INFEROPS_CAPACITY_ENGINE_MEMORY="${engine_memory}"
INFEROPS_CAPACITY_NODES="${node_json}"
INFEROPS_CAPACITY_PODS="${pod_json}"
export INFEROPS_CAPACITY_ENGINE_CPUS INFEROPS_CAPACITY_ENGINE_MEMORY \
  INFEROPS_CAPACITY_NODES INFEROPS_CAPACITY_PODS

# Assembled by a JSON writer reading the environment rather than by string
# concatenation. Kubernetes quantities are their own grammar -- `2Gi`, `1500m`,
# `1e3`, a bare integer -- and a shell that parsed them with `cut` would be a
# capacity gate that silently rounded. tests/architecture extracts this program
# and runs it against representative node and pod documents.
python - "$(inferops::native_path "${capacity_file}")" <<'CAPACITY_PYTHON'
import json
import os
import sys
from pathlib import Path

BINARY = {"Ki": 1024, "Mi": 1024**2, "Gi": 1024**3, "Ti": 1024**4, "Pi": 1024**5}
DECIMAL = {"n": 1e-9, "u": 1e-6, "m": 1e-3, "k": 1e3, "M": 1e6, "G": 1e9, "T": 1e12}

# A pod in one of these has released whatever it was granted; counting it would
# make a cluster look full because something finished on it yesterday.
FINISHED = {"Succeeded", "Failed"}


def quantity(value: object) -> float:
    """One Kubernetes quantity as a number, or zero when it is absent.

    Absent is zero rather than an error on purpose: a container with no
    resource request has no request, and the sum of what is committed is
    exactly the sum over the containers that asked for something.
    """
    if value is None:
        return 0.0
    text = str(value).strip()
    if not text:
        return 0.0
    for suffix, factor in BINARY.items():
        if text.endswith(suffix):
            return float(text[: -len(suffix)]) * factor
    if text and text[-1] in DECIMAL:
        return float(text[:-1]) * DECIMAL[text[-1]]
    return float(text)


def millicores(value: object) -> int:
    return int(round(quantity(value) * 1000))


nodes = json.loads(os.environ.get("INFEROPS_CAPACITY_NODES", "{}")).get("items", [])
pods = json.loads(os.environ.get("INFEROPS_CAPACITY_PODS", "{}")).get("items", [])

schedulable = [
    node for node in nodes if not node.get("spec", {}).get("unschedulable", False)
]
allocatable_cpu = sum(
    millicores(node.get("status", {}).get("allocatable", {}).get("cpu"))
    for node in schedulable
)
allocatable_memory = sum(
    int(quantity(node.get("status", {}).get("allocatable", {}).get("memory")))
    for node in schedulable
)

committed_cpu = 0
committed_memory = 0
for pod in pods:
    if pod.get("status", {}).get("phase") in FINISHED:
        continue
    spec = pod.get("spec", {})
    containers = spec.get("containers", []) or []
    init_containers = spec.get("initContainers", []) or []
    # A pod's effective request is the larger of what its containers ask for
    # together and what its largest init container asks for alone, because the
    # init containers run one at a time and before any of the others.
    cpu = sum(
        millicores(
            container.get("resources", {}).get("requests", {}).get("cpu")
        )
        for container in containers
    )
    memory = sum(
        int(quantity(container.get("resources", {}).get("requests", {}).get("memory")))
        for container in containers
    )
    for container in init_containers:
        requests = container.get("resources", {}).get("requests", {})
        cpu = max(cpu, millicores(requests.get("cpu")))
        memory = max(memory, int(quantity(requests.get("memory"))))
    committed_cpu += cpu
    committed_memory += memory

document = {
    "engine": {
        "cpus": int(os.environ.get("INFEROPS_CAPACITY_ENGINE_CPUS", "0") or 0),
        "memoryBytes": int(
            os.environ.get("INFEROPS_CAPACITY_ENGINE_MEMORY", "0") or 0
        ),
    },
    "cluster": {
        "schedulableNodes": len(schedulable),
        "allocatableCpuMillis": allocatable_cpu,
        "allocatableMemoryBytes": allocatable_memory,
        "committedCpuMillis": committed_cpu,
        "committedMemoryBytes": committed_memory,
    },
}

Path(sys.argv[1]).write_text(
    json.dumps(document, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
    newline="\n",
)
CAPACITY_PYTHON

unset INFEROPS_CAPACITY_NODES INFEROPS_CAPACITY_PODS

(cd "${INFEROPS_ROOT}" && python -m "${INFEROPS_MULTI_MODULE}" preflight \
  --confirm-real-kubernetes)

inferops::log "the host and the cluster can hold ${api_replicas} API replica(s) and ${runtime_replicas} runtime replica(s). Nothing has been installed yet."

# --- prerequisites ----------------------------------------------------------

inferops::section "Applying the Terraform prerequisites"

started_at="$(now_rfc3339)"
prerequisites_started="$(now_ms)"
bash "${INFEROPS_ROOT}/scripts/environment/terraform-prerequisites.sh" apply
prerequisites_ms=$(($(now_ms) - prerequisites_started))
inferops::log "prerequisites applied in ${prerequisites_ms} ms."

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

inferops::section "Installing the release with ${api_replicas} API replica(s)"

# Deliberately without `--wait`, and deliberately with the replica counts set
# from the descriptor rather than taken from the values file. `--create-namespace`
# is absent and must stay absent: the namespace is Terraform's, and Helm creating
# it would make this release's uninstall delete a prerequisite.
install_started="$(now_ms)"
inferops::target_helm install "${INFEROPS_RELEASE_NAME}" "${chart_path}" \
  --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
  --values "${values_path}" \
  --set "api.replicaCount=${api_replicas}" \
  --set "runtime.replicaCount=${runtime_replicas}" \
  --timeout "$((install_budget_ms / 1000))s"
install_ms=$(($(now_ms) - install_started))
inferops::log "helm accepted the install in ${install_ms} ms."

# --- measured model readiness -----------------------------------------------

inferops::section "Waiting for the serving runtime to load the model"

runtime_started="$(now_ms)"
inferops::target_kubectl rollout status "deployment/${descriptor_runtime_deployment}" \
  -n "${INFEROPS_RELEASE_NAMESPACE}" --timeout="$((runtime_rollout_budget_ms / 1000))s"
runtime_ready_ms=$(($(now_ms) - runtime_started))
inferops::log "the serving runtime became ready in ${runtime_ready_ms} ms."

inferops::section "Waiting for every platform API replica"

# `kubectl rollout status` returns when the Deployment reports the whole
# updated replica set available, so it covers every replica rather than the
# first. What it does not do is say which pod took how long, and that is
# collected per pod below: a certification that every expected replica reached
# readiness may not rest on a controller's summary count.
api_started="$(now_ms)"
inferops::target_kubectl rollout status "deployment/${descriptor_api_deployment}" \
  -n "${INFEROPS_RELEASE_NAMESPACE}" --timeout="$((api_rollout_budget_ms / 1000))s"
api_ready_ms=$(($(now_ms) - api_started))
inferops::log "every platform API replica became ready in ${api_ready_ms} ms."

inferops::target_kubectl get deployments,services,pods,endpointslices \
  -n "${INFEROPS_RELEASE_NAMESPACE}" -l "${INFEROPS_RELEASE_SELECTOR}" -o wide

# --- the release's own in-cluster check --------------------------------------

inferops::section "Running the release's connection test"

release_test_started="$(now_ms)"
# Without `--logs`: the chart deletes a test pod that succeeded, and
# `helm test --logs` then fails fetching logs from a pod that is gone,
# reporting a passing test as a failure. scripts/environment/kubernetes-certification.sh
# states the whole of it beside its own call.
inferops::target_helm test "${INFEROPS_RELEASE_NAME}" \
  --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
  --timeout "$((release_test_budget_ms / 1000))s"
release_test_ms=$(($(now_ms) - release_test_started))
release_test_passed="true"
inferops::log "the in-cluster connection test passed in ${release_test_ms} ms."

# --- what ran, as facts ------------------------------------------------------

inferops::section "Collecting cluster facts"

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
  inferops::fail "the control-plane node's image digest could not be established. A C2 record names the cluster it ran on by digest."

# Every pod of the release, with its readiness and how long it took to reach it.
# This is the per-replica half of the evidence, and it is read from the pods
# rather than from the Deployment for the reason stated above.
if ! pods_json="$(inferops::target_kubectl get pods -n "${INFEROPS_RELEASE_NAMESPACE}" \
  -l "${INFEROPS_RELEASE_SELECTOR}" -o json)"; then
  inferops::fail "could not read the release's pods. Per-replica readiness is what this certification is about, and an unanswered query is not a measurement."
fi

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
INFEROPS_FACT_INIT_COMMAND="$(require_query "the model verification command" \
  deployment_field "${descriptor_runtime_deployment}" \
  '{.spec.template.spec.initContainers[*].command}')"

INFEROPS_FACT_PODS_JSON="${pods_json}"
INFEROPS_FACT_API_COMPONENT_NAME="${descriptor_api_component}"
INFEROPS_FACT_RUNTIME_COMPONENT_NAME="${descriptor_runtime_component}"
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
  INFEROPS_FACT_PODS_JSON INFEROPS_FACT_API_COMPONENT_NAME \
  INFEROPS_FACT_RUNTIME_COMPONENT_NAME \
  INFEROPS_FACT_PREREQUISITES_MS INFEROPS_FACT_INSTALL_MS INFEROPS_FACT_API_READY_MS \
  INFEROPS_FACT_RUNTIME_READY_MS INFEROPS_FACT_RELEASE_TEST_MS \
  INFEROPS_FACT_RELEASE_TEST_PASSED

mkdir -p "$(dirname "${facts_file}")"

python - "$(inferops::native_path "${facts_file}")" <<'FACTS_PYTHON'
import json
import os
import sys
from datetime import datetime
from pathlib import Path


def fact(name: str) -> str:
    return os.environ.get(f"INFEROPS_FACT_{name}", "")


def number(name: str) -> int:
    value = fact(name).strip()
    return int(value) if value.isdigit() else 0


def words(name: str) -> list[str]:
    return [word for word in fact(name).split() if word]


def every_true(name: str) -> bool:
    values = words(name)
    return bool(values) and all(value == "true" for value in values)


def moment(value: str | None) -> datetime | None:
    """One Kubernetes timestamp, or nothing when it is absent or malformed.

    Kubernetes writes `2026-09-08T12:00:00Z`; `fromisoformat` accepts the `Z`
    from Python 3.11 onwards. A value it cannot read is `None` rather than an
    exception, because a missing readiness transition is a pod that is not ready
    -- which the reader refuses on its own terms -- and not a malformed document.
    """
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None


def replica(pod: dict) -> dict:
    status = pod.get("status", {})
    conditions = {
        condition.get("type"): condition
        for condition in status.get("conditions", []) or []
    }
    ready_condition = conditions.get("Ready", {})
    ready = ready_condition.get("status") == "True"
    started = moment(status.get("startTime"))
    became_ready = moment(ready_condition.get("lastTransitionTime"))
    if ready and started is not None and became_ready is not None:
        ready_after_ms = max(0, int((became_ready - started).total_seconds() * 1000))
    else:
        ready_after_ms = 0
    return {
        "podName": pod.get("metadata", {}).get("name", ""),
        "component": pod.get("metadata", {})
        .get("labels", {})
        .get("app.kubernetes.io/component", ""),
        "ready": ready,
        "readyAfterMs": ready_after_ms,
        "restarts": sum(
            int(state.get("restartCount", 0) or 0)
            for state in status.get("containerStatuses", []) or []
        ),
    }


pods = json.loads(fact("PODS_JSON") or '{"items": []}').get("items", [])
components = {fact("API_COMPONENT_NAME"), fact("RUNTIME_COMPONENT_NAME")}
# The `helm test` hook pod carries this release's instance label and is not a
# serving replica. Selecting by the two component labels the descriptor names
# keeps it out without this program having to know what a hook is.
replicas = sorted(
    (
        replica(pod)
        for pod in pods
        if pod.get("metadata", {}).get("labels", {}).get("app.kubernetes.io/component")
        in components
    ),
    key=lambda entry: entry["podName"],
)

release = json.loads(fact("RELEASE_JSON")) or [{}]
terraform = json.loads(fact("TERRAFORM")) if fact("TERRAFORM") else {}

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
    "replicas": replicas,
    "modelCache": {
        "claimName": fact("CLAIM_NAME"),
        "volumeReadOnly": every_true("VOLUME_READ_ONLY"),
        "mountReadOnly": every_true("MOUNT_READ_ONLY"),
        "initContainers": words("INIT_CONTAINERS"),
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
    json.dumps(document, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
    newline="\n",
)
FACTS_PYTHON

unset INFEROPS_FACT_PODS_JSON

inferops::log "cluster facts written to ${facts_rel}. They are host state, not evidence, and .artifacts/ is ignored by version control."

# --- each serving replica's own counters, before the request set -------------

# One snapshot of every ready serving replica's counters, read from that pod and
# from no other.
#
# The pod list comes out of the cluster facts this run already wrote rather than
# from a second query. The tool requires a snapshot to name exactly the ready
# serving replicas that document lists, and deriving it from the same file is
# what makes that true by construction instead of by two queries happening to
# agree.
runtime_counter_snapshot() {
  local label="$1"
  local pods pod port opened deadline release_deadline reading entries=""

  if ! pods="$(INFEROPS_FACTS_FILE="$(inferops::native_path "${facts_file}")" \
    INFEROPS_RUNTIME_COMPONENT="${descriptor_runtime_component}" inferops::python -c '
import json, os
from pathlib import Path

document = json.loads(
    Path(os.environ["INFEROPS_FACTS_FILE"]).read_text(encoding="utf-8")
)
component = os.environ["INFEROPS_RUNTIME_COMPONENT"]
for replica in document.get("replicas", []):
    if replica.get("component") == component and replica.get("ready"):
        print(replica.get("podName", ""))
')"; then
    inferops::fail "the serving replicas whose counters this certification reads could not be listed from ${facts_rel}."
  fi

  [ -n "${pods}" ] ||
    inferops::fail "no ready serving replica was listed in ${facts_rel}, so there is nothing to read counters from."

  while read -r pod; do
    [ -n "${pod}" ] || continue

    # The port the pod publishes, asked of the pod. A port named in this script
    # would be a second place the chart's container port is written down.
    if ! port="$(inferops::target_kubectl get "pod/${pod}" \
      -n "${INFEROPS_RELEASE_NAMESPACE}" \
      -o "jsonpath={.spec.containers[?(@.name=='runtime')].ports[0].containerPort}")"; then
      inferops::fail "could not read the port serving replica '${pod}' publishes its counters on."
    fi
    case "${port}" in
      '' | *[!0-9]*)
        inferops::fail "serving replica '${pod}' reports '${port}' as its container port, which is not a number."
        ;;
    esac

    if port_in_use "${INFEROPS_COUNTER_FORWARD_HOST}" "${INFEROPS_COUNTER_FORWARD_PORT}"; then
      inferops::fail "something is already listening on ${INFEROPS_COUNTER_FORWARD_HOST}:${INFEROPS_COUNTER_FORWARD_PORT}, which is the port this run reads each serving replica's counters through. This script will not read counters from a listener it did not start. Free the port, or set a different one, and run again."
    fi

    inferops::target_kubectl port-forward "pod/${pod}" \
      "${INFEROPS_COUNTER_FORWARD_PORT}:${port}" \
      -n "${INFEROPS_RELEASE_NAMESPACE}" \
      --address "${INFEROPS_COUNTER_FORWARD_HOST}" \
      >>"${diag_dir}/counter-forward.log" 2>&1 &
    forward_pid="$!"

    opened=0
    deadline=$((SECONDS + counter_forward_budget_ms / 1000))
    while [ "${SECONDS}" -lt "${deadline}" ]; do
      if ! kill -0 "${forward_pid}" 2>/dev/null; then
        forward_pid=""
        inferops::fail "the forward to serving replica '${pod}' exited before it accepted a connection. Its output is in .artifacts/kubernetes-multi-replica-certification/counter-forward.log."
      fi
      if port_in_use "${INFEROPS_COUNTER_FORWARD_HOST}" "${INFEROPS_COUNTER_FORWARD_PORT}"; then
        opened=1
        break
      fi
      sleep 1
    done
    if [ "${opened}" -ne 1 ]; then
      close_forward
      inferops::fail "the forward to serving replica '${pod}' did not accept a connection within $((counter_forward_budget_ms / 1000)) s."
    fi

    if ! reading="$(INFEROPS_COUNTER_POD="${pod}" \
      INFEROPS_COUNTER_HOST="${INFEROPS_COUNTER_FORWARD_HOST}" \
      INFEROPS_COUNTER_PORT="${INFEROPS_COUNTER_FORWARD_PORT}" \
      INFEROPS_COUNTER_PATH="${metrics_path}" \
      INFEROPS_COUNTER_NAMES="${decode_counter} ${predicted_counter} ${prompt_counter}" \
      inferops::python -c "${INFEROPS_COUNTER_PROGRAM}")"; then
      close_forward
      inferops::fail "serving replica '${pod}' did not answer for its counters at ${metrics_path}. The runtime publishes them under --metrics, which the chart passes whenever telemetry is enabled."
    fi
    close_forward

    # The next replica binds the same port, and `wait` returns when the process
    # is gone rather than when the kernel has released its listening socket. The
    # gap is normally imperceptible; waiting for the port to actually go quiet
    # turns a rare "address already in use" between two replicas into no event
    # at all, and it is bounded by the same budget as the forward itself.
    release_deadline=$((SECONDS + counter_forward_budget_ms / 1000))
    while [ "${SECONDS}" -lt "${release_deadline}" ]; do
      port_in_use "${INFEROPS_COUNTER_FORWARD_HOST}" "${INFEROPS_COUNTER_FORWARD_PORT}" ||
        break
      sleep 1
    done

    entries="${entries}${reading}
"
  done <<<"${pods}"

  printf '%s' "${entries}" >"${diag_dir}/runtime-counters-${label}.json"
}

inferops::section "Reading each serving replica's counters before the request set"

mkdir -p "${diag_dir}"
counters_before_at="$(now_rfc3339)"
runtime_counter_snapshot before
inferops::log "counters read from every ready serving replica at ${counters_before_at}."

# --- the request set, sent from inside the cluster ---------------------------

inferops::section "Sending ${request_count} requests through the API Service"

# The driver carries this release's name and instance labels and the
# `release-test` component label. That is not decoration: the release's
# default-deny NetworkPolicy selects every pod carrying the name and instance
# pair, the API's ingress rule admits pods carrying the same pair, and the
# release-test rule is the one egress allowance describing exactly this client --
# an in-cluster pod that talks to both Services. A pod labelled anything else is
# either denied on a policy-enforcing plugin or not described by the policy at
# all, and both are worse than reusing the identity the chart already wrote a
# rule for. On the accepted local cluster no policy is enforced at all
# (docs/proof/security/v1-s3-004-pr1-network-policy-enforcement.md), so this is
# about being correct where it would be, not about being permitted here.
#
# Every response body is written to the pod's own memory-backed scratch
# directory, matched for the markers a real answer carries, and never printed.
# The generated text is not this workflow's to retain, and a log line carrying it
# would put it in .artifacts/ and in `kubectl logs`.
# The body is built by a JSON writer rather than by string concatenation, and
# the model identifier in it is the one read out of the release's own ConfigMap
# rather than the one the descriptor names: a request naming a model the release
# was not configured with is refused by the API, and the assertion that the two
# agree belongs to the tool that reads both.
if ! request_body="$(INFEROPS_DRIVER_MODEL="${INFEROPS_FACT_MODEL_IDENTIFIER}" inferops::python -c '
import json, os, sys

print(
    json.dumps(
        {
            "model": os.environ["INFEROPS_DRIVER_MODEL"],
            "messages": [{"role": "user", "content": sys.argv[1]}],
        },
        separators=(",", ":"),
    )
)
' "${request_prompt}")"; then
  inferops::fail "the request body could not be built. Nothing was sent."
fi

# A body containing a single quote would end the quoted YAML scalar it is
# written into below and produce a manifest that is not the one this script
# meant. The committed prompt contains none, and this refuses the day one does
# rather than applying a malformed Job.
case "${request_body}" in
  *\'*) inferops::fail "the request body contains a single quote, which cannot be written into the driver manifest safely. Nothing was sent." ;;
esac

driver_url="http://${descriptor_api_service}.${INFEROPS_RELEASE_NAMESPACE}.svc.cluster.local:${descriptor_api_port}${request_path}"

distribution_started="$(now_ms)"


cat <<DRIVER | inferops::target_kubectl apply -n "${INFEROPS_RELEASE_NAMESPACE}" -f - >/dev/null
apiVersion: batch/v1
kind: Job
metadata:
  name: ${driver_name}
  namespace: ${INFEROPS_RELEASE_NAMESPACE}
  labels:
    app.kubernetes.io/name: inferops-llm
    app.kubernetes.io/instance: ${INFEROPS_RELEASE_NAME}
    app.kubernetes.io/component: ${driver_component}
    app.kubernetes.io/managed-by: inferops-certification
spec:
  backoffLimit: 0
  completions: 1
  parallelism: 1
  activeDeadlineSeconds: $((distribution_budget_ms / 1000))
  template:
    metadata:
      labels:
        app.kubernetes.io/name: inferops-llm
        app.kubernetes.io/instance: ${INFEROPS_RELEASE_NAME}
        app.kubernetes.io/component: ${driver_component}
    spec:
      restartPolicy: Never
      automountServiceAccountToken: false
      securityContext:
        runAsNonRoot: true
        runAsUser: 65534
        runAsGroup: 65534
        fsGroup: 65534
        seccompProfile:
          type: RuntimeDefault
      containers:
        - name: driver
          image: ${driver_image}
          imagePullPolicy: IfNotPresent
          securityContext:
            allowPrivilegeEscalation: false
            readOnlyRootFilesystem: true
            capabilities:
              drop:
                - ALL
          resources:
            requests:
              cpu: 10m
              memory: 16Mi
            limits:
              cpu: 100m
              memory: 64Mi
          volumeMounts:
            - name: scratch
              mountPath: /scratch
          env:
            - name: REQUEST_COUNT
              value: "${request_count}"
            - name: REQUEST_ID_PREFIX
              value: "${request_id_prefix}"
            - name: CORRELATION_ID
              value: "${request_correlation_id}"
            - name: REQUEST_TIMEOUT_SECONDS
              value: "$((request_timeout_ms / 1000))"
            - name: REQUEST_URL
              value: "${driver_url}"
            - name: REQUEST_BODY
              value: '${request_body}'
          command:
            - /bin/sh
            - -c
            - |
              # One connection per request, so that kube-proxy picks an endpoint
              # each time. A single client reusing one connection would send the
              # whole set to one replica and prove nothing about the Service.
              #
              # BusyBox sends its own Content-Type with --post-data. The one
              # named below states what the body actually is; this API reads no
              # request Content-Type at all, so neither is load-bearing and a run
              # must not be read as having established anything about it.
              set -u
              index=1
              while [ "\$index" -le "\$REQUEST_COUNT" ]; do
                id="\$(printf '%s-%03d' "\$REQUEST_ID_PREFIX" "\$index")"
                status=0
                : >/scratch/body.json
                : >/scratch/error.txt
                if wget -q -O /scratch/body.json \\
                  --header "Content-Type: application/json" \\
                  --header "X-InferOps-Request-ID: \$id" \\
                  --header "X-InferOps-Correlation-ID: \$CORRELATION_ID" \\
                  --post-data "\$REQUEST_BODY" \\
                  -T "\$REQUEST_TIMEOUT_SECONDS" \\
                  "\$REQUEST_URL" 2>/scratch/error.txt; then
                  status=200
                else
                  status="\$(grep -o 'HTTP/[0-9.]* [0-9][0-9][0-9]' /scratch/error.txt | head -n1 | grep -o '[0-9][0-9][0-9]\$' || true)"
                  [ -n "\$status" ] || status=0
                fi
                adapter="\$(grep -o '"adapterKind":"[a-zA-Z0-9_-]*"' /scratch/body.json | head -n1 | cut -d: -f2 | tr -d '"' || true)"
                model="\$(grep -o '"modelRef":"[a-zA-Z0-9._-]*"' /scratch/body.json | head -n1 | cut -d: -f2 | tr -d '"' || true)"
                prompt_tokens="\$(grep -o '"prompt_tokens":[0-9]*' /scratch/body.json | head -n1 | cut -d: -f2 || true)"
                completion_tokens="\$(grep -o '"completion_tokens":[0-9]*' /scratch/body.json | head -n1 | cut -d: -f2 || true)"
                total_tokens="\$(grep -o '"total_tokens":[0-9]*' /scratch/body.json | head -n1 | cut -d: -f2 || true)"
                printf 'inferops-request requestId=%s status=%s adapterKind=%s modelIdentifier=%s promptTokens=%s completionTokens=%s totalTokens=%s\n' \\
                  "\$id" "\$status" "\${adapter:-none}" "\${model:-none}" \\
                  "\${prompt_tokens:-0}" "\${completion_tokens:-0}" "\${total_tokens:-0}"
                index=\$((index + 1))
              done
              rm -f /scratch/body.json /scratch/error.txt
      volumes:
        - name: scratch
          emptyDir:
            medium: Memory
            sizeLimit: 16Mi
DRIVER

driver_created=1
inferops::log "request driver '${driver_name}' created."

# The Job has to exist and be scheduled before it can be waited on; `kubectl wait`
# against a condition on an object whose pod has not been created yet fails for a
# reason that is not the request set's.
inferops::target_kubectl wait --for=condition=Ready pod \
  -l "app.kubernetes.io/component=${driver_component},app.kubernetes.io/instance=${INFEROPS_RELEASE_NAME}" \
  -n "${INFEROPS_RELEASE_NAMESPACE}" --timeout="${INFEROPS_DRIVER_START_SECONDS}s" >/dev/null 2>&1 || true

# Polled rather than waited on, and the reason is worth stating because the
# obvious call is wrong here. `kubectl wait --for=condition=complete` watches for
# one condition becoming true and has no notion of "finished either way", so a
# Job that fails -- and this one is `backoffLimit: 0`, `restartPolicy: Never`, so
# any crash of the driver's shell fails it immediately -- is indistinguishable
# from one still legitimately running, and the call would block for the whole
# distribution budget. Half an hour to report a failure that happened in the
# first second is not a bounded failure; it is a hang with a timeout on it.
#
# Both terminal conditions are therefore asked for, and `Failed` covers the
# Job's own `activeDeadlineSeconds` as well as a crash. They are asked for in one
# query whose own status is kept, because an unanswered query is not a Job that
# is still running: swallowing an unreachable API server here would spend the
# whole distribution budget before saying anything, which is the failure this
# loop exists to avoid.
driver_conditions() {
  inferops::target_kubectl get "job/${driver_name}" -n "${INFEROPS_RELEASE_NAMESPACE}" \
    -o "jsonpath={range .status.conditions[*]}{.type}={.status} {end}"
}

driver_deadline=$((SECONDS + distribution_budget_ms / 1000))
driver_outcome=""
while [ "${SECONDS}" -lt "${driver_deadline}" ]; do
  if ! driver_state="$(driver_conditions)"; then
    inferops::fail "could not ask the request driver whether it had finished. An unanswered query is not a Job that is still running, and the release was left in place."
  fi
  case "${driver_state}" in
    *"Complete=True"*)
      driver_outcome="complete"
      break
      ;;
    *"Failed=True"*)
      driver_outcome="failed"
      break
      ;;
  esac
  sleep "${INFEROPS_DRIVER_POLL_SECONDS}"
done

case "${driver_outcome}" in
  complete) ;;
  failed)
    inferops::fail "the request driver failed. Its own output and the release's are in .artifacts/kubernetes-multi-replica-certification/, and the release was left in place. A driver that fails before sending anything and one that fails part-way through look different there: driver.log holds one line per request it completed."
    ;;
  *)
    inferops::fail "the request driver neither completed nor failed within $((distribution_budget_ms / 1000)) s. Its output is in .artifacts/kubernetes-multi-replica-certification/, and the release was left in place."
    ;;
esac

distribution_ms=$(($(now_ms) - distribution_started))
ended_at="$(now_rfc3339)"
inferops::log "the request set completed in ${distribution_ms} ms."

mkdir -p "${diag_dir}"

if ! driver_log="$(inferops::target_kubectl logs "job/${driver_name}" \
  -n "${INFEROPS_RELEASE_NAMESPACE}")"; then
  inferops::fail "could not read the request driver's own results. An unanswered query is not an empty request set."
fi
printf '%s\n' "${driver_log}" >"${diag_dir}/driver.log"

inferops::section "Reading each serving replica's counters after the request set"

counters_after_at="$(now_rfc3339)"
runtime_counter_snapshot after
inferops::log "counters read again at ${counters_after_at}; the window they bound is the one every serving-tier claim is made over."

mkdir -p "$(dirname "${counters_file}")"

INFEROPS_COUNTERS_BEFORE="$(cat "${diag_dir}/runtime-counters-before.json")"
INFEROPS_COUNTERS_AFTER="$(cat "${diag_dir}/runtime-counters-after.json")"
INFEROPS_COUNTERS_PATH="${metrics_path}"
INFEROPS_COUNTERS_BEFORE_AT="${counters_before_at}"
INFEROPS_COUNTERS_AFTER_AT="${counters_after_at}"
export INFEROPS_COUNTERS_BEFORE INFEROPS_COUNTERS_AFTER INFEROPS_COUNTERS_PATH \
  INFEROPS_COUNTERS_BEFORE_AT INFEROPS_COUNTERS_AFTER_AT

python - "$(inferops::native_path "${counters_file}")" <<'COUNTERS_DOCUMENT'
import json
import os
import sys
from pathlib import Path


def snapshot(text: str) -> list[dict]:
    """One JSON object per line, as the reader wrote them. Nothing is invented.

    A line that is not an object is a defect in the reader above rather than
    something to skip quietly, so it fails here instead of producing a snapshot
    that is short by one replica.
    """
    entries = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        entry = json.loads(line)
        if not isinstance(entry, dict):
            raise SystemExit(f"a counter reading is not an object: {line[:60]}")
        entries.append(entry)
    return entries


document = {
    "metricsPath": os.environ.get("INFEROPS_COUNTERS_PATH", ""),
    "readBeforeAt": os.environ.get("INFEROPS_COUNTERS_BEFORE_AT", ""),
    "readAfterAt": os.environ.get("INFEROPS_COUNTERS_AFTER_AT", ""),
    "before": snapshot(os.environ.get("INFEROPS_COUNTERS_BEFORE", "")),
    "after": snapshot(os.environ.get("INFEROPS_COUNTERS_AFTER", "")),
}

Path(sys.argv[1]).write_text(
    json.dumps(document, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
    newline="\n",
)
COUNTERS_DOCUMENT

unset INFEROPS_COUNTERS_BEFORE INFEROPS_COUNTERS_AFTER

inferops::log "serving runtime counters written to ${counters_rel}."

# The replicas' own records. Every InferOps API record is one JSON line on
# stderr carrying `k8s.pod.name` and `inferops.request.id`, so the pod is asked
# for its log one pod at a time -- a single selector-wide `kubectl logs` would
# interleave the pods and lose which one wrote which line.
if ! api_pods="$(inferops::target_kubectl get pods -n "${INFEROPS_RELEASE_NAMESPACE}" \
  -l "app.kubernetes.io/component=${descriptor_api_component},app.kubernetes.io/instance=${INFEROPS_RELEASE_NAME}" \
  -o name)"; then
  inferops::fail "could not list the platform API pods whose records the correlation is drawn from."
fi

: >"${diag_dir}/replica-records.log"
while read -r pod; do
  [ -n "${pod}" ] || continue
  inferops::target_kubectl logs "${pod}" -n "${INFEROPS_RELEASE_NAMESPACE}" \
    --container api >>"${diag_dir}/replica-records.log" 2>/dev/null || true
done <<<"${api_pods}"

INFEROPS_OBSERVE_DRIVER_LOG="$(cat "${diag_dir}/driver.log")"
INFEROPS_OBSERVE_RECORDS_LOG="$(cat "${diag_dir}/replica-records.log")"
INFEROPS_OBSERVE_STARTED_AT="${started_at}"
INFEROPS_OBSERVE_ENDED_AT="${ended_at}"
INFEROPS_OBSERVE_ELAPSED_MS="${distribution_ms}"
INFEROPS_OBSERVE_PREFIX="${request_id_prefix}"
export INFEROPS_OBSERVE_DRIVER_LOG INFEROPS_OBSERVE_RECORDS_LOG \
  INFEROPS_OBSERVE_STARTED_AT INFEROPS_OBSERVE_ENDED_AT \
  INFEROPS_OBSERVE_ELAPSED_MS INFEROPS_OBSERVE_PREFIX

mkdir -p "$(dirname "${observations_file}")"

python - "$(inferops::native_path "${observations_file}")" <<'OBSERVATIONS_PYTHON'
import json
import os
import sys
from pathlib import Path

# The record fields this correlation reads, spelled as the telemetry catalog
# publishes them. They are copied rather than imported because this program runs
# as a standalone script under whatever interpreter the host has; the
# architecture suite compares each one against inferops.telemetry.names, so a
# rename there fails the build rather than silently collecting nothing.
POD_NAME = "k8s.pod.name"
REQUEST_ID = "inferops.request.id"
EVENT = "inferops.event"
OUTCOME = "inferops.outcome"
HTTP_STATUS = "http.response.status_code"
ADAPTER_KIND = "inferops.adapter.kind"
MODEL_ID = "inferops.model.id"
MODEL_REVISION = "inferops.model.revision"
RUNTIME_ID = "inferops.runtime.id"
DURATION_MS = "inferops.duration.ms"
COMPLETED = "request.completed"


def driver_results(text: str) -> list[dict]:
    """One entry per line the driver printed, and nothing else.

    The driver prints one `inferops-request` line per request and the response
    bodies never reach its output. Any other line the image writes is ignored
    rather than parsed, so a BusyBox warning is not mistaken for a result.
    """
    results = []
    for line in text.splitlines():
        fields = line.split()
        if not fields or fields[0] != "inferops-request":
            continue
        entry = {}
        for field in fields[1:]:
            name, separator, value = field.partition("=")
            if separator:
                entry[name] = value
        results.append(
            {
                "requestId": entry.get("requestId", ""),
                "status": int(entry.get("status", "0") or 0),
                "adapterKind": entry.get("adapterKind", "none"),
                "modelIdentifier": entry.get("modelIdentifier", "none"),
                "promptTokens": int(entry.get("promptTokens", "0") or 0),
                "completionTokens": int(entry.get("completionTokens", "0") or 0),
                "totalTokens": int(entry.get("totalTokens", "0") or 0),
            }
        )
    return results


def replica_records(text: str, prefix: str) -> list[dict]:
    """The completion records the API replicas wrote about this request set.

    Bounded twice on purpose: only structured records naming a request this run
    sent are kept, and only the named fields are copied out of them. A record
    about someone else's request, a line that is not JSON, and every field the
    correlation does not read are all dropped here rather than carried into a
    committed record.
    """
    records = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("{"):
            continue
        try:
            document = json.loads(line)
        except ValueError:
            continue
        if not isinstance(document, dict):
            continue
        request_id = document.get(REQUEST_ID, "")
        if not isinstance(request_id, str) or not request_id.startswith(prefix):
            continue
        if document.get(EVENT) != COMPLETED:
            continue
        records.append(
            {
                "podName": document.get(POD_NAME, ""),
                "requestId": request_id,
                "event": document.get(EVENT, ""),
                "outcome": document.get(OUTCOME, ""),
                "httpStatus": int(document.get(HTTP_STATUS, 0) or 0),
                "adapterKind": document.get(ADAPTER_KIND, ""),
                "modelIdentifier": document.get(MODEL_ID, ""),
                "modelRevision": document.get(MODEL_REVISION, ""),
                "runtimeId": document.get(RUNTIME_ID, ""),
                "durationMs": int(float(document.get(DURATION_MS, 0) or 0)),
            }
        )
    return records


prefix = os.environ.get("INFEROPS_OBSERVE_PREFIX", "")
document = {
    "startedAt": os.environ.get("INFEROPS_OBSERVE_STARTED_AT", ""),
    "endedAt": os.environ.get("INFEROPS_OBSERVE_ENDED_AT", ""),
    "elapsedMs": int(os.environ.get("INFEROPS_OBSERVE_ELAPSED_MS", "0") or 0),
    "requests": driver_results(os.environ.get("INFEROPS_OBSERVE_DRIVER_LOG", "")),
    "records": replica_records(
        os.environ.get("INFEROPS_OBSERVE_RECORDS_LOG", ""), prefix
    ),
}

Path(sys.argv[1]).write_text(
    json.dumps(document, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
    newline="\n",
)
OBSERVATIONS_PYTHON

unset INFEROPS_OBSERVE_DRIVER_LOG INFEROPS_OBSERVE_RECORDS_LOG

inferops::log "observations written to ${observations_rel}."

# --- the assertions, before anything is torn down ----------------------------

inferops::section "Certifying the multi-replica path"

# Deliberately before the teardown: a failed assertion has to leave the release
# standing, because the pods are the only place left to look.
(cd "${INFEROPS_ROOT}" && python -m "${INFEROPS_MULTI_MODULE}" certify \
  --confirm-real-kubernetes)

# --- teardown ----------------------------------------------------------------

inferops::section "Removing the request driver"

# Not swallowed on this path. A driver Job still in the namespace when the
# residue check runs would be counted as the release's own residue, and the run
# would fail blaming the teardown for this workflow's artifact.
if ! remove_driver; then
  inferops::fail "the request driver Job '${driver_name}' was not removed from '${INFEROPS_RELEASE_NAMESPACE}' within ${INFEROPS_DRIVER_DELETE_SECONDS} s. It carries this release's instance label, so the residue check after the uninstall would report it as an object of the release surviving its own uninstall -- which would be the wrong diagnosis. Remove the Job by hand and rerun; the release is still installed."
fi
driver_removed="true"

inferops::section "Uninstalling the release"

uninstall_started="$(now_ms)"
inferops::target_helm uninstall "${INFEROPS_RELEASE_NAME}" \
  --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
  --wait \
  --timeout "$((uninstall_budget_ms / 1000))s"
uninstall_ms=$(($(now_ms) - uninstall_started))

inferops::section "Residue"

# Asked repeatedly inside the uninstall budget rather than once, for the reason
# scripts/environment/kubernetes-certification.sh states beside its own residue
# check: `helm uninstall --wait` waits for the objects Helm deleted itself, and a
# Deployment's pods are removed afterwards by the garbage collector on the
# controller manager's schedule. Asking the instant Helm returns counts
# terminating pods as residue -- and here that number goes into the record, so an
# unbounded answer would publish a residue figure that was never true.
residue_deadline=$((SECONDS + uninstall_budget_ms / 1000))
while :; do
  if ! remaining="$(inferops::target_kubectl get \
    deployments,replicasets,services,configmaps,serviceaccounts,pods,networkpolicies,jobs,pvc \
    -n "${INFEROPS_RELEASE_NAMESPACE}" -l "${INFEROPS_RELEASE_SELECTOR}" -o name)"; then
    inferops::fail "could not ask what survived the uninstall. An unanswered query is not an empty result."
  fi
  [ -n "${remaining}" ] || break
  [ "${SECONDS}" -lt "${residue_deadline}" ] || break
  sleep 2
done
residue_objects="$(printf '%s' "${remaining}" | grep -c . || true)"
if [ -n "${remaining}" ]; then
  printf '%s\n' "${remaining}"
fi

helm_release_absent="true"
if inferops::target_helm status "${INFEROPS_RELEASE_NAME}" \
  --namespace "${INFEROPS_RELEASE_NAMESPACE}" >/dev/null 2>&1; then
  helm_release_absent="false"
fi

namespace_survives="true"
inferops::target_kubectl get namespace "${INFEROPS_RELEASE_NAMESPACE}" >/dev/null 2>&1 ||
  namespace_survives="false"

if ! claims_after="$(inferops::claim_count)"; then
  inferops::fail "could not count the persistent volume claims after uninstalling. An unanswered query is not an empty result."
fi

INFEROPS_CLEANUP_RELEASE_UNINSTALLED="true"
INFEROPS_CLEANUP_DRIVER_REMOVED="${driver_removed}"
INFEROPS_CLEANUP_RESIDUE="${residue_objects}"
INFEROPS_CLEANUP_HELM_ABSENT="${helm_release_absent}"
INFEROPS_CLEANUP_NAMESPACE="${namespace_survives}"
INFEROPS_CLEANUP_CLAIMS_BEFORE="${claims_before}"
INFEROPS_CLEANUP_CLAIMS_AFTER="${claims_after}"
INFEROPS_CLEANUP_UNINSTALL_MS="${uninstall_ms}"
export INFEROPS_CLEANUP_RELEASE_UNINSTALLED INFEROPS_CLEANUP_DRIVER_REMOVED \
  INFEROPS_CLEANUP_RESIDUE INFEROPS_CLEANUP_HELM_ABSENT \
  INFEROPS_CLEANUP_NAMESPACE INFEROPS_CLEANUP_CLAIMS_BEFORE \
  INFEROPS_CLEANUP_CLAIMS_AFTER INFEROPS_CLEANUP_UNINSTALL_MS

mkdir -p "$(dirname "${cleanup_file}")"

python - "$(inferops::native_path "${cleanup_file}")" <<'CLEANUP_PYTHON'
import json
import os
import sys
from pathlib import Path


def flag(name: str) -> bool:
    return os.environ.get(f"INFEROPS_CLEANUP_{name}", "") == "true"


def number(name: str) -> int:
    value = os.environ.get(f"INFEROPS_CLEANUP_{name}", "").strip()
    return int(value) if value.isdigit() else 0


document = {
    "releaseUninstalled": flag("RELEASE_UNINSTALLED"),
    "driverRemoved": flag("DRIVER_REMOVED"),
    "residueObjects": number("RESIDUE"),
    "helmReleaseAbsent": flag("HELM_ABSENT"),
    "namespaceSurvives": flag("NAMESPACE"),
    "claimsBefore": number("CLAIMS_BEFORE"),
    "claimsAfter": number("CLAIMS_AFTER"),
    "uninstallMs": number("UNINSTALL_MS"),
}

Path(sys.argv[1]).write_text(
    json.dumps(document, indent=2, sort_keys=True) + "\n",
    encoding="utf-8",
    newline="\n",
)
CLEANUP_PYTHON

inferops::section "Recording the cleanup outcome"

# The record is written a second time rather than mutated: the cleanup outcome
# cannot exist before the teardown, and the assertions above may not run after
# it. What the second write adds is the cleanup member, and the assertions over
# it are the same tool's.
(cd "${INFEROPS_ROOT}" && python -m "${INFEROPS_MULTI_MODULE}" record-cleanup \
  --confirm-real-kubernetes)

inferops::section "Result"
inferops::log "the release installed with ${api_replicas} API replicas and ${runtime_replicas} serving runtime replicas, every replica became model-ready, and ${request_count} real requests succeeded through the API Service."
inferops::log "the successful requests correlate to more than one platform API replica, and every serving runtime replica's own decode counter advanced while they ran. No request is attributed to a serving replica; the serving claim is per replica over the window the two counter reads bound."
inferops::log "record        .cache/inferops/certification/k8s-multi-replica-inference.json (labelled local real Kubernetes)"
inferops::log "the namespace and the model cache claim survived. Reclaiming them is scripts/environment/terraform-prerequisites.sh destroy --confirm, and nothing here does it for you."
