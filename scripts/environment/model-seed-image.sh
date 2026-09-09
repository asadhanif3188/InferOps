#!/usr/bin/env bash
# Builds an image carrying the pinned model artifact, and loads it into this
# project's cluster.
#
# Why this exists. The acquisition job's committed source is `download`, and that
# is right for a fresh checkout: everything it needs is public and pinned. It is
# wrong for a host that already holds the artifact, which would then transfer
# 1.71 GiB again over a transport whose certificate this project does not
# validate. Under `model.acquisition.source: seed-image` the job reads the
# artifact out of this image instead. The job is still the only thing that writes
# the claim -- this changes where it reads, not who writes.
#
# The artifact is taken from the workspace cache, which is where
# `python -m tools.model_acquisition` puts it and where
# docs/serving/model-source.v1.json says it lives. It is verified here before it
# is baked in, and verified again inside the cluster by the job, because a hash
# checked once on a host says nothing about the bytes that reached a node.
#
# Usage:
#   scripts/environment/model-seed-image.sh build
#   scripts/environment/model-seed-image.sh load
#   scripts/environment/model-seed-image.sh values > .artifacts/model-seed-values.yaml

# shellcheck source=scripts/environment/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

readonly INFEROPS_SEED_IMAGE_REPOSITORY="localhost/inferops-model-seed"
readonly INFEROPS_SEED_DOCKERFILE_REL="deploy/model-seed/Dockerfile"
readonly INFEROPS_MODEL_SOURCE_REL="docs/serving/model-source.v1.json"
readonly INFEROPS_MODEL_CACHE_REL=".cache/inferops/models"

action="${1:-}"
[ -n "${action}" ] ||
  inferops::fail "expected one of build, load, digest, values. Usage: model-seed-image.sh build|load|digest|values"

inferops::require_cmd python

# Every pin comes from the accepted source record rather than from this script.
# A downloader and a seeder that disagreed about which bytes are correct would be
# two definitions of the artifact, and the one that drifted would be whichever
# nobody read.
#
# The carriage returns are stripped because a Windows Python writes CRLF, and a
# path carrying a trailing CR is a path that does not exist -- which presents as
# the artifact being absent when it is sitting right there.
read_source() {
  python -c "
import json, pathlib, sys
record = json.loads(pathlib.Path(sys.argv[1]).read_text(encoding='utf-8'))
print(record['revision'])
print(record['file'])
print(record['expectedSizeBytes'])
print(record['sha256'].removeprefix('sha256:'))
print(record['cache']['artifactRelativePath'])
" "$(inferops::native_path "${INFEROPS_ROOT}/${INFEROPS_MODEL_SOURCE_REL}")"
}

{
  read -r model_revision
  read -r model_file
  read -r model_bytes
  read -r model_sha
  read -r model_relative
} < <(read_source | tr -d '\r')

# Each of them, not just one. A process substitution's exit status does not
# reach `set -e`, so a Python that died halfway through printing leaves some of
# these set and some empty, and the empty one is whichever line it died before.
for required in "${model_revision}" "${model_file}" "${model_bytes}" \
  "${model_sha}" "${model_relative}"; do
  [ -n "${required}" ] ||
    inferops::fail "could not read the pinned artifact out of ${INFEROPS_MODEL_SOURCE_REL}"
done

readonly INFEROPS_SEED_IMAGE_REF="${INFEROPS_SEED_IMAGE_REPOSITORY}:${model_revision}"
artifact="${INFEROPS_ROOT}/${INFEROPS_MODEL_CACHE_REL}/${model_relative}"
context_dir="$(dirname "${artifact}")"

# The manifest digest, for the same reason api-image.sh reads it: a
# `repository@digest` reference resolves by the manifest digest, and `.Id` is the
# config digest on a graphdriver-backed daemon.
inferops::seed_image_digest() {
  local digest
  digest="$(docker image inspect "${INFEROPS_SEED_IMAGE_REF}" \
    --format '{{range .RepoDigests}}{{.}} {{end}}' 2>/dev/null |
    tr ' ' '\n' | sed -n 's|^.*@||p' | head -1 || true)"
  [[ "${digest}" =~ ^sha256:[0-9a-f]{64}$ ]] || return 1
  printf '%s' "${digest}"
}

