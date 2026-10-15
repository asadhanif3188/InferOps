# Qualification q1-1: QUALIFIED

The first Q1 environment and identity qualification, under
[revision 1 of the Q1 freeze record](../../freeze-r1.v1alpha1.json), on 2026-10-15, at the
commit `08b89144f76d86cbbcf44de8845d04f018c88453`, on the docker-desktop provider. It is a
qualification and not a reliability experiment: it injected no fault, it derived no
bound, and no figure of it is a latency, a throughput, an availability, or a threshold.

**Result: `QUALIFIED`.** Each of the 17 rules is held, so each acceptance criterion
`Q1-AC1` to `Q1-AC17` holds. The result is stated by
[`record.v1alpha1.json`](record.v1alpha1.json), which `tools.environment_qualification`
built from this directory, and `python -m tools.environment_qualification --check` builds
it again with the same bytes. The driver states no result.

## What ran

The three phases of [the frozen driver](../../procedure/q1-driver.txt) ran once each,
from the committed tree with a clean working tree, in this order, and each printed its
`driver exit` line before the next one started. [`transcript.txt`](transcript.txt) holds
what each phase printed.

| Phase | Started (UTC) | Ended (UTC) | What it did |
|---|---|---|---|
| `up q1run-1` | 07:04:55 | 07:17:45 | The capacity gate before anything was installed (`ACCEPTED`); the API image built at the executing commit and loaded, and the model seed image loaded; the prerequisite layer with the model cache claim; the claim filled by one preparation Helm release, which was removed; the delivery controller installed and verified; the capacity gate again (`ACCEPTED`), the reading that Q1 reads; the Application applied; the two rollouts, each within its bound of 900 s |
| `qualify q1run-1 q1-1` | 07:18:00 | 07:22:24 | Steps S0 to S9: the commit, the tree, the desired revision, and the freeze check; the provenance; the controller verification; 5 reconciliation samples; the Deployments; one endpoint reading; the model cache observation of each runtime pod; one RP-1 caller run; the header; the record |
| `down q1run-1` | after 07:22:24 | 07:25:04 | The Application, the controller, and the prerequisite layer removed. The namespaces and the custom resource definitions equal those that the phase `up` read before it installed anything, and no persistent volume remains |

`q1run-1` names the work directory under `.artifacts/`. An earlier collection of the
capacity gate was named `run-1`, so a fresh name was taken; the run name is not a
qualification identifier and no rule reads it.

## The criteria

| Criterion | Rule | Detail that the record states |
|---|---|---|
| `Q1-AC1` | `target-reached` | No refusal; the capacity collection read the selected target |
| `Q1-AC2` | `provider-selected` | Every source names docker-desktop |
| `Q1-AC3` | `context-unambiguous` | One target, one node, and the runtime pods run on it |
| `Q1-AC4` | `working-tree-clean` | The working tree was clean |
| `Q1-AC5` | `procedure-frozen` | The freeze record is the checkout's, and no material file changed |
| `Q1-AC6` | `desired-revision-known` | The delivery paths of the executing commit equal those of the desired revision |
| `Q1-AC7` | `one-executing-commit` | Each collection names the executing commit |
| `Q1-AC8` | `release-provenance-resolved` | Release `b5457f49092c578496738973a8786a95428517e7ddf755303b4f6842dcb8c9db` at the desired revision |
| `Q1-AC9` | `capacity-accepted` | `ACCEPTED` for 2 API and 2 runtime replicas |
| `Q1-AC10` | `controller-identified` | Verified, version `v3.5.3` |
| `Q1-AC11` | `controller-reconciled` | 5 samples settled at the desired revision and release |
| `Q1-AC12` | `deployments-ready` | Each Deployment states and reports 2 Ready replicas |
| `Q1-AC13` | `endpoints-ready` | Each Service has 2 endpoints, both Ready |
| `Q1-AC14` | `images-declared` | The declared API digest and the pinned runtime image |
| `Q1-AC15` | `model-identity-verified` | 15 model identity rules held for the pinned model |
| `Q1-AC16` | `caller-completed` | 34 of 34 requests have the outcome success |
| `Q1-AC17` | `readings-in-order` | The capacity reading precedes, and each other reading lies inside |

## The identities

| Identity | Value |
|---|---|
| Executing commit and desired revision | `08b89144f76d86cbbcf44de8845d04f018c88453`, the merge of `V2-S6-001-PR1`, and the remote main when the phases `up` and `qualify` read it |
| Release | Key `local-docker-desktop/support-assistant`, identifier `b5457f49092c578496738973a8786a95428517e7ddf755303b4f6842dcb8c9db`, workload version `0.2.0` |
| Chart | `inferops-llm` `0.6.0`, Helm values SHA-256 `6a1304a8f7a2c629a20a2b2ee6697f29a05d9963be43b470c82589c7f469b930` |
| Contract and binding | Contract SHA-256 `818ef5d113b325781e7477c226467487e8a5fae4f42a090a7e06eb2a2fcf5085`; binding `local-docker-desktop`, SHA-256 `8a6903d85ffae7555a22fb1935a66f85d2dbbc4248ab871541ed5f8d59f7d5ee` |
| API image | `sha256:5b4be2da31141bc43c0fa65133b4377ef002a3ff922278cda98ba247a244c7e1`, built at the executing commit and declared to the Application |
| Runtime image | `ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384`, the pinned one |
| Model | `Qwen/Qwen3-1.7B-GGUF` at `90862c4b9d2787eaed51d12237eafdfe7c5f6077`, `Qwen3-1.7B-Q8_0.gguf`, 1,834,426,016 bytes, the pinned digest |
| Delivery controller | `v3.5.3`, the version that the bootstrap procedure pins; its verification exited 0 |
| Caller profile | RP-1, revision 1, SHA-256 `ff3cbab5a3bde8d4e25defe940cbcfb4ea3ff1ba028f1bc25c577636c261c1c3` |
| Freeze record | `docs/proof/experiments/v2-q1/freeze-r1.v1alpha1.json`, content SHA-256 `f23426223d19abf19fa3c8beaaa138abe93bdef8ab376335eda50b0da3f29ded` |

