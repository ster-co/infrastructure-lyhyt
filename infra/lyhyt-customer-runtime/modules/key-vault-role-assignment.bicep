targetScope = 'resourceGroup'

param keyVaultResourceId string
param roleAssignmentName string
param principalId string
param roleDefinitionId string = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')

var keyVaultResourceIdSegments = split(keyVaultResourceId, '/')
var keyVaultName = keyVaultResourceIdSegments[8]
// The module is invoked at the resource group parsed from the canonical ID,
// so the role definition is resolved in the vault's subscription too.

resource keyVault 'Microsoft.KeyVault/vaults@2026-03-01-preview' existing = {
  name: keyVaultName
}

// The default role is Key Vault Secrets User: read-only data-plane access.
resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: roleAssignmentName
  scope: keyVault
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: roleDefinitionId
  }
}

output roleAssignmentId string = roleAssignment.id
