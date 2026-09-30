using '../main.bicep'

param environment = 'tst'
param location = 'swedencentral'
param regionCode = 'swec'

// The pilot uses one customer Key Vault per customer/environment. Keep the
// optional shared platform vault disabled; an existing vault is not deleted.
param enablePlatformKeyVault = false
param platformKeyVaultPublicNetworkAccess = 'Enabled'
param platformKeyVaultNetworkDefaultAction = 'Allow'
param platformKeyVaultEnablePurgeProtection = true
param platformKeyVaultSoftDeleteRetentionInDays = 90

param additionalTags = {
  workload: 'central-platform'
  purpose: 'bicep-pilot'
}
