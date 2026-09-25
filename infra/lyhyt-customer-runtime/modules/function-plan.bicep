param functionPlanName string
param location string
param tags object
param skuName string
param skuTier string
param skuCapacity int

// Flex Consumption is selected explicitly by each customer-runtime entry point.
// One plan is dedicated to each Function App because the audited workloads have
// different runtime versions and long-running execution needs.
resource functionPlan 'Microsoft.Web/serverfarms@2024-04-01' = {
  name: functionPlanName
  location: location
  tags: tags
  kind: 'functionapp,linux'
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
