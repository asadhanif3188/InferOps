# Runtime and model feasibility workflow

Status: **procedure only. It has never been run.** No stage below has been executed
by this project, no model has been downloaded, and no inference has been served.
This document is the plan a trial follows, written before the trial so that the
trial can produce a result rather than a narrative.

It exists to serve
[ADR 0002](../architecture/decisions/0002-model-and-serving-runtime.md), which fixes
the criteria and the thresholds `T1`–`T12` referenced throughout. Read that record
first; the thresholds are not repeated here.

## What this workflow is for, and what it is not for

It answers one question: **can a specific runtime image, at a specific digest,
serve a specific model revision inside the environment ADR 0001 already proved, and
does the result meet the thresholds?**

It is not a benchmark, not a model-quality evaluation, and not a performance
claim. `T9` sets a floor for "usable at all" and nothing more. Any number this
workflow produces describes one model on one host on one day, and must be published
with that framing or not at all.

## Bounds

The trial is deliberately bounded. These are limits on the procedure itself, not
advice.

| Bound | Limit | Why |
|---|---|---|
| Single-file download | 3 GB | Above this, a failed trial has cost more than it can justify on a disk-constrained host |
| Total download for one trial | 8 GB | Matches `T4` |
| Free-space floor | Abort if the target volume would drop below 5 GB free | ADR 0001 recorded that engine disk growth is not returned on teardown |
| Host-wide changes | None beyond the exceptions ADR 0001 D5 already names | A trial does not get to widen an accepted isolation rule |
| Cluster | The project's own `inferops-dev` cluster only | ADR 0001 D5 |
| Namespace | One `inferops-` namespace, created by the trial and deleted by it | ADR 0001 D5 and D6 |
| Duration | If a single stage exceeds 30 minutes, stop and record the timeout as the result | An unbounded wait is not evidence of anything |

### Authorisation gate

Stages 2 onward download model weights and run a workload. **Do not start them
without explicit authorisation from whoever owns the host.** Record who authorised
it and when, in the evidence record. Stage 0 and Stage 1 are safe to run without
it: they read published metadata and resolve digests, and they download nothing of
consequence.

If authorisation is withheld, the correct outcome is a completed Stage 0 and
Stage 1, a recorded blocker, and thresholds `T3`–`T10` left explicitly unmet. It is
not a smaller claim built from documentation.

## Prerequisites

- The environment in [prerequisites](../prerequisites.md), with the cluster from
  [the local cluster runbook](../environment/local-cluster.md) creatable and
  destroyable. The **minimum** tier is the floor for running the cluster; it is not
  a claim that the minimum tier can serve a model. Whether it can is precisely what
  `T3` and `T4` are there to find out, and ADR 0001 D7 already warns that the
  reference host does not meet the tier its own estimate assigned to serving.
- A model cache directory **outside the repository working tree**, with the free
  space the bounds above require. Point the acquisition tool at it through its own
  cache environment variable rather than copying files by hand; nothing about the
  cache location belongs in this repository or in a commit.
- Network access to the runtime's container registry and the model publisher.
- No account, API key, or paid subscription. If any stage asks for one, that is a
  `T11` failure and the trial stops.

## Stage 0 — Record the environment

Capture, before anything else, what the rest of the record will be interpreted
against: operating system and build, container engine server version, cluster tool
version, node image digest, `kubectl` client and server versions, the memory and
processor allocation actually reaching the container VM, and free space on the
target volume.

This repeats what
[the cluster smoke proof](../proof/environment/v1-s0-002-pr2-cluster-smoke.md)
established for the environment, and it is repeated deliberately: an environment
measured three months ago is not the environment the trial ran in.

## Stage 1 — Resolve and pin, before downloading anything

Nothing large is fetched here. The output is a set of immutable identifiers.

1. **Licence.** Retrieve the runtime's licence and the model's licence from their
   own repositories. Record the licence identifier, the URL, and the date read.
   Check `T1` against the licence text, not against a summary of it — including any
   acceptable-use policy or supplementary terms referenced from it.
2. **Runtime image digest.** Resolve the published tag to a digest and record the
   digest. Deploy by digest from this point on. A tag that was correct when it was
   read is not a pin; ADR 0001 recorded this failure mode already.
3. **Model revision.** Record the model repository's commit revision, not its
   default branch name.
4. **File hashes.** Record the SHA-256 of each weight file to be used, as published
   by the repository, so that Stage 2 can verify what it received rather than trust
   it.
5. **Size.** Record the download size and check it against the bounds table before
   proceeding.

If any of these cannot be obtained, `T2` fails and the trial stops here. That is a
complete, publishable result.

## Stage 2 — Acquire the weights

**Authorisation required.**

1. Re-check free space on the target volume against the floor in the bounds table.
2. Download the pinned files, by revision, into the cache directory.
3. Verify each downloaded file against the hash recorded in Stage 1. A mismatch
   stops the trial; do not proceed with a file that does not match, and record the
   mismatch as the result.
4. Record the elapsed time, the bytes transferred, and free space afterwards.

## Stage 3 — Deploy into the project's own cluster

**Authorisation required.**

Create the cluster, then a single `inferops-`-prefixed namespace, and deploy one
replica of the runtime, referenced **by image digest**. The workload must carry the
project label ADR 0001 D5 requires, run as a non-root user, request no privilege
escalation, and mount nothing from the host except the model cache. Set explicit
memory and CPU requests and limits — a workload with no limit cannot produce a
resource measurement worth recording, only an anecdote.

