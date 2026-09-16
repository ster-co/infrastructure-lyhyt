targetScope = 'subscription'

@allowed([
  'dev'
  'tst'
  'acc'
  'prod'
])
param environment string

param location string
param regionCode string
param additionalTags object = {}

// The platform vault has an independent lifecycle from the shared ACR.
param enablePlatformKeyVault bool = false
@allowed([
  'Enabled'
  'Disabled'
])
param platformKeyVaultPublicNetworkAccess string = 'Enabled'
@allowed([
  'Allow'
  'Deny'
])
param platformKeyVaultNetworkDefaultAction string = 'Allow'
param platformKeyVaultEnablePurgeProtection bool = true
@minValue(7)
@maxValue(90)
param platformKeyVaultSoftDeleteRetentionInDays int = 90

var commonTags = union({
  project: 'lyhyt'
  environment: environment
  managedBy: 'bicep'
}, additionalTags)

var platformResourceGroupName = 'rg-lyhyt-platform-${environment}-${regionCode}'
// Key Vault names are globally unique. The short semantic prefix keeps the
// purpose visible while uniqueString makes the result bounded and stable.
var platformKeyVaultName = 'kvp${uniqueString(subscription().id, platformResourceGroupName, 'platform')}'

resource platformResourceGroup 'Microsoft.Resources/resourceGroups@2025-04-01' = {
  name: platformResourceGroupName
  location: location
  tags: commonTags
}

module platform './modules/platform.bicep' = {
  name: 'deploy-platform-${environment}'
  scope: platformResourceGroup
  params: {
    environment: environment
    location: location
    tags: commonTags
  }
}

module platformKeyVault './modules/key-vault.bicep' = if (enablePlatformKeyVault) {
  name: 'deploy-platform-key-vault-${environment}'
  scope: platformResourceGroup
  params: {
    keyVaultName: platformKeyVaultName
    location: location
    tenantId: subscription().tenantId
    tags: commonTags
    publicNetworkAccess: platformKeyVaultPublicNetworkAccess
    networkDefaultAction: platformKeyVaultNetworkDefaultAction
    softDeleteRetentionInDays: platformKeyVaultSoftDeleteRetentionInDays
    enablePurgeProtection: platformKeyVaultEnablePurgeProtection
  }
}

output platformResourceGroupName string = platformResourceGroup.name
output containerRegistryName string = platform.outputs.containerRegistryName
output containerRegistryLoginServer string = platform.outputs.containerRegistryLoginServer
output containerRegistryId string = platform.outputs.containerRegistryId
#disable-next-line BCP318
output platformKeyVaultResourceId string = enablePlatformKeyVault ? platformKeyVault.outputs.?keyVaultResourceId : ''
#disable-next-line BCP318
output platformKeyVaultName string = enablePlatformKeyVault ? platformKeyVault.outputs.?keyVaultName : ''
#disable-next-line BCP318
output platformKeyVaultUri string = enablePlatformKeyVault ? platformKeyVault.outputs.?keyVaultUri : ''
