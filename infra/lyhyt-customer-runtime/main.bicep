targetScope = 'subscription'

@allowed([
  'dev'
  'tst'
  'acc'
  'prod'
])
param environment string

param customerCode string
param location string
param regionCode string
param vnetAddressPrefix string
@allowed([
  'Enabled'
  'Disabled'
])
param publicNetworkAccess string
param zoneRedundant bool

@allowed([
  'Allow'
  'Deny'
])
param functionHostStorageNetworkDefaultAction string = 'Allow'

param functionPlanSkuName string = 'Y1'
param functionPlanSkuTier string = 'Dynamic'
@minValue(0)
param functionPlanCapacity int = 0
param functionWorkerRuntime string = 'python'
param functionWorkerRuntimeVersion string = '3.11'

type functionConfigurationType = {
  customerTenantId: string
  customerHostname: string
  allowedGroupIds: array
  deploymentTier: string
}

param functionConfiguration functionConfigurationType = {
  customerTenantId: ''
  customerHostname: ''
  allowedGroupIds: []
  deploymentTier: 'standard'
}

type containerRegistryReferenceType = {
  // Canonical identity. The subscription, resource group, and registry name
  // are derived from this ID wherever Azure resources are scoped.
  resourceId: string
  // Application endpoint handoff; it must describe the registry in resourceId.
  loginServer: string
}

param containerRegistryReference containerRegistryReferenceType
param containerImage string

type keyVaultConfigurationType = {
  enabled: bool
  customerKeyVaultResourceId: string
  customerKeyVaultUri: string
  platformKeyVaultResourceId: string
  platformKeyVaultUri: string
  requireKeyVault: bool
}

param keyVaultConfiguration keyVaultConfigurationType = {
  enabled: false
  customerKeyVaultResourceId: ''
  customerKeyVaultUri: ''
  platformKeyVaultResourceId: ''
  platformKeyVaultUri: ''
  requireKeyVault: false
}
param enablePlatformKeyVaultRoleAssignment bool = false
param additionalTags object = {}

var commonTags = union({
  project: 'lyhyt'
  customerCode: customerCode
  environment: environment
  component: 'customer-runtime'
  managedBy: 'bicep'
}, additionalTags)

