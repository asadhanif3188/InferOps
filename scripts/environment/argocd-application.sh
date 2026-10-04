#!/usr/bin/env bash
# Applies, verifies, and removes the one Argo CD Application that ADR 0019 decided,
# and the project that holds it.
#
# The cluster already exists and is the operator's. Argo CD is already installed
# by scripts/environment/argocd-bootstrap.sh. The platform namespace and the model
# cache claim already exist and are Terraform's. This script creates none of them.
#
# The two objects are committed in infra/argocd/. The constants below restate
# their names, and tests/architecture/test_argocd_application.py fails when a
# constant and a manifest differ.
#
# apply    Applies the project, then the Application, with server-side apply. It
#          adds two things to the committed bytes: an annotation that records the
#          SHA-256 of the committed file, and the API image digest as one Helm
#          parameter. Waits a bounded time until Argo CD reports that it applied
#          the revision that `main` names.
# verify   Reads the two objects and changes nothing in the cluster. Compares
#          the live sync policy, source, and destination with the decision, and
#          prints the revision and the states that Argo CD reports.
# remove   Deletes the Application with a cascade, so that Argo CD deletes the
#          workload objects it applied. Then deletes the project. The namespace
#          and the claim stay.
#
# Every refusal below comes before the first mutation.
#
#   target-not-selected-or-not-verified   inferops::resolve_target
#   api-image-digest-not-given            apply
#   argocd-not-installed-by-the-bootstrap apply, verify, remove
#   destination-not-prepared              apply
#   helm-release-present                  apply
#   foreign-argocd-custom-resource        apply, remove
#   application-controller-not-ready      remove
#
# What this script reports is what Argo CD reports: a revision, a sync state, and
# a health state. None of them is a caller outcome. A request that a caller sent
# is the only evidence that the workload serves one.
#
# Does not touch: the cluster, the Argo CD installation, the platform namespace,
# a claim, a Helm release, or the operator's own kubeconfig. It reads no Secret
# value.
#
# Usage: scripts/environment/argocd-application.sh apply --api-image-digest sha256:HEX
#        scripts/environment/argocd-application.sh verify
#        scripts/environment/argocd-application.sh remove --confirm

# shellcheck source=scripts/environment/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

readonly USAGE="Usage: argocd-application.sh apply --api-image-digest sha256:HEX | verify | remove --confirm"

# --- The two objects --------------------------------------------------------

readonly INFEROPS_GITOPS_PROJECT_MANIFEST="infra/argocd/workloads-project.yaml"
readonly INFEROPS_GITOPS_APPLICATION_MANIFEST="infra/argocd/local-docker-desktop-support-assistant.yaml"
readonly INFEROPS_GITOPS_PROJECT_NAME="inferops-workloads"
readonly INFEROPS_GITOPS_APPLICATION_NAME="local-docker-desktop-support-assistant"

# What the Application must say. `verify` compares the live object with these.
readonly INFEROPS_GITOPS_REPOSITORY_URL="https://github.com/asadhanif3188/InferOps.git"
readonly INFEROPS_GITOPS_TARGET_REVISION="main"
readonly INFEROPS_GITOPS_DESTINATION_SERVER="https://kubernetes.default.svc"
readonly INFEROPS_GITOPS_MODEL_CACHE_CLAIM="inferops-model-cache"

# --- The marker -------------------------------------------------------------

# The committed manifests carry the label. The procedure adds the annotation in
# the same request, so an object of its own always holds both.
readonly INFEROPS_GITOPS_MARKER_LABEL="inferops.io/lifecycle"
readonly INFEROPS_GITOPS_MARKER_VALUE="reconciliation"
readonly INFEROPS_GITOPS_PIN_ANNOTATION="inferops.io/argocd-application-manifest-sha256"

# --- The Argo CD installation this procedure requires -----------------------

readonly INFEROPS_ARGOCD_NAMESPACE="argocd"
readonly INFEROPS_ARGOCD_MARKER_LABEL="inferops.io/lifecycle"
readonly INFEROPS_ARGOCD_MARKER_VALUE="bootstrap"
readonly INFEROPS_ARGOCD_PIN_ANNOTATION="inferops.io/argocd-manifest-sha256"
readonly INFEROPS_ARGOCD_CONTROLLER="argocd-application-controller"
readonly INFEROPS_ARGOCD_KINDS="applications.argoproj.io applicationsets.argoproj.io appprojects.argoproj.io"

