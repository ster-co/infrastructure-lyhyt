param aiServicesName string
param documentIntelligenceName string
param aiProjectName string
param aiLocation string
param documentIntelligenceLocation string
param tags object
param deployments array
param aiSkuName string
param documentIntelligenceSkuName string
param aiNetworkSettings object
param documentIntelligenceNetworkSettings object
param restoreAiServices bool = false

resource aiServices 'Microsoft.CognitiveServices/accounts@2026-05-15-preview' = {
  name: aiServicesName
  location: aiLocation
  tags: tags
  kind: 'AIServices'
  identity: {
    type: 'SystemAssigned'
  }
  sku: {
    name: aiSkuName
  }
  properties: {
    restore: restoreAiServices
    allowProjectManagement: true
    customSubDomainName: aiServicesName
    networkAcls: {
      defaultAction: aiNetworkSettings.defaultAction
      ipRules: []
      virtualNetworkRules: []
    }
    publicNetworkAccess: aiNetworkSettings.publicNetworkAccess
  }
}

resource aiProject 'Microsoft.CognitiveServices/accounts/projects@2026-05-15-preview' = {
  parent: aiServices
  name: aiProjectName
  location: aiLocation
  identity: {
    type: 'SystemAssigned'
  }
  properties: {
    displayName: aiProjectName
  }
}

@batchSize(1)
resource modelDeployments 'Microsoft.CognitiveServices/accounts/deployments@2026-05-15-preview' = [for deployment in deployments: {
  parent: aiServices
  name: deployment.name
  sku: {
    capacity: deployment.capacity
    name: deployment.skuName
  }
  properties: union({
    deploymentState: 'Running'
    model: {
      format: deployment.format
      name: deployment.model
      version: deployment.version
    }
    raiPolicyName: deployment.raiPolicyName
    versionUpgradeOption: deployment.versionUpgradeOption
  }, contains(deployment, 'serviceTier') ? {
    serviceTier: deployment.serviceTier
  } : {})
}]

resource documentIntelligence 'Microsoft.CognitiveServices/accounts@2026-05-15-preview' = {
  name: documentIntelligenceName
  location: documentIntelligenceLocation
  tags: tags
  kind: 'FormRecognizer'
  identity: {
    type: 'None'
  }
  sku: {
    name: documentIntelligenceSkuName
  }
  properties: {
    allowProjectManagement: false
    customSubDomainName: documentIntelligenceName
    networkAcls: {
      defaultAction: documentIntelligenceNetworkSettings.defaultAction
      ipRules: []
      virtualNetworkRules: []
    }
    publicNetworkAccess: documentIntelligenceNetworkSettings.publicNetworkAccess
  }
}

output aiServicesResourceId string = aiServices.id
output aiProjectResourceId string = aiProject.id
output aiEndpoint string = 'https://${aiServices.name}.cognitiveservices.azure.com/'
output documentIntelligenceResourceId string = documentIntelligence.id
output documentIntelligenceEndpoint string = 'https://${documentIntelligence.name}.cognitiveservices.azure.com/'
output deploymentNames array = [for deployment in deployments: deployment.name]
