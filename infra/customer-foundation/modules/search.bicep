param searchServiceName string
param location string
param tags object
param enableSearchService bool = true

@allowed([
  'Enabled'
  'Disabled'
])
param publicNetworkAccess string = 'Enabled'

resource searchService 'Microsoft.Search/searchServices@2026-03-01-preview' = if (enableSearchService) {
  name: searchServiceName
  location: location
  tags: tags
  sku: {
    name: 'basic'
  }
  properties: {
    authOptions: {
      apiKeyOnly: {}
    }
    computeType: 'Default'
    hostingMode: 'Default'
    networkRuleSet: {
      bypass: 'None'
      ipRules: []
    }
    partitionCount: 1
    publicNetworkAccess: publicNetworkAccess
    replicaCount: 1
    semanticSearch: 'standard'
  }
}

output searchServiceResourceId string = enableSearchService ? searchService.id : ''
output searchServiceName string = searchServiceName
output searchEndpoint string = 'https://${searchServiceName}.search.windows.net'
