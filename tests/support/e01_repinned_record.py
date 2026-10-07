"""A copy of an E01 freeze record with its pins moved to a temporary tree's content.

Some suites run the E01 runner, or list moved inputs, in a temporary repository
built from the files in this tree. Those checks start from a tree that agrees with
its freeze record. The committed records pin the content of the files as they were
when each record was registered, and files in this tree have changed since then:
the chart and the renderer changed after the experiment's runs. A temporary copy of
today's files therefore differs from the committed pins, and the runner refuses it.

:func:`repin_record` makes the temporary copy agree with itself. It rewrites the
copy of one record, under the temporary root, so that each pin is the content
digest of the file under that root. It classifies each pin that moved against the
superseded record, as the freeze rules require, and registers the rewritten copy in
the temporary registry. It writes under the root it is given and nowhere else.

**What this is not.** The rewritten record is a test fixture. It is not a freeze
revision, and it is never committed. Its added ``inputChanges`` rows are not a
classification of any change: each is written ``material: false`` with a reason
that says a test wrote it. The committed records are not read as changed by any of this.
``python -m tools.experiment_freeze --changes <record>`` still lists every file in
this tree that differs from a committed pin, and a real run is still refused until
a merged freeze revision classifies each one. So these suites test how the runner
and the listing behave on a tree that agrees with its record, and on one planted
difference at a time. They do not show that today's files are the files a committed
record pinned.

The runner is the exception. :mod:`tests.support.e01_pinned_runner` still derives
its pinned content and requires the pinned digest, so the one edit made to the
runner after its pin stays the only difference this tree may hold there.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Final

from tools.experiment_freeze import REGISTRY_PATH, content_digest

#: The reason written for a pin this module moved. It names what wrote it.
_REASON: Final = (
    "Written by a test in a temporary repository, so that the copy of the record "
    "agrees with the copy of the tree. It is not a classification of the change."
)


def _load(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _write(path: Path, document: Any) -> None:
    path.write_text(
        json.dumps(document, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def repin_record(root: Path, record: str) -> list[str]:
    """Move the pins of ``record`` under ``root`` to the content under ``root``.

    Returns the paths whose pin moved, sorted. A pinned file that is absent under
    ``root`` keeps its pin, so a test that removes a file still sees it reported.
    """
    document = _load(root / record)
    moved: list[str] = []
    for pin in document["pinnedInputs"]:
        target = root / pin["path"]
        if not target.is_file():
            continue
        digest = content_digest(target.read_bytes())
        if digest != pin["sha256"]:
            pin["sha256"] = digest
            moved.append(pin["path"])
    if not moved:
        return []

    supersedes = document["metadata"].get("supersedes")
    if supersedes is not None:
        previous = {
            pin["path"]: pin["sha256"]
            for pin in _load(root / supersedes["path"])["pinnedInputs"]
        }
        classified = {change["path"] for change in document.get("inputChanges", [])}
        for path in moved:
            if path not in classified and previous.get(path) != next(
                pin["sha256"] for pin in document["pinnedInputs"] if pin["path"] == path
            ):
                document.setdefault("inputChanges", []).append(
                    {
                        "path": path,
                        "change": "changed" if path in previous else "added",
                        "material": False,
                        "reason": _REASON,
                    }
                )
    _write(root / record, document)

    registry = _load(root / REGISTRY_PATH)
    for row in registry["records"]:
        if row["path"] == record:
            row["contentSha256"] = content_digest((root / record).read_bytes())
    _write(root / REGISTRY_PATH, registry)
    return sorted(moved)
