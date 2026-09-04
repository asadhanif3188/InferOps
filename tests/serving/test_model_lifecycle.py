"""The model lifecycle state model, its cache classification, and its measurement.

Every test here drives the workflow through injected command, HTTP, TCP, and
clock seams, over a synthetic cache holding a few bytes. **No container is
started, no image is inspected, no model byte is read, and no real latency is
observed.** The timings that appear below are arithmetic on a fake clock.

Three groups, and each corresponds to a way this could go wrong:

1. **The record against the things it describes.** The probe ports, statuses,
   budgets, and cache root are all decided in other files. A lifecycle record
   free to restate them differently would be a fourth copy that drifts.
2. **The invariants inside the record.** One of them is the reason the record
   exists: while the model loads, the liveness probe passes and readiness is
   false. A record where those agree describes a deployment a liveness probe
   restarts mid-load, so it is refused rather than published.
3. **The measurement, and what it refuses to do.** It refuses to start without
   confirmation, refuses to start from anything but a cache hit, always removes
   its container, and cannot reach the model cache when it cleans up.
"""

from __future__ import annotations

import copy
import json
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from inferops.api.lifecycle import DEFAULT_DRAIN_TIMEOUT_MS
from tools.model_acquisition import load_manifest
from tools.model_acquisition.core import ModelManifest
from tools.model_lifecycle import (
    EXPECTED_RESULT_DIRECTORY,
    LIFECYCLE_PATH,
    MODEL_CACHE_DIRECTORY,
    CacheState,
    ComparisonResult,
    Environment,
    LifecycleRefused,
    LifecycleState,
    ModelLifecycleError,
    ProbeOutcome,
    ProbeSample,
    RestartResult,
    StartObservation,
    clean_results,
    compare_restart,
    compare_starts,
    load_lifecycle,
    observation_document,
    observe_cache,
    observe_start,
    read_restart_results,
    read_results,
    result_directory,
    summarize,
    summarize_restart,
    write_restart_results,
    write_results,
)
from tools.model_lifecycle.__main__ import main
from tools.runtime_packaging import CommandResult, HttpResponse, load_runtime_package

pytestmark = pytest.mark.docs

LIFECYCLE_DOCUMENT: dict[str, Any] = json.loads(
    LIFECYCLE_PATH.read_text(encoding="utf-8")
)

#: A few bytes standing in for 1.71 GiB. The suite proves the workflow's
#: mechanics; it proves nothing about the real artifact.
SYNTHETIC_BYTES = b"synthetic model bytes"


class ScriptedRunner:
    """Answer a Docker command by what it asks, and retain the exact vectors.

    Dispatching on the verb rather than on position is deliberate. A positional
    script encodes the exact number of commands :mod:`tools.runtime_packaging`
    happens to issue today, so adding one there would break every measurement
    test in this file with a failure in an unrelated module. This answers the
    questions the package actually asks, records every vector for inspection,
    and refuses one it does not recognise.
    """

    def __init__(
        self,
        *,
        owned: bool = False,
        running: bool = True,
        engine_version: str = "29.0.0",
    ) -> None:
        #: Whether a container carrying the package's ownership label exists.
        #: ``docker run`` sets it and ``docker rm`` clears it, as they do really.
        self.owned = owned
        self.running = running
        self.engine_version = engine_version
        self.calls: list[tuple[str, ...]] = []

    def run(self, arguments: Sequence[str]) -> CommandResult:
        command = tuple(arguments)
        self.calls.append(command)
        package = load_runtime_package()

        if command[1:2] == ("version",):
            return CommandResult(0, f"{self.engine_version}\n")
        if command[1:3] == ("image", "inspect"):
            return CommandResult(0, f"{package.image_reference}\n")
        if command[1:3] == ("container", "inspect"):
            if any("State.Running" in argument for argument in command):
                return CommandResult(0, f"{str(self.running).lower()}\n")
            if not self.owned:
                return CommandResult(1, "", "no such container")
            return CommandResult(0, f"{package.package_id}\n")
        if command[1:3] == ("container", "ls"):
            return CommandResult(0, "\n")
        if command[1:2] == ("run",):
            self.owned = True
            return CommandResult(0, "container-id\n")
        if command[1:2] == ("stop",):
            return CommandResult(0, "stopped\n")
        if command[1:2] == ("rm",):
            self.owned = False
            return CommandResult(0, "removed\n")
        raise AssertionError(f"unexpected command: {command}")


class FakeClock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.now += seconds


def _mutated(path: tuple[str, ...], value: object) -> dict[str, Any]:
    document = copy.deepcopy(LIFECYCLE_DOCUMENT)
    cursor: Any = document
    for member in path[:-1]:
        cursor = cursor[member]
    cursor[path[-1]] = value
    return document


def _write(tmp_path: Path, document: dict[str, Any]) -> Path:
    path = tmp_path / "model-lifecycle.v1.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    return path


def _refuses(tmp_path: Path, document: dict[str, Any], match: str) -> None:
    with pytest.raises(ModelLifecycleError, match=match):
        load_lifecycle(_write(tmp_path, document))


@pytest.fixture(scope="module")
def lifecycle():
    return load_lifecycle()


@pytest.fixture
def synthetic_cache(tmp_path: Path) -> tuple[ModelManifest, Path]:
    """A verified cache holding a handful of bytes instead of the real artifact."""
    import hashlib

    manifest = replace(
        load_manifest(),
        expected_size_bytes=len(SYNTHETIC_BYTES),
        sha256=f"sha256:{hashlib.sha256(SYNTHETIC_BYTES).hexdigest()}",
    )
    artifact = manifest.artifact_path(tmp_path)
    artifact.parent.mkdir(parents=True, exist_ok=True)
    artifact.write_bytes(SYNTHETIC_BYTES)
    return manifest, tmp_path


# --------------------------------------------------------------------------
# The record against the things it describes
# --------------------------------------------------------------------------


def test_the_record_agrees_with_the_container_package_on_every_shared_value(
    lifecycle,
) -> None:
    """Six numbers live in the package. A second copy of them is a second truth."""
    package = load_runtime_package()

    assert lifecycle.liveness_kind == package.liveness_kind
    assert lifecycle.liveness_port == package.liveness_port
    assert lifecycle.readiness_path == package.readiness_path
    assert lifecycle.readiness_ready_status == package.ready_status
    assert lifecycle.readiness_loading_status == package.loading_status
    assert lifecycle.startup_budget_ms == package.startup_budget_ms
    assert lifecycle.startup_poll_interval_ms == package.poll_interval_ms
    assert lifecycle.stop_timeout_seconds == package.stop_timeout_seconds


def test_the_drain_budget_is_the_api_module_s_own_default(lifecycle) -> None:
    assert lifecycle.drain_timeout_ms == DEFAULT_DRAIN_TIMEOUT_MS


