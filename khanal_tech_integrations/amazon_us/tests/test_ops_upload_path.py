"""
Tests for _resolve_upload_path -- confines enqueue_csv_comparison/
enqueue_reconciliation's csv_path input to the site's private/files
directory, rejecting arbitrary-file-read attempts (../ traversal,
absolute paths outside it) that were previously accepted as long as
os.path.isfile() returned True.
"""
import os
import unittest

import frappe

from khanal_tech_integrations.amazon_us.api import ops


class TestResolveUploadPath(unittest.TestCase):
    def setUp(self):
        self.legit_path = frappe.get_site_path("private", "files", "test_resolve_upload_path.csv")
        with open(self.legit_path, "w") as f:
            f.write("dummy\n")

    def tearDown(self):
        if os.path.exists(self.legit_path):
            os.remove(self.legit_path)

    def test_accepts_file_under_private_files(self):
        resolved = ops._resolve_upload_path(self.legit_path)
        self.assertEqual(resolved, os.path.realpath(self.legit_path))

    def test_rejects_absolute_path_outside_private_files(self):
        with self.assertRaises(frappe.ValidationError):
            ops._resolve_upload_path("/etc/passwd")

    def test_rejects_traversal_back_out_of_private_files(self):
        traversal = frappe.get_site_path("private", "files", "..", "..", "..", "etc", "passwd")
        with self.assertRaises(frappe.ValidationError):
            ops._resolve_upload_path(traversal)

    def test_rejects_nonexistent_file_inside_private_files(self):
        missing = frappe.get_site_path("private", "files", "does_not_exist.csv")
        with self.assertRaises(frappe.ValidationError):
            ops._resolve_upload_path(missing)
