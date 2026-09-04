{{/*
The refusals.

`values.schema.json` decides the shape of a value. This file decides the rules
that need to see two values at once, which a JSON Schema cannot express here
without duplicating the whole object per profile.

Each refusal names the value and states the constraint. None of them repeats a
value read out of the values file, for the same reason the platform's own
refusals do not: an error message is where a credential gets published.

Every rule here fails the render. There is no rule that warns, and none that
substitutes a default: rule 4 of docs/serving/mock-and-real-boundary.md is that
substituting a working result for a missing one is a defect and not a fallback,
and a chart that quietly defaulted would commit that defect once per install
rather than once per test.
*/}}

{{- define "inferops-llm.validate" -}}

{{/* -- the selection ---------------------------------------------------- */}}

{{- if not .Values.profile -}}
{{- fail "profile is required and has no default. Set it to 'real' for the serving path this project certifies, or 'mock' for the fixture replayer, which certifies nothing. An omission is refused rather than treated as 'mock': see docs/serving/mock-and-real-boundary.md rule 5." -}}
{{- end -}}

{{- if not (has .Values.profile (list "mock" "real")) -}}
{{- fail "profile must be exactly 'mock' or 'real'." -}}
{{- end -}}

{{/* -- placement, and the namespace this chart may not create ----------- */}}

{{- if .Values.namespacePrefixCheck -}}
{{- if not (hasPrefix "inferops-" .Release.Namespace) -}}
{{- fail "the release namespace must be prefixed 'inferops-' (ADR 0001 D5), and it must already exist. Terraform owns the namespace; this chart installs into it. Never pass --create-namespace: it makes both tools own one resource." -}}
{{- end -}}
{{- end -}}

{{/* -- images ----------------------------------------------------------- */}}

{{- if not .Values.api.image.repository -}}
{{- fail "api.image.repository is required. No InferOps API image is published, so there is no default that would resolve: build one, load it into the cluster, and state its repository here." -}}
{{- end -}}
{{- if not .Values.api.image.digest -}}
{{- fail "api.image.digest is required. A tag is a label that can be moved; a digest is what the engine resolves." -}}
{{- end -}}
{{- if not .Values.runtime.image.repository -}}
{{- fail "runtime.image.repository is required." -}}
{{- end -}}
{{- if not .Values.runtime.image.digest -}}
{{- fail "runtime.image.digest is required, and must be the digest ADR 0002 pins." -}}
{{- end -}}

{{/* -- ownership -------------------------------------------------------- */}}

{{- if not .Values.ownership.owner -}}
{{- fail "ownership.owner is required. A release with no accountable owner is the ambiguity docs/architecture/resource-ownership.md exists to prevent." -}}
{{- end -}}
{{- if not .Values.ownership.workloadId -}}
{{- fail "ownership.workloadId is required. It is configuration rather than a caller's header, because a workload identifier read off a request would be an unbounded metric label." -}}
{{- end -}}

{{/* -- the model, per profile ------------------------------------------- */}}

{{- if not .Values.model.identifier -}}
{{- fail "model.identifier is required under both profiles. It is the identity the API checks a caller's 'model' member against." -}}
{{- end -}}

{{- if eq .Values.profile "real" -}}

{{- if hasPrefix "mock-" (lower .Values.model.identifier) -}}
{{- fail "a real release refuses a mock-labelled model identity, which starts with 'mock-'. This is the same refusal src/inferops/adapters/llama_cpp/settings.py raises at start-up, moved to render time so that the release is never built." -}}
{{- end -}}

{{- if not .Values.model.revision -}}
{{- fail "model.revision is required under the real profile. A model identifier alone pins nothing, and a real record naming no revision is a record nobody can reproduce." -}}
{{- end -}}

{{- if not .Values.model.alias -}}
{{- fail "model.alias is required under the real profile: it is the name the runtime serves the artifact under." -}}
{{- end -}}

{{- if not .Values.model.containerPath -}}
{{- fail "model.containerPath is required under the real profile." -}}
{{- end -}}
{{- if not (hasSuffix ".gguf" .Values.model.containerPath) -}}
{{- fail "model.containerPath must name a .gguf artifact, which is the only format the selected runtime loads." -}}
{{- end -}}

{{- if not .Values.model.cache.claimName -}}
{{- fail "model.cache.claimName is required under the real profile. It names an existing PersistentVolumeClaim that Terraform owns; this chart mounts it and never creates it, because a pod is disposable by definition and nothing durable may live only inside one." -}}
{{- end -}}
{{- if not .Values.model.cache.readOnly -}}
{{- fail "model.cache.readOnly must stay true. The serving deployment mounts the cache; the acquisition job writes it. Writing content is not owning the container, and a serving replica that could write the cache is a second writer nobody decided on." -}}
{{- end -}}

{{- end -}}

{{- if eq .Values.profile "mock" -}}

{{- if not (hasPrefix "mock-" .Values.model.identifier) -}}
{{- fail "a mock release accepts only a mock-labelled model identity, which starts with 'mock-'. A mock configured with a real model identity emits a transcript naming that model, and a transcript naming a real model is the exact artifact somebody later cites as real-runtime evidence." -}}
{{- end -}}

