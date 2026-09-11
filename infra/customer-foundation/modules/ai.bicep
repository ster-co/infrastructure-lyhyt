param aiServicesName string
param documentIntelligenceName string
param location string
param tags object
param deployments array

@allowed([
  'Enabled'
  'Disabled'
])
param publicNetworkAccess string = 'Enabled'

resource aiServices 'Microsoft.CognitiveServices/accounts@2026-05-15-preview' = {
  name: aiServicesName
  location: location
  tags: tags
  kind: 'AIServices'
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    name: 'S0'
  }
  properties: {
    allowProjectManagement: true
    customSubDomainName: aiServicesName
    networkAcls: {
      defaultAction: 'Allow'
      ipRules: []
      virtualNetworkRules: []
    }
    publicNetworkAccess: publicNetworkAccess
  }
}

resource modelDeployments 'Microsoft.CognitiveServices/accounts/deployments@2026-05-15-preview' = [for deployment in deployments: {
  parent: aiServices
  name: deployment.name
  sku: {
    capacity: deployment.capacity
    name: deployment.skuName
  }
  properties: {
    deploymentState: 'Running'
    model: {
      format: deployment.format
      name: deployment.model
      version: deployment.version
    }
    raiPolicyName: deployment.raiPolicyName
    versionUpgradeOption: deployment.versionUpgradeOption
  }
}]

resource documentIntelligence 'Microsoft.CognitiveServices/accounts@2026-05-15-preview' = {
  name: documentIntelligenceName
  location: location
  tags: tags
  kind: 'FormRecognizer'
  identity: {
    type: 'None'
  }
  sku: {
    name: 'S0'
  }
  properties: {
    allowProjectManagement: false
    customSubDomainName: documentIntelligenceName
    networkAcls: {
      defaultAction: 'Allow'
      ipRules: []
      virtualNetworkRules: []
    }
    publicNetworkAccess: publicNetworkAccess
  }
}

output aiServicesResourceId string = aiServices.id
output aiEndpoint string = 'https://${aiServices.name}.cognitiveservices.azure.com/'
output documentIntelligenceResourceId string = documentIntelligence.id
output documentIntelligenceEndpoint string = 'https://${documentIntelligence.name}.cognitiveservices.azure.com/'
output deploymentNames array = [for deployment in deployments: deployment.name]
