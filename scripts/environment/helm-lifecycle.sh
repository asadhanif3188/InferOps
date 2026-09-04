#!/usr/bin/env bash
# Installs the InferOps LLM release, tests it, upgrades it, rolls the upgrade
# back, uninstalls it, and asserts that the uninstall left the prerequisites and
# nothing else.
#
# This is the answer to "does the chart install and uninstall". Rendering it does
# not answer that, and neither does a lint: a rollout that Kubernetes reports as
# successful and a Service that selects nothing look identical from outside until
# something asks.
#
# Creates: one Helm release named by INFEROPS_RELEASE_NAME in
# INFEROPS_RELEASE_NAMESPACE, and — only if it does not already exist — that
# namespace. Removes: the release. It never removes the namespace and never
# removes a PersistentVolumeClaim; both are prerequisites that outlive a release
# by design, and asserting that they survived is one of the checks below.
#
# The namespace is Terraform's (docs/architecture/resource-ownership.md).
# V1-S3-005 writes that Terraform. Until it does, this script creates the
# namespace itself, labels it as the prerequisite it stands in for, and says so
# in its output — rather than passing `--create-namespace`, which would hand the
# same resource to Helm and make the release's uninstall delete it.
#
# On failure it collects diagnostics into .artifacts/ and leaves the release in
# place for inspection.
#
# Usage: scripts/environment/helm-lifecycle.sh --values PATH [--keep-namespace]

# shellcheck source=scripts/environment/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

values_file=""

while [ "$#" -gt 0 ]; do
  case "$1" in
    --values)
      [ "$#" -ge 2 ] || inferops::fail "--values needs a path. Usage: helm-lifecycle.sh --values PATH"
      values_file="$2"
      shift 2
      ;;
    --keep-namespace)
      # Accepted and ignored: the namespace is never removed by this script.
      # The flag exists so that a contributor who reaches for it is told that,
      # rather than discovering it by reading the source.
      inferops::log "--keep-namespace is the only behaviour: this script never removes a namespace."
      shift
      ;;
    *)
      inferops::fail "unknown argument '$1'. Usage: helm-lifecycle.sh --values PATH [--keep-namespace]"
      ;;
  esac
done

[ -n "${values_file}" ] ||
  inferops::fail "--values is required. The chart's shipped defaults select no serving profile and are refused on purpose, so there is no values file this script could reasonably assume. See docs/environment/helm-release-lifecycle.md."

[ -f "${values_file}" ] ||
  inferops::fail "no such values file: ${values_file}"

inferops::require_cmd helm
inferops::require_cmd kubectl
inferops::require_engine
inferops::assert_target_cluster

# Not input validation: the namespace is a readonly constant in lib.sh and
# nothing here can change it, so this branch cannot be taken today. It is here
# for the edit that changes that constant -- ADR 0001 (D5) makes the prefix the
# isolation rule, and the chart's own refusal only fires once a render has been
# reached. Stated plainly because a check that reads like a guard on operator
# input and is not one is worse than no check at all.
case "${INFEROPS_RELEASE_NAMESPACE}" in
  inferops-*) ;;
  *) inferops::fail "the release namespace must be prefixed 'inferops-' (ADR 0001 D5). It is '${INFEROPS_RELEASE_NAMESPACE}', which means the constant in lib.sh was changed without this rule being reconsidered." ;;
esac

chart_dir="${INFEROPS_ROOT}/${INFEROPS_CHART_PATH}"
[ -d "${chart_dir}" ] || inferops::fail "no chart at ${INFEROPS_CHART_PATH}"

chart_path="$(inferops::native_path "${chart_dir}")"
values_path="$(inferops::native_path "$(cd "$(dirname "${values_file}")" && pwd)/$(basename "${values_file}")")"

diag_dir="${INFEROPS_ARTIFACT_DIR}/helm-lifecycle"

