#!/usr/bin/env bash
# Generates a CycloneDX software bill of materials for the pinned runtime
# image and for the committed dependency lockfile.
#
# Writes to .artifacts/security/, which version control ignores. Promoting a
# copy into docs/proof/security/sbom/ is a deliberate, separate step - ADR
# 0005 D5's evidence-retention rule is that raw lane output is not committed
# as-is; a chosen, reviewed copy is.

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./lib.sh
source "${SCRIPT_DIR}/lib.sh"

inferops::security::require_cmd trivy
mkdir -p "${INFEROPS_SECURITY_ARTIFACT_DIR}"

image="$(inferops::security::runtime_image_reference)"
inferops::security::log "generating an SBOM for ${image}"
trivy image \
  --format cyclonedx \
  --output "${INFEROPS_SECURITY_ARTIFACT_DIR}/runtime-image.cyclonedx.json" \
  "${image}"

inferops::security::log "generating an SBOM for uv.lock (including dev and check groups)"
(
  cd "${INFEROPS_SECURITY_ROOT}" && trivy fs \
    --include-dev-deps \
    --format cyclonedx \
    --output "${INFEROPS_SECURITY_ARTIFACT_DIR}/python-dependencies.cyclonedx.json" \
    .
)

inferops::security::log "wrote ${INFEROPS_SECURITY_ARTIFACT_DIR}/runtime-image.cyclonedx.json and .../python-dependencies.cyclonedx.json"
