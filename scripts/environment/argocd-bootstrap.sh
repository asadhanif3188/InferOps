#!/usr/bin/env bash
# Installs, verifies, and removes the Argo CD installation that ADR 0017 decided.
#
# The cluster already exists and is the operator's. This script selects it,
# verifies it, and installs into it. It does not create, enable, reset,
# reconfigure, or delete a cluster.
#
# The inputs are pinned in docs/environment/argocd-bootstrap.v1alpha1.json. The
# constants below restate them, and tests/architecture/test_argocd_bootstrap.py
# fails when a constant and the record differ.
#
# install  Creates the namespace `argocd` with the bootstrap marker, and applies
#          the pinned install manifest, unmodified, with server-side apply. Waits
#          a bounded time for the four workloads. Reports success only when every
#          Argo CD container runs the pinned digest of its image at that moment.
#          A second run on an installation this script created applies the same
#          bytes again.
# verify   Reads the installation and changes nothing in the cluster. Checks the
#          marker, the recorded pin, every object the record lists, the four
#          workloads, and the image digests.
# remove   Deletes what `install` created and nothing else, in the order ADR 0017
#          D11 decides. Deletes by the kinds and names listed here, so it needs
#          no download.
#
# Every refusal below comes before the first mutation, with one exception that
# ADR 0017 D11 decides: the removal checks for a custom resource a second time
# after it deletes the four workloads, and before it deletes a definition.
#
#   target-not-selected-or-not-verified  inferops::resolve_target
#   kubernetes-minor-not-tested          install
#   foreign-argocd-present               install, remove
#   installed-pin-differs                install
#   manifest-digest-mismatch             install
#   argocd-custom-resources-present      remove
#
# Does not touch: the cluster, the platform namespace, a Helm release, or the
# operator's own kubeconfig. It creates no Application, AppProject, or
# ApplicationSet object, and it reads no Secret value.
#
# On a failed install it collects diagnostics into .artifacts/argocd-bootstrap/
# and leaves the installation in place for inspection.
#
# Usage: scripts/environment/argocd-bootstrap.sh install [--manifest PATH]
#        scripts/environment/argocd-bootstrap.sh verify
#        scripts/environment/argocd-bootstrap.sh remove --confirm

# shellcheck source=scripts/environment/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

readonly USAGE="Usage: argocd-bootstrap.sh install [--manifest PATH] | verify | remove --confirm"

# --- The pins ---------------------------------------------------------------

readonly INFEROPS_ARGOCD_VERSION="v3.5.3"
readonly INFEROPS_ARGOCD_MANIFEST_URL="https://raw.githubusercontent.com/argoproj/argo-cd/c9c369efcc5b2a0bd720803f8d14a1c3eaddf579/manifests/core-install.yaml"
readonly INFEROPS_ARGOCD_MANIFEST_SHA256="1a87025d8eb2eae621653fd312fb9ca51df1b4b3b6992a030e3a9ef38e45c448"
readonly INFEROPS_ARGOCD_MANIFEST_OBJECT_COUNT="34"
readonly INFEROPS_ARGOCD_IMAGE_DIGEST="sha256:dd3f47d5a5e4da563a7a398506e892481b358a7cec50abdf320c71aa55904bfa"
readonly INFEROPS_ARGOCD_REDIS_IMAGE_DIGEST="sha256:08ad0b1d280850169a790dba1393ff7a90aef951fc19632cf4d3ce4f78e679ba"
readonly INFEROPS_ARGOCD_TESTED_MINORS="1.33 1.34 1.35 1.36"

# --- The namespace and its marker -------------------------------------------

# The name is not a preference. The manifest's one ClusterRoleBinding names a
# ServiceAccount in `argocd`, so an unmodified manifest binds the application
# controller only when it is applied there.
readonly INFEROPS_ARGOCD_NAMESPACE="argocd"
readonly INFEROPS_ARGOCD_MARKER_LABEL="inferops.io/lifecycle"
readonly INFEROPS_ARGOCD_MARKER_VALUE="bootstrap"
readonly INFEROPS_ARGOCD_PIN_ANNOTATION="inferops.io/argocd-manifest-sha256"

# --- The objects ------------------------------------------------------------

# The five cluster-scoped objects. They carry no marker, so the refusal of a
# foreign installation reads them by name.
readonly INFEROPS_ARGOCD_DEFINITIONS="applications.argoproj.io applicationsets.argoproj.io appprojects.argoproj.io"
readonly INFEROPS_ARGOCD_CLUSTER_ROLE="argocd-application-controller"
readonly INFEROPS_ARGOCD_CLUSTER_ROLE_BINDING="argocd-application-controller"

