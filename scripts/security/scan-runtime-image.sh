#!/usr/bin/env bash
# Scans the pinned runtime image for known vulnerabilities.
#
# Contributor-run, like every check in this repository: no continuous-
# integration service runs this, ADR 0005 D6 leaves that undecided, and a
# result here is current only as of the machine and the moment that ran it.
#
# Usage:
#   scripts/security/scan-runtime-image.sh [SEVERITY]
#
# SEVERITY defaults to the committed blocking threshold (CRITICAL,HIGH).
# Passing a lower threshold is how the guard's rejection path is exercised
# deliberately, against the real image, without inventing a fixture.

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./lib.sh
source "${SCRIPT_DIR}/lib.sh"

inferops::security::assert_runtime_image_has_no_blocking_vulnerabilities "$@"
inferops::security::log "no ${1:-${INFEROPS_SCAN_BLOCKING_SEVERITY}} finding in the pinned runtime image"
