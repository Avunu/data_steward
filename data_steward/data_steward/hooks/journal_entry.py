# Copyright (c) 2026, Avunu LLC and contributors
# For license information, please see license.txt

from typing import TYPE_CHECKING, cast

import frappe
from frappe import _

from data_steward.api import assert_capability
from data_steward.data_steward.doctype.data_steward_settings.data_steward_settings import require_roles

if TYPE_CHECKING:
	from erpnext.accounts.doctype.journal_entry.journal_entry import JournalEntry


def _get_journal_entry_for_clearance(journal_entry_name: str) -> JournalEntry:
	"""Role and document-permission checks shared by both clearance endpoints."""
	require_roles("Accounts Manager", "System Manager")
	journal_entry = cast("JournalEntry", frappe.get_doc("Journal Entry", journal_entry_name))
	journal_entry.check_permission("write")
	# Bank clearance applies to submitted entries only; a draft's is wiped on save
	if journal_entry.docstatus != 1:
		frappe.throw(_("Only a submitted Journal Entry can have a clearance date."))
	return journal_entry


def _add_clearance_comment(
	journal_entry: JournalEntry, old_clearance_date: object, new_clearance_date: object
) -> None:
	journal_entry.add_comment(
		"Edit",
		_("Clearance Date changed from {0} to {1}").format(
			old_clearance_date or _("(none)"), new_clearance_date or _("(none)")
		),
	)


@frappe.whitelist(methods=["POST"])
def manually_clear_journal_entry(journal_entry_name: str) -> str:
	"""Manually clear a journal entry by finding matching bank transaction."""
	# Check if the journal entry manually clear capability is enabled
	assert_capability("journal_entry_manually_clear")
	journal_entry = _get_journal_entry_for_clearance(journal_entry_name)
	old_clearance_date = journal_entry.get("clearance_date")

	# find a matching bank transaction - `payment_entry` is a Dynamic Link,
	# so also pin `payment_document` or a Payment Entry with the same name matches
	bank_transaction_date = frappe.db.get_value(
		"Bank Transaction",
		[
			["Bank Transaction Payments", "payment_document", "=", "Journal Entry"],
			["Bank Transaction Payments", "payment_entry", "=", journal_entry_name],
		],
		"date",
	)
	if not bank_transaction_date:
		return "No matching bank transaction found."

	# set the clearance date on the journal entry; the request commits it
	frappe.db.set_value("Journal Entry", journal_entry_name, "clearance_date", bank_transaction_date)
	_add_clearance_comment(journal_entry, old_clearance_date, bank_transaction_date)
	return f"Journal Entry {journal_entry_name} cleared to {bank_transaction_date}."


@frappe.whitelist(methods=["POST"])
def remove_clearance_date_journal_entry(journal_entry_name: str) -> str:
	"""Remove clearance date from a journal entry."""
	# Check if the journal entry remove clearance capability is enabled
	assert_capability("journal_entry_remove_clearance")
	journal_entry = _get_journal_entry_for_clearance(journal_entry_name)
	old_clearance_date = journal_entry.get("clearance_date")

	frappe.db.set_value("Journal Entry", journal_entry_name, "clearance_date", None)
	_add_clearance_comment(journal_entry, old_clearance_date, None)
	return f"Journal Entry {journal_entry_name} clearance date removed."
