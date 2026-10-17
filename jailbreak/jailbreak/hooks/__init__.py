# Copyright (c) 2026, Avunu LLC and contributors
# For license information, please see license.txt

import json

import frappe

from jailbreak.api import assert_capability
from jailbreak.jailbreak.doctype.jailbreak_settings.jailbreak_settings import require_roles


@frappe.whitelist()
def bulk_merge(doctype: str, rows: str) -> list[str]:
	# Check if global bulk merge capability is enabled
	assert_capability("global_bulk_merge")
	# bulk_rename checks write/delete on each row itself; merging across any
	# DocType is still a System Manager decision.
	require_roles("System Manager")

	from frappe.model.rename_doc import bulk_rename

	rows = json.loads(rows)

	return bulk_rename(doctype, rows)
