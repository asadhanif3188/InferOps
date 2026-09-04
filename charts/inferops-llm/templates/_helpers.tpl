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
INFEROPS_LLAMA_SERVER_MODEL_PATH: {{ .Values.model.containerPath | quote }}
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
