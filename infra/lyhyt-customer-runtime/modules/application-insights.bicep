param componentName string
param location string
param tags object
param workspaceResourceId string

resource applicationInsights 'Microsoft.Insights/components@2020-02-02' = {
  name: componentName
  location: location
  kind: 'web'
  tags: tags
  properties: {
    Application_Type: 'web'
    Flow_Type: 'Bluefield'
    IngestionMode: 'LogAnalytics'
    WorkspaceResourceId: workspaceResourceId
  }
}

@secure()
output connectionString string = applicationInsights.listConnectionStrings('2021-05-01-preview').connectionStrings[0].connectionString
output resourceId string = applicationInsights.id
output name string = applicationInsights.name