## The selected environment

| Part | Value |
|---|---|
| Provider | docker-desktop |
| Kubernetes server and kubelet | `v1.36.1` |
| Node | One node, `desktop-control-plane`, allocating 12,000 millicores, 10,429,960,192 bytes of memory, and 110 pods |
| Container engine | 12 CPUs, 10,429,960,192 bytes of memory |
| `environmentSha256` | `sha256:23db293eeac80960eb77eac228188ceb5ac2cd1c11a925636aa61f1318866461` |

Under the selection rule of the freeze record, E02A and E02B execute in this
environment, and a run whose environment identity differs is not a run of the
controlled comparison. No run of E02A or E02B exists, no freeze record of either exists,
and no tool compares two identities yet, so this page selects the environment and
compares nothing.

## What the files show beside the criteria

These are readings of this qualification. None is compared with a bound.

- **The capacity margin was small.** Both capacity readings stated that the release
  requires 9 pods, 3,110 millicores of CPU requests, and 9,865,003,008 bytes of memory
  limits, against 10,125,873,152 bytes available: a margin of 260,870,144 bytes. The
  gate reads stated requests and limits, not use.
- **The model cache record is `INCONCLUSIVE`, by design.** Its rules
  `capacity-preflight-sufficient` and `not-ready-while-loading` are not observed: Q1
  runs neither the V1 multi-replica preflight nor samples of the start. The 15 rules
  that Q1 reads are held: one runtime image, one model argument, one claim mounted read
  only and in effect read only, one directory, one file with the pinned byte count, a
  verification in each pod, one reported model, and one completion from each runtime.
- **The caller run.** RP-1 against the API Service, mode `in-cluster`, concurrency 2,
  from 07:20:44.212Z. It dispatched 34 requests in 61,967 ms and ended by its duration
  bound of 60 s, before its ceiling of 50. Each of the 34 has the outcome `success`. One
  run of 34 requests shows that the path answered. It is not a success rate.
- **Startup probes failed while the pods started, and no pod restarted.** The pod
  events of the release namespace hold one failed startup probe for each API pod at
  07:16:31Z and two for each runtime pod between 07:16:56Z and 07:17:06Z, before each
  became Ready. At 07:17:45Z every pod of the release reported 0 restarts, and the two
  runtime containers reported 0 restarts when the model cache observation read them.
  The events that name another pod template are of the preparation release, which was
  removed before the Application was applied.
- **The controller reported the release as delivered.** At the end of the phase `up`
  the Application was `Synced` and `Healthy` at `08b8914`. Q1 does not read that
  report as the caller's result: `caller-completed` reads the caller record.

## What is committed, and what is not

Every file that the phase `qualify` wrote in its directory is committed as written,
including `started-at` and `reported-revision`, which the driver writes beside the
collections, with one exception:

- **`capacity/pods.json` is not committed.** It is the capacity gate's read of every
  pod of the cluster, taken while the controller was installed, and it holds container
  paths under a home directory in the controller's pods. The repository's publication
  check refuses a committed file with such a path, and the file was not edited. Its
  SHA-256, with LF, is `6f695f25d46e24bbb53a7efc94af8ae745f51032ffbe3e46e4770bcd9d9d2ccd`,
  and it was 267,824 bytes. Q1 reads the stored capacity record and not this read, so
  `--check` is unaffected. The capacity record cannot be built again from this
  directory.

Two files were added after the phases: `transcript.txt`, the three transcripts joined in
phase order, with terminal colour codes removed, the absolute path of the host
written as `<repository>` (two lines), and trailing whitespace removed from six lines;
and this page. The record does not list either,
because the tool lists only the files that it reads.

No abort condition of the freeze record occurred: no tracked file changed while the
phases ran, nobody changed a replica count, a request, a limit, or an object of the
release, and each of the 18 target checks that the operating procedures printed
verified the docker-desktop target. The one line of the transcript with the word
"refused" in the phase `up` is text of the chart's notes, which the preparation release
printed.

## What this establishes, and what it does not

It establishes, for one qualification on one provider, one node, one Kubernetes version,
and one release, at C2, that the desired-state release of two API replicas and two
runtime replicas was delivered by the controller at the desired revision with the exact
identities above, that both runtime replicas served the pinned model from one read-only
claim, and that the in-cluster caller completed real requests through the API Service.

It does not establish behaviour under a fault, the replacement of a pod, or a recovery;
a runtime start time, a caller gap, or any bound that later work derives; a latency, a
throughput, a success rate, or the reliability of the caller path; that a later run uses
the same environment; capacity beyond the stated requests and limits on one node;
production availability, high availability, a service level, or resilience to the loss
of a node, a zone, or a region; or anything about another provider, node, Kubernetes
version, or release. It is not a result of E02 to E06, and no claim cites it.