# --- The mechanism ----------------------------------------------------------

readonly INFEROPS_GITOPS_FIELD_MANAGER="inferops-argocd-application"
# The finalizer that makes a deletion of the Application delete what it applied.
readonly INFEROPS_GITOPS_CASCADE_FINALIZER="resources-finalizer.argocd.argoproj.io"
readonly INFEROPS_GITOPS_DIGEST_PARAMETER="api.image.digest"

# The kinds the project lets the Application manage, and the pods and replica
# sets that Kubernetes derives from them. The removal asks for all of them.
readonly INFEROPS_GITOPS_RESIDUE_KINDS="deployments,replicasets,pods,jobs,services,configmaps,serviceaccounts,networkpolicies,roles,rolebindings"

# One budget for the first sync. It must outlast the acquisition hook, which
# hashes the model artifact, and one fetch of the repository.
readonly SYNC_BUDGET_SECONDS=1200
# One budget for each wait of the removal.
readonly REMOVAL_BUDGET_SECONDS=600

readonly UNANSWERED="A query that did not answer is not an empty result. This procedure does not continue on an unanswered query."
readonly NOT_CALLER_TRUTH="These are the states that Argo CD reports. They are not a caller outcome."

# --- Arguments --------------------------------------------------------------

[ "$#" -ge 1 ] || inferops::fail "no operation was given. ${USAGE}"
operation="$1"
shift

api_image_digest=""
digest_given=0
confirmed=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --api-image-digest)
      [ "$#" -ge 2 ] && [ -n "$2" ] || inferops::fail "--api-image-digest needs a value. ${USAGE}"
      [ "${digest_given}" -eq 0 ] || inferops::fail "--api-image-digest was given twice. ${USAGE}"
      digest_given=1
      api_image_digest="$2"
      shift 2
      ;;
    --confirm)
      confirmed=1
      shift
      ;;
    *)
      inferops::fail "unknown argument '$1'. ${USAGE}"
      ;;
  esac
done

case "${operation}" in
  apply)
    [ "${confirmed}" -eq 0 ] || inferops::fail "--confirm applies to 'remove' only. ${USAGE}"
    [[ "${api_image_digest}" =~ ^sha256:[0-9a-f]{64}$ ]] ||
      inferops::fail "refusing: api-image-digest-not-given: 'apply' needs --api-image-digest sha256:HEX, with 64 lowercase hexadecimal characters. No InferOps API image is published, so the digest names the image on this host: scripts/environment/api-image.sh digest prints it. Nothing was changed."
    ;;
  verify)
    [ "${digest_given}" -eq 0 ] && [ "${confirmed}" -eq 0 ] ||
      inferops::fail "'verify' takes no option. ${USAGE}"
    ;;
  remove)
    [ "${digest_given}" -eq 0 ] || inferops::fail "--api-image-digest applies to 'apply' only. ${USAGE}"
    [ "${confirmed}" -eq 1 ] ||
      inferops::fail "'remove' deletes the Application '${INFEROPS_GITOPS_APPLICATION_NAME}', every workload object it applied in '${INFEROPS_RELEASE_NAMESPACE}', and the project '${INFEROPS_GITOPS_PROJECT_NAME}'. Run it again with --confirm."
    ;;
  *)
    inferops::fail "unknown argument '${operation}'. ${USAGE}"
    ;;
esac

project_file="${INFEROPS_ROOT}/${INFEROPS_GITOPS_PROJECT_MANIFEST}"
application_file="${INFEROPS_ROOT}/${INFEROPS_GITOPS_APPLICATION_MANIFEST}"
[ -f "${project_file}" ] || inferops::fail "no project manifest at ${INFEROPS_GITOPS_PROJECT_MANIFEST}"
[ -f "${application_file}" ] || inferops::fail "no Application manifest at ${INFEROPS_GITOPS_APPLICATION_MANIFEST}"

inferops::require_cmd kubectl
inferops::require_cmd sha256sum
inferops::require_engine
# Every operation acts on the target this call verifies, and on no other. It
# takes the provider from the operator, with no default, and it runs before the
# first read of the cluster, so no line below reaches an unverified target.
inferops::resolve_target

