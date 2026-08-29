{{/*
Expand the name of the chart.
*/}}
{{- define "algenta.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Create a default fully qualified app name.
*/}}
{{- define "algenta.fullname" -}}
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

{{- define "algenta.chart" -}}
{{- printf "%s-%s" .Chart.Name .Chart.Version | replace "+" "_" | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{/*
Common labels. Call with (dict "root" $ "component" "api"|"engine"|...).
*/}}
{{- define "algenta.labels" -}}
helm.sh/chart: {{ include "algenta.chart" .root }}
{{ include "algenta.selectorLabels" . }}
{{- if .root.Chart.AppVersion }}
app.kubernetes.io/version: {{ .root.Chart.AppVersion | quote }}
{{- end }}
app.kubernetes.io/managed-by: {{ .root.Release.Service }}
{{- end -}}

{{/*
Selector labels. Call with (dict "root" $ "component" "api"|"engine"|...).
*/}}
{{- define "algenta.selectorLabels" -}}
app.kubernetes.io/name: {{ include "algenta.name" .root }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
{{- if .component }}
app.kubernetes.io/component: {{ .component }}
{{- end }}
{{- end -}}

{{/*
Resolve an image reference. Call with (dict "root" $ "image" .Values.api.image).
*/}}
{{- define "algenta.image" -}}
{{- $registry := .root.Values.global.imageRegistry -}}
{{- $repo := .image.repository | default (printf "%s/%s" $registry .component) -}}
{{- printf "%s:%s" $repo .image.tag -}}
{{- end -}}

{{/*
Cross-field validation that a JSON schema alone cannot express as clearly, or that
benefits from a human-readable `helm template`/`helm install` failure message instead of a
raw schema-validation dump. Call once, near the top of every template that renders
release-shaped resources (api-deployment.yaml, engine-deployment.yaml, secret.yaml,
configmap.yaml) — `fail` aborts the whole render, so it only needs to run once in
practice, but templates render in an unspecified order and each one is cheap to guard.
*/}}
{{- define "algenta.validateValues" -}}

{{- if ne (int .Values.engine.replicaCount) 1 -}}
{{ fail "engine.replicaCount must be exactly 1. The engine bundles a Celery worker + Mojo runtime + agent runtime that share one RWO volume and is confirmed single-instance-only (Dockerfile.engine.prod, fly.engine.toml, .github/workflows/deploy.yml all pin count=1). See values.yaml's engine.replicaCount comment." }}
{{- end -}}

{{- if and (gt (int .Values.api.replicaCount) 1) (or (ne .Values.persistence.sources.accessMode "ReadWriteMany") (not .Values.persistence.sources.acknowledgeMultiWriterRisk)) -}}
{{ fail "api.replicaCount > 1 requires BOTH persistence.sources.accessMode=ReadWriteMany AND persistence.sources.acknowledgeMultiWriterRisk=true. Reason: apps/api_server/services/source_registry.py (the dataset-upload registry) does plain, unlocked pathlib file I/O against that volume — concurrent API replicas writing to it over ReadWriteOnce is unsafe. Only set the acknowledgement once you have confirmed either your StorageClass is genuinely ReadWriteMany-capable, or you do not use the dataset-upload / /v1/data feature at all. See README.md." }}
{{- end -}}

{{- if and .Values.api.autoscaling.enabled (gt (int .Values.api.autoscaling.maxReplicas) 1) (or (ne .Values.persistence.sources.accessMode "ReadWriteMany") (not .Values.persistence.sources.acknowledgeMultiWriterRisk)) -}}
{{ fail "api.autoscaling.maxReplicas > 1 falls under the same rule as api.replicaCount > 1 (the HPA can drive the Deployment past 1 replica just as directly) — set persistence.sources.accessMode=ReadWriteMany and persistence.sources.acknowledgeMultiWriterRisk=true, or cap maxReplicas at 1. See README.md." }}
{{- end -}}

{{- $extDb := .Values.externalDatabase.enabled -}}
{{- $bunDb := .Values.postgresql.enabled -}}
{{- if and $extDb $bunDb -}}
{{ fail "Both externalDatabase.enabled and postgresql.enabled are true — pick exactly one Postgres source. Set postgresql.enabled=false to use your own managed instance (externalDatabase.*), or externalDatabase.enabled=false to use the bundled trial Postgres." }}
{{- end -}}
{{- if and (not $extDb) (not $bunDb) -}}
{{ fail "Neither externalDatabase.enabled nor postgresql.enabled is true — the API and engine have no Postgres to talk to. Set exactly one." }}
{{- end -}}

{{- $extRedis := .Values.externalRedis.enabled -}}
{{- $bunRedis := .Values.redis.enabled -}}
{{- if and $extRedis $bunRedis -}}
{{ fail "Both externalRedis.enabled and redis.enabled are true — pick exactly one Redis source." }}
{{- end -}}
{{- if and (not $extRedis) (not $bunRedis) -}}
{{ fail "Neither externalRedis.enabled nor redis.enabled is true — set exactly one. (Redis is a soft dependency at the app layer — a bad REDIS_URL degrades rather than crashes — but this chart still requires a deliberate choice of source.)" }}
{{- end -}}

{{- $extStore := .Values.externalObjectStore.enabled -}}
{{- $bunStore := .Values.minio.enabled -}}
{{- if and $extStore $bunStore -}}
{{ fail "Both externalObjectStore.enabled and minio.enabled are true — pick exactly one S3-compatible object store source." }}
{{- end -}}
{{- if and (not $extStore) (not $bunStore) -}}
{{ fail "Neither externalObjectStore.enabled nor minio.enabled is true — set exactly one." }}
{{- end -}}

{{- if and $extDb .Values.externalDatabase.enabled (not .Values.externalDatabase.url) (not .Values.externalDatabase.host) -}}
{{ fail "externalDatabase.enabled=true but neither externalDatabase.url nor externalDatabase.host is set." }}
{{- end -}}
{{- if and $extRedis (not .Values.externalRedis.url) (not .Values.externalRedis.host) -}}
{{ fail "externalRedis.enabled=true but neither externalRedis.url nor externalRedis.host is set." }}
{{- end -}}
{{- if and $extStore (not .Values.externalObjectStore.endpointUrl) -}}
{{ fail "externalObjectStore.enabled=true but externalObjectStore.endpointUrl is not set." }}
{{- end -}}

{{- if and $extDb (not .Values.externalDatabase.url) (not .Values.externalDatabase.existingSecret) -}}
{{ fail "externalDatabase.enabled=true with no externalDatabase.url set requires externalDatabase.existingSecret (a Secret holding the Postgres password) — this chart never accepts a plaintext external-database password in values.yaml. Either set externalDatabase.url to a full DSN with embedded credentials, or point existingSecret at a Secret you manage." }}
{{- end -}}
{{- if and $extStore (not .Values.externalObjectStore.existingSecret) -}}
{{ fail "externalObjectStore.enabled=true requires externalObjectStore.existingSecret (a Secret holding access-key-id/secret-access-key) — this chart never accepts plaintext object-store credentials in values.yaml." }}
{{- end -}}

{{- if and (not .Values.secrets.existingSecret) (not .Values.config.apiPublicBaseUrl) -}}
{{/* Advisory only — config.apiPublicBaseUrl empty is legal (matches compose's own default-empty), so this is intentionally not a fail. Left as a documented no-op branch so a future stricter mode has an obvious place to hook in. */}}
{{- end -}}

{{- end -}}

{{/*
Name of the Secret the workloads mount env from — either the operator-supplied
existingSecret, or the one this chart renders in templates/secret.yaml.
*/}}
{{- define "algenta.secretName" -}}
{{- .Values.secrets.existingSecret | default (printf "%s-app-secrets" (include "algenta.fullname" .)) -}}
{{- end -}}

{{- define "algenta.sourcesClaimName" -}}
{{- .Values.persistence.sources.existingClaim | default (printf "%s-sources" (include "algenta.fullname" .)) -}}
{{- end -}}

{{- define "algenta.apiServiceAccountName" -}}
{{- if .Values.api.serviceAccount.create -}}
{{- .Values.api.serviceAccount.name | default (printf "%s-api" (include "algenta.fullname" .)) -}}
{{- else -}}
{{- .Values.api.serviceAccount.name | default "default" -}}
{{- end -}}
{{- end -}}

{{- define "algenta.engineServiceAccountName" -}}
{{- if .Values.engine.serviceAccount.create -}}
{{- .Values.engine.serviceAccount.name | default (printf "%s-engine" (include "algenta.fullname" .)) -}}
{{- else -}}
{{- .Values.engine.serviceAccount.name | default "default" -}}
{{- end -}}
{{- end -}}

{{- define "algenta.databaseSecretName" -}}
{{- if .Values.postgresql.enabled -}}
{{- printf "%s-postgresql" (include "algenta.fullname" .) -}}
{{- else -}}
{{- .Values.externalDatabase.existingSecret | default (printf "%s-external-database" (include "algenta.fullname" .)) -}}
{{- end -}}
{{- end -}}

{{- define "algenta.redisSecretName" -}}
{{- if .Values.redis.enabled -}}
{{- printf "%s-redis" (include "algenta.fullname" .) -}}
{{- else -}}
{{- .Values.externalRedis.existingSecret | default (printf "%s-external-redis" (include "algenta.fullname" .)) -}}
{{- end -}}
{{- end -}}

{{- define "algenta.objectStoreSecretName" -}}
{{- if .Values.minio.enabled -}}
{{- printf "%s-minio" (include "algenta.fullname" .) -}}
{{- else -}}
{{- .Values.externalObjectStore.existingSecret | default (printf "%s-external-objectstore" (include "algenta.fullname" .)) -}}
{{- end -}}
{{- end -}}

{{/*
Shared datastore env vars (DATABASE_URL / DATABASE_URL_SYNC / REDIS_URL / S3_*), common to
both api and engine containers. Renders a YAML list of env entries — include with
`{{- include "algenta.env.datastores" . | nindent N }}` from within a `env:` block.

Password/access-key values are pulled from a Secret via secretKeyRef and referenced back
into the composed DSN with Kubernetes' own $(VAR_NAME) container-env expansion (the
referenced var must be defined earlier in the same env list, which it is here) — this
lets a single full connection string carry a credential without ever putting that
credential in a ConfigMap or in `helm get values`.
*/}}
{{- define "algenta.env.datastores" -}}
{{- if .Values.externalDatabase.url }}
- name: DATABASE_URL
  value: {{ .Values.externalDatabase.url | quote }}
- name: DATABASE_URL_SYNC
  value: {{ (.Values.externalDatabase.urlSync | default .Values.externalDatabase.url) | quote }}
{{- else }}
- name: DATABASE_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ include "algenta.databaseSecretName" . }}
      key: {{ if .Values.postgresql.enabled }}postgres-password{{ else }}{{ .Values.externalDatabase.existingSecretPasswordKey }}{{ end }}
{{- $dbHost := .Values.postgresql.enabled | ternary (printf "%s-postgresql" (include "algenta.fullname" .)) .Values.externalDatabase.host }}
{{- $dbPort := .Values.postgresql.enabled | ternary 5432 (.Values.externalDatabase.port | int) }}
{{- $dbName := .Values.postgresql.enabled | ternary .Values.postgresql.database .Values.externalDatabase.database }}
{{- $dbUser := .Values.postgresql.enabled | ternary .Values.postgresql.username .Values.externalDatabase.username }}
{{/* DATABASE_HOST must be defined BEFORE DATABASE_URL/_SYNC below — Kubernetes' $(VAR)
     container-env expansion only resolves references to vars defined EARLIER in the same
     env list. */}}
