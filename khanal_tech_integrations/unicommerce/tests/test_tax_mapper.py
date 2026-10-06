import unittest
from types import SimpleNamespace
from unittest.mock import patch

from khanal_tech_integrations.unicommerce.mappers import compute_tax_from_line, get_tax_code


class TestTaxMapper(unittest.TestCase):
    def setUp(self):
        self.tax_map_json = (
            '{"5_intra":"KACS5","12_intra":"KACS12","18_intra":"KACS18","28_intra":"KACS28",'
            '"5_inter":"KAIG5","12_inter":"KAIG12","18_inter":"KAIG18","28_inter":"KAIG28",'
            '"0_exempt":"KAEX"}'
        )

    def _mock_settings(self):
        return SimpleNamespace(tax_code_map=self.tax_map_json)

    def test_get_tax_code_all_intra_combinations(self):
        with patch("khanal_tech_integrations.unicommerce.mappers.tax.frappe.get_single", return_value=self._mock_settings()):
            self.assertEqual(get_tax_code(0, "KA", "KA"), "KAEX")
            self.assertEqual(get_tax_code(5, "KA", "KA"), "KACS5")
            self.assertEqual(get_tax_code(12, "KA", "KA"), "KACS12")
            self.assertEqual(get_tax_code(18, "KA", "KA"), "KACS18")
            self.assertEqual(get_tax_code(28, "KA", "KA"), "KACS28")

    def test_get_tax_code_all_inter_combinations(self):
        with patch("khanal_tech_integrations.unicommerce.mappers.tax.frappe.get_single", return_value=self._mock_settings()):
            self.assertEqual(get_tax_code(0, "TN", "KA"), "KAEX")
            self.assertEqual(get_tax_code(5, "TN", "KA"), "KAIG5")
            self.assertEqual(get_tax_code(12, "TN", "KA"), "KAIG12")
            self.assertEqual(get_tax_code(18, "TN", "KA"), "KAIG18")
            self.assertEqual(get_tax_code(28, "TN", "KA"), "KAIG28")

    def test_get_tax_code_missing_mapping_throws(self):
        with patch(
            "khanal_tech_integrations.unicommerce.mappers.tax.frappe.get_single",
            return_value=SimpleNamespace(tax_code_map='{"18_intra":"KACS18"}'),
        ):
            with self.assertRaises(Exception):
                get_tax_code(12, "TN", "KA")

    def test_compute_tax_from_line_exclusive(self):
        self.assertEqual(compute_tax_from_line(100, 2, 18, False), 36.00)

    def test_compute_tax_from_line_inclusive(self):
        # 236 inclusive @18% => tax 36.00
        self.assertEqual(compute_tax_from_line(118, 2, 18, True), 36.00)


if __name__ == "__main__":
    unittest.main()
