param containerAppName string
param location string
param tags object
param containerEnvironmentId string
param identityResourceId string
param containerRegistryLoginServer string
param containerImage string
param customerCode string
param environment string

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
          env: [
            {
              name: 'CUSTOMER_CODE'
              value: customerCode
            }
            {
              name: 'ENVIRONMENT'
              value: environment
            }
          ]
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
