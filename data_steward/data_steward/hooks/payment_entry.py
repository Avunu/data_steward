# Copyright (c) 2026, Avunu LLC and contributors
# For license information, please see license.txt

import frappe
from frappe import _

from data_steward.api import assert_capability
from data_steward.data_steward.doctype.data_steward_settings.data_steward_settings import require_roles
from data_steward.data_steward.hooks.clearance import validate_clearance_date


@frappe.whitelist(methods=["POST"])
def set_clearance_date(payment_entry_name: str, clearance_date: str | None) -> str:
	"""Set clearance date for a payment entry.

	No commit here: the request commits on success and rolls back on an error.
	"""
	# Check if the payment entry set clearance date capability is enabled
	assert_capability("payment_entry_set_clearance_date")
	require_roles("Accounts Manager", "System Manager")

	payment_entry = frappe.get_doc("Payment Entry", payment_entry_name)
	payment_entry.check_permission("write")
	# Bank clearance applies to submitted entries only
	if payment_entry.docstatus != 1:
		frappe.throw(_("Only a submitted Payment Entry can have a clearance date."))
	# Same rule as ERPNext's Bank Clearance: not before the cheque/reference date
	validate_clearance_date(clearance_date, payment_entry.get("reference_date"))
	old_clearance_date = payment_entry.get("clearance_date")

	frappe.db.set_value("Payment Entry", payment_entry_name, "clearance_date", clearance_date)
	payment_entry.add_comment(
		"Edit",
		_("Clearance Date changed from {0} to {1}").format(
			old_clearance_date or _("(none)"), clearance_date or _("(none)")
		),
	)
	return f"Payment Entry {payment_entry_name} clearance date set to {clearance_date}."