- name: DATABASE_HOST
  value: {{ $dbHost | quote }}
- name: DATABASE_URL
  value: {{ printf "postgresql+asyncpg://%s:$(DATABASE_PASSWORD)@$(DATABASE_HOST):%d/%s" $dbUser (int $dbPort) $dbName | quote }}
- name: DATABASE_URL_SYNC
  value: {{ printf "postgresql://%s:$(DATABASE_PASSWORD)@$(DATABASE_HOST):%d/%s" $dbUser (int $dbPort) $dbName | quote }}
{{- end }}
{{- if .Values.externalRedis.url }}
- name: REDIS_URL
  value: {{ .Values.externalRedis.url | quote }}
{{- else }}
{{- $redisHost := .Values.redis.enabled | ternary (printf "%s-redis" (include "algenta.fullname" .)) .Values.externalRedis.host }}
{{- $redisPort := .Values.redis.enabled | ternary 6379 (.Values.externalRedis.port | int) }}
{{- $redisDb := .Values.externalRedis.database | default 0 }}
{{- if and (not .Values.redis.enabled) .Values.externalRedis.existingSecret }}
- name: REDIS_PASSWORD
  valueFrom:
    secretKeyRef:
      name: {{ .Values.externalRedis.existingSecret }}
      key: {{ .Values.externalRedis.existingSecretPasswordKey }}
