{{/*
Names, labels, and the derived environment.

Two things here are load-bearing rather than conventional.

The adapter selection is derived from `.Values.profile` in exactly one place --
`inferops-llm.derivedEnv` -- and there is no values path that reaches
`INFEROPS_SERVING_ADAPTER` any other way. Every free-form values map that reaches
a rendered object -- `extraEnv`, `secretRefs`, `commonLabels`, `commonAnnotations`,
and the per-object annotation maps -- is checked against the derived names in
`inferops-llm.validate` and **refused** rather than merged, so a real release
cannot acquire a `mock` identity, or the reverse, through an override that happens
to be applied last. That refusal covers the labels as well as the environment,
because the label is the identity a dashboard, a selector, and a scoped teardown
sweep all read.

The label set carries `inferops.io/lifecycle: release`. The ownership document
records that a scoped teardown sweeping `app.kubernetes.io/part-of=inferops`
across `inferops-` namespaces would reach Terraform-owned prerequisites, and
that the resolution is a second label distinguishing the two. This is the
release half of it. The prerequisite half is Terraform's and is now written --
`infra/terraform/` sets `inferops.io/lifecycle: prerequisite` on the namespace
and the model cache claim -- but nothing has applied it, and the sweep itself
still does not exclude that marker, so it must stay bound to the smoke namespace
it is bound to today.
*/}}

{{- define "inferops-llm.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "inferops-llm.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- $name := default .Chart.Name .Values.nameOverride -}}
{{- if contains $name .Release.Name -}}
{{- .Release.Name | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name $name | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- define "inferops-llm.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
The label keys this chart derives, and the annotation keys, each as a list.

They exist so that `inferops-llm.validate` can refuse a `commonLabels` or
`commonAnnotations` entry that collides with one, rather than appending it and
producing a mapping with the same key twice. A duplicate key is not a rendering
curiosity: every parser this project's output passes through resolves it
last-one-wins, so an appended `inferops.io/profile` is the value a reader, a
selector, and a teardown sweep all see.
*/}}
{{- define "inferops-llm.derivedLabelKeys" -}}
- helm.sh/chart
- app.kubernetes.io/name
- app.kubernetes.io/instance
- app.kubernetes.io/version
- app.kubernetes.io/managed-by
- app.kubernetes.io/part-of
- app.kubernetes.io/component
- inferops.io/lifecycle
- inferops.io/profile
- inferops.io/owner
- inferops.io/workload
{{- end -}}

{{- define "inferops-llm.derivedAnnotationKeys" -}}
- inferops.io/tenant
- inferops.io/cost-center
- inferops.io/configuration-checksum
- prometheus.io/scrape
- prometheus.io/port
- prometheus.io/path
{{- end -}}

