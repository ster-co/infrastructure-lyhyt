import hashlib
import json
import os
import re
import shutil
import subprocess
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


class KeyVaultArchitectureTests(unittest.TestCase):
    def read(self, relative_path: str) -> str:
        return (ROOT / relative_path).read_text(encoding="utf-8")

    def build_json(self, relative_path: str) -> dict:
        az = shutil.which("az")
        if az is None:
            self.skipTest("Azure CLI is not installed")
        env = os.environ.copy()
        env.setdefault("AZURE_CONFIG_DIR", "/tmp/lyhyt-az")
        env.setdefault("DOTNET_BUNDLE_EXTRACT_BASE_DIR", "/tmp/lyhyt-bicep-extract")
        result = subprocess.run(
            [az, "bicep", "build", "--file", str(ROOT / relative_path), "--stdout"],
            check=False,
            capture_output=True,
            text=True,
            env=env,
        )
        self.assertEqual(
            result.returncode,
            0,
            f"Bicep build failed for {relative_path}:\n{result.stderr}",
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

    @staticmethod
    def stable_name(prefix: str, *stable_inputs: str) -> str:
        suffix = hashlib.sha256("\x00".join(stable_inputs).encode()).hexdigest()[:13]
        return f"{prefix}{suffix}"

    def test_platform_key_vault_contract_is_rbac_only_and_safe(self):
        main = self.read("infra/lyhyt-platform/main.bicep")
        module = self.read("infra/lyhyt-platform/modules/key-vault.bicep")

        self.assertIn("module platformKeyVault './modules/key-vault.bicep'", main)
        for output_name in (
            "platformKeyVaultResourceId",
            "platformKeyVaultName",
            "platformKeyVaultUri",
        ):
            self.assertRegex(main, re.compile(rf"^output {output_name} ", re.MULTILINE))
        self.assertIn("enableRbacAuthorization: true", module)
        self.assertIn("accessPolicies: []", module)
        self.assertIn("enablePurgeProtection", module)
        self.assertNotIn("Microsoft.KeyVault/vaults/secrets", module)
        self.assertRegex(main, r"platformKeyVaultName = 'kvp\$\{uniqueString\(")

    def test_customer_key_vault_contract_and_same_tenant_handoff(self):
        main = self.read("infra/customer-foundation/main.bicep")
        module = self.read("infra/customer-foundation/modules/key-vault-role-assignment.bicep")

        for output_name in (
            "customerKeyVaultResourceId",
            "customerKeyVaultName",
            "customerKeyVaultUri",
        ):
            self.assertRegex(main, re.compile(rf"^output {output_name} ", re.MULTILINE))
        self.assertIn("runtimeAccessPrincipalId", main)
        self.assertIn("enableSameTenantRuntimeKeyVaultRoleAssignment", main)
        self.assertIn("principalType: 'ServicePrincipal'", module)
        self.assertIn("4633458b-17de-408a-b874-0445c86b69e6", main)
        self.assertNotIn("Microsoft.KeyVault/vaults/secrets", module)
        self.assertRegex(main, r"keyVaultName = 'kvc\$\{uniqueString\(")

    def test_runtime_uami_and_typed_key_vault_contract(self):
        identity = self.read("infra/lyhyt-customer-runtime/modules/identity.bicep")
        main = self.read("infra/lyhyt-customer-runtime/main.bicep")
        container_app = self.read("infra/lyhyt-customer-runtime/modules/container-app.bicep")

        for output_name in (
            "identityResourceId",
            "identityPrincipalId",
            "identityClientId",
            "identityName",
        ):
            self.assertRegex(identity, re.compile(rf"^output {output_name} ", re.MULTILINE))
            self.assertRegex(main, re.compile(rf"^output {output_name} ", re.MULTILINE))

        self.assertIn("type keyVaultConfigurationType = {", main)
        for contract_key in (
            "enabled",
            "customerKeyVaultResourceId",
            "customerKeyVaultUri",
            "platformKeyVaultResourceId",
            "platformKeyVaultUri",
            "requireKeyVault",
        ):
            self.assertIn(contract_key, main)

        self.assertIn("managedIdentityClientId: identity.outputs.identityClientId", main)
        self.assertIn("keyVaultIntegrationEnabled: keyVaultConfiguration.enabled", main)
        self.assertIn("keyVaultIntegrationEnabled ? [", container_app)
        self.assertIn("enabled: false", main)
        self.assertIn("requireKeyVault: false", main)
        for environment_name in (
            "AZURE_CLIENT_ID",
            "CLIENT_KEY_VAULT_URI",
            "PLATFORM_KEY_VAULT_URI",
            "REQUIRE_KEY_VAULT",
            "CUSTOMER_CODE",
            "ENVIRONMENT",
        ):
            self.assertIn(f"name: '{environment_name}'", container_app)
        self.assertNotIn("keyVaultUrl", container_app)
        self.assertNotIn("secretRef", container_app)
        self.assertNotIn("secrets:", container_app)
        self.assertNotRegex(container_app, r"param\s+keyVaultConfiguration\s+object")

    def test_external_resource_references_are_canonical(self):
        runtime = self.read("infra/lyhyt-customer-runtime/main.bicep")
        acr_module = self.read("infra/lyhyt-customer-runtime/modules/role-assignment.bicep")
        platform_module = self.read(
            "infra/lyhyt-customer-runtime/modules/key-vault-role-assignment.bicep"
        )
        foundation_module = self.read(
            "infra/customer-foundation/modules/key-vault-role-assignment.bicep"
        )

        self.assertIn("type containerRegistryReferenceType = {", runtime)
        self.assertIn("resourceId: string", runtime)
        self.assertIn("loginServer: string", runtime)
        for forbidden in (
            "param containerRegistryName",
            "param containerRegistryResourceGroupName",
            "param platformKeyVaultName",
            "param platformKeyVaultResourceGroupName",
        ):
            self.assertNotIn(forbidden, runtime)
        for module in (acr_module, platform_module, foundation_module):
            self.assertIn("targetScope = 'resourceGroup'", module)
            self.assertIn("split(", module)
            self.assertIn("subscriptionResourceId(", module)
            self.assertIn("scope: ", module)
        self.assertIn("scope: resourceGroup(containerRegistrySubscriptionId, containerRegistryResourceGroupName)", runtime)
        self.assertIn("scope: resourceGroup(platformKeyVaultSubscriptionId, platformKeyVaultResourceGroupName)", runtime)

    def test_key_vault_names_are_bounded_and_distinct(self):
        names = [
            self.stable_name("kvp", "subscription", "rg-lyhyt-platform-tst-swec", "platform"),
            self.stable_name("kvc", "subscription", "rg-pilot-foundation-tst-swec", "pilot", "tst", "swec"),
            self.stable_name("kvc", "subscription", "rg-other-foundation-tst-swec", "other", "tst", "swec"),
        ]
        for name in names:
            self.assertGreaterEqual(len(name), 3)
            self.assertLessEqual(len(name), 24)
            self.assertRegex(name, r"^[a-z][a-z0-9-]*[a-z0-9]$")
        self.assertEqual(names[0], self.stable_name("kvp", "subscription", "rg-lyhyt-platform-tst-swec", "platform"))
        self.assertNotEqual(names[1], names[2])
        self.assertNotEqual(names[0], names[1])

    def test_compiled_runtime_contains_uami_mappings_and_role_dependencies(self):
        template = self.build_json("infra/lyhyt-customer-runtime/main.bicep")
        resources = list(self.walk_resources(template))
        role_scopes = [
            resource.get("scope", "")
            for resource in resources
            if resource.get("type") == "Microsoft.Authorization/roleAssignments"
        ]
        self.assertTrue(any("ContainerRegistry" in scope for scope in role_scopes))
        self.assertTrue(any("KeyVault" in scope for scope in role_scopes))

        container_deployments = [
            resource
            for resource in resources
            if resource.get("type") == "Microsoft.Resources/deployments"
            and "deploy-container-app-" in resource.get("name", "")
        ]
        self.assertEqual(len(container_deployments), 1)
        dependency_text = json.dumps(container_deployments[0].get("dependsOn", []))
        self.assertIn("acrPullRoleAssignment", dependency_text)
        self.assertIn("platformKeyVaultRoleAssignment", dependency_text)

        container_apps = [
            resource
            for resource in resources
            if resource.get("type") == "Microsoft.App/containerApps"
        ]
        self.assertEqual(len(container_apps), 1)
        compiled_text = json.dumps(template)
        for setting in (
            "AZURE_CLIENT_ID",
            "CLIENT_KEY_VAULT_URI",
            "PLATFORM_KEY_VAULT_URI",
            "REQUIRE_KEY_VAULT",
            "CUSTOMER_CODE",
            "ENVIRONMENT",
        ):
            self.assertIn(setting, compiled_text)
        self.assertIn("keyVaultIntegrationEnabled", compiled_text)
        self.assertIn("managedIdentityClientId", compiled_text)
        self.assertEqual(
            len(re.findall(r"name: '([^']+)'", self.read("infra/lyhyt-customer-runtime/modules/container-app.bicep"))),
            len(set(re.findall(r"name: '([^']+)'", self.read("infra/lyhyt-customer-runtime/modules/container-app.bicep")))),
        )

    def test_compiled_role_assignment_modules_use_canonical_scopes(self):
        for relative_path in (
            "infra/lyhyt-customer-runtime/modules/role-assignment.bicep",
            "infra/lyhyt-customer-runtime/modules/key-vault-role-assignment.bicep",
            "infra/customer-foundation/modules/key-vault-role-assignment.bicep",
        ):
            template = self.build_json(relative_path)
            role_resources = [
                resource
                for resource in self.walk_resources(template)
                if resource.get("type") == "Microsoft.Authorization/roleAssignments"
            ]
            self.assertEqual(len(role_resources), 1, relative_path)
            scope = role_resources[0].get("scope", "")
            self.assertTrue(
                "ContainerRegistry" in scope or "KeyVault" in scope,
                relative_path,
            )

        runtime_resources = list(
            self.walk_resources(self.build_json("infra/lyhyt-customer-runtime/main.bicep"))
        )
        external_role_deployments = [
            resource
            for resource in runtime_resources
            if resource.get("type") == "Microsoft.Resources/deployments"
            and (
                "assign-acr-pull-" in resource.get("name", "")
                or "assign-platform-key-vault-secrets-user-" in resource.get("name", "")
            )
        ]
        self.assertEqual(len(external_role_deployments), 2)
        for deployment in external_role_deployments:
            self.assertIn("SubscriptionId", deployment.get("subscriptionId", ""))
            self.assertIn("ResourceGroupName", deployment.get("resourceGroup", ""))

    def test_role_assignments_are_optional_and_target_the_runtime_principal(self):
        platform = self.read("infra/lyhyt-platform/main.bicep")
        foundation = self.read("infra/customer-foundation/main.bicep")
        runtime = self.read("infra/lyhyt-customer-runtime/main.bicep")

        self.assertIn("param enablePlatformKeyVault bool = false", platform)
        self.assertIn("param enableSameTenantRuntimeKeyVaultRoleAssignment bool = false", foundation)
        self.assertIn("param enablePlatformKeyVaultRoleAssignment bool = false", runtime)
        self.assertIn("principalId: identity.outputs.identityPrincipalId", runtime)
        self.assertIn("keyVaultSecretsUserRoleDefinitionId", runtime)
        self.assertNotIn("Key Vault Secrets Officer", runtime)
        self.assertNotIn("Key Vault Administrator", runtime)

    def test_secret_surfaces_are_absent_from_outputs_params_and_container_app(self):
        entry_points = (
            "infra/lyhyt-platform/main.bicep",
            "infra/customer-foundation/main.bicep",
            "infra/lyhyt-customer-runtime/main.bicep",
        )
        forbidden_output_names = re.compile(
            r"(secret|password|connection|string|token|apiKey|sharedKey)", re.IGNORECASE
        )
        for relative_path in entry_points:
            source = self.read(relative_path)
            for output_name in re.findall(r"^output\s+(\w+)", source, re.MULTILINE):
                self.assertIsNone(
                    forbidden_output_names.search(output_name),
                    f"secret-looking output: {relative_path}:{output_name}",
                )

        container_app = self.read("infra/lyhyt-customer-runtime/modules/container-app.bicep")
        self.assertNotRegex(
            self.read("infra/lyhyt-customer-runtime/main.bicep"),
            r"^output\s+workspaceSharedKey\b",
        )
        self.assertNotIn("Microsoft.KeyVault/vaults/secrets", "\n".join(
            self.read(path)
            for path in (
                "infra/lyhyt-platform/main.bicep",
                "infra/lyhyt-platform/modules/key-vault.bicep",
                "infra/customer-foundation/main.bicep",
                "infra/customer-foundation/modules/key-vault.bicep",
                "infra/customer-foundation/modules/key-vault-role-assignment.bicep",
                "infra/lyhyt-customer-runtime/main.bicep",
                "infra/lyhyt-customer-runtime/modules/container-app.bicep",
                "infra/lyhyt-customer-runtime/modules/key-vault-role-assignment.bicep",
            )
        ))
        self.assertNotIn("SystemAssigned", container_app)
        for migrated_secret_name in (
            "AZURE_OPENAI_API_KEY",
            "AZURE_SEARCH_API_KEY",
            "DB_PASSWORD",
            "DB_USER_NAME",
            "SP_SECRET_VALUE",
            "AzureWebJobsStorage",
            "MAIL_ATTACHMENTS_STORAGE_CONNECTION",
            "SESSION_SECRET",
            "EXTRACTION_CODE",
            "DOCUMENT_PARSER_CODE",
            "AFAS_API_KEY",
            "BRAVE_SEARCH_API_KEY",
        ):
            self.assertNotIn(f"name: '{migrated_secret_name}'", container_app)

        forbidden_parameter_names = re.compile(
            r"(password|connectionString|accessToken|apiKey|sharedKey)", re.IGNORECASE
        )
        for parameter_file in (ROOT / "infra").glob("**/*.bicepparam"):
            parameter_text = parameter_file.read_text(encoding="utf-8")
            for migrated_secret_name in (
                "AZURE_OPENAI_API_KEY",
                "AZURE_SEARCH_API_KEY",
                "DB_PASSWORD",
                "DB_USER_NAME",
                "SP_SECRET_VALUE",
                "AzureWebJobsStorage",
                "MAIL_ATTACHMENTS_STORAGE_CONNECTION",
                "SESSION_SECRET",
                "EXTRACTION_CODE",
                "DOCUMENT_PARSER_CODE",
                "AFAS_API_KEY",
                "BRAVE_SEARCH_API_KEY",
                "azure-openai-api-key",
                "azure-search-api-key",
                "db-password",
                "db-user-name",
                "sp-secret-value",
                "azure-web-jobs-storage",
                "mail-attachments-storage-connection",
                "session-secret",
                "extraction-code",
                "document-parser-code",
                "afas-api-key",
                "brave-search-api-key",
            ):
                self.assertNotIn(migrated_secret_name, parameter_text)
            for line in parameter_text.splitlines():
                match = re.match(r"\s*param\s+(\w+)\s*=", line)
                if match:
                    self.assertIsNone(
                        forbidden_parameter_names.search(match.group(1)),
                        f"secret-looking parameter: {parameter_file}:{line}",
                    )

    def test_documentation_records_allowlists_and_identity_verification(self):
        documentation = self.read("docs/key-vault-contract.md")
        for secret_name in (
            "azure-openai-api-key",
            "azure-search-api-key",
            "db-password",
            "db-user-name",
            "sp-secret-value",
            "azure-web-jobs-storage",
            "mail-attachments-storage-connection",
            "session-secret",
            "extraction-code",
            "document-parser-code",
            "afas-api-key",
            "brave-search-api-key",
        ):
            self.assertIn(f"`{secret_name}`", documentation)
        self.assertIn("azure-identity 1.25.3", documentation)
        self.assertIn("AZURE_CLIENT_ID", documentation)
        self.assertIn("DefaultAzureCredential", documentation)


if __name__ == "__main__":
    unittest.main()
