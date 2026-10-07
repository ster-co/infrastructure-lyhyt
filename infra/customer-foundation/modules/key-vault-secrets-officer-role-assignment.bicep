targetScope = 'resourceGroup'

param keyVaultResourceId string
param roleAssignmentName string
// Object ID of the enterprise application/service principal in this tenant.
param principalObjectId string

var keyVaultResourceIdSegments = split(keyVaultResourceId, '/')
var keyVaultName = keyVaultResourceIdSegments[8]
var keyVaultSecretsOfficerRoleDefinitionId = subscriptionResourceId('Microsoft.Authorization/roleDefinitions', 'b86a8fe4-44ce-4948-aee5-eccb2c155cd7')

resource keyVault 'Microsoft.KeyVault/vaults@2026-03-01-preview' existing = {
  name: keyVaultName
}

// Grants the customer-tenant migration service principal data-plane access to
// publish the customer foundation's safe configuration outputs.
resource roleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: roleAssignmentName
  scope: keyVault
  properties: {
    principalId: principalObjectId
    principalType: 'ServicePrincipal'
    roleDefinitionId: keyVaultSecretsOfficerRoleDefinitionId
  }
}

output roleAssignmentId string = roleAssignment.id
