"""Open a log of operator events, record one event, close the log, or check stored logs.

    python -m tools.experiment_events open FILE --experiment ID --run ID
    python -m tools.experiment_events record FILE --kind KIND --actor ACTOR
        [--code CODE] [--subject KIND/NAME] [--commit SHA]
        [--occurred-at INSTANT --clock CLOCK]
    python -m tools.experiment_events close FILE
    python -m tools.experiment_events check FILE [FILE ...]

``open`` writes the header of a new log and refuses a file that exists.
``record`` appends one event and takes the instant of the record itself.
``close`` appends the end line. ``check`` holds stored logs to their form, and
it refuses a log that is open.

**Exit status 0 says that the command did what it was asked for.** It does not
say that a fault took effect, that a detection was correct, or that a reversal
reached a cluster. Exit status 3 says that a file is not a log, that a log
cannot be written to, or that an event was refused. Nothing is written for an
event that is refused. Exit status 2 says that the arguments are not usable.

**The command reads and writes one file.** It contacts no cluster, no Git
host, and no caller. See docs/environment/experiment-operator-events.md.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from .core import (
    ACTORS,
    CLOCKS,
    KINDS,
    REFUSED_EXIT,
    EventRefused,
    LogRefused,
    close_log,
    log_text,
    open_log,
    read_log,
    record,
)


def _emit(text: str) -> None:
    """Write LF bytes on every host."""
    sys.stdout.flush()
    sys.stdout.buffer.write(text.encode("utf-8"))
    sys.stdout.buffer.flush()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python -m tools.experiment_events",
        description="Record the operator events of one experiment run in one log.",
    )
    commands = parser.add_subparsers(dest="command", required=True)
    opener = commands.add_parser("open", help="write the header of a new log")
    opener.add_argument("file", type=Path, help="the log to create")
    opener.add_argument("--experiment", required=True, help="the experiment identifier")
    opener.add_argument("--run", required=True, help="the run identifier")
    recorder = commands.add_parser("record", help="append one event to an open log")
    recorder.add_argument("file", type=Path, help="an open log")
    recorder.add_argument("--kind", required=True, choices=tuple(KINDS))
    recorder.add_argument("--actor", required=True, choices=ACTORS)
    recorder.add_argument("--code", help="the registered code of the event")
    recorder.add_argument("--subject", help="a resource kind, '/', and a name")
    recorder.add_argument("--commit", help="the commit of the reversal")
    recorder.add_argument("--occurred-at", help="an instant on another clock")
    recorder.add_argument("--clock", choices=tuple(CLOCKS))
    closer = commands.add_parser("close", help="append the end line to an open log")
    closer.add_argument("file", type=Path, help="an open log")
    check = commands.add_parser("check", help="hold stored logs to their form")
    check.add_argument("files", nargs="+", type=Path, help="stored logs")
    arguments = parser.parse_args(argv)

    if arguments.command == "check":
        refused_any = False
        for path in arguments.files:
            try:
                stored = read_log(path.read_bytes().decode("utf-8"))
            except (OSError, UnicodeDecodeError):
                refused_any = True
                print(
                    f"REFUSED  {path.name}: events-log-unreadable: the file is not "
                    "readable UTF-8 text",
                    file=sys.stderr,
                )
                continue
            except LogRefused as refused:
                refused_any = True
                print(f"REFUSED  {path.name}: {refused}", file=sys.stderr)
                continue
            print(f"READ     {stored.summary()}")
        return REFUSED_EXIT if refused_any else 0

    try:
        if arguments.command == "open":
            line = open_log(arguments.file, arguments.experiment, arguments.run)
        elif arguments.command == "record":
            line = record(
                arguments.file,
                arguments.kind,
                arguments.actor,
                code=arguments.code,
                subject=arguments.subject,
                commit=arguments.commit,
                occurred_at=arguments.occurred_at,
                clock=arguments.clock,
            )
        else:
            line = close_log(arguments.file)
    except EventRefused as refused:
        print(f"REFUSED  {refused}", file=sys.stderr)
        return REFUSED_EXIT
    if arguments.command == "open":
        print(f"OPENED   {arguments.file.name} at {line['openedAt']}")
    else:
        _emit(log_text([line]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
