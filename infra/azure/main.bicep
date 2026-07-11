// Algenta Decision Service — guided customer-hosted Azure gateway (Build order 7).
//
// Stands up the decision runtime in the CUSTOMER's Azure subscription:
//   user-assigned managed identity · Log Analytics + App Insights · Key Vault (RBAC) ·
//   Storage account + Blob container (the native artifact store) · PostgreSQL Flexible ·
//   optional Azure Cache for Redis · Container Apps env + the api container.
//
// Trust posture (matches the plan):
//   * Managed identity — NO long-lived storage/DB secrets distributed to the app. The MI is
//     granted Key Vault Secrets User + Storage Blob Data Contributor.
//   * Secrets live in Key Vault; the container app references them (never inlined in config).
//   * NO admin key is emitted as an output (go-live uses a short-lived Entra-bound handshake).
//   * Private profile: DISABLE_CLOUD=1, empty control-plane URL, Azure Blob object store.
//
// This is a "guided" (not one-click) deployment: tenant policy, resource-provider registration,
// networking, and Entra admin-consent may require operator intervention. See README.md.
//
// Validate:  az bicep build --file main.bicep
// Deploy:    az deployment group create -g <rg> -f main.bicep -p @main.parameters.json

@description('Location for all resources.')
param location string = resourceGroup().location

@description('Location for PostgreSQL Flexible Server. Defaults to `location`; override when the subscription is offer-restricted for Postgres in the primary region (LocationIsOfferRestricted).')
param postgresLocation string = location

@description('Optional extra suffix for the PostgreSQL server name — use to sidestep the global (DNS) name reservation Azure holds after a failed/deleted flexible server.')
param pgNameSuffix string = ''

@description('Short prefix for resource names (3-12 lowercase alphanumerics).')
@minLength(3)
@maxLength(12)
param namePrefix string = 'algenta'

@description('Container image for the api service (GHCR digest-pinned recommended).')
param apiImage string

@description('PostgreSQL administrator login.')
param postgresAdminLogin string = 'algenta'

@description('PostgreSQL administrator password.')
@secure()
param postgresAdminPassword string

@description('Config encryption key (Fernet/AES) for per-connector credential encryption.')
@secure()
param configEncryptionKey string

@description('JWT signing secret for hosted sessions.')
@secure()
param jwtSecret string

@description('Deploy Azure Cache for Redis (rate-limit/quota/coordination). Off = single-replica dev.')
param deployRedis bool = true

@description('Microsoft Entra tenant id the gateway accepts tokens from (empty = Entra off).')
param entraTenantId string = ''

@description('Entra audience = the gateway app registration app-id URI or client id (empty = Entra off).')
param entraAudience string = ''

@description('Azure Container Registry name that holds the api image (empty = public/anonymous image, no ACR pull wired).')
param acrName string = ''

@description('ACR login server, e.g. myregistry.azurecr.io (required when acrName is set).')
param acrLoginServer string = ''

var suffix = uniqueString(resourceGroup().id)
var kvName = take('${namePrefix}kv${suffix}', 24)
var saName = take('${namePrefix}sa${suffix}', 24)
var pgName = '${namePrefix}-pg-${suffix}${pgNameSuffix}'
var dbName = 'algenta'
var blobContainer = 'artifacts'

// Built-in role definition ids.
var roleKeyVaultSecretsUser = '4633458b-17de-408a-b874-0445c86b69e6'
var roleStorageBlobDataContributor = 'ba92f5b4-2d11-453d-a403-e96b0029c9fe'
var roleAcrPull = '7f951dda-4ed3-4680-a7ca-43fe172d538d'
var useAcr = !empty(acrName)

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: '${namePrefix}-id'
  location: location
}

// When the api image lives in a private ACR, grant the app's managed identity AcrPull on it
// (the registry is created outside this template; referenced as existing) so the Container App
// can pull without admin creds. dependsOn ensures the grant lands before the app's first pull.
resource acr 'Microsoft.ContainerRegistry/registries@2023-07-01' existing = if (useAcr) {
  name: acrName
}

