# V2-E01, part E01-D: run `20261006-e01-d-1`

**Outcome: PASSED.** One real deployment with one completion request, under
[revision 3 of the freeze record](../../freeze-r3.v1alpha1.json), at the merged commit
`ad725905a7838e8210e54a29de7913bc0c7c49e5`, on the `docker-desktop` provider. Intended evidence level: C2.

This page states the limitations first, then each criterion with its verdict and the
evidence it rests on. [`run.v1alpha1.json`](run.v1alpha1.json) holds every compared value.

## Limitations

- No runner and no coded analysis exist for E01-D. The automated assistant session that wrote the driver started it and applied the registered verification rules to the files. A script that is not committed compared the values. This manifest states each compared value, so a reader can compare them again from the files.
- The driver is not a pinned input of the freeze record. driver.txt holds it as it ran.
- The run sent one completion request. It does not establish that a second request is answered.
- The run did not observe the network. It does not establish that the acquisition hook downloaded nothing. Argo CD reports that the sync operation, which holds the hook, started at 2026-10-06T12:13:07Z and finished at 2026-10-06T12:13:16Z.
- The eight-character clause of E01-AC10 is not computed over the live Application. It rests on the consumed static result and on three tests.
- The model revision is verified by configuration and by content. Nothing reads the revision from the model file.
- The pod status reports the API container's image under another digest than the one the run supplied. postRunObservations states what a later read of the node showed. No E01-D criterion names the API image digest.
- transcript.txt is the driver's output with three kinds of text replaced: terminal colour codes are removed, the absolute path of the repository on the host is replaced by <repository>, and two Docker build links are replaced by <build details link>. The unredacted transcript is not committed.
- The response body and the readiness body are under .artifacts/, which Git ignores. They are not committed.
- sha256sum in step P2 printed the digest of the working-tree bytes of the freeze record and of the registry. On this host those bytes hold CRLF. The content digests in this manifest are computed with every CRLF replaced by LF, as the registry defines them.
- The times are the host's clock and the cluster's clock. No repository file proves them.
- One provider, one cluster with one node, one contract, one binding, and one run.

## What executed

- The driver in [`driver.txt`](driver.txt) ran the registered steps once: preparation P1
  to P7, procedure D1 to D6, and the cleanup. [`commands.txt`](commands.txt) lists the
  commands in order, and [`transcript.txt`](transcript.txt) holds what they printed.
- Start: 2026-10-06T12:03:47Z. End: 2026-10-06T12:15:17Z.
- Preconditions: the working tree was clean, `refs/heads/main` on the remote named the
  executing commit, the freeze check passed, no material file differed from revision 3,
  each environment attribute that step P3 reads was equal, and each preparation step
  ended with exit status 0.
- The apply of step D3 started at 12:12:45Z and returned at 12:13:19Z. Both rollouts were
  complete 18 seconds later. The deadline was 600 seconds.
- The readiness request returned 200. Then the run sent one completion request, and it
  sent no other.
- Abort conditions: none was met.
- Cleanup: the Application, its project, Argo CD, the platform namespace, and the claim
  were removed. The namespaces and the custom resource definitions after the run equal
  those of step P3. The images stay.

## Criteria

### E01-AC8: holds

> The release rendered from the unmodified reference contract, accepted into Git and reconciled by Argo CD, produces at least one real successful completion: HTTP 200, with at least one choice whose assistant message is not empty.

| Rule | Verdict | Observed | Evidence |
|---|---|---|---|
| completion.json records HTTP status 200 for the one request of step D5. | holds | httpStatus: `"200"`<br>curlExitStatus: `0`<br>requestsSent: `1` | completion.json, transcript.txt |
| The response holds at least one choice, and the assistant message of the first choice has a length greater than 0. | holds | choiceCount: `1`<br>firstChoiceMessageRole: `"assistant"`<br>assistantMessageLength: `6` | completion.json |
| The release that served it is the one of steps D1 to D3: the rules of E01-AC9 hold. | holds | E01-AC9: `true` | the rules of E01-AC9 in this manifest |