# --- Reads ------------------------------------------------------------------
#
# Each read reports on stderr and returns non-zero when the question could not
# be asked. No caller nests one inside another substitution, because a failing
# inner substitution does not reach the outer assignment's status.

# The Argo CD namespace, as `phase|marker|pin`. Prints nothing when it is absent.
gitops::argocd_namespace_record() {
  local output
  if ! output="$(inferops::target_kubectl get namespace "${INFEROPS_ARGOCD_NAMESPACE}" \
    --ignore-not-found \
    -o "jsonpath={.status.phase}|{.metadata.labels.${INFEROPS_ARGOCD_MARKER_LABEL//./\\.}}|{.metadata.annotations.${INFEROPS_ARGOCD_PIN_ANNOTATION//./\\.}}")"; then
    inferops::warn "the query for namespace '${INFEROPS_ARGOCD_NAMESPACE}' did not answer."
    return 1
  fi
  printf '%s' "${output}" | tr -d '\r'
}

# Every Application, ApplicationSet, and AppProject object in every namespace,
# one `Kind/namespace/name|marker|pin` on each line.
gitops::custom_resources() {
  local kind output found=""
  for kind in ${INFEROPS_ARGOCD_KINDS}; do
    if ! output="$(inferops::target_kubectl get "${kind}" --all-namespaces \
      -o "jsonpath={range .items[*]}{.kind}/{.metadata.namespace}/{.metadata.name}|{.metadata.labels.${INFEROPS_GITOPS_MARKER_LABEL//./\\.}}|{.metadata.annotations.${INFEROPS_GITOPS_PIN_ANNOTATION//./\\.}}{\"\\n\"}{end}")"; then
      inferops::warn "the query for '${kind}' objects did not answer."
      return 1
    fi
    found="${found}${output}"$'\n'
  done
  printf '%s' "${found}" | tr -d '\r' | grep . || true
}

# One field of the Application, by JSONPath. Prints nothing when the Application
# or the field is absent.
gitops::application_field() {
  local output
  if ! output="$(inferops::target_kubectl get applications.argoproj.io "${INFEROPS_GITOPS_APPLICATION_NAME}" \
    -n "${INFEROPS_ARGOCD_NAMESPACE}" --ignore-not-found -o "jsonpath=$1")"; then
    inferops::warn "the query for the Application '${INFEROPS_GITOPS_APPLICATION_NAME}' did not answer."
    return 1
  fi
  printf '%s' "${output}" | tr -d '\r'
}

# The workload objects in the destination namespace that carry the release
# label, by name.
gitops::workload_objects() {
  local output
  if ! output="$(inferops::target_kubectl get "${INFEROPS_GITOPS_RESIDUE_KINDS}" \
    -n "${INFEROPS_RELEASE_NAMESPACE}" -l "${INFEROPS_RELEASE_SELECTOR}" -o name)"; then
    inferops::warn "the query for workload objects in '${INFEROPS_RELEASE_NAMESPACE}' did not answer."
    return 1
  fi
  printf '%s' "${output}" | tr -d '\r'
}

gitops::claims() {
  local output
  if ! output="$(inferops::target_kubectl get persistentvolumeclaims \
    -n "${INFEROPS_RELEASE_NAMESPACE}" -o name)"; then
    inferops::warn "the query for claims in '${INFEROPS_RELEASE_NAMESPACE}' did not answer."
    return 1
  fi
  printf '%s' "${output}" | tr -d '\r'
}

# --- Checks -----------------------------------------------------------------

gitops::report_target() {
  inferops::log "provider: ${INFEROPS_TARGET_PROVIDER}"
  inferops::log "server version: ${INFEROPS_TARGET_SERVER_VERSION:-unknown}"
  inferops::log "repository revision: ${INFEROPS_TARGET_VERIFIED_REVISION}"
  # The revision names the last commit, and a working tree can differ from it.
  # These digests name the bytes that ran and the bytes that were applied.
  inferops::log "procedure SHA-256: $(sha256sum "${BASH_SOURCE[0]}" | awk '{ print $1 }')"
  inferops::log "library SHA-256: $(sha256sum "$(dirname "${BASH_SOURCE[0]}")/lib.sh" | awk '{ print $1 }')"
  inferops::log "project manifest SHA-256: ${project_sha}"
  inferops::log "Application manifest SHA-256: ${application_sha}"
}

# Refuses a cluster whose Argo CD the bootstrap procedure did not install.
gitops::refuse_without_bootstrap() {
  local record phase="" marker="" pin=""
  if ! record="$(gitops::argocd_namespace_record)"; then
    inferops::fail "could not read the namespace '${INFEROPS_ARGOCD_NAMESPACE}'. ${UNANSWERED}"
  fi
  [ -z "${record}" ] || IFS='|' read -r phase marker pin <<<"${record}"
  [ -n "${phase}" ] ||
    inferops::fail "refusing: argocd-not-installed-by-the-bootstrap: no namespace '${INFEROPS_ARGOCD_NAMESPACE}' exists. Install Argo CD first: scripts/environment/argocd-bootstrap.sh install. Nothing was changed."
  [ "${marker}" = "${INFEROPS_ARGOCD_MARKER_VALUE}" ] && [[ "${pin}" =~ ^[0-9a-f]{64}$ ]] ||
    inferops::fail "refusing: argocd-not-installed-by-the-bootstrap: the namespace '${INFEROPS_ARGOCD_NAMESPACE}' does not carry the bootstrap marker and a recorded manifest SHA-256. This procedure gives an Application only to an Argo CD that the bootstrap procedure installed. Nothing was changed."
  [ "${phase}" = "Active" ] ||
    inferops::fail "refusing: argocd-not-installed-by-the-bootstrap: the namespace '${INFEROPS_ARGOCD_NAMESPACE}' is in phase '${phase}', not 'Active'. Nothing was changed."
  inferops::log "the namespace '${INFEROPS_ARGOCD_NAMESPACE}' carries the bootstrap marker and records manifest SHA-256 ${pin}."
}

# Reads every Argo CD custom resource into own_application and own_project, as
# `present` or empty, and refuses every other one. It never adopts an object.
gitops::refuse_foreign_custom_resources() {
  local found identity marker pin foreign=""
  if ! found="$(gitops::custom_resources)"; then
    inferops::fail "could not ask which Application, ApplicationSet, and AppProject objects exist. ${UNANSWERED}"
  fi
  own_application=""
  own_project=""
  while IFS='|' read -r identity marker pin; do
    [ -n "${identity}" ] || continue
    if [ "${marker}" = "${INFEROPS_GITOPS_MARKER_VALUE}" ] && [[ "${pin}" =~ ^[0-9a-f]{64}$ ]]; then
      case "${identity}" in
        "Application/${INFEROPS_ARGOCD_NAMESPACE}/${INFEROPS_GITOPS_APPLICATION_NAME}")
          own_application="present"
          continue
          ;;
        "AppProject/${INFEROPS_ARGOCD_NAMESPACE}/${INFEROPS_GITOPS_PROJECT_NAME}")
          own_project="present"
          continue
          ;;
      esac
    fi
    foreign="${foreign} ${identity}"
  done <<<"${found}"
  [ -z "${foreign}" ] ||
    inferops::fail "refusing: foreign-argocd-custom-resource: these objects exist, and this procedure did not create them:${foreign}. One Application and one project are decided. An object with one of the two names and without the marker is not adopted. Nothing was changed."
}

# Compares the live Application with the decision. It reads the live object, so
# it sees a change that somebody made in the cluster.
gitops::assert_live_application() {
  local record project repository revision path server namespace prune self_heal finalizers
  if ! record="$(gitops::application_field '{.spec.project}|{.spec.source.repoURL}|{.spec.source.targetRevision}|{.spec.source.path}|{.spec.destination.server}|{.spec.destination.namespace}|{.spec.syncPolicy.automated.prune}|{.spec.syncPolicy.automated.selfHeal}|{.metadata.finalizers}')"; then
    inferops::fail "could not read the Application. ${UNANSWERED}"
  fi
  IFS='|' read -r project repository revision path server namespace prune self_heal finalizers <<<"${record}"
  local findings=0
  gitops::expect() {
    if [ "$2" = "$3" ]; then
      inferops::log "$1: $2"
    else
      inferops::warn "$1 is '$2', and the decision is '$3'."
      findings=$((findings + 1))
    fi
  }
  gitops::expect "project" "${project}" "${INFEROPS_GITOPS_PROJECT_NAME}"
  gitops::expect "source repository" "${repository}" "${INFEROPS_GITOPS_REPOSITORY_URL}"
  gitops::expect "followed revision" "${revision}" "${INFEROPS_GITOPS_TARGET_REVISION}"
  gitops::expect "source path" "${path}" "${INFEROPS_CHART_PATH}"
  gitops::expect "destination server" "${server}" "${INFEROPS_GITOPS_DESTINATION_SERVER}"
  gitops::expect "destination namespace" "${namespace}" "${INFEROPS_RELEASE_NAMESPACE}"
  gitops::expect "automated pruning" "${prune}" "false"
  gitops::expect "automated self-heal" "${self_heal}" "true"
  gitops::expect "finalizers" "${finalizers}" ""
  [ "${findings}" -eq 0 ] ||
    inferops::fail "${findings} finding(s). The live Application is not the one that was decided."
}

# Prints what Argo CD reports about the Application.
gitops::report_application() {
  local record
  if ! record="$(gitops::application_field '{.status.sync.status}|{.status.sync.revision}|{.status.health.status}|{.status.operationState.phase}|{.status.operationState.syncResult.revision}|{.status.reconciledAt}')"; then
    inferops::fail "could not read the Application. ${UNANSWERED}"
  fi
  IFS='|' read -r sync_status sync_revision health_status operation_phase operation_revision reconciled_at <<<"${record}"
  inferops::log "desired revision: ${INFEROPS_GITOPS_TARGET_REVISION}, resolved by Argo CD to ${sync_revision:-nothing yet}"
  inferops::log "revision of the last sync operation: ${operation_revision:-none}, phase ${operation_phase:-none}"
  inferops::log "sync state: ${sync_status:-none}"
  inferops::log "health state: ${health_status:-none}"
  inferops::log "last comparison with Git: ${reconciled_at:-none}"
  inferops::log "${NOT_CALLER_TRUTH}"
}

# --- apply ------------------------------------------------------------------

diag_dir="${INFEROPS_ARTIFACT_DIR}/argocd-application"

collect_diagnostics() {
  mkdir -p "${diag_dir}"
  inferops::warn "collecting diagnostics into .artifacts/argocd-application/"
  inferops::target_kubectl get applications.argoproj.io "${INFEROPS_GITOPS_APPLICATION_NAME}" \
    -n "${INFEROPS_ARGOCD_NAMESPACE}" -o yaml >"${diag_dir}/application.yaml" 2>&1 || true
  inferops::target_kubectl get "${INFEROPS_GITOPS_RESIDUE_KINDS}" \
    -n "${INFEROPS_RELEASE_NAMESPACE}" -o wide >"${diag_dir}/get-workload.txt" 2>&1 || true
  inferops::target_kubectl describe pods \
    -n "${INFEROPS_RELEASE_NAMESPACE}" >"${diag_dir}/describe-pods.txt" 2>&1 || true
  inferops::target_kubectl get events -n "${INFEROPS_RELEASE_NAMESPACE}" \
    --sort-by=.lastTimestamp >"${diag_dir}/events.txt" 2>&1 || true
}

mutated=0

on_apply_exit() {
  local rc=$?
  if [ "${rc}" -ne 0 ] && [ "${mutated}" -eq 1 ]; then
    collect_diagnostics
    inferops::warn "the Application was left in place. Remove it with: scripts/environment/argocd-application.sh remove --confirm"
  fi
  exit "${rc}"
}

# Applies one committed manifest with the pin annotation, and for the
# Application the digest parameter. The patch is local: it reads the file and
# contacts no cluster.
gitops::apply_manifest() {
  local file="$1" sha="$2" patch="$3" document
  if ! document="$(inferops::target_kubectl patch --local --type json -o json \
    -f "$(inferops::native_path "${file}")" -p "${patch}")"; then
    inferops::fail "the manifest ${file#"${INFEROPS_ROOT}/"} could not be read."
  fi
  [ "$(sha256sum "${file}" | awk '{ print $1 }')" = "${sha}" ] ||
    inferops::fail "the manifest ${file#"${INFEROPS_ROOT}/"} changed while this procedure ran. It was not applied."
  mutated=1
  printf '%s\n' "${document}" |
    inferops::target_kubectl apply --server-side \
      --field-manager="${INFEROPS_GITOPS_FIELD_MANAGER}" -f -
}

apply() {
  local claims helm_records deadline annotation_patch before generation_before reconciled_before generation_after

  inferops::section "Refusals"
  gitops::report_target
  inferops::log "API image digest: ${api_image_digest}"
  gitops::refuse_without_bootstrap

  # The namespace and the claim are Terraform's. This procedure creates neither,
  # and the Application does not: it sets no CreateNamespace option.
  if ! claims="$(gitops::claims)"; then
    inferops::fail "refusing: destination-not-prepared: the namespace '${INFEROPS_RELEASE_NAMESPACE}' does not exist, or the query did not answer. Apply the prerequisite layer first: scripts/environment/terraform-prerequisites.sh apply. Nothing was changed."
  fi
  case $'\n'"${claims}"$'\n' in
    *$'\n'"persistentvolumeclaim/${INFEROPS_GITOPS_MODEL_CACHE_CLAIM}"$'\n'*) ;;
    *) inferops::fail "refusing: destination-not-prepared: the namespace '${INFEROPS_RELEASE_NAMESPACE}' holds no claim '${INFEROPS_GITOPS_MODEL_CACHE_CLAIM}'. Apply the prerequisite layer first: scripts/environment/terraform-prerequisites.sh apply. Nothing was changed." ;;
  esac
  inferops::log "the namespace '${INFEROPS_RELEASE_NAMESPACE}' and the claim '${INFEROPS_GITOPS_MODEL_CACHE_CLAIM}' exist."

  # Helm records a release in a Secret that carries these two labels. The names
  # are read and no value is. A release of the same name would be a second tool
  # that owns the same objects.
  if ! helm_records="$(inferops::target_kubectl get secrets -n "${INFEROPS_RELEASE_NAMESPACE}" \
    -l "owner=helm,name=${INFEROPS_RELEASE_NAME}" -o name)"; then
    inferops::fail "could not ask whether a Helm release exists in '${INFEROPS_RELEASE_NAMESPACE}'. ${UNANSWERED}"
  fi
  [ -z "${helm_records}" ] ||
    inferops::fail "refusing: helm-release-present: a Helm release named '${INFEROPS_RELEASE_NAME}' is recorded in '${INFEROPS_RELEASE_NAMESPACE}'. Helm and Argo CD would both own its objects. Uninstall the release first. Nothing was changed."
  inferops::log "no Helm release named '${INFEROPS_RELEASE_NAME}' is recorded in '${INFEROPS_RELEASE_NAMESPACE}'."

  gitops::refuse_foreign_custom_resources
  inferops::log "no other Application, ApplicationSet, or AppProject object exists."

  # Read before the apply. When the apply changes the Application, the wait
  # below accepts only a report that Argo CD made after the change.
  if ! before="$(gitops::application_field '{.metadata.generation}|{.status.reconciledAt}')"; then
    inferops::fail "could not read the Application before the apply. ${UNANSWERED}"
  fi
  generation_before="${before%%|*}"
  reconciled_before="${before#*|}"

  trap on_apply_exit EXIT

  inferops::section "Apply"
  annotation_patch='{"op":"add","path":"/metadata/annotations","value":{"'"${INFEROPS_GITOPS_PIN_ANNOTATION}"'":"%s"}}'
  # shellcheck disable=SC2059
  gitops::apply_manifest "${project_file}" "${project_sha}" \
    "[$(printf "${annotation_patch}" "${project_sha}")]"
  # shellcheck disable=SC2059
  gitops::apply_manifest "${application_file}" "${application_sha}" \
    "[$(printf "${annotation_patch}" "${application_sha}"),{\"op\":\"add\",\"path\":\"/spec/source/helm/parameters\",\"value\":[{\"name\":\"${INFEROPS_GITOPS_DIGEST_PARAMETER}\",\"value\":\"${api_image_digest}\"}]}]"

  if ! generation_after="$(gitops::application_field '{.metadata.generation}')"; then
    inferops::fail "could not read the Application after the apply. ${UNANSWERED}"
  fi
  if [ "${generation_after}" = "${generation_before}" ]; then
    inferops::log "the apply did not change the Application (generation ${generation_after})."
  else
    inferops::log "the apply changed the Application: generation '${generation_before:-none}' to '${generation_after}'. A report from before the change is not accepted."
  fi

  inferops::section "Sync"
  # Synced alone is not enough: an Application is Synced before its first
  # operation when nothing differs. The operation must have succeeded at a
  # revision, and that revision must be the one the comparison resolved. When
  # the apply changed the Application, the comparison must also be a new one.
  deadline=$((SECONDS + SYNC_BUDGET_SECONDS))
  while :; do
    gitops::report_application
    if [ "${generation_after}" != "${generation_before}" ] &&
      { [ -z "${reconciled_at}" ] || [ "${reconciled_at}" = "${reconciled_before}" ]; }; then
      inferops::log "Argo CD has not compared the changed Application yet."
    elif [ "${sync_status}" = "Synced" ] && [ "${operation_phase}" = "Succeeded" ] &&
      [[ "${sync_revision}" =~ ^[0-9a-f]{40}$ ]] && [ "${operation_revision}" = "${sync_revision}" ]; then
      break
    fi
    if [ "${SECONDS}" -ge "${deadline}" ]; then
      if ! gitops::application_field '{range .status.conditions[*]}{.type}: {.message}{"\n"}{end}{.status.operationState.message}{"\n"}' >&2; then
        inferops::warn "the conditions of the Application could not be read."
      fi
      inferops::fail "Argo CD did not report a succeeded sync within ${SYNC_BUDGET_SECONDS}s. The Application was left in place."
    fi
    sleep 10
  done

  inferops::section "Live Application"
  gitops::assert_live_application

  inferops::section "Result"
  inferops::log "Argo CD reports that it applied revision ${sync_revision} of '${INFEROPS_GITOPS_TARGET_REVISION}' to '${INFEROPS_RELEASE_NAMESPACE}' on provider '${INFEROPS_TARGET_PROVIDER}'."
  inferops::log "This does not establish that the workload serves a request."
}