{{- if .Values.model.revision -}}
{{- fail "model.revision must be empty under the mock profile. A mock loads no weights, and a mock release carrying a revision reads back as one that had." -}}
{{- end -}}
{{- if .Values.model.alias -}}
{{- fail "model.alias must be empty under the mock profile." -}}
{{- end -}}
{{- if .Values.model.containerPath -}}
{{- fail "model.containerPath must be empty under the mock profile: nothing is mounted and no artifact is read." -}}
{{- end -}}
{{- if .Values.model.cache.claimName -}}
{{- fail "model.cache.claimName must be empty under the mock profile. A mock that mounted the model cache would look, from the outside, exactly like a release that served from it." -}}
{{- end -}}
{{- if .Values.security.secretRefs -}}
{{- fail "security.secretRefs must be empty under the mock profile. A mock never holds real data and never requires real credentials, which is the rule the committed mock-llm contract example already obeys." -}}
{{- end -}}

{{- end -}}

{{/* -- resources, both halves ------------------------------------------- */}}

{{- range $component := list "api" "runtime" -}}
{{- $resources := (index $.Values $component).resources -}}
{{- if or (not $resources.requests) (not $resources.limits) -}}
{{- fail (printf "%s.resources must state both requests and limits. A workload with no request is scheduled anywhere and a workload with no limit is bounded by nothing." $component) -}}
{{- end -}}
{{- end -}}

{{/* -- environment overrides may not reach a derived name --------------- */}}

{{/*
The reserved set is every name the chart writes: the configuration it derives
from `profile`, and the pod identity it supplies through the downward API. The
second is in the set for the same reason as the first -- `INFEROPS_POD_NAME` is
the replica label everything this process emits carries, a duplicate environment
name is resolved last-one-wins by the kubelet, and an entry that could overwrite
it would make an identity the API server supplies into one an operator typed.
*/}}
{{- $reserved := merge
      (dict)
      (include "inferops-llm.derivedEnv" . | fromYaml)
      (dict "INFEROPS_POD_NAME" "") -}}
{{- range $component := list "api" "runtime" -}}
{{- range $entry := (index $.Values $component).extraEnv -}}
{{- if eq $entry.name "INFEROPS_POD_NAME" -}}
{{- fail (printf "%s.extraEnv may not set the pod identity. It is supplied through the downward API, and a duplicate environment name is resolved last-one-wins by the kubelet, so an entry here would turn a value the API server supplies into one an operator typed." $component) -}}
{{- end -}}
{{- if hasKey $reserved $entry.name -}}
{{- fail (printf "%s.extraEnv may not set a name this chart derives. The chart writes it from 'profile' and from nothing else, and a merge that could overwrite it is exactly how a real release comes to publish 'mock', or the reverse. Refused name: %s" $component $entry.name) -}}
{{- end -}}
{{- if hasPrefix "INFEROPS_LLAMA_SERVER_" $entry.name -}}
{{- fail (printf "%s.extraEnv may not set a runtime setting the chart derives from the profile and the pinned runtime record." $component) -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/* -- a secret reference may not shadow a derived name ----------------- */}}

{{- range $entry := .Values.security.secretRefs -}}
{{- if hasKey $reserved $entry.name -}}
{{- fail (printf "security.secretRefs may not bind a name this chart derives: %s" $entry.name) -}}
{{- end -}}
{{- if hasPrefix "INFEROPS_" $entry.name -}}
{{- fail "security.secretRefs may not bind a name in the INFEROPS_ namespace. That namespace is the chart's configuration surface, and a secret bound into it would put credential-shaped configuration where a reader expects rendered configuration." -}}
{{- end -}}
{{- end -}}

{{/* -- a label or annotation may not shadow a derived one ---------------- */}}

{{/*
The same rule as the environment, on the surface it is easier to forget.

A label appended after a derived one produces a mapping carrying that key twice,
and every parser this output passes through resolves it last-one-wins. So
`commonLabels` naming `inferops.io/profile` does not decorate a release, it
relabels it -- and a mock release labelled `real` is precisely what rule 1 of the
mock and real boundary forbids, because the label is what identifies the artifact
from the artifact itself.

`app.kubernetes.io/part-of` and `inferops.io/lifecycle` are here for a second
reason. The ownership document's scoped-teardown resolution selects on exactly
those two, so a release that could rewrite them could exempt itself from the
sweep that is meant to remove it, or present itself as a Terraform-owned
prerequisite.
*/}}

{{- $labelKeys := (include "inferops-llm.derivedLabelKeys" . | fromYamlArray) -}}
{{- range $key, $value := .Values.commonLabels -}}
{{- if has $key $labelKeys -}}
{{- fail (printf "commonLabels may not set a label this chart derives. Appending one produces the same key twice, and the appended value is the one every parser keeps -- so this relabels the release rather than decorating it. Refused label: %s" $key) -}}
{{- end -}}
{{- end -}}

