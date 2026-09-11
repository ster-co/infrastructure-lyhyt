param environmentName string
param location string
param tags object
param logAnalyticsCustomerId string

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
    publicNetworkAccess: 'Enabled'
    workloadProfiles: [
      {
        name: 'Consumption'
        workloadProfileType: 'Consumption'
      }
    ]
  }
}

output containerEnvironmentId string = containerEnvironment.id
output containerEnvironmentDefaultDomain string = containerEnvironment.properties.defaultDomain
