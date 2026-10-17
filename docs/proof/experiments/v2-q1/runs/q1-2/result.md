# Qualification q1-2: QUALIFIED

The second Q1 environment and identity qualification, and the first under
[revision 2 of the Q1 freeze record](../../freeze-r2.v1alpha1.json), on 2026-10-17, at the
commit `ed892a4eac2ee505996f53b6d3e0da31b8e4e204`, on the docker-desktop provider. It is a
qualification and not a reliability experiment: it injected no fault, it derived no
bound, and no figure of it is a latency, a throughput, an availability, or a threshold.

**Result: `QUALIFIED`.** Each of the 17 rules is held, so each acceptance criterion
`Q1-AC1` to `Q1-AC17` holds. The result is stated by
[`record.v1alpha1.json`](record.v1alpha1.json), which `tools.environment_qualification`
built from this directory, and `python -m tools.environment_qualification --check` builds
it again with the same bytes. The driver states no result.

Revision 2 states the stable environment identity that [ADR
0021](../../../../../architecture/decisions/ADR-0021-environment-identity-is-configuration-memory-is-capacity.md)
decides: the configuration, with no memory figure. Memory is read again as a capacity
fact, and `capacity-accepted` held on this run's own reading. This is the qualification
that the Q2 revision 3 and the Q3 revision 2 hold their characterizations to.

## What ran

The branch was created at `ed892a4`, the merge of `V2-S6-004-PR1` and the remote main.
No tracked file was edited before the phase `down` ended, so the executing commit and
the desired revision are the same commit. The Docker Desktop engine had been stopped and
was started before the phase `up`; its virtual machine therefore booted before this run.

| Phase | Started (UTC) | Ended (UTC) | What it did |
|---|---|---|---|
| `up q1run-2` | 14:56:11 | 15:05:50 | The capacity gate before anything was installed (`ACCEPTED`); the API image built at the executing commit and loaded, and the model seed image loaded, its import into the node taking 190.7 s as the transcript states; the prerequisite layer with the model cache claim; the claim filled by one preparation Helm release, which was removed; the delivery controller installed and verified; the capacity gate again (`ACCEPTED`), the reading that Q1 reads; the Application applied; the two rollouts, each within its bound of 900 s |
| `qualify q1run-2 q1-2` | 15:06:05 | 15:10:59 | Steps S0 to S9: the commit, the tree, the desired revision, and the freeze check; the provenance; the controller verification; 5 reconciliation samples; the Deployments; one endpoint reading; the model cache observation of each runtime pod; one RP-1 caller run; the header; the record |
| `down q1run-2` | 15:11:07 | 15:12:54 | The Application, the controller, and the prerequisite layer removed. The namespaces and the custom resource definitions equal those that the phase `up` read before it installed anything, and no persistent volume remains |

Each phase exited 0. Instants are those that the driver printed.

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
| `Q1-AC12` | `deployments-ready` | Each Deployment states and reports 2 Ready replicas. The rule reads the API and the runtime Deployment, and not the collector Deployment |
| `Q1-AC13` | `endpoints-ready` | Each Service has 2 endpoints, both Ready. The endpoint record covers the API and the runtime Service |
| `Q1-AC14` | `images-declared` | The declared API digest and the pinned runtime image |
| `Q1-AC15` | `model-identity-verified` | 15 model identity rules held for the pinned model |
| `Q1-AC16` | `caller-completed` | 33 of 33 requests have the outcome success |
| `Q1-AC17` | `readings-in-order` | The capacity reading precedes, and each other reading lies inside |

## The identities

| Identity | Value |
|---|---|
| Executing commit and desired revision | `ed892a4eac2ee505996f53b6d3e0da31b8e4e204`, the merge of `V2-S6-004-PR1`, and the remote main when the phases `up` and `qualify` read it |
| Release | Key `local-docker-desktop/support-assistant`, identifier `b5457f49092c578496738973a8786a95428517e7ddf755303b4f6842dcb8c9db`, workload version `0.2.0`, the release of `q1-1` |
| Chart | `inferops-llm` `0.6.0` |
| Contract and binding | Contract SHA-256 `818ef5d113b325781e7477c226467487e8a5fae4f42a090a7e06eb2a2fcf5085`; binding `local-docker-desktop`, SHA-256 `8a6903d85ffae7555a22fb1935a66f85d2dbbc4248ab871541ed5f8d59f7d5ee` |
| API image | `sha256:f10c9e9bcd2d085c911f44724196baac344e10f65a4cd3a8400e38fd48400fcc`, the manifest-list digest that the build at the executing commit reported, declared to the Application. The build printed the image manifest `sha256:bba83fa7…` and the config `sha256:cd65ca24…`, those that the builds of `q1-1` and `q2-1` printed |
| Runtime image | `ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384`, the pinned one |
| Model | `Qwen/Qwen3-1.7B-GGUF` at `90862c4b9d2787eaed51d12237eafdfe7c5f6077`, 1,834,426,016 bytes, the pinned digest |
| Delivery controller | `v3.5.3`, the version that the bootstrap procedure pins; its verification exited 0 |
| Caller profile | RP-1, revision 1, SHA-256 `ff3cbab5a3bde8d4e25defe940cbcfb4ea3ff1ba028f1bc25c577636c261c1c3` |
| Freeze record | `docs/proof/experiments/v2-q1/freeze-r2.v1alpha1.json`, content SHA-256 `add73e7e4e9ed20253b0e67734d463cf27f20d685014bae57c79ce241ea48d22` |
| Record | Content SHA-256, with LF, `1141cbd1c0acd7eff839395a89eba3fe116a060dafb3941128bf23c440ec1b3d`. The Q2 and Q3 records of this lineage and the Q4 bound record state this digest |

