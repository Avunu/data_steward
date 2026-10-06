# Copyright (c) 2026, Avunu LLC and contributors
# For license information, please see license.txt

"""S1 coverage for `hooks.journal_entry`'s two functions."""

from __future__ import annotations

import frappe

from jailbreak.jailbreak.hooks.journal_entry import (
	manually_clear_journal_entry,
	remove_clearance_date_journal_entry,
)
from jailbreak.tests import JailbreakIntegrationTestCase
from jailbreak.tests.factories import (
	make_bank_transaction,
	make_cleared_journal_entry,
	make_journal_entry,
	make_user,
	set_capability,
)


class TestManuallyClearJournalEntry(JailbreakIntegrationTestCase):
	def test_disabled_capability_raises_permission_error(self):
		je = make_cleared_journal_entry()
		set_capability("journal_entry_manually_clear", 0)

		with self.assertRaises(frappe.PermissionError):
			manually_clear_journal_entry(je.name)

	def test_clears_against_the_matching_bank_transaction_date(self):
		je = make_cleared_journal_entry(clearance_date="2020-02-02")

		with self.capability_enabled("journal_entry_manually_clear"):
			result = manually_clear_journal_entry(je.name)

		self.assertEqual(result, f"Journal Entry {je.name} cleared to 2020-02-02.")
		self.assertEqual(str(frappe.db.get_value("Journal Entry", je.name, "clearance_date")), "2020-02-02")

	def test_no_matching_bank_transaction_reports_none_found(self):
		je = make_journal_entry()  # no Bank Transaction references it

		with self.capability_enabled("journal_entry_manually_clear"):
			result = manually_clear_journal_entry(je.name)

		self.assertEqual(result, "No matching bank transaction found.")
		self.assertIsNone(frappe.db.get_value("Journal Entry", je.name, "clearance_date"))

	def test_payment_entry_reference_with_the_same_name_is_not_a_match(self):
		"""`payment_entry` on Bank Transaction Payments is a Dynamic Link, so
		the lookup must also filter `payment_document="Journal Entry"`."""
		je = make_journal_entry()
		bt = make_bank_transaction(
			date="2020-03-03",
			deposit=25,
			description="wrong-doctype probe",
			payment_entries=[
				{"payment_document": "Journal Entry", "payment_entry": je.name, "allocated_amount": 25}
			],
		)
		# Same name, different doctype - the shape a name collision with a
		# Payment Entry (or any other payment document) would produce.
		frappe.db.set_value(
			"Bank Transaction Payments", bt.payment_entries[0].name, "payment_document", "Payment Entry"
		)

		with self.capability_enabled("journal_entry_manually_clear"):
			result = manually_clear_journal_entry(je.name)

		self.assertEqual(result, "No matching bank transaction found.")
		self.assertIsNone(frappe.db.get_value("Journal Entry", je.name, "clearance_date"))


class TestRemoveClearanceDateJournalEntry(JailbreakIntegrationTestCase):
	def test_disabled_capability_raises_permission_error(self):
		je = make_journal_entry()
		frappe.db.set_value("Journal Entry", je.name, "clearance_date", "2020-02-02")
		set_capability("journal_entry_remove_clearance", 0)

		with self.assertRaises(frappe.PermissionError):
			remove_clearance_date_journal_entry(je.name)

	def test_removes_an_existing_clearance_date(self):
		je = make_journal_entry()
		frappe.db.set_value("Journal Entry", je.name, "clearance_date", "2020-02-02")

		with self.capability_enabled("journal_entry_remove_clearance"):
			result = remove_clearance_date_journal_entry(je.name)

		self.assertEqual(result, f"Journal Entry {je.name} clearance date removed.")
		self.assertIsNone(frappe.db.get_value("Journal Entry", je.name, "clearance_date"))


def _clearance_comment_exists(name: str) -> bool:
	return bool(
		frappe.db.exists(
			"Comment",
			{
				"reference_doctype": "Journal Entry",
				"reference_name": name,
				"comment_type": "Edit",
				"content": ["like", "%Clearance Date changed from%"],
			},
		)
	)


class TestJournalEntryClearancePermissions(JailbreakIntegrationTestCase):
	"""An enabled capability is not enough on its own: the caller also needs
	Accounts Manager or System Manager, plus write on the Journal Entry."""

	def test_manually_clear_without_role_raises_permission_error(self):
		# Accounts User can write Journal Entries, but is not an Accounts Manager.
		user = make_user("jb_test_je_accounts_user@example.com", "Accounts User")
		je = make_cleared_journal_entry()

		with self.capability_enabled("journal_entry_manually_clear"):
			with self.set_user(user.name):
				with self.assertRaises(frappe.PermissionError):
					manually_clear_journal_entry(je.name)

		self.assertIsNone(frappe.db.get_value("Journal Entry", je.name, "clearance_date"))
		self.assertFalse(_clearance_comment_exists(je.name))

	def test_remove_clearance_without_role_raises_permission_error(self):
		user = make_user("jb_test_je_accounts_user@example.com", "Accounts User")
		je = make_journal_entry()
		frappe.db.set_value("Journal Entry", je.name, "clearance_date", "2020-02-02")

		with self.capability_enabled("journal_entry_remove_clearance"):
			with self.set_user(user.name):
				with self.assertRaises(frappe.PermissionError):
					remove_clearance_date_journal_entry(je.name)

		self.assertEqual(str(frappe.db.get_value("Journal Entry", je.name, "clearance_date")), "2020-02-02")
		self.assertFalse(_clearance_comment_exists(je.name))

	def test_system_manager_without_document_write_raises_permission_error(self):
		"""The role gate is not a bypass of the document's own permissions."""
		user = make_user("jb_test_je_sysman_only@example.com", "System Manager")
		je = make_cleared_journal_entry()

		with self.capability_enabled("journal_entry_manually_clear"):
			with self.set_user(user.name):
				with self.assertRaises(frappe.PermissionError):
					manually_clear_journal_entry(je.name)

	def test_system_manager_manually_clears_and_comments(self):
		user = make_user("jb_test_je_sysman@example.com", "System Manager", "Accounts User")
		je = make_cleared_journal_entry(clearance_date="2020-02-02")

		with self.capability_enabled("journal_entry_manually_clear"):
			with self.set_user(user.name):
				manually_clear_journal_entry(je.name)

		self.assertEqual(str(frappe.db.get_value("Journal Entry", je.name, "clearance_date")), "2020-02-02")
		self.assertTrue(_clearance_comment_exists(je.name))

	def test_accounts_manager_removes_clearance_and_comments(self):
		user = make_user("jb_test_je_accounts_manager@example.com", "Accounts Manager")
		je = make_journal_entry()
		frappe.db.set_value("Journal Entry", je.name, "clearance_date", "2020-02-02")

		with self.capability_enabled("journal_entry_remove_clearance"):
			with self.set_user(user.name):
				remove_clearance_date_journal_entry(je.name)

		self.assertIsNone(frappe.db.get_value("Journal Entry", je.name, "clearance_date"))
		self.assertTrue(_clearance_comment_exists(je.name))
