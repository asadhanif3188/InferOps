"""Every relative link in every committed Markdown document resolves.

This is the check behind ``published-documents-link-only-to-things-that-exist``,
which the claim and test matrix certifies at ``C0``. Until now the check existed
only as a shell snippet in ``CONTRIBUTING.md`` that a contributor had to remember
to run, and the certified claim was false in this repository for as long as
nobody did: two links in the deferred-risk register pointed at a copy of the
network-policy experiment that never existed at that path, and two evidence
records cited an ADR filename that was never committed.

What this establishes is only that a path resolves. It says nothing about whether
the document at the other end says what the citing sentence claims it says.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

pytestmark = pytest.mark.docs

REPO_ROOT = Path(__file__).resolve().parents[2]

# A fenced block, so a command sample containing ``](...)`` is not read as a link.
FENCE = re.compile(r"^[ \t]*(```|~~~)")

# An inline code span, so a format illustration such as `[the template](...)` is
# not read as a link either. Documents use these to show what a record must carry.
INLINE_CODE = re.compile(r"`[^`]*`")

# ``[text](target)``. A target is read up to its first closing parenthesis, the
# same limitation CONTRIBUTING records; repository paths carry no parentheses.
LINK = re.compile(r"\]\(([^)]+)\)")

SKIPPED_SCHEMES = ("http://", "https://", "mailto:", "#")


def committed_markdown() -> list[Path]:
    listed = subprocess.run(
        ["git", "ls-files", "-z", "*.md"],
        cwd=REPO_ROOT,
        capture_output=True,
        check=True,
        text=True,
    ).stdout
    return [REPO_ROOT / name for name in listed.split("\0") if name]


def links_in(document: Path) -> list[str]:
    """Every relative link target in ``document``, outside code."""
    targets: list[str] = []
    fenced = False
    for line in document.read_text(encoding="utf-8").splitlines():
        if FENCE.match(line):
            fenced = not fenced
            continue
        if fenced:
            continue
        for target in LINK.findall(INLINE_CODE.sub("", line)):
            target = target.strip()
            if target.startswith(SKIPPED_SCHEMES):
                continue
            target = target.split("#", 1)[0]
            if target:
                targets.append(target)
    return targets


MARKDOWN = committed_markdown()


def test_the_repository_publishes_markdown_to_check() -> None:
    assert len(MARKDOWN) > 50, len(MARKDOWN)


@pytest.mark.parametrize(
    "document", MARKDOWN, ids=lambda p: str(p.relative_to(REPO_ROOT)).replace("\\", "/")
)
def test_every_relative_link_resolves_from_its_own_directory(document: Path) -> None:
    broken = [
        target
        for target in links_in(document)
        if not (document.parent / target).exists()
    ]
    assert not broken, {
        "document": str(document.relative_to(REPO_ROOT)).replace("\\", "/"),
        "targets that do not resolve": broken,
    }
