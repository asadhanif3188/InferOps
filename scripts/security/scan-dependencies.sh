#!/usr/bin/env bash
# Scans the committed dependency lockfile for known vulnerabilities.
#
# Scans uv.lock including its `test` and `checks` dependency groups: the published
# distribution declares no runtime dependency (pyproject.toml says so
# explicitly), so those groups are the only Python dependencies this
# repository pins anywhere.
#
# Contributor-run, like every check in this repository: no continuous-
# integration service runs this, and ADR 0005 D6 leaves that undecided.
#
# Usage:
#   scripts/security/scan-dependencies.sh [SEVERITY]
#
# SEVERITY defaults to the committed blocking threshold (CRITICAL,HIGH).

set -Eeuo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=./lib.sh
source "${SCRIPT_DIR}/lib.sh"

inferops::security::assert_dependencies_have_no_blocking_vulnerabilities "$@"
inferops::security::log "no ${1:-${INFEROPS_SCAN_BLOCKING_SEVERITY}} finding in uv.lock"
