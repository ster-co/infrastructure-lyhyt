/*
Run this script in the customer database as a Microsoft Entra administrator
after the SQL baseline migration creates dbo.vw_projects. Replace the clearly
marked value with the deployed Search service name.
*/

IF DATABASE_PRINCIPAL_ID(N'__SEARCH_SERVICE_NAME__') IS NULL
BEGIN
    CREATE USER [__SEARCH_SERVICE_NAME__] FROM EXTERNAL PROVIDER;
END;
GO

GRANT SELECT ON OBJECT::dbo.vw_projects TO [__SEARCH_SERVICE_NAME__];
GO
