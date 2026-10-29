using '../main.bicep'

param customerCode = 'lyhyt-demo'
param environment = 'tst'
param location = 'swedencentral'
param regionCode = 'swec'
param customerResourceGroupName = 'rg-lyhyt-demo'
param resourceNames = {
  aiServices: 'lyhyt-ai'
  aiProject: 'proj-lyhyt'
  documentIntelligence: 'lyhyt-demo-di'
  search: 'lyhyt-demo-search'
  sqlServer: 'lyhyt-demo'
  sqlDatabase: 'lyhyt-demo-calculation'
  storageAccount: 'lyhytdemostorage'
}

param serviceLocations = {
  ai: 'swedencentral'
  documentIntelligence: 'swedencentral'
  search: 'francecentral'
  sql: 'swedencentral'
  storage: 'francecentral'
}
param aiSkuName = 'S0'
param documentIntelligenceSkuName = 'S0'
param searchSkuName = 'basic'
param searchReplicaCount = 1
param searchPartitionCount = 1
param searchSemanticSearch = 'free'
param storageSkuName = 'Standard_GRS'
param sqlDatabaseSku = {
  name: 'HS_Gen5_2'
  tier: 'Hyperscale'
  family: 'Gen5'
  capacity: 2
}
param sqlDatabaseBackupRedundancy = 'GeoZone'
param sqlDatabaseZoneRedundant = true
param sqlDatabaseReadScale = 'Enabled'
param networkSettings = {
  ai: { publicNetworkAccess: 'Enabled', defaultAction: 'Allow' }
  documentIntelligence: { publicNetworkAccess: 'Enabled', defaultAction: 'Allow' }
  sql: { publicNetworkAccess: 'Enabled' }
  search: { publicNetworkAccess: 'Enabled' }
  storage: { publicNetworkAccess: 'Enabled', defaultAction: 'Allow' }
}

// Replace these non-secret placeholders with values from the customer tenant.
param sqlEntraAdministratorLogin = 'replace-with-customer-entra-admin'
param sqlEntraAdministratorObjectId = '00000000-0000-0000-0000-000000000000'
param sqlEntraAdministratorTenantId = '00000000-0000-0000-0000-000000000000'
param sqlEntraOnlyAuthentication = true

// Selected from the reference configuration; workload-specific containers are omitted.
param storageContainerNames = [
  'rag-files'
  'offerte-backups'
]

// Reference capacities are examples and must be checked against customer quota.
param aiDeployments = [
  {
    name: 'gpt-5'
    model: 'gpt-5'
    format: 'OpenAI'
    version: '2025-08-07'
    skuName: 'GlobalStandard'
    capacity: 50
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
    raiPolicyName: 'Microsoft.DefaultV2'
  }
  {
    name: 'gpt-5.4'
    model: 'gpt-5.4'
    format: 'OpenAI'
    version: '2026-03-05'
    skuName: 'GlobalStandard'
    capacity: 50
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
    raiPolicyName: 'Microsoft.DefaultV2'
  }
  {
    name: 'gpt-4.1-mini'
    model: 'gpt-4.1-mini'
    format: 'OpenAI'
    version: '2025-04-14'
    skuName: 'GlobalStandard'
    capacity: 250
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
    raiPolicyName: 'Microsoft.DefaultV2'
  }
  {
    name: 'gpt-4.1-nano'
    model: 'gpt-4.1-nano'
    format: 'OpenAI'
    version: '2025-04-14'
    skuName: 'GlobalStandard'
    capacity: 250
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
    raiPolicyName: 'Microsoft.DefaultV2'
  }
  {
    name: 'text-embedding-3-large'
    model: 'text-embedding-3-large'
    format: 'OpenAI'
    version: '1'
    skuName: 'GlobalStandard'
    capacity: 150
    versionUpgradeOption: 'NoAutoUpgrade'
    raiPolicyName: 'Microsoft.DefaultV2'
  }
]

param additionalTags = {
  workload: 'customer-foundation'
  purpose: 'customer-foundation-pilot'
}
