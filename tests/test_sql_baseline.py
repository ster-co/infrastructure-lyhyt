from pathlib import Path
import unittest


BASELINE = Path(__file__).parents[1] / "docs" / "database" / "0001_baseline.sql"

EXPECTED_TABLES = {
    "cc_analysis",
    "cc_categories",
    "cc_document_types",
    "cc_info",
    "cc_lg_checkpoints",
    "cc_lg_writes",
    "cc_locations",
    "cc_mail_origin",
    "cc_nota",
    "cc_offerte_summary",
    "cc_partners",
    "cc_project_deadline_sync",
    "cc_project_members",
    "cc_projectrows",
    "cc_projects",
    "cc_projectsources",
    "cc_prompting",
    "cc_prompts",
    "cc_requests",
    "cc_schema",
    "cc_services",
    "cc_sessions",
    "cc_share_links",
    "cc_source_pointers",
    "cc_sources",
    "cc_stabucodes",
    "cc_test",
    "cc_werk_type",
    "getemail",
    "graph_subscription",
    "graph_sync_state",
    "mail_review",
    "mail_review_attachment",
    "settings_attributes",
    "settings_entity",
    "settings_value",
}


class SqlBaselineTests(unittest.TestCase):
    def _read_baseline(self):
        self.assertTrue(BASELINE.exists(), f"Missing baseline: {BASELINE}")
        return BASELINE.read_text(encoding="utf-8")

    def test_baseline_contains_only_application_tables_and_required_objects(self):
        sql = self._read_baseline()

        for table_name in EXPECTED_TABLES:
            self.assertIn(f"CREATE TABLE [dbo].[{table_name}]", sql)

        self.assertNotIn("CREATE TABLE [dbo].[MSchange_tracking_history]", sql)
        self.assertNotIn("CREATE VIEW [sys].[database_firewall_rules]", sql)
        self.assertIn("CREATE VIEW [dbo].[vw_projects]", sql)
        self.assertEqual(sql.count("CREATE TRIGGER [dbo]."), 29)


    def test_baseline_preserves_schema_dependencies_and_index_details(self):
        sql = self._read_baseline()

        self.assertIn("ON DELETE CASCADE", sql)
        self.assertIn("ON DELETE SET NULL", sql)
        self.assertIn("FK_cc_sources_cc_info", sql)
        self.assertIn("WITH CHECK", sql)
        self.assertIn("INCLUDE ([projectrow_id], [requested_at]", sql)
        self.assertIn("CONSTRAINT [UX_cc_projectrows_project_stabucode] UNIQUE", sql)
