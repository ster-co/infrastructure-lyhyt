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
@description('Customer-owned resource group name. This is explicit so sample and customer names are reviewed before deployment.')
param customerResourceGroupName string
@description('Reviewed names for the seven customer foundation resources.')
param resourceNames object

param sqlEntraAdministratorLogin string
param sqlEntraAdministratorObjectId string
param sqlEntraAdministratorPrincipalType string = 'User'
param sqlEntraAdministratorTenantId string
param sqlEntraOnlyAuthentication bool = true
param enableSearchService bool = true
param searchConfigurationPrincipalObjectId string = ''

@description('Per-service Azure regions. Customer overrides are validated before deployment.')
param serviceLocations object
param storageContainerNames array
param aiDeployments array
param aiSkuName string = 'S0'
param documentIntelligenceSkuName string = 'S0'
param searchSkuName string = 'basic'
param searchReplicaCount int = 1
param searchPartitionCount int = 1
param searchSemanticSearch string = 'free'
param storageSkuName string = 'Standard_GRS'
param sqlDatabaseSku object
param sqlDatabaseBackupRedundancy string = 'GeoZone'
param sqlDatabaseZoneRedundant bool = true
param sqlDatabaseReadScale string = 'Enabled'
param networkSettings object
param restoreAiServices bool = false
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

var commonTags = union({
    project: 'lyhyt'
    customer: customerCode
    environment: environment
    regionCode: regionCode
    managedBy: 'bicep'
    ownershipBoundary: 'customer'
    component: 'customer-foundation'
  }, additionalTags)

resource customerResourceGroup 'Microsoft.Resources/resourceGroups@2025-04-01' = {
  name: customerResourceGroupName
  location: location
  tags: commonTags
}

module storage './modules/storage.bicep' = {
  name: 'customer-foundation-storage'
  scope: customerResourceGroup
  params: {
    storageAccountName: resourceNames.storageAccount
    location: serviceLocations.storage
    tags: commonTags
    containerNames: storageContainerNames
    skuName: storageSkuName
    publicNetworkAccess: networkSettings.storage.publicNetworkAccess
    networkDefaultAction: networkSettings.storage.defaultAction
  }
}

module sql './modules/sql.bicep' = {
  name: 'customer-foundation-sql'
  scope: customerResourceGroup
  params: {
    sqlServerName: resourceNames.sqlServer
    sqlDatabaseName: resourceNames.sqlDatabase
    location: serviceLocations.sql
    tags: commonTags
    sqlEntraAdministratorLogin: sqlEntraAdministratorLogin
    sqlEntraAdministratorObjectId: sqlEntraAdministratorObjectId
    sqlEntraAdministratorPrincipalType: sqlEntraAdministratorPrincipalType
    sqlEntraAdministratorTenantId: sqlEntraAdministratorTenantId
    sqlEntraOnlyAuthentication: sqlEntraOnlyAuthentication
    publicNetworkAccess: networkSettings.sql.publicNetworkAccess
    databaseSku: sqlDatabaseSku
    backupStorageRedundancy: sqlDatabaseBackupRedundancy
    databaseZoneRedundant: sqlDatabaseZoneRedundant
    databaseReadScale: sqlDatabaseReadScale
  }
}

module search './modules/search.bicep' = {
  name: 'customer-foundation-search'
  scope: customerResourceGroup
  params: {
    searchServiceName: resourceNames.search
    location: serviceLocations.search
    tags: commonTags
    publicNetworkAccess: networkSettings.search.publicNetworkAccess
    skuName: searchSkuName
    replicaCount: searchReplicaCount
    partitionCount: searchPartitionCount
    semanticSearch: searchSemanticSearch
    enableSearchService: enableSearchService
    enableSearchConfiguration: environment == 'tst' && networkSettings.search.publicNetworkAccess == 'Enabled'
    searchConfigurationPrincipalObjectId: searchConfigurationPrincipalObjectId
  }
}

module ai './modules/ai.bicep' = {
  name: 'customer-foundation-ai'
  scope: customerResourceGroup
  params: {
    aiServicesName: resourceNames.aiServices
    documentIntelligenceName: resourceNames.documentIntelligence
    aiProjectName: resourceNames.aiProject
    aiLocation: serviceLocations.ai
    documentIntelligenceLocation: serviceLocations.documentIntelligence
    tags: commonTags
    deployments: aiDeployments
    aiSkuName: aiSkuName
    documentIntelligenceSkuName: documentIntelligenceSkuName
    aiNetworkSettings: networkSettings.ai
    documentIntelligenceNetworkSettings: networkSettings.documentIntelligence
    restoreAiServices: restoreAiServices
  }
}

output createdCustomerResourceGroupName string = customerResourceGroup.name
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
output aiProjectResourceId string = ai.outputs.aiProjectResourceId
output aiEndpoint string = ai.outputs.aiEndpoint
output documentIntelligenceResourceId string = ai.outputs.documentIntelligenceResourceId
output documentIntelligenceEndpoint string = ai.outputs.documentIntelligenceEndpoint
output gpt5DeploymentName string = ai.outputs.deploymentNames[0]
output gpt54DeploymentName string = ai.outputs.deploymentNames[1]
output gpt41MiniDeploymentName string = ai.outputs.deploymentNames[2]
output gpt41NanoDeploymentName string = ai.outputs.deploymentNames[3]
output textEmbedding3LargeDeploymentName string = ai.outputs.deploymentNames[4]
