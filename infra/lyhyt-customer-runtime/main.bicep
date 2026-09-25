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

type functionRuntimeConfigurationType = {
  documentParser: {
    workerRuntime: string
    workerRuntimeVersion: string
  }
  mailboxSync: {
    workerRuntime: string
    workerRuntimeVersion: string
  }
  sdb: {
    workerRuntime: string
    workerRuntimeVersion: string
  }
}

param functionRuntimeConfiguration functionRuntimeConfigurationType
param enableDoclingResources bool = false

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
var applicationInsightsName = 'appi-lyhyt-${customerCode}-${environment}-${regionCode}'
var documentParserFunctionPlanName = 'asp-lyhyt-${customerCode}-document-parser-${environment}-${regionCode}'
var mailboxSyncFunctionPlanName = 'asp-lyhyt-${customerCode}-mailbox-sync-${environment}-${regionCode}'
var sdbFunctionPlanName = 'asp-lyhyt-${customerCode}-sdb-${environment}-${regionCode}'
var functionHostStorageAccountName = 'st${take(compactCustomerCode, 8)}fn${environment}${regionCode}'
var documentParserIdentityName = 'id-lyhyt-${customerCode}-document-parser-${environment}'
var mailboxSyncIdentityName = 'id-lyhyt-${customerCode}-mailbox-sync-${environment}'
var sdbIdentityName = 'id-lyhyt-${customerCode}-sdb-${environment}'
var documentParserFunctionAppName = 'func-lyhyt-${customerCode}-document-parser-${environment}-${regionCode}-${uniqueString(subscription().id, customerCode, environment, regionCode, 'document-parser')}'
var mailboxSyncFunctionAppName = 'func-lyhyt-${customerCode}-mailbox-sync-${environment}-${regionCode}-${uniqueString(subscription().id, customerCode, environment, regionCode, 'mailbox-sync')}'
var sdbFunctionAppName = 'func-lyhyt-${customerCode}-sdb-${environment}-${regionCode}-${uniqueString(subscription().id, customerCode, environment, regionCode, 'sdb')}'
var documentParserDeploymentContainerName = 'deployment-document-parser'
var mailboxSyncDeploymentContainerName = 'deployment-mailbox-sync'
var sdbDeploymentContainerName = 'deployment-sdb'
var functionBlobContainerNames = concat([
  documentParserDeploymentContainerName
  mailboxSyncDeploymentContainerName
  sdbDeploymentContainerName
  'di-cache'
  'sync-reports'
  'background-job-status'
], enableDoclingResources ? [
  'docling-jobs'
] : [])
var functionQueueNames = concat([
  'sync-jobs'
  'sync-jobs-poison'
  'extraction-jobs'
  'extraction-jobs-poison'
  'offerte-flow-jobs'
  'offerte-flow-jobs-poison'
], enableDoclingResources ? [
  'docling-jobs'
] : [])
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
var documentParserPlatformKeyVaultRoleAssignmentName = guid(keyVaultConfiguration.platformKeyVaultResourceId, documentParserIdentityName, keyVaultSecretsUserRoleDefinitionId)
var mailboxSyncPlatformKeyVaultRoleAssignmentName = guid(keyVaultConfiguration.platformKeyVaultResourceId, mailboxSyncIdentityName, keyVaultSecretsUserRoleDefinitionId)
var sdbPlatformKeyVaultRoleAssignmentName = guid(keyVaultConfiguration.platformKeyVaultResourceId, sdbIdentityName, keyVaultSecretsUserRoleDefinitionId)
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
    blobContainerNames: functionBlobContainerNames
    queueNames: functionQueueNames
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

