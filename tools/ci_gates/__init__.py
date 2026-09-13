"""The expected-failure gate: the published commands, run against the fixtures
that must be refused.

Every rule in this repository already has a test behind it. What this package
adds is one step further out: it runs the **commands** the documents publish,
from a shell, and checks the exit status rather than the return value. A gate in
a continuous-integration workflow can only read an exit status, so a rule proved
only inside a pytest process is a rule the gate cannot enforce.

It is also the positive half. A validator that refused everything would pass a
suite of negative controls perfectly, so every run checks the accepted fixtures
too and fails if one of them is refused.

It reads files in this repository and runs modules from it. No network, no
cluster, no model, no container engine. See docs/testing/ci-gate-matrix.md.
"""