# The four workloads. Removal stops them before it deletes a definition.
readonly INFEROPS_ARGOCD_STATEFULSETS="argocd-application-controller"
readonly INFEROPS_ARGOCD_DEPLOYMENTS="argocd-applicationset-controller argocd-redis argocd-repo-server"

# The 29 namespaced objects the manifest declares, as `resource/name`.
readonly INFEROPS_ARGOCD_NAMESPACED_OBJECTS="serviceaccount/argocd-application-controller serviceaccount/argocd-applicationset-controller serviceaccount/argocd-redis serviceaccount/argocd-repo-server role/argocd-application-controller role/argocd-applicationset-controller role/argocd-redis rolebinding/argocd-application-controller rolebinding/argocd-applicationset-controller rolebinding/argocd-redis configmap/argocd-cm configmap/argocd-cmd-params-cm configmap/argocd-gpg-keys-cm configmap/argocd-rbac-cm configmap/argocd-ssh-known-hosts-cm configmap/argocd-tls-certs-cm secret/argocd-secret service/argocd-applicationset-controller service/argocd-metrics service/argocd-redis service/argocd-repo-server deployment/argocd-applicationset-controller deployment/argocd-redis deployment/argocd-repo-server statefulset/argocd-application-controller networkpolicy/argocd-application-controller-network-policy networkpolicy/argocd-applicationset-controller-network-policy networkpolicy/argocd-redis-network-policy networkpolicy/argocd-repo-server-network-policy"

# Every container of the installation, init containers included, by the image
# it must run. A container named in neither list fails the image check.
readonly INFEROPS_ARGOCD_CONTAINERS="argocd-application-controller argocd-applicationset-controller argocd-repo-server copyutil secret-init"
readonly INFEROPS_ARGOCD_REDIS_CONTAINERS="redis"

# --- The mechanism ----------------------------------------------------------

# The field manager that server-side apply records. A second run by the same
# manager changes nothing it already holds.
readonly INFEROPS_ARGOCD_FIELD_MANAGER="inferops-argocd-bootstrap"

# One budget for the four rollouts together. It must outlast two image pulls on
# a node that holds neither image.
readonly ROLLOUT_BUDGET_SECONDS=900
# One budget for each wait of the removal.
readonly REMOVAL_BUDGET_SECONDS=300

readonly UNANSWERED="A query that did not answer is not an empty result. This procedure does not continue on an unanswered query."

# --- Arguments --------------------------------------------------------------

[ "$#" -ge 1 ] || inferops::fail "no operation was given. ${USAGE}"
operation="$1"
shift

manifest_argument=""
manifest_given=0
confirmed=0

while [ "$#" -gt 0 ]; do
  case "$1" in
    --manifest)
      [ "$#" -ge 2 ] && [ -n "$2" ] || inferops::fail "--manifest needs a path. ${USAGE}"
      [ "${manifest_given}" -eq 0 ] || inferops::fail "--manifest was given twice. ${USAGE}"
      manifest_given=1
      manifest_argument="$2"
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
  install)
    [ "${confirmed}" -eq 0 ] || inferops::fail "--confirm applies to 'remove' only. ${USAGE}"
    ;;
  verify)
    [ -z "${manifest_argument}" ] && [ "${confirmed}" -eq 0 ] ||
      inferops::fail "'verify' takes no option. ${USAGE}"
    ;;
  remove)
    [ -z "${manifest_argument}" ] || inferops::fail "--manifest applies to 'install' only. ${USAGE}"
    [ "${confirmed}" -eq 1 ] ||
      inferops::fail "'remove' deletes the namespace '${INFEROPS_ARGOCD_NAMESPACE}', three definitions, one cluster role, and one cluster role binding. Run it again with --confirm."
    ;;
  *)
    inferops::fail "unknown argument '${operation}'. ${USAGE}"
    ;;
esac

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

