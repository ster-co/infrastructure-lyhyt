param searchServiceName string
param location string
param tags object
param enableSearchService bool = true
param enableSearchConfiguration bool = true
param searchConfigurationPrincipalObjectId string = ''

@allowed([
  'Enabled'
  'Disabled'
])
param publicNetworkAccess string = 'Enabled'

resource searchService 'Microsoft.Search/searchServices@2026-03-01-preview' = if (enableSearchService) {
  name: searchServiceName
  location: location
  tags: tags
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    name: 'basic'
  }
  properties: {
    authOptions: {
      aadOrApiKey: {}
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

// The workflow identity uses the Search Service Contributor data-plane role to apply Search objects.
var searchServiceContributorRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
)

resource searchConfigurationRoleAssignment 'Microsoft.Authorization/roleAssignments@2022-04-01' = if (enableSearchService && enableSearchConfiguration && !empty(searchConfigurationPrincipalObjectId)) {
  name: guid(searchService.id, searchConfigurationPrincipalObjectId, searchServiceContributorRoleId)
  scope: searchService
  properties: {
    principalId: searchConfigurationPrincipalObjectId
    principalType: 'ServicePrincipal'
    roleDefinitionId: searchServiceContributorRoleId
  }
}

output searchServiceResourceId string = enableSearchService ? searchService.id : ''
output searchServiceName string = searchServiceName
output searchEndpoint string = 'https://${searchServiceName}.search.windows.net'