resource acrRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (useAcr) {
  name: guid(acrName, identity.id, roleAcrPull)
  scope: acr
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions', roleAcrPull
    )
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource logs 'Microsoft.OperationalInsights/workspaces@2023-09-01' = {
  name: '${namePrefix}-logs'
  location: location
  properties: {
    sku: { name: 'PerGB2018' }
    retentionInDays: 30
  }
}

resource appInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: '${namePrefix}-ai'
  location: location
  kind: 'web'
  properties: {
    Application_Type: 'web'
    WorkspaceResourceId: logs.id
  }
}

resource vault 'Microsoft.KeyVault/vaults@2023-07-01' = {
  name: kvName
  location: location
  properties: {
    sku: { family: 'A', name: 'standard' }
    tenantId: subscription().tenantId
    enableRbacAuthorization: true
    enableSoftDelete: true
  }
}

resource secretPgPassword 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: vault
  name: 'postgres-password'
  properties: { value: postgresAdminPassword }
}
resource secretConfigKey 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: vault
  name: 'config-encryption-key'
  properties: { value: configEncryptionKey }
}
resource secretJwt 'Microsoft.KeyVault/vaults/secrets@2023-07-01' = {
  parent: vault
  name: 'jwt-secret'
  properties: { value: jwtSecret }
}

resource kvRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(vault.id, identity.id, roleKeyVaultSecretsUser)
  scope: vault
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions', roleKeyVaultSecretsUser
    )
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: saName
  location: location
  sku: { name: 'Standard_LRS' }
  kind: 'StorageV2'
  properties: {
    allowBlobPublicAccess: false
    minimumTlsVersion: 'TLS1_2'
    supportsHttpsTrafficOnly: true
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
}

resource container 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = {
  parent: blobService
  name: blobContainer
  properties: { publicAccess: 'None' }
}

resource storageRole 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(storage.id, identity.id, roleStorageBlobDataContributor)
  scope: storage
  properties: {
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions', roleStorageBlobDataContributor
    )
    principalId: identity.properties.principalId
    principalType: 'ServicePrincipal'
  }
}

resource postgres 'Microsoft.DBforPostgreSQL/flexibleServers@2023-06-01-preview' = {
  name: pgName
  location: postgresLocation
  sku: { name: 'Standard_B1ms', tier: 'Burstable' }
  properties: {
    version: '16'
    administratorLogin: postgresAdminLogin
    administratorLoginPassword: postgresAdminPassword
    storage: { storageSizeGB: 32 }
    highAvailability: { mode: 'Disabled' }
    backup: { backupRetentionDays: 7, geoRedundantBackup: 'Disabled' }
  }
}

resource pgDatabase 'Microsoft.DBforPostgreSQL/flexibleServers/databases@2023-06-01-preview' = {
  parent: postgres
  name: dbName
}

// Allow other Azure services (the Container App) to reach the flexible server.
resource pgAllowAzure 'Microsoft.DBforPostgreSQL/flexibleServers/firewallRules@2023-06-01-preview' = {
  parent: postgres
  name: 'AllowAzureServices'
  properties: { startIpAddress: '0.0.0.0', endIpAddress: '0.0.0.0' }
}

resource redis 'Microsoft.Cache/redis@2023-08-01' = if (deployRedis) {
  name: '${namePrefix}-redis'
  location: location
  properties: {
    sku: { name: 'Basic', family: 'C', capacity: 0 }
    enableNonSslPort: false
    minimumTlsVersion: '1.2'
  }
}

resource caeEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${namePrefix}-cae'
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logs.properties.customerId
        sharedKey: logs.listKeys().primarySharedKey
      }
    }
  }
}

var pgFqdn = postgres.properties.fullyQualifiedDomainName
var databaseUrl = 'postgresql+asyncpg://${postgresAdminLogin}:${postgresAdminPassword}@${pgFqdn}:5432/${dbName}?ssl=require'
// Sync URL for Alembic. Bare postgresql:// => psycopg2, the sync driver shipped in the image (matches
// the Fly control-plane). NOT postgresql+psycopg (v3) — that driver isn't installed, so migrations
// fail with "No module named 'psycopg'".
var databaseUrlSync = 'postgresql://${postgresAdminLogin}:${postgresAdminPassword}@${pgFqdn}:5432/${dbName}?sslmode=require'

