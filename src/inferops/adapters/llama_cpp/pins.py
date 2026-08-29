"""The runtime and model this project selected, pinned rather than described.

Every constant here is copied from an accepted record and from nothing else:
the runtime image digest and the model revision, file, size, and hash are
`ADR 0002`'s decision, and the build string is the one the trial in the
feasibility record read back from the running process. Nothing in this module
resolves a tag, contacts a registry, or reads a file — the pins are values, and
the check that they still agree with the accepted records is a test, because a
constant nobody compares to its source is a copy that drifts.

**A pin is an identity, not a verification.** Holding the model's hash is not
the same as having computed it. What ties a running process to these bytes is
the SHA-256 verified on the file before it was mounted, the file being mounted
read-only, and the runtime's self-reported parameter count and quantisation
agreeing with the published model. The runtime exposes no hash of the file it
loaded, so no single check closes that gap, and this module does not pretend
one does.
"""

from __future__ import annotations

from dataclasses import dataclass

#: The registered runtime identifier, as the compatibility matrix publishes it.
LLAMA_SERVER_RUNTIME_ID = "llama-cpp-server"

#: The runtime's display name, as the same matrix row publishes it. This is what
#: a :class:`~inferops.domain.serving.RuntimeMetadata` reports as its name.
LLAMA_SERVER_RUNTIME_NAME = "llama.cpp llama-server"

#: The serving capability a ``synchronous-llm`` workload binds to. The mock's
#: half of the same pairing is ``inferops-mock-serving``, and the two are
#: disjoint on purpose.
LLAMA_SERVER_SERVING_CAPABILITY = "inferops-native-serving"

#: The adapter kind a result served by this runtime declares. It is a constant
#: rather than a setting for the same reason the mock's is: an adapter that
#: could be configured to name itself the other kind is the failure the closed
#: vocabulary exists to prevent.
LLAMA_SERVER_ADAPTER_KIND = "real"

#: The published image repository. Pinned by digest below, never by tag: ADR
#: 0002 records that this publisher ships from a branch tip with no versioned
#: tag scheme and rebuilds the ``server`` tag on a schedule.
PINNED_IMAGE_REPOSITORY = "ghcr.io/ggml-org/llama.cpp"

#: The multi-architecture index digest the trial ran, read back from the running
#: pod rather than trusted from the manifest.
PINNED_IMAGE_DIGEST = (
    "sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384"
)

#: Repository and digest joined into the reference a workload document carries.
PINNED_IMAGE_REFERENCE = f"{PINNED_IMAGE_REPOSITORY}@{PINNED_IMAGE_DIGEST}"

#: The build string the running process reported for that image, once, on one
#: host. It is an observation and not a pin: the digest is what identifies the
#: bytes, and this is what the process says about itself.
OBSERVED_BUILD_INFO = "b10588-70adb1b4c"

#: The model repository, revision, file, size, and published hash. The revision
#: names what the publisher said it published; the hash names what arrived.
PINNED_MODEL_REPOSITORY = "Qwen/Qwen3-1.7B-GGUF"
PINNED_MODEL_REVISION = "90862c4b9d2787eaed51d12237eafdfe7c5f6077"
PINNED_MODEL_FILE = "Qwen3-1.7B-Q8_0.gguf"
PINNED_MODEL_SIZE_BYTES = 1834426016
PINNED_MODEL_SHA256 = (
    "sha256:061b54daade076b5d3362dac252678d17da8c68f07560be70818cace6590cb1a"
)

#: The artifact format this runtime loads, as the compatibility matrix names it.
#: The runtime reads no other format without a conversion step, and a conversion
#: step produces different bytes with a different hash.
PINNED_ARTIFACT_FORMAT = "gguf"

#: The accepted records these values are copied from.
RUNTIME_DECISION_REF = (
    "docs/architecture/decisions/ADR-0002-model-and-serving-runtime.md"
)
RUNTIME_FEASIBILITY_REF = "docs/proof/serving/v1-s0-003-pr2-runtime-feasibility.md"
COMPATIBILITY_MATRIX_REF = (
    "contracts/workload/compatibility/runtime-model-compatibility.v1alpha1.json"
)


@dataclass(frozen=True, slots=True)
class RuntimePin:
    """The runtime identity a configuration is required to match."""

    runtime_id: str
    name: str
    repository: str
    digest: str
    decision_ref: str

    @property
    def reference(self) -> str:
        """Repository and digest, in the form a workload document carries."""
        return f"{self.repository}@{self.digest}"


@dataclass(frozen=True, slots=True)
class ModelPin:
    """The model identity and bytes a configuration is required to match."""

    repository: str
    revision: str
    file: str
    size_bytes: int
    sha256: str
    artifact_format: str
    decision_ref: str


#: The pinned runtime, as one value a caller can pass around.
PINNED_RUNTIME = RuntimePin(
    runtime_id=LLAMA_SERVER_RUNTIME_ID,
    name=LLAMA_SERVER_RUNTIME_NAME,
    repository=PINNED_IMAGE_REPOSITORY,
    digest=PINNED_IMAGE_DIGEST,
    decision_ref=RUNTIME_DECISION_REF,
)

#: The pinned model, as one value a caller can pass around.
PINNED_MODEL = ModelPin(
    repository=PINNED_MODEL_REPOSITORY,
    revision=PINNED_MODEL_REVISION,
    file=PINNED_MODEL_FILE,
    size_bytes=PINNED_MODEL_SIZE_BYTES,
    sha256=PINNED_MODEL_SHA256,
    artifact_format=PINNED_ARTIFACT_FORMAT,
    decision_ref=RUNTIME_DECISION_REF,
)
