# Copyright (c) 2026, Avunu LLC and contributors
# For license information, please see license.txt

"""S1 coverage for `hooks.payment_entry.set_clearance_date`."""

from __future__ import annotations

import frappe
from frappe.tests.classes.context_managers import set_user

from data_steward.data_steward.hooks.payment_entry import set_clearance_date
from data_steward.tests import DataStewardIntegrationTestCase
from data_steward.tests.factories import make_payment_entry, make_user, set_capability


class TestSetClearanceDate(DataStewardIntegrationTestCase):
	def test_disabled_capability_raises_permission_error(self):
		pe = make_payment_entry()
		set_capability("payment_entry_set_clearance_date", 0)

		with self.assertRaises(frappe.PermissionError):
			set_clearance_date(pe.name, "2021-06-15")

	def test_sets_the_clearance_date(self):
		pe = make_payment_entry()

		with self.capability_enabled("payment_entry_set_clearance_date"):
			result = set_clearance_date(pe.name, "2021-06-15")

		self.assertEqual(result, f"Payment Entry {pe.name} clearance date set to 2021-06-15.")
		self.assertEqual(str(frappe.db.get_value("Payment Entry", pe.name, "clearance_date")), "2021-06-15")


class TestSetClearanceDatePermissions(DataStewardIntegrationTestCase):
	"""An enabled capability is not enough on its own: the caller also needs
	Accounts Manager or System Manager, plus write on the Payment Entry."""

	def _clearance_comment_exists(self, name: str) -> bool:
		return bool(
			frappe.db.exists(
				"Comment",
				{
					"reference_doctype": "Payment Entry",
					"reference_name": name,
					"comment_type": "Edit",
					"content": ["like", "%Clearance Date changed from%"],
				},
			)
		)

	def test_user_without_role_raises_permission_error(self):
		# Accounts User can write Payment Entries, but is not an Accounts Manager.
		user = make_user("ds_test_pe_accounts_user@example.com", "Accounts User")
		pe = make_payment_entry(reference_no="_DS-PERM-PE-1")

		with (
			self.capability_enabled("payment_entry_set_clearance_date"),
			set_user(user.name),
			self.assertRaises(frappe.PermissionError),
		):
			set_clearance_date(pe.name, "2021-06-15")

		self.assertIsNone(frappe.db.get_value("Payment Entry", pe.name, "clearance_date"))
		self.assertFalse(self._clearance_comment_exists(pe.name))

	def test_system_manager_without_document_write_raises_permission_error(self):
		"""The role gate is not a bypass of the document's own permissions."""
		user = make_user("ds_test_pe_sysman_only@example.com", "System Manager")
		pe = make_payment_entry(reference_no="_DS-PERM-PE-2")

		with (
			self.capability_enabled("payment_entry_set_clearance_date"),
			set_user(user.name),
			self.assertRaises(frappe.PermissionError),
		):
			set_clearance_date(pe.name, "2021-06-15")

		self.assertIsNone(frappe.db.get_value("Payment Entry", pe.name, "clearance_date"))

	def test_system_manager_succeeds_and_comments(self):
		user = make_user("ds_test_pe_sysman@example.com", "System Manager", "Accounts User")
		pe = make_payment_entry(reference_no="_DS-PERM-PE-3")

		with self.capability_enabled("payment_entry_set_clearance_date"), set_user(user.name):
			set_clearance_date(pe.name, "2021-06-15")

		self.assertEqual(str(frappe.db.get_value("Payment Entry", pe.name, "clearance_date")), "2021-06-15")
		self.assertTrue(self._clearance_comment_exists(pe.name))

	def test_accounts_manager_succeeds_and_comments(self):
		user = make_user("ds_test_pe_accounts_manager@example.com", "Accounts Manager")
		pe = make_payment_entry(reference_no="_DS-PERM-PE-4")

		with self.capability_enabled("payment_entry_set_clearance_date"), set_user(user.name):
			set_clearance_date(pe.name, "2021-06-15")

		self.assertEqual(str(frappe.db.get_value("Payment Entry", pe.name, "clearance_date")), "2021-06-15")
		self.assertTrue(self._clearance_comment_exists(pe.name))


class TestSetClearanceDateDocstatus(DataStewardIntegrationTestCase):
	"""Bank clearance applies to submitted entries only."""

	def test_draft_is_refused(self):
		pe = make_payment_entry(reference_no="_DS-STATUS-PE-1", submit=False)

		with (
			self.capability_enabled("payment_entry_set_clearance_date"),
			self.assertRaises(frappe.ValidationError),
		):
			set_clearance_date(pe.name, "2021-06-15")

		self.assertIsNone(frappe.db.get_value("Payment Entry", pe.name, "clearance_date"))

	def test_cancelled_is_refused(self):
		pe = make_payment_entry(reference_no="_DS-STATUS-PE-2")
		pe.cancel()

		with (
			self.capability_enabled("payment_entry_set_clearance_date"),
			self.assertRaises(frappe.ValidationError),
		):
			set_clearance_date(pe.name, "2021-06-15")

		self.assertIsNone(frappe.db.get_value("Payment Entry", pe.name, "clearance_date"))
