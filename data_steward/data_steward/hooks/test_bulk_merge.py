# Copyright (c) 2026, Avunu LLC and contributors
# For license information, please see license.txt

"""S1 coverage for `hooks.bulk_merge` (`hooks/__init__.py`) - a thin
capability-gated wrapper around Frappe's own `bulk_rename`. Not one of the
5 hook modules the plan names by file, but it lives in the same package and
is whitelisted, destructive, and untested."""

from __future__ import annotations

import json
from unittest.mock import patch

import frappe
from frappe.tests.classes.context_managers import set_user

from data_steward.data_steward.hooks import bulk_merge
from data_steward.tests import DataStewardIntegrationTestCase
from data_steward.tests.factories import make_item, make_user, set_capability


class TestBulkMerge(DataStewardIntegrationTestCase):
	def test_disabled_capability_raises_permission_error(self):
		item = make_item("_DS Test Bulk Guard")
		set_capability("global_bulk_merge", 0)

		with self.assertRaises(frappe.PermissionError):
			bulk_merge("Item", json.dumps([[item.name, "_DS Test Bulk Guard Renamed"]]))

	def test_renames_the_document(self):
		item = make_item("_DS Test Bulk Old")

		with self.capability_enabled("global_bulk_merge"):
			result = bulk_merge("Item", json.dumps([[item.name, "_DS Test Bulk New"]]))

		self.assertEqual(result, [f"Successful: {item.name} to _DS Test Bulk New"])
		self.assertTrue(frappe.db.exists("Item", "_DS Test Bulk New"))
		self.assertFalse(frappe.db.exists("Item", item.name))

	def test_user_without_system_manager_raises_permission_error(self):
		"""Item Manager can rename Items through the core UI, but merging
		across any DocType through this endpoint is System Manager only."""
		user = make_user("ds_test_merge_item_manager@example.com", "Item Manager")
		item = make_item("_DS Test Bulk Perm Denied")

		with (
			self.capability_enabled("global_bulk_merge"),
			set_user(user.name),
			self.assertRaises(frappe.PermissionError),
		):
			bulk_merge("Item", json.dumps([[item.name, "_DS Test Bulk Perm Denied Renamed"]]))

		self.assertTrue(frappe.db.exists("Item", item.name))

	def test_system_manager_succeeds(self):
		# Item Manager for the per-row write/delete checks inside bulk_rename.
		user = make_user("ds_test_merge_sysman@example.com", "System Manager", "Item Manager")
		item = make_item("_DS Test Bulk Perm Old")

		with self.capability_enabled("global_bulk_merge"), set_user(user.name):
			result = bulk_merge("Item", json.dumps([[item.name, "_DS Test Bulk Perm New"]]))

		self.assertEqual(result, [f"Successful: {item.name} to _DS Test Bulk Perm New"])
		self.assertTrue(frappe.db.exists("Item", "_DS Test Bulk Perm New"))

	def test_refused_rows_come_back_as_failed_log_lines(self):
		"""Merge Selected shows this log, so a row Frappe refuses must come back
		as a "Failed" line, not vanish. ToDo has no Allow Rename, which is also
		why the desk no longer offers Merge Selected there."""
		keep = frappe.get_doc({"doctype": "ToDo", "description": "_DS Test merge keep"}).insert()
		drop = frappe.get_doc({"doctype": "ToDo", "description": "_DS Test merge drop"}).insert()

		# bulk_rename rolls back a failed row; keep this test's records.
		with self.capability_enabled("global_bulk_merge"), patch.object(frappe.db, "rollback"):
			result = bulk_merge("ToDo", json.dumps([[drop.name, keep.name, "true"]]))

		self.assertFalse(frappe.get_meta("ToDo").allow_rename)
		self.assertEqual(len(result), 1)
		self.assertIn(f"Failed: {drop.name} to {keep.name}", result[0])
		self.assertIn("not allowed to be renamed", result[0])
		self.assertTrue(frappe.db.exists("ToDo", drop.name))
