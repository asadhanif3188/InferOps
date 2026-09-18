#!/usr/bin/env bash
# Runs the V1 journey from a clean clone, one step at a time, and keeps a ledger
# of every step's outcome, exit code, and elapsed time.
#
# Usage:
#   scripts/environment/clean-clone.sh plan
#   scripts/environment/clean-clone.sh prerequisites [--prepare-only]
#   scripts/environment/clean-clone.sh run [--prepare-only] [--restart]
#       [--confirm-downloads] [--confirm-real-runtime] [--confirm-real-kubernetes]
#       [--confirm-cleanup]
#   scripts/environment/clean-clone.sh note TEXT [--step STEP]
#   scripts/environment/clean-clone.sh status
#   scripts/environment/clean-clone.sh cleanup --confirm [--include-model-cache]
#
# The steps, their order, and the consent each one needs are data:
# docs/environment/clean-clone.v1alpha1.json. This script runs them, and the
# ledger they are recorded in is kept by `python -m tools.clean_clone`, which
# refuses anything that would make the record read as more than it is -- a real
# step skipped in a certification run, a step passed before the one it stands on,
# an interval ending before it began, a ledger continued on another revision.
#
# Mostly an orchestrator. Most steps run a workflow that already exists and
# already guards itself, and hand it its own consent flag; a step whose consent
# was not given is never run. Some steps carry logic of their own -- the host
# prerequisites, the runtime image pull, the namespace snapshot, the values
# merge, cleanup, and the survival check -- and cleanup's release uninstall is the
# one mutation this script makes directly. The cluster belongs to its operator
# (ADR 0011 D1): this script selects nothing by default, verifies the selected
# cluster through `inferops::resolve_target` before its first mutation, creates
# and deletes no cluster, and runs no kind helper.
#
# Cleanup is its own decision. `run` leaves a release a failed step left behind in
# place for diagnosis, as every release workflow does; `cleanup --confirm` removes
# only what this run owns, and only from a cluster whose InferOps namespace it saw
# absent when the run first verified it.
#
# See docs/environment/clean-clone.md.

source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

# --- Verification -------------------------------------------------------------
#
# First in this file on purpose: every step that contacts the cluster starts here,
# and no line below may reach the cluster before it (ADR 0011 D3,
# `verification-precedes-every-mutation`). A target recorded by an earlier step is
# compared against, never trusted.

clean_clone::verify_target() {
  inferops::resolve_target
  CLEAN_CLONE_CLUSTER_UID="$(clean_clone::cluster_uid)" ||
    clean_clone::refuse "the verified cluster's identity could not be read, so it cannot be compared with the one this run began on."
  if [ -f "${CLEAN_CLONE_TARGET_BEFORE}" ]; then
    local recorded now
    recorded="$(sed -n 's/^provider=//p' "${CLEAN_CLONE_TARGET_BEFORE}") $(sed -n 's/^cluster=//p' "${CLEAN_CLONE_TARGET_BEFORE}") $(sed -n 's/^clusterUid=//p' "${CLEAN_CLONE_TARGET_BEFORE}")"
    now="${INFEROPS_TARGET_PROVIDER} ${INFEROPS_TARGET_CLUSTER_NAME} ${CLEAN_CLONE_CLUSTER_UID}"
    [ "${recorded}" = "${now}" ] ||
      clean_clone::refuse "this run first verified '${recorded}', and the selected target is now '${now}'. One ledger describes one cluster, and a cluster reset or recreated under the same name is not it."
  fi
}

# The UID of the cluster's own kube-system namespace. A provider and a cluster
# name say which cluster the operator selected; they do not change when the
# cluster is reset or recreated -- Docker Desktop's is always `docker-desktop` --
# and this does. A snapshot of namespaces is only a statement about the cluster it
# was taken on.
clean_clone::cluster_uid() {
  local uid
  uid="$(inferops::target_kubectl get namespace kube-system -o jsonpath='{.metadata.uid}' | tr -d '\r')" ||
    return 1
  [ -n "${uid}" ] || return 1
  printf '%s' "${uid}"
}

# --- Constants ----------------------------------------------------------------

here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "${INFEROPS_ROOT}"