- name: REDIS_URL
  value: {{ printf "redis://:$(REDIS_PASSWORD)@%s:%d/%d" $redisHost (int $redisPort) (int $redisDb) | quote }}
{{- else }}
- name: REDIS_URL
  value: {{ printf "redis://%s:%d/%d" $redisHost (int $redisPort) (int $redisDb) | quote }}
{{- end }}
{{- end }}
- name: S3_BUCKET_NAME
  value: {{ (.Values.minio.enabled | ternary .Values.minio.bucketName .Values.externalObjectStore.bucketName) | quote }}
- name: S3_ENDPOINT_URL
  value: {{ (.Values.minio.enabled | ternary (printf "http://%s-minio:9000" (include "algenta.fullname" .)) .Values.externalObjectStore.endpointUrl) | quote }}
- name: S3_REGION
  value: {{ .Values.externalObjectStore.region | quote }}
- name: S3_ACCESS_KEY_ID
  valueFrom:
    secretKeyRef:
      name: {{ include "algenta.objectStoreSecretName" . }}
      key: {{ if .Values.minio.enabled }}root-user{{ else }}{{ .Values.externalObjectStore.existingSecretAccessKeyIdKey }}{{ end }}
- name: S3_SECRET_ACCESS_KEY
  valueFrom:
    secretKeyRef:
      name: {{ include "algenta.objectStoreSecretName" . }}
      key: {{ if .Values.minio.enabled }}root-password{{ else }}{{ .Values.externalObjectStore.existingSecretSecretAccessKeyKey }}{{ end }}
{{- end -}}

