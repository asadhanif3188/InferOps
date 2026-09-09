# The InferOps platform API container image.
#
# `platform-api-container-image` in the ownership inventory: owned by the
# contributor's host, built locally and loaded straight into the cluster. It is
# published to no registry, which is why the chart's values carry a digest the
# builder records rather than one a registry hands out.
#
# What goes in is the application and the two modules that carry it, and nothing
# else. `src/inferops` has no runtime dependency at all -- `pyproject.toml`
# declares `dependencies = []` and the API imports no framework, by ADR 0004 --
# so this installs nothing and there is no wheel, no resolver, and no lock file
# in the build. `tools/api_carrier` is the standard-library HTTP carrier and
# `tools/api_container` is the entrypoint. The rest of `tools/` is host tooling
# -- a model downloader, a container packager, a manifest reader -- and a serving
# container has no business holding any of it, which is why the carrier was moved
# out of `tools/local_composition` rather than copied along with its neighbours.
#
# Build and load, from the repository root:
#
#   docker build -f deploy/api/Dockerfile -t inferops-api:dev .
#   kind load docker-image inferops-api:dev --name inferops-dev
#
# Then read back the digest the chart has to reference:
#
#   docker image inspect inferops-api:dev --format '{{ index .Id }}'
#
# `kind load` is what makes a registry unnecessary: it copies the image into the
# node's own containerd, and `imagePullPolicy: Never` in the real values then
# stops the kubelet trying to fetch a reference that exists nowhere else. An
# image that is not loaded fails as `ErrImageNeverPull`, which is the honest
# failure -- unlike a pull policy that would reach the network for a name no
# registry serves.

# Pinned by digest, like every other image this project runs. The tag is a label
# for humans; the digest is the thing.
FROM python:3.12-slim@sha256:78387bc3881b8273120a12ebe6c1ab22b018ccc2c9adf565ae1ac9b536e184ea

# No bytecode, because the root filesystem is read-only at runtime and a
# writable `__pycache__` is not available to write into. Unbuffered, because a
# container's logs are read from its streams and a buffered record is a record
# that arrives after the crash it was describing.
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/opt/inferops/src:/opt/inferops

WORKDIR /opt/inferops

COPY src/inferops /opt/inferops/src/inferops
COPY tools/__init__.py /opt/inferops/tools/__init__.py
COPY tools/api_carrier /opt/inferops/tools/api_carrier
COPY tools/api_container /opt/inferops/tools/api_container

# The serving address, stated here and overridable by the deployment. The
# entrypoint requires both and defaults neither, so this is the statement rather
# than a fallback: a container is reached through its pod's network namespace by
# a ClusterIP Service and by the kubelet's probes, and binding loopback would
# make it reachable by nothing. The host composition's loopback rule is a
# separate boundary in `tools/local_composition/core.py` and is untouched.
ENV INFEROPS_BIND_HOST=0.0.0.0 \
    INFEROPS_BIND_PORT=8090

# 65534 is the uid, gid and fsGroup the chart's pod security context sets. Named
# here as well so that `docker run` without Kubernetes exercises the same user
# the cluster will, rather than passing as root and failing only once deployed.
USER 65534:65534

EXPOSE 8090

# Exec form, so the entrypoint is PID 1 and receives SIGTERM directly. The shell
# form would put `/bin/sh` at PID 1, and it would not forward the signal -- which
# is the usual reason a pod takes its entire termination grace period and is then
# killed on every rollout.
ENTRYPOINT ["python", "-m", "tools.api_container"]
