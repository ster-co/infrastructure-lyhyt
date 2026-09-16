param environmentName string
param location string
param tags object
param logAnalyticsCustomerId string
param infrastructureSubnetId string
@allowed([
  'Enabled'
  'Disabled'
])
param publicNetworkAccess string
param zoneRedundant bool

@secure()
param logAnalyticsSharedKey string

resource containerEnvironment 'Microsoft.App/managedEnvironments@2026-01-01' = {
  name: environmentName
  location: location
  tags: tags
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsCustomerId
        sharedKey: logAnalyticsSharedKey
      }
    }
    publicNetworkAccess: publicNetworkAccess
    zoneRedundant: zoneRedundant
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
    // This is a workload-profiles environment. Its dedicated infrastructure
    // subnet is delegated by networking.bicep and is not shared with other
    // runtime resources.
    vnetConfiguration: {
      // Keep the external VIP type for the temporary TST pilot. The future
      // Front Door Premium route will use Private Link and disable public
      // network access without changing this external setting.
      internal: false
      infrastructureSubnetId: infrastructureSubnetId
      // Azure-managed platform CIDR defaults are intentional for isolated TST.
      // Explicit, non-overlapping ranges are required before production
      // peering or VPN integration.
    }
  }
}

output containerEnvironmentId string = containerEnvironment.id
output containerEnvironmentDefaultDomain string = containerEnvironment.properties.defaultDomain
