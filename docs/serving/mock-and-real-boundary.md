# The mock and real serving boundary

Status: **accepted rule**, effective for evidence produced after this document is
merged. It creates no mock serving path and does not authorise one; it fixes what
a mock may and may not be used to claim, before one exists to argue about.

It exists because the cheapest way to lose a project's credibility is to publish a
real-sounding claim backed by a fake. The rule in
[CONTRIBUTING](../../CONTRIBUTING.md) already says a mock cannot certify real
runtime behaviour. This document says *why*, in terms specific enough to settle an
argument, and says what has to be true of a record before a real-runtime claim may
rest on it.

## The rule

**A mock serving path may never be used to certify real local runtime behaviour,
however faithfully it reproduces the API surface.**

A real-local-runtime claim requires an executed record naming the runtime image
digest, the model revision and per-file hash, the environment, the exact commands,
and the actual results. No such record, no claim. Not a weaker claim — no claim.

## Why faithfulness does not help

The obvious objection is that a sufficiently good mock is indistinguishable from
the real thing at the API boundary. That is very nearly true, and it is also the
reason the mock cannot certify anything.

**Certification asks whether the contract matches reality. A mock is built from
the contract.** Pointing one at the other tests the author's understanding against
itself. It will pass. It would also pass if the contract were wrong, which is the
only case where the test was worth running.

Every property that makes real serving hard lives *outside* the response body:

| Property | What a real runtime has | What a mock has |
|---|---|---|
| Model load | A multi-second window in which the process is up and cannot answer | Readiness at process start |
| Memory | A resident footprint set by weights, quantisation, and KV cache | The mock's own footprint |
| Token accounting | Counts the runtime derived from its own tokeniser | Numbers its author chose |
| Latency and decode rate | A property of this model on this hardware | A sleep, or nothing |
| Weights | A large binary parsed by a native process | No weights at all |
| Failure modes | Whatever the runtime, the file, and the host actually do | Whatever was anticipated |

The last row is the important one, and the trial recorded in
[the V1-S0-003-PR2 feasibility record](../proof/serving/v1-s0-003-pr2-runtime-feasibility.md)
is the evidence for it. That run surfaced several defects that no mock of the
serving API could have surfaced, because none of them is in the serving API:

- the health endpoint returns 503 while loading, which is correct readiness
  behaviour and wrong liveness behaviour, so a liveness probe aimed at it restarts
  the pod mid-load and never converges;
- the weight transfer did not survive a single streamed request and had to be made
  resumable;
- `df` inside the cluster reported hundreds of gigabytes free on a sparse virtual
  disk whose real backing volume had a small fraction of that;
- the downloader does not validate TLS certificates, which moves the entire
  integrity argument onto the published file hash.

A mock would have been ready instantly, needed no weights, sat on no disk, and
downloaded nothing. It would have passed a contract suite on the first attempt and
taught the project none of the four things above.

## What a mock is legitimately for

This is not an argument against mocks. It is an argument against one specific
misuse. A mock is the right tool for:

- deterministic contract tests, where a real model's output would make the
  assertion flaky;
- continuous integration that cannot host a model, so that the contract is still
  exercised on every change;
- consumer-side development against a provider that is slow, large, or not yet
  built;
- negative and error-path testing, where provoking the real failure is expensive or
  destructive.

In each case the mock proves something real about the *consumer* or the *contract*. It
proves nothing about the provider.

## Boundary rules

1. **Label at the source.** A mock artifact — image, fixture, manifest, or
   response — must be identifiable as a mock from the artifact itself, not from the
   directory it happens to sit in.
2. **Separate records.** Mock evidence and real-runtime evidence are separate
   documents. A single record must not mix them, because a reader who skims will
   carry the strongest label in the document away from it.
3. **Cite the executed record.** Any real-runtime claim links to a record
   containing digests, revision, environment, commands, and results. A claim whose
   only support is a document is `documented and unexecuted`, and must say so.
4. **Absence is reportable.** Where a real record does not exist, the correct
   output is an unmet criterion and a recorded blocker. Substituting a mock result
   is a defect, not a fallback.
5. **A mock may never be the default in the mandatory path.** If the mandatory
   serving path can be satisfied by a mock, the project has not built a serving
   path.

## Vocabulary

The labels are the ones [CONTRIBUTING](../../CONTRIBUTING.md) already defines:
`documented/unexecuted`, `mock`, `synthetic`, `estimated`, `local real runtime`,
`cloud real runtime`, `production experience`. Pick the **weakest** label the
record actually supports. Where two could apply, the weaker one is correct.
