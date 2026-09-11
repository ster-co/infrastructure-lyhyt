using '../main.bicep'

param environment = 'tst'
param location = 'swedencentral'
param regionCode = 'swec'

param additionalTags = {
  workload: 'central-platform'
  purpose: 'bicep-pilot'
}
