# Copyright (c) 2026, Avunu LLC and contributors
# For license information, please see license.txt

"""The server half of the editable side panel: the preview says which permlevels the user may
change, and `save` writes only the fields it is given, refusing a stale copy."""

from __future__ import annotations

from typing import Any
from unittest.mock import patch

import frappe
from frappe.model.document import Document

from data_steward.side_panel import get_preview, get_write_permlevels, save
from data_steward.tests import DataStewardIntegrationTestCase
from data_steward.tests.factories import make_journal_entry, make_user

NO_ROLES_USER = "_ds-test-side-panel@example.com"


def _deny(*permtypes: str) -> Any:
	"""Patches `Document.has_permission` to refuse `permtypes` and grant everything else."""
	return patch.object(
		Document,
		"has_permission",
		autospec=True,
		side_effect=lambda _doc, permtype="read", *args, **kwargs: permtype not in permtypes,
	)


class TestPreview(DataStewardIntegrationTestCase):
	def test_core_preview_is_replaced(self):
		overrides = frappe.get_hooks("override_whitelisted_methods")
		self.assertEqual(
			overrides["frappe.desk.doc_preview.get_preview"][-1], "data_steward.side_panel.get_preview"
		)
		self.assertEqual(frappe.allowed_http_methods_for_whitelisted_func[get_preview], ["GET"])

	def test_adds_write_permlevels_to_core_preview(self):
		je = make_journal_entry(submit=False)
		preview = get_preview("Journal Entry", je.name)

		self.assertEqual(preview["doc"]["name"], je.name)
		self.assertIn(0, preview["permlevels"])
		self.assertIn(0, preview["write_permlevels"])
		self.assertEqual(preview["write_permlevels"], je.get_permlevel_access("write"))

	def test_nothing_writable_without_write_permission(self):
		je = make_journal_entry(submit=False)
		with _deny("write"):
			self.assertEqual(get_write_permlevels(je), [])

	def test_submitted_needs_submit_permission(self):
		je = make_journal_entry(submit=True)
		self.assertIn(0, get_write_permlevels(je))
		with _deny("submit"):
			self.assertEqual(get_write_permlevels(je), [])

	def test_nothing_writable_once_cancelled(self):
		je = make_journal_entry(submit=True)
		je.cancel()
		self.assertEqual(get_write_permlevels(je), [])


class TestSave(DataStewardIntegrationTestCase):
	def test_post_only(self):
		self.assertEqual(frappe.allowed_http_methods_for_whitelisted_func[save], ["POST"])

	def test_saves_the_given_fields_and_returns_the_new_preview(self):
		je = make_journal_entry(submit=False)
		preview = save("Journal Entry", je.name, '{"user_remark": "from the side panel"}', str(je.modified))

		self.assertEqual(preview["doc"]["user_remark"], "from the side panel")
		self.assertIn("write_permlevels", preview)
		self.assertEqual(frappe.db.get_value("Journal Entry", je.name, "user_remark"), "from the side panel")

	def test_accepts_a_dict(self):
		je = make_journal_entry(submit=False)
		save("Journal Entry", je.name, {"user_remark": "as a dict"}, str(je.modified))
		self.assertEqual(frappe.db.get_value("Journal Entry", je.name, "user_remark"), "as a dict")

	def test_refuses_a_copy_saved_since(self):
		je = make_journal_entry(submit=False)
		loaded = str(je.modified)
		je.user_remark = "saved elsewhere first"
		je.save()

		with self.assertRaises(frappe.TimestampMismatchError):
			save("Journal Entry", je.name, {"user_remark": "stale"}, loaded)
		self.assertEqual(
			frappe.db.get_value("Journal Entry", je.name, "user_remark"), "saved elsewhere first"
		)

	def test_refuses_tables_standard_and_unknown_fields(self):
		je = make_journal_entry(submit=False)
		for values in ({"accounts": []}, {"docstatus": 1}, {"owner": "Guest"}, {"no_such_field": 1}):
			with self.subTest(values=values), self.assertRaises(frappe.ValidationError):
				save("Journal Entry", je.name, values, str(je.modified))
		self.assertEqual(frappe.db.get_value("Journal Entry", je.name, "docstatus"), 0)

	def test_refuses_values_that_are_not_an_object(self):
		je = make_journal_entry(submit=False)
		with self.assertRaises(frappe.ValidationError):
			save("Journal Entry", je.name, '["user_remark"]', str(je.modified))

	def test_needs_write_permission(self):
		je = make_journal_entry(submit=False)
		make_user(NO_ROLES_USER)
		frappe.set_user(NO_ROLES_USER)
		try:
			with self.assertRaises(frappe.PermissionError):
				save("Journal Entry", je.name, {"user_remark": "not allowed"}, str(je.modified))
		finally:
			frappe.set_user("Administrator")
		self.assertNotEqual(frappe.db.get_value("Journal Entry", je.name, "user_remark"), "not allowed")