def test_the_cache_root_is_the_one_the_model_source_record_names(lifecycle) -> None:
    assert lifecycle.cache_root == load_manifest().cache_path


def test_the_record_points_at_documents_that_exist(lifecycle) -> None:
    repo_root = LIFECYCLE_PATH.resolve().parents[3]
    for reference in (
        lifecycle.package_ref,
        lifecycle.model_source_ref,
        lifecycle.document_ref,
    ):
        assert (repo_root / reference).is_file(), reference


@pytest.mark.parametrize(
    ("path", "value", "match"),
    [
        (("probes", "liveness", "port"), 9090, "liveness probe port"),
        (("probes", "readiness", "path"), "/ready", "readiness path"),
        (("probes", "readiness", "readyStatus"), 204, "ready status"),
        (("probes", "readiness", "loadingStatus"), 425, "loading status"),
        (("startup", "budgetMs"), 60000, "startup budget"),
        (("startup", "pollIntervalMs"), 500, "poll interval"),
        (("shutdown", "stopTimeoutSeconds"), 30, "stop timeout"),
        (("shutdown", "drainTimeoutMs"), 30000, "drain budget"),
        (("cache", "rootPath"), ".cache/elsewhere", "cache root"),
        (("documentRef"), "docs/serving/nope.md", "documentRef"),
    ],
)
def test_a_value_that_drifted_from_its_neighbour_fails_to_load(
    tmp_path: Path, path, value, match
) -> None:
    keys = path if isinstance(path, tuple) else (path,)
    _refuses(tmp_path, _mutated(keys, value), match)


# --------------------------------------------------------------------------
# The invariants inside the record
# --------------------------------------------------------------------------


def test_liveness_passes_and_readiness_is_false_while_the_model_loads(
    lifecycle,
) -> None:
    """The property the whole record exists for.

    The runtime answers 503 on its health endpoint throughout the load. A
    liveness probe pointed at that endpoint restarts a healthy process mid-load
    and never converges, so the two probes must disagree here.
    """
    loading = lifecycle.rule(LifecycleState.RUNTIME_LOADING)

    assert loading.liveness is ProbeOutcome.PASS
    assert loading.readiness is False
    assert loading.accepts_work is False


def test_a_record_that_lets_liveness_fail_during_the_load_is_refused(
    tmp_path: Path,
) -> None:
    """It would describe a deployment a liveness probe restarts mid-load."""
    document = copy.deepcopy(LIFECYCLE_DOCUMENT)
    for state in document["states"]:
        if state["stateId"] == "runtime-loading":
            state["liveness"] = "fail"
    _refuses(tmp_path, document, "runtime-loading must pass liveness")


def test_a_record_that_lets_liveness_fail_during_the_drain_is_refused(
    tmp_path: Path,
) -> None:
    """A liveness failure during a drain kills the work the drain was waiting on."""
    document = copy.deepcopy(LIFECYCLE_DOCUMENT)
    for state in document["states"]:
        if state["stateId"] == "runtime-draining":
            state["liveness"] = "fail"
    _refuses(tmp_path, document, "runtime-draining must pass liveness")


def test_readiness_is_true_in_exactly_one_state_and_it_is_the_serving_one(
    lifecycle,
) -> None:
    ready = [rule.state for rule in lifecycle.states if rule.readiness]

    assert ready == [LifecycleState.RUNTIME_READY]
    assert lifecycle.readiness_true_in == (LifecycleState.RUNTIME_READY,)


def test_every_state_before_the_ready_one_reports_not_ready(lifecycle) -> None:
    """Readiness remains false until inference is possible, read off the table."""
    order = [rule.state for rule in lifecycle.states]
    ready_at = order.index(LifecycleState.RUNTIME_READY)

    assert all(not rule.readiness for rule in lifecycle.states[:ready_at])


def test_a_second_ready_state_is_refused(tmp_path: Path) -> None:
    document = copy.deepcopy(LIFECYCLE_DOCUMENT)
    for state in document["states"]:
        if state["stateId"] == "runtime-loading":
            state["readiness"] = True
            state["acceptsWork"] = True
    _refuses(tmp_path, document, "exactly one state may report readiness")


def test_a_state_that_accepts_work_without_reporting_ready_is_refused(
    tmp_path: Path,
) -> None:
    """Accepting work while unready is how a load balancer's answer stops meaning anything."""
    document = copy.deepcopy(LIFECYCLE_DOCUMENT)
    for state in document["states"]:
        if state["stateId"] == "runtime-draining":
            state["acceptsWork"] = True
    _refuses(tmp_path, document, "accepts work if and only if")


def test_an_artifact_state_may_not_claim_a_liveness_outcome(tmp_path: Path) -> None:
    """There is no process there for a probe to reach."""
    document = copy.deepcopy(LIFECYCLE_DOCUMENT)
    for state in document["states"]:
        if state["stateId"] == "artifact-verified":
            state["liveness"] = "pass"
    _refuses(tmp_path, document, "no process for a liveness probe")


def test_a_reordered_state_table_is_refused(tmp_path: Path) -> None:
    document = copy.deepcopy(LIFECYCLE_DOCUMENT)
    document["states"] = list(reversed(document["states"]))
    _refuses(tmp_path, document, "accepted order")


def test_the_declared_probe_states_are_derived_from_the_table_not_asserted(
    tmp_path: Path,
) -> None:
    """A probe list free to disagree with the table is a second, silent answer."""
    document = _mutated(("probes", "liveness", "passesIn"), ["runtime-ready"])
    _refuses(tmp_path, document, "disagree with the state table")


def test_a_restart_transition_is_required(tmp_path: Path) -> None:
    """Without it, "restart behaviour is predictable" is a sentence and not a rule."""
    document = copy.deepcopy(LIFECYCLE_DOCUMENT)
    document["transitions"] = [
        transition
        for transition in document["transitions"]
        if not (
            transition["from"] == "runtime-stopped"
            and transition["to"] == "runtime-starting"
        )
    ]
    _refuses(tmp_path, document, "no restart transition")


def test_a_drain_that_never_stops_is_refused(tmp_path: Path) -> None:
    document = copy.deepcopy(LIFECYCLE_DOCUMENT)
    document["transitions"] = [
        transition
        for transition in document["transitions"]
        if not (
            transition["from"] == "runtime-draining"
            and transition["to"] == "runtime-stopped"
        )
    ]
    _refuses(tmp_path, document, "not a shutdown")


def test_every_state_is_reachable_from_an_empty_cache(lifecycle) -> None:
    reached = {LifecycleState.ARTIFACT_ABSENT}
    changed = True
    while changed:
        changed = False
        for transition in lifecycle.transitions:
            if transition.source in reached and transition.target not in reached:
                reached.add(transition.target)
                changed = True

    assert reached == set(LifecycleState)


