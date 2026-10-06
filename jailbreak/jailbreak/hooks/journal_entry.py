import frappe
from frappe import _

from jailbreak import assert_capability
from jailbreak.jailbreak.doctype.jailbreak_settings.jailbreak_settings import require_roles


def _get_journal_entry_for_clearance(journal_entry_name: str):
	"""Role and document-permission checks shared by both clearance endpoints."""
	require_roles("Accounts Manager", "System Manager")
	journal_entry = frappe.get_doc("Journal Entry", journal_entry_name)
	journal_entry.check_permission("write")
	return journal_entry


def _add_clearance_comment(journal_entry, old_clearance_date, new_clearance_date) -> None:
	journal_entry.add_comment(
		"Edit",
		_("Clearance Date changed from {0} to {1}").format(
			old_clearance_date or _("(none)"), new_clearance_date or _("(none)")
		),
	)


@frappe.whitelist()
def manually_clear_journal_entry(journal_entry_name: str) -> str:
	"""Manually clear a journal entry by finding matching bank transaction."""
	# Check if the journal entry manually clear capability is enabled
	assert_capability("journal_entry_manually_clear")
	journal_entry = _get_journal_entry_for_clearance(journal_entry_name)
	old_clearance_date = journal_entry.get("clearance_date")

	try:
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
		if bank_transaction_date:
			# set the clearance date on the journal entry
			frappe.db.set_value("Journal Entry", journal_entry_name, "clearance_date", bank_transaction_date)
			_add_clearance_comment(journal_entry, old_clearance_date, bank_transaction_date)
			frappe.db.commit()
			return f"Journal Entry {journal_entry_name} cleared to {bank_transaction_date}."
		else:
			return "No matching bank transaction found."
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), _("Journal Entry Manual Clear Error"))
		frappe.throw(_("Error manually clearing journal entry: {0}").format(str(e)))


@frappe.whitelist()
def remove_clearance_date_journal_entry(journal_entry_name: str) -> str:
	"""Remove clearance date from a journal entry."""
	# Check if the journal entry remove clearance capability is enabled
	assert_capability("journal_entry_remove_clearance")
	journal_entry = _get_journal_entry_for_clearance(journal_entry_name)
	old_clearance_date = journal_entry.get("clearance_date")

	try:
		frappe.db.set_value("Journal Entry", journal_entry_name, "clearance_date", None)
		_add_clearance_comment(journal_entry, old_clearance_date, None)
		frappe.db.commit()
		return f"Journal Entry {journal_entry_name} clearance date removed."
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), _("Journal Entry Remove Clearance Error"))
		frappe.throw(_("Error removing journal entry clearance date: {0}").format(str(e)))