var customerRuntimeResourceGroupName = 'rg-lyhyt-${customerCode}-${environment}-${regionCode}'
var logAnalyticsWorkspaceName = 'log-lyhyt-${customerCode}-${environment}-${regionCode}'
var containerEnvironmentName = 'cae-lyhyt-${customerCode}-${environment}-${regionCode}'
var identityName = 'id-lyhyt-${customerCode}-api-${environment}'
var containerAppName = 'ca-lyhyt-${customerCode}-api-${environment}'
var compactCustomerCode = replace(toLower(customerCode), '-', '')
var functionPlanName = 'asp-lyhyt-${customerCode}-${environment}-${regionCode}'
var functionHostStorageAccountName = 'st${take(compactCustomerCode, 8)}fn${environment}${regionCode}'
var documentParserIdentityName = 'id-lyhyt-${customerCode}-document-parser-${environment}'
var mailboxSyncIdentityName = 'id-lyhyt-${customerCode}-mailbox-sync-${environment}'
var documentParserFunctionAppName = 'func-lyhyt-${customerCode}-document-parser-${environment}-${regionCode}-${uniqueString(subscription().id, customerCode, environment, regionCode, 'document-parser')}'
var mailboxSyncFunctionAppName = 'func-lyhyt-${customerCode}-mailbox-sync-${environment}-${regionCode}-${uniqueString(subscription().id, customerCode, environment, regionCode, 'mailbox-sync')}'
var functionHostStorageRoleDefinitionIds = [
  // Storage Blob Data Owner
  'b7e6dc6d-f1e8-4753-8033-0f276bb0955b'
  // Storage Queue Data Contributor
  '974c5e8b-45b9-4653-ba55-5f855dd0d3'
  // Storage Table Data Contributor
  '0a9a7e1f-bf94-4f9a-9ec5-1c16b5e4e9c9'
]
var containerRegistryResourceIdSegments = split(containerRegistryReference.resourceId, '/')
var containerRegistrySubscriptionId = containerRegistryResourceIdSegments[2]
var containerRegistryResourceGroupName = containerRegistryResourceIdSegments[4]
// Keep the disabled default parseable without pointing at a real vault. The
// role-assignment module is still conditional on integration being enabled.
var platformKeyVaultResourceIdForParsing = empty(keyVaultConfiguration.platformKeyVaultResourceId) ? '/subscriptions/${subscription().id}/resourceGroups/disabled/providers/Microsoft.KeyVault/vaults/disabled' : keyVaultConfiguration.platformKeyVaultResourceId
var platformKeyVaultResourceIdSegments = split(platformKeyVaultResourceIdForParsing, '/')
var platformKeyVaultSubscriptionId = platformKeyVaultResourceIdSegments[2]
var platformKeyVaultResourceGroupName = platformKeyVaultResourceIdSegments[4]
var acrPullRoleDefinitionId = subscriptionResourceId(containerRegistrySubscriptionId, 'Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
var keyVaultSecretsUserRoleDefinitionId = subscriptionResourceId(platformKeyVaultSubscriptionId, 'Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')
var acrPullRoleAssignmentName = guid(containerRegistryReference.resourceId, identityName, acrPullRoleDefinitionId)
var platformKeyVaultRoleAssignmentName = guid(keyVaultConfiguration.platformKeyVaultResourceId, identityName, keyVaultSecretsUserRoleDefinitionId)
var platformKeyVaultRoleAssignmentEnabled = enablePlatformKeyVaultRoleAssignment && keyVaultConfiguration.enabled

resource customerRuntimeResourceGroup 'Microsoft.Resources/resourceGroups@2025-04-01' = {
  name: customerRuntimeResourceGroupName
  location: location
  tags: commonTags
}

module functionHostStorage './modules/function-host-storage.bicep' = {
  name: 'deploy-function-host-storage-${customerCode}-${environment}'
  scope: customerRuntimeResourceGroup
  params: {
    storageAccountName: functionHostStorageAccountName
    location: location
    tags: union(commonTags, {
      component: 'customer-runtime-function-host-storage'
    })
    publicNetworkAccess: publicNetworkAccess
    networkDefaultAction: functionHostStorageNetworkDefaultAction
  }
}

module networking './modules/networking.bicep' = {
  name: 'deploy-networking-${customerCode}-${environment}'
  scope: customerRuntimeResourceGroup
  params: {
    customerCode: customerCode
    environment: environment
    location: location
    regionCode: regionCode
    vnetAddressPrefix: vnetAddressPrefix
    additionalTags: commonTags
  }
}

module monitoring './modules/monitoring.bicep' = {
  name: 'deploy-monitoring-${customerCode}-${environment}'
  scope: customerRuntimeResourceGroup
  params: {
    workspaceName: logAnalyticsWorkspaceName
    location: location
    tags: commonTags
  }
}

module containerEnvironment './modules/container-environment.bicep' = {
  name: 'deploy-container-environment-${customerCode}-${environment}'
  scope: customerRuntimeResourceGroup
  params: {
    environmentName: containerEnvironmentName
    location: location
    tags: commonTags
    logAnalyticsCustomerId: monitoring.outputs.workspaceCustomerId
    logAnalyticsSharedKey: monitoring.outputs.workspaceSharedKey
    infrastructureSubnetId: networking.outputs.containerAppsSubnetId
    publicNetworkAccess: publicNetworkAccess
    zoneRedundant: zoneRedundant
  }
}

module identity './modules/identity.bicep' = {
  name: 'deploy-identity-${customerCode}-${environment}'
  scope: customerRuntimeResourceGroup
  params: {
    identityName: identityName
    location: location
    tags: commonTags
  }
}

module documentParserIdentity './modules/identity.bicep' = {
  name: 'deploy-document-parser-identity-${customerCode}-${environment}'
  scope: customerRuntimeResourceGroup
  params: {
    identityName: documentParserIdentityName
    location: location
    tags: commonTags
  }
}

module mailboxSyncIdentity './modules/identity.bicep' = {
  name: 'deploy-mailbox-sync-identity-${customerCode}-${environment}'
  scope: customerRuntimeResourceGroup
  params: {
    identityName: mailboxSyncIdentityName
    location: location
    tags: commonTags
  }
}

module functionPlan './modules/function-plan.bicep' = {
  name: 'deploy-function-plan-${customerCode}-${environment}'
  scope: customerRuntimeResourceGroup
  params: {
    functionPlanName: functionPlanName
    location: location
    tags: commonTags
    skuName: functionPlanSkuName
    skuTier: functionPlanSkuTier
    skuCapacity: functionPlanCapacity
  }
}

module documentParserHostStorageRoleAssignment './modules/storage-data-role-assignment.bicep' = {
  name: 'assign-document-parser-host-storage-${customerCode}-${environment}'
  scope: customerRuntimeResourceGroup
  params: {
    storageAccountResourceId: functionHostStorage.outputs.storageAccountResourceId
    roleDefinitionIds: functionHostStorageRoleDefinitionIds
    principalId: documentParserIdentity.outputs.identityPrincipalId
  }
}

module mailboxSyncHostStorageRoleAssignment './modules/storage-data-role-assignment.bicep' = {
  name: 'assign-mailbox-sync-host-storage-${customerCode}-${environment}'
  scope: customerRuntimeResourceGroup
  params: {
    storageAccountResourceId: functionHostStorage.outputs.storageAccountResourceId
    roleDefinitionIds: functionHostStorageRoleDefinitionIds
    principalId: mailboxSyncIdentity.outputs.identityPrincipalId
  }
}

module acrPullRoleAssignment './modules/role-assignment.bicep' = {
  name: 'assign-acr-pull-${customerCode}-${environment}'
  scope: resourceGroup(containerRegistrySubscriptionId, containerRegistryResourceGroupName)
  params: {
    containerRegistryResourceId: containerRegistryReference.resourceId
    roleAssignmentName: acrPullRoleAssignmentName
    principalId: identity.outputs.identityPrincipalId
  }
}

module platformKeyVaultRoleAssignment './modules/key-vault-role-assignment.bicep' = if (platformKeyVaultRoleAssignmentEnabled) {
  name: 'assign-platform-key-vault-secrets-user-${customerCode}-${environment}'
  scope: resourceGroup(platformKeyVaultSubscriptionId, platformKeyVaultResourceGroupName)
  params: {
    keyVaultResourceId: keyVaultConfiguration.platformKeyVaultResourceId
    roleAssignmentName: platformKeyVaultRoleAssignmentName
    principalId: identity.outputs.identityPrincipalId
  }
}

module containerApp './modules/container-app.bicep' = {
  name: 'deploy-container-app-${customerCode}-${environment}'
  scope: customerRuntimeResourceGroup
  dependsOn: [
    acrPullRoleAssignment
    platformKeyVaultRoleAssignment
  ]
  params: {
    containerAppName: containerAppName
    location: location
    tags: commonTags
    containerEnvironmentId: containerEnvironment.outputs.containerEnvironmentId
    identityResourceId: identity.outputs.identityResourceId
    containerRegistryLoginServer: containerRegistryReference.loginServer
    containerImage: containerImage
    customerCode: customerCode
    environment: environment
    keyVaultIntegrationEnabled: keyVaultConfiguration.enabled
    managedIdentityClientId: identity.outputs.identityClientId
    customerKeyVaultUri: keyVaultConfiguration.customerKeyVaultUri
    platformKeyVaultUri: keyVaultConfiguration.platformKeyVaultUri
    requireKeyVault: keyVaultConfiguration.requireKeyVault
  }
}

module documentParserFunctionApp './modules/function-app.bicep' = {
  name: 'deploy-document-parser-function-app-${customerCode}-${environment}'
  scope: customerRuntimeResourceGroup
  dependsOn: [
    documentParserHostStorageRoleAssignment
  ]
  params: {
    functionAppName: documentParserFunctionAppName
    location: location
    tags: commonTags
    functionPlanResourceId: functionPlan.outputs.functionPlanResourceId
    alwaysOn: functionPlanSkuName != 'Y1'
    identityResourceId: documentParserIdentity.outputs.identityResourceId
    identityClientId: documentParserIdentity.outputs.identityClientId
    functionWorkload: 'document-parser'
    functionWorkerRuntime: functionWorkerRuntime
    functionWorkerRuntimeVersion: functionWorkerRuntimeVersion
    customerCode: customerCode
    environment: environment
    customerTenantId: functionConfiguration.customerTenantId
    customerHostname: functionConfiguration.customerHostname
    allowedGroupIds: functionConfiguration.allowedGroupIds
    deploymentTier: functionConfiguration.deploymentTier
    providerKeyVaultUri: keyVaultConfiguration.platformKeyVaultUri
    hostStorageBlobServiceUri: functionHostStorage.outputs.blobServiceUri
    hostStorageQueueServiceUri: functionHostStorage.outputs.queueServiceUri
    hostStorageTableServiceUri: functionHostStorage.outputs.tableServiceUri
  }
}

module mailboxSyncFunctionApp './modules/function-app.bicep' = {
  name: 'deploy-mailbox-sync-function-app-${customerCode}-${environment}'
  scope: customerRuntimeResourceGroup
  dependsOn: [
    mailboxSyncHostStorageRoleAssignment
  ]
  params: {
    functionAppName: mailboxSyncFunctionAppName
    location: location
    tags: commonTags
    functionPlanResourceId: functionPlan.outputs.functionPlanResourceId
    alwaysOn: functionPlanSkuName != 'Y1'
    identityResourceId: mailboxSyncIdentity.outputs.identityResourceId
    identityClientId: mailboxSyncIdentity.outputs.identityClientId
    functionWorkload: 'mailbox-sync'
    functionWorkerRuntime: functionWorkerRuntime
    functionWorkerRuntimeVersion: functionWorkerRuntimeVersion
    customerCode: customerCode
    environment: environment
    customerTenantId: functionConfiguration.customerTenantId
    customerHostname: functionConfiguration.customerHostname
    allowedGroupIds: functionConfiguration.allowedGroupIds
    deploymentTier: functionConfiguration.deploymentTier
    providerKeyVaultUri: keyVaultConfiguration.platformKeyVaultUri
    hostStorageBlobServiceUri: functionHostStorage.outputs.blobServiceUri
    hostStorageQueueServiceUri: functionHostStorage.outputs.queueServiceUri
    hostStorageTableServiceUri: functionHostStorage.outputs.tableServiceUri
  }
}

output customerRuntimeResourceGroupName string = customerRuntimeResourceGroup.name
output logAnalyticsWorkspaceId string = monitoring.outputs.workspaceId
output containerEnvironmentId string = containerEnvironment.outputs.containerEnvironmentId
output containerEnvironmentDefaultDomain string = containerEnvironment.outputs.containerEnvironmentDefaultDomain
output identityResourceId string = identity.outputs.identityResourceId
output identityName string = identity.outputs.identityName
output identityClientId string = identity.outputs.identityClientId
output identityPrincipalId string = identity.outputs.identityPrincipalId
output containerAppName string = containerApp.outputs.containerAppName
output containerAppResourceId string = containerApp.outputs.containerAppResourceId
output containerAppFqdn string = containerApp.outputs.containerAppFqdn
output deployedImage string = containerApp.outputs.deployedImage
output functionPlanResourceId string = functionPlan.outputs.functionPlanResourceId
output functionHostStorageResourceId string = functionHostStorage.outputs.storageAccountResourceId
output functionHostStorageAccountName string = functionHostStorage.outputs.storageAccountName
output documentParserFunctionAppName string = documentParserFunctionApp.outputs.functionAppName
output documentParserFunctionAppResourceId string = documentParserFunctionApp.outputs.functionAppResourceId
output documentParserFunctionAppHostname string = documentParserFunctionApp.outputs.functionAppHostname
output documentParserIdentityResourceId string = documentParserIdentity.outputs.identityResourceId
output documentParserIdentityClientId string = documentParserIdentity.outputs.identityClientId
output documentParserIdentityPrincipalId string = documentParserIdentity.outputs.identityPrincipalId
output mailboxSyncFunctionAppName string = mailboxSyncFunctionApp.outputs.functionAppName
output mailboxSyncFunctionAppResourceId string = mailboxSyncFunctionApp.outputs.functionAppResourceId
output mailboxSyncFunctionAppHostname string = mailboxSyncFunctionApp.outputs.functionAppHostname
output mailboxSyncIdentityResourceId string = mailboxSyncIdentity.outputs.identityResourceId
output mailboxSyncIdentityClientId string = mailboxSyncIdentity.outputs.identityClientId
output mailboxSyncIdentityPrincipalId string = mailboxSyncIdentity.outputs.identityPrincipalId
