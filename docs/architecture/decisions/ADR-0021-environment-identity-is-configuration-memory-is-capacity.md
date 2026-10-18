# ADR 0021: The environment identity states the configuration, and memory is a capacity fact

| Field | Value |
|---|---|
| Status | **Accepted** |
| Date proposed | 2026-10-17 |
| Date accepted | 2026-10-17 |
| Decision owner | [`repository-maintainer`](../../governance/decision-authority.md) |
| Supersedes | None |
| Amends | None. It decides the rule that [revision 1 of the Q1 freeze record](../../proof/experiments/v2-q1/freeze-r1.v1alpha1.json) applied without deciding it, and [revision 2](../../proof/experiments/v2-q1/freeze-r2.v1alpha1.json) carries it |
| Superseded by | None |

> [!IMPORTANT]
> This record decides what the environment identity of a qualification states.
>
> **The identity states the configuration.** It is the provider, the Kubernetes
> server version, each node with its kubelet version and the CPU and the pods that
> it allocates, and the CPU count of the container engine. A start of the virtual
> machine does not change any of them.
>
> **Memory is a capacity fact.** Each capacity reading states the memory of the
> node and of the container engine. The capacity gate decides, for each reading,
> whether the declared limits and the reserve fit it. The identity holds no memory
> figure, and no tolerance, rounding, or mask is applied to one.
>
> **History is kept.** `q1-1`, `q2-1`, and `q3-1` are built again under the freeze
> revisions they name, with the exact identity they were decided with. `q3-1` stays
> `REFUSED`. A source of the `q1-1` lineage is never combined with one of the
> next lineage.
>
> **Nothing ran.** No qualification or characterization ran under this record. The
> next qualification is `q1-2`, and it may be `REFUSED`.

## Decision status

| ID | Decision | Status | What supports it |
|---|---|---|---|
| D1 | The environment identity names the environment whose results one controlled comparison may compare. It states facts of the configuration: the stable environment identity, `identityRevision` 2 | **Accepted** | Tests hold its members, its digest, that each configuration fact is part of it, and that it does not depend on the order of the capacity record |
| D2 | A memory figure is a capacity fact. It is not part of the identity. The capacity gate decides it for each reading | **Accepted** | Tests hold the three observed memory readings as one stable identity, and an insufficient reading as refused by the real gate while its stable identity is unchanged |
| D3 | A characterization of the next lineage requires both: the gate accepted its own capacity reading, and the stable identity of that reading has the digest that the qualification states | **Accepted** | Tests of the Q2 and Q3 tools refuse a reading that the gate refused although its stable identity matches |
| D4 | An identity input that is absent, malformed, or unreadable states no identity, and the qualification is refused | **Accepted** | Tests give the Q1 tool each absent or malformed member and an unreadable capacity record |
| D5 | A record is built under the freeze revision that its header names. A revision does not reinterpret a record of an earlier revision. The exact and the stable identities never share a digest, and the Q4 bound tool refuses a pair of sources of two lineages | **Accepted** | `--check` of the Q1, Q2, Q3, and Q4 tools over the committed records, and tests of each lineage and of the refused pairs |
| D6 | The next path is frozen before it runs: revision 2 of the Q1 freeze record, revision 3 of the Q2 record, and revision 2 of the Q3 record, each held to the qualification `q1-2` | **Accepted**, not executed | The freeze tool holds the three records, their supersession, their pins, and the classification of every moved pin. No run of any of them exists |

## Context

[Revision 1 of the Q1 freeze record](../../proof/experiments/v2-q1/freeze-r1.v1alpha1.json)
recorded an environment identity that holds the memory of the node and of the container
engine to the byte. The Q1 page said that whether the identity should keep that figure
was not decided. The Q2 and Q3 tools compare the digest of their own capacity reading
with the one that `q1-1` states.

On 2026-10-16 the Q3 characterization [`q3-1`](../../proof/experiments/v2-q3/runs/q3-1/result.md)
was refused on that comparison. The virtual machine of the docker-desktop engine had
started again, and the engine and the node reported 10,429,972,480 bytes where `q1-1`
states 10,429,960,192. Every other value of the identity was the same: the provider, the
server version, the node, the kubelet version, 12 CPUs, 12,000 millicores, and 110 pods.
One further start of the virtual machine, read by hand, reported 10,429,956,096 bytes. So
on this host the memory figure changed at each of the two starts that were observed, and
the gate accepted the target on each reading.