readonly CLEAN_CLONE_DIR_REL=".artifacts/clean-clone"
readonly CLEAN_CLONE_TARGET_BEFORE="${INFEROPS_ROOT}/${CLEAN_CLONE_DIR_REL}/target-before.txt"
readonly CLEAN_CLONE_NAMESPACES_BEFORE="${INFEROPS_ROOT}/${CLEAN_CLONE_DIR_REL}/namespaces-before.txt"
readonly CLEAN_CLONE_WORKLOADS="${CLEAN_CLONE_DIR_REL}/workloads"
readonly CLEAN_CLONE_BASE_VALUES="charts/inferops-llm/ci/real-values.yaml"
readonly CLEAN_CLONE_API_VALUES="${CLEAN_CLONE_DIR_REL}/api-image-values.yaml"
readonly CLEAN_CLONE_SEED_VALUES="${CLEAN_CLONE_DIR_REL}/model-seed-values.yaml"
readonly CLEAN_CLONE_MERGED_VALUES="${CLEAN_CLONE_DIR_REL}/real-values.merged.yaml"
readonly CLEAN_CLONE_LEDGER="${CLEAN_CLONE_DIR_REL}/ledger.v1alpha1.json"

# How long a namespace may take to finish terminating after the destroy that
# deleted it. Terraform returns once the API server accepts the deletion.
readonly CLEAN_CLONE_NAMESPACE_GONE_SECONDS=300

readonly usage="Usage: clean-clone.sh plan | prerequisites [--prepare-only] | run [--prepare-only] [--restart] [--confirm-downloads] [--confirm-real-runtime] [--confirm-real-kubernetes] [--confirm-cleanup] | note TEXT [--step STEP] | status | cleanup --confirm [--include-model-cache]"

# --- Output and time ----------------------------------------------------------

# A refusal, as distinct from a failure: a precondition was not met and nothing
# was attempted. Exit 3, the code every tool here already uses for it.
clean_clone::refuse() {
  printf '[inferops] REFUSED: %s\n' "$*" >&2
  exit 3
}

# Milliseconds since the epoch, from bash's own clock. EPOCHREALTIME is used
# rather than `date +%s%3N` because BSD date has no %N, and some locales write it
# with a comma.
clean_clone::now_ms() {
  local now="${EPOCHREALTIME/[.,]/}"
  printf '%s' "$((now / 1000))"
}

[ -n "${EPOCHREALTIME:-}" ] ||
  inferops::fail "this bash has no EPOCHREALTIME; the clean-clone workflow and two of the workflows it runs need bash 5 or later."

# Asked before anything else, because the checkout check that opens a run is
# itself a python command: without this, a host with no python at all would be
# told its checkout cannot stand for a clean clone.
command -v python >/dev/null 2>&1 ||
  inferops::fail "no 'python' on PATH. Until the toolchain-sync step installs the locked environment, the ledger is kept by the host's own CPython 3.12, using its standard library only. See docs/environment/clean-clone.md."

clean_clone::ledger() {
  inferops::python -m tools.clean_clone --ledger "${CLEAN_CLONE_LEDGER}" "$@"
}

# The locked toolchain, first on PATH for this shell and everything it starts.
# Every workflow here calls a bare `python`, and the one it must find is the one
# `uv sync --locked` just installed, not whichever the host happened to have.
clean_clone::activate_toolchain() {
  local bin=".venv/bin"
  [ -d ".venv/Scripts" ] && bin=".venv/Scripts"
  [ -d "${bin}" ] || inferops::fail "no locked environment at .venv; run the toolchain-sync step first."
  PATH="${INFEROPS_ROOT}/${bin}:${PATH}"
  export PATH
}

# --- Arguments ----------------------------------------------------------------

action="${1:-}"
[ "$#" -gt 0 ] && shift
case "${action}" in
  plan | prerequisites | run | note | status | cleanup) ;;
  *) inferops::fail "${usage}" ;;
esac

mode="certification"
restart=0
confirm_cleanup=0
include_model_cache=0
note_text=""
note_step=""
granted=""

while [ "$#" -gt 0 ]; do
  case "${action}:$1" in
    prerequisites:--prepare-only | run:--prepare-only) mode="preparation" ;;
    run:--restart) restart=1 ;;
    run:--confirm-downloads) granted="${granted} artifact-download" ;;
    run:--confirm-real-runtime) granted="${granted} real-runtime" ;;
    run:--confirm-real-kubernetes) granted="${granted} real-kubernetes" ;;
    run:--confirm-cleanup)
      confirm_cleanup=1
      granted="${granted} cleanup"
      ;;
    cleanup:--confirm)
      confirm_cleanup=1
      granted="${granted} cleanup"
      ;;
    cleanup:--include-model-cache) include_model_cache=1 ;;
    note:--step)
      [ "$#" -ge 2 ] || inferops::fail "--step needs a step identifier. ${usage}"
      note_step="$2"
      shift
      ;;
    note:-*) inferops::fail "unknown argument '$1' for 'note'. ${usage}" ;;
    note:*)
      [ -z "${note_text}" ] || inferops::fail "unknown argument '$1': a note takes one quoted description. ${usage}"
      note_text="$1"
      ;;
    *) inferops::fail "unknown argument '$1' for '${action}'. ${usage}" ;;
  esac
  shift