def test_the_shutdown_order_reports_unready_before_it_drains(lifecycle) -> None:
    """The ordering is the property; a drain that runs first receives what it was avoiding."""
    assert "readiness false" in lifecycle.shutdown_order[0]
    assert "drain" in lifecycle.shutdown_order[1]
    assert "remove" in lifecycle.shutdown_order[-1]


def test_a_shutdown_that_drains_before_reporting_unready_is_refused(
    tmp_path: Path,
) -> None:
    document = copy.deepcopy(LIFECYCLE_DOCUMENT)
    order = list(document["shutdown"]["order"])
    order[0], order[1] = order[1], order[0]
    document["shutdown"]["order"] = order
    _refuses(tmp_path, document, "not the accepted sequence")


def test_rewording_a_step_description_is_not_a_loading_failure(
    tmp_path: Path,
) -> None:
    """The order is matched on step identifiers, not on the prose beside them.

    A record whose steps are checked by substring cannot be reworded without
    breaking, and a reworded step can silently stop being checked. Both are
    avoided by giving each step an identifier.
    """
    document = copy.deepcopy(LIFECYCLE_DOCUMENT)
    for step in document["shutdown"]["order"]:
        step["description"] = f"reworded: {step['description']}"

    reworded = load_lifecycle(_write(tmp_path, document))

    assert reworded.shutdown_steps == load_lifecycle().shutdown_steps
    assert all(text.startswith("reworded:") for text in reworded.shutdown_order)


def test_a_renamed_shutdown_step_is_refused(tmp_path: Path) -> None:
    document = copy.deepcopy(LIFECYCLE_DOCUMENT)
    document["shutdown"]["order"][0]["step"] = "drain-first-and-hope"
    _refuses(tmp_path, document, "not the accepted sequence")


def test_only_a_cache_hit_may_proceed_without_a_network(lifecycle) -> None:
    by_state = {rule.cache_state: rule for rule in lifecycle.cache_rules}

    assert by_state[CacheState.HIT].requires_network is False
    assert by_state[CacheState.MISS].requires_network is True
    assert by_state[CacheState.PARTIAL].requires_network is True


def test_a_cache_hit_declared_to_need_a_network_is_refused(tmp_path: Path) -> None:
    document = copy.deepcopy(LIFECYCLE_DOCUMENT)
    for rule in document["cache"]["states"]:
        if rule["cacheState"] == "hit":
            rule["requiresNetwork"] = True
    _refuses(tmp_path, document, "without a network connection")


def test_a_restart_that_does_not_preserve_its_artifact_is_refused(
    tmp_path: Path,
) -> None:
    """Every restart would become a 1.71 GiB download."""
    _refuses(
        tmp_path,
        _mutated(("restart", "artifactSurvives"), False),
        "makes every restart a download",
    )


def test_a_restart_that_inherits_readiness_is_refused(tmp_path: Path) -> None:
    _refuses(
        tmp_path,
        _mutated(("restart", "readinessResets"), False),
        "reports a fresh process ready before it is",
    )


def test_the_measurement_directory_may_not_be_the_model_cache(tmp_path: Path) -> None:
    """The refusal that stops a cleanup path deleting 1.71 GiB of model bytes.

    It asserts the model-cache message specifically. Matching the generic
    "not the managed one" would pass with this guard deleted, because the pinned
    directory equality beside it refuses the same document for another reason.
    """
    _refuses(
        tmp_path,
        _mutated(("measurement", "directory"), MODEL_CACHE_DIRECTORY.as_posix()),
        "may not be the model cache",
    )


def test_the_record_declares_the_three_observations_the_two_comparisons_use(
    lifecycle,
) -> None:
    assert lifecycle.observation_ids == ("cold", "warm", "restart")


def test_the_two_comparisons_write_four_distinct_files(lifecycle) -> None:
    """A restart summary written over a cold/warm summary is the failure here.

    It would not be a corrupted file. It would be a readable one describing an
    experiment that was never run, which is worse, so the loader refuses a
    record whose four file names are not four.
    """
    names = (
        lifecycle.raw_file,
        lifecycle.summary_file,
        lifecycle.restart_raw_file,
        lifecycle.restart_summary_file,
    )
    assert len(set(names)) == 4


def test_a_record_reusing_one_file_name_for_both_comparisons_is_refused(
    tmp_path: Path,
) -> None:
    _refuses(
        tmp_path,
        _mutated(("measurement", "restartSummaryFile"), "summary.json"),
        "four distinct result files",
    )


# --------------------------------------------------------------------------
# Cache classification, offline
# --------------------------------------------------------------------------


def test_an_empty_cache_is_a_miss_that_maps_to_the_absent_state(tmp_path: Path) -> None:
    observation = observe_cache(load_manifest(), repo_root=tmp_path)

    assert observation.cache_state is CacheState.MISS
    assert observation.bytes_present == 0
    assert observation.lifecycle_state is LifecycleState.ARTIFACT_ABSENT
    assert observation.verified is False


def test_a_resumable_transfer_is_a_partial_and_reports_the_bytes_it_holds(
    tmp_path: Path,
) -> None:
    manifest = load_manifest()
    partial = manifest.partial_path(tmp_path)
    partial.parent.mkdir(parents=True, exist_ok=True)
    partial.write_bytes(b"1234")

    observation = observe_cache(manifest, repo_root=tmp_path)

    assert observation.cache_state is CacheState.PARTIAL
    assert observation.bytes_present == 4
    assert observation.lifecycle_state is LifecycleState.ARTIFACT_PARTIAL


def test_a_present_artifact_is_a_hit_and_is_not_read_unless_asked(
    synthetic_cache: tuple[ModelManifest, Path],
) -> None:
    """Verification is opt-in because reading 1.71 GiB warms the cache being measured."""
    manifest, repo_root = synthetic_cache

    unverified = observe_cache(manifest, repo_root=repo_root)
    verified = observe_cache(manifest, repo_root=repo_root, verify=True)

    assert unverified.cache_state is CacheState.HIT
    assert unverified.verified is False
    assert verified.verified is True
    assert verified.bytes_present == len(SYNTHETIC_BYTES)


def test_a_cached_file_whose_digest_is_wrong_is_refused(
    synthetic_cache: tuple[ModelManifest, Path],
) -> None:
    manifest, repo_root = synthetic_cache
    manifest.artifact_path(repo_root).write_bytes(b"different but same length")
    wrong_length = replace(manifest, expected_size_bytes=25)

    with pytest.raises(ModelLifecycleError, match="does not match the pinned source"):
        observe_cache(wrong_length, repo_root=repo_root, verify=True)


# --------------------------------------------------------------------------
# The measurement, and what it refuses
# --------------------------------------------------------------------------


def _ready_runner() -> ScriptedRunner:
    """A host with Docker, the pinned image, and no container of our name yet."""
    return ScriptedRunner()


