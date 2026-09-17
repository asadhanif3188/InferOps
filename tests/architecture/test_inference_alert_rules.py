"""The alert definitions as an owned artifact, and as a file a collector will load.

Two things, and they are the two the alert record cannot check about itself.

**Ownership.** ADR 0004 `D7` was amended to take the alert *definition* out of
`telemetry-backend` and make it a repository artifact, exactly as the dashboard
definition was. That amendment is only real if the inventory carries the row, the row
says what `implemented` does and does not mean, and `telemetry-backend` still carries
the receiver, the routing tree and the rotation. All three are compared here against
the committed inventory rather than read in a document.

**Loadability.** That the rule files this repository generates are files the pinned
collector will actually accept, checked by running that collector's own `promtool
check rules` over both of them. This is not an evaluation and it is not a firing
alert: it establishes that the files load, that every expression parses in the engine
that would evaluate them, and that the durations are ones it accepts. The distance
between that and an alert somebody was told about is a cluster, a receiver, a routing
tree and a person -- none of which this module has, and none of which exists.

The check skips, loudly, where the collector image is not available locally. A suite
that quietly stopped verifying the one thing it added would be worse than one that
never claimed to.
"""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest
import yaml

from tools.inference_alerts import RENDER_PATHS

pytestmark = pytest.mark.architecture

REPO_ROOT = Path(__file__).resolve().parents[2]
CHART_DIR = REPO_ROOT / "charts" / "inferops-llm"
VALUES = yaml.safe_load((CHART_DIR / "values.yaml").read_text(encoding="utf-8"))
INVENTORY = json.loads(
    (
        REPO_ROOT / "docs" / "architecture" / "resource-ownership.v1alpha1.json"
    ).read_text(encoding="utf-8")
)
DECISION = (
    REPO_ROOT
    / "docs"
    / "architecture"
    / "decisions"
    / "ADR-0004-component-and-ownership-boundaries.md"
).read_text(encoding="utf-8")

COLLECTOR_VALUES = VALUES["telemetry"]["collection"]["collector"]
IMAGE = (
    f"{COLLECTOR_VALUES['image']['repository']}@{COLLECTOR_VALUES['image']['digest']}"
)

RESOURCE_ID = "inference-alert-definitions"


def resource(resource_id: str) -> dict:
    found: dict = next(
        entry for entry in INVENTORY["resources"] if entry["resourceId"] == resource_id
    )
    return found


# --------------------------------------------------------------------------
# Ownership
# --------------------------------------------------------------------------


def test_the_alert_definitions_are_an_owned_repository_artifact() -> None:
    row = resource(RESOURCE_ID)
    assert row["owner"] == "repository"
    assert row["lifecycle"] == "repository"
    assert row["kind"] == "repository artifact"
    assert row["createdBy"] == "a merged pull request"
    assert row["destroyedBy"] == "a merged pull request"
    assert "helm uninstall" in row["survives"]
    assert "cluster teardown" in row["survives"]


def test_the_row_says_what_implemented_does_not_mean() -> None:
    """`implemented` here means a checked definition and nothing more.

    The dashboard row had to say the same thing for the same reason: a status
    column is read as "this works", and what works is a file.
    """
    row = resource(RESOURCE_ID)
    assert row["v1Status"] == "implemented"
    handoff = row["handoff"].lower()
    assert "receiver" in handoff
    assert "nothing routes" in handoff or "no receiver" in handoff
    assert "telemetry-backend" in handoff


def test_routing_stays_with_the_deferred_backend_row() -> None:
    backend = resource("telemetry-backend")
    assert backend["v1Status"] == "deferred"
    assert backend["owner"] == "undecided"
    handoff = backend["handoff"].lower()
    assert "receiver" in handoff
    assert "routing tree" in handoff
    assert RESOURCE_ID in handoff


def test_the_decision_records_the_amendment_that_created_the_row() -> None:
    assert "the alert definition is a repository artifact" in DECISION.lower()
    assert RESOURCE_ID in DECISION


# --------------------------------------------------------------------------
# Loadability, against the engine that would evaluate these
# --------------------------------------------------------------------------

DOCKER = shutil.which("docker")


def _image_present() -> bool:
    if DOCKER is None:
        return False
    result = subprocess.run(
        [DOCKER, "image", "inspect", IMAGE],
        capture_output=True,
        text=True,
        check=False,
        timeout=120,
    )
    return result.returncode == 0


needs_collector_image = pytest.mark.skipif(
    not _image_present(),
    reason=(
        "the pinned collector image is not present locally, so the alert rules are "
        "not checked against the engine that would load them. Pull it to run this: "
        f"docker pull {IMAGE}"
    ),
)


@needs_collector_image
@pytest.mark.parametrize("profile", sorted(RENDER_PATHS))
def test_the_pinned_collector_loads_the_rule_file_this_repository_renders(
    profile: str, tmp_path: Path
) -> None:
    """`promtool check rules`, from the image the chart pins, on the committed file.

    It establishes that the file is a rule file the engine accepts, that every
    expression parses there and not only in this repository's own subset parser,
    and that every `for` is a duration it reads. It establishes nothing about
    whether any of them would ever be true.
    """
    assert DOCKER is not None
    rules_dir = tmp_path / "rules"
    rules_dir.mkdir()
    name = RENDER_PATHS[profile].name
    (rules_dir / name).write_text(
        RENDER_PATHS[profile].read_text(encoding="utf-8"),
        encoding="utf-8",
        newline="\n",
    )
    result = subprocess.run(
        [
            DOCKER,
            "run",
            "--rm",
            "-v",
            f"{rules_dir}:/etc/inferops/alerts:ro",
            "--entrypoint",
            "/bin/promtool",
            IMAGE,
            "check",
            "rules",
            f"/etc/inferops/alerts/{name}",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=300,
        env={**os.environ, "MSYS_NO_PATHCONV": "1"},
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "SUCCESS" in result.stdout
    expected = len(
        yaml.safe_load(RENDER_PATHS[profile].read_text(encoding="utf-8"))["groups"][0][
            "rules"
        ]
    )
    assert f"{expected} rules found" in result.stdout
