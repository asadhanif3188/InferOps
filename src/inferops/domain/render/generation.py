"""Generated release output: the values, the release that names them, and their digests.

:func:`generate_release` is the one path from validated, parsed inputs to a
generated release. It runs the boundary for the Helm values renderer's support,
renders the values, takes their digest, and records the RenderedWorkloadRelease that
names them, and returns all of it as :class:`GeneratedRelease`: two files' exact
bytes, ready for a caller to write, and the objects they were written from. It
writes nothing itself; ``writing`` puts the two files in a directory.

**Two files, each in one spelling.**

- ``values.generated.yaml`` - the generated chart values, in the canonical YAML form
  ``values_yaml`` writes, under the renderer's fixed header. A release names it by
  this file name, so it lives beside the release.
- ``rendered-workload-release.yaml`` - the release, in the same canonical form, under
  a fixed header of its own. The published release validator reads it as it reads
  any release document.

**Digests.** Every input's digest is the one the boundary already computed: the
contract's and the binding's of their parsed value, the renderer's and the platform
defaults' as full revisions. The values' digest, which the release records in
``output.helmValues.sha256``, and the release file's own digest are
:func:`~inferops.domain.release.canonical.output_digest` - the SHA-256 of the exact
bytes - for the reason that module gives. The release identifier is derived from the
inputs alone, so the values' digest moves it not at all: two generations with the
same identifier and different values digests were rendered from the same inputs and
wrote different values.

**Deterministic.** Like the rest of the package this reads no clock, random source,
environment variable, or file: equal inputs give equal bytes in both files, and the
header lines name no revision, date, or identifier.

**What a generated release is not.** Its output is static, evidence level C0, until a
real deployment installs it. Nothing here installs, commits, or reconciles it.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final

from ..context import NO_REQUEST_CONTEXT, RequestContext
from ..environment.binding import EnvironmentBinding
from ..release.canonical import output_digest
from ..release.release import (
    HelmValuesReference,
    RenderedWorkloadRelease,
    RendererReference,
)
from ..release.values import Sha256Hex, ValuesFileName
from ..workload.contract import WorkloadContract
from ..workload.values import DnsLabel
from .defaults import PlatformDefaults
from .helm_values import GeneratedHelmValues, HelmValuesRenderer
from .normalization import prepare_render
from .recording import record_release
from .renderer import _render_prepared
from .values_yaml import canonical_yaml

#: The file the generated values are written to, which the release names.
VALUES_FILE_NAME: Final = ValuesFileName("values.generated.yaml")

#: The file the release is written to, beside the values.
RELEASE_FILE_NAME: Final = "rendered-workload-release.yaml"

#: Comment lines written above the release. Constant: no revision, no date.
RELEASE_HEADER: Final[tuple[str, ...]] = (
    "Generated RenderedWorkloadRelease: what the values beside it were rendered from.",
    "Do not edit by hand: render the release again from the sources it names.",
)


def release_text(release: RenderedWorkloadRelease) -> bytes:
    """A release's file: its document in the canonical YAML form, under the header.

    Every string a release holds is printable ASCII, so the text is ASCII too.
    """
    if not isinstance(release, RenderedWorkloadRelease):
        raise TypeError("a release file is written from a RenderedWorkloadRelease")
    return canonical_yaml(release.as_document(), header=RELEASE_HEADER).encode("ascii")


def values_text(values: GeneratedHelmValues) -> bytes:
    """A values file: the generated values in their canonical YAML form, as ASCII."""
    if not isinstance(values, GeneratedHelmValues):
        raise TypeError("a values file is written from GeneratedHelmValues")
    return values.to_yaml().encode("ascii")


@dataclass(frozen=True, slots=True)
class GeneratedRelease:
    """One generation: the release, the values it names, and both files' bytes.

    It cannot hold files that disagree with its objects. Construction requires
    both files as immutable ``bytes`` - a ``bytearray`` equal to them could be
    changed afterwards - recomputes both from the release and the values, and
    checks that the release names the values file by :data:`VALUES_FILE_NAME` and
    by the digest of these bytes, so whatever a caller writes from one of these is
    a release and the values it names, whoever built it.
    """

    release: RenderedWorkloadRelease
    values: GeneratedHelmValues
    values_bytes: bytes
    release_bytes: bytes

    def __post_init__(self) -> None:
        if (
            type(self.values_bytes) is not bytes
            or type(self.release_bytes) is not bytes
        ):
            raise TypeError("a generated release holds its files as immutable bytes")
        if self.values_bytes != values_text(self.values):
            raise ValueError("the values bytes are not the values' canonical form")
        if self.release_bytes != release_text(self.release):
            raise ValueError("the release bytes are not the release's canonical form")
        named = self.release.output.helm_values
        if str(named.path) != str(VALUES_FILE_NAME):
            raise ValueError("the release does not name the generated values file")
        if str(named.sha256) != str(output_digest(self.values_bytes)):
            raise ValueError("the release does not record the values file's digest")

    @property
    def values_sha256(self) -> Sha256Hex:
        """The values file's digest, as the release records it."""
        return self.release.output.helm_values.sha256

    @property
    def release_sha256(self) -> Sha256Hex:
        """The release file's digest: the SHA-256 of its exact bytes."""
        return output_digest(self.release_bytes)

    def files(self) -> tuple[tuple[str, bytes], ...]:
        """Each file's name and bytes: the values first, then the release naming them."""
        return (
            (str(VALUES_FILE_NAME), self.values_bytes),
            (RELEASE_FILE_NAME, self.release_bytes),
        )


def generate_release(
    renderer: HelmValuesRenderer,
    contract: WorkloadContract,
    platform_defaults: PlatformDefaults,
    bindings: Sequence[EnvironmentBinding],
    *,
    binding_name: DnsLabel | None = None,
    context: RequestContext = NO_REQUEST_CONTEXT,
) -> GeneratedRelease:
    """The generated values and the release that names them, or every reason not.

    The boundary runs for the renderer's support first, then the renderer, then the
    release is recorded from the same context with the values file's name and
    digest. Each stage runs only once the one before it has passed, so a refusal
    leaves nothing to write.

    Raises:
        RenderRefused: every finding the boundary makes, or the renderer's own
            refusal, with ``context`` attached to each finding.
        ReleaseNotRecordedError: the values rendered, and the release naming them
            would be refused - a binding named with a credential-shaped part, for
            one, which no chart value carries and a release does.
        TypeError: ``renderer`` is not a :class:`~.helm_values.HelmValuesRenderer`,
            or an input is a raw document.
    """
    if not isinstance(renderer, HelmValuesRenderer):
        raise TypeError("renderer must be a HelmValuesRenderer")
    prepared = prepare_render(
        contract,
        platform_defaults,
        bindings,
        support=renderer.support,
        binding_name=binding_name,
        context=context,
    )
    values = _render_prepared(renderer, prepared, context=context)
    values_bytes = values_text(values)
    release = record_release(
        prepared,
        renderer=RendererReference(renderer.revision),
        helm_values=HelmValuesReference(VALUES_FILE_NAME, output_digest(values_bytes)),
        context=context,
    )
    return GeneratedRelease(release, values, values_bytes, release_text(release))


__all__ = [
    "RELEASE_FILE_NAME",
    "RELEASE_HEADER",
    "VALUES_FILE_NAME",
    "GeneratedRelease",
    "generate_release",
    "release_text",
    "values_text",
]
