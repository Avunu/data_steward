# Copyright (c) 2025, Avunu LLC and Contributors
# See license.txt

import frappe
from frappe.tests.utils import FrappeTestCase

from jailbreak.jailbreak.hooks.file import merge_files


class TestFileMerge(FrappeTestCase):
	def setUp(self):
		# Store original file_merge capability state and enable it
		settings = frappe.get_single("Jailbreak Settings")
		self._original_file_merge = settings.file_merge
		settings.file_merge = 1
		settings.save()

	def tearDown(self):
		# Restore original file_merge capability state
		settings = frappe.get_single("Jailbreak Settings")
		settings.file_merge = self._original_file_merge
		settings.save()

	def test_merge_files_basic(self):
		"""Test basic file merge functionality"""
		# Create two test files
		source_file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "test_source.txt",
				"is_private": 0,
				"file_url": "/files/test_source.txt",
			}
		).insert()

		target_file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "test_target.txt",
				"is_private": 0,
				"file_url": "/files/test_target.txt",
			}
		).insert()

		# Merge source into target
		result = merge_files(source_file.name, target_file.name)

		# Verify result
		self.assertTrue(result["success"])
		self.assertIn("merged", result["message"].lower())

		# Verify source file is deleted
		self.assertFalse(frappe.db.exists("File", source_file.name))

		# Verify target file still exists
		self.assertTrue(frappe.db.exists("File", target_file.name))

		# Clean up
		frappe.delete_doc("File", target_file.name, force=True)

	def test_merge_files_prevents_self_merge(self):
		"""Test that merging a file into itself is prevented"""
		# Create a test file
		test_file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "test_self.txt",
				"is_private": 0,
				"file_url": "/files/test_self.txt",
			}
		).insert()

		# Try to merge into itself - should throw error
		with self.assertRaises(frappe.ValidationError):
			merge_files(test_file.name, test_file.name)

		# Clean up
		frappe.delete_doc("File", test_file.name, force=True)

	def test_merge_files_capability_check(self):
		"""Test that capability check works"""
		# Disable capability
		settings = frappe.get_single("Jailbreak Settings")
		settings.file_merge = 0
		settings.save()

		# Create test files
		source_file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "test_source2.txt",
				"is_private": 0,
				"file_url": "/files/test_source2.txt",
			}
		).insert()

		target_file = frappe.get_doc(
			{
				"doctype": "File",
				"file_name": "test_target2.txt",
				"is_private": 0,
				"file_url": "/files/test_target2.txt",
			}
		).insert()

		# Try to merge - should throw permission error
		with self.assertRaises(frappe.PermissionError):
			merge_files(source_file.name, target_file.name)

		# Clean up
		frappe.delete_doc("File", source_file.name, force=True)
		frappe.delete_doc("File", target_file.name, force=True)

		# Re-enable capability
		settings.file_merge = 1
		settings.save()