done

clean_clone::granted() {
  case " ${granted} " in
    *" $1 "*) return 0 ;;
    *) return 1 ;;
  esac
}

# The consent a step needs, read from the checklist rather than restated here, and
# read once: every step's line is `<step> [<authorization> ...]`.
# Loaded in this shell, never inside a command substitution, which would fill a
# copy of the table and throw it away.
declare -A CLEAN_CLONE_REQUIRES=()
clean_clone::load_requirements() {
  local line step
  while read -r line; do
    step="${line%% *}"
    CLEAN_CLONE_REQUIRES["${step}"]="${line#"${step}"}"
  done < <(clean_clone::ledger requires)
  [ "${#CLEAN_CLONE_REQUIRES[@]}" -gt 0 ] ||
    inferops::fail "the checklist could not be read."
}

# --- Steps --------------------------------------------------------------------
#
# One function per checklist step, named after its identifier. Each runs in its
# own subshell with errexit on, so a failure inside one ends that step and is
# recorded, rather than ending the orchestrator before the ledger hears of it.

clean_clone::step_clean_checkout() {
  # A fresh run's check happens before its ledger exists -- see clean_clone::run.
  # Here the run is being resumed, so the state it finds is its own, and only an
  # uncommitted change can make this checkout stop being the clone the run began.
  clean_clone::ledger checkout
}

clean_clone::step_host_prerequisites() {
  local problems=0 tool

  for tool in git python uv; do
    command -v "${tool}" >/dev/null 2>&1 || {
      inferops::warn "'${tool}' is not on PATH."
      problems=$((problems + 1))
    }
  done
  if command -v python >/dev/null 2>&1; then
    python -c 'import sys; sys.exit(0 if sys.version_info[:2] == (3, 12) else 1)' || {
      inferops::warn "python is not 3.12; ADR 0009 pins the toolchain to CPython 3.12."
      problems=$((problems + 1))
    }
  fi
  inferops::log "bash ${BASH_VERSION}: EPOCHREALTIME available."

  # What the real steps need is asked only when a real step may run. A
  # preparation run without consent reports the gap and is not refused for it:
  # nothing it will do needs the tool.
  local needs_engine=0 needs_cluster_tools=0
  if [ "${mode}" = "certification" ] || clean_clone::granted artifact-download ||
    clean_clone::granted real-runtime || clean_clone::granted real-kubernetes; then
    needs_engine=1
  fi
  if [ "${mode}" = "certification" ] || clean_clone::granted real-kubernetes; then
    needs_cluster_tools=1
  fi

  # sha256sum because the model seed image's build verifies the artifact with it.
  local cluster_tools="kubectl helm terraform sha256sum"
  [ "${INFEROPS_PROVIDER:-}" = "kind" ] && cluster_tools="${cluster_tools} kind"
  for tool in docker ${cluster_tools}; do
    if command -v "${tool}" >/dev/null 2>&1; then
      continue
    fi
    if { [ "${tool}" = "docker" ] && [ "${needs_engine}" = 1 ]; } ||
      { [ "${tool}" != "docker" ] && [ "${needs_cluster_tools}" = 1 ]; }; then
      inferops::warn "'${tool}' is not on PATH, and a step this run may take needs it."
      problems=$((problems + 1))
    else
      inferops::log "'${tool}' is not on PATH; no step this run is authorized to take needs it."
    fi
  done

  if [ "${needs_engine}" = 1 ] && command -v docker >/dev/null 2>&1; then
    local cpus mem
    if ! docker version --format '{{.Server.Version}}' >/dev/null 2>&1; then
      inferops::warn "the container engine is not reachable. Start it and retry."
      problems=$((problems + 1))
    else
      cpus="$(docker info --format '{{.NCPU}}' 2>/dev/null || true)"
      mem="$(docker info --format '{{.MemTotal}}' 2>/dev/null || true)"
      if [ -z "${cpus}" ] || [ "${cpus}" -lt "${INFEROPS_MIN_ENGINE_CPUS}" ]; then
        inferops::warn "the engine reports ${cpus:-no} processors; ADR 0001 (D7) needs ${INFEROPS_MIN_ENGINE_CPUS}."
        problems=$((problems + 1))
      fi
      if [ -z "${mem}" ] || [ "${mem}" -lt "${INFEROPS_MIN_ENGINE_MEM_BYTES}" ]; then
        inferops::warn "the engine reports ${mem:-no} bytes of memory; ADR 0001 (D7) needs $(inferops::gib "${INFEROPS_MIN_ENGINE_MEM_BYTES}")."
        problems=$((problems + 1))
      fi
      inferops::log "engine: ${cpus:-unknown} processors, $(inferops::gib "${mem:-0}")."
    fi
  fi

  local kind path free
  read -r kind path <<<"$(inferops::disk_probe_target)"
  if free="$(inferops::free_disk_bytes "${path}")"; then
    if [ "${free}" -lt "${INFEROPS_MIN_FREE_DISK_BYTES}" ]; then
      inferops::warn "$(inferops::gb "${free}") free on the ${kind} volume; ADR 0001 (D7) needs $(inferops::gb "${INFEROPS_MIN_FREE_DISK_BYTES}"). If the engine's disk lives elsewhere, name that volume with INFEROPS_DISK_VOLUME -- it selects what is measured and cannot lower the bar."
      problems=$((problems + 1))
    else
      inferops::log "disk: $(inferops::gb "${free}") free on the ${kind} volume."
    fi
  else
    inferops::warn "free disk on the ${kind} volume could not be measured; not counted as a failure."
  fi

  [ "${problems}" -eq 0 ] ||
    clean_clone::refuse "${problems} host prerequisite(s) are not met. Nothing was changed."
  inferops::log "host prerequisites met for a ${mode} run."
}

