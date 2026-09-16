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