# The marker an upgrade sets and a rollback has to remove. `telemetry.serviceVersion`
# is used because it is a free string that reaches the ConfigMap and therefore
# the pod-template checksum: an upgrade that set something inert would produce a
# revision Helm records and Kubernetes never acts on, and rolling that back would
# prove nothing about whether the workload followed.
readonly UPGRADE_MARKER="lifecycle-upgrade-probe"

collect_diagnostics() {
  mkdir -p "${diag_dir}"
  inferops::warn "collecting diagnostics into .artifacts/helm-lifecycle/"
  inferops::helm list --namespace "${INFEROPS_RELEASE_NAMESPACE}" >"${diag_dir}/releases.txt" 2>&1 || true
  inferops::helm history "${INFEROPS_RELEASE_NAME}" \
    --namespace "${INFEROPS_RELEASE_NAMESPACE}" >"${diag_dir}/history.txt" 2>&1 || true
  inferops::kubectl get all,configmap,serviceaccount,pvc \
    -n "${INFEROPS_RELEASE_NAMESPACE}" -o wide >"${diag_dir}/get-all.txt" 2>&1 || true
  inferops::kubectl describe pods -n "${INFEROPS_RELEASE_NAMESPACE}" >"${diag_dir}/describe-pods.txt" 2>&1 || true
  inferops::kubectl get events -n "${INFEROPS_RELEASE_NAMESPACE}" \
    --sort-by=.lastTimestamp >"${diag_dir}/events.txt" 2>&1 || true
  inferops::kubectl logs -n "${INFEROPS_RELEASE_NAMESPACE}" \
    -l "${INFEROPS_RELEASE_SELECTOR}" --all-containers --tail=200 >"${diag_dir}/release.log" 2>&1 || true
}

on_exit() {
  local rc=$?
  if [ "${rc}" -ne 0 ]; then
    collect_diagnostics
    inferops::warn "the release was left in place. Remove it with: helm uninstall ${INFEROPS_RELEASE_NAME} --namespace ${INFEROPS_RELEASE_NAMESPACE}"
  fi
  exit "${rc}"
}

trap on_exit EXIT

# --- the prerequisite layer, and what stands in for it ----------------------

inferops::section "Prerequisites"

if inferops::kubectl get namespace "${INFEROPS_RELEASE_NAMESPACE}" >/dev/null 2>&1; then
  inferops::log "namespace '${INFEROPS_RELEASE_NAMESPACE}' already exists; reusing it."
else
  inferops::log "creating namespace '${INFEROPS_RELEASE_NAMESPACE}'."
  inferops::log "This stands in for Terraform, which V1-S3-005 has not written yet."
  inferops::kubectl create namespace "${INFEROPS_RELEASE_NAMESPACE}"
  # Labelled as a prerequisite rather than a release, which is the distinction
  # the ownership document's scoped-teardown resolution turns on: a sweep that
  # matched only `part-of` would reach this namespace as if a release owned it.
  inferops::kubectl label namespace "${INFEROPS_RELEASE_NAMESPACE}" \
    "app.kubernetes.io/part-of=inferops" \
    "inferops.io/lifecycle=prerequisite"
fi

# Counted before anything is installed, and compared after everything is
# removed. A claim is the one thing in this namespace that must survive an
# uninstall, and counting is how that is asserted without this script needing to
# know which claim a values file named.
#
# Asked through a function that separates "the answer is none" from "the question
# could not be asked". Discarding stderr and swallowing the exit status would make
# an API server that refused the query indistinguishable from a namespace with no
# claims -- and the residue assertions below would then certify a clean removal
# on the strength of a question nobody answered. That is the same reading
# verify-clean.sh already refuses for the cluster: a check that cannot fail is
# worse than no check.
# It reports on stderr and returns non-zero rather than calling inferops::fail,
# and the callers below never nest it inside another substitution. Both of those
# are load-bearing: `exit` inside `$( )` ends the subshell, and in
# `outer "$(inner)"` a failing inner substitution does not reach the assignment's
# status -- so a nested call would print the diagnosis and carry on, which is the
# failure this function exists to prevent wearing a different hat.
inferops::release_objects() {
  local kinds="$1"
  local output
  if ! output="$(inferops::kubectl get "${kinds}" \
    -n "${INFEROPS_RELEASE_NAMESPACE}" "${@:2}" -o name)"; then
    inferops::warn "the query for ${kinds} in '${INFEROPS_RELEASE_NAMESPACE}' did not answer."
    return 1
  fi
  printf '%s' "${output}"
}

