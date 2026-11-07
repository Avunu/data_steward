// Copyright (c) 2026, Avunu LLC and contributors
// For license information, please see license.txt

/* global data_steward */

// Custom Script for File DocType
frappe.ui.form.on("File", {
	refresh: function (frm) {
		if (frm.is_new() || frm.doc.is_folder) {
			return;
		}
		// Check if the file merge capability is enabled
		data_steward.check_capability("file_merge").then((enabled) => {
			if (enabled) {
				frm.add_custom_button(__("Merge into..."), () => frappe.ui.file_merge.merge_into(frm), __("Actions"));
			}
		});
	},
});