clean_clone::step_toolchain_sync() {
  uv sync --locked
}

clean_clone::step_default_lane_checks() {
  # The commands of two of the default-checks lane's gates, code-quality and
  # default-lane-tests. The lane's other gates -- scans, renders, image builds, the
  # link and expected-failure checks -- are not run here.
  uv run --locked ruff format --check .
  uv run --locked ruff check .
  uv run --locked python -m mypy
  uv run --locked python -m pytest -q
}

clean_clone::step_workload_scaffold() {
  # A directory of its own per attempt: the scaffolder refuses an occupied
  # destination rather than overwriting it, and a retried step must not need
  # anybody to delete the last attempt's output first.
  local into
  into="${CLEAN_CLONE_WORKLOADS}/attempt-$(clean_clone::now_ms)"
  python -m tools.workload_scaffold \
    --name clean-clone-mock --owner team-platform --environment ci \
    --profile mock-llm --runtime-profile resource-conscious \
    --cpu 250m --memory 128Mi --tenant demo --cost-center demo-cost-center \
    --data-classification public \
    --description "Clean-clone mock workload; never real-runtime evidence." \
    --into "${into}"
  python -m tools.contract_validation "${into}/clean-clone-mock/workload.yaml"
  python -m pytest "${into}/clean-clone-mock/tests" -q
  python -m tools.workload_scaffold \
    --name clean-clone-real --owner team-platform --environment local \
    --profile synchronous-llm --runtime-profile resource-conscious \
    --cpu 6 --memory 3Gi --tenant demo --cost-center demo-cost-center \
    --data-classification internal \
    --description "Clean-clone real workload; validation is not evidence of deployment." \
    --into "${into}"
  python -m tools.contract_validation "${into}/clean-clone-real/workload.yaml"
  python -m pytest "${into}/clean-clone-real/tests" -q
}

clean_clone::step_model_acquisition() {
  python -m tools.model_acquisition acquire
  python -m tools.model_acquisition verify
}

clean_clone::step_runtime_image() {
  local reference
  reference="$(clean_clone::ledger runtime-image)"
  case "${reference}" in
    *@sha256:*) ;;
    *) clean_clone::refuse "the runtime package names '${reference}', which is not pinned by digest." ;;
  esac
  docker pull "${reference}"
}

clean_clone::step_local_real_inference() {
  python -m tools.runtime_certification certify --confirm-real-runtime
}

# The verified cluster's namespaces, one per line, sorted bytewise.
#
# Carriage returns are stripped because a Windows tool may write CRLF, and a
# snapshot compared line by line would then find every namespace missing. The C
# locale fixes the collation both sides of that comparison are sorted in, which
# `comm` requires and does not check.
clean_clone::namespaces() {
  inferops::target_kubectl get namespaces -o name | tr -d '\r' | LC_ALL=C sort
}

