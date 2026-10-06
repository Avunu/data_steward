# Copyright (c) 2025, Avunu LLC and contributors
# For license information, please see license.txt

from typing import Literal

import frappe
from frappe import _
from frappe.model.document import Document

capability_name = Literal[
	"global_bulk_merge", 
	"global_unsubmit", 
	"item_convert_to_variant", 
	"version_restore",
	"file_merge",
	"sales_invoice_calculate_outstanding",
	"payment_request_mark_paid",
	"payment_request_reinitiate_charge", 
	"payment_entry_set_clearance_date",
	"journal_entry_manually_clear",
	"journal_entry_remove_clearance",
	"bank_transaction_change_date"
]

capabilities = {
	"global_bulk_merge": "Bulk Merge",
	"global_unsubmit": "Unsubmit",
	"item_convert_to_variant": "Convert to Variant",
	"version_restore": "Version Restore",
	"file_merge": "File Merge",
	"sales_invoice_calculate_outstanding": "Sales Invoice Calculate Outstanding",
	"payment_request_mark_paid": "Payment Request Mark as Paid",
	"payment_request_reinitiate_charge": "Payment Request Re-Initiate Charge",
	"payment_entry_set_clearance_date": "Payment Entry Set Clearance Date",
	"journal_entry_manually_clear": "Journal Entry Manually Clear",
	"journal_entry_remove_clearance": "Journal Entry Remove Clearance",
	"bank_transaction_change_date": "Bank Transaction Change Date",
}


class JailbreakSettings(Document):
	# begin: auto-generated types
	# This code is auto-generated. Do not modify anything in this block.

	from typing import TYPE_CHECKING

	if TYPE_CHECKING:
		from frappe.types import DF

		global_bulk_merge: DF.Check
		global_unsubmit: DF.Check
		item_convert_to_variant: DF.Check
		version_restore: DF.Check
		file_merge: DF.Check
		sales_invoice_calculate_outstanding: DF.Check
		payment_request_mark_paid: DF.Check
		payment_request_reinitiate_charge: DF.Check
		payment_entry_set_clearance_date: DF.Check
		journal_entry_manually_clear: DF.Check
		journal_entry_remove_clearance: DF.Check
		bank_transaction_change_date: DF.Check
	# end: auto-generated types
	pass


@frappe.whitelist()
def check_capability(capability: capability_name) -> bool:
	"""
	Check if a jailbreak capability is enabled (for frontend use).

	:param capability: The capability to check.
	:type capability: capability_name
	:return: True if the capability is enabled, False otherwise.
	:rtype: bool
	"""
	try:
		settings: JailbreakSettings = frappe.get_cached_doc("Jailbreak Settings")  # type: ignore
	except frappe.DoesNotExistError:
		return False

	if capability not in capabilities:
		return False

	return bool(getattr(settings, capability, False))


@frappe.whitelist()
def assert_capability(capability: capability_name) -> None:
	"""
	Check if a jailbreak capability is enabled prior to exposing or using it.

	:param capability: The capability to check.
	:type capability: capability_names
	:raises frappe.PermissionError: If the capability is not enabled.
	:raises frappe.DoesNotExistError: If the Jailbreak Settings document does not exist.
	:raises frappe.ValidationError: If the capability is not recognized.
	"""
	settings: JailbreakSettings
	try:
		settings = frappe.get_cached_doc("Jailbreak Settings")  # type: ignore
	except frappe.DoesNotExistError:
		frappe.throw(
			_("Jailbreak Settings document does not exist."),
			exc=frappe.DoesNotExistError,
		)

	if capability not in capabilities:
		frappe.throw(_("Invalid capability: {0}").format(capability), exc=frappe.ValidationError)

	# Check if the capability is enabled
	if not getattr(settings, capability, False):
		capability_label = capabilities.get(capability, capability)
		frappe.throw(
			_("The {0} capability is not enabled.").format(capability_label),
			exc=frappe.PermissionError,
		)
