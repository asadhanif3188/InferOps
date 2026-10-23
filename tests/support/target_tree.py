"""A copy of the delivery inputs in which the desired state holds the two-replica target.

The desired-state release of ``local-docker-desktop/support-assistant`` selects one
side of the controlled comparison of V2-E02A and V2-E02B. Rule G1 of the V2-E02A
freeze record switches it to the single-runtime baseline before the first V2-E02A
run, and rule G3 restores the two-replica target after the last one. Each switch
is a reviewed change to ``main``.

Some suites test how a tool reads the two-replica topology: two runtime pods, two
budgets, the footprint of two runtime replicas. Those tests do not depend on the
side that the desired state selects. :func:`target_root` gives them a copy of the
delivery inputs of this tree in which the desired-state directory holds the target
release, derived again from its declared sources by
``tools.baseline_profile.target_release``. A suite passes that root to a tool that
takes one, or reads the target's generated values from it.

**What this is not.** The copy is a test fixture under a temporary directory. It is
not desired state, no Application reads it, and nothing here writes this tree. A
test that holds what the desired state of this tree selects reads this tree.
"""

from __future__ import annotations

import atexit
import functools
import shutil
import tempfile
from pathlib import Path

from tools.baseline_profile import target_release
from tools.generated_release import GENERATED_FILES, derive, regenerate

REPO_ROOT = Path(__file__).resolve().parents[2]

#: The directories and files the copy holds: every input that a delivery tool
#: reads, and the desired state itself.
COPIED: tuple[str, ...] = (
    "charts",
    "contracts",
    "deploy",
    "docs/serving",
    "gitops",
    "infra",
    "scripts",
    "src",
)

#: The desired-state directory of the target key.
DESIRED_STATE_DIRECTORY = (
    "gitops/environments/local-docker-desktop/workloads/support-assistant"
)

#: The files that the G1 switch moved and that a record pins when its scope holds
#: the desired-state tree and the desired-state tool: the two generated files and
#: the declaration. A record that also pins ``tools/baseline_profile`` lists its
#: three modules too. A record registered before the switch lists these until a
#: later revision of it classifies them.
G1_MOVED: tuple[str, ...] = (
    f"{DESIRED_STATE_DIRECTORY}/rendered-workload-release.yaml",
    f"{DESIRED_STATE_DIRECTORY}/values.generated.yaml",
    "tools/gitops_desired_state/core.py",
)

_IGNORED = shutil.ignore_patterns("__pycache__", "*.pyc", "*.egg-info", ".terraform")


@functools.cache
def target_root() -> Path:
    """A temporary copy of :data:`COPIED`, with the target release in the desired state.

    The copy is made once for a test session and removed when the session ends.
    """
    root = Path(tempfile.mkdtemp(prefix="inferops-target-"))
    atexit.register(shutil.rmtree, root, ignore_errors=True)
    for relative in COPIED:
        source = REPO_ROOT / relative
        if source.is_dir():
            shutil.copytree(source, root / relative, ignore=_IGNORED)
        else:
            (root / relative).parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, root / relative)
    regenerate(target_release(), root)
    return root


@functools.cache
def target_files() -> dict[str, bytes]:
    """The two generated files of the target release, by name, from this tree's sources."""
    files = dict(derive(target_release(), REPO_ROOT).files())
    assert set(files) == set(GENERATED_FILES)
    return files


def target_values(directory: Path) -> Path:
    """Write the target's generated values into ``directory``, and return the file."""
    path = directory / GENERATED_FILES[0]
    path.write_bytes(target_files()[GENERATED_FILES[0]])
    return path
