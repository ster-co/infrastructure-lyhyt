targetScope = 'subscription'

@minLength(2)
@maxLength(12)
param customerCode string

@allowed([
  'tst'
  'acc'
  'prod'
])
param environment string

param location string
param regionCode string
param customerTenantId string

param sqlEntraAdministratorLogin string
param sqlEntraAdministratorObjectId string
param sqlEntraAdministratorPrincipalType string = 'User'
param sqlEntraAdministratorTenantId string
param sqlEntraOnlyAuthentication bool = true

// Generic customer-side handoff. For the same-tenant pilot this is the
// LYHYT runtime UAMI principal ID. In the future cross-tenant architecture it
// can be a customer-tenant service-principal object ID created through WIF.
param runtimeAccessPrincipalId string = ''
param enableSameTenantRuntimeKeyVaultRoleAssignment bool = false

param storageContainerNames array
param aiDeployments array
param additionalTags object = {}

@allowed([
  'Enabled'
  'Disabled'
])
param publicNetworkAccess string = 'Enabled'

@allowed([
  'Allow'
  'Deny'
])
param storageNetworkDefaultAction string = 'Allow'

@allowed([
  'Allow'
  'Deny'
])
param keyVaultNetworkDefaultAction string = 'Deny'

param keyVaultEnablePurgeProtection bool = true

@minValue(7)
@maxValue(90)
param keyVaultSoftDeleteRetentionInDays int = 7

var compactCustomerCode = replace(toLower(customerCode), '-', '')
var commonTags = union({
    project: 'lyhyt'
    customer: customerCode
    environment: environment
    managedBy: 'bicep'
    ownershipBoundary: 'customer'
    component: 'customer-foundation'
  }, additionalTags)

var customerResourceGroupName = 'rg-${customerCode}-foundation-${environment}-${regionCode}'
var storageAccountName = 'st${compactCustomerCode}${environment}${regionCode}'
// Keep customer identity out of the name itself: customerCode and regionCode
// are bounded for this deployment, but the vault name must remain globally
// valid even when those inputs change shape in future entry points.
var keyVaultName = 'kvc${uniqueString(subscription().id, customerResourceGroupName, customerCode, environment, regionCode)}'
var sqlServerName = 'sql-${customerCode}-${environment}-${regionCode}'
var sqlDatabaseName = 'sqldb-${customerCode}-${environment}'
var searchServiceName = 'search-${customerCode}-${environment}-${regionCode}'
var aiServicesName = 'ai-${customerCode}-${environment}-${regionCode}'
var documentIntelligenceName = 'di-${customerCode}-${environment}-${regionCode}'
var keyVaultSecretsUserRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')

resource customerResourceGroup 'Microsoft.Resources/resourceGroups@2025-04-01' = {
  name: customerResourceGroupName
  location: location
  tags: commonTags
}

module storage './modules/storage.bicep' = {
  name: 'customer-foundation-storage'
  scope: customerResourceGroup
  params: {
    storageAccountName: storageAccountName
    location: location
    tags: commonTags
    containerNames: storageContainerNames
    publicNetworkAccess: publicNetworkAccess
    networkDefaultAction: storageNetworkDefaultAction
  }
}

module keyVault './modules/key-vault.bicep' = {
  name: 'customer-foundation-key-vault'
  scope: customerResourceGroup
  params: {
    keyVaultName: keyVaultName
    location: location
    tenantId: customerTenantId
    tags: commonTags
    publicNetworkAccess: publicNetworkAccess
    networkDefaultAction: keyVaultNetworkDefaultAction
    softDeleteRetentionInDays: keyVaultSoftDeleteRetentionInDays
    enablePurgeProtection: keyVaultEnablePurgeProtection
  }
}

module sameTenantRuntimeKeyVaultAccess './modules/key-vault-role-assignment.bicep' = if (enableSameTenantRuntimeKeyVaultRoleAssignment) {
  name: 'assign-kv-access-${customerCode}-${environment}'
  scope: customerResourceGroup
  params: {
    keyVaultResourceId: keyVault.outputs.keyVaultResourceId
    roleAssignmentName: guid(keyVault.outputs.keyVaultResourceId, runtimeAccessPrincipalId, keyVaultSecretsUserRoleDefinitionId)
    principalId: runtimeAccessPrincipalId
  }
}

module sql './modules/sql.bicep' = {
  name: 'customer-foundation-sql'
  scope: customerResourceGroup
  params: {
    sqlServerName: sqlServerName
    sqlDatabaseName: sqlDatabaseName
    location: location
    tags: commonTags
    sqlEntraAdministratorLogin: sqlEntraAdministratorLogin
    sqlEntraAdministratorObjectId: sqlEntraAdministratorObjectId
    sqlEntraAdministratorPrincipalType: sqlEntraAdministratorPrincipalType
    sqlEntraAdministratorTenantId: sqlEntraAdministratorTenantId
    sqlEntraOnlyAuthentication: sqlEntraOnlyAuthentication
    publicNetworkAccess: publicNetworkAccess
  }
}

module search './modules/search.bicep' = {
  name: 'customer-foundation-search'
  scope: customerResourceGroup
  params: {
    searchServiceName: searchServiceName
    location: location
    tags: commonTags
    publicNetworkAccess: publicNetworkAccess
  }
}

module ai './modules/ai.bicep' = {
  name: 'customer-foundation-ai'
  scope: customerResourceGroup
  params: {
    aiServicesName: aiServicesName
    documentIntelligenceName: documentIntelligenceName
    location: location
    tags: commonTags
    deployments: aiDeployments
    publicNetworkAccess: publicNetworkAccess
  }
}

output customerResourceGroupName string = customerResourceGroup.name
output storageAccountResourceId string = storage.outputs.storageAccountResourceId
output storageAccountName string = storage.outputs.storageAccountName
output blobEndpoint string = storage.outputs.blobEndpoint
output storageContainerNames array = storage.outputs.containerNames
output customerKeyVaultResourceId string = keyVault.outputs.keyVaultResourceId
output customerKeyVaultName string = keyVault.outputs.keyVaultName
output customerKeyVaultUri string = keyVault.outputs.keyVaultUri
output sqlServerResourceId string = sql.outputs.sqlServerResourceId
output sqlServerFqdn string = sql.outputs.sqlServerFqdn
output sqlDatabaseResourceId string = sql.outputs.sqlDatabaseResourceId
output sqlDatabaseName string = sql.outputs.sqlDatabaseName
output searchServiceResourceId string = search.outputs.searchServiceResourceId
output searchServiceName string = search.outputs.searchServiceName
output searchEndpoint string = search.outputs.searchEndpoint
output aiServicesResourceId string = ai.outputs.aiServicesResourceId
output aiEndpoint string = ai.outputs.aiEndpoint
output documentIntelligenceResourceId string = ai.outputs.documentIntelligenceResourceId
output documentIntelligenceEndpoint string = ai.outputs.documentIntelligenceEndpoint
output gpt5DeploymentName string = ai.outputs.deploymentNames[0]
output gpt54DeploymentName string = ai.outputs.deploymentNames[1]
output gpt5MiniDeploymentName string = ai.outputs.deploymentNames[2]
output textEmbedding3LargeDeploymentName string = ai.outputs.deploymentNames[3]
