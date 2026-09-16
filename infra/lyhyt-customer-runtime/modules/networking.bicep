param customerCode string
param environment string
param location string
param regionCode string
param vnetAddressPrefix string
param additionalTags object = {}

var tags = union({
  project: 'lyhyt'
  customerCode: customerCode
  environment: environment
  regionCode: regionCode
  component: 'customer-runtime-networking'
  managedBy: 'bicep'
}, additionalTags)

var virtualNetworkName = 'vnet-lyhyt-${customerCode}-${environment}-${regionCode}'
var containerAppsSubnetName = 'snet-lyhyt-${customerCode}-containerapps-${environment}-${regionCode}'
var privateEndpointsSubnetName = 'snet-lyhyt-${customerCode}-private-endpoints-${environment}-${regionCode}'

// Keep the child ranges deterministic while requiring each customer/environment
// to receive a centrally allocated, non-overlapping vnetAddressPrefix. Bicep's
// second cidrSubnet argument is the absolute new prefix length.
var containerAppsSubnetPrefix = cidrSubnet(vnetAddressPrefix, 23, 0)
var privateEndpointsSubnetPrefix = cidrSubnet(vnetAddressPrefix, 24, 4)

resource virtualNetwork 'Microsoft.Network/virtualNetworks@2024-07-01' = {
  name: virtualNetworkName
  location: location
  tags: tags
  properties: {
    addressSpace: {
      addressPrefixes: [
        vnetAddressPrefix
      ]
    }
  }
}

// This is a workload-profiles Container Apps Environment using the Consumption
// workload profile, not a legacy Consumption-only environment. The subnet is
// dedicated exclusively to that Container Apps Environment.
resource containerAppsSubnet 'Microsoft.Network/virtualNetworks/subnets@2024-07-01' = {
  parent: virtualNetwork
  name: containerAppsSubnetName
  properties: {
    addressPrefix: containerAppsSubnetPrefix
    delegations: [
      {
        name: 'containerAppsEnvironment'
        properties: {
          serviceName: 'Microsoft.App/environments'
        }
      }
    ]
  }
}

resource privateEndpointsSubnet 'Microsoft.Network/virtualNetworks/subnets@2024-07-01' = {
  parent: virtualNetwork
  name: privateEndpointsSubnetName
  properties: {
    addressPrefix: privateEndpointsSubnetPrefix
    // Enable this subnet for future Private Endpoints. Private Endpoint
    // resources and their DNS dependencies are intentionally out of scope.
    privateEndpointNetworkPolicies: 'Disabled'
  }
}

output virtualNetworkId string = virtualNetwork.id
output virtualNetworkName string = virtualNetwork.name
output containerAppsSubnetId string = containerAppsSubnet.id
output privateEndpointsSubnetId string = privateEndpointsSubnet.id