def _completion() -> HttpResponse:
    return HttpResponse(200, {"choices": [{"message": {"content": "ok"}}]})


def _observe(
    lifecycle,
    synthetic_cache: tuple[ModelManifest, Path],
    *,
    statuses: Sequence[int],
    liveness: Sequence[bool],
    monkeypatch: pytest.MonkeyPatch,
):
    manifest, repo_root = synthetic_cache
    monkeypatch.setattr(
        "tools.runtime_packaging.core.load_manifest", lambda *_a, **_k: manifest
    )
    monkeypatch.setattr("tools.runtime_packaging.core.verify_artifact", lambda *_: None)
    status_iter = iter(statuses)
    live_iter = iter(liveness)
    clock = FakeClock()
    runner = _ready_runner()

    observation = observe_start(
        lifecycle,
        load_runtime_package(),
        runner,
        observation_id="cold",
        confirmed=True,
        http_get=lambda _url, _timeout: HttpResponse(next(status_iter)),
        http_post=lambda _url, _body, _timeout: _completion(),
        tcp_probe=lambda _host, _port, _timeout: next(live_iter),
        manifest=manifest,
        repo_root=repo_root,
        clock=clock,
        sleeper=clock.sleep,
    )
    return observation, runner


def test_a_measured_start_records_liveness_passing_while_readiness_is_still_false(
    lifecycle,
    synthetic_cache: tuple[ModelManifest, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The acceptance criterion, measured rather than asserted.

    The two probes are asked at the same moment, so a sample in which one says
    live and the other says 503 is direct evidence that a liveness probe would
    not have restarted this process while it loaded.
    """
    observation, _ = _observe(
        lifecycle,
        synthetic_cache,
        statuses=(503, 503, 200),
        liveness=(True, True, True),
        monkeypatch=monkeypatch,
    )

    assert observation.liveness_held_while_loading is True
    assert observation.liveness_never_dropped_after_it_passed is True
    assert observation.readiness_false_until_ready is True
    assert observation.cache_state is CacheState.HIT
    assert [sample.readiness_status for sample in observation.samples] == [
        503,
        503,
        200,
    ]


def test_a_start_whose_socket_was_unreachable_does_not_claim_a_clean_readiness_trace(
    lifecycle,
    synthetic_cache: tuple[ModelManifest, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """`readinessFalseUntilReady` is a property that can fail, and this is how.

    A sample that reached no socket at all is recorded as status 0. That is not
    the runtime saying it is loading, so an observation containing one does not
    get to report a clean readiness trace — which is the whole reason the
    property is derived from the loading count rather than from "nothing said
    ready before the end", a form that is true of every observation by
    construction.
    """
    observation, _ = _observe(
        lifecycle,
        synthetic_cache,
        statuses=(0, 503, 200),
        liveness=(False, True, True),
        monkeypatch=monkeypatch,
    )

    assert [sample.readiness_status for sample in observation.samples] == [0, 503, 200]
    assert observation.readiness_false_until_ready is False
    assert observation.liveness_held_while_loading is True
    assert observation.first_liveness_ms == observation.samples[1].elapsed_ms


def test_a_liveness_probe_that_dropped_mid_load_is_reported_not_hidden(
    lifecycle,
    synthetic_cache: tuple[ModelManifest, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A drop after the first pass is what would make a restart real."""
    observation, _ = _observe(
        lifecycle,
        synthetic_cache,
        statuses=(503, 503, 200),
        liveness=(True, False, True),
        monkeypatch=monkeypatch,
    )

    assert observation.liveness_never_dropped_after_it_passed is False


def test_a_measured_start_always_stops_and_removes_its_container(
    lifecycle,
    synthetic_cache: tuple[ModelManifest, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _, runner = _observe(
        lifecycle,
        synthetic_cache,
        statuses=(503, 503, 200),
        liveness=(True, True, True),
        monkeypatch=monkeypatch,
    )

    assert any(call[:2] == ("docker", "stop") for call in runner.calls)
    assert any(call[:2] == ("docker", "rm") for call in runner.calls)


def test_a_start_that_fails_still_removes_its_container(
    lifecycle,
    synthetic_cache: tuple[ModelManifest, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed observation that leaked a container would block the next one."""
    manifest, repo_root = synthetic_cache
    monkeypatch.setattr(
        "tools.runtime_packaging.core.load_manifest", lambda *_a, **_k: manifest
    )
    monkeypatch.setattr("tools.runtime_packaging.core.verify_artifact", lambda *_: None)
    # One sample: the first unexpected status ends the loop immediately.
    runner = _ready_runner()
    clock = FakeClock()

    with pytest.raises(ModelLifecycleError, match="does not publish"):
        observe_start(
            lifecycle,
            load_runtime_package(),
            runner,
            observation_id="cold",
            confirmed=True,
            http_get=lambda _url, _timeout: HttpResponse(418),
            http_post=lambda *_: pytest.fail("inference must not be attempted"),
            tcp_probe=lambda *_: True,
            manifest=manifest,
            repo_root=repo_root,
            clock=clock,
            sleeper=clock.sleep,
        )

    assert any(call[:2] == ("docker", "rm") for call in runner.calls)


def test_a_measured_start_refuses_without_the_real_runtime_confirmation(
    lifecycle,
) -> None:
    with pytest.raises(LifecycleRefused, match="confirm-real-runtime"):
        observe_start(
            lifecycle,
            load_runtime_package(),
            ScriptedRunner(),
            observation_id="cold",
            confirmed=False,
            http_get=lambda *_: pytest.fail("no HTTP without confirmation"),
            http_post=lambda *_: pytest.fail("no HTTP without confirmation"),
        )


def test_a_measured_start_refuses_a_cache_that_is_not_a_hit(
    lifecycle, tmp_path: Path
) -> None:
    """It never downloads implicitly, so a miss is a refusal rather than a transfer."""
    with pytest.raises(ModelLifecycleError, match="acquire it explicitly"):
        observe_start(
            lifecycle,
            load_runtime_package(),
            ScriptedRunner(),
            observation_id="cold",
            confirmed=True,
            http_get=lambda *_: pytest.fail("no HTTP for an empty cache"),
            http_post=lambda *_: pytest.fail("no HTTP for an empty cache"),
            repo_root=tmp_path,
        )


def test_a_start_named_by_no_declared_observation_is_refused(
    lifecycle, tmp_path: Path
) -> None:
    with pytest.raises(ModelLifecycleError, match="no such observation"):
        observe_start(
            lifecycle,
            load_runtime_package(),
            ScriptedRunner(),
            observation_id="lukewarm",
            confirmed=True,
            http_get=lambda *_: pytest.fail("unreachable"),
            http_post=lambda *_: pytest.fail("unreachable"),
            repo_root=tmp_path,
        )


def test_the_startup_wait_is_bounded_by_the_budget_the_package_pins(
    lifecycle,
    synthetic_cache: tuple[ModelManifest, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    manifest, repo_root = synthetic_cache
    monkeypatch.setattr(
        "tools.runtime_packaging.core.load_manifest", lambda *_a, **_k: manifest
    )
    monkeypatch.setattr("tools.runtime_packaging.core.verify_artifact", lambda *_: None)
    bounded = replace(lifecycle, startup_budget_ms=1_000)
    runner = _ready_runner()
    clock = FakeClock()

    with pytest.raises(ModelLifecycleError, match="within the startup budget"):
        observe_start(
            bounded,
            load_runtime_package(),
            runner,
            observation_id="cold",
            confirmed=True,
            http_get=lambda _url, _timeout: HttpResponse(503),
            http_post=lambda *_: pytest.fail("never ready, never probed"),
            tcp_probe=lambda *_: True,
            manifest=manifest,
            repo_root=repo_root,
            clock=clock,
            sleeper=clock.sleep,
        )


def test_a_comparison_reports_both_starts_as_hits_and_the_artifact_as_preserved(
    lifecycle,
    synthetic_cache: tuple[ModelManifest, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Restart behaviour, read off a comparison rather than promised in a document."""
    manifest, repo_root = synthetic_cache
    monkeypatch.setattr(
        "tools.runtime_packaging.core.load_manifest", lambda *_a, **_k: manifest
    )
    monkeypatch.setattr("tools.runtime_packaging.core.verify_artifact", lambda *_: None)
    package = load_runtime_package()
    runner = _ready_runner()
    statuses = iter((503, 200, 503, 200))
    clock = FakeClock()

    result = compare_starts(
        lifecycle,
        package,
        runner,
        confirmed=True,
        http_get=lambda _url, _timeout: HttpResponse(next(statuses)),
        http_post=lambda _url, _body, _timeout: _completion(),
        tcp_probe=lambda *_: True,
        manifest=manifest,
        repo_root=repo_root,
        clock=clock,
        sleeper=clock.sleep,
        now=lambda: 1_700_000_000.0,
    )

    assert result.cold.cache_state is CacheState.HIT
    assert result.warm.cache_state is CacheState.HIT
    assert result.verified_before_warm is True
    assert result.verified_after_warm is True
    assert result.artifact_survived_restart is True
    assert result.environment.model_sha256 == manifest.sha256


def _compare_restart(
    lifecycle,
    synthetic_cache: tuple[ModelManifest, Path],
    monkeypatch: pytest.MonkeyPatch,
    *,
    statuses: Sequence[int],
    reads: list[str],
) -> RestartResult:
    """Drive a restart comparison, recording when the artifact is read end to end.

    `reads` receives an entry for every readiness probe and for every end-to-end
    read of the artifact, in the order they happen, so a test can assert *where*
    in the sequence each read fell rather than only how many there were.
    Counting alone would not do: a read moved from after the second start to
    between the two starts is still the same number of reads.

    **Both** read sites are instrumented, and that is the point. Independent
    review found this helper patching `tools.runtime_packaging.core` to a silent
    no-op, which made it blind to the read `preflight` performs before every
    start -- the read that made an earlier version of the claim below false. A
    seam muted rather than recorded is a test asserting the absence of something
    it arranged not to see.
    """
    manifest, repo_root = synthetic_cache
    monkeypatch.setattr(
        "tools.runtime_packaging.core.load_manifest", lambda *_a, **_k: manifest
    )
    # `preflight` hash-verifies the artifact before it creates a container, so
    # this fires once per start.
    monkeypatch.setattr(
        "tools.runtime_packaging.core.verify_artifact",
        lambda *_: reads.append("preflight-verify"),
    )
    # `observe_cache` resolves this name when it reads the artifact end to end.
    # A patch anywhere else would leave this test asserting nothing.
    monkeypatch.setattr(
        "tools.model_lifecycle.core.verify_artifact",
        lambda *_: reads.append("verify"),
    )
    status_iter = iter(statuses)
    clock = FakeClock()

    def _probe(_url: str, _timeout: float) -> HttpResponse:
        status = next(status_iter)
        reads.append(f"probe:{status}")
        return HttpResponse(status)

    return compare_restart(
        lifecycle,
        load_runtime_package(),
        _ready_runner(),
        confirmed=True,
        http_get=_probe,
        http_post=lambda _url, _body, _timeout: _completion(),
        tcp_probe=lambda *_: True,
        manifest=manifest,
        repo_root=repo_root,
        clock=clock,
        sleeper=clock.sleep,
        now=lambda: 1_700_000_000.0,
    )


def test_a_restart_comparison_reports_the_artifact_as_surviving_the_stop(
    lifecycle,
    synthetic_cache: tuple[ModelManifest, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The claim the record makes about a restart, read off a measurement.

    The byte count is compared at three points -- before the first start,
    between the two, and after the second -- so an artifact that was replaced
    while nothing was running would be visible rather than assumed away.
    """
    reads: list[str] = []
    result = _compare_restart(
        lifecycle,
        synthetic_cache,
        monkeypatch,
        statuses=(503, 200, 503, 200),
        reads=reads,
    )

    assert result.cold.cache_state is CacheState.HIT
    assert result.restart.cache_state is CacheState.HIT
    assert result.cache_state_between is CacheState.HIT
    assert result.bytes_between == len(SYNTHETIC_BYTES)
    assert result.verified_after_restart is True
    assert result.artifact_survived_restart is True
    assert result.restart_needed_no_network is True
    assert result.readiness_reset_on_restart is True


def test_a_restart_comparison_adds_no_read_of_its_own_between_the_two_starts(
    lifecycle,
    synthetic_cache: tuple[ModelManifest, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """What this comparison adds to the interval, which is nothing.

    The cold/warm comparison reads the artifact end to end between its arms on
    purpose, to warm the host file cache. This one does not: it classifies the
    cache without opening the file and leaves its own digest read until after
    both starts.

    The asserted sequence is the whole sequence rather than the part that
    flatters the claim. It shows `preflight` reading the artifact before each
    start, which is what makes the stronger claim -- that the interval is
    read-free -- false, and it is asserted here so that the code and the
    documents cannot drift back to it.
    """
    reads: list[str] = []
    _compare_restart(
        lifecycle,
        synthetic_cache,
        monkeypatch,
        statuses=(503, 200, 503, 200),
        reads=reads,
    )

    assert reads == [
        "preflight-verify",
        "probe:503",
        "probe:200",
        "preflight-verify",
        "probe:503",
        "probe:200",
        "verify",
    ], (
        "this comparison's own end-to-end read falls after the last probe of "
        "the second start; the two before the starts belong to preflight and "
        "are the reason no start measured here is cache-cold"
    )
    assert reads.index("verify") == len(reads) - 1
    assert reads.count("verify") == 1


def test_a_restarted_runtime_that_came_back_ready_is_not_reported_as_a_reset(
    lifecycle,
    synthetic_cache: tuple[ModelManifest, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """The property fails when it should, which is what makes publishing it worth
    anything.

    The second start answers `200` on its very first sample. Readiness therefore
    never began false for it, and a comparison that still claimed the reset
    would be claiming something it did not observe.
    """
    reads: list[str] = []
    result = _compare_restart(
        lifecycle,
        synthetic_cache,
        monkeypatch,
        statuses=(503, 200, 200),
        reads=reads,
    )

    assert result.restart.readiness_started_not_ready is False
    assert result.readiness_reset_on_restart is False
    assert reads == [
        "preflight-verify",
        "probe:503",
        "probe:200",
        "preflight-verify",
        "probe:200",
        "verify",
    ]
    assert (
        summarize_restart(lifecycle, result)["acceptance"]["readinessResetOnRestart"]
        is False
    )


def test_a_restart_comparison_refuses_without_the_real_runtime_confirmation(
    lifecycle, tmp_path: Path
) -> None:
    with pytest.raises(LifecycleRefused, match="confirm-real-runtime"):
        compare_restart(
            lifecycle,
            load_runtime_package(),
            ScriptedRunner(),
            confirmed=False,
            http_get=lambda *_: pytest.fail("unreachable"),
            http_post=lambda *_: pytest.fail("unreachable"),
            repo_root=tmp_path,
        )


def test_a_restart_comparison_refuses_to_start_beside_an_existing_container(
    lifecycle, tmp_path: Path
) -> None:
    with pytest.raises(ModelLifecycleError, match="already exists"):
        compare_restart(
            lifecycle,
            load_runtime_package(),
            ScriptedRunner(owned=True),
            confirmed=True,
            http_get=lambda *_: pytest.fail("unreachable"),
            http_post=lambda *_: pytest.fail("unreachable"),
            repo_root=tmp_path,
        )


def test_a_comparison_refuses_to_start_beside_an_existing_owned_container(
    lifecycle, tmp_path: Path
) -> None:
    package = load_runtime_package()
    # A container already carries the package's own name.
    runner = ScriptedRunner(owned=True)

    with pytest.raises(ModelLifecycleError, match="already exists"):
        compare_starts(
            lifecycle,
            package,
            runner,
            confirmed=True,
            http_get=lambda *_: pytest.fail("unreachable"),
            http_post=lambda *_: pytest.fail("unreachable"),
            repo_root=tmp_path,
        )


def test_a_comparison_refuses_without_the_real_runtime_confirmation(
    lifecycle, tmp_path: Path
) -> None:
    with pytest.raises(LifecycleRefused, match="confirm-real-runtime"):
        compare_starts(
            lifecycle,
            load_runtime_package(),
            ScriptedRunner(),
            confirmed=False,
            http_get=lambda *_: pytest.fail("unreachable"),
            http_post=lambda *_: pytest.fail("unreachable"),
            repo_root=tmp_path,
        )


# --------------------------------------------------------------------------
# The records this writes, and the cleanup that may only reach them
# --------------------------------------------------------------------------


def _observation(observation_id: str) -> StartObservation:
    return StartObservation(
        observation_id=observation_id,
        cache_state=CacheState.HIT,
        artifact_bytes=len(SYNTHETIC_BYTES),
        ready_status=200,
        loading_status=503,
        create_ms=10,
        first_liveness_ms=20,
        ready_ms=100 if observation_id == "cold" else 60,
        inference_ms=5,
        inference_status=200,
        stop_ms=7,
        samples=(
            ProbeSample(elapsed_ms=20, liveness=True, readiness_status=503),
            ProbeSample(elapsed_ms=60, liveness=True, readiness_status=200),
        ),
    )


def _result(
    observation_id_pair: tuple[str, str] = ("cold", "warm"),
) -> ComparisonResult:
    return ComparisonResult(
        lifecycle_id="inferops-local-model-lifecycle",
        started_at="2026-01-01T00:00:00+00:00",
        environment=Environment(
            platform="synthetic",
            python_version="3.12.0",
            engine_version="29.0.0",
            image_reference=load_runtime_package().image_reference,
            model_revision="revision",
            model_sha256="sha256:" + "0" * 64,
        ),
        cold=_observation(observation_id_pair[0]),
        warm=_observation(observation_id_pair[1]),
        verify_ms=42,
        verified_before_warm=True,
        verified_after_warm=True,
    )


def test_an_observation_record_carries_no_prompt_completion_or_model_byte() -> None:
    """The record is timings, statuses, and booleans. Nothing else is in it."""
    document = json.dumps(observation_document(_observation("cold")))

    for forbidden in ("prompt", "content", "message", "choices", "synthetic model"):
        assert forbidden not in document, forbidden


def test_the_summary_reports_each_acceptance_property_it_measured(lifecycle) -> None:
    document = summarize(lifecycle, _result())

    assert document["acceptance"] == {
        "cacheHitInBothStarts": True,
        "livenessHeldWhileLoading": True,
        "readinessFalseUntilReady": True,
        "artifactSurvivedRestart": True,
    }
    assert document["readyMsDelta"] == -40
    assert document["evidenceClass"] == "local-real-cpu"
    assert document["certificationCeiling"] == "C2"


def test_results_round_trip_through_the_managed_directory(
    lifecycle, tmp_path: Path
) -> None:
    raw, summary = write_results(lifecycle, _result(), repo_root=tmp_path)

    assert raw.parent == tmp_path / EXPECTED_RESULT_DIRECTORY
    assert json.loads(summary.read_text(encoding="utf-8"))["lifecycleId"]
    documents = read_results(lifecycle, repo_root=tmp_path)
    assert [document["observationId"] for document in documents] == ["cold", "warm"]


def _restart_result() -> RestartResult:
    return RestartResult(
        lifecycle_id="inferops-local-model-lifecycle",
        started_at="2026-01-01T00:00:00+00:00",
        environment=Environment(
            platform="synthetic",
            python_version="3.12.0",
            engine_version="29.0.0",
            image_reference=load_runtime_package().image_reference,
            model_revision="revision",
            model_sha256="sha256:" + "0" * 64,
        ),
        cold=_observation("cold"),
        restart=_observation("restart"),
        cache_state_between=CacheState.HIT,
        bytes_between=len(SYNTHETIC_BYTES),
        verify_ms=42,
        verified_after_restart=True,
    )


def test_the_restart_summary_reports_each_property_it_measured(lifecycle) -> None:
    document = summarize_restart(lifecycle, _restart_result())

    assert document["comparison"] == "restart"
    assert document["acceptance"] == {
        "artifactSurvivedRestart": True,
        "readinessResetOnRestart": True,
        "restartNeededNoNetwork": True,
        "livenessHeldWhileLoading": True,
        "readinessFalseUntilReady": True,
    }
    assert document["cacheStateBetweenStarts"] == "hit"
    assert document["readyMsDelta"] == -40
    assert document["evidenceClass"] == "local-real-cpu"
    assert document["certificationCeiling"] == "C2"


def test_a_restart_record_carries_no_prompt_completion_or_model_byte(
    lifecycle,
) -> None:
    document = json.dumps(summarize_restart(lifecycle, _restart_result()))

    for forbidden in ("prompt", "content", "message", "choices", "synthetic model"):
        assert forbidden not in document, forbidden


def test_the_two_comparisons_do_not_overwrite_each_other(
    lifecycle, tmp_path: Path
) -> None:
    """Both written into one directory, and both still readable afterwards.

    Written in this order on purpose: the restart pair second, so that a shared
    file name would leave the cold/warm summary describing the restart run and
    this assertion would fail on the round trip rather than on the file count.
    """
    write_results(lifecycle, _result(), repo_root=tmp_path)
    restart_raw, restart_summary = write_restart_results(
        lifecycle, _restart_result(), repo_root=tmp_path
    )

    assert restart_raw.parent == tmp_path / EXPECTED_RESULT_DIRECTORY
    assert [
        d["observationId"] for d in read_results(lifecycle, repo_root=tmp_path)
    ] == [
        "cold",
        "warm",
    ]
    assert [
        d["observationId"] for d in read_restart_results(lifecycle, repo_root=tmp_path)
    ] == ["cold", "restart"]
    assert json.loads(restart_summary.read_text(encoding="utf-8"))["comparison"] == (
        "restart"
    )


def test_a_restart_result_is_refused_before_the_comparison_has_been_run(
    lifecycle, tmp_path: Path
) -> None:
    with pytest.raises(ModelLifecycleError, match="no raw lifecycle result"):
        read_restart_results(lifecycle, repo_root=tmp_path)


def test_cleanup_reaches_both_comparisons_and_still_nothing_else(
    lifecycle, tmp_path: Path
) -> None:
    """The restart files are new, and the cleanup that may reach them is not.

    Scoping is by directory rather than by file name, so a comparison added
    later lands inside the guarded tree by construction. This asserts that it
    did rather than trusting that it would.
    """
    write_results(lifecycle, _result(), repo_root=tmp_path)
    write_restart_results(lifecycle, _restart_result(), repo_root=tmp_path)
    directory = tmp_path / EXPECTED_RESULT_DIRECTORY
    assert (directory / lifecycle.restart_summary_file).is_file()

    cleanup = clean_results(lifecycle, repo_root=tmp_path, confirm=True)

    assert cleanup.removed is True
    assert not directory.exists()
    assert (tmp_path / MODEL_CACHE_DIRECTORY).exists() is False


def test_an_observation_with_no_samples_claims_no_readiness_reset() -> None:
    """The branch the pipeline cannot reach, asserted rather than assumed.

    `_sample_until_ready` never returns an empty tuple, so nothing in normal
    operation builds this observation. The default still has to be the one that
    claims less: an observation that watched nothing has not seen readiness
    start false, and reporting a reset off it would be reporting a measurement
    nobody took.
    """
    observation = replace(_observation("restart"), samples=())

    assert observation.readiness_started_not_ready is False
    assert observation.readiness_false_until_ready is False


def test_a_raw_line_naming_an_undeclared_observation_is_refused(
    lifecycle, tmp_path: Path
) -> None:
    directory = tmp_path / EXPECTED_RESULT_DIRECTORY
    directory.mkdir(parents=True)
    (directory / lifecycle.raw_file).write_text(
        json.dumps({"observationId": "lukewarm"}) + "\n", encoding="utf-8"
    )

    with pytest.raises(ModelLifecycleError, match="undeclared observation"):
        read_results(lifecycle, repo_root=tmp_path)


def test_cleanup_removes_only_this_tool_s_own_directory(
    lifecycle, tmp_path: Path
) -> None:
    """The model cache is a sibling, and it must survive a confirmed cleanup."""
    write_results(lifecycle, _result(), repo_root=tmp_path)
    model_cache = tmp_path / MODEL_CACHE_DIRECTORY
    model_cache.mkdir(parents=True, exist_ok=True)
    (model_cache / "weights.gguf").write_bytes(SYNTHETIC_BYTES)
    baseline = tmp_path / ".cache/inferops/baseline"
    baseline.mkdir(parents=True, exist_ok=True)
    (baseline / "summary.json").write_text("{}", encoding="utf-8")

    cleanup = clean_results(lifecycle, repo_root=tmp_path, confirm=True)

    assert cleanup.removed is True
    assert not (tmp_path / EXPECTED_RESULT_DIRECTORY).exists()
    assert (model_cache / "weights.gguf").read_bytes() == SYNTHETIC_BYTES
    assert (baseline / "summary.json").is_file()


def test_cleanup_without_confirmation_reports_and_changes_nothing(
    lifecycle, tmp_path: Path
) -> None:
    write_results(lifecycle, _result(), repo_root=tmp_path)

    cleanup = clean_results(lifecycle, repo_root=tmp_path)

    assert cleanup.removed is False
    assert cleanup.bytes_found > 0
    assert (tmp_path / EXPECTED_RESULT_DIRECTORY).exists()


def test_the_results_directory_is_refused_when_it_is_the_model_cache(
    tmp_path: Path,
) -> None:
    """Both entry points refuse it, and both name the model cache when they do."""
    diverted = replace(load_lifecycle(), result_directory=MODEL_CACHE_DIRECTORY)

    with pytest.raises(ModelLifecycleError, match="may not be the model cache"):
        result_directory(diverted, repo_root=tmp_path)
    with pytest.raises(ModelLifecycleError, match="may not be the model cache"):
        clean_results(diverted, repo_root=tmp_path, confirm=True)


def test_this_module_s_model_cache_constant_is_held_to_the_source_record() -> None:
    """It is a convenience alias, not a second answer to where the cache is."""
    assert load_manifest().cache_path == MODEL_CACHE_DIRECTORY


def test_cleanup_refuses_a_symbolic_link_above_the_managed_tree(
    lifecycle, tmp_path: Path
) -> None:
    """A link in the path is refused rather than followed into whatever it names."""
    real = tmp_path / "elsewhere"
    real.mkdir()
    link = tmp_path / ".cache" / "inferops"
    link.parent.mkdir(parents=True)
    try:
        link.symlink_to(real, target_is_directory=True)
    except (OSError, NotImplementedError):
        pytest.skip("this host does not permit creating a symbolic link")

    with pytest.raises(ModelLifecycleError, match="symbolic link"):
        clean_results(lifecycle, repo_root=tmp_path, confirm=True)


def test_cleanup_refuses_a_symbolic_link_inside_the_results_directory(
    lifecycle, tmp_path: Path
) -> None:
    outside = tmp_path / "outside.json"
    outside.write_text("{}", encoding="utf-8")
    write_results(lifecycle, _result(), repo_root=tmp_path)
    link = tmp_path / EXPECTED_RESULT_DIRECTORY / "linked.json"
    try:
        link.symlink_to(outside)
    except (OSError, NotImplementedError):
        pytest.skip("this host does not permit creating a symbolic link")

    with pytest.raises(ModelLifecycleError, match="symbolic link"):
        clean_results(lifecycle, repo_root=tmp_path, confirm=True)
    assert outside.is_file(), "the link's target must not have been removed"


def test_a_results_directory_resolving_outside_the_checkout_is_refused(
    lifecycle, tmp_path: Path
) -> None:
    """A repository root that is not a parent of what it resolves to is refused."""
    diverted = replace(lifecycle, result_directory=Path("../lifecycle"))

    with pytest.raises(ModelLifecycleError, match="not the managed one"):
        result_directory(diverted, repo_root=tmp_path)


# --------------------------------------------------------------------------
# The command
# --------------------------------------------------------------------------


def test_the_offline_commands_report_the_record_and_the_cache(
    capsys: pytest.CaptureFixture[str],
) -> None:
    assert main(["check"]) == 0
    assert "inferops-local-model-lifecycle" in capsys.readouterr().out

    assert main(["states"]) == 0
    output = capsys.readouterr().out
    for state in LifecycleState:
        assert str(state) in output


def _redirect_results(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Path:
    """Point the command's results directory at a temporary one.

    `read_results` binds the repository root as a default argument, so patching
    the module constant would not reach it. The directory resolver is the seam
    every reader and writer actually goes through, and it is the one that
    carries the guards, so redirecting it keeps those guards in the path.
    """
    directory = tmp_path / EXPECTED_RESULT_DIRECTORY
    monkeypatch.setattr(
        "tools.model_lifecycle.core.result_directory",
        lambda _lifecycle, **_kwargs: directory,
    )
    return directory


def test_the_results_command_refuses_when_neither_comparison_has_been_run(
    lifecycle,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Nothing measured is a refusal and not a silent success.

    A command that printed two "not run" lines and exited zero would let a
    script that checks the exit code conclude a measurement had happened.
    """
    _redirect_results(monkeypatch, tmp_path)

    assert main(["results"]) == 3
    output = capsys.readouterr().out
    assert "cold/warm  not run" in output
    assert "restart    not run" in output


def test_the_results_command_reports_one_comparison_and_names_the_absent_one(
    lifecycle,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A reader who sees numbers must be able to tell which experiment made them."""
    _redirect_results(monkeypatch, tmp_path)
    write_restart_results(lifecycle, _restart_result(), repo_root=tmp_path)

    assert main(["results"]) == 0
    output = capsys.readouterr().out
    assert "cold/warm  not run" in output
    assert "restart    cold" in output
    assert "restart    restart" in output


def test_the_results_command_does_not_report_a_corrupt_result_as_not_run(
    lifecycle,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The distinction the "not run" line exists to keep.

    A result that exists and disagrees with the record is not an absent one.
    Printing "not run" over it would hide a corrupt file behind a message that
    reads like a clean, empty state -- so the absence has its own exception type
    and everything else reaches the refusal with its own message.
    """
    directory = _redirect_results(monkeypatch, tmp_path)
    write_results(lifecycle, _result(), repo_root=tmp_path)
    write_restart_results(lifecycle, _restart_result(), repo_root=tmp_path)
    (directory / lifecycle.restart_raw_file).write_text(
        json.dumps({"observationId": "lukewarm"}) + "\n", encoding="utf-8"
    )

    assert main(["results"]) == 3
    captured = capsys.readouterr()
    assert "undeclared observation" in captured.err
    assert "not run" not in captured.out


@pytest.mark.parametrize("command", ("measure", "restart"))
def test_the_measuring_commands_refuse_without_their_confirmation(
    command: str,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The guard that stops a default-lane invocation operating a real runtime.

    Parametrised over both comparisons rather than written once. The second
    command was added after the first, and a guard the new command inherited by
    accident is one an edit can remove without any test noticing.
    """
    assert main([command]) == 3
    assert "confirm-real-runtime" in capsys.readouterr().err


#: Record mutations that reach a different refusal in `load_lifecycle`. Each is
#: a real message this tool can print, rather than one a test wrote for itself.
LEAK_CASES: tuple[tuple[str, tuple[str, ...], object], ...] = (
    ("schema", ("schemaVersion",), "inferops.io/v2"),
    ("identity", ("lifecycleId",), "something-else"),
    ("document", ("documentRef",), "docs/serving/nope.md"),
    ("probe port", ("probes", "liveness", "port"), 9090),
    ("ready status", ("probes", "readiness", "readyStatus"), 204),
    ("budget", ("startup", "budgetMs"), 60000),
    ("cache root", ("cache", "rootPath"), ".cache/elsewhere"),
    ("evidence class", ("measurement", "evidenceClass"), "cloud-real-gpu"),
    ("results directory", ("measurement", "directory"), ".cache/inferops/models"),
)


@pytest.mark.parametrize(
    ("label", "path", "value"), LEAK_CASES, ids=[case[0] for case in LEAK_CASES]
)
def test_a_real_refusal_names_no_local_path(
    label: str,
    path: tuple[str, ...],
    value: object,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Every refusal below is one `load_lifecycle` actually raises.

    An earlier version of this test injected a message it had written itself and
    then asserted that its own message carried no path — which would have passed
    with every real refusal leaking one. These drive nine distinct refusals
    through the command and assert that none of them names the temporary
    directory the broken record was read from, or any absolute path at all.
    """
    del label
    record = _write(tmp_path, _mutated(path, value))
    monkeypatch.setattr("tools.model_lifecycle.__main__.LIFECYCLE_PATH", record)

    assert main(["check"]) == 3

    error = capsys.readouterr().err
    assert "REFUSED model lifecycle" in error
    assert str(tmp_path) not in error
    for part in tmp_path.parts:
        if part not in ("\\", "/") and len(part) > 3:
            assert part not in error, part
    assert "C:" not in error and "/home/" not in error


def test_an_unreadable_record_is_refused_without_naming_where_it_was(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    missing = tmp_path / "absent" / "model-lifecycle.v1.json"
    monkeypatch.setattr("tools.model_lifecycle.__main__.LIFECYCLE_PATH", missing)

    assert main(["check"]) == 3
    error = capsys.readouterr().err
    assert "the lifecycle record is unreadable" in error
    assert str(tmp_path) not in error
