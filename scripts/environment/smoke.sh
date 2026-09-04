#!/usr/bin/env bash
# Deploys the hello-world workload, waits for it to become ready, and asserts
# that a request made from inside the cluster reaches it through its Service.
#
# On failure it collects diagnostics into .artifacts/ and leaves the workload in
# place for inspection; it does not tear down the evidence of its own failure.
#
# Usage: scripts/environment/smoke.sh

# shellcheck source=scripts/environment/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

[ "$#" -eq 0 ] ||
  inferops::fail "expected no arguments, got $#: $*. Usage: smoke.sh"

inferops::require_cmd kubectl
inferops::assert_target_cluster

manifest_dir="${INFEROPS_ROOT}/deploy/smoke"
diag_dir="${INFEROPS_ARTIFACT_DIR}/smoke"

collect_diagnostics() {
  mkdir -p "${diag_dir}"
  inferops::warn "collecting diagnostics into .artifacts/smoke/"
  inferops::kubectl get all -n "${INFEROPS_NAMESPACE}" -o wide >"${diag_dir}/get-all.txt" 2>&1 || true
  inferops::kubectl describe all -n "${INFEROPS_NAMESPACE}" >"${diag_dir}/describe-all.txt" 2>&1 || true
  inferops::kubectl get events -n "${INFEROPS_NAMESPACE}" \
    --sort-by=.lastTimestamp >"${diag_dir}/events.txt" 2>&1 || true
  inferops::kubectl logs -n "${INFEROPS_NAMESPACE}" \
    -l app.kubernetes.io/name=hello-world --tail=200 >"${diag_dir}/hello-world.log" 2>&1 || true
  inferops::kubectl logs -n "${INFEROPS_NAMESPACE}" \
    job/hello-world-verify --tail=200 >"${diag_dir}/verify.log" 2>&1 || true
  inferops::kubectl get nodes -o yaml >"${diag_dir}/nodes.yaml" 2>&1 || true
}

on_exit() {
  local rc=$?
  if [ "${rc}" -ne 0 ]; then
    collect_diagnostics
  fi
  exit "${rc}"
}

# On EXIT rather than on ERR, so that a deliberate failure — an assertion this
# script raises itself — collects diagnostics just as a failing command does.
# An ERR trap alone misses every `exit` path, and those are most of the
# interesting ones.
trap on_exit EXIT

inferops::section "Applying the hello-world workload"

inferops::kubectl apply -f "$(inferops::native_path "${manifest_dir}/hello-world.yaml")"

inferops::section "Waiting for readiness"

# Bounded. A hung rollout must fail the script, not hang the contributor.
inferops::kubectl rollout status deployment/hello-world \
  -n "${INFEROPS_NAMESPACE}" --timeout=180s
inferops::kubectl wait --for=condition=Available deployment/hello-world \
  -n "${INFEROPS_NAMESPACE}" --timeout=60s

inferops::kubectl get pods,svc,endpointslices -n "${INFEROPS_NAMESPACE}" -o wide

inferops::section "Verifying the Service from inside the cluster"

# A Job left over from a previous run would otherwise be immutable and reject
# this apply.
inferops::kubectl delete job hello-world-verify \
  -n "${INFEROPS_NAMESPACE}" --ignore-not-found=true --wait=true

inferops::kubectl apply -f "$(inferops::native_path "${manifest_dir}/verify-job.yaml")"

# `kubectl wait` watches one condition at a time, so waiting for Complete alone
# would sit through the entire timeout before noticing a Job that had already
# failed. Poll for either terminal condition and stop at whichever arrives.
verify_deadline=$((SECONDS + 180))
verify_state=""
while [ "${SECONDS}" -lt "${verify_deadline}" ]; do
  verify_state="$(inferops::kubectl get job hello-world-verify \
    -n "${INFEROPS_NAMESPACE}" \
    -o jsonpath='{.status.conditions[?(@.type=="Complete")].status}/{.status.conditions[?(@.type=="Failed")].status}' \
    2>/dev/null || true)"
  case "${verify_state}" in
    True/*) break ;;
    */True) inferops::fail "the verification job failed; the Service did not answer as expected." ;;
  esac
  sleep 2
done

[ "${verify_state%%/*}" = "True" ] ||
  inferops::fail "the verification job did not reach a terminal state within the deadline."

verify_output="$(inferops::kubectl logs -n "${INFEROPS_NAMESPACE}" job/hello-world-verify)"
printf '%s\n' "${verify_output}"

# The Job's own exit status already gates this, but asserting on the marker here
# means a Job that somehow completes without running the assertion still fails.
printf '%s' "${verify_output}" | grep -q 'SMOKE_ASSERTION_PASSED' ||
  inferops::fail "the verification job completed without reporting a passing assertion."

inferops::section "Idle resource use"

# Best-effort: metrics-server is not installed in kind, so pod-level metrics are
# expected to be unavailable. The engine-level figures below are the real ones.
if inferops::kubectl top nodes >/dev/null 2>&1; then
  inferops::kubectl top nodes
  inferops::kubectl top pods -A
else
  inferops::log "in-cluster metrics are unavailable (no metrics-server in kind); using engine statistics instead."
fi

if command -v docker >/dev/null 2>&1; then
  docker stats --no-stream --format 'table {{.Name}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.MemPerc}}' ||
    inferops::warn "could not read engine statistics."
fi

inferops::section "Result"

inferops::log "hello-world smoke test passed on cluster '${INFEROPS_CLUSTER_NAME}'."
