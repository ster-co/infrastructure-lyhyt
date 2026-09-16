using '../main.bicep'

param environment = 'tst'
param location = 'swedencentral'
param regionCode = 'swec'

// Keep the optional shared vault disabled in the generic pilot example.
param enablePlatformKeyVault = false
param platformKeyVaultPublicNetworkAccess = 'Enabled'
param platformKeyVaultNetworkDefaultAction = 'Allow'
param platformKeyVaultEnablePurgeProtection = false
param platformKeyVaultSoftDeleteRetentionInDays = 90

param additionalTags = {
  workload: 'central-platform'
  purpose: 'bicep-pilot'
}
