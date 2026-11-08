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
		// The File list's views are all ListViews. Not `instanceof frappe.views.ListView`: that is
		// merge_records.js's subclass by now, which frappe's FileView and ReportView do not extend.
		if ("get_checked_items" in view) {
			frappe.ui.file_merge.add_list_action(view);
		}
	};
})();
