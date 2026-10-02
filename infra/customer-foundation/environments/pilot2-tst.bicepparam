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
    capacity: 100
    format: 'OpenAI'
    model: 'gpt-5-mini'
    name: 'gpt-5-mini'
    raiPolicyName: 'Microsoft.DefaultV2'
    skuName: 'GlobalStandard'
    version: '2025-08-07'
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
param customerTenantId = 'a450ace8-4fd1-4338-a906-912ee75dc7e3'
param enableSameTenantRuntimeKeyVaultRoleAssignment = false
param environment = 'tst'
param keyVaultEnablePurgeProtection = true
param keyVaultNetworkDefaultAction = 'Allow'
param keyVaultSoftDeleteRetentionInDays = 90
param location = 'swedencentral'
param publicNetworkAccess = 'Enabled'
param regionCode = 'swec'
param runtimeAccessPrincipalId = ''
param sqlEntraAdministratorLogin = 'LYHYT Infrastructure TST'
param sqlEntraAdministratorObjectId = 'efbf96fc-efab-4c35-80e1-2731b69faae3'
param sqlEntraAdministratorTenantId = 'a450ace8-4fd1-4338-a906-912ee75dc7e3'
param sqlEntraOnlyAuthentication = true
param storageContainerNames = [
  'rag-files'
  'offerte-backups'
]
param storageNetworkDefaultAction = 'Allow'
