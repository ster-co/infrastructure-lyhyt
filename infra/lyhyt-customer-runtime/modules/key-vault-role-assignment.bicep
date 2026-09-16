targetScope = 'resourceGroup'

param keyVaultResourceId string
param roleAssignmentName string
param principalId string

var keyVaultResourceIdSegments = split(keyVaultResourceId, '/')
var keyVaultName = keyVaultResourceIdSegments[8]
// The module is invoked at the resource group parsed from the canonical ID,
// so the role definition is resolved in the vault's subscription too.
var keyVaultSecretsUserRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', '4633458b-17de-408a-b874-0445c86b69e6')

resource keyVault 'Microsoft.KeyVault/vaults@2026-03-01-preview' existing = {
  name: keyVaultName
}

// Key Vault Secrets User: read-only data-plane access for the runtime UAMI.
resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: roleAssignmentName
  scope: keyVault
  properties: {
    principalId: principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: keyVaultSecretsUserRoleDefinitionId
  }
}

output roleAssignmentId string = roleAssignment.id
