from __future__ import annotations

import unittest

from scripts.pipeline.runtime_configuration import (
    NOT_CONFIGURED,
    ConfigurationDriftError,
    InMemorySecretPublisher,
    RUNTIME_SECRET_NAMES,
    build_runtime_configuration,
    publish_runtime_configuration,
)


class RuntimeConfigurationTests(unittest.TestCase):
    def setUp(self) -> None:
        self.values = build_runtime_configuration(
            {
                "sqlServerFqdn": {"value": "customer.database.windows.net"},
                "sqlDatabaseName": {"value": "sdb"},
                "aiEndpoint": {"value": "https://customer.openai.azure.com/"},
                "searchEndpoint": {"value": "https://customer.search.windows.net"},
                "gpt54DeploymentName": {"value": "gpt-5.4"},
                "gpt5MiniDeploymentName": {"value": "gpt-5-mini"},
                "textEmbedding3LargeDeploymentName": {"value": "text-embedding-3-large"},
            },
            {
                "sdbFunctionAppHostname": {"value": "sdb-functions.azurewebsites.net"},
                "documentParserFunctionAppHostname": {
                    "value": "sdb-parser.azurewebsites.net"
                },
            },
            "11111111-1111-1111-1111-111111111111",
        )

    def test_allowlist_excludes_identity_based_host_storage_connection(self) -> None:
        mappings = dict(RUNTIME_SECRET_NAMES)

        self.assertEqual(len(RUNTIME_SECRET_NAMES), 48)
        self.assertNotIn("AzureWebJobsStorage", mappings)
        self.assertNotIn("azure-web-jobs-storage", mappings.values())

    def test_safe_outputs_hydrate_endpoints_and_required_values_stay_not_configured(self) -> None:
        self.assertEqual(self.values["db-server-name"].value, "customer.database.windows.net")
        self.assertEqual(self.values["azure-openai-endpoint"].value, "https://customer.openai.azure.com/")
        self.assertEqual(self.values["azure-search-service-endpoint"].value, "https://customer.search.windows.net")
        self.assertEqual(self.values["llm-model-full"].value, "gpt-5.4")
        self.assertEqual(self.values["sp-tenant-id"].value, "11111111-1111-1111-1111-111111111111")
        self.assertEqual(
            self.values["extraction-endpoint"].value,
            "https://sdb-functions.azurewebsites.net/api/extraction",
        )
        self.assertEqual(
            self.values["document-parser-endpoint"].value,
            "https://sdb-parser.azurewebsites.net/api/http_trigger",
        )
        self.assertFalse(self.values["db-server-name"].value == NOT_CONFIGURED)
        self.assertEqual(self.values["db-password"].value, NOT_CONFIGURED)
        self.assertEqual(self.values["brave-search-api-key"].value, NOT_CONFIGURED)
        self.assertFalse(self.values["db-password"].hydrated)

    def test_invalid_endpoint_output_is_not_hydrated(self) -> None:
        values = build_runtime_configuration(
            {"aiEndpoint": {"value": "http://insecure.example"}},
            {},
            "invalid-tenant-id",
        )

        self.assertEqual(values["azure-openai-endpoint"].value, NOT_CONFIGURED)
        self.assertEqual(values["sp-tenant-id"].value, NOT_CONFIGURED)

    def test_publication_is_idempotent_and_preserves_retired_vault_entries(self) -> None:
        publisher = InMemorySecretPublisher(
            {"azure-web-jobs-storage": "legacy-value", "brave-search-api-key": "operator-key"}
        )

        first = publish_runtime_configuration(self.values, publisher)
        first_write_count = len(publisher.set_calls)
        second = publish_runtime_configuration(self.values, publisher)

        self.assertIn("document-parser-endpoint", first.created)
        self.assertIn("db-password", first.created)
        self.assertEqual(second.created, ())
        self.assertEqual(second.updated, ())
        self.assertEqual(len(publisher.set_calls), first_write_count)
        self.assertEqual(publisher.values["brave-search-api-key"], "operator-key")
        self.assertEqual(publisher.values["azure-web-jobs-storage"], "legacy-value")

    def test_hydration_updates_not_configured_value_and_refuses_drift_before_writing(self) -> None:
        publisher = InMemorySecretPublisher(
            {"db-server-name": NOT_CONFIGURED, "db-name": "operator-database"}
        )

        with self.assertRaises(ConfigurationDriftError) as error:
            publish_runtime_configuration(self.values, publisher)

        self.assertIn("db-name", error.exception.names)
        self.assertEqual(publisher.values["db-server-name"], NOT_CONFIGURED)
        self.assertEqual(publisher.set_calls, [])

        no_drift = dict(self.values)
        no_drift["db-name"] = type(self.values["db-name"])(NOT_CONFIGURED, False)
        result = publish_runtime_configuration(no_drift, publisher)

        self.assertIn("db-server-name", result.updated)
        self.assertEqual(publisher.values["db-server-name"], "customer.database.windows.net")


if __name__ == "__main__":
    unittest.main()
