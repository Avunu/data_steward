/* global jailbreak */

frappe.listview_settings["File"] = {
	onload: function (listview) {
		// Check if file merge capability is enabled
		jailbreak.check_capability("file_merge").then((enabled) => {
			if (enabled) {
				const action = () => {
					const selected_docs = listview.get_checked_items();
					if (selected_docs.length < 2) {
						frappe.throw(__("Please select at least two files to merge."));
						return;
					}

					let selected_files = selected_docs.map((doc) => doc.name);

					let d = new frappe.ui.Dialog({
						title: __("Merge Files"),
						fields: [
							{
								fieldtype: "HTML",
								fieldname: "merge_info",
								options: `<div class="alert alert-warning">
									<strong>${__("Warning")}:</strong> ${__("This action will merge the selected files into the target file. All references to the merged files will be replaced with the target file, and the merged files will be deleted. This action cannot be undone.")}
								</div>`,
							},
							{
								fieldtype: "Section Break",
							},
							{
								label: __("Merge into (Target File)"),
								fieldname: "merge_into",
								fieldtype: "Select",
								options: selected_files,
								reqd: 1,
								description: __("Select the file to keep. Other files will be merged into this one."),
							},
						],
						primary_action_label: __("Merge"),
						primary_action: function () {
							let merge_into = d.get_value("merge_into");
							let files_to_merge = selected_files.filter((file) => file !== merge_into);

							// Show final confirmation
							frappe.confirm(
								__(
									"Are you sure you want to merge {0} file(s) into {1}? This will delete the merged files and update all references. This action cannot be undone.",
									[files_to_merge.length, merge_into]
								),
								function () {
									// User confirmed, proceed with merge
									frappe.call({
										method: "jailbreak.jailbreak.hooks.file.batch_merge_files",
										args: {
											files_to_merge: files_to_merge,
											target_file: merge_into,
										},
										freeze: true,
										freeze_message: __("Merging files..."),
										callback: function (r) {
											if (!r.exc && r.message && r.message.success) {
												frappe.show_alert({
													message: r.message.message,
													indicator: "green",
												});
												listview.clear_checked_items();
												listview.refresh();
											}
										},
									});
									d.hide();
								}
							);
						},
					});

					d.show();
				};
				listview.page.add_actions_menu_item(__("Merge Files"), action, false);
			}
		});
	},
};
