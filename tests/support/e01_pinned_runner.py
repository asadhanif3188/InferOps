"""The E01 runner as the freeze records pinned it, rebuilt from the runner in the tree.

Revisions 2 and 3 of the E01 freeze record pin ``tools/experiment_e01/core.py`` by
content. After the E01-D run was committed, one function of that file changed: the
listing of committed runs leaves out a run of part E01-D, which the runner cannot
judge. The file therefore differs from its pin, and a temporary repository that
copies it is refused by the run's own precondition.

The suites that build such a repository need the pinned content. A shallow clone
does not hold the earlier revision of the file, so this module derives it: it
takes the runner in the tree and puts back the two passages that the change
replaced. It then requires that the result has the pinned digest. That requirement
is also a statement about the change: the committed-run listing is the only
difference between the runner in the tree and the runner that was pinned.

When another edit moves the runner, :func:`pinned_runner_bytes` fails and names the
digests. That is intended. A later freeze revision must classify such an edit, and
this module must then follow it.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Final

from tools.experiment_freeze import content_digest

#: The pinned file that the committed-run listing changed.
RUNNER: Final = "tools/experiment_e01/core.py"

#: The record whose pin of the runner is the reference. Revision 3 pins the same
#: digest, and :func:`pinned_runner_bytes` checks both.
_RECORDS: Final = (
    "docs/proof/experiments/v2-e01/freeze-r2.v1alpha1.json",
    "docs/proof/experiments/v2-e01/freeze-r3.v1alpha1.json",
)

#: Each passage the change wrote, with the passage it replaced.
_REPLACED: Final = (
    (
        """_RUN_ID: Final = re.compile(r"^(?P<date>[0-9]{8})-e01-abc-(?P<sequence>[1-9][0-9]*)$")
#: The identifier of a run of part E01-D. This runner does not execute that part and
#: holds no analysis of it, so :func:`committed_runs` leaves such a directory out.
_REAL_DEPLOYMENT_RUN_ID: Final = re.compile(r"^[0-9]{8}-e01-d-[1-9][0-9]*$")
""",
        """_RUN_ID: Final = re.compile(r"^(?P<date>[0-9]{8})-e01-abc-(?P<sequence>[1-9][0-9]*)$")
""",
    ),
    (
        '''def committed_runs(root: Path = REPO_ROOT) -> list[Path]:
    """Every run directory of the static parts under :data:`RUNS_DIR`, in name order.

    A directory named as a run of part E01-D is left out. No code here judges such a
    run: its verdicts are applied by hand from the freeze record's verification rules.
    Every other directory is returned, so a misnamed static run is still checked.
    """
    base = root / RUNS_DIR
    if not base.is_dir():
        return []
    return sorted(
        path
        for path in base.iterdir()
        if path.is_dir() and not _REAL_DEPLOYMENT_RUN_ID.match(path.name)
    )
''',
        '''def committed_runs(root: Path = REPO_ROOT) -> list[Path]:
    """Every run directory under :data:`RUNS_DIR`, in name order."""
    base = root / RUNS_DIR
    if not base.is_dir():
        return []
    return sorted(path for path in base.iterdir() if path.is_dir())
''',
    ),
)


def _pin(repo_root: Path, record: str) -> str:
    document = json.loads((repo_root / record).read_text(encoding="utf-8"))
    return next(
        str(item["sha256"])
        for item in document["pinnedInputs"]
        if item["path"] == RUNNER
    )


def pinned_runner_bytes(repo_root: Path) -> bytes:
    """The runner's content as revisions 2 and 3 pinned it, with LF line endings."""
    text = (repo_root / RUNNER).read_bytes().decode("utf-8").replace("\r\n", "\n")
    for written, replaced in _REPLACED:
        if text.count(written) != 1:
            raise AssertionError(
                f"{RUNNER} does not hold, exactly once, a passage that the "
                "committed-run change wrote"
            )
        text = text.replace(written, replaced)
    data = text.encode("utf-8")
    digest = content_digest(data)
    for record in _RECORDS:
        pinned = _pin(repo_root, record)
        if digest != pinned:
            raise AssertionError(
                f"{RUNNER} without the committed-run change has the digest {digest}, "
                f"and {record} pins {pinned}: another edit moved the runner"
            )
    return data


def copy_pinned_input(repo_root: Path, relative: str, target: Path) -> None:
    """Copy one pinned input to ``target``, with the runner in its pinned content."""
    target.parent.mkdir(parents=True, exist_ok=True)
    if relative == RUNNER:
        target.write_bytes(pinned_runner_bytes(repo_root))
    else:
        shutil.copyfile(repo_root / relative, target)