### E01-AC9: holds

> The deployed identities verify against the release: the desired-state revision Argo CD reports as synced holds the generated release; the release records the contract, binding, and values digests, and they match their sources and the values file; the running runtime container's image digest is the generated runtime.image.digest; the model revision the runtime reads is the generated model.revision; and the API serves the model under the generated model.identifier.

| Rule | Verdict | Observed | Evidence |
|---|---|---|---|
| Synced revision: in argo.json, status.sync.status is Synced, status.sync.revision is the executing commit, and status.operationState.phase is Succeeded with status.operationState.syncResult.revision equal to the executing commit. | holds | status.sync.status: `"Synced"`<br>status.sync.revision: `"ad725905a7838e8210e54a29de7913bc0c7c49e5"`<br>status.operationState.phase: `"Succeeded"`<br>status.operationState.syncResult.revision: `"ad725905a7838e8210e54a29de7913bc0c7c49e5"`<br>executingCommit: `"ad725905a7838e8210e54a29de7913bc0c7c49e5"` | argo.json |
| Generated release at that revision: provenance.json, resolved from that commit, gives the releaseId and the values digest that this record names under inputs.desiredStateRelease. | holds | resolvedFrom: `"ad725905a7838e8210e54a29de7913bc0c7c49e5"`<br>releaseId: `"eeda9493e0ffca2af499342e2850c63e30ff7254d094016c816d7fbe23fc01ae"`<br>valuesSha256: `"1849af0c88c2ef646b4f6eddfb515ba5fd3f3cbc5ac44950a35b9bf8cec864ce"`<br>frozenReleaseId: `"eeda9493e0ffca2af499342e2850c63e30ff7254d094016c816d7fbe23fc01ae"`<br>frozenHelmValuesSha256: `"1849af0c88c2ef646b4f6eddfb515ba5fd3f3cbc5ac44950a35b9bf8cec864ce"` | provenance.json |
| Recorded digests: step D1 exits 0, so the release's contract, binding, and values digests are the ones its sources and its values file derive. The SHA-256 that release.json records for values.generated.yaml equals the values digest that this record names under inputs.desiredStateRelease. | holds | stepD1ExitStatus: `0`<br>valuesGeneratedSha256: `"1849af0c88c2ef646b4f6eddfb515ba5fd3f3cbc5ac44950a35b9bf8cec864ce"`<br>frozenHelmValuesSha256: `"1849af0c88c2ef646b4f6eddfb515ba5fd3f3cbc5ac44950a35b9bf8cec864ce"` | release.json, transcript.txt |
| Runtime image: in pods.json, the imageID that the status of the container named runtime reports ends with the generated runtime.image.digest, sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384. | holds | runtimeContainerImageID: `"ghcr.io/ggml-org/llama.cpp@sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384"`<br>generatedRuntimeImageDigest: `"sha256:100de626bdc5b7df898c12561eefaf557019d2746d5fc8d3f4d7fd24e15ad384"` | pods.json |
| Model revision: in pods.json, the model volume mount of the runtime container has a subPath that ends with the generated model.revision, 90862c4b9d2787eaed51d12237eafdfe7c5f6077, and the init container verify-model terminated with exit code 0. | holds | modelVolumeMountSubPath: `"Qwen--Qwen3-1.7B-GGUF/90862c4b9d2787eaed51d12237eafdfe7c5f6077"`<br>generatedModelRevision: `"90862c4b9d2787eaed51d12237eafdfe7c5f6077"`<br>verifyModelExitCode: `0` | pods.json |
| Model identifier: completion.json records a response whose model is the generated model.identifier, qwen3-1-7b-q8-0. | holds | responseModel: `"qwen3-1-7b-q8-0"`<br>generatedModelIdentifier: `"qwen3-1-7b-q8-0"` | completion.json |

### E01-AC10: holds

> No claim-relevant workload intent is written by hand after rendering: no hand-written value and no operator-supplied parameter of the release restates or overrides claim-relevant workload intent; the release takes its values from the generated values file, from the hand-written values of the Argo CD Application, and from one operator-supplied Helm parameter, api.image.digest, over the chart's own defaults, and from no other source; admit_manual_values admits those hand-written values, with that parameter, beside the generated values with no finding; and no string in them contains a workload-intent generated value of eight characters or more.

