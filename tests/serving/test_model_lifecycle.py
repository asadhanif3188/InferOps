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
from collections.abc import Mapping, Sequence
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
    StartObservation,
    clean_results,
    compare_starts,
    load_lifecycle,
    observation_document,
    observe_cache,
    observe_start,
    read_results,
    result_directory,
    summarize,
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
    """Answer every command from a script and retain the exact argument vectors."""

    def __init__(self, results: Sequence[CommandResult]) -> None:
        self.results = list(results)
        self.calls: list[tuple[str, ...]] = []

    def run(self, arguments: Sequence[str]) -> CommandResult:
        self.calls.append(tuple(arguments))
        if not self.results:
            raise AssertionError(f"unexpected command: {arguments}")
        return self.results.pop(0)


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
    _refuses(tmp_path, document, "not graceful")


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
    """The refusal that stops a cleanup path deleting 1.71 GiB of model bytes."""
    _refuses(
        tmp_path,
        _mutated(("measurement", "directory"), str(MODEL_CACHE_DIRECTORY.as_posix())),
        "not the managed one",
    )


def test_a_comparison_is_exactly_one_cold_and_one_warm_start(lifecycle) -> None:
    assert lifecycle.observation_ids == ("cold", "warm")


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


#: A container that does not exist: the ownership inspect fails and the listing
#: that follows it finds nothing. Two results, in that order.
ABSENT = (CommandResult(1, "", "no such container"), CommandResult(0, "\n"))


def _observation_script(samples: int) -> list[CommandResult]:
    """The exact command sequence one successful observation produces, in order."""
    package = load_runtime_package()
    return [
        CommandResult(0, "29.0.0\n"),  # start: docker version
        CommandResult(0, f"{package.image_reference}\n"),  # start: image inspect
        *ABSENT,  # start: nothing owns the container name yet
        CommandResult(0, "container-id\n"),  # start: docker run
        CommandResult(0, "true\n"),  # start: the process did not exit
        *[CommandResult(0, "true\n") for _ in range(samples)],  # the sample loop
        CommandResult(0, f"{package.package_id}\n"),  # stop: the name is ours
        CommandResult(0, "stopped\n"),  # stop: docker stop
        CommandResult(0, "removed\n"),  # stop: docker rm
    ]


def _ready_runner(samples: int = 3) -> ScriptedRunner:
    return ScriptedRunner(_observation_script(samples))


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
        statuses=(0, 503, 200),
        liveness=(False, True, True),
        monkeypatch=monkeypatch,
    )

    assert observation.liveness_held_while_loading is True
    assert observation.liveness_never_dropped_after_it_passed is True
    assert observation.readiness_false_until_ready is True
    assert observation.cache_state is CacheState.HIT
    assert [sample.readiness_status for sample in observation.samples] == [0, 503, 200]


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
    runner = _ready_runner(samples=1)
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
            ScriptedRunner([]),
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
            ScriptedRunner([]),
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
            ScriptedRunner([]),
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
    # A 1,000 ms budget at a 250 ms poll is five samples, and the fifth is the
    # one that finds the deadline reached.
    runner = ScriptedRunner(_observation_script(samples=5))
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
    runner = ScriptedRunner(
        [
            *ABSENT,  # compare: nothing owns the name before either start
            CommandResult(0, "29.0.0\n"),  # environment capture
            *_observation_script(samples=2),  # the cold start
            *_observation_script(samples=2),  # the warm start
        ]
    )
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


def test_a_comparison_refuses_to_start_beside_an_existing_owned_container(
    lifecycle, tmp_path: Path
) -> None:
    package = load_runtime_package()
    runner = ScriptedRunner([CommandResult(0, f"{package.package_id}\n")])

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
            ScriptedRunner([]),
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
    lifecycle = load_lifecycle()
    diverted = replace(lifecycle, result_directory=MODEL_CACHE_DIRECTORY)

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


def test_the_measure_command_refuses_without_its_confirmation(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The guard that stops a default-lane invocation operating a real runtime."""
    assert main(["measure"]) == 3
    assert "confirm-real-runtime" in capsys.readouterr().err


def test_the_command_reports_a_refusal_without_leaking_a_local_path(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    def refuse(*_args: object, **_kwargs: object) -> Mapping[str, Any]:
        raise ModelLifecycleError("the lifecycle record is unreadable")

    monkeypatch.setattr("tools.model_lifecycle.__main__.load_lifecycle", refuse)

    assert main(["check"]) == 3
    error = capsys.readouterr().err
    assert "REFUSED model lifecycle" in error
    assert "C:" not in error and "/home/" not in error