# The namespace, as `phase|marker|pin`. Prints nothing when it does not exist.
argocd::namespace_record() {
  local output
  if ! output="$(inferops::target_kubectl get namespace "${INFEROPS_ARGOCD_NAMESPACE}" \
    --ignore-not-found \
    -o "jsonpath={.status.phase}|{.metadata.labels.${INFEROPS_ARGOCD_MARKER_LABEL//./\\.}}|{.metadata.annotations.${INFEROPS_ARGOCD_PIN_ANNOTATION//./\\.}}")"; then
    inferops::warn "the query for namespace '${INFEROPS_ARGOCD_NAMESPACE}' did not answer."
    return 1
  fi
  printf '%s' "${output}" | tr -d '\r'
}

# The cluster-scoped objects that exist, one `resource/name` on each line.
argocd::cluster_objects() {
  local targets=() definition output
  for definition in ${INFEROPS_ARGOCD_DEFINITIONS}; do
    targets+=("customresourcedefinition/${definition}")
  done
  targets+=("clusterrole/${INFEROPS_ARGOCD_CLUSTER_ROLE}")
  targets+=("clusterrolebinding/${INFEROPS_ARGOCD_CLUSTER_ROLE_BINDING}")
  if ! output="$(inferops::target_kubectl get "${targets[@]}" --ignore-not-found -o name)"; then
    inferops::warn "the query for the cluster-scoped objects did not answer."
    return 1
  fi
  printf '%s' "${output}" | tr -d '\r'
}

# Every Application, ApplicationSet, and AppProject object, in every namespace.
# A definition that does not exist holds no object, so it is not queried.
argocd::custom_resources() {
  local present="$1" definition output found=""
  for definition in ${INFEROPS_ARGOCD_DEFINITIONS}; do
    case "${present}" in
      *"/${definition}"*) ;;
      *) continue ;;
    esac
    if ! output="$(inferops::target_kubectl get "${definition}" --all-namespaces -o name)"; then
      inferops::warn "the query for '${definition}' objects did not answer."
      return 1
    fi
    found="${found}${output}"$'\n'
  done
  printf '%s' "${found}" | tr -d '\r' | grep . || true
}

argocd::pods() {
  local output
  if ! output="$(inferops::target_kubectl get pods -n "${INFEROPS_ARGOCD_NAMESPACE}" -o name)"; then
    inferops::warn "the query for pods in '${INFEROPS_ARGOCD_NAMESPACE}' did not answer."
    return 1
  fi
  printf '%s' "${output}" | tr -d '\r'
}

# --- Checks -----------------------------------------------------------------

# Reads the namespace into namespace_phase, namespace_marker, namespace_pin.
# An absent namespace leaves all three empty.
argocd::read_namespace() {
  local record
  if ! record="$(argocd::namespace_record)"; then
    inferops::fail "could not read the namespace '${INFEROPS_ARGOCD_NAMESPACE}'. ${UNANSWERED}"
  fi
  namespace_phase=""
  namespace_marker=""
  namespace_pin=""
  if [ -n "${record}" ]; then
    IFS='|' read -r namespace_phase namespace_marker namespace_pin <<<"${record}"
  fi
}

argocd::read_cluster_objects() {
  if ! cluster_objects="$(argocd::cluster_objects)"; then
    inferops::fail "could not read the cluster-scoped objects. ${UNANSWERED}"
  fi
}

# Refuses an Argo CD installation that this procedure did not create. It never
# adopts one. The marker is a label on the namespace, and the five
# cluster-scoped objects carry none, so they are read by name.
#
# Reads namespace_* and cluster_objects, which the caller has just read.
argocd::refuse_foreign_installation() {
  local operation="$1" namespace_pin_is_a_digest
  if [ -z "${namespace_phase}" ]; then
    case "${operation}" in
      install)
        [ -z "${cluster_objects}" ] ||
          inferops::fail "refusing: foreign-argocd-present: no namespace '${INFEROPS_ARGOCD_NAMESPACE}' exists, and these Argo CD objects do: $(printf '%s' "${cluster_objects}" | tr '
' ' '). This procedure did not create them, and server-side apply would take them over. Nothing was changed."
        return 0
        ;;
      *)
        inferops::fail "refusing: foreign-argocd-present: no namespace '${INFEROPS_ARGOCD_NAMESPACE}' exists, so no marker says that this procedure installed anything here. If a removal already finished, nothing is left to remove. Nothing was changed."
        ;;
    esac
  fi
  if [ "${namespace_marker}" != "${INFEROPS_ARGOCD_MARKER_VALUE}" ]; then
    inferops::fail "refusing: foreign-argocd-present: the namespace '${INFEROPS_ARGOCD_NAMESPACE}' exists and does not carry ${INFEROPS_ARGOCD_MARKER_LABEL}=${INFEROPS_ARGOCD_MARKER_VALUE}. This procedure did not create it, and it does not adopt it. Nothing was changed."
  fi
  # The procedure writes the label and the annotation in one request, so an
  # installation of its own always holds both. A label alone is not the marker.
  # Any SHA-256 is accepted here: the removal of an installation with an older
  # pin is the documented way to replace it.
  case "${namespace_pin}" in
    *[!0-9a-f]* | '') namespace_pin_is_a_digest=0 ;;
    *) namespace_pin_is_a_digest=1 ;;
  esac
  if [ "${namespace_pin_is_a_digest}" -eq 0 ] || [ "${#namespace_pin}" -ne 64 ]; then
    inferops::fail "refusing: foreign-argocd-present: the namespace '${INFEROPS_ARGOCD_NAMESPACE}' carries the label and does not record a manifest SHA-256 in ${INFEROPS_ARGOCD_PIN_ANNOTATION}. This procedure writes both in one request, so it did not create this namespace. Nothing was changed."
  fi
  if [ "${namespace_phase}" != "Active" ]; then
    inferops::fail "refusing: the namespace '${INFEROPS_ARGOCD_NAMESPACE}' is in phase '${namespace_phase:-unknown}', not 'Active'. A deletion is in progress. Wait until the namespace is gone, then run this procedure again. Nothing was changed."
  fi
}

