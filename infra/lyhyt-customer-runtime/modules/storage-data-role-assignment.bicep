targetScope = 'resourceGroup'

param storageAccountResourceId string
param roleDefinitionIds array
param principalId string

var storageAccountResourceIdSegments = split(storageAccountResourceId, '/')
var storageAccountName = storageAccountResourceIdSegments[8]

resource storageAccount 'Microsoft.Storage/storageAccounts@2026-04-01' existing = {
  name: storageAccountName
}

resource roleAssignments 'Microsoft.Authorization/roleAssignments@2022-04-01' = [for roleDefinitionId in roleDefinitionIds: {
  name: guid(storageAccount.id, principalId, roleDefinitionId)
  scope: storageAccount
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId('Microsoft.Authorization/roleDefinitions', roleDefinitionId)
  }
}]
