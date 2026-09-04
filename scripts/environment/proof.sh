#!/usr/bin/env bash
# Runs the whole environment proof end to end, from a clean state to a clean
# state: preflight, create, smoke, measure, tear down, verify residue.
#
# DESTRUCTIVE. It creates and then deletes the inferops-dev cluster. Run it only
# when you intend both.
#
# It is one script rather than a note in a document because "repeatable" has to
# mean a contributor can reproduce the sequence exactly, not approximately.
#
# Usage:
#   scripts/environment/proof.sh            # one full cycle
#   scripts/environment/proof.sh --cycles 2 # repeat from a clean state, to show it repeats

# shellcheck source=scripts/environment/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

cycles=1
while [ "$#" -gt 0 ]; do
  case "$1" in
    --cycles)
      # Checked before shifting: `--cycles` with nothing after it would
      # otherwise consume the last argument and leave the trailing shift to
      # fail, killing the script under errexit with no explanation at all.
      [ "$#" -ge 2 ] || inferops::fail "--cycles needs a value. Usage: proof.sh [--cycles N]"
      cycles="$2"
      shift
      ;;
    *) inferops::fail "unknown argument '$1'. Usage: proof.sh [--cycles N]" ;;
  esac
  shift
done

case "${cycles}" in
  '' | *[!0-9]*) inferops::fail "--cycles needs a positive whole number." ;;
esac
[ "${cycles}" -ge 1 ] || inferops::fail "--cycles needs a positive whole number."

here="$(dirname "${BASH_SOURCE[0]}")"

inferops::section "Environment proof: ${cycles} cycle(s)"
inferops::log "started at $(date -u '+%Y-%m-%dT%H:%M:%SZ')"

"${here}/preflight.sh"

cycle=1
while [ "${cycle}" -le "${cycles}" ]; do
  inferops::section "Cycle ${cycle} of ${cycles}: create"
  # --recreate so that a cluster left by an interrupted earlier run cannot make
  # a later cycle silently reuse stale state.
  "${here}/cluster-up.sh" --recreate

  inferops::section "Cycle ${cycle} of ${cycles}: verify"
  # Creation already ran this once. Running it again here, on its own, is what
  # makes "verify is repeatable" a result rather than a claim: the same read-only
  # script against the same cluster has to reach the same answer.
  "${here}/cluster-verify.sh"

  inferops::section "Cycle ${cycle} of ${cycles}: smoke"
  "${here}/smoke.sh"

  inferops::section "Cycle ${cycle} of ${cycles}: partial teardown"
  "${here}/cluster-down.sh" --workload

  inferops::section "Cycle ${cycle} of ${cycles}: full teardown"
  "${here}/cluster-down.sh"

  cycle=$((cycle + 1))
done

inferops::section "Proof complete"
inferops::log "finished at $(date -u '+%Y-%m-%dT%H:%M:%SZ')"
inferops::log "${cycles} cycle(s) created, exercised, and torn down with no unexpected residue."
