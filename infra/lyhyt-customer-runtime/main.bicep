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
param containerRegistryName string
param containerRegistryResourceGroupName string
param containerRegistryLoginServer string
param containerImage string
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
var acrPullRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')
var acrPullRoleAssignmentName = guid(containerRegistry.id, identityName, acrPullRoleDefinitionId)

resource customerRuntimeResourceGroup 'Microsoft.Resources/resourceGroups@2025-04-01' = {
  name: customerRuntimeResourceGroupName
  location: location
  tags: commonTags
}

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2025-11-01' existing = {
  name: containerRegistryName
  scope: resourceGroup(containerRegistryResourceGroupName)
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
  scope: resourceGroup(containerRegistryResourceGroupName)
  params: {
    containerRegistryName: containerRegistryName
    roleAssignmentName: acrPullRoleAssignmentName
    principalId: identity.outputs.identityPrincipalId
    roleDefinitionId: acrPullRoleDefinitionId
  }
}

module containerApp './modules/container-app.bicep' = {
  name: 'deploy-container-app-${customerCode}-${environment}'
  scope: customerRuntimeResourceGroup
  dependsOn: [
    acrPullRoleAssignment
  ]
  params: {
    containerAppName: containerAppName
    location: location
    tags: commonTags
    containerEnvironmentId: containerEnvironment.outputs.containerEnvironmentId
    identityResourceId: identity.outputs.identityResourceId
    containerRegistryLoginServer: containerRegistryLoginServer
    containerImage: containerImage
    customerCode: customerCode
    environment: environment
  }
}

output customerRuntimeResourceGroupName string = customerRuntimeResourceGroup.name
output logAnalyticsWorkspaceId string = monitoring.outputs.workspaceId
output containerEnvironmentId string = containerEnvironment.outputs.containerEnvironmentId
output containerEnvironmentDefaultDomain string = containerEnvironment.outputs.containerEnvironmentDefaultDomain
output identityResourceId string = identity.outputs.identityResourceId
output identityClientId string = identity.outputs.identityClientId
output identityPrincipalId string = identity.outputs.identityPrincipalId
output containerAppName string = containerApp.outputs.containerAppName
output containerAppResourceId string = containerApp.outputs.containerAppResourceId
output containerAppFqdn string = containerApp.outputs.containerAppFqdn
output deployedImage string = containerApp.outputs.deployedImage