inferops::count_lines() {
  # `grep -c .` exits non-zero on no matches, which is the count being zero
  # rather than a failure, so only that status is absorbed.
  printf '%s' "$1" | grep -c . || true
}

# The unanswered-query message names what it could not establish, because a
# script that stops here has proved nothing either way.
readonly UNANSWERED="An unanswered query is not an empty result, and every assertion about what this release left behind depends on the difference."

if ! claims_before_raw="$(inferops::release_objects pvc)"; then
  inferops::fail "could not count the persistent volume claims before installing. ${UNANSWERED}"
fi
claims_before="$(inferops::count_lines "${claims_before_raw}")"
inferops::log "persistent volume claims present before install: ${claims_before}"

if inferops::helm status "${INFEROPS_RELEASE_NAME}" \
  --namespace "${INFEROPS_RELEASE_NAMESPACE}" >/dev/null 2>&1; then
  # Silently upgrading an existing release would make this script's result mean
  # something different from what it says: it reports on an install.
  inferops::fail "release '${INFEROPS_RELEASE_NAME}' already exists in '${INFEROPS_RELEASE_NAMESPACE}'. Remove it first: helm uninstall ${INFEROPS_RELEASE_NAME} --namespace ${INFEROPS_RELEASE_NAMESPACE}"
fi

# --- install ----------------------------------------------------------------

inferops::section "Installing"

# --wait makes readiness part of this command rather than something the next
# step has to discover. The timeout has to outlast a model load: the measured
# range on the reference host was 133,515 ms to 358,735 ms, and a timeout below
# that would report a failure that is a slow load.
#
# --create-namespace is deliberately absent and must stay absent. It would make
# Helm an owner of the namespace above, and this release's uninstall would then
# delete a prerequisite.
inferops::helm install "${INFEROPS_RELEASE_NAME}" "${chart_path}" \
  --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
  --values "${values_path}" \
  --wait \
  --timeout 15m

inferops::kubectl get deployments,services,configmaps,serviceaccounts,pods \
  -n "${INFEROPS_RELEASE_NAMESPACE}" -l "${INFEROPS_RELEASE_SELECTOR}" -o wide

# --- does it answer ---------------------------------------------------------

inferops::section "Testing the installed release"

inferops::helm test "${INFEROPS_RELEASE_NAME}" \
  --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
  --logs \
  --timeout 5m

# --- upgrade ----------------------------------------------------------------

inferops::section "Upgrading"

inferops::helm upgrade "${INFEROPS_RELEASE_NAME}" "${chart_path}" \
  --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
  --values "${values_path}" \
  --set "telemetry.serviceVersion=${UPGRADE_MARKER}" \
  --wait \
  --timeout 15m

inferops::helm test "${INFEROPS_RELEASE_NAME}" \
  --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
  --logs \
  --timeout 5m

configured="$(inferops::kubectl get configmap \
  -n "${INFEROPS_RELEASE_NAMESPACE}" -l "${INFEROPS_RELEASE_SELECTOR}" \
  -o jsonpath='{.items[*].data.INFEROPS_SERVICE_VERSION}')"
[ "${configured}" = "${UPGRADE_MARKER}" ] ||
  inferops::fail "the upgrade did not reach the rendered configuration: expected '${UPGRADE_MARKER}', found '${configured}'. A revision Helm recorded and the cluster did not apply is not an upgrade."

# --- rollback ---------------------------------------------------------------

inferops::section "Rolling back to revision 1"

