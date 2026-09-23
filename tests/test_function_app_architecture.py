import json
import os
import re
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
RUNTIME = ROOT / "infra" / "lyhyt-customer-runtime"


class FunctionAppArchitectureTests(unittest.TestCase):
    def read(self, relative_path: str) -> str:
        return (ROOT / relative_path).read_text(encoding="utf-8")

    def build_runtime(self) -> dict:
        az = shutil.which("az")
        if az is None:
            self.skipTest("Azure CLI is not installed")
        env = os.environ.copy()
        env.setdefault("AZURE_CONFIG_DIR", "/tmp/lyhyt-az")
        env.setdefault("DOTNET_BUNDLE_EXTRACT_BASE_DIR", "/tmp/lyhyt-bicep-extract")
        result = subprocess.run(
            [
                az,
                "bicep",
                "build",
                "--file",
                str(RUNTIME / "main.bicep"),
                "--stdout",
                "--no-restore",
            ],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"Bicep build failed:\n{result.stderr}",
        )
        return json.loads(result.stdout)

    def walk_resources(self, value):
        if isinstance(value, dict):
            if "type" in value:
                yield value
            for child in value.values():
                yield from self.walk_resources(child)
        elif isinstance(value, list):
            for child in value:
                yield from self.walk_resources(child)

    def test_runtime_declares_two_workload_specific_function_apps(self):
        source = self.read("infra/lyhyt-customer-runtime/main.bicep")

        self.assertIn("documentParserFunctionApp", source)
        self.assertIn("mailboxSyncFunctionApp", source)
        self.assertIn("document-parser", source)
        self.assertIn("mailbox-sync", source)
        self.assertIn("module functionHostStorage", source)

    def test_compiled_runtime_contains_separate_function_apps_and_identities(self):
        resources = list(self.walk_resources(self.build_runtime()))

        function_apps = [
            resource
            for resource in resources
            if resource.get("type") == "Microsoft.Web/sites"
        ]
        self.assertEqual(len(function_apps), 2)

        identities = [
            resource
            for resource in resources
            if resource.get("type")
            == "Microsoft.ManagedIdentity/userAssignedIdentities"
        ]
        self.assertEqual(len(identities), 3)

        host_storage = [
            resource
            for resource in resources
            if resource.get("type") == "Microsoft.Storage/storageAccounts"
        ]
        self.assertEqual(len(host_storage), 1)

    def test_function_apps_use_identity_based_host_storage_and_workload_settings(self):
        resources = list(self.walk_resources(self.build_runtime()))
        function_apps = [
            resource
            for resource in resources
            if resource.get("type") == "Microsoft.Web/sites"
        ]
        self.assertEqual(len(function_apps), 2)
        compiled_function_apps = json.dumps(function_apps)
        for setting_name in (
            "FUNCTIONS_WORKER_RUNTIME",
            "FUNCTIONS_EXTENSION_VERSION",
            "AzureWebJobsStorage__credential",
            "AzureWebJobsStorage__blobServiceUri",
            "AzureWebJobsStorage__queueServiceUri",
            "AzureWebJobsStorage__tableServiceUri",
            "AzureWebJobsStorage__clientId",
            "FUNCTION_WORKLOAD",
        ):
            self.assertIn(setting_name, compiled_function_apps)
        self.assertIn("managedidentity", compiled_function_apps)

        function_module = self.read(
            "infra/lyhyt-customer-runtime/modules/function-app.bicep"
        )
        self.assertIsNone(
            re.search(
                r"(PASSWORD|SECRET|TOKEN|API_KEY|CONNECTION_STRING|SAS)",
                function_module,
                re.IGNORECASE,
            )
        )

    def test_runtime_outputs_identify_each_function_app_and_identity(self):
        source = self.read("infra/lyhyt-customer-runtime/main.bicep")

        for output_name in (
            "documentParserFunctionAppResourceId",
            "documentParserFunctionAppHostname",
            "documentParserIdentityPrincipalId",
            "mailboxSyncFunctionAppResourceId",
            "mailboxSyncFunctionAppHostname",
            "mailboxSyncIdentityPrincipalId",
            "functionHostStorageResourceId",
        ):
            self.assertRegex(source, re.compile(rf"^output {output_name} ", re.MULTILINE))

    def test_runtime_example_uses_an_immutable_container_image_reference(self):
        params = self.read(
            "infra/lyhyt-customer-runtime/environments/customer.example.bicepparam"
        )
        self.assertRegex(params, r"param containerImage\s*=.*@sha256:[0-9a-f]{64}")
        self.assertIn("functionPlanSkuName", params)
        self.assertIn("functionWorkerRuntimeVersion", params)


if __name__ == "__main__":
    unittest.main()
