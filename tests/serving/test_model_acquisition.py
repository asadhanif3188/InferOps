"""The selected model's source record, retry path, verification, and cleanup.

Every test uses tiny synthetic bytes under pytest's temporary directory. No
network, model, credential, cluster, or repository cache is touched. These checks
establish repository-tool behaviour only; they do not certify the real artifact.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from urllib.request import Request

import pytest

from inferops.adapters.llama_cpp import PINNED_MODEL
from tools.model_acquisition import (
    MODEL_SOURCE_PATH,
    AcquisitionError,
    CacheSafetyError,
    ModelManifest,
    PreflightError,
    VerificationError,
    acquire,
    check_prerequisites,
    clean_cache,
    load_manifest,
    verify_artifact,
)
from tools.model_acquisition.__main__ import build_parser

pytestmark = pytest.mark.docs


class FakeResponse:
    """A bounded, context-managed byte stream with an optional interruption."""

    def __init__(
        self,
        payload: bytes,
        *,
        status: int,
        headers: dict[str, str] | None = None,
        fragment_bytes: int | None = None,
        interrupt: bool = False,
    ) -> None:
        self.payload = payload
        self.status = status
        self.headers: Mapping[str, str] = headers or {}
        self.fragment_bytes = fragment_bytes
        self.interrupt = interrupt
        self.position = 0

    def read(self, size: int = -1) -> bytes:
        if self.interrupt and self.position:
            raise OSError("synthetic interruption")
        if self.position >= len(self.payload):
            return b""
        count = len(self.payload) - self.position
        if size >= 0:
            count = min(count, size)
        if self.fragment_bytes is not None:
            count = min(count, self.fragment_bytes)
        chunk = self.payload[self.position : self.position + count]
        self.position += len(chunk)
        return chunk

    def __enter__(self) -> FakeResponse:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc_value: BaseException | None,
        traceback: object | None,
    ) -> None:
        return None


@pytest.fixture
def synthetic_manifest() -> ModelManifest:
    payload = b"model-bytes"
    return ModelManifest(
        schema_version="inferops.io/v1alpha1",
        repository="publisher/model",
        revision="a" * 40,
        file="model.gguf",
        source_url=f"https://example.invalid/model/{'a' * 40}/model.gguf",
        license_spdx="Apache-2.0",
        license_reference=f"https://example.invalid/model/{'a' * 40}/LICENSE",
        expected_size_bytes=len(payload),
        sha256=f"sha256:{hashlib.sha256(payload).hexdigest()}",
        cache_path=Path(".cache/inferops/models"),
        artifact_relative_path=Path(f"publisher--model/{'a' * 40}/model.gguf"),
    )


def test_public_source_record_matches_every_accepted_model_pin() -> None:
    manifest = load_manifest()

    assert manifest.repository == PINNED_MODEL.repository
    assert manifest.revision == PINNED_MODEL.revision
    assert manifest.file == PINNED_MODEL.file
    assert manifest.expected_size_bytes == PINNED_MODEL.size_bytes
    assert manifest.sha256 == PINNED_MODEL.sha256
    assert manifest.license_spdx == "Apache-2.0"
    assert manifest.revision in manifest.source_url
    assert manifest.revision in manifest.license_reference


@pytest.mark.parametrize(
    ("field", "nested", "replacement", "message"),
    [
        ("sourceUrl", None, "https://huggingface.co/model/main/file", "not pinned"),
        (
            "reference",
            "license",
            "https://huggingface.co/model/blob/main/LICENSE",
            "not pinned",
        ),
        (
            "artifactRelativePath",
            "cache",
            "../model.gguf",
            "unsafe artifact path",
        ),
    ],
)
def test_source_record_refuses_unpinned_or_unsafe_locations(
    tmp_path: Path,
    field: str,
    nested: str | None,
    replacement: str,
    message: str,
) -> None:
    record = json.loads(MODEL_SOURCE_PATH.read_text(encoding="utf-8"))
    target = record if nested is None else record[nested]
    target[field] = replacement
    source_record = tmp_path / "model-source.v1.json"
    source_record.write_text(json.dumps(record), encoding="utf-8")

    with pytest.raises(PreflightError, match=message):
        load_manifest(source_record)


def test_offline_check_reports_an_absent_workspace_cache(
    tmp_path: Path, synthetic_manifest: ModelManifest
) -> None:
    report = check_prerequisites(synthetic_manifest, repo_root=tmp_path)

    assert report.cache_root == tmp_path / ".cache/inferops/models"
    assert report.artifact == synthetic_manifest.artifact_path(tmp_path)
    assert report.state == "absent"
    assert report.existing_bytes == 0
    assert report.required_free_bytes > synthetic_manifest.expected_size_bytes


def test_a_verified_file_is_a_cache_hit_without_opening_the_network(
    tmp_path: Path, synthetic_manifest: ModelManifest
) -> None:
    artifact = synthetic_manifest.artifact_path(tmp_path)
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"model-bytes")

    def refuse_network(request: Request) -> FakeResponse:
        raise AssertionError(request.full_url)

    result = acquire(
        synthetic_manifest,
        repo_root=tmp_path,
        opener=refuse_network,
    )

    assert result.cache_hit is True
    assert result.bytes_verified == len(b"model-bytes")
    assert artifact.read_bytes() == b"model-bytes"


def test_an_interrupted_download_is_retained_and_resumed_by_range(
    tmp_path: Path, synthetic_manifest: ModelManifest
) -> None:
    partial = synthetic_manifest.partial_path(tmp_path)

    def interrupted(request: Request) -> FakeResponse:
        assert request.get_header("Range") is None
        return FakeResponse(
            b"model-",
            status=200,
            fragment_bytes=3,
            interrupt=True,
        )

    with pytest.raises(AcquisitionError, match="available for retry"):
        acquire(synthetic_manifest, repo_root=tmp_path, opener=interrupted)

    assert partial.read_bytes() == b"mod"

    def resumed(request: Request) -> FakeResponse:
        assert request.get_header("Range") == "bytes=3-"
        return FakeResponse(
            b"el-bytes",
            status=206,
            headers={"Content-Range": "bytes 3-10/11"},
        )

    result = acquire(synthetic_manifest, repo_root=tmp_path, opener=resumed)

    assert result.cache_hit is False
    assert result.resumed_from_bytes == 3
    assert synthetic_manifest.artifact_path(tmp_path).read_bytes() == b"model-bytes"
    assert not partial.exists()


def test_a_source_ignoring_range_restarts_the_partial_safely(
    tmp_path: Path, synthetic_manifest: ModelManifest
) -> None:
    partial = synthetic_manifest.partial_path(tmp_path)
    partial.parent.mkdir(parents=True)
    partial.write_bytes(b"stale")

    def full_response(request: Request) -> FakeResponse:
        assert request.get_header("Range") == "bytes=5-"
        return FakeResponse(b"model-bytes", status=200)

    result = acquire(synthetic_manifest, repo_root=tmp_path, opener=full_response)

    assert result.resumed_from_bytes == 0
    assert synthetic_manifest.artifact_path(tmp_path).read_bytes() == b"model-bytes"


def test_integrity_failure_is_clear_and_discards_only_the_untrusted_partial(
    tmp_path: Path, synthetic_manifest: ModelManifest
) -> None:
    sibling = tmp_path / ".cache/inferops/keep.txt"
    sibling.parent.mkdir(parents=True)
    sibling.write_text("keep", encoding="utf-8")

    def wrong_bytes(request: Request) -> FakeResponse:
        assert request.full_url == synthetic_manifest.source_url
        return FakeResponse(b"wrong-bytes", status=200)

    with pytest.raises(VerificationError, match="untrusted partial"):
        acquire(synthetic_manifest, repo_root=tmp_path, opener=wrong_bytes)

    assert not synthetic_manifest.partial_path(tmp_path).exists()
    assert sibling.read_text(encoding="utf-8") == "keep"


def test_an_invalid_final_artifact_is_never_overwritten(
    tmp_path: Path, synthetic_manifest: ModelManifest
) -> None:
    artifact = synthetic_manifest.artifact_path(tmp_path)
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"wrong-bytes")

    with pytest.raises(VerificationError, match="integrity verification failed"):
        acquire(synthetic_manifest, repo_root=tmp_path)

    assert artifact.read_bytes() == b"wrong-bytes"


def test_size_verification_fails_before_hashing(
    tmp_path: Path, synthetic_manifest: ModelManifest
) -> None:
    artifact = synthetic_manifest.artifact_path(tmp_path)
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"short")

    with pytest.raises(VerificationError, match="size verification failed"):
        verify_artifact(artifact, synthetic_manifest)


def test_cleanup_is_a_dry_run_until_confirmed_and_is_cache_scoped(
    tmp_path: Path, synthetic_manifest: ModelManifest
) -> None:
    artifact = synthetic_manifest.artifact_path(tmp_path)
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(b"model-bytes")
    outside = tmp_path / "outside.txt"
    outside.write_text("keep", encoding="utf-8")

    preview = clean_cache(repo_root=tmp_path)
    assert preview.removed is False
    assert preview.bytes_found == len(b"model-bytes")
    assert artifact.exists()

    removed = clean_cache(repo_root=tmp_path, confirm=True)
    assert removed.removed is True
    assert not (tmp_path / ".cache/inferops/models").exists()
    assert outside.read_text(encoding="utf-8") == "keep"


def test_only_the_documented_cache_layout_is_accepted(
    tmp_path: Path, synthetic_manifest: ModelManifest
) -> None:
    unsafe = replace(synthetic_manifest, cache_path=Path("models"))

    with pytest.raises(CacheSafetyError, match="documented model cache"):
        check_prerequisites(unsafe, repo_root=tmp_path)


def test_the_command_surface_has_no_credential_or_cache_override() -> None:
    help_text = build_parser().format_help()

    assert "check" in help_text
    assert "acquire" in help_text
    assert "verify" in help_text
    assert "clean" in help_text
    assert "token" not in help_text.lower()
    assert "password" not in help_text.lower()
    assert "cache-dir" not in help_text
