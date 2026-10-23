# Copyright (c) 2026, Avunu LLC and contributors
# For license information, please see license.txt

"""The date check ERPNext's Bank Clearance tool applies before it writes a
clearance date (`BankClearance.update_clearance_date`), shared by the
Payment Entry and Journal Entry clearance endpoints."""

from __future__ import annotations

import datetime

import frappe
from frappe import _
from frappe.utils import formatdate, getdate


def validate_clearance_date(
	clearance_date: str | datetime.date | None, cheque_date: str | datetime.date | None
) -> None:
	"""Refuse a clearance date earlier than the entry's cheque date.

	Like Bank Clearance, the check applies only when both dates are set: a
	cleared date of `None` (removing clearance) and an entry with no cheque
	date are let through, and a clearance date on the cheque date itself is
	allowed.
	"""
	if not (clearance_date and cheque_date):
		return
	clearance, cheque = getdate(clearance_date), getdate(cheque_date)
	if clearance and cheque and clearance < cheque:
		frappe.throw(
			_("Clearance date {0} must be after cheque date {1}.").format(
				formatdate(clearance_date), formatdate(cheque_date)
			),
			title=_("Invalid Clearance Date"),
		)
