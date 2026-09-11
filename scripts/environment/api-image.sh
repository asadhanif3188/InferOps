#!/usr/bin/env bash
# Builds the InferOps API image and loads it into this project's cluster.
#
# `platform-api-container-image` in the ownership inventory is owned by the
# contributor's host: built locally, loaded straight into the node, published to
# no registry. That ownership is the reason this script exists rather than a
# registry reference in the chart's values.
#
# Why the digest is read back rather than written down. The chart pins every
# image by digest and its schema refuses anything else, which is right: a tag is
# a name somebody can move. But an image that was never pushed has no registry
# digest to look up, and the value that stood in `ci/real-values.yaml` until now
# was the SHA-256 of the ASCII string `inferops-api-image-not-yet-published` --
# honest as a placeholder, and not a digest of anything. So the digest here is
# taken from the image that was actually built, after it was actually built, and
# an operator writes *that* into their deployment values. Nothing in this
# repository commits a digest for an image nobody can verify.
#
# Usage:
#   scripts/environment/api-image.sh build
#   scripts/environment/api-image.sh load
#   scripts/environment/api-image.sh digest
#   scripts/environment/api-image.sh values > .artifacts/api-image-values.yaml

# shellcheck source=scripts/environment/lib.sh
source "$(dirname "${BASH_SOURCE[0]}")/lib.sh"

readonly INFEROPS_API_IMAGE_REPOSITORY="localhost/inferops-api"
readonly INFEROPS_API_IMAGE_TAG="dev"
readonly INFEROPS_API_IMAGE_REF="${INFEROPS_API_IMAGE_REPOSITORY}:${INFEROPS_API_IMAGE_TAG}"
readonly INFEROPS_API_DOCKERFILE_REL="deploy/api/Dockerfile"

action="${1:-}"
[ -n "${action}" ] ||
  inferops::fail "expected one of build, load, digest, values. Usage: api-image.sh build|load|digest|values"

# The digest of the image that is actually present, or nothing when it is not
# built. Prints nothing and returns 1 rather than printing an empty string, so
# that a caller cannot mistake "not built" for a digest.
#
# `RepoDigests` and not `.Id`, and the difference is the whole correctness of
# this script. A `repository@digest` reference -- which is what the chart builds
# and what containerd resolves inside the node -- resolves by the *manifest*
# digest. `.Id` is the image *config* digest on a graphdriver-backed daemon, a
# different hash entirely, and equals the manifest digest only where the
# containerd image store is in use. Handing the config digest to the chart would
# build a reference that is well-formed, unresolvable, and fails at schedule time
# as ErrImageNeverPull -- long after the build appeared to succeed. So the
# manifest digest is what is read, and a daemon that cannot supply one refuses
# here rather than three steps later.
inferops::api_image_digest() {
  local digest
  digest="$(docker image inspect "${INFEROPS_API_IMAGE_REF}" \
    --format '{{range .RepoDigests}}{{.}} {{end}}' 2>/dev/null |
    tr ' ' '\n' | sed -n 's|^.*@||p' | head -1 || true)"
  [[ "${digest}" =~ ^sha256:[0-9a-f]{64}$ ]] || return 1
  printf '%s' "${digest}"
}

case "${action}" in
  build)
    inferops::require_engine

    dockerfile="${INFEROPS_ROOT}/${INFEROPS_API_DOCKERFILE_REL}"
    [ -f "${dockerfile}" ] ||
      inferops::fail "no Dockerfile at ${INFEROPS_API_DOCKERFILE_REL}"

    inferops::section "docker build"
    # The repository root is the build context, because the image copies the
    # application from `src/` and its carrier from `tools/`. `.dockerignore`
    # keeps the model cache, the virtual environment and the artifact directory
    # out of it -- without that, the context would include 1.71 GiB of weights.
    docker build \
      -f "$(inferops::native_path "${dockerfile}")" \
      -t "${INFEROPS_API_IMAGE_REF}" \
      "$(inferops::native_path "${INFEROPS_ROOT}")"

    digest="$(inferops::api_image_digest)" ||
      inferops::fail "the build reported success and no manifest digest can be read for ${INFEROPS_API_IMAGE_REF}. A daemon using the classic graphdriver image store publishes none for an image that was never pushed, and the config digest it does publish is not a reference Kubernetes can resolve. Enable the containerd image store and build again."
    inferops::log "built ${INFEROPS_API_IMAGE_REF}"
    inferops::log "digest ${digest}"
    inferops::log "load it into the cluster with: scripts/environment/api-image.sh load"
    ;;

  load)
    inferops::require_engine
    # The provider-aware target this project consumes rather than creates
    # (docs/environment/local-cluster-provider-contract.md). `kind load` names a
    # cluster and would happily name somebody else's, so this re-verifies the
    # explicitly selected target before touching it.
    inferops::resolve_target
    inferops::require_target_capability imagePreparation kind-load \
      "${INFEROPS_TARGET_IMAGE_PREPARATION}"

    inferops::api_image_digest >/dev/null ||
      inferops::fail "no image at ${INFEROPS_API_IMAGE_REF}. Build it first: scripts/environment/api-image.sh build"

    digest="$(inferops::api_image_digest)" ||
      inferops::fail "no manifest digest for ${INFEROPS_API_IMAGE_REF}; build it again"

    inferops::section "kind load docker-image"
    kind load docker-image "${INFEROPS_API_IMAGE_REF}" \
      --name "${INFEROPS_TARGET_CLUSTER_NAME}"

    # The load is not the claim. What the chart asks containerd for is
    # `repository@digest`, so that exact reference is resolved inside the node
    # before anything reports the image available. A load that succeeded and a
    # reference that does not resolve is the failure this catches, and catching
    # it here costs one command instead of a rollout that never schedules.
    inferops::section "verify the reference the chart will use"
    if ! docker exec "${INFEROPS_TARGET_CLUSTER_NAME}-control-plane" \
      crictl inspecti "${INFEROPS_API_IMAGE_REPOSITORY}@${digest}" >/dev/null 2>&1; then
      inferops::fail "the image loaded and '${INFEROPS_API_IMAGE_REPOSITORY}@${digest}' does not resolve inside the node. Deploying it would fail as ErrImageNeverPull. Do not write this digest into any values file."
    fi

    inferops::log "loaded into '${INFEROPS_TARGET_CLUSTER_NAME}'; the digest reference resolves inside the node. The real values must set api.image.pullPolicy: Never, so that a reference no registry serves is never fetched."
    ;;

  digest)
    inferops::require_engine
    digest="$(inferops::api_image_digest)" ||
      inferops::fail "no image at ${INFEROPS_API_IMAGE_REF}. Build it first: scripts/environment/api-image.sh build"
    printf '%s\n' "${digest}"
    ;;

  values)
    inferops::require_engine
    digest="$(inferops::api_image_digest)" ||
      inferops::fail "no image at ${INFEROPS_API_IMAGE_REF}. Build it first: scripts/environment/api-image.sh build"
    # A values overlay, not an edit of a committed file. The digest describes one
    # host's build and belongs in .artifacts/, which version control ignores.
    cat <<YAML
# Generated by scripts/environment/api-image.sh. Host state, not evidence.
# The digest is the image built on this host; it exists in no registry.
api:
  image:
    repository: ${INFEROPS_API_IMAGE_REPOSITORY}
    digest: ${digest}
    pullPolicy: Never
YAML
    ;;

  *)
    inferops::fail "unknown argument '${action}'. Usage: api-image.sh build|load|digest|values"
    ;;
esac
