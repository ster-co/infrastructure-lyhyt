param sqlServerName string
param sqlDatabaseName string
param location string
param tags object
param sqlEntraAdministratorLogin string
param sqlEntraAdministratorObjectId string
param sqlEntraAdministratorPrincipalType string
param sqlEntraAdministratorTenantId string
param sqlEntraOnlyAuthentication bool = true

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
    capacity: 1
    family: 'Gen5'
    name: 'GP_S_Gen5_1'
    tier: 'GeneralPurpose'
  }
  properties: {
    autoPauseDelay: 60
    availabilityZone: 'NoPreference'
    catalogCollation: 'SQL_Latin1_General_CP1_CI_AS'
    collation: 'SQL_Latin1_General_CP1_CI_AS'
    isLedgerOn: false
    maxSizeBytes: 4294967296
    minCapacity: json('0.5')
    readScale: 'Disabled'
    requestedBackupStorageRedundancy: 'Geo'
    zoneRedundant: false
  }
}

output sqlServerResourceId string = sqlServer.id
output sqlServerFqdn string = '${sqlServer.name}.${environment().suffixes.sqlServerHostname}'
output sqlDatabaseResourceId string = sqlDatabase.id
output sqlDatabaseName string = sqlDatabase.name
