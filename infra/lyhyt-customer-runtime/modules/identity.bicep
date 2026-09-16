param identityName string
param location string
param tags object

resource identity 'Microsoft.ManagedIdentity/userAssignedIdentities@2025-05-31-preview' = {
  name: identityName
  location: location
  tags: tags
}

output identityResourceId string = identity.id
output identityName string = identity.name
output identityClientId string = identity.properties.clientId
output identityPrincipalId string = identity.properties.principalId