clean_clone::step_provider_verification() {
  bash "${here}/target-detect.sh"
  clean_clone::verify_target

  local namespaces
  namespaces="$(clean_clone::namespaces)" ||
    clean_clone::refuse "the cluster's namespaces could not be listed, so its InferOps footprint is unknown."

  if [ -f "${CLEAN_CLONE_TARGET_BEFORE}" ]; then
    inferops::log "resumed: the target matches the one this run first verified."
    return 0
  fi

  # Cleanup may remove the release namespace only because this run created it.
  # A cluster that already holds it -- from an earlier run, by hand, by anybody --
  # is refused here, so that nothing cleanup later removes could be someone
  # else's.
  if printf '%s\n' "${namespaces}" | grep -Fxq "namespace/${INFEROPS_RELEASE_NAMESPACE}"; then
    clean_clone::refuse "namespace '${INFEROPS_RELEASE_NAMESPACE}' already exists in this cluster. A clean-clone run starts from a cluster holding no InferOps release namespace, so that its cleanup removes only what it created. Remove it with the documented cleanup first (docs/environment/kubernetes-troubleshooting.md#cleanup)."
  fi

  mkdir -p "$(dirname "${CLEAN_CLONE_TARGET_BEFORE}")"
  printf '%s\n' "${namespaces}" >"${CLEAN_CLONE_NAMESPACES_BEFORE}"
  {
    printf 'provider=%s\n' "${INFEROPS_TARGET_PROVIDER}"
    printf 'cluster=%s\n' "${INFEROPS_TARGET_CLUSTER_NAME}"
    printf 'context=%s\n' "${INFEROPS_TARGET_CONTEXT}"
    printf 'clusterUid=%s\n' "${CLEAN_CLONE_CLUSTER_UID}"
    printf 'serverVersion=%s\n' "${INFEROPS_TARGET_SERVER_VERSION}"
    printf 'verifiedAt=%s\n' "${INFEROPS_TARGET_VERIFIED_AT}"
  } >"${CLEAN_CLONE_TARGET_BEFORE}"
  inferops::log "recorded $(wc -l <"${CLEAN_CLONE_NAMESPACES_BEFORE}" | tr -d ' ') namespace(s) cleanup must leave in place."
}

clean_clone::step_release_images() {
  mkdir -p "${CLEAN_CLONE_DIR_REL}"
  bash "${here}/api-image.sh" build
  bash "${here}/api-image.sh" load
  bash "${here}/api-image.sh" values >"${CLEAN_CLONE_API_VALUES}"
  bash "${here}/model-seed-image.sh" build
  bash "${here}/model-seed-image.sh" load
  bash "${here}/model-seed-image.sh" values >"${CLEAN_CLONE_SEED_VALUES}"
  # Six release workflows take one values file. It is composed here from the
  # committed real values and the two overlays just printed, in the order
  # `helm -f` would layer them, rather than by hand.
  clean_clone::ledger values --output "${CLEAN_CLONE_MERGED_VALUES}" \
    "${CLEAN_CLONE_BASE_VALUES}" "${CLEAN_CLONE_API_VALUES}" "${CLEAN_CLONE_SEED_VALUES}"
}

clean_clone::step_terraform_prerequisites() {
  bash "${here}/terraform-prerequisites.sh" check
  bash "${here}/terraform-prerequisites.sh" plan
  bash "${here}/terraform-prerequisites.sh" apply
}

clean_clone::step_helm_deployment() {
  bash "${here}/helm-lifecycle.sh" --values "${CLEAN_CLONE_MERGED_VALUES}"
}

clean_clone::step_kubernetes_inference() {
  bash "${here}/kubernetes-certification.sh" certify \
    --values "${CLEAN_CLONE_MERGED_VALUES}" --confirm-real-kubernetes
}

clean_clone::step_telemetry_verification() {
  bash "${here}/telemetry-collection-verify.sh" verify \
    --values "${CLEAN_CLONE_MERGED_VALUES}" --confirm-real-kubernetes
}

# The two experiments refuse to start over a run directory that already exists.
# One this run's own earlier attempt left is moved aside, never deleted: it is
# the record of what that attempt saw.
clean_clone::set_aside() {
  local directory="$1"
  if [ -e "${directory}" ]; then
    local aside
    aside="${directory}.attempt-$(clean_clone::now_ms)"
    mv -- "${directory}" "${aside}"
    inferops::log "moved an earlier attempt's run directory aside to ${aside}."
  fi
}

clean_clone::step_load() {
  clean_clone::set_aside ".cache/inferops/experiments/performance-scenarios"
  bash "${here}/performance-scenarios.sh" run \
    --values "${CLEAN_CLONE_BASE_VALUES}" \
    --values "${CLEAN_CLONE_API_VALUES}" \
    --values "${CLEAN_CLONE_SEED_VALUES}" \
    --confirm-real-kubernetes
}

clean_clone::step_failure() {
  clean_clone::set_aside ".cache/inferops/experiments/inference-pod-recovery"
  bash "${here}/inference-pod-recovery.sh" run \
    --values "${CLEAN_CLONE_BASE_VALUES}" \
    --values "${CLEAN_CLONE_API_VALUES}" \
    --values "${CLEAN_CLONE_SEED_VALUES}" \
    --confirm-real-kubernetes
}

