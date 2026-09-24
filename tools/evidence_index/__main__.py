"""Check, print, or regenerate the V1 evidence index.

    python -m tools.evidence_index
    python -m tools.evidence_index --print
    python -m tools.evidence_index --check
    python -m tools.evidence_index --write

The first prints the index's summary counts. ``--print`` prints the whole index the
register and the ledger produce today and writes nothing. ``--check`` compares that
with the committed ``docs/proof/v1-evidence-index.v1alpha1.json`` and exits 1 on
the first difference, so it is usable as a gate. ``--write`` is the only mode that
touches a file, and it writes that one file.

**Every mode reads files.** None contacts a cluster, a runtime, a model, or the
network. See docs/proof/v1-evidence-index.md.
"""

from __future__ import annotations

import argparse
import json
import sys

from .core import INDEX_PATH, build_index, render_index


def _check(text: str) -> int:
    if not INDEX_PATH.exists():
        print(f"MISSING  {INDEX_PATH}")
        print("         regenerate with: python -m tools.evidence_index --write")
        return 1
    # Text mode on purpose: a checkout that gave the file CRLF is not a
    # difference in what the index says.
    committed = INDEX_PATH.read_text(encoding="utf-8")
    if committed == text:
        print(f"OK       {INDEX_PATH.name} is what the register and ledger produce")
        return 0
    for number, (left, right) in enumerate(
        zip(committed.splitlines(), text.splitlines(), strict=False), start=1
    ):
        if left != right:
            print(f"DRIFTED  {INDEX_PATH.name} line {number}")
            print(f"         committed: {left.strip()}")
            print(f"         produced:  {right.strip()}")
            break
    else:
        print(
            f"DRIFTED  {INDEX_PATH.name} has {len(committed.splitlines())} lines; "
            f"the register and ledger produce {len(text.splitlines())}"
        )
    print("         regenerate with: python -m tools.evidence_index --write")
    return 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.evidence_index",
        description=(
            "Print, check, or regenerate the V1 evidence index from the claim and "
            "evidence register and the normalization ledger."
        ),
    )
    group = parser.add_mutually_exclusive_group()
    group.add_argument(
        "--print", action="store_true", help="print the index without writing it"
    )
    group.add_argument(
        "--check", action="store_true", help="compare the committed index"
    )
    group.add_argument("--write", action="store_true", help="regenerate the index")
    arguments = parser.parse_args(argv)

    text = render_index(build_index())

    if arguments.print:
        # Bytes, so the output is comparable with the committed file on every
        # platform rather than re-encoded and re-terminated by the console.
        sys.stdout.flush()
        sys.stdout.buffer.write(text.encode("utf-8"))
        sys.stdout.buffer.flush()
        return 0
    if arguments.check:
        return _check(text)
    if arguments.write:
        with INDEX_PATH.open("w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
        print(f"WROTE    {INDEX_PATH}")
        return 0

    print(json.dumps(json.loads(text)["summary"], indent=2))
    return 0


if __name__ == "__main__":  # pragma: no cover - exercised as a subprocess
    raise SystemExit(main())