| Rule | Verdict | Observed | Evidence |
|---|---|---|---|
| Sources of values: in argo.json, spec.source.helm.valueFiles is exactly the one generated values file, spec.source.helm.valuesObject equals the valuesObject of the committed manifest, spec.source.helm.parameters is exactly one parameter named api.image.digest whose value is the digest of step P4, and spec.source.helm holds no other member than releaseName. Step D3's verify exits 0. | holds | valueFiles: `["/gitops/environments/local-docker-desktop/workloads/support-assistant/values.generated.yaml"]`<br>valuesObjectEqualsCommittedManifest: `true`<br>parameters: `[{"name": "api.image.digest", "value": "sha256:dfb772f2e0cc36e343ef95cd16718e9e9330898685e579b34de15a8ceb6a24dd"}]`<br>digestOfStepP4: `"sha256:dfb772f2e0cc36e343ef95cd16718e9e9330898685e579b34de15a8ceb6a24dd"`<br>membersOfSpecSourceHelm: `["parameters", "releaseName", "valueFiles", "valuesObject"]`<br>stepD3VerifyExitStatus: `0` | argo.json, infra/argocd/local-docker-desktop-support-assistant.yaml at the executing commit, transcript.txt |
| Admission: the three tests of tests/architecture/test_argocd_application.py that step D6 selects pass at the executing commit. They hold that the admission check returns no finding for the Application's hand-written values, that those values set no leaf that the generated values file holds, that they carry no API image digest, and that they equal the hand-written values fixture without its API image digest. No step runs the admission check over the hand-written values with the parameter merged in: the fixture is that shape, and the consumed static result admits it. | holds | pytestSummary: `"3 passed, 33 deselected"`<br>pytestExitStatus: `0` | transcript.txt, step D6 |
| Eight-character clause: the consumed static result holds, in E01-AC5, that the fixture with its digest is admitted with no finding and that no string in it contains a workload-intent generated value of eight characters or more. The Application's hand-written values with the parameter are that shape. No code computes the clause over the live Application. | holds | consumedStaticRun: `"docs/proof/experiments/v2-e01/runs/20261003-e01-abc-1/run.v1alpha1.json"`<br>consumedOutcomeE01A: `"PASSED"`<br>computedOverTheLiveApplication: `false` | the consumed static result that the freeze record names, transcript.txt, step D6 |

## One observation outside the criteria

The pod of the API requested `localhost/inferops-api@sha256:dfb772f2e0cc36e343ef95cd16718e9e9330898685e579b34de15a8ceb6a24dd`. Its container status
reports the image identity `localhost/inferops-api@sha256:8d2b578c4322238734890a0424a2733f6f3269a0a5d54706c8664e9f49a222cd`.
The pod requested the digest that the run supplied. The container status names another digest of the same repository. After the run, the node's image store listed both digests for one image identifier, and that identifier is the configuration digest that the build of step P4 exported. The earlier digest is of a build before this run, which the node still held. This read is not a registered step, and its output is not in the transcript.
No E01-D criterion names the API image digest. The rule of E01-AC10 compares the parameter on the Application with the digest of step P4, and they are equal.

## What this run does not establish

- Portability to another workload shape.
- Asynchronous or batch support.
- Reliability under failure.
- Production readiness.
- That the first run, 20261002-e01-abc-1, executed under this revision's execution boundary. It did not; history.priorRuns says why.
- Behaviour on another provider, another Kubernetes version, another node count, or another storage class than the environment identity names.
- That Argo CD applies a later commit of main. The run observes one commit.
- A caller outcome from a sync state or a health state that Argo CD reports.
- Latency, throughput, capacity, or availability.
- That the acquisition hook downloads the model into an empty claim.
- That a second request is answered. The run sends one.
- That no model download happened in the run. No step observes it.
- That the verdicts are independent. The session that drove the run applied the rules.
