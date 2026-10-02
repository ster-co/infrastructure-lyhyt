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
param runtimeKeyVaultNetworkDefaultAction = 'Deny'
// Each Function App uses a dedicated Flex Consumption plan and its audited
// Python runtime version. Package publication is handled by application CI/CD.
param functionRuntimeConfiguration = {
  documentParser: {
    workerRuntime: 'python'
    workerRuntimeVersion: '3.12'
  }
  mailboxSync: {
    workerRuntime: 'python'
    workerRuntimeVersion: '3.11'
  }
  sdb: {
    workerRuntime: 'python'
    workerRuntimeVersion: '3.12'
  }
}
param enableDoclingResources = false
// Replace this canonical reference with the complete resource ID and endpoint
// from the shared platform deployment. The resource ID is the identity used
// for existing-resource resolution and ACR RBAC scope.
param containerRegistryReference = {
  resourceId: '/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/replace-with-platform-resource-group/providers/Microsoft.ContainerRegistry/registries/replacewithacrname'
  loginServer: 'replacewithacrname.azurecr.io'
}
// Replace the digest with the immutable image selected by the release manifest.
param containerImage = 'replacewithacrname.azurecr.io/pilot/your-image@sha256:0000000000000000000000000000000000000000000000000000000000000000'

// The LYHYT runtime vault is the only runtime configuration vault. These are
// safe URI/resource-ID placeholders; they are not secret values.
param keyVaultConfiguration = {
  enabled: true
  runtimeKeyVaultResourceId: '/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/replace-with-runtime-resource-group/providers/Microsoft.KeyVault/vaults/replace-with-runtime-vault'
  runtimeKeyVaultUri: 'https://replace-with-runtime-vault.vault.azure.net/'
  customerKeyVaultResourceId: ''
  customerKeyVaultUri: ''
  platformKeyVaultResourceId: ''
  platformKeyVaultUri: ''
  requireKeyVault: false
}
param enablePlatformKeyVaultRoleAssignment = false

param additionalTags = {
  workload: 'customer-runtime'
  purpose: 'foundation-pilot'
}
