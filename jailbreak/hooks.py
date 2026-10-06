app_name = "jailbreak"
app_title = "Jailbreak"
app_publisher = "Avunu LLC"
app_description = "Add destructive superpowers to any Frappe site."
app_email = "mail@avu.nu"
app_license = "MIT"

app_include_js = "jailbreak.bundle.js"

doctype_js = {
	"Item": "public/js/item.js",
	"Version": "public/js/version.js",
	"Payment Entry": "public/js/payment_entry.js",
	"Journal Entry": "public/js/journal_entry.js",
}

doctype_list_js = {
	"Version": "public/js/version_list.js",
}

export_python_type_annotations = True

override_doctype_class = {"Version": "jailbreak.jailbreak.overrides.version.Version"}
