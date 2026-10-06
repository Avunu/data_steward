/* global jailbreak */

frappe.listview_settings["Version"] = {
	onload: function (doclist) {
		// Version restore is temporarily disabled server-side (it never actually
		// reverted anything), so don't offer the bulk action. Kept for the rewrite.
		// (Function-local: doctype scripts are eval'd into the global scope.)
		const restore_disabled = true;
		if (restore_disabled) return;

		// Check if version restore capability is enabled
		jailbreak.check_capability("version_restore").then((enabled) => {
			if (enabled) {
				const action = () => {
					const selected_docs = doclist.get_checked_items();
					if (selected_docs.length > 0) {
						let docnames = selected_docs.map((doc) => doc.name);
						frappe.call({
							method: "jailbreak.jailbreak.overrides.version.bulk_restore",
							args: { docnames },
							callback: function (r) {
								if (r.message) {
									let body = (restored_items) => {
										const html = restored_items.map((item) => {
											const version = item.version || item;
											const new_name = item.new_name || "";
											if (new_name) {
												return `<li>Version ${version} restored as <a href='/app/form/${new_name}'>${new_name}</a></li>`;
											} else {
												return `<li>Version ${version}</li>`;
											}
										});
										return "<br><ul>" + html.join("");
									};

									let message = (title, items) => {
										return items.length > 0
											? title + body(items) + "</ul>"
											: "";
									};

									const { restored, invalid, failed } = r.message;
									const restored_summary = message(
										__("Versions restored successfully"),
										restored
									);
									const invalid_summary = message(
										__("Versions that were already restored"),
										invalid
									);
									const failed_summary = message(
										__("Versions that failed to restore"),
										failed
									);
									const summary =
										restored_summary + invalid_summary + failed_summary;

									frappe.msgprint(
										summary,
										__("Version Restoration Summary"),
										true
									);

									if (restored.length > 0) {
										doclist.refresh();
									}
								}
							},
						});
					}
				};
				doclist.page.add_actions_menu_item(__("Restore"), action, false);
			}
		});
	},
};
