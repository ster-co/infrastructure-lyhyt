param functionPlanName string
param location string
param tags object
param skuName string
param skuTier string
param skuCapacity int

// The hosting SKU is intentionally configurable. TST can use Y1/Dynamic;
// production can select Elastic Premium when VNet integration and stronger
// scale isolation are approved.
resource functionPlan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: functionPlanName
  location: location
  tags: tags
  kind: 'linux'
  sku: {
    name: skuName
    tier: skuTier
    capacity: skuCapacity
  }
  properties: {
    reserved: true
  }
}

output functionPlanResourceId string = functionPlan.id
output functionPlanName string = functionPlan.name
