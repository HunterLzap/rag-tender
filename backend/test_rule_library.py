"""规则库目录测试。"""

import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from app.services.rule_library_service import list_rule_catalog


class RuleLibraryTests(unittest.TestCase):
    def test_rule_catalog_exposes_red_flag_rules(self) -> None:
        rules = list_rule_catalog()

        rule_ids = {rule["id"] for rule in rules}
        self.assertIn("submission.red_flag.deposit", rule_ids)
        self.assertIn("submission.red_flag.signature_seal", rule_ids)

        deposit = next(rule for rule in rules if rule["id"] == "submission.red_flag.deposit")
        self.assertEqual("投标待办", deposit["domain"])
        self.assertEqual("red_flag", deposit["rule_type"])
        self.assertEqual("strict", deposit["strictness"])
        self.assertIn("保证金", deposit["keywords"])
        self.assertTrue(deposit["enabled"])

    def test_format_self_defined_is_not_a_red_flag_keyword(self) -> None:
        rules = list_rule_catalog()
        format_rule = next(
            rule for rule in rules if rule["id"] == "submission.red_flag.format_copies"
        )

        self.assertNotIn("格式", format_rule["keywords"])
        self.assertIn("装订", format_rule["keywords"])


if __name__ == "__main__":
    unittest.main()