argocd::refuse_custom_resources() {
  local when="$1" found
  if ! found="$(argocd::custom_resources "${cluster_objects}")"; then
    inferops::fail "could not ask whether an Application, ApplicationSet, or AppProject object exists. ${UNANSWERED}"
  fi
  if [ -n "${found}" ]; then
    printf '%s\n' "${found}" >&2
    inferops::fail "refusing: argocd-custom-resources-present: the objects listed above exist (${when}). Deleting a definition deletes every object of its kind, and an Application with a resource finalizer deletes its workload. Delete these objects deliberately, then run the removal again."
  fi
  inferops::log "no Application, ApplicationSet, or AppProject object exists (${when})."
}

# Every namespaced object the manifest declares exists. `kubectl get` with a
# name fails when one is missing, so the exit status carries the answer.
argocd::assert_objects_exist() {
  local targets=() target listed count
  for target in ${INFEROPS_ARGOCD_NAMESPACED_OBJECTS}; do
    targets+=("${target}")
  done
  if ! listed="$(inferops::target_kubectl get "${targets[@]}" \
    -n "${INFEROPS_ARGOCD_NAMESPACE}" -o name)"; then
    inferops::fail "at least one namespaced object the manifest declares is missing from '${INFEROPS_ARGOCD_NAMESPACE}', or the query did not answer."
  fi
  count="$(printf '%s\n' "${listed}" | grep -c . || true)"
  [ "${count}" -eq "${#targets[@]}" ] ||
    inferops::fail "expected ${#targets[@]} namespaced objects in '${INFEROPS_ARGOCD_NAMESPACE}', the cluster returned ${count}."
  inferops::log "${count} namespaced objects exist in '${INFEROPS_ARGOCD_NAMESPACE}', as the record lists."
}

argocd::assert_cluster_objects_exist() {
  local count
  argocd::read_cluster_objects
  count="$(printf '%s\n' "${cluster_objects}" | grep -c . || true)"
  [ "${count}" -eq 5 ] ||
    inferops::fail "expected 5 cluster-scoped objects (three definitions, one cluster role, one cluster role binding), the cluster returned ${count}: $(printf '%s' "${cluster_objects}" | tr '\n' ' ')"
  inferops::log "5 cluster-scoped objects exist, as the record lists."
}

argocd::wait_for_rollouts() {
  local budget="$1" deadline remaining workload
  deadline=$((SECONDS + budget))
  for workload in ${INFEROPS_ARGOCD_DEPLOYMENTS}; do
    remaining=$((deadline - SECONDS))
    [ "${remaining}" -gt 0 ] || inferops::fail "the rollout budget of ${budget}s ended before deployment '${workload}' was checked."
    inferops::target_kubectl rollout status "deployment/${workload}" \
      -n "${INFEROPS_ARGOCD_NAMESPACE}" --timeout="${remaining}s"
  done
  for workload in ${INFEROPS_ARGOCD_STATEFULSETS}; do
    remaining=$((deadline - SECONDS))
    [ "${remaining}" -gt 0 ] || inferops::fail "the rollout budget of ${budget}s ended before statefulset '${workload}' was checked."
    inferops::target_kubectl rollout status "statefulset/${workload}" \
      -n "${INFEROPS_ARGOCD_NAMESPACE}" --timeout="${remaining}s"
  done
}

