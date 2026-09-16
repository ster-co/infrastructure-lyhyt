targetScope = 'resourceGroup'

param containerRegistryResourceId string
param roleAssignmentName string
param principalId string

var containerRegistryResourceIdSegments = split(containerRegistryResourceId, '/')
var containerRegistryName = containerRegistryResourceIdSegments[8]
// The module is invoked at the resource group parsed from the canonical ID.
// The built-in role ID therefore resolves in the registry's subscription.
var acrPullRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '7f951dda-4ed3-4680-a7ca-43fe172d538d')

resource containerRegistry 'Microsoft.ContainerRegistry/registries@2025-11-01' existing = {
  name: containerRegistryName
}

resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: roleAssignmentName
  scope: containerRegistry
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: acrPullRoleDefinitionId
  }
}

output roleAssignmentId string = roleAssignment.id
