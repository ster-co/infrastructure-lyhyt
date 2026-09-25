param storageAccountName string
param location string
param tags object
param blobContainerNames array = []
param queueNames array = []

@allowed([
  'Enabled'
  'Disabled'
])
param publicNetworkAccess string = 'Enabled'

@allowed([
  'Allow'
  'Deny'
])
param networkDefaultAction string = 'Allow'

resource storageAccount 'Microsoft.Storage/storageAccounts@2026-04-01' = {
  name: storageAccountName
  location: location
  tags: tags
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    accessTier: 'Hot'
    allowBlobPublicAccess: false
    allowCrossTenantReplication: false
    allowSharedKeyAccess: false
    defaultToOAuthAuthentication: true
    dnsEndpointType: 'Standard'
    encryption: {
      keySource: 'Microsoft.Storage'
      services: {
        blob: {
          enabled: true
          keyType: 'Account'
        }
        file: {
          enabled: true
          keyType: 'Account'
        }
      }
    }
    minimumTlsVersion: 'TLS1_2'
    networkAcls: {
      bypass: 'AzureServices'
      defaultAction: networkDefaultAction
      ipRules: []
      ipv6Rules: []
      virtualNetworkRules: []
    }
    publicNetworkAccess: publicNetworkAccess
    supportsHttpsTrafficOnly: true
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2026-04-01' = {
  parent: storageAccount
  name: 'default'
}

resource blobContainers 'Microsoft.Storage/storageAccounts/blobServices/containers@2026-04-01' = [for containerName in blobContainerNames: {
  parent: blobService
  name: containerName
  properties: {
    publicAccess: 'None'
  }
}]

resource queueService 'Microsoft.Storage/storageAccounts/queueServices@2026-04-01' = {
  parent: storageAccount
  name: 'default'
}

resource queues 'Microsoft.Storage/storageAccounts/queueServices/queues@2026-04-01' = [for queueName in queueNames: {
  parent: queueService
  name: queueName
}]

output storageAccountResourceId string = storageAccount.id
output storageAccountName string = storageAccount.name
output blobServiceUri string = 'https://${storageAccount.name}.blob.${environment().suffixes.storage}/'
output queueServiceUri string = 'https://${storageAccount.name}.queue.${environment().suffixes.storage}/'
output tableServiceUri string = 'https://${storageAccount.name}.table.${environment().suffixes.storage}/'
