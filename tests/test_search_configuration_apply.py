"""Tests for applying the customer foundation's Azure AI Search objects."""

from __future__ import annotations

import copy
import importlib.util
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
HELPER_PATH = ROOT / "scripts/pipeline/search_configuration_apply.py"


class FakeResponse:
    def __init__(self, status: int):
        self.status = status


class FakeSearchApi:
    def __init__(self) -> None:
        self.resources: dict[tuple[str, str], dict] = {}
        self.calls: list[tuple[str, str, str, dict | None]] = []

    def request(
        self,
        method: str,
        collection: str,
        name: str,
        body: dict | None = None,
    ) -> FakeResponse:
        key = (collection, name)
        self.calls.append((method, collection, name, body))
        if method == "GET":
            return FakeResponse(200 if key in self.resources else 404)
        self.resources[key] = copy.deepcopy(body or {})
        return FakeResponse(201)


def load_apply_module(test: unittest.TestCase):
    test.assertTrue(
        HELPER_PATH.is_file(),
        "Search configuration apply helper has not been implemented",
    )
    spec = importlib.util.spec_from_file_location("search_configuration_apply", HELPER_PATH)
    test.assertIsNotNone(spec)
    test.assertIsNotNone(spec.loader)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sample_configuration() -> dict:
    return {
        "indexes": [
            {"name": "pilot-projects", "fields": []},
            {"name": "pilot-sharepoint-tst", "fields": []},
        ],
        "dataSources": [{"name": "azuresql-pilot-datasource", "type": "azuresql"}],
        "skillsets": [
            {
                "name": "sql-vector-skillset",
                "skills": [{"apiKey": "__ENTER_IN_AZURE_PORTAL__"}],
            }
        ],
        "indexers": [
            {
                "name": "sql-pilot-indexer",
                "disabled": True,
                "skillsetName": "sql-vector-skillset",
            }
        ],
    }


def sample_deployment_outputs() -> dict:
    return {
        "searchEndpoint": "https://search-pilot-tst-swec.search.windows.net",
        "sqlDatabaseResourceId": "/subscriptions/11111111/resourceGroups/rg-pilot/providers/Microsoft.Sql/servers/sql-pilot/databases/sqldb-pilot-tst",
        "aiEndpoint": "https://ai-pilot-tst-swec.cognitiveservices.azure.com/",
        "textEmbedding3LargeDeploymentName": "text-embedding-3-large",
    }


