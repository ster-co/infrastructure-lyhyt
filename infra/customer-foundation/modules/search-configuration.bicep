param searchServiceName string
param searchEndpoint string
param customerCode string
param environment string
param location string
param tags object
param sqlDatabaseResourceId string
param azureOpenAiEndpoint string
param embeddingDeploymentName string

var searchCustomerCode = toLower(customerCode)
var portalApiKeyPlaceholder = '__ENTER_IN_AZURE_PORTAL__'

var projectsIndexTemplate = loadJsonContent('../search/projects-index.json')
var sharePointIndexTemplate = loadJsonContent('../search/sharepoint-index.json')
var sqlDataSourceTemplate = loadJsonContent('../search/sql-data-source.json')
var sqlSkillsetTemplate = loadJsonContent('../search/sql-vector-skillset.json')
var sqlIndexerTemplate = loadJsonContent('../search/sql-indexer.json')

var projectsIndex = union(projectsIndexTemplate, {
  name: '${searchCustomerCode}-projects'
})
var sharePointIndex = union(sharePointIndexTemplate, {
  name: '${searchCustomerCode}-sharepoint-${environment}'
})
var sqlDataSource = union(sqlDataSourceTemplate, {
  name: 'azuresql-${searchCustomerCode}-datasource'
  credentials: {
    connectionString: 'ResourceId=${sqlDatabaseResourceId};'
  }
})
var sqlEmbeddingSkill = union(sqlSkillsetTemplate.skills[0], {
  resourceUri: azureOpenAiEndpoint
  apiKey: portalApiKeyPlaceholder
  deploymentId: embeddingDeploymentName
})
var sqlSkillset = union(sqlSkillsetTemplate, {
  skills: [sqlEmbeddingSkill]
})
var sqlIndexer = union(sqlIndexerTemplate, {
  name: 'sql-${searchCustomerCode}-indexer'
  dataSourceName: sqlDataSource.name
  skillsetName: sqlSkillset.name
  targetIndexName: projectsIndex.name
  disabled: true
})

var searchConfiguration = {
  indexes: [
    projectsIndex
    sharePointIndex
  ]
  dataSources: [
    sqlDataSource
  ]
  skillsets: [
    sqlSkillset
  ]
  indexers: [
    sqlIndexer
  ]
}

resource searchService 'Microsoft.Search/searchServices@2026-03-01-preview' existing = {
  name: searchServiceName
}

resource configurationIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: 'uami-search-config-${searchCustomerCode}-${environment}'
  location: location
  tags: tags
}

var searchServiceContributorRoleId = subscriptionResourceId(
  'Microsoft.Authorization/roleDefinitions',
  '7ca78c08-252a-4471-8644-bb5ff32d4ba0'
)

resource searchServiceContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: guid(searchService.id, configurationIdentity.id, searchServiceContributorRoleId)
  scope: searchService
  properties: {
    principalId: configurationIdentity.properties.principalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: searchServiceContributorRoleId
  }
}

resource applySearchConfiguration 'Microsoft.Resources/deploymentScripts@2023-08-01' = {
  name: 'apply-search-config-${searchCustomerCode}-${environment}'
  location: location
  kind: 'AzureCLI'
  identity: {
    type: 'UserAssigned'
    userAssignedIdentities: {
      '${configurationIdentity.id}': {}
    }
  }
  properties: {
    azCliVersion: '2.67.0'
    cleanupPreference: 'OnSuccess'
    forceUpdateTag: uniqueString(string(searchConfiguration), searchEndpoint, sqlDatabaseResourceId, azureOpenAiEndpoint, embeddingDeploymentName)
    retentionInterval: 'P1D'
    scriptContent: '''
cat > search_configuration_apply.py <<'SEARCH_HELPER_PYTHON'
${loadTextContent('../../../scripts/pipeline/search_configuration_apply.py')}
SEARCH_HELPER_PYTHON
cat > search-configuration.json <<'SEARCH_CONFIGURATION_JSON'
${string(searchConfiguration)}
SEARCH_CONFIGURATION_JSON
python3 search_configuration_apply.py
'''
    timeout: 'PT30M'
    environmentVariables: [
      {
        name: 'SEARCH_ENDPOINT'
        value: searchEndpoint
      }
      {
        name: 'SEARCH_API_VERSION'
        value: '2025-09-01'
      }
      {
        name: 'SEARCH_CONFIGURATION_FILE'
        value: 'search-configuration.json'
      }
      {
        name: 'SEARCH_CONFIG_IDENTITY_CLIENT_ID'
        value: configurationIdentity.properties.clientId
      }
    ]
  }
  dependsOn: [
    searchServiceContributor
  ]
}
