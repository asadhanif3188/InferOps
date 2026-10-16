# Q3 characterization `q3-1`: REFUSED on the environment

Status: **`REFUSED`. The precondition `environment-qualified` (Q3-AC5) was not held: the
environment identity of the capacity reading has the digest
`sha256:ac3a1022e86facb519bb0820b57d7a7fb32c0c6ea1011a59e88b8c1aa4efd087`, and
[`q1-1`](../../../v2-q1/runs/q1-1/result.md) states
`sha256:23db293eeac80960eb77eac228188ceb5ac2cd1c11a925636aa61f1318866461`. The driver
started no caller. The record states no G, and no Q4 bound record was built.** The six
other preconditions were held. The seven rules of the measurement were not observed,
because no caller ran. The characterization is kept, as [freeze revision 1](../../freeze-r1.v1alpha1.json)
requires of each one.

| Property | Value |
|---|---|
| Record | [`record.v1alpha1.json`](record.v1alpha1.json), built by `tools/caller_characterization` |
| Header | [`run.json`](run.json) |
| Transcript | [`transcript.txt`](transcript.txt): the phases `up`, `characterize`, and `down`, and the operator reads after them, with the absolute path of the host replaced by `<repository>` |
| Freeze record | `docs/proof/experiments/v2-q3/freeze-r1.v1alpha1.json`, SHA-256 `b8c5f7acf2bde60d82f0909eb02fc2f01572e214351ea8b4d6e56043543d8c82` |
| Executing commit | `0307f7f738069fd22488b92d78023a8bb03f5896`, for the phase `up` and the characterization |
| Desired revision | `b0bdccad4cce78ea532c206ecb4cbb99e4f4c420`, the remote main |
| Release | `local-docker-desktop/support-assistant`, identifier `b5457f49092c578496738973a8786a95428517e7ddf755303b4f6842dcb8c9db`, the one of `q1-1` |
| Environment | `sha256:ac3a1022e86facb519bb0820b57d7a7fb32c0c6ea1011a59e88b8c1aa4efd087`: Kubernetes `v1.36.1`, one node `desktop-control-plane`, 12 CPUs, 10,429,972,480 bytes of memory. Not the environment of `q1-1` |
| API image | `sha256:de5173b2c143f6f80ecec4fab34b3d7be67e1713a604ba970bb40c07c4257953`, the manifest-list digest that the phase `up` declared, a fourth manifest-list digest for the inputs that the Q1 record pins, after those of `q1-1`, of the attempt under Q2 revision 1, and of `q2-1`. The build printed the image manifest `bba83fa7…` and the config `cd65ca24…`, as [the builds of Q2](../../../v2-q2/runs/q2-1/result.md) did |

## What ran

All instants are UTC, on 2026-10-16. The host instants are those that the driver printed.

1. **The phase `up`** of the Q1 driver ran without a change, from 07:26:17 to 07:33:55,
   with the work directory `q3run-1`. Both capacity readings were `ACCEPTED`; the
   second, which the characterization reads, was collected at 07:32:50. The controller
   reported the Application `Synced` and `Healthy` at the revision `b0bdcca`, with 2 API
   pods and 2 runtime pods Running and Ready.
2. **The characterization `q3-1`** started at 07:34:10.644. The working tree was clean,
   the delivery paths equaled the desired revision, and the freeze tool listed no
   changed material file of the Q3 or the Q1 record. The driver resolved the provenance,
   read the Deployments and the pods, and asked the tool for the preconditions.
   `environment-qualified` was not held, so the driver started no caller and no watch,
   wrote the header at 07:34:24.556, and kept the `REFUSED` record.
3. **The phase `down`** of the Q1 driver removed the Application, the controller, and the
   prerequisite layer, and ended at 07:36:23. The namespaces and the custom resource
   definitions after it were those before the phase `up`.

## Why the environment differs

The environment identity that Q1 computes holds, among other values, the memory that the
container engine reports and the memory that the node allocates. Each is a number of
bytes, and the digest compares them exactly.

| Reading | Container engine memory | Node allocatable memory |
|---|---|---|
| `q1-1`, 2026-10-15 (and `q2-1`, the same day) | 10,429,960,192 B | 10,429,960,192 B |
| `q3-1`, 2026-10-16, capacity reading of the phase `up` | 10,429,972,480 B | 10,429,972,480 B |

Every other value of the identity is the same: the provider, the Kubernetes version, the
node name, its kubelet version, 12 CPUs and 12,000 m, and 110 pods. The difference is
12,288 bytes.

**The virtual machine of the engine had booted again.** After the refusal, between the
end of the characterization at 07:34:26 and the start of the phase `down` at 07:35:15, the
operator read the uptime of the node container: 4,574 s, so the machine had booted at about 06:19
on 2026-10-16, after `q2-1`. These reads were made by hand and are in the last section of
the transcript; they are not part of the record.

**The host owner then authorized one attempt to restore the environment, and it did not
restore it.** The attempt was made to find whether the environment of `q1-1` comes back,
before any further characterization; no identifier was spent:

- `docker desktop restart` restarted the engine and not its virtual machine: the uptime
  grew to 5,580 s, and the memory stayed at 10,429,972,480 B.
- `wsl --shutdown` stopped the virtual machine, and the engine started it again: the
  uptime was 9 s, and the memory was **10,429,956,096 B**, a third figure.

So the memory that this host reports changed at each of the two boots of its virtual
machine that were observed, and the environment digest of `q1-1` did not hold across
either. No phase `up` and no further
characterization was run after the attempt.

## What this record establishes

- At C2, on one provider: the frozen driver and the tool refused a characterization whose
  capacity reading is not of the environment of `q1-1`, before any caller was started,
  and kept the refusal.
- The phase `up` at `0307f7f` resolved the release of `q1-1`, and the Deployments ran the
  declared API image and the runtime image of `q1-1` at 2 Ready replicas each.

## What it does not establish

- Any value of G, any latency, any gap, or any count of caller requests. No caller ran.
- Any Q4 bound. The Q4 tool states bounds only from a `CHARACTERIZED` Q3 record.
- That the release does not serve, or that a characterization in this environment would
  be refused by any rule other than `environment-qualified`.
- Why the kernel reports another memory figure after a boot. The reads show that it
  does; they do not show the cause.

## Not committed

- `capacity/pods.json`, the capacity gate's read of every pod of the cluster, which holds
  container paths under a home directory in the controller's pods. Its SHA-256 with CRLF
  read as LF is `14475254fa76461b8fc169b19141519b2438aa512ef76d3477ae4001ff9bcb03`. The
  record does not read it.
