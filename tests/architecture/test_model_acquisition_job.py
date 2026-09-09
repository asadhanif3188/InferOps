"""The model acquisition script, executed rather than read.

`model-acquisition-job` is the single sanctioned handoff in the design: the one
object a release may use to write into a prerequisite it does not own. Terraform
creates the model cache claim empty, the serving runtime mounts it read only and
refuses to start on an artifact that is absent or does not verify, and until now
there was nothing between the two. The practical consequence was a real profile
that could be installed only against a claim somebody had filled by hand.

What makes this worth executing rather than reading is that every way it can go
wrong looks like success from the outside. A job that wrote a short file under
the real name would report success and leave the runtime to refuse the bytes
later. A job that treated any existing file as a cache hit would skip the
transfer and hand the runtime a corrupted artifact. A job that verified after
renaming would leave the wrong bytes in place under the right name. None of
those is visible in a rendered manifest, and all of them are visible in an exit
status and a directory listing.

So this module takes the script out of the committed render and runs it under
`bash` against a real directory, with `wget` replaced by a stub that records
whether it was called and controls what it produces. The assertions are about
the filesystem afterwards and about whether a transfer happened at all -- not
about wording.

**One adaptation, stated.** The script writes to `/claim`, which is where the
kubelet mounts the claim and which a test cannot create. The claim root -- and
only the claim root -- is repointed at a temporary directory. The derived
revision path below it, the verification, the temporary-file-and-rename, the
cache-hit branch and the discard-on-mismatch branch are all executed exactly as
rendered, and a test asserts that the substitution replaced the one token it was
supposed to.
"""

from __future__ import annotations

import hashlib
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

pytestmark = pytest.mark.architecture

REPO_ROOT = Path(__file__).resolve().parents[2]
RENDER_PATH = (
    REPO_ROOT / "charts" / "inferops-llm" / "ci" / "rendered" / "real.expected.yaml"
)
REAL_VALUES_PATH = REPO_ROOT / "charts" / "inferops-llm" / "ci" / "real-values.yaml"

BASH = shutil.which("bash")
needs_bash = pytest.mark.skipif(
    BASH is None,
    reason="bash is not installed; the executable acquisition tests skip, loudly",
)

REAL_VALUES = yaml.safe_load(REAL_VALUES_PATH.read_text(encoding="utf-8"))
MODEL = REAL_VALUES["model"]
FILE_NAME = MODEL["artifact"]["fileName"]
REVISION = MODEL["revision"]
REPOSITORY = MODEL["artifact"]["repository"]

# The layout the runtime mounts, derived the way the chart derives it.
SUBDIRECTORY = f"{REPOSITORY.replace('/', '--')}/{REVISION}"


def _documents() -> list[dict]:
    return [
        document
        for document in yaml.safe_load_all(RENDER_PATH.read_text(encoding="utf-8"))
        if document
    ]


def acquisition_job() -> dict:
    jobs = [d for d in _documents() if d.get("kind") == "Job"]
    assert len(jobs) == 1, "the real render carries one acquisition job"
    return jobs[0]


def rendered_script() -> str:
    container = acquisition_job()["spec"]["template"]["spec"]["containers"][0]
    command = container["command"]
    assert command[:2] == ["/bin/sh", "-c"], command[:2]
    return command[2]


SCRIPT = rendered_script()

# The pins the script was rendered with. Read back out of the values rather than
# restated, so a test cannot agree with a script that drifted from the record.
WANT_BYTES = int(MODEL["artifact"]["sizeBytes"])
WANT_SHA = MODEL["artifact"]["sha256"].removeprefix("sha256:")


class Run:
    def __init__(self, completed: subprocess.CompletedProcess[str], log: Path) -> None:
        self.returncode = completed.returncode
        self.output = completed.stdout + completed.stderr
        self.calls = [
            line for line in log.read_text(encoding="utf-8").splitlines() if line
        ]

    @property
    def refused(self) -> bool:
        return self.returncode != 0

    @property
    def transferred(self) -> bool:
        """Did the script actually reach for the network?"""
        return any(line.startswith("wget ") for line in self.calls)


