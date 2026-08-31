"""What this process is consuming, from the one source the standard library has.

The catalog's ``resource-use`` family asks how much memory and processor time the
emitting process consumes. Half of that question is answered here and half is not,
and the half that is not is worth reading before the code.

**Processor time is portable and exact.** :func:`cpu_seconds` reads
:func:`time.process_time`, which is the CPU time this process has consumed, user
and system together, monotonic and unaffected by a clock change. It is what
``inferops_process_cpu_seconds_total`` publishes.

**Resident memory has no source this module may use.** The only per-process
memory figure the standard library exposes is ``/proc/self/statm``, and reading it
would be a module under ``src/inferops`` reading a path -- which is the property
``tests/architecture/test_domain_dependency_boundary.py`` enforces, so that the
distribution stays usable from a wheel with no file system around it. Every other
answer needs a process-inspection library, and the distribution declares no
runtime dependency. So ``inferops_process_resident_memory_bytes`` stays in the
catalog, stays assigned to this emitter, and is recorded there as **not emitted**
with that reason. It is not published as a family with no samples, and it is
certainly not published as a zero: a zero would be a measurement claiming this
process holds no memory, which is false everywhere.

The catalog's ``no-container-resource-source`` limitation is untouched by any of
this. What a process sees of itself is not what a container or a node is charged;
those are a different measurement from a source that does not exist here.
"""

from __future__ import annotations

import time


def cpu_seconds() -> float:
    """Processor time this process has consumed, user and system together."""
    return time.process_time()