class SearchConfigurationApplyTests(unittest.TestCase):
    def test_search_configuration_runs_only_for_public_search_in_tst(self) -> None:
        module = load_apply_module(self)
        self.assertTrue(
            module.should_apply_search_configuration(
                "tst", {"enableSearchService": True, "publicNetworkAccess": "Enabled"}
            )
        )
        for environment, parameters in (
            ("acc", {"enableSearchService": True, "publicNetworkAccess": "Enabled"}),
            ("tst", {"enableSearchService": False, "publicNetworkAccess": "Enabled"}),
            ("tst", {"enableSearchService": True, "publicNetworkAccess": "Disabled"}),
        ):
            with self.subTest(environment=environment, parameters=parameters):
                self.assertFalse(module.should_apply_search_configuration(environment, parameters))

    def test_builds_customer_configuration_from_json_templates_and_outputs(self) -> None:
        module = load_apply_module(self)
        configuration = module.build_search_configuration(
            ROOT / "infra/customer-foundation/search",
            "Pilot-Co",
            "tst",
            sample_deployment_outputs(),
        )

        self.assertEqual(
            [item["name"] for item in configuration["indexes"]],
            ["pilot-co-projects", "pilot-co-sharepoint-tst"],
        )
        self.assertEqual(
            configuration["dataSources"][0]["credentials"]["connectionString"],
            "ResourceId=/subscriptions/11111111/resourceGroups/rg-pilot/providers/Microsoft.Sql/servers/sql-pilot/databases/sqldb-pilot-tst;",
        )
        skill = configuration["skillsets"][0]["skills"][0]
        self.assertEqual(
            skill["resourceUri"], "https://ai-pilot-tst-swec.cognitiveservices.azure.com"
        )
        self.assertEqual(skill["deploymentId"], "text-embedding-3-large")
        self.assertEqual(skill["apiKey"], "__ENTER_IN_AZURE_PORTAL__")
        indexer = configuration["indexers"][0]
        self.assertEqual(indexer["dataSourceName"], "azuresql-pilot-co-datasource")
        self.assertEqual(indexer["targetIndexName"], "pilot-co-projects")
        self.assertTrue(indexer["disabled"])

    def test_first_apply_creates_objects_in_dependency_order(self) -> None:
        module = load_apply_module(self)
        api = FakeSearchApi()
        module.apply_search_configuration(sample_configuration(), api.request, emit=lambda _: None)

        writes = [(method, collection, name) for method, collection, name, _ in api.calls if method == "PUT"]
        self.assertEqual(
            writes,
            [
                ("PUT", "indexes", "pilot-projects"),
                ("PUT", "indexes", "pilot-sharepoint-tst"),
                ("PUT", "datasources", "azuresql-pilot-datasource"),
                ("PUT", "skillsets", "sql-vector-skillset"),
                ("PUT", "indexers", "sql-pilot-indexer"),
            ],
        )
        self.assertTrue(api.resources[("indexers", "sql-pilot-indexer")]["disabled"])

    def test_reapply_preserves_portal_skillset_key_and_indexer_state(self) -> None:
        module = load_apply_module(self)
        api = FakeSearchApi()
        configuration = sample_configuration()
        module.apply_search_configuration(configuration, api.request, emit=lambda _: None)

        skillset = api.resources[("skillsets", "sql-vector-skillset")]
        skillset["skills"][0]["apiKey"] = "portal-managed-value"
        indexer = api.resources[("indexers", "sql-pilot-indexer")]
        indexer["disabled"] = False
        api.calls.clear()
        messages: list[str] = []

        module.apply_search_configuration(configuration, api.request, emit=messages.append)

        writes = [(method, collection, name) for method, collection, name, _ in api.calls if method == "PUT"]
        self.assertEqual(
            writes,
            [
                ("PUT", "indexes", "pilot-projects"),
                ("PUT", "indexes", "pilot-sharepoint-tst"),
                ("PUT", "datasources", "azuresql-pilot-datasource"),
            ],
        )
        self.assertEqual(
            api.resources[("skillsets", "sql-vector-skillset")]["skills"][0]["apiKey"],
            "portal-managed-value",
        )
        self.assertFalse(api.resources[("indexers", "sql-pilot-indexer")]["disabled"])
        self.assertNotIn("portal-managed-value", "\n".join(messages))

    def test_non_not_found_read_error_aborts_create_once_objects(self) -> None:
        module = load_apply_module(self)
        api = FakeSearchApi()

        def failing_request(method: str, collection: str, name: str, body: dict | None = None) -> FakeResponse:
            if method == "GET" and collection == "skillsets":
                return FakeResponse(403)
            return api.request(method, collection, name, body)

        with self.assertRaises(module.SearchConfigurationError):
            module.apply_search_configuration(
                sample_configuration(), failing_request, emit=lambda _: None
            )

    def test_actual_skillset_key_is_rejected_before_any_request(self) -> None:
        module = load_apply_module(self)
        api = FakeSearchApi()
        configuration = sample_configuration()
        configuration["skillsets"][0]["skills"][0]["apiKey"] = "test-secret-value"

        with self.assertRaises(module.SearchConfigurationError):
            module.apply_search_configuration(
                configuration, api.request, emit=lambda _: None
            )

        self.assertEqual(api.calls, [])


if __name__ == "__main__":
    unittest.main()
