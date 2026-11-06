# Copyright (c) 2026, Avunu LLC and contributors
# For license information, please see license.txt

app_name = "data_steward"
app_title = "Data Steward"
app_publisher = "Avunu LLC"
app_description = "Merge duplicate records, convert Items to variants and fix bank clearance dates"
app_email = "mail@avu.nu"
app_license = "MIT"

# Frappe's About dialog takes the logo from here. not_listed keeps the app off the apps screen.
# app_logo_url would change the site's own logo.
add_to_apps_screen = [
	{
		"name": "data_steward",
		"logo": "/assets/data_steward/images/data_steward-logo.svg",
		"title": "Data Steward",
		"route": "/desk",
		"has_permission": "data_steward.apps_screen.not_listed",
	}
]

required_apps = ["erpnext"]

app_include_js = "data_steward.bundle.js"

doctype_js = {
	"Item": "public/js/item.js",
	"Payment Entry": "public/js/payment_entry.js",
	"Journal Entry": "public/js/journal_entry.js",
}

# The desk side panel's preview, plus which fields the user may change there (side_panel.py).
override_whitelisted_methods = {
	"frappe.desk.doc_preview.get_preview": "data_steward.side_panel.get_preview",
}

export_python_type_annotations = True

# Copies the capability toggles from Jailbreak Settings, when the old jailbreak app is still installed.
after_install = "data_steward.install.after_install"
