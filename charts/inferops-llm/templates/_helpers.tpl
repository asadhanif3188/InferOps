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
release half of it. The prerequisite half is Terraform's and does not exist:
V1-S3-005 owns it, and until it does the sweep must stay bound to the smoke
namespace it is bound to today.
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

{{- define "inferops-llm.serviceAccountName" -}}
{{- if .Values.security.serviceAccount.create -}}
{{- default (include "inferops-llm.fullname" .) .Values.security.serviceAccount.name -}}
{{- else -}}
{{- default "default" .Values.security.serviceAccount.name -}}
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