@pytest.fixture
def claim(tmp_path: Path) -> Path:
    """A directory standing in for the mounted claim, empty as Terraform leaves it."""
    root = tmp_path / "claim"
    root.mkdir()
    return root


def run_acquisition(
    claim: Path,
    *,
    payload: bytes | None = None,
    wget_exit: int = 0,
    max_wget_failures: int = 0,
) -> Run:
    """Execute the rendered script with the claim root repointed and wget stubbed."""
    assert BASH is not None
    sandbox = claim.parent
    log = sandbox / "calls.log"
    log.write_text("", encoding="utf-8")

    # The one adaptation: the claim root. Asserted to be a single occurrence, so
    # this cannot silently start rewriting more of the script than it means to.
    assert SCRIPT.count("dir='/claim/") == 1, "the claim root is not where it was"
    body = SCRIPT.replace("dir='/claim/", f"dir='{claim.as_posix()}/", 1)

    script_path = sandbox / "acquire.sh"
    script_path.write_text(body, encoding="utf-8", newline="\n")

    bin_dir = sandbox / "bin"
    bin_dir.mkdir(exist_ok=True)
    stub = bin_dir / "wget"
    # Records the call, then writes whatever the scenario asked for to the `-O`
    # target. `-c` resumption is modelled by appending rather than truncating,
    # which is what makes the partial-artifact case meaningful.
    stub.write_text(
        "#!/usr/bin/env bash\n"
        'printf \'wget %s\\n\' "$*" >>"${ACQ_LOG}"\n'
        "attempts=$(grep -c '^wget ' \"${ACQ_LOG}\")\n"
        'if [ "${attempts}" -le "${ACQ_FAILURES:-0}" ]; then exit 1; fi\n'
        'target=""\n'
        'while [ "$#" -gt 0 ]; do\n'
        '  if [ "$1" = "-O" ]; then target="$2"; shift; fi\n'
        "  shift\n"
        "done\n"
        '[ -n "${target}" ] || exit 2\n'
        'cat "${ACQ_PAYLOAD}" >>"${target}"\n'
        'exit "${ACQ_EXIT:-0}"\n',
        encoding="utf-8",
        newline="\n",
    )
    stub.chmod(0o755)

    # `sleep` is stubbed to return immediately. The script pauses between resumed
    # attempts so that a budget of sixty is not spent inside a second against a
    # connection that is refused instantly -- which is correct, and which would
    # make a test of the budget take five minutes of doing nothing. The pause is
    # what is skipped; the counting is not, and the counting is what is under
    # test. A test that instead lowered `maxAttempts` would be exercising a
    # script this chart does not render.
    pause = bin_dir / "sleep"
    pause.write_text(
        '#!/usr/bin/env bash\nprintf \'sleep %s\\n\' "$*" >>"${ACQ_LOG}"\nexit 0\n',
        encoding="utf-8",
        newline="\n",
    )
    pause.chmod(0o755)

    payload_path = sandbox / "payload.bin"
    payload_path.write_bytes(b"" if payload is None else payload)

    env = dict(os.environ)
    env["PATH"] = os.pathsep.join([str(bin_dir), str(Path(BASH).parent)])
    env["ACQ_LOG"] = str(log)
    env["ACQ_PAYLOAD"] = str(payload_path)
    env["ACQ_EXIT"] = str(wget_exit)
    env["ACQ_FAILURES"] = str(max_wget_failures)

    completed = subprocess.run(
        [BASH, str(script_path)],
        cwd=sandbox,
        env=env,
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    return Run(completed, log)


def good_bytes() -> bytes:
    """Bytes that satisfy the rendered pins.

    The real artifact is 1.71 GiB and its hash is fixed, so the script is
    re-rendered against a small stand-in instead: the pins in the script under
    test are rewritten to describe these bytes. That keeps every branch and every
    comparison exactly as rendered while making the test run in milliseconds.
    """
    return b"inferops-model-acquisition-test-artifact\n"


@pytest.fixture(autouse=True)
def _retarget_pins(monkeypatch: pytest.MonkeyPatch) -> None:
    """Point the rendered script's pins at the small stand-in artifact."""
    payload = good_bytes()
    retargeted = SCRIPT.replace(
        f"want_bytes='{WANT_BYTES}'", f"want_bytes='{len(payload)}'"
    ).replace(
        f"want_sha='{WANT_SHA}'", f"want_sha='{hashlib.sha256(payload).hexdigest()}'"
    )
    assert retargeted != SCRIPT, "the pins are not where this test expects them"
    # `monkeypatch` restores the module attribute after each test, which is what
    # keeps every test starting from the committed script rather than from the
    # previous test's rewrite of it.
    monkeypatch.setattr(f"{__name__}.SCRIPT", retargeted)


def artifact_path(claim: Path) -> Path:
    return claim / SUBDIRECTORY / FILE_NAME


# --------------------------------------------------------------------------
# The rendered object, before anything is executed
# --------------------------------------------------------------------------


def test_the_job_writes_the_directory_the_runtime_reads() -> None:
    """A job that filled a different directory would fill a cache nobody serves."""
    assert f"/claim/{SUBDIRECTORY}" in SCRIPT
    runtime = next(
        d
        for d in _documents()
        if d.get("kind") == "Deployment" and d["metadata"]["name"].endswith("-runtime")
    )
    mounts = [
        mount
        for container in runtime["spec"]["template"]["spec"]["containers"]
        + runtime["spec"]["template"]["spec"]["initContainers"]
        for mount in container["volumeMounts"]
        if mount["name"] == "model-cache"
    ]
    assert mounts, "the runtime mounts no model cache"
    for mount in mounts:
        assert mount["subPath"] == SUBDIRECTORY, mount
        assert mount["readOnly"] is True


def test_the_job_carries_the_licence_the_source_record_publishes() -> None:
    """Provenance that lives only in a document is provenance a cluster cannot
    be asked about."""
    import json

    source = json.loads(
        (REPO_ROOT / "docs" / "serving" / "model-source.v1.json").read_text(
            encoding="utf-8"
        )
    )
    annotations = acquisition_job()["metadata"]["annotations"]
    assert annotations["inferops.io/model-license"] == source["license"]["spdx"]
    assert (
        annotations["inferops.io/model-license-reference"]
        == source["license"]["reference"]
    )
    assert annotations["inferops.io/model-revision"] == source["revision"]


def test_the_job_mounts_the_claim_writable_and_the_runtime_does_not() -> None:
    job_mounts = acquisition_job()["spec"]["template"]["spec"]["containers"][0][
        "volumeMounts"
    ]
    assert [m for m in job_mounts if m["name"] == "model-cache"], job_mounts
    assert not any(m.get("readOnly") for m in job_mounts if m["name"] == "model-cache")
    volume = next(
        v
        for v in acquisition_job()["spec"]["template"]["spec"]["volumes"]
        if v["name"] == "model-cache"
    )
    assert volume["persistentVolumeClaim"]["claimName"] == MODEL["cache"]["claimName"]
    assert "readOnly" not in volume["persistentVolumeClaim"], (
        "a read-only volume cannot be written by the one object allowed to write it"
    )


# --------------------------------------------------------------------------
# From an empty claim
# --------------------------------------------------------------------------


@needs_bash
def test_an_empty_claim_is_populated_and_verified(claim: Path) -> None:
    """The case the whole story exists for: a claim Terraform just provisioned."""
    run = run_acquisition(claim, payload=good_bytes())
    assert run.returncode == 0, run.output
    assert run.transferred, "nothing was fetched into an empty claim"
    assert artifact_path(claim).read_bytes() == good_bytes()
    assert not list(claim.rglob("*.part")), "a temporary file was left behind"


@needs_bash
def test_the_revision_directory_is_created_beneath_the_claim(claim: Path) -> None:
    """`subPath` cannot create it, which is why the job mounts the claim root."""
    run = run_acquisition(claim, payload=good_bytes())
    assert run.returncode == 0, run.output
    assert (claim / SUBDIRECTORY).is_dir()


# --------------------------------------------------------------------------
# From a populated claim
# --------------------------------------------------------------------------


@needs_bash
def test_a_verified_artifact_is_reused_without_transferring_anything(
    claim: Path,
) -> None:
    """The property that keeps an upgrade from re-fetching 1.71 GiB."""
    target = artifact_path(claim)
    target.parent.mkdir(parents=True)
    target.write_bytes(good_bytes())

    run = run_acquisition(claim, payload=good_bytes())
    assert run.returncode == 0, run.output
    assert not run.transferred, "a verified cache hit still reached for the network"
    assert "already present and verified" in run.output


@needs_bash
def test_a_corrupt_artifact_is_not_a_cache_hit(claim: Path) -> None:
    """Same name, same length, different bytes.

    A byte-count check alone accepts this, which is why the cache-hit branch
    hashes as well. Accepting it would hand the runtime a corrupted artifact and
    report success.
    """
    corrupt = bytearray(good_bytes())
    corrupt[0] ^= 0xFF
    target = artifact_path(claim)
    target.parent.mkdir(parents=True)
    target.write_bytes(bytes(corrupt))

    run = run_acquisition(claim, payload=good_bytes())
    assert run.returncode == 0, run.output
    assert run.transferred, "a corrupt artifact was reused instead of replaced"
    assert artifact_path(claim).read_bytes() == good_bytes()


@needs_bash
def test_a_truncated_artifact_is_not_a_cache_hit(claim: Path) -> None:
    target = artifact_path(claim)
    target.parent.mkdir(parents=True)
    target.write_bytes(good_bytes()[:5])

    run = run_acquisition(claim, payload=good_bytes())
    assert run.returncode == 0, run.output
    assert run.transferred
    assert artifact_path(claim).read_bytes() == good_bytes()


@needs_bash
def test_another_revisions_directory_is_never_touched(claim: Path) -> None:
    """The job acquires the artifact this release was rendered with, and no other."""
    other = claim / "Qwen--Qwen3-1.7B-GGUF" / ("0" * 40) / FILE_NAME
    other.parent.mkdir(parents=True)
    other.write_bytes(b"another revision's bytes\n")

    run = run_acquisition(claim, payload=good_bytes())
    assert run.returncode == 0, run.output
    assert other.read_bytes() == b"another revision's bytes\n"


# --------------------------------------------------------------------------
# When acquisition fails
# --------------------------------------------------------------------------


@needs_bash
def test_bytes_that_do_not_verify_are_refused_and_leave_nothing(claim: Path) -> None:
    """The property that matters most: a failure leaves nothing that looks complete.

    A short or substituted transfer must not end up under the real name. If it
    did, the job would report success, the runtime's own check would refuse the
    bytes minutes later, and the install would have said it worked.
    """
    run = run_acquisition(claim, payload=b"not the pinned bytes\n")
    assert run.refused, run.output
    assert "do not match the pinned byte count and SHA-256" in run.output
    assert not artifact_path(claim).exists(), "a failed transfer was named as complete"
    assert not list(claim.rglob("*.part")), "the temporary file was left behind"


@needs_bash
def test_a_transfer_that_never_completes_is_refused_within_its_budget(
    claim: Path,
) -> None:
    """Resumption is a count, not an unbounded retry."""
    run = run_acquisition(claim, payload=good_bytes(), max_wget_failures=10_000)
    assert run.refused, run.output
    assert "attempt budget" in run.output
    assert not artifact_path(claim).exists()
    assert not list(claim.rglob("*.part"))


@needs_bash
def test_a_transfer_reporting_success_with_short_bytes_is_still_refused(
    claim: Path,
) -> None:
    """`wget` exiting zero is not evidence that the artifact arrived.

    A proxy returning a truncated body, a connection closed at the right moment:
    the transfer reports success and the file is short. Verification is what
    catches it, and it runs before the rename, so nothing short is ever named
    like something complete.

    This does **not** establish that `wget -c` resumption assembles an artifact
    across attempts. That property needs a transfer that really is interrupted
    and really is continued, which this harness does not model and which nothing
    in this repository has yet observed -- the finding that made the Sprint 0
    downloader resumable is a measurement, not a test.
    """
    payload = good_bytes()
    run = run_acquisition(claim, payload=payload[: len(payload) // 2])
    assert run.refused, run.output
    assert not artifact_path(claim).exists()
    assert not list(claim.rglob("*.part"))
