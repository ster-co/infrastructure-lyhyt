param containerAppName string
param location string
param tags object
param containerEnvironmentId string
param identityResourceId string
param containerRegistryLoginServer string
param containerImage string
param customerCode string
param environment string
param keyVaultIntegrationEnabled bool
param managedIdentityClientId string
param customerKeyVaultUri string
param platformKeyVaultUri string
param requireKeyVault bool

var keyVaultEnvironmentVariables = keyVaultIntegrationEnabled ? [
  {
    name: 'AZURE_CLIENT_ID'
    value: managedIdentityClientId
  }
  {
    name: 'CLIENT_KEY_VAULT_URI'
    value: customerKeyVaultUri
  }
  {
    name: 'PLATFORM_KEY_VAULT_URI'
    value: platformKeyVaultUri
  }
  {
    name: 'REQUIRE_KEY_VAULT'
    value: requireKeyVault ? 'true' : 'false'
  }
] : []

resource containerApp 'Microsoft.App/containerapps@2026-01-01' = {
  name: containerAppName
  location: location
  tags: tags
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityResourceId}': {}
    }
  }
  properties: {
    configuration: {
      activeRevisionsMode: 'Single'
      ingress: {
        allowInsecure: false
        external: true
        targetPort: 80
        traffic: [
          {
            latestRevision: true
            weight: 100
          }
        ]
        transport: 'Auto'
      }
      registries: [
        {
          identity: identityResourceId
          server: containerRegistryLoginServer
        }
      ]
    }
    environmentId: containerEnvironmentId
    template: {
      containers: [
        {
          name: 'api'
          image: containerImage
          env: concat([
            {
              name: 'CUSTOMER_CODE'
              value: customerCode
            }
            {
              name: 'ENVIRONMENT'
              value: environment
            }
          ], keyVaultEnvironmentVariables)
          resources: {
            cpu: json('0.25')
            memory: '0.5Gi'
          }
        }
      ]
      scale: {
        minReplicas: 0
        maxReplicas: 1
      }
    }
  }
}

output containerAppName string = containerApp.name
output containerAppResourceId string = containerApp.id
output containerAppFqdn string = containerApp.properties.configuration.ingress.fqdn
output deployedImage string = containerImage