clean_clone::step_cleanup() {
  if [ ! -f "${CLEAN_CLONE_TARGET_BEFORE}" ]; then
    inferops::log "this run never verified a cluster, so nothing in any cluster is known to be its own. No cluster object is touched."
  else
    clean_clone::verify_target

    # The namespace was absent when this run first verified the cluster, so a
    # release in it is this run's. Anything else in it is refused rather than
    # removed, and a listing that could not be made is not read as an empty one.
    local releases
    releases="$(inferops::target_helm list --all --namespace "${INFEROPS_RELEASE_NAMESPACE}" --short)" ||
      clean_clone::refuse "helm could not list the releases in '${INFEROPS_RELEASE_NAMESPACE}'. Nothing was removed."
    releases="$(printf '%s\n' "${releases}" | sed '/^[[:space:]]*$/d')"
    if [ -n "${releases}" ]; then
      [ "${releases}" = "${INFEROPS_RELEASE_NAME}" ] ||
        clean_clone::refuse "'${INFEROPS_RELEASE_NAMESPACE}' holds a release other than '${INFEROPS_RELEASE_NAME}'. Nothing was removed."
      inferops::log "a failed step left release '${INFEROPS_RELEASE_NAME}' installed; uninstalling it."
      inferops::target_helm uninstall "${INFEROPS_RELEASE_NAME}" \
        --namespace "${INFEROPS_RELEASE_NAMESPACE}" --wait --timeout 10m
    fi

    # The guarded wrapper, which refuses again if a release is still there.
    bash "${here}/terraform-prerequisites.sh" destroy --confirm

    # A listing that fails is not a namespace that has gone: asked as a loop
    # condition, a failed kubectl would end the wait exactly as absence does.
    local waited=0 listing
    while :; do
      listing="$(clean_clone::namespaces)" ||
        inferops::fail "the namespaces could not be listed while waiting for '${INFEROPS_RELEASE_NAMESPACE}' to go."
      printf '%s\n' "${listing}" | grep -Fxq "namespace/${INFEROPS_RELEASE_NAMESPACE}" || break
      [ "${waited}" -lt "${CLEAN_CLONE_NAMESPACE_GONE_SECONDS}" ] ||
        inferops::fail "namespace '${INFEROPS_RELEASE_NAMESPACE}' was still terminating after ${CLEAN_CLONE_NAMESPACE_GONE_SECONDS}s."
      sleep 5
      waited=$((waited + 5))
    done
    inferops::log "namespace '${INFEROPS_RELEASE_NAMESPACE}' and the model cache claim are gone."
  fi

  if [ -d "${CLEAN_CLONE_WORKLOADS}" ]; then
    rm -r -- "${CLEAN_CLONE_WORKLOADS}"
    inferops::log "removed this run's workload scaffolds."
  fi

  if [ "${include_model_cache}" = 1 ]; then
    # The acquisition tool imports the platform package, which only the locked
    # environment carries. Cleanup is often its own invocation, after a run that
    # already ended, so nothing earlier in this shell has put that environment
    # first on PATH -- and the host's own python would fail to import it.
    clean_clone::activate_toolchain
    python -m tools.model_acquisition clean --confirm
  fi

  inferops::log "kept, by design:"
  inferops::log "  the cluster itself, and every namespace this run did not create;"
  inferops::log "  the images loaded into the cluster's node -- nothing InferOps runs removes them on docker-desktop;"
  inferops::log "  the API and model seed images on this host's engine, and the pulled runtime image;"
  [ "${include_model_cache}" = 1 ] ||
    inferops::log "  the verified model in the workspace cache (cleanup --include-model-cache removes it);"
  inferops::log "  every record under .cache/inferops/ and this run's ledger, which are the evidence."
}

clean_clone::step_cluster_survived() {
  if [ ! -f "${CLEAN_CLONE_TARGET_BEFORE}" ]; then
    inferops::log "this run never verified a cluster; there is nothing whose survival to check."
    return 0
  fi
  clean_clone::verify_target

  local nodes not_ready
  nodes="$(inferops::target_kubectl get nodes \
    -o jsonpath='{range .items[*]}{.metadata.name}{" "}{.status.conditions[?(@.type=="Ready")].status}{"\n"}{end}' |
    tr -d '\r')"
  [ -n "${nodes}" ] || inferops::fail "the cluster reports no nodes."
  not_ready="$(printf '%s\n' "${nodes}" | awk 'NF && $2 != "True"' | wc -l | tr -d ' ')"
  [ "${not_ready}" -eq 0 ] || inferops::fail "${not_ready} node(s) are not Ready."

  local now missing
  now="$(clean_clone::namespaces)"
  missing="$(printf '%s\n' "${now}" | LC_ALL=C comm -13 - "${CLEAN_CLONE_NAMESPACES_BEFORE}" | wc -l | tr -d ' ')"
  [ "${missing}" -eq 0 ] ||
    inferops::fail "${missing} namespace(s) present before this run are gone."
  if printf '%s\n' "${now}" | grep -Fxq "namespace/${INFEROPS_RELEASE_NAMESPACE}"; then
    inferops::fail "namespace '${INFEROPS_RELEASE_NAMESPACE}' is still there; cleanup did not finish."
  fi
  inferops::log "the cluster verifies, every node is Ready, and every namespace present before this run survived."
}

