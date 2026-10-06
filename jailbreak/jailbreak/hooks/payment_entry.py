import frappe
from frappe import _

from jailbreak import assert_capability
from jailbreak.jailbreak.doctype.jailbreak_settings.jailbreak_settings import require_roles


@frappe.whitelist()
def set_clearance_date(payment_entry_name: str, clearance_date: str | None) -> str:
	"""Set clearance date for a payment entry."""
	# Check if the payment entry set clearance date capability is enabled
	assert_capability("payment_entry_set_clearance_date")
	require_roles("Accounts Manager", "System Manager")

	payment_entry = frappe.get_doc("Payment Entry", payment_entry_name)
	payment_entry.check_permission("write")
	old_clearance_date = payment_entry.get("clearance_date")

	try:
		frappe.db.set_value("Payment Entry", payment_entry_name, "clearance_date", clearance_date)
		payment_entry.add_comment(
			"Edit",
			_("Clearance Date changed from {0} to {1}").format(
				old_clearance_date or _("(none)"), clearance_date or _("(none)")
			),
		)
		frappe.db.commit()
		return f"Payment Entry {payment_entry_name} clearance date set to {clearance_date}."
	except Exception as e:
		frappe.log_error(frappe.get_traceback(), _("Payment Entry Set Clearance Date Error"))
		frappe.throw(_("Error setting payment entry clearance date: {0}").format(str(e)))
