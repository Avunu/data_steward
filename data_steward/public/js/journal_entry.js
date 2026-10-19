// Copyright (c) 2026, Avunu LLC and contributors
// For license information, please see license.txt

/* global data_steward */

// add a button "Manually Clear" to the "Journal Entry" form
// the button will find a matching bank transaction and set the corresponding "clearance_date" field
frappe.ui.form.on("Journal Entry", {
	refresh: function (frm) {
		// Check if journal entry manually clear capability is enabled
		data_steward.check_capability("journal_entry_manually_clear").then((enabled) => {
			if (enabled) {
				frm.add_custom_button(
					__("Manually Clear"),
					function () {
						// find a matching bank transaction
						frappe.call({
							method: "data_steward.data_steward.hooks.journal_entry.manually_clear_journal_entry",
							args: {
								journal_entry_name: frm.doc.name,
							},
							callback: function (response) {
								if (response.message) {
									frappe.msgprint(response.message);
								}
							},
						});
					},
					__("Actions"),
				);
			}
		});

		// Check if journal entry remove clearance capability is enabled
		data_steward.check_capability("journal_entry_remove_clearance").then((enabled) => {
			if (enabled) {
				frm.add_custom_button(
					__("Remove Clearance"),
					function () {
						// find a matching bank transaction
						frappe.call({
							method: "data_steward.data_steward.hooks.journal_entry.remove_clearance_date_journal_entry",
							args: {
								journal_entry_name: frm.doc.name,
							},
							callback: function (response) {
								if (response.message) {
									frappe.msgprint(response.message);
								}
							},
						});
					},
					__("Actions"),
				);
			}
		});
	},
});