# --- Orchestration ------------------------------------------------------------

# Runs one step, measures it, and records it, leaving the step's exit status in
# CLEAN_CLONE_LAST_RC rather than returning it.
#
# That is not style. Bash ignores errexit -- inside a subshell too -- for every
# command run by a function called where a failure is being tested: `f || x`,
# `if f`, `! f`. A step called that way would carry on past its first failing
# command and be recorded by whatever its last command returned. So a step is
# only ever called as a plain statement, and nothing here tests this function's
# status.
CLEAN_CLONE_LAST_RC=0
clean_clone::attempt() {
  local step="$1" auth missing="" started finished rc outcome

  [ -n "${CLEAN_CLONE_REQUIRES[${step}]+set}" ] ||
    inferops::fail "the checklist names no step '${step}'."
  for auth in ${CLEAN_CLONE_REQUIRES[${step}]}; do
    clean_clone::granted "${auth}" || missing="${missing} ${auth}"
  done
  if [ -n "${missing}" ]; then
    if [ "${mode}" = "preparation" ]; then
      started="$(clean_clone::now_ms)"
      clean_clone::ledger record --step "${step}" --outcome not-run --exit-code 0 \
        --started-ms "${started}" --finished-ms "${started}" \
        --reason "preparation run; not authorized:${missing}"
      CLEAN_CLONE_LAST_RC=0
      return 0
    fi
    clean_clone::refuse "step '${step}' needs${missing}, which this invocation was not given."
  fi

  inferops::section "step ${step}"
  started="$(clean_clone::now_ms)"
  set +e
  (
    set -e
    "clean_clone::step_${step//-/_}"
  )
  rc=$?
  set -e
  finished="$(clean_clone::now_ms)"

  case "${rc}" in
    0) outcome="passed" ;;
    3) outcome="refused" ;;
    *) outcome="failed" ;;
  esac
  # A ledger that refuses the record -- a wall clock stepped backwards during a
  # long step is the realistic case -- must not end the orchestrator before it
  # has said what the step itself did. The run stops either way, so that nothing
  # after this step stands on an attempt the ledger does not hold.
  if ! clean_clone::ledger record --step "${step}" --outcome "${outcome}" --exit-code "${rc}" \
    --started-ms "${started}" --finished-ms "${finished}"; then
    inferops::warn "step '${step}' exited ${rc}, and the ledger refused to record it. The run stops here; run again to repeat the step."
    [ "${rc}" -ne 0 ] || rc=3
  fi
  CLEAN_CLONE_LAST_RC="${rc}"
}

clean_clone::consent_arguments() {
  local auth
  for auth in ${granted}; do
    printf -- '--authorize\n%s\n' "${auth}"
  done
}

clean_clone::selection_arguments() {
  [ -z "${INFEROPS_PROVIDER:-}" ] || printf -- '--provider\n%s\n' "${INFEROPS_PROVIDER}"
  [ -z "${INFEROPS_KIND_CLUSTER_NAME:-}" ] ||
    printf -- '--cluster-name\n%s\n' "${INFEROPS_KIND_CLUSTER_NAME}"
}

# Leaves the first non-zero status of the two steps in CLEAN_CLONE_LAST_RC.
clean_clone::cleanup_path() {
  local rc
  clean_clone::attempt cleanup
  rc="${CLEAN_CLONE_LAST_RC}"
  # Asked even when cleanup failed: whether the cluster survived is the one
  # question a failed cleanup makes more urgent, not less.
  clean_clone::attempt cluster-survived
  [ "${rc}" -ne 0 ] || rc="${CLEAN_CLONE_LAST_RC}"
  CLEAN_CLONE_LAST_RC="${rc}"
}