{{- $annotationKeys := (include "inferops-llm.derivedAnnotationKeys" . | fromYamlArray) -}}
{{- range $key, $value := .Values.commonAnnotations -}}
{{- if has $key $annotationKeys -}}
{{- fail (printf "commonAnnotations may not set an annotation this chart derives. Refused annotation: %s" $key) -}}
{{- end -}}
{{- end -}}

{{/*
The per-object annotation maps, which reach one object each. Left unchecked they
do something worse than the release-wide map: they desynchronise attribution
*within* one release, so two objects installed by the same command disagree about
which tenant they belong to.
*/}}
{{- range $map := list .Values.api.service.annotations .Values.runtime.service.annotations .Values.security.serviceAccount.annotations -}}
{{- range $key, $value := $map -}}
{{- if has $key $annotationKeys -}}
{{- fail (printf "a per-object annotations map may not set an annotation this chart derives; two objects in one release would then disagree about it. Refused annotation: %s" $key) -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{/* -- probes, and the budgets they are given -------------------------- */}}

{{/*
Three rules, and the first is the one this PR exists to get right.

A startup probe whose budget is smaller than the adapter's own startup budget
makes that budget unreachable: the kubelet kills the container while the adapter
is still inside the window it was told it had, and restarts it into the same
load. The measured loads are the reason the default is twice the published
figure -- V1-S2-007 recorded 133,515 ms to 215,672 ms across six starts, and
V1-S2-005 recorded 358,735 ms on the same host -- and this refusal is what stops
a values file quietly taking it back.

A probe whose timeout is not shorter than its period overlaps itself: the next
attempt starts before the previous one has been given up on, and the failure
count then measures something other than consecutive failures.
*/}}

{{- range $component := list "api" "runtime" -}}
{{- $probes := (index $.Values $component).probes -}}
{{- if $probes.enabled -}}
{{- range $kind := list "startup" "readiness" "liveness" -}}
{{- $probe := index $probes $kind -}}
{{- if ge (int $probe.timeoutSeconds) (int $probe.periodSeconds) -}}
{{- fail (printf "%s.probes.%s.timeoutSeconds must be less than periodSeconds. A probe that may take as long as the interval between probes overlaps itself, and the failure threshold then counts something other than consecutive failures." $component $kind) -}}
{{- end -}}
{{- end -}}
{{- end -}}
{{- end -}}

{{- if .Values.runtime.probes.enabled -}}
{{- if lt (int .Values.runtime.probes.startup.budgetMs) (int .Values.runtime.startupBudgetMs) -}}
{{- fail "runtime.probes.startup.budgetMs must be at least runtime.startupBudgetMs. The first is how long the kubelet waits for the container and the second is how long the adapter waits for the model; a kubelet that gives up first kills the container mid-load and restarts it into the same load, which makes the adapter's budget unreachable rather than generous." -}}
{{- end -}}
{{- end -}}

{{/* -- shutdown, and whether the grace period covers it ------------------ */}}

{{/*
The API drains: readiness goes false, what is in flight finishes, the process
exits. The pause before that is for the endpoint race. A grace period that does
not cover both ends in SIGKILL, and a drain that ends in SIGKILL was decoration.

The runtime does not drain -- `llama-server` is stopped rather than asked to
finish -- so it only has to outlast its own pause.
*/}}

{{- $apiDrainSeconds := div (add (int .Values.api.drainTimeoutMs) 999) 1000 -}}
{{- $apiNeeded := add (int .Values.api.lifecycle.preStopSleepSeconds) $apiDrainSeconds -}}
{{- if lt (int .Values.api.lifecycle.terminationGracePeriodSeconds) $apiNeeded -}}
{{- fail (printf "api.lifecycle.terminationGracePeriodSeconds must cover the preStop pause and the drain together, which is %d seconds for the values given. A period shorter than that ends in SIGKILL part-way through a drain the API performed to avoid exactly that." $apiNeeded) -}}
{{- end -}}

{{- if le (int .Values.runtime.lifecycle.terminationGracePeriodSeconds) (int .Values.runtime.lifecycle.preStopSleepSeconds) -}}
{{- fail "runtime.lifecycle.terminationGracePeriodSeconds must be greater than preStopSleepSeconds, or the pause consumes the whole period and the process is killed rather than stopped." -}}
{{- end -}}

{{/* -- telemetry --------------------------------------------------------- */}}

{{- if and .Values.telemetry.scrapeAnnotations (not .Values.telemetry.enabled) -}}
{{- fail "telemetry.scrapeAnnotations requires telemetry.enabled. Annotating a port as scrapeable when the workload publishes no metrics advertises an endpoint that answers nothing, and a collector that believed it would report the absence as a scrape failure rather than as a decision." -}}
{{- end -}}

{{/* -- the chart's own test ---------------------------------------------- */}}

{{- if .Values.tests.enabled -}}
{{- if or (not .Values.tests.image.repository) (not .Values.tests.image.digest) -}}
{{- fail "tests.image.repository and tests.image.digest are required while tests.enabled is true. The test pod needs an HTTP client, and an unpinned one is a different client on a different day." -}}
{{- end -}}
{{- end -}}

{{- end -}}
