// Copyright (c) 2026, Avunu LLC and contributors
// For license information, please see license.txt

// Frappe's own File list settings load first (doctype_list_js comes after
// them), so extend them rather than replace them. The File Manager view
// skips `onload`, but every view calls `refresh` after loading its rows.
(() => {
	const settings = frappe.listview_settings["File"] || (frappe.listview_settings["File"] = {});
	const frappe_refresh = settings.refresh;
	settings.refresh = function (view) {
		if (frappe_refresh) {
			frappe_refresh.call(this, view);
		}
		frappe.ui.file_merge.add_list_action(/** @type {frappe.views.ListView} */ (view));
	};
})();
