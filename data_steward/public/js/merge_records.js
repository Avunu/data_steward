// Copyright (c) 2026, Avunu LLC and contributors
// For license information, please see license.txt

/* global data_steward */

frappe.provide("frappe.ui.merge_records");

frappe.ui.merge_records = {
	/** @param {frappe.views.ListView} listview */
	merge_selected_records: function (listview) {
		if (listview.get_checked_items().length < 2) {
			frappe.throw(__("Please select at least two records to merge."));
			return;
		}

		let selected_docs = listview.get_checked_items().map((doc) => doc.name);

		let d = new frappe.ui.Dialog({
			title: __("Merge Records"),
			fields: [
				{
					label: __("Merge into"),
					fieldname: "merge_into",
					fieldtype: "Select",
					options: selected_docs,
					reqd: 1,
				},
			],
			primary_action_label: __("Merge"),
			primary_action: function () {
				let merge_into = d.get_value("merge_into");
				let docs_to_merge = selected_docs.filter((doc) => doc !== merge_into);

				frappe.call({
					method: "data_steward.data_steward.hooks.bulk_merge",
					args: {
						doctype: listview.doctype,
						rows: docs_to_merge.map((doc) => [doc, merge_into, "true"]),
					},
					callback: function (r) {
						if (r.message) {
							listview.clear_checked_items();
							listview.refresh();
						}
					},
				});
				d.hide();
			},
		});
		d.show();
	},
};

// Override the ListView class (the desk bundle loads after frappe's, so it is defined)
const BaseListView = frappe.views.ListView;
if (BaseListView) {
	// The cast restores the generic constructor type (`ListView<TColumn>`) that a subclass loses.
	frappe.views.ListView = /** @type {typeof BaseListView} */ (
		class extends BaseListView {
			/** @param {ConstructorParameters<NonNullable<typeof frappe.views.ListView>>[0]} opts */
			constructor(opts) {
				super(opts);
				this.merge_button_added = false;
			}

			/** @override */
			setup_page() {
				super.setup_page();
				this.add_merge_button();
			}

			add_merge_button() {
				// Frappe only renames (and so merges) DocTypes with Allow Rename set
				if (!this.merge_button_added && this.meta?.allow_rename) {
					// Check if global bulk merge capability is enabled
					data_steward.check_capability("global_bulk_merge").then((enabled) => {
						if (enabled) {
							this.page.add_action_item(__("Merge Selected"), () => {
								frappe.ui.merge_records.merge_selected_records(this);
							});
						}
					});
					this.merge_button_added = true;
				}
			}
		}
	);
}
