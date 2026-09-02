"""Acquire and verify the model selected by ADR 0002.

The public source record supplies the network location and licence reference.
The accepted adapter pins remain the authority for artifact identity; loading the
record fails if either copy drifts. Downloads use a ``.part`` file, resume with an
HTTP Range request, and become the cache artifact only after size and SHA-256
verification. No credential input or request header exists in this module.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import sys
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol, Self, cast
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from inferops.adapters.llama_cpp import PINNED_MODEL

REPO_ROOT = Path(__file__).resolve().parents[2]
MODEL_SOURCE_PATH = REPO_ROOT / "docs" / "serving" / "model-source.v1.json"
CACHE_HEADROOM_BYTES = 64 * 1024 * 1024
DOWNLOAD_CHUNK_BYTES = 1024 * 1024
EXPECTED_SCHEMA_VERSION = "inferops.io/v1alpha1"
EXPECTED_LICENSE = "Apache-2.0"
EXPECTED_CACHE_PATH = Path(".cache/inferops/models")


class ModelAcquisitionError(RuntimeError):
    """Base class for an expected, safely reportable workflow refusal."""


class PreflightError(ModelAcquisitionError):
    """A local prerequisite or source-record invariant was not met."""


class VerificationError(ModelAcquisitionError):
    """An artifact does not have the selected model's expected identity."""


class AcquisitionError(ModelAcquisitionError):
    """A transfer did not complete; a safe partial may remain for retry."""


class CacheSafetyError(ModelAcquisitionError):
    """Cleanup was refused because its target was not the documented cache."""


class DownloadResponse(Protocol):
    """The small part of an HTTP response the downloader consumes."""

    status: int
    headers: Mapping[str, str]

    def read(self, size: int = -1) -> bytes: ...

    def __enter__(self) -> Self: ...

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object | None,
    ) -> bool | None: ...


OpenUrl = Callable[[Request], DownloadResponse]


@dataclass(frozen=True, slots=True)
class ModelManifest:
    """The selected artifact's retrievable identity and cache layout."""

    schema_version: str
    repository: str
    revision: str
    file: str
    source_url: str
    license_spdx: str
    license_reference: str
    expected_size_bytes: int
    sha256: str
    cache_path: Path
    artifact_relative_path: Path

    @property
    def sha256_hex(self) -> str:
        """The digest without its algorithm prefix, for hashlib comparison."""
        return self.sha256.removeprefix("sha256:")

    def artifact_path(self, repo_root: Path = REPO_ROOT) -> Path:
        """The final file inside this checkout's documented cache."""
        return repo_root / self.cache_path / self.artifact_relative_path

    def partial_path(self, repo_root: Path = REPO_ROOT) -> Path:
        """The retryable transfer beside the final artifact."""
        return self.artifact_path(repo_root).with_name(f"{self.file}.part")


@dataclass(frozen=True, slots=True)
class PreflightReport:
    """Offline facts established before a transfer is allowed to start."""

    cache_root: Path
    artifact: Path
    state: str
    existing_bytes: int
    required_free_bytes: int
    available_free_bytes: int


@dataclass(frozen=True, slots=True)
class DownloadResult:
    """A verified cache result and whether the network was needed."""

    artifact: Path
    bytes_verified: int
    cache_hit: bool
    resumed_from_bytes: int


@dataclass(frozen=True, slots=True)
class CleanupResult:
    """What cleanup found and whether confirmation allowed its removal."""

    cache_root: Path
    bytes_found: int
    removed: bool


def _object(value: Any, field: str) -> dict[str, Any]:
    if not isinstance(value, dict):
        raise PreflightError(f"source record field '{field}' must be an object")
    return cast(dict[str, Any], value)


def _string(value: Any, field: str) -> str:
    if not isinstance(value, str) or not value:
        raise PreflightError(f"source record field '{field}' must be a string")
    return value