# The image identity each container reports, compared with the pin.
#
# The manifest names each image by tag, and it is applied unmodified, so the
# apply does not fix the image bytes. This check reads what the container
# runtime resolved. It covers this moment only: a pod that restarts later
# resolves the tag again.
argocd::assert_pinned_images() {
  local statuses name identity expected seen="" mismatches=0 wanted
  if ! statuses="$(inferops::target_kubectl get pods -n "${INFEROPS_ARGOCD_NAMESPACE}" \
    -o 'jsonpath={range .items[*]}{range .status.initContainerStatuses[*]}{.name}{" "}{.imageID}{"\n"}{end}{range .status.containerStatuses[*]}{.name}{" "}{.imageID}{"\n"}{end}{end}')"; then
    inferops::fail "could not read the container statuses in '${INFEROPS_ARGOCD_NAMESPACE}'. ${UNANSWERED}"
  fi
  statuses="$(printf '%s' "${statuses}" | tr -d '\r')"

  while read -r name identity; do
    [ -n "${name}" ] || continue
    case " ${INFEROPS_ARGOCD_CONTAINERS} " in
      *" ${name} "*) expected="${INFEROPS_ARGOCD_IMAGE_DIGEST}" ;;
      *)
        case " ${INFEROPS_ARGOCD_REDIS_CONTAINERS} " in
          *" ${name} "*) expected="${INFEROPS_ARGOCD_REDIS_IMAGE_DIGEST}" ;;
          *)
            inferops::warn "container '${name}' is not one the record lists."
            mismatches=$((mismatches + 1))
            continue
            ;;
        esac
        ;;
    esac
    if [ "${identity##*@}" = "${expected}" ]; then
      inferops::log "container '${name}' runs ${identity}"
    else
      inferops::warn "container '${name}' runs '${identity:-no image identity}', and the pin is ${expected}."
      mismatches=$((mismatches + 1))
    fi
    seen="${seen} ${name}"
  done <<<"${statuses}"

  for wanted in ${INFEROPS_ARGOCD_CONTAINERS} ${INFEROPS_ARGOCD_REDIS_CONTAINERS}; do
    case " ${seen} " in
      *" ${wanted} "*) ;;
      *)
        inferops::warn "no running pod reports a container named '${wanted}'."
        mismatches=$((mismatches + 1))
        ;;
    esac
  done

  [ "${mismatches}" -eq 0 ] ||
    inferops::fail "${mismatches} image finding(s). At least one container does not run the pinned digest of its image, so this procedure does not report success. The installation was left in place."
  inferops::log "every container runs the pinned digest of its image at this moment. A pod that restarts later resolves the tag again."
}

argocd::report_target() {
  inferops::log "provider: ${INFEROPS_TARGET_PROVIDER}"
  inferops::log "server version: ${INFEROPS_TARGET_SERVER_VERSION:-unknown}"
  inferops::log "container runtime: ${INFEROPS_TARGET_CONTAINER_RUNTIME:-unknown}"
  inferops::log "node image digest: ${INFEROPS_TARGET_NODE_IMAGE_DIGEST:-unknown}"
  inferops::log "repository revision: ${INFEROPS_TARGET_VERIFIED_REVISION}"
  # The revision names the last commit, and a working tree can differ from it.
  # These two digests name the bytes that ran.
  inferops::log "procedure SHA-256: $(sha256sum "${BASH_SOURCE[0]}" | awk '{ print $1 }')"
  inferops::log "library SHA-256: $(sha256sum "$(dirname "${BASH_SOURCE[0]}")/lib.sh" | awk '{ print $1 }')"
}

# --- install ----------------------------------------------------------------

diag_dir="${INFEROPS_ARTIFACT_DIR}/argocd-bootstrap"

collect_diagnostics() {
  mkdir -p "${diag_dir}"
  inferops::warn "collecting diagnostics into .artifacts/argocd-bootstrap/"
  inferops::target_kubectl get deployments,statefulsets,pods,services \
    -n "${INFEROPS_ARGOCD_NAMESPACE}" -o wide >"${diag_dir}/get-workloads.txt" 2>&1 || true
  inferops::target_kubectl describe pods \
    -n "${INFEROPS_ARGOCD_NAMESPACE}" >"${diag_dir}/describe-pods.txt" 2>&1 || true
  inferops::target_kubectl get events -n "${INFEROPS_ARGOCD_NAMESPACE}" \
    --sort-by=.lastTimestamp >"${diag_dir}/events.txt" 2>&1 || true
}

mutated=0

on_install_exit() {
  local rc=$?
  if [ "${rc}" -ne 0 ] && [ "${mutated}" -eq 1 ]; then
    collect_diagnostics
    inferops::warn "the installation was left in place. Remove it with: scripts/environment/argocd-bootstrap.sh remove --confirm"
  fi
  exit "${rc}"
}

