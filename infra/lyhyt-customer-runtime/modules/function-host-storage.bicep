param storageAccountName string
param location string
param tags object

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

output storageAccountResourceId string = storageAccount.id
output storageAccountName string = storageAccount.name
output blobServiceUri string = 'https://${storageAccount.name}.blob.${environment().suffixes.storage}/'
output queueServiceUri string = 'https://${storageAccount.name}.queue.${environment().suffixes.storage}/'
output tableServiceUri string = 'https://${storageAccount.name}.table.${environment().suffixes.storage}/'
