param sqlServerName string
param sqlDatabaseName string
param location string
param tags object
param sqlEntraAdministratorLogin string
param sqlEntraAdministratorObjectId string
param sqlEntraAdministratorPrincipalType string
param sqlEntraAdministratorTenantId string
param sqlEntraOnlyAuthentication bool = true
param databaseSku object
param backupStorageRedundancy string = 'GeoZone'
param databaseZoneRedundant bool = true
param databaseReadScale string = 'Enabled'

@allowed([
  'Enabled'
  'Disabled'
])
param publicNetworkAccess string = 'Enabled'

resource sqlServer 'Microsoft.Sql/servers@2025-02-01-preview' = {
  name: sqlServerName
  location: location
  tags: tags
  properties: {
    administrators: {
      administratorType: 'ActiveDirectory'
      azureADOnlyAuthentication: sqlEntraOnlyAuthentication
      login: sqlEntraAdministratorLogin
      principalType: sqlEntraAdministratorPrincipalType
      sid: sqlEntraAdministratorObjectId
      tenantId: sqlEntraAdministratorTenantId
    }
    minimalTlsVersion: '1.2'
    publicNetworkAccess: publicNetworkAccess
    restrictOutboundNetworkAccess: 'Disabled'
    version: '12.0'
  }
}

resource sqlDatabase 'Microsoft.Sql/servers/databases@2025-02-01-preview' = {
  parent: sqlServer
  name: sqlDatabaseName
  location: location
  sku: {
    capacity: databaseSku.capacity
    family: databaseSku.family
    name: databaseSku.name
    tier: databaseSku.tier
  }
  properties: {
    availabilityZone: 'NoPreference'
    catalogCollation: 'SQL_Latin1_General_CP1_CI_AS'
    collation: 'SQL_Latin1_General_CP1_CI_AS'
    isLedgerOn: false
    readScale: databaseReadScale
    requestedBackupStorageRedundancy: backupStorageRedundancy
    zoneRedundant: databaseZoneRedundant
  }
}

output sqlServerResourceId string = sqlServer.id
output sqlServerFqdn string = '${sqlServer.name}${environment().suffixes.sqlServerHostname}'
output sqlDatabaseResourceId string = sqlDatabase.id
output sqlDatabaseName string = sqlDatabase.name
