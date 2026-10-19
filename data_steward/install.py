# Copyright (c) 2026, Avunu LLC and contributors
# For license information, please see license.txt

"""Install hooks.

Data Steward replaces the old `jailbreak` app. A site switches by installing
`data_steward` while `jailbreak` is still installed, then uninstalling
`jailbreak`, so the capability toggles a System Manager set in Jailbreak
Settings are copied across here, before the old app and its Single go away.
"""

import frappe
from frappe.utils import cint

OLD_SETTINGS = "Jailbreak Settings"
NEW_SETTINGS = "Data Steward Settings"

# Jailbreak Settings field -> Data Steward Settings field. The names match; the
# map is explicit so a field that only the old app has is never copied blindly.
CAPABILITY_FIELDS = {
	"global_bulk_merge": "global_bulk_merge",
	"item_convert_to_variant": "item_convert_to_variant",
	"payment_entry_set_clearance_date": "payment_entry_set_clearance_date",
	"journal_entry_manually_clear": "journal_entry_manually_clear",
	"journal_entry_remove_clearance": "journal_entry_remove_clearance",
}


def _jailbreak_settings_exist() -> bool:
	return bool(frappe.db.exists("DocType", OLD_SETTINGS))


def copy_jailbreak_settings() -> bool:
	"""Copy each capability toggle from Jailbreak Settings into Data Steward
	Settings. A no-op (False) on a site that never had the old app.

	Reads `tabSingles` directly rather than loading the old DocType's
	controller, which belongs to another app.
	"""
	if not _jailbreak_settings_exist():
		return False

	old_values = frappe.db.get_singles_dict(OLD_SETTINGS)

	settings = frappe.get_single(NEW_SETTINGS)
	for old_field, new_field in CAPABILITY_FIELDS.items():
		settings.set(new_field, 1 if cint(old_values.get(old_field)) else 0)
	settings.flags.ignore_permissions = True
	settings.save()
	return True


def after_install() -> None:
	copy_jailbreak_settings()
