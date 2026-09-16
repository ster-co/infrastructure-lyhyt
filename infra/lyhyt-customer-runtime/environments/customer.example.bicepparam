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

// Replace these placeholders with values from the shared platform deployment.
param containerRegistryName = 'replacewithacrname'
param containerRegistryResourceGroupName = 'replace-with-platform-resource-group'
param containerRegistryLoginServer = 'replacewithacrname.azurecr.io'
param containerImage = 'replacewithacrname.azurecr.io/pilot/your-image:your-tag'

param additionalTags = {
  workload: 'customer-runtime'
  purpose: 'foundation-pilot'
}
