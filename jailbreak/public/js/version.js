// Copyright (c) 2026, Avunu LLC and contributors
// For license information, please see license.txt

/* global jailbreak */

frappe.ui.form.on("Version", {
	refresh: function (frm) {
		// Version restore is temporarily disabled server-side (it never actually
		// reverted anything), so don't offer the buttons. Kept for the rewrite.
		// (Function-local: doctype scripts are eval'd into the global scope.)
		const restore_disabled = true;
		if (restore_disabled) return;

		// Check if version restore capability is enabled
		jailbreak.check_capability("version_restore").then((enabled) => {
			if (enabled) {
				if (frm.doc.restored) {
					frm.add_custom_button(__("Open"), function () {
						if (frm.doc.ref_doctype && frm.doc.docname) {
							frappe.set_route("Form", frm.doc.ref_doctype, frm.doc.docname);
						}
					});
				} else {
					frm.add_custom_button(__("Restore"), function () {
						frm.call({
							method: "restore",
							doc: frm.doc,
							callback: function () {
								frm.reload_doc();
							},
						});
					});
				}
			}
		});
	},
});