// Shared by the app container AND the migration init container, so migrations run with the exact same
// config the app imports (avoids import-time env drift).
var apiEnv = [
  { name: 'DATABASE_URL', secretRef: 'database-url' }
  { name: 'DATABASE_URL_SYNC', secretRef: 'database-url-sync' }
  { name: 'ALGENTA_CONFIG_ENCRYPTION_KEY', secretRef: 'config-encryption-key' }
  { name: 'JWT_SECRET', secretRef: 'jwt-secret' }
  // Private profile — no phone-home; customer keeps the data plane.
  { name: 'ALGENTA_DEPLOYMENT_MODE', value: 'self_hosted' }
  { name: 'DISABLE_CLOUD', value: '1' }
  { name: 'DISABLE_TELEMETRY', value: '1' }
  { name: 'CONTROL_PLANE_URL', value: '' }
  // Native Azure Blob artifact store via the container's managed identity.
  { name: 'ALGENTA_RI_OBJECT_STORE', value: 'azure_blob' }
  { name: 'AZURE_BLOB_CONTAINER', value: blobContainer }
  { name: 'AZURE_STORAGE_ACCOUNT_URL', value: storage.properties.primaryEndpoints.blob }
  { name: 'AZURE_CLIENT_ID', value: identity.properties.clientId }
  { name: 'APPLICATIONINSIGHTS_CONNECTION_STRING', value: appInsights.properties.ConnectionString }
  // Entra identity (inert unless both are set). When set, the app auto-allowlists the Entra JWKS
  // host for egress (build_privacy_policy), so no manual ALGENTA_EGRESS_ALLOWLIST is needed.
  { name: 'ALGENTA_ENTRA_TENANT_ID', value: entraTenantId }
  { name: 'ALGENTA_ENTRA_AUDIENCE', value: entraAudience }
]

resource apiApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${namePrefix}-api'
  location: location
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: { '${identity.id}': {} }
  }
  properties: {
    managedEnvironmentId: caeEnv.id
    configuration: {
      registries: useAcr ? [
        { server: acrLoginServer, identity: identity.id }
      ] : []
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
      }
      secrets: [
        { name: 'database-url', value: databaseUrl }
        { name: 'database-url-sync', value: databaseUrlSync }
        {
          name: 'config-encryption-key'
          keyVaultUrl: secretConfigKey.properties.secretUri
          identity: identity.id
        }
        {
          name: 'jwt-secret'
          keyVaultUrl: secretJwt.properties.secretUri
          identity: identity.id
        }
      ]
    }
    template: {
      // Run Alembic to head BEFORE the app starts. The gateway has no other migration runner (unlike
      // the Fly control-plane's release_command), so without this its DB drifts behind the image and
      // routes 500 on missing tables. Init containers run to completion before the app container.
      initContainers: [
        {
          name: 'migrate'
          image: apiImage
          resources: { cpu: json('0.5'), memory: '1Gi' }
          command: [ 'python' ]
          args: [ '-m', 'alembic', '-c', 'apps/api_server/alembic.ini', 'upgrade', 'head' ]
          env: apiEnv
        }
      ]
      containers: [
        {
          name: 'api'
          image: apiImage
          resources: { cpu: json('1.0'), memory: '2Gi' }
          env: apiEnv
        }
      ]
      scale: { minReplicas: 1, maxReplicas: 3 }
    }
  }
  dependsOn: [ kvRole, storageRole, pgDatabase, acrRole ]
}

@description('The gateway base URL — point the Copilot/Excel/Foundry adapters here.')
output gatewayUrl string = 'https://${apiApp.properties.configuration.ingress.fqdn}'
@description('User-assigned managed identity client id (for Entra app-role assignments).')
output managedIdentityClientId string = identity.properties.clientId
@description('Blob container the decision artifacts are written to.')
output artifactContainer string = blobContainer