{{/*
Shared, non-secret app-config env vars common to both api and engine containers.
*/}}
{{- define "algenta.env.appConfig" -}}
- name: API_ENV
  value: {{ .Values.config.apiEnv | quote }}
- name: LOG_LEVEL
  value: {{ .Values.config.logLevel | quote }}
- name: RUNTIME_FALLBACK_MODE
  value: {{ .Values.config.runtimeFallbackMode | quote }}
- name: RESULT_STORAGE_ENABLED
  value: {{ .Values.config.resultStorageEnabled | quote }}
- name: ALGENTA_DEPLOYMENT_MODE
  value: {{ .Values.config.deploymentMode | quote }}
- name: ALGENTA_DISABLE_CLOUD
  value: {{ .Values.config.disableCloud | ternary "1" "0" | quote }}
- name: ALGENTA_DISABLE_TELEMETRY
  value: {{ .Values.config.disableTelemetry | ternary "1" "0" | quote }}
- name: ALGENTA_TELEMETRY_MODE
  value: {{ .Values.config.telemetryMode | quote }}
- name: ALGENTA_METERING_MODE
  value: {{ .Values.config.meteringMode | quote }}
- name: ALGENTA_ALLOW_OUTBOUND_NETWORK
  value: {{ .Values.config.allowOutboundNetwork | ternary "1" "0" | quote }}
{{- if .Values.config.apiPublicBaseUrl }}
- name: ALGENTA_API_PUBLIC_BASE_URL
  value: {{ .Values.config.apiPublicBaseUrl | quote }}
{{- end }}
- name: MOJO_BINARY_PATH
  value: /app/mojo_build/simulate
- name: ALGENTA_SOURCES_DIR
  value: /home/app/.algenta/sources
- name: ALGENTA_RUNTIME_DIR
  value: /home/app/.algenta/runtime
{{/* Despite the name, this is the API's OWN address, not the engine's — it is the loopback
     URL + key the bundled agent runtime (running inside the engine Pod) uses to call BACK
     into /v1, mirroring docker-compose.selfhosted.yml where BOTH the api and engine
     containers set ALGENTA_ENGINE_URL to http://api:8000. The engine's OWN address (for the
     api container to reach the agent-core sidecar) is the separate ALGENTA_AGENT_CORE_URL
     var, set per-container in api-deployment.yaml / engine-deployment.yaml because its
     value differs (Service DNS name from api, loopback from engine). */}}
- name: ALGENTA_ENGINE_URL
  value: {{ printf "http://%s-api:%d" (include "algenta.fullname" .) (int .Values.api.service.port) | quote }}
{{- end -}}