clean_clone::run() {
  local -a consent selection
  mapfile -t consent < <(clean_clone::consent_arguments)
  mapfile -t selection < <(clean_clone::selection_arguments)

  local began_now=0 checkout_rc=0 checkout_started checkout_finished
  if [ -f "${CLEAN_CLONE_LEDGER}" ] && [ "${restart}" = 0 ]; then
    clean_clone::ledger resume --mode "${mode}" "${selection[@]}" "${consent[@]}" ||
      exit 3
  else
    # A fresh run's clean-checkout check runs before anything is written, because
    # the ledger is itself state a previous run leaves. A checkout refused here
    # gets no ledger at all, so the next invocation is fresh again rather than a
    # resumption that would skip this check.
    inferops::section "step clean-checkout"
    checkout_started="$(clean_clone::now_ms)"
    if [ "${mode}" = "certification" ]; then
      clean_clone::ledger checkout --fresh || checkout_rc=$?
    else
      clean_clone::ledger checkout || checkout_rc=$?
    fi
    checkout_finished="$(clean_clone::now_ms)"
    [ "${checkout_rc}" -eq 0 ] ||
      clean_clone::refuse "this checkout cannot stand for a clean clone. No ledger was written."

    local -a again=()
    [ "${restart}" = 0 ] || again=(--restart)
    clean_clone::ledger begin --mode "${mode}" --started-ms "${checkout_started}" \
      "${selection[@]}" "${consent[@]}" "${again[@]}" || exit 3
    # A restarted run is a new run, and the cluster snapshot is the old run's. Left
    # in place it would make provider verification read the restart as a
    # resumption -- skipping the refusal of an existing release namespace and the
    # new snapshot -- and survival would be judged against the old run's cluster.
    # Moved aside beside the old ledger, never deleted.
    if [ "${restart}" = 1 ]; then
      clean_clone::set_aside "${CLEAN_CLONE_TARGET_BEFORE}"
      clean_clone::set_aside "${CLEAN_CLONE_NAMESPACES_BEFORE}"
    fi
    clean_clone::ledger record --step clean-checkout --outcome passed --exit-code 0 \
      --started-ms "${checkout_started}" --finished-ms "${checkout_finished}"
    began_now=1
  fi

  clean_clone::load_requirements
  local -a pending
  mapfile -t pending < <(clean_clone::ledger pending)
  case " ${pending[*]} " in
    *" toolchain-sync "*) ;;
    *) clean_clone::activate_toolchain ;;
  esac

  local step rc=0
  for step in "${pending[@]}"; do
    if [ "${step}" = "clean-checkout" ] && [ "${began_now}" = 1 ]; then
      continue
    fi
    clean_clone::attempt "${step}"
    rc="${CLEAN_CLONE_LAST_RC}"
    [ "${rc}" -eq 0 ] || break
    [ "${step}" != "toolchain-sync" ] || clean_clone::activate_toolchain
  done

  if [ "${rc}" -ne 0 ]; then
    inferops::warn "the run stopped at step '${step}' with exit ${rc}. Anything it installed is left in place for diagnosis."
    inferops::warn "fix the cause and run again to resume from that step, or remove what this run owns with: scripts/environment/clean-clone.sh cleanup --confirm"
  elif [ "${confirm_cleanup}" = 1 ]; then
    clean_clone::cleanup_path
    rc="${CLEAN_CLONE_LAST_RC}"
  else
    inferops::log "the forward path is recorded. Nothing is removed until: scripts/environment/clean-clone.sh cleanup --confirm"
  fi

  inferops::section "summary"
  clean_clone::ledger summary
  exit "${rc}"
}

case "${action}" in
  plan)
    clean_clone::ledger plan
    ;;
  prerequisites)
    # The two checks alone, recorded nowhere, so an operator can ask before
    # starting a run whether it could start.
    if [ "${mode}" = "certification" ]; then
      clean_clone::ledger checkout --fresh || clean_clone::refuse "this checkout cannot stand for a clean clone."
      granted="artifact-download real-runtime real-kubernetes"
    else
      clean_clone::ledger checkout || clean_clone::refuse "this checkout has uncommitted changes."
    fi
    clean_clone::step_host_prerequisites
    ;;
  run)
    clean_clone::run
    ;;
  note)
    [ -n "${note_text}" ] || inferops::fail "a note needs a description of what was done by hand. ${usage}"
    if [ -n "${note_step}" ]; then
      clean_clone::ledger note --description "${note_text}" --step "${note_step}"
    else
      clean_clone::ledger note --description "${note_text}"
    fi
    ;;
  status)
    clean_clone::ledger summary
    ;;
  cleanup)
    [ "${confirm_cleanup}" = 1 ] ||
      clean_clone::refuse "cleanup uninstalls, destroys the Terraform prerequisites, and reclaims the model weights in the claim. Pass --confirm."
    [ -f "${CLEAN_CLONE_LEDGER}" ] ||
      clean_clone::refuse "no ledger at ${CLEAN_CLONE_LEDGER}; there is no run whose resources are known."
    # Before anything is touched: a run whose cleanup already passed has nothing
    # left that it owns, and a second pass would only add a record that reads as
    # though it did.
    clean_clone::ledger cleanable || exit 3
    clean_clone::load_requirements
    clean_clone::cleanup_path
    inferops::section "summary"
    clean_clone::ledger summary
    exit "${CLEAN_CLONE_LAST_RC}"
    ;;
esac