# The property being checked is that a rollback is possible at all. A
# Deployment's selector is immutable after creation, so a chart whose selector
# varied with anything a values file can change would make revision 2 a new
# object rather than an update, and revision 1 unreachable.
inferops::helm rollback "${INFEROPS_RELEASE_NAME}" 1 \
  --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
  --wait \
  --timeout 15m

inferops::helm test "${INFEROPS_RELEASE_NAME}" \
  --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
  --logs \
  --timeout 5m

configured="$(inferops::kubectl get configmap \
  -n "${INFEROPS_RELEASE_NAMESPACE}" -l "${INFEROPS_RELEASE_SELECTOR}" \
  -o jsonpath='{.items[*].data.INFEROPS_SERVICE_VERSION}')"
[ "${configured}" != "${UPGRADE_MARKER}" ] ||
  inferops::fail "the rollback left the upgrade's configuration in place: INFEROPS_SERVICE_VERSION is still '${UPGRADE_MARKER}'."

inferops::helm history "${INFEROPS_RELEASE_NAME}" \
  --namespace "${INFEROPS_RELEASE_NAMESPACE}"

# --- uninstall --------------------------------------------------------------

inferops::section "Uninstalling"

inferops::helm uninstall "${INFEROPS_RELEASE_NAME}" \
  --namespace "${INFEROPS_RELEASE_NAMESPACE}" \
  --wait \
  --timeout 10m

# --- what is left -----------------------------------------------------------

inferops::section "Residue"

residue=0
report_residue() {
  inferops::warn "$1"
  residue=$((residue + 1))
}

# Everything Helm installs carries the release's instance label, so this is the
# question "did uninstall remove the release" asked of the cluster rather than
# of Helm's own bookkeeping.
if ! remaining="$(inferops::release_objects \
  deployments,replicasets,services,configmaps,serviceaccounts,pods,pvc \
  -l "${INFEROPS_RELEASE_SELECTOR}")"; then
  inferops::fail "could not ask what survived the uninstall. ${UNANSWERED}"
fi
if [ -n "${remaining}" ]; then
  report_residue "objects labelled '${INFEROPS_RELEASE_SELECTOR}' survived the uninstall:"
  printf '%s\n' "${remaining}"
else
  inferops::log "no object carrying the release label remains."
fi

if inferops::helm status "${INFEROPS_RELEASE_NAME}" \
  --namespace "${INFEROPS_RELEASE_NAMESPACE}" >/dev/null 2>&1; then
  report_residue "helm still reports a release named '${INFEROPS_RELEASE_NAME}'."
else
  inferops::log "helm reports no release named '${INFEROPS_RELEASE_NAME}'."
fi

# The other half, and the one a teardown script is more likely to get wrong: the
# prerequisites have to be *there*. An uninstall that removed them would be a
# release that owned what it only referenced.
if inferops::kubectl get namespace "${INFEROPS_RELEASE_NAMESPACE}" >/dev/null 2>&1; then
  inferops::log "namespace '${INFEROPS_RELEASE_NAMESPACE}' survived, as a prerequisite must."
else
  report_residue "namespace '${INFEROPS_RELEASE_NAMESPACE}' was removed by an uninstall. It is a prerequisite and must outlive the release."
fi

if ! claims_after_raw="$(inferops::release_objects pvc)"; then
  inferops::fail "could not count the persistent volume claims after uninstalling. ${UNANSWERED}"
fi
claims_after="$(inferops::count_lines "${claims_after_raw}")"
if [ "${claims_after}" = "${claims_before}" ]; then
  inferops::log "persistent volume claims: ${claims_after}, unchanged by the release."
else
  report_residue "the claim count changed across the release: ${claims_before} before, ${claims_after} after. This chart must neither create nor delete a claim."
fi

[ "${residue}" -eq 0 ] ||
  inferops::fail "${residue} residue finding(s). The release did not remove cleanly, or removed something it does not own."

inferops::section "Result"
inferops::log "install, test, upgrade, test, rollback, test, uninstall: all succeeded."
inferops::log "the namespace and every claim survived; no release object did."
