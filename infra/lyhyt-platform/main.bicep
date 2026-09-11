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

var commonTags = union({
  project: 'lyhyt'
  environment: environment
  managedBy: 'bicep'
}, additionalTags)

var platformResourceGroupName = 'rg-lyhyt-platform-${environment}-${regionCode}'

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

output platformResourceGroupName string = platformResourceGroup.name
output containerRegistryName string = platform.outputs.containerRegistryName
output containerRegistryLoginServer string = platform.outputs.containerRegistryLoginServer
output containerRegistryId string = platform.outputs.containerRegistryId
