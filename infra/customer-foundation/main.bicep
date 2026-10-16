targetScope = 'subscription'

@minLength(2)
@maxLength(12)
param customerCode string

@allowed([
  'tst'
  'acc'
  'prod'
])
param environment string

param location string
param regionCode string

param sqlEntraAdministratorLogin string
param sqlEntraAdministratorObjectId string
param sqlEntraAdministratorPrincipalType string = 'User'
param sqlEntraAdministratorTenantId string
param sqlEntraOnlyAuthentication bool = true
param enableSearchService bool = true

param storageContainerNames array
param aiDeployments array
param additionalTags object = {}

@allowed([
  'Enabled'
  'Disabled'
])
param publicNetworkAccess string = 'Enabled'

@allowed([
  'Allow'
  'Deny'
])
param storageNetworkDefaultAction string = 'Allow'

var compactCustomerCode = replace(toLower(customerCode), '-', '')
var commonTags = union({
    project: 'lyhyt'
    customer: customerCode
    environment: environment
    managedBy: 'bicep'
    ownershipBoundary: 'customer'
    component: 'customer-foundation'
  }, additionalTags)

var customerResourceGroupName = 'rg-${customerCode}-foundation-${environment}-${regionCode}'
var storageAccountName = 'st${compactCustomerCode}${environment}${regionCode}'
var sqlServerName = 'sql-${customerCode}-${environment}-${regionCode}'
var sqlDatabaseName = 'sqldb-${customerCode}-${environment}'
var searchServiceName = 'search-${customerCode}-${environment}-${regionCode}'
var aiServicesName = 'ai-${customerCode}-${environment}-${regionCode}'
var documentIntelligenceName = 'di-${customerCode}-${environment}-${regionCode}'
resource customerResourceGroup 'Microsoft.Resources/resourceGroups@2025-04-01' = {
  name: customerResourceGroupName
  location: location
  tags: commonTags
}

module storage './modules/storage.bicep' = {
  name: 'customer-foundation-storage'
  scope: customerResourceGroup
  params: {
    storageAccountName: storageAccountName
    location: location
    tags: commonTags
    containerNames: storageContainerNames
    publicNetworkAccess: publicNetworkAccess
    networkDefaultAction: storageNetworkDefaultAction
  }
}

module sql './modules/sql.bicep' = {
  name: 'customer-foundation-sql'
  scope: customerResourceGroup
  params: {
    sqlServerName: sqlServerName
    sqlDatabaseName: sqlDatabaseName
    location: location
    tags: commonTags
    sqlEntraAdministratorLogin: sqlEntraAdministratorLogin
    sqlEntraAdministratorObjectId: sqlEntraAdministratorObjectId
    sqlEntraAdministratorPrincipalType: sqlEntraAdministratorPrincipalType
    sqlEntraAdministratorTenantId: sqlEntraAdministratorTenantId
    sqlEntraOnlyAuthentication: sqlEntraOnlyAuthentication
    publicNetworkAccess: publicNetworkAccess
  }
}

module search './modules/search.bicep' = {
  name: 'customer-foundation-search'
  scope: customerResourceGroup
  params: {
    searchServiceName: searchServiceName
    location: location
    tags: commonTags
    publicNetworkAccess: publicNetworkAccess
    enableSearchService: enableSearchService
  }
}

module ai './modules/ai.bicep' = {
  name: 'customer-foundation-ai'
  scope: customerResourceGroup
  params: {
    aiServicesName: aiServicesName
    documentIntelligenceName: documentIntelligenceName
    location: location
    tags: commonTags
    deployments: aiDeployments
    publicNetworkAccess: publicNetworkAccess
  }
}

output customerResourceGroupName string = customerResourceGroup.name
output storageAccountResourceId string = storage.outputs.storageAccountResourceId
output storageAccountName string = storage.outputs.storageAccountName
output blobEndpoint string = storage.outputs.blobEndpoint
output storageContainerNames array = storage.outputs.containerNames
output sqlServerResourceId string = sql.outputs.sqlServerResourceId
output sqlServerFqdn string = sql.outputs.sqlServerFqdn
output sqlDatabaseResourceId string = sql.outputs.sqlDatabaseResourceId
output sqlDatabaseName string = sql.outputs.sqlDatabaseName
output searchServiceResourceId string = search.outputs.searchServiceResourceId
output searchServiceName string = search.outputs.searchServiceName
output searchEndpoint string = search.outputs.searchEndpoint
output aiServicesResourceId string = ai.outputs.aiServicesResourceId
output aiEndpoint string = ai.outputs.aiEndpoint
output documentIntelligenceResourceId string = ai.outputs.documentIntelligenceResourceId
output documentIntelligenceEndpoint string = ai.outputs.documentIntelligenceEndpoint
output gpt5DeploymentName string = ai.outputs.deploymentNames[0]
output gpt54DeploymentName string = ai.outputs.deploymentNames[1]
output gpt5MiniDeploymentName string = ai.outputs.deploymentNames[2]
output textEmbedding3LargeDeploymentName string = ai.outputs.deploymentNames[3]