# Puts the verified manifest bytes at ${manifest_file}, or refuses.
argocd::obtain_manifest() {
  local actual download_native
  if [ -n "${manifest_argument}" ]; then
    [ -f "${manifest_argument}" ] || inferops::fail "no such manifest file: ${manifest_argument}"
    manifest_file="${manifest_argument}"
    inferops::log "reading the manifest from the file the operator named. It is verified like a download."
  else
    manifest_file="${diag_dir}/core-install.yaml"
    mkdir -p "${diag_dir}"
    if [ -f "${manifest_file}" ] &&
      [ "$(sha256sum "${manifest_file}" | awk '{ print $1 }')" = "${INFEROPS_ARGOCD_MANIFEST_SHA256}" ]; then
      inferops::log "a copy with the pinned SHA-256 is already in .artifacts/argocd-bootstrap/; no download."
    else
      inferops::require_cmd curl
      inferops::log "downloading ${INFEROPS_ARGOCD_MANIFEST_URL}"
      # A Windows curl needs a native path, as kubectl does. lib.sh turns off
      # the automatic conversion, so an unconverted path fails as a write error.
      download_native="$(inferops::native_path "${manifest_file}.download")"
      curl --fail --silent --show-error --location --proto '=https' --max-time 120 \
        --output "${download_native}" "${INFEROPS_ARGOCD_MANIFEST_URL}" ||
        inferops::fail "the manifest could not be downloaded. Nothing was changed. A copy obtained another way is accepted with --manifest PATH, and is verified the same way."
      mv "${manifest_file}.download" "${manifest_file}"
    fi
  fi

  actual="$(sha256sum "${manifest_file}" | awk '{ print $1 }')"
  [ "${actual}" = "${INFEROPS_ARGOCD_MANIFEST_SHA256}" ] ||
    inferops::fail "refusing: manifest-digest-mismatch: the manifest bytes have SHA-256 ${actual:-unreadable}, and the pin is ${INFEROPS_ARGOCD_MANIFEST_SHA256}. Nothing was changed."
  inferops::log "manifest SHA-256 is the pinned value: ${actual}"
}

install() {
  local minor state_was_absent=0 applied applied_count manifest_native

  inferops::section "Refusals"
  argocd::report_target

  minor="$(printf '%s' "${INFEROPS_TARGET_SERVER_VERSION:-}" | sed -n 's/^v\([0-9][0-9]*\.[0-9][0-9]*\)\..*$/\1/p')"
  case " ${INFEROPS_ARGOCD_TESTED_MINORS} " in
    *" ${minor:-unknown} "*) inferops::log "Kubernetes minor ${minor} is one upstream lists as tested with Argo CD ${INFEROPS_ARGOCD_VERSION}." ;;
    *) inferops::fail "refusing: kubernetes-minor-not-tested: the server reports '${INFEROPS_TARGET_SERVER_VERSION:-no version}', and the tested minors are: ${INFEROPS_ARGOCD_TESTED_MINORS}. Nothing was changed." ;;
  esac

  argocd::read_namespace
  argocd::read_cluster_objects
  argocd::refuse_foreign_installation install
  if [ -z "${namespace_phase}" ]; then
    state_was_absent=1
    inferops::log "no namespace '${INFEROPS_ARGOCD_NAMESPACE}' and no Argo CD cluster-scoped object exists."
  else
    [ "${namespace_pin}" = "${INFEROPS_ARGOCD_MANIFEST_SHA256}" ] ||
      inferops::fail "refusing: installed-pin-differs: the namespace '${INFEROPS_ARGOCD_NAMESPACE}' records manifest SHA-256 '${namespace_pin:-none}', and the pin is ${INFEROPS_ARGOCD_MANIFEST_SHA256}. An upgrade in place is not decided. Remove the installation first. Nothing was changed."
    inferops::log "the namespace '${INFEROPS_ARGOCD_NAMESPACE}' carries the bootstrap marker and records the pinned SHA-256. The same bytes are applied again."
  fi

  argocd::obtain_manifest

  trap on_install_exit EXIT

  inferops::section "Namespace"
  if [ "${state_was_absent}" -eq 1 ]; then
    # One request, so that the namespace never exists without its marker.
    mutated=1
    printf '{"apiVersion":"v1","kind":"Namespace","metadata":{"name":"%s","labels":{"%s":"%s"},"annotations":{"%s":"%s"}}}\n' \
      "${INFEROPS_ARGOCD_NAMESPACE}" \
      "${INFEROPS_ARGOCD_MARKER_LABEL}" "${INFEROPS_ARGOCD_MARKER_VALUE}" \
      "${INFEROPS_ARGOCD_PIN_ANNOTATION}" "${INFEROPS_ARGOCD_MANIFEST_SHA256}" |
      inferops::target_kubectl create -f -
  else
    inferops::log "the namespace already exists; it is not created or relabelled."
  fi

  inferops::section "Apply"
  mutated=1
  manifest_native="$(inferops::native_path "${manifest_file}")"
  # Server-side apply, because a definition in this manifest exceeds the size
  # limit of the annotation that client-side apply writes. --force-conflicts
  # takes over a field another manager holds. When no marked namespace exists,
  # the refusals above keep a foreign cluster-scoped object from this line.
  # When one exists they do not: the five cluster-scoped objects carry no
  # marker, so one that another party replaced since is taken over here.
  #
  # The file is hashed again first. Its path is predictable, and the namespace
  # was created since the first hash.
  [ "$(sha256sum "${manifest_file}" | awk '{ print $1 }')" = "${INFEROPS_ARGOCD_MANIFEST_SHA256}" ] ||
    inferops::fail "refusing: manifest-digest-mismatch: the manifest bytes changed after they were verified. Nothing was applied. A namespace that this run created was left in place."
  applied="$(inferops::target_kubectl apply --server-side --force-conflicts \
    --field-manager="${INFEROPS_ARGOCD_FIELD_MANAGER}" \
    -n "${INFEROPS_ARGOCD_NAMESPACE}" -f "${manifest_native}")"
  printf '%s\n' "${applied}"
  applied_count="$(printf '%s\n' "${applied}" | grep -c 'serverside-applied' || true)"
  [ "${applied_count}" -eq "${INFEROPS_ARGOCD_MANIFEST_OBJECT_COUNT}" ] ||
    inferops::fail "the apply reported ${applied_count} objects, and the manifest declares ${INFEROPS_ARGOCD_MANIFEST_OBJECT_COUNT}."
  inferops::log "${applied_count} objects applied by field manager '${INFEROPS_ARGOCD_FIELD_MANAGER}'."

  inferops::section "Rollout"
  argocd::wait_for_rollouts "${ROLLOUT_BUDGET_SECONDS}"

  inferops::section "Objects"
  argocd::assert_cluster_objects_exist
  argocd::assert_objects_exist

  inferops::section "Images"
  argocd::assert_pinned_images

  inferops::section "Result"
  inferops::log "Argo CD ${INFEROPS_ARGOCD_VERSION} is installed in '${INFEROPS_ARGOCD_NAMESPACE}' on provider '${INFEROPS_TARGET_PROVIDER}'."
  inferops::log "no Application exists, so it reconciles nothing."
}