A Q1 record states the Kubernetes provider and server version among the identities of
the qualification, in its member `identities.kubernetes`, beside the commit, the release,
the images, and the model. None of those is a memory figure. The memory figure is the one
that the engine reports for one start of its virtual machine, and nothing in the
repository sets it.

Every pod of the release states memory limits. The capacity gate refuses a reading
unless the sum of the declared limits and a reserve of 512 MiB fits the memory that the
node allocates, and it refuses a node under memory pressure. That rule is what keeps an
insufficient environment from being qualified, and it is applied to each reading.

## Decision criteria

1. **The identity must survive what the experiment cannot control.** A controlled
   comparison runs across several changes and days. A start of the virtual machine is
   outside its control.
2. **An insufficient environment must stay refused.** A change to the identity must not
   let a reading through that the gate refuses.
3. **The identity must be deterministic and public-safe.** It is computed from the
   stored capacity record alone, holds no address, context name, or path, and refuses
   when a part cannot be read.
4. **History must not move.** A committed record keeps its meaning, its result, and its
   digest.
5. **No figure is chosen to fit the observed ones.** No tolerance, rounding, or mask is
   chosen because it would accept 12,288 bytes.

## D1 — The identity states the configuration

The stable environment identity has these members, read from the capacity record:

| Member | Read from |
|---|---|
| `provider` | `environment.provider` |
| `kubernetesServerVersion` | `environment.kubernetesServerVersion` |
| `nodes[].name`, `nodes[].kubeletVersion` | each node, sorted by name |
| `nodes[].allocatable.cpuMillis`, `nodes[].allocatable.pods` | each node |
| `containerEngine.cpus` | `environment.containerEngine.cpus` |
| `identityRevision` | the constant `2` |

Its digest is the SHA-256 of its canonical JSON text, as for the exact identity. The
member `identityRevision` makes its text, and so its digest, different from that of any
exact identity.

The CPU figures stay in the identity. They are figures of the configuration, they did
not change at either observed start, and a startup interval or a caller gap can depend
on them.

## D2 — Memory is a capacity fact

The memory of the node and of the container engine stays in the capacity record of each
reading, which is committed with each run. The capacity gate decides for each reading
whether the declared limits and the reserve fit it. Q1-AC9 requires its result
`ACCEPTED`.

The identity does not compare the memory of two readings. A reading with more memory
than the qualification, and a reading with less that the gate still accepts, are both
of the same identity.

## D3 — A later run is held to both

The Q2 rule `environment-qualified` of revision 3 and the Q3 rule of revision 2 require,
in this order: the qualification `q1-2` is `QUALIFIED` under revision 2 of the Q1 freeze
record, the gate accepted the target on the run's own capacity reading, the stable
identity of that reading is readable, its provider is `docker-desktop`, and its digest is
the one that `q1-2` states. A reading that the gate refused refuses the run, whatever its
identity.

## D4 — An unreadable input refuses

When a member of the identity is absent, of another form, or negative, or the capacity
record cannot be read, the tool states no identity and no digest, and the rule
`context-unambiguous` of Q1 is not held. No default is substituted.

## D5 — History is kept

Each tool keeps the revisions it registered and builds a record under the revision that
its header names:

| Record | Revision | Qualification | Identity |
|---|---|---|---|
| `q1-1` | Q1 revision 1 | itself | exact |
| `q2-1` | Q2 revision 2 | `q1-1` | exact |
| `q3-1` | Q3 revision 1 | `q1-1` | exact |
| the next Q1 run | Q1 revision 2 | itself | stable |
| the next Q2 and Q3 runs | Q2 revision 3, Q3 revision 2 | `q1-2` | stable |

The committed records are built again byte for byte. `q3-1` stays `REFUSED`, and `q2-1`
stays bound to `q1-1`. The Q4 bound tool compares the provider, the environment digest,
the release identifier, and the qualification record of its two sources, so a source of
one lineage and a source of the other are refused.

Revision 1 of the Q1 freeze record can no longer govern a new qualification. Its pinned
Q1 tool has moved, so the freeze check of the driver lists a changed material file, and
`procedure-frozen` refuses.

## D6 — The next path is frozen before it runs

