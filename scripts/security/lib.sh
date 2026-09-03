#!/usr/bin/env bash
# Shared definitions for the InferOps supply-chain scanning scripts.
#
# Sourced, never executed. The pinned severity threshold, the artifact
# directory, and the guard functions the security baseline names are defined
# here once, so that a script cannot silently gate on a threshold another
# script did not agree to.
#
# Sourcing it twice would re-declare readonly constants and, with errexit
# inherited, close the caller's shell. Guard against that the same way
# scripts/environment/lib.sh does.

# This file is sourced, not executed, and most of what it defines is consumed
# by the scripts beside it rather than here. shellcheck would report SC2034 on
# every constant below without this.
# shellcheck shell=bash
# shellcheck disable=SC2034

if [ -n "${INFEROPS_SECURITY_LIB_SOURCED:-}" ]; then
  return 0
fi
INFEROPS_SECURITY_LIB_SOURCED=1

set -Eeuo pipefail

# --- Policy -------------------------------------------------------------

# The whole severity policy, in one value read by every guard below rather
# than typed into each of them: a finding at or above this threshold makes a
# guard refuse to report success. A finding below it is recorded in the scan
# output and does not block. See docs/security/control-matrix.md for how an
# accepted exception would be recorded against a specific finding.
readonly INFEROPS_SCAN_BLOCKING_SEVERITY="CRITICAL,HIGH"

# The runtime contract that names the image InferOps pins for local serving.
# Read at scan time rather than copied into this file, so the two cannot
# drift the day the contract's digest is rotated and this file is not.
readonly INFEROPS_CONTAINER_PACKAGE_REL="deploy/serving/runtime/container-package.v1.json"

# --- Paths ----------------------------------------------------------------

inferops::security::repo_root() {
  cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd
}

INFEROPS_SECURITY_ROOT="$(inferops::security::repo_root)"
readonly INFEROPS_SECURITY_ROOT

# Raw scan and SBOM output. Under .artifacts/, which version control already
# ignores: this is lane output, and ADR 0005 D5's evidence-retention rule is
# that raw output is promoted into a committed, redacted record rather than
# kept as-is.
readonly INFEROPS_SECURITY_ARTIFACT_DIR="${INFEROPS_SECURITY_ROOT}/.artifacts/security"

# --- Output -----------------------------------------------------------------

inferops::security::log() { printf '[inferops-security] %s\n' "$*"; }
inferops::security::fail() {
  printf '[inferops-security] FAILED: %s\n' "$*" >&2
  exit 1
}

inferops::security::require_cmd() {
  command -v "$1" >/dev/null 2>&1 ||
    inferops::security::fail "'$1' is not on PATH. See docs/prerequisites.md."
}

# --- The pinned runtime image ------------------------------------------------

# The image reference InferOps pins for local serving, read out of the
# committed runtime contract rather than duplicated here.
inferops::security::runtime_image_reference() {
  local contract="${INFEROPS_SECURITY_ROOT}/${INFEROPS_CONTAINER_PACKAGE_REL}"
  [ -f "${contract}" ] ||
    inferops::security::fail "${INFEROPS_CONTAINER_PACKAGE_REL} is not committed"
  local ref
  ref="$(grep -o '"imageReference"[[:space:]]*:[[:space:]]*"[^"]*"' "${contract}" |
    head -1 | sed -E 's/.*"([^"]*)"$/\1/')"
  [ -n "${ref}" ] ||
    inferops::security::fail "${INFEROPS_CONTAINER_PACKAGE_REL} names no imageReference"
  printf '%s' "${ref}"
}

# --- Guards -------------------------------------------------------------

# Scans the pinned runtime image for known vulnerabilities and refuses to
# report success when a finding at or above the blocking severity turns up.
# Nothing here consults or writes an accepted exception automatically; one is
# recorded by hand in the security baseline, the way every other exception in
# this repository is.
inferops::security::assert_runtime_image_has_no_blocking_vulnerabilities() {
  local severity="${1:-${INFEROPS_SCAN_BLOCKING_SEVERITY}}"
  inferops::security::require_cmd trivy
  local image
  image="$(inferops::security::runtime_image_reference)"
  mkdir -p "${INFEROPS_SECURITY_ARTIFACT_DIR}"
  inferops::security::log "scanning ${image} for ${severity} findings"
  trivy image \
    --scanners vuln \
    --severity "${severity}" \
    --exit-code 1 \
    --format json \
    --output "${INFEROPS_SECURITY_ARTIFACT_DIR}/runtime-image-scan.json" \
    "${image}" ||
    inferops::security::fail "${image} carries a ${severity} finding with no recorded exception; see ${INFEROPS_SECURITY_ARTIFACT_DIR}/runtime-image-scan.json"
}

# Scans the committed dependency lockfile, including the dev and check
# groups - the only Python dependencies pinned anywhere in this repository,
# since the published distribution declares none - and refuses to report
# success on the same terms as the guard above.
inferops::security::assert_dependencies_have_no_blocking_vulnerabilities() {
  local severity="${1:-${INFEROPS_SCAN_BLOCKING_SEVERITY}}"
  inferops::security::require_cmd trivy
  mkdir -p "${INFEROPS_SECURITY_ARTIFACT_DIR}"
  inferops::security::log "scanning uv.lock (including dev and check groups) for ${severity} findings"
  (
    cd "${INFEROPS_SECURITY_ROOT}" && trivy fs \
      --scanners vuln \
      --include-dev-deps \
      --severity "${severity}" \
      --exit-code 1 \
      --format json \
      --output "${INFEROPS_SECURITY_ARTIFACT_DIR}/dependency-scan.json" \
      .
  ) ||
    inferops::security::fail "uv.lock carries a ${severity} finding with no recorded exception; see ${INFEROPS_SECURITY_ARTIFACT_DIR}/dependency-scan.json"
}
