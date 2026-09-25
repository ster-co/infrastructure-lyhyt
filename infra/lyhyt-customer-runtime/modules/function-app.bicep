param functionAppName string
param location string
param tags object
param functionPlanResourceId string
param identityResourceId string
param identityClientId string
param functionWorkerRuntime string
param functionWorkerRuntimeVersion string
param deploymentStorageContainerUri string
param applicationInsightsConnectionString string
param keyVaultIntegrationEnabled bool = false
param customerKeyVaultUri string = ''
param providerKeyVaultUri string = ''
param requireKeyVault bool = false
param hostStorageBlobServiceUri string
param hostStorageQueueServiceUri string
param hostStorageTableServiceUri string

var hostSettings = [
  {
    name: 'FUNCTIONS_EXTENSION_VERSION'
    value: '~4'
  }
  {
    name: 'FUNCTIONS_WORKER_RUNTIME'
    value: functionWorkerRuntime
  }
  {
    name: 'FUNCTIONS_WORKER_RUNTIME_VERSION'
    value: functionWorkerRuntimeVersion
  }
  {
    name: 'AzureWebJobsStorage__credential'
    value: 'managedidentity'
  }
  {
    name: 'AzureWebJobsStorage__clientId'
    value: identityClientId
  }
  {
    name: 'AzureWebJobsStorage__blobServiceUri'
    value: hostStorageBlobServiceUri
  }
  {
    name: 'AzureWebJobsStorage__queueServiceUri'
    value: hostStorageQueueServiceUri
  }
  {
    name: 'AzureWebJobsStorage__tableServiceUri'
    value: hostStorageTableServiceUri
  }
]

var applicationSettings = [
  {
    name: 'AZURE_CLIENT_ID'
    value: identityClientId
  }
  {
    name: 'CLIENT_KEY_VAULT_URI'
    value: customerKeyVaultUri
  }
  {
    name: 'PLATFORM_KEY_VAULT_URI'
    value: providerKeyVaultUri
  }
  {
    name: 'REQUIRE_KEY_VAULT'
    value: keyVaultIntegrationEnabled && requireKeyVault ? 'true' : 'false'
  }
  {
    name: 'APPLICATIONINSIGHTS_CONNECTION_STRING'
    value: applicationInsightsConnectionString
  }
]

resource functionApp 'Microsoft.Web/sites@2024-04-01' = {
  name: functionAppName
  location: location
  tags: tags
  kind: 'functionapp,linux'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${identityResourceId}': {}
    }
  }
  properties: {
    serverFarmId: functionPlanResourceId
    httpsOnly: true
    clientAffinityEnabled: false
    functionAppConfig: {
      deployment: {
        storage: {
          type: 'BlobContainer'
          value: deploymentStorageContainerUri
          authentication: {
            type: 'UserAssignedIdentity'
            userAssignedIdentityResourceId: identityResourceId
          }
        }
      }
      runtime: {
        name: functionWorkerRuntime
        version: functionWorkerRuntimeVersion
      }
    }
    siteConfig: {
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      appSettings: concat(hostSettings, applicationSettings)
    }
  }
}

output functionAppName string = functionApp.name
output functionAppResourceId string = functionApp.id
output functionAppHostname string = functionApp.properties.defaultHostName
