"""Print one stream of a collection, check stored streams, or print their changes.

    python -m tools.experiment_timeline stream DIRECTORY NAME
    python -m tools.experiment_timeline check FILE [FILE ...]
    python -m tools.experiment_timeline changes FILE

``stream`` reads the directory that a collector wrote and prints one of the four
streams: ``endpoints``, ``pods``, ``deployments``, or ``argo``. ``check`` reads
stored streams and holds each one to its form. ``changes`` prints each tracked
value that differs between two consecutive readings of one stored stream.

**Exit status 0 says that the command printed what it was asked for.** It does
not say that a read answered, that an endpoint was Ready, or that a state was
healthy: a stream whose every read is unanswered is a stream. Exit status 3 says
that a directory is not a collection or that a file is not a stream. Exit status
2 says that the arguments are not usable.

**The command reads files and writes to its standard output.** It contacts no
cluster. See docs/environment/experiment-timelines.md.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core import (
    REFUSED_EXIT,
    STREAMS,
    CollectionRefused,
    Stream,
    StreamRefused,
    build_streams,
    changes,
    changes_text,
    read_stream,
    stream_text,
)


def _emit(text: str) -> None:
    """Write LF bytes on every host, so one stream has one digest."""
    sys.stdout.flush()
    sys.stdout.buffer.write(text.encode("utf-8"))
    sys.stdout.buffer.flush()


def _stored(path: Path) -> Stream:
    try:
        text = path.read_bytes().decode("utf-8")
    except (OSError, UnicodeDecodeError) as fault:
        raise StreamRefused(
            "timeline-stream-unreadable", "the file is not readable UTF-8 text"
        ) from fault
    return read_stream(text)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.experiment_timeline",
        description=(
            "Print the infrastructure timeline streams of one experiment run, "
            "from the directory that a collector wrote."
        ),
    )
    commands = parser.add_subparsers(dest="command", required=True)
    stream = commands.add_parser("stream", help="print one stream of a collection")
    stream.add_argument("directory", type=Path, help="the directory a collector wrote")
    stream.add_argument("name", choices=STREAMS, help="the stream to print")
    check = commands.add_parser("check", help="hold stored streams to their form")
    check.add_argument("files", nargs="+", type=Path, help="stored streams")
    differ = commands.add_parser("changes", help="print the changes of one stream")
    differ.add_argument("file", type=Path, help="a stored stream")
    arguments = parser.parse_args(argv)

    if arguments.command == "stream":
        try:
            streams = build_streams(arguments.directory)
        except CollectionRefused as refused:
            print(f"REFUSED  not-a-collection: {refused}", file=sys.stderr)
            return REFUSED_EXIT
        _emit(stream_text(streams[arguments.name]))
        return 0

    if arguments.command == "changes":
        try:
            stored = _stored(arguments.file)
        except StreamRefused as refused:
            print(f"REFUSED  {refused}", file=sys.stderr)
            return REFUSED_EXIT
        _emit(changes_text(changes(stored)))
        return 0

    refused_any = False
    for path in arguments.files:
        try:
            stored = _stored(path)
        except StreamRefused as refused:
            refused_any = True
            print(f"REFUSED  {path.name}: {refused}", file=sys.stderr)
            continue
        print(f"READ     {stored.summary()}")
    return REFUSED_EXIT if refused_any else 0


if __name__ == "__main__":
    raise SystemExit(main())
