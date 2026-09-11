using '../main.bicep'

param customerCode = 'pilot'
param environment = 'tst'
param location = 'swedencentral'
param regionCode = 'swec'

// Replace these non-secret placeholders with values from the customer tenant.
param customerTenantId = '00000000-0000-0000-0000-000000000000'
param sqlEntraAdministratorLogin = 'replace-with-customer-entra-admin'
param sqlEntraAdministratorObjectId = '00000000-0000-0000-0000-000000000000'
param sqlEntraAdministratorPrincipalType = 'User'
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
    capacity: 1000
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
    raiPolicyName: 'Microsoft.DefaultV2'
  }
  {
    name: 'gpt-5.4'
    model: 'gpt-5.4'
    format: 'OpenAI'
    version: '2026-03-05'
    skuName: 'GlobalStandard'
    capacity: 2000
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
    raiPolicyName: 'Microsoft.DefaultV2'
  }
  {
    name: 'gpt-5-mini'
    model: 'gpt-5-mini'
    format: 'OpenAI'
    version: '2025-08-07'
    skuName: 'GlobalStandard'
    capacity: 100
    versionUpgradeOption: 'OnceNewDefaultVersionAvailable'
    raiPolicyName: 'Microsoft.DefaultV2'
  }
  {
    name: 'text-embedding-3-large'
    model: 'text-embedding-3-large'
    format: 'OpenAI'
    version: '1'
    skuName: 'GlobalStandard'
    capacity: 250
    versionUpgradeOption: 'NoAutoUpgrade'
    raiPolicyName: 'Microsoft.DefaultV2'
  }
]

param additionalTags = {
  workload: 'customer-foundation'
  purpose: 'customer-foundation-pilot'
}
