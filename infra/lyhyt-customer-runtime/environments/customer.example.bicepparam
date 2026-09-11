using '../main.bicep'

param customerCode = 'pilot'
param environment = 'tst'
param location = 'swedencentral'
param regionCode = 'swec'
param containerRegistryName = 'acrlyhyttstmrfj6hm3oed7q'
param containerRegistryResourceGroupName = 'rg-lyhyt-platform-tst-swec'
param containerRegistryLoginServer = 'acrlyhyttstmrfj6hm3oed7q.azurecr.io'
param containerImage = 'acrlyhyttstmrfj6hm3oed7q.azurecr.io/pilot/hello:2026-09-11-1'

param additionalTags = {
  workload: 'customer-runtime'
  purpose: 'foundation-pilot'
}