# --- verify -----------------------------------------------------------------

verify() {
  local custom_resources

  inferops::section "Marker and pin"
  argocd::report_target
  argocd::read_namespace
  [ -n "${namespace_phase}" ] ||
    inferops::fail "no namespace '${INFEROPS_ARGOCD_NAMESPACE}' exists. Argo CD is not installed by this procedure on this target."
  argocd::read_cluster_objects
  argocd::refuse_foreign_installation verify
  [ "${namespace_pin}" = "${INFEROPS_ARGOCD_MANIFEST_SHA256}" ] ||
    inferops::fail "the namespace '${INFEROPS_ARGOCD_NAMESPACE}' records manifest SHA-256 '${namespace_pin:-none}', and the pin is ${INFEROPS_ARGOCD_MANIFEST_SHA256}."
  inferops::log "the namespace carries ${INFEROPS_ARGOCD_MARKER_LABEL}=${INFEROPS_ARGOCD_MARKER_VALUE} and records the pinned SHA-256."

  inferops::section "Objects"
  argocd::assert_cluster_objects_exist
  argocd::assert_objects_exist

  inferops::section "Rollout"
  argocd::wait_for_rollouts 120

  inferops::section "Images"
  argocd::assert_pinned_images

  inferops::section "Secrets, Leases, and ConfigMaps in the namespace, by name"
  # Names only. No Secret value is read. The list holds the seven objects of
  # these kinds that the manifest declares, and whatever was created at run time.
  inferops::target_kubectl get secrets,leases,configmaps \
    -n "${INFEROPS_ARGOCD_NAMESPACE}" -o name

  inferops::section "Custom resources"
  if ! custom_resources="$(argocd::custom_resources "${cluster_objects}")"; then
    inferops::fail "could not ask whether an Application, ApplicationSet, or AppProject object exists. ${UNANSWERED}"
  fi
  if [ -n "${custom_resources}" ]; then
    printf '%s
' "${custom_resources}"
  else
    inferops::log "no Application, ApplicationSet, or AppProject object exists, so Argo CD reconciles nothing."
  fi

  inferops::section "Result"
  inferops::log "the installation in '${INFEROPS_ARGOCD_NAMESPACE}' is the pinned Argo CD ${INFEROPS_ARGOCD_VERSION}, and every container runs its pinned digest at this moment."
}