def _positive_int(value: Any, field: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise PreflightError(
            f"source record field '{field}' must be a positive integer"
        )
    return value


def _read_source_record(path: Path) -> dict[str, Any]:
    try:
        value: Any = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as error:
        raise PreflightError(
            "the committed model source record is unreadable"
        ) from error
    return _object(value, "root")


def load_manifest(path: Path = MODEL_SOURCE_PATH) -> ModelManifest:
    """Load the public source record and refuse drift from the accepted pins."""
    record = _read_source_record(path)
    license_record = _object(record.get("license"), "license")
    cache_record = _object(record.get("cache"), "cache")
    manifest = ModelManifest(
        schema_version=_string(record.get("schemaVersion"), "schemaVersion"),
        repository=_string(record.get("repository"), "repository"),
        revision=_string(record.get("revision"), "revision"),
        file=_string(record.get("file"), "file"),
        source_url=_string(record.get("sourceUrl"), "sourceUrl"),
        license_spdx=_string(license_record.get("spdx"), "license.spdx"),
        license_reference=_string(license_record.get("reference"), "license.reference"),
        expected_size_bytes=_positive_int(
            record.get("expectedSizeBytes"), "expectedSizeBytes"
        ),
        sha256=_string(record.get("sha256"), "sha256"),
        cache_path=Path(_string(cache_record.get("path"), "cache.path")),
        artifact_relative_path=Path(
            _string(
                cache_record.get("artifactRelativePath"),
                "cache.artifactRelativePath",
            )
        ),
    )
    _validate_manifest(manifest)
    return manifest


def _validate_manifest(manifest: ModelManifest) -> None:
    if manifest.schema_version != EXPECTED_SCHEMA_VERSION:
        raise PreflightError(
            "the model source record has an unsupported schema version"
        )
    accepted = (
        manifest.repository,
        manifest.revision,
        manifest.file,
        manifest.expected_size_bytes,
        manifest.sha256,
    )
    pinned = (
        PINNED_MODEL.repository,
        PINNED_MODEL.revision,
        PINNED_MODEL.file,
        PINNED_MODEL.size_bytes,
        PINNED_MODEL.sha256,
    )
    if accepted != pinned:
        raise PreflightError(
            "the model source record has drifted from the accepted pins"
        )
    if manifest.license_spdx != EXPECTED_LICENSE:
        raise PreflightError("the model source record has an unexpected licence")
    if manifest.cache_path != EXPECTED_CACHE_PATH or manifest.cache_path.is_absolute():
        raise PreflightError("the model source record names an unsupported cache path")
    if manifest.artifact_relative_path.is_absolute() or ".." in (
        manifest.artifact_relative_path.parts
    ):
        raise PreflightError("the model source record names an unsafe artifact path")
    expected_artifact_path = Path(
        manifest.repository.replace("/", "--"),
        manifest.revision,
        manifest.file,
    )
    if manifest.artifact_relative_path != expected_artifact_path:
        raise PreflightError(
            "the model source record has an unexpected cache artifact path"
        )
    expected_source = (
        f"https://huggingface.co/{manifest.repository}/resolve/"
        f"{manifest.revision}/{manifest.file}?download=true"
    )
    expected_license = (
        f"https://huggingface.co/{manifest.repository}/blob/{manifest.revision}/LICENSE"
    )
    if manifest.source_url != expected_source:
        raise PreflightError(
            "the model source URL is not pinned to the selected revision"
        )
    if manifest.license_reference != expected_license:
        raise PreflightError(
            "the licence reference is not pinned to the selected revision"
        )
    for label, url in (
        ("model source", manifest.source_url),
        ("licence reference", manifest.license_reference),
    ):
        parsed = urlsplit(url)
        if parsed.scheme != "https" or parsed.hostname != "huggingface.co":
            raise PreflightError(f"the {label} must use HTTPS on huggingface.co")
        if parsed.username is not None or parsed.password is not None:
            raise PreflightError(f"the {label} must not contain credentials")
    digest = manifest.sha256_hex
    if len(digest) != 64 or any(
        character not in "0123456789abcdef" for character in digest
    ):
        raise PreflightError("the model SHA-256 is not a lowercase 64-character digest")
    if manifest.artifact_relative_path.name != manifest.file:
        raise PreflightError(
            "the cache artifact path does not end with the selected file"
        )


def default_cache_root(repo_root: Path = REPO_ROOT) -> Path:
    """Return the only cache root this V1 workflow is allowed to manage."""
    return repo_root / EXPECTED_CACHE_PATH


def _existing_parent(path: Path) -> Path:
    candidate = path
    while not candidate.exists():
        if candidate.parent == candidate:
            raise PreflightError("no existing parent was found for the model cache")
        candidate = candidate.parent
    return candidate


def _hash(path: Path) -> str:
    digest = hashlib.sha256()
    try:
        with path.open("rb") as artifact:
            while chunk := artifact.read(DOWNLOAD_CHUNK_BYTES):
                digest.update(chunk)
    except OSError as error:
        raise VerificationError(
            "the cached model artifact could not be read"
        ) from error
    return digest.hexdigest()


def verify_artifact(path: Path, manifest: ModelManifest) -> int:
    """Verify size and SHA-256, returning the trusted byte count."""
    if not path.is_file():
        raise VerificationError("the selected model artifact is not cached")
    try:
        size = path.stat().st_size
    except OSError as error:
        raise VerificationError(
            "the cached model artifact could not be inspected"
        ) from error
    if size != manifest.expected_size_bytes:
        raise VerificationError(
            "model size verification failed: cached bytes do not match the source record"
        )
    if _hash(path) != manifest.sha256_hex:
        raise VerificationError(
            "model integrity verification failed: SHA-256 does not match the source record"
        )
    return size


def check_prerequisites(
    manifest: ModelManifest,
    *,
    repo_root: Path = REPO_ROOT,
) -> PreflightReport:
    """Check local state and disk capacity without opening a network connection."""
    if not ((3, 12) <= sys.version_info[:2] < (3, 13)):
        raise PreflightError("Python 3.12 is required by the repository toolchain")
    cache_root = default_cache_root(repo_root)
    artifact = manifest.artifact_path(repo_root)
    partial = manifest.partial_path(repo_root)
    _assert_documented_cache(cache_root, repo_root)
    if manifest.cache_path != EXPECTED_CACHE_PATH or manifest.cache_path.is_absolute():
        raise CacheSafetyError("artifact target is not the documented model cache")
    try:
        artifact.resolve(strict=False).relative_to(cache_root.resolve(strict=False))
        partial.resolve(strict=False).relative_to(cache_root.resolve(strict=False))
    except ValueError as error:
        raise CacheSafetyError(
            "artifact target resolves outside the model cache"
        ) from error
    for target in (artifact, partial):
        candidate = cache_root
        for part in target.relative_to(cache_root).parts:
            candidate = candidate / part
            if candidate.exists() and candidate.is_symlink():
                raise CacheSafetyError(
                    "artifact target contains a symbolic link inside the model cache"
                )
    parent = _existing_parent(cache_root)
    if not os.access(parent, os.W_OK):
        raise PreflightError("the model cache parent is not writable")

    state = "absent"
    existing_bytes = 0
    if artifact.exists():
        verify_artifact(artifact, manifest)
        state = "verified"
        existing_bytes = manifest.expected_size_bytes
    elif partial.exists():
        if not partial.is_file():
            raise PreflightError("the resumable model cache entry is not a file")
        try:
            existing_bytes = partial.stat().st_size
        except OSError as error:
            raise PreflightError(
                "the resumable model cache entry could not be inspected"
            ) from error
        if existing_bytes > manifest.expected_size_bytes:
            raise PreflightError(
                "the resumable model cache entry exceeds expected size"
            )
        state = "partial"

    required = max(manifest.expected_size_bytes - existing_bytes, 0)
    if state != "verified":
        required += CACHE_HEADROOM_BYTES
    available = shutil.disk_usage(parent).free
    if available < required:
        raise PreflightError(
            "insufficient free space for the remaining model bytes and cache headroom"
        )
    return PreflightReport(
        cache_root=cache_root,
        artifact=artifact,
        state=state,
        existing_bytes=existing_bytes,
        required_free_bytes=required,
        available_free_bytes=available,
    )


def _open_url(request: Request) -> DownloadResponse:
    return cast(DownloadResponse, urlopen(request, timeout=60))  # nosec B310


def _content_range_starts_at(headers: Mapping[str, str], offset: int) -> bool:
    value = headers.get("Content-Range", "")
    return value.startswith(f"bytes {offset}-")


def _write_response(response: DownloadResponse, partial: Path, mode: str) -> None:
    try:
        with partial.open(mode) as output:
            while chunk := response.read(DOWNLOAD_CHUNK_BYTES):
                output.write(chunk)
            output.flush()
            os.fsync(output.fileno())
    except OSError as error:
        raise AcquisitionError(
            "model transfer stopped; the verified cache was not changed and the "
            "partial file is available for retry"
        ) from error


def acquire(
    manifest: ModelManifest,
    *,
    repo_root: Path = REPO_ROOT,
    opener: OpenUrl = _open_url,
) -> DownloadResult:
    """Acquire the selected bytes, resuming safely and promoting atomically."""
    report = check_prerequisites(manifest, repo_root=repo_root)
    artifact = report.artifact
    partial = manifest.partial_path(repo_root)
    if report.state == "verified":
        return DownloadResult(
            artifact=artifact,
            bytes_verified=manifest.expected_size_bytes,
            cache_hit=True,
            resumed_from_bytes=0,
        )

    try:
        artifact.parent.mkdir(parents=True, exist_ok=True)
    except OSError as error:
        raise AcquisitionError(
            "the model cache directory could not be created"
        ) from error
    offset = report.existing_bytes
    headers = {"Accept-Encoding": "identity", "User-Agent": "InferOps-model-cache/1"}
    if offset:
        headers["Range"] = f"bytes={offset}-"
    request = Request(manifest.source_url, headers=headers, method="GET")
    try:
        with opener(request) as response:
            if offset and response.status == 206:
                if not _content_range_starts_at(response.headers, offset):
                    raise AcquisitionError(
                        "model source returned an inconsistent resume range; partial retained"
                    )
                mode = "ab"
            elif response.status == 200:
                mode = "wb"
                if offset:
                    offset = 0
            else:
                raise AcquisitionError(
                    "model source did not accept the pinned artifact request"
                )
            _write_response(response, partial, mode)
    except AcquisitionError:
        raise
    except OSError as error:
        raise AcquisitionError(
            "model transfer stopped; the verified cache was not changed and the "
            "partial file is available for retry"
        ) from error

    try:
        downloaded_size = partial.stat().st_size
    except OSError as error:
        raise AcquisitionError(
            "the partial model file could not be inspected"
        ) from error
    if downloaded_size < manifest.expected_size_bytes:
        raise AcquisitionError(
            "model transfer ended early; rerun acquire to resume the partial file"
        )
    if downloaded_size > manifest.expected_size_bytes:
        partial.unlink(missing_ok=True)
        raise VerificationError(
            "model size verification failed; the oversized partial file was discarded"
        )
    try:
        verify_artifact(partial, manifest)
    except VerificationError:
        partial.unlink(missing_ok=True)
        raise VerificationError(
            "model integrity verification failed; the untrusted partial file was discarded"
        ) from None
    try:
        partial.replace(artifact)
    except OSError as error:
        raise AcquisitionError(
            "the verified partial model could not be promoted into the cache"
        ) from error
    return DownloadResult(
        artifact=artifact,
        bytes_verified=manifest.expected_size_bytes,
        cache_hit=False,
        resumed_from_bytes=report.existing_bytes if offset else 0,
    )


def _assert_documented_cache(cache_root: Path, repo_root: Path) -> None:
    lexical = repo_root / EXPECTED_CACHE_PATH
    if cache_root != lexical:
        raise CacheSafetyError("cleanup target is not the documented model cache")
    resolved_repo = repo_root.resolve()
    resolved_cache = cache_root.resolve(strict=False)
    try:
        resolved_cache.relative_to(resolved_repo)
    except ValueError as error:
        raise CacheSafetyError("model cache resolves outside the repository") from error
    candidate = repo_root
    for part in EXPECTED_CACHE_PATH.parts:
        candidate = candidate / part
        if candidate.exists() and candidate.is_symlink():
            raise CacheSafetyError("cleanup refused a symbolic link in the cache path")


def _tree_bytes(root: Path) -> int:
    total = 0
    if not root.exists():
        return total
    for path in root.rglob("*"):
        if path.is_symlink():
            raise CacheSafetyError("cleanup refused a symbolic link inside the cache")
        if path.is_file():
            total += path.stat().st_size
    return total


def clean_cache(
    *,
    repo_root: Path = REPO_ROOT,
    confirm: bool = False,
) -> CleanupResult:
    """Inspect or remove only this checkout's documented model cache."""
    cache_root = default_cache_root(repo_root)
    _assert_documented_cache(cache_root, repo_root)
    existed = cache_root.exists()
    bytes_found = _tree_bytes(cache_root)
    if confirm and existed:
        try:
            shutil.rmtree(cache_root)
        except OSError as error:
            raise CacheSafetyError(
                "the documented model cache could not be removed"
            ) from error
    return CleanupResult(
        cache_root=cache_root,
        bytes_found=bytes_found,
        removed=confirm and existed,
    )