module applicationInsights './modules/application-insights.bicep' = {
  name: 'deploy-application-insights-${customerCode}-${environment}'
  scope: customerRuntimeResourceGroup
  params: {
    componentName: applicationInsightsName
    location: location
    tags: commonTags
    workspaceResourceId: monitoring.outputs.workspaceId
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

module sdbIdentity './modules/identity.bicep' = {
  name: 'deploy-sdb-identity-${customerCode}-${environment}'
  scope: customerRuntimeResourceGroup
  params: {
    identityName: sdbIdentityName
    location: location
    tags: commonTags
  }
}

module documentParserFunctionPlan './modules/function-plan.bicep' = {
  name: 'deploy-document-parser-function-plan-${customerCode}-${environment}'
  scope: customerRuntimeResourceGroup
  params: {
    functionPlanName: documentParserFunctionPlanName
    location: location
    tags: commonTags
    skuName: 'FC1'
    skuTier: 'FlexConsumption'
    skuCapacity: 0
  }
}

module mailboxSyncFunctionPlan './modules/function-plan.bicep' = {
  name: 'deploy-mailbox-sync-function-plan-${customerCode}-${environment}'
  scope: customerRuntimeResourceGroup
  params: {
    functionPlanName: mailboxSyncFunctionPlanName
    location: location
    tags: commonTags
    skuName: 'FC1'
    skuTier: 'FlexConsumption'
    skuCapacity: 0
  }
}

module sdbFunctionPlan './modules/function-plan.bicep' = {
  name: 'deploy-sdb-function-plan-${customerCode}-${environment}'
  scope: customerRuntimeResourceGroup
  params: {
    functionPlanName: sdbFunctionPlanName
    location: location
    tags: commonTags
    skuName: 'FC1'
    skuTier: 'FlexConsumption'
    skuCapacity: 0
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

module sdbHostStorageRoleAssignment './modules/storage-data-role-assignment.bicep' = {
  name: 'assign-sdb-host-storage-${customerCode}-${environment}'
  scope: customerRuntimeResourceGroup
  params: {
    storageAccountResourceId: functionHostStorage.outputs.storageAccountResourceId
    roleDefinitionIds: functionHostStorageRoleDefinitionIds
    principalId: sdbIdentity.outputs.identityPrincipalId
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

module documentParserPlatformKeyVaultRoleAssignment './modules/key-vault-role-assignment.bicep' = if (platformKeyVaultRoleAssignmentEnabled) {
  name: 'assign-document-parser-platform-key-vault-secrets-user-${customerCode}-${environment}'
  scope: resourceGroup(platformKeyVaultSubscriptionId, platformKeyVaultResourceGroupName)
  params: {
    keyVaultResourceId: keyVaultConfiguration.platformKeyVaultResourceId
    roleAssignmentName: documentParserPlatformKeyVaultRoleAssignmentName
    principalId: documentParserIdentity.outputs.identityPrincipalId
  }
}

module mailboxSyncPlatformKeyVaultRoleAssignment './modules/key-vault-role-assignment.bicep' = if (platformKeyVaultRoleAssignmentEnabled) {
  name: 'assign-mailbox-sync-platform-key-vault-secrets-user-${customerCode}-${environment}'
  scope: resourceGroup(platformKeyVaultSubscriptionId, platformKeyVaultResourceGroupName)
  params: {
    keyVaultResourceId: keyVaultConfiguration.platformKeyVaultResourceId
    roleAssignmentName: mailboxSyncPlatformKeyVaultRoleAssignmentName
    principalId: mailboxSyncIdentity.outputs.identityPrincipalId
  }
}

module sdbPlatformKeyVaultRoleAssignment './modules/key-vault-role-assignment.bicep' = if (platformKeyVaultRoleAssignmentEnabled) {
  name: 'assign-sdb-platform-key-vault-secrets-user-${customerCode}-${environment}'
  scope: resourceGroup(platformKeyVaultSubscriptionId, platformKeyVaultResourceGroupName)
  params: {
    keyVaultResourceId: keyVaultConfiguration.platformKeyVaultResourceId
    roleAssignmentName: sdbPlatformKeyVaultRoleAssignmentName
    principalId: sdbIdentity.outputs.identityPrincipalId
  }
}

module containerApp './modules/container-app.bicep' = {
  name: 'deploy-container-app-${customerCode}-${environment}'
  scope: customerRuntimeResourceGroup
  dependsOn: [
    acrPullRoleAssignment
    platformKeyVaultRoleAssignment
    documentParserPlatformKeyVaultRoleAssignment
    mailboxSyncPlatformKeyVaultRoleAssignment
    sdbPlatformKeyVaultRoleAssignment
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
    documentParserPlatformKeyVaultRoleAssignment
  ]
  params: {
    functionAppName: documentParserFunctionAppName
    location: location
    tags: commonTags
    functionPlanResourceId: documentParserFunctionPlan.outputs.functionPlanResourceId
    identityResourceId: documentParserIdentity.outputs.identityResourceId
    identityClientId: documentParserIdentity.outputs.identityClientId
    functionWorkerRuntime: functionRuntimeConfiguration.documentParser.workerRuntime
    functionWorkerRuntimeVersion: functionRuntimeConfiguration.documentParser.workerRuntimeVersion
    deploymentStorageContainerUri: '${functionHostStorage.outputs.blobServiceUri}${documentParserDeploymentContainerName}'
    applicationInsightsConnectionString: applicationInsights.outputs.connectionString
    keyVaultIntegrationEnabled: keyVaultConfiguration.enabled
    customerKeyVaultUri: keyVaultConfiguration.customerKeyVaultUri
    providerKeyVaultUri: keyVaultConfiguration.platformKeyVaultUri
    requireKeyVault: keyVaultConfiguration.requireKeyVault
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
    mailboxSyncPlatformKeyVaultRoleAssignment
  ]
  params: {
    functionAppName: mailboxSyncFunctionAppName
    location: location
    tags: commonTags
    functionPlanResourceId: mailboxSyncFunctionPlan.outputs.functionPlanResourceId
    identityResourceId: mailboxSyncIdentity.outputs.identityResourceId
    identityClientId: mailboxSyncIdentity.outputs.identityClientId
    functionWorkerRuntime: functionRuntimeConfiguration.mailboxSync.workerRuntime
    functionWorkerRuntimeVersion: functionRuntimeConfiguration.mailboxSync.workerRuntimeVersion
    deploymentStorageContainerUri: '${functionHostStorage.outputs.blobServiceUri}${mailboxSyncDeploymentContainerName}'
    applicationInsightsConnectionString: applicationInsights.outputs.connectionString
    keyVaultIntegrationEnabled: keyVaultConfiguration.enabled
    customerKeyVaultUri: keyVaultConfiguration.customerKeyVaultUri
    providerKeyVaultUri: keyVaultConfiguration.platformKeyVaultUri
    requireKeyVault: keyVaultConfiguration.requireKeyVault
    hostStorageBlobServiceUri: functionHostStorage.outputs.blobServiceUri
    hostStorageQueueServiceUri: functionHostStorage.outputs.queueServiceUri
    hostStorageTableServiceUri: functionHostStorage.outputs.tableServiceUri
  }
}

module sdbFunctionApp './modules/function-app.bicep' = {
  name: 'deploy-sdb-function-app-${customerCode}-${environment}'
  scope: customerRuntimeResourceGroup
  dependsOn: [
    sdbHostStorageRoleAssignment
    sdbPlatformKeyVaultRoleAssignment
  ]
  params: {
    functionAppName: sdbFunctionAppName
    location: location
    tags: commonTags
    functionPlanResourceId: sdbFunctionPlan.outputs.functionPlanResourceId
    identityResourceId: sdbIdentity.outputs.identityResourceId
    identityClientId: sdbIdentity.outputs.identityClientId
    functionWorkerRuntime: functionRuntimeConfiguration.sdb.workerRuntime
    functionWorkerRuntimeVersion: functionRuntimeConfiguration.sdb.workerRuntimeVersion
    deploymentStorageContainerUri: '${functionHostStorage.outputs.blobServiceUri}${sdbDeploymentContainerName}'
    applicationInsightsConnectionString: applicationInsights.outputs.connectionString
    keyVaultIntegrationEnabled: keyVaultConfiguration.enabled
    customerKeyVaultUri: keyVaultConfiguration.customerKeyVaultUri
    providerKeyVaultUri: keyVaultConfiguration.platformKeyVaultUri
    requireKeyVault: keyVaultConfiguration.requireKeyVault
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
output applicationInsightsResourceId string = applicationInsights.outputs.resourceId
output functionHostStorageResourceId string = functionHostStorage.outputs.storageAccountResourceId
output functionHostStorageAccountName string = functionHostStorage.outputs.storageAccountName
output documentParserFunctionPlanResourceId string = documentParserFunctionPlan.outputs.functionPlanResourceId
output mailboxSyncFunctionPlanResourceId string = mailboxSyncFunctionPlan.outputs.functionPlanResourceId
output sdbFunctionPlanResourceId string = sdbFunctionPlan.outputs.functionPlanResourceId
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
output sdbFunctionAppName string = sdbFunctionApp.outputs.functionAppName
output sdbFunctionAppResourceId string = sdbFunctionApp.outputs.functionAppResourceId
output sdbFunctionAppHostname string = sdbFunctionApp.outputs.functionAppHostname
output sdbIdentityResourceId string = sdbIdentity.outputs.identityResourceId
output sdbIdentityClientId string = sdbIdentity.outputs.identityClientId
output sdbIdentityPrincipalId string = sdbIdentity.outputs.identityPrincipalId
