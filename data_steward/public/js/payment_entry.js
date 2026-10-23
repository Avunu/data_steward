// Copyright (c) 2026, Avunu LLC and contributors
// For license information, please see license.txt

/* global data_steward */

// add a button "Set Clearance Date" to the "Payment Entry" form
// the button will set the corresponding "clearance_date" field
frappe.ui.form.on("Payment Entry", {
	refresh: function (frm) {
		// Bank clearance applies to submitted entries only
		if (frm.doc.docstatus !== 1) return;

		// Check if payment entry set clearance date capability is enabled
		data_steward.check_capability("payment_entry_set_clearance_date").then((enabled) => {
			if (enabled) {
				frm.add_custom_button(__("Set Clearance Date"), function () {
					// open a dialog to change the date
					frappe.prompt(
						[
							{
								fieldname: "clearance_date",
								fieldtype: "Date",
								label: __("Clearance Date"),
								reqd: 1,
								default: frm.doc.clearance_date,
								// The server refuses a date before the cheque date, as
								// ERPNext's Bank Clearance tool does
								min_date: frm.doc.reference_date
									? frappe.datetime.str_to_obj(frm.doc.reference_date)
									: undefined,
							},
						],
						function (values) {
							// change the date
							frappe.call({
								method: "data_steward.data_steward.hooks.payment_entry.set_clearance_date",
								args: {
									payment_entry_name: frm.doc.name,
									clearance_date: values.clearance_date,
								},
								callback: function (response) {
									if (response.message) {
										frappe.msgprint(response.message);
									}
								},
							});
						},
						__("Set Clearance Date"),
						__("Set"),
					);
				});
			}
		});
	},
});