# --- verify -----------------------------------------------------------------

verify() {
  local objects

  inferops::section "Marker"
  gitops::report_target
  gitops::refuse_without_bootstrap
  gitops::refuse_foreign_custom_resources
  [ -n "${own_project}" ] && [ -n "${own_application}" ] ||
    inferops::fail "the project '${INFEROPS_GITOPS_PROJECT_NAME}' and the Application '${INFEROPS_GITOPS_APPLICATION_NAME}' do not both exist with the marker. The Application is not applied by this procedure on this target."
  inferops::log "the project and the Application exist, and each carries ${INFEROPS_GITOPS_MARKER_LABEL}=${INFEROPS_GITOPS_MARKER_VALUE} and a recorded manifest SHA-256."

  inferops::section "Live Application"
  gitops::assert_live_application

  inferops::section "What Argo CD reports"
  gitops::report_application

  inferops::section "Workload objects in the destination namespace, by name"
  if ! objects="$(gitops::workload_objects)"; then
    inferops::fail "could not list the workload objects. ${UNANSWERED}"
  fi
  printf '%s\n' "${objects}"

  inferops::section "Result"
  inferops::log "the Application '${INFEROPS_GITOPS_APPLICATION_NAME}' is the one that was decided: automated sync, self-heal, and no pruning."
  inferops::log "This does not establish that the workload serves a request."
}

