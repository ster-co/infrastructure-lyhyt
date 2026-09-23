using '../main.bicep'

param customerCode = 'pilot'
param environment = 'tst'
param location = 'swedencentral'
param regionCode = 'swec'

// Replace with a centrally allocated, unique range for every customer/environment.
// Subnets are derived deterministically from this explicit VNet prefix.
param vnetAddressPrefix = '10.20.0.0/21'

// Temporary TST pilot values. Production parameter files must choose these
// explicitly; the runtime entry point has no defaults for either parameter.
param publicNetworkAccess = 'Enabled'
param zoneRedundant = false
param functionHostStorageNetworkDefaultAction = 'Allow'
// Y1/Dynamic is suitable for the TST pilot. Select an Elastic Premium SKU
// explicitly for production private networking and stronger scale isolation.
param functionPlanSkuName = 'Y1'
param functionPlanSkuTier = 'Dynamic'
param functionPlanCapacity = 0
param functionWorkerRuntime = 'python'
param functionWorkerRuntimeVersion = '3.11'
param functionConfiguration = {
  customerTenantId: '00000000-0000-0000-0000-000000000000'
  customerHostname: 'pilot.lyhyt.nl'
  allowedGroupIds: []
  deploymentTier: 'standard'
}

// Replace this canonical reference with the complete resource ID and endpoint
// from the shared platform deployment. The resource ID is the identity used
// for existing-resource resolution and ACR RBAC scope.
param containerRegistryReference = {
  resourceId: '/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/replace-with-platform-resource-group/providers/Microsoft.ContainerRegistry/registries/replacewithacrname'
  loginServer: 'replacewithacrname.azurecr.io'
}
// Replace the digest with the immutable image selected by the release manifest.
param containerImage = 'replacewithacrname.azurecr.io/pilot/your-image@sha256:0000000000000000000000000000000000000000000000000000000000000000'

// Application-level Key Vault hydration is disabled until the application
// selects this UAMI explicitly. These are safe URI/resource-ID placeholders;
// they are not secret values.
param keyVaultConfiguration = {
  enabled: false
  customerKeyVaultResourceId: '/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/replace-with-customer-resource-group/providers/Microsoft.KeyVault/vaults/replace-with-customer-vault'
  customerKeyVaultUri: 'https://replace-with-customer-vault.vault.azure.net/'
  platformKeyVaultResourceId: '/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/replace-with-platform-resource-group/providers/Microsoft.KeyVault/vaults/replace-with-platform-vault'
  platformKeyVaultUri: 'https://replace-with-platform-vault.vault.azure.net/'
  requireKeyVault: false
}
param enablePlatformKeyVaultRoleAssignment = false

param additionalTags = {
  workload: 'customer-runtime'
  purpose: 'foundation-pilot'
}
