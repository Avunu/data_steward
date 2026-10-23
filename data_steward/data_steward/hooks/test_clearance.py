# Copyright (c) 2026, Avunu LLC and contributors
# For license information, please see license.txt

"""Coverage for `hooks.clearance.validate_clearance_date`, the Bank Clearance
date rule both clearance endpoints share."""

from __future__ import annotations

import datetime

import frappe
from frappe.tests import UnitTestCase

from data_steward.data_steward.hooks.clearance import validate_clearance_date


class TestValidateClearanceDate(UnitTestCase):
	def test_before_cheque_date_is_refused(self):
		with self.assertRaises(frappe.ValidationError):
			validate_clearance_date("2021-01-01", "2021-01-02")

	def test_date_objects_are_compared_too(self):
		with self.assertRaises(frappe.ValidationError):
			validate_clearance_date(datetime.date(2021, 1, 1), datetime.date(2021, 1, 2))

	def test_on_or_after_cheque_date_is_allowed(self):
		validate_clearance_date("2021-01-02", "2021-01-02")
		validate_clearance_date("2021-01-03", "2021-01-02")

	def test_missing_dates_are_not_checked(self):
		# Bank Clearance checks only when both dates are set
		validate_clearance_date(None, "2021-01-02")
		validate_clearance_date("2021-01-01", None)