{{/*
Every object this release installs carries these. `part-of` is the ADR 0001 D5
isolation label; `lifecycle` is the release marker described above.
*/}}
{{- define "inferops-llm.labels" -}}
helm.sh/chart: {{ include "inferops-llm.chart" . }}
app.kubernetes.io/name: {{ include "inferops-llm.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
app.kubernetes.io/part-of: inferops
inferops.io/lifecycle: release
inferops.io/profile: {{ .Values.profile }}
{{- if .Values.ownership.owner }}
inferops.io/owner: {{ .Values.ownership.owner }}
{{- end }}
{{- if .Values.ownership.workloadId }}
inferops.io/workload: {{ .Values.ownership.workloadId }}
{{- end }}
{{- with .Values.commonLabels }}
{{ toYaml . }}
{{- end }}
{{- end -}}

{{/*
Attribution that must not become a selector. The telemetry redaction rules keep
a tenant identifier out of anything a query groups by, and a label is exactly
that, so tenant and cost centre are annotations.
*/}}
{{- define "inferops-llm.annotations" -}}
{{- if .Values.ownership.tenant }}
inferops.io/tenant: {{ .Values.ownership.tenant | quote }}
{{- end }}
{{- if .Values.ownership.costCenter }}
inferops.io/cost-center: {{ .Values.ownership.costCenter | quote }}
{{- end }}
{{- with .Values.commonAnnotations }}
{{ toYaml . }}
{{- end }}
{{- end -}}

{{- define "inferops-llm.api.selectorLabels" -}}
app.kubernetes.io/name: {{ include "inferops-llm.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: platform-api
{{- end -}}

{{- define "inferops-llm.runtime.selectorLabels" -}}
app.kubernetes.io/name: {{ include "inferops-llm.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: serving-runtime
{{- end -}}

{{/*
Every pod this release puts in the namespace, hook included.

It is the selector the default-deny policy uses, and it is deliberately the pair
without a component: a policy that named the components would stop selecting the
day a component is added, and the pod that stopped being selected would be the
new one nobody had written a rule for. Naming the release instead means a new
pod arrives denied and has to be opened deliberately.

The `helm test` pod carries these labels too, which is why it is inside the
default-deny and has a rule of its own rather than an exemption.
*/}}
{{- define "inferops-llm.releaseSelectorLabels" -}}
app.kubernetes.io/name: {{ include "inferops-llm.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
{{- end -}}

{{- define "inferops-llm.acquisition.selectorLabels" -}}
app.kubernetes.io/name: {{ include "inferops-llm.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: model-acquisition
{{- end -}}

{{- define "inferops-llm.test.selectorLabels" -}}
app.kubernetes.io/name: {{ include "inferops-llm.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: release-test
{{- end -}}

{{/*
The one egress rule two policies both need, written once.

Every pod here that reaches anything reaches it by Service name, so a policy
that denies egress and forgets DNS denies everything by producing a resolution
failure -- which surfaces as a connection error rather than as a policy error,
and is the failure mode that makes people give up on network policy.

The cluster's resolver is addressed by label rather than by address. The
namespace selector uses `kubernetes.io/metadata.name`, which the API server sets
on every namespace itself, so it is not a label somebody has to remember to
apply. Both are values rather than constants because the resolver's labels are a
property of the cluster's add-ons and not of this chart, and a cluster whose
resolver is labelled differently needs to say so rather than to patch a
template.

Both protocols. UDP is the common path and TCP is what a resolver falls back to
for a large answer; allowing only UDP produces an intermittent failure that
looks like anything except a network policy.
*/}}
{{- define "inferops-llm.dnsEgressRule" -}}
- to:
    - namespaceSelector:
        matchLabels:
          {{- toYaml .Values.security.networkPolicy.dns.namespaceSelector | nindent 10 }}
      podSelector:
        matchLabels:
          {{- toYaml .Values.security.networkPolicy.dns.podSelector | nindent 10 }}
  ports:
    - port: {{ .Values.security.networkPolicy.dns.port }}
      protocol: UDP
    - port: {{ .Values.security.networkPolicy.dns.port }}
      protocol: TCP
{{- end -}}

{{/*
The two workload identities, and why there are two rather than one.

The API and the serving runtime are separate workloads with separate failure
modes, and until V1-S3-004 they shared one ServiceAccount. Nothing was bound to
it, so the sharing cost nothing on the day it was written -- which is exactly
the shape of the problem: **the first RoleBinding somebody adds for one of them
grants it to the other**, and it grants it to whichever pod the reviewer was not
thinking about. Splitting the identity now is cheap; splitting it after a
binding exists means auditing what the binding reached.

What this is **not** is an isolation property. Neither account is granted
anything -- this chart renders no Role and no RoleBinding, and no pod mounts a
token -- so today the two names differ and the privilege of each is the same
nothing. The value is entirely in what a future grant cannot accidentally reach,
and stating it that way is the point.

`create: false` points both at `default`, which is the namespace's own account
and not one this release owns. That is a deliberate escape hatch for a cluster
whose accounts are provisioned elsewhere, and it is the one setting here that
gives up the separation above.
*/}}
{{- define "inferops-llm.api.serviceAccountName" -}}
{{- if .Values.security.serviceAccount.create -}}
{{- default (printf "%s-api" (include "inferops-llm.fullname" .)) .Values.security.serviceAccount.api.name -}}
{{- else -}}
{{- default "default" .Values.security.serviceAccount.api.name -}}
{{- end -}}
{{- end -}}

{{- define "inferops-llm.runtime.serviceAccountName" -}}
{{- if .Values.security.serviceAccount.create -}}
{{- default (printf "%s-runtime" (include "inferops-llm.fullname" .)) .Values.security.serviceAccount.runtime.name -}}
{{- else -}}
{{- default "default" .Values.security.serviceAccount.runtime.name -}}
{{- end -}}
{{- end -}}

{{/*
The model acquisition job's own account.

It exists because the job is a `pre-install` hook and the ServiceAccounts above
are not. Helm applies a phase's hooks before the release manifest, so at the
moment the hook Job is created the runtime's account has not been rendered yet,
and the API server refuses the Job outright: `error looking up service account
... not found`. The Job never schedules, the hook times out, and the install
fails with `failed pre-install: timed out waiting for the condition` -- which
names the symptom and not the cause. V1-S3-011 found this by installing the
chart into a real cluster for the first time.

So the account a hook names has to be created by the same phase that creates the
hook. This one is, at a lower weight, and it is removed with the hook rather than
left behind: the hook owns it for the length of the hook and nothing else.

When the operator turns account creation off, this falls back to whatever the
runtime resolves to -- their own account, or `default` -- because in that case
nothing here is creating an account for the hook to wait for.
*/}}
{{- define "inferops-llm.acquisition.serviceAccountName" -}}
{{- if .Values.security.serviceAccount.create -}}
{{- printf "%s-model-acquisition" (include "inferops-llm.fullname" .) | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- include "inferops-llm.runtime.serviceAccountName" . -}}
{{- end -}}
{{- end -}}

{{- define "inferops-llm.configMapName" -}}
{{- printf "%s-configuration" (include "inferops-llm.fullname" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "inferops-llm.runtimeServiceName" -}}
{{- printf "%s-runtime" (include "inferops-llm.fullname" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "inferops-llm.runtimeEndpoint" -}}
{{- printf "http://%s:%d" (include "inferops-llm.runtimeServiceName" .) (int .Values.runtime.service.port) -}}
{{- end -}}

{{/*
The serving capability, derived from the profile and configurable nowhere.

`inferops-native-serving` and `inferops-mock-serving` are disjoint on purpose,
and the adapter packages hold them as constants rather than settings for the
reason this mapping repeats: an adapter that could be configured to name itself
the other kind is the failure the closed vocabulary exists to prevent.
*/}}
{{- define "inferops-llm.capabilityId" -}}
{{- if eq .Values.profile "real" -}}
inferops-native-serving
{{- else -}}
inferops-mock-serving
{{- end -}}
{{- end -}}

{{/*
The scrape annotations, when `telemetry.scrapeAnnotations` asks for them.

They are the one form of scrape configuration that is a field on the workload
rather than a resource beside it, which is why they are here while
`telemetry-scrape-configuration` stays deferred to V1-S3-007: this says where
metrics are, and it does not decide what reads them or where they go. Nothing in
this project reads them today.

They are refused in `commonAnnotations` and in every per-object map whether or
not they are switched on, because a hand-written `prometheus.io/port` beside a
derived one is the duplicate-key hazard the other guards exist for.
*/}}
{{- define "inferops-llm.scrapeAnnotations" -}}
{{- $root := .context -}}
{{- if and $root.Values.telemetry.enabled $root.Values.telemetry.scrapeAnnotations }}
prometheus.io/scrape: "true"
prometheus.io/port: {{ .port | quote }}
prometheus.io/path: {{ $root.Values.telemetry.metricsPath | quote }}
{{- end }}
{{- end -}}

{{/*
How many consecutive startup-probe failures fit inside a budget.

Stated as a budget in the values file and converted here, so that raising the
budget cannot leave the count behind. Integer arithmetic, rounding up: a
threshold rounded down is a budget the kubelet does not actually give.
*/}}
{{- define "inferops-llm.startupFailureThreshold" -}}
{{- $period := mul (int .periodSeconds) 1000 -}}
{{- div (add (int .budgetMs) (sub $period 1)) $period -}}
{{- end -}}

{{/*
The API's three probes.

The mapping is the one docs/serving/inference-api-surface.v1alpha1.json
publishes rather than a choice made here: `/health/live` answers while the model
is loading and while the API is draining, and `/health/ready` is the conjunction
of the API accepting work and the selected adapter reporting itself able. So
liveness asks the first and readiness the second, and neither is ever pointed at
the other's path.

Until the startup probe passes the kubelet runs neither of the other two. That
is what makes a slow start a slow start rather than a restart loop.
*/}}
{{- define "inferops-llm.api.probes" -}}
{{- if .Values.api.probes.enabled }}
startupProbe:
  httpGet:
    path: {{ .Values.api.livenessPath }}
    port: http
  periodSeconds: {{ .Values.api.probes.startup.periodSeconds }}
  timeoutSeconds: {{ .Values.api.probes.startup.timeoutSeconds }}
  failureThreshold: {{ include "inferops-llm.startupFailureThreshold" (dict "budgetMs" .Values.api.probes.startup.budgetMs "periodSeconds" .Values.api.probes.startup.periodSeconds) }}
readinessProbe:
  httpGet:
    path: {{ .Values.api.readinessPath }}
    port: http
  periodSeconds: {{ .Values.api.probes.readiness.periodSeconds }}
  timeoutSeconds: {{ .Values.api.probes.readiness.timeoutSeconds }}
  failureThreshold: {{ .Values.api.probes.readiness.failureThreshold }}
livenessProbe:
  httpGet:
    path: {{ .Values.api.livenessPath }}
    port: http
  periodSeconds: {{ .Values.api.probes.liveness.periodSeconds }}
  timeoutSeconds: {{ .Values.api.probes.liveness.timeoutSeconds }}
  failureThreshold: {{ .Values.api.probes.liveness.failureThreshold }}
{{- end }}
{{- end -}}

{{/*
The runtime's three probes, and the one asymmetry in this chart.

**Liveness is a TCP connect and readiness is an HTTP GET, and they are not
interchangeable.** `llama-server` answers `/health` with 503 for the whole of a
model load: correct readiness behaviour, and fatal as a liveness answer. The
V1-S2-007 observation recorded 2,753 samples across six starts in which a healthy
process was loading a model and an HTTP liveness probe would have been failing.
docs/serving/runtime-profile.local.v1.json publishes `health.liveness.kind` as
`tcp` for that reason, and a test compares this template against it.

The socket is accepted several seconds before the model is loaded, which is why
the TCP probe cannot serve as the startup gate either. The startup probe is the
HTTP one, and its budget is the measured load time with margin.
*/}}
{{- define "inferops-llm.runtime.probes" -}}
{{- if .Values.runtime.probes.enabled }}
startupProbe:
  httpGet:
    path: {{ .Values.runtime.healthPath }}
    port: http
  periodSeconds: {{ .Values.runtime.probes.startup.periodSeconds }}
  timeoutSeconds: {{ .Values.runtime.probes.startup.timeoutSeconds }}
  failureThreshold: {{ include "inferops-llm.startupFailureThreshold" (dict "budgetMs" .Values.runtime.probes.startup.budgetMs "periodSeconds" .Values.runtime.probes.startup.periodSeconds) }}
readinessProbe:
  httpGet:
    path: {{ .Values.runtime.healthPath }}
    port: http
  periodSeconds: {{ .Values.runtime.probes.readiness.periodSeconds }}
  timeoutSeconds: {{ .Values.runtime.probes.readiness.timeoutSeconds }}
  failureThreshold: {{ .Values.runtime.probes.readiness.failureThreshold }}
livenessProbe:
  tcpSocket:
    port: http
  periodSeconds: {{ .Values.runtime.probes.liveness.periodSeconds }}
  timeoutSeconds: {{ .Values.runtime.probes.liveness.timeoutSeconds }}
  failureThreshold: {{ .Values.runtime.probes.liveness.failureThreshold }}
{{- end }}
{{- end -}}

{{/*
The pause between SIGTERM and the process being asked to stop.

A `sleep` action rather than an `exec`: an `exec` needs a shell inside the image,
and no InferOps image is published to be asked whether it has one. Kubernetes has
accepted a sleep action natively since 1.30 and this chart's floor is 1.34.

It exists because endpoint removal is asynchronous. The kubelet sends SIGTERM and
the EndpointSlice update races it, so without a pause a pod can be handed work
after it has stopped accepting any.
*/}}
{{- define "inferops-llm.preStop" -}}
{{- if gt (int .preStopSleepSeconds) 0 }}
lifecycle:
  preStop:
    sleep:
      seconds: {{ int .preStopSleepSeconds }}
{{- end }}
{{- end -}}

{{- define "inferops-llm.tests.image" -}}
{{- printf "%s@%s" .Values.tests.image.repository .Values.tests.image.digest -}}
{{- end -}}

{{- define "inferops-llm.api.image" -}}
{{- printf "%s@%s" .Values.api.image.repository .Values.api.image.digest -}}
{{- end -}}

{{- define "inferops-llm.runtime.image" -}}
{{- printf "%s@%s" .Values.runtime.image.repository .Values.runtime.image.digest -}}
{{- end -}}

{{/*
The pod-level part of the six security properties every workload manifest in
this repository carries.
*/}}
{{- define "inferops-llm.podSecurityContext" -}}
runAsNonRoot: true
runAsUser: {{ .Values.security.runAsUser }}
runAsGroup: {{ .Values.security.runAsGroup }}
{{- if .Values.security.fsGroup }}
fsGroup: {{ .Values.security.fsGroup }}
{{- end }}
seccompProfile:
  type: RuntimeDefault
{{- end -}}

{{- define "inferops-llm.containerSecurityContext" -}}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
capabilities:
  drop:
    - ALL
{{- end -}}

{{/*
The configuration both workloads read, as a single ConfigMap body.

This is the `runtime-configuration` row of the ownership inventory. It holds no
secret value: secret material is referenced by name through `security.secretRefs`
and reaches a container as an `env[].valueFrom.secretKeyRef`, never as a rendered
literal.

`INFEROPS_SERVING_ADAPTER` is written here and nowhere else, from `profile` and
from nothing else. That is the whole of the mock and real selection.
*/}}
{{- define "inferops-llm.derivedEnv" -}}
INFEROPS_SERVING_ADAPTER: {{ .Values.profile | quote }}
INFEROPS_REQUEST_TIMEOUT_MS: {{ .Values.api.requestTimeoutMs | quote }}
INFEROPS_MAX_OUTPUT_TOKENS: {{ .Values.api.maxOutputTokens | quote }}
INFEROPS_DRAIN_TIMEOUT_MS: {{ .Values.api.drainTimeoutMs | quote }}
INFEROPS_DEPLOYMENT_ENVIRONMENT: {{ .Values.telemetry.deploymentEnvironment | quote }}
INFEROPS_CAPABILITY_ID: {{ include "inferops-llm.capabilityId" . | quote }}
INFEROPS_RELEASE_ID: {{ .Release.Name | quote }}
INFEROPS_SERVICE_VERSION: {{ .Values.telemetry.serviceVersion | quote }}
INFEROPS_WORKLOAD_ID: {{ .Values.ownership.workloadId | quote }}
INFEROPS_WORKLOAD_VERSION: {{ .Values.ownership.workloadVersion | quote }}
INFEROPS_OWNER_ID: {{ .Values.ownership.owner | quote }}
{{- if eq .Values.profile "real" }}
INFEROPS_MODEL_IDENTIFIER: {{ .Values.model.identifier | quote }}
INFEROPS_MODEL_REVISION: {{ .Values.model.revision | quote }}
INFEROPS_RUNTIME_IMAGE_DIGEST: {{ .Values.runtime.image.digest | quote }}
INFEROPS_LLAMA_SERVER_ENDPOINT: {{ include "inferops-llm.runtimeEndpoint" . | quote }}
INFEROPS_LLAMA_SERVER_MODEL_PATH: {{ include "inferops-llm.model.containerPath" . | quote }}
INFEROPS_LLAMA_SERVER_MODEL_ALIAS: {{ .Values.model.alias | quote }}
INFEROPS_LLAMA_SERVER_CONTEXT_SIZE: {{ .Values.runtime.contextSizeTokens | quote }}
INFEROPS_LLAMA_SERVER_THREADS: {{ .Values.runtime.threads | quote }}
INFEROPS_LLAMA_SERVER_STARTUP_BUDGET_MS: {{ .Values.runtime.startupBudgetMs | quote }}
INFEROPS_LLAMA_SERVER_METRICS_ENABLED: {{ .Values.telemetry.enabled | quote }}
{{- else }}
INFEROPS_MODEL_IDENTIFIER: {{ .Values.model.identifier | quote }}
{{- end }}
{{- end -}}

{{/*
The identity a pod can only learn from the API server, supplied through the
downward API rather than baked into configuration.
*/}}
{{- define "inferops-llm.downwardEnv" -}}
- name: INFEROPS_POD_NAME
  valueFrom:
    fieldRef:
      fieldPath: metadata.name
{{- end -}}

{{/*
Secret material, by reference. The chart names a Secret and a key and renders no
value; what is behind the reference is the workload owner's and is never read
here.
*/}}
{{- define "inferops-llm.secretEnv" -}}
{{- range .Values.security.secretRefs }}
- name: {{ .name }}
  valueFrom:
    secretKeyRef:
      name: {{ .secretName }}
      key: {{ .key }}
{{- end }}
{{- end -}}

{{/*
The model artifact: where it lives inside the claim, and where the container
sees it.

Both are derived, and neither is settable, because the pair is what makes the
declared revision decide which bytes are read.

`cacheSubPath` is `<repository>/<revision>`, with the repository's separator
replaced the way the workspace cache already replaces it -- so the claim holds
the same layout `docs/serving/model-source.v1.json` publishes for the checkout,
and one artifact record describes both. Mounting the claim *at* that
subdirectory rather than at its root is the whole mechanism: a release declaring
one revision cannot see another revision's directory at all, so cache reuse
cannot bypass the revision it claims to be reusing. A values file that could
write this path would put that back.

`containerPath` is the mount directory and the pinned file name. It is what the
runtime is given as `--model` and what the integrity check reads, and it is one
expression so that those two cannot be different files.
*/}}
{{- define "inferops-llm.model.cacheSubPath" -}}
{{- printf "%s/%s" (replace "/" "--" .Values.model.artifact.repository) .Values.model.revision -}}
{{- end -}}

{{- define "inferops-llm.model.containerPath" -}}
{{- printf "%s/%s" (trimSuffix "/" .Values.model.cache.mountPath) .Values.model.artifact.fileName -}}
{{- end -}}

{{- define "inferops-llm.model.integrityImage" -}}
{{- printf "%s@%s" .Values.model.integrity.image.repository .Values.model.integrity.image.digest -}}
{{- end -}}

{{/*
The read-only mount of the Terraform-owned claim, written once and used by both
containers that need it.

`readOnly` is stated on the mount and on the volume, and `subPath` selects the
revision directory. Two containers referring to one definition is what stops the
init container verifying one path while the runtime loads another -- which would
be an integrity check that proved something about a file nobody served.
*/}}
{{- define "inferops-llm.model.volumeMount" -}}
- name: model-cache
  mountPath: {{ .Values.model.cache.mountPath | quote }}
  readOnly: true
  subPath: {{ include "inferops-llm.model.cacheSubPath" . | quote }}
{{- end -}}

{{/*
What the init container runs before `llama-server` is started.

It is deliberately a plain POSIX script and not a program: BusyBox is the only
thing in the pod that can read the artifact before the runtime does, and adding
a program would mean adding an image to build one into.

`$(...)` appears in it. Kubernetes performs its own `$(VAR)` substitution over a
container command and leaves an unresolved reference exactly as written, so the
shell -- not the kubelet -- is what evaluates these.

**Every value this script carries reaches a shell.** Independent review of this
change found that `model.cache.mountPath` did not: its pattern forbade only
whitespace, so a values file could close the assignment below and append its own
commands -- and the first of them could be `exit 0`, which is an integrity check
that reports success without reading anything. What refuses that now is
`values.schema.json`, where `mountPath` joined `artifact.repository`,
`artifact.fileName`, `revision`, and `sha256` as a closed character class. The
single quotes on the assignment are the second line rather than the first: with
the pattern in place nothing can reach them, and they are here because the cost
of being wrong about that is a check that passes by not running.

The byte count comes from `stat` and not from `wc -c`, and the difference is not
style. **BusyBox's `wc -c` reads the stream**: measured in the pinned image at
0.87 s for 256 MiB against 0.00 s for `stat -c %s`. Written with `wc`, the
default mode read the artifact twice -- once to count it and once to hash it --
which on the bind-mount throughput this project has measured would add minutes
to every pod start, and the `size` mode would have been a full read described as
a cheap one.

The three modes differ only in how much they read. None of them decides which
file is read: that is the mount, and it is revision-scoped whatever this says.
*/}}
{{- define "inferops-llm.model.verifyScript" -}}
{{- $artifact := include "inferops-llm.model.containerPath" . -}}
set -eu
artifact='{{ $artifact }}'
if [ ! -f "$artifact" ]; then
  echo "REFUSED: the mounted model cache holds no artifact for the declared revision" >&2
  exit 1
fi
{{- if eq .Values.model.integrity.verifyOnStart "none" }}
echo "model artifact present; content not verified (model.integrity.verifyOnStart=none)"
{{- else }}
present=$(stat -c %s "$artifact")
if [ "$present" != "{{ printf "%d" (int64 .Values.model.artifact.sizeBytes) }}" ]; then
  echo "REFUSED: the mounted model artifact does not match the pinned byte count" >&2
  exit 1
fi
{{- if eq .Values.model.integrity.verifyOnStart "sha256" }}
echo "{{ trimPrefix "sha256:" .Values.model.artifact.sha256 }}  $artifact" | sha256sum -c -
echo "model artifact verified: byte count and SHA-256"
{{- else }}
echo "model artifact verified: byte count only (model.integrity.verifyOnStart=size)"
{{- end }}
{{- end }}
{{- end -}}

{{/*
The init container itself.

It runs on every pod start, which is what makes it a restart property rather
than an install-time one: a pod that comes back finds the artifact where the
previous one left it, and re-establishes that it is the artifact this release
declared before anything serves from it. A verification performed once at
install time would say nothing about the pod that replaced the one it ran in.

It carries the same security context and the same read-only mount as the
runtime, and it is given no environment at all: everything it compares against
is rendered into the script from a pinned value.
*/}}
{{- define "inferops-llm.model.verifyInitContainer" -}}
- name: verify-model
  image: {{ include "inferops-llm.model.integrityImage" . | quote }}
  imagePullPolicy: {{ .Values.model.integrity.image.pullPolicy }}
  command:
    - /bin/sh
    - -c
    - |
      {{- include "inferops-llm.model.verifyScript" . | nindent 6 }}
  securityContext:
    {{- include "inferops-llm.containerSecurityContext" . | nindent 4 }}
  resources:
    {{- toYaml .Values.model.integrity.resources | nindent 4 }}
  volumeMounts:
    {{- include "inferops-llm.model.volumeMount" . | nindent 4 }}
{{- end -}}

{{/*
The claim, mounted writable at its root, for the one object allowed to write it.

Deliberately not `inferops-llm.model.volumeMount`. That one is `readOnly: true`
with a `subPath` selecting the revision directory, and both properties are load
bearing for a serving replica: it may not write, and it may not see another
revision's bytes. The acquisition job is the opposite case on both counts. It has
to write, and it has to be able to create the revision directory -- which a
`subPath` mount cannot do, because `subPath` resolves at mount time and a
directory that does not exist yet is not a directory the kubelet will mount.

So the job mounts the claim at its root and derives the same revision path the
serving mount selects, from the same helper. One expression, two mounts: a job
that wrote one directory while the runtime read another would be an acquisition
that filled a cache nobody served from.
*/}}
{{- define "inferops-llm.model.acquisitionVolumeMount" -}}
- name: model-cache
  mountPath: "/claim"
{{- end -}}

{{- define "inferops-llm.model.acquisitionImage" -}}
{{- if eq .Values.model.acquisition.source "seed-image" -}}
{{- printf "%s@%s" .Values.model.acquisition.seedImage.repository .Values.model.acquisition.seedImage.digest -}}
{{- else -}}
{{- include "inferops-llm.model.integrityImage" . -}}
{{- end -}}
{{- end -}}

{{/*
What the acquisition job runs.

Four properties, and each one is a way an acquisition can look finished and not
be.

**A cache hit is a verified cache hit.** The job exits early only after the
artifact has been read and its byte count and SHA-256 compared. A file of the
right name and the wrong content is not reuse, it is corruption that survived --
so it is removed and acquired again rather than trusted. This is what makes the
job safe to run before every install and upgrade.

**Nothing incomplete is ever named like something complete.** The transfer writes
`<file>.part` and renames only after verification passes. A pod evicted halfway
through leaves a `.part` the next run resumes or discards; it can never leave a
short file under the real name, which the runtime would then mount, hash, and
refuse -- correctly, but only after an install had reported success.

**The hash is checked before the bytes are used, not after they are trusted.**
The download transport is not certificate-validated: BusyBox `wget` says so
itself and docs/security/security-baseline.v1alpha1.json records it. The content
hash is therefore the whole of the defence, and it is compared against the pin
this release was rendered with rather than against anything the transfer
supplied.

**Resumption is a count, not a retry loop.** A single streamed transfer of this
artifact was measured not to survive, which is the finding that made the Sprint 0
downloader resumable. `wget -c` continues an existing `.part`, and the attempt
budget bounds it.

**A replacement is staged, never a removal followed by a hope.** An artifact that
is present and does not match the pins used to be deleted here, before anything
had been acquired to put in its place. The first real execution of the
V1-S3-008 upgrade/rollback experiment is what showed the cost of that ordering,
and it is worth stating plainly because nothing short of a run could have found
it: that experiment injects a deliberately wrong `model.artifact.sizeBytes`, the
same value renders into *this* script as well as into the serving runtime's
verification, and so the hook dutifully discarded a 1.83 GB artifact it then
could not replace -- leaving the Terraform-owned claim empty and the rollback
with nothing to roll back to. The claim is a prerequisite this release is a guest
in. A candidate that cannot be acquired must leave it exactly as it was found, so
the replacement is staged beside the artifact and moved over it only once it has
verified.

The cost is disk: for the length of one acquisition the claim holds the old
artifact and the new one. That is the right trade against emptying a claim
nothing else can refill.

`$(...)` appears below and the shell evaluates it: Kubernetes substitutes only
`$(VAR)` references it recognises and leaves the rest exactly as written. Every
interpolated value reaches that shell, which is why `artifact.repository`,
`artifact.fileName`, `revision`, `sha256` and `seedImage.artifactPath` are all
closed character classes in values.schema.json.
*/}}
{{- define "inferops-llm.model.acquisitionScript" -}}
{{- $dir := printf "/claim/%s" (include "inferops-llm.model.cacheSubPath" .) -}}
set -eu
dir='{{ $dir }}'
artifact="$dir/{{ .Values.model.artifact.fileName }}"
want_bytes='{{ printf "%d" (int64 .Values.model.artifact.sizeBytes) }}'
want_sha='{{ trimPrefix "sha256:" .Values.model.artifact.sha256 }}'
#
verify() {
  [ -f "$1" ] || return 1
  [ "$(stat -c %s "$1")" = "$want_bytes" ] || return 1
  echo "$want_sha  $1" | sha256sum -c - >/dev/null 2>&1 || return 1
  return 0
}
#
mkdir -p "$dir"
#
if verify "$artifact"; then
  echo "model artifact already present and verified; nothing to acquire"
  exit 0
fi
#
if [ -e "$artifact" ]; then
  echo "the claim holds an artifact that does not match the pinned byte count and hash; it will be replaced only by bytes that verify" >&2
fi
{{- if eq .Values.model.acquisition.source "seed-image" }}
seed='{{ .Values.model.acquisition.seedImage.artifactPath }}/{{ .Values.model.artifact.fileName }}'
if [ ! -f "$seed" ]; then
  echo "REFUSED: the seed image carries no artifact at $seed" >&2
  exit 1
fi
if ! cp "$seed" "$artifact.part"; then
  echo "REFUSED: the seed artifact could not be staged onto the claim" >&2
  rm -f "$artifact.part"
  exit 1
fi
{{- else }}
attempt=1
until wget -c -q -O "$artifact.part" '{{ .Values.model.artifact.sourceUrl }}'; do
  attempt=$((attempt + 1))
  if [ "$attempt" -gt {{ int .Values.model.acquisition.download.maxAttempts }} ]; then
    echo "REFUSED: the transfer did not complete within its attempt budget" >&2
    rm -f "$artifact.part"
    exit 1
  fi
  echo "transfer interrupted; resuming (attempt $attempt)"
  # A pause, because the failures worth resuming through are the ones that
  # resolve on their own. `wget` fails in milliseconds on a refused connection or
  # an unresolvable name, so a loop without this spends a sixty-attempt budget
  # inside a second and reports a transient outage as a permanent one.
  sleep {{ int .Values.model.acquisition.download.retryPauseSeconds }}
done
{{- end }}
#
if ! verify "$artifact.part"; then
  echo "REFUSED: the acquired bytes do not match the pinned byte count and SHA-256" >&2
  rm -f "$artifact.part"
  if [ -e "$artifact" ]; then
    echo "the artifact already on the claim was left exactly as it was found" >&2
  fi
  exit 1
fi
#
mv "$artifact.part" "$artifact"
echo "model artifact acquired and verified: byte count and SHA-256"
{{- end -}}

{{/*
The name of the telemetry scrape ConfigMap.
*/}}
{{- define "inferops-llm.telemetryScrapeConfigMapName" -}}
{{ include "inferops-llm.fullname" . }}-telemetry-scrape
{{- end -}}

{{/*
The serving runtime's registered identifier, derived from the profile.

It is derived for the same reason `inferops-llm.capabilityId` is: a value carrying
this label would be a way to compose a mock adapter and publish the real runtime's
identifier, or the reverse. The two constants it mirrors are `MOCK_RUNTIME_ID` in
src/inferops/adapters/mock_serving.py and `LLAMA_SERVER_RUNTIME_ID` in
src/inferops/adapters/llama_cpp/pins.py, and a test compares this helper against
both so that one identifier cannot become two.
*/}}
{{- define "inferops-llm.runtimeId" -}}
{{- if eq .Values.profile "real" -}}
llama-cpp-server
{{- else -}}
inferops-mock-serving
{{- end -}}
{{- end -}}

{{/*
Every metric label the collector drops on the way in.

Derived from the accepted telemetry catalog rather than chosen here: it is every
attribute whose declared placements include neither `metric-label` nor
`info-label`, written in the form a Prometheus exposition spells it. A test
recomputes the list from docs/telemetry/telemetry-catalog.v1alpha1.json and fails
if the two disagree, so a placement decision taken in the catalog reaches the
collector without anybody remembering to come here.

Nothing in this repository emits any of them as a label -- the registry refuses one
at construction. This is the second line, for a series that arrives from a component
this project did not write, or from one it writes later: a correlation identifier, a
tenant, a pod name, or a duration that reached a label is dropped before it is
stored, rather than after somebody reads the bill.
*/}}
{{- define "inferops-llm.forbiddenMetricLabels" -}}
http_response_status_code|inferops_correlation_id|inferops_cost_record_id|inferops_duration_ms|inferops_evaluation_decision|inferops_event|inferops_field_path|inferops_finish_reason|inferops_owner_id|inferops_request_id|inferops_retry_count|inferops_tenant_id|inferops_workload_version|k8s_pod_name|level|service_name|span_id|timestamp|trace_id
{{- end -}}

{{/*
The name of one scrape job, scoped to the release.

**Why it is not a constant.** The scrape configuration this chart renders is a
document an operator merges into whatever configuration their collector already
has, and Prometheus refuses a configuration holding two `scrape_configs` entries
with the same `job_name`. Two releases of this chart installed beside each other --
the case every `keep` filter here is written to distinguish -- would each render a
fragment named `inferops-platform-api`, and the merged configuration would not load
at all. A job name that is right only while exactly one release exists is a job name
that fails at the moment composition starts.

It uses the same release-qualified name every object in this release carries, so a
job in a collector's configuration and an object in `kubectl get` are traceable to
each other by their shared prefix.
*/}}
{{- define "inferops-llm.telemetryJobName" -}}
{{ include "inferops-llm.fullname" .context }}-{{ .component }}
{{- end -}}

{{/*
The Prometheus scrape configuration for this release.

**What it is, and what it is not.** It is a document. No collector, store,
dashboard, or alerting path is selected -- ADR 0006 D8 leaves that to the open
question ADR 0004 carries -- so nothing reads this, and nothing scrapes either
endpoint. What it removes is the step where somebody writes scrape configuration by
hand against labels they guessed, and gets a job that silently matches nothing.

**Discovery selects on labels, not on annotations.** Every pod this chart installs
carries `app.kubernetes.io/part-of`, `app.kubernetes.io/instance`, and
`app.kubernetes.io/component`, always and whatever the values file says. The
`prometheus.io/*` annotations are optional and off by default, so a configuration
that keyed on them would select nothing in the default installation. Discovery is
also pinned to this release's namespace and instance: a job matching
`part-of: inferops` alone would scrape a second release installed beside this one
and attribute its series here.

**The release name is escaped before it reaches the regex, and that is the only
place in this chart where it needs to be.** Every other use of `.Release.Name` here
is an exact-match label value. This one is a `keep` filter, Helm permits a release
name to contain a dot, and a dot in an unescaped RE2 pattern matches any character
-- so a release called `a.z` would have matched a release called `aXz` installed
beside it, and would have collected its series under this release's name. That is
the precise failure the pinning above exists to prevent, so an unescaped name would
have been a control that read as one and was not.

**The port is kept explicitly.** Pod discovery yields one target per declared
container port, so a pod with two ports produces two targets and the second answers
nothing on the metrics path. Keeping the port the release publishes is what stops a
permanently failing target being reported as a broken endpoint.

**What the collector does NOT relabel, and why that is the decision.** The API
publishes the workload, the model, the outcome, and the identity attributes on its
own series already. A target label of the same name would win the collision --
`honor_labels` is false, stated here rather than left to the default -- and
Prometheus would rename the emitter's to `exported_*`, changing every query written
against it. So the API job attaches Kubernetes context and nothing else, and the
workload, model, environment, version, capability, release, model revision, runtime
image digest, and adapter kind are read where the catalog puts them: on the series
themselves, and on `inferops_build_info`, which is one series per process and is the
join ADR 0006 D3 designed for.

The runtime job is the opposite case. `llama-server` publishes bare series with no
labels at all -- the feasibility record measured exactly that -- so the collector
supplies the operating dimensions and there is nothing to collide with. It supplies
only the bounded ones the catalog permits as metric labels. It does not supply the
identity attributes, because putting an immutable version on every series is
precisely what the identity metric exists to avoid.

**`instance` carries the pod name, and it is the one unbounded label here.**
Prometheus requires the targets of one job to differ in their label sets, so with
two replicas a per-target identity is not optional; the only question is what it
holds. It holds the pod name rather than the default `<podIP>:<port>`, which is
equally unbounded, changes on every reschedule, and names nothing a person can look
up. The cost is stated in docs/telemetry/kubernetes-telemetry-collection.md rather
than left to be discovered: every series from a job is multiplied by the number of
distinct pods inside the store's retention window. Collapsing `instance` to a
constant per component would remove that multiplier and would also make two replicas
indistinguishable, which is the one question the multi-replica certification exists
to answer.

The catalog's rule that `k8s.pod.name` is not a metric label is an **emitter** rule
and is untouched: no InferOps process labels a series with its pod, and the registry
still refuses one that tries.

**The Kubernetes context labels carry a `k8s_` prefix** so that a label the collector
attached is never read as an attribute an emitter placed. `k8s_component` is the
workload tier -- `platform-api` or `serving-runtime` -- and is a different thing from
`inferops.component`, which is the readiness component the API names when it refuses
traffic.
*/}}
{{- define "inferops-llm.telemetryScrapeConfig" -}}
{{- $interval := printf "%ds" (int .Values.telemetry.collection.scrapeIntervalSeconds) -}}
{{- $timeout := printf "%ds" (int .Values.telemetry.collection.scrapeTimeoutSeconds) -}}
scrape_configs:
  - job_name: {{ include "inferops-llm.telemetryJobName" (dict "context" $ "component" "platform-api") }}
    scheme: http
    metrics_path: {{ .Values.telemetry.metricsPath | quote }}
    scrape_interval: {{ $interval }}
    scrape_timeout: {{ $timeout }}
    # Stated rather than left to the default, because it is the whole reason the
    # relabelling below adds no label the API already publishes.
    honor_labels: false
    kubernetes_sd_configs:
      - role: pod
        namespaces:
          own_namespace: false
          names:
            - {{ .Release.Namespace }}
    relabel_configs:
      - source_labels:
          - __meta_kubernetes_pod_label_app_kubernetes_io_part_of
          - __meta_kubernetes_pod_label_app_kubernetes_io_instance
          - __meta_kubernetes_pod_label_app_kubernetes_io_component
        separator: ";"
        action: keep
        regex: {{ printf "inferops;%s;platform-api" (regexQuoteMeta .Release.Name) | quote }}
      - source_labels:
          - __meta_kubernetes_pod_container_port_number
        action: keep
        regex: {{ .Values.api.containerPort | quote }}
      - source_labels:
          - __meta_kubernetes_namespace
        target_label: k8s_namespace
      - source_labels:
          - __meta_kubernetes_pod_label_app_kubernetes_io_component
        target_label: k8s_component
      - source_labels:
          - __meta_kubernetes_pod_name
        target_label: instance
    metric_relabel_configs:
      - action: labeldrop
        regex: {{ printf "(%s)" (include "inferops-llm.forbiddenMetricLabels" .) | quote }}
{{- if eq .Values.profile "real" }}
  - job_name: {{ include "inferops-llm.telemetryJobName" (dict "context" $ "component" "serving-runtime") }}
    scheme: http
    metrics_path: {{ .Values.telemetry.collection.runtimeMetricsPath | quote }}
    scrape_interval: {{ $interval }}
    scrape_timeout: {{ $timeout }}
    honor_labels: false
    kubernetes_sd_configs:
      - role: pod
        namespaces:
          own_namespace: false
          names:
            - {{ .Release.Namespace }}
    relabel_configs:
      - source_labels:
          - __meta_kubernetes_pod_label_app_kubernetes_io_part_of
          - __meta_kubernetes_pod_label_app_kubernetes_io_instance
          - __meta_kubernetes_pod_label_app_kubernetes_io_component
        separator: ";"
        action: keep
        regex: {{ printf "inferops;%s;serving-runtime" (regexQuoteMeta .Release.Name) | quote }}
      - source_labels:
          - __meta_kubernetes_pod_container_port_number
        action: keep
        regex: {{ .Values.runtime.containerPort | quote }}
      - source_labels:
          - __meta_kubernetes_namespace
        target_label: k8s_namespace
      - source_labels:
          - __meta_kubernetes_pod_label_app_kubernetes_io_component
        target_label: k8s_component
      - source_labels:
          - __meta_kubernetes_pod_name
        target_label: instance
      # The runtime publishes bare series. These four are the operating dimensions
      # the catalog permits as metric labels, and the collector is the only thing
      # positioned to supply them.
      - target_label: deployment_environment
        replacement: {{ .Values.telemetry.deploymentEnvironment | quote }}
      - target_label: inferops_workload_id
        replacement: {{ .Values.ownership.workloadId | quote }}
      - target_label: inferops_model_id
        replacement: {{ .Values.model.identifier | quote }}
      - target_label: inferops_runtime_id
        replacement: {{ include "inferops-llm.runtimeId" . | quote }}
    metric_relabel_configs:
      - action: labeldrop
        regex: {{ printf "(%s)" (include "inferops-llm.forbiddenMetricLabels" .) | quote }}
{{- end }}
{{- end -}}

{{/*
The recording rules: what a native runtime series means in InferOps terms, and what
is missing.

**Two groups, and the second is the one that earns its place.** The first names the
three `llamacpp:` series the accepted catalog maps to an InferOps concept and gives
each a derived name. Every recorded name is `inferops:` with a colon -- the
Prometheus recording-rule convention -- and never `inferops_` with an underscore, so
a derived series can never be confused with, or collide with, one the API emits.

The second makes absence readable. A target that exists and fails is `up == 0` and
easy; a job whose discovery matched nothing produces no `up` series at all, so a
query that groups by job returns an empty result, and an empty result looks like a
healthy quiet system. `absent()` is what separates them, and there is one per job.

`inferops:model_ready_absent:platform_api` reads **1 today, and will until the
serving-runtime adapter is instrumented**: `inferops_model_ready` is declared in the
catalog, assigned to the adapter, and marked not emitted. A rule that averaged a
metric nothing produces would have published an empty series, which reads as a
healthy system rather than an absent one. This publishes the absence instead.

No alerting rule is written and no dashboard is built. An alert needs a receiver, a
routing tree, and somebody on the other end, and none of the three is decided.
*/}}
{{- define "inferops-llm.telemetryRecordingRules" -}}
{{- $interval := printf "%ds" (int .Values.telemetry.collection.scrapeIntervalSeconds) -}}
{{- $apiJob := include "inferops-llm.telemetryJobName" (dict "context" . "component" "platform-api") -}}
{{- $runtimeJob := include "inferops-llm.telemetryJobName" (dict "context" . "component" "serving-runtime") -}}
{{- $jobs := $apiJob -}}
{{- if eq .Values.profile "real" -}}
{{- $jobs = printf "%s|%s" (regexQuoteMeta $apiJob) (regexQuoteMeta $runtimeJob) -}}
{{- else -}}
{{- $jobs = regexQuoteMeta $apiJob -}}
{{- end -}}
{{- $selector := printf "up{job=~\"%s\"}" $jobs -}}
{{- $scope := printf "k8s_namespace=\"%s\", k8s_component=\"platform-api\"" .Release.Namespace -}}
groups:
{{- if eq .Values.profile "real" }}
  - name: inferops-runtime-metric-mapping
    interval: {{ $interval }}
    rules:
      # llamacpp:prompt_tokens_total and llamacpp:tokens_predicted_total are the two
      # native counters the catalog maps to inferops_inference_tokens_total. The
      # direction label is what distinguishes them, exactly as it does on the metric
      # the API emits.
      - record: inferops:inference_tokens:runtime_total
        expr: |
          label_replace(llamacpp:prompt_tokens_total, "inferops_token_direction", "input", "", "")
          or
          label_replace(llamacpp:tokens_predicted_total, "inferops_token_direction", "output", "", "")
      - record: inferops:inference_requests_in_flight:runtime
        expr: llamacpp:requests_processing
      # Partial, and named so that it cannot be read as the queue histogram.
      # llamacpp:requests_deferred shows that queueing happened and never how long
      # any request waited; the wait is the adapter's measurement, and the adapter is
      # not instrumented.
      - record: inferops:inference_requests_deferred:runtime
        expr: llamacpp:requests_deferred
{{- end }}
  - name: inferops-collection-health
    interval: {{ $interval }}
    rules:
      - record: inferops:scrape_targets:count
        expr: count by (job, k8s_namespace, k8s_component) ({{ $selector }})
      # sum rather than a count over a filtered vector: a job whose every target is
      # down must read zero here, and a count over an empty vector reads nothing.
      - record: inferops:scrape_targets_up:sum
        expr: sum by (job, k8s_namespace, k8s_component) ({{ $selector }})
      - record: inferops:scrape_job_absent:platform_api
        expr: absent(up{job="{{ $apiJob }}"})
{{- if eq .Values.profile "real" }}
      - record: inferops:scrape_job_absent:serving_runtime
        expr: absent(up{job="{{ $runtimeJob }}"})
{{- end }}
      # The API answered a scrape and published no identity: a target that is up and
      # useless, which `up` alone cannot tell from one that is up and correct.
      #
      # Scoped to this release's namespace and tier for the same reason the jobs are
      # named for the release: an unscoped absent() over a store holding two releases
      # reads 0 as soon as either one of them publishes an identity.
      - record: inferops:build_info_absent:platform_api
        expr: absent(inferops_build_info{{ "{" }}{{ $scope }}{{ "}" }})
      # Reads 1 until the adapter the catalog assigns this metric to emits it.
      - record: inferops:model_ready_absent:platform_api
        expr: absent(inferops_model_ready{{ "{" }}{{ $scope }}{{ "}" }})
{{- end -}}

{{/*
The collector ingress allowance, written once and used by both workload policies.

It renders only when `telemetry.collection.collector` names both a namespace and a
pod selector; the template refuses one without the other, because a namespace with
no pod selector admits every pod in it and reads in the rendered policy exactly
like the narrow rule it is not.

The namespace and the pod selector are one list item rather than two, which is the
difference between "a pod in that namespace with those labels" and "any pod in that
namespace, or any pod anywhere with those labels". The second is the mistake this
object is most often written with.

`kubernetes.io/metadata.name` is set on every namespace by the API server itself,
so it is not a label anybody has to remember to apply.
*/}}
{{- define "inferops-llm.collector.serviceAccountName" -}}
{{- if .Values.security.serviceAccount.create -}}
{{- default (printf "%s-collector" (include "inferops-llm.fullname" .)) .Values.security.serviceAccount.collector.name -}}
{{- else -}}
{{- default "default" .Values.security.serviceAccount.collector.name -}}
{{- end -}}
{{- end -}}

{{- define "inferops-llm.collector.serviceName" -}}
{{- printf "%s-collector" (include "inferops-llm.fullname" .) -}}
{{- end -}}

{{- define "inferops-llm.collector.configMapName" -}}
{{- printf "%s-collector-configuration" (include "inferops-llm.fullname" .) -}}
{{- end -}}

{{- define "inferops-llm.collector.selectorLabels" -}}
app.kubernetes.io/name: {{ include "inferops-llm.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/component: telemetry-collector
{{- end -}}

{{- define "inferops-llm.collector.image" -}}
{{- printf "%s@%s" .Values.telemetry.collection.collector.image.repository .Values.telemetry.collection.collector.image.digest -}}
{{- end -}}

{{/*
Who may scrape a workload's metrics endpoint.

Two cases, and the second is why this reads a computed value rather than a
configured one. A collector somebody else runs is named by `collector.namespace`
and `collector.podSelector`, and both are required together because a namespace
with no pod selector admits every pod in it. A collector this release installs is
in this namespace carrying labels this chart chose -- so the chart fills them in
rather than asking an operator to restate them, because the failure mode of
asking is a release that installs a collector and then denies it.
*/}}
{{- define "inferops-llm.collectorIngressRule" -}}
{{- $root := .context -}}
{{- $collector := $root.Values.telemetry.collection.collector -}}
{{- $namespace := $collector.namespace -}}
{{- $selector := $collector.podSelector -}}
{{- if $collector.deploy -}}
{{- $namespace = $root.Release.Namespace -}}
{{- $selector = (include "inferops-llm.collector.selectorLabels" $root | fromYaml) -}}
{{- end -}}
{{- if and $namespace $selector }}
- from:
    - namespaceSelector:
        matchLabels:
          kubernetes.io/metadata.name: {{ $namespace }}
      podSelector:
        matchLabels:
          {{- toYaml $selector | nindent 10 }}
  ports:
    - port: {{ .port }}
      protocol: TCP
{{- end }}
{{- end -}}
