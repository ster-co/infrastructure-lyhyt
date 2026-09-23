param functionAppName string
param location string
param tags object
param functionPlanResourceId string
param alwaysOn bool
param identityResourceId string
param identityClientId string
param functionWorkload string
param functionWorkerRuntime string
param functionWorkerRuntimeVersion string
param customerCode string
param environment string
param customerTenantId string
param customerHostname string
param allowedGroupIds array
param deploymentTier string
param providerKeyVaultUri string
param hostStorageBlobServiceUri string
param hostStorageQueueServiceUri string
param hostStorageTableServiceUri string
param additionalAppSettings array = []

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
    siteConfig: {
      alwaysOn: alwaysOn
      ftpsState: 'Disabled'
      minTlsVersion: '1.2'
      linuxFxVersion: '${functionWorkerRuntime == 'python' ? 'Python' : functionWorkerRuntime}|${functionWorkerRuntimeVersion}'
      appSettings: concat([
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
          name: 'WEBSITE_RUN_FROM_PACKAGE'
          value: '1'
        }
        {
          name: 'AZURE_CLIENT_ID'
          value: identityClientId
        }
        {
          name: 'CUSTOMER_CODE'
          value: customerCode
        }
        {
          name: 'ENVIRONMENT'
          value: environment
        }
        {
          name: 'FUNCTION_WORKLOAD'
          value: functionWorkload
        }
        {
          name: 'CUSTOMER_TENANT_ID'
          value: customerTenantId
        }
        {
          name: 'CUSTOMER_HOSTNAME'
          value: customerHostname
        }
        {
          name: 'ALLOWED_GROUP_IDS'
          value: string(allowedGroupIds)
        }
        {
          name: 'DEPLOYMENT_TIER'
          value: deploymentTier
        }
        {
          name: 'PROVIDER_KEY_VAULT_URI'
          value: providerKeyVaultUri
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
      ], additionalAppSettings)
    }
  }
}

output functionAppName string = functionApp.name
output functionAppResourceId string = functionApp.id
output functionAppHostname string = functionApp.properties.defaultHostName
