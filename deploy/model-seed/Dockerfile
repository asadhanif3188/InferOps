# An image carrying the pinned model artifact, for filling a claim without a
# network transfer.
#
# The acquisition job's default source is `download`, which is the path a fresh
# checkout can run: the URL, the byte count and the hash all come from
# docs/serving/model-source.v1.json and all of them are public. This is the other
# path. A host that already holds the verified artifact -- because
# `python -m tools.model_acquisition` put it in the workspace cache -- has no
# reason to fetch 1.71 GiB again over a transport whose certificate this project
# does not validate.
#
# **It does not make a second writer.** The acquisition job is still the only
# thing that writes the claim; this only changes where it reads from. That
# matters, because `docs/architecture/resource-ownership.md` calls that job the
# single sanctioned handoff in the design, and a host-side seeder writing the
# claim directly would have been a second one.
#
# The base is BusyBox at the same digest the chart already pins four times over,
# because this image *is* the job's image under `seed-image`: the script it runs
# needs `sh`, `stat` and `sha256sum`, and reusing the pin means there is not a
# fifth copy of it to drift.
#
# **This image is never pushed.** It carries 1.71 GiB of model weights and its
# digest describes one host's build, so it is loaded into the node and its
# reference goes into an ignored overlay -- exactly like the API image. Nothing
# about it is committed except this file.
#
# The build context is the revision directory of the workspace cache, so the
# `COPY` below takes the artifact and nothing else:
#
#   scripts/environment/model-seed-image.sh build
FROM docker.io/library/busybox@sha256:9db7b59979c38555a39def84a31fb98b5296952f9e3afd4f6f11f05b07adfab0

# `/seed` is `model.acquisition.seedImage.artifactPath`. The job reads
# `<artifactPath>/<artifact.fileName>` from here and copies it into the claim,
# then verifies byte count and SHA-256 before renaming -- the same verification
# the download path performs, because it is the same script either way. A
# corrupted or wrong artifact baked in here is refused at that point rather than
# trusted for having come from an image.
COPY . /seed/
