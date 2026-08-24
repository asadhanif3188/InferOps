# Contracts

Status: one contract accepted at alpha maturity. No component in this repository
consumes it.

This directory indexes versioned, machine-readable public contracts and the
compatibility policy each one carries. The schemas themselves live under
[`contracts/`](../../contracts/README.md); the documents here say what each schema
means, how it is versioned, which rules are enforced, and which are not.

| Contract | Version | Status | Document |
|---|---|---|---|
| WorkloadContract | `v1alpha1` | Accepted; no consumer exists | [WorkloadContract v1alpha1](workload-contract.md) |

A published schema is a commitment about what will be accepted. It is not evidence
that anything accepts it, and it certifies no runtime behaviour.

## What a contract entry must carry

Owner, version, maturity, compatibility rules, valid and invalid fixtures, security
behaviour, telemetry implications, and validation evidence. A proposed document must
be visibly labelled as proposed.

Where a rule is stated but not yet enforced, the entry must say so in the same place
it states the rule. A reader must never have to discover from a failure that a rule
was aspirational.

## Not yet published

No capability descriptor, runtime descriptor, model-access API, evaluation result,
cost record, policy decision, or compatibility matrix exists. Each will be added
when the capability behind it exists rather than in advance.
