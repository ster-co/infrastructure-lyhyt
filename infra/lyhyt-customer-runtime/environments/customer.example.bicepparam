using '../main.bicep'

param customerCode = 'pilot'
param environment = 'tst'
param location = 'swedencentral'
param regionCode = 'swec'

// Replace these placeholders with values from the shared platform deployment.
param containerRegistryName = 'replacewithacrname'
param containerRegistryResourceGroupName = 'replace-with-platform-resource-group'
param containerRegistryLoginServer = 'replacewithacrname.azurecr.io'
param containerImage = 'replacewithacrname.azurecr.io/pilot/your-image:your-tag'

param additionalTags = {
  workload: 'customer-runtime'
  purpose: 'foundation-pilot'
}
