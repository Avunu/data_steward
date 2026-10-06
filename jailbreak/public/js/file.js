/* global jailbreak */

// Custom Script for File DocType
frappe.ui.form.on("File", {
	refresh: function (frm) {
		if (!frm.is_new()) {
			// Check if file merge capability is enabled
			jailbreak.check_capability("file_merge").then((enabled) => {
				if (enabled) {
					frm.add_custom_button(
						__("Merge Files"),
						function () {
							show_merge_dialog(frm);
						},
						__("Actions")
					);
				}
			});
		}
	},
});

function show_merge_dialog(frm) {
	// Create dialog to select target file
	let merge_dialog = new frappe.ui.Dialog({
		title: __("Merge Files"),
		fields: [
			{
				fieldtype: "HTML",
				fieldname: "merge_info",
				options: `<div class="alert alert-warning">
					<strong>${__("Warning")}:</strong> ${__("This action will merge the current file into the selected target file. All references to the current file will be replaced with the target file, and the current file will be deleted. This action cannot be undone.")}
				</div>`,
			},
			{
				fieldtype: "Section Break",
			},
			{
				label: __("Source File (will be deleted)"),
				fieldname: "source_file_info",
				fieldtype: "HTML",
				options: `<p><strong>${__("File")}:</strong> ${frm.doc.file_name || frm.doc.name}<br/>
					<strong>${__("URL")}:</strong> ${frm.doc.file_url || "N/A"}</p>`,
			},
			{
				fieldtype: "Column Break",
			},
			{
				label: __("Target File (will be kept)"),
				fieldname: "target_file",
				fieldtype: "Link",
				options: "File",
				reqd: 1,
				description: __("Select the file to merge into"),
				get_query: function () {
					return {
						filters: {
							name: ["!=", frm.doc.name],
						},
					};
				},
			},
		],
		primary_action_label: __("Merge"),
		primary_action: function () {
			let target_file = merge_dialog.get_value("target_file");

			// Show confirmation dialog
			frappe.confirm(
				__(
					"Are you sure you want to merge {0} into {1}? This will delete {0} and update all references. This action cannot be undone.",
					[frm.doc.file_name || frm.doc.name, target_file]
				),
				function () {
					// User confirmed, proceed with merge
					frappe.call({
						method: "jailbreak.jailbreak.hooks.file.merge_files",
						args: {
							source_file: frm.doc.name,
							target_file: target_file,
						},
						freeze: true,
						freeze_message: __("Merging files..."),
						callback: function (r) {
							if (!r.exc && r.message && r.message.success) {
								frappe.show_alert({
									message: r.message.message,
									indicator: "green",
								});

								// Redirect to the target file
								frappe.set_route("Form", "File", target_file);
							}
						},
					});
					merge_dialog.hide();
				}
			);
		},
	});

	merge_dialog.show();
}