| Record | Supersedes | Pins | Holds a run to |
|---|---|---|---|
| [Q1 revision 2](../../proof/experiments/v2-q1/freeze-r2.v1alpha1.json) | Q1 revision 1 | 189 | the stable identity. The seventeen criteria are unchanged |
| [Q2 revision 3](../../proof/experiments/v2-q2/freeze-r3.v1alpha1.json) | Q2 revision 2 | 194 | `q1-2` and the stable identity. Three statements change |
| [Q3 revision 2](../../proof/experiments/v2-q3/freeze-r2.v1alpha1.json) | Q3 revision 1 | 199 | `q1-2` and the stable identity. Two statements change. The rule of G and the Q4 formulas are unchanged |

The record of `q1-2` does not exist when these are registered, so no freeze record pins
it. Each characterization states its content digest, and the Q4 bound tool requires its
two sources to state the same one.

## Alternatives that were rejected

| Alternative | Why it was rejected |
|---|---|
| Keep the memory figure in the identity, to the byte | The identity would name one start of the virtual machine, not the environment. Two of two observed starts changed it. Each later start would spend a qualification, and the qualification chain and every result-bearing run of one comparison would have to run within one start |
| Round the memory figure, or accept a tolerance | Any width would be chosen against the observed figures. A rounding boundary can also put two readings of one configuration on two sides |
| Hold the memory of a later reading to at least that of the qualification | The third observed start reported less than `q1-1`, so it would refuse the same configuration. The gate already decides what is enough |
| Read the configured memory of the virtual machine from the host | No collector reads it, it lives in host settings outside the repository, and a path to it would not be public-safe |
| Edit revision 1, or build `q1-1`, `q2-1`, or `q3-1` under the new identity | It would change the meaning of committed records and of the refusal of `q3-1` |

## Consequences

- **A later run is not refused for a memory figure that the gate accepts.** It is
  refused when the gate refuses its reading, or when a fact of the configuration
  differs.
- **An environment with more memory is the same identity.** No record shows that
  memory above the declared limits has no effect on a startup interval or a caller gap.
  Each record states its own reading, so a later reader can compare them.
- **A new qualification is needed.** `q2-1` cannot be a source of Q4 with a Q3
  characterization of `q1-2`. The next lineage needs its own Q1, Q2, and Q3 runs.

## Compatibility impact

The Q1 record schema stays `inferops.io/environment-qualification/v1alpha1`. A record of
revision 2 states the stable identity in its member `environment`, with
`identityRevision` 2. A record of revision 1 states the exact identity and has no such
member. The Q2, Q3, and Q4 tools are the only consumers, and each reads the revision a
record names. V1, its tag, and its records are not changed.

## Security considerations

The stable identity states fewer figures than the exact one. It holds no address, no
context name, no path, and no account identifier.

## Evidence

Evidence level: **C0 for the decision and the tools.** Tests run the tools on synthetic
directories and on the committed records. The real capacity gate ran on a modified copy
of the committed capacity collection of `q1-1`. No cluster was contacted, and no
qualification or characterization ran.
[The validation record](../../proof/environment/v2-s6-004-pr1-validation.md) lists the
commands and their results. No claim was added or changed.

## Risks, assumptions, and open questions

| ID | Item | Status | Note |
|---|---|---|---|
| R1 | Why the engine and the node report other memory figures after each start | Open | Not established. The decision does not depend on the cause |
| R2 | Memory above the declared limits can affect a later measurement, through the page cache of the node for example | Open | Each record states its reading. No rule compares them |
| R3 | `q1-2` may be `REFUSED` | Accepted | Its refusal is kept, and no Q2 or Q3 run of the next lineage follows it |
| R4 | The freeze record of E02A and E02B does not exist yet | Closed 2026-10-18 by `V2-S6-003-PR1` | It must state the stable identity of the selected qualification and hold each run to the gate on its own reading. **Amended 2026-10-18:** the freeze records of E02A and E02B, revision 1 each, name `q1-2` and its stable identity, and P4 of each holds a run to the gate on its own reading. `tools.experiment_preregistration --check` compares the named identity with the record of `q1-2`. No run of either exists |
| R5 | A change of the CPU count or of the node's allocatable pods by the operator is a new environment | Accepted | It is a fact of the configuration. A new qualification is needed |