case "${action}" in
  build)
    inferops::require_engine
    inferops::require_cmd sha256sum

    [ -f "${artifact}" ] ||
      inferops::fail "no artifact at ${INFEROPS_MODEL_CACHE_REL}/${model_relative}. Acquire it first: python -m tools.model_acquisition"

    # Verified before it is baked in. An image built from a corrupt artifact
    # would be a seed that fails inside the cluster instead of on the host, and
    # the host is where it is cheap to find out.
    inferops::section "verify the artifact this image will carry"
    present="$(wc -c <"${artifact}" | tr -d ' ')"
    [ "${present}" = "${model_bytes}" ] ||
      inferops::fail "the cached artifact is ${present} bytes and the record pins ${model_bytes}"
    printf '%s  %s\n' "${model_sha}" "${artifact}" | sha256sum -c - >/dev/null ||
      inferops::fail "the cached artifact does not match the pinned SHA-256"
    inferops::log "artifact verified: ${model_bytes} bytes, SHA-256 matches ${INFEROPS_MODEL_SOURCE_REL}"

    inferops::section "docker build"
    # The context is the revision directory and nothing above it, so the build
    # is handed the artifact and no other part of the workspace.
    docker build \
      -f "$(inferops::native_path "${INFEROPS_ROOT}/${INFEROPS_SEED_DOCKERFILE_REL}")" \
      -t "${INFEROPS_SEED_IMAGE_REF}" \
      "$(inferops::native_path "${context_dir}")"

    digest="$(inferops::seed_image_digest)" ||
      inferops::fail "the build reported success and no manifest digest can be read for ${INFEROPS_SEED_IMAGE_REF}. Enable the containerd image store and build again."
    inferops::log "built ${INFEROPS_SEED_IMAGE_REF}"
    inferops::log "digest ${digest}"
    ;;

  load)
    inferops::require_cmd kind
    inferops::require_engine
    inferops::assert_target_cluster

    digest="$(inferops::seed_image_digest)" ||
      inferops::fail "no image at ${INFEROPS_SEED_IMAGE_REF}. Build it first: scripts/environment/model-seed-image.sh build"

    inferops::section "kind load docker-image"
    kind load docker-image "${INFEROPS_SEED_IMAGE_REF}" \
      --name "${INFEROPS_CLUSTER_NAME}"

    inferops::section "verify the reference the chart will use"
    if ! docker exec "${INFEROPS_CLUSTER_NAME}-control-plane" \
      crictl inspecti "${INFEROPS_SEED_IMAGE_REPOSITORY}@${digest}" >/dev/null 2>&1; then
      inferops::fail "the image loaded and '${INFEROPS_SEED_IMAGE_REPOSITORY}@${digest}' does not resolve inside the node. Deploying it would fail as ErrImageNeverPull."
    fi

    inferops::log "loaded into '${INFEROPS_CLUSTER_NAME}'; the digest reference resolves inside the node."
    inferops::warn "this image carries ${model_bytes} bytes of model weights and now occupies that much inside the node as well as the claim it fills. Deleting the cluster reclaims both."
    ;;

  digest)
    inferops::require_engine
    digest="$(inferops::seed_image_digest)" ||
      inferops::fail "no image at ${INFEROPS_SEED_IMAGE_REF}. Build it first: scripts/environment/model-seed-image.sh build"
    printf '%s\n' "${digest}"
    ;;

  values)
    inferops::require_engine
    digest="$(inferops::seed_image_digest)" ||
      inferops::fail "no image at ${INFEROPS_SEED_IMAGE_REF}. Build it first: scripts/environment/model-seed-image.sh build"
    # An overlay, not an edit of a committed file: the digest is one host's build.
    # `sourceUrl` is cleared because the chart refuses a values file that names
    # both a seed image and a download URL -- one of the two describes where the
    # bytes come from, and a file naming both leaves a reader to guess.
    cat <<YAML
# Generated by scripts/environment/model-seed-image.sh. Host state, not evidence.
# Pass alongside charts/inferops-llm/ci/real-values.yaml, after it.
model:
  artifact:
    sourceUrl: ""
  acquisition:
    source: seed-image
    seedImage:
      repository: ${INFEROPS_SEED_IMAGE_REPOSITORY}
      digest: ${digest}
      pullPolicy: Never
      artifactPath: /seed
YAML
    ;;

  *)
    inferops::fail "unknown argument '${action}'. Usage: model-seed-image.sh build|load|digest|values"
    ;;
esac