Configure the three probes as ADR 0002 proposes: `startupProbe` and
`readinessProbe` against the health endpoint, `livenessProbe` against the TCP port.
Give the startup probe a budget generous enough that Stage 4 measures the model's
load time rather than the probe's patience.

Record the applied manifest, the pod's resolved image digest as the cluster reports
it — not as the manifest requested it — and its security context.

## Stage 4 — Observe the load and readiness transition

This stage exists to test `T6` and `T8`, and it is the one most easily faked by
looking only at the end state.

1. Poll the health endpoint from the moment the pod's container starts. Record that
   it reports **not ready** during load, and the response it gives while doing so.
2. Record the time from container start to first ready.
3. Confirm that no restart occurred during load. A restart here means the probe
   configuration is wrong, and both the restart and the correction belong in the
   record.
4. Repeat three times cold — weights present, process fresh — and three times warm.
   Report the worst case, not the best.

Query the runtime's metadata endpoint and record the model identity it reports.
If it disagrees with the pinned revision, the pin is not doing its job and that is
the finding.

## Stage 5 — One real inference

The point of the whole exercise, and the stage whose result is easiest to overstate.

1. Send one chat completion request to the OpenAI-compatible endpoint, at
   temperature 0, with a fixed maximum token count, from **inside** the cluster —
   through cluster DNS and the Service — so that what is proven is the path the
   platform will actually use.
2. Record the full request and the full response verbatim, including the model
   identifier and the token usage the runtime reports.
3. Record wall-clock latency, and derive a decode rate from the reported token
   counts and the measured time. Label it a derived figure.
4. Repeat twice more to show the result is not a single lucky sample, and report
   the spread.

Choose a prompt whose response is safe to publish: neutral, short, containing no
personal data, no host detail, and nothing that would embarrass anyone if it is
read by a stranger in a public repository — because it will be.

A response that arrives is not automatically a pass. Check the body shape against
`T5`: `choices[0].message.content` present and non-empty, `model` present,
`usage` carrying token counts.

## Stage 6 — Metrics

Scrape the metrics endpoint and record the exposition verbatim, or a faithful
excerpt. `T7` asks for two specific things — a request counter and token counters —
so record which required series are present, which are absent, and their exact
names. "Metrics are available" is not a result; a list of series is.

## Stage 7 — Resource measurement

With the runtime ready and idle, and again immediately after Stage 5, record:

- pod memory and CPU as the cluster reports them;
- total memory in use inside the container VM;
- free space on the target volume;
- the size of the runtime image as the engine stores it.

Compare against `T3` and `T4`. Report the numbers whether or not they pass.

## Stage 8 — Teardown and residue

Remove the namespace, then the cluster, using the project's own scoped teardown.
Then verify residue is absent the way ADR 0001 D6 requires — cluster list, context
list, engine container list, and engine volume list, the last two filtered by
label — and re-measure free space across the whole cycle rather than only while the
workload existed. ADR 0001 recorded that the second measurement is the one that
tells the truth about disk.

The cached weights survive teardown by design, like the cached node image. Say so
in the record, with their size, rather than leaving a reader to discover it.

## Step-down procedure

If a **step-down** threshold fails — `T3`, `T4`, `T8`, or `T9` — do this once,
and only once, before judging the runtime:

1. Record the failure with its measured value. Do not overwrite it.
2. Move to the next-smaller model or quantisation named in ADR 0002's shortlist.
3. Re-run Stages 2 through 8.
4. Record **both** results. "The 1.7B model did not fit and the 0.6B model did" is
   the finding; "the runtime works" is not.

If a step-down also fails, stop. The result is that the reference host cannot serve
this candidate, which is a legitimate outcome that ADR 0001 D7 already flagged as
possible.

## Abort conditions

Stop immediately, and record the stage reached and the reason, if any of these
occur:

- a licence turns out to require acceptance, an account, or a payment (`T1`, `T11`);
- a downloaded file does not match its published hash;
- free space would fall below the floor;
- the workload requires privileged execution, a host mount beyond the model cache,
  or a change to a host-wide setting ADR 0001 D5 does not already permit;
- a stage exceeds the 30-minute limit;
- teardown leaves residue that scoped deletion cannot remove.

An aborted trial with a recorded reason is a result. A trial quietly restarted with
different settings until it passed is not.

## Recording the outcome

Use [the feasibility evidence template](../proof/serving/TEMPLATE-runtime-feasibility.md).
Every threshold gets an explicit verdict — met, not met, or not executed — and no
threshold may be left blank. Label every figure as measured, derived, or documented,
following the evidence rules in [CONTRIBUTING](../../CONTRIBUTING.md).

## What this workflow cannot establish

Stated here so that a passing record is not read as more than it is:

- **Nothing about model quality.** One completion at temperature 0 shows the path
  works. It says nothing about whether the answer is good.
- **Nothing about throughput or concurrency.** Every stage is single-request.
- **Nothing about any other host.** One host, one architecture, one point in time —
  the same limit ADR 0001's evidence carries.
- **Nothing about a GPU path.** There is no discrete accelerator on the reference
  host, so `T12` can only ever be satisfied here by the CPU path being complete on
  its own.
- **Nothing about production behaviour.** A local kind cluster is not a production
  environment and a passing trial is not a production readiness claim.