## The selected environment

| Part | Value |
|---|---|
| Provider | docker-desktop |
| Kubernetes server and kubelet | `v1.36.1` |
| Node | One node, `desktop-control-plane`, allocating 12,000 millicores and 110 pods |
| Container engine | 12 CPUs |
| Identity revision | 2: no memory figure |
| `environmentSha256` | `sha256:6a219b3ff959a0020d982d967abeed6696aa0f0d1b594bdf3ad86b9aeda8cd5c` |

Under the selection rule of the freeze record, E02A and E02B execute in the environment
that a `QUALIFIED` qualification states, and a run whose environment identity differs is
not a run of the controlled comparison. This is that environment. No run of E02A or E02B
exists and no freeze record of either exists, so no comparison with a run of them has
been made. The Q2 characterization [`q2-2`](../../../v2-q2/runs/q2-2/result.md) and the Q3
characterization [`q3-2`](../../../v2-q3/runs/q3-2/result.md) compared their own readings with
this digest, and each held.

**The capacity reading of this run.** The engine and the node reported 10,429,972,480 bytes
of memory. That is 12,288 bytes more than `q1-1` read, and the figure that `q3-1` read
after an earlier boot of the virtual machine. The identity holds no memory figure, so it
is the one that the capacity readings of `q1-1` and `q3-1` also give; a test computes the
three. The figure is a capacity fact of this reading, which the gate accepted. This run
does not establish why the figure repeated.

## What the files show beside the criteria

These are readings of this qualification. None is compared with a bound.

- **The capacity margin was small.** The capacity reading stated that the release requires
  9,865,003,008 bytes of memory limits, against 10,125,885,440 bytes available after the
  reserve and the pods that were running: a margin of 260,882,432 bytes. The gate reads
  stated requests and limits, not use.
- **The model cache record is `INCONCLUSIVE`, by design**, as for `q1-1`: its rules
  `capacity-preflight-sufficient` and `not-ready-while-loading` are not observed. The 15
  rules that Q1 reads are held.
- **The caller run.** RP-1 against the API Service, mode `in-cluster`, concurrency 2, from
  15:09:10.230Z. It dispatched 33 requests in 60,905 ms and ended by its duration bound of
  60 s, before its ceiling of 50. Each of the 33 has the outcome `success`. It is not a
  success rate.
- **Startup probes failed while the runtime pods started.** The pod events hold two failed
  probes for each runtime pod at 15:05:03Z. Both runtime pods were created at 15:04:52Z,
  Initialized at 15:04:56Z, and Ready at 15:05:23Z, and both reported 0 restarts when the
  model cache observation read them. The events of the pods `…-56d47dfdc5-jjl4s`,
  `…-collector-f86bcbf84-sfv6m`, and `…-runtime-77dc4cbd7-lcd76`, around 15:02:54Z, are of
  the preparation release, which was removed before the Application was applied.
- **The controller reported the release as delivered.** At the end of the phase `up` the
  Application was `Synced` and `Healthy` at `ed892a4`. Q1 does not read that report as the
  caller's result.

## What is committed, and what is not

Every file that the phase `qualify` wrote in its directory is committed as written, with
one exception:

- **`capacity/pods.json` is not committed**, for the reason given for `q1-1`: it holds
  container paths under a home directory in the controller's pods, and the publication
  check refuses such a file. It was not edited. Its SHA-256, with LF, is
  `2257cf76fc64a08bfee1b49ab341cbd3c9065cc11a38fd5f0c3a94e39622110d`, as the operator
  measured it before leaving it out; it held 11 lines with `/home/`. No committed file
  corroborates the two values. Q1 reads the stored capacity record, so `--check` is
  unaffected; the capacity record cannot be built again from this directory.

Two files were added after the phases: `transcript.txt`, the three transcripts joined in
phase order, with terminal colour codes removed, the absolute path of the host written as
`<repository>` (two lines), and trailing whitespace removed from six lines, counts that the
assembling script printed and that the committed file cannot show; and this page.

No abort condition of the freeze record is shown. The transcript shows a clean working
tree and no changed material file at the start of the phase `up` and at step S0, and each
of the 18 target checks that the operating procedures printed verified the docker-desktop
target. That no tracked file changed while the qualification ran, and that nobody
changed the release by hand, is the operator's statement. The one line of the transcript
with the word "refused" in the phase `up` is text of the chart's notes.

## What this establishes, and what it does not

It establishes, for one qualification on one provider, one node, one Kubernetes version,
and one release, at C2, that the desired-state release of two API replicas and two runtime
replicas was delivered by the controller at the desired revision with the identities
above, that both runtime replicas served the pinned model from one read-only claim, and
that the in-cluster caller completed real requests through the API Service, in the stable
environment identity above, with the capacity gate accepting this run's memory reading.

It does not establish behaviour under a fault, the replacement of a pod, or a recovery; a
runtime start time, a caller gap, or any bound; a latency, a throughput, a success rate,
or the reliability of the caller path; the memory of a later environment of the same
identity, which each later reading states and the gate decides; why the engine and the
node report another memory figure after a boot of the virtual machine; production
availability, high availability, a service level, or resilience to the loss of a node, a
zone, or a region; or anything about another provider, node, Kubernetes version, or
release. It is not a result of E02 to E06, and no claim cites it.
