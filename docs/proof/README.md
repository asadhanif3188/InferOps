# Evidence records

Status: entry point established. The records here are the only thing in this
repository that may be cited as evidence for a public claim.

A record here is produced by a reviewed change, never by a job. That rule comes from
[the telemetry and evidence flow](../architecture/system-architecture.md): a record a
pipeline can regenerate is a record that can be regenerated to say something else.

What a record may be used to claim is decided elsewhere — by the evidence class of
the layer that produced it, and the certification ceiling that class carries, in
[the certification document](../testing/certification.md). A record does not get to
nominate its own strength.

## Records

| Area | Records |
|---|---|
| Governance | [`v1-s0-001-pr1.md`](governance/v1-s0-001-pr1.md) |
| Environment | [host inventory](environment/v1-s0-002-pr1-host-inventory.md), [cluster smoke](environment/v1-s0-002-pr2-cluster-smoke.md), and the two change-validation records beside them |
| Serving | [runtime feasibility](serving/v1-s0-003-pr2-runtime-feasibility.md), [`v1-s0-012-pr1-validation.md`](serving/v1-s0-012-pr1-validation.md), and the change-validation records beside them |
| Contracts | [`v1-s0-004-pr1-validation.md`](contracts/v1-s0-004-pr1-validation.md), [`v1-s0-004-pr2-validation.md`](contracts/v1-s0-004-pr2-validation.md) |
| Domain | [`v1-s1-001-pr1-validation.md`](domain/v1-s1-001-pr1-validation.md) |
| Architecture | [`v1-s0-005-pr1-validation.md`](architecture/v1-s0-005-pr1-validation.md) |
| Testing | [`v1-s0-006-pr1-validation.md`](testing/v1-s0-006-pr1-validation.md), [`v1-s1-007-pr1-validation.md`](testing/v1-s1-007-pr1-validation.md) |
| Telemetry | [`v1-s0-007-pr1-validation.md`](telemetry/v1-s0-007-pr1-validation.md), [`v1-s1-008-pr1-validation.md`](telemetry/v1-s1-008-pr1-validation.md) |
| Cost | [`v1-s0-008-pr1-validation.md`](cost/v1-s0-008-pr1-validation.md) |
| Security | [`v1-s0-009-pr1-validation.md`](security/v1-s0-009-pr1-validation.md) |
| Toolchain | [`v1-s0-011-pr1-validation.md`](toolchain/v1-s0-011-pr1-validation.md) |
| Scaffolding | [`v1-s1-006-pr1-validation.md`](scaffolding/v1-s1-006-pr1-validation.md), [`v1-s1-006-pr2-validation.md`](scaffolding/v1-s1-006-pr2-validation.md) |
| Developer quick start | [`v1-s1-009-pr1-validation.md`](quickstart/v1-s1-009-pr1-validation.md) |

## Templates

Four templates, in [`templates/`](templates/). Copy one, fill it in, and commit the
copy; never edit a template to hold a result.

| Template | What it is for |
|---|---|
| `experiment` | [Registering what will be measured](templates/TEMPLATE-experiment.md), how, and what result would count as a failure — **before** the run |
| `environment` | [Recording the host](templates/TEMPLATE-environment.md), the immutable component versions, and the digests a result depends on |
| `raw-result` | [Describing a machine-readable result set](templates/TEMPLATE-raw-result.md), its schema, its hash, and what was removed before it was committed |
| `claim-evidence` | [Binding one public claim](templates/TEMPLATE-claim-evidence.md) to its evidence, the level that evidence can support, and the limitations that travel with it |

A fifth, domain-specific one lives beside the records it produces:
[the runtime and model feasibility record](serving/TEMPLATE-runtime-feasibility.md),
which is the recording format for
[the feasibility workflow](../serving/feasibility-workflow.md).

The experiment template is the one that is easy to skip and the one that changes the
result. Registering the method and the failure condition before the run is what
separates a measurement from a search for a number that supports what was already
believed.

## The sections every record carries

| Section | Why it is required |
|---|---|
| `classification` | The weakest label the record actually supports, and the ceiling that label carries. A record without it is read at whatever strength the reader wants |
| `provenance` | The immutable versions: repository revision, image digests, model revision, tool versions. A result whose inputs are named by a moving tag is not reproducible |
| `environment` | The host, operating system, resources, and cluster. Two of this project's accepted records are true of exactly one machine, and say so here |
| `method` | The exact commands, in the order they were run, including the ones that failed. A method that cannot be re-executed describes a result rather than evidencing one |
| `results` | What was observed, with measured values labelled measured and derived values labelled derived |
| `limitations` | What the record does **not** establish. This is the section that stops a result being cited for something adjacent to what it measured |
| `authorisation` | Who authorised a run that costs money, downloads a large artifact, or touches something outside the contributor's own machine, and when. "Not required" is an answer; silence is not |

These are checked. [`tests/telemetry/`](../../tests/telemetry/) reads each template
and fails if a required section is missing or duplicated, so a template cannot lose
a section quietly.

## What a template is not

A template is a format, and a format is not evidence. None of the four has produced
a record yet, the catalog records that count as zero, and a test refuses any attempt
to cite a template path as the evidence behind a claim.
