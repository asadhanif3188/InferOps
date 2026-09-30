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
# accepted exception is recorded against a specific finding.
readonly INFEROPS_SCAN_BLOCKING_SEVERITY="CRITICAL,HIGH"

# The findings each guard accepts rather than blocks on, one Trivy ignore file
# per scan so that an exception argued for the image cannot silence the same
# identifier in the lockfile. Every identifier in them is an exception in the
# security baseline, and tests/security/ compares the two in both directions.
readonly INFEROPS_RUNTIME_IMAGE_ACCEPTED_FINDINGS_REL="scripts/security/runtime-image.trivyignore"
readonly INFEROPS_DEPENDENCY_ACCEPTED_FINDINGS_REL="scripts/security/dependencies.trivyignore"

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

# --- Accepted findings -------------------------------------------------------

# The absolute path of a committed ignore file, refused rather than handed to
# Trivy when it could accept more than its exceptions argued:
#
#   - it is missing. Trivy stops with an error then, which the guards below
#     would otherwise report as a finding;
#   - an entry is anything but one finding identifier and an expiry date.
#     Trivy stops suppressing an entry on its date, so an exception cannot
#     outlive its review deadline without the guard blocking again;
#   - SUBJECT is given, the file accepts a finding, and its `# assessed-image:`
#     line names any other image. An exception is argued for the bytes behind
#     one digest and says nothing about the next.
#
# Usage: accepted_findings_file RELATIVE_PATH [SUBJECT]
inferops::security::accepted_findings_file() {
  local rel="$1" subject="${2:-}"
  local path="${INFEROPS_SECURITY_ROOT}/${rel}"
  [ -f "${path}" ] ||
    inferops::security::fail "${rel} is not committed; it lists the findings accepted as exceptions, and an empty one accepts none"
  local line accepts=""
  while IFS= read -r line || [ -n "${line}" ]; do
    line="${line%$'\r'}"
    [[ "${line}" =~ ^[[:space:]]*(#|$) ]] && continue
    [[ "${line}" =~ ^(CVE-[0-9]{4}-[0-9]{4,}|GHSA-[0-9a-z]{4}-[0-9a-z]{4}-[0-9a-z]{4})\ exp:[0-9]{4}-[0-9]{2}-[0-9]{2}$ ]] ||
      inferops::security::fail "${rel} has an entry that is not one finding identifier followed by exp:YYYY-MM-DD"
    accepts=1
  done <"${path}"
  if [ -n "${accepts}" ] && [ -n "${subject}" ]; then
    local assessed
    assessed="$(sed -n -E 's/^# assessed-image: ([^[:space:]]+)[[:space:]]*$/\1/p' "${path}")"
    [ "${assessed}" = "${subject}" ] ||
      inferops::security::fail "${rel} accepts findings assessed against '${assessed:-no image}', and the runtime contract pins ${subject}; re-assess them against the pinned image before this guard will scan it"
  fi
  printf '%s' "${path}"
}

# Names every finding an ignore file lists, and whether Trivy will still accept
# it: an entry stops suppressing from the start of its expiry date, UTC, and the
# finding blocks again. A scan that starts failing on that date has then already
# said why. The entries were checked by accepted_findings_file before this reads
# them.
#
# Usage: log_accepted_findings RELATIVE_PATH
inferops::security::log_accepted_findings() {
  local id expiry today
  today="$(date -u +%Y-%m-%d)"
  while read -r id expiry; do
    expiry="${expiry#exp:}"
    if [[ "${today}" < "${expiry}" ]]; then
      inferops::security::log "accepting ${id} as listed in $1; it blocks again from ${expiry}"
    else
      inferops::security::log "not accepting ${id}: its entry in $1 expired on ${expiry}; re-assess it or remove it"
    fi
  done < <(sed -e 's/\r$//' -e '/^[[:space:]]*#/d' -e '/^[[:space:]]*$/d' "${INFEROPS_SECURITY_ROOT}/$1")
}

# --- Guards -------------------------------------------------------------

# Scans the pinned runtime image for known vulnerabilities and refuses to
# report success when a finding at or above the blocking severity turns up
# that is not an accepted exception. The accepted ones are read from the
# committed ignore file, and only while it was assessed against the image the
# runtime contract pins; nothing here writes one. An exception is recorded by
# hand in the security baseline, the way every other exception in this
# repository is, and a suppressed finding stays in the scan output.
inferops::security::assert_runtime_image_has_no_blocking_vulnerabilities() {
  local severity="${1:-${INFEROPS_SCAN_BLOCKING_SEVERITY}}"
  inferops::security::require_cmd trivy
  local image accepted
  image="$(inferops::security::runtime_image_reference)"
  accepted="$(inferops::security::accepted_findings_file "${INFEROPS_RUNTIME_IMAGE_ACCEPTED_FINDINGS_REL}" "${image}")"
  mkdir -p "${INFEROPS_SECURITY_ARTIFACT_DIR}"
  inferops::security::log "scanning ${image} for ${severity} findings"
  inferops::security::log_accepted_findings "${INFEROPS_RUNTIME_IMAGE_ACCEPTED_FINDINGS_REL}"
  trivy image \
    --scanners vuln \
    --severity "${severity}" \
    --ignorefile "${accepted}" \
    --show-suppressed \
    --exit-code 1 \
    --format json \
    --output "${INFEROPS_SECURITY_ARTIFACT_DIR}/runtime-image-scan.json" \
    "${image}" ||
    inferops::security::fail "${image} carries a ${severity} finding that no unexpired entry in ${INFEROPS_RUNTIME_IMAGE_ACCEPTED_FINDINGS_REL} accepts, or Trivy could not finish the scan; see ${INFEROPS_SECURITY_ARTIFACT_DIR}/runtime-image-scan.json and the output above"
}

# Scans the committed dependency lockfile, including the `test` and `checks`
# groups - the only Python dependencies pinned anywhere in this repository,
# since the published distribution declares none - and refuses to report
# success on the same terms as the guard above.
inferops::security::assert_dependencies_have_no_blocking_vulnerabilities() {
  local severity="${1:-${INFEROPS_SCAN_BLOCKING_SEVERITY}}"
  inferops::security::require_cmd trivy
  local accepted
  accepted="$(inferops::security::accepted_findings_file "${INFEROPS_DEPENDENCY_ACCEPTED_FINDINGS_REL}")"
  mkdir -p "${INFEROPS_SECURITY_ARTIFACT_DIR}"
  inferops::security::log "scanning uv.lock (including the test and checks groups) for ${severity} findings"
  inferops::security::log_accepted_findings "${INFEROPS_DEPENDENCY_ACCEPTED_FINDINGS_REL}"
  (
    cd "${INFEROPS_SECURITY_ROOT}" && trivy fs \
      --scanners vuln \
      --include-dev-deps \
      --severity "${severity}" \
      --ignorefile "${accepted}" \
      --show-suppressed \
      --exit-code 1 \
      --format json \
      --output "${INFEROPS_SECURITY_ARTIFACT_DIR}/dependency-scan.json" \
      .
  ) ||
    inferops::security::fail "uv.lock carries a ${severity} finding that no unexpired entry in ${INFEROPS_DEPENDENCY_ACCEPTED_FINDINGS_REL} accepts, or Trivy could not finish the scan; see ${INFEROPS_SECURITY_ARTIFACT_DIR}/dependency-scan.json and the output above"
}
