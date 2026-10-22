# Copyright (c) 2026, Avunu LLC and contributors
# For license information, please see license.txt

app_name = "data_steward"
app_title = "Data Steward"
app_publisher = "Avunu LLC"
app_description = "Merge duplicate records, convert Items to variants and fix bank clearance dates"
app_email = "mail@avu.nu"
app_license = "MIT"

required_apps = ["erpnext"]

app_include_js = "data_steward.bundle.js"

doctype_js = {
	"Item": "public/js/item.js",
	"Payment Entry": "public/js/payment_entry.js",
	"Journal Entry": "public/js/journal_entry.js",
}

export_python_type_annotations = True

# Copies the capability toggles from Jailbreak Settings, when the old jailbreak app is still installed.
after_install = "data_steward.install.after_install"
