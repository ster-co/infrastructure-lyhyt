using '../main.bicep'

param additionalTags = {
  purpose: 'customer-foundation-pilot'
  workload: 'customer-foundation'
}

param aiDeployments = [
  {
    capacity: 100
    format: 'OpenAI'
    model: 'gpt-5'
    name: 'gpt-5'
    raiPolicyName: 'Microsoft.DefaultV2'
    skuName: 'GlobalStandard'
    version: '2025-08-07'
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
  }
  {
    capacity: 100
    format: 'OpenAI'
    model: 'gpt-5.4'
    name: 'gpt-5.4'
    raiPolicyName: 'Microsoft.DefaultV2'
    skuName: 'GlobalStandard'
    version: '2026-03-05'
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
  }
  {
    capacity: 250
    format: 'OpenAI'
    model: 'gpt-4.1-mini'
    name: 'gpt-4.1-mini'
    raiPolicyName: 'Microsoft.DefaultV2'
    skuName: 'GlobalStandard'
    version: '2025-04-14'
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
  }
  {
    capacity: 250
    format: 'OpenAI'
    model: 'gpt-4.1-nano'
    name: 'gpt-4.1-nano'
    raiPolicyName: 'Microsoft.DefaultV2'
    skuName: 'GlobalStandard'
    version: '2025-04-14'
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
  }
  {
    capacity: 250
    format: 'OpenAI'
    model: 'text-embedding-3-large'
    name: 'text-embedding-3-large'
    raiPolicyName: 'Microsoft.DefaultV2'
    skuName: 'GlobalStandard'
    version: '1'
    versionUpgradeOption: 'NoAutoUpgrade'
  }
]

param customerCode = 'pilot2'
param environment = 'tst'
param location = 'swedencentral'
param publicNetworkAccess = 'Enabled'
param regionCode = 'swec'
param customerResourceGroupName = 'rg-pilot2-foundation-tst-swec'
param resourceNames = {
  aiServices: 'ai-pilot2-tst-swec'
  aiProject: 'proj-pilot2-tst'
  documentIntelligence: 'di-pilot2-tst-swec'
  search: 'search-pilot2-tst-swec'
  sqlServer: 'sql-pilot2-tst-swec'
  sqlDatabase: 'sqldb-pilot2-tst'
  storageAccount: 'stpilot2tstswec'
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
param searchSemanticSearch = 'standard'
param storageSkuName = 'Standard_LRS'
param sqlDatabaseSku = {
  name: 'GP_S_Gen5_1'
  tier: 'GeneralPurpose'
  family: 'Gen5'
  capacity: 1
}
param sqlDatabaseBackupRedundancy = 'Geo'
param sqlDatabaseZoneRedundant = false
param sqlDatabaseReadScale = 'Disabled'
param networkSettings = {
  ai: { publicNetworkAccess: 'Enabled', defaultAction: 'Allow' }
  documentIntelligence: { publicNetworkAccess: 'Enabled', defaultAction: 'Allow' }
  sql: { publicNetworkAccess: 'Enabled' }
  search: { publicNetworkAccess: 'Enabled' }
  storage: { publicNetworkAccess: 'Enabled', defaultAction: 'Allow' }
}
param sqlEntraAdministratorLogin = 'LYHYT Infrastructure TST'
param sqlEntraAdministratorObjectId = 'efbf96fc-efab-4c35-80e1-2731b69faae3'
param sqlEntraAdministratorTenantId = 'a450ace8-4fd1-4338-a906-912ee75dc7e3'
param sqlEntraOnlyAuthentication = true
param storageContainerNames = [
  'rag-files'
  'offerte-backups'
]
param storageNetworkDefaultAction = 'Allow'