# --- remove -----------------------------------------------------------------

remove() {
  local ready claims_before claims_after deadline objects

  inferops::section "Refusals"
  gitops::report_target
  gitops::refuse_without_bootstrap
  gitops::refuse_foreign_custom_resources
  [ -n "${own_project}" ] || [ -n "${own_application}" ] ||
    inferops::fail "no project '${INFEROPS_GITOPS_PROJECT_NAME}' and no Application '${INFEROPS_GITOPS_APPLICATION_NAME}' exists with the marker. Nothing is left to remove. Nothing was changed."

  if ! claims_before="$(gitops::claims)"; then
    inferops::fail "could not list the claims in '${INFEROPS_RELEASE_NAMESPACE}' before the removal. ${UNANSWERED}"
  fi

  if [ -n "${own_application}" ]; then
    # The cascade is done by the application controller. A deletion that it
    # cannot finish keeps the Application, so the controller is checked first.
    if ! ready="$(inferops::target_kubectl get statefulset "${INFEROPS_ARGOCD_CONTROLLER}" \
      -n "${INFEROPS_ARGOCD_NAMESPACE}" --ignore-not-found -o 'jsonpath={.status.readyReplicas}')"; then
      inferops::fail "could not read the application controller. ${UNANSWERED}"
    fi
    ready="$(printf '%s' "${ready}" | tr -d '\r')"
    [ "${ready:-0}" -ge 1 ] ||
      inferops::fail "refusing: application-controller-not-ready: the statefulset '${INFEROPS_ARGOCD_CONTROLLER}' reports no ready replica. It performs the cascade, and without it the deletion does not finish. Nothing was changed."

    inferops::section "Deleting the Application, with a cascade"
    inferops::target_kubectl patch applications.argoproj.io "${INFEROPS_GITOPS_APPLICATION_NAME}" \
      -n "${INFEROPS_ARGOCD_NAMESPACE}" --type merge \
      -p "{\"metadata\":{\"finalizers\":[\"${INFEROPS_GITOPS_CASCADE_FINALIZER}\"]}}"
    inferops::target_kubectl delete applications.argoproj.io "${INFEROPS_GITOPS_APPLICATION_NAME}" \
      -n "${INFEROPS_ARGOCD_NAMESPACE}" --timeout="${REMOVAL_BUDGET_SECONDS}s"
  else
    inferops::log "no Application exists; only the project is deleted."
  fi

  inferops::section "Workload residue"
  deadline=$((SECONDS + REMOVAL_BUDGET_SECONDS))
  while :; do
    if ! objects="$(gitops::workload_objects)"; then
      inferops::fail "could not ask what the removal left. ${UNANSWERED} The project was not deleted."
    fi
    [ -n "${objects}" ] || break
    [ "${SECONDS}" -lt "${deadline}" ] ||
      inferops::fail "these objects remain in '${INFEROPS_RELEASE_NAMESPACE}' after ${REMOVAL_BUDGET_SECONDS}s: $(printf '%s' "${objects}" | tr '\n' ' '). The project was not deleted. No recovery is decided for an object that the cascade left."
    sleep 2
  done
  inferops::log "no object carrying '${INFEROPS_RELEASE_SELECTOR}' remains in '${INFEROPS_RELEASE_NAMESPACE}'."

  inferops::section "Deleting the project"
  inferops::target_kubectl delete appprojects.argoproj.io "${INFEROPS_GITOPS_PROJECT_NAME}" \
    -n "${INFEROPS_ARGOCD_NAMESPACE}" --ignore-not-found --timeout="${REMOVAL_BUDGET_SECONDS}s"

  inferops::section "Prerequisites"
  if ! claims_after="$(gitops::claims)"; then
    inferops::fail "could not list the claims in '${INFEROPS_RELEASE_NAMESPACE}' after the removal. ${UNANSWERED}"
  fi
  [ "${claims_after}" = "${claims_before}" ] ||
    inferops::fail "the claims in '${INFEROPS_RELEASE_NAMESPACE}' changed across the removal: before '${claims_before}', after '${claims_after}'. The removal must not delete a claim."
  inferops::log "the namespace '${INFEROPS_RELEASE_NAMESPACE}' and its claims are unchanged: ${claims_after:-none}"

  inferops::section "Result"
  gitops::refuse_foreign_custom_resources
  [ -z "${own_application}" ] && [ -z "${own_project}" ] ||
    inferops::fail "the Application or the project still exists after the removal."
  inferops::log "no Application and no project of this procedure remains. The Argo CD installation, the namespace, and the claim were not touched."
}

project_sha="$(sha256sum "${project_file}" | awk '{ print $1 }')"
application_sha="$(sha256sum "${application_file}" | awk '{ print $1 }')"

case "${operation}" in
  apply) apply ;;
  verify) verify ;;
  remove) remove ;;
esac
