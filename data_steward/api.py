# Copyright (c) 2026, Avunu LLC and contributors
# For license information, please see license.txt

import frappe

from data_steward.data_steward.doctype.data_steward_settings.data_steward_settings import (
	capability_name,
)


@frappe.whitelist()
def assert_capability(capability: capability_name) -> None:
	from data_steward.data_steward.doctype.data_steward_settings.data_steward_settings import (
		assert_capability as _assert_capability,
	)

	return _assert_capability(capability)


@frappe.whitelist()
def check_capability(capability: capability_name) -> bool:
	from data_steward.data_steward.doctype.data_steward_settings.data_steward_settings import (
		check_capability as _check_capability,
	)

	return _check_capability(capability)