# --- remove -----------------------------------------------------------------

remove() {
  local workload definition deadline pods remaining

  inferops::section "Refusals"
  argocd::report_target
  argocd::read_namespace
  argocd::read_cluster_objects
  argocd::refuse_foreign_installation remove
  [ "${namespace_pin}" = "${INFEROPS_ARGOCD_MANIFEST_SHA256}" ] ||
    inferops::warn "the namespace records manifest SHA-256 '${namespace_pin:-none}', not the pinned one. Removal deletes by name and continues."
  argocd::refuse_custom_resources "before the controllers stop"

  inferops::section "Stopping the controllers"
  for workload in ${INFEROPS_ARGOCD_STATEFULSETS}; do
    inferops::target_kubectl delete statefulset "${workload}" \
      -n "${INFEROPS_ARGOCD_NAMESPACE}" --ignore-not-found --timeout="${REMOVAL_BUDGET_SECONDS}s"
  done
  for workload in ${INFEROPS_ARGOCD_DEPLOYMENTS}; do
    inferops::target_kubectl delete deployment "${workload}" \
      -n "${INFEROPS_ARGOCD_NAMESPACE}" --ignore-not-found --timeout="${REMOVAL_BUDGET_SECONDS}s"
  done

  deadline=$((SECONDS + REMOVAL_BUDGET_SECONDS))
  while :; do
    if ! pods="$(argocd::pods)"; then
      inferops::fail "could not ask whether an Argo CD pod remains. ${UNANSWERED} The controllers were deleted and no definition was."
    fi
    [ -n "${pods}" ] || break
    [ "${SECONDS}" -lt "${deadline}" ] ||
      inferops::fail "pods remain in '${INFEROPS_ARGOCD_NAMESPACE}' after ${REMOVAL_BUDGET_SECONDS}s: $(printf '%s' "${pods}" | tr '\n' ' '). No definition was deleted. Run the removal again."
    sleep 2
  done
  inferops::log "no pod remains in '${INFEROPS_ARGOCD_NAMESPACE}'."

  inferops::section "Second check"
  argocd::read_cluster_objects
  argocd::refuse_custom_resources "after the controllers stopped"

  inferops::section "Deleting the cluster-scoped objects"
  for definition in ${INFEROPS_ARGOCD_DEFINITIONS}; do
    inferops::target_kubectl delete customresourcedefinition "${definition}" \
      --ignore-not-found --timeout="${REMOVAL_BUDGET_SECONDS}s"
  done
  inferops::target_kubectl delete clusterrolebinding "${INFEROPS_ARGOCD_CLUSTER_ROLE_BINDING}" \
    --ignore-not-found --timeout="${REMOVAL_BUDGET_SECONDS}s"
  inferops::target_kubectl delete clusterrole "${INFEROPS_ARGOCD_CLUSTER_ROLE}" \
    --ignore-not-found --timeout="${REMOVAL_BUDGET_SECONDS}s"

  inferops::section "Deleting the namespace"
  inferops::target_kubectl delete namespace "${INFEROPS_ARGOCD_NAMESPACE}" \
    --ignore-not-found --timeout="${REMOVAL_BUDGET_SECONDS}s"

  inferops::section "Residue"
  deadline=$((SECONDS + REMOVAL_BUDGET_SECONDS))
  while :; do
    argocd::read_namespace
    argocd::read_cluster_objects
    remaining="${cluster_objects}"
    [ -z "${namespace_phase}" ] || remaining="${remaining} namespace/${INFEROPS_ARGOCD_NAMESPACE}"
    [ -n "${remaining}" ] || break
    [ "${SECONDS}" -lt "${deadline}" ] ||
      inferops::fail "these objects remain after ${REMOVAL_BUDGET_SECONDS}s: $(printf '%s' "${remaining}" | tr '\n' ' '). The removal is not complete. No recovery is decided for a deletion that does not finish."
    sleep 2
  done

  inferops::section "Result"
  inferops::log "no Argo CD definition, cluster role, cluster role binding, or namespace '${INFEROPS_ARGOCD_NAMESPACE}' remains."
  inferops::log "the cluster, the platform namespace, and every release were not touched. Images that the node pulled stay in its image store."
}

case "${operation}" in
  install) install ;;
  verify) verify ;;
  remove) remove ;;
esac
